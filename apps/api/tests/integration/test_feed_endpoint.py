"""Integration tests for the home feed endpoint (T106).

Exercises ``GET /api/v1/feed`` through a FastAPI :class:`TestClient`
with the standard fake-auth middleware pattern.

Covers:

* Happy path with followees.
* For-you scoring: a review-attached entry scores higher than a plain log.
* Latest mode disables weighting entirely.
* Critic-seed padding when the follow graph is sparse.
* Visibility matrix — private DiaryEntry hidden from non-follower.
* Block edge — blocked users excluded from the feed.
* Cursor pagination — two-page walk returns disjoint pages.
* Bad cursor falls back to "no cursor" (matches diary).
* Limit capping (200 → MAX_HOME_FEED_LIMIT).
* Unauthenticated request returns 401.
* Empty fan-out returns an empty entry list (not an error).
* Sidecars (users / albums / reviews) populated correctly.
"""

from __future__ import annotations

import base64
import json
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
from auxd_api.modules.seeding.models import CriticSeed
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


def _make_album(album_id: str = "album-feed") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title=f"Album {album_id}",
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
    await CriticSeed.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    await CriticSeed.delete_all()


async def _setup_minimal_feed(viewer_id: str, count: int) -> list[DiaryEntry]:
    """Insert ``count`` followees + a diary entry each, with the viewer
    following all of them. Returns the inserted DiaryEntries.
    """
    viewer = _make_user(viewer_id, "viewer")
    await viewer.insert()
    entries: list[DiaryEntry] = []
    now = datetime.now(UTC)
    album = _make_album("album-shared")
    await album.insert()
    for i in range(count):
        followee = _make_user(f"user-friend-{i:02d}", f"friend{i:02d}")
        await followee.insert()
        await Follow(
            follower_id=viewer.id,
            followee_id=followee.id,
            state=FollowState.ACCEPTED,
        ).insert()
        entry = DiaryEntry(
            user_id=followee.id,
            album_id=album.id,
            logged_at=now - timedelta(minutes=i),
            rating=3.5,
            visibility=Visibility.PUBLIC,
        )
        await entry.insert()
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feed_returns_entries_from_followed_users(_clean_env: None, _clean_db: None) -> None:
    """Two followees with public diary entries → both rows appear with sidecars."""
    await _setup_minimal_feed("user-viewer", count=2)
    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": "user-viewer"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["entries"]) == 2
    # Sidecars populated.
    assert len(body["users"]) == 2
    assert len(body["albums"]) == 1
    # All entries are diary_entry kind.
    for entry in body["entries"]:
        assert entry["kind"] == "diary_entry"
    # mode defaults to for_you and score fields present.
    assert body["mode"] == "for_you"
    assert all("score" in entry for entry in body["entries"])


@pytest.mark.asyncio
async def test_feed_empty_when_no_followees(_clean_env: None, _clean_db: None) -> None:
    """Viewer follows nobody and no critic seeds → empty entries list."""
    viewer = _make_user("user-viewer", "viewer")
    await viewer.insert()
    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": "user-viewer"})
    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["next_cursor"] is None


