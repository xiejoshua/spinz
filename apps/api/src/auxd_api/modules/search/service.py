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

import asyncio
import json
import logging
import random
import re
from typing import Any

from beanie.odm.enums import SortDirection

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.identity import (
    _materialize_album_from_mirror,
    resolve_identity,
)
from auxd_api.modules.albums.models import Album
from auxd_api.modules.mb_mirror.service import AlbumMirrorService
from auxd_api.modules.mb_mirror.types import MirrorRow
from auxd_api.providers.base import CatalogProvider
from auxd_api.providers.errors import ProviderError
from auxd_api.redis_client import cache_get, cache_set

_LOGGER = logging.getLogger("auxd.search")

# Threshold for tier-2/3 activation: below this many cumulative hits
# we run the next tier. Atlas hits below the threshold trigger the
# Discogs master query; Atlas + Discogs hits still below the threshold
# trigger the MusicBrainz fallback.
_FALLBACK_THRESHOLD = 5

# Atlas Search index name — must match the ``name`` field in
# ``apps/api/migrations/atlas_search/albums_index.json``.
_ATLAS_INDEX = "albums_text_search"

# Cache lifetime for the 3-tier merged-candidate set. The /search route
# fetches up to 50 candidates per (query, type) and then narrows them
# in-process via decade/year/genre/sort filters. The slow part is the
# Discogs + MusicBrainz fallback (~1–25s on cold path); filters change
# constantly while the user iterates, so we cache the candidate list
# under the query and reuse it for every subsequent filter combination.
_CANDIDATES_CACHE_TTL = 5 * 60

# Composite reranker tuning (feature 004) — module constants so they're
# easy to revisit post-beta without redeploying behaviour through env
# vars. ``_ARTIST_MATCH_BOOST`` lifts candidates whose artist tokens
# cover the query well; ``_TIEBREAK_BAND`` is documentary only — the
# (composite_score desc, rating_count desc) sort resolves equal-score
# bands naturally without a separate proximity check.
_ARTIST_MATCH_BOOST = 10.0
_TIEBREAK_BAND = 0.05
_TOKEN_COVERAGE_THRESHOLD = 0.80
_STOPWORDS = frozenset({"the", "a", "an", "and", "&"})

# Hard ceiling on the result count we report to the client (FR-008).
# Matches the mirror's own cap so the two layers agree on the wire shape.
_TOTAL_DISPLAY_CAP = 10_000

# Process-wide latch — Atlas Search isn't configured on local MongoDB
# (the ``$search`` operator only exists on Atlas tiers M0+ with a
# Search index defined). When we detect that, every subsequent
# ``_atlas_search`` call returns [] silently instead of logging
# 371× per seed-pipeline run. The latch resets on process restart so
# a freshly-deployed Atlas index picks up automatically.
_ATLAS_DISABLED = False


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


def _serialize_album(
    album: Album,
    *,
    relevance_rank: int | None = None,
) -> dict[str, Any]:
    """Return the search-hit payload for a locally-cached :class:`Album`.

    The DB column on :class:`Album` is ``artist_credit`` (matches the
    MusicBrainz vocabulary) but the API response key is ``artist_name``
    to match the frontend's ``SearchAlbum`` type. The two names existed
    in parallel until 2026-05-24 when the missing-artist UI bug was
    diagnosed — the response was serialising ``artist_credit`` and the
    React components were reading ``artist_name``, so the artist line
    rendered as ``undefined``. Pinning the response key to
    ``artist_name`` aligns serialiser → wire → component.

    ``rating_count`` and ``created_at`` ride alongside as platform
    signals the post-filter sort step needs (``popular_on_auxd``
    sorts on the former, ``recently_added`` on the latter). Both
    survive the JSON round trip through Redis cache because
    ``created_at`` is emitted as an ISO string.

    ``relevance_rank`` (feature 004) is the row's index in the
    mirror's BM25-ranked result list. The composite reranker reads
    it back from the cached payload so a cache hit doesn't lose the
    relevance order. Frontend ignores the underscore-prefixed key.
    """
    payload: dict[str, Any] = {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_name": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
        "genres": list(album.genres),
        "source": album.source.value,
        "rating_count": getattr(album, "rating_count", 0) or 0,
        "created_at": album.created_at.isoformat() if album.created_at else None,
    }
    if relevance_rank is not None:
        payload["_relevance_rank"] = relevance_rank
    return payload


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
    # Short-circuit when a prior call already discovered the cluster
    # lacks Atlas Search. Saves the round trip + the log spam on every
    # subsequent query. The latch is process-scoped so a redeploy
    # with a freshly-provisioned index resets it.
    global _ATLAS_DISABLED
    if _ATLAS_DISABLED:
        return []

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
        # First failure: log once at INFO with a clear "this is expected
        # in local dev" rationale. Flip the latch so subsequent calls
        # short-circuit silently.
        _ATLAS_DISABLED = True
        _LOGGER.info(
            "search.atlas_unavailable",
            extra={
                "event": "search.atlas_unavailable",
                "error": str(exc),
                "note": (
                    "Atlas $search not available on this cluster — disabling "
                    "for the lifetime of this process. Searches will fall "
                    "through to Discogs + MusicBrainz tiers as designed. "
                    "Expected when running against local MongoDB; on Atlas, "
                    "verify the 'albums_text_search' index is provisioned."
                ),
            },
        )
        return []
    # Beanie's aggregate returns raw dicts; coerce back into Album for
    # the dedupe/serialise step.
    return [Album.model_validate(row) for row in rows]


