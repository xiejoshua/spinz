"""Password-reset service layer (feature 002-auth-email-flows).

Owns the forgot-password / reset-password side of the auth-email-flows
surface: token issue / consume helpers, the reset-email send helper,
and the AuthError subclasses the route layer maps to HTTP status codes.

The verify-email side lives in :mod:`auxd_api.modules.auth.email_verification`
with structurally parallel helpers — see that module's docstring for
the kind-split rationale.

Direct email send pattern
=========================
Identical to the verification email path: Resend SDK is sync, hopped
through :func:`asyncio.to_thread`, wrapped in
:func:`auxd_api.lib.resilience.retry` (3 attempts, exponential 0.5–5s),
with a :class:`FailedEmail` audit row on retry exhaustion.

Reset tokens are NOT routed through the notification dispatcher because
they fire outside an authenticated session (the user has forgotten
their password).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import resend
import sentry_sdk
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from auxd_api.lib.auth_tokens import generate_token, hash_token, verify_token
from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.resilience import retry
from auxd_api.modules.auth.password import hash_password
from auxd_api.modules.auth.service import AuthError, validate_password_policy
from auxd_api.modules.auth.tokens_models import PasswordResetToken
from auxd_api.modules.notifications.models import (
    FailedEmail,
    NotificationType,
)
from auxd_api.modules.users.models import User, UserStatus
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.auth.password_reset")

# Reset tokens live for 1 hour per FR-102 (OWASP recommendation — short
# window limits replay risk on link leak).
RESET_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)

# Email retry budget — mirrors the verification email path.
_EMAIL_RETRY_ATTEMPTS: Final[int] = 3

# Jinja env memoised lazily. Mirrors the verification module.
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Return the memoised Jinja environment for reset email rendering.

    StrictUndefined surfaces a missing payload key as a render error
    rather than blank-in-the-email — caught at adapter-call time.
    """
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=PackageLoader("auxd_api", "templates/email"),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
    return _jinja_env


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ResetTokenInvalidError(AuthError):
    """Raised when a reset-password request supplies a token we can't find.

    Mapped to ``410 Gone`` — the link is permanently invalid (it never
    existed, or referred to a cleaned-up row). Friendly UI: "this link
    is no longer valid".
    """

    code = "reset_token_invalid"


class ResetTokenExpiredError(AuthError):
    """Raised when the token row exists but ``expires_at`` is in the past.

    Mapped to ``410 Gone`` — the 1-hour TTL has elapsed. The friendly UI
    routes the user back to ``/forgot-password`` to request a fresh link.
    """

    code = "reset_token_expired"


class ResetTokenUsedError(AuthError):
    """Raised when the token row exists but ``used_at`` is set.

    Mapped to ``410 Gone``. Single-use tokens; a repeat click is always
    invalid (no idempotent re-click path for reset — the user already
    has a new session from the first consume).
    """

    code = "reset_token_used"


# ---------------------------------------------------------------------------
# Issue / consume
# ---------------------------------------------------------------------------


async def _invalidate_prior_unused_tokens(user_id: str) -> None:
    """Atomically stamp ``used_at`` on every unused reset token for ``user_id``.

    Race-safe per the same ``update_many`` pattern used by
    :func:`auxd_api.modules.auth.email_verification._invalidate_prior_unused_tokens`.
    """
    now = _utcnow()
    motor_collection = PasswordResetToken.get_motor_collection()
    await motor_collection.update_many(
        {"user_id": user_id, "used_at": None},
        {"$set": {"used_at": now}},
    )


async def issue_reset_token(user: User) -> tuple[PasswordResetToken, str]:
    """Create and persist a fresh :class:`PasswordResetToken` for ``user``.

    Invalidates any prior unused reset tokens for the same user first so
    only one valid token exists at a time (FR-104).

    Returns ``(persisted_token_doc, raw_token)`` — the raw token is what
    goes into the email; the document carries only the hash.
    """
    await _invalidate_prior_unused_tokens(user.id)

    raw, token_hash_value = generate_token()
    now = _utcnow()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash_value,
        expires_at=now + RESET_TOKEN_TTL,
        created_at=now,
    )
    await token.insert()
    log_call(
        provider="auxd",
        endpoint="auth.reset_requested",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "token_id": token.id},
    )
    emit_event(
        user_id=user.id,
        event="auth.reset_requested",
        properties={"token_id": token.id},
    )
    return token, raw


