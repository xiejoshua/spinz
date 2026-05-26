"""Grammy Album of the Year scraper — Wikipedia (full nominees).

Replaces the hand-curated 157-entry sampler in
``data/seed_lists/grammy_aoty.csv`` with the full ~340-entry
nominee list scraped from Wikipedia's
``Grammy_Award_for_Album_of_the_Year`` article.

Page structure
==============
The article carries one stats table (artists by win-count) followed
by 8 per-decade tables. Each per-decade table layout::

    | Year (rowspan=5)         | Album    | Artist |
    |                          | Album    | Artist |
    | (winner row tinted gold) | …        | …      |

The winner row is rendered with ``<i><b>...</b></i>`` markup and a
yellow row background; nominee rows are italics only. We capture
every row (winner + 4 nominees) since all are canon-worthy for the
catalog.

Last verified: 2026-05-25.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Final

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
# See ``scripts/generate_seed_csvs.py`` for the same pattern + rationale.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.seed_sources._common import (  # noqa: E402 — must follow sys.path bootstrap
    SeedEntry,
    parse_html,
    polite_get,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.wikipedia_grammy_aoty")

_URL: Final[str] = "https://en.wikipedia.org/wiki/Grammy_Award_for_Album_of_the_Year"

# Pull a leading 4-digit year out of a year cell. Wikipedia decorates
# year cells with footnote refs (``1959[20]``) and sometimes a <br/>
# followed by a reference; the leading-digit anchor handles all of it.
_YEAR_RE = re.compile(r"(\d{4})")


# Skip the first wikitable (artist stats by win-count). The per-decade
# ceremony tables have a "Year" column and rowspan'd year cells; the
# stats table has columns like "Artist/Band" / "Number of Victories".
def _is_ceremony_table(table) -> bool:
    """True when the table is structured as the per-decade ceremony grid.

    Heuristic: the first ``<th>`` cell in the table's header reads
    ``"Year"`` (possibly with a footnote suffix). The stats table
    leads with ``"Artist/Band"`` so it falls out of the filter.
    """
    first_th = table.css_first("th")
    if first_th is None:
        return False
    return first_th.text(strip=True).lower().startswith("year")


def fetch_entries() -> list[SeedEntry]:
    """Scrape Grammy AOTY winners + nominees, 1959 → present.

    Output ordering: oldest ceremony first (1959 album wins at rank 1,
    1959 nominees at ranks 2-5, then 1960 ceremony at ranks 6-10, etc.).
    ``source_rank`` is therefore a stable enumeration across ceremonies
    rather than a per-ceremony placement — the catalog ingest doesn't
    use ranks semantically; they're just diagnostic.
    """
    response = polite_get(_URL)
    tree = parse_html(response.text)
    entries: list[SeedEntry] = []
    current_year: int | None = None
    rank = 1

    for table in tree.css("table.wikitable"):
        if not _is_ceremony_table(table):
            continue
        for row in table.css("tr"):
            # The winner row carries a rowspan'd <th> with the ceremony
            # year; nominee rows only have <td> cells.
            year_cell = row.css_first("th[rowspan]")
            if year_cell is not None:
                year_match = _YEAR_RE.search(year_cell.text(strip=True))
                if year_match:
                    current_year = int(year_match.group(1))

            cells = row.css("td")
            if len(cells) < 2:
                continue

            album_text = cells[0].text(strip=True)
            artist_text = cells[1].text(strip=True)
            if not album_text or not artist_text:
                continue

            entries.append(
                SeedEntry(
                    artist=artist_text,
                    title=album_text,
                    year=current_year,
                    source_rank=rank,
                )
            )
            rank += 1

    _LOGGER.info(
        "wikipedia_grammy_aoty.fetched",
        extra={
            "event": "wikipedia_grammy_aoty.fetched",
            "entries": len(entries),
        },
    )
    return entries


def main() -> int:
    entries = fetch_entries()
    path = write_csv(entries, "grammy_aoty.csv")
    print(f"wrote {len(entries)} entries → {path}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
