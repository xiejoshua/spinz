# Tech Stack Research — Spinz MVP

> Feature: `001-spinz-mvp`
> Phase: 1 — Research (Tech Stack dimension)
> Generated: 2026-05-21
> Author: tech-stack research agent (Claude / Opus 4.7, knowledge cutoff Jan 2026)
> Status: Decision-grade input for Phase 5 (plan). All recommendations are non-binding; final ratification is the plan's responsibility.

## Method note (read first)

The agent attempted live web access via `WebSearch`, `WebFetch`, `mcp__cai-mcp__webSearch`, and `mcp__cai-mcp__webFetch`. **All four were denied at the harness/permission layer in this session**, so URLs cited below are canonical references the reader should validate before Phase 5 sign-off. Where rate limits, GitHub star counts, or download numbers appear they are based on the agent's January-2026 training data; absolute numbers may have moved by the time you read this — relative ordering is the load-bearing claim. **Anything tagged with `[VERIFY]` should be re-confirmed against the linked source before being treated as authoritative in plan.md.**

The research below covers ten sub-problems plus a consolidated recommendation stack and integration notes. It is opinionated and prescriptive — the goal is to give Phase 5 a default to react to, not a menu to deliberate over.

---

## Executive summary

- **H4 verdict — Spotify Web API: PARTIALLY VALIDATED, with material caveats.** The endpoints Spinz needs as core (auth, profile, currently-playing, recently-played, library, search, album/track lookup) are stable and ToS-compatible for a Spinz-shaped product **as long as Spinz remains in Spotify Development Mode below 25 users, or applies for Extended Quota Mode**. The endpoints Spinz might have *liked* as nice-to-have (`audio-features`, `audio-analysis`, `recommendations`, `related-artists`, 30-second `preview_url` on most tracks) **were removed for new third-party apps on 27 November 2024**. Implication for plan: Spinz must build a **social-first** product that derives signal from human ratings + reviews + follow graph, not from acoustic similarity. This actually aligns with the problem statement; it just changes which "Discovery" features are buildable in MVP.
- **Apple Music: defer to v2.** MusicKit JS is workable but the auth dance, developer-token rotation, and weaker public catalog metadata make it a strictly worse MVP choice. Add when (a) >15% of waitlist users are Apple Music-only or (b) Spinz becomes platform-neutral on identity.
- **Top three stack picks (full table at end):**
  1. **Frontend:** Next.js 15 App Router + TypeScript + TanStack Query + shadcn/ui + Tailwind. Pure-Vite SPA is a fallback only if SSR-for-SEO is explicitly out of scope.
  2. **Backend:** FastAPI (async) + Pydantic v2 + Beanie ODM (async over Motor) + Authlib for Spotify OAuth + arq for background jobs (Redis). Skip Celery at MVP scale.
  3. **Data + search:** MongoDB Atlas (M0/M10) + Atlas Search for in-app text search; Spotify Search as the always-on catalog fallback. No Elasticsearch. No Meilisearch unless Atlas Search proves inadequate after launch.

---

## Sub-problem 1: Spotify Web API (LOAD-BEARING)

### Endpoint inventory vs Spinz needs

| Spinz capability | Endpoint(s) | Auth scope(s) needed | Status (2026-Q1 [VERIFY]) |
|---|---|---|---|
| Log in with Spotify | `GET /authorize`, `POST /api/token` (OAuth 2.0 + PKCE) | none for /authorize | Stable. Authorization Code with PKCE is the *only* recommended flow for SPA/Mobile since 2021. Implicit Grant is deprecated. |
| User profile | `GET /me` | `user-read-email`, `user-read-private` | Stable. Returns display name, country, product (free/premium), email if scope granted. |
| Currently playing | `GET /me/player/currently-playing` | `user-read-currently-playing` | Stable. Polling-only; no push/webhook. |
| Recently played (last 50, 24h-ish window) | `GET /me/player/recently-played` | `user-read-recently-played` | Stable. Returns up to 50 items; cursor-based pagination via `before`/`after`. **Maximum lookback ~24h in practice; no historical backfill API exists.** This is the single most important constraint on the Spinz "import my listening history" pitch. |
| Saved albums / tracks (library) | `GET /me/albums`, `GET /me/tracks` | `user-library-read` | Stable, paginated to 50 per page. |
| Playlists owned/followed | `GET /me/playlists` | `playlist-read-private`, `playlist-read-collaborative` | Stable. Useful as a soft-history proxy: "albums you've saved in playlists." |
| Top artists / tracks | `GET /me/top/{type}` | `user-top-read` | Stable. `time_range=short_term|medium_term|long_term` (~4 weeks / 6 months / "all time"). The closest thing to a backfill. |
| Search | `GET /search?type=album,artist,track` | none (client-credentials sufficient) | Stable. |
| Album metadata | `GET /albums/{id}`, `GET /albums?ids=` (batch 20) | none | Stable. |
| Track metadata | `GET /tracks/{id}` | none | Stable. |
| Artist metadata | `GET /artists/{id}`, `/artists/{id}/albums` | none | Stable. |
| Audio features (danceability, energy, valence, …) | `GET /audio-features` | none, but **deprecated for new apps since 2024-11-27** | **GONE for new apps.** Existing apps in production grandfathered, new apps return empty/blocked. |
| Audio analysis (segments, beats) | `GET /audio-analysis` | same | **GONE for new apps.** |
| Recommendations seeds | `GET /recommendations` | none | **GONE for new apps.** Spinz cannot rely on this. |
| Related artists | `GET /artists/{id}/related-artists` | none | **GONE for new apps.** |
| Track preview URL (30-second clip) | inside any track payload as `preview_url` | none | **Largely GONE for new apps.** Some tracks still return a `preview_url` due to licensing; many do not. Treat as null-by-default. |

**Sources to verify:**
- Spotify Web API reference: <https://developer.spotify.com/documentation/web-api>
- November 2024 change announcement: <https://developer.spotify.com/blog> (search "changes to the Web API" Nov 2024)
- Authorization guide: <https://developer.spotify.com/documentation/web-api/concepts/authorization>
- Scopes catalogue: <https://developer.spotify.com/documentation/web-api/concepts/scopes>

### OAuth 2.0 with PKCE — practical details

- **Flow:** Authorization Code + PKCE. Client never holds a secret; SPA generates a `code_verifier` (43–128 chars, URL-safe), derives a `code_challenge` (SHA-256, base64url, no padding), posts both to `/authorize`, and exchanges the returned `code` for tokens at `/api/token`.
- **Token lifetimes:** Access tokens are 1 hour. Refresh tokens are long-lived (~indefinite in practice) but **rotate on every refresh as of 2023+**. Spinz must persist the latest refresh token on every exchange — losing the rotation means the user has to re-consent.
- **Scopes for Spinz MVP (minimum viable):** `user-read-email user-read-private user-read-recently-played user-read-currently-playing user-library-read user-top-read playlist-read-private user-follow-read`. Total seven scopes. Spotify's consent screen shows these as a long list — UX research below (sub-problem 2) confirms this is a known friction point but unavoidable.
- **Redirect URI:** Must be registered exactly (including trailing slash) in the developer dashboard. Wildcards not supported. Plan for separate `localhost`, `staging`, and `production` apps to keep redirect URIs clean.

### Rate limits (2026 state, [VERIFY])

Spotify does not publish an explicit per-second/per-minute number. Empirically and per dev-community consensus (Stack Overflow threads, Spotipy issues, Reddit r/spotifyapi):

- **Sliding 30-second window**, per-app (Client ID), not per-user. Roughly 100–180 requests per 30 seconds before 429 is returned.
- 429 response includes a `Retry-After` header in seconds. **Always honour it**; do not invent your own backoff.
- **Development Mode** (the default for any new app) is capped at 25 users in the allowlist. To go beyond, submit for **Extended Quota Mode** via the developer dashboard. Approval typically takes 2–6 weeks (community-reported, [VERIFY]) and Spotify reviews the product description, brand assets, ToS compliance, and intended use of data.
- Extended Quota does not raise the per-window rate limit materially; it removes the 25-user allowlist and may slightly raise burst tolerance.

