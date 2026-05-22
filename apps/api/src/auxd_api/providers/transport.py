"""Resilience-wrapped httpx transport — T050 + T051.

:class:`ResilienceTransport` is the single httpx ``AsyncBaseTransport``
implementation used by every provider client in the auxd backend. It
wraps each outbound request with the canonical composition from
:mod:`auxd_api.lib.resilience` (circuit breaker → retry → timeout —
Constitution P1) and emits exactly one
:func:`auxd_api.lib.observability.log_call` per request (Constitution P5).

HTTP-status → exception mapping (T052 taxonomy):

* connection error / 5xx after retries → :class:`ProviderUnavailable`
* ``HTTP 429``                          → :class:`ProviderRateLimited` (no retry)
* ``CircuitBreakerOpenError``           → :class:`ProviderUnavailable`
* ``asyncio.TimeoutError``              → :class:`ProviderUnavailable`
* 2xx / 3xx / 4xx (non-429)             → flow through unchanged

Status field surfaced in ``log_call``:

* clean response → integer HTTP code (``200``, ``404``, ``429`` …)
* timeout        → ``"timeout"``
* circuit open   → ``"circuit_open"``
* other failure  → ``"failed"``

Design choice: the transport is **stateless w.r.t. rate limiting**. The
MusicBrainz 1-req/sec policy is enforced inside
:class:`~auxd_api.providers.musicbrainz.MusicBrainzCatalogProvider` via an
async semaphore + lock pair rather than coupling rate-limit policy into
the transport layer. The transport is responsible for resilience +
observability; pacing is the provider's concern.
"""

from __future__ import annotations

import time

import httpx

from auxd_api.lib.observability import log_call
from auxd_api.lib.resilience import (
    BackoffStrategy,
    CircuitBreakerOpenError,
    call_with_resilience,
)
from auxd_api.providers.errors import (
    ProviderRateLimited,
    ProviderUnavailable,
)


class _Retryable429(Exception):
    """Internal sentinel — bubbles a 429 out of the inner attempt.

    We deliberately do *not* retry on 429 (Constitution P1 retry semantics:
    429 is "back off", not "transient"). The sentinel is mapped to
    :class:`ProviderRateLimited` immediately after the resilience stack
    exits, never re-entering retry.
    """

    def __init__(self, response: httpx.Response) -> None:
        super().__init__("429 from upstream")
        self.response = response


