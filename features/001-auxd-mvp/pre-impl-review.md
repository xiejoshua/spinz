# Pre-Implementation Review: auxd MVP

> Feature: `001-auxd-mvp` | Date: 2026-05-22
> Reviewer: Product Forge Pre-Impl Review Agent
> Status: **PROCEED WITH CONDITIONS** — 6 minor clarifications to make before Phase 6 begins

## Summary

| Section | Findings | Severity breakdown |
|---|---|---|
| Design Review | 6 findings | 0 critical · 4 warning · 2 info |
| Architecture Review | 10 findings | 0 critical · 5 warning · 5 info |
| Risk Assessment | 13 risks | 2 critical · 4 high · 4 medium · 3 low |

**Recommendation: PROCEED WITH CONDITIONS**

- No critical design or architecture findings — the spec, plan, and tasks are coherent and load-bearing decisions are sound.
- 6 specific clarifications (listed in Conditions for Approval) should be added to the spec or plan before Phase 6 starts. Most are 5–30 minute additions.
- 2 critical risks are pre-existing (carried from Phase 0 and Phase 1); both have documented mitigations.

---

## Design Review

> Scope: 4 wireframes (onboarding, home feed, log sheet, album detail) + 5 user journeys + 32 Must-Have stories. Profile, settings, search, backlog screens deliberately not wireframed (founder accepted this in Phase 2; design polish during implementation per [product-spec/wireframes/index.html](./product-spec/wireframes/index.html)).

### State completeness check

| Screen | Happy | Empty | Loading | Error | Partial | Offline |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Onboarding "Confirm last 30 days" | ✅ | ⚠️ (intent in S-A2 AC; not wireframed) | ⚠️ (intent in S-A2 AC; not wireframed) | ⚠️ (intent in S-A2 AC; not wireframed) | ✅ (skip allowed) | N/A |
| Home feed | ✅ | ⚠️ (intent in S-A5 AC; not wireframed) | ⚠️ (not wireframed) | ⚠️ (not wireframed) | ✅ (critic-seed padding) | ⚠️ |
| Log sheet | ✅ | ✅ (manual search fallback if no prefill) | ⚠️ (not wireframed) | ⚠️ (Spotify down → manual search) | N/A | ⚠️ |
| Album detail | ✅ | ⚠️ ("Report missing album" intent in S-F2; not wireframed) | ⚠️ (not wireframed) | ⚠️ (not wireframed) | ✅ (no friends rated this) | ⚠️ |

Design intent for empty/loading/error states EXISTS in user-stories.md acceptance criteria; what's missing is visual representation in wireframes. Not a blocker — Phase 6 implementation will design these inline. The team should track this in T178 (final design polish pass).

### UX pattern compliance (vs research/ux-patterns.md)

| UX recommendation | Addressed? | Notes |
|---|:---:|---|
| Bottom-sheet log with ½-star + Aux + optional review (<8s commit) | ✅ | T077 (Log sheet) implements; T084 validates timing |
| Chronological diary (no algorithmic reorder) | ✅ | S-B5, S-E2 |
| Recency-ordered feed weighted by review + extreme ratings | ✅ | S-E3, T106; **see A-002 finding on tiebreak** |
| Goodreads-style notification firehose AVOIDED | ✅ | notification-taxonomy.md conservative defaults; T133 coalescer |
| AOTY/RYM 100-point + metadata wall AVOIDED | ✅ | ½-star locked; album-detail is friend-first |
| Mobile-first PWA with bottom-tab nav | ✅ | T037 |
| Just-finished prompt with one-tap disable | ✅ | T127, T129; respects user autonomy |
| Letterboxd-style critic surface | ⚠️ | Critic "· Critic" suffix (T152) is correct but understated. Founder may want to revisit visibility post-launch. |

### Accessibility pre-check (WCAG 2.1 AA)

