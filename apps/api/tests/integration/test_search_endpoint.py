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


# ---------------------------------------------------------------------------
# Post-2026-05-24 search-quality regression tests (Fix 3).
#
# The parallel MB + Discogs merge with cross-source bonus is the central
# behavioural change. These tests pin the exact ordering for the user's
# two failing cases ("Graduation", "kanye west") plus the cross-source
# bonus arithmetic that makes that ordering happen.
# ---------------------------------------------------------------------------


MBID_GRADUATION = "44444444-aaaa-bbbb-cccc-555555555555"
MBID_MBDTF = "66666666-aaaa-bbbb-cccc-777777777777"


def _kanye_graduation_mb() -> CatalogAlbum:
    return CatalogAlbum(
        mbid=MBID_GRADUATION,
        title="Graduation",
        artist_name="Kanye West",
        release_year=2007,
        external_ids={"mbid": MBID_GRADUATION},
        score=100,
    )


def _kanye_graduation_discogs() -> CatalogAlbum:
    # Same album as ``_kanye_graduation_mb`` but surfaced by Discogs
    # (no MBID — the cross-source dedup must hit on (title, artist)).
    return CatalogAlbum(
        mbid=None,
        discogs_release_id="discogs-grad-1",
        title="Graduation",
        artist_name="Kanye West",
        release_year=2007,
        external_ids={"discogs": "discogs-grad-1"},
    )


