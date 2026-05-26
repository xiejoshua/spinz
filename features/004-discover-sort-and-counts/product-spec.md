# Product Spec: Discover sort + result counts (lite)

**Feature:** `004-discover-sort-and-counts`
**Mode:** lite
**Status:** draft (Phase 2)
**Parent feature:** `003-discover-rehaul` (Discover surface shipped 2026-05-25)

## Problem

Two quality regressions on the shipped Discover surface are degrading the core
"find what you want, see how much is here" loop:

1. **Result-count undercount.** With a query active (or query + decade/genre/year
   filters), the UI shows misleading totals like "50 results" when the catalog
   actually holds more. Source: `search_albums_cached` is pinned to
   `limit=50` for the candidate set in `routes.py:202-209`, and the route
   then reports `total = len(filtered)` (line 228). The total is bounded by
   the artificial candidate cap; there is no path to know the 51st match
   exists. "Load more" continues paginating inside the same 50-row window,
   so the displayed count grows toward 50 and stops.

2. **Ranking failure on artist-name queries.** Searching `"kanye west"`
   returns Tyler the Creator's *Igor* before Kanye's *Jesus Is King* because
   the current strategy (search-fix v4, 2026-05-24) "passes Discogs's
   master-search ordering through unchanged." Discogs treats credit /
   feature / contributor mentions as a match and then ranks those matches
   by community popularity. Kanye is a credited writer on *Igor* →
   *Igor* matches the query → *Igor*'s popularity floats it above the
   artist's own discography. We surrendered relevance to a provider whose
   search semantics don't align with our user expectation ("show me the
   artist's albums").

Both are blocking the Discover surface from feeling trustworthy. Fix now —
before any growth attempt that drives search volume up.

## Out of scope

- **A new sort UI control.** Existing sort dropdown (`relevance`,
  `popular_on_auxd`, `recently_added`, `year_newest`, `year_oldest`,
  `surprise`) stays as-is. We're improving the implementation of
  `relevance`, not adding a new key.
- **Intent classifier** (Strategy D from the brainstorm). Not building a
  parser to distinguish artist vs title vs structured queries at this
  feature. The composite-score approach (B) handles all three reasonably
  without explicit intent typing.
- **Reranker model / ML reranking** (Strategy E stage 2). The candidate
  pool stays small enough that in-process scoring is sufficient.
- **Discogs `community.have` enrichment.** Tried in v3, reverted in v4 —
  not reintroducing.
- **Front-end count display changes** beyond honoring whatever the backend
  reports. The existing string "Showing {N} of {total}{hasMore ? '+' : ''}"
  in `advanced-search-client.tsx:484` is already correct given honest
  totals.
- **Atlas Search index changes.** Atlas remains Tier 1 with its existing
  `log1p(rating_count)` popularity boost; we are not retuning that.
- **Mirror schema changes.** No new columns, no FTS5 index rebuild. The
  mirror already serves BM25-ranked text search and decade/genre/year
  filters with true counts.

## Locked strategy: C + B (trimmed)

Brainstormed five strategies (A-E). User locked **C + B trimmed**:

**Strategy C — Mirror FTS5 as the relevance source.**
The Turso mirror's `search_text` already runs FTS5 `MATCH` with `ORDER BY
rank` (BM25). It returns relevance-ranked rows today; the current
`search_albums` flow consumes them as "tier 0 candidates" without preserving
or using the rank. We will:

- Treat the mirror's BM25 ordering as the **authoritative relevance signal**
  for the merged candidate list.
- Drop "pass Discogs's master-search ordering through unchanged" as the
  primary ranking story. Discogs results are still merged in when the
  mirror is thin (<5 hits), but they enter at the *bottom* of the
  candidate list, not interleaved.

**Strategy B trimmed — Lightweight composite reranker on top.**
Apply a small in-process scoring pass over the mirror's BM25-ordered
candidates with two adjustments only:

- **Artist-match boost.** Candidates whose `artist_credit` casefold-tokens
  cover ≥80% of the query tokens get a `+10` boost. This is the
  Kanye/Igor fix specifically — a query of `["kanye", "west"]` matches
  `artist_credit="Kanye West"` fully and `artist_credit="Tyler, the
  Creator"` not at all, so Kanye's albums lift above Tyler's.
