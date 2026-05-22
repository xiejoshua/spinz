# Plan: auxd MVP — Technical Blueprint

> **Phase 5 — Technical Plan** | Generated: 2026-05-22
> Feature slug: `001-auxd-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - SpecKit Spec: [spec.md](./spec.md)
> - Product Spec: [product-spec/README.md](./product-spec/README.md)
> - Research: [research/README.md](./research/README.md)
> - Decision Log: [product-spec/decision-log.md](./product-spec/decision-log.md)

---

## 0. Pre-Implementation Prerequisites (must complete before any feature work)

### Task 0 — Ratify Project Constitution

`.specify/memory/constitution.md` is currently the unfilled template. **Phase 5B Task 0** is to author the constitution with these five principles (from research/codebase-analysis.md, reviewed against this plan):

1. **External-call resilience.** Every provider/API call wraps in retry + timeout + circuit-breaker. No bare `httpx.get(...)` in feature code; all external calls go through `lib/resilience` helpers. Failures degrade gracefully with documented fallback behavior, never propagate to the user as raw 500s.

2. **Schema-versioned MongoDB documents.** Every Mongo document carries `_schema_version: int`. Readers tolerate `current_version` and `current_version − 1`; lazy-upgrade on next write. Migration code lives in `backend/migrations/{collection}_v{N}_to_v{N+1}.py`. No big-bang migrations.

3. **Library-first modules.** Backend organized as composable libraries, not god-objects. Each `backend/<module>/` exposes a single public service (`<module>.service.<verb>(...)`); internals are private. Cross-module calls go through public services, not internal helpers.

4. **Test-first for catalog/auth edges.** Spotify integration, MusicBrainz integration, and OAuth flows have contract tests written before implementation. Integration tests must pass against Spotify's sandbox / Development Mode before any feature using those edges merges to main.

5. **Observability mandatory.** Every external API call emits a structured log line with `provider`, `endpoint`, `latency_ms`, `status_code`, `request_id`. Every notification dispatch emits a PostHog event. Every error captured to Sentry with feature + module tags.

The constitution should also include a sixth project-specific principle:

6. **Provider abstraction.** Every music-provider integration goes through `lib/providers/MusicProvider` interface; provider-specific code lives in `lib/providers/<provider>/`. Feature code never imports `spotify_sdk` directly. This isolates future deprecations (Spotify removed audio-features in Nov 2024 — the pattern is the protection).

### Task 1 — Submit Spotify Extended Quota Mode Application (Day 1, parallel work)

2–6 week external dependency on Spotify's app-review queue. Submit on **Day 1 of Phase 6** to overlap with implementation. Application requires:
- Business / use-case description (use the wedge thesis from spec.md §1.3)
- Compliance with Spotify Developer Policy + branding guidelines ("Powered by Spotify" attribution on album surfaces)
- Privacy policy + terms of service URLs (placeholders OK at submission; finalize before public launch)
- Sample app screenshots (use wireframes/ HTMLs as placeholders if needed)

**Fallback plan:** All implementation through M2 happens in Spotify Development Mode (25-user quota). Closed-beta wave (M-2 from public launch) operates entirely inside Development Mode. Production-tier quotas only required for public launch; if Extended Quota review is delayed, the launch waitlist can hold real users without violating quotas.

---

## 1. Architecture Overview

### 1.1 Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER (PWA)                              │
│  Next.js 15 App Router · TanStack Query · Zustand · shadcn/ui   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / JSON
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BACKEND (Fly.io)                           │
│  FastAPI (async) · Pydantic v2 · Beanie ODM · Authlib · arq     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   FastAPI app (HTTP)                                     │    │
│  │   ├── auth · diary · reviews · backlog · social         │    │
│  │   ├── feed · albums · search · notifications · prompts  │    │
│  │   └── seeding · moderation · data-export                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   arq worker (background)                                │    │
│  │   ├── spotify_poll · digest_dispatch · suggestions_job  │    │
│  │   ├── moderation_scan · deletion_cascade · gdpr_export  │    │
│  │   └── mbid_reconcile                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────┬──────────────────┬───────────────────┬────────────────────┘
      │                  │                   │
      ▼                  ▼                   ▼
┌──────────┐      ┌──────────────┐    ┌───────────────────┐
│  Redis   │      │ MongoDB Atlas│    │  Spotify API +    │
│  (arq +  │      │  + Atlas     │    │  MusicBrainz +    │
│  cache)  │      │  Search      │    │  Postmark (email) │
└──────────┘      └──────────────┘    └───────────────────┘

Observability: Sentry · PostHog (self-hosted) · OpenTelemetry traces → Fly logs
```

### 1.1.1 Cross-cutting fail-modes (locked in Phase 5C)

The platform makes deliberate fail-mode choices for shared infrastructure:

| Dependency | If unavailable | Fail-mode | Alert |
|---|---|---|---|
| **Redis (notification rate-limit + coalescer)** | All limiting bypassed | **FAIL OPEN** — requests pass through | Sentry `rate_limit.redis_down` |
| **Redis (endpoint rate-limit)** | Per-IP / per-user write-endpoint limits bypassed | **FAIL OPEN** — same policy as notification limiter (defensive layer; missing user activity is worse than briefly unlimited writes) | Sentry `endpoint_rate_limit.redis_down` |
| **Redis (cache)** | Direct DB hits | FAIL OPEN — accept slower queries | Sentry `cache.redis_down` |
| **Redis (arq job queue)** | New jobs cannot enqueue | FAIL CLOSED — API returns 503 for endpoints that enqueue jobs (e.g., GDPR export) | Sentry `jobs.redis_down` |
| **Spotify API** | Provider returns 503/timeout | Circuit-breaker opens; cached metadata served; auto-prompt + import paused | Sentry `spotify.unavailable` |
| **MongoDB Atlas** | Connection refused | FAIL CLOSED — 503 on all data-touching endpoints; static pages still load | Sentry `db.unavailable` (paging) |
| **PostMark (email)** | Send fails | Retry with exponential backoff (3 attempts); on final failure, log to `failed_emails` collection for manual retry | Sentry `email.send_failed` |
| **PostHog** | Event dispatch fails | FAIL SILENT — events dropped; do not block user actions | Sentry `analytics.posthog_down` |
| **Sentry** | Sentry itself down | FAIL SILENT — log to stdout (captured by Fly logs) | (none — fallback log channel) |

Rationale: rate-limiting is defensive (Spotify enforces its own limits at their edge; our limiter prevents misuse, but missing notifications during a Redis outage is a worse user experience than briefly unlimited notifications). Job queue and database are load-bearing and fail closed.

### 1.2 Repository structure

**Monorepo with two top-level packages.** pnpm workspaces for orchestration; `apps/web` and `apps/api` deploy independently.

