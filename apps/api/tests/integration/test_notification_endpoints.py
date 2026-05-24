"""Integration tests for the notification inbox + preference endpoints (T139 + T140).

Covers the six new routes added to ``notifications/routes.py``:

* GET /notifications — paginated list, actor denormalisation, cursor.
* GET /notifications/unread-count — cheap badge poll.
* POST /notifications/{id}/read — owner-only, idempotent.
* POST /notifications/mark-all-read — bulk flip.
* GET /users/me/notification-preferences — flatten + computed enabled.
* PUT /users/me/notification-preferences — validates security-email-lock,
  quiet-hours-incomplete, invalid-timezone.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.notifications.models import (
    ChannelDispatchState,
    Notification,
    NotificationType,
)
from auxd_api.modules.notifications.routes import router as notifications_router
from auxd_api.modules.users.models import NotificationPreferencesSubDoc, User
from tests.integration._auth_helpers import FakeAuthMiddleware


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(notifications_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test",
        display_name=handle.capitalize(),
        avatar_url=f"https://cdn.example.com/{handle}.png",
    )


def _make_notification(
    *,
    user_id: str,
    notif_type: NotificationType = NotificationType.N001_FOLLOW_NEW,
    actor_id: str | None = "user-actor",
    payload: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    read_at: datetime | None = None,
) -> Notification:
    return Notification(
        user_id=user_id,
        type=notif_type,
        payload=payload or {"actor_handle": "alice", "actor_display_name": "Alice"},
        actor_id=actor_id,
        dispatch=ChannelDispatchState(in_app_delivered=True),
        read_at=read_at,
        created_at=created_at or datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Notification.delete_all()
    await User.delete_all()
    yield
    await Notification.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_notifications_with_actor_denormalised(
    _clean_env: None, _clean_db: None
) -> None:
    """Each row includes actor handle/display_name/avatar from the User row."""
    recipient = _make_user("user-recipient", "viewer")
    actor = _make_user("user-actor", "alice")
    await recipient.insert()
    await actor.insert()

    notif = _make_notification(user_id=recipient.id, actor_id=actor.id)
    await notif.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["notifications"]) == 1
    row = body["notifications"][0]
    assert row["id"] == notif.id
    assert row["type"] == "follow.new"
    assert row["actor_id"] == actor.id
    assert row["actor_handle"] == "alice"
    assert row["actor_display_name"] == "Alice"
    assert row["actor_avatar_url"] == "https://cdn.example.com/alice.png"
    assert row["read_at"] is None
    assert body["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_sorts_created_at_desc(_clean_env: None, _clean_db: None) -> None:
    """Most-recent notification first regardless of insert order."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()

    now = datetime.now(UTC)
    older = _make_notification(user_id=recipient.id, created_at=now - timedelta(hours=2))
    newer = _make_notification(user_id=recipient.id, created_at=now - timedelta(minutes=10))
    await older.insert()
    await newer.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications",
        headers={"X-User-Id": recipient.id},
    )
    body = response.json()
    ids = [row["id"] for row in body["notifications"]]
    assert ids == [newer.id, older.id]


@pytest.mark.asyncio
async def test_list_filters_to_current_user_only(_clean_env: None, _clean_db: None) -> None:
    """A notification for a different user is invisible to the caller."""
    me = _make_user("user-me", "meee")
    other = _make_user("user-other", "other")
    await me.insert()
    await other.insert()

    mine = _make_notification(user_id=me.id)
    theirs = _make_notification(user_id=other.id)
    await mine.insert()
    await theirs.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications",
        headers={"X-User-Id": me.id},
    )
    body = response.json()
    ids = [row["id"] for row in body["notifications"]]
    assert ids == [mine.id]


