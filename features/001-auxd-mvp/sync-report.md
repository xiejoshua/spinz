# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #10 — 2026-05-23 (post-Session 17 §10 social + feed)**

---

## Run #10 (2026-05-23, post-§10-social-graph-and-feed)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **107/172** tasks complete (62%)
> Prior run: #9 (2026-05-23T15:45Z) — DRIFT_DETECTED, applied_split_with_override (12 inline + 8 deferred; Sessions 15-16 doc catch-up)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Session 17 (§10 Social graph + Feed: T101-T112 + inline GET /users/{handle})

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **11 NEW + 3 carry-forward = 14** | NEW: L1-002, L2-023, L2-024, L2-026, L3-025, L3-026, L3-027, L3-028, L3-030, L3-031, L4-021, L5-014. CF: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **8 NEW + 5 carry-forward = 13** | NEW: L2-025, L2-027, L3-023, L3-029, L3-032, L4-022, L4-023, L4-024, L5-015, L5-016, L5-017. CF: L2-019, L4-013, L4-017, L4-020, L5-008 |
| ✅ CLEAN | **L6 + L7** | Layer 6 verified clean for all Session 17 Must Have stories; L7 168 links across 38 files all resolve |
| ✅ RESOLVED since Run #9 | 0 new resolutions | (Run #9's 12 inline fixes all verified intact) |

