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

<!-- CR-001: reframed from "casual streaming-era listeners" to "music-engaged listeners"; streaming auto-import is no longer the activation primitive. -->
<!-- CR-002: "social-graph (not algorithmic)" softened — wedge is data-stage-aware, not anti-algorithm. ML returns in v2 when scale + data earn its keep. -->
Music-engaged listeners (18–35) have no low-friction way to record, share, and discover album experiences with people whose taste they trust. Their listening stays passive and ephemeral. The moment of "I just finished a great album" evaporates because there is no native place to capture it that combines album-first context, social-graph-first discovery (richer methods like ML-based recs return in v2 once the data + graph density support them), and a friction floor low enough for non-power-users.

### 1.2 Solution summary

<!-- CR-001: Letterboxd-for-music posture; manual log replaces streaming auto-import. -->
<!-- CR-002: "instead of an algorithm" reworded — wedge is data-stage-aware, not anti-algorithm. -->
**auxd** is a social album-tracking platform — Letterboxd-for-music in posture. Log an album in <8 seconds with a ½-star rating via a clean manual search, optionally add a review, see what people you follow thought of it, and discover what to play next from your social graph (richer ML-based recs layer on top in v2 once data + graph density support them). The first session is filled by a curated critic-seed feed; the diary fills as you log.

### 1.3 Wedge thesis

<!-- CR-001: wedge honestly restated as 3-of-4 of the original combo; auto-imported streaming history removed as MVP primitive. -->
auxd is the *unhad combination* of three things none of the 13 prior attempts (RateYourMusic, AOTY, MusicBoard, Albums.fm, hi-fi.cafe, Sonemic, Last.fm, etc.) combined at once:

1. **Social-graph-primary feed** as the home surface (Letterboxd proved this compounds)
2. **Album-as-unit** of consumption (RYM proved the audience exists)
3. **Casual-first onboarding + clean manual logging at album-grain** — friction floor below "another social app to maintain", Letterboxd-pattern log sheet

> *Honest scope note:* the original wedge thesis posited a fourth ingredient — auto-imported streaming history as the activation primitive. That ingredient is deferred to v2 (see decision-log R4 / CR-001). At MVP we ship 3-of-4: the social-graph + album-unit + casual-manual-log combination. The critic-seed feed (see [seeding-strategy.md](./seeding-strategy.md)) becomes load-bearing for first-session non-empty content.

### 1.4 Background

Three research dimensions converged on this design:

- **Competitor analysis (research/competitors.md):** Six concrete failure causes across prior Letterboxd-for-music attempts — no auto-import, power-user-only positioning, catalog-first-social-second, no tastemaker seeding, scope creep into adjacent domains, mobile-second. The combinatorial gap is open. *(CR-001 note: at MVP we accept the "no auto-import" attribute of prior attempts — but we differentiate via critic-seed feed + casual manual-log UX, not via auto-import.)*
- **UX patterns (research/ux-patterns.md):** Letterboxd's bottom-sheet log + ½-star + heart + optional review (sub-8-second commit) is the proven minimum-friction pattern. Goodreads-style notification firehose and AOTY/RYM 100-point metadata walls are the documented anti-patterns to avoid.
<!-- CR-001 removed: Spotify-endpoint-stability tech-stack bullet — not load-bearing now that MVP doesn't depend on Spotify. -->
- **Catalog source (research/tech-stack.md, revised for CR-001):** MusicBrainz is the primary canonical catalog source; Discogs is the fallback for releases MusicBrainz lacks. Atlas Search indexes a cached MusicBrainz subset; cover art is sourced from the Cover Art Archive.

> Full research and hypothesis verdicts: [research/README.md](../research/README.md)

---

## 2. Users & Personas

<!-- CR-001: persona reframed — no longer Spotify-specific; music-engaged listener -->
### 2.1 Primary persona — Casey, the Music-Engaged Listener

