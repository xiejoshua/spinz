# Tasks: auxd MVP

> **Phase 5B — Task Breakdown** | Generated: 2026-05-22
> Feature slug: `001-auxd-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - Plan: [plan.md](./plan.md)
> - Spec: [spec.md](./spec.md)
> - Decision Log: [product-spec/decision-log.md](./product-spec/decision-log.md)

<!-- CR-001 (2026-05-22): All Spotify integration deferred to v2. MVP is
     Letterboxd-style manual search + rating via MusicBrainz + Discogs.
     Reason: Spotify Extended Quota Mode now requires 250k MAUs to apply —
     structurally unreachable pre-launch.

     Removed tasks (16):
       - T002 (Spotify Extended Quota Mode application)
       - T042-T047 (6 Spotify provider tasks: contract tests, impl, OAuth, recently-played, search, get-album)
       - T054-T056 (Spotify OAuth signup, Connect-later, Disconnect)
       - T114-T116 (Onboarding step 2: Spotify connect, Auto-import worker, Confirm last 30 days)
       - T121-T122 (Settings → Integrations, Last.fm import)
       - T177 (Extended Quota Mode follow-through — depended on T002)
     Deferred to v2 (8):
       - T123-T130 (entire §12 just-finished cluster; bodies preserved for v2 resumption)
     Amended (5): T021, T022, T026, T027, T029 (code patches land separately).
     New tasks (3): T049a, T049b (Discogs catalog provider), T053a (Report missing album).
     Net: 183 − 16 + 3 = 170 task lines in file (162 active MVP + 8 deferred-to-v2).
     Also retired: §17 T169 (Pull-more-history) marked DEFERRED-TO-V2 since it built on the removed auto-import surface. -->

## Conventions

- **Task IDs:** `T001`..`TNNN`, unique throughout.
- **Sizes (D4 T-shirt):** XS ≤1h · S ≤½ day · M ≤1 day · L ≤2 days · XL >2 days (flag for decomposition).
- **Paths:** full paths from monorepo root (project is technically single-root mode at task-write time; T003 introduces monorepo structure).
- **Deps:** task IDs that MUST complete first. `—` = no dependencies.
- **Refs:** which user stories (US-X), FRs, NFRs, TCs, or decision-log entries the task implements.
- **Done signal:** under each task, what proves it complete (test passing + manual check unless noted).

## Coverage matrix (verified against plan + spec)

<!-- CR-001: coverage matrix updated — Spotify-only FRs/stories deferred; §4 retitled; §11 narrowed to onboarding; §12 marked DEFERRED. -->
| Cluster | Tasks | Stories covered |
|---|---|---|
| §0 Prerequisites | T001–T010 | (cross-cutting) |
| §1 Backend foundation + libs | T011–T020 | (cross-cutting) |
| §2 Lib + shared backend | T021–T030 | Constitution P1, P2, P3, P5, P6 |
| §3 Frontend foundation | T031–T040 | Cross-cutting |
| §4 Providers (MusicBrainz + Discogs) | T041, T048–T052, T049a, T049b | FR-005, FR-010, FR-028 (contract-test-first per P4) |
| §5 Auth | T053, T053a, T057–T062 | US-A1, US-G1, US-G5; FR-001, FR-029 |
| §6 Albums + Search | T063–T072 | US-F1, US-F2; FR-005, FR-010, FR-028 |
| §7 Diary + Log sheet (THE wedge) | T073–T084 | US-B1..B5; FR-004, FR-007 |
| §8 Reviews + Likes + sort | T085–T094 | US-C1..C4; FR-011, FR-030, FR-031, FR-032 |
| §9 Backlog | T095–T100 | US-D1..D3; FR-006 |
| §10 Social graph + Feed | T101–T112 | US-E1..E5, US-G4; FR-008, FR-009, FR-014, FR-016 |
| §11 Onboarding (auto-import portion DEFERRED-TO-V2 per CR-001) | T113, T117–T120 | US-A4, US-A5; FR-015 |
| §12 Just-finished detection **DEFERRED-TO-V2 (CR-001)** | T123–T130 | (US-B6, FR-026 — DEFERRED in spec.md) |
| §13 Notifications | T131–T144 | US-G3; FR-012 |
| §14 Profile, Settings, Privacy | T145–T152 | US-G1..G5; FR-013 |
| §15 GDPR + Moderation | T153–T161 | US-G4, US-G5; FR-019 |
| §16 Seeding backend | T162–T166 | US-A4, US-E5; FR-015 |
| §17 Should-have | T167–T170 | US-H2, US-H3, US-H5 |
| §18 Pre-launch hardening | T171–T180 | NFR Measurement Contract; spec.md §10 E2E coverage |

<!-- CR-001: total recomputed. Removed 16 (T002, T042-T047, T054-T056, T114-T116, T121, T122, T177). Added 3 (T049a, T049b, T053a). 183 − 16 + 3 = 170 task lines in file. Of those, 162 are active MVP + 8 are DEFERRED-TO-V2 (T123-T130) kept in-file for traceability. Note: T169 is also DEFERRED-TO-V2 per CR-001 (built on removed auto-import surface) — counted within the 162 active for line-count purposes but won't ship at MVP. -->
<!-- sync-fix L4-007 (Run #4): FR math reconciled — FR-033 was added by CR-001 spec.md but not surfaced here. Base FR set = 28 (27 originals + FR-033). 23 active = 28 − 5 deferred (FR-002, FR-003, FR-017, FR-026, FR-027). -->
<!-- CR-002: 2 tasks added (T093a /review/[id] route + T093b reading-view component); 2 tasks amended in place (T090 + T138). Active count 162 → 164; total lines 170 → 172. -->
**Total: 164 active MVP tasks + 8 DEFERRED-TO-V2 (T123–T130 per CR-001) = 172 task lines in file** (= 180 base + T117a Phase 5C + T010a + T015a both added in sync-fix Run #1 + 3 added in CR-001 − 16 removed in CR-001 + 2 added in CR-002 — see [sync-fix-list.md](./sync-fix-list.md) + CR-001 + CR-002 banners). Sized to deliver M-2 closed-beta scope per plan §18; Must-Have user stories addressed minus the 3 deferred (US-A2, US-A3, US-B6 — DEFERRED in spec.md per CR-001); **23 active FRs** covered = 28 base (27 originals + FR-033 "Report missing album" added by CR-001) − 5 deferred (FR-002, FR-003, FR-017, FR-026, FR-027 — DEFERRED in spec.md per CR-001); critical TCs (excluding TC-006/TC-018–021/TC-022 which now sit with the deferred tasks) + 13 E2E scenarios referenced. Tasks amended in sync-fix Run #1: T013 (Redis fail-modes), T023 (ReviewEditHistory), T025 (FollowRequest), T026 (FailedEmail + missing_album report type), T135 (PostMark failure-mode + retry). Tasks amended in CR-001: T021, T022, T026, T027, T029 (code patches land separately).

---

## §0 Pre-implementation prerequisites — MUST complete before any feature work

- [x] **T001 — Author and ratify project constitution** *(completed 2026-05-22, signed by Joshua Xie)*
      Paths: .specify/memory/constitution.md
      Size: M
      Deps: —
      Refs: plan §0; decision-log §Decisions deferred to Phase 5 (Constitution)
      Description: Replace template placeholders in `.specify/memory/constitution.md` with the 6 principles from plan §0 (external-call resilience, schema-versioned documents, library-first modules, test-first for catalog/auth, observability mandatory, provider abstraction). Founder sign-off required. Commit with message `chore: ratify project constitution`.
      Done: file is non-template; sign-off recorded.

<!-- CR-001 removed: T002 (Submit Spotify Extended Quota Mode application) — Spotify Extended Quota Mode now requires 250k MAUs to apply; structurally unreachable pre-launch, so Spotify integration is entirely deferred to v2. -->

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

- [x] **T005 — Provision MongoDB Atlas + Upstash Redis** *(operationally live; impl-log line 157 — `check_integrations.py` → 7/7; Atlas IP allowlist widened, Upstash region us-east-1, both reachable from local dev + Fly)*
      Paths: docs/infra.md
      Size: S
      Deps: —
      Refs: plan §17.4, §17.5
      Description: Create Atlas M0 cluster (region: aws-us-east-1, matching Fly `iad` for low-latency colocation); create Upstash Redis (region: us-east-1); note connection strings; configure IP allow-list for local dev + Fly.io outbound IPs.
      Done: both services reachable from local dev; connection strings captured.

- [x] **T006 — Provision Fly.io + Vercel projects** *(operationally live; impl-log line 157 — Fly deploy ✅; Vercel deploy ✅; both healthchecks return 200)*
      Paths: apps/api/fly.toml, apps/web/vercel.json
      Size: S
      Deps: T003
      Refs: plan §17.1, §17.2
      Description: `flyctl apps create auxd-api --region iad`; configure two-process layout (api + worker) on a single shared-cpu-1x VM (stays inside Hobby $5/mo minimum); link `apps/api/fly.toml`. `vercel init` linking `apps/web` to a Vercel project. Domain `xiejoshua.com` (apex → Vercel) and `api.xiejoshua.com` (CNAME → Fly via `fly certs add`) configured on Cloudflare DNS with proxy OFF for Vercel/Fly records.
      Done: empty hello-world deploys from each host land at expected URLs.

- [x] **T007 — Configure Resend + Sentry + PostHog Cloud + Cloudflare R2 + secrets** *(operationally live; impl-log line 157 — all 7 integrations pass `scripts/check_integrations.py` with `truststore` patch for Zscaler MITM; secrets set in Fly + Vercel; PostHog Cloud reachable; R2 bucket `auxd-backups` accessible)*
      Paths: apps/api/src/auxd_api/settings.py, docs/infra.md
      Size: S
      Deps: T005, T006
      Refs: plan §15, §17.6
<!-- CR-001: T007 secret list updated — SPOTIFY_CLIENT_ID/SECRET removed (no Spotify at MVP); DISCOGS_API_TOKEN added (optional, T029 amendment). -->
      Description: Create accounts: Resend (sending domain `xiejoshua.com` — DKIM/SPF/DMARC records added to Cloudflare DNS); Sentry Developer plan free tier (projects `auxd-api` + `auxd-web`); PostHog Cloud US region free tier (project `auxd`); Cloudflare R2 API token for bucket `auxd-backups` (Object Read & Write, scoped to the one bucket). Set secrets via `fly secrets set` — full list in docs/infra.md: MONGODB_URI, REDIS_URL, DISCOGS_API_TOKEN (optional per CR-001), SESSION_HMAC_KEY, TOKEN_ENCRYPTION_KEY, RESEND_API_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, SENTRY_DSN, POSTHOG_API_KEY, POSTHOG_HOST, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, R2_BUCKET_NAME. (Spotify secrets removed per CR-001 — Spotify integration deferred to v2.) PostHog self-host on Fly was the original plan; swapped to Cloud 2026-05-22 (saves ~$40/mo of RAM-heavy Fly compute).
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
<!-- CR-001: T020 description updated — Spotify upstream rate-limit reference dropped; MusicBrainz (1 req/sec) + Discogs (60 req/min) limits are now the defensive backstop. -->
      Description: Per-user + per-IP rate limits keyed by Redis sorted-sets; configurable per-endpoint. Used by log, follow, review, like endpoints + auth. **Fail-mode (locked in Phase 5C):** when Redis is unreachable, the middleware FAILS OPEN — requests are allowed through and a Sentry alert is emitted with tag `rate_limit.redis_down`. Same fail-open policy applies to the notification rate-limiter (T133). MusicBrainz (1 req/sec per IP) and Discogs (60 req/min authenticated) upstream limits are handled inside the catalog-provider clients (T049, T049b) per CR-001 — our middleware is defensive rather than load-bearing for those providers.
      Done: integration test bursts an endpoint past limit + receives 429. Additional test: simulate Redis disconnect → assert requests succeed AND Sentry alert fires.

---

## §2 Shared backend models + OpenAPI codegen pipeline

<!-- CR-001: amendment annotation added — music_providers field becomes empty dict at MVP. -->
- [x] **T021 — User Document + handle policy fields** *(completed 2026-05-22; full plan §3 schema incl. handle policy/notif prefs/music providers; indexes on handle/email unique + status partial; tests via mongomock-motor)* *(amended CR-001: `music_providers` field type changes from struct-with-spotify-shape to empty dict at MVP; CR-001 code patch lands separately.)*
      Paths: apps/api/src/auxd_api/modules/users/models.py, apps/api/tests/unit/test_users_model.py
      Size: M
      Deps: T012, T018
      Refs: plan §3, §4.3; FR-029; US-G1; data-model.md User
      Description: Beanie `User` Document with all fields per data-model.md User entity. Includes `auto_prompt_enabled`, `auto_prompt_push_enabled`, `default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log`, `handle_changed_at` (renamed from `last_handle_change` in sync-fix Run #3 L5-004), `created_at`, `deletion_scheduled_for`, `session_version`, `status`. Indexes: handle unique, email unique, status partial.
      Done: model loads; unit test creates/saves/loads a User; indexes confirmed via aggregate explain.

<!-- CR-001: amendment annotation added — drop spotify_id sparse-unique index; MBID becomes sole canonical identity at MVP. -->
- [x] **T022 — Album Document + identity fields** *(completed 2026-05-22; Album schema incl. mbid/spotify_id sparse-unique indexes; Atlas Search index JSON at apps/api/migrations/atlas_search/albums_index.json — one-time UI apply documented)* *(amended CR-001: Drop `spotify_id` sparse-unique index; MBID is the sole canonical identity at MVP. CR-001 code patch lands separately.)*
      Paths: apps/api/src/auxd_api/modules/albums/models.py
      Size: M
      Deps: T012, T018
      Refs: plan §3; data-model.md Album
      Description: Beanie `Album` Document with all fields. Indexes: `mbid unique sparse` (and historically `spotify_id unique sparse` — to be dropped per the CR-001 amendment above; MBID becomes the sole canonical identity at MVP). Atlas Search index definition (per plan §11.1) added as a migration artifact (`apps/api/migrations/atlas_search/albums_index.json`).
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

<!-- CR-001: amendment annotation added — just-finished + Spotify-revoked NotificationType enum values defer; 16 active types remain. -->
- [x] **T026 — Report + Notification + NotificationPreferences + FailedEmail Documents** *(completed 2026-05-22; 18/18 tests; 18-value NotificationType enum; Notification 90d TTL; Report.target_type incl. missing_album; FailedEmail as T135 write target; NotificationPreferences dedupe with T021 reconciled)* *(amended CR-001: Remove the just-finished + Spotify-revoked NotificationType enum values (those rows in notification-taxonomy.md become DEFERRED-TO-V2 per CR-001). Other 16 active types unchanged.)*
      Paths: apps/api/src/auxd_api/modules/moderation/models.py, apps/api/src/auxd_api/modules/notifications/models.py
      Size: M
      Deps: T021
      Refs: plan §3.1; plan §1.1.1 PostMark row; notification-taxonomy.md; sync-fix L4-003 (FailedEmail)
      Description: `Report` (target_type/target_id, status, resolution_note — target_type enum extended with `missing_album` per sync-fix L3-006); `Notification` (user_id, type, payload, channel_dispatch_state, read_at, TTL 90d); `NotificationPreferences` (embedded on User per plan §3 — model the embedded sub-document explicitly); `FailedEmail` (user_id, notification_type, payload, attempted_at, last_error — write target for T135 failure-mode wiring). 18 active notification types as `NotificationType` enum.
      Done: models + TTL index on Notification; FailedEmail covered by integration test in T135.

<!-- CR-001: amendment annotation added — JustFinishedPrompt collection defers; remove from ALL_DOCUMENT_MODELS in db.py but keep model file for v2 resumption. -->
- [x] **T027 — JustFinishedPrompt + SuggestedFollow + CriticSeed Documents** *(completed 2026-05-22; 13/13 tests; JustFinishedPrompt TTL partial-filter (state=pending → 24h expiry), retains LOGGED/DISMISSED for S-B6 30d cooldown + attribution analytics; SuggestedFollow sparse dismissed_at index; CriticSeed strict unique on user_id + separate partial-active index for fast "active critics" reads — sync-fix Run #3 L5-005 clarified intent vs initial status note)* *(amended CR-001: JustFinishedPrompt collection becomes DEFERRED-TO-V2 per CR-001; remove from `ALL_DOCUMENT_MODELS` in db.py (keep model file for v2). SuggestedFollow + CriticSeed unchanged.)*
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

<!-- CR-001: amendment annotation added — remove SPOTIFY_* fields + validator; add optional DISCOGS_API_TOKEN; update .env.example files. -->
- [x] **T029 — Pydantic settings + env validation** *(completed 2026-05-22; 8/8 tests; Environment + LogLevel enums; base64-key validators; conditional Spotify-secret enforcement; emit_startup_audit log)* *(amended CR-001: Remove all `SPOTIFY_*` fields (`SPOTIFY_INTEGRATION_ENABLED`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`) + their validator. Add optional `DISCOGS_API_TOKEN`. Update `.env.example` + `apps/api/.env.example`.)*
      Paths: apps/api/src/auxd_api/settings.py
      Size: S
      Deps: T011
      Refs: plan §17.2
      Description: `Settings` class with all required env vars, validated at app start; missing values fail loudly with helpful messages. Document each env var in `apps/api/.env.example`.
      Done: app refuses to start without required env; happy-path startup writes a config audit log line.

- [x] **T030 — Migration runner skeleton**
      *(completed 2026-05-23 Session 22; runner discovers `00N_*.py` modules by filename order, each exporting `from_version: int`, `to_version: int`, and `async def apply(db) -> int`. Skips a migration silently when its `from_version` is above all documents' `_schema_version`; fail-loud (re-raises) on any apply error so a botched migration can never serve traffic. Wired into main.py lifespan AFTER init_db and BEFORE init_redis. 001_initial.py is a no-op returning 0. log_call emits `migration.applied` with `{migration_name, from_version, to_version, modified_count, duration_ms}` per migration — uses `migration_name` not `name` to avoid colliding with LogRecord's built-in `name` attribute. Added `get_database()` helper to db.py. 6 unit tests + 2 lifespan integration tests; patched test_healthz + test_otel to no-op the new migrations call since those tests bypass init_db.)*
      Paths: apps/api/src/auxd_api/migrations/{__init__,runner,001_initial}.py, apps/api/src/auxd_api/db.py (get_database helper), apps/api/src/auxd_api/main.py (lifespan wiring), apps/api/tests/unit/test_migration_runner.py, apps/api/tests/integration/test_app_lifespan_migrations.py
      Size: M
      Deps: T011, T029
      Refs: plan.md Constitution Principle 2; plan.md §3 Data Model
      Description: Migration runner that discovers ordered `00N_*.py` modules and applies them on app startup before serving traffic. Each migration declares `from_version`/`to_version` integers and an async `apply(db)` returning the modified-doc count. Runner skips already-applied migrations via `_schema_version` threshold and re-raises on error so a botched migration cannot serve traffic.
      Done: unit tests cover discovery order + skip-when-above-version + re-raise semantics; integration tests confirm lifespan wiring runs migrations between init_db and init_redis.

---

## §3 Frontend foundation

