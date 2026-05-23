"""Social-graph service layer — follow / unfollow / block / un-block (T101 + T102).

Pure async business logic invoked by ``modules/social/routes.py``. The
module owns four mutation paths plus a read helper:

* :func:`follow_user` — create a Follow row (public profile) or a
  FollowRequest (private profile). Idempotent; honours blocks in both
  directions.
* :func:`unfollow_user` — remove the Follow row AND cancel any pending
  FollowRequest. Idempotent (no-op if not following).
* :func:`block_user` — create a Block row and cascade-resolve the social
  graph between the two users: Follow rows in *either* direction get
  deleted, pending FollowRequests in *either* direction get cancelled.
  This is THE Block contract (TC-028).
* :func:`unblock_user` — delete the Block row. Does NOT auto-restore the
  cascaded follows — the user has to re-follow manually.
* :func:`list_blocks` — return the current viewer's blocks for the
  ``GET /users/me/blocks`` surface.

Why a separate service?
=======================
Each path touches multiple collections (Follow, FollowRequest, Block,
User) and the cascade-on-block in particular has non-trivial sequencing:
delete-follows-then-cancel-requests-then-insert-block. Keeping that
logic in pure ``async def`` functions makes it testable in isolation
and lets the route layer focus on HTTP shape + auth + rate-limit
concerns. Errors are signalled via :class:`SocialError` subclasses; the
route layer translates each to the appropriate HTTPException — see
``routes.py``'s ``_SOCIAL_ERROR_STATUS_MAP``.

Notifications stubs
===================
The notifications module (``T123``) is not yet implemented. Where a
follow / follow-request would eventually emit ``N-001`` / ``N-002``, we
leave a structured-log ``# TODO`` and a no-op so the wave can ship
without the dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pymongo.errors import DuplicateKeyError

from auxd_api.modules.social.models import (
    BLOCK_OTHER_REASON_MAX_LEN,
    Block,
    BlockReason,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.social.suggestions_models import (
    Suggestion,
    SuggestionDismissal,
)
from auxd_api.modules.users.models import User

# Block-list pagination ceiling. Block lists are small in practice
# (handfuls per user) so we expose a single page; the constant lives
# here so the route layer can re-use it for sanity-checks.
LIST_BLOCKS_LIMIT: Final[int] = 200


__all__ = [
    "BlockResult",
    "BlockedError",
    "DismissResult",
    "FollowResult",
    "InvalidBlockReasonError",
    "LIST_BLOCKS_LIMIT",
    "MAX_SUGGESTIONS_LIMIT",
    "SUGGESTIONS_DEFAULT_LIMIT",
    "SelfBlockError",
    "SelfFollowError",
    "SocialError",
    "SuggestionEntry",
    "UnblockResult",
    "UserNotFoundError",
    "block_user",
    "dismiss_suggestion",
    "follow_user",
    "list_blocks",
    "list_suggestions",
    "unblock_user",
    "unfollow_user",
]


# Suggestion read-page bounds. The card-stack UI typically pulls 5; the
# hard ceiling stops a hostile client from requesting a 10k-row page.
SUGGESTIONS_DEFAULT_LIMIT: Final[int] = 5
MAX_SUGGESTIONS_LIMIT: Final[int] = 20


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SocialError(Exception):
    """Base class for social-service errors. ``code`` is the wire identifier."""

    code: str = "social_error"


class UserNotFoundError(SocialError):
    """Raised when the target handle resolves to no user."""

    code = "user_not_found"


class SelfFollowError(SocialError):
    """Raised when a user tries to follow themselves."""

    code = "self_follow_forbidden"


class SelfBlockError(SocialError):
    """Raised when a user tries to block themselves."""

    code = "self_block_forbidden"


class BlockedError(SocialError):
    """Raised when a follow is attempted across a Block edge.

    Symmetric: either ``blocker→followee`` or ``followee→blocker`` blocks
    are enough to refuse the follow. The route layer maps this to ``403``.
    """

    code = "blocked"


class InvalidBlockReasonError(SocialError):
    """Raised when the supplied free-text rationale exceeds the cap."""

    code = "invalid_block_reason"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Return ``datetime.now(UTC)`` — wrapped for monkeypatch-friendliness."""
    return datetime.now(UTC)


