"""Auth HTTP routes — signup, login, logout, logout-all-devices (T053, T059).

The auth surface owns three sub-paths under ``/api/v1/auth``:

* ``POST /api/v1/auth/signup`` — create a new account with email +
  password + handle, issue a session cookie, return the public-facing
  account payload.
* ``POST /api/v1/auth/login`` — verify credentials and issue a session
  cookie. Generic 401 on failure (no information leakage about which of
  email vs password was wrong).
* ``POST /api/v1/auth/logout`` — clear the session cookies on the
  *current* device. No-op for anonymous callers.
* ``POST /api/v1/auth/logout-all-devices`` — bump ``User.session_version``
  so every outstanding cookie becomes invalid the next time the session
  middleware re-validates (sliding refresh threshold + decoded version
  check). Documents the trade-off where the existing middleware doesn't
  hit the DB on every request, so logout-all is not strictly real-time.

CSRF discipline (see :class:`auxd_api.middleware.SessionMiddleware`):
signup + login are anonymous POSTs, so the middleware skips the CSRF
check entirely; logout + logout-all require an authenticated session
and therefore the standard double-submit cookie/header pair.

Rate limits (T020 dependency factory):
* signup: per-IP 5/min (defends against credential-stuffing-style
  account creation).
* login: per-IP 10/min (anonymous floor) + per-user 30/min (kicks in
  once a successful login attaches a session).

Observability (Constitution P5): every auth event emits a ``log_call``
line plus a PostHog event so the funnel analytics + ops dashboards see
the same signal. Passwords are NEVER logged.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, EmailStr, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.middleware import clear_session_cookies, issue_session
from auxd_api.modules.auth.service import (
    AuthError,
    DuplicateEmailError,
    DuplicateHandleError,
    InvalidCredentialsError,
    InvalidHandleError,
    ReservedHandleError,
    WeakPasswordError,
    authenticate_user,
    create_user_account,
)
from auxd_api.modules.users.models import (
    DISPLAY_NAME_MAX_LEN,
    HANDLE_MAX_LEN,
    HANDLE_MIN_LEN,
    User,
    UserStatus,
)

_LOGGER = logging.getLogger("auxd.auth.routes")

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class _SignupRequest(BaseModel):
    """Wire shape for ``POST /auth/signup``."""

    email: EmailStr
    password: str = Field(min_length=12)
    handle: str = Field(min_length=HANDLE_MIN_LEN, max_length=HANDLE_MAX_LEN)
    display_name: str | None = Field(default=None, max_length=DISPLAY_NAME_MAX_LEN)


class _LoginRequest(BaseModel):
    """Wire shape for ``POST /auth/login``."""

    email: EmailStr
    password: str = Field(min_length=1)  # length checked in policy; only require non-empty here.


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


# Map AuthError subclasses → (status_code, error_code_string).
# 409 for "conflict" (duplicate handle/email), 422 for "format invalid",
# 401 for "invalid credentials".
_ERROR_STATUS_MAP: dict[type[AuthError], int] = {
    DuplicateEmailError: status.HTTP_409_CONFLICT,
    DuplicateHandleError: status.HTTP_409_CONFLICT,
    ReservedHandleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidHandleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    WeakPasswordError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
}


def _auth_error_response(exc: AuthError) -> HTTPException:
    """Translate an :class:`AuthError` into an HTTPException with stable shape."""
    status_code = _ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(
        status_code=status_code,
        detail={"error": exc.code, "message": str(exc)},
    )


def _public_user_payload(user: User) -> dict[str, Any]:
    """Return the API-safe user payload — never includes ``password_hash``."""
    return {
        "id": user.id,
        "handle": user.handle,
        "email": user.email,
        "display_name": user.display_name,
    }


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


_SIGNUP_RATE_LIMIT = rate_limit(
    endpoint="auth.signup",
    per_ip=RateLimit(limit=5, window_seconds=60),
)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_SIGNUP_RATE_LIMIT)],
)
async def signup(payload: _SignupRequest, response: Response) -> dict[str, Any]:
    """Create a new account and issue a session cookie.

    Returns ``201`` with the public-user payload on success. Failure
    modes:

    * ``422`` — Pydantic validation (bad email shape, short password) or
      service-level format violations (handle char-class, reserved-squat
      list, weak password).
    * ``409`` — handle or email already in use.
    """
    try:
        result = await create_user_account(
            email=payload.email,
            password=payload.password,
            handle=payload.handle,
            display_name=payload.display_name,
        )
    except AuthError as exc:
        # Log internally with the error code so ops can debug bursts of
        # weak-password vs duplicate-handle; never log the password
        # itself or any caller-supplied detail beyond the code.
        log_call(
            provider="auxd",
            endpoint="auth.signup_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code},
        )
        emit_event(
            user_id=None,
            event="signup.rejected",
            properties={"reason": exc.code},
        )
        raise _auth_error_response(exc) from exc

    issue_session(response, user_id=result.user.id, session_version=result.user.session_version)
    log_call(
        provider="auxd",
        endpoint="auth.signup_completed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": result.user.id},
    )
    emit_event(
        user_id=result.user.id,
        event="signup.completed",
        properties={"handle": result.user.handle},
    )
    return _public_user_payload(result.user)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


_LOGIN_RATE_LIMIT = rate_limit(
    endpoint="auth.login",
    per_ip=RateLimit(limit=10, window_seconds=60),
    per_user=RateLimit(limit=30, window_seconds=60),
)


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_LOGIN_RATE_LIMIT)],
)
async def login(payload: _LoginRequest, response: Response) -> dict[str, Any]:
    """Verify credentials and issue a session cookie.

    Returns ``200`` with the public-user payload on success and ``401``
    with a generic ``invalid_credentials`` error code on any failure
    path. The route logs which sub-case fired internally so ops can
    distinguish "unknown email" from "wrong password" without leaking
    the distinction to the client.
    """
    try:
        user = await authenticate_user(email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        log_call(
            provider="auxd",
            endpoint="auth.login_failed",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "email_provided": bool(payload.email)},
        )
        emit_event(
            user_id=None,
            event="login.failed",
            properties={"reason": exc.code},
        )
        raise _auth_error_response(exc) from exc

    issue_session(response, user_id=user.id, session_version=user.session_version)
    log_call(
        provider="auxd",
        endpoint="auth.login_completed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id},
    )
    emit_event(
        user_id=user.id,
        event="login.completed",
        properties={"handle": user.handle},
    )
    return _public_user_payload(user)


# ---------------------------------------------------------------------------
# Logout
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


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request) -> JSONResponse:
    """Clear the session cookies on the current device.

    No-op for anonymous callers — returns ``200`` either way so a logout
    button on the client doesn't need conditional logic around current
    auth state.
    """
    session: Session | None = getattr(request.state, "session", None)
    response = JSONResponse({"signed_out": True})
    clear_session_cookies(response)
    if isinstance(session, Session):
        log_call(
            provider="auxd",
            endpoint="auth.logout",
            latency_ms=0.0,
            status="ok",
            extra={"user_id": session.user_id},
        )
        emit_event(
            user_id=session.user_id,
            event="auth.logout",
            properties={},
        )
    return response


@router.post("/logout-all-devices", status_code=status.HTTP_200_OK)
async def logout_all_devices(
    session: Annotated[Session, Depends(_require_session)],
) -> JSONResponse:
    """Invalidate every outstanding session for the current user.

    Bumps ``User.session_version`` so any cookie issued before this call
    fails the version check the next time the session middleware decodes
    it. Also clears the current device's cookies for parity with
    :func:`logout`.

    **Known trade-off (documented in the route docstring):** the
    :class:`auxd_api.middleware.SessionMiddleware` does *not* re-validate
    ``session_version`` against the User on every request — the version
    check happens at decode time only, so an already-decoded session
    won't be re-checked until the cookie's refresh threshold kicks in
    (<7 days remaining) or the cookie expires (30d). A future v1.x
    ticket will add per-request version checks via a Redis cache. At
    MVP scale this is acceptable: logout-all is a defence against a
    lost device, not a real-time kill switch.
    """
    user = await User.get(session.user_id)
    if user is None:
        # Defensive: session decoded ok but the user row is gone.
        # Treat as 401 to avoid leaking which path was followed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    user.session_version += 1
    await user.save()
    response = JSONResponse({"signed_out_all": True, "session_version": user.session_version})
    clear_session_cookies(response)
    log_call(
        provider="auxd",
        endpoint="auth.logout_all",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "session_version": user.session_version},
    )
    emit_event(
        user_id=user.id,
        event="auth.logout_all",
        properties={"session_version": user.session_version},
    )
    return response


# Keep the unused symbol referenced so linters see it (UserStatus is
# imported above for future suspended-account branching in login).
_ = UserStatus

__all__ = ["router"]
