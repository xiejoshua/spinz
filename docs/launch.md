# M0 Launch Ceremony Runbook (T180)

> Last reviewed: 2026-05-23 (Session 26).
> Phase: §18 hardening complete; pre-launch checklist (T179) signed off.
> Owner: Joshua Xie (founder = operator = on-call at MVP).
> Communication channel: founder's own Discord workspace
> (`#auxd-launch` for self-observability + the production
> `#auxd-moderation` for moderation flags).

## TL;DR timeline

Times are anchored to **T0 = first public signup window open**.

| Marker | Action | Owner |
|---|---|---|
| T-72h | Final staging smoke; checklist gate | Founder |
| T-24h | Critic-seed roster activated; on-call schedule confirmed | Founder |
| T-1h | Pre-flight: `/healthz`, Sentry clean, dashboards refreshing | Founder |
| T0 | Announce; wave-1 invites sent | Founder |
| T+15min | First-signup smoke | Founder |
| T+1h | Onboarding funnel review (≥10 signups) | Founder |
| T+6h | Notification firehose dashboard check | Founder |
| T+24h | Day-1 retention check + Sentry triage | Founder |
| T+72h | Launch-window close; M0→M1 decision | Founder |

## T-72h: final staging smoke + checklist gate

1. **Pre-launch checklist (T179) green?** All gates marked ✅ in
   `docs/launch-checklist.md §1-§9`. Any 🟡 follow-ups documented.
   ⚠️ pre-launch operator actions §10 either done or scheduled.

2. **Staging smoke** — full §5 walkthrough from `docs/staging.md`:
   /healthz ✓, signup ✓, onboarding ✓, wedge ✓, notifications ✓,
   push subscription ✓, email arrival ✓, reports CLI ✓.

3. **Founder on-call schedule confirmed.** Block the next 72h
   continuous on the calendar; have the phone notifications dialed
   in for the moderation Discord channel + Sentry email + Resend
   webhook callbacks.

4. **Backup verification.** Confirm `mongodump` ran in the last 24h
   on production (`.github/workflows/backup-mongo.yml`).

5. **Rollback plan rehearsed.** Mental walkthrough of
   `docs/launch-checklist.md §9`: which `flyctl releases rollback`
   command to fire, where Vercel's "Promote to Production" sits.

## T-24h: critic-seed activation + final dashboards

1. **Critic-seed roster activated** via `docs/critic-seed-runbook.md`:
   ```bash
   cd apps/api
   uv run python -m apps.api.scripts.seed_critics --env production --roster docs/critic-seed-runbook.md
   ```
   Verify each critic has logged ≥3 seed reviews + diary entries
   (per the agreement in the runbook). If any critic is missing,
   either nudge them or backfill with the founder's own account
   while flagging that for cleanup at T+72h.

2. **Notification monitoring dashboards refreshed.** Open the
   PostHog dashboards from `docs/closed-beta-runbook.md §3` in
   browser tabs and pin them. Confirm they're populating with the
   staging data so any unexpected blank panel surfaces NOW (not at
   T+1h).

3. **Staging → prod data parity check.** Spot-check on production:
   - `User` count matches expected (critic accounts only at this point)
   - `CriticSeed` collection has the roster
   - No `Report` open older than 72h (should be 0)
   - `NotificationCounter` collection initialized for every existing user

4. **Founder DM channels staged.** Inbox cleared, push notifications
   on, the founder's own Slack/Discord workspaces ready to receive
   wave-1 reactions.

## T-1h: pre-flight checks

1. **`/healthz`** — `curl https://api.xiejoshua.com/healthz` → 200
   `{"ok": true, "version": "..."}`. Version should match the SHA
   from the last green deploy in
   `.github/workflows/deploy-api.yml`.

2. **Sentry** — open the project for `auxd-api-prod`; trailing 1h
   shows 0 NEW issues (RESOLVED or otherwise-acknowledged items are
   fine).

3. **PostHog ingestion** — confirm a manual test event from a
   founder devtools session arrives in PostHog within 60s.

4. **Frontend production** — `curl -I https://xiejoshua.com` → 200
   with `x-vercel-id` header set.

5. **Workers** — `flyctl logs -a auxd-api --proc worker` shows the
   arq event loop active.

## T0: announce + first wave

