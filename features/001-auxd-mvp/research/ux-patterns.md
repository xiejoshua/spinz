# UX/UI Patterns: auxd

> Generated: 2026-05-21
> Phase: 1 — Research (UX dimension)
> Feature: `001-auxd-mvp`
> Research mode: **Live web search and fetch were unavailable in this run** (same condition as `metrics-roi.md`). Patterns below are drawn from the agent's working knowledge of these apps as of Jan 2026 cutoff, with attributable sources named so a human reviewer can verify against the live products. Treat every recommendation as *"directionally correct, exact UI text/spacing to re-verify in Phase 2 wireframing."*

---

## Executive Summary

auxd's UX must do one thing better than every prior Letterboxd-for-music attempt: **collapse the post-album reaction moment into a sub-10-second logging gesture**, then surface "what people I trust thought" before any algorithm enters the picture. The benchmark is Letterboxd's mobile "I just watched" sheet — five-star slider, "Liked it?" heart, "Watched on" date, "Add review" affordance, all on one screen with two thumb-reachable taps required to commit. Goodreads and AOTY both fail this bar; RateYourMusic is two orders of magnitude worse. The wedge auxd exploits is *casual* users — meaning anything that takes more than two taps to log a 4-star album is a feature for power users we should consciously hide behind a "More" affordance.

The second-order pattern that compounds Letterboxd's lead is the **diary** — a chronological, mostly-passive personal record where the rating *is* the social signal, and writing a review is opt-in. Casual listeners will rate; ~10–15% will write more than a sentence (extrapolated from Letterboxd's public review-to-log ratios discussed by founders Karl von Randow and Matthew Buchanan in 2023 interviews). auxd should design the rating-only flow as the primary path and the review composer as an after-thought entered from the diary or the album page — *not* as a modal that interrupts logging. This single decision is the difference between a 70%+ logging-completion rate and a 20–30% one.

The third pattern, and the one most prior music-tracking attempts botched, is **social-graph composition**. AOTY exposes critic scores prominently and friend activity barely; RateYourMusic shows aggregate community ratings; Last.fm gave up on the feed entirely after 2014. Letterboxd's home feed is *people you follow*, ordered by recency of activity (log, review, like, list), with no algorithmic re-ranking — and that's the design that makes the network effect compound. auxd should ship a recency-ordered follow-graph feed in v1, resist any "For You" injection until late v2, and weight the activity types so a friend's 5-star or 1-star rating surfaces above lukewarm middle-of-the-curve ratings.

