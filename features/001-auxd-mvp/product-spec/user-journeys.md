# User Journeys: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> Personas: Casey (primary), Maya (engaged), Jamie (tastemaker)
> Related: [product-spec.md](./product-spec.md) | [user-stories.md](./user-stories.md) | [wireframes/](./wireframes/index.html)

Five primary journeys. Steps are *user perspective* — what the user does, what they see, what they feel. System internals reference user-stories by ID.

---

## Journey 1: First-time onboarding (Casey)

> Entry point: xiejoshua.com landing page. Exit point: home feed populated, ≥1 album logged. Target completion time: **<3 minutes**.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Lands on `xiejoshua.com` from a friend's invite link | Shows: "Casey invited you to auxd" hero + Casey's 5 recent ratings + "Get started with Spotify" big button | 😊 curious | Social proof primes commitment |
| 2 | Taps "Get started with Spotify" | Redirects to Spotify OAuth consent page | 😐 mild friction | OAuth screen owned by Spotify; we explain scopes in our pre-screen tooltip |
| 3 | Approves Spotify scopes | Redirects back to auxd with auth code; exchange for tokens; account auto-created using Spotify display name and email | 😊 quick | Auto-create account avoids form-filling tax |
| 4 | Sees "Pulling your last 30 days…" screen | Background: import job runs, fetches recently-played, dedupes to ~30 albums, caches metadata | 😊 anticipation | Progress: "Found 28 albums…" |
| 5 | Sees "Confirm your last 30 days" with top 5 albums as cards | Top 5 ranked by play count or recency; ½-star rating widget per card | 😊 engaged | This is the activation hook — they're already invested |
| 6 | ½-stars 3 of 5 albums, skips 2 | Ratings save optimistically; UI advances immediately | 😊 in control | No required field; user is never blocked |
| 7 | Sees "Follow 3 to fill your feed" | Shows 6 critic-seed cards + 4 mutual-taste suggestions (based on just-imported listens) | 😊 curious | Each card: avatar, name, "writes about indie hip-hop" tagline, 3 recent rating samples |
| 8 | Follows 4 accounts (1 mutual-taste, 3 critics) | Follow records created; suggestion job re-runs to update remaining suggestions | 😊 anticipatory | Each follow has a 200ms haptic on mobile |
| 9 | Taps "Done" | Lands on home feed | 😊 satisfied | Feed already populated with critic-seed activity from past 7 days |
| 10 | Scrolls feed, taps an album rated 5★ by a critic | Album detail page opens (SSR'd) | 😊 engaged | Critic review prominent; "Friends" section empty; "Add to Up Next" button visible |
| 11 | Adds album to Up Next | Toast: "Added to Up Next"; counter increments | 😊 productive | First moment of personal-curation behavior |

**Alternative path: User skips Spotify connect** *(revised in Revision #1 — skippable, no degraded-mode framing)*

| Step | Diverge from | What happens |
|---|---|---|
| 2a | At the Spotify auth screen | User taps the prominent **Skip — connect later** link (no shame, no "limited features" framing) → skips steps 3 & 4 of import flow |
| 3a | After skip | User goes directly to "Follow 3 to fill your feed" with critic-seed-only suggestions (mutual-taste suggestions are empty since we have no taste signal yet) |
| 4a | After follow step | User lands on home feed (populated by critic-seed activity from past 7 days); all features work: manual log, reviews, backlog, auxes |
| Later | From Settings → Integrations | User can connect Spotify any time; the same 30-day auto-import then back-fills the diary |

**Drop-off risk points:**
- Step 2 — Spotify OAuth consent screen (cannot be helped — owned by Spotify; mitigate with pre-screen "we only request read access" tooltip)
- Step 7 — "Follow 3" minimum is 1; users who skip with "Continue" land on a feed that's mostly critic-seed content
- Step 9 — empty feed is a worst-case if the user only followed seed critics with no recent activity; pad with last-7-day critic activity

**Journey metric goals:**
- Time-to-first-rating (steps 1–6): median **<90 seconds**
- Time-to-first-follow (steps 1–8): median **<120 seconds**
- Time-to-feed-with-≥5-entries (steps 1–9): median **<150 seconds**
- Drop-off between step 1 (landing) and step 9 (feed): target **<30%**

---

## Journey 1.5: Just-finished auto-prompt (Casey, Spotify-connected, returning) *(added in Revision #1)*

> Entry point: Casey finishes an album on Spotify and either opens auxd within ~15 minutes OR has auto-prompt push enabled. Exit point: diary entry created from the prompt. Target: ≥30% of Spotify-connected sessions trigger an auto-prompt log within 3 months of connect.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Casey finishes "GNX" on Spotify | auxd background polling detects finished album within 5–15 min via Spotify recently-played | (background) | Polling cadence: 5 min while user has active app session in last 24h, 15 min otherwise |
| 2 | Casey opens auxd (or push lands if opted-in) | A `JustFinishedPrompt` is in `pending` state; the home feed renders a hero prompt card at the top: "Just listened to GNX — log it?" with primary "Log" CTA and secondary "Not now" + "⋮ menu" | 😊 mild surprise | Hero prompt is dismissable via swipe-up or "Not now" |
| 3 | Casey taps "Log" | Log sheet opens with album prefilled; same path as Journey 2 | 😊 fast | <8 second commit follows |
| 4 | Casey rates + commits | DiaryEntry created with `source: spotify_just_finished_prompt`; the `JustFinishedPrompt` state → `logged` with the entry id; the prompt disappears | 😊 done |

**Alternative paths:**
- 3a — Casey taps "Not now" → prompt dismisses; same album won't re-prompt for 30 days
- 3b — Casey taps "⋮ menu" → options: "Don't prompt me for this album", "Disable auto-prompts", "Settings"
- 3c — Casey is in quiet hours (e.g., overnight) → prompt is queued, surfaces next open outside quiet hours
- 3d — Casey has `auto_prompt_enabled=false` → no prompt ever appears, even if detection fires

**Drop-off risk points:**
- Push fatigue if `auto_prompt_push_enabled=true` and the user finishes many albums (mitigation: push rate limit + coalescing — at most 1 push/day for auto-prompts)
- "Stale" prompts if user opens app days after finishing (mitigation: prompts expire after 24h)
- Privacy concern: user might feel watched. Mitigation: "Disable auto-prompts" is one-tap from the prompt itself, not buried in settings.

**Journey metric goals:**
- % of Spotify-connected sessions with active prompt: **>40%** (signal that detection is firing meaningfully)
- Log-through-rate on prompts (Log tap vs Not now): **>25%** at M3, **>40%** at M6
- % of users who disable auto-prompts in first 30 days: **<15%** (privacy escape hatch is functioning but not the norm)

---

## Journey 2: Log an album in <8 seconds (Casey, returning user)

> Entry point: user finishes an album on Spotify. Exit point: diary entry created. Target completion time: **<8 seconds from intent to commit**.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens auxd (app already running or pinned tab) | App resumes on last surface (or home if cold-start) | 😊 |
| 2 | Taps the persistent "+" Log button (top-right or FAB) | Bottom sheet slides up; album search prefilled with most recent Spotify listen ("Black Star — Mos Def & Talib Kweli (1998)") | 😊 fast | Prefill is the magic — saves 4–5 seconds |
| 3 | Confirms the prefill is correct (it is) | Album card highlights; rating row + Aux row (🏅) + review row appear | 😐 focused | If prefill is wrong, user types to search |
| 4 | Taps 4 ½-stars | Rating displays "4 ★ ★ ★ ★ ☆" with a faint half-star indicator if applicable | 😊 commit | Single tap to commit; rolling thumb on mobile changes value |
| 5 | Skips review, taps "Log" | Entry saves, sheet dismisses, toast: "Logged — see in your diary" with link | 😊 done |
| (T=<8s end-to-end measured from step 2 to step 5) |

**Alternative path: Adding a review**

| 4a | Taps "Add a review" inline after rating | Review textarea expands; soft keyboard appears on mobile |
| 5a | Types a 2-sentence review, taps "Log" | Entry + Review save; toast shows |
| (T=<25s end-to-end including writing) |

**Alternative path: Manually searching (no Spotify prefill or Spotify off)**

| 2b | Bottom sheet opens with no prefill | Empty search field with autocomplete |
| 3b | Types "kendrick gnx" | Search results appear (Atlas Search + Spotify search merged), debounced 200ms |
| 4b | Taps the right album | Album card highlights, same rating/Aux/review rows appear |
| 5b–7b | (continues as 4–5 above) |

**Drop-off risk points:**
- Step 2 prefill is wrong (user listened to a different album last, or used Spotify on another device) → friction
- Step 3 album not in catalog (rare) → "Report missing album" surface
- Step 4 user wants a 3.5★ but only finds integer-star widget → must explicitly support half-star (½-star drag)

**Journey metric goals:**
- Time-from-log-button-to-commit: **median <8s** (without review), **median <25s** (with review)
- % of logs where prefill is accepted: **>40%** (high prefill accuracy is a wedge ingredient)

---

## Journey 3: Discover via the social graph (Casey)

> Entry point: open auxd home tab. Exit point: user opens Spotify to listen to an album they discovered. Target conversion: 1 in 4 sessions ends in an outbound Spotify play.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens home tab | Feed loads (SSR or client-cache): reverse-chrono with weight boosts; ~10 hero entries + lazy-load more on scroll | 😊 |
| 2 | Sees a 5★ rating with a 50-word review from Jamie (a critic Casey follows) for an album Casey doesn't know | Entry card shows: Jamie avatar, "Jamie rated ★★★★★ • 2h ago", album cover thumb, review snippet, 👍 Like action (FR-031) | 😊 intrigued |
| 3 | Taps the album cover | Album detail page opens (SSR, fast) | 😊 curious | Page shows cover, metadata, tracklist, friends-who-rated, public reviews |
| 4 | Sees that 2 other people Casey follows also rated this album 4★+ | "Friends" section shows 3 avatars + their ratings | 😊 validated | Social proof from inside the trusted graph |
| 5 | Reads Jamie's full review | Review expands inline | 😊 engaged | Spends 30–90 seconds reading |
| 6 | Taps "Listen on Spotify" | Opens `spotify:album:{id}` deep-link → Spotify app/web opens at album | 😊 completes | This is the social-originated-play metric event (M3 target 25%) |
| (User listens to album on Spotify, returns to auxd to log later) |

**Alternative path: Add to Up Next instead of listening immediately**

| 6a | Taps "Add to Up Next" instead | Toast confirms; backlog grows | 😊 deferred |
| (User comes back days later; logged-from-backlog flow takes over) |

**Drop-off risk points:**
- Step 1 — empty/sparse feed (mitigation: critic-seed padding)
- Step 2 — feed entries look like spam if too many in quick succession from the same user (mitigation: rate-limit per-user fan-out, coalesce visually)
- Step 6 — Spotify deep-link fails (e.g., not installed on mobile) → fall through to web player

**Journey metric goals:**
- Sessions with ≥1 album opened: **>50% of all sessions**
- Sessions ending in `Listen on Spotify` outbound: **>25% (M3) / >40% (M6)** — this is the social-originated play rate KPI
- Average dwell time on album detail when discovered via feed: **30–90 seconds** (long enough to read a review, short enough not to be stuck)

---

## Journey 4: Maintain backlog (Casey)

> Entry point: user is curious "what should I play next?" Exit point: they queue something. Target: backlog drives **>30% of logged plays** by M6.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens "Up Next" tab on bottom nav | Backlog list renders, user-defined order (default: newest-added first) | 😊 |
| 2 | Scrolls through 8 albums in queue | Each item: cover thumb, title/artist, "added 3 days ago" timestamp, "by Jamie via review" attribution if added from feed | 😊 reflective |
| 3 | Sees an album they're in the mood for, taps it | Album detail page opens | 😊 |
| 4 | Reviews the album page briefly, taps "Listen on Spotify" | Spotify deep-link opens | 😊 |
| 5 | Later, after listening, returns to auxd | (Some hours/days later) |
| 6 | Logs the album via Log button | Diary entry created; if `keep_backlog_after_log=false` (default), album auto-removed from backlog with toast "Removed from Up Next" | 😊 satisfying loop |

**Alternative path: Manually pruning the backlog**

| Step | Variation |
|---|---|
| 2a | User long-presses an item → context menu: "Remove from Up Next", "Listen on Spotify", "Open album" |
| 3a | User taps Remove → confirmation toast, item disappears |

**Drop-off risk points:**
- Step 1 — empty backlog for new users (mitigation: first-week onboarding tip to add 3 albums)
- Step 6 — user didn't realize album was auto-removed; toast must be visible & undoable

**Journey metric goals:**
- % of users with ≥3 backlog items at D7: **>60%**
- % of MAU-logged-plays that came via backlog: **>30% by M6**

---

<!-- Journey 4.5 (Create and share a curated List) was added in R1 and removed in R3.
     Lists deferred to v2 — see out-of-scope.md and decision-log.md row 7.
     Journey content preserved in git history (R1 = v1.1). -->

## Journey 5: Write and share a long-form review (Maya / Jamie)

> Entry point: Maya / Jamie just finished an album they want to write about. Exit point: review published; ideally shared externally. Target: ≥10% of week-active users publish a review per week by M6.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens auxd, taps "+" Log | Bottom sheet opens with prefilled album (or Maya searches) | 😊 |
| 2 | Confirms album, rates 4½★ | Rating commits | 😐 deliberate |
| 3 | Taps "Add a review" | Textarea expands; full editor surface | 😊 |
| 4 | Writes 200-word review with line breaks and one emphasis | Save state: draft autosaved every 5s | 😊 in flow |
| 5 | Reviews own draft, taps "Log" | Entry + Review committed; sheet dismisses to toast: "Review posted to your diary" with a "Share" CTA | 😊 done |
| 6 | Taps "Share" CTA in toast | OS share sheet opens with prefilled URL (`xiejoshua.com/r/{review_id}`) and OG image preview | 😊 amplifies |
| 7 | Shares to Twitter/X or copies link | External post happens; OG card renders cover + rating + review snippet | 😊 reach |

**Drop-off risk points:**
- Step 3 → 5: Review interrupted by app background / network drop → autosave is critical
- Step 6 → 7: OG image generation fails → share card looks broken on Twitter → no one clicks (mitigation: pre-render OG image at write time, not on demand)

**Journey metric goals:**
- Median review length (Must-Have + Should-Have, excluding ratings-only): **80–250 words**
- % of users who write ≥1 review in their first 14 days: **>15%** (this is the "engaged listener" activation signal)
- Reviews shared externally: **>20%** of published reviews tracked via share-sheet event (event fires when user actually taps share, even if we can't confirm publication)

---

## Cross-journey notes

- **All journeys must stay <3 minutes for first-time use** — this is the casual-user friction floor.
- **Every journey ends in either (a) a logged diary entry, (b) a backlog item, (c) an outbound Spotify play, or (d) a share event.** If a journey ends in scroll-and-leave, that's a failed journey.
- **Empty states matter** in every journey — research §State Inventory called out 22 distinct states; the most-failing journeys are those where step 1 hits an empty state without a meaningful CTA.
- **Aux (🏅) and Like (👍) are distinct concepts** — Aux is the entry-owner's "this is one of my standouts" personal signal on their own DiaryEntry; Like is other users' social engagement on a Review. Different verbs, different icons, different objects. *(Semantic split locked in Revision #3.)*

---

## Resolved decisions (Phase 3 Revision #2)

All 5 prior open questions resolved. See [decision-log.md §User journeys](./decision-log.md) for full table.

1. **UJ-1 — Log sheet prefilled album = most-recently-finished album** (not last-played track). Track-level prefill triggers on background music or skips; album-level is the actual log moment.
2. **UJ-2 — "Follow 3" card order: mixed, but always ≥3 critics in top 6 visible cards.** Critic-first reads too editorial; pure-mixed dilutes seeding.
3. **UJ-3 — Review expanded inline at MVP** (no dedicated reading view). Most reviews are short; inline keeps the feed in-flow.
4. **UJ-4 — Reviews share-card only at MVP** (no API cross-post to Twitter/X). Cross-post APIs are deprecating; share-card with OG preview is portable and platform-risk-free.
5. **UJ-5 — No "Reading list" surface at MVP.** Up Next is for albums only.
