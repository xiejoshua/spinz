# Notification Taxonomy: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> **Why a first-class document:** Notification firehose is the #1 documented churn driver in this niche (the Goodreads pattern: default-on alerts → user installs alerts to "see what's there" → user is overwhelmed → user uninstalls). The MVP defaults below are *deliberately quiet*.
> Related: [product-spec.md](./product-spec.md) | [user-stories.md §G3](./user-stories.md) | [data-model.md](./data-model.md)

---

## Operating principles

1. **Defaults conservative.** New users are opted INTO only what is critical for the product to function (follow notifications, weekly digest). Everything else opt-in.
2. **Three channels.** Each notification type can dispatch to: **in-app feed**, **email**, **push** (web push at MVP; native push deferred to v2). Per-type per-channel toggles.
3. **No "engagement-bait" notifications.** Never send "You haven't logged in 3 days!" or "Look what you're missing!" — those are the Goodreads anti-patterns to avoid.
4. **Digest first, real-time second.** Weekly digest is the default high-engagement surface. Real-time push only for high-signal events (follows, mentions if added).
5. **Quiet hours.** User-configurable (default off); when on, suppress push 22:00–08:00 user-local.
6. **Anti-spam guardrails.** Rate limit: ≤5 notifications/hour per user, ≤25/day. Excess are coalesced into a single "X new updates" notification.
7. **Mute the actor / mute the type / mute permanently** — every notification surface offers all three controls inline.

---

## Notification types (full enumeration)

Each row defines: identifier, trigger event, surfaces (default ON channels), recommended copy, rate-limit notes.

