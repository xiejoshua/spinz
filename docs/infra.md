# Infra runbook — auxd

> Owner: Joshua Xie · Last updated: 2026-05-22

## Hosting topology

- **Frontend:** Vercel (`apps/web`). Domain `TBD.app`.
- **Backend:** Fly.io (`apps/api`). Domain `api.TBD.app`. Two processes: `api` (uvicorn) + `worker` (arq).
- **Database:** MongoDB Atlas M0 cluster — single region `us-west`.
- **Cache + job queue:** Upstash Redis — single region `us-west`.
- **Email:** Postmark (DKIM/SPF/DMARC on `TBD.app`).
- **Error tracking:** Sentry (cloud).
- **Product analytics:** PostHog (self-hosted single container on Fly).
- **Push notifications:** Web Push (VAPID — see below).

Each of these is provisioned in tasks T005, T006, T007.

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

- **MongoDB Atlas:** `atlas.mongodb.com` — Joshua Xie account; project `auxd`.
- **Upstash:** `console.upstash.com` — Joshua Xie account; db `auxd-cache`.
- **Fly.io:** `fly.io` — `joshua.xie` org; app `auxd-api`.
- **Vercel:** `vercel.com` — `joshua-xie` team; project `auxd-web`.
- **Postmark:** `postmarkapp.com` — server `auxd`.
- **Sentry:** `sentry.io` — org `joshua-xie`; project `auxd-api` + `auxd-web`.

> ⚠️ T005/T006/T007 are external account-provisioning tasks not yet completed
> at the time of this T008 commit. This file is the placeholder runbook; fill
> in actual account identifiers and Atlas/Upstash connection strings as those
> tasks complete.

## Backup + restore (T010a)

- **MongoDB:** nightly `mongodump --uri $MONGODB_URI --gzip --archive` to
  S3 bucket `auxd-backups-prod` (lifecycle: retain 30d, expire after).
- **Restore drill:** at least once before M0 launch, restore a backup to a
  throwaway Atlas cluster and run the validation script in
  `features/001-auxd-mvp/migrations/validation.py` against it.
- **Atlas point-in-time backup** is available at the M10+ tier; deferred
  until usage grows past M0's M0 free tier.

## Synthetic monitoring (T010)

GitHub Actions cron every 15 minutes:
- `curl https://TBD.app` (Vercel frontend)
- `curl https://api.TBD.app/healthz` (Fly backend)
- On failure → Discord webhook to founder channel.