| Check | Status | Notes |
|---|:---:|---|
| Color contrast | ⚠️ | Wireframes use grayscale placeholders; T178 must pick a palette that hits 4.5:1 on text + 3:1 on UI components |
| Touch target sizes ≥44pt | ⚠️ | Wireframes don't measure; T077 + T127 + Log FAB (T078) must hit this |
| Focus order logical | ⚠️ | Not in wireframes; Phase 6 task adds focus management |
| Screen reader landmarks | ✅ | Implicit in shadcn/ui + Next.js App Router; verified by T171 (axe-core audit) |
| Error messages descriptive | ⚠️ | User-stories.md has user-facing copy; AC review at T053, T101 etc. should verify |
| Form labels present | ✅ | React Hook Form + shadcn/ui Form component enforces |
| Reduced-motion respect | ⚠️ | Not explicitly addressed; T178 must |

T171 (a11y audit) is in the plan and gates pre-launch. The above gaps will surface in T171 if not caught earlier.

### Component reuse

N/A — greenfield project. No existing components to reuse. shadcn/ui generation in T032 establishes the component base.

### Design findings

| ID | Severity | Finding | Recommendation |
|---|:---:|---|---|
| **D-001** | WARNING | Onboarding edge case: user signs up via Spotify on email tied to an account scheduled for deletion (grace period). Behavior not specified. | Add to product-spec/decision-log.md and US-A1 AC: "If email is associated with a deleted-status account, refuse signup and return a 'Restore your account' CTA that cancels the deletion." |
| **D-002** | WARNING | Onboarding edge case: user starts email/password signup, later tries to sign in with Spotify OAuth whose email matches the existing account. Should auto-link the Spotify provider or show a "Connect Spotify to your existing account?" flow. | Add to US-A2 AC: "If Spotify returns email matching an existing active auxd account, prompt to connect (auth via auxd password first), then attach `MusicProvider` sub-doc. Do NOT auto-link silently." |
| **D-003** | WARNING | Wireframes don't show empty/loading/error states for any of the 4 critical screens. Design intent lives in user-stories AC but isn't visualized. | Add to T178 (Final design polish pass): explicit subtask to design + implement empty/loading/error states for all 4 critical screens + profile + settings + search + backlog. |
| **D-004** | WARNING | Profile, settings, search, backlog screens have no wireframes — design happens during implementation. Risk: design drift / inconsistent surfaces. | Acceptable for a single-founder MVP; flag for Phase 6 to design-spec each surface BEFORE implementing it (one task = design + implement per surface). Track in T178 + per-screen tasks. |
| **D-005** | INFO | "Most Liked" sort tiebreak when `likes_count` is equal between two reviews — not specified. | Add to FR-032 and US-C2 AC: "Within the same `likes_count` bucket, order by `created_at` descending (newer first). Within the same `likes_count` AND `created_at`, order by review_id (stable)." |
| **D-006** | INFO | Block → existing-like interaction: if user A previously liked user B's review, then A blocks B, does the like auto-remove? Not specified. | Add to US-G4 + US-C4 AC: "Block cascades: existing ReviewLike records by blocker on blockee's reviews are deleted. Likes-count counters decrement. No notification fires for the implicit un-like." |

---

## Architecture Review

### Structural checks

| Check | Status | Evidence |
|---|:---:|---|
| Separation of concerns (routes / service / model layers) | ✅ | Plan §6 enforces routes.py / service.py / models.py per module |
| Dependency direction correct (no circular deps) | ✅ | Plan §6 module surface is single-public-service per module |
| API contracts complete | ⚠️ | Plan describes endpoints but doesn't fully spec request/response schemas. OpenAPI-codegen pipeline (T028) generates types from Pydantic models, so contracts emerge as models are built. Acceptable but front-loaded API contracts would catch frontend/backend mismatches earlier. |
| Data model consistent with spec entities | ✅ | 15 entities in plan §3 match data-model.md after R3 (Lists removed); ReviewLike added |
| Migration strategy defined | ✅ | Phase 5.5 migration plan locked |
| Error handling patterns defined | ✅ | T052 (provider error taxonomy) + Sentry capture in T015 |
| Authentication/authorization approach defined | ✅ | Plan §4 (Authlib + HMAC session cookies + lib/visibility) |
| Caching strategy defined | ✅ | Plan §17.5 (Upstash Redis: album metadata 7d, user listening 1h, OAuth state, rate-limit) |