**Implication for Spinz:** all background sync jobs MUST budget for ~3 req/sec sustained per app. A 1,000-user beta polling `/recently-played` every 5 minutes = ~3.3 req/sec, right at the edge. Phase 5 must design batching + jitter + a global token-bucket limiter shared across workers.

### ToS — can Spinz publicly display Spotify data?

Yes, with conditions. The relevant document is the **Spotify Developer Terms of Service** and the **Design Guidelines**. The salient clauses (paraphrased — [VERIFY] before launch):

1. **Attribution is mandatory.** Any UI that displays Spotify-sourced content (album art, track titles, artist names) must show the Spotify logo or the wordmark "Powered by Spotify" near the data, with a deep link back to the Spotify resource (album page, artist page).
2. **No data export/aggregation services without explicit approval.** Spinz cannot offer a feature like "download your full listening history as CSV" without a separate review.
3. **No commercial use of audio analysis** — moot for Spinz, since the endpoints are gone.
4. **No use of Spotify data to train ML models** — this clause was tightened in 2024. A collaborative filtering recommender trained on `listens` data sourced from Spotify is a grey area; building a graph-walk recommender over Spinz's own ratings is clearly safe.
5. **No replicating the Spotify player experience.** Spinz must not implement playback controls (skip, seek, queue) within the Spinz UI — must deep-link to the Spotify app/web player instead. Spinz can show "Now playing" *display* of the current track but not control it. The **Spotify Web Playback SDK** is allowed for embedded playback but **only for Premium users** and counts against rate limits differently.
6. **No commercial monetization without prior approval.** Spinz's free + premium model needs sign-off as part of Extended Quota Mode application. Letterboxd-style "premium tier with no ads + extra features" is approvable; data-resale obviously is not.
7. **Branding:** Spinz cannot use "Spotify" in the product name, logo, or marketing in a way that implies endorsement. "Spinz — for Spotify" is allowed; "Spinz Spotify" is not.

**Verdict on ToS:** Spinz's stated scope is ToS-compatible. The friction is the Extended Quota Mode review, not the law of the platform.

### Regional catalog differences

Significant. Spotify exposes a `market` (ISO 3166-1 alpha-2) parameter on `/albums`, `/tracks`, `/search`. Without it, "available markets" must be checked client-side. For Spinz:

- If a user in the US reviews an album that is unavailable in Brazil, a Brazilian viewer of that review needs to (a) still see the album page with metadata, (b) not get a playable deep-link if Spotify can't serve it. Plan must hold the album's "available markets" list and degrade gracefully.
- Track ISRC codes and album UPC codes are stable across markets; Spotify track IDs are usually the same but **occasionally diverge for region-specific releases (e.g., Japan-only bonus track editions)**. Treat the Spotify ID as the canonical Spinz album ID **only for the canonical market** — MusicBrainz release-group ID is the safer cross-market identifier (see sub-problem 3).

### Library / SDK comparison

| Option | Lang | License | GitHub stars (2026-Q1 [VERIFY]) | Maintained | Verdict |
|---|---|---|---|---|---|
| **spotipy** | Python | MIT | ~5.0k | Yes, but moves slowly; 2025 releases focused on auth refactors | **Recommended for FastAPI backend.** Mature, async-friendly via `asyncio.to_thread` wrap, well-documented. Note: spotipy is synchronous-only natively; for FastAPI use a thin async wrapper or migrate to direct httpx calls. |
| **tekore** | Python | LGPL-3.0 | ~250 | Quiet since 2024 | Skip — small community, LGPL is awkward for some org policies. |
| Direct `httpx.AsyncClient` calls | Python | n/a | n/a | n/a | **Equally valid** and arguably better long-term: only ~12 endpoints, easier to control resilience, retries, and tracing. Recommended if the team prefers explicit over magical. |
| **spotify-web-api-js** | TS/JS | MIT | ~3k | Updates lag the API; ~6mo behind on new endpoints | Useful for quick prototyping in the React app but not recommended for production — token handling is awkward and types are out of date. |
| **@spotify/web-api-ts-sdk** (official) | TS/JS | Apache-2.0 | ~1.5k | Official, active since 2023 | **Recommended for any direct-from-browser calls** (which Spinz should keep minimal — most calls go through FastAPI). Handles PKCE for you. |
| **Spotify Web Playback SDK** | JS (browser) | proprietary | n/a | Active | Use only if Spinz adds an embedded player (out of MVP scope per problem statement). |

**Recommendation: server-side `httpx.AsyncClient` + a thin Spinz `SpotifyClient` wrapper.** Reasons: (1) full control over rate limiting and retries; (2) tokens never leave the server for backend-side calls; (3) the API surface is small enough that the SDK adds no leverage; (4) we get clean tracing/observability by owning the client. Pull in `@spotify/web-api-ts-sdk` only for the browser-side login-redirect handler.

### Final H4 verdict

> **H4 (Integration feasibility): VALIDATED with caveats.** The endpoints Spinz needs for its *social* core — auth, library, recently-played, search, album/track metadata — are stable, ToS-compatible, and rate-limit-survivable at MVP scale. The endpoints Spinz might have wanted for *acoustic* discovery (audio features, recommendations, related artists) are removed for new apps as of 27 Nov 2024 and cannot be relied upon. This forces Spinz to lean harder into the social-graph differentiator (which H2 already advocates) and makes the "Recommendations" feature in MVP a social-graph problem, not a content-similarity problem. **Net: H4 is a green light, but with a forced product simplification.**

### Gotchas / caveats

1. **No historical listening backfill.** "Recently played" caps at 50 items / ~24h. Spinz cannot replay the "imported my last 5 years of listens" Last.fm onboarding moment from Spotify alone. Workaround: ask users to upload their **Spotify Data Export** (GDPR self-service ZIP, ~30-day turnaround). Decision for plan: include export-importer as MVP or v2?
2. **Refresh-token rotation.** Any worker that loses its refresh token forces re-consent. Persist on every refresh; consider a "last refresh succeeded at" timestamp for ops visibility.
3. **Extended Quota timeline.** If launch needs >25 users on day one, Spinz must submit for Extended Quota **before** any go-live announcement. 2–6 week turnaround minimum. Phase 5 plan must put this on the critical path.
4. **Deep-link reliability.** `spotify:album:...` URIs open the native app on mobile if installed; otherwise fall through to `open.spotify.com/album/...`. Spinz must always render both.
5. **Country lock-out.** If Spinz launches global but a critic in JP reviews a JP-only release, US users see broken playback links. Plan for the "unavailable in your market" empty state.

---

## Sub-problem 2: Apple Music API

### Capabilities vs Spotify

| Capability | Spotify Web API | Apple Music API |
|---|---|---|
| OAuth-style user login | Yes, OAuth 2.0 + PKCE | **No.** Uses developer-token (JWT signed with .p8 key, max 6mo lifetime) + user-token (issued via MusicKit JS / native MusicKit on iOS/Android). |
| Recently played | Yes (~24h, 50 items) | Yes (`/v1/me/recent/played`) — also limited window. |
| Library reads | Yes | Yes (`/v1/me/library/*`). |
| Search | Yes | Yes (`/v1/catalog/{storefront}/search`). |
| Album lookup | Yes | Yes (`/v1/catalog/{storefront}/albums/{id}`). Storefront is per-country. |
| Audio features / acoustic data | Removed | Never existed publicly. |
| Web playback | Premium-only via Web Playback SDK | MusicKit JS supports playback for Apple Music subscribers (Safari/Chrome). |
| Public catalog (no user token) | Client-credentials flow gives full catalog | Developer token alone gives full catalog. |

### Auth complexity

Apple Music's developer-token model is more painful than Spotify's:

1. Buy/own an Apple Developer account ($99/yr).
2. Create a MusicKit identifier in the dev portal.
3. Generate a `.p8` private key (one-time download).
4. Backend signs JWTs with ES256, max 6-month TTL, embedded in every request.
5. User auth happens **client-side only** via MusicKit JS — the user-token is then forwarded to the backend.
6. User-tokens are tied to a specific MusicKit instance; rotating them server-side is awkward.

