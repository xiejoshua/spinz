# Phase 7 Verify Report — 003 Discover Rehaul

Date: 2026-05-24
Verifier: Claude (Opus 4.7) in `/speckit-product-forge-forge` lifecycle

## Verdict

**PASS.** All static checks green, no CRITICAL findings, no regressions
in existing test suites touched by the changes.

## Checks run

### TypeScript

```
pnpm exec tsc --noEmit  →  EXIT 0
```

### Biome (web)

```
pnpm exec biome check src/  →  Checked 171 files, no errors
```

Six files were auto-formatted by biome during implementation; one
incidental pre-existing OKLCH float-normalization fix
(`oklch(0.50 ...)` → `oklch(0.5 ...)`) was applied alongside the
feature code.

### Ruff (api)

```
uv run ruff check src/auxd_api/modules/users/routes.py \
                  src/auxd_api/modules/discover/ \
                  src/auxd_api/modules/search/
  → All checks passed
uv run ruff format --check (same paths)
  → 7 files already formatted
```

### Backend tests

```
uv run pytest tests/integration/test_search_endpoint.py \
              tests/integration/test_users_profile_endpoint.py
  → 20 passed (no failures, no errors)
```

The existing search-endpoint suite covers the legacy ``GET /search``
shape; new parameters (decade/year_min/year_max/sort/offset) ride on
top of the same handler and default values preserve the prior wire
contract, so legacy tests still pass without modification. New
parameter coverage is left to E2E (TC-E2E-014) and follow-up unit
tests if regressions surface.

## Artifacts produced

| Layer | Files |
|---|---|
| Backend modules | `apps/api/src/auxd_api/modules/discover/__init__.py`, `routes.py`, `service.py` |
| Backend route extensions | `apps/api/src/auxd_api/modules/users/routes.py` (added `GET /users/search` before `/{handle}`), `apps/api/src/auxd_api/modules/search/routes.py` (extended with filters/sort/pagination/total) |
| Router registration | `apps/api/src/auxd_api/routers/v1.py` (added `discover_router`) |
| Shared types | `packages/shared-types/src/api.ts` (regenerated via OpenAPI codegen) |
| Frontend types | `apps/web/src/lib/social-types.ts` (`UserSearchResult`, `UserSearchResponse`, `DiscoverAlbumSummary`, `PopularAlbumItem`, `PopularThisWeekResponse`, `FromFollowsAnnotation`, `FromFollowsItem`, `FromFollowsResponse`) |
| Frontend components | `apps/web/src/components/discover/section-shell.tsx`, `album-card.tsx`, `discover-search-bar.tsx`, `popular-this-week-section.tsx`, `from-follows-section.tsx`, `discover-front-page.tsx`; `apps/web/src/components/search/decade-chip-row.tsx`, `advanced-search-client.tsx` |
| Frontend routes | `apps/web/src/app/(app)/discover/page.tsx` (replaced `<DiscoverTabs>` with `<DiscoverFrontPage>`), `apps/web/src/app/(app)/search/page.tsx` (replaced `<SearchClient>` with `<AdvancedSearchClient>`) |
| Frontend deletion | `apps/web/src/components/discover/discover-tabs.tsx` (deleted; no remaining references) |
| E2E | `apps/web/tests/e2e/tc-e2e-014-discover-rehaul.spec.ts` |
| Forge artifacts | `features/003-discover-rehaul/{research,product-spec}/README.md`, `spec.md`, `plan.md`, `.forge-status.yml` |

## Spec coverage matrix

Each FR maps to the code that implements it.

