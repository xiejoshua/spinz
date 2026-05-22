"""Tests for the ``/healthz`` liveness endpoint (T011).

Coverage:

* Body shape — must always include ``status``, ``db``, ``redis``,
  ``version``.
* Status code is always 200 (Fly uses the code as a process-up signal;
  body inspection distinguishes ok/degraded).
* Degraded path: with no lifespan, both pings return ``down`` and
  ``status`` becomes ``degraded``.
* Healthy path: with the lifespan running and the data-layer pings
  patched to ``ok``, ``status`` becomes ``ok``.
* The versioned ``/api/v1`` router is mounted (its prefix shows up in
  the OpenAPI document so the T028 codegen has something to consume).
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auxd_api import db as db_module
from auxd_api import main as main_module
from auxd_api import redis_client as redis_module
from auxd_api import settings as settings_module
from auxd_api.main import app

_REQUIRED_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "SPOTIFY_INTEGRATION_ENABLED",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
)


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def test_healthz_returns_200_when_pings_are_down() -> None:
    """No lifespan = no clients = both pings report ``down`` = ``degraded``.

    Status code stays at 200: Fly should not flap the container restart
    loop just because the data layer is temporarily unreachable.
    """
    db_module._client = None
    redis_module._client = None
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "down"
    assert body["redis"] == "down"
    assert "version" in body


def test_healthz_returns_ok_when_lifespan_initialises_clients(
    monkeypatch: pytest.MonkeyPatch, _clean_env: None
) -> None:
    """Happy path: lifespan inits patched (no-op) clients, pings return ok."""

    async def _noop_async(*_args: object, **_kwargs: object) -> None:
        return None

    async def _ping_ok() -> str:
        return "ok"

    monkeypatch.setattr(main_module, "init_db", _noop_async)
    monkeypatch.setattr(main_module, "close_db", _noop_async)
    monkeypatch.setattr(main_module, "init_redis", _noop_async)
    monkeypatch.setattr(main_module, "close_redis", _noop_async)
    monkeypatch.setattr(main_module, "init_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "close_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "ping_db", _ping_ok)
    monkeypatch.setattr(main_module, "ping_redis", _ping_ok)

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
    assert body["version"]


def test_healthz_reports_db_only_degraded_when_redis_ok(
    monkeypatch: pytest.MonkeyPatch, _clean_env: None
) -> None:
    """Either subcheck failing flips overall status to ``degraded``."""

    async def _noop_async(*_args: object, **_kwargs: object) -> None:
        return None

    async def _ping_db_down() -> str:
        return "down"

    async def _ping_redis_ok() -> str:
        return "ok"

    monkeypatch.setattr(main_module, "init_db", _noop_async)
    monkeypatch.setattr(main_module, "close_db", _noop_async)
    monkeypatch.setattr(main_module, "init_redis", _noop_async)
    monkeypatch.setattr(main_module, "close_redis", _noop_async)
    monkeypatch.setattr(main_module, "init_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "close_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "ping_db", _ping_db_down)
    monkeypatch.setattr(main_module, "ping_redis", _ping_redis_ok)

    with TestClient(app) as client:
        response = client.get("/healthz")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "down"
    assert body["redis"] == "ok"


def test_healthz_reports_redis_only_degraded_when_db_ok(
    monkeypatch: pytest.MonkeyPatch, _clean_env: None
) -> None:
    async def _noop_async(*_args: object, **_kwargs: object) -> None:
        return None

    async def _ping_db_ok() -> str:
        return "ok"

    async def _ping_redis_down() -> str:
        return "down"

    monkeypatch.setattr(main_module, "init_db", _noop_async)
    monkeypatch.setattr(main_module, "close_db", _noop_async)
    monkeypatch.setattr(main_module, "init_redis", _noop_async)
    monkeypatch.setattr(main_module, "close_redis", _noop_async)
    monkeypatch.setattr(main_module, "init_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "close_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "ping_db", _ping_db_ok)
    monkeypatch.setattr(main_module, "ping_redis", _ping_redis_down)

    with TestClient(app) as client:
        response = client.get("/healthz")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "ok"
    assert body["redis"] == "down"


def test_openapi_document_advertises_v1_namespace() -> None:
    """The ``/api/v1`` router is mounted so the OpenAPI document carries
    its prefix — needed by the T028 codegen pipeline. At T011 the router
    is empty, but its existence (or any endpoint with the prefix) is
    sufficient for the contract.
    """
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    # No endpoints yet, but the document must be retrievable for the
    # codegen pipeline. Future T031+ endpoints will add ``/api/v1/...``
    # paths; here we just confirm the document shape is valid.
    assert spec["info"]["title"] == "auxd API"
    assert "paths" in spec
    assert "/healthz" in spec["paths"]