### Integration point validation

| Integration | Plan coverage | Risk |
|---|:---:|:---:|
| Spotify Web API (OAuth + recently-played + currently-playing + library-read + album + search) | ✅ | M |
| Apple Music API | ✅ Deferred to v2 (correctly) | L |
| MusicBrainz API (release-group lookup, MBID reconciliation) | ✅ Rate-limited to 1 req/s; backfill via worker | L |
| MongoDB Atlas (M0 → M10 upgrade path) | ✅ Plan §17.4; migration scripts ready | L |
| Atlas Search index | ⚠️ Manual UI step at M0; Atlas Admin API automation deferred to v1.x | M |
| Upstash Redis | ✅ Serverless; free tier covers M3 | L |
| Postmark (transactional email + weekly digest) | ✅ DNS configured pre-launch (T007) | L |
| Web Push API + VAPID | ✅ T008 generates keys; T128 adapter | L |
| Sentry (errors) | ✅ T015 + T036 | L |
| PostHog (self-hosted, single Fly container) | ⚠️ Self-hosted ops is a footgun if it goes flaky; fallback plan to PostHog Cloud documented in plan §15.2 | M |
| Fly.io (api + worker) | ✅ Plan §17.2 | L |
| Vercel (web) | ✅ Plan §17.1 | L |

### NFR coverage

| NFR | Plan approach | Adequate? |
|---|---|:---:|
| p95 home feed load <500ms | Fan-out-on-read + Redis cache + SSR | ✅ |
| p95 album detail <400ms | SSR + cached metadata | ✅ |
| Spotify 30-day import p99 <8s | async + httpx + per-user batch | ✅ |
| 99.5% monthly uptime | Single-region M0 — adequate for MVP; multi-region post-M3 | ✅ |
| 10k concurrent users at peak | Fly.io scales; MongoDB M10 supports this; PostHog self-hosted may bottleneck | ⚠️ |
| WCAG 2.1 AA | Plan + T171 audit + shadcn/ui + Radix primitives | ✅ |
| Privacy + no third-party tracking | Self-hosted PostHog + Sentry (errors only) + no ad SDKs | ✅ |
| Security (OAuth tokens encrypted, bcrypt 12, CSRF, rate limit) | T017 + T019 + T020 + T053 | ✅ |
| GDPR (export + erasure within 30d) | T058 + T153 + gdpr_audit_log | ✅ |
| Spotify ToS ("Powered by Spotify" attribution) | T002 application + T070 album detail design | ⚠️ Founder should verify branding placement during T178 design polish |
| i18n / l10n | English-only at MVP; copy keys extracted | ✅ |
| Mobile responsiveness | Mobile-first design; PWA installable | ✅ |
| SEO | Album + profile SSR with OG tags | ✅ |
| Observability | Sentry + PostHog + structured logs + OTel | ✅ |

### Architecture findings