```
auxd/
├── apps/
│   ├── api/                            (FastAPI backend)
│   │   ├── src/auxd_api/
│   │   │   ├── main.py                 (FastAPI app factory)
│   │   │   ├── settings.py             (Pydantic Settings)
│   │   │   ├── db.py                   (Beanie init + connection)
│   │   │   ├── modules/
│   │   │   │   ├── auth/               (handlers, services, schemas)
│   │   │   │   ├── albums/
│   │   │   │   ├── diary/
│   │   │   │   ├── reviews/
│   │   │   │   ├── backlog/
│   │   │   │   ├── social/
│   │   │   │   ├── feed/
│   │   │   │   ├── search/
│   │   │   │   ├── notifications/
│   │   │   │   ├── prompts/            (just-finished detection)
│   │   │   │   ├── seeding/
│   │   │   │   ├── moderation/
│   │   │   │   └── data_export/
│   │   │   ├── providers/              (MusicProvider abstraction)
│   │   │   │   ├── base.py
│   │   │   │   ├── spotify/
│   │   │   │   └── musicbrainz/
│   │   │   ├── lib/                    (cross-cutting utilities)
│   │   │   │   ├── resilience.py       (retry + timeout + circuit breaker)
│   │   │   │   ├── visibility.py       (single can_read() function)
│   │   │   │   ├── observability.py    (structured logging, PostHog client)
│   │   │   │   └── markdown.py
│   │   │   ├── workers/
│   │   │   │   └── (arq job definitions)
│   │   │   └── migrations/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── contract/               (against Spotify sandbox)
│   │   ├── pyproject.toml              (uv-managed)
│   │   ├── Dockerfile
│   │   └── fly.toml
│   └── web/                            (Next.js 15 frontend)
│       ├── src/app/                    (App Router)
│       │   ├── (auth)/
│       │   │   ├── login/
│       │   │   └── signup/
│       │   ├── (onboarding)/
│       │   ├── (app)/                  (post-auth shell)
│       │   │   ├── page.tsx            (home feed)
│       │   │   ├── @[handle]/          (profile)
│       │   │   ├── album/[id]/
│       │   │   ├── up-next/
│       │   │   ├── discover/
│       │   │   ├── search/
│       │   │   └── settings/
│       │   ├── api/                    (route handlers as needed for OG, share, etc.)
│       │   └── opengraph-image/        (OG image generators)
│       ├── src/components/
│       │   ├── log-sheet/              (THE wedge interaction)
│       │   ├── just-finished-prompt/
│       │   ├── rating-widget/          (½-star)
│       │   ├── aux-toggle/           (🏅)
│       │   ├── review-card/            (with 👍 like button)
│       │   ├── feed-entry/
│       │   ├── critic-badge/
│       │   └── ui/                     (shadcn/ui generated)
│       ├── src/lib/
│       │   ├── api-client.ts           (typed fetch wrapper)
│       │   ├── auth.ts                 (session + tokens)
│       │   ├── posthog.ts
│       │   └── analytics.ts
│       ├── src/hooks/
│       ├── tests/
│       │   ├── unit/                   (Vitest + RTL)
│       │   └── e2e/                    (Playwright)
│       ├── package.json
│       ├── next.config.ts
│       └── vercel.json
├── packages/
│   └── shared-types/                   (TS types generated from Pydantic models via openapi-typescript)
├── .specify/                           (existing — Spec Kit scaffolding)
├── .claude/
├── .product-forge/
├── features/                           (existing — feature artifacts)
├── pnpm-workspace.yaml
├── package.json
├── .github/workflows/
│   ├── ci.yml                          (lint + test on PR)
│   ├── deploy-api.yml                  (push to Fly.io on main)
│   └── deploy-web.yml                  (Vercel auto-deploys; this triggers preview)
└── README.md
```

---

## 2. Tech Stack — Confirmations

All Phase 1 research recommendations confirmed unchanged.

| Layer | Choice | Rationale (vs research recommendation) |
|---|---|---|
| Frontend framework | **Next.js 15 (App Router)** | Confirmed. SSR is load-bearing for album-detail OG previews (share-virality lever) and SEO on `/album/*`. Vite alternative rejected — would need a separate SSR setup that duplicates Next.js plumbing. |
| Frontend state — server | **TanStack Query** | Confirmed. Server cache + automatic invalidation; pairs cleanly with Next.js Server Components. |
| Frontend state — client | **Zustand** | Confirmed. Lightweight for ephemeral UI state (Log sheet open/closed, sort preference, etc.). |
| Frontend UI kit | **shadcn/ui + Radix primitives** | Confirmed. Copy-paste components; full Tailwind control; accessibility built-in (load-bearing for WCAG 2.1 AA). |
| Frontend forms | **React Hook Form + Zod** | Confirmed. Zod schemas double as TS types and runtime validators; can share Zod schemas with backend Pydantic via codegen if needed. |
| Frontend testing | **Vitest + Testing Library + Playwright** | Vitest for unit (faster than Jest, native ESM); Playwright for E2E (per spec.md §10). |
| Backend framework | **FastAPI (async only)** | Confirmed. Locked by config + research; async is essential for Spotify polling. |
| Backend validation | **Pydantic v2** | Confirmed. v2's performance + JSON Schema export power the OpenAPI → TS types pipeline. |
| Backend ODM | **Beanie** | Confirmed. Async-native, Pydantic-v2-native; less boilerplate than raw PyMongo. Bench note: if Beanie ever bottlenecks on aggregation pipelines, drop to raw `motor` for that one query — Beanie supports the escape hatch. |
| Backend auth | **Authlib (Spotify OAuth) + custom email/password** | Authlib chosen over fastapi-users because we need granular control over Spotify-scoped flows and handle policy enforcement (FR-029) that fastapi-users doesn't natively support. Custom session middleware with HMAC-signed cookies (no JWT — simpler, single-server). |
| Backend background jobs | **arq + Redis** | arq is FastAPI-async-native; Celery would force sync-in-async patterns. Redis serves double duty (job queue + ephemeral cache). |
| Backend HTTP client | **`httpx.AsyncClient`** with custom transport | Confirmed. `spotipy` rejected — it's sync-only and would require thread-pool wrapping. Direct `httpx` with custom retry + circuit-breaker transport. |
| Database | **MongoDB Atlas (Shared M0 tier at MVP)** | Confirmed. Free tier handles M3 target (~500 WAL); upgrade to M10 when WAL crosses ~3k. |
| Search | **Atlas Search** (native to Atlas) | Confirmed. One less moving part than Meilisearch/Typesense. Spotify search as fallback for cold catalog. |
| Cache | **Redis (Upstash serverless)** | Album metadata cache (7d TTL), user listening cache (1h TTL), arq job queue, OAuth state. |
| Email | **Postmark** | Transactional email + weekly digest. Resend was the alternative; Postmark wins on deliverability + clear pricing. |
| Web push | **Standard Web Push API + VAPID keys** | No third-party push service needed at PWA stage. |
| Observability — errors | **Sentry** (free tier first) | Confirmed. |
| Observability — product analytics | **PostHog (self-hosted, single container on Fly.io)** | Self-hosted to avoid third-party-tracking compliance surface; single PostHog container is sufficient for M6 scale. |
| Observability — traces | **OpenTelemetry → Fly logs** at MVP | No dedicated tracing backend at MVP; Honeycomb/Tempo deferred to post-launch if needed. |
| Recommendation engine | **Heuristic only (Python, in-process)** | Confirmed. Social-graph walking + mutual-taste overlap; no ML/ALS at MVP. |
| Music identity | **MusicBrainz release-group MBID canonical, Spotify album ID fallback** | Locked. |
| Hosting — backend | **Fly.io (single region: SJC; multi-region post-M3)** | Async-friendly; cheap; pgvector not needed; Redis sidecar via Upstash. |
| Hosting — frontend | **Vercel (Next.js native)** | Edge functions for SSR; OG image generation; cheap. |
| CI/CD | **GitHub Actions** | Lint + type-check + unit/integration tests on PR; auto-deploy on main. |
| Package manager (frontend) | **pnpm** (workspaces) | Faster than npm; deterministic; matches monorepo. |
| Package manager (backend) | **uv** | Fastest Python package manager; deterministic lockfile; lighter than Poetry. |
| Lint / format | **Ruff (Python) + Biome (TS/JS) + Prettier** | Ruff replaces Black + isort + flake8 in one tool. Biome is faster than ESLint for TS; Prettier just for Markdown / JSON. |
| Type checking | **mypy strict (Python) + tsc strict (TS)** | Both enforced in CI. |

---

## 3. Data Model — Finalized

> Schemas as Beanie Documents. Embedded sub-docs vs referenced where noted. All documents carry `_schema_version: int = 1` (per Constitution Principle 2).

### 3.1 Collection inventory + indexes (load-modeling validated for M6 target)