# ---------------------------------------------------------------------------
# For-you scoring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_for_you_review_attached_scores_higher_than_plain_log(
    _clean_env: None, _clean_db: None
) -> None:
    """A diary entry with an attached review scores higher than one without
    when both are otherwise identical.
    """
    viewer = _make_user("user-viewer", "viewer")
    a = _make_user("user-friend-a", "frienda")
    b = _make_user("user-friend-b", "friendb")
    for user in (viewer, a, b):
        await user.insert()
    for friend in (a, b):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)

    plain_entry = DiaryEntry(
        user_id=a.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await plain_entry.insert()

    reviewed_entry = DiaryEntry(
        user_id=b.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await reviewed_entry.insert()
    review = Review(
        user_id=b.id,
        diary_entry_id=reviewed_entry.id,
        album_id=album.id,
        body="A great record from start to finish.",
    )
    await review.insert()
    reviewed_entry.review_id = review.id
    await reviewed_entry.save()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/feed?mode=for_you",
        headers={"X-User-Id": viewer.id},
    )
    body = response.json()
    # The reviewed entry should be first because its score multiplier
    # (1.20 from review_attached) wins the tie against the plain log.
    ids = [entry["id"] for entry in body["entries"]]
    assert ids[0] == reviewed_entry.id
    # The review sidecar is populated.
    assert review.id in body["reviews"]


@pytest.mark.asyncio
async def test_for_you_extreme_rating_scores_higher(_clean_env: None, _clean_db: None) -> None:
    """A 5.0 rating boosts an entry over a 4.0 rating with the same recency."""
    viewer = _make_user("user-viewer", "viewer")
    a = _make_user("user-friend-a", "frienda")
    b = _make_user("user-friend-b", "friendb")
    for user in (viewer, a, b):
        await user.insert()
    for friend in (a, b):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)

    plain = DiaryEntry(
        user_id=a.id,
        album_id=album.id,
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    extreme = DiaryEntry(
        user_id=b.id,
        album_id=album.id,
        logged_at=now,
        rating=5.0,
        visibility=Visibility.PUBLIC,
    )
    await plain.insert()
    await extreme.insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed?mode=for_you", headers={"X-User-Id": viewer.id})
    ids = [entry["id"] for entry in response.json()["entries"]]
    assert ids[0] == extreme.id


@pytest.mark.asyncio
async def test_latest_mode_strips_score_and_orders_by_logged_at(
    _clean_env: None, _clean_db: None
) -> None:
    """Latest mode disables weighting and sorts logged_at DESC."""
    viewer = _make_user("user-viewer", "viewer")
    a = _make_user("user-friend-a", "frienda")
    b = _make_user("user-friend-b", "friendb")
    for user in (viewer, a, b):
        await user.insert()
    for friend in (a, b):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)
    older_with_review = DiaryEntry(
        user_id=a.id,
        album_id=album.id,
        logged_at=now - timedelta(hours=2),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    )
    await older_with_review.insert()
    review = Review(
        user_id=a.id,
        diary_entry_id=older_with_review.id,
        album_id=album.id,
        body="x",
    )
    await review.insert()
    older_with_review.review_id = review.id
    await older_with_review.save()

    newer_plain = DiaryEntry(
        user_id=b.id,
        album_id=album.id,
        logged_at=now,
        rating=2.0,
        visibility=Visibility.PUBLIC,
    )
    await newer_plain.insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed?mode=latest", headers={"X-User-Id": viewer.id})
    body = response.json()
    # Latest mode → newer plain comes first (older entry is the
    # for-you winner via review boost, but latest mode ignores it).
    ids = [entry["id"] for entry in body["entries"]]
    assert ids[0] == newer_plain.id
    # No score / score_components on the wire.
    assert "score" not in body["entries"][0]
    assert "score_components" not in body["entries"][0]
    assert body["mode"] == "latest"


# ---------------------------------------------------------------------------
# Critic-seed padding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critic_seed_padding_when_follow_graph_sparse(
    _clean_env: None, _clean_db: None
) -> None:
    """Viewer with no followees but two critic-seed authors active → padded."""
    viewer = _make_user("user-viewer", "viewer")
    seed_a = _make_user("user-seed-a", "critica")
    seed_b = _make_user("user-seed-b", "criticb")
    for user in (viewer, seed_a, seed_b):
        await user.insert()
    for seed in (seed_a, seed_b):
        await CriticSeed(user_id=seed.id, priority=80, active=True).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)
    for seed in (seed_a, seed_b):
        await DiaryEntry(
            user_id=seed.id,
            album_id=album.id,
            logged_at=now,
            rating=5.0,
            visibility=Visibility.PUBLIC,
        ).insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": viewer.id})
    body = response.json()
    assert len(body["entries"]) == 2
    # Each padded entry is tagged in score_components.
    for entry in body["entries"]:
        assert entry["score_components"]["source"] == "critic_seed_padding"


