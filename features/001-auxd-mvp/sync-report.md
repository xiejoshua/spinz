# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #2 — 2026-05-22**
> Phase: 6 (Implementation, in progress) — 4/183 tasks complete
> Drift budget: cosmetic ≤ 20, structural = 0

---

## Run #2 (2026-05-22)

> Layers checked: 6/7 | Skipped: Layer 6 (spec ↔ code) — feature only 4/183 implemented; Layer 6 premature.
> Layer 5 runs for the **first time** (code now exists post-§0 scaffold).

### Summary

| Severity | Count | Net of recurring | New this run |
|----------|-------|-----------------:|-------------:|
| ❌ CRITICAL | 0 | — | — |
| ⚠️ WARNING | 3 | 2 new + 1 recurring | L7-011, L7-012 + L2-007 (recurring, severity escalated) |
| ℹ️ INFO | 22 | 10 recurring + 12 new | L1-002, L1-003, L2-010, L2-011, L2-012, L2-013, L3-011, L3-012, L7-013 + (L7-009 RESOLVED) |
| ✅ CLEAN | Layer 5 (0 findings) | — | — |

**Verdict: DRIFT DETECTED (NOT CRITICAL)** — 0 individual finding is CRITICAL-severity; the strict `structural: 0` budget would still gate, but the picture is mostly recurring-advisory-INFO + a small set of new fixable items.

### Run #1 backlog disposition — VERIFIED

All 10 active items from Run #1's `sync-fix-list.md` are landed and verified by independent re-scan:

| ID | What it was | Status in Run #2 |
|----|-------------|------------------|
| L3-001 | Endpoint rate-limit in plan §4.5 | ✅ landed @ plan §4.5 (token-bucket dep + per-endpoint qpm table + FAIL OPEN) |
| L3-002 | Follow-request queue (US-G2 infra) | ✅ landed @ plan §3.1 + §6 social.request_follow/respond_to_follow_request |
| L3-003 | review_edit_history (FR-030 audit) | ✅ landed @ plan §3.1 collection + §6 reviews module |
| L3-004 | axe-core CI gate | ✅ landed @ plan §16.4 + new §16.5 audit cadence |
| L3-006 | Report-missing-album path | ✅ landed @ plan §11.2.1 + §13.1 enum extension |
| L3-007 | Settings → Integrations route + services | ✅ landed @ plan §1.2 + new §4.6 + §6 auth |
| L4-001 | OpenTelemetry task | ✅ T015a present (deps T011/T015, refs Constitution P5) |
| L4-002 | Nightly mongodump task | ✅ T010a present (deps T005/T007, refs §17.4) |
| L4-003 | T135 PostMark failure-mode wiring | ✅ T135 amended (retry + failed_emails + Sentry tag) |
| L4-004 | T013 Redis fail-mode policy | ✅ T013 amended (cache FAIL OPEN + arq FAIL CLOSED 503) |

Plus the 10 inline cleanups applied in Run #1 (L2-001 S-B6 body, L2-002 hearted label, L2-003 count 32→30, L2-008 Lists residual, L4-006 T117a Refs A-005, L4-007 matrix total, L4-008 §1 label, L7-001 PS digest index, L7-002 research digest index, L7-003 interview-script link) all hold in Run #2.

Plus 2 deferred items: L3-005 (i18n) and L3-008 (Last.fm) — both correctly still absent (deferred as planned).

### Layer-by-layer

| Layer | Pair | Verdict | New findings |
|-------|------|---------|--------------|
| 1 | research ↔ product-spec | ⚠️ 3 INFO | L1-001 recurring, L1-002 NEW Apple Music threshold drift, **L1-003 NEW Spotify OAuth scopes narrower than research — potential S-A1 OAuth-signup blocker** |
| 2 | product-spec ↔ spec.md | ⚠️ 1 WARN + 8 INFO | L2-007 recurring (escalated WARN), L2-010/011/012/013 NEW |
| 3 | spec.md ↔ plan.md | ⚠️ 4 INFO | L3-009/010 recurring, L3-011 NEW typo, L3-012 NEW module-placement ambiguity |
| 4 | plan.md ↔ tasks.md | ⚠️ 1 INFO | L4-005 recurring only (satellite collections still missing from §3.1) |
| 5 | tasks.md ↔ code (NEW LAYER) | ✅ CLEAN | 0 findings; 4/4 completed tasks verified end-to-end |
| 6 | spec ↔ code | ⏭️ SKIPPED | Feature only 4/183 implemented |
| 7 | cross-link integrity | ⚠️ 2 WARN + 6 INFO | L7-011/012 NEW broken anchors, L7-013 NEW orphan (implementation-log.md), L7-009 RESOLVED |

### Notable new findings (worth acting on)

#### DRIFT-L1-003 — Spotify OAuth scopes narrower than research recommends

| Field | Value |
|-------|-------|
| Severity | INFO (but raises a real runtime concern) |
| Category | structural |
| Source | `research/tech-stack.md:61` recommends 8 scopes incl. `user-read-email`, `user-read-private`, `user-top-read` |
| Target | `product-spec/product-spec.md:132` (FR-002) + decision-log Q22 — lock essentials to 3 scopes only (`recently-played`, `currently-playing`, `library-read`) |
| Issue | S-A1 says Spotify-OAuth-shortcut signup auto-creates account using Spotify display name + email — but without `user-read-email`/`user-read-private`, Spotify OAuth cannot return those fields. S-A3 "top 5 by play time" prefill arguably needs `user-top-read`. |
| Resolution | Add `user-read-email` + `user-read-private` to essential scopes in FR-002 + Q22. Clarify whether S-A3 prefill uses `/me/player/recently-played` (already essential) or `/me/top/tracks` (needs `user-top-read`). |

