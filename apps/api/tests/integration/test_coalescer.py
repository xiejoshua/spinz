"""Integration tests for the notification coalescer (T133).

Uses ``fakeredis.aioredis.FakeRedis`` (added to dev-deps in pyproject) to
exercise the real :func:`coalescer.allow_dispatch` against an in-memory
Redis. Each test gets a fresh fake client to keep buckets isolated.

Covers:

* All three rate-limit buckets (hour / day / actor_24h) — under-limit
  returns ``send`` + records a hit, at-limit returns ``coalesce`` with
  the correct ``coalesced_window``.
* Per-event dedup — same ``(type, actor, target)`` returns ``drop`` on
  second call; differs on actor / target / type don't.
* Fail-open path — :func:`get_redis` raising / Redis transport error
  returns ``send`` and (in the transport-error case) fires the
  ``notif_limiter.redis_down`` Sentry alert.
* TC-026 review-storm scenario: per-actor cross-type bucket caps the
  fan-out at 3 in a 24h window.
* Key-shape assertions so a future refactor can't silently rename the
  bucket scheme.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import fakeredis.aioredis
import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from auxd_api import redis_client as redis_module
from auxd_api.modules.notifications import coalescer as coalescer_module
from auxd_api.modules.notifications.coalescer import (
    ACTOR_24H_LIMIT,
    DAY_LIMIT,
    DEDUP_TTL_SECONDS,
    HOUR_LIMIT,
    _actor_24h_key,
    _day_key,
    _dedup_key,
    _hour_key,
    allow_dispatch,
)
from auxd_api.modules.notifications.models import NotificationType

# Fixed ``now_ms`` used by tests so sliding-window math is deterministic.
_NOW_MS = 1_700_000_000_000


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """Provide an in-memory Redis client installed at the module level."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module._client = client
    try:
        yield client
    finally:
        await client.aclose()
        redis_module._client = None


# ---------------------------------------------------------------------------
# Happy path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_under_all_limits_returns_send(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    decision = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=NotificationType.N001_FOLLOW_NEW,
        target_id=None,
        now_ms=_NOW_MS,
    )
    assert decision.verdict == "send"
    assert decision.coalesced_window is None
    # Recorded a hit in both per-user buckets and the actor bucket.
    assert await fake_redis.zcard(_hour_key("u1", NotificationType.N001_FOLLOW_NEW)) == 1
    assert await fake_redis.zcard(_day_key("u1", NotificationType.N001_FOLLOW_NEW)) == 1
    assert await fake_redis.zcard(_actor_24h_key("actor1", "u1")) == 1


# ---------------------------------------------------------------------------
# Per-user per-type per-hour.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hour_limit_breach_returns_coalesce(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """5 follow.new events in the hour land; the 6th coalesces."""
    notif_type = NotificationType.N004_REVIEW_LIKED
    # Pre-seed 5 hits in the hour bucket directly so we don't blow the
    # per-actor cross-type bucket (which would coalesce first).
    hour_key = _hour_key("u1", notif_type)
    for i in range(HOUR_LIMIT):
        await fake_redis.zadd(hour_key, {str(_NOW_MS + i): _NOW_MS + i})

    decision = await allow_dispatch(
        user_id="u1",
        actor_id=None,  # skip cross-type bucket
        notif_type=notif_type,
        target_id=None,
        now_ms=_NOW_MS + HOUR_LIMIT,
    )
    assert decision.verdict == "coalesce"
    assert decision.coalesced_window == "hour"


# ---------------------------------------------------------------------------
# Per-user per-type per-day.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_day_limit_breach_returns_coalesce(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """Day bucket caps at 25; the 26th coalesces with window=day."""
    notif_type = NotificationType.N004_REVIEW_LIKED
    # Pre-seed the day bucket at the limit. Use timestamps spread over a
    # 23h window so the hour bucket stays under-limit.
    day_key = _day_key("u1", notif_type)
    for i in range(DAY_LIMIT):
        ts = _NOW_MS - (3700 * 1000) - (i * 60_000)  # >1h ago, well spread
        await fake_redis.zadd(day_key, {str(ts): ts})

    decision = await allow_dispatch(
        user_id="u1",
        actor_id=None,
        notif_type=notif_type,
        target_id=None,
        now_ms=_NOW_MS,
    )
    assert decision.verdict == "coalesce"
    assert decision.coalesced_window == "day"


