# Implementation Log — auxd MVP (Phase 6)

> Feature: `001-auxd-mvp` | Phase: 6 Implementation
> Session 1 start: 2026-05-22

## Session 1 — Pre-implementation sync-fix-list application

**Goal:** Land the 10 active sync-verify backlog items before code starts, then execute autonomous §0 prerequisites (T001, T003, T004, T008).

### Checkpoint #1 — After sync-fix-list apply (10 items)

| Check | Status | Notes |
|-------|:------:|-------|
| Plan additions land cleanly | ✅ | 4 new sections added: §4.5 Endpoint rate-limit, §4.6 Settings→Integrations, §11.2.1 Report-missing-album, §16.5 Accessibility audit cadence. §1.1.1 fail-mode table + §3.1 collection inventory + §6 service surface table all extended. |
| Task additions land cleanly | ✅ | 2 new tasks added (T010a mongodump, T015a OTel). 5 tasks amended in-place (T013, T023, T025, T026, T135). Coverage matrix total updated to 183. |
| Cross-link integrity | ✅ | New §-references and DRIFT-L\* tags resolvable. No broken anchors introduced. |
| sync-fix-list.md updated | ✅ | All 10 active items checked + dated. 2 deferred items remain unchecked (L3-005, L3-008). |
| Structural drift advance | ✅ projected | Next sync-verify run expected to show 27 → ~10 structural items (cosmetic 14 INFOs remain advisory). Re-run after Phase 6B confirms. |

**Verdict:** CLEAN — proceed with §0 autonomous prerequisites (T001 → human sign-off → T003 → T004 → T008).

### Checkpoint #2 — After T001, T003, T004, T008 (4 tasks complete)

| Check | Status | Notes |
|-------|:------:|-------|
| Task-Code correspondence | ✅ | T001 → `.specify/memory/constitution.md` (ratified, committed `0c608a9`). T003 → 17 files across `apps/api/`, `apps/web/`, `packages/shared-types/`, `package.json`, `pnpm-workspace.yaml`, `.gitignore`, root `README.md`. T004 → `.github/workflows/ci.yml`. T008 → VAPID public in `apps/web/.env.example`; runbook in `docs/infra.md`. |
| Spec AC alignment | ✅ | T001 includes all 6 plan §0 principles. T003 scaffold matches plan §1.2 monorepo layout (`apps/api`, `apps/web`, `packages/shared-types`). T004 CI workflow follows plan §16.4 sketch (Ruff + mypy strict; Biome + tsc strict; pnpm filter pattern). T008 uses ES256 P-256 keys per Web Push standard. |
| Unplanned changes | ✅ None | All 21 files map directly to a planned task. No incidental file edits outside scope. |
| Plan alignment | ✅ | Tech stack matches plan §2: FastAPI 0.115 + Pydantic 2.9 (Python 3.12), Next.js 15 + React 19 + TypeScript 5.6, pnpm 9 workspace mode. `.product-forge/config.yml` updated to monorepo mode with `backend/frontend/shared` paths. |
| Constitution alignment | ✅ | Principle V (observability mandatory) — `/healthz` is the seed; full observability lands in T011 + T015 + T015a. Principle III (library-first) — module layout in `apps/api/src/auxd_api/` is ready for `modules/<module>/` + `lib/` subdirs in T011+. |

**Open items / human-action gates:**
- pnpm + uv not installed locally — scaffolding written but **build verification (pnpm install / uv sync / dev-server boot) is pending tool install**. Recommended: `brew install pnpm uv` then re-run T003 Done-criteria checks.
- T002 (Spotify Extended Quota Mode application) — not attempted this session; external 2-6 week dependency. Surface for next session.
- T005 (Atlas + Upstash provisioning) — external accounts not yet created. Connection strings TBD; `docs/infra.md` has placeholders.
- T006 (Fly + Vercel projects) — external accounts not yet created. DNS records for `TBD.app` and `api.TBD.app` TBD.
- T007 (Postmark + Sentry + PostHog + secrets) — external accounts + secret provisioning TBD.
- T009 (deploy workflows) — depends on T006 + T007 going live before workflows are meaningful.
- T010 (synthetic monitoring) — depends on T009.
- T010a (mongodump backup) — depends on T005 + T007 (S3 bucket creation).

**Verdict:** CLEAN — 4/4 autonomous §0 tasks complete; 5 human-action tasks remain. Session can stop here per user directive ("Stop and report" on human-action blockers). Next session: install pnpm + uv, verify build, then attempt T002 (Spotify app — external) before continuing.

