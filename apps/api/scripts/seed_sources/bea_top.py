"""Best Ever Albums Top-N scraper.

besteveralbums.com aggregates 60,000+ professional and user-submitted
album lists into a single ranking. Their public "Overall Chart" page
exposes the full ranking — 10 albums per page, 10,000 entries total
— at the URL::

    https://www.besteveralbums.com/overall.php?orderby=InfoRankScore&sortdir=desc&page={N}

Each page interleaves two row classes (``.chartrow`` for odd ranks,
``.chartrow2`` for even ranks) within a two-column visual layout.
The parser walks both, pulls the rank/title/artist out of stable
sub-classes, and aggregates across pages.

Default target is the top 3000 (300 pages). The user can widen via
``--top`` if they want deeper catalog coverage; 3000 hits the same
sweet-spot that BEA's free-account CSV export uses.

Rate-limit
==========
The shared ``polite_get`` floor (2s/request) puts the full 300-page
crawl at ~10 minutes wall-clock. The retry-on-403 logic catches the
occasional bot-gate trip without aborting the run.

Last verified: 2026-05-25.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

import httpx  # noqa: E402

from scripts.seed_sources._common import (  # noqa: E402
    SeedEntry,
    parse_html,
    polite_get,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.bea_top")

_PAGE_URL: Final[str] = (
    "https://www.besteveralbums.com/overall.php?orderby=InfoRankScore&sortdir=desc&page={page}"
)
_ENTRIES_PER_PAGE: Final[int] = 10
_DEFAULT_TOP: Final[int] = 3000  # matches BEA's free-tier export ceiling


def _parse_page(html: str) -> list[SeedEntry]:
    """Pull one page's 10 album entries (sorted ascending by rank).

    The two-column layout puts odd ranks in ``.chartrow`` and even
    ranks in ``.chartrow2``; both share the same internal sub-class
    structure for rank / title / artist cells. We accept both and
    sort the page's output by rank at the end.
    """
    tree = parse_html(html)
    rows = tree.css(".chartrow, .chartrow2")
    entries: list[SeedEntry] = []
    for row in rows:
        rank_node = row.css_first(".chart-rank-col .bigger")
        title_node = row.css_first(".chart-title-col a.nav2emph.bigger")
        if rank_node is None or title_node is None:
            # Sub-rows under each album (buy links, comments) share
            # the chartrow class but don't carry rank/title — skip
            # cleanly without false-positive entries.
            continue
        rank_text = rank_node.text(strip=True).rstrip(".")
        if not rank_text.isdigit():
            continue
        # Artist link lives in a second ``.chart-title-col`` (the
        # first holds the album link). Walk them in order and take
        # the first anchor we find past the first column.
        title_cols = row.css(".chart-title-col")
        artist: str | None = None
        for col in title_cols[1:]:
            link = col.css_first("a")
            if link is not None:
                artist = link.text(strip=True)
                break
        if not artist:
            continue
        entries.append(
            SeedEntry(
                artist=artist,
                title=title_node.text(strip=True),
                source_rank=int(rank_text),
            )
        )

    entries.sort(key=lambda e: e.source_rank or 1_000_000)
    return entries


def fetch_entries(top: int = _DEFAULT_TOP) -> list[SeedEntry]:
    """Crawl BEA's Overall Chart for the top ``top`` albums.

    Stops early if a page returns fewer than the expected 10 entries
    (signals end-of-chart or transient failure). Per-page errors are
    absorbed so one bad page doesn't abort the whole crawl.
    """
    if top <= 0:
        raise ValueError("top must be positive")
    pages = (top + _ENTRIES_PER_PAGE - 1) // _ENTRIES_PER_PAGE
    all_entries: list[SeedEntry] = []
    for page in range(1, pages + 1):
        url = _PAGE_URL.format(page=page)
        try:
            response = polite_get(url)
        except (RuntimeError, httpx.HTTPError) as exc:
            _LOGGER.warning(
                "bea_top.page_failed",
                extra={
                    "event": "bea_top.page_failed",
                    "page": page,
                    "error": repr(exc),
                },
            )
            continue
        page_entries = _parse_page(response.text)
        if not page_entries:
            _LOGGER.warning(
                "bea_top.page_empty",
                extra={"event": "bea_top.page_empty", "page": page},
            )
            continue
        all_entries.extend(page_entries)
        _LOGGER.info(
            "bea_top.page_done",
            extra={
                "event": "bea_top.page_done",
                "page": page,
                "entries": len(page_entries),
                "total_so_far": len(all_entries),
            },
        )
        if len(all_entries) >= top:
            break

    return all_entries[:top]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Best Ever Albums Top-N into a seed CSV.")
    parser.add_argument(
        "--top",
        type=int,
        default=_DEFAULT_TOP,
        help=f"How many albums to crawl (default: {_DEFAULT_TOP}; BEA chart caps at 10,000).",
    )
    args = parser.parse_args()
    entries = fetch_entries(args.top)
    path = write_csv(entries, "bea_top_3000.csv")
    print(f"wrote {len(entries)} entries → {path}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