- **Platform popularity as tiebreaker only.** Within a band of candidates
  whose composite scores are within 5% of each other, sort by
  `rating_count` desc. Popularity never overrides relevance — it only
  resolves ties.

Skipped from full Strategy B: Discogs `community.have` (the broken signal),
title-match scoring (mirror BM25 already gives this via the `title` column
in the FTS5 virtual table), Atlas autocomplete score injection (Atlas hits
have their own ordering and remain Tier 1).

## Count-fix locked approach

Route **query mode** through the mirror the same way **filter-only mode**
already does:

- Extend `AlbumMirrorService.filter_search` (or add a sibling method) to
  accept an FTS5 `MATCH` expression alongside the existing year/decade/genre
  filters.
- The mirror returns `(rows, total)` where `total = COUNT(*)` over the
  same `WHERE` clause — true match count, not a 50-cap.
- Page size stays 50 (we still slice for the response), but the response
  carries the honest total.

The Discogs / MB fallback tiers still fire only when the mirror is thin
(<5 mirror hits), and the fallback rows extend the candidate list for
serialization — but the `total` reported to the client comes from the
mirror's `COUNT(*)`, capped at a reasonable display ceiling (proposed:
`min(true_total, 10000)`).

## User stories

### US-001 — Trustworthy result counts under filters

As a Discover user applying genre/decade/year filters, I want the result
counter to reflect the catalog's real match count, so I can judge whether to
narrow my filters or scroll deeper.

**Acceptance:**

- Query + decade filter (`q="kanye" decade=2010s`) shows true `total` from
  mirror `COUNT(*)`, e.g. "Showing 50 of 218."
- Filter-only (no query) behavior is unchanged — already correct.
- Pagination continues to honor `has_more` based on the true total.
- "Surprise me" remains single-page (no pagination concept).

### US-002 — Artist-name queries return that artist's discography first

As a user searching for an artist by name, I want their own albums to
appear before albums where they're a credit/feature/contributor.

**Acceptance:**

- `q="kanye west"` returns Kanye West albums in the top results;
  Tyler the Creator's *Igor* (where Kanye is a credited writer) appears
  below all Kanye West albums.
- `q="frank ocean"` returns *Blonde*, *Channel Orange*, *Nostalgia, Ultra*
  ahead of any compilation or feature credit.
- Tie-break for two Kanye albums (e.g. *Graduation* vs *808s & Heartbreak*)
  uses `rating_count` desc.
- Title-only queries (`q="graduation"`) still find the album — the
  artist-match boost is additive, not exclusive.

### US-003 — Mixed queries still work

As a user typing both artist and title (`"kanye graduation"`), I want
the result to surface the specific album, not just the artist's
discography.

**Acceptance:**

- `q="kanye graduation"` returns *Graduation* by Kanye West at top.
- The mirror FTS5 already handles this via implicit-AND token matching;
  the composite reranker preserves rather than inverts BM25 order for
  high-confidence multi-token matches.

## Functional requirements

- **FR-001.** Add `search_text_with_filters(query, year_min, year_max,
  decade_buckets, genre, sort_key, limit, offset)` to
  `AlbumMirrorService` returning `(rows, total)`. Internally combines
  the existing FTS5 `MATCH` expression with the existing
  `_build_filter_where` clause via SQL `AND`.
- **FR-002.** Update `search_albums` in
  `auxd_api/modules/search/service.py` to call the new mirror method
  when both `query` and any filter (or just `query` alone) are present
  and the mirror is enabled. Returns the new shape `(rows, total)`
  from the mirror tier.
- **FR-003.** Update the route's query-mode branch in `routes.py:194-229`
  to read `total` from the mirror result rather than `len(sorted_results)`.
