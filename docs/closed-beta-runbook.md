# Closed-Beta Wave Runbook (T176)

> Last reviewed: 2026-05-23 (Session 26).
> Purpose: pre-launch wave-1 invite playbook — who to invite, how to
> invite, what to watch, when to advance to public M0.
> Audience: founder (operator role at MVP).

## TL;DR

- Target wave size: **≤30 invitees** (critic-seed roster + close friends).
- Mechanism: founder shares the public signup URL directly via email/DM.
  No invite-code system at MVP.
- Onboarding-completed target: **≥80% within 48h**.
- Beta-exit criteria: ≥80% onboarded + week-1 retention ≥50% + no P0
  bugs at 72h. If green: open M0 (T180).

## 1. Invite list curation

### 1.1 Roster shape

Keep the list in a private spreadsheet (Google Sheets recommended;
not committed to the repo). Suggested columns:

| Column | Type | Notes |
|---|---|---|
| handle_suggestion | string (lowercase, ≤24 chars) | rough handle suggestion; final pick is the invitee's |
| real_name | string | for outreach personalisation only |
| contact | email or DM channel | how you reach them |
| role | enum: `critic`, `friend`, `internal` | feeds the "who has the most signal" filter |
| invite_status | enum: `pending`, `invited`, `onboarded`, `active`, `lapsed`, `bounced` | lifecycle |
| invited_at | ISO 8601 date | for invitee-to-onboard latency analysis |
| onboarded_at | ISO 8601 date | first wedge-log timestamp from PostHog |
| notes | string | conversation hooks, e.g. "loves Mount Eerie, hates being asked to opt into anything" |

### 1.2 Wave-1 composition (≤30 invitees)

| Bucket | Target count | Source |
|---|---|---|
| Critic-seed roster | up to 10 | `apps/api/scripts/seed_critics.py` roster — folks who agreed to be visible on the leaderboard and to log a few entries per week |
| Close-friend founder circle | up to 15 | personal network with a music habit |
| Internal QA | 2-3 | the operator's secondary accounts on different devices (one iOS, one Android-Chrome) |
| Spare | ~5 | held back for early lapsers' replacements at T+48h |

### 1.3 Outreach template

```
Subject: auxd beta — would you like to be one of the first 30?

Hey <name>,

I've been building auxd for the past few months — it's a private,
social album-tracking site (think Letterboxd but for music). I'd
love your honest reactions during a small closed beta this week.

What you'd do:
  - Sign up at https://xiejoshua.com (≤5 min)
  - Follow at least 3 of the listed critics on step-2
  - Log a couple of albums via the FAB
  - Optionally write a review
  - Tell me what felt off

What I'll do:
  - Be on-call for the next 72h for any breakage
  - Read every report you file
  - Ship fixes within 24h for anything sharp

There's no invite code; the link goes to a regular signup page.
I'll be watching the dashboards for who signs up so I know it's
you.

— Josh
```

Send in batches of 10 over 3 days so you can react to volume.

## 2. Invite mechanism

No invite-code system at MVP. The signup page is public; the
operator distributes the URL by hand.

**Rationale:** an invite-code mechanism is a real feature (code
generation, single-use, expiry, redemption analytics) and the MVP
guardrail is "if you didn't get a personal email/DM from Josh,
you're not in the wave". With ≤30 known invitees and PostHog
person-property tagging, the founder can see exactly who has
signed up versus not. If wave-1 escalates into uncontrolled spread
(rare at this size), the founder can flip the signup-route feature
flag (TODO: track as a v1.x candidate — see plan §17 follow-ups).

If invite-code becomes necessary in v1.x:

- Plan a `InviteCode` Beanie model (code, generated_at, used_at,
  used_by_user_id, max_uses).
- Wire a `POST /api/v1/auth/redeem-invite` endpoint behind a feature
  flag.
- Update the signup form to require the code.

## 3. Early-signal monitoring (PostHog dashboards)

Bookmark these PostHog dashboards before sending invites (created
from `posthog_dashboard.yml` if present, or build manually from the
listed events):

### 3.1 Onboarding funnel

Steps (in order):

