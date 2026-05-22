# Implement — Phase 6 Digest (Session 1)

> Feature: `001-spinz-mvp` | Session 1 ended: 2026-05-22T03:30:00Z
> Tasks executed this session: 4 (T001, T003, T004, T008) + 10 sync-fix-list applies (pre-implementation)
> Phase status: `phases.implement = in_progress` — §0 prerequisites partially complete

## Session 1 scope

**Pre-implementation:** Applied 10 active items from `sync-fix-list.md` to plan.md (4 new sections), tasks.md (2 new tasks T010a + T015a; 5 amended T013/T023/T025/T026/T135), and bookkeeping files. Structural drift advance: from 27 to projected ~10 on next sync-verify run (cosmetic INFOs remain advisory).

**Autonomous §0 prerequisites executed:**
- **T001** — Constitution authored from plan §0 + ratified by founder + committed (`0c608a9 chore: ratify project constitution`).
- **T003** — Monorepo scaffolding: pnpm workspace + apps/api (uv) + apps/web (Next.js 15) + packages/shared-types. 17 files written. `.product-forge/config.yml` updated to monorepo mode.
- **T004** — `.github/workflows/ci.yml` with backend (ruff + mypy strict + pytest) + frontend (Biome + tsc strict + build) + aggregate `ci-status` gate.
- **T008** — VAPID keypair generated (P-256 / ES256). Public key in `apps/web/.env.example`; private key tracked outside repo with rotation procedure in `docs/infra.md`.

**Tasks NOT attempted this session (human-action blockers):**
- T002 — Spotify Extended Quota Mode application (external 2–6 wk dependency)
- T005 — MongoDB Atlas + Upstash Redis provisioning (external accounts)
- T006 — Fly.io + Vercel projects + DNS for spinz.app (external accounts + DNS)
- T007 — Postmark + Sentry + PostHog accounts + secret provisioning
- T009 — Deploy workflows (depends on T006+T007 live)
- T010 — Synthetic monitoring (depends on T009)
- T010a — Nightly mongodump backup (depends on T005+T007)

## Key decisions

- **Plan §4.5 / §4.6 / §11.2.1 / §16.5 added** during sync-fix apply to close structural drift on Must-Have requirements (endpoint rate-limit, Settings→Integrations, report-missing-album, axe-core CI gate). All four reference their DRIFT-L\* source in the section heading for forward traceability.
- **§3.1 collection inventory extended** with `follow_requests`, `review_edit_history`, and `missing_album` as a new `reports.target_type` enum value. The follow-request queue is Must-Have infrastructure for US-G2 even though US-H3 (the UI flow) is Should-Have — surfaced explicitly in sync-fix-list.
- **Constitution signed name-only.** Per founder directive, `**Ratified by:** Joshua Xie (founder, solo mode)` — no email. Memory saved for future governance docs.
- **Monorepo workspace_type = pnpm** (not Turbo or Nx) — keeps overhead minimal at MVP. Can migrate later if multi-app builds become non-trivial. shared-types package uses `workspace:*` protocol.
- **No build verification performed locally.** pnpm and uv are not installed in this dev environment. Scaffolding is syntactically valid and follows current Next.js 15 + FastAPI patterns, but `pnpm install` / `uv sync` / dev-server boot will be the user's first verification step.
- **VAPID generated via Python `cryptography` lib, not openssl `ec` shell commands** — the initial openssl extraction had byte-offset issues. Python's `cryptography.hazmat.primitives.asymmetric.ec` is the canonical correct path.

## Artifacts produced

### New files (T003)
- `package.json`, `pnpm-workspace.yaml`, `.gitignore`
- `apps/api/pyproject.toml`, `apps/api/README.md`
- `apps/api/src/spinz_api/__init__.py`, `apps/api/src/spinz_api/main.py`
- `apps/api/tests/__init__.py`, `apps/api/tests/test_healthz.py`
- `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/next.config.mjs`, `apps/web/biome.json`, `apps/web/next-env.d.ts`, `apps/web/README.md`
- `apps/web/.env.example`
- `apps/web/src/app/layout.tsx`, `apps/web/src/app/page.tsx`
- `packages/shared-types/package.json`, `packages/shared-types/tsconfig.json`, `packages/shared-types/README.md`
- `packages/shared-types/src/index.ts`
- `README.md` (root, rewritten)

