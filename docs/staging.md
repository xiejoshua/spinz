# Staging Environment Runbook (T175)

> Last reviewed: 2026-05-23 (Session 26).
> Purpose: zero-context replay of the staging-environment lifecycle —
> provision, deploy, smoke test, rollback. No code changes; this is a
> pure ops runbook.

## Architecture overview

Staging is a **production-shaped, lower-cost mirror** of the prod
stack. Same code; isolated data + secrets.

| Component | Production | Staging |
|---|---|---|
| Frontend | Vercel project `auxd-web` (xiejoshua.com) | Vercel preview branch (`staging` branch → preview URL) |
| Backend | Fly app `auxd-api` (iad) | Fly app `auxd-api-staging` (iad) |
| Database | MongoDB Atlas M0 cluster `auxd-prod` | MongoDB Atlas M0 cluster `auxd-staging` |
| Redis | Upstash `auxd-redis-prod` | Upstash `auxd-redis-staging` |
| Object storage | R2 bucket `auxd-backups-prod` | R2 bucket `auxd-backups-staging` |
| Sentry | project `auxd-api-prod` | project `auxd-api-staging` |
| PostHog | project `auxd-prod` | project `auxd-staging` |
| Email | Resend domain `auxd.xiejoshua.com` | Resend sandbox domain `staging.auxd.xiejoshua.com` |
| Discord moderation webhook | `#auxd-moderation-prod` | `#auxd-moderation-staging` |

## 1. Provisioning

### 1.1 Fly app

```bash
# Create the Fly app + a single iad machine for `web` + one for `worker`.
flyctl apps create auxd-api-staging --org personal
# Verify
flyctl apps list | grep auxd-api-staging
```

Copy `apps/api/fly.toml` to `apps/api/fly.staging.toml` and adjust:

```toml
app = "auxd-api-staging"
primary_region = "iad"

[env]
  ENVIRONMENT = "staging"
  LOG_LEVEL = "INFO"
  POSTHOG_HOST = "https://us.i.posthog.com"
  R2_BUCKET_NAME = "auxd-backups-staging"
  ALLOWED_ORIGINS = "https://staging.xiejoshua.com,https://auxd-web-staging.vercel.app"
```

Everything else (processes, http_service, vm sizing) stays the same.

### 1.2 MongoDB Atlas

1. Create cluster: Atlas UI → "+ Build a Cluster" → M0 Free → `auxd-staging` in
   `us-east-1` (lowest hop to Fly iad).
2. Network access → Add IP `0.0.0.0/0` (Fly egress is dynamic; we
   rely on MONGO connection-string credentials for auth).
3. Database access → Add user `auxd_staging` with `readWrite` on
   database `auxd_staging`.
4. Copy the SRV connection string. Encode the password.

### 1.3 Upstash Redis

1. Upstash Console → "+ Create Database" → `auxd-redis-staging` →
   region `us-east-1` (Virginia).
2. TLS: enable.
3. Copy `UPSTASH_REDIS_REST_URL` (we use the standard `redis://`
   URL via REST is not needed; the FastAPI app uses redis-py).

### 1.4 Cloudflare R2

```bash
wrangler r2 bucket create auxd-backups-staging
```

Generate an R2 token with `Object Read & Write` scope; store the
access-key-id, secret-access-key, account-id, and endpoint URL.

### 1.5 Vercel preview

Vercel project `auxd-web` → Settings → Git → set `staging` branch
to "Always create a preview deployment". Then push a `staging`
branch from git:

```bash
git checkout -b staging
git push origin staging
```

The first push triggers a preview build with the env vars below.

## 2. Secrets

All secrets live in `flyctl secrets` for the backend, and in
Vercel's "Environment Variables" pane for the frontend. **Never
commit secrets to the repo.**

### 2.1 Backend Fly secrets

