# Performance Audit — spec.md §6.1 NFR Measurement (T172)

> Last reviewed: 2026-05-23 (Session 26).
> Tools: k6 (backend load), playwright-lighthouse (frontend audits).
> Spec target: spec.md §6.1 NFR Measurement Contract.

## Thresholds (spec.md §6.1)

| Surface | p95 | p99 | Source |
|---|---|---|---|
| Home feed load (`GET /` page) | <500ms | — | spec.md §6.1 |
| Album detail load (`GET /album/*`) | <400ms | — | spec.md §6.1 |
| Catalog API error rate | <2% / 5-min window | — | spec.md §6.1 |
| Uptime | ≥99.5% / month | — | spec.md §6.1 |
| Notification rate per user | <12/week (trailing 7d p95) | — | spec.md §6.1 |
| Report → resolution time | median <72h | — | spec.md §6.1 |

Derived backend-only budgets (subtract React + asset load from the
end-to-end budget):

| Backend endpoint | p95 budget | Rationale |
|---|---|---|
| `/healthz` | <500ms (p99 <1000ms) | Platform plumbing sanity — DB-free path |
| `/api/v1/feed?mode=for_you` | <300ms | leaves 200ms for React + assets on a 500ms end-to-end budget |
| `/api/v1/notifications/unread-count` | <400ms | high-poll endpoint (120/min/session); MongoDB single-doc fetch |
| `/api/v1/search` | <400ms | leaves headroom inside the 8s wedge p95 (TC-E2E-003) |
| `/api/v1/diary` (wedge commit) | <500ms backend (8s end-to-end p95 — see TC-E2E-003) | Already guarded by `apps/api/tests/integration/test_log_perf.py` |
| Home feed (backend) | <2500ms in mongomock | Already guarded by `apps/api/tests/perf/test_feed_perf.py` |

## Backend k6 scripts

Installed via Homebrew: `brew install k6`. Each script lives in
`apps/api/tests/perf/k6_*.js` and is operator-driven (NOT CI).

### Baseline — /healthz

```bash
k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
       apps/api/tests/perf/k6_baseline.js
```

50 VUs ramping → sustained 60s → ramp-down. Thresholds:
- `http_req_duration p(95) < 500ms, p(99) < 1000ms`
- `http_req_failed rate < 0.01`

### Unread count poll (highest-traffic endpoint)

```bash
k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
       --env SESSION_COOKIE='auxd_session=...' \
       apps/api/tests/perf/k6_unread_count.js
```

100 VUs, 0.5s sleep (matches real client polling at 120/min). Thresholds:
- `http_req_duration p(95) < 400ms, p(99) < 800ms`
- `http_req_failed rate < 0.01`

### Home feed read

```bash
k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
       --env SESSION_COOKIE='auxd_session=...' \
       apps/api/tests/perf/k6_feed_home.js
```

30 VUs, 2s think-time (matches real feed read cadence). Thresholds:
- `http_req_duration p(95) < 300ms, p(99) < 700ms`
- `http_req_failed rate < 0.01`

Requires the staging test account to follow ≥50 followees with ≥10
diary entries each — the critic-seed roster (T117) provides this if
the operator runs `apps/api/scripts/follow_all_critics.py` against the
test account on the staging DB.

### Search

```bash
k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
       apps/api/tests/perf/k6_search.js
```

20 VUs, mix of "daft punk", "carrie", "rachmaninoff", "asdfqwerty"
queries (last one tests the empty-result path). Thresholds:
- `http_req_duration p(95) < 400ms, p(99) < 1000ms`
- `http_req_failed rate < 0.02` (search tolerates 2% blips — live
  MusicBrainz fallback timeouts count against it).

### Lifting a session cookie

For staging only — do not share production cookies.

1. Open Chrome devtools on the signed-in staging app.
2. Application → Cookies → `auxd_session` → copy the full
   `name=value` pair (the entire string).
3. Pass via `--env SESSION_COOKIE='auxd_session=<value>'`.

## Frontend Lighthouse audits

Run via Playwright + `playwright-lighthouse`. NOT in CI (Chromium
remote-debug interferes with the regular Playwright fixture).

```bash
cd apps/web
# Set up a logged-in dev server first:
E2E_BACKEND_REACHABLE=true PLAYWRIGHT_BASE_URL=https://auxd-staging.vercel.app \
  pnpm exec playwright test tests/perf/lighthouse.spec.ts --project=chromium
```

Audits four screens:
- `/` (home feed)
- `/album/[id]` (album detail)
- `/up-next` (backlog UI)
- `/notifications` (bell + dropdown)

Thresholds (from `tests/perf/lighthouse.spec.ts`):

| Category | Threshold |
|---|---|
| Performance | ≥80 |
| Accessibility | ≥90 (overlaps with T171 axe-core gate) |
| Best Practices | ≥90 |

## CI guardrail (in-process)

These two pytest specs DO run in CI and provide an early-warning
signal for backend perf regressions:

- `apps/api/tests/integration/test_log_perf.py` (T084) — wedge
  commit time p95 <1500ms over 10 trials in mongomock (proxy for the
  8s end-to-end target — spec.md §6.1, TC-E2E-003).
- `apps/api/tests/perf/test_feed_perf.py` (T107) — home feed read
  p95 <2500ms over 10 trials with 500 followees × 10 entries seed.

Both run against mongomock-motor (sorted-list backend), so the
budgets are intentionally generous — they catch order-of-magnitude
regressions, not micro-perf.

## Pre-staging gaps

The end-to-end NFRs (page-view durations from PostHog, uptime,
catalog error rate) can only be measured against a deployed app:

- **p95 home feed load (spec.md §6.1, `<500ms`)** — N/A pending T175
  staging deploy; first measurement comes from PostHog
  `pageview.duration_ms` after 7 days of usage.
- **p95 album detail load (`<400ms`)** — same.
- **Catalog API error rate (`<2% / 5-min window`)** — N/A pending
  staging; backend trace counter `catalog.api.4xx + 5xx / total`
  is wired (T088, T093) but only emits real data once live.
- **Uptime (`≥99.5% monthly`)** — N/A pending staging deploy +
  Sentry availability monitor + Fly synthetic check.

These get re-measured at T+72h in the launch runbook (`docs/launch.md`).

## Known follow-ups

- 🟡 Lighthouse mobile profile not yet run — `playwright-lighthouse`
  defaults to desktop. Add `settings: { formFactor: 'mobile' }` to
  the audit config once `playwright-lighthouse` ≥5.0 lands (current
  4.x doesn't pass settings through cleanly).
- 🟡 No k6 cloud run wired — could ship to Grafana k6 Cloud for
  long-running soak tests later. MVP runs locally against staging
  only.
- 🟡 Push-notification fan-out (T136 dispatcher) not load-tested —
  the dispatcher uses an in-memory queue; under burst we may want
  to migrate to a Redis-backed queue. Out of scope for MVP launch;
  documented in plan §17 follow-ups.
