"""Per-source seed-list loaders.

Each source exposes ``fetch_entries() -> list[AlbumSeedEntry]`` and
registers itself in :data:`SOURCES` so the CLI runner + quarterly
cron can discover it by name. The convention is to keep raw list
data as a CSV under ``apps/api/data/seed_lists/{source_name}.csv``
(two columns: ``artist,title`` plus optional ``year``,
``source_rank``) and have the Python module just parse + register.

This keeps the engineering surface tiny — adding a new source to
Bundle Y means:

1. Drop the CSV in ``apps/api/data/seed_lists/{name}.csv``
2. Add a one-liner registration in this module's ``SOURCES`` dict
   pointing at :func:`load_from_csv`

No per-site scraper, no schema migration. The list maintainer can
swap in a richer CSV at any time without touching code.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

from auxd_api.modules.catalog_seed.service import AlbumSeedEntry

# Data directory lives alongside the API package (apps/api/data/), not
# inside the src/ tree. Resolve relative to this file so the loader
# works regardless of cwd (CLI runner vs. arq worker have different
# working directories).
#
# parents[0]=sources/  [1]=catalog_seed/  [2]=modules/  [3]=auxd_api/
# parents[4]=src/      [5]=api/  ← target ancestor; data/ sits here.
_DATA_DIR = Path(__file__).resolve().parents[5] / "data" / "seed_lists"


def load_from_csv(filename: str) -> Callable[[], list[AlbumSeedEntry]]:
    """Return a loader closure that parses ``data/seed_lists/{filename}``.

    Closure deferral keeps the file I/O lazy — :data:`SOURCES` is
    imported at app-startup time, and we don't want module import to
    fail if a CSV is temporarily missing. Errors surface when the
    runner actually invokes the loader.

    Expected CSV layout (header row required)::

        artist,title,year,source_rank
        Lauryn Hill,The Miseducation Of Lauryn Hill,1998,1
        Outkast,Speakerboxxx / The Love Below,2003,2

    Year and source_rank are optional; leave blank when unknown.
    """

    def loader() -> list[AlbumSeedEntry]:
        path = _DATA_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"catalog_seed source CSV missing: {path} — "
                "drop the file in apps/api/data/seed_lists/ to enable this source."
            )
        entries: list[AlbumSeedEntry] = []
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                artist = (row.get("artist") or "").strip()
                title = (row.get("title") or "").strip()
                if not artist or not title:
                    continue
                year_raw = (row.get("year") or "").strip()
                rank_raw = (row.get("source_rank") or "").strip()
                entries.append(
                    AlbumSeedEntry(
                        artist=artist,
                        title=title,
                        year_hint=int(year_raw) if year_raw.isdigit() else None,
                        source_rank=int(rank_raw) if rank_raw.isdigit() else None,
                    )
                )
        return entries

    return loader


# ---------------------------------------------------------------------------
# Bundle Y registry
# ---------------------------------------------------------------------------

# Each source is registered as ``name -> loader_fn``. Adding a new
# source = drop CSV under data/seed_lists/, append a line here. The
# CLI runner ``scripts/seed_catalog.py`` and the quarterly cron both
# read from this dict.
#
# Bundle Y status (003 / 2026-05-25):
#
#   ✅ grammy_aoty           — auto-scraped (~370 entries; Wikipedia)
#   ✅ pitchfork_2000s       — auto-scraped (~200 entries)
#   ✅ pitchfork_2010s       — auto-scraped (~200 entries)
#   ✅ aoty_yearly           — auto-scraped (~50/year × range, default 2007-now)
#   ✅ rolling_stone_500     — auto-fetched from community CSV mirror (~500)
#   ✅ bea_top_3000          — auto-scraped (~3000, ~10min run; --top N to widen)
#   ⬜ pitchfork_2020s       — N/A (Pitchfork hasn't published the decade
#                              rollup yet; aoty_yearly covers post-2020)
#   ⬜ jazz_canon            — manual CSV (DownBeat + All About Jazz)
#   ⬜ electronic_canon      — manual CSV (RA Top 100 + FACT)
#   ⬜ hiphop_canon          — manual CSV (Complex + The Source)
#   ⬜ metal_canon           — manual CSV (Decibel Hall of Fame — their
#                              official page is JS-rendered; no clean scrape)
#   ⬜ country_canon         — manual CSV (RS Greatest Country)
#   ⬜ classical_canon       — manual CSV (Gramophone Hall of Fame)
#
# To regenerate the ✅ rows::
#     uv run --extra seed-scripts python scripts/generate_seed_csvs.py --all
#
# To enable any of the ⬜ rows: drop the CSV in apps/api/data/seed_lists/
# under the matching filename and flip the registration here from
# commented-out to active.
SOURCES: dict[str, Callable[[], list[AlbumSeedEntry]]] = {
    "grammy_aoty": load_from_csv("grammy_aoty.csv"),
    "pitchfork_2000s": load_from_csv("pitchfork_2000s.csv"),
    "pitchfork_2010s": load_from_csv("pitchfork_2010s.csv"),
    "aoty_yearly": load_from_csv("aoty_yearly.csv"),
    "rolling_stone_500": load_from_csv("rolling_stone_500.csv"),
    "bea_top_3000": load_from_csv("bea_top_3000.csv"),
    # "pitchfork_2020s": load_from_csv("pitchfork_2020s.csv"),
    # "jazz_canon": load_from_csv("jazz_canon.csv"),
    # "electronic_canon": load_from_csv("electronic_canon.csv"),
    # "hiphop_canon": load_from_csv("hiphop_canon.csv"),
    # "metal_canon": load_from_csv("metal_canon.csv"),
    # "country_canon": load_from_csv("country_canon.csv"),
    # "classical_canon": load_from_csv("classical_canon.csv"),
}


__all__ = ["SOURCES", "load_from_csv"]
