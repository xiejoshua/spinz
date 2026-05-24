"""Integration tests for the friends-who-rated-and-auxed endpoint (T103).

Exercises ``GET /api/v1/albums/{album_id}/friends`` through a FastAPI
:class:`TestClient`. Auth is forged via the fake middleware pattern used
by the diary + follow + block integration tests.

Covers:

* Happy path with three followed users who rated the album.
* Visibility filter — private DiaryEntry hidden from non-follower
  viewer (the followee set is correct but visibility still applies for
  private/followers content).
* Blocked users excluded — even if the viewer follows them.
* Sort order — entries returned ``rating DESC, logged_at DESC``.
* Unknown album returns 404.
* Empty result when the viewer follows no one or no friend has rated.
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
from auxd_api.modules.feed.routes import router as feed_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.social.models import (
    Block,
    BlockReason,
    Follow,
    FollowState,
)
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
    app.include_router(feed_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        avatar_url=f"https://cdn.example.com/{handle}.png",
    )


def _make_album(album_id: str = "album-friends") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="A Lonely Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friends_endpoint_returns_three_followed_users(
    _clean_env: None, _clean_db: None
) -> None:
    """Three followed users rated the album → all three appear in the response."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    carol = _make_user("user-carol", "carol")
    await viewer.insert()
    await alice.insert()
    await bob.insert()
    await carol.insert()

    album = _make_album()
    await album.insert()

    for friend in (alice, bob, carol):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()

    now = datetime.now(UTC)
    await DiaryEntry(
        user_id=alice.id,
        album_id=album.id,
        logged_at=now - timedelta(days=1),
        rating=5.0,
        auxed=True,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=bob.id,
        album_id=album.id,
        logged_at=now - timedelta(hours=1),
        rating=4.0,
        auxed=False,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=carol.id,
        album_id=album.id,
        logged_at=now,
        rating=3.5,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["next_cursor"] is None
    handles = [entry["handle"] for entry in body["entries"]]
    assert set(handles) == {"alice", "bob", "carol"}
    # Each entry carries denormalised profile fields.
    for entry in body["entries"]:
        assert entry["user_id"]
        assert entry["display_name"]
        assert entry["avatar_url"]
        assert "rating" in entry
        assert "auxed" in entry
        assert "logged_at" in entry


@pytest.mark.asyncio
async def test_friends_endpoint_sort_rating_desc_logged_at_desc(
    _clean_env: None, _clean_db: None
) -> None:
    """rating DESC, logged_at DESC."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await alice.insert()
    await bob.insert()
    album = _make_album()
    await album.insert()

    for friend in (alice, bob):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()

    now = datetime.now(UTC)
    # alice rates 5.0 a long time ago, bob rates 4.0 just now. alice
    # should come first because rating is the primary key.
    await DiaryEntry(
        user_id=alice.id,
        album_id=album.id,
        logged_at=now - timedelta(days=30),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=bob.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    body = response.json()
    handles = [entry["handle"] for entry in body["entries"]]
    assert handles == ["alice", "bob"]


@pytest.mark.asyncio
async def test_friends_endpoint_excludes_private_entries_from_non_owner(
    _clean_env: None, _clean_db: None
) -> None:
    """Private diary entries don't surface even from a followed user."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await alice.insert()
    await bob.insert()
    album = _make_album()
    await album.insert()

    for friend in (alice, bob):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()

    now = datetime.now(UTC)
    # alice has a private entry — not surfaced.
    await DiaryEntry(
        user_id=alice.id,
        album_id=album.id,
        logged_at=now,
        rating=5.0,
        visibility=Visibility.PRIVATE,
    ).insert()
    # bob has a public entry — surfaced.
    await DiaryEntry(
        user_id=bob.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    handles = [entry["handle"] for entry in response.json()["entries"]]
    assert handles == ["bob"]


@pytest.mark.asyncio
async def test_friends_endpoint_excludes_blocked_users(_clean_env: None, _clean_db: None) -> None:
    """Blocked users do not surface — even if a Follow row still exists.

    This shouldn't happen in practice (block cascades the follow) but
    the visibility matrix is the last line of defense.
    """
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await alice.insert()
    await bob.insert()
    album = _make_album()
    await album.insert()

    # Viewer follows both but has blocked alice.
    for friend in (alice, bob):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()
    await Block(
        blocker_id=viewer.id,
        blockee_id=alice.id,
        reason=BlockReason.HARASSMENT,
    ).insert()

    now = datetime.now(UTC)
    await DiaryEntry(
        user_id=alice.id,
        album_id=album.id,
        logged_at=now,
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=bob.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    handles = [entry["handle"] for entry in response.json()["entries"]]
    assert handles == ["bob"]


@pytest.mark.asyncio
async def test_friends_endpoint_unknown_album_returns_404(
    _clean_env: None, _clean_db: None
) -> None:
    viewer = _make_user("user-viewer", "viewer")
    await viewer.insert()
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/albums/album-does-not-exist/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "album_not_found"


@pytest.mark.asyncio
async def test_friends_endpoint_empty_when_no_follows(_clean_env: None, _clean_db: None) -> None:
    """The viewer follows no one → empty entries list (not an error)."""
    viewer = _make_user("user-viewer", "viewer")
    await viewer.insert()
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}/friends",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    assert response.json() == {"entries": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_friends_endpoint_unauthenticated_returns_401(
    _clean_env: None, _clean_db: None
) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}/friends")
    assert response.status_code == 401
