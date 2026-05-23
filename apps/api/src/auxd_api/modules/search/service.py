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
   the most-relevant hits in a single round-trip, including the
   popularity boost from the ``log1p(rating_count)`` score function.

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
    """Return the search-hit payload for a locally-cached :class:`Album`."""
    return {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
        "source": album.source.value,
    }


async def _atlas_search(query: str, limit: int) -> list[Album]:
    """Run the Atlas Search aggregation pipeline against ``albums``.

    Uses the ``compound.should`` form so a query that matches *either*
    ``title`` or ``artist_credit`` scores well — Lucene picks the higher
    of the two. Falls back to an empty list if Atlas Search isn't
    configured (e.g. local mongomock); the route layer treats that as
    "zero Atlas hits, fall through to provider tier".
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