async def consume_reset_token(raw_token: str) -> tuple[User, PasswordResetToken]:
    """Validate ``raw_token`` and return the linked user + token row.

    Caller is responsible for applying the password change + bumping
    ``session_version`` + stamping ``token.used_at`` — separation lets
    the route layer keep the state-write transactional with the session
    re-issue.

    Raises:
        ResetTokenInvalidError: Token hash does not match any row.
        ResetTokenUsedError: Row exists but ``used_at`` is set.
        ResetTokenExpiredError: Row exists, unused, but past
            ``expires_at``.
    """
    expected_hash = hash_token(raw_token)
    token = await PasswordResetToken.find_one(PasswordResetToken.token_hash == expected_hash)
    if token is None:
        log_call(
            provider="auxd",
            endpoint="auth.reset_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "not_found"},
        )
        emit_event(
            user_id=None,
            event="auth.reset_invalid",
            properties={"reason": "not_found"},
        )
        raise ResetTokenInvalidError("reset token is invalid")

    if not verify_token(raw_token, token.token_hash):  # pragma: no cover - defensive
        log_call(
            provider="auxd",
            endpoint="auth.reset_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "hash_mismatch", "token_id": token.id},
        )
        raise ResetTokenInvalidError("reset token is invalid")

    user = await User.find_one(User.id == token.user_id)
    if user is None:
        log_call(
            provider="auxd",
            endpoint="auth.reset_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "user_missing", "token_id": token.id},
        )
        emit_event(
            user_id=None,
            event="auth.reset_invalid",
            properties={"reason": "user_missing"},
        )
        raise ResetTokenInvalidError("reset token is invalid")

    if token.used_at is not None:
        log_call(
            provider="auxd",
            endpoint="auth.reset_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "used", "user_id": user.id, "token_id": token.id},
        )
        emit_event(
            user_id=user.id,
            event="auth.reset_invalid",
            properties={"reason": "used"},
        )
        raise ResetTokenUsedError("reset token has already been used")

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= _utcnow():
        log_call(
            provider="auxd",
            endpoint="auth.reset_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "expired", "user_id": user.id, "token_id": token.id},
        )
        emit_event(
            user_id=user.id,
            event="auth.reset_invalid",
            properties={"reason": "expired"},
        )
        raise ResetTokenExpiredError("reset token has expired")

    return user, token


async def apply_password_reset(
    *,
    user: User,
    token: PasswordResetToken,
    new_password: str,
) -> User:
    """Apply the new password, bump ``session_version``, mark token used.

    Caller (the reset-password route) has already validated the token
    via :func:`consume_reset_token`. This helper is the canonical state-
    write surface.

    Raises:
        WeakPasswordError: Password violates policy (length, letter,
            digit). Propagates so the route layer can map to 422.
    """
    validate_password_policy(new_password)

    now = _utcnow()
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user.updated_at = now
    await user.save()

    token.used_at = now
    await token.save()

    log_call(
        provider="auxd",
        endpoint="auth.reset_consumed",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "token_id": token.id,
            "session_version": user.session_version,
        },
    )
    emit_event(
        user_id=user.id,
        event="auth.reset_consumed",
        properties={
            "token_id": token.id,
            "session_version": user.session_version,
        },
    )
    return user


# ---------------------------------------------------------------------------
# Forgot-password orchestration (always-200, no-enumeration)
# ---------------------------------------------------------------------------


