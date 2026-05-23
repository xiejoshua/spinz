"""Integration tests for the in-app notification adapter (T134).

Uses the autouse Beanie + mongomock-motor fixture from ``conftest.py``
so the adapter writes against a live (mocked) ``notifications``
collection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from auxd_api.modules.notifications.adapters.in_app import InAppAdapter
from auxd_api.modules.notifications.models import Notification, NotificationType


@pytest_asyncio.fixture(autouse=True)
async def _clean() -> AsyncIterator[None]:
    await Notification.delete_all()
    yield
    await Notification.delete_all()


@pytest.mark.asyncio
async def test_in_app_send_writes_notification_row() -> None:
    """Adapter writes a row with the expected fields + in_app_delivered=True."""
    adapter = InAppAdapter()
    notif = await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="user_actor",
    )
    assert notif.user_id == "user_recipient"
    assert notif.type is NotificationType.N001_FOLLOW_NEW
    assert notif.actor_id == "user_actor"
    assert notif.payload["actor_handle"] == "alice"
    assert notif.dispatch.in_app_delivered is True
    assert notif.read_at is None

    # Persisted in the collection.
    found = await Notification.find_one(Notification.id == notif.id)
    assert found is not None
    assert found.user_id == "user_recipient"


@pytest.mark.asyncio
async def test_in_app_send_propagates_coalesced_count() -> None:
    """coalesced_count > 0 lands in the payload for the UI to render rollups."""
    adapter = InAppAdapter()
    notif = await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="user_actor",
        coalesced_count=4,
    )
    assert notif.payload.get("coalesced_count") == 4


@pytest.mark.asyncio
async def test_in_app_send_does_not_mutate_caller_payload() -> None:
    """The adapter copies the payload — caller's dict is untouched."""
    adapter = InAppAdapter()
    caller_payload: dict[str, object] = {
        "actor_handle": "alice",
        "actor_display_name": "Alice",
    }
    await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N001_FOLLOW_NEW,
        payload=caller_payload,
        actor_id="user_actor",
        coalesced_count=2,
    )
    assert "coalesced_count" not in caller_payload


@pytest.mark.asyncio
async def test_in_app_send_creates_separate_rows_per_call() -> None:
    """Two sends → two rows. Coalescing is the dispatcher's job, not the adapter's."""
    adapter = InAppAdapter()
    first = await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id="user_actor_1",
    )
    second = await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N001_FOLLOW_NEW,
        payload={"actor_handle": "bob", "actor_display_name": "Bob"},
        actor_id="user_actor_2",
    )
    assert first.id != second.id
    rows = await Notification.find(Notification.user_id == "user_recipient").to_list()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_in_app_send_no_actor_for_system_notification() -> None:
    """actor_id=None is valid (system notifications like weekly.digest)."""
    adapter = InAppAdapter()
    notif = await adapter.send(
        user_id="user_recipient",
        type=NotificationType.N008_WEEKLY_DIGEST,
        payload={"summary_url": "https://auxd.fm/d/abc", "hero_count": 3},
        actor_id=None,
    )
    assert notif.actor_id is None
    assert notif.dispatch.in_app_delivered is True
