"""Redis-backed sliding-window rate limiter (T020).

Built as a FastAPI dependency factory so each endpoint pins its own
``(per_ip, per_user)`` budget without the boilerplate of a custom
middleware per-route::

    @router.post(
        "/auth/login",
        dependencies=[
            Depends(
                rate_limit(
                    endpoint="auth.login",
                    per_ip=RateLimit(limit=10, window_seconds=60),
                )
            ),
        ],
    )
    async def login(...): ...

Algorithm
=========
Per ``(endpoint, dimension, identifier)`` triple, the limiter maintains
a Redis sorted set keyed by request timestamps. On each call the
limiter:

1. Trims entries older than ``window_seconds`` via ``ZREMRANGEBYSCORE``.
2. Counts the surviving entries with ``ZCARD``.
3. If the count is below the limit, ``ZADD``s a fresh timestamp and
   ``EXPIRE``s the key to ``window_seconds`` so unused keys self-GC.
4. If the count is at-or-above the limit, raises
   :class:`fastapi.HTTPException` with status 429.

Fail mode
=========
**FAIL OPEN** on any :class:`redis.exceptions.RedisError`:

* The request is allowed through.
* A Sentry warning tagged ``rate_limit.redis_down`` is emitted.

Locked in pre-impl-review C-5 and sync-fix L4-004. The rationale is
that the limiter is defensive (Spotify enforces upstream limits at the
edge) — a Redis blip should never block legitimate traffic.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

import sentry_sdk
from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from auxd_api import redis_client as redis_module
from auxd_api.lib.sessions import Session

_LOGGER = logging.getLogger("auxd.ratelimit")

_KEY_PREFIX: Final[str] = "ratelimit"


@dataclass(frozen=True, slots=True)
class RateLimit:
    """A budget expressed as a count over a rolling time window."""

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("RateLimit.limit must be positive")
        if self.window_seconds <= 0:
            raise ValueError("RateLimit.window_seconds must be positive")


def _alert_rate_limit_down(operation: str, exc: BaseException) -> None:
    """Emit a Sentry warning tagged ``rate_limit.redis_down``.

    Pair with the fail-open path so operators can correlate sudden
    traffic spikes with a brief Redis outage. The tag string is
    stable so alerting rules can be built on top.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "rate_limit")
        scope.set_tag("status", "redis_down")
        scope.set_extra("operation", operation)
        scope.set_extra("error", str(exc))
        sentry_sdk.capture_message("rate_limit.redis_down", level="warning")


def _client_ip(request: Request) -> str:
    """Return the best-effort client IP.

    Prefers the first ``X-Forwarded-For`` hop when Fly is in front of
    us (Starlette already trusts it because we pass
    ``--proxy-headers`` to uvicorn). Falls back to ``request.client.host``
    and finally to a stable sentinel so the rate-limiter key shape stays
    well-formed even when the source IP cannot be determined.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _bucket_key(endpoint: str, dimension: str, identifier: str) -> str:
    return f"{_KEY_PREFIX}:{endpoint}:{dimension}:{identifier}"


async def _check_and_record(
    *,
    bucket_key: str,
    limit: RateLimit,
    now_ms: int | None = None,
) -> bool:
    """Return ``True`` when the request is allowed, ``False`` when it is over budget.

    On Redis failure, returns ``True`` (fail open) and emits a Sentry
    alert. Never raises — the caller can treat failures and successes
    uniformly.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    cutoff_ms = now_ms - limit.window_seconds * 1000
    try:
        client = redis_module.get_redis()
    except RuntimeError:
        # No Redis configured (e.g., unit tests without lifespan). Treat
        # as a fail-open scenario but skip the Sentry alert — this is a
        # programming setup state, not a runtime degradation.
        return True
    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(bucket_key, 0, cutoff_ms)
        pipe.zcard(bucket_key)
        results = await pipe.execute()
        current_count = int(results[-1])
        if current_count >= limit.limit:
            return False
        # Record this hit. Use the timestamp as both score and member so
        # the same instant only counts once per bucket-key.
        await client.zadd(bucket_key, {str(now_ms): now_ms})
        await client.expire(bucket_key, limit.window_seconds)
    except RedisError as exc:
        _alert_rate_limit_down(operation=f"check:{bucket_key}", exc=exc)
        return True
    return True


def rate_limit(
    *,
    endpoint: str,
    per_ip: RateLimit | None = None,
    per_user: RateLimit | None = None,
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI dependency enforcing the given per-IP / per-user limits.

    Either ``per_ip`` or ``per_user`` (or both) must be provided. The IP
    limit applies to every caller; the user limit only applies when the
    request carries a valid session (set by :class:`SessionMiddleware`).
    """
    if per_ip is None and per_user is None:
        raise ValueError("rate_limit requires at least one of per_ip or per_user")

    async def _dependency(request: Request) -> None:
        # IP dimension — every request has an IP, so always evaluated when configured.
        if per_ip is not None:
            ip = _client_ip(request)
            allowed = await _check_and_record(
                bucket_key=_bucket_key(endpoint, "ip", ip),
                limit=per_ip,
            )
            if not allowed:
                _LOGGER.info(
                    "ratelimit.exceeded",
                    extra={
                        "event": "ratelimit.exceeded",
                        "dimension": "ip",
                        "endpoint": endpoint,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate limit exceeded",
                )

        # User dimension — only evaluated when the request is authenticated.
        if per_user is not None:
            session: Session | None = getattr(request.state, "session", None)
            if session is not None:
                allowed = await _check_and_record(
                    bucket_key=_bucket_key(endpoint, "user", session.user_id),
                    limit=per_user,
                )
                if not allowed:
                    _LOGGER.info(
                        "ratelimit.exceeded",
                        extra={
                            "event": "ratelimit.exceeded",
                            "dimension": "user",
                            "endpoint": endpoint,
                        },
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="rate limit exceeded",
                    )

    return _dependency


__all__ = [
    "RateLimit",
    "rate_limit",
]
