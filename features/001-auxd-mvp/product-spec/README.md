# Product Spec Index: auxd MVP

<!-- CR-001: status bumped to v1.5 reflecting R4 / CR-001 application. -->
> Status: REVISED v1.5 (CR-001 / R4 applied) | Feature: `001-auxd-mvp` | Date: 2026-05-22
> ← [Feature Root](../README.md) | ← [Research](../research/README.md)

<!-- CR-001: positioning rewritten — Letterboxd-for-music posture; manual log replaces streaming auto-import. Wedge restated as 3-of-4. -->
## What we're building

**auxd** is a social album-tracking platform for music-engaged listeners (18–35) — Letterboxd-for-music in posture. Log an album in <8 seconds via clean manual search with a ½-star rating, optionally add a review, see what people you follow thought of it, and discover what to play next from your social graph instead of an algorithm. First-session content comes from a curated critic-seed feed; the diary fills as you log.

The wedge is the *unhad combination* of three things none of the 13 prior Letterboxd-for-music attempts combined at once: **social-graph music discovery + clean manual logging at album-grain + casual-first onboarding** — 3-of-4 of the original combo. *(The 4th ingredient, auto-imported streaming history, was the planned activation primitive at v1.0–v1.3 but is deferred to v2 per CR-001 / R4 because the streaming-API gate is structurally unreachable pre-launch.)*

## Document Map

| Document | Purpose | Status |
|---|---|---|
| [product-spec.md](./product-spec.md) | Main PRD — overview, personas, capabilities, FR/NFR, risks, top-level decisions | DRAFT |
<!-- CR-001: document-index counts updated for R4 supersessions. -->
| [user-stories.md](./user-stories.md) | 27 Must-Have + 1 Should-Have + 3 Could-Have stories at MVP with Given/When/Then ACs, grouped by capability clusters | DRAFT (R4) |
| [user-journeys.md](./user-journeys.md) | 4 primary journeys at MVP + 1 deferred-to-v2 stub (Journey 1.5) | DRAFT (R4) |
| [data-model.md](./data-model.md) | 15 active entities + 2 deferred-to-v2 schemas (MusicProvider, JustFinishedPrompt) preserved, relationships, visibility rules, indexes (preliminary; finalized in Phase 5) | DRAFT (R4) |
| [notification-taxonomy.md](./notification-taxonomy.md) | 14 active notification types + 6 reserved-gap IDs, defaults, anti-spam guardrails, channel rules (CRITICAL — top churn driver) | DRAFT (R4) |
| [seeding-strategy.md](./seeding-strategy.md) | Originally 4-pronged cold-start; at MVP effectively 3-pronged (critic seed + invite mechanics + mutual-follow nudge — Last.fm import prong deferred to v2 per CR-001) | DRAFT (R4) |
| [success-metrics.md](./success-metrics.md) | North Star (WAL), M3/M6 targets, leading indicators, guardrails, anti-metrics | DRAFT |
| [out-of-scope.md](./out-of-scope.md) | v2 deferrals, permanent exclusions, v1.x candidates | DRAFT |
| [decision-log.md](./decision-log.md) | 12 open questions resolved + structural decisions + Phase 5 deferrals | DRAFT |
| [wireframes/index.html](./wireframes/index.html) | 4 critical screens, basic-html fidelity (onboarding, home feed, log sheet, album detail) | DRAFT |
| [digest.md](./digest.md) | Phase 2 auto-generated digest — key decisions, artifacts produced, open risks, handoff notes | SYSTEM |

<!-- CR-001: top decisions list updated to reflect R4 (CR-001) supersessions. -->
## Top decisions locked (Phase 2 + Phase 3 Revisions #1–#4)

1. **Streaming integration deferred to v2** *(R4 / CR-001)* — was: "Spotify-only at launch" (R1). Apple Music remains v2.
2. **½-star rating** (Letterboxd model)
3. **Just-finished auto-prompt cluster DEFERRED to v2** *(R4 / CR-001)* — was: "enabled at MVP" (R1)
4. **Public by default** with per-entry override
5. **Curated Lists DEFERRED to v2** — *R1 elevated, R3 returned to v2*
6. **Onboarding** = signup (email+password) → handle pick → follow ≥3 critics → critic-seed feed *(R4 / CR-001)* — was: streaming-auth with skip (R1)
7. **Album identity** = MusicBrainz MBID canonical, **Discogs ID** fallback *(R4 / CR-001)* — was: Spotify ID fallback (R0)
8. **Provider-interface abstraction** — CatalogProvider (MusicBrainz + Discogs at MVP) + MusicProvider (no impls at MVP; preserved for v2)
9. **No paid tier at launch** — future auxd Pro ($19/yr) + Patron ($39/yr) documented as future-state
10. **Heuristic social-graph recs** only at MVP — no ML
11. **PWA + responsive web only** — no native mobile
12. **Atlas Search against cached MusicBrainz subset** *(R4 / CR-001)* — was: Atlas + Spotify search
13. **Aux (🏅) vs Like (👍) split** — Aux = self-curation on your own DiaryEntry; Like = social engagement on others' Reviews — *R3 split; R1 had unified them*
14. **No soft prompt on short reviews** — *R3*
15. **Reviews are Likeable + sortable by Most Liked / Newest / Highest-Rated** — *R3*
16. **Critic seeds: pre-checked cards on Follow ≥3 (opt-in default-tick); minimum 3 follows** *(R4 raised from minimum 1)*
17. **Deluxe/remasters: merged under release-group MBID + Edition selector on detail** — *R2*
18. **Diary persists immutably on streaming disconnect** — *R2; N/A at MVP per CR-001 (no streaming connect surface)*
19. **Reviews: edits allowed, public shows latest+badge, 90d internal audit log** — *R2*
20. **Handles: immutable first 30d, then ≤1 change per 30d, obvious-squat reservations at launch** — *R2*
21. **Streaming OAuth scopes** — *N/A at MVP per CR-001 / R4 (no streaming OAuth)*

