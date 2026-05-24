# Technical Plan: Auth Email Flows (lite)

**Feature:** `002-auth-email-flows`
**Mode:** lite (single-doc plan, no separate tasks.md)
**Status:** draft (Phase 5)

## 0. Pre-flight

- **Resend** already wired (`apps/api/src/auxd_api/modules/notifications/adapters/email.py`,
  uses `resend.Emails.send` via `asyncio.to_thread`); reuse end-to-end.
- **Argon2 password hashing** already wired (`apps/api/src/auxd_api/modules/auth/password.py`).
- **`session_version` invalidation pattern** already exists (T150 password change,
  schedule_account_deletion); reuse for password reset.
- **Rate-limit factory** at `apps/api/src/auxd_api/lib/rate_limit.py`; reuse.
- **Jinja templates** under `apps/api/src/auxd_api/templates/email/` inherit
  `base.html`; reuse with two new templates.
- **arq cron** workers wired at `apps/api/src/auxd_api/workers/`; reuse.
- **No new infra config** — testmail.app is operator-side (Playwright config),
  not part of the backend deployment.

## 1. Schema deltas

### 1A. `User` (existing collection, additive)

| Field | Type | Default | Notes |
|---|---|---|---|
| `email_verified` | `bool` | `False` | New users start unverified. Existing 0 users in prod => no backfill concern, but the schema_version pattern (Constitution P2) handles it on lazy-upgrade-on-write. |
| `email_verified_at` | `datetime \| None` | `None` | Stamped on successful verification. |

No index changes. `email_verified` is a small enum; queries are usually
keyed by `_id` or `email` already.

### 1B. `EmailVerificationToken` (new collection)

| Field | Type | Notes |
|---|---|---|
| `id` | `str` (KSUID) | Primary key. |
| `user_id` | `str` | FK to User._id. |
| `token_hash` | `str` | SHA-256 of `(raw_token + pepper)`, hex. **Unique index.** |
| `expires_at` | `datetime` | `created_at + 24h`. |
| `used_at` | `datetime \| None` | Stamped on consume. |
| `created_at` | `datetime` | Audit. |

Indexes:
- `token_hash` UNIQUE — lookup on verify.
- `user_id, used_at` — invalidate prior tokens on resend (partial filter
  `used_at: null`).
- `expires_at` — cleanup cron sweep.

### 1C. `PasswordResetToken` (new collection)

Same shape as `EmailVerificationToken` but TTL is **1h** instead of 24h.
Separate collection (not a unified `AuthToken` with a `kind` field)
because:
- Cleanup cadence differs.
- Rate-limit windows differ.
- Future divergence (e.g., 2FA challenge tokens) is easier with
  separate collections than with a polymorphic one.

### 1D. Migration

Additive only — no destructive change to existing rows. New fields on
`User` default to `False`/`None`; new collections have no pre-existing
data. Falls under the Constitution P2 "lazy-upgrade-on-write" pattern;
no `migrations/00N_*.py` runner entry needed (the runner is for
schema-version-driven structural rewrites, not pure additive fields).

## 2. Token primitive (`lib/auth_tokens.py`)

Small module owning the raw-token generation + hashing contract.
Single import surface so verification + reset paths use identical
crypto:

```python
TOKEN_BYTES = 32  # 256-bit secret; URL-safe base64 → ~43 chars

def generate_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Raw goes in the email; hash goes in Mongo."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    return raw, _hash(raw)

def hash_token(raw: str) -> str:
    """SHA-256(raw || pepper), hex. Deterministic — same input always hashes the same."""
    pepper = get_settings().AUTH_TOKEN_PEPPER
    return hashlib.sha256((raw + pepper).encode("utf-8")).hexdigest()

def verify_token(raw: str, expected_hash: str) -> bool:
    """Constant-time compare against the stored hash."""
    return secrets.compare_digest(hash_token(raw), expected_hash)
```

New setting `AUTH_TOKEN_PEPPER` — base64 32-byte secret (operator MUST
provision and rotate independently of SESSION_HMAC_KEY). Validated at
boot with the same `>=32 bytes after b64 decode` rule as
SESSION_HMAC_KEY.

