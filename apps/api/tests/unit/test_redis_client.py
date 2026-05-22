"""Unit tests for :mod:`auxd_api.redis_client` (T011 + T013).

T011 owns the connection-management primitives (``init_redis``,
``close_redis``, ``get_redis``, ``ping_redis``); T013 adds the arq
enqueue pool, the cache wrappers (fail-open + Sentry-alert), and the
job-enqueue wrapper (raise :class:`JobEnqueueUnavailable` + Sentry-alert).

Tests never touch a real Redis — the async ``redis.asyncio.Redis``
client is replaced with a :class:`MagicMock` whose async methods are
:class:`AsyncMock` instances.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from auxd_api import redis_client as redis_module
from auxd_api.redis_client import (
    JobEnqueueUnavailable,
    cache_get,
    cache_set,
    close_arq_pool,
    close_redis,
    enqueue_job,
    get_arq_pool,
    get_redis,
    init_redis,
    ping_redis,
)


def _build_fake_client(ping_outcome: object = True) -> MagicMock:
    fake = MagicMock(name="redis-client")
    if isinstance(ping_outcome, Exception):
        fake.ping = AsyncMock(side_effect=ping_outcome)
    else:
        fake.ping = AsyncMock(return_value=ping_outcome)
    fake.aclose = AsyncMock()
    return fake


@pytest.mark.asyncio
async def test_init_redis_pings_and_stores_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _build_fake_client(ping_outcome=True)
    monkeypatch.setattr(Redis, "from_url", lambda *_a, **_kw: fake)
    redis_module._client = None
    try:
        await init_redis("redis://localhost:6379/0")
        fake.ping.assert_awaited_once()
        assert get_redis() is fake
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_init_redis_closes_client_when_ping_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _build_fake_client(ping_outcome=RedisConnectionError("connection refused"))
    monkeypatch.setattr(Redis, "from_url", lambda *_a, **_kw: fake)
    redis_module._client = None

    with pytest.raises(RedisConnectionError):
        await init_redis("redis://localhost:6379/0")

    fake.aclose.assert_awaited_once()
    assert redis_module._client is None


def test_get_redis_before_init_raises() -> None:
    redis_module._client = None
    with pytest.raises(RuntimeError, match="not initialised"):
        get_redis()


@pytest.mark.asyncio
async def test_close_redis_is_idempotent() -> None:
    fake = _build_fake_client()
    redis_module._client = fake
    await close_redis()
    fake.aclose.assert_awaited_once()
    assert redis_module._client is None

    # Second call is a no-op.
    await close_redis()
    fake.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ping_redis_returns_down_when_uninitialised() -> None:
    redis_module._client = None
    assert await ping_redis() == "down"


@pytest.mark.asyncio
async def test_ping_redis_returns_ok_when_ping_succeeds() -> None:
    fake = _build_fake_client(ping_outcome=True)
    redis_module._client = fake
    try:
        assert await ping_redis() == "ok"
        fake.ping.assert_awaited_once()
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_ping_redis_returns_down_on_redis_error() -> None:
    fake = _build_fake_client(ping_outcome=RedisConnectionError("disconnected"))
    redis_module._client = fake
    try:
        assert await ping_redis() == "down"
    finally:
        redis_module._client = None


# ---------------------------------------------------------------------------
# T013 — cache wrappers (fail-open)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_uninitialised() -> None:
    redis_module._client = None
    assert await cache_get("any-key") is None


@pytest.mark.asyncio
async def test_cache_get_returns_value_on_success() -> None:
    fake = MagicMock()
    fake.get = AsyncMock(return_value="cached-value")
    redis_module._client = fake
    try:
        assert await cache_get("k") == "cached-value"
        fake.get.assert_awaited_once_with("k")
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_cache_get_fails_open_with_sentry_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.get = AsyncMock(side_effect=RedisTimeoutError("slow"))
    redis_module._client = fake

    alerts: list[dict[str, object]] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_cache_down",
        lambda operation, exc: alerts.append({"operation": operation, "exc_type": type(exc)}),
    )
    try:
        assert await cache_get("k") is None
        assert len(alerts) == 1
        assert alerts[0]["operation"] == "get:k"
        assert alerts[0]["exc_type"] is RedisTimeoutError
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_cache_set_no_op_when_uninitialised() -> None:
    redis_module._client = None
    await cache_set("k", "v")  # must not raise


@pytest.mark.asyncio
async def test_cache_set_writes_value_on_success() -> None:
    fake = MagicMock()
    fake.set = AsyncMock(return_value=True)
    redis_module._client = fake
    try:
        await cache_set("k", "v", ex_seconds=60)
        fake.set.assert_awaited_once_with("k", "v", ex=60)
    finally:
        redis_module._client = None


@pytest.mark.asyncio
async def test_cache_set_fails_open_with_sentry_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.set = AsyncMock(side_effect=RedisConnectionError("disconnected"))
    redis_module._client = fake

    alerts: list[dict[str, object]] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_cache_down",
        lambda operation, exc: alerts.append({"operation": operation, "exc_type": type(exc)}),
    )
    try:
        await cache_set("k", "v")  # must not raise
        assert len(alerts) == 1
        assert alerts[0]["operation"] == "set:k"
    finally:
        redis_module._client = None


# ---------------------------------------------------------------------------
# T013 — arq pool + enqueue_job (fail-503)
# ---------------------------------------------------------------------------


def test_get_arq_pool_before_init_raises() -> None:
    redis_module._arq_pool = None
    with pytest.raises(RuntimeError, match="arq pool is not initialised"):
        get_arq_pool()


@pytest.mark.asyncio
async def test_init_arq_pool_creates_and_stores_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pool = MagicMock(name="arq-pool")
    fake_pool.aclose = AsyncMock()

    async def _fake_create_pool(_settings: object) -> object:
        return fake_pool

    monkeypatch.setattr(redis_module, "create_pool", _fake_create_pool)
    redis_module._arq_pool = None
    try:
        await redis_module.init_arq_pool("redis://localhost:6379/0")
        assert get_arq_pool() is fake_pool
    finally:
        redis_module._arq_pool = None


@pytest.mark.asyncio
async def test_close_arq_pool_is_idempotent() -> None:
    fake_pool = MagicMock()
    fake_pool.aclose = AsyncMock()
    redis_module._arq_pool = fake_pool
    await close_arq_pool()
    fake_pool.aclose.assert_awaited_once()
    assert redis_module._arq_pool is None
    # Second call is a no-op.
    await close_arq_pool()
    fake_pool.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_job_returns_arq_job_on_success() -> None:
    fake_job = MagicMock(name="arq-job")
    fake_pool = MagicMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    redis_module._arq_pool = fake_pool
    try:
        job = await enqueue_job("noop_job", 1, key="value")
        assert job is fake_job
        fake_pool.enqueue_job.assert_awaited_once_with("noop_job", 1, key="value")
    finally:
        redis_module._arq_pool = None


@pytest.mark.asyncio
async def test_enqueue_job_raises_job_enqueue_unavailable_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pool = MagicMock()
    fake_pool.enqueue_job = AsyncMock(side_effect=RedisConnectionError("broker unreachable"))
    redis_module._arq_pool = fake_pool

    alerts: list[str] = []
    monkeypatch.setattr(
        redis_module,
        "_alert_jobs_down",
        lambda job_name, exc: alerts.append(job_name),
    )
    try:
        with pytest.raises(JobEnqueueUnavailable, match="broker unreachable"):
            await enqueue_job("send_email", to="x@y.z")
        assert alerts == ["send_email"]
    finally:
        redis_module._arq_pool = None


@pytest.mark.asyncio
async def test_enqueue_job_raises_runtime_when_pool_uninitialised() -> None:
    redis_module._arq_pool = None
    with pytest.raises(RuntimeError, match="arq pool is not initialised"):
        await enqueue_job("any_job")
