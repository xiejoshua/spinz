"""Unit + integration tests for :mod:`auxd_api.lib.otel` and lifespan wiring.

See :doc:`/features/001-auxd-mvp/plan.md` §15.4 and Constitution P5.

Test isolation is non-trivial because OTel state is *global* (the
``opentelemetry.trace`` module holds a process-wide tracer provider) and
the FastAPI instrumentor mutates ``app`` in place. The
``_reset_otel_state`` autouse fixture wipes all of this between tests:

  * resets ``auxd_api.lib.otel._initialized``
  * resets ``trace._TRACER_PROVIDER_SET_ONCE`` and ``trace._TRACER_PROVIDER``
    so a fresh ``set_tracer_provider`` actually takes effect
  * uninstruments FastAPI + httpx so the next ``init_otel`` re-installs
    cleanly without ``AlreadyInstrumentedError``
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.semconv.resource import ResourceAttributes

from auxd_api import main as main_module
from auxd_api import settings as settings_module
from auxd_api.lib import otel as otel_module
from auxd_api.lib.otel import init_otel


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


# CR-001: removed SPOTIFY_* env keys; DISCOGS_API_TOKEN is the new
# (optional) catalog-fallback toggle.
_REQUIRED_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "DISCOGS_API_TOKEN",
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


def _reset_global_tracer_provider() -> None:
    """Reset the global tracer provider so a fresh ``set_tracer_provider`` works.

    ``opentelemetry.trace.set_tracer_provider`` is guarded by a
    once-set flag; the SDK warns and silently keeps the old provider on
    subsequent calls. We poke at the (documented-as-private) internals
    here because there is no public reset API and these tests *must*
    leave global state clean for the rest of the suite.
    """
    # Both attributes are part of the OTel SDK's `trace` module since
    # 1.x; if their names ever change the failure will be loud (AttributeError)
    # rather than silent — which is what we want.
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None
    trace._PROXY_TRACER_PROVIDER = trace.ProxyTracerProvider()


def _uninstrument_all() -> None:
    """Drop FastAPI + httpx instrumentation so the next init reinstalls cleanly.

    ``FastAPIInstrumentor.instrument_app`` marks the *app instance* (not the
    instrumentor singleton) as already-instrumented via the attribute
    ``_is_instrumented_by_opentelemetry`` and rewrites the app's middleware
    stack so it closes over the *current* tracer. We therefore have to call
    :py:meth:`FastAPIInstrumentor.uninstrument_app` on the cached
    ``auxd_api.main.app`` between tests — otherwise the next ``init_otel``
    silently no-ops on the FastAPI side and spans go nowhere.
    """
    # auxd_api.main.app is cached at first import; uninstrument it so the
    # next lifespan-driven init_otel reinstalls fresh.
    try:
        from auxd_api.main import app as main_app  # noqa: PLC0415

        if getattr(main_app, "_is_instrumented_by_opentelemetry", False):
            FastAPIInstrumentor.uninstrument_app(main_app)
    except Exception:  # pragma: no cover — defensive; never block the suite
        pass

    fastapi_instr = FastAPIInstrumentor()
    if fastapi_instr.is_instrumented_by_opentelemetry:
        fastapi_instr.uninstrument()
    httpx_instr = HTTPXClientInstrumentor()
    if httpx_instr.is_instrumented_by_opentelemetry:
        httpx_instr.uninstrument()


@pytest.fixture(autouse=True)
def _reset_otel_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """Per-test reset of OTel + settings + env so each test starts clean."""
    # Env hygiene — mirror the discipline in tests/unit/test_settings.py so
    # Settings() construction is deterministic regardless of CI runner env.
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    # CR-001: removed SPOTIFY_INTEGRATION_ENABLED=false bootstrap.
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()

    # OTel module-level + global state reset.
    otel_module._initialized = False
    _uninstrument_all()
    _reset_global_tracer_provider()

    # Bypass the real DB + Redis connects during lifespan — these tests
    # exercise the OTel side of init only. The conftest-level mongomock
    # fixture handles any Document instantiation; the lifespan's
    # init_db()/init_redis() calls are replaced with no-ops so we never
    # reach localhost:27017 or localhost:6379.
    async def _noop_async(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(main_module, "init_db", _noop_async)
    monkeypatch.setattr(main_module, "close_db", _noop_async)
    monkeypatch.setattr(main_module, "init_redis", _noop_async)
    monkeypatch.setattr(main_module, "close_redis", _noop_async)
    monkeypatch.setattr(main_module, "init_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "close_arq_pool", _noop_async)

    yield

    settings_module.get_settings.cache_clear()
    otel_module._initialized = False
    _uninstrument_all()
    _reset_global_tracer_provider()


# ---------------------------------------------------------------------------
# init_otel — unit behaviour
# ---------------------------------------------------------------------------


class TestInitOtel:
    def test_init_otel_returns_true_on_first_call(self) -> None:
        app = FastAPI()
        assert init_otel(app, environment="local") is True

    def test_init_otel_returns_false_on_second_call(self) -> None:
        app = FastAPI()
        assert init_otel(app, environment="local") is True
        # Second call is a no-op regardless of arg differences (would-be
        # provider/env changes are deliberately ignored).
        assert init_otel(app, environment="production") is False

    def test_init_otel_sets_global_tracer_provider(self) -> None:
        app = FastAPI()
        init_otel(app, environment="local")
        provider = trace.get_tracer_provider()
        # After init the global provider must be the SDK TracerProvider,
        # not the default ProxyTracerProvider.
        assert isinstance(provider, TracerProvider)

    def test_init_otel_resource_attributes(self) -> None:
        app = FastAPI()
        init_otel(app, environment="staging", service_name="auxd-api")
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        attrs = provider.resource.attributes
        assert attrs[ResourceAttributes.SERVICE_NAME] == "auxd-api"
        assert attrs[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] == "staging"

    def test_init_otel_instruments_fastapi_and_httpx(self) -> None:
        app = FastAPI()
        init_otel(app, environment="local")
        # FastAPIInstrumentor marks the *app instance* (not the singleton).
        assert getattr(app, "_is_instrumented_by_opentelemetry", False) is True
        # HTTPXClientInstrumentor uses the singleton-level flag.
        assert HTTPXClientInstrumentor().is_instrumented_by_opentelemetry

    def test_init_otel_default_service_name(self) -> None:
        app = FastAPI()
        init_otel(app, environment="local")
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        assert provider.resource.attributes[ResourceAttributes.SERVICE_NAME] == "auxd-api"


# ---------------------------------------------------------------------------
# End-to-end: a request through the real app produces a span with http.route
# ---------------------------------------------------------------------------


def test_healthz_request_creates_span_with_http_route() -> None:
    """A request to /healthz on the real app produces a span with http.route.

    Mirrors the Done criterion from tasks.md T015a verbatim: "a request
    hitting /healthz produces a structured span in Fly logs containing
    trace_id, span_id, and http.route".
    """
    # Import inside the test so the autouse fixture's env setup is already
    # applied before ``auxd_api.main`` (and therefore ``get_settings``) loads.
    from auxd_api.main import app  # noqa: PLC0415

    # The way we drive this: let init_otel (called from the lifespan) install
    # the SDK provider, then add our in-memory exporter as a second
    # SimpleSpanProcessor on the same provider so we capture everything the
    # FastAPI instrumentor emits.
    exporter = InMemorySpanExporter()

    with TestClient(app) as client:
        # Lifespan has now fired and init_otel installed the SDK provider.
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), (
            f"expected SDK TracerProvider after lifespan, got {type(provider).__name__}"
        )
        # Attach the in-memory exporter so we can read finished spans.
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        response = client.get("/healthz")
        # The OTel test only cares that a request lands on /healthz and
        # produces a span. The body's ``status`` field is exercised by
        # tests/test_healthz.py — here the data layer is no-op'd so it
        # would report ``degraded``.
        assert response.status_code == 200
        assert "status" in response.json()

    # Force-flush any pending spans to the exporter before assertions.
    provider.force_flush()
    spans = exporter.get_finished_spans()

    healthz_spans = [
        s for s in spans if s.attributes and s.attributes.get("http.route") == "/healthz"
    ]
    assert healthz_spans, (
        f"expected at least one span with http.route=/healthz; got "
        f"{[(s.name, dict(s.attributes or {})) for s in spans]}"
    )
    span = healthz_spans[0]
    # The Done criterion: trace_id, span_id, http.route all present.
    assert span.context is not None
    assert span.context.trace_id != 0
    assert span.context.span_id != 0
    assert span.attributes is not None
    assert span.attributes.get("http.route") == "/healthz"


# ---------------------------------------------------------------------------
# Lifespan integration: TestClient context-manager triggers provider install
# ---------------------------------------------------------------------------


def test_lifespan_initialises_tracer_provider() -> None:
    """Entering the FastAPI lifespan installs the SDK TracerProvider."""
    from auxd_api.main import app  # noqa: PLC0415  # local import to honour env-reset fixture

    # Before TestClient context: no SDK provider yet (autouse fixture reset it).
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)

    with TestClient(app):
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), (
            "FastAPI lifespan must initialise the SDK TracerProvider via init_otel"
        )
        assert otel_module._initialized is True
