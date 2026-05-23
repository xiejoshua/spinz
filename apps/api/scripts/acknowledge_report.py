"""CLI: acknowledge a moderation report (T157).

Usage::

    uv run python apps/api/scripts/acknowledge_report.py <report_id> [--note "..."]

The founder runs this from an ops shell to flip a report's
``acknowledged_at`` and fire ``N-012 report.acknowledged`` to the
original reporter. There is no HTTP endpoint at MVP — a future admin UI
will wrap the same :func:`acknowledge_report` service call.

Exits with status 0 on success, 1 on any error (report not found,
already acknowledged, DB unavailable). The error message is printed to
stderr so it stays separable from any logging the service emits to
stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from auxd_api.db import close_db, init_db
from auxd_api.modules.reports.service import (
    TargetNotFoundError,
    acknowledge_report,
)
from auxd_api.settings import get_settings


async def _amain(report_id: str, ack_note: str | None) -> int:
    settings = get_settings()
    await init_db(settings.MONGODB_URI)
    try:
        report = await acknowledge_report(report_id, ack_note=ack_note)
    except TargetNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_db()
    print(f"acknowledged report {report.id} at {report.acknowledged_at!s}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Acknowledge a moderation report (T157).")
    parser.add_argument("report_id", help="KSUID of the Report to acknowledge.")
    parser.add_argument(
        "--note",
        dest="ack_note",
        default=None,
        help="Optional short note included on the N-012 payload.",
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args.report_id, args.ack_note))


if __name__ == "__main__":  # pragma: no cover — invoked from the CLI only.
    raise SystemExit(main())
