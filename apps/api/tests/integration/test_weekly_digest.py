"""Integration tests for the weekly digest dispatcher (T138 + T143).

Covers:

* Eligibility predicate: Monday 09:02 local → eligible; off-window
  rejects.
* User opt-out: ``weekly_digest=False`` → skipped.
* Suspended user: ``status=SUSPENDED`` → skipped.
* Empty follow-graph: digest renders 0 heroes gracefully (no 500).
* Three-hero carousel: renders when all three metrics have data.
* Two-hero carousel: drops the empty metric.
* T143: ≥1 ReviewLike in trailing 7d → review-likes hero in payload.
* T143: 0 ReviewLikes → review-likes hero NOT rendered.
* NT-3: digest fires during quiet hours (email channel bypass).
* Full sweep batch: cron run hits only the 09:00–09:04 eligible window.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource, ArtistRefSubDoc
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.notifications import coalescer as coalescer_module
from auxd_api.modules.notifications import dispatcher as dispatcher_module
from auxd_api.modules.notifications.coalescer import CoalesceDecision
from auxd_api.modules.notifications.models import (
    FailedEmail,
    Notification,
    NotificationType,
)
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.reviews.models import Review, ReviewLike
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import (
    NotificationPreferencesSubDoc,
    User,
    UserStatus,
)
from auxd_api.workers import digest_dispatch as digest_module
from auxd_api.workers.digest_dispatch import (
    _dispatch_for_user,
    _is_eligible_now,
    dispatch_weekly_digests,
)


@pytest.fixture
def _digest_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Set the env so settings + Resend client work cleanly."""
    monkeypatch.setenv("SESSION_HMAC_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_stub")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://auxd.test")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _clean() -> AsyncIterator[None]:
    """Reset every collection touched by the digest path."""
    for cls in (
        User,
        Follow,
        DiaryEntry,
        Review,
        ReviewLike,
        Album,
        Notification,
        FailedEmail,
        PushSubscription,
    ):
        await cls.delete_all()
    yield
    for cls in (
        User,
        Follow,
        DiaryEntry,
        Review,
        ReviewLike,
        Album,
        Notification,
        FailedEmail,
        PushSubscription,
    ):
        await cls.delete_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_monday_morning(*, minute: int = 2) -> datetime:
    """Build a UTC datetime that lands on Monday at 09:0M UTC."""
    # Pick a known Monday: 2026-05-25 is a Monday.
    return datetime(2026, 5, 25, 9, minute, tzinfo=UTC)


async def _make_user(
    *,
    handle: str,
    weekly_digest: bool = True,
    status: UserStatus = UserStatus.ACTIVE,
    quiet_hours_tz: str = "UTC",
) -> User:
    prefs = NotificationPreferencesSubDoc(weekly_digest=weekly_digest)
    user = User(
        handle=handle,
        email=f"{handle}@example.com",
        display_name=handle.title(),
        password_hash="$argon2id$test",
        status=status,
        notification_preferences=prefs,
        quiet_hours_tz=quiet_hours_tz,
    )
    await user.insert()
    return user


