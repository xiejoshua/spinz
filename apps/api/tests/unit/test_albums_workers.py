"""Unit tests for :mod:`auxd_api.modules.albums.workers` (T064 + T065).

Covers both album-cache jobs:

* :func:`refresh_stale_album_metadata` — stale rows refreshed, no-stale
  returns zero, provider failures skipped without crashing.
* :func:`reconcile_candidate_albums` — confident match merged, low
  confidence retried later, no candidates returns zero, multiple matches
  pick the best score.

Providers are mocked via :class:`AsyncMock` and injected through the
``ctx`` dict the worker-startup hook normally populates. mongomock-motor
backs Beanie so the find/save cycle is exercised end-to-end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.albums.workers import (
    reconcile_candidate_albums,
    refresh_stale_album_metadata,
)
from auxd_api.providers.base import CatalogAlbum
from auxd_api.providers.errors import ProviderUnavailable

MBID_OK_COMPUTER = "b1392450-e666-3926-a536-22c65f834433"
MBID_KID_A = "11111111-2222-3333-4444-555555555555"


@pytest_asyncio.fixture
async def _clean_albums() -> AsyncIterator[None]:
    await Album.delete_all()
    yield
    await Album.delete_all()


def _stale_album(**overrides: object) -> Album:
    defaults: dict[str, object] = {
        "mbid": MBID_OK_COMPUTER,
        "title": "OK Computer",
        "artist_credit": "Radiohead",
        "source": AlbumSource.MUSICBRAINZ,
        # 1 day in the past — definitely stale.
        "cache_expires_at": datetime.now(UTC) - timedelta(days=1),
    }
    defaults.update(overrides)
    return Album(**defaults)


def _fresh_album(**overrides: object) -> Album:
    defaults: dict[str, object] = {
        "mbid": MBID_OK_COMPUTER,
        "title": "OK Computer",
        "artist_credit": "Radiohead",
        "source": AlbumSource.MUSICBRAINZ,
        "cache_expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(overrides)
    return Album(**defaults)


def _candidate_album(**overrides: object) -> Album:
    defaults: dict[str, object] = {
        "discogs_release_id": "release-249504",
        "title": "OK Computer",
        "artist_credit": "Radiohead",
        "source": AlbumSource.DISCOGS,
        "cache_expires_at": datetime.now(UTC) + timedelta(days=7),
        "candidate": True,
    }
    defaults.update(overrides)
    return Album(**defaults)


# ---------------------------------------------------------------------------
# T064 — refresh_stale_album_metadata
# ---------------------------------------------------------------------------


def _as_aware(dt: datetime) -> datetime:
    """Coerce a BSON-roundtripped datetime back to UTC-aware for comparisons.

    Beanie hands back naive datetimes from mongomock because BSON only
    stores UTC offsets implicitly; the in-process workers always write
    aware datetimes, so for assertion purposes we just re-attach UTC.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@pytest.mark.asyncio
async def test_refresh_picks_up_stale_album_and_refreshes(_clean_albums: None) -> None:
    """A stale MBID-bearing Album is re-fetched + merged + ``cache_expires_at`` bumped."""
    stale = _stale_album(release_year=1996)  # wrong year — refresh should fix.
    await stale.insert()
    original_expiry = stale.cache_expires_at

    mb_provider = AsyncMock()
    mb_provider.get_album_by_mbid.return_value = CatalogAlbum(
        mbid=MBID_OK_COMPUTER,
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        cover_art_url="https://coverartarchive.org/release-group/" + MBID_OK_COMPUTER + "/front",
    )
    ctx = {"mb_provider": mb_provider}
    refreshed = await refresh_stale_album_metadata(ctx)

    assert refreshed == 1
    mb_provider.get_album_by_mbid.assert_awaited_once_with(MBID_OK_COMPUTER)
    persisted = await Album.find_one(Album.mbid == MBID_OK_COMPUTER)
    assert persisted is not None
    assert persisted.release_year == 1997
    # TTL bumped forward.
    assert _as_aware(persisted.cache_expires_at) > _as_aware(original_expiry)