# ---------------------------------------------------------------------------
# Per-actor cross-type 24h.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actor_cross_type_breach_returns_coalesce(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """One actor blasting one recipient >3 in 24h triggers actor_24h coalesce."""
    actor_key = _actor_24h_key("actor_storm", "u1")
    for i in range(ACTOR_24H_LIMIT):
        ts = _NOW_MS - (i * 1000)
        await fake_redis.zadd(actor_key, {str(ts): ts})

    decision = await allow_dispatch(
        user_id="u1",
        actor_id="actor_storm",
        notif_type=NotificationType.N004_REVIEW_LIKED,
        target_id="rev_new",
        now_ms=_NOW_MS + 500,
    )
    assert decision.verdict == "coalesce"
    assert decision.coalesced_window == "actor_24h"


# ---------------------------------------------------------------------------
# TC-026 — review storm scenario.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tc026_review_storm_coalesces_after_three_likes(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """Per spec TC-026: 3 review.liked from same actor → 4th coalesces.

    The per-actor cross-type bucket is the binding constraint here (3 in
    24h), so the 4th event from the same actor to the same recipient
    must coalesce regardless of the per-type buckets being well
    under-limit.
    """
    notif_type = NotificationType.N004_REVIEW_LIKED
    actor = "fan_alice"
    recipient = "creator_bob"

    # Three legitimate likes — each lands as send.
    for i in range(3):
        decision = await allow_dispatch(
            user_id=recipient,
            actor_id=actor,
            notif_type=notif_type,
            target_id=f"rev_{i}",
            now_ms=_NOW_MS + i * 60_000,
        )
        assert decision.verdict == "send", f"like #{i} should send"

    # The 4th coalesces via the actor_24h bucket.
    fourth = await allow_dispatch(
        user_id=recipient,
        actor_id=actor,
        notif_type=notif_type,
        target_id="rev_4",
        now_ms=_NOW_MS + 4 * 60_000,
    )
    assert fourth.verdict == "coalesce"
    assert fourth.coalesced_window == "actor_24h"


# ---------------------------------------------------------------------------
# Dedup.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_same_event_drops_second(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    notif_type = NotificationType.N004_REVIEW_LIKED
    first = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=notif_type,
        target_id="rev_x",
        now_ms=_NOW_MS,
    )
    assert first.verdict == "send"

    second = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=notif_type,
        target_id="rev_x",
        now_ms=_NOW_MS + 500,
    )
    assert second.verdict == "drop"
    assert second.reason == "dedup_window"


@pytest.mark.asyncio
async def test_dedup_different_actor_same_target_not_deduped(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    notif_type = NotificationType.N004_REVIEW_LIKED
    first = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=notif_type,
        target_id="rev_x",
        now_ms=_NOW_MS,
    )
    assert first.verdict == "send"
    second = await allow_dispatch(
        user_id="u1",
        actor_id="actor2",  # different actor
        notif_type=notif_type,
        target_id="rev_x",
        now_ms=_NOW_MS + 500,
    )
    assert second.verdict == "send"


@pytest.mark.asyncio
async def test_dedup_different_type_same_actor_target_not_deduped(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    # Use albums-style target ids so both types have a fold-in identifier.
    first = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=NotificationType.N004_REVIEW_LIKED,
        target_id="album_x",
        now_ms=_NOW_MS,
    )
    assert first.verdict == "send"
    second = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=NotificationType.N006_FRIEND_LOGGED_ALBUM,  # different type
        target_id="album_x",
        now_ms=_NOW_MS + 500,
    )
    assert second.verdict == "send"


@pytest.mark.asyncio
async def test_dedup_ttl_matches_spec(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """The dedup key TTL is 1 hour per spec."""
    notif_type = NotificationType.N004_REVIEW_LIKED
    await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=notif_type,
        target_id="rev_x",
        now_ms=_NOW_MS,
    )
    ttl = await fake_redis.ttl(_dedup_key(notif_type, "actor1", "rev_x"))
    assert 0 < ttl <= DEDUP_TTL_SECONDS


# ---------------------------------------------------------------------------
# Fail-open semantics.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_uninitialised_returns_send_without_sentry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No init_redis() ran → fail open silently. No Sentry alert in this branch."""
    redis_module._client = None
    alerts: list[str] = []
    monkeypatch.setattr(
        coalescer_module,
        "_alert_limiter_down",
        lambda operation, exc: alerts.append(operation),
    )
    decision = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=NotificationType.N004_REVIEW_LIKED,
        target_id="rev_x",
        now_ms=_NOW_MS,
    )
    assert decision.verdict == "send"
    assert decision.reason == "limiter_disabled"
    assert alerts == []


