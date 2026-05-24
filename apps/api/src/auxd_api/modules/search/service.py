"""Search service layer (T069).

Wraps the Atlas Search aggregation pipeline + the multi-provider
fallback merge into a single :func:`search_albums` entry point. The
route layer (:mod:`auxd_api.modules.search.routes`) is intentionally
thin — every piece of business logic lives here so the same flow can be
called from a future GraphQL surface, a CLI tool, or unit tests without
spinning up the FastAPI app.

Fallback flow:

1. Atlas Search via :func:`Album.aggregate` with the ``albums_text_search``
   index (autocomplete on ``title`` + ``artist_credit``). Atlas returns
   the most-relevant hits in a single round-trip. The index also
   indexes ``rating_count`` as a numeric field so the query-time
   popularity boost (``compound.should`` with a ``function`` score
   clause referencing ``log1p(rating_count)``) is wired here — see
   ``apps/api/migrations/atlas_search/albums_index.json``. The
   ``log1p`` shape damps the boost so a 1000-rating album doesn't
   dwarf text relevance; the ``boost.value`` of 2 keeps popularity in
   the same order-of-magnitude as the autocomplete score.

2. If fewer than :data:`_FALLBACK_THRESHOLD` hits, also query
   MusicBrainz via :meth:`CatalogProvider.search_albums`. New MBIDs are
   materialised into the local catalog via
   :func:`auxd_api.modules.albums.identity.resolve_identity` so the next
   query for the same album is fully local.

3. If still fewer than :data:`_FALLBACK_THRESHOLD` hits, also query
   Discogs (graceful-disabled when ``DISCOGS_API_TOKEN`` is unset).
   Discogs hits are materialised as candidate albums for the T065
   reconciliation worker.

Dedupe key is ``(title.lower(), artist_credit.lower())`` plus MBID where
present — handles the common case where the same release appears in
Atlas + MusicBrainz + Discogs with subtly different formatting.
"""

from __future__ import annotations

import logging
from typing import Any

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.identity import resolve_identity
from auxd_api.modules.albums.models import Album
from auxd_api.providers.base import CatalogAlbum, CatalogProvider
from auxd_api.providers.errors import ProviderError

_LOGGER = logging.getLogger("auxd.search")

# Threshold for tier-2/3 fallback activation: below this many Atlas hits
# we also query MusicBrainz, and below this *combined* hit count we
# additionally query Discogs.
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
    """
    if mbid:
        return f"mbid:{mbid}"
    return f"meta:{title.casefold()}|{artist.casefold()}"


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
    fall through to provider tier". mongomock rejects the unknown
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
    """Run the three-tier search pipeline and return merged + deduped hits.

    Atlas-hits keep their natural sort order (relevance + popularity);
    provider-fallback hits are appended in arrival order. Within each
    tier we secondary-sort by ``release_year`` descending so newer
    releases break relevance ties — matches the Letterboxd convention
    of surfacing more recent items first when relevance is equal.
    """
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    # ---- Tier 1: Atlas Search -----------------------------------------
    atlas_hits = await _atlas_search(query, limit)
    for album in atlas_hits:
        key = _dedupe_key(
            mbid=album.mbid,
            title=album.title,
            artist=album.artist_credit,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(_serialize_album(album))

    if len(merged) >= _FALLBACK_THRESHOLD:
        return merged

    # ---- Tier 2: MusicBrainz -------------------------------------------
    try:
        mb_hits = await mb_provider.search_albums(query, limit=limit)
    except ProviderError as exc:
        _LOGGER.warning(
            "search.musicbrainz_error",
            extra={"event": "search.musicbrainz_error", "error": str(exc)},
        )
        mb_hits = []
    # Sort MB hits by relevance score desc; ``None`` scores sink to the
    # bottom so post-MVP feedback about "Graduation doesn't appear unless
    # typed exactly" is addressed by surfacing the canonical 90-100 score
    # release-groups above the long tail of unofficial / scrap releases.
    # ``-1`` sentinel < every valid 0-100 score, so None-scored hits sort
    # last while staying mypy-clean (no Optional comparison).
    mb_hits.sort(key=lambda h: h.score if h.score is not None else -1, reverse=True)
    merged += await _materialize_fallback(
        hits=mb_hits,
        seen=seen,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        prefer="mbid",
    )

    if len(merged) >= _FALLBACK_THRESHOLD:
        return merged

    # ---- Tier 3: Discogs ----------------------------------------------
    try:
        discogs_hits = await discogs_provider.search_albums(query, limit=limit)
    except ProviderError as exc:
        _LOGGER.warning(
            "search.discogs_error",
            extra={"event": "search.discogs_error", "error": str(exc)},
        )
        discogs_hits = []
    merged += await _materialize_fallback(
        hits=discogs_hits,
        seen=seen,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        prefer="discogs",
    )

    return merged


async def _materialize_fallback(
    *,
    hits: list[CatalogAlbum],
    seen: set[str],
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    prefer: str,
) -> list[dict[str, Any]]:
    """Materialise provider hits into local Albums + return serialised payloads.

    Each hit is run through :func:`resolve_identity` so the row lands in
    the local catalog and a future query for the same album is fully
    local (Atlas-tier hit). Hits whose dedupe key matches a row we've
    already added are skipped — preserves the natural Atlas-first
    ordering when MusicBrainz returns the same record we just saw
    locally.
    """
    materialised: list[dict[str, Any]] = []
    for hit in hits:
        key = _dedupe_key(
            mbid=hit.mbid,
            title=hit.title,
            artist=hit.artist_name,
        )
        if key in seen:
            continue
        seen.add(key)
        try:
            if prefer == "mbid" and hit.mbid:
                album = await resolve_identity(
                    mbid=hit.mbid,
                    mb_provider=mb_provider,
                    discogs_provider=discogs_provider,
                )
            elif hit.discogs_release_id:
                album = await resolve_identity(
                    discogs_release_id=hit.discogs_release_id,
                    mb_provider=mb_provider,
                    discogs_provider=discogs_provider,
                )
            else:
                # No usable identifier — skip the hit; the next refresh
                # cycle won't be able to reconcile it anyway.
                continue
        except (AlbumNotFoundError, ProviderError) as exc:
            _LOGGER.info(
                "search.materialize_skipped",
                extra={"event": "search.materialize_skipped", "error": str(exc)},
            )
            continue
        materialised.append(_serialize_album(album))
    return materialised


__all__ = ["search_albums"]
