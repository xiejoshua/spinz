"""Unit tests for the per-user genre-signature computation (T163).

Covers :func:`auxd_api.modules.seeding.genre_signature.compute_genre_signature` —
the weighted aggregation of a user's diary entries by album genres, the
24-hour Redis cache, and the fail-open behaviour when Redis is down.

The DB is mongomock-motor (auto-fixtured in :mod:`tests.conftest`); the
Redis client is a per-test :class:`MagicMock` swapped in via the
``redis_module._client`` module-level singleton, mirroring the pattern
used by :mod:`tests.unit.test_redis_client`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from auxd_api import redis_client as redis_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.seeding.genre_signature import (
    _CACHE_TTL_SECONDS,
    compute_genre_signature,
)


def _make_album(
    album_id: str,
    *,
    genres: list[str],
    title: str = "Test Album",
) -> Album:
    return Album(
        id=album_id,
        mbid=None,
        discogs_release_id=None,
        title=title,
        artist_credit="Test Artist",
        genres=genres,
        source=AlbumSource.MANUAL,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_entry(
    *,
    user_id: str,
    album_id: str,
    rating: float | None,
    logged_at: datetime | None = None,
) -> DiaryEntry:
    return DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=logged_at or datetime.now(UTC),
        rating=rating,
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await DiaryEntry.delete_all()
    await Album.delete_all()
    yield
    await DiaryEntry.delete_all()
    await Album.delete_all()


@pytest_asyncio.fixture
async def _no_redis() -> AsyncIterator[None]:
    """Run with Redis singleton unset → cache_get/set are no-ops."""
    prev = redis_module._client
    redis_module._client = None
    try:
        yield
    finally:
        redis_module._client = prev


@pytest.mark.asyncio
async def test_empty_diary_returns_empty(_clean_db: None, _no_redis: None) -> None:
    """User with no diary entries → ``{}``."""
    result = await compute_genre_signature("user-ghost")
    assert result == {}


@pytest.mark.asyncio
async def test_single_album_two_genres_top_rating(_clean_db: None, _no_redis: None) -> None:
    """5★ + 2 genres → both genres equal, max weight = 1.0."""
    await _make_album("alb-1", genres=["jazz", "fusion"]).insert()
    await _make_entry(user_id="user-a", album_id="alb-1", rating=5.0).insert()

    sig = await compute_genre_signature("user-a")
    assert set(sig.keys()) == {"jazz", "fusion"}
    assert sig["jazz"] == 1.0
    assert sig["fusion"] == 1.0


@pytest.mark.asyncio
async def test_multi_album_varied_ratings(_clean_db: None, _no_redis: None) -> None:
    """Higher-rated entries dominate; weights are normalised to peak=1.0."""
    await _make_album("alb-jazz", genres=["jazz"]).insert()
    await _make_album("alb-rock", genres=["rock"]).insert()
    # 5★ jazz → weight 2.0; 3★ rock → weight 1.0.
    await _make_entry(user_id="user-a", album_id="alb-jazz", rating=5.0).insert()
    await _make_entry(user_id="user-a", album_id="alb-rock", rating=3.0).insert()

    sig = await compute_genre_signature("user-a")
    # Jazz is the peak → normalised to 1.0; rock is half of that.
    assert sig["jazz"] == 1.0
    assert sig["rock"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_no_rating_treated_as_baseline(_clean_db: None, _no_redis: None) -> None:
    """Entries without a rating contribute the baseline 1.0 weight."""
    await _make_album("alb-1", genres=["pop"]).insert()
    await _make_album("alb-2", genres=["pop"]).insert()
    await _make_entry(user_id="user-a", album_id="alb-1", rating=None).insert()
    await _make_entry(user_id="user-a", album_id="alb-2", rating=None).insert()

    sig = await compute_genre_signature("user-a")
    # Two entries, both baseline → pop is the only genre, normalised to 1.0.
    assert sig == {"pop": 1.0}


@pytest.mark.asyncio
async def test_albums_without_genres_excluded(_clean_db: None, _no_redis: None) -> None:
    """Entries pointing at albums with empty ``genres`` contribute nothing."""
    await _make_album("alb-nogenre", genres=[]).insert()
    await _make_album("alb-jazz", genres=["jazz"]).insert()
    await _make_entry(user_id="user-a", album_id="alb-nogenre", rating=5.0).insert()
    await _make_entry(user_id="user-a", album_id="alb-jazz", rating=4.0).insert()

    sig = await compute_genre_signature("user-a")
    assert sig == {"jazz": 1.0}


@pytest.mark.asyncio
async def test_cache_hit_short_circuits_compute(_clean_db: None) -> None:
    """A live cache hit skips the DB compute entirely."""
    # No diary entries in the DB; if the function reads them and computes
    # empty, the assertion below will fail.
    cached_payload = json.dumps({"jazz": 1.0, "fusion": 0.5})
    fake = MagicMock()
    fake.get = AsyncMock(return_value=cached_payload)
    fake.set = AsyncMock()
    redis_module._client = fake
    try:
        sig = await compute_genre_signature("user-a")
        assert sig == {"jazz": 1.0, "fusion": 0.5}
        fake.get.assert_awaited_once()
        fake.set.assert_not_awaited()
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_cache_miss_recomputes_and_writes(_clean_db: None) -> None:
    """Cache miss → compute from DB and write the result back with TTL."""
    await _make_album("alb-1", genres=["pop"]).insert()
    await _make_entry(user_id="user-b", album_id="alb-1", rating=4.0).insert()

    fake = MagicMock()
    fake.get = AsyncMock(return_value=None)  # cache miss
    fake.set = AsyncMock(return_value=True)
    redis_module._client = fake
    try:
        sig = await compute_genre_signature("user-b")
        assert sig == {"pop": 1.0}
        fake.set.assert_awaited_once()
        args, kwargs = fake.set.call_args
        assert args[0] == "genre_signature:user-b"
        # The encoded payload should round-trip cleanly.
        assert json.loads(args[1]) == {"pop": 1.0}
        assert kwargs["ex"] == _CACHE_TTL_SECONDS
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_redis_unavailable_fails_open(_clean_db: None) -> None:
    """Both ``get`` and ``set`` raising → function still returns a valid signature."""
    await _make_album("alb-1", genres=["ambient"]).insert()
    await _make_entry(user_id="user-c", album_id="alb-1", rating=4.5).insert()

    fake = MagicMock()
    fake.get = AsyncMock(side_effect=RedisConnectionError("down"))
    fake.set = AsyncMock(side_effect=RedisConnectionError("down"))
    redis_module._client = fake
    try:
        sig = await compute_genre_signature("user-c")
        assert sig == {"ambient": 1.0}
    finally:
        redis_module._client = None
