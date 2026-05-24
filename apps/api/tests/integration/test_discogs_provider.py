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
        # Post-2026-05-24 fix: ``search_albums`` runs two parallel calls
        # (title + artist). The mock payload here covers both, so we get
        # one unique release id back across both branches.
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

    @respx.mock
    async def test_search_issues_parallel_title_and_artist_calls(self, _with_token: None) -> None:
        """Post-2026-05-24 fix: ``search_albums`` MUST issue two requests
        — one with ``release_title=<q>`` and one with ``artist=<q>``.

        Discogs's bare ``q=<q>`` form returns ties in arbitrary order;
        the structured params return ties ordered by ``community.have``
        count, which is the popularity tiebreaker MB lacks.
        """
        route = respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json={"results": []})
        )
        provider = DiscogsCatalogProvider()
        try:
            await provider.search_albums("Graduation")
        finally:
            await provider.aclose()
        # Both calls should have hit the same endpoint with different params.
        assert route.call_count == 2
        sent_params: list[dict[str, str]] = [dict(call.request.url.params) for call in route.calls]
        # The two params dicts collectively cover ``release_title`` and ``artist``.
        param_keys: set[str] = set()
        for params in sent_params:
            # Each call must have exactly one of the structured keys, plus
            # ``type`` and ``per_page`` — the bare ``q`` key must NOT appear.
            assert "q" not in params
            assert params["type"] == "release"
            assert "per_page" in params
            for key in ("release_title", "artist"):
                if key in params:
                    param_keys.add(key)
        assert param_keys == {"release_title", "artist"}, (
            f"expected both release_title and artist branches, got {param_keys}"
        )

    @respx.mock
    async def test_search_dedupes_release_present_in_both_branches(self, _with_token: None) -> None:
        """A release whose id appears in BOTH the title and artist
        branches must surface exactly once in the merged result. Without
        the dedup the same album would appear twice (and waste a slot
        of the caller's ``limit``).
        """
        shared_release = {
            "id": 249504,
            "title": "Radiohead - OK Computer",
            "year": 1997,
            "type": "release",
        }
        respx.get(f"{DISCOGS_BASE}/database/search").mock(
            return_value=Response(200, json={"results": [shared_release]})
        )
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("Radiohead")
        finally:
            await provider.aclose()
        assert len(results) == 1
        assert results[0].discogs_release_id == "249504"

    @respx.mock
    async def test_search_preserves_branch_relative_order_for_popularity(
        self, _with_token: None
    ) -> None:
        """Each Discogs branch returns results in popularity-rank order
        (Discogs sorts structured queries by ``community.have`` count).
        The merge must preserve that order within each branch.
        """
        # Title branch hands back A (most popular), B (less popular).
        title_branch = {
            "results": [
                {"id": 1, "title": "Artist - Title A", "year": 2010, "type": "release"},
                {"id": 2, "title": "Artist - Title B", "year": 2011, "type": "release"},
            ]
        }
        # Artist branch hands back C, D in popularity order.
        artist_branch = {
            "results": [
                {"id": 3, "title": "Artist - Title C", "year": 2012, "type": "release"},
                {"id": 4, "title": "Artist - Title D", "year": 2013, "type": "release"},
            ]
        }

        # Return different payloads per call by using a side-effect on
        # respx — alternates between the two branches in call order.
        responses_iter = iter([title_branch, artist_branch])

        def _handler(request: object) -> Response:
            return Response(200, json=next(responses_iter))

        respx.get(f"{DISCOGS_BASE}/database/search").mock(side_effect=_handler)
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("Artist")
        finally:
            await provider.aclose()
        # Title branch comes first (most users mean a title when they
        # type a string); within each branch the popularity order is
        # preserved.
        titles = [r.title for r in results]
        assert titles == ["Title A", "Title B", "Title C", "Title D"]

    @respx.mock
    async def test_search_truncates_to_caller_limit(self, _with_token: None) -> None:
        """The merged list must not exceed the caller's ``limit`` even
        when both branches return a full page each.
        """
        # Both branches return 3 unique results — 6 total candidates.
        branch_payload = {
            "results": [
                {"id": 1, "title": "Artist - T1", "year": 2010, "type": "release"},
                {"id": 2, "title": "Artist - T2", "year": 2011, "type": "release"},
                {"id": 3, "title": "Artist - T3", "year": 2012, "type": "release"},
            ]
        }
        artist_branch = {
            "results": [
                {"id": 4, "title": "Artist - T4", "year": 2013, "type": "release"},
                {"id": 5, "title": "Artist - T5", "year": 2014, "type": "release"},
                {"id": 6, "title": "Artist - T6", "year": 2015, "type": "release"},
            ]
        }
        responses_iter = iter([branch_payload, artist_branch])

        def _handler(request: object) -> Response:
            return Response(200, json=next(responses_iter))

        respx.get(f"{DISCOGS_BASE}/database/search").mock(side_effect=_handler)
        provider = DiscogsCatalogProvider()
        try:
            results = await provider.search_albums("Artist", limit=4)
        finally:
            await provider.aclose()
        assert len(results) == 4

    # ------------------------------------------------------------------
    # v3 (Fix B) — ``get_community_data`` popularity-enrichment endpoint
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
