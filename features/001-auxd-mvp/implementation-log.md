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

## Session 4 — 2026-05-22 evening — §0 closeout + backend data layer (Wave A + Wave B)

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

## Session 5 — 2026-05-22 evening — request-path wave (T011 + T013 + T019 + T020 + T028)

User confirmed GitHub repo secrets and Atlas IP allowlist are resolved at the start of the session. T002 (Spotify Extended Quota submission) remains the long-tail blocker.

### Tasks completed

| Task | What landed | Notes |
|------|-------------|-------|
| T011 | FastAPI app skeleton + `/api/v1` router + extended `/healthz` + JSON root logging | `routers/v1.py` aggregator (empty for now); `/healthz` returns `{status, db, redis, version}`, returns 200 with `degraded` when any subcheck fails so Fly never restart-loops on data-layer flap; `lib/logging.py` installs `JSONFormatter` on the root logger (1-line JSON-per-record). `ping_db`/`ping_redis` are no-raise sub-check helpers. |
| T013 | Redis client expansion + arq worker + Dockerfile/fly.toml two-process layout + fail-mode wiring | `redis_client.py` now owns the arq pool lifecycle (separate from the cache client) + `cache_get`/`cache_set` (fail-open + Sentry tag `cache.redis_down`) + `enqueue_job` (fail-503 via `JobEnqueueUnavailable` + Sentry tag `jobs.redis_down`). Global exception handler in `main.py` converts the exception to HTTP 503. `workers/main.py` registers `WorkerSettings` with a single `noop_job` so the enqueue → dequeue path is smoke-testable. fly.toml moved to `[processes]` (app + worker) with `[[vm]]` `processes = ["app", "worker"]`. arq 0.26+ added to deps. |
| T019 | Session middleware (HMAC cookie + CSRF double-submit + sliding expiry) | `lib/sessions.py` owns the token format (`base64url(payload).base64url(sig)`, payload `{u, c, i, e, v}`). `middleware.py` decodes on every request, sets `request.state.session`, returns 401 on tamper/expiry (refusing to silently downgrade so HMAC-rotation regressions surface), enforces CSRF on non-safe methods when authenticated, re-issues the cookie when remaining lifetime < 7d. `issue_session()` and `clear_session_cookies()` exported for use by login/logout handlers landing in T040+. |
| T020 | Rate-limit FastAPI dependency (Redis sorted-set sliding window + fail-open) | `lib/rate_limit.py` exposes a `rate_limit(endpoint, per_ip, per_user)` factory returning a `Depends()`-compatible callable. Algorithm: pipeline of `ZREMRANGEBYSCORE` + `ZCARD` → conditional `ZADD` + `EXPIRE`. Per-user dimension only evaluated when `request.state.session` is set. Fail-mode: RedisError → allow + Sentry tag `rate_limit.redis_down` (locked in Phase 5C C-5 + sync-fix L4-004). X-Forwarded-For honoured for first-hop client IP. |
| T028 | OpenAPI → TS type codegen pipeline | `packages/shared-types/scripts/codegen.sh` invokes `python -c "from auxd_api.main import app; …app.openapi()…"` in-process (no uvicorn boot needed) and pipes through `openapi-typescript` to `src/api.ts`. `src/index.ts` now re-exports the generated `paths`/`components`/`operations` (plus legacy `greeting()` from T003). `.github/workflows/codegen.yml` runs on `apps/api/**` + `packages/shared-types/**` changes and `git diff --exit-code`s `src/api.ts` so a stale checked-in copy fails the PR with the regen command in the error. `codegen:check` script wired for the same purpose locally. |

### Checkpoint #9 — Post-wave mini-verify

