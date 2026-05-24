"""Contract tests for :class:`DiscogsCatalogProvider` — T049a / T049b.

P4 test-first sequence:

1. T049a (this file) — written BEFORE the impl exists. All tests MUST fail
   at collection (``ImportError``).
2. T049b fills in the impl. Re-running this file MUST yield all-green.

Discogs is the PRIMARY external source post-search-fix-v4 (2026-05-24).
Searches use ``type=master`` and pass Discogs's native ranking through
unchanged. When ``DISCOGS_API_TOKEN`` is unset the provider must run in
"disabled mode" and return ``[]`` / ``None`` rather than raising —
search/lookups simply degrade gracefully to the MusicBrainz fallback.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from auxd_api.lib.resilience import (
    InMemoryCircuitBreakerStore,
    get_default_store,
    set_default_store,
)
from auxd_api.providers.discogs import DiscogsCatalogProvider
from auxd_api.providers.errors import (
    ProviderRateLimited,
    ProviderUnavailable,
)
from auxd_api.settings import get_settings

DISCOGS_BASE = "https://api.discogs.com"
TEST_TOKEN = "test_pat_token_xxxxxxxxxxxx"


@pytest.fixture(autouse=True)
def _clean_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> Iterator[None]:
    """Isolate Settings construction from the user's local ``.env`` file.

    Mirrors :mod:`tests.unit.test_settings`: switches CWD to ``tmp_path``
    so pydantic-settings can't find a real ``.env`` (which on dev
    machines may carry pre-CR-001 keys like ``SPOTIFY_INTEGRATION_ENABLED``
    that the new ``extra=forbid`` settings now reject).
    """
    # Minimum env so Settings() can construct at all.
    monkeypatch.setenv(
        "SESSION_HMAC_KEY",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  # 32 zero bytes
    )
    monkeypatch.setenv(
        "TOKEN_ENCRYPTION_KEY",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  # 32 zero bytes
    )
    monkeypatch.delenv("DISCOGS_API_TOKEN", raising=False)
    # Strip any stray pre-CR-001 keys that might still be in the host env.
    for key in (
        "SPOTIFY_INTEGRATION_ENABLED",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_store() -> Iterator[None]:
    original = get_default_store()
    set_default_store(InMemoryCircuitBreakerStore())
    yield
    set_default_store(original)


@pytest.fixture
def _no_sleep() -> Iterator[None]:
    """Skip retry backoff sleeps for retry-driven tests."""
    with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture
def _with_token(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DISCOGS_API_TOKEN", TEST_TOKEN)
    get_settings.cache_clear()
    yield


@pytest.fixture
def _without_token(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("DISCOGS_API_TOKEN", raising=False)
    get_settings.cache_clear()
    yield


def _master_search_payload() -> dict[str, object]:
    """A canonical Discogs ``/database/search?type=master`` result."""
    return {
        "results": [
            {
                "id": 249504,
                "title": "Radiohead - OK Computer",
                "year": 1997,
                "type": "master",
                "cover_image": "https://img.discogs.com/abc/front.jpg",
                "community": {"have": 50000, "want": 12000},
            },
        ]
    }


def _master_detail_payload() -> dict[str, object]:
    """A canonical Discogs ``/masters/{id}`` detail payload."""
    return {
        "id": 249504,
        "title": "OK Computer",
        "year": 1997,
        "artists": [{"name": "Radiohead"}],
        "images": [{"uri": "https://img.discogs.com/abc/front.jpg"}],
        "community": {"have": 50000, "want": 12000},
    }


def _release_payload() -> dict[str, object]:
    """A canonical Discogs ``/releases/{id}`` detail payload — kept for
    the backward-compat ``provider='discogs'`` lookup branch.
    """
    return {
        "id": 249504,
        "title": "OK Computer",
        "year": 1997,
        "artists": [{"name": "Radiohead"}],
        "images": [{"uri": "https://img.discogs.com/abc/front.jpg"}],
    }


class TestDiscogsCatalogProvider:
    # ------------------------------------------------------------------
    # search_albums — v4 master-based search
    # ------------------------------------------------------------------

    @respx.mock
    async def test_search_albums_returns_canonical_master_list(self, _with_token: None) -> None:
        """Master search yields a CatalogAlbum with ``discogs_master_id`` set."""
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json=_master_search_payload())
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("Radiohead OK Computer")
        finally:
            await provider.aclose()
        assert len(results) == 1
        first = results[0]
        assert first.discogs_master_id == "249504"
        assert first.discogs_release_id is None
        assert first.title == "OK Computer"
        assert first.artist_name == "Radiohead"
        assert first.release_year == 1997
        assert first.community_have == 50000
        assert first.external_ids == {"discogs_master": "249504"}
        assert first.mbid is None  # MBID reconciliation happens later in T065
        # No relevance score — Discogs's master ranking is implicit.
        assert first.score is None

    @respx.mock
    async def test_search_albums_uses_master_type_query(self, _with_token: None) -> None:
        """Post-search-fix-v4: ``search_albums`` MUST issue a single
        ``type=master`` query — no parallel title/artist calls, no
        ``type=release`` request.

        Discogs's master search ranks by popularity + relevance
        natively; passing the result order through unchanged IS the
        algorithm the user has endorsed.
        """
        route = respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json={"results": []})
        )
        provider = DiscogsCatalogProvider()
        try:
            await provider.search_albums("Graduation")
        finally:
            await provider.aclose()
        assert route.call_count == 1
        params = dict(route.calls.last.request.url.params)
        assert params["q"] == "Graduation"
        assert params["type"] == "master"
        assert "per_page" in params
        # Post-2026-05-24: sort by community wantlist desc — the user's
        # "Most Wanted" preference. Discogs's default ``sort=score``
        # was producing niche-title-first ordering for queries like
        # "to pimp"; ``sort=want`` aligns with discogs.com Most Wanted.
        assert params["sort"] == "want"
        assert params["sort_order"] == "desc"
        # No leftover release-based parameters from the v3 implementation.
        assert "release_title" not in params
        assert "artist" not in params

    @respx.mock
    async def test_map_master_search_result_extracts_master_id(self, _with_token: None) -> None:
        """A master search response with ``id=123`` maps to
        ``CatalogAlbum.discogs_master_id="123"`` and
        ``discogs_release_id=None``.
        """
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "id": 123,
                            "title": "Artist - Title",
                            "year": 2020,
                            "type": "master",
                        }
                    ]
                },
            )
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("anything")
        finally:
            await provider.aclose()
        assert len(results) == 1
        assert results[0].discogs_master_id == "123"
        assert results[0].discogs_release_id is None

    @respx.mock
    async def test_map_master_search_result_extracts_community_have(
        self, _with_token: None
    ) -> None:
        """``community.have`` in a master search result populates
        :class:`CatalogAlbum.community_have`. Missing community blocks
        leave the field ``None``.
        """
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "title": "Artist - With Have",
                            "year": 2020,
                            "type": "master",
                            "community": {"have": 5000, "want": 200},
                        },
                        {
                            "id": 2,
                            "title": "Artist - Without Community",
                            "year": 2021,
                            "type": "master",
                        },
                    ]
                },
            )
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("anything")
        finally:
            await provider.aclose()
        assert results[0].community_have == 5000
        assert results[1].community_have is None

    @respx.mock
    async def test_map_master_search_result_parses_artist_title_split(
        self, _with_token: None
    ) -> None:
        """Title formatted ``"Artist - Title"`` is split on the first
        " - " into ``artist_name`` and ``title``.
        """
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "title": "Kanye West - Graduation",
                            "year": 2007,
                            "type": "master",
                        }
                    ]
                },
            )
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("graduation")
        finally:
            await provider.aclose()
        assert results[0].artist_name == "Kanye West"
        assert results[0].title == "Graduation"

    @respx.mock
    async def test_search_requires_personal_access_token(self, _with_token: None) -> None:
        route = respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json={"results": []})
        )
        provider = DiscogsCatalogProvider()
        try:
            await provider.search_albums("anything")
        finally:
            await provider.aclose()
        assert route.called
        auth = route.calls.last.request.headers.get("authorization", "")
        assert auth.startswith("Discogs token=")
        assert TEST_TOKEN in auth

    @respx.mock
    async def test_propagates_provider_unavailable_on_5xx(
        self, _with_token: None, _no_sleep: None
    ) -> None:
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(503, json={"error": "down"})
        )
        provider = DiscogsCatalogProvider()
        try:
            with pytest.raises(ProviderUnavailable):
                await provider.search_albums("anything")
        finally:
            await provider.aclose()

    @respx.mock
    async def test_propagates_provider_rate_limited_on_429(self, _with_token: None) -> None:
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(429, json={"error": "rate"})
        )
        provider = DiscogsCatalogProvider()
        try:
            with pytest.raises(ProviderRateLimited):
                await provider.search_albums("anything")
        finally:
            await provider.aclose()

    async def test_returns_empty_list_when_token_is_unset(self, _without_token: None) -> None:
        """Token unset → disabled mode: searches return [], lookups return None."""
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("anything")
            lookup = await provider.get_album_by_external_id("discogs", "249504")
            master_lookup = await provider.get_album_by_external_id("discogs_master", "249504")
            mbid_lookup = await provider.get_album_by_mbid("xxx")
        finally:
            await provider.aclose()
        assert results == []
        assert lookup is None
        assert master_lookup is None
        assert mbid_lookup is None

    @respx.mock
    async def test_get_album_by_mbid_returns_none(self, _with_token: None) -> None:
        """Discogs has no MBID→release mapping; get_album_by_mbid is a no-op."""
        provider = DiscogsCatalogProvider()
        try:
            result = await provider.get_album_by_mbid("b1392450-e666-3926-a536-22c65f834433")
        finally:
            await provider.aclose()
        assert result is None

    # ------------------------------------------------------------------
    # get_album_by_external_id — master + release branches
    # ------------------------------------------------------------------

    @respx.mock
    async def test_get_album_by_external_id_master_branch(self, _with_token: None) -> None:
        """``provider="discogs_master"`` calls ``/masters/{id}`` and returns
        a mapped result. Master detail has the richer schema:
        ``artists`` is an array of objects (not a joined string) and
        ``community`` is always populated on real masters.
        """
        route = respx.get(f"{DISCOGS_BASE}/masters/249504").mock(
            return_value=Response(200, json=_master_detail_payload())
        )
        provider = DiscogsCatalogProvider()
        try:
            album = await provider.get_album_by_external_id("discogs_master", "249504")
        finally:
            await provider.aclose()
        assert route.called
        assert album is not None
        assert album.discogs_master_id == "249504"
        assert album.discogs_release_id is None
        assert album.title == "OK Computer"
        assert album.artist_name == "Radiohead"
        assert album.release_year == 1997
        assert album.cover_art_url == "https://img.discogs.com/abc/front.jpg"
        assert album.community_have == 50000

    @respx.mock
    async def test_get_album_by_external_id_master_branch_404_returns_none(
        self, _with_token: None
    ) -> None:
        """A 404 from ``/masters/{id}`` surfaces as ``None`` — a missing
        master is a normal lookup outcome, not an error.
        """
        respx.get(f"{DISCOGS_BASE}/masters/missing").mock(
            return_value=Response(404, json={"message": "not found"})
        )
        provider = DiscogsCatalogProvider()
        try:
            album = await provider.get_album_by_external_id("discogs_master", "missing")
        finally:
            await provider.aclose()
        assert album is None

    @respx.mock
    async def test_get_album_by_external_id_release_branch_still_works(
        self, _with_token: None
    ) -> None:
        """The release-id branch (``provider="discogs"``) remains for
        backward compatibility with code that still carries Discogs
        release identifiers (e.g. older Album rows pre-v4).
        """
        respx.get(f"{DISCOGS_BASE}/releases/249504").mock(
            return_value=Response(200, json=_release_payload())
        )
        provider = DiscogsCatalogProvider()
        try:
            album = await provider.get_album_by_external_id("discogs", "249504")
        finally:
            await provider.aclose()
        assert album is not None
        assert album.discogs_release_id == "249504"
        assert album.discogs_master_id is None
        assert album.title == "OK Computer"
        assert album.artist_name == "Radiohead"
        assert album.release_year == 1997
        assert album.cover_art_url == "https://img.discogs.com/abc/front.jpg"

    async def test_get_album_by_external_id_unknown_provider_returns_none(
        self, _with_token: None
    ) -> None:
        """An unknown ``provider`` value returns ``None`` rather than
        falling through to an unintended endpoint.
        """
        provider = DiscogsCatalogProvider()
        try:
            album = await provider.get_album_by_external_id("spotify", "anything")
        finally:
            await provider.aclose()
        assert album is None

    # ------------------------------------------------------------------
    # get_community_data — retained for future enrichment paths
    # ------------------------------------------------------------------

    @respx.mock
    async def test_get_community_data_extracts_have_count(self, _with_token: None) -> None:
        """``community.have`` is extracted as the popularity signal."""
        respx.get(f"{DISCOGS_BASE}/releases/249504").mock(
            return_value=Response(
                200,
                json={"id": 249504, "community": {"have": 5000, "want": 2000}},
            )
        )
        provider = DiscogsCatalogProvider()
        try:
            have = await provider.get_community_data("249504")
        finally:
            await provider.aclose()
        assert have == 5000

    @respx.mock
    async def test_get_community_data_returns_none_on_404(self, _with_token: None) -> None:
        """404 means the release was deleted; surface as ``None``, not raise."""
        respx.get(f"{DISCOGS_BASE}/releases/missing").mock(
            return_value=Response(404, json={"message": "not found"})
        )
        provider = DiscogsCatalogProvider()
        try:
            have = await provider.get_community_data("missing")
        finally:
            await provider.aclose()
        assert have is None

    @respx.mock
    async def test_get_community_data_returns_none_on_missing_community(
        self, _with_token: None
    ) -> None:
        """Payload without a ``community`` block surfaces ``None``."""
        respx.get(f"{DISCOGS_BASE}/releases/249504").mock(
            return_value=Response(200, json={"id": 249504})
        )
        provider = DiscogsCatalogProvider()
        try:
            have = await provider.get_community_data("249504")
        finally:
            await provider.aclose()
        assert have is None

    async def test_get_community_data_returns_none_when_disabled(
        self, _without_token: None
    ) -> None:
        """Token unset → graceful disabled-mode return of ``None``."""
        provider = DiscogsCatalogProvider()
        try:
            have = await provider.get_community_data("249504")
        finally:
            await provider.aclose()
        assert have is None
