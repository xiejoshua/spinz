# Implementation log — 004-discover-sort-and-counts

Date: 2026-05-26
Author: Joshua Xie

## Tasks completed

All 9 (T001 — T009).

## Files touched

Created:
- `apps/api/src/auxd_api/modules/mb_mirror/service.py` — added `search_text_with_filters` + `_TOTAL_DISPLAY_CAP`.
- `apps/api/src/auxd_api/modules/search/service.py` — added module constants, `_tokenize`, `_coverage_ratio`, `_composite_rerank`, relocated `_filter_results` / `_sort_results` from routes, added `search_albums_with_total`; bumped cache key v2 → v3; `_serialize_album` carries optional `_relevance_rank`.
- `apps/api/src/auxd_api/modules/search/routes.py` — query-mode branch now calls `search_albums_with_total`; removed `_filter_results` / `_sort_results` (moved to service); dropped unused `random` import.
- `apps/api/tests/unit/test_mb_mirror_search_text_with_filters.py` (new, 8 tests).
- `apps/api/tests/unit/test_search_composite_rerank.py` (new, 14 tests).
- `apps/api/tests/integration/test_search_endpoint.py` — added `_StubMirrorService` + `_mirror_row` helpers; 7 new TCs (TC-1..TC-7).

No frontend touched (per spec).

## Decisions

### `_filter_results` / `_sort_results` relocation

Moved from `search/routes.py` to `search/service.py`. Rationale:
the new `search_albums_with_total` orchestrator needs both helpers for
the legacy (mirror-disabled) fallback path and the thin-mirror append
mode. Importing them from routes would have created a service ←→
routes cycle. Routes now imports nothing test-relevant from itself
beyond the router object and provider factories.

### Mirror dep injection in tests

The default `get_mirror_service` reads `app.state.mirror_client` from
the FastAPI lifespan. Integration tests construct a bare `FastAPI()`
which never sets that state — the default branch already returned a
disabled service, so legacy tests were unaffected. For TC-1..TC-6 I
added an optional `mirror_service` kwarg to `_make_app` that overrides
`get_mirror_service` via `app.dependency_overrides`, and a
`_StubMirrorService` subclass that overrides `search_text_with_filters`
+ `search_text` + `enabled` to return pre-seeded data. TC-7 leaves the
override unset to exercise the degraded path.

### Composite reranker tuning

Implemented exactly per spec Q2:
- `_ARTIST_MATCH_BOOST = 10.0`
- `_TOKEN_COVERAGE_THRESHOLD = 0.80`
- `_STOPWORDS = {"the", "a", "an", "and", "&"}`
- coverage = `|q ∩ t| / min(|q|, |t|)` (symmetric)

The base score is `N - i` where `i` is the row's index in mirror BM25
order. The final sort key is `(-score, -rating_count, i)` — the index
tiebreak guarantees stable ordering for identical (score, rating_count)
pairs, which keeps the reranker deterministic.

The `_TIEBREAK_BAND = 0.05` constant from the spec is kept as a module
constant for documentation only — the `(score desc, rating_count desc)`
sort naturally resolves any band of equal scores without a separate
proximity check, which is exactly what spec Q1 described.

### Total cap location

Both the mirror service AND the search service own `_TOTAL_DISPLAY_CAP
= 10_000`. The mirror caps its own COUNT(*) return so the orchestrator
never sees a true count > 10k. The orchestrator re-caps the
mirror_total + legacy_count sum for mode 2 (thin-mirror + Discogs
append).

### Cache key v2 → v3

`_serialize_album` now writes an optional `_relevance_rank` field for
mirror-tier hits. Old v2 cache entries lack the field, so bumping the
key invalidates them automatically. The cached payload still round-
trips correctly because the rank is just an int. Frontend ignores
underscore-prefixed keys.

### Thin-mirror dedup

When the mirror returns <5 hits and we fall through to the legacy
Discogs/MB chain, I strip from the legacy results any hit whose MBID
already appeared in the mirror tier. The legacy `search_albums` flow
already materialises mirror hits at tier 0, so without this strip a
mirror row would appear once at the top (from the new orchestrator)
and again somewhere lower (from the cached legacy candidates).

