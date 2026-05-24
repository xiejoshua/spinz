"""Search service layer (T069).

Wraps the Atlas Search aggregation pipeline + the multi-provider
parallel merge into a single :func:`search_albums` entry point. The
route layer (:mod:`auxd_api.modules.search.routes`) is intentionally
thin — every piece of business logic lives here so the same flow can be
called from a future GraphQL surface, a CLI tool, or unit tests without
spinning up the FastAPI app.

Flow (post-2026-05-24 v3 fix):

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

2. If Atlas returns fewer than :data:`_FALLBACK_THRESHOLD` hits, query
   MusicBrainz AND Discogs in PARALLEL (``asyncio.gather``). The two
   results are merged via a combined score with three components:

   * MB hits keep their MB relevance score (0..100).
   * Discogs hits get an initial position-based score
     (``100 - i * 10``) used as a fallback popularity proxy.
   * **Lexical heuristic boost** (Fix A, v3): every candidate gets an
     additive boost based on the query→hit relationship (artist exact
     match +200, title prefix match +100, title substring +50).
     Disambiguates "kanye west" (artist intent) from "Graduation"
     (title intent) without needing a separate parser.
   * **Discogs popularity enrichment** (Fix B+C, v3): the top N
     Discogs candidates are enriched with REAL community-have counts
     fetched from ``/releases/{id}``. The position-based score was an
     incorrect assumption — Discogs's ``/database/search`` returns by
     relevance, not by popularity. ``log10(community.have+1) * 25``
     produces a 0..150 popularity score that replaces the
     position-based proxy when available. Cached in Redis for 24h.
   * Hits that appear in BOTH providers get a ``+50`` cross-source
     bonus — provider agreement is a strong canonical-release signal.

   The previous v2 ladder surfaced compilations titled "Kanye West" by
   non-Kanye artists ahead of Kanye's actual releases for the artist
   query. The v3 artist-exact-match boost catapults Kanye's hits;
   the title-prefix boost similarly solves "to pimp" →
   "To Pimp a Butterfly" beating "Pimp To Eat".

   MB hits with an MBID materialise via
   :func:`auxd_api.modules.albums.identity.resolve_identity` so future
   queries for the same album are fully local. Discogs hits without an
   MBID materialise as ``candidate=True`` albums for the T065
   reconciliation worker.

Dedupe key is ``(title.lower(), artist_credit.lower())`` plus MBID where
present — handles the common case where the same release appears in
Atlas + MusicBrainz + Discogs with subtly different formatting.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from typing import Any, cast

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.identity import resolve_identity
from auxd_api.modules.albums.models import Album
from auxd_api.providers.base import CatalogAlbum, CatalogProvider
from auxd_api.providers.errors import ProviderError
from auxd_api.redis_client import cache_get, cache_set

_LOGGER = logging.getLogger("auxd.search")

# Threshold for tier-2/3 activation: below this many Atlas hits we run
# the parallel MB + Discogs merge (post-2026-05-24 fix replaces the old
# strictly-sequential MB-then-Discogs ladder with a single parallel
# query and combined-score merge — see module docstring).
_FALLBACK_THRESHOLD = 5

# Atlas Search index name — must match the ``name`` field in
# ``apps/api/migrations/atlas_search/albums_index.json``.
_ATLAS_INDEX = "albums_text_search"

# v3 enrichment tuning. ``_ENRICH_TOP_N`` caps the per-search blast
# radius of Discogs detail-endpoint fetches (Discogs's authenticated
# rate limit is 60 req/min). ``_COMMUNITY_CACHE_TTL_SECONDS`` is 24h:
# community.have counts move slowly. ``_POPULARITY_SCORE_SCALE``
# converts log10(have+1) into a 0..~150 score range that sits alongside
# MB's 0..100 relevance band — ``25`` produces ~50 for 100-have albums,
# ~75 for 1 000, ~100 for 10 000, ~125 for 100 000 (canonical popular
# releases) without dwarfing MB relevance entirely.
_ENRICH_TOP_N = 10
_COMMUNITY_CACHE_TTL_SECONDS = 86400
_COMMUNITY_CACHE_KEY = "discogs:community:{release_id}"
_POPULARITY_SCORE_SCALE = 25.0


def _heuristic_boost(*, hit_artist: str, hit_title: str, query: str) -> int:
    """Lexical heuristic boost — Fix A of v3 search-quality patch.

    Disambiguates artist-intent vs title-intent queries that MB and
    Discogs both tie at ~100 on relevance:

    * **Artist exact match (+200)** — the query equals the hit's
      ``artist_name``. Strongest signal: queries like "kanye west"
      almost certainly mean "albums by this artist", so Kanye's own
      releases get +200 while a niche compilation titled "Kanye West"
      by a different artist gets nothing.
    * **Title prefix (+100)** — the title starts with the query.
      Solves "to pimp" → "To Pimp a Butterfly" beating
      "Pimp To Eat" (whose title only *contains* the query).
    * **Title substring (+50)** — weaker tier when the prefix
      condition isn't met. Prefix and substring are mutually exclusive
      (``elif``) so a hit can't double-count.

    Magnitudes are hand-tuned to sit comfortably above MB's 0..100
    relevance band: +200 lifts a low-MB-score hit (score=10) above a
    high-MB-score non-artist hit (score=100). The boosts compose
    additively with the existing MB / Discogs / cross-source scoring.

    Case-insensitive via :py:meth:`str.casefold` (Unicode-aware lower).
    Whitespace stripped to handle trailing-space queries.
    """
    q = query.casefold().strip()
    if not q:
        return 0
    artist = (hit_artist or "").casefold().strip()
    title = (hit_title or "").casefold().strip()

    boost = 0
    if artist == q:
        boost += 200
    if title.startswith(q):
        boost += 100
    elif q in title:
        boost += 50
    return boost


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

    Tier 1 (Atlas): if Atlas returns ``>= _FALLBACK_THRESHOLD`` hits, return
    them directly — Atlas is the cleanest source once the catalog populates
    with user activity and gets a query-time popularity boost from
    ``log1p(rating_count)`` (see :func:`_atlas_search`).

    Tier 2 + 3 (parallel MB + Discogs): for cold-catalog queries we always
    query MusicBrainz AND Discogs in parallel — not as ordered fallbacks.
    The post-2026-05-24 fix moves Discogs onto the hot path because Discogs
    sorts its structured-query results by ``community.have`` count (a real
    popularity signal MB lacks). MB hits bring relevance precision via
    ``score``; Discogs hits bring popularity ranking via position. The two
    are merged via a combined score that lets a hit confirmed by BOTH
    providers (cross-source bonus) bubble past hits seen in only one.

    Atlas-hits keep their natural sort order (relevance + popularity);
    provider-merge hits append in combined-score order.
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

    # ---- Tier 2 + 3: MB + Discogs in PARALLEL --------------------------
    # asyncio.gather lets both upstream calls overlap on the wire (each
    # provider has its own connection pool + circuit breaker). A single
    # provider failure does not poison the other — see
    # ``_safe_provider_search`` for the per-provider error funnel.
    mb_task = _safe_provider_search(mb_provider, query, limit, "musicbrainz")
    discogs_task = _safe_provider_search(discogs_provider, query, limit, "discogs")
    mb_hits, discogs_hits = await asyncio.gather(mb_task, discogs_task)

    # Sort MB by relevance score desc; ``None`` scores sink via -1 sentinel.
    # Keeps mypy clean (no Optional comparison) and pins None below 0.
    mb_hits.sort(key=lambda h: h.score if h.score is not None else -1, reverse=True)
    # Discogs hits arrive in popularity-rank order — preserve as-is.

    # Combined scoring:
    #   * MB hits keep raw MB score (0..100 from MB's Lucene relevance).
    #   * Discogs hits get ``max(0, 100 - i * 10)`` as a FALLBACK
    #     popularity proxy. The real popularity score (Fix B+C, v3)
    #     comes from ``_enrich_with_popularity`` below — when that
    #     enrichment succeeds, the position-based component is
    #     replaced with ``log10(have+1) * 25``.
    #   * Every hit additionally receives a ``_heuristic_boost``
    #     (Fix A, v3) for artist-exact-match (+200), title-prefix
    #     (+100), or title-substring (+50). This disambiguates
    #     artist-intent ("kanye west") vs title-intent ("Graduation")
    #     queries that providers tie at ~100 on relevance.
    #   * A hit found in BOTH branches gets a +50 cross-source bonus.
    #     Hand-tuned: it must be smaller than two top scores summed
    #     (200) but large enough to lift a single-source ~50 hit
    #     above a single-source 90-100 hit. ``+50`` keeps a cross-
    #     confirmed canonical release ahead of a higher-relevance
    #     single-source result, which is the design intent.
    candidates: list[tuple[int, CatalogAlbum, str]] = []
    for hit in mb_hits:
        base = hit.score if hit.score is not None else 0
        score = base + _heuristic_boost(
            hit_artist=hit.artist_name,
            hit_title=hit.title,
            query=query,
        )
        candidates.append((score, hit, "mb"))
    for i, hit in enumerate(discogs_hits):
        position_score = max(0, 100 - i * 10)
        score = position_score + _heuristic_boost(
            hit_artist=hit.artist_name,
            hit_title=hit.title,
            query=query,
        )
        candidates.append((score, hit, "discogs"))

    # Fix B+C (v3): enrich Discogs candidates with real popularity
    # (community.have) before the cross-source dedup. The enrichment
    # replaces the position-based proxy with a log-scaled community
    # score; failures fall back to the existing position score.
    candidates = await _enrich_with_popularity(candidates, discogs_provider, query)

    # Cross-source dedup is trickier than within-source dedup because MB
    # hits carry an MBID and Discogs hits don't. A naive
    # ``_dedupe_key(mbid=..., title=..., artist=...)`` would produce
    # ``mbid:<x>`` for MB and ``meta:<title>|<artist>`` for Discogs even
    # when both surface the same canonical album — the cross-source
    # bonus would never apply. Resolve by maintaining TWO indexes:
    #
    #   ``by_key`` keyed on the strong (MBID-when-available) form for
    #   final result ordering.
    #
    #   ``meta_alias`` keyed on the weak (title, artist) form so a
    #   Discogs hit can find an MB hit's existing entry by metadata
    #   alone. When the alias matches, we merge into the MB entry's
    #   slot rather than creating a duplicate.
    by_key: dict[str, dict[str, Any]] = {}
    meta_alias: dict[str, str] = {}

    def _meta_key(hit: CatalogAlbum) -> str:
        return f"meta:{hit.title.casefold()}|{hit.artist_name.casefold()}"

    for score, hit, source in candidates:
        strong_key = _dedupe_key(mbid=hit.mbid, title=hit.title, artist=hit.artist_name)
        meta_key = _meta_key(hit)

        # Find an existing entry by either the strong key (MBID match)
        # or the metadata alias (title/artist match across sources).
        existing_strong = by_key.get(strong_key)
        aliased_strong_key = meta_alias.get(meta_key)
        existing_aliased = by_key.get(aliased_strong_key) if aliased_strong_key else None

        if existing_strong is not None:
            entry = existing_strong
        elif existing_aliased is not None:
            entry = existing_aliased
        else:
            entry = None

        if entry is not None:
            entry["score"] = int(entry["score"]) + score
            sources_set: set[str] = entry["sources"]
            sources_set.add(source)
            # Prefer the hit that carries an MBID (richer identity) when
            # both branches surface the same album with different ids.
            existing_hit: CatalogAlbum = entry["hit"]
            if existing_hit.mbid is None and hit.mbid is not None:
                entry["hit"] = hit
        else:
            by_key[strong_key] = {"score": score, "hit": hit, "sources": {source}}
            # Index the metadata alias so the OTHER source can find this
            # entry. ``setdefault`` means the first-seen entry wins the
            # alias slot when multiple distinct hits share a (title,
            # artist) tuple — which is desirable: cross-source dedup
            # should be a one-to-one bond, not a one-to-many fan-out.
            meta_alias.setdefault(meta_key, strong_key)

    # Cross-source confirmation: a hit found in both MB and Discogs is
    # almost always the canonical release. Bump it.
    for entry in by_key.values():
        if len(entry["sources"]) > 1:
            entry["score"] = int(entry["score"]) + 50

    # Sort by combined score desc, then materialise in that order until
    # we hit the caller's ``limit``.
    sorted_entries = sorted(by_key.values(), key=lambda e: int(e["score"]), reverse=True)

    for entry in sorted_entries:
        # mypy: the redefinition annotation would clash with the earlier
        # ``for hit in mb_hits:`` loop binding above. Use ``cast`` to
        # narrow back from ``Any`` (the values in the ``dict[str, Any]``
        # entry) without re-shadowing the name.
        hit = cast(CatalogAlbum, entry["hit"])
        key = _dedupe_key(mbid=hit.mbid, title=hit.title, artist=hit.artist_name)
        if key in seen:
            continue
        seen.add(key)
        try:
            if hit.mbid:
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
        merged.append(_serialize_album(album))
        if len(merged) >= limit:
            return merged

    return merged


async def _safe_provider_search(
    provider: CatalogProvider, query: str, limit: int, name: str
) -> list[CatalogAlbum]:
    """Provider search that returns ``[]`` on :class:`ProviderError`.

    The parallel merge needs both upstreams to either return a list or
    silently degrade — a raised :class:`ProviderError` from one provider
    would propagate through ``asyncio.gather`` and abort the other call,
    even if the second was about to succeed. Catching here keeps the
    other branch's results usable when MB is rate-limited or Discogs
    times out.
    """
    try:
        return await provider.search_albums(query, limit=limit)
    except ProviderError as exc:
        _LOGGER.warning(
            f"search.{name}_error",
            extra={"event": f"search.{name}_error", "error": str(exc)},
        )
        return []


async def _get_discogs_community_score(
    release_id: str, discogs_provider: CatalogProvider
) -> int | None:
    """Return a popularity score for a Discogs release (cache-first).

    Caches the result for :data:`_COMMUNITY_CACHE_TTL_SECONDS` so the
    second user to search for a hot album hits Redis instead of the
    Discogs detail endpoint. Cache miss fetches via
    :meth:`DiscogsCatalogProvider.get_community_data`; non-fatal
    failure modes (provider disabled, 404, rate-limit, network error,
    Redis down) return ``None`` so callers can keep the existing
    position-based score.

    The 0..150-ish score is ``log10(community.have + 1) *
    _POPULARITY_SCORE_SCALE``. The log shape damps the gap between a
    100-have niche release and a 100 000-have canonical (~50 vs ~125,
    not 100x) so popularity composes cleanly with MB's 0..100
    relevance band.
    """
    cache_key = _COMMUNITY_CACHE_KEY.format(release_id=release_id)
    try:
        cached = await cache_get(cache_key)
    except Exception:  # pragma: no cover - cache_get is already fail-open
        cached = None

    if cached is not None:
        try:
            return int(cached)
        except (ValueError, TypeError):
            pass  # Stale shape — refetch.

    # Cache miss — call provider. ``get_community_data`` is a v3
    # addition to :class:`DiscogsCatalogProvider`; older providers
    # without the method are treated as graceful-disabled (None).
    getter = getattr(discogs_provider, "get_community_data", None)
    if getter is None:
        return None
    try:
        have = await getter(release_id)
    except Exception:  # pragma: no cover - provider impls already swallow
        return None
    if have is None:
        return None
    score = int(math.log10(have + 1) * _POPULARITY_SCORE_SCALE)
    # cache_set is already fail-open at the Redis layer; the suppress
    # is a defensive belt for any unexpected raise the wrapper misses.
    with contextlib.suppress(Exception):  # pragma: no cover - defensive
        await cache_set(cache_key, str(score), ex_seconds=_COMMUNITY_CACHE_TTL_SECONDS)
    return score


async def _enrich_with_popularity(
    candidates: list[tuple[int, CatalogAlbum, str]],
    discogs_provider: CatalogProvider,
    query: str,
) -> list[tuple[int, CatalogAlbum, str]]:
    """Replace position-based Discogs scores with real popularity data.

    Picks the top :data:`_ENRICH_TOP_N` candidates by score (after
    boosts have been applied), selects only those that came from
    Discogs with a ``discogs_release_id``, and fetches
    ``community.have`` for each in parallel via
    :func:`asyncio.gather`. The new score is
    ``log10(have+1) * _POPULARITY_SCORE_SCALE + heuristic_boost``;
    the position-based component is dropped.

    Failure modes are graceful: any single fetch returning ``None``
    leaves that candidate's original (position-based) score in place.
    MB candidates are not enriched (no MBID→Discogs lookup available
    in the Discogs search API).

    Top-N capping bounds Discogs API blast radius (authenticated tier
    is 60 req/min) and per-search latency (worst case: 10 cache
    misses in parallel, each capped by the provider's 10s timeout).
    """
    if not candidates:
        return candidates

    # Sort once so the top N are at the head — preserves the original
    # ordering for everything beyond the enrichment window.
    sorted_candidates = sorted(candidates, key=lambda c: c[0], reverse=True)
    to_enrich_idx: list[int] = []
    for idx, (_score, hit, source) in enumerate(sorted_candidates[:_ENRICH_TOP_N]):
        if source == "discogs" and hit.discogs_release_id:
            to_enrich_idx.append(idx)

    if not to_enrich_idx:
        return sorted_candidates

    fetch_tasks = [
        _get_discogs_community_score(
            sorted_candidates[idx][1].discogs_release_id or "",
            discogs_provider,
        )
        for idx in to_enrich_idx
    ]
    new_scores = await asyncio.gather(*fetch_tasks)

    rebuilt = list(sorted_candidates)
    for enriched_idx, community_score in zip(to_enrich_idx, new_scores, strict=True):
        if community_score is None:
            continue  # Fetch failed — keep position-based score.
        _old_score, hit, source = rebuilt[enriched_idx]
        # New score = community popularity + heuristic. The
        # position-based component is replaced because real popularity
        # is strictly better than a relevance-ordering proxy.
        boost = _heuristic_boost(
            hit_artist=hit.artist_name,
            hit_title=hit.title,
            query=query,
        )
        rebuilt[enriched_idx] = (community_score + boost, hit, source)

    return rebuilt


__all__ = ["search_albums"]
