"""User-account HTTP routes — handle change + account deletion (T057, T058)
+ profile edit + avatar + privacy + account-settings (T145/T146/T147/T150).

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

* ``PATCH /api/v1/users/me`` (T145) — update display name / bio. Single
  endpoint over both because the Edit Profile UI persists both on submit.

* ``POST /api/v1/users/me/avatar`` (T146) — multipart upload, max 5MB,
  resizes to 256/128/64 px, stores on R2, updates ``User.avatar_url``.

* ``PUT /api/v1/users/me/privacy`` (T147) — update the four
  visibility-policy fields atomically (``private_profile``,
  ``default_entry_visibility``, ``default_backlog_visibility``,
  ``keep_backlog_after_log``).

* ``GET /api/v1/users/me/follow-requests`` (T148) +
  ``POST .../approve`` + ``POST .../decline`` — pending follow-request
  inbox.

* ``POST /api/v1/users/me/email`` + ``POST /api/v1/users/me/password``
  (T150) — credential changes; both bump ``session_version`` so other
  devices log out next refresh.

Every successful mutation emits a structured ``log_call`` line + PostHog
event (Constitution P5). The session is enforced via the standard
``_require_session`` dependency; CSRF is handled by the session
middleware (these are authenticated POSTs, so the double-submit
cookie/header pair is mandatory).
"""

from __future__ import annotations

import io
import logging
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, EmailStr, Field

from auxd_api.lib.audit import record_gdpr_event
from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.lib.storage import (
    AVATAR_SIZES,
    MissingR2ConfigurationError,
    upload_avatar,
)
from auxd_api.lib.visibility import Visibility
from auxd_api.middleware import clear_session_cookies
from auxd_api.modules.auth.password import hash_password, verify_password
from auxd_api.modules.auth.service import (
    AuthError,
    DuplicateEmailError,
    DuplicateHandleError,
    InvalidHandleError,
    ReservedHandleError,
    WeakPasswordError,
)
from auxd_api.modules.gdpr.models import GdprAuditAction
from auxd_api.modules.notifications.dispatcher import dispatch as dispatch_notification
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.seeding.service import critic_seed_user_ids
from auxd_api.modules.social.models import (
    Block,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.users.models import (
    BIO_MAX_LEN,
    DISPLAY_NAME_MAX_LEN,
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
    response: Response,
) -> dict[str, Any]:
    """Schedule account deletion 30 days from now (idempotent).

    Side-effect: clears the caller's session cookies on the response so
    the browser is signed out the moment the deletion is scheduled.
    ``schedule_account_deletion`` also bumps ``session_version`` to
    invalidate cookies on other devices (best-effort — middleware
    re-validates at refresh time, not per request, per the documented
    trade-off in ``auth/routes.py:logout_all_devices``).
    """
    user = await _load_current_user(session)
    state = await schedule_account_deletion(user)
    clear_session_cookies(response)
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


# ---------------------------------------------------------------------------
# T153 — POST /users/me/data-export (GDPR self-service)
# ---------------------------------------------------------------------------


# Per-user 1/day. Export is expensive — there's no UX need for repeats
# inside a single day.
_DATA_EXPORT_RATE_LIMIT = rate_limit(
    endpoint="users.data_export",
    per_user=RateLimit(limit=1, window_seconds=24 * 60 * 60),
)


@router.post(
    "/me/data-export",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_DATA_EXPORT_RATE_LIMIT)],
)
async def post_request_data_export(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Queue a full data export and return 202 with the job + audit IDs.

    The work itself is done by :func:`auxd_api.workers.gdpr_export.
    generate_user_data_export` — the endpoint enqueues, writes the
    ``EXPORT_REQUESTED`` audit row, and returns immediately. The user
    receives an email with the signed download URLs when the worker
    completes (~60s for typical accounts).
    """
    user = await _load_current_user(session)
    audit_row = await record_gdpr_event(user.id, GdprAuditAction.EXPORT_REQUESTED, completed=False)

    # Local import keeps the redis dep lazy — same pattern as elsewhere
    # in the codebase. The enqueue helper raises a JobEnqueueUnavailable
    # if Redis is unreachable; the main app's exception handler converts
    # that into HTTP 503.
    from auxd_api.redis_client import enqueue_job

    job = await enqueue_job("generate_user_data_export", user.id)

    log_call(
        provider="auxd",
        endpoint="users.data_export_requested",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "job_id": job.job_id if job is not None else None,
            "audit_log_id": audit_row.id if audit_row is not None else None,
        },
    )
    emit_event(
        user_id=user.id,
        event="data.export_requested",
        properties={"audit_log_id": audit_row.id if audit_row is not None else None},
    )
    return {
        "job_id": job.job_id if job is not None else None,
        "audit_log_id": audit_row.id if audit_row is not None else None,
        "eta_seconds": 60,
    }


def _optional_session(request: Request) -> Session | None:
    session = getattr(request.state, "session", None)
    return session if isinstance(session, Session) else None


def _serialize_user_card(user: User, *, is_critic_seed: bool = False) -> dict[str, Any]:
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "private_profile": user.private_profile,
        "is_critic_seed": is_critic_seed,
    }


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me_current(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Return the SanitizedUser payload for the current session.

    MUST be declared before ``GET /{handle}`` — otherwise FastAPI's
    path-match-first-wins routing captures "me" as a handle parameter
    and dispatches to :func:`get_user_profile`, which then 404s with
    ``user_not_found`` because no user has the handle "me".

    Mirrors the response shape of ``POST /api/v1/auth/login`` so the
    frontend can rehydrate ``useAuthStore`` on cold boot via a single
    server-side fetch in ``app/(app)/layout.tsx``. Without this the
    auth store relied entirely on the in-memory state from the prior
    login flow, which meant a hard reload could leave the BottomTabs
    Profile link pointing at /login (and then bouncing to /feed via
    the (auth) shell's logged-in redirect).
    """
    user = await _load_current_user(session)
    return {
        "id": user.id,
        "handle": user.handle,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
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
                        "requester_id": viewer_id,
                        "requestee_id": target.id,
                        "status": FollowRequestStatus.PENDING.value,
                    }
                )
                relation = "pending" if pending is not None else "none"

    critic_seed_ids = await critic_seed_user_ids([target.id])
    return {
        "user": _serialize_user_card(target, is_critic_seed=target.id in critic_seed_ids),
        "counts": {
            "followers": follower_count,
            "following": following_count,
        },
        "relation": relation,
    }


