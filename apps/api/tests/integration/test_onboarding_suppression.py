"""Integration tests for T142 — onboarding-preselected N-001 suppression.

When the critic-seed onboarding wave bulk-creates Follow rows for new
users (each with ``Follow.source = "onboarding_preselected"``), the
dispatcher MUST suppress the corresponding N-001 follow.new
notification. Otherwise every critic-seed account gets a notification
storm on every new-user signup (NT-1).

The other follow types (N-002 request_pending, N-003 request_approved)
are NOT suppressed by this rule — they only fire on explicit user
action, never on the bulk onboarding path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import fakeredis.aioredis
import pytest
import pytest_asyncio

from auxd_api import redis_client as redis_module
from auxd_api.lib import observability as observability_module
from auxd_api.modules.notifications.dispatcher import (
    ONBOARDING_PRESELECTED_SOURCE,
    dispatch,
)
from auxd_api.modules.notifications.models import (
    Notification,
    NotificationType,
)
from auxd_api.modules.users.models import User


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module._client = client
    try:
        yield client
    finally:
        await client.aclose()
        redis_module._client = None


@pytest_asyncio.fixture
async def recipient() -> AsyncIterator[User]:
    await User.delete_all()
    await Notification.delete_all()
    user = User(
        handle="seed_account",
        email="seed@example.com",
        display_name="Critic Seed",
        password_hash="$argon2id$test",
    )
    await user.insert()
    yield user
    await User.delete_all()
    await Notification.delete_all()


@pytest.fixture
def emit_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def _fake_emit(
        *,
        user_id: str | None,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        captured.append({"user_id": user_id, "event": event, "properties": properties or {}})

    monkeypatch.setattr(observability_module, "emit_event", _fake_emit)
    # Also patch the dispatcher's bound reference (it imports emit_event by name).
    from auxd_api.modules.notifications import dispatcher as dispatcher_module

    monkeypatch.setattr(dispatcher_module, "emit_event", _fake_emit)
    return captured


# ---------------------------------------------------------------------------
# T142 happy path: onboarding source suppresses N-001.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_preselected_n001_suppressed(
    fake_redis: fakeredis.aioredis.FakeRedis,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """N-001 + source=onboarding_preselected -> no row + suppressed event."""
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "newbie", "actor_display_name": "Newbie"},
        actor_id="actor_newbie_ksuid_00",
        follow_source=ONBOARDING_PRESELECTED_SOURCE,
    )
    assert result is None
    assert (await Notification.find_all().to_list()) == []
    # The single dispatch event was a "suppressed" verdict (not "send").
    decisions = [
        e["properties"]["decision"] for e in emit_capture if e["event"] == "notification.dispatched"
    ]
    assert decisions == ["suppressed"]


@pytest.mark.asyncio
async def test_manual_follow_source_still_dispatches(
    fake_redis: fakeredis.aioredis.FakeRedis,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """source="manual" doesn't trigger the suppression rule."""
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_alice_ksuid_00",
        follow_source="manual",
    )
    assert result is not None
    assert result.type is NotificationType.N001_FOLLOW_NEW
    decisions = [
        e["properties"]["decision"] for e in emit_capture if e["event"] == "notification.dispatched"
    ]
    assert decisions == ["send"]


@pytest.mark.asyncio
async def test_profile_follow_source_default_still_dispatches(
    fake_redis: fakeredis.aioredis.FakeRedis,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """source="profile" (the social.create_follow default) dispatches."""
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_alice_ksuid_00",
        follow_source="profile",
    )
    assert result is not None
    decisions = [
        e["properties"]["decision"] for e in emit_capture if e["event"] == "notification.dispatched"
    ]
    assert decisions == ["send"]


@pytest.mark.asyncio
async def test_other_types_not_suppressed_by_onboarding_source(
    fake_redis: fakeredis.aioredis.FakeRedis,
    recipient: User,
    emit_capture: list[dict[str, Any]],
) -> None:
    """N-002 (and other types) still fire even with onboarding source.

    The suppression rule is N-001-specific. A test for N-002 with the
    same source guards against an over-broad rewrite.
    """
    result = await dispatch(
        user_id=recipient.id,
        type=NotificationType.N002_FOLLOW_REQUEST_PENDING,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="actor_alice_ksuid_00",
        follow_source=ONBOARDING_PRESELECTED_SOURCE,
    )
    assert result is not None
    assert result.type is NotificationType.N002_FOLLOW_REQUEST_PENDING