async def _either_direction_block_exists(user_a: str, user_b: str) -> bool:
    """Return ``True`` if a Block row exists between ``user_a`` and ``user_b`` either way."""
    existing = await Block.find_one(
        {
            "$or": [
                {"blocker_id": user_a, "blockee_id": user_b},
                {"blocker_id": user_b, "blockee_id": user_a},
            ]
        }
    )
    return existing is not None


# ---------------------------------------------------------------------------
# Follow / unfollow
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FollowResult:
    """Return shape for :func:`follow_user`.

    ``state`` is the wire-level state — either ``"accepted"`` (public
    profile, Follow row created) or ``"pending"`` (private profile,
    FollowRequest created). ``follow_id`` is the id of whichever row was
    inserted / found (the Follow row id for accepted, the FollowRequest
    id for pending).
    """

    state: str
    follow_id: str
    followee_id: str


async def follow_user(*, follower_id: str, followee: User) -> FollowResult:
    """Follow ``followee`` from ``follower_id``.

    Behaviour:

    * Refuses self-follow with :class:`SelfFollowError`.
    * Refuses any cross-block edge with :class:`BlockedError` (either
      direction is enough — same symmetry as the visibility matrix).
    * Public profile: idempotently creates a Follow row with
      ``state=ACCEPTED``. If one already exists, returns its current
      state (could be PENDING from legacy data) without mutating.
    * Private profile: idempotently creates a FollowRequest with
      ``status=PENDING``. If one already exists and is still pending,
      returns it. If a previously declined request exists, re-opens it
      (transitions back to PENDING) per the model docstring's
      "re-requests reuse the row" contract.
    """
    if follower_id == followee.id:
        raise SelfFollowError("cannot follow yourself")

    if await _either_direction_block_exists(follower_id, followee.id):
        raise BlockedError("follow blocked")

    if followee.private_profile:
        return await _request_follow_private(follower_id=follower_id, followee=followee)
    return await _follow_public(follower_id=follower_id, followee=followee)


async def _follow_public(*, follower_id: str, followee: User) -> FollowResult:
    """Public-profile follow — direct Follow row with ``state=ACCEPTED``."""
    existing = await Follow.find_one({"follower_id": follower_id, "followee_id": followee.id})
    if existing is not None:
        return FollowResult(
            state=existing.state.value,
            follow_id=existing.id,
            followee_id=followee.id,
        )

    row = Follow(
        follower_id=follower_id,
        followee_id=followee.id,
        state=FollowState.ACCEPTED,
        source="profile",
        created_at=_now(),
    )
    try:
        await row.insert()
    except DuplicateKeyError:
        # Race: another concurrent follow already won. Re-read and
        # return its state.
        existing = await Follow.find_one({"follower_id": follower_id, "followee_id": followee.id})
        if existing is not None:
            return FollowResult(
                state=existing.state.value,
                follow_id=existing.id,
                followee_id=followee.id,
            )
        raise

    # TODO: wire N-001 when notifications module lands at T123
    return FollowResult(
        state=FollowState.ACCEPTED.value,
        follow_id=row.id,
        followee_id=followee.id,
    )


async def _request_follow_private(*, follower_id: str, followee: User) -> FollowResult:
    """Private-profile follow — open or reopen a FollowRequest row.

    No Follow row is created at this step; the approval path (out of
    scope here, future ticket) writes the Follow row with
    ``state=ACCEPTED`` and the request row transitions to
    ``status=ACCEPTED``.
    """
    existing = await FollowRequest.find_one(
        {"requester_id": follower_id, "requestee_id": followee.id}
    )
    if existing is not None:
        if existing.status == FollowRequestStatus.PENDING:
            return FollowResult(
                state="pending",
                follow_id=existing.id,
                followee_id=followee.id,
            )
        if existing.status == FollowRequestStatus.ACCEPTED:
            # The request was already approved. The corresponding Follow
            # row should exist; surface ``accepted`` for client UX.
            return FollowResult(
                state="accepted",
                follow_id=existing.id,
                followee_id=followee.id,
            )
        # Declined / expired — re-open by transitioning back to pending
        # (model docstring contract: "re-requests after decline reuse
        # the row by transitioning status, rather than inserting a
        # duplicate").
        existing.status = FollowRequestStatus.PENDING
        existing.responded_at = None
        await existing.save()
        return FollowResult(
            state="pending",
            follow_id=existing.id,
            followee_id=followee.id,
        )

    row = FollowRequest(
        requester_id=follower_id,
        requestee_id=followee.id,
        status=FollowRequestStatus.PENDING,
        created_at=_now(),
    )
    try:
        await row.insert()
    except DuplicateKeyError:
        existing = await FollowRequest.find_one(
            {"requester_id": follower_id, "requestee_id": followee.id}
        )
        if existing is not None:
            return FollowResult(
                state=existing.status.value,
                follow_id=existing.id,
                followee_id=followee.id,
            )
        raise

    # TODO: wire N-001 when notifications module lands at T123
    # TODO: N-002 follow request notification
    return FollowResult(
        state="pending",
        follow_id=row.id,
        followee_id=followee.id,
    )


