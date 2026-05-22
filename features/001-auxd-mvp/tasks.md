# Tasks: auxd MVP

> **Phase 5B — Task Breakdown** | Generated: 2026-05-22
> Feature slug: `001-auxd-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - Plan: [plan.md](./plan.md)
> - Spec: [spec.md](./spec.md)
> - Decision Log: [product-spec/decision-log.md](./product-spec/decision-log.md)

## Conventions

- **Task IDs:** `T001`..`TNNN`, unique throughout.
- **Sizes (D4 T-shirt):** XS ≤1h · S ≤½ day · M ≤1 day · L ≤2 days · XL >2 days (flag for decomposition).
- **Paths:** full paths from monorepo root (project is technically single-root mode at task-write time; T003 introduces monorepo structure).
- **Deps:** task IDs that MUST complete first. `—` = no dependencies.
- **Refs:** which user stories (US-X), FRs, NFRs, TCs, or decision-log entries the task implements.
- **Done signal:** under each task, what proves it complete (test passing + manual check unless noted).

## Coverage matrix (verified against plan + spec)

| Cluster | Tasks | Stories covered |
|---|---|---|
| §0 Prerequisites | T001–T010 | (cross-cutting) |
| §1 Backend foundation + libs | T011–T020 | (cross-cutting) |
| §2 Lib + shared backend | T021–T030 | Constitution P1, P2, P3, P5, P6 |
| §3 Frontend foundation | T031–T040 | Cross-cutting |
| §4 Providers (Spotify + MusicBrainz) | T041–T052 | FR-002, FR-003 (contract-test-first per P4) |
| §5 Auth | T053–T062 | US-A1, US-A2, US-G1, US-G5; FR-001, FR-002, FR-027, FR-029 |
| §6 Albums + Search | T063–T072 | US-F1, US-F2; FR-005, FR-010, FR-028 |
| §7 Diary + Log sheet (THE wedge) | T073–T084 | US-B1..B5; FR-004, FR-007 |
| §8 Reviews + Likes + sort | T085–T094 | US-C1..C4; FR-011, FR-030, FR-031, FR-032 |
| §9 Backlog | T095–T100 | US-D1..D3; FR-006 |
| §10 Social graph + Feed | T101–T112 | US-E1..E5, US-G4; FR-008, FR-009, FR-014, FR-016 |
| §11 Onboarding + Auto-import | T113–T122 | US-A2..A5; FR-002, FR-003, FR-015 |
| §12 Just-finished detection | T123–T130 | US-B6; FR-026 |
| §13 Notifications | T131–T144 | US-G3; FR-012 |
| §14 Profile, Settings, Privacy | T145–T152 | US-G1..G5; FR-013 |
| §15 GDPR + Moderation | T153–T161 | US-G4, US-G5; FR-019 |
| §16 Seeding backend | T162–T166 | US-A4, US-E5; FR-015 |
| §17 Should-have (Last.fm import etc.) | T167–T170 | US-H1, US-H2 |
| §18 Pre-launch hardening | T171–T180 | NFR Measurement Contract; spec.md §10 E2E coverage |

**Total: 183 tasks** (= 180 base + T117a Phase 5C + T010a + T015a both added in sync-fix Run #1 — see [sync-fix-list.md](./sync-fix-list.md)). Sized to deliver M-2 closed-beta scope per plan §18; 30/30 Must-Have user stories addressed; all 27 active FRs covered; all 32 critical TCs + 13 E2E scenarios referenced. Tasks amended in sync-fix Run #1: T013 (Redis fail-modes), T023 (ReviewEditHistory), T025 (FollowRequest), T026 (FailedEmail + missing_album report type), T135 (PostMark failure-mode + retry).

---

## §0 Pre-implementation prerequisites — MUST complete before any feature work

- [x] **T001 — Author and ratify project constitution** *(completed 2026-05-22, signed by Joshua Xie)*
      Paths: .specify/memory/constitution.md
      Size: M
      Deps: —
      Refs: plan §0; decision-log §Decisions deferred to Phase 5 (Constitution)
      Description: Replace template placeholders in `.specify/memory/constitution.md` with the 6 principles from plan §0 (external-call resilience, schema-versioned documents, library-first modules, test-first for catalog/auth, observability mandatory, provider abstraction). Founder sign-off required. Commit with message `chore: ratify project constitution`.
      Done: file is non-template; sign-off recorded.

- [ ] **T002 — Submit Spotify Extended Quota Mode application**
      Paths: docs/spotify-application.md (notes only)
      Size: S
      Deps: —
      Refs: plan §0 Task 1; decision-log Q22
      Description: Submit application via Spotify Developer Dashboard. Include business description (wedge thesis from spec.md §1.3), required scopes (5 essential per Q22 v1.3 / sync-fix Run #2: `user-read-email`, `user-read-private`, `user-read-recently-played`, `user-read-currently-playing`, `user-library-read`), privacy policy URL placeholder, ToS URL placeholder. **Parallel work** — does not block other tasks but is on the 2–6 week external critical path.
      Done: application submitted; reference ID captured in `docs/spotify-application.md`.

- [x] **T003 — Monorepo scaffolding (pnpm + uv + workspaces)** *(verified 2026-05-22: pnpm install ✓, uv sync ✓, both dev servers boot ✓, frontend resolves @auxd/shared-types via workspace:* protocol — implementation-log.md checkpoint #3)*
      Paths: package.json, pnpm-workspace.yaml, .gitignore, README.md, apps/api/pyproject.toml, apps/web/package.json
      Size: M
      Deps: T001
      Refs: plan §1.2
      Description: Init pnpm workspace; create `apps/api` (uv-managed Python) and `apps/web` (pnpm-managed Node) skeletons; create `packages/shared-types` placeholder. Verify both packages build empty. Update `.product-forge/config.yml` to enable monorepo mode (`codebase.paths: { backend: "apps/api", frontend: "apps/web", shared: "packages/shared-types" }`).
      Done: `pnpm install` succeeds at root; `uv sync` succeeds in `apps/api`; `pnpm --filter @auxd/web dev` and `uv run --project apps/api uvicorn ...` both boot.

- [x] **T004 — CI baseline (lint, type-check, test on PR)** *(workflow written 2026-05-22; all steps verified locally — ruff ✓, ruff format ✓, mypy strict ✓, pytest 1/1 ✓, biome ✓, tsc ✓, next build ✓; first remote PR run pending push)*
      Paths: .github/workflows/ci.yml, apps/api/pyproject.toml (ruff, mypy config), apps/web/biome.json, apps/web/tsconfig.json
      Size: M
      Deps: T003
      Refs: plan §16.4
      Description: GitHub Actions workflow with two jobs (backend, frontend). Ruff + mypy strict for Python; Biome + tsc strict for TS. Vitest + pytest configured with placeholder tests that pass. Coverage uploaded to Codecov (or local artifact for now).
      Done: PR-trigger workflow runs green on a no-op commit.

- [ ] **T005 — Provision MongoDB Atlas + Upstash Redis**
      Paths: docs/infra.md
      Size: S
      Deps: —
      Refs: plan §17.4, §17.5
      Description: Create Atlas M0 cluster (region: aws-us-east-1, matching Fly `iad` for low-latency colocation); create Upstash Redis (region: us-east-1); note connection strings; configure IP allow-list for local dev + Fly.io outbound IPs.
      Done: both services reachable from local dev; connection strings captured.

- [ ] **T006 — Provision Fly.io + Vercel projects**
      Paths: apps/api/fly.toml, apps/web/vercel.json
      Size: S
      Deps: T003
      Refs: plan §17.1, §17.2
      Description: `flyctl apps create auxd-api --region iad`; configure two-process layout (api + worker) on a single shared-cpu-1x VM (stays inside Hobby $5/mo minimum); link `apps/api/fly.toml`. `vercel init` linking `apps/web` to a Vercel project. Domain `xiejoshua.com` (apex → Vercel) and `api.xiejoshua.com` (CNAME → Fly via `fly certs add`) configured on Cloudflare DNS with proxy OFF for Vercel/Fly records.
      Done: empty hello-world deploys from each host land at expected URLs.

- [ ] **T007 — Configure Resend + Sentry + PostHog Cloud + Cloudflare R2 + secrets**
      Paths: apps/api/src/auxd_api/settings.py, docs/infra.md
      Size: S
      Deps: T005, T006
      Refs: plan §15, §17.6
      Description: Create accounts: Resend (sending domain `xiejoshua.com` — DKIM/SPF/DMARC records added to Cloudflare DNS); Sentry Developer plan free tier (projects `auxd-api` + `auxd-web`); PostHog Cloud US region free tier (project `auxd`); Cloudflare R2 API token for bucket `auxd-backups` (Object Read & Write, scoped to the one bucket). Set secrets via `fly secrets set` — full list in docs/infra.md: MONGODB_URI, REDIS_URL, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SESSION_HMAC_KEY, TOKEN_ENCRYPTION_KEY, RESEND_API_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, SENTRY_DSN, POSTHOG_API_KEY, POSTHOG_HOST, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, R2_BUCKET_NAME. PostHog self-host on Fly was the original plan; swapped to Cloud 2026-05-22 (saves ~$40/mo of RAM-heavy Fly compute).
      Done: secrets present in Fly + Vercel; PostHog Cloud ingest reachable from backend; Resend test-email roundtrip succeeds; R2 bucket accessible via S3-compat API from local dev.

- [x] **T008 — Generate VAPID keypair for Web Push** *(generated 2026-05-22; public key in apps/web/.env.example; private key tracked in docs/infra.md placeholder pending Fly secret)*
      Paths: docs/infra.md (private key in Fly secret, public key in repo)
      Size: XS
      Deps: T007
      Refs: plan §15.2 push, FR-026
      Description: Generate VAPID public/private keypair; public key committed to `apps/web/.env.example` and frontend bundle, private key in Fly secret as `VAPID_PRIVATE_KEY`.
      Done: keys generated and placed.

- [x] **T009 — Bootstrap deployment workflows (auto-deploy on main)** *(completed 2026-05-22; .github/workflows/deploy-api.yml uses superfly/flyctl-actions; Vercel auto-deploys via GitHub integration; needs FLY_API_TOKEN secret)*
      Paths: .github/workflows/deploy-api.yml, .github/workflows/deploy-web.yml
      Size: S
      Deps: T006, T007
      Refs: plan §17
      Description: GitHub Actions jobs that `flyctl deploy` for api and trigger Vercel deploy for web on push-to-main. Smoke test post-deploy.
      Done: a no-op push to main lands both apps without intervention.

- [x] **T010 — Synthetic monitoring + alerting** *(completed 2026-05-22; .github/workflows/synthetic.yml — 15-min cron probing both URLs; Discord webhook on failure; needs DISCORD_WEBHOOK_URL secret)*
      Paths: .github/workflows/synthetic.yml, docs/infra.md
      Size: XS
      Deps: T009
      Refs: plan §15.5
      Description: GitHub Actions cron every 15min curls `https://xiejoshua.com` and `https://api.xiejoshua.com/healthz`, posts to Discord webhook on failure.
      Done: synthetic check is live; intentional /healthz outage triggers Discord notification within 15min.

