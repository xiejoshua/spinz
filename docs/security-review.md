# Security Review — OWASP Top 10 (2021) (T173)

> Last reviewed: 2026-05-23 (Session 26).
> Reviewer: founder, against the consolidated codebase at commit pre-`S26 close-out`.
> Scope: full auxd backend (`apps/api/src/auxd_api/**`) + frontend (`apps/web/src/**`).
> Mode: internal manual review supplemented by ripgrep evidence
> gathering and a follow-the-data-flow analysis of every state-changing
> endpoint.

## Severity legend

- **CRITICAL** — exploitable in production; blocks launch.
- **HIGH** — exploitable in production with non-trivial setup; should
  be fixed before launch.
- **MEDIUM** — defence-in-depth gap; document mitigations, accept for
  MVP.
- **LOW** — observation / hygiene; track as post-MVP follow-up.
- **PASS** — no issue identified.

## Findings summary

| # | OWASP class | Status | Severity | Fix applied this session |
|---|---|---|---|---|
| A01 | Broken Access Control | PASS | — | n/a |
| A02 | Cryptographic Failures | PASS | — | n/a |
| A03 | Injection | PASS | — | n/a |
| A04 | Insecure Design | PASS | — | n/a |
| A05 | Security Misconfiguration | OBSERVATION | LOW | n/a |
| A06 | Vulnerable Components | OBSERVATION | LOW | n/a |
| A07 | Identification + Authentication Failures | **RISK FIXED** | **HIGH** | **YES — CSRF wiring** |
| A08 | Software + Data Integrity | PASS | — | n/a |
| A09 | Logging + Monitoring | PASS | — | n/a |
| A10 | Server-Side Request Forgery | PASS | — | n/a |

**Bottom line: 1 HIGH risk identified and fixed in this session
(A07 CSRF). 0 CRITICAL or HIGH open at end of session. 2 LOW
observations tracked as follow-ups.**

---

## A01 — Broken Access Control

**Status: PASS.**

Every write endpoint enforces both (a) authentication via
`SessionMiddleware` and (b) ownership where applicable.
Sampled endpoints:

| Endpoint | Auth | Ownership | Evidence |
|---|---|---|---|
| `POST /api/v1/diary` (wedge log) | required | n/a (user-scoped insert) | `apps/api/src/auxd_api/modules/diary/routes.py` |
| `PATCH /api/v1/diary/{id}` (T144 edit) | required | owner-only | `apps/api/src/auxd_api/modules/diary/routes.py` — 404 returned when `entry.user_id != session.user_id` |
| `DELETE /api/v1/reviews/{id}` | required | owner-only | `apps/api/src/auxd_api/modules/reviews/routes.py` |
| `POST /api/v1/social/follow/{handle}` | required | self-action only | `apps/api/src/auxd_api/modules/social/routes.py` |
| `POST /api/v1/users/me/follow-requests/{id}/approve` | required | recipient-only | `apps/api/src/auxd_api/modules/users/routes.py` |
| `DELETE /api/v1/notifications/push-subscriptions/{id}` | required | owner-only | `apps/api/src/auxd_api/modules/notifications/routes.py` |
| `PUT /api/v1/users/me/prefs` | required | self only (no `user_id` in path) | `apps/api/src/auxd_api/modules/users/routes.py` |
| `POST /api/v1/reports/*` | required | self-reporting rejected with 422 | `apps/api/src/auxd_api/modules/reports/service.py:63` |
| `/suspended` 403 contract | enforced by middleware | n/a | `apps/api/src/auxd_api/middleware.py:_account_suspended_response` |
| `POST /api/v1/notifications/mark-all-read` | required | owner-only (`NotificationCounter.user_id == session.user_id`) | `apps/api/src/auxd_api/modules/notifications/routes.py` |

**No IDOR vectors found.** All paths that take a target ID resolve
ownership against `session.user_id` before mutating.

## A02 — Cryptographic Failures

**Status: PASS.**