async def unfollow_user(*, follower_id: str, followee_id: str) -> bool:
    """Unfollow ``followee_id`` from ``follower_id``.

    Idempotent: returns ``False`` when there was nothing to remove.
    Cancels any pending FollowRequest in the same direction so a private
    profile's pending row doesn't linger after the requester revokes.
    """
    removed = False
    row = await Follow.find_one({"follower_id": follower_id, "followee_id": followee_id})
    if row is not None:
        await row.delete()
        removed = True

    request = await FollowRequest.find_one(
        {
            "requester_id": follower_id,
            "requestee_id": followee_id,
            "status": FollowRequestStatus.PENDING.value,
        }
    )
    if request is not None:
        request.status = FollowRequestStatus.DECLINED
        request.responded_at = _now()
        await request.save()
        removed = True

    return removed


# ---------------------------------------------------------------------------
# Block / unblock
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BlockResult:
    """Return shape for :func:`block_user`."""

    block_id: str
    follows_removed: int
    requests_cancelled: int
    created: bool


@dataclass(frozen=True, slots=True)
class UnblockResult:
    """Return shape for :func:`unblock_user`."""

    removed: bool


def _validate_block_reason(reason: BlockReason, notes: str | None) -> None:
    """Raise :class:`InvalidBlockReasonError` if ``notes`` violates the cap.

    The block ``reason`` enum value is validated by Pydantic at the
    route boundary; this helper enforces the free-text length policy
    for the ``OTHER`` case. We deliberately do NOT mandate ``notes`` for
    ``OTHER`` — moderators can backfill context out-of-band.
    """
    if notes is None:
        return
    if len(notes) > BLOCK_OTHER_REASON_MAX_LEN:
        raise InvalidBlockReasonError("notes too long")
    # ``reason`` parameter only used for symmetry / future per-reason
    # validation; cast to avoid lint warnings about unused argument.
    _ = reason


async def block_user(
    *,
    blocker_id: str,
    blockee: User,
    reason: BlockReason,
    notes: str | None,
) -> BlockResult:
    """Block ``blockee`` from ``blocker_id`` with full cascade-resolve.

    Cascade contract (TC-028):

    * Delete any Follow row in either direction between the two users.
    * Cancel any FollowRequest in either direction by transitioning its
      status to ``DECLINED`` and stamping ``responded_at``.
    * Insert (or update reason on) the Block row.

    Idempotent: if a Block row already exists, the existing reason +
    notes are preserved (we do NOT overwrite — the original moderation
    intent stands), and the cascade lookup re-runs to clean up any
    follow / request rows the user re-created in the meantime.
    """
    if blocker_id == blockee.id:
        raise SelfBlockError("cannot block yourself")

    _validate_block_reason(reason, notes)

    # Cascade: delete every Follow in either direction.
    follow_rows = await Follow.find(
        {
            "$or": [
                {"follower_id": blocker_id, "followee_id": blockee.id},
                {"follower_id": blockee.id, "followee_id": blocker_id},
            ]
        }
    ).to_list()
    for row in follow_rows:
        await row.delete()

    # Cascade: cancel pending FollowRequests in either direction.
    now = _now()
    request_rows = await FollowRequest.find(
        {
            "$or": [
                {
                    "requester_id": blocker_id,
                    "requestee_id": blockee.id,
                    "status": FollowRequestStatus.PENDING.value,
                },
                {
                    "requester_id": blockee.id,
                    "requestee_id": blocker_id,
                    "status": FollowRequestStatus.PENDING.value,
                },
            ]
        }
    ).to_list()
    for req in request_rows:
        req.status = FollowRequestStatus.DECLINED
        req.responded_at = now
        await req.save()

    # Idempotent insert. If the Block row already exists, return it
    # unchanged (preserves original reason + audit trail).
    existing_block = await Block.find_one({"blocker_id": blocker_id, "blockee_id": blockee.id})
    if existing_block is not None:
        return BlockResult(
            block_id=existing_block.id,
            follows_removed=len(follow_rows),
            requests_cancelled=len(request_rows),
            created=False,
        )

    block = Block(
        blocker_id=blocker_id,
        blockee_id=blockee.id,
        reason=reason,
        other_reason=notes,
        created_at=now,
    )
    try:
        await block.insert()
    except DuplicateKeyError:
        existing_block = await Block.find_one({"blocker_id": blocker_id, "blockee_id": blockee.id})
        if existing_block is not None:
            return BlockResult(
                block_id=existing_block.id,
                follows_removed=len(follow_rows),
                requests_cancelled=len(request_rows),
                created=False,
            )
        raise

    return BlockResult(
        block_id=block.id,
        follows_removed=len(follow_rows),
        requests_cancelled=len(request_rows),
        created=True,
    )


