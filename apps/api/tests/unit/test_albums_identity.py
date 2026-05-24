"""Unit tests for :mod:`auxd_api.modules.albums.identity` (T063).

Coverage:

* MBID cache hit returns the cached :class:`Album` without calling MusicBrainz.
* MBID cache miss fetches from MusicBrainz, materialises a fresh row, returns it.
* MBID with no upstream match raises :class:`AlbumNotFoundError`.
* Discogs-master path (search-fix v4 primary path) — cache hit /
  cache miss / provider failure.
* Discogs-release fallback creates a candidate row via Discogs lookup.
* Missing all identifiers raises :class:`ValueError`.

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
from auxd_api.providers.errors import ProviderUnavailable

MBID = "b1392450-e666-3926-a536-22c65f834433"
DISCOGS_ID = "release-249504"
MASTER_ID = "master-249504"


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


# ---------------------------------------------------------------------------
# Search-fix v4 — Discogs master path (primary external lookup)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_identity_by_discogs_master_id_hits_cache(
    _clean_albums: None,
) -> None:
    """An existing Album with ``discogs_master_id`` is returned directly —
    no provider call, no second materialisation.
    """
    from datetime import UTC, datetime, timedelta

    existing = Album(
        discogs_master_id=MASTER_ID,
        title="Cached Master Album",
        artist_credit="Cached Artist",
        source=AlbumSource.DISCOGS,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
        candidate=False,
    )
    await existing.insert()

    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()

    album = await resolve_identity(
        discogs_master_id=MASTER_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.discogs_master_id == MASTER_ID
    assert album.title == "Cached Master Album"
    discogs_provider.get_album_by_external_id.assert_not_called()
    mb_provider.get_album_by_mbid.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_identity_by_discogs_master_id_materializes(
    _clean_albums: None,
) -> None:
    """No existing Album → fetches Discogs master detail, creates an
    Album row with ``candidate=False`` (masters are canonical, not
    reconciliation candidates), and returns the new row.
    """
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id=MASTER_ID,
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        cover_art_url="https://img.discogs.com/ok/front.jpg",
        community_have=50000,
        external_ids={"discogs_master": MASTER_ID},
    )

    album = await resolve_identity(
        discogs_master_id=MASTER_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.discogs_master_id == MASTER_ID
    assert album.mbid is None
    assert album.discogs_release_id is None
    assert album.title == "OK Computer"
    assert album.artist_credit == "Radiohead"
    assert album.source is AlbumSource.DISCOGS
    # Masters are canonical identities — not flagged for reconciliation.
    assert album.candidate is False
    discogs_provider.get_album_by_external_id.assert_awaited_once_with("discogs_master", MASTER_ID)
    mb_provider.get_album_by_mbid.assert_not_called()
    # Persisted.
    persisted = await Album.find_one(Album.discogs_master_id == MASTER_ID)
    assert persisted is not None
    assert persisted.id == album.id


@pytest.mark.asyncio
async def test_resolve_identity_by_discogs_master_id_no_upstream_match_raises(
    _clean_albums: None,
) -> None:
    """Discogs returning ``None`` for a master id raises :class:`AlbumNotFoundError`."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = None

    with pytest.raises(AlbumNotFoundError):
        await resolve_identity(
            discogs_master_id=MASTER_ID,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


@pytest.mark.asyncio
async def test_resolve_identity_by_discogs_master_id_provider_failure_propagates(
    _clean_albums: None,
) -> None:
    """A :class:`ProviderError` raised by the Discogs master lookup
    propagates to the caller. The search service catches ProviderError
    at its outer try/except; the identity layer does not swallow
    upstream failures silently.
    """
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.side_effect = ProviderUnavailable(
        "discogs down", provider="discogs"
    )

    with pytest.raises(ProviderUnavailable):
        await resolve_identity(
            discogs_master_id=MASTER_ID,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


# ---------------------------------------------------------------------------
# Discogs release-id fallback path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discogs_fallback_creates_candidate_album(_clean_albums: None) -> None:
    """Discogs release-id path creates a candidate row flagged for T065
    reconciliation. Distinct from the master path: release ids carry
    pressing-specific metadata, masters do not.
    """
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
    assert album.candidate is True  # release-id rows still need MBID reconciliation
    discogs_provider.get_album_by_external_id.assert_awaited_once_with("discogs", DISCOGS_ID)
    mb_provider.get_album_by_mbid.assert_not_called()


@pytest.mark.asyncio
async def test_discogs_cache_hit_returns_without_provider_call(
    _clean_albums: None,
) -> None:
    """Pre-existing Discogs release id hits cache and short-circuits the provider."""
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
    """Discogs release id returning None raises :class:`AlbumNotFoundError`."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = None

    with pytest.raises(AlbumNotFoundError):
        await resolve_identity(
            discogs_release_id=DISCOGS_ID,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


# ---------------------------------------------------------------------------
# Error paths + priority
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_identifier_raises_value_error(_clean_albums: None) -> None:
    """None of mbid / master_id / release_id supplied → :class:`ValueError`."""
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()

    with pytest.raises(ValueError, match="mbid"):
        await resolve_identity(
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )


@pytest.mark.asyncio
async def test_mbid_preferred_when_both_provided(_clean_albums: None) -> None:
    """When MBID + Discogs release id are both supplied, MBID wins."""
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


@pytest.mark.asyncio
async def test_mbid_preferred_over_master_id(_clean_albums: None) -> None:
    """MBID also wins over ``discogs_master_id`` — MB is the canonical
    identity when both are present.
    """
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
        discogs_master_id=MASTER_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.mbid == MBID
    discogs_provider.get_album_by_external_id.assert_not_called()


@pytest.mark.asyncio
async def test_master_id_preferred_over_release_id(_clean_albums: None) -> None:
    """When both Discogs identifiers are supplied (no MBID), the master
    id wins because it's the canonical Discogs identifier.
    """
    mb_provider = AsyncMock()
    discogs_provider = AsyncMock()
    discogs_provider.get_album_by_external_id.return_value = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id=MASTER_ID,
        title="From Master",
        artist_name="Some Artist",
        external_ids={"discogs_master": MASTER_ID},
    )

    album = await resolve_identity(
        discogs_master_id=MASTER_ID,
        discogs_release_id=DISCOGS_ID,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )
    assert album.discogs_master_id == MASTER_ID
    discogs_provider.get_album_by_external_id.assert_awaited_once_with("discogs_master", MASTER_ID)
