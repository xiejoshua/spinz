"""Integration tests for diary <-> backlog auto-remove (T096) + event (T100).

Drives ``POST /api/v1/diary/entries`` end-to-end with the backlog
preloaded for the same album and asserts:

* The fresh log removes the matching backlog item.
* ``LogEntryResult.backlog_item_removed`` propagates to the route layer.
* The route emits a single ``backlog.converted_to_log`` PostHog event.
* The idempotent path (60s double-tap) does NOT re-trigger the event
  or the auto-remove.
* The ``User.keep_backlog_after_log`` opt-out keeps the item.
* A log for an album that was never queued leaves the backlog alone
  and emits no conversion event (the common case).
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "DISCOGS_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            request.state.session = Session(
                user_id=user_id,
                csrf_token="test-csrf",
                issued_at=0,
                expires_at=int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
                session_version=1,
            )
        else:
            request.state.session = None
        return await call_next(request)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(_FakeAuthMiddleware)
    app.include_router(diary_router, prefix="/api/v1")
    return app


def _make_album(album_id: str = "album-int-001") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="Interaction Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_user(
    user_id: str = "user-casey",
    handle: str = "casey",
    *,
    keep_backlog_after_log: bool = False,
) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        keep_backlog_after_log=keep_backlog_after_log,
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await User.delete_all()


async def _preload_backlog_with_album(*, user_id: str, album_id: str) -> BacklogItem:
    """Insert a User, Backlog, and BacklogItem in one helper."""
    backlog = Backlog(user_id=user_id)
    await backlog.insert()
    item = BacklogItem(backlog_id=backlog.id, album_id=album_id, position=1)
    await item.insert()
    return item


# ---------------------------------------------------------------------------
# T096 — auto-remove on log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_removes_matching_backlog_item(_clean_env: None, _clean_db: None) -> None:
    user = _make_user()
    await user.insert()
    album = _make_album()
    await album.insert()
    item = await _preload_backlog_with_album(user_id=user.id, album_id=album.id)

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": user.id},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert response.status_code == 201
    # The matching BacklogItem is gone.
    assert await BacklogItem.get(item.id) is None


@pytest.mark.asyncio
async def test_log_without_backlog_match_leaves_backlog_alone(
    _clean_env: None, _clean_db: None
) -> None:
    """Logging an album that was never queued is a clean no-op for the backlog."""
    user = _make_user()
    await user.insert()
    other_album = _make_album("album-other")
    await other_album.insert()
    queued = _make_album("album-queued")
    await queued.insert()
    # Backlog has *some* item, but not the one we're logging.
    queued_item = await _preload_backlog_with_album(user_id=user.id, album_id=queued.id)

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": user.id},
        json={"album_id": other_album.id, "rating": 4.0},
    )
    assert response.status_code == 201
    # The unrelated backlog item is untouched.
    assert await BacklogItem.get(queued_item.id) is not None


@pytest.mark.asyncio
async def test_log_with_keep_after_log_keeps_item(_clean_env: None, _clean_db: None) -> None:
    """When ``keep_backlog_after_log=True``, the matching item stays in the queue."""
    user = _make_user(keep_backlog_after_log=True)
    await user.insert()
    album = _make_album()
    await album.insert()
    item = await _preload_backlog_with_album(user_id=user.id, album_id=album.id)

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": user.id},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert response.status_code == 201
    # Item is still present.
    assert await BacklogItem.get(item.id) is not None


@pytest.mark.asyncio
async def test_log_with_no_backlog_row_is_safe(_clean_env: None, _clean_db: None) -> None:
    """User has never opened the backlog — auto-remove is a clean no-op."""
    user = _make_user()
    await user.insert()
    album = _make_album()
    await album.insert()
    # No Backlog row exists.

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": user.id},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert response.status_code == 201
    # And no Backlog was auto-created on this path either.
    assert await Backlog.find_one({"user_id": user.id}) is None


@pytest.mark.asyncio
async def test_log_compacts_remaining_positions(_clean_env: None, _clean_db: None) -> None:
    """Auto-remove leaves the rest of the queue in 1, 2, 3 order."""
    user = _make_user()
    await user.insert()
    a, b, c = _make_album("a"), _make_album("b"), _make_album("c")
    for album in (a, b, c):
        await album.insert()
    backlog = Backlog(user_id=user.id)
    await backlog.insert()
    items = [
        BacklogItem(backlog_id=backlog.id, album_id=a.id, position=1),
        BacklogItem(backlog_id=backlog.id, album_id=b.id, position=2),
        BacklogItem(backlog_id=backlog.id, album_id=c.id, position=3),
    ]
    for item in items:
        await item.insert()

    client = TestClient(_make_app())
    # Log the middle one — should compact positions to 1, 2.
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": user.id},
        json={"album_id": b.id, "rating": 4.0},
    )
    assert response.status_code == 201

    survivors = await BacklogItem.find({"backlog_id": backlog.id}).sort("+position").to_list()
    assert [item.position for item in survivors] == [1, 2]
    assert [item.album_id for item in survivors] == [a.id, c.id]


# ---------------------------------------------------------------------------
# T100 — backlog.converted_to_log event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_emits_conversion_event_when_item_removed(
    _clean_env: None, _clean_db: None
) -> None:
    user = _make_user()
    await user.insert()
    album = _make_album()
    await album.insert()
    await _preload_backlog_with_album(user_id=user.id, album_id=album.id)

    client = TestClient(_make_app())
    with patch("auxd_api.modules.diary.routes.emit_event") as mock_emit:
        response = client.post(
            "/api/v1/diary/entries",
            headers={"X-User-Id": user.id},
            json={"album_id": album.id, "rating": 4.5},
        )
        assert response.status_code == 201

    # Exactly one ``backlog.converted_to_log`` call.
    conversion_calls = [
        call
        for call in mock_emit.call_args_list
        if call.kwargs.get("event") == "backlog.converted_to_log"
    ]
    assert len(conversion_calls) == 1
    props = conversion_calls[0].kwargs["properties"]
    assert props["album_id"] == album.id
    assert props["entry_id"] == response.json()["id"]
    assert props["source"] == "manual"


@pytest.mark.asyncio
async def test_log_does_not_emit_event_when_not_in_backlog(
    _clean_env: None, _clean_db: None
) -> None:
    user = _make_user()
    await user.insert()
    album = _make_album()
    await album.insert()
    # No backlog item for this album.

    client = TestClient(_make_app())
    with patch("auxd_api.modules.diary.routes.emit_event") as mock_emit:
        response = client.post(
            "/api/v1/diary/entries",
            headers={"X-User-Id": user.id},
            json={"album_id": album.id, "rating": 4.5},
        )
        assert response.status_code == 201

    conversion_calls = [
        call
        for call in mock_emit.call_args_list
        if call.kwargs.get("event") == "backlog.converted_to_log"
    ]
    assert conversion_calls == []


@pytest.mark.asyncio
async def test_log_does_not_emit_event_when_keep_after_log_is_true(
    _clean_env: None, _clean_db: None
) -> None:
    user = _make_user(keep_backlog_after_log=True)
    await user.insert()
    album = _make_album()
    await album.insert()
    await _preload_backlog_with_album(user_id=user.id, album_id=album.id)

    client = TestClient(_make_app())
    with patch("auxd_api.modules.diary.routes.emit_event") as mock_emit:
        response = client.post(
            "/api/v1/diary/entries",
            headers={"X-User-Id": user.id},
            json={"album_id": album.id, "rating": 4.5},
        )
        assert response.status_code == 201

    conversion_calls = [
        call
        for call in mock_emit.call_args_list
        if call.kwargs.get("event") == "backlog.converted_to_log"
    ]
    assert conversion_calls == []


@pytest.mark.asyncio
async def test_idempotent_log_does_not_emit_event_twice(_clean_env: None, _clean_db: None) -> None:
    """A double-tap log within 60s emits the conversion event exactly once."""
    user = _make_user()
    await user.insert()
    album = _make_album()
    await album.insert()
    await _preload_backlog_with_album(user_id=user.id, album_id=album.id)

    client = TestClient(_make_app())
    with patch("auxd_api.modules.diary.routes.emit_event") as mock_emit:
        first = client.post(
            "/api/v1/diary/entries",
            headers={"X-User-Id": user.id},
            json={"album_id": album.id, "rating": 4.5},
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/diary/entries",
            headers={"X-User-Id": user.id},
            json={"album_id": album.id, "rating": 4.5},
        )
        assert second.status_code == 200
        # Same entry id — the idempotent path returned the existing row.
        assert second.json()["id"] == first.json()["id"]

    conversion_calls = [
        call
        for call in mock_emit.call_args_list
        if call.kwargs.get("event") == "backlog.converted_to_log"
    ]
    # The conversion fires on the FRESH insert only.
    assert len(conversion_calls) == 1
