"""Backend perf guard for the wedge commit path (T084).

The wedge NFR (spec.md §6.1; TC-001) sets a hard p95 budget of 8 seconds
end-to-end for the user-visible commit, with the backend handling
budgeted at <500 ms p95. This module guards the backend half — it drives
``POST /api/v1/diary/entries`` against the in-memory ``TestClient``
across N trials and asserts the p95 server-side commit time is under
budget.

The test uses the same ``FakeAuthMiddleware`` pattern as
``test_diary_logging.py`` so it doesn't depend on the cookie / HMAC
round-trip. Network / TLS / Vercel cold-start overhead are covered by
the frontend Playwright spec in ``apps/web/tests/e2e/log-wedge.spec.ts``
— this layer is the lower bound.

The budget here is generous (1500 ms) because the test runs against a
small in-process database and the goal is to catch order-of-magnitude
regressions (an accidental N+1 query, a missing index, a sync provider
call landing on the wedge path), not to micro-benchmark.
"""

from __future__ import annotations

import base64
import secrets
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User
from tests.integration._auth_helpers import FakeAuthMiddleware

TRIALS = 10
# Generous in-process budget — the real spec target is <500 ms p95 over
# the wire. In-process commits should clear that ceiling by an order of
# magnitude on healthy CI runners.
P95_BUDGET_MS = 1500.0


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


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(diary_router, prefix="/api/v1")
    return app


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await User.delete_all()


@pytest.mark.asyncio
async def test_log_commit_p95_under_budget(_clean_env: None, _clean_db: None) -> None:
    """Drive the wedge POST across ``TRIALS`` distinct logs and assert p95.

    Each trial uses a fresh ``(user, album)`` pair so the 60-second
    idempotency window never short-circuits the commit path. The trial
    list is sorted and the p95 sample is asserted against the budget.
    """
    # Seed N albums + a single user so each trial maps to a different
    # album (avoiding idempotency dedup on rapid repeated requests).
    albums: list[Album] = []
    for i in range(TRIALS):
        album = Album(
            id=f"perf-album-{i:03d}",
            mbid=None,
            title=f"Perf Album {i}",
            artist_credit="Perf Artist",
            source=AlbumSource.MUSICBRAINZ,
            cache_expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        await album.insert()
        albums.append(album)

    client = TestClient(_make_app())
    headers = {"X-User-Id": "user-perf"}
    durations_ms: list[float] = []
    for album in albums:
        started = time.perf_counter()
        response = client.post(
            "/api/v1/diary/entries",
            headers=headers,
            json={"album_id": album.id, "rating": 4.0, "auxed": False},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert response.status_code == 201, response.text
        durations_ms.append(elapsed_ms)

    durations_ms.sort()
    p95_index = max(0, int(len(durations_ms) * 0.95) - 1)
    p95 = durations_ms[p95_index]
    # Surface the sample so the failure mode reads cleanly.
    pretty = ", ".join(f"{d:.1f}" for d in durations_ms)
    assert p95 < P95_BUDGET_MS, (
        f"wedge p95={p95:.1f}ms exceeds {P95_BUDGET_MS:.0f}ms — durations(ms)=[{pretty}]"
    )
