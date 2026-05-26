"""AOTY (Album of the Year) yearly top-50 scraper.

Pulls albumoftheyear.org's curated yearly summary list, which
aggregates dozens of critic year-end lists into a single ranking.
Covering 2000–present at ~50 entries per year gives ~1,250 albums
of contemporary critical canon — strong on the recency Pitchfork's
Best-of-Decade lists are too cyclic to deliver.

URL pattern
===========
``https://www.albumoftheyear.org/list/summary/{YEAR}/``

Each entry on the page lives in a ``.listSummaryRow`` block::

    <div class="listSummaryRow">
      <div class="listSummaryRank">1</div>
      …
      <h2 class="albumTitle listSummary"><a>Album</a></h2>
      <h3 class="artistTitle listSummary"><a>Artist</a></h3>
      …
    </div>

The CSS classes are stable — they're load-bearing in AOTY's own
front-end + multiple third-party scrapers depend on them.

Rate limit
==========
AOTY is generous to scrapers but the :func:`polite_get` helper still
enforces 1 req/sec — pulling 25+ years takes ~30s.

Last verified: 2026-05-25.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
# See ``scripts/generate_seed_csvs.py`` for the same pattern + rationale.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

import httpx  # noqa: E402 — must follow sys.path bootstrap

from scripts.seed_sources._common import (  # noqa: E402 — must follow sys.path bootstrap
    SeedEntry,
    parse_html,
    polite_get,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.aoty_yearly")

_URL_TEMPLATE: Final[str] = "https://www.albumoftheyear.org/list/summary/{year}/"

# AOTY's archive starts 1960 but the editorial coverage is thin
# pre-2000. Default span is 2000-now; the caller can widen via
# ``--start`` / ``--end``.
_DEFAULT_START_YEAR: Final[int] = 2000


def _current_year() -> int:
    """Indirection so tests can monkeypatch without importing datetime."""
    from datetime import datetime

    return datetime.now().year


def fetch_year(year: int) -> list[SeedEntry]:
    """Scrape one year's top-50 list. Returns [] on 4xx/5xx/network.

    Catches every transport-layer error so one bad year (publisher
    404, transient bot-gate trip past all retries, malformed page)
    doesn't abort the multi-year sweep — the calling
    :func:`fetch_entries` just records an empty list for that year
    and moves on.
    """
    url = _URL_TEMPLATE.format(year=year)
    try:
        response = polite_get(url)
    except (RuntimeError, httpx.HTTPError) as exc:
        _LOGGER.warning(
            "aoty_yearly.year_failed",
            extra={
                "event": "aoty_yearly.year_failed",
                "year": year,
                "error": repr(exc),
            },
        )
        return []

    tree = parse_html(response.text)
    rows = tree.css(".listSummaryRow")
    entries: list[SeedEntry] = []
    for row in rows:
        rank_node = row.css_first(".listSummaryRank")
        title_node = row.css_first(".albumTitle.listSummary a")
        artist_node = row.css_first(".artistTitle.listSummary a")
        if not title_node or not artist_node:
            continue
        rank_text = rank_node.text(strip=True) if rank_node else ""
        rank = int(rank_text) if rank_text.isdigit() else None
        entries.append(
            SeedEntry(
                artist=artist_node.text(strip=True),
                title=title_node.text(strip=True),
                year=year,
                source_rank=rank,
            )
        )
    return entries


def fetch_entries(start_year: int, end_year: int) -> list[SeedEntry]:
    """Walk the year range and accumulate every entry into one list.

    Source ranks are 1-50 per year — duplicate ranks across years
    are expected (this enumeration isn't unique across the whole
    dataset; year + rank is the composite key).
    """
    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")
    all_entries: list[SeedEntry] = []
    for year in range(start_year, end_year + 1):
        entries = fetch_year(year)
        _LOGGER.info(
            "aoty_yearly.year_done",
            extra={
                "event": "aoty_yearly.year_done",
                "year": year,
                "entries": len(entries),
            },
        )
        all_entries.extend(entries)
    return all_entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape AOTY yearly top-50 lists into a single seed CSV."
    )
    parser.add_argument(
        "--start",
        type=int,
        default=_DEFAULT_START_YEAR,
        help="First year to fetch (default: 2000).",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=_current_year(),
        help="Last year to fetch (default: current year).",
    )
    args = parser.parse_args()
    entries = fetch_entries(args.start, args.end)
    path = write_csv(entries, "aoty_yearly.csv")
    print(f"wrote {len(entries)} entries → {path}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
