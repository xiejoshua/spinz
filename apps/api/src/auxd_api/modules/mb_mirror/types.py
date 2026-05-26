"""Shared types for the MB mirror module.

A :class:`MirrorRow` is the projection of a MusicBrainz
release-group into the columns we actually query against. The shape
is deliberately narrow — anything past the columns listed here
would inflate Turso storage without buying us search/lookup value
the existing :class:`auxd_api.modules.albums.models.Album` document
doesn't already cover.

If we ever need a richer field (e.g. label, country, ISRC), add it
here, bump the schema version in :mod:`.schema`, and re-ingest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MirrorRow:
    """One release-group as stored in the mirror.

    ``genres`` is the comma-joined list of MB tags above the
    cutoff threshold (the ETL writer applies the cutoff so the
    read path doesn't have to parse). Pre-joining as a CSV
    string keeps the column simple in SQLite and matches the
    shape the frontend already expects from ``Album.genres``.
    """

    mbid: str
    title: str
    artist_credit: str
    release_year: int | None
    primary_type: str | None
    genres: str
    cover_art_url: str | None

    @property
    def genres_list(self) -> list[str]:
        """Parse the CSV genres field back into a list."""
        return [g for g in (self.genres or "").split(",") if g]
