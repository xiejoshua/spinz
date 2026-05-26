# Plan — Discover Rehaul (Option A: Editorial Front Page)

Maps spec.md to concrete files, endpoints, components, and tasks.
Awaiting user approval before task breakdown (Phase 5B) and
implementation (Phase 6).

## Architecture overview

```
                              /discover  (server component)
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
   <DiscoverSearchBar>     <PopularThisWeekSection>  <FromFollowsSection>
   (client, debounced)     (client, RQ-fetched)      (client, RQ-fetched)
              │                     │                     │
              │            GET /discover/popular   GET /discover/from-follows
              │
        GET /users/search          <SuggestionsList>  (existing)
        GET /search?type=album            │
                                  GET /users/me/suggestions

                              /search  (server component)
                                    │
                        <AdvancedSearchClient>
                                    │
                  GET /search?q=&decade=&sort=&offset=&limit=
```

## Backend endpoints (FastAPI)

### NEW: `GET /api/v1/users/search`
- **Module:** `apps/api/src/auxd_api/modules/users/routes.py` (extend) or new `search.py` sub-module
- **Query params:** `q` (str, min_length=2, max_length=80), `limit` (int, 1–20, default=8)
- **Auth:** required
- **Behavior:**
  - Atlas `$search` against `users.handle` (prefix-boosted, weight 3) +
    `users.display_name` (fuzzy, weight 1).
  - Exclude soft-deleted (`deleted_at` not null), block-list (viewer
    blocked OR viewer blocked-by).
  - Order by relevance score; cap at `limit`.
