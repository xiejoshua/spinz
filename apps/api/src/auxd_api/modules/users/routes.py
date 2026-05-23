"""User-account HTTP routes — handle change + account deletion (T057, T058).

Endpoints mounted under ``/api/v1/users/me``:

* ``POST /api/v1/users/me/handle`` — change the current user's handle.
  Returns ``200`` on success with the new handle + ``handle_changed_at``
  ISO timestamp. Failure modes:

    * ``422`` — invalid format / reserved handle.
    * ``409`` — handle already in use by another user.
    * ``429`` — 30-day cooldown not yet elapsed (response body carries
      ``retry_after_days``).
    * ``401`` — no session.

* ``POST /api/v1/users/me/delete`` — schedule account deletion 30 days
  out (idempotent). Returns ``200`` with the scheduled ISO timestamp.

* ``DELETE /api/v1/users/me/delete`` — cancel a pending deletion.
  Returns ``200`` with the restored status.

Every successful mutation emits a structured ``log_call`` line + PostHog
event (Constitution P5). The session is enforced via the standard
``_require_session`` dependency; CSRF is handled by the session
middleware (these are authenticated POSTs, so the double-submit
cookie/header pair is mandatory).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.sessions import Session
from auxd_api.modules.auth.service import (
    AuthError,
    DuplicateHandleError,
    InvalidHandleError,
    ReservedHandleError,
)
from auxd_api.modules.social.models import (
    Block,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.users.models import (
    HANDLE_MAX_LEN,
    HANDLE_MIN_LEN,
    User,
)
from auxd_api.modules.users.redirect import resolve_handle
from auxd_api.modules.users.service import (
    HandleChangeTooSoonError,
    cancel_account_deletion,
    change_handle,
    schedule_account_deletion,
)

_LOGGER = logging.getLogger("auxd.users.routes")

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    """Pull a :class:`Session` from ``request.state`` or raise 401."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