| Check | Status | Notes |
|-------|:------:|-------|
| Backend full suite | ✅ | 305/305 passing in 11.4s (was 229 → +76 new tests across the wave: T011 +25, T013 +20, T019 +23, T020 +8 — `test_sessions` includes a tampered-signature test that now uses a full-signature replacement instead of a single-char flip after one transient failure on an unlucky base64 alignment). |
| Backend ruff + format | ✅ | All 69 source files clean (auto-fixed 3 import-order + UP037 nits during the wave). |
| Backend mypy --strict | ✅ | 0 errors across 68 source files. One `type: ignore[arg-type]` added in the `JobEnqueueUnavailable` exception-handler test to paper over Starlette's `add_exception_handler` typing (handler narrows to subclass, Starlette signature is `Exception` only). |
| Frontend typecheck (apps/web) | ✅ | `tsc --noEmit` clean; the new `paths`/`components`/`operations` exports are picked up via `transpilePackages: ['@auxd/shared-types']` in `next.config.mjs`. |
| Frontend lint (apps/web Biome) | ✅ | 7 files clean. |
| Shared-types typecheck | ✅ | Generated `api.ts` (73 lines, paths for `/healthz` + empty `components.schemas` since no Pydantic models are routed yet) passes `tsc --noEmit`. |
| Codegen deterministic check | ✅ | `pnpm --filter @auxd/shared-types codegen:check` (regen + `git diff --exit-code`) returns clean — the CI gate will pass on its first PR. |

### Implementation decisions worth flagging

- **Two-pool Redis layout** in `redis_client.py` (cache `_client` vs arq `_arq_pool`) — arq attaches its own serialisation + connection pooling, so reusing the cache client would couple the two failure surfaces. Both connect to the same Redis URL; one Sentry alert per affected operation is the spec.
- **JSON logging on the root logger** (not just `auxd.observability`) — uvicorn's access logs and any third-party `logging` user now get the same shape. The `observability` logger keeps its dedicated handler for `log_call` so the `external_call` event stays separately filterable.
- **Sliding-expiry refresh on response, not request** — the new cookie is bundled with whatever the handler returns, so the client only sees the updated `Set-Cookie` after the in-flight call succeeds. Avoids the trap where a failed handler re-issues a session against the old state.
- **Fail-mode divergence on the same request** (cache → open, jobs → 503) was made explicit with a dedicated integration test (`test_cache_failure_does_not_block_enqueue_path`) so the contract from sync-fix L4-004 + pre-impl-review C-5 has runtime evidence.
- **OpenAPI ingestion is in-process** (no `uvicorn` spin-up) so the codegen script runs in <100ms and doesn't need real env vars. Confirmed locally: settings are deferred to lifespan, not module import.

### Status snapshot

- Tasks completed: **27 / 183** (Session 4: 22 → Session 5: +5).
- Foundation now complete enough that §3 service+handler tasks (T031+) can begin: every cluster's prerequisites are in code.
- Sync-verify scope expanded: Layer 6 (spec ↔ code) is still premature (no business logic yet), but Layer 5 (tasks ↔ code) coverage for the request path has more surface to compare against now. Recommend re-running sync-verify before the next 6B code review cluster.

### Operator follow-up status (post-Session-5)

- ✅ GitHub repo secrets configured by user.
- ✅ Atlas IP allowlist widened by user.
- 🟡 **T002 Spotify Extended Quota Mode submission** — still pending. Long-tail (2-6 week external lead).
- ✅ First push to `main` (`33393b8`) tripped **two CI regressions** introduced by Session 5; both fixed in `2f04a0b` + `e6d5f28`:
  1. **CI pytest red:** `workers/main.py` was constructing the full `Settings()` at class-definition (import-time) via `get_settings()`. Locally my `.env` had `SESSION_HMAC_KEY` + `TOKEN_ENCRYPTION_KEY` set; CI doesn't. Test collection blew up before any test ran. Fix: read `REDIS_URL` directly from `os.environ` (the only env var the worker needs at boot); reserve `get_settings()` for code paths that run after worker `on_startup`. Updated the 2 worker-settings helper tests to exercise the env-var path + local-default fallback. Caught the same regression locally via `env -i HOME=$HOME PATH=$PATH uv run pytest` before re-pushing.
  2. **deploy-api red:** `flyctl deploy` rejected the new `fly.toml` with "missing an app name". The `[processes].app` group name collided with the top-level `app = "auxd-api"` field — Fly's parser treats them ambiguously even though TOML scoping is clean. Fix: rename the HTTP process group `app` → `web` (and update `http_service.processes` + `[[vm]].processes` + Dockerfile CMD comment). Also switched the workflow to the conventional monorepo invocation (`working-directory: apps/api` + `flyctl deploy --remote-only -a auxd-api`) so we never depend on the fly.toml-parsing path for the app name in the first place.
