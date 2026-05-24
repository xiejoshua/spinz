"""Search service layer (T069).

Wraps the Atlas Search aggregation pipeline + the Discogs-primary
external lookup into a single :func:`search_albums` entry point. The
route layer (:mod:`auxd_api.modules.search.routes`) is intentionally
thin — every piece of business logic lives here so the same flow can be
called from a future GraphQL surface, a CLI tool, or unit tests without
spinning up the FastAPI app.

Search-fix v4 (2026-05-24) — Discogs masters as the primary external
source. v2 (parallel MB + Discogs with cross-source bonus) and v3
(heuristic boosts + community.have enrichment) both failed on the
user's "Graduation" / "kanye west" queries because we were trying to
re-implement a relevance + popularity merge on top of two providers
that don't agree on identity. v4 drops the merge entirely: Discogs's
``type=master`` search ranks results by popularity + relevance
out-of-the-box (the same algorithm discogs.com uses), and we pass that
ordering through unchanged.

Three-tier flow:

1. **Atlas** — when the local catalog returns ``>=
   _FALLBACK_THRESHOLD`` hits, return them directly. Atlas is the
   cleanest source once the catalog populates with user activity and
   gets a query-time popularity boost from ``log1p(rating_count)``.

2. **Discogs masters (primary external source)** — pass Discogs's
   native ranking through unchanged. No heuristic boosts, no
   cross-source bonuses, no community.have enrichment layer. Each hit
   is materialised via :func:`resolve_identity` using
   ``discogs_master_id``.

3. **MusicBrainz (fallback only)** — query MB only when Discogs
   returned fewer than ``_FALLBACK_THRESHOLD`` hits combined with
   Atlas. Dedupes against the Discogs hits by ``(title, artist)``
   because MB carries MBIDs while Discogs masters do not, so the
   strong-key dedup can't cross sources.

Dedupe key is MBID when present, falling back to a casefolded
``title|artist`` tuple. The fallback key isn't perfect but is close
enough at MVP to eliminate the worst duplicates without sliding into
fuzzy-match territory.
"""

from __future__ import annotations

import logging
from typing import Any

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.identity import resolve_identity
from auxd_api.modules.albums.models import Album
from auxd_api.providers.base import CatalogProvider
from auxd_api.providers.errors import ProviderError

_LOGGER = logging.getLogger("auxd.search")

# Threshold for tier-2/3 activation: below this many cumulative hits
# we run the next tier. Atlas hits below the threshold trigger the
# Discogs master query; Atlas + Discogs hits still below the threshold
# trigger the MusicBrainz fallback.
_FALLBACK_THRESHOLD = 5

# Atlas Search index name — must match the ``name`` field in
# ``apps/api/migrations/atlas_search/albums_index.json``.
_ATLAS_INDEX = "albums_text_search"


def _dedupe_key(*, mbid: str | None, title: str, artist: str) -> str:
    """Return a stable dedupe key for a search hit.

    MBID, when present, is the strongest possible key. Otherwise we fall
    back to a casefolded ``title|artist`` tuple — close enough at MVP to
    eliminate the worst duplicates without sliding into fuzzy-match
    territory.

    Used in tandem with :func:`_dedupe_alias_keys`: every hit registers
    BOTH the strong (MBID-based) AND the weak (title/artist) key in the
    seen-set so cross-source dedup works correctly. A Discogs master hit
    (no MBID) and an MB hit (with MBID) for the same canonical album
    will dedupe via the shared title/artist key even though their
    strong keys differ.
    """
    if mbid:
        return f"mbid:{mbid}"
    return f"meta:{title.casefold()}|{artist.casefold()}"


