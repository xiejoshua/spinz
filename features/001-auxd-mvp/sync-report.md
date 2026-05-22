# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #3 — 2026-05-22**
> Phase: 6 (Implementation, in progress) — 22/183 tasks complete
> Drift budget: cosmetic ≤ 20, structural = 0

---

## Run #3 (2026-05-22)

> Layers checked: 6/7 (1, 2, 3, 4, 5, 7) | Skipped: Layer 6 (spec ↔ code) — backward direction premature; only data-layer code (no business logic / endpoints) has landed.
> Layer 5 now exercises **22 completed tasks** with concrete file paths (vs Run #2's 4).

### Summary

| Severity | Count | Net of recurring | New this run |
|----------|-------|-----------------:|-------------:|
| ❌ CRITICAL | 0 | — | — |
| ⚠️ WARNING | 2 | 0 recurring + 2 new | L5-001, L5-002 (Layer 5 model-vs-task field drift) |
| ℹ️ INFO | 17 | 13 recurring + 4 new | L5-003, L5-004, L5-005, L7-014 |
| ✅ CLEAN | Layers 1, 2, 3, 4 (no new findings); Layer 7 substantially clean | — | — |

**Verdict: DRIFT_DETECTED (NOT CRITICAL).** No individual finding is CRITICAL-severity. New WARNINGS are Layer 5 model-shape drift where tasks.md task descriptions promised fields the corresponding Beanie Documents don't yet implement (T021 User, T024 BacklogItem). These are pre-service-layer model edits, not runtime regressions. All other layers held — Run #2 inline cleanups all verified intact; no new drift in spec ↔ plan ↔ tasks.

Structural count: **5** (4 new + 1 partially-recurring satellite collections). Cosmetic count: **2** (the rest are advisory recurring INFO). Strict `structural: 0` budget still trips, but the picture is narrower than Run #2 (24 → 5).

### Run #2 disposition — VERIFIED

All 10 Run #2 inline cleanups hold post-Wave-A/Wave-B:

| Item | Verified |
|------|----------|
| L2-007 (PS S-G3 "18 active") | ✅ user-stories.md:284 reads "18 active types ... N-019/N-020 reserved-gap" |
| L2-010 (spec.md "16 entities") | ✅ spec.md:307 reads "16 active entities ... count reconciled with ReviewLike in sync-verify Run #2" |
| L2-011 (data-model.md `likes_count`) | ✅ DM-3 + DM-5 narrative reads `likes_count` |
| L2-012 (J2/J3 "Aux row"/"Like action") | ✅ user-journeys.md J2 + J3 free of "heart" terminology |
| L2-013 (digest.md body refreshed) | ✅ product-spec/digest.md body counts 30/8/18/16 |
| L3-011 (typo `action_report`) | ✅ plan.md §6 no `actiion_report` |
| L3-012 (auth/ module placement) | ✅ plan.md §4.6 unambiguous |
| L7-011 (S-B6 anchor) | ✅ user-stories.md:118 links to "Notification types" + "Anti-spam guardrails" headings |
| L7-012 (long-form #drift-l2-003 slug) | ✅ spec.md:122 uses `#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30` |
| L1-003 (OAuth scopes widened 3→5) | ✅ 5 scopes (`user-read-email`, `user-read-private`, `user-read-recently-played`, `user-read-currently-playing`, `user-library-read`) consistent across spec.md:35, spec.md:196 (FR-002), plan.md:393-397, product-spec.md:132 + Q22 |

### Run #1 backlog disposition — STILL VERIFIED LANDED

All 10 Run #1 backlog items remain landed (verified by code re-scan, not just plan presence):

| ID | Where it lives now |
|----|---------------------|
| L3-001 endpoint rate-limit | plan.md §4.5 |
| L3-002 follow-request queue | plan.md §3.1 (`follow_requests` row) + social/models.py FollowRequest Document ✅ landed Wave B |
| L3-003 review_edit_history | plan.md §3.1 + reviews/models.py ReviewEditHistory Document (90d TTL on edited_at) ✅ landed Wave B |
| L3-004 axe-core CI gate | plan.md §16.4 + §16.5 |
| L3-006 missing_album target_type | moderation/models.py ReportTargetType.MISSING_ALBUM ✅ landed Wave B |
| L3-007 Settings → Integrations | plan.md §1.2 + §4.6 + §6 auth |
| L4-001 OTel task | T015a present + apps/api/src/auxd_api/lib/otel.py landed (Session 2) |
| L4-002 mongodump | T010a present + .github/workflows/backup-mongo.yml landed Wave A |
| L4-003 PostMark/Resend failure mode | notifications/models.py FailedEmail Document landed Wave B |
| L4-004 Redis fail-mode | T013 amended; service-layer landing pending |

### Layer-by-layer

| Layer | Pair | Verdict | Notes |
|-------|------|---------|-------|
| 1 | research ↔ product-spec | ⏭️ recurring only | L1-001 (W1 activation) + L1-002 (Apple Music 15% → 30%) carried unchanged. No new drift. |
| 2 | product-spec ↔ spec.md | ⏭️ recurring only | L2-004/005/006/009 carried. No new drift. |
| 3 | spec.md ↔ plan.md | ⏭️ recurring only | L3-009 (/critics) + L3-010 (handle suggestions) carried. No new drift. |
| 4 | plan.md ↔ tasks.md | ✅ partial improvement on L4-005 | follow_requests + review_edit_history now in plan §3.1 (good); satellite list still incomplete in product-spec/data-model.md inventory (handle_redirects, gdpr_audit_log, feed_buckets). |
| 5 | tasks.md ↔ code | ⚠️ 2 NEW WARN + 3 NEW INFO | **The headline finding of this run.** Several T021 + T024 + T027 field/index promises don't match landed code. |
| 6 | spec.md ↔ code | ⏭️ SKIPPED | Backward-only would be premature — no services / endpoints / UI yet. |
| 7 | cross-link integrity | ⚠️ 1 NEW INFO | New: L7-014 duplicate `## Session 3` header in implementation-log.md. Recurring 5 phase-digest orphans + L7-013 implementation-log orphan unchanged. |

---

## New findings (Run #3)

### DRIFT-L5-001 — T021 User Document missing 5 fields promised by task description

| Field | Value |
|-------|-------|
| Layer | 5 (tasks.md ↔ code) |
| Direction | Forward (tasks → code) |
| Severity | WARNING |
| Category | structural |
| Source | `tasks.md:239` T021 Description: "Includes `auto_prompt_enabled`, `auto_prompt_push_enabled`, **`default_entry_visibility`**, **`default_backlog_visibility`**, **`keep_backlog_after_log`**, **`last_handle_change`**, `created_at`, `deletion_scheduled_for`, **`session_version`**, `status`" |
| Target | `apps/api/src/auxd_api/modules/users/models.py:108-187` |
| Expected | Fields `default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log`, `last_handle_change`, `session_version` present on the `User` model |
| Actual | None of the 5 are present. Code uses `handle_changed_at` instead of `last_handle_change`. The other 4 are absent entirely (also absent from `test_users_model.py`). |
| Cross-check | `product-spec/data-model.md:49-51` confirms `default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log` as spec-level fields on User. |
| Proposed resolution | Either (a) add the 5 missing fields to `User` (preferred — spec + task both call for them; needed by US-G1 default-visibility behavior and FR-029 handle policy enforcement); or (b) document in implementation-log.md why they were deferred to a follow-up task and update the T021 description accordingly. |

### DRIFT-L5-002 — T024 BacklogItem missing `per_item_visibility` + field-name drift `notes` → `note`

| Field | Value |
|-------|-------|
| Layer | 5 (tasks.md ↔ code) |
| Direction | Forward (tasks → code) |
| Severity | WARNING |
| Category | structural |
| Source | `tasks.md:263` T024 Description: "BacklogItem with `position`, **`per_item_visibility`**, **`notes`**" + `plan.md:256` §3.1 `backlog_items` row notes "Per-album visibility override" |
| Target | `apps/api/src/auxd_api/modules/backlog/models.py:52-79` (BacklogItem) |
| Expected | `per_item_visibility: Visibility` field + `notes: str \| None` field |
| Actual | `per_item_visibility` absent. Field is `note: str \| None` (singular), not `notes`. Tests reference only `note` (test_backlog_models.py:101-117). |
| Proposed resolution | Add `per_item_visibility: Visibility \| None = None` (None means "inherit from Backlog default"). Rename `note` → `notes` OR update tasks.md T024 description + plan.md §3.1 to match `note` singular. The visibility override is the structurally important half — it's the Per-album visibility override called out in plan §3.1; renaming `note`/`notes` is cosmetic. |

### DRIFT-L5-003 — T024 BacklogItem compound index not unique

| Field | Value |
|-------|-------|
| Layer | 5 (tasks.md ↔ code) |
| Direction | Forward (status notes → code) |
| Severity | INFO |
| Category | structural |
| Source | `.forge-status.yml` T024 note: "BacklogItem with position (**compound unique on backlog_id+album_id**)" |
| Target | `apps/api/src/auxd_api/modules/backlog/models.py:74-78` |
| Expected | `IndexModel([("backlog_id", ASCENDING), ("album_id", ASCENDING)], unique=True)` |
| Actual | Index `(backlog_id, position)` (non-unique) + `(album_id, backlog_id)` (non-unique). No uniqueness anywhere preventing the same album appearing twice in one backlog. |
| Proposed resolution | Either (a) add unique compound `(backlog_id, album_id)` (matches the status-note claim and is the natural "no dup album in one backlog" invariant); or (b) defer the uniqueness check to the service-layer add path and update the status note. Plan.md §3.1 does NOT mandate uniqueness, so this is a structural-but-low-stakes call. |

### DRIFT-L5-004 — User field-name drift (cosmetic naming)

| Field | Value |
|-------|-------|
| Layer | 5 (data-model.md ↔ code) |
| Direction | Forward |
| Severity | INFO |
| Category | structural |
| Source | `product-spec/data-model.md:48,54` |
| Target | `apps/api/src/auxd_api/modules/users/models.py:141,148-149` |
| Field drifts | `is_private_profile` (spec) → `private_profile` (code); `last_login_at` (spec) → `last_seen_at` (code); `last_handle_change` (spec + tasks) → `handle_changed_at` (code). |
| Proposed resolution | Pick one naming and align across data-model.md, tasks.md T021, and the model. `last_seen_at` is the more accurate of the pair (the field updates on activity, not just login); `handle_changed_at` is symmetric with `created_at`. Recommend aligning spec to code, since code names are more accurate. |

### DRIFT-L5-005 — T027 CriticSeed field + index drift

| Field | Value |
|-------|-------|
| Layer | 5 (tasks/spec ↔ code) |
| Direction | Forward |
| Severity | INFO |
| Category | structural |
| Source | `.forge-status.yml` T027 note: "CriticSeed (unique on user_id partial active=True; **priority/category/description**)" + `product-spec/data-model.md:294-301` CriticSeed sketch shows `category`, `description` |
| Target | `apps/api/src/auxd_api/modules/seeding/models.py:77-118` |
| Expected per spec | `category` enum + `description` field; unique on user_id with `active=True` partial filter |
| Actual | Fields are `genre_signature: list[str]`, `public_bio: str \| None`, `notes: str \| None`. Indexes: plain `unique=True` on user_id (no partial filter) + separate partial-on-active index. |
| Proposed resolution | Two-part fix: (a) either re-name `genre_signature`/`public_bio` to `category`/`description` to match spec OR update data-model.md to track the richer code shape; (b) merge the two user_id indexes into one `unique=True, partialFilterExpression={"active": True}` if the intent is "one active critic-seed per user". |

### DRIFT-L7-014 — Duplicate `## Session 3` header in implementation-log.md

| Field | Value |
|-------|-------|
| Layer | 7 (cross-link integrity) |
| Severity | INFO |
| Category | cosmetic |
| Source | `features/001-auxd-mvp/implementation-log.md:105, 155` |
| Issue | Both line 105 ("Infra-decision swaps") and line 155 ("§0 closeout + backend data layer (Wave A + Wave B)") use `## Session 3`. The second appears to be Session 4. |
| Proposed resolution | Renumber line 155 to `## Session 4 — 2026-05-22 evening — §0 closeout + backend data layer (Wave A + Wave B)`. Also update `.forge-status.yml` `session_count: 3` to `4`. |

---

## Recurring advisory (carried from Run #1 + Run #2)

Tally only — these items are tracked as known-advisory by prior gate-override decisions. Their presence does NOT count as new drift in Run #3.

| Layer | Items | Notes |
|-------|-------|-------|
| 1 | L1-001 (W1 activation) · L1-002 (Apple Music threshold) | L1-002 was deferred in Run #2 — still unresolved. |
| 2 | L2-004 · L2-005 (FR trace tags) · L2-006 (cluster names) · L2-009 (entity inventory ReviewLike — partially mooted by Run #2 L2-010) | Stable. |
| 3 | L3-009 (/critics route) · L3-010 (handle suggestion algorithm) | Stable. |
| 4 | L4-005 (satellite collections) — **partial progress**: plan.md §3.1 now includes follow_requests + review_edit_history; product-spec/data-model.md inventory still missing FollowRequest + ReviewEditHistory + FailedEmail entries. | Run #3 narrows the gap. |
| 7 | L7-004..008 (5 phase-digest orphans) · L7-013 (implementation-log.md orphan) | Same convention question. |

**Recurring count carried: 13 items (unchanged tally vs Run #2).**

---

## Resolved since Run #2

None of the open advisory items were closed organically in this window. Wave A + Wave B work focused on landing the data layer, not on metadata cleanup.

**Resolved count this run: 0.**

---

## What's CLEAN in Run #3

- ✅ All 22 completed tasks (T001, T003, T004, T008, T009, T010, T010a, T012, T014, T015, T015a, T016, T017, T018, T021–T027, T029) have landed code at the declared paths.
- ✅ 17 Beanie Documents registered in `ALL_DOCUMENT_MODELS` (single source of truth; conftest.py imports it).
- ✅ Lifespan order honors P5: `init_db` → `init_sentry` → `init_otel` (main.py:35-41).
- ✅ Atlas Search index JSON at `apps/api/migrations/atlas_search/albums_index.json` matches plan §11.1 (title + artist_credit + artists.name + popularity_score).
- ✅ DiaryEntry.auxed bool present (R3 Aux/Like split honored).
- ✅ Review.reactions.likes_count + ReviewLike compound unique (review_id, user_id).
- ✅ ReviewEditHistory 90d TTL on edited_at (FR-030 + sync-fix L3-003).
- ✅ FollowRequest separate from Follow (sync-fix L3-002 + US-G2 infra).
- ✅ Block.reason enum + cascade-on-block correctly deferred to T101 service layer (intentional model-only landing).
- ✅ NotificationType enum has exactly 18 active values (N-001 through N-018); N-019/N-020 reserved-gap respected.
- ✅ Report.target_type enum includes `MISSING_ALBUM` (sync-fix L3-006).
- ✅ FailedEmail Document landed for T135 write target (sync-fix L4-003).
- ✅ JustFinishedPrompt TTL partial filter scoped to `state=pending` (24h expiry); LOGGED/DISMISSED rows retained for 30-day cooldown + attribution.
- ✅ All 3 deploy workflows (deploy-api.yml, synthetic.yml, backup-mongo.yml) match T009/T010/T010a descriptions.
- ✅ Aux/Like split clean across all docs.
- ✅ Brand rename clean (0 spinz/Spinz residuals in features/ or apps/).
- ✅ Run #2 anchor fixes hold (`#n-018` → real headings; long-form `#drift-l2-003-…` slug).
- ✅ Spotify OAuth scopes still 5 across all 4 propagated files (sync-fix Run #2 L1-003).

---

## Drift items table

| ID | Layer | Sev | Cat | Title | Status |
|----|-------|-----|-----|-------|--------|
| L5-001 | 5 | WARN | struct | T021 User missing 5 promised fields | NEW |
| L5-002 | 5 | WARN | struct | T024 BacklogItem missing per_item_visibility + note/notes drift | NEW |
| L5-003 | 5 | INFO | struct | T024 BacklogItem compound index not unique | NEW |
| L5-004 | 5 | INFO | struct | User field-name drift (private_profile / last_seen_at / handle_changed_at) | NEW |
| L5-005 | 5 | INFO | struct | T027 CriticSeed field + index drift | NEW |
| L7-014 | 7 | INFO | cos | Duplicate ## Session 3 header in implementation-log.md | NEW |
| L1-001 | 1 | INFO | struct | W1 activation definition narrowed | RECURRING |
| L1-002 | 1 | INFO | struct | Apple Music re-eval threshold 15% → 30% | RECURRING (deferred Run #2) |
| L2-004 | 2 | INFO | struct | FR-003 trace tag US-A3 → US-A2 | RECURRING |
| L2-005 | 2 | INFO | struct | FR-027 trace tag US-G2 removal | RECURRING |
| L2-006 | 2 | INFO | struct | Cluster name enrichment | RECURRING |
| L2-009 | 2 | INFO | struct | Entity inventory ReviewLike row | RECURRING (partially mooted) |
| L3-009 | 3 | INFO | struct | /critics route in plan, not spec | RECURRING |
| L3-010 | 3 | INFO | struct | Handle collision suggestion incomplete | RECURRING |
| L4-005 | 4 | INFO | cos | Satellite collections in §3.1 inventory | RECURRING (narrowed) |
| L7-004..008 | 7 | INFO | struct | 5 phase-digest orphans | RECURRING (convention) |
| L7-013 | 7 | INFO | struct | implementation-log.md orphan | RECURRING (convention) |

---

## Verdict

**DRIFT_DETECTED (NOT CRITICAL).**

- 0 individual finding is CRITICAL-severity.
- Structural count: **5** (4 new structural + L4-005 satellite collections partial-recurring). With strict `structural: 0` budget, the budget-rule trips.
- Cosmetic count: **2** — well within the 20 budget.
- New drift in Run #3 is concentrated entirely in Layer 5 — tasks.md task descriptions promised User/BacklogItem/CriticSeed fields that the landed Beanie Documents don't yet implement. Either the models need to grow OR the task descriptions need to be reconciled.
- Recommended disposition: split L5-001 + L5-002 into model-amendment commits before the service layer starts (services will read these fields). L5-003/L5-004/L5-005 can be applied opportunistically or grouped into a single "model field-name reconciliation" PR.

### Outlook to Run #4

If L5-001/L5-002 are applied (User adds 5 fields; BacklogItem adds per_item_visibility), Run #4 structural count projects to ~3 (L4-005 inventory cleanup + 2 cosmetic naming items). Layer 6 (spec ↔ code) becomes meaningful once endpoint code lands (cluster §3+ tasks in tasks.md — first endpoints around T040+).

---

## Sync History

| Run | Date | Layers | CRITICAL | WARNING | INFO | Initial verdict | Final disposition |
|-----|------|--------|---------:|--------:|-----:|------------------|-------------------|
| #1 | 2026-05-21 | 5/7 | 0 | 19 | 14 | CRITICAL DRIFT (budget rule) | RESOLVED WITH OVERRIDE — 10 applied / 10 backlogged / 2 deferred / 14 INFO skipped |
| #2 | 2026-05-22 | 6/7 | 0 | 3 | 22 | DRIFT_DETECTED | RESOLVED WITH OVERRIDE — 10 applied (incl. L1-003 OAuth widening) / 13 advisory recurring / gate overridden |
| #3 | 2026-05-22 | 6/7 | 0 | 2 | 17 | DRIFT_DETECTED | TBD — read-only scan; user to disposition L5-001..005 + L7-014 |

---

## Disposition checkboxes (user-driven)

> Run #3 is a read-only scan. The skill explicitly does NOT modify any artifact. Disposition decisions go below; an interactive follow-up should apply them and update `.forge-status.yml` + `sync-fix-list.md`.

- [ ] L5-001 — Add 5 missing fields to `User` (`default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log`, `last_handle_change`, `session_version`) OR amend tasks.md T021 description
- [ ] L5-002 — Add `per_item_visibility` to BacklogItem; reconcile `note`/`notes` naming
- [ ] L5-003 — Add unique compound `(backlog_id, album_id)` to BacklogItem indexes (or update status note)
- [ ] L5-004 — Decide whether code or spec field names win for `private_profile` / `last_seen_at` / `handle_changed_at`; propagate
- [ ] L5-005 — Reconcile CriticSeed shape (genre_signature/public_bio vs category/description) and index uniqueness semantics
- [ ] L7-014 — Renumber duplicate `## Session 3` → `## Session 4` in implementation-log.md; bump `session_count` to 4
- [ ] (recurring) L4-005 — Add FollowRequest + ReviewEditHistory + FailedEmail to product-spec/data-model.md inventory table (closes most of the remaining inventory gap)
