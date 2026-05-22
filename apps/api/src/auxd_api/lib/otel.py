"""OpenTelemetry instrumentation — Constitution P5; plan §15.4.

Provides :func:`init_otel` that:

  1. Configures the global tracer provider with ``service.name=auxd-api``
     and resource attributes including ``deployment.environment``.
  2. Attaches a :class:`ConsoleSpanExporter` (wrapped in
     :class:`BatchSpanProcessor`) — spans go to stdout where Fly captures
     them as structured log records. Per plan §15.4 there is no dedicated
     tracing backend at MVP; Fly logs *are* the tracing backend.
  3. Calls ``FastAPIInstrumentor.instrument_app(app)`` for HTTP request
     spans (containing ``http.route``, ``trace_id``, ``span_id``, etc.).
  4. Calls ``HTTPXClientInstrumentor().instrument()`` for outbound httpx
     spans (covers Spotify/MusicBrainz and any other future provider
     client that uses httpx — which is all of them per plan §6).

MongoDB (Beanie/PyMongo) instrumentation is deferred until T012 wires
Beanie into the app. Adding it later is a one-line
``PymongoInstrumentor().instrument()`` call inside :func:`init_otel`
(the corresponding dep, ``opentelemetry-instrumentation-pymongo``, also
needs to be added to ``pyproject.toml`` at that point). See TODO below.

The function is idempotent — second and subsequent calls are no-ops
guarded by a module-level ``_initialized`` flag. This matters because
the FastAPI lifespan may re-enter in tests (multiple ``TestClient(app)``
constructions) and because operators occasionally reload modules.

FAIL-LOUD discipline (Constitution P5): observability is mandatory, so
init failures are logged via :func:`log_call` *and* re-raised. We never
silently swallow an init error — if traces can't be wired, we'd rather
crash at startup than ship a "looks healthy but is blind" service.
Runtime span emission failures inside instrumented code paths are
handled by the OTel SDK itself (fail-safe — exceptions in exporters
don't break the request path).
"""

from __future__ import annotations

import time
from typing import Final

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes

from auxd_api.lib.observability import log_call

__all__ = ["init_otel"]


_DEFAULT_SERVICE_NAME: Final[str] = "auxd-api"

# Module-level flag guarding idempotency of :func:`init_otel`.
_initialized: bool = False


def init_otel(
    app: FastAPI,
    *,
    environment: str,
    service_name: str = _DEFAULT_SERVICE_NAME,
) -> bool:
    """Initialise the OTel SDK and FastAPI/httpx instrumentors on ``app``.

    Sets a :class:`TracerProvider` with resource attributes
    ``service.name`` and ``deployment.environment``, attaches a
    :class:`ConsoleSpanExporter` via :class:`BatchSpanProcessor`, and
    instruments the FastAPI app + global httpx client.

    Args:
        app: The :class:`FastAPI` application instance to instrument.
        environment: Deployment environment string
            (``"local"``/``"dev"``/``"staging"``/``"production"``) —
            normally the value of ``settings.ENVIRONMENT.value``.
        service_name: Service identifier emitted on every span. Defaults
            to ``"auxd-api"``; exposed as an argument for tests that want
            to verify the resource attribute.

    Returns:
        ``True`` if initialisation happened on this call. ``False`` if
        OTel was already initialised earlier in this process (idempotent
        no-op). Useful for tests + accidental lifespan re-entry.

    Raises:
        Exception: Any error encountered while configuring the tracer
            provider or attaching instrumentors is logged via
            :func:`log_call` and re-raised. Constitution P5 mandates
            fail-loud behaviour on observability init — a silently
            uninstrumented service is worse than a crashed one.
    """
    global _initialized
    if _initialized:
        return False

    start = time.perf_counter()
    try:
        resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: service_name,
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: environment,
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        # FastAPIInstrumentor swaps in a new ``build_middleware_stack`` method
        # but does *not* invalidate any already-built ``middleware_stack``.
        # Starlette/FastAPI builds the stack lazily — and crucially, it builds
        # it *before* the lifespan handler runs. So if we don't force a
        # rebuild here, ``init_otel`` called from the lifespan would mark the
        # app as instrumented yet emit zero spans (the live middleware stack
        # is the pre-instrumentation one). Force the rebuild.
        app.middleware_stack = app.build_middleware_stack()
        HTTPXClientInstrumentor().instrument()
        # TODO(T012): Once Beanie/PyMongo is wired, add the matching dep
        # ``opentelemetry-instrumentation-pymongo`` and a one-line
        # ``PymongoInstrumentor().instrument()`` call here.
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        log_call(
            provider="otel",
            endpoint="init",
            latency_ms=latency_ms,
            status="init_failed",
            extra={"error": str(exc), "environment": environment},
        )
        raise

    _initialized = True
    latency_ms = (time.perf_counter() - start) * 1000.0
    log_call(
        provider="otel",
        endpoint="init",
        latency_ms=latency_ms,
        status="ok",
        extra={"environment": environment, "service_name": service_name},
    )
    return True
