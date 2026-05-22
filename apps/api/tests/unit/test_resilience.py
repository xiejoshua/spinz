"""Unit tests for :mod:`auxd_api.lib.resilience` (Constitution Principle I)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from auxd_api.lib import resilience
from auxd_api.lib.resilience import (
    CircuitBreakerOpenError,
    CircuitBreakerState,
    InMemoryCircuitBreakerStore,
    call_with_resilience,
    circuit_breaker,
    circuit_breaker_decorator,
    get_default_store,
    retry,
    set_default_store,
    timeout,
)


@pytest.fixture(autouse=True)
def _isolate_store() -> Any:
    """Each test starts with a fresh in-memory store."""
    original = get_default_store()
    set_default_store(InMemoryCircuitBreakerStore())
    yield
    set_default_store(original)


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class TestRetry:
    async def test_retry_succeeds_on_first_attempt(self) -> None:
        calls = 0

        async def func() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        result = await retry(func, attempts=3)
        assert result == "ok"
        assert calls == 1

    async def test_retry_succeeds_after_failures(self) -> None:
        calls = 0

        async def func() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")
            return "ok"

        result = await retry(func, attempts=3, base_delay=0.0)
        assert result == "ok"
        assert calls == 3

    async def test_retry_exhaustion_raises(self) -> None:
        calls = 0

        async def func() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError(f"boom {calls}")

        with pytest.raises(RuntimeError, match="boom 3"):
            await retry(func, attempts=3, base_delay=0.0)
        assert calls == 3

    async def test_retry_only_retries_listed_exceptions(self) -> None:
        calls = 0

        async def func() -> None:
            nonlocal calls
            calls += 1
            raise KeyError("not retryable")

        with pytest.raises(KeyError):
            await retry(func, attempts=3, retry_on=(ValueError,), base_delay=0.0)
        assert calls == 1

    async def test_retry_backoff_exponential(self) -> None:
        async def func() -> None:
            raise RuntimeError("boom")

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with pytest.raises(RuntimeError):
                await retry(
                    func,
                    attempts=4,
                    backoff="exponential",
                    base_delay=0.5,
                    max_delay=30.0,
                )

            # 3 retries (after attempts 1, 2, 3) → delays 0.5, 1.0, 2.0.
            delays = [call.args[0] for call in sleep_mock.await_args_list]
            assert delays == [0.5, 1.0, 2.0]

    async def test_retry_backoff_linear(self) -> None:
        async def func() -> None:
            raise RuntimeError("boom")

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with pytest.raises(RuntimeError):
                await retry(
                    func,
                    attempts=4,
                    backoff="linear",
                    base_delay=0.5,
                    max_delay=30.0,
                )

            delays = [call.args[0] for call in sleep_mock.await_args_list]
            assert delays == [0.5, 1.0, 1.5]

    async def test_retry_backoff_fixed(self) -> None:
        async def func() -> None:
            raise RuntimeError("boom")

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with pytest.raises(RuntimeError):
                await retry(
                    func,
                    attempts=4,
                    backoff="fixed",
                    base_delay=0.25,
                )

            delays = [call.args[0] for call in sleep_mock.await_args_list]
            assert delays == [0.25, 0.25, 0.25]

    async def test_retry_backoff_respects_max_delay(self) -> None:
        async def func() -> None:
            raise RuntimeError("boom")

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with pytest.raises(RuntimeError):
                await retry(
                    func,
                    attempts=5,
                    backoff="exponential",
                    base_delay=1.0,
                    max_delay=3.0,
                )

            delays = [call.args[0] for call in sleep_mock.await_args_list]
            # 1.0, 2.0, 4.0→3.0, 8.0→3.0
            assert delays == [1.0, 2.0, 3.0, 3.0]

    async def test_retry_on_retry_callback_invoked(self) -> None:
        calls: list[tuple[int, Exception]] = []

        async def func() -> None:
            raise RuntimeError(f"boom-{len(calls)}")

        def cb(attempt: int, exc: Exception) -> None:
            calls.append((attempt, exc))

        with pytest.raises(RuntimeError):
            await retry(func, attempts=3, base_delay=0.0, on_retry=cb)

        # Callback fires for each *failed* attempt that triggers a retry — i.e.
        # before the sleep that precedes the *next* attempt. Final failure
        # propagates without firing the callback.
        assert len(calls) == 2
        assert [a for a, _ in calls] == [1, 2]
        assert all(isinstance(e, RuntimeError) for _, e in calls)

    async def test_retry_does_not_retry_circuit_breaker_open(self) -> None:
        calls = 0

        async def func() -> None:
            nonlocal calls
            calls += 1
            raise CircuitBreakerOpenError("test")

        with pytest.raises(CircuitBreakerOpenError):
            await retry(func, attempts=5, base_delay=0.0)
        assert calls == 1

    async def test_retry_rejects_zero_attempts(self) -> None:
        async def func() -> str:
            return "ok"

        with pytest.raises(ValueError, match="attempts must be >= 1"):
            await retry(func, attempts=0)


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    async def test_timeout_passes_through_on_fast(self) -> None:
        async with timeout(1.0):
            await asyncio.sleep(0)
        # No exception → success.

    async def test_timeout_raises_on_slow(self) -> None:
        with pytest.raises(asyncio.TimeoutError):
            async with timeout(0.05):
                await asyncio.sleep(1.0)

    async def test_timeout_cancellation_propagates(self) -> None:
        """Slow inner work is cancelled cleanly; the cancel is observable."""
        finally_ran = False

        async def slow() -> None:
            nonlocal finally_ran
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                finally_ran = True
                raise

        with pytest.raises(asyncio.TimeoutError):
            async with timeout(0.05):
                await slow()

        assert finally_ran is True


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    async def test_cb_closed_allows_calls(self) -> None:
        for _ in range(3):
            async with circuit_breaker("svc-a", failure_threshold=5):
                pass
        state = await get_default_store().get_state("svc-a")
        assert state.state == "closed"
        assert state.consecutive_failures == 0

    async def test_cb_opens_after_threshold_failures(self) -> None:
        for _ in range(5):
            with pytest.raises(RuntimeError):
                async with circuit_breaker("svc-b", failure_threshold=5):
                    raise RuntimeError("boom")

        state = await get_default_store().get_state("svc-b")
        assert state.state == "open"
        assert state.consecutive_failures == 5
        assert state.opened_at is not None

    async def test_cb_open_raises_immediately(self) -> None:
        # Force-open the breaker via the store.
        store = get_default_store()
        await store.set_state(
            "svc-c",
            CircuitBreakerState(state="open", consecutive_failures=5, opened_at=datetime.now(UTC)),
        )

        called = False

        async def inner() -> None:
            nonlocal called
            called = True

        with pytest.raises(CircuitBreakerOpenError) as excinfo:
            async with circuit_breaker("svc-c", failure_threshold=5, recovery_timeout=60):
                await inner()

        assert called is False
        assert excinfo.value.name == "svc-c"

    async def test_cb_transitions_to_half_open_after_recovery_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = get_default_store()
        opened_at = datetime.now(UTC) - timedelta(seconds=120)
        await store.set_state(
            "svc-d",
            CircuitBreakerState(state="open", consecutive_failures=5, opened_at=opened_at),
        )

        # Fake "now" to be 120s after open.
        monkeypatch.setattr(resilience, "_now", lambda: opened_at + timedelta(seconds=120))

        # First call after recovery → enters half_open and probe runs.
        async with circuit_breaker("svc-d", failure_threshold=5, recovery_timeout=30):
            mid = await store.get_state("svc-d")
            assert mid.state == "half_open"

        final = await store.get_state("svc-d")
        # Successful probe closes the breaker.
        assert final.state == "closed"
        assert final.consecutive_failures == 0
        assert final.opened_at is None

    async def test_cb_half_open_success_closes(self) -> None:
        store = get_default_store()
        # Start directly in half_open.
        await store.set_state(
            "svc-e",
            CircuitBreakerState(
                state="half_open", consecutive_failures=3, opened_at=datetime.now(UTC)
            ),
        )

        async with circuit_breaker("svc-e", failure_threshold=5, recovery_timeout=30):
            pass

        state = await store.get_state("svc-e")
        assert state.state == "closed"
        assert state.consecutive_failures == 0
        assert state.opened_at is None

    async def test_cb_half_open_failure_reopens(self) -> None:
        store = get_default_store()
        old_opened_at = datetime.now(UTC) - timedelta(seconds=300)
        await store.set_state(
            "svc-f",
            CircuitBreakerState(state="half_open", consecutive_failures=5, opened_at=old_opened_at),
        )

        with pytest.raises(RuntimeError):
            async with circuit_breaker("svc-f", failure_threshold=5, recovery_timeout=30):
                raise RuntimeError("probe failed")

        state = await store.get_state("svc-f")
        assert state.state == "open"
        assert state.opened_at is not None
        # Timer reset: opened_at advanced beyond the original.
        assert state.opened_at > old_opened_at

    async def test_cb_independent_names(self) -> None:
        # Trip svc-foo, leave svc-bar alone.
        for _ in range(5):
            with pytest.raises(RuntimeError):
                async with circuit_breaker("svc-foo", failure_threshold=5):
                    raise RuntimeError("boom")

        foo = await get_default_store().get_state("svc-foo")
        bar = await get_default_store().get_state("svc-bar")
        assert foo.state == "open"
        assert bar.state == "closed"
        # svc-bar still works.
        async with circuit_breaker("svc-bar", failure_threshold=5):
            pass

    async def test_cb_success_resets_failure_counter(self) -> None:
        # 3 failures, then a success → counter resets, breaker stays closed.
        for _ in range(3):
            with pytest.raises(RuntimeError):
                async with circuit_breaker("svc-g", failure_threshold=5):
                    raise RuntimeError("boom")
        async with circuit_breaker("svc-g", failure_threshold=5):
            pass
        state = await get_default_store().get_state("svc-g")
        assert state.state == "closed"
        assert state.consecutive_failures == 0

    async def test_cb_decorator_form(self) -> None:
        calls = 0

        @circuit_breaker_decorator("svc-deco", failure_threshold=3)
        async def flaky() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await flaky()

        # Fourth call should short-circuit.
        with pytest.raises(CircuitBreakerOpenError):
            await flaky()
        # Inner func never invoked the 4th time.
        assert calls == 3

    async def test_cb_explicit_store_overrides_default(self) -> None:
        custom = InMemoryCircuitBreakerStore()
        for _ in range(5):
            with pytest.raises(RuntimeError):
                async with circuit_breaker("svc-custom", failure_threshold=5, store=custom):
                    raise RuntimeError("boom")

        # Custom store tripped; default store unaffected.
        in_custom = await custom.get_state("svc-custom")
        in_default = await get_default_store().get_state("svc-custom")
        assert in_custom.state == "open"
        assert in_default.state == "closed"

    async def test_cb_nested_open_propagates_without_double_counting(self) -> None:
        store = get_default_store()
        # Pre-open svc-inner.
        await store.set_state(
            "svc-inner",
            CircuitBreakerState(state="open", consecutive_failures=5, opened_at=datetime.now(UTC)),
        )

        with pytest.raises(CircuitBreakerOpenError):
            async with circuit_breaker("svc-outer", failure_threshold=5, recovery_timeout=60):
                async with circuit_breaker("svc-inner", failure_threshold=5, recovery_timeout=60):
                    pass

        # Outer breaker did NOT count the inner short-circuit as a failure.
        outer = await store.get_state("svc-outer")
        assert outer.state == "closed"
        assert outer.consecutive_failures == 0


# ---------------------------------------------------------------------------
# Composed
# ---------------------------------------------------------------------------


class TestComposed:
    async def test_call_with_resilience_happy_path(self) -> None:
        async def func() -> int:
            return 42

        result = await call_with_resilience(
            "svc-happy", func, retry_attempts=3, timeout_seconds=1.0
        )
        assert result == 42

    async def test_call_with_resilience_retries_then_succeeds(self) -> None:
        calls = 0

        async def func() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")
            return "ok"

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await call_with_resilience(
                "svc-retry",
                func,
                retry_attempts=3,
                timeout_seconds=1.0,
                cb_failure_threshold=10,
            )
        assert result == "ok"
        assert calls == 3

    async def test_call_with_resilience_opens_circuit_after_repeated_failures(self) -> None:
        async def always_fails() -> None:
            raise RuntimeError("boom")

        with patch("auxd_api.lib.resilience.asyncio.sleep", new_callable=AsyncMock):
            # cb_failure_threshold=2 with retry_attempts=3 means a single outer
            # call_with_resilience produces exactly one CB increment (on the
            # final retry exhaustion). Two such calls trip the breaker.
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await call_with_resilience(
                        "svc-trip",
                        always_fails,
                        retry_attempts=3,
                        timeout_seconds=1.0,
                        cb_failure_threshold=2,
                    )

        state = await get_default_store().get_state("svc-trip")
        assert state.state == "open"

        # Next call short-circuits immediately, never invokes the function.
        called = False

        async def should_not_run() -> None:
            nonlocal called
            called = True

        with pytest.raises(CircuitBreakerOpenError):
            await call_with_resilience(
                "svc-trip",
                should_not_run,
                retry_attempts=3,
                timeout_seconds=1.0,
                cb_failure_threshold=2,
                cb_recovery_timeout=60,
            )
        assert called is False

    async def test_call_with_resilience_per_attempt_timeout(self) -> None:
        """Each retry attempt gets its own ``timeout_seconds`` budget."""

        async def slow() -> None:
            await asyncio.sleep(1.0)

        with pytest.raises(asyncio.TimeoutError):
            await call_with_resilience(
                "svc-slow",
                slow,
                retry_attempts=1,  # no retries → single attempt, fast failure
                timeout_seconds=0.05,
                cb_failure_threshold=10,
            )
