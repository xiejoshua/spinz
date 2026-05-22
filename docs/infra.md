# Infra runbook — auxd

> Owner: Joshua Xie · Last updated: 2026-05-22 (infra-decisions revision)

## Hosting topology

- **Frontend:** Vercel (`apps/web`). Domain `xiejoshua.com` (temporary — final product domain TBD).
- **Backend:** Fly.io (`apps/api`). Domain `api.xiejoshua.com`. Two processes (`api` + `worker`) on a single shared-cpu-1x VM to stay under the Hobby-plan $5/mo minimum.
- **Database:** MongoDB Atlas M0 cluster — region `aws-us-east-1` (matches Fly `iad` for low-latency colocation).
- **Cache + job queue:** Upstash Redis — region `us-east-1`.
- **Email:** Resend (3,000 emails/mo free tier; DKIM/SPF/DMARC on `xiejoshua.com`).
- **Error tracking:** Sentry Developer plan (5K errors/mo free).
- **Product analytics:** PostHog Cloud (US region — 1M events/mo, 1yr retention, free tier).
- **Push notifications:** Web Push (VAPID — see below).
- **Backups:** Cloudflare R2 (10 GB storage free, S3-compatible API).
- **DNS / domain:** Cloudflare (registrar + DNS).

Each of these is provisioned in tasks T005, T006, T007 (with T010a covering R2 backups).

### Why these picks (cost minimization)

Total realistic monthly cost: **$5/mo (Fly Hobby only)**. Every other dependency lands on a free tier sized appropriately for M0 closed-beta scale.

| Component | Choice | Free-tier shape | Upgrade trigger |
|-----------|--------|------------------|-----------------|
| Compute (backend) | Fly.io Hobby | $5/mo includes ~168 hrs shared-cpu-1x | Add memory or scale out when p95 hits ceilings |
| Database | Atlas M0 | 512 MB storage, shared CPU | Upgrade to M10 (~$57/mo) at ~80% storage or when needing point-in-time backup |
| Cache + queue | Upstash free | 10k commands/day, 256 MB | Upgrade when daily commands exceed 8k (estimate via PostHog event volume) |
| Frontend | Vercel Hobby | 100 GB bandwidth, unlimited static | Upgrade to Pro ($20/mo) when bandwidth or function-invocation limits hit |
| Email | Resend free | 3k emails/mo | Upgrade to Pro ($20/mo for 50k) — expect this around 500 active users |
| Analytics | PostHog Cloud free | 1M events/mo, 1yr retention | Upgrade at >1M (paid scales linearly; ~$0.0003/event after free) |
| Errors | Sentry Developer | 5k errors/mo, 1 user | Upgrade to Team ($26/mo) when team grows or error volume scales |
| Backups | R2 free | 10 GB storage + 1M Class A ops | Storage costs at $0.015/GB-mo after free; expect ~$0/mo through M3 |

Prior plan had self-hosted PostHog on Fly (~$40/mo for the 4 GB RAM PostHog needs) and Postmark email ($15/mo). Those were swapped 2026-05-22 to Cloud + Resend respectively, dropping projected MVP run-rate from ~$60/mo to **$5/mo**.

## VAPID keys (T008)

Generated 2026-05-22 via `cryptography.hazmat.primitives.asymmetric.ec` (P-256).

- **Public key** (browser-readable; safe to commit): see `apps/web/.env.example`
  `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.
- **Private key** (server-only; never commit): store as the Fly secret
  `VAPID_PRIVATE_KEY` via `fly secrets set VAPID_PRIVATE_KEY=...`.
  Current value tracked outside the repo in the project password manager
  under `auxd / vapid_private_key (2026-05-22)`.

### Rotation procedure

VAPID keys do not expire but should rotate annually or on any suspected
compromise. To rotate:

```bash
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
import base64
priv = ec.generate_private_key(ec.SECP256R1())
n = priv.public_key().public_numbers()
priv_b = priv.private_numbers().private_value.to_bytes(32, 'big')
pub_b = b'\x04' + n.x.to_bytes(32,'big') + n.y.to_bytes(32,'big')
b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip('=')
print('PRIVATE:', b(priv_b))
print('PUBLIC :', b(pub_b))
"
```

Then:

1. Update `apps/web/.env.example` + Vercel env var `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.
2. `fly secrets set VAPID_PRIVATE_KEY=... -a auxd-api`.
3. Force-resubscribe all existing push subscriptions on next user open
   (they will silently fail on backend until they re-subscribe with the
   new public key — `lib/observability` will catch the count divergence).

## Account credentials

