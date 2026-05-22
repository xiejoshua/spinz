"""Process-wide Redis client lifecycle + cache/queue helpers.

T011 owns the connection-management primitives (``init_redis``,
``close_redis``, ``get_redis``, ``ping_redis``). T013 adds:

* The arq enqueue pool (``init_arq_pool``, ``close_arq_pool``,
  ``get_arq_pool``) — a separate connection used by the API process to
  push jobs onto the queue. Workers read from the same Redis via their
  own ``WorkerSettings`` (see :mod:`auxd_api.workers.main`).
* Cache wrappers (``cache_get`` / ``cache_set``) that FAIL OPEN on
  :class:`RedisError` and emit a Sentry warning tagged
  ``cache.redis_down``. Cache is a perf optimisation, never load-bearing.
* The enqueue wrapper (``enqueue_job``) that FAILS LOUD into the request
  path via :class:`JobEnqueueUnavailable` and emits a Sentry warning
  tagged ``jobs.redis_down``. The FastAPI exception handler in
  :mod:`auxd_api.main` converts that into ``HTTP 503``.

Constitution P5 (fail-loud) applies at startup: both pools ping on init.
Runtime use sites pick the right fail mode for the call (cache → open,
job-enqueue → 503) per the policy locked in pre-impl-review C-5 +
sync-fix L4-004.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Final, cast

import sentry_sdk
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

_client: Redis | None = None
_arq_pool: ArqRedis | None = None

OK: Final[str] = "ok"
DOWN: Final[str] = "down"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class JobEnqueueUnavailable(RuntimeError):
    """Raised by :func:`enqueue_job` when Redis is unreachable.

    Surfaced into the request path so the FastAPI exception handler in
    :mod:`auxd_api.main` can convert it into ``HTTP 503``. Tests asserting
    fail-loud behaviour for job-enqueue sites should expect this type.
    """


# ---------------------------------------------------------------------------
# Cache client (T011 → T013)
# ---------------------------------------------------------------------------


async def init_redis(redis_url: str) -> None:
    """Open the process-wide Redis client and verify it with a ping.

    Steps:
        1. Construct the async client from ``redis_url``.
        2. Issue a ``PING`` to fail loudly on a wrong host / closed port.
        3. Stash the client at module scope for :func:`get_redis`.

    Any failure propagates (Constitution P5). The startup ping is the
    only place we treat Redis as required — runtime call sites use the
    T013 fail-open wrappers and treat Redis as best-effort.
    """
    global _client
    client: Redis = Redis.from_url(redis_url, decode_responses=True)
    # ``redis-py`` types ``ping`` as ``Awaitable[bool] | bool`` because the
    # same class is used for sync + async; cast away the union for mypy.
    try:
        await cast(Awaitable[bool], client.ping())
    except RedisError:
        await client.aclose()
        raise
    _client = client


async def close_redis() -> None:
    """Dispose of the Redis client, if any. Idempotent."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> Redis:
    """Return the singleton Redis client, raising if :func:`init_redis` has not run."""
    if _client is None:
        raise RuntimeError("Redis client is not initialised; call init_redis() first.")
    return _client


async def ping_redis() -> str:
    """Return :data:`OK` if Redis is reachable, :data:`DOWN` otherwise.

    Suitable for ``/healthz`` sub-checks: never raises. Returns
    :data:`DOWN` when the module-level client has not been initialised
    (e.g. unit tests that skip the lifespan) or when ``PING`` fails for
    any reason.
    """
    if _client is None:
        return DOWN
    try:
        await cast(Awaitable[bool], _client.ping())
    except RedisError:
        return DOWN
    return OK


# ---------------------------------------------------------------------------
# arq enqueue pool (T013)
# ---------------------------------------------------------------------------


async def init_arq_pool(redis_url: str) -> None:
    """Open the arq enqueue pool used by the API process.

    The pool is distinct from :func:`init_redis`'s cache client because
    arq attaches its own serialization + connection pooling on top of
    plain Redis. The worker process (see ``auxd_api.workers.main``)
    connects with its own ``WorkerSettings`` against the same broker.
    """
    global _arq_pool
    settings = RedisSettings.from_dsn(redis_url)
    _arq_pool = await create_pool(settings)


