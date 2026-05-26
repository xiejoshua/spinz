"""Integration tests for the search endpoint (T069).

Post-search-fix-v4 (2026-05-24) coverage:

* Atlas-only hits (mongomock returns nothing from ``$search``, so this
  case is exercised as "no Atlas hits, fallback returns results").
* Discogs masters as the primary external source — ranking passed
  through unchanged, no resorting.
* MusicBrainz as a fallback-only tier — invoked when Atlas + Discogs
  combined yields fewer than the threshold.
* Discogs token unset → graceful-disabled mode; MB-only flow still
  returns results.
* Provider failures surface as empty/partial results with the
  report-missing CTA where appropriate.

Providers are mocked via :class:`AsyncMock` and injected via FastAPI
dependency overrides on the search router. The dedicated test app
bypasses the full DB lifespan but keeps the route + service layer
wired so the request → response shape matches production.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.dependencies import get_mirror_service
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.mb_mirror.service import AlbumMirrorService
from auxd_api.modules.mb_mirror.types import MirrorRow
from auxd_api.modules.search.routes import (
    _discogs_provider,
    _mb_provider,
)
from auxd_api.modules.search.routes import (
    router as search_router,
)
from auxd_api.providers.base import CatalogAlbum, CatalogProvider

MBID_OK = "b1392450-e666-3926-a536-22c65f834433"


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "DISCOGS_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def _clean_albums() -> AsyncIterator[None]:
    await Album.delete_all()
    yield
    await Album.delete_all()


def _make_app(
    *,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    mirror_service: AlbumMirrorService | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(search_router, prefix="/api/v1")

    async def _override_mb() -> CatalogProvider:
        return mb_provider

    async def _override_discogs() -> CatalogProvider:
        return discogs_provider

    app.dependency_overrides[_mb_provider] = _override_mb
    app.dependency_overrides[_discogs_provider] = _override_discogs
    if mirror_service is not None:
        # Feature 004 — most legacy tests run the mirror-disabled path
        # (default dep returns a service wrapping ``app.state.mirror_client``
        # which the bare ``FastAPI()`` test app never sets). New TC-1..TC-6
        # need an enabled mirror, so they pass a stub here.
        def _override_mirror() -> AlbumMirrorService:
            return mirror_service

        app.dependency_overrides[get_mirror_service] = _override_mirror
    return app


class _StubMirrorService(AlbumMirrorService):
    """Test-friendly mirror that returns a pre-seeded ``(rows, total)``
    tuple without touching Turso.

    The real service's ``search_text_with_filters`` does both the FTS5
    SELECT and the COUNT(*) over the mirror. Here we just hand back
    the rows + total the test wants to assert on.
    """

    def __init__(
        self,
        *,
        rows: list[MirrorRow] | None = None,
        total: int | None = None,
    ) -> None:
        super().__init__(client=None)
        self._stub_rows = rows or []
        self._stub_total = total if total is not None else len(self._stub_rows)

    @property
    def enabled(self) -> bool:
        return True

    async def search_text_with_filters(  # type: ignore[override]
        self,
        *,
        query: str,
        year_min: int | None,
        year_max: int | None,
        decade_buckets: set[int] | None,
        genre: str | None,
        sort_key: str,
        limit: int,
        offset: int,
    ) -> tuple[list[MirrorRow], int]:
        from auxd_api.modules.mb_mirror.service import _TOTAL_DISPLAY_CAP

        return self._stub_rows, min(self._stub_total, _TOTAL_DISPLAY_CAP)

    async def search_text(  # type: ignore[override]
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[MirrorRow]:
        # Used by legacy ``search_albums`` thin-mirror tier. Returns the
        # same stubbed rows so the orchestrator's mode-2 path materialises
        # them correctly.
        return self._stub_rows[:limit]


def _mirror_row(
    *,
    title: str,
    artist: str,
    mbid: str | None = None,
    release_year: int | None = 2015,
) -> MirrorRow:
    return MirrorRow(
        mbid=mbid or f"mb-{title.lower().replace(' ', '-')}",
        title=title,
        artist_credit=artist,
        release_year=release_year,
        primary_type="Album",
        genres="hip hop",
        cover_art_url=None,
    )


def _ok_computer_mb_hit() -> CatalogAlbum:
    """MusicBrainz-shaped hit: carries MBID, no Discogs identifiers."""
    return CatalogAlbum(
        mbid=MBID_OK,
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        external_ids={"mbid": MBID_OK},
    )


def _ok_computer_master_hit() -> CatalogAlbum:
    """Discogs-master-shaped hit: carries ``discogs_master_id``, no MBID."""
    return CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-249504",
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        cover_art_url="https://img.discogs.com/ok/front.jpg",
        community_have=50000,
        external_ids={"discogs_master": "master-249504"},
    )


@pytest.mark.asyncio
async def test_empty_query_returns_report_missing_url(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """When every provider returns no hits, surface the report-missing CTA URL."""
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "no-such-album"})
    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["report_missing_album_url"] == "/api/v1/reports/missing-album"


@pytest.mark.asyncio
async def test_search_uses_discogs_ranking_directly(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """Discogs master order is passed through unchanged — no resorting.

    Mocks Discogs returning hits in the order [TPAB-like, Graduation-like,
    MBDTF-like] and asserts the response preserves that order exactly.
    Discogs's master search already factors in popularity + relevance;
    re-sorting on our side would defeat the entire v4 design.
    """
    tpab = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-tpab",
        title="To Pimp a Butterfly",
        artist_name="Kendrick Lamar",
        release_year=2015,
        external_ids={"discogs_master": "master-tpab"},
    )
    graduation = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-grad",
        title="Graduation",
        artist_name="Kanye West",
        release_year=2007,
        external_ids={"discogs_master": "master-grad"},
    )
    mbdtf = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-mbdtf",
        title="My Beautiful Dark Twisted Fantasy",
        artist_name="Kanye West",
        release_year=2010,
        external_ids={"discogs_master": "master-mbdtf"},
    )

    discogs_returns = [tpab, graduation, mbdtf]
    by_master: dict[str, CatalogAlbum] = {
        hit.discogs_master_id: hit for hit in discogs_returns if hit.discogs_master_id is not None
    }

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = discogs_returns
    discogs_provider.get_album_by_external_id.side_effect = lambda provider, external_id: (
        by_master.get(external_id) if provider == "discogs_master" else None
    )

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "anything"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Order is EXACTLY what Discogs returned — no reordering, no
    # heuristic boosts, no popularity merge.
    assert titles == [
        "To Pimp a Butterfly",
        "Graduation",
        "My Beautiful Dark Twisted Fantasy",
    ]


@pytest.mark.asyncio
async def test_search_falls_back_to_mb_when_discogs_empty(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """When Discogs returns no master hits, the MB fallback fires.

    Pins the MB-as-fallback contract: MB is only queried when Atlas +
    Discogs combined returned fewer than ``_FALLBACK_THRESHOLD`` hits.
    """
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_mb_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_mb_hit()

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert "OK Computer" in titles
    # Persisted into catalog — a follow-up query finds the row locally.
    assert await Album.find_one(Album.mbid == MBID_OK) is not None


@pytest.mark.asyncio
async def test_search_falls_back_to_mb_when_discogs_disabled(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """A graceful-disabled Discogs (empty list) doesn't break the MB
    fallback. The provider is mocked as an empty search to mirror the
    ``DISCOGS_API_TOKEN`` unset behaviour.
    """
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_mb_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_mb_hit()

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    titles = {hit["title"] for hit in response.json()["results"]}
    assert titles == {"OK Computer"}


@pytest.mark.asyncio
async def test_search_materializes_discogs_master_as_album_row(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """Each Discogs master hit materialises into an Album row with
    ``discogs_master_id`` set and ``candidate=False``.

    Discogs masters are canonical identities (one per album across
    pressings) — not reconciliation candidates.
    """
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []

    discogs_hit = _ok_computer_master_hit()
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "ok computer"})
    assert response.status_code == 200

    row = await Album.find_one(Album.discogs_master_id == "master-249504")
    assert row is not None
    assert row.candidate is False  # masters are canonical, not reconciliation candidates
    assert row.source is AlbumSource.DISCOGS


@pytest.mark.asyncio
async def test_search_dedupes_discogs_against_mb_by_title_artist(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """Cross-source dedup: when MB returns the same canonical album that
    a Discogs master hit already added, the title/artist fallback key
    excludes the second materialisation.

    Discogs goes first (tier 2). Its hit is keyed
    ``meta:ok computer|radiohead`` because Discogs masters don't carry
    MBIDs. MB then returns the same album with an MBID; its strong
    key would be ``mbid:<MBID_OK>`` — DIFFERENT from the metadata
    key. To get correct dedup the service must check the metadata
    key BEFORE the MBID key for MB hits.

    This test deliberately sets the MB-fallback ``_FALLBACK_THRESHOLD``
    gate by giving MB only one hit (well below 5), but with Discogs
    also under threshold, MB still runs — exercising the dedup branch.
    """
    mb_hit = _ok_computer_mb_hit()
    discogs_hit = _ok_computer_master_hit()

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [mb_hit]
    mb_provider.get_album_by_mbid.return_value = mb_hit

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # OK Computer must surface exactly once. Both the strong key
    # (``mbid:...``) AND the weak key (``meta:ok computer|radiohead``)
    # are added to the seen-set when the Discogs hit is processed; MB's
    # follow-up with the same title/artist also hits the weak key.
    assert titles.count("OK Computer") == 1


@pytest.mark.asyncio
async def test_response_shape_uses_artist_name_not_artist_credit(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """The serialised search hit MUST surface ``artist_name`` (not
    ``artist_credit``) so the frontend ``SearchAlbum`` type binds the
    right field. The DB column stays ``Album.artist_credit`` but the
    wire shape pins ``artist_name`` post-2026-05-24.
    """
    discogs_hit = _ok_computer_master_hit()
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "ok computer"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    hit = body["results"][0]
    assert hit["artist_name"] == "Radiohead"
    # Legacy field name MUST NOT leak.
    assert "artist_credit" not in hit


@pytest.mark.asyncio
async def test_discogs_provider_failure_falls_through_to_mb(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """When Discogs raises a :class:`ProviderError`, the search still
    progresses to the MB fallback. A single upstream failure cannot
    crash the request.
    """
    from auxd_api.providers.errors import ProviderUnavailable

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_mb_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_mb_hit()

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.side_effect = ProviderUnavailable(
        "discogs timeout", provider="discogs"
    )

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == ["OK Computer"]


@pytest.mark.asyncio
async def test_both_providers_fail_returns_empty_with_report_url(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """When BOTH MB and Discogs raise, the response is empty + carries
    the report-missing-album CTA (no crash, no exception leak)."""
    from auxd_api.providers.errors import ProviderUnavailable

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.side_effect = ProviderUnavailable("mb down", provider="musicbrainz")
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.side_effect = ProviderUnavailable(
        "discogs down", provider="discogs"
    )

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "anything"})
    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["report_missing_album_url"] == "/api/v1/reports/missing-album"


@pytest.mark.asyncio
async def test_search_skips_discogs_hits_missing_master_id(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """A Discogs hit without ``discogs_master_id`` cannot be materialised
    and is skipped silently. Pins the contract that v4 requires the
    master id for the Discogs tier — release ids alone are not enough.
    """
    no_master = CatalogAlbum(
        mbid=None,
        discogs_release_id="release-only-no-master",
        discogs_master_id=None,
        title="No Master",
        artist_name="Test Artist",
        release_year=2020,
        external_ids={"discogs": "release-only-no-master"},
    )

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [no_master]

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "anything"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == []


@pytest.mark.asyncio
async def test_query_type_unsupported_returns_422(_clean_env: None) -> None:
    """``type=artist`` (or anything other than ``album``) → ``HTTP 422``.

    The Query pattern constraint short-circuits unsupported types at
    validation time — FastAPI surfaces that as a 422 with a structured
    error body, so this test pins the validation behaviour.
    """
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)
    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "x", "type": "artist"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Feature 004 — discover sort + counts (TC-1..TC-7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tc1_query_with_decade_reports_true_total(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-1 (US-001) — q='kanye' + decade=2010s, mirror reports 218 → response total == 218."""
    rows = [
        _mirror_row(
            title=f"Kanye Album {i}",
            artist="Kanye West",
            mbid=f"mb-kanye-{i}",
            release_year=2015,
        )
        for i in range(50)
    ]
    mirror = _StubMirrorService(rows=rows, total=218)
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get(
        "/api/v1/search",
        params={"q": "kanye", "decade": "2010s", "limit": 50},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 218
    assert body["has_more"] is True  # 50 returned, 168 more available


@pytest.mark.asyncio
async def test_tc2_kanye_west_ranks_jesus_is_king_above_igor(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-2 (US-002) — composite reranker lifts Kanye's own album above Igor."""
    rows = [
        _mirror_row(title="Igor", artist="Tyler, the Creator", mbid="mb-igor"),
        _mirror_row(title="Jesus Is King", artist="Kanye West", mbid="mb-jik"),
        # Need ≥5 rows to trigger mode-1 (skip legacy fallback).
        _mirror_row(title="Graduation", artist="Kanye West", mbid="mb-grad"),
        _mirror_row(title="808s & Heartbreak", artist="Kanye West", mbid="mb-808s"),
        _mirror_row(
            title="My Beautiful Dark Twisted Fantasy",
            artist="Kanye West",
            mbid="mb-mbdtf",
        ),
    ]
    mirror = _StubMirrorService(rows=rows, total=len(rows))
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    results = response.json()["results"]
    # First hit is a Kanye West album, not Igor.
    assert results[0]["artist_name"] == "Kanye West"
    # Igor is below every Kanye West hit.
    artists = [hit["artist_name"] for hit in results]
    igor_idx = artists.index("Tyler, the Creator")
    last_kanye_idx = max(i for i, a in enumerate(artists) if a == "Kanye West")
    assert last_kanye_idx < igor_idx


@pytest.mark.asyncio
async def test_tc3_kanye_west_top5_has_at_least_4_kanye_albums(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-3 (US-002 broader) — success criterion: ≥4 Kanye-authored in top-5."""
    rows = [
        _mirror_row(title="Igor", artist="Tyler, the Creator", mbid="mb-igor"),
        _mirror_row(title="Compilation", artist="Various Artists", mbid="mb-comp"),
        _mirror_row(title="Graduation", artist="Kanye West", mbid="mb-grad"),
        _mirror_row(title="808s & Heartbreak", artist="Kanye West", mbid="mb-808s"),
        _mirror_row(title="Jesus Is King", artist="Kanye West", mbid="mb-jik"),
        _mirror_row(title="MBDTF", artist="Kanye West", mbid="mb-mbdtf"),
    ]
    mirror = _StubMirrorService(rows=rows, total=len(rows))
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west", "limit": 5})
    assert response.status_code == 200
    top5 = response.json()["results"]
    kanye_count = sum(1 for hit in top5 if hit["artist_name"] == "Kanye West")
    assert kanye_count >= 4


@pytest.mark.asyncio
async def test_tc4_mixed_query_returns_specific_album_first(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-4 (US-003) — q='kanye graduation' → Graduation at top.

    Mirror's FTS5 multi-token AND already places Graduation (the row
    matching BOTH tokens) at BM25 rank 0; the reranker preserves that.
    """
    rows = [
        _mirror_row(title="Graduation", artist="Kanye West", mbid="mb-grad"),
        _mirror_row(title="MBDTF", artist="Kanye West", mbid="mb-mbdtf"),
        _mirror_row(title="808s & Heartbreak", artist="Kanye West", mbid="mb-808s"),
        _mirror_row(title="Jesus Is King", artist="Kanye West", mbid="mb-jik"),
        _mirror_row(title="Yeezus", artist="Kanye West", mbid="mb-yeezus"),
    ]
    mirror = _StubMirrorService(rows=rows, total=len(rows))
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye graduation"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["title"] == "Graduation"


@pytest.mark.asyncio
async def test_tc5_total_capped_at_10000(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-5 (FR-008) — mirror reports 12,500 → response total == 10,000."""
    rows = [_mirror_row(title=f"Album {i}", artist="Artist", mbid=f"mb-{i}") for i in range(50)]
    mirror = _StubMirrorService(rows=rows, total=12_500)
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "anything"})
    assert response.status_code == 200
    assert response.json()["total"] == 10_000


@pytest.mark.asyncio
async def test_tc6_thin_mirror_appends_discogs_below(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-6 (FR-005) — mirror returns 2 hits, Discogs has 8 → mirror first."""
    mirror_rows = [
        _mirror_row(title="Mirror Hit A", artist="Kanye West", mbid="mb-a"),
        _mirror_row(title="Mirror Hit B", artist="Kanye West", mbid="mb-b"),
    ]
    mirror = _StubMirrorService(rows=mirror_rows, total=2)

    # 8 Discogs masters; legacy search_albums will materialise them.
    discogs_hits = [
        CatalogAlbum(
            mbid=None,
            discogs_release_id=None,
            discogs_master_id=f"master-{i}",
            title=f"Discogs Hit {i}",
            artist_name="Kanye West",
            release_year=2020,
            external_ids={"discogs_master": f"master-{i}"},
        )
        for i in range(8)
    ]
    by_master = {hit.discogs_master_id: hit for hit in discogs_hits if hit.discogs_master_id}

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = discogs_hits
    discogs_provider.get_album_by_external_id.side_effect = lambda provider, external_id: (
        by_master.get(external_id) if provider == "discogs_master" else None
    )

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye", "limit": 10})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Mirror rows come first; Discogs appended below.
    assert titles[:2] == ["Mirror Hit A", "Mirror Hit B"]
    # At least some Discogs hits appended.
    assert any(t.startswith("Discogs Hit") for t in titles[2:])


@pytest.mark.asyncio
async def test_tc7_mirror_disabled_falls_back_to_legacy_path(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-7 (Q3) — mirror unreachable → legacy Discogs-primary flow preserved."""
    discogs_hit = _ok_computer_master_hit()
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit

    # No mirror_service argument → app uses the disabled default dep.
    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "ok computer"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == ["OK Computer"]


@pytest.mark.asyncio
async def test_tc8_empty_mirror_discogs_returns_igor_first_kanye_still_wins(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-8 (004 follow-up) — empty mirror + Discogs returning Igor before
    Jesus Is King → reranker on the combined path must still lift the
    Kanye-authored result to the top. This is the bug the user hit in
    real-world testing after the original 004 ship: the mirror tier is
    sparse for many artists on first browse, Mode 2 fires with mirror
    rows = 0, and Discogs's popularity-driven order (Igor #1) bled
    through unchanged. The composite rerank now runs on the COMBINED
    mirror + legacy list, so artist-match (+10) beats credit-only-match.
    """
    # Mirror returns nothing (cold catalog for this artist).
    mirror = _StubMirrorService(rows=[], total=0)

    # Discogs returns Igor first (popularity-ordered), Jesus Is King second.
    igor = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-igor",
        title="Igor",
        artist_name="Tyler, The Creator",
        release_year=2019,
        external_ids={"discogs_master": "master-igor"},
    )
    jik = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-jik",
        title="Jesus Is King",
        artist_name="Kanye West",
        release_year=2019,
        external_ids={"discogs_master": "master-jik"},
    )
    by_master = {hit.discogs_master_id: hit for hit in (igor, jik) if hit.discogs_master_id}

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [igor, jik]
    discogs_provider.get_album_by_external_id.side_effect = lambda provider, external_id: (
        by_master.get(external_id) if provider == "discogs_master" else None
    )

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    artists = [hit["artist_name"] for hit in response.json()["results"]]
    # Jesus Is King must rank above Igor even though Discogs returned
    # Igor first. The +10 artist-match boost on Jesus Is King's "Kanye
    # West" entry beats Igor's "Tyler, The Creator" (which doesn't
    # match the "kanye west" query tokens at all).
    jik_idx = titles.index("Jesus Is King")
    igor_idx = titles.index("Igor")
    assert jik_idx < igor_idx, (
        f"Expected Jesus Is King above Igor, got order: {list(zip(titles, artists, strict=False))}"
    )


@pytest.mark.asyncio
async def test_tc9_mirror_disabled_discogs_igor_first_kanye_still_wins(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-9 (004 follow-up) — mirror disabled (no env wired up; Mode 3
    degraded path) + Discogs returning Igor before Jesus Is King → the
    rerank-on-degraded-path branch must still surface Kanye first.
    Covers the dev/local case where the Turso mirror isn't seeded yet.
    """
    igor = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-igor",
        title="Igor",
        artist_name="Tyler, The Creator",
        release_year=2019,
        external_ids={"discogs_master": "master-igor"},
    )
    jik = CatalogAlbum(
        mbid=None,
        discogs_release_id=None,
        discogs_master_id="master-jik",
        title="Jesus Is King",
        artist_name="Kanye West",
        release_year=2019,
        external_ids={"discogs_master": "master-jik"},
    )
    by_master = {hit.discogs_master_id: hit for hit in (igor, jik) if hit.discogs_master_id}

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [igor, jik]
    discogs_provider.get_album_by_external_id.side_effect = lambda provider, external_id: (
        by_master.get(external_id) if provider == "discogs_master" else None
    )

    # No mirror_service arg → app uses the disabled default dep.
    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    jik_idx = titles.index("Jesus Is King")
    igor_idx = titles.index("Igor")
    assert jik_idx < igor_idx


@pytest.mark.asyncio
async def test_tc10_tyler_the_creator_query_demotes_channel_orange(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """TC-10 (004 follow-up #2) — q='tyler the creator' must lift Tyler's
    own albums above Channel Orange (Frank Ocean, where Tyler is a
    credited producer). Bug surfaced post-ship: punctuation in
    'Tyler, The Creator' (the comma) broke the tokenizer, dropping
    coverage below the 0.8 threshold and disabling the rerank boost.
    Fix: tokenizer strips punctuation; rerank is now a hard partition,
    not a soft boost.
    """
    rows = [
        # Mirror has Channel Orange (Frank Ocean) + 4 Tyler albums.
        # Source order deliberately puts Channel Orange first to
        # simulate a Discogs-style popularity ranking.
        _mirror_row(title="Channel Orange", artist="Frank Ocean", mbid="mb-co"),
        _mirror_row(title="Igor", artist="Tyler, The Creator", mbid="mb-igor"),
        _mirror_row(title="Flower Boy", artist="Tyler, The Creator", mbid="mb-fb"),
        _mirror_row(
            title="Call Me If You Get Lost",
            artist="Tyler, The Creator",
            mbid="mb-cmiygl",
        ),
        _mirror_row(title="Goblin", artist="Tyler, The Creator", mbid="mb-goblin"),
    ]
    mirror = _StubMirrorService(rows=rows, total=len(rows))
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)

    app = _make_app(
        mb_provider=mb_provider,
        discogs_provider=discogs_provider,
        mirror_service=mirror,
    )
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "tyler the creator"})
    assert response.status_code == 200
    artists = [hit["artist_name"] for hit in response.json()["results"]]
    # All Tyler albums come first; Channel Orange last.
    tyler_count = sum(1 for a in artists if a == "Tyler, The Creator")
    assert tyler_count == 4
    assert artists[:4] == ["Tyler, The Creator"] * 4
    assert artists[-1] == "Frank Ocean"


@pytest.mark.asyncio
async def test_query_or_filter_required(_clean_env: None) -> None:
    """Calling /search with neither a query nor any filter yields 400.

    Feature 003: ``q`` is no longer strictly required — the route also
    accepts a "browse" mode where the user supplies at least one
    structured filter (decade / year_min / year_max / genre). When
    neither is provided the route rejects with a 400, not the 422 that
    a missing-required-param would have raised pre-003.
    """
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)
    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search")
    assert response.status_code == 400
    assert response.json()["detail"] == "provide_query_or_filter"
