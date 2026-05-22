# Research — Digest

> **Feature:** 001-spinz-mvp
> **Phase:** research
> **Generated at:** 2026-05-21T22:51:00Z
> **Artifact owner:** speckit.product-forge.research

## Key decisions

- **Product wedge locked:** auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding — *all four simultaneously*. None of the 13 competitors analyzed does all four.
- **H4 (Spotify integration) validated with caveats.** Social-core endpoints stable; audio-features / recommendations / related-artists deprecated 2024-11-27 for new apps — this *strengthens* the social-graph thesis (H2) by removing the algorithmic-rec fallback. **Extended Quota Mode (2–6 wk Spotify review) is on the critical path.**
- **H1 (user-research validation) UNRESOLVED.** Phase 0 deferred user interviews to Phase 1; Phase 1 deferred to "first 8 weeks of live metrics" because web tools were denied at the harness. Phase 2 spec carries this risk forward.
- **Tech stack chosen:** Next.js 15 App Router + TanStack Query + shadcn/ui (frontend); FastAPI async + Pydantic v2 + Beanie ODM + Authlib + arq/Redis (backend); MongoDB Atlas + Atlas Search; heuristic social-graph recs at MVP (defer `implicit` ALS to v2).
- **North Star metric:** Weekly Active Loggers (WAL). M3 / M6 targets: WAL 500 / 2,500; W1 activation 30% / 35%; D30 retention 8% / 12%.

## Artifacts produced

- `research/README.md` — synthesis, key findings, hypothesis verdicts, 12 open questions, 6 red flags.
- `research/competitors.md` — 13 competitor entries; H3 six-cause failure stack; H5 pricing translation; Reddit pulse; pricing reference table.
- `research/ux-patterns.md` — 22-row state inventory, 15-row anti-pattern table, 11 sections, 12 open questions for Phase 2.
- `research/codebase-analysis.md` — greenfield confirmation, constitution gap, 5 recommended principles, feed strategy + album-identity flags.
- `research/tech-stack.md` — 10 sub-problems, decision matrices, Spotify API deep audit, recommended stack table.
- `research/metrics-roi.md` — Letterboxd / Last.fm / Strava benchmarks, North Star defense, M3/M6 target table.

## Open risks

- **Unmitigated: user-research gap.** No live user signal supports H1 yet. Spec is betting on cultural pattern matching, not data. *Mitigation:* run the Phase 0 interview-script during early-access wave.
- **Unmitigated: web-research provenance is offline-only.** All quantitative claims (pricing, conversion rates, Spotify API limits, deprecation dates) are from training data through Jan 2026 and need spot-checking during Phase 2 review.
- **Accepted: Spotify platform risk.** Nov 2024 deprecation precedent is concrete; mitigation is the provider-interface abstraction in plan.
- **Unmitigated: cold-start seeding strategy is undecided.** Social product without seed graph = ghost town. Phase 2 spec must specify the seeding mechanism (critic recruitment + Last.fm import + invite + mutual-follow nudge).
- **Unmitigated: constitution gap.** Phase 5 Constitution Check is currently vacuous — no project principles in force. Task 0 of Phase 5B should ratify principles before any feature work begins.

## Handoff notes for next phase

- **Phase 2 must close** the 12 open questions in `README.md §Open Questions for Product Spec` — these are the spec decisions that gate the wedge.
- **Wireframe order matters.** Wireframe the Log sheet first (highest-leverage screen), then onboarding, then album detail. The Log sheet is the sub-8-second core interaction; if it's wrong, nothing else matters.
- **Notification taxonomy is a first-class object** for the spec — the #1 documented churn driver in this niche (Goodreads-style firehose). Spec must enumerate every notification with default state and per-item opt-in/opt-out.
- **Spotify-only at MVP** is the recommended scope; Apple Music is v2. Spec should narrow to this unless founder explicitly wants to widen.
- **Pricing exists in the spec as future-state, not launch-state.** Spinz Pro $19/yr + Patron $39/yr in the spec but launch is free-only until WAL ≥ 1,000 and D30 ≥ 10%.
- **Album-identity (MusicBrainz release-group MBID canonical, Spotify ID fallback)** is a structural decision the spec should commit to, not the plan — it cascades through search, dedup, recs, and analytics.