@pytest.mark.asyncio
async def test_redis_error_fails_open_with_sentry_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RedisError during the check fails open + fires the Sentry alert."""

    class BrokenClient:
        def pipeline(self) -> Any:  # noqa: ANN401
            raise RedisConnectionError("disconnected")

        async def set(self, *a: Any, **k: Any) -> bool:  # noqa: ANN401
            return True

        async def zadd(self, *a: Any, **k: Any) -> int:  # noqa: ANN401
            return 1

        async def expire(self, *a: Any, **k: Any) -> bool:  # noqa: ANN401
            return True

    redis_module._client = BrokenClient()  # type: ignore[assignment]
    alerts: list[str] = []
    monkeypatch.setattr(
        coalescer_module,
        "_alert_limiter_down",
        lambda operation, exc: alerts.append(operation),
    )

    decision = await allow_dispatch(
        user_id="u1",
        actor_id="actor1",
        notif_type=NotificationType.N004_REVIEW_LIKED,
        target_id=None,
        now_ms=_NOW_MS,
    )
    assert decision.verdict == "send"
    assert decision.reason == "redis_fail_open"
    assert len(alerts) == 1
    assert "review.liked" in alerts[0]
    redis_module._client = None


@pytest.mark.asyncio
async def test_no_actor_skips_cross_type_check(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """System notifications (no actor_id) skip the per-actor bucket."""
    # Pre-fill the actor bucket so a check would coalesce; but since we
    # pass actor_id=None the cross-type bucket is skipped entirely.
    notif_type = NotificationType.N008_WEEKLY_DIGEST
    decision = await allow_dispatch(
        user_id="u1",
        actor_id=None,
        notif_type=notif_type,
        target_id=None,
        now_ms=_NOW_MS,
    )
    assert decision.verdict == "send"
    # No cross-type bucket was created.
    keys = await fake_redis.keys("*cross_type*")
    assert keys == []


# ---------------------------------------------------------------------------
# Key-shape asserts (regression guard against silent renames).
# ---------------------------------------------------------------------------


def test_key_shape_hour() -> None:
    key = _hour_key("u_abc", NotificationType.N001_FOLLOW_NEW)
    assert key == "notif:u_abc:rate:follow.new:hour"


def test_key_shape_day() -> None:
    key = _day_key("u_abc", NotificationType.N004_REVIEW_LIKED)
    assert key == "notif:u_abc:rate:review.liked:day"


def test_key_shape_actor_24h() -> None:
    key = _actor_24h_key("actor_abc", "user_xyz")
    assert key == "notif:actor_abc:user_xyz:cross_type:day"


def test_key_shape_dedup() -> None:
    key = _dedup_key(NotificationType.N004_REVIEW_LIKED, "actor_abc", "rev_xyz")
    assert key == "notif:dedup:review.liked:actor_abc:rev_xyz"