@pytest.mark.asyncio
async def test_cross_source_bonus_lifts_confirmed_canonical_release(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """A hit confirmed by BOTH MB and Discogs must outrank a hit only
    seen by one provider.

    Concretely: Kanye's *Graduation* hits MB with score=80 AND lands at
    Discogs position 0 (popularity rank 100). Combined score 80 + 100 + 50
    cross-source bonus = 230. A noise hit only in MB at score=100 cannot
    catch up to that 230 — so Kanye's *Graduation* lands first.
    """
    grad_mb = CatalogAlbum(
        mbid=MBID_GRADUATION,
        title="Graduation",
        artist_name="Kanye West",
        release_year=2007,
        external_ids={"mbid": MBID_GRADUATION},
        score=80,
    )
    noise_mb = CatalogAlbum(
        mbid="99999999-ffff-ffff-ffff-999999999999",
        title="Graduation (Tribute)",
        artist_name="Random Artist",
        release_year=2020,
        external_ids={"mbid": "99999999-ffff-ffff-ffff-999999999999"},
        score=100,
    )

    by_mbid = {
        MBID_GRADUATION: grad_mb,
        "99999999-ffff-ffff-ffff-999999999999": noise_mb,
    }

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [grad_mb, noise_mb]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [_kanye_graduation_discogs()]
    discogs_provider.get_album_by_external_id.return_value = _kanye_graduation_discogs()

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "graduation"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Kanye's Graduation must be FIRST — combined score 230 beats the
    # tribute's MB-only 100.
    assert titles[0] == "Graduation"
    # The first hit should carry an MBID (we preferred the MB hit over
    # the Discogs hit during dedup because MBID identity is richer).
    assert response.json()["results"][0]["mbid"] == MBID_GRADUATION


@pytest.mark.asyncio
async def test_graduation_query_surfaces_kanye_in_top_two(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """User's failing case: searching "Graduation" must surface Kanye's
    canonical album in the top results, not Chinese-language compilations.

    Setup mirrors the production failure: MB returns 5 hits all tied at
    score 100 (Kanye + 4 niche releases — MB has no popularity
    tiebreaker). Discogs returns Kanye's Graduation at popularity-rank
    position 0. The combined-score merge with cross-source bonus pulls
    Kanye to the top.
    """
    # 4 niche MB hits all at score=100 — same relevance, no MB way to
    # break the tie.
    niche_titles = [
        ("11111111-1111-1111-1111-aaaaaaaaaaaa", "毕业 (Chinese)"),
        ("22222222-2222-2222-2222-bbbbbbbbbbbb", "Graduation Mixtape"),
        ("33333333-3333-3333-3333-cccccccccccc", "Graduation Vol. 2"),
        ("44444444-4444-4444-4444-dddddddddddd", "School Graduation"),
    ]
    niche_hits = [
        CatalogAlbum(
            mbid=mbid,
            title=title,
            artist_name="Unknown Artist",
            release_year=2015,
            external_ids={"mbid": mbid},
            score=100,
        )
        for mbid, title in niche_titles
    ]
    grad_mb = _kanye_graduation_mb()

    by_mbid: dict[str, CatalogAlbum] = {
        grad_mb.mbid: grad_mb for grad_mb in [grad_mb] if grad_mb.mbid is not None
    }
    for hit in niche_hits:
        if hit.mbid is not None:
            by_mbid[hit.mbid] = hit

    mb_provider = AsyncMock(spec=CatalogProvider)
    # All 5 hits tied at score 100; Kanye is intentionally NOT first in
    # the raw MB response — the niche releases come back ahead of him.
    mb_provider.search_albums.return_value = [*niche_hits, grad_mb]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]

    discogs_provider = AsyncMock(spec=CatalogProvider)
    # Discogs's popularity rank: Kanye at position 0 (highest community.have).
    discogs_provider.search_albums.return_value = [_kanye_graduation_discogs()]
    discogs_provider.get_album_by_external_id.return_value = _kanye_graduation_discogs()

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "Graduation"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Kanye's Graduation must rank in the top 2 — combined score
    # 100 (MB) + 100 (Discogs pos 0) + 50 (cross-source) = 250, vs each
    # niche release at 100 (MB only).
    assert "Graduation" in titles[:2], f"Kanye's Graduation must be in top 2, got {titles}"
    # Specifically: should be FIRST given the score arithmetic.
    assert titles[0] == "Graduation"


@pytest.mark.asyncio
async def test_kanye_west_query_surfaces_canonical_releases_at_top(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """User's failing case: searching "kanye west" must surface Kanye's
    canonical albums, not niche releases whose TITLE happens to be
    "Kanye West".

    Setup mirrors the production failure: MB returns 3 niche-title hits
    plus Kanye's Graduation + MBDTF (the artist-typed query matches both
    title and artist branches). Discogs returns Kanye's canonical albums
    at popularity-rank positions 0-1. The cross-source bonus elevates
    the canonical albums above the niche-titled ones.
    """
    mbdtf_mb = CatalogAlbum(
        mbid=MBID_MBDTF,
        title="My Beautiful Dark Twisted Fantasy",
        artist_name="Kanye West",
        release_year=2010,
        external_ids={"mbid": MBID_MBDTF},
        score=90,
    )
    grad_mb = _kanye_graduation_mb()

    niche_hits = [
        CatalogAlbum(
            mbid=f"aaaaaaaa-bbbb-cccc-dddd-{i:012d}",
            title="Kanye West",  # Album literally titled "Kanye West"
            artist_name=f"Tribute Artist {i}",
            release_year=2018 + i,
            external_ids={"mbid": f"aaaaaaaa-bbbb-cccc-dddd-{i:012d}"},
            score=100,  # MB scores tributes-titled-"Kanye West" identically
        )
        for i in range(3)
    ]
    by_mbid: dict[str, CatalogAlbum] = {}
    for hit in (mbdtf_mb, grad_mb, *niche_hits):
        if hit.mbid is not None:
            by_mbid[hit.mbid] = hit

    mb_provider = AsyncMock(spec=CatalogProvider)
    # Niche tributes come back ahead of Kanye in the raw MB response
    # (this is exactly what reproduced the bug — score=100 ties resolved
    # in arbitrary order).
    mb_provider.search_albums.return_value = [*niche_hits, grad_mb, mbdtf_mb]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]

    # Discogs sorts the artist=kanye+west call by popularity — Kanye's
    # canonical albums sit at positions 0 and 1.
    grad_discogs = _kanye_graduation_discogs()
    mbdtf_discogs = CatalogAlbum(
        mbid=None,
        discogs_release_id="discogs-mbdtf-1",
        title="My Beautiful Dark Twisted Fantasy",
        artist_name="Kanye West",
        release_year=2010,
        external_ids={"discogs": "discogs-mbdtf-1"},
    )
    by_discogs = {
        "discogs-grad-1": grad_discogs,
        "discogs-mbdtf-1": mbdtf_discogs,
    }
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [grad_discogs, mbdtf_discogs]
    discogs_provider.get_album_by_external_id.side_effect = lambda provider, rid: by_discogs.get(
        rid
    )

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Both canonical albums must bubble to the top — combined scores:
    # Graduation: 100 (MB) + 100 (Discogs pos 0) + 50 = 250
    # MBDTF:       90 (MB) +  90 (Discogs pos 1) + 50 = 230
    # Niche tributes: 100 (MB only). Each lower than both canonicals.
    canonical_titles = {
        "Graduation",
        "My Beautiful Dark Twisted Fantasy",
    }
    assert set(titles[:2]) == canonical_titles, (
        f"Kanye's canonical albums must dominate top 2, got top 5 = {titles[:5]}"
    )


@pytest.mark.asyncio
async def test_partial_provider_failure_does_not_abort_other_branch(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """When MB raises a :class:`ProviderError`, the Discogs branch must
    still return its hits (and vice versa). This pins the per-provider
    error funnel inside ``_safe_provider_search`` — a single upstream
    failure cannot poison the parallel ``asyncio.gather``.
    """
    from auxd_api.providers.errors import ProviderUnavailable

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.side_effect = ProviderUnavailable(
        "musicbrainz timeout", provider="musicbrainz"
    )

    discogs_hit = _kanye_graduation_discogs()
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "Graduation"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    assert titles == ["Graduation"]


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


# ---------------------------------------------------------------------------
# v3 search-quality regression tests (Fix A — lexical heuristic boosts).
#
# v2 (parallel merge + cross-source bonus) shipped in df4d071 but still
# failed on the user's "kanye west" query: niche releases TITLED "Kanye
# West" by non-Kanye artists still beat Kanye's real albums when both
# tied at MB score 100. The v3 ``_heuristic_boost`` (+200 for artist
# exact match, +100 for title prefix, +50 for title substring)
# disambiguates artist-intent vs title-intent queries without parsing.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kanye_west_query_artist_exact_boost(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """v3 regression: niche releases TITLED "Kanye West" by non-Kanye
    artists must NOT outrank Kanye's actual albums when querying
    "kanye west".

    Production failure (df4d071, v2): MB scored "Kanye West" by Randy
    Royale and "Kanye West" by Lil Barty at 100, same as Kanye's own
    releases. Discogs's position-based score was symmetric. Result:
    niche covers won the top of the list.

    v3 fix: ``_heuristic_boost`` adds +200 when the query equals the
    hit's artist credit. Kanye's hits get +200; niche tributes get 0.
    """
    grad_mb = CatalogAlbum(
        mbid=MBID_GRADUATION,
        title="Graduation",
        artist_name="Kanye West",
        release_year=2007,
        external_ids={"mbid": MBID_GRADUATION},
        score=100,
    )
    mbdtf_mb = CatalogAlbum(
        mbid=MBID_MBDTF,
        title="My Beautiful Dark Twisted Fantasy",
        artist_name="Kanye West",
        release_year=2010,
        external_ids={"mbid": MBID_MBDTF},
        score=100,
    )
    # Niche releases titled "Kanye West" by other artists. MB ties them
    # with Kanye at score=100 — the failure mode v3 exists to fix.
    randy_royale = CatalogAlbum(
        mbid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        title="Kanye West",
        artist_name="Randy Royale",
        release_year=2019,
        external_ids={"mbid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        score=100,
    )
    lil_barty = CatalogAlbum(
        mbid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        title="Kanye West",
        artist_name="Lil Barty",
        release_year=2020,
        external_ids={"mbid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        score=100,
    )

    by_mbid: dict[str, CatalogAlbum] = {}
    for hit in (grad_mb, mbdtf_mb, randy_royale, lil_barty):
        if hit.mbid is not None:
            by_mbid[hit.mbid] = hit

    mb_provider = AsyncMock(spec=CatalogProvider)
    # Niche covers come back FIRST in the raw MB response — same
    # arbitrary tie-resolution as production. Without the artist-exact
    # boost they'd still win.
    mb_provider.search_albums.return_value = [randy_royale, lil_barty, grad_mb, mbdtf_mb]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []  # Isolate the boost.

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    body = response.json()
    titles_with_artists = [(hit["title"], hit["artist_name"]) for hit in body["results"]]
    # Top two must be Kanye's actual releases, not the niche tributes.
    # Kanye hits: MB score 100 + boost 200 = 300.
    # Niche hits: MB score 100 + boost 0   = 100.
    top_two = set(titles_with_artists[:2])
    assert ("Graduation", "Kanye West") in top_two, (
        f"Kanye's Graduation must rank in top 2, got {titles_with_artists}"
    )
    assert ("My Beautiful Dark Twisted Fantasy", "Kanye West") in top_two, (
        f"Kanye's MBDTF must rank in top 2, got {titles_with_artists}"
    )


@pytest.mark.asyncio
async def test_to_pimp_query_title_prefix_boost(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """v3 regression: a query that PREFIXES a canonical album title must
    rank that album above one whose title only contains the query as a
    substring.

    Concrete failure (production): "to pimp" → "Pimp To Eat" ranks
    above "To Pimp a Butterfly" because both MB tied at score=100.

    v3 fix: ``_heuristic_boost`` returns +100 for title prefix match
    but only +50 for title substring (in fact "to pimp" is neither a
    prefix nor a substring of "Pimp To Eat" — both Pimp/To get +0).
    """
    tpab = CatalogAlbum(
        mbid="cccccccc-cccc-cccc-cccc-cccccccccccc",
        title="To Pimp a Butterfly",
        artist_name="Kendrick Lamar",
        release_year=2015,
        external_ids={"mbid": "cccccccc-cccc-cccc-cccc-cccccccccccc"},
        score=100,
    )
    pimp_to_eat = CatalogAlbum(
        mbid="dddddddd-dddd-dddd-dddd-dddddddddddd",
        title="Pimp To Eat",
        artist_name="Anybody Killa",
        release_year=2001,
        external_ids={"mbid": "dddddddd-dddd-dddd-dddd-dddddddddddd"},
        score=100,
    )
    by_mbid = {hit.mbid: hit for hit in (tpab, pimp_to_eat) if hit.mbid is not None}

    mb_provider = AsyncMock(spec=CatalogProvider)
    # ``Pimp To Eat`` deliberately returned first — the failure mode.
    mb_provider.search_albums.return_value = [pimp_to_eat, tpab]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "to pimp"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # TPAB: MB score 100 + title-prefix boost 100 = 200.
    # Pimp To Eat: MB score 100 + 0 (query is neither prefix nor substring) = 100.
    assert titles[0] == "To Pimp a Butterfly", (
        f"'To Pimp a Butterfly' must rank first for query 'to pimp', got {titles}"
    )


@pytest.mark.asyncio
async def test_heuristic_boost_unicode_casefold(
    _clean_env: None,
    _clean_albums: None,
) -> None:
    """v3 boost uses :py:meth:`str.casefold` so a lower-case query like
    "kanye west" matches a title-cased artist credit "Kanye West".

    Pins case-insensitive intent: users type queries however they like.
    """
    grad_mb = CatalogAlbum(
        mbid=MBID_GRADUATION,
        title="Graduation",
        artist_name="Kanye West",  # Title-cased on the wire.
        release_year=2007,
        external_ids={"mbid": MBID_GRADUATION},
        score=10,  # Deliberately LOW MB score — proves the boost lifts it.
    )
    other = CatalogAlbum(
        mbid="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        title="Some Other Album",
        artist_name="Random Artist",
        release_year=2018,
        external_ids={"mbid": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"},
        score=100,  # HIGH MB score — would normally win.
    )
    by_mbid = {hit.mbid: hit for hit in (grad_mb, other) if hit.mbid is not None}

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [other, grad_mb]
    mb_provider.get_album_by_mbid.side_effect = lambda mbid: by_mbid[mbid]
    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = []

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    # Lower-case query against title-cased "Kanye West" artist credit.
    response = client.get("/api/v1/search", params={"q": "kanye west"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Boost: 10 (MB) + 200 (artist exact match) = 210 vs 100 (MB only).
    assert titles[0] == "Graduation", (
        f"Casefold artist match must catch 'Kanye West' for query 'kanye west', got {titles}"
    )


# ---------------------------------------------------------------------------
# v3 search-quality regression tests (Fix B+C — Discogs popularity enrichment).
#
# v2 used position-based score as a popularity proxy, but Discogs's
# ``/database/search`` returns hits by relevance — NOT popularity. The
# v3 enrichment fetches ``community.have`` from ``/releases/{id}`` for
# the top N Discogs candidates, replacing the position score with
# ``log10(have+1) * 25``. Caches at 24h to bound API blast radius.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_with_popularity_cache_hit(
    _clean_env: None,
    _clean_albums: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On cache hit the service skips the Discogs detail-endpoint fetch.

    Pins the lower bound of latency on a repeat query for a hot album:
    no extra network hops once the popularity score has been cached.
    """
    from auxd_api.modules.search import service as search_service

    # Fake cache: any release_id resolves to popularity 200.
    async def _cache_get(_key: str) -> str | None:
        return "200"

    async def _cache_set(*_args: object, **_kwargs: object) -> None:
        pass

    monkeypatch.setattr(search_service, "cache_get", _cache_get)
    monkeypatch.setattr(search_service, "cache_set", _cache_set)

    discogs_hit = _kanye_graduation_discogs()
    mb_hit = _kanye_graduation_mb()

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [mb_hit]
    mb_provider.get_album_by_mbid.return_value = mb_hit

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit
    # ``get_community_data`` MUST NOT be called when the cache hits.
    discogs_provider.get_community_data = AsyncMock(return_value=None)

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "graduation"})
    assert response.status_code == 200
    discogs_provider.get_community_data.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_with_popularity_cache_miss_fetches(
    _clean_env: None,
    _clean_albums: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache miss → ``get_community_data`` is called and a popularity
    score is written back to cache. The new score derives from
    ``log10(have+1) * 25``.
    """
    from auxd_api.modules.search import service as search_service

    written: dict[str, str] = {}

    async def _cache_get(_key: str) -> str | None:
        return None  # Miss.

    async def _cache_set(key: str, value: str, *, ex_seconds: int | None = None) -> None:
        written[key] = value

    monkeypatch.setattr(search_service, "cache_get", _cache_get)
    monkeypatch.setattr(search_service, "cache_set", _cache_set)

    discogs_hit = _kanye_graduation_discogs()
    mb_hit = _kanye_graduation_mb()

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = [mb_hit]
    mb_provider.get_album_by_mbid.return_value = mb_hit

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit
    # Canonical popular release: 5000 community.have. Score
    # = int(log10(5001) * 25) ≈ 92.
    discogs_provider.get_community_data = AsyncMock(return_value=5000)

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "graduation"})
    assert response.status_code == 200
    discogs_provider.get_community_data.assert_awaited_once_with("discogs-grad-1")
    # Cache write must include the canonical key + log-scaled score.
    assert any("discogs-grad-1" in k for k in written), (
        f"expected discogs:community:discogs-grad-1 key, got {list(written)}"
    )
    cached_score = next(int(v) for k, v in written.items() if "discogs-grad-1" in k)
    # log10(5001) ≈ 3.699 → * 25 ≈ 92. Allow ±2 for int truncation.
    assert 88 <= cached_score <= 96, f"expected ~92 for have=5000, got {cached_score}"


@pytest.mark.asyncio
async def test_enrich_with_popularity_fetch_failure_falls_back(
    _clean_env: None,
    _clean_albums: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``get_community_data`` returns ``None`` (graceful failure),
    the original position-based score is preserved — the search still
    returns results, just without the popularity refinement.
    """
    from auxd_api.modules.search import service as search_service

    async def _cache_get(_key: str) -> str | None:
        return None  # Cache miss forces the fetch path.

    async def _cache_set(*_args: object, **_kwargs: object) -> None:
        pass

    monkeypatch.setattr(search_service, "cache_get", _cache_get)
    monkeypatch.setattr(search_service, "cache_set", _cache_set)

    discogs_hit = _kanye_graduation_discogs()

    mb_provider = AsyncMock(spec=CatalogProvider)
    mb_provider.search_albums.return_value = []  # Discogs-only path.

    discogs_provider = AsyncMock(spec=CatalogProvider)
    discogs_provider.search_albums.return_value = [discogs_hit]
    discogs_provider.get_album_by_external_id.return_value = discogs_hit
    # Fetch fails — disabled token, network error, etc.
    discogs_provider.get_community_data = AsyncMock(return_value=None)

    app = _make_app(mb_provider=mb_provider, discogs_provider=discogs_provider)
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "graduation"})
    assert response.status_code == 200
    titles = [hit["title"] for hit in response.json()["results"]]
    # Position-based score (100 + 100 boost) keeps the hit in the
    # result — no crash, no missing data.
    assert titles == ["Graduation"]
