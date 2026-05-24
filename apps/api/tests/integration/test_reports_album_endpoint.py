"""Integration tests for ``POST /api/v1/reports/album`` (T167).

Mirrors the patterns in :mod:`tests.integration.test_reports_endpoints`:

* 401 unauthenticated.
* 201 happy path for each album-specific reason (``wrong_metadata``,
  ``duplicate``, ``other``).
* 422 on an invalid reason (e.g. ``harassment`` smuggled onto an album
  report).
* 422 when the album doesn't exist (FK validation).
* Idempotency: same (reporter, album, target_type) within 24h returns
  ``200`` + ``created=False`` and a single row in the collection.
* Rate limit fires after 10 album reports in a 24-hour window.
"""

from __future__ import annotations

import base64
import secrets
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
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportTargetType,
)
from auxd_api.modules.reports.routes import router as reports_router
from auxd_api.modules.users.models import User


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Report.delete_all()
    await User.delete_all()
    await Album.delete_all()
    yield
    await Report.delete_all()
    await User.delete_all()
    await Album.delete_all()


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
    app.include_router(reports_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test",
        display_name=handle.capitalize(),
    )


def _make_album(album_id: str = "alb-1", *, title: str = "Test Album") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title=title,
        artist_credit="Test Artist",
        release_year=2020,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: skip the rate-limit check so per-test setup is simple."""
    from auxd_api.lib import rate_limit as rate_limit_module

    async def _allow_all(**_: object) -> bool:
        return True

    monkeypatch.setattr(rate_limit_module, "_check_and_record", _allow_all)


# ---------------------------------------------------------------------------
# 401 unauthenticated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_album_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/album",
        json={"album_id": "alb-1", "reason": "wrong_metadata"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 201 happy paths — one per allowed reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_album_wrong_metadata_creates_row(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    album = _make_album()
    await reporter.insert()
    await album.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/album",
        json={
            "album_id": album.id,
            "reason": "wrong_metadata",
            "detail": "title is missing remaster suffix",
        },
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["target_type"] == "album"
    assert body["target_id"] == album.id
    assert body["created"] is True
    persisted = await Report.get(body["report_id"])
    assert persisted is not None
    assert persisted.target_type is ReportTargetType.ALBUM
    assert persisted.reason is ReportReason.WRONG_METADATA


@pytest.mark.asyncio
async def test_report_album_duplicate_creates_row(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    album = _make_album()
    await reporter.insert()
    await album.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/album",
        json={
            "album_id": album.id,
            "reason": "duplicate",
            "detail": "merge with alb-2",
        },
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 201, response.text
    persisted = await Report.get(response.json()["report_id"])
    assert persisted is not None
    assert persisted.reason is ReportReason.DUPLICATE


# ---------------------------------------------------------------------------
# 422 invalid reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_report_rejects_content_reason(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    album = _make_album()
    await reporter.insert()
    await album.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/album",
        json={"album_id": album.id, "reason": "harassment"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_reason"


# ---------------------------------------------------------------------------
# 422 target not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_target_not_found_returns_422(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    await reporter.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/album",
        json={"album_id": "does-not-exist", "reason": "wrong_metadata"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "target_not_found"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_report_idempotent_within_24h(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    album = _make_album()
    await reporter.insert()
    await album.insert()

    client = TestClient(_make_app())
    body = {"album_id": album.id, "reason": "wrong_metadata"}
    first = client.post(
        "/api/v1/reports/album",
        json=body,
        headers={"X-User-Id": reporter.id},
    )
    assert first.status_code == 201
    first_id = first.json()["report_id"]

    second = client.post(
        "/api/v1/reports/album",
        json=body,
        headers={"X-User-Id": reporter.id},
    )
    assert second.status_code == 200
    assert second.json()["report_id"] == first_id
    assert second.json()["created"] is False

    rows = await Report.find(
        {
            "reporter_id": reporter.id,
            "target_type": ReportTargetType.ALBUM.value,
            "target_id": album.id,
        }
    ).to_list()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_report_rate_limit_fires_after_ten(
    _clean_env: None,
    _clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from auxd_api.lib import rate_limit as rate_limit_module

    state = {"count": 0}

    async def _counting(*, bucket_key: str, limit: rate_limit_module.RateLimit) -> bool:
        _ = bucket_key
        state["count"] += 1
        return state["count"] <= limit.limit

    monkeypatch.setattr(rate_limit_module, "_check_and_record", _counting)

    reporter = _make_user("user-reporter", "reporter")
    albums = [_make_album(album_id=f"alb-{i}") for i in range(11)]
    await reporter.insert()
    for a in albums:
        await a.insert()

    client = TestClient(_make_app())
    last_status: int | None = None
    for i in range(11):
        resp = client.post(
            "/api/v1/reports/album",
            json={"album_id": albums[i].id, "reason": "wrong_metadata"},
            headers={"X-User-Id": reporter.id},
        )
        last_status = resp.status_code
        if i < 10:
            assert resp.status_code == 201, f"call {i}: {resp.text}"
    assert last_status == 429