#### DRIFT-L2-012 — "Heart" terminology survived two renames in user-journeys.md

| Field | Value |
|-------|-------|
| Severity | INFO (display copy stale) |
| Category | structural |
| Source | `product-spec/user-journeys.md:88, 103, 124` — Journey 2 ("heart row"), Journey 2 alt ("rating/heart/review"), Journey 3 ("❤️ heart action") |
| Issue | These were missed by R1 (Heart→Award rename) AND R3 (Award/Like split). Should now read: J2 "Aux row" (🏅) and J3 "👍 Like action" per FR-031 |
| Resolution | Replace "heart row" → "Aux row" (🏅) in J2; replace "❤️ heart action" → "👍 Like action" in J3 |

#### DRIFT-L7-011 — Broken anchor `#n-018` in user-stories.md

| Field | Value |
|-------|-------|
| Severity | WARNING |
| Category | structural |
| Source | `product-spec/user-stories.md:118` links `[notification-taxonomy.md](./notification-taxonomy.md#n-018)` |
| Issue | N-018 is a table row, not a heading. No anchor `#n-018` exists. |
| Resolution | Either drop the anchor, point to nearest heading, or add explicit `<a id="n-018"></a>` in the table row |

#### DRIFT-L7-012 — Short-form anchor doesn't match GitHub slug

| Field | Value |
|-------|-------|
| Severity | WARNING |
| Category | structural |
| Source | `spec.md:122` links `[sync-report.md](./sync-report.md#drift-l2-003)` |
| Issue | Heading is `### DRIFT-L2-003 — Story count claim…` which GitHub slugifies to `drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30`. Short `#drift-l2-003` matches nothing. Two other callers (product-spec/README.md:56, user-stories.md:363) correctly use long-form. |
| Resolution | Update to long-form slug for consistency |

#### Smaller new fixes
- **L2-007 (recurring, escalated)** — PS user-stories.md S-G3 AC says "20 types including auto-prompts and list-related events"; spec.md correctly says "18 active". Fix PS to "18 active types (N-019/N-020 reserved-gap after Lists removal)".
- **L2-010** — spec.md §7 "15 entities" prose vs grouped table; reconcile to "16 entities (incl. ReviewLike)".
- **L2-011** — data-model.md DM-3 references stale `aux_count`; was renamed to `likes_count` in R3.
- **L2-013** — product-spec/digest.md body still echoes pre-R3 counts (37 stories, 9 clusters incl. Lists, 17 notification types, 14 entities). Refresh to R3 state.
- **L3-011** — plan.md §6 typo: `actiion_report` (double-i) → `action_report`.
- **L3-012** — plan.md §4.6 ambiguity: `auth/` module vs new `integrations/` module — pick one and align §1.2 file tree.

### Recurring (still INFO/advisory)
- L1-001 (W1 activation narrowing), L2-004/005 (FR trace tags), L2-006 (cluster names), L2-009 (entity count), L3-009 (/critics route), L3-010 (handle suggestions), L4-005 (satellite collections in §3.1), L7-004/005/006/007/008 (5 phase-digest orphans by convention).

### What's CLEAN
- ✅ All 30/30 Must-Have stories mapped product-spec ↔ spec.md ↔ plan.md ↔ tasks.md
- ✅ All 4 pre-impl-review locks (C-1 T117a, C-3 feed weighting, C-4 coalescer cross-type, C-5 rate-limiter fail-open) present
- ✅ Lists deferral CRITICAL invariant holds (FR-021..025, S-I*, List/ListItem, N-019/N-020, Journey 4.5 — all absent)
- ✅ Aux rename consistent (display "Aux'd"; code "auxed"; 🏅 icon)
- ✅ Brand rename complete (no "spinz" or "Spinz" leakage in any tracked file)
- ✅ Layer 5: T001/T003/T004/T008 all verified end-to-end
- ✅ No broken file links (only 2 broken anchors and 1 wrong-form short anchor)
- ✅ All Run #1 backlog items landed + 10 inline cleanups all hold

### Run #2 verdict

**0 individual findings are CRITICAL.** The strict `structural: 0` budget rule would fire on the 22+ structural items, but ~10 of those are recurring INFOs already accepted as advisory in Run #1.

**Final disposition (2026-05-22): RESOLVED WITH OVERRIDE.**

#### ✅ Applied inline (10 items)
| ID | What changed | File |
|----|--------------|------|
| L2-007 | "20 types incl list-related" → "18 active types (N-019/N-020 reserved-gap)" | product-spec/user-stories.md S-G3 AC |
| L2-010 | spec.md §7 "15 entities" → "16 active entities (incl. ReviewLike)" — also 2nd location at "Must read first" | spec.md |
| L2-011 | DM-3 `aux_count` → `` `likes_count`, R3 rename ``; DM-5 "orphan aux counts" → "orphan ReviewLike rows or stale `likes_count` aggregates"; decision-log DM-5 same | product-spec/data-model.md + decision-log.md |
| L2-012 | Journey 2 "heart row" → "Aux row (🏅)"; Journey 2 alt "rating/heart/review" → "rating/Aux/review"; Journey 3 "❤️ heart action" → "👍 Like action (FR-031)" | product-spec/user-journeys.md |
| L2-013 | digest.md body refreshed to R3 state (30 stories, 8 active clusters, 18 notification types, 16 active entities — was 37/9/17/14) | product-spec/digest.md |
| L3-011 | typo `actiion_report` → `action_report` | plan.md §6 |
| L3-012 | module placement locked to `auth/` (matches §1.2 file tree); ambiguity removed | plan.md §4.6 |
| L7-011 | broken anchor `#n-018` → links to "Notification types (full enumeration)" + "Anti-spam guardrails" headings | product-spec/user-stories.md S-B6 |
| L7-012 | short-form anchor `#drift-l2-003` → full GitHub slug `#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30` | spec.md |
| **L1-003** | **Spotify OAuth scopes widened from 3 to 5: added `user-read-email` + `user-read-private`** (required by S-A1 OAuth-shortcut signup). Decision-log Q22 → v1.3. Propagated to product-spec.md FR-002, spec.md §0 decision #17 + FR-002 row, plan.md §4.4, tasks.md T002. | 5 files |

