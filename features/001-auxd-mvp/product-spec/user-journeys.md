# User Journeys: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> Personas: Casey (primary), Maya (engaged), Jamie (tastemaker)
> Related: [product-spec.md](./product-spec.md) | [user-stories.md](./user-stories.md) | [wireframes/](./wireframes/index.html)

Five primary journeys. Steps are *user perspective* — what the user does, what they see, what they feel. System internals reference user-stories by ID.

---

<!-- CR-001: Journey 1 rewritten end-to-end. No streaming-OAuth step; manual onboarding only. Target time tightened because the streaming-auth round-trip is gone. -->
## Journey 1: First-time onboarding (Casey)

> Entry point: xiejoshua.com landing page. Exit point: home feed populated with critic-seed activity; user has logged ≥1 album manually OR added one to Up Next. Target completion time: **<2 minutes** (tighter than the prior <3min target because there is no streaming-auth round-trip).

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Lands on `xiejoshua.com` from a friend's invite link | Shows: "Casey invited you to auxd" hero + Casey's 5 recent ratings + "Sign up" big button | 😊 curious | Social proof primes commitment |
| 2 | Taps "Sign up" | Single-screen form: email + password + handle, with inline handle availability check | 😐 mild friction | Form is the only friction; ~20–40 seconds |
| 3 | Submits valid signup | Account created; advances to handle-confirmation toast then directly to "Follow ≥3 critics" | 😊 quick | No streaming auth, no import wait |
| 4 | Sees "Follow ≥3 critics to fill your feed" | Shows up to 10 critic-seed cards, pre-checked by default (per Q13) | 😊 curious | Each card: avatar, name, "writes about indie hip-hop" tagline, 3 recent rating samples |
| 5 | Untickes 2 critics whose taste isn't theirs; keeps 6 ticked | Live count: "6 critics selected" | 😊 in control | Default-tick + free unticking is the proven middle (Q13) |
| 6 | Taps "Continue" | Follow records created; user lands on home feed | 😊 anticipatory | Each follow has a 200ms haptic on mobile |
| 7 | Sees home feed populated with critic-seed activity from past 7 days | Feed renders SSR-fast | 😊 satisfied | Critic-seed feed is load-bearing for first-session content |
| 8 | Scrolls feed, taps an album rated 5★ by a critic | Album detail page opens (SSR'd) | 😊 engaged | Critic review prominent; "Friends" section empty (no follows that overlap yet); "Add to Up Next" + "Log" CTAs visible |
| 9 | Adds album to Up Next OR taps "Log" and uses manual search | Toast confirms; backlog or diary updates | 😊 productive | First moment of personal-curation behavior |

**Drop-off risk points:**
- Step 2 — signup form. Mitigate with social-proof copy + a "why do you need my email?" tooltip explaining we only use it for transactional + digest mail.
- Step 4 — "Follow ≥3 critics" minimum of 3 (raised from 1 because there is no streaming taste signal to fall back to). Users who try to tap Continue with <3 selected see a soft modal explaining the minimum.
- Step 7 — empty feed is a worst-case if the user only followed seed critics with no recent activity; pad with broader-roster last-14-day critic activity.

**Journey metric goals:**
- Time-to-first-follow (steps 1–6): median **<60 seconds**
- Time-to-feed-with-≥5-entries (steps 1–7): median **<75 seconds**
- Time-to-first-log-OR-backlog (steps 1–9): median **<3 minutes**
- Drop-off between step 1 (landing) and step 7 (feed): target **<25%**

---

<!-- CR-001: Journey 1.5 marked DEFERRED-TO-V2 — body preserved as a frozen snapshot; nothing in the MVP wires it. -->
## Journey 1.5: *(DEFERRED-TO-V2)* Just-finished auto-prompt

**Status:** DEFERRED-TO-V2 (CR-001 / R4, 2026-05-22). Originally added in Revision #1. Returns in v2 alongside the streaming-integration cluster. The frozen happy-path/drop-off-mitigations/metric-goals content is preserved in git history at v1.3; deliberately not re-displayed here to keep the MVP user-journeys surface honest.

> Re-activation trigger: see [out-of-scope.md](./out-of-scope.md) row for streaming integration.

---

<!-- CR-001: Journey 2 rewritten — manual search is now the only logging path; no streaming prefill. -->
## Journey 2: Log an album via manual search in <8 seconds (Casey, returning user)

> Entry point: user wants to record an album they just finished listening to. Exit point: diary entry created. Target completion time: **<8 seconds from intent to commit** (measured for cached/popular albums; first-time queries that require Discogs cold-fetch may add 200–500ms).

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens auxd (app already running or pinned tab) | App resumes on last surface (or home if cold-start) | 😊 |
| 2 | Taps the persistent "+" Log button (top-right or FAB) | Bottom sheet slides up; empty album-search field focused, soft keyboard up on mobile | 😊 fast | Empty-state is the Letterboxd norm — users know what they want to log |
| 3 | Types "kendrick gnx" | Autocomplete suggests results from Atlas Search (cached MusicBrainz subset), debounced 200ms; if no in-cache hits, a "Searching catalog…" inline indicator appears while Discogs is queried | 😐 focused | Most popular albums are in cache; long-tail albums see a brief cold-fetch |
| 4 | Taps the right album result | Album card highlights; rating row + Aux row (🏅) + review row appear | 😊 commit |
| 5 | Taps 4 ½-stars | Rating displays "4 ★ ★ ★ ★ ☆" with a faint half-star indicator if applicable | 😊 |
| 6 | Skips review, taps "Log" | Entry saves, sheet dismisses, toast: "Logged — see in your diary" with link | 😊 done |
| (T ≤ 8s end-to-end measured from step 2 to step 6, for cached/popular albums) |

**Alternative path: Adding a review**

| 5a | Taps "Add a review" inline after rating | Review textarea expands; soft keyboard appears on mobile |
| 6a | Types a 2-sentence review, taps "Log" | Entry + Review save; toast shows |
| (T ≤ 25s end-to-end including writing) |

**Alternative path: Cold-fetch (album not in MusicBrainz cache)**

| 3b | Types a niche album title | "Searching catalog…" inline indicator appears; system queries MusicBrainz; if no MusicBrainz hit, Discogs is queried |
| 4b | Album appears with a "(new to auxd)" badge | User taps; on commit, the album record is created as a candidate with MBID reconciliation deferred |

**Drop-off risk points:**
- Step 3 — user can't type the album name fast enough → autocomplete must surface near-matches aggressively (typo tolerance)
- Step 3 — album not in catalog (cold-fetch fails on both MusicBrainz and Discogs) → "Report missing album" surface
- Step 5 — user wants a 3.5★ but only finds integer-star widget → must explicitly support half-star (½-star drag)

**Journey metric goals:**
- Time-from-log-button-to-commit: **median <8s** (without review, cached album), **median <25s** (with review)
- Catalog hit rate (% of searches that match within Atlas Search cache, no Discogs cold-fetch needed): **>90%** at M3, **>95%** at M6 (see [success-metrics.md](./success-metrics.md) — this metric replaces the prior streaming-prefill-accepted metric)

---

<!-- CR-001: Journey 3 rewritten — no outbound streaming deep-link at MVP; conversion measured as "Add to Up Next" or "Log it now" instead. -->
## Journey 3: Discover via the social graph (Casey)

> Entry point: open auxd home tab. Exit point: user takes a discovery action — either adds the album to Up Next or logs it immediately. Target conversion: 1 in 4 sessions ends in a discovery action (Up Next add or log).

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens home tab | Feed loads (SSR or client-cache): reverse-chrono with weight boosts; ~10 hero entries + lazy-load more on scroll | 😊 |
<!-- CR-002: feed preview format and nav target updated for UJ-3 (dedicated /review/:id route). -->
| 2 | Sees a 5★ rating from Jamie (a critic Casey follows) for an album Casey doesn't know | Entry card shows: Jamie avatar, "Jamie rated ★★★★★ • 2h ago", album cover thumb (via Cover Art Archive), first ~80 chars of the review as preview, 👍 Like action (FR-031). The whole card is tappable — there is no inline-expand chevron at MVP. | 😊 intrigued |
| 3 | Taps the album cover thumb | Album detail page opens (SSR, fast) | 😊 curious | Page shows cover, metadata, tracklist, friends-who-rated, public reviews |
| 4 | Sees that 2 other people Casey follows also rated this album 4★+ | "Friends" section shows 3 avatars + their ratings | 😊 validated | Social proof from inside the trusted graph |
<!-- CR-002: review reading is now a nav to /review/:id, not an inline expand. -->
| 5 | Returns to the feed and taps Jamie's review preview text | Navigates to `/review/:id` reading view: full hero (album cover, title, artist, viewer's rating context if any, Aux badge, Like button, share), Jamie's full review body | 😊 engaged | Spends 30–90 seconds reading. Page is URL-shareable (OG meta enabled). v2 will add screenshot image-gen on this surface (UJ-4 v2). |
| 6 | Taps "Add to Up Next" OR taps "Log" if they're going to listen right now | Toast confirms; backlog grows OR diary entry is created via manual-log flow | 😊 completes | This is the social-originated-discovery metric event (M3 target 25%) |
| (User listens to album outside auxd via whatever streaming service they use; returns to auxd to log if they didn't already) |

**Alternative path: Log immediately**

| 6a | Taps "Log" on the album detail page | Bottom-sheet Log flow opens with the album prefilled | 😊 productive |
| 7a | Rates + commits (optional review) | Diary entry created; toast confirms | 😊 done |

**Drop-off risk points:**
- Step 1 — empty/sparse feed (mitigation: critic-seed padding)
- Step 2 — feed entries look like spam if too many in quick succession from the same user (mitigation: rate-limit per-user fan-out, coalesce visually)
- Step 6 — outbound streaming play is not measurable at MVP because there is no integration; users will play albums in whichever app they prefer

**Journey metric goals:**
- Sessions with ≥1 album opened: **>50% of all sessions**
- Sessions ending in `Add to Up Next` OR `Log` action on a discovered album: **>25% (M3) / >40% (M6)** — this is the social-originated-discovery rate KPI (replaces the prior social-originated-play KPI which depended on streaming deep-links)
- Average dwell time on album detail when discovered via feed: **30–90 seconds** (long enough to read a review, short enough not to be stuck)

---

## Journey 4: Maintain backlog (Casey)

> Entry point: user is curious "what should I play next?" Exit point: they queue something. Target: backlog drives **>30% of logged plays** by M6.

| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
<!-- CR-001: Journey 4 — no streaming deep-link at MVP. Flow now ends with the user playing the album outside auxd via their own streaming service. -->
| 1 | Opens "Up Next" tab on bottom nav | Backlog list renders, user-defined order (default: newest-added first) | 😊 |
| 2 | Scrolls through 8 albums in queue | Each item: cover thumb, title/artist, "added 3 days ago" timestamp, "by Jamie via review" attribution if added from feed | 😊 reflective |
| 3 | Sees an album they're in the mood for, taps it | Album detail page opens | 😊 |
| 4 | Reviews the album page briefly, decides to listen to it | (User leaves auxd to play the album in their streaming service of choice; auxd does not currently surface outbound streaming deep-links — that returns in v2.) | 😊 |
| 5 | Later, after listening, returns to auxd | (Some hours/days later) |
| 6 | Logs the album via Log button | Diary entry created; if `keep_backlog_after_log=false` (default), album auto-removed from backlog with toast "Removed from Up Next" | 😊 satisfying loop |

**Alternative path: Manually pruning the backlog**

| Step | Variation |
|---|---|
| 2a | User long-presses an item → context menu: "Remove from Up Next", "Open album" |
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

<!-- CR-001: Journey 5 step 1 — manual search is the entry point; no streaming prefill at MVP. -->
| Step | User action | System response | Emotion | Notes |
|---|---|---|---|---|
| 1 | Opens auxd, taps "+" Log | Bottom sheet opens with empty search; Maya types the album name and picks the result | 😊 |
| 2 | Confirms album, rates 4½★ | Rating commits | 😐 deliberate |
| 3 | Taps "Add a review" | Textarea expands; full editor surface | 😊 |
| 4 | Writes 200-word review with line breaks and one emphasis | Save state: draft autosaved every 5s | 😊 in flow |
| 5 | Reviews own draft, taps "Log" | Entry + Review committed; sheet dismisses to toast: "Review posted to your diary" with a "Share" CTA | 😊 done |
<!-- CR-002: share URL is now the canonical /review/:id route. -->
| 6 | Taps "Share" CTA in toast | OS share sheet opens with prefilled URL (`xiejoshua.com/review/:id`) and OG image preview pointing at the full reading-view hero | 😊 amplifies |
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
<!-- CR-001: success exits no longer include "outbound streaming play" — that's not measurable without integration. -->
- **Every journey ends in either (a) a logged diary entry, (b) a backlog item, or (c) a share event.** If a journey ends in scroll-and-leave, that's a failed journey.
- **Empty states matter** in every journey — research §State Inventory called out 22 distinct states; the most-failing journeys are those where step 1 hits an empty state without a meaningful CTA. *CR-001 note: the first-session empty-diary state is now load-bearing — it was previously masked by the streaming auto-import that pre-populated the diary; without auto-import the user lands on an empty personal diary surface and the critic-seed feed carries the discovery weight.*
- **Aux (🏅) and Like (👍) are distinct concepts** — Aux is the entry-owner's "this is one of my standouts" personal signal on their own DiaryEntry; Like is other users' social engagement on a Review. Different verbs, different icons, different objects. *(Semantic split locked in Revision #3.)*

---

## Resolved decisions (Phase 3 Revision #2)

All 5 prior open questions resolved. See [decision-log.md §User journeys](./decision-log.md) for full table.

<!-- CR-001: UJ-1 and UJ-2 superseded by CR-001 — streaming prefill removed; "Follow 3" surface no longer mixes critic-seed + mutual-taste (mutual-taste deferred). -->
1. **UJ-1 — *(SUPERSEDED by CR-001)* Log sheet prefilled album.** Was: "most-recently-finished album, not last-played track". Now: log sheet opens with empty search at MVP because there is no streaming integration to source prefill from. UJ-1 returns alongside streaming integration in v2.
2. **UJ-2 — *(SUPERSEDED by CR-001)* "Follow 3" card order.** Was: "mixed but always ≥3 critics in top 6 visible cards". Now: critic-seed cards are the only cards surfaced (mutual-taste suggestions require taste data we don't have without streaming history). Minimum follow count raised from 1 to 3 to compensate.
<!-- CR-002: UJ-3 changed — dedicated /review/:id route only; no inline expand. UJ-4 unchanged at MVP, v2 roadmap note added. -->
3. **UJ-3 — Dedicated `/review/:id` route only.** No inline expand in the feed. Feed shows rating + album thumbnail + first ~80 chars of review text as preview; tapping anywhere on the preview navigates to the route. Reading view surface: full hero (album cover, title, artist, viewer's rating, Aux badge if any, Like button, share). Letterboxd parity; URL-shareable with OG meta. *(v1.2: inline expand. v1.5/CR-002: shifted to dedicated route only.)*
4. **UJ-4 — Reviews share-card only at MVP** (no API cross-post to Twitter/X). Cross-post APIs are deprecating; share-card with OG preview is portable and platform-risk-free. *(CR-002 v2 roadmap note: screenshot image-gen — server-side PNG of the `/review/:id` hero — queued for v2 once the dedicated reading-view route exists.)*
5. **UJ-5 — No "Reading list" surface at MVP.** Up Next is for albums only.
