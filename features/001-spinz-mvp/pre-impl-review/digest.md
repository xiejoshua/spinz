# Pre-Impl Review — Digest

> **Feature:** 001-spinz-mvp
> **Phase:** pre_impl_review (5C)
> **Generated at:** 2026-05-22T01:30:00Z
> **Artifact owner:** speckit.product-forge.pre-impl-review

## Key decisions

- **Recommendation: PROCEED WITH CONDITIONS** — the artifact stack is internally consistent, well-reasoned, and implementable. No critical design or architecture findings.
- **5 conditions for approval** (total effort ~65 min): add T117a (synchronous critic-seed card algorithm); spec 2 onboarding edge cases; lock feed weighting math + tiebreak; lock coalescer cross-type semantics; lock rate-limiter fail-mode.
- **No critical findings in design or architecture** — every dimension passed the structural checks.
- **2 critical risks identified** (R-001 H1 validation, R-002 cold-start) — both pre-existing from earlier phases with documented mitigations. No new critical risks surfaced by the review.
- **Rollout strategy confirmed** — closed beta → soft launch → public launch per plan §18 matches the risk profile (2 critical + 4 high risks justify staged rollout, which the plan already specifies).
- **Constitution alignment** — all 6 principles are satisfied by design, with 3 enforcement-via-convention areas flagged for future lint-rule additions (P3 library-first, P5 observability per-task, P6 provider abstraction).

## Artifacts produced

- `pre-impl-review.md` — full review document (~3,500 words). State completeness check across 4 wireframes + 5 journeys; UX pattern compliance; accessibility pre-check; integration point validation; NFR coverage; 6 design findings; 10 architecture findings; 13-risk register; pre-impl checklist.
- `pre-impl-review/digest.md` — this file.

## Open risks

- **R-001 (CRITICAL): H1 user-research validation never confirms.** Pre-existing from Phase 0; carried forward. Mitigation = run Phase 0 interview script during early-access wave; M3 KPI gate triggers pivot meeting if WAL <50% target. *No amount of pre-impl review can resolve this; only live signal will.*
- **R-002 (CRITICAL): Cold-start network effect — critic-seed recruitment is founder-bandwidth-bound.** Pre-existing from research/seeding-strategy. Mitigation = L-12 → L-0 playbook with cull cadence; delay public launch if seed conversion <20% after 4 weeks.
- **R-003 + R-004 + R-005 + R-006 (HIGH):** Spotify Extended Quota Mode delay, notification firehose, just-finished privacy perception, Spotify endpoint deprecation. All documented with mitigations in plan + tasks.
- **R-007 (MEDIUM): 180-task scope discipline.** Drift risk over a 3–6 month build. Mitigation = constitution + decision-log + Phase 6B code review.
- **R-010 (MEDIUM): GDPR cross-reference cascade gaps.** Add a follow-up test in T160 to cover ReviewLike records on both sides of deletion. Minor refinement.
- **5 WARNING-level architecture findings (A-001..A-005)** are deferred to "conditions for approval" — either fix inline before Phase 6 or accept as deferred-decision risk.

## Handoff notes for next phase

- **Phase 6 (Implement) start order is now:** address the 5 approval conditions (~65 min inline) → Task T001 (constitution) → Task T002 (Spotify Extended Quota Mode application, parallel) → continue per plan §18 build order.
- **If the 5 conditions are NOT addressed inline:** Phase 6 implementer will need to make these decisions during T117 (critic-seed cards), T106 (feed weighting), T133 (coalescer), T020 (rate-limit), and during T053/T054 (onboarding). The risk is making these decisions under task-completion pressure rather than in a clear-head review state. Founder choice; the orchestrator should record the choice as a gate condition.
- **C-1 (add T117a)** is the most impactful — without it, T117 + T118 cannot ship correctly. If accepting all conditions as deferred, surface this one explicitly to the implementer.
- **D-003 + D-004** (wireframes missing empty/loading/error states + 4 surfaces without wireframes) are intentional design tradeoffs from Phase 2. They land in Phase 6 as "design + implement" combined tasks, not as separate wireframing tasks. T178 (Final design polish) consolidates.
- **Constitution enforcement gaps (A-007, A-009, A-010)** are convention-only at MVP. Add lint rules to T004 backlog if/when team grows beyond founder.
- **C-3 (feed weighting tiebreak)** is a 15-min clarification but has subtle implications for testing — T107 (perf benchmark) should include tiebreak determinism in its test cases. Note for Phase 6.
- **No regression in product-spec/decision-log decisions** — pre-impl review didn't surface any decision-log issue. R3's Award/Like split + Lists deferral + skippable Spotify all remain sound.
- **No regression in plan technical choices** — fan-out-on-read, provider abstraction, monorepo topology, Vercel + Fly + Atlas + Upstash all hold up under review.