#### ⏭️ Skipped as advisory (13 items — recurring from Run #1)
L1-001 (W1 activation narrowing) · L2-004/005 (FR trace tags) · L2-006 (cluster name enrichment) · L2-009 (entity inventory ReviewLike — partially mooted by L2-010 reconciliation) · L3-009 (`/critics` route) · L3-010 (handle collision suggestion) · L4-005 (4 satellite collections still not in plan §3.1) · L7-004..008 (5 phase-digest orphans by convention) · L7-013 (implementation-log.md orphan, same convention class)

#### 🛂 Gate override
- **Reason:** Same logic as Run #1. 0 individual findings are CRITICAL-severity. Of the 25 structural items, 10 are recurring advisory already accepted, 10 are now resolved inline, and 5 are deferred. Phase 6 continues at 4/183 tasks complete.
- **Approved by:** Joshua Xie (founder, solo mode)
- **Approved at:** 2026-05-22

#### Run #2 to Run #3 outlook
After this commit lands, projected structural drift for next run: ~14 items (the 13 recurring advisories + L1-002 still unaddressed re: Apple Music threshold). All real structural concerns surfaced post-rename are now resolved.

Next sync-verify will likely run between Phase 6B (code review) and Phase 7 (full verify) — Layer 6 (spec ↔ code) becomes meaningful once feature code lands.

---

## Run #1 (2026-05-21) — Historical record

> Layers checked: 5/7 | Skipped: Layer 5 (tasks ↔ code), Layer 6 (spec ↔ code) — no code yet
> Drift budget: cosmetic ≤ 20, structural = 0
> Run #1 (first sync-verify on this feature)
>
> **Final disposition: RESOLVED WITH OVERRIDE** — 10 inline cleanups applied, 10 plan-level items backlogged to [sync-fix-list.md](./sync-fix-list.md), 2 deferred, 14 INFOs skipped as advisory, gate overridden. Phase 6 cleared to start.

## Summary

| Severity | Count | Structural | Cosmetic |
|----------|-------|-----------:|---------:|
| ❌ CRITICAL | 0 | 0 | 0 |
| ⚠️ WARNING | 19 | 18 | 1 |
| ℹ️ INFO | 14 | 9 | 5 |
| ✅ CLEAN (layers w/ no critical drift) | 5 of 5 |

**Verdict: CRITICAL DRIFT (per budget rule)**
- Structural drift budget = 0; observed structural items = 27 → triggers gate
- Cosmetic drift budget = 20; observed cosmetic items = 6 → within budget
- **Important nuance:** No individual finding is CRITICAL-severity. The CRITICAL verdict is driven entirely by the strict `structural: 0` budget. Most findings are surgical cleanup, plan additions, or backlog work that would normally be addressed during Phase 6. The gate exists to force a deliberate disposition decision before code starts.

## Layer Results

| Layer | Pair | Verdict | Warnings | Info |
|-------|------|---------|---------:|-----:|
| 1 | research ↔ product-spec | ⚠️ 1 item | 0 | 1 |
| 2 | product-spec ↔ spec.md | ⚠️ 4 / ℹ️ 5 | 4 | 5 |
| 3 | spec.md ↔ plan.md | ⚠️ 8 / ℹ️ 2 | 8 | 2 |
| 4 | plan.md ↔ tasks.md | ⚠️ 4 / ℹ️ 5 | 4 | 5 |
| 5 | tasks.md ↔ code | ⏭️ skipped (no code) | — | — |
| 6 | spec.md ↔ code | ⏭️ skipped (no code) | — | — |
| 7 | cross-link integrity | ⚠️ 3 / ℹ️ 7 | 3 | 7 |

---

## Layer 1 — research ↔ product-spec

**Status:** 1 INFO. 15+ verified alignments — research findings consistently reflected in product-spec.

### DRIFT-L1-001 — W1 activation definition narrowed

| Field | Value |
|-------|-------|
| Direction | Forward (research → product-spec) |
| Severity | INFO |
| Category | structural |
| Source | `research/metrics-roi.md:159` — KPI table |
| Source evidence | "W1 activation rate \| % of signups who, within 7 days, (a) connect Spotify, (b) follow ≥3 users, (c) log ≥3 albums \| 30% \| 35%" |
| Target | `product-spec/success-metrics.md:18`; `product-spec/product-spec.md` §7 |
| Expected | Full 3-condition definition: Spotify-connect + ≥3 follows + ≥3 logs |
| Actual | Definition narrowed to "log ≥3 albums" only; targets (30%/35%) unchanged — looser definition arithmetically easier to hit |
| Resolution | Either (a) restore the 3-condition definition in `success-metrics.md`, or (b) add a decision-log entry explaining the narrowing (Spotify-connect now skippable per Q12; follow-gate captured via "follow ≥1 critic seed during onboarding" leading indicator) |

