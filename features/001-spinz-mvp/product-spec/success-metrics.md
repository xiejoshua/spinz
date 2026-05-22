# Success Metrics: Spinz MVP

> Feature: `001-spinz-mvp` | Phase: 2 | Date: 2026-05-21
> Source: [research/metrics-roi.md](../research/metrics-roi.md) — full benchmark deep-dive
> Related: [product-spec.md](./product-spec.md) | [decision-log.md](./decision-log.md)

## North Star

**Weekly Active Loggers (WAL)** — unique users who logged ≥1 album AND opened the app in trailing 7 days.

**Why this metric:** matches the cadence at which casual listeners finish albums (1–4/week), gates against the Last.fm "scrobbles continue but nobody opens the app" failure mode, and aligns directly with the wedge (logging is the core activity).

## KPI Table

| Metric | Definition | M3 target | M6 target | Measurement |
|---|---|---|---|---|
| **WAL (North Star)** | Unique users logged ≥1 album AND opened app, trailing 7d | 500 | 2,500 | PostHog cohort query, daily rollup |
| **W1 activation rate** | New signups who log ≥3 albums in their first week | 30% | 35% | PostHog funnel, cohort attribution |
| **D30 retention** | Day-30 retention of weekly cohort | 8% | 12% | PostHog retention chart |
| **Social-originated play rate** | % of `Listen on Spotify` events triggered from feed or friend-discovery surface (vs profile or search) | 25% | 40% | Event source attribution |
| **Reviews per WAL** | Average reviews published per weekly active logger | 0.5 | 0.8 | Review count / WAL |
| **Follow graph density** | Median # of follows per WAL | 5 | 12 | Per-cohort, snapshot weekly |
| **Backlog → Log conversion** | % of backlog items that get logged within 30 days of being added | 30% | 45% | Event chain query |

## Leading Indicators

Watched daily during launch and weekly thereafter; these surface trouble 2–4 weeks before the North Star moves.

- **Onboarding completion rate** (steps 1 → land on home feed): target >70%
- **Time-to-first-rating** (median): target <90 sec
- **Time-to-first-follow** (median): target <120 sec
- **Drop-off at Spotify OAuth consent**: target <25% (outside our control but signal of value clarity)
- **D1 returnvisit rate**: target >40%
- **% of new users who follow ≥1 critic seed during onboarding**: target >80%

## Health / Guardrail Metrics

These must not regress; an alert fires if any cross a threshold.

| Guardrail | Threshold | Rationale |
|---|---|---|
| p95 home feed load | <500ms | Above this, perceived quality drops |
| p95 album detail load | <400ms | SSR critical for sharing |
| Spotify API error rate | <2% per 5m window | Above this, degraded experience surfaces |
| Notification rate per user per week | <12 (excluding digest) | Above this, churn risk per Goodreads pattern |
| Report → resolution time | median <72h | Moderation hygiene |
| Account deletion rate | <1% MAU per month | Above this, dissatisfaction signal |

## Anti-metrics (what failure looks like)

These signals indicate the product isn't working — even if WAL is climbing.

| Anti-metric | Signal |
|---|---|
| WAL climbs but D30 stagnates | Acquisition-driven growth without product fit |
| Reviews/WAL <0.2 | Logs are happening but engagement is shallow ("zombie scrobbling") |
| Social-originated play rate <15% by M3 | The social-graph thesis (H2) is failing; rec strategy broken |
| Follow graph density median <3 | Cold-start seeding strategy failed; product is islands of one |
| Notification settings dramatically opt-out (>40% of users disable in-app notifications) | Notification taxonomy is wrong; firehose problem |
| % users connecting Spotify drops below 50% | OAuth UX broken or trust gap |

## Measurement Plan

| Cadence | What we check |
|---|---|
| **Day 0 (launch)** | Smoke metrics: signups/hour, OAuth completion rate, first-log conversion. Alarms on Spotify API errors. |
| **Day 1** | First retention cohort baseline. Founder reads the first 50 user-written reviews qualitatively. |
| **Day 7** | First W1 activation cohort. Drop-off step analysis. Onboarding funnel review. |
| **Day 14** | First D14 cohort returns. Initial qualitative interviews (5 users). |
| **Day 30 (M1)** | First D30 cohort returns. Full funnel + anti-metric review. Decide go/iterate/pivot. |
| **Month 3 (M3)** | KPI gate: WAL ≥500? If <250, pivot meeting. |
| **Month 6 (M6)** | KPI gate: WAL ≥2,500? Plus 15 qualitative interviews to validate H1. |

## Reporting

- **Daily**: Auto-generated email digest of signups, WAL, OAuth errors, p95 latency. Distributed to founder.
- **Weekly**: Cohort report (PostHog-generated); reviewed every Monday.
- **Monthly**: Investor-grade + retention deep-dive. Compared against M3/M6 plan.
- **Quarterly**: Full retro + pivot decision if metrics are off-trajectory.

## Notes from research

Benchmarks compared against:
- **Letterboxd**: 6 yrs → 1M; 12 yrs → 10M; ~5% paid conversion at maturity; $50–60M valuation (Mar 2023).
- **Last.fm at peak**: 70M signups on frictionless scrobbling; proves auto-import primitive scales.
- **Strava** (proxy): users with ≥5 follows retain ~3–4× longer at D90.
- **Goodreads** (cautionary): notification firehose drove documented churn; explicit anti-pattern.

Spinz's targets are **deliberately set below Letterboxd's mature numbers** because (a) we're a portfolio/side-project, not a venture-backed effort, and (b) Spotify is already paying for the underlying job — switching cost is real.
