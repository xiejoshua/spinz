"""Search HTTP routes (T069).

Single endpoint at MVP:

* ``GET /api/v1/search?q=<str>&type=album&limit=<int>`` — runs Atlas
  Search against the local ``albums`` collection, then progressively
  falls back through MusicBrainz and Discogs when local hits are sparse.

Three-tier fallback strategy:

1. **Atlas first** — local catalog has the lowest latency + reflects any
   prior user activity (popularity boost).
2. **MusicBrainz fallback** when local hits ``< 5`` — auto-materialises
   any new MBIDs into the local catalog via
   :func:`auxd_api.modules.albums.identity.resolve_identity` so the next
   query for the same album is fully local.
3. **Discogs fallback** when still ``< 5`` — same materialise-and-cache
   pattern but the new rows are marked ``candidate=True`` for the T065
   reconciliation worker.

When the merged result is still empty after all three tiers, the
response includes a ``report_missing_album_url`` hint pointing at the
"Report missing album" stub endpoint (T053a) so the UI can surface a
self-service entry path.

Constitution P6: providers are typed as the :class:`CatalogProvider`
Protocol throughout; concrete instances are constructed in the FastAPI
dependency factory so tests can inject mocks without touching the HTTP
layer.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from auxd_api.dependencies import get_mirror_service
from auxd_api.modules.mb_mirror.service import AlbumMirrorService
from auxd_api.modules.search.service import (
    filter_only_search,
    probe_external_for_filters,
    search_albums_with_total,
)
from auxd_api.providers.base import CatalogProvider
from auxd_api.providers.discogs import DiscogsCatalogProvider
from auxd_api.providers.musicbrainz import MusicBrainzCatalogProvider

router = APIRouter(prefix="/search", tags=["search"])

# Path to the "Report missing album" endpoint (T053a stub). Surfaced in
# the response when no provider returned a hit so the UI can render a
# direct CTA without hard-coding the URL on the frontend.
_REPORT_MISSING_ALBUM_URL = "/api/v1/reports/missing-album"


async def _mb_provider() -> CatalogProvider:
    """Construct a per-request MusicBrainz provider.

    Lifecycle: arq workers reuse a single long-lived client; the request
    path builds one per call. The httpx client construction cost is
    negligible compared to the 1 req/sec MB etiquette delay, so the
    simpler per-request shape avoids dependency-overrides leaking
    between tests.
    """
    return MusicBrainzCatalogProvider()


async def _discogs_provider() -> CatalogProvider:
    """Construct a per-request Discogs provider.

    Runs in graceful-disabled mode when ``DISCOGS_API_TOKEN`` is unset
    (see :class:`DiscogsCatalogProvider`) — the search pipeline degrades
    cleanly to "MusicBrainz only" in that case.
    """
    return DiscogsCatalogProvider()


@router.get("")
async def search(
    background_tasks: BackgroundTasks,
    mb_provider: Annotated[CatalogProvider, Depends(_mb_provider)],
    discogs_provider: Annotated[CatalogProvider, Depends(_discogs_provider)],
    mirror_service: Annotated[AlbumMirrorService, Depends(get_mirror_service)],
    q: Annotated[str, Query(max_length=200)] = "",
    type: Annotated[str, Query(pattern="^album$")] = "album",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0, le=500)] = 0,
    decade: Annotated[
        str | None,
        Query(
            description=(
                "Comma-separated list of decade buckets to include. "
                "Each value must be of the form ``YYYYs`` (e.g. ``2010s,2020s``)."
            ),
            max_length=80,
        ),
    ] = None,
    year_min: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_max: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    genre: Annotated[
        str | None,
        Query(
            description=(
                "Optional substring match against an album's genre tags. "
                "Matches case-insensitively against any tag in "
                "``Album.genres`` (provider-supplied + curator-edited). "
                "Albums missing genre tags are excluded when this filter "
                "is set."
            ),
            max_length=60,
        ),
    ] = None,
    sort: Annotated[
        str,
        Query(
            pattern=(
                "^(relevance|popular_on_auxd|recently_added|year_newest|year_oldest|surprise)$"
            ),
            description=(
                "Sort key. ``relevance`` preserves provider/Atlas merged order "
                "(text quality + Discogs popularity) when a query is present, "
                "and falls back to ``popular_on_auxd`` when filter-only. "
                "``popular_on_auxd`` ranks by Album.rating_count desc. "
                "``recently_added`` by Album.created_at desc. "
                "``surprise`` returns a random sample (single page; no "
                "pagination — re-issue the request to reshuffle)."
            ),
        ),
    ] = "relevance",
    require_cover: Annotated[
        bool,
        Query(
            description=(
                "When true, exclude results that have neither an MBID "
                "nor an explicit ``cover_art_url`` — i.e. cover art is "
                "definitely unavailable. Defaults to false so the Log "
                "sheet (which needs to surface obscure releases even "
                "without art) keeps full coverage. Discover surfaces "
                "opt in."
            ),
        ),
    ] = False,
) -> dict[str, Any]:
    """Search the catalog with optional filtering, sorting, and pagination
    (003 / FR-015..FR-020).

    Three-tier provider fallback (Atlas → Discogs masters → MusicBrainz)
    runs first to assemble a candidate set, then the filter/sort/paginate
    pass narrows it down to the requested window. Post-filter sorting is
    in-memory because the candidate set is bounded (≤50 from each tier).

    Args:
        q: Free-text search term. Required, 1..200 chars.
        type: Currently only ``"album"`` is supported.
        limit: Page size (1..50). Default 10.
        offset: 0-indexed pagination offset (0..500). Default 0.
        decade: Optional ``YYYYs``-bucket filter, comma-separated. A
            release-year of ``2025`` falls in ``2020s``. Albums missing a
            release year are excluded from any decade-filtered result.
        year_min / year_max: Inclusive numeric year-range filter, applied
            in addition to ``decade`` when both are present.
        sort: ``relevance`` (default — preserves merged provider order),
            ``popularity`` (Discogs+MB don't expose a count, falls back
            to relevance when the field is absent), ``year_newest`` or
            ``year_oldest`` (numeric on ``release_year``).

    Returns:
        ``{results: [...], total: int, has_more: bool,
        report_missing_album_url?: str}``. The report URL is non-null
        only when the merged + filtered result list is empty.
    """
    if type != "album":
        raise HTTPException(status_code=400, detail="unsupported_search_type")

    decade_buckets = _parse_decade_buckets(decade)
    if year_min is not None and year_max is not None and year_min > year_max:
        raise HTTPException(
            status_code=400,
            detail="year_min must be <= year_max",
        )

    query = q.strip()
    genre_clean = genre.strip().lower() if genre else None
    has_filter = bool(decade_buckets or year_min is not None or year_max is not None or genre_clean)

    if not query and not has_filter:
        raise HTTPException(
            status_code=400,
            detail="provide_query_or_filter",
        )

    if query:
        # Query mode — feature 004 routes query+filter through the
        # mirror's FTS5 MATCH + WHERE so ``total`` reflects a true
        # COUNT(*) rather than ``len(candidates)`` over a 50-cap
        # window. Composite reranker inside the service applies the
        # artist-match boost for ``sort='relevance'``.
        page, total = await search_albums_with_total(
            query=query,
            year_min=year_min,
            year_max=year_max,
            decade_buckets=decade_buckets,
            genre=genre_clean,
            require_cover=require_cover,
            sort_key=sort,
            limit=limit,
            offset=offset,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
            mirror_service=mirror_service,
        )
        # Surprise mode has no pagination concept — re-issue to reshuffle.
        has_more = sort != "surprise" and (offset + limit) < total
    else:
        # Filter-only browse against the local catalog — pagination at
        # the Mongo layer with a true total count. No Discogs / MB.
        page, total = await filter_only_search(
            year_min=year_min,
            year_max=year_max,
            decade_buckets=decade_buckets,
            genre=genre_clean,
            require_cover=require_cover,
            sort_key=sort,
            limit=limit,
            offset=offset,
            mirror_service=mirror_service,
        )
        has_more = sort != "surprise" and (offset + limit) < total

        # Approach C — when the local catalog is thin for this filter
        # combo, schedule a Discogs probe AFTER the response is sent.
        # Newly materialised albums show up on the next browse.
        background_tasks.add_task(
            probe_external_for_filters,
            decade_buckets=decade_buckets,
            genre=genre_clean,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
            local_total=total,
        )

    response: dict[str, Any] = {
        "results": page,
        "total": total,
        "has_more": has_more,
    }
    if not page and offset == 0:
        response["report_missing_album_url"] = _REPORT_MISSING_ALBUM_URL
    return response


# ---------------------------------------------------------------------------
# Filter + sort helpers (003)
# ---------------------------------------------------------------------------


def _parse_decade_buckets(raw: str | None) -> set[int] | None:
    """Parse a comma-separated ``YYYYs`` list into decade-start years.

    ``"2010s,2020s"`` → ``{2010, 2020}``. Returns ``None`` when no
    decade filter is requested. Raises ``HTTPException(400)`` on any
    malformed token so the frontend gets a clear validation error
    instead of a silently-empty result list.
    """
    if not raw:
        return None
    buckets: set[int] = set()
    for token in raw.split(","):
        cleaned = token.strip().lower()
        if not cleaned:
            continue
        if not cleaned.endswith("s") or not cleaned[:-1].isdigit():
            raise HTTPException(
                status_code=400,
                detail=f"invalid_decade_token:{token!r}",
            )
        year = int(cleaned[:-1])
        if year < 1900 or year > 2100:
            raise HTTPException(
                status_code=400,
                detail=f"decade_out_of_range:{token!r}",
            )
        # Round down to the decade start so ``2015s`` would normalise
        # to ``2010``. Defence-in-depth — the frontend always sends
        # decade-aligned tokens.
        buckets.add((year // 10) * 10)
    return buckets or None


__all__ = ["router"]