async def _resolve_or_materialise_mirror_row(row: MirrorRow) -> Album:
    """Return the local :class:`Album` for a mirror row, materialising it
    on first sight.

    The mirror tier (tier 0 in :func:`search_albums` + the analogous
    branch in :func:`filter_only_search`) returns lightweight
    :class:`MirrorRow` dataclasses with just enough metadata to render
    a search-result card. Downstream code (serialisers, log/review
    routes, the album-detail page) all key off
    :class:`auxd_api.modules.albums.models.Album` documents, so each
    mirror hit needs a real Album row.

    First call: insert; subsequent calls: return cached row. Dedupes
    by MBID so concurrent searches that surface the same row don't
    insert duplicates (the existing ``Album.mbid`` unique sparse index
    would reject the duplicate anyway, but we'd rather avoid the
    write attempt).
    """
    cached = await Album.find_one(Album.mbid == row.mbid)
    if cached is not None:
        return cached
    album = _materialize_album_from_mirror(row)
    await album.insert()
    return album


def _candidates_cache_key(query: str) -> str:
    # v3 bumped 2026-05-26 (feature 004): ``_serialize_album`` now
    # carries an optional ``_relevance_rank`` so the composite
    # reranker can survive a cache hit. Old v2 payloads lack the
    # field; this bump invalidates them automatically.
    return f"search:candidates:v3:album:{query.strip().lower()}"


async def search_albums_cached(
    *,
    query: str,
    limit: int,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    mirror_service: AlbumMirrorService | None = None,
) -> list[dict[str, Any]]:
    """Cached entry point for the merged candidate fetch.

    Reuses the merged candidate list across requests with the same
    ``query`` so changing filters / sort / pagination does not re-run
    the slow Discogs + MusicBrainz fallback path (which can take 1–25s
    on a cold query). Cache TTL is :data:`_CANDIDATES_CACHE_TTL`.

    The MB mirror is consulted via :func:`search_albums` (tier 0) on
    cache misses; threaded through so cache misses still benefit from
    the mirror speed-up. Mirror hits + the downstream tiers produce
    one merged list that's cached as a unit.

    Falls open if Redis is unavailable: a cache miss runs the real
    fetch and silently fails to write back, so the request still
    succeeds.
    """
    key = _candidates_cache_key(query)
    cached = await cache_get(key)
    if cached is not None:
        try:
            payload = json.loads(cached)
            if isinstance(payload, list):
                return payload[:limit]
        except (json.JSONDecodeError, ValueError):
            _LOGGER.info(
                "search.candidates.cache_parse_error",
                extra={"event": "search.candidates.cache_parse_error"},
            )
    results = await search_albums(
        query=query,
        limit=limit,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror_service,
    )
    await cache_set(key, json.dumps(results), ex_seconds=_CANDIDATES_CACHE_TTL)
    return results


