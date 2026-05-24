"""Integration tests for the review-like endpoint (T088).

Drives ``POST /api/v1/reviews/{id}/like`` and the corresponding
``DELETE`` through a FastAPI :class:`TestClient`.

Coverage:

* TC-015 happy path: like increments counter, returns ``liked=True``,
  populates ``recent_likers``.
* TC-016: self-like rejected with 400.
* Double-like idempotent (no double-increment).
* Un-like decrements + clears ``recent_likers``.
* Un-like on a never-liked review returns current state.
* Like on deleted review returns 404.
* Unauthenticated request returns 401.
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
from auxd_api.modules.reviews.models import Review, ReviewLike
from auxd_api.modules.reviews.routes import router as reviews_router
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


async def _seed_review(*, owner_id: str = "user-author") -> Review:
    album_id = f"album-{owner_id}"
    await Album(
        id=album_id,
        mbid=None,
        title="Liked Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    ).insert()
    entry = DiaryEntry(
        user_id=owner_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await entry.insert()
    review = Review(
        user_id=owner_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body="Worth a like.",
        visibility="public",
    )
    await review.insert()
    return review


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()


@pytest.mark.asyncio
async def test_like_review_happy_path(_clean_env: None, _clean_db: None) -> None:
    """TC-015: like increments counter; recent_likers updated."""
    review = await _seed_review()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["liked"] is True
    assert body["likes_count"] == 1

    persisted = await Review.get(review.id)
    assert persisted is not None
    assert persisted.reactions.likes_count == 1
    assert "user-fan" in persisted.reactions.recent_likers


@pytest.mark.asyncio
async def test_like_review_self_like_returns_400(_clean_env: None, _clean_db: None) -> None:
    """TC-016: author cannot like their own review."""
    review = await _seed_review(owner_id="user-author")
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-author"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "self_like_forbidden"


@pytest.mark.asyncio
async def test_like_review_idempotent_no_double_increment(
    _clean_env: None, _clean_db: None
) -> None:
    review = await _seed_review()
    client = TestClient(_make_app())
    first = client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    second = client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    assert first.json()["likes_count"] == 1
    assert second.json()["likes_count"] == 1
    rows = await ReviewLike.find({"review_id": review.id}).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_unlike_review_decrements(_clean_env: None, _clean_db: None) -> None:
    review = await _seed_review()
    client = TestClient(_make_app())
    client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    response = client.delete(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["liked"] is False
    assert body["likes_count"] == 0


@pytest.mark.asyncio
async def test_unlike_review_never_liked_returns_current_state(
    _clean_env: None, _clean_db: None
) -> None:
    """Un-liking a never-liked review is a benign idempotent no-op."""
    review = await _seed_review()
    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fresh"},
    )
    assert response.status_code == 200
    assert response.json() == {"liked": False, "likes_count": 0}


@pytest.mark.asyncio
async def test_like_review_on_deleted_returns_404(_clean_env: None, _clean_db: None) -> None:
    review = await _seed_review()
    review.deleted_at = datetime.now(UTC)
    await review.save()
    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/reviews/{review.id}/like",
        headers={"X-User-Id": "user-fan"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_like_review_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    review = await _seed_review()
    client = TestClient(_make_app())
    response = client.post(f"/api/v1/reviews/{review.id}/like")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_like_review_then_relike_after_unlike(_clean_env: None, _clean_db: None) -> None:
    """Like → un-like → re-like restores the like with counter=1."""
    review = await _seed_review()
    client = TestClient(_make_app())
    client.post(f"/api/v1/reviews/{review.id}/like", headers={"X-User-Id": "user-fan"})
    client.delete(f"/api/v1/reviews/{review.id}/like", headers={"X-User-Id": "user-fan"})
    final = client.post(f"/api/v1/reviews/{review.id}/like", headers={"X-User-Id": "user-fan"})
    assert final.status_code == 200
    assert final.json() == {"liked": True, "likes_count": 1}