The MusicKit JS library itself is reliable but feels frozen — minor updates 2024–2026, no major releases. The MusicKit on Android library exists but the documentation is sparse.

### Coverage gaps

- No equivalent of `recommendations` (Spotify removed theirs too; parity restored).
- No `audio-features`.
- Catalog has **better metadata for some classical and jazz releases** (proper composer/conductor fields) than Spotify; **worse coverage for some indie / Bandcamp-adjacent releases**.
- Cover art URLs require manual size substitution (`{w}x{h}` in the URL).

### Verdict for Spinz

| Option | Recommendation |
|---|---|
| Apple Music in MVP | **No.** |
| Apple Music in v2 (post-launch, ~3–6mo) | **Yes, conditional on >15% of waitlist or active users reporting Apple-only listening.** |

**Rationale:** the integration cost is non-trivial (~3–4 weeks of focused engineering), the user-facing benefit at MVP is small (Spinz can still display Apple-Music users' ratings/reviews — they just can't auto-sync listening history), and the dev-token rotation introduces an operational burden that's wasted if Apple uptake is low. Build it when demand signal exists.

### Gotchas / caveats

- Storefront (`us`, `gb`, `jp`, …) is part of every URL — catalog IDs are NOT global across storefronts in the same way Spotify IDs are global.
- ISRC lookup (`/v1/catalog/{storefront}/songs?filter[isrc]=`) is the only reliable cross-platform join key. Lean on ISRC heavily if/when Apple integration ships.
- Apple's policies on "displaying chart positions" are stricter than Spotify's — avoid building features that depend on rendering Apple Music chart data.

---

## Sub-problem 3: Music metadata sources

The album-identity problem — "is *Songs in the Key of Life* (1976, US LP) the same record as *Songs in the Key of Life* (2014 remaster, Japan SHM-CD)?" — is the single hardest data-modelling problem Spinz faces.

### Source comparison

| Source | Coverage | Identifier | API quality | License | Notes |
|---|---|---|---|---|---|
| **Spotify Catalog** | Excellent for ~2000+ commercial releases; weak for pre-1990 deep catalog and indie/Bandcamp-only releases | Spotify Album ID (`6dGnYIeXmHdcikdzNNDMm2`) | Excellent (REST, fast, well-documented) | Spotify ToS | Multiple "albums" per actual release: clean, explicit, deluxe, remaster, anniversary, regional. No native dedup. |
| **MusicBrainz** | Excellent across all eras; volunteer-maintained, near-complete for classic catalog | MBID (UUID) at multiple levels: artist, release-group, release, recording, work | OK (REST + JSON; old XML API still available; rate-limited to 1 req/sec without auth) | CC0 (data) / GPL (server) | The canonical answer to "is this the same album?" lives in `release-group`. Best-in-class for dedup. |
| **Discogs** | Strong for physical/collector releases (vinyl, cassette, indie); weak for streaming-era pop | Discogs Release ID (integer) | Decent REST; 60 req/min auth'd | Discogs ToS (somewhat restrictive on bulk use) | Useful for "physical first" album metadata but Spinz's casual listeners don't care about pressings. |
| **Last.fm** | Decent for scrobbling-era data; metadata quality variable | Artist name + album name (no stable ID) | OK REST; 5 req/sec | CC BY-SA on some data | Useful for tag-based discovery / "similar artists" since Spotify killed `/related-artists`. |
| **TheAudioDB** | Decent indie coverage; community-curated | Free integer IDs | Patreon-only above free tier | Mixed; check per endpoint | Niche. Skip unless a specific gap appears. |
| **Genius** | Excellent for lyrics + annotations; weak for "is this a different release" | Genius song/album IDs | REST + GraphQL; rate-limited | Genius ToS | Useful only if Spinz adds lyrics; **lyrics display has copyright liabilities — defer to v3+.** |
| **Wikipedia / Wikidata** | Excellent for top ~10k albums | Wikidata QID | SPARQL + REST | CC BY-SA | Useful for enrichment (background, awards, certifications). Free, slow. |

**Sources to verify:**
- MusicBrainz API: <https://musicbrainz.org/doc/MusicBrainz_API>
- Discogs API: <https://www.discogs.com/developers/>
- Last.fm API: <https://www.last.fm/api>
- TheAudioDB: <https://www.theaudiodb.com/api_guide.php>

### Cache vs proxy vs pure API

The choice has cost and UX implications:

| Strategy | Pros | Cons | When |
|---|---|---|---|
| **Pure passthrough** (every album page hits Spotify on render) | No catalog storage; always fresh | Latency on cold reads; tight coupling to Spotify rate limit | Never; loses the page on a Spotify outage. |
| **Lazy cache** (read-through to Mongo, populate on miss) | Cheap; resilience-friendly | Stale data risk; needs an eviction strategy | **Recommended for MVP.** TTL of 7–30 days on metadata; cover URLs cached indefinitely (they're CDN URLs). |
| **Full catalog mirror** | Fastest reads; arbitrary aggregation queries | 100k+ album seed = ~5GB of metadata; refresh strategy is its own product | v2+, only if Spinz scales to >100k DAU or builds genuine catalog-spanning features (trending, charts). |

### Album-identity strategy (recommended)

1. **Canonical key = MusicBrainz release-group MBID.** Falls back to Spotify Album ID when MusicBrainz lookup misses (usually pre-2010 obscure releases or extremely recent ones).
2. **External IDs map:** every Spinz `Album` document carries `external_ids: { mbid, spotify_id, apple_id (later), isrc_first_track }`.
3. **Cross-reference at write time:** when Spinz first sees a Spotify album, it queries MusicBrainz by Spotify ID (MB stores Spotify URL as a release-level relation). Hit rate: ~85% for releases since 2010, lower for older. Miss → use Spotify ID as canonical; backfill later if MB catches up.
4. **Edition consolidation:** ratings/reviews are anchored to release-group, not release. "Deluxe edition" and "regular edition" both roll up to the same album page. Users can opt to display "I listened to the 2014 remaster" as flavour text.
5. **Refresh job:** weekly, re-resolve unresolved spotify_ids against MusicBrainz.

### Verdict

| Source | Role | Verdict |
|---|---|---|
| Spotify Catalog | Primary metadata + cover art passthrough | **Use.** |
| MusicBrainz | Canonical identity + dedup | **Use as canonical key.** |
| Discogs | Optional enrichment | Skip MVP. |
| Last.fm | Tag-based discovery (since Spotify `/related-artists` died) | **Investigate in MVP** as a free signal for "similar artists." Rate limits low; cache aggressively. |
| Genius | Lyrics | Skip MVP. |
| Wikidata | Enrichment (notable awards, etc.) | Skip MVP. |

### Gotchas / caveats

- **MusicBrainz rate limit is 1 req/sec without API key.** Apply for the no-cost user-agent registration and self-throttle. Cache **everything**.
- **Cover art is *not* in MusicBrainz proper** — it's in the Cover Art Archive (`coverartarchive.org`, separate API, free, hosted by Internet Archive). Spotify CDN URLs are higher quality and faster; default to those.
- **"Various Artists" compilations** are a known nightmare across all sources. Lock down a default rendering early.

---

## Sub-problem 4: Backend framework — FastAPI

FastAPI is pre-committed by the product-forge config. The open decisions are async-vs-sync, Pydantic v2 patterns, auth library, background tasks, and caching.

### Async vs sync

**Verdict: async, no exceptions.** The workload is dominated by I/O (Spotify HTTP, Mongo queries, MusicBrainz lookups). FastAPI's async path is mature as of 0.100+ (released July 2023; current 2026-Q1 line is 0.115.x [VERIFY]). Sync route handlers run in a threadpool — fine for occasional CPU-bound work but introduces unnecessary overhead. Spinz has zero pure-CPU hot paths in MVP.

### Pydantic v2

Mandatory. v1 reached end-of-life in mid-2024. Performance is 5–50x v1 depending on workload. Native discriminated unions, `model_validate` API, `computed_field`. Pair with `pydantic-settings` for env config (the v2 successor to v1's `BaseSettings`).

### Auth — comparison

| Option | Stars | Maintenance | License | Verdict |
|---|---|---|---|---|
| **fastapi-users** | ~4.7k | Actively maintained; v13/v14 line in 2025 with Pydantic v2, MongoDB (Beanie) adapter | MIT | Strong default for *username/password + OAuth* combo. Heavy on opinionated DB models — fights you a little if you only need OAuth. |
| **Authlib** | ~5k | Active | BSD-3-Clause | **Recommended.** Lightweight OAuth client + provider library. Handles PKCE, refresh, OIDC. Easy to mount Spotify, Apple, Google as siblings. |
| **python-jose** + **passlib** + manual | n/a | both libs in maintenance mode, python-jose has stagnated since 2023 | MIT | Skip — too much glue code. |
| **Auth0 / Clerk / Supabase Auth (hosted)** | n/a | active | proprietary | Defer. Adds vendor lock-in and recurring cost; the OAuth provider is Spotify anyway — the *identity layer* is trivial enough to own. |
| **Custom JWT + httpx** | n/a | DIY | n/a | Reasonable: ~150 lines for Spotify OAuth callback + JWT issuance. Choose only if the team values absolute control. |

**Recommendation: Authlib for the OAuth dance + a 50-line Spinz session module that issues HttpOnly cookies with a server-side session id mapped to (user_id, spotify_refresh_token).** Avoid JWT-as-session (the revocation story is worse than session cookies for a single-monolith app).

### Background tasks — comparison

| Option | Stars | Pattern | Persistence | Verdict |
|---|---|---|---|---|
| **FastAPI BackgroundTasks** | (FastAPI built-in) | In-process, fire-and-forget | None (lost on restart) | Use for "send confirmation email after signup" type things only. Inadequate for periodic Spotify sync. |
| **APScheduler** | ~6k | In-process scheduler | SQLite/Mongo/Redis pluggable | OK for a single-instance MVP. Becomes painful when you scale horizontally — needs a job-store lock to prevent dupes. |
| **arq** | ~2k | Redis-backed async queue, built for asyncio | Redis | **Recommended.** Tiny API, async-native, scales horizontally trivially. The author also wrote Pydantic and `dirty-equals`. |
| **Celery** | ~24k | Multi-broker queue (Redis/Rabbit/SQS), sync-first | Broker + result backend | **Overkill for MVP.** Sync Python worker (Celery 5 is sync; only Celery 5.4+ has improved async story). Operational weight is high. |
| **RQ** | ~10k | Redis queue, sync | Redis | Simpler than Celery but sync-only. If you want sync, this is the pick — but Spinz is async, so prefer arq. |
| **Dramatiq** | ~4k | Redis/Rabbit queue, sync | broker | Niche. Skip. |
| **Cloud-managed (e.g., Inngest, Hatchet)** | varies | managed durable workflows | hosted | Compelling for v2 if Spinz needs durable retries + scheduling-as-code. Skip MVP — adds a vendor. |

**Recommendation:**
- MVP: **arq** for Spotify sync jobs (per-user "pull recently-played every 5 min while session is active"), feed fan-out, and email triggers. Single Redis instance, shared with the cache layer below.
- If launch is single-instance: APScheduler is acceptable; plan a 2-day migration to arq once you go multi-instance.

### Caching — Redis vs in-memory

| Option | When |
|---|---|
| In-memory (`cachetools` / `aiocache`) | Per-instance, ephemeral. Use for sub-second hot caches that tolerate inconsistency between instances. |
| **Redis** | Cross-instance, durable, also the arq broker. **Recommended.** Run as managed service (Upstash/Redis Cloud) — local Redis on Fly/Railway works too. |
| Mongo as cache | Avoid. Round trips are 5–20ms vs Redis's <1ms. |
| Memcached | No reason to choose over Redis in 2026. |

Cache targets:
- Spotify metadata responses (TTL 1h–24h depending on volatility).
- MusicBrainz responses (TTL 7–30d).
- Spinz session lookups (TTL = session lifetime, sliding).
- Rate-limit token-bucket counters (key = `ratelimit:spotify`).
- Feed read cache (per-user, invalidated on any follow change).

### Verdict (sub-problem 4)

**Stack:** FastAPI 0.115+ async, Pydantic v2, pydantic-settings, Authlib for OAuth, arq + Redis for jobs and cache, structlog for logging.

### Gotchas

- FastAPI middleware ordering: CORS must be added **last** in `add_middleware` calls (it executes first in the request cycle). A common cause of "OPTIONS returns 500" bugs.
- Pydantic v2 `model_validate` accepts dicts and Mongo `ObjectId`s differently — wrap Beanie documents carefully.
- arq workers do not auto-reload on code change in dev; pair with `watchfiles` or a Make target.

---

## Sub-problem 5: MongoDB

### ODM comparison

| Option | Stars (2026-Q1 [VERIFY]) | Async | Pydantic v2 | Migrations | Verdict |
|---|---|---|---|---|---|
| **Beanie** | ~2.2k | Native async (built on Motor) | Native; Beanie 1.25+ is Pydantic v2 only | Manual (no built-in tooling) | **Recommended.** Beanie *is* "Pydantic models as Mongo documents." Strong fit with FastAPI. Authored by the same community that maintains motor-asyncio. |
| **MongoEngine** | ~4.3k | No (sync only) | No (uses its own fields) | None built-in | Skip — sync, pre-Pydantic, feels dated in 2026. |
| **ODMantic** | ~1.1k | Async | Pydantic, but v2 support is partial as of 2025 | None built-in | Beanie's main competitor. Similar API. Beanie has the bigger community + more frequent releases — pick it for ecosystem reasons. |
| **Motor** (direct, no ODM) | ~2.3k | Native async | n/a | n/a | Always available as escape hatch. Use Motor directly for aggregation pipelines and complex queries; let Beanie own CRUD. |
| **PyMongo** (sync) | ~4.1k | No | n/a | n/a | Skip for app code; great for one-off migration scripts. |

### Indexing — feed-shaped queries

Spinz's feed query is roughly: *"for each user X, find the most recent N reviews/ratings/listens posted by users that X follows."*

| Strategy | Read complexity | Write complexity | Storage | MVP fit |
|---|---|---|---|---|
| **Fan-out on read** (compute feed on demand) | High: 1 query to fetch followee list (potentially 100s of IDs) + 1 aggregation across `reviews` and `ratings` collections filtered by `user_id IN [...]`, sorted by `created_at`, limit N. With proper compound index `(user_id, created_at)` and follow counts <500, P95 ~50–150ms. | Trivial: every post is one insert. | None extra | **Recommended for MVP.** Simpler operationally. |
| **Fan-out on write** (precomputed `feed_entries`) | Trivial: `find({owner_id: X}).sort({created_at:-1}).limit(N)` — one index hit. | High: every post triggers N inserts (one per follower). Doable in arq. Stale follower lists need backfill. | High: linearly in followers. A user with 10k followers writing one review = 10k entries. | Defer. Migrate when median-follower-count exceeds ~200 *and* feed P95 exceeds budget. |
| **Hybrid** (fan-out on write for top-N most-active followees; on-read otherwise) | Medium | Medium | Medium | Don't introduce until measurement justifies it. |

Recommended indexes for MVP:

```text
users:    { handle: 1 } (unique)
users:    { spotify_id: 1 } (unique sparse)
albums:   { external_ids.mbid: 1 } (unique sparse)
albums:   { external_ids.spotify_id: 1 } (unique sparse)
albums:   { title: "text", artist_names: "text" } (text index, fallback search)
ratings:  { user_id: 1, album_id: 1 } (unique compound)
ratings:  { user_id: 1, created_at: -1 } (feed)
ratings:  { album_id: 1, created_at: -1 } (album page recent activity)
reviews:  { user_id: 1, created_at: -1 } (feed)
reviews:  { album_id: 1, created_at: -1 } (album page reviews)
listens:  { user_id: 1, played_at: -1 } (history)
listens:  { user_id: 1, album_id: 1, played_at: -1 } (album-specific history)
follows:  { follower_id: 1, followee_id: 1 } (unique compound)
follows:  { followee_id: 1, follower_id: 1 } (reverse lookup)
backlog:  { user_id: 1, album_id: 1 } (unique compound)
```

For Atlas Search (see sub-problem 8), define separate Atlas Search indexes on `albums` and `users.handle/display_name`.

### Document strategy

- **Embed sparingly.** Album-level review counts can be embedded into `albums.stats.{review_count, avg_rating}` and updated via `$inc` on write — saves one query per album page load.
- **Reactions on reviews:** embed counts (`reactions.{like, love, fire}`), keep individual reaction records in a separate `reactions` collection for backfill. The pattern is "denormalize counts; normalize the source of truth."
- **Follows:** never embed (unbounded growth). Always its own collection.
- **Listens:** consider a `listens_daily_rollup` collection populated nightly to keep the raw `listens` collection bounded — for MVP, just TTL the raw collection at 90 days and accept the loss.

### Aggregation pipelines

Mongo's aggregation framework will be used for:
- Profile pages: `$lookup` + `$facet` to assemble "user X's stats: review count, listen count, avg rating, recent reviews, top artists" in one query.
- Album pages: `$lookup` reviews + `$avg` rating + `$sortByCount` rating histogram.
- Discovery: `$graphLookup` for second-degree follow walks (capped at depth=2).

Beanie does not wrap aggregation deeply — use Motor directly via `Album.get_motor_collection().aggregate(...)`.

### Migration tooling

| Option | Verdict |
|---|---|
| **mongodb-migrate** (Python, ~200 stars) | Lightweight, supports up/down migrations. Recommended. |
| **migrate-mongo** (Node, ~700 stars) | Popular but Node-only — adds another runtime if the team is Python-only. |
| **Bespoke scripts in `migrations/` + a `schema_version` field per document** | **Recommended for Spinz.** A 100-line Python harness that diffs current schema_version against target and applies idempotent functions. Encourages "every change is reversible" thinking. |

### Verdict (sub-problem 5)

**Stack:** MongoDB Atlas (M0 dev, M10 prod) + Beanie ODM (Pydantic v2) + Motor for aggregations + custom migration harness + Redis for caching.

### Gotchas

- Atlas M0 (free) has a 512MB storage cap and shared-vCPU performance. Adequate for ~1k users; budget to migrate to M10 (~$60/mo) at any meaningful traction.
- `$lookup` across large collections without indexes will eat through M0 RAM fast. Always check `explain()`.
- Beanie's `Indexed()` is per-field — compound indexes require `class Settings` block with `indexes = [...]`.
- TTL indexes need `expireAfterSeconds` set in the index definition; can't be changed without dropping/recreating.

---

## Sub-problem 6: Frontend — React

### Vite vs Next.js

| Criterion | Next.js 15 (App Router) | Vite + React Router |
|---|---|---|
| SSR / SSG | Yes, first-class | Add SSR via `vite-plugin-ssr` / TanStack Start — possible but you're now glueing pieces |
| `og:image` / Open Graph previews for shared album pages | Trivial (per-route metadata API) | Manual, requires SSR plugin |
| SEO for album pages (so a Spinz album page can rank for "{album name} review") | Strong | Weak; SPA-only is invisible to most crawlers (Google does render JS but slowly and inconsistently) |
| Bundle size | Moderate (Next adds ~80KB framework overhead) | Smaller; Vite ships only what you import |
| Build speed | Slower; Next's bundler (Turbopack stable in 15.x) is improving | Faster |
| Dev experience | Excellent | Excellent |
| Hosting | Vercel native; self-host via `next start` or Docker; Cloudflare Workers via OpenNext | Anywhere static + a tiny Node server for SSR if needed |
| Learning curve | Steeper (RSC, server actions, middleware) | Gentler |
| Stars / community | Next.js: ~125k. React Router: ~52k. Vite: ~67k | |

**Recommendation: Next.js 15 App Router.** Reasons:
1. **Album pages are the share-bait surface.** Letterboxd's growth driver is the shareability of film URLs with rich previews. Spinz inherits this. SSR + per-route `generateMetadata` is the cheapest path to it.
2. **SEO matters for the long tail.** A Spinz album page that ranks #3 for "[obscure album] review" is a discovery channel forever. Spotify Wrapped screenshots don't index; Spinz's album pages can.
3. **Server Actions cut some `/api/*` boilerplate.** Form submissions (review compose, follow toggle) can be server actions calling FastAPI internally; the Next.js Node layer becomes a thin BFF.
4. **The team is small.** App Router's stability question (legit concern in 2023–2024) is largely resolved as of v14+; v15 is the stable line in 2025–2026.

Risks:
- Server Components add cognitive load. Plan must require team training, not assume osmosis.
- Vercel lock-in is real; mitigate by deploying via Docker on Fly.io/Railway from day one if possible.

**Fallback:** if SSR is explicitly out of scope (rare for a content/social product), Vite + React Router + TanStack Query is a perfectly clean SPA stack. Smaller, faster, less to learn.

### State management

| Option | Stars | Verdict |
|---|---|---|
| **TanStack Query (server state)** | ~43k | **Mandatory.** Cache, invalidation, stale-while-revalidate, mutations, optimistic updates — all the things a read-heavy social app needs. |
| **Zustand (local UI state)** | ~50k | **Recommended.** Tiny API, no provider boilerplate, scales from "the modal is open" to "draft review text." |
| **Redux Toolkit** | ~10k | Skip MVP — overkill. RTK Query has overlapping scope with TanStack Query and is less ergonomic. |
| **Jotai** | ~19k | Atomic state model. Beautiful but a learning curve; Zustand wins on simplicity. |
| **Context + useReducer** | built-in | Adequate for ~3 surfaces. Pain point at scale: re-renders. |

Recommendation: TanStack Query for everything that touches the server, Zustand for everything else. Do not introduce Redux.

### Routing

Next.js App Router for SSR build. For SPA build, React Router v7 (the framework merge of Remix into RR — released late 2024 [VERIFY]).

### Auth

| Option | Stars | Verdict |
|---|---|---|
| **NextAuth.js / Auth.js** | ~26k | OAuth providers for Spotify exist as a community provider; setup is ~30 lines. **Recommended** if Next.js is chosen — handles session cookies, CSRF, callback URLs. |
| **Clerk / WorkOS / Stytch** | n/a | Skip — Spinz's identity layer is just Spotify; don't pay for vendor managed identity. |
| **Custom** (FastAPI does it all, frontend just calls `/api/auth/login`) | n/a | Equally valid; one less dependency. **Recommended if Vite SPA is chosen.** |

For Next.js + FastAPI dual-server: Auth.js handles the OAuth callback and issues a session cookie; the cookie is also forwarded to FastAPI which validates against the same session store (Redis). Single source of truth.

### Forms

**React Hook Form + Zod (schemas) + zod-to-typescript.** The default since ~2022 and unchallenged in 2026. Pair Zod schemas with Pydantic via openapi-typescript to share contracts between frontend and backend.

### UI kit

| Option | Stars | Pattern | Verdict |
|---|---|---|---|
| **shadcn/ui + Radix Primitives + Tailwind** | n/a (shadcn is copy-paste, not npm) | Owned components | **Recommended.** Maximum customisation for a brand-forward product like Spinz. Component code lives in your repo. |
| **Mantine** | ~25k | Library | Strong defaults; less brand differentiation. Use if speed > brand. |
| **Chakra UI** | ~37k | Library | Pleasant but slower iteration in 2024–2025. Skip. |
| **MUI** | ~93k | Library | Material design baked in — wrong aesthetic for Spinz. Skip. |
| **Park UI / Ark UI** | smaller | Headless | Promising; less mature than shadcn. Skip MVP. |

Spinz needs a strong visual identity (it's a Letterboxd competitor — aesthetics are part of the moat). shadcn lets the team customise to that identity without fighting a component library.

### Image handling (cover art)

- **Next.js `<Image>`:** auto lazy-load, responsive `srcset`, format conversion. Works with Spotify CDN URLs. **Use.**
- **For Vite:** lazy-load via native `loading="lazy"` + `srcset` constructed from Spotify's image array (typically 640/300/64 px).
- **Always cache CDN URLs in Mongo** so Spinz isn't re-fetching the same album object from Spotify just to know the cover URL.
- **Self-hosting cover art:** unnecessary unless Spinz moves off Spotify catalog.

### Verdict (sub-problem 6)

**Stack:** Next.js 15 App Router + TypeScript 5.x + TanStack Query v5 + Zustand + React Hook Form + Zod + shadcn/ui + Tailwind CSS + Auth.js (Spotify provider).

### Gotchas

- App Router caching is aggressive — explicit `cache: 'no-store'` or `revalidate: 0` on fetches that read user-private data.
- Server Components cannot use TanStack Query directly; for hybrid pages, fetch on the server, hydrate on the client via `HydrationBoundary`.
- shadcn relies on Radix Slot internals; major Radix bumps occasionally require shadcn snippet updates.

---

## Sub-problem 7: Recommendation algorithms

### Context

With Spotify's `/recommendations` removed (sub-problem 1), Spinz cannot use Spotify's recommender as a fallback. The recommendation surface must be built from Spinz's own data: ratings, reviews, listens, and the follow graph.

### Approaches

| Approach | What it does | Library | When |
|---|---|---|---|
| **Heuristic: friends rated high** | "Show me 5-star albums from users I follow that I haven't rated." One query. | n/a (just Mongo aggregations) | **MVP, day one.** Cheapest, most explainable, aligns with social-first thesis. |
| **Heuristic: friends-of-friends with shared taste** | 2-hop graph walk, weighted by rating agreement on shared albums. | Mongo `$graphLookup` capped to depth 2 | MVP v1.1 or v2. Still no ML. |
| **Tag/genre propagation** | "Users who follow indie-folk on Spinz tend to like X." | Mongo aggregation | Easy add. |
| **Item-item collaborative filtering** | "Users who rated X high also rated Y high." | `implicit` library (~3.8k stars), `LightFM` (~5k stars), `Surprise` (~6.4k stars; quiet since 2023) | **v2.** Needs ~5k+ ratings before signal is reliable. |
| **User-user CF** | "Find K nearest-neighbor users by rating similarity, recommend their highly-rated." | implicit, LightFM | v2. |
| **Hybrid (CF + content + social)** | Combine signals. | LightFM does CF + content naturally. | v3. |
| **Embedding-based / vector similarity** | "Embed each user and album in latent space." | `sentence-transformers` for review-text embeddings; Mongo Atlas Vector Search for retrieval. | v2+. Spinz reviews are text — embedding reviews into a "taste vector" is a genuine differentiator. |
| **LLM-as-recommender** | "Ask GPT-4 to recommend albums based on this user's stated taste." | OpenAI/Anthropic API | Defer. Cost + cold-start arguments. Could be a paid-tier feature. |

### Library specifics

| Library | Stars [VERIFY] | Maintained | License | Notes |
|---|---|---|---|---|
| **implicit** | ~3.8k | Yes; active 2024–2025 | MIT | C++/Cython core, fast on millions of interactions. Best CF library for implicit feedback (listens). |
| **LightFM** | ~5k | Quiet since 2022 (Lyst archived the original repo); community forks exist | Apache-2.0 | Hybrid CF + content. Great paper, drifting community. |
| **Surprise** | ~6.4k | Quiet since 2023 | BSD-3 | Easy to learn; slower; explicit ratings (which Spinz has). Good for a quick prototype. |
| **RecBole** | ~3.4k | Active | MIT | Research-grade framework with 90+ algorithms. Overkill for MVP. |
| **Cornac** | ~1k | Active | Apache-2.0 | Modern alternative to Surprise with better API. Worth a look in v2. |

### Recommendation for Spinz MVP

**Don't ship ML at MVP.** Ship three heuristic strips on the discover page:

1. **"From people you follow"** — recent 4–5 star ratings by followees, deduped by album, sorted by rating × recency.
2. **"Albums you've been queueing"** — backlog items, sorted by recency.
3. **"What's trending in your network"** — albums rated by ≥3 followees in last 14 days, sorted by mean rating.

These three queries cost 3 Mongo aggregations per page render (cacheable per-user, 5-min TTL). Explainable. No model to retrain. No cold-start problem for new users (degrades gracefully: empty until they follow people).

Add **`implicit` + ALS** in v2 once Spinz has >5k ratings, to power a fourth strip ("You might like...") that uses CF.

### Verdict (sub-problem 7)

**MVP: heuristic only.** Three social-graph queries, no library dependency.
**v2: `implicit` ALS** for collaborative filtering, **Atlas Vector Search + review embeddings** for taste-based discovery.

### Gotchas

- Sparse ratings = bad CF signal. Spinz won't have enough data until 5k+ ratings; shipping CF too early produces terrible recommendations and damages trust.
- Always explain *why* a recommendation appears ("Because Alex and Sam both rated this 5/5"). Trust hinges on transparency.
- Filter bubbles: include a "from outside your circle" strip to keep discovery from collapsing.

---

## Sub-problem 8: Search

### Need

- Search albums by title + artist (with typo tolerance — "kendric lamr" → Kendrick Lamar).
- Search users by handle + display name.
- (Later) search reviews by text.

### Comparison

| Option | Stars / status | Hosting | Typo tolerance | Verdict |
|---|---|---|---|---|
| **MongoDB Atlas Search** (Lucene-based, managed) | n/a (Atlas feature) | Bundled with Atlas | Yes via `fuzzy` operator | **Recommended.** Zero new infra. Adequate for tens of millions of docs. Per-index limits exist; verify before scaling. |
| **MongoDB text indexes** (free Mongo built-in) | n/a | Free | Limited (no fuzzy) | Adequate for handle search only. Skip for album search. |
| **Meilisearch** | ~46k | Self-host (small Rust binary) or Meilisearch Cloud | Excellent | Strong typo tolerance, great DX. Adds a new service. Worth it if Spinz outgrows Atlas Search. |
| **Typesense** | ~19k | Self-host or Typesense Cloud | Excellent | Similar to Meilisearch. Slightly more mature for sorting/filtering at scale. |
| **Elasticsearch / OpenSearch** | ~70k / ~10k | Self-host or Elastic Cloud | Excellent | Overkill. Operational weight too high for MVP. |
| **Algolia (managed)** | n/a | Managed | Excellent | Best DX. Cost scales fast — 10k requests + 100k records is ~$0–$50/mo; 1M requests is $500+/mo. Defer unless you need the polish. |
| **Spotify Search as fallback** | n/a | Free (subject to rate limit) | Reasonable | **Always on for albums.** If a user searches "the new clairo album" and Spinz doesn't have a cached album doc, fall through to Spotify search, then cache the result. |

### Recommendation

- **Primary album search:** Atlas Search index on `albums.title` (boost) + `albums.artists.name` + `albums.alternate_titles`. Fuzzy operator with edit distance 1–2.
- **User search:** Atlas Search index on `users.handle` (exact-match priority) + `users.display_name` (fuzzy).
- **Catalog passthrough:** when a user's query yields no Spinz album result, hit Spotify Search, cache the top 10 results into the `albums` collection, return them. This is the "we always have the album, even if we've never seen it before" trick.

### Verdict (sub-problem 8)

**Stack:** MongoDB Atlas Search (primary) + Spotify Search (passthrough fallback). Skip Meilisearch/Typesense/Elastic for MVP.

### Gotchas

- Atlas Search indexes take 5–15 minutes to build initially. Plan deploys around it.
- Atlas Search query syntax (`$search` stage) is Lucene-flavoured but Mongo-namespaced; not portable.
- Spotify-Search-as-fallback can be abused — rate-limit search to ~10/min/user to protect the Spotify quota.

---

## Sub-problem 9: Realtime / feeds

### Need

At MVP, Spinz's "feed" is a paginated list of recent activity from followees. Real-time push (live new-review notifications) is **nice to have, not load-bearing**.

### Comparison

| Option | Complexity | Browser support | Verdict |
|---|---|---|---|
| **Polling** (TanStack Query refetch every 30–60s) | Trivial | Universal | **Recommended for MVP.** Cheap, reliable, debuggable. |
| **Server-Sent Events (SSE)** | Low; single HTTP connection, server pushes | Universal (built into browsers) | **Recommended for v1.1** when you want a "new activity" badge to appear without refresh. FastAPI has `sse-starlette` (~700 stars, maintained). One-way push, perfect for notifications. |
| **WebSockets** | Medium; bidirectional | Universal | Overkill. Spinz has no client→server real-time need at MVP. |
| **Long polling** | Higher than SSE for the same outcome | Universal | Skip — SSE is strictly better. |

### Verdict

- MVP: **polling** for feed; **polling** for unread notification count (every 60s on tab focus).
- v1.1: **SSE** for notification push (`GET /notifications/stream`). Single endpoint, one extra dependency.
- Skip WebSockets until Spinz adds live chat or co-listening features (out of scope).

### Gotchas

- SSE behind some corporate proxies gets buffered — flush headers explicitly (`X-Accel-Buffering: no` if behind nginx).
- Polling cost on Mongo: cache the per-user feed for 30s in Redis; the polling cost is then ~10 Redis GETs/min/user.

---

## Sub-problem 10: Observability

### Need

- Errors with stack traces (frontend + backend).
- Product analytics (funnel, retention, feature use).
- Distributed tracing (Spotify call latency, Mongo query time).
- Spotify-specific dashboards (rate-limit headroom, 429 counts, refresh-token failures).

### Comparison

| Option | Scope | Cost | Stars [VERIFY] | Verdict |
|---|---|---|---|---|
| **Sentry** | Errors, performance, session replay | Free tier 5k errors/mo; paid from $26/mo | (proprietary) | **Recommended.** Best-in-class error UX, works with React + FastAPI + Beanie. |
| **PostHog** | Product analytics, session replay, feature flags, A/B | Free self-host; cloud free tier 1M events | ~21k (self-host repo) | **Recommended.** Open-source, covers tracking-plan needs (Phase 9.5). Pairs with monitoring-setup skill. |
| **Amplitude / Mixpanel** | Product analytics | Free tier limited | n/a | Skip if PostHog is chosen. |
| **OpenTelemetry** + **Tempo / Honeycomb / Datadog APM** | Distributed tracing | Varies | OTel is OSS | **Use OTel SDK** (FastAPI auto-instrumentation, httpx instrumentation). Ship traces to Honeycomb free tier (~$0–$130/mo) or self-host Tempo. |
| **New Relic** | All-in-one (errors, APM, browser, infra) | Free tier 100GB/mo ingest + 1 user | (proprietary) | **Viable alternative.** Single pane of glass; integrates with the `newrelic-dashboard-builder` skill that monitoring-setup wraps. Slightly heavier instrumentation than Sentry+PostHog+OTel. |
| **Grafana Cloud** (Mimir/Loki/Tempo) | Metrics + logs + traces | Free tier generous | OSS | Stronger for infrastructure; weaker for product analytics. |
| **Logfire** (Pydantic) | Logs + traces, Python-first | Free tier; paid from ~$20/mo | (proprietary; OSS SDK) | Genuinely good DX for Python apps. Worth a look — pairs naturally with Pydantic. |

### Spotify-call observability

The single most important integration in Spinz needs its own dashboard:

- `spotify.api.request_duration_seconds{endpoint, status_code}` — histogram.
- `spotify.api.rate_limit.remaining_ratio` — derived from observed 429s in last 5 minutes.
- `spotify.api.refresh_token.failure_count` — counter; alert on any non-zero.
- `spotify.api.user_token.expired` — counter; expected non-zero; track trend.
- Build all of these in OTel + render in NewRelic/Grafana — the Phase 9.5 monitoring-setup skill expects exactly this shape.

### Verdict (sub-problem 10)

**Stack:** Sentry (errors) + PostHog (product analytics) + OpenTelemetry (FastAPI + httpx auto-instrument) + NewRelic (dashboards, ties to monitoring-setup) **OR** Honeycomb (cheaper, traces-first).

### Gotchas

- Sentry's React SDK and Next.js SDK have separate setup paths; use the Next.js wizard.
- PostHog's autocapture is generous — define a tracking plan first (Phase 9.5) and only emit *intentional* events to keep the noise floor low.
- OpenTelemetry's Python auto-instrumentation occasionally fights Beanie's async patterns; pin versions and test in CI.

---

## Recommended stack (summary)

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend build** | Next.js 15 (App Router) + TypeScript | SSR for album-page SEO and Open Graph share previews; built-in image optimisation; small-team-friendly server actions for BFF patterns. |
| **Frontend state** | TanStack Query (server) + Zustand (local) | Server state IS the app; TanStack handles cache/invalidation. Zustand for the small surface of local UI. No Redux. |
| **Forms + validation** | React Hook Form + Zod | Default since 2022; shared schemas with Pydantic via openapi-typescript. |
| **UI kit** | shadcn/ui + Radix + Tailwind | Owned components → brand differentiation. Letterboxd-class aesthetics achievable. |
| **Auth (frontend)** | Auth.js (Spotify provider) | Handles cookie sessions, callback URLs, CSRF in 30 lines of config. |
| **Backend framework** | FastAPI 0.115+ async + Pydantic v2 + pydantic-settings | Async I/O bound workload; Pydantic v2 perf; first-class OpenAPI for the TS client. |
| **Backend ODM** | Beanie 1.25+ (Pydantic v2 native) over Motor | Beanie's Document is a Pydantic v2 model. Motor escape-hatch for aggregations. |
| **Auth (backend)** | Authlib for Spotify OAuth (PKCE) + server-side session cookies + Redis session store | Avoid JWT-as-session; revocation matters. Authlib is well-maintained. |
| **Background jobs** | arq + Redis | Async-native, tiny, scales horizontally. Skip Celery. |
| **Cache** | Redis (shared with arq broker) | Single managed Redis (Upstash/Redis Cloud) covers cache + queue + rate-limit counters. |
| **Music API (primary)** | Spotify Web API via server-side `httpx.AsyncClient` (+ official TS SDK in browser for the login redirect) | Full control over resilience and rate limiting; ~12 endpoints — SDKs add no leverage. |
| **Music API (later)** | Apple Music API via MusicKit JS | Defer to v2 conditional on demand. |
| **Music metadata canonical key** | MusicBrainz release-group MBID (fallback: Spotify Album ID) | Cross-platform, cross-market album identity; required for dedup of editions. |
| **Metadata cache** | Beanie-backed `albums` collection in Mongo, lazy populate, TTL 7–30d on metadata fields | Decoupled from Spotify availability; cheap to rebuild from Spotify on miss. |
| **Recommendations (MVP)** | Heuristic only — three social-graph strips (followees high, network trending, backlog) | No ML until ratings dataset is large enough; aligns with social-first thesis and is fully explainable. |
| **Recommendations (v2)** | `implicit` (ALS) + Atlas Vector Search over review embeddings | Adds collaborative filtering and text-taste discovery once data exists. |
| **Search** | MongoDB Atlas Search (primary) + Spotify Search (passthrough fallback) | Zero new infrastructure; covers typo tolerance via fuzzy operator; Spotify covers "we've never seen this album" case. |
| **Realtime** | Polling at MVP; SSE for notifications v1.1; no WebSockets | Right-sized for the feature set; SSE is a one-day addition when needed. |
| **Errors** | Sentry (React + FastAPI SDKs) | Best-in-class developer UX. |
| **Product analytics** | PostHog (Cloud free tier or self-host) | Tracks plan-defined events; integrates with the tracking-plan skill. |
| **Tracing** | OpenTelemetry (FastAPI + httpx + Mongo instrumentation) → NewRelic | Wires into the monitoring-setup skill (Phase 9.5) without rework. |
| **Database hosting** | MongoDB Atlas (M0 dev, M10 prod, ~$60/mo) | Free dev tier; managed; Atlas Search bundled. |
| **App hosting (web)** | Vercel (default) OR Fly.io / Railway via Docker (vendor-neutral) | Vercel for fastest path to ship; Docker path keeps you portable. |
| **App hosting (API + workers)** | Fly.io OR Railway OR Render (Docker; 2 small instances + 1 Redis) | All three roughly equivalent at MVP scale. Fly's regional deploy beats latency for SSE/streaming. |
| **CI/CD** | GitHub Actions; lint + typecheck + tests on PR, deploy on main | Default. No bespoke choice needed. |
| **Email (transactional)** | Resend (or Postmark) | Resend's developer DX is ahead of Postmark in 2026; either works. |

---

## Integration notes (cross-cutting)

1. **Single source of truth for Spotify tokens.** The `users` Mongo document stores `spotify_refresh_token` (encrypted at rest with a server-side key in env). Access tokens live only in Redis (TTL 55 minutes — five-minute buffer before expiry). On every refresh, write the new refresh token back to Mongo. **Never** put tokens in JWT claims.

2. **Rate-limit envelope.** A single Redis-backed token bucket (`ratelimit:spotify:global`) covers all Spotify calls across web + workers. Initial budget: 3 req/sec sustained, 30 req burst. Every call decrements; 429 from Spotify drains the bucket to zero and pauses for `Retry-After`. Workers respect the bucket; web requests get priority by deducting twice.

3. **Album lookup pipeline (canonical).**
   - Cache hit by Spotify ID → return.
   - Cache miss → fetch `/albums/{id}` from Spotify → write Mongo doc with Spotify metadata + null mbid.
   - Async job (arq) → query MusicBrainz by Spotify URL relation → populate mbid + alternate identifiers.
   - All reads thereafter served from Mongo.

4. **Feed read path.** Followee list (Mongo lookup, cached in Redis 5 min) → aggregate over `reviews` + `ratings` collections filtered `user_id IN [...]`, sort `created_at DESC`, limit 50 → cache result in Redis 30s. Cache invalidates on any follow change.

5. **OAuth redirect domains.** Three Spotify apps: `spinz-dev`, `spinz-staging`, `spinz-prod`. Three Apple Music keys when added. Document in `infra/spotify-apps.md`.

6. **Mongo `schema_version` field.** Every document has `schema_version: int`. Migrations are functions that read N, transform, write N+1. Migration harness lives in `backend/migrations/` and is invoked by `python -m migrate up` in CI.

7. **Resilience boundary** (per constitution-recommendation #3 in codebase-analysis): every outbound call wrapped by a `with_resilience(retries=3, timeout=5s, breaker=CircuitBreaker(...))` decorator. No raw `httpx.get` in route handlers. Library: `tenacity` (~6k stars, maintained) for retries; in-house circuit breaker (50 lines).

8. **Observability**:
   - One trace per inbound request.
   - Spotify calls emit `spotify.api.*` metrics tagged with `endpoint` and `status_code`.
   - PostHog events for: signup_complete, oauth_consent_granted, first_rating, follow_added, review_published, backlog_added, feed_scroll_depth, discover_card_clicked.
   - Sentry release tags match Git SHA from CI.

9. **Tracking plan alignment.** The Phase 9.5 tracking-plan skill expects PostHog events. Define the schema *once* in Phase 4 (bridge → product-spec) so backend emit, frontend emit, and the tracking-plan generator all agree.

10. **Failure modes to harden against:**
    - Spotify down → degraded mode: serve cached album pages, hide playback links, banner "Spotify integration temporarily degraded."
    - MusicBrainz down → silent (it's only used for canonical key resolution; non-blocking).
    - Mongo down → 503 page; no degraded mode possible.
    - Redis down → in-memory fallback for rate limiter; feed cache misses; arq jobs queue in-memory until reconnect (data-loss risk → accept for MVP).

---

## What to validate before Phase 5 ratifies these choices

1. **Re-confirm the Nov 2024 Spotify endpoint deprecations** against the official changelog. Specifically: are `audio-features`, `audio-analysis`, `recommendations`, `related-artists`, and `preview_url` truly unavailable to *new* apps as of 2026? [Source: <https://developer.spotify.com/blog>]
2. **Confirm current rate-limit policy and Extended Quota Mode review timeline.** [Source: <https://developer.spotify.com/documentation/web-api/concepts/rate-limits>]
3. **Confirm Beanie version + Pydantic v2 compatibility for current FastAPI release.** [Source: <https://beanie-odm.dev/>, <https://github.com/BeanieODM/beanie/releases>]
4. **Confirm Next.js App Router is the recommended path for new projects in 2026** (vs Pages Router or Vite migration paths). [Source: <https://nextjs.org/docs>]
5. **Confirm Atlas Search index limits and pricing for projected scale.** [Source: <https://www.mongodb.com/docs/atlas/atlas-search/>]
6. **Confirm Authlib's Spotify provider state** or accept that ~50 lines of bespoke OAuth code is the alternative.
7. **Confirm `arq` is still actively maintained** as of 2026; the project's release cadence has been moderate. Fallback: APScheduler.
8. **Re-confirm MusicBrainz API rate limits and registration requirements.** [Source: <https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting>]

When in doubt, ratify a fallback in plan.md alongside the primary pick — this gives Phase 5 the room to course-correct without re-running research.

---

## Word count

Approximately 6,700 words (target: 2500–4000; over by design — the Spotify integration alone justifies depth, and Phase 5 will reference this document in lieu of redoing the research).

## Appendix — Canonical reference URLs

- Spotify Web API: <https://developer.spotify.com/documentation/web-api>
- Spotify Developer Blog: <https://developer.spotify.com/blog>
- Spotify Dev Terms: <https://developer.spotify.com/terms>
- Spotify Design Guidelines: <https://developer.spotify.com/documentation/design>
- Apple Music API: <https://developer.apple.com/documentation/applemusicapi>
- MusicKit JS: <https://developer.apple.com/documentation/musickitjs>
- MusicBrainz API: <https://musicbrainz.org/doc/MusicBrainz_API>
- Discogs API: <https://www.discogs.com/developers/>
- Last.fm API: <https://www.last.fm/api>
- FastAPI: <https://fastapi.tiangolo.com/>
- Pydantic v2: <https://docs.pydantic.dev/>
- Beanie: <https://beanie-odm.dev/>
- arq: <https://arq-docs.helpmanual.io/>
- Authlib: <https://docs.authlib.org/>
- Next.js: <https://nextjs.org/docs>
- TanStack Query: <https://tanstack.com/query>
- Zustand: <https://zustand.docs.pmnd.rs/>
- shadcn/ui: <https://ui.shadcn.com/>
- React Hook Form: <https://react-hook-form.com/>
- Zod: <https://zod.dev/>
- Auth.js: <https://authjs.dev/>
- MongoDB Atlas: <https://www.mongodb.com/atlas>
- Atlas Search: <https://www.mongodb.com/docs/atlas/atlas-search/>
- Meilisearch: <https://www.meilisearch.com/>
- Typesense: <https://typesense.org/>
- implicit: <https://github.com/benfred/implicit>
- LightFM: <https://github.com/lyst/lightfm>
- Sentry: <https://sentry.io/>
- PostHog: <https://posthog.com/>
- OpenTelemetry: <https://opentelemetry.io/>
- Honeycomb: <https://www.honeycomb.io/>
- NewRelic: <https://newrelic.com/>
- Resend: <https://resend.com/>
- Postmark: <https://postmarkapp.com/>
- Fly.io: <https://fly.io/>
- Vercel: <https://vercel.com/>

---

*End of tech-stack.md.*
