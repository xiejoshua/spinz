"""MusicBrainz release-group mirror, backed by Turso (libSQL/SQLite).

Why this module exists
======================
The web-API path (``MusicBrainzCatalogProvider``) enforces MB's
1 req/sec etiquette policy and is gated by network round-trip
latency (~150-2000ms per query). For batch ingest pipelines and
high-traffic search surfaces, that's a hard ceiling.

Mirroring the release-group slice of MB into Turso's free-tier
libSQL database gives us:

* Sub-10ms lookups for any release-group we've mirrored (~1.5M
  rows after filtering for "has cover art + known year").
* No request budget — Turso's free tier serves unlimited reads at
  our scale.
* No rate-limit failure paths to handle in the hot read flow.

The mirror is read-only at request time; population happens via a
batch ingest worker (:mod:`auxd_api.scripts.mb_mirror_ingest` and
the monthly arq cron) that streams from MB's public JSON dumps.

Architecture
============
* :mod:`.client` — thin async wrapper around Turso's HTTP API
  (``/v2/pipeline``). Stateless, just httpx + a small protocol
  layer; avoids pinning to any third-party libSQL client.
* :mod:`.schema` — DDL for the ``albums_mirror`` table + FTS5 index.
* :mod:`.service` — :class:`AlbumMirrorService` with the lookup
  surface (``find_by_mbid``, ``search_text``, ``upsert_many``).
* :mod:`.types` — pydantic shape for mirror rows.

Settings gate
=============
The mirror is disabled when ``TURSO_DATABASE_URL`` is unset, so a
dev / CI environment without Turso credentials silently falls
through to the existing Atlas → Discogs → MB-API stack. No surprise
network calls.
"""
