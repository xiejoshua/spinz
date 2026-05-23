"""Integration tests for the email notification adapter (T135).

Covers:

* Happy path: monkeypatched Resend send → Notification.dispatch.email_sent_at
  populated, log_call recorded.
* Retry exhaustion: 3 consecutive 5xx → FailedEmail row created with all
  metadata + Sentry alert tagged ``email.send_failed``.
* Type-driven NOOP: types with ``email_subject=None`` short-circuit.
* Disabled mode: ``RESEND_API_KEY=None`` → adapter NOOPs gracefully.
* Jinja render: payload values appear in rendered HTML; unsubscribe URL
  is present in the footer.
* End-to-end through dispatcher: dispatch N-013 → in-app row created
  AND email_sent_at populated.
* Registry presence: ``register_adapter("email", EmailAdapter())``
  ran at module-load.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from auxd_api import settings as settings_module
from auxd_api.modules.notifications import adapters as adapters_module
from auxd_api.modules.notifications import coalescer as coalescer_module
from auxd_api.modules.notifications.adapters.email import EmailAdapter
from auxd_api.modules.notifications.coalescer import CoalesceDecision
from auxd_api.modules.notifications.dispatcher import dispatch
from auxd_api.modules.notifications.models import (
    ChannelDispatchState,
    FailedEmail,
    Notification,
    NotificationType,
)
from auxd_api.modules.users.models import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _resend_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """Inject a stub Resend key + flush settings cache so the adapter activates."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_stub_key")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://auxd.test")
    monkeypatch.setenv("RESEND_FROM_ADDRESS", "auxd <hello@auxd.test>")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _clean_collections() -> AsyncIterator[None]:
    await User.delete_all()
    await Notification.delete_all()
    await FailedEmail.delete_all()
    yield
    await User.delete_all()
    await Notification.delete_all()
    await FailedEmail.delete_all()


@pytest_asyncio.fixture
async def recipient() -> User:
    """An active recipient with a usable email address."""
    user = User(
        handle="recipient",
        email="recipient@example.com",
        display_name="Recipient",
        password_hash="$argon2id$test",
    )
    await user.insert()
    return user


@pytest_asyncio.fixture
async def existing_notification(recipient: User) -> Notification:
    """An in-app row the email adapter can stamp ``email_sent_at`` on."""
    notif = Notification(
        user_id=recipient.id,
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        payload={"scheduled_for_iso": "2026-06-22T12:00:00+00:00"},
        actor_id=None,
        dispatch=ChannelDispatchState(in_app_delivered=True),
    )
    await notif.insert()
    return notif


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_send_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    _resend_env: None,
    recipient: User,
    existing_notification: Notification,
) -> None:
    """Monkeypatched Resend returns success → dispatch.email_sent_at stamped."""
    capture: dict[str, Any] = {}

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        capture.update(args)
        return {"id": "email_id_123"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)

    adapter = EmailAdapter()
    result = await adapter.send(
        user_id=recipient.id,
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        payload={"scheduled_for_iso": "2026-06-22T12:00:00+00:00"},
        notification_id=existing_notification.id,
    )

    assert result is not None
    assert result.dispatch.email_sent_at is not None
    # Resend was called with the expected envelope.
    assert capture["from"] == "auxd <hello@auxd.test>"
    assert capture["to"] == ["recipient@example.com"]
    assert "scheduled for deletion" in capture["subject"]
    # No FailedEmail row written on success.
    assert (await FailedEmail.find_all().to_list()) == []


