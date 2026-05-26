"""Meta-runner for the catalog-seed CSV generators.

Usage::

    # Generate one source
    uv run --extra seed-scripts python scripts/generate_seed_csvs.py grammy_aoty

    # Generate one source with sub-args
    uv run --extra seed-scripts python scripts/generate_seed_csvs.py pitchfork_decade --decade 2010s

    # Generate all available sources (skip-on-fail)
    uv run --extra seed-scripts python scripts/generate_seed_csvs.py --all

Each source module under ``scripts.seed_sources`` exposes a
``fetch_entries(*args)`` callable that returns ``list[SeedEntry]``.
The meta-runner dispatches by name, handles per-source CLI args, and
absorbs per-source failures so one broken site doesn't kill the
whole batch.

The ``--all`` mode is intended for the operator's quarterly refresh
pass: drop the new CSVs in ``apps/api/data/seed_lists/``, then run
``scripts/seed_catalog.py`` per source (or via the arq cron) to
ingest into the local catalog.

See ``data/seed_lists/README.md`` for the Bundle Y source matrix.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Bootstrap sys.path so ``scripts.seed_sources`` resolves whether the
# script is invoked as ``python scripts/generate_seed_csvs.py`` (the
# documented form) or via ``-m`` (the package form). Without this the
# direct-invocation form errors with ``No module named 'scripts'``.
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.seed_sources import (  # noqa: E402 — must follow sys.path bootstrap
    aoty_yearly,
    bea_top,
    pitchfork_decade,
    rolling_stone_500,
    wikipedia_grammy_aoty,
)
from scripts.seed_sources._common import (  # noqa: E402 — must follow sys.path bootstrap
    SeedEntry,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.runner")


def _run_grammy_aoty() -> tuple[list[SeedEntry], str]:
    return wikipedia_grammy_aoty.fetch_entries(), "grammy_aoty.csv"


def _run_pitchfork_decade(*, decade: str) -> tuple[list[SeedEntry], str]:
    return pitchfork_decade.fetch_entries(decade), f"pitchfork_{decade}.csv"


def _run_aoty_yearly(*, start: int = 2000, end: int | None = None) -> tuple[list[SeedEntry], str]:
    from datetime import datetime

    end_year = end if end is not None else datetime.now().year
    return aoty_yearly.fetch_entries(start, end_year), "aoty_yearly.csv"


def _run_rolling_stone_500() -> tuple[list[SeedEntry], str]:
    return rolling_stone_500.fetch_entries(), "rolling_stone_500.csv"


def _run_bea_top(*, top: int = 3000) -> tuple[list[SeedEntry], str]:
    return bea_top.fetch_entries(top=top), "bea_top_3000.csv"


# Registry: source name → (runner, default kwargs).
#
# ``--all`` iterates this dict and invokes each with its defaults.
# CLI sub-args (e.g. ``--decade 2010s``) only apply to the
# named-source flow; ``--all`` just runs the defaults to keep the
# batch shell-flag-free.
_DEFAULTS_2000S: dict[str, Any] = {"decade": "2000s"}
_DEFAULTS_2010S: dict[str, Any] = {"decade": "2010s"}

SOURCES: dict[str, tuple[Callable[..., tuple[list[SeedEntry], str]], dict[str, Any]]] = {
    "grammy_aoty": (_run_grammy_aoty, {}),
    "pitchfork_2000s": (_run_pitchfork_decade, _DEFAULTS_2000S),
    "pitchfork_2010s": (_run_pitchfork_decade, _DEFAULTS_2010S),
    "aoty_yearly": (_run_aoty_yearly, {}),
    "rolling_stone_500": (_run_rolling_stone_500, {}),
    "bea_top_3000": (_run_bea_top, {}),
}


def _run_one(name: str, **overrides: Any) -> int:
    """Invoke one source's runner; persist + report on success.

    Returns the number of entries written (0 on failure).
    """
    if name not in SOURCES:
        sys.stderr.write(f"unknown source: {name!r}\navailable: {sorted(SOURCES)}\n")
        return 0
    runner, defaults = SOURCES[name]
    kwargs = {**defaults, **overrides}
    try:
        entries, filename = runner(**kwargs)
    except Exception as exc:  # noqa: BLE001 — runner-level isolation
        _LOGGER.exception(
            "generate_seed_csvs.source_failed",
            extra={
                "event": "generate_seed_csvs.source_failed",
                "source": name,
                "error": repr(exc),
            },
        )
        sys.stderr.write(f"[{name}] FAILED: {exc!r}\n")
        return 0
    path = write_csv(entries, filename)
    print(f"[{name}] wrote {len(entries)} entries → {path}")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one or more catalog-seed CSVs.")
    parser.add_argument(
        "source",
        nargs="?",
        choices=sorted(SOURCES),
        help="Source name to scrape. Omit when using --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every registered source with its defaults, skip-on-fail.",
    )
    parser.add_argument(
        "--decade",
        choices=["2000s", "2010s"],
        help="Override the decade for the pitchfork_decade source.",
    )
    parser.add_argument(
        "--start",
        type=int,
        help="Override start year for the aoty_yearly source (default: 2000).",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="Override end year for the aoty_yearly source (default: current year).",
    )
    parser.add_argument(
        "--top",
        type=int,
        help="Override top-N depth for the bea_top_3000 source (default: 3000).",
    )
    args = parser.parse_args()

    if not args.all and not args.source:
        parser.error("specify a source name or pass --all")

    if args.all:
        total = 0
        for name in sorted(SOURCES):
            total += _run_one(name)
        print(f"\n=== ALL DONE: {total} total entries across registered sources ===")
        return 0

    overrides: dict[str, Any] = {}
    if args.decade is not None:
        overrides["decade"] = args.decade
    if args.start is not None:
        overrides["start"] = args.start
    if args.end is not None:
        overrides["end"] = args.end
    if args.top is not None:
        overrides["top"] = args.top
    count = _run_one(args.source, **overrides)
    return 0 if count else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
