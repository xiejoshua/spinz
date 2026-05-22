# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #4 — 2026-05-22**
> Phase: 6 (Implementation, in progress) — 35/170 tasks complete (post-CR-001 task graph; 27/183 of pre-CR-001 graph)
> Drift budget: cosmetic ≤ 20, structural = 0

---

## Run #4 (2026-05-22, late)

> **Trigger:** post-CR-001 (commit `fa43ad8` — Spotify pivot) + post-§4 Providers wave (commit `d69272c` — T041/T048-T052/T049a/T049b).
> **Layers checked:** 6/7 (1, 2, 3, 4, 5, 7) | **Skipped:** Layer 6 (spec ↔ code backward) — still premature; only data + provider scaffolding has landed, no services/routes/UI yet.
> **Focus per user prompt:** structural drift detection on Layers 2-5 (recently re-edited boundaries); Layers 1, 6, 7 scanned at lower priority.

### Summary

| Severity | Count | Net of recurring | New this run |
|----------|-------|-----------------:|-------------:|
| CRITICAL | 0 | — | — |
| WARNING | 4 | 0 recurring + 4 new | L2-014 (FR-033 orphaned in spec.md), L3-013 (plan §5.1 protocol method names diverge from code), L3-014 (plan §5.2 `lib/resilience.rate_limit` symbol does not exist), L4-006 (discogs_id vs discogs_release_id field-name drift) |
| INFO | 14 | 11 recurring + 3 new | L2-015 (wireframe 01 label stale), L2-016 (spec.md "16 entities / 15 active" count narrative inconsistent with CR-001), L4-007 (tasks.md "27 active FRs" claim stale post-FR-033 addition) |
| CLEAN | Layers 1 (no new), 6 (skipped); Layer 7 substantially clean | — | — |

**Verdict: DRIFT_DETECTED (NOT CRITICAL).** No CRITICAL-severity individual finding. 4 new WARNINGs are concentrated at the Layer 2-4 boundaries opened by CR-001 — the spec-level pivot to MusicBrainz + Discogs introduced a `FR-033` that did not propagate downward, and the §4 Providers wave landed against the actual code shape without aligning plan §5.1's Protocol-method names. The strict `structural: 0` budget is again tripped — escalate-or-override decision belongs to the parent agent's approval flow.

Structural count: **7** (4 new structural WARN + 3 new structural INFO). Cosmetic count: **0**. Strict `structural: 0` budget trips.

### Run #3 disposition — VERIFIED RESOLVED

All 6 Run #3 inline cleanup items have landed:

| Run #3 finding | Verified at |
|----------------|-------------|
| L5-001 (User missing 5 fields) | apps/api/src/auxd_api/modules/users/models.py:153-160 — `default_entry_visibility`, `default_backlog_visibility`, `keep_backlog_after_log`, `session_version` all present. `handle_changed_at` is the agreed code-side name for `last_handle_change` (per L5-004 resolution). |
| L5-002 (BacklogItem missing `per_item_visibility`; note/notes rename) | apps/api/src/auxd_api/modules/backlog/models.py:81-83 — `per_item_visibility: Visibility \| None` present; field is `notes` (matches task description). |
| L5-003 (BacklogItem compound uniqueness) | apps/api/src/auxd_api/modules/backlog/models.py:88 — `(backlog_id, album_id) unique=True`. |
| L5-004 (User field-name drift) | product-spec/data-model.md:51,57,59 — spec aligned to code (`private_profile`, `last_seen_at`, `handle_changed_at`). |
| L5-005 (CriticSeed shape drift) | product-spec/data-model.md:314-316 — `genre_signature` + `public_bio` aligned; `notes` clarified. user_id index left as plain unique+separate active partial (in-line note explains the intent). |
| L7-014 (duplicate `## Session 3`) | implementation-log.md:155 — renumbered to `## Session 4`; sessions 1..7 now sequential; .forge-status.yml `session_count: 7`. |

