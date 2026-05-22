# Product Spec — Digest

> **Feature:** 001-auxd-mvp
> **Phase:** product-spec (revised in Phase 3 Revalidation Revision #1)
> **Generated at:** 2026-05-21T23:10:00Z · **Revised at:** 2026-05-21T23:35:00Z
> **Artifact owner:** speckit.product-forge.product-spec
>
> **Revision #1 changes (2026-05-21):** Lists elevated from v2 to MVP (Cluster I, 6 stories, 2 new entities); Auto-prompt for just-finished detection elevated from v2 to MVP (S-B6, N-018, JustFinishedPrompt entity); Spotify connect made explicitly skippable (drops "degraded mode" framing); "Liked" / "Heart" renamed to "Aux'd" / "Aux" across all docs.
>
> **Revision #2 changes (2026-05-21):** All 10 product-spec.md §10 open questions resolved with locked decisions (Q13–Q22): critic seeds pre-checked, 30-day auto-import, deluxe/remaster merge under release-group + Edition selector, handle policy (30d immutability + change-rate-limit), reviews with hidden edit history, notification real-time vs digest taxonomy, diary-immutable-on-disconnect, critics-only-no-artists seed graph, lazy-fetch for fresh-release albums, OAuth scopes locked. All 20 supporting-doc questions resolved (NT-1..5, SS-1..5, DM-1..5, UJ-1..5). FRs 028–030 added (Edition selector, handle policy, review edit policy). Zero open questions remain at spec level.
>
> **Revision #3 changes (2026-05-21):** Removed "say more" soft prompt for short reviews; split unified "Aux" terminology into Aux (🏅 — self-curation on own DiaryEntry) + Like (👍 — social engagement on others' Reviews); added Likes on reviews (FR-031) + Most Liked sort (FR-032) + user story S-C4 + ReviewLike entity; reverted Lists from MVP to v2 (de-elevates R1's elevation — removed FR-021..025, Cluster I S-I1..S-I6, List+ListItem entities, N-019/N-020, Journey 4.5). Build estimate dropped back to 3–6 months. Net: 30 stories, 27 active FRs, 18 active notification types, 15 entities, 5 journeys.

## Key decisions

- **Target users:** Casey (casual Spotify listener 18–35, primary), Maya (engaged listener, secondary), Jamie (tastemaker/critic — also the cold-start seed roster).
- **Scope (post-Revision #1):** 37 Must-Have user stories across 9 capability clusters (onboarding, log/rate/aux, reviews, backlog, social graph, album detail/search, **Lists**, profile/settings/privacy, alternative imports). Apple Music, ALS recs, Wrapped, native mobile, collaborative Lists → v2.
- **Top 3 user stories (load-bearing):** S-A2 (auto-import last 30 days on Spotify connect — gates activation), S-B1 (log album in <8 seconds — the wedge interaction), S-E3 (weighted-reverse-chronological feed — the social-graph thesis surface).
- **Two first-class supporting docs:** notification-taxonomy.md (17 types, conservative defaults, anti-Goodreads-firehose discipline) and seeding-strategy.md (4-pronged cold-start: critic roster + Last.fm import + invites + mutual-follow nudge).
- **Structural decisions locked:** Spotify-only at launch (skippable at signup); ½-star rating; public-by-default; **Lists + Auto-prompt in MVP**; "Aux" replaces "Heart"; MusicBrainz MBID canonical / Spotify ID fallback; provider-interface abstraction; PWA-only; no paid tier at launch.

## Artifacts produced

- `product-spec/product-spec.md` — main PRD (~2,700 words). Personas, capabilities, FR-001 to FR-020, NFRs, risks, top-level decision log, 10 open questions.
- `product-spec/user-stories.md` — 35 stories with Given/When/Then ACs, grouped by capability cluster.
- `product-spec/user-journeys.md` — 5 primary journeys (onboarding, log-in-<8s, social-graph-discover, backlog management, write/share review) with alternatives, drop-off points, metric goals.
- `product-spec/data-model.md` — 14 entities with field-level sketches, visibility rules, preliminary indexes, deferrals to Phase 5.
- `product-spec/notification-taxonomy.md` — 17 notification types, per-channel defaults, anti-spam guardrails, settings UI, anti-pattern bans.
- `product-spec/seeding-strategy.md` — 4-pronged cold-start strategy, founder pre-launch playbook (L-12 to L 0), operational levers.
- `product-spec/success-metrics.md` — North Star (WAL), M3/M6 targets, leading indicators, guardrails, anti-metrics.
- `product-spec/out-of-scope.md` — v2 deferrals, permanent exclusions, v1.x candidates.
- `product-spec/decision-log.md` — full decision table for 12 open questions + structural decisions + Phase 5 deferrals.
- `product-spec/wireframes/` — 4 critical screens in basic HTML (index, onboarding, home feed, log sheet, album detail) + index page.
- `product-spec/README.md` — index over all of the above.
- `product-spec/digest.md` — this file.

## Open risks

- **Unmitigated — H1 user-research validation.** No live user signal supports the "remember/share moment" hypothesis yet; spec is built on competitor pattern matching, not user data. *Mitigation:* run interview script (problem-discovery/interview-script.md) during early-access wave; treat first 8 weeks of live metrics as the validation gate; pivot/iterate decision at M3.
- **Unmitigated — Phase 5 constitution gap.** Project constitution at `.specify/memory/constitution.md` is the unfilled template. Phase 5's Constitution Check gate is currently vacuous — Task 0 must ratify principles before any feature work.
- **Unmitigated — cold-start critical mass.** Seeding strategy requires founder direct work (50+ critic outreach attempts, ~30 active seeds before launch); if conversion is <20% after 4 weeks of outreach, launch must delay. Seeding is launch infrastructure, not marketing.
- **Unmitigated — Spotify Extended Quota Mode review.** 2–6 week external dependency on Spotify's review queue; must start application Day 1 of Phase 6. Risk: rejection or stuck-in-review pushes public launch.
- **Accepted — quantitative research figures are training-data-based.** Web access was denied during Phase 1; pricing, conversion rates, and Spotify API limits are flagged for spot-check during Phase 3.
- **Accepted — 12+10 open questions remain.** Many are intentional Phase 3 deferrals (refine in revalidation) and Phase 5 deferrals (technical decisions belong in plan, not spec). Tracked in the documents that own them.

## Handoff notes for next phase

- **Phase 3 (Revalidation) should focus on:** (a) the 10 product-spec.md §10 open questions, especially Q1 (critic-seed follow defaults) and Q4 ("Liked" heart visibility) which have strong user-facing consequences; (b) the open questions in notification-taxonomy.md (especially the digest cadence and N-004 aggregation choice); (c) the seeding-strategy.md questions about critic-seed compensation model.
- **Phase 4 (Bridge to SpecKit spec.md) should:** carry forward the 30 Must-Have user stories with their Given/When/Then ACs verbatim; carry forward the data-model.md entity sketches; preserve the wedge thesis statement; note feature_mode is standard (classic SpecKit, not v-model).
- **Phase 5 (Plan) needs to:** decide fan-out-on-write vs fan-out-on-read for feed; finalize MongoDB indexes; pick auth library; choose background-job runner; specify Spotify API rate-limit + retry strategy; design provider-interface abstraction; **ratify constitution before any plan-level work begins**.
- **Wireframes intentionally exclude:** profile pages, settings pages, search results, backlog/Up Next screens, secondary onboarding steps. These follow established UX patterns in research/ux-patterns.md and can be designed during implementation; their omission here is by choice, not gap.
- **No mockups produced.** Greenfield project has no design tokens to scan; mockups would be generic noise. High-fidelity design happens during implementation, not in Phase 2.
- **No i18n harvest applicable.** Project is English-only at MVP per decision-log; copy strings are extracted to keys for future locales but no harvest run is needed.
- **No migration plan applicable yet at this phase.** Data model has Data Model section → Phase 5.5 (Migration Plan) will trigger during plan phase, not now.
