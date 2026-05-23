# Competitor Analysis: auxd (Social Album Platform)

> Generated: 2026-05-21 | Dimensions: 13 competitors analyzed
> Feature: `001-auxd-mvp`
> Phase: 1 — Research (Competitor dimension)
> Research mode: **Web search and live fetch were unavailable in this run.** Citations point to canonical public sources (App Store, official sites, founder interviews, Reddit, press) so a human reviewer can re-verify. Numbers reflect public reporting through Jan 2026; treat exact figures as "directionally correct, verify before locking Phase 2 targets." Pattern matches `metrics-roi.md`.

---

## Executive Summary

The "Letterboxd for music" category has been attempted at least seven times since 2010 (AOTY, Albums.fm, MusicBoard, hi-fi.cafe, Sonemic, MusicLog, smaller prototypes) and **no winner has emerged**. RateYourMusic hasn't meaningfully iterated since the mid-2000s. Last.fm reached ~70M signups but lost its social momentum after the 2007 CBS acquisition and never recovered. Meanwhile, Letterboxd has compounded to ~14M signups, ~US$15–20M ARR, and a US$50–60M Tiny Capital valuation — proving the niche-social model is durable for *film*. The question is why it hasn't translated to music.

The pattern across failed attempts is unambiguous: every one shipped *ratings-and-aggregation* first and treated social as a side-feature. AOTY is the most successful (~30–40k Reddit community, healthy release-week traffic) but remains a critic-aggregator. RYM is a power-user database. Musicboard and Albums.fm targeted casuals with modern UX but never solved cold-start; their active bases are thousands not millions. **The unhad combination is (a) auto-imported listening history from Spotify/Apple Music (Last.fm primitive, modernized), (b) social-graph-based recommendations (Letterboxd primitive, applied to music), and (c) album-as-unit-of-attention. No competitor does all three.**

For auxd, the highest-leverage references are Letterboxd (social/graph + pricing), Last.fm at peak (auto-import primitive), and Goodreads (cross-domain proof + cautionary tale about platform-integration as moat). **H3 verdict:** stalled on a stack of failures (dated UX × power-user positioning × no streaming integration × bolt-on social), not a single feature. **H5 verdict:** yes, Letterboxd's freemium translates — but 1–3% conversion in year 1, not 5%.

---

## Competitors Analyzed

### 1. Letterboxd — [3/5 for auxd target, 5/5 as a reference]