- **FR-004.** When the mirror returns ≥ `_FALLBACK_THRESHOLD` (5) rows,
  skip the Discogs + MB tiers entirely (existing short-circuit; reused).
- **FR-005.** When mirror returns <5 rows: keep the existing Discogs + MB
  fallback, but the candidates from those tiers are *appended* after the
  mirror's BM25-ranked rows, not interleaved.
- **FR-006.** Composite reranker in `_sort_results` for the `relevance`
  branch:
  - Start with mirror BM25 order (already returned that way).
  - Apply artist-match boost: if query tokens cover ≥80% of
    `artist_credit` tokens (or vice versa — symmetric), `score += 10`.
  - Tie-break ties (within 5% composite score) by `rating_count` desc.
- **FR-007.** No change to `popular_on_auxd`, `recently_added`,
  `year_newest`, `year_oldest`, `surprise` branches.
- **FR-008.** Cap displayed `total` at 10,000 — beyond that, return
  `total=10000` and let pagination naturally tail off. Avoids leaking
  unbounded `COUNT(*)` to clients and gives the frontend a sane upper
  bound for "x of y+" display.

## Non-functional requirements

- **NFR-001.** Cold query latency (cache miss) stays under 1.5s p95 for
  query+filter combos — the mirror lookup replaces the Discogs round-trip
  in the common case, so latency should drop, not rise.
- **NFR-002.** Cached candidate hits stay under 50ms (Redis read +
  in-process sort).
- **NFR-003.** No new external dependencies. Pure code change.
- **NFR-004.** Existing 26 search/identity integration tests stay green
  (mirror is disabled in tests, so pre-mirror behavior must remain
  untouched along the disabled path).

## Open decisions (locked at draft)

- **Q1: Where does the score-band tiebreaker live?** → In
  `_sort_results` for the `relevance` branch. Other sort branches stay
  pure (no popularity injection).
- **Q2: How is "≥80% token coverage" defined?** → Casefold + split on
  whitespace, intersection size ≥ ceil(0.8 × min(query_tokens,
  artist_tokens)). Excludes stopwords from the token set
  (`the`, `a`, `an`, `&`, `and`).
- **Q3: What happens when the mirror is disabled / unreachable?** →
  Fall back to the previous behavior (Discogs-primary), but report
  `total = len(filtered)` with `has_more = false` and a degraded-mode
  log event so we don't silently lie about counts. Frontend already
  handles a small `total`.
- **Q4: Does the candidate cache key need a new version bump?** → Yes,
  bump to `v3` because the serialized shape now needs to carry the
  mirror's BM25 rank as a hint for the reranker. `_serialize_album`
  gains an optional `_relevance_rank: int | None` field, ignored by
  the frontend.

## Risks

- **R-001.** Composite reranker tuning drift. If the 80% token-coverage
  threshold or the 5% score-band size feel wrong against real queries,
  these need to be retunable without a code change. Mitigation: define
  both as module-level constants with clear comments; revisit after
  closed beta.
- **R-002.** Mirror coverage gaps for non-MB-canonical releases (rare
  Discogs-only artist names, indie one-offs). Mitigation: existing
  fallback to Discogs/MB tiers preserved exactly when mirror returns
  <5 hits.
- **R-003.** True `COUNT(*)` over 1.3M rows with complex WHERE could be
  slow on cold cache. Mitigation: the existing `_PROBE_CACHE_TTL` and
  `_CANDIDATES_CACHE_TTL` patterns keep hot queries fast; SQLite scans
  on the mirror are sub-second per existing telemetry.

## Success criteria

- Searching `"kanye west"` returns at least 4 Kanye West albums in the
  top 5 results.
- Result counter for `q="kanye" decade=2010s` shows a true total >50
  (assuming catalog has >50 matches), not a 50-cap.
- All existing search tests green.
- New regression tests: at least 5 fixture queries with locked-in
  expected top-3 orderings.