@pytest.mark.asyncio
async def test_critic_seed_padding_skips_blocked_seeds(_clean_env: None, _clean_db: None) -> None:
    """A critic-seed user the viewer blocks is not used for padding."""
    viewer = _make_user("user-viewer", "viewer")
    seed_a = _make_user("user-seed-a", "critica")
    for user in (viewer, seed_a):
        await user.insert()
    await CriticSeed(user_id=seed_a.id, priority=80, active=True).insert()
    await Block(
        blocker_id=viewer.id,
        blockee_id=seed_a.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    album = _make_album()
    await album.insert()
    await DiaryEntry(
        user_id=seed_a.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": viewer.id})
    body = response.json()
    assert body["entries"] == []


# ---------------------------------------------------------------------------
# Visibility matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_entries_hidden_from_non_owner(_clean_env: None, _clean_db: None) -> None:
    """A followee's private diary entry is not surfaced in the feed."""
    viewer = _make_user("user-viewer", "viewer")
    friend = _make_user("user-friend", "friend")
    for user in (viewer, friend):
        await user.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    await DiaryEntry(
        user_id=friend.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PRIVATE,
    ).insert()
    public_entry = DiaryEntry(
        user_id=friend.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await public_entry.insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": viewer.id})
    body = response.json()
    ids = [entry["id"] for entry in body["entries"]]
    assert ids == [public_entry.id]


@pytest.mark.asyncio
async def test_blocked_users_excluded_from_feed(_clean_env: None, _clean_db: None) -> None:
    """A blocked user's diary entries do not appear even with a Follow row."""
    viewer = _make_user("user-viewer", "viewer")
    a = _make_user("user-friend-a", "frienda")
    b = _make_user("user-friend-b", "friendb")
    for user in (viewer, a, b):
        await user.insert()
    for friend in (a, b):
        await Follow(
            follower_id=viewer.id,
            followee_id=friend.id,
            state=FollowState.ACCEPTED,
        ).insert()
    await Block(
        blocker_id=viewer.id,
        blockee_id=a.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    album = _make_album()
    await album.insert()
    await DiaryEntry(
        user_id=a.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()
    visible_entry = DiaryEntry(
        user_id=b.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await visible_entry.insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": viewer.id})
    ids = [entry["id"] for entry in response.json()["entries"]]
    assert ids == [visible_entry.id]


# ---------------------------------------------------------------------------
# Cursor pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feed_cursor_paginates_through_pages(_clean_env: None, _clean_db: None) -> None:
    """Two pages of 2 entries each yield disjoint sets."""
    viewer = _make_user("user-viewer", "viewer")
    friend = _make_user("user-friend", "friend")
    for user in (viewer, friend):
        await user.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)
    inserted_ids: list[str] = []
    for i in range(5):
        entry = DiaryEntry(
            user_id=friend.id,
            album_id=album.id,
            logged_at=now - timedelta(hours=i),
            rating=3.5,
            visibility=Visibility.PUBLIC,
        )
        await entry.insert()
        inserted_ids.append(entry.id)

    client = TestClient(_make_app())
    first = client.get(
        "/api/v1/feed?mode=latest&limit=2",
        headers={"X-User-Id": viewer.id},
    )
    first_body = first.json()
    assert len(first_body["entries"]) == 2
    assert first_body["next_cursor"] is not None
    first_ids = {entry["id"] for entry in first_body["entries"]}

    second = client.get(
        f"/api/v1/feed?mode=latest&limit=2&cursor={first_body['next_cursor']}",
        headers={"X-User-Id": viewer.id},
    )
    second_body = second.json()
    assert len(second_body["entries"]) == 2
    second_ids = {entry["id"] for entry in second_body["entries"]}
    # Disjoint pages.
    assert first_ids & second_ids == set()


@pytest.mark.asyncio
async def test_feed_malformed_cursor_returns_first_page(_clean_env: None, _clean_db: None) -> None:
    """A junk cursor is treated as "no cursor" (matches diary cursor semantics)."""
    await _setup_minimal_feed("user-viewer", count=2)
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/feed?cursor=this-is-not-base64",
        headers={"X-User-Id": "user-viewer"},
    )
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 2


@pytest.mark.asyncio
async def test_feed_limit_capped(_clean_env: None, _clean_db: None) -> None:
    """A huge limit query param is silently capped (no 4xx)."""
    await _setup_minimal_feed("user-viewer", count=2)
    client = TestClient(_make_app())
    response = client.get("/api/v1/feed?limit=10000", headers={"X-User-Id": "user-viewer"})
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 2


@pytest.mark.asyncio
async def test_feed_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/feed")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feed_score_components_carry_decay_and_base(
    _clean_env: None, _clean_db: None
) -> None:
    """For-you mode entries always carry the base + decay components."""
    await _setup_minimal_feed("user-viewer", count=1)
    client = TestClient(_make_app())
    response = client.get("/api/v1/feed", headers={"X-User-Id": "user-viewer"})
    body = response.json()
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    components = entry["score_components"]
    assert "base" in components
    assert "decay" in components
    assert components["decay"] > 0.0


@pytest.mark.asyncio
async def test_feed_cursor_payload_is_base64_json(_clean_env: None, _clean_db: None) -> None:
    """The returned cursor decodes to a valid JSON payload with l + i keys."""
    viewer = _make_user("user-viewer", "viewer")
    friend = _make_user("user-friend", "friend")
    for user in (viewer, friend):
        await user.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    now = datetime.now(UTC)
    for i in range(3):
        await DiaryEntry(
            user_id=friend.id,
            album_id=album.id,
            logged_at=now - timedelta(hours=i),
            rating=3.5,
            visibility=Visibility.PUBLIC,
        ).insert()

    client = TestClient(_make_app())
    response = client.get("/api/v1/feed?mode=latest&limit=2", headers={"X-User-Id": viewer.id})
    body = response.json()
    cursor = body["next_cursor"]
    assert isinstance(cursor, str)
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    decoded_bytes = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
    payload = json.loads(decoded_bytes)
    assert "l" in payload
    assert "i" in payload
