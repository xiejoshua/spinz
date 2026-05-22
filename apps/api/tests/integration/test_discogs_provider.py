"""Contract tests for :class:`DiscogsCatalogProvider` — T049a / T049b.

P4 test-first sequence:

1. T049a (this file) — written BEFORE the impl exists. All tests MUST fail
   at collection (``ImportError``).
2. T049b fills in the impl. Re-running this file MUST yield all-green.

Discogs is an OPTIONAL fallback: when ``DISCOGS_API_TOKEN`` is unset the
provider must run in "disabled mode" and return ``[]`` / ``None`` rather
than raising — search/lookups simply degrade gracefully.
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


def _search_payload() -> dict[str, object]:
    return {
        "results": [
            {
                "id": 249504,
                "title": "Radiohead - OK Computer",
                "year": 1997,
                "type": "release",
            },
        ]
    }


def _release_payload() -> dict[str, object]:
    return {
        "id": 249504,
        "title": "OK Computer",
        "year": 1997,
        "artists": [{"name": "Radiohead"}],
        "images": [{"uri": "https://img.discogs.com/abc/front.jpg"}],
    }


class TestDiscogsCatalogProvider:
    @respx.mock
    async def test_search_albums_returns_canonical_list(self, _with_token: None) -> None:
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json=_search_payload())
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("Radiohead OK Computer")
        finally:
            await provider.aclose()
        assert len(results) == 1
        first = results[0]
        assert first.discogs_release_id == "249504"
        assert first.title == "OK Computer"
        assert first.artist_name == "Radiohead"
        assert first.release_year == 1997
        assert first.external_ids == {"discogs": "249504"}
        assert first.mbid is None  # MBID reconciliation happens later in T065

    @respx.mock
    async def test_get_album_by_external_id_returns_release(self, _with_token: None) -> None:
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
        assert album.title == "OK Computer"
        assert album.artist_name == "Radiohead"
        assert album.release_year == 1997
        assert album.cover_art_url == "https://img.discogs.com/abc/front.jpg"

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
            mbid_lookup = await provider.get_album_by_mbid("xxx")
        finally:
            await provider.aclose()
        assert results == []
        assert lookup is None
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