async def _make_album(*, title: str, artist: str) -> Album:
    album = Album(
        title=title,
        artists=[ArtistRefSubDoc(name=artist)],
        artist_credit=artist,
        source=AlbumSource.MANUAL,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()
    return album


async def _make_follow(*, follower: User, followee: User) -> None:
    follow = Follow(
        follower_id=follower.id,
        followee_id=followee.id,
        state=FollowState.ACCEPTED,
    )
    await follow.insert()


async def _stub_dispatch(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace ``dispatch`` in the worker with a capturing stub."""
    captured: list[dict[str, Any]] = []

    async def _fake_dispatch(**kwargs: Any) -> None:
        captured.append(kwargs)
        return None

    monkeypatch.setattr(digest_module, "dispatch", _fake_dispatch)
    return captured


# ---------------------------------------------------------------------------
# Eligibility predicate
# ---------------------------------------------------------------------------


def test_eligibility_monday_morning_window() -> None:
    """Monday 09:02 UTC, user-tz UTC → eligible."""
    user = User(
        handle="user_one",
        email="user_one@example.com",
        display_name="User One",
        password_hash="$argon2id$x",
        quiet_hours_tz="UTC",
    )
    now = _utc_monday_morning(minute=2)
    assert _is_eligible_now(user=user, now_utc=now) is True


def test_eligibility_outside_window() -> None:
    """Monday 10:00 UTC → not eligible (past the 5-min slot)."""
    user = User(
        handle="user_two",
        email="user_two@example.com",
        display_name="User Two",
        password_hash="$argon2id$x",
        quiet_hours_tz="UTC",
    )
    now = datetime(2026, 5, 25, 10, 0, tzinfo=UTC)
    assert _is_eligible_now(user=user, now_utc=now) is False


def test_eligibility_not_monday() -> None:
    """Tuesday 09:02 UTC → not eligible."""
    user = User(
        handle="user_three",
        email="user_three@example.com",
        display_name="User Three",
        password_hash="$argon2id$x",
        quiet_hours_tz="UTC",
    )
    now = datetime(2026, 5, 26, 9, 2, tzinfo=UTC)
    assert _is_eligible_now(user=user, now_utc=now) is False


# ---------------------------------------------------------------------------
# Single-user dispatch — TC-027 + carousel coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_for_user_empty_follow_graph_renders_zero_heroes(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """User with zero follows → carousel renders 0 heroes, no crash."""
    captured = await _stub_dispatch(monkeypatch)
    user = await _make_user(handle="alone")

    sent = await _dispatch_for_user(user=user, now_utc=_utc_monday_morning())
    assert sent is True
    assert len(captured) == 1
    payload = captured[0]["payload"]
    assert payload["hero_count"] == 0
    assert payload["heroes"] == []
    assert payload["entries"] == []
    assert payload["review_likes_count"] == 0


@pytest.mark.asyncio
async def test_dispatch_three_hero_carousel_all_metrics(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """All three metrics populated → carousel renders three heroes."""
    captured = await _stub_dispatch(monkeypatch)

    viewer = await _make_user(handle="viewer")
    friend = await _make_user(handle="friend")
    await _make_follow(follower=viewer, followee=friend)

    album_a = await _make_album(title="Album A", artist="Artist A")
    album_b = await _make_album(title="Album B", artist="Artist B")
    album_c = await _make_album(title="Album C", artist="Artist C")

    # Most-rated source: a high-rated diary entry on album A.
    await DiaryEntry(
        user_id=friend.id,
        album_id=album_a.id,
        logged_at=datetime.now(UTC) - timedelta(days=2),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    # Most-reviewed source: 3 reviews on album B (more than album A which has 0).
    for i in range(3):
        await Review(
            user_id=friend.id,
            diary_entry_id=f"diary_entry_{i}",
            album_id=album_b.id,
            body="great album",
        ).insert()

    # Most-Aux'd source: 2 Aux'd entries on album C.
    for _ in range(2):
        await DiaryEntry(
            user_id=friend.id,
            album_id=album_c.id,
            logged_at=datetime.now(UTC) - timedelta(days=1),
            auxed=True,
            visibility=Visibility.PUBLIC,
        ).insert()

    sent = await _dispatch_for_user(user=viewer, now_utc=_utc_monday_morning())
    assert sent is True
    payload = captured[0]["payload"]
    heroes = payload["heroes"]
    # Three heroes expected, one per metric.
    assert len(heroes) == 3
    labels = {h["label"] for h in heroes}
    assert labels == {"Most rated", "Most reviewed", "Most Aux'd"}


@pytest.mark.asyncio
async def test_dispatch_two_hero_carousel_skips_empty_metric(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """Empty metric dropped, not padded with placeholder."""
    captured = await _stub_dispatch(monkeypatch)

    viewer = await _make_user(handle="viewer2")
    friend = await _make_user(handle="friend2")
    await _make_follow(follower=viewer, followee=friend)

    album_a = await _make_album(title="Album A", artist="A")
    album_b = await _make_album(title="Album B", artist="B")

    # Only most-rated + most-Aux'd; no reviews.
    await DiaryEntry(
        user_id=friend.id,
        album_id=album_a.id,
        logged_at=datetime.now(UTC) - timedelta(days=2),
        rating=4.5,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=friend.id,
        album_id=album_b.id,
        logged_at=datetime.now(UTC) - timedelta(days=1),
        auxed=True,
        visibility=Visibility.PUBLIC,
    ).insert()

    sent = await _dispatch_for_user(user=viewer, now_utc=_utc_monday_morning())
    assert sent is True
    heroes = captured[0]["payload"]["heroes"]
    labels = {h["label"] for h in heroes}
    assert "Most reviewed" not in labels
    assert labels == {"Most rated", "Most Aux'd"}


# ---------------------------------------------------------------------------
# T143 review-likes hero
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t143_review_likes_hero_rendered_when_count_geq_1(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """≥1 ReviewLike in trailing 7d → review_likes_count > 0."""
    captured = await _stub_dispatch(monkeypatch)
    viewer = await _make_user(handle="reviewer")

    # The viewer's own review.
    review = Review(
        user_id=viewer.id,
        diary_entry_id="reviewer_diary_entry_1",
        album_id="some_album",
        body="my take",
    )
    await review.insert()

    # Two likes from different actors inside the window.
    for actor in ("actor_a", "actor_b"):
        await ReviewLike(review_id=review.id, user_id=actor).insert()

    sent = await _dispatch_for_user(user=viewer, now_utc=_utc_monday_morning())
    assert sent is True
    payload = captured[0]["payload"]
    assert payload["review_likes_count"] == 2
    # hero_count includes the review-likes hero entry.
    assert payload["hero_count"] >= 1


@pytest.mark.asyncio
async def test_t143_review_likes_hero_not_rendered_when_zero(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """0 ReviewLikes → review_likes_count == 0 (no empty zero-state)."""
    captured = await _stub_dispatch(monkeypatch)
    viewer = await _make_user(handle="zeroreviewer")

    sent = await _dispatch_for_user(user=viewer, now_utc=_utc_monday_morning())
    assert sent is True
    assert captured[0]["payload"]["review_likes_count"] == 0


# ---------------------------------------------------------------------------
# Sweep / cron-batch behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweep_skips_opted_out_and_suspended(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """Sweep dispatches only to ACTIVE + weekly_digest=True users."""
    captured = await _stub_dispatch(monkeypatch)

    # Eligible.
    eligible = await _make_user(handle="eligible")
    # Opted out.
    await _make_user(handle="opted_out", weekly_digest=False)
    # Suspended.
    await _make_user(handle="suspended", status=UserStatus.SUSPENDED)

    monkeypatch.setattr(digest_module, "datetime", _FakeDatetime(_utc_monday_morning(minute=2)))

    dispatched = await dispatch_weekly_digests(ctx={})
    assert dispatched == 1
    assert len(captured) == 1
    assert captured[0]["user_id"] == eligible.id


@pytest.mark.asyncio
async def test_sweep_off_window_skips_all(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """When the cron fires outside 09:00–09:04 UTC, no users are dispatched."""
    captured = await _stub_dispatch(monkeypatch)
    await _make_user(handle="window_test")

    # Run at 10:00 Monday UTC — past the eligibility window.
    monkeypatch.setattr(
        digest_module,
        "datetime",
        _FakeDatetime(datetime(2026, 5, 25, 10, 0, tzinfo=UTC)),
    )

    dispatched = await dispatch_weekly_digests(ctx={})
    assert dispatched == 0
    assert captured == []


@pytest.mark.asyncio
async def test_sweep_hourly_batches_only_one_eligible(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """Twelve 5-min invocations across an hour → exactly one fires the digest."""
    user = await _make_user(handle="hourly_test")

    fire_count = 0
    fired: list[datetime] = []

    async def _fake_dispatch(**kwargs: Any) -> None:
        nonlocal fire_count
        fire_count += 1
        return None

    monkeypatch.setattr(digest_module, "dispatch", _fake_dispatch)

    # Step the clock from 08:00 through 09:55 UTC in 5-minute increments
    # (24 invocations across two hours). Only the 09:00 invocation should
    # land in the eligibility window.
    base_hour = 8
    for hour_offset in range(2):
        for minute in range(0, 60, 5):
            now = datetime(2026, 5, 25, base_hour + hour_offset, minute, tzinfo=UTC)
            monkeypatch.setattr(digest_module, "datetime", _FakeDatetime(now))
            await dispatch_weekly_digests(ctx={})
            if fire_count > 0 and not fired:
                fired.append(now)

    assert fire_count == 1
    assert fired[0].hour == 9 and fired[0].minute == 0
    _ = user  # silence


# ---------------------------------------------------------------------------
# NT-3: quiet hours do NOT suppress digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nt3_digest_fires_during_quiet_hours(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """Digest fires even when the user is in quiet hours per NT-3.

    We assert by calling ``is_notifiable`` for the email channel on
    N-008 while quiet hours wrap the current local time.
    """
    user = await _make_user(handle="quiet_user")
    # Set quiet hours in-memory only — mongomock-motor cannot serialize
    # datetime.time, but ``is_notifiable`` reads off the in-memory User.
    user.quiet_hours_start = time(22, 0)
    user.quiet_hours_end = time(8, 0)
    user.quiet_hours_tz = "UTC"

    # 02:00 UTC — inside quiet hours.
    now = datetime(2026, 5, 25, 2, 0, tzinfo=UTC)
    decision = await dispatcher_module.is_notifiable(
        user, NotificationType.N008_WEEKLY_DIGEST, "email", now=now
    )
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_digest_dispatches_via_dispatcher_writes_email_path(
    monkeypatch: pytest.MonkeyPatch, _digest_env: None
) -> None:
    """End-to-end: real ``dispatch`` for digest fires email path through adapter."""
    # Patch coalescer to send; patch Resend to capture invocation.
    monkeypatch.setattr(
        coalescer_module,
        "allow_dispatch",
        AsyncMock(return_value=CoalesceDecision(verdict="send")),
    )
    captured: dict[str, Any] = {}

    def _fake_send(args: dict[str, Any]) -> dict[str, str]:
        captured.update(args)
        return {"id": "x"}

    import resend

    monkeypatch.setattr(resend.Emails, "send", _fake_send)

    user = await _make_user(handle="digest_e2e")
    sent = await _dispatch_for_user(user=user, now_utc=_utc_monday_morning())
    assert sent is True
    # Email channel default-on for N-008 → Resend invocation captured.
    assert captured.get("to") == [user.email]
    assert "auxd" in captured.get("subject", "").lower()


# ---------------------------------------------------------------------------
# Test helper: a fake datetime module that lets us inject a fixed "now".
# ---------------------------------------------------------------------------


class _FakeDatetime:
    """Stand-in for the ``datetime`` module exposing the fields the worker uses.

    Only the bits the worker touches are reimplemented; everything else
    delegates to the real module so isinstance + arithmetic still work.
    """

    def __init__(self, now_utc: datetime) -> None:
        self._now = now_utc

    def now(self, tz: Any = None) -> datetime:  # noqa: D401 — mimic datetime.now
        if tz is None:
            return self._now.replace(tzinfo=None)
        return self._now.astimezone(tz)

    UTC = UTC

    @property
    def datetime(self) -> type[datetime]:
        return datetime

    timedelta = timedelta
