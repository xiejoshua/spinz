# MusicBrainz mirror (Turso / libSQL)

A read-only mirror of the MusicBrainz release-group catalog,
hosted on Turso's free-tier libSQL database. Gives us sub-10ms
metadata lookups for ~1.5M release-groups without burning the
MB web API's 1 req/sec etiquette policy.

## Why this exists

Until now every search/resolve call hit the MB web API or
Discogs at request time — ~150-2000ms per query, gated by rate
limits, and prone to provider-side failures. The mirror covers
the bulk of "we already know this MBID, what's its metadata?"
lookups locally, dropping the hot-path latency to ~10ms and
removing the rate-limit failure mode from common reads.

The web API + Discogs are still wired as fallbacks for anything
the mirror doesn't have (long-tail releases, fresh material).

## Architecture

```
┌─ FastAPI request ────────────────────────────────────────┐
│                                                          │
│  search.service.search_albums(...)                       │
│       │                                                  │
│       ├─ tier-0: AlbumMirrorService.search_text()       │  ← this module
│       │      └─ Turso libSQL (FTS5 + indexed columns)   │
│       │      └─ ~10ms hit when populated                │
│       │                                                  │
│       ├─ tier-1: Atlas Search ($search aggregation)     │
│       ├─ tier-2: Discogs masters search                  │
│       └─ tier-3: MusicBrainz web API                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Module layout

| File | Role |
|---|---|
| `client.py` | Thin async wrapper over Turso's `/v2/pipeline` HTTP API |
| `schema.py` | DDL for `albums_mirror` + FTS5 index + sync triggers |
| `service.py` | `AlbumMirrorService` with read + bulk-upsert surface |
| `types.py` | `MirrorRow` data shape |

## Operator setup

### 1. Create a Turso account + database

```bash
# Install the Turso CLI (one-time)
curl -sSfL https://get.tur.so/install.sh | bash

# Sign up + log in
turso auth signup
turso auth login

# Create a database (free tier)
turso db create auxd-mb-mirror

# Get the connection URL + auth token
turso db show auxd-mb-mirror --url
turso db tokens create auxd-mb-mirror
```

### 2. Configure the API

Add to `apps/api/.env`:

```dotenv
TURSO_DATABASE_URL=libsql://auxd-mb-mirror-<your-org>.turso.io
TURSO_AUTH_TOKEN=<the-token-from-turso-db-tokens>
```

Leave these unset to disable the mirror (the search flow falls
through to Atlas → Discogs → MB API unchanged).

### 3. Run the initial ingest

```bash
cd apps/api

# Smoke test with 50k rows (~2 min, validates the pipeline)
uv run --extra seed-scripts python scripts/mb_mirror_ingest.py --limit 50000

# Full ingest (~1-2 hours for ~1.5M filtered rows)
uv run --extra seed-scripts python scripts/mb_mirror_ingest.py
```

The ETL is idempotent — re-running upserts rows in place. Pin
to a specific dump date via `--dump-date YYYYMMDD-HHMMSS` for
reproducibility; defaults to MB's latest published dump.

### 4. Verify

```bash
uv run python -c "
import asyncio
from auxd_api.settings import get_settings
from auxd_api.modules.mb_mirror.client import TursoClient
from auxd_api.modules.mb_mirror.service import AlbumMirrorService

async def main():
    client = TursoClient.from_settings(get_settings())
    if client is None:
        print('mirror disabled — TURSO_DATABASE_URL missing')
        return
    async with client as turso:
        svc = AlbumMirrorService(turso)
        row = await svc.find_by_mbid('5e02b1ab-c50e-3a35-a06b-94ed3c66c1c5')  # Innervisions
        print(f'lookup: {row}')
        results = await svc.search_text('blonde frank ocean', limit=5)
        for r in results:
            print(f'  {r.artist_credit} - {r.title} ({r.release_year})')

asyncio.run(main())
"
```

## Schema versioning

Bump `schema.SCHEMA_VERSION` whenever a column changes shape;
the ETL records the version in `mirror_meta` so future ingests
can detect drift and refuse to write into a stale schema. Rolling
a new schema = (1) bump the constant, (2) re-run ETL fresh.

## Cost

Turso's free tier as of 2026:

* 9 GB total storage
* 500M row reads / month
* 10M row writes / month
* Unlimited databases (per org)

Our ~1.5M filtered rows × ~250 bytes/row ≈ **400-600 MB**, well
under the storage cap. Read traffic at our user scale stays
well under the 500M/month read cap. Write budget is consumed
only during the monthly refresh ingest (~3M writes per refresh
including FTS index sync triggers).

## Refresh cadence

Monthly is the recommended baseline — MB releases new dumps
twice a week, but the marginal data drift between consecutive
weekly dumps is negligible for our purposes. Re-run the ingest
script manually (or wire it into the existing arq cron stack
similar to `catalog_seed_job.py`) once a month.

## Failure semantics

The mirror is a **best-effort cache**, not a source of truth.
Every read method on `AlbumMirrorService` returns the empty
sentinel (`None` / `[]`) on:

* Mirror disabled (no `TURSO_DATABASE_URL`)
* Network failure to Turso
* libSQL error

The search flow's fallback tiers absorb the miss without
exception handling. **Never raise from a mirror read** — the
upstream tiers must keep working when the mirror has a bad
moment.

## Future work

* **Cover-art URL backfill** — populate `cover_art_url` from
  CoverArtArchive's API during ingest (one extra HTTP call per
  row, gated by a separate rate-limit budget). Currently the
  field stays null and the cover proxy resolves on-demand at
  render time.
* **Live Data Feed integration** — apply MB's hourly delta
  stream instead of monthly full ingests. Reduces both ingest
  duration (delta is ~MB-sized, not GB-sized) and staleness
  window.
* **Search-flow tier-0 wiring** — surface mirror hits as a
  pre-Atlas tier in `search.service.search_albums()`. Deferred
  until the mirror is populated + measured.