@pytest.mark.asyncio
async def test_refresh_returns_zero_when_no_stale(_clean_albums: None) -> None:
    """No stale rows → no provider calls, returns 0."""
    fresh = _fresh_album()
    await fresh.insert()

    mb_provider = AsyncMock()
    ctx = {"mb_provider": mb_provider}
    refreshed = await refresh_stale_album_metadata(ctx)

    assert refreshed == 0
    mb_provider.get_album_by_mbid.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_skips_album_on_provider_error(_clean_albums: None) -> None:
    """Per-album provider failures are logged + skipped — other rows still refresh."""
    bad = _stale_album(mbid=MBID_OK_COMPUTER, title="Bad Row")
    good = _stale_album(mbid=MBID_KID_A, title="Kid A")
    await bad.insert()
    await good.insert()

    mb_provider = AsyncMock()

    async def _maybe_fail(mbid: str) -> CatalogAlbum | None:
        if mbid == MBID_OK_COMPUTER:
            raise ProviderUnavailable("musicbrainz down", provider="musicbrainz")
        return CatalogAlbum(
            mbid=MBID_KID_A,
            title="Kid A",
            artist_name="Radiohead",
            release_year=2000,
        )

    mb_provider.get_album_by_mbid.side_effect = _maybe_fail
    ctx = {"mb_provider": mb_provider}
    refreshed = await refresh_stale_album_metadata(ctx)

    # Only the good row counted; the bad row stayed stale.
    assert refreshed == 1
    assert mb_provider.get_album_by_mbid.await_count == 2


@pytest.mark.asyncio
async def test_refresh_upstream_missing_extends_ttl_but_not_counted(
    _clean_albums: None,
) -> None:
    """When upstream returns ``None`` (MBID disappeared), TTL pushes out, no refresh."""
    stale = _stale_album()
    await stale.insert()

    mb_provider = AsyncMock()
    mb_provider.get_album_by_mbid.return_value = None
    ctx = {"mb_provider": mb_provider}
    refreshed = await refresh_stale_album_metadata(ctx)

    assert refreshed == 0
    persisted = await Album.find_one(Album.mbid == MBID_OK_COMPUTER)
    assert persisted is not None
    # TTL was extended even though no refresh happened.
    assert _as_aware(persisted.cache_expires_at) > datetime.now(UTC)


@pytest.mark.asyncio
async def test_refresh_skips_albums_without_mbid(_clean_albums: None) -> None:
    """Stale Discogs-only rows are NOT eligible — they go through reconciliation instead."""
    discogs_only = _candidate_album(cache_expires_at=datetime.now(UTC) - timedelta(days=1))
    await discogs_only.insert()

    mb_provider = AsyncMock()
    ctx = {"mb_provider": mb_provider}
    refreshed = await refresh_stale_album_metadata(ctx)
    assert refreshed == 0
    mb_provider.get_album_by_mbid.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_raises_when_provider_missing_from_ctx(
    _clean_albums: None,
) -> None:
    """Missing ``ctx['mb_provider']`` is a misconfiguration — surface loudly."""
    stale = _stale_album()
    await stale.insert()
    with pytest.raises(RuntimeError, match="mb_provider"):
        await refresh_stale_album_metadata({})


# ---------------------------------------------------------------------------
# T065 — reconcile_candidate_albums
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconcile_confident_match_promotes_candidate(
    _clean_albums: None,
) -> None:
    """A high-confidence MusicBrainz hit merges the MBID + clears the candidate flag."""
    candidate = _candidate_album()
    await candidate.insert()

    mb_provider = AsyncMock()
    cover = f"https://coverartarchive.org/release-group/{MBID_OK_COMPUTER}/front"
    mb_provider.search_albums.return_value = [
        CatalogAlbum(
            mbid=MBID_OK_COMPUTER,
            title="OK Computer",
            artist_name="Radiohead",
            cover_art_url=cover,
        )
    ]
    ctx = {"mb_provider": mb_provider}
    reconciled = await reconcile_candidate_albums(ctx)

    assert reconciled == 1
    promoted = await Album.find_one(Album.discogs_release_id == "release-249504")
    assert promoted is not None
    assert promoted.mbid == MBID_OK_COMPUTER
    assert promoted.candidate is False
    assert promoted.source is AlbumSource.MUSICBRAINZ