# Static Argon2 hash used to keep response time constant when the
# forgot-password lookup misses. argon2-cffi's ``PasswordHasher.verify``
# raises on mismatch; we don't care about the verdict, just that the
# CPU cost is paid. The string is the result of hashing ``"never-match"``
# with the default parameters — generated once with
# ``PasswordHasher().hash("never-match")`` and pinned here so the cost
# is paid even when no User row exists.
_NO_MATCH_HASH: Final[str] = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "Y29uc3RhbnQtdGltZS0xMjM0NTY3OA$"
    "0nLY5d7ksb0bClmDXBxnTtihUgnzr+1G6F7y4VeAYpA"
)


async def handle_forgot_password(email: str) -> bool:
    """Look up ``email`` and (silently) dispatch a reset email if eligible.

    Returns ``True`` if a reset email was actually queued, ``False``
    otherwise — but callers MUST NOT surface the return value to the
    response body (FR-141). The endpoint always emits the same 200 body
    regardless of outcome.

    Internal flow per plan §3C:

    1. Lower-case email lookup.
    2. If ``user is None``: do a constant-time fake-Argon2 verify
       (defense against the no-match-fast timing oracle).
    3. If ``user.status is not ACTIVE``: silent skip.
    4. If ``user.email_verified is False``: silent skip — we don't push
       reset links to addresses the user hasn't claimed.
    5. Otherwise: invalidate prior unused reset tokens + create new +
       send email.
    """
    from auxd_api.modules.auth.password import verify_password

    normalised_email = email.strip().lower()
    user = await User.find_one(User.email == normalised_email)
    if user is None:
        # Constant-time fake verify so response time matches the
        # hit branch. We don't care about the result; the CPU cost is
        # the point.
        verify_password("never-match", _NO_MATCH_HASH)
        log_call(
            provider="auxd",
            endpoint="auth.reset_no_match",
            latency_ms=0.0,
            status="noop",
            extra={"reason": "user_not_found"},
        )
        emit_event(
            user_id=None,
            event="auth.reset_no_match",
            properties={"reason": "user_not_found"},
        )
        return False

    if user.status is not UserStatus.ACTIVE:
        log_call(
            provider="auxd",
            endpoint="auth.reset_no_match",
            latency_ms=0.0,
            status="noop",
            extra={"reason": "user_not_active", "user_id": user.id, "status": user.status.value},
        )
        emit_event(
            user_id=user.id,
            event="auth.reset_no_match",
            properties={"reason": "user_not_active", "status": user.status.value},
        )
        return False

    if user.email_verified is False:
        log_call(
            provider="auxd",
            endpoint="auth.reset_no_match",
            latency_ms=0.0,
            status="noop",
            extra={"reason": "email_unverified", "user_id": user.id},
        )
        emit_event(
            user_id=user.id,
            event="auth.reset_no_match",
            properties={"reason": "email_unverified"},
        )
        return False

    _token, raw = await issue_reset_token(user)
    try:
        await send_password_reset_email(user, raw)
    except Exception as exc:  # noqa: BLE001 — best-effort transactional email
        _LOGGER.exception(
            "auth.forgot_password.email_failed",
            extra={
                "event": "auth.forgot_password.email_failed",
                "user_id": user.id,
                "error": str(exc),
            },
        )
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("subsystem", "auth")
            scope.set_tag("status", "forgot_password.email_failed")
            scope.set_extra("user_id", user.id)
            scope.set_extra("error", str(exc))
            sentry_sdk.capture_message("forgot_password.email_failed", level="error")
    return True


# ---------------------------------------------------------------------------
# Email send helper
# ---------------------------------------------------------------------------


_RESET_SUBJECT: Final[str] = "Reset your auxd password"
_RESET_TEMPLATE: Final[str] = "n019_password_reset.html"


def _alert_email_send_failed(*, user_id: str, last_error: str) -> None:
    """Emit a Sentry error tagged ``email.send_failed`` for the reset email."""
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "auth.password_reset")
        scope.set_tag("status", "email.send_failed")
        scope.set_extra("user_id", user_id)
        scope.set_extra("last_error", last_error)
        sentry_sdk.capture_message("email.send_failed", level="error")


