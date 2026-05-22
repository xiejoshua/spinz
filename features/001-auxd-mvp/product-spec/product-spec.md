# Product Spec: auxd (Social Album Platform — MVP)

> Status: DRAFT | Version: 1.0 | Date: 2026-05-21
> Feature: `001-auxd-mvp` | Size: Large
>
> **Related documents:** [User Journeys](./user-journeys.md) | [User Stories](./user-stories.md) | [Data Model](./data-model.md) | [Notification Taxonomy](./notification-taxonomy.md) | [Seeding Strategy](./seeding-strategy.md) | [Success Metrics](./success-metrics.md) | [Out of Scope](./out-of-scope.md) | [Decision Log](./decision-log.md) | [Wireframes](./wireframes/index.html)
>
> **Research artifacts:** [Research Index →](../research/README.md)

---

## 1. Overview

### 1.1 Problem statement

Casual streaming-era listeners (18–35) have no low-friction way to record, share, and discover album experiences with people whose taste they trust. Their listening stays passive and ephemeral. The moment of "I just finished a great album" evaporates because there is no native place to capture it that combines album-first context, social-graph (not algorithmic) discovery, and a friction floor low enough for non-power-users.

### 1.2 Solution summary

**auxd** is a social album-tracking platform: log an album in <8 seconds with a ½-star rating, optionally add a review, see what people you follow thought of it, and discover what to play next from your social graph instead of an algorithm. Spotify auth on day one auto-imports recently-played history so the diary is never empty.

### 1.3 Wedge thesis

auxd is the *unhad combination* of four things none of the 13 prior attempts (RateYourMusic, AOTY, MusicBoard, Albums.fm, hi-fi.cafe, Sonemic, Last.fm, etc.) combined:

1. **Auto-imported streaming history** as the activation primitive (Last.fm proved this scales)
2. **Social-graph-primary feed** as the home surface (Letterboxd proved this compounds)
3. **Album-as-unit** of consumption (RYM proved the audience exists)
4. **Casual-first onboarding** — friction floor below "another social app to maintain"

### 1.4 Background

Three research dimensions converged on this design:

- **Competitor analysis (research/competitors.md):** Six concrete failure causes across prior Letterboxd-for-music attempts — no auto-import, power-user-only positioning, catalog-first-social-second, no tastemaker seeding, scope creep into adjacent domains, mobile-second. The combinatorial gap is open.
- **UX patterns (research/ux-patterns.md):** Letterboxd's bottom-sheet log + ½-star + heart + optional review (sub-8-second commit) is the proven minimum-friction pattern. Goodreads-style notification firehose and AOTY/RYM 100-point metadata walls are the documented anti-patterns to avoid.
- **Tech stack (research/tech-stack.md):** Spotify's social-core endpoints are stable; the algorithmic-rec endpoints were deprecated 2024-11-27, which *strengthens* the social-graph thesis — there's no algo-rec fallback available, so social-graph is the only viable rec path.

> Full research and hypothesis verdicts: [research/README.md](../research/README.md)

---

## 2. Users & Personas

### 2.1 Primary persona — Casey, the Casual Streamer

- **Age:** 24
- **Context:** Designer/grad student/early-career professional; listens to Spotify daily (commute, work-music, Sunday cooking)
- **Music identity:** Has a "music taste" but it lives in their head, screenshots, and a private Notes file. Listens to ~2–4 full albums per week (the rest is playlist/shuffle).
- **Goals:** Remember the albums that hit; share discoveries with 3–5 friends whose taste they trust; find what to play next when nothing in Spotify Discover Weekly resonates.
- **Frustrations:** Spotify's "Liked" model is too coarse; Last.fm is data without community; RateYourMusic feels like a forum from 2008; no one I know is on the smaller alternatives.
- **Acceptance signal:** Casey logs an album within their first session and returns to log a second album within 7 days.

### 2.2 Secondary persona — Maya, the Engaged Listener

