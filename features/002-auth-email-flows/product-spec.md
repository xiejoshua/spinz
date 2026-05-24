# Product Spec: Auth Email Flows (lite)

**Feature:** `002-auth-email-flows`
**Mode:** lite
**Status:** draft (Phase 2)

## Problem

The shipped auxd MVP authenticates users with email + password but does not
verify that the email belongs to the signer-up, nor offer a path to recover a
forgotten password. Two concrete user-facing gaps:

- A signup with a typo'd or hostile email gets the account anyway. Future
  password-reset email or transactional email will never reach the legitimate
  owner; the typo'd address remains immutably tied to a real account.
- A user who forgets their password has no recourse. The current "Forgot
  password?" link is a `mailto:appeals@auxd.xiejoshua.com` placeholder — a
  human-handled escape hatch that doesn't scale and is awkward for the user.

Both are standard auth-hygiene flows for any consumer product handling
identity + content. Add them now, before the M0 closed beta where any of these
edges will surface.

## Out of scope

- **Recovery of soft-deleted accounts.** Stays manual via
  `mailto:appeals@auxd.xiejoshua.com` per founder direction. The deletion
  banner on /login already routes here.
- **Multi-factor authentication (TOTP / SMS).** Deferred to v2 — separate
  feature.
- **Email-change verification UX.** Phase 6 will surface email change behind
  the same verification primitive but the change-email flow as a whole is a
  follow-up tightening, not a new flow.
- **Social-login providers.** Deferred indefinitely (post-CR-001).
- **Magic-link sign-in.** Deferred to v2 — different threat model.
- **Branded transactional domain.** Deploy-time concern; this feature uses the
  existing Resend `RESEND_FROM_ADDRESS` config.

## User stories

### US-001 — Verify email at signup
As a new signup, I want a one-click verification link sent to my email
immediately after account creation, so the platform can confirm I own that
address before I rely on it for security-critical communications.

**Acceptance:**
- Signup creates the User with `email_verified=false`, issues a session as
  today, and triggers an immediate verification email.
- Email contains a single-use link of the form `/verify-email/{token}` valid
  for **24 hours**.
- Clicking the link in any browser (signed-in OR signed-out) marks the email
  verified, invalidates the token, and lands the user on a confirmation page.
- Re-clicking the same link after success shows a friendly "already verified"
  state — no 500, no security warning.
- Unverified users CAN browse the app (read feeds, view profiles, etc.) but
  cannot perform state-changing writes (log entry, write review, follow user,
  upload avatar). A persistent banner with a "Resend verification email"
  button shows on every authenticated page until verified.

### US-002 — Resend verification email
As a user whose verification email got lost (spam, typo, slow delivery), I
want to request a fresh email without having to sign up again.

**Acceptance:**
- A "Resend verification email" button on the unverified-banner and on
  `/settings/account` (when unverified) sends a fresh email.
- Rate-limited per-user **3 / hour**; user-friendly toast on rate-limit hit.
- Each resend invalidates any prior unused token (one valid token at a time).

### US-003 — Forgot password (request)
As a user who forgot my password, I want to request a reset email by entering
the email associated with my account, so I can regain access without
contacting support.

**Acceptance:**
- `/forgot-password` page hosts a one-field form (email).
- Submitting returns a generic success message regardless of whether the
  email is registered (no enumeration). Always shows "If that email is
  registered, we sent a reset link."
- Email contains a single-use link `/reset-password/{token}` valid for **1
  hour**.
- Rate-limited per-IP **5 / hour** and per-email **3 / hour**.
- Reset request against a `DELETION_PENDING` or `SUSPENDED` user silently
  succeeds at the response layer (no enumeration) but does NOT actually send
  the email — those users have a different recovery path.

### US-004 — Reset password (consume)
As a user who clicked a password-reset link, I want to set a new password and
be signed in.

**Acceptance:**
- `/reset-password/{token}` page hosts new-password + confirm fields.
- On submit: backend validates the token (exists, not used, not expired),
  enforces password policy (≥12 chars, ≥1 letter, ≥1 digit — same as signup),
  hashes via Argon2, sets `password_hash`, bumps `session_version` (logs out
  every existing session on every device), marks the token used.
- Issues a fresh session cookie and lands on `/feed`.
- An email confirmation ("Your password was changed") fires immediately via
  the existing N017 notification type (already wired).
- Expired / used / unknown tokens all show a friendly "This link is no longer
  valid. Request a fresh one." page that links back to `/forgot-password`.

### US-005 — Forgot-password link on /login
As a user staring at the login page who realises they forgot their password,
I want a one-click path to the reset flow.

**Acceptance:**
- The "Forgot password?" link under the password input on `/login` (already
  editorial-styled, currently a `mailto:` placeholder) now routes to
  `/forgot-password`.
- The recovery `mailto:appeals@…` link stays on the deletion-pending banner
  (separate path for deleted-account recovery).

## Functional requirements

### Tokens (shared infrastructure)
- **FR-101** Tokens are 32-byte cryptographically random URL-safe base64
  strings (~43 chars). Stored hashed (SHA-256 with a per-deploy pepper) at
  rest; the raw token is only ever emitted in the email payload.
- **FR-102** Verification tokens TTL: 24h. Reset tokens TTL: 1h.
- **FR-103** All tokens are single-use. `used_at` stamped on successful
  consumption. Subsequent attempts return the friendly "no longer valid"
  state, not a security error.
- **FR-104** Creating a new token of the same kind for the same user
  invalidates prior unused tokens of that kind.
- **FR-105** Expired/used tokens are deleted by an arq cron job after 7
  days. Audit log retained per Constitution P2.