```bash
# Crypto secrets (T019, T017). 32-byte b64. Generate with:
#   python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
flyctl secrets set -a auxd-api-staging \
  SESSION_HMAC_KEY="<base64-32b>" \
  TOKEN_ENCRYPTION_KEY="<base64-32b>"

# Datastores
flyctl secrets set -a auxd-api-staging \
  MONGODB_URI="mongodb+srv://auxd_staging:<pw>@auxd-staging.xxxx.mongodb.net/auxd_staging?retryWrites=true&w=majority" \
  REDIS_URL="rediss://default:<pw>@<host>.upstash.io:6379"

# Email + Resend (sandbox domain at staging)
flyctl secrets set -a auxd-api-staging \
  RESEND_API_KEY="re_<staging_key>"

# Push notifications (VAPID, T136)
flyctl secrets set -a auxd-api-staging \
  VAPID_PRIVATE_KEY="<staging private key>" \
  VAPID_PUBLIC_KEY="<staging public key>" \
  VAPID_SUBJECT="mailto:appeals@staging.auxd.xiejoshua.com"

# Cloudflare R2
flyctl secrets set -a auxd-api-staging \
  R2_ACCESS_KEY_ID="<staging key id>" \
  R2_SECRET_ACCESS_KEY="<staging secret>" \
  R2_ACCOUNT_ID="<account>" \
  R2_ENDPOINT_URL="https://<account>.r2.cloudflarestorage.com"

# Discord (separate staging webhook)
flyctl secrets set -a auxd-api-staging \
  DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/<staging>"

# Observability
flyctl secrets set -a auxd-api-staging \
  SENTRY_DSN="https://<staging-key>@<org>.ingest.sentry.io/<staging-project>" \
  POSTHOG_API_KEY="phc_<staging-key>"

# Catalog providers (optional in staging — Discogs fallback)
flyctl secrets set -a auxd-api-staging \
  DISCOGS_API_TOKEN="<staging discogs PAT>"
```

Verify:

```bash
flyctl secrets list -a auxd-api-staging
```

### 2.2 Frontend Vercel env vars

In the Vercel dashboard for project `auxd-web`, under
"Environment Variables", scope **all** of these to `Preview` only
(the `staging` branch):

