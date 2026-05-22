# Research Index: Spinz (001-spinz-mvp)

> Generated: 2026-05-21 | Feature: `001-spinz-mvp`
> Input richness: 8/8 | Interview mode: CONFIRM (no interview needed)
> Research dimensions: competitors ✅ · ux-patterns ✅ · codebase ✅ · tech-stack ✅ · metrics-roi ✅
>
> **Web access caveat:** WebSearch / WebFetch and the MCP equivalents were denied at the harness layer for all 4 web-dependent agents (the codebase agent didn't need web). Outputs are drawn from agent training data through ~January 2026. Every quantitative claim carries a `[VERIFY]` flag in its source file; Phase 2 must spot-check the figures that gate spec decisions (pricing, conversion rates, Spotify API limits, deprecation dates).

## Executive Summary

Spinz's product wedge is the *unhad combination* of four things that today's competitors each have partially: **auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding**. Letterboxd proved the formula works in film. Last.fm proved auto-import scales at 70M signups. RateYourMusic and AOTY proved the depth audience exists but is power-user-only. No incumbent combines them.

The technical foundation is feasible — Spotify's social-core endpoints (auth, library, recently-played, search, album/track metadata) are stable and ToS-compatible. **A critical timing constraint emerged:** Spotify removed the audio-features / recommendations / related-artists endpoints for new apps on 2024-11-27. This *strengthens* Spinz's social-graph thesis (H2) because algorithmic recs from Spotify are no longer available; the product can't rely on a fallback. It also means Extended Quota Mode approval (2–6 week review by Spotify) is on the critical path for public launch.

Validation remains thin on the user-research dimension (Phase 0 deferred this gap to Phase 1; Phase 1 did not close it because web access was blocked). The H1 hypothesis ("casual listeners have an unmet remember/share moment") is still anecdotal. Phase 2 product-spec should narrow segment further and treat the first 8 weeks of metrics as the real validation gate, not the spec itself.

## Key Findings

| Dimension | Top Insight |
|---|---|
| 🏆 Competitors | Six concrete failure causes across prior Letterboxd-for-music attempts (no auto-import / empty network / catalog-first / no tastemaker seed / scope creep / mobile-second). The wedge is doing **all four simultaneously**, which none does. |
| 🎨 UX/UI | Copy Letterboxd's bottom-sheet log + ½-star + heart + optional review (sub-8-second commit) and chronological diary. Avoid Goodreads' notification firehose and AOTY/RYM's 100-point metadata wall. |
| 🔧 Codebase | Greenfield confirmed. **Constitution is the unfilled template** — Phase 5's Constitution Check gate is currently vacuous; run `/speckit-constitution` first or include ratification as Task 0. |
| 🔒 Constraints | Spotify Extended Quota Mode approval (2–6 wk review) is on the critical path. Audio-features / recs / related-artists endpoints deprecated 2024-11-27 — no algorithmic-rec fallback. Album-identity must normalize across Spotify ID and MusicBrainz release-group MBID. |
| 📦 Tech Stack | Next.js 15 App Router + TanStack Query + shadcn/ui (frontend); FastAPI async + Pydantic v2 + Beanie + Authlib + arq/Redis (backend); MongoDB Atlas + Atlas Search; heuristic social-graph recs at MVP (defer `implicit` ALS to v2). |
| 📊 Metrics | North Star = **Weekly Active Loggers (WAL)**. Letterboxd hit 1M in 6 yrs, 10M in 12 yrs; ~5% paid conversion at $19/$49 yr. Plan for ~10k users / ~$10k ARR by 12–18 months. Strava data suggests users following ≥5 retain ~3–4× longer at D90. |

## Research Documents

| Document | Status | Key Insight |
|---|---|---|
| [competitors.md](./competitors.md) | ✅ (4,600 w) | 13 competitors analyzed; H3 = six-cause stack of prior failures; H5 = Letterboxd pricing translates, target 1–3% conversion year 1. |
| [ux-patterns.md](./ux-patterns.md) | ✅ (5,308 w) | 22-row state inventory, 15-row anti-pattern table, 12 open questions for Phase 2. Wireframe Log sheet first. |
| [codebase-analysis.md](./codebase-analysis.md) | ✅ (3,154 w) | Greenfield. Constitution empty. 5 recommended principles. Front-load scaffolding before feature work. |
| [tech-stack.md](./tech-stack.md) | ✅ (9,446 w) | H4 validated with caveats. Spotify endpoint deprecation reframes the rec strategy. Detailed reference for Phase 5. |
| [metrics-roi.md](./metrics-roi.md) | ✅ (2,679 w) | North Star = WAL. M3/M6 target table. Letterboxd, Last.fm, Strava benchmarks. |
| [digest.md](./digest.md) | SYSTEM | Phase 1 auto-generated digest — synthesis, validated hypotheses, open questions handed forward to product-spec. |

## Hypothesis Verdicts (H1–H5)

| H# | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Casual Spotify listeners 18–35 have a recurring unmet "remember/share" moment | **UNRESOLVED** — competitor and cultural signals suggest yes, but no user interviews. **Owns Phase 2 risk.** |
| H2 | Social-graph recs feel more trustworthy than algorithmic | **STRENGTHENED** — Spotify's algo-rec endpoint deprecation makes social-graph the only viable path; less competition for that surface. |
| H3 | Prior Letterboxd-for-music attempts stalled for identifiable reasons | **CONFIRMED** — six concrete causes identified; combinatorial gap exists. |
| H4 | Spotify Web API supports the required patterns sustainably | **VALIDATED WITH CAVEATS** — social-core endpoints stable; audio-features removed; Extended Quota review required. |
| H5 | Free + premium model is segment-compatible | **DIRECTIONALLY YES** — Letterboxd model translates; target ~$19/yr Pro + ~$39/yr Patron, 1–3% conversion year 1 (not Letterboxd's mature 5%, because Spotify is already paying for the underlying job). |

## Synthesis: Recommended Approach

1. **Lock the wedge.** Phase 2 product-spec narrows to: (a) Spotify-auth-only at launch (Apple Music in v2); (b) auto-import recently-played as onboarding hook; (c) social-graph feed as default home, chronological order, weighted by reviews and ★★★★★/★ extremes from followed users.
2. **Front-load scaffolding.** Tasks 0–N in Phase 5B must be: ratify constitution, scaffold FastAPI + Beanie + Mongo + Authlib OAuth happy-path, scaffold Next.js shell + shadcn/ui + TanStack Query, scaffold Atlas Search index — **before** any feature work.
3. **Album-identity model.** Pick MusicBrainz release-group MBID as canonical key, Spotify album ID as fallback identifier. This decision is structural — wrong choice cascades into search, recommendation, dedup, and analytics.
4. **Notification taxonomy.** Nail it in Phase 2 product-spec, not late. Goodreads' default-on notification firehose is the #1 documented cause of churn in this niche; design notification scope and defaults as a first-class object.
5. **Tastemaker seeding strategy.** Phase 2 must specify the cold-start mechanism (founder-curated critic seed list + Last.fm import + invite mechanics + mutual-follow nudge). The product is worthless without a seed graph.
6. **No paid tier in M0–M3.** Defer monetization until WAL ≥ 1,000 and D30 retention ≥ 10%. Pricing exists in the spec as future-state ($19 Pro / $39 Patron), not launch-state.

## Open Questions for Product Spec (Phase 2)

These are research-raised but not research-resolved. Phase 2 must close them:

1. **Spotify-only vs multi-provider at launch.** Apple Music = larger US user base, more dev pain. Recommend Spotify-only MVP.
2. **Rating scale.** ½-star (Letterboxd-style) is the recommendation. Lock it.
3. **Feed composition algorithm.** Reverse-chronological + weighting (reviews, extreme ratings) — confirm or override.
4. **Backlog vs Spotify "Liked Songs" semantics.** What's the user-facing differentiator? Albums vs songs? Aspirational vs current?
5. **Review minimum length / required vs optional.** Recommend optional after rating (Letterboxd model).
6. **Public-by-default vs follower-only ratings/reviews.** Privacy default frames the product.
7. **Lists feature scope at MVP** (Letterboxd-style curated lists vs deferred to v2).
8. **Notification taxonomy** — full list with defaults and per-notification opt-in/opt-out.
9. **Tastemaker seeding strategy** (critic recruitment, invite mechanics, import flow).
10. **"Just-finished" detection** — auto-prompt from recently-played, or manual log only? Auto risks creepiness; manual loses moments.
11. **Wrapped-style year-end retrospective** — MVP or v2?
12. **Onboarding** — Spotify auth + import last 30 days, or zero-state with manual log first?

## Red Flags / Risks Identified

1. **User-research gap remains open.** Phase 0 deferred validation to Phase 1; Phase 1 deferred to "first 8 weeks of metrics" because web access blocked deeper market research. Phase 2 spec is therefore betting on cultural pattern matching, not data. *Mitigation:* run the Phase 0 interview-script during early-access wave.
2. **Spotify platform risk is concrete and recent** — the Nov 2024 endpoint deprecation is a precedent for unilateral capability loss. *Mitigation:* abstract every Spotify call behind a provider interface; design every feature to degrade gracefully if a Spotify capability disappears.
3. **Constitution gap.** No project-level principles in force. Phase 5 plan compliance check is currently a no-op. *Mitigation:* ratify constitution before plan (Task 0).
4. **Web-research provenance is offline-only.** Every figure in the research artifacts is from training data, cutoff Jan 2026. Quantitative claims used to gate spec decisions need a human re-verification pass during Phase 2 review.
5. **Cold-start network effect.** Social-first product without seed graph = ghost town. Seeding strategy is load-bearing for launch, not "marketing".
6. **Critical-path Spotify approval** — Extended Quota Mode review (2–6 wk) must start before public launch and is outside Spinz's control. Sequence accordingly in Phase 5 roadmap.

## Prior lessons that apply

No prior lessons log exists yet (`.product-forge/lessons.md` was not present at research time). This section will populate on subsequent feature cycles.