### Checkpoint #3 — Post-install verification (after `brew install pnpm uv`)

User installed pnpm 11.2.2 + uv 0.11.16 via Homebrew. All T003 + T004 done-criteria exercised locally and PASSING:

| Step | Command | Result |
|------|---------|--------|
| pnpm install (root) | `pnpm install` | ✅ 29 unique packages added (Next.js 15.5.18, React 19.2.6, TypeScript 5.9.3, Biome 1.9.4, @auxd/shared-types resolved via workspace:*). 34s. |
| uv sync (apps/api) | `uv sync --extra dev` | ✅ fastapi 0.136.1, pydantic 2.13.4, mypy 2.1.0, ruff 0.15.14, pytest 9.0.3, uvicorn 0.47.0 (+ ~25 transitives). |
| Backend boots | `uv run uvicorn auxd_api.main:app --port 8000` | ✅ `GET /healthz` → 200 `{"status":"ok","version":"0.0.0"}`. |
| Frontend boots | `pnpm --filter @auxd/web dev` | ✅ Next.js dev server starts on :3000. `GET /` → 200 with `<h1>auxd</h1>` + the shared-types greeting + the T003-verified line — proves the workspace package resolution chain works end-to-end. |
| Ruff check | `uv run ruff check .` | ✅ All checks passed (0 lint issues). |
| Ruff format check | `uv run ruff format --check .` | ✅ 4 files already formatted. |
| Mypy strict | `uv run mypy src tests` | ✅ Success: no issues found in 4 source files. |
| Pytest | `uv run pytest -v` | ✅ 1/1 test_healthz_returns_ok PASSED in 0.18s. |
| Biome check (frontend) | `pnpm --filter @auxd/web lint` | ✅ Checked 7 files in 8ms — clean. |
| tsc strict (frontend) | `pnpm --filter @auxd/web typecheck` | ✅ No errors. |
| Next build (frontend) | `pnpm --filter @auxd/web build` | ✅ Compiled in 1.15s. Static pages prerendered (`/` + `/_not-found`). First-load JS = 102 kB shared + 125 B per route — well within plan §6 perf NFR target. |

**Note:** Python is 3.14 locally (newer than the pyproject `>=3.12` constraint). uv resolves and tests pass — fine for development.
**Note:** pnpm installed is 11.2.2 (newer than `packageManager: pnpm@9.12.0` declared in package.json). Engines allows `>=9.0.0`. No conflict observed; the `packageManager` field is corepack-enforced only, and corepack is opt-in. If corepack gets enabled later, bump the declared version.

**Verdict:** GREEN — T003 + T004 Done-criteria fully satisfied. Monorepo is build-verified and CI-verified locally. The CI workflow at `.github/workflows/ci.yml` will run the same commands on PR-trigger once the repo is pushed to a remote.

## Session 2 — Foundation libs wave (2026-05-22 PM)

**Goal:** Execute productive-while-blocked tasks — backend foundation libs that don't depend on any external account (T002/T005/T006/T007 remain blocked). Picked 6 Constitution-required tasks: T018, T029, T014, T017 (Wave 1, parallel) → T015, T015a (Wave 2, sequential).

Tasks completed: **T014, T015, T015a, T017, T018, T029**. Total now 10/183.

### Checkpoint #4 — After Wave 1 (T018, T029, T014, T017)

| Check | Status | Notes |
|-------|:------:|-------|
| Task-Code correspondence | ✅ | T018 → `lib/ids.py` + tests (6/6). T029 → `settings.py` + `.env.example` + tests (8/8). T014 → `lib/resilience.py` + tests (29/29, **100% coverage**). T017 → `lib/secrets.py` + tests (11/11). |
| Spec AC alignment | ✅ | All Done criteria satisfied per spec strings. |
| Unplanned changes | ✅ None | All files map directly to a task. `pytest-cov>=5.0` added to dev extras for T014's coverage gate. |
| Plan alignment | ✅ | CircuitBreakerStore Protocol with InMemoryCircuitBreakerStore default — matches plan §5.3 expectation that Redis backing plugs in via T020. TokenEncryptor MultiFernet rotation matches plan §17.2. Pydantic Settings field set matches plan §17.2. |
| Constitution alignment | ✅ | P1 (resilience) — primitives in place; P2 (schema-versioning) — not yet exercised; P3 (library-first) — clean module structure with `__all__` exports; P5 (observability) — log_call/emit_event/init_sentry land in T015. |

