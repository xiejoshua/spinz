"""Integration tests for the private-profile gating contract (REV-002 / US-G2).

When a user flips ``User.private_profile=True``, their PUBLIC-visibility
content (diary entries, reviews) must NOT be served to anonymous or
non-follower viewers. The owner and accepted-followers still see
everything they're entitled to.

The fix demoted PUBLIC content to FOLLOWERS scope inside
:func:`auxd_api.lib.visibility.can_read_with_relation` via a new
``owner_is_private`` flag. These tests pin the end-to-end contract on
the four affected read surfaces:

* ``GET /api/v1/users/{handle}/diary`` (diary list)
* ``GET /api/v1/users/{handle}/reviews`` (reviews list)
* ``GET /api/v1/reviews/{id}`` (single review)
* ``GET /api/v1/albums/{album_id}`` (album-detail public_reviews rollup)
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
from auxd_api.modules.albums.routes import router as albums_router
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import ReactionsSubDoc, Review, ReviewLike
from auxd_api.modules.reviews.routes import router as reviews_router
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import HandleRedirect, User
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
    app.include_router(reviews_router, prefix="/api/v1")
    app.include_router(albums_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str, *, private_profile: bool = False) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        private_profile=private_profile,
    )


def _make_album(album_id: str = "album-001") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="Test Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


async def _make_diary_entry(
    *,
    user_id: str,
    album_id: str,
    visibility: Visibility = Visibility.PUBLIC,
) -> DiaryEntry:
    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=visibility,
    )
    await entry.insert()
    return entry


async def _make_review(
    *,
    user_id: str,
    album_id: str,
    body: str = "great",
    visibility: str = "public",
) -> Review:
    now = datetime.now(UTC)
    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility(visibility),
        created_at=now,
        updated_at=now,
    )
    await entry.insert()
    review = Review(
        user_id=user_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body=body,
        visibility=visibility,
        reactions=ReactionsSubDoc(),
        created_at=now,
        updated_at=now,
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
# GET /users/{handle}/diary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diary_anonymous_blocked_by_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """Private-profile user's PUBLIC diary entries do NOT surface to anonymous viewers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    await owner.insert()
    album = _make_album()
    await album.insert()
    entry = await _make_diary_entry(
        user_id=owner.id, album_id=album.id, visibility=Visibility.PUBLIC
    )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{owner.handle}/diary")
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["entries"]}
    assert entry.id not in ids