| Collection | Volume estimate at M6 | Indexes | Notes |
|---|---|---|---|
| `users` | 5k–10k | `handle` unique sparse · `email` unique sparse · `status` partial | KSUID `_id`; encrypted token sub-doc |
| `albums` | 50k–200k | `mbid` unique sparse · `spotify_id` unique sparse · Atlas Search index on `title + artist_credit + artists.name` | Lazy-cache; 7d TTL via `cache_expires_at` |
| `diary_entries` | 50k–500k | `user_id + logged_at desc` · `user_id + album_id + logged_at desc` · `album_id + visibility + rating desc` · `visibility + logged_at desc` (sparse on public) | Soft-delete with `deleted_at`; 30d grace |
| `reviews` | 10k–100k | `user_id + created_at desc` · `album_id + reactions.likes_count desc` (R3 Most-Liked sort) · `diary_entry_id` unique | 1:1 optional with DiaryEntry |
| `review_likes` | 50k–500k | `(review_id, user_id)` unique compound · `user_id + created_at desc` | New in R3 |
| `backlogs` | 5k–10k (1 per User) | `user_id` unique | Singleton per User |
| `backlog_items` | 25k–200k | `backlog_id + position` · `album_id + backlog_id` | Per-album visibility override |
| `follows` | 50k–500k | `(follower_id, followee_id)` unique compound · `followee_id + state + created_at desc` · `follower_id + created_at desc` | Asymmetric; `state: 'accepted'` (default) for public profiles |
| `follow_requests` | 1k–20k | `(requester_id, requestee_id)` unique compound · `requestee_id + status + created_at desc` | Sync-fix L3-002 — private-profile pending queue (US-G2 infra) |
| `blocks` | 1k–10k | `(blocker_id, blockee_id)` unique compound · `blockee_id` | Cascade-resolves Follow + FollowRequest |
| `reports` | 100–5k | `target_type + target_id` · `status + created_at desc` | Daily log-scan; `target_type ∈ {user, diary_entry, review, missing_album}` (R3 + sync-fix L3-006) |
| `review_edit_history` | 5k–50k | `review_id + version desc` · `edited_at` (TTL 90d) | Sync-fix L3-003 — FR-030 90-day audit log; never exposed publicly |
| `notifications` | 100k–1M | `user_id + created_at desc` · `user_id + read_at` (sparse) · TTL 90d | Hard-delete via TTL after 90d |
| `notification_preferences` | 5k–10k (embedded on User) | — | Embedded; no separate collection |
| `just_finished_prompts` | 10k–100k | `user_id + state + detected_at desc` · TTL 24h on `pending` | New in R1 |
| `suggested_follows` | 10k–100k | `user_id + score desc` · `dismissed_at` (sparse) | Precomputed offline |
| `critic_seeds` | 25–80 | `priority desc` · `active` partial | Editorial roster |

### 3.2 Beanie model patterns (illustrative; complete in Phase 6)

```python
# apps/api/src/auxd_api/modules/diary/models.py
from beanie import Document, Indexed
from pydantic import Field
from ksuid import Ksuid
from datetime import datetime
from enum import Enum

class Visibility(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"

class DiaryEntrySource(str, Enum):
    MANUAL = "manual"
    SPOTIFY_IMPORT = "spotify_import"
    SPOTIFY_JUST_FINISHED_PROMPT = "spotify_just_finished_prompt"
    SPOTIFY_PREFILL = "spotify_prefill"
    LASTFM_IMPORT = "lastfm_import"

class DiaryEntry(Document):
    _schema_version: int = 1
    id: str = Field(default_factory=lambda: str(Ksuid()))
    user_id: Indexed(str)
    album_id: Indexed(str)
    logged_at: datetime
    rating: float | None = None  # 0.5–5.0 in 0.5 increments
    auxed: bool = False
    review_id: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    source: DiaryEntrySource = DiaryEntrySource.MANUAL
    relisten: bool = False
    device: str | None = None
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "diary_entries"
        indexes = [
            [("user_id", 1), ("logged_at", -1)],
            [("user_id", 1), ("album_id", 1), ("logged_at", -1)],
            [("album_id", 1), ("visibility", 1), ("rating", -1)],
        ]
```

### 3.3 Visibility check — single source of truth

```python
# apps/api/src/auxd_api/lib/visibility.py
async def can_read(viewer: User | None, content: Content) -> bool:
    if content.deleted_at is not None:
        return False
    if viewer is None:
        return content.visibility == Visibility.PUBLIC
    if await is_blocked(blocker_id=content.user_id, blockee_id=viewer.id):
        return False
    if viewer.id == content.user_id:
        return True
    if content.visibility == Visibility.PUBLIC:
        return True
    if content.visibility == Visibility.FOLLOWERS:
        return await is_following(follower_id=viewer.id, followee_id=content.user_id)
    return False  # private + not owner
```

Every read path goes through this function. **Constitution-enforced via lint rule** in Phase 6: no module may compute its own visibility logic — must call `lib.visibility.can_read`.

---

## 4. Auth Architecture

### 4.1 Sign-up flows

**Flow A — Spotify OAuth shortcut:**
1. User taps "Get started with Spotify" → redirect to `https://accounts.spotify.com/authorize` with scopes (§4.4) + PKCE.
2. On callback, exchange auth code for tokens.
3. Fetch Spotify profile → `display_name`, `email`, `external_id`.
4. Auto-create User with handle = first-available slug derived from `display_name`.
5. Store `MusicProvider` embedded sub-doc on User with encrypted tokens (envelope encryption via Fly.io secret).
6. Issue session cookie (HMAC-signed; 30-day rolling expiry).

**Flow B — Email/password:**
1. User submits email + password + handle.
2. bcrypt hash (cost 12); persist User with `password_hash` and `status: active`.
3. Issue session cookie.
4. Spotify connect prompted in onboarding step 2 (skippable).

### 4.2 Session model

- HMAC-signed cookie carrying `{user_id, issued_at, version}`; signed with rotating key from Fly secret.
- 30-day sliding TTL; refresh on every authenticated request.
- No JWTs (no third-party service needs token; sticky session keeps server-side state simple).
- Revocation: `User.session_version` bumped on password change / explicit logout-all-devices → invalidates all prior cookies.
- CSRF protection via double-submit cookie pattern.

### 4.3 Handle policy enforcement (FR-029)

Implementation lives in `modules/auth/handle_service.py`:

```python
async def change_handle(user: User, new_handle: str) -> Result:
    if (now() - user.created_at) < timedelta(days=30):
        return Error("HANDLE_LOCKED_FIRST_30D", available_at=user.created_at + 30d)
    if user.last_handle_change and (now() - user.last_handle_change) < timedelta(days=30):
        return Error("HANDLE_LOCKED_RATELIMIT", available_at=...)
    if await is_reserved_squat(new_handle):
        return Error("HANDLE_RESERVED", verification_url=...)
    if not await is_available(new_handle):
        return Error("HANDLE_TAKEN", suggestions=[...])
    # write new handle; preserve old handle in `handle_redirects` for 90 days
    await persist_redirect(old=user.handle, new=new_handle, expires=now() + 90d)
    user.handle = new_handle
    user.last_handle_change = now()
    await user.save()
```

`is_reserved_squat()` checks against a static list (200–500 entries) deployed alongside backend. Manual review queue + verification flow for claims.

### 4.4 Spotify OAuth scopes (FR-002 / Q22 — LOCKED)