def _build_filter_only_match(
    *,
    year_min: int | None,
    year_max: int | None,
    decade_buckets: set[int] | None,
    genre: str | None,
    require_cover: bool,
) -> dict[str, Any]:
    """Compose the Mongo match clause for filter-only browse mode.

    Pushes every filter down to the DB layer so the count + paginate
    can be done natively (catalog browse needs true totals, not a
    50-row in-memory cap). Decade buckets become an ``$or`` of
    inclusive year ranges, each intersected with any global
    ``year_min`` / ``year_max`` constraint. Genre is a regex against
    the ``Album.genres`` array. ``require_cover`` filters to docs
    with at least one of ``mbid`` / ``cover_art_url`` populated.

    Returns ``{}`` (match-everything) when no filters are set, or
    ``{"_id": "__never__"}`` when the decade-buckets-vs-year-range
    intersection is empty (yields zero results without a real query).
    """
    clauses: list[dict[str, Any]] = []

    # Year + decade ranges, intersected.
    if decade_buckets:
        ranges: list[dict[str, Any]] = []
        for decade_start in sorted(decade_buckets):
            eff_min = decade_start if year_min is None else max(decade_start, year_min)
            eff_max = decade_start + 9 if year_max is None else min(decade_start + 9, year_max)
            if eff_min > eff_max:
                continue
            ranges.append({"release_year": {"$gte": eff_min, "$lte": eff_max}})
        if not ranges:
            return {"_id": "__never__"}
        clauses.append(ranges[0] if len(ranges) == 1 else {"$or": ranges})
    elif year_min is not None or year_max is not None:
        year_clause: dict[str, int] = {}
        if year_min is not None:
            year_clause["$gte"] = year_min
        if year_max is not None:
            year_clause["$lte"] = year_max
        clauses.append({"release_year": year_clause})

    if genre:
        # Mongo regex against an array field implicitly checks every
        # element; one of the strings in ``Album.genres`` only needs
        # to contain the substring.
        clauses.append({"genres": {"$regex": re.escape(genre), "$options": "i"}})

    if require_cover:
        clauses.append(
            {
                "$or": [
                    {"mbid": {"$ne": None}},
                    {"cover_art_url": {"$ne": None}},
                ]
            }
        )

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _filter_only_sort_spec(sort_key: str) -> list[tuple[str, SortDirection]]:
    """Translate a UI sort key into a Mongo sort spec for filter-only mode."""
    if sort_key == "year_newest":
        return [("release_year", SortDirection.DESCENDING)]
    if sort_key == "year_oldest":
        return [("release_year", SortDirection.ASCENDING)]
    if sort_key == "recently_added":
        return [("created_at", SortDirection.DESCENDING)]
    if sort_key == "popular_on_auxd":
        return [
            ("rating_count", SortDirection.DESCENDING),
            ("created_at", SortDirection.DESCENDING),
        ]
    # ``relevance`` (and anything unexpected) falls back to platform-
    # popular ordering when there's no query to score against.
    return [
        ("rating_count", SortDirection.DESCENDING),
        ("created_at", SortDirection.DESCENDING),
    ]


