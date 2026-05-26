"""Catalog seed pipeline — Bundle Y curated essentials ingest.

Background
==========
The local ``albums`` catalog historically grew only when users
searched / logged something via the 3-tier Atlas → Discogs → MB
pipeline. That's fine for discovery but leaves catalog browse
(``/search?decade=2010s``) very thin until enough users have organically
surfaced albums in that bucket.

This module powers a curated bulk seed driven by "essentials" lists
(Bundle Y from the 003 product spec): Rolling Stone 500, Pitchfork
Best-of-Decade, Grammy Album of the Year, plus genre canons (jazz,
electronic, hip-hop, metal, country, classical). Each list is
expressed as a list of :class:`AlbumSeedEntry` tuples; the ingest
service walks them through the existing :func:`search_albums`
pipeline, which materialises each into the local catalog via
:func:`resolve_identity` (idempotent — the dedupe is handled there).

Architecture
============
* :mod:`auxd_api.modules.catalog_seed.models` — :class:`SeedRun`
  Beanie document tracks each ingest run for observability.
* :mod:`auxd_api.modules.catalog_seed.service` — :func:`ingest_seed_list`
  is the worker entry point; rate-limit aware, fault-tolerant.
* :mod:`auxd_api.modules.catalog_seed.sources` — per-source plugins
  exposing ``fetch_entries() -> list[AlbumSeedEntry]``. Add new sources
  by dropping a CSV into ``apps/api/data/seed_lists/`` and registering
  the loader.

Operational
===========
Initial backfill (one-shot)::

    cd apps/api
    uv run python scripts/seed_catalog.py grammy_aoty

Quarterly refresh runs in the arq worker (see
``workers/catalog_seed_job.py``) — disabled by default behind the
``CATALOG_SEED_CRON_ENABLED`` settings flag so the founder can decide
when to opt in.
"""
