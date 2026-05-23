"""Integration tests for the album-detail endpoint (T067).

Drives the ``GET /api/v1/albums/{album_id}`` route through a FastAPI
:class:`TestClient` against the mongomock-motor backing store set up in
``conftest.py``. The tests cover the visibility matrix:

* Anonymous viewer → public reviews only.
* Authenticated viewer → public + followers (via Follow edges) + own.
* Owner of a private entry → sees their own entry.
* Unknown album → ``HTTP 404``.

Auth is forged by directly attaching a :class:`Session` to
``request.state.session`` via a dependency override on a dedicated test
middleware, so the test app can run without spinning up the full HMAC
session flow.
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
from auxd_api.modules.albums.routes import router as albums_router
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review, ReviewLike
from auxd_api.modules.social.models import Follow, FollowState

MBID = "b1392450-e666-3926-a536-22c65f834433"


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """Minimal env so :class:`Settings` can construct in the test process."""
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
    """Attach a :class:`Session` to ``request.state.session`` based on an X-User-Id header.

    Avoids cookie + HMAC plumbing for the visibility-matrix tests — the
    visibility logic doesn't care HOW the session got there, only that
    it's typed correctly.
    """

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
    app.include_router(albums_router, prefix="/api/v1")
    return app


def _album_payload(album_id: str) -> Album:
    return Album(
        id=album_id,
        mbid=MBID,
        title="OK Computer",
        artist_credit="Radiohead",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


@pytest_asyncio.fixture
async def _seeded_album() -> AsyncIterator[Album]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Follow.delete_all()
    album = _album_payload(album_id="album-001")
    await album.insert()
    yield album
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Follow.delete_all()


def test_unknown_album_returns_404(_clean_env: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/albums/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "album_not_found"


@pytest.mark.asyncio
async def test_anonymous_viewer_sees_public_reviews_only(
    _clean_env: None,
    _seeded_album: Album,
) -> None:
    """Anonymous request returns only public-visibility reviews + empty friends list."""
    # Public review.
    public_diary = DiaryEntry(
        user_id="author-public",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=4.5,
        visibility=Visibility.PUBLIC,
    )
    await public_diary.insert()
    await Review(
        user_id="author-public",
        diary_entry_id=public_diary.id,
        album_id=_seeded_album.id,
        body="public review",
        visibility="public",
    ).insert()
    # Followers-visibility review — must NOT appear for anonymous.
    fol_diary = DiaryEntry(
        user_id="author-followers",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.FOLLOWERS,
    )
    await fol_diary.insert()
    await Review(
        user_id="author-followers",
        diary_entry_id=fol_diary.id,
        album_id=_seeded_album.id,
        body="followers-only review",
        visibility="followers",
    ).insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{_seeded_album.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["album"]["id"] == _seeded_album.id
    assert body["my_history"] == []
    assert body["friends"] == []
    # Only the public review appears.
    review_bodies = {r["body"] for r in body["public_reviews"]}
    assert review_bodies == {"public review"}


@pytest.mark.asyncio
async def test_authenticated_viewer_sees_followed_users_followers_content(
    _clean_env: None,
    _seeded_album: Album,
) -> None:
    """A logged-in viewer with a Follow edge sees the followee's followers-vis content."""
    # Viewer follows author-followers.
    await Follow(
        follower_id="viewer-bob",
        followee_id="author-followers",
        state=FollowState.ACCEPTED,
    ).insert()

    fol_diary = DiaryEntry(
        user_id="author-followers",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.FOLLOWERS,
    )
    await fol_diary.insert()
    await Review(
        user_id="author-followers",
        diary_entry_id=fol_diary.id,
        album_id=_seeded_album.id,
        body="followers-only review",
        visibility="followers",
    ).insert()
    # Also a stranger's followers-vis content — viewer does NOT follow,
    # so it must NOT appear.
    stranger_diary = DiaryEntry(
        user_id="stranger",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=3.0,
        visibility=Visibility.FOLLOWERS,
    )
    await stranger_diary.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{_seeded_album.id}",
        headers={"X-User-Id": "viewer-bob"},
    )
    assert response.status_code == 200
    body = response.json()
    friend_user_ids = {entry["user_id"] for entry in body["friends"]}
    assert "author-followers" in friend_user_ids
    assert "stranger" not in friend_user_ids
    review_bodies = {r["body"] for r in body["public_reviews"]}
    assert "followers-only review" in review_bodies


@pytest.mark.asyncio
async def test_owner_sees_their_own_history_including_private(
    _clean_env: None,
    _seeded_album: Album,
) -> None:
    """The viewer's own private diary entries appear in ``my_history``."""
    private = DiaryEntry(
        user_id="viewer-bob",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PRIVATE,
    )
    await private.insert()
    # Soft-deleted entries are excluded.
    deleted = DiaryEntry(
        user_id="viewer-bob",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PRIVATE,
        deleted_at=datetime.now(UTC),
    )
    await deleted.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{_seeded_album.id}",
        headers={"X-User-Id": "viewer-bob"},
    )
    assert response.status_code == 200
    body = response.json()
    history_ids = {entry["id"] for entry in body["my_history"]}
    assert private.id in history_ids
    assert deleted.id not in history_ids


@pytest.mark.asyncio
async def test_authenticated_viewer_does_not_see_followed_users_private_content(
    _clean_env: None,
    _seeded_album: Album,
) -> None:
    """Even with a Follow edge, PRIVATE content stays hidden from non-owners.

    The album-detail endpoint queries on visibility ``in ['public',
    'followers']`` so private entries are excluded at the query level —
    this test verifies they don't leak through.
    """
    await Follow(
        follower_id="viewer-bob",
        followee_id="author-private",
        state=FollowState.ACCEPTED,
    ).insert()
    private_entry = DiaryEntry(
        user_id="author-private",
        album_id=_seeded_album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PRIVATE,
    )
    await private_entry.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{_seeded_album.id}",
        headers={"X-User-Id": "viewer-bob"},
    )
    assert response.status_code == 200
    body = response.json()
    friend_user_ids = {entry["user_id"] for entry in body["friends"]}
    assert "author-private" not in friend_user_ids


@pytest.mark.asyncio
async def test_aggregate_and_editions_present_in_response(
    _clean_env: None,
    _seeded_album: Album,
) -> None:
    """Response includes ``aggregate`` rollup + ``editions`` list."""
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{_seeded_album.id}")
    assert response.status_code == 200
    body = response.json()
    assert "aggregate" in body
    assert {"avg_rating", "rating_count", "review_count", "aux_count", "like_count"}.issubset(
        body["aggregate"].keys()
    )
    # The single edition is the album itself.
    assert len(body["editions"]) == 1
    assert body["editions"][0]["id"] == _seeded_album.id
