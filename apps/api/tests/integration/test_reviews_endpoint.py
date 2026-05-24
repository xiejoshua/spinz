"""Integration tests for the list-reviews-for-album endpoint (T089).

Drives ``GET /api/v1/albums/{album_id}/reviews?sort=...`` through a
FastAPI :class:`TestClient` with the mongomock backing store. Auth is
forged via a fake middleware.

Coverage (TC-017):

* ``sort=newest`` orders by created_at DESC.
* ``sort=most_liked`` orders by reactions.likes_count DESC.
* ``sort=highest_rated`` joins with DiaryEntry.rating DESC.
* Tier ordering: friends first, then public, then critic-seed.
* Visibility filter: PRIVATE author's reviews never reach a stranger.
* Soft-deleted reviews excluded.
* User sidecar populated.
* Unknown album returns 404.
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
from auxd_api.modules.reviews.models import ReactionsSubDoc, Review, ReviewLike
from auxd_api.modules.reviews.routes import router as reviews_router
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import User
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


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
    )


async def _seed_album(album_id: str = "album-001") -> Album:
    album = Album(
        id=album_id,
        mbid=None,
        title="Listy",
        artist_credit="Tester",
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
    await CriticSeed.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Follow.delete_all()
    await User.delete_all()
    await CriticSeed.delete_all()


# ---------------------------------------------------------------------------
# Basic sort behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reviews_unknown_album_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/albums/nope/reviews")
    assert response.status_code == 404
    assert response.json()["detail"] == "album_not_found"


@pytest.mark.asyncio
async def test_get_reviews_sort_newest_default(_clean_env: None, _clean_db: None) -> None:
    """``sort=newest`` (and the default) returns reviews ordered created_at DESC."""
    album = await _seed_album()
    a_user = _make_user("u-a", "alice")
    b_user = _make_user("u-b", "bob")
    await a_user.insert()
    await b_user.insert()
    older = datetime.now(UTC) - timedelta(hours=2)
    newer = datetime.now(UTC) - timedelta(minutes=1)
    older_review = await _seed_review(
        user_id="u-a", album_id=album.id, body="older", created_at=older
    )
    newer_review = await _seed_review(
        user_id="u-b", album_id=album.id, body="newer", created_at=newer
    )
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews")
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [r["id"] for r in body["reviews"]]
    assert ids[0] == newer_review.id
    assert ids[1] == older_review.id


@pytest.mark.asyncio
async def test_get_reviews_sort_most_liked(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    a_user = _make_user("u-a", "alice")
    b_user = _make_user("u-b", "bob")
    c_user = _make_user("u-c", "carol")
    await a_user.insert()
    await b_user.insert()
    await c_user.insert()
    low = await _seed_review(user_id="u-a", album_id=album.id, body="lo", likes=1)
    high = await _seed_review(user_id="u-b", album_id=album.id, body="hi", likes=42)
    mid = await _seed_review(user_id="u-c", album_id=album.id, body="md", likes=10)

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews?sort=most_liked")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    assert ids == [high.id, mid.id, low.id]


@pytest.mark.asyncio
async def test_get_reviews_sort_highest_rated(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    a_user = _make_user("u-a", "alice")
    b_user = _make_user("u-b", "bob")
    c_user = _make_user("u-c", "carol")
    await a_user.insert()
    await b_user.insert()
    await c_user.insert()
    low = await _seed_review(user_id="u-a", album_id=album.id, body="lo", rating=2.0)
    high = await _seed_review(user_id="u-b", album_id=album.id, body="hi", rating=5.0)
    mid = await _seed_review(user_id="u-c", album_id=album.id, body="md", rating=3.5)

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews?sort=highest_rated")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    assert ids == [high.id, mid.id, low.id]


# ---------------------------------------------------------------------------
# Tier ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reviews_friends_tier_appears_before_public(
    _clean_env: None, _clean_db: None
) -> None:
    """A followed user's review precedes an unrelated public author's review.

    Tier 0 (friends) → tier 1 (public). Within each tier the chosen
    sort applies — here both reviews are equally fresh so the tier
    ordering is the discriminator.
    """
    album = await _seed_album()
    viewer = _make_user("u-viewer", "viewer")
    friend = _make_user("u-friend", "friend")
    stranger = _make_user("u-stranger", "stranger")
    await viewer.insert()
    await friend.insert()
    await stranger.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    stranger_review = await _seed_review(
        user_id=stranger.id,
        album_id=album.id,
        body="public stranger review",
    )
    friend_review = await _seed_review(
        user_id=friend.id,
        album_id=album.id,
        body="friend review",
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/reviews?sort=newest",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    # Friend's review precedes the stranger's even though the upstream
    # sort would put them in arbitrary order.
    assert ids.index(friend_review.id) < ids.index(stranger_review.id)


@pytest.mark.asyncio
async def test_get_reviews_critic_seed_appears_last_among_otherwise_equal(
    _clean_env: None, _clean_db: None
) -> None:
    album = await _seed_album()
    public_author = _make_user("u-public", "publik")
    critic_author = _make_user("u-critic", "critik")
    await public_author.insert()
    await critic_author.insert()
    await CriticSeed(user_id=critic_author.id, active=True).insert()

    public_review = await _seed_review(user_id=public_author.id, album_id=album.id, body="public")
    critic_review = await _seed_review(user_id=critic_author.id, album_id=album.id, body="critic")

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews?sort=newest")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["reviews"]]
    # Public tier (1) precedes critic-seed tier (2).
    assert ids.index(public_review.id) < ids.index(critic_review.id)


# ---------------------------------------------------------------------------
# Visibility filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reviews_excludes_private_for_stranger(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    author = _make_user("u-author", "author")
    viewer = _make_user("u-viewer", "viewer")
    await author.insert()
    await viewer.insert()
    private = await _seed_review(
        user_id=author.id, album_id=album.id, body="private", visibility="private"
    )
    public = await _seed_review(
        user_id=author.id, album_id=album.id, body="public", visibility="public"
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/reviews",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["reviews"]}
    assert public.id in ids
    assert private.id not in ids


@pytest.mark.asyncio
async def test_get_reviews_excludes_followers_for_anonymous(
    _clean_env: None, _clean_db: None
) -> None:
    album = await _seed_album()
    author = _make_user("u-author", "author")
    await author.insert()
    public = await _seed_review(
        user_id=author.id, album_id=album.id, body="public", visibility="public"
    )
    followers_only = await _seed_review(
        user_id=author.id, album_id=album.id, body="followers", visibility="followers"
    )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews")
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["reviews"]}
    assert public.id in ids
    assert followers_only.id not in ids


@pytest.mark.asyncio
async def test_get_reviews_excludes_soft_deleted(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    author = _make_user("u-author", "author")
    await author.insert()
    public = await _seed_review(user_id=author.id, album_id=album.id, body="public")
    gone = await _seed_review(user_id=author.id, album_id=album.id, body="gone")
    gone.deleted_at = datetime.now(UTC)
    await gone.save()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews")
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["reviews"]}
    assert public.id in ids
    assert gone.id not in ids


# ---------------------------------------------------------------------------
# Users sidecar + paging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reviews_includes_user_sidecar(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    a_user = _make_user("u-a", "alice")
    b_user = _make_user("u-b", "bob")
    await a_user.insert()
    await b_user.insert()
    await _seed_review(user_id="u-a", album_id=album.id, body="a")
    await _seed_review(user_id="u-b", album_id=album.id, body="b")

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews")
    body = response.json()
    assert set(body["users"].keys()) == {"u-a", "u-b"}
    assert body["users"]["u-a"]["handle"] == "alice"
    assert body["users"]["u-b"]["display_name"] == "Bob"


@pytest.mark.asyncio
async def test_get_reviews_limit_capped(_clean_env: None, _clean_db: None) -> None:
    album = await _seed_album()
    author = _make_user("u-a", "alice")
    await author.insert()
    for i in range(3):
        await _seed_review(
            user_id="u-a",
            album_id=album.id,
            body=f"r-{i}",
            created_at=datetime.now(UTC) - timedelta(seconds=i),
        )
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["reviews"]) == 2
    # All three rows exist, so a next_cursor is emitted.
    assert body["next_cursor"] is not None


@pytest.mark.asyncio
async def test_get_reviews_invalid_sort_returns_422(_clean_env: None, _clean_db: None) -> None:
    """Unknown sort values are rejected by the Query pattern with 422."""
    album = await _seed_album()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/reviews?sort=worst_first")
    assert response.status_code == 422
