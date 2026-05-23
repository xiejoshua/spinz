"""Notification coalescer + rate limiter (T133).

Implements the locked-in Phase-5C contract from plan §8.2 +
``notification-taxonomy.md`` anti-spam guardrails. Four guardrails are
enforced per dispatch:

1. **Per-event dedup.** Same ``(type, actor_id, target_id)`` within 1h →
   drop the second event. Backed by a single Redis key with ``SETEX`` and
   1-hour TTL.
2. **Per-user per-type per-hour rate limit.** ≤5 events of one type to
   one recipient inside a rolling 1-hour window. Excess → ``coalesce``.
3. **Per-user per-type per-day rate limit.** ≤25 events of one type to
   one recipient inside a rolling 24-hour window. Excess → ``coalesce``.
4. **Per-actor cross-type 24h limit.** ≤3 events from one actor to one
   recipient inside a rolling 24-hour window, counting ACROSS all types.
   This catches the "X follows you, then likes 5 of your reviews in an
   hour" review-storm scenario (TC-026). Only checked when ``actor_id``
   is supplied.

All three rate-limit buckets share the same Redis-sorted-set sliding
window primitive that :mod:`auxd_api.lib.rate_limit` uses for HTTP
endpoints. Key shapes are documented in the asserts of
``tests/integration/test_coalescer.py``.

Fail-mode (Phase 5C — locked in resolves A-004): if Redis is unreachable
or :func:`get_redis` is uninitialised, the coalescer FAILS OPEN with a
``send`` verdict and emits a Sentry warning tagged
``notif_limiter.redis_down``. The rationale is the one from
notification-taxonomy.md §Anti-spam: notifications missed during a Redis
outage are worse than the brief loss of rate-limiting that an
unbounded-firehose-during-outage produces.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Final, Literal

import sentry_sdk
from redis.exceptions import RedisError

from auxd_api import redis_client as redis_module
from auxd_api.modules.notifications.models import NotificationType

_LOGGER = logging.getLogger("auxd.notifications.coalescer")

# ---------------------------------------------------------------------------
# Bucket constants — windows + limits per the taxonomy + plan §8.2.
# ---------------------------------------------------------------------------

# Per-user per-type per-hour.
HOUR_WINDOW_SECONDS: Final[int] = 3600
HOUR_LIMIT: Final[int] = 5

# Per-user per-type per-day.
DAY_WINDOW_SECONDS: Final[int] = 86400
DAY_LIMIT: Final[int] = 25

# Per-actor cross-type per-day (24h trailing).
ACTOR_24H_WINDOW_SECONDS: Final[int] = 86400
ACTOR_24H_LIMIT: Final[int] = 3

# Per-event dedup window (no rate-limit math — a binary "have we seen this?").
DEDUP_TTL_SECONDS: Final[int] = 3600


# ---------------------------------------------------------------------------
# Decision value object.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoalesceDecision:
    """Outcome of :func:`allow_dispatch`.

    Attributes:
        verdict: ``"send"``, ``"coalesce"``, or ``"drop"``.
        reason: Optional short tag — useful in the dispatcher log line.
        coalesced_window: When ``verdict == "coalesce"``, identifies which
            bucket breached its limit so the in-app rollup copy can be
            cohort-specific ("hour" vs "day" vs "actor_24h").
    """

    verdict: Literal["send", "coalesce", "drop"]
    reason: str | None = None
    coalesced_window: Literal["hour", "day", "actor_24h"] | None = None


# ---------------------------------------------------------------------------
# Key shape helpers (asserted on by the integration tests).
# ---------------------------------------------------------------------------


def _hour_key(user_id: str, notif_type: NotificationType) -> str:
    return f"notif:{user_id}:rate:{notif_type.value}:hour"


def _day_key(user_id: str, notif_type: NotificationType) -> str:
    return f"notif:{user_id}:rate:{notif_type.value}:day"


def _actor_24h_key(actor_id: str, user_id: str) -> str:
    return f"notif:{actor_id}:{user_id}:cross_type:day"


def _dedup_key(notif_type: NotificationType, actor_id: str, target_id: str) -> str:
    return f"notif:dedup:{notif_type.value}:{actor_id}:{target_id}"


# ---------------------------------------------------------------------------
# Sentry alerting (mirror lib/rate_limit._alert_rate_limit_down).
# ---------------------------------------------------------------------------


def _alert_limiter_down(operation: str, exc: BaseException) -> None:
    """Emit a Sentry warning tagged ``notif_limiter.redis_down``.

    Pairs with the fail-open path so operators can correlate a sudden
    notification flood with a Redis outage. Mirror of
    :func:`auxd_api.lib.rate_limit._alert_rate_limit_down` with a
    notif-specific tag.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "notif_limiter")
        scope.set_tag("status", "redis_down")
        scope.set_extra("operation", operation)
        scope.set_extra("error", str(exc))
        sentry_sdk.capture_message("notif_limiter.redis_down", level="warning")


# ---------------------------------------------------------------------------
# Rate-limit primitive — mirrors lib/rate_limit._check_and_record.
# ---------------------------------------------------------------------------


