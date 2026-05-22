# Migration Risk Matrix — auxd MVP

> Companion to [migration-plan.md](./migration-plan.md). Each risk has a concrete mitigation — no "monitor carefully".

## M0 (initial setup) risks

| # | Risk | Severity | Mitigation |
|--:|---|:---:|---|
| 1 | Atlas Search index doesn't propagate before catalog search ships | HIGH | Apply Atlas Search index FIRST (before deploying any search-dependent feature). Validation step in `validation.py` runs a `$search` query — if it errors, deploy blocks. Allow 5-min propagation window in deploy checklist. |
| 2 | Reserved-handles seed deployed late, after first signup | HIGH | Seed is loaded by `forward.py` BEFORE any application code is deployable (`migrations_meta` record gates app startup if `001_initial` missing). |
| 3 | Forward script run against wrong cluster (e.g., prod when meant for staging) | HIGH | Defensive `MONGODB_URI` validation in `forward.py`: print target host in dry-run mode; require explicit confirmation in `--prod` mode (post-launch). At M0, single-cluster setup eliminates this risk for the first run. |
| 4 | Idempotency bug — re-running forward.py corrupts state | MEDIUM | Forward script checks `list_collection_names()` + `list_indexes()` before each operation; re-runs are no-ops. Validated by running `forward.py` twice in CI smoke test. |
| 5 | Index build blocks writes on M10+ tier | LOW (M0) | On Atlas M0 free tier, indexes build in-place on empty collections (no impact). When upgrading to M10+ post-launch, switch to `background=True` (already noted in `forward.py` index options). |
| 6 | TTL index misconfigured (e.g., expires too aggressively) | MEDIUM | Notifications TTL = 90d, JustFinishedPrompt safety-net TTL = 30d (per-doc 24h handled at application level). Validated by `validation.py` — if `expireAfterSeconds` doesn't match expected values, deploy fails. |
| 7 | Atlas Search API integration not implemented at M0 | MEDIUM | Documented manual-application path. `forward.py` prints index JSON; founder pastes into Atlas UI. Phase 5 task should automate via Atlas Admin API if scale demands it. |
| 8 | Reserved-handles list includes accidental real-user names | LOW | Curated list of 200 obvious-squat names (major artists, brands, system). Reviewed by founder pre-application. Claim-via-verification flow handles legitimate ownership post-launch (per FR-029). |
| 9 | Schema-versioning pattern not enforced in app code | MEDIUM | Constitution Principle 2 mandates `_schema_version: int = 1` on every Document base class. Phase 6 Task T030 builds the migration runner that enforces it. Lint rule in CI checks for missing field on new models. |
| 10 | Rollback accidentally fires in production | CRITICAL | `rollback.py` requires `--confirm-destruction` flag PLUS interactive "I UNDERSTAND" prompt for non-test URIs. Cannot run via cron / automated deploys. Removed entirely from production runtime environments post-M0. |

## Post-M0 (live production) risks — for future migrations

| # | Risk | Severity | Mitigation |
|--:|---|:---:|---|
| 11 | Schema change deploys before readers tolerate new version | HIGH | Constitution P2: readers tolerate `N-1` and `N`. New writers ship AFTER readers can read new shape. Two-deploy release pattern. |
| 12 | Unique constraint violation during dual-write | HIGH | Pre-backfill check query: assert no duplicate keys exist in shadow column before flipping reader to new column. |
| 13 | Replication lag under backfill load (post-M10 multi-region) | MEDIUM | Throttle backfill at 1k rows / 100ms; monitor `replica_lag_ms`; pause backfill if lag > 30s. |
| 14 | Field deletion loses data | HIGH | Backup snapshot before applying. Three-deploy pattern: 1) stop writing to field, 2) verify field is unused, 3) drop. Each deploy ≥7d apart. |
| 15 | Atlas Search index change degrades query quality | MEDIUM | Build new index alongside old; switch reader endpoint after smoke-testing relevance with sample queries; drop old after 7d observation. |
| 16 | Beanie ODM transition (e.g., Beanie 2.x major release) | LOW–MEDIUM | Pin Beanie version in `pyproject.toml`. Migration to new major requires its own RFC + migration plan. |
| 17 | GDPR audit log retention drift | MEDIUM | 7-year retention is policy, not TTL — implemented at application level via periodic archival job (not in M0 scope; v1.x). |

## Tooling assessment

| Tool | Used? | Notes |
|---|:---:|---|
| `motor` + `pymongo` (async + sync drivers) | ✅ M0 | `forward.py` / `rollback.py` / `validation.py` all use async motor; CI uses sync pymongo for smoke tests. |
| Alembic-equivalent for Mongo | ❌ | No mature equivalent. We use the `migrations_meta` collection as our history + Constitution P2 per-doc versioning. |
| Beanie's built-in migration support | ⚠️ | Beanie has minimal migration tooling. We use raw motor + Beanie's lazy-upgrade-on-read pattern. |
| Atlas CLI (`atlas`) | Optional (v1.x) | For automating Atlas Search index application. M0 = manual UI. |
| Atlas Admin API | Optional (v1.x) | Same as above. |
| Backup snapshots | Manual at M0 (mongodump) | Atlas M10+ has automatic point-in-time backups. Until then, daily `mongodump` → S3 ($1/mo per [plan §17.4](../plan.md)). |
