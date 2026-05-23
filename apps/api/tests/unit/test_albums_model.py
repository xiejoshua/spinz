"""Unit tests for :mod:`auxd_api.modules.albums.models`.

These tests exercise the Beanie ``Album`` document **without** a live
MongoDB connection. Beanie's ``Document`` is a Pydantic v2 model at heart,
so construction, validation, and serialization are exercised in-process —
DB-roundtrip behaviour (indexes, uniqueness) belongs in integration tests.
"""

from __future__ import annotations

import string
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from auxd_api.modules.albums.models import (
    Album,
    AlbumSource,
    ArtistRefSubDoc,
    EditionRefSubDoc,
    TrackSubDoc,
)

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


def _minimum_album(**overrides: object) -> Album:
    """Construct an ``Album`` with only the required fields populated.

    Centralised so every test stays focused on the one constraint it's
    pinning, rather than re-listing the required-fields tuple inline.
    """
    defaults: dict[str, object] = {
        "title": "Black on Both Sides",
        "artist_credit": "Mos Def",
        "source": AlbumSource.MUSICBRAINZ,
        "cache_expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(overrides)
    return Album(**defaults)


def test_album_has_ksuid_id() -> None:
    """``Album.id`` defaults to a fresh KSUID (27-char base62 string)."""
    album = _minimum_album()
    assert isinstance(album.id, str)
    assert len(album.id) == 27
    assert set(album.id).issubset(BASE62_ALPHABET)


def test_album_required_fields() -> None:
    """``title``, ``artist_credit``, ``source``, ``cache_expires_at`` are all required."""
    # Omitting any one of the four required fields must raise ValidationError.
    base = {
        "title": "Black on Both Sides",
        "artist_credit": "Mos Def",
        "source": AlbumSource.MUSICBRAINZ,
        "cache_expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    for missing in ("title", "artist_credit", "source", "cache_expires_at"):
        partial = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(ValidationError):
            Album(**partial)


def test_album_optional_identifiers() -> None:
    """Both ``mbid`` and ``discogs_release_id`` may be ``None`` (rare but supported).

    CR-001: replaced ``spotify_id`` with ``discogs_release_id`` as the
    secondary catalog identifier.
    """
    album = _minimum_album()
    assert album.mbid is None
    assert album.discogs_release_id is None
    # Either alone is fine.
    only_mbid = _minimum_album(mbid="3f7d5b4e-1234-5678-9abc-def012345678")
    assert only_mbid.mbid is not None
    assert only_mbid.discogs_release_id is None
    only_discogs = _minimum_album(discogs_release_id="release-249504")
    assert only_discogs.mbid is None
    assert only_discogs.discogs_release_id == "release-249504"


def test_album_discogs_release_id_field_and_index() -> None:
    """CR-001 + post-§6 fix: ``discogs_release_id`` is unique with a
    ``partialFilterExpression`` (not ``sparse``).

    Direct replacement for the deleted ``spotify_id`` index/field test.
    The partialFilterExpression is required because Pydantic serialises
    ``None`` → MongoDB ``null`` (not "missing field"), and a sparse index
    still indexes documents where the field IS present with a ``null``
    value — so a sparse-unique constraint fired on the *second* insert
    of a null-discogs Album in production (caught after the §6 search
    endpoint went live and the second MB-fallback materialise tried to
    insert).
    """
    album = _minimum_album(discogs_release_id="release-321321")
    assert album.discogs_release_id == "release-321321"

    # The unique partial-filter index must be declared exactly once and
    # never alongside a leftover ``spotify_id`` index.
    indexes = Album.Settings.indexes
    discogs_indexes = [idx for idx in indexes if "discogs_release_id" in dict(idx.document["key"])]
    assert len(discogs_indexes) == 1
    discogs_index = discogs_indexes[0]
    assert discogs_index.document.get("unique") is True
    # NOT sparse — partial filter instead.
    assert discogs_index.document.get("sparse") is None
    partial = discogs_index.document.get("partialFilterExpression")
    # MongoDB's partialFilterExpression grammar disallows $ne / $not, so
    # we use $type: "string" instead — same semantic (only index real
    # string values, exclude null + missing).
    assert partial == {"discogs_release_id": {"$type": "string"}}

    # No residual ``spotify_id`` index survived CR-001.
    for idx in indexes:
        assert "spotify_id" not in idx.document["key"]


def test_album_mbid_partial_filter_index_matches_discogs() -> None:
    """Symmetric to the discogs check: ``mbid`` uses the same partial-filter
    shape so both identifiers behave consistently when ``None``.
    """
    indexes = Album.Settings.indexes
    mbid_indexes = [idx for idx in indexes if "mbid" in dict(idx.document["key"])]
    # mbid is in two places: the unique partial-filter index AND any other
    # mbid-bearing compound index. Filter to the unique one.
    unique = [idx for idx in mbid_indexes if idx.document.get("unique") is True]
    assert len(unique) == 1
    mbid_index = unique[0]
    assert mbid_index.document.get("sparse") is None
    partial = mbid_index.document.get("partialFilterExpression")
    assert partial == {"mbid": {"$type": "string"}}


def test_album_with_tracklist() -> None:
    """An ``Album`` with embedded :class:`TrackSubDoc` rows round-trips through JSON.

    CR-001: tracks no longer carry ``spotify_track_id``; assertions
    rewritten around ``mbid`` instead.
    """
    tracks = [
        TrackSubDoc(position=1, title="Fear Not of Man", duration_ms=283000),
        TrackSubDoc(position=2, title="Hip Hop", duration_ms=337000),
        TrackSubDoc(
            position=3,
            title="Love",
            duration_ms=234000,
            mbid="11111111-2222-3333-4444-555555555555",
        ),
    ]
    album = _minimum_album(tracklist=tracks)
    assert len(album.tracklist) == 3
    assert album.tracklist[0].position == 1
    assert album.tracklist[2].mbid == "11111111-2222-3333-4444-555555555555"
    # Default disc_number = 1 must round-trip through serialization.
    dumped = album.model_dump()
    assert all(track["disc_number"] == 1 for track in dumped["tracklist"])


def test_album_source_enum() -> None:
    """``AlbumSource`` accepts the three documented values and rejects junk.

    CR-001: ``SPOTIFY`` member dropped; ``DISCOGS`` replaces it.
    """
    for value in ("musicbrainz", "discogs", "manual"):
        album = _minimum_album(source=AlbumSource(value))
        assert album.source.value == value
    with pytest.raises(ValidationError):
        _minimum_album(source="spotify")  # CR-001: no longer a valid source
    with pytest.raises(ValidationError):
        _minimum_album(source="lastfm")  # not a valid AlbumSource


def test_artist_ref_subdoc() -> None:
    """``ArtistRefSubDoc`` accepts name-only artists; identifiers stay optional.

    CR-001: removed ``spotify_id`` assertions — artists are keyed on
    ``mbid`` only at MVP.
    """
    # Name-only construction is legal (manual-entry obscure album).
    bare = ArtistRefSubDoc(name="Some Indie Artist")
    assert bare.name == "Some Indie Artist"
    assert bare.mbid is None
    # Typical case: identifier populated.
    full = ArtistRefSubDoc(
        name="Mos Def",
        mbid="bf710b71-48e5-4e8e-b2c3-aaaaaaaaaaaa",
    )
    assert full.mbid is not None


def test_album_cache_expires_at_required() -> None:
    """Omitting ``cache_expires_at`` fails fast — no silent default to ``None``."""
    with pytest.raises(ValidationError) as excinfo:
        Album(
            title="Black on Both Sides",
            artist_credit="Mos Def",
            source=AlbumSource.MUSICBRAINZ,
        )
    # Surface the precise field name in the error so a regression that
    # accidentally relaxes the schema is easy to attribute.
    assert any(err["loc"] == ("cache_expires_at",) for err in excinfo.value.errors())


def test_album_default_collections_are_empty_not_shared() -> None:
    """``artists`` / ``tracklist`` / ``editions`` / ``genres`` default to fresh lists.

    Pinned because shared default-list bugs are notoriously easy to introduce
    when migrating between Pydantic versions or when refactoring Field()
    defaults — and the resulting cross-instance contamination is hard to
    diagnose in production.
    """
    a = _minimum_album()
    b = _minimum_album()
    a.artists.append(ArtistRefSubDoc(name="X"))
    a.tracklist.append(TrackSubDoc(position=1, title="t"))
    a.editions.append(EditionRefSubDoc(name="Deluxe"))
    a.genres.append("hip hop")
    assert b.artists == []
    assert b.tracklist == []
    assert b.editions == []
    assert b.genres == []


def test_album_release_date_preserves_granularity() -> None:
    """``release_date`` accepts a ``date`` while ``release_year`` denormalises year."""
    album = _minimum_album(release_date=date(1999, 10, 12), release_year=1999)
    assert album.release_date == date(1999, 10, 12)
    assert album.release_year == 1999
