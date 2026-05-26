# Catalog seed lists

This directory holds the raw CSVs that drive the curated catalog seed
(see `apps/api/src/auxd_api/modules/catalog_seed/`). Each file is a
flat CSV with the schema:

```csv
artist,title,year,source_rank
The Beatles,Sgt. Pepper's Lonely Hearts Club Band,1967,10
```

`year` and `source_rank` are optional. `artist` + `title` are
required and become the query string fed to the existing 3-tier
search pipeline (Atlas → Discogs masters → MusicBrainz), which
materialises each match into the local `albums` collection.

## Bundle Y status

| Source | File | Status | Entries |
|---|---|---|---|
| Grammy Album of the Year | `grammy_aoty.csv` | ✅ auto-scraped | 371 |
| Pitchfork Best of the 2000s | `pitchfork_2000s.csv` | ✅ auto-scraped | 198 |
| Pitchfork Best of the 2010s | `pitchfork_2010s.csv` | ✅ auto-scraped | 199 |
| AOTY yearly top-50 (2007-now) | `aoty_yearly.csv` | ✅ auto-scraped | ~950 |
| Rolling Stone 500 (2020) | `rolling_stone_500.csv` | ✅ auto-fetched (CSV mirror) | 499 |
| Best Ever Albums Top 3000 | `bea_top_3000.csv` | ✅ auto-scraped (~10min run) | 3,000 |
| Pitchfork Best of the 2020s | `pitchfork_2020s.csv` | ⬜ N/A | use aoty_yearly |
| Jazz canon (DownBeat + AAJ) | `jazz_canon.csv` | ⬜ manual | ~150 |
| Electronic canon (RA + FACT) | `electronic_canon.csv` | ⬜ manual | ~150 |
| Hip-hop canon (Complex + Source) | `hiphop_canon.csv` | ⬜ manual | ~150 |
| Metal canon (Decibel HoF) | `metal_canon.csv` | ⬜ manual | ~150 |
| Country canon (RS Greatest Country) | `country_canon.csv` | ⬜ manual | 100 |
| Classical canon (Gramophone HoF) | `classical_canon.csv` | ⬜ manual | ~100 |

**Auto-scraped total:** ~5,200 unique entries before dedupe (BEA's
Top 3000 dominates; substantial overlap with Pitchfork + Grammy
gets collapsed at ingest time via the existing MBID-based
`resolve_identity` cache).

## Regenerating the auto-scraped CSVs

The CSV files for sources marked ✅ above are produced by
`apps/api/scripts/generate_seed_csvs.py`. The scrapers live under
`apps/api/scripts/seed_sources/` and ship with `uv sync --extra seed-scripts`.

```bash
cd apps/api
uv sync --extra seed-scripts

# One source
uv run --extra seed-scripts python scripts/generate_seed_csvs.py grammy_aoty
uv run --extra seed-scripts python scripts/generate_seed_csvs.py pitchfork_2010s
uv run --extra seed-scripts python scripts/generate_seed_csvs.py aoty_yearly --start 2000 --end 2025

# All registered sources, skip-on-fail
uv run --extra seed-scripts python scripts/generate_seed_csvs.py --all
```

Each run overwrites the existing CSV in place. The ingest pipeline
is idempotent, so re-running `scripts/seed_catalog.py {source}` after
a refresh just hits already-cached rows for unchanged entries and
materialises any new ones.

## Adding a new source

1. Drop the CSV in this directory under the source name (e.g.
   `pitchfork_2010s.csv`).
2. Open `apps/api/src/auxd_api/modules/catalog_seed/sources/__init__.py`
   and uncomment the matching line in `SOURCES`:
   ```python
   "pitchfork_2010s": load_from_csv("pitchfork_2010s.csv"),
   ```
3. Update the status table above (flip ⬜ → ✅).
4. Run the ingest:
   ```bash
   uv run python scripts/seed_catalog.py pitchfork_2010s
   ```

The pipeline is idempotent — re-running against the same CSV just
hits the local cache via `resolve_identity`'s MBID dedupe; no
duplicates, no harm.

## Where to source each list

The six ✅ sources are auto-scraped — see the regeneration commands
above. The ⬜ sources still need a manual CSV drop because each
publisher's list page lives on its own custom-rendered site (most
are JS-rendered, paywall-gated, or layout-volatile in ways that
make a stable scraper not worth the maintenance load).

Pointers for sourcing the manual ones:

* **Genre canons** — best path is to hand-compile from these
  published lists into CSV form (each is ~100-150 entries):
  * **Jazz** — DownBeat 80th-anniversary list + All About Jazz Top 100
  * **Electronic** — Resident Advisor Top 100 (residentadvisor.net/features) + FACT Magazine 100 Greatest
  * **Hip-hop** — Complex 100 Best Albums + The Source 5 Mic albums
  * **Metal** — Decibel Magazine Hall of Fame (decibelmagazine.com/hall-of-fame/ — JS-rendered, scrape blocked)
  * **Country** — Rolling Stone's 100 Greatest Country Albums
  * **Classical** — Gramophone Hall of Fame (gramophone.co.uk/hall-of-fame)
  
  The CSV format is just `artist,title,year,source_rank` — fastest path is to copy-paste from the published article into a spreadsheet, normalize, and export.

* **Pitchfork 2020s** — Pitchfork hasn't published a decade rollup
  yet (likely 2029). For now `aoty_yearly.csv` covers 2020-onward
  via critic-aggregated yearly top-50s, which is functionally
  equivalent until the editorial rollup lands.

## Idempotency notes

The ingest service walks each `(artist, title)` through
`search_albums()`, which triggers `resolve_identity()` as a
side-effect. `resolve_identity()` dedupes by MBID first, falling back
to `(title, artist)` casefolded — so re-running a CSV is safe and
cheap (cached hits short-circuit on the local catalog query).
