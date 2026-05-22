# User Stories: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> Personas referenced: **Casey** (casual streamer, primary), **Maya** (engaged listener), **Jamie** (tastemaker/critic)
> Related: [product-spec.md](./product-spec.md) | [user-journeys.md](./user-journeys.md) | [data-model.md](./data-model.md)

User stories are grouped by capability cluster. **Must Have** = blocking for M0/launch; **Should Have** = within first month if scope allows; **Could Have** = post-launch / v1.x. Anything else has been deferred to v2 — see [out-of-scope.md](./out-of-scope.md).

Acceptance criteria are Given/When/Then to keep verifiable behavior front and center.

---

## Cluster A — Onboarding & first-session activation (Must Have)

### S-A1: Sign up with email or Spotify shortcut
**As Casey,** I want to sign up in under 60 seconds, so that I don't bounce before seeing any value.

**AC:**
- Given I'm on the landing page, When I click "Get started with Spotify", Then I am redirected to Spotify OAuth and on consent return to step 2 of onboarding with an account auto-created using my Spotify display name and email.
- Given I prefer email signup, When I provide email + password + handle, Then my account is created and I'm asked to connect Spotify next (skippable but discouraged).
- Given my chosen handle is taken, When I submit, Then I see an inline error with 3 suggested alternatives.
- **Edge: deleted-account email collision (Phase 5C decision):** Given the email I'm signing up with is tied to an account in `status: deleted` (grace period), When I submit (via either signup method), Then I see a "This email is tied to an account scheduled for deletion. Restore your account?" page with a Restore CTA that requires re-authentication. New account creation is REFUSED.
- **Edge: Spotify-OAuth email matches existing email/password account (Phase 5C decision):** Given Spotify OAuth returns an email matching an existing ACTIVE auxd account, When the OAuth callback fires, Then I see a "Connect Spotify to your existing account?" page that requires my existing auxd password to confirm identity. On confirm, the Spotify `MusicProvider` sub-doc attaches to the existing User. Silent auto-link is NEVER performed.

### S-A2: Optionally connect Spotify and auto-import recent listens
**As Casey,** I want the option to connect Spotify and auto-import my last 30 days, so my first session shows something real — but I also want to be able to skip Spotify entirely and still use auxd fully.

**AC:**
- Given I'm on the Spotify auth step, When the screen renders, Then I see a clear primary CTA "Connect Spotify" and an equally visible secondary "Skip — connect later" link, plus an explanation of what Spotify connect enables.
- Given I tap Skip, When I confirm, Then I advance to "Follow 3" with critic-seed-only suggestions; my account is fully functional (manual log, reviews, backlog, auxes all work); no "degraded mode" indicator is shown anywhere.
- Given I authorized Spotify, When the import completes, Then my diary shows up to 50 deduped album entries from the last 30 days with timestamps preserved.
- Given the import is taking >5s, When I'm on the import screen, Then I see a progress indicator with the count of albums found and a "Continue without waiting" link.
- Given Spotify returns no recent listens, When the import completes, Then I see a friendly empty state with a "Log your first album manually" CTA.
- Given I skipped Spotify at signup, When I later open Settings → Integrations and tap Connect Spotify, Then OAuth runs and (on success) the same 30-day import auto-runs to back-fill my diary.

### S-A3: Confirm and ½-star recent listens
**As Casey,** I want to rate my standout listens from the past 30 days in <60 seconds, so that my diary captures my actual taste signal.

**AC:**
- Given the import succeeded, When I see the "Confirm your last 30 days" screen, Then I'm shown my top 5 albums (by play time) as tappable cards with a ½-star rating widget per card.
- Given I tap a star, When I commit, Then the rating saves immediately (optimistic UI) and is reflected in my diary.
- Given I want to skip, When I tap "Skip", Then I advance to the next onboarding step without ratings.

### S-A4: Follow 3 to fill the feed
**As Casey,** I want to follow a small starter set of accounts during onboarding, so that my home feed has content when I land on it.

