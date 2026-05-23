"""Integration tests for ``GET /api/v1/users/{handle}/reviews`` (T094).

Mirrors :mod:`tests.integration.test_reviews_endpoint` but exercises the
author-keyed sibling of the album-keyed reviews list. Coverage:

* 404 on unknown handle.
* Newest sort + cursor pagination + albums sidecar shape.
* Visibility filter: anonymous viewer sees public only.
* Sort variants — ``most_liked`` and ``highest_rated``.
* Owner sees own private reviews on the route.
* Soft-deleted rows excluded.
* Handle redirect: old handle returns the canonical user's reviews.
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
from auxd_api.modules.reviews.models import ReactionsSubDoc, Review, ReviewLike
from auxd_api.modules.reviews.routes import router as reviews_router
from auxd_api.modules.social.models import Follow
from auxd_api.modules.users.models import HandleRedirect, User


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
    app.include_router(reviews_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
    )


async def _seed_album(album_id: str, title: str = "Album", artist: str = "Artist") -> Album:
    album = Album(
        id=album_id,
        mbid=None,
        title=title,
        artist_credit=artist,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()
    return album


async def _seed_review(
    *,
    user_id: str,
    album_id: str,
    body: str,
    rating: float = 4.0,
    visibility: str = "public",
    likes: int = 0,
    created_at: datetime | None = None,
) -> Review:
    when = created_at or datetime.now(UTC)
    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=when,
        rating=rating,
        visibility=Visibility(visibility),
        created_at=when,
        updated_at=when,
    )
    await entry.insert()
    review = Review(
        user_id=user_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body=body,
        visibility=visibility,
        reactions=ReactionsSubDoc(likes_count=likes),
        created_at=when,
        updated_at=when,
    )
    await review.insert()
    entry.review_id = review.id
    await entry.save()
    return review


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Follow.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Follow.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()


# ---------------------------------------------------------------------------
# 404 + happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_reviews_unknown_handle_returns_404(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/ghost/reviews")
    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"


@pytest.mark.asyncio
async def test_get_user_reviews_newest_with_albums_sidecar(
    _clean_env: None, _clean_db: None
) -> None:
    """Default sort is newest; the albums sidecar carries every album on the page."""
    author = _make_user("u-author", "author")
    await author.insert()
    album_a = await _seed_album("alb-a", title="Listy", artist="Tester")
    album_b = await _seed_album("alb-b", title="Bops", artist="Other")
    older = datetime.now(UTC) - timedelta(hours=2)
    newer = datetime.now(UTC) - timedelta(minutes=1)
    older_review = await _seed_review(
        user_id=author.id, album_id=album_a.id, body="older", created_at=older
    )
    newer_review = await _seed_review(
        user_id=author.id, album_id=album_b.id, body="newer", created_at=newer
    )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews")
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [r["id"] for r in body["reviews"]]
    assert ids[0] == newer_review.id
    assert ids[1] == older_review.id
    # Albums sidecar contains both rows we joined.
    assert set(body["albums"].keys()) == {album_a.id, album_b.id}
    assert body["albums"][album_a.id]["title"] == "Listy"
    assert body["albums"][album_b.id]["title"] == "Bops"
    # Users sidecar carries just the author.
    assert set(body["users"].keys()) == {author.id}
    assert body["users"][author.id]["handle"] == author.handle


@pytest.mark.asyncio
async def test_get_user_reviews_cursor_pages(_clean_env: None, _clean_db: None) -> None:
    """Limit + cursor work: page 1 caps and emits a cursor; page 2 finishes."""
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    base = datetime.now(UTC) - timedelta(hours=3)
    for i in range(3):
        await _seed_review(
            user_id=author.id,
            album_id=album.id,
            body=f"r-{i}",
            created_at=base + timedelta(seconds=i),
        )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["reviews"]) == 2
    assert body["next_cursor"] is not None

    cursor = body["next_cursor"]
    second = client.get(f"/api/v1/users/{author.handle}/reviews?limit=2&cursor={cursor}")
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["reviews"]) == 1


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_reviews_excludes_followers_for_anonymous(
    _clean_env: None, _clean_db: None
) -> None:
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    public = await _seed_review(
        user_id=author.id, album_id=album.id, body="public", visibility="public"
    )
    followers_only = await _seed_review(
        user_id=author.id, album_id=album.id, body="followers", visibility="followers"
    )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews")
    body = response.json()
    ids = {r["id"] for r in body["reviews"]}
    assert public.id in ids
    assert followers_only.id not in ids


@pytest.mark.asyncio
async def test_get_user_reviews_owner_sees_own_private(_clean_env: None, _clean_db: None) -> None:
    """The reviews list MUST include the owner's private rows when they're the viewer."""
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    private = await _seed_review(
        user_id=author.id, album_id=album.id, body="private", visibility="private"
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{author.handle}/reviews",
        headers={"X-User-Id": author.id},
    )
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["reviews"]}
    assert private.id in ids


@pytest.mark.asyncio
async def test_get_user_reviews_excludes_soft_deleted(_clean_env: None, _clean_db: None) -> None:
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    public = await _seed_review(user_id=author.id, album_id=album.id, body="public")
    gone = await _seed_review(user_id=author.id, album_id=album.id, body="gone")
    gone.deleted_at = datetime.now(UTC)
    await gone.save()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews")
    ids = {r["id"] for r in response.json()["reviews"]}
    assert public.id in ids
    assert gone.id not in ids


# ---------------------------------------------------------------------------
# Sort variants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_reviews_sort_most_liked(_clean_env: None, _clean_db: None) -> None:
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    low = await _seed_review(user_id=author.id, album_id=album.id, body="lo", likes=1)
    high = await _seed_review(user_id=author.id, album_id=album.id, body="hi", likes=42)
    mid = await _seed_review(user_id=author.id, album_id=album.id, body="md", likes=10)

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews?sort=most_liked")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    assert ids == [high.id, mid.id, low.id]


@pytest.mark.asyncio
async def test_get_user_reviews_sort_highest_rated(_clean_env: None, _clean_db: None) -> None:
    author = _make_user("u-author", "author")
    await author.insert()
    album = await _seed_album("alb-1")
    low = await _seed_review(user_id=author.id, album_id=album.id, body="lo", rating=2.0)
    high = await _seed_review(user_id=author.id, album_id=album.id, body="hi", rating=5.0)
    mid = await _seed_review(user_id=author.id, album_id=album.id, body="md", rating=3.5)

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{author.handle}/reviews?sort=highest_rated")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    assert ids == [high.id, mid.id, low.id]


# ---------------------------------------------------------------------------
# Handle redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_reviews_resolves_old_handle(_clean_env: None, _clean_db: None) -> None:
    """An old handle in the URL surfaces the canonical user's reviews."""
    author = _make_user("u-author", "alice_v2")
    await author.insert()
    await HandleRedirect(
        old_handle="alice_v1",
        new_handle="alice_v2",
        user_id=author.id,
    ).insert()
    album = await _seed_album("alb-1")
    review = await _seed_review(user_id=author.id, album_id=album.id, body="hi")

    client = TestClient(_make_app())
    response = client.get("/api/v1/users/alice_v1/reviews")
    assert response.status_code == 200, response.text
    body = response.json()
    ids = {r["id"] for r in body["reviews"]}
    assert review.id in ids
    # User sidecar carries the canonical user (alice_v2), not the redirect.
    assert author.id in body["users"]
    assert body["users"][author.id]["handle"] == "alice_v2"