async def _load_current_user(session: Session) -> User:
    """Look up the User row tied to ``session`` or raise 401."""
    user = await User.get(session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return user


# Status-code mapping for handle-change errors. Centralised so the
# tests can assert on the wire shape and the route stays short.
_HANDLE_ERROR_STATUS: dict[type[AuthError], int] = {
    InvalidHandleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ReservedHandleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DuplicateHandleError: status.HTTP_409_CONFLICT,
    HandleChangeTooSoonError: status.HTTP_429_TOO_MANY_REQUESTS,
}


# ---------------------------------------------------------------------------
# Handle change
# ---------------------------------------------------------------------------


class _HandleChangeRequest(BaseModel):
    """Wire shape for ``POST /users/me/handle``."""

    new_handle: str = Field(min_length=HANDLE_MIN_LEN, max_length=HANDLE_MAX_LEN)


@router.post("/me/handle", status_code=status.HTTP_200_OK)
async def post_change_handle(
    payload: _HandleChangeRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Apply the FR-029 handle-change policy and persist the rename."""
    user = await _load_current_user(session)
    try:
        result = await change_handle(user=user, new_handle=payload.new_handle)
    except HandleChangeTooSoonError as exc:
        log_call(
            provider="auxd",
            endpoint="users.handle_change_too_soon",
            latency_ms=0.0,
            status="rejected",
            extra={"user_id": user.id, "retry_after_days": exc.retry_after_days},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": exc.code,
                "message": str(exc),
                "retry_after_days": exc.retry_after_days,
            },
        ) from exc
    except AuthError as exc:
        status_code = _HANDLE_ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
        log_call(
            provider="auxd",
            endpoint="users.handle_change_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"user_id": user.id, "reason": exc.code},
        )
        raise HTTPException(
            status_code=status_code,
            detail={"error": exc.code, "message": str(exc)},
        ) from exc

    log_call(
        provider="auxd",
        endpoint="users.handle_changed",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "old_handle": result.redirect.old_handle,
            "new_handle": result.user.handle,
        },
    )
    emit_event(
        user_id=user.id,
        event="handle.changed",
        properties={
            "old": result.redirect.old_handle,
            "new": result.user.handle,
        },
    )
    handle_changed_at = result.user.handle_changed_at
    return {
        "handle": result.user.handle,
        "handle_changed_at": handle_changed_at.isoformat() if handle_changed_at else None,
    }


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------


def _serialize_deletion_state(state_status: str, scheduled_for: Any) -> dict[str, Any]:
    """Format the deletion-state payload uniformly across schedule + cancel."""
    return {
        "status": state_status,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
    }


@router.post("/me/delete", status_code=status.HTTP_200_OK)
async def post_schedule_deletion(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Schedule account deletion 30 days from now (idempotent)."""
    user = await _load_current_user(session)
    state = await schedule_account_deletion(user)
    log_call(
        provider="auxd",
        endpoint="users.account_deletion_scheduled",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "scheduled_for": state.scheduled_for.isoformat() if state.scheduled_for else None,
        },
    )
    emit_event(
        user_id=user.id,
        event="account.deletion_scheduled",
        properties={
            "scheduled_for": state.scheduled_for.isoformat() if state.scheduled_for else None,
        },
    )
    return _serialize_deletion_state(state.status.value, state.scheduled_for)


@router.delete("/me/delete", status_code=status.HTTP_200_OK)
async def delete_cancel_deletion(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Cancel a pending account deletion."""
    user = await _load_current_user(session)
    state = await cancel_account_deletion(user)
    log_call(
        provider="auxd",
        endpoint="users.account_deletion_cancelled",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id},
    )
    emit_event(
        user_id=user.id,
        event="account.deletion_cancelled",
        properties={},
    )
    return _serialize_deletion_state(state.status.value, state.scheduled_for)


def _optional_session(request: Request) -> Session | None:
    session = getattr(request.state, "session", None)
    return session if isinstance(session, Session) else None


def _serialize_user_card(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "private_profile": user.private_profile,
    }


@router.get("/{handle}")
async def get_user_profile(handle: str, request: Request) -> dict[str, Any]:
    """Public profile lookup — powers `/profile/[handle]` SSR header (T109).

    Returns the user card + follower/following counts + the viewer's
    relation to the target (so the frontend can render the Follow / Block
    affordances without a second roundtrip). Privacy-aware: a blocked
    viewer sees 404 (not 403) to avoid existence-leak.
    """
    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    session = _optional_session(request)
    viewer_id = session.user_id if session is not None else None

    # Block check first — blocked viewers can't even confirm the user exists.
    if viewer_id is not None and viewer_id != target.id:
        block = await Block.find_one(
            {
                "$or": [
                    {"blocker_id": target.id, "blockee_id": viewer_id},
                    {"blocker_id": viewer_id, "blockee_id": target.id},
                ]
            }
        )
        if block is not None and block.blocker_id == target.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    follower_count = await Follow.find(
        {"followee_id": target.id, "state": FollowState.ACCEPTED.value}
    ).count()
    following_count = await Follow.find(
        {"follower_id": target.id, "state": FollowState.ACCEPTED.value}
    ).count()

    relation: str
    if viewer_id is None:
        relation = "anonymous"
    elif viewer_id == target.id:
        relation = "self"
    else:
        # Check the viewer's outbound block first.
        outbound_block = await Block.find_one({"blocker_id": viewer_id, "blockee_id": target.id})
        if outbound_block is not None:
            relation = "blocked"
        else:
            follow = await Follow.find_one(
                {
                    "follower_id": viewer_id,
                    "followee_id": target.id,
                    "state": FollowState.ACCEPTED.value,
                }
            )
            if follow is not None:
                relation = "following"
            else:
                pending = await FollowRequest.find_one(
                    {
                        "follower_id": viewer_id,
                        "followee_id": target.id,
                        "status": FollowRequestStatus.PENDING.value,
                    }
                )
                relation = "pending" if pending is not None else "none"

    return {
        "user": _serialize_user_card(target),
        "counts": {
            "followers": follower_count,
            "following": following_count,
        },
        "relation": relation,
    }


__all__ = ["router"]