### CR-001 backbone — VERIFIED

| Check | Status | Evidence |
|-------|:------:|----------|
| Spotify code scrub | done | `grep -rln "SPOTIFY_CLIENT\|spotify_client" apps/api/src/` = 0 (all remaining mentions are CR-001 historical docstrings or anti-regression test guards). |
| .env.example clean | done | apps/api/.env.example — Catalog block now describes MusicBrainz + Discogs only; `DISCOGS_API_TOKEN` present, `SPOTIFY_*` keys removed. |
| settings.py validators | done | apps/api/src/auxd_api/settings.py — discogs_enabled audit log replaces spotify_enabled; SPOTIFY_* fields gone; field-by-field rejection on legacy keys via `extra="forbid"`. |
| User.music_providers shape | done | apps/api/src/auxd_api/modules/users/models.py:181 — `dict[str, MusicProviderState]` (neutral) replaced the old Spotify-shaped list. |
| Album.spotify_id dropped | done | apps/api/src/auxd_api/modules/albums/models.py — no spotify_id field; `discogs_release_id` field + sparse-unique index landed. |
| AlbumSource enum | done | apps/api/src/auxd_api/modules/albums/models.py:63-64 — `MUSICBRAINZ` + `DISCOGS` only; `SPOTIFY` removed. |
| NotificationType enum | done | 16 active types (down from 18); the two removed values (`spotify.revoked` + `just_finished.prompt`) and `JustFinishedPrompt` are CR-001 deferred. |
| JustFinishedPrompt deferral | done | apps/api/src/auxd_api/modules/prompts/models.py — class kept importable; NOT registered in ALL_DOCUMENT_MODELS (db.py:36-62). test_db.py:38 asserts `len(ALL_DOCUMENT_MODELS) == 16`; test_db.py:87 asserts JustFinishedPrompt not in ALL_DOCUMENT_MODELS. |
| Wireframes 01 + 03 redesigned | done | wireframes/01-onboarding.html `<title>` is "Follow Critics"; wireframes/03-log-sheet.html rewritten for manual search. |
| Pytest backbone | done | impl-log Session 7 — 352/352 pass + 3 skip (skips = deferred JustFinishedPrompt instantiation tests). |

### §4 Providers wave — VERIFIED LANDED

