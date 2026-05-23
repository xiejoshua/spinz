"""Integration tests for ``POST /api/v1/reports/missing-album`` (T053a)."""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.reports.routes import router as reports_router
from auxd_api.modules.users.models import HandleRedirect, User


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
async def _clean_reports() -> AsyncIterator[None]:
    await Report.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await Report.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(reports_router, prefix="/api/v1")
    # Mount auth too so we can authenticate one of the tests via signup.
    app.include_router(auth_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_anonymous_submission_creates_open_report(
    _clean_env: None,
    _clean_reports: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/missing-album",
        json={
            "artist": "Boards of Canada",
            "album": "Geogaddi",
            "mbid_hint": "f1d56ad3-aa48-4f8e-9c2f-c4456cdef123",
            "query": "boards geogaddi",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "report_id" in body
    assert "catalog" in body["message"].lower()
    persisted = await Report.get(body["report_id"])
    assert persisted is not None
    assert persisted.target_type is ReportTargetType.MISSING_ALBUM
    assert persisted.reason is ReportReason.CATALOG_GAP
    assert persisted.status is ReportStatus.OPEN
    assert persisted.reporter_id is None
    assert "Boards of Canada" in persisted.detail
    assert "Geogaddi" in persisted.detail
    assert "f1d56ad3" in persisted.detail
    assert persisted.target_id == "boards geogaddi"


@pytest.mark.asyncio
async def test_authenticated_submission_records_reporter(
    _clean_env: None,
    _clean_reports: None,
) -> None:
    client = TestClient(_make_app())
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "alice@example.com",
            "password": "correct-horse-battery-staple-9",
            "handle": "alice42",
            "display_name": "Alice",
        },
    )
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    # Signup issues a session — the missing-album endpoint is a safe path
    # by HTTP method (POST) but the SessionMiddleware only enforces CSRF
    # on authenticated requests, so we need to forward the CSRF header.
    csrf = client.cookies.get("auxd_csrf")
    assert csrf is not None
    response = client.post(
        "/api/v1/reports/missing-album",
        json={"artist": "Stereolab", "album": "Dots and Loops"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    persisted = await Report.get(response.json()["report_id"])
    assert persisted is not None
    assert persisted.reporter_id == user_id
    # Without a query, the target_id is the synthesised "artist - album" form.
    assert persisted.target_id == "Stereolab - Dots and Loops"


@pytest.mark.asyncio
async def test_missing_artist_or_album_returns_422(
    _clean_env: None,
    _clean_reports: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/missing-album",
        json={"artist": "", "album": "Geogaddi"},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/reports/missing-album",
        json={"artist": "Boards of Canada"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rate_limit_fires_on_burst(
    _clean_env: None,
    _clean_reports: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the rate limiter to behave deterministically and assert 429 on burst."""
    from auxd_api import redis_client as redis_module
    from auxd_api.lib import rate_limit as rate_limit_module

    # Build a tiny stub Redis client that returns increasing zcard counts —
    # the dependency is configured for 3/min so the 4th call should 429.
    state = {"count": 0}

    class _FakeRedisPipeline:
        def zremrangebyscore(self, *_args: object) -> _FakeRedisPipeline:
            return self

        def zcard(self, *_args: object) -> _FakeRedisPipeline:
            return self

        async def execute(self) -> list[int]:
            current = state["count"]
            state["count"] += 1
            return [0, current]

    class _FakeRedis:
        def pipeline(self) -> _FakeRedisPipeline:
            return _FakeRedisPipeline()

        async def zadd(self, *_args: object, **_kwargs: object) -> int:
            return 1

        async def expire(self, *_args: object) -> bool:
            return True

    monkeypatch.setattr(redis_module, "_client", _FakeRedis())
    monkeypatch.setattr(
        rate_limit_module,
        "_alert_rate_limit_down",
        lambda operation, exc: None,
    )

    client = TestClient(_make_app())
    payload = {"artist": "x", "album": "y"}
    for _ in range(3):
        assert client.post("/api/v1/reports/missing-album", json=payload).status_code == 201
    burst = client.post("/api/v1/reports/missing-album", json=payload)
    assert burst.status_code == 429