- **Age:** 24
- **Context:** Designer/grad student/early-career professional; listens to music daily across streaming services (commute, work-music, Sunday cooking)
- **Music identity:** Has a "music taste" but it lives in their head, screenshots, and a private Notes file. Listens to ~2–4 full albums per week (the rest is playlist/shuffle).
- **Goals:** Remember the albums that hit; share discoveries with 3–5 friends whose taste they trust; find what to play next when their normal rotation feels stale.
- **Frustrations:** Streaming services' "Liked" model is too coarse; Last.fm is data without community; RateYourMusic feels like a forum from 2008; no one I know is on the smaller alternatives.
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
<!-- CR-001: source enum reduced to manual at MVP; auto-import sources deferred to v2 with auto-prompt cluster -->
- Each Log = one diary entry with: album, date, rating (optional), Aux (optional), review (optional), visibility, source (currently `manual` only at MVP; `streaming_import` / `just_finished_prompt` / `lastfm_import` source values are reserved for v2).
- Diary is chronological, never algorithmically reordered.
- A user can log the same album multiple times (e.g., relistens, with different ratings).
<!-- CR-001 removed: streaming poll → just-finished auto-prompt block — deferred to v2 (cluster US-B6, FR-026, JustFinishedPrompt collection, polling worker T123). JustFinishedPrompt code/data shape is preserved as deferred; nothing in the MVP wires it. See decision-log R4. -->
<!-- CR-001 removed: 30-day streaming-history pre-populate. At MVP the diary is empty at first session; critic-seed feed carries first-session content. -->

