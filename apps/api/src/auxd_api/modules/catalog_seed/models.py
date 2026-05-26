"""Beanie documents for the catalog seed pipeline.

A :class:`SeedRun` row is created when the ingest worker (or the CLI
runner) starts a pass against a named source list. Counters are
incremented in-place as entries flow through resolution, and the
``status`` flips to ``completed`` / ``failed`` at the end. The last
50 error messages are retained for diagnostic — anything older rotates
out so the document doesn't bloat indefinitely on a long-running pass.

Rationale for keeping this as a first-class document rather than a
log line: the founder needs to see "how full is the catalog" + "did
the quarterly cron actually run", and both are dashboard-friendly
queries against this collection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class SeedRunStatus(StrEnum):
    """Lifecycle state of a :class:`SeedRun` row."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SeedRun(Document):
    """One execution of the catalog-seed ingest pipeline.

    Created at startup, mutated in-place as entries are processed, and
    flipped to :attr:`SeedRunStatus.COMPLETED` once the source is
    exhausted. ``status`` stays as :attr:`SeedRunStatus.RUNNING`
    indefinitely if the worker dies mid-pass — the dashboard can flag
    stuck runs via a "running for > 24h" query.
    """

    _schema_version: int = 1

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]

    source_name: str = Field(
        ...,
        description=(
            "Canonical name of the source list (e.g. ``grammy_aoty``, "
            "``rolling_stone_500``). Matches the key registered in "
            ":mod:`auxd_api.modules.catalog_seed.sources`."
        ),
    )
    status: SeedRunStatus = SeedRunStatus.RUNNING

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    entries_attempted: int = 0
    entries_succeeded: int = 0
    """Resolved + materialised into the local catalog (includes already-cached)."""

    entries_failed: int = 0
    """Provider returned nothing or raised an error."""

    entries_skipped: int = 0
    """Resolved but already in the local catalog (no work needed)."""

    error_log: list[str] = Field(default_factory=list)
    """Last 50 errors (entries beyond that get truncated by the service layer)."""

    class Settings:
        """Beanie collection settings.

        ``(source_name, started_at DESC)`` supports the "most recent
        run for source X" query that the dashboard uses; the standalone
        ``status`` index drives "any stuck runs?" alerts.
        """

        name = "seed_runs"
        indexes: list[IndexModel] = [
            IndexModel([("source_name", ASCENDING), ("started_at", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ]


__all__ = ["SeedRun", "SeedRunStatus"]