| ID | Type | Trigger | Default in_app | Default email | Default push | Notes |
|---|---|---|---|---|---|---|
| N-001 | `follow.new` | Someone follows you | ✅ ON | ❌ OFF | ✅ ON | Coalesced if >3/hr. Real-time. |
<!-- CR-001: field renamed from is_private_profile to private_profile (already corrected in data-model in sync-fix Run #3 L5-004; reflect here). -->
| N-002 | `follow.request_pending` | Someone requested to follow your private profile | ✅ ON | ❌ OFF | ✅ ON | Real-time. Only fires if `private_profile=true`. |
| N-003 | `follow.request_approved` | A user you requested to follow approved you | ✅ ON | ❌ OFF | ❌ OFF | Quiet — they'll see it on next app open. |
| N-004 | `review.liked` | Someone liked one of your reviews | ✅ ON | ❌ OFF | ❌ OFF | Coalesced aggressively (per-review per-day). Rename history: `review.hearted` (v1.0) → `review.auxed` (R1) → `review.liked` (R3 — Aux/Like semantic split). |
| N-005 | `review.reply` | Someone replied to your review *(v2 feature; schema reserved)* | ✅ ON | ❌ OFF | ❌ OFF | Not active at MVP. |
| N-006 | `friend.logged_album` | A close-friend (top-5 interacted) logged an album you have in your Up Next | ✅ ON | ❌ OFF | ❌ OFF | Useful! Triggers exactly once per album per friend. |
| N-007 | `friend.high_rated` | A followed user rated an album ≥4.5★ that you don't have in your diary | ❌ OFF | ❌ OFF | ❌ OFF | Deliberately OFF by default. Opt-in for power discovery users. |
<!-- CR-002: layout updated — three-hero carousel callout above the chronological body (NT-2). -->
| N-008 | `weekly.digest` | Monday 09:00 user-local, summarizing top 10 entries from follow graph past 7 days | ❌ OFF | ✅ ON | ❌ OFF | Primary engagement surface. Plain HTML email. Layout: **three-hero callout carousel at top** (most-rated, most-reviewed, most-Aux'd in your follow graph this week — see NT-2), then ~6 hero entries + 4 secondary in chronological order. |
<!-- CR-001: N-009 / N-010 / N-011 deferred to v2 — bundled with streaming-integration cluster. IDs reserved; not reassigned. Rows preserved as reserved-gap for traceability. -->
| N-009 | *(DEFERRED-TO-V2 — was `import.completed`; reserved-gap per CR-001)* | — | — | — | — | Returns with streaming + Last.fm import in v2. |
| N-010 | *(DEFERRED-TO-V2 — was `import.failed`; reserved-gap per CR-001)* | — | — | — | — | Returns with streaming + Last.fm import in v2. |
| N-011 | *(DEFERRED-TO-V2 — was `spotify.reconnect_required`; reserved-gap per CR-001)* | — | — | — | — | Returns with streaming integration in v2. |
| N-012 | `report.acknowledged` | A report you filed has been reviewed | ✅ ON | ❌ OFF | ❌ OFF | Transparency on moderation. |
| N-013 | `account.deletion_scheduled` | User scheduled account deletion | ✅ ON | ✅ ON | ❌ OFF | Confirmation + grace-period reminder. |
| N-014 | `account.deletion_reminder_7d` | 7 days before hard delete | ✅ ON | ✅ ON | ❌ OFF | "Cancel deletion?" reminder. |
| N-015 | `system.announcement` | Founder-issued product announcement | ❌ OFF | ❌ OFF | ❌ OFF | Opt-in to "auxd news" in onboarding. Use sparingly (target: ≤6/year). |
| N-016 | `security.new_session` | New device/browser login | ✅ ON | ✅ ON | ❌ OFF | Security hygiene. Always-on (cannot disable email channel). |
| N-017 | `security.password_changed` | Password changed | ✅ ON | ✅ ON | ❌ OFF | Always-on email. |
<!-- CR-001: N-018 deferred to v2 with the just-finished cluster. ID reserved; not reassigned. -->
| N-018 | *(DEFERRED-TO-V2 — was `just_finished.prompt`; reserved-gap per CR-001)* | — | — | — | — | Returns with streaming integration in v2 alongside the JustFinishedPrompt entity (US-B6). |
<!-- N-019 (list.auxed) and N-020 (list.added_to) were added in Revision #1 and removed in Revision #3 — Lists deferred to v2. IDs reserved; not reassigned. -->

---

## Defaults summary (what a new user gets)

<!-- CR-001: defaults summary updated — import status / just-finished / spotify-reconnect channels removed since the underlying types are deferred. -->
**At signup, a new user receives:**
- In-app: follow notifications, follow requests (if private), review likes, transactional/security, friend-logged-from-my-backlog
- Email: weekly digest, deletion-scheduled, security events
- Push: follow notifications, follow-request-pending

**Total recurring noise expected at MVP defaults, week one of active user:** ~3–7 notifications (one digest email + a few follow events + transactional confirmations). Lower than the v1.3 estimate because CR-001 deferred the import-status, just-finished-prompt, and reconnect channels. Well under Goodreads' 15+/week.

---

## Settings UI

Settings → Notifications page renders the table above with per-type per-channel toggles. Grouping:

```
Notifications

▸ Activity
   Follow notifications        [in-app ✓] [email ☐] [push ✓]
   Follow request pending      [in-app ✓] [email ☐] [push ✓]
   Follow request approved     [in-app ✓] [email ☐] [push ☐]
   Review likes                [in-app ✓] [email ☐] [push ☐]
   Friend logged my up-next    [in-app ✓] [email ☐] [push ☐]
   Friend high-rated discovery [in-app ☐] [email ☐] [push ☐]

<!-- CR-001: Auto-prompts section removed (deferred); Import-status + Spotify-reconnect rows removed from Account & system (deferred). -->
▸ Digests
   Weekly digest               [in-app ☐] [email ✓] [push ☐]

▸ Account & system
   auxd news                  [in-app ☐] [email ☐] [push ☐]
   Security events             [in-app ✓] [email ✓ (locked)] [push ☐]

▸ Quiet hours
   Enable quiet hours [☐]
   From [22:00] to [08:00] in [your local time]
```

Per-channel "Off all" mass toggle is offered at the top:
> **Quick controls:** [Mute all push] · [Mute all email] · [Mute all in-app]

These are reversible single-tap controls — not destructive.

---

## Email design rules

- **Plain HTML, no tracking pixels** (PostHog gets click data via UTM-tagged links).
- Subject line: actionable, not engagement-bait. ✅ `"3 friends logged albums this week"` ❌ `"You haven't been to auxd in a while 😢"`
- Preheader: real preview content, not throwaway.
- Unsubscribe link in footer, **always functional within one click** (no "are you sure" interstitial).
- "Manage all notifications" link prominent at the bottom.
- Logo small, links to settings not landing page.

---

## Push (web push at MVP)

- Use the standard browser Push API + service worker.
- Permission prompt is **not** shown at first session — too aggressive. Shown after the user's 3rd follow OR after 7 days of activity, whichever comes first.
- Each push body ≤120 chars; tap action deep-links to the source entity.
- Push notifications include their type ID in the payload so the client can suppress or coalesce if multiple arrive close together.
- Native iOS/Android push deferred to v2.

---

## Anti-patterns we are NOT shipping

| Anti-pattern | Why it's banned |
|---|---|
| "You haven't logged in N days" reminders | Goodreads/social media engagement bait; documented churn driver |
| Streak / "don't break the streak" alerts | Forced gamification documented as off-putting for casual segment (UX research §Anti-patterns) |
| Sound on push (web or native) | Casual users find unsolicited sound aggressive |
<!-- CR-002: "algorithm distrust" framing softened. We aren't anti-algorithm — we're against PUSHED recs the user didn't ask for, regardless of how they were generated. -->
| "Recommended for you" notifications | We don't push recs the user didn't ask for. The rec primitive (social-graph at MVP; richer methods in v2) belongs in surfaces the user navigated to, not unsolicited notifications. |
| Real-time "X is online now" presence | Surveillance-y; we are not a chat app |
| Cross-posted notifications (one event, three channels at once) | We pick the channel hierarchy in the table above; never dispatch all three for one event |

---

## Anti-spam guardrails (locked in Phase 5C — resolves A-003 from pre-impl-review)

- **Per-user rate limit (per-type, independent):** ≤5 in-app notifications per hour, ≤25/day **per notification type**. Each type has its own counter; e.g., follow notifications and review-like notifications consume separate buckets. Excess events still happen; they're coalesced into a single notification ("X people followed you today").
- **Per-actor rate limit (CROSS-TYPE):** Notifications from user X to user Y collapsed if >3 happen in a trailing 24-hour window — counting ACROSS all notification types from X to Y. Example: if X follows Y, then likes 3 of Y's reviews within 1 hour, the first 3 events fire individually and any subsequent X→Y notifications in the next 24h collapse into "X did several things on your reviews today".
- **Per-event dedup:** If user X follows then unfollows then follows again within 1 hour, only the latest event is surfaced.
<!-- CR-001: import-storm guardrail superseded — no import at MVP. Preserved as a v2-pending note. -->
- **Notification storms after import:** *(DEFERRED-TO-V2)* This guardrail (suppress N-001/N-007 for 24h after a fresh import) is reserved for v2 when streaming-import / Last.fm-import return. N/A at MVP.
- **Fail-mode:** If Redis is unreachable, the rate-limiter FAILS OPEN — notifications dispatch through and a Sentry alert fires with tag `notif_limiter.redis_down`. This is intentional: notifications missed during an outage are worse than notifications sent without rate-limiting during a short outage.

---

## Implementation flagged for Phase 5

- A **notification dispatcher service** (in-process at MVP; can extract to worker later) with explicit per-channel routing.
- A **dedup + coalescer** layer that runs at write time.
- A **scheduled job** for weekly digest (Monday 09:00 user-local) — needs per-user-tz handling.
- Per-channel adapters: `InAppAdapter` (writes to Notification collection), `EmailAdapter` (uses Resend — sync-fix Run #2 locked Resend over Postmark 2026-05-22 for cost), `WebPushAdapter` (uses VAPID).
- An `is_notifiable(user, type, channel)` predicate that respects preferences, quiet hours, blocks, and rate limits.

---

## Resolved decisions (Phase 3 Revision #2)

All 5 prior open questions resolved. See [decision-log.md §Notification taxonomy](./decision-log.md) for full table.

1. **NT-1 — Suppress critic-seed N-001 (follow) notifications during onboarding wave.** Otherwise every seed account gets a notification storm from new-user onboarding.
<!-- CR-002: NT-2 expanded from single hero to three-hero carousel. -->
2. **NT-2 — Weekly digest includes a three-hero carousel: most-rated, most-reviewed, and most-Aux'd albums in your follow graph this week.** Three editorial picks instead of one; stronger email-open hook. Three cheap aggregate queries (one count over followed-user entries per metric in the week). *(v1.2: single hero. v1.5/CR-002: expanded to three-hero carousel.)*
3. **NT-3 — Weekly digest fires during quiet hours.** Quiet hours suppress push and in-app prompts only; email/digest fire on their own schedule.
<!-- CR-001: NT-4 renamed to review.liked (R3 split, preserved). -->
4. **NT-4 — N-004 (review.liked) surfaces both in-app AND aggregated into weekly digest.** In-app for immediate feedback; digest aggregates for absent users.
<!-- CR-001: NT-5 superseded — import deferred. -->
5. **NT-5 — *(SUPERSEDED by CR-001 / R4)*** "Import succeeded" notification N/A at MVP because all imports are deferred. Decision returns alongside imports in v2.