# ---------------------------------------------------------------------------
# T145 — PATCH /users/me (display name + bio)
# ---------------------------------------------------------------------------


class _PatchProfileRequest(BaseModel):
    """Wire shape for ``PATCH /users/me``.

    Both fields are optional; the route applies whichever the caller
    supplied. This lets the Edit Profile form submit partial updates
    without first re-reading the current value.
    """

    display_name: str | None = Field(default=None, max_length=DISPLAY_NAME_MAX_LEN)
    bio: str | None = Field(default=None, max_length=BIO_MAX_LEN)


@router.patch("/me", status_code=status.HTTP_200_OK)
async def patch_me(
    payload: _PatchProfileRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Update display name / bio in place. Idempotent."""
    user = await _load_current_user(session)
    changed = False
    if payload.display_name is not None:
        stripped = payload.display_name.strip()
        if not stripped:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "invalid_display_name", "message": "display name is empty"},
            )
        if stripped != user.display_name:
            user.display_name = stripped
            changed = True
    if payload.bio is not None:
        normalised_bio = payload.bio.strip()
        if normalised_bio != user.bio:
            user.bio = normalised_bio
            changed = True
    if changed:
        await user.save()
        log_call(
            provider="auxd",
            endpoint="users.profile_updated",
            latency_ms=0.0,
            status="ok",
            extra={"user_id": user.id},
        )
        emit_event(
            user_id=user.id,
            event="profile.updated",
            properties={
                "fields": [
                    field
                    for field, supplied in (
                        ("display_name", payload.display_name is not None),
                        ("bio", payload.bio is not None),
                    )
                    if supplied
                ]
            },
        )
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
    }


# ---------------------------------------------------------------------------
# T146 — POST /users/me/avatar
# ---------------------------------------------------------------------------


# 5 MB hard cap. Larger uploads are 413'd before we hand the bytes to
# Pillow so a malicious 100 MB blob can't pin a worker thread.
_AVATAR_MAX_BYTES = 5 * 1024 * 1024

# Allowed input content-types; we always re-encode to JPEG on the way
# out so the bucket only ever holds a single format.
_AVATAR_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})

# Per-user 5/min — avatars don't get edited often; budget defends
# against burst spam.
_AVATAR_RATE_LIMIT = rate_limit(
    endpoint="users.avatar_upload",
    per_user=RateLimit(limit=5, window_seconds=60),
)


def _resize_avatar(raw_bytes: bytes) -> dict[int, bytes]:
    """Decode + EXIF-rotate + resize ``raw_bytes`` to the three avatar sizes.

    Returns a ``{size: jpeg_bytes}`` map keyed by the integer pixel
    dimension. JPEG quality 85 mirrors the Wagtail-default sweet spot
    for "looks fine on a profile card without bloating the bucket".

    Raises ``HTTPException(415)`` for anything Pillow can't decode (bad
    payload bytes, unsupported format the route filter missed, etc).
    """
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()  # force-decode so corrupt files fail here, not on resize
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": "invalid_image", "message": "image could not be decoded"},
        ) from exc

    # Apply EXIF orientation so the user's portrait isn't sideways.
    upright = ImageOps.exif_transpose(image)
    if upright is None:
        upright = image
    # Squash transparency onto white before encoding to JPEG (RGBA→RGB).
    if upright.mode in {"RGBA", "LA", "P"}:
        background = Image.new("RGB", upright.size, (255, 255, 255))
        rgba = upright.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1] if rgba.mode == "RGBA" else None)
        upright = background
    elif upright.mode != "RGB":
        upright = upright.convert("RGB")

    out: dict[int, bytes] = {}
    for size in AVATAR_SIZES:
        # Centre-crop to a square then resize to the target size so a
        # rectangular source doesn't get smushed in one dimension.
        width, height = upright.size
        edge = min(width, height)
        left = (width - edge) // 2
        top = (height - edge) // 2
        square = upright.crop((left, top, left + edge, top + edge))
        resized = square.resize((size, size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=85, optimize=True)
        out[size] = buf.getvalue()
    return out


@router.post(
    "/me/avatar",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_AVATAR_RATE_LIMIT)],
)
async def post_avatar(
    session: Annotated[Session, Depends(_require_session)],
    file: Annotated[UploadFile, File(description="JPEG/PNG/WebP, <=5MB")],
) -> dict[str, Any]:
    """Accept a multipart avatar, resize to 256/128/64 px, upload to R2.

    Validates size + content-type up-front so we never let an oversized
    blob into PIL. On success returns the canonical 256px URL and a
    ``sizes`` map. Updates ``User.avatar_url`` to the 256px URL.
    """
    started = time.perf_counter()
    user = await _load_current_user(session)

    content_type = (file.content_type or "").lower()
    if content_type not in _AVATAR_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "unsupported_content_type",
                "message": f"unsupported content-type: {file.content_type!r}",
            },
        )

    # Read with a hard byte cap. Reading one extra byte lets us 413 if
    # the body exceeds the limit without buffering the whole oversize
    # payload through PIL.
    raw = await file.read(_AVATAR_MAX_BYTES + 1)
    if len(raw) > _AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "file_too_large",
                "message": f"avatar must be <= {_AVATAR_MAX_BYTES} bytes",
            },
        )
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "empty_file", "message": "avatar payload is empty"},
        )

    sized_blobs = _resize_avatar(raw)
    try:
        url_map = upload_avatar(user_id=user.id, sized_blobs=sized_blobs)
    except MissingR2ConfigurationError as exc:
        log_call(
            provider="r2",
            endpoint="avatar_upload_misconfigured",
            latency_ms=(time.perf_counter() - started) * 1000,
            status="failed",
            extra={"user_id": user.id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "avatar_storage_unavailable", "message": str(exc)},
        ) from exc

    primary_url = url_map[str(AVATAR_SIZES[0])]
    user.avatar_url = primary_url
    await user.save()
    log_call(
        provider="r2",
        endpoint="avatar_upload",
        latency_ms=(time.perf_counter() - started) * 1000,
        status="ok",
        extra={"user_id": user.id, "bytes": len(raw)},
    )
    emit_event(
        user_id=user.id,
        event="profile.avatar_uploaded",
        properties={"bytes": len(raw)},
    )
    return {"avatar_url": primary_url, "sizes": url_map}


# ---------------------------------------------------------------------------
# T147 — PUT /users/me/privacy (default visibility + private profile)
# ---------------------------------------------------------------------------


class _PrivacySettingsRequest(BaseModel):
    """Wire shape for ``PUT /users/me/privacy``.

    All four fields are required so the client always sends the full
    desired state — avoids the "did the user mean to clear this?" ambiguity
    a PATCH would introduce. The Visibility enum is validated by Pydantic;
    the route is otherwise a thin setter.
    """

    private_profile: bool
    default_entry_visibility: Visibility
    default_backlog_visibility: Visibility
    keep_backlog_after_log: bool


@router.put("/me/privacy", status_code=status.HTTP_200_OK)
async def put_privacy(
    payload: _PrivacySettingsRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Replace the four privacy-policy fields atomically."""
    user = await _load_current_user(session)
    user.private_profile = payload.private_profile
    user.default_entry_visibility = payload.default_entry_visibility
    user.default_backlog_visibility = payload.default_backlog_visibility
    user.keep_backlog_after_log = payload.keep_backlog_after_log
    await user.save()
    log_call(
        provider="auxd",
        endpoint="users.privacy_updated",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "private_profile": payload.private_profile},
    )
    emit_event(
        user_id=user.id,
        event="privacy.updated",
        properties={
            "private_profile": payload.private_profile,
            "default_entry_visibility": payload.default_entry_visibility.value,
            "default_backlog_visibility": payload.default_backlog_visibility.value,
            "keep_backlog_after_log": payload.keep_backlog_after_log,
        },
    )
    return {
        "private_profile": user.private_profile,
        "default_entry_visibility": user.default_entry_visibility.value,
        "default_backlog_visibility": user.default_backlog_visibility.value,
        "keep_backlog_after_log": user.keep_backlog_after_log,
    }


