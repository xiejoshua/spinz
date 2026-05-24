"""Integration tests for the search endpoint (T069).

Coverage:

* Atlas-only hits (mongomock returns nothing from ``$search``, so this
  case is exercised as "no Atlas hits, fallback returns results").
* Atlas + MusicBrainz fallback merge — MB hits materialise as new
  Album rows and the result list grows.
* Atlas + MusicBrainz + Discogs fallback — Discogs hits become
  candidate albums.
* Empty result → ``report_missing_album_url`` hint surfaces.
* Discogs token unset → graceful-disabled mode; MB-only fallback still
  works.

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
MBID_KID_A = "11111111-2222-3333-4444-555555555555"


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


def _ok_computer_hit() -> CatalogAlbum:
    return CatalogAlbum(
        mbid=MBID_OK,
        title="OK Computer",
        artist_name="Radiohead",
        release_year=1997,
        external_ids={"mbid": MBID_OK},
    )


def _kid_a_hit() -> CatalogAlbum:
    return CatalogAlbum(
        mbid=MBID_KID_A,
        title="Kid A",
        artist_name="Radiohead",
        release_year=2000,
        external_ids={"mbid": MBID_KID_A},
    )


def _discogs_hit() -> CatalogAlbum:
    return CatalogAlbum(
        mbid=None,
        discogs_release_id="release-249504",
        title="In Rainbows",
        artist_name="Radiohead",
        release_year=2007,
        external_ids={"discogs": "release-249504"},
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
async def test_musicbrainz_fallback_materializes_results(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """Zero Atlas hits → MusicBrainz fallback materialises + returns hits."""
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_hit(), _kid_a_hit()]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: (
        _ok_computer_hit() if mbid == MBID_OK else _kid_a_hit()
    )
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    body = response.json()
    titles = {hit["title"] for hit in body["results"]}
    assert titles == {"OK Computer", "Kid A"}
    # Persisted into catalog — a follow-up query finds them locally.
    assert await Album.find_one(Album.mbid == MBID_OK) is not None
    # Empty-result hint NOT present because we got hits.
    assert "report_missing_album_url" not in body


@pytest.mark.asyncio
async def test_discogs_fallback_runs_when_mb_under_threshold(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """MB returns < threshold → Discogs is also queried; results merge."""
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_hit()
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [_discogs_hit()]
    discogs_provider.get_album_by_external_id.return_value = _discogs_hit()

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    body = response.json()
    titles = {hit["title"] for hit in body["results"]}
    assert "OK Computer" in titles  # from MB
    assert "In Rainbows" in titles  # from Discogs
    # Discogs hit was materialised as a candidate album.
    candidate = await Album.find_one(Album.discogs_release_id == "release-249504")
    assert candidate is not None
    assert candidate.candidate is True


@pytest.mark.asyncio
async def test_discogs_disabled_still_returns_mb_results(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """A graceful-disabled Discogs (empty search) doesn't break MB-only flow."""
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_hit()
    # Discogs mock with token unset behaves identically to disabled mode.
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    body = response.json()
    titles = {hit["title"] for hit in body["results"]}
    assert titles == {"OK Computer"}


