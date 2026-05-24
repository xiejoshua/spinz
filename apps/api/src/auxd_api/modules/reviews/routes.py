"""Reviews HTTP routes — create, edit, delete, like, list (T085-T089).

Endpoints (all under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``POST /reviews`` (T085) — create a new review attached to a diary
  entry. 1:1 enforced; markdown sanitized.
* ``PATCH /reviews/{id}`` (T086) — owner-only patch with audit log.
* ``DELETE /reviews/{id}`` (T087) — owner-only soft-delete.
* ``POST /reviews/{id}/like`` (T088) — idempotent like toggle.
* ``DELETE /reviews/{id}/like`` (T088) — idempotent un-like.
* ``GET /albums/{album_id}/reviews`` (T089) — paginated list of
  reviews for an album with sort, tier ordering, and visibility
  filtering.

Rate limiting (T020):

* create/edit/delete share an authoring budget — most users author a
  handful of reviews a day.
* like/un-like: per-user 30/min mirrors the diary log endpoint —
  legitimate engagement is well under this, scripted spam is caught.
* list endpoint: per-IP only (anonymous-callable) with a comfortable
  budget for scroll-heavy clients.

Observability (Constitution P5):

* Every committed mutation emits a structured event via
  :func:`auxd_api.lib.observability.log_call` plus an analytics event
  via :func:`emit_event` so the funnel (review created → review
  liked) lights up in PostHog.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.lib.visibility import (
    OwnedContent,
    Viewer,
    ViewerRelation,
    can_read_with_relation,
)
from auxd_api.lib.visibility import Visibility as LibVisibility
from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.reviews.likes_service import (
    LikeReviewResult,
    ReviewLikeError,
    ReviewLikeNotFoundError,
    SelfLikeError,
    like_review,
    unlike_review,
)
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.reviews.service import (
    ReviewAlreadyDeletedError,
    ReviewAlreadyExistsError,
    ReviewBodyEmptyError,
    ReviewBodyTooLongError,
    ReviewError,
    ReviewNotFoundError,
    ReviewNotOwnedError,
    UnknownDiaryEntryError,
    create_review,
    delete_review,
    edit_review,
)
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.seeding.service import critic_seed_user_ids
from auxd_api.modules.social.models import Block, Follow, FollowState
from auxd_api.modules.users.models import User
from auxd_api.modules.users.redirect import resolve_handle

_LOGGER = logging.getLogger("auxd.reviews.routes")

router = APIRouter(tags=["reviews"])


# Per-user 30/min — matches the diary log endpoint. Generous for normal
# authoring; defends against scripted abuse beyond that.
_REVIEW_WRITE_RATE_LIMIT = rate_limit(
    endpoint="reviews.write",
    per_user=RateLimit(limit=30, window_seconds=60),
)

# Like / un-like — same 30/min ceiling.
_REVIEW_LIKE_RATE_LIMIT = rate_limit(
    endpoint="reviews.like",
    per_user=RateLimit(limit=30, window_seconds=60),
)

# List endpoint — anonymous-callable, per-IP only. Same shape as the
# diary read endpoint.
_REVIEW_LIST_RATE_LIMIT = rate_limit(
    endpoint="reviews.list",
    per_ip=RateLimit(limit=120, window_seconds=60),
)

_MAX_REVIEW_LIST_LIMIT = 100
_DEFAULT_REVIEW_LIST_LIMIT = 25


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class _CreateReviewRequest(BaseModel):
    """Wire shape for ``POST /reviews``."""

    diary_entry_id: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=10_000)
    visibility: str | None = None


class _EditReviewRequest(BaseModel):
    """Wire shape for ``PATCH /reviews/{id}``."""

    # Empty bodies should hit the dedicated empty-body error from the
    # service rather than Pydantic — we want a 422 with the service's
    # ``review_body_empty`` code, not a generic validation error.
    body: str | None = Field(default=None, max_length=10_000)
    visibility: str | None = None


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


_REVIEW_ERROR_STATUS_MAP: dict[type[ReviewError], int] = {
    UnknownDiaryEntryError: status.HTTP_404_NOT_FOUND,
    ReviewNotFoundError: status.HTTP_404_NOT_FOUND,
    ReviewNotOwnedError: status.HTTP_403_FORBIDDEN,
    ReviewAlreadyExistsError: status.HTTP_409_CONFLICT,
    ReviewBodyEmptyError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ReviewBodyTooLongError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ReviewAlreadyDeletedError: status.HTTP_410_GONE,
}


def _review_error_response(exc: ReviewError) -> HTTPException:
    status_code = _REVIEW_ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.code)


_REVIEW_LIKE_ERROR_STATUS_MAP: dict[type[ReviewLikeError], int] = {
    ReviewLikeNotFoundError: status.HTTP_404_NOT_FOUND,
    SelfLikeError: status.HTTP_400_BAD_REQUEST,
}


def _review_like_error_response(exc: ReviewLikeError) -> HTTPException:
    status_code = _REVIEW_LIKE_ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.code)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


def _optional_session(request: Request) -> Session | None:
    session = getattr(request.state, "session", None)
    return session if isinstance(session, Session) else None


# ---------------------------------------------------------------------------
# Visibility adapters — mirror diary/routes.py
# ---------------------------------------------------------------------------


class _SessionViewer:
    """Minimal :class:`Viewer` adapter wrapping a session user id."""

    __slots__ = ("id",)

    id: str

    def __init__(self, user_id: str) -> None:
        self.id = user_id


class _ReviewContent:
    """Adapter exposing :class:`OwnedContent` for a :class:`Review`."""

    __slots__ = ("deleted_at", "owner_id", "visibility")

    def __init__(self, review: Review) -> None:
        self.owner_id = review.user_id
        try:
            self.visibility = LibVisibility(review.visibility)
        except ValueError:
            self.visibility = LibVisibility.PUBLIC
        self.deleted_at = review.deleted_at


async def _resolve_relations(
    viewer_id: str | None,
    owner_ids: set[str],
) -> dict[str, ViewerRelation]:
    """Compute the viewer's relation to every owner id in one batch.

    Identical shape to the diary read endpoint's helper — kept inlined
    rather than shared because endpoint-specific paging makes a shared
    helper more awkward than the thin duplicate.
    """
    relations: dict[str, ViewerRelation] = {}
    if viewer_id is None:
        return {owner: ViewerRelation.ANONYMOUS for owner in owner_ids}

    others = {owner_id for owner_id in owner_ids if owner_id != viewer_id}
    if viewer_id in owner_ids:
        relations[viewer_id] = ViewerRelation.OWNER

    if not others:
        return relations

    blocks = await Block.find(
        {
            "$or": [
                {"blocker_id": viewer_id, "blockee_id": {"$in": list(others)}},
                {"blocker_id": {"$in": list(others)}, "blockee_id": viewer_id},
            ]
        }
    ).to_list()
    blockers: set[str] = set()
    blocked_by: set[str] = set()
    for block in blocks:
        if block.blocker_id == viewer_id:
            blockers.add(block.blockee_id)
        else:
            blocked_by.add(block.blocker_id)

    follows = await Follow.find(
        {
            "follower_id": viewer_id,
            "followee_id": {"$in": list(others)},
            "state": FollowState.ACCEPTED.value,
        }
    ).to_list()
    follow_set = {follow.followee_id for follow in follows}

    for owner in others:
        if owner in blockers:
            relations[owner] = ViewerRelation.BLOCKER
        elif owner in blocked_by:
            relations[owner] = ViewerRelation.BLOCKED
        elif owner in follow_set:
            relations[owner] = ViewerRelation.FOLLOWER
        else:
            relations[owner] = ViewerRelation.NOT_FOLLOWER
    return relations


async def _load_private_owner_ids(owner_ids: set[str]) -> set[str]:
    """Return the subset of ``owner_ids`` whose User has ``private_profile=True``.

    REV-002: rollup endpoints (album-detail public-reviews, friends list,
    etc.) batch many distinct authors. Loading each author's
    ``private_profile`` flag in one query keeps the per-review visibility
    check O(1) without N+1 lookups.
    """
    if not owner_ids:
        return set()
    rows = await User.find({"_id": {"$in": list(owner_ids)}, "private_profile": True}).to_list()
    return {row.id for row in rows}


def _serialize_review(review: Review) -> dict[str, Any]:
    """Return the wire shape for a review."""
    return {
        "id": review.id,
        "user_id": review.user_id,
        "diary_entry_id": review.diary_entry_id,
        "album_id": review.album_id,
        "body": review.body,
        "visibility": review.visibility,
        "likes_count": review.reactions.likes_count,
        "recent_likers": list(review.reactions.recent_likers),
        "edited_at": review.edited_at.isoformat() if review.edited_at is not None else None,
        "deleted_at": review.deleted_at.isoformat() if review.deleted_at is not None else None,
        "created_at": review.created_at.isoformat(),
    }


def _serialize_user_card(user: User, *, critic_seed_ids: set[str] | None = None) -> dict[str, Any]:
    """Return the minimal user-card payload bundled in the reviews sidecar.

    ``critic_seed_ids`` is the per-batch set of active-critic-seed user
    ids — when provided, the card carries ``is_critic_seed`` so the
    frontend ReviewCard renders the T152 ``· Critic`` suffix.
    """
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_critic_seed": (user.id in critic_seed_ids if critic_seed_ids is not None else False),
    }


def _serialize_album_card(album: Album) -> dict[str, Any]:
    """Return the minimal album-card payload bundled in the reviews-by-user sidecar.

    Mirrors :func:`auxd_api.modules.diary.routes._serialize_album_card`
    — the user-reviews endpoint joins each review to its album so the
    client can render a card with cover + title + artist without a
    per-row roundtrip. The full album detail still lives behind
    ``GET /api/v1/albums/{id}``.
    """
    return {
        "id": album.id,
        "mbid": album.mbid,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
    }


# ---------------------------------------------------------------------------
# T085 — POST /reviews
# ---------------------------------------------------------------------------


@router.post(
    "/reviews",
    dependencies=[Depends(_REVIEW_WRITE_RATE_LIMIT)],
)
async def post_review(
    payload: _CreateReviewRequest,
    response: Response,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Create a new review attached to a diary entry.

    Returns ``201`` on a fresh insert. Failure modes:

    * ``404`` — diary entry not found or deleted.
    * ``403`` — caller is not the diary entry's owner.
    * ``409`` — a Review already exists for that diary entry (1:1).
    * ``422`` — body empty after sanitization or over the length cap.
    """
    started = time.perf_counter()
    try:
        result = await create_review(
            user_id=session.user_id,
            diary_entry_id=payload.diary_entry_id,
            body=payload.body,
            visibility=payload.visibility,
        )
    except ReviewError as exc:
        log_call(
            provider="auxd",
            endpoint="reviews.create_rejected",
            latency_ms=(time.perf_counter() - started) * 1000,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id},
        )
        raise _review_error_response(exc) from exc

    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="reviews.create_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "review_id": result.review.id,
            "diary_entry_id": result.diary_entry.id,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="review.create",
        properties={
            "duration_ms": duration_ms,
            "review_id": result.review.id,
            "album_id": result.review.album_id,
            "visibility": result.review.visibility,
        },
    )
    response.status_code = status.HTTP_201_CREATED
    return _serialize_review(result.review)


