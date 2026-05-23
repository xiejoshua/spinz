"""Album document model — canonical catalog cache.

The ``Album`` document is the identity anchor for every diary entry, review,
backlog item, and search hit in auxd. ``mbid`` (MusicBrainz release-group MBID)
is the canonical identifier when available; ``discogs_release_id`` is the
secondary fallback for brand-new releases not yet ingested by MusicBrainz.

Identity-resolution rules (data-model.md §"Album identity normalization"):

* Prefer ``mbid`` as the canonical key when present — it federates cleanly
  with the rest of the music metadata ecosystem.
* Fall back to ``discogs_release_id`` when ``mbid`` is unavailable.
* Both identifiers are stored as unique sparse indexes: at most one document
  may claim a given ``mbid`` (and likewise for ``discogs_release_id``), but
  documents may exist with neither populated (rare, but supported for
  manually-entered obscure albums — the Letterboxd-style manual-search
  catalog model the MVP adopted in CR-001).

The 7-day ``cache_expires_at`` window (plan §3.1) drives lazy refresh: when a
read path observes an expired record it re-fetches from MusicBrainz / Discogs
on the next request and updates the document in place. There is no nightly
batch — the workload is bursty around new releases and a TTL-driven sweep
would refresh albums no user is actually looking at.

Atlas Search (plan §11.1) covers free-text discovery. The index definition
lives outside this file at ``apps/api/migrations/atlas_search/albums_index.json``
and is applied once-per-cluster via the Atlas UI (MVP) — see that file's
README for the operational runbook.

CR-001 (2026-05-22): dropped Spotify identifiers from the album catalog
(``spotify_id`` on :class:`Album`, ``spotify_id`` on :class:`ArtistRefSubDoc`,
``spotify_track_id`` on :class:`TrackSubDoc`, ``spotify_id`` on
:class:`EditionRefSubDoc`, and the ``SPOTIFY`` member of :class:`AlbumSource`).
``discogs_release_id`` replaces the spotify-side identity on Album and is
sparse-unique indexed. See ``features/001-auxd-mvp/change-log.md``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from auxd_api.lib.ids import new_ksuid


class AlbumSource(StrEnum):
    """Provenance of the catalog record.

    Recorded for audit / debugging — knowing whether a particular album was
    seeded from MusicBrainz (URLs are immutable), Discogs (community-edited
    metadata), or a manual founder edit is decisive when triaging stale or
    incorrect rows.

    CR-001 (2026-05-22): removed the ``SPOTIFY`` member; the MVP no longer
    seeds catalog rows from Spotify. ``DISCOGS`` replaces it as the
    secondary-provider provenance marker.
    """

    MUSICBRAINZ = "musicbrainz"
    DISCOGS = "discogs"
    MANUAL = "manual"


class ArtistRefSubDoc(BaseModel):
    """Embedded artist reference inside an :class:`Album`.

    Kept structured (rather than a flat string) so Atlas Search can index
    ``artists.name`` independently of the denormalized ``artist_credit``
    display string. In practice ``mbid`` should usually be populated, but
    we don't enforce that here: manually-entered albums may legitimately
    have only a free-text artist name.

    CR-001 (2026-05-22): removed ``spotify_id`` — the MVP no longer carries
    Spotify identifiers. Future Discogs artist linkage will arrive as
    ``discogs_artist_id`` in a follow-up change.
    """

    mbid: str | None = None
    name: str


class TrackSubDoc(BaseModel):
    """Embedded track row inside :class:`Album.tracklist`.

    Tracklist is denormalized into the album document at MVP (data-model.md
    DM-4). If album docs grow past ~20KB we'll promote tracks to their own
    collection — until then the embedded form keeps the album-detail page a
    single document read.

    CR-001 (2026-05-22): removed ``spotify_track_id`` — the MVP carries
    only the MusicBrainz ``mbid`` for tracks.
    """

    position: int
    """1-indexed position within the album (disc-local; pair with ``disc_number``)."""

    disc_number: int = 1
    """Disc number for multi-disc releases; defaults to ``1`` (single disc)."""

    title: str
    duration_ms: int | None = None
    mbid: str | None = None


class EditionRefSubDoc(BaseModel):
    """Reference to a sibling release in the same MusicBrainz release-group.

    Editions surface in the UI as "Also available: Deluxe Edition / Bonus
    Tracks / Anniversary Remaster" so users can pick which pressing they
    actually listened to. The references are lightweight pointers — the
    target editions are themselves full :class:`Album` documents.

    CR-001 (2026-05-22): removed ``spotify_id`` — editions are keyed on
    ``mbid`` only at MVP.
    """

    name: str
    """Human-readable edition label, e.g. ``"Deluxe Edition"`` or ``"Bonus Tracks"``."""

    mbid: str | None = None


class Album(Document):
    """Canonical album record (catalog cache).

    Indexes (plan §3.1 row ``albums``):

    * ``mbid`` — unique sparse (MusicBrainz canonical identifier).
    * ``discogs_release_id`` — unique sparse (Discogs fallback identifier).
    * ``cache_expires_at`` — sparse, drives lazy refresh sweeps.
    * ``popularity_score`` — descending, supports search-ranking boosts and
      "popular albums" carousels.
    * Atlas Search index on ``title`` + ``artist_credit`` + ``artists.name``
      is defined separately in ``apps/api/migrations/atlas_search/albums_index.json``
      and applied via Atlas UI (one-time, per cluster).

    CR-001 (2026-05-22): replaced ``spotify_id`` (and its sparse-unique
    index) with ``discogs_release_id``.
    """

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    """KSUID primary key — chronologically sortable string of length 27."""

    schema_version: int = Field(default=1, alias="_schema_version")
    """Document schema version; readers tolerate ``current`` and ``current - 1``."""

    mbid: str | None = None
    """MusicBrainz release-group MBID — canonical identifier when available."""

    discogs_release_id: str | None = None
    """Discogs release ID — secondary fallback when MBID is unavailable (CR-001)."""

    title: Indexed(str)  # type: ignore[valid-type]
    """Album title; indexed (single-field) to support prefix lookups."""

    artist_credit: str
    """Display string for the artist line, e.g. ``"Mos Def & Talib Kweli"``."""

    artists: list[ArtistRefSubDoc] = Field(default_factory=list)
    """Structured artist references — feeds Atlas Search ``artists.name`` field."""

    release_date: date | None = None
    """Calendar release date when known; granularity preserved at write time."""

    release_year: int | None = None
    """Denormalized year extracted from ``release_date`` for cheap indexing / sort."""

    cover_art_url: str | None = None
    """Primary cover-art URL (CDN-hosted at MVP; MusicBrainz/Cover Art Archive by default)."""

    tracklist: list[TrackSubDoc] = Field(default_factory=list)
    """Ordered tracks; embedded at MVP (DM-4) — promote to own collection if >20KB."""

    duration_ms: int | None = None
    """Total album duration in milliseconds; sum of track durations when computable."""

    label: str | None = None
    """Record label name (e.g. ``"Rawkus Records"``); free-text, not normalized at MVP."""

    genres: list[str] = Field(default_factory=list)
    """Free-text genre tags; provider-supplied (MusicBrainz/Discogs) or curator-edited (manual)."""

    editions: list[EditionRefSubDoc] = Field(default_factory=list)
    """Release-group siblings (Standard / Deluxe / Bonus); displayed in detail view."""

    popularity_score: float = 0.0
    """0–100 popularity; recomputed offline. Drives Atlas Search ranking boosts."""

    source: AlbumSource
    """Which provider seeded this record (audit field; ``MANUAL`` for founder edits)."""

    cache_expires_at: datetime
    """Lazy-refresh marker (7-day window per plan); records past TTL are re-fetched on read."""

    # T063: ``candidate`` marks Discogs-sourced rows that still need MBID
    # reconciliation by the T065 worker. A ``True`` value means the record
    # was materialised via the Discogs fallback path (no MBID yet) and
    # should be retried against MusicBrainz on a weekly schedule.
    candidate: bool = False
    """``True`` when this album was seeded via Discogs and still awaits MBID reconciliation."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        """Beanie collection settings — name, indexes, and serialization options."""

        name = "albums"
        # CR-001: replaced the ``spotify_id`` sparse-unique index with
        # ``discogs_release_id``.
        indexes = [
            IndexModel([("mbid", ASCENDING)], unique=True, sparse=True),
            IndexModel([("discogs_release_id", ASCENDING)], unique=True, sparse=True),
            IndexModel([("cache_expires_at", ASCENDING)], sparse=True),
            IndexModel([("popularity_score", DESCENDING)]),
        ]


__all__ = [
    "Album",
    "AlbumSource",
    "ArtistRefSubDoc",
    "EditionRefSubDoc",
    "TrackSubDoc",
]