---

## Layer 2 — product-spec ↔ spec.md

**Status:** 0 CRITICAL, 4 WARNING, 5 INFO. R3 Lists reversion correctly applied. Aux/Like split correctly bridged.

### DRIFT-L2-001 — US-B6 referenced but no story body

| Field | Value |
|-------|-------|
| Direction | Backward (spec.md → product-spec) |
| Severity | WARNING |
| Category | structural |
| Source | `spec.md:141` US-B6 |
| Target | `product-spec/user-stories.md` Cluster B (no `### S-B6:` body) |
| Expected | Full S-B6 story body with G/W/T ACs aligned to Journey 1.5 + FR-026 + N-018 |
| Actual | S-B6 only appears in coverage table (line 336) and history line (349); no body |
| Resolution | Add `### S-B6: Just-finished auto-prompt` to user-stories.md Cluster B with G/W/T ACs derivable from Journey 1.5 + FR-026 + N-018 |

### DRIFT-L2-002 — Stale "hearted" filter label in spec.md

| Field | Value |
|-------|-------|
| Direction | Forward (R3 cleanup miss) |
| Severity | WARNING |
| Category | structural |
| Source | `spec.md:298` |
| Source evidence | `\| Frontend \| `app/@[handle]` \| Profile; diary; filters (Aux'd, hearted, public-only) \|` |
| Target | R3 Decision #9 (Aux/Like split — `spec.md:27`) |
| Expected | `filters (Aux'd, public-only)` (no DiaryEntry-level Likes filter; Likes are on Reviews) |
| Actual | "hearted" relic from pre-R1 naming still present |
| Resolution | Edit `spec.md:298` — drop "hearted" from filter list |

### DRIFT-L2-003 — Story count claim (32) vs enumerated bodies (30)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | `spec.md:122,124,359`; `product-spec/user-stories.md:348`; `product-spec/digest.md:12` |
| Source evidence | All four locations claim "32 Must-Have stories" |
| Target | Enumerated US-* bodies in spec.md §4 |
| Expected | 32 itemized US-* bullets |
| Actual | 30 unique US-* IDs enumerated (A1..A5, B1..B6, C1..C4, D1..D3, E1..E5, F1..F2, G1..G5) |
| Resolution | Either (a) reconcile the count to 30 across all 4 files, or (b) identify the 2 missing stories from prior versions and add them. Recommended: (a) |

### DRIFT-L2-008 — Stale "Lists" reference in product-spec S-A2 + Journey 1

| Field | Value |
|-------|-------|
| Direction | Forward (R3 cleanup miss in product-spec) |
| Severity | WARNING |
| Category | structural |
| Source | `product-spec/user-stories.md:30` (S-A2 AC); `product-spec/user-journeys.md:35` (Journey 1 alt path) |
| Source evidence | "manual log, **Lists**, reviews, backlog, auxes all work" |
| Target | R3 Lists deferral |
| Expected | No mention of "Lists" as MVP feature |
| Actual | "Lists" remains in two PS locations; spec.md correctly omits |
| Resolution | Remove "Lists, " from both PS locations. spec.md needs no change |

### DRIFT-L2-004 — FR-003 traceability label (INFO)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | structural |
| Source | `spec.md:197` FR-003 traces to US-A3 |
| Expected | US-A2 (Spotify-connect+import) or "US-A2, US-A3" |
| Actual | Only US-A3 (rate the imported listens) |
| Resolution | Change FR-003 trace from "US-A3" to "US-A2" |

### DRIFT-L2-005 — FR-027 traceability label (INFO)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | structural |
| Source | `spec.md:217` FR-027 traces to "US-A2, US-G2" |
| Expected | US-A2 (back-fill diary part of S-A2 AC); US-G2 is privacy defaults, unrelated |
| Actual | US-G2 incorrectly tagged |
| Resolution | Change FR-027 trace from "US-A2, US-G2" to "US-A2" |

### DRIFT-L2-006 — Cluster name enrichment (INFO)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | structural |
| Source | spec.md cluster labels enriched ("Cluster B — Logging, rating, Aux, auto-prompt") vs PS labels |
| Resolution | Accept as deliberate enrichment OR normalize. No functional impact |

### DRIFT-L2-007 — PS S-G3 AC count needs update (INFO, PS is stale)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | structural |
| Source | `product-spec/user-stories.md:269` S-G3 AC |
| Source evidence | "20 types including auto-prompts and list-related events" |
| Expected | "18 active notification types including auto-prompts" (after R3 removed N-019/N-020) |
| Resolution | Update PS S-G3 AC; spec.md is already correct |

### DRIFT-L2-009 — Entity inventory missing ReviewLike; count 14/15/16 (INFO)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | structural |
| Source | `product-spec/data-model.md:10–30` inventory table |
| Expected | ReviewLike row in inventory; consistent count claim |
| Actual | Inventory shows 14 active (List/ListItem struck through); ReviewLike defined in body §146 but not in inventory; spec.md §7 + §13 claim "15 entities" |
| Resolution | Add ReviewLike to inventory; reconcile count to 16 across data-model.md, spec.md §7+§13, digest.md |

---

## Layer 3 — spec.md ↔ plan.md

**Status:** 0 CRITICAL, 8 WARNING, 2 INFO. Pre-impl-review C-3/C-4/C-5 locks verified present. 14/14 Must-Have stories have plan homes — but several spec.md NFRs and FRs lack explicit plan strategy.

