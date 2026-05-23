"""Unit tests for :mod:`auxd_api.lib.audit` (T154).

Covers:

* ``record_gdpr_event`` writes one row per call with the right
  ``completed_at`` shape (None for intent rows, set for outcome rows).
* The EXPORT_REQUESTED → EXPORT_COMPLETED pattern produces a
  chronologically ordered pair of rows for the same user.
* Notes are persisted verbatim.
* A failing insert returns ``None`` rather than raising — the helper
  has a "never break the primary path" contract.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio

from auxd_api.lib import audit as audit_module
from auxd_api.lib.audit import record_gdpr_event
from auxd_api.modules.gdpr.models import GdprAuditAction, GdprAuditLog


@pytest_asyncio.fixture
async def _clean_audit() -> AsyncIterator[None]:
    await GdprAuditLog.delete_all()
    yield
    await GdprAuditLog.delete_all()


@pytest.mark.asyncio
async def test_record_gdpr_event_writes_intent_row(_clean_audit: None) -> None:
    row = await record_gdpr_event("user-123", GdprAuditAction.EXPORT_REQUESTED)
    assert row is not None
    assert row.user_id == "user-123"
    assert row.action is GdprAuditAction.EXPORT_REQUESTED
    assert row.completed_at is None  # intent row — no completion stamp yet.
    assert isinstance(row.requested_at, datetime)
    assert row.notes is None


@pytest.mark.asyncio
async def test_record_gdpr_event_writes_completed_row_with_notes(_clean_audit: None) -> None:
    row = await record_gdpr_event(
        "user-123",
        GdprAuditAction.DELETION_COMPLETED,
        notes="5 collections cascade-deleted, 42 rows",
        completed=True,
    )
    assert row is not None
    assert row.completed_at is not None  # outcome row.
    assert row.notes == "5 collections cascade-deleted, 42 rows"


@pytest.mark.asyncio
async def test_export_request_completion_pair_persists_in_order(_clean_audit: None) -> None:
    """The canonical EXPORT_REQUESTED → EXPORT_COMPLETED pair pattern."""
    await record_gdpr_event("user-pair", GdprAuditAction.EXPORT_REQUESTED)
    await record_gdpr_event(
        "user-pair",
        GdprAuditAction.EXPORT_COMPLETED,
        notes="json: 12 KB, zip: 34 KB",
        completed=True,
    )
    rows = (
        await GdprAuditLog.find(GdprAuditLog.user_id == "user-pair").sort("+requested_at").to_list()
    )
    assert len(rows) == 2
    assert rows[0].action is GdprAuditAction.EXPORT_REQUESTED
    assert rows[0].completed_at is None
    assert rows[1].action is GdprAuditAction.EXPORT_COMPLETED
    assert rows[1].completed_at is not None
    assert rows[1].notes == "json: 12 KB, zip: 34 KB"


@pytest.mark.asyncio
async def test_record_gdpr_event_swallows_write_errors(
    monkeypatch: pytest.MonkeyPatch, _clean_audit: None
) -> None:
    """A failing insert returns ``None``; the helper does not raise.

    The contract is "never break the primary path" — the export still
    delivers / the deletion still cascades even if the audit ledger is
    transiently unreachable. Persistent failures are observable via
    the structured log line.
    """

    class _BoomDocument:
        """Replacement for GdprAuditLog that explodes on insert."""

        def __init__(self, **_: object) -> None: ...

        async def insert(self) -> None:
            raise RuntimeError("Mongo unreachable")

    monkeypatch.setattr(audit_module, "GdprAuditLog", _BoomDocument)
    result = await record_gdpr_event("user-fail", GdprAuditAction.EXPORT_REQUESTED)
    assert result is None
