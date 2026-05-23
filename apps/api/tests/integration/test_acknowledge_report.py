"""Integration tests for the N-012 report-acknowledge flow (T157).

Exercises :func:`auxd_api.modules.reports.service.acknowledge_report`:

* Marks ``Report.acknowledged_at = now``.
* Dispatches N-012 to the original reporter (monkeypatched dispatcher).
* Idempotent: a second call is a no-op + no double-dispatch.
* Anonymous reporter (catalog-gap path with ``reporter_id=None``) still
  marks the row but skips the dispatch.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.reports import service as service_module
from auxd_api.modules.reports.service import acknowledge_report


@pytest_asyncio.fixture
async def _clean_reports() -> AsyncIterator[None]:
    await Report.delete_all()
    yield
    await Report.delete_all()


@pytest.fixture
def _capture_dispatch(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture every dispatcher call from the service module."""
    calls: list[dict[str, Any]] = []

    async def _fake_dispatch(
        *,
        user_id: str,
        type: NotificationType,  # noqa: A002 — match real signature
        payload: dict[str, Any],
        actor_id: str | None = None,
        follow_source: str | None = None,
    ) -> None:
        _ = follow_source
        calls.append(
            {
                "user_id": user_id,
                "type": type,
                "payload": payload,
                "actor_id": actor_id,
            }
        )
        return None

    monkeypatch.setattr(service_module, "dispatch_notification", _fake_dispatch)
    return calls


def _make_report(reporter_id: str | None = "user-reporter") -> Report:
    return Report(
        reporter_id=reporter_id,
        target_type=ReportTargetType.USER,
        target_id="user-target",
        reason=ReportReason.HARASSMENT,
        detail="bad behaviour",
        status=ReportStatus.OPEN,
    )


@pytest.mark.asyncio
async def test_acknowledge_sets_timestamp_and_dispatches_n012(
    _clean_reports: None, _capture_dispatch: list[dict[str, Any]]
) -> None:
    report = _make_report()
    await report.insert()

    result = await acknowledge_report(report.id)
    assert result.acknowledged_at is not None
    persisted = await Report.get(report.id)
    assert persisted is not None
    assert persisted.acknowledged_at is not None

    assert len(_capture_dispatch) == 1
    call = _capture_dispatch[0]
    assert call["user_id"] == "user-reporter"
    assert call["type"] is NotificationType.N012_REPORT_ACKNOWLEDGED
    assert call["payload"]["report_id"] == report.id


@pytest.mark.asyncio
async def test_acknowledge_includes_optional_ack_note_in_payload(
    _clean_reports: None, _capture_dispatch: list[dict[str, Any]]
) -> None:
    report = _make_report()
    await report.insert()

    await acknowledge_report(report.id, ack_note="Reviewed — no action taken.")
    assert _capture_dispatch[0]["payload"]["ack_note"] == "Reviewed — no action taken."


@pytest.mark.asyncio
async def test_acknowledge_is_idempotent(
    _clean_reports: None, _capture_dispatch: list[dict[str, Any]]
) -> None:
    report = _make_report()
    await report.insert()

    first = await acknowledge_report(report.id)
    first_ts = first.acknowledged_at
    assert first_ts is not None

    second = await acknowledge_report(report.id)
    assert second.acknowledged_at == first_ts  # timestamp did not drift

    # No double dispatch.
    assert len(_capture_dispatch) == 1


@pytest.mark.asyncio
async def test_acknowledge_anonymous_reporter_skips_dispatch(
    _clean_reports: None, _capture_dispatch: list[dict[str, Any]]
) -> None:
    """Catalog-gap reports have ``reporter_id=None`` — no one to notify."""
    report = _make_report(reporter_id=None)
    await report.insert()

    result = await acknowledge_report(report.id)
    assert result.acknowledged_at is not None  # row still marked
    assert _capture_dispatch == []  # but no dispatch fired