### DRIFT-L3-001 — Endpoint rate-limiting missing from plan

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §6 NFR Security |
| Source evidence | "rate limiting on log/follow/review/like endpoints" |
| Target | plan.md (only notification-dispatcher rate-limiting in §8.2) |
| Expected | Plan describes HTTP endpoint rate-limiting (per-IP / per-user) on POST /diary, /follow, /reviews, /reviews/{id}/like |
| Actual | §1.1.1 mentions Redis rate-limit but only in notification context; no endpoint middleware plan |
| Resolution | Add §4.5 (or §6.x) describing `lib/rate_limit.endpoint(...)` Redis token-bucket middleware; fail-open same policy as §1.1.1; add to fail-mode table |

### DRIFT-L3-002 — Follow-request queue missing (Must-Have US-G2 infrastructure)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §4 US-G2 |
| Source evidence | "private-profile toggle creates pending follow-requests queue; existing followers stay on visibility downgrade" |
| Target | plan.md §3 / §6 social — missing |
| Expected | `follow_requests` collection or `Follow.state` enum (pending/accepted/declined); `request_follow` / `respond_to_follow_request` services in §6 social |
| Actual | §3.1 `follows` treats follows as binary; §6 social has no request lifecycle |
| Resolution | Add follow-request model + services. Note: spec.md US-H3 (Friend-request UI) is Should-Have, but the **queue infrastructure** is Must-Have via US-G2 |

### DRIFT-L3-003 — Review edit history collection missing (FR-030 90d audit)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §4 US-C3 + §5 FR-030 |
| Source evidence | "Latest version shown publicly with 'edited' badge + hover timestamp; 90-day internal audit log preserved" |
| Target | plan.md (partial — `edited_at` exists but no audit storage) |
| Expected | `review_edit_history` collection with TTL 90d; history-row write on every `edit_review` |
| Actual | No edit-history collection in §3.1; `edit_review` service has no description of history capture |
| Resolution | Add `review_edit_history` to §3.1: `(review_id, version, body_at_time, edited_at, edited_by)`, TTL 90d. Update §6 `edit_review` to write history row |

### DRIFT-L3-004 — Accessibility CI gate missing (axe-core)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §6 NFR Accessibility + §6.1 NFR Measurement Contract |
| Source evidence | "axe-core automated audit + manual keyboard nav test \| Per-screen audit on every release \| 0 violations" |
| Target | plan.md §15 / §16 — missing |
| Expected | §16.4 CI workflow includes axe-core run with 0-violations gate |
| Actual | §2 mentions "shadcn/ui...accessibility built-in" but no automated audit; CI workflow lacks any a11y lint |
| Resolution | Add `@axe-core/playwright` to E2E suite in §16.4; add per-screen audit checklist to §16.2 or new §16.5 |

### DRIFT-L3-005 — i18n key extraction strategy missing

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §6 NFR i18n/l10n |
| Source evidence | "English-only at MVP; copy strings extracted to keys" |
| Target | plan.md — missing |
| Expected | §7.6 (or similar) describing i18n library (next-intl/react-i18next) and `src/locales/en.json` extraction process |
| Actual | Zero mentions of i18n in plan.md |
| Resolution | Add §7.6 "Copy / i18n strategy". Possibly intentional (deferred to `speckit-product-forge-i18n-harvest` skill, currently `not_applicable` in status) — confirm before fixing |

### DRIFT-L3-006 — "Report missing album" path absent (FR-005, US-F2)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §4 US-F2 + §5 FR-005 |
| Source evidence | "'Report missing album' link on empty result" |
| Target | plan.md §11 / §13 — missing |
| Expected | `POST /api/search/report-missing` endpoint, queue, founder review path |
| Actual | §11 describes Atlas+Spotify merge but no empty-state report; §13 `reports.target_type` enum lacks `missing_album` |
| Resolution | Extend `reports.target_type` enum in §13.1 with `missing_album` (or add `album_requests` collection); reference from §11 |

### DRIFT-L3-007 — Settings → Integrations UI + services partial (FR-027)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §5 FR-027 |
| Source evidence | "Settings → Integrations: Spotify status, back-fill diary trigger, immutability on disconnect" |
| Target | plan.md §6 / §7 — partial |
| Expected | `app/(app)/settings/integrations/` route in §7.1; `disconnect_spotify` / `trigger_diary_backfill` services in §6 auth |
| Actual | §1.2 tree shows `settings/` but no `integrations` sub-route; §6 auth has only `connect_spotify`; disconnect-immutability appears only in §16.2 test mapping |
| Resolution | Add `settings/integrations/` route, `disconnect_spotify` + `trigger_diary_backfill` services, and explicit note re: diary-intact-on-disconnect |

### DRIFT-L3-008 — Last.fm scaffolding absent (FR-017 Should-Have)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | spec.md §5 FR-017 |
| Source evidence | "Last.fm history import as Spotify alternative" |
| Target | plan.md §5 (provider abstraction) — partial (enum value exists, no class plan) |
| Expected | §5.4 future-proofing note: Last.fm implements `MusicProvider` interface; enum placeholder ready |
| Actual | `LASTFM_IMPORT` exists as `DiaryEntrySource` enum but no provider plan |
| Resolution | Add one-line §5.4 note. Lower priority — FR-017 is Should-Have |

### DRIFT-L3-009 — `/critics` route added in plan, not in spec (INFO, backward)

| Field | Value |
|-------|-------|
| Direction | Backward |
| Severity | INFO |
| Category | structural |
| Source | plan.md §11.3 |
| Source evidence | "Critic-seed directory at `/critics`" |
| Target | spec.md — no `/critics` page in US-A4 / FR-015 / wireframes |
| Resolution | Cross-reference `seeding-strategy.md` from spec.md OR drop the `/critics` route from §11.3. Low impact |

