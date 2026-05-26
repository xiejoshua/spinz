# Product Spec — Discover Rehaul

**Status:** Awaiting user gate on design selection (Phase 2 → Phase 3).

The user explicitly required: *"design several possibilities and
present them to me before implementing."* This document offers three
design philosophies — each a complete approach, not an à-la-carte menu.
Pick one to lock in as the canonical spec; revalidation will follow.

## Goals (shared across all 3 options)

1. **Find people to follow** — handle/display-name search above the
   existing precomputed suggestions row.
2. **Discover albums** — surface "Popular this week" and "Albums rated
   by people you follow" as a browseable section, not just a feed
   inclusion.
3. **Advanced catalog search** — beyond the 10-result Log search:
   year/decade filter, sort options, 30–50 results with pagination
   or infinite scroll.

## Non-goals (for this feature)

- Genre/mood filters — MusicBrainz tagging is sparse, defer to v2.
- Cross-entity universal search (artists, tracks) — albums-only stays.
- Saved searches / search history — defer.
- Recommendation tuning / "Made for you" algorithmic personalization
  beyond the existing suggestions worker.

---

## Option A — "Editorial Front Page"

**Philosophy:** Discover is the music newspaper's front page. Sectioned
editorial layout, no tabs. One search bar at the top handles both
entities with a small People/Albums pill toggle. Power users go to
`/search` for the advanced surface.

### Layout

```
┌─────────────────────────────────────────────────────┐
│ DISCOVER                                            │
│ Find people. Find albums.                           │
│                                                     │
│ [People ●] [Albums]                                 │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🔍  Search people by handle or name…            │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ THIS WEEK                                           │
│ Popular albums                                      │
│ [□][□][□][□][□][□]                                  │
│                                                     │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ FROM YOUR FOLLOWS                                   │
│ Albums rated by people you follow                   │
│ [□][□][□][□][□][□]                                  │
│                                                     │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ CRITICS TO FOLLOW                                   │
│ ◯ @lily   · Mutual taste            · [Follow]      │
│ ◯ @marcus · Followed by people you  · [Follow]      │
│ ◯ @noor   · Shares a critic         · [Follow]      │
│                                                     │
│ Looking for something specific? → /search           │
└─────────────────────────────────────────────────────┘
```

### Pros
- Strongest editorial feel; matches the newspaper analogy already
  established on feed and profile.
- Low cognitive load — no tab nav decisions.
- "Sticky" homepage that's worth returning to even without intent.

### Cons
- Advanced search lives on a separate `/search` route — extra click
  for power users.
- Single-bar People/Albums toggle is a small interaction (some users
  may miss it).

### Routes touched
- `/discover` — single-page editorial layout (this file).
- `/search` — new dedicated advanced-search route (or reuse with
  expanded params).

---

## Option B — "Universal Search + Enriched Tabs"

**Philosophy:** Keep the existing 2-tab structure but pour content
into both. **Suggestions** tab becomes a rich curated digest
(people + albums interleaved). **Albums** tab becomes the full faceted
browse surface (Letterboxd `/films`-style).

### Layout

