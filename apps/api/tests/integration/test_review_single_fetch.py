"""Integration tests for the single-review fetch endpoint (T093a backing).

``GET /api/v1/reviews/{id}`` powers the ``/review/[id]`` SSR reading view.
Visibility is enforced via the same matrix as the list endpoint; non-readers
get a ``404`` (not ``403``) so we don't leak existence of private rows.
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
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.reviews.routes import router as reviews_router
from auxd_api.modules.social.models import Follow
from auxd_api.modules.users.models import User


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT", "DISCOGS_API_TOKEN"):
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
    app.include_router(reviews_router, prefix="/api/v1")
    return app


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await User.delete_all()


async def _seed(user_id: str = "user-casey", visibility: Visibility = Visibility.PUBLIC) -> Review:
    await User(
        id=user_id,
        handle=user_id.replace("user-", ""),
        email=f"{user_id}@ex.com",
        password_hash="$argon2id$test-hash",
        display_name=user_id.replace("user-", "").capitalize(),
    ).insert()
    await Album(
        id="album-001",
        mbid=None,
        title="Test Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    ).insert()
    entry = DiaryEntry(
        user_id=user_id,
        album_id="album-001",
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=visibility,
    )
    await entry.insert()
    review = Review(
        user_id=user_id,
        diary_entry_id=entry.id,
        album_id="album-001",
        body="Good record.",
        visibility=visibility.value,
    )
    await review.insert()
    return review


@pytest.mark.asyncio
async def test_get_public_review_returns_payload(_clean_env: None, _clean_db: None) -> None:
    review = await _seed()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/reviews/{review.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["review"]["id"] == review.id
    assert body["user"]["handle"] == "casey"
    assert body["album"]["title"] == "Test Album"
    # Anonymous viewer has no diary entry sidecar.
    assert body["viewer_entry"] is None


@pytest.mark.asyncio
async def test_get_unknown_review_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/reviews/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_soft_deleted_review_returns_404(_clean_env: None, _clean_db: None) -> None:
    review = await _seed()
    review.deleted_at = datetime.now(UTC)
    await review.save()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/reviews/{review.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_private_review_returns_404_to_non_owner(
    _clean_env: None, _clean_db: None
) -> None:
    review = await _seed(visibility=Visibility.PRIVATE)
    client = TestClient(_make_app())
    # Different user.
    response = client.get(f"/api/v1/reviews/{review.id}", headers={"X-User-Id": "user-bob"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_private_review_returns_payload_to_owner(
    _clean_env: None, _clean_db: None
) -> None:
    review = await _seed(visibility=Visibility.PRIVATE)
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/reviews/{review.id}", headers={"X-User-Id": "user-casey"})
    assert response.status_code == 200
    assert response.json()["review"]["id"] == review.id


@pytest.mark.asyncio
async def test_get_includes_viewer_entry_when_viewer_has_logged_album(
    _clean_env: None, _clean_db: None
) -> None:
    review = await _seed()
    await User(
        id="user-bob",
        handle="bob",
        email="bob@ex.com",
        password_hash="$argon2id$test-hash",
        display_name="Bob",
    ).insert()
    await DiaryEntry(
        user_id="user-bob",
        album_id="album-001",
        logged_at=datetime.now(UTC),
        rating=3.5,
        auxed=True,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/reviews/{review.id}", headers={"X-User-Id": "user-bob"})
    assert response.status_code == 200
    body = response.json()
    assert body["viewer_entry"] is not None
    assert body["viewer_entry"]["rating"] == 3.5
    assert body["viewer_entry"]["auxed"] is True
