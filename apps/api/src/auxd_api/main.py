"""FastAPI app entry point (T011).

Wires the global runtime stack — JSON root logging, MongoDB + Redis
clients, Sentry + OpenTelemetry — via the ASGI lifespan so external
dependencies are configured exactly once per process and before any
request is served. Constitution P5 (fail-loud) governs init order:
the most disruptive failure surface (the data layer) runs first so the
container crashes before observability is wired rather than coming up
serving requests against a broken DB.

The application root exposes ``/healthz`` for liveness probes
(``{status, db, redis, version}``); the feature surface is mounted at
``/api/v1`` from :mod:`auxd_api.routers.v1` and grows as feature
modules land (T031+). The OpenAPI document at ``/openapi.json`` reflects
the versioned namespace and is consumed by the T028 codegen pipeline.
"""

from __future__ import annotations

# Make Python's SSL stack use the OS's native trust store (macOS
# keychain / Windows cert store / Linux system bundle) instead of the
# bundled certifi roots. Required on corporate networks that do TLS
# inspection (e.g. Zscaler) where the intercepting proxy re-signs
# upstream certs with a CA that ships only in the OS trust store, never
# in certifi. MUST run before any HTTPS client (httpx, requests, sentry)
# is constructed — hence the early-import position above the rest.
import truststore

truststore.inject_into_ssl()

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auxd_api import __version__
from auxd_api.db import close_db, get_database, init_db, ping_db
from auxd_api.lib.logging import configure_logging
from auxd_api.lib.observability import init_sentry
from auxd_api.lib.otel import init_otel
from auxd_api.middleware import SessionMiddleware
from auxd_api.migrations import run_migrations
from auxd_api.modules.mb_mirror.client import TursoClient
from auxd_api.redis_client import (
    JobEnqueueUnavailable,
    close_arq_pool,
    close_redis,
    init_arq_pool,
    init_redis,
    ping_redis,
)
from auxd_api.routers.v1 import router as v1_router
from auxd_api.settings import emit_startup_audit, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise data stores, then observability, on app startup.

    Order is deliberate: MongoDB → Redis → Sentry → OpenTelemetry. Each
    step's failure surface decreases — a broken DB should crash the
    process before logs are wired so the operator sees the connection
    error immediately rather than chasing a "healthy" container that
    serves 5xx on every route.
    """
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL.value)
    emit_startup_audit(settings, logging.getLogger("auxd.startup"))

    await init_db(settings.MONGODB_URI)
    # Run any lazy schema migrations (T030, Constitution P2). MUST run
    # AFTER ``init_db`` (Beanie needs to be wired so models can be
    # queried) and BEFORE ``init_redis`` so that the data layer is
    # consistent before any background-worker enqueue or HTTP traffic
    # touches it. Failures propagate — fail-loud is the only safe stance.
    await run_migrations(get_database(settings.MONGODB_URI))
    await init_redis(settings.REDIS_URL)
    await init_arq_pool(settings.REDIS_URL)

    # MusicBrainz mirror — read-only Turso/libSQL cache of ~1.3M
    # release-groups. Optional: when ``TURSO_DATABASE_URL`` is unset
    # the constructor returns ``None`` and downstream consumers
    # (``resolve_identity``, ``search_albums``, ``filter_only_search``)
    # silently fall through to Atlas + Discogs + MB API as they did
    # pre-mirror. When configured, the client owns its own httpx
    # connection pool for the lifetime of the process; we open it once
    # here at lifespan boot rather than per-request so the connection
    # pool, SSL handshake, and any keep-alive savings amortize across
    # every request. Stored on ``app.state.mirror_client`` so the
    # dependency in :mod:`auxd_api.dependencies` can hand the same
    # instance to every route. Closed on shutdown.
    app.state.mirror_client = TursoClient.from_settings(settings)
    if app.state.mirror_client is not None:
        await app.state.mirror_client.__aenter__()

    init_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT.value,
        release=__version__,
    )
    init_otel(app, environment=settings.ENVIRONMENT.value)
    try:
        yield
    finally:
        if app.state.mirror_client is not None:
            await app.state.mirror_client.aclose()
        await close_arq_pool()
        await close_redis()
        await close_db()


app = FastAPI(
    title="auxd API",
    version=__version__,
    description="auxd backend — social album-tracking platform.",
    lifespan=lifespan,
)
# CORS allow-list — read directly from `os.environ` (not via `get_settings()`)
# because middleware is registered at module-import time, BEFORE any pytest
# fixture has a chance to set SESSION_HMAC_KEY + TOKEN_ENCRYPTION_KEY. Going
# through Settings here would force test collection to require the entire
# secret env, which broke CI (locally a .env file masks the issue).
#
# With the Next.js rewrites pattern in production, the browser actually calls
# xiejoshua.com/api/v1/* (same-origin), so the API rarely sees a real
# cross-origin request — CORS stays as defense for direct API access (curl,
# OG fetchers, future native clients) and dev (localhost:3000 → :8000).
_ALLOWED_ORIGINS_RAW = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
_ALLOWED_ORIGINS = [origin.strip() for origin in _ALLOWED_ORIGINS_RAW.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Requested-With", "X-CSRF-Token"],
)
# Session middleware must wrap every route, including future /api/v1/auth
# endpoints, so register it before the router include.
app.add_middleware(SessionMiddleware)
app.include_router(v1_router)


@app.exception_handler(JobEnqueueUnavailable)
async def _handle_job_enqueue_unavailable(
    _request: Request, exc: JobEnqueueUnavailable
) -> JSONResponse:
    """Convert :class:`JobEnqueueUnavailable` into ``HTTP 503``.

    The Sentry alert (tag ``jobs.redis_down``) is already emitted inside
    :func:`auxd_api.redis_client.enqueue_job` before the exception
    propagates, so this handler is purely responsible for the response
    shape. Sync-fix L4-004 + pre-impl-review C-5 lock this contract.
    """
    return JSONResponse(
        status_code=503,
        content={
            "error": "job_queue_unavailable",
            "detail": str(exc),
        },
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe with per-dependency sub-checks.

    Returns HTTP 200 unconditionally — Fly uses the status code as a
    process-up signal, and a degraded data layer should not flap the
    container restart loop. Callers inspect the body to distinguish
    healthy from degraded states:

    * ``status``: ``"ok"`` only when every sub-check is ``"ok"``;
      ``"degraded"`` otherwise.
    * ``db`` / ``redis``: ``"ok"`` or ``"down"`` per the corresponding
      ``ping_*`` helper.
    * ``version``: package version, useful for confirming a deploy.
    """
    db_status = await ping_db()
    redis_status = await ping_redis()
    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "redis": redis_status,
        "version": __version__,
    }
