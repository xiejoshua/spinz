"""Discogs catalog provider — T049b (CR-001 optional fallback).

:class:`DiscogsCatalogProvider` implements the
:class:`~auxd_api.providers.base.CatalogProvider` Protocol against the
Discogs API v2 (``api.discogs.com``).

Search-fix v4 (2026-05-24) — Discogs masters as the primary external
source. We dropped the v3 parallel ``release_title=`` + ``artist=`` calls
because the merge layer above still failed on the user's "Graduation" /
"kanye west" queries even with heuristic boosts + community.have
enrichment. The v4 design delegates ranking ENTIRELY to Discogs by
searching ``type=master`` and passing the result order through unchanged.
Discogs's master search already factors in popularity + relevance — this
IS the algorithm the user has explicitly endorsed (results return in the
same order as discogs.com).

Disabled-mode contract
======================
``DISCOGS_API_TOKEN`` is optional (see :mod:`auxd_api.settings`). When
unset, the provider must NOT raise — every protocol method returns the
empty/None equivalent. Concrete behaviour:

* ``search_albums(...)`` → ``[]``
* ``get_album_by_mbid(...)`` → ``None`` (Discogs has no MBID lookup anyway)
* ``get_album_by_external_id(...)`` → ``None``

This degraded mode keeps the search pipeline (T069) working as
MusicBrainz-only when an operator chooses not to provision a Discogs
Personal Access Token.

Authentication
==============
Discogs uses a custom header scheme: ``Authorization: Discogs token={pat}``.
The PAT is supplied via ``DISCOGS_API_TOKEN`` (see plan §17.2).
"""

from __future__ import annotations

import httpx

from auxd_api.providers.base import CatalogAlbum, CatalogProvider, CatalogTrack


def _parse_discogs_duration(value: object) -> int | None:
    """Parse a Discogs "mm:ss" / "h:mm:ss" duration into milliseconds.

    Returns None for empty / malformed values — Discogs sometimes omits
    duration on bonus tracks and bootlegs.
    """
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) < 2 or len(parts) > 3:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if any(n < 0 for n in nums):
        return None
    if len(nums) == 2:
        minutes, seconds = nums
        return (minutes * 60 + seconds) * 1000
    hours, minutes, seconds = nums
    return (hours * 3600 + minutes * 60 + seconds) * 1000
from auxd_api.providers.errors import ProviderRateLimited, ProviderUnavailable
from auxd_api.providers.transport import build_async_client
from auxd_api.settings import get_settings

_USER_AGENT = "auxd/0.0.0 (https://auxd.xiejoshua.com)"
_BASE_URL = "https://api.discogs.com"


