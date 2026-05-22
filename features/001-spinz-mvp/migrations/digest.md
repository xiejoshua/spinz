# Migration Plan — Digest

> **Feature:** 001-spinz-mvp
> **Phase:** migration_plan (5.5)
> **Generated at:** 2026-05-22T01:15:00Z
> **Artifact owner:** speckit.product-forge.migration-plan

## Key decisions

- **Big-bang strategy is appropriate at M0 because the project is greenfield.** No production data exists; no live writers to dual-write through; no replicas to drag through lag. Documented as the exception, not the new normal.
- **Post-M0 default strategy is expand–migrate–contract with Constitution Principle 2 per-doc schema versioning.** All future migrations must use lazy-upgrade-on-write and tolerate two adjacent schema versions during the deploy window.
- **16 collections + 30+ indexes + 1 Atlas Search index** are created by `forward.py`. The script is idempotent — safe to re-run.
- **Reserved-handles seed = 200 names**, sourced from major artists, brands, and system handles. Loaded from `seed-data/reserved_handles.txt` (under version control; updates via PR).
- **`rollback.py` is gated behind `--confirm-destruction` + interactive "I UNDERSTAND" prompt for non-test URIs.** Cannot fire from automated deploys; removed from production runtime post-launch.
- **`validation.py` doubles as a CI smoke test.** Should be wired into the deploy pipeline (per [tasks.md T004](../tasks.md)) so it runs against a fresh Atlas test cluster on every PR; catches drift between Beanie models and migration scripts.

## Artifacts produced

- `migrations/migration-plan.md` — master document; strategy, pre-migration checklist, runbook, future-migration pattern (Constitution P2), rollback triggers.
- `migrations/forward.py` — initial schema setup; idempotent; ~370 lines; uses motor (async). Returns exit code 2 if Atlas Search needs manual application.
- `migrations/rollback.py` — DESTRUCTIVE drop-everything; gated behind `--confirm-destruction` + interactive prompt; ~100 lines.
- `migrations/validation.py` — post-migration assertions: 18 collections, 50+ indexes by name, reserved-handles count ≥200, migrations_meta record, Atlas Search queryability; ~200 lines.
- `migrations/risk-matrix.md` — 10 M0 risks + 7 post-M0 risks, each with concrete mitigation.
- `migrations/seed-data/reserved_handles.txt` — 200 reserved handles in plain-text format.
- `migrations/digest.md` — this file.

## Open risks

- **Atlas Search index application is manual at M0.** `forward.py` prints the JSON definition; founder must paste into Atlas UI. Automating via Atlas Admin API is flagged for v1.x. Documented in migration-plan §3 + risk-matrix #7. **Mitigation:** deploy checklist requires Atlas Search index to be applied AND queryable (per `validation.py`) before catalog-search-dependent features ship.
- **Schema-versioning pattern enforcement** depends on Constitution Principle 2 being ratified (Phase 6 Task T001). If the constitution isn't ratified, future migrations may not follow the pattern. **Mitigation:** Task T001 is the absolute first task in Phase 6; cannot start any feature work without it.
- **No Alembic-equivalent for Mongo.** Migration history lives in the `migrations_meta` collection + per-doc `_schema_version`. Phase 6 Task T030 builds the runner skeleton. **Mitigation:** documented pattern; runner is small (~100 lines) and follows the well-known per-doc-schema-version pattern.
- **`rollback.py` exists in the codebase post-launch.** Even with safety gates, having a destructive script in the production repo is a footgun. **Mitigation:** add a deploy-time check that refuses to deploy if `rollback.py` is in any production-bound bundle; consider moving to an `ops/` directory excluded from production builds.
- **Reserved-handles list quality.** 200 names are a conservative initial set. Real-world ownership claims will surface gaps. **Mitigation:** claim-via-verification flow (per FR-029) handles legitimate ownership requests post-launch; the list is updated via PR review.
- **`forward.py` runs OUTSIDE the FastAPI app context.** It uses motor directly rather than Beanie, which means changes to Beanie model definitions could drift from the migration script. **Mitigation:** Phase 6 Task T030 (migration runner) wires `forward.py` into CI as a smoke test against a fresh Atlas test cluster; drift fails the build.

## Handoff notes for next phase

- **Phase 5C (Pre-Impl Review) recommended next**, given the 180-task scope + complex external integrations. Optional but valuable for catching ordering/dependency mistakes before they cost a sprint.
- **Phase 6 (Implement) start order is rigid:** Task T001 (constitution ratification) → Task T002 (Spotify Extended Quota Mode application) → Task T003 (monorepo scaffolding) → Task T005 (Atlas + Upstash provisioning, which feeds the migration scripts) → Apply migration via `forward.py` → Task T011 (FastAPI healthz) → continue per build order.
- **The migration scripts are deliberately decoupled from the application code** (no Beanie imports in `forward.py`). They can run before the application is built. This is the correct sequencing for greenfield: schema first, then app.
- **Future schema changes follow the pattern in migration-plan §6.** Each future change gets its own migration file (`002_*.py`, `003_*.py`, ...) keyed by `migrations_meta.version`. The runner T030 reads `migrations_meta` to determine which to apply on app startup.
- **Atlas Search index application** is on the critical path for Task T068 (per [plan §11.1](../plan.md)). The deploy checklist must include the Atlas UI step before catalog search ships to users.
- **`validation.py` must be runnable in CI against a fresh Atlas test cluster on every PR.** Set up a dedicated test Atlas project; pre-deploy job runs `forward.py` against it, then `validation.py`, then cleanup.
