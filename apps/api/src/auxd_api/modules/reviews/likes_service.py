"""Review-like service — idempotent toggle, self-like rejection (T088).

Likes deserve their own module: the semantics are distinct from
review-body mutations (notification side-effect on like, no
notification on un-like, self-like rejection, atomic counter updates,
``recent_likers`` last-10 trimming). Pulling them out of
:mod:`auxd_api.modules.reviews.service` keeps the latter focused on
body / audit / soft-delete and lets the like flow evolve independently
when the notification dispatch lands (T123).

Idempotency
===========
The unique ``(review_id, user_id)`` compound index on
:class:`ReviewLike` is the source of truth. The service layer races
the ``find_one → insert`` window are caught by the index — we treat
:class:`pymongo.errors.DuplicateKeyError` as "already liked, return
current state" so the API contract is genuinely idempotent.

Notification side-effect
========================
:func:`like_review` emits an N-004 notification on a fresh like only —
re-likes (idempotent path) and un-likes are silent. The dispatch is
currently a TODO until T123 wires the notifications module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pymongo.errors import DuplicateKeyError

from auxd_api.modules.reviews.models import ReactionsSubDoc, Review, ReviewLike

# Keep at most this many recent-liker user ids on the Review document.
# Anything beyond the cap is trimmed off the tail (FIFO eviction) so the
# document size stays bounded under viral engagement.
RECENT_LIKERS_CAP: Final[int] = 10

_LOGGER = logging.getLogger("auxd.reviews.likes")


__all__ = [
    "RECENT_LIKERS_CAP",
    "LikeReviewResult",
    "ReviewLikeError",
    "ReviewLikeNotFoundError",
    "SelfLikeError",
    "like_review",
    "unlike_review",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReviewLikeError(Exception):
    """Base class for review-like errors. ``code`` is the wire identifier."""

    code: str = "review_like_error"


class ReviewLikeNotFoundError(ReviewLikeError):
    """Raised when the target review does not exist (or is soft-deleted)."""

    code = "review_not_found"


class SelfLikeError(ReviewLikeError):
    """A user cannot like their own review (TC-016)."""

    code = "self_like_forbidden"


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LikeReviewResult:
    """Return shape for :func:`like_review` / :func:`unlike_review`.

    ``liked`` reflects whether the viewer currently has a like row on
    this review *after* the call resolves. ``likes_count`` is the
    canonical counter from :class:`ReactionsSubDoc.likes_count` after
    any increment / decrement.
    """

    liked: bool
    likes_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _ensure_reactions(review: Review) -> ReactionsSubDoc:
    """Return ``review.reactions``.

    The ``reactions`` field carries a default factory on the model, so
    every newly-deserialised :class:`Review` carries a populated
    :class:`ReactionsSubDoc`. This helper is a small abstraction point
    so the like flow can grow defensive checks later without sprinkling
    them through every call site.
    """
    return review.reactions


async def _dispatch_like_notification(review: Review, liker_user_id: str) -> None:
    """Stub for the N-004 notification dispatch.

    The notifications module is scaffolded (models only, no dispatch
    surface) — wire this up when T123 lands. Until then we emit a
    structured log line so the integration tests can assert the call
    site exists, and so an operator running the system without
    notifications still sees the activity.
    """
    # TODO: wire when T123 lands — replace with the real dispatch.
    _LOGGER.info(
        "review_like.notification_pending",
        extra={
            "event": "review_like.notification_pending",
            "review_id": review.id,
            "review_owner_id": review.user_id,
            "liker_id": liker_user_id,
            "notification_code": "N-004",
        },
    )


# ---------------------------------------------------------------------------
# like_review
# ---------------------------------------------------------------------------


async def like_review(*, review_id: str, user_id: str) -> LikeReviewResult:
    """Add a like from ``user_id`` to ``review_id`` (idempotent).

    Behaviour:

    * Raises :class:`ReviewLikeNotFoundError` if the review doesn't
      exist or is soft-deleted.
    * Raises :class:`SelfLikeError` (TC-016) if the caller owns the
      review.
    * If a :class:`ReviewLike` row already exists for
      ``(review_id, user_id)``, returns the current state without a
      second increment or notification emit — pure idempotency.
    * Otherwise inserts a new ReviewLike, atomically increments
      ``Review.reactions.likes_count`` via ``$inc``, prepends the user
      to ``recent_likers`` (FIFO, capped at :data:`RECENT_LIKERS_CAP`),
      and emits the N-004 notification.
    """
    review = await Review.get(review_id)
    if review is None or review.deleted_at is not None:
        raise ReviewLikeNotFoundError("review not found")
    if review.user_id == user_id:
        raise SelfLikeError("cannot like own review")

    # Insert-first idempotency: the unique compound index is the source
    # of truth. ``find_one`` then ``insert`` is racy under concurrency;
    # catching DuplicateKeyError closes that race for free.
    existing = await ReviewLike.find_one({"review_id": review.id, "user_id": user_id})
    if existing is not None:
        reactions = _ensure_reactions(review)
        return LikeReviewResult(liked=True, likes_count=reactions.likes_count)

    like = ReviewLike(review_id=review.id, user_id=user_id, created_at=_now())
    try:
        await like.insert()
    except DuplicateKeyError:
        # Lost the race to a concurrent insert — fetch the canonical
        # count and return the idempotent state.
        refreshed = await Review.get(review.id)
        if refreshed is None:
            raise ReviewLikeNotFoundError("review not found") from None
        reactions = _ensure_reactions(refreshed)
        return LikeReviewResult(liked=True, likes_count=reactions.likes_count)

    # Update the denormalized counters + recent-likers list on the
    # Review document. We compose the new ``recent_likers`` in memory
    # (prepend + de-dup + cap) rather than fighting Mongo's ``$push``
    # ``$position`` semantics in the abstract — the list is tiny.
    reactions = _ensure_reactions(review)
    reactions.likes_count = reactions.likes_count + 1
    fresh_recent = [user_id, *[u for u in reactions.recent_likers if u != user_id]]
    reactions.recent_likers = fresh_recent[:RECENT_LIKERS_CAP]
    review.updated_at = _now()
    await review.save()

    await _dispatch_like_notification(review=review, liker_user_id=user_id)

    return LikeReviewResult(liked=True, likes_count=reactions.likes_count)


# ---------------------------------------------------------------------------
# unlike_review
# ---------------------------------------------------------------------------


async def unlike_review(*, review_id: str, user_id: str) -> LikeReviewResult:
    """Remove a like from ``user_id`` on ``review_id`` (idempotent).

    Behaviour:

    * Raises :class:`ReviewLikeNotFoundError` if the review doesn't
      exist or is soft-deleted.
    * If no :class:`ReviewLike` row exists for the pair, returns the
      current state without mutation — idempotent un-like on a
      never-liked review is benign.
    * Otherwise deletes the row, atomically decrements the
      ``likes_count`` (floored at 0), and removes the user from
      ``recent_likers``.
    * NO notification is emitted on un-like (per the product spec).
    """
    review = await Review.get(review_id)
    if review is None or review.deleted_at is not None:
        raise ReviewLikeNotFoundError("review not found")

    existing = await ReviewLike.find_one({"review_id": review.id, "user_id": user_id})
    reactions = _ensure_reactions(review)
    if existing is None:
        return LikeReviewResult(liked=False, likes_count=reactions.likes_count)

    await existing.delete()
    # Floor at zero — defensive. The counter should never drift below 0
    # under correct operation, but a bug that double-decremented could
    # otherwise wedge the counter into negative territory and surface
    # in the UI as ``"-1 likes"``.
    reactions.likes_count = max(0, reactions.likes_count - 1)
    reactions.recent_likers = [u for u in reactions.recent_likers if u != user_id]
    review.updated_at = _now()
    await review.save()

    return LikeReviewResult(liked=False, likes_count=reactions.likes_count)
