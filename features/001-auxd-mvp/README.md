# Feature: auxd MVP — Social Album Platform

> Created: 2026-05-21 | Status: Phase 3 complete (Revalidation APPROVED) — ready for Phase 4 Bridge
> Slug: `001-auxd-mvp`
> Feature mode: `standard` | SpecKit mode: `classic`

## What is this?

auxd is a social album-tracking platform for casual Spotify listeners (18–35). Users log albums they've listened to, rate them (½-star scale, Letterboxd-style), write optional reviews, maintain a backlog of "want to listen" albums, and discover music via their social graph rather than algorithmic recommendations. Spotify OAuth on day one auto-imports recently-played history so the diary is never empty.

**The wedge** is the *unhad combination* of four things none of the 13 prior Letterboxd-for-music attempts combined: **auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding** — all four simultaneously.

## Lifecycle Status

| Phase | Status | Documents |
|---|---|---|
| 0. Problem Discovery | ✅ Complete | [problem-discovery/](./problem-discovery/) |
| 1. Research | ✅ Complete | [research/](./research/README.md) |
| 2. Product Spec | ✅ Complete | [product-spec/](./product-spec/README.md) |
| 3. Revalidation | ✅ Approved (v1.3, 3 revisions) | [review.md](./review.md) |
| 4. SpecKit Bridge | ✅ Complete | [spec.md](./spec.md) |
| 4.5. i18n Harvest | ⏳ N/A (English-only) | — |
| 5. Plan | ✅ Complete | [plan.md](./plan.md) |
| 5B. Tasks | ✅ Complete | [tasks.md](./tasks.md) |
| 5.5. Migration Plan | ✅ Complete | [migrations/](./migrations/migration-plan.md) |
| 5C. Pre-Impl Review | ✅ Approved with conditions (5/5 applied) | [pre-impl-review.md](./pre-impl-review.md) |
| 6. Implementation | ⏳ Pending | — |
| 6B. Code Review | ⏳ Pending | (code-review.md) |
| 7. Verification | ⏳ Pending | (verify-report.md) |
| 8A. Test Plan | ⏳ Pending | (testing/) |
| 8B. Test Run | ⏳ Pending | (test-report.md) |
| 9. Release Readiness | ⏳ Pending | (release-readiness.md) |
| 9.5. Monitoring Setup | ⏳ Pending | (monitoring/) |
| 9B. Experiment Design | ⏳ Pending | (experiment/) |
| 10. Retrospective | ⏳ Pending | (retrospective.md) |

## Quick Start

1. **Why this product exists:** [problem-discovery/problem-statement.md](./problem-discovery/problem-statement.md)
2. **Research synthesis:** [research/README.md](./research/README.md)
3. **The spec:** [product-spec/README.md](./product-spec/README.md) — start here for "what are we building"
4. **The wedge in one paragraph:** [product-spec/product-spec.md §1.3](./product-spec/product-spec.md)
5. **The decisions locked so far:** [product-spec/decision-log.md](./product-spec/decision-log.md)

## Top decisions locked (Phase 2 + Phase 3 Revisions #1–#3)

1. Spotify-only at launch (Apple Music = v2)
2. ½-star rating scale (Letterboxd model)
3. Auto-prompt for just-finished albums ENABLED at MVP (opt-out, default ON) — *R1*
4. Public-by-default with per-entry privacy override
5. **Curated Lists DEFERRED to v2** — *R1 elevated to MVP; R3 returned to v2*
6. Onboarding = Spotify auth + auto-import 30d, Spotify step explicitly skippable — *R1*
7. Album identity = MusicBrainz MBID canonical, Spotify ID fallback
8. PWA + responsive web only at MVP
9. **Aux (🏅) vs Like (👍) — split semantics** — *R1 unified as Aux; R3 split into Aux (self) + Like (social engagement on reviews)*
10. Critic seeds: pre-checked checkbox cards on Follow 3 (opt-in with default-tick) — *R2*
11. Deluxe / remasters: merged under release-group MBID + Edition selector on album detail — *R2*
12. Diary persists immutably on Spotify disconnect — *R2*
13. Reviews: edits allowed, public shows latest+badge, 90d internal audit log — *R2*
14. Handles: immutable first 30d, then ≤1 change per 30d, obvious-squat reservations at launch — *R2*
15. Spotify OAuth scopes locked: recently-played + currently-playing + library-read (playlist-read-private deferred) — *R2*
16. **No "say more" soft prompt on short reviews** — *R3*
17. **Reviews are Likeable (👍) + sortable by Most Liked / Newest / Highest-Rated** — *R3*

## Feature description (original input)

> Build a social platform where users can rate albums, track albums they've listened to, write and share reviews, keep a backlog of albums they'd like to listen to, and get album recommendations.

## Critical findings carried into Phase 3

- **Spotify deprecated audio-features / recommendations endpoints 2024-11-27** — strengthens the social-graph thesis; no algorithmic-rec fallback available.
- **Extended Quota Mode review (2–6 wk)** is on the critical path for public launch.
- **Constitution at `.specify/memory/constitution.md` is the unfilled template** — Phase 5 Task 0 must ratify principles before any feature work.
- **User-research validation gap** carried forward — H1 stays unresolved until live metrics + early-access interviews.