### Verification flow
- **FR-110** Signup writes `User.email_verified=false` +
  `User.email_verified_at=null` and issues a verification token in the
  same transaction.
- **FR-111** Verification email uses a new Jinja template
  `n018_email_verification.html` inheriting from `base.html`.
- **FR-112** GET `/api/v1/auth/verify-email?token=…` (or POST equivalent)
  validates the token and flips the user's verified state. Idempotent on
  re-click — already-verified users get a 200 with a benign body.
- **FR-113** POST `/api/v1/auth/resend-verification` is authenticated
  (the user has a session even if unverified); rate-limited 3/hour
  per-user.
- **FR-114** Backend `SessionMiddleware` adds a "verified" allow-list
  parallel to the existing suspended allow-list: unverified users can
  hit `/healthz`, the auth surface, `GET` reads, and the resend/verify
  endpoints, but state-changing routes return `403 email_unverified` if
  the user is `email_verified=false`.

### Forgot-password flow
- **FR-120** POST `/api/v1/auth/forgot-password` { email } returns 200
  with a generic body for every input. Looks up user by lowercased
  email. If found AND status is `ACTIVE` AND `email_verified=true`,
  issues a fresh token + sends email; otherwise no-op.
- **FR-121** POST `/api/v1/auth/reset-password` { token, new_password }
  validates the token, enforces password policy, persists the new hash,
  bumps `session_version`, marks token used, issues a session cookie,
  returns the user payload.
- **FR-122** Password-reset email uses Jinja template
  `n019_password_reset.html`.
- **FR-123** After successful reset, an N017
  (`security.password_changed`) notification fires via the existing
  dispatcher (no new notification type needed — N017 already covers
  "your password was changed").

### Rate limits
- **FR-130** `/auth/forgot-password`: per-IP 5/hour, per-email 3/hour.
- **FR-131** `/auth/reset-password`: per-IP 10/hour (token entropy is
  the primary guard).
- **FR-132** `/auth/verify-email`: per-IP 30/hour (single-use tokens
  don't need tight per-IP limits since each is invalidated on use).
- **FR-133** `/auth/resend-verification`: per-user 3/hour.

### Security
- **FR-140** No timing-based enumeration. Token validation uses
  `secrets.compare_digest`. Forgot-password path performs the user
  lookup + a fake hash computation even on no-match so response time
  is constant across hit/miss.
- **FR-141** No enumeration via response body. Forgot-password and
  reset-password return the same generic success/failure messages
  regardless of whether the email/user exists.
- **FR-142** All emails use the existing Resend infrastructure with the
  same retry + FailedEmail audit row pattern as N008 / N013 / etc.

## Non-functional requirements

- **NFR-1 (Privacy / GDPR)** Reset + verification tokens link a user to
  their email. The cleanup cron purges them at 7 days; the audit log
  retains only token IDs + outcomes, never the secret.
- **NFR-2 (Performance)** Verification + reset endpoints respond <500ms
  at p95 in dev (token validation is a single Mongo lookup by
  `token_hash` index + an Argon2 password verify for reset).
- **NFR-3 (Observability)** Every state transition emits a structured
  `log_call` line (`auth.verification_sent` / `_consumed` / `_expired` /
  `_used`, `auth.reset_requested` / `_consumed` / `_invalid`) plus a
  PostHog `auth.*` event with the same code so the funnel is visible
  in analytics.
- **NFR-4 (Email deliverability)** The two new templates inherit
  `base.html` (logo, footer, no tracking pixel) so they pass the same
  spam-filter checks as the existing N008/N013 templates.

## Locked decisions

| Decision | Locked value | Rationale |
|---|---|---|
| Token format | 32-byte URL-safe base64, SHA-256 + pepper at rest | Standard. Pepper raises the cost of a leaked-table attack. |
| Verification TTL | 24h | Industry standard; matches email-arrival expectations. |
| Reset TTL | 1h | OWASP recommendation; short window limits replay risk on link leak. |
| Unverified browse | Read-only allowed; writes 403 | Lets users explore the app before committing the verification click; prevents content creation from un-vouched addresses. |
| Forgot-password enumeration | Always generic 200 + always-on fake-hash timing | Industry standard. |
| Deleted-account recovery | Manual via `mailto:appeals@auxd.xiejoshua.com` (unchanged) | Per founder direction; deletion path is rare enough that manual is fine. |
| Email change verification | Out of scope for this feature | Follow-up; existing `/settings/account` email change still requires current password but does NOT verify the new address yet. |
| Provider | Resend (unchanged) | testmail.app handles E2E test inboxes; Resend handles real delivery. |
| Token cleanup cadence | arq cron, 7-day retention | Matches the existing FailedEmail cleanup pattern. |

## Test strategy

E2E happy paths via Playwright + testmail.app:

1. **Verify happy path** — signup with `<ns>.<id>@inbox.testmail.app` → poll
   testmail.app for the verification email → click link → assert
   `email_verified=true` in `/api/v1/users/me` payload.
2. **Resend** — request resend → assert old token rejected, new token accepted.
3. **Forgot-password happy path** — request reset → poll inbox → click link →
   set new password → assert old password fails, new password succeeds.
4. **Forgot-password enumeration guard** — request reset for unregistered
   email → assert 200 + generic body + no email sent (testmail.app inbox
   stays empty after a short poll).
5. **Reset session invalidation** — reset password → assert all previously
   issued cookies fail (401 on `/users/me`).

Unit/integration tests cover token-creation, validation, replay,
expiry, rate-limit hits, and policy enforcement.

## Open questions

None at this draft. The decision matrix above is canonical for Phase 5 (Plan).