**Structural count:** 17 (NEW: 13; CF: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 9 (NEW: 5; CF: 4 — L4-013, L4-017, L4-020, L5-008). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override (Applied — 16 inline + 8 deferred).** Same doc-catch-up pattern as Runs #8/#9. Session 17 shipped a large net-new surface (8 social routes + 4 feed routes + 1 inline profile endpoint + 2 collections + 5 PostHog events + for_you/latest mode split + multiplicative score formula) — plan.md, spec.md, and product-spec/ hadn't been amended for any of it. Code is healthy (667 pass/3 skip; +75 tests; 13 frontend routes; 0 orphan files). Resolved in a single coordinated edit pass covering plan.md (7 locations) + spec.md/product-spec (5 locations) + tasks.md (4 small fixes + 2 new deferred-task placeholders T101a + T163a) + 1 research breadcrumb. Carry-forwards remain user-deferred. Post-apply gates: ruff + mypy strict + Biome 104 files + tsc all clean (no source code touched).

### Sessions 17 propagation audit

| Cluster | Code shipped | Plan documented | Spec/product-spec documented | Drift IDs |
|---------|:---:|:---:|:---:|:--|
| Follow / unfollow (T101) | ✅ | ✅ | ✅ | — |
| Block (T102) | ✅ | ✅ | ✅ | — |
| Friends-who-rated (T103) | ✅ | ✅ | ✅ | — |
| Suggestions worker (T104) | ✅ | ⚠️ algorithm not in plan §12 | ⚠️ collection name + reason field drift | L2-026, L2-027, L3-025, L3-032 |
| Suggestions API + dismiss (T105) | ✅ | ❌ not in plan §6 | ✅ | L3-027, L4-024 |
| Home feed for_you/latest (T106) | ✅ | ❌ §10 has wrong contract + formula | ❌ "For You" name not in spec; mode toggle not described | L1-002, L2-023, L3-029, L3-030 |
| Feed perf (T107) | ✅ | ✅ | ✅ | — |
| Inline `GET /users/{handle}` | ✅ | partial (plan §6 mentions `user_profile`; relation enum absent) | ❌ no FR row | L2-024, L4-021 |
| FollowRequest approve/decline | partial (pending writes; responder UI not shipped) | ⚠️ plan §6 over-promises | ⚠️ US-G2 / S-H3 ambiguous | L2-025, L3-026, L4-022 |
| POST /reports/user (T111 frontend stub) | not shipped | ❌ no task | ❌ no task | L4-023 |
| Rate-limit table (§4.5) | shipped | ❌ stale | n/a | L3-028 |
| PostHog events | shipped | ❌ social events absent from §15.2 | n/a | L3-031 |
| Frontend feed UI + profile + follow + block-report + discover | ✅ | n/a (frontend) | ✅ | minor Paths under-enumeration (L5-015/16/17 under L5-008 umbrella) |
| Test filename match | shipped | ❌ T106 cites wrong filename | n/a | L5-014 |

### Key findings

**L1-002 (most substantive product question):** ux-patterns research explicitly said "resist any 'For You' injection until late v2" — code shipped `?mode=for_you|latest`. Weights ARE the "weight the activity types" anti-noise design research called for, but the LABEL is the exact phrase research warned against. Two options: (1) rename query param to `weighted|latest` (code churn), (2) amend ux-patterns with a breadcrumb clarifying "For You" here = interaction-weight reordering only, no out-of-graph injection. Recommended: option 2 (cheaper + faithful to research intent).

**L3-030 (plan vs shipped algorithm formula mismatch):** plan §10.2 says additive `score = base_recency + 0.20*has_review + ...`; shipped is multiplicative `score = 1.0 * 1.20(if review) * 1.15(if extreme) * ... * 0.5^(age_hours/72)`. These compose differently. Plan needs to match shipped (or vice versa — multiplicative is the better composer for stacking weights).

**L3-026 (plan over-promise):** plan §6 lists `respond_to_follow_request` + `list_follow_requests` as part of `social` module surface — neither shipped. Fix: mark as DEFERRED in plan.

**L4-022 + L4-023 (no T-id for deferred work):** FollowRequest approve/decline UI + `POST /reports/user` endpoint are both real future work with no tasks tracking them. Fix: add `T101a` (FollowRequest responder) and `T163a` (submit-report endpoints).

**L5-014 (filename typo):** T106 Paths cite `test_feed.py`; actual is `test_feed_endpoint.py`. One-line fix.

### Proposed inline actions (16 items)

| ID | File | Change |
|----|------|--------|
| L1-002 | research/ux-patterns.md | 1-line breadcrumb: "For You here = interaction-weight reordering; no out-of-graph injection" |
| L2-023 | spec.md US-E3 + product-spec S-E3 | Name both modes ("For You" weighted default + "Latest" chronological) in AC |
| L2-024 | spec.md §5 FR table | Add FR-036 (profile read with viewer-relation classifier, 404-on-blocked) |
| L2-025 | product-spec S-G2 + spec.md US-G2 | Append breadcrumb that approve/decline UI is tracked under S-H3 (Could-have) — MVP ships creation only |
| L2-026 | product-spec/data-model.md | Rename SuggestedFollow → Suggestion; add SuggestionDismissal block |
| L2-027 | product-spec/data-model.md | Suggestion reason field → `reasons: list[str]` (multiple) with shipped tag labels |
| L3-025 | plan.md §3.1 | Replace `suggested_follows` row with `suggestions` + `suggestion_dismissals` rows |
| L3-026 | plan.md §6 social row | Append shipped surface; mark `respond_to_follow_request` + `list_follow_requests` DEFERRED |
| L3-027 | plan.md §6 social row | Add `list_suggestions`, `dismiss_suggestion`, `list_blocks`, `get_user_profile` |
| L3-028 | plan.md §4.5 rate-limit table | Add 5 social/feed rows; correct stale `POST /follow` 30/min → 60/min |
| L3-029 | plan.md §10.1 | Replace `viewer.feed_latest_only` (User field) with `?mode=for_you|latest` query param |
| L3-030 | plan.md §10.2 | Rewrite score formula to match shipped (multiplicative + 0.5^(age_hours/72) half-life) |
| L3-031 | plan.md §15.2 PostHog table | Add 5 shipped social events (follow/unfollow/block/unblock/suggestion.dismiss) |
| L4-021 | tasks.md T109 Paths | Append `apps/api/src/auxd_api/modules/users/routes.py` (inline `get_user_profile`) |
| L5-014 | tasks.md T106 Paths | Rename `test_feed.py` → `test_feed_endpoint.py` |
| L4-022 + L4-023 | tasks.md §10/§15 | Insert `T101a` (FollowRequest approve/decline; DEFERRED) + `T163a` (POST /reports/user) |

### Defer (8 items)

- L2-019, L3-017, L4-009 — invite-mechanic cluster
- L4-013, L4-017, L4-020, L5-008, L5-015, L5-016, L5-017 — Paths-convention umbrella
- L6-002 — low-priority polish (US-A1 handle suggestions)

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1-#8 | (rows preserved below) | | | | | | |
| #9 | 2026-05-23 (post-§8+§9) | 7/7 | 0 | 12 | 10 | DRIFT_DETECTED | applied_split_with_override |
| **#10** | **2026-05-23 (post-§10)** | **7/7** | **0** | **14** | **13** | **DRIFT_DETECTED** | **applied_split_with_override** (16 inline applied + 8 deferred) |

---

## Run #9 (2026-05-23, post-§8-reviews-and-§9-backlog)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **95/171** tasks complete (56%)
> Prior run: #8 (2026-05-23T12:30Z) — DRIFT_DETECTED, applied_split_with_override (8 inline + 1 sweep fix; 6 deferred)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 15–16 (§8 Reviews + Likes + sort, §9 Backlog / Up Next)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **9 NEW + 3 carry-forward = 12** | NEW: L2-020, L2-021, L3-020, L3-021, L3-022, L3-024, L4-019, L5-013, L6-004. Carry-forward: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **6 NEW + 4 carry-forward = 10** | NEW: L1-001, L2-022, L3-023, L4-018, L4-020, L5-012. Carry-forward: L2-019, L4-013, L4-017, L5-008 |
| ✅ RESOLVED | **0 NEW resolutions** | Sessions 15–16 introduced new doc drift; carry-forward items from prior runs all still open. |
| ✅ CLEAN | **L7 only** | Cross-link integrity holds; L7-016 confirmed resolved since Run #8 |

**Structural count:** 13 (NEW: 9; carry-forward: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 9 (NEW: 6; carry-forward: 3 — L4-013, L4-017, L5-008). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override (Applied this run — 12 inline + 7 deferred).** Sessions 15–16 shipped 9 new REST endpoints (7 reviews, 2 backlog reads), the `albums`/`users` sidecar pattern, `Review.deleted_at` soft-delete, 4 new PostHog events, and `@dnd-kit` drag-reorder UX — none of which were documented in plan.md §6 (service surface), §3.1 (collection inventory), or §15.2 (analytics events). The shipped code is healthy; the gap was downstream doc catch-up. 9 of the 9 NEW WARNs resolved in a single coordinated edit pass:
1. **plan.md** catch-up to Session 15/16 reality (§6 rows for reviews + backlog; §3.1 reviews index; §15.2 PostHog event table; §12.1 CriticSeed correction).
2. **spec.md / product-spec** add FR-034 + FR-035 + US-C3 delete AC + Review schema fields.
3. **tasks.md** insert orphan T094 header + fix T093a / T100 stale Paths.
4. **Sessions 15-16 frontend gap** — L6-004 (US-C3 edit affordance not mounted) — add a small inline "Edit" button to the review reading-view footer.

Remaining carry-forwards (L2-019, L3-017, L4-009, L6-002) keep their existing dispositions — invite-mechanic cluster + low-priority polish.

### Sessions 15–16 propagation audit (the headline check)

| Cluster | Status | Notes |
|---------|:------:|-------|
| §8 Reviews + Likes + sort | ✅ Code shipped; 11/11 tasks complete; **plan + spec doc gaps** (L2-021, L3-020, L3-022, L6-004) |
| §9 Backlog / Up Next | ✅ Code shipped; 6/6 tasks complete; **plan + spec doc gaps** (L2-020, L3-021, L3-024, L5-013) |
| Must Have stories with implementation evidence | ✅ US-C1, US-C2, US-C4, US-D1, US-D2, US-D3 all have route + component + test. **US-C3 partial — edit dialog built but not yet mounted (L6-004)**. |
| Layer 5 forward sweep | ✅ All Session 15-16 declared Paths exist on disk; no orphan files |
| Layer 7 cross-links | ✅ CLEAN — 154 links across 37 files all resolve |

### New drift cluster: plan.md doc-catch-up to shipped reality

The single dominant root cause for 5 NEW WARNs (L3-020, L3-021, L3-022, L3-024, L4-019) is the plan.md not being amended after Sessions 15-16 shipped:

| plan.md location | What's missing | DRIFT ID |
|------------------|----------------|:--------:|
| §6 `reviews` row | `delete_review`, `get_review`, users-sidecar note | L3-020 |
| §6 `backlog` row | `list_backlog_items`, `contains_album`, albums-sidecar note | L3-021 |
| §3.1 `reviews` row | `deleted_at` sparse index + 30d-grace note | L3-022 |
| §12.1 critic-seed | "marked `critic_seed_active=true`" — should be CriticSeed table FK | L3-023 |
| §15.2 PostHog events | `backlog.added` → 4 shipped events: item_added, item_removed, reordered, converted_to_log | L3-024 |
| tasks.md §8 index | T094 header eaten (orphan task body at line 861) | L4-019 |

**Recommended inline resolution:** single coordinated pass amending plan.md (5 locations) + tasks.md (insert T094 header).

### New spec + product-spec gaps

| spec.md / product-spec | What's missing | DRIFT ID |
|------------------------|----------------|:--------:|
| spec.md §5 FR table | FR-034 (drag-reorder backlog with persisted order — US-D2) + FR-035 (auto-remove on log with `keep_backlog_after_log` setting — US-D3) | L2-020 |
| product-spec US-C3 AC + spec US-C3 | Delete-review AC (soft-delete 30d grace, confirmation dialog, idempotent 410) — currently shipped without story trace | L2-021 |
| product-spec/data-model.md Review block | `edited_at` + `deleted_at` field enumeration (DiaryEntry has both; Review is implicit via umbrella line) | L2-022 |

### New small-task / stale-path findings

| Where | What | DRIFT ID |
|-------|------|:--------:|
| tasks.md T093a Paths | `opengraph-image.tsx` listed but never shipped (deferred to T093c per impl-log Session 15) | L4-018 / L5-012 |
| tasks.md T100 Paths | Claims `apps/web/src/lib/analytics.ts` — emission is server-side via `emit_event`; no frontend analytics module exists | L5-013 |
| tasks.md T092 / T093 Paths | Helper files (`delete-confirmation.tsx`, `review-sort-select.tsx`, `recent-searches.tsx`) not enumerated — same Paths-convention umbrella as L4-013 | L4-020 |

### Layer 6 finding: US-C3 surface gap

**L6-004:** `EditReviewDialog` is implemented and exported (`apps/web/src/components/review-card/edit-review.tsx`) but never imported by any live route. The `review-reading-view` footer has no Edit button on the owner branch. Documented in implementation-log.md Session 15 as "ready-to-plug; activates when /profile/[handle]/reviews ships." A small ~10-line patch to surface it on the reading-view footer (when `isOwn`) would close the spec→code gap immediately.

### Carry-forward status snapshot

| ID | Description | Status | Disposition |
|----|-------------|:------:|-------------|
| L1-001 (NEW) | Backlog sort alternatives (rating/year) silently omitted vs research | OPEN | Apply inline (1-line breadcrumb) |
| L2-019 | SS-3 cohort `signup_cohort` undefined | OPEN | DEFER (invite-mechanic cluster) |
| L3-017 | plan.md §12 missing SS-3 invite-landing section | OPEN | DEFER (invite-mechanic cluster) |
| L4-009 | tasks.md missing invite-landing tasks | OPEN | DEFER (invite-mechanic cluster) |
| L4-013 | Paths under-enumeration convention | OPEN-DEFERRED | DEFER (convention umbrella) |
| L4-017 | T077/T079 Paths missing `recent-searches.tsx` | OPEN-DEFERRED | DEFER (convention umbrella) |
| L5-008 | T080 wildcard absorbs helpers; convention not written | OPEN-DEFERRED | DEFER (convention umbrella) |
| L6-002 | US-A1 auto-handle suggestions on collision | OPEN | DEFER (low-priority polish) |

### Proposed actions (inline + deferred)

**Applied inline this run (12 items, single coordinated pass — all green):**

| ID | File(s) | Change | Status |
|----|---------|--------|:------:|
| L1-001 | product-spec/user-stories.md | S-D2 breadcrumb deferring rating/year/added-date sort modes to v2 | ✅ APPLIED |
| L2-020 | spec.md §5 FR table | Added FR-034 (drag-reorder) + FR-035 (auto-remove on log) | ✅ APPLIED |
| L2-021 | product-spec/user-stories.md S-C3 (retitled "Edit (or delete)") + spec.md US-C3 | Delete-review AC line appended | ✅ APPLIED |
| L2-022 | product-spec/data-model.md Review block | `edited_at` + `deleted_at` field lines added | ✅ APPLIED |
| L3-020 | plan.md §6 reviews row | `delete_review` + `get_review` + users-sidecar note appended | ✅ APPLIED |
| L3-021 | plan.md §6 backlog row | `list_backlog_items` + `contains_album` + albums-sidecar note appended | ✅ APPLIED |
| L3-022 | plan.md §3.1 reviews row | `deleted_at sparse` index + 30d-grace note | ✅ APPLIED |
| L3-023 | plan.md §12.1 critic-seed | "critic_seed_active=true" replaced with CriticSeed FK truth | ✅ APPLIED |
| L3-024 | plan.md §15.2 PostHog table | `backlog.added` row replaced with 4 shipped events (item_added, item_removed, reordered, converted_to_log) | ✅ APPLIED |
| L4-019 / L4-018 / L5-012 | tasks.md §8 | Orphan T094 header restored at line 860 ("Reviews-only profile sub-route"); T093a Paths fixed (opengraph-image.tsx dropped, T093c follow-up note added) | ✅ APPLIED |
| L5-013 | tasks.md T100 Paths | `apps/web/src/lib/analytics.ts` dropped; cite `apps/api/.../diary/routes.py` | ✅ APPLIED |
| L6-004 | apps/web/src/components/review-reading-view/index.tsx | "Edit" button on owner footer opens `EditReviewDialog` (~10-line patch; build green) | ✅ APPLIED |

Build verification post-apply: Biome 96 files clean; tsc 0 errors; next build 11 routes (no bundle-size regression for `/review/[id]`).

**Defer (7 items, existing dispositions stand):**
- L2-019, L3-017, L4-009 — invite-mechanic cluster sequencing
- L4-013, L4-017, L5-008 — Paths-convention umbrella
- L6-002 — low-priority polish
- L4-018, L5-012 — overlapping with the inline T100 + T093a fixes (will be subsumed)
- L3-023 — short cosmetic edit included in the inline pass

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #8 | 2026-05-23 (post-§7-wedge-wave) | 7/7 | 0 | 8 | 9 | DRIFT_DETECTED | applied_split_with_override |
| **#9** | **2026-05-23 (post-§8+§9 waves)** | **7/7** | **0** | **12** | **10** | **DRIFT_DETECTED** | **applied_split_with_override** (pending user confirmation) |

---

## Run #8 (2026-05-23, post-§7-wedge-wave)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **75/172** tasks complete (44%)
> Prior run: #7 (2026-05-23T09:30Z) — DRIFT_DETECTED, applied_split_with_override (4 WARN + 4 INFO; 2 deferred to invite-mechanic cluster, 2 NEW spec-vs-code gaps tracked for next wave)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 13–14 (§7 Diary + Log sheet wedge wave: T073–T084 — wedge interaction now end-to-end live)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **5 NEW + 3 carry-forward = 8** | NEW: L3-019, L4-014, L4-015, L5-007, L7-016. Carry-forward: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **7 NEW + 2 carry-forward = 9** | NEW: L3-018, L4-016, L4-017, L5-008, L5-009, L5-010, L5-011. Carry-forward: L2-019, L4-013 |
| ✅ RESOLVED | **3** | L4-010 (plan §7.1 routes added inline post-Run #7), L4-011 (T072 ref to §11.4 verified), **L6-003 (T081 my-history.tsx shipped)** |
| ✅ CLEAN | **1 layer** | L1 — research ↔ product-spec consistent under CR-002 propagation |

**Structural count:** 10 (NEW: 6 — L3-019, L4-014, L4-015, L4-016, L5-007, L7-016; carry-forward: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 7 (NEW: 6 — L3-018, L4-017, L5-008, L5-009, L5-010, L5-011; carry-forward: 1 — L4-013). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of Runs #2–#7 pattern. Override granted because (1) zero CRITICAL findings, (2) 4 of the 5 NEW WARN items (L3-019, L4-014, L5-007, L7-016) are projections of the same root cause — the Session 14 `/profile/[handle]` vs `/@[handle]` routing decision; these resolve in a single coordinated edit pass and are applied inline below, (3) L4-015 (diary `albums` sidecar) is a fresh API contract worth documenting before §8 reviews land — applied inline, (4) L6-002 (US-A1 handle suggestions) and L3-017 / L4-009 (invite-mechanic cluster) remain user-deferred under their existing dispositions, (5) Sessions 13–14 themselves landed cleanly across L1, L2 (CLEAN), and L5/L6 forward checks (every shipped Must Have story has route + component + test evidence).

**Inline application (Run #8 close-out):** All 8 planned inline items applied without errors; verified by post-edit grep. spec.md:350 (frontend module table) had a missed `app/@[handle]` reference caught in the post-edit sweep — also fixed under the L3-019 umbrella.

### Sessions 13–14 propagation audit (the headline check)

The two wedge-wave sessions (Session 13 backend wave + Session 14 §7 close-out) introduced 12 new code modules across backend and frontend. **L5 backward sweep confirms zero orphan files** — every modified or new file traces to a `[x]` task in tasks.md. **L6 forward sweep confirms every Must Have story shipped in this wave has implementation evidence:**

| Story | Wave evidence | Status |
|-------|--------------|:------:|
| US-B1 (log <8s) | T077 log-sheet + T084 NFR test (10-trial p95 <8000ms; backend <1500ms in-process) | ✅ |
| US-B2 (½-star rating) | T077 `rating-widget.tsx` with ARIA slider | ✅ |
| US-B3 (Aux toggle) | T077 `aux-toggle.tsx` + T073 `auxed` bool persisted | ✅ |
| US-B4 (relisten + my history) | T073 relisten flag + T081 `my-history.tsx` (resolves L6-003) | ✅ |
| US-B5 (edit/delete diary entry) | T075 backend (PATCH+DELETE+restore) + T082 edit UI + T083 delete-confirmation + 8s undo toast | ✅ |
| US-E2 (chronological diary on profile) | T074 backend cursor pagination + T080 `/profile/[handle]` SSR + client `DiaryList` | ✅ |
| US-F1 (album-detail my history) | T081 `my-history.tsx` + `album/[id]/page.tsx` wires `<MyHistory>` | ✅ |

### New drift cluster: the `/profile/[handle]` ↔ `/@[handle]` route decision

The single dominant root cause for 4 of 5 NEW WARNs (L3-019, L4-014, L5-007, plus the parenthetical L3-018) is the Session 14 routing decision documented in implementation-log.md (line 220, 236):

> "Next.js cannot use `@<segment>` as a folder name (the `@` prefix is reserved for parallel routes). Going with `/profile/<handle>` for now; the `/@handle` SEO/sharing URL can land later via middleware rewrite."

This single decision affects:

| Artifact | Locations | Drift ID |
|----------|-----------|:--------:|
| plan.md | §1.2 (file tree), §7.1 (routing bullet), §11.3 (share URL), §16.5 (a11y page list) | L3-019 |
| tasks.md | T080 Paths, T093d Paths, T101 Paths | L4-014 / L5-007 |
| implementation-log.md | Session 14 references "plan §16" (wrong — §16 is testing) | L3-018 |

**Recommended inline resolution (single coordinated pass):**
1. plan.md — update 4 locations to cite `/profile/[handle]` as canonical; add a Handle-URL-Aliasing subsection noting the deferred middleware rewrite.
2. tasks.md — fix 3 stale Paths entries (T080, T093d, T101).
3. implementation-log.md — fix Session 14 "plan §16" → "plan §7.1 / §1.2" (3 occurrences).

### New finding: diary `albums` sidecar contract

L4-015: Session 14 added a server-side `albums: {[id]: AlbumCard}` sidecar to `GET /users/{handle}/diary` (one Album lookup per page, deduped on `_id`). 2 new integration tests lock the contract. But T074 description and plan.md §6 still describe only `{entries, next_cursor}`. Worth documenting now because §8 reviews-list will likely want the same sidecar pattern (or a parallel reviewers sidecar).

**Recommended inline resolution:**
1. tasks.md T074 — append response envelope `{entries, next_cursor, albums: {id: AlbumCard}}` with `AlbumCard = {id, mbid, title, artist_credit, release_year, cover_art_url}`.
2. plan.md §6 — add a brief note next to the `diary` row about the sidecar pattern.

### Carry-forward status snapshot

| ID | Description | Status | Disposition |
|----|-------------|:------:|-------------|
| L2-019 | SS-3 cohort-gate derivation underspecified (signup_cohort not defined) | **OPEN — narrowed in Run #8** (data-model.md now references `signup_cohort` via `visible_in_just_joined` default without defining it) | DEFER to invite-mechanic cluster sequencing (alongside L3-017 + L4-009) |
| L3-017 | Plan §12 missing SS-3 invite-landing ticker section | **OPEN** | DEFER (invite-mechanic cluster) |
| L4-009 | tasks.md missing invite-landing tasks | **OPEN** | DEFER (invite-mechanic cluster) |
| L4-010 | Plan §7.1 routing should enumerate `/search` and `/api/cover` | **RESOLVED** (inline added post-Run #7) | — |
| L4-011 | T072 references plan §17.5 (should be §11.4) | **RESOLVED** | — |
| L4-013 | Multiple task Paths under-specify helper files | OPEN-DEFERRED | Project-level convention note ("Paths = primary surfaces") still unwritten; Run #7 disposition stands |
| L6-002 | US-A1 auto-handle suggestions on collision unimplemented | **OPEN** | DEFER (low-priority polish; no first-launch collision impact) |
| L6-003 | US-F1 my-history section on album detail unimplemented | **RESOLVED** by T081 | — |

### All Drift Items

#### NEW this run

**L3-018** [INFO / cosmetic] implementation-log Session 14 cites "plan §16" — plan §16 is Testing Strategy, not Routing. Should cite §7.1 (routing enumeration) + §1.2 (file-tree). 3 occurrences.
*Proposed:* Edit `implementation-log.md` Session 14 occurrences of "plan §16" → "plan §7.1 / §1.2". Trivial.

**L3-019** [WARNING / structural] Plan §1.2, §7.1, §11.3, §16.5 still enumerate `/@[handle]/` as a Next.js route folder. Shipped code at `apps/web/src/app/(app)/profile/[handle]/page.tsx`.
*Proposed:* Update 4 plan.md locations to `/profile/[handle]` as canonical; add a follow-up note about a future middleware rewrite for `/@handle`.

**L4-014** [WARNING / structural] T080, T093d, T101 declare paths under `(app)/@[handle]/` — folder name Next.js can't create.
*Proposed:* Update T080, T093d, T101 Paths to `(app)/profile/[handle]/`. Single-line edit per task.

**L4-015** [WARNING / structural] GET `/users/{handle}/diary` now returns `{entries, next_cursor, albums: {id: AlbumCard}}` sidecar (Session 14 contract addition). T074 description and plan §6 don't mention it.
*Proposed:* Append response envelope to T074 description; add one-line note to plan §6 row for `diary` cross-referencing T074.

**L4-016** [INFO / structural] T082 description says "pre-fill the entry's current values" — Session 14 shipped rating/aux/visibility only (review-body edit deferred to §8 T086).
*Proposed:* One-line clarification to T082 Description: "pre-fill rating + aux + visibility; review-body edit lands with T086."

**L4-017** [INFO / cosmetic] T077 / T079 Paths don't list `recent-searches.tsx` (Session 13). Same pattern as L4-013.
*Proposed:* Same disposition as L4-013 (convention note). No edit required.

**L5-007** [WARNING / structural] T080/T093d/T101 declare `(app)/@[handle]/` — folder name Next.js can't create. Projection of L3-019/L4-014.
*Proposed:* Same fix as L4-014 (resolves both L4 and L5 simultaneously).

**L5-008** [INFO / cosmetic] T080's `components/diary/*` wildcard absorbs 3 of 4 new diary helpers; `recent-searches.tsx` on T079 is the only real omission.
*Proposed:* No edit required if wildcard convention holds; track under the L4-013 convention disposition.

**L5-009** [INFO / cosmetic] T083 Paths declares frontend-only; the backend restore endpoint (T075 ships it) isn't called out in any task that references restoration.
*Proposed:* One-line note in T075 description: "T075 also delivers `POST /diary/entries/{id}/restore`."

**L5-010** [INFO / cosmetic] T079 declares `album-prefill.tsx` — file never shipped (prefill logic inlined into `album-search.tsx` + `log-sheet/index.tsx`).
*Proposed:* T079 Paths — replace `album-prefill.tsx` with `recent-searches.tsx`.

**L5-011** [INFO / cosmetic] T082 declares `components/diary/edit-entry.tsx` — file never shipped (edit functionality reused `log-sheet/index.tsx` via `LogSheetSeed.edit`).
*Proposed:* T082 Paths — replace `edit-entry.tsx` with `log-sheet/index.tsx (edit-mode), diary/diary-entry-card.tsx (edit trigger)`.

**L7-016** [WARNING / structural] spec.md:138 has a broken anchor `[sync-report.md](./sync-report.md#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30)` — no DRIFT-L2-003 heading exists in the current sync-report.md (Run #1 was compacted).
*Proposed:* Drop the anchor; leave the bare `[sync-report.md](./sync-report.md)` link plus the parenthetical "sync-verify Run #1" prose.

#### Carry-forward (still open from prior runs)

- **L2-019** — INFO structural — SS-3 cohort gate references undefined `signup_cohort` field. DEFER (invite-mechanic cluster).
- **L3-017** — WARNING structural — plan.md §12 missing SS-3 invite-landing ticker section. DEFER (invite-mechanic cluster).
- **L4-009** — WARNING structural — tasks.md missing invite-landing tasks. DEFER (invite-mechanic cluster).
- **L4-013** — INFO cosmetic — multiple task Paths under-specify helper files. OPEN-DEFERRED under unwritten convention note.
- **L6-002** — WARNING structural — US-A1 auto-handle suggestions on collision unimplemented. DEFER (no first-launch impact).

#### Resolved this run

- **L4-010** — RESOLVED — plan §7.1 enumerates `/search` and `/api/cover/[size]/[mbid]` (lines 555–557, inline-applied post-Run #7).
- **L4-011** — RESOLVED — T072 reference to plan §11.4 (cover-art proxy section) verified intact.
- **L6-003** — RESOLVED — T081 shipped `apps/web/src/components/album-detail/my-history.tsx` and wired it into `app/(app)/album/[id]/page.tsx`.

### Proposed actions (inline + deferred)

**Applied inline this run (8 items + 1 missed-ref caught in post-edit sweep):**

| ID | File(s) | Change | Status |
|----|---------|--------|:------:|
| L3-018 | implementation-log.md | "plan §16" → "plan §1.2 / §7.1 / §11.3" in 3 Session 14 occurrences | ✅ APPLIED |
| L3-019 | plan.md | §1.2 file-tree, §7.1 routing bullet (+ new §7.1.1 Handle-URL-Aliasing subsection), §11.3 share URL, §16.5 a11y page list all repointed to `/profile/[handle]` | ✅ APPLIED |
| L4-014 / L5-007 | tasks.md | T080, T093d, T101 Paths: `(app)/@[handle]/` → `(app)/profile/[handle]/` | ✅ APPLIED |
| L4-015 | tasks.md + plan.md | T074 description: appended response envelope `{entries, next_cursor, albums}` + AlbumCard shape. plan.md §6 diary row: appended sidecar note + cross-ref to T074 | ✅ APPLIED |
| L4-016 | tasks.md | T082 description amended: "review-body editing lands with T086" + Refs aligned to actual shipped files | ✅ APPLIED |
| L5-009 | tasks.md | T075 description amended: explicitly enumerates `POST /diary/entries/{id}/restore` as part of T075's scope | ✅ APPLIED |
| L5-010 | tasks.md | T079 Paths: `album-prefill.tsx` → `recent-searches.tsx` | ✅ APPLIED |
| L5-011 | tasks.md | T082 Paths: `diary/edit-entry.tsx` → `log-sheet/index.tsx (edit-mode), diary/diary-entry-card.tsx (edit trigger), stores/ui.ts (LogSheetSeed.edit)` | ✅ APPLIED |
| L7-016 | spec.md | Broken `#drift-l2-003` anchor dropped; bare link + Run #1 prose preserved | ✅ APPLIED |
| (caught in sweep) | spec.md:350 | Frontend module table row `app/@[handle]` → `app/profile/[handle]` + middleware-rewrite cross-ref to plan §7.1.1 | ✅ APPLIED |

**Defer (6 items, existing dispositions stand):**

- L2-019, L3-017, L4-009, L4-013 — invite-mechanic cluster sequencing
- L4-017, L5-008, L5-009 — convention-note umbrella (track under L4-013)
- L6-002 — low-priority polish

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| **#8** | **2026-05-23 (post-§7-wedge-wave)** | **7/7** | **0** | **8** | **9** | **DRIFT_DETECTED** | **applied_split_with_override** (pending user confirmation) |

---

## Run #7 (2026-05-23, post-frontend-wave)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **63/172** tasks complete (37%)
> Prior run: #6 (2026-05-23T04:45Z) — DRIFT_DETECTED, applied_split_with_override (3 items deferred to invite-mechanic cluster sequencing)
> Trigger: user invoked `/speckit.product-forge.sync-verify` with "Verify the new code" after Sessions 10–12 (§3 + §5 + §6 frontend completion)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **4** | 2 NEW (L6-002, L6-003 — US-A1/US-F1 spec ↔ code gaps) + 2 carry-forward (L3-017, L4-009 — Run #6 deferred) |
| ℹ️ INFO | **4** | 3 NEW (L4-010 plan §7.1 routes catch-up; L4-011 T072 ref to wrong plan §; L4-013 task Paths under-specified) + 1 carry-forward (L2-019 cohort rule) |
| ✅ CLEAN | 3 layers fully clean (L1, L2, L7) | |

**Structural count:** 6 (over budget of 0) — 3 NEW + 3 carry-forward.
**Cosmetic count:** 2 (under budget of 20) — L4-012 instrumentation-client.ts + L4-013 helper-file paths.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of Run #2/#3/#4/#5/#6 pattern. Override granted because (1) zero CRITICAL findings, (2) all 4 NEW WARN items are doc-catch-up after the frontend wave (no broken contracts), (3) Sessions 10–12 themselves landed cleanly across L1/L2/L5/L7, (4) the 2 NEW L6 spec-vs-code gaps are tracked refinements for the next §6/§7 wave rather than show-stoppers.

### Sessions 10–12 propagation audit (the headline check)

| Wave | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Session 10 (§3 core, T031–T036) | n/a | ✅ | ✅ | ⚠️ L4-013 (helper paths) | ✅ | n/a (foundation) | ✅ |
| Session 11 (§3 + §5 UI, T037–T040, T061, T062) | n/a | ✅ | ⚠️ L4-010 (plan §7.1) | ⚠️ L4-012/L4-013 | ✅ | ⚠️ L6-002 (US-A1 handle suggestions) | ✅ |
| Session 12 (§6 frontend, T070–T072) | n/a | ✅ | ⚠️ L4-010/L4-011 | ⚠️ L4-013 | ✅ | ⚠️ L6-003 (US-F1 my-history list) | ✅ |
| Operator-side .env.local fix (between S11 and S12) | n/a | n/a | n/a | n/a | ✅ | ✅ | n/a |

L5 forward (completed tasks → code) is CLEAN — all 37 expected files from T031–T040, T061, T062, T070–T072 exist on disk. L5 backward (code → tasks) is CLEAN — every modified file is inside a completed-task scope. L7 is CLEAN — zero broken links in new doc sections.

### NEW findings (Run #7)

#### DRIFT-L4-010 — plan.md §7.1 missing `/search` + `/api/cover` route enumeration
- **Layer:** 4 (forward, tasks → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `tasks.md` T071 (search page) + T072 (cover-art proxy) — both shipped
- **Target:** `plan.md` §7.1 Routing (Next.js App Router) — enumerates `/album/[id]`, `/@[handle]`, `/review/[id]`, `/`, `api/og/...` but not `/search` or `/api/cover/[size]/[mbid]`
- **Evidence:** plan.md:546–555 lists routes; absent are `/search` and `/api/cover/[size]/[mbid]/route.ts`.
- **Expected:** Add two bullets to §7.1: (a) `/search` SSR'd page with debounced client-side query; (b) `/api/cover/[size]/[mbid]` Route Handler proxying Cover Art Archive with `?fallback=...` redirect.
- **Proposed resolution:** Two-line addition to plan.md §7.1.
- **Auto-resolvable:** No.
- **Disposition:** APPLY INLINE — doc-only catch-up; low risk; isolates the routes for future readers.

#### DRIFT-L4-011 — T072 references plan §17.5 (Redis), not the cover-art proxy
- **Layer:** 4 (forward, tasks → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `tasks.md` T072 `Refs: plan §17.5; DM-2; CR-001`
- **Target:** `plan.md` §17.5 — currently titled "Redis" and describes Upstash. No cover-art-proxy subsection exists.
- **Evidence:** T072 ref string says "plan §17.5"; plan §17.5 is Redis hosting; cover-art proxy implementation pattern has no dedicated plan section. CAA usage IS described in `plan.md §1.2`, `§6 module table`, `§15.4 (CAA 404 rate metric)`, and `§17.4 (CAA hot-link policy)` — but no §X.Y for the Next.js proxy route handler.
- **Expected:** Either (a) add a `§11.3 Cover-art proxy (route handler)` subsection describing the `/api/cover/[size]/[mbid]` proxy pattern + CAA 404 fallback chain + 7-day cache headers, or (b) update T072's `Refs:` line to point to whichever existing plan section best fits (likely `§17.4 / §6.5`).
- **Proposed resolution:** Add `§11.3` subsection to plan.md and update T072 Refs.
- **Auto-resolvable:** No.
- **Disposition:** APPLY INLINE — minor doc structure addition.

#### DRIFT-L4-012 — T036 Paths missing `instrumentation-client.ts`
- **Layer:** 4 (forward, tasks → plan/Paths)
- **Severity:** ℹ️ INFO — **Category:** cosmetic
- **Source:** `tasks.md` T036 Paths list (`apps/web/src/lib/sentry.ts, apps/web/src/lib/posthog.ts, apps/web/instrumentation.ts`)
- **Target:** Actual code includes `apps/web/instrumentation-client.ts` (required by @sentry/nextjs v8+ for browser-runtime init).
- **Evidence:** File exists; not in T036 Paths.
- **Expected:** T036 Paths should add `apps/web/instrumentation-client.ts` for completeness.
- **Proposed resolution:** Append to T036 Paths line.
- **Auto-resolvable:** No (per Step 3A — task descriptions are structural).
- **Disposition:** APPLY INLINE — single-line update.

#### DRIFT-L4-013 — Multiple task Paths under-specified vs actual shipped infrastructure
- **Layer:** 4 (forward, tasks → code)
- **Severity:** ℹ️ INFO — **Category:** cosmetic (no contract change; just under-enumeration)
- **Source:** Various tasks (T037, T038, T039, T070, T071, T036, T033)
- **Target:** `tasks.md` Paths lines for each
- **Evidence:** Shipped infrastructure files not in any task's declared Paths:
  - `apps/web/src/components/ui/label.tsx` (T038 — needed by Form composition, missing from T032 scaffold)
  - `apps/web/src/components/nav/log-fab.tsx` (T037 — companion to bottom-tabs)
  - `apps/web/src/components/nav/onboarding-progress.tsx` (T039 — companion to onboarding layout)
  - `apps/web/src/components/health-check.tsx` (T033 — smoke surface)
  - `apps/web/src/lib/album-types.ts` (T070 — shared TypeScript types)
  - `apps/web/src/lib/api-server.ts` (T070 — `server-only` fetch helper)
  - `apps/web/src/lib/auth-schemas.ts` (T038 — Zod schemas)
  - `apps/web/src/lib/posthog-server.ts` (T036 — server-only PostHog client, split for webpack bundling fix)
- **Expected:** Each task's Paths list should be updated to reflect actual shipped files (or accept that ancillary helpers are out-of-scope for Paths).
- **Proposed resolution:** Add a project-level convention note clarifying that Paths is "primary surfaces only", not "every file touched". This bypasses needing to amend every task.
- **Auto-resolvable:** No.
- **Disposition:** DEFER — a convention note is the right fix but it's not a per-task amendment. Track in implementation-log as a process improvement.

#### DRIFT-L6-002 — US-A1 AC "auto-handle suggestions on collision" not implemented
- **Layer:** 6 (forward, spec → code)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `spec.md:145` US-A1 AC: *"email + password + handle (no music-service OAuth shortcut); auto-handle suggestions on collision."*
- **Target:** `apps/web/src/app/(auth)/signup/signup-form.tsx` — on backend 422 returns generic error message; doesn't render suggested-alternate handles.
- **Evidence:** signup-form's `setApiFormErrors` maps backend errors to field-level errors. If backend returns `{detail: [{msg: "handle taken", loc: ["body", "handle"]}]}`, the form shows the msg. But there's no separate "suggested handles" rendering path.
- **Expected:** Either backend `/api/v1/auth/signup` returns 422 with a `suggested_handles: [...]` extension, OR backend exposes `GET /api/v1/users/handle-suggestions?email=...` that frontend calls on collision. Frontend then renders 3 suggested chips below the handle field.
- **Actual:** Neither. Backend currently returns a plain error; frontend has no UI affordance for suggestions.
- **Proposed resolution:** Two-part:
  1. Backend: extend signup endpoint error response (or add a sibling endpoint) to return suggestions.
  2. Frontend: signup-form renders 3 suggested chips on collision; clicking a chip pre-fills the handle field.
- **Auto-resolvable:** No.
- **Disposition:** DEFER to a §5 polish task or a §11 onboarding task. Tracked as a spec-acceptance gap; not critical until first user actually hits a collision.

#### DRIFT-L6-003 — US-F1 AC "my history" section absent from album-detail page
- **Layer:** 6 (forward, spec → code)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `spec.md:190` US-F1 AC: *"SSR; cover, metadata, tracklist, **my history**, friends' ratings + Aux'd, public reviews list..."*
- **Target:** `apps/web/src/app/(app)/album/[id]/page.tsx` + `components/album-detail/*` — renders cover, metadata, tracklist, friends, public reviews, edition selector, OG meta. **Does NOT render a "my history" section.** Only the latest entry is shown via `<AlbumActions>` ("You rated this 4★ · Aux'd").
- **Evidence:** Backend response includes `my_history: DiaryRow[]` (up to `_MY_HISTORY_LIMIT` entries). The page consumes `my_history[0]` for the latest-entry chip but doesn't render the full history list.
- **Expected:** A `<MyHistorySection>` component rendering all `my_history` entries (logged_at + rating + auxed flag + visibility) as a list when `my_history.length > 1`. Single entry continues to show as the chip in AlbumActions.
- **Proposed resolution:** Add `components/album-detail/my-history-section.tsx` (small component, ~30 LOC) + render in `album/[id]/page.tsx` when `my_history.length > 1`.
- **Auto-resolvable:** No.
- **Disposition:** APPLY in next §7 wave alongside the log-sheet (which will be the primary way users add diary entries — having the history rendered there closes the loop visually).

### Carry-forward (Run #6 — unchanged, still deferred per Run #6's disposition)

- **DRIFT-L3-017** — plan.md §12 missing SS-3 invite-landing ticker logic. Still deferred to invite-mechanic cluster sequencing.
- **DRIFT-L4-009** — tasks.md missing invite-landing tasks. Still deferred.
- **DRIFT-L2-019** — SS-3 cohort-gate derivation underspecified. Still deferred.

### Recurring advisory (unchanged from Runs #2–#6)

11 items: L1-001, L1-002, L2-004/005, L2-006, L2-009, L3-009, L3-010, L4-005, L7-004..008 (5 items), L7-013. See Run #6 for descriptions.

### Next action

User to disposition the 4 NEW WARN/INFO items. Recommended order:
1. **L4-010** + **L4-011** apply inline now — small doc adds to plan.md §7.1 (+ new §11.4 cover-art-proxy subsection).
2. **L4-012** apply inline now — single-line T036 Paths update.
3. **L6-003** defer to next §7 wave (alongside log-sheet) — natural sequencing.
4. **L6-002** defer to a §5 polish task — handle suggestions are nice-to-have, not first-launch blockers.
5. **L4-013** convention note (defer; track as process improvement, not per-task amendment).
6. Carry-forward Run #6 items remain deferred to invite-mechanic cluster.

### Applied resolutions (Run #7 — user-approved inline)

| ID | File(s) touched | Change |
|---|---|---|
| **L4-010** | `plan.md` §7.1 | Added two bullets enumerating `/search` (debounced TanStack Query client page) and `/api/cover/[size]/[mbid]` (CAA Route Handler), with cross-refs to §11.2/§11.4. |
| **L4-011** | `plan.md` §11.4 (new) + `tasks.md` T072 | Added new §11.4 "Cover-art proxy (Next.js Route Handler)" — full subsection covering request shape, behavior, param-naming note, consumer pattern, observability. Updated T072 Refs from `plan §17.5` → `plan §11.4`; renamed Paths param `[albumId]` → `[mbid]`; documented rename rationale in description. |
| **L4-012** | `tasks.md` T036 | Appended `apps/web/instrumentation-client.ts` to T036 Paths (required by @sentry/nextjs v8+ for browser-runtime init). |

**Deferred (per user disposition):**
- **L4-013** — convention note about Paths being "primary surfaces only" — tracked here as a process improvement, not a per-task amendment.
- **L6-002** — US-A1 auto-handle suggestions → defer to §5 polish or §11 onboarding task. Needs backend coordination first.
- **L6-003** — US-F1 my-history section → defer to next §7 wave (will land alongside the log-sheet — natural sequencing since the log-sheet writes diary entries that populate my_history).
- **Run #6 carry-forward** (L3-017, L4-009, L2-019) — unchanged; tied to invite-mechanic cluster sequencing.

**Gate:** override granted; verdict `applied_split_with_override`. Phase 6 unblocked.

---

## Run #6 (2026-05-23, post-CR-002)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — 48/170 tasks complete (164 active + 8 deferred after CR-002 added T093a/b)
> Prior run: #5 (2026-05-23T03:00Z) — DRIFT_DETECTED, applied_split_with_override
> Trigger: CR-002 (Phase 2 decision review pass) filed; user invoked `/speckit.product-forge.sync-verify`

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **2** | Both are L3/L4 projections of the same single gap (SS-3 invite-mechanic not yet sequenced) |
| ℹ️ INFO | **1** | SS-3 cohort-derivation rule underspecified |
| ✅ CLEAN | 5/7 layers (L1, L2, L5, L6, L7) | |

**Structural:** 3 (over budget of 0) — all three express the same SS-3-cluster-pending-sequencing gap from different layer-projections.
**Cosmetic:** 0 (under budget of 20).

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of the Run #2/#3/#4/#5 pattern. Override granted because (1) zero CRITICAL findings, (2) the 3 NEW items are pre-acknowledged in CR-002 under `tasks_followup_pending_cluster: ["invite-landing /i/{handle} ticker (SS-3) — cluster not yet sequenced in tasks.md"]`, and (3) CR-002 itself was applied cleanly across 14 artifacts with full forward propagation everywhere else.

### CR-002 application audit

| CR-002 Change | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Q3 rationale softening | ✅ | ✅ | ✅ | n/a | n/a | n/a | ✅ |
| Differentiator row softening | ✅ | ✅ | ✅ | n/a | n/a | n/a | ✅ |
| NT-2 three-hero carousel | n/a | ✅ | ✅ | ✅ | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| SS-3 invite ticker + opt-in flag | n/a | ✅ | ⚠️ L3-017 | ⚠️ L4-009 | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| UJ-3 `/review/:id` route only | n/a | ✅ | ✅ | ✅ | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| UJ-4 v2 roadmap note | n/a | ✅ | n/a | n/a | n/a | n/a | ✅ |

Only the SS-3 column has open drift — same single gap viewed from two layers + one internal-consistency note. The CR-002 itself pre-flagged this, so Run #6 completes its job: surface the deliberate gap as a tracked finding for the next cluster-sequencing pass.

### NEW findings (Run #6)

#### DRIFT-L3-017 — plan.md §12 missing SS-3 invite-landing ticker logic
- **Layer:** 3 (forward, spec/product-spec → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `product-spec/seeding-strategy.md:74-78` (Mechanics block, CR-002)
- **Target:** `plan.md` §12 Seeding-Strategy Backend (no §12.4 / §12.5 for invite-mechanic)
- **Evidence:** seeding-strategy.md describes the "Recently joined" ticker with 15-min cache + cohort-gate defaults; plan.md §12 only covers CriticSeed roster + pre-checked card algorithm.
- **Expected:** Plan.md §12.4 (or §12.5) subsection with query (`User.find({visible_in_just_joined: True}).sort(handle_created_at desc).limit(3)`), 15-min Redis cache key shape, and cohort-gate logic for the default flag value on signup.
- **Proposed resolution:** Add §12.4 when invite-mechanic cluster is sequenced. Mirror §12.2 algorithm-block style.
- **Auto-resolvable:** No.
- **Disposition:** DEFERRED — pre-flagged in CR-002.

#### DRIFT-L4-009 — tasks.md missing invite-landing + visible_in_just_joined task(s)
- **Layer:** 4 (forward, plan → tasks)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `product-spec/data-model.md:53` (`User.visible_in_just_joined` field, CR-002) + `product-spec/seeding-strategy.md:74-78`
- **Target:** `tasks.md` (no row matches)
- **Expected:** Minimum 3 tasks when the cluster is sequenced — (a) backend `GET /api/v1/seeds/just-joined` endpoint + 15-min cache + Field migration on User; (b) frontend landing-page ticker component + onboarding-step-1 ticker placement; (c) settings task — Settings → Privacy toggle for `visible_in_just_joined`.
- **Proposed resolution:** Insert when the invite-mechanic cluster (likely §11/§12 backend wave) is sequenced. Task IDs reserved-but-not-allocated.
- **Auto-resolvable:** No.
- **Disposition:** DEFERRED — pre-flagged in CR-002 (`tasks_followup_pending_cluster`).

#### DRIFT-L2-019 — SS-3 cohort-gate derivation underspecified
- **Layer:** 2 (internal — seeding-strategy.md ↔ data-model.md)
- **Severity:** ℹ️ INFO — **Category:** structural
- **Source:** seeding-strategy.md SS-3 row references "L-12..L-1 cohorts"
- **Target:** data-model.md User document — no `signup_cohort` field; no derivation rule
- **Expected:** Either (a) add `User.signup_cohort` field, OR (b) explicit "derive from `handle_created_at` against a `LAUNCH_DATE` constant" rule.
- **Proposed resolution:** Add a one-line derivation rule to data-model.md User block AND seeding-strategy.md SS-3 row. Recommended: derivation from `handle_created_at` against a `LAUNCH_DATE` settings constant — avoids storing redundant data and matches the Phase 5 pattern.
- **Auto-resolvable:** No.
- **Disposition:** DEFER to invite-mechanic cluster pass alongside L3-017 + L4-009.

### Recurring advisory (carry-forward from Run #5 — unchanged)

| ID | Description | Last seen |
|---|---|---|
| DRIFT-L1-001 | W1 activation narrowing | Run #5 |
| DRIFT-L1-002 | Apple Music re-eval threshold drift 15% → 30% (deferred since Run #2) | Run #5 |
| DRIFT-L2-004 / L2-005 | FR trace tags | Run #5 |
| DRIFT-L2-006 | Cluster name enrichment | Run #5 |
| DRIFT-L2-009 | Entity inventory ReviewLike row | Run #5 |
| DRIFT-L3-009 | `/critics` route in plan, no spec backing | Run #5 |
| DRIFT-L3-010 | Handle collision suggestion algorithm incomplete | Run #5 |
| DRIFT-L4-005 | 4 satellite collections in product-spec/data-model.md inventory | Run #5 |
| DRIFT-L7-004..008 | 5 phase-digest orphans (convention class) | Run #5 |
| DRIFT-L7-013 | implementation-log.md orphan (convention class) | Run #5 |

### Next action (Run #6 → Run #7)

Continue Phase 6 implementation. Re-run sync-verify between Phase 6B (code-review) and Phase 7 (full verify). When the invite-mechanic cluster gets sequenced (likely alongside §11/§12 backend wave or the onboarding wave), the three deferred items (DRIFT-L3-017 + DRIFT-L4-009 + DRIFT-L2-019) should be resolved together in a single coherent cluster pass.

---

## Run #5 (2026-05-22, late)

> Phase: 6 (Implementation, in progress) — 42/170 tasks complete
> Drift budget: cosmetic ≤ 20, structural = 0
> **Trigger:** post-§6 Albums + Search backend wave (commit `3e8a602` + shared-types regen `bbd1f4e`) + post-deploy partial-filter fix (commit `66f0403`). First run where Layer 6 (spec ↔ code backward) is meaningful — §6 added the first end-to-end product surfaces (album-detail endpoint + search endpoint).
> **Layers checked:** 7/7 (1, 2, 3, 4, 5, 6, 7). **Skipped:** none.
> **Focus per user prompt:** structural-drift detection on all layers with Layer 6 elevated as the headline; verify Run #4 dispositions still hold; check for §6 fallout the user pre-suspects (partial-filter not in implementation-log; artist_credit data-shape gap; Atlas Search operator follow-up; data-model.md `candidate` semantics).

### Summary

| Severity | Count | Net of recurring | New this run |
|----------|-------|-----------------:|-------------:|
| CRITICAL | 0 | — | — |
| WARNING | 1 | 0 recurring + 1 new | L3-015 (plan.md §11.2.1 report-missing-album URL diverges from code + tasks.md) |
| INFO | 17 | 11 recurring + 6 new | L2-017, L2-018, L3-016, L4-008, L5-006, L7-015 |
| CLEAN | Layer 6 substantially clean (forward-only paths, no backward drift); Run #4 dispositions all holding | — | — |

**Verdict: DRIFT_DETECTED (NOT CRITICAL).** No CRITICAL finding. 1 new WARNING + 6 new INFOs are concentrated on the boundaries §6 opened — and on a Run #4 finding (L4-005 satellite-collection inventory) that the §6 wave touched but didn't fully reconcile. The strict `structural: 0` budget trips again on 7 structural items (1 WARN + 6 INFO); the picture is narrower than Run #4's 7-structural baseline once recurring advisory is excluded.

Structural count: **7** (1 new WARN + 6 new INFO). Cosmetic count: **0**. Strict `structural: 0` budget trips.

### Run #4 disposition — VERIFIED RESOLVED

All 7 Run #4 items applied per commit `aa98618` (sync-fix-run-4 doc propagation):

| Run #4 finding | Verified at |
|----------------|-------------|
| L2-014 (FR-033 propagation) | product-spec/product-spec.md:174 (FR-033 row added); product-spec/README.md:62 ("23 functional requirements active … FR-033"); tasks.md:522 T053a Refs line includes `FR-033` |
| L3-013 (plan §5.1 Protocol names) | plan.md:455-482 — Protocol now reads `get_album_by_mbid` + `get_album_by_external_id`; cover-art as field; `provider_id` dropped; `get_user_library` out of MVP. plan.md:538 services-table row aligned. |
| L3-014 (plan §5.2 rate-limit symbol) | plan.md:487 — "enforced in-class via an `asyncio.Lock` + `time.monotonic()` pacing pair". plan.md:489 — Discogs graceful-disabled-when-token-unset. |
| L4-006 (`discogs_id` → `discogs_release_id`) | product-spec/data-model.md:88, 95, 99, 403 — all `discogs_release_id`. tasks.md:584 T063 description uses `discogs_release_id`. |
| L2-015 (wireframe 01 label) | spec.md:203-204 — "Follow-Critics screen (the new onboarding activation step)". |
| L2-016 (entity count narrative) | spec.md:355-357 ("14 active at MVP") + spec.md:582-583 (mirror). |
| L4-007 (tasks.md FR math) | tasks.md:65 + tasks.md:1588 — "23 active FRs … 28 base (27 originals + FR-033) − 5 deferred". |

### §6 Albums + Search wave — VERIFIED LANDED

| Task | Code/test landing | Notes |
|------|-------------------|-------|
| T063 | `modules/albums/identity.py` + `modules/albums/errors.py` + `Album.candidate` field + `tests/unit/test_albums_identity.py` (8 tests) | `resolve_identity(mbid?, discogs_release_id?, mb_provider, discogs_provider)` → Album; MBID-first; Discogs fallback materialises with `candidate=True`. |
| T064 | `modules/albums/workers.py:refresh_stale_album_metadata` + `workers/main.py` cron registration | arq cron daily 04:00 UTC; cap 100/run; provider shared across runs via `_on_startup`. Code path is `modules/albums/workers.py`, not `workers/album_cache_refresh.py` per tasks.md Paths — inline-noted on tasks.md `[x]` line per locked decision #5. |
| T065 | `modules/albums/workers.py:reconcile_candidate_albums` | arq cron weekly Sun 03:00 UTC; fuzzy artist+title match against MB; threshold 0.8; promotes matched candidates to `MUSICBRAINZ` source. |
| T066 | `modules/albums/editions.py` + `tests/unit/test_albums_editions.py` (11 tests) | `get_editions` + `get_canonical_edition` (earliest year + longest tracklist tiebreak) + `aggregate_ratings` across editions. Known MVP limitation: `Album.mbid` unique constraint collapses editions to 1 row per release-group — documented in module docstring + flagged as follow-up CR. |
| T067 | `modules/albums/routes.py` + `routers/v1.py` mount + `tests/integration/test_album_detail_endpoint.py` (6 tests) | `GET /api/v1/albums/{album_id}` returns `{album, editions, aggregate, my_history, friends, public_reviews}`. Visibility filtered via `can_read_with_relation` adapters; bulk relation resolver minimises Mongo round-trips. |
| T068 | `migrations/atlas_search/albums_index.json` extended + `migrations/README.md` + `tests/unit/test_albums_atlas_index.py` (5 tests) | `lucene.standard` analyzer + edgeNgram autocomplete (2-8) + `foldDiacritics` + `rating_count` field + `scoreDetails.popularity = log1p(rating_count)`. Operator follow-up: apply updated index to dev Atlas cluster via UI/atlas-cli. |
| T069 | `modules/search/routes.py` + `modules/search/service.py` + `routers/v1.py` mount + `tests/integration/test_search_endpoint.py` (7 tests) | `GET /api/v1/search?q=...&type=album&limit=N`. Three-tier: Atlas $search (graceful-degrades on mongomock) → MB → Discogs. Dedupe by mbid OR casefolded `(title, artist)`. Empty result returns `{report_missing_album_url: "/api/v1/reports/missing-album"}` hint pointing at T053a stub. |
| shared-types regen | `packages/shared-types/src/api.ts` (commit `bbd1f4e`) | OpenAPI codegen ran; api.ts updated for the 2 new endpoints; tsc strict clean. |
| partial-filter fix | `Album.Settings.indexes` migrated from `sparse=True` → `partialFilterExpression={field: {$exists: True, $ne: None}}` (commit `66f0403`) | Post-deploy production bug: Pydantic serialises `None` → BSON `null`, sparse-unique indexes both null values, second null insert collides. Fix excludes `null` from the unique constraint. Conftest drops the two indexes post-`init_beanie` since mongomock-motor doesn't honor partial filters. |

### Layer-by-layer

| Layer | Pair | Verdict | Notes |
|-------|------|---------|-------|
| 1 | research ↔ product-spec | recurring only | L1-001 + L1-002 still carried unchanged. No new drift; §6 wave did not touch the research layer. |
| 2 | product-spec ↔ spec.md | **2 NEW INFO** | L2-017 (spec.md "18 active notification types" stale post-CR-001 — should be 14 active per notification-taxonomy + product-spec/README); L2-018 (`Album.candidate` field semantics drift — data-model.md says "candidate album record flagged for admin merge" but code/T063 use it for the Discogs-fallback path with automated T065 reconciliation). Recurring INFO L2-004/005/006/009 unchanged. |
| 3 | spec.md ↔ plan.md | **1 NEW WARN + 1 NEW INFO** | L3-015 (plan §11.2.1 says `POST /api/search/report-missing` but code search-endpoint hint + tasks.md T053a both use `/api/v1/reports/missing-album`); L3-016 (plan §3.1 `albums` row says "`mbid` unique sparse · `discogs_release_id` unique sparse" but code uses `partialFilterExpression` per commit `66f0403` — sparse was the production bug). Recurring INFO L3-009/010 unchanged. |
| 4 | plan.md ↔ tasks.md | **1 NEW INFO** | L4-008 — recurring L4-005 narrowed (the §6 wave's `albums_text_search` Atlas index + `migrations/README.md` are new artifacts neither plan §3.1 inventory nor product-spec/data-model.md indexes table acknowledge). Recurring L4-005 (4 satellite collections inventory) unchanged. |
| 5 | tasks.md ↔ code | **1 NEW INFO** | L5-006 — partial-filter fix (commit `66f0403`) not captured in `implementation-log.md`. Session 8 entry stops at 400/400 tests + the lingering Operator-follow-up bullet for the Atlas index; the post-deploy index migration + conftest drop pattern + bump to 401/401 tests has no Session 8.5 entry. The commit body explains it; the implementation log does not. Also: tasks.md T067/T068/T069 Paths lines reference `tests/integration/test_album_detail.py` / `docs/atlas-search-setup.md` / `tests/integration/test_search.py` but the actual files are `test_album_detail_endpoint.py` / `apps/api/migrations/README.md` / `test_search_endpoint.py` — same path-divergence class as §4 (locked decision #5) but here NOT inline-noted on the `[x]` lines. |
| 6 | spec.md ↔ code | **1 NEW INFO** | First meaningful Layer 6 sweep. L6-001 (response shape advisory) — US-F1 AC mentions "SSR; cover, metadata, tracklist, my history, friends' ratings + Aux'd, public reviews list (sortable), Log + Up Next CTAs, OG meta. Edition selector chip". Backend T067 covers album/tracklist/my_history/friends/public_reviews/editions/aggregate cleanly. The frontend-bound concerns (SSR, OG meta, sort selector, Log/Up Next CTAs) are deferred to T070+ as expected — not drift, but worth marking the surface dependency explicitly. US-F2 AC ("Atlas Search (cached MusicBrainz subset) + live MusicBrainz lookup on cache-miss + Discogs fallback for obscure pressings; ≥3 chars + 200ms debounce; 'Report missing album' link on empty result") is satisfied by T069 (Atlas → MB → Discogs fallback merge with materialise + dedupe + report-missing hint on empty). The ≥3 chars + 200ms debounce are frontend concerns (T071+); the route accepts `q.min_length=1` for forward-compat. FR-005 + FR-010 traceability: clean. FR-033 traceability: spec.md → tasks.md T053a (Refs FR-005;FR-033) → search route's report-missing URL hint (T053a stub) — chain is consistent. **Backward direction substantially clean. No regression-class drift detected.** |
| 7 | cross-link integrity | **1 NEW INFO** | L7-015 — `migrations/README.md` (new this wave) is not indexed by any other markdown doc in the feature folder, mirrors the L7-013 / L7-004..008 phase-digest-orphan convention class. Recurring 5 phase-digest orphans + L7-013 unchanged. |

---

## New findings (Run #5)

### DRIFT-L3-015 — plan §11.2.1 report-missing-album URL diverges from code + tasks.md

| Field | Value |
|-------|-------|
| Layer | 3 (plan.md ↔ code; also plan.md ↔ tasks.md) |
| Direction | Forward (plan → code/tasks) |
| Severity | WARNING |
| Category | structural |
| Source | `plan.md:766` — "Tapping submits a `POST /api/search/report-missing` request that creates a `reports` document with `target_type: 'missing_album'`, `target_id: query_string`, and submitter user id." |
| Target | `apps/api/src/auxd_api/modules/search/routes.py:48` — `_REPORT_MISSING_ALBUM_URL = "/api/v1/reports/missing-album"`; `tasks.md:523` T053a Description — "`POST /api/v1/reports/missing-album` accepts `query` …" |
| Authoritative | `/api/v1/reports/missing-album` per code (currently in the search response hint) + tasks.md T053a (the future endpoint task). |
| Actual | plan.md §11.2.1 narrative still uses the unversioned `/api/search/report-missing` form, which (a) lives outside `/api/v1` (inconsistent with the rest of the API surface) and (b) is conceptually `reports/missing-album` (Report-entity-owned), not `search/report-missing` (search-module-owned). The §13 reading list reference + the §11.2.1 elevation note + the CR-001 changelog row all repeat this stale path. |
| Cross-check | `tasks.md:1588` coverage matrix and `tasks.md:523` T053a path agree on `/api/v1/reports/missing-album`. The search route's `_REPORT_MISSING_ALBUM_URL` constant is the live shape exposed via OpenAPI today. |
| Proposed resolution | Update plan.md:766 to `POST /api/v1/reports/missing-album` (matches code + tasks.md T053a). Optionally also rename the `target_id` semantics: plan currently says "`target_id: query_string`" but T053a stores `query`/`artist`/`title`/`release_year` as separate fields on the Report payload — recommend "`target_id: query_string; additional structured hints in detail/payload`". |

### DRIFT-L2-017 — spec.md "18 active notification types" stale post-CR-001

| Field | Value |
|-------|-------|
| Layer | 2 (spec.md ↔ product-spec/notification-taxonomy.md) |
| Direction | Backward (taxonomy → spec.md narrative) |
| Severity | INFO |
| Category | structural |
| Source | `spec.md:195` (US-G3 AC: "18 active notification types with per-channel toggles"); `spec.md:371` (§7 data-model entity narrative: "Notification, NotificationPreferences — 18 active types"); `spec.md:584` (§13 reading list: "18 active notification types with defaults") |
| Target | `product-spec/notification-taxonomy.md` — 14 active rows (N-001..N-008, N-012..N-017); reserved-gap IDs N-009/N-010/N-011/N-018/N-019/N-020; `product-spec/README.md:64` correctly says "14 notification types active"; `product-spec/user-stories.md:289-290` correctly references "every active notification type from notification-taxonomy.md" + lists reserved-gap IDs explicitly. |
| Actual | spec.md narrative claims 18 active across three locations; the canonical count is 14 active + 6 reserved-gap = 20 IDs allocated. The "18 active" was a v1.3 number reduced by CR-001 (which moved N-009/N-010/N-011 + N-018 to deferred-to-v2 reserved-gap status). README.md already reflects the corrected count; spec.md never caught up. |
| Proposed resolution | Update 3 spec.md locations from "18 active notification types" to "14 active notification types (N-009/N-010/N-011 + N-018 deferred to v2 per CR-001; N-019/N-020 deferred with R3 Lists deferral; IDs preserved as reserved-gap)". |

### DRIFT-L2-018 — `Album.candidate` field semantics diverge between data-model.md and code/T063

| Field | Value |
|-------|-------|
| Layer | 2 (product-spec/data-model.md ↔ code/tasks T063) |
| Direction | Backward (code → data-model.md) |
| Severity | INFO |
| Category | structural (field-meaning) |
| Source | `product-spec/data-model.md:355-359` — "Album identity normalization (load-bearing) … 3. Else (rare — e.g., a user manually typed an album title with no provider hit) → create a 'candidate' album record flagged for **admin merge**." |
| Target | `apps/api/src/auxd_api/modules/albums/models.py:199-204` — "`candidate` marks Discogs-sourced rows that still need MBID reconciliation by the T065 worker"; `apps/api/src/auxd_api/modules/albums/identity.py:122-137` — Discogs path materialises with `candidate=True`; `apps/api/src/auxd_api/modules/albums/workers.py:174-237` — `reconcile_candidate_albums` automatically promotes candidates via fuzzy MBID match (no admin step). Also `product-spec/user-stories.md:249` correctly says "If MusicBrainz MBID is not yet available, the album is created as a `candidate` record (flagged for MBID reconciliation when MusicBrainz catches up)". |
| Actual | data-model.md says "candidate" means "manually-entered album, flagged for admin merge". Code + T063/T065 + S-F1 AC say "candidate" means "Discogs-sourced album awaiting automated MBID reconciliation by the T065 weekly worker". The data-model narrative case (rare manual entry, no provider hit) doesn't currently exist in code at all — manual album creation lands via T053a's future Report flow, not via `resolve_identity`. |
| Proposed resolution | Update data-model.md §"Album identity normalization" step 3 to: "Else if Discogs ID is present → materialise `Album(candidate=True, source=DISCOGS)` to be reconciled by the weekly T065 MBID-reconciliation worker." Also add a brief mention of the new `Album.candidate: bool` field to the Album entity sketch (line 89-114). |

### DRIFT-L3-016 — plan §3.1 `albums` index spec says "unique sparse" but code uses partialFilterExpression

| Field | Value |
|-------|-------|
| Layer | 3 (plan.md ↔ code) + Layer 2 (product-spec/data-model.md ↔ code) |
| Direction | Forward (plan → code) — and post-fix, backward (code → plan) |
| Severity | INFO |
| Category | structural (index-shape) |
| Source | `plan.md:264` — "`albums` … `mbid` unique sparse · `discogs_release_id` unique sparse · Atlas Search index on `title + artist_credit + artists.name`". Same wording in `product-spec/data-model.md:402-404`. |
| Target | `apps/api/src/auxd_api/modules/albums/models.py:215-237` — both indexes now use `partialFilterExpression={field: {$exists: True, $ne: None}}` per commit `66f0403`. |
| Actual | The original plan + data-model wording is the bug that was caught in prod: sparse-unique still indexes null values (because Pydantic emits `None` → BSON `null`, which is *present*, not *missing*), and the second null insert collides on the unique constraint. The fix uses `partialFilterExpression` to exclude both missing and null. The plan + data-model wording reflects the *pre-fix* design intent; code now reflects the *post-fix* shape. |
| Cross-check | Conftest at `apps/api/tests/conftest.py:43-61` drops both indexes post-`init_beanie` because mongomock-motor doesn't honor `partialFilterExpression` — a real-MongoDB testcontainers smoke test is the documented mitigation (per commit `66f0403` body). |
| Proposed resolution | Update plan.md:264 + product-spec/data-model.md:402-403 from "unique sparse" to "unique partial-filter (`{$exists: true, $ne: null}`) — sparse was insufficient because Pydantic serialises `None` to BSON `null`". The decision row should also be captured in `product-spec/decision-log.md` as DM-6 ("Album identity index shape — partialFilter not sparse") for v2 forward-compat. |

### DRIFT-L4-008 — §6 wave artifacts not in plan §3.1 / data-model.md inventory tables

| Field | Value |
|-------|-------|
| Layer | 4 (plan.md ↔ tasks.md) + Layer 2 (product-spec/data-model.md) |
| Direction | Forward (tasks/code → plan + data-model) |
| Severity | INFO |
| Category | structural (inventory completeness) |
| Source | `apps/api/migrations/atlas_search/albums_index.json` (T068, extended this wave); `apps/api/migrations/README.md` (T068, NEW this wave); `Album.candidate: bool` field (T063, NEW this wave) |
| Target | `plan.md:264` (`albums` indexes row); `product-spec/data-model.md:89-114` (Album sketch); `product-spec/data-model.md:395-419` (Indexes table) |
| Actual | The new `Album.candidate` field is invisible to data-model.md's Album sketch. The Atlas Search index `albums_text_search` has a `rating_count` field + `scoreDetails.popularity = log1p(rating_count)` block — neither shows up in plan.md or data-model.md's index narrative. plan.md §3.1 still says "Atlas Search index on `title + artist_credit + artists.name`" — accurate as far as it goes, but understates the actual shape now in production. |
| Cross-check | Narrows the recurring L4-005 finding ("4 satellite collections missing from product-spec/data-model.md inventory") rather than replacing it — L4-005 still tracks FollowRequest + ReviewEditHistory + FailedEmail; L4-008 tracks the §6 wave artifacts. |
| Proposed resolution | Add `Album.candidate: bool` to the Album sketch in data-model.md:89-114. Update plan.md:264's `albums` indexes row to mention the popularity-boost index field. Optionally add a "Migration artifacts" subsection to plan §3 or §11 enumerating `migrations/atlas_search/albums_index.json` + `migrations/README.md` so future readers can find them from the plan. |

### DRIFT-L5-006 — partial-filter fix (commit `66f0403`) not in implementation-log.md Session 8

| Field | Value |
|-------|-------|
| Layer | 5 (tasks.md/code ↔ implementation-log.md) |
| Direction | Backward (code commit → log) |
| Severity | INFO |
| Category | structural (audit trail) |
| Source | commit `66f0403` body — "Found in prod after §6 wave deploy: GET /api/v1/search?q=... → HTTP 500 with DuplicateKeyError … Fix: change both mbid_1 and discogs_release_id_1 unique indexes from `sparse=True` to `partialFilterExpression={field: {$exists: true, $ne: null}}`." |
| Target | `features/001-auxd-mvp/implementation-log.md` — last entry is Session 8 mini-verify at 400/400 + the lingering "Operator follow-up: apply Atlas Search index" bullet. Test count post-fix is 401/401 per commit body; the log still says 400/400. |
| Actual | The 66f0403 commit is a Session-8-follow-up bug-fix-after-deploy event that is materially relevant to: (a) the partial-filter design decision (DM-6 candidate), (b) the conftest drop pattern + v1.x real-MongoDB-testcontainers note, (c) the 400→401 test count. None of those land in the implementation-log. Future readers reconstructing Session 8 from the log alone will see "shipped, 400/400 green" and miss the post-deploy production incident + fix. |
| Cross-check | tasks.md doesn't acknowledge it either (T022 + T063 + the workers/T064/T065 all stay `[x]` with their original Session-8 notes). T067 + T069 paths still reference test file basenames that don't match the actual landed files (`test_album_detail.py` vs `test_album_detail_endpoint.py`; `test_search.py` vs `test_search_endpoint.py`). T068 references `docs/atlas-search-setup.md` not `apps/api/migrations/README.md`. |
| Proposed resolution | Add a "Session 8.5 — Post-deploy partial-filter fix (2026-05-23 morning)" subsection to implementation-log.md capturing (a) the production incident shape, (b) the partial-filter fix, (c) the conftest drop pattern + the real-MongoDB testcontainers v1.x note, (d) the 401/401 new test count. Optionally also add inline `[x]`-line notes to T067/T068/T069 acknowledging the test/doc path divergences (parallel to the §4 wave's inline notes on T049/T064/etc.). |

### DRIFT-L7-015 — `apps/api/migrations/README.md` is not indexed by any other doc

| Field | Value |
|-------|-------|
| Layer | 7 (cross-link integrity) |
| Direction | Internal |
| Severity | INFO |
| Category | structural (convention orphan) |
| Source | `apps/api/migrations/README.md` (NEW this wave) — documents the manual UI + `atlas-cli` apply paths for the `albums_text_search` Atlas Search index |
| Target | `apps/api/migrations/migration-plan.md` — the parent migration doc — does not link to `apps/api/migrations/README.md`. Likewise the feature-level docs (plan.md §11.1, tasks.md T068 Done criterion, implementation-log Session 8 Operator-follow-up) all reference "the README" but as a path, not a markdown link. |
| Actual | Same convention class as L7-004..008 (5 phase-digest orphans) + L7-013 (implementation-log orphan). Not a user-visible defect; flagged because the runbook for applying the Atlas index lives only in the new README and the discoverability path from plan → migrations is currently a grep, not a link. |
| Proposed resolution | Add a markdown link to `apps/api/migrations/README.md` from `apps/api/migrations/migration-plan.md` §"Atlas Search indexes" (or equivalent). Optionally also link it from plan.md §11.1 + tasks.md T068 Done line. |

---

## Drift table

| ID | Layer | Severity | Category | Title | Status |
|----|:-:|:-:|:-:|---|---|
| L3-015 | 3 | WARN | struct | plan §11.2.1 `POST /api/search/report-missing` vs code/tasks `/api/v1/reports/missing-album` | NEW |
| L2-017 | 2 | INFO | struct | spec.md "18 active notification types" stale post-CR-001 (should be 14 active) | NEW |
| L2-018 | 2 | INFO | struct | `Album.candidate` field semantics drift — data-model.md says "admin merge", code/T063 say "T065 reconciliation" | NEW |
| L3-016 | 3 | INFO | struct | plan §3.1 + data-model.md indexes "unique sparse" vs code `partialFilterExpression` (post-`66f0403` fix) | NEW |
| L4-008 | 4 | INFO | struct | §6 wave artifacts (`Album.candidate`, Atlas index `rating_count` field, migrations/README.md) not in plan §3.1 + data-model.md inventory | NEW |
| L5-006 | 5 | INFO | struct | partial-filter fix (commit `66f0403`) not in implementation-log.md; also tasks.md T067/T068/T069 Paths divergences not inline-noted | NEW |
| L6-001 | 6 | INFO | advisory | First Layer-6 sweep: §6 backend endpoints satisfy US-F1/US-F2 backward path; frontend-bound concerns (SSR/OG meta/sort selector/debounce) deferred to T070+ — not drift, surface marker | NEW (advisory) |
| L7-015 | 7 | INFO | struct | `apps/api/migrations/README.md` orphan (no markdown link from migration-plan.md or plan.md) | NEW |
| L1-001 | 1 | INFO | struct | W1 activation definition narrowed | RECURRING |
| L1-002 | 1 | INFO | struct | Apple Music re-eval threshold 15% → 30% | RECURRING (deferred) |
| L2-004 | 2 | INFO | struct | FR-003 trace tag US-A3 → US-A2 (FR-003 DEFERRED-TO-V2 — moot candidate) | RECURRING (CR-001 mooted) |
| L2-005 | 2 | INFO | struct | FR-027 trace tag US-G2 removal (FR-027 DEFERRED-TO-V2 — moot candidate) | RECURRING (CR-001 mooted) |
| L2-006 | 2 | INFO | struct | Cluster name enrichment | RECURRING |
| L2-009 | 2 | INFO | struct | Entity inventory ReviewLike row | RECURRING (partially mooted) |
| L3-009 | 3 | INFO | struct | /critics route in plan, not spec | RECURRING |
| L3-010 | 3 | INFO | struct | Handle collision suggestion incomplete | RECURRING |
| L4-005 | 4 | INFO | struct | 4 satellite collections (FollowRequest + ReviewEditHistory + FailedEmail + NotificationPreferences-embedded) still missing from product-spec/data-model.md inventory | RECURRING (narrowed by L4-008) |
| L7-004..008 | 7 | INFO | struct | 5 phase-digest orphans | RECURRING (convention class) |
| L7-013 | 7 | INFO | struct | implementation-log.md orphan | RECURRING (convention class) |

---

## Verdict

**DRIFT_DETECTED (NOT CRITICAL).**

- 0 individual finding is CRITICAL-severity. No data-loss / runtime regression. Test suite is green (401/401 pass + 3 skip per commit `66f0403`).
- Structural count: **7** (1 new structural WARN + 6 new structural INFO). With strict `structural: 0` budget, the budget rule trips.
- Cosmetic count: **0** — well within the 20 budget.
- Net drift narrowed materially since Run #4 (was 7 structural items with 4 WARN; now 7 structural items with 1 WARN). The §6 wave's headline edge — the partial-filter production-bug fix — landed cleanly and is properly captured in the commit body; the implementation-log + plan + data-model inventory updates are the only places it didn't propagate.
- Layer 6 is meaningful for the first time. Backward direction is substantially clean: US-F1 + US-F2 + FR-005 + FR-010 + FR-033 traceability through `/api/v1/albums/{album_id}` + `/api/v1/search` + the future T053a stub is well-formed. The frontend-bound parts of those stories (SSR, OG meta, sort UI, debounce) are still pending and properly out-of-scope for this run.
- Recommended disposition (carrying forward Run #2/#3/#4's `applied_split_with_override` pattern):
  1. Apply **L3-015** (plan §11.2.1 report-missing URL alignment) — single highest-value cleanup; closes the only WARN.
  2. Apply **L3-016** + **L4-008** as a single index-shape + inventory commit — both touch plan.md §3.1 and data-model.md indexes-table + Album sketch; the partial-filter shape change is also a candidate for a new DM-6 decision-log entry.
  3. Apply **L2-017** (notification-count narrative) + **L2-018** (`Album.candidate` semantics) — both pure documentation cleanup.
  4. Apply **L5-006** (Session 8.5 implementation-log entry) — captures the post-deploy production incident + fix + 401/401 test count; also wraps up the small tasks.md path-divergence notes for T067/T068/T069 in the same edit.
  5. **L7-015** (migration README orphan) is opportunistic — add a single markdown link from `migrations/migration-plan.md` and the convention class shrinks by 1.
  6. **L6-001** is advisory (forward surface marker) — no action; will fold back in once frontend wave (T070+) lands and Layer 6 backward gets a second pass.
  7. Recurring advisory (L1-001/L1-002/L2-004/005/006/009/L3-009/010/L4-005/L7-004..008/L7-013) — skipped as in Runs #2/#3/#4. Mootness of L2-004/L2-005 since CR-001 is a candidate for explicit retirement; recommend grouping into a single "retire-as-moot" disposition in the parent agent's approval flow.
  8. Override on the budget rule (structural ≠ 0) as in Runs #2/#3/#4 — the picture is narrow, well-scoped, and all WARN/INFO items are documentation drift, not runtime drift.

### Outlook to Run #6

If L3-015 + L3-016 + L4-008 + L2-017 + L2-018 + L5-006 + L7-015 land (1 WARN + 6 INFO), Run #6 structural count projects to **~3** (4 satellite collections inventory gap if not folded into L4-008's data-model.md edit, + L7-004..008 phase-digest orphans + L7-013 if convention is not formalised, + advisory L6-001 surface marker). Layer 6 backward becomes more meaningful as soon as frontend wave (T070+ Next.js scaffold + album-detail page + search UI + cover-art proxy) lands. Frontend wave will also retire L6-001 advisory once SSR / OG meta / sort UI / debounce are wired.

**Honest shape assessment: the artifact set is in a coherent shape post-§6.** All the new structural items are documentation-tier drift — narratives that didn't catch up with the §6 wave's code and the post-deploy partial-filter fix. No misalignment requires human-in-the-loop resolution before §3 / §5 begin. The §6 wave proved the data-layer + provider-scaffolding + route-pattern + visibility-filtering composition all hang together; the next wave can proceed.

---

## Sync History

| Run | Date | Layers | CRITICAL | WARNING | INFO | Initial verdict | Final disposition |
|-----|------|--------|---------:|--------:|-----:|------------------|-------------------|
| #1 | 2026-05-21 | 5/7 | 0 | 19 | 14 | CRITICAL DRIFT (budget rule) | RESOLVED WITH OVERRIDE — 10 applied / 10 backlogged / 2 deferred / 14 INFO skipped |
| #2 | 2026-05-22 | 6/7 | 0 | 3 | 22 | DRIFT_DETECTED | RESOLVED WITH OVERRIDE — 10 applied (incl. L1-003 OAuth widening) / 13 advisory recurring / gate overridden |
| #3 | 2026-05-22 | 6/7 | 0 | 2 | 17 | DRIFT_DETECTED | RESOLVED_WITH_OVERRIDE @ 2026-05-22T22:30:00Z — 6 inline cleanups applied (L5-001..005 + L7-014); 13 advisory recurring skipped; gate overridden |
| #4 | 2026-05-22 | 6/7 | 0 | 4 | 14 | DRIFT_DETECTED | RESOLVED_WITH_OVERRIDE @ 2026-05-23T01:00:00Z — applied_split_with_override (L2-014/015/016 + L3-013/014 + L4-006/007 applied inline via commit `aa98618`); 11 advisory recurring skipped |
| #5 | 2026-05-22 | 7/7 | 0 | 1 | 17 | DRIFT_DETECTED | TBD — read-only scan; user to disposition L3-015 (1 WARN) + L2-017/L2-018/L3-016/L4-008/L5-006/L6-001/L7-015 (7 new INFO + 11 recurring) |

---

## Disposition checkboxes (user-driven)

> Run #5 is a read-only scan. The skill explicitly does NOT modify any artifact. Disposition decisions go below; an interactive follow-up should apply them and update `.forge-status.yml` + `sync-fix-list.md`.

- [ ] **L3-015** — Update plan.md:766 report-missing-album URL `POST /api/search/report-missing` → `POST /api/v1/reports/missing-album` (matches code + tasks.md T053a). Optionally clarify `target_id` semantics to acknowledge T053a's structured payload fields.
- [ ] **L2-017** — Reconcile spec.md narrative counts (3 locations: US-G3 AC, §7 data-model, §13 reading list) from "18 active notification types" to "14 active notification types (with N-009/N-010/N-011/N-018/N-019/N-020 reserved-gap)"; aligns with notification-taxonomy.md + product-spec/README.md.
- [ ] **L2-018** — Update data-model.md §"Album identity normalization" step 3 from "manually-entered → admin merge" to "Discogs-sourced → automated T065 reconciliation"; add `Album.candidate: bool` to the Album sketch.
- [ ] **L3-016** — Update plan.md:264 + data-model.md:402-403 from "unique sparse" to "unique partial-filter ({$exists, $ne: null}) — sparse was insufficient because Pydantic serialises None to BSON null"; add new DM-6 decision-log entry capturing the partial-filter design.
- [ ] **L4-008** — Add `Album.candidate` to data-model.md Album sketch; extend plan.md:264 to mention the Atlas index's `rating_count` + popularity-boost. Bundles cleanly with L3-016 in a single index-shape commit.
- [ ] **L5-006** — Add "Session 8.5 — Post-deploy partial-filter fix" subsection to implementation-log.md (incident → fix → conftest drop pattern → 401/401 test count → v1.x testcontainers note). Add inline-divergence notes to tasks.md T067/T068/T069 path lines per locked decision #5 pattern.
- [ ] **L7-015** — Link `apps/api/migrations/README.md` from `apps/api/migrations/migration-plan.md`. Optionally also from plan.md §11.1 + tasks.md T068 Done line.
- [ ] **L6-001** — (Advisory, no action) — Frontend-bound surface marker; revisit in Run #6 once T070+ lands.
- [ ] (recurring) **L4-005** — Add FollowRequest + ReviewEditHistory + FailedEmail to product-spec/data-model.md inventory table; bundles cleanly with L4-008.
- [ ] (recurring, mootness candidate) **L2-004 / L2-005** — Retire as moot since CR-001 (FR-003 + FR-027 both DEFERRED-TO-V2; FR-row tags moot when the FR itself is deferred).
- [ ] (recurring, convention class) **L7-004..008 + L7-013 + L7-015** — Consider a single "phase-digest + implementation-log + migrations-README convention call" disposition: either index all from feature README, or formally exempt the convention class.
