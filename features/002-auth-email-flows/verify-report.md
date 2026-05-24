# Verify Report: Auth Email Flows (lite)

**Feature:** `002-auth-email-flows`
**Mode:** lite
**Date:** 2026-05-24
**Verdict:** **PASS** (0 CRITICAL · 0 WARNING · 26 PASSED)

Lite mode verification covers the four artifact layers that exist for
this feature: product-spec ↔ plan ↔ code ↔ tests. Research / spec.md /
tasks.md are `not_applicable` per lite mode and are not included in
the traceability chain.

---

## Layer 1: product-spec ↔ plan

| Spec item | Plan coverage | Status |
|---|---|---|
| US-001 Verify email at signup | §1A (`User.email_verified` field), §3E (signup bootstrap), §3A (verify endpoint), §5 (n018 template) | ✅ |
| US-002 Resend verification | §3B (resend endpoint, rate-limited 3/hr per-user, invalidates prior tokens) | ✅ |
| US-003 Forgot-password request | §3C (always-200, enumeration-resistant, fake-hash on no-match), §1C (PasswordResetToken collection) | ✅ |
| US-004 Reset-password consume | §3D (validates token, applies policy, bumps session_version, dispatches N017) | ✅ |
| US-005 /login Forgot-password link | §7B (login-form link swap to /forgot-password) | ✅ |
| FR-101 32-byte URL-safe token | §2 (`secrets.token_urlsafe(32)`) | ✅ |
| FR-102 24h / 1h TTLs | §1B (verify 24h), §1C (reset 1h) | ✅ |
| FR-103 Single-use | §3A/3D (mark `used_at`, deny re-consume) | ✅ |
| FR-104 Invalidate prior on resend | §3B/§3C (atomic `update_many` filter `used_at: None`) | ✅ |
| FR-105 7-day cleanup | §6 (arq cron) | ✅ |
| FR-110..114 Verification flow | §3A/3B/3E, §5 template, §4 middleware | ✅ |
| FR-120..123 Forgot/reset flow | §3C/3D, §5 template (n019), §3D N017 dispatch | ✅ |
| FR-130..133 Rate limits | §9 rate-limit summary table | ✅ |
| FR-140 No timing enumeration | §3C fake-hash on no-match | ✅ |
| FR-141 No response-body enumeration | §3C always-200 generic body | ✅ |
| FR-142 Resend infra reuse | §5 direct-send pattern + lib.resilience.retry | ✅ |

## Layer 2: plan ↔ code

| Plan section | Code path | Status |
|---|---|---|
| §1A User.email_verified | `apps/api/src/auxd_api/modules/users/models.py` | ✅ |
| §1B EmailVerificationToken | `apps/api/src/auxd_api/modules/auth/tokens_models.py` | ✅ |
| §1C PasswordResetToken | same file | ✅ |
| §2 Token primitive | `apps/api/src/auxd_api/lib/auth_tokens.py` | ✅ |
| §3A POST /auth/verify-email | `apps/api/src/auxd_api/modules/auth/routes.py:479` | ✅ |
| §3B POST /auth/resend-verification | `routes.py:524` | ✅ |
| §3C POST /auth/forgot-password | `routes.py:612` | ✅ |
| §3D POST /auth/reset-password | `routes.py:645` | ✅ |
| §3E Signup bootstrap | `routes.py:signup` (modified to issue token + send) | ✅ |
| §4 email_unverified middleware gate | `apps/api/src/auxd_api/middleware.py:112` (allow-list at L129) | ✅ |
| §5 n018_email_verification.html | `apps/api/src/auxd_api/templates/email/n018_email_verification.html` | ✅ |
| §5 n019_password_reset.html | `apps/api/src/auxd_api/templates/email/n019_password_reset.html` | ✅ |
| §5 send_verification_email helper | `apps/api/src/auxd_api/modules/auth/email_verification.py` | ✅ |
| §5 send_password_reset_email helper | `apps/api/src/auxd_api/modules/auth/password_reset.py` | ✅ |
| §6 Token cleanup cron | `apps/api/src/auxd_api/workers/auth_tokens_cleanup.py` + `workers/main.py` registration | ✅ |
| §7A /verify-email/[token] route | `apps/web/src/app/(auth)/verify-email/[token]/page.tsx` + `verify-email-client.tsx` | ✅ |
| §7A /forgot-password route | `apps/web/src/app/(auth)/forgot-password/page.tsx` + `forgot-password-form.tsx` | ✅ |
| §7A /reset-password/[token] route | `apps/web/src/app/(auth)/reset-password/[token]/page.tsx` + `reset-password-form.tsx` | ✅ |
| §7B Login form link swap | `apps/web/src/app/(auth)/login/login-form.tsx` | ✅ |
| §7C Verification banner | `apps/web/src/components/auth/verification-banner.tsx` + mounted in `(app)/layout.tsx` | ✅ |
| §7D Settings Email sub-section | `apps/web/src/components/profile-settings/index.tsx:EmailVerificationSection` | ✅ |
| §7E SanitizedUser.email_verified | `apps/web/src/stores/auth.ts` | ✅ |
| §7F api-client 403 handler | `apps/web/src/lib/api-client.ts` (`isEmailUnverifiedDetail`) | ✅ |
| §8 AUTH_TOKEN_PEPPER setting + validator | `apps/api/src/auxd_api/settings.py` + `apps/api/.env.example` | ✅ |
| §9 Rate-limit summary | All four endpoints register via `rate_limit(...)` factory in `routes.py` | ✅ |
| §10 Observability hooks | `log_call` + `emit_event` calls present in each endpoint | ✅ |

