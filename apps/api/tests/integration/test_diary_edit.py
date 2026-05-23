"""Integration tests for the diary edit / delete / restore endpoints (T075).

Covers the owner-only mutation surface added on top of the log endpoint:

* PATCH /api/v1/diary/entries/{id}
  - happy-path edit by owner
  - 403 for non-owner
  - 404 for deleted entry
  - review create / update / delete sub-paths via the ``review_body``
    sentinel ("" deletes, non-empty creates-or-updates)

* DELETE /api/v1/diary/entries/{id}
  - happy-path soft-delete (204)
  - double-delete returns 410
  - cascade: attached review is gone after delete

* POST /api/v1/diary/entries/{id}/restore
  - happy-path restore within 30d
  - rejected after 30d (mock the clock by writing ``deleted_at`` directly)
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import Review


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


def _make_album(album_id: str = "album-edit-001") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="Editable",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


async def _make_entry(
    *,
    user_id: str = "user-casey",
    album_id: str = "album-edit-001",
    rating: float | None = 4.0,
    visibility: Visibility = Visibility.PUBLIC,
    review_body: str | None = None,
) -> DiaryEntry:
    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=rating,
        visibility=visibility,
    )
    await entry.insert()
    if review_body is not None:
        review = Review(
            user_id=user_id,
            diary_entry_id=entry.id,
            album_id=album_id,
            body=review_body,
            visibility=visibility.value,
        )
        await review.insert()
        entry.review_id = review.id
        await entry.save()
    return entry


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()


# ---------------------------------------------------------------------------
# PATCH /diary/entries/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_happy_path_owner_can_edit(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(rating=3.0)
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
        json={"rating": 5.0, "auxed": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rating"] == 5.0
    assert body["auxed"] is True
    assert body["edited_at"] is not None
    # Persisted.
    persisted = await DiaryEntry.get(entry.id)
    assert persisted is not None
    assert persisted.rating == 5.0


@pytest.mark.asyncio
async def test_patch_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(user_id="user-casey")
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-mallory"},
        json={"rating": 1.0},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


@pytest.mark.asyncio
async def test_patch_unknown_entry_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.patch(
        "/api/v1/diary/entries/does-not-exist",
        headers={"X-User-Id": "user-casey"},
        json={"rating": 4.0},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "entry_not_found"


@pytest.mark.asyncio
async def test_patch_deleted_entry_returns_404(_clean_env: None, _clean_db: None) -> None:
    """Deleted entries cannot be edited — restore first."""
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    entry.deleted_at = datetime.now(UTC)
    await entry.save()
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
        json={"rating": 4.0},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "entry_not_found"


@pytest.mark.asyncio
async def test_patch_creates_review_when_provided(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    assert entry.review_id is None
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
        json={"review_body": "Brand new take."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] is not None
    review = await Review.get(body["review_id"])
    assert review is not None
    assert review.body == "Brand new take."


@pytest.mark.asyncio
async def test_patch_updates_existing_review(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="Old body")
    review_id = entry.review_id
    assert review_id is not None
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
        json={"review_body": "Revised take."},
    )
    assert response.status_code == 200
    # Same review id — updated in place.
    assert response.json()["review_id"] == review_id
    review = await Review.get(review_id)
    assert review is not None
    assert review.body == "Revised take."
    assert review.edited_at is not None


@pytest.mark.asyncio
async def test_patch_empty_review_body_deletes_review(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="To be removed")
    review_id = entry.review_id
    assert review_id is not None
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
        json={"review_body": ""},
    )
    assert response.status_code == 200
    assert response.json()["review_id"] is None
    # Review is gone.
    assert await Review.get(review_id) is None


# ---------------------------------------------------------------------------
# DELETE /diary/entries/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_happy_path_owner_soft_deletes(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 204
    persisted = await DiaryEntry.get(entry.id)
    assert persisted is not None
    assert persisted.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(user_id="user-casey")
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-mallory"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_double_delete_returns_410(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    client = TestClient(_make_app())
    first = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert first.status_code == 204
    second = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert second.status_code == 410
    assert second.json()["detail"] == "already_deleted"


@pytest.mark.asyncio
async def test_delete_cascades_to_attached_review(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="Cascades to /dev/null")
    review_id = entry.review_id
    assert review_id is not None
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 204
    assert await Review.get(review_id) is None


# ---------------------------------------------------------------------------
# POST /diary/entries/{id}/restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_happy_path_within_grace_window(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    # Soft-delete one hour ago — comfortably inside the 30d grace window.
    entry.deleted_at = datetime.now(UTC) - timedelta(hours=1)
    await entry.save()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted_at"] is None
    persisted = await DiaryEntry.get(entry.id)
    assert persisted is not None
    assert persisted.deleted_at is None


@pytest.mark.asyncio
async def test_restore_after_grace_window_returns_410(_clean_env: None, _clean_db: None) -> None:
    """Restore is rejected when more than 30 days have passed.

    We mock the clock by writing ``deleted_at`` to 31 days ago — the
    cleanup cron hasn't yet hard-deleted, so the row still exists, but
    the restore window has closed.
    """
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    entry.deleted_at = datetime.now(UTC) - timedelta(days=31)
    await entry.save()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == "restore_expired"


@pytest.mark.asyncio
async def test_restore_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    entry = await _make_entry(user_id="user-casey")
    entry.deleted_at = datetime.now(UTC) - timedelta(hours=1)
    await entry.save()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-mallory"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_restore_not_deleted_entry_returns_404(_clean_env: None, _clean_db: None) -> None:
    """Calling restore on an active entry is a no-op error."""
    album = _make_album()
    await album.insert()
    entry = await _make_entry()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 404