@pytest.mark.asyncio
async def test_reconcile_no_match_leaves_candidate(_clean_albums: None) -> None:
    """When no hit clears the threshold, the row stays a candidate."""
    candidate = _candidate_album()
    await candidate.insert()

    mb_provider = AsyncMock()
    mb_provider.search_albums.return_value = [
        # Title matches, but artist doesn't — score 0.6, below 0.8 threshold.
        CatalogAlbum(
            mbid=MBID_KID_A,
            title="OK Computer",
            artist_name="Some Other Band",
        )
    ]
    ctx = {"mb_provider": mb_provider}
    reconciled = await reconcile_candidate_albums(ctx)

    assert reconciled == 0
    still_candidate = await Album.find_one(Album.discogs_release_id == "release-249504")
    assert still_candidate is not None
    assert still_candidate.mbid is None
    assert still_candidate.candidate is True


@pytest.mark.asyncio
async def test_reconcile_picks_best_of_multiple_hits(_clean_albums: None) -> None:
    """Multiple hits → pick the one with the highest confidence score."""
    candidate = _candidate_album()
    await candidate.insert()

    mb_provider = AsyncMock()
    mb_provider.search_albums.return_value = [
        # Bad match — title only.
        CatalogAlbum(
            mbid=MBID_KID_A,
            title="OK Computer",
            artist_name="Some Cover Band",
        ),
        # Perfect match — both title + artist.
        CatalogAlbum(
            mbid=MBID_OK_COMPUTER,
            title="OK Computer",
            artist_name="Radiohead",
        ),
    ]
    ctx = {"mb_provider": mb_provider}
    reconciled = await reconcile_candidate_albums(ctx)

    assert reconciled == 1
    promoted = await Album.find_one(Album.discogs_release_id == "release-249504")
    assert promoted is not None
    assert promoted.mbid == MBID_OK_COMPUTER


@pytest.mark.asyncio
async def test_reconcile_returns_zero_when_no_candidates(_clean_albums: None) -> None:
    """No candidate rows → no provider call, returns 0."""
    not_candidate = _fresh_album()
    await not_candidate.insert()

    mb_provider = AsyncMock()
    ctx = {"mb_provider": mb_provider}
    reconciled = await reconcile_candidate_albums(ctx)

    assert reconciled == 0
    mb_provider.search_albums.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_skips_candidate_on_provider_error(
    _clean_albums: None,
) -> None:
    """Provider failures on a single candidate don't blow up the batch."""
    bad = _candidate_album(discogs_release_id="release-bad", title="Bad Match")
    good = _candidate_album(discogs_release_id="release-good", title="OK Computer")
    await bad.insert()
    await good.insert()

    mb_provider = AsyncMock()

    async def _maybe_fail(query: str, *, limit: int = 10) -> list[CatalogAlbum]:
        if "Bad Match" in query:
            raise ProviderUnavailable("musicbrainz", provider="musicbrainz")
        return [
            CatalogAlbum(
                mbid=MBID_OK_COMPUTER,
                title="OK Computer",
                artist_name="Radiohead",
            )
        ]

    mb_provider.search_albums.side_effect = _maybe_fail
    ctx = {"mb_provider": mb_provider}
    reconciled = await reconcile_candidate_albums(ctx)

    # The good candidate got reconciled; the bad one stayed a candidate.
    assert reconciled == 1
    assert mb_provider.search_albums.await_count == 2