### New files (T004)
- `.github/workflows/ci.yml`

### New files (T008)
- `docs/infra.md`

### Modified files (constitution / sync-fix)
- `.specify/memory/constitution.md` (T001 — full ratification)
- `.product-forge/config.yml` (T003 — monorepo mode enabled)
- `plan.md` (sync-fix §1.1.1, §3.1, §4.5, §4.6, §6, §11.2.1, §13.1, §16.4, §16.5)
- `tasks.md` (sync-fix T010a + T015a added; T013/T023/T025/T026/T135 amended; T001/T003/T004/T008 marked [x])
- `sync-fix-list.md` (all 10 active items checked + dated)
- `implementation-log.md` (2 checkpoints written)

### Commits
- `0c608a9 chore: ratify project constitution` — constitution.md only, per user directive.
- All other changes remain uncommitted. Recommended next commit: `chore: scaffold pnpm + uv monorepo for §0 prerequisites` covering T003/T004/T008 + sync-fix bundle.

## Open risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Build verification deferred** — pnpm + uv not installed locally, so `pnpm install` / `uv sync` / dev-server boot has not been exercised. | M | First action of next session: `brew install pnpm uv`, then run the T003 Done-criteria checks. If anything fails, treat as a regression and fix before further §0 work. |
| **External dependency chain (T002/T005/T006/T007) blocks T009/T010/T010a** | H | T002 is the longest lead-time (2–6 wk Spotify review). Submit Day 1 of next session. T005-T007 can run in parallel and unlock T009. |
| **No code committed yet for T003-T008** — only constitution committed | L | Bundle into a single follow-up commit before §1 backend foundation work starts to keep history clean. |
| **Constitution + monorepo not yet validated against an actual feature task** | L | T011 (FastAPI app skeleton) will be the first real exercise of the constitution + module layout principle. Expect minor refactors during T011 if the layout guidance proves brittle. |
| **OpenTelemetry T015a depends on T015 which depends on T011** — three-deep chain; OTel is Constitution P5 mandatory | L | Standard sequencing; no action needed beyond following the dep order in tasks.md. |
| **§1.1.1 fail-mode table now references `endpoint_rate_limit.redis_down` Sentry tag** which has no implementation yet | L | Lands in T013 + T020 + T015 wiring; Sentry tag is just a string contract. |

## Handoff to next phase / next session

**For next session of Phase 6 (continue Implement):**
1. Install tooling — `brew install pnpm uv` and verify `pnpm --version` and `uv --version` succeed.
2. Run T003 Done-criteria: `pnpm install` at root, `uv sync` in `apps/api`, `pnpm web:dev` (expect Next.js to serve `Hello from @spinz/shared-types.` at localhost:3000), `uv run --project apps/api uvicorn spinz_api.main:app --reload` (expect `/healthz` to return `{"status":"ok"}`).
3. If both boot cleanly, commit the scaffold as a single `chore: scaffold pnpm + uv monorepo for §0 prerequisites` commit.
4. **Then attempt T002** (Spotify Extended Quota app) — external, 2-6 wk lead. Submit Day 1. Capture reference ID in `docs/spotify-application.md`.
5. **Optionally** begin T005/T006/T007 external provisioning in parallel.
6. Once §0 is closed, begin §1 backend foundation work — T011 FastAPI app skeleton expansion (auth modules, settings, lifespan, etc.).

**For code-review (Phase 6B):** Currently premature — only the constitution is committed code. Code review becomes meaningful once §1+ tasks land actual feature code.

**For verify-full (Phase 7):** Same as above — verification is premature when only the constitution is committed.

**For sync-verify:** After all autonomous §0 tasks land in a commit, re-run sync-verify. Expected structural drift count: 0 (from 27 at Run #1). The 14 INFO items remain advisory.
