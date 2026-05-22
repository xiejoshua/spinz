"""Discogs catalog provider — T049b (CR-001 optional fallback).

:class:`DiscogsCatalogProvider` implements the
:class:`~auxd_api.providers.base.CatalogProvider` Protocol against the
Discogs API v2 (``api.discogs.com``). It is the OPTIONAL fallback in the
catalog stack: when MusicBrainz returns thin results, search service
(T069) falls through to this provider.

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

from auxd_api.providers.base import CatalogAlbum, CatalogProvider
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
        if not self._enabled or self._client is None:
            return []
        response = await self._client.get(
            "/database/search",
            params={"q": query, "type": "release", "per_page": str(limit)},
        )
        if response.status_code >= 400:
            self._raise_for_status(response)
        payload = response.json()
        items: list[dict[str, object]] = payload.get("results", []) or []
        return [self._map_search_result(item) for item in items]

    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None:
        """Discogs has no MBID lookup; always returns ``None``.

        MBID reconciliation flows the other direction (Discogs id →
        candidate album → T065 worker queries MusicBrainz).
        """
        return None

    async def get_album_by_external_id(
        self, provider: str, external_id: str
    ) -> CatalogAlbum | None:
        if not self._enabled or self._client is None:
            return None
        if provider != "discogs":
            return None
        response = await self._client.get(f"/releases/{external_id}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            self._raise_for_status(response)
        return self._map_release(response.json())

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
    def _map_search_result(item: dict[str, object]) -> CatalogAlbum:
        """Map a Discogs ``/database/search`` result to :class:`CatalogAlbum`.

        Discogs search results have a different shape from release detail
        lookups: ``title`` is ``"Artist - Title"`` (joined), and there is
        no ``artists`` array. We split on the first " - " to recover the
        artist/title pair; if no separator is present, the whole string
        becomes the title.
        """
        release_id = item.get("id")
        release_id_str = str(release_id) if release_id is not None else ""
        raw_title = str(item.get("title", ""))
        artist_name = ""
        title = raw_title
        if " - " in raw_title:
            artist_part, _, title_part = raw_title.partition(" - ")
            artist_name = artist_part.strip()
            title = title_part.strip()
        year = item.get("year")
        release_year: int | None = None
        if isinstance(year, int):
            release_year = year
        elif isinstance(year, str) and year.isdigit():
            release_year = int(year)
        cover_uri_raw = item.get("cover_image")
        cover_art_url: str | None = (
            cover_uri_raw if isinstance(cover_uri_raw, str) and cover_uri_raw else None
        )
        return CatalogAlbum(
            mbid=None,
            discogs_release_id=release_id_str or None,
            title=title,
            artist_name=artist_name,
            release_year=release_year,
            cover_art_url=cover_art_url,
            external_ids={"discogs": release_id_str} if release_id_str else {},
        )

    @staticmethod
    def _map_release(item: dict[str, object]) -> CatalogAlbum:
        """Map a Discogs ``/releases/{id}`` detail payload to :class:`CatalogAlbum`."""
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
