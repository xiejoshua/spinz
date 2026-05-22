# Product Spec Index: Spinz MVP

> Status: REVISED v1.3 (pending Phase 3 final approval) | Feature: `001-spinz-mvp` | Date: 2026-05-21
> ← [Feature Root](../README.md) | ← [Research](../research/README.md)

## What we're building

**Spinz** is a social album-tracking platform for casual Spotify listeners (18–35). Log an album in <8 seconds with a ½-star rating, optionally add a review, see what people you follow thought of it, and discover what to play next from your social graph instead of an algorithm. Spotify auth on day one auto-imports recently-played history so the diary is never empty.

The wedge is the *unhad combination* of four things none of the 13 prior Letterboxd-for-music attempts combined: **auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding** — all four simultaneously.

## Document Map

| Document | Purpose | Status |
|---|---|---|
| [product-spec.md](./product-spec.md) | Main PRD — overview, personas, capabilities, FR/NFR, risks, top-level decisions | DRAFT |
| [user-stories.md](./user-stories.md) | 30 Must-Have + 2 Should-Have + 3 Could-Have stories with Given/When/Then ACs, grouped by 8 capability clusters | DRAFT |
| [user-journeys.md](./user-journeys.md) | 5 primary journeys with step-by-step + alternative paths + drop-off risk + metric goals | DRAFT |
| [data-model.md](./data-model.md) | 14 entities, relationships, visibility rules, indexes (preliminary; finalized in Phase 5) | DRAFT |
| [notification-taxonomy.md](./notification-taxonomy.md) | 17 notification types, defaults, anti-spam guardrails, channel rules (CRITICAL — top churn driver) | DRAFT |
| [seeding-strategy.md](./seeding-strategy.md) | 4-pronged cold-start: critic seed + Last.fm import + invite mechanics + mutual-follow nudge | DRAFT |
| [success-metrics.md](./success-metrics.md) | North Star (WAL), M3/M6 targets, leading indicators, guardrails, anti-metrics | DRAFT |
| [out-of-scope.md](./out-of-scope.md) | v2 deferrals, permanent exclusions, v1.x candidates | DRAFT |
| [decision-log.md](./decision-log.md) | 12 open questions resolved + structural decisions + Phase 5 deferrals | DRAFT |
| [wireframes/index.html](./wireframes/index.html) | 4 critical screens, basic-html fidelity (onboarding, home feed, log sheet, album detail) | DRAFT |
| [digest.md](./digest.md) | Phase 2 auto-generated digest — key decisions, artifacts produced, open risks, handoff notes | SYSTEM |

## Top decisions locked (Phase 2 + Phase 3 Revisions #1–#3)

1. **Spotify-only at launch** · Apple Music = v2
2. **½-star rating** (Letterboxd model)
3. **Auto-prompt for just-finished albums ENABLED at MVP** (opt-out, default ON) — *R1*
4. **Public by default** with per-entry override
5. **Curated Lists DEFERRED to v2** — *R1 elevated, R3 returned to v2*
6. **Onboarding** = Spotify auth + auto-import last 30 days **with prominent Skip option** — *R1*; skip = full product, no degraded mode
7. **Album identity** = MusicBrainz MBID canonical, Spotify ID fallback
8. **Provider-interface abstraction** for all music sources
9. **No paid tier at launch** — future Spinz Pro ($19/yr) + Patron ($39/yr) documented as future-state
10. **Heuristic social-graph recs** only at MVP — no ML
11. **PWA + responsive web only** — no native mobile
12. **Atlas Search** for catalog search
13. **Award (🏅) vs Like (👍) split** — Award = self-curation on your own DiaryEntry; Like = social engagement on others' Reviews — *R3 split; R1 had unified them*
14. **No soft prompt on short reviews** — *R3*
15. **Reviews are Likeable + sortable by Most Liked / Newest / Highest-Rated** — *R3*
16. **Critic seeds: pre-checked cards on Follow 3 (opt-in default-tick)** — *R2*
17. **Deluxe/remasters: merged under release-group MBID + Edition selector on detail** — *R2*
18. **Diary persists immutably on Spotify disconnect** — *R2*
19. **Reviews: edits allowed, public shows latest+badge, 90d internal audit log** — *R2*
20. **Handles: immutable first 30d, then ≤1 change per 30d, obvious-squat reservations at launch** — *R2*
21. **Spotify OAuth scopes locked: recently-played + currently-playing + library-read** (playlist-read-private deferred) — *R2*

See [decision-log.md](./decision-log.md) for the full table with rationale.

## Counts (after Revisions #1 + #2 + #3)

- **30 Must-Have user stories** (~3–6 month build) — net of R1 (+7) + R3 (-6 Lists +1 S-C4 Like); count reconciled in sync-verify Run #1 — see [sync-report.md § DRIFT-L2-003](../sync-report.md#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30)
- **27 functional requirements** active (FR-001 to FR-020, FR-026 to FR-032 — FR-021..FR-025 are reserved-gaps after Lists removal in R3)
- **18 notification types** active (N-001 to N-018; N-019 / N-020 reserved-gaps after Lists removal)
- **15 data entities** (User, MusicProvider, Album, DiaryEntry, Backlog, BacklogItem, Review, **ReviewLike** *(new R3)*, Follow, Block, Report, Notification, NotificationPreferences, JustFinishedPrompt, SuggestedFollow, CriticSeed) — List/ListItem removed
- **5 user journeys** (Journey 4.5 Lists removed in R3)
- **4 critical wireframes**
- **10 risks** with mitigations
- **0 open questions remaining at spec level**

### What's left for Phase 5

Technical decisions (not spec-level) deliberately deferred:

- Atlas Search index tuning (depends on Spotify catalog sample data)
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

- **Revision #1** locked the 4 main user-facing defaults (Lists in MVP, auto-prompt enabled, Spotify skippable, Heart→Award rename).
- **Revision #2** locked the 10 product-spec.md §10 questions (Q13–Q22) and 20 supporting-doc questions (NT-1..5, SS-1..5, DM-1..5, UJ-1..5).

See [decision-log.md](./decision-log.md) for the full resolution table with rationale.

## Risks carried forward

| Risk | Where it's mitigated |
|---|---|
| H1 (user-research validation) never confirms | [product-spec §8](./product-spec.md), [success-metrics.md](./success-metrics.md), early-access interview wave |
| Spotify changes API terms | [decision-log.md](./decision-log.md) provider-interface decision; v2 multi-provider readiness |
| Extended Quota Mode review delay | [seeding-strategy.md](./seeding-strategy.md) timeline; closed beta inside Development Mode quotas |
| Cold-start ghost-town | [seeding-strategy.md](./seeding-strategy.md) — first-class document, 4 prongs |
| Notification firehose churn | [notification-taxonomy.md](./notification-taxonomy.md) — conservative defaults, anti-pattern bans |
| Music metadata quality | [data-model §Album](./data-model.md), MBID canonical, album-merge admin UI |
| Privacy/safety incident | [product-spec §5 NFR](./product-spec.md), block + report from MVP |
| Performance regression | [product-spec §8](./product-spec.md), p95 NFRs, fan-out-on-read default |

## Must read first

1. [product-spec.md](./product-spec.md) — the source-of-truth PRD
2. [decision-log.md](./decision-log.md) — what we decided and why
3. [user-stories.md](./user-stories.md) — what we're building, story-by-story
4. [notification-taxonomy.md](./notification-taxonomy.md) — the load-bearing first-class doc
5. [seeding-strategy.md](./seeding-strategy.md) — the launch-blocker first-class doc

Everything else supports those five.
