"""Integration tests for the T013 Redis fail-mode contracts.

These tests live next to the unit tests but use a real FastAPI app + an
in-process :class:`TestClient` to exercise the contracts end-to-end:

* ``cache_get``/``cache_set`` FAIL OPEN — the request continues, returns
  a 200, and the Sentry alert (``cache.redis_down``) is emitted exactly
  once per affected operation.
* ``enqueue_job`` FAILS LOUD via :class:`JobEnqueueUnavailable`, which the
  global FastAPI exception handler converts into ``HTTP 503``. The
  Sentry alert (``jobs.redis_down``) is emitted before the response is
  sent.

The tests are integration-flavoured because they cross the helper →
exception-handler → response shape boundary, but they don't require a
running Redis: the underlying client objects are replaced with mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from auxd_api import redis_client as redis_module
from auxd_api.main import _handle_job_enqueue_unavailable
from auxd_api.redis_client import (
    JobEnqueueUnavailable,
    cache_get,
    cache_set,
    enqueue_job,
)


@pytest.fixture
def _isolate_redis_module() -> Iterator[None]:
    """Reset module-level singletons before/after each test so state can't leak."""
    redis_module._client = None
    redis_module._arq_pool = None
    yield
    redis_module._client = None
    redis_module._arq_pool = None


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app that mirrors main.py's exception handler.

    A standalone app keeps the test independent of any lifespan side
    effects (DB, OTel) — the only behaviour under test is the
    :class:`JobEnqueueUnavailable` → 503 conversion.
    """
    app = FastAPI()
    # Cast: starlette's ``add_exception_handler`` is typed against
    # ``Exception`` while our handler narrows to ``JobEnqueueUnavailable``;
    # the looser typing is a known framework limitation.
    app.add_exception_handler(JobEnqueueUnavailable, _handle_job_enqueue_unavailable)  # type: ignore[arg-type]

    @app.post("/test/cache-then-enqueue")
    async def _cache_then_enqueue() -> dict[str, str]:
        # Cache write must not break the request even if Redis is down.
        await cache_set("test:key", "value", ex_seconds=30)
        # Enqueue is load-bearing — its failure should yield 503.
        await enqueue_job("noop_job")
        return {"status": "ok"}

    @app.get("/test/cache-only")
    async def _cache_only() -> dict[str, str | None]:
        value = await cache_get("test:key")
        return {"value": value}

    return app


def test_cache_get_fail_open_yields_200_with_null_value(
    monkeypatch: pytest.MonkeyPatch, _isolate_redis_module: None
) -> None:
    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=RedisConnectionError("disconnected"))
    redis_module._client = fake_client

    alerts: list[str] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_cache_down",
        lambda operation, exc: alerts.append(operation),
    )

    client = TestClient(_make_test_app())
    response = client.get("/test/cache-only")
    assert response.status_code == 200
    assert response.json() == {"value": None}
    assert alerts == ["get:test:key"]


def test_enqueue_failure_returns_503_with_error_body(
    monkeypatch: pytest.MonkeyPatch, _isolate_redis_module: None
) -> None:
    # Cache layer succeeds — the failure is on enqueue only.
    cache_client = MagicMock()
    cache_client.set = AsyncMock(return_value=True)
    redis_module._client = cache_client

    arq_pool = MagicMock()
    arq_pool.enqueue_job = AsyncMock(side_effect=RedisConnectionError("broker unreachable"))
    redis_module._arq_pool = arq_pool

    job_alerts: list[str] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_jobs_down",
        lambda job_name, exc: job_alerts.append(job_name),
    )

    client = TestClient(_make_test_app())
    response = client.post("/test/cache-then-enqueue")
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "job_queue_unavailable"
    assert "noop_job" in body["detail"]
    assert job_alerts == ["noop_job"]


def test_cache_failure_does_not_block_enqueue_path(
    monkeypatch: pytest.MonkeyPatch, _isolate_redis_module: None
) -> None:
    """When cache fails but enqueue succeeds the request still returns 200.

    Locks in the divergent fail modes — cache is best-effort, enqueue is
    load-bearing — so a single Redis blip on one path doesn't poison the
    other.
    """
    cache_client = MagicMock()
    cache_client.set = AsyncMock(side_effect=RedisConnectionError("disconnected"))
    redis_module._client = cache_client

    fake_job = MagicMock(name="job")
    arq_pool = MagicMock()
    arq_pool.enqueue_job = AsyncMock(return_value=fake_job)
    redis_module._arq_pool = arq_pool

    cache_alerts: list[str] = []
    job_alerts: list[str] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_cache_down",
        lambda operation, exc: cache_alerts.append(operation),
    )
    monkeypatch.setattr(
        redis_module,
        "_alert_jobs_down",
        lambda job_name, exc: job_alerts.append(job_name),
    )

    client = TestClient(_make_test_app())
    response = client.post("/test/cache-then-enqueue")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert cache_alerts == ["set:test:key"]
    assert job_alerts == []
