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
from auxd_api.modules.albums.models import Album, AlbumSource
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
) -> FastAPI:
    app = FastAPI()
    app.include_router(search_router, prefix="/api/v1")

    async def _override_mb() -> CatalogProvider:
        return mb_provider

    async def _override_discogs() -> CatalogProvider:
        return discogs_provider

    app.dependency_overrides[_mb_provider] = _override_mb
    app.dependency_overrides[_discogs_provider] = _override_discogs
    return app


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


@pytest.mark.asyncio
async def test_query_required(_clean_env: None) -> None:
    """``q`` is a required Query parameter."""
    mb_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider = AsyncMock(spec=CatalogProvider)
    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search")
    assert response.status_code == 422
