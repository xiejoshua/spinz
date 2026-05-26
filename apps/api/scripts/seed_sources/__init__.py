"""Per-source CSV generators for the catalog-seed pipeline.

Each module exposes ``fetch_entries() -> list[SeedEntry]`` and an
optional ``write_csv()`` convenience that drops the output at
``apps/api/data/seed_lists/{name}.csv``. The :mod:`_common` module
holds the shared HTTP/CSV/parser plumbing so individual scrapers
stay focused on one site's layout.

When a publisher's HTML structure changes, only the affected module
breaks — other sources keep working. The :mod:`generate_seed_csvs`
meta-runner skips modules whose scraper raises and moves on.

See ``apps/api/data/seed_lists/README.md`` for the Bundle Y source
matrix and ``catalog_seed`` module docs for the downstream pipeline.
"""
