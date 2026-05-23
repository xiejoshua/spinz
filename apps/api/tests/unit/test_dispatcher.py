"""Unit tests for the notification dispatcher (T131 + T132 + T142 + T144).

Covers:

* :func:`is_notifiable` predicate across pref / default / quiet-hours /
  block / status dimensions, including the security-type email lock.
* :func:`dispatch` happy path + every suppression branch (missing user,
  suspended user, fully suppressed channels, T142 onboarding-preselected
  follow source, coalescer drop / coalesce, adapter raise).
* :func:`dispatch` always emits exactly one ``notification.dispatched``
  PostHog event for the T144 measurement contract.

The Beanie autouse fixture from ``conftest.py`` wires the Documents to
mongomock-motor, so we can write / read User / Notification / Block rows
freely without spinning up Redis.

Coalescer + adapter are stubbed via monkeypatch on the relevant module
attributes — these are unit tests, the integration tests in
``tests/integration/test_coalescer.py`` exercise the real Redis path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, time
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from auxd_api.modules.notifications import (
    adapters as adapters_module,
)
from auxd_api.modules.notifications import (
    coalescer as coalescer_module,
)
from auxd_api.modules.notifications import (
    dispatcher as dispatcher_module,
)
from auxd_api.modules.notifications.adapters.in_app import InAppAdapter
from auxd_api.modules.notifications.coalescer import CoalesceDecision
from auxd_api.modules.notifications.dispatcher import (
    ONBOARDING_PRESELECTED_SOURCE,
    ChannelDecision,
    dispatch,
    is_notifiable,
)
from auxd_api.modules.notifications.models import (
    Notification,
    NotificationType,
)
from auxd_api.modules.social.models import Block, BlockReason
from auxd_api.modules.users.models import (
    User,
    UserStatus,
)

# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _clean_collections() -> AsyncIterator[None]:
    """Reset notification-relevant collections between tests."""
    await User.delete_all()
    await Notification.delete_all()
    await Block.delete_all()
    yield
    await User.delete_all()
    await Notification.delete_all()
    await Block.delete_all()


@pytest_asyncio.fixture
async def recipient() -> User:
    """A standard ACTIVE recipient with default preferences."""
    user = User(
        handle="recipient",
        email="recipient@example.com",
        display_name="Recipient",
        password_hash="$argon2id$test",
    )
    await user.insert()
    return user


@pytest.fixture(autouse=True)
def _stub_send_decisions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default coalescer + emit_event to "send" + capture so tests opt in to overrides.

    Each test that wants a non-send coalescer decision overrides
    ``coalescer_module.allow_dispatch`` itself.
    """
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="send")),
    )


