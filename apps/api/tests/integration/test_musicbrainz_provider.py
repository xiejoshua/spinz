"""Contract tests for :class:`MusicBrainzCatalogProvider` — T048 / T049.

P4 test-first sequence:

1. T048 (this file) — written BEFORE the impl exists. All tests MUST fail
   with ``ImportError`` / ``AttributeError`` at collection or first-run.
2. T049 fills in the impl. Re-running this file MUST then yield all-green.

Tests use :mod:`respx` to mock the underlying HTTP transport — the
``ResilienceTransport`` is composed unchanged so the resilience semantics
(retry on 5xx, no retry on 429, observability) are exercised end-to-end.
"""

from __future__ import annotations

import asyncio
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
from auxd_api.providers.errors import (
    ProviderRateLimited,
    ProviderUnavailable,
)
from auxd_api.providers.musicbrainz import MusicBrainzCatalogProvider

MB_BASE = "https://musicbrainz.org/ws/2"

OK_COMPUTER_MBID = "b1392450-e666-3926-a536-22c65f834433"


@pytest.fixture(autouse=True)
def _isolate_store() -> Iterator[None]:
    """Fresh in-memory breaker store per test."""
    original = get_default_store()
    set_default_store(InMemoryCircuitBreakerStore())
    yield
    set_default_store(original)


@pytest.fixture
def _no_sleep() -> Iterator[None]:
    """Skip retry-backoff sleeps; opt-in for retry-driven tests only."""
    with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock):
        yield


def _search_payload() -> dict[str, object]:
    return {
        "release-groups": [
            {
                "id": OK_COMPUTER_MBID,
                "title": "OK Computer",
                "first-release-date": "1997-05-21",
                "artist-credit": [{"name": "Radiohead"}],
            },
            {
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "Kid A",
                "first-release-date": "2000-10-02",
                "artist-credit": [{"name": "Radiohead"}],
            },
        ],
    }


def _lookup_payload() -> dict[str, object]:
    return {
        "id": OK_COMPUTER_MBID,
        "title": "OK Computer",
        "first-release-date": "1997-05-21",
        "artist-credit": [{"name": "Radiohead"}],
    }


class TestMusicBrainzCatalogProvider:
    @respx.mock
    async def test_search_albums_returns_canonical_list(self) -> None:
        respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(200, json=_search_payload())
        )
        provider = MusicBrainzCatalogProvider()
        try:
            results = await provider.search_albums("Radiohead OK Computer")
        finally:
            await provider.aclose()

        assert len(results) == 2
        first = results[0]
        assert first.mbid == OK_COMPUTER_MBID
        assert first.title == "OK Computer"
        assert first.artist_name == "Radiohead"
        assert first.release_year == 1997
        assert first.external_ids == {"mbid": OK_COMPUTER_MBID}
        assert first.cover_art_url == (
            f"https://coverartarchive.org/release-group/{OK_COMPUTER_MBID}/front"
        )

    @respx.mock
    async def test_get_album_by_mbid_returns_album(self) -> None:
        route = respx.get(f"{MB_BASE}/release-group/{OK_COMPUTER_MBID}").mock(
            return_value=Response(200, json=_lookup_payload())
        )
        provider = MusicBrainzCatalogProvider()
        try:
            album = await provider.get_album_by_mbid(OK_COMPUTER_MBID)
        finally:
            await provider.aclose()
        assert album is not None
        assert album.title == "OK Computer"
        assert album.artist_name == "Radiohead"
        assert album.release_year == 1997
        assert album.mbid == OK_COMPUTER_MBID
        # MB lookup MUST pass `inc=artist-credits` — without it the response
        # excludes the artist-credit array entirely and we ship empty
        # artist_credit on materialised Albums. Asserted explicitly after the
        # 2026-05-23 production incident.
        called_url = route.calls.last.request.url
        assert "inc=artist-credits" in str(called_url), (
            f"expected inc=artist-credits in lookup URL, got {called_url}"
        )

    @respx.mock
    async def test_get_album_by_mbid_returns_none_on_404(self) -> None:
        respx.get(f"{MB_BASE}/release-group/00000000-0000-0000-0000-000000000000").mock(
            return_value=Response(404, json={"error": "Not Found"})
        )
        provider = MusicBrainzCatalogProvider()
        try:
            album = await provider.get_album_by_mbid("00000000-0000-0000-0000-000000000000")
        finally:
            await provider.aclose()
        assert album is None

    @respx.mock
    async def test_search_respects_limit_param(self) -> None:
        route = respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(200, json={"release-groups": []})
        )
        provider = MusicBrainzCatalogProvider()
        try:
            await provider.search_albums("anything", limit=25)
        finally:
            await provider.aclose()

        assert route.called
        called_request = route.calls.last.request
        assert called_request.url.params["limit"] == "25"

    @respx.mock
    async def test_observes_musicbrainz_1_req_per_second_rate_limit(self) -> None:
        """Two consecutive calls must be spaced >= 1.0s apart (MB etiquette)."""
        respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(200, json={"release-groups": []})
        )
        # Use a fake clock so the test stays fast: replace asyncio.sleep with
        # a recorder so we can assert the throttle delay was scheduled.
        recorded: list[float] = []

        async def _record_sleep(delay: float) -> None:
            recorded.append(delay)

        provider = MusicBrainzCatalogProvider()
        try:
            with patch("auxd_api.providers.musicbrainz.asyncio.sleep", _record_sleep):
                await provider.search_albums("first")
                await provider.search_albums("second")
        finally:
            await provider.aclose()

        # The second call must have triggered at least one positive sleep to
        # honour the 1 req/sec pacing.
        positive_sleeps = [d for d in recorded if d > 0]
        assert positive_sleeps, "expected MusicBrainz client to pace requests (no sleep observed)"

    @respx.mock
    async def test_propagates_provider_rate_limited_on_429(self) -> None:
        respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(429, json={"error": "rate"})
        )
        provider = MusicBrainzCatalogProvider()
        try:
            with pytest.raises(ProviderRateLimited):
                await provider.search_albums("anything")
        finally:
            await provider.aclose()

    @respx.mock
    async def test_propagates_provider_unavailable_on_5xx_after_retries(
        self, _no_sleep: None
    ) -> None:
        respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(503, json={"error": "down"})
        )
        provider = MusicBrainzCatalogProvider()
        try:
            with (
                patch(
                    "auxd_api.providers.musicbrainz.asyncio.sleep",
                    new_callable=AsyncMock,
                ),
                pytest.raises(ProviderUnavailable),
            ):
                await provider.search_albums("anything")
        finally:
            await provider.aclose()

    @respx.mock
    async def test_sends_required_user_agent_header(self) -> None:
        route = respx.get(f"{MB_BASE}/release-group/{OK_COMPUTER_MBID}").mock(
            return_value=Response(200, json=_lookup_payload())
        )
        provider = MusicBrainzCatalogProvider()
        try:
            await provider.get_album_by_mbid(OK_COMPUTER_MBID)
        finally:
            await provider.aclose()
        assert route.called
        ua = route.calls.last.request.headers.get("user-agent", "")
        assert "auxd" in ua

    # Avoid an unused-import warning when asyncio is only referenced in
    # imports above for type checking.
    def test_smoketest_asyncio_imported(self) -> None:
        assert asyncio is not None
