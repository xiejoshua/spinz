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

from fastapi import APIRouter, Depends, HTTPException, Query

from auxd_api.modules.search.service import search_albums
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
    q: Annotated[str, Query(min_length=1, max_length=200)],
    mb_provider: Annotated[CatalogProvider, Depends(_mb_provider)],
    discogs_provider: Annotated[CatalogProvider, Depends(_discogs_provider)],
    type: Annotated[str, Query(pattern="^album$")] = "album",
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> dict[str, Any]:
    """Search the catalog with progressive provider fallback.

    Args:
        q: Free-text search term. Required, 1..200 chars.
        type: Currently only ``"album"`` is supported.
        limit: Maximum hits to return (1..25). Default 10.
        mb_provider: Injected MusicBrainz :class:`CatalogProvider`.
        discogs_provider: Injected Discogs :class:`CatalogProvider`.

    Returns:
        ``{results: [...], report_missing_album_url: str | None}``. The
        report URL is non-null only when the merged result list is empty.
    """
    # Only album search is wired at MVP — the path parameter narrows the
    # caller and future expansion (artist / track) lands as new branches
    # here.
    if type != "album":
        raise HTTPException(status_code=400, detail="unsupported_search_type")

    results = await search_albums(
        query=q,
        limit=limit,
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
    )

    response: dict[str, Any] = {"results": results}
    if not results:
        response["report_missing_album_url"] = _REPORT_MISSING_ALBUM_URL
    return response


__all__ = ["router"]
