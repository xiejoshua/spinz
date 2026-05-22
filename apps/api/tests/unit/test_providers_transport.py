"""Unit tests for :mod:`auxd_api.providers.transport` (T050 + T051)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from auxd_api.lib.resilience import (
    InMemoryCircuitBreakerStore,
    get_default_store,
    set_default_store,
)
from auxd_api.providers.errors import (
    ProviderRateLimited,
    ProviderUnavailable,
)
from auxd_api.providers.transport import ResilienceTransport, build_async_client


@pytest.fixture(autouse=True)
def _isolate_store() -> Iterator[None]:
    """Fresh in-memory breaker store per test (mirrors test_resilience.py)."""
    original = get_default_store()
    set_default_store(InMemoryCircuitBreakerStore())
    yield
    set_default_store(original)


@pytest.fixture
def _no_sleep() -> Iterator[None]:
    """Skip retry-backoff sleeps so tests stay fast.

    Opt-in (not autouse) because the patch replaces the global
    ``asyncio.sleep`` reference — tests that rely on real sleeps for
    timeout assertions must NOT enable it.
    """
    with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock):
        yield


def _make_transport(
    inner: httpx.AsyncBaseTransport,
    **overrides: Any,
) -> ResilienceTransport:
    defaults: dict[str, Any] = {
        "provider_name": "testprov",
        "retry_attempts": 3,
        "retry_base_delay": 0.0,
        "timeout_seconds": 1.0,
        "inner_transport": inner,
    }
    defaults.update(overrides)
    return ResilienceTransport(**defaults)


# ---------------------------------------------------------------------------
# T050 — resilience behaviour
# ---------------------------------------------------------------------------


class TestResilienceTransport:
    async def test_200_passes_through(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock),
        ) as client:
            resp = await client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_429_raises_provider_rate_limited_without_retry(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(429, json={"error": "rate"})

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock, retry_attempts=3),
        ) as client:
            with pytest.raises(ProviderRateLimited) as excinfo:
                await client.get("/search")

        assert call_count == 1, "429 must NOT retry; saw {call_count} attempts"
        assert excinfo.value.provider == "testprov"

    async def test_503_retries_then_raises_provider_unavailable(self, _no_sleep: None) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(503, json={"error": "boom"})

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock, retry_attempts=3),
        ) as client:
            with pytest.raises(ProviderUnavailable) as excinfo:
                await client.get("/search")

        assert call_count == 3
        assert excinfo.value.provider == "testprov"

    async def test_connection_error_raises_provider_unavailable(self, _no_sleep: None) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock, retry_attempts=2),
        ) as client:
            with pytest.raises(ProviderUnavailable):
                await client.get("/")

    async def test_5xx_then_200_succeeds(self, _no_sleep: None) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return httpx.Response(502, json={})
            return httpx.Response(200, json={"ok": True})

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock, retry_attempts=3),
        ) as client:
            resp = await client.get("/")
        assert resp.status_code == 200
        assert attempts == 2

    async def test_4xx_non_429_passes_through(self) -> None:
        """404 must NOT raise — it's a normal lookup outcome for providers."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        mock = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://x.test",
            transport=_make_transport(mock),
        ) as client:
            resp = await client.get("/missing")
        assert resp.status_code == 404

    async def test_build_async_client_attaches_user_agent(self) -> None:
        seen_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(200, json={})

        mock = httpx.MockTransport(handler)
        async with build_async_client(
            base_url="https://x.test",
            provider_name="testprov",
            user_agent="auxd/0.0.0 (test)",
            inner_transport=mock,
        ) as client:
            await client.get("/")
        assert seen_headers["user-agent"] == "auxd/0.0.0 (test)"


# ---------------------------------------------------------------------------
# T051 — observability instrumentation
# ---------------------------------------------------------------------------


class TestObservabilityInstrumentation:
    async def test_log_call_emitted_once_on_success(self, caplog: pytest.LogCaptureFixture) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        mock = httpx.MockTransport(handler)
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            async with httpx.AsyncClient(
                base_url="https://x.test",
                transport=_make_transport(mock),
            ) as client:
                await client.get("/hello")

        external_calls = [r for r in caplog.records if getattr(r, "event", None) == "external_call"]
        assert len(external_calls) == 1
        record = external_calls[0]
        assert record.provider == "testprov"  # type: ignore[attr-defined]
        assert record.endpoint == "/hello"  # type: ignore[attr-defined]
        assert record.status == 200  # type: ignore[attr-defined]
        assert isinstance(record.latency_ms, float)  # type: ignore[attr-defined]
        assert record.latency_ms >= 0.0  # type: ignore[attr-defined]

    async def test_log_call_emitted_with_429_status(
        self, caplog: pytest.LogCaptureFixture, _no_sleep: None
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        mock = httpx.MockTransport(handler)
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            async with httpx.AsyncClient(
                base_url="https://x.test",
                transport=_make_transport(mock),
            ) as client:
                with pytest.raises(ProviderRateLimited):
                    await client.get("/rate")

        external_calls = [r for r in caplog.records if getattr(r, "event", None) == "external_call"]
        assert len(external_calls) == 1
        assert external_calls[0].status == 429  # type: ignore[attr-defined]

    async def test_log_call_emitted_with_timeout_sentinel(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import asyncio as _asyncio

        async def slow_handler(request: httpx.Request) -> httpx.Response:
            await _asyncio.sleep(5.0)
            return httpx.Response(200)

        mock = httpx.MockTransport(slow_handler)
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            async with httpx.AsyncClient(
                base_url="https://x.test",
                transport=_make_transport(mock, retry_attempts=1, timeout_seconds=0.05),
            ) as client:
                with pytest.raises(ProviderUnavailable):
                    await client.get("/slow")

        external_calls = [r for r in caplog.records if getattr(r, "event", None) == "external_call"]
        assert len(external_calls) == 1
        assert external_calls[0].status == "timeout"  # type: ignore[attr-defined]

    async def test_log_call_propagates_request_id_header(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        mock = httpx.MockTransport(handler)
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            async with httpx.AsyncClient(
                base_url="https://x.test",
                transport=_make_transport(mock),
            ) as client:
                await client.get("/x", headers={"X-Request-Id": "req-abc123"})

        external_calls = [r for r in caplog.records if getattr(r, "event", None) == "external_call"]
        assert len(external_calls) == 1
        assert external_calls[0].request_id == "req-abc123"  # type: ignore[attr-defined]
