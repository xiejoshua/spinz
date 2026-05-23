"""Unit tests for :mod:`auxd_api.modules.albums.identity` (T063).

Coverage:

* MBID cache hit returns the cached :class:`Album` without calling MusicBrainz.
* MBID cache miss fetches from MusicBrainz, materialises a fresh row, returns it.
* MBID with no upstream match raises :class:`AlbumNotFoundError`.
* Discogs fallback (no MBID) creates a candidate row via Discogs lookup.
* Missing both identifiers raises :class:`ValueError`.

Tests use mongomock-motor via the session fixture in ``conftest.py`` so
the Album.insert() calls actually round-trip through Beanie's writer
path; providers are mocked with :class:`AsyncMock` to keep the tests
provider-impl-agnostic (Constitution P6).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.identity import resolve_identity
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.providers.base import CatalogAlbum

MBID = "b1392450-e666-3926-a536-22c65f834433"
DISCOGS_ID = "release-249504"


@pytest_asyncio.fixture
async def _clean_albums() -> AsyncIterator[None]:
    """Wipe ``albums`` between tests so the cache-hit suite stays deterministic."""
    await Album.delete_all()
    yield
    await Album.delete_all()


@pytest.mark.asyncio
async def test_mbid_cache_hit_returns_existing_album(_clean_albums: None) -> None:
    """When an Album with the MBID exists, return it without provider calls."""
    from datetime import UTC, datetime, timedelta

    existing = Album(
        mbid=MBID,
        title="OK Computer",
        artist_credit="Radiohead",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await existing.insert()

    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()

    album = await resolve_identity(
        mbid=MBID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.mbid == MBID
    assert album.title == "OK Computer"
    mb_provider.get_album_by_mbid.assert_not_called()
    discogs_provider.get_album_by_external_id.assert_not_called()


@pytest.mark.asyncio
async def test_mbid_cache_miss_fetches_and_materializes(_clean_albums: None) -> None:
    """On miss, fetch from MusicBrainz + insert + return the new row."""
    mb_provider = AsyncMock()
    mb_provider.get_album_by_mbid.return_value = CatalogAlbum(
        mbid=MBID,
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        cover_art_url="https://coverartarchive.org/release-group/" + MBID + "/front",
        external_ids={"mbid": MBID},
    )
    discogs_provider = AsyncMock()

    album = await resolve_identity(
        mbid=MBID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.mbid == MBID
    assert album.title == "OK Computer"
    assert album.artist_credit == "Radiohead"
    assert album.release_year == 1997
    assert album.source is AlbumSource.MUSICBRAINZ
    assert album.candidate is False
    mb_provider.get_album_by_mbid.assert_awaited_once_with(MBID)
    # Persisted — a follow-up lookup must hit the cache.
    persisted = await Album.find_one(Album.mbid == MBID)
    assert persisted is not None
    assert persisted.id == album.id


@pytest.mark.asyncio
async def test_mbid_no_upstream_match_raises_album_not_found(
    _clean_albums: None,
) -> None:
    """When MusicBrainz returns ``None``, surface :class:`AlbumNotFoundError`."""
    mb_provider = AsyncMock()
    mb_provider.get_album_by_mbid.return_value = None
    discogs_provider = AsyncMock()

    with pytest.raises(AlbumNotFoundError):
        await resolve_identity(
            mbid=MBID,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


@pytest.mark.asyncio
async def test_discogs_fallback_creates_candidate_album(_clean_albums: None) -> None:
    """Discogs-only id creates a candidate row flagged for T065 reconciliation."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = CatalogAlbum(
        mbid=None,
        discogs_release_id=DISCOGS_ID,
        title="Some Indie Album",
        artist_name="Unknown Artist",
        release_year=2026,
        external_ids={"discogs": DISCOGS_ID},
    )

    album = await resolve_identity(
        discogs_release_id=DISCOGS_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.mbid is None
    assert album.discogs_release_id == DISCOGS_ID
    assert album.source is AlbumSource.DISCOGS
    assert album.candidate is True
    discogs_provider.get_album_by_external_id.assert_awaited_once_with("discogs", DISCOGS_ID)
    mb_provider.get_album_by_mbid.assert_not_called()


@pytest.mark.asyncio
async def test_discogs_cache_hit_returns_without_provider_call(
    _clean_albums: None,
) -> None:
    """Pre-existing Discogs id hits cache and short-circuits the provider."""
    from datetime import UTC, datetime, timedelta

    existing = Album(
        discogs_release_id=DISCOGS_ID,
        title="Cached Indie Album",
        artist_credit="Some Artist",
        source=AlbumSource.DISCOGS,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
        candidate=True,
    )
    await existing.insert()

    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()

    album = await resolve_identity(
        discogs_release_id=DISCOGS_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.discogs_release_id == DISCOGS_ID
    discogs_provider.get_album_by_external_id.assert_not_called()


@pytest.mark.asyncio
async def test_discogs_no_upstream_match_raises_album_not_found(
    _clean_albums: None,
) -> None:
    """Discogs returning None raises :class:`AlbumNotFoundError`."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = None

    with pytest.raises(AlbumNotFoundError):
        await resolve_identity(
            discogs_release_id=DISCOGS_ID,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


@pytest.mark.asyncio
async def test_no_identifier_raises_value_error(_clean_albums: None) -> None:
    """Neither MBID nor Discogs id supplied → :class:`ValueError`."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()

    with pytest.raises(ValueError, match="mbid or discogs_release_id"):
        await resolve_identity(
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


@pytest.mark.asyncio
async def test_mbid_preferred_when_both_provided(_clean_albums: None) -> None:
    """When MBID + Discogs id are both supplied, MBID wins."""
    mb_provider = AsyncMock()
    mb_provider.get_album_by_mbid.return_value = CatalogAlbum(
        mbid=MBID,
        title="MBID Wins",
        artist_name="Some Artist",
        external_ids={"mbid": MBID},
    )
    discogs_provider = AsyncMock()

    album = await resolve_identity(
        mbid=MBID,
        discogs_release_id=DISCOGS_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.mbid == MBID
    mb_provider.get_album_by_mbid.assert_awaited_once_with(MBID)
    discogs_provider.get_album_by_external_id.assert_not_called()
