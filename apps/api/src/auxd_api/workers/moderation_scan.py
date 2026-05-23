"""Daily moderation log-scan worker (T156).

03:00 UTC arq cron that:

1. Aggregates :class:`Report` rows from the trailing 7 days, grouped by
   the *target user* — for content reports (review / diary_entry) the
   author is resolved as the target.
2. When ``count >= 3`` for any user, flags them via
   :attr:`User.flagged_for_review` + :attr:`User.flagged_for_review_at`.
3. Posts a Discord webhook payload (when configured) summarising the
   flag — count, top reason categories, deep link template.
4. Idempotent: a user already flagged within the trailing 7 days is
   skipped on subsequent runs.

The flag is informational only at MVP. The founder reads it from
Mongo Compass / Discord and decides whether to suspend the account
(T159) or acknowledge the reports (T157). No automatic account
moderation is taken.

Threshold rationale: 3+ reports in a week is the same heuristic used by
the existing :class:`Report` aggregation pivot — small enough to catch
emerging abuse, large enough to avoid noise from one-off disagreements.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.moderation.models import Report, ReportTargetType
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.worker.moderation_scan")

# Number of reports in the trailing 7d that triggers a flag.
_FLAG_THRESHOLD = 3

# Look-back window for both report aggregation and the "already flagged
# recently?" idempotency check.
_LOOK_BACK = timedelta(days=7)

# Cap per run so a sudden flood can't pin the worker. 50 distinct flagged
# users in a day is far beyond any reasonable normal-state.
_BATCH_LIMIT = 50

# Discord webhook is best-effort — if the call fails the flag is still
# applied. Keep the timeout tight so a Discord outage doesn't drag the
# worker.
_DISCORD_TIMEOUT_SECONDS = 5.0


async def _resolve_target_user(report: Report) -> str | None:
    """Return the *author* user_id that ``report`` ultimately targets.

    For ``target_type=user`` reports, the target is the user directly.
    For review / diary_entry reports, we resolve the row's author. For
    missing_album reports, return ``None`` — those have no user target.
    """
    if report.target_type is ReportTargetType.USER:
        return report.target_id
    if report.target_type is ReportTargetType.REVIEW:
        row = await Review.find_one(Review.id == report.target_id)
        return row.user_id if row is not None else None
    if report.target_type is ReportTargetType.DIARY_ENTRY:
        row = await DiaryEntry.find_one(DiaryEntry.id == report.target_id)
        return row.user_id if row is not None else None
    return None


async def _aggregate_recent_reports() -> dict[str, list[Report]]:
    """Group trailing-7d reports by target user.

    Reports without a resolvable user target (missing_album, deleted
    review/entry) are dropped silently — the only thing we care about is
    "who has accumulated enough reports to flag?".
    """
    cutoff = datetime.now(UTC) - _LOOK_BACK
    rows = await Report.find({"created_at": {"$gte": cutoff}}).to_list()
    grouped: dict[str, list[Report]] = {}
    for report in rows:
        user_id = await _resolve_target_user(report)
        if user_id is None:
            continue
        grouped.setdefault(user_id, []).append(report)
    return grouped


def _summarise_reasons(reports: list[Report]) -> str:
    """Return a compact `reason(count)` summary for the Discord message."""
    counts: dict[str, int] = {}
    for r in reports:
        counts[r.reason.value] = counts.get(r.reason.value, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k} ({v})" for k, v in ordered)


async def _post_discord_alert(
    *,
    handle: str,
    user_id: str,
    count: int,
    reason_summary: str,
    webhook_url: str,
) -> None:
    """Best-effort Discord notification. Failures are logged, not raised."""
    message = (
        f":warning: User flagged for review: @{handle} ({user_id})\n"
        f"  - {count} reports in the trailing 7d\n"
        f"  - Reasons: {reason_summary}\n"
        f"  - Review: Mongo `users` collection, `_id`: {user_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=_DISCORD_TIMEOUT_SECONDS) as client:
            response = await client.post(webhook_url, json={"content": message})
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — best-effort
        log_call(
            provider="discord",
            endpoint="webhook.moderation_alert",
            latency_ms=0.0,
            status="failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return
    log_call(
        provider="discord",
        endpoint="webhook.moderation_alert",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": user_id, "count": count},
    )


async def scan_reports_for_flags(ctx: dict[str, Any]) -> int:
    """Cron entry-point. Returns the number of users newly flagged."""
    _ = ctx  # arq ctx not used; jobs lifted at startup.
    now = datetime.now(UTC)
    recent_cutoff = now - _LOOK_BACK

    grouped = await _aggregate_recent_reports()

    settings = get_settings()
    webhook_url = getattr(settings, "DISCORD_WEBHOOK_URL", None)

    newly_flagged = 0
    for user_id, reports in grouped.items():
        if len(reports) < _FLAG_THRESHOLD:
            continue
        if newly_flagged >= _BATCH_LIMIT:
            break

        user = await User.find_one(User.id == user_id)
        if user is None:
            # Author row vanished between the report write and now;
            # skip without alerting.
            continue

        # Idempotency: a user already flagged in the last 7 days is
        # skipped, no re-alert. Beanie reads DateTimes back from Mongo
        # as naive UTC by default — coerce to tz-aware before comparing
        # so the comparison doesn't crash with "can't compare
        # offset-naive and offset-aware".
        flagged_at = user.flagged_for_review_at
        if flagged_at is not None:
            if flagged_at.tzinfo is None:
                flagged_at = flagged_at.replace(tzinfo=UTC)
            if flagged_at >= recent_cutoff:
                continue

        user.flagged_for_review = True
        user.flagged_for_review_at = now
        await user.save()
        newly_flagged += 1

        summary = _summarise_reasons(reports)
        log_call(
            provider="auxd",
            endpoint="moderation.user_flagged",
            latency_ms=0.0,
            status="ok",
            extra={
                "user_id": user_id,
                "handle": user.handle,
                "report_count": len(reports),
                "reasons": summary,
            },
        )
        emit_event(
            user_id=None,
            event="moderation.user_flagged",
            properties={
                "user_id": user_id,
                "report_count": len(reports),
                "reasons": summary,
            },
        )

        if webhook_url:
            await _post_discord_alert(
                handle=user.handle,
                user_id=user_id,
                count=len(reports),
                reason_summary=summary,
                webhook_url=webhook_url,
            )

    log_call(
        provider="auxd",
        endpoint="moderation.scan_completed",
        latency_ms=0.0,
        status="ok",
        extra={"newly_flagged": newly_flagged, "candidates": len(grouped)},
    )
    return newly_flagged


# Re-export asyncio so module-level monkeypatching in tests can hook the
# sleep used by the Discord retry (none at MVP — kept for forward compat).
_ = asyncio

__all__ = ["scan_reports_for_flags"]
