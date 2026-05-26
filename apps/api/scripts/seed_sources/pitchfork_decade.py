"""Pitchfork "Best Albums of the {decade}" scraper.

Pitchfork ships the full list page as SSR HTML with the entire
article body duplicated into a JSON-LD ``NewsArticle`` script tag.
That's the structured surface we parse against — much more stable
than the visible HTML markup, which gets re-skinned every couple of
years.

Each entry in the article body looks like::

    N.
    Artist: Album Title (YYYY)
    [paragraphs of review text]
    Listen/Buy: …

A flat regex against this format pulls all 200 entries cleanly. The
parser was validated against the 2010s list (199/200 entries matched
on first run; the one drop was a multi-artist entry with non-standard
punctuation that the regex would now catch with the slash-tolerant
artist class).

URLs (Bundle Y):

* 2000s: https://pitchfork.com/features/lists-and-guides/7702-the-top-200-albums-of-the-2000s/
* 2010s: https://pitchfork.com/features/lists-and-guides/the-200-best-albums-of-the-2010s/

Last verified: 2026-05-25.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Final

# Bootstrap sys.path so direct invocation (``python scripts/seed_sources/
# pitchfork_decade.py 2010s``) finds the ``scripts`` package. See
# ``scripts/generate_seed_csvs.py`` for the same pattern + rationale.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.seed_sources._common import (  # noqa: E402 — must follow sys.path bootstrap
    SeedEntry,
    parse_html,
    polite_get,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.pitchfork_decade")

# Map decade label to source URL. New decade pages land here when
# Pitchfork publishes them (next likely: a 2020s rollup around 2029).
#
# 2000s coverage caveat: Pitchfork originally split the 2000s list
# across multiple paginated pages (200-181 through 20-1) but has
# since taken the inner pages down — only the top-20 page is still
# served. We capture what's still live; the rest needs to come from
# another source (archive.org, BEA, AOTY yearly).
URLS: Final[dict[str, str]] = {
    "2000s": "https://pitchfork.com/features/lists-and-guides/7710-the-top-200-albums-of-the-2000s-20-1/",
    "2010s": "https://pitchfork.com/features/lists-and-guides/the-200-best-albums-of-the-2010s/",
}

# Pattern matches the canonical entry shape in the JSON-LD body:
#   "\nN.\nArtist: Title (YYYY)\n"
#
# Rank captured as 1-3 digit int; artist as a slash-tolerant
# non-newline / non-colon run (handles "Artist1 / Artist2"); title as
# the remainder up to the trailing year-in-parens. Year is exactly
# 4 digits.
_ENTRY_RE = re.compile(r"\n(\d{1,3})\.\n([^\n:]+?): ([^\n]+?) \((\d{4})\)\n")


def _extract_article_body(html: str) -> str:
    """Return the ``articleBody`` text from the page's NewsArticle JSON-LD.

    Pitchfork ships TWO JSON-LD scripts on each list page — a
    NewsArticle (the one we want, ~220KB) and a BreadcrumbList (~400
    bytes). We filter by type rather than ordinal so a future
    additional script doesn't shift the index out from under us.
    """
    tree = parse_html(html)
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=False)
        if not raw or '"NewsArticle"' not in raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            _LOGGER.warning(
                "pitchfork_decade.json_parse_failed",
                extra={
                    "event": "pitchfork_decade.json_parse_failed",
                    "error": repr(exc),
                },
            )
            continue
        body = payload.get("articleBody")
        if isinstance(body, str) and body:
            return body
    raise RuntimeError("Pitchfork page missing NewsArticle JSON-LD with articleBody")


def fetch_entries(decade: str) -> list[SeedEntry]:
    """Scrape the 200-entry list for ``decade`` (e.g. ``"2010s"``).

    Returns entries sorted by source_rank ascending (#1 first). The
    caller writes the CSV — :func:`write_csv` is the persistence
    half; :func:`fetch_entries` is the pure-fetch half.
    """
    if decade not in URLS:
        raise ValueError(f"unknown decade {decade!r}; supported: {sorted(URLS)}")
    response = polite_get(URLS[decade])
    body = _extract_article_body(response.text)
    matches = _ENTRY_RE.findall(body)
    entries = [
        SeedEntry(
            artist=artist.strip(),
            title=title.strip(),
            year=int(year),
            source_rank=int(rank),
        )
        for rank, artist, title, year in matches
    ]
    # Sort ascending by rank so the CSV reads #1 → #200.
    entries.sort(key=lambda e: e.source_rank or 1_000_000)
    _LOGGER.info(
        "pitchfork_decade.fetched",
        extra={
            "event": "pitchfork_decade.fetched",
            "decade": decade,
            "entries": len(entries),
        },
    )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Pitchfork's Best Albums of the {decade} into a seed CSV."
    )
    parser.add_argument(
        "decade",
        choices=sorted(URLS),
        help="Which decade list to fetch.",
    )
    args = parser.parse_args()
    entries = fetch_entries(args.decade)
    path = write_csv(entries, f"pitchfork_{args.decade}.csv")
    print(f"wrote {len(entries)} entries → {path}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