### DRIFT-L3-010 — Handle collision suggestion algorithm incomplete (INFO)

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | INFO |
| Category | structural |
| Source | spec.md §4 US-A1 |
| Source evidence | "auto-handle suggestions on collision" (plural) |
| Target | plan.md §4.1 Flow A — "first-available slug" (singular) |
| Resolution | Add to §4.1: "On collision, generate 3 candidate handles (e.g., `casey`, `casey7`, `casey_listens`) via `signup_check_handle`" |

### Pre-impl-review conditional locks (C-3, C-4, C-5) — VERIFIED PRESENT

- **§1.1.1 rate-limiter fail-open** (C-5): plan.md:86-101, table row "Redis (rate-limit + coalescer) — FAIL OPEN"; cross-ref from §8.2 line 547
- **§8.2 notification coalescer cross-type** (C-4): plan.md:542-548, "INTENTIONALLY cross-type"; "Resolves A-003"
- **§10.2 feed weighting math + tiebreak** (C-3): plan.md:630-658; resolves A-001 (`top_5_interacted_users`) + A-002 (stable tiebreak `score → logged_at desc → entry_id`)

---

## Layer 4 — plan.md ↔ tasks.md

**Status:** 0 CRITICAL, 4 WARNING, 5 INFO. T117a present (Phase 5C C-1). T020 fail-open locked (C-5). 181/181 tasks have `Refs:` line — zero orphan tasks. Lists deferral preserved.

### DRIFT-L4-001 — OpenTelemetry task missing

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | plan.md §15.4 |
| Source evidence | "OTel SDK in backend; instruments FastAPI, httpx, Beanie automatically. Spans export to Fly logs" |
| Target | tasks.md — `grep "OpenTelemetry\|OTel"` returns 0 hits |
| Expected | Task to install OTel SDK + FastAPI/httpx/Beanie auto-instrumentors |
| Actual | No task |
| Resolution | Add T015a (or T020a) — "OpenTelemetry instrumentation: install otel SDK + FastAPI/httpx/Beanie auto-instrumentors; configure span exporter to Fly logs." Size XS. Refs: Constitution P5, plan §15.4 |

### DRIFT-L4-002 — Nightly mongodump backup task missing

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | plan.md §17.4 |
| Source evidence | "at M0 manual nightly mongodump → S3 ($1/mo)" |
| Target | tasks.md — zero hits for `backup\|mongodump\|S3` |
| Expected | M0 backup task |
| Actual | No task |
| Resolution | Add §0 or §18 task — "Nightly mongodump backup to S3 (M0 manual backups)." Size XS-S. Refs: plan §17.4, NFR availability |

### DRIFT-L4-003 — T135 PostMark failure-mode not wired

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | plan.md §1.1.1 PostMark row |
| Source evidence | "Retry with exponential backoff (3 attempts); on final failure log to `failed_emails`; Sentry alert tag `email.send_failed`" |
| Target | T135 — wraps Postmark client but doesn't mention failure mode |
| Expected | T135 description includes retry + `failed_emails` write + Sentry tag |
| Actual | T135: "Postmark client wrapper; per-type HTML templates; one-click unsubscribe..." — no failure-mode wiring |
| Resolution | Amend T135 to include retry + `failed_emails` + Sentry tag. Add `failed_emails` to T026 (Notifications models) or sibling |

### DRIFT-L4-004 — Redis cache + arq fail-mode policy not encoded in tasks

| Field | Value |
|-------|-------|
| Direction | Forward |
| Severity | WARNING |
| Category | structural |
| Source | plan.md §1.1.1 |
| Source evidence | "Redis (cache) | FAIL OPEN | Sentry `cache.redis_down`"; "Redis (arq job queue) | FAIL CLOSED | API returns 503 | Sentry `jobs.redis_down`" |
| Target | tasks.md — only T020 (rate-limiter) encodes fail-mode |
| Expected | Tasks for T013, T149, T153 should wire differentiated fail-mode semantics |
| Actual | Only rate-limiter explicit |
| Resolution | Expand T013 or add small task — "Wire Redis fail-mode: cache FAIL OPEN with `cache.redis_down`; arq-enqueue endpoints FAIL CLOSED 503 with `jobs.redis_down`. Apply to GDPR export and other job-enqueue surfaces" |

### DRIFT-L4-005 — Ancillary collections not in §3.1 inventory (INFO/cosmetic)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | cosmetic |
| Source | plan.md §3.1 lists 15 named collections |
| Target | `handle_redirects`, `review_edits`, `gdpr_audit_log`, `failed_emails`, `feed_buckets` exist inline in §4.3 / §14.3 / T086 etc. but not in §3.1 |
| Resolution | Optional — add note to §3.1 listing satellite collections OR move them into §3.1 explicitly. No functional impact |

### DRIFT-L4-006 — T117a Refs cites A-009; canonical is A-005 (INFO, upstream PIR inconsistency)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | cosmetic |
| Source | tasks.md:1027 T117a Refs: "US-A4; FR-015; A-009 from pre-impl-review" |
| Target | pre-impl-review.md:141 — architecture finding A-005 is the canonical ID; line 189 mitigation listing says "A-009" |
| Resolution | Change T117a Refs to "A-005 from pre-impl-review". Also fix upstream pre-impl-review.md internal inconsistency (line 141 vs 189) |