- ✅ **Production deploy verified end-to-end** (`e6d5f28` → Fly deploy at 2026-05-22T21:53Z): `curl https://api.xiejoshua.com/healthz` returns `{"status":"ok","db":"ok","redis":"ok","version":"0.0.0"}` HTTP 200 — the new healthz contract is live, both subchecks (MongoDB Atlas + Upstash Redis) pass, and the two-process layout (`web` + `worker`) is running.

## Session 6 — 2026-05-22 night — CR-001 application (Spotify pivot)

**Scope:** apply Change Request CR-001 — remove all Spotify integration; pivot the MVP to a Letterboxd-style manual search + rating model backed by MusicBrainz (primary) + Discogs (fallback) + Cover Art Archive (covers). Spotify deferred to v2 because Extended Quota Mode now requires 250k MAUs to apply (structurally unreachable pre-launch).

**Execution model:** 5 parallel subagents (product-spec rewrite, spec.md rewrite, plan.md rewrite, tasks.md rewrite, code+tests patch) + wireframe redesigns + change-log + sync-verify done in main context. Locked decisions: MusicBrainz+Discogs catalog; just-finished cluster deferred-to-v2 (kept importable); provider abstraction kept; Must-Have priority in-release.

**Tasks (post-CR-001 state):**

| Action | Tasks | Notes |
|---|---|---|
| Hard-removed | T002, T042–T047, T054–T056, T114–T116, T121, T122, T177 (16 total) | All Spotify-only; T177 = orphan from T002 |
| Deferred-to-v2 | T123–T130 §12 cluster + T169 (9 total) | JustFinishedPrompt model kept importable but unregistered with Beanie |
| Amended completed | T021, T022, T026, T027, T029 (5 total) | Code patches landed alongside the spec edits |
| Added | T049a/b Discogs + T053a Report-missing-album (3 total) | Replace gap from Spotify removal |
| Final | 183 → 170 active lines (162 MVP + 8 §12 deferred) | |

**Verification:**
- Backend full suite: **306/306 pass + 3 skip** in 11.25s (skips = deferred JustFinishedPrompt instantiation tests).
- ruff + ruff format + mypy --strict: clean across 68 source files.
- CI green (CI, codegen, deploy-api all ✅ on commit `fa43ad8`).
- Production `/healthz` re-verified after deploy: 200 with all subchecks `ok`.

**Cross-agent risk consensus:** all three doc-rewriting agents independently flagged critic-seed cold-start as the new High-criticality risk. Logged in spec.md §11, plan.md §21, product-spec/seeding-strategy.md. Instrumentation flag set: if `log.commit.duration_ms` p50 > 3 min during M-2 closed beta, UX intervention required.

**Schedule impact:** **−2 to −6 weeks** (Spotify Extended Quota was the longest-tail blocker; removing it shortens M-1/M0 path).

**Memory persistence:** saved `project_auxd_spotify_pivot.md` to project memory so future sessions don't reintroduce Spotify by reflex.

**Commit history (Session 6):** `fa43ad8` — single squashed CR commit (44 files, +1789/−1131).

## Session 7 — 2026-05-22 late night — §4 Providers wave

**Scope:** build the post-CR-001 catalog backbone. 8 tasks: T041 Protocols, T048+T049 MusicBrainz pair, T049a+T049b Discogs pair, T050 Resilience transport, T051 Provider observability, T052 Error taxonomy. Constitution P4 test-first discipline.

### Tasks completed