Essential at MVP:
- `user-read-recently-played` (auto-import + just-finished detection)
- `user-read-currently-playing` (just-finished detection — confirms album completion event)
- `user-library-read` (read user's saved albums for backlog hints)

`playlist-read-private` deferred. Scopes are requested in one round at signup OR in onboarding step 2 (skippable). Token refresh happens server-side; refresh tokens encrypted at rest with envelope key from Fly secret.

### 4.5 Endpoint rate-limiting (sync-fix Run #1 — DRIFT-L3-001 → spec.md §6 NFR Security)

All user-action write endpoints are wrapped in a Redis token-bucket rate-limit dependency:

```python
# apps/api/src/auxd_api/lib/rate_limit.py
async def endpoint(
    request: Request,
    key: str,           # "log" | "follow" | "review" | "like"
    per_user_qpm: int,  # configured per-key via Pydantic Settings
    per_ip_qpm: int,
) -> None:
    """FastAPI dependency. Raises 429 on exceeded; FAIL OPEN if Redis down."""
```

Per-endpoint limits (defaults, tunable via `Settings`):

| Endpoint | Per-user qpm | Per-IP qpm | Notes |
|---|---|---|---|
| `POST /diary` | 60 | 120 | Generous — power-loggers may log fast |
| `POST /follow` | 30 | 60 | Anti-spam social graph manipulation |
| `POST /reviews` | 20 | 40 | Anti-spam writes |
| `POST /reviews/{id}/like` | 120 | 240 | Idempotent toggle; generous to allow rapid feed scroll |

Fail-mode is **FAIL OPEN** (see §1.1.1 — same policy as notification rate-limit). Sentry alert tag `endpoint_rate_limit.redis_down` fires on Redis unavailability. 429 responses include `Retry-After` header.

### 4.6 Settings → Integrations (sync-fix Run #1 — DRIFT-L3-007 → spec.md FR-027)

Settings → Integrations is the single management surface for music-provider connections. Lives at `app/(app)/settings/integrations/page.tsx`. Provides:

- **Spotify status row** — connected / not connected, last-sync timestamp, account display name
- **Connect Spotify** CTA (when not connected) → runs the same OAuth flow as onboarding Flow B (§4.1) but skips the auto-import-30-days step until user confirms via the back-fill trigger below
- **Back-fill diary trigger** → enqueues the 30-day import as an arq job; idempotent; shows progress when running
- **Disconnect Spotify** CTA → revokes tokens locally (server-side delete of `User.providers.spotify` sub-doc), removes the OAuth grant via Spotify revocation endpoint best-effort, halts polling for just-finished detection, but **leaves the existing diary intact and immutable** (Q19 decision)

Backend services in `apps/api/src/auxd_api/modules/auth/` (or new `integrations/` module):

```python
async def disconnect_spotify(user: User) -> None:
    """Revoke tokens, delete provider sub-doc, halt polling. Diary untouched."""

async def trigger_diary_backfill(user: User) -> str:
    """Enqueue arq job to back-fill 30 days; return job id for progress polling."""
```

Frontend route is gated behind authenticated session; the disconnect action requires a confirm modal that surfaces "your diary will remain visible — disconnecting only stops Spotify auto-features".

---

## 5. Provider-Interface Abstraction (Constitution Principle 6)

### 5.1 `MusicProvider` interface

```python
# apps/api/src/auxd_api/providers/base.py
from abc import ABC, abstractmethod
from typing import Protocol

class MusicProvider(Protocol):
    """Abstract music provider. All concrete providers (Spotify, MusicBrainz, future Apple Music) implement this."""

    provider_id: str

    async def get_recently_played(self, user: User, since: datetime, limit: int = 50) -> list[Listen]: ...
    async def get_currently_playing(self, user: User) -> CurrentlyPlaying | None: ...
    async def search_albums(self, query: str, market: str = "US", limit: int = 20) -> list[AlbumRef]: ...
    async def get_album(self, external_id: str) -> AlbumDetail | None: ...
    async def get_user_library(self, user: User, limit: int = 50) -> list[AlbumRef]: ...

class CatalogProvider(Protocol):
    """For metadata-only providers (MusicBrainz, Discogs) — read-only catalog access."""

    async def lookup_by_mbid(self, mbid: str) -> AlbumDetail | None: ...
    async def reconcile_spotify_to_mbid(self, spotify_id: str) -> str | None: ...
```

### 5.2 Concrete implementations

- `providers/spotify/SpotifyMusicProvider` — implements `MusicProvider`; wraps `httpx.AsyncClient` with resilience transport (lib/resilience.py).
- `providers/musicbrainz/MusicBrainzCatalogProvider` — implements `CatalogProvider`.
- Feature code injects via FastAPI dependency: `def get_music_provider() -> MusicProvider: return SpotifyMusicProvider(...)`.

### 5.3 Resilience pattern

```python
# Every provider call is wrapped:
async with circuit_breaker("spotify"):
    async with retry(attempts=3, backoff="exponential", jitter=True):
        async with timeout(5.0):
            response = await self.client.get(...)
```

Circuit breaker per-provider (not per-endpoint) — when Spotify-wide fails, fall through to cached responses or surface "Spotify temporarily unavailable" UI.

### 5.4 Future-proofing

Spotify deprecated audio-features / recommendations / related-artists endpoints on 2024-11-27. **The interface deliberately omits these.** No feature code can call them. Apple Music integration in v2 adds an `AppleMusicProvider` implementing the same interface; switching providers is a config change.

---

## 6. Backend Modules — Service Layout

Each module exposes a single `<module>.service.py` with public functions; routes live in `<module>.routes.py`; schemas in `<module>.schemas.py`.

| Module | Public service surface | Notes |
|---|---|---|
| `auth` | `signup_with_email`, `signup_with_spotify`, `connect_spotify`, `disconnect_spotify`, `trigger_diary_backfill`, `change_handle`, `delete_account`, `request_data_export` | Handle policy + 30d immutability lock; integration disconnect leaves diary intact (§4.6) |
| `albums` | `get_or_create`, `resolve_identity`, `aggregate_ratings`, `merge_editions` | MBID canonical / Spotify fallback resolution |
| `diary` | `log_entry`, `edit_entry`, `delete_entry`, `relist_entry`, `user_diary` | Visibility evaluated on read; write endpoint rate-limited (§4.5) |
| `reviews` | `write_review`, `edit_review` *(writes `review_edit_history` row per edit — §3.1 + FR-030)*, `like_review`, `unlike_review`, `list_reviews_for_album` | Sort: newest/most-liked/highest-rated; write/like endpoints rate-limited (§4.5) |
| `backlog` | `add_to_backlog`, `remove_from_backlog`, `reorder`, `auto_remove_on_log` | Private by default |
| `social` | `follow` *(direct or via request — §4.3)*, `unfollow`, `request_follow`, `respond_to_follow_request` *(approve/decline)*, `list_follow_requests`, `block`, `unblock`, `is_following`, `is_blocked`, `user_profile` | Asymmetric; private-profile creates pending FollowRequest (US-G2 infra, sync-fix L3-002); follow endpoint rate-limited (§4.5) |
| `feed` | `home_feed`, `friends_who_rated_for_album` | Fan-out-on-read; weighted ordering |
| `search` | `search_albums`, `search_users` | Atlas Search + Spotify fallback merge |
| `notifications` | `dispatch`, `mark_read`, `list_user_notifications`, `update_preferences` | Dispatcher + adapters |
| `prompts` | `poll_user_for_just_finished`, `dismiss_prompt`, `disable_for_user` | Just-finished detection |
| `seeding` | `get_critic_seeds_for_onboarding`, `record_card_response`, `compute_suggestions` | Pre-checked card ordering |
| `moderation` | `submit_report`, `daily_scan_for_flagged_users`, `actiion_report` | Daily cron |
| `data_export` | `enqueue_export`, `process_export`, `mail_export` | GDPR pipeline |

---

## 7. Frontend Architecture

### 7.1 Routing (Next.js App Router)

- `(auth)` route group — public; sign-up, login, OAuth callback.
- `(onboarding)` route group — authenticated but pre-feed; multi-step flow.
- `(app)` route group — authenticated post-onboarding; bottom-tab nav.
- `api/og/...` — server routes for OG image generation.
- All `/album/[id]` and `/@[handle]` pages are SSR for share-link previews.
- Home feed (`/`) is SSR on first load (so user sees content fast); subsequent navigation client-side via TanStack Query.

### 7.2 Auth on the frontend

- Session cookie set by backend on sign-up / login; `httpOnly`, `SameSite=Lax`, `Secure` in prod.
- `lib/auth.ts` reads session via server-side `cookies()` API in Next.js Server Components.
- Protected layouts redirect to `/login` if no session.
- Client-side hydration carries a sanitized user object in Zustand (id, handle, display_name, avatar_url — no tokens).

### 7.3 API client

- Typed via `openapi-typescript` codegen from FastAPI OpenAPI schema.
- TanStack Query wrappers per endpoint in `src/lib/api/`.
- Mutations invalidate relevant query keys (e.g., `log_entry` invalidates `["diary", user_id]`).

### 7.4 The Log sheet (THE wedge interaction — sub-8-second commit target)

`components/log-sheet/` is the highest-leverage component. Implementation principles:
- Pre-render the sheet inside the layout (always mounted, hidden until trigger) — avoids first-tap-to-render cost.
- Album prefill fetched eagerly on app load (cached for 60s).
- Rating commit is optimistic; server reconciles in background.
- Server-measured commit time: emit PostHog event `log.commit` with `duration_ms` from sheet-open to commit-success; aggregate p50/p95 dashboards.
- Aux icon: 🏅 medal; one-tap toggle independent of rating.
- Review field collapsed by default; tap "Add a review" expands inline (no keyboard pop on initial sheet open).
- Visibility select defaulted to user's `default_entry_visibility` (per FR-013).

### 7.5 Just-finished prompt

`components/just-finished-prompt/` renders at the top of `/` (home feed) when a `JustFinishedPrompt` is in `pending` state for the user.
- Polling: TanStack Query refetch every 60s while app is foreground; SSE consideration deferred to v1.x (polling is enough at MVP scale).
- Overflow menu: "Disable auto-prompts" (POSTs to `notifications/update_preferences` toggling `auto_prompt_enabled=false`), "Don't prompt for this album" (POSTs to `prompts/dismiss?album_id=X` with 30d sticky).

---

## 8. Notification Dispatcher (load-bearing — Goodreads-firehose prevention)

### 8.1 Architecture

```
event source (any service)
   │
   ▼
notifications.dispatch(user_id, type, payload)
   │
   ▼
┌─────────────────────────────┐
│  is_notifiable(user, type)? │  ← checks preferences, quiet hours, blocks
└────────────┬────────────────┘
             │ yes
             ▼
┌─────────────────────────────┐
│  coalesce + rate-limit       │  ← per-actor, per-event, per-window
└────────────┬────────────────┘
             │ pass
             ▼
┌─────────────────────────────┐
│  fan out to adapters         │
│   ├─ InAppAdapter (DB write) │
│   ├─ EmailAdapter (Postmark) │
│   └─ WebPushAdapter (VAPID)  │
└─────────────────────────────┘
```

### 8.2 Coalescer + rate limiter (locked in Phase 5C)

- **Per-user rate limit (per-type, independent):** ≤5 in-app/hour, ≤25/day. Each notification type has its own counter; e.g., follow notifications and review-like notifications consume separate buckets. Excess events queue into a single coalesced "X new updates today" notification.
- **Per-actor rate limit (CROSS-TYPE):** notifications from User X to User Y are coalesced if >3 happen in the trailing 24h. This is INTENTIONALLY cross-type — if X follows Y, then likes 3 of Y's reviews in the same hour, the first 3 events fire individually and subsequent events from X collapse into "X did several things on your reviews today". Resolves A-003 from pre-impl-review.
- **Per-event dedup:** same event-type + same actor + same target within 1h → drop the second.
- **Fail-mode (locked in Phase 5C — resolves A-004):** If Redis is unreachable, the rate-limiter and coalescer FAIL OPEN — notifications dispatch through without limiting, and a Sentry alert fires with tag `notif_limiter.redis_down`. Spotify upstream enforces its own limits at their edge; our limiter is defensive.
- Implementation: Redis sorted-sets keyed by `notif:{user_id}:rate:{type}:{window}` (per-type) and `notif:{actor_id}:{recipient_id}:cross_type:{window}` (cross-type per-actor); TTL'd per-window.

### 8.3 Adapters

- `InAppAdapter`: writes to `notifications` collection; counts toward rate limit.
- `EmailAdapter`: sends via Postmark; transactional emails ignore quiet hours; weekly digest fires Monday 09:00 user-local.
- `WebPushAdapter`: VAPID-signed payloads; respects quiet hours (suppresses push within window); coalesces if multiple events fire close together.

### 8.4 Weekly digest job

- Scheduled via arq cron: every 5 minutes the worker checks for users whose `Monday 09:00 user-local` is in the current 5-minute window; per-user-tz awareness.
- For each eligible user: query top 10 entries from their follow graph past 7 days + 1 "most-rated album in your follow graph this week" hero.
- Render plain HTML email; send via Postmark; emit PostHog event `digest.sent`.
- Suppression: `weekly_digest` channel must be ON in `NotificationPreferences`.

---

## 9. Just-finished Detection (FR-026)

### 9.1 Polling strategy

- Cadence:
  - 5 minutes while user has an active session in the last 24h.
  - 15 minutes if dormant >24h, capped at 60 minutes.
  - Stop after 14 days of no activity (resume on next login).
- Worker: `workers/spotify_poll.py` — arq scheduled task per-user; reads `MusicProvider.get_recently_played(user, since=last_poll)`.
- Aggregation: identify "completed album" event when ≥4 distinct tracks from the same Spotify album are present in the last hour (heuristic — Spotify doesn't expose a clean "album finished" event).

### 9.2 Prompt lifecycle

```
DETECTED (new JustFinishedPrompt, state=pending)
   │
   ├─→ ACTED (user taps "Log") → state=logged, link to DiaryEntry
   ├─→ DISMISSED (user taps "Not now") → state=dismissed, 30d sticky per-album
   ├─→ EXPIRED (>24h with no action) → state=expired (TTL collection)
   └─→ SUPERSEDED (newer prompt for different album arrives) → state=expired
```

Constraints:
- At most one `pending` prompt per user at a time (newest wins).
- `User.auto_prompt_enabled = false` → no `JustFinishedPrompt` records created (poll still runs for the user but doesn't create prompts; this allows enabling later without backfilling).
- Quiet hours: if user is in quiet hours when detection fires, prompt is created but no push fires; in-app shows on next foreground out of quiet hours.

---

## 10. Feed Query Strategy

### 10.1 Fan-out-on-read (DM-1 locked)

```python
# Sketch — feed.service.home_feed
async def home_feed(viewer: User, cursor: datetime | None = None, limit: int = 25) -> FeedPage:
    followed = await social.followed_user_ids(viewer.id)
    if not followed:
        return await pad_with_critic_seed(limit=limit)

    # 1. Pull recent entries from followed users
    candidate_entries = await DiaryEntry.find({
        "user_id": {"$in": followed},
        "visibility": {"$in": ["public", "followers"]},
        "deleted_at": None,
        "logged_at": {"$lt": cursor} if cursor else {},
    }).sort([("logged_at", -1)]).limit(limit * 3).to_list()

    # 2. Apply visibility filter (followers-only entries → check is_following)
    visible = await asyncio.gather(*[
        can_read(viewer, entry) for entry in candidate_entries
    ])
    candidate_entries = [e for e, v in zip(candidate_entries, visible) if v]

    # 3. Apply weighting
    if not viewer.feed_latest_only:
        candidate_entries = apply_weights(candidate_entries, viewer)

    # 4. Pad with critic-seed if sparse
    if len(candidate_entries) < limit:
        candidate_entries += await critic_seed_padding(limit - len(candidate_entries))

    return FeedPage(entries=candidate_entries[:limit], next_cursor=candidate_entries[-1].logged_at if candidate_entries else None)
```

### 10.2 Weighting math (locked in Phase 5C)

For each candidate entry:
```
score = base_recency_score
      + 0.20 * (has_review ? 1 : 0)
      + 0.15 * (rating == 5.0 || rating == 0.5 ? 1 : 0)  # extreme ratings
      + 0.10 * (entry.user_id in top_5_interacted_users ? 1 : 0)

base_recency_score = exp(-age_hours / 72)  # half-life ~3 days
```

**`top_5_interacted_users` definition** (locked in Phase 5C — resolves A-001 from pre-impl-review):

For each viewer, the top-5-interacted users are computed nightly by an arq job (`workers/compute_interaction_scores.py`). For each `(viewer, other_user)` pair, the interaction score is:

```
interaction = (likes_given_by_viewer_to_other × 3)
            + (reviews_by_other_on_albums_viewer_logged_this_month × 2)
            + (profile_visits_by_viewer_to_other × 1)
```

Normalize per-viewer (divide each pair's score by the viewer's max score), then take the top 5. Persisted on `User.top_5_interacted_at_*` with `computed_at` timestamp. Re-computed nightly; new users have an empty list (the 0.10 weight contributes nothing until interaction history accumulates — fine for cold start).

**Sort tiebreak** (locked in Phase 5C — resolves A-002 from pre-impl-review):

When two entries have identical `score`, the secondary sort is `logged_at` descending (newer first). When `score` AND `logged_at` are identical (extremely rare), tertiary sort is `entry_id` (KSUID, deterministic + chronological). This guarantees stable ordering across pagination cursors.

"Latest" toggle skips weighting and sorts strictly by `logged_at` desc with `entry_id` tiebreak.

### 10.3 Switch criteria to fan-out-on-write

Documented in `docs/architecture/feed-fanout.md` (created in Phase 6 Task X):
- Switch when p95 home feed load >200ms at the DB layer (measured server-side, not including SSR render).
- Migration path: introduce `feed_buckets` collection writing-on-DiaryEntry-create; readers consult buckets when populated, fall through to on-read query otherwise.

---

## 11. Search Architecture

### 11.1 Atlas Search index on `albums`

```javascript
{
  "mappings": {
    "fields": {
      "title": [
        { "type": "string", "analyzer": "lucene.standard", "multi": { "edgeNgram": { "type": "string", "analyzer": "edgeNgram" } } }
      ],
      "artist_credit": [
        { "type": "string", "analyzer": "lucene.standard" }
      ],
      "artists.name": { "type": "string", "analyzer": "lucene.standard" },
      "popularity_score": { "type": "number" }
    }
  }
}
```

Search query: `compound`:
- `must`: text match on title + artist
- `should`: boost by `popularity_score`
- Typo tolerance: built-in via Atlas Search fuzzy matching

### 11.2 Spotify search fallback

When Atlas Search returns <5 results, also query Spotify `/search?type=album&q={query}` and merge:
- Spotify results not yet in `albums` collection are lazy-created with a 7d cache window.
- Merged results sort by Atlas-Search score first, Spotify results appended.

### 11.2.1 Report missing album (sync-fix L3-006 → spec.md FR-005 / US-F2)

When BOTH Atlas Search AND Spotify search return zero results for a query, the empty-state UI shows a "Report missing album" link. Tapping submits a `POST /api/search/report-missing` request that creates a `reports` document with `target_type: 'missing_album'`, `target_id: query_string`, and submitter user id. Surfaces in the founder admin queue (Compass at MVP per §13.3); founder may add the album manually or extend Atlas Search ranking. No automated resolution at MVP.

### 11.3 User search

Out of scope at MVP. Users find each other via:
- Follow graph (suggestions)
- Profile URL share (`TBD.app/@handle`)
- Critic-seed directory at `/critics`

---

## 12. Seeding-Strategy Backend

### 12.1 CriticSeed roster

Authored manually by founder; persisted as `critic_seeds` collection records. Each row links to a real User account marked `critic_seed_active=true`.

### 12.2 Pre-checked card algorithm (FR-015 / Q13)

```python
async def get_critic_seeds_for_onboarding(user: User, limit: int = 6) -> list[CriticCard]:
    # 1. Pull active critic seeds sorted by priority desc
    seeds = await CriticSeed.find({"active": True}).sort([("priority", -1)]).to_list()

    # 2. Score each seed by relevance to user's just-imported taste signal
    user_genre_signature = await compute_genre_signature_from_imports(user)
    scored = [(s, similarity(s.genre_signature, user_genre_signature)) for s in seeds]

    # 3. Pick top N ensuring ≥3 critics in top 6 (per UJ-2)
    top_critics = sorted(scored, key=lambda x: x[1], reverse=True)[:limit]

    # 4. Mark all as pre-checked=True
    return [CriticCard(seed=s, pre_checked=True, source="critic") for s, _ in top_critics]
```

Mutual-taste suggestions (4 cards) are computed separately via `seeding.compute_suggestions(user)`; they're UNCHECKED by default.

### 12.3 Analytics

Every Follow created during onboarding carries `source: onboarding_preselected | onboarding_mutual_taste | manual` so we can measure:
- % of users who keep the critic-seed defaults
- % of users who untick critic-seed defaults
- Conversion of mutual-taste suggestions

---

## 13. Moderation Flow (US-G4)

### 13.1 Report queue

User-submitted reports persist to `reports` collection in `state=open`. Each report carries `reporter_id`, `target_type` (`user` / `diary_entry` / `review` / `missing_album` — last value added by sync-fix L3-006 for catalog gap reporting), `target_id`, `reason` (enum), `detail` (free text ≤2000 chars). For `target_type=missing_album`, `target_id` is the raw search query string; `reason` is implicitly `catalog_gap` and `reporter_id` is the submitting user.

### 13.2 Daily log-scan

arq scheduled job at 03:00 UTC daily:
```python
async def daily_moderation_scan():
    # Find users with ≥3 reports in trailing 7 days
    flagged = await Report.aggregate([...]).to_list()
    for user_id, count in flagged:
        await flag_user_for_review(user_id, count)
        await notify_admin(f"User {user_id} flagged: {count} reports in 7d")
```

### 13.3 Admin review UI

Out of scope at MVP — flagged users surface in a single founder-only admin dashboard (read from Atlas directly in MongoDB Compass). Web UI is v1.x.

### 13.4 No auto-suspension

Per US-G4 acceptance criteria: no realtime auto-suspension at MVP. All actions require manual founder review. This is a deliberate trade-off — minimizes false-positives during launch when moderation patterns are unknown.

---

## 14. GDPR Pipeline

### 14.1 Data export

`POST /api/users/me/export` → enqueues an arq job:

```python
async def process_export(user_id: str, export_id: str):
    user = await User.get(user_id)
    diary = await DiaryEntry.find({"user_id": user_id}).to_list()
    reviews = await Review.find({"user_id": user_id}).to_list()
    auxes = [d for d in diary if d.auxed]
    likes_given = await ReviewLike.find({"user_id": user_id}).to_list()
    backlog = await Backlog.get_with_items(user_id)
    follows = await Follow.find_pair_for_user(user_id)
    notifications = await Notification.find({"user_id": user_id}).to_list()

    # Generate JSON + CSV
    json_blob = serialize_user_data(user, diary, reviews, auxes, likes_given, backlog, follows, notifications)
    csv_files = generate_csv_per_collection(...)

    # Email via Postmark with attachment-or-link
    await postmark.send_export(user.email, export_id, json_blob, csv_files)

    # Record in `gdpr_audit_log` collection
    await log_export(user_id, export_id, completed_at=now())
```

SLA: complete within 24h (typically <5 minutes).

### 14.2 Account deletion

`POST /api/users/me/delete` →
1. Set `user.status = "deleted"`, `user.deletion_scheduled_for = now() + 30d`.
2. Show user a banner on subsequent logins: "your account is scheduled for deletion in N days — cancel?".
3. arq cron daily: find users where `deletion_scheduled_for < now()` and process cascade hard-delete:
   - `DiaryEntry`, `Review`, `ReviewLike` (both given and received), `BacklogItem`, `Backlog`, `Follow` (both directions), `Block` (both directions), `Notification`, `SuggestedFollow`, `JustFinishedPrompt`, `MusicProvider` tokens, then User.
   - `Report` records retained (audit trail) but `reporter_id` nulled.

### 14.3 GDPR audit log

Every export + deletion request persisted to `gdpr_audit_log` collection with `user_id`, `action`, `requested_at`, `completed_at`, `notes`. Retained 7 years for compliance.

---

## 15. Observability Instrumentation

### 15.1 Sentry

- Both apps (api + web) ship Sentry SDK.
- Backend: every uncaught exception in FastAPI handlers + worker jobs.
- Frontend: every uncaught error in React boundary; source maps uploaded on deploy.
- Sample rate: 100% errors; 10% transactions at MVP.

### 15.2 PostHog (self-hosted single container)

Key product events:

| Event | Properties | Surface |
|---|---|---|
| `signup.completed` | `method` (email/spotify), `referrer` | Onboarding |
| `onboarding.spotify_connected` | `imported_count`, `top5_rated_count` | Onboarding |
| `onboarding.spotify_skipped` | — | Onboarding |
| `onboarding.completed` | `time_to_complete_ms`, `follows_count`, `critic_seed_kept_pct` | Onboarding |
| `log.commit` | `duration_ms`, `has_rating`, `has_aux`, `has_review`, `source` | Log sheet |
| `review.published` | `word_count`, `visibility` | Review write |
| `review.liked` | `reviewer_id`, `liker_id` | Like toggle |
| `feed.entry_clicked` | `position`, `source_user_id` | Home feed |
| `album.listen_on_spotify_clicked` | `source` (feed/profile/search/album_detail) | Album detail / feed |
| `backlog.added` | `source` | Up Next |
| `prompt.shown` | `album_id`, `delay_minutes` | Just-finished |
| `prompt.acted` | `action` (logged / dismissed), `delay_minutes` | Just-finished |
| `digest.sent` | `entries_count`, `digest_week` | Email |
| `follow.created` | `source` (onboarding / suggestion / profile / invite) | Various |
| `search.executed` | `query_length`, `result_count`, `via_spotify_fallback` | Search |

Funnels watched daily: signup → onboarding-complete → first-log → 7d-return → 30d-return.

### 15.3 Structured logs

Format: JSON lines; fields: `timestamp`, `level`, `module`, `event`, `user_id`, `request_id`, `provider`, `latency_ms`, `status_code`, `error`. Shipped to Fly logs; queryable via `fly logs` + Logtail integration.

### 15.4 OpenTelemetry traces

OTel SDK in backend; instruments FastAPI, httpx, Beanie automatically. Spans export to Fly logs as structured records (no dedicated tracing backend at MVP).

### 15.5 Synthetic monitoring

GitHub Actions cron every 15 minutes: `curl https://TBD.app` → assert 200 + < 500ms. Failure → ping founder via Discord webhook. Pingdom / BetterStack deferred to v1.x.

---

## 16. Testing Strategy

> Aligns with spec.md §10 (32 critical TCs + 13 E2E scenarios).

### 16.1 Pyramid

```
        ┌────────────────────────┐
        │   E2E (Playwright)     │   ~13 scenarios per spec.md §10
        └────────────────────────┘
       ┌────────────────────────────┐
       │  Integration (pytest+httpx) │   ~50+ tests
       └────────────────────────────┘
   ┌──────────────────────────────────┐
   │  Unit (pytest / Vitest+RTL)     │   ~300+ tests
   └──────────────────────────────────┘
   ┌──────────────────────────────────┐
   │  Contract (pytest)               │   ~15 tests (Spotify, MusicBrainz)
   └──────────────────────────────────┘
```

### 16.2 Test files map (from spec.md §10 critical TCs)

| Spec TC | Test file |
|---|---|
| TC-001..TC-007 (logging + Spotify integration) | `apps/api/tests/integration/test_diary_logging.py` + `test_spotify_provider.py` |
| TC-008..TC-010 (album identity + Editions) | `apps/api/tests/unit/test_album_identity.py` + `test_editions.py` |
| TC-011..TC-014 (visibility matrix) | `apps/api/tests/unit/test_visibility.py` (property test with hypothesis) |
| TC-015..TC-017 (Likes + sort) | `apps/api/tests/unit/test_review_likes.py` + `test_review_sort.py` |
| TC-018..TC-021 (just-finished prompts) | `apps/api/tests/integration/test_prompts_lifecycle.py` |
| TC-022 (disconnect immutability) | `apps/api/tests/integration/test_spotify_disconnect.py` |
| TC-023..TC-024 (handle policy) | `apps/api/tests/unit/test_handle_policy.py` |
| TC-025 (review edit) | `apps/api/tests/integration/test_review_edit.py` |
| TC-026..TC-027 (notifications + digest) | `apps/api/tests/integration/test_notification_dispatch.py` |
| TC-028 (block cascading) | `apps/api/tests/integration/test_blocks.py` |
| TC-029..TC-030 (GDPR) | `apps/api/tests/integration/test_gdpr_pipeline.py` |
| TC-031 (search) | `apps/api/tests/integration/test_search.py` |
| TC-032 (visibility matrix property) | included in `test_visibility.py` (hypothesis-based) |
| TC-E2E-001..013 | `apps/web/tests/e2e/*.spec.ts` (one file per scenario or grouped by surface) |

### 16.3 Contract tests (against Spotify sandbox / Dev Mode)

Run on PR + nightly:
- `tests/contract/test_spotify_recently_played.py`
- `tests/contract/test_spotify_album_detail.py`
- `tests/contract/test_spotify_search.py`
- `tests/contract/test_spotify_currently_playing.py`
- `tests/contract/test_musicbrainz_release_group_lookup.py`

If contract tests fail = Spotify changed their API; treat as critical.

### 16.4 CI workflow

```yaml
# .github/workflows/ci.yml — sketch
jobs:
  lint-and-test-backend:
    - ruff check + format check
    - mypy strict
    - pytest tests/unit (parallel)
    - pytest tests/integration (with mongo + redis containers)
    - pytest tests/contract (only on main or nightly)
    - upload coverage to codecov; gate at module targets (spec.md §10)

  lint-and-test-frontend:
    - biome lint + tsc strict
    - vitest run --coverage
    - playwright install + e2e (only smoke on PR; full nightly)
    - playwright + @axe-core/playwright a11y audit on built pages — gate at 0 violations (sync-fix L3-004 → NFR Accessibility, NFR Measurement Contract row "axe-core 0 violations")

  ci-status:
    needs: [lint-and-test-backend, lint-and-test-frontend]
    runs: aggregate status
```

### 16.5 Accessibility audit cadence (sync-fix L3-004)

- **Per-PR (automated):** `@axe-core/playwright` runs against built `(onboarding)`, `(app)/home`, `(app)/album/[id]`, `(app)/@[handle]`, `(app)/settings/*`, `components/log-sheet` test pages. Threshold: **0 violations**.
- **Per-release (manual):** Founder runs keyboard-only nav audit on the same screen set; result recorded in a release-readiness checklist.
- **Failing the gate:** Any axe violation blocks merge; can be waived only via a documented `// a11y-waiver:` comment with rationale + Phase 9 follow-up issue.

---

## 17. Hosting & Deployment

### 17.1 Frontend — Vercel

- Repo connected; auto-deploy on every push to a branch (preview deployments).
- Production deploys triggered by push to `main`.
- Env vars: `NEXT_PUBLIC_API_URL`, `POSTHOG_KEY`, `SENTRY_DSN`, etc.

### 17.2 Backend — Fly.io

- Single app `auxd-api` deployed via `flyctl deploy` on push to `main` (GitHub Actions).
- Region: `sjc` (US-West) at MVP; add `iad` (US-East) post-M3.
- Secrets via `fly secrets set`: `MONGODB_URI`, `REDIS_URL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SESSION_HMAC_KEY`, `TOKEN_ENCRYPTION_KEY`, `POSTMARK_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `SENTRY_DSN`, `POSTHOG_API_KEY`.
- Health check: `GET /healthz` → returns `{ "status": "ok", "db": "ok", "redis": "ok" }`.
- Worker process: arq runs in same fly app (separate process group); `fly.toml` defines `[processes]` for api + worker.

### 17.3 Domain & TLS

- Domain `TBD.app` (founder-registered pre-launch).
- Apex → Vercel; `api.TBD.app` → Fly.io.
- TLS via Vercel + Fly (Let's Encrypt automatic).

### 17.4 Database

- MongoDB Atlas Shared M0 cluster at MVP (free, sufficient for ~M3).
- Connection string in `MONGODB_URI` Fly secret.
- Backups: Atlas point-in-time (M10+); at M0 manual nightly mongodump → S3 ($1/mo).

### 17.5 Redis

- Upstash serverless Redis at MVP (free tier covers M3-ish; pay-as-you-go after).
- Used for: arq job queue, cache layer, Redis-backed rate limiter.

### 17.6 Email

- Postmark with `TBD.app` domain DKIM/SPF/DMARC configured pre-launch.
- Free tier (100 emails/mo) covers internal testing; paid tier ($15/mo for 10k emails) when public.

---

## 18. Phased Implementation Roadmap

### Phase M-2 (Closed Beta) — ~10 weeks of build

Internal-only + critic-seed onboarding wave. All work inside Spotify Development Mode (25-user quota). No public access.

**Build order:**
1. Constitution + scaffolding (Task 0–4)
2. Auth + Spotify OAuth happy-path (US-A1, US-A2)
3. Album catalog + provider abstraction (US-F1, US-F2)
4. Diary + Log sheet (US-B1, US-B2, US-B3, US-B4, US-B5)
5. Reviews + Likes + sort (US-C1, US-C2, US-C3, US-C4)
6. Backlog (US-D1, US-D2, US-D3)
7. Social graph (US-E1, US-E2, US-E3, US-E4, US-E5)
8. Auto-import + Onboarding flow (US-A3, US-A4, US-A5)
9. Just-finished detection (US-B6)
10. Notifications + preferences (US-G3, all 18 types)
11. Profile + settings + privacy (US-G1, US-G2, US-G4, US-G5)
12. GDPR pipeline
13. Internal observability dashboards + admin
14. Critic-seed roster onboarded; founder authoring first 30 reviews seeded

### Phase M-1 (Soft Launch) — ~2 weeks

- Waitlist-controlled ramp; public-access wave but invite-only.
- Real-user testing of all Must-Have stories; bug-bash.
- Spotify Extended Quota Mode approval (or delay).

### Phase M0 (Public Launch)

- Public signups open.
- Critic-seed roster live in onboarding.
- Public-tier Spotify quotas active.

### Phase M1–M3

- Iterate based on signal.
- Phase 7 (Verify Full) → Phase 8 (Test Plan / Test Run) → Phase 9 (Release Readiness) → real launch.

---

## 19. Cross-validation against Product Spec

| Check | Status | Notes |
|---|---|---|
| All 32 Must-Have stories addressed in plan? | ✅ | Each user story mapped to one or more backend modules / frontend components in §6, §7 |
| Tech stack matches research recommendations? | ✅ | Every research recommendation confirmed; no substitutions |
| All FRs (FR-001..020, FR-026..032) covered? | ✅ | FR-021..025 correctly NOT covered (Lists deferred to v2) |
| NFR Measurement Contract instrumentation specified? | ✅ | §15 maps each NFR to PostHog event / Sentry / synthetic check |
| Aux (🏅) vs Like (👍) semantic split preserved? | ✅ | Aux = DiaryEntry.auxed boolean; Like = ReviewLike collection + counter on Review |
| Provider-interface abstraction? | ✅ | §5 — `MusicProvider` protocol; all Spotify calls through it |
| Constitution gap addressed? | ✅ | §0 Task 0 ratifies with 6 principles |
| Critical Spotify dependencies surfaced? | ✅ | §0 Task 1 = Day-1 Extended Quota Mode application |
| Notification dispatcher load-bearing design? | ✅ | §8 — separate dispatcher, coalescer, rate-limit, adapters |
| Open questions from product-spec? | ✅ | All 30 spec-level questions already resolved (per spec.md §12); Phase 5 technical decisions all locked in this plan |
| Data model finalized? | ✅ | §3 — collection inventory + indexes + Beanie patterns + visibility check |
| GDPR + moderation flows? | ✅ | §14 + §13 |
| Hosting + deployment + CI/CD? | ✅ | §17 |
| Testing strategy maps to spec.md §10? | ✅ | §16 — TC mapping table |

**Result: ✅ 14/14 cross-validation checks passed.**

---

## 20. Constitution Compliance Check

> Performed against the 6 principles in §0 (forward-looking — constitution itself is Task 0).

| Principle | Status | Evidence in plan |
|---|---|---|
| 1. External-call resilience | ✅ | §5.3 — circuit breaker + retry + timeout per-provider |
| 2. Schema-versioned documents | ✅ | §3.2 — every Beanie Document carries `_schema_version: int = 1` |
| 3. Library-first modules | ✅ | §6 — each module has a single public service; cross-module via public API only |
| 4. Test-first for catalog/auth edges | ✅ | §16.3 — contract tests for Spotify + MusicBrainz; written before impl per Phase 5B task ordering |
| 5. Observability mandatory | ✅ | §15 — Sentry + PostHog + structured logs + OTel; every external call instrumented |
| 6. Provider abstraction | ✅ | §5 — `MusicProvider` interface; concrete providers isolated |

**Result: ✅ 6/6 constitution principles satisfied by design.**

---

## 21. Risks & Open Architectural Questions

| Risk / Question | Mitigation / Plan |
|---|---|
| Spotify Extended Quota Mode rejection | Closed-beta and M-1 soft launch operate inside Development Mode quotas; if rejected, scale-up plan = re-application after addressing rejection reasons, or partner-app approach |
| Atlas Search index tuning quality unknown | Spotify search fallback merges results; iterate index post-launch based on PostHog `search.executed.result_count` distribution |
| Feed performance at scale | Fan-out-on-read benchmarked at <100ms for follow-graphs <100; switch to fan-out-on-write only if p95 >200ms; load-modeling tracked weekly |
| Just-finished detection accuracy | Heuristic (≥4 tracks from same album in 1h) tuned post-launch; user can dismiss + disable to prevent false-positive damage |
| Notification firehose regression | PostHog dashboard "notification rate per user per week" with alert at threshold; rate-limit + coalescer + quiet hours layered |
| Single-region backend latency for EU/APAC | Multi-region post-M3; static OG image generation can be edge-deployed if needed earlier |
| Self-hosted PostHog operational cost | Single container on Fly.io; if it becomes flaky, migrate to PostHog Cloud (~$0/mo at our scale) |
| Cover-art proxy bandwidth cost via Spotify CDN | Lightweight pass-through; if Fly egress costs spike, move to Cloudflare Worker proxy ($0–$5/mo) |
| Reserved-squat handle false positives | Manual verification flow; conservative initial list of 200 (not 500) handles |
| MusicBrainz rate limits | 1 req/sec per IP — sufficient for our reconcile job which runs offline; we cache aggressively |

---

## 22. Handoff to Phase 5B (Tasks)

This plan is the input to **Phase 5B (tasks.md)** which decomposes the work into ordered, dependency-aware tasks. Phase 5B should:

1. Generate ~80–120 tasks covering the full scope above
2. Sequence them per the Phase M-2 build order (§18)
3. Estimate sizes (XS/S/M/L/XL per Product Forge sizing)
4. Mark dependencies between tasks
5. Front-load: Task 0 (Constitution), Task 1 (Extended Quota Mode app), Task 2 (Monorepo + scaffolding), Task 3 (CI baseline), Task 4 (Mongo + Redis connect + healthz)
6. Group by capability cluster for parallel-track potential where possible

Cross-cutting non-feature tasks Phase 5B must include:
- Task 0 — Author and ratify constitution
- Task 1 — Submit Spotify Extended Quota Mode application
- Task 2 — Monorepo scaffolding (pnpm + uv + workspaces; lint/format/typecheck/CI baseline)
- Task 3 — Atlas + Upstash Redis provisioning; Fly.io + Vercel projects
- Task 4 — Postmark + Sentry + PostHog accounts; secrets in Fly
- Task 5 — Domain + DKIM/SPF setup; web push VAPID keys generated
- (Per-module tasks follow per §6, sequenced per §18)
