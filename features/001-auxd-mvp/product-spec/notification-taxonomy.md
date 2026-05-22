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
| N-002 | `follow.request_pending` | Someone requested to follow your private profile | ✅ ON | ❌ OFF | ✅ ON | Real-time. Only fires if `is_private_profile=true`. |
| N-003 | `follow.request_approved` | A user you requested to follow approved you | ✅ ON | ❌ OFF | ❌ OFF | Quiet — they'll see it on next app open. |
| N-004 | `review.liked` | Someone liked one of your reviews | ✅ ON | ❌ OFF | ❌ OFF | Coalesced aggressively (per-review per-day). Rename history: `review.hearted` (v1.0) → `review.awarded` (R1) → `review.liked` (R3 — Award/Like semantic split). |
| N-005 | `review.reply` | Someone replied to your review *(v2 feature; schema reserved)* | ✅ ON | ❌ OFF | ❌ OFF | Not active at MVP. |
| N-006 | `friend.logged_album` | A close-friend (top-5 interacted) logged an album you have in your Up Next | ✅ ON | ❌ OFF | ❌ OFF | Useful! Triggers exactly once per album per friend. |
| N-007 | `friend.high_rated` | A followed user rated an album ≥4.5★ that you don't have in your diary | ❌ OFF | ❌ OFF | ❌ OFF | Deliberately OFF by default. Opt-in for power discovery users. |
| N-008 | `weekly.digest` | Monday 09:00 user-local, summarizing top 10 entries from follow graph past 7 days | ❌ OFF | ✅ ON | ❌ OFF | Primary engagement surface. Plain HTML email, ~6 hero entries + 4 secondary. |
| N-009 | `import.completed` | Spotify or Last.fm import job finished | ✅ ON | ❌ OFF | ❌ OFF | Transactional — confirms work done. |
| N-010 | `import.failed` | Spotify or Last.fm import errored / partial | ✅ ON | ✅ ON | ❌ OFF | Transactional + email so user can recover. |
| N-011 | `spotify.reconnect_required` | OAuth token revoked or expired and refresh failed | ✅ ON | ✅ ON | ✅ ON | Transactional; must be high-visibility, product is degraded. |
| N-012 | `report.acknowledged` | A report you filed has been reviewed | ✅ ON | ❌ OFF | ❌ OFF | Transparency on moderation. |
| N-013 | `account.deletion_scheduled` | User scheduled account deletion | ✅ ON | ✅ ON | ❌ OFF | Confirmation + grace-period reminder. |
| N-014 | `account.deletion_reminder_7d` | 7 days before hard delete | ✅ ON | ✅ ON | ❌ OFF | "Cancel deletion?" reminder. |
| N-015 | `system.announcement` | Founder-issued product announcement | ❌ OFF | ❌ OFF | ❌ OFF | Opt-in to "auxd news" in onboarding. Use sparingly (target: ≤6/year). |
| N-016 | `security.new_session` | New device/browser login | ✅ ON | ✅ ON | ❌ OFF | Security hygiene. Always-on (cannot disable email channel). |
| N-017 | `security.password_changed` | Password changed | ✅ ON | ✅ ON | ❌ OFF | Always-on email. |
| N-018 | `just_finished.prompt` | Spotify detected a finished album; prompt user to log it | ✅ ON | ❌ OFF | ❌ OFF | Added in Revision #1 (auto-prompt elevated to MVP). In-app default ON; push default OFF (opt-in). Respects `User.auto_prompt_enabled` and quiet hours. Coalesced — only the latest unacted album is surfaced per user. |
<!-- N-019 (list.awarded) and N-020 (list.added_to) were added in Revision #1 and removed in Revision #3 — Lists deferred to v2. IDs reserved; not reassigned. -->

---

## Defaults summary (what a new user gets)

**At signup, a new user receives:**
- In-app: follow notifications, follow requests (if private), review likes, import status, just-finished prompts (when Spotify connected), transactional/security, friend-logged-from-my-backlog
- Email: weekly digest, import-failed alert, deletion-scheduled, security events
- Push: follow notifications, follow-request-pending, spotify-reconnect-required

