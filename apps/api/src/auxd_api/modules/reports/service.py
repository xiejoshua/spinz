"""Content-report service helpers (T155 + T163a + T157).

Houses the small set of operations that mutate :class:`Report` rows
for the user / review / diary-entry routes plus the N-012 acknowledge
flow. Routes call into here so the business logic (idempotency
window, self-report rejection, FK validation) is unit-testable without
the HTTP layer.

T155 + T163a contract:

* Authenticated reporter only — anonymous reports of user content are
  not in the MVP scope (catalog-gap reports remain anonymous-friendly
  per the existing :func:`auxd_api.modules.reports.routes.report_missing_album`).
* Idempotency: within a rolling 24-hour window, the same
  ``(reporter_id, target_type, target_id)`` triple returns the existing
  row — no duplicate inserts.
* Self-report on user targets is rejected with a 422.
* FK validation: the target user / review / diary entry must exist.

T157 contract:

* :func:`acknowledge_report` marks an open report ``acknowledged_at = now``
  and dispatches ``N-012 report.acknowledged`` to the original
  reporter. Re-acknowledging is an idempotent no-op (no double
  dispatch, no timestamp drift).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.notifications.dispatcher import dispatch as dispatch_notification
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User

# 24-hour idempotency window for duplicate reports — keeps the queue
# clean without disenfranchising a user who legitimately reports a
# repeat offender for a fresh incident after a day.
_IDEMPOTENCY_WINDOW = timedelta(hours=24)


class ReportError(Exception):
    """Base class for report-service-layer errors with a stable ``code``."""

    code: str = "report_error"


class TargetNotFoundError(ReportError):
    code = "target_not_found"


class SelfReportError(ReportError):
    code = "self_report_forbidden"


class ReportAlreadyAcknowledgedError(ReportError):
    """Raised when :func:`acknowledge_report` is called twice on the same row."""

    code = "already_acknowledged"


@dataclass(frozen=True, slots=True)
class SubmitResult:
    """Outcome of :func:`submit_report` — flags whether the row was new."""

    report: Report
    created: bool


async def _target_exists(target_type: ReportTargetType, target_id: str) -> bool:
    """Return ``True`` when ``target_id`` exists in the target's collection."""
    if target_type is ReportTargetType.USER:
        return await User.find_one(User.id == target_id) is not None
    if target_type is ReportTargetType.REVIEW:
        return await Review.find_one(Review.id == target_id) is not None
    if target_type is ReportTargetType.DIARY_ENTRY:
        return await DiaryEntry.find_one(DiaryEntry.id == target_id) is not None
    if target_type is ReportTargetType.ALBUM:
        return await Album.find_one(Album.id == target_id) is not None
    # The catalog-gap path passes a free-text query as target_id — no FK
    # check is meaningful there. Caller never passes that target_type
    # into this service; routes for MISSING_ALBUM live in routes.py.
    return False


async def submit_report(
    *,
    reporter_id: str,
    target_type: ReportTargetType,
    target_id: str,
    reason: ReportReason,
    detail: str | None,
) -> SubmitResult:
    """Persist a user/review/diary report with idempotency + FK validation.

    Returns :class:`SubmitResult` — ``created=False`` means the caller
    hit the idempotency window and should return ``200`` with the
    existing row instead of ``201``.

    Raises:
        SelfReportError: ``reporter_id == target_id`` on a user target.
        TargetNotFoundError: target row doesn't exist.
    """
    if target_type is ReportTargetType.USER and reporter_id == target_id:
        raise SelfReportError("cannot report your own account")

    if not await _target_exists(target_type, target_id):
        raise TargetNotFoundError(f"{target_type.value} not found")

    # Idempotency window — the same (reporter, target_type, target_id)
    # triple within 24h reuses the existing row.
    cutoff = datetime.now(UTC) - _IDEMPOTENCY_WINDOW
    existing = await Report.find_one(
        {
            "reporter_id": reporter_id,
            "target_type": target_type.value,
            "target_id": target_id,
            "created_at": {"$gte": cutoff},
        }
    )
    if existing is not None:
        return SubmitResult(report=existing, created=False)

    report = Report(
        reporter_id=reporter_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        detail=(detail or ""),
        status=ReportStatus.OPEN,
    )
    await report.insert()
    return SubmitResult(report=report, created=True)


async def acknowledge_report(report_id: str, *, ack_note: str | None = None) -> Report:
    """Mark a report acknowledged and dispatch N-012 to the reporter.

    Idempotent: a second call returns the existing row without
    re-dispatching the notification or moving the timestamp.

    Args:
        report_id: KSUID of the :class:`Report` to acknowledge.
        ack_note: Optional short note included on the N-012 payload so
            the reporter sees a custom message instead of the canned
            "your report was reviewed" copy.

    Raises:
        TargetNotFoundError: ``report_id`` doesn't exist.
    """
    row = await Report.find_one(Report.id == report_id)
    if row is None:
        raise TargetNotFoundError(f"report {report_id!r} not found")

    if row.acknowledged_at is not None:
        # Already acknowledged — no-op. Mirrors the FollowRequest
        # approve route's idempotent stance.
        return row

    row.acknowledged_at = datetime.now(UTC)
    await row.save()

    if row.reporter_id is not None:
        # Anonymous reports (catalog-gap) have no reporter to notify;
        # skip the dispatch but still mark the row.
        payload: dict[str, str] = {"report_id": row.id}
        if ack_note:
            payload["ack_note"] = ack_note
        await dispatch_notification(
            user_id=row.reporter_id,
            type=NotificationType.N012_REPORT_ACKNOWLEDGED,
            payload=payload,
            actor_id=None,
        )

    return row


__all__ = [
    "ReportAlreadyAcknowledgedError",
    "ReportError",
    "SelfReportError",
    "SubmitResult",
    "TargetNotFoundError",
    "acknowledge_report",
    "submit_report",
]