| Concern | Implementation | File:Line |
|---|---|---|
| Session cookie integrity | HMAC-SHA256 with ≥32-byte key, validated at settings load | `apps/api/src/auxd_api/lib/sessions.py`, `settings.py:103` |
| OAuth / OIDC token encryption | Fernet (AES-128-CBC + HMAC), with `MultiFernet` for key rotation | `apps/api/src/auxd_api/lib/secrets.py:76` |
| Password hashing | argon2id via `argon2-cffi`, defaults (time_cost=3, memory=64 MiB, parallelism=1) | `apps/api/src/auxd_api/modules/auth/password.py:30` |
| VAPID push keys | EC keypair from `pywebpush`, env-loaded, secret base64 (T136) | `apps/api/src/auxd_api/modules/notifications/push.py` |
| TLS termination | Fly.io edge (auto-issued, HSTS) + Vercel edge | infra |
| Cookies | `HttpOnly; SameSite=Lax; Secure` (when ENVIRONMENT != local) | `apps/api/src/auxd_api/middleware.py:121` |

No hand-rolled crypto; all primitives use vetted libraries.

## A03 — Injection

**Status: PASS.**

| Vector | Mitigation | Evidence |
|---|---|---|
| MongoDB query injection | Beanie + Motor only accept typed model fields → parameterized queries by construction | `apps/api/src/auxd_api/modules/**/service.py` |
| `$where` / `$function` clauses | `rg '\$where\|\$function\|eval\\b'` against `apps/api/src` → 0 hits | verified |
| Atlas Search injection | User input goes into `$search.text.query` (escaped by driver); no `$expr` | `apps/api/src/auxd_api/modules/search/service.py` |
| XSS in review markdown | Reviews rendered as plaintext with `whitespace-pre-line` CSS — no HTML/markdown parsing | `apps/web/src/app/(app)/review/[id]/page.tsx` |
| Header injection via user-supplied URLs | Avatar upload reads `bytes` not URL; OG image fetches its own env-locked backend | `apps/api/src/auxd_api/modules/users/routes.py:554`, `apps/web/src/app/api/og/**` |

## A04 — Insecure Design

**Status: PASS.**

| Design control | Where enforced |
|---|---|
| Rate limiting on every write endpoint | `apps/api/src/auxd_api/lib/rate_limit.py` — 11 modules wire `RateLimit` decorators (auth, backlog, diary, feed, notifications, reports, reviews, seeding, social, users) |
| Reports cannot self-report | `apps/api/src/auxd_api/modules/reports/service.py:63` → `self_report_forbidden` 422 |
| Idempotency keys | T060 idempotency-key pattern on writes (24h window on report submission) | `reports/service.py` |
| Private profile FollowRequest flow | T148 — POST follow against private profile returns 202 + creates pending Request entity; followee approves/declines | `social/routes.py` + `users/routes.py:follow-requests` |
| Block visibility cascade | Block makes both sides invisible; verified in `tests/integration/test_blocks.py` (T101) |
| Suspended-account allow-list | Only `/logout`, `/logout-all-devices`, `/users/me/delete` reachable when suspended | `middleware.py:_SUSPENDED_ALLOWED_PATHS` |

## A05 — Security Misconfiguration

**Status: OBSERVATION (LOW).**

| Check | Status | Notes |
|---|---|---|
| Required secrets validated at boot | PASS | `settings.py` `Settings` raises on missing/bad `SESSION_HMAC_KEY`, `TOKEN_ENCRYPTION_KEY`. `emit_startup_audit` (`settings.py:emit_startup_audit`) logs which integrations are enabled at INFO without leaking values. |
| `ALLOWED_ORIGINS` read at module load | PASS | `apps/api/src/auxd_api/main.py:101` — env var is read directly via `os.environ.get` to avoid `get_settings()` cache invalidation issues. |
| `DEBUG` stripped in production | PASS | FastAPI's `debug=False` is the default; no `?debug=` query parameters used. |
| Stack traces in production | PASS | Sentry-only; no `traceback` ever returned in API responses (verified by grep `traceback.print_exc` → 0 hits in `apps/api/src`). |
| CORS allow-list scope | LOW | `ALLOWED_ORIGINS` is a comma-separated string. Recommend a CI lint that rejects `*` literal at deploy time. |