| Task | Files | Notes |
|------|-------|-------|
| T041 | `providers/base.py` (148L), `providers/__init__.py` (50L), `tests/unit/test_providers_base.py` (109L) | `CatalogProvider` Protocol + `MusicProvider` Protocol (deferred-to-v2, no MVP impl); `CatalogAlbum` + `ListeningEvent` Pydantic models |
| T052 | `providers/errors.py` (92L), `tests/unit/test_providers_errors.py` (75L) | `ProviderError` base + `ProviderUnavailable` / `ProviderRateLimited` / `ProviderAuthRevoked` / `ProviderNotFound`; each carries optional `provider` field |
| T050 | `providers/transport.py` (282L), `tests/unit/test_providers_transport.py` (265L) | Custom `ResilienceTransport(httpx.AsyncBaseTransport)` wraps `circuit_breaker + retry + timeout`. 5xx → `ProviderUnavailable` after retry exhaustion; 429 → `ProviderRateLimited` immediately (no retry — P1 honored); connection error → `ProviderUnavailable` |
| T051 | extends `providers/transport.py` (above) | Per-request `log_call(provider, endpoint, latency_ms, status, request_id)` emission; status mapping uses HTTP code for clean responses + sentinels `"timeout"` / `"circuit_open"` / `"failed"` |
| T048 | `tests/integration/test_musicbrainz_provider.py` (225L) | 9 contract tests: search/get_by_mbid/limit/rate-limit/429→ProviderRateLimited/5xx→ProviderUnavailable/404→None. **Confirmed FAILING with ImportError before T049 written.** |
| T049 | `providers/musicbrainz.py` (180L) | `MusicBrainzCatalogProvider`: `httpx.AsyncClient` with `ResilienceTransport`, internal `asyncio.Lock + time.monotonic()` for the 1 req/sec MB policy, UA `"auxd/0.0.0 (https://auxd.xiejoshua.com)"`, CAA cover URL `https://coverartarchive.org/release-group/{mbid}/front`. **9/9 T048 tests PASS after impl** |
| T049a | `tests/integration/test_discogs_provider.py` (226L) | 7 contract tests: search/lookup/token-required/5xx/429/empty-when-token-unset. **Confirmed FAILING with ImportError before T049b written.** |
| T049b | `providers/discogs.py` (221L) | `DiscogsCatalogProvider`: reads `DISCOGS_API_TOKEN` lazily; **graceful-disabled mode when token unset** (returns empty/None — search endpoint T069 can call unconditionally). `Authorization: Discogs token={token}` scheme. **7/7 T049a tests PASS after impl** |

Plus `pyproject.toml` got `respx>=0.21` added to dev deps (resolved → 0.23.1) — the canonical httpx route mocker; used by both contract-test files.

### Architectural decisions worth flagging

- **Rate-limit policy stays provider-specific** — MB has its 1/sec lock inside `MusicBrainzCatalogProvider`; transport stays pure (resilience + observability only). Cleaner separation since Discogs handles its own pacing server-side.
- **429 retry semantics** — 429 bypasses the retry layer (one attempt, immediate raise); 5xx goes through normal retry-with-backoff. Honors P1's "429 means back off, not transient".
- **Discogs disabled-mode** — no token = construction succeeds, all queries return empty/None. Discogs is a true graceful fallback per the CR-001 decision, never load-bearing.
- **Cover-art URL synthesized** — MB responses don't carry image URLs; auxd derives them from the CAA URL convention. Frontend handles 404 fallback if the asset is missing.
- **ID-space ownership** — each catalog provider is authoritative for its own ID space (`mbid` vs `discogs`). Cross-provider joins are T063's job (identity-normalization service).
- **Env hygiene workaround** — the user's local `.env` still has pre-CR-001 `SPOTIFY_*` keys that `extra="forbid"` rejects. The new `_clean_env` fixture chdirs to `tmp_path` so pydantic-settings can't discover the polluted file. **Operator follow-up: strip SPOTIFY_* lines from `apps/api/.env` before next local `uv run uvicorn`.**

### Checkpoint #11 — Post-wave mini-verify

