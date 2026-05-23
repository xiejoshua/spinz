"""Email notification adapter (T135).

Sends transactional notifications through Resend with the
Constitution-P1 resilience contract (retry + Sentry alert on terminal
failure). On retry exhaustion the adapter writes a :class:`FailedEmail`
audit row so the operator console (sync-fix L4-003) can surface the
miss for manual replay or refund.

Design highlights:

* **Updater adapter shape.** The dispatcher passes ``notification_id``
  pointing at the in-app row it already persisted; this adapter stamps
  ``dispatch.email_sent_at`` on that row. When the row id is missing
  (e.g. the in-app channel was suppressed for this user), the adapter
  still attempts the send but skips the row update.
* **Type-driven NOOP.** Types whose ``email_subject`` is ``None`` in
  :data:`TYPES` have the email channel off by design — the dispatcher
  should never call us for those, but defense-in-depth returns ``None``
  immediately rather than rendering an empty subject.
* **Per-type Jinja templates.** Each type with ``email_subject`` set has
  a matching ``apps/api/src/auxd_api/templates/email/<key>.html`` that
  inherits from ``base.html`` (logo, footer with unsubscribe + manage
  links). Tracking pixels are deliberately absent per the taxonomy doc.
* **Retry + Sentry.** :func:`auxd_api.lib.resilience.retry` wraps the
  blocking Resend call (the SDK is sync — we hop into a thread via
  :func:`asyncio.to_thread`). After 3 attempts, a :class:`FailedEmail`
  document is inserted and a Sentry message tagged
  ``email.send_failed`` fires.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Final

import resend
import sentry_sdk
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from auxd_api.lib.observability import log_call
from auxd_api.lib.resilience import retry
from auxd_api.modules.notifications.models import (
    FailedEmail,
    Notification,
    NotificationType,
)
from auxd_api.modules.notifications.types import TYPES
from auxd_api.modules.users.models import User
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.notifications.email")

# Per-type → template filename map. Types whose ``email_subject`` is
# ``None`` deliberately have no entry — the adapter NOOPs for them.
_TEMPLATE_BY_TYPE: Final[dict[NotificationType, str]] = {
    NotificationType.N008_WEEKLY_DIGEST: "n008_weekly_digest.html",
    NotificationType.N013_ACCOUNT_DELETION_SCHEDULED: ("n013_account_deletion_scheduled.html"),
    NotificationType.N014_ACCOUNT_DELETION_REMINDER_7D: ("n014_account_deletion_reminder_7d.html"),
    NotificationType.N016_SECURITY_NEW_SESSION: "n016_security_new_session.html",
    NotificationType.N017_SECURITY_PASSWORD_CHANGED: ("n017_security_password_changed.html"),
}

_EMAIL_RETRY_ATTEMPTS: Final[int] = 3


# Jinja environment with strict-undefined + HTML autoescape. Strict
# undefined surfaces a missing payload key as a clear render error
# rather than blank-in-the-email — caught at adapter-call time, never
# in the recipient's inbox.
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Return the memoised Jinja environment.

    Constructed lazily so module import doesn't trigger package-resource
    lookup before the application is wired. ``PackageLoader`` resolves
    against the installed package; works under both src layout and
    editable installs.
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


# ---------------------------------------------------------------------------
# Sentry alert helpers
# ---------------------------------------------------------------------------


def _alert_email_send_failed(
    *,
    user_id: str,
    notif_type: NotificationType,
    last_error: str,
) -> None:
    """Emit a Sentry error tagged ``email.send_failed``.

    Pair with the FailedEmail audit row so an operator can correlate the
    document with the alert. Tag intentionally stable so Sentry alert
    rules can be built on top.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "notifications")
        scope.set_tag("status", "email.send_failed")
        scope.set_extra("user_id", user_id)
        scope.set_extra("type", notif_type.value)
        scope.set_extra("last_error", last_error)
        sentry_sdk.capture_message("email.send_failed", level="error")


# ---------------------------------------------------------------------------
# Resend blocking call wrapped in to_thread so the worker loop stays free.
# ---------------------------------------------------------------------------


