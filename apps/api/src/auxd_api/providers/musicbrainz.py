"""MusicBrainz catalog provider — T049.

:class:`MusicBrainzCatalogProvider` is the MVP catalog backbone. It
implements the :class:`~auxd_api.providers.base.CatalogProvider` Protocol
against the MusicBrainz JSON web service (``/ws/2``).

Resilience + observability are inherited from
:class:`~auxd_api.providers.transport.ResilienceTransport`. This module
adds the MusicBrainz-specific bits:

* Required ``User-Agent`` per MB etiquette policy
  (https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting).
* 1 req/sec per-IP rate limit enforced via an asyncio Lock + monotonic
  clock — chosen over a Semaphore because we need temporal spacing, not
  bounded concurrency.
* Mapping of MB ``release-group`` JSON to
  :class:`~auxd_api.providers.base.CatalogAlbum`.

Cover art is generated from the Cover Art Archive URL convention
(``coverartarchive.org/release-group/{mbid}/front``) — we don't make a
second round-trip to verify the asset exists; the CAA falls back to a
404 image that the frontend can detect client-side.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from auxd_api.providers.base import CatalogAlbum, CatalogProvider
from auxd_api.providers.errors import ProviderRateLimited, ProviderUnavailable
from auxd_api.providers.transport import build_async_client

_USER_AGENT = "auxd/0.0.0 (https://auxd.xiejoshua.com)"
_BASE_URL = "https://musicbrainz.org/ws/2"
_CAA_BASE = "https://coverartarchive.org"
_MIN_INTERVAL_SECONDS = 1.0
"""MusicBrainz etiquette: 1 request per second per IP."""


class MusicBrainzCatalogProvider(CatalogProvider):
    """Catalog provider backed by the MusicBrainz JSON web service."""

    def __init__(
        self,
        *,
        inner_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = build_async_client(
            base_url=_BASE_URL,
            provider_name="musicbrainz",
            user_agent=_USER_AGENT,
            timeout_seconds=10.0,
            retry_attempts=3,
            inner_transport=inner_transport,
        )
        self._pace_lock = asyncio.Lock()
        self._last_call_ts: float = 0.0

    async def aclose(self) -> None:
        """Release the underlying httpx client. Idempotent."""
        await self._client.aclose()

    async def __aenter__(self) -> MusicBrainzCatalogProvider:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # CatalogProvider protocol
    # ------------------------------------------------------------------

    async def search_albums(self, query: str, limit: int = 10) -> list[CatalogAlbum]:
        """Search MusicBrainz release-groups by free-text ``query``.

        Returns up to ``limit`` matches. Empty list on no results.
        """
        await self._wait_for_rate_limit_slot()
        response = await self._client.get(
            "/release-group",
            params={"query": query, "limit": str(limit), "fmt": "json"},
        )
        # Surface 4xx (non-429, non-404) as ProviderUnavailable — search
        # doesn't have a sensible "not-found" semantic distinct from empty.
        if response.status_code >= 400:
            if response.status_code == 429:  # pragma: no cover - transport already mapped
                raise ProviderRateLimited("musicbrainz", provider="musicbrainz")
            raise ProviderUnavailable(
                f"musicbrainz search returned {response.status_code}",
                provider="musicbrainz",
            )
        payload = response.json()
        groups: list[dict[str, object]] = payload.get("release-groups", []) or []
        return [self._map_release_group(item) for item in groups]

    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None:
        """Look up a release-group by MBID. Returns ``None`` on 404."""
        await self._wait_for_rate_limit_slot()
        response = await self._client.get(f"/release-group/{mbid}", params={"fmt": "json"})
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            if response.status_code == 429:  # pragma: no cover - transport already mapped
                raise ProviderRateLimited("musicbrainz", provider="musicbrainz")
            raise ProviderUnavailable(
                f"musicbrainz lookup returned {response.status_code}",
                provider="musicbrainz",
            )
        return self._map_release_group(response.json())

    async def get_album_by_external_id(
        self, provider: str, external_id: str
    ) -> CatalogAlbum | None:
        """Look up by external id. Only ``provider="mbid"`` is supported.

        Discogs ids are not resolvable from MusicBrainz directly; the
        identity normalisation service (T063) handles cross-provider
        joins via the candidate-album flow.
        """
        if provider != "mbid":
            return None
        return await self.get_album_by_mbid(external_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _wait_for_rate_limit_slot(self) -> None:
        """Enforce the 1 req/sec MB etiquette policy.

        Uses :func:`time.monotonic` (not :func:`time.time`) so the pacing
        is immune to wall-clock adjustments. The lock keeps concurrent
        callers serialised against the same provider instance.
        """
        async with self._pace_lock:
            now = time.monotonic()
            elapsed = now - self._last_call_ts
            if elapsed < _MIN_INTERVAL_SECONDS:
                await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            self._last_call_ts = time.monotonic()

    @staticmethod
    def _map_release_group(item: dict[str, object]) -> CatalogAlbum:
        """Map a MusicBrainz release-group dict to a :class:`CatalogAlbum`.

        Defensive about optional fields — older MB records can lack
        ``first-release-date`` or have an empty ``artist-credit`` list.
        """
        mbid = str(item.get("id", ""))
        title = str(item.get("title", ""))
        artist_credit_raw = item.get("artist-credit")
        artist_name = ""
        if isinstance(artist_credit_raw, list) and artist_credit_raw:
            first_credit = artist_credit_raw[0]
            if isinstance(first_credit, dict):
                name = first_credit.get("name") or first_credit.get("artist", {}).get("name")
                if isinstance(name, str):
                    artist_name = name
        release_year: int | None = None
        first_release_date = item.get("first-release-date")
        if isinstance(first_release_date, str) and len(first_release_date) >= 4:
            year_part = first_release_date[:4]
            if year_part.isdigit():
                release_year = int(year_part)
        cover_art_url = f"{_CAA_BASE}/release-group/{mbid}/front" if mbid else None
        return CatalogAlbum(
            mbid=mbid or None,
            discogs_release_id=None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            external_ids={"mbid": mbid} if mbid else {},
        )


__all__ = ["MusicBrainzCatalogProvider"]