| FR | Implementation |
|---|---|
| FR-001 People/Albums toggle | `DiscoverSearchBar` `ModeToggle` |
| FR-002 Three editorial sections | `DiscoverFrontPage` |
| FR-003 Footer "→ /search" CTA | `DiscoverFrontPage.FooterCta` |
| FR-004 People autocomplete | `DiscoverSearchBar.peopleQuery` → `GET /users/search` |
| FR-005 Albums autocomplete + "More results" | `DiscoverSearchBar.albumsQuery` + `AlbumResultsList` CTA |
| FR-006 `?mode=` URL sync | `DiscoverSearchBar.onModeChange` |
| FR-007..009 Popular This Week | `PopularThisWeekSection` + `discover.get_popular_this_week` |
| FR-010..012 From Your Follows | `FromFollowsSection` + `discover.get_from_follows` (empty state included) |
| FR-013..014 Critics to Follow | `DiscoverFrontPage` reuses existing `<SuggestionsList>` |
| FR-015..016 /search route + chip filters | `apps/web/src/app/(app)/search/page.tsx` + `AdvancedSearchClient` + `DecadeChipRow` |
| FR-017 Year-range numeric input | `AdvancedSearchClient.FilterRow` |
| FR-018 24-result paginated grid | `AdvancedSearchClient` infinite query, page size 24, "Load more →" |
| FR-019 URL filter mirror | `AdvancedSearchClient.syncUrl` |
| FR-020 Result count display | `AdvancedSearchClient.Results` ("Showing X of Y") |
| FR-021..022 Privacy filters | `users.search` block-cascade filter; `discover.get_from_follows` active-status filter |
| FR-023 Rate limit | `_USERS_SEARCH_RATE_LIMIT` (30/min/user, 60/min/IP), `_DISCOVER_RATE_LIMIT` (60/min/user) |

## NFR coverage

| NFR | Implementation |
|---|---|
| NFR-001 ≤200ms p95 user-search | Mongo prefix-regex on indexed handle; block-cascade in a single follow-up query |
| NFR-002 Popular cached 5min | `cache_set(..., ex_seconds=_POPULAR_CACHE_TTL)` |
| NFR-003 From-follows cached 60s | `cache_set(..., ex_seconds=_FROM_FOLLOWS_CACHE_TTL)` |
| NFR-004 Responsive 375/768/1024/1440 | Tailwind `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 xl:grid-cols-6`; flex-wrap on filter row |
| NFR-005 Keyboard nav + visible focus | `focus-visible: outline` on every interactive element; `role=radiogroup` + `aria-checked` on toggle; `aria-pressed` on chips |
| NFR-006 Editorial fidelity | `SectionShell` matches feed/profile/email pattern; Newsreader headlines + JetBrains Mono eyebrows + 48px hairline; `--accent` burgundy for primary actions |

## Open / deferred follow-ups

1. **Atlas $search index for users** — current implementation uses a
   Mongo regex prefix match on `users.handle` (indexed) + substring
   match on `display_name` (unindexed, OK at MVP catalog size).
   Upgrade path: add `users_text_search` Atlas index mirroring the
   existing `albums_text_search` shape; route then prefers `$search`
   with regex as fallback. Documented as a v2 follow-up.

2. **Atlas user-index migration file** — when the Atlas index is
   created, capture the definition in
   `apps/api/migrations/atlas_search/users_index.json` for
   reproducibility.

3. **Genre / mood filters** — explicitly out of scope per spec; tagging
   is too sparse on the catalog to justify a v1 surface. Plan revisit
   once MusicBrainz tag enrichment lands.

4. **Result-count exactness** — `total` reflects post-filter count
   over the internal candidate set (≤50 per tier). For ultra-popular
   queries where the true total exceeds the candidate cap, the UI
   shows "Showing N of M+" to hint at unbounded depth.

5. **Backfill/popular-albums worker** — the current implementation
   computes Popular This Week on cache-miss in the request path
   (5-minute TTL). A dedicated cron worker that precomputes the
   global ranking would shave the cold-fetch cost off the first
   visitor in each 5-minute window. Deferred until the workload
   actually justifies it.

6. **TC-E2E-014 deep coverage** — current spec covers the unauth shim
   + signed-in section/toggle/filter visibility. A fuller integration
   test would seed Atlas with known albums, run a known query, and
   assert specific result ordering. Deferred until `E2E_BACKEND_REACHABLE`
   harness covers Atlas seeding.

## Gate decisions recorded

| Phase | Decision | Notes |
|---|---|---|
| 0 Problem Discovery | skipped | Problem well-defined by user (3 concrete pieces) |
| 2 Product Spec | approved | User selected Option A (Editorial Front Page) from 3 presented options |
| 3 Revalidation | approved | Consolidated with Phase 2 gate |
| 4 Bridge → spec.md | approved | spec.md drafted from approved Option A |
| 5 Plan | approved | "Approve — skip tasks.md, implement directly" |
| 5B Tasks | skipped | Per user direction; T001–T016 outline in plan.md is canonical |
| 6 Implement | completed | All 16 tasks marked complete via TaskUpdate |
| 7 Verify Full | completed | This report |

## Sign-off

Joshua Xie
