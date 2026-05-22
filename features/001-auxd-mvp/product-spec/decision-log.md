# Decision Log: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 (Product Spec) | Date: 2026-05-21
> Status: DRAFT — open for revision in Phase 3 (Revalidation)
>
> Every decision below is the **default position** entering Phase 3. Where research-recommended, it's labeled. Reasoning is captured so revisions can be intentional. All decisions can be overridden in Phase 3 with a written rationale appended below the affected row.

---

## Product Wedge (locked from research; revised by CR-001 / R4)

<!-- CR-001: wedge thesis honestly restated as 3-of-4. Target-user re-scoped from "casual Spotify listeners" to "music-engaged listeners". Differentiator no longer references streaming-API deprecation. -->
| Decision | Choice | Rationale | Source |
|---|---|---|---|
| Wedge thesis | **(Revised by CR-001):** Social-graph-primary + album-as-unit + casual-first manual-log — 3-of-4 of the original combination. Auto-imported streaming history was the 4th ingredient at v1.0–v1.3 but deferred to v2 in R4. | None of 13 competitors does these three simultaneously; combinatorial gap is narrower but still real. The 4th ingredient (streaming auto-import) returns in v2. | research/competitors.md (H3), CR-001 / R4 |
| Target user | **(Revised by CR-001):** Music-engaged listeners 18–35 — Letterboxd-for-music posture | Not RYM power users; not generic music fans. Reframed from "casual Spotify listeners" because the MVP no longer assumes streaming-service-of-choice. | problem-discovery/problem-statement.md, CR-001 / R4 |
| Differentiator | Social-graph recs (not algorithmic) | Algorithm-distrust dynamic in the target segment; social-graph is the rec path that compounds. *(Pre-CR-001 rationale also cited streaming-API deprecation; CR-001 removed that bullet since the MVP doesn't depend on streaming APIs at all.)* | research/tech-stack.md |

---

## Open Questions — Resolutions

| # | Question | Decision | Rationale | Status |
|---|---|---|---|---|
<!-- CR-001: Q1 superseded — streaming integration deferred entirely. -->
| 1 | Spotify-only vs multi-provider at launch | **SUPERSEDED by CR-001 / R4.** Was: "Spotify-only at MVP, Apple Music = v2". Now: **no streaming integration at MVP** — see decision-log R4 row. Apple Music status unchanged (still v2). | The 250k-MAU Extended Quota Mode gate makes Spotify structurally unreachable pre-launch. | SUPERSEDED (v1.5 — CR-001) |
| 2 | Rating scale | **½-star, 0–5 in halves** (Letterboxd model) | UX research's top recommendation; granular enough for taste, simple to consume | LOCKED |
| 3 | Feed composition algorithm | **Reverse-chronological** from followed users, **weighted** toward (a) entries with a written review attached, (b) ★★★★★ and ★ extreme ratings, (c) entries by users the viewer interacts with most | Avoids "algorithm distrust" problem; transparent ordering; surfaces signal | LOCKED |
<!-- CR-001: Q4 reframed — comparison is now against generic streaming-service Liked semantics, not Spotify-specific. -->
| 4 | Backlog vs streaming-service "Liked" semantics | **Backlog = albums only**, distinct from streaming-services' generic "Liked"/track-favourite primitives (which are track-grain). Backlog is aspirational ("want to listen") not historical. | Keeps album-as-unit wedge intact; doesn't compete with the track-grain Liked primitive any streaming service exposes. | LOCKED (rationale narrowed by CR-001) |
| 5 | Review minimum length / required vs optional | **Optional after rating. No minimum length. No soft prompt** (revised in Revision #3, 2026-05-21). Reviews can be ≥1 character without any "say more?" nudge. | Letterboxd model; matches sub-8-sec log target. Soft prompts add nag-feel for users who legitimately want one-line reactions. | LOCKED (v1.3) |
| 6 | Public-by-default vs follower-only ratings/reviews | **Public by default**. Per-entry override to "followers only" or "private (diary only)". Profile-level "private profile" toggle in settings (default off). | Public is the Letterboxd default; required for the social-graph thesis to compound; private escape hatch for safety | LOCKED |
| 7 | Curated user-created lists | **Deferred to v2** (revised in Revision #3, 2026-05-21 — reverses Revision #1's MVP elevation). Founder reconsidered after seeing the scope cost. The MVP refocuses on the core wedge (log + rate + Aux + review + backlog + social-feed); Lists return as a post-launch capability once retention is validated. Re-eval trigger: WAL > 1k AND ≥10% of users ask for lists in feedback. | Significant UI/data complexity (drag-order, collab, cover-pickers, list-of-the-week surfacing). Build estimate dropped ~5–8 weeks. Lists were elevated in R1 then de-elevated in R3 after weighing scope vs. wedge focus — the wedge holds without Lists at MVP. | LOCKED (v1.3) |
| 8 | Notification taxonomy + defaults | **First-class spec document** ([notification-taxonomy.md](./notification-taxonomy.md)); conservative defaults — only "someone followed you" and weekly digest on by default | Top documented churn driver in niche (Goodreads firehose pattern); requires careful design | LOCKED |
| 9 | Cold-start / seeding strategy | **First-class spec document** ([seeding-strategy.md](./seeding-strategy.md)); 4-pronged: founder-curated critic seed roster + Last.fm history import + invite mechanics + mutual-follow nudge | Social product without seed graph = ghost town | LOCKED |
<!-- CR-001: Q10 superseded — just-finished auto-prompt deferred to v2. -->
| 10 | "Just-finished" auto-detection vs manual log only | **SUPERSEDED by CR-001 / R4.** Was: "Auto-prompt at MVP — opt-out, default ON" (R1). Now: **manual log only at MVP**. The just-finished cluster (S-B6, FR-026, JustFinishedPrompt entity, polling worker T123, N-018) is deferred to v2 and returns alongside streaming integration. Code surface preserved as unwired-from-MVP. | Streaming integration the prompt depends on is itself deferred (Q1 supersession); without it the auto-prompt has no detection source. | SUPERSEDED (v1.5 — CR-001) |
| 11 | Wrapped-style year-end retrospective | **Deferred to v2.** Will revisit Q4 2027 for first-year cohort. | High polish, seasonal; not blocking for launch; powerful virality lever once user base exists | LOCKED |
<!-- CR-001: Q12 superseded — onboarding flow simplified to no-streaming. -->
| 12 | Onboarding flow | **SUPERSEDED by CR-001 / R4.** Was: "Spotify auth + auto-import last 30 days, but explicitly SKIPPABLE" (R1). Now: **signup (email+password) → handle pick → follow ≥3 critics → critic-seed feed**. No streaming-auth step exists. Minimum follow count raised from 1 to 3 because there is no streaming taste signal to fall back on. | Streaming integration deferred (Q1 supersession); the skip path effectively becomes the only path. The "Follow 3" surface becomes load-bearing for first-session non-empty content. | SUPERSEDED (v1.5 — CR-001) |
| 13 | Critic seeds: followed-by-default at signup, or shown as suggested-only? | **Pre-checked checkbox cards on the "Follow 3" onboarding screen.** Critic-seed accounts appear in step 4 as cards with the follow-checkbox ALREADY TICKED; user can untick before tapping "Continue". Technically opt-in (explicit user assent), practically gets the "instant feed" outcome. No auto-follow without consent. | Default-follow without consent is brand-eroding (Twitter "topics you may like" pattern). Pure opt-in loses too much activation. Pre-checked cards is the proven middle. | LOCKED (v1.2) |
<!-- CR-001: Q14 superseded — no auto-import at MVP. -->
| 14 | Auto-import window: 30 days, 6 months, or all-available at signup? | **SUPERSEDED by CR-001 / R4.** N/A — no auto-import at MVP. The whole import-window concept returns alongside streaming integration in v2. | Q1 supersession. | SUPERSEDED (v1.5 — CR-001) |
<!-- CR-001: Q15 wording narrowed — only the streaming-id-keyed cascade is gone; release-group MBID merge remains in effect. -->
| 15 | Deluxe / remastered editions: separate album entries or merged under release-group? | **Merge under MusicBrainz release-group MBID; surface an "Edition" selector on the album detail page.** One canonical album entry per release group; Edition chip near the cover shows "All editions" with a dropdown for Standard / Deluxe / Bonus / etc. Ratings, reviews, and Aux'd aggregate across all editions. | Letterboxd-style merge for casual users; the Edition selector preserves power-user granularity without splitting the catalog. Cascade implications: search, dedup, analytics all key off the release-group MBID. *(CR-001 narrowed the rationale — pre-CR-001 the cascade also touched rec/streaming-fallback paths that no longer exist at MVP.)* | LOCKED (v1.2; rationale narrowed by CR-001) |
| 16 | Profile handle (`@`) reservation, mutability, squatting prevention | **Handles are unique, immutable for first 30 days after creation, then changeable once per 30 days.** 200–500 obvious-squat candidates (taylorswift, kendrick, drake, etc.) reserved at launch; claim-via-verification only after launch. Old handles become available 90 days after account deletion / abandonment, with a redirect period to prevent link-rot. No paid "claim your name" service at MVP. | Prevents impersonation chaos at launch; gives users flexibility without enabling churn-style handle hopping; respects the trust thesis. | LOCKED (v1.2) |
| 17 | Reviews: edits-after-publish or append-only? | **Edits allowed; edit history hidden from public; preserved internally for 90 days for moderation/audit.** Public surfaces (album detail, profile feed) show only latest version + small "edited" badge with timestamp on hover. Internal revision log enables admin to inspect bad-actor edits (e.g., review that went viral, then was changed). | Append-only with public history adds UI complexity and discourages typo edits. Hidden audit log balances trust + ergonomics. | LOCKED (v1.2) |
<!-- CR-001: Q18 adjusted — N-011 (spotify-reconnect) and N-018 (just-finished) removed from default channels because both types are deferred. -->
| 18 | Notification real-time vs digest taxonomy refinement | **Concrete defaults (adjusted by CR-001):** Real-time push (when push enabled): N-001 follow + N-002 follow-request only. Real-time in-app: N-001–N-006, N-012 (report-acknowledged), N-013/14 (deletion), N-016/17 (security). Daily/weekly digest: only N-008 (weekly digest). *(N-009/N-010/N-011 import + reconnect, N-018 just-finished, N-019/N-020 lists are all reserved-gap at MVP per CR-001 + R3.)* Coalescing per existing notification-taxonomy.md guardrails. | Aggregating individual notifications into intermediate daily roll-ups adds complexity for marginal gain. Weekly digest is the only batched channel; everything else is event-driven or off. | LOCKED (v1.2; channel list adjusted by CR-001) |
<!-- CR-001: Q19 superseded — no streaming connect/disconnect surface at MVP. -->
| 19 | Disconnect streaming mid-product-life — does the diary stay? | **SUPERSEDED by CR-001 / R4.** N/A — there is no streaming connect/disconnect surface at MVP. When streaming integration returns in v2, the "yes — immutable" rule from v1.2 re-applies. | Q1 supersession. | SUPERSEDED (v1.5 — CR-001) |
| 20 | Seed graph includes artists themselves, or only critics/curators? | **Critics + curators only at MVP.** Artists may join as regular users but are not surfaced via the CriticSeed roster. Artist-as-seed is a separate v1.x cohort with distinct badge ("Artist" vs "Critic"), distinct ranking rules, and possibly rate-limited self-promotion guidelines. | A critic's review of GNX has different epistemic weight than Kendrick's tweet about his own album. Mixing them in the same seed surface blurs the trusted-taste-graph thesis. *(CR-001 / R4: this decision becomes more load-bearing because the critic-seed feed is now the primary first-session content source.)* | LOCKED (v1.2; weight increased by CR-001) |
<!-- CR-001: Q21 superseded — no reach-back window at MVP. -->
| 21 | Albums released *during* user's reach-back window — included? | **SUPERSEDED by CR-001 / R4.** N/A — there is no reach-back window at MVP (no streaming auto-import). New releases enter the catalog the moment a user manually searches for them: MusicBrainz primary, Discogs fallback, `candidate` record for entries pending MBID reconciliation. | Q1 supersession. | SUPERSEDED (v1.5 — CR-001) |
<!-- CR-001: Q22 superseded — no streaming OAuth at MVP. -->
| 22 | Streaming OAuth scopes — which are essential vs nice-to-have at MVP? | **SUPERSEDED by CR-001 / R4.** N/A — no streaming OAuth at MVP. The scope-essentials decision returns alongside streaming integration in v2. | Q1 supersession. | SUPERSEDED (v1.5 — CR-001) |

---

## Structural decisions (carried from research)

| Decision | Choice | Rationale |
|---|---|---|
<!-- CR-001: album-identity key — Discogs ID replaces Spotify album ID as the secondary canonical key. -->
| Album-identity key | **MusicBrainz release-group MBID** canonical; **Discogs release ID** as fallback identifier when MBID unavailable | Cascades through search, dedup, analytics; MBID is the only stable cross-provider key. *(Pre-CR-001 the fallback was Spotify album ID; CR-001 swapped to Discogs as the actual catalog provider at MVP.)* |
<!-- CR-001: provider abstraction kept; MVP ships one impl per kind (MusicBrainz + Discogs). -->
| Provider abstraction | Two abstractions kept: **`CatalogProvider` Protocol** (impls at MVP: MusicBrainz, Discogs) and **`MusicProvider` Protocol** (impls at MVP: NONE — streaming integration deferred; preserves interface for v2). | Future-proofs the catalog + streaming surfaces independently; MVP ships exactly one impl per kind (MusicBrainz, Discogs) for catalog and zero for streaming. |
| Pricing tier | **No paid tier at launch**. Future auxd Pro ($19/yr) + Patron ($39/yr) documented in spec as future-state. | Per metrics-roi.md: defer until WAL ≥ 1,000 and D30 ≥ 10% |
| Native vs PWA | **Responsive web + PWA at MVP**. Native iOS/Android deferred. | Faster iteration; one codebase; lower platform-policy risk |
| Recommendation engine | **Heuristic social-graph recs only at MVP** (no ML); `implicit`/ALS deferred to v2 | Needs scale + data first; heuristic walking the follow-graph is sufficient for early days |
<!-- CR-001: search — Atlas Search against MusicBrainz cache primary; Discogs cold-fetch fallback. -->
| Search | **MongoDB Atlas Search** against a cached MusicBrainz subset; **Discogs cold-fetch** as fallback when Atlas + MusicBrainz return no hits | Native to chosen DB; less moving parts than Elasticsearch/Meilisearch at MVP scale. *(Pre-CR-001 the fallback was Spotify search; CR-001 swapped it.)* |
| Privacy default | Public profile + public ratings/reviews; per-entry override to followers-only or private | Letterboxd default; needed for social-graph compounding |
| **Terminology — "Aux" vs "Like" semantic split** (refined in Revision #3, 2026-05-21; supersedes the unified Aux terminology from Revision #1) | Two distinct concepts, two distinct names: <br> • **Aux (🏅)** = a deliberate personal-curation signal on your OWN content. Boolean on DiaryEntry: "this album is one of my standouts in MY diary." Rare and intentional. <br> • **Like (👍)** = a lightweight social engagement signal on OTHER users' content. Counter on Review: number of people who appreciated this user's review. Common and fast. <br> Lists are deferred to v2 (per decision #7), so no Aux-or-Like split applies there at MVP. | Letterboxd model: "Like" (heart) on your own log is personal-favorite; "Like" on a review is social. We had unified both under "Aux" in R1; founder split them in R3 to be precise about self-directed-curation vs other-directed-engagement. Two icons (🏅 for Aux, 👍 for Like) reinforce the distinction in UI. |
<!-- CR-001: D-001 narrowed to email/password signup only; D-002 superseded entirely because no streaming OAuth signup exists. -->
| **Onboarding edge case — email collision with deleted-status account** *(added in Phase 5C, 2026-05-22 — D-001 from pre-impl-review; narrowed by CR-001 / R4)* | If a user attempts email+password signup with an email tied to an account in `status: deleted` (i.e., scheduled-for-deletion grace period), REFUSE the signup. The signup screen shows a "Restore your account?" CTA. Tapping it requires the user to authenticate as the original account (email/password), then cancels the deletion via the same endpoint as US-G5 "cancel deletion". No new account is ever created over a deleted-status account. | Prevents impersonation, accidental data loss, and confusing dual-account state. The grace-period account is the canonical source of truth until hard-delete completes. |
| **Onboarding edge case — streaming-OAuth email matches existing email/password account** *(added in Phase 5C, 2026-05-22 — D-002; SUPERSEDED by CR-001 / R4)* | **SUPERSEDED by CR-001 / R4 — N/A at MVP** because there is no streaming-OAuth signup or connect path. Decision returns alongside streaming integration in v2 (the silent-auto-link prohibition + password-reauth-required rule will re-apply then). | Streaming integration deferred. | SUPERSEDED (v1.5 — CR-001) |
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
<!-- CR-001: NT-4 — review.auxed renamed to review.liked per R3 split. -->
| NT-4 | N-004 (review.liked) — in-app or aggregated into digest only? | **Both.** In-app for immediate feedback (low volume per user); digest aggregates ("your reviews got 12 likes this week") for absent users. |
<!-- CR-001: NT-5 superseded — "import succeeded" notification N/A because import is deferred. -->
| NT-5 | "Import succeeded" notification — every time, or first time only? | **SUPERSEDED by CR-001 / R4.** N/A — no streaming or Last.fm import at MVP, so the notification type (N-009/N-010) is reserved-gap. Decision returns when imports return in v2. | SUPERSEDED (v1.5 — CR-001) |

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
<!-- CR-001: DM-2 changed — Cover Art Archive replaces Spotify CDN. -->
| DM-2 | Cover-art storage: proxy Cover Art Archive vs cache to S3? | **Proxy Cover Art Archive.** No legal surface for storing cover art; saves S3 cost. Small blurhash placeholders cached client-side. *(Pre-CR-001 the proxied source was Spotify CDN; CR-001 swapped to Cover Art Archive.)* |
| DM-3 | Reactions on Reviews (likes count) — feature-flag the UI? | **Ship visible.** Already in the data model; gating for vanity is over-engineering. Volume will be low at MVP; that's fine. |
<!-- CR-001: DM-4 — tracklist source changed; per-track streaming IDs dropped. -->
| DM-4 | Tracklist storage: denormalize into Album or fetch on demand? | **Denormalize at MVP.** Tracklists are small; saves catalog-provider roundtrips on album detail page. Per-track streaming-IDs dropped from the embedded tracklist (per CR-001). Revisit if Album docs balloon. |
| DM-5 | Soft-deleted DiaryEntry: should reactions cascade? | **Yes — cascade.** Don't leave orphan `likes_count` aggregates or ReviewLike rows pointing at deleted entries. |

### User journeys (user-journeys.md questions)

| # | Question | Decision |
|---|---|---|
<!-- CR-001: UJ-1 superseded — no prefill source at MVP. -->
| UJ-1 | Log sheet prefilled album = most-recently-played track or most-recently-finished album? | **SUPERSEDED by CR-001 / R4.** N/A — no streaming prefill at MVP; log sheet opens with an empty search field. Decision returns when streaming integration returns in v2. | SUPERSEDED (v1.5 — CR-001) |
<!-- CR-001: UJ-2 superseded — no mutual-taste cards at MVP. -->
| UJ-2 | Onboarding "Follow N" card order — critics-first or mixed? | **SUPERSEDED by CR-001 / R4.** Mutual-taste cards required taste data from streaming history; with streaming deferred, only critic-seed cards are surfaced. The "Follow ≥3 critics" surface is critic-only. Decision returns when streaming and mutual-taste suggestions return in v2. | SUPERSEDED (v1.5 — CR-001) |
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
<!-- CR-001: Spotify CDN swapped for Cover Art Archive in the deferred-to-Phase-5 list (already resolved as DM-2). -->
| Cover-art storage strategy (proxy Cover Art Archive vs cache to S3) | Plan-time call; affects rate-limit math. *(CR-001 locked the source as Cover Art Archive; remaining call is proxy vs cache.)* |
| Feed read strategy (fan-out-on-write vs fan-out-on-read) | Sketched in data-model.md, locked in plan |
| Atlas Search index schemas | Plan time |
| Observability stack (Sentry / PostHog / OpenTelemetry combo) | Plan time |

---

## Decisions deferred to Phase 0 of Phase 5 (Constitution)

The constitution at `.specify/memory/constitution.md` is the unfilled template. Phase 5 must ratify principles before any feature work. Recommended principles (from research/codebase-analysis.md):

1. **External-call resilience** — every provider API call wrapped (retry + timeout + circuit breaker).
2. **Schema-versioned documents** — MongoDB documents carry `_schema_version` field; never assume shape.
3. **Library-first modules** — backend organized as composable libraries, not god-objects.
<!-- CR-001: principle reworded — Spotify-specific contract-test bullet replaced with catalog-provider + auth wording. -->
4. **Test-first for catalog/auth edges** — Catalog-provider (MusicBrainz + Discogs) integration and the auth flow have contract tests before implementation.
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
<!-- CR-001: R4 row added. -->
| 2026-05-22 | **v1.5: Revision #4 (CR-001) — Streaming integration deferred to v2** | Reason: Spotify Extended Quota Mode now requires 250k MAUs to apply (2026-05 policy change). The gate is structurally unreachable pre-launch (the app would be capped at 25 users forever). MVP pivots to a Letterboxd-style manual-search + rating model: MusicBrainz primary + Discogs fallback catalog; Atlas Search indexes a cached MusicBrainz subset; cover art via Cover Art Archive. Onboarding becomes signup → handle → follow ≥3 critics → critic-seed feed. The just-finished prompt cluster (US-B6, FR-026, JustFinishedPrompt, polling worker T123, N-018) is deferred to v2 — code preserved but unwired. Provider abstraction kept (CatalogProvider + MusicProvider); MVP ships one impl per catalog kind and zero streaming impls. Diary is empty at first session; critic-seed feed carries first-session content. **Decisions superseded:** Q1, Q10, Q12, Q14, Q19, Q21, Q22, D-002, NT-5, UJ-1, UJ-2. **Decisions narrowed:** Q4, Q15, Q18, Q20, DM-2, DM-4. **Stories deferred:** S-A2, S-A3, S-B6, S-H1. **Wedge thesis** restated as 3-of-4 of the original combination. | Product Forge Phase 6+ |