| Check | Status | Notes |
|-------|:------:|-------|
| Backend full suite | ✅ | **352/352 passing + 3 skipped** in 11.51s (was 306/3 → +46 new tests) |
| Backend ruff + format | ✅ | All 80 source files clean |
| Backend mypy --strict | ✅ | 0 errors across 79 source files |
| P4 test-first audit trail | ✅ | T048 and T049a both verified FAILING with ImportError before their impls were written |
| respx integration | ✅ | New dev dep; resolved to 0.23.1; both contract-test files mock via `@respx.mock` |

### Status snapshot

- Tasks completed: **35 / 170** (Session 6: 27 → Session 7: +8).
- §4 Providers cluster now COMPLETE. §6 (Albums + Search) unblocks: T063 identity normalization, T064 cache + TTL refresh, T065 MBID reconciliation, T067 album detail endpoint, T068 Atlas Search index, T069 search endpoint (Atlas + MB + Discogs fallback merge), T070 album detail page, T071 search UI, T072 cover-art proxy.
- §7 (Diary + Log sheet) also gains: T079 (Manual album search + prefill) can now bind to the catalog providers.

### Operator follow-up

- ✅ Strip `SPOTIFY_*` lines from local `apps/api/.env` — done at the top of the next session (Run #4 sync-fix commit `aa98618`); local `uv run uvicorn` boots cleanly.
- ✅ Apply for Discogs Personal Access Token — done; token set in local `.env` and rolled to Fly via `fly secrets set DISCOGS_API_TOKEN=...`. All 4 machines (2 web + 2 worker) updated; healthcheck verified at 2026-05-23T01:25Z.

## Session 8 — 2026-05-23 early morning — §6 Albums + Search backend wave (T063–T069)

**Scope:** the post-§4 catalog-read backbone. 7 tasks, all backend services + endpoints + arq workers + Atlas Search index. Frontend portion (T070/T071/T072) deferred to a later wave once §3 Next.js scaffold lands.

### Tasks completed

| Task | Files | Notes |
|------|-------|-------|
| T063 | `modules/albums/identity.py` (142L), `modules/albums/errors.py` (29L), `modules/albums/models.py` (+1 field), `tests/unit/test_albums_identity.py` (225L; 8 tests) | `resolve_identity(*, mbid?, discogs_release_id?, mb_provider, discogs_provider)` → Album. MBID-first lookup with 7d TTL cache. Discogs fallback creates Album with `candidate=True` (picked up by T065 reconciliation later). New `Album.candidate: bool` field + `AlbumNotFoundError` exception. |
| T064 | `modules/albums/workers.py` (243L; shared with T065), `workers/main.py` (rewrite to add `_on_startup`/`_on_shutdown` lifecycle hooks + cron registration), `tests/unit/test_albums_workers.py` (343L; 11 tests covering both T064 + T065) | `refresh_stale_album_metadata` arq cron daily 04:00 UTC. Cap 100 per run. **MB provider injected into ctx via WorkerSettings._on_startup** so the 1 req/sec etiquette is honored across all cron invocations rather than spinning up a fresh client each time. |
| T065 | (shares files with T064) | `reconcile_candidate_albums` arq cron weekly Sun 03:00 UTC. Fuzzy artist+title match against MB search → merges MBID into the candidate. |
| T066 | `modules/albums/editions.py` (138L), `tests/unit/test_albums_editions.py` (270L; 11 tests) | `get_editions` / `get_canonical_edition` / `aggregate_ratings`. **Known MVP limitation: `Album.mbid` unique-sparse index collapses editions to 1 row per release-group; future migration drops the unique constraint + adds `release_group_mbid` field.** Flagged as follow-up CR candidate. |
| T067 | `modules/albums/routes.py` (372L), `routers/v1.py` (mounts albums_router), `tests/integration/test_album_detail_endpoint.py` (325L; 6 tests) | `GET /api/v1/albums/{album_id}` returns `{album, editions, aggregate, my_history, friends, public_reviews}`. Visibility filtering via `lib/visibility.can_read`: anonymous = public reviews only; owner = own private history; followers = followed-user content per Review.visibility. Review.visibility coerced via Visibility(value) with try/except fallback to PUBLIC for forward-compat. |
| T068 | `migrations/atlas_search/albums_index.json` (extended), `migrations/README.md` (new, 61L), `tests/unit/test_albums_atlas_index.py` (81L; 5 tests) | Extended the T022 index JSON: lucene.standard analyzer + dual string/autocomplete field shapes on title + artist_credit (edgeNgram 2-8 chars + diacritic folding) + rating_count + `scoreDetails.popularity` using log1p(rating_count). Manual UI apply + atlas-cli automated apply both documented in the new README. |
| T069 | `modules/search/__init__.py` (1L), `modules/search/routes.py` (113L), `modules/search/service.py` (259L), `routers/v1.py` (mounts search_router), `tests/integration/test_search_endpoint.py` (287L; 7 tests) | `GET /api/v1/search?q=...&type=album&limit=N` three-tier search. (1) Atlas $search aggregation first — degrades to [] under mongomock so the fallback path carries tests. (2) If <5 hits → MB.search_albums + `resolve_identity` materialize. (3) If still <5 → Discogs.search_albums + materialize as candidates. Dedupe by mbid OR case-folded (title, artist). Empty result returns `{report_missing_album_url: '/api/v1/reports/missing-album'}` hint pointing at future T053a. |

### Architectural decisions worth flagging

- **Album.mbid is treated as release-group MBID at MVP** — individual editions are NOT separate Album docs because of the unique-sparse index. Editions surfaced inline via the existing `Album.editions` subdoc; `get_editions()` queries them from that list. Future migration plan documented in `modules/albums/editions.py` module docstring.
- **MB provider sharing across cron invocations** (T064 + T065): worker `_on_startup` constructs one `MusicBrainzCatalogProvider`, stashes it on `ctx["mb_provider"]`, and `_on_shutdown` calls `provider.aclose()`. This avoids both the construction cost AND the cross-invocation rate-limit-state-loss problem (since the 1/sec policy is enforced via an in-instance asyncio.Lock, sharing the instance preserves spacing across consecutive cron firings).
- **Atlas Search graceful degradation** (T069): mongomock doesn't support the `$search` aggregation stage; `_atlas_search` catches the unsupported-operation error and returns `[]`, letting the MB+Discogs fallback path carry every test. Tradeoff: local dev search experience runs in provider-only mode. Operator-facing: consider a `MOCK_ATLAS_SEARCH=1` env var if local Atlas-like ergonomics become important.
- **`Album.candidate` field** is the only new model field added this wave (cache_expires_at already existed). T021 amendment is one line; downstream impact captured in T063 identity service.

### Checkpoint #12 — Post-wave mini-verify

| Check | Status | Notes |
|-------|:------:|-------|
| Backend full suite | ✅ | **400/400 pass + 3 skip** in 11.53s (was 352/3 → +48 new tests) |
| Backend ruff + format | ✅ | 94 source files; clean |
| Backend mypy --strict | ✅ | 0 errors across 93 source files |
| Visibility-filter integration | ✅ | 6 integration tests confirm anonymous/owner/follower paths work end-to-end |
| respx mocking | ✅ | 7 search-endpoint tests + 6 album-detail tests use the §4 wave's respx infra |

### Status snapshot

- Tasks completed: **42 / 170** (Session 7: 35 → Session 8: +7).
- §6 Albums + Search **backend** cluster COMPLETE. Frontend portion (T070/T071/T072) waits for §3 Next.js scaffold.
- Logged Mid-wave observations as future-CR candidates:
  - Album.mbid unique-sparse limitation → release-group field flip
  - T069 p95 latency may exceed 200ms in MB-fallback path (acceptable for v0; rethink in v1.x if signal lands)
  - Atlas Search mock-shim for local dev (optional ergonomic improvement)

### Operator follow-up

- ✅ Strip stale `SPOTIFY_*` from `apps/api/.env` (done in sync-fix Run #4).
- ✅ Discogs Personal Access Token (done; live on Fly as of 2026-05-23T01:25Z).
- 🟡 Apply the updated Atlas Search index JSON to the dev cluster via UI or `atlas-cli` (see `apps/api/migrations/README.md`). The `_atlas_search` fail-soft path means search will still work without this, just without Atlas-tier results.