## 3. Backend endpoints

All four under `apps/api/src/auxd_api/modules/auth/routes.py` (extends
the existing router; preserves the prefix `/auth`).

### 3A. `POST /api/v1/auth/verify-email`
- Body: `{ token: str }`
- Anonymous-callable (the link in the email works even when logged
  out — the user might click from a different device).
- Looks up `EmailVerificationToken` by `token_hash`. Validates `used_at
  is None` AND `expires_at > now`.
- On success: marks token `used_at`, loads the linked user, sets
  `email_verified=True` + `email_verified_at=now()`, persists.
- Idempotent re-click: if the linked user is already verified, returns
  200 with `{verified: true, idempotent: true}`. No error.
- Rate limit: per-IP 30/hour.

### 3B. `POST /api/v1/auth/resend-verification`
- Authenticated. The signup path issued a session, so the unverified
  user still has a cookie.
- Rate limit: per-user 3/hour.
- If user is already verified: 200 with `{verified: true}` no-op.
- Otherwise: invalidate all unused EmailVerificationToken rows for
  this user (set `used_at=now()` with reason `superseded`), generate
  a fresh token, send email.

### 3C. `POST /api/v1/auth/forgot-password`
- Body: `{ email: EmailStr }`
- Anonymous.
- **Always returns 200 with body `{ok: true, message: "If that email is registered, we've sent a reset link."}`** regardless of outcome.
- Internal flow:
  - Lower-case email lookup.
  - If `user is None`: do a single Argon2-verify call against a static
    dummy hash so response time is constant. Return.
  - If `user.status is not ACTIVE` (DELETED, SUSPENDED, DELETION_PENDING):
    return without sending. Audit log records the silent skip.
  - If `user.email_verified is False`: return without sending. We don't
    want to push reset links to addresses the user hasn't claimed.
  - Otherwise: invalidate prior unused reset tokens for this user,
    generate new one, send email.
- Rate limits: per-IP 5/hour, per-email 3/hour.

### 3D. `POST /api/v1/auth/reset-password`
- Body: `{ token: str, new_password: str }`
- Anonymous.
- Validates token (same shape as verify). If invalid/used/expired:
  return `410 token_invalid`.
- Applies password policy via the existing public
  `validate_password_policy` helper.
- Updates `user.password_hash`, bumps `user.session_version`,
  stamps token `used_at`.
- Issues a fresh session (caller is now logged in).
- Dispatches the existing `N017_SECURITY_PASSWORD_CHANGED`
  notification (via `dispatch_notification`) so the user gets the
  "your password was changed" email automatically.
- Rate limit: per-IP 10/hour.

### 3E. Signup endpoint change
- Existing `POST /api/v1/auth/signup` (in
  `apps/api/src/auxd_api/modules/auth/routes.py:signup`) now also:
  1. After `User.insert()`, generates an EmailVerificationToken.
  2. Dispatches the verification email via a new helper
     `send_verification_email(user, raw_token)`.
- If the email send fails, **signup still succeeds** — the user can
  resend from the banner. Catch + log + Sentry-tag; do not block.

## 4. Middleware: `email_unverified` gate

Extend `apps/api/src/auxd_api/middleware.py:SessionMiddleware` with a
verification check that mirrors the existing SUSPENDED check, but
applies only to **state-changing** methods (POST/PATCH/PUT/DELETE):

```python
_UNVERIFIED_ALLOWED_PATHS = frozenset({
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/auth/logout",
    "/api/v1/users/me/data-export",  # GDPR right is not gated on verification
    "/api/v1/users/me/delete",       # User can change their mind without verifying
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
})
```

When `user.email_verified is False` AND method is state-changing AND
path not in allow-list → return:

```json
{
  "error": "email_unverified",
  "message": "Verify your email to continue.",
  "resend_endpoint": "/api/v1/auth/resend-verification"
}
```

Status 403. Frontend reads the `error` code and surfaces the
verification banner.

## 5. Email templates

Two new files under
`apps/api/src/auxd_api/templates/email/`:

- **`n018_email_verification.html`** — extends `base.html`. Subject:
  "Confirm your email for auxd". One CTA button → `{verify_url}`
  (constructed as `{PUBLIC_APP_URL}/verify-email/{raw_token}`).
  Footer: "If you didn't sign up, ignore this email."
- **`n019_password_reset.html`** — extends `base.html`. Subject:
  "Reset your auxd password". CTA → `{reset_url}`. Footer: "If you
  didn't request this, you can ignore. Your password stays the same."

Both templates use StrictUndefined (existing pattern) — missing keys
fail loud at adapter-call time, not in the recipient's inbox.

**Direct send pattern** (bypassing the dispatcher):

The dispatcher (`apps/api/src/auxd_api/modules/notifications/dispatcher.py`)
operates on `Notification` rows tied to a `NotificationType` enum
value. Verification + reset emails are out-of-band — they're sent
DURING the authentication transition, not as a result of a user-side
event. They follow the same direct-send pattern as the GDPR export
email in `workers/gdpr_export.py`:

```python
import resend
resend.api_key = settings.RESEND_API_KEY
resend.Emails.send({
    "from": settings.RESEND_FROM_ADDRESS,
    "to": [user.email],
    "subject": subject,
    "html": rendered_html,
})
```

Wrapped in `lib.resilience.retry` (3 attempts, exponential 0.5–5s);
on exhaustion writes a `FailedEmail` audit row + Sentry tag.

## 6. Worker: token cleanup

New `apps/api/src/auxd_api/workers/auth_tokens_cleanup.py` — arq cron
running daily at 04:00 UTC. Sweeps both token collections; deletes
rows where `(used_at is not None AND used_at < now-7d) OR (used_at is
None AND expires_at < now-7d)`. Audit log emits `auth.token_cleanup`
with row counts.

Registered in `workers/main.py` `WorkerSettings.cron_jobs` next to
the existing `digest_dispatch` cron.

## 7. Frontend surfaces

### 7A. New routes
- **`/verify-email/[token]/page.tsx`** — Server component, public. On
  mount calls `POST /api/v1/auth/verify-email` with the token; shows
  one of three editorial states: success (Newsreader headline,
  "Email verified.", CTA → `/feed`); already-verified (idempotent
  branch, same shape); failure (410 "This link is no longer valid",
  link → `/login`).
- **`/forgot-password/page.tsx`** — Public. One-field form
  (email). On submit calls `/api/v1/auth/forgot-password`; always
  shows generic success page ("Check your inbox") regardless of
  response.
- **`/reset-password/[token]/page.tsx`** — Public. Two-field form
  (new password + confirm). On submit calls
  `/api/v1/auth/reset-password`; on success redirects to `/feed`
  (session cookie comes in the response); on 410 shows "Link no
  longer valid" + CTA → `/forgot-password`.

All three follow the existing editorial pattern: mono uppercase
eyebrow, Newsreader serif headline, hairline rule, sans body, single
form. Match `/login` + `/signup` chrome (no `(auth)` group — these
are public and the layout reuses the auth chrome).

### 7B. Login form
- "Forgot password?" link beneath the Password input (already
  editorial-styled): swap from `mailto:appeals@…` to
  `<Link href="/forgot-password">`.

### 7C. Verification banner
- New `components/auth/verification-banner.tsx`. Mounted in
  `(app)/layout.tsx` between the header and the page children.
  Reads `useAuthStore().user.email_verified`; if `false`, renders a
  Section-tone-danger banner with body "Verify your email to
  continue. Check your inbox or [Resend verification email]." Button
  calls `POST /api/v1/auth/resend-verification`; success toast on 200,
  rate-limit toast on 429.
- The banner is the ONLY mention; no modal, no full-screen lock.

### 7D. Settings page
- `/profile/[handle]/settings`'s ProfileSettings index renders a new
  "Email" sub-section under Account when `email_verified=false`:
  shows the email + a "Resend verification" button. When verified:
  shows the email + small mono "VERIFIED" badge.

### 7E. Type addition
- Extend `SanitizedUser` (`apps/web/src/stores/auth.ts`) with
  `email_verified: boolean`. Auth-hydrator + `/users/me` payload
  already round-trip the whole user object; just add the field on
  both ends.