def _dedupe_alias_keys(*, mbid: str | None, title: str, artist: str) -> list[str]:
    """Return every dedupe key that should be associated with a hit.

    Cross-source dedup between Atlas hits (which carry MBIDs +
    discogs_release_ids) and Discogs master hits (which carry
    ``discogs_master_id`` but no MBID) relies on registering BOTH
    keys when a hit is processed:

    * The strong (MBID) key catches future MB hits with the same MBID.
    * The weak (title/artist) key catches future Discogs hits that
      surface the same canonical album by a different identifier
      (master_id only, no MBID).

    When the strong key is the only one (MBID present), this returns
    both ``mbid:<id>`` AND ``meta:<title>|<artist>`` so a follow-up
    Discogs hit with the same album metadata is correctly skipped.
    When only the weak key is available (Discogs master hit, no MBID),
    this returns just the metadata form.
    """
    meta_key = f"meta:{title.casefold()}|{artist.casefold()}"
    if mbid:
        return [f"mbid:{mbid}", meta_key]
    return [meta_key]


def _serialize_album(album: Album) -> dict[str, Any]:
    """Return the search-hit payload for a locally-cached :class:`Album`.

    The DB column on :class:`Album` is ``artist_credit`` (matches the
    MusicBrainz vocabulary) but the API response key is ``artist_name``
    to match the frontend's ``SearchAlbum`` type. The two names existed
    in parallel until 2026-05-24 when the missing-artist UI bug was
    diagnosed — the response was serialising ``artist_credit`` and the
    React components were reading ``artist_name``, so the artist line
    rendered as ``undefined``. Pinning the response key to
    ``artist_name`` aligns serialiser → wire → component.
    """
    return {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_name": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
        "source": album.source.value,
    }


async def _atlas_search(query: str, limit: int) -> list[Album]:
    """Run the Atlas Search aggregation pipeline against ``albums``.

    Uses the ``compound.should`` form so a query that matches *either*
    ``title`` or ``artist_credit`` scores well — Lucene picks the higher
    of the two. A third ``function``-score clause adds a popularity
    boost driven by ``log1p(rating_count)`` so canonical, widely-rated
    releases sort ahead of obscure ones at equal text relevance. The
    ``boost.value`` of 2 keeps popularity within the same order of
    magnitude as the autocomplete clauses without overwhelming them
    (a perfect title-match still beats a popular near-miss).

    Falls back to an empty list if Atlas Search isn't configured (e.g.
    local mongomock); the route layer treats that as "zero Atlas hits,
    fall through to the external tiers". mongomock rejects the unknown
    ``$search`` operator, so the existing try/except continues to short
    out the whole pipeline — the popularity-boost clause is only ever
    evaluated against real Atlas in staging / prod.
    """
    pipeline: list[dict[str, Any]] = [
        {
            "$search": {
                "index": _ATLAS_INDEX,
                "compound": {
                    "should": [
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "title",
                                "tokenOrder": "any",
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "artist_credit",
                                "tokenOrder": "any",
                            }
                        },
                        {
                            "function": {
                                "score": {
                                    "function": {"log1p": {"path": {"value": "rating_count"}}}
                                },
                                "boost": {"value": 2},
                            }
                        },
                    ]
                },
            }
        },
        {"$limit": limit},
    ]
    try:
        rows: list[dict[str, Any]] = await Album.aggregate(pipeline).to_list()
    except Exception as exc:  # pragma: no cover - mongomock raises, real Atlas doesn't
        _LOGGER.info(
            "search.atlas_unavailable",
            extra={"event": "search.atlas_unavailable", "error": str(exc)},
        )
        return []
    # Beanie's aggregate returns raw dicts; coerce back into Album for
    # the dedupe/serialise step.
    return [Album.model_validate(row) for row in rows]