🟡 **LOW follow-up:** Add a CI assertion that `ALLOWED_ORIGINS` env var does not contain `*` for `production` environment. (Track as post-launch.)

## A06 — Vulnerable + Outdated Components

**Status: OBSERVATION (LOW).**

| Stack | Pinning | Cadence |
|---|---|---|
| Python deps | `uv.lock` (pinned) | `uv lock --upgrade` quarterly |
| JS deps | `pnpm-lock.yaml` (pinned) | `pnpm update --interactive` quarterly + `pnpm dlx renovate-config-validator` periodically |
| Docker base | `python:3.14-slim` pinned in `Dockerfile` | Re-base quarterly |
| Fly machine OS | managed by Fly | n/a |

🟡 **LOW follow-up:** Wire Dependabot (or Renovate) on the GitHub repo to surface vulnerable transitive deps automatically. (Track post-launch.)

## A07 — Identification + Authentication Failures

**Status: RISK FIXED IN THIS SESSION — was HIGH.**

### Finding (CSRF wiring missing in the frontend)

The backend `SessionMiddleware`
(`apps/api/src/auxd_api/middleware.py:259-279`) enforces a
double-submit CSRF contract for **every authenticated state-changing
request**: the client must send an `X-CSRF-Token` header that matches
the `auxd_csrf` cookie. Pre-session-26 audit, `rg -i csrf apps/web`
returned **zero hits** — the frontend `apiFetch`
(`apps/web/src/lib/api-client.ts`) never lifted the cookie into the
header. **Every authenticated POST / PATCH / DELETE from the
production browser would have 403'd with
`csrf_token_invalid`** — including login → home redirect,
wedge logging, follow, like, settings save, account deletion.

Integration tests pass because they bypass `SessionMiddleware` with a
test-only `_FakeAuthMiddleware` and never exercise CSRF (see e.g.
`apps/api/tests/integration/test_account_settings_endpoints.py:64`
where `csrf_token="test-csrf"` is constructed in-line on the Session
dataclass without going through the cookie/header double-submit).

### Fix applied (this session)

1. **`apps/web/src/lib/api-client.ts`** — added a `readCsrfToken()`
   helper that reads `auxd_csrf` from `document.cookie` and a
   `CSRF_PROTECTED_METHODS` set covering `POST/PUT/PATCH/DELETE`.
   `apiFetch` now injects `X-CSRF-Token` automatically when the
   method is state-changing and a token is present.
2. **`apps/api/src/auxd_api/main.py:108`** — added
   `"X-CSRF-Token"` to the CORSMiddleware `allow_headers` allowlist
   (previously only `Content-Type, Accept, X-Requested-With`),
   without which the browser would strip the header on cross-origin
   preflights in dev (localhost:3000 → :8000).
3. **`apps/web/tests/unit/api-client.test.ts`** — added regression
   coverage: `apiFetch` (a) omits the header on GET, (b) lifts the
   cookie value into the header on POST when `document.cookie` is
   populated, (c) omits the header when no cookie is set (SSR /
   signed-out).

### Other A07 controls (all PASS)

| Control | File:Line |
|---|---|
| `session_version` bump on password change | `apps/api/src/auxd_api/modules/auth/routes.py:329` |
| `session_version` bump on email change | `apps/api/src/auxd_api/modules/users/routes.py` (T150) |
| Global logout-all-devices invalidates all cookies | `apps/api/src/auxd_api/modules/auth/routes.py:329` |
| Session HMAC validation refuses tampered cookies | `apps/api/src/auxd_api/middleware.py:215-232` |
| Cookie HttpOnly + SameSite=Lax + Secure (prod) | `apps/api/src/auxd_api/middleware.py:142-160` |
| Argon2id password hashing with defaults | `apps/api/src/auxd_api/modules/auth/password.py:30` |
| Password policy ≥12 chars + letter + digit | `apps/api/src/auxd_api/modules/auth/service.py:123` |
| Wrong-password error message is generic | `auth/routes.py` — "wrong email or password" (no user enumeration leak) |