- **Age:** 29
- **Context:** Music-adjacent professional or hobbyist (musician, writer, podcaster, music critic, music blogger). Already tracks albums elsewhere (Notion, RYM, AOTY) but unsatisfied with the social layer.
- **Goals:** Maintain a curated album diary; write reviews; influence and be influenced by a small trusted network; eventually have followers.
- **Frustrations:** Power-user trackers are ugly; her friends won't switch to RYM; her existing audience is split across Twitter / Substack / Discord.
- **Acceptance signal:** Maya writes ≥1 review of >50 words within first week; has ≥3 followers within first month.

### 2.3 Tertiary persona — Jamie, the Tastemaker (Critic/Influencer)

- **Age:** 31
- **Context:** Music journalist, label A&R, popular-Twitter music account, niche-podcast host. auxd needs them as the *seed graph* for Casey and Maya.
- **Goals:** A clean, native home for music opinions; broadcast/share-out without algorithmic suppression; build an audience that's actually engaged with music.
- **Frustrations:** Twitter/X demotes outbound links; Substack is too long-form; Threads has no music structure; everywhere else they have to build audience from scratch.
- **Acceptance signal:** Jamie writes a review on auxd that ≥10 followers see organically within 24h. auxd's seeding strategy (see [seeding-strategy.md](./seeding-strategy.md)) is built around recruiting Jamies.

---

## 3. Core Capabilities (MVP scope)

The MVP has **five user-facing capabilities** plus onboarding and social/identity primitives.