async def search_albums(
    *,
    query: str,
    limit: int,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
) -> list[dict[str, Any]]:
    """Two-tier search (with Atlas as a local-only tier-0).

    Tier 1 (Atlas): if Atlas returns ``>= _FALLBACK_THRESHOLD`` hits,
    return directly. Atlas is the cleanest source once the catalog
    populates.

    Tier 2 (Discogs masters): pass Discogs's native ranking through
    unchanged. Discogs's algorithm already factors in popularity +
    relevance — this IS the algorithm the user has endorsed. No merge
    layer, no heuristic boosts, no cross-source bonuses. Materialise
    each hit via :func:`resolve_identity` using ``discogs_master_id``.

    Tier 3 (MusicBrainz, fallback-only): query MB only when Atlas +
    Discogs returned fewer than ``_FALLBACK_THRESHOLD`` hits. Dedupes
    against existing hits by ``(title, artist)`` because MB carries
    MBIDs while Discogs masters do not.
    """
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    def _seen_any(keys: list[str]) -> bool:
        """True if any of the candidate keys is already in the seen-set."""
        return any(key in seen for key in keys)

    def _seen_add(keys: list[str]) -> None:
        """Register all dedupe keys for an accepted hit."""
        seen.update(keys)

    # ---- Tier 1: Atlas Search -----------------------------------------
    atlas_hits = await _atlas_search(query, limit)
    for album in atlas_hits:
        keys = _dedupe_alias_keys(
            mbid=album.mbid,
            title=album.title,
            artist=album.artist_credit,
        )
        if _seen_any(keys):
            continue
        _seen_add(keys)
        merged.append(_serialize_album(album))

    if len(merged) >= _FALLBACK_THRESHOLD:
        return merged

    # ---- Tier 2: Discogs masters (primary external source) ------------
    try:
        discogs_hits = await discogs_provider.search_albums(query, limit=limit)
    except ProviderError as exc:
        _LOGGER.warning(
            "search.discogs_error",
            extra={"event": "search.discogs_error", "error": str(exc)},
        )
        discogs_hits = []

    for hit in discogs_hits:
        keys = _dedupe_alias_keys(
            mbid=hit.mbid,
            title=hit.title,
            artist=hit.artist_name,
        )
        if _seen_any(keys):
            continue
        if not hit.discogs_master_id:
            # Master ID is required for materialisation; mark seen so an
            # MB hit with the same metadata can still process normally,
            # but skip emitting this hit.
            _seen_add(keys)
            continue
        try:
            album = await resolve_identity(
                discogs_master_id=hit.discogs_master_id,
                mb_provider=mb_provider,
                discogs_provider=discogs_provider,
            )
        except (AlbumNotFoundError, ProviderError) as exc:
            _LOGGER.info(
                "search.materialize_skipped",
                extra={"event": "search.materialize_skipped", "error": str(exc)},
            )
            continue
        # After materialise the row may carry an MBID (cross-cycle
        # reconciliation could have populated one). Register both the
        # incoming-hit keys AND the materialised album's keys so future
        # cross-source dedup catches both forms.
        album_keys = _dedupe_alias_keys(
            mbid=album.mbid,
            title=album.title,
            artist=album.artist_credit,
        )
        _seen_add(keys)
        _seen_add(album_keys)
        merged.append(_serialize_album(album))
        if len(merged) >= limit:
            return merged

    if len(merged) >= _FALLBACK_THRESHOLD:
        return merged

    # ---- Tier 3: MusicBrainz (fallback only) --------------------------
    try:
        mb_hits = await mb_provider.search_albums(query, limit=limit)
    except ProviderError as exc:
        _LOGGER.warning(
            "search.mb_error",
            extra={"event": "search.mb_error", "error": str(exc)},
        )
        mb_hits = []

    for hit in mb_hits:
        keys = _dedupe_alias_keys(
            mbid=hit.mbid,
            title=hit.title,
            artist=hit.artist_name,
        )
        if _seen_any(keys):
            continue
        if not hit.mbid:
            _seen_add(keys)
            continue
        try:
            album = await resolve_identity(
                mbid=hit.mbid,
                mb_provider=mb_provider,
                discogs_provider=discogs_provider,
            )
        except (AlbumNotFoundError, ProviderError) as exc:
            _LOGGER.info(
                "search.materialize_skipped",
                extra={"event": "search.materialize_skipped", "error": str(exc)},
            )
            continue
        album_keys = _dedupe_alias_keys(
            mbid=album.mbid,
            title=album.title,
            artist=album.artist_credit,
        )
        _seen_add(keys)
        _seen_add(album_keys)
        merged.append(_serialize_album(album))
        if len(merged) >= limit:
            return merged

    return merged


__all__ = ["search_albums"]