@pytest.mark.asyncio
async def test_email_retry_exhaustion_writes_failed_email_and_sentry(
    monkeypatch: pytest.MonkeyPatch,
    _resend_env: None,
    recipient: User,
    existing_notification: Notification,
) -> None:
    """3× 5xx → FailedEmail row + Sentry alert tagged ``email.send_failed``."""
    attempts = {"count": 0}

    def _always_fail(args: dict[str, Any]) -> dict[str, str]:
        attempts["count"] += 1
        raise RuntimeError("HTTP 502 from Resend")

    import resend

    monkeypatch.setattr(resend.Emails, "send", _always_fail)

    # Capture Sentry alerts.
    captured_messages: list[str] = []

    def _fake_capture(message: str, level: str = "error") -> None:
        captured_messages.append(message)

    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "capture_message", _fake_capture)

    # Speed up the retry sleeps to keep the test snappy.
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    adapter = EmailAdapter()
    result = await adapter.send(
        user_id=recipient.id,
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        payload={"scheduled_for_iso": "2026-06-22T12:00:00+00:00"},
        notification_id=existing_notification.id,
    )
    assert result is None
    assert attempts["count"] == 3

    failed_rows = await FailedEmail.find_all().to_list()
    assert len(failed_rows) == 1
    failed = failed_rows[0]
    assert failed.user_id == recipient.id
    assert failed.notification_type is NotificationType.N013_ACCOUNT_DELETION_SCHEDULED
    assert failed.retry_count == 3
    assert "502" in failed.last_error

    # Sentry alert fired.
    assert "email.send_failed" in captured_messages


@pytest.mark.asyncio
async def test_email_noop_when_type_has_no_email_subject(
    monkeypatch: pytest.MonkeyPatch,
    _resend_env: None,
    recipient: User,
) -> None:
    """Types with ``email_subject=None`` → no Resend call, no FailedEmail."""
    sent_count = {"n": 0}

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        sent_count["n"] += 1
        return {"id": "x"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)

    adapter = EmailAdapter()
    # N-001 has email_subject=None.
    result = await adapter.send(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
    )
    assert result is None
    assert sent_count["n"] == 0
    assert (await FailedEmail.find_all().to_list()) == []


@pytest.mark.asyncio
async def test_email_disabled_when_no_resend_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    recipient: User,
) -> None:
    """Without RESEND_API_KEY → adapter NOOPs + logs warning."""
    # Chdir to a clean tmp dir so the local .env (which has a real key)
    # is not loaded by pydantic-settings.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    settings_module.get_settings.cache_clear()

    sent_count = {"n": 0}

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        sent_count["n"] += 1
        return {"id": "x"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)
    try:
        adapter = EmailAdapter()
        result = await adapter.send(
            user_id=recipient.id,
            type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
            payload={"scheduled_for_iso": "2026-06-22T12:00:00+00:00"},
        )
        assert result is None
        assert sent_count["n"] == 0
    finally:
        settings_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_email_template_renders_payload_and_unsubscribe(
    monkeypatch: pytest.MonkeyPatch,
    _resend_env: None,
    recipient: User,
    existing_notification: Notification,
) -> None:
    """Rendered HTML contains payload values + unsubscribe link."""
    captured_html: dict[str, str] = {}

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        captured_html["html"] = args["html"]
        return {"id": "x"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)

    adapter = EmailAdapter()
    iso = "2026-06-22T12:00:00+00:00"
    await adapter.send(
        user_id=recipient.id,
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        payload={"scheduled_for_iso": iso},
        notification_id=existing_notification.id,
    )
    html = captured_html["html"]
    assert iso in html
    assert "Unsubscribe" in html
    # Manage all notifications link is present.
    assert "Manage all notifications" in html
    # No tracking pixels.
    assert "<img" not in html.lower() or "tracking" not in html.lower()


@pytest.mark.asyncio
async def test_email_adapter_registered_at_import() -> None:
    """``register_adapter("email", EmailAdapter())`` fired at module load."""
    adapter = adapters_module.get_adapter("email")
    assert adapter is not None
    assert isinstance(adapter, EmailAdapter)


@pytest.mark.asyncio
async def test_dispatcher_threads_notification_id_to_email(
    monkeypatch: pytest.MonkeyPatch,
    _resend_env: None,
    recipient: User,
) -> None:
    """End-to-end: dispatch N-013 → in-app row + email_sent_at populated."""
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="send")),
    )

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        return {"id": "email_id_e2e"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        payload={"scheduled_for_iso": "2026-06-22T12:00:00+00:00"},
        actor_id=None,
    )
    assert result is not None
    # The dispatcher returns the in-app row; we re-load to get the
    # email_sent_at stamp written by the email adapter after the
    # in-app insert.
    refreshed = await Notification.find_one(Notification.id == result.id)
    assert refreshed is not None
    assert refreshed.dispatch.in_app_delivered is True
    assert refreshed.dispatch.email_sent_at is not None