- **MongoDB Atlas:** `atlas.mongodb.com` — Joshua Xie account; project `auxd`; cluster region `us-east-1` (AWS).
- **Upstash:** `console.upstash.com` — Joshua Xie account; db `auxd-cache`; region `us-east-1`.
- **Cloudflare:** `dash.cloudflare.com` — Joshua Xie account; domain `xiejoshua.com` registered; R2 bucket `auxd-backups`.
- **Fly.io:** `fly.io` — `joshua.xie` org; app `auxd-api`; region `iad` (Ashburn, VA).
- **Vercel:** `vercel.com` — `joshua-xie` team; project `auxd-web`.
- **Resend:** `resend.com` — Joshua Xie account; sending domain `xiejoshua.com`.
- **PostHog Cloud:** `us.posthog.com` — Joshua Xie account; project `auxd`; ingest host `https://us.i.posthog.com`.
- **Sentry:** `sentry.io` — `joshua-xie` org; projects `auxd-api` + `auxd-web`.

> Account-provisioning status as of 2026-05-22: Atlas ✓, Upstash ✓, PostHog Cloud ✓, Cloudflare (DNS + R2 bucket) ✓. **Still pending:** Sentry signup, Resend signup + domain verification, Fly.io signup + billing, Vercel signup.

## Secrets to set on Fly (`fly secrets set`)

| Secret | Source | Required at |
|--------|--------|-------------|
| `MONGODB_URI` | Atlas → Connect → Connect application | T012 (Beanie connection) |
| `REDIS_URL` | Upstash → Database → Connect | T013 (Redis client) |
| `SESSION_HMAC_KEY` | `openssl rand -base64 32` | T019 (session middleware) |
| `TOKEN_ENCRYPTION_KEY` | `openssl rand -base64 32` | T017 (already in libs) |
| `SPOTIFY_CLIENT_ID` | Spotify Developer Dashboard | T002 (Spotify quota app) |
| `SPOTIFY_CLIENT_SECRET` | Spotify Developer Dashboard | T002 |
| `RESEND_API_KEY` | Resend → API Keys → Create | T135 (email adapter) |
| `SENTRY_DSN` | Sentry → Project → Settings → Client Keys | T015 (already coded) |
| `POSTHOG_API_KEY` | PostHog → Project Settings → Project API Key | T015 (already coded) |
| `VAPID_PUBLIC_KEY` | `apps/web/.env.example` (already committed) | T008 done |
| `VAPID_PRIVATE_KEY` | Generated 2026-05-22; password manager | T008 done; needs Fly to receive |
| `R2_ACCESS_KEY_ID` | Cloudflare → R2 → API Tokens → Create | T010a (backups) |
| `R2_SECRET_ACCESS_KEY` | Same flow as above | T010a |
| `R2_ENDPOINT_URL` | Cloudflare → R2 bucket → Settings → S3 API | T010a |
| `R2_BUCKET_NAME` | Defaults to `auxd-backups`; override only if different | T010a |

## DNS setup (Cloudflare → `xiejoshua.com`)

| Record | Type | Target | Cloudflare proxy |
|--------|------|--------|------------------|
| `xiejoshua.com` (apex) | A | Vercel-assigned IP | OFF (Vercel manages SSL) |
| `xiejoshua.com` (apex) | AAAA | Vercel-assigned IPv6 | OFF |
| `api.xiejoshua.com` | CNAME | `<app>.fly.dev` (printed by `fly certs add`) | OFF (Fly manages SSL) |
| `_acme-challenge.api.xiejoshua.com` | CNAME | Fly-printed validation target | OFF |
| SPF | TXT | `v=spf1 include:_spf.resend.com ~all` | n/a |
| DKIM | TXT | Resend-printed selectors (`resend._domainkey`) | n/a |
| DMARC | TXT | `v=DMARC1; p=quarantine; rua=mailto:dmarc@xiejoshua.com` | n/a |

When the final product domain is decided, re-point these records — code uses `NEXT_PUBLIC_API_URL` and `RESEND_API_KEY` (configurable domain via Resend dashboard), so the swap is config-only with no code changes.

## Backup + restore (T010a)

- **MongoDB:** nightly `mongodump --uri $MONGODB_URI --gzip --archive` piped to Cloudflare R2 bucket `auxd-backups` via S3-compatible API (boto3 or rclone). Lifecycle: retain 30 days, expire after.
- **R2 endpoint:** `https://<account_id>.r2.cloudflarestorage.com/auxd-backups`. Use the four `R2_*` secrets listed above.
- **Restore drill:** at least once before M0 launch, restore a backup to a
  throwaway Atlas cluster and run the validation script in
  `features/001-auxd-mvp/migrations/validation.py` against it.
- **Atlas point-in-time backup** is available at the M10+ tier; deferred
  until usage grows past M0's M0 free tier.
- **Free-tier headroom:** R2 free tier covers 10 GB storage + 1M Class A ops/mo. A 100 MB compressed mongodump (estimate for ~200k diary entries + albums) × 30 daily snapshots = ~3 GB. Won't hit the wall through M3.

## Synthetic monitoring (T010)

GitHub Actions cron every 15 minutes:
- `curl https://xiejoshua.com` (Vercel frontend)
- `curl https://api.xiejoshua.com/healthz` (Fly backend)
- On failure → Discord webhook to founder channel.