# ---------------------------------------------------------------------------
# T086 — PATCH /reviews/{id}
# ---------------------------------------------------------------------------


@router.patch(
    "/reviews/{review_id}",
    dependencies=[Depends(_REVIEW_WRITE_RATE_LIMIT)],
)
async def patch_review(
    review_id: str,
    payload: _EditReviewRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Patch an existing review — owner-only.

    Audit-log row is appended to :class:`ReviewEditHistory` before the
    update lands. Failure modes:

    * ``404`` — review not found or soft-deleted.
    * ``403`` — caller is not the review's owner.
    * ``422`` — body empty after sanitization.
    """
    try:
        review = await edit_review(
            review_id=review_id,
            user_id=session.user_id,
            body=payload.body,
            visibility=payload.visibility,
        )
    except ReviewError as exc:
        log_call(
            provider="auxd",
            endpoint="reviews.edit_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "review_id": review_id,
            },
        )
        raise _review_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="reviews.edit_committed",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": session.user_id,
            "review_id": review.id,
            "audit_written": review.__dict__.get("_audit_written", False),
        },
    )
    emit_event(
        user_id=session.user_id,
        event="review.edit",
        properties={"review_id": review.id, "album_id": review.album_id},
    )
    return _serialize_review(review)


# ---------------------------------------------------------------------------
# T087 — DELETE /reviews/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_REVIEW_WRITE_RATE_LIMIT)],
)
async def delete_review_endpoint(
    review_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Soft-delete a review — owner-only. Returns 204 on success.

    Failure modes:

    * ``404`` — review not found.
    * ``403`` — caller is not the review's owner.
    * ``410`` — review already deleted (idempotent double-delete).
    """
    try:
        review = await delete_review(review_id=review_id, user_id=session.user_id)
    except ReviewError as exc:
        log_call(
            provider="auxd",
            endpoint="reviews.delete_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "review_id": review_id,
            },
        )
        raise _review_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="reviews.delete_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "review_id": review.id},
    )
    emit_event(
        user_id=session.user_id,
        event="review.delete",
        properties={"review_id": review.id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# T088 — POST/DELETE /reviews/{id}/like
# ---------------------------------------------------------------------------


def _serialize_like_result(result: LikeReviewResult) -> dict[str, Any]:
    return {"liked": result.liked, "likes_count": result.likes_count}


@router.post(
    "/reviews/{review_id}/like",
    dependencies=[Depends(_REVIEW_LIKE_RATE_LIMIT)],
)
async def post_review_like(
    review_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Like a review (idempotent).

    Failure modes:

    * ``404`` — review not found or deleted.
    * ``400`` — caller is the review's author (self-like rejected).
    """
    try:
        result = await like_review(review_id=review_id, user_id=session.user_id)
    except ReviewLikeError as exc:
        log_call(
            provider="auxd",
            endpoint="reviews.like_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "review_id": review_id,
            },
        )
        raise _review_like_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="reviews.like_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "review_id": review_id},
    )
    emit_event(
        user_id=session.user_id,
        event="review.like",
        properties={"review_id": review_id, "likes_count": result.likes_count},
    )
    return _serialize_like_result(result)


@router.delete(
    "/reviews/{review_id}/like",
    dependencies=[Depends(_REVIEW_LIKE_RATE_LIMIT)],
)
async def delete_review_like(
    review_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Remove a like (idempotent). NO notification emitted on un-like.

    Failure modes:

    * ``404`` — review not found or deleted.
    """
    try:
        result = await unlike_review(review_id=review_id, user_id=session.user_id)
    except ReviewLikeError as exc:
        log_call(
            provider="auxd",
            endpoint="reviews.unlike_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "review_id": review_id,
            },
        )
        raise _review_like_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="reviews.unlike_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "review_id": review_id},
    )
    emit_event(
        user_id=session.user_id,
        event="review.unlike",
        properties={"review_id": review_id, "likes_count": result.likes_count},
    )
    return _serialize_like_result(result)


# ---------------------------------------------------------------------------
# T089 — GET /albums/{album_id}/reviews
# ---------------------------------------------------------------------------


_SORT_NEWEST = "newest"
_SORT_MOST_LIKED = "most_liked"
_SORT_HIGHEST_RATED = "highest_rated"
_ALLOWED_SORTS = frozenset({_SORT_NEWEST, _SORT_MOST_LIKED, _SORT_HIGHEST_RATED})


def _encode_cursor(payload: dict[str, Any]) -> str:
    """Encode a sort-specific cursor payload as a URL-safe token."""
    raw = json.dumps(payload, separators=(",", ":"), default=str)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> dict[str, Any] | None:
    """Inverse of :func:`_encode_cursor`. Returns ``None`` on malformed input."""
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _tier_key(
    review: Review,
    *,
    friend_owner_ids: frozenset[str],
    critic_seed_owner_ids: frozenset[str],
) -> int:
    """Tier ordering — 0 = friends, 1 = public, 2 = critic-seed.

    Tier boundaries are NOT exposed to the client. Within a tier the
    chosen sort applies; across tiers we merge with friends first,
    then public, then critic-seed.
    """
    if review.user_id in friend_owner_ids:
        return 0
    if review.user_id in critic_seed_owner_ids:
        return 2
    return 1


@router.get(
    "/albums/{album_id}/reviews",
    dependencies=[Depends(_REVIEW_LIST_RATE_LIMIT)],
)
async def get_album_reviews(
    album_id: str,
    request: Request,
    sort: Annotated[str, Query(pattern="^(newest|most_liked|highest_rated)$")] = _SORT_NEWEST,
    cursor: str | None = None,
    limit: int = _DEFAULT_REVIEW_LIST_LIMIT,
) -> dict[str, Any]:
    """Paginated list of reviews for an album with sort + tier ordering.

    Query params:

    * ``sort`` — ``newest`` (default), ``most_liked``, ``highest_rated``.
    * ``cursor`` — opaque token from a prior call.
    * ``limit`` — page size, default 25, capped at 100.

    Response shape::

        {
            "reviews": [{...}, ...],
            "next_cursor": "<base64>" | null,
            "users": { "<user_id>": {id, handle, display_name, avatar_url}, ... }
        }

    Tier ordering (NOT exposed to the client):

    1. **Friends** — reviews by users the viewer ACCEPTED-follows.
    2. **Public** — any other public-visibility review.
    3. **Critic seed** — reviews authored by users in the
       :class:`CriticSeed` roster.

    Within each tier, the requested sort applies. Visibility / block
    filtering happens via the standard :class:`OwnedContent` matrix.

    Returns ``HTTP 404`` when the album id is unknown.
    """
    if limit < 1:
        limit = _DEFAULT_REVIEW_LIST_LIMIT
    if limit > _MAX_REVIEW_LIST_LIMIT:
        limit = _MAX_REVIEW_LIST_LIMIT

    if sort not in _ALLOWED_SORTS:
        # The Query pattern already validates this, but defensive coding
        # keeps the contract obvious to readers.
        sort = _SORT_NEWEST

    album = await Album.get(album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="album_not_found")

    session = _optional_session(request)
    viewer: Viewer | None = None
    viewer_id: str | None = None
    if session is not None:
        viewer_id = session.user_id
        viewer = _SessionViewer(viewer_id)

    # The list endpoint over-fetches by a small buffer so the tier sort
    # + visibility filter don't shrink the page below the requested
    # limit. The buffer is capped so worst-case payload stays bounded.
    fetch_limit = min(limit * 4, _MAX_REVIEW_LIST_LIMIT * 4)

    reviews = await _fetch_album_reviews(
        album_id=album_id,
        sort=sort,
        cursor=cursor,
        fetch_limit=fetch_limit,
    )

    # Resolve viewer relations to every review's author.
    owner_ids = {review.user_id for review in reviews}
    relations = await _resolve_relations(viewer_id, owner_ids)

    # REV-002: batch-load each author's ``private_profile`` flag so the
    # visibility matrix can demote PUBLIC content authored by a private-
    # profile user to FOLLOWERS scope. The fan-out is bounded by the
    # already-bounded ``fetch_limit``; deduped on ``owner_id``.
    private_owner_ids = await _load_private_owner_ids(owner_ids)

    # Visibility filter.
    visible: list[Review] = []
    for review in reviews:
        content = _ReviewContent(review)
        relation = relations.get(
            review.user_id,
            ViewerRelation.ANONYMOUS if viewer_id is None else ViewerRelation.NOT_FOLLOWER,
        )
        if can_read_with_relation(
            viewer,
            content,
            relation,
            owner_is_private=review.user_id in private_owner_ids,
        ):
            visible.append(review)

    # Tier classification: friends + critic-seed owner-id sets.
    friend_owner_ids: frozenset[str] = frozenset()
    if viewer_id is not None and owner_ids - {viewer_id}:
        friend_rows = await Follow.find(
            {
                "follower_id": viewer_id,
                "followee_id": {"$in": list(owner_ids - {viewer_id})},
                "state": FollowState.ACCEPTED.value,
            }
        ).to_list()
        friend_owner_ids = frozenset(f.followee_id for f in friend_rows)

    critic_seed_owner_ids: frozenset[str] = frozenset()
    if owner_ids:
        critic_rows = await CriticSeed.find(
            {"user_id": {"$in": list(owner_ids)}, "active": True}
        ).to_list()
        critic_seed_owner_ids = frozenset(c.user_id for c in critic_rows)

    # Tier-sort the visible list. Stable sort preserves the in-tier
    # ordering produced by the upstream Mongo sort.
    visible.sort(
        key=lambda r: _tier_key(
            r,
            friend_owner_ids=friend_owner_ids,
            critic_seed_owner_ids=critic_seed_owner_ids,
        )
    )

    # Page-size cap + next-cursor computation. The cursor is derived
    # from the LAST visible row's sort key so the next page picks up
    # from there. If we trimmed because we filled the requested
    # ``limit``, emit a cursor; otherwise the page is the tail.
    page = visible[:limit]
    next_cursor: str | None = None
    if len(visible) > limit and page:
        last = page[-1]
        next_cursor = _cursor_for(sort=sort, review=last)

    # User-card sidecar for every author on the page.
    page_owner_ids = {review.user_id for review in page}
    users_payload: dict[str, dict[str, Any]] = {}
    if page_owner_ids:
        user_rows = await User.find({"_id": {"$in": list(page_owner_ids)}}).to_list()
        critic_seed_ids = await critic_seed_user_ids([row.id for row in user_rows])
        users_payload = {
            user.id: _serialize_user_card(user, critic_seed_ids=critic_seed_ids)
            for user in user_rows
        }

    return {
        "reviews": [_serialize_review(review) for review in page],
        "next_cursor": next_cursor,
        "users": users_payload,
    }


def _cursor_for(*, sort: str, review: Review) -> str:
    """Return an opaque cursor token encoding the review's sort key."""
    if sort == _SORT_MOST_LIKED:
        return _encode_cursor(
            {
                "s": sort,
                "lc": review.reactions.likes_count,
                "c": review.created_at.isoformat(),
                "i": review.id,
            }
        )
    if sort == _SORT_HIGHEST_RATED:
        return _encode_cursor(
            {
                "s": sort,
                "c": review.created_at.isoformat(),
                "i": review.id,
            }
        )
    return _encode_cursor(
        {
            "s": sort,
            "c": review.created_at.isoformat(),
            "i": review.id,
        }
    )


async def _fetch_album_reviews(
    *,
    album_id: str,
    sort: str,
    cursor: str | None,
    fetch_limit: int,
) -> list[Review]:
    """Query reviews for an album under the given sort + cursor.

    The ``highest_rated`` sort needs the diary entry's rating, which
    lives on :class:`DiaryEntry`. Rather than an aggregation pipeline
    (Beanie's typed aggregate API is awkward with optional fields
    today), we fetch reviews + the matching diary entries in two
    queries and sort in memory. The list is bounded by ``fetch_limit``
    so this is O(N log N) on a small N.
    """
    decoded = _decode_cursor(cursor) if cursor else None
    base_filter: dict[str, Any] = {"album_id": album_id, "deleted_at": None}

    if sort == _SORT_NEWEST:
        if decoded is not None:
            cursor_created = decoded.get("c")
            cursor_id = decoded.get("i")
            if isinstance(cursor_created, str) and isinstance(cursor_id, str):
                try:
                    cursor_dt = datetime.fromisoformat(cursor_created)
                except ValueError:
                    cursor_dt = None
                if cursor_dt is not None:
                    base_filter["$or"] = [
                        {"created_at": {"$lt": cursor_dt}},
                        {"created_at": cursor_dt, "_id": {"$lt": cursor_id}},
                    ]
        return (
            await Review.find(base_filter).sort("-created_at", "-_id").limit(fetch_limit).to_list()
        )

    if sort == _SORT_MOST_LIKED:
        if decoded is not None:
            cursor_likes = decoded.get("lc")
            cursor_created = decoded.get("c")
            cursor_id = decoded.get("i")
            if isinstance(cursor_likes, int) and isinstance(cursor_id, str):
                try:
                    cursor_dt = (
                        datetime.fromisoformat(cursor_created)
                        if isinstance(cursor_created, str)
                        else None
                    )
                except ValueError:
                    cursor_dt = None
                if cursor_dt is not None:
                    base_filter["$or"] = [
                        {"reactions.likes_count": {"$lt": cursor_likes}},
                        {
                            "reactions.likes_count": cursor_likes,
                            "created_at": {"$lt": cursor_dt},
                        },
                        {
                            "reactions.likes_count": cursor_likes,
                            "created_at": cursor_dt,
                            "_id": {"$lt": cursor_id},
                        },
                    ]
        return (
            await Review.find(base_filter)
            .sort("-reactions.likes_count", "-created_at", "-_id")
            .limit(fetch_limit)
            .to_list()
        )

    # highest_rated
    if decoded is not None:
        cursor_created = decoded.get("c")
        cursor_id = decoded.get("i")
        if isinstance(cursor_created, str) and isinstance(cursor_id, str):
            try:
                cursor_dt = datetime.fromisoformat(cursor_created)
            except ValueError:
                cursor_dt = None
            if cursor_dt is not None:
                base_filter["$or"] = [
                    {"created_at": {"$lt": cursor_dt}},
                    {"created_at": cursor_dt, "_id": {"$lt": cursor_id}},
                ]
    reviews = (
        await Review.find(base_filter).sort("-created_at", "-_id").limit(fetch_limit).to_list()
    )
    # Join with DiaryEntry.rating then sort by rating DESC, created_at DESC.
    diary_ids = [r.diary_entry_id for r in reviews]
    entries = await DiaryEntry.find({"_id": {"$in": diary_ids}}).to_list()
    rating_by_entry = {entry.id: entry.rating for entry in entries}
    reviews.sort(
        key=lambda r: (
            -(rating_by_entry.get(r.diary_entry_id) or 0),
            -int(r.created_at.timestamp() * 1000),
        )
    )
    return reviews


# ---------------------------------------------------------------------------
# T093a — GET /reviews/{review_id} (single-review fetch for SSR reading view)
# ---------------------------------------------------------------------------


@router.get(
    "/reviews/{review_id}",
    dependencies=[Depends(_REVIEW_LIST_RATE_LIMIT)],
)
async def get_review_by_id(review_id: str, request: Request) -> dict[str, Any]:
    """Fetch a single review by id with reviewer + album + viewer-entry sidecars.

    Powers the ``/review/[id]`` SSR route (T093a). Visibility is enforced
    via the same matrix used for the list endpoint — non-readers get
    ``HTTP 404`` (not 403) so we don't leak the existence of private or
    block-hidden reviews.

    Response shape::

        {
            "review": {...},                 // _serialize_review
            "user": {...} | null,            // reviewer's UserCard
            "album": {...},                  // album payload (mirror of /albums/{id})
            "viewer_entry": {...} | null     // viewer's own DiaryEntry on this album, if any
        }
    """
    review = await Review.get(review_id)
    if review is None or review.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review_not_found")

    session = _optional_session(request)
    viewer: Viewer | None = None
    viewer_id: str | None = None
    if session is not None:
        viewer_id = session.user_id
        viewer = _SessionViewer(viewer_id)

    relations = await _resolve_relations(viewer_id, {review.user_id})
    relation = relations.get(
        review.user_id,
        ViewerRelation.ANONYMOUS if viewer_id is None else ViewerRelation.NOT_FOLLOWER,
    )
    # REV-002: load the author's ``private_profile`` flag so the matrix
    # can demote PUBLIC content to FOLLOWERS scope when the author has
    # gone private. The User row is also needed for the user-card
    # payload below, so the lookup is reused.
    author = await User.get(review.user_id)
    author_is_private = author.private_profile if author is not None else False
    if not can_read_with_relation(
        viewer,
        _ReviewContent(review),
        relation,
        owner_is_private=author_is_private,
    ):
        # 404, not 403, to avoid leaking existence to non-readers.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review_not_found")

    album = await Album.get(review.album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="album_not_found")

    # Reuse the lookup performed above for the visibility check.
    user = author

    viewer_entry_payload: dict[str, Any] | None = None
    if viewer_id is not None:
        viewer_entry = await DiaryEntry.find_one(
            {"user_id": viewer_id, "album_id": review.album_id, "deleted_at": None}
        )
        if viewer_entry is not None:
            viewer_entry_payload = {
                "id": viewer_entry.id,
                "user_id": viewer_entry.user_id,
                "logged_at": viewer_entry.logged_at.isoformat(),
                "rating": viewer_entry.rating,
                "auxed": viewer_entry.auxed,
                "review_id": viewer_entry.review_id,
                "visibility": viewer_entry.visibility.value,
            }

    if user is not None:
        critic_seed_ids = await critic_seed_user_ids([user.id])
        user_card = _serialize_user_card(user, critic_seed_ids=critic_seed_ids)
    else:
        user_card = None
    return {
        "review": _serialize_review(review),
        "user": user_card,
        "album": _serialize_album_payload(album),
        "viewer_entry": viewer_entry_payload,
    }


def _serialize_album_payload(album: Album) -> dict[str, Any]:
    """Mirror of ``albums/routes.py::_serialize_album`` — the shape consumed
    by the frontend `AlbumPayload` type so the reading-view hero can reuse
    the album-detail component patterns.
    """
    return {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
        "label": album.label,
        "genres": list(album.genres),
        "tracklist": [
            {
                "position": track.position,
                "title": track.title,
                "duration_ms": track.duration_ms,
                "artist_credit": getattr(track, "artist_credit", None),
            }
            for track in album.tracklist
        ],
        "duration_ms": album.duration_ms,
        "source": album.source.value,
    }


# ---------------------------------------------------------------------------
# T094 — GET /users/{handle}/reviews (reviews-only profile sub-route)
# ---------------------------------------------------------------------------


@router.get(
    "/users/{handle}/reviews",
    dependencies=[Depends(_REVIEW_LIST_RATE_LIMIT)],
)
async def get_user_reviews(
    handle: str,
    request: Request,
    sort: Annotated[str, Query(pattern="^(newest|most_liked|highest_rated)$")] = _SORT_NEWEST,
    cursor: str | None = None,
    limit: int = _DEFAULT_REVIEW_LIST_LIMIT,
) -> dict[str, Any]:
    """Paginated list of reviews authored by a single user.

    Mirrors :func:`get_album_reviews` (T089) but keys off the author's
    user-id instead of the album id, and skips the tier classification —
    every row on this surface is authored by the same person, so
    friends-vs-public ordering is meaningless.

    Query params:

    * ``sort`` — ``newest`` (default), ``most_liked``, ``highest_rated``.
    * ``cursor`` — opaque token from a prior call.
    * ``limit`` — page size, default 25, capped at 100.

    Response shape::

        {
            "reviews": [{...}, ...],
            "next_cursor": "<base64>" | null,
            "users":  { "<user_id>": {id, handle, display_name, avatar_url} },
            "albums": { "<album_id>": {id, mbid, title, artist_credit, ...} }
        }

    Visibility is enforced via the standard
    :func:`auxd_api.lib.visibility.can_read_with_relation` matrix — the
    owner always sees own private rows; an anonymous viewer sees only
    public; followers see followers-only rows; blocks suppress
    mutually.

    Handle redirects via :func:`auxd_api.modules.users.redirect.resolve_handle`
    so old ``@handle`` URLs keep working. Returns ``HTTP 404`` when the
    handle has no matching user (current or redirected).
    """
    if limit < 1:
        limit = _DEFAULT_REVIEW_LIST_LIMIT
    if limit > _MAX_REVIEW_LIST_LIMIT:
        limit = _MAX_REVIEW_LIST_LIMIT

    if sort not in _ALLOWED_SORTS:
        sort = _SORT_NEWEST

    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    session = _optional_session(request)
    viewer: Viewer | None = None
    viewer_id: str | None = None
    if session is not None:
        viewer_id = session.user_id
        viewer = _SessionViewer(viewer_id)

    # Over-fetch a small buffer so visibility filtering can't shrink
    # the page below the requested ``limit``. Cap so the worst-case
    # payload stays bounded.
    fetch_limit = min(limit * 4, _MAX_REVIEW_LIST_LIMIT * 4)

    reviews = await _fetch_user_reviews(
        user_id=target.id,
        sort=sort,
        cursor=cursor,
        fetch_limit=fetch_limit,
    )

    # Visibility filter against the single author. ``_resolve_relations``
    # handles owner / blocks / follows in one batched query.
    relations = await _resolve_relations(viewer_id, {target.id})
    relation = relations.get(
        target.id,
        ViewerRelation.ANONYMOUS if viewer_id is None else ViewerRelation.NOT_FOLLOWER,
    )

    # REV-002: a private-profile target demotes PUBLIC content to
    # FOLLOWERS scope so anonymous / non-follower viewers cannot read
    # reviews authored by a user who flipped their profile private.
    owner_is_private = target.private_profile

    visible: list[Review] = []
    for review in reviews:
        if can_read_with_relation(
            viewer,
            _ReviewContent(review),
            relation,
            owner_is_private=owner_is_private,
        ):
            visible.append(review)

    page = visible[:limit]
    next_cursor: str | None = None
    if len(visible) > limit and page:
        next_cursor = _cursor_for(sort=sort, review=page[-1])

    # User sidecar — always exactly one row (the author). The frontend
    # keeps the same lookup shape as the album endpoint so it can share
    # the ReviewCard component.
    critic_seed_ids = await critic_seed_user_ids([target.id])
    users_payload: dict[str, dict[str, Any]] = {
        target.id: _serialize_user_card(target, critic_seed_ids=critic_seed_ids)
    }

    # Album sidecar — joined for every review on the page. Deduped by
    # album_id so the worst case is one Album lookup per distinct album
    # in the page.
    album_ids = {review.album_id for review in page}
    albums_payload: dict[str, dict[str, Any]] = {}
    if album_ids:
        album_rows = await Album.find({"_id": {"$in": list(album_ids)}}).to_list()
        albums_payload = {album.id: _serialize_album_card(album) for album in album_rows}

    return {
        "reviews": [_serialize_review(review) for review in page],
        "next_cursor": next_cursor,
        "users": users_payload,
        "albums": albums_payload,
    }


async def _fetch_user_reviews(
    *,
    user_id: str,
    sort: str,
    cursor: str | None,
    fetch_limit: int,
) -> list[Review]:
    """Query reviews authored by ``user_id`` under the given sort + cursor.

    Mirrors :func:`_fetch_album_reviews` but pivots on ``user_id``
    instead of ``album_id``. The ``highest_rated`` sort still joins
    against :class:`DiaryEntry.rating` in memory — same in-memory join
    the album endpoint uses, bounded by ``fetch_limit``.
    """
    decoded = _decode_cursor(cursor) if cursor else None
    base_filter: dict[str, Any] = {"user_id": user_id, "deleted_at": None}

    if sort == _SORT_NEWEST:
        if decoded is not None:
            cursor_created = decoded.get("c")
            cursor_id = decoded.get("i")
            if isinstance(cursor_created, str) and isinstance(cursor_id, str):
                try:
                    cursor_dt = datetime.fromisoformat(cursor_created)
                except ValueError:
                    cursor_dt = None
                if cursor_dt is not None:
                    base_filter["$or"] = [
                        {"created_at": {"$lt": cursor_dt}},
                        {"created_at": cursor_dt, "_id": {"$lt": cursor_id}},
                    ]
        return (
            await Review.find(base_filter).sort("-created_at", "-_id").limit(fetch_limit).to_list()
        )

    if sort == _SORT_MOST_LIKED:
        if decoded is not None:
            cursor_likes = decoded.get("lc")
            cursor_created = decoded.get("c")
            cursor_id = decoded.get("i")
            if isinstance(cursor_likes, int) and isinstance(cursor_id, str):
                try:
                    cursor_dt = (
                        datetime.fromisoformat(cursor_created)
                        if isinstance(cursor_created, str)
                        else None
                    )
                except ValueError:
                    cursor_dt = None
                if cursor_dt is not None:
                    base_filter["$or"] = [
                        {"reactions.likes_count": {"$lt": cursor_likes}},
                        {
                            "reactions.likes_count": cursor_likes,
                            "created_at": {"$lt": cursor_dt},
                        },
                        {
                            "reactions.likes_count": cursor_likes,
                            "created_at": cursor_dt,
                            "_id": {"$lt": cursor_id},
                        },
                    ]
        return (
            await Review.find(base_filter)
            .sort("-reactions.likes_count", "-created_at", "-_id")
            .limit(fetch_limit)
            .to_list()
        )

    # highest_rated — join with DiaryEntry.rating in memory.
    if decoded is not None:
        cursor_created = decoded.get("c")
        cursor_id = decoded.get("i")
        if isinstance(cursor_created, str) and isinstance(cursor_id, str):
            try:
                cursor_dt = datetime.fromisoformat(cursor_created)
            except ValueError:
                cursor_dt = None
            if cursor_dt is not None:
                base_filter["$or"] = [
                    {"created_at": {"$lt": cursor_dt}},
                    {"created_at": cursor_dt, "_id": {"$lt": cursor_id}},
                ]
    reviews = (
        await Review.find(base_filter).sort("-created_at", "-_id").limit(fetch_limit).to_list()
    )
    diary_ids = [r.diary_entry_id for r in reviews]
    entries = await DiaryEntry.find({"_id": {"$in": diary_ids}}).to_list()
    rating_by_entry = {entry.id: entry.rating for entry in entries}
    reviews.sort(
        key=lambda r: (
            -(rating_by_entry.get(r.diary_entry_id) or 0),
            -int(r.created_at.timestamp() * 1000),
        )
    )
    return reviews


# Static reference so OwnedContent stays imported.
_ = OwnedContent

__all__ = ["router"]