### 7F. 403 `email_unverified` handler
- `lib/api-client.ts`'s 403 handler currently routes `account_suspended`
  to `/suspended`. Extend with `email_unverified` → toast "Verify
  your email to continue." + no redirect (the banner is permanent
  context already).

## 8. Settings + env

Add to `apps/api/src/auxd_api/settings.py`:

```python
AUTH_TOKEN_PEPPER: str = Field(
    description="Base64-encoded 32-byte secret. Hashes verification + reset tokens at rest.",
)
PUBLIC_APP_URL: str = Field(
    default="http://localhost:3000",
    description="Origin for verify-email + reset-password links. Already used by web push.",
)
```

`PUBLIC_APP_URL` already exists (per `apps/api/src/auxd_api/modules/notifications/adapters/web_push.py`); confirm and reuse. `AUTH_TOKEN_PEPPER` is new — operator generates with `python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"` and sets in `apps/api/.env`.

Boot-time validation: same pattern as `SESSION_HMAC_KEY` — require
`>=32 bytes after b64 decode`.

## 9. Rate limit summary

| Endpoint | Per-IP | Per-user / per-email |
|---|---|---|
| `POST /auth/verify-email` | 30/hr | — |
| `POST /auth/resend-verification` | — | 3/hr per-user |
| `POST /auth/forgot-password` | 5/hr | 3/hr per-email |
| `POST /auth/reset-password` | 10/hr | — |

Implementation via the existing `rate_limit(endpoint=…, per_ip=…, per_user=…)` factory in `lib/rate_limit.py`. Per-email rate limits piggy-back on the user-id path internally (look up user by email first, fall back to anonymous limit if no match — same enumeration-resistance posture).

## 10. Observability

Every state transition emits structured `log_call` + PostHog event:

| Event | Provider | Endpoint | Status |
|---|---|---|---|
| Token issued (verify) | `auxd` | `auth.verification_sent` | `ok` |
| Token consumed (verify) | `auxd` | `auth.verification_consumed` | `ok` |
| Token rejected (verify) | `auxd` | `auth.verification_invalid` | `rejected` |
| Token resent (verify) | `auxd` | `auth.verification_resent` | `ok` |
| Reset requested | `auxd` | `auth.reset_requested` | `ok` |
| Reset requested (no-match) | `auxd` | `auth.reset_no_match` | `noop` |
| Reset consumed | `auxd` | `auth.reset_consumed` | `ok` |
| Reset rejected | `auxd` | `auth.reset_invalid` | `rejected` |
| Middleware 403 | `auxd` | `session.email_unverified` | `rejected` |

PostHog events mirror with `auth.*` namespace.

## 11. Tests

### Backend (pytest)
New test files under `apps/api/tests/integration/`:
- `test_email_verification_endpoints.py` — verify happy path,
  idempotent re-click, expired token, used token, unknown token, rate
  limits, signup-bootstraps-token assertion, resend invalidates prior.
- `test_password_reset_endpoints.py` — forgot-password happy path,
  generic 200 for unknown email, generic 200 for unverified email,
  generic 200 for suspended/deletion_pending, rate limits, reset
  consumes token, reset bumps session_version, reset enforces password
  policy, reset fires N017 notification.
- `test_email_unverified_middleware.py` — write methods 403 when
  unverified, allow-list paths pass, read methods always pass.
- `test_auth_tokens_lib.py` — token entropy, hash determinism,
  constant-time verify, expired-detection.

### Frontend (vitest)
- `tests/unit/auth-tokens-client.test.ts` — 403 `email_unverified` handler in `api-client.ts`.
- Vitest unit tests for new pages' state machines (success/failure branches).

### E2E (Playwright + testmail.app)
Behind `E2E_BACKEND_REACHABLE` gate (existing pattern). Uses the
`@testmail-app/api` GraphQL client:

- `verify-email-happy-path.spec.ts` — sign up with
  `<TESTMAIL_NAMESPACE>.<random-tag>@inbox.testmail.app`, poll
  testmail.app's GraphQL for the inbound email, parse the
  `/verify-email/{token}` link, navigate, assert verified state.