class _Retryable5xx(Exception):
    """Internal sentinel — bubbles a 5xx out of the inner attempt for retry."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"{response.status_code} from upstream")
        self.response = response
        self.status_code = response.status_code


class ResilienceTransport(httpx.AsyncBaseTransport):
    """``httpx.AsyncBaseTransport`` that applies resilience + observability.

    Wraps an inner ``AsyncHTTPTransport`` (or any caller-supplied transport
    for tests/mocking). Every request flows through
    :func:`call_with_resilience` so the circuit-breaker + retry + timeout
    primitives apply uniformly across all providers.

    Args:
        provider_name: Short stable name surfaced in ``log_call`` and as
            the ``provider`` field on raised :class:`ProviderError`s
            (e.g. ``"musicbrainz"``).
        circuit_breaker_name: Name of the breaker to use. Usually the same
            as ``provider_name``; exposed separately because some providers
            may want a finer-grained breaker (one per host, one per
            endpoint family). Defaults to ``provider_name``.
        retry_attempts: Total attempts including the initial call. Default
            3 mirrors the resilience module default.
        retry_backoff: Backoff strategy for retries.
        retry_base_delay: Base delay in seconds for backoff.
        timeout_seconds: Per-attempt wall-clock timeout.
        inner_transport: Optional override of the underlying transport.
            Tests pass an ``httpx.MockTransport`` here; production code
            lets the default ``httpx.AsyncHTTPTransport`` handle real I/O.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        circuit_breaker_name: str | None = None,
        retry_attempts: int = 3,
        retry_backoff: BackoffStrategy = "exponential",
        retry_base_delay: float = 0.5,
        timeout_seconds: float = 10.0,
        inner_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._cb_name = circuit_breaker_name or provider_name
        self._retry_attempts = retry_attempts
        self._retry_backoff: BackoffStrategy = retry_backoff
        self._retry_base_delay = retry_base_delay
        self._timeout_seconds = timeout_seconds
        self._inner: httpx.AsyncBaseTransport = (
            inner_transport if inner_transport is not None else httpx.AsyncHTTPTransport()
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Resilience- + observability-wrapped request handler.

        The flow per call:

        1. Start a wall-clock timer for the ``log_call`` latency field.
        2. Invoke :func:`call_with_resilience` with the inner transport
           call as the work item. The composed stack handles
           timeout-per-attempt + retry + breaker.
        3. Translate non-200 outcomes to T052 exceptions:

           * 429 → :class:`ProviderRateLimited` (no retry; one attempt)
           * 5xx after retries → :class:`ProviderUnavailable`
           * Timeout / connection failure → :class:`ProviderUnavailable`
           * Circuit open → :class:`ProviderUnavailable`

        4. Emit exactly one :func:`log_call` line — even on failure — with
           the appropriate status sentinel.
        """
        start = time.perf_counter()
        endpoint = request.url.path or "/"
        request_id = self._extract_request_id(request)

        response: httpx.Response | None = None
        status_for_log: int | str = "failed"
        try:
            response = await self._call_with_resilience(request)
            status_for_log = response.status_code
            return response
        except _Retryable429 as exc:
            status_for_log = 429
            raise ProviderRateLimited(
                f"{self._provider_name} returned 429",
                provider=self._provider_name,
            ) from exc
        except _Retryable5xx as exc:
            status_for_log = exc.status_code
            raise ProviderUnavailable(
                f"{self._provider_name} returned {exc.status_code} after retries",
                provider=self._provider_name,
            ) from exc
        except CircuitBreakerOpenError as exc:
            status_for_log = "circuit_open"
            raise ProviderUnavailable(
                f"{self._provider_name} circuit breaker open",
                provider=self._provider_name,
            ) from exc
        except TimeoutError as exc:
            # asyncio.TimeoutError is aliased to the builtin TimeoutError since
            # Python 3.11, so a single ``except TimeoutError`` covers both.
            status_for_log = "timeout"
            raise ProviderUnavailable(
                f"{self._provider_name} request timed out",
                provider=self._provider_name,
            ) from exc
        except httpx.HTTPError as exc:
            status_for_log = "failed"
            raise ProviderUnavailable(
                f"{self._provider_name} request failed: {exc}",
                provider=self._provider_name,
            ) from exc
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_call(
                provider=self._provider_name,
                endpoint=endpoint,
                latency_ms=latency_ms,
                status=status_for_log,
                request_id=request_id,
            )

    async def _call_with_resilience(self, request: httpx.Request) -> httpx.Response:
        """Run the inner request through the composed resilience stack."""

        async def _attempt() -> httpx.Response:
            response = await self._inner.handle_async_request(request)
            # 429 must NOT retry — surface immediately via the dedicated
            # sentinel so the retry layer doesn't catch + re-attempt.
            if response.status_code == 429:
                raise _Retryable429(response)
            if 500 <= response.status_code < 600:
                raise _Retryable5xx(response)
            return response

        return await call_with_resilience(
            self._cb_name,
            _attempt,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
            retry_base_delay=self._retry_base_delay,
            timeout_seconds=self._timeout_seconds,
            # Only retry on 5xx + httpx network errors. Explicitly exclude
            # _Retryable429 so the rate-limit signal short-circuits to the
            # outer handler on the very first attempt.
            retry_on=(_Retryable5xx, httpx.HTTPError),
        )

    @staticmethod
    def _extract_request_id(request: httpx.Request) -> str | None:
        """Pull the inbound request id off the outgoing request, if present.

        Provider clients that want to propagate the auxd correlation id can
        set the ``X-Request-Id`` header on the outgoing request; we mirror
        it into the ``log_call`` ``request_id`` field for cross-system
        tracing.
        """
        value = request.headers.get("x-request-id")
        return value if value else None


# Re-export helpers used by callers building provider clients. Keeping
# them here lets each provider import a single module rather than
# touching the resilience internals.
__all__ = [
    "ResilienceTransport",
]


# ---------------------------------------------------------------------------
# Convenience: a builder used by provider clients to compose a fully
# wired ``httpx.AsyncClient`` in one place.
# ---------------------------------------------------------------------------


def build_async_client(
    *,
    base_url: str,
    provider_name: str,
    user_agent: str,
    timeout_seconds: float = 10.0,
    retry_attempts: int = 3,
    extra_headers: dict[str, str] | None = None,
    inner_transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Construct an ``httpx.AsyncClient`` wired with a :class:`ResilienceTransport`.

    Used by every provider client (MusicBrainz, Discogs) so each provider
    inherits a uniform resilience + observability posture without copying
    boilerplate. ``inner_transport`` is the seam tests use to inject an
    ``httpx.MockTransport``.
    """
    headers: dict[str, str] = {"User-Agent": user_agent}
    if extra_headers:
        headers.update(extra_headers)
    transport = ResilienceTransport(
        provider_name=provider_name,
        circuit_breaker_name=provider_name,
        retry_attempts=retry_attempts,
        timeout_seconds=timeout_seconds,
        inner_transport=inner_transport,
    )
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        transport=transport,
        timeout=httpx.Timeout(timeout_seconds),
    )


# ``build_async_client`` is intentionally module-private import-wise (not
# in ``__all__``) so users who explicitly want resilience plumbing reach
# for it via fully-qualified name. The signature is publicly stable.