| Task | Code/test landing | Notes |
|------|-------------------|-------|
| T041 | providers/base.py + providers/__init__.py + tests/unit/test_providers_base.py | `CatalogProvider` + `MusicProvider` Protocols defined; `CatalogAlbum` + `ListeningEvent` Pydantic models. **BUT:** method names diverge from plan §5.1 — see L3-013. |
| T048 | tests/integration/test_musicbrainz_provider.py (9 tests via respx) | Path divergence acknowledged in tasks.md in-line note (per locked decision #5). |
| T049 | providers/musicbrainz.py | 1 req/sec lock; CAA cover URL synthesized. Single-file (not package) per locked decision #5. |
| T049a | tests/integration/test_discogs_provider.py (7 tests via respx) | Same path divergence per locked decision #5. |
| T049b | providers/discogs.py | Disabled-mode when DISCOGS_API_TOKEN unset; `Authorization: Discogs token=...` scheme. |
| T050 | providers/transport.py — ResilienceTransport(httpx.AsyncBaseTransport) | 429 bypasses retry; 5xx through retry; timeout/connect-error → ProviderUnavailable. |
| T051 | providers/transport.py — log_call per request | Single emission point covers both MB + Discogs. |
| T052 | providers/errors.py — ProviderError taxonomy | All four subclasses carry optional `provider: str`. HTTP-status mapping (503/429/401/404) consistent across module docstring + T052 description. |
| respx>=0.21 dev dep | apps/api/pyproject.toml:38 | Resolved to 0.23.1. |

### Layer-by-layer

| Layer | Pair | Verdict | Notes |
|-------|------|---------|-------|
| 1 | research ↔ product-spec | recurring only | L1-001 (W1 activation) + L1-002 (Apple Music 15% → 30%) carried unchanged. Research's historical Spotify mentions are explicitly permitted by CR-001 locked-decision #1 (only flag MVP-scoped sections still treating Spotify as in-scope) — no such MVP-scoped residual found. |
| 2 | product-spec ↔ spec.md | **2 NEW WARN + 2 NEW INFO** | L2-014 (FR-033 in spec.md only — not propagated to product-spec.md / README.md / data-model.md) is the headline. L2-015 (wireframe 01 label) + L2-016 (entity count narrative) are CR-001 cosmetic-but-meaning fallout. Recurring INFO L2-004/005/006/009 unchanged. |
| 3 | spec.md ↔ plan.md | **2 NEW WARN** | L3-013 (plan §5.1 Protocol method names `lookup_by_mbid`/`lookup_by_external_id`/`cover_art_url` + `provider_id: str` field + `AlbumRef`/`AlbumDetail`/`Listen`/`CurrentlyPlaying` return types do not match code's `get_album_by_mbid`/`get_album_by_external_id` + `CatalogAlbum`/`ListeningEvent`) — most consequential drift this run. L3-014 (plan §5.2 references non-existent `lib/resilience.rate_limit`). Recurring INFO L3-009/010 unchanged. |
| 4 | plan.md ↔ tasks.md | **1 NEW WARN + 1 NEW INFO** | L4-006 (`discogs_id` in product-spec/data-model.md + tasks.md:584 T063 Description vs `discogs_release_id` in code + plan §3.1 + spec.md FR-005). L4-007 (tasks.md:65 "27 active FRs covered minus the 5 deferred" — should be "28 active FRs" if FR-033 was meant to be covered, but tasks.md T053a actually refs FR-005 not FR-033 → cross-trace gap). Recurring L4-005 (satellite collections) narrowed but still active. |
| 5 | tasks.md ↔ code | clean | The 5 Run #3 WARN/INFO items all landed. The path divergences (providers/musicbrainz single-file vs package per Paths spec) are documented as in-line task notes per CR-001 locked-decision #5 — not re-flagged. |
| 6 | spec.md ↔ code | SKIPPED | Backward direction premature — no service/route/UI code yet. Provider scaffolding is forward-only (no spec/FR specifically *defines* CatalogProvider beyond §5.1, which is the L3 drift above). |
| 7 | cross-link integrity | clean | L7-014 resolved. Recurring 5 phase-digest orphans + L7-013 implementation-log orphan unchanged. No new orphans introduced by CR-001 or the §4 wave. |

---

## New findings (Run #4)

### DRIFT-L2-014 — FR-033 (Report missing album) exists only in spec.md

| Field | Value |
|-------|-------|
| Layer | 2 (product-spec ↔ spec.md) — also touches Layer 3 + 4 |
| Direction | Backward (spec → product-spec); also forward (spec → plan/tasks) |
| Severity | WARNING |
| Category | structural |
| Source | `spec.md:253` (FR-033 row); `spec.md:432` (validation criterion 12); `spec.md:558` (risk-mitigation row); `spec.md:603` (CR-001 changelog row) |
| Target | `product-spec/product-spec.md` (FR table lines 139-172) + `product-spec/README.md:62` + `product-spec/data-model.md` |
| Expected | FR-033 row in product-spec.md FR table; README.md active-FR count + enumeration includes FR-033; functional-requirement total updated |
| Actual | `grep -n "FR-033" product-spec/**/*.md` returns ZERO hits. README.md still claims "22 functional requirements active (FR-001, FR-004 to FR-016, FR-018 to FR-020, FR-028 to FR-032)" — excludes FR-033. spec.md has 23 active FRs; product-spec has 22. |
| Cross-check | tasks.md T053a Refs line (`Refs: FR-005; CR-001; sync-fix L3-006`) does not include FR-033 either — FR is orphaned even within the artifact set that *does* know about it. |
| Proposed resolution | (a) Add FR-033 row to product-spec/product-spec.md aligned to spec.md wording; update README.md active count 22 → 23 and enumeration to include FR-033; (b) update tasks.md T053a Refs line to add `FR-033`; (c) optionally cross-link FR-033 from data-model.md (Report entity already has `target_type=missing_album`). |

### DRIFT-L3-013 — plan §5.1 Protocol method names diverge from code

| Field | Value |
|-------|-------|
| Layer | 3 (spec.md / plan.md ↔ code) |
| Direction | Forward (plan → code) |
| Severity | WARNING |
| Category | structural |
| Source | `plan.md:455-480` (§5.1 code block); also `plan.md:533` (services table row for `providers/musicbrainz`) |
| Target | `apps/api/src/auxd_api/providers/base.py:89-140` |
| Expected per plan | `CatalogProvider` has `provider_id: str`; methods `search_albums(q, limit) -> list[AlbumRef]`, `lookup_by_mbid(mbid) -> AlbumDetail \| None`, `lookup_by_external_id(external_id) -> AlbumDetail \| None`, `cover_art_url(release_group_mbid) -> str \| None`. `MusicProvider` has `provider_id: str` + `get_recently_played(user, since, limit) -> list[Listen]`, `get_currently_playing(user) -> CurrentlyPlaying \| None`, `get_user_library(user, limit) -> list[AlbumRef]`. |
| Actual in code | `CatalogProvider` has NO `provider_id` field. Methods are `search_albums(query, limit=10) -> list[CatalogAlbum]`, `get_album_by_mbid(mbid) -> CatalogAlbum \| None`, `get_album_by_external_id(provider, external_id) -> CatalogAlbum \| None`. There is NO `cover_art_url` Protocol method — cover-art URL is a *field* on `CatalogAlbum` (set by the MB impl using the CAA URL convention). `MusicProvider` has NO `provider_id`, NO `get_user_library` method, and `get_recently_played` signature is `(user_token: str, limit: int = 50)` not `(user, since, limit)`. Return types `CatalogAlbum`/`ListeningEvent` rather than `AlbumRef`/`AlbumDetail`/`Listen`/`CurrentlyPlaying`. |
| Cross-check | tasks.md T048 Description references "MusicBrainz `lookup_by_mbid`" (plan-aligned name, not code-aligned). tasks.md T049a Description references "`search_releases` and `get_release` methods" — Discogs-specific names that match *neither* plan §5.1 nor code. tasks.md T041 Description says "interface methods (per plan §5.1)" without resolving the discrepancy. The implementation-log Session 7 entry does NOT call out the rename (unlike the path divergence, which was). |
| Proposed resolution | Update plan §5.1 + §6 services table to the code-aligned signatures (`get_album_by_mbid` / `get_album_by_external_id`; cover-art-as-field; drop `cover_art_url` Protocol method; drop `provider_id` since neither concrete impl uses it; drop `get_user_library` since v2 has not decided that surface yet; align `get_recently_played` to token-based signature). Optionally also amend tasks.md T048 / T049a / T041 Descriptions for consistency. Code-shape was chosen deliberately during impl (see Session 7 architectural decisions) — the spec/plan should follow the code's narrower MVP surface. |

### DRIFT-L3-014 — plan §5.2 references non-existent `lib/resilience.rate_limit`

| Field | Value |
|-------|-------|
| Layer | 3 (plan.md ↔ code) |
| Direction | Forward (plan → code) |
| Severity | WARNING |
| Category | structural |
| Source | `plan.md:484` — "Rate-limited to **1 req/sec per IP** per MusicBrainz policy (enforced client-side via `lib/resilience.rate_limit`)" |
| Target | `apps/api/src/auxd_api/lib/resilience.py` |
| Actual | `lib/resilience.py` exports: `timeout`, `retry`, `circuit_breaker`, `circuit_breaker_decorator`, `call_with_resilience`, `CircuitBreakerOpenError`, `CircuitBreakerState`, `CircuitBreakerStore`, `InMemoryCircuitBreakerStore`. **No `rate_limit` function exists.** MusicBrainz rate-limiting is implemented inline in `MusicBrainzCatalogProvider` (asyncio.Lock + time.monotonic at providers/musicbrainz.py:131-143) — this is documented as a Session 7 architectural decision ("Rate-limit policy stays provider-specific"). |
| Cross-check | tasks.md T049 in-line note describes the chosen mechanism correctly ("asyncio.Lock + time.monotonic() pacing"). |
| Proposed resolution | Update plan.md:484 wording from "enforced client-side via `lib/resilience.rate_limit`" to "enforced inline within `MusicBrainzCatalogProvider` via `asyncio.Lock` + `time.monotonic()` (rate-limit is provider-specific; the transport layer is pure resilience + observability)". Optionally add a one-line architectural note to plan §5.3 capturing why rate-limit was deliberately not lifted into the transport. |

### DRIFT-L4-006 — `discogs_id` vs `discogs_release_id` field-name drift

| Field | Value |
|-------|-------|
| Layer | 4 (plan.md / spec.md ↔ tasks.md ↔ code); also Layer 2 (product-spec) |
| Direction | Backward (code → product-spec) + forward (tasks.md text → code) |
| Severity | WARNING |
| Category | structural |
| Source | `product-spec/data-model.md:88` (`<!-- CR-001: ... discogs_id added ... -->`), `:95` (`discogs_id` field on Album), `:99` (`{ name, mbid?, discogs_id? }` on artists sub-doc), `:401-403` (indexes table `{ discogs_id: 1 } sparse unique`); `tasks.md:584` (T063 Description: `resolve_identity(mbid=None, discogs_id=None)`) |
| Target | `apps/api/src/auxd_api/modules/albums/models.py:154` (`discogs_release_id: str \| None`) + index at `:210` |
| Authoritative | `discogs_release_id` per `plan.md:242` (decision-log row), `plan.md:264` (§3.1 indexes), `plan.md:485` (§5.2 narrative), `plan.md:761` (§11.2 narrative), `spec.md` (FR-005, FR-010 referencing albums identity), and **landed code**. |
| Actual code | `discogs_release_id` field + unique sparse index. Beanie schema, JSON shape, and provider mapping all use `discogs_release_id`. |
| Proposed resolution | Update product-spec/data-model.md (lines 88, 95, 99, 403) to `discogs_release_id`. Update tasks.md:584 T063 Description from `discogs_id` to `discogs_release_id`. (Code/plan/spec are correct.) |

### DRIFT-L2-015 — wireframe 01 label stale post-CR-001

| Field | Value |
|-------|-------|
| Layer | 2 (spec.md ↔ product-spec wireframes) |
| Direction | Backward (wireframe → spec.md cross-reference) |
| Severity | INFO |
| Category | structural (label semantically wrong) |
| Source | `spec.md:203` — "[wireframes/01-onboarding.html](./product-spec/wireframes/01-onboarding.html) — **Confirm-last-30-days screen**" |
| Target | `product-spec/wireframes/01-onboarding.html:9` — `<title>Wireframe: Onboarding — Follow Critics</title>` |
| Actual | Wireframe was fully rewritten in CR-001 to the "Follow Critics" step; spec.md cross-reference still describes the deprecated Spotify "confirm-last-30-days" screen. |
| Proposed resolution | Update spec.md:203 label from "Confirm-last-30-days screen" to "Follow Critics — minimum 3 to advance" (or similar) to match the CR-001 wireframe content. |

### DRIFT-L2-016 — spec.md "16 entities / 15 active at MVP" narrative inconsistent with CR-001 deferrals

| Field | Value |
|-------|-------|
| Layer | 2 (spec.md ↔ product-spec/data-model.md) |
| Direction | Inconsistent narrative within spec.md (lines 355 vs 580) |
| Severity | INFO |
| Category | structural (narrative count claim) |
| Source | `spec.md:355` — "**16 entities listed below**; **15 active at MVP** (JustFinishedPrompt **deferred to v2 per CR-001**)"; `spec.md:580` — "[product-spec/data-model.md](./product-spec/data-model.md) — **16 active entities** + relationships + preliminary indexes" |
| Target | `product-spec/data-model.md` — 16 entity sections (User, MusicProvider (deferred sub-doc), Album, DiaryEntry, Review, ReviewLike, Follow, Backlog & BacklogItem, JustFinishedPrompt (deferred), Block, Report, Notification, NotificationPreferences, SuggestedFollow, CriticSeed) — 14 active, not 15, when MusicProvider is also counted as deferred-to-v2 (its sub-doc always-empty at MVP per CR-001). |
| Actual code | 16 Documents registered in ALL_DOCUMENT_MODELS (db.py); FollowRequest + ReviewEditHistory + FailedEmail are *additional* Documents not present in data-model.md inventory (recurring L4-005). |
| Proposed resolution | Reconcile the two spec.md claims and the data-model.md inventory. Recommend: "16 entity sections; 14 active at MVP (JustFinishedPrompt + MusicProvider both DEFERRED-TO-V2 per CR-001). MVP code registers 16 Documents (the 14 active + FollowRequest + ReviewEditHistory + FailedEmail + NotificationPreferences-embedded-on-User; see plan §3.1 for the canonical inventory)." Also closes recurring L4-005 simultaneously. |

### DRIFT-L4-007 — tasks.md "27 active FRs covered minus the 5 deferred" stale post-FR-033 addition

| Field | Value |
|-------|-------|
| Layer | 4 (spec.md ↔ tasks.md) |
| Direction | Forward (spec → tasks) |
| Severity | INFO |
| Category | structural (count claim) |
| Source | `tasks.md:65` — "**Total: 162 active MVP tasks ... 27 active FRs covered minus the 5 deferred (FR-002, FR-003, FR-017, FR-026, FR-027 — DEFERRED in spec.md per CR-001)**" |
| Target | spec.md FR table (28 rows total — 5 deferred + 23 active including FR-033) |
| Actual | spec.md has 28 FR rows, 5 deferred → 23 active. tasks.md says "27 active FRs" — likely the pre-FR-033 count. Math doesn't reconcile with current spec.md state. |
| Cross-check | T053a (the FR-033 task) refs FR-005 not FR-033 — even if the count is meant to be "27 base + 1 new", the cross-trace is broken. |
| Proposed resolution | If FR-033 is intended to be counted (recommended): update tasks.md:65 to "28 active FRs covered minus the 5 deferred"; update T053a Refs to include FR-033. If FR-033 is itself a Layer 2 cleanup target (per L2-014), defer this fix until L2-014 is resolved. |

---

## Drift table

| ID | Layer | Severity | Category | Title | Status |
|----|:-:|:-:|:-:|---|---|
| L2-014 | 2 | WARN | struct | FR-033 orphaned in spec.md (not in product-spec / tasks Refs) | NEW |
| L3-013 | 3 | WARN | struct | plan §5.1 Protocol method names diverge from code | NEW |
| L3-014 | 3 | WARN | struct | plan §5.2 references non-existent `lib/resilience.rate_limit` | NEW |
| L4-006 | 4 | WARN | struct | `discogs_id` (product-spec + tasks T063) vs `discogs_release_id` (code + plan + spec) | NEW |
| L2-015 | 2 | INFO | struct | spec.md:203 wireframe 01 label stale ("Confirm-last-30-days" → "Follow Critics") | NEW |
| L2-016 | 2 | INFO | struct | spec.md "16 entities / 15 active" narrative count inconsistent with CR-001 deferrals | NEW |
| L4-007 | 4 | INFO | struct | tasks.md "27 active FRs" count stale post-FR-033 addition | NEW |
| L1-001 | 1 | INFO | struct | W1 activation definition narrowed | RECURRING |
| L1-002 | 1 | INFO | struct | Apple Music re-eval threshold 15% → 30% | RECURRING |
| L2-004 | 2 | INFO | struct | FR-003 trace tag US-A3 → US-A2 (note: FR-003 now DEFERRED-TO-V2 per CR-001 — recurring item may now be moot) | RECURRING (CR-001 may have mooted) |
| L2-005 | 2 | INFO | struct | FR-027 trace tag US-G2 removal (note: FR-027 now DEFERRED-TO-V2 — likely moot) | RECURRING (CR-001 may have mooted) |
| L2-006 | 2 | INFO | struct | Cluster name enrichment | RECURRING |
| L2-009 | 2 | INFO | struct | Entity inventory ReviewLike row | RECURRING (partially mooted by Run #2 L2-010) |
| L3-009 | 3 | INFO | struct | /critics route in plan, not spec | RECURRING |
| L3-010 | 3 | INFO | struct | Handle collision suggestion incomplete | RECURRING |
| L4-005 | 4 | INFO | cosmetic | Satellite collections (FollowRequest + ReviewEditHistory + FailedEmail) missing from product-spec/data-model.md inventory | RECURRING (narrowed); naturally bundles with L2-016 |
| L7-004..008 | 7 | INFO | struct | 5 phase-digest orphans | RECURRING (convention class) |
| L7-013 | 7 | INFO | struct | implementation-log.md orphan | RECURRING (convention class) |

---

## Verdict

**DRIFT_DETECTED (NOT CRITICAL).**

- 0 individual finding is CRITICAL-severity. No data-loss / runtime regression. Test suite is green (352/352 pass + 3 skip per Session 7 close-out).
- Structural count: **7** (4 new structural WARN + 3 new structural INFO). With strict `structural: 0` budget, the budget rule trips.
- Cosmetic count: **0** — well within the 20 budget.
- New drift in Run #4 is concentrated on the boundaries CR-001 + §4 Providers wave cracked open:
  - Layer 2: spec.md added FR-033 + a new wireframe + new entity-count narrative; the corresponding product-spec.md / README.md / data-model.md cross-references did not catch up.
  - Layer 3: plan §5.1 + §5.2 describe a Protocol surface (`provider_id`, `lookup_by_mbid`, `cover_art_url`, `get_user_library`) and a resilience symbol (`lib/resilience.rate_limit`) that the actual landed code chose not to implement — the §4 wave's architectural decisions (provider-specific rate limiting; cover-art-as-field; MBID-centric methods) were not reflected back into plan.md.
  - Layer 4: a single field-name field (`discogs_id` vs `discogs_release_id`) drifted across product-spec + tasks.md while plan + spec + code stayed aligned.
- Recommended disposition (carrying forward Run #3's `applied_split_with_override` pattern):
  1. Apply L2-014 (FR-033 propagation) — single highest-value cleanup; closes the loop on the most prominent CR-001 addition.
  2. Apply L4-006 (`discogs_id` → `discogs_release_id` rename) — pure mechanical rename across 4 lines in 2 files.
  3. Apply L3-013 + L3-014 together as a plan §5.1/§5.2 alignment commit — code is the authoritative target per Session 7 architectural decisions.
  4. Apply L2-015 (wireframe label) + L2-016 + L4-007 (count narratives) opportunistically — closes the residual narrative drift from CR-001's count changes.
  5. Override on the budget rule (structural ≠ 0) as in Run #2 + Run #3 — the picture is narrow and well-scoped; no findings block §6 entry once the four WARN items above are resolved.

### Outlook to Run #5

If L2-014, L3-013, L3-014, L4-006 land (the four WARN), Run #5 structural count projects to ~4 (3 cosmetic-narrative items + the recurring L4-005 inventory gap, which L2-016's proposed resolution would also close). Layer 6 (spec ↔ code backward) becomes meaningful once the first service/route lands (likely cluster §5 Auth or §6 Albums + Search — T053, T057-T062 + T063-T072).

---

## Sync History

| Run | Date | Layers | CRITICAL | WARNING | INFO | Initial verdict | Final disposition |
|-----|------|--------|---------:|--------:|-----:|------------------|-------------------|
| #1 | 2026-05-21 | 5/7 | 0 | 19 | 14 | CRITICAL DRIFT (budget rule) | RESOLVED WITH OVERRIDE — 10 applied / 10 backlogged / 2 deferred / 14 INFO skipped |
| #2 | 2026-05-22 | 6/7 | 0 | 3 | 22 | DRIFT_DETECTED | RESOLVED WITH OVERRIDE — 10 applied (incl. L1-003 OAuth widening) / 13 advisory recurring / gate overridden |
| #3 | 2026-05-22 | 6/7 | 0 | 2 | 17 | DRIFT_DETECTED | RESOLVED_WITH_OVERRIDE @ 2026-05-22T22:30:00Z — 6 inline cleanups applied (L5-001..005 + L7-014); 13 advisory recurring skipped; gate overridden |
| #4 | 2026-05-22 | 6/7 | 0 | 4 | 14 | DRIFT_DETECTED | TBD — read-only scan; user to disposition L2-014, L3-013, L3-014, L4-006 (+ 3 new INFO + 11 recurring) |

---

## Disposition checkboxes (user-driven)

> Run #4 is a read-only scan. The skill explicitly does NOT modify any artifact. Disposition decisions go below; an interactive follow-up should apply them and update `.forge-status.yml` + `sync-fix-list.md`.

- [ ] **L2-014** — Propagate FR-033 (Report missing album) into product-spec/product-spec.md FR table + product-spec/README.md active-FR enumeration + tasks.md T053a Refs line
- [ ] **L3-013** — Update plan §5.1 + §6 services table to code-aligned Protocol method names (`get_album_by_mbid` / `get_album_by_external_id`; cover-art-as-field; drop `provider_id` + `cover_art_url` + `get_user_library`; align `get_recently_played` signature)
- [ ] **L3-014** — Update plan §5.2 wording to describe the inline asyncio.Lock + time.monotonic() rate-limit mechanism instead of the non-existent `lib/resilience.rate_limit`
- [ ] **L4-006** — Rename `discogs_id` → `discogs_release_id` in product-spec/data-model.md (4 lines) + tasks.md:584 T063 Description (1 line)
- [ ] **L2-015** — Update spec.md:203 wireframe 01 label "Confirm-last-30-days screen" → "Follow Critics — minimum 3 to advance"
- [ ] **L2-016** — Reconcile spec.md:355 + spec.md:580 entity-count claims; reflect MusicProvider + JustFinishedPrompt both deferred (14 active); align with data-model.md inventory; bundle with L4-005 inventory cleanup if feasible
- [ ] **L4-007** — Update tasks.md:65 "27 active FRs covered" → "28 active FRs covered" (or defer behind L2-014)
- [ ] (recurring) **L4-005** — Add FollowRequest + ReviewEditHistory + FailedEmail to product-spec/data-model.md inventory table (would also close L2-016's "16 active" mismatch)
- [ ] (recurring, possibly mooted) **L2-004 / L2-005** — re-check whether FR-003 + FR-027 trace tags still need adjustment now that both FRs are DEFERRED-TO-V2; may be retire-as-moot candidates
