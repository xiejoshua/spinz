"""External-call resilience primitives — Constitution Principle I (NON-NEGOTIABLE).

This module is the *only* sanctioned entry point for outbound provider/API
calls in the auxd backend. Every such call MUST be wrapped (composed in this
order, outside → inside) in::

    circuit_breaker(name)
        retry(attempts=..., backoff=...)
            timeout(seconds=...)
                <the actual provider call>

Public surface
==============
* :func:`circuit_breaker` — async context manager guarding a named breaker.
* :func:`circuit_breaker_decorator` — decorator form of the breaker.
* :func:`retry` — async retry helper with pluggable backoff.
* :func:`timeout` — thin async context manager wrapping :func:`asyncio.timeout`.
* :func:`call_with_resilience` — composed convenience that applies all three.
* :class:`CircuitBreakerOpenError` — raised when a call is short-circuited.
* :class:`CircuitBreakerState`, :class:`CircuitBreakerStore`,
  :class:`InMemoryCircuitBreakerStore`, :func:`set_default_store`,
  :func:`get_default_store` — circuit-breaker state plumbing.

Storage abstraction
===================
The breaker state is read/written through a :class:`CircuitBreakerStore`
:class:`~typing.Protocol`. The default implementation
(:class:`InMemoryCircuitBreakerStore`) keeps state in a per-process ``dict``;
this is fine for unit tests and single-worker dev. In multi-worker
production we plug in a Redis-backed store via :func:`set_default_store`
(see plan §5.3, task T020).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Literal, Protocol

BackoffStrategy = Literal["exponential", "linear", "fixed"]
CircuitState = Literal["closed", "open", "half_open"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CircuitBreakerOpenError(Exception):
    """Raised when a call is short-circuited because the breaker is open.

    Feature code should treat this as a *fast failure*: it means the
    downstream provider is currently considered unhealthy and we are
    deliberately refusing to add load. It MUST NOT be retried — see
    :func:`retry` which excludes it explicitly.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"circuit breaker '{name}' is open")
        self.name = name


# ---------------------------------------------------------------------------
# State + storage
# ---------------------------------------------------------------------------


@dataclass
class CircuitBreakerState:
    """Persisted state of a single named circuit breaker."""

    state: CircuitState = "closed"
    consecutive_failures: int = 0
    opened_at: datetime | None = None


class CircuitBreakerStore(Protocol):
    """Abstract storage backend for circuit-breaker state.

    Implementations must be safe to call concurrently from multiple tasks.
    The default in-process implementation guards with an
    :class:`asyncio.Lock`; a Redis-backed implementation will rely on
    atomic Redis operations.
    """

    async def get_state(self, name: str) -> CircuitBreakerState: ...

    async def set_state(self, name: str, state: CircuitBreakerState) -> None: ...


@dataclass
class InMemoryCircuitBreakerStore:
    """Per-process in-memory store. Default for tests and single-worker dev."""

    _states: dict[str, CircuitBreakerState] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get_state(self, name: str) -> CircuitBreakerState:
        async with self._lock:
            existing = self._states.get(name)
            if existing is None:
                fresh = CircuitBreakerState()
                self._states[name] = fresh
                return CircuitBreakerState(
                    state=fresh.state,
                    consecutive_failures=fresh.consecutive_failures,
                    opened_at=fresh.opened_at,
                )
            # Return a copy so callers can't mutate the stored object.
            return CircuitBreakerState(
                state=existing.state,
                consecutive_failures=existing.consecutive_failures,
                opened_at=existing.opened_at,
            )

    async def set_state(self, name: str, state: CircuitBreakerState) -> None:
        async with self._lock:
            self._states[name] = CircuitBreakerState(
                state=state.state,
                consecutive_failures=state.consecutive_failures,
                opened_at=state.opened_at,
            )


_default_store: CircuitBreakerStore = InMemoryCircuitBreakerStore()


def set_default_store(store: CircuitBreakerStore) -> None:
    """Replace the process-wide default circuit-breaker store.

    Called once at application startup when a Redis-backed store becomes
    available (T020). Tests may also call this — they should restore the
    previous store afterwards via :func:`get_default_store`.
    """
    global _default_store
    _default_store = store


def get_default_store() -> CircuitBreakerStore:
    """Return the current process-wide default circuit-breaker store."""
    return _default_store


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@asynccontextmanager
async def timeout(seconds: float) -> AsyncIterator[None]:
    """Wrap an ``async with`` block in :func:`asyncio.timeout`.

    Raises:
        asyncio.TimeoutError: When the wrapped block exceeds ``seconds``.
            (Note: under the hood :func:`asyncio.timeout` raises a
            :class:`TimeoutError` which is aliased to
            :class:`asyncio.TimeoutError` since Python 3.11.)
    """
    async with asyncio.timeout(seconds):
        yield


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


def _compute_delay(
    attempt: int,
    backoff: BackoffStrategy,
    base_delay: float,
    max_delay: float,
) -> float:
    """Compute the sleep delay before retry ``attempt + 1``.

    ``attempt`` is 1-based and refers to the attempt that just failed.
    """
    delay: float
    if backoff == "exponential":
        delay = base_delay * float(2 ** (attempt - 1))
    elif backoff == "linear":
        delay = base_delay * attempt
    else:  # fixed
        delay = base_delay
    return min(delay, max_delay)