async def _check_and_record(
    *,
    client: object,
    bucket_key: str,
    limit: int,
    window_seconds: int,
    now_ms: int,
) -> bool:
    """Sliding-window check + record. Returns ``True`` when under-limit.

    Sorted-set algorithm identical to :mod:`auxd_api.lib.rate_limit`:
    trim expired entries, count survivors, record the new hit, refresh
    TTL on the key. Returns ``False`` (would breach) when the count is
    AT-OR-OVER the limit — no hit recorded in that case so the limit
    "freezes" once breached, rather than the limit being moved forward.

    Raises :class:`RedisError` on transport / command failure — callers
    catch and convert to the fail-open path.
    """
    cutoff_ms = now_ms - window_seconds * 1000
    # mypy-friendly accessor — the real client is duck-typed Redis;
    # the integration tests inject fakeredis which honours the same
    # pipeline / zadd / expire API.
    pipe = client.pipeline()  # type: ignore[attr-defined]
    pipe.zremrangebyscore(bucket_key, 0, cutoff_ms)
    pipe.zcard(bucket_key)
    results = await pipe.execute()
    current_count = int(results[-1])
    if current_count >= limit:
        return False
    # Record this hit; same timestamp serves as score and member, so a
    # duplicate millisecond can't double-count the same producer.
    await client.zadd(bucket_key, {str(now_ms): now_ms})  # type: ignore[attr-defined]
    await client.expire(bucket_key, window_seconds)  # type: ignore[attr-defined]
    return True


# ---------------------------------------------------------------------------
# Public surface.
# ---------------------------------------------------------------------------


async def allow_dispatch(
    *,
    user_id: str,
    actor_id: str | None,
    notif_type: NotificationType,
    target_id: str | None = None,
    now_ms: int | None = None,
) -> CoalesceDecision:
    """Decide whether to ``send``, ``coalesce``, or ``drop`` a dispatch.

    Order of checks:
        1. Dedup (per-event) — drops the second occurrence of the same
           ``(type, actor_id, target_id)`` triple inside 1h.
        2. Per-user per-type per-hour — coalesces above 5/hr.
        3. Per-user per-type per-day — coalesces above 25/day.
        4. Per-actor cross-type 24h — coalesces above 3/24h. Only checked
           when ``actor_id`` is supplied (system notifications skip).

    Args:
        user_id: KSUID of the recipient.
        actor_id: KSUID of the user who triggered the event, or ``None``
            for system events. Cross-type per-actor bucket is skipped
            when ``None``.
        notif_type: Notification type from the taxonomy.
        target_id: Optional identifier of the *target object* — e.g. the
            review id for a review.liked event. Used in dedup. When
            ``None``, dedup is skipped (no key shape to construct).
        now_ms: Optional injected current-time-in-ms for deterministic
            tests; defaults to ``int(time.time() * 1000)``.

    Returns:
        A :class:`CoalesceDecision`. Verdict ``"send"`` means the
        dispatcher should fan out to all enabled channels and counts
        toward the limits. ``"coalesce"`` means write a single rollup
        notification with ``coalesced_count > 0`` and SKIP outbound email
        / push. ``"drop"`` means write nothing.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    # Lift the Redis client. RuntimeError means init_redis() hasn't
    # run — we mirror the rate-limit fail-open contract for tests +
    # local dev, but skip the Sentry alert because this is a setup state
    # not a runtime degradation.
    try:
        client = redis_module.get_redis()
    except RuntimeError:
        return CoalesceDecision(verdict="send", reason="limiter_disabled")

    try:
        # --- 1. Dedup ----------------------------------------------------
        if actor_id is not None and target_id is not None:
            dedup_key = _dedup_key(notif_type, actor_id, target_id)
            # ``set ... nx ex`` returns truthy when the key was set (i.e.
            # not previously present), and None when it already existed.
            written = await client.set(dedup_key, "1", ex=DEDUP_TTL_SECONDS, nx=True)
            if not written:
                return CoalesceDecision(verdict="drop", reason="dedup_window")

        # --- 2. Per-user per-type per-hour -------------------------------
        allowed_hour = await _check_and_record(
            client=client,
            bucket_key=_hour_key(user_id, notif_type),
            limit=HOUR_LIMIT,
            window_seconds=HOUR_WINDOW_SECONDS,
            now_ms=now_ms,
        )
        if not allowed_hour:
            return CoalesceDecision(
                verdict="coalesce",
                reason="user_type_hour",
                coalesced_window="hour",
            )

        # --- 3. Per-user per-type per-day --------------------------------
        allowed_day = await _check_and_record(
            client=client,
            bucket_key=_day_key(user_id, notif_type),
            limit=DAY_LIMIT,
            window_seconds=DAY_WINDOW_SECONDS,
            now_ms=now_ms,
        )
        if not allowed_day:
            return CoalesceDecision(
                verdict="coalesce",
                reason="user_type_day",
                coalesced_window="day",
            )

        # --- 4. Per-actor cross-type 24h ---------------------------------
        if actor_id is not None:
            allowed_actor = await _check_and_record(
                client=client,
                bucket_key=_actor_24h_key(actor_id, user_id),
                limit=ACTOR_24H_LIMIT,
                window_seconds=ACTOR_24H_WINDOW_SECONDS,
                now_ms=now_ms,
            )
            if not allowed_actor:
                return CoalesceDecision(
                    verdict="coalesce",
                    reason="actor_cross_type_24h",
                    coalesced_window="actor_24h",
                )

    except RedisError as exc:
        # FAIL OPEN — see module docstring. Better to over-send than miss
        # genuine signals during a brief Redis outage.
        _alert_limiter_down(operation=f"allow_dispatch:{notif_type.value}", exc=exc)
        return CoalesceDecision(verdict="send", reason="redis_fail_open")

    return CoalesceDecision(verdict="send")


__all__ = [
    "ACTOR_24H_LIMIT",
    "ACTOR_24H_WINDOW_SECONDS",
    "CoalesceDecision",
    "DAY_LIMIT",
    "DAY_WINDOW_SECONDS",
    "DEDUP_TTL_SECONDS",
    "HOUR_LIMIT",
    "HOUR_WINDOW_SECONDS",
    "allow_dispatch",
]