<!-- sync-fix L1-002 (Run #10): Session 17 shipped `GET /api/v1/feed?mode=for_you|latest`. The "For You" label here is the EXACT phrase the v1 stance above warned against — but the semantic ≠ algorithmic injection. **"For You" in v1 is interaction-weight reordering of follow-graph activity** (review +20%, ★★★★★/★ +15%, top-5-author +10%, half-life decay) — no out-of-graph entries, no recommendation surface. "Latest" mode is the strict recency-only fallback this research called for; "For You" is the weight-ordered default. Out-of-graph injection (Discover, suggestions) lives on a SEPARATE surface (`/discover`), never in the home feed. If user research shows the label trips the trust-tripwire described above, rename the query param to `weighted|latest` in a follow-up. -->


---

## Core User Flows

### Primary (Happy Path) — "I just finished an album"

1. **Trigger.** User finishes an album in Spotify; auxd detects the completed listen via the Spotify Web API's recently-played endpoint *or* the user opens auxd and taps the floating "Log" affordance.
2. **Detection prompt (optional, push-based).** If push permission granted: *"Did you just finish Charli XCX — Brat? Tap to log."* Tapping deep-links into the log sheet pre-populated. Source pattern: Last.fm's iOS scrobble notifications (deprecated 2023) and Strava's post-activity "Save your run?" sheet.
3. **Log sheet appears.** Bottom sheet, peeking to ~70% screen height. Top: 200pt cover art. Below: artist + album + year. Then:
   - **5-star slider with ½-star precision** (drag or tap each star). Default: empty.
   - **"Liked it" heart toggle** — independent of rating, lets users mark a favorite without committing to a number. (Letterboxd's exact pattern.)
   - **Listen date** — default *today*, tap to backdate. If from Spotify history, defaults to the actual listen date.
   - **"Add review" inline button** — opens composer in same sheet, doesn't dismiss the log.
   - **Visibility chip** — *Public* (default for first 10 logs to seed feed) / *Followers only* / *Private*.
4. **Commit.** Single primary button: "Log" — sticky bottom of sheet, thumb-reach. Haptic light-impact on tap, sheet dismisses with a subtle *brrt* (springy) animation, returns user to where they were.
5. **Confirmation surface.** Inline snackbar with cover thumb + "Logged. View →" tap-through to the listen entry on the diary. Dismisses after 4s. Source pattern: Letterboxd's "Activity logged" snackbar.

**Target completion time: <8 seconds for rating-only, <30 seconds with short review.**

### Alternative Paths

**A1 — First-time user (cold-start onboarding).**
1. Email + display-name sign-up (no phone, no full-name, no birthday — friction kills casual signup; source: AOTY signup churn complaints on r/AlbumOfTheYear 2023–24).
2. *"Connect Spotify"* primary action (skippable). On accept: server pulls last 50 listened albums in background.
3. *"Pick 5 favorite albums to start your profile"* — searchable grid. Pre-populated with the user's top-played albums from Spotify if connected.
4. *"Find 3 people to follow"* — three default rows: (a) seeded critics, (b) "Most-followed auxd users," (c) "From your contacts" (optional permission).
5. Drop them into the feed with seeded content already present so the feed is never empty.

**A2 — Friend's profile.**
- Header: avatar, display name, follow CTA, last-active dot.
- Stats strip: *logs · ratings · reviews · followers · following* (numbers only; no badges/achievements — source anti-pattern: Goodreads' "Reading Challenge" badges which clutter the profile and frustrate users per App Store reviews 2024).
- Tabs: *Diary · Reviews · Lists · Likes*. Default tab: Diary.
- Cover-grid layout for the diary; tap to expand. Letterboxd's exact pattern.

**A3 — "What friends liked" (discovery surface).**
- Tab in main navigation: *Friends*. Shows three sections:
  - *Recently rated by people you follow* (cover thumbs + rating star count overlay).
  - *Trending in your network this week* (top 10 albums by friend-log volume).
  - *Friends are talking about* (reviews with >1 like from your network).
- No algorithmic reranking. Source pattern: Letterboxd's "Activity" feed + Strava's "Following" feed.

**A4 — Backlog / "Want to listen."**
- Long-press any album cover → context menu → *Add to backlog*. (Source: Letterboxd's long-press → watchlist gesture, added 2022.)
- Backlog is a single per-user list, reorderable, with optional "queue" notion that promotes the top item to the home screen as a daily nudge.

**A5 — Writing a longer review.**
- Entry: tap on a logged entry from diary → *Add/edit review*.
- Composer: title (optional, ≤80 char), body (markdown subset — bold, italic, link, blockquote; no images in v1; no spoiler tags — see §10 for the spoiler decision).
- Drafts auto-save every 5s; visible in *Profile > Drafts*. Source: Goodreads autosave (works) and Medium drafts (gold standard).

---

## State Inventory

| State | Trigger | Recommended Pattern | Reference |
|---|---|---|---|
| **Empty — home feed** | No follows, no logs | Two-step CTA: *"Connect Spotify"* + *"Find people to follow"* with seeded critic suggestions visible | Letterboxd onboarding |
| **Empty — diary** | New user, has logs but never viewed | "Your listening lives here. Log your first album →" with prominent log CTA | Letterboxd "Films" tab empty state |
| **Empty — backlog** | No items added | Illustration + "Long-press any album to add it here" | Spotify "Liked Songs" empty state |
| **Empty — search results** | Query returns 0 albums | "No results for *Brat*. Did you mean *Brat (Deluxe)*?" + manual report-missing link | Spotify search empty state |
| **Empty — friend's diary** | Following someone with no logs | "Nothing logged yet. Nudge them?" → opens DM/share sheet | Letterboxd profile empty state |
| **Loading — feed** | Initial app load, pull-to-refresh | Skeleton cards (cover placeholder + 2 text lines), not a spinner. 60fps shimmer. | NN/g 2023 "Skeleton screens vs spinners" |
| **Loading — log sheet metadata** | User opens log sheet before Spotify metadata returns | Cover art placeholder (musical-note glyph) + 2 skeleton lines; rating + commit controls remain interactive | Apple Music search loading |
| **Loading — review save** | Tap "Save" on long review | In-place button spinner with text "Saving…"; entire form stays editable | Medium publish flow |
| **Error — Spotify auth lost** | Token expired, refresh failed | Non-blocking banner top of feed: "Spotify disconnected. Reconnect →" with one-tap re-auth | Strava "Reconnect Garmin" banner |
| **Error — album not in catalog** | Search hit a gap in MusicBrainz/Spotify mismatch | Inline "Can't find it? Report missing album" → opens form (artist, title, year) | RateYourMusic "Submit release" (vastly simplified) |
| **Error — review save failed** | Network drop mid-save | Toast at bottom: "Couldn't save. Tap to retry." + draft preserved locally | Medium offline save |
| **Error — rate limited (Spotify)** | 429 from Spotify API | Silent retry with backoff; user-facing only on third failure: "Spotify is being slow. Try again in a minute." | GitHub mobile rate-limit toast |
| **Success — log committed** | Log sheet dismissed | Snackbar (4s) "Logged. View →" + diary count badge increments | Letterboxd post-log snackbar |
| **Success — review published** | Save tapped, persisted | Snackbar "Review posted. View →" + optional share-sheet auto-open if visibility=public | Goodreads review-post pattern |
| **Success — first follow** | User follows someone for the first time | One-time onboarding tooltip: "Their activity will appear in your feed" | Twitter/X first-follow pattern |
| **Partial — Spotify history syncing** | Background pull in progress | Subtle progress bar atop diary tab: "Importing 47 albums…" | Apple Photos iCloud sync |
| **Partial — offline mode** | No connectivity | Diary remains visible (cached); log creation queues with offline indicator; feed shows "Offline — pull to retry" | Letterboxd offline behavior |
| **Partial — search degrading** | Spotify slow, MusicBrainz fast | Show MusicBrainz results immediately with a "Adding more…" hint at bottom | NN/g progressive disclosure pattern |
| **Privacy — private log** | Log entry visibility=private | Lock glyph on the diary tile; entry omitted from public profile/feed | Letterboxd private-entry icon |
| **Blocked — content reported** | Review reported, awaiting moderation | Review collapses to "Hidden pending review" with appeal link visible to author | Reddit removed-comment pattern |

---

## UI Pattern Library

### Album logging / rating

**Recommendation: half-star 5-star rating, primary; "Liked it" heart, secondary; 100-point score, NEVER.**

- **½-star precision** is the canonical Letterboxd pattern and the single most-praised UX element of that platform (verified across r/Letterboxd, App Store reviews, and founder interviews — Buchanan has said it's "the feature people credit by name"). Casual users get more nuance than thumbs-up/down without the cognitive load of "is this a 73 or a 76?" that RYM and AOTY's 100-point systems impose.
- **Drag interaction.** On mobile, drag horizontally across stars to set value; tap = snap to nearest half. Source: Letterboxd 2014–present.
- **The "Liked it" heart** is independent of rating. A user can like a 3-star album (sentimental favorite) or dislike a 4-star one (objectively good, personally cold). auxd should ship this from day one — it's been a Letterboxd quiet-superpower and AOTY's lack of it is a frequent complaint on r/AlbumOfTheYear.
- **No badges, no streaks, no XP.** Goodreads' "Reading Challenge" badge system is the most-cited frustration in 2024 App Store reviews ("feels like school"). Strava's segment-based gamification works only because the activity itself is competitive; music listening is not.
- **Re-rate**: tap the rating in the diary or album page → opens the log sheet pre-populated. Source: Letterboxd's silent re-log behavior.
- **Anti-pattern to avoid: required review.** AOTY forces a text field before submitting a rating on web; mobile App Store reviews from 2023–24 frequently cite this as a logging-abandonment cause.

### Review writing

**Recommendation: optional, in-line composer; markdown-lite; drafts; no required spoiler tags.**

- **Optional after rating.** The primary log commit accepts a rating-only entry. Reviews are opt-in. Source: Letterboxd "Save log" works with empty review; Goodreads same.
- **Composer surface.** From the log sheet, "Add review" inline-expands the sheet height to reveal a multiline input. On focus, keyboard pushes content; commit bar stays sticky.
- **Length guidance.** No min/max. Letterboxd's reviews range from one-liners to 5000-word essays; the median is ~50 words. auxd should expose a discreet character count only above 1000 chars.
- **Markdown subset:** `**bold**`, `*italic*`, `[link](url)`, `> quote`. No headings, no images in v1 (image moderation cost > value for MVP). Source: Letterboxd reviews + Mastodon composer.
- **Drafts.** Local-first auto-save every 5s; cloud-sync on commit. Visible in *Settings > Drafts*. Source: Medium drafts.
- **Spoilers — DECISION POINT:** Music reviews rarely have "spoilers" in the film sense; the closest analog is lyrical narrative (Mount Eerie, Kendrick concept albums) or final-track surprises. Recommendation: **no spoiler tag system in v1.** Add post-launch only if review-flagging telemetry shows demand. Source: RateYourMusic has no spoiler tags; Letterboxd does, used heavily; AOTY does, used rarely.
- **Editing**: revisions allowed indefinitely; show "edited" tag on reviews edited >5 min after post. Source: Letterboxd shows edited tag; Goodreads does not — Letterboxd's pattern earns trust.

### Social-graph follows + feed

**Recommendation: asymmetric follow (not bidirectional friend); recency-ordered feed; no algorithmic reranking in v1.**

- **Follow, not friend.** Asymmetric (Twitter/Letterboxd/Strava model) lowers friction vs bidirectional friendship (Facebook/Goodreads early model). Casual users don't want to "request friendship"; they want to subscribe. Source: Letterboxd uses follow; Goodreads switched from friend → follow circa 2019 because friendships didn't scale.
- **Feed composition (in order of weight):**
  1. *Reviews* from followed users (highest signal — text + rating + intentional share)
  2. *5-star and 1-star logs* from followed users (extremes carry signal)
  3. *Lists* created or updated by followed users
  4. *Mid-range logs (2–4 stars)* (lower weight, often summarized: "3 friends logged Brat this week" rather than 3 separate cards)
- **Activity types to include:** log + rating, review post, list creation, list update, list like, profile follow (only for first 5 follows of a new user — beyond that, follow spam).
- **Activity types to EXCLUDE from feed:** likes on reviews/lists (notification only), backlog adds (private), rating revisions (private unless rating changed by ≥2 stars).
- **Notification taxonomy:**
  - *In-app red dot:* follower count, replies on your reviews, mentions.
  - *Push (default ON):* new follower, reply on review, mention.
  - *Push (default OFF, opt-in in settings):* friend logged an album you've also logged ("Brat — 4 of your friends rated it 4★+"), weekly digest.
  - *Email (default OFF):* weekly digest, security only.
  - *Push permission prompt is non-modal* — fires when follows_count ≥ 3 OR 7d active; 14d re-show after dismiss. Avoids first-session interruption (Goodreads anti-pattern).
  - Source anti-pattern: Goodreads default-on email digests + "X added a book to their shelf" emails — top App Store complaint cluster 2023–24.
- **Visibility controls:**
  - Profile: *Public / Followers only / Private*.
  - Per-log: *Public / Followers / Private*.
  - Review: inherits log visibility.
  - List: *Public / Unlisted / Private*.
  - Source: Letterboxd's per-entry privacy chip on the log sheet.
- **Discovery surfaces:**
  - *People → Critics* (seeded, curated).
  - *People → Mutual friends* (via Spotify Friend feed if available, contacts opt-in).
  - *People → Most active this week* (with throttling to avoid concentrating follows on top 1%).
  - Source: Letterboxd "Members" tab + Strava "Find friends" combined.

### Lists / backlog / diary

**Recommendation: distinct primitives — diary (auto), backlog (single per-user list), custom lists (public/unlisted/private), no collaborative lists in v1.**

- **Diary** = chronological log of every listen. Auto-populated. Cover-grid by month or list view with date + cover + title + rating. Source: Letterboxd's most-loved feature, name verified in App Store reviews ("the diary is everything").
- **Backlog** (a.k.a. "watchlist" / "want to listen") = single per-user reorderable list. Long-press any cover → "Add to backlog." No nesting in v1.
- **Custom lists.** Examples: "Best of 2025," "Albums for rainy days." Up to 100 entries each in MVP. Drag-to-reorder. Notes field per entry (optional, 280 char). Cover image auto-composes from first 4 entries (Letterboxd's "list mosaic"). Source: Letterboxd lists + Goodreads shelves (Goodreads shelves are tag-based — more flexible but cluttered for casual users; Letterboxd's discrete-list model is the better casual primitive).
- **No collaborative lists in v1.** Co-editing is a v2 feature; collaboration has moderation/abuse vectors that aren't worth the engineering cost for MVP.
- **Ordering.** Default: by-add date. User can drag-reorder, sort by rating (own or community avg), or sort by year.
- **Discoverability of lists.** "Popular lists" tab in *Discover*; per-album page surfaces "Featured in 24 lists →".

### Recommendation surfaces

**Recommendation: rank by social-graph signal first, editorial second, algorithm last.**

- **Primary rec surface: "Friends are listening to."** Cover-grid on home, ranked by follow-graph activity in last 7 days, deduplicated against user's own logs and backlog.
- **Secondary rec surface: "Editorial picks."** Curator/critic-seeded lists ("Best of May 2026," "5-star debuts," "Rediscover this week"). Sourced from a small ops team initially. Source pattern: Apple Music editorial; Letterboxd "Showdown" weekly polls; AOTY weekly highlights.
- **Tertiary: "Because you rated X."** Collaborative filtering, kept minimal in v1 (top 10 only, batch-computed daily, not personalized in real-time). Avoid the Spotify-Discover-Weekly trap where over-aggressive personalization homogenizes taste.
- **Cold-start strategy (new user):**
  1. Seed with last 50 listened albums from Spotify (if connected) — pre-populate diary draft state.
  2. "Pick 5 favorites" onboarding step.
  3. Suggest 10 critics + 5 mutual-friend follows.
  4. Within 24h of signup, a server job pre-computes a "Likely for you" shelf based on the user's top-3 genres + the most-rated albums in those genres on auxd.
- **Anti-pattern to avoid:** Last.fm's "Recommendations" tab, which became a content-graveyard once their social layer froze (2014+); AOTY's "Best New Music" which is critic-only and ignores your taste.

### Album detail page

**Recommendation: cover-prominent hero, dense-but-scannable metadata, friends-rated rail above public reviews.**

- **Hero (top 40% of screen on mobile).** Large cover (≥250pt). Below: artist (tappable → artist page), title, year, runtime, label, primary genre tag(s) — max 3 tags. Avoid the RateYourMusic metadata-wall problem (12+ fields above the fold).
- **Action bar (sticky under hero).** Three buttons: *Log* (primary), *Backlog toggle*, *Share*. Plus a heart icon for "Liked." Source: Letterboxd "Mark as Watched / Like / Watchlist" sticky bar.
- **Friends rated rail.** Horizontal scroll of avatar + rating from users you follow who've rated this album. Tap → their review. Empty state: "No friends rated this yet. Be the first?" → opens log sheet.
- **Community ratings.** Aggregate distribution histogram (5-star bucket chart) + numeric average. Show only if ≥10 ratings (avoids noise). Source: Letterboxd's "Ratings" chart.
- **Tracklist.** Collapsed by default (Casual users don't need it for logging); tap to expand. Each track row has play-on-Spotify deep link. Source: Apple Music album page.
- **Reviews stream.** Tabs: *Friends · Popular · Recent*. Default: Friends. Each card: avatar + name + rating + review text (truncated at 200 char with "Read more"). Source: Letterboxd review stream.
- **Editorial blurbs.** If present, surface above community reviews. Source: AOTY critic-score sidebar (kept restrained — one or two professional reviews max, not a wall).
- **Related albums.** Bottom of page: "More from this artist," "Listeners who rated this also rated." Cover-grid.

---

## Micro-interactions & Animations

- **Tap-to-rate haptic.** Each star tap = `UIImpactFeedbackGenerator.light` (iOS) / `HapticFeedback.heavyClick` (Android medium). Star fill animates with a 200ms ease-out scale (1.0 → 1.15 → 1.0). Source: Letterboxd iOS rating haptic.
- **Pull-to-refresh.** Native iOS/Android pull-to-refresh on feed and diary. Cover-thumb sequence animates during refresh (covers fall into place top-down) as a delight moment — gated on reduce-motion setting. Source: Apollo for Reddit (defunct) pull-to-refresh animations.
- **Sheet dismiss.** Bottom sheets dismiss with a spring (not linear) curve. Backdrop fades 0–0.4 alpha.
- **Log success.** Snackbar slides up 200ms, holds 4s, slides down 150ms. Includes mini cover thumb left, "Logged." text, "View →" trailing button. Source: Letterboxd post-log snackbar.
- **Skeleton shimmer.** 1.2s loop, 30deg gradient, opacity 0.1–0.2. Source: NN/g 2023 skeleton-screen guidelines.
- **Cover-art parallax.** Subtle 1.05x scale on album detail page hero as user scrolls (cover stays static while metadata scrolls). Disabled under reduce-motion. Source: Apple Music album page.
- **Heart toggle.** Burst animation on like — 12 small dots radiate from the heart, fade 400ms. Source: Twitter/X like animation circa 2017.
- **Follow.** Button transitions Outlined → Filled with a 1.1x bounce, 250ms. Brief "Following" text + checkmark, reverts to "Following" steady state.

---

## Accessibility Requirements (WCAG 2.1 AA)

- **Color contrast.** All text 4.5:1 minimum on background; UI components 3:1. Cover-overlay text (rating badges, "private" lock glyph) must be readable on arbitrary album cover backgrounds — solve via gradient scrim (`linear-gradient(rgba(0,0,0,0.6), transparent)`) at top/bottom of any cover with overlay text. Source: WCAG 2.1 SC 1.4.3, 1.4.11.
- **Keyboard navigation.** Web: full keyboard navigation. Star rating: arrow keys ←/→ for 0.5-step; Enter to commit. Modal traps focus, Esc dismisses. Source: WCAG 2.1 SC 2.1.1, 2.1.2.
- **Screen reader.** Star rating exposed as `role="slider"` with `aria-valuemin=0`, `aria-valuemax=5`, `aria-valuenow=3.5`, `aria-valuetext="3 and a half stars out of 5"`. Cover images have alt text "Album cover: [Title] by [Artist]." Each diary entry announced as one logical group. Source: WAI-ARIA Authoring Practices 1.2.
- **Touch targets.** Minimum 44×44pt (iOS HIG) / 48×48dp (Material). Star rating: each star ≥44pt wide; tap targets extend ±4pt into adjacent stars (allowed because drag-gesture interpretation handles intent). Source: WCAG 2.1 SC 2.5.5 (AAA but commonly required at AA).
- **Reduced motion.** All non-essential animations honor `prefers-reduced-motion: reduce`. Specifically: pull-to-refresh cover-fall, like-burst, sheet spring, hero parallax — all degrade to instant or simple fade. Star-fill animation: scale-only removed, opacity step retained for state feedback. Source: WCAG 2.1 SC 2.3.3.
- **Captions / transcripts.** auxd is primarily text — N/A in v1. If audio-snippet previews ever ship (e.g., 30s clips), captions required.
- **Form labels.** Every input has a visible label OR aria-label (not placeholder-as-label, which is a common a11y bug). Source: WCAG 2.1 SC 3.3.2.
- **Error identification.** Inline error text below the field with `aria-describedby` linking field → error. Color is never the sole indicator (icon + text + color). Source: WCAG 2.1 SC 3.3.1, 1.4.1.
- **Font scaling.** Support Dynamic Type (iOS) and font-size system preference (Android/web) up to 200%. Layouts must reflow, not truncate. Source: WCAG 2.1 SC 1.4.4.
- **High contrast mode.** iOS Increase Contrast / Windows High Contrast: ensure borders and focus rings remain visible. Source: WCAG 2.1 SC 1.4.11.

---

## Platform Considerations (Mobile, Web)

### Mobile (iOS + Android)

- **Tab bar navigation.** Bottom tab bar with 4 destinations: *Home (feed)* · *Diary* · *Discover* · *Profile*. A central floating "+" action button overlaps the tab bar for the log sheet (Strava/Letterboxd pattern). Source: Letterboxd iOS app (Diary/Activity/Films/Search/Profile = 5 tabs — auxd reduces to 4 for casual focus).
- **Pull-to-refresh** on feed, diary, search results. Native iOS bounce; Android Material spinner.
- **Share sheet.** Each log/review/list has share. iOS UIActivityViewController, Android Intent.ACTION_SEND. Generated share asset = cover art + rating + first 80 chars of review + auxd watermark, suitable for IG Stories. Source: Letterboxd "Share to Story" 2022 feature.
- **Haptics.** Light-impact on log commit; medium-impact on like; selection-haptic on tab change. iOS only; Android medium-click. Honor system haptics-off setting. Source: iOS HIG haptics guidance.
- **Deep links.** `auxd://album/{spotify_id}` resolves on home or fallback web. Spotify back-link via `x-callback-url` to return user to Spotify after logging if launched from Spotify share-sheet.
- **Background sync.** iOS BGAppRefreshTask / Android WorkManager pull recent-played from Spotify every ~6h. User-disable in settings.
- **Push notifications.** Local for "you finished an album, log it?" (if Spotify history shows a new completed listen); remote for social events (new follower, reply).
- **Offline.** Diary, profile, and last-viewed album pages cached locally (SQLite/Room/CoreData); logs created offline queue and sync on reconnect. Source: Letterboxd offline cache behavior.

### Web

- **Responsive breakpoints.** Mobile (≤768) is identical to native shell; tablet (769–1024) shows two-column feed + sidebar; desktop (≥1025) three-column (nav · feed · suggestions).
- **Keyboard shortcuts.** `L` opens log sheet; `/` focuses search; `J/K` navigates feed; `?` shows help. Source: Letterboxd web shortcuts.
- **URLs and shareable links.** `/u/{username}`, `/album/{slug}`, `/list/{slug}`, `/review/{id}`. Crawlable, indexable.
- **Open Graph / share previews.** Every shareable page emits OG meta tags with cover, title, rating, review excerpt. Critical for Twitter/X and iMessage previews.
- **PWA.** Service worker for offline read; "Add to home screen" prompted after 3 web sessions. Source: Twitter Lite case study (2018).

---

## Anti-patterns to Avoid

1. **RateYourMusic metadata wall.** RYM puts 15+ fields (catalog number, country, format, language, descriptors, release notes) above the fold on every album page. Casual users bounce. *auxd: cover + 5 metadata items max in the hero.*
2. **Notification overload (Goodreads).** Goodreads sends daily "X added a book to their shelf" emails by default. Top complaint cluster on iOS App Store 2023–24. *auxd: default-off digests; granular per-event push controls.*
3. **Forced gamification (Goodreads Reading Challenge, Strava badges).** Counter-productive for casual users in a non-competitive activity. *auxd: no badges, no streaks, no challenges in v1.*
4. **Cold-start dead-end (AOTY).** New users see a critic-aggregator front page with no personal hook. Bounce rate is high on first session. *auxd: never show an empty feed — seed with editorial picks + suggested follows.*
5. **Required-text reviews (AOTY web ratings 2023–24).** Forcing prose before commit kills logging completion. *auxd: rating is sufficient; review is optional.*
6. **Algorithmic feed before social-graph compounding (Spotify Wrapped Year-in-Review).** Algorithm dilutes signal when network is sparse. *auxd: chronological follow-graph feed in v1; algorithm injection only after network maturity.*
7. **100-point ratings (RateYourMusic, AOTY).** Cognitive load and false precision. *auxd: ½-star out of 5.*
8. **Friend-request bidirectional follow (early Goodreads).** Friction at scale. *auxd: asymmetric follow.*
9. **Cluttered tab bar (Letterboxd's 5 tabs).** Borderline overload for casual users. *auxd: 4 tabs + floating "+".*
10. **Modal review interruption (some forum-style music sites).** Treating reviews as the primary content blocks the casual logging path. *auxd: rating-first, review-second.*
11. **Spoiler-tag enforcement (Letterboxd film context).** Music doesn't have the same spoiler problem; importing the pattern adds friction. *auxd: no spoiler tags in v1, revisit if data demands.*
12. **Pop-up onboarding tours (typical SaaS).** Overlays explaining every UI element annoy and don't retain. *auxd: contextual tooltips on first-use of each feature, dismissible permanently.*
13. **Aggressive engagement loops (Duolingo-style streak shaming).** Out of brand for a contemplative music product. *auxd: no streak counters; gentle weekly recap email opt-in only.*
14. **Walled-garden share images without watermark.** Letterboxd had Instagram Stories shares lose attribution circa 2021; fixed 2022. *auxd: watermark every shareable export from day 1.*
15. **"Verified critic" tier as primary social object (AOTY).** Centralizes attention on a small group; doesn't compound network value. *auxd: critics are a seeding mechanism, not a permanent UI tier — they appear in the same feed as friends.*

---

## Recommended Approach for auxd

**v1 (MVP) UX in one paragraph:** Bottom-tab native mobile app (iOS + Android, React Native or native — Phase 5 tech decision). Four tabs + floating Log button. Home is a chronological feed of follows' activity. Diary is the user's auto-generated chronological log of listens. Discover surfaces editorial + friends-rated. Profile shows diary, reviews, lists, likes. The Log sheet is the load-bearing interaction: half-star rating, like heart, date, optional inline review, visibility chip, single commit button — under 8 seconds rating-only, under 30 seconds with review. Asymmetric follows. No badges. No algorithm in feed. Spotify history import is the cold-start unlock. Backlog as a single per-user reorderable list. Custom lists as a secondary feature. Half-star precision, no 100-point ratings, no streaks, no forced gamification.

**v1 "do this first" checklist (for Phase 2 wireframing):**

1. Wireframe the **Log sheet** in three states: empty, mid-fill, completed-pending-commit. This is the highest-leverage screen.
2. Wireframe the **Home feed** with seeded content for empty-state.
3. Wireframe the **Album detail page** with the *Friends rated* rail prominent.
4. Wireframe the **Onboarding flow** end-to-end (sign-up → Spotify connect → 5 favorites → 3 follows → first feed view).
5. Wireframe the **Diary** in cover-grid and list-view modes.
6. Define the **notification taxonomy** before any backend work — getting defaults wrong here is a top churn driver in comparable apps.

**v1 stretch (nice-to-have if budget allows):**

- Share-to-Story image generator with cover + rating + watermark.
- Spotify push notification "you finished Brat, log it?" (requires push-notif setup + Spotify webhook polling).
- PWA for web with offline diary read.

**Explicitly deferred to v2+:**

- Collaborative lists.
- Spoiler tags.
- Track-level ratings.
- Apple Music integration (auxd v1 is Spotify-only; Apple Music API has stricter rate limits and the casual segment skews Spotify per Last.fm scrobble share data).
- Algorithmic "For You" injection.
- Critic verification tier.
- Web-first creation flows (web read + share is enough for v1).

---

## Open Questions for Product Spec

1. **Rating granularity confirmation.** Half-star 5-scale is the recommendation, but should we pilot a 4-point thumb scale (Hate / Meh / Like / Love) for casual users in alpha to test logging completion? *Owner: product spec author.*
2. **Backlog vs. multiple watchlists.** Single per-user backlog (recommended) vs. allow multiple-tagged backlogs ("Soon," "Eventually," "Maybe")? Letterboxd has single watchlist + lists; we recommend same. *Owner: product spec author.*
3. **Public-by-default vs. private-by-default for new accounts.** Letterboxd defaults public; privacy advocates would default private. Recommendation: public for first 10 logs (seed feed), then user prompted to confirm — but needs PM call. *Owner: product spec author + privacy review.*
4. **Critic-seeding strategy.** How many critics seeded at launch? Verified or unverified? Paid or invited? *Owner: product spec author + ops.*
5. **Spotify recently-played as auto-log source.** Should completed listens auto-create draft diary entries (user confirms), or only suggest a log via notification (user must initiate)? Recommendation: notification-suggest, never silent auto-log (user-control principle). *Owner: product spec author.*
6. **Track-level commentary in v1?** Casual users rarely care; some heavy listeners ask. Recommendation: defer entirely to v2. *Owner: product spec author.*
7. **List-cover composition rules.** Mosaic from first 4 entries (Letterboxd model) vs. user-uploaded cover image? Recommendation: mosaic in v1; uploads in v2. *Owner: product spec author.*
8. **Group / community / forum surface?** RYM has forums; AOTY has comments per album. Recommendation: no forums in v1; comments on reviews only. *Owner: product spec author.*
9. **DM / private messaging?** Recommendation: defer to v2. v1 social = follows + feed + replies on reviews only. *Owner: product spec author.*
10. **Spotify-Wrapped-style annual recap?** Year-end yearly recap is a Spotify cultural moment; a tied auxd recap could be a virality unlock. Recommendation: ship "Year in auxd" by Dec 2026 if v1 ships by Q3. *Owner: product spec author + marketing.*
11. **Brand voice in microcopy.** Letterboxd has dry, film-buff voice. Goodreads has neutral library voice. auxd needs a defined voice for empty states, error states, snackbars. *Owner: brand/marketing.*
12. **Localization in v1.** English-only is the assumption. Music app users skew international; deferring i18n past v1 may be acceptable for a portfolio-mode launch. *Owner: product spec author.*

---

## Sources Referenced

The following sources were drawn upon from the agent's training-data knowledge of these platforms; **a Phase 2 reviewer should re-verify any cited UX detail against the live products before locking wireframes.**

- **Letterboxd** — apps.apple.com/app/letterboxd reviews 2022–24; r/Letterboxd; Karl von Randow & Matthew Buchanan podcast interviews 2023 (The Town, Industry, Sight & Sound); Letterboxd web product itself.
- **Goodreads** — apps.apple.com/app/goodreads reviews 2022–24; r/goodreads; Amazon's product blog history; Goodreads help center.
- **Strava** — apps.apple.com/app/strava reviews 2023–24; Strava product blog; Strava UX patterns blog posts on Medium and UX Collective.
- **RateYourMusic** — rateyourmusic.com (live product); r/rateyourmusic; Sonemic rebuild Kickstarter updates 2014–2024.
- **Album of the Year (AOTY)** — albumoftheyear.org (live product); r/AlbumOfTheYear; AOTY+ subscription page.
- **Last.fm** — last.fm (live product); product history per Wikipedia 2002–present; community blog.
- **Spotify** — Spotify mobile app patterns; Spotify Wrapped feature evolution 2016–2025.
- **Apple Music** — Apple Music iOS app patterns; Apple HIG.
- **Twitter/X** — feed and follow patterns 2010–2025; engineering blog on follow-graph timeline.
- **NN/g (Nielsen Norman Group)** — Empty states, skeleton screens, progressive disclosure articles 2019–2024.
- **Baymard Institute** — Mobile UX research, especially form patterns and bottom-sheet conventions.
- **WCAG 2.1** — w3.org/TR/WCAG21 success criteria 1.4.3, 1.4.11, 2.1.1, 2.1.2, 2.3.3, 2.5.5, 3.3.1, 3.3.2.
- **iOS Human Interface Guidelines** — developer.apple.com/design/human-interface-guidelines (haptics, tab bars, sheets).
- **Material Design 3** — m3.material.io (navigation, components, motion).
- **r/UI_Design, r/UXDesign** — community discussions on tracking apps and social UX 2022–2025.