### 3.1 Rate albums
- ½-star rating, 0–5 in halves (e.g., 3.5★).
- Optional **"Aux"** (🏅): a deliberate personal-curation signal on YOUR own diary entry — "this album is one of my standouts in my diary." Rare and intentional. Independent of the star rating. *(Distinct from "Like" — see §3.3 for Likes-on-reviews; the semantic split was finalized in Revision #3.)*
- Re-rating allowed; history preserved in diary entries.
- Ratings are public by default; per-entry visibility override (public / followers-only / private-diary).

### 3.2 Log listens (diary)
- Each Log = one diary entry with: album, date, rating (optional), Aux (optional), review (optional), visibility, source (manual / Spotify auto-import / Spotify just-finished-prompt / Last.fm import).
- Diary is chronological, never algorithmically reordered.
- A user can log the same album multiple times (e.g., relistens, with different ratings).
- When Spotify is connected: the system polls recently-played; on detecting an album was just finished, it surfaces an in-app prompt ("Just listened to {album} — log it?") and (opt-in) push. This is the **auto-prompt** feature. User-level setting `auto_prompt_enabled` (default ON). Quiet hours respected. Per-album dismissal sticks for 30 days.
- The auto-imported Spotify history on first session pre-populates the diary (last 30 days, deduped to one entry per album).

### 3.3 Write/share reviews
- Optional after rating; no length minimum (≥1 character).
- Markdown-safe subset (bold, italic, line breaks; no images/embeds at MVP).
- Public-by-default visibility; per-review override.
- No nag prompts on review length (the "say more" hint was removed in Revision #3).
- Edits preserved with `edited_at` timestamp; latest version shown publicly with "edited" badge; internal 90-day revision history kept for moderation only (per FR-030).
- **Other users can "Like" a review** (👍): a lightweight social engagement signal — distinct from the entry-owner's Aux (🏅 — see §3.1). Reviews surface a Like counter and can be sorted by **Most Liked** in addition to Newest / Highest-Rated. *(Added in Revision #3.)*

### 3.4 Maintain backlog ("Up Next")
- A list of albums the user intends to listen to.
- Distinct from Spotify's "Liked" (which is tracks).
- Aspirational, not historical; once logged, an album is auto-removed from backlog (with optional setting to keep).
- Backlog is **private by default** (don't surface "Casey wants to listen to X" — feels surveillance-y); per-album visibility override available.

### 3.5 Discover via social graph
- Default home surface = follow-graph feed.
- Reverse-chronological with weight boost for: written reviews, ★★★★★/★ extreme ratings, entries by closely-followed users.
- No algorithmic reranking; transparent ordering.
- "Friends rated this high" surface on album detail pages.
- "Suggested follows" surface during onboarding and after every 10 logs, based on mutual taste overlap (heuristic).

### 3.6 Onboarding (gates activation)
- Step 1: Sign up (email + password OR Spotify-OAuth shortcut).
- Step 2: Spotify auth screen with a **prominent Skip button**. Skipping is fully supported — the user goes directly to step 4 and lands on a working product (manual log, critic-seed feed, reviews, Lists, backlog all function). Spotify can be connected later from Settings → Integrations to back-fill the diary; it's a value-add, not a requirement. No "degraded mode" framing.
- Step 3 (Spotify-connected path only): Auto-import last 30 days of recently-played albums → present as a "Confirm your last 30 days" screen → user ½-stars top 5 in <60 sec.
- Step 4: "Follow 3 to fill your feed" — curated critic-seed roster + mutual-taste suggestions (taste data is rich on Spotify-connected path, falls back to critic-seed-only on skipped path); minimum 1 follow to advance.
- Step 5: Land on home feed (pre-populated with critic-seed + just-followed entries).
- Step 6 (Spotify-connected, deferred — runs in background ~10 min later): First just-finished prompt rolls out only once initial state has settled, so onboarding never collides with auto-prompt UX.

### 3.7 Social/identity primitives
- Public profile: avatar, display name, handle (`@`), bio (140 chars), ratings histogram, recent diary entries, follows/followers.
- Follow graph: asymmetric (X follows Y, Y doesn't have to follow back; like Twitter, not Facebook).
- Block (user level) + report (per-content) — minimal moderation surface for MVP.

> **§3.8 Curated Lists was elevated to MVP in Revision #1, then reverted to v2 in Revision #3** (2026-05-21). See [out-of-scope.md](./out-of-scope.md) and [decision-log.md](./decision-log.md) row 7 for the trade-off discussion. The MVP refocuses on the core wedge: log + rate + Aux + review + backlog + social-feed.

---

## 4. Functional Requirements

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-001 | Users can sign up via email/password or Spotify OAuth | Must | OAuth shortcut auto-creates account |
| FR-002 | Users can connect Spotify account via OAuth 2.0 PKCE (optional — skippable at signup and connectable later from settings) | Must | **Essential scopes at MVP:** `user-read-recently-played`, `user-read-currently-playing`, `user-library-read`. `playlist-read-private` deferred (request lazily if Lists ever ingest from playlists). Skipping = product works fully; no "degraded mode". |
| FR-003 | System auto-imports last 30 days of recently-played albums on Spotify connect (whether at signup or later) | Must | Albums = aggregated from track-level history; dedup to album-grain |
| FR-004 | Users can log an album with ½-star rating, Aux (🏅), and optional review | Must | Single bottom-sheet UX; <8s commit target. Aux is the entry-owner's personal "standout" signal — distinct from Likes on reviews (FR-031). |
| FR-005 | Users can search the album catalog (Spotify catalog + MusicBrainz fallback) | Must | Atlas Search index on cached metadata |
| FR-006 | Users can add an album to "Up Next" (backlog) | Must | Private by default |
| FR-007 | Users have a chronological diary visible on their profile | Must | Public by default; per-entry override |
| FR-008 | Users can follow / unfollow other users | Must | Asymmetric follows |
| FR-009 | Home feed shows entries from followed users in weighted-reverse-chronological order | Must | Weights: review-attached, extreme ratings, interaction history |
| FR-010 | Album detail page shows: cover, metadata, tracklist, ratings histogram, friends-who-rated, public reviews | Must | Tracklist is read-only metadata, no playback at MVP |
| FR-011 | Users can write a public-or-followers-only review on any album | Must | Markdown-safe subset |
| FR-012 | Users receive notifications per the [Notification Taxonomy](./notification-taxonomy.md) | Must | Conservative defaults |
| FR-013 | Users can set per-entry visibility (public / followers-only / private) | Must | Default = public |
| FR-014 | Users can block (user) and report (content) | Must | Minimal MVP moderation |
| FR-015 | Critic-seed accounts are pre-followed for new users (TBD: opt-in or opt-out) | Must | Lock in [seeding-strategy.md](./seeding-strategy.md) |
| FR-016 | Suggested follows surfaced during onboarding and periodically thereafter | Must | Mutual-taste heuristic |
| FR-017 | Last.fm history can be imported as an alternative to Spotify auto-import | Should | Covers users who don't want OAuth |
| FR-018 | User can export their diary as JSON or CSV | Should | GDPR / portability hygiene |
| FR-019 | User can delete their account; all owned content removed within 30 days | Must | GDPR right-to-erasure |
| FR-020 | All forms validate client + server side | Must | Standard practice |
<!-- FR-021..FR-025 RESERVED — were Lists FRs in Revision #1, removed in Revision #3 (Lists deferred to v2). IDs preserved for audit; not reassigned. -->
| FR-026 | When Spotify is connected, the system surfaces a "just-finished" prompt on detecting a finished album | Must | In-app default ON; push opt-in. Per-user `auto_prompt_enabled` and quiet-hours respected. Per-album dismissal sticks for 30 days. |
| FR-027 | Settings → Integrations exposes Spotify connect/disconnect status and a "back-fill diary" trigger | Must | Skipped-at-signup users use this to connect later. **On disconnect:** the diary persists immutably — all DiaryEntry / Rating / Review / Aux / Follow remains; only auto-import + auto-prompt + Log-sheet prefill stop. Reconnect resumes from next polling cycle; no gap back-fill. A small "Disconnected on YYYY-MM-DD" note is shown in Settings only. |
| FR-028 | Album detail page surfaces an "Edition" chip with dropdown when an album has multiple editions under the same release-group MBID | Must | Default: "All editions" view (aggregates ratings/reviews/likes). Dropdown: Standard / Deluxe / Bonus / etc. Ratings/reviews/likes aggregate across all editions; the chip is filter-only, not data-partition. |
| FR-029 | Users can change their handle (`@`) at most once per 30 days; first change is locked for the first 30 days after account creation | Must | 200–500 obvious-squat candidates reserved at launch; abandoned handles re-usable 90d post-deletion with redirect to prevent link-rot. No paid claim service. |
| FR-030 | Users can edit a published review; the latest version is shown publicly with an "edited" badge; an internal 90-day revision history is preserved for moderation | Must | Edit-history is NOT public. Internal log includes prior versions + edit timestamps + edit-event hashes for tamper detection. |
| FR-031 | Users can "Like" (👍) other users' reviews — a lightweight social engagement signal distinct from the entry-owner's Aux | Must | Idempotent toggle; per-user, per-review. Like is on the Review only (not on DiaryEntry); Aux stays on the entry owner's DiaryEntry. Notifications generated per N-004 (review.liked). |
| FR-032 | Reviews on album-detail and profile surfaces can be sorted by Newest (default), Most Liked, or Highest-Rated | Must | Sort persists per-device; "Most Liked" surfaces engagement-validated reviews; "Highest-Rated" surfaces the reviewer's rating order. Sort applies to the reviews list, not to other surfaces. |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | p95 home feed load <500ms (server-side); p95 album detail <400ms; p99 Spotify import (30-day, ~50 albums) <8s end-to-end |
| **Availability** | 99.5% monthly uptime target at MVP; degrade gracefully when Spotify API is unavailable (show cached data, queue writes) |
| **Scalability** | Sized for 10,000 concurrent users at peak (3x M6 WAL target of 2,500) without architectural changes |
| **Accessibility** | WCAG 2.1 AA — keyboard nav, screen-reader labels on rating widget, contrast on album-art-heavy surfaces ≥4.5:1, reduced-motion respect, touch targets ≥44pt mobile |
| **Privacy** | Public-by-default opt-out per entry; private-profile toggle; backlog private by default; no third-party tracking beyond PostHog (self-hosted) and Sentry (errors) at MVP; no ad SDKs |
| **Security** | OAuth tokens encrypted at rest; no Spotify refresh tokens client-side; rate limiting on log/follow/review endpoints; CSRF protection; password hash bcrypt min cost 12 |
| **Compliance** | GDPR (export + erasure); Spotify ToS compliance ("Powered by Spotify" attribution required on album surfaces); audit Spotify branding guidelines before public launch |
| **Spotify rate limits** | All Spotify calls server-side via async httpx; per-user circuit breaker; cache album metadata 7d; cache user listening 1h |
| **i18n / l10n** | English-only at MVP; copy strings extracted to keys for future locales (no harvest run since `i18n_harvest` is `not_applicable`) |
| **Mobile responsiveness** | Mobile-first design, breakpoint at 768px; PWA installable; iOS/Android-native deferred to v2 |
| **SEO** | Album detail pages SSR with Open Graph meta tags (Letterboxd-style link sharing relies on OG previews); profile pages SSR; everything else can be CSR |
| **Observability** | Every external API call logged with provider/latency/status; Sentry for errors; PostHog for product analytics; daily ETL of key metrics |

---

## 6. Out of Scope (v1)

See full list with rationales: [out-of-scope.md](./out-of-scope.md)

Highlights:
- Apple Music integration (v2)
- Native iOS / Android apps (v2 — PWA at MVP)
- ALS / collaborative-filtering recommendation engine — v2
- Wrapped-style annual retrospective — v2
- **Curated user-created Lists — v2** *(elevated to MVP in Revision #1, returned to v2 in Revision #3)*
- In-app messaging / DMs — out (forever, unless explicit product pivot)
- Editorial/curated content surface (Pitchfork-style) — out at MVP
- Paid tier / payments code — no Stripe at MVP

> *Revision history:* R1 elevated Lists + Auto-prompt from v2 to MVP. R3 returned Lists to v2 after weighing scope cost vs wedge focus; Auto-prompt remains in MVP.

---

## 7. Success Criteria

See full metrics: [success-metrics.md](./success-metrics.md) and [research/metrics-roi.md](../research/metrics-roi.md)

**North Star:** Weekly Active Loggers (WAL) — unique users who logged ≥1 album AND opened the app in trailing 7 days.

**M3 targets:** WAL 500 · W1 activation 30% · D30 retention 8% · social-originated play rate 25%
**M6 targets:** WAL 2,500 · W1 activation 35% · D30 retention 12% · social-originated play rate 40%

**Definition of MVP success:** At M6, the M6 targets are met *and* qualitative interviews with 15+ active users confirm H1 (the "remember/share moment" hypothesis was real for them and auxd captured it).

---

## 8. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| H1 (user-research validation) never confirms — casual users don't actually want this | M | H | Run the [interview script](../problem-discovery/interview-script.md) during early-access wave; treat first 8 weeks of metrics as the real validation gate; have a pivot-or-shutdown decision point at M3 if North Star is <20% of target |
| Spotify changes API terms / deprecates more endpoints | M | H | Provider-interface abstraction; Apple Music integration ready in v2 if Spotify becomes hostile; degrade gracefully when capabilities disappear |
| Extended Quota Mode application denied or stuck in review | M | M | Apply Day 1 of plan; design closed-beta phase that lives entirely inside Development Mode quotas |
| Cold-start ghost-town — seed graph never compounds | M | H | Seeding strategy (see doc) is launched as a project alongside the product, not a marketing afterthought; founder-curated critic seed must be live before public-access wave |
| Notification firehose drives churn (the Goodreads pattern) | L | H | Conservative defaults; per-notification granular settings; weekly digest as primary mode, not real-time push |
| Music metadata quality (deluxe editions, regional variants, duplicate releases) confuses users | M | M | MusicBrainz MBID canonical + Spotify fallback; album-merge UI in admin; user "report wrong album" surface |
| Privacy / safety incident (harassment, doxxing via diaries) | L | H | Block + report from MVP; private-profile toggle; rate-limit follows; do not show real-time presence; explicit ToS |
| Search returns irrelevant results due to Atlas Search tuning | M | M | Start with Spotify search as primary, Atlas as fallback; iterate index after launch |
| Performance regression at 5k+ concurrent users due to feed fan-out choice | M | M | Plan-time decision (fan-out-on-write vs read); MVP defaults to fan-out-on-read because writes are infrequent and follow-counts low |
| Content moderation load exceeds founder bandwidth | L | M | Defer paid moderation tools; cap feature growth; community guidelines + ToS clear from day one |

---

## 9. Decision Log (Top-level summary)

See full log: [decision-log.md](./decision-log.md)

Top decisions locked across Phase 2 + Phase 3 Revisions #1–#3:
1. Spotify-only at launch; Apple Music = v2
2. ½-star rating (Letterboxd model)
3. Auto-prompt for just-finished albums ENABLED at MVP (opt-out default ON) — *R1*
4. Public-by-default with per-entry override
5. **Curated Lists DEFERRED to v2** — *R1 elevated, R3 returned to v2*
6. Spotify auth + auto-import = onboarding flow, with skippable Spotify step — *R1*
7. MusicBrainz MBID canonical / Spotify ID fallback for album identity
8. Provider-interface abstraction for music sources
9. No paid tier at launch (future auxd Pro $19/yr + Patron $39/yr documented as future-state)
10. Heuristic social-graph recs only (no ML at MVP)
11. PWA + responsive web only (no native at MVP)
12. Atlas Search for catalog search
13. **Aux (🏅) vs Like (👍) — split semantics** — *R1 unified as Aux; R3 split into Aux (self) + Like (social)*
14. **No "say more" soft prompt on short reviews** — *R3 removed*
15. **Reviews are Likeable + sortable by Most Liked** — *R3 added*

---

## 10. Open Questions

**All 10 product-spec open questions were resolved in Phase 3 Revision #2** (2026-05-21). See [decision-log.md §Open Questions — Resolutions](./decision-log.md) Q13–Q22 for the locked decisions with rationale.

For completeness, the resolutions:

| # | Original question | Resolution |
|---|---|---|
| Q13 | Critic seeds: followed by default or suggested-only? | **Pre-checked checkbox cards on Follow 3 screen** |
| Q14 | Auto-import window: 30 days, 6 months, all-available? | **30 days at signup; "Pull more history" as v1.x setting** |
| Q15 | Deluxe / remasters: separate entries or merged? | **Merged under release-group MBID; Edition selector on album detail** |
| Q16 | Handle reservation / mutability / squatting | **Unique, immutable 30d after create, then changeable ≤1/30d; reserve obvious-squat candidates** |
| Q17 | Review edits: allowed or append-only? | **Edits allowed; public shows latest+badge; 90d internal audit log** |
| Q18 | Notification real-time vs digest? | **Push only for follows / follow-requests / spotify-reconnect; in-app for all event types; weekly digest is the only batched channel** |
| Q19 | Diary persistence on Spotify disconnect? | **Yes — immutable; reconnect does not back-fill the gap** |
| Q20 | Seed graph: artists or critics-only? | **Critics + curators only at MVP; artists a separate v1.x cohort** |
| Q21 | Albums released during reach-back window? | **Included naturally; lazy-fetch from Spotify catalog if not in MusicBrainz yet** |
| Q22 | Spotify OAuth scopes — essential vs nice-to-have? | **Essential: recently-played, currently-playing, library-read. playlist-read-private deferred** |

> Zero open questions remain at spec level. Technical decisions deferred to Phase 5 (fan-out strategy, Atlas Search tuning, etc.) are documented in [decision-log.md §Decisions deferred to Phase 5](./decision-log.md).
