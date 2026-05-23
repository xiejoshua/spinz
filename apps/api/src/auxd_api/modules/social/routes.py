"""Social-graph HTTP routes — follow / unfollow / block / un-block (T101 + T102).

Endpoints (all mounted under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``POST /users/{handle}/follow`` (T101) — follow a user. Returns the
  new follow state — ``accepted`` for public profiles, ``pending`` for
  private profiles where a FollowRequest is queued instead of an
  immediate Follow row.
* ``DELETE /users/{handle}/follow`` (T101) — un-follow. Idempotent;
  cancels any pending FollowRequest along the way.
* ``POST /users/{handle}/block`` (T102) — block a user with optional
  reason + notes. Cascades: dissolves Follow rows in either direction,
  cancels pending FollowRequests in either direction (TC-028).
* ``DELETE /users/{handle}/block`` (T102) — un-block. Idempotent. Does
  NOT auto-restore the previously-cascaded follows.
* ``GET /users/me/blocks`` (T102) — viewer's outgoing block list with
  blockee profile fields denormalised for the UI.

Rate limiting (T020):

* follow / block share an authoring budget — 60/min per user mirrors
  the diary edit ceiling. Both surfaces are deliberate user actions; a
  scripted abuser is the only realistic way to exceed.
* list-my-blocks: per-user 60/min — this is a settings-page surface so
  the budget is generous but still bounded.

Observability (Constitution P5):

* Every committed mutation emits a structured ``log_call`` line plus a
  PostHog event (``social.follow`` / ``social.unfollow`` /
  ``social.block`` / ``social.unblock``).
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.social.models import BLOCK_OTHER_REASON_MAX_LEN, BlockReason
from auxd_api.modules.social.service import (
    MAX_SUGGESTIONS_LIMIT,
    SUGGESTIONS_DEFAULT_LIMIT,
    BlockedError,
    InvalidBlockReasonError,
    SelfBlockError,
    SelfFollowError,
    SocialError,
    UserNotFoundError,
    block_user,
    dismiss_suggestion,
    follow_user,
    list_blocks,
    list_suggestions,
    unblock_user,
    unfollow_user,
)
from auxd_api.modules.users.redirect import resolve_handle

_LOGGER = logging.getLogger("auxd.social.routes")

router = APIRouter(tags=["social"])


# Per-user 60/min mirrors the diary edit rate limit — comfortable for
# normal use, defends against scripted spam.
_SOCIAL_WRITE_RATE_LIMIT = rate_limit(
    endpoint="social.write",
    per_user=RateLimit(limit=60, window_seconds=60),
)

# List-my-blocks is a settings surface; per-user 60/min is plenty.
_SOCIAL_READ_RATE_LIMIT = rate_limit(
    endpoint="social.read",
    per_user=RateLimit(limit=60, window_seconds=60),
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class _BlockRequest(BaseModel):
    """Wire shape for ``POST /users/{handle}/block``.

    ``reason`` is required so moderators can triage; ``notes`` is the
    free-text rationale used when ``reason == BlockReason.OTHER``. The
    400-char cap mirrors :data:`BLOCK_OTHER_REASON_MAX_LEN` so the
    service-layer length check is consistent with the wire bound.
    """

    reason: BlockReason
    notes: str | None = Field(default=None, max_length=BLOCK_OTHER_REASON_MAX_LEN)


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


_SOCIAL_ERROR_STATUS_MAP: dict[type[SocialError], int] = {
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    SelfFollowError: status.HTTP_400_BAD_REQUEST,
    SelfBlockError: status.HTTP_400_BAD_REQUEST,
    BlockedError: status.HTTP_403_FORBIDDEN,
    InvalidBlockReasonError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _social_error_response(exc: SocialError) -> HTTPException:
    status_code = _SOCIAL_ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.code)


# ---------------------------------------------------------------------------
# Session helpers (mirror diary routes pattern)
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# ---------------------------------------------------------------------------
# T101 — follow / unfollow
# ---------------------------------------------------------------------------


@router.post(
    "/users/{handle}/follow",
    dependencies=[Depends(_SOCIAL_WRITE_RATE_LIMIT)],
)
async def post_follow(
    handle: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Follow the user identified by ``handle``.

    Returns:

    * ``200`` on idempotent re-follow (already accepted or pending),
    * ``201`` on a fresh accepted Follow row,
    * ``202`` on a fresh pending FollowRequest (private profile).

    Errors:

    * ``400`` self-follow forbidden,
    * ``403`` blocked across either direction,
    * ``404`` unknown handle.
    """
    started = time.perf_counter()
    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )

    try:
        result = await follow_user(follower_id=session.user_id, followee=target)
    except SocialError as exc:
        log_call(
            provider="auxd",
            endpoint="social.follow_rejected",
            latency_ms=(time.perf_counter() - started) * 1000,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "followee_id": target.id,
            },
        )
        raise _social_error_response(exc) from exc

    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="social.follow_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "followee_id": target.id,
            "state": result.state,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="social.follow",
        properties={
            "follower_id": session.user_id,
            "followee_id": target.id,
            "state": result.state,
            "requested": result.state == "pending",
        },
    )
    # TODO: wire N-001 when notifications module lands at T123
    if result.state == "pending":
        # TODO: N-002 follow request notification
        pass
    return {
        "state": result.state,
        "follow_id": result.follow_id,
        "followee_id": result.followee_id,
    }


