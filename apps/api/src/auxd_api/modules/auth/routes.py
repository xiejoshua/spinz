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
from datetime import UTC, datetime
from typing import Annotated, Any

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, EmailStr, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.middleware import clear_session_cookies, issue_session
from auxd_api.modules.auth.email_verification import (
    VerificationTokenExpiredError,
    VerificationTokenInvalidError,
    VerificationTokenUsedError,
    consume_or_idempotent_verify,
    issue_verification_token,
    resend_verification_token,
    send_verification_email,
)
from auxd_api.modules.auth.password_reset import (
    ResetTokenExpiredError,
    ResetTokenInvalidError,
    ResetTokenUsedError,
    apply_password_reset,
    consume_reset_token,
    handle_forgot_password,
)
from auxd_api.modules.auth.service import (
    AccountDeletionPendingError,
    AccountSuspendedError,
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
from auxd_api.modules.notifications.dispatcher import dispatch as dispatch_notification
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.users.models import (
    DISPLAY_NAME_MAX_LEN,
    HANDLE_MAX_LEN,
    HANDLE_MIN_LEN,
    User,
    UserStatus,
)
from auxd_api.modules.users.service import cancel_account_deletion

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
    # Opt-in: when the user re-submits from the "account scheduled for
    # deletion" banner on /login, this flag tells the route to cancel
    # the pending deletion atomically before issuing a session. Default
    # ``False`` keeps the normal login path enumeration-resistant.
    cancel_deletion: bool = False


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
    AccountSuspendedError: status.HTTP_403_FORBIDDEN,
    AccountDeletionPendingError: status.HTTP_403_FORBIDDEN,
    # Feature 002-auth-email-flows — verification token states.
    # Per plan §2 error mapping: invalid + used → 410 Gone (link permanently
    # invalid), expired → 422 (a fresh resend will recover).
    VerificationTokenInvalidError: status.HTTP_410_GONE,
    VerificationTokenExpiredError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    VerificationTokenUsedError: status.HTTP_410_GONE,
    # Reset-password token states — all three map to 410 Gone (no
    # idempotent re-click path; the user already has a fresh session
    # after the first consume).
    ResetTokenInvalidError: status.HTTP_410_GONE,
    ResetTokenExpiredError: status.HTTP_410_GONE,
    ResetTokenUsedError: status.HTTP_410_GONE,
}


def _auth_error_response(exc: AuthError) -> HTTPException:
    """Translate an :class:`AuthError` into an HTTPException with stable shape.

    AccountDeletionPendingError carries an extra ``scheduled_for`` field
    in the detail payload so the frontend can surface the date on the
    login banner without a second round-trip.
    """
    status_code = _ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    detail: dict[str, Any] = {"error": exc.code, "message": str(exc)}
    if isinstance(exc, AccountDeletionPendingError) and exc.scheduled_for is not None:
        detail["scheduled_for"] = exc.scheduled_for.isoformat()
    return HTTPException(status_code=status_code, detail=detail)