async def retry[T](
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    backoff: BackoffStrategy = "exponential",
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Run ``func`` up to ``attempts`` times, retrying transient failures.

    Args:
        func: Zero-arg coroutine factory. Called fresh for every attempt.
        attempts: Total number of attempts, including the initial call.
            Must be >= 1.
        backoff: Backoff strategy between retries.
        base_delay: Base delay in seconds.
        max_delay: Cap on per-retry delay in seconds.
        retry_on: Tuple of exception types that are considered retryable.
            Anything else propagates immediately.
        on_retry: Optional callback invoked as
            ``on_retry(attempt_number_that_failed, exception)`` *before*
            the sleep that precedes the next attempt. Useful for logging.

    Raises:
        ValueError: If ``attempts < 1``.
        CircuitBreakerOpenError: Never retried, propagated immediately
            even if listed in ``retry_on``.
        Exception: The last raised exception once attempts are exhausted.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except CircuitBreakerOpenError:
            # Per Constitution P1: never retry on an open breaker — that's
            # the whole point of the breaker. Propagate immediately.
            raise
        except retry_on as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            if on_retry is not None:
                on_retry(attempt, exc)
            await asyncio.sleep(_compute_delay(attempt, backoff, base_delay, max_delay))

    # Unreachable: the loop either returns, re-raises, or completes the
    # final attempt with ``raise``. Kept for type-checker happiness.
    assert last_exc is not None  # pragma: no cover
    raise last_exc  # pragma: no cover


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Indirection point for tests that need to fake the clock."""
    return datetime.now(UTC)


@asynccontextmanager
async def circuit_breaker(
    name: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    store: CircuitBreakerStore | None = None,
) -> AsyncIterator[None]:
    """Guard an ``async with`` block with a named circuit breaker.

    State machine:
        * ``closed`` — calls pass through. Each failure increments
          ``consecutive_failures``. Once it reaches ``failure_threshold``
          the breaker transitions to ``open``.
        * ``open`` — calls are short-circuited with
          :class:`CircuitBreakerOpenError`. After ``recovery_timeout``
          seconds elapse, the next call is allowed through and the
          breaker enters ``half_open``.
        * ``half_open`` — exactly one probe is in flight. Success →
          ``closed`` (and ``consecutive_failures`` resets to 0). Failure
          → ``open`` (timer reset).

    Args:
        name: Unique breaker identifier — typically the provider name
            (e.g. ``"spotify"``, ``"google_oauth"``).
        failure_threshold: Consecutive failures that trip the breaker.
        recovery_timeout: Seconds the breaker stays open before the next
            probe is allowed.
        store: Optional override of the process-wide default store.

    Raises:
        CircuitBreakerOpenError: When the breaker is open and the
            recovery timeout has not yet elapsed.
    """
    backend = store if store is not None else _default_store

    state = await backend.get_state(name)

    if state.state == "open":
        elapsed = (_now() - state.opened_at).total_seconds() if state.opened_at is not None else 0.0
        if elapsed < recovery_timeout:
            raise CircuitBreakerOpenError(name)
        # Recovery elapsed → transition to half-open for this probe.
        state.state = "half_open"
        await backend.set_state(name, state)

    try:
        yield
    except CircuitBreakerOpenError:
        # A nested breaker raised — don't count it against this breaker.
        raise
    except Exception:
        failed = await backend.get_state(name)
        if failed.state == "half_open":
            # Probe failed → re-open with timer reset.
            failed.state = "open"
            failed.opened_at = _now()
            # consecutive_failures stays as-is; the open->half_open->open
            # cycle is governed by the timer, not the counter.
        else:
            failed.consecutive_failures += 1
            if failed.consecutive_failures >= failure_threshold:
                failed.state = "open"
                failed.opened_at = _now()
        await backend.set_state(name, failed)
        raise
    else:
        succeeded = await backend.get_state(name)
        if succeeded.state == "half_open":
            succeeded.state = "closed"
            succeeded.consecutive_failures = 0
            succeeded.opened_at = None
            await backend.set_state(name, succeeded)
        elif succeeded.consecutive_failures != 0:
            succeeded.consecutive_failures = 0
            await backend.set_state(name, succeeded)


def circuit_breaker_decorator[T](
    name: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    store: CircuitBreakerStore | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator form of :func:`circuit_breaker`.

    Example::

        @circuit_breaker_decorator("spotify")
        async def list_playlists(user_id: str) -> list[Playlist]:
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with circuit_breaker(
                name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                store=store,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Composed convenience
# ---------------------------------------------------------------------------


async def call_with_resilience[T](
    name: str,
    func: Callable[[], Awaitable[T]],
    *,
    cb_failure_threshold: int = 5,
    cb_recovery_timeout: float = 30.0,
    retry_attempts: int = 3,
    retry_backoff: BackoffStrategy = "exponential",
    retry_base_delay: float = 0.5,
    retry_max_delay: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    timeout_seconds: float = 10.0,
    store: CircuitBreakerStore | None = None,
) -> T:
    """Apply ``circuit_breaker → retry → timeout`` around ``func``.

    This is the canonical helper that feature code should use for any
    outbound provider call (Constitution P1). The composition order is
    fixed: the circuit breaker is the outermost layer (so retries don't
    waste budget against an open breaker), retry is the middle layer
    (so each individual call attempt gets its own timeout), and the
    timeout is the innermost layer (applied per attempt).
    """

    async def _attempt() -> T:
        async with timeout(timeout_seconds):
            return await func()

    async with circuit_breaker(
        name,
        failure_threshold=cb_failure_threshold,
        recovery_timeout=cb_recovery_timeout,
        store=store,
    ):
        return await retry(
            _attempt,
            attempts=retry_attempts,
            backoff=retry_backoff,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
            retry_on=retry_on,
        )


__all__ = [
    "BackoffStrategy",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "CircuitBreakerStore",
    "CircuitState",
    "InMemoryCircuitBreakerStore",
    "call_with_resilience",
    "circuit_breaker",
    "circuit_breaker_decorator",
    "get_default_store",
    "retry",
    "set_default_store",
    "timeout",
]