# ---------------------------------------------------------------------------
# T148 — GET /users/me/follow-requests + approve / decline
# ---------------------------------------------------------------------------


_FOLLOW_REQUESTS_LIMIT_DEFAULT = 25
_FOLLOW_REQUESTS_LIMIT_MAX = 50

_FOLLOW_REQUESTS_READ_RATE_LIMIT = rate_limit(
    endpoint="users.follow_requests_read",
    per_user=RateLimit(limit=60, window_seconds=60),
)
_FOLLOW_REQUESTS_WRITE_RATE_LIMIT = rate_limit(
    endpoint="users.follow_requests_write",
    per_user=RateLimit(limit=60, window_seconds=60),
)


@router.get(
    "/me/follow-requests",
    dependencies=[Depends(_FOLLOW_REQUESTS_READ_RATE_LIMIT)],
)
async def get_my_follow_requests(
    session: Annotated[Session, Depends(_require_session)],
    cursor: str | None = None,
    limit: int = _FOLLOW_REQUESTS_LIMIT_DEFAULT,
) -> dict[str, Any]:
    """List my pending follow requests sorted by ``created_at desc``.

    Returns each row's requester profile (handle / display_name /
    avatar_url) so the UI can render the card without a second
    roundtrip. Cursor is the last row's id; the index on
    ``(requestee_id, status, created_at desc)`` keeps this O(log n).
    """
    capped_limit = min(max(limit, 1), _FOLLOW_REQUESTS_LIMIT_MAX)
    query: dict[str, Any] = {
        "requestee_id": session.user_id,
        "status": FollowRequestStatus.PENDING.value,
    }
    if cursor:
        query["_id"] = {"$lt": cursor}
    rows = (
        await FollowRequest.find(query)
        .sort("-created_at", "-_id")
        .limit(capped_limit + 1)
        .to_list()
    )
    has_more = len(rows) > capped_limit
    page = rows[:capped_limit]
    next_cursor = page[-1].id if has_more and page else None

    requester_ids = [row.requester_id for row in page]
    users: dict[str, User] = {}
    if requester_ids:
        for user in await User.find({"_id": {"$in": requester_ids}}).to_list():
            users[user.id] = user

    out_requests: list[dict[str, Any]] = []
    for row in page:
        out_requests.append(
            {
                "id": row.id,
                "requester_id": row.requester_id,
                "created_at": row.created_at.isoformat(),
            }
        )

    users_payload: dict[str, dict[str, Any]] = {
        uid: {
            "id": users[uid].id,
            "handle": users[uid].handle,
            "display_name": users[uid].display_name,
            "avatar_url": users[uid].avatar_url,
        }
        for uid in users
    }

    return {
        "requests": out_requests,
        "users": users_payload,
        "next_cursor": next_cursor,
    }