def _public_user_payload(user: User) -> dict[str, Any]:
    """Return the API-safe user payload — never includes ``password_hash``."""
    return {
        "id": user.id,
        "handle": user.handle,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
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

    # Feature 002-auth-email-flows — bootstrap a verification token + dispatch
    # the welcome verification email. Best-effort: email failure must NOT
    # block signup (the user can resend from the banner), so we wrap in a
    # broad try/except and route any failure through Sentry + log_call.
    try:
        _token, raw_token = await issue_verification_token(result.user)
        await send_verification_email(result.user, raw_token)
    except Exception as exc:  # noqa: BLE001 — best-effort transactional email
        _LOGGER.exception(
            "auth.signup.verification_email_failed",
            extra={
                "event": "auth.signup.verification_email_failed",
                "user_id": result.user.id,
                "error": str(exc),
            },
        )
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("subsystem", "auth")
            scope.set_tag("status", "signup.verification_email_failed")
            scope.set_extra("user_id", result.user.id)
            scope.set_extra("error", str(exc))
            sentry_sdk.capture_message("signup.verification_email_failed", level="error")

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

    Returns ``200`` with the public-user payload on success. Failure
    modes:

    * ``401 invalid_credentials`` — unknown email OR wrong password.
      The two sub-cases are deliberately collapsed so the route cannot
      be used to enumerate registered emails.
    * ``403 account_suspended`` — password correct but the account is
      suspended. Only fires after password verification; never leaks
      for wrong-password attempts.
    * ``403 account_deletion_pending`` — password correct but the
      account is inside the 30-day deletion grace window. Detail body
      carries ``scheduled_for`` (ISO timestamp) so the frontend can
      surface it on the login banner alongside a "cancel deletion and
      sign in" CTA that re-submits with ``cancel_deletion: true``.

    When ``cancel_deletion=true`` is set and the matched user is in
    ``DELETION_PENDING`` state, the route cancels the pending deletion
    via :func:`cancel_account_deletion` BEFORE issuing the session so
    the cookie lands against an ``ACTIVE`` user.
    """
    try:
        user = await authenticate_user(
            email=payload.email,
            password=payload.password,
            allow_deletion_pending=payload.cancel_deletion,
        )
    except AuthError as exc:
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

    # If the caller opted in to cancelling deletion, do it atomically
    # before issuing the session so the cookie tracks the freshly-ACTIVE
    # session_version (cancel_account_deletion preserves it; the bump
    # happened at schedule_account_deletion time).
    deletion_cancelled = False
    if payload.cancel_deletion and user.status is UserStatus.DELETION_PENDING:
        await cancel_account_deletion(user)
        deletion_cancelled = True

    issue_session(response, user_id=user.id, session_version=user.session_version)
    log_call(
        provider="auxd",
        endpoint="auth.login_completed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "deletion_cancelled": deletion_cancelled},
    )
    emit_event(
        user_id=user.id,
        event="login.completed",
        properties={"handle": user.handle, "deletion_cancelled": deletion_cancelled},
    )
    if deletion_cancelled:
        emit_event(
            user_id=user.id,
            event="account.deletion_cancelled",
            properties={"via": "login_cancel"},
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


# ---------------------------------------------------------------------------
# Email verification (feature 002-auth-email-flows)
# ---------------------------------------------------------------------------


class _VerifyEmailRequest(BaseModel):
    """Wire shape for ``POST /auth/verify-email``."""

    token: str = Field(..., min_length=1)


class _ResendVerificationResponse(BaseModel):
    """Wire shape for the resend-verification response body."""

    ok: bool
    verified: bool


_VERIFY_EMAIL_RATE_LIMIT = rate_limit(
    endpoint="auth.verify_email",
    per_ip=RateLimit(limit=30, window_seconds=3600),
)


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_VERIFY_EMAIL_RATE_LIMIT)],
)
async def verify_email(payload: _VerifyEmailRequest) -> dict[str, Any]:
    """Consume a verification token and flip the linked user to verified.

    Anonymous-callable: the email link works even when logged out (the
    user might click from a different device). Idempotent re-click is
    explicitly supported — already-verified users receive a benign 200
    rather than an error.

    Returns ``{verified: true, idempotent: bool}`` on success. Failure
    modes:

    * ``410 verification_token_invalid`` — unknown or hash-mismatched
      token. The friendly UI shows "this link is no longer valid".
    * ``410 verification_token_used`` — token already consumed AND the
      linked user is NOT already verified. (The idempotent re-click
      case is handled in :func:`consume_or_idempotent_verify` before
      we get here.)
    * ``422 verification_token_expired`` — token row is past its 24h
      TTL. User can request a fresh one from the banner.

    Rate limit: per-IP 30/hour (FR-132).
    """
    try:
        user, idempotent = await consume_or_idempotent_verify(payload.token)
    except AuthError as exc:
        raise _auth_error_response(exc) from exc

    return {
        "verified": True,
        "idempotent": idempotent,
        "user": _public_user_payload(user),
    }


_RESEND_VERIFICATION_RATE_LIMIT = rate_limit(
    endpoint="auth.resend_verification",
    per_user=RateLimit(limit=3, window_seconds=3600),
)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_RESEND_VERIFICATION_RATE_LIMIT)],
)
async def resend_verification(
    session: Annotated[Session, Depends(_require_session)],
) -> _ResendVerificationResponse:
    """Issue a fresh verification token + send a new verification email.

    Authenticated route. The signup path issues a session even for
    unverified users, so this endpoint always has a session to key off.
    The middleware ``email_unverified`` gate explicitly allow-lists this
    path so unverified users CAN reach it.

    No-op when the user is already verified: returns ``{ok: true,
    verified: true}`` with no DB write. Otherwise invalidates any prior
    unused token + writes a fresh one + dispatches the email.

    Rate limit: per-user 3/hour (FR-133). Friendly toast on 429.
    """
    user = await User.find_one(User.id == session.user_id)
    if user is None:
        # Session decoded but the user row vanished — treat as 401.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )

    issued = await resend_verification_token(user)
    if issued is None:
        # User already verified — surface as a benign no-op.
        return _ResendVerificationResponse(ok=True, verified=True)

    _token, raw_token = issued
    try:
        await send_verification_email(user, raw_token)
    except Exception as exc:  # noqa: BLE001 — best-effort transactional email
        _LOGGER.exception(
            "auth.resend_verification.email_failed",
            extra={
                "event": "auth.resend_verification.email_failed",
                "user_id": user.id,
                "error": str(exc),
            },
        )
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("subsystem", "auth")
            scope.set_tag("status", "resend_verification.email_failed")
            scope.set_extra("user_id", user.id)
            scope.set_extra("error", str(exc))
            sentry_sdk.capture_message("resend_verification.email_failed", level="error")

    return _ResendVerificationResponse(ok=True, verified=False)


# ---------------------------------------------------------------------------
# Password reset (feature 002-auth-email-flows)
# ---------------------------------------------------------------------------


class _ForgotPasswordRequest(BaseModel):
    """Wire shape for ``POST /auth/forgot-password``.

    Only one field — the user's email. Validated as a syntactically
    correct address via Pydantic's ``EmailStr``; the no-enumeration
    posture means we DON'T tell the caller whether the address is
    actually registered.
    """

    email: EmailStr


class _ResetPasswordRequest(BaseModel):
    """Wire shape for ``POST /auth/reset-password``."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(min_length=12)


_FORGOT_PASSWORD_RATE_LIMIT = rate_limit(
    endpoint="auth.forgot_password",
    per_ip=RateLimit(limit=5, window_seconds=3600),
)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_FORGOT_PASSWORD_RATE_LIMIT)],
)
async def forgot_password(payload: _ForgotPasswordRequest) -> dict[str, Any]:
    """Issue a password-reset email (best-effort) for the supplied address.

    ALWAYS returns 200 with the same generic body regardless of outcome
    (FR-141 — no enumeration). The internal flow either dispatches a
    reset email or silently no-ops on a hit-miss / suspended / unverified
    branch; the caller never learns which.

    Rate limit: per-IP 5/hour (FR-130). The per-email 3/hour limit is
    not enforced here because doing so would itself be an enumeration
    oracle — instead, the per-user-id slot kicks in once we resolve a
    matching user inside :func:`handle_forgot_password` (handled via the
    rate-limiter's per-user branch attached on a follow-up). At MVP the
    per-IP cap is the primary guard against probing volume.
    """
    await handle_forgot_password(payload.email)
    return {
        "ok": True,
        "message": "If that email is registered, we've sent a reset link.",
    }


