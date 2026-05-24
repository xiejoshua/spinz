"""Beanie Documents for the Moderation module (T026).

Currently exposes a single collection — :class:`Report` (plan §3.1
``reports`` row) — plus the three enums that constrain its fields:

* :class:`ReportTargetType` — what the user is reporting. Extended in
  sync-fix L3-006 with ``missing_album`` so the catalog-gap surface
  (FR-005, US-F2) can reuse the same intake collection rather than
  spinning up a parallel ``catalog_gaps`` collection.
* :class:`ReportReason` — high-level category. ``catalog_gap`` pairs with
  ``target_type == missing_album``; the other reasons pair with the
  user/diary/review target types.
* :class:`ReportStatus` — moderation lifecycle. The daily aggregation job
  (FR-021) only considers ``OPEN`` rows.

The ``Report`` document itself is intentionally thin — moderation actions
(suspending a user, hiding content, fulfilling a missing-album request)
live in dedicated services that read these rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid

REPORT_DETAIL_MAX_LEN = 2000


class ReportTargetType(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """What the report is about.

    ``MISSING_ALBUM`` was added in sync-fix L3-006 — when a user searches
    the catalog and gets no hit, the "report this gap" CTA writes a
    :class:`Report` with ``target_type=missing_album`` and
    ``target_id=<the raw search query>``. This keeps catalog gaps in the
    same review queue as content/abuse reports without a second collection.
    """

    USER = "user"
    DIARY_ENTRY = "diary_entry"
    REVIEW = "review"
    MISSING_ALBUM = "missing_album"  # sync-fix L3-006 (FR-005, US-F2)
    # T167: report-wrong-album / album-merge admin path. Same Report
    # collection, distinct ``target_type`` so the moderation queue can
    # filter on it and the founder CLI (apps/api/scripts/merge_albums.py)
    # can prioritise album merges from user reports.
    ALBUM = "album"


class ReportReason(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """High-level reason category.

    ``CATALOG_GAP`` is only valid when paired with
    ``ReportTargetType.MISSING_ALBUM``; the service layer enforces that
    pairing — the schema deliberately keeps the enums independent so a
    single rejected combination doesn't require a schema migration.
    """

    HARASSMENT = "harassment"
    SPAM = "spam"
    NSFW = "nsfw"
    IMPERSONATION = "impersonation"
    HATE_SPEECH = "hate_speech"
    CATALOG_GAP = "catalog_gap"  # only with target_type=missing_album
    # T167 — album-report reasons. Distinct values so the founder
    # moderation funnel can track "wrong metadata" vs "duplicate album"
    # without inferring intent from a free-text detail field.
    WRONG_METADATA = "wrong_metadata"  # only with target_type=album
    DUPLICATE = "duplicate"  # only with target_type=album
    OTHER = "other"


class ReportStatus(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """Moderation lifecycle state.

    The daily aggregation job (FR-021) scans rows where ``status == OPEN``
    and groups by ``(target_type, target_id)`` to surface repeat offenders.
    """

    OPEN = "open"
    RESOLVED_NO_ACTION = "resolved_no_action"
    RESOLVED_WITH_ACTION = "resolved_with_action"
    DUPLICATE = "duplicate"


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory."""
    return datetime.now(UTC)


class Report(Document):
    """A single user-submitted moderation report.

    Indexes mirror plan §3.1 ``reports`` row:

    * ``(target_type, target_id)`` — "how many reports has this entity
      received?" pivots, used by the daily aggregation job.
    * ``(status, created_at desc)`` — the founder review queue, ordered
      newest-first within each status bucket.

    ``reporter_id`` is nullable because GDPR erasure (FR-019) blanks it on
    the original reporter's hard-delete while preserving the report itself
    for moderation history.
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    reporter_id: str | None  # nullable for GDPR-erased reporters (FR-019)
    target_type: ReportTargetType
    target_id: str
    # ^ for missing_album, the raw search query string; otherwise an entity KSUID.
    reason: ReportReason
    detail: str = Field(default="", max_length=REPORT_DETAIL_MAX_LEN)
    status: ReportStatus = ReportStatus.OPEN
    resolution_note: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    # T157 — when the founder acknowledges a report, ``acknowledged_at``
    # is set and N-012 ``report.acknowledged`` is dispatched to the
    # reporter. Distinct from ``resolved_at`` so the moderation lifecycle
    # (open → acknowledged → resolved) is traceable without overloading
    # the resolution timestamp.
    acknowledged_at: datetime | None = None

    class Settings:
        name = "reports"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("target_type", ASCENDING), ("target_id", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
        ]


__all__ = [
    "REPORT_DETAIL_MAX_LEN",
    "Report",
    "ReportReason",
    "ReportStatus",
    "ReportTargetType",
]