## Layer 3: code ↔ tests

| Surface | Test file | Coverage |
|---|---|---|
| Token primitive | `apps/api/tests/unit/test_auth_tokens.py` | 10 tests (entropy, determinism, pepper sensitivity, constant-time verify) |
| Verify endpoints + signup bootstrap | `apps/api/tests/integration/test_email_verification_endpoints.py` | 9 tests (happy, idempotent, expired, used, unknown, resend invalidation, anonymous 401) |
| Forgot/reset endpoints | `apps/api/tests/integration/test_password_reset_endpoints.py` | 13 tests (forgot happy, unknown email, unverified, suspended, deletion-pending, prior-invalidation; reset happy + session_version bump + N017 dispatch, expired, used, unknown, weak password) |
| email_unverified middleware | `apps/api/tests/integration/test_email_unverified_middleware.py` | 8 tests (GET pass, POST 403, allow-list, post-verification pass, anon 401) |
| Frontend api-client 403 handler | `apps/web/tests/unit/auth-email-flows.test.ts` | 7 tests (`isEmailUnverifiedDetail` correctness) |
| E2E happy paths via testmail.app | `apps/web/tests/e2e/auth-{email-verification,password-reset,forgot-password-no-enumeration}.spec.ts` | 3 specs, auto-skip without `TESTMAIL_NAMESPACE` + `TESTMAIL_API_KEY` |

## Final gate state

| Check | Result |
|---|---|
| Backend ruff | All checks passed |
| Backend mypy --strict | 0 errors in 216 source files |
| Backend pytest | **1083 passed / 3 skipped** (was 1043; +40 new tests) |
| Frontend biome | 164 files clean |
| Frontend tsc | 0 errors |
| Frontend vitest | **123 passed** (was 116; +7 new tests) |
| Live route compile | /forgot-password 200, /reset-password/{token} 200, /verify-email/{token} 200 |

## Operator follow-ups

| Item | Required before merge? | Notes |
|---|---|---|
| Generate + set `AUTH_TOKEN_PEPPER` in `apps/api/.env` (+ any deploy env) | **YES** | `python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| Confirm `PUBLIC_APP_URL` set in dev (already in `.env.example`) | already done | localhost:3000 for dev |
| Confirm Resend `RESEND_FROM_ADDRESS` domain verified | already done | re-uses existing config |
| Set `TESTMAIL_NAMESPACE` + `TESTMAIL_API_KEY` for E2E | optional | E2E specs skip cleanly without |
| No DB migrations to run | n/a | additive schema only |
| No DNS / domain changes | n/a | |

## Notable decisions captured in the implementation

- **Two separate token collections** (not unified) — cleaner cleanup
  cadence + rate-limit boundaries + future divergence.
- **Direct-send pattern** for verification + reset emails (bypasses
  the notification dispatcher; mirrors `gdpr_export.py`'s shape).
  Wrapped in `lib.resilience.retry` (3 attempts) with FailedEmail
  audit row on terminal failure.
- **Constant-time fake-Argon2** on forgot-password no-match path:
  pinned PHC string verified to keep CPU cost matched between hit/miss.
- **`(auth)` layout redirect moved** from layout-level into page-level
  on `/login` + `/signup` so the new recovery routes (which share the
  same `(auth)` shell) stay reachable while a session cookie is set.
- **Defensive `email_verified` read** on frontend (`!== false`) so a
  field-missing response doesn't spuriously show the banner —
  belt-and-braces while the backend gap was being closed (now closed).
- **`/logout-all-devices` added to unverified allow-list** alongside
  `/logout` — security operations should always work.

## Sync drift

None. Product-spec, plan, code, and tests are all aligned. Optional
phases (research, revalidation, bridge, tasks-as-separate-phase,
pre-impl review, code review, separate test plan/run, release readiness,
monitoring setup, experiment design) are `not_applicable` per lite mode
and do not generate drift.

---

**Phase 7 (Verify) verdict: PASS.** Feature is ready for commit + push.
Operator MUST set `AUTH_TOKEN_PEPPER` before next deploy.