## Verify gate results

### Backend (apps/api)
- `ruff check .` — clean.
- `ruff format --check .` — clean.
- `mypy --strict src` — 9 errors, all pre-existing on `main` (verified
  via git stash). 0 introduced by this feature.
- `pytest` — 1109 passed, 3 pre-existing failures
  (`test_email_adapter::test_email_template_renders_payload_and_unsubscribe`,
  `test_db::test_all_document_models_has_twenty_one_entries`,
  `test_db::test_canonical_list_matches_conftest_expectation`), 3 skipped.
  All 7 new integration TCs + 22 new unit tests green.

### Frontend (apps/web)
- `pnpm lint` (biome) — clean.
- `pnpm typecheck` (tsc) — clean.
- `pnpm test:unit` (vitest) — 123/123 passed.

## Spec deviations

None. The implementation matches the locked strategy (C + B trimmed)
in product-spec.md and the per-file change spec in plan.md exactly.

## Post-ship follow-up (2026-05-26, same day)

**Bug:** User tested in real-world dev and reported "kanye west still
returns Igor" even after the 004 ship. Count fix was confirmed working.

**Root cause:** The locked spec (FR-005) said legacy/Discogs hits "append
below mirror, never interleave." That assumed the mirror would carry
strong artist coverage. In the dev env (and likely in any not-yet-fully-
seeded mirror), the mirror returns 0 hits for popular artists like
Kanye West, triggering Mode 2 (thin-mirror) where the legacy chain's
Discogs-popularity ordering bleeds through unchanged. Discogs's master
search returns *Igor* (Kanye is a credited writer) before *Jesus Is
King* by popularity. The reranker only ran over `mirror_serialized` —
the empty list — and `_sort_results(..., sort_key='relevance')` is a
no-op pass-through, so Discogs's order survived to the response.

The same flaw applies to Mode 3 (mirror disabled / unreachable): the
degraded path called `_sort_results` without rerank.

**Fix:** Run `_composite_rerank` over the COMBINED list at the end of
Mode 2, and over `sorted_results` in Mode 3, when `sort_key='relevance'`.
The `artist_name` field on Discogs-sourced rows is the same shape as
mirror rows, so the +10 artist-match boost works identically:
- *Jesus Is King* (Discogs, artist_name="Kanye West") → coverage 1.0 → +10
- *Igor* (Discogs, artist_name="Tyler, The Creator") → coverage 0.0 → +0

After rerank, *Jesus Is King* beats *Igor* regardless of who supplied
the row.