1. `signup.completed`
2. `onboarding.step_2_loaded`
3. `onboarding.critics_followed` (count ≥3 per user)
4. `onboarding.step_3_loaded`
5. `wedge.log_committed` (first log within 24h of signup)
6. `social.follow_created` (any follow beyond seed roster within 7d)

Track conversion at each step. Watch for big drop-offs (e.g.
step-2 critics-followed <80% suggests the critic-seed roster needs
clearer copy or better avatars; check `docs/critic-seed-runbook.md`).

### 3.2 Retention cohort by week-of-signup

PostHog Retention insight, grouped by `signed_up_week`. Targets:

- Day-1 retention: ≥80%
- Week-1 retention: ≥50%
- Week-2 retention: ≥40%

### 3.3 Push opt-in rate

```
push.permission_granted / push.prompt_shown
```

Target: ≥40% on iOS PWA, ≥50% on desktop Chrome (lower iOS bar
because Apple's permission UI is the gatekeeper, not us).

### 3.4 Notification rate per user per week

**Load-bearing Goodreads-firehose guard.** Spec.md §6.1 sets the
threshold at p95 < 12 notifications/user/week. The backend cron
job (T144) alerts via Discord webhook when p95 exceeds 12 across a
trailing 7-day window. The dashboard surfaces:

- p50 / p95 / p99 of `notifications.dispatched` per user per week
- a stacked bar by channel (in-app, email, push) — to see if one
  channel is screaming.

### 3.5 Wedge time

`wedge.log_committed.duration_ms`. Target: p95 < 8s end-to-end
(spec.md §6.1). Already guarded in-process by
`apps/api/tests/integration/test_log_perf.py` at 1500ms (the
mongomock budget is more generous than real Atlas, see test
docstring). The real-world p95 surfaces only after deploy.

### 3.6 Critic-seed activity

`reviews.created.by_role[critic]` + `diary.log.by_role[critic]`
weekly. Critics that go silent for ≥7 days get a personal nudge
DM from the founder (the social-pact part of the critic-seed
arrangement, see `docs/critic-seed-runbook.md`).

## 4. What we're watching for (red flags)

These need IMMEDIATE founder attention (notify in the founder's
own Slack/Discord, escalate within the hour).

| Signal | Threshold | Trigger | Action |
|---|---|---|---|
| Churn within first 24h | >20% of invitees sign up but don't log a single entry within 24h | per-user inspection via PostHog person profile | DM the user, ask what stopped them |
| Support volume (founder DM inbox) | >5 distinct users complaining within 6h | manual count | freeze further invites; triage |
| p95 wedge time | >8s sustained 1h | PostHog dashboard 3.5 | check backend Fly logs for slow MongoDB queries |
| Notification firehose alert | T144 cron fires once | Discord webhook | inspect coalescer logs; force a Notification cooldown via worker pause if needed |
| Any 5xx rate | >0.5% trailing 5min | Sentry → Issues | usually a single bad cookie; check `session.invalid_cookie` event |
| Any reports filed within 72h | ≥1 | `reports.created` event + Discord moderation webhook | review within 4h per the `acknowledge_report` flow |

## 5. Beta exit criteria

Decision happens at **T+72h after first invite sent**. Open M0 (T180)
when ALL of these are green:

- [ ] ≥80% of invitees have completed onboarding (
      `onboarding.step_3_completed` event count ≥ 0.8 × invitees).
- [ ] Week-1 retention ≥50% on the wave-1 cohort.
- [ ] No P0 (data loss, auth break, crash loop) bugs open.
- [ ] Notification rate p95 ≤12/user/week.
- [ ] No moderation reports unresolved >24h.
- [ ] Sentry: no recurring CRITICAL issue in the trailing 24h.

If any of the above is red, defer M0 and run a fix loop (track in
implementation-log under "wave-1 follow-ups"). Re-evaluate at
T+96h.

## 6. After exit

When green:

1. Run T180 launch ceremony (`docs/launch.md`).
2. Open signup to the wider invite list (≤500 invitees in M1 if
   the M0 wave holds).
3. Schedule a retrospective (`speckit-product-forge-retrospective`)
   at T+14d against `research/metrics-roi.md` predictions.