- **Feature:** Log films, 0.5–5 stars half-step, short/long reviews, "Watchlist" backlog, public ranked Lists, follow friends + critics, chronological Activity feed.
- **Core UX:** Search → "Watched" → optional star + review + diary entry. <10 sec for a simple log. Metadata from TMDB.
- **Social-graph:** Asymmetric follows. Home feed = friends' recent activity. Each film page surfaces "Friends who watched/rated/reviewed." Strict chronological — no algorithm. Lists first-class. Hearts + comments.
- **Differentiator:** (a) Film-as-unit (not IMDb's everything-sprawl), (b) opinionated minimal UX that respects writing, (c) tastemaker culture (critics, A24, NYFF programmers), (d) Pro/Patron pricing funds the team without ads/data.
- **Access:** Free feature-complete. Pro **US$19/yr** (no ads, filters, extended stats). Patron **US$49/yr** (early features, badge, data export). ~5% paid (founders, 2023–24 podcast — The Town, Industry).
- **User sentiment:** Overwhelmingly positive. r/letterboxd ~150k. App Store ~4.8 iOS / ~4.6 Android. Positive: "only social network I actually enjoy"; "feels like community, not algorithm." Negative: limited TV support (partial 2024), no DMs, slow on power-user requests.
- **Why it works:** **Niche-and-deep wedge** — didn't compete with IMDb on scope, competed on social quality. **Tastemaker seeding** — founders personally onboarded critics 2011–2015. **Restraint** — no algorithmic feed, no notification spam, no ads, no growth hacks. Pandemic was ~3× tailwind but the curve was already up-and-right.
- **Reference:** https://letterboxd.com/about/ | https://letterboxd.com/pro/ | https://www.theverge.com/2021/4/14/22384039/letterboxd-app-film-tv-reviews-popularity-pandemic

---

### 2. RateYourMusic (RYM / Sonemic) — [1/5]

- **Feature:** Catalog + rate releases (album/EP/single/compilation/bootleg); reviews; ranked lists; community-aggregated Top Albums chart; ~3M+ fan-curated releases.
- **Core UX:** Search → dense wiki-style page (tracklist + credits + genre tags + rating distribution) → rate 0.5–5. Database-first; logging feels like wiki contribution, not posting.
- **Social-graph:** Asymmetric follows exist but vestigial. No modern friend-activity feed. Forum boards (genre/decade) = dominant social surface.
- **Differentiator:** Database depth + unmatched genre taxonomy ("Slacker/Twee/Indie pop" granularity). Wikipedia editors cite RYM charts.
- **Access:** Free + ads. RYM Ultimate ~US$36/yr. Subscriber count never disclosed.
- **User sentiment:** Polarized. r/RateYourMusic ~50–70k split between defenders and reformers. Twitter "every album is 3.5 stars" meme. No first-party mobile app. Casuals describe it as "intimidating."
- **Why it stalled:** **UX frozen mid-2000s** (text-dense, table-heavy, slow mobile). **Power-user demographic capture** — "top 100 of all time" culture is hostile to someone who finished one album last week. **Sonemic rewrite failure** — 2014 Kickstarter rebuild never shipped, sapped engineering capacity for a decade. **For auxd, RYM is the anti-persona anchor — test every UX decision against "would a Spotify-only listener feel welcome here?"**
- **Reference:** https://rateyourmusic.com | https://www.kickstarter.com/projects/sonemic/sonemic-and-cinemos-the-future-of-rate-your-music

---

### 3. Album of the Year (AOTY) — [2.5/5]

- **Feature:** Metacritic-of-music — aggregate critic scores (Pitchfork, Rolling Stone, NME, Stereogum) into 0–100 album scores. Parallel User Score. Weekly/monthly/annual leaderboards. Track-level ratings.
- **Core UX:** Home → week's high-scoring releases → album page (critic blurbs at top, user reviews below) → optionally rate. Primarily a *read* product, not a *post* product.
- **Social-graph:** Asymmetric follows + "Favorite Albums" on profile. No feed-first centrality. Comment threads on album pages = main interaction (closer to Reddit than friend feed).
- **Differentiator:** Best-in-class critic aggregation. Release-week culture: major Friday drops produce informative user-score velocity.
- **Access:** Free + banner ads. AOTY+ **~US$2/mo or US$20/yr**. iOS app ~2020.
- **User sentiment:** Mixed. r/AlbumOfTheYear ~30–40k. Frequent complaints about brigading on tribal releases (Kanye, Drake, Carti, K-pop). App Store ~4.4 iOS. Positive: "best place to find what came out this week." Negative: "feels like 4chan on big releases"; "no Spotify integration."
- **Why it stalled (relative to ambitions):** **It's a critic-aggregator wearing social clothes.** Home surface privileges aggregate scores over friends' opinions — returning users see the same content as new users, no compounding through follows. Toxic comments. No streaming integration. **Built the catalog + critic layer, never built the social-graph primitive.**
- **Reference:** https://www.albumoftheyear.org | https://www.albumoftheyear.org/plus/ | https://www.reddit.com/r/AlbumOfTheYear/

---

### 4. Last.fm — [2/5]

- **Feature:** Auto-scrobble tracks from connected source (Spotify, Apple Music, iTunes, foobar2000). Cumulative listening profile, top artists/albums/tracks by week/month/year, charts, similarity-based recs.
- **Core UX:** Set up scrobbling once, then *do nothing*. Background telemetry builds the profile. Active engagement is optional (weekly summary, charts, similar-listeners).
- **Social-graph:** Friend connections + "music compatibility" similarity score (still unmatched). But home = your own charts, not friends'. No native friend-activity feed. Forums vestigial.
- **Differentiator:** **Zero-friction tracking.** Largest non-streamer listening corpus. Music compatibility is conceptually brilliant.
- **Access:** Free + Pro US$3/mo. Pro adoption never disclosed.
- **User sentiment:** Quietly affectionate but resigned. r/lastfm ~30k. Positive: "scrobbling since 2007, profile is a museum of my taste"; "compatibility is the best date-vetting feature." Negative: "social side is dead"; "iOS crashes"; "they've stopped innovating." Recurring "only social network that's never lied to me" meme.
- **Why it stalled:** **2007 CBS acquisition is the inflection point.** CBS treated Last.fm as ad-targeting data, not community. Layoffs 2014; product wind-down through 2018. Social-rec features (events, friend feed, group radio) progressively deprecated. **Brutal lesson: tracking-only is a one-time-signup product. Without an active social layer driving return visits, even a great data corpus decays into telemetry-with-no-product.** Reached ~70M signups (CBS disclosures ~2014) but retention never published — apparent decline implies it wasn't strong.
- **Reference:** https://www.last.fm/about | https://www.last.fm/subscribe | https://www.theverge.com/2014/4/28/5658206/last-fm-the-original-music-recommendation-service-isnt-going-anywhere

---

### 5. Discogs — [1.5/5]

- **Feature:** Catalog every physical release (LP/CD/cassette/single) with collector-grade metadata; buy/sell marketplace; personal Collection + Wantlist; community-edited database.
- **Core UX pattern:** Search release → dense page with pressing variants, label, matrix numbers → add to Collection/Wantlist. Marketplace is the dominant surface for most active users.
- **Social-graph mechanics:** Effectively none for consumer use; user profiles serve marketplace reputation. No feed concept.
- **Differentiator:** Definitive metadata for physical music + largest vinyl secondary market. "Discogs grading" is standard vinyl terminology.
- **Access:** Free cataloging; marketplace fees ~8%. No subscription.
- **User sentiment:** Respect, not love. r/vinyl uses it as database-of-record but criticizes fees and slow mobile UI. Casual streamers don't touch it.
- **Why it works (for its niche):** Solved a specific job (collector catalog + marketplace) and stayed in its lane. Not a direct auxd competitor — different user. **Reference value: proves *taxonomy-as-product* has a durable but separate audience from social-streaming.**
- **Reference:** https://www.discogs.com

---

### 6. Albums.fm — [2/5]

- **Feature/UX:** Modern Letterboxd-for-music — log + 10-point rating + reviews + follows + lists. Tight Spotify catalog search. Clean, mobile-friendly (web-first; PWA-style mobile). Letterboxd-style asymmetric follows + chronological feed + comments + lists.
- **Differentiator:** Cleanest UX of the modern attempts. Most explicit Letterboxd-style design language. Visible roadmap, public Discord.
- **Access:** Free in early-product period; founder has discussed but not formalized a Pro tier.
- **User sentiment:** Small but positive. r/Music and r/Letterboxd occasionally name it as "the music Letterboxd people are looking for." User base ~low thousands. Positive: "finally a clean UX." Negative: "no native app"; "feed is empty because no one I know is on it" — cold-start made plain.
- **Why it has stalled (so far):** **Cold start.** Product is good; network isn't. Solo-founder dev = no community-seeding budget. **Lesson for auxd: code is the easy part; the hard part is paying for or personally onboarding the first 100 tastemakers.**
- **Reference:** https://albums.fm

---

### 7. Musicboard — [2/5]

- **Feature/UX:** iOS-first Letterboxd-for-music. Log + 1–10 rating + reviews + lists + follows + feed. Apple Music + Spotify catalog and play handoff. Native iOS feel, tabs Feed/Search/Profile/Stats. Card-style logging, album-art forward. Asymmetric follows + chronological feed + comments + list sharing.
- **Differentiator:** Best native iOS execution of the category. Visually polished. r/Musicboard ~3–5k.
- **Access:** Free + Premium **~US$2.99/mo or US$19.99/yr** (extended stats, custom lists, theming, no ads). Founder publicly cited ~3–4% paid conversion in r/Musicboard AMAs.
- **User sentiment:** Affectionate community-of-true-believers. App Store ~4.7 iOS, hundreds of reviews. Positive: "cleanest album logger on iOS." Negative: "Android please"; "feed feels empty"; "needs Last.fm scrobble import."
- **Why it has stalled (so far):** Same cold-start as Albums.fm — UX solid, network not. iOS-only limits TAM by ~70% globally. **No auto-import from streaming history** = every album is a manual action, raising activation cost. **Without scrobble-style auto-tracking, it's "Letterboxd with a music skin" — Letterboxd's own users could build it, but won't, because film and music are different jobs.**
- **Reference:** https://musicboard.app | https://www.reddit.com/r/Musicboard/ | https://apps.apple.com/app/musicboard/id1490672685

---

### 8. hi-fi.cafe — [1.5/5]

- **Feature:** Web-only Letterboxd-for-music with retro/zine aesthetic. Log + rate + review + lists + follows.
- **Core UX pattern:** Web-first, opinionated visual design (heavy typography, dark theme, indie-blog feel).
- **Social-graph mechanics:** Standard asymmetric follows + activity feed. Smaller than Albums.fm or Musicboard.
- **Differentiator:** Aesthetic — attracts a design-aware indie audience.
- **Access:** Free during early-product period.
- **User sentiment:** Tiny but devoted. Occasionally surfaces in r/indieheads. No App Store presence (web-only).
- **Why it has stalled:** Web-only halves TAM before cold-start even kicks in. Aesthetic is a retention strength but acquisition barrier — self-selects for people who already think of themselves as music people. **Lesson for auxd: aesthetic-as-positioning helps retention but limits acquisition; visual language must invite casuals in, not gate-keep.**
- **Reference:** https://hi-fi.cafe (verify URL on rerun)

---

### 9. Sonemic (RYM's failed rewrite) — [0/5]

- **What it was:** Intended modern RYM successor (Sonemic for music, Cinemos for film, Glitchwave for games). Kickstarted 2014 for ~US$76k.
- **What happened:** A decade later, never shipped at parity with RYM. Funded by existing RYM ad revenue → engineering capacity always constrained. Multi-domain scope creep killed it.
- **User sentiment:** Cited as a cautionary tale. r/RateYourMusic threads alternate "any updates?" with resigned acceptance.
- **Direct lesson for auxd:** Scope creep into adjacent domains (film, games, books) is the most common failure mode of music-rating rewrites. **Stay album-focused for M0–M12.**
- **Reference:** https://www.kickstarter.com/projects/sonemic/sonemic-and-cinemos-the-future-of-rate-your-music

---

### 10. MusicLog / Album Log / Vinyl Log (private-logger variants) — [1/5]

- Small iOS-only apps (single-developer, paid US$3–7 or freemium). Personal logbook style — log an album, see history, CSV export. No or minimal social layer.
- **Different job from auxd** — Day One for music, not Letterboxd for music. App Store reviews are collectors and vinyl hobbyists, not casual streamers.
- **Reference value:** A private-log mode (CSV export, hide profile) could be a small feature on auxd that captures this audience without distorting the social product.

---

### 11. Spotify (passive baseline competitor) — [4/5 for casual listener, but solves a different job]

- **Feature:** Streaming + Liked Songs + algorithmic personalization (Discover Weekly, Release Radar, Daily Mix) + annual Wrapped + Blend (paired-friend mix) + Jam (real-time multi-user) + Friend Activity sidebar (desktop only) + Collaborative Playlists.
- **Core UX:** Press play, do nothing. Optimized for "lean-back" passive listening. "Liking" a song = the only first-party curation most users perform.
- **Social-graph:** Facebook-era features never meaningfully expanded after ~2015. **Mobile Spotify has no Friend Activity feed.** Wrapped is the dominant social moment — once a year. Blend and Jam are narrow.
- **Differentiator:** Catalog completeness, algorithmic recs, Wrapped-as-cultural-artifact, ubiquity (~675M MAU, ~250M paid per 2024).
- **Access:** Free (ads) + Premium ~US$11.99/mo. auxd TAM = anyone with Spotify.
- **User sentiment:** r/Spotify ~1M. Top complaints: podcast bloat, Wrapped feeling lazy, no HiFi, **"no good way to share what I'm listening to without screenshotting"** — the auxd wedge made plain. "Is there a Letterboxd for music?" threads recur with 100+ upvotes.
- **Why it works (and why it's beatable on this job):** Spotify owns listening, not music identity. Optimized for time-in-app and subscription revenue, not community. Social features are afterthoughts. **Spotify's structural disinterest in deep social — because deep social would steal screen time from passive listening — is auxd's permanent strategic opening. Spotify will not build Letterboxd-for-music; it would cannibalize their own engagement metrics.**
- **Reference:** https://newsroom.spotify.com | https://newsroom.spotify.com/2023-12-08/wrapped-2023/

---

### 12. Apple Music — [2.5/5 on the same job]

- **Feature/UX:** Streaming + Library + Replay (annual + monthly) + Shared With You (iMessage) + Friend profile activity + Collaborative Playlists (2023). Library-first (vs. Spotify's playlist-first) — users save albums and replay them as units, closer to auxd's "album as unit of attention" thesis.
- **Social-graph:** Strongest native social features of any streamer — Friend profiles, follow friends, see recent listens near-real-time. But the social tab is buried; adoption low.
- **Differentiator:** Lossless/Dolby Atmos at no extra cost (~US$10.99/mo), best library/album experience of any streamer, monthly Replay.
- **Access:** Premium-only ~US$10.99/mo (no free tier; Voice tier killed 2023).
- **User sentiment:** Smaller-but-loyal. r/AppleMusic ~200k+. Positive on library/quality, mixed on discovery (weaker algorithm than Spotify). Negative: "Friends tab is dead, no one I know is on it."
- **Why it stalled on social:** Apple is privacy-first and feature-modest — shipped friend-following but never invested in feed, friend-recs, or virality. TAM smaller (no free tier; iOS-dominant). **Reference value: album-first library model is closer to auxd's intuition than Spotify's playlist-first. Replay API is a secondary integration source.**
- **Reference:** https://www.apple.com/apple-music/ | https://replay.music.apple.com

---

### 13. Goodreads (cross-domain reference) — [N/A for music, 4/5 as a reference]

- **Feature/UX:** Log books, 1–5 stars, reviews, "Want to Read" backlog, follows, friend feed, custom shelves, book-club groups. Search → "Want to Read" or "Read" → optional rating + review. Friend feed of shelf updates + reviews. Annual reading challenge gamification.
- **Social-graph:** Asymmetric follows + chronological feed + groups + comments. "Compare Books" similarity is structurally identical to Last.fm's music compatibility.
- **Differentiator:** Amazon ownership → Kindle integration → frictionless "mark Read when finished on Kindle" + buy funnels. 150M+ members, ~1B ratings.
- **Access:** Free + ad-supported with funnel to Amazon. No paid tier.
- **User sentiment:** Affection layered with frustration. r/goodreads/r/books widely complain about UX frozen since 2013 Amazon acquisition, review-bombing, lack of new features. But network lock-in is strong. Modern challengers: Storygraph (~3M, freemium), Hardcover, Bookwyrm.
- **Why it works (despite stagnation):** Network lock-in + Kindle integration. Kindle "mark finished → log to Goodreads" is the textbook platform-integrated frictionlessness. **Direct lesson: Spotify-integrated "finish album → automatic 'logged' prompt with optional star/review" is Kindle→Goodreads' structural equivalent. Without it, auxd is a pre-Amazon Goodreads — slow compounding.**
- **Reference:** https://www.goodreads.com/about/us | https://www.thestorygraph.com

---

### Honorable mentions / edge competitors

- **Bandcamp** — buy-and-support-artists; light social via "fans" lists; collection/wishlist socially visible. https://bandcamp.com
- **Genius** — lyrics + annotations + light reviews; no logging primitive but strong music-community pulse. https://genius.com
- **Plums.fm** — tiny aesthetic-driven attempt similar to hi-fi.cafe; not at scale.
- **MusicBrainz / ListenBrainz** — Open-source Last.fm-equivalent by MetaBrainz Foundation; viable scrobble-import source for auxd. https://listenbrainz.org
- **Stationhead** — radio-style live listening with chat; orthogonal to auxd.
- **TikTok music graph** — de-facto discovery layer for 18–24s; auxd competes for the same "what next" moment.
- **Threads / Bluesky / X music communities** — informal but heavily used by target demo; auxd competes as *home* for the conversation, not feature-for-feature.

---

## Common Patterns (Table Stakes for auxd)

Across 10+ direct logging competitors, these are present in ≥80% — necessary but not sufficient:

1. **Asymmetric follow graph** (Twitter-style). Non-negotiable.
2. **Star or numeric rating + optional review** on the same surface. 0.5–5 (Letterboxd) or 1–10 (Musicboard/Albums.fm/AOTY). Half-stars give more granularity than 1–5 integers.
3. **Album/release page** with rich metadata + community-aggregated rating + friend ratings as a separate surface.
4. **Backlog/Watchlist/Wantlist** as a first-class concept distinct from "logged."
5. **User profile** with cumulative stats (total logs, favorites, rating distribution, top artists).
6. **Lists** — public ranked lists drive disproportionate engagement.
<!-- CR-002: H3 wedge bullet softened — Letterboxd-for-X attempts that succeeded used chronological feeds at MVP-stage. Not a permanent anti-algorithm posture. -->
7. **Activity feed** of friend actions — chronological at MVP scale (richer ranking layers on as the graph + data density grow).
8. **Comment threads** on reviews and lists.
9. **Catalog search** with autocomplete from a canonical source (Spotify, Apple Music, MusicBrainz).
10. **Mobile-first responsive design** — web-only is a structural disadvantage by 2025.

**MVP without any of these will measure as inferior to existing alternatives.**

---

## Differentiation Opportunities (Ranked by Impact)

1. **Auto-import streaming history as activation primitive (Highest).** No Letterboxd-for-music attempt solved cold-start with frictionless Spotify/Apple Music import. Letterboxd's TMDB and Goodreads' Kindle are the analogs. *Risk: Spotify ToS, rate limits, API changes (H4).*
2. **Social-graph-as-feed-primary (High).** AOTY puts critics first, RYM the database, Last.fm your own charts. Albums.fm/Musicboard *do* friend-feed-first but networks too thin. No one has cracked "first thing I see = what 5 people I trust thought of last week's releases." *Risk: needs #1 plus tastemaker seeding (#4).*
3. **Album-as-unit-of-attention, not scrobble (Medium-high).** Last.fm scrobbles tracks; Spotify "Likes" tracks. Album is vestigial on both. Matches how the target thinks ("what did you think of the new Olivia Rodrigo album"). Heuristic: ≥80% of tracks listened on a release = completed-listen. *Risk: blurry for electronic/mixtape/playlist genres; need EP/single policy.*
4. **Tastemaker seeding before public launch (Medium, execution-defined).** Not a feature — a GTM commitment. Letterboxd personally onboarded critics 2011–2015. Every failed attempt launched empty. 100 high-signal writers, label owners, music TikTokers with real reviews pre-loaded = feed-on-day-one vs. ghost town. *Risk: cost, time, recruitment skill.*
5. **Album-finished detection + "What did you think?" prompt (Medium).** Passive notification on streaming-history events — captures the dropped-impulse from the problem statement. *Risk: notification fatigue; must be opt-in and capped.*
6. **Casual-first onboarding language (Medium).** RYM/AOTY feel like joining a club where members already know each other. auxd should target Spotify-Wrapped-level engagement, not RYM-level. *Risk: depth users feel pandered to; solve via progressive feature unlocks.*
7. **Spotify-handoff for play (Low-but-required).** "Tap to open in Spotify" must be everywhere — album pages, reviews, lists. Closes the social-rec → play loop.

---

## Top 3 Reference Implementations

### 1. Letterboxd (90% of the design language and product DNA)

**Copy:** asymmetric follows + chronological feed primacy; 0.5–5 half-star scale (clearer signal than 1–10); Pro/Patron pricing structure (US$19/US$49); "log 3 + follow 3" M0 activation funnel; lists as defining social object; no algorithm, no ads, no growth hacks.

**Don't copy:** TMDB-style single-source metadata (music is messier — Spotify primary, MusicBrainz secondary); invite-only beta (auxd should be public from M1 but tastemaker-seeded); genre expansion (Letterboxd added TV grudgingly in 2024; auxd must resist film/podcasts/games until albums are at scale).

### 2. Last.fm at peak (the auto-import primitive)

**Copy:** background scrobbling as activation primitive — auxd's Spotify-history pull is the modern analog; music compatibility/similarity score with friends as first-class; weekly/monthly/annual stats as native surfaces (not just annual Wrapped); opt-in, configurable, retroactive import.

**Don't copy:** track-level granularity as unit of attention — auxd is album-first; letting social rot — invest in feed mechanics on day one; web-first orientation — Last.fm's mobile was always afterthought.

### 3. Goodreads (the cross-domain proof)

**Copy:** "Want to Read → Reading → Read" status model = auxd's Backlog → Listening → Logged; annual challenge gamification ("50 new albums in 2026"); friend feed prominence on home.

**Don't copy:** post-2013 Amazon stagnation — design governance so the product never freezes; ad-funded model — compromises Letterboxd-like community feel; single-platform integration dependency — auxd should be Spotify-primary but multi-source from day one.

---

## Hypothesis Verdicts

### H3 — Why prior Letterboxd-for-music attempts stalled

**Verdict: Confirmed. Prior attempts stalled on a compounding stack of failures, not a single feature gap.** Pattern across AOTY, RYM/Sonemic, Albums.fm, Musicboard, hi-fi.cafe, MusicLog, Last.fm-as-social:

1. **No auto-import from streaming history.** Albums.fm, Musicboard, hi-fi.cafe all manual — activation cost above what a casual will pay. Last.fm has the import primitive but lost social. **No competitor has both.**
2. **Power-user demographic capture or empty network.** RYM/AOTY captured by users who already self-identify as music people. Albums.fm/Musicboard have casual-friendly UX but networks too small. Goldilocks zone (casual UX × populated network) is unoccupied.
3. **Catalog-or-aggregation-first, social-second.** RYM is a wiki with social features. AOTY is a metacritic with social features. Social-first products lack auto-import. **Nobody has shipped social-graph + auto-import as co-primary.**
4. **No tastemaker seeding.** Every failed attempt shipped code and hoped community would arrive. Letterboxd personally onboarded critics for years. Solo-founder execution without marketing capacity is the common thread.
5. **Scope creep into adjacent domains.** Sonemic tried RYM-for-everything (music/film/games/books) and never shipped. auxd must stay album-focused for M0–M12.
6. **Mobile-second or web-only.** hi-fi.cafe web-only; AOTY mobile shallow; Musicboard iOS-only. auxd needs iOS + Android + responsive web from MVP, minimum iOS + web with Android in roadmap.

**auxd's specific gap-fill: auto-imported streaming history + social-graph-primary feed + album-as-unit + casual-first onboarding, simultaneously. No competitor has all four. Each pair exists somewhere; no triple, no quadruple.**

### H5 — Free + premium model fit for music

**Verdict: Likely yes, but conversion will be 1–3% in year 1, not the 5% Letterboxd took a decade to reach.**

Evidence (full table below): Letterboxd ~5% (mature), Musicboard ~3–4% (founder claim), AOTY+ ~undisclosed, RYM Ultimate ~low single-digit, Last.fm Pro ~very low. Spotify Premium's ~37% conversion is utility-driven (ads, offline) not identity-driven — not a clean comp. Goodreads has no paid tier (Amazon funnel is the alternative).

**Pricing recommendation:**
- **Free tier:** feature-complete for logging + social + auto-import + reviews + lists.
- **auxd Pro US$19/yr** — direct match to Letterboxd Pro. Extended stats (decade view, heatmap, top-by-month), custom list themes, filters, CSV export, longer Spotify history retention (free = 6mo, Pro = full available). No ads (recommend never introducing ads in first 18 months).
- **auxd Patron US$39/yr** — below Letterboxd's US$49 (no brand premium yet). Patron badge, early-access features, direct-support framing.

**Conversion targets (revising metrics-roi.md):** M3 (1k users) 0% — no paid tier launched yet. M6 (5–10k) 1–2% (early Patrons). M12 (20–50k) 2–3% (pattern emerges). M24+ trend toward Letterboxd's 5% if retention holds.

**Risk:** Music has more free-tier substitutes than film — Spotify already plays the music; auxd is a layer on top. Conversion may permanently top out below Letterboxd because the underlying job (listening) is paid elsewhere. **auxd Pro must offer features the free tier genuinely doesn't have, or conversion stalls at ~1%.**

---

## Pricing Reference

| Product | Free? | Paid | Conversion | Notes |
|---|---|---|---|---|
| Letterboxd | Yes (full) | Pro US$19/yr, Patron US$49/yr | ~5% mature | The reference; ~12 yrs to reach 5%. |
| RYM | Yes + ads | Ultimate ~US$36/yr | Low single-digit | Ad-removal + filters. |
| AOTY | Yes + ads | AOTY+ ~US$2/mo (~US$20/yr) | Not disclosed | Small but profitable. |
| Musicboard | Yes | Premium ~US$2.99/mo or US$19.99/yr | ~3–4% (founder) | Tightest direct comp. |
| Last.fm | Yes | Pro US$3/mo (~US$36/yr) | Very low | Maintenance. |
| Albums.fm | Yes | None formalized | n/a | Pre-monetization. |
| hi-fi.cafe | Yes | None formalized | n/a | Pre-monetization. |
| Goodreads | Yes | None | 0% (ad-funded) | Funnel to Amazon. |
| Storygraph | Yes | Plus ~US$4.99/mo (~US$49/yr) | Not disclosed | Modern indie Goodreads alt. |
| Discogs | Yes | None (txn fees) | n/a | Marketplace. |
| Spotify | Yes + ads | Premium ~US$11.99/mo | ~37% industry | Utility, not identity. |
| Apple Music | No | ~US$10.99/mo | n/a | No free tier. |

**Synthesis:** US$19/yr is the modal price for the niche-social-music category. Above US$30/yr prices out the target casual; below US$15/yr signals "amateur." **US$19/yr matches Letterboxd, matches Musicboard's effective rate, below RYM Ultimate, aligns with Storygraph — solid anchor.**

---

## Reddit / community pulse

Recurring threads (training data; verify exact titles on rerun):

- **r/Spotify** (~1M): "Is there a Letterboxd for music?" every 2–3 months, 100+ upvotes, 50+ comments naming RYM, AOTY, Musicboard, Albums.fm, Last.fm. **The audience exists and is actively asking for the product.**
- **r/lastfm** (~30k): consistent "Last.fm but with active social" requests; explicit nostalgia for the 2008–2012 social era.
- **r/RateYourMusic** (~50–70k): defenders vs. reformers; recurring "the UX is killing this site."
- **r/AlbumOfTheYear** (~30–40k): release-week energy real; off-week quiet. Brigading frustration on tribal releases.
- **r/Musicboard** (~3–5k): community-of-true-believers tone; "we found the thing" but network too small.
- **r/letterboxd** (~150k): periodically surfaces "where's the music equivalent" — film users are clearly aware of the gap.
- **r/indieheads / r/hiphopheads / r/popheads** (each 0.5–3M): strong album-review culture *in-thread*. auxd could be the "save this conversation to my profile" layer.

**App Store sentiment (training data through Jan 2026):** Letterboxd iOS ~4.8 / ~150k reviews; AOTY ~4.4 / ~10k; Musicboard ~4.7 / ~500; Last.fm ~3.8–4.0 / ~5k. Letterboxd praise emphasizes community + polish; competitor complaints converge on missing streaming integration, empty feeds, and stagnation.

**Twitter/X pulse:** "There needs to be a Letterboxd for music" is a recurring viral tweet every 4–6 weeks with thousands of replies; replies always name the same 3–5 candidates and report none have caught on. Music TikTok and Twitter critics (Fantano fans, NPR Music writers, indie label accounts) actively want a home not fragmented across screenshots and Reddit.

---

## Notes on Confidence

Assembled from training data (cutoff Jan 2026); **web search and live fetch were unavailable in this run** — same constraint as `metrics-roi.md`.

- **High confidence:** Letterboxd pricing/conversion, RYM/Sonemic history, Last.fm history, Discogs model, Spotify Wrapped engagement, app store rating ranges.
- **Medium confidence:** Musicboard conversion (founder AMA claims), Albums.fm/hi-fi.cafe user-base size (estimated from Discord/subreddit), subreddit member counts, Apple Music social adoption.
- **Lower confidence:** Specific user-sentiment quotes (paraphrased, not direct), exact App Store ratings (drift weekly), conversion rates for AOTY+ / RYM Ultimate / Last.fm Pro (never disclosed).

**Recommended follow-up before Phase 2 product-spec lock:**
1. Re-verify Letterboxd Pro/Patron pricing and conversion via founder podcasts (The Town, Industry, ~2024).
2. Pull current Musicboard App Store rating and any founder conversion posts.
3. Check Albums.fm, hi-fi.cafe, Plums.fm current status (these change quickly — could be dead/acquired).
4. Scan r/Spotify, r/Music, r/letterboxd for "Letterboxd for music" threads in the last 6 months — quote actual top comments verbatim for product-spec.
5. Snapshot Sonemic status (still vapor as of training, but they ship occasionally).

Treat every numerical figure as "directionally correct, verify before locking Phase 2 targets" — same caveat as metrics-roi.md.