```
┌─────────────────────────────────────────────────────┐
│ DISCOVER                                            │
│                                                     │
│ [Suggestions ●] [Albums]                            │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ ── TAB: Suggestions ──                              │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🔍  Search for people…                          │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ POPULAR THIS WEEK                                   │
│ [□][□][□][□]                                        │
│                                                     │
│ FROM YOUR FOLLOWS                                   │
│ [□][□][□][□]                                        │
│                                                     │
│ PEOPLE TO FOLLOW                                    │
│ ◯ @lily   · reason  · [Follow]                      │
│ ◯ @marcus · reason  · [Follow]                      │
│                                                     │
│ ── TAB: Albums ──                                   │
│ ┌──────────────┐ ┌────────────────────────────────┐ │
│ │ FILTERS      │ │ 🔍 Search albums…              │ │
│ │ ──────       │ │ ──────                         │ │
│ │ Decade       │ │ [□][□][□][□]                   │ │
│ │  ☐ 2020s     │ │ [□][□][□][□]                   │ │
│ │  ☐ 2010s     │ │ [□][□][□][□]                   │ │
│ │  ☐ 2000s     │ │ [□][□][□][□]                   │ │
│ │  ☐ 1990s     │ │ [□][□][□][□]                   │ │
│ │  ☐ Earlier   │ │ [□][□][□][□]                   │ │
│ │              │ │                                │ │
│ │ Year range   │ │ [Load more →]                  │ │
│ │  [____][____]│ │                                │ │
│ │              │ │ 36 results                     │ │
│ │ Sort         │ │                                │ │
│ │  Relevance ▾ │ │                                │ │
│ └──────────────┘ └────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

Mobile: left rail collapses to a `[Filters ▾]` sheet trigger above
the result grid.

### Pros
- Maximum power for the Albums tab — best surface for the user's
  "more extensive and advanced" ask.
- Clean philosophical split: "discover passively" (Suggestions) vs
  "search actively" (Albums).
- Existing TabBar reused; lowest disruption to existing patterns.

### Cons
- User-search nested inside Suggestions tab (not above tabs) — slightly
  less prominent than the explicit ask.
- Left-rail filter pattern is desktop-strong, mobile-OK-with-work.
- Two distinct search bars (one for people in Suggestions, one for
  albums in Albums tab) — two different mental models.

### Routes touched
- `/discover?tab=suggestions` (default, was `people`).
- `/discover?tab=albums` (now with filter params:
  `?tab=albums&decade=2010s&sort=popularity`).

---

## Option C — "Persistent Search Header + Auto-switch Tabs"

**Philosophy:** One persistent search bar at the top of the page with
a People/Albums toggle. Two tabs underneath: **For You** (curated when
idle) and **Search** (active results when typing). Typing in the bar
automatically switches the tab to Search.

### Layout

```
┌─────────────────────────────────────────────────────┐
│ DISCOVER                                            │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🔍  Search…              [People] [Albums ●]   │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ [For You ●] [Search]                                │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ ── TAB: For You ──                                  │
│ POPULAR THIS WEEK                                   │
│ [□][□][□][□][□][□]                                  │
│                                                     │
│ FROM YOUR FOLLOWS                                   │
│ [□][□][□][□][□][□]                                  │
│                                                     │
│ PEOPLE TO FOLLOW                                    │
│ ◯ @lily   · reason  · [Follow]                      │
│ ◯ @marcus · reason  · [Follow]                      │
│                                                     │
│ ── TAB: Search (auto when typing) ──                │
│ (when Albums toggled)                               │
│ [Decade ▾] [Year ▾] [Sort: Relevance ▾]             │
│ [□][□][□][□][□]                                     │
│ [□][□][□][□][□]                                     │
│ [□][□][□][□][□]                                     │
│ [Load more →]                                       │
│                                                     │
│ (when People toggled)                               │
│ ◯ @lilyclark   · Lily Clark   · [Follow]            │
│ ◯ @lilyjones   · Lily Jones   · [Follow]            │
│ ◯ @lilybeats   · Lily Beats   · [Follow]            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Pros
- Single search bar serves both entities — clearest information
  architecture; matches the user's explicit "search above suggestions"
  framing most literally.
- Filters surface as a horizontal chip row (mobile-friendly), not a
  desktop-only left rail.
- Tab auto-switch on typing is a natural, modern interaction (matches
  GitHub, Notion, Linear search behavior).

### Cons
- Tab auto-switching is invisible UX magic — needs a subtle indicator
  (e.g. tab label changes "Search · 36 results").
- Less editorial-feeling than Option A; more "app dashboard."
- People search shares vertical space with album results — minor design
  challenge for the unified empty/loading state.

### Routes touched
- `/discover` — default (For You).
- `/discover?q=blonde&type=album&decade=2010s` — Search tab with state
  preserved in URL.

---

## Decision matrix

| Concern | Option A | Option B | Option C |
|---|---|---|---|
| Editorial feel | ✅ Strongest | ◐ Mixed | ◐ Mixed |
| Advanced album search power | ◐ Routes away | ✅ Full left-rail | ✅ Chip-row filters |
| User-search prominence | ✅ Top of page | ◐ Inside tab | ✅ Top of page |
| Mobile parity | ✅ Native | ◐ Filter sheet needed | ✅ Native |
| Disruption to existing patterns | High (no tabs) | Low (same tabs) | Medium (new tab labels) |
| Best for power user | ◐ | ✅ | ✅ |
| Best for casual return-visitor | ✅ | ◐ | ◐ |

## Open questions (deferred to revalidation)

- **Default landing:** which surface should `/discover` open on for
  first-time visitors with no follow graph yet? (Probably "Popular
  this week.")
- **Empty states:** how do we treat "no follows yet" for the "From
  your follows" section? (Hide vs. show with prompt to follow.)
- **Recently logged dedup:** should "Popular this week" suppress
  albums the viewer has already logged?
- **Result count display:** "36 results" vs. "Showing 1-24 of 36"?
- **Pagination model:** Load-more button vs. infinite-scroll
  intersection observer? Letterboxd uses both depending on surface.

---

## Recommendation

The user emphasized two things: (1) **user search above suggestions**
(literal phrasing) and (2) **more extensive/advanced than the simple
log search**. Those two requirements pull in slightly different
directions:

- (1) favors **Option A** or **Option C** (search bar above the
  tabs/sections).
- (2) favors **Option B** (left-rail faceted browse is the most
  "extensive" surface).

**Option C** is the strongest synthesis: persistent top search bar
matches (1), chip-row filters in the Search tab deliver on (2), and
the auto-switch behavior keeps the page coherent. **Option B** is
the choice if the user values the dedicated "browse the catalog"
power-surface above all else. **Option A** is the choice if the
editorial feel is non-negotiable.

Awaiting selection.