| ID | Severity | Finding | Recommendation |
|---|:---:|---|---|
| **A-001** | WARNING | Feed weighting uses "top-5-interacted users" multiplier but doesn't define "interaction". Without a definition, T106 implementation will guess. | Add to plan §10.2: "interaction" = weighted sum (likes given by viewer to user × 3 + reviews-of-their-albums-this-month × 2 + profile visits by viewer × 1), normalized; top-5 computed nightly. |
| **A-002** | WARNING | Feed sort tiebreak when scores are identical — not specified. | Add to plan §10.2: "When score is identical, secondary sort is logged_at descending; tertiary sort is entry_id (stable, KSUID guarantees ordering)." |
| **A-003** | WARNING | Notification coalescer cross-type vs per-type semantics is ambiguous. If user X follows + likes 5 reviews of user Y in 1 hour, is that 6 separate or coalesced? | Add to plan §8.2 + notification-taxonomy.md: "Per-actor rate limit (≤3/24h to same recipient) is CROSS-TYPE — counts all notification types from actor X to recipient Y in the window. Per-type rate limits (≤5/hr global to user) are independent." |
| **A-004** | WARNING | Rate-limiter fail-mode when Redis is unavailable — not specified. Critical for correctness vs availability tradeoff. | Add to plan §1.1 + T020 description: "If Redis is unreachable, rate-limit middleware FAILS OPEN (allows requests) and emits Sentry alert with tag `rate_limit.redis_down`. Spotify rate-limiting also fails open with the same alert (Spotify itself enforces per-app limits at their edge — our limiter is defensive)." |
| **A-005** | WARNING | T117 (critic-seed onboarding cards) algorithm depends on T104 (suggested-follow precompute worker), but onboarding needs synchronous "compute cards NOW from just-imported diary" mode — not batch-precomputed. | Add new task T117a (Size: M, Deps: T117): "Synchronous card-ordering for onboarding. Given a freshly-imported diary, compute genre-signature → score critic-seeds → return top 6 (with ≥3 critics) within 1s. Uses same scoring as T104 batch but runs inline. Mark cards pre-checked." |
| **A-006** | INFO | Atlas Search index gives equal weight to title and artist_credit. Music search is typically title-driven. | Tune in T068 starting weights: title × 2.0, artist_credit × 1.0, artists.name × 0.8. Re-tune post-launch based on PostHog `search.executed.result_count` distribution. |
| **A-007** | INFO | Beanie base Document class enforcing `_schema_version: int = 1` (Constitution P2) is implicit in T012 description. Could drift if a future model forgets to inherit. | Make T012 explicit: "Create `class auxdDocument(beanie.Document)` base class with `_schema_version: int = 1` enforced via Pydantic model validator. ALL feature models in §2 (T021–T030) inherit from `auxdDocument`, not from `beanie.Document` directly. CI lint rule (T004) flags any direct `beanie.Document` import outside the base." |
| **A-008** | INFO | Constitution P5 (Observability) — many tasks don't explicitly call out PostHog events. Plan §15.2 enumerates the events but task ACs don't reference them. | Amend T053, T077, T088, T101, T108, T118, T127, etc. ACs to include: "Emit PostHog event per plan §15.2 (e.g., `log.commit` with `duration_ms`, `review.liked`, `follow.created` with source)." A blanket cross-cutting task (T015) builds the helper but doesn't add events per-feature; per-task callouts ensure no event is forgotten. |
| **A-009** | INFO | Constitution P3 (library-first) enforcement is convention-only. No lint rule prevents `from modules.diary.internals.helper import _internal_func`. | Acceptable at MVP; add to T004 future enhancement list: lint rule that flags any import of `modules.X.something` where `something` ≠ `service`, `routes`, `schemas`, `models`. |
| **A-010** | INFO | Constitution P6 (provider abstraction) enforcement is convention-only. No lint rule against direct `spotipy` or other provider-SDK imports outside `providers/`. | Acceptable at MVP; add to T004 future enhancement: lint rule that flags direct provider-SDK imports outside `providers/` directory. |

---

## Risk Assessment

### Risk register

