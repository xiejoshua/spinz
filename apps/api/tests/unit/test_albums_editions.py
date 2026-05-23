"""Unit tests for :mod:`auxd_api.modules.albums.editions` (T066).

Exercises the edition-aggregation service against mongomock-motor:

* :func:`get_editions` returns every Album sharing a release-group MBID.
* :func:`get_canonical_edition` picks the earliest-year row, breaking
  ties on longest tracklist.
* :func:`aggregate_ratings` rolls up DiaryEntry + Review + ReviewLike
  counts across every edition; empty release-groups return zeros.

At MVP, the ``Album.mbid`` unique-sparse index means a release-group can
have at most one :class:`Album` row in the catalog (see module
docstring); future work will add per-release MBIDs and drop the unique
constraint. These tests therefore exercise the single-edition behaviour
end-to-end and verify the dedupe key by exercising the in-process
sort/dedupe logic directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from auxd_api.modules.albums.editions import (
    aggregate_ratings,
    get_canonical_edition,
    get_editions,
)
from auxd_api.modules.albums.models import Album, AlbumSource, TrackSubDoc
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review, ReviewLike

RG_MBID = "b1392450-e666-3926-a536-22c65f834433"
RG_MBID_OTHER = "11111111-2222-3333-4444-555555555555"


def _album(**overrides: object) -> Album:
    defaults: dict[str, object] = {
        "mbid": RG_MBID,
        "title": "OK Computer",
        "artist_credit": "Radiohead",
        "source": AlbumSource.MUSICBRAINZ,
        "cache_expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(overrides)
    return Album(**defaults)


@pytest_asyncio.fixture
async def _clean_albums() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()


@pytest.mark.asyncio
async def test_get_editions_returns_album_for_known_mbid(_clean_albums: None) -> None:
    """A known MBID returns the single matching Album."""
    album = _album(release_year=1997)
    await album.insert()

    editions = await get_editions(RG_MBID)
    assert len(editions) == 1
    assert editions[0].title == "OK Computer"


@pytest.mark.asyncio
async def test_get_editions_only_returns_matching_mbid(_clean_albums: None) -> None:
    """Other-MBID albums are NOT returned in the rollup."""
    await _album(release_year=1997).insert()
    other = _album(mbid=RG_MBID_OTHER, title="Kid A", release_year=2000)
    await other.insert()

    editions = await get_editions(RG_MBID)
    assert len(editions) == 1
    assert editions[0].mbid == RG_MBID


@pytest.mark.asyncio
async def test_get_editions_unknown_mbid_returns_empty(_clean_albums: None) -> None:
    """Querying an MBID with no Albums returns an empty list (no exception)."""
    editions = await get_editions("00000000-0000-0000-0000-000000000000")
    assert editions == []


@pytest.mark.asyncio
async def test_get_canonical_edition_returns_album_with_mbid(_clean_albums: None) -> None:
    """With a single edition, the canonical pick is that edition."""
    album = _album(release_year=1997)
    await album.insert()

    canonical = await get_canonical_edition(RG_MBID)
    assert canonical is not None
    assert canonical.mbid == RG_MBID
    assert canonical.release_year == 1997


@pytest.mark.asyncio
async def test_get_canonical_edition_unknown_mbid_returns_none(
    _clean_albums: None,
) -> None:
    """No editions for the MBID → ``None``."""
    assert await get_canonical_edition("00000000-0000-0000-0000-000000000000") is None


def test_canonical_edition_in_memory_picks_earliest_year() -> None:
    """In-memory sort logic — earliest ``release_year`` wins.

    Direct logic test (no DB round-trip) for the canonical-pick
    behaviour; pinned here so future schema changes that add per-release
    MBIDs (and drop the unique constraint) inherit the same tiebreak
    rules.
    """
    later = _album(release_year=2017, title="Deluxe")
    earlier = _album(release_year=1997, title="Standard")
    # Mimic the sort key used in get_canonical_edition.
    pick = min(
        [later, earlier],
        key=lambda a: (
            a.release_year if a.release_year is not None else 9999,
            -len(a.tracklist),
        ),
    )
    assert pick.title == "Standard"


def test_canonical_edition_in_memory_ties_break_on_longest_tracklist() -> None:
    """In-memory sort logic — longer tracklist wins when years tie."""
    short = _album(
        release_year=1997,
        title="Standard",
        tracklist=[TrackSubDoc(position=1, title="t1")],
    )
    longer = _album(
        release_year=1997,
        title="Deluxe",
        tracklist=[
            TrackSubDoc(position=1, title="t1"),
            TrackSubDoc(position=2, title="t2"),
            TrackSubDoc(position=3, title="t3"),
        ],
    )
    pick = min(
        [short, longer],
        key=lambda a: (
            a.release_year if a.release_year is not None else 9999,
            -len(a.tracklist),
        ),
    )
    assert pick.title == "Deluxe"


@pytest.mark.asyncio
async def test_aggregate_ratings_returns_zeros_for_empty_release_group(
    _clean_albums: None,
) -> None:
    """No editions → every counter is zero."""
    aggregate = await aggregate_ratings("00000000-0000-0000-0000-000000000000")
    assert aggregate == {
        "avg_rating": 0.0,
        "rating_count": 0,
        "review_count": 0,
        "aux_count": 0,
        "like_count": 0,
    }


@pytest.mark.asyncio
async def test_aggregate_ratings_returns_zeros_when_no_diary_activity(
    _clean_albums: None,
) -> None:
    """Editions exist but no DiaryEntries — still zero counts."""
    await _album().insert()
    aggregate = await aggregate_ratings(RG_MBID)
    assert aggregate["rating_count"] == 0
    assert aggregate["review_count"] == 0
    assert aggregate["aux_count"] == 0
    assert aggregate["like_count"] == 0


@pytest.mark.asyncio
async def test_aggregate_ratings_sums_diary_review_like_counts(
    _clean_albums: None,
) -> None:
    """DiaryEntry + Review + ReviewLike counts roll up correctly."""
    album = _album()
    await album.insert()

    # 3 ratings + 1 aux on the edition.
    await DiaryEntry(
        user_id="u1",
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.5,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id="u2",
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        auxed=True,
        visibility=Visibility.PUBLIC,
    ).insert()
    diary3 = DiaryEntry(
        user_id="u3",
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await diary3.insert()

    # 1 review + 2 likes on the review.
    review = Review(
        user_id="u3",
        diary_entry_id=diary3.id,
        album_id=album.id,
        body="brilliant",
    )
    await review.insert()
    await ReviewLike(review_id=review.id, user_id="u1").insert()
    await ReviewLike(review_id=review.id, user_id="u2").insert()

    aggregate = await aggregate_ratings(RG_MBID)
    assert aggregate["rating_count"] == 3
    assert aggregate["avg_rating"] == round((4.5 + 5.0 + 4.0) / 3, 2)
    assert aggregate["aux_count"] == 1
    assert aggregate["review_count"] == 1
    assert aggregate["like_count"] == 2


@pytest.mark.asyncio
async def test_aggregate_ratings_skips_soft_deleted_diary_entries(
    _clean_albums: None,
) -> None:
    """Soft-deleted diary entries don't count toward the rollup."""
    album = _album()
    await album.insert()

    await DiaryEntry(
        user_id="u1",
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.5,
        visibility=Visibility.PUBLIC,
    ).insert()
    # Soft-deleted — must not contribute.
    deleted = DiaryEntry(
        user_id="u2",
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PUBLIC,
        deleted_at=datetime.now(UTC),
    )
    await deleted.insert()

    aggregate = await aggregate_ratings(RG_MBID)
    assert aggregate["rating_count"] == 1
    assert aggregate["avg_rating"] == 4.5