class DiscogsCatalogProvider(CatalogProvider):
    """Catalog provider backed by the Discogs API.

    When the ``DISCOGS_API_TOKEN`` setting is unset, the provider runs in
    "disabled mode" — every protocol method returns the empty/None
    equivalent without making a network call.
    """

    def __init__(
        self,
        *,
        inner_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._token: str | None = settings.DISCOGS_API_TOKEN
        self._enabled = self._token is not None
        if self._enabled:
            assert self._token is not None  # narrowing for mypy
            extra_headers = {"Authorization": f"Discogs token={self._token}"}
            self._client: httpx.AsyncClient | None = build_async_client(
                base_url=_BASE_URL,
                provider_name="discogs",
                user_agent=_USER_AGENT,
                timeout_seconds=10.0,
                retry_attempts=3,
                extra_headers=extra_headers,
                inner_transport=inner_transport,
            )
        else:
            self._client = None

    async def aclose(self) -> None:
        """Release the underlying httpx client, if any. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> DiscogsCatalogProvider:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # CatalogProvider protocol
    # ------------------------------------------------------------------

    async def search_albums(self, query: str, limit: int = 10) -> list[CatalogAlbum]:
        """Search Discogs masters by free-text query, sorted by community wantlist.

        Uses ``/database/search?q=<q>&type=master&per_page=<limit>
        &sort=want&sort_order=desc`` — Discogs masters are canonical
        album entries (one per album, not per pressing). Discogs's
        default ``sort=score`` ordering scored matches by relevance, but
        operator + user testing on 2026-05-24 showed that picked up
        niche masters whose titles happened to contain the query terms
        ahead of the actual popular work (e.g. obscure "Pimp To Eat"
        ahead of canonical "To Pimp a Butterfly"). Switching to
        ``sort=want`` ranks by aggregate wantlist count across all
        pressings of the master, which is the strongest popularity
        signal Discogs exposes through the public API and aligns with
        the user-reported behaviour of discogs.com's "Most Wanted" view.

        Returns :class:`CatalogAlbum` rows with ``discogs_master_id``
        populated; ``discogs_release_id`` is ``None`` for master hits
        (look up via ``master_id`` if a specific pressing is needed
        later). ``community_have`` is included when Discogs returns it
        on the search response.

        Graceful empty list when token unset or provider disabled.
        """
        if not self._enabled or self._client is None:
            return []
        response = await self._client.get(
            "/database/search",
            params={
                "q": query,
                "type": "master",
                "per_page": str(limit),
                "sort": "want",
                "sort_order": "desc",
            },
        )
        if response.status_code >= 400:
            self._raise_for_status(response)
        payload = response.json()
        items: list[dict[str, object]] = payload.get("results", []) or []
        return [self._map_master_search_result(item) for item in items]

    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None:
        """Discogs has no MBID lookup; always returns ``None``.

        MBID reconciliation flows the other direction (Discogs id →
        candidate album → T065 worker queries MusicBrainz).
        """
        return None

    async def get_album_by_external_id(
        self, provider: str, external_id: str
    ) -> CatalogAlbum | None:
        """Resolve a Discogs identifier to a :class:`CatalogAlbum`.

        Two ``provider`` values are accepted at MVP:

        * ``"discogs"`` — release-id lookup via ``/releases/{id}``. Kept
          for backward compatibility and for release-detail enrichment
          paths that may still carry a release-id.
        * ``"discogs_master"`` — master-id lookup via ``/masters/{id}``,
          the primary identifier path post-search-fix-v4 (2026-05-24).

        Returns ``None`` (not raises) for 404 — a missing record is a
        normal lookup outcome.
        """
        if not self._enabled or self._client is None:
            return None
        if provider == "discogs":
            response = await self._client.get(f"/releases/{external_id}")
            if response.status_code == 404:
                return None
            if response.status_code >= 400:
                self._raise_for_status(response)
            return self._map_release(response.json())
        if provider == "discogs_master":
            response = await self._client.get(f"/masters/{external_id}")
            if response.status_code == 404:
                return None
            if response.status_code >= 400:
                self._raise_for_status(response)
            return self._map_master_detail(response.json())
        return None

    # ------------------------------------------------------------------
    # Popularity enrichment endpoint
    # ------------------------------------------------------------------

    async def get_community_data(self, release_id: str) -> int | None:
        """Return Discogs ``community.have`` for a release id, or ``None``.

        Retained from v3 for future enrichment paths even though the v4
        search flow no longer calls it. The ``/releases/{id}`` detail
        payload includes a ``community`` object with ``have`` and
        ``want`` counts; ``have`` is the number of Discogs users who
        marked the release as owned (canonical popular releases sit in
        the 50 000-200 000 range, niche bootlegs in single digits).

        Failure semantics are intentionally graceful:

        * Provider disabled (``DISCOGS_API_TOKEN`` unset) → ``None``.
        * Network error, transport-level retries exhausted → ``None``.
        * 404 (release deleted) → ``None``.
        * Any other 4xx/5xx → ``None``.
        * Payload missing or mis-typed ``community.have`` → ``None``.
        """
        if not self._enabled or self._client is None:
            return None
        try:
            response = await self._client.get(f"/releases/{release_id}")
        except Exception:
            return None
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        community = payload.get("community") if isinstance(payload, dict) else None
        if not isinstance(community, dict):
            return None
        have = community.get("have")
        if isinstance(have, int):
            return have
        if isinstance(have, str) and have.isdigit():
            return int(have)
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Map remaining non-success codes to :class:`ProviderError` types.

        The transport already maps 429 → :class:`ProviderRateLimited` and
        5xx-after-retries → :class:`ProviderUnavailable`; this is the
        defensive belt-and-braces fallback for any 4xx we didn't expect.
        """
        if response.status_code == 429:  # pragma: no cover - transport already maps
            raise ProviderRateLimited("discogs", provider="discogs")
        raise ProviderUnavailable(
            f"discogs returned {response.status_code}",
            provider="discogs",
        )

    @staticmethod
    def _map_master_search_result(item: dict[str, object]) -> CatalogAlbum:
        """Map a Discogs ``/database/search?type=master`` result to :class:`CatalogAlbum`.

        Master search results have the title formatted as
        ``"Artist - Title"`` (joined string); the ``master_id`` is in
        ``id``. Some responses include ``community: {have, want}``
        directly in the search result; extract ``have`` when present.
        """
        master_id = item.get("id")
        master_id_str = str(master_id) if master_id is not None else ""
        raw_title = str(item.get("title", ""))
        artist_name = ""
        title = raw_title
        if " - " in raw_title:
            artist_part, _, title_part = raw_title.partition(" - ")
            artist_name = artist_part.strip()
            title = title_part.strip()

        year_raw = item.get("year")
        release_year: int | None = None
        if isinstance(year_raw, int):
            release_year = year_raw
        elif isinstance(year_raw, str) and year_raw.isdigit():
            release_year = int(year_raw)

        community = item.get("community", {})
        community_have: int | None = None
        if isinstance(community, dict):
            have = community.get("have")
            if isinstance(have, int):
                community_have = have
            elif isinstance(have, str) and have.isdigit():
                community_have = int(have)

        cover_uri_raw = item.get("cover_image")
        cover_art_url: str | None = (
            cover_uri_raw if isinstance(cover_uri_raw, str) and cover_uri_raw else None
        )

        return CatalogAlbum(
            mbid=None,  # Discogs masters don't carry MBIDs in search; reconciliation later.
            discogs_release_id=None,
            discogs_master_id=master_id_str if master_id_str else None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            community_have=community_have,
            external_ids=({"discogs_master": master_id_str} if master_id_str else {}),
            score=None,  # Discogs doesn't expose a per-result relevance score.
        )

    @staticmethod
    def _map_master_detail(item: dict[str, object]) -> CatalogAlbum:
        """Map a Discogs ``/masters/{id}`` detail payload to :class:`CatalogAlbum`.

        Master detail has a richer schema than the search response —
        ``artists`` is an array of objects (not a joined string),
        ``images`` carries multiple cover URIs, and ``community`` is
        always present on real masters.
        """
        master_id = item.get("id")
        master_id_str = str(master_id) if master_id is not None else ""
        title = str(item.get("title", ""))

        artists_raw = item.get("artists")
        artist_name = ""
        if isinstance(artists_raw, list) and artists_raw:
            first = artists_raw[0]
            if isinstance(first, dict):
                name = first.get("name")
                if isinstance(name, str):
                    artist_name = name

        year = item.get("year")
        release_year: int | None = None
        if isinstance(year, int):
            release_year = year
        elif isinstance(year, str) and year.isdigit():
            release_year = int(year)

        cover_art_url: str | None = None
        images_raw = item.get("images")
        if isinstance(images_raw, list) and images_raw:
            first_image = images_raw[0]
            if isinstance(first_image, dict):
                uri = first_image.get("uri")
                if isinstance(uri, str) and uri:
                    cover_art_url = uri

        community = item.get("community", {})
        community_have: int | None = None
        if isinstance(community, dict):
            have = community.get("have")
            if isinstance(have, int):
                community_have = have
            elif isinstance(have, str) and have.isdigit():
                community_have = int(have)

        return CatalogAlbum(
            mbid=None,
            discogs_release_id=None,
            discogs_master_id=master_id_str or None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            community_have=community_have,
            external_ids=({"discogs_master": master_id_str} if master_id_str else {}),
            genres=DiscogsCatalogProvider._extract_genres(item),
            tracklist=DiscogsCatalogProvider._extract_tracklist(item),
        )

    @staticmethod
    def _extract_genres(item: dict[str, object]) -> list[str]:
        """Flatten Discogs `genres` + `styles` into one ordered list.

        Both fields can contain duplicates (e.g. "Hip Hop" in both arrays
        or capitalisation variants). We preserve insertion order, dedupe
        case-insensitively, and cap at 5 to keep the chip row sane.
        """
        out: list[str] = []
        seen: set[str] = set()
        for key in ("genres", "styles"):
            raw = item.get(key)
            if not isinstance(raw, list):
                continue
            for entry in raw:
                if not isinstance(entry, str):
                    continue
                cleaned = entry.strip()
                if not cleaned:
                    continue
                lower = cleaned.casefold()
                if lower in seen:
                    continue
                seen.add(lower)
                out.append(cleaned)
                if len(out) >= 5:
                    return out
        return out

    @staticmethod
    def _extract_tracklist(item: dict[str, object]) -> list[CatalogTrack]:
        """Pull Discogs master tracklist into CatalogTrack rows.

        Discogs encodes durations as "mm:ss" strings (sometimes "h:mm:ss"
        for long tracks). We parse into ms or leave None on malformed
        entries — the cumulative duration_ms on the album materialise
        path then sums whatever we got.

        Tracks of `type_` other than "track" (e.g. "heading", "index")
        are skipped — they're side / disc dividers, not playable items.
        """
        raw = item.get("tracklist")
        if not isinstance(raw, list):
            return []
        out: list[CatalogTrack] = []
        position = 0
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            type_ = entry.get("type_")
            if isinstance(type_, str) and type_.lower() != "track":
                continue
            title = entry.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            position += 1
            duration_ms = _parse_discogs_duration(entry.get("duration"))
            out.append(
                CatalogTrack(
                    position=position,
                    title=title.strip(),
                    duration_ms=duration_ms,
                )
            )
        return out

    @staticmethod
    def _map_release(item: dict[str, object]) -> CatalogAlbum:
        """Map a Discogs ``/releases/{id}`` detail payload to :class:`CatalogAlbum`.

        Kept for the ``provider="discogs"`` release-id branch of
        :meth:`get_album_by_external_id`. The v4 search flow uses
        :meth:`_map_master_detail` for the primary path.
        """
        release_id = item.get("id")
        release_id_str = str(release_id) if release_id is not None else ""
        title = str(item.get("title", ""))
        artists_raw = item.get("artists")
        artist_name = ""
        if isinstance(artists_raw, list) and artists_raw:
            first = artists_raw[0]
            if isinstance(first, dict):
                name = first.get("name")
                if isinstance(name, str):
                    artist_name = name
        year = item.get("year")
        release_year: int | None = None
        if isinstance(year, int):
            release_year = year
        elif isinstance(year, str) and year.isdigit():
            release_year = int(year)
        cover_art_url: str | None = None
        images_raw = item.get("images")
        if isinstance(images_raw, list) and images_raw:
            first_image = images_raw[0]
            if isinstance(first_image, dict):
                uri = first_image.get("uri")
                if isinstance(uri, str) and uri:
                    cover_art_url = uri
        return CatalogAlbum(
            mbid=None,
            discogs_release_id=release_id_str or None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            external_ids={"discogs": release_id_str} if release_id_str else {},
        )


__all__ = ["DiscogsCatalogProvider"]