@pytest.mark.asyncio
async def test_list_cursor_paginates(_clean_env: None, _clean_db: None) -> None:
    """Cursor returns the next page; final page has ``next_cursor: null``."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()

    now = datetime.now(UTC)
    for i in range(5):
        await _make_notification(
            user_id=recipient.id,
            created_at=now - timedelta(minutes=i),
        ).insert()

    client = TestClient(_make_app())
    first = client.get(
        "/api/v1/notifications?limit=2",
        headers={"X-User-Id": recipient.id},
    )
    body_first = first.json()
    assert len(body_first["notifications"]) == 2
    assert body_first["next_cursor"] is not None

    second = client.get(
        f"/api/v1/notifications?limit=2&cursor={body_first['next_cursor']}",
        headers={"X-User-Id": recipient.id},
    )
    body_second = second.json()
    assert len(body_second["notifications"]) == 2
    assert body_second["next_cursor"] is not None

    third = client.get(
        f"/api/v1/notifications?limit=2&cursor={body_second['next_cursor']}",
        headers={"X-User-Id": recipient.id},
    )
    body_third = third.json()
    # 5 total; 2+2 = 4; one more on the last page; no cursor after.
    assert len(body_third["notifications"]) == 1
    assert body_third["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_caps_limit_at_max(_clean_env: None, _clean_db: None) -> None:
    """Asking for limit=999 is rejected by FastAPI Query validator (422)."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications?limit=999",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    response = TestClient(_make_app()).get("/api/v1/notifications")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_surfaces_coalesced_count(_clean_env: None, _clean_db: None) -> None:
    """Payload's ``coalesced_count`` is hoisted onto the response row."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    notif = _make_notification(
        user_id=recipient.id,
        payload={
            "actor_handle": "alice",
            "actor_display_name": "Alice",
            "coalesced_count": 4,
        },
    )
    await notif.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications",
        headers={"X-User-Id": recipient.id},
    )
    assert response.json()["notifications"][0]["coalesced_count"] == 4


# ---------------------------------------------------------------------------
# GET /notifications/unread-count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unread_count_returns_count(_clean_env: None, _clean_db: None) -> None:
    """Returns the number of unread notifications for the current user."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    now = datetime.now(UTC)
    await _make_notification(user_id=recipient.id, read_at=None).insert()
    await _make_notification(user_id=recipient.id, read_at=None).insert()
    await _make_notification(user_id=recipient.id, read_at=now).insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications/unread-count",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 200
    assert response.json() == {"count": 2}


@pytest.mark.asyncio
async def test_unread_count_zero_when_empty(_clean_env: None, _clean_db: None) -> None:
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/notifications/unread-count",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 200
    assert response.json() == {"count": 0}