async def _load_owned_follow_request(request_id: str, user_id: str) -> FollowRequest:
    """Fetch a FollowRequest, enforcing owner-only access.

    Returns the row when it belongs to ``user_id`` (i.e. they are the
    requestee). Raises 404 otherwise — we don't leak existence of a
    request the caller doesn't own.
    """
    row = await FollowRequest.find_one({"_id": request_id})
    if row is None or row.requestee_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "request_not_found", "message": "follow request not found"},
        )
    return row


@router.post(
    "/me/follow-requests/{request_id}/approve",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_FOLLOW_REQUESTS_WRITE_RATE_LIMIT)],
)
async def post_approve_follow_request(
    request_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Approve a pending follow request.

    On a fresh approve:
        * Transition the FollowRequest row to ``status=ACCEPTED``.
        * Create the corresponding accepted ``Follow`` row.
        * Dispatch ``N-003 follow.request_approved`` to the requester.

    Idempotent: if the row is already ``ACCEPTED``, the route is a
    no-op and returns the existing state (no duplicate Follow created,
    no duplicate notification).
    """
    row = await _load_owned_follow_request(request_id, session.user_id)
    if row.status is FollowRequestStatus.ACCEPTED:
        return {
            "id": row.id,
            "status": row.status.value,
            "follow_id": None,
        }

    if row.status is not FollowRequestStatus.PENDING:
        # Already declined / expired — return current state with a 200 so
        # the inbox can refresh without surfacing an error to the user.
        return {"id": row.id, "status": row.status.value, "follow_id": None}

    now = datetime.now(UTC)
    row.status = FollowRequestStatus.ACCEPTED
    row.responded_at = now
    await row.save()

    # Idempotency at the Follow-row level: if the row already exists
    # (e.g. retried approval), reuse it.
    existing = await Follow.find_one(
        {"follower_id": row.requester_id, "followee_id": session.user_id}
    )
    if existing is None:
        follow = Follow(
            follower_id=row.requester_id,
            followee_id=session.user_id,
            state=FollowState.ACCEPTED,
            source="invite",
            created_at=now,
        )
        await follow.insert()
        follow_id = follow.id
    else:
        follow_id = existing.id

    # Look up the approver's handle so the requester can deep-link back.
    approver = await User.get(session.user_id)
    actor_handle = approver.handle if approver is not None else ""

    await dispatch_notification(
        user_id=row.requester_id,
        type=NotificationType.N003_FOLLOW_REQUEST_APPROVED,
        payload={"actor_handle": actor_handle},
        actor_id=session.user_id,
    )

    log_call(
        provider="auxd",
        endpoint="users.follow_request_approved",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": session.user_id,
            "request_id": row.id,
            "requester_id": row.requester_id,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="follow_request.approved",
        properties={"request_id": row.id, "requester_id": row.requester_id},
    )
    return {"id": row.id, "status": row.status.value, "follow_id": follow_id}


@router.post(
    "/me/follow-requests/{request_id}/decline",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_FOLLOW_REQUESTS_WRITE_RATE_LIMIT)],
)
async def post_decline_follow_request(
    request_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Decline a pending follow request.

    Idempotent — re-declining an already-declined row is a 200 no-op.
    Does NOT dispatch a notification (taxonomy: the requester will see
    the decline on their next app open via the absent inbox row).
    """
    row = await _load_owned_follow_request(request_id, session.user_id)
    if row.status is FollowRequestStatus.DECLINED:
        return {"id": row.id, "status": row.status.value}
    if row.status is not FollowRequestStatus.PENDING:
        return {"id": row.id, "status": row.status.value}

    row.status = FollowRequestStatus.DECLINED
    row.responded_at = datetime.now(UTC)
    await row.save()
    log_call(
        provider="auxd",
        endpoint="users.follow_request_declined",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": session.user_id,
            "request_id": row.id,
            "requester_id": row.requester_id,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="follow_request.declined",
        properties={"request_id": row.id, "requester_id": row.requester_id},
    )
    return {"id": row.id, "status": row.status.value}


# ---------------------------------------------------------------------------
# T150 — POST /users/me/email + POST /users/me/password
# ---------------------------------------------------------------------------


class _EmailChangeRequest(BaseModel):
    """Wire shape for ``POST /users/me/email``."""

    new_email: EmailStr
    current_password: str = Field(min_length=1)


class _PasswordChangeRequest(BaseModel):
    """Wire shape for ``POST /users/me/password``."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12)


# Per-user 5/hour — credential changes are deliberate user actions and
# should never burst. Sets a hard ceiling against credential-stuffing
# style abuse if the session somehow leaks.
_CREDENTIAL_CHANGE_RATE_LIMIT = rate_limit(
    endpoint="users.credential_change",
    per_user=RateLimit(limit=5, window_seconds=3600),
)


@router.post(
    "/me/email",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_CREDENTIAL_CHANGE_RATE_LIMIT)],
)
async def post_change_email(
    payload: _EmailChangeRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Change the user's email after re-verifying their current password.

    MVP scope: no separate verify-email click-link flow (would require a
    new collection + email template + click handler). We log an
    ``email.changed`` event so a follow-up T?? can wire the confirmation
    pipeline without re-touching this surface. ``session_version`` is
    bumped so any sessions issued before the change need to re-auth.
    """
    user = await _load_current_user(session)
    if user.password_hash is None or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_credentials",
                "message": "current password is incorrect",
            },
        )

    new_email = payload.new_email.strip().lower()
    if new_email == user.email:
        return {"email": user.email, "session_version": user.session_version}

    if await User.find_one({"email": new_email, "_id": {"$ne": user.id}}) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": DuplicateEmailError.code, "message": "email is already registered"},
        )

    user.email = new_email
    user.session_version += 1
    await user.save()

    # TODO(T?? — email confirmation): once the verify-email flow lands,
    # set ``user.email_confirmed_at = None`` here and fire the
    # confirmation email. For MVP we trust the password re-check.
    log_call(
        provider="auxd",
        endpoint="users.email_changed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "session_version": user.session_version},
    )
    emit_event(
        user_id=user.id,
        event="email.changed",
        properties={"session_version": user.session_version},
    )
    return {"email": user.email, "session_version": user.session_version}


