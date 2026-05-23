"""GDPR audit log Document (T154).

Append-only record of every GDPR-significant action against a user
account — export requests + completions, deletion lifecycle events.

Schema is deliberately thin: a single document captures both halves of
an export request (request + completion) by writing two rows, not by
mutating one. The append-only shape mirrors the "tamper-evident audit
trail" requirement in plan §15 / NFR Compliance — a deletion can never
clear its own audit trail because the audit row is written *before* the
deletion completes (and the post-completion row references the same
``user_id`` from outside the deleted user document).

Retention: indefinite at MVP — the per-row ``requested_at`` field is
indexed, but no MongoDB TTL is configured. A future ops follow-up will
configure a 7-year TTL once the legal team confirms the retention
window. The index is shaped so a TTL can be slapped on later without a
schema migration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class GdprAuditAction(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """The action being audited.

    Values are stable wire identifiers — never rename without a
    migration on existing rows (rare; this collection is append-only).
    """

    EXPORT_REQUESTED = "export_requested"
    EXPORT_COMPLETED = "export_completed"
    DELETION_SCHEDULED = "deletion_scheduled"
    DELETION_COMPLETED = "deletion_completed"
    DELETION_CANCELED = "deletion_canceled"


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory shared by every default_factory."""
    return datetime.now(UTC)


class GdprAuditLog(Document):
    """Append-only audit row for a GDPR event.

    ``completed_at`` distinguishes the "intent" rows (export_requested,
    deletion_scheduled) from "outcome" rows (export_completed,
    deletion_completed, deletion_canceled). A pair of (requested →
    completed) rows is the canonical paper trail for any GDPR action;
    the helper at :func:`auxd_api.lib.audit.record_gdpr_event` always
    writes ONE row per call — pairing happens at the call site
    (request → completion are two separate calls).
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so
    # IDs are chronologically sortable (matches the sibling collections).
    # The mypy ``[assignment]`` mismatch with Document.id is a known and
    # accepted pattern.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str
    action: GdprAuditAction
    requested_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    notes: str | None = None  # "export size: 412 KB", "5 collections, 38 rows", etc.

    class Settings:
        name = "gdpr_audit_logs"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            # Primary read path: "what's the audit history for this user?".
            IndexModel([("user_id", ASCENDING), ("requested_at", DESCENDING)]),
            # 7-year TTL is deferred to ops — the index is shaped to host one
            # later without a schema migration.
            IndexModel([("requested_at", ASCENDING)]),
        ]


__all__ = [
    "GdprAuditAction",
    "GdprAuditLog",
]
