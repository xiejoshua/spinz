"""Weekly digest dispatch job (T138 + T143 + CR-002 three-hero carousel).

arq cron job that fires every 5 minutes. For each :class:`User` whose
``notification_preferences.weekly_digest == True`` AND whose
``quiet_hours_tz``-local Monday 09:00 falls inside the current 5-minute
window, the job:

1. Builds a three-hero carousel (NT-2 / CR-002) — three aggregate
   queries on the trailing 7-day :class:`DiaryEntry` + :class:`Review`
   stream over the user's follow-graph: most-rated album, most-reviewed
   album, most-Aux'd album.
2. Counts :class:`ReviewLike` rows on the user's own reviews in the
   trailing 7 days — T143 review-likes hero is rendered when the count
   is ≥ 1.
3. Loads up to 10 chronological follow-graph diary entries from the
   trailing 7 days.
4. Dispatches an N-008 weekly_digest notification with the rich payload
   so the :class:`EmailAdapter` renders the
   ``n008_weekly_digest.html`` template (which the dispatcher then
   sends through Resend with the retry + FailedEmail wire).

NT-3: digest fires during quiet hours — the dispatcher's
:func:`is_notifiable` already carves email out of the quiet-hours
suppression so no special-casing is needed here.

Eligibility window: a user is eligible if their local time falls in
``[09:00, 09:05)`` on a Monday. The 5-minute cron cadence means we land
in this window exactly once per user per Monday.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from auxd_api.lib.observability import emit_event
from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.notifications.dispatcher import dispatch
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.reviews.models import Review, ReviewLike
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import User, UserStatus
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.worker.digest")

# Eligibility window. We fire the cron every 5 minutes, so a user whose
# local Monday 09:00 falls inside this window will be processed exactly
# once per week.
_DIGEST_WEEKDAY_MONDAY = 0  # datetime.weekday(): Monday is 0.
_DIGEST_HOUR = 9
_DIGEST_WINDOW_MINUTES = 5

# Trailing window for digest content + review-likes aggregate.
_TRAILING_WINDOW_DAYS = 7

# Cap on chronological entries surfaced in the digest body.
_MAX_DIGEST_ENTRIES = 10


# ---------------------------------------------------------------------------
# Eligibility predicate
# ---------------------------------------------------------------------------


def _is_eligible_now(*, user: User, now_utc: datetime) -> bool:
    """Return ``True`` if ``user``'s local time is in the eligibility window.

    Eligibility = local weekday is Monday AND local time is in
    ``[09:00, 09:05)``. Bad timezone strings on the User row fall back to
    UTC — defensive (settings UI validates IANA tz on write).
    """
    tz_name = user.quiet_hours_tz or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    local = now_utc.astimezone(tz)
    if local.weekday() != _DIGEST_WEEKDAY_MONDAY:
        return False
    if local.hour != _DIGEST_HOUR:
        return False
    return 0 <= local.minute < _DIGEST_WINDOW_MINUTES


# ---------------------------------------------------------------------------
# Three-hero carousel — NT-2 / CR-002
# ---------------------------------------------------------------------------


async def _get_followed_user_ids(user_id: str) -> list[str]:
    """Return the KSUIDs of every accepted followee of ``user_id``."""
    follows = await Follow.find(
        {"follower_id": user_id, "state": FollowState.ACCEPTED.value}
    ).to_list()
    return [f.followee_id for f in follows]


async def _build_hero_for_metric(
    *,
    followed_user_ids: list[str],
    window_start: datetime,
    label: str,
    metric_collection: str,
    match_filter: dict[str, Any] | None = None,
    sort_field: str,
    metric_text_template: str,
) -> dict[str, Any] | None:
    """Helper that runs a single hero aggregation pipeline.

    Returns a hero dict ``{label, album_id, album_title, artist_name,
    metric_value, metric_text}`` or ``None`` when no rows match.
    """
    if not followed_user_ids:
        return None

    match_stage: dict[str, Any] = {
        "user_id": {"$in": followed_user_ids},
        "created_at": {"$gte": window_start},
    }
    if match_filter is not None:
        match_stage.update(match_filter)

    group_stage: dict[str, Any]
    if metric_collection == "diary_entries_rating":
        group_stage = {
            "_id": "$album_id",
            "metric_value": {"$avg": "$rating"},
        }
        match_stage["rating"] = {"$ne": None}
        collection: type[Album] | type[DiaryEntry] | type[Review] = DiaryEntry
    elif metric_collection == "diary_entries_count":
        group_stage = {
            "_id": "$album_id",
            "metric_value": {"$sum": 1},
        }
        collection = DiaryEntry
    elif metric_collection == "reviews_count":
        group_stage = {
            "_id": "$album_id",
            "metric_value": {"$sum": 1},
        }
        collection = Review
    else:  # pragma: no cover — defensive
        return None

    pipeline = [
        {"$match": match_stage},
        {"$group": group_stage},
        {"$sort": {sort_field: -1}},
        {"$limit": 1},
    ]
    cursor = collection.aggregate(pipeline)
    rows = await cursor.to_list(length=1)
    if not rows:
        return None

    top = rows[0]
    album_id = top.get("_id")
    metric_value = top.get("metric_value")
    if album_id is None or metric_value is None:
        return None

    album = await Album.find_one(Album.id == album_id)
    if album is None:
        return None

    artist_name = ", ".join(a.name for a in album.artists) if album.artists else "Unknown"
    metric_text = metric_text_template.format(value=metric_value)
    return {
        "label": label,
        "album_id": album_id,
        "album_title": album.title,
        "artist_name": artist_name,
        "metric_value": metric_value,
        "metric_text": metric_text,
    }


async def _build_three_hero_carousel(
    *,
    followed_user_ids: list[str],
    window_start: datetime,
) -> list[dict[str, Any]]:
    """Build the three-hero carousel (most-rated / most-reviewed / most-Aux'd).

    Empty metrics are dropped — the carousel renders 0-3 heroes
    gracefully rather than padding with placeholders.
    """
    heroes: list[dict[str, Any]] = []

    most_rated = await _build_hero_for_metric(
        followed_user_ids=followed_user_ids,
        window_start=window_start,
        label="Most rated",
        metric_collection="diary_entries_rating",
        sort_field="metric_value",
        metric_text_template="Average rating {value:.1f}/5",
    )
    if most_rated is not None:
        heroes.append(most_rated)

    most_reviewed = await _build_hero_for_metric(
        followed_user_ids=followed_user_ids,
        window_start=window_start,
        label="Most reviewed",
        metric_collection="reviews_count",
        sort_field="metric_value",
        metric_text_template="{value:.0f} new reviews",
    )
    if most_reviewed is not None:
        heroes.append(most_reviewed)

    most_auxed = await _build_hero_for_metric(
        followed_user_ids=followed_user_ids,
        window_start=window_start,
        label="Most Aux'd",
        metric_collection="diary_entries_count",
        match_filter={"auxed": True},
        sort_field="metric_value",
        metric_text_template="{value:.0f} Aux'd this week",
    )
    if most_auxed is not None:
        heroes.append(most_auxed)

    return heroes


# ---------------------------------------------------------------------------
# T143 — review-likes hero
# ---------------------------------------------------------------------------


async def _count_review_likes_in_window(
    *,
    user_id: str,
    window_start: datetime,
) -> int:
    """Count ReviewLike rows on the user's reviews in the trailing window."""
    review_ids = [r.id async for r in Review.find(Review.user_id == user_id)]
    if not review_ids:
        return 0
    count = await ReviewLike.find(
        {
            "review_id": {"$in": review_ids},
            "created_at": {"$gte": window_start},
        }
    ).count()
    return int(count)


# ---------------------------------------------------------------------------
# Chronological body — top 10 follow-graph entries
# ---------------------------------------------------------------------------


async def _load_chronological_entries(
    *,
    followed_user_ids: list[str],
    window_start: datetime,
) -> list[dict[str, Any]]:
    """Load up to ten followed-user diary entries from the trailing window."""
    if not followed_user_ids:
        return []
    raw_entries = (
        await DiaryEntry.find(
            {
                "user_id": {"$in": followed_user_ids},
                "logged_at": {"$gte": window_start},
                "deleted_at": None,
                "visibility": {"$ne": "private"},
            }
        )
        .sort("-logged_at")
        .limit(_MAX_DIGEST_ENTRIES)
        .to_list()
    )
    if not raw_entries:
        return []

    # Batch lookup of users + albums for join.
    user_ids = {e.user_id for e in raw_entries}
    album_ids = {e.album_id for e in raw_entries}
    users = await User.find({"_id": {"$in": list(user_ids)}}).to_list()
    albums = await Album.find({"_id": {"$in": list(album_ids)}}).to_list()
    by_user = {u.id: u for u in users}
    by_album = {a.id: a for a in albums}

    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        actor = by_user.get(entry.user_id)
        album = by_album.get(entry.album_id)
        if actor is None or album is None:
            continue
        entries.append(
            {
                "actor_handle": actor.handle,
                "album_title": album.title,
                "rating": entry.rating,
                "logged_at_iso": entry.logged_at.isoformat(),
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Single-user dispatch
# ---------------------------------------------------------------------------


async def _dispatch_for_user(*, user: User, now_utc: datetime) -> bool:
    """Build + dispatch the digest for ``user``. Returns True if dispatched."""
    window_start = now_utc - timedelta(days=_TRAILING_WINDOW_DAYS)

    followed_user_ids = await _get_followed_user_ids(user.id)
    heroes = await _build_three_hero_carousel(
        followed_user_ids=followed_user_ids, window_start=window_start
    )
    review_likes_count = await _count_review_likes_in_window(
        user_id=user.id, window_start=window_start
    )
    entries = await _load_chronological_entries(
        followed_user_ids=followed_user_ids, window_start=window_start
    )

    settings = get_settings()
    summary_url = f"{settings.PUBLIC_APP_URL}/digest"
    hero_count = len(heroes) + (1 if review_likes_count > 0 else 0)

    payload: dict[str, Any] = {
        "summary_url": summary_url,
        "hero_count": hero_count,
        "heroes": heroes,
        "entries": entries,
        "review_likes_count": review_likes_count,
    }

    await dispatch(
        user_id=user.id,
        type=NotificationType.N008_WEEKLY_DIGEST,
        payload=payload,
        actor_id=None,
    )

    emit_event(
        user_id=user.id,
        event="digest.sent",
        properties={
            "user_id": user.id,
            "hero_count": len(heroes),
            "body_count": len(entries),
            "has_review_likes_hero": review_likes_count > 0,
        },
    )
    return True


# ---------------------------------------------------------------------------
# arq job — the cron entry point
# ---------------------------------------------------------------------------


async def dispatch_weekly_digests(ctx: dict[str, Any]) -> int:
    """Cron entry: dispatch the weekly digest to eligible users.

    Returns the number of digests dispatched on this invocation.
    """
    _ = ctx  # arq context unused — Beanie was initialised at worker startup.
    now_utc = datetime.now(UTC)
    dispatched = 0

    # Stream users to avoid loading the entire 100k corpus into RAM.
    # ``async for`` over Beanie's find cursor honours batches.
    async for user in User.find(
        {
            "status": UserStatus.ACTIVE.value,
            "notification_preferences.weekly_digest": True,
        }
    ):
        if not _is_eligible_now(user=user, now_utc=now_utc):
            continue
        try:
            sent = await _dispatch_for_user(user=user, now_utc=now_utc)
        except Exception as exc:  # noqa: BLE001 — one bad user must not stop the sweep
            _LOGGER.exception(
                "digest.user_failed",
                extra={
                    "event": "digest.user_failed",
                    "user_id": user.id,
                    "error": str(exc),
                },
            )
            continue
        if sent:
            dispatched += 1

    _LOGGER.info(
        "digest.sweep_completed",
        extra={
            "event": "digest.sweep_completed",
            "dispatched": dispatched,
            "now_utc": now_utc.isoformat(),
        },
    )
    return dispatched


__all__ = [
    "_dispatch_for_user",
    "_is_eligible_now",
    "dispatch_weekly_digests",
]