## A08 — Software + Data Integrity Failures

**Status: PASS.**

| Control | Evidence |
|---|---|
| Lockfiles committed | `uv.lock`, `pnpm-lock.yaml` |
| CI codegen drift check | `pnpm exec biome check .` + `ruff check .` + `mypy --strict` + `pnpm build` + `pnpm exec tsc --noEmit` (all enforced in CI) |
| OpenAPI ↔ shared-types ↔ frontend drift | `packages/shared-types/src/api.ts` generated from the FastAPI `openapi.json`; drift check is a CI gate (Run #12 green) |
| Sync-verify cross-artifact gate | `features/001-auxd-mvp/sync-report.json` enforces 0 structural budget |
| Forge phase audit trail | `features/001-auxd-mvp/.forge-status.yml` |

## A09 — Security Logging + Monitoring

**Status: PASS.**

| Signal | Sink | Source |
|---|---|---|
| Structured app logs (`event=...`) | stdout (Fly captures) | `apps/api/src/auxd_api/lib/observability.py:log_call` decorator + `_LOGGER.info("session.invalid_cookie", extra={...})` in middleware |
| Errors | Sentry | `apps/api/src/auxd_api/main.py:71` `init_sentry` |
| OTel traces | OTel collector → backend | `apps/api/src/auxd_api/lib/otel.py` |
| Product analytics | PostHog | `apps/api/src/auxd_api/lib/observability.py` PostHog dispatcher |
| Moderation alerts | Discord webhook | `apps/api/src/auxd_api/modules/moderation/service.py` |
| Notification firehose alert | T144 alert at p95 > 12/user/week | `apps/api/src/auxd_api/workers/notification_rate_alert.py` |
| Rate-limit Redis-down warning | Sentry tag `rate_limit.redis_down` | `apps/api/src/auxd_api/lib/rate_limit.py:80` |

`session.csrf_mismatch`, `session.invalid_cookie`, and
`session.account_suspended` events all log at INFO with a structured
`event` field so an operator can grep production logs for spikes.

## A10 — Server-Side Request Forgery (SSRF)

**Status: PASS.**

| Possible SSRF source | Mitigation |
|---|---|
| Avatar upload | `Image.open(io.BytesIO(raw_bytes))` — Pillow opens from in-memory bytes, NEVER from a URL. No `Image.open(url)` anywhere in the codebase (`rg "Image.open" apps/api/src` → only the bytes path). |
| Catalog API calls | MusicBrainz + Discogs hit known fixed hosts (`musicbrainz.org`, `api.discogs.com`) via `ResilienceTransport` (`apps/api/src/auxd_api/lib/resilience.py`); host is hard-coded in the provider modules — no user input concatenated. |
| OG image fetch | `apps/web/src/app/api/og/album/[id]/route.tsx` fetches its own backend via `process.env.OG_BACKEND_URL` — no user URL fetches. |
| Discord webhook dispatch | Single env var `DISCORD_WEBHOOK_URL` — never user-controlled. |
| Resend email | Resend API endpoint hard-coded; recipient address is `User.email` (validated on signup). |
| GDPR export download | R2 presigned URL generated by us, not user-supplied. |

No user-supplied URL gets fetched anywhere in the codebase.

## Out-of-scope considerations (documented for completeness)

- **Mass-assignment / property pollution** — Beanie models declare
  fields explicitly via Pydantic, no `__init__(**kwargs)`-style
  spreads. PATCH endpoints whitelist fields via dedicated
  `Patch...` Pydantic models (e.g. `PatchPrivacy`). Verified by
  grep: no `User(**body)` calls in `apps/api/src`.
- **Sub-resource integrity (SRI)** — no third-party scripts loaded
  by the frontend. All assets bundled via Next.js. N/A.
- **Open redirect** — login flow always redirects to `/` (no
  `?next=` query param honoured). N/A.

## Sign-off

| Role | Name | Date | Status |
|---|---|---|---|
| Reviewer | Joshua Xie | 2026-05-23 | applied |
