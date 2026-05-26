"""Rolling Stone 500 Greatest Albums (2020 revision) — community CSV mirror.

The Rolling Stone site itself bot-blocks scraping. The 2020-revision
canonical list lives in several community-maintained GitHub mirrors;
we pull from one of those instead. Currently sourcing
``AlexJHayward/500-greatest-albums-json`` (publicly archived
``greatest_500_albums.csv``) which carries all 500 entries plus
descriptions and cover URLs.

Note: the mirror's CSV has some mojibake on stylised quotes (curly
quotes encoded as ``â`` runs, plus an occasional ``\\ufeff`` BOM
artifact at the front of the title field). We normalise those down
to plain ASCII in :func:`_clean` so the downstream ``resolve_identity``
search has a clean query string to work with.

If this mirror goes stale, swap ``_SOURCE_URL`` to another of the
GitHub search results for "rolling-stone-500-csv". The schema we
expect is:

    rank, artist, title, title_artist, description, coverUrl

Only the first three columns are used.

Last verified: 2026-05-25.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Final

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

import httpx  # noqa: E402

from scripts.seed_sources._common import (  # noqa: E402
    SeedEntry,
    polite_get,
    write_csv,
)

_LOGGER = logging.getLogger("auxd.seed_sources.rolling_stone_500")

_SOURCE_URL: Final[str] = (
    "https://raw.githubusercontent.com/AlexJHayward/"
    "500-greatest-albums-json/main/greatest_500_albums.csv"
)

# Mojibake → ASCII map for the stylised quote runs the mirror's
# scraper emits. The fall-through ``unicodedata.normalize`` pass
# strips any residual decomposed accents so the search query stays
# clean.
_MOJIBAKE_QUOTES = {
    "‘": "",
    "’": "",
    "“": "",
    "”": "",
    "â\x80\x98": "",
    "â\x80\x99": "",
    "â\x80\x9c": "",
    "â\x80\x9d": "",
}


def _clean(value: str) -> str:
    """Normalise a CSV field for the search pipeline.

    Strips:
    * BOM (``\\ufeff`` proper + the ``ï»¿`` mojibake form some mirror
      rows carry when the BOM bytes were UTF-8-decoded as Latin-1)
    * Stylised curly quotes (typeset + mojibake variants)
    * Leading/trailing whitespace
    * Stray surrounding straight quotes ("\\"Foo\\"")
    """
    if not value:
        return value
    # Proper BOM character.
    value = value.replace("﻿", "")
    # Mojibake-encoded BOM (UTF-8 BOM bytes decoded as Latin-1).
    value = value.replace("ï»¿", "")
    for bad, good in _MOJIBAKE_QUOTES.items():
        value = value.replace(bad, good)
    value = unicodedata.normalize("NFKC", value)
    value = value.strip().strip('"').strip("'")
    # Collapse runs of whitespace introduced by inline newlines in
    # the mirror's CSV.
    return re.sub(r"\s+", " ", value)


def fetch_entries() -> list[SeedEntry]:
    """Download the mirror CSV and yield SeedEntry rows sorted by rank.

    The mirror file is ~420 KB; one shot suffices. Returns up to 500
    entries sorted ascending by rank (#1 first).

    The mirror's header row carries a leading space on every column
    name (``"rank, artist, title, …"``), which would silently kill
    a naive ``row.get("artist")`` lookup. The DictReader is wrapped
    in a key-normalising step to strip those.
    """
    response = polite_get(_SOURCE_URL)
    reader = csv.DictReader(io.StringIO(response.text))
    entries: list[SeedEntry] = []
    for raw_row in reader:
        # Normalise column keys — the mirror's header is
        # ``"rank, artist, title, …"`` with leading spaces.
        row = {(k or "").strip().lower(): v for k, v in raw_row.items()}

        rank_raw = (row.get("rank") or "").strip()
        artist = _clean(row.get("artist") or "")
        title = _clean(row.get("title") or "")
        if not artist or not title:
            continue
        rank = int(rank_raw) if rank_raw.isdigit() else None
        entries.append(SeedEntry(artist=artist, title=title, source_rank=rank))

    entries.sort(key=lambda e: e.source_rank or 1_000_000)
    _LOGGER.info(
        "rolling_stone_500.fetched",
        extra={"event": "rolling_stone_500.fetched", "entries": len(entries)},
    )
    return entries


def main() -> int:
    try:
        entries = fetch_entries()
    except httpx.HTTPError as exc:
        sys.stderr.write(f"failed to fetch RS500 mirror: {exc!r}\n")
        return 1
    path = write_csv(entries, "rolling_stone_500.csv")
    print(f"wrote {len(entries)} entries → {path}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
