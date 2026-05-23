# Plan: auxd MVP — Technical Blueprint

> **Phase 5 — Technical Plan** | Generated: 2026-05-22
> Feature slug: `001-auxd-mvp` | SpecKit mode: `classic`
>
> **Source artifacts:**
> - SpecKit Spec: [spec.md](./spec.md)
> - Product Spec: [product-spec/README.md](./product-spec/README.md)
> - Research: [research/README.md](./research/README.md)
> - Decision Log: [product-spec/decision-log.md](./product-spec/decision-log.md)

<!-- CR-001: top-of-plan decision block — all third-party listening-history integration deferred to v2 -->
> **CR-001 (2026-05-22) — Listening-history integration deferred to v2.** All third-party listening-history provider integration (the original OAuth shortcut, recently-played polling, just-finished detection, library-read prefill, and cover-art CDN proxy) is removed from the MVP. Rationale: the upstream provider's Extended Quota Mode now requires 250k MAUs to apply — structurally unreachable pre-launch. **MVP catalog backbone is MusicBrainz primary + Discogs fallback; cover art via Cover Art Archive.** Onboarding is signup → handle → follow ≥3 critics → critic-seed feed. Album logging is manual search → rate + Aux + review (Letterboxd-style). The `MusicProvider` + `CatalogProvider` Protocols are retained for forward compatibility; MVP ships one `CatalogProvider` impl per kind and no `MusicProvider` impl. All deferred surfaces remain visible in this plan under `**DEFERRED-TO-V2 (CR-001)**` labels.

---

## 0. Pre-Implementation Prerequisites (must complete before any feature work)

### Task 0 — Ratify Project Constitution

`.specify/memory/constitution.md` is currently the unfilled template. **Phase 5B Task 0** is to author the constitution with these five principles (from research/codebase-analysis.md, reviewed against this plan):

1. **External-call resilience.** Every provider/API call wraps in retry + timeout + circuit-breaker. No bare `httpx.get(...)` in feature code; all external calls go through `lib/resilience` helpers. Failures degrade gracefully with documented fallback behavior, never propagate to the user as raw 500s.

2. **Schema-versioned MongoDB documents.** Every Mongo document carries `_schema_version: int`. Readers tolerate `current_version` and `current_version − 1`; lazy-upgrade on next write. Migration code lives in `backend/migrations/{collection}_v{N}_to_v{N+1}.py`. No big-bang migrations.

3. **Library-first modules.** Backend organized as composable libraries, not god-objects. Each `backend/<module>/` exposes a single public service (`<module>.service.<verb>(...)`); internals are private. Cross-module calls go through public services, not internal helpers.

<!-- CR-001: Principle 4 — narrow test-first scope to catalog providers + email/password auth -->
4. **Test-first for catalog/auth edges.** MusicBrainz and Discogs catalog integrations and the email/password auth flow have contract tests written before implementation. Contract tests must pass before any feature using those edges merges to main.

5. **Observability mandatory.** Every external API call emits a structured log line with `provider`, `endpoint`, `latency_ms`, `status_code`, `request_id`. Every notification dispatch emits a PostHog event. Every error captured to Sentry with feature + module tags.

The constitution should also include a sixth project-specific principle:

<!-- CR-001: Principle 6 — provider abstraction language rewritten to be catalog-first, provider-vendor-neutral -->
6. **Provider abstraction.** Every catalog or music-provider integration goes through the `lib/providers/CatalogProvider` or `lib/providers/MusicProvider` Protocol; provider-specific code lives in `lib/providers/<provider>/`. Feature code never imports a vendor SDK directly. MVP ships one `CatalogProvider` impl per kind (`MusicBrainzCatalogProvider` + `DiscogsCatalogProvider`); the `MusicProvider` Protocol is defined but unimplemented at MVP. The abstraction isolates future listening-history providers and prevents repeats of past third-party endpoint deprecations.

