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
from auxd_api.providers.musicbrainz import (
    MusicBrainzCatalogProvider,
    _build_mb_lucene_query,
    _escape_lucene,
)

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
                "score": 100,
            },
            {
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "Kid A",
                "first-release-date": "2000-10-02",
                "artist-credit": [{"name": "Radiohead"}],
                "score": 85,
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
        # MB search hits MUST carry the relevance score so the search
        # service can re-rank fallback-tier results (post-2026-05-24
        # fix for the "canonical releases buried under obscure ones"
        # bug). 100 = perfect match per MB's own scale.
        assert first.score == 100
        assert results[1].score == 85

    @respx.mock
    async def test_search_album_score_missing_is_none(self) -> None:
        """Older MB records may omit ``score`` — provider MUST default to
        ``None`` rather than crashing or coercing to 0 (which would
        wrongly sort them ahead of legitimate low-score hits).
        """
        respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(
                200,
                json={
                    "release-groups": [
                        {
                            "id": OK_COMPUTER_MBID,
                            "title": "OK Computer",
                            "first-release-date": "1997-05-21",
                            "artist-credit": [{"name": "Radiohead"}],
                            # No ``score`` key.
                        }
                    ]
                },
            )
        )
        provider = MusicBrainzCatalogProvider()
        try:
            results = await provider.search_albums("Radiohead OK Computer")
        finally:
            await provider.aclose()
        assert len(results) == 1
        assert results[0].score is None

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
        # MB lookup endpoint never returns a ``score`` (nothing to compare
        # against on a single-row fetch); ensure the mapping reflects that
        # rather than fabricating a fake score.
        assert album.score is None

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

    @respx.mock
    async def test_search_sends_structured_lucene_query(self) -> None:
        """Post-2026-05-24 fix: MB search MUST send a structured Lucene
        query of the form ``release:"<q>" OR artist:"<q>"`` instead of
        the bare ``query=<q>`` form. Without this disambiguation the bare
        form returned niche tributes titled "Kanye West" ahead of
        canonical Kanye albums for the input ``"kanye west"``.
        """
        route = respx.get(f"{MB_BASE}/release-group").mock(
            return_value=Response(200, json={"release-groups": []})
        )
        provider = MusicBrainzCatalogProvider()
        try:
            await provider.search_albums("kanye west")
        finally:
            await provider.aclose()
        assert route.called
        sent_query = route.calls.last.request.url.params["query"]
        # Expected exact shape: release:"kanye west" OR artist:"kanye west"
        assert sent_query == 'release:"kanye west" OR artist:"kanye west"', (
            f"expected structured Lucene query, got {sent_query!r}"
        )

    # Avoid an unused-import warning when asyncio is only referenced in
    # imports above for type checking.
    def test_smoketest_asyncio_imported(self) -> None:
        assert asyncio is not None


class TestMusicBrainzLuceneQueryBuilder:
    """Unit-style coverage for the structured-query helpers (Fix 1)."""

    def test_build_query_for_artist_typical_input(self) -> None:
        assert _build_mb_lucene_query("kanye west") == 'release:"kanye west" OR artist:"kanye west"'

    def test_build_query_for_title_typical_input(self) -> None:
        assert _build_mb_lucene_query("Graduation") == 'release:"Graduation" OR artist:"Graduation"'

    def test_build_query_trims_whitespace(self) -> None:
        # User-typed leading/trailing whitespace must be normalised before
        # interpolation so we don't ship `release:"  q  "` to MB.
        assert (
            _build_mb_lucene_query("  Radiohead  ") == 'release:"Radiohead" OR artist:"Radiohead"'
        )

    def test_escape_lucene_passes_through_safe_text(self) -> None:
        assert _escape_lucene("Radiohead") == "Radiohead"

    def test_escape_lucene_escapes_plus(self) -> None:
        # ``+`` is Lucene-special; if interpolated raw it forces the next
        # token to be present, which would break the OR clause.
        assert _escape_lucene("Daft Punk + Justice") == r"Daft Punk \+ Justice"

    def test_escape_lucene_escapes_quotes_and_meta(self) -> None:
        # Embedded double-quotes would break out of the quoted phrase
        # clause; the backslash escape keeps the user's input contained.
        assert _escape_lucene('Say "Hi" (Mix)') == r"Say \"Hi\" \(Mix\)"

    def test_escape_lucene_escapes_field_separator(self) -> None:
        # The ``:`` character is the Lucene field separator. Without
        # escaping, a user input like ``artist:foo`` would let the
        # caller inject an alternate field clause and bypass our
        # structured-query design.
        assert _escape_lucene("artist:foo") == r"artist\:foo"

    def test_build_query_escapes_special_chars_inside_phrase(self) -> None:
        # Smoke test the integration: the builder must propagate escapes
        # into the final ``release:"..." OR artist:"..."`` shape.
        built = _build_mb_lucene_query("Daft Punk + Justice")
        assert "release:" in built
        assert "artist:" in built
        assert r"\+" in built