**Verdict:** CLEAN — proceed to Wave 2.

### Checkpoint #5 — After Wave 2 (T015, T015a)

| Check | Status | Notes |
|-------|:------:|-------|
| Task-Code correspondence | ✅ | T015 → `lib/observability.py` + tests (13/13). T015a → `lib/otel.py` + `main.py` modified for lifespan + `tests/test_otel.py` (8/8). |
| Spec AC alignment | ✅ | `/healthz` request now produces an OTel span with `http.route` attribute (verified via InMemorySpanExporter in test_otel.py); `init_sentry` idempotent; PostHog client lazy-init with no-op when key absent. |
| Unplanned changes | ✅ None | Only main.py modified (lifespan addition); test_healthz.py left untouched (TestClient without context-manager doesn't trigger lifespan, so existing test still passes). |
| Plan alignment | ✅ | OTel SDK + FastAPI/httpx auto-instrumentors per plan §15.4. ConsoleSpanExporter→stdout matches plan's "no dedicated tracing backend at MVP". PymongoInstrumentor deferred to T012 with TODO comment in otel.py. |
| Constitution alignment | ✅ | P5 (observability) — fully wired. Every external API call has `log_call()` available. PostHog event channel ready. Sentry error capture ready. OTel traces ready. |

**Notable discovery:** `FastAPIInstrumentor.instrument_app(app)` does NOT invalidate the app's cached middleware stack. Without `app.middleware_stack = app.build_middleware_stack()` inside `init_otel`, the app is marked instrumented but emits zero spans when init happens from a lifespan. The agent caught this via test failure, documented it inline in `otel.py`, and added a regression test in `test_otel.py`. Production-tier trap avoided.

**Verdict:** CLEAN — Wave 2 complete; 10/183 tasks done; full suite 76/76 green; ruff/format/mypy clean across 18 source files.

### Remaining external blockers (unchanged)
T002 (Spotify Extended Quota), T005 (Atlas + Upstash), T006 (Fly + Vercel + DNS), T007 (Postmark + Sentry + PostHog + secrets). Downstream T009/T010/T010a still gated on those.

### Productive-while-blocked work remaining
Significant feature scope still unblocked: T011 (FastAPI app expansion), T012 (Beanie connection scaffold), T016 (lib/visibility), T019 (session middleware), T021–T027 (7 Beanie Document models), T028 (OpenAPI codegen), T031–T040 (frontend foundation). Next session can pick another wave.

## Session 3 — Infra-decision swaps (2026-05-22 evening)

Founder shared blocker progress: Atlas + Upstash + PostHog accounts created on US-East infra, Cloudflare domain `xiejoshua.com` registered as a temporary domain, R2 bucket spun up. Asked for cost-minimization audit + alternatives.

Applied four architectural decisions that drop projected MVP run-rate from ~$60/mo to **$5/mo**:

| Decision | Was | Now | Savings |
|----------|-----|-----|---------|
| Product analytics | PostHog self-hosted on Fly (needs ~4 GB RAM) | PostHog Cloud US (1M events/mo free) | ~$40/mo |
| Email | Postmark Starter ($15/mo for 10k) | Resend (3k/mo free) | $15/mo |
| Backups | S3 (~$1-3/mo at MVP scale) | Cloudflare R2 (10 GB free) | ~$2/mo |
| Fly region | `sjc` (us-west) | `iad` (us-east, colocates with Atlas/Upstash/R2) | latency win |

Plus domain placeholder `TBD.app` → `xiejoshua.com` / `api.xiejoshua.com` across 6 live artifacts.

### Files modified

- **Code (8 files):** `apps/api/src/auxd_api/settings.py` (POSTMARK_API_KEY → RESEND_API_KEY field rename; new R2_* fields; POSTHOG_HOST default updated to `https://us.i.posthog.com`; audit-log payload updated), `apps/api/.env.example` (synced; added R2 section), `apps/api/src/auxd_api/lib/observability.py` (docstring + provider-name comments), 3 test files (env-key allowlists updated for the rename + new R2 fields).
- **Docs / plan (6 files):** `docs/infra.md` (rewritten with cost-map table + R2 backup runbook + per-secret source table + DNS table for Cloudflare), `features/001-auxd-mvp/plan.md` (§1.1 topology diagram, §1.1.1 fail-mode row, tech-stack table, §15.2 observability rewrite, §17.2 hosting + region change + secrets list, §17.3 domain section, §17.4 backups section, §17.6 email section, risks row updated, §22 handoff bullet), `features/001-auxd-mvp/spec.md` (privacy NFR row), `features/001-auxd-mvp/tasks.md` (T002 / T005 / T006 / T007 / T010a / T135 / T143 / T154 descriptions + Done lines).
- **Supporting docs:** `features/001-auxd-mvp/migrations/risk-matrix.md` (S3 → R2 ref), `features/001-auxd-mvp/product-spec/notification-taxonomy.md` (EmailAdapter ref), `features/001-auxd-mvp/product-spec/seeding-strategy.md` (invite-link URL), `features/001-auxd-mvp/product-spec/user-journeys.md` (landing-page URL refs).

### Files deliberately not modified (historical snapshots)

- `features/001-auxd-mvp/implement/digest.md` — Phase 6 Session 1 digest, frozen.
- `features/001-auxd-mvp/plan/digest.md` — Phase 5 plan digest, frozen.
- Session 1 entries in this implementation-log — frozen.
- Earlier sync-report entries — frozen.

All carry TBD.app / Postmark / S3 references as time-of-writing record. Future readers should look at the latest plan.md / docs/infra.md as source-of-truth.

### Verification (pre-commit)

- Backend full suite: **76/76 passing** (settings rename didn't break anything).
- ruff check + format + mypy --strict: all green across 18 source files.
- No residual `Postmark` / `S3` / `sjc` / `us-west` in live artifacts (only intentional history mentions like "swapped from Postmark on…").
- 3 TBD.app refs remain in historical-snapshot files (intentional).

### Blockers status snapshot (post-session)

| Blocker | Status |
|---------|--------|
| T002 Spotify Extended Quota Mode | ⏸ submit pending |
| T005 Atlas M0 + Upstash Redis | ✅ accounts created — needs cluster + DB provisioned in `us-east-1`, IP allowlist, connection strings captured |
| T006 Fly + Vercel + DNS | ⏸ signups pending (Fly Hobby $5/mo billing required) |
| T007 Resend + Sentry + PostHog Cloud + R2 | 🟡 partial — PostHog ✅, R2 bucket ✅ (tokens pending), Resend ⏸ pending, Sentry ⏸ pending |
| Domain | ✅ `xiejoshua.com` registered via Cloudflare (DNS records pending creation) |
| Downstream T009/T010/T010a | ⏸ unchanged — gated on T005/T006/T007 |

---

## Session 3 — 2026-05-22 evening — §0 closeout + backend data layer (Wave A + Wave B)

Blockers (MongoDB Atlas, Upstash, Sentry, PostHog Cloud, Resend, R2, Fly billing, Cloudflare DNS) all resolved earlier in session. All seven integrations pass the smoke check on the user's host (`apps/api/scripts/check_integrations.py` → 7/7 with `truststore` patch for Zscaler MITM). Fly deploy ✅; Vercel deploy ✅; both healthchecks return 200.

### Wave A — §0 deployment automation (committed `743d052`)

| Task | What landed | Operator follow-up |
|------|-------------|--------------------|
| T009 | `.github/workflows/deploy-api.yml` — auto-deploy on push to main, `apps/api/**` path filter | Add `FLY_API_TOKEN` GitHub secret |
| T010 | `.github/workflows/synthetic.yml` — 15-min cron probe of frontend + `/healthz`; Discord webhook on failure | Add `DISCORD_WEBHOOK_URL` GitHub secret |
| T010a | `.github/workflows/backup-mongo.yml` — 03:30 UTC mongodump\|aws s3 cp to R2; 30-day lifecycle | Add `MONGODB_URI`, `R2_*` secrets; widen Atlas IP allowlist to `0.0.0.0/0` (or self-host runner) |

§0 deployment automation now complete. Three workflows + Dependabot + PR template all live on `main`.

### Wave B — backend data layer (T012 + T016 + T021..T027)

Launched as 8 parallel agents on `main`:

- **T016 — `lib/visibility`** — `can_read(viewer, content)` Visibility × ViewerRelation matrix via Protocols (no Beanie coupling, no service-layer leak). 54 tests, 100% coverage.
- **T021 — User** — Beanie Document with handle policy + notification preferences + music providers + status. KSUID id. Indexes: handle/email unique, status partial.
- **T022 — Album** — Beanie Document with mbid/spotify_id sparse-unique indexes. Atlas Search index JSON shipped at `apps/api/migrations/atlas_search/albums_index.json` for one-time UI apply.
- **T023 — DiaryEntry + Review + ReviewLike + ReviewEditHistory** — `auxed: bool` on DiaryEntry (Aux/Like split R3); Review with `reactions` sub-doc + 1:1 diary_entry_id; ReviewLike unique (review_id, user_id); ReviewEditHistory 90d TTL on edited_at (FR-030).
- **T024 — Backlog + BacklogItem** — Backlog 1:1 with User (unique user_id); BacklogItem with position + per_item_visibility + notes.
- **T025 — Follow + FollowRequest + Block** — three Documents with FollowState/FollowRequestStatus/BlockReason enums + compound unique indexes. Cascade-on-block deferred to T101 service layer (model layer is data-only).
- **T026 — Report + Notification + NotificationPreferences + FailedEmail** — `NotificationType` (18 active per spec v1.4); Notification 90d TTL; FailedEmail as T135 write target; Report.target_type incl. `missing_album` (sync-fix L3-006).
- **T027 — JustFinishedPrompt + SuggestedFollow + CriticSeed** — JustFinishedPrompt TTL partial-filter (`state=pending` → 24h) so LOGGED/DISMISSED/SUPPRESSED rows survive for S-B6 30d cooldown + attribution analytics.

Then **T012 — Beanie connection** wired it all together:

- `apps/api/src/auxd_api/db.py` — `init_db(uri)` + `close_db()` + `get_client()`; `ALL_DOCUMENT_MODELS` module-level constant as single source of truth (also consumed by `tests/conftest.py`).
- URI validated via `pymongo.uri_parser` BEFORE opening a socket; password redacted in the error path.
- Ping admin command verifies the connection (P5: fail loud). `client.close()` called on ping failure to avoid leaked pool.
- `main.py` lifespan: `init_db` → `init_sentry` → `init_otel` (DB first because it's the most disruptive failure surface).

### Testing strategy for Beanie Documents

Initial test runs hit `CollectionWasNotInitialized` because Beanie 1.x's `Document.__init__` calls `get_motor_collection()`. Two complementary fixes:

1. **`tests/conftest.py`** — session-scope autouse fixture that spins up `AsyncMongoMockClient()` (via `mongomock-motor`) and calls `init_beanie()` against all 17 Document classes once per test session. Pure Python; no real Mongo dependency.
2. **`Model.model_validate(...)`** instead of `Model(...)` for field-shape tests — bypasses `__init__` entirely and exercises Pydantic validation cleanly.

Result: all 229 tests run in ~11s without a Mongo process.

### Final-sweep cleanups during mini-verify

- `User.id` aligned with the 16-other-Documents convention (`alias="_id"` + `# type: ignore[assignment]`); `Album.id` also aligned.
- Removed 9 now-unused `# type: ignore[call-arg]` / `[arg-type]` comments in test files (Beanie's runtime registration via the conftest fixture made them redundant — mypy strict mode now resolves the constructor signatures fully).
- Removed redundant per-test `_stub_motor_collection` monkeypatch from `test_backlog_models.py` (session-scope conftest handles it).
- `test_otel.py` autouse fixture now monkeypatches `init_db` / `close_db` to no-ops — the OTel-specific tests don't need to traverse the real DB connect path.

### Verification (pre-commit)

- Full backend suite: **229/229 passing** in 11.20s (up from 76/76 in Session 2).
- `ruff check` + `ruff format --check` across 51 files: clean.
- `mypy --strict` across 51 source files: 0 errors.
- Document model class count: 17 across 10 module directories; conftest + `db.py` agree on the canonical list.

### Status snapshot

- Tasks completed: **22 / 183** (Session 2: 10 → Session 3: +12).
- Foundation complete: §0 deployment automation, §1 lib + shared backend, §2 data layer.
- Next wave candidates: T019 (sessions middleware) + T020 (rate limit) → T028 (OpenAPI codegen) → §3 services + handlers (T031+).

### Operator follow-up still pending

- GitHub repo secrets: `FLY_API_TOKEN`, `DISCORD_WEBHOOK_URL`, `MONGODB_URI`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`.
- Atlas IP allowlist widening to `0.0.0.0/0` (or self-hosted runner).
- T002 Spotify Extended Quota Mode submission (2-6 week external lead — still the longest-tail blocker for production OAuth scope).