_RESET_PASSWORD_RATE_LIMIT = rate_limit(
    endpoint="auth.reset_password",
    per_ip=RateLimit(limit=10, window_seconds=3600),
)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_RESET_PASSWORD_RATE_LIMIT)],
)
async def reset_password(payload: _ResetPasswordRequest, response: Response) -> dict[str, Any]:
    """Consume a reset token, persist the new password, issue a fresh session.

    Anonymous-callable. The reset link is the credential; the caller is
    NOT logged in when this fires.

    On success: token is consumed, ``user.password_hash`` is updated,
    ``user.session_version`` is bumped (logging out every other device),
    a fresh session cookie is set on the response, and the existing
    ``N017 security.password_changed`` notification fires to confirm
    the change.

    Failure modes:

    * ``410 reset_token_invalid|expired|used`` — token state is bad;
      friendly UI sends user back to ``/forgot-password``.
    * ``422 weak_password`` — new password violates policy (length,
      letter, digit). Same policy as signup + change-password.

    Rate limit: per-IP 10/hour (FR-131). Token entropy (32 bytes) is
    the primary guard.
    """
    try:
        user, token = await consume_reset_token(payload.token)
    except AuthError as exc:
        raise _auth_error_response(exc) from exc

    try:
        user = await apply_password_reset(
            user=user,
            token=token,
            new_password=payload.new_password,
        )
    except WeakPasswordError as exc:
        raise _auth_error_response(exc) from exc

    issue_session(response, user_id=user.id, session_version=user.session_version)

    # Fire the existing N017 notification so the user gets the "your
    # password was changed" email automatically. The dispatcher
    # tolerates suppression branches gracefully; failure here MUST NOT
    # block the response.
    changed_at_iso = datetime.now(UTC).isoformat()
    try:
        await dispatch_notification(
            user_id=user.id,
            type=NotificationType.N017_SECURITY_PASSWORD_CHANGED,
            payload={"changed_at_iso": changed_at_iso},
            actor_id=None,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort; never block the reset
        _LOGGER.exception(
            "auth.reset_password.notification_failed",
            extra={
                "event": "auth.reset_password.notification_failed",
                "user_id": user.id,
                "error": str(exc),
            },
        )

    return _public_user_payload(user)


# Keep the unused symbol referenced so linters see it (UserStatus is
# imported above for future suspended-account branching in login).
_ = UserStatus

__all__ = ["router"]
