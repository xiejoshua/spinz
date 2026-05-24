"""Integration tests for review edit + delete endpoints (T086, T087).

* PATCH /api/v1/reviews/{id}
  - TC-025: owner-edits a review; audit row written; body + ``edited_at`` updated.
  - Two consecutive edits → two :class:`ReviewEditHistory` rows.
  - Non-owner 403.
  - Empty body 422.
  - Markdown sanitizer applied on edit (XSS gate).
  - Visibility patch path.

* DELETE /api/v1/reviews/{id}
  - Owner soft-deletes — ``deleted_at`` populated.
  - Diary entry's ``review_id`` cleared.
  - Non-owner 403.
  - Double-delete returns 410.
  - Likes_count still visible on the now-deleted row (cascade is deferred).
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
from auxd_api.modules.reviews.models import ReactionsSubDoc, Review, ReviewEditHistory, ReviewLike
from auxd_api.modules.reviews.routes import router as reviews_router
from auxd_api.modules.reviews.service import hash_body
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
    app.include_router(reviews_router, prefix="/api/v1")
    return app


async def _seed_review(
    *,
    owner_id: str = "user-casey",
    body: str = "Original body.",
    visibility: Visibility = Visibility.PUBLIC,
) -> tuple[DiaryEntry, Review]:
    """Seed an album, diary entry, and review owned by ``owner_id``."""
    album_id = f"album-{owner_id}"
    await Album(
        id=album_id,
        mbid=None,
        title="Test Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    ).insert()
    entry = DiaryEntry(
        user_id=owner_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=visibility,
    )
    await entry.insert()
    review = Review(
        user_id=owner_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body=body,
        visibility=visibility.value,
    )
    await review.insert()
    entry.review_id = review.id
    await entry.save()
    return entry, review


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await ReviewEditHistory.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await ReviewEditHistory.delete_all()


# ---------------------------------------------------------------------------
# PATCH — T086
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_review_writes_audit_row_and_updates_body(
    _clean_env: None, _clean_db: None
) -> None:
    """TC-025: edit writes ReviewEditHistory row; body updated; edited_at set."""
    _entry, review = await _seed_review(body="Old take.")
    pre_edit_body = review.body
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "New take."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "New take."
    assert body["edited_at"] is not None

    audit_rows = await ReviewEditHistory.find({"review_id": review.id}).to_list()
    assert len(audit_rows) == 1
    audit = audit_rows[0]
    assert audit.body_at_time == pre_edit_body
    # Hash check — the snapshot round-trips deterministically.
    assert hash_body(audit.body_at_time) == hash_body(pre_edit_body)
    assert audit.edited_by == "user-casey"
    assert audit.version == 1


@pytest.mark.asyncio
async def test_edit_review_two_consecutive_edits_write_two_rows(
    _clean_env: None, _clean_db: None
) -> None:
    _entry, review = await _seed_review(body="Version 1.")
    client = TestClient(_make_app())
    client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "Version 2."},
    )
    client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "Version 3."},
    )
    rows = await ReviewEditHistory.find({"review_id": review.id}).sort("+version").to_list()
    assert [row.version for row in rows] == [1, 2]
    assert rows[0].body_at_time == "Version 1."
    assert rows[1].body_at_time == "Version 2."


@pytest.mark.asyncio
async def test_edit_review_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    _entry, review = await _seed_review(owner_id="user-casey")
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-mallory"},
        json={"body": "Squatting."},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


@pytest.mark.asyncio
async def test_edit_review_empty_body_rejected(_clean_env: None, _clean_db: None) -> None:
    _entry, review = await _seed_review()
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "   "},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "review_body_empty"


@pytest.mark.asyncio
async def test_edit_review_sanitizes_xss(_clean_env: None, _clean_db: None) -> None:
    """Sanitizer is applied on edit too — same gate as create."""
    _entry, review = await _seed_review()
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "ok <script>alert(1)</script> good"},
    )
    assert response.status_code == 200
    assert "<script>" not in response.json()["body"]


@pytest.mark.asyncio
async def test_edit_review_visibility_only(_clean_env: None, _clean_db: None) -> None:
    """Patch with only ``visibility`` does not write an audit row."""
    _entry, review = await _seed_review(visibility=Visibility.PUBLIC)
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"visibility": "private"},
    )
    assert response.status_code == 200
    assert response.json()["visibility"] == "private"
    audit_rows = await ReviewEditHistory.find({"review_id": review.id}).to_list()
    assert audit_rows == []


@pytest.mark.asyncio
async def test_edit_review_same_body_no_audit_row(_clean_env: None, _clean_db: None) -> None:
    """Patching with the same body as already-stored writes no audit row."""
    _entry, review = await _seed_review(body="Same.")
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "Same."},
    )
    assert response.status_code == 200
    audit_rows = await ReviewEditHistory.find({"review_id": review.id}).to_list()
    assert audit_rows == []


@pytest.mark.asyncio
async def test_edit_review_not_found_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.patch(
        "/api/v1/reviews/does-not-exist",
        headers={"X-User-Id": "user-casey"},
        json={"body": "Phantom edit."},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "review_not_found"


@pytest.mark.asyncio
async def test_edit_review_deleted_returns_404(_clean_env: None, _clean_db: None) -> None:
    """Editing a soft-deleted review is a 404, not a 410."""
    _entry, review = await _seed_review()
    review.deleted_at = datetime.now(UTC)
    await review.save()
    client = TestClient(_make_app())
    response = client.patch(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
        json={"body": "Resurrected take."},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE — T087
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_review_sets_deleted_at_and_clears_diary_ref(
    _clean_env: None, _clean_db: None
) -> None:
    entry, review = await _seed_review()
    assert entry.review_id == review.id
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 204

    persisted = await Review.get(review.id)
    assert persisted is not None
    assert persisted.deleted_at is not None

    refreshed = await DiaryEntry.get(entry.id)
    assert refreshed is not None
    assert refreshed.review_id is None


@pytest.mark.asyncio
async def test_delete_review_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    _entry, review = await _seed_review(owner_id="user-casey")
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-mallory"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_review_double_delete_returns_410(_clean_env: None, _clean_db: None) -> None:
    _entry, review = await _seed_review()
    client = TestClient(_make_app())
    first = client.delete(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert first.status_code == 204
    second = client.delete(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert second.status_code == 410
    assert second.json()["detail"] == "already_deleted"


@pytest.mark.asyncio
async def test_delete_review_likes_remain_orphaned(_clean_env: None, _clean_db: None) -> None:
    """Cascade-delete of ReviewLikes is deferred — soft-delete leaves them in place.

    The like rows are filtered out of the read endpoint via the
    ``deleted_at IS None`` predicate on Review, so they're invisible
    to the user, but the row itself persists until the eventual
    hard-delete cron runs.
    """
    _entry, review = await _seed_review()
    # Manually bump the counter so we can assert it survives the delete.
    review.reactions = ReactionsSubDoc(likes_count=3, recent_likers=["u1", "u2", "u3"])
    await review.save()
    await ReviewLike(review_id=review.id, user_id="u1").insert()
    await ReviewLike(review_id=review.id, user_id="u2").insert()
    await ReviewLike(review_id=review.id, user_id="u3").insert()

    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 204

    persisted = await Review.get(review.id)
    assert persisted is not None
    # Counters preserved on the soft-deleted row.
    assert persisted.reactions.likes_count == 3
    # Like rows still there — cron will sweep them later.
    likes = await ReviewLike.find({"review_id": review.id}).to_list()
    assert len(likes) == 3


@pytest.mark.asyncio
async def test_delete_review_not_found_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.delete(
        "/api/v1/reviews/does-not-exist",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "review_not_found"