- [x] **T010a — Nightly mongodump backup to Cloudflare R2** *(added in sync-fix Run #1 — DRIFT-L4-002; swapped S3 → R2 on 2026-05-22 to stay on free tier; completed 2026-05-22 with .github/workflows/backup-mongo.yml — 03:30 UTC cron, mongodump|aws s3 cp streaming, Discord alert on failure; needs MONGODB_URI + R2_* + DISCORD_WEBHOOK_URL secrets, Atlas IP allowlist widened to 0.0.0.0/0)*
      Paths: .github/workflows/backup-mongo.yml, docs/infra.md (backup-restore runbook)
      Size: S
      Deps: T005, T007
      Refs: plan §17.4; NFR availability/durability
      Description: GitHub Actions scheduled workflow (daily 03:30 UTC) runs `mongodump --uri $MONGODB_URI --gzip --archive` and uploads to a Cloudflare R2 bucket (`auxd-backups`) via the S3-compatible API (boto3 or rclone — R2 endpoint via `R2_ENDPOINT_URL` secret). 30-day lifecycle policy via R2 bucket settings. Cost target: $0/mo at M0 (R2 free tier covers 10 GB storage + 1M Class A ops/mo — well above 30× ~100 MB compressed mongodumps). Atlas point-in-time backup deferred until M10+ tier. On failure, post to Discord webhook with last-success timestamp. Runbook in docs/infra.md describes restore procedure (`mongorestore --gzip --archive < dump.gz`).
      Done: workflow runs successfully against staging cluster; manual smoke-test of restore against a throwaway database succeeds; runbook reviewed.

---

## §1 Backend foundation + libs (single-source-of-truth utilities)

- [x] **T011 — FastAPI app skeleton + healthz** *(completed 2026-05-22 Session 5; versioned /api/v1 APIRouter mounted (empty for now); /healthz returns {status, db, redis, version} with status=ok only when both subchecks pass; JSON root-logger formatter in lib/logging.py; 21 new tests; ruff + mypy strict clean)*
      Paths: apps/api/src/auxd_api/main.py, apps/api/src/auxd_api/settings.py
      Size: S
      Deps: T003, T005
      Refs: plan §17.2; NFR availability
      Description: App factory with versioned `/api/v1` routing; `GET /healthz` returns `{status, db, redis}`; structured logging via Python logging + JSON formatter.
      Done: `/healthz` returns 200 with all sub-checks ok locally.

- [x] **T012 — Beanie + MongoDB connection** *(completed 2026-05-22; AsyncIOMotorClient + `init_db`/`close_db` wired into FastAPI lifespan; ALL_DOCUMENT_MODELS constant single-sources the 17-model list shared with conftest; ping-on-connect P5 fail-loud; URI-parser rejects missing DB name with redacted-password error; 14/14 unit tests; 229/229 full suite)*
      Paths: apps/api/src/auxd_api/db.py, apps/api/tests/unit/test_db.py
      Size: S
      Deps: T011
      Refs: plan §3
      Description: Beanie init on app startup; connection pool config; document base class with `_schema_version: int = 1` (Constitution P2).
      Done: integration test connects to local Mongo and inserts/retrieves a sanity document.

- [x] **T013 — Redis connection + arq worker scaffold + fail-mode wiring** *(completed 2026-05-22 Session 5; arq 0.26+ added; redis_client.py owns arq pool + cache_get/set fail-open (cache.redis_down Sentry tag) + enqueue_job fail-503 via JobEnqueueUnavailable (jobs.redis_down Sentry tag) + FastAPI exception handler → HTTP 503; workers/main.py with noop_job; fly.toml [processes] app+worker; 20 new tests incl. 3 integration tests covering divergent fail modes)*
      Paths: apps/api/src/auxd_api/redis_client.py, apps/api/src/auxd_api/workers/main.py, apps/api/Dockerfile, apps/api/tests/integration/test_redis_fail_modes.py
      Size: M
      Deps: T011, T005
      Refs: plan §1.1.1, §8.4, §15; sync-fix L4-004
      Description: Shared Redis client; arq `WorkerSettings` skeleton with a `noop_job`; Dockerfile defines two processes (api + worker). **Fail-mode wiring (sync-fix L4-004):** cache wrapper (`get/set`) catches `ConnectionError` and returns `None`/no-op (FAIL OPEN) with Sentry tag `cache.redis_down`. arq job-enqueue wrapper catches `ConnectionError` and raises `JobEnqueueUnavailable` → FastAPI dependency converts to `HTTP 503` with Sentry tag `jobs.redis_down`. Applied at every enqueue site (GDPR export, weekly digest, just-finished detection, suggested-follows recompute).
      Done: `noop_job` enqueued from api, executed by worker, log line confirms. Plus integration tests simulate Redis disconnect and assert (a) cache reads return None silently with Sentry alert, (b) job-enqueue endpoint returns 503 with Sentry alert.

- [x] **T014 — `lib/resilience` (retry + timeout + circuit breaker)** *(completed 2026-05-22; 29/29 tests; 100% coverage on resilience.py; in-memory CB store with Redis pluggable later via set_default_store)*
      Paths: apps/api/src/auxd_api/lib/resilience.py, apps/api/tests/unit/test_resilience.py
      Size: M
      Deps: T011
      Refs: Constitution P1; plan §5.3
      Description: `circuit_breaker(name)`, `retry(attempts, backoff)`, `timeout(seconds)` async context managers / decorators. Per-provider circuit-breaker state (open / half-open / closed) backed by Redis.
      Done: unit tests cover retry exhaustion + circuit-breaker open/close transitions + timeout cancellation. Coverage ≥90%.

- [x] **T015 — `lib/observability` (structured logging + PostHog client)** *(completed 2026-05-22; 13/13 tests; log_call + emit_event + init_sentry; graceful no-op when keys absent)*
      Paths: apps/api/src/auxd_api/lib/observability.py, apps/api/tests/unit/test_observability.py
      Size: M
      Deps: T011, T013
      Refs: Constitution P5; plan §15
      Description: `log_call(provider, endpoint, latency_ms, status, request_id)` helper; PostHog server-side client wrapper `emit_event(user_id, event, properties)`; Sentry init on app start.
      Done: unit tests assert log structure + PostHog event format; manual Sentry test event lands in Sentry dashboard.

- [x] **T015a — OpenTelemetry instrumentation** *(added in sync-fix Run #1 — DRIFT-L4-001; completed 2026-05-22; 8/8 tests; FastAPI+httpx auto-instrumentors; ConsoleSpanExporter→stdout for Fly logs; PymongoInstrumentor deferred to T012)*
      Paths: apps/api/src/auxd_api/lib/otel.py, apps/api/src/auxd_api/main.py (init), apps/api/pyproject.toml (deps)
      Size: XS
      Deps: T011, T015
      Refs: Constitution P5; plan §15.4; NFR Observability
      Description: Install `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-httpx` + `opentelemetry-instrumentation-asyncpg` (or equivalent Beanie/MongoDB instrumentor). Configure OTLP exporter to stdout (captured by Fly logs at MVP — no dedicated tracing backend per plan §15.4). Spans emitted for all HTTP requests, outbound httpx calls, and DB operations. Service name = `auxd-api`; resource attributes include `deployment.environment`.
      Done: a request hitting `/healthz` produces a structured span in Fly logs containing `trace_id`, `span_id`, and `http.route`. Unit test asserts the OTel provider is registered on app start.

- [x] **T016 — `lib/visibility` (single source of truth for can_read)** *(completed 2026-05-22; 54/54 tests, 100% coverage; Visibility × ViewerRelation matrix via Protocols — no Beanie coupling)*
      Paths: apps/api/src/auxd_api/lib/visibility.py, apps/api/tests/unit/test_visibility.py
      Size: M
      Deps: T012
      Refs: plan §3.3, plan §6; TC-011..014, TC-032
      Description: `async def can_read(viewer, content) -> bool` implementing the full visibility matrix (public / followers-only / private × viewer-is-owner / -follower / -blocked / -anonymous). Use `hypothesis` for property-based test on the full 16-state matrix.
      Done: hypothesis property test exercises all combinations; coverage ≥95% (per plan §16.1 target).

- [x] **T017 — Encrypted token storage utility** *(completed 2026-05-22; 11/11 tests; Fernet/MultiFernet envelope encryption; rotate_to() preserves old keys for transition periods)*
      Paths: apps/api/src/auxd_api/lib/secrets.py, apps/api/tests/unit/test_secrets.py
      Size: S
      Deps: T011
      Refs: plan §4.1, §17.2 (token encryption)
      Description: Envelope encryption helper for OAuth tokens (encrypt with key from Fly secret; rotate-safe).
      Done: round-trip encryption test passes; failure modes handled (missing key, bad ciphertext).

- [x] **T018 — KSUID ID generator** *(completed 2026-05-22; 6/6 tests; svix-ksuid wrapper; chronological-sort guarantee verified)*
      Paths: apps/api/src/auxd_api/lib/ids.py, apps/api/tests/unit/test_ids.py
      Size: XS
      Deps: T011
      Refs: plan §3
      Description: KSUID factory + Beanie field type. KSUIDs sort chronologically; useful for cursor pagination.
      Done: unit test confirms ordered generation.

- [x] **T019 — Session middleware (HMAC cookie + CSRF)** *(completed 2026-05-22 Session 5; lib/sessions.py HMAC-SHA256 token format with payload {u,c,i,e,v}; middleware.py decodes + CSRF-enforces + slides expiry; 401 on tamper/expiry (no silent downgrade); issue_session() helper for login handlers; 23 new tests incl. Done-criterion sign-in/call/sign-out integration)*
      Paths: apps/api/src/auxd_api/lib/sessions.py, apps/api/src/auxd_api/middleware.py
      Size: M
      Deps: T011, T017
      Refs: plan §4.2; NFR Security
      Description: HMAC-signed session cookie (httpOnly, SameSite=Lax, Secure in prod); 30-day sliding expiry; CSRF double-submit cookie. Reject invalid/tampered cookies with 401.
      Done: integration test signs in, makes authenticated call, signs out, verifies invalidation.

- [x] **T020 — Rate-limit middleware (Redis-backed, fail-open)** *(completed 2026-05-22 Session 5; FastAPI dependency factory rate_limit(endpoint, per_ip, per_user); Redis sorted-set sliding window ZREMRANGEBYSCORE+ZCARD+ZADD+EXPIRE; per-user only evaluated when request.state.session present; fail-open with Sentry tag rate_limit.redis_down; silent pass when get_redis() raises (test-env); X-Forwarded-For honoured; 8 new tests)*
      Paths: apps/api/src/auxd_api/lib/rate_limit.py, apps/api/tests/integration/test_rate_limit.py
      Size: M
      Deps: T013, T015
      Refs: NFR Security; plan §1.1 (fail-mode); plan §8.2; pre-impl-review A-004
      Description: Per-user + per-IP rate limits keyed by Redis sorted-sets; configurable per-endpoint. Used by log, follow, review, like endpoints + auth. **Fail-mode (locked in Phase 5C):** when Redis is unreachable, the middleware FAILS OPEN — requests are allowed through and a Sentry alert is emitted with tag `rate_limit.redis_down`. Same fail-open policy applies to the notification rate-limiter (T133). Spotify upstream enforces its own rate limits at the edge, so our limiter is defensive rather than load-bearing.
      Done: integration test bursts an endpoint past limit + receives 429. Additional test: simulate Redis disconnect → assert requests succeed AND Sentry alert fires.

---

## §2 Shared backend models + OpenAPI codegen pipeline

- [x] **T021 — User Document + handle policy fields** *(completed 2026-05-22; full plan §3 schema incl. handle policy/notif prefs/music providers; indexes on handle/email unique + status partial; tests via mongomock-motor)*
      Paths: apps/api/src/auxd_api/modules/users/models.py, apps/api/tests/unit/test_users_model.py
      Size: M
      Deps: T012, T018
      Refs: plan §3, §4.3; FR-029; US-G1; data-model.md User
      Description: Beanie `User` Document with all fields per data-model.md User entity. Includes `auto_prompt_enabled`, `auto_prompt_push_enabled`, `default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log`, `handle_changed_at` (renamed from `last_handle_change` in sync-fix Run #3 L5-004), `created_at`, `deletion_scheduled_for`, `session_version`, `status`. Indexes: handle unique, email unique, status partial.
      Done: model loads; unit test creates/saves/loads a User; indexes confirmed via aggregate explain.

- [x] **T022 — Album Document + identity fields** *(completed 2026-05-22; Album schema incl. mbid/spotify_id sparse-unique indexes; Atlas Search index JSON at apps/api/migrations/atlas_search/albums_index.json — one-time UI apply documented)*
      Paths: apps/api/src/auxd_api/modules/albums/models.py
      Size: M
      Deps: T012, T018
      Refs: plan §3; data-model.md Album
      Description: Beanie `Album` Document with all fields. Indexes: `mbid unique sparse`, `spotify_id unique sparse`. Atlas Search index definition (per plan §11.1) added as a migration artifact (`apps/api/migrations/atlas_search/albums_index.json`).
      Done: model + indexes; Atlas Search index applied to dev cluster (one-time manual via Atlas UI documented).

- [x] **T023 — DiaryEntry + Review + ReviewLike + ReviewEditHistory Documents** *(completed 2026-05-22; 15/15 tests; DiaryEntry.auxed bool, Review.reactions sub-doc, ReviewLike unique (review_id, user_id), ReviewEditHistory 90d TTL on edited_at per FR-030)*
      Paths: apps/api/src/auxd_api/modules/diary/models.py, apps/api/src/auxd_api/modules/reviews/models.py
      Size: M
      Deps: T021, T022
      Refs: plan §3.1; data-model.md; FR-030; sync-fix L3-003 (ReviewEditHistory = 90d audit log)
      Description: Beanie `DiaryEntry` (with `auxed: bool` — Aux is on DiaryEntry only), `Review` (with `reactions.likes_count: int` + `recent_likers`), `ReviewLike` (new in R3 — per-user-per-review record), `ReviewEditHistory` (per-edit version row — `review_id`, `version`, `body_at_time`, `edited_at`, `edited_by`; TTL 90d on `edited_at` per FR-030 audit window). Indexes per plan §3.1 table.
      Done: models + indexes; unit tests on field constraints.

- [x] **T024 — Backlog + BacklogItem Documents** *(completed 2026-05-22; Backlog 1:1 with User, BacklogItem with position/per_item_visibility/notes; tests pure-Pydantic via mongomock conftest)*
      Paths: apps/api/src/auxd_api/modules/backlog/models.py
      Size: S
      Deps: T021, T022
      Refs: plan §3
      Description: Beanie `Backlog` (1:1 with User) + `BacklogItem` with `position`, `per_item_visibility`, `notes`.
      Done: models; backlog auto-create on first user access.

- [x] **T025 — Follow + FollowRequest + Block Documents** *(completed 2026-05-22; Follow/FollowRequest/Block models + state enums; compound unique indexes; cascade-on-block deferred to T101 service layer per plan §6.2)*
      Paths: apps/api/src/auxd_api/modules/social/models.py
      Size: S
      Deps: T021
      Refs: plan §3.1; sync-fix L3-002 (FollowRequest = private-profile pending queue, US-G2 infra)
      Description: Beanie `Follow` (state: accepted [default for public profiles] / pending / rejected — kept on the Follow doc itself for transition-history) + `FollowRequest` (separate collection — `requester_id`, `requestee_id`, `status: pending/accepted/declined/expired`, `created_at`, `responded_at`) + `Block`. Compound unique indexes; cascade-resolve on block (Block creation dissolves any existing Follow + any pending FollowRequest in either direction).
      Done: models + unique constraints + cascade trigger covered by integration test; FollowRequest status transitions covered by unit test.

- [x] **T026 — Report + Notification + NotificationPreferences + FailedEmail Documents** *(completed 2026-05-22; 18/18 tests; 18-value NotificationType enum; Notification 90d TTL; Report.target_type incl. missing_album; FailedEmail as T135 write target; NotificationPreferences dedupe with T021 reconciled)*
      Paths: apps/api/src/auxd_api/modules/moderation/models.py, apps/api/src/auxd_api/modules/notifications/models.py
      Size: M
      Deps: T021
      Refs: plan §3.1; plan §1.1.1 PostMark row; notification-taxonomy.md; sync-fix L4-003 (FailedEmail)
      Description: `Report` (target_type/target_id, status, resolution_note — target_type enum extended with `missing_album` per sync-fix L3-006); `Notification` (user_id, type, payload, channel_dispatch_state, read_at, TTL 90d); `NotificationPreferences` (embedded on User per plan §3 — model the embedded sub-document explicitly); `FailedEmail` (user_id, notification_type, payload, attempted_at, last_error — write target for T135 failure-mode wiring). 18 active notification types as `NotificationType` enum.
      Done: models + TTL index on Notification; FailedEmail covered by integration test in T135.

- [x] **T027 — JustFinishedPrompt + SuggestedFollow + CriticSeed Documents** *(completed 2026-05-22; 13/13 tests; JustFinishedPrompt TTL partial-filter (state=pending → 24h expiry), retains LOGGED/DISMISSED for S-B6 30d cooldown + attribution analytics; SuggestedFollow sparse dismissed_at index; CriticSeed strict unique on user_id + separate partial-active index for fast "active critics" reads — sync-fix Run #3 L5-005 clarified intent vs initial status note)*
      Paths: apps/api/src/auxd_api/modules/prompts/models.py, apps/api/src/auxd_api/modules/seeding/models.py
      Size: M
      Deps: T021, T022
      Refs: plan §3
      Description: `JustFinishedPrompt` (state, detected_at, TTL 24h on pending), `SuggestedFollow` (score, reason enum, dismissed_at), `CriticSeed` (active, priority, genre_signature, public_bio, notes — sync-fix Run #3 L5-005 replaced earlier `category`/`description` sketch with the richer code shape).
      Done: models + TTL configured.

- [x] **T028 — OpenAPI → TS type codegen pipeline** *(completed 2026-05-22 Session 5; packages/shared-types/scripts/codegen.sh dumps app.openapi() in-process and pipes through openapi-typescript 7.13 → src/api.ts; pnpm scripts codegen + codegen:check; .github/workflows/codegen.yml fails PR on stale TS via git diff --exit-code; src/index.ts re-exports paths/components/operations; initial api.ts committed)*
      Paths: packages/shared-types/package.json, packages/shared-types/scripts/codegen.sh, .github/workflows/codegen.yml
      Size: S
      Deps: T003, T011
      Refs: plan §7.3
      Description: Pipeline that pulls FastAPI's `/openapi.json` at build-time and runs `openapi-typescript` to generate TS types into `packages/shared-types/src/`. Triggered on backend changes via CI.
      Done: a backend schema change produces a TS diff in shared-types; frontend consumes from `@auxd/shared-types`.

- [x] **T029 — Pydantic settings + env validation** *(completed 2026-05-22; 8/8 tests; Environment + LogLevel enums; base64-key validators; conditional Spotify-secret enforcement; emit_startup_audit log)*
      Paths: apps/api/src/auxd_api/settings.py
      Size: S
      Deps: T011
      Refs: plan §17.2
      Description: `Settings` class with all required env vars, validated at app start; missing values fail loudly with helpful messages. Document each env var in `apps/api/.env.example`.
      Done: app refuses to start without required env; happy-path startup writes a config audit log line.

- [ ] **T030 — Migration runner skeleton**
      Paths: apps/api/src/auxd_api/migrations/__init__.py, apps/api/src/auxd_api/migrations/runner.py
      Size: S
      Deps: T012
      Refs: Constitution P2; plan §3
      Description: Migration runner that reads `_schema_version` on documents and lazy-upgrades. Initial migration `001_initial.py` is a no-op (seeds schema_version=1 on existing docs). Pattern documented for future migrations.
      Done: runner executes on app boot; no-op migration completes.

---

## §3 Frontend foundation

- [ ] **T031 — Next.js 15 App Router skeleton**
      Paths: apps/web/src/app/layout.tsx, apps/web/src/app/page.tsx, apps/web/next.config.ts, apps/web/tailwind.config.ts
      Size: S
      Deps: T003
      Refs: plan §1.2, §7.1
      Description: App Router skeleton with root layout; Tailwind configured; placeholder home page.
      Done: `pnpm --filter @auxd/web dev` serves the page.

- [ ] **T032 — shadcn/ui setup + design tokens**
      Paths: apps/web/components.json, apps/web/src/components/ui/*, apps/web/src/lib/utils.ts
      Size: S
      Deps: T031
      Refs: plan §2; NFR Accessibility
      Description: Init shadcn/ui via CLI; copy initial component set (Button, Sheet, Dialog, Toast, Input, Select, Tabs, Avatar, Badge, Form). Tailwind config defines design tokens (color palette tuned for music — TBD with founder).
      Done: a Button renders correctly; dark mode toggle works.

- [ ] **T033 — TanStack Query setup + API client**
      Paths: apps/web/src/lib/query-client.ts, apps/web/src/lib/api-client.ts, apps/web/src/providers.tsx
      Size: S
      Deps: T031, T028
      Refs: plan §7.3
      Description: QueryClient provider; typed fetch wrapper consuming `@auxd/shared-types`; React Query DevTools in dev. Standard `useApiQuery` and `useApiMutation` helpers.
      Done: a hello-world query against `/healthz` displays the response.

- [ ] **T034 — Zustand setup for client state**
      Paths: apps/web/src/stores/auth.ts, apps/web/src/stores/ui.ts
      Size: XS
      Deps: T031
      Refs: plan §7.2
      Description: Auth store (sanitized user object); UI store (log-sheet open/closed, feed sort preference). Hydrate from server components on first load.
      Done: stores load; toggling log-sheet store updates a test UI.

- [ ] **T035 — React Hook Form + Zod setup**
      Paths: apps/web/src/lib/forms.ts, apps/web/src/components/ui/form.tsx
      Size: XS
      Deps: T032
      Refs: plan §2
      Description: Hook Form + Zod resolver wired into shadcn/ui Form component. Reusable form-error component.
      Done: a sample form validates and submits.

- [ ] **T036 — Sentry + PostHog (frontend)**
      Paths: apps/web/src/lib/sentry.ts, apps/web/src/lib/posthog.ts, apps/web/instrumentation.ts
      Size: S
      Deps: T031, T007
      Refs: plan §15.1, §15.2
      Description: Sentry SDK with source-map upload on Vercel deploy; PostHog client (server + browser, single-instance singleton). Manual capture helpers.
      Done: a thrown error reaches Sentry; a test PostHog event reaches PostHog.

- [ ] **T037 — Authenticated layout (post-auth shell)**
      Paths: apps/web/src/app/(app)/layout.tsx, apps/web/src/components/nav/bottom-tabs.tsx
      Size: M
      Deps: T031, T032, T034
      Refs: spec.md §4 user stories cluster G; plan §7.1
      Description: Authenticated route group with redirect-to-login if no session. Bottom-tab nav (Home, Up Next, Discover, Profile). Persistent "+" Log FAB.
      Done: navigating to `/` redirects to `/login` when unauthenticated; otherwise renders the shell.

- [ ] **T038 — Public layout (pre-auth pages)**
      Paths: apps/web/src/app/(auth)/layout.tsx, apps/web/src/app/(auth)/login/page.tsx, apps/web/src/app/(auth)/signup/page.tsx
      Size: M
      Deps: T031, T032, T035
      Refs: US-A1; FR-001
      Description: Public layout for login/signup. Forms wired but submit is a no-op (T053 wires real auth).
      Done: pages render and forms validate locally.

- [ ] **T039 — Onboarding route group skeleton**
      Paths: apps/web/src/app/(onboarding)/layout.tsx, apps/web/src/app/(onboarding)/step-1/page.tsx
      Size: S
      Deps: T037
      Refs: spec.md §4 user stories cluster A
      Description: Route group for onboarding steps with progress indicator; step routing wired (steps fleshed out in §11).
      Done: scaffolded routes navigate sequentially.

- [ ] **T040 — Playwright E2E setup**
      Paths: apps/web/playwright.config.ts, apps/web/tests/e2e/smoke.spec.ts, .github/workflows/e2e.yml
      Size: M
      Deps: T031, T009
      Refs: plan §16; spec.md §10 E2E
      Description: Playwright installed; config targets Vercel preview deploy. Smoke test asserts landing page renders. Full E2E suite (TC-E2E-001..013) added per-feature in their respective tasks.
      Done: smoke test runs in CI against PR preview deploy.

---

## §4 Providers — Spotify + MusicBrainz (contract-test-first per Constitution P4)

- [ ] **T041 — MusicProvider + CatalogProvider protocols**
      Paths: apps/api/src/auxd_api/providers/base.py
      Size: S
      Deps: T014, T015
      Refs: Constitution P6; plan §5.1
      Description: Abstract `MusicProvider` and `CatalogProvider` Protocol classes defining the interface methods (per plan §5.1). NO concrete implementations yet — that's enforcement of P6 (provider abstraction).
      Done: protocols compile; mypy strict passes.

- [ ] **T042 — Spotify provider — contract tests (FAIL state) [TEST-FIRST]**
      Paths: apps/api/tests/contract/test_spotify_recently_played.py, apps/api/tests/contract/test_spotify_album_detail.py, apps/api/tests/contract/test_spotify_search.py, apps/api/tests/contract/test_spotify_currently_playing.py
      Size: M
      Deps: T041, T002
      Refs: Constitution P4; plan §16.3
      Description: Contract tests against Spotify's actual API (Development Mode quota) covering all methods auxd uses. Tests run as `pytest -m contract` and are excluded from normal CI but run nightly + on main. At this stage they MUST FAIL (no implementation yet) — that's the test-first pattern.
      Done: pytest collects 12+ tests; all fail with import/implementation errors (expected).

- [ ] **T043 — Spotify provider — implementation**
      Paths: apps/api/src/auxd_api/providers/spotify/__init__.py, apps/api/src/auxd_api/providers/spotify/client.py, apps/api/src/auxd_api/providers/spotify/oauth.py, apps/api/src/auxd_api/providers/spotify/mappings.py
      Size: L
      Deps: T042, T014, T015, T017
      Refs: FR-002, FR-003, FR-026; spec.md §1.3 (provider abstraction)
      Description: Concrete `SpotifyMusicProvider` implementing `MusicProvider` protocol. OAuth helper for code exchange + refresh. `httpx.AsyncClient` with resilience transport (circuit breaker + retry + timeout per T014). Pydantic models for Spotify responses → internal types.
      Done: contract tests (T042) PASS against Spotify Dev Mode.

- [ ] **T044 — Spotify provider — token refresh + revoke handling**
      Paths: apps/api/src/auxd_api/providers/spotify/oauth.py, apps/api/tests/integration/test_spotify_oauth.py
      Size: M
      Deps: T043
      Refs: FR-002, FR-027 (disconnect immutability)
      Description: Refresh token flow; handle 401 → refresh → retry; detect revoke (refresh fails) → mark `MusicProvider.status = revoked` and emit N-011 notification. On revoke, diary persists (immutability per Q19).
      Done: integration test simulates token expiry + refresh + revoke; immutability verified.

- [ ] **T045 — Spotify provider — `get_recently_played`**
      Paths: covered in T043
      Size: (sub-task of T043)
      Refs: FR-003, US-A3
      Description: Paginated recently-played fetch; dedupe to album-grain (≥4 tracks from same album in window = "album listen").
      Done: covered by T042 contract tests.

- [ ] **T046 — Spotify provider — `search_albums`**
      Paths: covered in T043
      Size: (sub-task of T043)
      Refs: FR-005, US-F2
      Description: Album search by query; market parameter handling; pagination.
      Done: covered by T042 contract tests.

- [ ] **T047 — Spotify provider — `get_album` + tracklist**
      Paths: covered in T043
      Size: (sub-task of T043)
      Refs: FR-010, US-F1
      Description: Single-album fetch with tracklist + metadata; cover-art URL extraction.
      Done: covered by T042 contract tests.

- [ ] **T048 — MusicBrainz catalog provider — contract tests (FAIL state)**
      Paths: apps/api/tests/contract/test_musicbrainz_release_group_lookup.py
      Size: S
      Deps: T041
      Refs: Constitution P4
      Description: Contract test for MusicBrainz `lookup_by_mbid` and Spotify ID → MBID reconciliation.
      Done: tests fail (expected, no implementation).

- [ ] **T049 — MusicBrainz catalog provider — implementation**
      Paths: apps/api/src/auxd_api/providers/musicbrainz/__init__.py, apps/api/src/auxd_api/providers/musicbrainz/client.py
      Size: M
      Deps: T048, T014
      Refs: plan §5; decision-log Q15
      Description: `MusicBrainzCatalogProvider`. Rate-limited to 1 req/sec per IP (MusicBrainz policy). Reconciliation strategy: query by artist + title, match best release-group MBID.
      Done: contract tests (T048) PASS.

- [ ] **T050 — Resilience transport — httpx custom Transport**
      Paths: apps/api/src/auxd_api/lib/http_transport.py
      Size: M
      Deps: T014
      Refs: Constitution P1
      Description: Custom `httpx.AsyncBaseTransport` that wraps requests with `lib/resilience` (circuit breaker + retry + timeout). Used by all provider clients.
      Done: unit tests assert transport applies all three policies.

- [ ] **T051 — Provider observability instrumentation**
      Paths: apps/api/src/auxd_api/providers/spotify/client.py, apps/api/src/auxd_api/providers/musicbrainz/client.py
      Size: S
      Deps: T043, T049, T015
      Refs: Constitution P5; NFR Observability
      Description: Every provider call emits `log_call(provider, endpoint, latency_ms, status, request_id)` via lib/observability.
      Done: log lines present; assertion test verifies structure.

- [ ] **T052 — Provider error taxonomy**
      Paths: apps/api/src/auxd_api/providers/errors.py
      Size: S
      Deps: T041
      Refs: plan §5
      Description: `ProviderError`, `ProviderUnavailable`, `ProviderRateLimited`, `ProviderAuthRevoked`, `ProviderNotFound`. Mapped to user-facing API responses appropriately (503, 429, 401, 404).
      Done: error taxonomy with tests asserting mapping.

---

## §5 Auth module + onboarding entry

- [ ] **T053 — Email/password signup + login endpoints**
      Paths: apps/api/src/auxd_api/modules/auth/routes.py, apps/api/src/auxd_api/modules/auth/service.py, apps/api/tests/integration/test_auth_email.py
      Size: M
      Deps: T021, T019, T020
      Refs: US-A1; FR-001
      Description: `POST /api/v1/auth/signup` (email + password + handle), `POST /api/v1/auth/login` (email + password). bcrypt cost 12. Handle validation: 3–24 chars, `/^[a-z0-9_]+$/`, unique. Suggest 3 alternatives on collision.
      Done: integration tests cover happy path + 5 error cases (handle taken, email taken, weak password, invalid handle chars, account suspended).

- [ ] **T054 — Spotify OAuth signup/login shortcut**
      Paths: apps/api/src/auxd_api/modules/auth/spotify_oauth.py, apps/api/tests/integration/test_spotify_signup.py
      Size: M
      Deps: T053, T043, T044
      Refs: US-A1, US-A2; FR-001, FR-002
      Description: `GET /api/v1/auth/spotify/authorize` (returns PKCE-encoded redirect URL); `GET /api/v1/auth/spotify/callback` (exchanges code, creates User if new, attaches `MusicProvider` sub-doc). Auto-handle from Spotify display_name with collision-resolve.
      Done: integration test simulates OAuth callback; account created; session cookie issued.

- [ ] **T055 — Connect-Spotify-later flow (post-signup)**
      Paths: apps/api/src/auxd_api/modules/auth/service.py, apps/api/tests/integration/test_connect_spotify.py
      Size: M
      Deps: T054, T044
      Refs: US-A2; FR-002, FR-027; decision-log Q12
      Description: `POST /api/v1/users/me/integrations/spotify/connect` → returns OAuth URL. Callback attaches `MusicProvider` to existing User. Triggers auto-import (T117).
      Done: integration test: skip Spotify at signup → use product manually → connect later → diary back-fills with 30 days.

- [ ] **T056 — Disconnect Spotify (immutability)**
      Paths: apps/api/src/auxd_api/modules/auth/service.py, apps/api/tests/integration/test_disconnect_spotify.py
      Size: S
      Deps: T055
      Refs: FR-027; decision-log Q19; TC-022
      Description: `DELETE /api/v1/users/me/integrations/spotify` → marks `MusicProvider.status = disconnected`. ALL DiaryEntry / Rating / Review / Aux / Like / Follow persist untouched. Reconnect resumes without gap back-fill.
      Done: TC-022 integration test passes.

- [ ] **T057 — Handle change policy + reserved-squat list**
      Paths: apps/api/src/auxd_api/modules/auth/handle_service.py, apps/api/data/reserved_handles.txt, apps/api/tests/unit/test_handle_policy.py
      Size: M
      Deps: T021
      Refs: US-G1; FR-029; decision-log Q16; TC-023, TC-024
      Description: `change_handle(user, new_handle)` enforces: 30-day post-creation lock, ≤1 change per 30 days, reserved-squat rejection (200 names committed in `data/reserved_handles.txt`), unique check with 3 suggestions on collision. Old handle stored in `handle_redirects` for 90 days.
      Done: TC-023 + TC-024 unit tests pass; redirect on old URL works (T060 wires the redirect at routing layer).

- [ ] **T058 — Account deletion (30-day grace) + cascade**
      Paths: apps/api/src/auxd_api/modules/auth/service.py, apps/api/src/auxd_api/workers/deletion_cascade.py, apps/api/tests/integration/test_account_deletion.py
      Size: M
      Deps: T021, T023, T024, T025, T026
      Refs: US-G5; FR-019; TC-029
      Description: `POST /api/v1/users/me/delete` sets `status=deleted` + `deletion_scheduled_for = now + 30d`. arq daily cron finds users past their scheduled date and cascade-hard-deletes all owned content. Cancellation via `POST /api/v1/users/me/delete/cancel`.
      Done: TC-029 integration test: schedule deletion → see banner → cancel within 30d → account restored. Or: do not cancel → after 30d, all data is gone.

- [ ] **T059 — Logout (current session + logout-all-devices)**
      Paths: apps/api/src/auxd_api/modules/auth/service.py
      Size: XS
      Deps: T053, T019
      Refs: NFR Security
      Description: `POST /api/v1/auth/logout` (clear cookie); `POST /api/v1/auth/logout-all` (increment `session_version` invalidating all prior cookies).
      Done: unit test confirms behavior.

- [ ] **T060 — Handle redirect routing**
      Paths: apps/web/src/middleware.ts, apps/api/src/auxd_api/modules/auth/routes.py
      Size: S
      Deps: T057
      Refs: FR-029
      Description: Frontend middleware intercepts `/@oldhandle` requests; backend lookup returns new handle if redirect exists (≤90 days post-change); 301 redirect. Otherwise 404.
      Done: unit + integration tests pass.

- [ ] **T061 — Signup + login UI**
      Paths: apps/web/src/app/(auth)/signup/page.tsx, apps/web/src/app/(auth)/login/page.tsx, apps/web/tests/e2e/auth.spec.ts
      Size: M
      Deps: T038, T053, T054
      Refs: US-A1; FR-001
      Description: Wire signup + login forms to backend. Spotify OAuth button initiates flow. Error handling for all 5 error cases from T053.
      Done: E2E test signs up via email + via Spotify OAuth.

- [ ] **T062 — Auth E2E + session persistence**
      Paths: apps/web/tests/e2e/session.spec.ts
      Size: S
      Deps: T061
      Refs: NFR Security
      Description: Test that session survives navigation, page refresh, and respects expiry.
      Done: E2E passes.

---

## §6 Albums + Search

- [ ] **T063 — Album identity normalization service**
      Paths: apps/api/src/auxd_api/modules/albums/identity.py, apps/api/tests/unit/test_album_identity.py
      Size: M
      Deps: T022, T043, T049
      Refs: US-F1; FR-010; decision-log Q15, Q21; TC-008, TC-009, TC-010
      Description: `resolve_identity(spotify_id=None, mbid=None)` → canonical Album. If MBID known → use it; else Spotify ID; else create `candidate` Album flagged for MBID reconciliation. Lazy-fetch from providers; cache 7d.
      Done: TC-008/009/010 unit tests pass.

- [ ] **T064 — Album cache + TTL refresh worker**
      Paths: apps/api/src/auxd_api/workers/album_cache_refresh.py
      Size: S
      Deps: T063, T013
      Refs: NFR Spotify rate limits
      Description: Daily arq job that finds Albums with `cache_expires_at < now()` and refreshes from Spotify (rate-limited).
      Done: worker runs; refresh observed.

- [ ] **T065 — MBID reconciliation worker**
      Paths: apps/api/src/auxd_api/workers/mbid_reconcile.py
      Size: S
      Deps: T063, T049
      Refs: decision-log Q21
      Description: Periodic job that finds Albums with `candidate=true` and attempts MBID reconciliation via MusicBrainz. On match, merge candidate into canonical.
      Done: worker runs; candidate records reconcile over time.

- [ ] **T066 — Edition aggregation (release-group → editions)**
      Paths: apps/api/src/auxd_api/modules/albums/editions.py, apps/api/tests/unit/test_editions.py
      Size: M
      Deps: T063
      Refs: US-F1; FR-028; decision-log Q15; TC-010
      Description: Group albums by release-group MBID; expose "All editions" view that aggregates ratings/reviews/likes across editions. Edition selector returns list of editions for a release-group.
      Done: TC-010 unit test passes.

- [ ] **T067 — Album detail endpoint**
      Paths: apps/api/src/auxd_api/modules/albums/routes.py, apps/api/tests/integration/test_album_detail.py
      Size: M
      Deps: T063, T066, T016
      Refs: US-F1; FR-010
      Description: `GET /api/v1/albums/{id}` returns album + tracklist + my history + friends-who-rated-and-auxed + public reviews + edition list. Visibility-filtered via lib/visibility.
      Done: integration test covers logged-in/anonymous/blocked/private cases.

- [ ] **T068 — Atlas Search index for albums**
      Paths: apps/api/migrations/atlas_search/albums_index.json, docs/atlas-search-setup.md
      Size: S
      Deps: T022
      Refs: plan §11.1; FR-005
      Description: Index definition with `lucene.standard` analyzer + edgeNgram on title; popularity boost. Applied to Atlas via UI or `atlas-cli`. Documented for future migrations.
      Done: search query returns relevant results.

- [ ] **T069 — Search endpoint (Atlas + Spotify fallback merge)**
      Paths: apps/api/src/auxd_api/modules/search/routes.py, apps/api/src/auxd_api/modules/search/service.py, apps/api/tests/integration/test_search.py
      Size: M
      Deps: T068, T043
      Refs: US-F2; FR-005; TC-031
      Description: `GET /api/v1/search?q=...&type=album` → Atlas Search results merged with Spotify search (Spotify only if Atlas returns <5 results). Debounce on client side; results sorted by relevance.
      Done: TC-031 integration test passes; results in <200ms p95.

- [ ] **T070 — Album detail page (frontend, SSR)**
      Paths: apps/web/src/app/(app)/album/[id]/page.tsx, apps/web/src/components/album-detail/*
      Size: L
      Deps: T067, T037
      Refs: US-F1; FR-010, FR-028; wireframes/04-album-detail.html
      Description: SSR page rendering wireframes/04 design. Edition selector chip + dropdown. Friends section (avatars + ratings + 🏅 Aux'd). Ratings histogram. Reviews list with sort selector (Newest / Most Liked / Highest-Rated — wired in T093). Log + Up Next + Listen-on-Spotify CTAs. Open Graph meta tags.
      Done: page renders matching wireframe; OG card previews correctly in social shares.

- [ ] **T071 — Search page + UI**
      Paths: apps/web/src/app/(app)/search/page.tsx, apps/web/src/components/search/*
      Size: M
      Deps: T069
      Refs: US-F2; FR-005
      Description: Search page with input + autocomplete; 200ms debounce; "Report missing album" link on empty state.
      Done: E2E test covers typed query → results → album navigation.

- [ ] **T072 — Cover-art proxy (route handler)**
      Paths: apps/web/src/app/api/cover/[size]/[albumId]/route.ts
      Size: S
      Deps: T067
      Refs: plan §17.5; DM-2
      Description: Next.js route handler proxying Spotify CDN with caching headers (`Cache-Control: public, max-age=604800`). Optional blurhash placeholder generation.
      Done: proxy serves cover art; CDN caching verified.

---

## §7 Diary + Log sheet — THE WEDGE INTERACTION

- [ ] **T073 — Diary log endpoint (Aux-bool included)**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py, apps/api/src/auxd_api/modules/diary/service.py, apps/api/tests/integration/test_diary_logging.py
      Size: M
      Deps: T023, T021, T063
      Refs: US-B1, US-B2, US-B3; FR-004; TC-001, TC-002, TC-003
      Description: `POST /api/v1/diary/entries` with `album_id`, `rating` (optional, 0.5–5.0 in halves), `auxed` (bool), `review_body` (optional), `visibility`. Server measures end-to-end commit time; emit PostHog `log.commit` event with `duration_ms`. Idempotent: same album logged twice in 60sec returns existing entry (avoids double-tap dupes).
      Done: TC-001, TC-002, TC-003 pass.

- [ ] **T074 — Diary read endpoint (chronological diary)**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py
      Size: S
      Deps: T073, T016
      Refs: US-E2; FR-007
      Description: `GET /api/v1/users/{handle}/diary?cursor=...&limit=25` reverse-chrono; visibility-filtered. Optional filter param: `auxed=true` for "Aux'd" tab.
      Done: integration test covers visibility matrix.

- [ ] **T075 — Diary edit / delete endpoints**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py, apps/api/tests/integration/test_diary_edit.py
      Size: M
      Deps: T073
      Refs: US-B5; FR-004
      Description: `PATCH /api/v1/diary/entries/{id}` (rating/auxed/review/visibility editable). `DELETE` is soft-delete with 30d recovery. Editor must be owner.
      Done: integration tests cover edit + soft-delete + recovery + hard-delete after 30d.

- [ ] **T076 — Relisten support (multiple entries for same album)**
      Paths: covered in T073
      Size: (sub-task)
      Refs: US-B4; TC-003
      Description: Multiple DiaryEntry records per (user, album) allowed; album-detail "my history" shows all prior logs.
      Done: TC-003 covered.

- [ ] **T077 — Log sheet component (THE wedge interaction)**
      Paths: apps/web/src/components/log-sheet/index.tsx, apps/web/src/components/log-sheet/rating-widget.tsx, apps/web/src/components/log-sheet/aux-toggle.tsx, apps/web/src/components/log-sheet/review-editor.tsx
      Size: L
      Deps: T037, T073, T032
      Refs: US-B1, US-B2, US-B3; FR-004; wireframes/03-log-sheet.html
      Description: Bottom-sheet component. ALWAYS-MOUNTED in app shell layout (hidden until open) to avoid first-tap render cost. Rating widget = ½-star tap-or-drag. Aux toggle = 🏅 medal. Review collapsed by default; tap to expand. Visibility select defaults to user prefs. Commit fires `POST /api/v1/diary/entries` and measures duration. PostHog event `log.commit` with duration_ms.
      Done: E2E test logs an album in <8 seconds; commit duration_ms tracked.

- [ ] **T078 — Persistent + Log button (FAB in shell)**
      Paths: apps/web/src/components/nav/log-fab.tsx, apps/web/src/app/(app)/layout.tsx
      Size: XS
      Deps: T077, T037
      Refs: US-B1
      Description: Persistent "+" button in bottom-right of app shell; opens log sheet.
      Done: button present on all authenticated routes.

- [ ] **T079 — Prefill album from Spotify recently-played (Log sheet)**
      Paths: apps/web/src/components/log-sheet/album-prefill.tsx, apps/api/src/auxd_api/modules/diary/routes.py
      Size: M
      Deps: T077, T043
      Refs: US-B1; FR-004; UJ-1 decision
      Description: When Spotify connected: fetch most-recently-FINISHED album (per UJ-1 — not most-recently-played track) on log-sheet open; pre-fill album card. User can tap "Change" to search.
      Done: prefill works; analytics tracks % of logs that accept prefill (PostHog `log.prefill_accepted`).

- [ ] **T080 — Diary view on profile**
      Paths: apps/web/src/app/(app)/@[handle]/page.tsx, apps/web/src/components/diary/*
      Size: M
      Deps: T074, T037
      Refs: US-E2; FR-007
      Description: Profile page with reverse-chrono diary view; "Aux'd" filter tab. Pagination with cursor.
      Done: profile page renders.

- [ ] **T081 — "My history" on album detail page**
      Paths: apps/web/src/components/album-detail/my-history.tsx
      Size: S
      Deps: T070, T074
      Refs: US-B4
      Description: Shows all prior diary entries for the album by current user; allows expanding to see ratings + dates.
      Done: section renders.

- [ ] **T082 — Edit diary entry UI**
      Paths: apps/web/src/components/diary/edit-entry.tsx
      Size: S
      Deps: T080, T075
      Refs: US-B5
      Description: Opens log sheet pre-filled with the entry's current values; PATCH on save.
      Done: edit flow works end-to-end.

- [ ] **T083 — Soft-delete + undo toast**
      Paths: apps/web/src/components/diary/delete-confirmation.tsx
      Size: S
      Deps: T082
      Refs: US-B5
      Description: Confirm-delete modal with text-confirm; undo via Toast for 8 seconds (server-side recovery within 30d also possible).
      Done: undo path works.

- [ ] **T084 — Wedge NFR validation (commit time <8s)**
      Paths: apps/web/tests/e2e/log-wedge.spec.ts, apps/api/tests/integration/test_log_perf.py
      Size: S
      Deps: T077, T079
      Refs: spec.md §6.1 NFR; TC-001; TC-E2E-003
      Description: E2E test measures commit time across 10 trials; asserts p95 <8s. Backend integration test asserts server-side handling <500ms p95.
      Done: NFR target verified.

---

## §8 Reviews + Likes + sort

- [ ] **T085 — Review create endpoint**
      Paths: apps/api/src/auxd_api/modules/reviews/routes.py, apps/api/src/auxd_api/modules/reviews/service.py
      Size: M
      Deps: T023, T073
      Refs: US-C1; FR-011
      Description: `POST /api/v1/reviews` (body, visibility) linked to a DiaryEntry. Markdown-safe rendering (allow bold, italic, line breaks; no images, no scripts). ≥1 char minimum, NO soft prompt (per decision #5 / R3).
      Done: integration test creates a review; markdown sanitization verified.

- [ ] **T086 — Review edit + audit log**
      Paths: apps/api/src/auxd_api/modules/reviews/service.py, apps/api/tests/integration/test_review_edit.py
      Size: M
      Deps: T085
      Refs: US-C3; FR-030; TC-025
      Description: `PATCH /api/v1/reviews/{id}` updates body. Public surface shows latest + "edited" badge with timestamp. Internal `review_edits` collection stores prior versions for 90 days with hash for tamper detection.
      Done: TC-025 integration passes.

- [ ] **T087 — Review delete (with cascading reaction cleanup)**
      Paths: apps/api/src/auxd_api/modules/reviews/service.py
      Size: S
      Deps: T085
      Refs: DM-5
      Description: Soft-delete review with 30d grace; on hard-delete cascade-delete `ReviewLike` records.
      Done: integration test confirms cascade.

- [ ] **T088 — Like-review endpoint (idempotent toggle)**
      Paths: apps/api/src/auxd_api/modules/reviews/likes_service.py, apps/api/tests/unit/test_review_likes.py
      Size: M
      Deps: T085
      Refs: US-C4; FR-031; TC-015, TC-016
      Description: `POST /api/v1/reviews/{id}/like` toggles. Creates `ReviewLike`; increments `Review.reactions.likes_count`; emits N-004 notification. Reject if liker == reviewer (TC-016). Reject if already-liked (idempotent return current state). Un-like deletes record + decrements counter (no notification).
      Done: TC-015 + TC-016 pass.

- [ ] **T089 — List reviews endpoint with sort**
      Paths: apps/api/src/auxd_api/modules/reviews/routes.py, apps/api/tests/unit/test_review_sort.py
      Size: M
      Deps: T088, T016
      Refs: US-C2; FR-032; TC-017
      Description: `GET /api/v1/albums/{id}/reviews?sort=newest|most_liked|highest_rated&cursor=...` with primary tier (friends → public → critic-seed) + sort within tier. Visibility-filtered.
      Done: TC-017 passes.

- [ ] **T090 — Review card component (with Like button)**
      Paths: apps/web/src/components/review-card/index.tsx, apps/web/src/components/review-card/like-button.tsx
      Size: M
      Deps: T037, T088
      Refs: US-C4
      Description: Review card showing reviewer (avatar + handle + Critic suffix if seed), stars, "edited" badge if applicable, body with read-more, 👍 Like button + count. Like is optimistic.
      Done: component renders; Like toggle works.

- [ ] **T091 — Review composition UI (in log sheet)**
      Paths: covered in T077 (log-sheet/review-editor.tsx)
      Size: (sub-task)
      Refs: US-C1
      Description: Textarea with markdown hint; no length nudges.
      Done: covered.

- [ ] **T092 — Edit + delete review UI**
      Paths: apps/web/src/components/review-card/edit-review.tsx
      Size: S
      Deps: T090, T086
      Refs: US-C3
      Description: Edit-review modal; soft-delete with undo toast.
      Done: flow works.

- [ ] **T093 — Reviews list on album detail (with sort selector)**
      Paths: apps/web/src/components/album-detail/reviews-list.tsx
      Size: M
      Deps: T070, T089, T090
      Refs: US-C2; FR-032; TC-E2E-006
      Description: Reviews list embedded in album detail. Sort selector (Newest default / Most Liked / Highest-Rated) persisted to Zustand per-device. Tier ordering enforced.
      Done: TC-E2E-006 passes.

- [ ] **T094 — "My reviews" on profile**
      Paths: apps/web/src/app/(app)/@[handle]/reviews/page.tsx
      Size: S
      Deps: T089
      Refs: cross-cutting profile
      Description: Reviews-only view of a user's profile.
      Done: page renders.

---

## §9 Backlog (Up Next)

- [ ] **T095 — Backlog CRUD endpoints**
      Paths: apps/api/src/auxd_api/modules/backlog/routes.py, apps/api/src/auxd_api/modules/backlog/service.py
      Size: M
      Deps: T024, T021
      Refs: US-D1, US-D2; FR-006
      Description: `POST /api/v1/users/me/backlog/items` (add album); `DELETE` (remove); `PATCH .../reorder`; `GET .../items` paginated. Backlog auto-created on first access.
      Done: integration tests cover all paths.

- [ ] **T096 — Auto-remove-on-log behavior**
      Paths: apps/api/src/auxd_api/modules/diary/service.py
      Size: S
      Deps: T073, T095
      Refs: US-D3
      Description: On `log_entry`, if album is in user's backlog AND `User.keep_backlog_after_log == false` (default), remove from backlog. Toast confirms.
      Done: integration test confirms behavior.

- [ ] **T097 — Up Next page (frontend)**
      Paths: apps/web/src/app/(app)/up-next/page.tsx, apps/web/src/components/up-next/*
      Size: M
      Deps: T095, T037
      Refs: US-D1, US-D2; FR-006
      Description: Backlog list with drag-reorder (using `@dnd-kit/sortable`), per-item context menu (Remove, Listen on Spotify, Open album, Edit blurb).
      Done: page renders; drag works on mobile + web.

- [ ] **T098 — Add-to-backlog from album detail**
      Paths: apps/web/src/components/album-detail/up-next-button.tsx
      Size: XS
      Deps: T070, T095
      Refs: US-D1
      Description: "+ Up Next" button on album detail page; toggles add/remove based on current state.
      Done: button works.

- [ ] **T099 — Add-to-backlog from log sheet**
      Paths: covered in T077
      Size: (sub-task)
      Refs: US-D1
      Description: Alternative path inside Log sheet to add to backlog instead of logging.
      Done: covered.

- [ ] **T100 — Backlog → Log conversion event**
      Paths: apps/api/src/auxd_api/modules/diary/service.py, apps/web/src/lib/analytics.ts
      Size: XS
      Deps: T096
      Refs: success-metrics: backlog→log conversion
      Description: PostHog event when an album logged was previously in user's backlog; tracks the M3/M6 KPI.
      Done: event emitted with correct properties.

---

## §10 Social graph + Feed

- [ ] **T101 — Follow / unfollow endpoints**
      Paths: apps/api/src/auxd_api/modules/social/routes.py, apps/api/src/auxd_api/modules/social/service.py
      Size: M
      Deps: T025, T021
      Refs: US-E1; FR-008
      Description: `POST /api/v1/users/{handle}/follow`, `DELETE`. Asymmetric. If followee has private profile, create `state=pending` and notify. Emit N-001 + (if pending) N-002.
      Done: integration tests cover all states.

- [ ] **T102 — Block endpoint (+ cascade-resolve follow)**
      Paths: apps/api/src/auxd_api/modules/social/service.py, apps/api/tests/integration/test_blocks.py
      Size: M
      Deps: T101
      Refs: US-G4; FR-014; TC-028
      Description: `POST /api/v1/users/{handle}/block`. Dissolves any Follow in either direction. Hides content from blocker (via lib/visibility).
      Done: TC-028 passes.

- [ ] **T103 — Friends-who-rated-and-auxed endpoint**
      Paths: apps/api/src/auxd_api/modules/feed/service.py
      Size: M
      Deps: T101, T073
      Refs: US-E4; FR-010
      Description: `GET /api/v1/albums/{id}/friends` returns avatars + ratings + Aux'd from followed accounts who have rated this album; sort by rating desc then logged_at desc; visibility-filtered.
      Done: integration test covers visibility matrix.

- [ ] **T104 — Suggested-follow precompute worker**
      Paths: apps/api/src/auxd_api/workers/suggestions_job.py
      Size: L
      Deps: T101, T073
      Refs: US-E5; FR-016
      Description: arq scheduled job (every N hours per user) that scores candidate follows using the algorithm from seeding-strategy §4 (mutual-taste 40%, followed-by-followed 30%, shared-seed 15%, label/genre 10%, recency 5%). Excludes blocked, dismissed (≤30d), already-followed.
      Done: suggestions appear in `/api/v1/users/me/suggestions` for users with ≥5 logged entries.

- [ ] **T105 — Suggested-follow API + dismiss endpoint**
      Paths: apps/api/src/auxd_api/modules/social/routes.py
      Size: S
      Deps: T104
      Refs: US-E5
      Description: `GET /api/v1/users/me/suggestions?limit=5`; `POST /api/v1/users/me/suggestions/{user_id}/dismiss`.
      Done: integration test.

- [ ] **T106 — Home feed endpoint (fan-out-on-read + weighting)**
      Paths: apps/api/src/auxd_api/modules/feed/routes.py, apps/api/src/auxd_api/modules/feed/service.py, apps/api/tests/integration/test_feed.py
      Size: L
      Deps: T101, T073, T085, T016
      Refs: US-E3; FR-009; DM-1
      Description: `GET /api/v1/feed?cursor=...&limit=25&mode=for_you|latest` — implements fan-out-on-read with weighted score (reviews +20%, ★★★★★/★ +15%, top-5-interacted +10%, half-life ~3d). "Latest" mode disables weights. Critic-seed padding when followed-user activity is sparse.
      Done: integration tests cover happy path + sparse-feed + visibility matrix + sort modes.

- [ ] **T107 — Feed performance benchmark (p95 <500ms)**
      Paths: apps/api/tests/perf/test_feed_perf.py
      Size: S
      Deps: T106
      Refs: spec.md §6.1; NFR
      Description: Synthetic load test with ~500 followed users; assert p95 query time <200ms at DB layer (per plan §10.3 fan-out-switch trigger).
      Done: perf test passes; baseline recorded for regression checks.

- [ ] **T108 — Feed UI (home page)**
      Paths: apps/web/src/app/(app)/page.tsx, apps/web/src/components/feed/feed-entry.tsx
      Size: L
      Deps: T106, T037, T032
      Refs: US-E3; FR-009; TC-E2E-004; wireframes/02-home-feed.html
      Description: SSR home feed; entry cards per wireframe (avatar, stars, 🏅 Aux badge if applied, album cover thumb, review snippet, 👍 like count, Listen on Spotify button). "Latest" tab toggle. Infinite scroll via cursor pagination. Lazy-load cover art (Next.js Image with blur placeholder).
      Done: TC-E2E-004 passes.

- [ ] **T109 — Profile + diary page**
      Paths: apps/web/src/app/(app)/@[handle]/page.tsx
      Size: M
      Deps: T080, T101
      Refs: US-E2, US-G1
      Description: Public profile with avatar, display_name, bio, handle, follows/followers counts, ratings histogram, diary tab, reviews tab, Aux'd filter.
      Done: page renders.

- [ ] **T110 — Follow button (with optimistic update)**
      Paths: apps/web/src/components/social/follow-button.tsx
      Size: S
      Deps: T101, T109
      Refs: US-E1
      Description: Follow button with optimistic count update; confirm modal on unfollow.
      Done: works on profile page.

- [ ] **T111 — Block + Report UI**
      Paths: apps/web/src/components/social/block-report-menu.tsx
      Size: M
      Deps: T102
      Refs: US-G4
      Description: Overflow menu on profile/diary entry/review with Block + Report options. Report modal with reason enum + free-text detail.
      Done: works.

- [ ] **T112 — Discover tab (suggestions surface)**
      Paths: apps/web/src/app/(app)/discover/page.tsx
      Size: M
      Deps: T105, T037
      Refs: US-E5
      Description: Discover tab listing suggested follows with reason ("Mutual taste", "Followed by 3 of your follows", etc.). Dismiss button per suggestion.
      Done: page renders.

---

## §11 Onboarding + Auto-import

- [ ] **T113 — Onboarding step 1: Sign up (already covered)**
      Paths: covered in T061
      Size: (sub-task)
      Refs: US-A1
      Description: First step of onboarding routes through signup page.
      Done: covered.

- [ ] **T114 — Onboarding step 2: Spotify connect (with prominent Skip)**
      Paths: apps/web/src/app/(onboarding)/connect-spotify/page.tsx
      Size: M
      Deps: T054, T055, T039
      Refs: US-A2; FR-002, FR-027; decision-log Q12
      Description: Page with "Connect Spotify" primary CTA + equally visible "Skip — connect later" link + explanation of what Spotify enables (auto-import + auto-prompt + log prefill). Skip routes to step 4 (Follow 3) with critic-seed-only. Skip does NOT use "degraded mode" framing.
      Done: E2E test covers both paths.

- [ ] **T115 — Auto-import worker (30-day Spotify history)**
      Paths: apps/api/src/auxd_api/workers/spotify_import.py, apps/api/tests/integration/test_spotify_import.py
      Size: M
      Deps: T043, T073
      Refs: US-A2, US-A3; FR-003; TC-006
      Description: arq job triggered after Spotify connect; fetches `get_recently_played(since=now-30d, limit=50)`; aggregates to album-grain; creates DiaryEntry records with `source=spotify_import`. p99 <8s end-to-end. Idempotent (re-imports merge).
      Done: TC-006 passes.

- [ ] **T116 — Onboarding step 3: Confirm last 30 days (top-5 rate)**
      Paths: apps/web/src/app/(onboarding)/confirm-listens/page.tsx
      Size: M
      Deps: T115, T077, T039
      Refs: US-A3; wireframes/01-onboarding.html
      Description: Show top-5 imported albums (by play count) as cards with ½-star widgets. Skip allowed. Save = optimistic; advance to step 4.
      Done: E2E test covers happy path + skip.

- [ ] **T117 — Critic-seed batch precompute algorithm (backend, scheduled)**
      Paths: apps/api/src/auxd_api/modules/seeding/service.py, apps/api/tests/unit/test_seeding_algorithm.py
      Size: M
      Deps: T027, T104
      Refs: US-A4; FR-015; decision-log Q13; UJ-2 (≥3 critics in top 6)
      Description: `get_card_recommendations_for_user(user_id)` runs as part of `T104` suggested-follow precompute job; returns the scored list of critic-seeds (and mutual-taste candidates) cached for the user. Used for routine "Suggested follows" surfaces (Discover tab post-onboarding).
      Done: unit test on card distribution; mutual-taste algorithm covered.

- [ ] **T117a — Critic-seed SYNCHRONOUS card-ordering for onboarding** *(added in Phase 5C Revision)*
      Paths: apps/api/src/auxd_api/modules/seeding/onboarding_service.py, apps/api/tests/unit/test_onboarding_card_ordering.py
      Size: M
      Deps: T117, T115, T163
      Refs: US-A4; FR-015; A-005 from pre-impl-review (architecture findings table; pre-impl-review.md line 141)
      Description: `get_onboarding_cards(user, diary_signal)` — runs INLINE during onboarding step 4 (cannot wait for T104's nightly precompute, which has no signal for a brand-new user). Given the user's just-imported 30-day diary, computes genre signature → scores active critic-seeds → returns top 6 (with ≥3 critics in top 6 enforcement per UJ-2) + 4 mutual-taste candidates. Latency target: <1s p95. All 6 critic cards marked pre-checked=true; 4 mutual-taste cards pre-checked=false.
      Done: unit test covers (a) ≥3 critic guarantee in top 6, (b) <1s p95 with 80-seed roster, (c) deterministic ordering given fixed diary signal.

- [ ] **T118 — Onboarding step 4: Follow 3 to fill your feed**
      Paths: apps/web/src/app/(onboarding)/follow-3/page.tsx
      Size: M
      Deps: T117a, T101, T039
      Refs: US-A4; FR-015
      Description: Show cards from T117. Critic-seed cards pre-checked; mutual-taste unchecked. User can untick; minimum 1 to advance. Continue button triggers Follow creates with `source=onboarding_preselected | onboarding_mutual_taste | manual`.
      Done: E2E test covers all default-keep + custom-pick paths.

- [ ] **T119 — Onboarding step 5: Land on feed (non-empty guarantee)**
      Paths: apps/web/src/app/(onboarding)/complete/page.tsx, apps/api/src/auxd_api/modules/feed/service.py
      Size: S
      Deps: T106, T118
      Refs: US-A5
      Description: Last step redirects to `/` after a short success animation; backend ensures feed has ≥5 entries by padding with critic-seed last-7d activity.
      Done: E2E covers feed-with-≥5-entries after onboarding.

- [ ] **T120 — Onboarding completion analytics**
      Paths: apps/web/src/lib/analytics.ts
      Size: XS
      Deps: T119
      Refs: success-metrics
      Description: PostHog event `onboarding.completed` with `time_to_complete_ms`, `follows_count`, `critic_seed_kept_pct`, `top5_rated_count`.
      Done: event fires correctly.

- [ ] **T121 — Settings → Integrations (Spotify connect-later + back-fill)**
      Paths: apps/web/src/app/(app)/settings/integrations/page.tsx
      Size: M
      Deps: T055, T056, T115
      Refs: US-A2; FR-027
      Description: Spotify connect status; Connect button (for skipped-at-signup users); Disconnect button (with "diary persists" confirmation); "Back-fill diary" trigger.
      Done: E2E covers connect → disconnect → reconnect → diary persists.

- [ ] **T122 — Last.fm import (Should-Have)**
      Paths: apps/api/src/auxd_api/workers/lastfm_import.py, apps/web/src/app/(onboarding)/lastfm-import/page.tsx
      Size: M
      Deps: T039, T115
      Refs: US-H1
      Description: Alternative to Spotify: user provides Last.fm username; fetch up to 365d of scrobbles via Last.fm API; dedupe to album-grain; populate diary with ratings null.
      Done: integration test.

---

## §12 Just-finished detection (auto-prompt)

- [ ] **T123 — Spotify polling worker**
      Paths: apps/api/src/auxd_api/workers/spotify_poll.py
      Size: L
      Deps: T043, T027
      Refs: US-B6; FR-026
      Description: arq scheduled per-user polling. Cadence: 5min if active <24h, 15min if dormant, capped at 60min. Stop after 14d dormancy. Fetches `get_recently_played(since=last_poll)` + `get_currently_playing`. Persists `last_poll_at` on User.
      Done: worker runs; cadence transitions verified.

- [ ] **T124 — Just-finished detection heuristic**
      Paths: apps/api/src/auxd_api/modules/prompts/detection.py, apps/api/tests/unit/test_detection.py
      Size: M
      Deps: T123
      Refs: US-B6
      Description: Heuristic: ≥4 distinct tracks from the same Spotify album appear in last hour AND last track of album just finished → "album finished" event. Generates JustFinishedPrompt in `pending` state.
      Done: unit test covers heuristic edges (partial album, shuffled, paused, multi-album session).

- [ ] **T125 — JustFinishedPrompt lifecycle endpoints**
      Paths: apps/api/src/auxd_api/modules/prompts/routes.py, apps/api/tests/integration/test_prompts_lifecycle.py
      Size: M
      Deps: T027, T124
      Refs: US-B6; FR-026; TC-018, TC-019, TC-020, TC-021
      Description: `GET /api/v1/users/me/just-finished/pending` (current active prompt); `POST .../dismiss?album_id=X` (30d sticky); `POST .../disable` (sets `User.auto_prompt_enabled=false`).
      Done: TC-018, 019, 020, 021 pass.

- [ ] **T126 — Quiet hours enforcement (prompts + push)**
      Paths: apps/api/src/auxd_api/modules/notifications/quiet_hours.py
      Size: S
      Deps: T026
      Refs: FR-026; NT-3
      Description: `is_in_quiet_hours(user, now)` helper. Suppresses push and in-app prompts during user-local quiet window. Email/digest unaffected.
      Done: unit test covers tz boundaries.

- [ ] **T127 — Just-finished prompt component (frontend)**
      Paths: apps/web/src/components/just-finished-prompt/index.tsx
      Size: M
      Deps: T125, T037
      Refs: US-B6
      Description: Hero card at top of home feed when prompt is `pending`. "Log" primary CTA opens log sheet pre-filled. "Not now" dismisses. Overflow menu: "Don't prompt for this album" + "Disable auto-prompts". Polls every 60s when foreground.
      Done: component works; TC-E2E-008 covered.

- [ ] **T128 — Web push notification dispatch (for auto-prompt)**
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/web_push.py
      Size: M
      Deps: T008, T126
      Refs: US-B6; FR-026
      Description: VAPID-signed push notification adapter. Auto-prompt push fires only if `User.auto_prompt_push_enabled=true` (default false). Click action deep-links to home.
      Done: push delivered when opt-in; respects quiet hours.

- [ ] **T129 — Disable auto-prompts UI (Settings + inline)**
      Paths: apps/web/src/app/(app)/settings/notifications/page.tsx, apps/web/src/components/just-finished-prompt/overflow-menu.tsx
      Size: S
      Deps: T127
      Refs: US-B6, US-G3; TC-E2E-009
      Description: One-tap "Disable auto-prompts" from prompt overflow + Settings toggle. Both POST to `notifications/update_preferences`.
      Done: TC-E2E-009 passes.

- [ ] **T130 — Auto-prompt analytics**
      Paths: apps/web/src/lib/analytics.ts
      Size: XS
      Deps: T127
      Refs: success-metrics
      Description: PostHog events `prompt.shown`, `prompt.acted` (action: logged/dismissed/disabled-from-prompt).
      Done: events fire.

---

## §13 Notifications (load-bearing — Goodreads-firehose prevention)

- [ ] **T131 — Notification dispatcher core**
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py, apps/api/tests/unit/test_dispatcher.py
      Size: L
      Deps: T026
      Refs: FR-012; plan §8
      Description: `dispatch(user_id, type, payload)` entry point. Calls `is_notifiable()` → `coalesce()` → fan-out to adapters. Single in-process at MVP.
      Done: unit tests cover all branches.

- [ ] **T132 — `is_notifiable` predicate**
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py
      Size: S
      Deps: T131
      Refs: notification-taxonomy.md §Settings UI
      Description: Checks per-user-per-type-per-channel preferences, quiet hours, blocks, account status. Returns per-channel dispatch decision.
      Done: unit tests cover all dimensions.

- [ ] **T133 — Coalescer + rate limiter**
      Paths: apps/api/src/auxd_api/modules/notifications/coalescer.py, apps/api/tests/integration/test_coalescer.py
      Size: L
      Deps: T131, T013
      Refs: notification-taxonomy.md anti-spam guardrails; TC-026
      Description: Redis sorted-set-backed limiter: ≤5/hr, ≤25/day per user. Per-actor coalescing: ≤3/24h from same actor. Per-event dedup: same actor+type+target within 1h drops the second. Burst → coalesced "X new updates" notification.
      Done: TC-026 passes.

- [ ] **T134 — InApp notification adapter**
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/in_app.py
      Size: S
      Deps: T131, T026
      Refs: FR-012
      Description: Writes to `notifications` collection.
      Done: unit + integration tests.

- [ ] **T135 — Email notification adapter (Resend) + failure-mode wiring**
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/email.py, apps/api/src/auxd_api/modules/notifications/models.py (FailedEmail Document), apps/api/src/auxd_api/templates/email/*
      Size: M
      Deps: T131, T007, T026
      Refs: FR-012; plan §1.1.1 PostMark row; notification-taxonomy.md email design rules; sync-fix L4-003
      Description: Resend client wrapper (Python `resend` SDK; configure with `RESEND_API_KEY` from Settings); per-type HTML templates; one-click unsubscribe in footer; never tracking pixels. **Failure-mode wiring (sync-fix L4-003):** wrap send calls in `retry(attempts=3, backoff=exponential)` from T014. On final failure, write a `failed_emails` document `(user_id, notification_type, payload, attempted_at, last_error)` to the `failed_emails` collection for manual retry; emit Sentry alert with tag `email.send_failed`. The `FailedEmail` Beanie Document model lives alongside `Notification` in T026's module — extend T026 to include it.
      Done: test email sent + received via Resend sandbox. Plus integration test: mock Resend to 5xx three times → assert `failed_emails` document created with all metadata + Sentry tag fired.

- [ ] **T136 — Web push notification adapter**
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/web_push.py
      Size: (already in T128)
      Refs: FR-012
      Description: See T128.
      Done: covered.

- [ ] **T137 — Notification types (all 18 actives)**
      Paths: apps/api/src/auxd_api/modules/notifications/types.py, apps/api/tests/integration/test_notification_types.py
      Size: M
      Deps: T131, T132, T133, T134, T135
      Refs: FR-012; notification-taxonomy.md
      Description: Implement each of N-001..N-018 active types with: trigger source(s), payload schema, copy templates per channel, default settings. Integration tests fire each type and verify dispatch.
      Done: 18 types instrumented; defaults match taxonomy table.

- [ ] **T138 — Weekly digest job**
      Paths: apps/api/src/auxd_api/workers/digest_dispatch.py, apps/api/tests/integration/test_weekly_digest.py
      Size: L
      Deps: T135, T106
      Refs: FR-012; NT-2, NT-3; TC-027
      Description: arq cron every 5min; checks for users whose "Monday 09:00 user-local" falls in current 5-min window. Per-user: query top 10 feed entries past 7d + 1 "most-rated album in your follow graph this week" hero. Render + send via Resend. Quiet hours don't suppress (NT-3).
      Done: TC-027 passes.

- [ ] **T139 — Notification preferences UI**
      Paths: apps/web/src/app/(app)/settings/notifications/page.tsx
      Size: M
      Deps: T137
      Refs: US-G3; notification-taxonomy.md settings UI
      Description: Per-type per-channel toggles grouped per taxonomy. Quiet hours config. Quick controls (Mute all push / email / in-app).
      Done: UI works; updates persist.

- [ ] **T140 — In-app notification feed UI**
      Paths: apps/web/src/components/notifications/notification-list.tsx, apps/web/src/app/(app)/notifications/page.tsx
      Size: M
      Deps: T134
      Refs: US-G3
      Description: Bell icon in top bar with unread count; clicking opens notification list (paginated). Mark-read on view + explicit mark-all-read.
      Done: works end-to-end.

- [ ] **T141 — Web push subscribe flow (prompt at right time)**
      Paths: apps/web/src/components/notifications/push-prompt.tsx
      Size: S
      Deps: T140, T128
      Refs: plan §15 push
      Description: Push permission prompt shown after user's 3rd follow OR 7d of activity (whichever first), not on first session.
      Done: prompt logic verified.

- [ ] **T142 — Critic-seed onboarding wave: suppress N-001 follow notifications**
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py
      Size: XS
      Deps: T131, T117
      Refs: NT-1
      Description: When `Follow.source == onboarding_preselected`, suppress N-001 dispatch. Critic-seed accounts don't get hit by onboarding-wave notifications.
      Done: integration test.

- [ ] **T143 — Coalesce review.liked into weekly digest aggregate**
      Paths: apps/api/src/auxd_api/workers/digest_dispatch.py
      Size: S
      Deps: T138
      Refs: NT-4
      Description: Weekly digest includes "your reviews got X likes this week" hero entry for users with ≥1 like in trailing week.
      Done: covered in digest test.

- [ ] **T144 — Notification rate-limit alerting**
      Paths: apps/api/src/auxd_api/lib/observability.py, .github/workflows/observability-alerts.yml
      Size: XS
      Deps: T015, T133
      Refs: NFR Measurement Contract
      Description: PostHog dashboard "notification rate per user per week" with alert at p95 >12 (excluding digest).
      Done: dashboard live; alert configured.

---

## §14 Profile, Settings, Privacy

- [ ] **T145 — Edit profile UI (display_name, bio, avatar, handle)**
      Paths: apps/web/src/app/(app)/settings/profile/page.tsx
      Size: M
      Deps: T109, T057
      Refs: US-G1; FR-029
      Description: Form for profile fields. Handle change uses T057 backend; UI shows lockout reason if applicable. Avatar upload (PUT to backend; 5MB max).
      Done: E2E covers happy path + 30d-lock + change-too-soon error.

- [ ] **T146 — Avatar upload pipeline**
      Paths: apps/api/src/auxd_api/modules/auth/routes.py, apps/api/src/auxd_api/lib/storage.py
      Size: S
      Deps: T021
      Refs: US-G1
      Description: `POST /api/v1/users/me/avatar` accepts ≤5MB image; resizes to 256/128/64 sizes; stores on Fly volume or Cloudflare R2 (Phase 5 decision); returns URL.
      Done: avatar upload works.

- [ ] **T147 — Privacy settings UI**
      Paths: apps/web/src/app/(app)/settings/privacy/page.tsx
      Size: M
      Deps: T021
      Refs: US-G2; FR-013
      Description: Default visibility for new entries + new backlog items; private-profile toggle; "Keep backlog after logging" toggle.
      Done: settings persist; private-profile flips behavior on subsequent reads.

- [ ] **T148 — Private profile → follow-request queue**
      Paths: apps/api/src/auxd_api/modules/social/service.py, apps/web/src/components/social/follow-requests.tsx
      Size: M
      Deps: T101, T147
      Refs: US-G2, US-H3
      Description: When `is_private_profile=true`, new follows create `state=pending`; followee sees inbox of pending requests; can approve/reject.
      Done: integration test.

- [ ] **T149 — Settings → Data (export + delete)**
      Paths: apps/web/src/app/(app)/settings/data/page.tsx
      Size: M
      Deps: T058, T153
      Refs: US-G5; FR-018, FR-019
      Description: "Export my data" button enqueues T153 job. "Delete my account" with text-confirm modal triggers T058. Banner shows during grace period with cancel button.
      Done: E2E covers both flows.

- [ ] **T150 — Settings → Account (email, password change)**
      Paths: apps/web/src/app/(app)/settings/account/page.tsx, apps/api/src/auxd_api/modules/auth/service.py
      Size: M
      Deps: T053, T059
      Refs: NFR Security
      Description: Email change (with verify-email flow), password change (with current-password confirm), logout-all-devices button.
      Done: E2E covers email + password change.

- [ ] **T151 — Public profile (private-toggle-aware)**
      Paths: covered in T109
      Size: (sub-task)
      Refs: US-G2
      Description: When viewer not following private profile owner, render "This account is private" page instead of diary.
      Done: covered.

- [ ] **T152 — Critic-suffix badge on display name**
      Paths: apps/web/src/components/critic-badge/index.tsx
      Size: XS
      Deps: T117, T109
      Refs: SS-2
      Description: Subtle "· Critic" text suffix inline next to display_name everywhere when `CriticSeed.active=true` for that user. No icons.
      Done: badge renders inline on profile, reviews, feed entries.

---

## §15 GDPR + Moderation

- [ ] **T153 — Data export job**
      Paths: apps/api/src/auxd_api/workers/gdpr_export.py, apps/api/tests/integration/test_gdpr_export.py
      Size: L
      Deps: T023, T024, T025, T026, T135
      Refs: US-G5; FR-018; TC-030
      Description: arq job: gather all User-owned content → JSON + CSV → email via Resend with attachment-or-link → log to `gdpr_audit_log`.
      Done: TC-030 passes.

- [ ] **T154 — GDPR audit log collection**
      Paths: apps/api/src/auxd_api/lib/audit.py
      Size: S
      Deps: T012
      Refs: NFR Compliance
      Description: `gdpr_audit_log` collection storing each export/deletion event with `user_id`, `action`, `requested_at`, `completed_at`, `notes`. 7-year retention.
      Done: log entries written on T153 + T058.

- [ ] **T155 — Report submission endpoint**
      Paths: apps/api/src/auxd_api/modules/moderation/routes.py
      Size: M
      Deps: T026, T101
      Refs: US-G4; FR-014
      Description: `POST /api/v1/reports` with `target_type`, `target_id`, `reason`, `detail`. Rate-limited per-reporter.
      Done: integration test.

- [ ] **T156 — Daily moderation log-scan**
      Paths: apps/api/src/auxd_api/workers/moderation_scan.py
      Size: M
      Deps: T155
      Refs: US-G4
      Description: arq cron at 03:00 UTC. Finds users with ≥3 reports in trailing 7d. Flags + notifies admin via Discord webhook.
      Done: integration test.

- [ ] **T157 — Report acknowledgment notification (N-012)**
      Paths: apps/api/src/auxd_api/modules/notifications/types.py
      Size: XS
      Deps: T137, T155
      Refs: notification-taxonomy.md N-012
      Description: N-012 fires when a report is reviewed (admin action).
      Done: covered by T137 type implementation.

- [ ] **T158 — Admin notes / read-only flag visibility**
      Paths: apps/api/src/auxd_api/modules/auth/models.py
      Size: XS
      Deps: T021
      Refs: US-G4
      Description: Add `admin_notes` field on User (admin-only). No UI at MVP; founder reads via Mongo Compass.
      Done: field exists.

- [ ] **T159 — Suspended account UX**
      Paths: apps/api/src/auxd_api/middleware.py, apps/web/src/app/suspended/page.tsx
      Size: S
      Deps: T155
      Refs: US-G4
      Description: When `User.status=suspended`, all authenticated routes redirect to a `/suspended` page explaining the situation + appeal link.
      Done: E2E covers behavior.

- [ ] **T160 — GDPR cascading delete tests**
      Paths: apps/api/tests/integration/test_gdpr_cascade.py
      Size: M
      Deps: T058
      Refs: FR-019; TC-029
      Description: Test that after 30d grace + cascade, no records remain for deleted user across all collections; Report records retain nulled reporter_id.
      Done: TC-029 passes.

- [ ] **T161 — Privacy policy + ToS placeholders**
      Paths: apps/web/src/app/legal/privacy/page.tsx, apps/web/src/app/legal/terms/page.tsx
      Size: S
      Deps: T031
      Refs: NFR Compliance
      Description: Placeholder pages with founder-authored content (or lawyer-reviewed pre-launch).
      Done: pages render; linked from footer + signup screen.

---

## §16 Seeding backend + founder workflow

- [ ] **T162 — CriticSeed admin (manual roster management)**
      Paths: apps/api/scripts/manage_critic_seed.py, docs/critic-seed-runbook.md
      Size: S
      Deps: T027
      Refs: seeding-strategy.md §1
      Description: CLI to add/remove/activate/deactivate CriticSeed records. Document founder workflow.
      Done: CLI works; runbook authored.

- [ ] **T163 — Genre signature computation**
      Paths: apps/api/src/auxd_api/modules/seeding/genre_signature.py
      Size: M
      Deps: T117, T073
      Refs: T117 algorithm
      Description: Compute per-user `genre_signature` (vector of genre weights) from their diary entries' album metadata. Used by T117 for matching.
      Done: unit test.

- [ ] **T164 — Mutual-taste suggestions algorithm**
      Paths: apps/api/src/auxd_api/modules/seeding/mutual_taste.py
      Size: M
      Deps: T163
      Refs: seeding-strategy.md §4
      Description: Implement the 4-factor scoring (mutual-taste 40%, followed-by-followed 30%, shared-seed 15%, label/genre 10%, recency 5%) — covered partially in T104 (which is the SuggestedFollow precompute) but extracted here as a reusable scoring service.
      Done: unit test.

- [ ] **T165 — Critic-of-the-week (deferred)**
      Paths: (deferred to v1.x)
      Size: —
      Refs: seeding-strategy.md operational levers
      Description: NOT in MVP scope. Documented as future-state.
      Done: N/A.

- [ ] **T166 — Founder seed-content workflow tools**
      Paths: docs/founder-workflows/seed-content.md
      Size: XS
      Deps: T162
      Refs: seeding-strategy.md §1 pre-launch playbook
      Description: Document workflow: identify candidates → cold outreach template → onboarding script → activity expectations → cull cadence.
      Done: doc authored.

---

## §17 Should-have features

- [ ] **T167 — Album merge / report-wrong-album**
      Paths: apps/api/src/auxd_api/modules/albums/admin.py, apps/web/src/components/album-detail/report-wrong.tsx
      Size: M
      Deps: T067
      Refs: US-H2
      Description: User-facing "Report wrong album" form on album page; admin queue (read-only at MVP via Mongo); merge operation via CLI.
      Done: integration test.

- [ ] **T168 — Share-card OG image generator**
      Paths: apps/web/src/app/api/og/album/[id]/route.ts, apps/web/src/app/api/og/review/[id]/route.ts
      Size: M
      Deps: T070, T085
      Refs: US-H5
      Description: Vercel OG image generation for album and review URLs; pre-rendered at write time and cached.
      Done: share-link previews on Twitter/X show expected card.

- [ ] **T169 — Pull-more-history (Should-Have)**
      Paths: apps/web/src/app/(app)/settings/integrations/page.tsx, apps/api/src/auxd_api/workers/spotify_import.py
      Size: M
      Deps: T115
      Refs: decision-log Q14 (v1.x progressive enhancement)
      Description: "Pull more history" button (Settings → Integrations) extends import window by paging deeper or via Last.fm import. Marked as v1.x — defer if M-2 capacity tight.
      Done: deferred OK if needed.

- [ ] **T170 — Friend-request flow (US-H3)**
      Paths: apps/web/src/components/social/follow-requests.tsx
      Size: M
      Deps: T148
      Refs: US-H3
      Description: UI for managing pending follow requests when private profile is on. Builds on T148 backend.
      Done: E2E covers approve + reject.

---

## §18 Pre-launch hardening + NFR validation

- [ ] **T171 — Accessibility audit (WCAG 2.1 AA)**
      Paths: apps/web/tests/a11y/*.spec.ts, apps/web/playwright.config.ts (axe-core integration)
      Size: M
      Deps: T108, T070, T077
      Refs: NFR Accessibility
      Description: axe-core automated audit on every screen + manual keyboard nav test. Target 0 violations.
      Done: a11y suite passes.

- [ ] **T172 — Performance audit (p95 + p99 targets)**
      Paths: apps/api/tests/perf/*.py, apps/web/tests/perf/lighthouse.spec.ts
      Size: M
      Deps: T106, T070
      Refs: spec.md §6.1
      Description: k6 or Locust load tests against staging; Lighthouse runs against production. Verify all spec.md §6.1 thresholds.
      Done: all NFRs measured + at target.

- [ ] **T173 — Security review**
      Paths: docs/security-review.md
      Size: M
      Deps: T053, T058
      Refs: NFR Security
      Description: Internal security audit: OWASP Top 10 checklist applied to all endpoints. Run `/security-review` skill against the codebase.
      Done: review documented + critical issues closed.

- [ ] **T174 — E2E test suite (TC-E2E-001..013)**
      Paths: apps/web/tests/e2e/*.spec.ts
      Size: L
      Deps: throughout
      Refs: spec.md §10 E2E
      Description: Complete the 13 E2E scenarios. Most are touched by individual tasks; T174 ensures all 13 exist and pass against staging.
      Done: all 13 E2E scenarios pass.

- [ ] **T175 — Smoke staging environment**
      Paths: docs/staging.md
      Size: S
      Deps: T009
      Refs: plan §17, §18
      Description: Fly.io staging app + Atlas staging database + Vercel preview env. All workers run.
      Done: staging env deployed.

- [ ] **T176 — Closed-beta wave preparation**
      Paths: docs/closed-beta-runbook.md
      Size: S
      Deps: T175, T117
      Refs: plan §18 Phase M-2
      Description: Document runbook: who to invite (critic-seed + close friends), how invites get generated, how to monitor early signals (PostHog dashboards), what we're watching for.
      Done: runbook authored.

- [ ] **T177 — Extended Quota Mode follow-through**
      Paths: docs/spotify-application.md
      Size: S
      Deps: T002
      Refs: plan §0 Task 1
      Description: Follow up with Spotify reviewers as needed; address any feedback; ensure approval before public launch.
      Done: Extended Quota Mode approved or known-rejected.

- [ ] **T178 — Final wireframe → design polish pass**
      Paths: apps/web/src/components/* (design tokens, polish)
      Size: L
      Deps: T108, T070, T077, T080
      Refs: wireframes/*, plan §18
      Description: Design polish: typography scale, color palette tuning, micro-interaction animations, haptic feedback on rating/Aux/Like, mobile responsiveness verification. Founder + (optional) designer involvement.
      Done: visual quality at launch-ready bar.

- [ ] **T179 — Pre-launch checklist + readiness review**
      Paths: docs/launch-checklist.md
      Size: M
      Deps: T171, T172, T173, T174, T177
      Refs: plan §18 Phase M-2 → M0
      Description: Comprehensive checklist (modeled on Product Forge Phase 9 release-readiness). Founder + Phase 6B + Phase 7 cover most items; this consolidates.
      Done: checklist complete; all items ✅.

- [ ] **T180 — M0 launch ceremony**
      Paths: docs/launch.md
      Size: S
      Deps: T179
      Refs: plan §18 Phase M0
      Description: Public signup opens; critic-seed roster live; monitoring on; founder on-call. PostHog dashboards under active watch.
      Done: launch executed; sign-ups happening; no critical issues in first 72h.

---

## Phase 5.5 trigger

Plan §3 declares a Data Model (15 entities + indexes + Beanie patterns + Atlas Search index). This satisfies the Phase 5.5 (Migration Plan) conditional trigger. After Phase 5B approval, the orchestrator should prompt for Phase 5.5 to produce migration scripts (forward / rollback / validation) for the initial schema setup.

For a greenfield project, "migration" at MVP is the initial collection creation + Atlas Search index application + reserved-handles seed. Subsequent schema changes follow Constitution Principle 2 (per-doc `_schema_version` + lazy upgrade on write).

---

## Parallel-track opportunities

| Group | Tasks | Can parallelize with |
|---|---|---|
| §0 Prereqs (T001 + T002) | Constitution + Spotify app | Can run concurrently with each other; T001 needed before T003 |
| §1 Backend libs + §3 Frontend foundation | T011..T030 + T031..T040 | Two engineers can split backend / frontend after T003 |
| §6 Albums + §8 Reviews + §9 Backlog | T063..T072 + T085..T094 + T095..T100 | Once auth (§5) is done, these three modules touch independent collections — can parallelize across 2-3 engineers |
| §13 Notifications + §12 Just-finished detection | T123..T130 + T131..T144 | Have a shared dependency (T128 web push) but otherwise independent |
| §11 Onboarding + §10 Feed | T113..T122 + T101..T112 | Onboarding consumes feed but feed work can complete first |
| §18 Hardening | T171..T180 | Must run after most feature work; some tasks parallelize within §18 |

---

## Constitution + decision-log + NFR coverage summary

- **Constitution Principle 1 (resilience):** T014 + T050 + T051 (provider-level + transport-level); enforced by lint rule in T004 CI.
- **Constitution Principle 2 (schema versioning):** T012 + T030 (runner) + every model task includes `_schema_version: int = 1`.
- **Constitution Principle 3 (library-first):** Module structure throughout (each module has `routes.py`, `service.py`, `models.py` only).
- **Constitution Principle 4 (test-first):** T042 + T048 (contract tests before T043 + T049 implementations).
- **Constitution Principle 5 (observability):** T015 (lib) + T051 (provider) + woven throughout (each task adds its PostHog events).
- **Constitution Principle 6 (provider abstraction):** T041 + T043 + T049.
- **All 32 Must-Have user stories** → each maps to ≥1 task per coverage matrix.
- **All 27 active FRs** → each maps to ≥1 task per coverage matrix.
- **All 32 critical TCs + 13 E2E scenarios** → mapped per plan §16.2 + woven into tasks above.
- **NFR Measurement Contract (spec.md §6.1)** → instrumentation woven (T015, T077 wedge timing, T107 feed perf, T144 notification rate, T172 perf audit).
- **Aux (🏅) vs Like (👍) split preserved:** T023 (separate fields), T073 (Aux on DiaryEntry), T088 (Like on Review via ReviewLike), T090 (UI distinct icons), notification N-001 (follow) vs N-004 (review.liked).
- **Lists deliberately ABSENT:** No tasks for Lists per R3 deferral; out-of-scope.md and decision-log row 7 confirm v2 deferral.
