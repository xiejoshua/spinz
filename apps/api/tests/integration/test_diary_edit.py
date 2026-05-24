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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import Review
from tests.integration._auth_helpers import FakeAuthMiddleware


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


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
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
    """REV-003: the cascade soft-deletes the review (deleted_at set).

    Hard-delete was the old behaviour; it bypassed the 30-day restore
    window and made review bodies irrecoverable. The cascade now mirrors
    the diary entry's own soft-delete so the same restore path can
    bring both back.
    """
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
    persisted_review = await Review.get(review_id)
    assert persisted_review is not None  # soft-delete: row still exists
    assert persisted_review.deleted_at is not None  # but flagged deleted


@pytest.mark.asyncio
async def test_restore_within_window_undeletes_cascaded_review(
    _clean_env: None, _clean_db: None
) -> None:
    """REV-003: restore brings back BOTH the diary entry AND its review."""
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="Recoverable opinion")
    review_id = entry.review_id
    assert review_id is not None
    client = TestClient(_make_app())

    delete_response = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert delete_response.status_code == 204

    # Both rows now soft-deleted.
    deleted_entry = await DiaryEntry.get(entry.id)
    assert deleted_entry is not None
    assert deleted_entry.deleted_at is not None
    deleted_review = await Review.get(review_id)
    assert deleted_review is not None
    assert deleted_review.deleted_at is not None

    restore_response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert restore_response.status_code == 200, restore_response.text

    restored_entry = await DiaryEntry.get(entry.id)
    assert restored_entry is not None
    assert restored_entry.deleted_at is None
    restored_review = await Review.get(review_id)
    assert restored_review is not None
    assert restored_review.deleted_at is None
    # The original review body survives the round-trip.
    assert restored_review.body == "Recoverable opinion"


@pytest.mark.asyncio
async def test_restore_after_window_keeps_review_soft_deleted(
    _clean_env: None, _clean_db: None
) -> None:
    """REV-003: restore outside the grace window fails; the review stays soft-deleted.

    The 30-day cron sweep will eventually hard-delete both rows; in the
    meantime the public read surface continues to hide them because the
    soft-delete flags are set.
    """
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="Too late to recover")
    review_id = entry.review_id
    assert review_id is not None

    # Simulate the cascade having fired 31 days ago (just outside the
    # restore window).
    old_when = datetime.now(UTC) - timedelta(days=31)
    entry.deleted_at = old_when
    await entry.save()
    review = await Review.get(review_id)
    assert review is not None
    review.deleted_at = old_when
    await review.save()

    client = TestClient(_make_app())
    restore_response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert restore_response.status_code == 410
    assert restore_response.json()["detail"] == "restore_expired"

    # Both rows remain soft-deleted (the cron sweep handles eventual hard-delete).
    stale_entry = await DiaryEntry.get(entry.id)
    assert stale_entry is not None
    assert stale_entry.deleted_at is not None
    stale_review = await Review.get(review_id)
    assert stale_review is not None
    assert stale_review.deleted_at is not None


@pytest.mark.asyncio
async def test_restore_does_not_resurrect_independently_deleted_review(
    _clean_env: None, _clean_db: None
) -> None:
    """REV-003 caveat: a review the user deleted BEFORE the diary delete stays deleted.

    The restore cascade only un-soft-deletes the review when its
    ``deleted_at`` matches the diary entry's (i.e. it was the cascade
    that flagged it). A review the user explicitly removed via
    ``DELETE /reviews/{id}`` earlier — with a different deleted_at —
    must NOT be silently brought back by a diary restore.
    """
    album = _make_album()
    await album.insert()
    entry = await _make_entry(review_body="Already removed by user")
    review_id = entry.review_id
    assert review_id is not None

    review = await Review.get(review_id)
    assert review is not None
    # User deleted the review on its own first (e.g. via the review
    # delete endpoint). Use a clearly-earlier timestamp so the diary
    # restore cascade's same-instant heuristic ignores it.
    review.deleted_at = datetime.now(UTC) - timedelta(hours=1)
    await review.save()

    client = TestClient(_make_app())
    # Now soft-delete the diary entry. The cascade in delete_entry
    # observes that the review is already soft-deleted (review.deleted_at
    # is not None) and leaves it alone.
    delete_response = client.delete(
        f"/api/v1/diary/entries/{entry.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert delete_response.status_code == 204

    # Restore the diary entry.
    restore_response = client.post(
        f"/api/v1/diary/entries/{entry.id}/restore",
        headers={"X-User-Id": "user-casey"},
    )
    assert restore_response.status_code == 200

    # The diary entry is restored…
    restored_entry = await DiaryEntry.get(entry.id)
    assert restored_entry is not None
    assert restored_entry.deleted_at is None
    # …but the review the user previously deleted stays deleted (the
    # cascade-restore heuristic only matches the same-instant case).
    surviving_review = await Review.get(review_id)
    assert surviving_review is not None
    assert surviving_review.deleted_at is not None


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