<!-- CR-001: Task 1 (Extended Quota Mode application) removed — no listening-history provider at MVP -->
**DEFERRED-TO-V2 (CR-001):** Listening-history provider application + quota review. Original §0 Task 1 required submitting an Extended Quota Mode application to a third-party listening-history provider on Day 1 of Phase 6. CR-001 removes that integration from the MVP entirely; no provider application is required to ship. v2 candidates: Last.fm scrobble import, Apple Music MusicKit (Apple's developer programme has a different quota model and is not blocked by the same 250k MAU threshold).

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
<!-- CR-001: worker box + downstream box rewritten — no listening-history polling worker at MVP; catalog providers swapped to MusicBrainz + Discogs -->
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   arq worker (background)                                │    │
│  │   ├── digest_dispatch · suggestions_job                  │    │
│  │   ├── moderation_scan · deletion_cascade · gdpr_export  │    │
│  │   └── mbid_reconcile                                     │    │
│  │   (just-finished polling worker DEFERRED-TO-V2 / CR-001) │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────┬──────────────────┬───────────────────┬────────────────────┘
      │                  │                   │
      ▼                  ▼                   ▼
┌──────────┐      ┌──────────────┐    ┌───────────────────┐
│  Redis   │      │ MongoDB Atlas│    │  MusicBrainz +    │
│  (arq +  │      │  + Atlas     │    │  Discogs +        │
│  cache)  │      │  Search      │    │  Cover Art Archive│
│          │      │              │    │  + Resend (email) │
└──────────┘      └──────────────┘    └───────────────────┘

Observability: Sentry · PostHog Cloud · OpenTelemetry traces → Fly logs
Backups: Cloudflare R2 (10 GB free, S3-compatible)
```

### 1.1.1 Cross-cutting fail-modes (locked in Phase 5C)

The platform makes deliberate fail-mode choices for shared infrastructure:

| Dependency | If unavailable | Fail-mode | Alert |
|---|---|---|---|
| **Redis (notification rate-limit + coalescer)** | All limiting bypassed | **FAIL OPEN** — requests pass through | Sentry `rate_limit.redis_down` |
| **Redis (endpoint rate-limit)** | Per-IP / per-user write-endpoint limits bypassed | **FAIL OPEN** — same policy as notification limiter (defensive layer; missing user activity is worse than briefly unlimited writes) | Sentry `endpoint_rate_limit.redis_down` |
| **Redis (cache)** | Direct DB hits | FAIL OPEN — accept slower queries | Sentry `cache.redis_down` |
| **Redis (arq job queue)** | New jobs cannot enqueue | FAIL CLOSED — API returns 503 for endpoints that enqueue jobs (e.g., GDPR export) | Sentry `jobs.redis_down` |
<!-- CR-001: replaced listening-history provider row with MusicBrainz + Discogs catalog rows -->
| **MusicBrainz API** | 503/timeout/rate-limited | Circuit-breaker opens; cached catalog subset served from `albums`; live cache-miss lookups return "service degraded" search results | Sentry `musicbrainz.unavailable` |
| **Discogs API** | 503/timeout/rate-limited | Circuit-breaker opens; fallback path returns nothing (MusicBrainz primary already attempted); search still returns Atlas Search + MusicBrainz hits | Sentry `discogs.unavailable` |
| **Cover Art Archive** | 503/timeout/404 | Album surface renders placeholder cover; no retry storm | Sentry `caa.unavailable` (sampled, low priority) |
| **MongoDB Atlas** | Connection refused | FAIL CLOSED — 503 on all data-touching endpoints; static pages still load | Sentry `db.unavailable` (paging) |
| **Resend (email)** | Send fails | Retry with exponential backoff (3 attempts); on final failure, log to `failed_emails` collection for manual retry | Sentry `email.send_failed` |
| **PostHog** | Event dispatch fails | FAIL SILENT — events dropped; do not block user actions | Sentry `analytics.posthog_down` |
| **Sentry** | Sentry itself down | FAIL SILENT — log to stdout (captured by Fly logs) | (none — fallback log channel) |

<!-- CR-001: rationale rephrased to be provider-vendor-neutral -->
Rationale: rate-limiting is defensive (upstream catalog providers enforce their own limits at their edge — MusicBrainz at 1 req/sec, Discogs at 60 req/min authenticated; our limiter prevents misuse, but missing notifications during a Redis outage is a worse user experience than briefly unlimited notifications). Job queue and database are load-bearing and fail closed.

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
│   │   │   ├── providers/              (Catalog/MusicProvider abstraction)
│   │   │   │   ├── base.py
│   │   │   │   ├── musicbrainz/        (CR-001: primary CatalogProvider)
│   │   │   │   └── discogs/            (CR-001: fallback CatalogProvider)
│   │   │   ├── lib/                    (cross-cutting utilities)
│   │   │   │   ├── resilience.py       (retry + timeout + circuit breaker)
│   │   │   │   ├── visibility.py       (single can_read() function)
│   │   │   │   ├── observability.py    (structured logging, PostHog Cloud client)
│   │   │   │   └── markdown.py
│   │   │   ├── workers/
│   │   │   │   └── (arq job definitions)
│   │   │   └── migrations/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── contract/               (CR-001: against MusicBrainz + Discogs APIs + Cover Art Archive)
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
<!-- CR-001: FastAPI rationale rephrased — async remains essential for concurrent MusicBrainz/Discogs lookups -->
| Backend framework | **FastAPI (async only)** | Confirmed. Locked by config + research; async is essential for concurrent rate-limited catalog lookups (MusicBrainz at 1 req/sec, Discogs fallbacks). |
| Backend validation | **Pydantic v2** | Confirmed. v2's performance + JSON Schema export power the OpenAPI → TS types pipeline. |
| Backend ODM | **Beanie** | Confirmed. Async-native, Pydantic-v2-native; less boilerplate than raw PyMongo. Bench note: if Beanie ever bottlenecks on aggregation pipelines, drop to raw `motor` for that one query — Beanie supports the escape hatch. |
<!-- CR-001: backend auth narrowed to email/password — third-party OAuth deferred to v2 -->
| Backend auth | **Custom email/password** (Authlib kept on the dep list for v2 OAuth) | Custom email/password is the sole signup path at MVP. Authlib stays in the dependency manifest as a thin shim for v2 listening-history provider OAuth, but no OAuth flow ships in the MVP. Session middleware uses HMAC-signed cookies (no JWT — simpler, single-server). Handle policy (FR-029) enforced in `modules/auth/handle_service.py`. |
| Backend background jobs | **arq + Redis** | arq is FastAPI-async-native; Celery would force sync-in-async patterns. Redis serves double duty (job queue + ephemeral cache). |
<!-- CR-001: httpx rationale rephrased — sync vendor SDKs rejected for catalog providers too -->
| Backend HTTP client | **`httpx.AsyncClient`** with custom transport | Confirmed. Sync vendor SDKs (e.g., `musicbrainzngs`, `discogs-client`) rejected — they are sync-only and would require thread-pool wrapping. Direct `httpx` with custom retry + circuit-breaker transport. |
| Database | **MongoDB Atlas (Shared M0 tier at MVP)** | Confirmed. Free tier handles M3 target (~500 WAL); upgrade to M10 when WAL crosses ~3k. |
<!-- CR-001: search rationale rephrased — cold-catalog fallback is now MusicBrainz live + Discogs -->
| Search | **Atlas Search** (native to Atlas) | Confirmed. One less moving part than Meilisearch/Typesense. Cold-catalog fallback path: live MusicBrainz lookup → Discogs fallback (see §11). |
<!-- CR-001: Redis cache rationale — no OAuth state at MVP, no listening cache -->
| Cache | **Redis (Upstash serverless)** | Album metadata cache (7d TTL), arq job queue, Redis-backed rate limiter. (OAuth state cache + listening cache DEFERRED-TO-V2 / CR-001.) |
| Email | **Resend** | Transactional email + weekly digest. Free tier 3k emails/mo covers MVP. Swapped from Postmark on 2026-05-22 to stay on free tier ($15/mo saved). |
| Web push | **Standard Web Push API + VAPID keys** | No third-party push service needed at PWA stage. |
| Observability — errors | **Sentry** (free tier first) | Confirmed. |
| Observability — product analytics | **PostHog Cloud (US region, free tier)** | 1M events/mo + 1yr retention on free tier — easily covers M6 closed-beta scale. Self-host on Fly was the original plan but needs 4 GB RAM (~$40/mo); swapped 2026-05-22 to Cloud to drop MVP run-rate to $5/mo. Migrate to self-host if event volume crosses 1M/mo or compliance forces on-prem. |
| Observability — traces | **OpenTelemetry → Fly logs** at MVP | No dedicated tracing backend at MVP; Honeycomb/Tempo deferred to post-launch if needed. |
| Recommendation engine | **Heuristic only (Python, in-process)** | Confirmed. Social-graph walking + mutual-taste overlap; no ML/ALS at MVP. |
<!-- CR-001: identity model — MBID is the sole canonical key; Discogs release ID is the fallback -->
| Music identity | **MusicBrainz release-group MBID canonical; Discogs release ID fallback** | Locked. MBID is the sole canonical identity at MVP. `discogs_release_id` is a sparse-unique secondary key on `albums` for obscure pressings that MusicBrainz doesn't cover. |
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
<!-- CR-001: User.music_providers becomes an empty dict at MVP; no provider tokens persisted -->
| `users` | 5k–10k | `handle` unique sparse · `email` unique sparse · `status` partial | KSUID `_id`. `User.music_providers: dict = {}` at MVP (no provider tokens persisted — v2 may populate). No encrypted token sub-doc required at MVP. |
<!-- CR-001: `albums` indexes — `spotify_id` dropped; `discogs_release_id` added as fallback identity -->
<!-- sync-fix L3-016 (Run #5): index shape corrected post-commit-66f0403 — sparse unique caused a production E11000 when a second null insert hit the index, because Pydantic serialises None → MongoDB null (not "missing"). Replaced with partialFilterExpression which excludes both missing AND null from the unique constraint. -->
| `albums` | 50k–200k | `mbid` unique with `partialFilterExpression({mbid: {$exists: true, $ne: null}})` · `discogs_release_id` same partial-filter shape · Atlas Search index on `title + artist_credit + artists.name` with `lucene.standard` analyzer + edgeNgram autocomplete + `log1p(rating_count)` popularity boost | Lazy-cache; 7d TTL via `cache_expires_at`. MBID is the sole canonical identity; `discogs_release_id` populated only when MusicBrainz returns no match. `Album.candidate: bool` flag marks Discogs-sourced rows pending MBID reconciliation by the T065 worker. |
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
<!-- CR-001: notification type enum — `just_finished` + listening-history-provider-revoked types removed at MVP -->
| `notifications` | 100k–1M | `user_id + created_at desc` · `user_id + read_at` (sparse) · TTL 90d | Hard-delete via TTL after 90d. **CR-001:** the `just_finished` notification type and the `listening_history_provider_revoked` notification type are NOT emitted at MVP (deferred to v2 with the listening-history integration). All other notification types remain. |
| `notification_preferences` | 5k–10k (embedded on User) | — | Embedded; no separate collection |
<!-- CR-001: `just_finished_prompts` collection — kept for forward compat; not used at MVP -->
| `just_finished_prompts` | **DEFERRED-TO-V2 (CR-001)** | `user_id + state + detected_at desc` · TTL 24h on `pending` | **Status: DEFERRED-TO-V2.** Collection schema and indexes are kept in this plan so the v2 listening-history integration can land without a migration; no writers exist at MVP. |
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

# CR-001: DiaryEntrySource — only MANUAL ships at MVP; listening-history import sources deferred to v2
class DiaryEntrySource(str, Enum):
    MANUAL = "manual"
    # DEFERRED-TO-V2 (CR-001): JUST_FINISHED_PROMPT, LISTENING_HISTORY_IMPORT, LISTENING_HISTORY_PREFILL, LASTFM_IMPORT
    # Enum values kept off the wire at MVP; v2 will reintroduce as needed.

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

<!-- CR-001: single email/password signup flow; OAuth shortcut DEFERRED-TO-V2; onboarding sequence: signup → handle → follow ≥3 critics → critic-seed feed -->
**Email/password (sole MVP path):**
1. User submits email + password + handle on the signup page.
2. Validate handle against policy (FR-029, §4.3) — uniqueness, reserved-squat, format.
3. bcrypt hash password (cost 12); persist User with `password_hash`, `handle`, `status: active`, `music_providers: {}`.
4. Issue session cookie (HMAC-signed; 30-day rolling expiry).
5. Onboarding sequence: confirm handle → follow ≥3 critic-seed accounts (pre-checked cards in §12) → land on critic-seed feed.
6. First album logged via manual search (§11) + rate + Aux + optional review (Letterboxd-style).

**DEFERRED-TO-V2 (CR-001):** OAuth shortcut signup. The original Flow A used a third-party listening-history provider's OAuth + PKCE to populate `display_name` + `email` + an `external_id` and to auto-import 30 days of history. v2 will reintroduce an OAuth-based signup path once a viable listening-history provider is selected (Last.fm or Apple Music MusicKit). Until then, MVP uses email/password exclusively; this is also the Letterboxd model and matches the wedge thesis.

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

### 4.4 Listening-history provider OAuth scopes — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: §4.4 entirely replaced — no third-party OAuth ships at MVP; deferred-marker block keeps the historical decision visible for v2 -->
**DEFERRED-TO-V2 (CR-001).** This section originally locked the 5 OAuth scopes a third-party listening-history provider OAuth flow would request (email, profile, recently-played, currently-playing, library-read), including the resolution of DRIFT-L1-003 in sync-fix Run #2 that widened the scope set on 2026-05-22.

Per CR-001 (2026-05-22), all third-party listening-history provider OAuth flow is removed from the MVP. No tokens are issued, stored, refreshed, or revoked. `User.music_providers = {}` at MVP. v2 will reintroduce a provider-specific scope lock (Last.fm or Apple Music MusicKit have different scope models from the original provider and the lock will be re-derived from the v2 spec).

Preserved sync-fix history: DRIFT-L1-003 resolution (5-scope widen on 2026-05-22) is recorded in the project decision log for v2 context but does not gate any MVP code.

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

### 4.6 Settings → Integrations — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: §4.6 reduced to a deferred marker — no integrations exist at MVP, so the page ships empty (or is hidden in the nav) -->
**DEFERRED-TO-V2 (CR-001).** The original §4.6 specified Settings → Integrations as the single management surface for a third-party listening-history provider connection — including connect/disconnect CTAs, a back-fill diary trigger, and Q19's "diary intact on disconnect" guarantee. This section also carried the sync-fix Run #1 (DRIFT-L3-007) resolution and the Run #2 placement decision that kept these services in `modules/auth/` rather than a new `integrations/` module.

Per CR-001 (2026-05-22), no third-party listening-history provider integration ships at MVP. The Settings → Integrations page is therefore **empty at MVP**: either render an "Integrations coming in v2" placeholder, or hide the nav entry behind a feature flag. Either choice is acceptable; the implementing PR may pick the lower-effort path.

`disconnect_spotify`, `trigger_diary_backfill`, and the related service surface are NOT implemented at MVP. The `User.music_providers` sub-doc remains `{}` for every user, so there is nothing to disconnect.

Sync-fix Run #1 (DRIFT-L3-007 → spec.md FR-027) and Run #2 (placement lock) are preserved in the project decision log for v2 context. When v2 lands the listening-history integration, this section will be re-derived from the v2 spec and these sync-fixes re-applied.

---

## 5. Provider-Interface Abstraction (Constitution Principle 6)

<!-- CR-001: §5 rewritten — CatalogProvider is the MVP backbone; MusicProvider stays defined but has no impls at MVP -->

### 5.1 `CatalogProvider` interface (MVP) + `MusicProvider` interface (v2 forward-compat)

```python
# apps/api/src/auxd_api/providers/base.py
from typing import Protocol
from datetime import datetime

# sync-fix L3-013 (Run #4): Protocol method names + return types re-aligned to the
# actual code that landed in T041/T049/T049b. `lookup_by_mbid` → `get_album_by_mbid`,
# `lookup_by_external_id` → `get_album_by_external_id`; cover-art is a *field* on
# `CatalogAlbum` (synthesized from CAA URL convention), not a Protocol method;
# return types `AlbumRef`/`AlbumDetail`/`Listen` → `CatalogAlbum` / `ListeningEvent`.
# `provider_id` field dropped (not used by code). `get_user_library` moved out of
# MVP scope — MusicProvider stays deferred-to-v2 with a smaller surface.

class CatalogProvider(Protocol):
    """Read-only catalog metadata. MVP ships two impls (MusicBrainz + Discogs).
    No user auth required — pure server-to-server."""

    async def search_albums(self, query: str, limit: int = 10) -> list[CatalogAlbum]: ...
    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None: ...
    async def get_album_by_external_id(self, provider: str, external_id: str) -> CatalogAlbum | None: ...

class MusicProvider(Protocol):
    """User-scoped listening-history provider. DEFERRED-TO-V2 (CR-001) — Protocol defined for forward compat;
    NO concrete impls at MVP. v2 candidates: Last.fm scrobble import, Apple Music MusicKit."""

    async def get_recently_played(self, user_token: str, limit: int = 50) -> list[ListeningEvent]: ...
    async def get_currently_playing(self, user_token: str) -> ListeningEvent | None: ...
```

### 5.2 Concrete implementations (MVP)

<!-- sync-fix L3-014 (Run #4): rate-limit policy is provider-specific (Session 7 deliberate). MB pacing is in-class (asyncio.Lock + time.monotonic in MusicBrainzCatalogProvider), not via a shared `lib/resilience.rate_limit` helper (no such function exists). Discogs relies on server-side enforcement (60 req/min authenticated). -->
- `providers/musicbrainz.py:MusicBrainzCatalogProvider` — implements `CatalogProvider`. Rate-limited to **1 req/sec per IP** per MusicBrainz etiquette policy, enforced in-class via an `asyncio.Lock` + `time.monotonic()` pacing pair so the policy lives next to the only provider that needs it. Wraps `httpx.AsyncClient` with `providers/transport.py:ResilienceTransport` (T050) — composes `circuit_breaker(name="musicbrainz") + retry(attempts=3) + timeout(10s)` from `lib/resilience.py`. Primary identity source — returns release-group MBID.
<!-- sync-fix L3-014 (Run #4): Discogs token-absent path is graceful-disabled (construction succeeds, queries return empty/None) — not "unauthenticated mode". This makes the provider a true optional fallback. -->
- `providers/discogs.py:DiscogsCatalogProvider` — implements `CatalogProvider`. Fallback path for releases not in MusicBrainz (e.g., obscure pressings, bootlegs, label-specific reissues). Authenticated via `DISCOGS_API_TOKEN` (60 req/min). **Graceful-disabled when token unset**: construction succeeds, every method returns empty/None so the search service can call it unconditionally. Returns Discogs release ID — populated into `Album.discogs_release_id` only when no MBID is found.
- Cover-art is fetched via Cover Art Archive (CAA) using the MBID returned by `MusicBrainzCatalogProvider`. CAA is a sibling service to MusicBrainz, served directly from `coverartarchive.org/release-group/<mbid>/front`. No S3 cache at MVP — direct hot-link to CAA URLs is permitted by their ToS; revisit if bandwidth cost spikes.
- Feature code injects via FastAPI dependency: `def get_catalog_providers() -> list[CatalogProvider]: return [MusicBrainzCatalogProvider(...), DiscogsCatalogProvider(...)]`. The albums service iterates providers in order and short-circuits on first hit.

`MusicProvider` has no concrete impl at MVP. v2 candidates (deferred): `LastFmMusicProvider` (scrobble import), `AppleMusicMusicProvider` (MusicKit).

### 5.3 Resilience pattern

```python
# Every catalog-provider call is wrapped (per-provider circuit breaker):
async with circuit_breaker("musicbrainz"):  # or "discogs"
    async with retry(attempts=3, backoff="exponential", jitter=True):
        async with timeout(5.0):
            response = await self.client.get(...)
```

Circuit breaker per-provider (not per-endpoint) — when MusicBrainz-wide fails, fall through to Discogs fallback; when both fail, search surfaces "catalog temporarily unavailable" UI but local Atlas Search results still render.

### 5.4 Future-proofing

The interface intentionally omits audio-features, recommendations, and related-artist endpoints — those are not part of the MVP product surface, and historically third-party providers have deprecated these endpoint families without notice. Forward-compat: v2 listening-history integrations implement `MusicProvider`; switching or adding providers is a config change. Catalog-side, the `CatalogProvider` Protocol is provider-vendor-neutral — a future Apple Music catalog provider or a self-hosted catalog snapshot would slot in without feature-code changes.

---

## 6. Backend Modules — Service Layout

Each module exposes a single `<module>.service.py` with public functions; routes live in `<module>.routes.py`; schemas in `<module>.schemas.py`.

| Module | Public service surface | Notes |
|---|---|---|
<!-- CR-001: `auth` service surface narrowed — third-party OAuth + diary backfill DEFERRED-TO-V2 -->
| `auth` | `signup_with_email`, `change_handle`, `delete_account`, `request_data_export` | Handle policy + 30d immutability lock. (`signup_with_spotify`, `connect_spotify`, `disconnect_spotify`, `trigger_diary_backfill` DEFERRED-TO-V2 / CR-001.) |
<!-- CR-001: `albums` service surface — identity resolves to MBID primary + Discogs fallback (no third-party listening-history fallback) -->
| `albums` | `get_or_create`, `resolve_identity`, `aggregate_ratings`, `merge_editions` | MBID canonical / Discogs release-ID fallback resolution |
| `diary` | `log_entry`, `edit_entry`, `delete_entry`, `relist_entry`, `user_diary` | Visibility evaluated on read; write endpoint rate-limited (§4.5) |
| `reviews` | `write_review`, `edit_review` *(writes `review_edit_history` row per edit — §3.1 + FR-030)*, `like_review`, `unlike_review`, `list_reviews_for_album` | Sort: newest/most-liked/highest-rated; write/like endpoints rate-limited (§4.5) |
| `backlog` | `add_to_backlog`, `remove_from_backlog`, `reorder`, `auto_remove_on_log` | Private by default |
| `social` | `follow` *(direct or via request — §4.3)*, `unfollow`, `request_follow`, `respond_to_follow_request` *(approve/decline)*, `list_follow_requests`, `block`, `unblock`, `is_following`, `is_blocked`, `user_profile` | Asymmetric; private-profile creates pending FollowRequest (US-G2 infra, sync-fix L3-002); follow endpoint rate-limited (§4.5) |
| `feed` | `home_feed`, `friends_who_rated_for_album` | Fan-out-on-read; weighted ordering |
<!-- CR-001: `search` service surface — cold-catalog fallback is MusicBrainz live + Discogs -->
| `search` | `search_albums`, `search_users` | Atlas Search primary; cold-catalog miss → live MusicBrainz lookup → Discogs fallback (§11.1) |
| `notifications` | `dispatch`, `mark_read`, `list_user_notifications`, `update_preferences` | Dispatcher + adapters |
<!-- CR-001: `prompts` module DEFERRED-TO-V2 — no listening-history polling at MVP -->
| `prompts` | **DEFERRED-TO-V2 (CR-001)** | Just-finished detection (`poll_user_for_just_finished`, `dismiss_prompt`, `disable_for_user`) ships with the v2 listening-history integration. Module folder may exist as a stub at MVP for the JustFinishedPrompt collection schema, but no service code or routes are wired in. |
| `seeding` | `get_critic_seeds_for_onboarding`, `record_card_response`, `compute_suggestions` | Pre-checked card ordering |
| `moderation` | `submit_report`, `daily_scan_for_flagged_users`, `action_report` | Daily cron |
| `data_export` | `enqueue_export`, `process_export`, `mail_export` | GDPR pipeline |
<!-- CR-001: providers/spotify row dropped; providers/musicbrainz + providers/discogs rows added -->
<!-- sync-fix L3-013 (Run #4): method names re-aligned to actual T041 Protocol shape. cover-art URL is a *field* on CatalogAlbum (synthesized from CAA convention), not a Protocol method. -->
| `providers/musicbrainz` | `search_albums`, `get_album_by_mbid`, `get_album_by_external_id` | Primary `CatalogProvider`. Rate-limited 1 req/sec per IP via in-class asyncio.Lock + monotonic (MusicBrainz policy). Cover art URL synthesized as CAA sibling-service path `coverartarchive.org/release-group/{mbid}/front` — populated into `CatalogAlbum.cover_art_url` field. |
| `providers/discogs` | `search_albums`, `get_album_by_mbid` (returns None — Discogs is not MBID-canonical), `get_album_by_external_id` | Fallback `CatalogProvider` for releases not in MusicBrainz. Authenticated via `DISCOGS_API_TOKEN`; graceful-disabled when token unset. |

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

### 7.5 Just-finished prompt — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: just-finished prompt frontend component DEFERRED — no detection signal exists at MVP without the listening-history provider -->
**DEFERRED-TO-V2 (CR-001).** The `components/just-finished-prompt/` component was designed to render at the top of `/` (home feed) when a `JustFinishedPrompt` was in `pending` state for the user, with 60s TanStack Query polling, an overflow "Disable auto-prompts" toggle, and a per-album "Don't prompt for this album" dismiss with 30d stickiness. The component is removed from the MVP component tree (the directory may exist as an empty stub for §1.2 file-tree alignment) because the detection signal that fed it (recently-played + currently-playing polling from a third-party listening-history provider) is itself deferred. When v2 reintroduces detection, this component returns unchanged.

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
│   ├─ EmailAdapter (Resend)   │
│   └─ WebPushAdapter (VAPID)  │
└─────────────────────────────┘
```

### 8.2 Coalescer + rate limiter (locked in Phase 5C)

- **Per-user rate limit (per-type, independent):** ≤5 in-app/hour, ≤25/day. Each notification type has its own counter; e.g., follow notifications and review-like notifications consume separate buckets. Excess events queue into a single coalesced "X new updates today" notification.
- **Per-actor rate limit (CROSS-TYPE):** notifications from User X to User Y are coalesced if >3 happen in the trailing 24h. This is INTENTIONALLY cross-type — if X follows Y, then likes 3 of Y's reviews in the same hour, the first 3 events fire individually and subsequent events from X collapse into "X did several things on your reviews today". Resolves A-003 from pre-impl-review.
- **Per-event dedup:** same event-type + same actor + same target within 1h → drop the second.
<!-- CR-001: rationale generalized — defensive layer no longer references a third-party listening-history provider -->
- **Fail-mode (locked in Phase 5C — resolves A-004):** If Redis is unreachable, the rate-limiter and coalescer FAIL OPEN — notifications dispatch through without limiting, and a Sentry alert fires with tag `notif_limiter.redis_down`. Email and web-push delivery providers enforce their own limits at their edge (Resend rate limits, VAPID server checks); our limiter is defensive.
- Implementation: Redis sorted-sets keyed by `notif:{user_id}:rate:{type}:{window}` (per-type) and `notif:{actor_id}:{recipient_id}:cross_type:{window}` (cross-type per-actor); TTL'd per-window.

### 8.3 Adapters

- `InAppAdapter`: writes to `notifications` collection; counts toward rate limit.
- `EmailAdapter`: sends via Resend (Python SDK `resend`); transactional emails ignore quiet hours; weekly digest fires Monday 09:00 user-local.
- `WebPushAdapter`: VAPID-signed payloads; respects quiet hours (suppresses push within window); coalesces if multiple events fire close together.

### 8.4 Weekly digest job

- Scheduled via arq cron: every 5 minutes the worker checks for users whose `Monday 09:00 user-local` is in the current 5-minute window; per-user-tz awareness.
- For each eligible user: query top 10 entries from their follow graph past 7 days + 1 "most-rated album in your follow graph this week" hero.
- Render plain HTML email; send via Resend; emit PostHog event `digest.sent`.
- Suppression: `weekly_digest` channel must be ON in `NotificationPreferences`.

---

## 9. Just-finished Detection (FR-026) — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: entire §9 deferred — no listening-history polling source exists at MVP -->
**DEFERRED-TO-V2 (CR-001).** The full just-finished detection cluster ships with the v2 listening-history integration. This includes:

- **§9.1 Polling strategy** — cadence (5 min active / 15 min dormant / 60 min cap, stop after 14d idle) and the `workers/spotify_poll.py` arq job that read `MusicProvider.get_recently_played(user, since=last_poll)` and aggregated "completed album" events via the ≥4-distinct-tracks-in-1h heuristic.
- **§9.2 Prompt lifecycle** — the `pending → logged | dismissed | expired | superseded` state machine on `JustFinishedPrompt`, one-pending-per-user constraint, `auto_prompt_enabled` gate, and quiet-hours interaction.

The `JustFinishedPrompt` collection schema remains in §3.1 for forward compat (so v2 lands without a migration), but no writers exist at MVP. FR-026 traceability: at MVP, FR-026 is not implemented; v2 spec must re-anchor against the chosen listening-history provider's capabilities.

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

<!-- CR-001: feed weighting is 100% social-graph based at MVP — no listening-history signal exists -->
### 10.2 Weighting math (locked in Phase 5C; CR-001 confirms social-graph-only)

The MVP feed weighting is **100% social-graph based**. There is no listening-history signal (which would have come from the deferred third-party listening-history provider) feeding into the score. All inputs are derived from in-app interactions: review/Aux behaviour, ratings, and the precomputed top-5-interacted-users set. v2 may add a listening-history signal as an additive bonus once a provider integration ships.

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

<!-- sync-fix L7-015 (Run #5): added markdown link to the migrations runbook so the operator-facing apply path is discoverable from the plan. -->

The canonical index definition lives at [`apps/api/migrations/atlas_search/albums_index.json`](../../apps/api/migrations/atlas_search/albums_index.json). The operator runbook for applying it (Atlas UI or `atlas-cli` paths) is at [`apps/api/migrations/README.md`](../../apps/api/migrations/README.md). The JSON below is the indicative shape that ships in code as of the §6 wave — refer to the linked file for the live source of truth.

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

<!-- CR-001: §11.2 — Atlas Search primary; cold-catalog miss → live MusicBrainz lookup → Discogs fallback -->
### 11.2 Cold-catalog fallback (MusicBrainz live + Discogs)

When Atlas Search returns <5 results — i.e., the cached MusicBrainz subset hasn't seen this query yet — the search service falls through to two upstream catalogs in order:

1. **Live MusicBrainz lookup.** Query `https://musicbrainz.org/ws/2/release-group?query=...&fmt=json` via `MusicBrainzCatalogProvider.search_albums`. Subject to 1 req/sec per IP — the search service enforces this with a Redis-backed token bucket. Hits are lazy-cached into the `albums` collection (7d TTL via `cache_expires_at`); subsequent identical queries hit Atlas Search directly.
2. **Discogs fallback.** If MusicBrainz returns no useful match (e.g., obscure pressings, bootlegs, label-specific reissues), query Discogs via `DiscogsCatalogProvider.search_albums`. Discogs results are lazy-cached into `albums` with `discogs_release_id` populated and `mbid = null`. A nightly `mbid_reconcile` worker (already on the worker list — §1.1 / §8) attempts to back-fill an MBID for Discogs-only entries as MusicBrainz coverage grows.

Merged result ordering: Atlas Search score first, live MusicBrainz hits next, Discogs hits last. The frontend shows the first 10 in one list; "load more" extends the merge order. This is the Letterboxd-equivalent search path: a manual search → manual select → manual log workflow.

<!-- CR-001: §11.2.1 — report missing album is now MORE important; only path to surface catalog gaps -->
### 11.2.1 Report missing album (sync-fix L3-006 → spec.md FR-005 / US-F2 — elevated by CR-001)

<!-- sync-fix L3-015 (Run #5): URL aligned to the surface used by both code (modules/search/routes.py _REPORT_MISSING_ALBUM_URL constant) and tasks.md T053a — the future "Report missing album" endpoint lives under /api/v1/reports/missing-album, not /api/search/report-missing. -->
When all three search paths (Atlas Search, MusicBrainz live, Discogs) return zero results for a query, the empty-state UI shows a "Report missing album" link. Tapping submits a `POST /api/v1/reports/missing-album` request that creates a `reports` document with `target_type: 'missing_album'`, `target_id: query_string`, and submitter user id. Surfaces in the founder admin queue (Compass at MVP per §13.3); founder may add the album manually (insert into `albums` with a curated MBID or `discogs_release_id`) or extend Atlas Search ranking. No automated resolution at MVP.

**CR-001 elevation:** Now that manual search is the only album-discovery path (no listening-history prefill), the "Report missing album" affordance is the sole user-facing safety valve for catalog gaps. The founder admin queue should be reviewed at least weekly during M-2/M-1 — every unresolved missing-album report is a logged user who could not log their album.

### 11.3 User search

Out of scope at MVP. Users find each other via:
- Follow graph (suggestions)
- Profile URL share (`xiejoshua.com/@handle`)
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

    # Email via Resend with attachment-or-link
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

### 15.2 PostHog Cloud (US region, free tier)

- Host: `https://us.i.posthog.com` (ingest) / `https://us.posthog.com` (dashboard).
- Free tier: 1M events/mo, 1yr retention — easily covers M6 closed-beta scale.
- Self-host on Fly was the original plan (single container on Fly.io); swapped 2026-05-22 because PostHog's 4 GB RAM minimum (~$40/mo) blew through the MVP cost budget. Migration path: re-host on self-managed infra when event volume crosses ~1M/mo OR when compliance forces on-prem (neither is true at MVP).
- Server SDK: `posthog` Python package (already in `apps/api/pyproject.toml`).
- Wrapper: `auxd_api.lib.observability.emit_event(...)` — fire-and-forget, no-op when `POSTHOG_API_KEY` is unset, never raises into request path.

Key product events:

| Event | Properties | Surface |
|---|---|---|
<!-- CR-001: signup.completed loses the OAuth method value; spotify-import + listen-on events removed; prompt events DEFERRED; search.executed swaps fallback flag -->
| `signup.completed` | `method` (always `email` at MVP — `oauth_listening_history` DEFERRED-TO-V2), `referrer` | Onboarding |
| `onboarding.completed` | `time_to_complete_ms`, `follows_count`, `critic_seed_kept_pct` | Onboarding |
| `log.commit` | `duration_ms`, `has_rating`, `has_aux`, `has_review`, `source` | Log sheet |
| `review.published` | `word_count`, `visibility` | Review write |
| `review.liked` | `reviewer_id`, `liker_id` | Like toggle |
| `feed.entry_clicked` | `position`, `source_user_id` | Home feed |
| `backlog.added` | `source` | Up Next |
| `digest.sent` | `entries_count`, `digest_week` | Email |
| `follow.created` | `source` (onboarding / suggestion / profile / invite) | Various |
| `search.executed` | `query_length`, `result_count`, `via_musicbrainz_fallback`, `via_discogs_fallback` | Search |
| `search.album_reported_missing` | `query`, `submitter_id` | Search (CR-001 elevated — track catalog-gap rate) |

**DEFERRED-TO-V2 (CR-001) events** (kept here for v2 reactivation): `onboarding.listening_history_connected` (imported_count, top5_rated_count), `onboarding.listening_history_skipped`, `album.listen_on_external_provider_clicked` (source), `prompt.shown` (album_id, delay_minutes), `prompt.acted` (action, delay_minutes).

Funnels watched daily: signup → onboarding-complete → first-log → 7d-return → 30d-return.

<!-- CR-001: catalog-provider observability metrics — replaces the listening-history-provider metrics from the previous plan version -->
### 15.2.1 Catalog-provider metrics (CR-001)

Tracked via structured logs (§15.3) and surfaced in a PostHog insight; reviewed weekly during M-2/M-1:

| Metric | Definition | Target |
|---|---|---|
| MusicBrainz catalog hit rate | Atlas-Search-hit-count / (Atlas-Search-hit-count + MusicBrainz-live-lookup-count) | ≥70% after first week of beta (Atlas Search cache warming up) |
| MusicBrainz API latency p95 | `latency_ms` for `provider=musicbrainz`, p95 over 24h trailing | <800ms |
| Discogs fallback rate | Discogs-live-lookup-count / total-search-executed | <5% (high values indicate MusicBrainz coverage gaps worth investigating) |
| Cover Art Archive 404 rate | CAA `status_code=404` / total CAA fetches | <10% (high values indicate cold catalog or unmatched MBIDs) |
| Missing-album report rate | `search.album_reported_missing` events per 100 `search.executed` events | <2% (high values indicate catalog gaps or query-quality issues) |

DEFERRED-TO-V2 (CR-001): listening-history-provider import p99 + listening-history-provider API error rate — re-introduce with the v2 integration.

### 15.3 Structured logs

Format: JSON lines; fields: `timestamp`, `level`, `module`, `event`, `user_id`, `request_id`, `provider`, `latency_ms`, `status_code`, `error`. Shipped to Fly logs; queryable via `fly logs` + Logtail integration.

### 15.4 OpenTelemetry traces

OTel SDK in backend; instruments FastAPI, httpx, Beanie automatically. Spans export to Fly logs as structured records (no dedicated tracing backend at MVP).

### 15.5 Synthetic monitoring

GitHub Actions cron every 15 minutes: `curl https://xiejoshua.com` → assert 200 + < 500ms. Failure → ping founder via Discord webhook. Pingdom / BetterStack deferred to v1.x.

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
<!-- CR-001: contract test scope swap — MusicBrainz + Discogs + Cover Art Archive -->
   ┌──────────────────────────────────┐
   │  Contract (pytest)               │   ~10 tests (MusicBrainz, Discogs, CAA)
   └──────────────────────────────────┘
```

### 16.2 Test files map (from spec.md §10 critical TCs)

| Spec TC | Test file |
|---|---|
<!-- CR-001: TC-001..TC-007 scope narrowed — provider integration tests swap to catalog providers -->
| TC-001..TC-007 (logging + catalog providers) | `apps/api/tests/integration/test_diary_logging.py` + `test_musicbrainz_provider.py` + `test_discogs_provider.py` |
| TC-008..TC-010 (album identity + Editions) | `apps/api/tests/unit/test_album_identity.py` + `test_editions.py` |
| TC-011..TC-014 (visibility matrix) | `apps/api/tests/unit/test_visibility.py` (property test with hypothesis) |
| TC-015..TC-017 (Likes + sort) | `apps/api/tests/unit/test_review_likes.py` + `test_review_sort.py` |
<!-- CR-001: just-finished prompt TCs DEFERRED-TO-V2 -->
| TC-018..TC-021 (just-finished prompts) | **DEFERRED-TO-V2 (CR-001)** — `test_prompts_lifecycle.py` not built at MVP; v2 reintroduces with the listening-history integration |
<!-- CR-001: disconnect-immutability TC DEFERRED-TO-V2 — no provider to disconnect at MVP -->
| TC-022 (disconnect immutability) | **DEFERRED-TO-V2 (CR-001)** — no listening-history provider integration at MVP, so disconnect immutability isn't testable; v2 reintroduces as `test_listening_history_disconnect.py` |
| TC-023..TC-024 (handle policy) | `apps/api/tests/unit/test_handle_policy.py` |
| TC-025 (review edit) | `apps/api/tests/integration/test_review_edit.py` |
| TC-026..TC-027 (notifications + digest) | `apps/api/tests/integration/test_notification_dispatch.py` |
| TC-028 (block cascading) | `apps/api/tests/integration/test_blocks.py` |
| TC-029..TC-030 (GDPR) | `apps/api/tests/integration/test_gdpr_pipeline.py` |
| TC-031 (search) | `apps/api/tests/integration/test_search.py` |
| TC-032 (visibility matrix property) | included in `test_visibility.py` (hypothesis-based) |
| TC-E2E-001..013 | `apps/web/tests/e2e/*.spec.ts` (one file per scenario or grouped by surface) |

<!-- CR-001: contract test list rewritten — catalog providers only at MVP -->
### 16.3 Contract tests (against MusicBrainz + Discogs + Cover Art Archive)

Run on PR + nightly:
- `tests/contract/test_musicbrainz_release_group_lookup.py` — MBID-by-lookup and release-group search.
- `tests/contract/test_musicbrainz_search.py` — query-string search returns release groups.
- `tests/contract/test_discogs_search.py` — search with `DISCOGS_API_TOKEN`.
- `tests/contract/test_discogs_release_lookup.py` — release-id direct lookup.
- `tests/contract/test_cover_art_archive_front.py` — `release-group/<mbid>/front` returns 200 with image bytes.

If contract tests fail = an upstream catalog provider changed their API; treat as critical and route to the founder triage queue.

**DEFERRED-TO-V2 (CR-001):** `test_spotify_recently_played.py`, `test_spotify_album_detail.py`, `test_spotify_search.py`, `test_spotify_currently_playing.py` (originally part of this list). These return with the v2 listening-history integration, retargeted at whichever provider v2 selects.

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
- Region: `iad` (US-East, Ashburn VA) at MVP to colocate with Atlas + Upstash (both `us-east-1`); add a second region post-M3 if cross-region latency demands.
- Plan: Hobby ($5/mo minimum; first $5 of compute included). Two-process layout (api + arq worker) on a single shared-cpu-1x VM stays inside the included allowance.
<!-- CR-001: Fly secrets list — SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET / SPOTIFY_INTEGRATION_ENABLED removed; DISCOGS_API_TOKEN added; TOKEN_ENCRYPTION_KEY retained for v2 but unused at MVP -->
- Secrets via `fly secrets set`: `MONGODB_URI`, `REDIS_URL`, `DISCOGS_API_TOKEN` (optional, server-side only), `SESSION_HMAC_KEY`, `TOKEN_ENCRYPTION_KEY` (provisioned for v2 listening-history token encryption; unused at MVP), `RESEND_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `SENTRY_DSN`, `POSTHOG_API_KEY`, `POSTHOG_HOST`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`. See `docs/infra.md` for the full source-of-truth table. **DEFERRED-TO-V2 (CR-001):** `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_INTEGRATION_ENABLED` (removed from this list — re-add when v2 selects a listening-history provider; the env-var names should be re-derived per the v2 provider).
- Health check: `GET /healthz` → returns `{ "status": "ok", "db": "ok", "redis": "ok" }`.
- Worker process: arq runs in same fly app (separate process group); `fly.toml` defines `[processes]` for api + worker.

### 17.3 Domain & TLS

- Domain `xiejoshua.com` (temporary, founder-registered via Cloudflare 2026-05-22; final product domain TBD).
- Apex → Vercel; `api.xiejoshua.com` → Fly.io.
- DNS hosted at Cloudflare (proxy OFF on Vercel + Fly records — both providers manage their own SSL via Let's Encrypt).
- When the final product domain is decided, re-point DNS records — code uses `NEXT_PUBLIC_API_URL` env var, so the swap is config-only.

### 17.4 Database

- MongoDB Atlas Shared M0 cluster at MVP (free, 512 MB storage, sufficient for ~M3 closed-beta).
- Region `aws-us-east-1` (matches Fly `iad` for sub-10ms backend ↔ DB latency).
- Connection string in `MONGODB_URI` Fly secret.
- Backups: Atlas point-in-time available at M10+ tier; at M0 we run a manual nightly `mongodump --gzip --archive` → **Cloudflare R2 bucket `auxd-backups`** via S3-compatible API (10 GB free tier; ~$0/mo at MVP scale — swapped from S3 on 2026-05-22 to stay free). Lifecycle: retain 30 days, expire after. See T010a for the GitHub Actions workflow + restore drill.

### 17.5 Redis

- Upstash serverless Redis at MVP (free tier: 256 MB, 10k commands/day — covers M3-ish closed-beta).
- Region `us-east-1` (colocated with Atlas + Fly).
- Used for: arq job queue, cache layer, Redis-backed rate limiter.

### 17.6 Email

- **Resend** (resend.com) with `xiejoshua.com` domain DKIM/SPF/DMARC configured pre-launch. Swapped from Postmark on 2026-05-22 to stay on a free tier.
- Free tier: 3,000 emails/mo — covers M3 closed-beta with significant headroom. Upgrade to Pro ($20/mo for 50k emails) around 500 active users.
- Server SDK: `resend` Python package (added in T135 implementation).

---

## 18. Phased Implementation Roadmap

### Phase M-2 (Closed Beta) — ~8 weeks of build (CR-001: ~2 weeks shorter; OAuth + polling + just-finished cluster removed)

<!-- CR-001: build order rewritten — no third-party OAuth, no auto-import, no just-finished detection at MVP -->
Internal-only + critic-seed onboarding wave. No third-party listening-history provider quota gating. No public access.

**Build order:**
1. Constitution + scaffolding (Task 0–4)
2. Auth (email/password) + handle policy + session middleware (US-A1, US-A2)
3. Album catalog + `CatalogProvider` abstraction (MusicBrainz + Discogs + Cover Art Archive) (US-F1, US-F2)
4. Diary + Log sheet — manual search → rate + Aux + review (US-B1, US-B2, US-B3, US-B4, US-B5)
5. Reviews + Likes + sort (US-C1, US-C2, US-C3, US-C4)
6. Backlog (US-D1, US-D2, US-D3)
7. Social graph (US-E1, US-E2, US-E3, US-E4, US-E5)
8. Onboarding flow — signup → handle → follow ≥3 critics → critic-seed feed (US-A4, US-A5)
9. Notifications + preferences (US-G3, all 18 types minus the two CR-001-deferred types)
10. Profile + settings + privacy (US-G1, US-G2, US-G4, US-G5) — Settings → Integrations renders an "Integrations coming in v2" placeholder per §4.6
11. GDPR pipeline
12. Internal observability dashboards + admin
13. Critic-seed roster onboarded; founder authoring first 30 reviews seeded

**DEFERRED-TO-V2 (CR-001):** Step 8 of the original plan (Auto-import + listening-history OAuth-shortcut Onboarding flow, US-A3) and Step 9 (Just-finished detection, US-B6) — both ship with the v2 listening-history integration.

### Phase M-1 (Soft Launch) — ~2 weeks

- Waitlist-controlled ramp; public-access wave but invite-only.
- Real-user testing of all Must-Have stories; bug-bash.
- (CR-001: no third-party listening-history provider quota gate at this phase.)

### Phase M0 (Public Launch)

- Public signups open.
- Critic-seed roster live in onboarding.
- (CR-001: no listening-history-provider production-tier quota dependency at launch.)

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
<!-- CR-001: provider abstraction row + Spotify-dependency row updated -->
| Provider-interface abstraction? | ✅ | §5 — `CatalogProvider` Protocol (MusicBrainz + Discogs impls at MVP); `MusicProvider` Protocol defined for v2 |
| Constitution gap addressed? | ✅ | §0 Task 0 ratifies with 6 principles |
| Critical third-party listening-history dependencies surfaced? | n/a (CR-001) | **DEFERRED-TO-V2 (CR-001):** no listening-history provider at MVP; original §0 Task 1 (Day-1 Extended Quota Mode application) removed per CR-001 (2026-05-22). |
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
<!-- CR-001: Principle 4 evidence — contract tests now cover MusicBrainz + Discogs + Cover Art Archive -->
| 4. Test-first for catalog/auth edges | ✅ | §16.3 — contract tests for MusicBrainz + Discogs + Cover Art Archive + email/password auth; written before impl per Phase 5B task ordering |
| 5. Observability mandatory | ✅ | §15 — Sentry + PostHog + structured logs + OTel; every external call instrumented |
| 6. Provider abstraction | ✅ | §5 — `MusicProvider` interface; concrete providers isolated |

**Result: ✅ 6/6 constitution principles satisfied by design.**

---

## 21. Risks & Open Architectural Questions

| Risk / Question | Mitigation / Plan |
|---|---|
<!-- CR-001: original Spotify-quota risk DEFERRED-TO-V2; new risks added for catalog coverage + manual-search dropoff -->
| Listening-history provider quota / availability (DEFERRED-TO-V2 / CR-001) | N/A at MVP — no provider integration ships. Risk re-appears when v2 selects a provider; mitigation will be derived from the v2 spec. |
| MusicBrainz catalog coverage gaps | Discogs fallback path absorbs most obscure pressings; "report missing album" surface (§11.2.1, elevated by CR-001) captures the residual; founder reviews queue weekly |
| Manual-search-only logging dropoff vs. OAuth-prefill MVP | Letterboxd evidence shows manual search is workable; instrument `log.commit.duration_ms` and `search.executed.result_count` distributions; if median time-to-first-log >3 minutes, prioritise UX improvements (recent-searches suggestions, top-rated-this-week chips) before considering an emergency v2-listening-history pull-forward |
| Atlas Search index tuning quality unknown | Live MusicBrainz + Discogs fallback paths absorb cold-catalog misses; iterate index post-launch based on PostHog `search.executed.result_count` + `search.executed.via_musicbrainz_fallback` + `search.executed.via_discogs_fallback` distributions |
| Feed performance at scale | Fan-out-on-read benchmarked at <100ms for follow-graphs <100; switch to fan-out-on-write only if p95 >200ms; load-modeling tracked weekly |
<!-- CR-001: just-finished detection accuracy risk DEFERRED-TO-V2 -->
| Just-finished detection accuracy (DEFERRED-TO-V2 / CR-001) | N/A at MVP — detection cluster deferred. Heuristic (≥4 tracks from same album in 1h) returns with v2 listening-history integration. |
| Notification firehose regression | PostHog dashboard "notification rate per user per week" with alert at threshold; rate-limit + coalescer + quiet hours layered |
| Single-region backend latency for EU/APAC | Multi-region post-M3; static OG image generation can be edge-deployed if needed earlier |
| PostHog Cloud free-tier event budget (1M/mo) | Monitor monthly event count via PostHog billing UI; if approaching ceiling, drop low-value events first (feed scroll telemetry before commit events); paid tier scales linearly at ~$0.0003/event |
<!-- CR-001: cover-art via Cover Art Archive — direct hot-link, no S3 cache at MVP -->
| Cover-art bandwidth + CAA hot-link permissibility | Cover Art Archive serves cover art directly from `coverartarchive.org/release-group/<mbid>/front`. Their ToS permits hot-linking (it is a public archive). No S3 cache at MVP. If CAA throttles us or bandwidth becomes a frontend perf concern, fall back to Cloudflare Worker proxy ($0–$5/mo). |
| Reserved-squat handle false positives | Manual verification flow; conservative initial list of 200 (not 500) handles |
| MusicBrainz rate limits | 1 req/sec per IP — sufficient for our reconcile job which runs offline; we cache aggressively |

---

## 22. Handoff to Phase 5B (Tasks)

This plan is the input to **Phase 5B (tasks.md)** which decomposes the work into ordered, dependency-aware tasks. Phase 5B should:

1. Generate ~80–120 tasks covering the full scope above
2. Sequence them per the Phase M-2 build order (§18)
3. Estimate sizes (XS/S/M/L/XL per Product Forge sizing)
4. Mark dependencies between tasks
<!-- CR-001: handoff task list — Extended Quota Mode application removed; Discogs API token provisioning added -->
5. Front-load: Task 0 (Constitution), Task 1 (Monorepo + scaffolding), Task 2 (CI baseline), Task 3 (Mongo + Redis + Discogs token provisioning + healthz)
6. Group by capability cluster for parallel-track potential where possible

Cross-cutting non-feature tasks Phase 5B must include:
- Task 0 — Author and ratify constitution
- Task 1 — Monorepo scaffolding (pnpm + uv + workspaces; lint/format/typecheck/CI baseline)
- Task 2 — Atlas + Upstash Redis provisioning; Fly.io + Vercel projects
- Task 3 — Resend + Sentry + PostHog Cloud + Cloudflare R2 accounts; **Discogs API token (CR-001)**; secrets in Fly (full list in docs/infra.md)
- Task 4 — Domain + DKIM/SPF setup; web push VAPID keys generated
- (Per-module tasks follow per §6, sequenced per §18)

**DEFERRED-TO-V2 (CR-001):** "Task 1 — Submit Extended Quota Mode application to a third-party listening-history provider" (original Phase 5B Day-1 task) is removed; reintroduce when v2 selects a provider.