See [decision-log.md](./decision-log.md) for the full table with rationale.

<!-- CR-001: counts updated to reflect R4 supersessions. -->
## Counts (after Revisions #1 + #2 + #3 + #4)

- **27 Must-Have user stories** (~2.5–5 month build) — net of R1 (+7) + R3 (-6 Lists +1 S-C4 Like) + R4 / CR-001 (-3 deferred: S-A2, S-A3, S-B6). Prior count was 30.
<!-- sync-fix L2-014: FR-033 added by CR-001 spec.md propagated here (Run #4). -->
- **23 functional requirements active** (FR-001, FR-004 to FR-016, FR-018 to FR-020, FR-028 to FR-032, **FR-033**). Reserved-gap IDs: FR-002, FR-003, FR-017, FR-021..FR-025, FR-026, FR-027 (CR-001 + R3 deferrals; IDs preserved for audit, not reassigned). FR-033 "Report missing album" surfaces from the manual-search empty-state per CR-001.
- **14 notification types active** (N-001 to N-008, N-012 to N-017). Reserved-gap IDs: N-009, N-010, N-011, N-018 (CR-001 deferrals) and N-019, N-020 (R3 Lists deferral).
- **15 active data entities** at MVP (User, Album, DiaryEntry, Backlog, BacklogItem, Review, ReviewLike, Follow, FollowRequest, Block, Report, Notification, NotificationPreferences, SuggestedFollow, CriticSeed). **MusicProvider** and **JustFinishedPrompt** are preserved in the schema as DEFERRED-TO-V2 surface area but are unwired from the MVP — User.music_providers is always `[]` and no MVP code path writes or reads JustFinishedPrompt.
- **4 user journeys at MVP** (Journey 1 onboarding, Journey 2 manual-search log, Journey 3 social-graph discovery, Journey 4 backlog, Journey 5 long-form review). Journey 1.5 (just-finished auto-prompt) is DEFERRED-TO-V2 per CR-001; Journey 4.5 (Lists) removed in R3.
- **4 critical wireframes** *(redesign in progress — outside the scope of CR-001 spec edits per the change request)*
- **10 risks** with mitigations (catalog-provider + empty-first-session risks added; streaming-API + Extended-Quota-Mode risks removed per CR-001)
- **0 open questions remaining at spec level**

### What's left for Phase 5

Technical decisions (not spec-level) deliberately deferred:

<!-- CR-001: Atlas Search depends on MusicBrainz subset sample, not Spotify catalog. -->
- Atlas Search index tuning (depends on the MusicBrainz subset selected for caching)
- GDPR audit-log schema
- Final MongoDB indexes (preliminary table in data-model.md)
- Provider-interface exact method signatures
- Specific auth library + background-job runner picks
- Hosting / deployment target
- Cover-art proxy headers
- Observability stack composition

> *Scope expansion summary:* Revision #1 grew the MVP by approximately 20% (Lists + Auto-prompt elevated). Revision #2 resolved all open questions without expanding scope further — locked decisions add detail to existing stories/FRs but don't add new capabilities.

## Open questions resolved (Revisions #1 + #2)

All open questions raised in Phase 2 and surfaced during Phase 3 review have been resolved. Summary:

- **Revision #1** locked the 4 main user-facing defaults (Lists in MVP, auto-prompt enabled, Spotify skippable, Heart→Aux rename).
- **Revision #2** locked the 10 product-spec.md §10 questions (Q13–Q22) and 20 supporting-doc questions (NT-1..5, SS-1..5, DM-1..5, UJ-1..5).

See [decision-log.md](./decision-log.md) for the full resolution table with rationale.

## Risks carried forward

<!-- CR-001: streaming-API + Extended-Quota-Mode risks removed (the CR-001 pivot itself was the response to those risks). New risks added: catalog-provider downtime + empty-first-session friction. -->
| Risk | Where it's mitigated |
|---|---|
| H1 (user-research validation) never confirms | [product-spec §8](./product-spec.md), [success-metrics.md](./success-metrics.md), early-access interview wave |
| Catalog provider (MusicBrainz) downtime / data quality | [product-spec §8](./product-spec.md), Discogs fallback + circuit breaker |
| Empty-first-session friction (no streaming auto-import) | [seeding-strategy.md](./seeding-strategy.md), critic-seed feed is load-bearing |
| Cold-start ghost-town | [seeding-strategy.md](./seeding-strategy.md) — first-class document, effectively 3 prongs at MVP |
| Notification firehose churn | [notification-taxonomy.md](./notification-taxonomy.md) — conservative defaults, anti-pattern bans |
| Music metadata quality | [data-model §Album](./data-model.md), MBID canonical + Discogs fallback, album-merge admin UI |
| Privacy/safety incident | [product-spec §5 NFR](./product-spec.md), block + report from MVP |
| Performance regression | [product-spec §8](./product-spec.md), p95 NFRs, fan-out-on-read default |

## Must read first

1. [product-spec.md](./product-spec.md) — the source-of-truth PRD
2. [decision-log.md](./decision-log.md) — what we decided and why
3. [user-stories.md](./user-stories.md) — what we're building, story-by-story
4. [notification-taxonomy.md](./notification-taxonomy.md) — the load-bearing first-class doc
5. [seeding-strategy.md](./seeding-strategy.md) — the launch-blocker first-class doc

Everything else supports those five.