- `forgot-password-happy-path.spec.ts` — same shape but for reset.
- `forgot-password-no-enumeration.spec.ts` — request reset for an
  unregistered email, assert no message arrives at testmail.app
  within a 30s window.

`.env.test` (new) carries `TESTMAIL_NAMESPACE` and `TESTMAIL_API_KEY`
(operator-provisioned). Tests skip cleanly when those env vars are
absent so CI without testmail credentials still passes.

## 12. Implementation order (suggested task slicing)

This is lite mode — no separate tasks.md. The plan IS the slicing.
Suggested PR-able chunks:

1. **Schema + token lib + settings** (backend foundation). Includes
   `User.email_verified` field, two token collections, `lib/auth_tokens.py`,
   `AUTH_TOKEN_PEPPER` settings boot validation. Lands first; nothing else
   compiles without it.
2. **Verify-email endpoint set + template** (FR-110..114). Signup-bootstraps-
   token, verify endpoint, resend endpoint, `n018` template, direct-send helper.
3. **Email-unverified middleware gate** (FR-114). Includes 403 path with
   allow-list, frontend api-client 403 handler.
4. **Forgot-password endpoint + reset-password endpoint + template**
   (FR-120..123). N017 notification dispatch on reset.
5. **Cleanup worker** + arq cron registration.
6. **Frontend new routes**: `/verify-email/[token]`, `/forgot-password`,
   `/reset-password/[token]`. Editorial chrome, mono+Newsreader.
7. **Verification banner** in (app) layout + Settings sub-section
   updates.
8. **Login-form "Forgot password?" link swap** to `/forgot-password`.
9. **Tests + Playwright + testmail.app wiring**.

Total estimated tasks: ~14–16 chunks (lite-mode "small" each).

## 13. Operator-side checklist (pre-merge)

- [ ] Generate + set `AUTH_TOKEN_PEPPER` in `apps/api/.env` (and any deploy env).
- [ ] Confirm `PUBLIC_APP_URL` is set on dev (`http://localhost:3000`) and
      whatever the deploy env points at.
- [ ] (Optional but recommended) Set `TESTMAIL_NAMESPACE` + `TESTMAIL_API_KEY`
      env vars locally for E2E tests; tests skip without them.
- [ ] Resend account: confirm the existing `RESEND_FROM_ADDRESS` domain is
      verified — verification + reset emails go through the same sender.
- [ ] No DB migrations to run by hand — additive schema only.
- [ ] No DNS / domain changes for this feature.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Email delivery slow / blocked (spam, greylist) | Resend retry x3 + FailedEmail audit row already in place. Resend verification button on banner. |
| Unverified-state write-gate breaks existing E2E flow | The flow only kicks in after signup — existing E2E suites that sign up as part of setup can skip the click, or directly toggle `email_verified=true` via a test-only escape hatch (NOT exposed in prod). |
| Pepper leak ↔ tokens become guessable | Pepper is operator-managed env secret; rotate independently of SESSION_HMAC_KEY. Token entropy alone (32 bytes) is sufficient against online attack; pepper is defence-in-depth against offline DB exfiltration. |
| Forgot-password timing leak | Always-on fake-hash on no-match (constant-time response). Always-200 response body. Existing rate limits cap probe volume. |
| Race: two simultaneous resend-verification requests | The "invalidate prior unused" step uses `update_many` with `used_at: None` filter → atomic; worst case both attempts mark the same prior token used, both insert fresh tokens, both emails fire. Last-one-wins user experience is benign (just one extra email). |
| User can't receive email (typo at signup) | Email change verification deferred; user contacts appeals@. Operator handles. |

## 15. Sync map

| Layer | Artifact | Coverage |
|---|---|---|
| Spec | product-spec.md | All FRs traced. |
| Plan | this doc | All sections present. |
| Tasks | (rolled into §12) | n/a — lite mode. |
| Code | (Phase 6 produces) | Will write back into the task_log. |
| Tests | (Phase 6 produces) | Will surface in verify. |

End of plan.