### DRIFT-L4-007 — Coverage matrix says "180 tasks" (INFO, cosmetic)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | cosmetic |
| Source | tasks.md:44 "**Total: 180 tasks**" |
| Actual | T117a added in Phase 5C → 181 |
| Resolution | Update to "**Total: 181 tasks (180 + T117a added Phase 5C)**" |

### DRIFT-L4-008 — Coverage matrix label mismatch §1 (INFO, cosmetic)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | cosmetic |
| Source | tasks.md:25 matrix row "§1 Infra + scaffolding" vs cluster header "§1 Backend foundation + libs" |
| Resolution | Align matrix label and cluster header |

### DRIFT-L4-009 — No admin UI marker in tasks (INFO, cosmetic)

| Field | Value |
|-------|-------|
| Severity | INFO |
| Category | cosmetic |
| Source | plan §13.3 "Out of scope at MVP — flagged users surface in Compass" |
| Resolution | No change required; T158 already uses deferred-tagging pattern. Cosmetic note only |

---

## Layer 7 — cross-link integrity

**Status:** 0 CRITICAL, 3 WARNING, 7 INFO. All 157 file-target links resolve. All anchors resolve. Convention question: phase-digest `*/digest.md` files are not indexed.

### DRIFT-L7-001 — product-spec/README.md doesn't index digest.md

| Severity | Category | Source | Resolution |
|----------|----------|--------|------------|
| WARNING | structural | `product-spec/README.md:14-25` document map | Add `digest.md` row OR document the digest-exclusion convention |

### DRIFT-L7-002 — research/README.md doesn't index digest.md

| Severity | Category | Source | Resolution |
|----------|----------|--------|------------|
| WARNING | structural | `research/README.md:30-36` table | Add `digest.md` row OR document convention |

### DRIFT-L7-010 — False positive in ux-patterns.md (cosmetic, no action)

| Severity | Category | Source | Resolution |
|----------|----------|--------|------------|
| WARNING | cosmetic | `research/ux-patterns.md:117` — `[link](url)` inside backticks | No action — false positive. If strict link-checker added to CI, exclude in-code matches |

### Orphan files (INFO — convention question)

| Target | Note |
|--------|------|
| `problem-discovery/interview-script.md` | Referenced as plain text 6× but never as `[markdown](link)`. Best candidate to fix: convert mentions in `spec.md:473` and `product-spec/product-spec.md:216` to links |
| `problem-discovery/digest.md` | Phase-digest convention question |
| `product-spec/digest.md` | Phase-digest convention question |
| `research/digest.md` | Phase-digest convention question |
| `plan/digest.md` | Phase-digest convention question |
| `tasks/digest.md` | Phase-digest convention question |
| `pre-impl-review/digest.md` | Phase-digest convention question |

---

## All Drift Items — Approval Tracker

| ID | Layer | Sev | Cat | Title | Decision |
|----|-------|-----|-----|-------|----------|
| L1-001 | 1 | INFO | struct | W1 activation definition narrowed | ⬜ |
| L2-001 | 2 | WARN | struct | US-B6 story body missing in PS | ⬜ |
| L2-002 | 2 | WARN | struct | Stale "hearted" filter in spec.md | ⬜ |
| L2-003 | 2 | WARN | struct | Story count 32 claim vs 30 enumerated | ⬜ |
| L2-004 | 2 | INFO | struct | FR-003 trace tag | ⬜ |
| L2-005 | 2 | INFO | struct | FR-027 trace tag | ⬜ |
| L2-006 | 2 | INFO | struct | Cluster name enrichment | ⬜ |
| L2-007 | 2 | INFO | struct | PS S-G3 notification count stale | ⬜ |
| L2-008 | 2 | WARN | struct | "Lists" residual in PS S-A2 + Journey 1 | ⬜ |
| L2-009 | 2 | INFO | struct | ReviewLike not in inventory; entity count | ⬜ |
| L3-001 | 3 | WARN | struct | Endpoint rate-limiting missing | ⬜ |
| L3-002 | 3 | WARN | struct | Follow-request queue missing | ⬜ |
| L3-003 | 3 | WARN | struct | Review edit history collection | ⬜ |
| L3-004 | 3 | WARN | struct | Accessibility CI gate (axe-core) | ⬜ |
| L3-005 | 3 | WARN | struct | i18n key extraction | ⬜ |
| L3-006 | 3 | WARN | struct | Report missing album path | ⬜ |
| L3-007 | 3 | WARN | struct | Settings → Integrations partial | ⬜ |
| L3-008 | 3 | WARN | struct | Last.fm provider scaffolding | ⬜ |
| L3-009 | 3 | INFO | struct | /critics route in plan, not spec | ⬜ |
| L3-010 | 3 | INFO | struct | Handle collision suggestion | ⬜ |
| L4-001 | 4 | WARN | struct | OpenTelemetry task missing | ⬜ |
| L4-002 | 4 | WARN | struct | Nightly mongodump backup task | ⬜ |
| L4-003 | 4 | WARN | struct | T135 PostMark failure-mode | ⬜ |
| L4-004 | 4 | WARN | struct | Redis cache + arq fail-mode | ⬜ |
| L4-005 | 4 | INFO | cosmetic | §3.1 inventory satellite collections | ⬜ |
| L4-006 | 4 | INFO | cosmetic | T117a Refs A-009 vs A-005 | ⬜ |
| L4-007 | 4 | INFO | cosmetic | Coverage matrix total 180 → 181 | ⬜ |
| L4-008 | 4 | INFO | cosmetic | §1 cluster label mismatch | ⬜ |
| L4-009 | 4 | INFO | cosmetic | Admin UI marker | ⬜ |
| L7-001 | 7 | WARN | struct | product-spec/README doesn't index digest | ⬜ |
| L7-002 | 7 | WARN | struct | research/README doesn't index digest | ⬜ |
| L7-003 | 7 | INFO | struct | interview-script.md orphan | ⬜ |
| L7-004..009 | 7 | INFO | struct | 6 digest.md orphans | ⬜ |
| L7-010 | 7 | WARN | cosmetic | False positive in ux-patterns.md | ⬜ N/A |