- **Response:** `{ "results": [{"id", "handle", "display_name", "avatar_url"}] }`
- **Rate limit:** 30 req/min/user (existing middleware)
- **Index:** new Atlas `$search` index `users_text` covering `handle`,
  `display_name`. Migration script under `apps/api/migrations/` (or
  document the Atlas console action if migration tooling isn't in use).

### NEW: `GET /api/v1/discover/popular-this-week`
- **Module:** new `apps/api/src/auxd_api/modules/discover/routes.py`
- **Query params:** `limit` (int, 1–20, default=12)
- **Auth:** required
- **Behavior:**
  - Aggregate `logs` collection by `album_id` over trailing 7 days.
  - Exclude albums the viewer has already logged.
  - Sort by log count desc, tiebreak by most-recent-log.
  - Cached at the application layer (5 min TTL by `viewer_id`-scoped key).
- **Response:**
  `{ "albums": [{"id", "title", "artist_name", "cover_art_url", "release_year"}], "computed_at": ISO }`
- **Worker:** `apps/api/src/auxd_api/workers/popular_albums_job.py` — cron
  every 60 min to precompute the global ranking (then the endpoint just
  filters by viewer-already-logged).

### NEW: `GET /api/v1/discover/from-follows`
- **Module:** `apps/api/src/auxd_api/modules/discover/routes.py`
- **Query params:** `limit` (int, 1–20, default=12)
- **Auth:** required
- **Behavior:**
  - Pull viewer's followee user_ids.
  - Aggregate `logs` + `reviews` from those user_ids in trailing 30 days.
  - Dedup by `album_id`; sort by
    `0.7 * recency_score + 0.3 * follow_weight`.
  - Each album carries one annotation: "@handle rated · 4/5" or
    "@handle logged" (most recent activity from any followee).
- **Response:**
  `{ "items": [{"album": {…}, "annotation": {"actor_handle": "lily", "verb": "rated", "rating": 4}}] }`
- **Cache:** per-viewer 60s.

### EXTEND: `GET /api/v1/search`
- **Module:** `apps/api/src/auxd_api/modules/search/routes.py` (existing)
- **New query params:**
  - `decade` (str | list, e.g. "2010s,2020s")
  - `year_min` (int, 1900–current_year)
  - `year_max` (int, 1900–current_year)
  - `sort` (enum: `relevance` (default) | `popularity` | `year_newest` | `year_oldest`)
  - `offset` (int, default=0)
- **Limit cap:** raise from `le=25` to `le=50`.
- **Response shape:** add `total` (when known) and `has_more` for
  paginated client UX.
- **Atlas index:** existing albums index OK; the `decade` filter applies
  on `release_year` numeric bucket. May need a `$search` compound
  query with `near`-on-release_year if Atlas-only.

## Frontend components (Next.js 15 App Router)

### Files to change

| File | Change |
|---|---|
| `apps/web/src/app/(app)/discover/page.tsx` | Replace `<DiscoverTabs />` with `<DiscoverFrontPage />` |
| `apps/web/src/components/discover/discover-tabs.tsx` | **Delete** (replaced) |
| `apps/web/src/components/discover/discover-front-page.tsx` | **New** — layout shell |
| `apps/web/src/components/discover/discover-search-bar.tsx` | **New** — single input + People/Albums toggle pill |
| `apps/web/src/components/discover/section-shell.tsx` | **New** — reusable eyebrow + headline + hairline wrapper |
| `apps/web/src/components/discover/popular-this-week-section.tsx` | **New** |
| `apps/web/src/components/discover/from-follows-section.tsx` | **New** |
| `apps/web/src/components/discover/suggestions-list.tsx` | Keep; called from new front-page shell as "Critics to Follow" |
| `apps/web/src/components/discover/album-card.tsx` | **New** — small editorial card used in both album sections |
| `apps/web/src/app/(app)/search/page.tsx` | **New** — advanced search route |
| `apps/web/src/components/search/advanced-search-client.tsx` | **New** — query input + chip filters + sort + load-more |
| `apps/web/src/components/search/decade-chip-row.tsx` | **New** |
| `apps/web/src/components/search/search-client.tsx` | Keep (used by Log sheet + the People/Albums search bar autocomplete) |
| `apps/web/src/lib/social-types.ts` | Extend with `UserSearchResult`, `PopularAlbumsResponse`, `FromFollowsResponse` |
| `packages/shared-types` | Regen after API changes (`pnpm --filter @auxd/shared-types codegen`) |

### Component contracts

#### `<DiscoverSearchBar>` (client)
- Props: none (state owned internally + URL sync via `useSearchParams`).
- State: `mode: "people" | "albums"`, `query: string` (debounced 200ms).
- People mode: calls `GET /users/search?q=…`; renders `<UserAutocompleteResults>`.
- Albums mode: calls `GET /search?q=…&type=album&limit=10`; renders
  `<AlbumAutocompleteResults>` + "More results in advanced search →"
  link to `/search?q=…`.
- Toggle is `role="radiogroup"` with `aria-checked` on each pill.

#### `<SectionShell>` (server-renderable)
- Props: `eyebrow: string`, `headline: string`, `children: ReactNode`.
- Renders: mono uppercase eyebrow + Newsreader headline + 48px hairline
  rule (`bg-[--separator]`) + content slot. Matches the pattern
  already used in feed/profile/editorial-emails.

#### `<PopularThisWeekSection>` (client)
- React Query fetches `GET /discover/popular-this-week?limit=12`.
- Renders 6–12 `<AlbumCard>` items in a responsive grid (mobile:
  2-up; tablet: 3-up; desktop: 6-up). Loading: shimmer skeletons.
  Empty: hide section.

#### `<FromFollowsSection>` (client)
- React Query fetches `GET /discover/from-follows?limit=12`.
- Same grid as Popular section, but each `<AlbumCard>` shows the
  annotation byline ("@lily rated · 4/5").
- Empty when viewer follows 0 users: prompt "Follow some critics
  to see what they're listening to."

#### `<AlbumCard>` (server-renderable)
- Props: `album: AlbumSummary`, `annotation?: AlbumAnnotation`.
- Editorial card: cover art (1:1, `next/image`), title (Newsreader 16/18),
  artist (Inter Tight, muted), optional annotation (Inter Tight 12, accent).
- Whole card is a `<Link>` to `/album/[id]`.

#### `<AdvancedSearchClient>` (client)
- URL-driven state via `useSearchParams` + `router.replace`.
- Top: query input (auto-focused on page load).
- Below: `<DecadeChipRow>` (multi-select chips), `<YearRangeInput>`
  (two number fields), `<SortSelect>` dropdown.
- Results: grid of `<AlbumCard>` (24 per page) + "Load more →" button
  appending to existing list (no scroll jump).
- Empty state: editorial "No matches. Try a different decade or a
  shorter query."

## Data model

No new collections. No schema migrations. Adds:
- One Atlas `$search` index on `users` (handle, display_name).
- Optionally a `popular_albums_cache` collection if we want
  out-of-process caching beyond Redis (defer to implementation —
  Redis is preferred since we already use Upstash).

## NFR implementation notes

- **Caching:** use existing Upstash Redis client. Keys:
  `discover:popular:v1:{viewer_id}` (5min), `discover:from-follows:v1:{viewer_id}` (60s).
- **Rate limit:** people-search hooks the existing token-bucket
  middleware; new bucket key `users.search`.
- **a11y:** verify with axe-core during E2E; ensure focus rings on the
  People/Albums toggle, on each result row, on filter chips.
- **Telemetry:** PostHog events
  - `discover.search.mode_toggle` `{mode}`
  - `discover.search.user_clicked` `{result_position}`
  - `discover.popular.album_clicked` `{album_id, position}`
  - `discover.from_follows.album_clicked` `{album_id, position, follow_handle}`
  - `discover.cta.advanced_search`
  - `search.advanced.filter_applied` `{decade, sort}`
  - `search.advanced.load_more` `{offset}`

## Task outline (full breakdown comes in tasks.md)

Backend
- T001 Add `GET /api/v1/users/search` + Atlas index — **S**
- T002 Add `GET /api/v1/discover/popular-this-week` + cron worker — **M**
- T003 Add `GET /api/v1/discover/from-follows` — **M**
- T004 Extend `GET /api/v1/search` with decade/year/sort/offset/total — **M**
- T005 Regen shared-types — **XS**

Frontend
- T006 `<SectionShell>` reusable component — **XS**
- T007 `<AlbumCard>` reusable component — **S**
- T008 `<DiscoverSearchBar>` with People/Albums toggle + autocomplete — **L**
- T009 `<PopularThisWeekSection>` — **S**
- T010 `<FromFollowsSection>` with annotation byline — **M**
- T011 `<DiscoverFrontPage>` + delete `<DiscoverTabs>` — **S**
- T012 `/search` route + `<AdvancedSearchClient>` + `<DecadeChipRow>` — **L**
- T013 PostHog events wiring — **XS**
- T014 Mobile responsive QA + adjustments — **S**

Cross-cutting
- T015 E2E specs: discover sections render, user search autocomplete,
  advanced search filter+load-more roundtrip — **M**
- T016 Verify Full (Phase 7) — **S**

**Estimated total:** ~14 tasks, mostly S/M with two L items
(`<DiscoverSearchBar>` and `<AdvancedSearchClient>`).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Atlas $search on users may not exist in current cluster tier | M | M | Verify tier supports $search; fallback to regex prefix match on indexed handle |
| Cron worker for popular-this-week adds operational surface | L | L | Reuse existing worker harness; simple aggregation |
| "From Your Follows" cold-start (viewer follows 0) UX | M | L | Soft prompt — covered in FR-012 |
| /search filter combinations explode result count display | L | M | Show "60+" instead of exact count when >`limit*5` |

## Open questions for revalidation

1. Do we delete the existing `/discover?tab=albums` query-string compat
   shim, or keep `?tab=…` redirects for a release cycle?
2. Should the People/Albums toggle default to People (per spec) or
   remember last-used per-user via localStorage?
3. Is a 12-album "Popular This Week" grid the right density, or should
   it be 6 with a "See more popular →" link to `/search?sort=popularity`?
4. For the "More results in advanced search →" link inside Albums
   autocomplete, should it carry the current query into `/search?q=`
   or just route to the empty advanced surface?

---

**Next gate:** approve this plan → proceed to tasks.md breakdown
(Phase 5B) or to implementation directly (skip 5B if you prefer).