# ---------------------------------------------------------------------------
# POST /notifications/{id}/read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_read_sets_read_at(_clean_env: None, _clean_db: None) -> None:
    """Single-row mark sets read_at; ok=true."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    notif = _make_notification(user_id=recipient.id)
    await notif.insert()
    assert notif.read_at is None

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/notifications/{notif.id}/read",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    refreshed = await Notification.find_one(Notification.id == notif.id)
    assert refreshed is not None
    assert refreshed.read_at is not None


@pytest.mark.asyncio
async def test_mark_read_is_idempotent(_clean_env: None, _clean_db: None) -> None:
    """Second call doesn't bump read_at and still returns ok."""
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    notif = _make_notification(user_id=recipient.id)
    await notif.insert()
    client = TestClient(_make_app())
    first = client.post(
        f"/api/v1/notifications/{notif.id}/read",
        headers={"X-User-Id": recipient.id},
    )
    first_row = await Notification.find_one(Notification.id == notif.id)
    assert first_row is not None
    first_read_at = first_row.read_at

    second = client.post(
        f"/api/v1/notifications/{notif.id}/read",
        headers={"X-User-Id": recipient.id},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    second_row = await Notification.find_one(Notification.id == notif.id)
    assert second_row is not None
    assert second_row.read_at == first_read_at


@pytest.mark.asyncio
async def test_mark_read_non_owner_returns_404(_clean_env: None, _clean_db: None) -> None:
    """Marking a notification owned by someone else returns 404."""
    owner = _make_user("user-owner", "owner")
    intruder = _make_user("user-intruder", "intruder")
    await owner.insert()
    await intruder.insert()
    notif = _make_notification(user_id=owner.id)
    await notif.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/notifications/{notif.id}/read",
        headers={"X-User-Id": intruder.id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_read_missing_returns_404(_clean_env: None, _clean_db: None) -> None:
    recipient = _make_user("user-recipient", "viewer")
    await recipient.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/notifications/nonexistent-id/read",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_all_read_flips_every_unread(_clean_env: None, _clean_db: None) -> None:
    """Bulk flip stamps read_at on every unread row owned by the user."""
    recipient = _make_user("user-recipient", "viewer")
    other = _make_user("user-other", "other")
    await recipient.insert()
    await other.insert()
    now = datetime.now(UTC)
    for _ in range(3):
        await _make_notification(user_id=recipient.id, read_at=None).insert()
    # Already-read row should NOT be re-stamped.
    already_read = _make_notification(user_id=recipient.id, read_at=now)
    await already_read.insert()
    # Other user's unread row should NOT be touched.
    others = _make_notification(user_id=other.id, read_at=None)
    await others.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/notifications/mark-all-read",
        headers={"X-User-Id": recipient.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["marked"] == 3

    # Other user's row still unread.
    untouched = await Notification.find_one(Notification.id == others.id)
    assert untouched is not None
    assert untouched.read_at is None


@pytest.mark.asyncio
async def test_mark_all_read_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    response = TestClient(_make_app()).post("/api/v1/notifications/mark-all-read")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /users/me/notification-preferences
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prefs_get_flattens_quiet_hours(_clean_env: None, _clean_db: None) -> None:
    """Quiet-hours fields are flattened into a nested object with computed ``enabled``."""
    user = _make_user("user-prefs", "prefs")
    user.notification_preferences = NotificationPreferencesSubDoc(
        in_app={"follow.new": True},
        email={"weekly.digest": True},
        push={"follow.new": False},
        weekly_digest=True,
    )
    user.quiet_hours_start = time(22, 0)
    user.quiet_hours_end = time(8, 0)
    user.quiet_hours_tz = "America/New_York"
    await user.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["in_app"] == {"follow.new": True}
    assert body["email"] == {"weekly.digest": True}
    assert body["push"] == {"follow.new": False}
    assert body["weekly_digest"] is True
    assert body["quiet_hours"] == {
        "enabled": True,
        "start": "22:00",
        "end": "08:00",
        "tz": "America/New_York",
    }


@pytest.mark.asyncio
async def test_prefs_get_enabled_false_when_unset(_clean_env: None, _clean_db: None) -> None:
    """``enabled`` is False when either start or end is missing."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
    )
    body = response.json()
    assert body["quiet_hours"]["enabled"] is False
    assert body["quiet_hours"]["start"] is None
    assert body["quiet_hours"]["end"] is None
    assert body["quiet_hours"]["tz"] == "UTC"


@pytest.mark.asyncio
async def test_prefs_get_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    response = TestClient(_make_app()).get("/api/v1/users/me/notification-preferences")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /users/me/notification-preferences
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prefs_put_persists_full_payload(_clean_env: None, _clean_db: None) -> None:
    """Round-trip: PUT then GET returns the same payload."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    payload = {
        "in_app": {"follow.new": True, "review.liked": False},
        "email": {"weekly.digest": True},
        "push": {"follow.new": False},
        "weekly_digest": False,
        "quiet_hours": {
            "enabled": True,
            "start": "23:30",
            "end": "07:15",
            "tz": "America/Los_Angeles",
        },
    }
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["in_app"] == payload["in_app"]
    assert body["email"] == payload["email"]
    assert body["push"] == payload["push"]
    assert body["weekly_digest"] is False
    assert body["quiet_hours"] == payload["quiet_hours"]

    # And the User row reflects the change.
    refreshed = await User.find_one(User.id == user.id)
    assert refreshed is not None
    assert refreshed.quiet_hours_start == time(23, 30)
    assert refreshed.quiet_hours_end == time(7, 15)
    assert refreshed.quiet_hours_tz == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_prefs_put_rejects_security_email_off(_clean_env: None, _clean_db: None) -> None:
    """N-016 (security.new_session) email cannot be set False."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {},
            "email": {"security.new_session": False},
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": False, "tz": "UTC"},
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "security_email_locked"
    assert detail["type"] == "security.new_session"


@pytest.mark.asyncio
async def test_prefs_put_allows_security_email_true(_clean_env: None, _clean_db: None) -> None:
    """Explicit True for a locked type is fine — it's the default anyway."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {},
            "email": {
                "security.new_session": True,
                "security.password_changed": True,
            },
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": False, "tz": "UTC"},
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_prefs_put_rejects_invalid_timezone(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {},
            "email": {},
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": False, "tz": "Atlantis/Lost_City"},
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_timezone"


@pytest.mark.asyncio
async def test_prefs_put_rejects_enabled_without_bounds(_clean_env: None, _clean_db: None) -> None:
    """quiet_hours.enabled=True without start/end is 422."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {},
            "email": {},
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": True, "tz": "UTC"},
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "quiet_hours_incomplete"


@pytest.mark.asyncio
async def test_prefs_put_rejects_unknown_type_key(_clean_env: None, _clean_db: None) -> None:
    """Unknown notification type keys are rejected by the validator."""
    user = _make_user("user-prefs", "prefs")
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {"made.up.type": True},
            "email": {},
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": False, "tz": "UTC"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_prefs_put_clears_quiet_hours_on_disable(_clean_env: None, _clean_db: None) -> None:
    """Setting enabled=False clears any previously persisted start/end."""
    user = _make_user("user-prefs", "prefs")
    user.quiet_hours_start = time(22, 0)
    user.quiet_hours_end = time(8, 0)
    await user.insert()
    client = TestClient(_make_app())
    response = client.put(
        "/api/v1/users/me/notification-preferences",
        headers={"X-User-Id": user.id},
        json={
            "in_app": {},
            "email": {},
            "push": {},
            "weekly_digest": True,
            "quiet_hours": {"enabled": False, "tz": "UTC"},
        },
    )
    assert response.status_code == 200, response.text
    refreshed = await User.find_one(User.id == user.id)
    assert refreshed is not None
    assert refreshed.quiet_hours_start is None
    assert refreshed.quiet_hours_end is None