## Recommended Disposition

The verdict is CRITICAL DRIFT only because `structural: 0` is a hard zero budget. None of the findings are runtime-CRITICAL. Recommended split:

1. **Apply now (10 items)** — quick PS / spec.md cleanup that should land before Phase 6 code starts:
   - L2-001, L2-002, L2-003, L2-008 (story body, "hearted" filter, count, Lists residuals)
   - L4-006, L4-007, L4-008 (T117a Refs, matrix total, label)
   - L7-001, L7-002, L7-003 (README digest indexes; interview-script link)

2. **Apply during Phase 6 (8 items, plan-level additions)** — small plan additions that become Phase 6 implementation work:
   - L3-001, L3-002, L3-003, L3-004, L3-006, L3-007, L4-001, L4-002, L4-003, L4-004

3. **Defer to v2 / Should-Have grooming (3 items)** — explicit deferrals:
   - L3-008 (Last.fm — already Should-Have)
   - L3-005 (i18n — `i18n_harvest: not_applicable` in status)
   - L7-004..009 (digest orphan convention)

4. **Optional polish (remaining items)** — INFO items that don't block work

## Sync History

| Run | Date | Layers | CRITICAL items | WARNING items | INFO items | Initial verdict | Final disposition |
|-----|------|--------|---------------:|--------------:|-----------:|------------------|-------------------|
| #1 | 2026-05-21 | 5/7 | 0 | 19 | 14 | CRITICAL DRIFT (budget rule) | RESOLVED WITH OVERRIDE — 10 applied / 10 backlogged / 2 deferred / 14 INFO skipped |
| #2 | 2026-05-22 | 6/7 | 0 | 3 | 22 | DRIFT DETECTED | RESOLVED WITH OVERRIDE — 10 applied (incl. L1-003 OAuth scopes widening) / 13 advisory recurring / gate overridden |

---

## Disposition Detail — Run #1

### ✅ Inline cleanups applied (10 items)

| ID | What changed | File |
|----|--------------|------|
| L2-001 | Added S-B6 story body with full G/W/T ACs derived from Journey 1.5 + FR-026 + N-018 | `product-spec/user-stories.md` (Cluster B, between S-B5 and Cluster C) |
| L2-002 | Dropped stale "hearted" from filter list | `spec.md:298` |
| L2-003 | Reconciled story count from 32 → 30 (4 locations) | `spec.md:122,124,359`, `product-spec/user-stories.md:363`, `product-spec/README.md:55`, `product-spec/digest.md` |
| L2-008 | Removed "Lists" residual from S-A2 AC + Journey 1 alt path | `product-spec/user-stories.md:30`, `product-spec/user-journeys.md:35` |
| L4-006 | T117a Refs corrected: A-009 → A-005 (canonical) | `tasks.md` T117a |
| L4-007 | Coverage matrix total: 180 → 181 (T117a included) | `tasks.md:44` |
| L4-008 | Coverage matrix label "§1 Infra + scaffolding" → "§1 Backend foundation + libs" | `tasks.md:25` |
| L7-001 | Added digest.md row to document map | `product-spec/README.md:26` |
| L7-002 | Added digest.md row to research documents table | `research/README.md:37` |
| L7-003 | Made interview-script.md a real markdown link in 2 risk-table cells | `spec.md:473`, `product-spec/product-spec.md:216` |

### 📋 Backlogged to Phase 6 (10 items)

See [sync-fix-list.md](./sync-fix-list.md) for full descriptions and tracking checkboxes:

- L3-001 endpoint rate-limiting (security NFR)
- L3-002 follow-request queue (US-G2 Must-Have infra)
- L3-003 review edit history collection (FR-030 90d audit)
- L3-004 axe-core a11y CI gate
- L3-006 report-missing-album path (FR-005)
- L3-007 Settings → Integrations route + services (FR-027)
- L4-001 OpenTelemetry instrumentation task
- L4-002 nightly mongodump backup task
- L4-003 PostMark failure-mode wiring in T135
- L4-004 Redis cache + arq fail-mode policy in tasks

### ⏭️ Deferred (2 items — not on Phase 6 critical path)

- L3-005 i18n key extraction (`i18n_harvest: not_applicable` in status)
- L3-008 Last.fm provider scaffolding (FR-017 is Should-Have)

### ⏸️ Skipped as advisory (14 INFO items)

L1-001, L2-004, L2-005, L2-006, L2-007, L2-009, L3-009, L3-010, L4-005, L4-009, L7-004 through L7-009 (digest-orphan convention question)

### 🚪 Gate override

- **Reason:** Zero individual findings are CRITICAL-severity. The CRITICAL DRIFT verdict was produced entirely by the strict `structural: 0` budget rule against 27 structural items. After applying the recommended split, residual drift items are either (a) plan-level additions that Phase 6 will pick up as implementation work, or (b) explicitly deferred items.
- **Approved by:** Joshua Xie (project owner, solo mode)
- **Approved at:** 2026-05-22T02:35:00Z
- **Next sync-verify expected:** After Phase 6B (code review) — should show structural drift = 0 once the 10 backlog items are landed.
