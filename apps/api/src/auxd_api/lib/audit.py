"""GDPR audit-event helper (T154).

Tiny wrapper around :class:`auxd_api.modules.gdpr.models.GdprAuditLog`
so callers don't construct Document instances by hand. The single
:func:`record_gdpr_event` entry point sets ``completed_at`` correctly
for both halves of a request-pair (requested → completed) and writes
the row with a consistent observability footprint.

Usage:

    >>> await record_gdpr_event(user_id, GdprAuditAction.EXPORT_REQUESTED)
    >>> # ... do the work ...
    >>> await record_gdpr_event(
    ...     user_id,
    ...     GdprAuditAction.EXPORT_COMPLETED,
    ...     notes=f"size: {size_kb} KB",
    ...     completed=True,
    ... )

The helper never raises into the caller — a failing write logs the
error and returns ``None``. This is deliberate: a GDPR action should
still surface its primary outcome (export delivered, account deleted)
even if the audit ledger is temporarily unreachable. Persistent audit
failures should land as Sentry alerts via the structured log line.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from auxd_api.lib.observability import log_call
from auxd_api.modules.gdpr.models import GdprAuditAction, GdprAuditLog

_LOGGER = logging.getLogger("auxd.audit")


async def record_gdpr_event(
    user_id: str,
    action: GdprAuditAction,
    notes: str | None = None,
    *,
    completed: bool = False,
) -> GdprAuditLog | None:
    """Persist a single GDPR audit row.

    Args:
        user_id: Owner of the audited action.
        action: The :class:`GdprAuditAction` enum value.
        notes: Optional human-readable annotation (size in KB,
            collection counts, etc.). Kept short — this is an audit
            ledger, not a debug log.
        completed: When ``True``, sets ``completed_at`` to ``now``.
            Use for outcome rows (EXPORT_COMPLETED, DELETION_COMPLETED,
            DELETION_CANCELED); leave ``False`` for intent rows
            (EXPORT_REQUESTED, DELETION_SCHEDULED).

    Returns:
        The persisted :class:`GdprAuditLog` instance, or ``None`` if
        the write failed (the failure is logged + observable, but the
        caller should not depend on the row being present to make
        progress).
    """
    now = datetime.now(UTC)
    row = GdprAuditLog(
        user_id=user_id,
        action=action,
        requested_at=now,
        completed_at=now if completed else None,
        notes=notes,
    )
    try:
        await row.insert()
    except Exception as exc:  # noqa: BLE001 — defensive: never break the primary path
        _LOGGER.exception(
            "gdpr_audit.write_failed",
            extra={
                "event": "gdpr_audit.write_failed",
                "user_id": user_id,
                "action": action.value,
                "error": str(exc),
            },
        )
        return None
    log_call(
        provider="auxd",
        endpoint="gdpr.audit_recorded",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": user_id,
            "action": action.value,
            "audit_log_id": row.id,
            "completed": completed,
        },
    )
    return row


__all__ = ["record_gdpr_event"]
