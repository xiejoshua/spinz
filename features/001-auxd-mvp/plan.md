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

<!-- sync-fix L3-040 (Run #11): migration path + filename pattern updated to match shipped runner (T030, Session 22). -->
2. **Schema-versioned MongoDB documents.** Every Mongo document carries `_schema_version: int`. Readers tolerate `current_version` and `current_version − 1`; lazy-upgrade on next write. Migration code lives in `apps/api/src/auxd_api/migrations/00N_<name>.py`. Filename-ordered numeric prefix; runner skips already-applied (by `_schema_version` threshold); fail-loud on apply error (re-raises so a botched migration cannot serve traffic). No big-bang migrations.

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
│       │   │   ├── profile/[handle]/   (profile — public URL `/@handle` reaches here via middleware rewrite; see §7.1)
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
| `reviews` | 10k–100k | `user_id + created_at desc` · `album_id + reactions.likes_count desc` (R3 Most-Liked sort) · `diary_entry_id` unique · `deleted_at sparse` (T087 soft-delete cron sweep; sync-fix L3-022, Run #9) | 1:1 optional with DiaryEntry. Soft-delete via `deleted_at` with 30d grace before hard-delete cascades `ReviewLike` rows (parallels diary_entries soft-delete). |
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
<!-- sync-fix L3-033 (Run #11): push_subscriptions added — shipped Session 20 (T136 WebPush adapter). -->
| `push_subscriptions` | 5k–20k | `user_id` · `endpoint` unique · `last_used_at` | Per-device VAPID; 410-Gone DELETE on dead send (web_push adapter cleanup). |
<!-- CR-001: `just_finished_prompts` collection — kept for forward compat; not used at MVP -->
| `just_finished_prompts` | **DEFERRED-TO-V2 (CR-001)** | `user_id + state + detected_at desc` · TTL 24h on `pending` | **Status: DEFERRED-TO-V2.** Collection schema and indexes are kept in this plan so the v2 listening-history integration can land without a migration; no writers exist at MVP. |
<!-- sync-fix L3-025 (Run #10): SuggestedFollow → Suggestion + separate SuggestionDismissal — Session 17 T104 shipped two collections with TTL semantics that differ (Suggestions 7d, Dismissals 30d). -->
| `suggestions` | 10k–100k | `(user_id, score desc)` · `(user_id, suggested_user_id)` unique · `computed_at` TTL 7d | Precomputed by T104 arq worker; refreshed N hours per user |
| `suggestion_dismissals` | 10k–100k | `(user_id, suggested_user_id)` unique · `dismissed_at` TTL 30d | Separate collection so dismissal TTL (30d cool-down) ≠ suggestion staleness (7d). Read endpoint joins for defense-in-depth filtering. |
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
| `POST /reviews` | 20 | 40 | Anti-spam writes |
| `POST /reviews/{id}/like` | 120 | 240 | Idempotent toggle; generous to allow rapid feed scroll |
<!-- sync-fix L3-028 (Run #10): Session 17 rate-limits added; old `POST /follow` 30/60 row corrected to shipped social_write 60/min (the table previously listed the planned-but-not-shipped limit). -->
| `POST/DELETE /users/{handle}/follow`, `POST/DELETE /users/{handle}/block` (shared `social_write` bucket) | 60 | 120 | Shipped at Session 17 T101+T102 |
| `GET /users/me/blocks`, `GET /users/me/suggestions`, `POST /suggestions/{id}/dismiss` (shared `social_read` bucket) | 60 | 120 | Read-side ceiling — block list + suggestions list are settings-surface, low frequency |
| `GET /albums/{id}/friends` (`friends_read`) | 120 | 240 | Album-detail rollup surface; high frequency |
| `GET /feed?mode=for_you\|latest` (`home_feed_read`) | 180 | 360 | Home feed is the hot path — generous ceiling for infinite-scroll |
| `GET /api/v1/users/{handle}` (`profile_read`) | 120 | 240 | Profile-page reads; default ceiling matches album-detail |
<!-- sync-fix L3-038 (Run #11): 7 new rows for Sessions 19-22 endpoints (notifications inbox + bell badge + prefs + push subs + onboarding cards + reviews-only sub-route). -->
| `GET /api/v1/notifications/unread-count` | 120 | 240 | Badge poll; cheapest endpoint |
| `POST /api/v1/notifications/mark-all-read` | 10 | 20 | Bulk action |
| `PUT /api/v1/users/me/notification-preferences` | 10 | 20 | Writes prefs subdoc + quiet-hours fields |
| `POST /api/v1/users/me/push-subscriptions` | 10 | 20 | Idempotent re-POST updates `last_used_at` |
| `GET /api/v1/onboarding/cards` | 30 | 60 | Inline critic-seed card ordering |
| `GET /api/v1/notifications` | 60 | 120 | Inbox list pagination |
| `GET /api/v1/users/{handle}/reviews` | 60 | 120 | T094 reviews view (`/profile/{handle}?view=reviews`) |
<!-- sync-fix L3-045 (Run #12): 8 new rows for Sessions 23-25 endpoints (PATCH /me + avatar + privacy + email + password + follow-requests + reports + data-export). -->
| `PATCH /api/v1/users/me` | 30 | 60 | T145 — profile fields write |
| `POST /api/v1/users/me/avatar` | 5/min | 10/min | T146 — 5MB max + JPEG/PNG/WebP only; bursty UX guard |
| `POST /api/v1/users/me/email` | 5/hour | 10/hour | T150 — anti-takeover; bumps `session_version` |
| `POST /api/v1/users/me/password` | 5/hour | 10/hour | T150 — anti-takeover; N-017 dispatch on success |
| `PUT /api/v1/users/me/privacy` | 60 | 120 | T147 — small JSON body |
| `GET /api/v1/users/me/follow-requests` + `POST .../{id}/{approve,decline}` | 60 | 120 | T148 — sidecar-enriched paginated list; approve/decline idempotent (shared bucket) |
| `POST /api/v1/reports/{user,review,diary-entry,album}` | 10/day per reporter | — | T155/T163a/T167 — anti-spam (shared bucket); idempotent 24h |
| `POST /api/v1/users/me/data-export` | 1/day | — | T153 — heavy worker; no real-time UX |

Fail-mode is **FAIL OPEN** (see §1.1.1 — same policy as notification rate-limit). Sentry alert tag `endpoint_rate_limit.redis_down` fires on Redis unavailability. 429 responses include `Retry-After` header.

### 4.6 Settings → Integrations — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: §4.6 reduced to a deferred marker — no integrations exist at MVP, so the page ships empty (or is hidden in the nav) -->
**DEFERRED-TO-V2 (CR-001).** The original §4.6 specified Settings → Integrations as the single management surface for a third-party listening-history provider connection — including connect/disconnect CTAs, a back-fill diary trigger, and Q19's "diary intact on disconnect" guarantee. This section also carried the sync-fix Run #1 (DRIFT-L3-007) resolution and the Run #2 placement decision that kept these services in `modules/auth/` rather than a new `integrations/` module.

Per CR-001 (2026-05-22), no third-party listening-history provider integration ships at MVP. The Settings → Integrations page is therefore **empty at MVP**: either render an "Integrations coming in v2" placeholder, or hide the nav entry behind a feature flag. Either choice is acceptable; the implementing PR may pick the lower-effort path.

`disconnect_spotify`, `trigger_diary_backfill`, and the related service surface are NOT implemented at MVP. The `User.music_providers` sub-doc remains `{}` for every user, so there is nothing to disconnect.

Sync-fix Run #1 (DRIFT-L3-007 → spec.md FR-027) and Run #2 (placement lock) are preserved in the project decision log for v2 context. When v2 lands the listening-history integration, this section will be re-derived from the v2 spec and these sync-fixes re-applied.

<!-- sync-fix L3-051 (Run #13): pin the T173 CSRF header-lift contract (closed an A07 wiring gap in the OWASP review pre-launch). -->
### 4.7 CSRF wiring contract (T173)

The double-submit cookie pattern referenced at §4.2 ("CSRF protection via double-submit cookie pattern") expands to the following concrete contract — pinned by T173 (OWASP Top 10 review) when an A07 wiring gap was caught and closed pre-launch (would have 403'd every authenticated mutation in prod):

1. **Cookie set semantics (backend):** On first authenticated response the backend sets `auxd_csrf` as a cookie with `SameSite=Lax` and **non-HttpOnly** so the frontend JS can read it via `document.cookie`. Value is opaque high-entropy random.
2. **Frontend header lift (`apps/web/src/lib/api-client.ts`):** A small cookie-reader helper reads the `auxd_csrf` cookie on every state-changing method (`POST` / `PATCH` / `PUT` / `DELETE`) and adds it as the `X-CSRF-Token` request header. Read-only methods (`GET` / `HEAD`) skip the lift.
3. **Backend CORS (`apps/api/src/auxd_api/main.py`):** `X-CSRF-Token` is listed in the CORS `allow_headers` set alongside the standard `Content-Type` + `Authorization` entries. Without this, browsers strip the header on cross-origin preflights.
4. **Backend enforcement (`SessionMiddleware`):** On every authenticated `POST` / `PATCH` / `PUT` / `DELETE` the middleware compares the `X-CSRF-Token` header against the `auxd_csrf` cookie value; mismatch or missing header returns `403` with `error: csrf_token_invalid`.

Regression tests pinned in T173: `apps/api/tests/integration/test_csrf_*.py` (3 specs covering missing header, mismatched header, and matched-pair happy path). Without the header lift in api-client.ts every authenticated write would 403; this is why the wiring is documented inline rather than left to the generic "double-submit" reference at §4.2.

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
| `diary` | `log_entry`, `edit_entry`, `delete_entry`, `restore_entry`, `relist_entry`, `user_diary` | Visibility evaluated on read; write endpoint rate-limited (§4.5). `user_diary` returns `{entries, next_cursor, albums: {[id]: AlbumCard}}` — the `albums` sidecar is deduped on `_id` so relistens cost one Album lookup per page (sync-fix L4-015, see T074). |
| `reviews` | `write_review`, `edit_review` *(writes `review_edit_history` row per edit — §3.1 + FR-030)*, `delete_review` *(T087 — soft-delete via `deleted_at` with 30d grace; cron-swept thereafter cascading ReviewLike rows)*, `like_review`, `unlike_review`, `list_reviews_for_album`, `get_review` *(T093a SSR backing — single-review fetch with reviewer + album + viewer-entry sidecars; 404 to non-readers to avoid existence-leak)* | Sort: newest/most-liked/highest-rated; write/like endpoints rate-limited (§4.5). List endpoint returns `users: {[id]: UserCard}` sidecar (one author lookup per page, deduped on `_id`) — parallels the diary `albums` sidecar (sync-fix L3-020/L4-015, Run #9). |
| `backlog` | `add_to_backlog`, `remove_from_backlog`, `reorder`, `auto_remove_on_log`, `list_backlog_items` *(paginated; default sort by `position` asc)*, `contains_album` *(GET /users/me/backlog/contains?album_id=… — frontend convenience helper for the +Up Next button)* | Private by default. List endpoint returns `albums: {[id]: AlbumCard}` sidecar (deduped on `_id`) — same pattern as diary `§6` row (sync-fix L3-021, Run #9). |
<!-- sync-fix L3-026 + L3-027 (Run #10): social row updated to match shipped surface; respond_to_follow_request + list_follow_requests marked DEFERRED until private-profile responder UI ships (T101a follow-up). list_suggestions + dismiss_suggestion + list_blocks + get_user_profile appended. -->
<!-- sync-fix L3-035 (Run #11): `follow` body now accepts an optional `source` literal allowlist (6 values) — shipped Session 18; drives T142 suppression + PostHog funnel facet. -->
| `social` | `follow` *(optional body {source: literal allowlist[6] = {onboarding_preselected, onboarding_mutual_taste, suggestion, profile, invite, manual}; defaults to "profile"})*, `unfollow`, `block`, `unblock`, `list_blocks`, `list_suggestions`, `dismiss_suggestion`, `get_user_profile` *(viewer-relation classifier — see FR-036)*, `is_following`, `is_blocked` · **DEFERRED:** `respond_to_follow_request` *(approve/decline)* + `list_follow_requests` (T101a follow-up — private-profile request creation ships at MVP via T101 writing `FollowRequest` rows with `state=pending`; responder UI deferred to v1.x — S-H3 Could-have). | Asymmetric; private-profile creates pending FollowRequest (US-G2 infra); follow + block endpoints rate-limited (§4.5). |
<!-- sync-fix L3-027 (Run #10): feed row covers the shipped surface; T103 + T106. -->
| `feed` | `home_feed` *(`?mode=for_you|latest` — see §10.1)*, `friends_who_rated_for_album` *(T103 — dedicated endpoint for surfaces that don't fetch the full album rollup)* | Fan-out-on-read; weighted ordering for `for_you` mode. List endpoints carry `users: {[id]: UserCard}` + `albums: {[id]: AlbumCard}` + `reviews: {[id]: ReviewSnippet}` sidecars (parallels diary/reviews sidecars). |
<!-- CR-001: `search` service surface — cold-catalog fallback is MusicBrainz live + Discogs -->
| `search` | `search_albums`, `search_users` | Atlas Search primary; cold-catalog miss → live MusicBrainz lookup → Discogs fallback (§11.1) |
<!-- sync-fix L3-034 (Run #11): notifications + seeding rows expanded — Sessions 19-21 shipped the full dispatcher + 6 public HTTP endpoints + push subscription endpoints; T117a shipped GET /api/v1/onboarding/cards. -->
| `notifications` | **Public HTTP:** `list_user_notifications`, `unread_count`, `mark_read`, `mark_all_read`, `get_preferences`, `update_preferences`, `register_push_subscription`, `delete_push_subscription` · **Internal:** `dispatch`, `is_notifiable`, `allow_dispatch`, `validate_payload`, `render_in_app` | Dispatcher + adapters. **Dispatcher writes in-app row FIRST, then threads `notification_id` to email + push adapters (S20 contract change).** |
<!-- CR-001: `prompts` module DEFERRED-TO-V2 — no listening-history polling at MVP -->
| `prompts` | **DEFERRED-TO-V2 (CR-001)** | Just-finished detection (`poll_user_for_just_finished`, `dismiss_prompt`, `disable_for_user`) ships with the v2 listening-history integration. Module folder may exist as a stub at MVP for the JustFinishedPrompt collection schema, but no service code or routes are wired in. |
| `seeding` | `get_critic_seeds_for_onboarding`, `record_card_response`, `compute_suggestions`, `score_critics_by_genre_signature`, `get_card_recommendations_for_user`, `get_onboarding_cards` · **Public HTTP:** `GET /api/v1/onboarding/cards` | Pre-checked card ordering; T117a Session 18 surfaced the HTTP endpoint for the inline critic-seed deck. |
| `moderation` | `submit_report`, `daily_scan_for_flagged_users`, `action_report` | Daily cron |
| `data_export` | `enqueue_export`, `process_export`, `mail_export` | GDPR pipeline |
<!-- sync-fix L3-041 (Run #12): 3 new module rows for Sessions 23-25 — `users` (S23 self-service surface), `gdpr` (S24 audit-log internal helper), `reports` (S15+S25 reports module + S24 acknowledge). The legacy `data_export` row above stays for traceability; actual code lives in `users` (endpoint) + `gdpr` (audit) + `workers/gdpr_export.py` (worker). -->
| `users` | PATCH /me (T145), POST /me/avatar (T146 — R2 upload + Pillow LANCZOS resize 256/128/64), PUT /me/privacy (T147), POST /me/email (T150 — current_password + session_version bump), POST /me/password (T150 — `validate_password_policy` reuse + N-017 dispatch), POST /me/delete (T058), DELETE /me/delete (T058 cancel), POST /me/data-export (T153 enqueue, returns 202), GET /me/follow-requests + POST .../{id}/{approve,decline} (T148) | 13 service methods including 4 from S17 (T057/T058/T059/T101a inline) + 9 new from S23. Profile + privacy + account self-service. |
| `gdpr` | `record_gdpr_event(user_id, action, notes, *, completed)` lib helper (T154) — called from T058 cascade + T153 enqueue/complete. `GdprAuditLog` Document persisted to `gdpr_audit_logs` collection. | Internal-only — no public HTTP routes. 4 action values: `export_requested / export_completed / deletion_scheduled / deletion_completed / deletion_canceled`. T160 cascade extension calls `record_gdpr_event` on deletion lifecycle. |
| `reports` | POST /reports/user (T155), POST /reports/review (T155/T163a), POST /reports/diary-entry (T155/T163a), POST /reports/album (T167) — all idempotent within 24h on `(reporter_id, target_type, target_id)`; self-report rejected with 422; FK-validated; per-reporter 10/day rate-limit. `acknowledge_report` service helper (T157) called by `apps/api/scripts/acknowledge_report.py` CLI. | 4 endpoints + 1 internal helper. ReportReason enum carries 7 of the 9 documented values; `target_type` includes `album` (S25 T167). |
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
- All `/album/[id]` and `/profile/[handle]` pages are SSR for share-link previews.
<!-- sync-fix L3-046 (Run #12): 8 new routes from S23-25 (settings landing + 4 sub-pages, /suspended, /legal/*, /api/og/*). -->
- `/settings` — landing page with `settings-nav.tsx` sidebar (S23).
- `/settings/profile` — T145 edit-profile form (display_name, bio, avatar upload).
- `/settings/privacy` — T147 privacy toggles + T148 pending follow-requests inbox.
- `/settings/account` — T150 email + password change forms.
- `/settings/data` — T149 data-export trigger + delete-account CTA.
- `/settings/notifications` — S21 per-channel toggles + quiet hours (already in plan; called out here for completeness).
- `/suspended` — T159 standalone page (no `(app)/layout`, no `(auth)/layout` chrome) shown when api-client catches a 403 with `error: account_suspended`.
- `/legal/privacy` + `/legal/terms` — T161 placeholder pages (standalone, no app/auth chrome) with prominent banner: "🚧 This is a placeholder. Final policy lawyer-reviewed before public launch." Footer-linked from `(auth)/layout`.
- `/api/og/album/[id]` + `/api/og/review/[id]` — T168 `next/og` `ImageResponse` routes (server-only; runtime=nodejs; 1200×630; details in §7.7).
<!-- sync-fix L3-019 (Run #8): canonical route is `/profile/[handle]` because Next.js cannot use `@` as a folder-name prefix (reserved for parallel routes). Public `/@handle` URLs are served via a Next.js middleware rewrite — see §7.1.1 Handle URL aliasing. -->

#### 7.1.1 Handle URL aliasing (deferred middleware rewrite)

The public share URL is `/@handle` (plan §11.3, e.g. `auxd.app/@casey`), but the on-disk route is `apps/web/src/app/(app)/profile/[handle]/page.tsx`. A Next.js middleware (`apps/web/src/middleware.ts`, deferred follow-up) rewrites `^/@(?<handle>[^/]+)(?<rest>/.*)?$` → `/profile/{handle}{rest}` so the canonical sharing URL still resolves to the SSR route. Until the middleware ships, the canonical interactive URL is `/profile/{handle}` and `/@handle` is not addressable. The middleware also handles the inverse — share targets generated for `/@handle` while logged-in users browse `/profile/handle` — by canonicalising the `<link rel="canonical">` to the `/@handle` form once the middleware is live.
<!-- CR-002: dedicated /review/:id route added (UJ-3). Replaces inline-expand feed behavior. -->
- `/review/[id]` is SSR (UJ-3 / CR-002) — share-link target with OG meta; full hero (album cover, title, artist, viewer's rating context, Aux badge if any, Like button, share). Naturally hosts the v2 screenshot image-gen surface (UJ-4 v2).
<!-- sync-fix L4-010 (Run #7): Session 12 added /search + /api/cover; enumerated here for completeness. -->
- `/search` is a client-component page (debounced TanStack Query, ≥3-char trigger, 200ms debounce) calling `GET /api/v1/search`; backed by the three-tier search architecture in §11.2. Empty-state surfaces the "Report missing album" link from §11.2.1.
- `/api/cover/[size]/[mbid]` is a Next.js Route Handler proxying Cover Art Archive; details in §11.4.
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
<!-- CR-002 disambiguation: this is the LOG-SHEET review composer expanding inline within the log sheet — NOT the feed-card review reading behavior. Feed reading navigates to /review/:id per UJ-3 / CR-002. -->
- Review field collapsed by default; tap "Add a review" expands inline within the log sheet (no keyboard pop on initial sheet open). *(This is composer expansion within the log sheet, not feed-card reading — feed cards navigate to `/review/:id` per UJ-3 / CR-002.)*
- Visibility select defaulted to user's `default_entry_visibility` (per FR-013).

### 7.5 Just-finished prompt — DEFERRED-TO-V2 (CR-001)

<!-- CR-001: just-finished prompt frontend component DEFERRED — no detection signal exists at MVP without the listening-history provider -->
**DEFERRED-TO-V2 (CR-001).** The `components/just-finished-prompt/` component was designed to render at the top of `/` (home feed) when a `JustFinishedPrompt` was in `pending` state for the user, with 60s TanStack Query polling, an overflow "Disable auto-prompts" toggle, and a per-album "Don't prompt for this album" dismiss with 30d stickiness. The component is removed from the MVP component tree (the directory may exist as an empty stub for §1.2 file-tree alignment) because the detection signal that fed it (recently-played + currently-playing polling from a third-party listening-history provider) is itself deferred. When v2 reintroduces detection, this component returns unchanged.

<!-- sync-fix L3-037 (Run #11): new §7.6 web push subscribe flow — Session 21 shipped T141 push-prompt + sw.js + criteria gates. -->
### 7.6 Web push subscribe flow

Push permission prompt is **non-modal** — banner on `/notifications` page. Criteria: `follows_count >= 3 OR (now - first_visit_at) >= 7d`. `markFollow()` increments `follows_count` from FollowButton mutation onSuccess + onboarding step-2 follow loop. `push-bootstrap.tsx` silently registers the service worker + stamps `first_visit_at` in localStorage at app boot. "Not now" sets `dismissed_at` (re-show after 14d). VAPID public key via `NEXT_PUBLIC_VAPID_PUBLIC_KEY`. `public/sw.js` minimal: `push` event → `self.registration.showNotification(title, {body, tag, data:{click_url, type}, icon, badge})`; `notificationclick` handler focuses an existing matching tab or opens a new window.

<!-- sync-fix L3-046 (Run #12): new §7.7 — S25 T168 OG share-card flow. -->
### 7.7 OG share-card image routes (T168)

Vercel `next/og` `ImageResponse` routes power the social-share preview cards:

- `apps/web/src/app/api/og/album/[id]/route.tsx` — 1200×630 share card for `/album/[id]`.
- `apps/web/src/app/api/og/review/[id]/route.tsx` — 1200×630 share card for `/review/[id]`.

**Runtime + behaviour:**
- `runtime = "nodejs"` (NOT edge — `next/og` ImageResponse with custom fonts works most reliably on the Node runtime).
- Server-side backend fetch via `API_BACKEND_URL` env var (falls back to `http://localhost:8000` for local dev).
- Generic `auxd` fallback image rendered on backend 404 (so dead-link share previews still render a brand card).
- `Cache-Control: public, max-age=31536000, immutable` (Vercel CDN edge cache — share-card content is immutable per `id`).

**`generateMetadata()` integration:**
- `/album/{id}` + `/review/{id}` `generateMetadata()` sets `openGraph.images = [{url: "/api/og/album/{id}", width: 1200, height: 630}]` + `twitter.card = "summary_large_image"`.
- The `<meta>` tags emitted by Next.js point at the absolute URL once `NEXT_PUBLIC_APP_URL` is set; otherwise relative URLs work for crawler fetches that respect the page's base URL.

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

<!-- sync-fix L3-036 (Run #11): §8.1 architecture clarified — in-app-FIRST contract, S20 dispatcher change. -->
The dispatcher creates the in-app Notification row **first** (via `InAppAdapter`), then threads the resulting `notification_id` to email and push adapters which UPDATE existing channel-state rather than write new rows. This S20 contract change keeps the audit trail single-row-per-dispatch (one `Notification` row aggregates the per-channel `channel_dispatch_state` rather than fanning out N rows per channel).

### 8.2 Coalescer + rate limiter (locked in Phase 5C)

- **Per-user rate limit (per-type, independent):** ≤5 in-app/hour, ≤25/day. Each notification type has its own counter; e.g., follow notifications and review-like notifications consume separate buckets. Excess events queue into a single coalesced "X new updates today" notification.
- **Per-actor rate limit (CROSS-TYPE):** notifications from User X to User Y are coalesced if >3 happen in the trailing 24h. This is INTENTIONALLY cross-type — if X follows Y, then likes 3 of Y's reviews in the same hour, the first 3 events fire individually and subsequent events from X collapse into "X did several things on your reviews today". Resolves A-003 from pre-impl-review.
- **Per-event dedup:** same event-type + same actor + same target within 1h → drop the second.
<!-- CR-001: rationale generalized — defensive layer no longer references a third-party listening-history provider -->
- **Fail-mode (locked in Phase 5C — resolves A-004):** If Redis is unreachable, the rate-limiter and coalescer FAIL OPEN — notifications dispatch through without limiting, and a Sentry alert fires with tag `notif_limiter.redis_down`. Email and web-push delivery providers enforce their own limits at their edge (Resend rate limits, VAPID server checks); our limiter is defensive.
- Implementation: Redis sorted-sets keyed by `notif:{user_id}:rate:{type}:{window}` (per-type) and `notif:{actor_id}:{recipient_id}:cross_type:{window}` (cross-type per-actor); TTL'd per-window.

### 8.3 Adapters

- `InAppAdapter`: writes to `notifications` collection; counts toward rate limit.
<!-- sync-fix L3-036 (Run #11): EmailAdapter expanded — Jinja2 templates, retry contract, FailedEmail audit row, NOOP-when-subject-None semantics. -->
- `EmailAdapter`: sends via Resend (Python SDK `resend`); transactional emails ignore quiet hours; weekly digest fires Monday 09:00 user-local. Renders per-type Jinja2 templates with `autoescape` + `StrictUndefined` from `apps/api/src/auxd_api/templates/email/*.html` (`base` + `n008_weekly_digest` + `n013_account_deletion_scheduled` + `n014_account_deletion_reminder_7d` + `n016_security_new_session` + `n017_security_password_changed`). Wraps `resend.Emails.send` in `lib/resilience.retry(attempts=3, backoff=exponential, 0.5–5s)`. On retry exhaustion writes a `FailedEmail` audit row + Sentry `email.send_failed`. **NOOP** for types whose `TYPES[type].email_subject` is `None`.
<!-- sync-fix L3-036 (Run #11): WebPushAdapter expanded — pywebpush + asyncio.to_thread, 410-Gone cleanup, NOOP-when-VAPID-unset. -->
- `WebPushAdapter`: VAPID-signed payloads; respects quiet hours (suppresses push within window); coalesces if multiple events fire close together. Calls `pywebpush.webpush` wrapped in `asyncio.to_thread` (sync SDK; don't block the event loop). Loads `PushSubscription` rows for the recipient and fans out; 410/404 responses DELETE the dead subscription; other exceptions Sentry-tagged and swallowed (send-and-forget). **NOOP** when `VAPID_PRIVATE_KEY` unset.
- Per-type defaults and copy templates live in the `TYPES` registry (T137 — `NotificationTypeSpec` dataclasses per notification type, the single source of truth for `default_in_app/email/push` flags + email subject + inbox preview copy).

### 8.4 Weekly digest job

- Scheduled via arq cron: every 5 minutes the worker checks for users whose `Monday 09:00 user-local` is in the current 5-minute window; per-user-tz awareness.
<!-- CR-002: digest hero changed from single → three-hero carousel (NT-2). -->
- For each eligible user: query top 10 entries from their follow graph past 7 days + a three-hero carousel callout (most-rated, most-reviewed, most-Aux'd in your follow graph this week — three cheap aggregate queries, one per metric, each indexed on `DiaryEntry.created_at` filtered by follow-graph). Carousel renders ABOVE the chronological body.
<!-- sync-fix L3-036 (Run #11): T143 review-likes hero — Session 20 added review-likes hero prepended above the carousel; PostHog `digest.sent` properties enumerated. -->
- **T143 prepends a "Your reviews got X likes this week" hero entry above the three-hero carousel** when ≥1 ReviewLike landed on the recipient's reviews in the trailing 7d (no zero-state — hero is omitted entirely when count is zero).
- Render plain HTML email; send via Resend; emit PostHog event `digest.sent` with properties `{user_id, hero_count, body_count, has_review_likes_hero}`.
- Suppression: `weekly_digest` channel must be ON in `NotificationPreferences`.

<!-- sync-fix L3-036 (Run #11): new §8.5 — is_notifiable predicate spec (S19 dispatcher contract). -->
### 8.5 `is_notifiable` predicate (decision order)

`is_notifiable(*, user, notif_type, actor_id=None) -> list[ChannelDecision]` returns one `ChannelDecision(channel, allowed, reason)` per channel (`in_app`, `email`, `push`).

Decision order (per-channel, short-circuit on first deny):

1. `user.status != ACTIVE` → blocked. Reason: `user_status`.
2. `actor_id` provided AND `Block` exists with `blocker_id=user.id, blocked_id=actor_id` → blocked. Reason: `blocked`.
3. Per-channel preference dict: if `user.notification_preferences.{channel}[notif_type.value]` key is present, use that bool. Reason on deny: `user_pref_off`.
4. Fallback to `TYPES[notif_type].default_{channel}` from the T137 registry. Reason on deny: `channel_default_off`.
5. **Push-only quiet-hours check** via `zoneinfo.ZoneInfo(user.quiet_hours_tz)` with rollover-midnight handling (e.g., 22:00–08:00 spans midnight). Reason on deny: `quiet_hours`. Email/digest bypass quiet hours per NT-3.
6. **Security-types email lock:** N-016 (`security.new_session`) + N-017 (`security.password_changed`) email channel returns `allowed=True` regardless of pref (hardcoded). Reason: NOT denied via `security_email_locked` — the PUT prefs route uses this same constant to return `422 security_email_locked` when a client tries to set `email[security.*] = false`.

Reasons enum: `{user_pref_off, channel_default_off, quiet_hours, blocked, user_status, security_email_locked}`.

<!-- sync-fix L3-036 (Run #11): new §8.6 — allow_dispatch coalescer + rate limiter spec (T133, S19). -->
### 8.6 Coalescer + rate limiter (`allow_dispatch`)

`allow_dispatch(*, user_id, actor_id, notif_type, target_id=None) -> CoalesceDecision` is the single entry point downstream of `is_notifiable`. Four Redis buckets gate dispatch:

1. **Per-user per-type hour** — `notif:{user_id}:rate:{type}:hour` sorted-set sliding window, **5/hr**.
2. **Per-user per-type day** — `notif:{user_id}:rate:{type}:day` sliding window, **25/day**.
3. **Per-actor cross-type day** — `notif:{actor_id}:{user_id}:cross_type:day` sliding window, **3/24h** (only when `actor_id` provided — system-emitter events skip this bucket).
4. **Per-event dedup** — `notif:dedup:{type}:{actor_id}:{target_id}` `SET NX EX 1h` for race-free atomic write.

Verdicts:
- Dedup hit → `drop`.
- Any rate breach → `coalesce(coalesced_window)`.
- Else → `send` (records hits in all 3 rate buckets atomically via pipeline).

**FAIL-OPEN** on Redis unavailability: returns `send` + emits `notif_limiter.redis_down` Sentry warning. Mirrors the `lib/rate_limit.py` pipeline pattern.

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
    # sync-fix L3-029 (Run #10): shipped uses request-scoped `?mode=for_you|latest` query param,
    # not a persisted `User.feed_latest_only` field. The mode is parsed off the route + threaded
    # into `build_home_feed(mode=...)`.
    if mode == "for_you":
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
<!-- sync-fix L3-030 (Run #10): plan formula was additive (`base + 0.20*has_review + 0.15*extreme + 0.10*top5`) with `exp(-h/72)` decay; shipped is MULTIPLICATIVE compose on a 1.0 base with `0.5^(age_hours/72)` half-life. Updated to match shipped at feed/service.py:512-548. The half-life math is equivalent at the half-life point but composes differently for stacked weights. -->

# Multiplicative composition on a 1.0 base — matches feed/service.py
score = 1.0
score *= 1.20  if entry.review_id is not None
score *= 1.15  if entry.rating in {5.0, 1.0}     # extreme ratings boost
score *= 1.10  if entry.user_id in viewer.top5_authors  # see §10.2.1
score *= math.pow(0.5, age_hours / 72.0)         # 3-day half-life (base 0.5; equivalent to exp(-h/72*ln 2))

# Reference (historical / additive sketch, pre-shipping):
# score = base_recency_score
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
- Profile URL share (`auxd.app/@handle` — rewritten to `/profile/[handle]` by middleware per §7.1.1)
- Critic-seed directory at `/critics`

<!-- sync-fix L4-011 (Run #7): cover-art proxy got its own plan section. T072 referenced §17.5 (Redis) by mistake; corrected to §11.4 here. -->
### 11.4 Cover-art proxy (Next.js Route Handler)

The frontend serves album cover art through `/api/cover/[size]/[mbid]` — a Next.js Route Handler that proxies Cover Art Archive (CAA) and chains to a caller-supplied fallback URL on 404. Source: `apps/web/src/app/api/cover/[size]/[mbid]/route.ts` (T072).

**Why a proxy at all** — the album-detail UI needs `<img>` URLs it can render with `loading="lazy"` and that the Vercel CDN can cache. Hot-linking CAA directly is permitted by their ToS (per §17.4), but doing so leaks every render through `coverartarchive.org` with no way to cache the negative case or chain to Discogs. The proxy normalizes the contract.

**Request shape:**
```
GET /api/cover/{size}/{mbid}?fallback={discogs_url}
  size  ∈ { "250", "500", "1200" }              — CAA's canonical front-image sizes
  mbid  ∈ release-group MBID (UUID-ish format)  — auxd canonical key per CR-001
  fallback (optional)                           — https:// URL, used on CAA 404
```

**Behaviour:**
1. **Validation.** `size` must be in the allowed set; `mbid` must match `/^[a-f0-9-]{20,}$/i`. Bad params → `400 invalid_size` or `400 invalid_mbid` (no upstream call).
2. **CAA fetch.** `GET https://coverartarchive.org/release-group/{mbid}/front-{size}` with `cache: "force-cache"` (Next.js fetch cache, default 365-day TTL). Success → stream body back with `Content-Type: image/jpeg` (or as CAA returned) and `Cache-Control: public, max-age=604800, s-maxage=604800, immutable` (7-day edge cache).
3. **CAA 404.** If a `fallback` query param is present AND starts with `https://`, respond with `302` to that URL plus `Cache-Control: public, max-age=3600` (1-hour negative cache). Otherwise respond `404` with the same 1-hour negative cache header.
4. **Upstream 5xx / network error.** Respond `502` with no cache headers (let the next render retry the proxy, which will retry CAA).

**Param naming note (sync-fix L4-011):** the original T072 task spec wrote `[albumId]`, but the route uses `[mbid]` because (a) CAA is MBID-keyed natively, and (b) the consumer (album-detail page + search results) already has the MBID from the backend response, so the proxy can stay stateless without a backend roundtrip.

**Consumer pattern (album-detail page, T070):**
```tsx
<img
  src={`/api/cover/500/${album.mbid}?fallback=${encodeURIComponent(album.cover_art_url ?? "")}`}
  alt={`Cover of ${album.title}`}
  loading="lazy"
/>
```

For albums without an MBID (Discogs-only candidates pending reconciliation), the consumer bypasses the proxy and renders `album.cover_art_url` directly — the proxy's MBID validator would reject those anyway.

**Observability:** CAA upstream failures already surface via the Sentry hook configured in `apps/web/instrumentation.ts`. The `caa.unavailable` Sentry alert tag described in §15.4 covers backend MBID-lookup failures; the proxy adds no separate alert at MVP because edge logs are sufficient for low-volume diagnosis.

---

## 12. Seeding-Strategy Backend

### 12.1 CriticSeed roster

Authored manually by founder; persisted as `critic_seeds` collection records, one row per founder-approved User. The `CriticSeed` table itself (via the `user_id` FK + the boolean `active` column on `CriticSeed`) is the source of truth for critic-tier membership — there is **no** `critic_seed_active` flag on `User`. Denormalising onto User was rejected to keep the editorial roster atomic (one place to flip on/off, no two-table sync). The review-list endpoint (`reviews_router`'s tier classifier) queries `CriticSeed.find({user_id: {$in: owner_ids}, active: true})` to compute the critic-seed tier (sync-fix L3-023, Run #9).

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

<!-- sync-fix L3-039 (Run #11): genre-bonus formula + `_GENRE_BONUS_MAX = 20.0` knob pinned — shipped Session 18 (T117). -->
Score = `priority + (jaccard_overlap_with_viewer_genre_signature × _GENRE_BONUS_MAX)` where `_GENRE_BONUS_MAX = 20.0` — caps the genre-overlap bonus so a perfect-match closes a 20-point priority gap. Bumping above 30 would let a niche-genre critic with priority=50 outrank a generalist with priority=80, which the founder doesn't want until per-user signal is much richer (codified in [seeding-strategy.md §3](./product-spec/seeding-strategy.md)).

<!-- sync-fix L3-032 (Run #10): post-onboarding suggestion scoring (T104) was only documented in tasks.md + product-spec/seeding-strategy.md §4 — moved here for plan.md completeness. -->
### 12.2.1 Post-onboarding suggestion scoring (T104 — Suggestion + SuggestionDismissal collections)

Runs as an arq scheduled job (`compute_suggestions_for_user(user_id)` in `apps/api/src/auxd_api/workers/suggestions_job.py`) every N hours per user. Output rows go to the `suggestions` collection (§3.1); user-dismissed suggestions accumulate in `suggestion_dismissals` (30d TTL).

Score formula (matches `product-spec/seeding-strategy.md` §4 exactly):

```text
score = 0.40 * mutual_taste_overlap        # |overlap of (album_id, rating∈{4,4.5,5}) sets| / |union|
      + 0.30 * followed_by_followed        # count of viewer's followees who follow the candidate (normalised)
      + 0.15 * shared_seed                 # viewer + candidate both follow ≥1 same CriticSeed
      + 0.10 * label_genre                 # shared label / genre on top-5 albums each
      + 0.05 * recency                     # candidate has a DiaryEntry in last 30 days
```

Excluded from output: already-followed (joined against `follows` at write time), blocked-in-either-direction (against `blocks`), dismissed-within-30d (against `suggestion_dismissals`). The read endpoint (`GET /users/me/suggestions` in `social/routes.py`) re-applies the already-followed + dismissed filters as defense-in-depth — a Follow could land between worker run and read.

arq cron registration is **DEFERRED to T009** (the arq deploy worker config); the scoring function itself is fully tested via `tests/unit/test_suggestions_algorithm.py` (15 tests).

### 12.3 Analytics

Every Follow created during onboarding carries `source: onboarding_preselected | onboarding_mutual_taste | manual` so we can measure:
- % of users who keep the critic-seed defaults
- % of users who untick critic-seed defaults
- Conversion of mutual-taste suggestions

---

## 13. Moderation Flow (US-G4)

### 13.1 Report queue

User-submitted reports persist to `reports` collection in `state=open`. Each report carries `reporter_id`, `target_type`, `target_id`, `reason` (enum), `detail` (free text ≤2000 chars).

<!-- sync-fix L3-044 (Run #12): target_type + reason enums updated to shipped S15/S25 contract; `missing_album` was a Run #5 L3-006 sync-fix value, now superseded by the `album` target_type (T167) which carries dedicated `wrong_metadata` + `duplicate` reasons for catalog-gap UX. -->

**`target_type` enum (5 values):** `user | diary_entry | review | album | missing_album`. The `album` target_type was added in S25 T167 for catalog-quality reports (wrong metadata / duplicate releases); the legacy `missing_album` target_type (Run #5 L3-006 sync-fix) is retained for search-empty-state reports — `target_id` is the raw query string and `reason` is implicitly `catalog_gap`.

**`reason` enum (9 values — S15 baseline + S25 expansion):** `harassment, spam, nsfw, impersonation, hate_speech, catalog_gap, wrong_metadata, duplicate, other`. The S15 baseline was `harassment / spam / impersonation / hate_speech / other`; S25 T167 added `wrong_metadata + duplicate` for the `album` target_type; `nsfw` and `catalog_gap` are reserved for content-flag + missing-album surfaces.

**Submission contract (T155 / T163a / T167 endpoints):** `POST /api/v1/reports/{user,review,diary-entry,album}` is idempotent within 24h on `(reporter_id, target_type, target_id)` — duplicate submissions return the existing row (200, not 409). Self-report rejected with 422. Per-reporter 10/day rate-limit shared across all `/reports/*` endpoints. FK-validated: 422 if `target_id` doesn't exist.

### 13.2 Daily log-scan

<!-- sync-fix L3-044 (Run #12): S24 T156 cron pseudocode + author-resolution + Discord webhook + idempotent re-run. -->

arq scheduled job at 03:00 UTC daily, in `workers/moderation_scan.py`:

```python
async def daily_moderation_scan():
    """
    T156 — flag users with ≥3 reports in trailing 7d.

    Author-resolution: content reports (target_type ∈ {review, diary_entry}) resolve
    to the row's `user_id` (author). User reports retain `target_id` directly.
    Reports against soft- or hard-deleted rows are silently dropped (no flag fired).

    Idempotent re-run: User.flagged_for_review_at is checked — if set within trailing 7d,
    skip the flag emission (Discord webhook is not re-fired).
    """
    candidates = await Report.find({"created_at": {"$gte": now() - timedelta(days=7)}}).to_list()
    by_user: dict[str, list[Report]] = group_by_effective_target_user_id(candidates)  # resolves authors
    for user_id, reports in by_user.items():
        if len(reports) < 3:
            continue
        user = await User.get(user_id)
        if user is None or user.deleted_at is not None:
            continue
        if user.flagged_for_review_at and (now() - user.flagged_for_review_at) < timedelta(days=7):
            continue  # idempotent — already flagged within trailing 7d
        user.flagged_for_review = True
        user.flagged_for_review_at = now()
        await user.save()
        reason_breakdown = Counter(r.reason for r in reports)
        await discord_webhook_post(
            settings.DISCORD_WEBHOOK_URL,
            f"User @{user.handle} flagged: {len(reports)} reports in 7d "
            f"(reasons: {dict(reason_breakdown)})",
        )
```

`DISCORD_WEBHOOK_URL` is the same setting reused from T010 synthetic monitoring (see §17.1).

### 13.3 Admin review UI

Out of scope at MVP — flagged users surface in a single founder-only admin dashboard (read from Atlas directly in MongoDB Compass). Web UI is v1.x. Acknowledgement happens via the CLI flow in §13.3a.

### 13.3a Acknowledge report — CLI flow (T157)

<!-- sync-fix L3-044 (Run #12): new §13.3a — S24 T157 acknowledge_report helper + CLI; no admin UI at MVP. -->

Founder runs `apps/api/scripts/acknowledge_report.py {report_id} --note "..."` from a deploy shell. The CLI invokes the `acknowledge_report` service helper which:
1. Marks `Report.acknowledged_at = now()` (no-op if already set — idempotent).
2. Fires an N-012 dispatch to the original reporter ("Thanks — we've reviewed your report.") via the standard notifications dispatcher (§8).

The CLI carries `--dry-run` and `--note` flags; the `--note` value is stored on `Report.resolution_note` for audit. No web UI is shipped at MVP.

### 13.4 No auto-suspension

Per US-G4 acceptance criteria: no realtime auto-suspension at MVP. All actions require manual founder review. This is a deliberate trade-off — minimizes false-positives during launch when moderation patterns are unknown.

### 13.5 SUSPENDED account middleware (T159)

<!-- sync-fix L3-044 (Run #12): new §13.5 — S24 T159 SuspendedAccountMiddleware; SUSPENDED users get 403 on every authenticated route except an allow-list. -->

`SuspendedAccountMiddleware` extends `SessionMiddleware`. When the resolved `User.status == "suspended"`, the middleware returns **HTTP 403** with body `{error: "account_suspended", appeal_url: "mailto:..."}` on **every authenticated route** EXCEPT the following allow-list:

- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all-devices`
- `POST /api/v1/users/me/delete` (the user can still self-delete while suspended)

There is no admin-action endpoint to suspend users at MVP — founder runs `db.users.updateOne({_id: X}, {$set: {status: "suspended"}})` directly via MongoDB Compass. The frontend `api-client.ts` catches the 403 + `error: "account_suspended"` body and redirects to the standalone `/suspended` page (no app/auth chrome).

### 13.6 Album merge — admin CLI (T167)

<!-- sync-fix L3-044 (Run #12): new §13.6 — S25 T167 admin path for album consolidation on wrong-metadata / duplicate reports. -->

`apps/api/scripts/merge_albums.py` is the admin tooling that consolidates a losing album row into a winning row when a `wrong_metadata` or `duplicate` report is resolved:

- Dry-run is the default (the CLI prints the operations it would perform; pass `--yes` for non-interactive execution).
- FK-rewrite: updates `DiaryEntry.album_id`, `Review.album_id`, `BacklogItem.album_id` losing → winning.
- Hard-deletes the losing `Album` row.
- **No `AlbumRedirect` Document at MVP** — losing-album URLs simply 404. This is acceptable for admin tooling (acknowledged trade-off: future bookmark-holders lose link integrity, but cost of `AlbumRedirect` infrastructure is not justified at MVP scale).

---

## 14. GDPR Pipeline

<!-- sync-fix L3-043 (Run #12): §14 rewritten to match shipped S24 T153/T154/T160 contract — path corrected to /api/v1/users/me/data-export, dual-artifact (JSON + ZIP-of-CSVs), R2_EXPORT_BUCKET + 24h presigned URLs, Resend not Postmark, audit-log threading, cascade list extended to 4 newer collections + Report anonymisation. -->

### 14.1 Data export

`POST /api/v1/users/me/data-export` → enqueues an arq job. Per-user 1/day rate-limit (§4.5); the endpoint returns **202 Accepted** with body `{job_id, audit_log_id, eta_seconds}`. Audit-log threading: `lib/audit.record_gdpr_event(user_id, EXPORT_REQUESTED, ...)` is called at the endpoint before enqueue; the worker calls `record_gdpr_event(user_id, EXPORT_COMPLETED, notes=..., completed=True)` on success.

The worker (`apps/api/src/auxd_api/workers/gdpr_export.py`) aggregates **13 owned collections** for the user — `User` itself is included but stripped of `password_hash`, `admin_notes`, and `session_version`:

- `DiaryEntry`, `Review`, `ReviewLike`, `ReviewEditHistory`, `Backlog`, `BacklogItem`, `Follow` (both directions), `FollowRequest` (both directions), `Block`, `Notification`, `PushSubscription`, `HandleRedirect`

```python
async def process_export(user_id: str, job_id: str, audit_log_id: str):
    user = strip_internal_fields(await User.get(user_id))
    diary = await DiaryEntry.find({"user_id": user_id}).to_list()
    reviews = await Review.find({"user_id": user_id}).to_list()
    review_likes = await ReviewLike.find({"user_id": user_id}).to_list()
    review_edit_history = await ReviewEditHistory.find({"user_id": user_id}).to_list()
    backlog = await Backlog.get_with_items(user_id)
    backlog_items = await BacklogItem.find({"backlog.user_id": user_id}).to_list()
    follows = await Follow.find_pair_for_user(user_id)
    follow_requests = await FollowRequest.find_pair_for_user(user_id)
    blocks = await Block.find({"blocker_id": user_id}).to_list()
    notifications = await Notification.find({"user_id": user_id}).to_list()
    push_subscriptions = await PushSubscription.find({"user_id": user_id}).to_list()
    handle_redirects = await HandleRedirect.find({"user_id": user_id}).to_list()

    # Dual-artifact: JSON (programmatic re-import) + ZIP-of-CSVs (spreadsheet inspection)
    json_blob = serialize_user_data(user, diary, reviews, ...)  # single-object JSON
    zip_blob = zip_of_csvs(
        # csv.writer + zipfile.ZipFile — one CSV per collection
        diary=diary, reviews=reviews, review_likes=review_likes, ...,
    )

    # Upload to R2 with 24h presigned URLs
    json_url = await r2.put_with_presigned(
        bucket=settings.R2_EXPORT_BUCKET,  # default `auxd-exports`
        key=f"exports/{user_id}/{job_id}/export.json",
        body=json_blob,
        presigned_ttl_seconds=86400,
    )
    zip_url = await r2.put_with_presigned(
        bucket=settings.R2_EXPORT_BUCKET,
        key=f"exports/{user_id}/{job_id}/export.zip",
        body=zip_blob,
        presigned_ttl_seconds=86400,
    )

    # Email via Resend DIRECTLY (NOT through the dispatcher chain — transactional shape
    # outside the notification taxonomy; one-off non-rate-limited delivery).
    await resend.send_export_email(user.email, json_url, zip_url)

    # Audit log on completion
    await record_gdpr_event(user_id, EXPORT_COMPLETED, notes=f"job_id={job_id}", completed=True)
```

SLA: complete within 24h (typically <5 minutes). Email provider is **Resend** (NOT Postmark — sync-fix L4-003 from Run #2 switched the project to Resend on cost grounds; see §17.6).

### 14.2 Account deletion

`POST /api/v1/users/me/delete` →
1. Set `user.status = "deleted"`, `user.deletion_scheduled_for = now() + 30d`.
2. Call `record_gdpr_event(user_id, DELETION_SCHEDULED, notes=f"scheduled_for={deletion_scheduled_for}")` for audit.
3. Show user a banner on subsequent logins: "your account is scheduled for deletion in N days — cancel?".
4. `DELETE /api/v1/users/me/delete` cancels the scheduled deletion (sets `status = "active"`, clears `deletion_scheduled_for`); calls `record_gdpr_event(user_id, DELETION_CANCELED, ...)`.
5. arq cron daily: finds users where `deletion_scheduled_for < now()` and processes cascade hard-delete (T058 extended by T160 — covers **13 owned collections** + 1 anonymisation, then User):

   - **Hard-delete (13 collections):** `DiaryEntry`, `Review`, `ReviewLike` (both given and received), `ReviewEditHistory`, `BacklogItem`, `Backlog`, `Follow` (both directions), `FollowRequest` (both directions), `Block` (both directions), `Notification`, `PushSubscription`, `Suggestion`, `SuggestionDismissal`, `FailedEmail`, `HandleRedirect`, then `User`.
   - **Anonymise (audit-retained):** `Report.reporter_id → None` on rows authored by the deleting user (T160 — preserves target rows for audit retention without leaking the deleted user's identity). `MusicProvider` tokens — empty at MVP per CR-001, so no-op.
   - Closes with `record_gdpr_event(user_id, DELETION_COMPLETED, completed=True)`.

### 14.3 GDPR audit log

Every export + deletion lifecycle event is persisted to the `gdpr_audit_logs` collection (S24 T154 — `GdprAuditLog` Document + `record_gdpr_event` helper). Fields: `user_id`, `action` ∈ `{export_requested, export_completed, deletion_scheduled, deletion_completed, deletion_canceled}`, `requested_at`, `completed_at?`, `notes?`. Indexed `(user_id, requested_at DESC)`. 7-year retention is deferred to operator config (no TTL at MVP — founder runs archival manually if needed).

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
<!-- sync-fix L3-024 (Run #9): single `backlog.added` row replaced with 4 shipped events from Session 16. -->
| `backlog.item_added` | `item_id`, `album_id`, `position`, `has_notes`, `per_item_visibility`, `source` | Up Next, album detail |
| `backlog.item_removed` | `item_id`, `source` | Up Next, album detail |
| `backlog.reordered` | `count` | Up Next |
| `backlog.converted_to_log` | `entry_id`, `album_id`, `source` | Diary log endpoint (T100 — emits when `auto_remove_on_log` removes a backlog item on a fresh diary insert; backbone for the M3/M6 backlog→log KPI) |
| `digest.sent` | `entries_count`, `digest_week` | Email |
<!-- sync-fix L3-031 (Run #10): single `follow.created` row replaced with the 5 shipped social events from Session 17 (T101-T105). -->
| `social.follow` | `follower_id`, `followee_id`, `state` (accepted/pending), `source` (profile/discover/onboarding) | Profile, Discover |
| `social.unfollow` | `followee_handle` | Profile |
| `social.block` | `blockee_handle`, `reason` | Profile, Diary entry, Review |
| `social.unblock` | `blockee_handle` | Settings, Profile |
| `social.suggestion_dismissed` | `suggested_user_id` | Discover |
| `search.executed` | `query_length`, `result_count`, `via_musicbrainz_fallback`, `via_discogs_fallback` | Search |
| `search.album_reported_missing` | `query`, `submitter_id` | Search (CR-001 elevated — track catalog-gap rate) |
<!-- sync-fix L3-048 (Run #12): 4 new events from S23-25 + 3 existing-but-undocumented events from S20-21. -->
| `profile.updated` | `fields_changed` (list), `viewer_id` | T145 — Settings → Profile save |
| `email.changed` | `viewer_id`, `session_version_after` | T150 — stub event (verify-email click-link pipeline deferred; this is the only signal at MVP) |
| `album.report_wrong` | `album_id`, `reason` ∈ `{wrong_metadata, duplicate}`, `viewer_id` | T167 — `/album/[id]` ReportWrong dialog submission |
| `og.image_requested` | `surface` ∈ `{album, review}`, `target_id`, `cache_status` ∈ `{hit, miss}` | T168 — one-off bot-driven; flagged as "may not fire reliably under bot traffic" (most crawlers don't execute server-side JS, but the Vercel edge already logs) |
| `settings.notifications_updated` | `fields_changed` (list), `viewer_id` | T139 (S21) — Settings → Notifications save |
| `notifications.opened` | `count_unread`, `viewer_id` | T140 (S21) — Bell open / `/notifications` page view |
| `notifications.mark_all_read` | `count_marked`, `viewer_id` | T140 (S21) — POST `/api/v1/notifications/mark-all-read` |
| `push.prompt_shown` / `push.permission_granted` / `push.permission_denied` / `push.dismissed` / `push.subscribe_failed` | `viewer_id`, `criteria` ∈ `{follows_count_3, activity_7d}` | T141 (S21) — non-modal push-prompt lifecycle |

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

- **Per-PR (automated):** `@axe-core/playwright` runs against built `(onboarding)`, `(app)/home`, `(app)/album/[id]`, `(app)/profile/[handle]`, `(app)/settings/*`, `components/log-sheet` test pages. Threshold: **0 violations**.
- **Per-release (manual):** Founder runs keyboard-only nav audit on the same screen set; result recorded in a release-readiness checklist.
- **Failing the gate:** Any axe violation blocks merge; can be waived only via a documented `// a11y-waiver:` comment with rationale + Phase 9 follow-up issue.

<!-- sync-fix L3-050 (Run #13): anchor §18 Pre-launch audit outputs (T171 a11y + T172 perf + T173 security). -->
### 16.6 Pre-launch audit outputs (T171 / T172 / T173)

- **T171 a11y audit results:** `docs/a11y-audit.md` — `@axe-core/playwright` scans across 23 routes (wcag2aa tag set); 0 CRITICAL after fixes landed in feed-list.tsx + diary-list.tsx (empty `<TabsContent>` panels for proper aria-controls→panel-id resolution); 4 SERIOUS/MODERATE flagged as Phase 9 follow-ups. Spec files under `apps/web/tests/a11y/` (helpers + auth + onboarding + app + settings).
- **T172 perf audit:** `docs/perf-audit.md` — 4 k6 scripts at `apps/api/tests/perf/k6_*.js` (smoke / soak / spike / stress) plus Lighthouse Playwright spec at `apps/web/tests/perf/lighthouse.spec.ts`; budgets mirror spec.md §6.1 (p95 home feed <500ms; p95 album detail <400ms). Some staging-environment metrics N/A pending T175 staging provisioning.
- **T173 OWASP Top 10 review:** `docs/security-review.md` — 1 HIGH (A07 CSRF wiring) closed pre-launch (api-client.ts cookie-reader + backend CORS `allow_headers` lift; see §4.7 for the contract); 0 CRITICAL/HIGH open; 2 LOW follow-ups documented for post-launch.

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
- Secrets via `fly secrets set`: `MONGODB_URI`, `REDIS_URL`, `DISCOGS_API_TOKEN` (optional, server-side only), `SESSION_HMAC_KEY`, `TOKEN_ENCRYPTION_KEY` (provisioned for v2 listening-history token encryption; unused at MVP), `RESEND_API_KEY`, `RESEND_FROM_ADDRESS` (S20 T135 — transactional From), `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (S20 T136 — mailto: identifier for VAPID), `PUBLIC_APP_URL` (S20 T136 — origin for push payload click URLs), `SENTRY_DSN`, `POSTHOG_API_KEY`, `POSTHOG_HOST`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME` (backups; default `auxd-backups`), `R2_AVATAR_BUCKET` (S23 T146 — default `auxd-avatars`; separate from backups because access-pattern is public-read + retention is durable not age-out), `R2_EXPORT_BUCKET` (S24 T153 — default `auxd-exports`; export bundles uploaded with 24h presigned URLs), `DISCORD_WEBHOOK_URL` (S24 T156 admin alert payload for `flagged_for_review` users; reused from T010 synthetic monitoring), `API_BACKEND_URL` (S25 T168 — server-side env var for `next/og` `ImageResponse` backend fetch; falls back to `http://localhost:8000` for local dev). See `docs/infra.md` for the full source-of-truth table. **DEFERRED-TO-V2 (CR-001):** `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_INTEGRATION_ENABLED` (removed from this list — re-add when v2 selects a listening-history provider; the env-var names should be re-derived per the v2 provider).
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

<!-- sync-fix L3-050 (Run #13): operator runbook index — anchors the 7 Session 26 docs + 2 earlier founder workflows. -->
### 17.7 Operator runbooks

Operator-facing runbooks live under `docs/` and are the single source of truth for environment provisioning, launch ceremony, and the closed-beta workflow:

- `docs/staging.md` (T175) — staging environment provisioning runbook (Fly secrets + Atlas + Upstash + DNS + smoke checks).
- `docs/launch.md` (T180) — M0 launch ceremony, T-72h → T+72h timeline + acceptance gates.
- `docs/launch-checklist.md` (T179) — 11-section consolidated readiness review (acts as the Phase 9 gate).
- `docs/closed-beta-runbook.md` (T176) — invitee curation + early-signal dashboards for Phase M-2.
- `docs/security-review.md` (T173) — OWASP Top 10 review; 1 HIGH (A07 CSRF wiring) closed; 0 CRITICAL/HIGH open.
- `docs/a11y-audit.md` (T171) — axe-core wcag2aa results across 23 routes; 0 CRITICAL after fixes.
- `docs/perf-audit.md` (T172) — k6 + Lighthouse thresholds vs spec.md §6.1.
- `docs/critic-seed-runbook.md` (T162) — CriticSeed admin workflow.
- `docs/founder-workflows/seed-content.md` (T166) — seed-content authoring workflow.

---

## 18. Phased Implementation Roadmap

### Phase M-2 (Closed Beta) — ~8 weeks of build (CR-001: ~2 weeks shorter; OAuth + polling + just-finished cluster removed)

<!-- CR-001: build order rewritten — no third-party OAuth, no auto-import, no just-finished detection at MVP -->
Internal-only + critic-seed onboarding wave. No third-party listening-history provider quota gating. No public access.

<!-- sync-fix L3-050 (Run #13): Phase M-2 cross-link to docs/closed-beta-runbook.md (T176). -->
**Operator runbook:** `docs/closed-beta-runbook.md` (T176) covers invitee curation + early-signal dashboards + bug-bash protocol for this phase.

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

<!-- sync-fix L3-050 (Run #13): Phase M0 cross-link to docs/launch.md (T180) + docs/launch-checklist.md (T179). -->
**Operator runbooks:** `docs/launch.md` (T180) defines the T-72h → T+72h M0 launch ceremony timeline + acceptance gates; `docs/launch-checklist.md` (T179) is the 11-section consolidated readiness review that acts as the Phase 9 gate.

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
