# Decision Log: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 (Product Spec) | Date: 2026-05-21
> Status: DRAFT — open for revision in Phase 3 (Revalidation)
>
> Every decision below is the **default position** entering Phase 3. Where research-recommended, it's labeled. Reasoning is captured so revisions can be intentional. All decisions can be overridden in Phase 3 with a written rationale appended below the affected row.

---

## Product Wedge (locked from research)

| Decision | Choice | Rationale | Source |
|---|---|---|---|
| Wedge thesis | Auto-import + social-graph-primary + album-as-unit + casual-first — all four simultaneously | None of 13 competitors does all four; combinatorial gap | research/competitors.md (H3) |
| Target user | Casual Spotify listeners 18–35 | Not RYM power users; not generic music fans | problem-discovery/problem-statement.md |
| Differentiator | Social-graph recs (not algorithmic) | Spotify deprecated algo-rec endpoints 2024-11-27 anyway | research/tech-stack.md |

---

## Open Questions — Resolutions

| # | Question | Decision | Rationale | Status |
|---|---|---|---|---|
| 1 | Spotify-only vs multi-provider at launch | **Spotify-only at MVP**. Apple Music = v2. | Largest streaming share in target demo; Apple Music adds 2–3 weeks for marginal addressable-market gain | LOCKED |
| 2 | Rating scale | **½-star, 0–5 in halves** (Letterboxd model) | UX research's top recommendation; granular enough for taste, simple to consume | LOCKED |
| 3 | Feed composition algorithm | **Reverse-chronological** from followed users, **weighted** toward (a) entries with a written review attached, (b) ★★★★★ and ★ extreme ratings, (c) entries by users the viewer interacts with most | Avoids "algorithm distrust" problem; transparent ordering; surfaces signal | LOCKED |
| 4 | Backlog vs Spotify "Liked Songs" semantics | **Backlog = albums only**, distinct from Spotify Liked (which is tracks). Backlog is aspirational ("want to listen") not historical | Keeps album-as-unit wedge intact; doesn't compete with Spotify primitive | LOCKED |
| 5 | Review minimum length / required vs optional | **Optional after rating. No minimum length. No soft prompt** (revised in Revision #3, 2026-05-21). Reviews can be ≥1 character without any "say more?" nudge. | Letterboxd model; matches sub-8-sec log target. Soft prompts add nag-feel for users who legitimately want one-line reactions. | LOCKED (v1.3) |
| 6 | Public-by-default vs follower-only ratings/reviews | **Public by default**. Per-entry override to "followers only" or "private (diary only)". Profile-level "private profile" toggle in settings (default off). | Public is the Letterboxd default; required for the social-graph thesis to compound; private escape hatch for safety | LOCKED |
| 7 | Curated user-created lists | **Deferred to v2** (revised in Revision #3, 2026-05-21 — reverses Revision #1's MVP elevation). Founder reconsidered after seeing the scope cost. The MVP refocuses on the core wedge (log + rate + Aux + review + backlog + social-feed); Lists return as a post-launch capability once retention is validated. Re-eval trigger: WAL > 1k AND ≥10% of users ask for lists in feedback. | Significant UI/data complexity (drag-order, collab, cover-pickers, list-of-the-week surfacing). Build estimate dropped ~5–8 weeks. Lists were elevated in R1 then de-elevated in R3 after weighing scope vs. wedge focus — the wedge holds without Lists at MVP. | LOCKED (v1.3) |
| 8 | Notification taxonomy + defaults | **First-class spec document** ([notification-taxonomy.md](./notification-taxonomy.md)); conservative defaults — only "someone followed you" and weekly digest on by default | Top documented churn driver in niche (Goodreads firehose pattern); requires careful design | LOCKED |
| 9 | Cold-start / seeding strategy | **First-class spec document** ([seeding-strategy.md](./seeding-strategy.md)); 4-pronged: founder-curated critic seed roster + Last.fm history import + invite mechanics + mutual-follow nudge | Social product without seed graph = ghost town | LOCKED |
| 10 | "Just-finished" auto-detection vs manual log only | **Auto-prompt at MVP — opt-out, default ON** (revised in Revision #1, 2026-05-21). Poll Spotify recently-played; on detecting a finished album, show an in-app prompt (and optional push) "Just listened to {album} — log it?". User can opt out per-prompt, per-album, or globally. Manual log continues to work in parallel. Quiet hours respected. | Founder accepted the privacy tradeoff. Moments captured by auto-prompt are likely the highest-value moments (immediate post-listen reactions) — losing them silently was deemed worse than the "surveillance-y" risk. Conservative implementation: in-app default ON; push default OFF; opt-out is one-tap. | LOCKED (v1.1) |
| 11 | Wrapped-style year-end retrospective | **Deferred to v2.** Will revisit Q4 2027 for first-year cohort. | High polish, seasonal; not blocking for launch; powerful virality lever once user base exists | LOCKED |
| 12 | Onboarding flow | **Spotify auth + auto-import last 30 days — but explicitly SKIPPABLE** (revised in Revision #1, 2026-05-21). Flow: signup → Spotify auth screen with prominent Skip button → (if accepted) import + confirm/½-star top 5 → "Follow 3 to fill your feed" → land on feed. (If skipped) Skip directly to "Follow 3" with critic-seed-only suggestions → land on feed; can connect Spotify any time later from Settings → Integrations to back-fill the diary. The skip path is NOT "degraded mode" — manual log + critic-seed feed + reviews + backlog all work fully. Spotify just enables auto-import and Log-sheet prefill. | Casey may not want OAuth on first visit; forcing it tanks signups. Better: a complete product without Spotify, with Spotify as a value-add. | LOCKED (v1.1) |
| 13 | Critic seeds: followed-by-default at signup, or shown as suggested-only? | **Pre-checked checkbox cards on the "Follow 3" onboarding screen.** Critic-seed accounts appear in step 4 as cards with the follow-checkbox ALREADY TICKED; user can untick before tapping "Continue". Technically opt-in (explicit user assent), practically gets the "instant feed" outcome. No auto-follow without consent. | Default-follow without consent is brand-eroding (Twitter "topics you may like" pattern). Pure opt-in loses too much activation. Pre-checked cards is the proven middle. | LOCKED (v1.2) |
| 14 | Auto-import window: 30 days, 6 months, or all-available at signup? | **30 days at signup.** Future "Pull more history" button in Settings → Integrations (v1.x progressive enhancement) can use Last.fm scrobbles if connected, or page deeper into Spotify if integration depth permits. | Spotify `/me/player/recently-played` is capped at 50 items (~30 days for casual listeners). First-session wait must stay short. Power-user deep-history is post-launch optimization. | LOCKED (v1.2) |
| 15 | Deluxe / remastered editions: separate album entries or merged under release-group? | **Merge under MusicBrainz release-group MBID; surface an "Edition" selector on the album detail page.** One canonical album entry per release group; Edition chip near the cover shows "All editions" with a dropdown for Standard / Deluxe / Bonus / etc. Ratings, reviews, and Aux'd aggregate across all editions. | Letterboxd-style merge for casual users; the Edition selector preserves power-user granularity without splitting the catalog. Cascade implications: search, dedup, recs, analytics all key off the release-group MBID. | LOCKED (v1.2) |
| 16 | Profile handle (`@`) reservation, mutability, squatting prevention | **Handles are unique, immutable for first 30 days after creation, then changeable once per 30 days.** 200–500 obvious-squat candidates (taylorswift, kendrick, drake, etc.) reserved at launch; claim-via-verification only after launch. Old handles become available 90 days after account deletion / abandonment, with a redirect period to prevent link-rot. No paid "claim your name" service at MVP. | Prevents impersonation chaos at launch; gives users flexibility without enabling churn-style handle hopping; respects the trust thesis. | LOCKED (v1.2) |
| 17 | Reviews: edits-after-publish or append-only? | **Edits allowed; edit history hidden from public; preserved internally for 90 days for moderation/audit.** Public surfaces (album detail, profile feed) show only latest version + small "edited" badge with timestamp on hover. Internal revision log enables admin to inspect bad-actor edits (e.g., review that went viral, then was changed). | Append-only with public history adds UI complexity and discourages typo edits. Hidden audit log balances trust + ergonomics. | LOCKED (v1.2) |
| 18 | Notification real-time vs digest taxonomy refinement | **Concrete defaults:** Real-time push (when push enabled): N-001 follow + N-002 follow-request + N-011 spotify-reconnect-required only. Real-time in-app: N-001–N-006, N-018 just-finished, N-009–N-012 transactional, N-016/17 security. Daily/weekly digest: only N-008 (weekly digest); no other batched channels at MVP. *(N-019 list-auxed removed in R3 — Lists deferred to v2.)* Coalescing per existing notification-taxonomy.md guardrails. | Aggregating individual notifications into intermediate daily roll-ups adds complexity for marginal gain. Weekly digest is the only batched channel; everything else is event-driven or off. | LOCKED (v1.2) |
| 19 | Disconnect Spotify mid-product-life — does the diary stay? | **Yes — immutable.** Disconnect removes auto-import, auto-prompt, Log-sheet prefill. All existing DiaryEntry / Rating / Review / Aux / Like / Follow remains untouched. Reconnect re-enables features; auto-import resumes from next polling cycle (no back-fill of the disconnected gap). Show small "disconnected from Spotify on YYYY-MM-DD" note in Settings → Integrations with Reconnect CTA. Do NOT surface this on the diary itself — entries belong to the user. | Trust thesis hinges on user data being durable independent of OAuth state. Spotify is the integration, not the storage. | LOCKED (v1.2) |
| 20 | Seed graph includes artists themselves, or only critics/curators? | **Critics + curators only at MVP.** Artists may join as regular users but are not surfaced via the CriticSeed roster. Artist-as-seed is a separate v1.x cohort with distinct badge ("Artist" vs "Critic"), distinct ranking rules, and possibly rate-limited self-promotion guidelines. | A critic's review of GNX has different epistemic weight than Kendrick's tweet about his own album. Mixing them in the same seed surface blurs the trusted-taste-graph thesis. | LOCKED (v1.2) |
| 21 | Albums released *during* user's reach-back window — included? | **Yes — included naturally.** Spotify recently-played returns whatever the user listened to in the window, regardless of release date. Edge case: very-new releases may not be in MusicBrainz yet; system lazy-fetches from Spotify catalog and creates a `candidate` Album record flagged for MBID reconciliation when MusicBrainz catches up. | Saves special-case logic; matches user intuition ("I listened to it, so it should be in my diary"). | LOCKED (v1.2) |
| 22 | Spotify OAuth scopes — which are essential vs nice-to-have at MVP? | **Essential at MVP (sync-fix Run #2 widening to 5 scopes):** `user-read-email` (populate `User.email` from OAuth — required by S-A1 OAuth-shortcut signup), `user-read-private` (populate `display_name` from OAuth — required by S-A1), `user-read-recently-played` (auto-import + just-finished detection), `user-read-currently-playing` (just-finished — confirms album completion), `user-library-read` (saved albums for backlog hints). **Deferred, request lazily on first feature need:** `playlist-read-private`, `user-top-read`, `user-follow-read`. Request all 5 essentials in one round at signup; widen later if features demand it. | Reduces consent-screen friction while still supporting S-A1 OAuth-shortcut account creation; without `user-read-email` + `user-read-private`, the OAuth flow can't return email/display name, forcing a UX-regressing extra step. Original v1.2 lock was too narrow; corrected in sync-verify Run #2. | LOCKED (v1.3 — sync-fix Run #2) |

---

## Structural decisions (carried from research)

| Decision | Choice | Rationale |
|---|---|---|
| Album-identity key | **MusicBrainz release-group MBID** canonical; **Spotify album ID** as fallback identifier when MBID unavailable | Cascades through search, dedup, recs, analytics; MBID is the only stable cross-provider key |
| Provider abstraction | Every Spotify call behind a `MusicProvider` interface | Future-proofs against another 2024-11-27-style deprecation; enables Apple Music in v2 with bounded scope |
| Pricing tier | **No paid tier at launch**. Future auxd Pro ($19/yr) + Patron ($39/yr) documented in spec as future-state. | Per metrics-roi.md: defer until WAL ≥ 1,000 and D30 ≥ 10% |
| Native vs PWA | **Responsive web + PWA at MVP**. Native iOS/Android deferred. | Faster iteration; one codebase; lower platform-policy risk |
| Recommendation engine | **Heuristic social-graph recs only at MVP** (no ML); `implicit`/ALS deferred to v2 | Needs scale + data first; heuristic walking the follow-graph is sufficient for early days |
| Search | **MongoDB Atlas Search**; Spotify search as fallback | Native to chosen DB; less moving parts than Elasticsearch/Meilisearch at MVP scale |
| Privacy default | Public profile + public ratings/reviews; per-entry override to followers-only or private | Letterboxd default; needed for social-graph compounding |
| **Terminology — "Aux" vs "Like" semantic split** (refined in Revision #3, 2026-05-21; supersedes the unified Aux terminology from Revision #1) | Two distinct concepts, two distinct names: <br> • **Aux (🏅)** = a deliberate personal-curation signal on your OWN content. Boolean on DiaryEntry: "this album is one of my standouts in MY diary." Rare and intentional. <br> • **Like (👍)** = a lightweight social engagement signal on OTHER users' content. Counter on Review: number of people who appreciated this user's review. Common and fast. <br> Lists are deferred to v2 (per decision #7), so no Aux-or-Like split applies there at MVP. | Letterboxd model: "Like" (heart) on your own log is personal-favorite; "Like" on a review is social. We had unified both under "Aux" in R1; founder split them in R3 to be precise about self-directed-curation vs other-directed-engagement. Two icons (🏅 for Aux, 👍 for Like) reinforce the distinction in UI. |
| **Onboarding edge case — email collision with deleted-status account** *(added in Phase 5C, 2026-05-22 — D-001 from pre-impl-review)* | If a user attempts signup (email/password OR Spotify OAuth) with an email tied to an account in `status: deleted` (i.e., scheduled-for-deletion grace period), REFUSE the signup. The signup screen shows a "Restore your account?" CTA. Tapping it requires the user to authenticate as the original account (email/password OR re-authorize Spotify), then cancels the deletion via the same endpoint as US-G5 "cancel deletion". No new account is ever created over a deleted-status account. | Prevents impersonation, accidental data loss, and confusing dual-account state. The grace-period account is the canonical source of truth until hard-delete completes. |
| **Onboarding edge case — Spotify OAuth email matches existing email/password account** *(added in Phase 5C, 2026-05-22 — D-002 from pre-impl-review)* | When Spotify OAuth returns an email matching an existing ACTIVE auxd account, do NOT silently auto-link. Show a "Connect Spotify to your existing account?" page that requires the user to authenticate via their existing auxd password first. On password-success, attach the `MusicProvider` Spotify sub-document to the existing User. If the email matches a deleted-status account, fall through to the rule above. | Silent auto-linking creates security risks (someone with access to a Spotify account auto-merging into a auxd account they don't own). Requiring password re-auth confirms identity. |
| Monetization timing | **No payments code at MVP.** Stub the future flag in the spec, no code path. | Avoid Stripe/billing surface area; revisit once retention validated |

---

## Document plan (Phase 2 outputs)

| Decision | Choice | Rationale |
|---|---|---|
| Spec detail level | **Standard** | Matches feature size (large); 5–8 pages of PRD reasonable for an MVP scope |
| Feature size | **Large** | 5 user-facing capabilities + onboarding + social + feeds + recs |
| User journey format | **Single file with multiple flows** (`user-journeys.md`) | Simpler than multi-file; flows are short enough to coexist |
| Wireframe fidelity | **Basic HTML, screen-decomposed** | Matches `default_wireframe_detail: basic-html`; 4 critical screens (log sheet, home feed, album detail, onboarding) |
| Mockups | **Skipped at this phase** | Greenfield: no project CSS/design tokens to scan; mockups would be generic Bootstrap-ish noise. Defer high-fidelity design to implementation phase. |
| Metrics document | **Yes, light file referencing research/metrics-roi.md** | Avoid duplicating the benchmark deep-dive |

---

## Supporting-doc decisions locked in Revision #2 (2026-05-21)

### Notification taxonomy (notification-taxonomy.md questions)

| # | Question | Decision |
|---|---|---|
| NT-1 | Suppress critic-seed N-001 follow-notifications during onboarding wave? | **Yes — suppress.** Otherwise every critic-seed gets a notification storm from new-user onboarding. |
| NT-2 | Weekly digest includes "most-rated album in follow graph this week" hero entry? | **Yes — single hero entry.** Adds editorial feel; cheap query; high signal. |
| NT-3 | Behavior when weekly digest fires during user's quiet hours? | **Send anyway.** Quiet hours only suppress push and in-app prompts; emails (including digest) fire on their own schedule. |
| NT-4 | N-004 (review.auxed) — in-app or aggregated into digest only? | **Both.** In-app for immediate feedback (low volume per user); digest aggregates ("your reviews got 12 auxes this week") for absent users. |
| NT-5 | "Import succeeded" notification — every time, or first time only? | **Every time.** Users re-trigger imports; want explicit confirmation. |

### Seeding strategy (seeding-strategy.md questions)

| # | Question | Decision |
|---|---|---|
| SS-1 | Critic seeds followed by default at signup, or suggested-only? | See Q13 above — **Pre-checked checkbox cards on Follow 3.** |
| SS-2 | "Featured Critic" badge surface — everywhere or only on seed profiles? | **Inline subtle "· Critic" suffix next to display name everywhere.** Subtle text, no icon, no checkmark. Provides social proof; avoids class-hierarchy feel. |
| SS-3 | Invite link includes "X just joined" social-proof line? | **No at MVP.** Adds a privacy surface; founder wants control over who is surfaced as a "joiner" during launch wave. |
| SS-4 | Critic stipend ($100/mo per seed) vs free Pro only? | **Free Pro only at MVP.** Stipend in v1.x for top-engagement seeds. A flat stipend creates a quasi-employment relationship that's complicated to unwind. Pay for retention only after we know it's working. |
| SS-5 | Off-ramp for a seed who wants to leave the program? | **Standard account, badge removed silently.** No public "Critic X has left auxd" announcement. |

### Data model (data-model.md questions — spec-level intent; final implementation in Phase 5)

| # | Question | Decision |
|---|---|---|
| DM-1 | Feed fan-out strategy: write vs read? | **Fan-out-on-read at MVP.** Writes are infrequent; follow-graph is sparse. Switch to fan-out-on-write only if feed query p95 exceeds 200ms at the DB layer (re-evaluate in Phase 5 from load model). |
| DM-2 | Cover-art storage: proxy Spotify CDN vs cache to S3? | **Proxy Spotify CDN.** No legal surface for storing cover art; saves S3 cost. Small blurhash placeholders cached client-side. |
| DM-3 | Reactions on Reviews (auxes count) — feature-flag the UI? | **Ship visible.** Already in the data model; gating for vanity is over-engineering. Volume will be low at MVP; that's fine. |
| DM-4 | Tracklist storage: denormalize into Album or fetch on demand? | **Denormalize at MVP.** Tracklists are small; saves Spotify roundtrips on album detail page. Revisit if Album docs balloon. |
| DM-5 | Soft-deleted DiaryEntry: should reactions cascade? | **Yes — cascade.** Don't leave orphan `likes_count` aggregates or ReviewLike rows pointing at deleted entries. |

### User journeys (user-journeys.md questions)

| # | Question | Decision |
|---|---|---|
| UJ-1 | Log sheet prefilled album = most-recently-played track or most-recently-finished album? | **Most-recently-finished album.** Track-level prefill triggers on background music or skips; album-level is the actual log moment. |
| UJ-2 | Onboarding "Follow 3" card order — critics-first or mixed? | **Mixed, but always ≥3 critics in the top 6 visible cards.** Critic-first reads too editorial; pure-mixed dilutes the seeding value. |
| UJ-3 | Review expanded inline (current) vs dedicated reading view? | **Inline expand at MVP.** Dedicated reading view is post-launch optimization. Most reviews are short and inline keeps the feed in-flow. |
| UJ-4 | Share reviews via API cross-post (Twitter/X) or share-card only? | **Share-card only at MVP.** Cross-post APIs are deprecating across platforms; share-card with OG preview is portable and platform-risk-free. |
| UJ-5 | "Reading list" parallel to Up Next for articles/reviews? | **Defer (out of scope).** Up Next is for albums only; reading-list-for-articles is a different surface that doesn't earn its keep at MVP. |

---

## Decisions deferred to Phase 5 (Plan)

These are technical/architectural decisions intentionally left to Phase 5 once the spec is locked:

| Decision | Why deferred |
|---|---|
| Authentication library (Authlib vs fastapi-users) | Tech-stack research recommended Authlib; final pick at plan time |
| Background job runner (arq vs Celery) | Research recommended arq; depends on deployment target |
| Hosting / deployment target (Vercel + Fly.io vs Railway vs self-host) | Outside spec scope |
| Cover-art storage strategy (proxy Spotify CDN vs cache to S3) | Plan-time call; affects rate-limit math |
| Feed read strategy (fan-out-on-write vs fan-out-on-read) | Sketched in data-model.md, locked in plan |
| Atlas Search index schemas | Plan time |
| Observability stack (Sentry / PostHog / OpenTelemetry combo) | Plan time |

---

## Decisions deferred to Phase 0 of Phase 5 (Constitution)

The constitution at `.specify/memory/constitution.md` is the unfilled template. Phase 5 must ratify principles before any feature work. Recommended principles (from research/codebase-analysis.md):

1. **External-call resilience** — every provider API call wrapped (retry + timeout + circuit breaker).
2. **Schema-versioned documents** — MongoDB documents carry `_schema_version` field; never assume shape.
3. **Library-first modules** — backend organized as composable libraries, not god-objects.
4. **Test-first for catalog/auth edges** — Spotify integration + auth flow have contract tests before implementation.
5. **Observability mandatory** — every external call logged with provider, latency, status.

---

## Revisions

> Each revision in Phase 3 appends a row here noting what changed and why.

| Date | Revision | Reason | Author |
|---|---|---|---|
| 2026-05-21 | v1.0: Initial decisions (this document) | Phase 2 draft, defaults from research | Product Forge Phase 2 |
| 2026-05-21 | v1.1: Revision #1 in Phase 3 | Founder elevated Lists into MVP scope; enabled auto-prompt for just-finished; made Spotify connect explicitly skippable; renamed Liked/Heart → Aux'd/Aux across all docs | Product Forge Phase 3 |
| 2026-05-21 | v1.2: Revision #2 in Phase 3 | All 10 product-spec.md §10 open questions resolved (Q13–Q22); all 20 supporting-doc open questions resolved (NT-1..5, SS-1..5, DM-1..5, UJ-1..5); zero open questions remain at spec level | Product Forge Phase 3 |
| 2026-05-21 | v1.3: Revision #3 in Phase 3 | Removed soft "say more" prompt for short reviews; split unified "Aux" into "Aux" (self-directed personal signal) + "Like" (other-directed social engagement); added Likes on reviews + Most Liked sort; reverted Lists from MVP back to v2 (de-elevated R1's elevation) | Product Forge Phase 3 |
| 2026-05-22 | v1.4: Phase 5C clarification pass | Resolved 5 conditions from pre-impl-review: (1) added T117a synchronous critic-seed card algorithm; (2) specified 2 onboarding edge cases (deleted-account email + Spotify-OAuth-on-existing-email); (3) locked feed weighting math + tiebreak rules; (4) locked notification coalescer cross-type semantics; (5) locked rate-limiter fail-open policy. No new scope; clarifications only. | Product Forge Phase 5C |
