# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #5 — 2026-05-22 (late)**
> Phase: 6 (Implementation, in progress) — 42/170 tasks complete
> Drift budget: cosmetic ≤ 20, structural = 0

---

## Run #5 (2026-05-22, late)

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
