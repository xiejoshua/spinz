# Plan: Discover sort + result counts (lite)

**Feature:** `004-discover-sort-and-counts`
**Mode:** lite (tasks rolled into this plan)
**Spec:** `product-spec.md`

## Architecture summary

Three code surfaces change. No new modules, no schema deltas, no provider
contract changes.

1. **Mirror service** — gain a method that combines FTS5 text MATCH with
   the existing `_build_filter_where` clause, returning a `(rows, total)`
   tuple analogous to `filter_search`.
2. **Search service** — `search_albums` becomes "(rows, total)"-returning
   when called with a `total_required=True` flag (new), or the route gets
   a sibling entry point `search_albums_with_total`. Composite reranker
   added to the `relevance` branch. Discogs/MB fallback rows append at
   the bottom rather than interleave.
3. **Search route** — query-mode branch reads the true `total` from the
   service layer rather than computing `len(filtered)`.

Frontend: zero changes. The existing string in
`advanced-search-client.tsx:484` (`"Showing X of Y" / "Showing X of Y+"`)
already renders correctly once the backend reports honest totals.

## Code changes

### Chunk 1 — Mirror: text + filter combined query

**File:** `apps/api/src/auxd_api/modules/mb_mirror/service.py`

Add `search_text_with_filters(...)` adjacent to `filter_search`:

```python
async def search_text_with_filters(
    self,
    *,
    query: str,
    year_min: int | None,
    year_max: int | None,
    decade_buckets: set[int] | None,
    genre: str | None,
    sort_key: str,
    limit: int,
    offset: int,
) -> tuple[list[MirrorRow], int]:
    """FTS5-text + filter combined query against the mirror.

    Returns rows in BM25-relevance order (when sort_key='relevance'),
    or in the sort_key's natural order otherwise. ``total`` is the
    unfiltered COUNT(*) over the combined MATCH + WHERE.
    """
```

Implementation notes:

- Build the FTS5 `MATCH` expression via the existing `_build_fts_match`.
- Build the filter `WHERE` via the existing `_build_filter_where`.
- Combined query:
  ```sql
  SELECT albums_mirror.mbid, ... FROM albums_mirror_fts
  JOIN albums_mirror ON albums_mirror.rowid = albums_mirror_fts.rowid
  WHERE albums_mirror_fts MATCH ? AND (<filter_where>)
  ORDER BY <order_clause>
  LIMIT ? OFFSET ?
  ```