async def close_arq_pool() -> None:
    """Dispose of the arq pool, if any. Idempotent."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


def get_arq_pool() -> ArqRedis:
    """Return the singleton arq pool, raising if :func:`init_arq_pool` has not run."""
    if _arq_pool is None:
        raise RuntimeError("arq pool is not initialised; call init_arq_pool() first.")
    return _arq_pool


# ---------------------------------------------------------------------------
# Cache wrappers (fail-open) — sync-fix L4-004
# ---------------------------------------------------------------------------


def _alert_cache_down(operation: str, exc: BaseException) -> None:
    """Emit a Sentry warning tagged ``cache.redis_down``.

    A no-op when Sentry is not initialised. The tag string is fixed so
    operators can build an alerting rule on it in Sentry.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "cache")
        scope.set_tag("status", "redis_down")
        scope.set_extra("operation", operation)
        scope.set_extra("error", str(exc))
        sentry_sdk.capture_message("cache.redis_down", level="warning")


async def cache_get(key: str) -> str | None:
    """Read ``key`` from cache. FAIL OPEN on Redis failure.

    Returns the stored string, ``None`` if the key is unset, and also
    ``None`` (with a Sentry alert) if the cache is unreachable. Cache is
    a latency optimisation, never load-bearing.
    """
    if _client is None:
        return None
    try:
        result = await cast(Awaitable[str | None], _client.get(key))
    except RedisError as exc:
        _alert_cache_down(operation=f"get:{key}", exc=exc)
        return None
    return result


async def cache_set(key: str, value: str, *, ex_seconds: int | None = None) -> None:
    """Write ``key → value`` to cache. FAIL OPEN on Redis failure.

    Sentry-alerts on failure but never raises. ``ex_seconds`` sets a TTL
    in seconds (passed through to Redis' ``SET ... EX``).
    """
    if _client is None:
        return
    try:
        await cast(
            Awaitable[bool],
            _client.set(key, value, ex=ex_seconds),
        )
    except RedisError as exc:
        _alert_cache_down(operation=f"set:{key}", exc=exc)


# ---------------------------------------------------------------------------
# Job enqueue wrapper (fail-503) — sync-fix L4-004
# ---------------------------------------------------------------------------


def _alert_jobs_down(job_name: str, exc: BaseException) -> None:
    """Emit a Sentry warning tagged ``jobs.redis_down``.

    Pair with the :class:`JobEnqueueUnavailable` raise: the alert fires
    before the exception leaves the helper so even routes that swallow
    the 503 still produce an alert.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "jobs")
        scope.set_tag("status", "redis_down")
        scope.set_extra("job", job_name)
        scope.set_extra("error", str(exc))
        sentry_sdk.capture_message("jobs.redis_down", level="warning")


async def enqueue_job(name: str, *args: Any, **kwargs: Any) -> Job | None:
    """Push a job onto the arq queue. FAIL LOUD with 503 on Redis failure.

    Raises :class:`JobEnqueueUnavailable` when the broker is unreachable;
    the FastAPI exception handler in :mod:`auxd_api.main` converts that
    into ``HTTP 503``. Also raises :class:`RuntimeError` if
    :func:`init_arq_pool` has not run — that is a programming error
    rather than a runtime failure mode.

    ``*args`` / ``**kwargs`` are forwarded verbatim to
    :meth:`arq.connections.ArqRedis.enqueue_job`, which accepts the
    job's positional + keyword arguments plus a handful of underscore-
    prefixed arq-internal options (``_job_id``, ``_defer_until``,
    ``_defer_by``, ``_expires``, ``_job_try``). Typed as :data:`Any`
    here because the wrapper is a generic pass-through; call sites
    pin the actual types.
    """
    pool = get_arq_pool()
    try:
        return await pool.enqueue_job(name, *args, **kwargs)
    except RedisConnectionError as exc:
        _alert_jobs_down(job_name=name, exc=exc)
        raise JobEnqueueUnavailable(f"arq broker unreachable for job {name!r}") from exc


__all__ = [
    "DOWN",
    "OK",
    "JobEnqueueUnavailable",
    "cache_get",
    "cache_set",
    "close_arq_pool",
    "close_redis",
    "enqueue_job",
    "get_arq_pool",
    "get_redis",
    "init_arq_pool",
    "init_redis",
    "ping_redis",
]