async def filter_only_search(
    *,
    year_min: int | None,
    year_max: int | None,
    decade_buckets: set[int] | None,
    genre: str | None,
    require_cover: bool,
    sort_key: str,
    limit: int,
    offset: int,
    mirror_service: AlbumMirrorService | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Browse-by-filter search.

    When ``mirror_service`` is enabled (and ``require_cover`` is not
    set — the mirror doesn't carry cover_art_url today), we query the
    Turso mirror's ~1.3M-row catalog. That turns the "browse 2010s
    albums" interaction from "~5 results from our seed catalog" into
    "1000s of results spanning the whole decade." Mirror hits
    materialise into the local ``albums`` collection lazily as
    serialisation walks the page, so on a second browse of the same
    slice they short-circuit at the Mongo cache.

    When ``mirror_service`` is disabled OR ``require_cover`` is True
    (cover-art filtering needs metadata the mirror doesn't store), we
    fall back to the original Mongo-only path. Same behaviour as
    pre-mirror; nothing changes for those code paths.

    Returns ``(page, total)``. ``surprise`` returns a single random
    page and reports ``len(page)`` as total (no pagination concept).
    """
    # Mirror-backed path: only when the service is wired in AND the
    # caller hasn't asked for cover-art filtering. The cover_art_url
    # column is null in the mirror today, so ``require_cover`` would
    # filter everything out — Mongo is the correct source for that
    # use case (its rows have cover URLs hydrated by past activity).
    if mirror_service is not None and mirror_service.enabled and not require_cover:
        rows, total = await mirror_service.filter_search(
            year_min=year_min,
            year_max=year_max,
            decade_buckets=decade_buckets,
            genre=genre,
            sort_key=sort_key,
            limit=limit,
            offset=offset,
        )
        page: list[dict[str, Any]] = []
        for row in rows:
            album = await _resolve_or_materialise_mirror_row(row)
            page.append(_serialize_album(album))
        return page, total

    # Pre-mirror Mongo-only path. Untouched semantics.
    match = _build_filter_only_match(
        year_min=year_min,
        year_max=year_max,
        decade_buckets=decade_buckets,
        genre=genre,
        require_cover=require_cover,
    )

    # Surprise me — defer to Mongo $sample so the random pick happens
    # at the database tier (no full collection scan into Python).
    if sort_key == "surprise":
        pipeline: list[dict[str, Any]] = []
        if match:
            pipeline.append({"$match": match})
        pipeline.append({"$sample": {"size": limit}})
        rows_dict = await Album.aggregate(pipeline).to_list()
        page = [_serialize_album(Album.model_validate(row)) for row in rows_dict]
        return page, len(page)

    sort_spec = _filter_only_sort_spec(sort_key)
    total = await Album.find(match).count()
    cursor = Album.find(match).sort(sort_spec).skip(offset).limit(limit)
    rows_local = await cursor.to_list()
    return [_serialize_album(album) for album in rows_local], total


async def search_albums(
    *,
    query: str,
    limit: int,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    mirror_service: AlbumMirrorService | None = None,
) -> list[dict[str, Any]]:
    """Search with a tiered fallback chain.

    Tier 0 (MB mirror, NEW): when ``mirror_service`` is supplied + enabled,
    we hit the Turso libSQL mirror's FTS5 index first. A populated mirror
    answers ~95% of "by title / by artist" queries in <10ms without any
    provider round-trip. Mirror hits materialise into the local ``albums``
    collection directly (no MB API call needed — the mirror IS the MB data).

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

    Backward compatibility: ``mirror_service`` defaults to ``None`` so
    every existing caller (catalog-seed CLI, worker, tests) continues
    to behave exactly as it did pre-mirror.
    """
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    def _seen_any(keys: list[str]) -> bool:
        """True if any of the candidate keys is already in the seen-set."""
        return any(key in seen for key in keys)

    def _seen_add(keys: list[str]) -> None:
        """Register all dedupe keys for an accepted hit."""
        seen.update(keys)

    # ---- Tier 0: MB mirror (Turso libSQL FTS5) -----------------------
    # Hit the mirror first when configured. Mirror hits are dramatically
    # cheaper than the rest of the pipeline (sub-10ms vs ~1-25s) AND
    # materialise into the local catalog as ``source=MUSICBRAINZ`` so
    # later tiers' dedup naturally suppresses re-emission via the
    # already-cached MBID key.
    if mirror_service is not None and mirror_service.enabled:
        mirror_rows = await mirror_service.search_text(query, limit=limit)
        for row in mirror_rows:
            album = await _resolve_or_materialise_mirror_row(row)
            keys = _dedupe_alias_keys(
                mbid=album.mbid,
                title=album.title,
                artist=album.artist_credit,
            )
            if _seen_any(keys):
                continue
            _seen_add(keys)
            merged.append(_serialize_album(album))

        if len(merged) >= limit:
            # Mirror answered the full request; skip the slower tiers.
            return merged[:limit]

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


# ---------------------------------------------------------------------------
# Approach C — browse-time external probing (003 / catalog growth)
# ---------------------------------------------------------------------------

# Trigger threshold: probe external providers when the local filter-only
# total is below this. Catalogs become "good enough" once a decade or
# genre has ~30+ matching albums; below that the page feels thin and the
# user is more likely to keep clicking around looking for more.
_PROBE_THRESHOLD = 30

# Hard wall-clock cap on a single probe. Discogs masters search typically
# returns in 200-800ms; a 3s ceiling catches the worst-case provider
# wobble without blocking the request lifecycle indefinitely (the probe
# runs as a FastAPI BackgroundTask AFTER the response is sent, so this
# also bounds how long a worker thread stays committed to the task).
_PROBE_TIMEOUT_S = 3.0

# Cache key for "we already probed this filter combo recently" so a user
# clicking through the same decade/genre doesn't trigger N redundant
# Discogs calls. 1h TTL keeps the cache responsive to a quarterly seed
# while not hammering the provider on every page view.
_PROBE_CACHE_TTL = 60 * 60


def _probe_cache_key(*, decade_buckets: set[int] | None, genre: str | None) -> str:
    """Stable cache key for a probe across (decade_buckets, genre) tuples."""
    decade_part = ",".join(str(d) for d in sorted(decade_buckets or [])) or "_"
    genre_part = (genre or "_").lower()
    return f"catalog_probe:v1:{decade_part}:{genre_part}"


async def probe_external_for_filters(
    *,
    decade_buckets: set[int] | None,
    genre: str | None,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    local_total: int,
) -> bool:
    """Approach C — best-effort catalog growth via Discogs probing.

    Runs when the filter-only result count is thin (< ``_PROBE_THRESHOLD``)
    and there's a hint we can turn into a free-text query. The probe
    re-uses :func:`search_albums` so the existing 3-tier merge does the
    materialisation through ``resolve_identity`` — newly-found albums
    show up on the *next* browse of this filter combo (this request
    returns whatever's already local).

    Returns ``True`` when a probe actually fired, ``False`` otherwise
    (so the route can log telemetry). Idempotent + bounded: each
    (decade, genre) tuple probes at most once per
    :data:`_PROBE_CACHE_TTL`, and each probe is hard-capped by
    :data:`_PROBE_TIMEOUT_S` wall-clock.

    Designed to be invoked as a FastAPI ``BackgroundTasks.add_task``
    callable — failures are swallowed (logged + Sentry-tagged) rather
    than bubbled up, because the user's response has already been
    sent by the time this runs.
    """
    if local_total >= _PROBE_THRESHOLD:
        return False
    # Genre is currently the only filter we can convert to a Discogs
    # search query cleanly (year-only probes would need a structured
    # search the provider doesn't expose). Skip when there's nothing
    # to query against.
    if not genre or not genre.strip():
        return False

    cache_key = _probe_cache_key(decade_buckets=decade_buckets, genre=genre)
    if await cache_get(cache_key) is not None:
        return False
    # Plant the cache key BEFORE the probe so a duplicate concurrent
    # request short-circuits — the work below mutates the local catalog,
    # so racing two probes for the same key would just be wasted IO.
    await cache_set(cache_key, "1", ex_seconds=_PROBE_CACHE_TTL)

    try:
        async with asyncio.timeout(_PROBE_TIMEOUT_S):
            await search_albums(
                query=genre.strip(),
                limit=20,
                mb_provider=mb_provider,
                discogs_provider=discogs_provider,
            )
    except (TimeoutError, ProviderError) as exc:
        # Best-effort: thin local catalog stays as-is until the next
        # probe window. Log so a misbehaving provider shows up in the
        # error budget.
        _LOGGER.info(
            "catalog_probe.degraded",
            extra={
                "event": "catalog_probe.degraded",
                "genre": genre,
                "error": str(exc),
            },
        )
        return False
    except Exception as exc:  # noqa: BLE001 — background-task discipline
        _LOGGER.warning(
            "catalog_probe.failed",
            extra={
                "event": "catalog_probe.failed",
                "genre": genre,
                "error": repr(exc),
            },
        )
        return False

    _LOGGER.info(
        "catalog_probe.completed",
        extra={
            "event": "catalog_probe.completed",
            "genre": genre,
            "local_total_before": local_total,
        },
    )
    return True


# ---------------------------------------------------------------------------
# Composite reranker (feature 004)
# ---------------------------------------------------------------------------


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    """Casefold + word-extract + strip stopwords.

    Uses ``\\w+`` to extract alphanumeric runs so punctuation doesn't
    glue onto adjacent letters — "Tyler, The Creator" must tokenise
    as ``{tyler, creator}`` (not ``{"tyler,", "creator"}``) for the
    artist-match check to clear the coverage threshold against a
    "tyler the creator" query. Unicode-aware so non-Latin scripts
    (Korean, Japanese, etc.) and accented characters (Björk, Beyoncé)
    survive intact.

    Stopwords (the, a, an, and, &) carry no signal for artist
    disambiguation so removing them avoids inflating coverage
    against trivial matches.
    """
    if not text:
        return set()
    return {tok for tok in _WORD_RE.findall(text.casefold()) if tok not in _STOPWORDS}


def _coverage_ratio(query_tokens: set[str], target_tokens: set[str]) -> float:
    """Return the symmetric token coverage of two token sets.

    Defined per spec Q2: ``|q ∩ t| / min(|q|, |t|)``. Symmetric so a
    single-token query against a two-token artist (``"kanye"`` vs
    ``"kanye west"``) scores 1.0, lifting an artist-only query against
    its full credit. Returns ``0.0`` when either set is empty.
    """
    if not query_tokens or not target_tokens:
        return 0.0
    overlap = len(query_tokens & target_tokens)
    return overlap / min(len(query_tokens), len(target_tokens))


def _composite_rerank(
    candidates: list[dict[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    """Two-bucket rerank: artist matches always above non-matches.

    User invariant (post-004 follow-up): "searching for an artist should
    ALWAYS produce all their albums before others." The earlier additive
    ``+10`` boost couldn't enforce this because a +10 delta is small
    relative to the BM25/popularity gap between, say, an obscure Tyler
    album at index 12 and Frank Ocean's *Channel Orange* (where Tyler
    is a credited producer) at index 0. Switching to a hard partition:

    * **Bucket A (top)** — candidates whose ``artist_name`` token coverage
      against the query meets ``_TOKEN_COVERAGE_THRESHOLD``. Sorted by
      ``(rating_count desc, i asc)`` so the artist's most-engaged-with
      albums lead, with mirror BM25 order as a stable tiebreaker.
    * **Bucket B (bottom)** — everything else. Sorted by ``i asc`` to
      preserve whatever order the source supplied (mirror BM25 for
      mirror rows; Discogs popularity for fallback rows). Don't second-
      guess the source within the non-matching bucket.

    Title-token coverage is intentionally not a boost dimension — the
    mirror's FTS5 BM25 already scores the title column, and the user's
    framing was specifically about artist queries.
    """
    if not candidates:
        return []
    query_tokens = _tokenize(query)
    matches: list[tuple[int, dict[str, Any]]] = []
    non_matches: list[tuple[int, dict[str, Any]]] = []
    for i, hit in enumerate(candidates):
        artist_tokens = _tokenize(str(hit.get("artist_name") or ""))
        if (
            query_tokens
            and _coverage_ratio(query_tokens, artist_tokens) >= _TOKEN_COVERAGE_THRESHOLD
        ):
            matches.append((i, hit))
        else:
            non_matches.append((i, hit))

    # Bucket A: popularity-first within the artist's discography,
    # with source order breaking exact rating-count ties.
    matches.sort(key=lambda pair: (-(int(pair[1].get("rating_count") or 0)), pair[0]))
    # Bucket B: keep source order; no reshuffle.
    non_matches.sort(key=lambda pair: pair[0])
    return [hit for _, hit in matches] + [hit for _, hit in non_matches]


# ---------------------------------------------------------------------------
# Filter + sort helpers (relocated from search/routes.py for feature 004)
# ---------------------------------------------------------------------------


def _filter_results(
    results: list[dict[str, Any]],
    *,
    decade_buckets: set[int] | None,
    year_min: int | None,
    year_max: int | None,
    genre: str | None,
    require_cover: bool = False,
) -> list[dict[str, Any]]:
    """Post-search filter applied to the merged candidate list.

    Albums missing a ``release_year`` are excluded from decade- or
    year-filtered queries (matches the user mental model: "show me
    2010s albums" should not surface a hit with no known year).

    ``genre`` is a case-insensitive substring match against any of an
    album's tags. The same missing-data rule applies — albums with no
    genre tags are excluded once the filter is set, so the result feels
    intentional rather than thin.

    ``require_cover`` drops any hit with neither an ``mbid`` (which
    routes through ``/api/cover/<mbid>`` for art) nor an explicit
    ``cover_art_url``. Used by browseable Discover surfaces where a
    coverless grid cell reads as broken; the Log sheet leaves this
    off so the user can still log obscure releases.
    """
    if (
        decade_buckets is None
        and year_min is None
        and year_max is None
        and genre is None
        and not require_cover
    ):
        return results

    needs_year_filter = decade_buckets is not None or year_min is not None or year_max is not None

    kept: list[dict[str, Any]] = []
    for hit in results:
        if require_cover and not (hit.get("mbid") or hit.get("cover_art_url")):
            continue
        if needs_year_filter:
            year = hit.get("release_year")
            if not isinstance(year, int):
                continue
            if year_min is not None and year < year_min:
                continue
            if year_max is not None and year > year_max:
                continue
            if decade_buckets is not None:
                decade_start = (year // 10) * 10
                if decade_start not in decade_buckets:
                    continue
        if genre is not None:
            tags = hit.get("genres")
            if not isinstance(tags, list) or not tags:
                continue
            if not any(genre in str(tag).lower() for tag in tags):
                continue
        kept.append(hit)
    return kept


def _sort_results(
    results: list[dict[str, Any]],
    *,
    sort_key: str,
) -> list[dict[str, Any]]:
    """Apply the user-selected sort to the filtered candidate list.

    Mirrors the pre-feature-004 implementation that lived in
    :mod:`auxd_api.modules.search.routes`. Relocated to the service
    layer so the legacy (mirror-disabled) fallback path can reuse it
    without circular imports.

    ``relevance`` preserves the input order — the route layer applies
    the composite reranker before calling this for the mirror-on path.
    """
    if sort_key == "relevance":
        return list(results)

    if sort_key == "popular_on_auxd":
        return sorted(
            results,
            key=lambda h: h.get("rating_count") or 0,
            reverse=True,
        )

    if sort_key == "recently_added":
        return sorted(
            results,
            key=lambda h: h.get("created_at") or "",
            reverse=True,
        )

    if sort_key == "surprise":
        shuffled = list(results)
        random.shuffle(shuffled)
        return shuffled

    reverse = sort_key == "year_newest"

    def _year_key(hit: dict[str, Any]) -> tuple[int, int]:
        year = hit.get("release_year")
        if isinstance(year, int):
            return (0, year)
        return (1, 0)

    return sorted(results, key=_year_key, reverse=reverse)


# ---------------------------------------------------------------------------
# Combined query + filter orchestrator (feature 004)
# ---------------------------------------------------------------------------


async def search_albums_with_total(
    *,
    query: str,
    year_min: int | None,
    year_max: int | None,
    decade_buckets: set[int] | None,
    genre: str | None,
    require_cover: bool,
    sort_key: str,
    limit: int,
    offset: int,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    mirror_service: AlbumMirrorService | None,
) -> tuple[list[dict[str, Any]], int]:
    """Query+filter search returning ``(page, total)``.

    Replaces the route's old 50-cap candidate fetch (which capped
    ``total`` at 50 by construction). Three execution modes:

    1. **Mirror enabled, ≥5 hits.** Route the query+filters through
       the mirror's FTS5 + WHERE in one SQL pass; honest COUNT(*)
       backs the total, BM25 backs the order, composite reranker
       lifts artist-matching candidates for ``sort_key='relevance'``.
    2. **Mirror enabled, <5 hits.** Keep the mirror rows at the top
       of the list (relevance-preserved) and APPEND the legacy
       Discogs/MB chain's results below. Total = mirror_total +
       non_mirror_count, capped at ``_TOTAL_DISPLAY_CAP``. Non-
       interleaved per FR-005.
    3. **Mirror disabled / unreachable.** Fall through to the legacy
       :func:`search_albums_cached` flow with in-process filter +
       sort; report ``total = len(filtered)``, no honest count.
       Emit a ``search.mirror_degraded`` log event so the count-lie
       mode is observable.
    """
    # Mode 3 — degraded path. The mirror dep is wired but inert (no
    # Turso client), so a single ``enabled`` check decides whether
    # we can offer honest totals at all.
    if mirror_service is None or not mirror_service.enabled:
        _LOGGER.info(
            "search.mirror_degraded",
            extra={
                "event": "search.mirror_degraded",
                "query": query,
                "has_filter": bool(
                    decade_buckets or year_min is not None or year_max is not None or genre
                ),
            },
        )
        candidates = await search_albums_cached(
            query=query,
            limit=50,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
            mirror_service=mirror_service,
        )
        filtered = _filter_results(
            candidates,
            decade_buckets=decade_buckets,
            year_min=year_min,
            year_max=year_max,
            genre=genre,
            require_cover=require_cover,
        )
        sorted_results = _sort_results(filtered, sort_key=sort_key)
        # 004 follow-up: the composite reranker must run even on the
        # degraded path. Without it, Discogs's master ordering bleeds
        # through verbatim and popular albums where the artist is a
        # *credit* (Igor for q="kanye west") outrank the actual artist's
        # discography. The boost reads ``artist_name`` from the legacy
        # serialiser — same field shape as mirror hits.
        if sort_key == "relevance":
            sorted_results = _composite_rerank(sorted_results, query=query)
        page = sorted_results[offset : offset + limit]
        return page, len(sorted_results)

    # Mode 1 / 2 — mirror-on path. Pull a window large enough to
    # cover the caller's offset + limit so the slice is local.
    mirror_window_limit = max(offset + limit, _FALLBACK_THRESHOLD * 2, 50)
    mirror_rows, mirror_total = await mirror_service.search_text_with_filters(
        query=query,
        year_min=year_min,
        year_max=year_max,
        decade_buckets=decade_buckets,
        genre=genre,
        sort_key=sort_key,
        limit=mirror_window_limit,
        offset=0,
    )

    mirror_serialized: list[dict[str, Any]] = []
    for i, row in enumerate(mirror_rows):
        album = await _resolve_or_materialise_mirror_row(row)
        mirror_serialized.append(_serialize_album(album, relevance_rank=i))

    if len(mirror_rows) >= _FALLBACK_THRESHOLD:
        # Mode 1 — mirror is the authoritative source.
        if sort_key == "relevance":
            ordered = _composite_rerank(mirror_serialized, query=query)
        else:
            ordered = mirror_serialized
        # ``require_cover`` still needs an in-process pass because
        # cover_art_url isn't a column on the mirror today.
        if require_cover:
            ordered = _filter_results(
                ordered,
                decade_buckets=None,  # already applied SQL-side
                year_min=None,
                year_max=None,
                genre=None,
                require_cover=True,
            )
        page = ordered[offset : offset + limit]
        return page, min(mirror_total, _TOTAL_DISPLAY_CAP)

    # Mode 2 — thin mirror, top up with the legacy Discogs/MB chain.
    # The legacy flow returns up to 50 candidates with the SAME query;
    # we filter them in-process to honor decade/year/genre and APPEND
    # below the mirror rows (no interleave per FR-005).
    legacy = await search_albums_cached(
        query=query,
        limit=50,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror_service,
    )
    # Strip out any legacy hit whose MBID already showed up in the
    # mirror tier — the mirror flow already materialised those.
    mirror_mbids = {hit.get("mbid") for hit in mirror_serialized if hit.get("mbid")}
    legacy_filtered = _filter_results(
        [hit for hit in legacy if hit.get("mbid") not in mirror_mbids],
        decade_buckets=decade_buckets,
        year_min=year_min,
        year_max=year_max,
        genre=genre,
        require_cover=require_cover,
    )
    legacy_sorted = _sort_results(legacy_filtered, sort_key=sort_key)

    if sort_key == "relevance":
        mirror_ordered = _composite_rerank(mirror_serialized, query=query)
    else:
        mirror_ordered = mirror_serialized
    if require_cover:
        mirror_ordered = _filter_results(
            mirror_ordered,
            decade_buckets=None,
            year_min=None,
            year_max=None,
            genre=None,
            require_cover=True,
        )

    combined = mirror_ordered + legacy_sorted
    # 004 follow-up: rerank the COMBINED list when sort=relevance so
    # legacy/Discogs hits with the matching artist (Jesus Is King) lift
    # above legacy hits where the query is a credit/feature only (Igor).
    # FR-005 said "never interleave" — the spirit is "the matching
    # artist's albums come first regardless of who supplied the row",
    # which the rerank achieves; the strict ordering letter is relaxed.
    if sort_key == "relevance":
        combined = _composite_rerank(combined, query=query)
    page = combined[offset : offset + limit]
    total = min(mirror_total + len(legacy_sorted), _TOTAL_DISPLAY_CAP)
    return page, total


__all__ = [
    "filter_only_search",
    "probe_external_for_filters",
    "search_albums",
    "search_albums_cached",
    "search_albums_with_total",
]
