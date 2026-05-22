# Spec: Spinz MVP — Social Album Platform

> **Product Forge Feature** | Generated: 2026-05-21
> Feature slug: `001-spinz-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - Product Spec: [product-spec/README.md](./product-spec/README.md) (locked at v1.3, approved after 3 revisions)
> - Research: [research/README.md](./research/README.md)
> - Problem Discovery: [problem-discovery/problem-statement.md](./problem-discovery/problem-statement.md)
> - Decision Log (45+ locked decisions): [product-spec/decision-log.md](./product-spec/decision-log.md)
> - Review Log: [review.md](./review.md)

---

## 0. Locked Decisions Carried From Product Spec (read first)

These 17 decisions are non-negotiable inputs to Phase 5 (plan). Each links back to [decision-log.md](./product-spec/decision-log.md) for rationale.

1. **Spotify-only at launch** (Apple Music = v2)
2. **½-star rating scale** (Letterboxd model)
3. **Auto-prompt for just-finished albums** ENABLED at MVP (opt-out, default ON)
4. **Public-by-default privacy** with per-entry visibility override
5. **Lists DEFERRED to v2** *(elevated in R1, returned to v2 in R3 — do NOT include Lists work in Phase 5)*
6. **Onboarding** = Spotify auth + auto-import last 30 days + **prominent Skip option**; skip is a full product, not "degraded mode"
7. **Album identity** = MusicBrainz release-group MBID canonical, Spotify album ID as fallback
8. **PWA + responsive web only** at MVP (no native iOS/Android)
9. **Award (🏅) vs Like (👍) — distinct semantics**: Award is the entry-owner's self-curation signal on their own DiaryEntry; Like is other-user social engagement on a Review. Two icons, two semantics, two data fields, two notification types.
10. **No "say more" soft prompt** on short reviews — reviews can be ≥1 character without a nudge
11. **Reviews are Likeable + sortable** by Newest / Most Liked / Highest-Rated
12. **Critic seeds** appear as PRE-CHECKED checkbox cards on the "Follow 3" onboarding screen (opt-in with default-tick)
13. **Deluxe / remasters** merged under release-group MBID; album detail surfaces an "Edition" chip + dropdown
14. **Diary persists immutably on Spotify disconnect** — reconnect does not back-fill the gap
15. **Reviews edits** allowed; public surface shows latest version + "edited" badge; 90-day internal audit log preserved
16. **Handles** immutable for first 30 days after account creation, then changeable once per 30 days; 200–500 obvious-squat candidates reserved at launch
17. **Spotify OAuth scopes** locked: `user-read-recently-played`, `user-read-currently-playing`, `user-library-read` only at MVP (`playlist-read-private` deferred)

> **Phase 5 prerequisite — Constitution gap:** `.specify/memory/constitution.md` is currently the unfilled template. Phase 5 MUST either run `/speckit.constitution` to ratify principles OR include constitution ratification as Task 0 before any feature work. Recommended principles from [research/codebase-analysis.md](./research/codebase-analysis.md): external-call resilience, schema-versioned documents, library-first modules, test-first for catalog/auth edges, observability mandatory.

---

## 1. Overview

### What we're building

Spinz is a social album-tracking platform for casual Spotify listeners (18–35). Users log albums they've listened to, rate them on a ½-star scale, write optional reviews, "Award" personal standouts in their own diary, "Like" reviews written by others, maintain a private backlog of "want to listen" albums, and discover music via their social graph rather than algorithmic recommendations. Spotify OAuth on day one auto-imports recently-played history so the diary is never empty.

### Why we're building it

Casual streaming-era listeners (18–35) have no low-friction way to record, share, and discover album experiences with people whose taste they trust. Their listening stays passive and ephemeral. The moment of "I just finished a great album" evaporates because there's no native place to capture it that combines album-first context, social-graph (not algorithmic) discovery, and a friction floor low enough for non-power-users.

### The wedge thesis

The *unhad combination* of four things none of the 13 prior Letterboxd-for-music attempts combined: **auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding** — all four simultaneously. Spotify's deprecation of audio-features / recommendations / related-artists endpoints (2024-11-27) makes the social-graph thesis the only viable rec path; there's no algorithmic-rec fallback available.

### Research backing

This spec is backed by a full research phase (Phase 1) covering:

- **Competitors:** 13 competitors analyzed; six concrete causes identified for why prior Letterboxd-for-music attempts (RYM, AOTY, MusicBoard, Albums.fm, hi-fi.cafe, Sonemic) stalled. The combinatorial gap is open.
- **UX/UI:** Letterboxd's bottom-sheet log + ½-star + heart + optional review (sub-8-second commit) is the proven minimum-friction pattern. Goodreads' notification firehose and AOTY/RYM 100-point metadata walls are the documented anti-patterns to avoid.
- **Tech stack:** Spotify Web API social-core endpoints are stable; Extended Quota Mode review (2–6 wk) is on the critical path for public launch. Recommended stack: Next.js 15 App Router + TanStack Query + shadcn/ui (frontend); FastAPI async + Pydantic v2 + Beanie + Authlib + arq/Redis (backend); MongoDB Atlas + Atlas Search.

> Deep-dive: [research/README.md](./research/README.md). All quantitative figures in research are training-data-based (web access was denied during Phase 1) and tagged for Phase 5 spot-check.

---

## 2. Goals

### Primary goal

When a casual listener finishes an album, they can record their reaction (rate, optionally Award, optionally review) in under 8 seconds; that signal compounds into a personal diary and a social-graph feed that surfaces what their trusted circle is listening to — creating a music identity and discovery loop that streaming alone doesn't provide.

### Secondary goals

- Make the first session non-empty via Spotify auto-import of the last 30 days (or critic-seed-only if user skips Spotify).
- Build a trusted social graph through curated critic-seed roster + mutual-taste suggestions + invite mechanics.
- Provide the album-detail surface as a social hub (friends' ratings + Awards, public reviews sortable by Newest / Most Liked / Highest-Rated, Editions).

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

### Primary persona — Casey, the Casual Streamer (24)

Designer/grad-student/early-career professional. Listens to Spotify daily. Has a "music taste" but it lives in their head, screenshots, and a Notes app. Listens to ~2–4 full albums per week (rest is playlist/shuffle). Wants to remember standouts and find what to play next without the algorithm or a 2008-era UI.

**Activation signal:** Casey logs an album within their first session AND returns to log a second album within 7 days.

### Secondary persona — Maya, the Engaged Listener (29)

Music-adjacent professional or hobbyist (musician, writer, podcaster, critic). Tracks albums elsewhere (Notion, RYM, AOTY) but unsatisfied with the social layer. Wants a clean diary, audience, and influence.

**Activation signal:** Maya writes ≥1 review of >50 words within first week; ≥3 followers within first month.

### Tertiary persona — Jamie, the Tastemaker / Critic (31)

Music journalist, label A&R, music podcaster, popular music-Twitter account. Spinz needs Jamies as the **seed graph** for Casey and Maya (see [product-spec/seeding-strategy.md](./product-spec/seeding-strategy.md)).

**Activation signal:** Jamie writes a review on Spinz that ≥10 followers see organically within 24h. Seeding strategy is built around recruiting Jamies pre-launch.

---

## 4. User Stories

> Full G/W/T acceptance criteria for every story: [product-spec/user-stories.md](./product-spec/user-stories.md)
> User journeys / flow narratives: [product-spec/user-journeys.md](./product-spec/user-journeys.md)
> 30 Must-Have, 2 Should-Have, 3 Could-Have *(count reconciled in sync-verify Run #1 — see [sync-report.md](./sync-report.md#drift-l2-003))*

### Must Have (MVP — 30 stories)

**Cluster A — Onboarding and first-session activation**

- [ ] **US-A1** As Casey, I want to sign up in under 60 seconds, so I don't bounce before seeing value. **AC:** Spotify OAuth shortcut OR email/password+handle; auto-handle suggestions on collision.
- [ ] **US-A2** As Casey, I want the option to connect Spotify and auto-import 30 days, OR skip Spotify entirely and still use Spinz fully. **AC:** Prominent Skip; no "degraded mode" framing; settings → Integrations connects later and back-fills.
- [ ] **US-A3** As Casey, I want to rate my standout listens from the past 30 days in <60 seconds. **AC:** Top-5 cards with ½-star widgets; skip allowed; optimistic save.
- [ ] **US-A4** As Casey, I want to follow a starter set during onboarding. **AC:** Mixed cards (≥3 critics in top 6) with critic-seed cards **PRE-CHECKED** by default (Q13); minimum 1 follow to advance.
- [ ] **US-A5** As Casey, my first home feed must be non-empty. **AC:** ≥5 entries; if follow graph sparse, padded with critic-seed activity from past 7 days.

**Cluster B — Logging, rating, Award, auto-prompt**

- [ ] **US-B1** As Casey, I want to log an album in <8 seconds. **AC:** Persistent "+" Log button → bottom sheet with Spotify-prefilled album; rating + Award + review + visibility; commit time measured server-side.
- [ ] **US-B2** As Casey, I want ½-star rating precision (0.5–5.0). **AC:** Tap-between-stars or drag-to-rate; null rating allowed.
- [ ] **US-B3** As Casey, I want to "Award" (🏅) an album in my diary as one of my standouts. **AC:** Toggle independent of rating; "Awards" filter on profile; appears on album detail "Friends who rated & awarded this" surface (Award is **self-directed-only** — not the same as reviewing/liking).
- [ ] **US-B4** As Maya, I want to re-log the same album multiple times. **AC:** New entry; prior entries preserved; album-page shows my full history.
- [ ] **US-B5** As Casey, I want to edit or delete a diary entry. **AC:** Edit rating/Award/review/visibility; soft-delete with 30d recovery; "edited" badge on changed entries.
- [ ] **US-B6** As Casey (Spotify connected), I want a prompt when Spotify detects I just finished an album, so I capture the moment. **AC:** In-app prompt 5–15min after detection; opt-in push; per-album dismissal sticks 30d; quiet hours respected; per-user `auto_prompt_enabled` setting (default ON); one-tap "Disable auto-prompts" from the prompt menu.

**Cluster C — Reviews + Likes + sort**

- [ ] **US-C1** As Maya, I want to write a review after rating. **AC:** Markdown-safe subset; ≥1 char minimum; no "say more" nudge (per R3 decision); save with entry.
- [ ] **US-C2** As Casey, I want to read reviews on an album detail page, sorted by Newest (default) / Most Liked / Highest-Rated. **AC:** Sort selector persists per-device; primary tier = friends, then public, then critic-seed; truncate at ~200 chars with inline expand.
- [ ] **US-C3** As Maya, I want to edit a published review. **AC:** Latest version shown publicly with "edited" badge + hover timestamp; 90-day internal audit log preserved; edit history NOT exposed publicly.
- [ ] **US-C4** As Casey, I want to "Like" (👍) another user's review. **AC:** Idempotent toggle; review's `likes_count` increments; N-004 (`review.liked`) notification to reviewer; cannot like own review.

**Cluster D — Backlog (Up Next)**

- [ ] **US-D1** As Casey, I want to add an album to my private backlog. **AC:** "Add to Up Next" from album detail or Log flow; private by default.
- [ ] **US-D2** As Casey, I want to view/reorder my backlog and deep-link to Spotify. **AC:** Drag-reorder persists; `spotify:album:ID` deep-link.
- [ ] **US-D3** As Casey, I want logged albums auto-removed from backlog. **AC:** Default behavior; per-user `keep_backlog_after_log` setting to override; toast confirms removal.

**Cluster E — Social graph and discovery**

- [ ] **US-E1** As Casey, I want to follow another user. **AC:** Asymmetric follows; existing follow dissolved on block; optimistic count update.
- [ ] **US-E2** As Casey, I want to browse a follower's diary. **AC:** Reverse-chrono, 25/page; followers-only entries hidden from non-followers; private entries always hidden.
- [ ] **US-E3** As Casey, my home feed surfaces signal from my follow graph. **AC:** Reverse-chrono with weight boosts (review-attached +20%, ★★★★★/★ +15%, top-5-interacted users +10%); "Latest" toggle disables weights and persists per-device.
- [ ] **US-E4** As Casey, I want to see "Friends who rated & Awarded" on album pages. **AC:** Avatars + ratings + Award badges (🏅) from followed accounts, sorted by rating desc then date desc.
- [ ] **US-E5** As Casey, the app suggests follows based on taste overlap. **AC:** Suggestion job runs after ≥5 ratings; "Discover" tab; dismissed suggestions excluded for 30d.

**Cluster F — Album detail and catalog**

- [ ] **US-F1** As Casey, the album detail page is the social hub. **AC:** SSR; cover, metadata, tracklist, my history, friends' ratings + Awards, public reviews list (sortable), Log + Up Next CTAs, OG meta. **Edition selector** chip when an album has multiple editions under the same release-group MBID (per Q15 / FR-028).
- [ ] **US-F2** As Casey, I want to search the album catalog. **AC:** Atlas Search (cached) + Spotify search (uncached); ≥3 chars + 200ms debounce; "Report missing album" link on empty result.

**Cluster G — Profile, settings, privacy**

- [ ] **US-G1** As Maya, I want to edit my profile (display name, bio, avatar, handle). **AC:** Optimistic save; **handle policy** (per Q16/FR-029): immutable first 30d; thereafter ≤1 change per 30d; 200–500 obvious-squat reservations at launch; verification flow for reserved-squat claims post-launch.
- [ ] **US-G2** As Casey, I want privacy defaults (per-entry visibility, private profile). **AC:** Default visibility setting; private-profile toggle creates pending follow-requests queue; existing followers stay on visibility downgrade.
- [ ] **US-G3** As Casey, I want to manage notifications including auto-prompts. **AC:** 18 active notification types with per-channel toggles; quiet hours config; quiet hours suppress push + in-app prompts, not email/digest.
- [ ] **US-G4** As Maya, I want to block and report. **AC:** Block dissolves existing follow + hides content; report queued with reason; ≥3 reports/7d → daily-log-scan flagging (manual review at MVP, no auto-suspension).
- [ ] **US-G5** As Casey, I want to export my data and delete my account. **AC:** Email JSON+CSV within 24h; 30-day deletion grace period with banner + cancel option.

> Should-Have: US-H1 (Last.fm history import), US-H2 (Album merge / report wrong album), US-H3 (Friend-request flow for private profile), US-H4 (Weekly digest UI improvements), US-H5 (Share-card refinements). Could-Have list in [user-stories.md §Cluster H](./product-spec/user-stories.md).

### Wireframe references

- [wireframes/01-onboarding.html](./product-spec/wireframes/01-onboarding.html) — Confirm-last-30-days screen
- [wireframes/02-home-feed.html](./product-spec/wireframes/02-home-feed.html) — Default home surface; Award badge + Like count distinguished
- [wireframes/03-log-sheet.html](./product-spec/wireframes/03-log-sheet.html) — THE wedge interaction (<8s commit target)
- [wireframes/04-album-detail.html](./product-spec/wireframes/04-album-detail.html) — Social hub with Editions, friends, sortable reviews

---

## 5. Functional Requirements

> Full requirements table with notes: [product-spec/product-spec.md §5](./product-spec/product-spec.md)
> FR-021..FR-025 are reserved-gaps after Lists removal in R3 (preserved for audit, not reassigned).

| ID | Requirement | Priority | Source story |
|---|---|---|---|
| FR-001 | Sign up via email/password or Spotify OAuth shortcut | Must | US-A1 |
| FR-002 | Connect Spotify via OAuth 2.0 PKCE; optional and skippable. Scopes locked: `user-read-recently-played`, `user-read-currently-playing`, `user-library-read` (per Q22) | Must | US-A2 |
| FR-003 | Auto-import last 30 days of recently-played on Spotify connect | Must | US-A3 |
| FR-004 | Log an album with ½-star rating, Award (🏅), and optional review in a single bottom sheet | Must | US-B1, US-B2, US-B3, US-C1 |
| FR-005 | Album catalog search (Atlas Search + Spotify search merge) | Must | US-F2 |
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
| FR-017 | Last.fm history import as Spotify alternative | Should | US-H1 |
| FR-018 | Export diary as JSON or CSV | Should | US-G5 |
| FR-019 | Account deletion with 30-day grace period; cascading hard-delete | Must | US-G5 |
| FR-020 | Client + server-side form validation | Must | (cross-cutting) |
| ~~FR-021..FR-025~~ | *Reserved — were Lists FRs in R1, removed in R3 (Lists deferred to v2). IDs preserved for audit.* | — | — |
| FR-026 | Just-finished auto-prompt (when Spotify connected); in-app default ON, push opt-in; quiet-hours respected; per-album 30d dismissal | Must | US-B6 |
| FR-027 | Settings → Integrations: Spotify status, back-fill diary trigger, immutability on disconnect | Must | US-A2, US-G2 |
| FR-028 | Album detail Edition chip + dropdown for multi-edition release-groups | Must | US-F1 |
| FR-029 | Handle change policy: immutable 30d post-creation, ≤1 change per 30d; ~200–500 squat reservations | Must | US-G1 |
| FR-030 | Review edits: latest public + edited badge; 90d internal audit log; edit history NOT public | Must | US-C3 |
| FR-031 | Like (👍) another user's review; idempotent toggle; counter on Review | Must | US-C4 |
| FR-032 | Review sort by Newest (default) / Most Liked / Highest-Rated; persists per-device | Must | US-C2 |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | p95 home feed load <500ms (SSR); p95 album detail <400ms; p99 Spotify 30-day import <8s end-to-end |
| Availability | 99.5% monthly uptime at MVP; degrade gracefully when Spotify API unavailable (show cached data, queue writes) |
| Scalability | Sized for 10,000 concurrent users at peak (3× M6 WAL target) without architectural changes |
| Accessibility | WCAG 2.1 AA — keyboard nav; screen-reader labels on rating widget + Award + Like; contrast ≥4.5:1 on album-art-heavy surfaces; reduced-motion respect; touch targets ≥44pt on mobile |
| Privacy | Public-by-default with per-entry opt-out; private-profile toggle; no third-party tracking beyond PostHog (self-hosted) + Sentry (errors); no ad SDKs |
| Security | OAuth tokens encrypted at rest; no refresh tokens client-side; rate limiting on log/follow/review/like endpoints; CSRF; bcrypt cost ≥12 |
| Compliance | GDPR (export + erasure); Spotify ToS ("Powered by Spotify" attribution + branding compliance) |
| Spotify rate limits | All Spotify calls server-side via async httpx; per-user circuit breaker; cache album metadata 7d; cache user listening 1h |
| i18n / l10n | English-only at MVP; copy strings extracted to keys |
| Mobile responsiveness | Mobile-first; PWA installable; breakpoint 768px |
| SEO | Album detail + profile pages SSR with Open Graph meta; everything else CSR acceptable |
| Observability | Every external API call logged with provider/latency/status; Sentry for errors; PostHog for product analytics; daily metrics ETL |

## 6.1 NFR Measurement Contract

> Every NFR has a measurable signal. Without this, the NFR cannot be verified.

| NFR | How to Measure | Signal / Query | Threshold |
|---|---|---|---|
| p95 home feed load | PostHog `pageview.duration_ms` on `/` | p95 over trailing 7d windows, per-device-class | <500ms |
| p95 album detail load | PostHog `pageview.duration_ms` on `/album/*` | p95 over trailing 7d | <400ms |
| Spotify import p99 | Backend trace `spotify.import.completed_at - started_at` | p99 over trailing 7d | <8s |
| Uptime | Synthetic check + Sentry availability monitor | Monthly uptime % | ≥99.5% |
| Spotify API error rate | Backend trace counter `spotify.api.4xx + 5xx / total` | per-5-min window | <2% |
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

**Greenfield project** — no existing application code; the project root is Spec Kit scaffolding only. All integration points are NEW modules. Spotify Web API is the primary external integration. MusicBrainz + Discogs are secondary metadata sources (lazy-fetched, cached).

### Reusable components

None — greenfield. Phase 5 plan must establish a project structure from scratch.

### New modules required (sketch — Phase 5 finalizes)

| Layer | Module | Responsibility |
|---|---|---|
| Backend | `auth` | OAuth flows (Spotify + email/password), session management, handle policy enforcement |
| Backend | `providers/spotify` | All Spotify API calls behind a `MusicProvider` interface; recently-played polling; just-finished detection; album catalog fetch |
| Backend | `providers/musicbrainz` | MBID lookup + release-group reconciliation |
| Backend | `albums` | Canonical Album records; identity normalization (MBID canonical / Spotify fallback); cache TTL; Edition aggregation |
| Backend | `diary` | DiaryEntry CRUD; visibility evaluation; soft-delete + 30d grace; relisten support |
| Backend | `reviews` | Review CRUD; markdown-safe rendering; edit history (90d internal); like-toggle + likes_count denormalization |
| Backend | `backlog` | Per-user Backlog + BacklogItem; auto-remove-on-log behavior |
| Backend | `social` | Follow / unfollow; block; suggested follows job; mutual-taste scoring |
| Backend | `feed` | Home feed read (fan-out-on-read at MVP); weighted ordering; "Latest" toggle |
| Backend | `notifications` | Dispatcher; per-channel adapters (in-app, email, push); coalescer + rate-limit; weekly digest job |
| Backend | `prompts` | JustFinishedPrompt lifecycle; Spotify polling; quiet hours; per-album dismissal |
| Backend | `seeding` | CriticSeed roster; pre-checked card ordering; analytics on opt-out rate |
| Backend | `moderation` | Report queue; daily-log-scan for ≥3-report threshold |
| Backend | `search` | Atlas Search index; Spotify search fallback |
| Backend | `data-export` | GDPR JSON/CSV export job; deletion grace + cascade |
| Frontend | `app/(auth)` | Sign-up, login, OAuth redirect |
| Frontend | `app/(onboarding)` | 5-step flow with Spotify Skip |
| Frontend | `app/(feed)` | Home feed; "Latest" toggle; entry cards |
| Frontend | `app/album/[id]` | Album detail; Edition chip; sortable reviews; friends section |
| Frontend | `app/@[handle]` | Profile; diary; filters (Awards, public-only) |
| Frontend | `app/up-next` | Backlog UI |
| Frontend | `app/settings/*` | Profile, privacy, notifications, integrations, data |
| Frontend | `components/log-sheet` | THE wedge interaction; bottom-sheet; ½-star widget; Award + review |
| Frontend | `components/just-finished-prompt` | In-app prompt surface; opt-out menu |
| Shared | `lib/visibility-check` | Single source of truth for visibility evaluation across all surfaces |

### Data model impact

15 entities (see [product-spec/data-model.md](./product-spec/data-model.md) for field-level sketch). Final indexes + collection layout in Phase 5.

| Entity | Notes |
|---|---|
| User, MusicProvider | Embedded music_providers; encrypted tokens; auto_prompt_enabled flag |
| Album | MBID canonical + Spotify ID fallback; 7d cache; tracklist denormalized at MVP |
| DiaryEntry | The central activity record; `awarded` boolean (renamed from `hearted` in R1); soft-delete 30d |
| Review | 1:1 optional with DiaryEntry; `reactions.likes_count` (R3 rename); 90d edit-history retained internally |
| ReviewLike *(new in R3)* | Per-user-per-review like records for idempotent toggle and Most Liked sort |
| Backlog, BacklogItem | Singleton per User; private by default |
| Follow, Block | Asymmetric follows; cascading dissolve on block |
| Report | Open / reviewing / actioned / dismissed; 90d resolution audit |
| Notification, NotificationPreferences | 18 active types; per-channel + quiet-hours |
| JustFinishedPrompt *(new in R1)* | Pending / dismissed / logged / expired lifecycle |
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
| Cover-art | Proxy Spotify CDN (DM-2 decision); no S3 cache | Locked |
| Recommendation engine | Heuristic social-graph at MVP; no ML/ALS | Locked (ALS deferred to v2) |

### Codebase constraints

| Constraint | Source | Impact on design |
|---|---|---|
| Constitution gap | `.specify/memory/constitution.md` is template-only | **Phase 5 MUST** ratify principles as Task 0 before any feature work |
| Provider-interface abstraction | Decision-log structural decisions | Every external music API call goes through `MusicProvider` interface; future-proofs against Spotify deprecations |
| Album-identity normalization | Decision Q15 | All album references resolve through MBID-canonical / Spotify-fallback; cascades through search, dedup, recs, analytics |
| External-call resilience | Recommended principle from research | Retry + timeout + circuit breaker on every Spotify call |
| Schema versioning | Recommended principle | Every Mongo document carries `_schema_version` int |
| Test-first for catalog + auth edges | Recommended principle | Contract tests for Spotify integration + auth flow before implementation |
| Observability mandatory | Recommended principle | Every external call logged with provider/latency/status |
| Spotify Extended Quota Mode | External dependency | 2–6 week review on critical path; **submit Day 1 of plan**; design closed-beta wave inside Development Mode quotas as fallback |

---

## 8. Acceptance Criteria (global)

The feature is complete when:

1. All 30 Must-Have user stories pass their G/W/T acceptance criteria.
2. Wireframes match implementation within acceptable visual deviation (designed on PWA-default styles).
3. Performance NFRs are met as measured by the NFR Measurement Contract (§6.1).
4. WCAG 2.1 AA passes automated (axe-core) + manual keyboard-nav audit on every screen.
5. Spotify Extended Quota Mode is approved and the production app is operating outside Development Mode quotas.
6. Constitution is ratified at `.specify/memory/constitution.md` (per Phase 5 Task 0).
7. Critic-seed roster: ≥25 active seed accounts onboarded pre-public-launch (per [seeding-strategy.md](./product-spec/seeding-strategy.md) playbook).
8. Notification rate-limits and quiet hours are verified end-to-end (no Goodreads-firehose regressions).
9. Spotify OAuth + auto-import + just-finished prompt flows are verified with at least 5 real user-side tests.
10. Disconnect → diary immutability is verified (data persists; reconnect resumes cleanly without back-fill).
11. Award (🏅) vs Like (👍) semantics are consistent: never confused in UI, copy, notifications, or API.

---

## 9. Success Metrics

> Full metrics + benchmarks: [product-spec/success-metrics.md](./product-spec/success-metrics.md), [research/metrics-roi.md](./research/metrics-roi.md)

**Primary KPI (North Star):** Weekly Active Loggers (WAL) — unique users who logged ≥1 album AND opened the app in trailing 7 days.

| Metric | M3 target | M6 target |
|---|---|---|
| WAL (North Star) | 500 | 2,500 |
| W1 activation rate (new signups logging ≥3 albums in first week) | 30% | 35% |
| D30 retention | 8% | 12% |
| Social-originated play rate (`Listen on Spotify` from feed or friend surface vs profile/search) | 25% | 40% |
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
| `providers/spotify` | ≥85% | unit + integration (contract tests against Spotify sandbox) |
| `albums` (identity normalization) | ≥85% | unit (MBID + Spotify fallback paths; Edition aggregation) |
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
| TC-001 | Log + ½-star + Award an album in <8 seconds (server-measured) | DiaryEntry created with all three; commit time recorded | integration |
| TC-002 | Log without rating (just confirm album) | Entry saves with null rating, null Award; no errors | unit |
| TC-003 | Re-log same album | Two DiaryEntry records with different `logged_at`; both visible in user's diary | integration |
| TC-004 | Spotify OAuth with all three scopes | Tokens stored encrypted; refresh works; revoke handled | integration |
| TC-005 | Spotify OAuth with permission denied for one scope | Friendly error; user can retry or skip | integration |
| TC-006 | 30-day Spotify import with 50+ albums | Dedupes to album-grain; preserves timestamps; <8s p99 | integration |
| TC-007 | Spotify API 429 (rate limit) | Circuit-breaker engages; client sees friendly degradation | unit + integration |
| TC-008 | Album with MBID and Spotify ID | Canonical Album record has both; subsequent lookups reuse | unit |
| TC-009 | Album with no MBID (fresh release) | Candidate record created; reconciles when MusicBrainz updates | unit + integration |
| TC-010 | Multi-edition album (Standard + Deluxe + Bonus) | Single canonical record; Edition selector aggregates ratings/reviews/likes across editions | unit |
| TC-011 | Public diary entry, viewer follows owner | Entry visible | unit (visibility matrix) |
| TC-012 | Followers-only entry, viewer NOT following | Entry hidden | unit |
| TC-013 | Private entry, viewer != owner | Entry hidden | unit |
| TC-014 | Entry on blocked-by owner, viewer is the blocker | Entry hidden | unit |
| TC-015 | Like a review (idempotent toggle) | First tap creates ReviewLike + increments counter + N-004; second tap removes both, no N-004 | unit + integration |
| TC-016 | Like own review | UI disabled with tooltip; API rejects | unit |
| TC-017 | Sort reviews by Most Liked | Result order matches `reactions.likes_count` desc within tier | unit |
| TC-018 | Just-finished detection (Spotify recently-played shows completed album) | JustFinishedPrompt created; surfaces in-app within 5–15 min | integration |
| TC-019 | Just-finished during quiet hours | No push; in-app prompt deferred to next non-quiet open | integration |
| TC-020 | Per-album auto-prompt dismissal | Same album does not re-prompt for 30 days | unit |
| TC-021 | User disables auto-prompts | No prompts surface even if detection fires | unit |
| TC-022 | Spotify disconnect | All existing entries persist; auto-import + auto-prompt + prefill stop; reconnect resumes without gap back-fill | integration |
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
| TC-E2E-001 | Full onboarding (Spotify connected) | Landing page invite link | Home feed with ≥5 entries |
| TC-E2E-002 | Full onboarding (Spotify skipped) | Landing page direct | Home feed with critic-seed entries only |
| TC-E2E-003 | Log + rate + Award + review an album in <25s | Home feed | Entry visible in diary |
| TC-E2E-004 | Discover album via social feed → Listen on Spotify | Home feed | Spotify deep-link fired (mocked) |
| TC-E2E-005 | Like a review → reviewer sees N-004 notification | Album detail page | Notification visible in reviewer's session |
| TC-E2E-006 | Sort reviews by Most Liked | Album detail | Result order changes; persistence across reload |
| TC-E2E-007 | Add album to Up Next, later log it, verify auto-remove | Album detail | Backlog reflects removal; toast confirms |
| TC-E2E-008 | Just-finished prompt: appears, log from prompt | Home feed (with mocked Spotify event) | Diary entry created with `source: spotify_just_finished_prompt` |
| TC-E2E-009 | Settings → disable auto-prompts → verify no prompts | Settings | Subsequent detection produces no UI |
| TC-E2E-010 | Edit profile + change handle (after 30d lock) | Settings → Profile | Handle changes; old URL redirects |
| TC-E2E-011 | Block a user → verify content hiding both ways | Other user's profile | Profile shows "Blocked"; content hidden |
| TC-E2E-012 | Export data → receive email with JSON+CSV | Settings → Data | Email received (mocked); contains diary + reviews |
| TC-E2E-013 | Delete account → 30d cancel flow | Settings → Data | Banner; cancellation restores account |

---

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| H1 (user-research validation) never confirms | High | Run the [interview script](./problem-discovery/interview-script.md) during early-access wave; treat first 8 weeks of live metrics as the real validation gate; M3 pivot/shutdown decision point if WAL <50% of target |
| Spotify changes API terms / further endpoint deprecation | High | Provider-interface abstraction; degrade gracefully; Apple Music ready as v2 fallback |
| Extended Quota Mode application denied or stuck | Medium | Apply Day 1 of plan; design closed-beta wave entirely inside Development Mode quotas |
| Cold-start ghost-town — seed graph doesn't compound | High | Seeding strategy launched as a project alongside the product, not a marketing afterthought; founder-curated critic seed must be live before public access |
| Notification firehose drives churn (Goodreads pattern) | High | Conservative defaults; granular per-type per-channel toggles; weekly digest primary mode |
| Music metadata quality | Medium | MBID canonical + Spotify fallback; Edition selector merges deluxe/remasters; user "report wrong album" surface |
| Privacy / safety incident | High | Block + report from MVP; private-profile toggle; rate-limit follows; explicit ToS |
| Search returns irrelevant results | Medium | Start with Spotify search as primary, Atlas as fallback; iterate index after launch |
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
2. [product-spec/data-model.md](./product-spec/data-model.md) — 15 entities + relationships + preliminary indexes
3. [product-spec/notification-taxonomy.md](./product-spec/notification-taxonomy.md) — 18 active notification types with defaults (load-bearing — wrong notification design = Goodreads-style churn)
4. [product-spec/seeding-strategy.md](./product-spec/seeding-strategy.md) — 4-pronged cold-start playbook (launch infrastructure, not marketing)
5. [research/tech-stack.md](./research/tech-stack.md) — Spotify API audit (H4 critical findings, Extended Quota Mode dependency)
6. [research/codebase-analysis.md](./research/codebase-analysis.md) — greenfield analysis + recommended constitution principles

Phase 5's Task 0 should be: **Ratify the project constitution** (currently template-only) with the 5 recommended principles from research/codebase-analysis.md or a founder-defined alternative.

---

## 14. Document History

This spec.md is generated from a product-spec that went through 3 revisions in Phase 3:

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2026-05-21 | Initial product-spec from Phase 2 |
| v1.1 | 2026-05-21 | R1: Lists + Auto-prompt elevated to MVP; Spotify skippable; Heart → Award rename |
| v1.2 | 2026-05-21 | R2: All 30 open questions resolved with locked decisions; FRs 028–030 added |
| v1.3 | 2026-05-21 | R3: Removed "say more" prompt; split Award (🏅 self) / Like (👍 social); added Likes + sort; reverted Lists to v2; FRs 031–032 added; ReviewLike entity added |
| **spec.md** | **2026-05-21** | **Generated by Phase 4 Bridge from product-spec v1.3** |