1. **Send wave-1 invites.** Use the template from
   `docs/closed-beta-runbook.md §1.3`. Send in batches of 10 over
   30 minutes so the founder can monitor the funnel as people
   arrive (don't fire all 30 at once).

2. **Set the launch flag.** At MVP there is no `signup_enabled`
   feature flag — the app is already live. T0 is simply the
   "announce" moment. (If a future iteration wires a flag, this is
   where it flips on; track that addition as a v1.x candidate.)

3. **Log the moment.** Record the timestamp + initial state in
   the personal launch journal (Notion / Obsidian / wherever).

## T+15min: first-signup smoke

1. **Watch PostHog Live Events.** Expect to see
   `signup.completed` events in real time.

2. **Cross-check the first signup.** Pick a critic-seed invitee
   you know is going to test first; verify in PostHog Person
   profile they:
   - Reached `/onboarding/step-3`
   - Followed ≥3 critics
   - Their `signup.completed` event has correctly tagged
     `signup_source=closed_beta`

3. **Verify the welcome email landed.** Check Resend dashboard
   for the delivery status of the welcome email to that invitee.

## T+1h: onboarding funnel review

By now ~10 signups should have arrived. Open the onboarding
funnel dashboard (`docs/closed-beta-runbook.md §3.1`):

- **Signup → step-2 conversion** — expect ≥90%
- **Step-2 → critics-followed conversion** — expect ≥85%
- **Critics-followed → step-3 conversion** — expect ≥90%
- **Step-3 → home-feed-loaded conversion** — expect ≥95%

If any step is dropping below threshold:
- ≥20% drop at any step → DM 1-2 affected users immediately for
  qualitative reason ("what happened? what confused you?")
- ≥40% drop → consider pausing further invites until cause
  identified

Sentry → 0 NEW CRITICAL issues. Any 5xx visible? Triage.

## T+6h: notification firehose check

The Goodreads-firehose-guard NFR (spec.md §6.1 — p95 < 12
notifications/user/week) is the load-bearing post-launch metric.
Open the dashboard from `docs/closed-beta-runbook.md §3.4`:

- p95 trending under 12/user/week
- No T144 alert fired in the trailing 6h
- Per-channel breakdown looks healthy (no single channel at 80%
  of total — would suggest a coalescer bug)

If alert fired:
- Inspect `notifications.dispatched` event payload to identify
  the offending notification type (N-001, N-002, …).
- Cross-reference with `coalescer.py` rules for that type.
- Temporary mitigation: scale worker process to 0 with
  `flyctl scale count worker=0 -a auxd-api`, fix in a hotfix,
  re-deploy, scale back.

## T+24h: retention + Sentry sweep

1. **Day-1 retention check.** PostHog Retention insight: expect
   ≥80% of T0 signups to have at least one event within the
   trailing 24h.

2. **Sentry triage.** Open Sentry → Issues → trailing 24h.
   Any NEW CRITICAL issue gets a hotfix today. NEW HIGH issues
   get triaged into "fix in next 48h" or "fix before M1". MEDIUM
   and below get added to the open follow-up list.

3. **Reports review.** Any `report.created` events in PostHog?
   For each, run `acknowledge_report.py` and write the
   resolution note in the moderation log.

4. **Smoke against production.** Repeat the §5 smoke from
   `docs/staging.md`, but on production with a throwaway test
   account.

## T+72h: launch-window close + decision gate

### Acceptance criteria (all must be true)

- [ ] No P0 (data loss, auth break, crash loop) bugs open
- [ ] ≥50% of wave-1 invitees onboarded (`onboarding.step_3_completed`)
- [ ] Notification rate p95 ≤12/user/week
- [ ] Week-1 retention trend on track for ≥50% projection
- [ ] No moderation report unresolved >24h
- [ ] No recurring CRITICAL Sentry issue in trailing 24h
- [ ] Founder personally tested all 9 active TC-E2E scenarios on production

### Decision

- **GREEN — open M1**: distribute the broader invite list (≤500
  invitees). Update `docs/closed-beta-runbook.md` with M1
  parameters.
- **YELLOW — extend M0 by 72h**: identify the failing criterion;
  push a fix; reassess at T+144h.
- **RED — hold + investigate**: pause new invites; founder full
  attention to root cause; schedule a "what went wrong"
  retrospective.

### Schedule next

If GREEN, schedule:
- M1 invite distribution (T+96h)
- Product-Forge retrospective (T+14d) — run
  `/speckit-product-forge-retrospective` against
  `features/001-auxd-mvp/research/metrics-roi.md` predictions to
  close the loop.

## Who-owns-what at M0

At MVP the founder owns everything. Specifically:

| Role | Responsibility | Person |
|---|---|---|
| Engineering on-call | Backend / frontend / infra fixes | Joshua Xie |
| Moderation | Acknowledge reports, suspension decisions | Joshua Xie |
| Customer support | DM responses, user nudges | Joshua Xie |
| Product analytics | PostHog dashboard reading | Joshua Xie |
| Comms | Wave-1 invite outreach, status posts | Joshua Xie |
| Security incident response | Per `docs/security-review.md` | Joshua Xie |

This concentrates risk — keep wave-1 size at ≤30 invitees and the
on-call window at 72h continuous so the load is humanly manageable.

## Rollback trigger conditions

Initiate rollback (per `docs/launch-checklist.md §9`) if ANY of:

- 5xx rate exceeds 1% sustained for >5 minutes (not a single blip).
- Any data-loss bug confirmed (e.g., diary entries vanishing).
- Auth break that locks ALL users out (test on a fresh incognito).
- An exploitable critical security finding surfaces post-launch
  (e.g., session-cookie tampering accepted by HMAC).

Recovery target: ≤30 min to roll back, communicate via
wave-1 DMs ("we're rolling back to investigate; back soon"), and
post-mortem within 24h.

---

**Sign-off:** by completing this runbook end-to-end without
deviation, the founder formally certifies M0 launched cleanly.