- For `sort_key == 'relevance'`, `ORDER BY rank` (FTS5's BM25). For
  other sort keys, reuse `_sort_clause_for`.
- COUNT query uses the same MATCH + WHERE without ORDER/LIMIT.
- Degrades silently on Turso error (mirror disabled → `([], 0)`,
  caller falls back to the legacy Discogs path).

Cap `total` at 10,000 inside this method per FR-008.

### Chunk 2 — Search service: integrate mirror text+filter + composite rerank

**File:** `apps/api/src/auxd_api/modules/search/service.py`

Add a new public entry point that returns `(rows, total)`:

```python
async def search_albums_with_total(
    *,
    query: str,
    year_min: int | None,
    year_max: int | None,
    decade_buckets: set[int] | None,
    genre: str | None,
    sort_key: str,
    limit: int,
    offset: int,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    mirror_service: AlbumMirrorService | None,
) -> tuple[list[dict[str, Any]], int]:
```

Flow (relevance-mode default):

1. **Mirror text+filter tier.** Call
   `mirror_service.search_text_with_filters(...)` if mirror is enabled.
   If it returns ≥ `_FALLBACK_THRESHOLD` (5) rows, materialize via
   `_resolve_or_materialise_mirror_row`, apply the composite reranker
   (only for `sort_key='relevance'`), slice to `[offset : offset+limit]`,
   and return `(page, mirror_total)`.
2. **Thin-mirror fallback.** Mirror returned <5 rows. Run the existing
   tiered pipeline (Atlas → Discogs masters → MB) but append the
   non-mirror hits *after* the mirror rows (never interleave). Total
   reported = `mirror_total + len(non_mirror_hits)` (the mirror is
   authoritative for catalog presence; the fallback adds breadth).
3. **Mirror disabled / unreachable.** Skip the new path entirely and
   call the legacy `search_albums_cached` flow; report
   `total = len(filtered)`, `has_more = False`. Emit
   `search.mirror_degraded` log event so the lying-total mode is
   observable.

Add the composite reranker:

```python
# Module-level constants — module-private but easy to tune.
_ARTIST_MATCH_BOOST = 10.0
_TIEBREAK_BAND = 0.05            # 5%
_TOKEN_COVERAGE_THRESHOLD = 0.80 # 80%
_STOPWORDS = frozenset({"the", "a", "an", "and", "&"})


def _composite_rerank(
    candidates: list[dict[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    """Apply artist-match boost + popularity tiebreaker over the
    candidates while preserving mirror BM25 order as the baseline.

    The candidates arrive in BM25 order. We assign each row a score
    of (N - i) where N is len(candidates) and i is its index, then
    apply +_ARTIST_MATCH_BOOST when the query's token coverage
    against artist_credit is ≥ _TOKEN_COVERAGE_THRESHOLD. Final
    sort is by (composite_score desc, rating_count desc) — the
    rating_count tiebreaker resolves ties inside _TIEBREAK_BAND
    naturally because exact-equal composite scores end up adjacent.
    """
```

Token coverage definition (per spec Q2):

```python
def _coverage_ratio(query_tokens: set[str], target_tokens: set[str]) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    overlap = len(query_tokens & target_tokens)
    return overlap / min(len(query_tokens), len(target_tokens))
```

Both `query_tokens` and `target_tokens` are casefolded, stopword-stripped,
whitespace-split.

Update `_serialize_album` to carry an optional `_relevance_rank` field
(integer index in mirror BM25 result) so the candidates cache can preserve
the rank across cache hits. Bump cache key to
`search:candidates:v3:album:...`.

### Chunk 3 — Route wiring

**File:** `apps/api/src/auxd_api/modules/search/routes.py`

In the `search` handler, replace the existing query-mode branch
(lines 194-229) with a single call to `search_albums_with_total`,
passing the filter args. Drop the `_filter_results` + `_sort_results`
in-process pass for the relevance branch — the new service path handles
both server-side.

Other sort keys (`popular_on_auxd`, `recently_added`, `year_*`,
`surprise`) continue to fetch via the mirror's `search_text_with_filters`
with the appropriate `sort_key`, then slice in the same way. No
in-process re-sort needed.

Backwards-compatible: legacy `search_albums_cached` and `search_albums`
remain exported for the catalog-seed CLI / worker which call them
directly (per the existing docstring contract).

### Chunk 4 — Tests

**File:** `apps/api/tests/integration/test_search_endpoint.py` (extend)

New test cases:

- **TC-1 (US-001):** `q="kanye" decade=2010s` returns true `total > 50`
  with a mocked mirror that has 218 matching rows. Verify
  `response.json()["total"] == 218` (or capped at 10,000 if applicable).
- **TC-2 (US-002):** Fixture mirror has *Igor* (Tyler the Creator, with
  Kanye credited) and *Jesus Is King* (Kanye West). `q="kanye west"`
  returns *Jesus Is King* before *Igor* — assertion on `results[0]`
  artist field == "Kanye West".
- **TC-3 (US-002 broader):** Fixture has 4 Kanye albums + 2 albums where
  Kanye is credited; `q="kanye west"` top-5 contains at least 4 Kanye-
  authored albums.
- **TC-4 (US-003):** `q="kanye graduation"` → top hit is *Graduation* by
  Kanye West.
- **TC-5 (count fix, FR-008):** Mirror returns 12,500 matches → API
  response total == 10,000 (cap).
- **TC-6 (FR-005):** Mirror returns 2 hits, Discogs returns 8 → response
  has 10 results, mirror's 2 are first.
- **TC-7 (degradation):** Mirror disabled → existing tests still pass
  (legacy behavior preserved).

**File:** `apps/api/tests/unit/` — new unit file
`test_search_composite_rerank.py`:

- Token-coverage edge cases: stopword handling, empty query, empty
  artist, single-token-match, no-match.
- `_composite_rerank` ordering: known-input → known-output for the 4
  fixture queries above.

**File:** `apps/api/tests/unit/test_mb_mirror_search_text_with_filters.py`
— new unit test for the mirror SQL builder.

## Test gate

Pre-merge bar (same as 002/003 lite features):

- `cd apps/api && uv run ruff check . && uv run ruff format --check . &&
  uv run mypy --strict src && uv run pytest` — all green; new tests
  add ≥15 cases.
- `cd apps/web && pnpm biome:check && pnpm tsc --noEmit && pnpm test:run`
  — all green (zero new frontend code; existing tests must still pass).
- Manual smoke at `/search?q=kanye%20west`: verify top 5 are Kanye
  albums; verify `/search?q=kanye&decade=2010s` shows a real total.

## Inline task list (lite mode)

| ID | Subject | File(s) | Size |
|----|---------|---------|------|
| T001 | Add `search_text_with_filters` to mirror service | `mb_mirror/service.py` | M |
| T002 | Unit test the mirror SQL builder | `tests/unit/test_mb_mirror_search_text_with_filters.py` | S |
| T003 | Add `_composite_rerank` + helpers + module constants | `search/service.py` | M |
| T004 | Unit test composite rerank + token coverage | `tests/unit/test_search_composite_rerank.py` | S |
| T005 | Add `search_albums_with_total` orchestrator | `search/service.py` | M |
| T006 | Wire route to new entry point; drop in-process filter for relevance | `search/routes.py` | M |
| T007 | Bump candidate cache key to v3 + carry `_relevance_rank` | `search/service.py` | S |
| T008 | Add 7 integration test cases (TC-1..TC-7) | `tests/integration/test_search_endpoint.py` | M |
| T009 | Verify gate: ruff + mypy strict + pytest + biome + tsc + vitest | (CI gates) | S |

Order: T001 → T002 (parallel), T003 → T004 (parallel), T005 (depends on
T001+T003), T006 (depends on T005), T007 inline with T005, T008 last
(depends on T006), T009 final.

## Operator follow-ups

- `_ARTIST_MATCH_BOOST`, `_TIEBREAK_BAND`, `_TOKEN_COVERAGE_THRESHOLD`
  exposed as module constants for post-beta tuning; not env vars yet
  (no need to hot-tune without restart at MVP scale).
- Mirror-disabled degraded total is logged as
  `search.mirror_degraded` — add to PostHog dashboard if/when query
  volume justifies.
- Composite reranker fixture queries should grow with closed-beta
  user reports; the unit test file is the canonical "things we tested
  and locked in" list.

## Risk register

- **R-001** (from spec) — reranker tuning drift. Mitigated by
  module-level constants + locked-in fixture tests.
- **R-002** (from spec) — mirror coverage gaps. Mitigated by preserved
  thin-mirror fallback chain.
- **R-003** (from spec) — COUNT(*) speed on 1.3M rows. Mitigated by
  existing Redis candidate cache (5 min TTL); SQLite is fast on the
  mirror per existing telemetry.
- **R-004 (new)** — score-band semantics edge case: when all candidates
  have identical BM25 scores (rare; degenerate one-token query against
  uniform corpus), the rerank is fully popularity-driven. This is
  acceptable — popularity-as-tiebreaker is the documented behavior.

## Definition of done

- All 9 inline tasks complete.
- 8 functional requirements (FR-001..FR-008) have a code path.
- 3 user stories have at least one integration test each.
- Verify gate green (see Test gate above).
- Manual smoke confirms top-5 for `q="kanye west"` is all Kanye West
  albums, and `q="kanye&decade=2010s"` total is honest.