@router.post(
    "/me/password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_CREDENTIAL_CHANGE_RATE_LIMIT)],
)
async def post_change_password(
    payload: _PasswordChangeRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Change the user's password and bump ``session_version``.

    Re-verifies the current password before applying the change. Fires
    ``N-017 security.password_changed`` so the user sees the audit trail
    in their inbox (email channel is LOCKED ON per taxonomy NT-2).
    """
    user = await _load_current_user(session)
    if user.password_hash is None or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_credentials",
                "message": "current password is incorrect",
            },
        )

    # Re-use the auth-module policy validator so weak-password rules stay
    # in lockstep with signup. The min_length=12 on the wire model is the
    # cheap pre-check; the service-layer call enforces the letter+digit
    # composition rule too.
    from auxd_api.modules.auth.service import (  # local import to avoid cycles at import time
        validate_password_policy,
    )

    try:
        validate_password_policy(payload.new_password)
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": exc.code, "message": str(exc)},
        ) from exc

    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    await user.save()
    changed_at = datetime.now(UTC).isoformat()

    await dispatch_notification(
        user_id=user.id,
        type=NotificationType.N017_SECURITY_PASSWORD_CHANGED,
        payload={"changed_at_iso": changed_at},
        actor_id=None,
    )

    log_call(
        provider="auxd",
        endpoint="users.password_changed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "session_version": user.session_version},
    )
    emit_event(
        user_id=user.id,
        event="password.changed",
        properties={"session_version": user.session_version},
    )
    return {"session_version": user.session_version, "changed_at": changed_at}


# Keep imports referenced even when the routes that use them are
# conditionally compiled by the linter — _ noop to silence ruff.
_ = (AuthError, DuplicateHandleError, InvalidHandleError, ReservedHandleError)

__all__ = ["router"]
