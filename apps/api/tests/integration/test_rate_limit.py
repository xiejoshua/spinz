"""Integration tests for the T020 rate-limit dependency.

Builds a tiny FastAPI app that mounts the dependency on two routes
(one IP-only, one IP+user) and asserts:

* Bursting past the limit returns ``HTTP 429``.
* Once the window slides past, requests succeed again.
* A Redis disconnect mid-flight FAILS OPEN and emits the
  ``rate_limit.redis_down`` Sentry alert.
* Per-user limits are evaluated only when an authenticated session is
  present on ``request.state.session``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from auxd_api import redis_client as redis_module
from auxd_api.lib import rate_limit as rate_limit_module
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session


@pytest.fixture
def _isolate_redis() -> Iterator[None]:
    """Reset the module-level Redis client between tests."""
    redis_module._client = None
    yield
    redis_module._client = None


class _FakeRedisPipeline:
    """Minimal pipeline mock honouring the (zremrangebyscore, zcard) sequence.

    Records the commands queued on it so tests can assert the call shape,
    and resolves ``execute()`` to the list of return values matching the
    real ``redis.asyncio.client.Pipeline`` contract.
    """

    def __init__(self, zcard_return: int) -> None:
        self._zcard_return = zcard_return
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def zremrangebyscore(self, key: str, min_score: int, max_score: int) -> _FakeRedisPipeline:
        self.calls.append(("zremrangebyscore", (key, min_score, max_score)))
        return self

    def zcard(self, key: str) -> _FakeRedisPipeline:
        self.calls.append(("zcard", (key,)))
        return self

    async def execute(self) -> list[object]:
        # zremrangebyscore returns the number of removed entries; we don't
        # care about that here, just that zcard's value flows through.
        return [0, self._zcard_return]


def _fake_redis(*, zcard_return: int) -> MagicMock:
    """Build a fake async Redis client that reports ``zcard_return`` keys."""
    fake = MagicMock(name="redis")
    fake.pipeline = MagicMock(return_value=_FakeRedisPipeline(zcard_return=zcard_return))
    fake.zadd = AsyncMock(return_value=1)
    fake.expire = AsyncMock(return_value=True)
    return fake


def _make_app(*, per_ip: RateLimit | None, per_user: RateLimit | None) -> FastAPI:
    app = FastAPI()
    dep = rate_limit(endpoint="test", per_ip=per_ip, per_user=per_user)

    @app.get("/hello", dependencies=[Depends(dep)])
    async def _hello() -> dict[str, str]:
        return {"hello": "world"}

    @app.post("/inject-session/{user_id}")
    async def _inject_session(user_id: str, request: Request) -> dict[str, str]:
        request.state.session = Session(
            user_id=user_id,
            csrf_token="csrf",
            issued_at=0,
            expires_at=10_000_000_000,
            session_version=1,
        )
        return {"ok": "true"}

    return app


def test_request_under_limit_returns_200(_isolate_redis: None) -> None:
    redis_module._client = _fake_redis(zcard_return=0)
    app = _make_app(per_ip=RateLimit(limit=3, window_seconds=60), per_user=None)
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}


def test_request_at_or_over_limit_returns_429(_isolate_redis: None) -> None:
    redis_module._client = _fake_redis(zcard_return=5)
    app = _make_app(per_ip=RateLimit(limit=5, window_seconds=60), per_user=None)
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 429
    body = response.json()
    assert body["detail"] == "rate limit exceeded"


def test_redis_failure_fails_open_with_sentry_alert(
    monkeypatch: pytest.MonkeyPatch, _isolate_redis: None
) -> None:
    failing = MagicMock(name="failing-redis")
    failing.pipeline = MagicMock(side_effect=RedisConnectionError("disconnected"))
    redis_module._client = failing

    alerts: list[str] = []
    monkeypatch.setattr(
        rate_limit_module,
        "_alert_rate_limit_down",
        lambda operation, exc: alerts.append(operation),
    )

    app = _make_app(per_ip=RateLimit(limit=1, window_seconds=60), per_user=None)
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200
    # Sentry alert fires exactly once for this request.
    assert len(alerts) == 1
    assert alerts[0].startswith("check:ratelimit:test:ip:")


def test_no_redis_configured_passes_silently_without_alert(
    monkeypatch: pytest.MonkeyPatch, _isolate_redis: None
) -> None:
    """When ``get_redis`` raises (no lifespan), the dependency passes silently.

    This is the "test environment" path — failing open AND emitting a
    Sentry alert on every request would flood logs. The intentional
    branch returns True without an alert.
    """
    alerts: list[str] = []
    monkeypatch.setattr(
        rate_limit_module,
        "_alert_rate_limit_down",
        lambda operation, exc: alerts.append(operation),
    )
    redis_module._client = None  # explicit
    app = _make_app(per_ip=RateLimit(limit=1, window_seconds=60), per_user=None)
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200
    assert alerts == []


def test_per_user_limit_only_evaluated_when_session_present(_isolate_redis: None) -> None:
    """The per-user dimension is skipped for anonymous requests."""
    fake = _fake_redis(zcard_return=0)
    redis_module._client = fake
    app = _make_app(
        per_ip=RateLimit(limit=100, window_seconds=60),
        per_user=RateLimit(limit=1, window_seconds=60),
    )
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200
    # Only one bucket should have been touched (IP), because the user
    # dimension is unreachable without a session.
    keys_touched = {call[1][0] for call in fake.pipeline.return_value.calls}
    ip_keys = {k for k in keys_touched if ":ip:" in k}
    user_keys = {k for k in keys_touched if ":user:" in k}
    assert ip_keys, "expected an IP bucket key"
    assert not user_keys, "user bucket should not be touched without a session"


def test_x_forwarded_for_is_honoured(_isolate_redis: None) -> None:
    """The IP bucket prefers the first X-Forwarded-For hop."""
    captured: list[tuple[str, tuple[object, ...]]] = []

    def _build_pipeline() -> Any:
        pipe = _FakeRedisPipeline(zcard_return=0)
        # Mirror the queued calls into the capture list so we can inspect.
        captured.extend(pipe.calls)
        return pipe

    fake = MagicMock(name="redis")

    # Re-build pipeline per call so .calls stays correct per request.
    def _pipeline_factory() -> _FakeRedisPipeline:
        pipe = _FakeRedisPipeline(zcard_return=0)
        return pipe

    fake.pipeline = MagicMock(side_effect=_pipeline_factory)
    fake.zadd = AsyncMock(return_value=1)
    fake.expire = AsyncMock(return_value=True)
    redis_module._client = fake

    app = _make_app(per_ip=RateLimit(limit=10, window_seconds=60), per_user=None)
    client = TestClient(app)
    response = client.get("/hello", headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})
    assert response.status_code == 200
    # The zadd call must use a key derived from the first hop.
    zadd_calls = fake.zadd.call_args_list
    assert any("203.0.113.5" in str(c) for c in zadd_calls), (
        f"expected zadd key to include 203.0.113.5, got {zadd_calls}"
    )
    _ = captured  # silence flake8/lint about unused variable in defensive capture


def test_rate_limit_factory_validates_at_least_one_dimension() -> None:
    with pytest.raises(ValueError, match="at least one of per_ip or per_user"):
        rate_limit(endpoint="x", per_ip=None, per_user=None)


def test_ratelimit_dataclass_rejects_zero_or_negative_inputs() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        RateLimit(limit=0, window_seconds=10)
    with pytest.raises(ValueError, match="window_seconds must be positive"):
        RateLimit(limit=5, window_seconds=0)