def _resend_send_sync(
    *,
    api_key: str,
    from_address: str,
    to_address: str,
    subject: str,
    html: str,
) -> dict[str, Any]:
    """Synchronous Resend send. Wrapped in :func:`asyncio.to_thread`."""
    resend.api_key = api_key
    response = resend.Emails.send(
        {
            "from": from_address,
            "to": [to_address],
            "subject": subject,
            "html": html,
        }
    )
    return dict(response) if response else {}


async def send_password_reset_email(user: User, raw_token: str) -> None:
    """Render + send the password-reset email via Resend.

    Direct-send pattern (NOT the dispatcher) — see module docstring.
    Failures are absorbed; the caller (forgot-password orchestrator)
    must treat this as best-effort.
    """
    settings = get_settings()
    reset_url = f"{settings.PUBLIC_APP_URL}/reset-password/{raw_token}"

    if settings.RESEND_API_KEY is None:
        log_call(
            provider="resend",
            endpoint="auth.send_password_reset_email_noop",
            latency_ms=0.0,
            status="ok",
            extra={"user_id": user.id, "reset_url": reset_url},
        )
        return

    context: dict[str, Any] = {
        "subject": _RESET_SUBJECT,
        "recipient_handle": user.handle,
        "public_app_url": settings.PUBLIC_APP_URL,
        "reset_url": reset_url,
        "unsubscribe_url": f"{settings.PUBLIC_APP_URL}/settings/notifications",
        "manage_url": f"{settings.PUBLIC_APP_URL}/settings/notifications",
    }

    try:
        template = _get_jinja_env().get_template(_RESET_TEMPLATE)
        html = template.render(**context)
    except Exception as exc:
        _LOGGER.exception(
            "auth.password_reset.render_failed",
            extra={
                "event": "auth.password_reset.render_failed",
                "user_id": user.id,
                "error": str(exc),
            },
        )
        _alert_email_send_failed(user_id=user.id, last_error=f"render: {exc}")
        return

    async def _attempt() -> dict[str, Any]:
        return await asyncio.to_thread(
            _resend_send_sync,
            api_key=settings.RESEND_API_KEY or "",
            from_address=settings.RESEND_FROM_ADDRESS,
            to_address=user.email,
            subject=_RESET_SUBJECT,
            html=html,
        )

    try:
        response = await retry(
            _attempt,
            attempts=_EMAIL_RETRY_ATTEMPTS,
            backoff="exponential",
            base_delay=0.5,
            max_delay=5.0,
        )
    except Exception as exc:
        failed = FailedEmail(
            user_id=user.id,
            notification_type=NotificationType.N017_SECURITY_PASSWORD_CHANGED,
            payload={"kind": "password_reset", "reset_url": reset_url},
            last_error=str(exc),
            retry_count=_EMAIL_RETRY_ATTEMPTS,
        )
        try:
            await failed.insert()
        except Exception as insert_exc:  # noqa: BLE001
            _LOGGER.exception(
                "auth.password_reset.failed_email_insert_failed",
                extra={
                    "event": "auth.password_reset.failed_email_insert_failed",
                    "user_id": user.id,
                    "error": str(insert_exc),
                },
            )
        _alert_email_send_failed(user_id=user.id, last_error=str(exc))
        log_call(
            provider="resend",
            endpoint="auth.send_password_reset_email",
            latency_ms=0.0,
            status="failed",
            extra={"user_id": user.id, "error": str(exc)},
        )
        return

    log_call(
        provider="resend",
        endpoint="auth.send_password_reset_email",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "resend_id": response.get("id") if isinstance(response, dict) else None,
        },
    )


__all__ = [
    "RESET_TOKEN_TTL",
    "ResetTokenExpiredError",
    "ResetTokenInvalidError",
    "ResetTokenUsedError",
    "apply_password_reset",
    "consume_reset_token",
    "handle_forgot_password",
    "issue_reset_token",
    "send_password_reset_email",
]