async def unblock_user(*, blocker_id: str, blockee_id: str) -> UnblockResult:
    """Un-block ``blockee_id`` from ``blocker_id``. Idempotent.

    Does NOT auto-restore any Follow rows that the cascade-on-block
    deleted — the user has to re-follow manually. This is intentional:
    re-establishing the social edge after a block requires fresh consent
    from the previously-blocked party (and from the user themselves).
    """
    row = await Block.find_one({"blocker_id": blocker_id, "blockee_id": blockee_id})
    if row is None:
        return UnblockResult(removed=False)
    await row.delete()
    return UnblockResult(removed=True)


@dataclass(frozen=True, slots=True)
class BlockListEntry:
    """A single row in the ``GET /users/me/blocks`` response."""

    blockee_id: str
    blockee_handle: str
    blockee_display_name: str
    blocked_at: datetime
    reason: str
    notes: str | None


# ---------------------------------------------------------------------------
# Suggestions (T105) — read + dismiss
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SuggestionEntry:
    """A single row in the ``GET /users/me/suggestions`` response.

    The user-card fields (``handle`` / ``display_name`` / ``avatar_url``)
    are denormalised so the frontend can render the card without an
    extra User lookup. ``score`` and ``reasons`` come straight from the
    precomputed :class:`Suggestion` row; ``computed_at`` lets the UI
    surface "freshness" if it wants.
    """

    user_id: str
    handle: str
    display_name: str
    avatar_url: str | None
    score: float
    reasons: list[str]
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class DismissResult:
    """Return shape for :func:`dismiss_suggestion`.

    ``created`` distinguishes a fresh dismissal from an idempotent re-hit
    so the route layer can emit analytics deterministically. ``removed``
    reports whether a precomputed :class:`Suggestion` row was actually
    deleted on the same call (it might not exist if the user dismissed
    before the worker ever wrote anything, or if the worker has already
    cleaned up).
    """

    created: bool
    removed: bool