**AC:**
- Given I'm in the "Follow 3 to fill your feed" step, When I see the screen, Then I'm shown a mix of (a) up to 6 critic-seed accounts, (b) up to 4 mutual-taste suggestions based on my just-imported listens. The top 6 visible cards always include ≥3 critics (per decision UJ-2).
- **Given critic-seed cards are shown, When the screen first renders, Then those critic-seed cards have their follow-checkbox PRE-CHECKED by default; the user can untick any before tapping "Continue" (per decision Q13).**
- Given mutual-taste suggestion cards are shown, When the screen renders, Then those cards are UNCHECKED by default; user explicitly opts in per card.
- Given I've followed ≥1 person (any source), When I tap "Continue", Then I advance to the home feed.
- Given I've followed 0 people, When I tap "Continue", Then a soft modal asks "follow at least one to see a feed?" with a "Skip anyway" option.
- Given I tap "Continue" with pre-checked critic-seed cards unchanged, When the follows commit, Then those follow records carry `source: onboarding_preselected` (analytics signal — we want to know what % of users keep vs untick the defaults).

### S-A5: Land on a non-empty home feed
**As Casey,** I want my first sight of the home feed to be populated with actual content, so that I understand the product immediately.

**AC:**
- Given I just completed onboarding, When I land on home, Then the feed shows entries from followed accounts in reverse-chronological order, with at least 5 entries visible.
- Given the feed has <5 entries from followed accounts, When I land on home, Then the feed is padded with critic-seed activity from the past 7 days.

---

## Cluster B — Logging & rating an album (Must Have)

### S-B1: Log an album in <8 seconds
**As Casey,** I want to log an album as listened in under 8 seconds, so that the moment doesn't slip away.

**AC:**
- Given I'm anywhere in the app, When I tap the persistent "+" Log button, Then a bottom-sheet appears with album search prefilled with the most recent Spotify listen.
- Given I tap "Log", When I confirm, Then a diary entry is created with default visibility = public, no rating, no review, sourced as "manual" (or "spotify-prefill" if the prefill was used).
- Given I tap "Log + Rate", When I rate, Then I commit the rating and a diary entry exists with both fields in <8s end-to-end (measured server-side: time from log-button-tap to confirmed entry).
- Given Spotify integration isn't connected, When I open the Log sheet, Then album search uses the catalog directly (no prefill), with autocomplete.

### S-B2: Rate an album with ½-star precision
**As Casey,** I want to express "this was better than fine but not great" as 3.5 stars, so that my taste signal is honest.

**AC:**
- Given I'm on the rating widget, When I tap between two stars, Then I select the ½-star value.
- Given I'm rating on mobile, When I drag across stars, Then the rating tracks my finger.
- Given I want no rating, When I close the rating widget without selecting, Then the entry saves without a rating.

### S-B3: Aux an album independently of rating
**As Casey,** I want to "Aux" an album that's a standout for me, separate from the star rating, so I have a personal-curation signal that's rarer and more deliberate than a rating.

**AC:**
- Given I'm in the Log sheet, When I tap the Aux icon (🏅 medal/badge), Then it toggles on the diary entry independently of the rating; tapping again removes it.
- Given I want to see all my Aux'd albums, When I open my profile → Filters → "Aux'd", Then I see only Aux'd entries in reverse-chronological order.
- Given another user views an album detail page, When my Aux is public, Then my avatar appears in the "Friends who rated &amp; aux'd this" section.

> *Aux is for diary entries only (your own log).* Reviews can be "Liked" by other users (S-C4) — that's a different concept: Aux (🏅) = self-directed curation on your own content; Like (👍) = other-directed social engagement on someone else's review. Semantics split in Revision #3.

### S-B4: Re-log an album (relisten)
**As Maya,** I want to log the same album multiple times when I listen to it again, so my diary reflects my real listening history.

**AC:**
- Given I previously logged an album, When I log it again, Then a new diary entry is created with a new date and (optionally) a new rating; the old entry is preserved.
- Given I'm on the album detail page, When I scroll to my history, Then I see all my prior logs of this album with their ratings.

### S-B5: Edit or delete a diary entry
**As Casey,** I want to fix typos in a review or remove an entry I logged by mistake, so my diary stays accurate.

**AC:**
- Given I'm on my diary entry, When I tap Edit, Then I can change rating, Aux, review, visibility.
- Given I edited the entry, When I save, Then the entry shows an "edited" badge with timestamp on hover.
- Given I tap Delete, When I confirm in a modal, Then the entry is soft-deleted (recoverable for 30 days; hard-deleted thereafter).

### S-B6: Just-finished auto-prompt *(elevated to MVP in Revision #1; story body added in sync-verify Run #1)*
**As Casey (Spotify connected),** I want a prompt when Spotify detects I just finished an album, so I capture the moment without having to remember to log it later.