| ID | Category | Risk | Likelihood | Impact | Severity | Mitigation |
|---|---|---|:---:|:---:|:---:|---|
| **R-001** | Scope / Validation | H1 (user-research validation) never confirms — casual listeners don't actually want this product | M | H | **CRITICAL** | Phase 0 interview script available; run during early-access wave. M3 KPI gate (WAL <250 = pivot meeting). Pivot/shutdown decision point at M3 if North Star <50% of target. Accept that the MVP is a betting strategy on cultural-pattern-matching, not data. |
| **R-002** | Operational | Cold-start network effect — critic-seed roster doesn't reach critical mass before launch | M | H | **CRITICAL** | Seeding-strategy.md L-12 → L-0 playbook; founder ownership of recruitment; cull inactive seeds; launch delays if conversion <20% after 4 weeks of outreach. T162 + T166 + T177 carry this. |
| **R-003** | Technical / External | Spotify Extended Quota Mode application denied or stuck in review | M | H | HIGH | T002 submits Day 1 of Phase 6; closed beta + soft launch waves entirely inside Development Mode 25-user quota. If denied, re-application after addressing rejection reasons OR partner-app approach. |
| **R-004** | Technical | Notification firehose drives churn (Goodreads pattern) — coalescer logic edge cases | M | H | HIGH | Conservative defaults; granular per-type per-channel toggles; weekly digest primary surface. PostHog dashboard "notification rate per user per week" with alert at p95 >12 (T144). |
| **R-005** | Privacy / UX | Just-finished detection feels surveillance-y for some users → mass opt-out | M | M-H | HIGH | One-tap "Disable auto-prompts" from prompt menu (T129); in-app default ON, push opt-in. Watch PostHog `prompt.disabled_rate` — if >15% in first 30 days, the wedge needs rethinking. |
| **R-006** | Technical / Platform | Further Spotify endpoint deprecation (Nov 2024 precedent — audio-features, recs, related-artists removed) | M | H | HIGH | Provider-interface abstraction (T041); design every feature to degrade gracefully. Apple Music ready as v2 fallback. Monitor Spotify developer changelog. |
| **R-007** | Scope | 180-task scope discipline — drift, scope creep, Lists creeping back in | M | M | MEDIUM | Constitution + decision-log are the contract; flag any PR that adds out-of-scope content. Pre-impl review (this doc) sets the baseline. Phase 6B (code review) catches drift. |
| **R-008** | Performance | Feed performance at scale — fan-out-on-read may not survive 1k+ followers | M | M | MEDIUM | PostHog dashboard with p95 alert at 200ms triggers fan-out-on-write switch (plan §10.3). Load-modeling validated for M6 target (2,500 WAL); switch threshold documented. |
| **R-009** | Quality | Atlas Search relevance unknown until live data | M | M | MEDIUM | Spotify search fallback merge (T069); iterate index post-launch using PostHog `search.executed.result_count` distribution. Initial weight: title × 2, artist × 1 (per A-006). |
| **R-010** | Compliance | GDPR cascade complexity — cross-reference cascades for review-likes, follows, blocks of deleted users | L | H | MEDIUM | T058 cascade list comprehensive; T160 integration test covers full deletion lifecycle. Add follow-up test: ReviewLike records by deleted user → deleted; ReviewLike records of deleted user's reviews → deleted (both directions). |
| **R-011** | Quality | Music metadata quality (deluxe editions, regional variants, missing MBID) | M | L | LOW | MBID canonical + Spotify ID fallback; Edition selector (T066) merges editions; "Report wrong album" surface (T167). MusicBrainz reconciliation worker (T065) for fresh releases. |
| **R-012** | Operational | Self-hosted PostHog goes flaky | L | M | LOW | Documented fallback to PostHog Cloud (~$0/mo at our scale); monitoring on the PostHog container itself; if it crashes >2× in a week, migrate to Cloud. |
| **R-013** | Performance | Single-region backend latency for EU/APAC users | M | L | LOW | Multi-region post-M3 (Plan §17.2); SSR fall-back via Vercel edge functions for the worst affected pages; not a launch blocker. |

### Rollout strategy

Per risk profile: **2 CRITICAL + 4 HIGH = feature flag + staged rollout (10% → 50% → 100%) recommended**.

However, auxd at M0 is essentially launching a brand-new product, not gradually exposing a feature inside an existing app. So "rollout staging" here means:

- **L-3 weeks: closed beta** (~30 critic seeds + ~50 friends-of-founder; Development Mode quota)
- **L-1 week: invite-only soft launch** (waitlist-controlled; ramp to ~250 users)
- **L 0: public launch** (Extended Quota Mode approved; public signups open)
- **L+1 week: monitor + iterate** based on M0+1w signals (DAU, activation, churn)
- **M1 (D30) checkpoint:** retention cohort returns; first qualitative interviews
- **M3 checkpoint:** WAL gate; pivot meeting if <50% of target

