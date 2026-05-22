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
    """Both ``mbid`` and ``spotify_id`` may be ``None`` (rare but supported)."""
    album = _minimum_album()
    assert album.mbid is None
    assert album.spotify_id is None
    # Either alone is fine.
    only_mbid = _minimum_album(mbid="3f7d5b4e-1234-5678-9abc-def012345678")
    assert only_mbid.mbid is not None
    assert only_mbid.spotify_id is None
    only_spotify = _minimum_album(spotify_id="3T4tUhGYeRNVUGevb0wThu")
    assert only_spotify.mbid is None
    assert only_spotify.spotify_id is not None


def test_album_with_tracklist() -> None:
    """An ``Album`` with embedded :class:`TrackSubDoc` rows round-trips through JSON."""
    tracks = [
        TrackSubDoc(position=1, title="Fear Not of Man", duration_ms=283000),
        TrackSubDoc(position=2, title="Hip Hop", duration_ms=337000),
        TrackSubDoc(
            position=3,
            title="Love",
            duration_ms=234000,
            spotify_track_id="0Ix9X0e9tQK4Y4VqkP5bJL",
        ),
    ]
    album = _minimum_album(tracklist=tracks)
    assert len(album.tracklist) == 3
    assert album.tracklist[0].position == 1
    assert album.tracklist[2].spotify_track_id == "0Ix9X0e9tQK4Y4VqkP5bJL"
    # Default disc_number = 1 must round-trip through serialization.
    dumped = album.model_dump()
    assert all(track["disc_number"] == 1 for track in dumped["tracklist"])


def test_album_source_enum() -> None:
    """``AlbumSource`` accepts the three documented values and rejects junk."""
    for value in ("spotify", "musicbrainz", "manual"):
        album = _minimum_album(source=AlbumSource(value))
        assert album.source.value == value
    with pytest.raises(ValidationError):
        _minimum_album(source="lastfm")  # not a valid AlbumSource


def test_artist_ref_subdoc() -> None:
    """``ArtistRefSubDoc`` accepts name-only artists; identifiers stay optional."""
    # Name-only construction is legal (manual-entry obscure album).
    bare = ArtistRefSubDoc(name="Some Indie Artist")
    assert bare.name == "Some Indie Artist"
    assert bare.mbid is None
    assert bare.spotify_id is None
    # Typical case: at least one identifier populated.
    full = ArtistRefSubDoc(
        name="Mos Def",
        mbid="bf710b71-48e5-4e8e-b2c3-aaaaaaaaaaaa",
        spotify_id="0eDvMgVFoNV3TpwtrVCoTj",
    )
    assert full.mbid is not None
    assert full.spotify_id is not None


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