**AC:**
- Given I have `auto_prompt_enabled=true` (default for Spotify-connected accounts) and Spotify recently-played reports a finished album, When background polling fires (5 min cadence with active session in last 24h, 15 min otherwise), Then a `JustFinishedPrompt` is created in `pending` state for that album.
- Given a `JustFinishedPrompt` is `pending`, When I next open auxd, Then the home feed shows a hero prompt card at the top: "Just listened to {album} — log it?" with primary "Log" CTA and secondary "Not now"/"⋮ menu" options.
- Given I tap "Log" on the hero prompt, When the Log sheet opens, Then the album is prefilled identically to Journey 2; on commit the resulting `DiaryEntry.source = spotify_just_finished_prompt` and the `JustFinishedPrompt` transitions to `logged` referencing the new entry id.
- Given I tap "Not now", When the prompt dismisses, Then the same album will not re-prompt me for 30 days.
- Given I tap "⋮ menu", When I select "Don't prompt me for this album" or "Disable auto-prompts", Then per-album mute or global opt-out (`auto_prompt_enabled=false`) applies immediately and persists.
- Given I am inside my configured quiet hours, When detection fires, Then the prompt is queued and surfaces on the next open outside quiet hours; if it ages past 24h it expires silently.
- Given I have opted into auto-prompt push (`auto_prompt_push_enabled=true`), When detection fires outside quiet hours, Then at most one push per day is delivered (per N-018 + coalescer rate-limit policy in [notification-taxonomy.md](./notification-taxonomy.md#n-018)).
- Given `auto_prompt_enabled=false`, When detection fires, Then no prompt card, no push, no entry is ever created from auto-detection.

> See [user-journeys.md § Journey 1.5](./user-journeys.md#journey-15-just-finished-auto-prompt-casey-spotify-connected-returning-added-in-revision-1) for the full happy path and drop-off mitigations, and FR-026 in [product-spec.md](./product-spec.md) for the requirement summary.

---

## Cluster C — Reviews (Must Have)

### S-C1: Write a review after rating
**As Maya,** I want to write a paragraph about an album I rated, so my followers see my reasoning.

**AC:**
- Given I'm in the Log sheet, When I tap "Add a review", Then a textarea expands with markdown-safe input.
- Given I save, When the entry commits, Then the review is shown on my profile diary and (if public) in followers' feeds.
- Reviews can be any length ≥1 character; no "say more" prompts or length-based hints (per decision #5, revised in Revision #3).

### S-C2: Read reviews on an album detail page
**As Casey,** I want to see what people I follow thought of an album before listening to it, so I can decide whether to invest 45 minutes.

**AC:**
- Given I open an album detail page, When the page loads, Then I see (in default sort order = **Newest**): friends' reviews → recent public reviews → critic-seed reviews.
- Given I tap the sort selector, When I see options, Then I can choose **Newest** (default), **Most Liked**, or **Highest-Rated** (per FR-032).
- Given I choose "Most Liked", When the list re-renders, Then reviews are ordered by `Review.reactions.likes_count` descending (within the same primary tier — friends first, then public, then critic-seed).
- Given my sort choice, When I leave and return to the page, Then the choice persists per-device.
- Given a review is long, When it's shown in the list, Then it's truncated at ~200 chars with "Read more" expanding it inline.
- Given a reviewer is private or has me blocked, When I view the album, Then their review is not shown.

### S-C4: Like another user's review *(added in Revision #3)*
**As Casey,** I want to "Like" a review I appreciated (e.g., a sharp critic-seed review), so I signal engagement and the review becomes findable to others via the Most Liked sort.

**AC:**
- Given I'm viewing someone else's review (album detail page, profile, feed), When I tap the Like button (👍), Then it toggles — the review's `likes_count` increments optimistically; the reviewer receives an N-004 (`review.liked`) notification.
- Given I tap Like again, When it toggles off, Then the count decrements and no extra notification is generated (un-like is silent).
- Given I'm viewing my OWN review, When I see the Like button, Then it's disabled with a "you can't like your own review" tooltip on hover. (My own diary entry can be Aux'd, but my own review can't be self-Liked.)
- Given I previously Liked a review, When I view it again, Then the Like button shows the active state.
- Likes never appear in the weekly digest individually (per NT-4 they aggregate); they may show as part of the digest's "most-liked reviews from your follow graph this week" hero entry.

### S-C3: Edit a review after publishing
**As Maya,** I want to refine a review I wrote earlier (typo fix, additional thought), so my published opinion is the polished one.

**AC:**
- Given I'm on my own review, When I tap Edit, Then the review opens in an editable state with the current published text prefilled.
- Given I save edits, When the review is re-published, Then it shows a small "edited" badge on the public surface with timestamp visible on hover/long-press (per decision Q17).
- **Edit history is NOT shown publicly** — readers only see the latest version. An internal 90-day revision log is preserved for moderation/audit; users do not have access to past versions of their own reviews via the UI at MVP.
- Given I save a no-op edit (no actual text change), When the review re-publishes, Then no "edited" badge is added.

---

## Cluster D — Backlog / Up Next (Must Have)

### S-D1: Add an album to backlog
**As Casey,** I want to save an album to a "listen to this later" list, so I don't forget it.

**AC:**
- Given I'm on an album detail page, When I tap "Add to Up Next", Then the album is added to my private backlog with a timestamp.
- Given I'm in the bottom-sheet Log flow, When I see options, Then "Add to Up Next" is an alternative to "Log".
- Given an album is already in backlog, When I view the album detail, Then the button reads "Remove from Up Next".

### S-D2: View and reorder backlog
**As Casey,** I want to see my Up Next as a list I can prioritize, so I know what to play next.

**AC:**
- Given I open Up Next, When the list renders, Then I see albums in user-defined order (default: most-recently-added first).
- Given I drag an item, When I drop, Then the order persists.
- Given I open an album from Up Next, When I see the detail page, Then there's a "Listen on Spotify" deep-link if connected (opens spotify:album:ID).

### S-D3: Auto-remove from backlog on log
**As Casey,** I want logged albums to disappear from my backlog automatically, so the list stays a true "next" queue.

**AC:**
- Given an album is in my backlog, When I log it, Then it's auto-removed from backlog unless I have settings → "Keep backlog after logging" enabled.
- Given I disabled auto-remove, When I log an album in my backlog, Then it stays in backlog and shows a "logged on X" badge.

---

## Cluster E — Social graph & discovery (Must Have)

### S-E1: Follow another user
**As Casey,** I want to follow a friend, so their listening shows up in my feed.

**AC:**
- Given I'm on someone's profile, When I tap Follow, Then I'm following them; the count updates optimistically.
- Given I previously followed someone, When I tap Following, Then a confirm modal appears for Unfollow.
- Given I block someone, When the block is applied, Then any existing follow relationship is automatically dissolved.

### S-E2: Browse a follower's diary
**As Casey,** I want to see what Jamie (a critic I follow) listened to recently, so I can find new music.

**AC:**
- Given I open a user's profile, When the page renders, Then I see their public diary in reverse-chronological order (paginated, 25/page).
- Given a diary entry is followers-only and I'm not a follower, When I view their profile, Then that entry is hidden (replaced with "X listens not visible" footer text).
- Given a diary entry is private, When anyone (not the owner) views, Then it's hidden.

### S-E3: See a weighted home feed
**As Casey,** I want my home feed to surface signal (reviews, strong opinions) from followed accounts, not just noise.

**AC:**
- Given my follow graph has activity, When I open home, Then the feed shows entries in mostly-reverse-chronological order with weight boost: reviews +20%, ★★★★★ or ★ ratings +15%, entries by my top-5-interacted-with users +10%.
- Given my followed accounts have been silent today, When I open home, Then I see entries from yesterday/this week so the feed isn't ever empty.
- Given I want to see strictly chronological, When I toggle "Latest" in feed header, Then weights are disabled. *(Toggle persisted per-device.)*

### S-E4: Discover via "friends who rated this"
**As Casey,** I want to see which friends rated an album highly, so I can use my social graph as my filter.

**AC:**
- Given I'm on an album detail page, When I scroll to the "Friends" section, Then I see avatars + names + ratings from followed accounts who rated this album, sorted by rating desc then by date desc.
- Given no friends have rated this album, When I view the section, Then I see a "0 friends have rated this" empty state with a "see all recent reviews" CTA.

### S-E5: Get suggested follows
**As Casey,** I want the app to suggest people whose taste matches mine, so my graph grows.

**AC:**
- Given I have ≥5 ratings in my diary, When the system runs the suggestion job, Then I see up to 5 suggested accounts on a "Discover" tab.
- Given a suggested account was already followed, blocked, or dismissed, When I see suggestions, Then they're filtered out.
- Given I dismiss a suggestion, When the same job runs next, Then the dismissed account is excluded for 30 days.

---

## Cluster F — Album detail & catalog (Must Have)

### S-F1: View an album detail page
**As Casey,** I want to see album info, tracklist, friends' ratings, and reviews on one page, so I can decide what to do (log, listen, save).

**AC:**
- Given I navigate to an album page, When it loads (SSR), Then I see: cover, title, artist, year, label, tracklist, my own log history if any, friends' ratings + auxes, public reviews list, "Add to Up Next" + "Log" CTAs.
- Given the album has multiple editions under the same MusicBrainz release-group MBID (Standard, Deluxe, Bonus, etc.), When the page renders, Then an "Edition" chip near the cover shows "All editions" with a dropdown to filter (per decision Q15 / FR-028). Default view aggregates ratings/reviews/auxes across all editions.
- Given the album has Open Graph metadata, When the URL is shared, Then the preview card shows cover + title + artist + average rating.
- Given the album is missing from MusicBrainz/Spotify caches, When the page loads, Then it falls through to a cold-fetch (Spotify catalog) and caches the result for 7 days. If MusicBrainz MBID is not yet available, the album is created as a `candidate` record (per decision Q21) flagged for MBID reconciliation when MusicBrainz catches up.

### S-F2: Search the catalog
**As Casey,** I want to find any album by typing its name, so logging is fast.

**AC:**
- Given I type ≥3 characters in search, When debounced 200ms, Then I see autocomplete results from Atlas Search (cached metadata) merged with Spotify search (uncached).
- Given a result is tapped, When I navigate, Then the album detail page opens.
- Given my search returns zero, When I see the empty state, Then there's a "Can't find your album?" link that opens a "Report missing album" form.

---

## Cluster G — Profile, settings, privacy (Must Have)

### S-G1: Edit profile
**As Maya,** I want to set my display name, bio, avatar, and handle, so my profile represents me.

**AC:**
- Given I'm on Settings → Profile, When I update fields, Then changes save on submit with optimistic UI.
- Given my account is less than 30 days old, When I attempt to change my handle, Then I see a soft notice "handles are locked for the first 30 days" with the date when changes will be available (per decision Q16).
- Given my account is ≥30 days old AND I haven't changed my handle in the last 30 days, When I change it, Then the new handle is set; my last-change timestamp is updated; the old handle becomes available 90 days later (with a redirect from the old `@handle` URL for that period).
- Given I attempt to change my handle within 30 days of a prior change, When I submit, Then I see "you can change your handle again on YYYY-MM-DD" inline.
- Given I attempt to claim a reserved-squat handle (e.g., taylorswift, kendrick), When I submit, Then I see "this handle is reserved — verification required" with a link to a verification request form (post-launch).
- Given the new handle is taken (and not reserved), When I submit, Then I see an inline error with 3 suggested alternatives.
- Given my avatar upload >5MB, When I attempt, Then I see "image too large, max 5MB" inline.

### S-G2: Manage privacy defaults
**As Casey,** I want to set default visibility for my diary entries, so I don't have to remember to make them followers-only every time.

**AC:**
- Given I'm on Settings → Privacy, When I set default visibility to "Followers only", Then new entries default to followers-only (per-entry override still available).
- Given I toggle "Private profile" on, When I save, Then my profile is only visible to my followers; anyone not following me sees a "this account is private" page.
- Given I toggle "Private profile" on, When I had pending follow requests, Then they require my approval (the toggle creates a request queue).

### S-G3: Manage notifications
**As Casey,** I want to turn off individual notification types (including auto-prompts), so I'm not overwhelmed.

**AC:**
- Given I'm on Settings → Notifications, When the page renders, Then I see every notification type from [notification-taxonomy.md](./notification-taxonomy.md) (20 types including auto-prompts and list-related events) with per-channel toggles (in-app, email, push).
- Given I toggle off "weekly digest", When I save, Then I stop receiving the weekly summary email.
- Given I toggle on "real-time push for follows", When someone follows me, Then I get a push within 30 seconds (best-effort).
- Given I toggle off "Just-finished prompt", When the auto-prompt detection runs, Then no prompts are surfaced (in-app or push).
- Given I configure Quiet hours 22:00–08:00, When a notification is generated during those hours, Then push and in-app prompts are suppressed (delivery deferred to next-open-outside-quiet-hours); email and digest still fire normally.

### S-G4: Block and report
**As Maya,** I want to block harassing users and report rule-breaking content, so I can use the product safely.

**AC:**
- Given I'm on someone's profile, When I tap "Block", Then they can no longer see my profile, follow me, or interact with my entries; existing follow is dissolved.
- Given I'm on a piece of content, When I tap "Report" and select a reason, Then a report is created and queued for review.
- Given I have ≥3 reports against me in 7 days, When the threshold is hit, Then my account is auto-flagged via a daily log scan (manual review process at MVP; no realtime auto-suspension; full moderation tooling deferred).

### S-G5: Export and delete account
**As Casey,** I want to export my diary or delete my account, so I have control over my data.

**AC:**
- Given I'm on Settings → Data, When I tap "Export my data", Then a JSON + CSV of my diary, ratings, reviews, follows is emailed to me within 24h.
- Given I tap "Delete my account", When I confirm in a modal (text-confirm), Then my account enters a 30-day grace period; after 30 days all my owned content is hard-deleted.
- Given I'm in the grace period, When I log in, Then I see a "your account is scheduled for deletion in N days — cancel?" banner.

---

<!-- Cluster I (Curated Lists) was added in Revision #1 and removed in Revision #3.
     Lists deferred to v2 — see out-of-scope.md and decision-log.md row 7.
     Stories S-I1 through S-I6 preserved in git history (Revision #1). -->

## Cluster H — Should-have / Could-have

### S-H1 (Should): Last.fm history import as Spotify alternative
**As Maya,** I want to import my Last.fm scrobbling history if I prefer not to connect Spotify, so I can join auxd without OAuth.

**AC:**
- Given I'm in onboarding, When I select "Import from Last.fm instead", Then I provide my Last.fm username and the system fetches up to 365 days of scrobbles, dedupes to album-grain, and pre-populates my diary.

### S-H2 (Should): Album merge / report wrong album
**As Casey,** I want to flag duplicate or wrong albums, so the catalog quality improves.

**AC:**
- Given I see a duplicate album, When I tap "Report wrong album", Then a form opens to specify the issue and (optionally) link to the correct release-group MBID.

### S-H3 (Could): Friend-request flow when private profile is on
**As Maya,** I want the option to approve / reject follow requests, so my private profile gives me control.

**AC:**
- Given my profile is private, When someone tries to follow, Then a "pending request" is created; I'm notified and can approve or reject.

### S-H4 (Could): Weekly emailed digest
**As Casey,** I want a weekly summary of what my friends listened to, so I don't have to open the app daily.

**AC:**
- Given I have weekly digest enabled (default ON), When the cron runs each Monday, Then I receive an email with top 10 entries from my follow graph, grouped by friend.

### S-H5 (Could): Embed / share card
**As Jamie,** I want to share my review on Twitter/X with a nice preview, so my followers see what I'm into.

**AC:**
- Given I'm on my own review, When I tap "Share", Then a system share sheet opens with an OG-image-ready URL.

---

## Story coverage by capability

| Capability (§3 of product-spec) | Stories |
|---|---|
| Rate albums | S-B2, S-B3 (Aux) |
| Log listens (diary) | S-B1, S-B4, S-B5, S-B6 (auto-prompt), S-A2, S-A3 |
| Write/share reviews | S-C1, S-C2 (sort), S-C3, **S-C4 (Like)**, S-H5 |
| Backlog / Up Next | S-D1, S-D2, S-D3 |
| Discover via social graph | S-E1, S-E2, S-E3, S-E4, S-E5 |
| Onboarding | S-A1, S-A2 (skippable), S-A3, S-A4, S-A5 |
| Album detail & search | S-F1, S-F2, S-H2 |
| Profile, settings, privacy | S-G1, S-G2, S-G3, S-G4, S-G5, S-H3 |
| Alternative imports | S-H1 |
| Notifications | S-G3, S-H4 |

> *Curated Lists capability was added in R1 (Cluster I, S-I1..S-I6) and removed in R3 — Lists deferred to v2.*

**Total Must-Have stories: 30 · Should-Have: 2 · Could-Have: 3.** *(Count reconciled in sync-verify Run #1 — see [sync-report.md § DRIFT-L2-003](../sync-report.md#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30). Earlier "32" claim arose from a v1.3 transition arithmetic slip; the enumerated S-* / US-* bodies have always been 30 post-R3.)*
History: 30 stories at v1.0 → 37 at v1.1 (Lists + auto-prompt added) → 30 at v1.3 (6 Lists stories removed, S-C4 Like added, S-B6 carried through as elevated MVP story = 31−1 churn). Estimated build: 3–6 months — back to the v1.0 range, reflecting that R3 ~20% scope reduction nets out against the small S-C4 addition.