Per [plan §18 Phase M-2 / M-1 / M0](./plan.md), this matches the planned roadmap. Pre-impl review confirms it.

### Risk mitigations required before coding starts

These are MUSTs before T011 (first feature code task) begins:

1. **A-009 — Add T117a** (synchronous critic-seed card ordering for onboarding). Without this, T117 + T118 cannot ship correctly.
2. **D-001 + D-002 — Spec the onboarding edge cases** (deleted-account email collision; Spotify-on-existing-email auto-link decision). 5–15 min spec updates.
3. **A-001 + A-002 — Lock the feed weighting + tiebreak math** in plan §10.2. Needed before T106.
4. **A-003 — Lock coalescer cross-type semantics** in plan §8.2. Needed before T133 (which depends on T131 dispatcher).
5. **A-004 — Lock rate-limiter fail-mode** in plan §1.1. Needed before T020.

All other findings are tracked + addressable during implementation (D-003, D-004, D-005, D-006, A-005, A-006, A-007, A-008, A-010).

---

## Conditions for Approval

Before Phase 6 (Implementation) begins, address these 5 inline updates:

| # | Action | Where | Owner | Effort |
|---|---|---|---|---|
| C-1 | Add T117a (synchronous critic-seed card ordering) | tasks.md cluster §11 | Phase 5B revision | 10 min |
| C-2 | Spec onboarding edge cases (D-001 + D-002) | product-spec/decision-log.md + user-stories.md S-A1 + S-A2 | Phase 3 revision (light) | 20 min |
| C-3 | Lock feed weighting math (A-001 + A-002) | plan.md §10.2 | Phase 5 inline edit | 15 min |
| C-4 | Lock coalescer cross-type semantics (A-003) | plan.md §8.2 + notification-taxonomy.md | Phase 5 inline edit | 10 min |
| C-5 | Lock rate-limiter fail-mode (A-004) | plan.md §1.1 + tasks.md T020 description | Phase 5 inline edit | 10 min |

**Total effort: ~65 minutes.** All can be done by the orchestrator inline without leaving Phase 5C.

Or, accept the conditions and proceed — they'll surface in Phase 6 implementation (the implementer will need to make these decisions inline). This is a defensible choice for a single-founder project but means the inline-clarification time happens later under time pressure rather than now in a clear-head review state.

---

## Pre-Implementation Checklist

- [ ] All CRITICAL design findings resolved → **0 critical findings (✅ none to resolve)**
- [ ] All CRITICAL architecture findings resolved → **0 critical findings (✅ none to resolve)**
- [ ] All Critical-severity risks have documented mitigations → **R-001 + R-002 mitigated (per Phase 0 interview script + seeding-strategy playbook) ✅**
- [ ] Rollout strategy agreed upon → **Closed beta → soft launch → public launch (per plan §18) ✅**
- [ ] tasks.md updated with any new tasks from this review → **PENDING** (C-1 adds T117a)
- [ ] WARNING-level design + architecture findings addressed or accepted → **PENDING** (C-2 through C-5)

---

## Confidence statement

The artifact stack (spec.md, plan.md, tasks.md, migrations/) is **internally consistent, well-reasoned, and implementable**. The wedge thesis is sharp. The decisions are defensible. The risks are documented and have concrete (not "monitor carefully") mitigations.

The findings in this review are **minor clarifications, not structural issues**. The product is ready for Phase 6 once the 5 conditions above are accepted (either by inline updates or by accepting them as deferred-to-implementation decisions).

The biggest residual risk is **R-001 (H1 user-research validation)** — but this is a pre-existing risk acknowledged from Phase 0, and no amount of pre-impl review can resolve it. Only live signal will. The MVP is correctly designed to validate H1 within 6 months of public launch.
