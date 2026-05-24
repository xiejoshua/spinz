# Spec: auxd MVP — Social Album Platform

> **Product Forge Feature** | Generated: 2026-05-21
> Feature slug: `001-auxd-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - Product Spec: [product-spec/README.md](./product-spec/README.md) (locked at v1.3, approved after 3 revisions)
> - Research: [research/README.md](./research/README.md)
> - Problem Discovery: [problem-discovery/problem-statement.md](./problem-discovery/problem-statement.md)
> - Decision Log (45+ locked decisions): [product-spec/decision-log.md](./product-spec/decision-log.md)
> - Review Log: [review.md](./review.md)

---

## 0. Locked Decisions Carried From Product Spec (read first)

<!-- CR-001: decision-row count bumped from 17 → 18 and several rows reframed; see #18 below -->
These 18 decisions are non-negotiable inputs to Phase 5 (plan). Each links back to [decision-log.md](./product-spec/decision-log.md) for rationale.

<!-- CR-001: original "Spotify-only at launch" reframed — catalog is MusicBrainz primary + Discogs fallback at MVP -->
1. **Catalog at launch** = MusicBrainz primary + Discogs fallback; Atlas Search indexes a cached MusicBrainz subset. (Original "Spotify-only at launch" **DEFERRED-TO-V2 (CR-001)** — streaming-platform integration deferred pending Extended Quota Mode policy.)
2. **½-star rating scale** (Letterboxd model)
<!-- CR-001: auto-prompt cluster requires streaming-history API; deferred -->
3. **Auto-prompt for just-finished albums** — **DEFERRED-TO-V2 (CR-001)**: structurally impossible without provider listening-history API.
4. **Public-by-default privacy** with per-entry visibility override
5. **Lists DEFERRED to v2** *(elevated in R1, returned to v2 in R3 — do NOT include Lists work in Phase 5)*
<!-- CR-001: onboarding now signup → handle → follow ≥3 critics → critic-seed feed -->
6. **Onboarding** = signup (email + password + handle) → follow ≥3 critics → critic-seed feed; no music-service auth at MVP.
<!-- CR-001: album identity now MBID canonical with no streaming-platform fallback at MVP -->
7. **Album identity** = MusicBrainz release-group MBID canonical (no streaming-platform ID fallback at MVP)
8. **PWA + responsive web only** at MVP (no native iOS/Android)
9. **Aux (🏅) vs Like (👍) — distinct semantics**: Aux is the entry-owner's self-curation signal on their own DiaryEntry; Like is other-user social engagement on a Review. Two icons, two semantics, two data fields, two notification types.
10. **No "say more" soft prompt** on short reviews — reviews can be ≥1 character without a nudge
11. **Reviews are Likeable + sortable** by Newest / Most Liked / Highest-Rated
12. **Critic seeds** appear as PRE-CHECKED checkbox cards on the "Follow 3" onboarding screen (opt-in with default-tick)
13. **Deluxe / remasters** merged under release-group MBID; album detail surfaces an "Edition" chip + dropdown
<!-- CR-001: streaming-platform disconnect path moot — no connect path at MVP; row reframed to v2 -->
14. **Diary persists immutably on streaming-platform disconnect** — **DEFERRED-TO-V2 (CR-001)**: no streaming-platform connect path at MVP; row applies once integration ships in v2.
15. **Reviews edits** allowed; public surface shows latest version + "edited" badge; 90-day internal audit log preserved
16. **Handles** immutable for first 30 days after account creation, then changeable once per 30 days; 200–500 obvious-squat candidates reserved at launch
<!-- CR-001: OAuth scopes row deferred — no music-service OAuth at MVP -->
17. **Music-service OAuth scopes** — **DEFERRED-TO-V2 (CR-001)**: no music-service auth at MVP (Letterboxd-style manual search via MusicBrainz + Discogs).
<!-- CR-001: new locked decision row added (2026-05-22) -->
18. **CR-001 (2026-05-22):** all streaming-platform integration deferred to v2; MVP is Letterboxd-style manual search via MusicBrainz + Discogs. Reason: Extended Quota Mode now requires 250k MAUs to apply — structurally unreachable pre-launch.

> **Phase 5 prerequisite — Constitution gap:** `.specify/memory/constitution.md` is currently the unfilled template. Phase 5 MUST either run `/speckit.constitution` to ratify principles OR include constitution ratification as Task 0 before any feature work. Recommended principles from [research/codebase-analysis.md](./research/codebase-analysis.md): external-call resilience, schema-versioned documents, library-first modules, test-first for catalog/auth edges, observability mandatory.

---

## 1. Overview

### What we're building

<!-- CR-001: persona reframed casual Spotify listeners → music-engaged listeners; streaming-history auto-import removed -->
<!-- CR-002: "rather than algorithmic recommendations" softened — wedge is data-stage-aware, not anti-algorithm. -->
auxd is a social album-tracking platform for music-engaged listeners (18–35) — Letterboxd-for-music in posture. Users log albums they've listened to via a manual search-and-pick flow, rate them on a ½-star scale, write optional reviews, "Aux" personal standouts in their own diary, "Like" reviews written by others, maintain a private backlog of "want to listen" albums, and discover music via their social graph (richer ML-based recs layer on top in v2 once data + graph density support them). The first session is non-empty via a critic-seed feed populated from the user's "follow ≥3 critics" onboarding step.

### Why we're building it

<!-- CR-002: "social-graph (not algorithmic)" softened — wedge is data-stage-aware, not anti-algorithm. -->
Casual streaming-era listeners (18–35) have no low-friction way to record, share, and discover album experiences with people whose taste they trust. Their listening stays passive and ephemeral. The moment of "I just finished a great album" evaporates because there's no native place to capture it that combines album-first context, social-graph-first discovery (richer ML-based recs return in v2 once the data + graph density support them), and a friction floor low enough for non-power-users.

### The wedge thesis

<!-- CR-001: 4-of-4 wedge reduced to 3-of-4; auto-imported streaming history dropped (deferred to v2) -->
The *unhad combination* of three things none of the 13 prior Letterboxd-for-music attempts combined at once: **social-graph-primary feed + album-as-unit + casual-first onboarding** — all three simultaneously. The original wedge included a fourth pillar, *auto-imported streaming history*, which is **DEFERRED-TO-V2 (CR-001)**: Extended Quota Mode now requires 250k MAUs to apply, making any streaming-platform integration structurally unreachable pre-launch. We are honestly shipping 3-of-4 of the original combinatorial gap; the social-graph thesis remains the rec path with no algorithmic-rec fallback.

### Research backing

This spec is backed by a full research phase (Phase 1) covering:

- **Competitors:** 13 competitors analyzed; six concrete causes identified for why prior Letterboxd-for-music attempts (RYM, AOTY, MusicBoard, Albums.fm, hi-fi.cafe, Sonemic) stalled. The combinatorial gap is open.
- **UX/UI:** Letterboxd's bottom-sheet log + ½-star + heart + optional review (sub-8-second commit) is the proven minimum-friction pattern. Goodreads' notification firehose and AOTY/RYM 100-point metadata walls are the documented anti-patterns to avoid.
<!-- CR-001: tech-stack line — streaming-platform Web API + Extended Quota Mode replaced with MusicBrainz + Discogs -->
- **Tech stack:** MusicBrainz catalog API + Discogs fallback; no Extended Quota gate to clear. Recommended stack: Next.js 15 App Router + TanStack Query + shadcn/ui (frontend); FastAPI async + Pydantic v2 + Beanie + Authlib + arq/Redis (backend); MongoDB Atlas + Atlas Search.

> Deep-dive: [research/README.md](./research/README.md). All quantitative figures in research are training-data-based (web access was denied during Phase 1) and tagged for Phase 5 spot-check.

---

## 2. Goals

### Primary goal

When a casual listener finishes an album, they can record their reaction (rate, optionally Aux, optionally review) in under 8 seconds; that signal compounds into a personal diary and a social-graph feed that surfaces what their trusted circle is listening to — creating a music identity and discovery loop that streaming alone doesn't provide.

### Secondary goals

<!-- CR-001: first-session non-empty now sourced entirely from critic-seed feed (no streaming auto-import) -->
- Make the first session non-empty via critic-seed activity surfaced after the "follow ≥3 critics" onboarding step.
- Build a trusted social graph through curated critic-seed roster + mutual-taste suggestions + invite mechanics.
- Provide the album-detail surface as a social hub (friends' ratings + Aux'd, public reviews sortable by Newest / Most Liked / Highest-Rated, Editions).

### Non-goals (v1)

- Apple Music integration (v2)
- Native iOS / Android apps (v2; PWA at MVP)
- **Curated user-created Lists** (v2; elevated to MVP in R1, returned to v2 in R3 after weighing scope vs wedge focus)
- ALS / collaborative-filtering recommendation engine (v2)
- Wrapped-style annual retrospective (v2)
- In-app messaging / DMs (out forever unless explicit product pivot)
- Editorial / curated content surface (out at MVP)
- Paid tier / Stripe (no payments code at MVP)
- Multi-language UI (English-only at MVP; copy keys extracted for future locales)
- Auto-generated lists (post-v2)

Full out-of-scope list with rationale: [product-spec/out-of-scope.md](./product-spec/out-of-scope.md)

---

## 3. Users

<!-- CR-001: primary persona reframed from "Casual Streamer" to music-engaged listener; streaming-app daily-use line softened -->
### Primary persona — Casey, the Music-Engaged Listener (24)

Designer/grad-student/early-career professional. Streams music daily across one of the major platforms. Has a "music taste" but it lives in their head, screenshots, and a Notes app. Listens to ~2–4 full albums per week (rest is playlist/shuffle). Wants to remember standouts and find what to play next without the algorithm or a 2008-era UI.

**Activation signal:** Casey logs an album within their first session AND returns to log a second album within 7 days.

### Secondary persona — Maya, the Engaged Listener (29)

Music-adjacent professional or hobbyist (musician, writer, podcaster, critic). Tracks albums elsewhere (Notion, RYM, AOTY) but unsatisfied with the social layer. Wants a clean diary, audience, and influence.

**Activation signal:** Maya writes ≥1 review of >50 words within first week; ≥3 followers within first month.

### Tertiary persona — Jamie, the Tastemaker / Critic (31)

Music journalist, label A&R, music podcaster, popular music-Twitter account. auxd needs Jamies as the **seed graph** for Casey and Maya (see [product-spec/seeding-strategy.md](./product-spec/seeding-strategy.md)).

**Activation signal:** Jamie writes a review on auxd that ≥10 followers see organically within 24h. Seeding strategy is built around recruiting Jamies pre-launch.

---

## 4. User Stories

> Full G/W/T acceptance criteria for every story: [product-spec/user-stories.md](./product-spec/user-stories.md)
> User journeys / flow narratives: [product-spec/user-journeys.md](./product-spec/user-journeys.md)
> 30 Must-Have, 2 Should-Have, 3 Could-Have *(count reconciled in sync-verify Run #1 — see [sync-report.md](./sync-report.md))*

### Must Have (MVP — 30 stories)

**Cluster A — Onboarding and first-session activation**

<!-- CR-001: US-A1 AC rewritten — removed OAuth shortcut clause -->
- [ ] **US-A1** As Casey, I want to sign up in under 60 seconds, so I don't bounce before seeing value. **AC:** email + password + handle (no music-service OAuth shortcut); auto-handle suggestions on collision.
<!-- CR-001: US-A2 deferred — no music-service connect path at MVP -->
- [ ] **US-A2** **DEFERRED-TO-V2 (CR-001)** — *Original AC: connect to a music service to auto-import recent listening, OR skip and still use auxd fully.* Streaming-platform connect deferred until Extended Quota Mode policy allows pre-launch app review.
<!-- CR-001: US-A3 deferred — depends on streaming-platform listening history -->
- [ ] **US-A3** **DEFERRED-TO-V2 (CR-001)** — *Original AC: rate standout listens from the past 30 days during onboarding via auto-imported recents.* Streaming-platform connect deferred until Extended Quota Mode policy allows pre-launch app review.
<!-- CR-001: US-A4 AC — minimum-follow floor raised from 1 to 3 critics to match CR-001 onboarding flow (signup → handle → follow ≥3 critics → critic-seed feed) -->
- [ ] **US-A4** As Casey, I want to follow a starter set during onboarding. **AC:** Mixed cards (≥3 critics in top 6) with critic-seed cards **PRE-CHECKED** by default (Q13); minimum **3 critic follows** to advance (raised from 1 per CR-001 onboarding flow, since first-session non-emptiness now depends entirely on critic-seed activity — see §11 cold-start risk).
- [ ] **US-A5** As Casey, my first home feed must be non-empty. **AC:** ≥5 entries; if follow graph sparse, padded with critic-seed activity from past 7 days.

**Cluster B — Logging, rating, Aux, auto-prompt**

<!-- CR-001: US-B1 AC rewritten — Letterboxd-pattern manual search; <8s target may revisit on first-typed-search -->
- [ ] **US-B1** As Casey, I want to log an album in <8 seconds. **AC:** Persistent "+" Log button → bottom sheet → MusicBrainz-backed search → pick album → rate + Aux + review + visibility (Letterboxd-pattern); commit time measured server-side. *Note: <8s target may rise to 12–15s on first-typed-search; revisit metric after live signal — see §9 success metrics.*
- [ ] **US-B2** As Casey, I want ½-star rating precision (0.5–5.0). **AC:** Tap-between-stars or drag-to-rate; null rating allowed.
- [ ] **US-B3** As Casey, I want to "Aux" (🏅) an album in my diary as one of my standouts. **AC:** Toggle independent of rating; "Aux'd" filter on profile; appears on album detail "Friends who rated & aux'd this" surface (Aux is **self-directed-only** — not the same as reviewing/liking).
- [ ] **US-B4** As Maya, I want to re-log the same album multiple times. **AC:** New entry; prior entries preserved; album-page shows my full history.
- [ ] **US-B5** As Casey, I want to edit or delete a diary entry. **AC:** Edit rating/Aux/review/visibility; soft-delete with 30d recovery; "edited" badge on changed entries.
<!-- CR-001: US-B6 deferred — depends on streaming-platform listening-history API -->
- [ ] **US-B6** **DEFERRED-TO-V2 (CR-001)** — *Original AC: in-app prompt 5–15min after a streaming-platform-detected just-finished album; opt-in push; per-album 30d dismissal; quiet hours; per-user `auto_prompt_enabled` (default ON).* Pending streaming-platform integration; structurally impossible without provider listening-history API.

**Cluster C — Reviews + Likes + sort**

- [ ] **US-C1** As Maya, I want to write a review after rating. **AC:** Markdown-safe subset; ≥1 char minimum; no "say more" nudge (per R3 decision); save with entry.
<!-- CR-002: inline expand replaced by nav to /review/:id; truncation behavior updated. -->
- [ ] **US-C2** As Casey, I want to read reviews on an album detail page, sorted by Newest (default) / Most Liked / Highest-Rated. **AC:** Sort selector persists per-device; primary tier = friends, then public, then critic-seed; each review preview shows author + rating + first ~80 chars; tapping the preview navigates to `/review/:id` for full reading view (per UJ-3 / CR-002).
- [ ] **US-C3** As Maya, I want to edit or delete a published review. **AC:** Edit — latest version shown publicly with "edited" badge + hover timestamp; 90-day internal audit log preserved; edit history NOT exposed publicly. Delete — text-confirm dialog soft-deletes (`deleted_at` set; removed from public surfaces immediately); 30-day grace before hard-delete cascades `ReviewLike` rows; double-delete returns `410 Gone`. (sync-fix L2-021, Run #9)
- [ ] **US-C4** As Casey, I want to "Like" (👍) another user's review. **AC:** Idempotent toggle; review's `likes_count` increments; N-004 (`review.liked`) notification to reviewer; cannot like own review.

**Cluster D — Backlog (Up Next)**

- [ ] **US-D1** As Casey, I want to add an album to my private backlog. **AC:** "Add to Up Next" from album detail or Log flow; private by default.
<!-- CR-001: US-D2 deep-link replaced — streaming-platform deep-link removed at MVP -->
- [ ] **US-D2** As Casey, I want to view/reorder my backlog and deep-link to an album. **AC:** Drag-reorder persists; deep-link to in-app album detail page only at MVP (external streaming-platform deep-links deferred to v2 alongside streaming integration).
- [ ] **US-D3** As Casey, I want logged albums auto-removed from backlog. **AC:** Default behavior; per-user `keep_backlog_after_log` setting to override; toast confirms removal.

**Cluster E — Social graph and discovery**

- [ ] **US-E1** As Casey, I want to follow another user. **AC:** Asymmetric follows; existing follow dissolved on block; optimistic count update.
- [ ] **US-E2** As Casey, I want to browse a follower's diary. **AC:** Reverse-chrono, 25/page; followers-only entries hidden from non-followers; private entries always hidden.
  <!-- sync-fix L6-005 (Run #11): T094 reviews-only sub-route shipped Session 22 — anchored under US-E2 AC for story-side traceability. -->
  - Profile diary view has a Reviews tab that filters to entries with attached reviews — backed by `GET /api/v1/users/{handle}/reviews` and the `/profile/{handle}/reviews` SSR route.
- [ ] **US-E3** As Casey, my home feed surfaces signal from my follow graph. **AC:** Two modes via `GET /api/v1/feed?mode=for_you|latest` — **"For You"** (default, weighted reverse-chrono with review-attached +20%, ★★★★★/★ +15%, top-5-interacted users +10%, 3-day half-life decay) and **"Latest"** (strict chronological — weights disabled); toggle persists per-device. (sync-fix L2-023, Run #10)
- [ ] **US-E4** As Casey, I want to see "Friends who rated & Aux'd" on album pages. **AC:** Avatars + ratings + Aux badges (🏅) from followed accounts, sorted by rating desc then date desc.
- [ ] **US-E5** As Casey, the app suggests follows based on taste overlap. **AC:** Suggestion job runs after ≥5 ratings; "Discover" tab; dismissed suggestions excluded for 30d.

**Cluster F — Album detail and catalog**

- [ ] **US-F1** As Casey, the album detail page is the social hub. **AC:** SSR; cover, metadata, tracklist, my history, friends' ratings + Aux'd, public reviews list (sortable), Log + Up Next CTAs, OG meta. **Edition selector** chip when an album has multiple editions under the same release-group MBID (per Q15 / FR-028).
<!-- CR-001: US-F2 AC rewritten — Atlas/MusicBrainz/Discogs three-tier instead of Spotify -->
- [ ] **US-F2** As Casey, I want to search the album catalog. **AC:** Atlas Search (cached MusicBrainz subset) + live MusicBrainz lookup on cache-miss + Discogs fallback for obscure pressings; ≥3 chars + 200ms debounce; "Report missing album" link on empty result.

**Cluster G — Profile, settings, privacy**

- [ ] **US-G1** As Maya, I want to edit my profile (display name, bio, avatar, handle). **AC:** Optimistic save; **handle policy** (per Q16/FR-029): immutable first 30d; thereafter ≤1 change per 30d; 200–500 obvious-squat reservations at launch; verification flow for reserved-squat claims post-launch.
- [ ] **US-G2** As Casey, I want privacy defaults (per-entry visibility, private profile). **AC:** Default visibility setting; private-profile toggle creates pending follow-requests queue (creation side ships at MVP via T101); existing followers stay on visibility downgrade. **Approver side (approve / decline / list pending) tracked under S-H3 (Could-have) — MVP ships request creation only** (sync-fix L2-025, Run #10).
  <!-- sync-fix L2-033 (Run #12): S23 T148 shipped the approver UI in full (3 endpoints + FollowRequestsInbox component). Run #10 L2-025 "Could-have" deferral is now stale. -->
  - (updated S23) Approver UI shipped at MVP — pending follow-requests inbox on `/settings/privacy` with approve/decline; N-003 dispatched on approve.
  <!-- sync-fix L6-007 (Run #12): T151 private-profile gate has 4 branches keyed on backend-supplied `relation` field. -->
  - Private-profile view has 4 branches keyed on the backend-supplied `relation` field: (1) `blocked` → "This account is unavailable" (no block-direction leak); (2) `pending` → "Follow request sent" + public header (avatar/display_name/counts) without diary; (3) `target.private_profile && relation NOT IN {self, following}` → "This account is private" + Follow Request button; (4) default → existing Diary/Reviews tabs.
<!-- sync-fix L2-017 (Run #5): notification count corrected — was "18 active types". Canonical post-CR-001 is 14 active + 6 reserved-gap (N-009/010/011/018 deferred per CR-001 + N-019/020 reserved post-R3 Lists removal). See product-spec/notification-taxonomy.md + product-spec/README.md. -->
<!-- sync-fix L2-028 (Run #11): count bumped 14 → 16; N-009/N-010 are registered with all defaults OFF per CR-001 deferral rather than removed from the enum. -->
<!-- sync-fix L2-029 (Run #11): US-G3 AC expanded with 5 shipped facets (N-008 push hardcoded-off, N-016/N-017 email lock, coalesced rollup copy, curated tz select, push-prompt criteria). -->
- [ ] **US-G3** As Casey, I want to manage notifications. **AC:** 16 active notification types (N-009 / N-010 registered with all defaults OFF per CR-001 deferral) + 4 reserved-gap IDs (N-011, N-018, N-019, N-020) with per-channel toggles; quiet hours config; quiet hours suppress push + in-app prompts, not email/digest. (Auto-prompts deferred-to-v2 per CR-001 along with the rest of the S-B6 surface.)
  - N-008 weekly_digest push is hardcoded-off (UI shows the switch as disabled-off).
  - N-016/N-017 (security.new_session, security.password_changed) email channel is locked-on — cannot be disabled (server returns 422 `security_email_locked` if PUT prefs attempts to set it false).
  - Inbox bell coalesced rollup copy: "X and N others did something" when a coalesced parent notification has `payload.coalesced_count > 0`.
  - Quiet-hours timezone select is a curated IANA shortlist with browser-resolved fallback (NOT the full `Intl.supportedValuesOf("timeZone")` dropdown).
  - Push permission prompt criteria: shown only after `follows_count >= 3 OR 7d activity`; banner is non-modal; "Not now" sets a 14d re-show timer.
- [ ] **US-G4** As Maya, I want to block and report. **AC:** Block dissolves existing follow + hides content; report queued with reason; ≥3 reports/7d → daily-log-scan flagging (manual review at MVP, no auto-suspension).
  <!-- sync-fix L6-006 (Run #12): S24 shipped SUSPENDED middleware (T159), Discord webhook admin notify (T156), acknowledge_report CLI (T157), 9-value reason enum (T155/T163a/T167), self-report 422 rejection, idempotent 24h. -->
  - Suspended accounts: SUSPENDED users get a 403 with body `{error: account_suspended, appeal_url}` on every authenticated route EXCEPT the allow-list (POST /api/v1/auth/logout, POST /api/v1/auth/logout-all-devices, POST /api/v1/users/me/delete). Frontend redirects to `/suspended` (standalone page, no app/auth chrome).
  - Reports: 9-value ReportReason enum `{harassment / spam / impersonation / hate_speech / wrong_metadata / duplicate / other}`. Idempotency: same `(reporter, target_type, target_id)` within 24h returns existing row not 409. Self-report rejected with 422. Per-reporter 10/day rate limit. FK validation: 422 if `target_id` doesn't exist.
  - Daily moderation log-scan (03:00 UTC arq cron): flags users with ≥3 reports in trailing 7d (content reports resolve to author user_id; reports against deleted rows silently dropped); fires Discord webhook with handle + count + reason breakdown; idempotent re-run within 7d skips already-flagged.
  - Acknowledge report via `apps/api/scripts/acknowledge_report.py {report_id} --note '...'` CLI (no admin UI at MVP). Sets `Report.acknowledged_at` + fires N-012 dispatch to reporter.
- [ ] **US-G5** As Casey, I want to export my data and delete my account. **AC:** Email JSON+CSV within 24h; 30-day deletion grace period with banner + cancel option.

> Should-Have: US-H1 (Last.fm history import), US-H2 (Album merge / report wrong album), US-H3 (Friend-request flow for private profile), US-H4 (Weekly digest UI improvements), US-H5 (Share-card refinements). Could-Have list in [user-stories.md §Cluster H](./product-spec/user-stories.md).

<!-- sync-fix L6-007 (Run #12): US-H2 + US-H5 ACs anchored here — both shipped in Session 25 (T167 album-report + merge CLI; T168 OG ImageResponse). -->
- [ ] **US-H2** (Should-have, shipped S25) Album merge / report wrong album. **AC:** Backend `POST /api/v1/reports/album` with new `ReportReason` values `WRONG_METADATA` + `DUPLICATE`; idempotent within 24h; FK validation. Frontend `ReportWrong` dialog on `/album/[id]` mounted via `AlbumActions`. Admin merge CLI at `apps/api/scripts/merge_albums.py` (dry-run default; `--yes` for non-interactive; updates `DiaryEntry.album_id` + `Review.album_id` + `BacklogItem.album_id` losing→winning; hard-deletes losing Album — no `AlbumRedirect` at MVP).
- [ ] **US-H5** (Should-have, shipped S25) Share-card OG preview. **AC:** Vercel `next/og` `ImageResponse` routes at `/api/og/album/{id}` + `/api/og/review/{id}`: 1200×630 image with server-side backend fetch; generic auxd fallback on backend 404; `Cache-Control public max-age=31536000 immutable` (Vercel CDN edge cache); `runtime=nodejs`. `generateMetadata()` on `/album/{id}` + `/review/{id}` sets `openGraph.images` + `twitter.card=summary_large_image`.

### Wireframe references

<!-- sync-fix L2-015 (Run #4): wireframe label updated post-CR-001 — was "Confirm-last-30-days screen" (Spotify-import activation). -->
- [wireframes/01-onboarding.html](./product-spec/wireframes/01-onboarding.html) — Follow-Critics screen (the new onboarding activation step)
- [wireframes/02-home-feed.html](./product-spec/wireframes/02-home-feed.html) — Default home surface; Aux badge + Like count distinguished
- [wireframes/03-log-sheet.html](./product-spec/wireframes/03-log-sheet.html) — THE wedge interaction (<8s commit target)
- [wireframes/04-album-detail.html](./product-spec/wireframes/04-album-detail.html) — Social hub with Editions, friends, sortable reviews

---

## 5. Functional Requirements

> Full requirements table with notes: [product-spec/product-spec.md §5](./product-spec/product-spec.md)
> FR-021..FR-025 are reserved-gaps after Lists removal in R3 (preserved for audit, not reassigned).

| ID | Requirement | Priority | Source story |
|---|---|---|---|
<!-- CR-001: FR-001 — OAuth shortcut clause removed -->
| FR-001 | Sign up via email + password + handle (no music-service OAuth shortcut at MVP) | Must | US-A1 |
<!-- CR-001: FR-002 — entire row deferred; kept for traceability -->
| FR-002 | **DEFERRED-TO-V2 (CR-001)** — Connect streaming-platform via OAuth 2.0 PKCE; deferred until Extended Quota Mode policy allows pre-launch app review. | Deferred | US-A2 |
<!-- CR-001: FR-003 — auto-import deferred with streaming integration -->
| FR-003 | **DEFERRED-TO-V2 (CR-001)** — Auto-import last 30 days of recently-played on streaming-platform connect; deferred with FR-002. | Deferred | US-A3 |
| FR-004 | Log an album with ½-star rating, Aux (🏅), and optional review in a single bottom sheet | Must | US-B1, US-B2, US-B3, US-C1 |
<!-- CR-001: FR-005 — search reframed as Atlas/MusicBrainz/Discogs three-tier -->
| FR-005 | Album catalog search: Atlas Search (cached MusicBrainz subset) + live MusicBrainz lookup on cache-miss + Discogs fallback for obscure pressings | Must | US-F2 |
| FR-006 | Add an album to "Up Next" (private backlog) | Must | US-D1 |
| FR-007 | User has a chronological diary visible on their profile | Must | US-E2 |
| FR-008 | Asymmetric follow / unfollow other users | Must | US-E1 |
| FR-009 | Home feed shows entries from followed users in weighted-reverse-chronological order | Must | US-E3 |
| FR-010 | Album detail page with cover, metadata, tracklist, friends section, reviews, Log + Up Next CTAs | Must | US-F1 |
| FR-011 | Write a public-or-followers-only review on any album (markdown-safe subset) | Must | US-C1 |
| FR-012 | Notifications per [Notification Taxonomy](./product-spec/notification-taxonomy.md) | Must | US-G3 |
| FR-013 | Per-entry visibility setting (public / followers / private) | Must | US-G2 |
| FR-014 | Block and report | Must | US-G4 |
| FR-015 | Critic-seed pre-checked cards on Follow 3 (opt-in default-tick; Q13) | Must | US-A4 |
| FR-016 | Suggested follows based on mutual-taste heuristic | Must | US-E5 |
<!-- CR-001: FR-017 — Last.fm import no longer makes sense without a streaming-history primary -->
| FR-017 | **DEFERRED-TO-V2 (CR-001)** — Last.fm history import (was an alternative to streaming-platform auto-import); deferred because the streaming-history primary is itself deferred. | Deferred | US-H1 |
| FR-018 | Export diary as JSON or CSV | Should | US-G5 |
| FR-019 | Account deletion with 30-day grace period; cascading hard-delete | Must | US-G5 |
| FR-020 | Client + server-side form validation | Must | (cross-cutting) |
| ~~FR-021..FR-025~~ | *Reserved — were Lists FRs in R1, removed in R3 (Lists deferred to v2). IDs preserved for audit.* | — | — |
<!-- CR-001: FR-026 deferred — depends on streaming-platform listening-history API -->
| FR-026 | **DEFERRED-TO-V2 (CR-001)** — Just-finished auto-prompt; deferred with streaming-platform integration (structurally impossible without provider listening-history API). | Deferred | US-B6 |
<!-- CR-001: FR-027 deferred — no integrations to surface at MVP -->
| FR-027 | **DEFERRED-TO-V2 (CR-001)** — Settings → Integrations surface; deferred — returns when first streaming-platform integration ships in v2. | Deferred | US-A2, US-G2 |
| FR-028 | Album detail Edition chip + dropdown for multi-edition release-groups | Must | US-F1 |
| FR-029 | Handle change policy: immutable 30d post-creation, ≤1 change per 30d; ~200–500 squat reservations | Must | US-G1 |
| FR-030 | Review edits: latest public + edited badge; 90d internal audit log; edit history NOT public | Must | US-C3 |
| FR-031 | Like (👍) another user's review; idempotent toggle; counter on Review | Must | US-C4 |
| FR-032 | Review sort by Newest (default) / Most Liked / Highest-Rated; persists per-device | Must | US-C2 |
<!-- CR-001: FR-033 added — "Report missing album" workflow tied to manual-search empty-state -->
| FR-033 | "Report missing album" workflow surfaced from manual-search empty-state: user submits artist + album + optional MBID/Discogs URL hint; report queued for catalog-team triage; user gets in-app confirmation. | Must | US-F2 |
<!-- sync-fix L2-020 (Run #9): FR-034 + FR-035 added — drag-reorder + auto-remove backlog behavior shipped in §9 Session 16 but had no FR-row trace. -->
| FR-034 | View Up Next backlog with drag-reorder; order persists per-user via `position` field on `BacklogItem` (1-indexed, contiguous after delete/reorder). Pointer + keyboard a11y supported. | Must | US-D2 |
| FR-035 | Auto-remove logged album from Up Next on `log_entry`, gated by `User.keep_backlog_after_log` (default `false` → auto-remove). PostHog `backlog.converted_to_log` event emits on successful auto-remove for M3/M6 KPI tracking. | Must | US-D3 |
<!-- sync-fix L2-024 (Run #10): FR-036 added — profile endpoint with viewer-relation classifier landed inline at Session 17 (T109 backing). -->
| FR-036 | Profile read endpoint (`GET /api/v1/users/{handle}`) returns user card + follower/following counts + viewer-relation state ∈ {`anonymous`, `none`, `following`, `pending`, `self`, `blocked`}. Existence-leak prevention: a viewer who is blocked-by the target sees `HTTP 404` (not `403`). Powers the `/profile/[handle]` SSR header (Follow + Block/Report affordances). | Must | US-E1, US-G2, US-G4 |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
<!-- CR-001: Performance — streaming-import row removed -->
| Performance | p95 home feed load <500ms (SSR); p95 album detail <400ms |
<!-- CR-001: Availability — streaming-API graceful-degrade clause removed -->
| Availability | 99.5% monthly uptime at MVP |
| Scalability | Sized for 10,000 concurrent users at peak (3× M6 WAL target) without architectural changes |
| Accessibility | WCAG 2.1 AA — keyboard nav; screen-reader labels on rating widget + Aux + Like; contrast ≥4.5:1 on album-art-heavy surfaces; reduced-motion respect; touch targets ≥44pt on mobile |
| Privacy | Public-by-default with per-entry opt-out; private-profile toggle; no third-party tracking beyond PostHog Cloud + Sentry (errors); no ad SDKs |
<!-- sync-fix L2-037 + L2-034 CF (Run #13): NFR Security refreshed on 3 counts — drop OAuth-tokens-at-rest (CR-001 dissolved Spotify), bcrypt→argon2 (T053 / T150 reuse), pin the T173 CSRF header-lift contract. -->
| Security | Password hashing: argon2id via argon2-cffi (T053); validated via `validate_password_policy` helper (≥12 char min) promoted in S23 T150 for shared signup/change-password policy. Rate limiting on log/follow/review/like endpoints (plan §4.5). CSRF: double-submit cookie pattern — backend sets `auxd_csrf` cookie on login; frontend `apps/web/src/lib/api-client.ts` lifts the cookie into the `X-CSRF-Token` header on every `POST`/`PATCH`/`PUT`/`DELETE`; backend `SessionMiddleware` validates equality on writes. `X-CSRF-Token` is in the backend CORS `allow_headers` list. T173 OWASP Top 10 review closed an A07 wiring gap before launch (cookie-reader added to api-client.ts; `X-CSRF-Token` added to CORS `allow_headers`) — see [docs/security-review.md](../../docs/security-review.md). |
<!-- CR-001: Compliance — streaming-ToS row removed -->
<!-- sync-fix L6-007 (Run #12): /legal/{privacy,terms} placeholder pages anchored — shipped Session 24 (T161). -->
| Compliance | GDPR (export + erasure). Legal placeholder pages at `/legal/privacy` + `/legal/terms` (standalone routes, no app/auth chrome) with prominent `<aside>` banner: "🚧 This is a placeholder. Final policy lawyer-reviewed before public launch." Footer links from `(auth)/layout`. PostHog page-view events. |
<!-- CR-001: rate-limit row reframed for MusicBrainz primary + Discogs fallback -->
| Catalog rate limits | MusicBrainz rate limit 1 req/sec per IP (server-side enforced); use Atlas Search cache for read-heavy paths; Discogs fallback governed by its own quota (server-side circuit breaker + retry-with-jitter) |
| i18n / l10n | English-only at MVP; copy strings extracted to keys |
| Mobile responsiveness | Mobile-first; PWA installable; breakpoint 768px |
| SEO | Album detail + profile pages SSR with Open Graph meta; everything else CSR acceptable |
| Observability | Every external API call logged with provider/latency/status; Sentry for errors; PostHog for product analytics; daily metrics ETL |

<!-- sync-fix L6-009 (Run #13): anchor S26 §18 audit output doc files (a11y / perf / security / compliance) — load-bearing for NFR claim ↔ evidence pairing. -->
### Verification evidence (S26 §18 audit outputs)

Each measurable NFR pairs with an audit artifact produced during §18 Pre-launch hardening (Session 26):

- **NFR Accessibility** → [docs/a11y-audit.md](../../docs/a11y-audit.md) — `@axe-core/playwright` scans (wcag2aa tag set) across 23 routes; 0 CRITICAL after fixes landed in feed-list.tsx + diary-list.tsx; 4 SERIOUS/MODERATE flagged as Phase 9 follow-ups (T171).
- **NFR Performance** → [docs/perf-audit.md](../../docs/perf-audit.md) — 4 k6 scripts at `apps/api/tests/perf/k6_*.js` (smoke / soak / spike / stress) + Lighthouse Playwright spec at `apps/web/tests/perf/lighthouse.spec.ts`; budgets mirror §6.1 thresholds. Some staging metrics N/A pending T175 staging provisioning (T172).
- **NFR Security** → [docs/security-review.md](../../docs/security-review.md) — OWASP Top 10 review; 1 HIGH (A07 CSRF wiring) closed pre-launch; 0 CRITICAL/HIGH open; 2 LOW follow-ups documented for post-launch (T173).
- **NFR Compliance** → [docs/launch-checklist.md](../../docs/launch-checklist.md) §10 (known-issues consolidation) + [docs/launch.md](../../docs/launch.md) (M0 launch ceremony, T-72h → T+72h timeline + acceptance gates) (T179 + T180).

## 6.1 NFR Measurement Contract

> Every NFR has a measurable signal. Without this, the NFR cannot be verified.

| NFR | How to Measure | Signal / Query | Threshold |
|---|---|---|---|
| p95 home feed load | PostHog `pageview.duration_ms` on `/` | p95 over trailing 7d windows, per-device-class | <500ms |
| p95 album detail load | PostHog `pageview.duration_ms` on `/album/*` | p95 over trailing 7d | <400ms |
<!-- CR-001: streaming-import p99 row removed (FR-003 deferred) -->
| Uptime | Synthetic check + Sentry availability monitor | Monthly uptime % | ≥99.5% |
<!-- CR-001: streaming-API error-rate row replaced with catalog-API error rate -->
| Catalog API error rate | Backend trace counter `catalog.api.4xx + 5xx / total` (MusicBrainz primary + Discogs fallback) | per-5-min window | <2% |
| Notification rate per user | Backend counter — notifications dispatched per user per week | trailing 7d, p95 | <12 (excluding digest) |
| Report → resolution time | Admin event `report.resolved.at - report.created.at` | median across active reports | <72h |
| Account deletion rate | Backend counter `account.deletion.confirmed / MAU` | per calendar month | <1% |
| Accessibility — WCAG AA | axe-core automated audit + manual keyboard nav test | Per-screen audit on every release | 0 violations |
| Coverage — engineering tests | CI test coverage report | Per-module (see §10) | per-module target |
| Mobile-touch-target ≥44pt | Lint rule + manual audit on log sheet + rating widget | Pre-release audit | 0 failures |

---

## 7. Technical Context

> Detailed analysis: [research/codebase-analysis.md](./research/codebase-analysis.md), [research/tech-stack.md](./research/tech-stack.md)

### Integration points

<!-- CR-001: external integrations reframed — MusicBrainz primary + Discogs fallback; streaming-platform integration deferred -->
**Greenfield project** — no existing application code; the project root is Spec Kit scaffolding only. All integration points are NEW modules. **MusicBrainz** is the primary catalog integration with **Discogs** as a fallback for obscure pressings. Streaming-platform integration is **DEFERRED-TO-V2 (CR-001)** — the `MusicProvider` Protocol abstraction is retained (per CR-001 decision #3) so v2 integration is a single new implementation without architectural rework. MVP ships **one impl per provider kind**: one `CatalogProvider` chain (MusicBrainz → Discogs) and zero active `MusicProvider` impls (Protocol defined, no production impl).

### Reusable components

None — greenfield. Phase 5 plan must establish a project structure from scratch.

### New modules required (sketch — Phase 5 finalizes)

| Layer | Module | Responsibility |
|---|---|---|
<!-- CR-001: auth module — OAuth-flows-mentioning-streaming-platform reduced to email/password only at MVP -->
| Backend | `auth` | Email + password sign-up and login flows, session management, handle policy enforcement (streaming-platform OAuth flow **deferred to v2** with FR-002) |
<!-- CR-001: providers/spotify module replaced with providers/musicbrainz primary + providers/discogs fallback behind CatalogProvider Protocol -->
| Backend | `providers/musicbrainz` | All MusicBrainz API calls behind a `CatalogProvider` Protocol; release-group MBID lookup + reconciliation; album catalog fetch; 1 req/sec rate-limit handling |
<!-- CR-001: new module for Discogs fallback -->
| Backend | `providers/discogs` | Fallback `CatalogProvider` impl for obscure pressings not in MusicBrainz; quota-aware retry-with-jitter |
<!-- CR-001: MusicProvider Protocol retained but no production impl at MVP -->
| Backend | `providers/_base` | `MusicProvider` + `CatalogProvider` Protocols (kept per CR-001 decision #3); MVP ships zero `MusicProvider` impls, two `CatalogProvider` impls (MusicBrainz, Discogs) |
<!-- CR-001: albums identity now MBID-only at MVP -->
| Backend | `albums` | Canonical Album records; identity normalization (MBID canonical at MVP; streaming-platform-ID fallback **deferred to v2**); cache TTL; Edition aggregation |
| Backend | `diary` | DiaryEntry CRUD; visibility evaluation; soft-delete + 30d grace; relisten support |
| Backend | `reviews` | Review CRUD; markdown-safe rendering; edit history (90d internal); like-toggle + likes_count denormalization |
| Backend | `backlog` | Per-user Backlog + BacklogItem; auto-remove-on-log behavior |
| Backend | `social` | Follow / unfollow; block; suggested follows job; mutual-taste scoring |
| Backend | `feed` | Home feed read (fan-out-on-read at MVP); weighted ordering; "Latest" toggle |
| Backend | `notifications` | Dispatcher; per-channel adapters (in-app, email, push); coalescer + rate-limit; weekly digest job |
<!-- CR-001: prompts module deferred — JustFinishedPrompt cluster moved to v2 -->
| Backend | `prompts` | **DEFERRED-TO-V2 (CR-001)** — JustFinishedPrompt lifecycle depends on streaming-platform listening-history API. Module spec retained for v2 plan. |
| Backend | `seeding` | CriticSeed roster; pre-checked card ordering; analytics on opt-out rate |
| Backend | `moderation` | Report queue; daily-log-scan for ≥3-report threshold |
<!-- CR-001: search module reframed — Atlas + MusicBrainz live + Discogs fallback (no streaming-platform search) -->
| Backend | `search` | Atlas Search index over a cached MusicBrainz subset; live MusicBrainz lookup on cache-miss; Discogs fallback for obscure pressings |
<!-- sync-fix L3-041 (Run #12): `data-export` row removed (folded into `users` + `gdpr` + `workers/gdpr_export.py` since Session 24); 3 new module rows added below. -->
| Backend | `users` | Profile + privacy + account self-service. `change_handle`, `schedule_deletion`, `cancel_deletion`, `request_data_export` (T153 — returns 202), `get_user_profile`, `patch_me` (T145), `post_avatar` (T146 — R2 upload + Pillow LANCZOS resize 256/128/64), `put_privacy` (T147), `get_my_follow_requests` + `post_approve_follow_request` + `post_decline_follow_request` (T148), `post_change_email` (T150 — current_password + session_version bump), `post_change_password` (T150 — `validate_password_policy` reuse + N-017 dispatch) |
| Backend | `gdpr` | Internal-only. `record_gdpr_event(user_id, action, notes, *, completed)` helper (T154) called from T058 cascade + T153 enqueue/complete paths; no public HTTP routes (audit log is internal). |
| Backend | `reports` | Public `POST /reports/{user,review,diary-entry,album}` (T155 / T163a / T167). Idempotent within 24h on `(reporter_id, target_type, target_id)`; self-report rejected with 422; FK-validated; per-reporter 10/day rate-limit. Internal `acknowledge_report` helper (T157) invoked by `apps/api/scripts/acknowledge_report.py` CLI. |
<!-- CR-001: app/(auth) module — OAuth-redirect path deferred -->
| Frontend | `app/(auth)` | Sign-up + login (email/password); OAuth redirect deferred to v2 with FR-002 |
<!-- CR-001: onboarding flow reframed signup → handle → follow ≥3 critics → critic-seed feed -->
| Frontend | `app/(onboarding)` | Streamlined flow: signup → handle → follow ≥3 critics → critic-seed feed (no music-service auth step at MVP) |
| Frontend | `app/(feed)` | Home feed; "Latest" toggle; entry cards |
| Frontend | `app/album/[id]` | Album detail; Edition chip; sortable reviews; friends section |
| Frontend | `app/profile/[handle]` | Profile; diary; filters (Aux'd, public-only). Public `/@handle` URL deferred to a middleware-rewrite task; see plan §7.1.1. |
| Frontend | `app/up-next` | Backlog UI |
| Frontend | `app/settings/*` | Profile, privacy, notifications, integrations, data |
| Frontend | `components/log-sheet` | THE wedge interaction; bottom-sheet; ½-star widget; Aux + review |
| Frontend | `components/just-finished-prompt` | In-app prompt surface; opt-out menu |
| Shared | `lib/visibility-check` | Single source of truth for visibility evaluation across all surfaces |

### Data model impact

<!-- CR-001: active-entity count drops MVP-active count to 15 (JustFinishedPrompt deferred); schema row kept in table for v2 traceability -->
<!-- sync-fix L2-016 (Run #4): entity count corrected — was "16 entities listed; 15 active". MusicProvider sub-doc + JustFinishedPrompt are both DEFERRED-TO-V2 per CR-001; 16 in schema, 14 active at MVP. -->
16 entities listed below; **14 active at MVP** (MusicProvider sub-doc + JustFinishedPrompt are both **deferred to v2 per CR-001** but preserved in schema for forward compat). See [product-spec/data-model.md](./product-spec/data-model.md) for field-level sketch; count reconciled with ReviewLike in sync-verify Run #2; ReviewLike count holds. Final indexes + collection layout in Phase 5.

| Entity | Notes |
|---|---|
<!-- CR-001: User/MusicProvider — embedded music_providers retained for v2; auto_prompt_enabled flag scoped to v2 cluster -->
| User, MusicProvider | Embedded music_providers (schema kept for v2 — no production impl at MVP per CR-001); encrypted tokens; auto_prompt_enabled flag **deferred to v2 (CR-001)** |
<!-- CR-001: Album identity simplified to MBID canonical only at MVP (Spotify ID fallback deferred) -->
| Album | MBID canonical at MVP (streaming-platform ID fallback **deferred to v2 (CR-001)**); 7d cache; tracklist denormalized at MVP |
| DiaryEntry | The central activity record; `auxed` boolean (renamed from `hearted` in R1); soft-delete 30d |
| Review | 1:1 optional with DiaryEntry; `reactions.likes_count` (R3 rename); 90d edit-history retained internally |
| ReviewLike *(new in R3)* | Per-user-per-review like records for idempotent toggle and Most Liked sort |
| Backlog, BacklogItem | Singleton per User; private by default |
| Follow, Block | Asymmetric follows; cascading dissolve on block |
| Report | Open / reviewing / actioned / dismissed; 90d resolution audit |
<!-- sync-fix L2-017 (Run #5): 14 active post-CR-001 (was 18); 4 deferred (N-009/010/011/018) + 2 R3-reserved (N-019/020). -->
<!-- sync-fix L2-028 (Run #11): count bumped 14 → 16; N-009/N-010 are registered with all defaults OFF per CR-001 deferral rather than removed from the enum. -->
| Notification, NotificationPreferences | 16 active notification types (N-009 / N-010 registered with all defaults OFF per CR-001 deferral) + 4 reserved-gap IDs (N-011, N-018, N-019, N-020); per-channel + quiet-hours |
<!-- sync-fix L2-030 (Run #11): PushSubscription entity added — shipped in Session 20 (T136 WebPush adapter). -->
| PushSubscription | Per-device VAPID push registration. 410-Gone deletes dead sub on send. Indexed (user_id, endpoint UNIQUE). |
<!-- sync-fix L2-032 (Run #12): GdprAuditLog entity added — shipped in Session 24 (T154 record_gdpr_event helper). -->
| GdprAuditLog | Per-action audit row for GDPR export + deletion lifecycle. Indexed (user_id, requested_at DESC); 7-year retention deferred to operator config. |
<!-- CR-001: JustFinishedPrompt entity deferred — cluster moves to v2 with streaming integration -->
| JustFinishedPrompt *(new in R1)* | **DEFERRED-TO-V2 (CR-001)** — Pending / dismissed / logged / expired lifecycle; entity schema kept in spec for v2 planning, not implemented at MVP. |
| SuggestedFollow | Precomputed offline; dismissed exclusion 30d |
| CriticSeed | Editorial roster; `active` toggle; priority ranking for Follow-3 |

### Tech stack notes

| Layer | Recommended at Phase 1 research | Confirmation owed in Phase 5 |
|---|---|---|
| Frontend build + framework | Next.js 15 App Router (SSR critical for OG previews + SEO) | Lock or substitute Vite + React Router |
| Frontend state | TanStack Query + Zustand | Confirm at plan |
| Frontend UI kit | shadcn/ui | Confirm at plan |
| Backend framework | FastAPI async (Pydantic v2) | Locked by config |
| Backend ODM | Beanie (async, Pydantic-native) | Confirm — vs PyMongo raw |
| Auth | Authlib or fastapi-users | Final pick at plan |
| Background jobs | arq + Redis (research recommended over Celery for FastAPI-native async) | Confirm |
| Database | MongoDB Atlas | Locked by config |
| Search | Atlas Search (native to MongoDB Atlas) | Locked |
<!-- CR-001: cover-art source migrates to Cover Art Archive (MusicBrainz-linked) + Discogs image URL fallback; no streaming-platform CDN at MVP -->
| Cover-art | Cover Art Archive (MusicBrainz-linked) primary + Discogs image URL fallback; no S3 cache. (Original DM-2 streaming-CDN-proxy decision **superseded by CR-001**.) | Locked (revised CR-001) |
| Recommendation engine | Heuristic social-graph at MVP; no ML/ALS | Locked (ALS deferred to v2) |

### Codebase constraints

| Constraint | Source | Impact on design |
|---|---|---|
| Constitution gap | `.specify/memory/constitution.md` is template-only | **Phase 5 MUST** ratify principles as Task 0 before any feature work |
<!-- CR-001: provider abstraction reframed — MusicProvider Protocol kept (per CR-001 decision #3); CatalogProvider added -->
| Provider-interface abstraction | Decision-log structural decisions + CR-001 #3 | Every external API call goes through a typed Protocol (`MusicProvider` for streaming, `CatalogProvider` for catalog); MVP ships one `CatalogProvider` chain (MusicBrainz → Discogs) and zero `MusicProvider` impls. Protocol retained so v2 streaming integration is additive. |
<!-- CR-001: album-identity normalization simplified — MBID canonical only at MVP -->
| Album-identity normalization | Decision Q15 (revised CR-001) | All album references resolve through MBID-canonical at MVP; streaming-platform-ID fallback deferred to v2. Cascades through search, dedup, analytics. |
<!-- CR-001: external-call resilience now scoped to MusicBrainz + Discogs -->
| External-call resilience | Recommended principle from research | Retry + timeout + circuit breaker on every MusicBrainz + Discogs call; respect 1 req/sec MusicBrainz IP limit. |
| Schema versioning | Recommended principle | Every Mongo document carries `_schema_version` int |
<!-- CR-001: test-first scope narrowed — auth + catalog edges only at MVP -->
| Test-first for catalog + auth edges | Recommended principle | Contract tests for MusicBrainz + Discogs integrations + email/password auth flow before implementation. |
| Observability mandatory | Recommended principle | Every external call logged with provider/latency/status |
<!-- CR-001: Extended Quota Mode row removed from MVP critical path — no longer a gating dependency -->
| ~~Streaming-platform Extended Quota Mode~~ | ~~External dependency~~ | **REMOVED-AT-MVP (CR-001)** — no streaming-platform integration at MVP; gating dependency eliminated. Row preserved (struck through) for audit trail. |

---

## 8. Acceptance Criteria (global)

The feature is complete when:

<!-- CR-001: AC #1 — Must-Have count drops; US-A2/A3/B6 deferred -->
1. All Must-Have user stories that remain in scope at MVP pass their G/W/T acceptance criteria (US-A2, US-A3, US-B6 are **DEFERRED-TO-V2 (CR-001)** and are not counted against MVP completion).
2. Wireframes match implementation within acceptable visual deviation (designed on PWA-default styles).
3. Performance NFRs are met as measured by the NFR Measurement Contract (§6.1).
4. WCAG 2.1 AA passes automated (axe-core) + manual keyboard-nav audit on every screen.
<!-- CR-001: AC #5 — Extended Quota Mode dependency removed at MVP -->
5. **REMOVED-AT-MVP (CR-001)** — *Original: Extended Quota Mode is approved and the production app is operating outside Development Mode quotas.* No streaming-platform gating dependency at MVP.
6. Constitution is ratified at `.specify/memory/constitution.md` (per Phase 5 Task 0).
7. Critic-seed roster: ≥25 active seed accounts onboarded pre-public-launch (per [seeding-strategy.md](./product-spec/seeding-strategy.md) playbook).
8. Notification rate-limits and quiet hours are verified end-to-end (no Goodreads-firehose regressions).
<!-- CR-001: AC #9 — streaming-platform OAuth + import + prompt flows deferred -->
9. **DEFERRED-TO-V2 (CR-001)** — *Original: streaming-platform OAuth + auto-import + just-finished prompt flows verified with ≥5 real user-side tests.* Returns when streaming-platform integration ships in v2.
<!-- CR-001: AC #10 — disconnect flow moot at MVP -->
10. **DEFERRED-TO-V2 (CR-001)** — *Original: disconnect → diary immutability is verified.* Moot at MVP (no streaming-platform connect path); returns with v2 integration.
11. Aux (🏅) vs Like (👍) semantics are consistent: never confused in UI, copy, notifications, or API.
<!-- CR-001: new AC for catalog-search resilience at MVP -->
12. Manual catalog search end-to-end is verified: MusicBrainz hit → Discogs fallback on miss → "Report missing album" workflow on empty result (FR-033).

---

## 9. Success Metrics

> Full metrics + benchmarks: [product-spec/success-metrics.md](./product-spec/success-metrics.md), [research/metrics-roi.md](./research/metrics-roi.md)

**Primary KPI (North Star):** Weekly Active Loggers (WAL) — unique users who logged ≥1 album AND opened the app in trailing 7 days.

| Metric | M3 target | M6 target |
|---|---|---|
| WAL (North Star) | 500 | 2,500 |
| W1 activation rate (new signups logging ≥3 albums in first week) | 30% | 35% |
| D30 retention | 8% | 12% |
<!-- CR-001: social-originated metric reframed — no streaming-platform deep-link at MVP; measure social-originated album-detail opens instead -->
| Social-originated album-detail opens (album-detail page opened from feed or friend surface vs profile/search) | 25% | 40% |
| Reviews per WAL | 0.5 | 0.8 |
| Follow graph density (median follows per WAL) | 5 | 12 |
| Backlog → Log conversion (within 30d of add) | 30% | 45% |

**Pivot threshold:** If M3 WAL is <250 (50% of target) AND D30 retention is <5%, run a pivot/iterate decision meeting (per problem-discovery digest — H1 user-research validation is still open until live signal confirms).

---

## 10. Testing Specification

> Testing strategy is finalized in Phase 8A (test-plan); this section gives Phase 5 the targets to design around.

### Coverage targets

| Module / Service | Target | Type |
|---|---|---|
<!-- CR-001: provider coverage retargeted to MusicBrainz + Discogs (streaming-platform provider deferred) -->
| `providers/musicbrainz` + `providers/discogs` | ≥85% | unit + integration (contract tests against MusicBrainz + Discogs sandboxes); streaming-platform provider **DEFERRED-TO-V2 (CR-001)** |
<!-- CR-001: albums coverage — only MBID-canonical path at MVP -->
| `albums` (identity normalization) | ≥85% | unit (MBID canonical path; Edition aggregation; streaming-platform fallback path **deferred to v2 (CR-001)**) |
| `diary` + `reviews` | ≥80% | unit + integration |
| `social` (follow, block, suggestions) | ≥80% | unit + integration |
| `feed` (weighted ordering) | ≥80% | unit + property tests on weight calc |
| `notifications` + `prompts` | ≥80% | unit (rate-limiter, coalescer, quiet-hours) + integration |
| `lib/visibility-check` | ≥95% | unit (visibility matrix is load-bearing) |
| `seeding` | ≥75% | unit + manual seeding integration |
| Frontend components (log-sheet, prompts, feed cards) | ≥75% | unit (RTL) + visual regression |
| E2E (Playwright) | smoke + critical journeys | per §10.E2E |

### Critical test cases

| # | Scenario | Expected | Type |
|---|---|---|---|
| TC-001 | Log + ½-star + Aux an album in <8 seconds (server-measured) | DiaryEntry created with all three; commit time recorded | integration |
| TC-002 | Log without rating (just confirm album) | Entry saves with null rating, null Aux; no errors | unit |
| TC-003 | Re-log same album | Two DiaryEntry records with different `logged_at`; both visible in user's diary | integration |
<!-- CR-001: TC-004/005/006 deferred — streaming-platform OAuth/import flows out at MVP -->
| TC-004 | **DEFERRED-TO-V2 (CR-001)** — *Original: streaming-platform OAuth with all required scopes.* | n/a at MVP | integration |
| TC-005 | **DEFERRED-TO-V2 (CR-001)** — *Original: streaming-platform OAuth with permission denied for one scope.* | n/a at MVP | integration |
| TC-006 | **DEFERRED-TO-V2 (CR-001)** — *Original: 30-day streaming-platform import with 50+ albums.* | n/a at MVP | integration |
<!-- CR-001: TC-007 retargeted to MusicBrainz/Discogs rate-limit handling -->
| TC-007 | MusicBrainz 503 / 429 (rate limit) + Discogs fallback 429 | Per-provider circuit-breaker engages; retry-with-jitter applied; client sees friendly degradation; "Report missing album" still works | unit + integration |
<!-- CR-001: TC-008 narrowed to MBID-canonical only at MVP -->
| TC-008 | Album with MBID; same album discovered via Discogs fallback | Canonical Album record keyed on MBID; Discogs result reconciles to MBID where possible; subsequent lookups reuse | unit |
| TC-009 | Album with no MBID (fresh release) | Candidate record created; reconciles when MusicBrainz updates | unit + integration |
| TC-010 | Multi-edition album (Standard + Deluxe + Bonus) | Single canonical record; Edition selector aggregates ratings/reviews/likes across editions | unit |
| TC-011 | Public diary entry, viewer follows owner | Entry visible | unit (visibility matrix) |
| TC-012 | Followers-only entry, viewer NOT following | Entry hidden | unit |
| TC-013 | Private entry, viewer != owner | Entry hidden | unit |
| TC-014 | Entry on blocked-by owner, viewer is the blocker | Entry hidden | unit |
| TC-015 | Like a review (idempotent toggle) | First tap creates ReviewLike + increments counter + N-004; second tap removes both, no N-004 | unit + integration |
| TC-016 | Like own review | UI disabled with tooltip; API rejects | unit |
| TC-017 | Sort reviews by Most Liked | Result order matches `reactions.likes_count` desc within tier | unit |
<!-- CR-001: TC-018 deferred — depends on streaming-platform listening-history API -->
| TC-018 | **DEFERRED-TO-V2 (CR-001)** — *Original: just-finished detection via streaming-platform recently-played.* | n/a at MVP | integration |
| TC-019 | Just-finished during quiet hours | No push; in-app prompt deferred to next non-quiet open | integration |
| TC-020 | Per-album auto-prompt dismissal | Same album does not re-prompt for 30 days | unit |
| TC-021 | User disables auto-prompts | No prompts surface even if detection fires | unit |
<!-- CR-001: TC-022 deferred — disconnect path moot at MVP -->
| TC-022 | **DEFERRED-TO-V2 (CR-001)** — *Original: streaming-platform disconnect → diary immutability; auto-import + prompt + prefill stop; reconnect without back-fill.* | n/a at MVP | integration |
| TC-023 | Handle change during 30-day lock | API rejects; UI shows next-available date | unit |
| TC-024 | Reserved-squat handle claim | API rejects; verification flow link shown | unit |
| TC-025 | Review edit | Latest version public; "edited" badge; 90d internal history written | unit + integration |
| TC-026 | Notification coalescing | Multiple follows from same actor in 24h collapse | unit |
| TC-027 | Weekly digest cron | Fires Monday 09:00 user-local; respects user TZ; ignores quiet hours | integration |
| TC-028 | Block dissolves existing follow | Both directions resolved; entries no longer visible | unit + integration |
| TC-029 | Account deletion → 30d grace → hard delete | Banner shown; cancel works; cascade deletes all owned content after 30d | integration |
| TC-030 | GDPR export | JSON + CSV emailed within 24h with all owned content | integration |
| TC-031 | Atlas Search returns relevant album | Top result matches typed query within 200ms debounce | integration |
| TC-032 | Visibility check function (matrix) | All 16 (visibility × viewer-relationship) combinations return correct boolean | unit (property test) |

### E2E scenarios (Playwright)

| TC-ID | Scenario | Entry | Exit |
|---|---|---|---|
<!-- CR-001: TC-E2E-001 deferred — streaming-connected onboarding path moves to v2 -->
| TC-E2E-001 | **DEFERRED-TO-V2 (CR-001)** — *Original: full onboarding with streaming-platform connected.* | n/a at MVP | n/a at MVP |
<!-- CR-001: TC-E2E-002 retargeted as THE canonical MVP onboarding flow (signup → handle → follow ≥3 critics → critic-seed feed) -->
| TC-E2E-002 | Full onboarding (MVP canonical: signup → handle → follow ≥3 critics → critic-seed feed) | Landing page direct | Home feed with ≥5 critic-seed entries |
| TC-E2E-003 | Log + rate + Aux + review an album in <25s | Home feed | Entry visible in diary |
<!-- CR-001: TC-E2E-004 deferred — streaming-platform deep-link removed at MVP -->
| TC-E2E-004 | **DEFERRED-TO-V2 (CR-001)** — *Original: discover album via social feed → streaming-platform deep-link.* | n/a at MVP | n/a at MVP |
| TC-E2E-005 | Like a review → reviewer sees N-004 notification | Album detail page | Notification visible in reviewer's session |
| TC-E2E-006 | Sort reviews by Most Liked | Album detail | Result order changes; persistence across reload |
| TC-E2E-007 | Add album to Up Next, later log it, verify auto-remove | Album detail | Backlog reflects removal; toast confirms |
<!-- CR-001: TC-E2E-008/009 deferred — Just-finished prompt cluster moves to v2 -->
| TC-E2E-008 | **DEFERRED-TO-V2 (CR-001)** — *Original: just-finished prompt appears + log from prompt.* | n/a at MVP | n/a at MVP |
| TC-E2E-009 | **DEFERRED-TO-V2 (CR-001)** — *Original: Settings → disable auto-prompts → verify no prompts.* | n/a at MVP | n/a at MVP |
| TC-E2E-010 | Edit profile + change handle (after 30d lock) | Settings → Profile | Handle changes; old URL redirects |
| TC-E2E-011 | Block a user → verify content hiding both ways | Other user's profile | Profile shows "Blocked"; content hidden |
| TC-E2E-012 | Export data → receive email with JSON+CSV | Settings → Data | Email received (mocked); contains diary + reviews |
| TC-E2E-013 | Delete account → 30d cancel flow | Settings → Data | Banner; cancellation restores account |

---

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| H1 (user-research validation) never confirms | High | Run the [interview script](./problem-discovery/interview-script.md) during early-access wave; treat first 8 weeks of live metrics as the real validation gate; M3 pivot/shutdown decision point if WAL <50% of target |
<!-- CR-001: streaming-platform API-deprecation risk re-scoped — risk applies only post-v2 -->
| Streaming-platform API terms change / endpoint deprecation | Low at MVP / Medium at v2 | Risk is dormant at MVP (no streaming integration); `MusicProvider` Protocol kept ready so v2 integration is additive. **CR-001 (2026-05-22)** demoted this risk from High → Low at MVP. |
<!-- CR-001: Extended Quota Mode risk eliminated at MVP -->
| ~~Extended Quota Mode application denied or stuck~~ | ~~Medium~~ | **REMOVED-AT-MVP (CR-001)** — Extended Quota Mode requires 250k MAUs and is unreachable pre-launch; streaming-platform integration deferred to v2. Risk row preserved (struck through) for audit. |
| Cold-start ghost-town — seed graph doesn't compound | High | Seeding strategy launched as a project alongside the product, not a marketing afterthought; founder-curated critic seed must be live before public access |
<!-- CR-001: cold-start ghost-town risk amplified — first-session non-empty now depends ENTIRELY on critic seed (no streaming fallback) -->
| Cold-start critic-seed under-delivery | High (new at CR-001) | First-session non-emptiness now depends *entirely* on critic-seed activity (no streaming auto-import fallback); seeding-strategy.md targets MUST be hit pre-public-launch. CR-001 raises the criticality of pre-launch critic recruitment. |
| Notification firehose drives churn (Goodreads pattern) | High | Conservative defaults; granular per-type per-channel toggles; weekly digest primary mode |
<!-- CR-001: music metadata quality mitigation reframed — MBID canonical, Discogs fallback, FR-033 user report -->
| Music metadata quality | Medium | MBID canonical via MusicBrainz; Discogs fallback for obscure pressings; Edition selector merges deluxe/remasters; FR-033 "Report missing album" user surface |
| Privacy / safety incident | High | Block + report from MVP; private-profile toggle; rate-limit follows; explicit ToS |
<!-- CR-001: search-relevance mitigation reframed — Atlas-cached MusicBrainz + live MusicBrainz + Discogs three-tier -->
| Search returns irrelevant results | Medium | Three-tier search: Atlas Search (cached MusicBrainz subset) → live MusicBrainz on cache-miss → Discogs fallback; iterate index after launch; "Report missing album" closes the loop on empty results |
| Performance regression at 5k+ users due to feed fan-out | Medium | Fan-out-on-read at MVP; switch to fan-out-on-write only if p95 >200ms; load-modeling in Phase 5 |
| Content moderation load exceeds founder bandwidth | Medium | Daily log-scan workflow at MVP; cap feature growth; ToS + guidelines clear from day one |

---

## 12. Open Questions

**0 open questions remain at spec level.** All 30 questions surfaced through Phase 3 have been resolved as locked decisions (see [decision-log.md](./product-spec/decision-log.md) Q1–Q22 + NT-1..5 + SS-1..5 + DM-1..5 + UJ-1..5).

Phase 5 (plan) will surface **technical** decisions (fan-out load model, Atlas Search index tuning, auth library final pick, background-job runner, hosting/deployment target, cover-art proxy headers, observability stack composition, GDPR audit-log schema). Those are not spec-level; they're listed in [decision-log.md §Decisions deferred to Phase 5](./product-spec/decision-log.md).

---

## 13. Required Reading for Phase 5

Phase 5 (plan) **must** read these supporting docs in addition to this spec.md:

1. [product-spec/decision-log.md](./product-spec/decision-log.md) — the 45+ locked decisions with rationale (THE source of truth on choices)
<!-- sync-fix L2-016 (Run #4): mirror of the §7 count correction — 14 active, 2 deferred-to-v2 in schema. -->
2. [product-spec/data-model.md](./product-spec/data-model.md) — 14 active entities (+2 v2-deferred-but-schema-preserved) + relationships + preliminary indexes
<!-- sync-fix L2-017 (Run #5): mirror of the §4 + §13 count corrections. -->
3. [product-spec/notification-taxonomy.md](./product-spec/notification-taxonomy.md) — 14 active notification types (+ 6 reserved-gap IDs) with defaults (load-bearing — wrong notification design = Goodreads-style churn)
4. [product-spec/seeding-strategy.md](./product-spec/seeding-strategy.md) — 4-pronged cold-start playbook (launch infrastructure, not marketing)
<!-- CR-001: tech-stack reading reframed — original Extended Quota Mode dependency superseded by CR-001 -->
5. [research/tech-stack.md](./research/tech-stack.md) — streaming-platform API audit (H4 critical findings) is **historical context only** at MVP per CR-001; current catalog stack is MusicBrainz primary + Discogs fallback (no Extended Quota gate to clear).
6. [research/codebase-analysis.md](./research/codebase-analysis.md) — greenfield analysis + recommended constitution principles

Phase 5's Task 0 should be: **Ratify the project constitution** (currently template-only) with the 5 recommended principles from research/codebase-analysis.md or a founder-defined alternative.

---

## 14. Document History

This spec.md is generated from a product-spec that went through 3 revisions in Phase 3:

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2026-05-21 | Initial product-spec from Phase 2 |
| v1.1 | 2026-05-21 | R1: Lists + Auto-prompt elevated to MVP; Spotify skippable; Heart → Aux rename |
| v1.2 | 2026-05-21 | R2: All 30 open questions resolved with locked decisions; FRs 028–030 added |
| v1.3 | 2026-05-21 | R3: Removed "say more" prompt; split Aux (🏅 self) / Like (👍 social); added Likes + sort; reverted Lists to v2; FRs 031–032 added; ReviewLike entity added |
| **spec.md** | **2026-05-21** | **Generated by Phase 4 Bridge from product-spec v1.3** |
<!-- CR-001: change-request row appended -->
| **CR-001** | **2026-05-22** | **All streaming-platform integration deferred to v2 (Extended Quota Mode now requires 250k MAUs — structurally unreachable pre-launch). MVP becomes Letterboxd-style manual search via MusicBrainz primary + Discogs fallback. US-A2/A3/B6 deferred; FR-002/003/017/026/027 deferred; FR-033 added (Report missing album); JustFinishedPrompt cluster deferred; MusicProvider Protocol kept for v2 additive integration. Decision row #18 added to §0.** |