@pytest.mark.asyncio
async def test_diary_non_follower_blocked_by_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """Private-profile user's PUBLIC entries are hidden from logged-in non-followers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    viewer = _make_user("u-viewer", "viewer")
    await owner.insert()
    await viewer.insert()
    album = _make_album()
    await album.insert()
    entry = await _make_diary_entry(
        user_id=owner.id, album_id=album.id, visibility=Visibility.PUBLIC
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/diary",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["entries"]}
    assert entry.id not in ids


@pytest.mark.asyncio
async def test_diary_follower_sees_private_profile_content(
    _clean_env: None, _clean_db: None
) -> None:
    """Accepted followers continue to see a private-profile user's PUBLIC entries."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    follower = _make_user("u-follower", "follower")
    await owner.insert()
    await follower.insert()
    await Follow(
        follower_id=follower.id,
        followee_id=owner.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    entry = await _make_diary_entry(
        user_id=owner.id, album_id=album.id, visibility=Visibility.PUBLIC
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/diary",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["entries"]}
    assert entry.id in ids


@pytest.mark.asyncio
async def test_diary_owner_sees_own_private_profile_content(
    _clean_env: None, _clean_db: None
) -> None:
    """The private-profile user themselves still sees their own entries."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    await owner.insert()
    album = _make_album()
    await album.insert()
    entry = await _make_diary_entry(
        user_id=owner.id, album_id=album.id, visibility=Visibility.PUBLIC
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/diary",
        headers={"X-User-Id": owner.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["entries"]}
    assert entry.id in ids


# ---------------------------------------------------------------------------
# GET /users/{handle}/reviews
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_reviews_anonymous_blocked_by_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """Private-profile user's PUBLIC reviews don't surface to anonymous viewers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    await owner.insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{owner.handle}/reviews")
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["reviews"]}
    assert review.id not in ids


@pytest.mark.asyncio
async def test_user_reviews_non_follower_blocked_by_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """Private-profile user's PUBLIC reviews don't surface to non-followers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    viewer = _make_user("u-viewer", "viewer")
    await owner.insert()
    await viewer.insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/reviews",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["reviews"]}
    assert review.id not in ids


@pytest.mark.asyncio
async def test_user_reviews_follower_sees_private_profile_content(
    _clean_env: None, _clean_db: None
) -> None:
    """Followers see a private-profile user's PUBLIC reviews."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    follower = _make_user("u-follower", "follower")
    await owner.insert()
    await follower.insert()
    await Follow(
        follower_id=follower.id,
        followee_id=owner.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/reviews",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["reviews"]}
    assert review.id in ids


@pytest.mark.asyncio
async def test_user_reviews_owner_sees_own_private_profile_content(
    _clean_env: None, _clean_db: None
) -> None:
    """The private-profile user sees their own reviews on their own profile."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    await owner.insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/reviews",
        headers={"X-User-Id": owner.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["reviews"]}
    assert review.id in ids


# ---------------------------------------------------------------------------
# GET /reviews/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_review_404_for_anonymous_against_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """A single review by a private-profile user returns 404 to anonymous viewers.

    We use 404 (not 403) to avoid leaking the existence of the review.
    """
    owner = _make_user("u-owner", "owner", private_profile=True)
    await owner.insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/reviews/{review.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "review_not_found"


@pytest.mark.asyncio
async def test_single_review_404_for_non_follower_against_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """A single review by a private-profile user returns 404 to non-followers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    viewer = _make_user("u-viewer", "viewer")
    await owner.insert()
    await viewer.insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "review_not_found"


@pytest.mark.asyncio
async def test_single_review_visible_to_follower_against_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """A single review by a private-profile user is visible to followers."""
    owner = _make_user("u-owner", "owner", private_profile=True)
    follower = _make_user("u-follower", "follower")
    await owner.insert()
    await follower.insert()
    await Follow(
        follower_id=follower.id,
        followee_id=owner.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=owner.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/reviews/{review.id}",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200
    assert response.json()["review"]["id"] == review.id


# ---------------------------------------------------------------------------
# GET /albums/{album_id} (public_reviews + friends rollups)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_detail_public_reviews_excludes_private_profile_authors(
    _clean_env: None, _clean_db: None
) -> None:
    """Album-detail public_reviews must not include reviews by private-profile authors.

    Catalog data (the album row itself, the aggregate, editions) is
    shared and remains visible to anonymous viewers; only the owned-
    content rollups are gated.
    """
    private_author = _make_user("u-private", "private_author", private_profile=True)
    public_author = _make_user("u-public", "public_author")
    await private_author.insert()
    await public_author.insert()
    album = _make_album()
    await album.insert()
    private_review = await _make_review(
        user_id=private_author.id, album_id=album.id, visibility="public"
    )
    public_review = await _make_review(
        user_id=public_author.id, album_id=album.id, visibility="public"
    )

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/albums/{album.id}")
    assert response.status_code == 200
    body = response.json()
    # The catalog row itself remains visible.
    assert body["album"]["id"] == album.id
    ids = {row["id"] for row in body["public_reviews"]}
    assert public_review.id in ids
    assert private_review.id not in ids


@pytest.mark.asyncio
async def test_album_detail_public_reviews_visible_to_follower_of_private_author(
    _clean_env: None, _clean_db: None
) -> None:
    """A follower of a private-profile author DOES see their public review on the album."""
    private_author = _make_user("u-private", "private_author", private_profile=True)
    follower = _make_user("u-follower", "follower")
    await private_author.insert()
    await follower.insert()
    await Follow(
        follower_id=follower.id,
        followee_id=private_author.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    review = await _make_review(user_id=private_author.id, album_id=album.id, visibility="public")

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["public_reviews"]}
    assert review.id in ids


@pytest.mark.asyncio
async def test_album_detail_friends_rollup_respects_private_profile(
    _clean_env: None, _clean_db: None
) -> None:
    """The friends rollup honours private-profile demotion the same way.

    Construction: viewer follows both author A (public profile) and
    author B (private profile). Both have PUBLIC diary entries against
    the album. Both should be visible to the viewer because they're
    followers — the demotion to FOLLOWERS doesn't hurt followers.
    """
    author_pub = _make_user("u-pub", "pub_author")
    author_priv = _make_user("u-priv", "priv_author", private_profile=True)
    viewer = _make_user("u-viewer", "viewer")
    await author_pub.insert()
    await author_priv.insert()
    await viewer.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=author_pub.id,
        state=FollowState.ACCEPTED,
    ).insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=author_priv.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    entry_pub = await _make_diary_entry(
        user_id=author_pub.id, album_id=album.id, visibility=Visibility.PUBLIC
    )
    entry_priv = await _make_diary_entry(
        user_id=author_priv.id, album_id=album.id, visibility=Visibility.PUBLIC
    )

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/albums/{album.id}",
        headers={"X-User-Id": viewer.id},
    )
    body = response.json()
    ids = {row["id"] for row in body["friends"]}
    assert entry_pub.id in ids
    assert entry_priv.id in ids