@pytest.fixture
def emit_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture every ``notification.dispatched`` event emitted during a test."""
    captured: list[dict[str, Any]] = []

    def _fake_emit(
        *,
        user_id: str | None,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        captured.append({"user_id": user_id, "event": event, "properties": properties or {}})

    monkeypatch.setattr(dispatcher_module, "emit_event", _fake_emit)
    return captured


# ---------------------------------------------------------------------------
# is_notifiable (T132).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_notifiable_pref_on_returns_allowed(recipient: User) -> None:
    """Explicit pref dict ON beats default OFF."""
    recipient.notification_preferences.in_app[NotificationType.N007_FRIEND_HIGH_RATED.value] = True
    decision = await is_notifiable(recipient, NotificationType.N007_FRIEND_HIGH_RATED, "in_app")
    assert decision.allowed is True
    assert decision.reason is None


@pytest.mark.asyncio
async def test_is_notifiable_pref_off_returns_suppressed(recipient: User) -> None:
    """Explicit pref dict OFF overrides a default ON."""
    recipient.notification_preferences.in_app[NotificationType.N001_FOLLOW_NEW.value] = False
    decision = await is_notifiable(recipient, NotificationType.N001_FOLLOW_NEW, "in_app")
    assert decision.allowed is False
    assert decision.reason == "user_pref_off"


@pytest.mark.asyncio
async def test_is_notifiable_default_on_when_pref_absent(recipient: User) -> None:
    """Missing key in pref dict falls back to channel default."""
    # N-001 follow.new default in_app is ON.
    decision = await is_notifiable(recipient, NotificationType.N001_FOLLOW_NEW, "in_app")
    assert decision.allowed is True
    assert decision.reason is None


@pytest.mark.asyncio
async def test_is_notifiable_default_off_when_pref_absent(recipient: User) -> None:
    """Opt-in-only types are suppressed unless the user explicitly opts in."""
    # N-007 friend.high_rated default in_app is OFF.
    decision = await is_notifiable(recipient, NotificationType.N007_FRIEND_HIGH_RATED, "in_app")
    assert decision.allowed is False
    assert decision.reason == "channel_default_off"


@pytest.mark.asyncio
async def test_is_notifiable_blocked_actor_suppressed(recipient: User) -> None:
    """Actor blocked by recipient suppresses all channels."""
    blocked_actor_id = "blocked_actor_ksuid_0000000000"
    await Block(
        blocker_id=recipient.id,
        blockee_id=blocked_actor_id,
        reason=BlockReason.HARASSMENT,
    ).insert()

    decision = await is_notifiable(
        recipient,
        NotificationType.N001_FOLLOW_NEW,
        "in_app",
        actor_id=blocked_actor_id,
    )
    assert decision.allowed is False
    assert decision.reason == "blocked"


@pytest.mark.asyncio
async def test_is_notifiable_suspended_user_suppressed(recipient: User) -> None:
    """SUSPENDED status suppresses every channel for every type."""
    recipient.status = UserStatus.SUSPENDED
    decision = await is_notifiable(recipient, NotificationType.N001_FOLLOW_NEW, "in_app")
    assert decision.allowed is False
    assert decision.reason == "user_status"


@pytest.mark.asyncio
async def test_is_notifiable_quiet_hours_suppress_push(recipient: User) -> None:
    """Push inside quiet hours is suppressed."""
    # Window 22:00–08:00 NY local; now = 23:00 NY local.
    recipient.quiet_hours_start = time(22, 0)
    recipient.quiet_hours_end = time(8, 0)
    recipient.quiet_hours_tz = "America/New_York"
    # 04:00 UTC on a Wednesday in winter -> 23:00 EST the previous day.
    now_utc = datetime(2026, 1, 15, 4, 0, tzinfo=UTC)

    decision = await is_notifiable(
        recipient,
        NotificationType.N001_FOLLOW_NEW,
        "push",
        now=now_utc,
    )
    assert decision.allowed is False
    assert decision.reason == "quiet_hours"


@pytest.mark.asyncio
async def test_is_notifiable_quiet_hours_do_not_suppress_email(
    recipient: User,
) -> None:
    """Email bypasses quiet hours per NT-3."""
    recipient.quiet_hours_start = time(22, 0)
    recipient.quiet_hours_end = time(8, 0)
    recipient.quiet_hours_tz = "America/New_York"
    # 04:00 UTC -> 23:00 EST the prior day, inside quiet hours.
    now_utc = datetime(2026, 1, 15, 4, 0, tzinfo=UTC)

    # N-016 has default_email ON + email is LOCKED for this type, but
    # even setting that aside: pick N-013 which is default_email ON but
    # not locked, so the test exercises the quiet-hours bypass cleanly.
    decision = await is_notifiable(
        recipient,
        NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        "email",
        now=now_utc,
    )
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_is_notifiable_quiet_hours_overnight_wrap(recipient: User) -> None:
    """Overnight window (start > end) handles the midnight rollover correctly."""
    recipient.quiet_hours_start = time(22, 0)
    recipient.quiet_hours_end = time(8, 0)
    recipient.quiet_hours_tz = "America/New_York"

    # Inside the window — 02:00 EST.
    now_inside = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)  # -> 02:00 EST
    assert dispatcher_module._quiet_hours_active(recipient, now_inside) is True

    # Outside — 10:00 EST.
    now_outside = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)  # -> 10:00 EST
    assert dispatcher_module._quiet_hours_active(recipient, now_outside) is False


@pytest.mark.asyncio
async def test_is_notifiable_security_email_locked_on(recipient: User) -> None:
    """N-016 / N-017 email channel is allowed even when the user opts out."""
    recipient.notification_preferences.email[NotificationType.N016_SECURITY_NEW_SESSION.value] = (
        False
    )
    decision = await is_notifiable(recipient, NotificationType.N016_SECURITY_NEW_SESSION, "email")
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# dispatch (T131) — happy path + suppressions.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_happy_path_writes_in_app_notification(
    recipient: User, emit_capture: list[dict[str, Any]]
) -> None:
    """Happy path: in-app row written, returned, send event emitted."""
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_ksuid_0000000000",
    )
    assert isinstance(result, Notification)
    assert result.user_id == recipient.id
    assert result.type is NotificationType.N001_FOLLOW_NEW
    assert result.dispatch.in_app_delivered is True
    assert result.payload["actor_handle"] == "alice"

    # Exactly one ``notification.dispatched`` event with decision=send.
    sent_events = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert len(sent_events) == 1
    assert sent_events[0]["properties"]["decision"] == "send"
    assert sent_events[0]["properties"]["channels"] == ["in_app"]
    assert sent_events[0]["properties"]["type"] == "follow.new"


@pytest.mark.asyncio
async def test_dispatch_missing_recipient_returns_none(
    emit_capture: list[dict[str, Any]],
) -> None:
    """Unknown user_id -> None + warning + suppressed event."""
    result = await dispatch(
        user_id="missing_user_0000000000000000",
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_ksuid_0000000000",
    )
    assert result is None
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert len(sent) == 1
    assert sent[0]["properties"]["decision"] == "suppressed"
    assert sent[0]["properties"]["channels"] == []


@pytest.mark.asyncio
async def test_dispatch_suspended_recipient_returns_none(
    recipient: User, emit_capture: list[dict[str, Any]]
) -> None:
    """SUSPENDED users see no notifications."""
    recipient.status = UserStatus.SUSPENDED
    await recipient.save()

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_ksuid_0000000000",
    )
    assert result is None
    # No in-app rows.
    assert (await Notification.find_all().to_list()) == []
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert sent[0]["properties"]["decision"] == "suppressed"


@pytest.mark.asyncio
async def test_dispatch_onboarding_preselected_n001_suppressed(
    recipient: User, emit_capture: list[dict[str, Any]]
) -> None:
    """T142: critic-seed wave follows do not fire N-001."""
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "newbie", "actor_display_name": "Newbie"},
        actor_id="actor_ksuid_0000000000",
        follow_source=ONBOARDING_PRESELECTED_SOURCE,
    )
    assert result is None
    assert (await Notification.find_all().to_list()) == []
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert sent[0]["properties"]["decision"] == "suppressed"


@pytest.mark.asyncio
async def test_dispatch_per_channel_suppress_keeps_in_app(
    recipient: User, emit_capture: list[dict[str, Any]]
) -> None:
    """User with email + push OFF still receives the in-app row."""
    # N-001 default email = OFF, push = ON. Disable push too.
    recipient.notification_preferences.push[NotificationType.N001_FOLLOW_NEW.value] = False
    await recipient.save()

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_ksuid_0000000000",
    )
    assert isinstance(result, Notification)
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert sent[0]["properties"]["channels"] == ["in_app"]


@pytest.mark.asyncio
async def test_dispatch_coalesce_writes_rollup_row(
    monkeypatch: pytest.MonkeyPatch,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """coalesce verdict -> single in-app row tagged with coalesced_count > 0."""
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="coalesce", coalesced_window="hour")),
    )

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_ksuid_0000000000",
    )
    assert isinstance(result, Notification)
    assert result.payload.get("coalesced_count") == 1
    assert "coalesced_from" in result.payload
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert sent[0]["properties"]["decision"] == "coalesce"


@pytest.mark.asyncio
async def test_dispatch_drop_verdict_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """drop verdict (dedup) -> no in-app row, single drop event."""
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="drop", reason="dedup_window")),
    )

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N004_REVIEW_LIKED,
        payload={
            "actor_handle": "alice",
            "review_id": "rev_xyz",
            "album_title": "OK Computer",
        },
        actor_id="actor_ksuid_0000000000",
    )
    assert result is None
    assert (await Notification.find_all().to_list()) == []
    sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
    assert sent[0]["properties"]["decision"] == "drop"


@pytest.mark.asyncio
async def test_dispatch_emits_event_on_every_path(
    monkeypatch: pytest.MonkeyPatch,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """T144 contract: every dispatch fires exactly one PostHog event."""
    # send
    await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_send",
    )
    # coalesce
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="coalesce", coalesced_window="hour")),
    )
    await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_coalesce",
    )
    # drop
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="drop")),
    )
    await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_drop",
    )

    decisions = [e["properties"]["decision"] for e in emit_capture]
    assert decisions == ["send", "coalesce", "drop"]


@pytest.mark.asyncio
async def test_dispatch_adapter_exception_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """Adapter raising is captured by gather; dispatch still returns None gracefully."""

    class BoomAdapter:
        channel = "in_app"

        async def send(self, **kwargs: Any) -> Notification:  # noqa: ANN401
            raise RuntimeError("adapter exploded")

    # Swap the in-app adapter via the registry directly so the test stays
    # in unit-test territory (no dispatcher-internal monkeypatching).
    adapters_module.reset_registry()
    adapters_module.register_adapter(BoomAdapter())
    try:
        result = await dispatch(
            user_id=recipient.id,
            type=NotificationType.N001_FOLLOW_NEW,
            payload={"actor_handle": "alice", "actor_display_name": "Alice"},
            actor_id="actor_x",
        )
        # No in-app row landed, but no crash either.
        assert result is None
        assert (await Notification.find_all().to_list()) == []
        sent = [e for e in emit_capture if e["event"] == "notification.dispatched"]
        # The send branch fired the event; channels reflects the empty fan-out.
        assert sent[0]["properties"]["decision"] == "send"
        assert sent[0]["properties"]["channels"] == []
    finally:
        adapters_module.reset_registry()
        adapters_module.register_adapter(InAppAdapter())


@pytest.mark.asyncio
async def test_dispatch_inner_exception_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    recipient: User,
) -> None:
    """A catastrophic failure inside the chain returns None + Sentry alert."""

    captured_calls: list[str] = []

    def _fake_capture(message: str, level: str = "error") -> None:
        captured_calls.append(message)

    # Make ``validate_payload`` raise an unexpected error to exercise the
    # outer try/except.
    def _broken_validate(notif_type: NotificationType, payload: dict[str, Any]) -> None:
        raise RuntimeError("simulated dispatcher bug")

    import sentry_sdk

    monkeypatch.setattr(dispatcher_module, "validate_payload", _broken_validate)
    monkeypatch.setattr(sentry_sdk, "capture_message", _fake_capture)

    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_x",
    )
    assert result is None
    assert "notification.dispatcher_failed" in captured_calls


# ---------------------------------------------------------------------------
# ChannelDecision is a frozen value object.
# ---------------------------------------------------------------------------


def test_channel_decision_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    decision = ChannelDecision(channel="in_app", allowed=True)
    with pytest.raises(FrozenInstanceError):
        decision.allowed = False  # type: ignore[misc]
