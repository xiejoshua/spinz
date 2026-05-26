# Research — Discover Rehaul

Compressed inline research (Phase 1) covering current state, comparable
products, and editorial design constraints. Sufficient context to drive
Phase 2 design options without a full multi-agent research pass.

## Current state

**Surface:** `/discover` renders `DiscoverTabs` — a 2-tab switcher
("People" / "Albums") backed by URL `?tab=`.

- **People tab** → `SuggestionsList` calls
  `GET /api/v1/users/me/suggestions?limit=10` (precomputed by the
  `suggestions_job` worker; mutual_taste + followed_by_followed +
  shared_seed + label_genre + recency scoring).
- **Albums tab** → `SearchClient` calls
  `GET /api/v1/search?q=&type=album&limit=10` — the *same* endpoint
  the Log sheet uses. Hard-capped at 10 hits; no filters, no pagination.

**Gaps the user called out:**
1. No way to search for *users* (handle/name lookup) — only the
   precomputed suggestions surface.
2. No album-level suggestions ("Popular this week", "Albums your
   follows rated").
3. Catalog search is a 10-result quick lookup — fine for logging,
   thin for browsing.

## Comparable products surveyed

| Product | User search | Album discovery | Catalog search |
|---|---|---|---|
| Letterboxd | `/members` dedicated page, handle+name fuzzy | "Popular this week" sectioned homepage + "Friends are watching" | Dedicated `/films` browse with left-rail filters (Decade, Genre, Rating, Sort) |
| Spotify | ⌘K palette, cross-entity | "Made for You" carousels | Search has tabbed results (Songs, Albums, Artists, Profiles) |
| Bandcamp | Inline header search | Heavy faceted homepage (Genre, Era, Format, Mood, Location) | Same faceted surface |
| Reddit | Universal search bar | n/a | Tabbed result page (Posts, Communities, People) |

**Pattern fit for auxd's editorial language:** Letterboxd's *sectioned
editorial homepage* + Bandcamp's *faceted catalog browse* are the
closest analogs. Spotify's ⌘K shortcut layers nicely on top of either
but is power-user-only on desktop.

## Editorial design constraints (carry forward from existing pages)

- **Typography:** Newsreader serif for display, Inter Tight for body,
  JetBrains Mono uppercase for eyebrows. No new fonts.
- **Color:** `--accent` burgundy `oklch(0.40 0.12 25)`, `--danger`
  brick `oklch(0.50 0.16 25)`, `--separator` `oklch(0.93 0 0)` for
  hairlines.
- **Section pattern:** mono eyebrow + Newsreader headline + 48px hairline
  rule, then content. Already established in feed/profile/email.
- **Tabs:** existing `TabBar` component is a horizontal underline-on-
  active pattern (see `discover-tabs.tsx`). Reusable.
- **No emojis as icons.** Lucide icons or SVG only.
- **Mobile-first:** primary breakpoints 375 / 768 / 1024 / 1440.

## Backend surface needed (irrespective of chosen design)

- `GET /api/v1/users/search?q=&limit=` — handle+display-name fuzzy
  search (Atlas `$search` on `users.handle` + `users.display_name`,
  prefix-boosted). Need rate-limit + privacy gate (block-list, soft-
  deleted users hidden).
- `GET /api/v1/discover/popular-this-week?limit=` — top albums by
  log-count in trailing 7 days (already computed for the weekly
  digest worker; just expose).
- `GET /api/v1/discover/from-follows?limit=` — albums logged or
  reviewed by users the viewer follows, dedup + sort by recency +
  follow-graph weight.
- `GET /api/v1/search` — extend with `limit` cap raised to ~50, add
  optional `decade=`, `year_min=`, `year_max=`, `sort=` (relevance /
  popularity / year), `offset=` for pagination.

## Design philosophies under consideration (Phase 2)

Three meaningfully distinct shapes will be presented to the user:

- **A. Editorial Front Page** — tab-less; single scrolling editorial
  homepage with sections; one search bar with People/Albums toggle;
  advanced search routes to a dedicated `/search` page.
- **B. Universal Search + Enriched Tabs** — keep 2-tab structure but
  Albums tab becomes a full faceted browse with left-rail filters and
  pagination; Suggestions tab interleaves people + album sections;
  user search is a sub-input inside Suggestions.
- **C. Persistent Search Header + Auto-switch Tabs** — sticky search
  bar at top with People/Albums toggle, two tabs ("For You" / "Search")
  where typing auto-switches to Search tab with contextual filters.

Tradeoffs in `product-spec/README.md`.
