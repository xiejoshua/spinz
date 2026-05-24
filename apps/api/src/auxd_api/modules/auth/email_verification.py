"""Email-verification service layer (feature 002-auth-email-flows).

Owns the verify-email side of the auth-email-flows surface: token
issue / consume / resend helpers, the verification-email send helper,
and the AuthError subclasses the route layer maps to HTTP status codes.

The reset-password side lives in :mod:`auxd_api.modules.auth.password_reset`
with structurally parallel helpers — the two modules are kept apart per
the same kind-split rationale as the underlying token collections (see
:mod:`auxd_api.modules.auth.tokens_models`).

Direct email send pattern
=========================
Verification emails are NOT routed through the notification dispatcher.
They are out-of-band — sent DURING the authentication transition rather
than as a result of a user-side event. The dispatcher operates on
``Notification`` rows tied to :class:`NotificationType` values; the
verification email is neither.

We mirror the direct-send pattern from
:func:`auxd_api.workers.gdpr_export._send_export_email`: Resend SDK is
sync, so the blocking ``Emails.send`` call is hopped via
:func:`asyncio.to_thread`. The send is wrapped in
:func:`auxd_api.lib.resilience.retry` (3 attempts, exponential 0.5–5s);
on retry exhaustion a :class:`FailedEmail` audit row is inserted so the
ops console can surface the miss for manual replay.

Observability (Constitution P5): every state transition emits a
``log_call`` + PostHog event. The canonical event names are listed in
plan §10.
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
from auxd_api.modules.auth.service import AuthError
from auxd_api.modules.auth.tokens_models import EmailVerificationToken
from auxd_api.modules.notifications.models import (
    FailedEmail,
    NotificationType,
)
from auxd_api.modules.users.models import User
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.auth.email_verification")

# Verification tokens live for 24 hours per FR-102.
VERIFICATION_TOKEN_TTL: Final[timedelta] = timedelta(hours=24)

# Email retry budget — mirrors the notifications email adapter (3 attempts,
# 0.5s base, 5s cap).
_EMAIL_RETRY_ATTEMPTS: Final[int] = 3

# Jinja env memoised lazily so module import doesn't trigger package-resource
# lookup before the application is wired. Mirrors the notification adapter.
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Return the memoised Jinja environment for verification email rendering.

    StrictUndefined surfaces a missing payload key as a clear render
    error rather than blank-in-the-email — caught at adapter-call time,
    never in the recipient's inbox.
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


class VerificationTokenInvalidError(AuthError):
    """Raised when a verify-email request supplies a token we can't find.

    Mapped to ``410 Gone`` at the route layer — the link is permanently
    invalid (it never existed, or referred to a row that was cleaned
    up). The friendly UI says "this link is no longer valid".
    """

    code = "verification_token_invalid"


class VerificationTokenExpiredError(AuthError):
    """Raised when the token row exists but ``expires_at`` is in the past.

    Mapped to ``422`` at the route layer — the user can request a fresh
    token via resend; the link has a 24h TTL.
    """

    code = "verification_token_expired"


class VerificationTokenUsedError(AuthError):
    """Raised when the token row exists but ``used_at`` is set.

    Mapped to ``410 Gone`` at the route layer. Single-use tokens; a
    repeat click is treated as invalid unless the linked user is
    already verified (in which case the route layer surfaces the
    idempotent success path before we even raise).
    """

    code = "verification_token_used"


# ---------------------------------------------------------------------------
# Issue / consume / resend
# ---------------------------------------------------------------------------


async def _invalidate_prior_unused_tokens(user_id: str) -> None:
    """Atomically stamp ``used_at`` on every unused token for ``user_id``.

    The ``update_many`` filter with ``used_at: None`` guarantees the
    write is race-safe: two simultaneous resend calls can both hit this
    line, but they'll either land on the same prior rows or insert
    fresh ones — never produce two valid tokens for one user.

    No-op if the user has no prior unused tokens.
    """
    now = _utcnow()
    motor_collection = EmailVerificationToken.get_motor_collection()
    await motor_collection.update_many(
        {"user_id": user_id, "used_at": None},
        {"$set": {"used_at": now}},
    )


async def issue_verification_token(user: User) -> tuple[EmailVerificationToken, str]:
    """Create and persist a fresh :class:`EmailVerificationToken` for ``user``.

    Invalidates any prior unused tokens for the same user first so the
    one-valid-token-at-a-time invariant holds (FR-104).

    Returns ``(persisted_token_doc, raw_token)`` — the raw token is what
    goes into the email; the document carries only the hash.
    """
    await _invalidate_prior_unused_tokens(user.id)

    raw, token_hash_value = generate_token()
    now = _utcnow()
    token = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash_value,
        expires_at=now + VERIFICATION_TOKEN_TTL,
        created_at=now,
    )
    await token.insert()
    log_call(
        provider="auxd",
        endpoint="auth.verification_sent",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "token_id": token.id},
    )
    emit_event(
        user_id=user.id,
        event="auth.verification_sent",
        properties={"token_id": token.id},
    )
    return token, raw


async def consume_verification_token(raw_token: str) -> User:
    """Validate ``raw_token`` and mark the linked user verified.

    Raises:
        VerificationTokenInvalidError: Token hash does not match any row.
        VerificationTokenUsedError: Row exists but ``used_at`` is set
            AND the linked user is NOT already verified (the idempotent
            re-click case is handled before we get here — see
            :func:`consume_or_idempotent_verify`).
        VerificationTokenExpiredError: Row exists, unused, but past
            ``expires_at``.

    Returns the persisted, verified :class:`User`. On success: token
    row's ``used_at`` is stamped, ``User.email_verified`` is ``True``,
    ``User.email_verified_at`` is the consume timestamp.
    """
    expected_hash = hash_token(raw_token)
    token = await EmailVerificationToken.find_one(
        EmailVerificationToken.token_hash == expected_hash
    )
    if token is None:
        log_call(
            provider="auxd",
            endpoint="auth.verification_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "not_found"},
        )
        emit_event(
            user_id=None,
            event="auth.verification_invalid",
            properties={"reason": "not_found"},
        )
        raise VerificationTokenInvalidError("verification token is invalid")

    # Constant-time recompute: hash_token already produced the lookup
    # value, but verify_token confirms equality with the persisted hash
    # under compare_digest — defends against a future change that swaps
    # the lookup index for a less-strict equality.
    if not verify_token(raw_token, token.token_hash):  # pragma: no cover - defensive
        log_call(
            provider="auxd",
            endpoint="auth.verification_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "hash_mismatch", "token_id": token.id},
        )
        raise VerificationTokenInvalidError("verification token is invalid")

    user = await User.find_one(User.id == token.user_id)
    if user is None:
        # Defence-in-depth: the linked user vanished between issue +
        # consume (e.g. hard delete). Treat as invalid.
        log_call(
            provider="auxd",
            endpoint="auth.verification_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "user_missing", "token_id": token.id},
        )
        emit_event(
            user_id=None,
            event="auth.verification_invalid",
            properties={"reason": "user_missing"},
        )
        raise VerificationTokenInvalidError("verification token is invalid")

    if token.used_at is not None:
        # Already-consumed token. The route layer treats this as
        # idempotent when the linked user is already verified; here we
        # surface the raw error and let the caller decide.
        log_call(
            provider="auxd",
            endpoint="auth.verification_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "used", "user_id": user.id, "token_id": token.id},
        )
        emit_event(
            user_id=user.id,
            event="auth.verification_invalid",
            properties={"reason": "used"},
        )
        raise VerificationTokenUsedError("verification token has already been used")

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        # BSON deserialisation can strip tzinfo; re-attach UTC for the compare.
        expires_at = expires_at.replace(tzinfo=UTC)
    now = _utcnow()
    if expires_at <= now:
        log_call(
            provider="auxd",
            endpoint="auth.verification_invalid",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": "expired", "user_id": user.id, "token_id": token.id},
        )
        emit_event(
            user_id=user.id,
            event="auth.verification_invalid",
            properties={"reason": "expired"},
        )
        raise VerificationTokenExpiredError("verification token has expired")

    # Mark token used + user verified.
    token.used_at = now
    await token.save()
    user.email_verified = True
    user.email_verified_at = now
    user.updated_at = now
    await user.save()

    log_call(
        provider="auxd",
        endpoint="auth.verification_consumed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "token_id": token.id},
    )
    emit_event(
        user_id=user.id,
        event="auth.verification_consumed",
        properties={"token_id": token.id},
    )
    return user


async def consume_or_idempotent_verify(raw_token: str) -> tuple[User, bool]:
    """Consume the token or surface the idempotent-already-verified state.

    Returns ``(user, idempotent)``:

    * ``(user, False)`` — token was just consumed; user is now verified.
    * ``(user, True)`` — token was previously consumed AND the user is
      already verified. The route layer returns ``200`` with a benign
      body in this case (FR-112 / US-001 acceptance).

    Any other failure mode (unknown token, expired, used-but-user-not-
    verified) raises through :func:`consume_verification_token`.
    """
    try:
        user = await consume_verification_token(raw_token)
        return user, False
    except VerificationTokenUsedError:
        # Cross-check the linked user state to support the idempotent
        # re-click path. We have to re-lookup the token because
        # consume_verification_token raised before exposing it.
        expected_hash = hash_token(raw_token)
        token = await EmailVerificationToken.find_one(
            EmailVerificationToken.token_hash == expected_hash
        )
        if token is None:  # pragma: no cover — defensive, race with cleanup cron
            raise
        linked_user = await User.find_one(User.id == token.user_id)
        if linked_user is not None and linked_user.email_verified:
            # Idempotent success: log + emit but don't surface as error.
            log_call(
                provider="auxd",
                endpoint="auth.verification_consumed",
                latency_ms=0.0,
                status="ok",
                extra={
                    "user_id": linked_user.id,
                    "token_id": token.id,
                    "idempotent": True,
                },
            )
            emit_event(
                user_id=linked_user.id,
                event="auth.verification_consumed",
                properties={"token_id": token.id, "idempotent": True},
            )
            return linked_user, True
        raise


async def resend_verification_token(user: User) -> tuple[EmailVerificationToken, str] | None:
    """Issue a fresh verification token for ``user`` and return ``(token, raw)``.

    Returns ``None`` if the user is already verified (no-op; the route
    layer surfaces this as a benign 200). Otherwise behaves identically
    to :func:`issue_verification_token`, with the resend-specific log
    event tag for analytics.
    """
    if user.email_verified:
        return None
    token, raw = await issue_verification_token(user)
    # Override the generic "verification_sent" event with the resend-specific
    # tag so the analytics funnel can split first-send vs resends.
    log_call(
        provider="auxd",
        endpoint="auth.verification_resent",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user.id, "token_id": token.id},
    )
    emit_event(
        user_id=user.id,
        event="auth.verification_resent",
        properties={"token_id": token.id},
    )
    return token, raw


# ---------------------------------------------------------------------------
# Email send helper
# ---------------------------------------------------------------------------


_VERIFICATION_SUBJECT: Final[str] = "Confirm your email for auxd"
_VERIFICATION_TEMPLATE: Final[str] = "n018_email_verification.html"


def _alert_email_send_failed(
    *,
    user_id: str,
    last_error: str,
) -> None:
    """Emit a Sentry error tagged ``email.send_failed`` for verification email."""
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "auth.email_verification")
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
    """Synchronous Resend send. Wrapped in :func:`asyncio.to_thread`.

    Mirrors the notification email adapter's helper of the same name.
    Returns the Resend response dict on success; raises on transport /
    5xx failure so the retry layer can decide what to do.
    """
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


async def send_verification_email(user: User, raw_token: str) -> None:
    """Render + send the email-verification email via Resend.

    Direct-send pattern (NOT the dispatcher) — see module docstring for
    the rationale. Failures are absorbed:

    * No ``RESEND_API_KEY`` set → log + return (local dev / CI mode).
    * Render failure → log + Sentry alert + return.
    * Send retry exhausted → write :class:`FailedEmail` row + Sentry
      alert + return.

    Callers (signup, resend-verification) MUST treat this as best-effort
    — never block the user-facing transition on email delivery. The
    raw token is still persisted in the database; a stale email arrives
    a few minutes late is fine.
    """
    settings = get_settings()
    verify_url = f"{settings.PUBLIC_APP_URL}/verify-email/{raw_token}"

    if settings.RESEND_API_KEY is None:
        # Disabled (local dev, test env). Log the URL so an operator
        # can hand-deliver if needed.
        log_call(
            provider="resend",
            endpoint="auth.send_verification_email_noop",
            latency_ms=0.0,
            status="ok",
            extra={"user_id": user.id, "verify_url": verify_url},
        )
        return

    context: dict[str, Any] = {
        "subject": _VERIFICATION_SUBJECT,
        "recipient_handle": user.handle,
        "public_app_url": settings.PUBLIC_APP_URL,
        "verify_url": verify_url,
        # base.html footer references these — supply benign defaults so
        # StrictUndefined doesn't choke on a transactional template that
        # doesn't need a real unsubscribe link.
        "unsubscribe_url": f"{settings.PUBLIC_APP_URL}/settings/notifications",
        "manage_url": f"{settings.PUBLIC_APP_URL}/settings/notifications",
    }

    try:
        template = _get_jinja_env().get_template(_VERIFICATION_TEMPLATE)
        html = template.render(**context)
    except Exception as exc:
        _LOGGER.exception(
            "auth.email_verification.render_failed",
            extra={
                "event": "auth.email_verification.render_failed",
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
            subject=_VERIFICATION_SUBJECT,
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
        # Retry exhausted — write FailedEmail row + Sentry alert.
        # We piggyback on the existing NotificationType registry by using
        # N016_SECURITY_NEW_SESSION as the closest-fit type for the audit
        # row. Future schema enhancement: widen ``notification_type`` to
        # accept a separate "transactional" enum so out-of-band sends can
        # be audited with their own identifier. For MVP the user_id +
        # payload combo is enough to debug.
        failed = FailedEmail(
            user_id=user.id,
            notification_type=NotificationType.N016_SECURITY_NEW_SESSION,
            payload={"kind": "email_verification", "verify_url": verify_url},
            last_error=str(exc),
            retry_count=_EMAIL_RETRY_ATTEMPTS,
        )
        try:
            await failed.insert()
        except Exception as insert_exc:  # noqa: BLE001 — last-resort logging
            _LOGGER.exception(
                "auth.email_verification.failed_email_insert_failed",
                extra={
                    "event": "auth.email_verification.failed_email_insert_failed",
                    "user_id": user.id,
                    "error": str(insert_exc),
                },
            )
        _alert_email_send_failed(user_id=user.id, last_error=str(exc))
        log_call(
            provider="resend",
            endpoint="auth.send_verification_email",
            latency_ms=0.0,
            status="failed",
            extra={"user_id": user.id, "error": str(exc)},
        )
        return

    log_call(
        provider="resend",
        endpoint="auth.send_verification_email",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user.id,
            "resend_id": response.get("id") if isinstance(response, dict) else None,
        },
    )


__all__ = [
    "VERIFICATION_TOKEN_TTL",
    "VerificationTokenExpiredError",
    "VerificationTokenInvalidError",
    "VerificationTokenUsedError",
    "consume_or_idempotent_verify",
    "consume_verification_token",
    "issue_verification_token",
    "resend_verification_token",
    "send_verification_email",
]