async def list_suggestions(
    *,
    viewer_id: str,
    limit: int = SUGGESTIONS_DEFAULT_LIMIT,
) -> list[SuggestionEntry]:
    """Return the viewer's top precomputed suggestions, defence-filtered.

    Reads :class:`Suggestion` rows in ``(user_id, score DESC)`` order and
    joins :class:`User` to materialise the card. Even though the worker
    excludes already-followed and recently-dismissed candidates at write
    time, this function re-applies both filters so a Follow / Dismiss
    between worker runs cannot leak a stale row to the client (defence
    in depth).
    """
    if limit < 1:
        limit = SUGGESTIONS_DEFAULT_LIMIT
    if limit > MAX_SUGGESTIONS_LIMIT:
        limit = MAX_SUGGESTIONS_LIMIT

    # Over-fetch by a small factor so the post-filter pass can still
    # honour ``limit`` after dropping rows that became ineligible
    # between the worker run and now.
    fetch_limit = max(limit * 3, limit + 10)
    rows = (
        await Suggestion.find({"user_id": viewer_id})
        .sort("-score", "_id")
        .limit(fetch_limit)
        .to_list()
    )
    if not rows:
        return []

    candidate_ids = [row.suggested_user_id for row in rows]

    # Recompute the exclusion set: who has the viewer started following
    # / blocking / dismissed since the worker last ran?
    follows = await Follow.find(
        {
            "follower_id": viewer_id,
            "followee_id": {"$in": candidate_ids},
            "state": FollowState.ACCEPTED.value,
        }
    ).to_list()
    already_followed = {row.followee_id for row in follows}

    blocks = await Block.find(
        {
            "$or": [
                {"blocker_id": viewer_id, "blockee_id": {"$in": candidate_ids}},
                {"blocker_id": {"$in": candidate_ids}, "blockee_id": viewer_id},
            ]
        }
    ).to_list()
    blocked: set[str] = set()
    for block in blocks:
        if block.blocker_id == viewer_id:
            blocked.add(block.blockee_id)
        else:
            blocked.add(block.blocker_id)

    dismissals = await SuggestionDismissal.find(
        {"user_id": viewer_id, "suggested_user_id": {"$in": candidate_ids}}
    ).to_list()
    dismissed = {row.suggested_user_id for row in dismissals}

    eligible_rows = [
        row
        for row in rows
        if row.suggested_user_id not in already_followed
        and row.suggested_user_id not in blocked
        and row.suggested_user_id not in dismissed
    ][:limit]
    if not eligible_rows:
        return []

    user_ids = [row.suggested_user_id for row in eligible_rows]
    users = await User.find({"_id": {"$in": user_ids}}).to_list()
    user_map = {user.id: user for user in users}

    out: list[SuggestionEntry] = []
    for row in eligible_rows:
        user = user_map.get(row.suggested_user_id)
        if user is None:
            # User hard-deleted between the worker run and now; skip the
            # row rather than emit a half-populated card.
            continue
        out.append(
            SuggestionEntry(
                user_id=user.id,
                handle=user.handle,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                score=row.score,
                reasons=list(row.reasons),
                computed_at=row.computed_at,
            )
        )
    return out


async def dismiss_suggestion(
    *,
    viewer_id: str,
    suggested_user_id: str,
) -> DismissResult:
    """Dismiss a single suggestion. Idempotent on the unique compound.

    Behaviour:

    * Inserts a :class:`SuggestionDismissal` row. The unique compound
      ``(user_id, suggested_user_id)`` guarantees one row per pair; a
      duplicate insert is caught and returned as a no-op so the endpoint
      is idempotent.
    * Deletes the corresponding :class:`Suggestion` row so the
      suggestion does not reappear in the API surface before the next
      worker run.
    """
    created = False
    try:
        await SuggestionDismissal(
            user_id=viewer_id,
            suggested_user_id=suggested_user_id,
        ).insert()
        created = True
    except DuplicateKeyError:
        # Idempotent — caller already dismissed this candidate.
        created = False

    # Also clear the precomputed row so the API doesn't briefly resurface
    # the candidate between this call and the next worker run.
    existing = await Suggestion.find_one(
        {"user_id": viewer_id, "suggested_user_id": suggested_user_id}
    )
    removed = False
    if existing is not None:
        await existing.delete()
        removed = True

    return DismissResult(created=created, removed=removed)


# ---------------------------------------------------------------------------
# Block list read (existing surface)
# ---------------------------------------------------------------------------


async def list_blocks(*, blocker_id: str) -> list[BlockListEntry]:
    """Return ``blocker_id``'s outgoing Block rows joined with the blockee profile.

    Block lists are small in practice (typical user has zero, motivated
    moderators a few dozen) so we don't paginate at MVP — a single page
    with a hard ceiling at :data:`LIST_BLOCKS_LIMIT` is sufficient. If
    we ever hit that ceiling in real usage we'll revisit with a cursor.
    """
    rows = (
        await Block.find({"blocker_id": blocker_id})
        .sort("-created_at")
        .limit(LIST_BLOCKS_LIMIT)
        .to_list()
    )
    if not rows:
        return []

    blockee_ids = list({row.blockee_id for row in rows})
    users = await User.find({"_id": {"$in": blockee_ids}}).to_list()
    user_map = {user.id: user for user in users}

    out: list[BlockListEntry] = []
    for row in rows:
        user = user_map.get(row.blockee_id)
        if user is None:
            # Defensive: hard-deleted user. Surface the id so moderators
            # can still see the row instead of silently filtering it out.
            handle = ""
            display_name = ""
        else:
            handle = user.handle
            display_name = user.display_name
        out.append(
            BlockListEntry(
                blockee_id=row.blockee_id,
                blockee_handle=handle,
                blockee_display_name=display_name,
                blocked_at=row.created_at,
                reason=row.reason.value,
                notes=row.other_reason,
            )
        )
    return out