**Total recurring noise expected at MVP defaults, week one of active user:** ~5–10 notifications (one digest email + a few follow events + a handful of just-finished prompts from connected Spotify users + transactional confirmations). Slightly lower after Revision #3 removed list-related notifications. Still well under Goodreads' 15+/week.

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

▸ Auto-prompts (when Spotify connected)
   Just-finished prompt        [in-app ✓] [email ☐] [push ☐]
   Quiet hours apply [✓]

▸ Digests
   Weekly digest               [in-app ☐] [email ✓] [push ☐]

▸ Account & system
   Import status               [in-app ✓] [email partial] [push ☐]
   Spotify reconnect needed    [in-app ✓] [email ✓] [push ✓]
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
| "Recommended for you" notifications | Algorithm-distrust; our rec philosophy is social-graph, not pushed |
| Real-time "X is online now" presence | Surveillance-y; we are not a chat app |
| Cross-posted notifications (one event, three channels at once) | We pick the channel hierarchy in the table above; never dispatch all three for one event |

---

## Anti-spam guardrails (locked in Phase 5C — resolves A-003 from pre-impl-review)

- **Per-user rate limit (per-type, independent):** ≤5 in-app notifications per hour, ≤25/day **per notification type**. Each type has its own counter; e.g., follow notifications and review-like notifications consume separate buckets. Excess events still happen; they're coalesced into a single notification ("X people followed you today").
- **Per-actor rate limit (CROSS-TYPE):** Notifications from user X to user Y collapsed if >3 happen in a trailing 24-hour window — counting ACROSS all notification types from X to Y. Example: if X follows Y, then likes 3 of Y's reviews within 1 hour, the first 3 events fire individually and any subsequent X→Y notifications in the next 24h collapse into "X did several things on your reviews today".
- **Per-event dedup:** If user X follows then unfollows then follows again within 1 hour, only the latest event is surfaced.
- **Notification storms after import:** Suppress N-001/N-007 for 24h after a fresh Spotify-import; otherwise a follower's import would spam everyone in their graph.
- **Fail-mode:** If Redis is unreachable, the rate-limiter FAILS OPEN — notifications dispatch through and a Sentry alert fires with tag `notif_limiter.redis_down`. This is intentional: notifications missed during an outage are worse than notifications sent without rate-limiting during a short outage.

---

## Implementation flagged for Phase 5

- A **notification dispatcher service** (in-process at MVP; can extract to worker later) with explicit per-channel routing.
- A **dedup + coalescer** layer that runs at write time.
- A **scheduled job** for weekly digest (Monday 09:00 user-local) — needs per-user-tz handling.
- Per-channel adapters: `InAppAdapter` (writes to Notification collection), `EmailAdapter` (uses Postmark or Resend), `WebPushAdapter` (uses VAPID).
- An `is_notifiable(user, type, channel)` predicate that respects preferences, quiet hours, blocks, and rate limits.

---

## Resolved decisions (Phase 3 Revision #2)

All 5 prior open questions resolved. See [decision-log.md §Notification taxonomy](./decision-log.md) for full table.

1. **NT-1 — Suppress critic-seed N-001 (follow) notifications during onboarding wave.** Otherwise every seed account gets a notification storm from new-user onboarding.
2. **NT-2 — Weekly digest includes "most-rated album in your follow graph this week" hero entry.** Single hero entry; cheap query; editorial feel.
3. **NT-3 — Weekly digest fires during quiet hours.** Quiet hours suppress push and in-app prompts only; email/digest fire on their own schedule.
4. **NT-4 — N-004 (review.awarded) surfaces both in-app AND aggregated into weekly digest.** In-app for immediate feedback; digest aggregates for absent users.
5. **NT-5 — "Import succeeded" notification fires every time** (not just first time). Users re-trigger imports; want explicit confirmation.
