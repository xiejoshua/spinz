"""Unit tests for :mod:`auxd_api.workers.main` (T013 scaffold).

The worker class is consumed by arq through introspection; these tests
guard the contract surface (``functions``, ``redis_settings``,
``keep_result``) and exercise :func:`noop_job` end-to-end.
"""

from __future__ import annotations

import logging

import pytest

from auxd_api.workers import main as workers_module
from auxd_api.workers.main import WorkerSettings, noop_job


def test_worker_settings_registers_noop_job() -> None:
    assert noop_job in WorkerSettings.functions
    assert len(WorkerSettings.functions) >= 1


def test_worker_settings_has_redis_settings_from_env() -> None:
    # Smoke check: ``redis_settings`` is built from REDIS_URL (or the
    # local default) at import time. Either way, the resulting instance
    # carries the standard arq RedisSettings shape.
    assert WorkerSettings.redis_settings is not None
    assert hasattr(WorkerSettings.redis_settings, "host")


def test_worker_settings_keep_result_window() -> None:
    # arq's ``keep_result`` is a TTL in seconds for stored job results.
    # We pin this to 600 in the scaffold so future bumps are intentional.
    assert WorkerSettings.keep_result == 600


@pytest.mark.asyncio
async def test_noop_job_returns_ok_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="auxd.worker")
    ctx = {"job_id": "j-1", "enqueue_time": "2026-01-01T00:00:00Z"}
    result = await noop_job(ctx)
    assert result == "ok"
    # The log line is the operator's anchor: confirm it fires.
    events = [r for r in caplog.records if r.message == "worker.noop_job.executed"]
    assert len(events) == 1


def test_redis_settings_helper_reads_env_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    # The helper reads REDIS_URL straight from os.environ so the worker
    # module can import without going through the full Settings stack.
    monkeypatch.setenv("REDIS_URL", "redis://example.com:9999/3")
    rs = workers_module._redis_settings_from_env()
    assert rs.host == "example.com"
    assert rs.port == 9999
    assert rs.database == 3


def test_redis_settings_helper_falls_back_to_local_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When REDIS_URL is unset, the helper falls back to the same local
    # default that Settings.REDIS_URL would use — that's what makes the
    # WorkerSettings class-body evaluation import-safe in CI.
    monkeypatch.delenv("REDIS_URL", raising=False)
    rs = workers_module._redis_settings_from_env()
    assert rs.host == "localhost"
    assert rs.port == 6379
    assert rs.database == 0