@router.delete(
    "/users/{handle}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_SOCIAL_WRITE_RATE_LIMIT)],
)
async def delete_follow(
    handle: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Un-follow the user identified by ``handle``.

    Idempotent: a 204 is returned whether or not a Follow row existed.
    Cancels any pending FollowRequest in the same direction so a
    private-profile request doesn't outlive the requester's intent.
    """
    started = time.perf_counter()
    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )

    removed = await unfollow_user(
        follower_id=session.user_id,
        followee_id=target.id,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="social.unfollow_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "followee_id": target.id,
            "removed": removed,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="social.unfollow",
        properties={
            "follower_id": session.user_id,
            "followee_id": target.id,
            "removed": removed,
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# T102 — block / unblock / list-my-blocks
# ---------------------------------------------------------------------------


@router.post(
    "/users/{handle}/block",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_SOCIAL_WRITE_RATE_LIMIT)],
)
async def post_block(
    handle: str,
    payload: _BlockRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Block the user identified by ``handle``.

    Cascade-on-block (TC-028): deletes any Follow row in either direction
    and cancels any pending FollowRequest in either direction.

    Returns ``204`` on success (whether the Block row was freshly created
    or already existed). Idempotent.

    Errors:

    * ``400`` self-block forbidden,
    * ``404`` unknown handle,
    * ``422`` notes exceeds cap (the Pydantic length bound catches this
      first; the service-layer check is defence-in-depth).
    """
    started = time.perf_counter()
    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )

    try:
        result = await block_user(
            blocker_id=session.user_id,
            blockee=target,
            reason=payload.reason,
            notes=payload.notes,
        )
    except SocialError as exc:
        log_call(
            provider="auxd",
            endpoint="social.block_rejected",
            latency_ms=(time.perf_counter() - started) * 1000,
            status="rejected",
            extra={
                "reason": exc.code,
                "user_id": session.user_id,
                "blockee_id": target.id,
            },
        )
        raise _social_error_response(exc) from exc

    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="social.block_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "blockee_id": target.id,
            "follows_removed": result.follows_removed,
            "requests_cancelled": result.requests_cancelled,
            "was_created": result.created,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="social.block",
        properties={
            "blocker_id": session.user_id,
            "blockee_id": target.id,
            "reason": payload.reason.value,
            "follows_removed": result.follows_removed,
            "requests_cancelled": result.requests_cancelled,
            "idempotent_hit": not result.created,
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{handle}/block",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_SOCIAL_WRITE_RATE_LIMIT)],
)
async def delete_block(
    handle: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Un-block the user identified by ``handle``.

    Idempotent: returns 204 whether or not a Block row existed. Does
    NOT auto-restore the cascaded follows — user has to re-follow
    manually.
    """
    started = time.perf_counter()
    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )

    result = await unblock_user(
        blocker_id=session.user_id,
        blockee_id=target.id,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="social.unblock_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "blockee_id": target.id,
            "removed": result.removed,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="social.unblock",
        properties={
            "blocker_id": session.user_id,
            "blockee_id": target.id,
            "removed": result.removed,
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# T105 — suggestions read + dismiss
# ---------------------------------------------------------------------------


@router.get(
    "/users/me/suggestions",
    dependencies=[Depends(_SOCIAL_READ_RATE_LIMIT)],
)
async def get_my_suggestions(
    session: Annotated[Session, Depends(_require_session)],
    limit: int = SUGGESTIONS_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return the viewer's top precomputed follow suggestions.

    Reads from the ``suggestions`` collection (precomputed by the T104
    worker). The handler re-applies the follow / block / dismissal
    filters even though the worker should have respected them at write
    time — these races are rare but the defence-in-depth filter is
    cheap.

    Query params:

    * ``limit`` — page size; default 5, capped at
      :data:`MAX_SUGGESTIONS_LIMIT` (20).

    Response shape::

        {
          "suggestions": [
            {
              "user": {"id", "handle", "display_name", "avatar_url"},
              "score": float,
              "reasons": [str],
              "computed_at": iso-string
            },
            ...
          ]
        }
    """
    started = time.perf_counter()
    capped_limit = min(max(limit, 1), MAX_SUGGESTIONS_LIMIT)
    entries = await list_suggestions(viewer_id=session.user_id, limit=capped_limit)
    log_call(
        provider="auxd",
        endpoint="social.suggestions_read",
        latency_ms=(time.perf_counter() - started) * 1000,
        status="ok",
        extra={"user_id": session.user_id, "count": len(entries)},
    )
    return {
        "suggestions": [
            {
                "user": {
                    "id": entry.user_id,
                    "handle": entry.handle,
                    "display_name": entry.display_name,
                    "avatar_url": entry.avatar_url,
                },
                "score": entry.score,
                "reasons": entry.reasons,
                "computed_at": entry.computed_at.isoformat(),
            }
            for entry in entries
        ]
    }


@router.post(
    "/users/me/suggestions/{suggested_user_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_SOCIAL_WRITE_RATE_LIMIT)],
)
async def post_dismiss_suggestion(
    suggested_user_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Dismiss a single suggestion for the viewer.

    Idempotent: double-dismiss returns 204 with no error.
    Side-effects: writes a :class:`SuggestionDismissal` row (TTL 30d so
    the candidate re-enters the pool after the cooling-off window) and
    clears the matching :class:`Suggestion` row so the API surface
    doesn't show the dismissed candidate before the next worker run.
    """
    started = time.perf_counter()
    result = await dismiss_suggestion(
        viewer_id=session.user_id,
        suggested_user_id=suggested_user_id,
    )
    log_call(
        provider="auxd",
        endpoint="social.suggestion_dismissed",
        latency_ms=(time.perf_counter() - started) * 1000,
        status="ok",
        extra={
            "user_id": session.user_id,
            "suggested_user_id": suggested_user_id,
            "was_created": result.created,
            "removed_precompute": result.removed,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="social.suggestion.dismiss",
        properties={
            "suggested_user_id": suggested_user_id,
            "idempotent_hit": not result.created,
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/users/me/blocks",
    dependencies=[Depends(_SOCIAL_READ_RATE_LIMIT)],
)
async def get_my_blocks(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """List the viewer's outgoing blocks.

    Response shape::

        {
          "blocks": [
            {
              "blockee_id": "...",
              "blockee_handle": "...",
              "blockee_display_name": "...",
              "blocked_at": "...",
              "reason": "...",
              "notes": "..." | null
            },
            ...
          ],
          "next_cursor": null
        }

    No pagination at MVP — block lists are small in practice. The
    ``next_cursor: null`` field is included for forward-compat with the
    rest of the list-endpoint API shape.
    """
    rows = await list_blocks(blocker_id=session.user_id)
    return {
        "blocks": [
            {
                "blockee_id": row.blockee_id,
                "blockee_handle": row.blockee_handle,
                "blockee_display_name": row.blockee_display_name,
                "blocked_at": row.blocked_at.isoformat(),
                "reason": row.reason,
                "notes": row.notes,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


__all__ = ["router"]