@pytest.mark.asyncio
async def test_dedupe_skips_provider_hit_already_in_atlas(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """A MusicBrainz hit whose MBID is already cached locally is not duplicated."""
    from datetime import UTC, datetime, timedelta

    # Pre-seed an Album with MBID_OK so the MB hit deduplicates against it.
    # NOTE: discogs_release_id set to a unique non-null value because
    # mongomock-motor doesn't honor partialFilterExpression — when the
    # search materialises Kid A with discogs_release_id=None it would
    # collide with this pre-seeded row if both were null. Real Atlas
    # excludes nulls from the unique constraint via the partial filter.
    pre = Album(
        mbid=MBID_OK,
        discogs_release_id="release-ok-pre-seed",
        title="OK Computer",
        artist_credit="Radiohead",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await pre.insert()

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_hit(), _kid_a_hit()]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: (
        _ok_computer_hit() if mbid == MBID_OK else _kid_a_hit()
    )
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    body = response.json()
    # OK Computer should appear exactly once even though it's in both
    # Atlas (mongomock returns []) AND MB. In mongomock the Atlas tier
    # returns nothing, so MB's OK Computer hit lands first; the second
    # MB call for Kid A also lands. Each MBID appears at most once.
    mbids = [hit["mbid"] for hit in body["results"]]
    assert len(mbids) == len(set(mbids))


@pytest.mark.asyncio
async def test_mb_hits_sorted_by_score_desc(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """MB hits with mixed scores must come back ordered by score desc.

    Pins the post-MVP feedback fix (2026-05-24): canonical popular
    release-groups score ~90-100 from MB while obscure unofficial
    releases score ~30-50 — surfacing the high-score hits first stops
    the "Graduation doesn't appear unless typed exactly" complaint.
    """
    low = CatalogAlbum(
        mbid="11111111-1111-1111-1111-111111111111",
        title="Low Score Release",
        artist_name="Artist",
        release_year=2010,
        external_ids={"mbid": "11111111-1111-1111-1111-111111111111"},
        score=50,
    )
    high = CatalogAlbum(
        mbid="22222222-2222-2222-2222-222222222222",
        title="High Score Release",
        artist_name="Artist",
        release_year=2011,
        external_ids={"mbid": "22222222-2222-2222-2222-222222222222"},
        score=90,
    )
    mid = CatalogAlbum(
        mbid="33333333-3333-3333-3333-333333333333",
        title="Mid Score Release",
        artist_name="Artist",
        release_year=2012,
        external_ids={"mbid": "33333333-3333-3333-3333-333333333333"},
        score=70,
    )
    by_mbid = {hit.mbid: hit for hit in (low, high, mid) if hit.mbid is not None}

    mb_provider = AsyncMock(spec=CatalogProvider)
    # Deliberately unsorted order — the service must sort, not rely on
    # the provider to return scores pre-ordered.
    mb_provider.search_albums.return_value = [low, high, mid]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "artist"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == ["High Score Release", "Mid Score Release", "Low Score Release"]


@pytest.mark.asyncio
async def test_mb_hits_none_score_sinks_to_bottom(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """Hits with ``score=None`` (e.g. fed through lookups) sort last.

    Belt-and-braces: a future provider quirk that yields ``None`` for
    score MUST NOT crash the comparator and MUST land below any scored
    hit, even one with score zero. The ``-1`` sentinel in the sort key
    encodes that contract.
    """
    scored_low = CatalogAlbum(
        mbid="aaaaaaaa-1111-1111-1111-111111111111",
        title="Scored Low",
        artist_name="Artist",
        release_year=2010,
        external_ids={"mbid": "aaaaaaaa-1111-1111-1111-111111111111"},
        score=50,
    )
    no_score = CatalogAlbum(
        mbid="bbbbbbbb-2222-2222-2222-222222222222",
        title="No Score",
        artist_name="Artist",
        release_year=2011,
        external_ids={"mbid": "bbbbbbbb-2222-2222-2222-222222222222"},
        score=None,
    )
    scored_high = CatalogAlbum(
        mbid="cccccccc-3333-3333-3333-333333333333",
        title="Scored High",
        artist_name="Artist",
        release_year=2012,
        external_ids={"mbid": "cccccccc-3333-3333-3333-333333333333"},
        score=70,
    )
    by_mbid = {hit.mbid: hit for hit in (scored_low, no_score, scored_high) if hit.mbid is not None}

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [scored_low, no_score, scored_high]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "artist"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == ["Scored High", "Scored Low", "No Score"]


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
    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [_ok_computer_hit()]
    mb_provider.get_album_by_mbid.return_value = _ok_computer_hit()
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "radiohead"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    hit = body["results"][0]
    assert hit["artist_name"] == "Radiohead"
    # Legacy field name MUST NOT leak — guards against accidental
    # re-introduction of the bug.
    assert "artist_credit" not in hit


@pytest.mark.asyncio
async def test_query_type_unsupported_returns_400(_clean_env: None) -> None:
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