def _resend_send_sync(
    *,
    api_key: str,
    from_address: str,
    to_address: str,
    subject: str,
    html: str,
) -> dict[str, Any]:
    """Synchronous Resend send. Wrapped in :func:`asyncio.to_thread`.

    Returns the Resend response dict. Raises ``Exception`` on any
    transport / 5xx failure — the retry layer in :meth:`EmailAdapter.send`
    handles the bounce-and-retry loop.
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
    # Resend SDK returns a typed-dict / dict[str, Any] — cast to keep mypy
    # happy without sprinkling ``# type: ignore`` through callers.
    return dict(response) if response else {}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class EmailAdapter:
    """Resend-backed email channel adapter.

    Conforms to :class:`auxd_api.modules.notifications.adapters.NotificationAdapter`.
    Stamps ``Notification.dispatch.email_sent_at`` on the in-app row the
    dispatcher already persisted (``notification_id``); on send failure
    after the retry budget is exhausted, writes a :class:`FailedEmail`
    audit row + emits a Sentry alert.
    """

    channel: str = "email"

    async def send(
        self,
        *,
        user_id: str,
        type: NotificationType,  # noqa: A002 — Protocol param name
        payload: dict[str, Any],
        actor_id: str | None = None,
        coalesced_count: int = 0,
        notification_id: str | None = None,
    ) -> Notification | None:
        """Render + send the email and update the audit trail.

        Returns the updated :class:`Notification` row when both the send
        succeeded AND ``notification_id`` was supplied. Returns ``None``
        for the type-NOOP path (no ``email_subject`` set), the disabled
        path (``RESEND_API_KEY`` unset), or any failure path — the audit
        of the failure lives in :class:`FailedEmail`.
        """
        _ = coalesced_count  # email layout is identity-based; per-row count

        spec = TYPES.get(type)
        if spec is None or spec.email_subject is None:
            # NOOP — the type has no email channel by spec. Defense in
            # depth: the dispatcher should not have called us for these.
            return None

        settings = get_settings()
        if settings.RESEND_API_KEY is None:
            # Disabled (local dev, test env with no real Resend key) —
            # log + return None gracefully so the dispatcher's email
            # branch is a NOOP rather than an error.
            _LOGGER.warning(
                "notifications.email.disabled",
                extra={
                    "event": "notifications.email.disabled",
                    "type": type.value,
                    "user_id": user_id,
                },
            )
            return None

        # Recipient profile lookup — handle + email. The dispatcher
        # already validated the user exists, but we re-load here so the
        # adapter is callable in isolation (digest worker uses this too).
        user = await User.find_one(User.id == user_id)
        if user is None:
            _LOGGER.warning(
                "notifications.email.recipient_missing",
                extra={
                    "event": "notifications.email.recipient_missing",
                    "type": type.value,
                    "user_id": user_id,
                },
            )
            return None

        template_filename = _TEMPLATE_BY_TYPE.get(type)
        if template_filename is None:
            # Type listed in TYPES with email_subject set but no template
            # mapped — programming error. Surface loudly.
            _LOGGER.error(
                "notifications.email.template_missing",
                extra={
                    "event": "notifications.email.template_missing",
                    "type": type.value,
                },
            )
            return None

        subject = spec.email_subject.format(**payload)

        # Build the render context. Common fields (recipient handle,
        # unsubscribe URL, public app URL) sit alongside the type-
        # specific payload so templates can mix-and-match.
        context: dict[str, Any] = {
            "subject": subject,
            "recipient_handle": user.handle,
            "public_app_url": settings.PUBLIC_APP_URL,
            "unsubscribe_url": (
                f"{settings.PUBLIC_APP_URL}/settings/notifications?unsubscribe={type.value}"
            ),
            "manage_url": f"{settings.PUBLIC_APP_URL}/settings/notifications",
            "cancel_url": f"{settings.PUBLIC_APP_URL}/settings/account",
            **payload,
        }

        try:
            template = _get_jinja_env().get_template(template_filename)
            html = template.render(**context)
        except Exception as exc:
            # Render failure is a programming error (missing template,
            # missing strict-undefined key). Log + abandon — no FailedEmail
            # write because the failure is upstream of the SDK call.
            _LOGGER.exception(
                "notifications.email.render_failed",
                extra={
                    "event": "notifications.email.render_failed",
                    "type": type.value,
                    "user_id": user_id,
                    "error": str(exc),
                },
            )
            _alert_email_send_failed(user_id=user_id, notif_type=type, last_error=f"render: {exc}")
            return None

        # Resend call wrapped in retry + to_thread. Resend SDK is sync;
        # to_thread avoids blocking the event loop. The retry layer fans
        # over network / transient 5xx errors; the inner Exception is
        # already in retry_on=(Exception,) by default.
        async def _attempt() -> dict[str, Any]:
            return await asyncio.to_thread(
                _resend_send_sync,
                api_key=settings.RESEND_API_KEY or "",
                from_address=settings.RESEND_FROM_ADDRESS,
                to_address=user.email,
                subject=subject,
                html=html,
            )

        last_error: str = ""
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
            last_error = f"{type.__name__ if False else 'Exception'}: {exc}"
            failed = FailedEmail(
                user_id=user_id,
                notification_type=type,
                payload=dict(payload),
                last_error=str(exc),
                retry_count=_EMAIL_RETRY_ATTEMPTS,
            )
            try:
                await failed.insert()
            except Exception as insert_exc:  # noqa: BLE001 — last-resort logging
                _LOGGER.exception(
                    "notifications.email.failed_email_insert_failed",
                    extra={
                        "event": "notifications.email.failed_email_insert_failed",
                        "type": type.value,
                        "user_id": user_id,
                        "error": str(insert_exc),
                    },
                )
            _alert_email_send_failed(user_id=user_id, notif_type=type, last_error=str(exc))
            log_call(
                provider="resend",
                endpoint="send_email",
                latency_ms=0.0,
                status="failed",
                extra={
                    "user_id": user_id,
                    "type": type.value,
                    "error": str(exc),
                },
            )
            _ = last_error  # captured above for clarity
            _ = actor_id  # adapter is recipient-centric, actor only matters for in-app
            return None

        log_call(
            provider="resend",
            endpoint="send_email",
            latency_ms=0.0,
            status="ok",
            extra={
                "user_id": user_id,
                "type": type.value,
                "resend_id": response.get("id") if isinstance(response, dict) else None,
            },
        )

        # Stamp dispatch.email_sent_at on the existing notification row.
        if notification_id is not None:
            notif = await Notification.find_one(Notification.id == notification_id)
            if notif is not None:
                notif.dispatch.email_sent_at = datetime.now(UTC)
                await notif.save()
                return notif
            _LOGGER.warning(
                "notifications.email.notification_row_missing",
                extra={
                    "event": "notifications.email.notification_row_missing",
                    "notification_id": notification_id,
                    "type": type.value,
                },
            )
        return None


__all__ = ["EmailAdapter"]
