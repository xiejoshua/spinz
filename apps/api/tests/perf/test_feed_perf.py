"""Backend perf guard for the home feed (T107).

The home feed (T106) is the dominant read surface — every session opens
on it. Spec.md §6.1 sets a p95 target of <500 ms over the wire; this
test guards the in-process equivalent by seeding ~500 followees with 10
random DiaryEntries each (5000 total) and asserting p95 of 10 ``GET
/feed?mode=for_you&limit=25`` calls is under :data:`P95_BUDGET_MS` (2500
ms).

The 2500 ms budget is generous because mongomock-motor uses sorted
Python lists rather than B-tree indexes, so the in-process number runs
considerably slower than real Atlas. The goal is catching
order-of-magnitude regressions (an accidental N+1 query, a missing
batched lookup, a sync provider call landing on the feed path), not
micro-benchmarking — see the sibling diary perf test
(``tests/integration/test_log_perf.py``) for the same rationale.

Mirrors the harness pattern from ``test_log_perf.py``:

* In-memory mongomock DB via the autouse session conftest fixture.
* :class:`_FakeAuthMiddleware` for session injection without HMAC.
* Asserts on a sorted-quantile sample, prints the full duration list on
  failure for diagnostic.
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
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.feed.routes import router as feed_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.social.models import Block, Follow, FollowState
from auxd_api.modules.users.models import User

# Tunables — exposed as module-level constants so a CI matrix could
# scale them without editing the test body.
FOLLOWEE_COUNT = 500
ENTRIES_PER_USER = 10
TRIALS = 10
P95_BUDGET_MS = 2500.0


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


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    """Attach a :class:`Session` based on the ``X-User-Id`` header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            request.state.session = Session(
                user_id=user_id,
                csrf_token="test-csrf",
                issued_at=0,
                expires_at=int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
                session_version=1,
            )
        else:
            request.state.session = None
        return await call_next(request)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(_FakeAuthMiddleware)
    app.include_router(feed_router, prefix="/api/v1")
    return app


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()


@pytest.mark.perf
@pytest.mark.asyncio
async def test_home_feed_p95_under_budget(_clean_env: None, _clean_db: None) -> None:
    """Seed 500 followees × 10 entries and assert p95 of ``GET /feed``.

    The dataset is intentionally larger than any reasonable real follow
    graph so the test catches algorithmic regressions (e.g. the inner
    scoring loop accidentally going O(N²) by re-loading the top-N
    authors per entry).
    """
    viewer_id = "user-viewer"
    viewer = User(
        id=viewer_id,
        handle="viewer",
        email="viewer@example.com",
        password_hash="$argon2id$test-hash",
        display_name="Viewer",
    )
    await viewer.insert()

    # Seed a single album so the album-sidecar query is just one row
    # but the diary fan-out is heavy. We're stressing the diary scan +
    # sort + score pass, not the album catalogue.
    album = Album(
        id="perf-album",
        mbid=None,
        title="Perf Album",
        artist_credit="Perf Artist",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()

    now = datetime.now(UTC)
    # Build all followees + Follow rows first so we can insert diary
    # entries in a single sweep.
    follow_rows: list[Follow] = []
    user_rows: list[User] = []
    for i in range(FOLLOWEE_COUNT):
        followee = User(
            id=f"perf-friend-{i:04d}",
            handle=f"friend{i:04d}",
            email=f"friend{i:04d}@example.com",
            password_hash="$argon2id$test-hash",
            display_name=f"Friend{i:04d}",
        )
        user_rows.append(followee)
        follow_rows.append(
            Follow(
                follower_id=viewer_id,
                followee_id=followee.id,
                state=FollowState.ACCEPTED,
            )
        )
    await User.insert_many(user_rows)
    await Follow.insert_many(follow_rows)

    # Build all diary entries — random ratings + staggered logged_at so
    # the sort isn't trivially monotonic.
    entries: list[DiaryEntry] = []
    for i, followee in enumerate(user_rows):
        for j in range(ENTRIES_PER_USER):
            entries.append(
                DiaryEntry(
                    user_id=followee.id,
                    album_id=album.id,
                    logged_at=now - timedelta(minutes=i * ENTRIES_PER_USER + j),
                    rating=3.0 + (i + j) % 5 * 0.5,
                    visibility=Visibility.PUBLIC,
                )
            )
    await DiaryEntry.insert_many(entries)

    client = TestClient(_make_app())
    headers = {"X-User-Id": viewer_id}
    durations_ms: list[float] = []
    for _ in range(TRIALS):
        started = time.perf_counter()
        response = client.get("/api/v1/feed?mode=for_you&limit=25", headers=headers)
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert response.status_code == 200, response.text
        durations_ms.append(elapsed_ms)

    durations_ms.sort()
    p95_index = max(0, int(len(durations_ms) * 0.95) - 1)
    p95 = durations_ms[p95_index]
    pretty = ", ".join(f"{d:.1f}" for d in durations_ms)
    assert p95 < P95_BUDGET_MS, (
        f"home feed p95={p95:.1f}ms exceeds {P95_BUDGET_MS:.0f}ms — durations(ms)=[{pretty}]"
    )