**Spec deviation:** FR-005's letter ("never interleave") is relaxed.
The spirit ("the matching artist's albums come first regardless of
source") is preserved. The composite score naturally keeps mirror rows
ahead of legacy rows when both match the artist (mirror has lower
indices → higher base scores → wins ties), so TC-6 (mirror-rows-first
ordering) still passes.

**New tests:**
- **TC-8** — empty mirror + Discogs returns `[Igor, Jesus Is King]` →
  asserts *Jesus Is King* indexes before *Igor*.
- **TC-9** — mirror disabled entirely (Mode 3) + same Discogs order →
  same assertion. Covers the local-dev / unprovisioned-Turso case.

**Files touched (delta):**
- `apps/api/src/auxd_api/modules/search/service.py` — 2 small blocks
  added in `search_albums_with_total` (Mode 2 combined rerank, Mode 3
  degraded rerank).
- `apps/api/tests/integration/test_search_endpoint.py` — TC-8 + TC-9.

**Gate results:** ruff clean, format clean, 43/43 search-touching
tests pass.

## Post-ship follow-up #2 (2026-05-26)

**Bug:** User real-world testing: q='tyler the creator' returned Frank
Ocean's *Channel Orange* (where Tyler is a credited producer) first.
Mirror had Tyler's albums; the rerank didn't lift them.

**Root cause:** Two compounding flaws.

1. **Tokenizer glued punctuation.** `_tokenize("Tyler, The Creator")`
   returned `{"tyler,", "creator"}` because `str.split()` only splits
   on whitespace. The trailing comma on "tyler," meant it never
   matched the query token `tyler`. Coverage dropped to
   `|{creator}| / 2 = 0.5`, below the 0.8 threshold → no boost
   applied → Tyler's albums got the same base score as Channel Orange.

2. **`+10` additive boost was too soft.** Even with the tokenizer fixed,
   a +10 score delta couldn't overcome a large BM25/popularity gap.
   With N=50 candidates: a non-match at index 0 scores 50; a match
   at index 12 scores 50-12+10 = 48 → non-match still wins. The user's
   "ALWAYS" invariant required a hard rule, not an additive boost.

**Fix:**

- **Tokenizer:** swap `str.split()` for `re.compile(r"\w+", re.UNICODE)`.
  Strips all punctuation cleanly. Preserves non-ASCII (Björk, Beyoncé,
  Sigur Rós) since `\w` is Unicode-aware in Python 3.
- **Rerank:** replace additive scoring with a two-bucket partition:
  - **Bucket A** (artist matches, coverage ≥ 0.8): sorted by
    `(rating_count desc, source_index asc)` so the artist's most-
    engaged albums lead, with source ordering as a stable tiebreaker.
  - **Bucket B** (non-matches): sorted by `source_index asc` to
    preserve mirror BM25 / Discogs popularity exactly as supplied.
  - Bucket A always ranks above Bucket B regardless of rating gaps.

`_ARTIST_MATCH_BOOST` and `_TIEBREAK_BAND` constants are now unused
but kept in the module for documentation continuity; could be removed
in a later cleanup PR.

**Spec adherence:** US-002's invariant ("artist's albums first") is
now strictly enforced rather than probabilistically. The strong
language in the user's bug report — "should ALWAYS produce all their
albums before others" — is the new contract.

**Discogs-side option (deferred):** Discogs's `/database/search?artist=<q>`
filters server-side to results where the artist field matches, which
would prevent credit/feature pollution at the source. Adopting this
requires an intent classifier ("is this query an artist name vs. a
title?"). Filed as a future enhancement; not implementing now because
the two-bucket rerank handles the same failure cases without the
extra plumbing.

**New tests:**

- **Unit** `test_tokenize_strips_punctuation` — pins Tyler/Earth-Wind-
  Fire/Wu-Tang/Florence cases.
- **Unit** `test_tokenize_preserves_unicode_letters` — Björk / Beyoncé
  / Sigur Rós survive the regex extract intact.
- **Unit** `test_tyler_the_creator_lifts_tyler_above_channel_orange` —
  pins the reported case with the original input-ordering trap.
- **Unit** `test_hard_bucket_invariant_no_match_can_outrank_match` —
  worst-case stress: 1M-rating non-match at index 0 vs. 10-rating
  match at index 1. Match still wins.
- **Integration TC-10** `test_tc10_tyler_the_creator_query_demotes_channel_orange`
  — pins the same case through the full route stack.

**Files touched (delta):**

- `apps/api/src/auxd_api/modules/search/service.py` — `_tokenize` uses
  Unicode-aware regex; `_composite_rerank` rewritten as two-bucket.
- `apps/api/tests/unit/test_search_composite_rerank.py` — 4 new tests.
- `apps/api/tests/integration/test_search_endpoint.py` — TC-10.

**Gate results:** ruff + format clean; 48/48 004-touching tests pass
(14 unit rerank + 8 unit mirror + 26 integration including TC-10).

## Operator follow-ups

1. The `search.mirror_degraded` log event fires whenever the mirror
   is unreachable or disabled; add it to PostHog/Sentry alerting once
   query volume justifies.
2. The `_ARTIST_MATCH_BOOST` / `_TOKEN_COVERAGE_THRESHOLD` constants
   are module-private. Post-beta, if real-query reports drift, expose
   via env-var or feature-flag.
3. Three pre-existing test failures live on `main` and were NOT
   introduced by this feature. They concern email-template rendering
   and the document-model count — orthogonal to search.