### 3.3 Write/share reviews
- Optional after rating; no length minimum (≥1 character).
- Markdown-safe subset (bold, italic, line breaks; no images/embeds at MVP).
- Public-by-default visibility; per-review override.
- No nag prompts on review length (the "say more" hint was removed in Revision #3).
- Edits preserved with `edited_at` timestamp; latest version shown publicly with "edited" badge; internal 90-day revision history kept for moderation only (per FR-030).
- **Other users can "Like" a review** (👍): a lightweight social engagement signal — distinct from the entry-owner's Aux (🏅 — see §3.1). Reviews surface a Like counter and can be sorted by **Most Liked** in addition to Newest / Highest-Rated. *(Added in Revision #3.)*

### 3.4 Maintain backlog ("Up Next")
<!-- CR-001: dropped "distinct from Spotify Liked"; backlog is now compared against generic streaming-service Liked semantics -->
- A list of albums the user intends to listen to.
- Distinct from generic streaming-service "Liked"/track-favourite primitives (which are track-grain). Backlog is album-grain.
- Aspirational, not historical; once logged, an album is auto-removed from backlog (with optional setting to keep).
- Backlog is **private by default** (don't surface "Casey wants to listen to X" — feels surveillance-y); per-album visibility override available.

### 3.5 Discover via social graph
- Default home surface = follow-graph feed.
- Reverse-chronological with weight boost for: written reviews, ★★★★★/★ extreme ratings, entries by closely-followed users.
- No algorithmic reranking; transparent ordering.
- "Friends rated this high" surface on album detail pages.
- "Suggested follows" surface during onboarding and after every 10 logs, based on mutual taste overlap (heuristic).

### 3.6 Onboarding (gates activation)
<!-- CR-001: onboarding collapsed to signup → handle → follow ≥3 critics → critic-seed feed; no streaming-auth step. -->
- Step 1: Sign up with email + password.
- Step 2: Pick a handle (`@`). Suggestion-driven; uniqueness checked inline.
- Step 3: "Follow ≥3 critics to fill your feed" — curated critic-seed roster surfaced as pre-checked cards (per Q13 / R2 decision); minimum 3 follows to advance.
- Step 4: Land on home feed (pre-populated with critic-seed activity from the past 7 days; user's own diary is empty until they log their first album).

### 3.7 Social/identity primitives
- Public profile: avatar, display name, handle (`@`), bio (140 chars), ratings histogram, recent diary entries, follows/followers.
- Follow graph: asymmetric (X follows Y, Y doesn't have to follow back; like Twitter, not Facebook).
- Block (user level) + report (per-content) — minimal moderation surface for MVP.

> **§3.8 Curated Lists was elevated to MVP in Revision #1, then reverted to v2 in Revision #3** (2026-05-21). See [out-of-scope.md](./out-of-scope.md) and [decision-log.md](./decision-log.md) row 7 for the trade-off discussion. The MVP refocuses on the core wedge: log + rate + Aux + review + backlog + social-feed.

---

## 4. Functional Requirements

| ID | Requirement | Priority | Notes |
|---|---|---|---|
<!-- CR-001: FR-001 simplified to email/password only at MVP; OAuth-shortcut deferred to v2. -->
| FR-001 | Users can sign up via email + password | Must | Plain email/password signup; no streaming-OAuth shortcut at MVP. |
<!-- CR-001 removed: FR-002 (streaming OAuth + scope detail). ID retained as reserved-gap for audit; not reassigned. -->
| FR-002 | *(reserved — was streaming-OAuth integration; deferred to v2 per CR-001)* | — | Re-eval trigger: see [out-of-scope.md](./out-of-scope.md) row for streaming integration. |
<!-- CR-001 removed: FR-003 (auto-import on connect). ID retained as reserved-gap. -->
| FR-003 | *(reserved — was 30-day auto-import on streaming connect; deferred to v2 per CR-001)* | — | Bundled with FR-002 in v2 streaming-integration cluster. |
| FR-004 | Users can log an album with ½-star rating, Aux (🏅), and optional review | Must | Single bottom-sheet UX; <8s commit target. Aux is the entry-owner's personal "standout" signal — distinct from Likes on reviews (FR-031). |
<!-- CR-001: catalog source changed to MusicBrainz primary + Discogs fallback. -->
| FR-005 | Users can search the album catalog (MusicBrainz primary + Discogs fallback) | Must | Atlas Search indexes a cached MusicBrainz subset; cover art via Cover Art Archive. |
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
<!-- CR-001: Last.fm import deferred to v2 — see out-of-scope.md. ID retained as reserved-gap. -->
| FR-017 | *(reserved — was Last.fm history import; deferred to v2 per CR-001)* | — | Re-eval trigger: power-user cohort asking for back-fill of historical scrobbles. |
| FR-018 | User can export their diary as JSON or CSV | Should | GDPR / portability hygiene |
| FR-019 | User can delete their account; all owned content removed within 30 days | Must | GDPR right-to-erasure |
| FR-020 | All forms validate client + server side | Must | Standard practice |
<!-- FR-021..FR-025 RESERVED — were Lists FRs in Revision #1, removed in Revision #3 (Lists deferred to v2). IDs preserved for audit; not reassigned. -->
<!-- CR-001: FR-026 deferred to v2 (just-finished prompt cluster). Code exists but is unwired from MVP. -->
| FR-026 | *(DEFERRED-TO-V2 — was: just-finished prompt on streaming-detected album completion)* | — | JustFinishedPrompt entity, polling worker, and related logic remain in the repo as deferred surface area; nothing in the MVP wires them. See decision-log R4 / CR-001. |
<!-- CR-001 removed: FR-027 (Settings → Integrations / connect-disconnect / back-fill). ID retained as reserved-gap. -->
| FR-027 | *(reserved — was Settings → Integrations streaming connect/disconnect/back-fill; deferred to v2 per CR-001)* | — | Returns in v2 when streaming integration returns. |
| FR-028 | Album detail page surfaces an "Edition" chip with dropdown when an album has multiple editions under the same release-group MBID | Must | Default: "All editions" view (aggregates ratings/reviews/likes). Dropdown: Standard / Deluxe / Bonus / etc. Ratings/reviews/likes aggregate across all editions; the chip is filter-only, not data-partition. |
| FR-029 | Users can change their handle (`@`) at most once per 30 days; first change is locked for the first 30 days after account creation | Must | 200–500 obvious-squat candidates reserved at launch; abandoned handles re-usable 90d post-deletion with redirect to prevent link-rot. No paid claim service. |
| FR-030 | Users can edit a published review; the latest version is shown publicly with an "edited" badge; an internal 90-day revision history is preserved for moderation | Must | Edit-history is NOT public. Internal log includes prior versions + edit timestamps + edit-event hashes for tamper detection. |
| FR-031 | Users can "Like" (👍) other users' reviews — a lightweight social engagement signal distinct from the entry-owner's Aux | Must | Idempotent toggle; per-user, per-review. Like is on the Review only (not on DiaryEntry); Aux stays on the entry owner's DiaryEntry. Notifications generated per N-004 (review.liked). |
| FR-032 | Reviews on album-detail and profile surfaces can be sorted by Newest (default), Most Liked, or Highest-Rated | Must | Sort persists per-device; "Most Liked" surfaces engagement-validated reviews; "Highest-Rated" surfaces the reviewer's rating order. Sort applies to the reviews list, not to other surfaces. |
<!-- sync-fix L2-014: FR-033 added by CR-001 spec.md propagated here (Run #4). -->
| FR-033 | "Report missing album" workflow surfaced from the manual-search empty-state in the Log sheet; user submits artist + album + optional MBID/Discogs URL hint; report queued for catalog-team triage; user gets in-app confirmation | Must | Tied to US-F2 (album search). Backed by `Report.target_type=missing_album` (data-model.md). Catalog gap-fill safety valve added in CR-001 since manual search is now the sole catalog-discovery surface. |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
<!-- CR-001: Spotify-import performance bullet removed; catalog-fetch NFR added. -->
| **Performance** | p95 home feed load <500ms (server-side); p95 album detail <400ms; p95 catalog search <300ms (Atlas Search against MusicBrainz cache). |
<!-- CR-001: availability NFR no longer references Spotify API. -->
| **Availability** | 99.5% monthly uptime target at MVP; degrade gracefully when the catalog provider (MusicBrainz) is unavailable — fall back to Discogs, then to cached metadata. |
| **Scalability** | Sized for 10,000 concurrent users at peak (3x M6 WAL target of 2,500) without architectural changes |
| **Accessibility** | WCAG 2.1 AA — keyboard nav, screen-reader labels on rating widget, contrast on album-art-heavy surfaces ≥4.5:1, reduced-motion respect, touch targets ≥44pt mobile |
| **Privacy** | Public-by-default opt-out per entry; private-profile toggle; backlog private by default; no third-party tracking beyond PostHog (self-hosted) and Sentry (errors) at MVP; no ad SDKs |
<!-- CR-001: removed OAuth-token-at-rest + refresh-token bullets; not applicable at MVP. -->
| **Security** | Rate limiting on log/follow/review endpoints; CSRF protection; password hash bcrypt min cost 12 |
<!-- CR-001: ToS compliance bullet redirected — MusicBrainz/Discogs/Cover Art Archive attribution per their license terms. -->
| **Compliance** | GDPR (export + erasure); MusicBrainz attribution per their license terms (CC0 for the database; cover art via Cover Art Archive carries its own per-image licensing — surface attribution where required). |
<!-- CR-001 removed: Spotify-rate-limits NFR row. Catalog-provider rate limits captured below. -->
| **Catalog provider rate limits** | All catalog calls server-side via async httpx; per-provider circuit breaker; cache album metadata 7d. MusicBrainz public-API courtesy limit (1 req/sec per IP) respected via a server-side gate; Discogs API rate limits respected via the same gate. |
| **i18n / l10n** | English-only at MVP; copy strings extracted to keys for future locales (no harvest run since `i18n_harvest` is `not_applicable`) |
| **Mobile responsiveness** | Mobile-first design, breakpoint at 768px; PWA installable; iOS/Android-native deferred to v2 |
| **SEO** | Album detail pages SSR with Open Graph meta tags (Letterboxd-style link sharing relies on OG previews); profile pages SSR; everything else can be CSR |
| **Observability** | Every external API call logged with provider/latency/status; Sentry for errors; PostHog for product analytics; daily ETL of key metrics |

---

## 6. Out of Scope (v1)

See full list with rationales: [out-of-scope.md](./out-of-scope.md)

Highlights:
<!-- CR-001: streaming integration (auto-import + just-finished prompt + Last.fm import) elevated to top of the deferred list. -->
- **Streaming integration** (auto-import + just-finished prompt) — v2 *(CR-001 / R4: 250k-MAU policy gate is structurally unreachable pre-launch)*
- **Last.fm scrobble import** — v2 *(CR-001 / R4: bundled with streaming-history cluster)*
- Apple Music integration (v2)
- Native iOS / Android apps (v2 — PWA at MVP)
- ALS / collaborative-filtering recommendation engine — v2
- Wrapped-style annual retrospective — v2
- **Curated user-created Lists — v2** *(elevated to MVP in Revision #1, returned to v2 in Revision #3)*
- In-app messaging / DMs — out (forever, unless explicit product pivot)
- Editorial/curated content surface (Pitchfork-style) — out at MVP
- Paid tier / payments code — no Stripe at MVP

> *Revision history:* R1 elevated Lists + Auto-prompt from v2 to MVP. R3 returned Lists to v2 after weighing scope cost vs wedge focus; Auto-prompt remained in MVP through R3. **R4 (CR-001, 2026-05-22)** deferred streaming integration (and the just-finished auto-prompt cluster) entirely to v2 — see decision-log R4.

---

## 7. Success Criteria

See full metrics: [success-metrics.md](./success-metrics.md) and [research/metrics-roi.md](../research/metrics-roi.md)

**North Star:** Weekly Active Loggers (WAL) — unique users who logged ≥1 album AND opened the app in trailing 7 days.

<!-- CR-001: "social-originated play rate" reframed as social-originated discovery rate — manual logging means we don't see outbound streaming plays directly; we measure album-detail-from-feed conversion as the proxy. -->
**M3 targets:** WAL 500 · W1 activation 30% · D30 retention 8% · social-originated discovery rate 25%
**M6 targets:** WAL 2,500 · W1 activation 35% · D30 retention 12% · social-originated discovery rate 40%

**Definition of MVP success:** At M6, the M6 targets are met *and* qualitative interviews with 15+ active users confirm H1 (the "remember/share moment" hypothesis was real for them and auxd captured it).

---

## 8. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| H1 (user-research validation) never confirms — engaged users don't actually want this | M | H | Run the [interview script](../problem-discovery/interview-script.md) during early-access wave; treat first 8 weeks of metrics as the real validation gate; have a pivot-or-shutdown decision point at M3 if North Star is <20% of target |
<!-- CR-001: replaced Spotify-API and Extended-Quota-Mode risks with the catalog-provider + empty-first-session risks that CR-001 introduces. -->
| Catalog provider (MusicBrainz) downtime / data quality | M | M | Discogs fallback; cached metadata serves stale on outage; per-provider circuit breaker; weekly metadata-quality audit on most-logged albums |
| Empty-first-session friction — users land on critic-seed feed with no personal diary | M | H | Critic-seed feed is load-bearing (see [seeding-strategy.md](./seeding-strategy.md)); "Log your first album" CTA prominent; onboarding never gates on having a personal diary |
| Cold-start ghost-town — seed graph never compounds | M | H | Seeding strategy (see doc) is launched as a project alongside the product, not a marketing afterthought; founder-curated critic seed must be live before public-access wave |
| Notification firehose drives churn (the Goodreads pattern) | L | H | Conservative defaults; per-notification granular settings; weekly digest as primary mode, not real-time push |
<!-- CR-001: MusicBrainz primary + Discogs fallback replaces MBID + Spotify-fallback wording. -->
| Music metadata quality (deluxe editions, regional variants, duplicate releases) confuses users | M | M | MusicBrainz MBID canonical + Discogs fallback; album-merge UI in admin; user "report wrong album" surface |
| Privacy / safety incident (harassment, doxxing via diaries) | L | H | Block + report from MVP; private-profile toggle; rate-limit follows; do not show real-time presence; explicit ToS |
<!-- CR-001: Atlas Search now primary against MusicBrainz cache; no streaming-catalog primary. -->
| Search returns irrelevant results due to Atlas Search tuning | M | M | Atlas Search against cached MusicBrainz subset is primary; Discogs is cold-fetch fallback for misses; iterate index after launch |
| Performance regression at 5k+ concurrent users due to feed fan-out choice | M | M | Plan-time decision (fan-out-on-write vs read); MVP defaults to fan-out-on-read because writes are infrequent and follow-counts low |
| Content moderation load exceeds founder bandwidth | L | M | Defer paid moderation tools; cap feature growth; community guidelines + ToS clear from day one |

---

## 9. Decision Log (Top-level summary)

See full log: [decision-log.md](./decision-log.md)

Top decisions locked across Phase 2 + Phase 3 Revisions #1–#4:
<!-- CR-001: top-level decisions updated to reflect R4 / CR-001. -->
1. **Streaming integration deferred to v2** — *R4 / CR-001 (2026-05-22): 250k-MAU policy gate unreachable pre-launch. Apple Music also remains v2.*
2. ½-star rating (Letterboxd model)
3. **Just-finished auto-prompt cluster DEFERRED to v2** — *R1 elevated, R4 deferred (bundled with CR-001 streaming-integration removal)*
4. Public-by-default with per-entry override
5. **Curated Lists DEFERRED to v2** — *R1 elevated, R3 returned to v2*
6. **Onboarding = signup → handle pick → follow ≥3 critics → critic-seed feed** — *R4 / CR-001 (replaces R1's Spotify-auth-with-skip flow)*
7. **MusicBrainz MBID canonical + Discogs fallback** for album identity — *R4 / CR-001 (replaces "MBID + Spotify ID fallback")*
8. Provider-interface abstraction kept; MVP ships one impl per kind (MusicBrainz, Discogs). Future streaming impls slot in v2.
9. No paid tier at launch (future auxd Pro $19/yr + Patron $39/yr documented as future-state)
10. Heuristic social-graph recs only (no ML at MVP)
11. PWA + responsive web only (no native at MVP)
12. **Atlas Search against cached MusicBrainz subset** for catalog search — *R4 / CR-001*
13. **Aux (🏅) vs Like (👍) — split semantics** — *R1 unified as Aux; R3 split into Aux (self) + Like (social)*
14. **No "say more" soft prompt on short reviews** — *R3 removed*
15. **Reviews are Likeable + sortable by Most Liked** — *R3 added*

---

## 10. Open Questions

**All 10 product-spec open questions were resolved in Phase 3 Revision #2** (2026-05-21). **Several resolutions were subsequently superseded by Revision #4 / CR-001 (2026-05-22)** — see decision-log R4 row.

See [decision-log.md §Open Questions — Resolutions](./decision-log.md) Q13–Q22 for the locked decisions with rationale, with CR-001 supersession noted inline.

For completeness, the resolutions (with CR-001 status):

| # | Original question | Resolution | CR-001 status |
|---|---|---|---|
| Q13 | Critic seeds: followed by default or suggested-only? | **Pre-checked checkbox cards on Follow 3 screen** | Still in effect (now load-bearing) |
| Q14 | Auto-import window: 30 days, 6 months, all-available? | **30 days at signup; "Pull more history" as v1.x setting** | **Superseded by CR-001 — auto-import deferred to v2** |
| Q15 | Deluxe / remasters: separate entries or merged? | **Merged under release-group MBID; Edition selector on album detail** | Still in effect (MBID canonical via MusicBrainz) |
| Q16 | Handle reservation / mutability / squatting | **Unique, immutable 30d after create, then changeable ≤1/30d; reserve obvious-squat candidates** | Still in effect |
| Q17 | Review edits: allowed or append-only? | **Edits allowed; public shows latest+badge; 90d internal audit log** | Still in effect |
| Q18 | Notification real-time vs digest? | **Push only for follows / follow-requests; in-app for all event types; weekly digest is the only batched channel** | Adjusted by CR-001 — "spotify-reconnect" push channel removed |
| Q19 | Diary persistence on Spotify disconnect? | (was: immutable on disconnect) | **Superseded by CR-001 — N/A, no streaming connect at MVP** |
| Q20 | Seed graph: artists or critics-only? | **Critics + curators only at MVP; artists a separate v1.x cohort** | Still in effect (more load-bearing now) |
| Q21 | Albums released during reach-back window? | (was: included naturally; lazy-fetch from streaming catalog if not in MusicBrainz yet) | **Superseded by CR-001 — no reach-back window at MVP; new releases enter the catalog via MusicBrainz primary + Discogs fallback the moment a user searches for them** |
| Q22 | Spotify OAuth scopes — essential vs nice-to-have? | (was: 5 essential scopes locked) | **Superseded by CR-001 — N/A, no streaming OAuth at MVP** |

> Zero open questions remain at spec level. Technical decisions deferred to Phase 5 (fan-out strategy, Atlas Search tuning, etc.) are documented in [decision-log.md §Decisions deferred to Phase 5](./decision-log.md).
