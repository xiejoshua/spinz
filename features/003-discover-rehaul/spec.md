# Spec — Discover Rehaul (Option A: Editorial Front Page)

**Locked design:** Option A — "Editorial Front Page" (selected from 3
options on 2026-05-24). See `product-spec/README.md` for the rejected
alternatives (B: faceted tabs, C: persistent search + auto-switch tabs).

## Goals

1. Replace the 2-tab `/discover` switcher with a sectioned editorial
   homepage.
2. Add user-search above the suggestions surface.
3. Surface "Popular this week" + "Albums rated by people you follow"
   as discoverable sections.
4. Move the advanced/extensive album search to a dedicated `/search`
   route with filters and 30+ results.

## User Stories

### US-001 — First-time landing
*As a viewer with no follow graph yet,* when I navigate to `/discover`,
I see "This Week's Popular Albums" so I can start engaging with the
catalog without needing to seed the recommendation algorithm first.

### US-002 — Recurring landing
*As a viewer with follows,* when I open `/discover`, I see albums my
follows have rated recently so I have a fresh, social-graph-derived
surface to engage with on each visit.

### US-003 — Finding a specific person
*As a viewer who wants to follow a specific friend,* I can toggle the
search bar to "People", type their handle (or display name), and pick
them from autocomplete results that route me to their profile.

### US-004 — Quick album lookup
*As a viewer doing a casual album lookup,* I can toggle the search bar
to "Albums" and pick from autocomplete results — same lightweight
behavior as the Log sheet's search.

### US-005 — Deep / advanced album browse
*As a viewer who wants to browse the catalog by decade or by year,*
I can click "Looking for something? → /search" and land on a dedicated
advanced-search surface with decade chips, year range, and sort
controls.

### US-006 — Acting on suggestions
*As a viewer,* I see 5 precomputed follow suggestions with a clear
reason (mutual taste, followed-by-followed, etc.) and can follow or
dismiss each from the `/discover` homepage without leaving the page.

## Functional Requirements

### Page structure (`/discover`)

- **FR-001** Top section: a single search bar with a People/Albums
  toggle pill. Default mode = People.
- **FR-002** Below search: three editorial sections in order, each
  using the mono-eyebrow + Newsreader-headline + 48px-hairline pattern
  established on feed/profile/email:
  1. *This Week* — Popular Albums
  2. *From Your Follows* — Albums rated by people you follow
  3. *Critics to Follow* — Suggested follows
- **FR-003** Footer link: "Looking for something? → /search" routes to
  the advanced album search.

### Search bar behavior

- **FR-004** When People is selected: input autocompletes
  user handles + display names with debounce 200ms, min 2 chars.
  Selecting a result navigates to `/profile/[handle]`.
- **FR-005** When Albums is selected: input autocompletes album
  results identical to the existing `SearchClient` behavior (10
  results, link to `/album/[id]`). A "More results in advanced
  search →" affordance routes to `/search?q=…`.
- **FR-006** Toggle state survives URL via `?mode=people|albums`.

### Popular This Week section

- **FR-007** Renders the top N (default 12) albums ranked by log count
  in the trailing 7 days. Albums the viewer has already logged are
  suppressed.
- **FR-008** Each album card shows cover art, title, artist, and
  release year. Card links to `/album/[id]`.
- **FR-009** Empty state (zero logs in window): hide the section
  entirely, do not render an empty box.

### From Your Follows section

- **FR-010** Renders recent albums logged or reviewed by users the
  viewer follows. Dedup by album_id, sort by
  `recency × follow_graph_weight`.
- **FR-011** Each card shows cover art, title, artist, and a small
  byline: "@handle rated · 4/5" (or "@handle logged" if no rating).
- **FR-012** Empty state (viewer follows 0 users OR none of the
  followees have logged anything recently): render a soft prompt:
  *"Follow some critics to see what they're listening to."*

### Critics to Follow section

- **FR-013** Reuses existing `SuggestionsList` with default `limit=5`.
- **FR-014** Each row supports Follow / Dismiss (existing behavior).

### Advanced search (`/search`)

- **FR-015** New route at `/search` with a persistent search input
  at the top.
- **FR-016** Below input: a horizontal chip row of filters: Decade
  (multi-select chips for 2020s / 2010s / 2000s / 1990s / 1980s /
  Earlier), Sort (Relevance / Popularity / Year Newest / Year Oldest).
- **FR-017** Optional year-range numeric input (min/max) below chips.
- **FR-018** Results render as a responsive grid; default 24 results
  per page, paginated by "Load more →" button.
- **FR-019** All filter state mirrored to URL params
  (`?q=&decade=&year_min=&year_max=&sort=&offset=`) for shareable links.
- **FR-020** Result count displayed: "36 results" (or "Showing 1–24 of
  60+" when more pages exist).

### Privacy / safety

- **FR-021** User-search excludes: soft-deleted users, users in the
  viewer's block list, users who have blocked the viewer.
- **FR-022** "From Your Follows" excludes followees who have soft-
  deleted their account or who have set their account private.
- **FR-023** Server-side rate limit on `/api/v1/users/search` —
  30 requests / minute / authenticated user.

## Non-Functional Requirements

- **NFR-001** People-search p95 latency ≤ 200ms (prefix queries on
  Atlas $search index).
- **NFR-002** "Popular This Week" served from cache (5-minute TTL);
  precomputed by a cron worker that refreshes hourly.
- **NFR-003** "From Your Follows" cached per-user 60s.
- **NFR-004** Mobile-first responsive at 375 / 768 / 1024 / 1440;
  no horizontal scroll on mobile except for explicitly
  horizontally-snapping album rows.
- **NFR-005** All interactive controls keyboard-navigable; visible
  focus rings; mode toggle uses `role="radiogroup"` with `aria-checked`.
- **NFR-006** Editorial visual fidelity: Newsreader serif for section
  headlines, JetBrains Mono uppercase for eyebrows, hairline rules
  in `--separator`, burgundy `--accent` for primary actions.

## Acceptance Criteria

| ID | Criterion |
|----|----|
| AC-001 | Viewer with no follows sees "This Week" populated when ≥1 album was logged in trailing 7d |
| AC-002 | Viewer with ≥3 follows sees "From Your Follows" with ≥1 album |
| AC-003 | Toggling search mode to People and typing 2+ chars surfaces autocomplete within 300ms |
| AC-004 | Selecting a People autocomplete result navigates to `/profile/[handle]` |
| AC-005 | `/search?q=blonde&decade=2010s&sort=year_newest` reproduces results identically on reload |
| AC-006 | All sections render correctly at 375px viewport with no horizontal scroll |
| AC-007 | Tab/keyboard navigation reaches every interactive control in visual order |
| AC-008 | Searching for a soft-deleted user's handle returns no result |
| AC-009 | Search bar mode preference (People vs Albums) persists across page reloads via URL `?mode=` |
| AC-010 | "Popular This Week" suppresses albums the viewer has already logged |

## Out of scope (this feature)

- Genre/mood filters (MusicBrainz tagging is too sparse — v2)
- Cross-entity search (artists, tracks) — albums + people only
- Saved searches / search history
- Recommendation algorithm tuning beyond existing suggestions worker
- `/search` infinite-scroll (using paginated load-more for v1)
