"""FastAPI app entry point.

Wires the global observability stack (Sentry + OpenTelemetry) via the
ASGI lifespan event so external dependencies are configured exactly once
per process and before any request is served. See plan §15.4 and
Constitution P5 for the FAIL-LOUD discipline applied at init.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from auxd_api import __version__
from auxd_api.lib.observability import init_sentry
from auxd_api.lib.otel import init_otel
from auxd_api.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise Sentry + OpenTelemetry on app startup.

    Both calls are idempotent — safe under repeated lifespan entry
    (e.g. multiple :class:`TestClient` constructions in the same
    process). Failures in either init path propagate (P5: fail-loud).
    """
    settings = get_settings()
    init_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT.value,
        release=__version__,
    )
    init_otel(app, environment=settings.ENVIRONMENT.value)
    yield


app = FastAPI(
    title="auxd API",
    version=__version__,
    description="auxd backend — social album-tracking platform.",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