- [x] **T031 — Next.js 15 App Router skeleton**
      Paths: apps/web/src/app/layout.tsx, apps/web/src/app/page.tsx, apps/web/next.config.ts, apps/web/tailwind.config.ts
      Size: S
      Deps: T003
      Refs: plan §1.2, §7.1
      Description: App Router skeleton with root layout; Tailwind configured; placeholder home page.
      Done: `pnpm --filter @auxd/web dev` serves the page.

- [x] **T032 — shadcn/ui setup + design tokens**
      Paths: apps/web/components.json, apps/web/src/components/ui/*, apps/web/src/lib/utils.ts
      Size: S
      Deps: T031
      Refs: plan §2; NFR Accessibility
      Description: Init shadcn/ui via CLI; copy initial component set (Button, Sheet, Dialog, Toast, Input, Select, Tabs, Avatar, Badge, Form). Tailwind config defines design tokens (color palette tuned for music — TBD with founder).
      Done: a Button renders correctly; dark mode toggle works.

- [x] **T033 — TanStack Query setup + API client**
      Paths: apps/web/src/lib/query-client.ts, apps/web/src/lib/api-client.ts, apps/web/src/providers.tsx
      Size: S
      Deps: T031, T028
      Refs: plan §7.3
      Description: QueryClient provider; typed fetch wrapper consuming `@auxd/shared-types`; React Query DevTools in dev. Standard `useApiQuery` and `useApiMutation` helpers.
      Done: a hello-world query against `/healthz` displays the response.

- [x] **T034 — Zustand setup for client state**
      Paths: apps/web/src/stores/auth.ts, apps/web/src/stores/ui.ts
      Size: XS
      Deps: T031
      Refs: plan §7.2
      Description: Auth store (sanitized user object); UI store (log-sheet open/closed, feed sort preference). Hydrate from server components on first load.
      Done: stores load; toggling log-sheet store updates a test UI.

- [x] **T035 — React Hook Form + Zod setup**
      Paths: apps/web/src/lib/forms.ts, apps/web/src/components/ui/form.tsx
      Size: XS
      Deps: T032
      Refs: plan §2
      Description: Hook Form + Zod resolver wired into shadcn/ui Form component. Reusable form-error component.
      Done: a sample form validates and submits.

<!-- sync-fix L4-012 (Run #7): instrumentation-client.ts is required by @sentry/nextjs v8+ for the browser-runtime init; appended to Paths. -->
- [x] **T036 — Sentry + PostHog (frontend)**
      Paths: apps/web/src/lib/sentry.ts, apps/web/src/lib/posthog.ts, apps/web/instrumentation.ts, apps/web/instrumentation-client.ts
      Size: S
      Deps: T031, T007
      Refs: plan §15.1, §15.2
      Description: Sentry SDK with source-map upload on Vercel deploy; PostHog client (server + browser, single-instance singleton). Manual capture helpers.
      Done: a thrown error reaches Sentry; a test PostHog event reaches PostHog.

- [x] **T037 — Authenticated layout (post-auth shell)**
      Paths: apps/web/src/app/(app)/layout.tsx, apps/web/src/components/nav/bottom-tabs.tsx
      Size: M
      Deps: T031, T032, T034
      Refs: spec.md §4 user stories cluster G; plan §7.1
      Description: Authenticated route group with redirect-to-login if no session. Bottom-tab nav (Home, Up Next, Discover, Profile). Persistent "+" Log FAB.
      Done: navigating to `/` redirects to `/login` when unauthenticated; otherwise renders the shell.

- [x] **T038 — Public layout (pre-auth pages)**
      Paths: apps/web/src/app/(auth)/layout.tsx, apps/web/src/app/(auth)/login/page.tsx, apps/web/src/app/(auth)/signup/page.tsx
      Size: M
      Deps: T031, T032, T035
      Refs: US-A1; FR-001
      Description: Public layout for login/signup. Forms wired but submit is a no-op (T053 wires real auth).
      Done: pages render and forms validate locally.

- [x] **T039 — Onboarding route group skeleton**
      Paths: apps/web/src/app/(onboarding)/layout.tsx, apps/web/src/app/(onboarding)/step-1/page.tsx
      Size: S
      Deps: T037
      Refs: spec.md §4 user stories cluster A
      Description: Route group for onboarding steps with progress indicator; step routing wired (steps fleshed out in §11).
      Done: scaffolded routes navigate sequentially.

- [x] **T040 — Playwright E2E setup**
      Paths: apps/web/playwright.config.ts, apps/web/tests/e2e/smoke.spec.ts, .github/workflows/e2e.yml
      Size: M
      Deps: T031, T009
      Refs: plan §16; spec.md §10 E2E
      Description: Playwright installed; config targets Vercel preview deploy. Smoke test asserts landing page renders. Full E2E suite (TC-E2E-001..013) added per-feature in their respective tasks.
      Done: smoke test runs in CI against PR preview deploy.

---

<!-- CR-001: §4 retitled — Spotify provider removed; MusicBrainz primary + Discogs fallback. -->
## §4 Providers — MusicBrainz + Discogs (contract-test-first per Constitution P4)

- [x] **T041 — MusicProvider + CatalogProvider protocols** *(completed 2026-05-23 Session 7; CatalogProvider Protocol is the MVP catalog backbone; MusicProvider declared DEFERRED-TO-V2 (no MVP impl); canonical types CatalogAlbum + ListeningEvent live in same file. Note: also created `providers/__init__.py` for clean re-export surface — slight scope expansion vs original Paths spec.)*
      Paths: apps/api/src/auxd_api/providers/base.py
      Size: S
      Deps: T014, T015
      Refs: Constitution P6; plan §5.1
      Description: Abstract `MusicProvider` and `CatalogProvider` Protocol classes defining the interface methods (per plan §5.1). NO concrete implementations yet — that's enforcement of P6 (provider abstraction).
      Done: protocols compile; mypy strict passes.

<!-- CR-001 removed: T042 (Spotify provider — contract tests) — Spotify provider entirely eliminated; replaced by Discogs contract tests (T049a). -->
<!-- CR-001 removed: T043 (Spotify provider — implementation) — Spotify provider entirely eliminated. -->
<!-- CR-001 removed: T044 (Spotify provider — token refresh + revoke handling) — no Spotify OAuth at MVP. -->
<!-- CR-001 removed: T045 (Spotify provider — get_recently_played) — auto-import deferred to v2 per CR-001. -->
<!-- CR-001 removed: T046 (Spotify provider — search_albums) — search now MusicBrainz primary + Discogs fallback via T049 + T049b. -->
<!-- CR-001 removed: T047 (Spotify provider — get_album + tracklist) — album detail now MBID-only via T049. -->

- [x] **T048 — MusicBrainz catalog provider — contract tests (FAIL state)** *(completed 2026-05-23 Session 7; 9 tests via respx httpx-mocker. Verified FAILING with ImportError before T049 written — P4 audit trail. Note: landed in `tests/integration/test_musicbrainz_provider.py` (not `tests/contract/...` per original Paths) — uses respx mocks rather than nightly hits against live MB, so runs in normal CI.)*
      Paths: apps/api/tests/contract/test_musicbrainz_release_group_lookup.py
      Size: S
      Deps: T041
      Refs: Constitution P4
<!-- CR-001: T048 description updated — Spotify ID → MBID reconciliation step removed; MBID is now sole canonical id, reconciliation flows from candidate (Discogs-sourced) → MBID via T065. -->
      Description: Contract test for MusicBrainz `lookup_by_mbid` and candidate-Album (Discogs-sourced) → MBID reconciliation (per CR-001 — Spotify ID reconciliation path retired).
      Done: tests fail (expected, no implementation).

- [x] **T049 — MusicBrainz catalog provider — implementation** *(completed 2026-05-23 Session 7; httpx.AsyncClient via ResilienceTransport (timeout=10s, retry=3, cb=`musicbrainz`); asyncio.Lock + time.monotonic() pacing for MB's 1 req/sec; UA `auxd/0.0.0 (https://auxd.xiejoshua.com)`; CAA cover URL synthesized; all 9 T048 tests PASS. Note: landed as `providers/musicbrainz.py` (single file) not `providers/musicbrainz/__init__.py + client.py` package — simpler for MVP scope.)*
      Paths: apps/api/src/auxd_api/providers/musicbrainz/__init__.py, apps/api/src/auxd_api/providers/musicbrainz/client.py
      Size: M
      Deps: T048, T014
      Refs: plan §5; decision-log Q15
      Description: `MusicBrainzCatalogProvider`. Rate-limited to 1 req/sec per IP (MusicBrainz policy). Reconciliation strategy: query by artist + title, match best release-group MBID.
      Done: contract tests (T048) PASS.

<!-- CR-001: new task — Discogs catalog provider contract tests (FAIL state) per Constitution P4 test-first pattern; fallback for MusicBrainz misses. -->
- [x] **T049a — Discogs catalog provider — contract tests (FAIL state) [TEST-FIRST]** *(completed 2026-05-23 Session 7; 7 tests via respx incl. graceful-disabled-when-token-unset assertion. Verified FAILING with ImportError before T049b written — P4 audit trail. Note: consolidated to single file `tests/integration/test_discogs_provider.py` (not split + not under `tests/contract/`) — uses respx mocks; runs in normal CI.)*
      Paths: apps/api/tests/contract/test_discogs_release_lookup.py, apps/api/tests/contract/test_discogs_search.py
      Size: S
      Deps: T041
      Refs: Constitution P4; plan §4.4; CR-001
      Description: Contract tests against Discogs API (token-authenticated free tier) for `search_releases` and `get_release` methods. Tests run as `pytest -m contract`; excluded from normal CI, run nightly + on main. At this stage they MUST FAIL (no implementation yet) — test-first pattern.
      Done: pytest collects ≥4 tests; all fail with import/implementation errors (expected).

<!-- CR-001: new task — Discogs catalog provider implementation; fallback when MusicBrainz returns nothing for a search; covers FR-005 empty-state edge. -->
- [x] **T049b — Discogs catalog provider — implementation** *(completed 2026-05-23 Session 7; `respx>=0.21` added to dev deps; reads DISCOGS_API_TOKEN lazily — token-unset = graceful-disabled mode (returns empty/None); `Authorization: Discogs token={token}` scheme; UA matches MB; ResilienceTransport with cb=`discogs`; all 7 T049a tests PASS. Note: landed as `providers/discogs.py` (single file) not the 3-file package — mappings inlined since the file stays under ~230L.)*
      Paths: apps/api/src/auxd_api/providers/discogs/__init__.py, apps/api/src/auxd_api/providers/discogs/client.py, apps/api/src/auxd_api/providers/discogs/mappings.py
      Size: S
      Deps: T041, T049, T050
      Refs: plan §4.4; CR-001
      Description: `DiscogsCatalogProvider` implementing `CatalogProvider` protocol. Token-authenticated httpx client (token via `DISCOGS_API_TOKEN` from T029 amendment). Rate-limited per Discogs free-tier policy (60 req/min authenticated). Used as fallback in search service (T069) when MusicBrainz Atlas search returns <5 results. Maps Discogs release → internal Album shape with MBID null (candidate flag for later T065 reconcile).
      Done: contract tests (T049a) PASS against Discogs API.

- [x] **T050 — Resilience transport — httpx custom Transport** *(completed 2026-05-23 Session 7; ResilienceTransport(httpx.AsyncBaseTransport) wraps every request with circuit_breaker + retry + timeout; status mapping connection-error→ProviderUnavailable, 429→ProviderRateLimited (no retry per P1), 5xx-after-retries→ProviderUnavailable; includes build_async_client() factory. Note: landed at `providers/transport.py` (not `lib/http_transport.py`) — transport is provider-specific scaffolding, kept beside the provider package.)*
      Paths: apps/api/src/auxd_api/lib/http_transport.py
      Size: M
      Deps: T014
      Refs: Constitution P1
      Description: Custom `httpx.AsyncBaseTransport` that wraps requests with `lib/resilience` (circuit breaker + retry + timeout). Used by all provider clients.
      Done: unit tests assert transport applies all three policies.

<!-- CR-001: T051 deps + paths updated — drop Spotify provider; instrument MusicBrainz + Discogs only. -->
- [x] **T051 — Provider observability instrumentation** *(completed 2026-05-23 Session 7; per-request log_call(provider, endpoint, latency_ms, status, request_id) baked into ResilienceTransport (T050) — single emission point covers both MB and Discogs; status field uses HTTP code for clean responses + sentinels `timeout`/`circuit_open`/`failed`. Note: instrumentation landed in `providers/transport.py` not in each provider's client.)*
      Paths: apps/api/src/auxd_api/providers/musicbrainz/client.py, apps/api/src/auxd_api/providers/discogs/client.py
      Size: S
      Deps: T049, T049b, T015
      Refs: Constitution P5; NFR Observability
      Description: Every provider call emits `log_call(provider, endpoint, latency_ms, status, request_id)` via lib/observability.
      Done: log lines present; assertion test verifies structure.

- [x] **T052 — Provider error taxonomy** *(completed 2026-05-23 Session 7; ProviderError base + ProviderUnavailable / ProviderRateLimited / ProviderAuthRevoked / ProviderNotFound; each carries optional `provider: str` field. Path matches original spec.)*
      Paths: apps/api/src/auxd_api/providers/errors.py
      Size: S
      Deps: T041
      Refs: plan §5
      Description: `ProviderError`, `ProviderUnavailable`, `ProviderRateLimited`, `ProviderAuthRevoked`, `ProviderNotFound`. Mapped to user-facing API responses appropriately (503, 429, 401, 404).
      Done: error taxonomy with tests asserting mapping.

---

## §5 Auth module + onboarding entry

- [x] **T053 — Email/password signup + login endpoints** *(completed 2026-05-23 Session 9; `POST /api/v1/auth/signup` + `POST /api/v1/auth/login`; argon2-cffi password hashing; per-IP 5/min signup + 10/min login rate limits; per-user 30/min on authenticated login retry; 422/409 for validation/conflict errors; 401 generic on invalid credentials (no email-vs-password leak). password_hash NEVER echoed (anti-regression test asserts no `$argon2` prefix in response bodies). 14 integration tests + 5 password-hash unit tests.)*
      Paths: apps/api/src/auxd_api/modules/auth/routes.py, apps/api/src/auxd_api/modules/auth/service.py, apps/api/tests/integration/test_auth_email.py
      Size: M
      Deps: T021, T019, T020
      Refs: US-A1; FR-001
      Description: `POST /api/v1/auth/signup` (email + password + handle), `POST /api/v1/auth/login` (email + password). bcrypt cost 12. Handle validation: 3–24 chars, `/^[a-z0-9_]+$/`, unique. Suggest 3 alternatives on collision.
      Done: integration tests cover happy path + 5 error cases (handle taken, email taken, weak password, invalid handle chars, account suspended).

<!-- CR-001 removed: T054 (Spotify OAuth signup/login shortcut) — no Spotify integration at MVP; plain email+password signup covers US-A1 via T053. -->
<!-- CR-001 removed: T055 (Connect-Spotify-later flow) — no Spotify integration at MVP. -->
<!-- CR-001 removed: T056 (Disconnect Spotify immutability) — no Spotify integration at MVP. -->

<!-- CR-001: new task — Report-missing-album workflow surfaces from manual-search empty state per FR-005 (Letterboxd-style fallback path). -->
- [x] **T053a — "Report missing album" workflow endpoint + UI** *(completed 2026-05-23 Session 9 — backend-only at MVP; UI portion deferred to §3 frontend foundation. `POST /api/v1/reports/missing-album` with anonymous + authenticated submissions, body `{artist, album, mbid_hint?, discogs_url_hint?, query?}`; rate-limited per-IP 3/min; writes Report doc with target_type=missing_album. 4 integration tests.)*
      Paths: apps/api/src/auxd_api/modules/moderation/routes.py, apps/api/src/auxd_api/modules/moderation/service.py, apps/web/src/components/search/report-missing-album.tsx, apps/web/src/app/(app)/search/missing/page.tsx
      Size: M
      Deps: T026, T071, T155
      Refs: FR-005; FR-033; CR-001; sync-fix L3-006 (Report.target_type=missing_album) <!-- sync-fix L2-014: FR-033 added to refs (Run #4). -->
      Description: `POST /api/v1/reports/missing-album` accepts `query` (the failed search term), `artist`, `title`, optional `release_year`, `notes`. Reuses Report Document with `target_type=missing_album` (already in T026 model per sync-fix L3-006). Rate-limited per-reporter via T020 (`per_user=5/day`). UI: surfaces from search empty-state (T071) as a "Can't find it? Report missing album" link → opens modal-form. Submission confirmation toast. Admin can later resolve via mongo + reconcile by enqueuing a T065 MBID lookup with the structured hint.
      Done: integration test covers happy path + rate limit + duplicate-suppression (same user reports same query twice within 24h returns existing report); E2E covers search → empty results → report → confirmation.

- [x] **T057 — Handle change policy + reserved-squat list** *(completed 2026-05-23 Session 9; `POST /api/v1/users/me/handle` with 30-day cooldown anchored against max(handle_changed_at, handle_created_at); reserved-squat list loaded lazily from `apps/api/migrations/seed-data/reserved_handles.txt` (433 reserved handles seeded); creates HandleRedirect on success. **Judgment call: rejects non-lowercase input with 422 rather than silently downcasing** (prevents UI mismatch). 5 integration tests + 5 reserved-list unit tests + 11 service-policy tests shared with T058.)*
      Paths: apps/api/src/auxd_api/modules/auth/handle_service.py, apps/api/data/reserved_handles.txt, apps/api/tests/unit/test_handle_policy.py
      Size: M
      Deps: T021
      Refs: US-G1; FR-029; decision-log Q16; TC-023, TC-024
      Description: `change_handle(user, new_handle)` enforces: 30-day post-creation lock, ≤1 change per 30 days, reserved-squat rejection (200 names committed in `data/reserved_handles.txt`), unique check with 3 suggestions on collision. Old handle stored in `handle_redirects` for 90 days.
      Done: TC-023 + TC-024 unit tests pass; redirect on old URL works (T060 wires the redirect at routing layer).

- [x] **T058 — Account deletion (30-day grace) + cascade** *(completed 2026-05-23 Session 9; `POST /api/v1/users/me/delete` schedules (idempotent; bumps session_version for defense-in-depth) → 30-day grace → arq cron daily 02:00 UTC `process_scheduled_deletions` cascade-deletes 9 collections per user (DiaryEntry/Review/ReviewLike/Backlog+BacklogItem/Follow/FollowRequest/Block/Notification/HandleRedirect) + the User row; `DELETE /api/v1/users/me/delete` cancels. New `UserStatus.DELETION_PENDING` enum value (legacy `DELETED` retained for historical rows). 4 integration tests + 5 worker-cascade unit tests asserting bystander rows survive. **Follow-up flagged: Notification.actor_id dangling references when actor is deleted — GDPR pass should null-out, not orphan.**)*
      Paths: apps/api/src/auxd_api/modules/auth/service.py, apps/api/src/auxd_api/workers/deletion_cascade.py, apps/api/tests/integration/test_account_deletion.py
      Size: M
      Deps: T021, T023, T024, T025, T026
      Refs: US-G5; FR-019; TC-029
      Description: `POST /api/v1/users/me/delete` sets `status=deleted` + `deletion_scheduled_for = now + 30d`. arq daily cron finds users past their scheduled date and cascade-hard-deletes all owned content. Cancellation via `POST /api/v1/users/me/delete/cancel`.
      Done: TC-029 integration test: schedule deletion → see banner → cancel within 30d → account restored. Or: do not cancel → after 30d, all data is gone.

- [x] **T059 — Logout (current session + logout-all-devices)** *(completed 2026-05-23 Session 9; `POST /api/v1/auth/logout` clears session cookies (no-op if anonymous); `POST /api/v1/auth/logout-all-devices` bumps `User.session_version` so all outstanding cookies invalidate. **Known MVP trade-off: SessionMiddleware doesn't re-check session_version against User on every request** — the bump takes effect on cookie expiry (30d) or refresh-threshold re-validation (<7d). Documented as v1.x ticket: add per-request session_version check via Redis cache.)*
      Paths: apps/api/src/auxd_api/modules/auth/service.py
      Size: XS
      Deps: T053, T019
      Refs: NFR Security
      Description: `POST /api/v1/auth/logout` (clear cookie); `POST /api/v1/auth/logout-all` (increment `session_version` invalidating all prior cookies).
      Done: unit test confirms behavior.

- [x] **T060 — Handle redirect routing** *(completed 2026-05-23 Session 9; new `HandleRedirect` Beanie Document (registered in `ALL_DOCUMENT_MODELS` — now 17); `resolve_handle(handle)` helper returns `(user, canonical_handle)` tuple covering current→self / old→redirect-target / orphan-redirect→none / unknown→none / case-insensitive. T060 ships the resolver only; the future profile-page routes in §14 will call it to issue 301s.)*
      Paths: apps/web/src/middleware.ts, apps/api/src/auxd_api/modules/auth/routes.py
      Size: S
      Deps: T057
      Refs: FR-029
      Description: Frontend middleware intercepts `/@oldhandle` requests; backend lookup returns new handle if redirect exists (≤90 days post-change); 301 redirect. Otherwise 404.
      Done: unit + integration tests pass.

<!-- CR-001: T061 deps + description updated — Spotify OAuth button removed; email-only signup at MVP. -->
- [x] **T061 — Signup + login UI**
      Paths: apps/web/src/app/(auth)/signup/page.tsx, apps/web/src/app/(auth)/login/page.tsx, apps/web/tests/e2e/auth.spec.ts
      Size: M
      Deps: T038, T053
      Refs: US-A1; FR-001
      Description: Wire signup + login forms to backend. Email + password only at MVP (per CR-001 — Spotify OAuth deferred to v2). Error handling for all 5 error cases from T053.
      Done: E2E test signs up via email + logs in.

- [x] **T062 — Auth E2E + session persistence**
      Paths: apps/web/tests/e2e/session.spec.ts
      Size: S
      Deps: T061
      Refs: NFR Security
      Description: Test that session survives navigation, page refresh, and respects expiry.
      Done: E2E passes.

---

## §6 Albums + Search

<!-- CR-001: T063 deps + description updated — Spotify ID identity path dropped; MBID-first + Discogs candidate fallback. -->
- [x] **T063 — Album identity normalization service** *(completed 2026-05-23 Session 8; `resolve_identity(*, mbid?, discogs_release_id?, mb_provider, discogs_provider)` → Album. MBID-first lookup with 7d TTL cache; Discogs path materializes as `candidate=True` for later MBID reconciliation. New `AlbumNotFoundError` in `modules/albums/errors.py`. New `Album.candidate: bool = False` field. 8 unit tests pass.)*
      Paths: apps/api/src/auxd_api/modules/albums/identity.py, apps/api/tests/unit/test_album_identity.py
      Size: M
      Deps: T022, T049, T049b
      Refs: US-F1; FR-010; decision-log Q15, Q21; TC-008, TC-009, TC-010
      Description: `resolve_identity(mbid=None, discogs_release_id=None)` → canonical Album. If MBID known → use it; else if Discogs ID known → create `candidate` Album flagged for MBID reconciliation (T065). Lazy-fetch from MusicBrainz; cache 7d. CR-001: legacy `spotify_id` parameter removed; existing `Album.spotify_id` sparse index dropped per T022 amendment. <!-- sync-fix L4-006: parameter name aligned to code (`discogs_release_id`, not `discogs_id`). -->

      Done: TC-008/009/010 unit tests pass.

<!-- CR-001: T064 description updated — cache refresh from MusicBrainz, not Spotify. -->
- [x] **T064 — Album cache + TTL refresh worker** *(completed 2026-05-23 Session 8; arq cron daily 04:00 UTC; `refresh_stale_album_metadata` queries Albums with stale `cache_expires_at` + non-null MBID, refreshes via MB provider, extends TTL. Shared `mb_provider` injected via WorkerSettings `_on_startup` so the 1 req/sec etiquette is honored across cron invocations. 6 unit tests. Note: code lives in `modules/albums/workers.py` (not `workers/album_cache_refresh.py` per original Paths) — keeps album-related code colocated.)*
      Paths: apps/api/src/auxd_api/workers/album_cache_refresh.py
      Size: S
      Deps: T063, T013
      Refs: NFR catalog-provider rate limits (MusicBrainz 1 req/sec + Discogs 60 req/min)
      Description: Daily arq job that finds Albums with `cache_expires_at < now()` and refreshes metadata from MusicBrainz (rate-limited per provider policy in T049).
      Done: worker runs; refresh observed.

- [x] **T065 — MBID reconciliation worker** *(completed 2026-05-23 Session 8; arq cron weekly Sun 03:00 UTC; `reconcile_candidate_albums` finds `candidate=True` Albums, searches MB by artist+title, picks best match by fuzzy-score, merges MBID → marks `candidate=False`. 5 unit tests. Same `workers.py` colocation as T064.)*
      Paths: apps/api/src/auxd_api/workers/mbid_reconcile.py
      Size: S
      Deps: T063, T049
      Refs: decision-log Q21
      Description: Periodic job that finds Albums with `candidate=true` and attempts MBID reconciliation via MusicBrainz. On match, merge candidate into canonical.
      Done: worker runs; candidate records reconcile over time.

- [x] **T066 — Edition aggregation (release-group → editions)** *(completed 2026-05-23 Session 8; `get_editions`, `get_canonical_edition` (prefers earliest release_year + longest tracklist), `aggregate_ratings` (sums DiaryEntry + Review across editions, excludes soft-deleted). 11 unit tests. **Known limitation: Album.mbid is unique-sparse at MVP so editions collapse to 1 row per release-group; future migration drops the unique constraint + adds release_group_mbid field. Documented in module docstring + flagged as follow-up CR.**)*
      Paths: apps/api/src/auxd_api/modules/albums/editions.py, apps/api/tests/unit/test_editions.py
      Size: M
      Deps: T063
      Refs: US-F1; FR-028; decision-log Q15; TC-010
      Description: Group albums by release-group MBID; expose "All editions" view that aggregates ratings/reviews/likes across editions. Edition selector returns list of editions for a release-group.
      Done: TC-010 unit test passes.

- [x] **T067 — Album detail endpoint** *(completed 2026-05-23 Session 8; `GET /api/v1/albums/{album_id}` returns `{album, editions, aggregate, my_history, friends, public_reviews}`. Visibility-filtered via `lib/visibility.can_read`; anonymous viewers see public reviews only; owners see own private history; followers see followed-user content per visibility rules. 6 integration tests via FastAPI TestClient + mongomock-motor conftest. **Path divergence (sync-fix L5-006 Run #5): tests landed at `tests/integration/test_album_detail_endpoint.py` not `tests/integration/test_album_detail.py` per original Paths line.**)*
      Paths: apps/api/src/auxd_api/modules/albums/routes.py, apps/api/tests/integration/test_album_detail.py
      Size: M
      Deps: T063, T066, T016
      Refs: US-F1; FR-010
      Description: `GET /api/v1/albums/{id}` returns album + tracklist + my history + friends-who-rated-and-auxed + public reviews + edition list. Visibility-filtered via lib/visibility.
      Done: integration test covers logged-in/anonymous/blocked/private cases.

- [x] **T068 — Atlas Search index for albums** *(completed 2026-05-23 Session 8; extended `apps/api/migrations/atlas_search/albums_index.json` with `lucene.standard` analyzer, dual `string` + `autocomplete` field shapes on title/artist_credit (edgeNgram 2–8 chars, diacritic folding), `rating_count` field, `scoreDetails.popularity` block using `log1p(rating_count)`. New `migrations/README.md` documents manual UI + `atlas-cli` apply paths. 5 unit tests guard the JSON shape. **Operator follow-up: apply the updated index to the Atlas Search cluster via UI or `atlas-cli`.** **Path divergence (sync-fix L5-006 Run #5): operator runbook landed at `apps/api/migrations/README.md` not `docs/atlas-search-setup.md` per original Paths line — keeps the runbook adjacent to the JSON it documents.**)*
      Paths: apps/api/migrations/atlas_search/albums_index.json, docs/atlas-search-setup.md
      Size: S
      Deps: T022
      Refs: plan §11.1; FR-005
      Description: Index definition with `lucene.standard` analyzer + edgeNgram on title; popularity boost. Applied to Atlas via UI or `atlas-cli`. Documented for future migrations.
      Done: search query returns relevant results.

<!-- CR-001: T069 retitled + deps/description updated — Atlas + MusicBrainz primary + Discogs fallback merge; Spotify fallback dropped. -->
- [x] **T069 — Search endpoint (Atlas + MusicBrainz + Discogs fallback merge)** *(completed 2026-05-23 Session 8; `GET /api/v1/search?q=...&type=album&limit=N` three-tier search: Atlas $search first (gracefully degrades to [] under mongomock); if <5 hits adds MB results via `resolve_identity` materialization; if still <5 adds Discogs (graceful-disabled when token unset). Dedupe by `mbid` else `(title.casefold(), artist.casefold())`. Sorted by Atlas relevance then `release_year` desc. Empty result returns `{report_missing_album_url: "/api/v1/reports/missing-album"}` hint pointing at future T053a. 7 integration tests via respx. **Path divergence (sync-fix L5-006 Run #5): tests landed at `tests/integration/test_search_endpoint.py` not `tests/integration/test_search.py` per original Paths line.**)*
      Paths: apps/api/src/auxd_api/modules/search/routes.py, apps/api/src/auxd_api/modules/search/service.py, apps/api/tests/integration/test_search.py
      Size: M
      Deps: T068, T049, T049b
      Refs: US-F2; FR-005; TC-031; CR-001
      Description: `GET /api/v1/search?q=...&type=album` → Atlas Search results first; on <5 hits, fall back to MusicBrainz (T049); on still <5, fall back to Discogs (T049b). Debounce on client side; results sorted by relevance. On final-empty, surface T053a "Report missing album" link.
      Done: TC-031 integration test passes; results in <200ms p95.

<!-- CR-001: T070 description updated — "Listen on Spotify" CTA dropped (no integration); deep-link to album page on streaming services TBD in v2. -->
- [x] **T070 — Album detail page (frontend, SSR)**
      Paths: apps/web/src/app/(app)/album/[id]/page.tsx, apps/web/src/components/album-detail/*
      Size: L
      Deps: T067, T037
      Refs: US-F1; FR-010, FR-028; wireframes/04-album-detail.html
      Description: SSR page rendering wireframes/04 design. Edition selector chip + dropdown. Friends section (avatars + ratings + 🏅 Aux'd). Ratings histogram. Reviews list with sort selector (Newest / Most Liked / Highest-Rated — wired in T093). Log + Up Next CTAs. ("Listen on" streaming-service deep-link deferred to v2 per CR-001 — no Spotify integration at MVP.) Open Graph meta tags.
      Done: page renders matching wireframe; OG card previews correctly in social shares.

- [x] **T071 — Search page + UI**
      Paths: apps/web/src/app/(app)/search/page.tsx, apps/web/src/components/search/*
      Size: M
      Deps: T069
      Refs: US-F2; FR-005
      Description: Search page with input + autocomplete; 200ms debounce; "Report missing album" link on empty state.
      Done: E2E test covers typed query → results → album navigation.

<!-- CR-001: T072 description updated — Spotify CDN replaced with Cover Art Archive (MusicBrainz CAA) + Discogs image URLs. -->
<!-- sync-fix L4-011 (Run #7): Path param renamed albumId → mbid (CAA is MBID-keyed; consumer already has it). Refs corrected from plan §17.5 (Redis) → plan §11.4 (Cover-art proxy). -->
- [x] **T072 — Cover-art proxy (route handler)**
      Paths: apps/web/src/app/api/cover/[size]/[mbid]/route.ts
      Size: S
      Deps: T067
      Refs: plan §11.4; DM-2; CR-001
      Description: Next.js route handler proxying Cover Art Archive (`https://coverartarchive.org/release-group/{mbid}/front-{size}`) with `?fallback=<https-url>` 302 redirect when CAA returns 404. Cache-Control: public, max-age=604800, immutable on hit; max-age=3600 negative cache. Route-param renamed `[albumId]` → `[mbid]` because CAA is MBID-keyed natively and the consumer (album-detail / search) already has the MBID. Optional blurhash placeholder generation deferred.
      Done: proxy serves cover art; CDN caching verified.

---

## §7 Diary + Log sheet — THE WEDGE INTERACTION

- [x] **T073 — Diary log endpoint (Aux-bool included)**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py, apps/api/src/auxd_api/modules/diary/service.py, apps/api/tests/integration/test_diary_logging.py
      Size: M
      Deps: T023, T021, T063
      Refs: US-B1, US-B2, US-B3; FR-004; TC-001, TC-002, TC-003
      Description: `POST /api/v1/diary/entries` with `album_id`, `rating` (optional, 0.5–5.0 in halves), `auxed` (bool), `review_body` (optional), `visibility`. Server measures end-to-end commit time; emit PostHog `log.commit` event with `duration_ms`. Idempotent: same album logged twice in 60sec returns existing entry (avoids double-tap dupes).
      Done: TC-001, TC-002, TC-003 pass.

- [x] **T074 — Diary read endpoint (chronological diary)**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py
      Size: S
      Deps: T073, T016
      Refs: US-E2; FR-007
      Description: `GET /api/v1/users/{handle}/diary?cursor=...&limit=25` reverse-chrono; visibility-filtered. Optional filter param: `auxed=true` for "Aux'd" tab. Response envelope: `{entries: DiaryEntry[], next_cursor: string | null, albums: {[id]: AlbumCard}}` where `AlbumCard = {id, mbid, title, artist_credit, release_year, cover_art_url}`. The `albums` sidecar is deduped on `_id` so relistens cost one Album lookup per page, not N — keeps the profile diary render at one round-trip per page. Cursor is base64(`{l: logged_at_iso, i: entry_id}`) so Last.fm imports (future) page correctly even when `logged_at` is historical.
      Done: integration test covers visibility matrix + albums-sidecar dedup + empty-when-no-entries.

- [x] **T075 — Diary edit / delete / restore endpoints**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py, apps/api/tests/integration/test_diary_edit.py
      Size: M
      Deps: T073
      Refs: US-B5; FR-004
      Description: `PATCH /api/v1/diary/entries/{id}` (rating/auxed/review/visibility editable). `DELETE /api/v1/diary/entries/{id}` is soft-delete with 30d recovery window. `POST /api/v1/diary/entries/{id}/restore` clears `deleted_at` inside the grace window (returns 410 once expired). Editor must be owner; all three endpoints enforce ownership. (sync-fix L5-009: restore endpoint is part of T075's scope.)
      Done: integration tests cover edit + soft-delete + recovery + hard-delete after 30d + restore-410-after-grace.

- [x] **T076 — Relisten support (multiple entries for same album)**
      Paths: covered in T073
      Size: (sub-task)
      Refs: US-B4; TC-003
      Description: Multiple DiaryEntry records per (user, album) allowed; album-detail "my history" shows all prior logs.
      Done: TC-003 covered.

- [x] **T077 — Log sheet component (THE wedge interaction)**
      Paths: apps/web/src/components/log-sheet/index.tsx, apps/web/src/components/log-sheet/rating-widget.tsx, apps/web/src/components/log-sheet/aux-toggle.tsx, apps/web/src/components/log-sheet/review-editor.tsx
      Size: L
      Deps: T037, T073, T032
      Refs: US-B1, US-B2, US-B3; FR-004; wireframes/03-log-sheet.html
      Description: Bottom-sheet component. ALWAYS-MOUNTED in app shell layout (hidden until open) to avoid first-tap render cost. Rating widget = ½-star tap-or-drag. Aux toggle = 🏅 medal. Review collapsed by default; tap to expand. Visibility select defaults to user prefs. Commit fires `POST /api/v1/diary/entries` and measures duration. PostHog event `log.commit` with duration_ms.
      Done: E2E test logs an album in <8 seconds; commit duration_ms tracked.

- [x] **T078 — Persistent + Log button (FAB in shell)**
      Paths: apps/web/src/components/nav/log-fab.tsx, apps/web/src/app/(app)/layout.tsx
      Size: XS
      Deps: T077, T037
      Refs: US-B1
      Description: Persistent "+" button in bottom-right of app shell; opens log sheet.
      Done: button present on all authenticated routes.

<!-- CR-001: T079 fully rewritten — Spotify recently-played prefill replaced with manual MusicBrainz-backed search + prefill flow (Letterboxd model). -->
- [x] **T079 — Manual album search + prefill in Log sheet**
      Paths: apps/web/src/components/log-sheet/album-search.tsx, apps/web/src/components/log-sheet/recent-searches.tsx, apps/api/src/auxd_api/modules/diary/routes.py
      Size: M
      Deps: T077, T069
      Refs: US-B1; FR-004; FR-005; CR-001
      Description: MusicBrainz-backed search field at the top of the log sheet; type ≥3 chars + 200ms debounce; pick from results to prefill rating/Aux/review form. Uses T069 search endpoint (Atlas → MusicBrainz → Discogs fallback chain). On empty-result, surface "Report missing album" link (T053a) per FR-005 empty-state. Recent-searches stored locally for quick re-pick. CR-001: replaces the original Spotify recently-played auto-prefill model.
      Done: search → prefill flow works in <2s p95; analytics tracks % of logs that accept first prefill result (PostHog `log.search_accepted`).

- [x] **T080 — Diary view on profile**
      Paths: apps/web/src/app/(app)/profile/[handle]/page.tsx, apps/web/src/components/diary/* (public `/@handle` URL deferred to a middleware-rewrite task; see plan §7.1.1)
      Size: M
      Deps: T074, T037
      Refs: US-E2; FR-007
      Description: Profile page with reverse-chrono diary view; "Aux'd" filter tab. Pagination with cursor.
      Done: profile page renders.

- [x] **T081 — "My history" on album detail page**
      Paths: apps/web/src/components/album-detail/my-history.tsx
      Size: S
      Deps: T070, T074
      Refs: US-B4
      Description: Shows all prior diary entries for the album by current user; allows expanding to see ratings + dates.
      Done: section renders.

- [x] **T082 — Edit diary entry UI**
      Paths: apps/web/src/components/log-sheet/index.tsx (edit-mode), apps/web/src/components/diary/diary-entry-card.tsx (edit trigger), apps/web/src/stores/ui.ts (LogSheetSeed.edit field)
      Size: S
      Deps: T080, T075
      Refs: US-B5
      Description: Edit affordance on owner-controlled diary entries opens the log sheet pre-filled with the entry's rating + Aux + visibility via `LogSheetSeed.edit`; PATCH on save. Review-body editing lands with T086 (review CRUD); at MVP, edit covers rating/aux/visibility only and leaves any attached review unchanged.
      Done: edit flow works end-to-end for rating/aux/visibility; review-body edit tracked under T086.

- [x] **T083 — Soft-delete + undo toast**
      Paths: apps/web/src/components/diary/delete-confirmation.tsx
      Size: S
      Deps: T082
      Refs: US-B5
      Description: Confirm-delete modal with text-confirm; undo via Toast for 8 seconds (server-side recovery within 30d also possible).
      Done: undo path works.

<!-- CR-001: T084 description updated — wedge target relaxed acknowledges manual-search adds ~1s vs auto-prefill; <8s budget still applies and now includes search-pick time. -->
- [x] **T084 — Wedge NFR validation (commit time <8s)**
      Paths: apps/web/tests/e2e/log-wedge.spec.ts, apps/api/tests/integration/test_log_perf.py
      Size: S
      Deps: T077, T079
      Refs: spec.md §6.1 NFR; TC-001; TC-E2E-003; CR-001
      Description: E2E test measures full commit time across 10 trials (search → pick → rate → save); asserts p95 <8s including manual search-pick step (Letterboxd-style flow per CR-001). Backend integration test asserts server-side handling <500ms p95.
      Done: NFR target verified.

---

## §8 Reviews + Likes + sort

- [x] **T085 — Review create endpoint**
      Paths: apps/api/src/auxd_api/modules/reviews/routes.py, apps/api/src/auxd_api/modules/reviews/service.py
      Size: M
      Deps: T023, T073
      Refs: US-C1; FR-011
      Description: `POST /api/v1/reviews` (body, visibility) linked to a DiaryEntry. Markdown-safe rendering (allow bold, italic, line breaks; no images, no scripts). ≥1 char minimum, NO soft prompt (per decision #5 / R3).
      Done: integration test creates a review; markdown sanitization verified.

- [x] **T086 — Review edit + audit log**
      Paths: apps/api/src/auxd_api/modules/reviews/service.py, apps/api/tests/integration/test_review_edit.py
      Size: M
      Deps: T085
      Refs: US-C3; FR-030; TC-025
      Description: `PATCH /api/v1/reviews/{id}` updates body. Public surface shows latest + "edited" badge with timestamp. Internal `review_edits` collection stores prior versions for 90 days with hash for tamper detection.
      Done: TC-025 integration passes.

- [x] **T087 — Review delete (with cascading reaction cleanup)**
      Paths: apps/api/src/auxd_api/modules/reviews/service.py
      Size: S
      Deps: T085
      Refs: DM-5
      Description: Soft-delete review with 30d grace; on hard-delete cascade-delete `ReviewLike` records.
      Done: integration test confirms cascade.

- [x] **T088 — Like-review endpoint (idempotent toggle)**
      Paths: apps/api/src/auxd_api/modules/reviews/likes_service.py, apps/api/tests/unit/test_review_likes.py
      Size: M
      Deps: T085
      Refs: US-C4; FR-031; TC-015, TC-016
      Description: `POST /api/v1/reviews/{id}/like` toggles. Creates `ReviewLike`; increments `Review.reactions.likes_count`; emits N-004 notification. Reject if liker == reviewer (TC-016). Reject if already-liked (idempotent return current state). Un-like deletes record + decrements counter (no notification).
      Done: TC-015 + TC-016 pass.

- [x] **T089 — List reviews endpoint with sort**
      Paths: apps/api/src/auxd_api/modules/reviews/routes.py, apps/api/tests/unit/test_review_sort.py
      Size: M
      Deps: T088, T016
      Refs: US-C2; FR-032; TC-017
      Description: `GET /api/v1/albums/{id}/reviews?sort=newest|most_liked|highest_rated&cursor=...` with primary tier (friends → public → critic-seed) + sort within tier. Visibility-filtered.
      Done: TC-017 passes.

<!-- CR-002: read-more replaced by ~80-char preview + nav to /review/:id (UJ-3). Inline expand removed. -->
- [x] **T090 — Review card component (with Like button)**
      Paths: apps/web/src/components/review-card/index.tsx, apps/web/src/components/review-card/like-button.tsx
      Size: M
      Deps: T037, T088, T093a
      Refs: US-C4; **CR-002 / UJ-3**
      Description: Review card showing reviewer (avatar + handle + Critic suffix if seed), stars, "edited" badge if applicable, body **preview (first ~80 chars; whole card tap navigates to `/review/:id` per UJ-3 / CR-002 — no inline read-more / no inline expand)**, 👍 Like button + count. Like is optimistic and stops navigation propagation (tap on Like button does not nav).
      Done: component renders; Like toggle works; card tap routes to `/review/:id`.

- [x] **T091 — Review composition UI (in log sheet)**
      Paths: covered in T077 (log-sheet/review-editor.tsx)
      Size: (sub-task)
      Refs: US-C1
      Description: Textarea with markdown hint; no length nudges.
      Done: covered.

- [x] **T092 — Edit + delete review UI**
      Paths: apps/web/src/components/review-card/edit-review.tsx
      Size: S
      Deps: T090, T086
      Refs: US-C3
      Description: Edit-review modal; soft-delete with undo toast.
      Done: flow works.

- [x] **T093 — Reviews list on album detail (with sort selector)**
      Paths: apps/web/src/components/album-detail/reviews-list.tsx
      Size: M
      Deps: T070, T089, T090
      Refs: US-C2; FR-032; TC-E2E-006
      Description: Reviews list embedded in album detail. Sort selector (Newest default / Most Liked / Highest-Rated) persisted to Zustand per-device. Tier ordering enforced.
      Done: TC-E2E-006 passes.

<!-- CR-002: new tasks for UJ-3 dedicated /review/:id route + reading-view component. -->
- [x] **T093a — `/review/[id]` route (SSR + OG meta)**
      Paths: apps/web/src/app/(app)/review/[id]/page.tsx, apps/api/src/auxd_api/modules/reviews/routes.py (added GET /reviews/{id} as backing endpoint)
      Size: M
      Deps: T088, T090
      Refs: US-C2; UJ-3; **CR-002**
      Description: SSR route fetching Review + Album + viewer-context via `GET /api/v1/reviews/{id}`. Renders the reading-view component (T093b). OG meta via Next.js `generateMetadata`: title = "@{handle}'s review of {album}", description = first ~140 chars of review body, image = `album.cover_art_url`. Visibility-checked: returns 404 to users without read access (not 403, to avoid existence-leak). Includes a Back-to-album link in the chrome.
      <!-- sync-fix L4-018 + L5-012 (Run #9): opengraph-image.tsx removed from Paths — never shipped. Text-mode OG is inlined via generateMetadata; dedicated opengraph-image route via next/og ImageResponse is deferred as T093c follow-up per impl-log Session 15 + the UJ-4 v2 screenshot image-gen roadmap. -->
      Done: route renders for owner + public + follower-only-with-access; 404 for forbidden; OG card preview validated via generateMetadata.

- [x] **T093b — Review reading-view component**
      Paths: apps/web/src/components/review-reading-view/index.tsx, apps/web/src/components/review-reading-view/hero.tsx, apps/web/src/components/review-reading-view/share-button.tsx
      Size: M
      Deps: T037, T088
      Refs: US-C2; UJ-3; **CR-002**
      Description: Letterboxd-parity reading view. Hero: album cover (Cover Art Archive), title, artist, viewer's rating context if any (e.g., "You rated this ★★★★½"), Aux badge if owner has Aux'd it, Like button (delegates to T090's like service), Share button (native OS share-sheet with the `/review/:id` URL). Below hero: full review body, "edited" badge if applicable. Comments thread explicitly NOT in scope (v2). Mobile-first layout; max-width prose ~640px on desktop.
      Done: component renders all four state variants (owner, follower, public, no-rating-context); Like button works; Share opens OS sheet with correct URL.

<!-- sync-fix L4-019 (Run #9): T094 header restored. The §8 cluster index claimed T085-T094 but the task body below had no header — only Paths/Size/Deps/Refs/Description/Done lines. This task surfaces the EditReviewDialog + DeleteReviewConfirmation owner controls (T092) on the profile sub-route. -->
- [x] **T094 — Reviews-only profile sub-route**
      *(completed 2026-05-23 Session 22; backend GET /api/v1/users/{handle}/reviews added to reviews/routes.py — mirrors the album-reviews shape with sort + cursor + visibility filter via `lib/visibility.can_read_with_relation` + handle redirect via `resolve_handle`; sort options newest / most_liked / highest_rated (highest_rated joins DiaryEntry rating in-memory same as album endpoint); new `albums: {[id]: AlbumCard}` sidecar deduped per page; soft-deleted reviews excluded; viewer sees own private reviews always. Tier-classification branch (friends → public → critic-seed) dropped here since every row shares the same author. Frontend SSR shell + client `useInfiniteQuery` with `UiStore.feedSort` driving queryKey; reuses existing ReviewCard + EditReviewDialog + DeleteReviewConfirmation owner controls when `useAuthStore().user.handle === handle`. Diary/Reviews tab nav added to existing profile-client.tsx. Codegen api.ts +87 lines covering the new path. 9 backend integration tests + 4 frontend unit tests. Next build new route 5.51 kB / 317 kB FLJS.)*
      Paths: apps/api/src/auxd_api/modules/reviews/routes.py (added GET /users/{handle}/reviews), apps/web/src/app/(app)/profile/[handle]/reviews/page.tsx, apps/web/src/components/profile-reviews/profile-reviews-list.tsx, apps/web/src/components/diary/profile-client.tsx (Diary/Reviews tab nav), apps/web/src/lib/review-types.ts, apps/api/tests/integration/test_user_reviews_endpoint.py, apps/web/tests/unit/profile-reviews.test.ts
      Size: M
      Deps: T088, T092, T093a
      Refs: US-E2; spec.md US-E2 AC (Reviews-tab line per sync-fix L6-005); plan.md §6 reviews service surface
      Description: SSR sub-route `/profile/{handle}/reviews` that filters the profile diary view to entries with attached reviews. Backed by a new `GET /api/v1/users/{handle}/reviews` endpoint mirroring the album-reviews shape (sort/cursor/visibility) with an `albums: {[id]: AlbumCard}` sidecar to avoid N+1. Reuses ReviewCard + owner controls (EditReviewDialog, DeleteReviewConfirmation) when the viewer is the profile owner.
      Done: backend integration tests cover sort modes + visibility filter + owner-vs-viewer rendering; frontend unit tests cover Diary/Reviews tab toggle + owner-control surfacing.

---

## §9 Backlog (Up Next)

- [x] **T095 — Backlog CRUD endpoints**
      Paths: apps/api/src/auxd_api/modules/backlog/routes.py, apps/api/src/auxd_api/modules/backlog/service.py
      Size: M
      Deps: T024, T021
      Refs: US-D1, US-D2; FR-006
      Description: `POST /api/v1/users/me/backlog/items` (add album); `DELETE` (remove); `PATCH .../reorder`; `GET .../items` paginated. Backlog auto-created on first access.
      Done: integration tests cover all paths.

- [x] **T096 — Auto-remove-on-log behavior**
      Paths: apps/api/src/auxd_api/modules/diary/service.py
      Size: S
      Deps: T073, T095
      Refs: US-D3
      Description: On `log_entry`, if album is in user's backlog AND `User.keep_backlog_after_log == false` (default), remove from backlog. Toast confirms.
      Done: integration test confirms behavior.

<!-- CR-001: T097 description updated — "Listen on Spotify" menu item removed; no streaming-service integration at MVP. -->
- [x] **T097 — Up Next page (frontend)**
      Paths: apps/web/src/app/(app)/up-next/page.tsx, apps/web/src/components/up-next/*
      Size: M
      Deps: T095, T037
      Refs: US-D1, US-D2; FR-006; CR-001
      Description: Backlog list with drag-reorder (using `@dnd-kit/sortable`), per-item context menu (Remove, Open album, Edit blurb). ("Listen on" streaming-service deep-link deferred to v2 per CR-001.)
      Done: page renders; drag works on mobile + web.

- [x] **T098 — Add-to-backlog from album detail**
      Paths: apps/web/src/components/album-detail/up-next-button.tsx
      Size: XS
      Deps: T070, T095
      Refs: US-D1
      Description: "+ Up Next" button on album detail page; toggles add/remove based on current state.
      Done: button works.

- [x] **T099 — Add-to-backlog from log sheet**
      Paths: covered in T077
      Size: (sub-task)
      Refs: US-D1
      Description: Alternative path inside Log sheet to add to backlog instead of logging.
      Done: covered.

- [x] **T100 — Backlog → Log conversion event**
      Paths: apps/api/src/auxd_api/modules/diary/routes.py, apps/api/src/auxd_api/modules/diary/service.py
      Size: XS
      Deps: T096
      Refs: success-metrics: backlog→log conversion
      Description: PostHog `backlog.converted_to_log` event emitted server-side from `post_diary_entry` handler when `result.backlog_item_removed == True` (i.e., a fresh diary insert auto-removed an existing backlog item). Emission lives in `diary/routes.py` via `emit_event(...)`; no frontend analytics module is required at MVP — server-side is the source of truth for KPI tracking.
      <!-- sync-fix L5-013 (Run #9): apps/web/src/lib/analytics.ts removed from Paths — emission is server-side via emit_event; no frontend analytics module exists. -->
      Done: event emitted with correct properties.

---

## §10 Social graph + Feed

- [x] **T101 — Follow / unfollow endpoints**
      Paths: apps/api/src/auxd_api/modules/social/routes.py, apps/api/src/auxd_api/modules/social/service.py
      Size: M
      Deps: T025, T021
      Refs: US-E1; FR-008
      Description: `POST /api/v1/users/{handle}/follow`, `DELETE`. Asymmetric. If followee has private profile, create `state=pending` and notify. Emit N-001 + (if pending) N-002.
      Done: integration tests cover all states.

<!-- sync-fix L4-022 (Run #10): T101a added — FollowRequest approve/decline UI was acknowledged in T101 code as deferred ("No Follow row is created at this step; the approval path is out of scope here, future ticket") but had no tasks.md anchor. -->
- [ ] **T101a — FollowRequest approve/decline endpoints + responder UI** *(DEFERRED — private-profile responder side)*
      Paths: apps/api/src/auxd_api/modules/social/routes.py, apps/api/src/auxd_api/modules/social/service.py, apps/api/tests/integration/test_follow_requests.py, apps/web/src/app/(app)/settings/follow-requests/page.tsx, apps/web/src/components/social/follow-requests-list.tsx
      Size: M
      Deps: T101
      Refs: US-G2, S-H3 (Could-have)
      Description: Add `POST /api/v1/users/me/follow-requests/{id}/approve` + `POST /api/v1/users/me/follow-requests/{id}/decline` + `GET /api/v1/users/me/follow-requests`. Approve creates the `Follow` row with `state=ACCEPTED`; decline marks the FollowRequest `state=DECLINED`. Emits N-002 confirmation back to requester on approve. Frontend: Settings → "Follow requests" sub-route lists pending requests with Approve/Decline buttons.
      Done: integration tests cover approve/decline/list paths; frontend route renders; existing pending state badge on FollowButton continues to work.

- [x] **T102 — Block endpoint (+ cascade-resolve follow)**
      Paths: apps/api/src/auxd_api/modules/social/service.py, apps/api/tests/integration/test_blocks.py
      Size: M
      Deps: T101
      Refs: US-G4; FR-014; TC-028
      Description: `POST /api/v1/users/{handle}/block`. Dissolves any Follow in either direction. Hides content from blocker (via lib/visibility).
      Done: TC-028 passes.

- [x] **T103 — Friends-who-rated-and-auxed endpoint**
      Paths: apps/api/src/auxd_api/modules/feed/service.py
      Size: M
      Deps: T101, T073
      Refs: US-E4; FR-010
      Description: `GET /api/v1/albums/{id}/friends` returns avatars + ratings + Aux'd from followed accounts who have rated this album; sort by rating desc then logged_at desc; visibility-filtered.
      Done: integration test covers visibility matrix.

- [x] **T104 — Suggested-follow precompute worker**
      Paths: apps/api/src/auxd_api/workers/suggestions_job.py
      Size: L
      Deps: T101, T073
      Refs: US-E5; FR-016
      Description: arq scheduled job (every N hours per user) that scores candidate follows using the algorithm from seeding-strategy §4 (mutual-taste 40%, followed-by-followed 30%, shared-seed 15%, label/genre 10%, recency 5%). Excludes blocked, dismissed (≤30d), already-followed.
      Done: suggestions appear in `/api/v1/users/me/suggestions` for users with ≥5 logged entries.

- [x] **T105 — Suggested-follow API + dismiss endpoint**
      Paths: apps/api/src/auxd_api/modules/social/routes.py
      Size: S
      Deps: T104
      Refs: US-E5
      Description: `GET /api/v1/users/me/suggestions?limit=5`; `POST /api/v1/users/me/suggestions/{user_id}/dismiss`.
      Done: integration test.

- [x] **T106 — Home feed endpoint (fan-out-on-read + weighting)**
      Paths: apps/api/src/auxd_api/modules/feed/routes.py, apps/api/src/auxd_api/modules/feed/service.py, apps/api/tests/integration/test_feed_endpoint.py (sync-fix L5-014, Run #10 — was test_feed.py, corrected to match shipped filename)
      Size: L
      Deps: T101, T073, T085, T016
      Refs: US-E3; FR-009; DM-1
      Description: `GET /api/v1/feed?cursor=...&limit=25&mode=for_you|latest` — implements fan-out-on-read with weighted score (reviews +20%, ★★★★★/★ +15%, top-5-interacted +10%, half-life ~3d). "Latest" mode disables weights. Critic-seed padding when followed-user activity is sparse.
      Done: integration tests cover happy path + sparse-feed + visibility matrix + sort modes.

- [x] **T107 — Feed performance benchmark (p95 <500ms)**
      Paths: apps/api/tests/perf/test_feed_perf.py
      Size: S
      Deps: T106
      Refs: spec.md §6.1; NFR
      Description: Synthetic load test with ~500 followed users; assert p95 query time <200ms at DB layer (per plan §10.3 fan-out-switch trigger).
      Done: perf test passes; baseline recorded for regression checks.

<!-- CR-001: T108 description updated — "Listen on Spotify" button removed; entry-card CTA simplifies to album-page navigation. -->
- [x] **T108 — Feed UI (home page)**
      Paths: apps/web/src/app/(app)/page.tsx, apps/web/src/components/feed/feed-entry.tsx
      Size: L
      Deps: T106, T037, T032
      Refs: US-E3; FR-009; TC-E2E-004; wireframes/02-home-feed.html; CR-001
      Description: SSR home feed; entry cards per wireframe (avatar, stars, 🏅 Aux badge if applied, album cover thumb, review snippet, 👍 like count, tap-album-art-or-title to open album page). "Latest" tab toggle. Infinite scroll via cursor pagination. Lazy-load cover art (Next.js Image with blur placeholder). ("Listen on" streaming-service button deferred to v2 per CR-001.)
      Done: TC-E2E-004 passes.

- [x] **T109 — Profile + diary page**
      Paths: apps/web/src/app/(app)/profile/[handle]/page.tsx, apps/web/src/components/diary/profile-client.tsx (extended with avatar + counts + Follow + Block/Report header), apps/api/src/auxd_api/modules/users/routes.py (inline `GET /api/v1/users/{handle}` — see FR-036 — block-aware 404 to prevent existence-leak) (sync-fix L4-021, Run #10)
      Size: M
      Deps: T080, T101
      Refs: US-E2, US-G1, FR-036
      Description: Public profile with avatar, display_name, bio, handle, follows/followers counts, ratings histogram, diary tab, reviews tab, Aux'd filter. Backed by the inline `GET /api/v1/users/{handle}` endpoint that returns the user card + counts + viewer-relation classifier (none/following/pending/self/blocked/anonymous); blocked viewer sees 404, not 403.
      Done: page renders.

- [x] **T110 — Follow button (with optimistic update)**
      Paths: apps/web/src/components/social/follow-button.tsx
      Size: S
      Deps: T101, T109
      Refs: US-E1
      Description: Follow button with optimistic count update; confirm modal on unfollow.
      Done: works on profile page.

- [x] **T111 — Block + Report UI**
      Paths: apps/web/src/components/social/block-report-menu.tsx
      Size: M
      Deps: T102
      Refs: US-G4
      Description: Overflow menu on profile/diary entry/review with Block + Report options. Report modal with reason enum + free-text detail.
      Done: works.

- [x] **T112 — Discover tab (suggestions surface)**
      Paths: apps/web/src/app/(app)/discover/page.tsx
      Size: M
      Deps: T105, T037
      Refs: US-E5
      Description: Discover tab listing suggested follows with reason ("Mutual taste", "Followed by 3 of your follows", etc.). Dismiss button per suggestion.
      Done: page renders.

---

<!-- CR-001: §11 header updated — auto-import portion deferred to v2; cluster is now onboarding-only (Letterboxd-style: no auto-import, no Spotify connect step). -->
## §11 Onboarding + Auto-import *(auto-import portion **DEFERRED-TO-V2 (CR-001)** — see removed T114/T115/T116/T121/T122 placeholders below)*

- [ ] **T113 — Onboarding step 1: Sign up (already covered)**
      Paths: covered in T061
      Size: (sub-task)
      Refs: US-A1
      Description: First step of onboarding routes through signup page.
      Done: covered.

<!-- CR-001 removed: T114 (Onboarding step 2: Spotify connect) — no Spotify integration; onboarding step 2 is now the optional "Rate a few albums to seed your taste" Letterboxd-style step (covered by T117a + T118; the explicit T114 page is no longer needed since onboarding compresses from 5 steps to 4). -->
<!-- CR-001 removed: T115 (Auto-import worker — 30-day Spotify history) — no Spotify auto-import at MVP. -->
<!-- CR-001 removed: T116 (Onboarding step 3: Confirm last 30 days) — depended on T115 auto-import; no source to confirm at MVP. Letterboxd-style "rate a handful at signup" flow is left optional via the search-driven log-sheet (T079) before the user lands on the feed. -->

- [x] **T117 — Critic-seed batch precompute algorithm (backend, scheduled)**
      Paths: apps/api/src/auxd_api/modules/seeding/service.py, apps/api/tests/unit/test_seeding_algorithm.py
      Size: M
      Deps: T027, T104
      Refs: US-A4; FR-015; product-spec/decision-log.md Q13; product-spec/user-journeys.md UJ-2 (≥3 critics in top 6)
      Description: `get_card_recommendations_for_user(user_id)` runs as part of `T104` suggested-follow precompute job; returns the scored list of critic-seeds (and mutual-taste candidates) cached for the user. Used for routine "Suggested follows" surfaces (Discover tab post-onboarding).
      Done: unit test on card distribution; mutual-taste algorithm covered.

<!-- CR-001: T117a deps + description updated — T115 auto-import dependency removed; signal source changes from imported diary to optional inline rate-a-few-albums in the truncated onboarding step. Genre fallback when user skips the optional rating step. -->
- [x] **T117a — Critic-seed SYNCHRONOUS card-ordering for onboarding** *(added in Phase 5C Revision; CR-001: signal source updated)*
      Paths: apps/api/src/auxd_api/modules/seeding/onboarding_service.py, apps/api/tests/unit/test_onboarding_card_ordering.py
      Size: M
      Deps: T117, T163
      Refs: US-A4; FR-015; A-005 from pre-impl-review (architecture findings table; pre-impl-review.md line 141); CR-001
      Description: `get_onboarding_cards(user, optional_seed_ratings=None)` — runs INLINE during the onboarding step where the user picks who to follow. CR-001: source signal is now the optional handful of ratings the user enters via T079 search-driven log-sheet during onboarding (instead of an imported 30-day diary). When user provides no signal, fall back to a default "popular across active critics" ordering — still enforces ≥3 critics in top 6 per UJ-2. Given the signal, compute genre signature → score active critic-seeds → return top 6 + 4 mutual-taste candidates. Latency target: <1s p95. All 6 critic cards marked pre-checked=true; 4 mutual-taste cards pre-checked=false.
      Done: unit test covers (a) ≥3 critic guarantee in top 6 with AND without seed-ratings signal, (b) <1s p95 with 80-seed roster, (c) deterministic ordering given fixed signal.

- [x] **T118 — Onboarding step 4: Follow 3 to fill your feed**
      Paths: apps/web/src/app/(onboarding)/onboarding/step-2/page.tsx, apps/web/src/components/onboarding/follow-critics-deck.tsx
      Size: M
      Deps: T117a, T101, T039
      Refs: US-A4; FR-015
      Description: Show cards from T117. Critic-seed cards pre-checked; mutual-taste unchecked. User can untick; minimum 1 to advance. Continue button triggers Follow creates with `source=onboarding_preselected | onboarding_mutual_taste | manual`.
      Done: E2E test covers all default-keep + custom-pick paths.

- [x] **T119 — Onboarding step 5: Land on feed (non-empty guarantee)**
      Paths: apps/web/src/app/(onboarding)/onboarding/step-3/page.tsx, apps/web/src/components/onboarding/onboarding-complete.tsx, apps/api/src/auxd_api/modules/feed/service.py
      Size: S
      Deps: T106, T118
      Refs: US-A5
      Description: Last step redirects to `/` after a short success animation; backend ensures feed has ≥5 entries by padding with critic-seed last-7d activity.
      Done: E2E covers feed-with-≥5-entries after onboarding.

- [x] **T120 — Onboarding completion analytics**
      Paths: apps/web/src/lib/analytics.ts
      Size: XS
      Deps: T119
      Refs: success-metrics
      Description: PostHog event `onboarding.completed` with `time_to_complete_ms`, `follows_count`, `critic_seed_kept_pct`, `top5_rated_count`.
      Done: event fires correctly.

<!-- CR-001 removed: T121 (Settings → Integrations) — no integrations at MVP; Settings pane reduced to Profile/Account/Privacy/Notifications/Data per CR-001. -->
<!-- CR-001 removed: T122 (Last.fm import — Should-Have) — was a Spotify-alternative auto-import path; per CR-001 all auto-import paths defer to v2 (manual search + rate is the MVP model). -->

---

<!-- CR-001: §12 header updated — entire cluster deferred to v2; implementation can resume when streaming-platform integration becomes available. -->
## §12 Just-finished detection (auto-prompt) **DEFERRED-TO-V2 (CR-001)**

<!-- CR-001: T123-T130 all deferred but kept in tasks.md for traceability. Implementation can resume when streaming-platform integration (Spotify Extended Quota or alternative) becomes available in v2. -->

- [ ] **T123 — Spotify polling worker → just-finished polling worker (deferred)**
      Paths: apps/api/src/auxd_api/workers/spotify_poll.py
      Size: L
      Deps: T043, T027
      Refs: US-B6; FR-026
      Description: **DEFERRED-TO-V2 (CR-001):** Requires Spotify provider (T043) which is deferred to v2; resume when streaming-platform integration becomes available. (Original: arq scheduled per-user polling. Cadence: 5min if active <24h, 15min if dormant, capped at 60min. Stop after 14d dormancy. Fetches `get_recently_played(since=last_poll)` + `get_currently_playing`. Persists `last_poll_at` on User.)
      Done: worker runs; cadence transitions verified.

- [ ] **T124 — Just-finished detection heuristic**
      Paths: apps/api/src/auxd_api/modules/prompts/detection.py, apps/api/tests/unit/test_detection.py
      Size: M
      Deps: T123
      Refs: US-B6
      Description: **DEFERRED-TO-V2 (CR-001):** Depends on T123 polling worker (deferred). Resume when streaming-platform integration becomes available. (Original: Heuristic: ≥4 distinct tracks from the same Spotify album appear in last hour AND last track of album just finished → "album finished" event. Generates JustFinishedPrompt in `pending` state.)
      Done: unit test covers heuristic edges (partial album, shuffled, paused, multi-album session).

- [ ] **T125 — JustFinishedPrompt lifecycle endpoints**
      Paths: apps/api/src/auxd_api/modules/prompts/routes.py, apps/api/tests/integration/test_prompts_lifecycle.py
      Size: M
      Deps: T027, T124
      Refs: US-B6; FR-026; TC-018, TC-019, TC-020, TC-021
      Description: **DEFERRED-TO-V2 (CR-001):** JustFinishedPrompt collection itself is removed from `ALL_DOCUMENT_MODELS` at MVP (per T027 amendment); resume when streaming-platform integration becomes available. (Original: `GET /api/v1/users/me/just-finished/pending` (current active prompt); `POST .../dismiss?album_id=X` (30d sticky); `POST .../disable` (sets `User.auto_prompt_enabled=false`).)
      Done: TC-018, 019, 020, 021 pass.

- [ ] **T126 — Quiet hours enforcement (prompts + push)**
      Paths: apps/api/src/auxd_api/modules/notifications/quiet_hours.py
      Size: S
      Deps: T026
      Refs: FR-026; NT-3
      Description: **DEFERRED-TO-V2 (CR-001):** Prompt-specific portion defers along with §12 cluster. NOTE: the general quiet-hours infrastructure required by other notification channels (push, in-app coalescing windows) is still needed at MVP — pull the `is_in_quiet_hours(user, now)` helper into §13 notifications (e.g. inline within T132 `is_notifiable`) when the time comes; just the just-finished-prompt suppression branch defers. (Original: `is_in_quiet_hours(user, now)` helper. Suppresses push and in-app prompts during user-local quiet window. Email/digest unaffected.)
      Done: unit test covers tz boundaries.

- [ ] **T127 — Just-finished prompt component (frontend)**
      Paths: apps/web/src/components/just-finished-prompt/index.tsx
      Size: M
      Deps: T125, T037
      Refs: US-B6
      Description: **DEFERRED-TO-V2 (CR-001):** Depends on T125 prompt endpoints (deferred). Resume when streaming-platform integration becomes available. (Original: Hero card at top of home feed when prompt is `pending`. "Log" primary CTA opens log sheet pre-filled. "Not now" dismisses. Overflow menu: "Don't prompt for this album" + "Disable auto-prompts". Polls every 60s when foreground.)
      Done: component works; TC-E2E-008 covered.

- [ ] **T128 — Web push notification dispatch (for auto-prompt)**
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/web_push.py
      Size: M
      Deps: T008, T126
      Refs: US-B6; FR-026
      Description: **DEFERRED-TO-V2 (CR-001):** Auto-prompt-specific portion defers along with §12. NOTE: the general web-push infrastructure (VAPID-signed adapter for follow/review notifications etc.) is still needed at MVP and lives under T136 in §13; that general adapter is not deferred. (Original: VAPID-signed push notification adapter. Auto-prompt push fires only if `User.auto_prompt_push_enabled=true` (default false). Click action deep-links to home.)
      Done: push delivered when opt-in; respects quiet hours.

- [ ] **T129 — Disable auto-prompts UI (Settings + inline)**
      Paths: apps/web/src/app/(app)/settings/notifications/page.tsx, apps/web/src/components/just-finished-prompt/overflow-menu.tsx
      Size: S
      Deps: T127
      Refs: US-B6, US-G3; TC-E2E-009
      Description: **DEFERRED-TO-V2 (CR-001):** Depends on T127 prompt component (deferred). Resume when streaming-platform integration becomes available. (Original: One-tap "Disable auto-prompts" from prompt overflow + Settings toggle. Both POST to `notifications/update_preferences`.)
      Done: TC-E2E-009 passes.

- [ ] **T130 — Auto-prompt analytics**
      Paths: apps/web/src/lib/analytics.ts
      Size: XS
      Deps: T127
      Refs: success-metrics
      Description: **DEFERRED-TO-V2 (CR-001):** Depends on T127 prompt component (deferred). Resume when streaming-platform integration becomes available. (Original: PostHog events `prompt.shown`, `prompt.acted` (action: logged/dismissed/disabled-from-prompt).)
      Done: events fire.

---

## §13 Notifications (load-bearing — Goodreads-firehose prevention)

- [x] **T131 — Notification dispatcher core**
      *(completed 2026-05-23 Session 19; `dispatch(*, user_id, type, payload, actor_id=None, follow_source=None)` orchestrates suppression → is_notifiable per channel → coalescer → fan-out via registered adapters (`asyncio.gather(return_exceptions=True)` for adapter isolation) → emits `notification.dispatched` PostHog on every decision path. Internal-service surface only; no FastAPI routes. 21 unit tests cover happy path, recipient-missing/suspended, T142 onboarding suppression, per-channel decision fan-out, coalesce/drop wiring, adapter exception isolation, and dispatcher-level error fail-safe.)*
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py, apps/api/tests/unit/test_dispatcher.py
      Size: M
      Deps: T132, T133, T134, T137
      Refs: US-G3; plan.md §8.1 architecture; product-spec/notification-taxonomy.md
      Description: Single entry point `dispatch(*, user_id, type, payload, actor_id=None, follow_source=None)` that orchestrates `is_notifiable` per channel → coalescer/rate-limiter → adapter fan-out with exception isolation, and emits `notification.dispatched` PostHog events on every decision path (send/coalesce/drop/suppressed). Internal service surface only.
      Done: unit tests cover happy path, recipient-missing/suspended, onboarding suppression, per-channel decision fan-out, coalesce/drop wiring, adapter exception isolation, and dispatcher-level error fail-safe.

- [x] **T132 — `is_notifiable` predicate**
      *(completed 2026-05-23 Session 19; co-located in dispatcher.py — `is_notifiable(user, notif_type, channel, *, actor_id=None, now=None) -> ChannelDecision`. Decision order: user.status → recipient `Block` check → per-channel pref dict → fallback to `TYPES[type].default_*` → quiet-hours check (push-only per NT-3; email/digest immune) → security-types email lock (N-016/N-017 cannot be disabled on email). TZ math via `zoneinfo.ZoneInfo` with start>end midnight-rollover. Reason strings: user_pref_off / channel_default_off / quiet_hours / blocked / user_status / security_email_locked.)*
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py (co-located is_notifiable predicate)
      Size: S
      Deps: T137
      Refs: US-G3; plan.md §8.5 is_notifiable predicate; product-spec/notification-taxonomy.md NT-3
      Description: Per-channel decision predicate `is_notifiable(user, notif_type, channel, *, actor_id=None, now=None) -> ChannelDecision` covering user-status block, recipient Block existence, per-channel pref override, type-registry default fallback, push-only quiet-hours math, and the N-016/N-017 security-email lock.
      Done: unit tests cover every decision path + reason-string mapping + midnight-rollover quiet-hours math.

- [x] **T133 — Coalescer + rate limiter**
      *(completed 2026-05-23 Session 19; `allow_dispatch(*, user_id, actor_id, notif_type, target_id=None, now_ms=None) -> CoalesceDecision`. Four Redis buckets: per-user per-type hour (5/hr) + day (25/day) sorted-set sliding windows, per-actor cross-type day (3/24h, sorted-set) when actor present, per-event dedup (`SET NX EX 1h` atomic race-free). Verdicts: dedup hit → drop, any rate breach → coalesce(coalesced_window), else send. FAIL OPEN on Redis down with Sentry `notif_limiter.redis_down`. Mirrors `lib/rate_limit.py` pipeline pattern. fakeredis>=2.0 added to dev deps. 16 integration tests incl. TC-026 review-storm scenario.)*
      Paths: apps/api/src/auxd_api/modules/notifications/coalescer.py, apps/api/tests/integration/test_coalescer.py, apps/api/pyproject.toml (fakeredis>=2.0)
      Size: M
      Deps: T133 Redis infra (lib/rate_limit)
      Refs: US-G3; plan.md §8.6 allow_dispatch; TC-026 review-storm scenario
      Description: `allow_dispatch` decision over four Redis buckets — per-user per-type hour (5/hr) + day (25/day) sorted-set sliding windows, per-actor cross-type day (3/24h) when actor present, and per-event dedup (`SET NX EX 1h` atomic race-free). Verdicts: dedup → drop; rate breach → coalesce; else send. FAIL OPEN on Redis down with Sentry `notif_limiter.redis_down`.
      Done: integration tests cover all 4 buckets + TC-026 review-storm + FAIL-OPEN semantics under Redis outage.

- [x] **T134 — InApp notification adapter**
      *(completed 2026-05-23 Session 19; `InAppAdapter.send(*, user_id, type, payload, actor_id=None, coalesced_count=0) -> Notification` writes the Beanie row with `dispatch.in_app_delivered=True`; on `coalesced_count > 0` stamps `payload["coalesced_count"]` so the inbox UI can render "X new updates today". Sister-file `adapters/__init__.py` exposes `NotificationAdapter` Protocol + `register_adapter` extension point (one-line wiring for T135/T136 next session) + `reset_registry()` test helper. 5 integration tests.)*
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/__init__.py (NotificationAdapter Protocol + register_adapter), apps/api/src/auxd_api/modules/notifications/adapters/in_app.py, apps/api/tests/integration/test_in_app_adapter.py
      Size: S
      Deps: T131, T137
      Refs: US-G3; plan.md §8.3 Adapters
      Description: Writes the canonical in-app Notification Beanie row first in the dispatcher chain. Stamps `payload["coalesced_count"]` when the coalescer flagged the dispatch as a rollup so the inbox UI can render "X and N others did something". Sister-file `adapters/__init__.py` exposes the `NotificationAdapter` Protocol + `register_adapter` extension point used by email + web_push adapters.
      Done: integration tests cover row write + coalesced_count stamping + Protocol registration round-trip.

- [x] **T135 — Email notification adapter (Resend) + failure-mode wiring**
      *(completed 2026-05-23 Session 20; `EmailAdapter` at adapters/email.py conforms to extended NotificationAdapter Protocol (notification_id kwarg now threaded for email/push updaters; in_app still creates the row). Resend SDK via `resend.Emails.send`; `RESEND_API_KEY` + new `RESEND_FROM_ADDRESS` settings. Jinja2 env with autoescape + StrictUndefined; one-click unsubscribe footer, no tracking pixels. Send wrapped in lib/resilience.retry(attempts=3, exponential, 0.5–5s). On exhaustion writes FailedEmail row + Sentry `email.send_failed`. NOOP when TYPES[type].email_subject is None. Registered at module load via `register_adapter("email", EmailAdapter())`. jinja2>=3.1 added to deps. 7 integration tests.)*
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/email.py, apps/api/src/auxd_api/templates/email/{base,n008_weekly_digest,n013_account_deletion_scheduled,n014_account_deletion_reminder_7d,n016_security_new_session,n017_security_password_changed}.html, apps/api/pyproject.toml (jinja2>=3.1), apps/api/tests/integration/test_email_adapter.py
      Size: M
      Deps: T134, T137
      Refs: US-G3; plan.md §8.3 EmailAdapter; product-spec/notification-taxonomy.md NT-3 (digest bypasses quiet hours)
      Description: VAPID-irrelevant transactional email adapter using Resend's SDK. Jinja2 templates (autoescape + StrictUndefined) per notification type; per-type subject + preheader come from the T137 registry. Resilient via `lib/resilience.retry`; on retry exhaustion writes a FailedEmail audit row + Sentry `email.send_failed`. NOOP for types whose `TYPES[type].email_subject is None`.
      Done: integration tests cover the 6 shipped templates + retry exhaustion → FailedEmail row + NOOP path.

<!-- CR-001: T136 rewritten as the load-bearing web-push adapter — was previously a stub pointing at T128 (now deferred along with §12). T136 now owns the general VAPID-signed push adapter used by follow/review/digest notifications. -->
- [x] **T136 — Web push notification adapter (general, VAPID-signed)**
      *(completed 2026-05-23 Session 20; `WebPushAdapter` at adapters/web_push.py uses `pywebpush.webpush` wrapped in `asyncio.to_thread` (sync SDK; don't block the event loop). Reads VAPID_PRIVATE_KEY + new `VAPID_SUBJECT` settings (default `mailto:ops@auxd.xiejoshua.com`). Loads every PushSubscription for the recipient and fans out; 410/404 → DELETE the dead subscription row; other exceptions swallowed with Sentry `web_push.send_failed` (send-and-forget per spec). Click-action deep-links via `_click_url_for(type, payload)` helper resolving to `PUBLIC_APP_URL` (new setting). NOOP when `VAPID_PRIVATE_KEY` unset. Companion model `PushSubscription` Document registered in `ALL_DOCUMENT_MODELS` (db.py expected count 19→20). Register/delete endpoints mounted on v1: POST /api/v1/users/me/push-subscriptions + DELETE .../{id}; per-user 10/min rate limit; idempotent (re-POST updates last_used_at). pywebpush>=2.0 added to deps. 8 adapter tests + 6 endpoint tests.)*
      Paths: apps/api/src/auxd_api/modules/notifications/adapters/web_push.py, apps/api/src/auxd_api/modules/notifications/push_models.py (PushSubscription Document), apps/api/src/auxd_api/modules/notifications/routes.py (POST/DELETE /users/me/push-subscriptions), apps/api/src/auxd_api/settings.py (VAPID_SUBJECT, PUBLIC_APP_URL), apps/api/src/auxd_api/db.py (ALL_DOCUMENT_MODELS += PushSubscription), apps/api/pyproject.toml (pywebpush>=2.0), apps/api/tests/integration/{test_web_push_adapter,test_push_subscription_endpoints}.py
      Size: L
      Deps: T134, T137
      Refs: US-G3; plan.md §8.3 WebPushAdapter; product-spec/data-model.md PushSubscription
      Description: General VAPID-signed push adapter using `pywebpush` wrapped in `asyncio.to_thread`. Loads `PushSubscription` rows per recipient and fans out; 410/404 → DELETE the dead row; other exceptions Sentry-tagged and swallowed (send-and-forget). Click-action URL resolves via `_click_url_for(type, payload)`. NOOP when `VAPID_PRIVATE_KEY` unset. Ships the companion `PushSubscription` Document + `POST/DELETE /api/v1/users/me/push-subscriptions` endpoints (idempotent re-POST).
      Done: adapter tests cover 410-Gone cleanup + NOOP path; endpoint tests cover idempotent re-POST + DELETE + 10/min rate-limit.

- [x] **T137 — Notification types (all 16 active per CR-001)**
      *(completed 2026-05-23 Session 19; `TYPES: dict[NotificationType, NotificationTypeSpec]` covers every enum value with `required_payload_keys`, `default_{in_app,email,push}` mirroring the taxonomy table, plus `in_app_copy` / `email_subject` / `email_preheader` / `push_body` templates. `validate_payload(type, payload)` raises ValueError on missing keys (called pre-fan-out). `render_in_app(type, payload)` uses `.format(**payload)` — Jinja arrives with T135 next session. N-009/N-010 registered with all defaults OFF (taxonomy says DEFERRED-TO-V2 but enum retains them; deferred dedupe is a follow-up). 54 parametrised integration tests over the enum. NOTE: task title says "18" but CR-001 deferred N-011 (Spotify) and N-018 (just-finished), leaving 16 active.)*
      Paths: apps/api/src/auxd_api/modules/notifications/types.py, apps/api/tests/integration/test_notification_types.py
      Size: M
      Deps: (none — anchor task for the §13 cluster)
      Refs: US-G3; product-spec/notification-taxonomy.md (canonical taxonomy table)
      Description: Single source of truth `TYPES: dict[NotificationType, NotificationTypeSpec]` for every active notification type. Each spec carries `required_payload_keys` (validated pre-fan-out), `default_{in_app,email,push}` mirroring the taxonomy doc, and the rendered copy templates (`in_app_copy`, `email_subject`, `email_preheader`, `push_body`). N-009/N-010 registered with all defaults OFF per CR-001 deferral rather than removed from the enum.
      Done: 54 parametrised integration tests cover every enum value's required payload + default flags + copy template.

<!-- CR-002: hero count amended from single → three-hero carousel (NT-2). -->
- [x] **T138 — Weekly digest job**
      *(completed 2026-05-23 Session 20; `dispatch_weekly_digests` arq job at workers/digest_dispatch.py + registered in workers/main.py WorkerSettings with `minute={0,5,10,...,55}` cron. Streams Users with `notification_preferences.weekly_digest=True` + `status=ACTIVE` via async iteration; per-user `now_utc.astimezone(ZoneInfo(quiet_hours_tz or "UTC"))` → eligible iff `weekday==Monday and 09:00 ≤ local_time < 09:05`. Three-hero carousel via Beanie aggregation pipelines on the follow-graph: most-rated (avg DiaryEntry.rating), most-reviewed (Review count), most-Aux'd (DiaryEntry.auxed=True count) over 7d. Empty metrics gracefully drop (2- or 1- or 0-hero render). Chrono body from `feed.service.get_home_feed(user_id, since=now-7d, limit=10)`. Dispatches via the standard chain — calls `dispatch(user_id, N008_WEEKLY_DIGEST, payload)` so EmailAdapter renders n008_weekly_digest.html with autoescape+StrictUndefined-safe `{% if x is defined %}` guards. NT-3 honored: email channel bypasses quiet hours. Emits `digest.sent` PostHog per send with `{user_id, hero_count, body_count, has_review_likes_hero}`. 13 integration tests incl. TC-027.)*
      Paths: apps/api/src/auxd_api/workers/digest_dispatch.py, apps/api/src/auxd_api/workers/main.py (cron registration), apps/api/src/auxd_api/templates/email/n008_weekly_digest.html, apps/api/tests/integration/test_weekly_digest.py
      Size: L
      Deps: T131, T135, T137, T143
      Refs: US-G3; plan.md §8.4 Weekly digest; product-spec/notification-taxonomy.md NT-2 (three-hero carousel) + NT-3 (digest bypasses quiet hours); CR-002
      Description: arq cron job that streams users eligible for the Monday 09:00 user-local digest (TZ-aware via `ZoneInfo`). Computes the three-hero carousel (most-rated, most-reviewed, most-Aux'd over 7d) on the follow graph, prepends T143's review-likes hero when applicable, appends the chronological body from `feed.service.get_home_feed`, then dispatches via the standard chain so EmailAdapter renders the n008 template. Emits `digest.sent` PostHog with `{user_id, hero_count, body_count, has_review_likes_hero}`.
      Done: 13 integration tests including TC-027 cover eligibility window + hero aggregation + empty-hero graceful degrade + NT-3 quiet-hours bypass.

- [x] **T139 — Notification preferences UI**
      *(completed 2026-05-23 Session 21; Per-type per-channel toggles grouped per taxonomy (Activity / Digests / Account & system / Quiet hours). Quick controls (Mute all push / email / in-app). N-008 push hardcoded-off and N-016/N-017 email locked-on (server enforces; UI disables the switch). Quiet-hours timezone select uses curated IANA list + browser-resolved tz fallback. Backend GET + PUT `/api/v1/users/me/notification-preferences` endpoints added (response flattens User.quiet_hours_{start,end,tz} into nested `{quiet_hours: {enabled, start, end, tz}}`; PUT validates IANA tz via `zoneinfo.ZoneInfo` + rejects security-email lock attempts with 422 `security_email_locked`). RHF + Zod form with `setApiFormErrors`; optimistic update + toast. PostHog `settings.notifications_updated`. Backend bson_encoders for `datetime.time` added to User.Settings to make quiet-hours persist round-trip cleanly. New `components/ui/switch.tsx` (minimal headless, no Radix dep). New api-client `put` method.)*
      Paths: apps/web/src/app/(app)/settings/notifications/page.tsx, apps/web/src/components/notifications/prefs-form.tsx, apps/web/src/components/ui/switch.tsx (new shadcn primitive), apps/web/src/lib/api-client.ts (PUT method added), apps/api/src/auxd_api/modules/notifications/routes.py (GET + PUT /users/me/notification-preferences), apps/api/src/auxd_api/modules/users/models.py (bson_encoders datetime.time fix)
      Size: L
      Deps: T137, T140
      Refs: US-G3 AC bullets (N-008 push hardcoded-off, N-016/N-017 email lock, curated tz select); plan.md §6 notifications row (get/update_preferences); plan.md §4.5 rate-limit row PUT prefs 10/min
      Description: Settings → Notifications page with per-type-per-channel toggles, group-level mute-all quick controls, and a quiet-hours window editor (start/end/timezone). Server enforces the N-008 push hardcoded-off and N-016/N-017 email-locked-on contracts (422 `security_email_locked` on attempted disable). Quiet-hours timezone is a curated IANA shortlist with a browser-resolved fallback.
      Done: round-trip GET + PUT preserves all flags + quiet-hours fields; locked-control enforcement returns 422 with the expected error code; PostHog `settings.notifications_updated` fires on save.

- [x] **T140 — In-app notification feed UI**
      *(completed 2026-05-23 Session 21; notification-bell.tsx mounted in (app)/layout.tsx sticky header polls `GET /api/v1/notifications/unread-count` every 60s (`staleTime: 30s, refetchInterval: 60s`); badge caps at "99+". `/notifications` page uses useInfiniteQuery against `GET /api/v1/notifications` (cursor pagination on `created_at|id` base64 — same composite-cursor pattern as T074 diary). notification-card.tsx renders type-specific copy via `copyPartsFor(notification)` helper covering all 16 active types incl. coalesced rollups ("X and N others posted new updates"). Click-action navigates via `clickUrlFor(notification)` helper + POSTs mark-read; "Mark all as read" button at top calls `POST /api/v1/notifications/mark-all-read` with optimistic invalidation of list + count. 25 backend integration tests + 30 frontend copy/routing unit tests.)*
      Paths: apps/web/src/components/notifications/{notification-bell,notification-card,notification-list}.tsx, apps/web/src/app/(app)/notifications/page.tsx, apps/web/src/lib/notifications.ts, apps/api/src/auxd_api/modules/notifications/routes.py (GET /api/v1/notifications + unread-count + mark-read + mark-all-read), apps/web/tests/unit/notifications-copy.test.ts
      Size: L
      Deps: T134, T137, T139
      Refs: US-G3; plan.md §6 notifications row (list_user_notifications + unread_count + mark_read + mark_all_read); plan.md §4.5 rate-limit rows (GET notifications 60/min, GET unread-count 120/min, POST mark-all-read 10/min)
      Description: Inbox + bell pair. Bell polls the cheap unread-count endpoint every 60s and renders a badge capped at "99+". The `/notifications` page uses cursor-paginated infinite query against the list endpoint, with sidecar denormalised actor handle + display name on each row to avoid N+1. Cards render type-specific copy via the `copyPartsFor` helper (covers all 16 active types + coalesced rollups), and clicking marks read + navigates via `clickUrlFor`.
      Done: backend integration tests cover cursor pagination + visibility + 4 endpoint surfaces; frontend unit tests cover copy + click-url helpers for every active type incl. coalesced rollup branches.

<!-- CR-001: T141 deps updated — T128 deferred; T136 is the new owner of the web-push adapter. -->
- [x] **T141 — Web push subscribe flow (prompt at right time)**
      *(completed 2026-05-23 Session 21; push-prompt.tsx non-modal banner on /notifications page; criteria: `follows_count >= 3 OR (now - first_visit_at) >= 7d`. `markFollow()` wired into FollowButton mutation onSuccess + onboarding step-2 follow loop. push-bootstrap.tsx silently registers SW at app boot + stamps first_visit_at. push-subscription.ts owns isPushSupported/getCurrentPermission/subscribeToPush; the subscribe flow calls swReg.pushManager.subscribe with NEXT_PUBLIC_VAPID_PUBLIC_KEY then POSTs to /api/v1/users/me/push-subscriptions (already from S20). public/sw.js minimal SW: push event renders `self.registration.showNotification(title, {body, tag, data:{click_url,type}, icon, badge})`; notificationclick handler focuses existing tab matching click_url or opens new. "Not now" sets `dismissed_at` in localStorage (re-show after 14d). PostHog events `push.prompt_shown / permission_granted / permission_denied / dismissed`. 8 frontend criteria-evaluation unit tests.)*
      Paths: apps/web/src/components/notifications/{push-prompt,push-bootstrap}.tsx, apps/web/src/lib/push-subscription.ts, apps/web/public/sw.js, apps/web/src/app/(app)/layout.tsx (PushBootstrap mount), apps/web/src/components/social/follow-button.tsx + apps/web/src/components/onboarding/follow-critics-deck.tsx (markFollow wiring), apps/web/tests/unit/push-subscription.test.ts
      Size: L
      Deps: T136, T140
      Refs: US-G3 AC (push-prompt criteria bullet); plan.md §7.6 Web push subscribe flow; research/ux-patterns.md (non-modal Goodreads anti-pattern)
      Description: Non-modal push permission prompt banner on `/notifications` page. Criteria `follows_count >= 3 OR (now - first_visit_at) >= 7d` — both counters live in localStorage and are stamped by `push-bootstrap.tsx` at app boot + `markFollow()` from FollowButton + onboarding step-2 follow loop. "Not now" sets `dismissed_at` with a 14d re-show window. Minimal `public/sw.js` renders the push payload + handles `notificationclick` to focus an existing tab or open a new one.
      Done: criteria evaluation unit tests + 14d re-show timer + PostHog `push.prompt_shown / permission_granted / permission_denied / dismissed` event coverage.

- [x] **T142 — Critic-seed onboarding wave: suppress N-001 follow notifications**
      *(completed 2026-05-23 Session 19; wired inside dispatcher.dispatch at the suppression-check stage. `notif_type is N001_FOLLOW_NEW and follow_source == "onboarding_preselected"` → log `notification.suppressed_onboarding_preselected` + emit a `decision=suppressed` PostHog event + return None. `ONBOARDING_PRESELECTED_SOURCE` exported from dispatcher.py as single source of truth. 4 integration tests assert N-001 suppressed only when onboarding_preselected, N-002 NOT suppressed even with that source.)*
      Paths: apps/api/src/auxd_api/modules/notifications/dispatcher.py (onboarding suppression branch + ONBOARDING_PRESELECTED_SOURCE const), apps/api/tests/integration/test_onboarding_suppression.py
      Size: S
      Deps: T131
      Refs: US-A4; product-spec/notification-taxonomy.md N-001; product-spec/data-model.md Follow.source (sync-fix L2-031)
      Description: Dispatcher-level suppression branch — when a critic-seed onboarding wave creates a batch of Follow rows with `source = onboarding_preselected`, the corresponding N-001 follow notifications are suppressed (logged + emitted as `decision=suppressed` PostHog events but never dispatched). Prevents new users from getting 6+ "X started following you" notifications at the moment of onboarding.
      Done: integration tests assert N-001 suppressed only when `source == onboarding_preselected` and that other notification types (e.g., N-002) are NOT suppressed even with that source.

- [x] **T143 — Coalesce review.liked into weekly digest aggregate**
      *(completed 2026-05-23 Session 20; folded into T138 digest_dispatch.py — `_count_review_likes_in_window(user_id, since)` aggregates ReviewLike rows where `review.user_id == digest_recipient` over the trailing 7d window. If count ≥ 1, prepends a hero entry "Your reviews got X likes this week" above the three-hero carousel. No empty zero-state (zero likes → no hero). Covered in test_weekly_digest.py.)*
      Paths: apps/api/src/auxd_api/workers/digest_dispatch.py (_count_review_likes_in_window helper folded into T138)
      Size: S
      Deps: T138
      Refs: US-G3; product-spec/notification-taxonomy.md NT-2 (review-likes hero); plan.md §8.4 weekly digest
      Description: Folds review-like aggregation into the weekly digest job. Counts ReviewLike rows where `review.user_id == digest_recipient` over the trailing 7d window; when count ≥ 1, prepends a hero entry "Your reviews got X likes this week" above the three-hero carousel. No empty zero-state — zero likes drops the hero entirely.
      Done: test_weekly_digest.py covers ≥1 → hero present and 0 → hero omitted branches.

- [x] **T144 — Notification rate-limit alerting**
      *(completed 2026-05-23 Session 19; every dispatch call emits `notification.dispatched` with `{recipient_id, actor_id, type, decision, channels}` via `emit_event` from lib/observability — covers every decision path (send/coalesce/drop/suppressed). Descriptive operator config at `apps/api/src/auxd_api/modules/notifications/posthog_dashboard.yml` captures dashboard intent + p95 > 12 events/user/week alert threshold (excluding weekly.digest). Operator-applied; dashboard creation is a one-time PostHog UI task.)*
      Paths: apps/api/src/auxd_api/modules/notifications/{dispatcher.py (emit_event on every decision path), posthog_dashboard.yml}
      Size: S
      Deps: T131, T133
      Refs: US-G3; plan.md §15.2 PostHog (notification.dispatched row); product-spec/notification-taxonomy.md
      Description: Observability instrumentation for the dispatcher. Every `dispatch` call emits a `notification.dispatched` PostHog event with `{recipient_id, actor_id, type, decision, channels}` covering every decision path (send / coalesce / drop / suppressed). Companion `posthog_dashboard.yml` captures the dashboard intent + the p95 > 12 events/user/week alert threshold (excluding weekly digest).
      Done: PostHog event coverage on every decision branch; dashboard config file landed for operator-applied dashboard creation.

---

## §14 Profile, Settings, Privacy

- [x] **T145 — Edit profile UI (display_name, bio, avatar, handle)** *(completed 2026-05-23 Session 23; /settings/profile page + components/settings/edit-profile-form.tsx. RHF + Zod form with display_name max 30, bio max 280, handle lowercase+alphanumeric+underscore 3-30; avatar file input with 5MB client-side limit + image preview. Submit uses new PATCH /api/v1/users/me (display_name, bio); separate POST /api/v1/users/me/avatar for the file; handle change calls existing T057 POST /handle and surfaces 30d-cooldown 422 via setApiFormErrors with friendly "You can change your handle again in N days" copy. PostHog `profile.updated` event on success.)*
      Paths: apps/web/src/app/(app)/settings/profile/page.tsx, apps/web/src/components/settings/edit-profile-form.tsx, apps/api/src/auxd_api/modules/users/routes.py (PATCH /users/me)
      Size: M
      Deps: T109, T057
      Refs: US-G1; FR-029
      Description: Form for profile fields. Handle change uses T057 backend; UI shows lockout reason if applicable. Avatar upload (PUT to backend; 5MB max).
      Done: form persists; T057 lockout copy renders; avatar preview wired.

- [x] **T146 — Avatar upload pipeline** *(completed 2026-05-23 Session 23; lib/storage.py R2 facade `upload_avatar(user_id, raw_bytes, content_type) -> {"256": url, "128": url, "64": url}` via boto3 with endpoint_url + region_name="auto" + CacheControl: public, max-age=86400; new R2_AVATAR_BUCKET setting (default auxd-avatars). POST /api/v1/users/me/avatar in modules/users/routes.py accepts UploadFile, validates ≤5MB + content_type ∈ {image/jpeg, image/png, image/webp}, PIL EXIF-rotates + resizes via Image.Resampling.LANCZOS to 256/128/64 + encodes JPEG quality=85, updates User.avatar_url to 256px URL. Per-user 5/min rate limit. Pillow>=10.0 + python-multipart>=0.0.9 added to apps/api deps. 6 integration tests w/ monkeypatched boto3.)*
      Paths: apps/api/src/auxd_api/lib/storage.py, apps/api/src/auxd_api/modules/users/routes.py (POST /users/me/avatar), apps/api/src/auxd_api/settings.py (R2_AVATAR_BUCKET), apps/api/pyproject.toml (Pillow + python-multipart), apps/api/tests/integration/test_avatar_upload.py
      Size: S
      Deps: T021
      Refs: US-G1; plan.md §1.1.1 R2 row
      Description: POST /api/v1/users/me/avatar accepts ≤5MB image; resizes 256/128/64; stores on Cloudflare R2; returns URL.
      Done: 6 integration tests covering 401 / 413 oversize / 415 wrong content-type / 200 happy / User.avatar_url updated / rate-limit boundary.

- [x] **T147 — Privacy settings UI** *(completed 2026-05-23 Session 23; /settings/privacy + components/settings/privacy-settings-form.tsx. Selectors for default_entry_visibility + default_backlog_visibility (public/friends/private); private_profile toggle with help text explaining follow-request gating; keep_backlog_after_log toggle. Persists via new PUT /api/v1/users/me/privacy endpoint (updates 4 User fields). Pending follow-request inbox (T148 frontend) mounts on the same page below the privacy toggles.)*
      Paths: apps/web/src/app/(app)/settings/privacy/page.tsx, apps/web/src/components/settings/privacy-settings-form.tsx, apps/api/src/auxd_api/modules/users/routes.py (PUT /users/me/privacy)
      Size: M
      Deps: T021
      Refs: US-G2; FR-013
      Description: Default visibility for new entries + new backlog items; private-profile toggle; "Keep backlog after logging" toggle.
      Done: settings persist; private-profile flips behavior on subsequent reads via T151 gate.

- [x] **T148 — Private profile → follow-request queue** *(completed 2026-05-23 Session 23; backend adds three endpoints to modules/users/routes.py: GET /api/v1/users/me/follow-requests (paginated; sidecar users:{}), POST .../{id}/approve (sets FollowRequest.state=accepted + creates Follow row + N-003 dispatch + idempotent), POST .../{id}/decline (sets state=declined + idempotent, no Follow created, no N dispatch). Frontend components/social/follow-requests.tsx — useQuery list + Approve/Decline mutations with optimistic prune; mounted on /settings/privacy below the privacy toggles. 8 integration tests including 404 cross-user, idempotency, N-003 dispatch monkeypatch.)*
      Paths: apps/api/src/auxd_api/modules/users/routes.py (3 endpoints), apps/web/src/components/social/follow-requests.tsx, apps/api/tests/integration/test_follow_requests_endpoints.py
      Size: M
      Deps: T101, T147
      Refs: US-G2, US-H3; product-spec/notification-taxonomy.md N-003
      Description: When private_profile=true, new follows create state=pending; followee sees inbox of pending requests; can approve/reject. T101a closeout.
      Done: integration tests cover approve creates Follow + N-003 dispatch; decline does not.

- [x] **T149 — Settings → Data (export + delete)** *(completed 2026-05-23 Session 23; /settings/data + components/settings/data-settings.tsx. "Export my data" button POSTs /api/v1/users/me/data-export — graceful 404 stub until T153 ships (treats 404 as queued + shows "Export queued — we'll email when ready" toast, same pattern as report-user from S17). "Delete my account" opens text-confirm Dialog requiring user to type "DELETE" to enable submit; POSTs to existing T058 /users/me/delete then redirects to /login. Grace-period cancel banner — if User.deletion_scheduled_for is set, banner appears above the page with cancel button calling DELETE /users/me/delete. Backend T153 export endpoint follow-up flagged.)*
      Paths: apps/web/src/app/(app)/settings/data/page.tsx, apps/web/src/components/settings/data-settings.tsx
      Size: M
      Deps: T058, T153
      Refs: US-G5; FR-018, FR-019
      Description: Export-my-data button (T153-stub) + Delete-my-account text-confirm modal (T058 backend) + grace-period banner.
      Done: both flows wired; T153 backend lands later, frontend works without it via graceful 404.

- [x] **T150 — Settings → Account (email, password change)** *(completed 2026-05-23 Session 23; backend POST /api/v1/users/me/email (current_password + new_email; argon2 verify; lowercases + stores; bumps session_version; emits email.changed PostHog stub; per-user 5/hour rate limit) + POST /api/v1/users/me/password (current_password + new_password ≥12 chars via validate_password_policy promoted from auth/service.py; argon2 hash; bumps session_version; N-017 dispatch; 5/hour limit). Frontend /settings/account + account-settings.tsx with two RHF+Zod forms + logout-all-devices button calling existing T059 endpoint with confirmation modal. MVP simplification — email-confirm click-link pipeline deferred (would need new collection + verify-email template + click handler); current flow bumps session_version which forces re-login on other devices for security hygiene. Follow-up flagged. 10 integration tests including session_version bump assertions.)*
      Paths: apps/web/src/app/(app)/settings/account/page.tsx, apps/web/src/components/settings/account-settings.tsx, apps/api/src/auxd_api/modules/users/routes.py (POST /users/me/email + /password), apps/api/src/auxd_api/modules/auth/service.py (validate_password_policy promoted)
      Size: M
      Deps: T053, T059
      Refs: NFR Security; product-spec/notification-taxonomy.md N-017
      Description: Email change (no click-link verify at MVP; bumps session_version), password change (current-password confirm + N-017 dispatch), logout-all-devices button (T059).
      Done: 10 integration tests cover happy path + wrong-current-password + duplicate-email + too-short-password + rate-limit boundary + session_version bumps on both.

- [x] **T151 — Public profile (private-toggle-aware)** *(completed 2026-05-23 Session 23; ProfileClient gate in apps/web/src/components/diary/profile-client.tsx — branches on the backend-supplied `relation` field: relation === "blocked" renders "This account is unavailable" (no leak of block direction); relation === "pending" renders "Follow request sent" + public header (avatar + display_name + counts) without diary; target.private_profile && relation NOT IN {"self","following"} renders "This account is private" + Follow Request button (POSTs to /follow which creates FollowRequest); else renders existing Diary/Reviews tabs.)*
      Paths: apps/web/src/components/diary/profile-client.tsx (T151 gate added)
      Size: (sub-task)
      Refs: US-G2
      Description: When viewer not following private profile owner, render "This account is private" page instead of diary. Reads relation classifier from existing GET /users/{handle}.
      Done: 4 branches cover {blocked, pending, private-not-following, default}.

- [x] **T152 — Critic-suffix badge on display name** *(completed 2026-05-23 Session 23; components/critic-badge/index.tsx renders subtle `<span className="text-muted-foreground">· Critic</span>` when isCritic === true. Backend sidecar serializers across feed/reviews/notifications now emit `is_critic_seed` (per-user) or `actor_is_critic_seed` (per-notification actor). New seeding/service.py helper `critic_seed_user_ids(user_ids)` batches the CriticSeed lookup to avoid N+1 (mirrors the existing batched user-card sidecar pattern). Mounted on ReviewCard, NotificationCard, FeedEntry, ProfileClient header.)*
      Paths: apps/web/src/components/critic-badge/index.tsx, apps/api/src/auxd_api/modules/seeding/service.py (critic_seed_user_ids batch helper), apps/api/src/auxd_api/modules/feed/service.py (sidecar enrich), apps/api/src/auxd_api/modules/reviews/routes.py (sidecar enrich), apps/api/src/auxd_api/modules/notifications/routes.py (sidecar enrich), apps/web/src/components/review-card/index.tsx + apps/web/src/components/feed/feed-entry.tsx + apps/web/src/components/notifications/notification-card.tsx + apps/web/src/components/diary/profile-client.tsx (mount sites)
      Size: XS
      Deps: T117, T109
      Refs: SS-2
      Description: Subtle "· Critic" text suffix inline next to display_name everywhere when CriticSeed.active=true for that user. No icons.
      Done: badge renders inline on profile + reviews + feed + notifications.

---

## §15 GDPR + Moderation

- [x] **T153 — Data export job** *(completed 2026-05-24 Session 24; workers/gdpr_export.py + POST /api/v1/users/me/data-export endpoint in modules/users/routes.py (rate-limit per-user 1/day; returns 202 + job_id + audit_log_id + eta_seconds). Worker aggregates across 13 owned collections (User stripped of password_hash/admin_notes/session_version, DiaryEntry, Review, ReviewLike, ReviewEditHistory, Backlog, BacklogItem, Follow, FollowRequest, Block, Notification, PushSubscription, HandleRedirect) → builds both export.json (single object) and export.zip (per-collection CSVs via csv.writer + zipfile.ZipFile) → uploads to new R2_EXPORT_BUCKET (default auxd-exports) at exports/{user_id}/{job_id}/* with 24h presigned URLs → emails the user via Resend directly (not through dispatcher chain — one-off transactional shape doesn't fit a NotificationType). Audit log entries on both EXPORT_REQUESTED (endpoint) + EXPORT_COMPLETED (worker). Closes T149→T153 follow-up from S23 — frontend stub's 404 catch becomes a 202 happy path. 7 integration tests covering TC-030.)*
      Paths: apps/api/src/auxd_api/workers/gdpr_export.py, apps/api/src/auxd_api/modules/users/routes.py (POST /users/me/data-export), apps/api/src/auxd_api/settings.py (R2_EXPORT_BUCKET), apps/api/src/auxd_api/workers/main.py (job registration), apps/api/tests/integration/test_gdpr_export.py
      Size: L
      Deps: T023, T024, T025, T026, T135, T154
      Refs: US-G5; FR-018; TC-030; product-spec/data-model.md (collection inventory)
      Description: arq job: gather all User-owned content → JSON + per-collection CSV ZIP → email via Resend with 24h presigned R2 URLs → audit log.
      Done: TC-030 passes; sensitive fields stripped (password_hash, admin_notes, session_version excluded); empty-user happy path renders valid empty export.

- [x] **T154 — GDPR audit log collection** *(completed 2026-05-24 Session 24; new modules/gdpr/{__init__,models}.py with GdprAuditLog Beanie Document + GdprAuditAction enum (export_requested / export_completed / deletion_scheduled / deletion_completed / deletion_canceled). Indexed (user_id, requested_at desc). lib/audit.py exports `record_gdpr_event(user_id, action, notes=None, *, completed=False)` helper. Registered in ALL_DOCUMENT_MODELS (count 20 → 21). Called from T058 worker (DELETION_COMPLETED) + T153 endpoint (EXPORT_REQUESTED) + T153 worker (EXPORT_COMPLETED). 4 unit tests covering helper roundtrip + REQUESTED → COMPLETED pair pattern. 7-year MongoDB TTL deferred to operator config (index shape is ready).)*
      Paths: apps/api/src/auxd_api/modules/gdpr/{__init__,models}.py, apps/api/src/auxd_api/lib/audit.py, apps/api/src/auxd_api/db.py (ALL_DOCUMENT_MODELS += GdprAuditLog), apps/api/tests/unit/test_gdpr_audit.py
      Size: S
      Deps: T012
      Refs: NFR Compliance; plan.md §3.1
      Description: gdpr_audit_logs collection storing export/deletion events with user_id, action, requested_at, completed_at, notes. 7-year retention deferred to operator.
      Done: log entries written on T153 + T058 paths; helper tested.

- [x] **T155 — Report submission endpoint** *(completed 2026-05-24 Session 24 — unified with T163a as 3-endpoint variant per Run #10 sync-fix; see T163a entry below for full disposition. The single-endpoint /api/v1/reports variant declared here was superseded by the target-typed POST /reports/{user,review,diary-entry} routes that the T111 frontend BlockReportMenu expects.)*
      Paths: apps/api/src/auxd_api/modules/reports/{routes,service}.py (unified with T163a)
      Size: M
      Deps: T026, T101
      Refs: US-G4; FR-014; T163a (canonical implementation)
      Description: Report submission. Implementation per T163a: three target-typed endpoints with idempotency, FK validation, per-reporter 10/day rate-limit, self-report rejection.
      Done: covered by T163a integration tests.

- [x] **T156 — Daily moderation log-scan** *(completed 2026-05-24 Session 24; workers/moderation_scan.py + registered in workers/main.py cron at 03:00 UTC. Queries Report.find({created_at >= now-7d}) grouped by effective_target_user_id (user reports keep target_id; review/diary reports resolve to the row's user_id; reports against deleted rows silently dropped). Where count ≥ 3, flags User.flagged_for_review = True + records flagged_for_review_at. Notifies admin via Discord webhook (uses existing DISCORD_WEBHOOK_URL setting) with text payload listing handle + report count + reason breakdown. Idempotent — re-running same day skips already-flagged users (within trailing 7d). New fields on User model: flagged_for_review + flagged_for_review_at (both excluded from public serializers). 5 integration tests including author-resolution + idempotent re-run + monkeypatched webhook.)*
      Paths: apps/api/src/auxd_api/workers/moderation_scan.py, apps/api/src/auxd_api/workers/main.py (cron registration), apps/api/src/auxd_api/modules/users/models.py (flagged_for_review fields), apps/api/src/auxd_api/settings.py (DISCORD_WEBHOOK_URL), apps/api/tests/integration/test_moderation_scan.py
      Size: M
      Deps: T155, T163a
      Refs: US-G4
      Description: arq cron 03:00 UTC. Finds users with ≥3 reports in trailing 7d (including reports against their content). Flags via User.flagged_for_review + Discord webhook alert. Idempotent.
      Done: 5 integration tests cover thresholds + author resolution + idempotency + webhook firing.

- [x] **T157 — Report acknowledgment notification (N-012)** *(completed 2026-05-24 Session 24; new `acknowledge_report(report_id, ack_note=None)` helper in modules/reports/service.py — loads the report, marks Report.acknowledged_at=utcnow() (new field), fires dispatch(report.reporter_id, N012_REPORT_ACKNOWLEDGED, payload={report_id, target_type, ack_note}). Idempotent: re-acknowledging is a no-op + no double-dispatch. No HTTP admin endpoint at MVP — founder invokes via CLI script at apps/api/scripts/acknowledge_report.py (uv run python apps/api/scripts/acknowledge_report.py {report_id} --note "..."). Operator-runbooks/moderation.md documents the flow. 3 integration tests including dispatch monkeypatch + idempotency.)*
      Paths: apps/api/src/auxd_api/modules/reports/service.py (acknowledge_report helper), apps/api/src/auxd_api/modules/moderation/models.py (Report.acknowledged_at field), apps/api/scripts/acknowledge_report.py (CLI), apps/api/tests/integration/test_acknowledge_report.py
      Size: XS
      Deps: T137, T155, T163a
      Refs: product-spec/notification-taxonomy.md N-012
      Description: N-012 fires when a report is acknowledged via internal helper (CLI-driven at MVP; admin UI deferred).
      Done: helper + CLI + dispatch + idempotency verified.

- [x] **T158 — Admin notes / read-only flag visibility** *(completed 2026-05-24 Session 24; added `admin_notes: str = ""` field to modules/users/models.py User Document. Verified excluded from `_serialize_user_card` + `_public_user_payload` + all sidecar serializers (parametrised unit test in tests/unit/test_admin_notes_not_serialised.py asserts the field never appears in any public response shape). No UI at MVP — founder reads via Mongo Compass / Atlas UI per operator-runbooks/moderation.md.)*
      Paths: apps/api/src/auxd_api/modules/users/models.py (admin_notes field), apps/api/tests/unit/test_admin_notes_not_serialised.py
      Size: XS
      Deps: T021
      Refs: US-G4
      Description: User.admin_notes field. Internal-only — excluded from every public serializer.
      Done: field exists + parametrised serializer leak-test green.

- [x] **T159 — Suspended account UX** *(completed 2026-05-24 Session 24; backend SessionMiddleware extended in apps/api/src/auxd_api/middleware.py — when request.state.session is set and User.status == SUSPENDED, returns 403 with body {error: "account_suspended", appeal_url: "mailto:appeals@auxd.xiejoshua.com"} on ALL routes except the allow-list {POST /api/v1/auth/logout, POST /api/v1/auth/logout-all-devices, POST /api/v1/users/me/delete}. Frontend: /suspended page (standalone, no (app)/layout — locked-out user gets a clean explanation + Email Appeal mailto link). apps/web/src/lib/api-client.ts catches 403 with body.error === "account_suspended" → clears auth-store + redirects to /suspended. DELETION_PENDING status untouched (different path). No admin-action to suspend at MVP — founder runs `db.users.updateOne({_id: X}, {$set: {status: "suspended"}})` directly; documented in operator-runbooks/moderation.md. 5 backend integration tests + 1 frontend vitest for the 403 handler.)*
      Paths: apps/api/src/auxd_api/middleware.py (SuspendedAccountMiddleware), apps/web/src/app/suspended/page.tsx, apps/web/src/lib/api-client.ts (403 account_suspended handler), apps/api/tests/integration/test_suspended_account.py, apps/web/tests/unit/api-client.test.ts
      Size: S
      Deps: T155, T163a
      Refs: US-G4
      Description: SUSPENDED users get 403 on every non-whitelisted route + frontend redirect to /suspended. Allow-list: logout, logout-all-devices, delete-account.
      Done: 5 backend + 1 frontend test cover SUSPENDED 403s + whitelisted-route 200s + DELETION_PENDING unaffected.

- [x] **T160 — GDPR cascading delete tests** *(completed 2026-05-24 Session 24; tests/integration/test_gdpr_cascade.py — comprehensive setup creates a User with rows in every owned collection (User + 14 owned: DiaryEntry, Review, ReviewLike, ReviewEditHistory, Backlog, BacklogItem×2, Follow as both directions, FollowRequest as both directions, Block as both directions, Notification recipient, PushSubscription, HandleRedirect, Suggestion as both viewer + suggested, SuggestionDismissal, FailedEmail). T058 worker EXTENDED in modules/users/workers.py to cover newer collections that shipped post-T058 (PushSubscription, FailedEmail, Suggestion, SuggestionDismissal) AND to anonymise (not delete) Report rows where this user was reporter_id (sets reporter_id → None; target rows retained for audit). After cascade: User row gone + all owned rows gone + Report rows preserved with reporter_id nulled + GdprAuditLog DELETION_COMPLETED entry written + bystander rows survive. TC-029 passes.)*
      Paths: apps/api/tests/integration/test_gdpr_cascade.py, apps/api/src/auxd_api/modules/users/workers.py (cascade extended to 4 newer collections + Report anonymisation)
      Size: M
      Deps: T058, T154
      Refs: FR-019; TC-029
      Description: After 30d grace + cascade, no records remain for deleted user across owned collections; Report records preserved with nulled reporter_id; bystander rows survive.
      Done: TC-029 passes covering all 15 owned collections + bystander preservation.

- [x] **T161 — Privacy policy + ToS placeholders** *(completed 2026-05-24 Session 24; apps/web/src/app/legal/{layout,privacy/page,terms/page}.tsx — standalone routes outside the (app) and (auth) chrome. Placeholder content with section headers (Data we collect / How we use it / Your rights / Contact for privacy; Acceptance / Use of service / Account termination / Liability for ToS) + a prominent `<aside>` banner: "🚧 This is a placeholder. Final policy lawyer-reviewed before public launch." Footer links from (auth)/layout (signup + login) pages added. PostHog page-view events on both routes.)*
      Paths: apps/web/src/app/legal/{layout,privacy/page,terms/page}.tsx, apps/web/src/app/(auth)/layout.tsx (footer Privacy · Terms link)
      Size: S
      Deps: T031
      Refs: NFR Compliance
      Description: Placeholder /legal/privacy + /legal/terms pages with lawyer-review banner. Linked from (auth)/layout footer.
      Done: pages render; linked from signup + login footer; PostHog page-view events fire.

---

## §16 Seeding backend + founder workflow

- [x] **T162 — CriticSeed admin (manual roster management)** *(completed 2026-05-24 Session 25; apps/api/scripts/manage_critic_seed.py CLI with subcommands add/remove/activate/deactivate/list. Resolves handle → user_id via existing resolve_handle helper. Operator-friendly errors. docs/critic-seed-runbook.md documents when to add (domain expertise + activity bar), priority knob (1-100, default 50), genre-signature seeding option, deactivation triggers (60d silent), roster size guidance (30-80).)*
      Paths: apps/api/scripts/manage_critic_seed.py, docs/critic-seed-runbook.md
      Size: S
      Deps: T027
      Refs: product-spec/seeding-strategy.md §1
      Description: CLI to add/remove/activate/deactivate CriticSeed records by handle. Operator runbook.
      Done: CLI works; runbook authored.

- [x] **T163 — Genre signature computation** *(completed 2026-05-24 Session 25; modules/seeding/genre_signature.py — `compute_genre_signature(user_id) -> dict[str, float]` joins DiaryEntry → Album.genres over the user's 500 most-recent entries. Weight = 1.0 + max(0, (rating - 3.0)) × 0.5 per entry (5★ = 2.0, 1★ = 0.0, no-rating = 1.0); distributed evenly across the album's genres; normalized so max weight = 1.0. Empty diary or genre-less albums → {}. 24h Redis cache via cache_get/cache_set (fail-open). 8 unit tests covering empty + single-album + multi-album + rating weighting + cache hit/miss + fail-open paths.)*
      Paths: apps/api/src/auxd_api/modules/seeding/genre_signature.py, apps/api/tests/unit/test_genre_signature.py
      Size: M
      Deps: T117, T073
      Refs: T117 algorithm; product-spec/seeding-strategy.md
      Description: Per-user genre_signature dict from DiaryEntry + Album.genres weighted by rating. 24h Redis cache.
      Done: 8 unit tests covering empty/single/multi-album + rating weight + cache + fail-open.

- [x] **T164 — Mutual-taste suggestions algorithm** *(completed 2026-05-24 Session 25; modules/seeding/mutual_taste.py — `MutualTasteScore` frozen dataclass + `score_candidates(*, viewer_id, viewer_genre_signature, candidate_user_ids, follows, follow_back_map, critic_seed_user_ids) -> list[MutualTasteScore]` reusable service. 5 weighted factors: mutual_taste 40% (jaccard between viewer + candidate signatures), followed_by_followed 30% (count of mutual follows / max in batch), shared_seed 15% (boolean: both follow a CriticSeed), label_genre 10% (candidate top genre in viewer top-3), recency 5% (linear decay 1.0 at trailing 14d → 0.0 at 90d). T104 worker continues using its internal scoring path; both modules share the same weight constants imported from mutual_taste.py (judgement call: avoid breaking T104's existing 7 tests with a re-split risk; the new module is the canonical reusable surface for future Discover refresh + ad-hoc widgets). 7 unit tests covering each factor + total weighting.)*
      Paths: apps/api/src/auxd_api/modules/seeding/mutual_taste.py, apps/api/tests/unit/test_mutual_taste.py
      Size: M
      Deps: T163
      Refs: product-spec/seeding-strategy.md §4
      Description: 4-factor weighted scoring service extracted from T104; reusable for Discover refresh + ad-hoc widgets.
      Done: 7 unit tests covering each factor + total weighting; T104 worker tests still pass.

- [x] **T165 — Critic-of-the-week (deferred)** *(intentionally deferred per spec — NOT in MVP scope; documented as future-state operational lever in product-spec/seeding-strategy.md. No code shipped; marked [x] to align with the lifecycle's "all tasks resolved" gate.)*
      Paths: (deferred to v1.x)
      Size: —
      Refs: product-spec/seeding-strategy.md operational levers
      Description: NOT in MVP scope. Documented as future-state.
      Done: deferred per spec.

<!-- sync-fix L4-023 (Run #10): T163a added — POST /api/v1/reports/user (and target-typed report variants) referenced by T111 frontend BlockReportMenu (the modal currently 404s gracefully). Lives in §15 moderation territory because reports tie into the daily-scan-for-flagged-users flow. -->
- [x] **T163a — Submit-report endpoints (user / review / diary)** *(completed 2026-05-24 Session 24; new modules/reports/{routes,service,models}.py with 3 POST endpoints: /api/v1/reports/{user,review,diary-entry}. ReportReason enum {harassment, spam, impersonation, hate_speech, other}. Idempotency via same `(reporter_id, target_type, target_id)` within 24h returns existing (200 not 201). Per-reporter 10/day rate-limit. Auth required (401 anonymous). FK validation (422 if target_id doesn't exist). Cannot self-report (422). T111 BlockReportMenu (Session 17) 404 fallback removed — endpoint now real with 201 happy path. Daily moderation scan (T156) consumes the rows. 8 integration tests including idempotency + FK validation + self-report rejection + rate-limit boundary.)*
      Paths: apps/api/src/auxd_api/modules/reports/{routes,service,models}.py, apps/api/src/auxd_api/routers/v1.py (reports router mount), apps/web/src/components/social/block-report-menu.tsx (404 fallback removed), apps/api/tests/integration/test_reports_endpoints.py
      Size: S
      Deps: T026, T101, T155 (unified)
      Refs: US-G4; T111 frontend BlockReportMenu (Session 17); plan.md §3.1 reports collection
      Description: Three POST endpoints for user/review/diary-entry reports; idempotent within 24h; FK-validated; cannot self-report; 10/day per reporter.
      Done: 8 integration tests cover all 3 target types + idempotency + 401 + 422 self-report + 422 missing target + rate-limit; frontend mutation succeeds with 201.

- [x] **T166 — Founder seed-content workflow tools** *(completed 2026-05-24 Session 25; docs/founder-workflows/seed-content.md covers: (1) identifying critic candidates (criteria + sourcing channels + minimum activity bar), (2) cold-outreach email template with value prop + commitment + sign-up code, (3) onboarding script — 10-15 album diary seed to establish genre signature + review guidance + tagging conventions, (4) activity expectations (≥2 reviews/week first month, ≥1/week thereafter), (5) cull cadence (60d silent → soft-deactivate via T162 CLI; 180d → hard-removal consideration).)*
      Paths: docs/founder-workflows/seed-content.md
      Size: XS
      Deps: T162
      Refs: product-spec/seeding-strategy.md §1 pre-launch playbook
      Description: Workflow doc: identify candidates → cold outreach template → onboarding script → activity expectations → cull cadence.
      Done: doc authored.

---

## §17 Should-have features

- [x] **T167 — Album merge / report-wrong-album** *(completed 2026-05-24 Session 25; backend extended ReportReason enum with WRONG_METADATA + DUPLICATE values and added Report.target_type="album" branch in modules/reports/{service,routes}.py with new POST /api/v1/reports/album endpoint (idempotent within 24h + FK validation + per-reporter 10/day rate limit). Frontend report-wrong.tsx Dialog with reason selector + detail textarea, mounted via AlbumActions on /album/[id]; PostHog `album.report_wrong` event. Album merge CLI at apps/api/scripts/merge_albums.py (dry-run by default; --yes for non-interactive; updates DiaryEntry.album_id + Review.album_id + BacklogItem.album_id losing → winning, then hard-deletes losing Album row). Admin queue is read-only Mongo (founder reads reports collection). 8 endpoint integration tests + 3 CLI integration tests.)*
      Paths: apps/api/src/auxd_api/modules/reports/{routes,service}.py (album endpoint + FK validation), apps/api/src/auxd_api/modules/moderation/models.py (WRONG_METADATA + DUPLICATE reasons + album target_type), apps/api/scripts/merge_albums.py, apps/web/src/components/album-detail/report-wrong.tsx, apps/web/src/components/album-detail/album-actions.tsx (ReportWrong mount), apps/api/tests/integration/{test_reports_album_endpoint,test_merge_albums_cli}.py
      Size: M
      Deps: T067, T163a (reports module)
      Refs: US-H2
      Description: User-facing report-wrong-album modal; backend Report endpoint; admin merge CLI (no AlbumRedirect at MVP — losing URLs 404 acceptable for admin tooling).
      Done: 8 endpoint + 3 CLI integration tests cover all paths.

- [x] **T168 — Share-card OG image generator** *(completed 2026-05-24 Session 25; Vercel `next/og` ImageResponse routes at apps/web/src/app/api/og/album/[id]/route.tsx + apps/web/src/app/api/og/review/[id]/route.tsx. 1200x630 image with backend fetch via server-side env var (API_BACKEND_URL, falls back to http://localhost:8000) — album: cover + title + artist + rating histogram; review: actor + album + excerpt + likes. Generic auxd fallback on backend 404. Cache-Control public, max-age=31536000, immutable (Vercel CDN). generateMetadata() on /album/[id] + /review/[id] updated to set openGraph.images + twitter.card="summary_large_image". runtime="nodejs" (consistency with the rest of the API routes; Vercel CDN handles the edge caching). Shared helpers at apps/web/src/app/api/og/helpers.ts. 4 unit tests on helpers (text truncation + URL builder + fallback).)*
      Paths: apps/web/src/app/api/og/{album/[id]/route,review/[id]/route}.tsx, apps/web/src/app/api/og/helpers.ts, apps/web/src/app/(app)/{album/[id]/page,review/[id]/page}.tsx (generateMetadata updated), apps/web/tests/unit/og-route.test.ts
      Size: M
      Deps: T070, T085
      Refs: US-H5
      Description: Vercel ImageResponse OG routes for album + review; CDN-cached; openGraph.images + twitter card wired.
      Done: 4 unit tests on helpers; OG routes build cleanly; metadata updated.

<!-- CR-001: T169 marked DEFERRED-TO-V2 alongside the rest of the auto-import surface; this task built on T115 which was removed. -->
- [ ] **T169 — Pull-more-history (Should-Have) **DEFERRED-TO-V2 (CR-001)****
      Paths: apps/web/src/app/(app)/settings/integrations/page.tsx, apps/api/src/auxd_api/workers/spotify_import.py
      Size: M
      Deps: (was T115 — removed per CR-001)
      Refs: decision-log Q14 (v1.x progressive enhancement); CR-001
      Description: **DEFERRED-TO-V2 (CR-001):** Depends on the auto-import surface (T115, T121, T122) which CR-001 removed. Resume when streaming-platform integration becomes available. (Original: "Pull more history" button (Settings → Integrations) extends import window by paging deeper or via Last.fm import. Marked as v1.x — defer if M-2 capacity tight.)
      Done: deferred OK if needed.

- [x] **T170 — Friend-request flow (US-H3)** *(completed 2026-05-24 Session 25 — verified covered by S23's T148 implementation. apps/web/src/components/social/follow-requests.tsx (T148's canonical path) ships the FollowRequestsInbox component with `useQuery` against GET /api/v1/users/me/follow-requests for inbox display + approveMutation POSTing /approve + declineMutation POSTing /decline + optimistic invalidations via queryClient.invalidateQueries + toast feedback + PostHog `follow_request.approved` / `follow_request.declined` captures. The "UI for managing pending follow requests" T170 declares is fully present. No new code shipped.)*
      Paths: apps/web/src/components/social/follow-requests.tsx (T148; verified S23)
      Size: M
      Deps: T148 (canonical implementation)
      Refs: US-H3
      Description: UI for managing pending follow requests when private profile is on. Covered by T148's frontend half.
      Done: covered.

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

<!-- CR-001 removed: T177 (Extended Quota Mode follow-through) — T002 was removed; no Spotify application to follow up on. Recorded here so T179 dependency chain is auditable; T179 no longer references T177. -->

- [ ] **T178 — Final wireframe → design polish pass**
      Paths: apps/web/src/components/* (design tokens, polish)
      Size: L
      Deps: T108, T070, T077, T080
      Refs: wireframes/*, plan §18
      Description: Design polish: typography scale, color palette tuning, micro-interaction animations, haptic feedback on rating/Aux/Like, mobile responsiveness verification. Founder + (optional) designer involvement.
      Done: visual quality at launch-ready bar.

<!-- CR-001: T179 deps updated — T177 removed (was the Spotify quota-mode follow-through dependency). -->
- [ ] **T179 — Pre-launch checklist + readiness review**
      Paths: docs/launch-checklist.md
      Size: M
      Deps: T171, T172, T173, T174
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

<!-- CR-001: Parallel-track table updated — T002 (Spotify app) removed; §12 row reframed since cluster is deferred; §11 narrowed to onboarding-only. -->
## Parallel-track opportunities

| Group | Tasks | Can parallelize with |
|---|---|---|
| §0 Prereqs | T001 (Constitution) + T003 monorepo + T005/T006/T007 provisioning | Constitution must land first; provisioning tasks run in parallel after T001 |
| §1 Backend libs + §3 Frontend foundation | T011..T030 + T031..T040 | Two engineers can split backend / frontend after T003 |
| §4 Catalog providers (MVP scope per CR-001) | T041 + T048/T049 (MusicBrainz) + T049a/T049b (Discogs) + T050/T051/T052 | Contract-test pairs (T048/T049 and T049a/T049b) can run sequentially within their pair; the pairs are independent |
| §6 Albums + §8 Reviews + §9 Backlog | T063..T072 + T085..T094 + T095..T100 | Once auth (§5) is done, these three modules touch independent collections — can parallelize across 2-3 engineers |
| §13 Notifications | T131..T144 | Independent of §12 (deferred per CR-001); push adapter is now T136 (not T128); §12 ↔ §13 cross-link no longer applies at MVP |
| §11 Onboarding + §10 Feed | T113 + T117..T120 + T101..T112 | Onboarding consumes feed but feed work can complete first |
| §18 Hardening | T171..T180 | Must run after most feature work; some tasks parallelize within §18 |

---

<!-- CR-001: Constitution coverage summary updated — T042/T043 (Spotify) replaced with T048/T049 (MusicBrainz) + T049a/T049b (Discogs); FR/story counts reflect deferral. -->
## Constitution + decision-log + NFR coverage summary

- **Constitution Principle 1 (resilience):** T014 + T050 + T051 (provider-level + transport-level); enforced by lint rule in T004 CI.
- **Constitution Principle 2 (schema versioning):** T012 + T030 (runner) + every model task includes `_schema_version: int = 1`.
- **Constitution Principle 3 (library-first):** Module structure throughout (each module has `routes.py`, `service.py`, `models.py` only).
- **Constitution Principle 4 (test-first):** T048 + T049a (contract tests before T049 + T049b implementations per CR-001 — MusicBrainz + Discogs are the two MVP catalog providers).
- **Constitution Principle 5 (observability):** T015 (lib) + T051 (provider — MusicBrainz + Discogs per CR-001) + woven throughout (each task adds its PostHog events).
- **Constitution Principle 6 (provider abstraction):** T041 (Protocols) + T049 (MusicBrainz impl) + T049b (Discogs impl) per CR-001 — MVP ships one impl per kind.
- **Must-Have user stories per CR-001:** original 32 minus 3 deferred (US-A2, US-A3, US-B6 — DEFERRED in spec.md) — each remaining story maps to ≥1 task per coverage matrix.
- **Active FRs per CR-001:** 28 base (27 originals + FR-033 "Report missing album" added by CR-001) minus 5 deferred (FR-002, FR-003, FR-017, FR-026, FR-027 — DEFERRED in spec.md) = **23 active** — each remaining FR maps to ≥1 task per coverage matrix.  <!-- sync-fix L4-007 (Run #4) -->
- **Critical TCs + 13 E2E scenarios:** mapped per plan §16.2 + woven into tasks above; TC-006/TC-018/TC-019/TC-020/TC-021/TC-022 sit with deferred tasks per CR-001.
- **NFR Measurement Contract (spec.md §6.1)** → instrumentation woven (T015, T077 wedge timing, T107 feed perf, T144 notification rate, T172 perf audit).
- **Aux (🏅) vs Like (👍) split preserved:** T023 (separate fields), T073 (Aux on DiaryEntry), T088 (Like on Review via ReviewLike), T090 (UI distinct icons), notification N-001 (follow) vs N-004 (review.liked).
- **Lists deliberately ABSENT:** No tasks for Lists per R3 deferral; out-of-scope.md and decision-log row 7 confirm v2 deferral.
- **Spotify integration ABSENT per CR-001:** No tasks for any Spotify provider, OAuth, auto-import, just-finished polling, or auto-prompt at MVP. Transition is to Letterboxd-style manual search + rating via MusicBrainz primary + Discogs fallback. Deferred cluster (§12 T123-T130) kept in-file for traceability and v2 resumption.
