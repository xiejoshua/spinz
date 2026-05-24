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

# Lucene reserved characters (per Lucene's
# https://lucene.apache.org/core/2_9_4/queryparsersyntax.html#Escaping%20Special%20Characters).
# A bare ``query=<text>`` parameter to MB hits Lucene under the hood; if
# we interpolate user input directly into a structured ``release:"<q>"
# OR artist:"<q>"`` query (post-2026-05-24 fix for the "kanye west returns
# niche releases titled 'Kanye West'" bug) any of these characters in the
# user's input would break parsing or — worse — let the user inject
# alternate field clauses. The leading backslash is escaped by Python's
# str literal already; the rest are the raw Lucene meta-characters.
_LUCENE_SPECIAL_CHARS = r'+-&|!(){}[]^"~*?:\/'


def _escape_lucene(value: str) -> str:
    """Escape Lucene-special characters in a user query for safe interpolation.

    Returns a string where every reserved Lucene character is prefixed
    with a backslash. Safe to embed inside a quoted Lucene phrase clause.
    """
    return "".join(f"\\{c}" if c in _LUCENE_SPECIAL_CHARS else c for c in value)


def _build_mb_lucene_query(query: str) -> str:
    """Build a structured release-group query: ``release:"q" OR artist:"q"``.

    The ``release:`` branch matches release-groups by title; the
    ``artist:`` branch matches release-groups attributed to artists with
    matching name. The ``OR`` combines both so the same input surfaces
    title-typical queries ("Graduation") and artist-typical queries
    ("Kanye West") without forcing the caller to pick a field.

    Prior to 2026-05-24 the provider sent the bare user input as
    ``query=<input>``, which MB interprets as a multi-field search. For
    common album titles that returned a glut of niche releases whose
    *title* happened to contain the artist's name (e.g. tribute albums
    literally titled "Kanye West"); the structured form pins the
    semantics so the relevance score actually reflects user intent.
    """
    escaped = _escape_lucene(query.strip())
    return f'release:"{escaped}" OR artist:"{escaped}"'


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

        Uses a structured Lucene query of the form
        ``release:"<q>" OR artist:"<q>"`` so the same input surfaces
        title-typical hits ("Graduation") and artist-typical hits
        ("Kanye West"). The previous bare ``query=<input>`` form let MB
        run a multi-field search that conflated artist-name occurrences
        in release titles with intent, surfacing niche tributes ahead of
        the canonical work — see :func:`_build_mb_lucene_query` for the
        full design note.

        Returns up to ``limit`` matches. Empty list on no results.
        """
        await self._wait_for_rate_limit_slot()
        mb_query = _build_mb_lucene_query(query)
        response = await self._client.get(
            "/release-group",
            params={"query": mb_query, "limit": str(limit), "fmt": "json"},
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
        """Look up a release-group by MBID. Returns ``None`` on 404.

        ``inc=artist-credits`` is required for the response to include the
        ``artist-credit`` array — without it MB returns the minimal-shape
        release-group record (id/title/type/dates) and our mapping leaves
        ``artist_name`` empty, which propagated as empty ``artist_credit``
        on materialised Albums in production until 2026-05-23. The search
        endpoint *does* include artist-credit by default, but the
        ``_materialize_fallback`` flow re-fetches each hit through this
        lookup to populate the canonical cache; missing inc= meant the
        re-fetch trashed the artist info from the search result.
        """
        await self._wait_for_rate_limit_slot()
        response = await self._client.get(
            f"/release-group/{mbid}",
            params={"fmt": "json", "inc": "artist-credits"},
        )
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

        ``score`` is populated only when MB supplies it. The search
        endpoint returns ``"score": <0-100>`` on every hit (100 = perfect
        match); the lookup endpoint omits it because there's nothing to
        compare against. For lookups we leave it ``None`` and the search
        service treats missing scores as the lowest tier.
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
        score_raw = item.get("score")
        score: int | None = None
        if isinstance(score_raw, int):
            score = score_raw
        elif isinstance(score_raw, str) and score_raw.isdigit():
            score = int(score_raw)
        cover_art_url = f"{_CAA_BASE}/release-group/{mbid}/front" if mbid else None
        return CatalogAlbum(
            mbid=mbid or None,
            discogs_release_id=None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            external_ids={"mbid": mbid} if mbid else {},
            score=score,
        )


__all__ = ["MusicBrainzCatalogProvider"]