| Variable | Value |
|---|---|
| `API_BACKEND_URL` | `https://auxd-api-staging.fly.dev` |
| `NEXT_PUBLIC_POSTHOG_KEY` | `phc_<staging-frontend-key>` (separate from backend's) |
| `NEXT_PUBLIC_POSTHOG_HOST` | `https://us.i.posthog.com` |
| `OG_BACKEND_URL` | `https://auxd-api-staging.fly.dev` |
| `SENTRY_DSN` | `https://<staging-key>@<org>.ingest.sentry.io/<frontend-staging-project>` |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | same as backend's `VAPID_PUBLIC_KEY` |

## 3. Initial deploy

### 3.1 Backend

```bash
# From repo root
cd apps/api
flyctl deploy -a auxd-api-staging --config fly.staging.toml --remote-only
```

`--remote-only` builds the Docker image on Fly's builder rather
than locally — avoids needing buildx + saves the m1 fan.

Verify:

```bash
flyctl status -a auxd-api-staging
flyctl logs -a auxd-api-staging --proc web
curl https://auxd-api-staging.fly.dev/healthz
# expect: {"ok": true, "version": "<short SHA>"}
```

### 3.2 Frontend

Vercel auto-builds on every push to the `staging` branch. To
trigger manually:

```bash
git push origin staging --force-with-lease   # if you've rebased
# or via Vercel CLI:
vercel --scope <your-team> --token "$VERCEL_TOKEN" --target=preview
```

Verify the preview URL responds:

```bash
curl -I https://auxd-web-staging.vercel.app
# Expect: HTTP/2 200 + x-vercel-id header
```

## 4. Workers

Both `web` and `worker` processes are defined in `fly.toml` and
share the same image. Cron jobs (T065 daily metrics ETL, T144
notification rate alert, T117 critic-seed activity scan) are
enabled in **staging** so we can verify they fire correctly.

Inspect worker logs:

```bash
flyctl logs -a auxd-api-staging --proc worker
# Expect arq worker output: "Starting worker for X tasks..."
```

If you need to disable a noisy cron temporarily in staging (e.g.,
during a load test), you can scale the worker process to 0 and
back to 1 — no code change required:

```bash
flyctl scale count worker=0 -a auxd-api-staging   # pause
flyctl scale count worker=1 -a auxd-api-staging   # resume
```

## 5. Smoke test checklist

Run after every staging deploy. Each step should take <2 min.

1. **Health probe** —
   ```bash
   curl -s https://auxd-api-staging.fly.dev/healthz | jq .
   ```
   Expect: `{"ok": true, "version": "..."}`.

2. **Frontend boot** — visit `https://auxd-web-staging.vercel.app`
   in an incognito window. Expect: redirect to `/login`.

3. **Sign-up smoke** — sign up with a fresh test account
   (`smoke_<ts>@example.com`). Expect: redirect to
   `/onboarding/step-1`. Open devtools → Application → Cookies →
   confirm `auxd_session` + `auxd_csrf` both present.

4. **Onboarding** — complete step-1 → step-2 (follow ≥3 critics
   from the seed roster) → step-3. Expect: lands on `/` with
   ≥5 critic-seed entries in the feed.

5. **Wedge log** — click the FAB → search "carrie" → pick first
   result → rate 4 stars → save. Expect: toast "logged"; entry
   visible on `/profile/<your-handle>`.

6. **Notifications** — confirm bell icon has zero-or-more badge.
   Visit `/notifications` → see at least one welcome notification
   if seeded (otherwise empty state).

7. **Push subscription** — visit any (app) page; click the
   push-bootstrap toast → grant. Then in devtools console:
   ```javascript
   navigator.serviceWorker.ready.then(r => r.pushManager.getSubscription()).then(s => console.log(!!s))
   // expect: true
   ```

8. **Email** — verify the welcome email from Resend's sandbox
   sender arrives in the test inbox. Sandbox emails route only to
   verified addresses; check the Resend dashboard.

9. **Reports CLI** — from local with prod env vars wiped:
   ```bash
   # acknowledge_report CLI runs against staging
   python -m apps.api.scripts.acknowledge_report --env staging --report-id <id>
   ```

## 6. Rollback

### 6.1 Backend (Fly)

```bash
flyctl releases list -a auxd-api-staging
# Expect a numbered list with most recent at top.
flyctl releases rollback -a auxd-api-staging <release-number>
```

Rollback is image-level; pre-existing data in Atlas + R2 is
unaffected. If a deploy ran a Beanie schema migration that's
forward-incompatible with the old image, you may need a manual
data fix. Document any forward-only migrations in
`features/001-auxd-mvp/migrations/`.

### 6.2 Frontend (Vercel)

In the Vercel dashboard for `auxd-web`:

1. Deployments → find the previous-known-good preview.
2. Click "..." → "Promote to Production" (or use the CLI:
   `vercel promote <deployment-url>`).

For a `staging` branch revert, push a `git revert <bad-sha>`
commit to the branch and let Vercel rebuild from HEAD.

## 7. Settings / code prerequisites

The backend `Settings` class (`apps/api/src/auxd_api/settings.py`)
already accepts an `ENVIRONMENT` enum value `STAGING`, so no code
changes are required for staging-specific behaviour. The
`ENVIRONMENT=staging` env var in `[env]` of `fly.staging.toml`
threads through to the cookie-secure flag, the Sentry environment
tag, and the OTel resource attribute.

If you need to add staging-only behaviour later (e.g. richer debug
logging in staging only), pattern it as:

```python
if settings.ENVIRONMENT is Environment.STAGING:
    ...
```

…and document in the relevant module.

## 8. Tear-down

If you ever need to destroy the staging environment:

```bash
flyctl apps destroy auxd-api-staging
# Atlas / Upstash / R2 — delete via their respective dashboards.
```

Note: destroying Atlas drops staging data permanently; export
before deletion if there's anything worth keeping (`mongodump`).
