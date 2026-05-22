# Codebase Analysis: auxd MVP

> Generated: 2026-05-21 | Codebase: `.` (project root)
> Feature: `001-auxd-mvp`
> Phase: 1 — Research (Codebase dimension)

---

## 1. Greenfield Status Confirmation

**This is a greenfield project.** There is no application code in the repository.

What exists today (verified by inspection of the project root):

- `.specify/` — Spec Kit templates, scripts, installed extensions
- `.claude/skills/` — installed Claude command skills (Product Forge, V-Model, Git extensions)
- `.product-forge/config.yml` — Product Forge configuration (project name, tech stack, defaults)
- `CLAUDE.md` — minimal context file (4 lines, points to "the current plan")
- `features/001-auxd-mvp/` — Phase 0 (Problem Discovery) artifacts and an empty `research/` directory

What does NOT exist:

- No `package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, or any other package/dependency manifest
- No `src/`, `app/`, `backend/`, `frontend/`, or any source directory
- No `Dockerfile`, `docker-compose.yml`, CI configuration, or deployment manifests
- No test directory, no test framework configured
- No constitution: `.specify/memory/constitution.md` is the unfilled placeholder template (`[PROJECT_NAME] Constitution`, `[PRINCIPLE_1_NAME]`, etc.)

**Consequences for the lifecycle:**

1. The "Reusable Existing Code" and "Reference Implementations" tables are necessarily empty.
2. The "Codebase Constraints" table cannot reference real ADRs or constitution sections — Phase 5 (plan) must propose and ratify them.
3. Phase 5 must include foundational scaffolding tasks (project init, auth, infra) **before** any feature-level work.
4. The plan's Constitution Check gate is effectively a no-op until the constitution is filled in. Recommend: ratify a minimal constitution as a Phase 5 prerequisite, or run `/speckit-constitution` first.

---

## 2. Architecture Overview

No application architecture exists. The scaffolding implies a target architecture composed of:

- A React single-page or server-rendered frontend (framework choice TBD — see §4).
- A FastAPI backend (Python ASGI) serving JSON over HTTPS, likely with Pydantic models and async I/O.
- A MongoDB document store (self-hosted or Atlas) holding domain documents (users, albums, ratings, reviews, follows, listen entries, backlog items).
- One or more external integrations: Spotify Web API (catalog + auth + listening history), possibly Apple Music API and MusicBrainz/Discogs as metadata fallbacks.

The scaffolding does pre-commit Spec Kit's standards-driven workflow: every architectural decision must be captured in `plan.md` and (in V-Model mode) decomposed through SYS → ARCH → MOD designs with traceability.

Note: `.product-forge/config.yml` currently declares `default_feature_mode: "v-model"` but `.forge-status.yml` for this feature records `feature_mode: "standard"` and `speckit_mode: "classic"` — the feature-level override stands. Phase 5 should not be derailed into full V-Model artifact production unless explicitly reaffirmed.

---

## 3. Project Scaffolding Inventory

### Spec Kit installation

- Spec Kit version: `0.8.12` (from `.specify/init-options.json`)
- Branch numbering: `sequential` (e.g., `001-auxd-mvp`)
- Scripts: `bash` (the `.sh` flavour at `.specify/scripts/bash/`)
- Integration: `claude` (with `ai_skills: true`)

### Installed Spec Kit extensions

| Extension | Version | Role |
|---|---|---|
| `git` | (bundled) | Auto-commits and branch management hooks before/after every Spec Kit phase |
| `product-forge` | 1.5.1 | Full product lifecycle orchestrator (research → ship → retrospective). 30+ commands. |
| `v-model` | 0.5.0 | IEEE/ISO formal artifact progression + traceability matrix (optional for this feature) |

### Hook wiring (`.specify/extensions.yml`)

`auto_execute_hooks: true`. Every Spec Kit phase has `before_*` and `after_*` git hooks for commit/branch automation. `after_tasks` additionally triggers the V-Model traceability matrix (optional, prompts the user).

### Claude skills installed (`.claude/skills/`)

55 skills across three families:

- **Spec Kit core (8):** specify, plan, tasks, implement, clarify, analyze, checklist, taskstoissues
- **Product Forge (28):** forge, research, product-spec, revalidate, bridge, plan, tasks, implement, verify-full, test-plan, test-run, status, problem-discovery, api-docs, security-check, tracking-plan, pre-impl-review, code-review, release-readiness, sync-verify, change-request, portfolio, backfill, monitoring-setup, migration-plan, i18n-harvest, experiment-design, feature-flag-cleanup, retrospective
- **V-Model (13):** requirements, acceptance, system-design, system-test, architecture-design, integration-test, module-design, unit-test, hazard-analysis, impact-analysis, peer-review, test-results, audit-report, trace
- **Git helpers (5):** initialize, feature, commit, validate, remote
- **Constitution (1):** speckit-constitution

### Spec Kit templates available

`.specify/templates/` contains `plan-template.md`, `tasks-template.md`, `spec-template.md`, `constitution-template.md`, `checklist-template.md`. These are vanilla — no auxd-specific customizations yet.

---

## 4. Constitution Status

`.specify/memory/constitution.md` is **the unfilled template** — every section is `[PLACEHOLDER]`. Specifically:

- All five core principles are unnamed (`[PRINCIPLE_1_NAME]` … `[PRINCIPLE_5_NAME]`).
- Sections 2 and 3 (additional constraints, development workflow) are empty.
- Governance, version, and ratification metadata are placeholders.

**Implication:** there are no mandatory architectural patterns currently in force. This is unusual for the Spec Kit `plan` workflow, whose Constitution Check gate is built around verifying that the plan honours ratified principles.

**Recommendation for Phase 5:** before producing `plan.md`, run `/speckit-constitution` (or include constitution ratification as Task 0 in the plan) to capture a minimum viable set of principles. Suggested initial set, tailored to auxd:

1. **Library-first feature modules** — each auxd domain (users, albums, ratings, reviews, follows, listening, recommendations) is implemented as a self-contained FastAPI router + service + repository slice. No god-modules.
2. **Test-first for catalog/auth edges** — Spotify OAuth callback, listening-history sync, and album-id normalization (MusicBrainz/Spotify/Apple cross-reference) get contract tests before implementation.
3. **External calls behind a resilience boundary** — every outbound call to Spotify/Apple/MusicBrainz wrapped in retry+timeout+circuit-breaker; no raw `httpx.get` in handlers.
4. **MongoDB schema versioning** — every collection document carries a `schema_version` field; migrations are explicit, written, and reversible.
5. **Observability** — structured JSON logging, request-IDs, and one tracing primitive (OpenTelemetry preferred) wired from day one.

The above are *recommendations only*. Phase 5 (or a pre-Phase-5 `/speckit-constitution` step) must formally ratify whichever subset the owner adopts.

---

## 5. Tech Stack Implications

`.product-forge/config.yml` pre-commits the stack: `React + FastAPI + MongoDB`. Domain is `content platform / social`. These choices have non-trivial downstream consequences.

### Frontend (React)

**Open decisions for Phase 5:**

- **SPA vs SSR.** A social-first content platform benefits from SSR for share-link unfurling (`og:image`, album art, review previews) and SEO. Recommend Next.js (App Router) for the MVP — gives SSR, image optimization, route-level code-splitting, and a built-in API layer for the few endpoints that don't need to hit FastAPI directly. Pure SPA (Vite + React Router) is a viable lighter-weight alternative.
- **State management.** TanStack Query for server state (read-heavy app), Zustand or React Context for local UI state. Redux is overkill at MVP scale.
- **Styling.** Tailwind + a component library (shadcn/ui or Radix primitives) is the default for fast UI iteration.
- **Type system.** TypeScript end-to-end — Pydantic models on the backend can be auto-generated into TS types via `openapi-typescript`.

### Backend (FastAPI)

**Open decisions for Phase 5:**

- **Sync vs async.** FastAPI is async-native; the workload (HTTP I/O to Spotify, Mongo I/O) is I/O-bound — async is correct. Use `motor` (async MongoDB driver) over `pymongo`.
- **Monolith vs modular.** MVP should be a modular monolith: one FastAPI app, one deployment unit, organised by domain modules (see §6).
- **Pydantic v2.** Standard for FastAPI ≥0.100. Pydantic models double as Mongo document schemas with `model_dump()`.
- **Background work.** Likely needed for Spotify listening-history sync (per-user polling) and reverse-feed precomputation. Recommend `arq` or `Celery` only if needed; for MVP, a simple APScheduler in-process job runner may suffice. Decision deferred to Phase 5.

### Data (MongoDB)

**Open decisions for Phase 5:**

- **Document modelling.** See §8 — denormalization choices for feeds and social graph are load-bearing.
- **Hosted vs self.** MongoDB Atlas free tier is the path of least resistance for an MVP.
- **Indexes.** Will need compound indexes on `(user_id, created_at)` for feeds, `(album_id)` for review aggregates, text index for review search if in scope.

### Auth — TBD, flag for Phase 5

The problem statement and hypothesis H4 imply Spotify OAuth is on the critical path. The natural choice: **Spotify OAuth 2.0 as the primary auth provider** (it also unlocks listening history and library reads in one consent flow). Implications:

- No separate password store needed at MVP.
- Account linking story for Apple Music users becomes complex if/when added (Spotify-as-identity ≠ Apple-as-identity).
- Email fallback may still be needed for transactional comms — decide in Phase 5 whether to capture email at OAuth.

Recommend a tiny auth abstraction (Spotify provider + a pluggable second provider) rather than hardcoding Spotify everywhere.

### Music metadata — TBD, flag for Phase 5

Two paths, with very different cost/control profiles:

| Approach | Pros | Cons |
|---|---|---|
| **Spotify-as-truth (catalog passthrough)** | No catalog of our own; consistent IDs and art with the user's player; rate-limited but free | Total dependency on Spotify; some albums missing or regionally variant; can't natively support Apple-only users |
| **Internal catalog cache (MusicBrainz/Discogs core + Spotify enrichment)** | Independence; richer metadata (credits, alternative releases); enables Apple Music integration later | Significant data plumbing; duplicate-release/edition normalization is a known hard problem (see Phase 0 risk #5) |

Recommendation for MVP: **hybrid — Spotify IDs as canonical, MusicBrainz as fallback when Spotify lacks a release.** Decide formally in Phase 5.

---

## 6. Likely Module Layout (Greenfield Proposal)

This is a **proposal for Phase 5**, not a discovered structure.

### FastAPI (`backend/` or `apps/api/`)

```
app/
  main.py                     # FastAPI app factory + middleware wiring
  config.py                   # Pydantic-settings env loader
  core/
    auth/                     # Spotify OAuth flow, session/JWT mgmt
    db/                       # Motor client + index management
    integrations/             # Spotify, Apple, MusicBrainz adapters with resilience
    observability/            # logging, tracing, metrics
  modules/
    users/                    # profile, settings, follows-out/-in
    albums/                   # canonical album resource + metadata aggregation
    ratings/                  # 1-5 (or 1-10) star + half-star
    reviews/                  # long-form review text + reactions
    listens/                  # listening history sync + entries
    backlog/                  # to-listen list
    social/                   # follow graph, mutual-follows, feed reads
    discovery/                # friend-graph recommendations, trending
    notifications/            # in-app + email triggers (later)
  workers/
    spotify_sync.py           # periodic listen-history pull
  schemas/                    # Pydantic request/response models
  tests/
    unit/  contract/  integration/
```

### React (`frontend/` or `apps/web/`)

```
src/
  app/                        # (if Next.js) routes / layouts
  features/
    auth/
    profile/
    album/                    # album page (header, ratings, reviews)
    review/                   # compose, view, react
    feed/                     # home feed
    backlog/
    search/
    social/                   # followers/following lists
    discover/
  components/                 # shared design-system components
  lib/
    api/                      # generated OpenAPI client
    state/                    # zustand stores
  styles/
```

Phase 5 must pick definitively between two-folder (`backend/` + `frontend/`) and monorepo (`apps/api`, `apps/web`, `packages/shared`). Recommend monorepo with pnpm workspaces if Next.js is selected — enables shared TypeScript types.

---

## 7. Reusable Existing Code

| Component/Service | Location | How to Reuse |
|---|---|---|
| *(none)* | N/A | Greenfield — Phase 5 establishes all primitives |

---

## 8. Reference Implementations (Similar Features)

| Feature | Location | Key Pattern |
|---|---|---|
| *(none)* | N/A | First feature in repo. Phase 5 sets reference patterns for future features. |

---

## 9. Integration Points

External systems auxd must talk to (none internal — greenfield).

| Layer | System | Change Type | Description |
|---|---|---|---|
| Auth + Catalog | **Spotify Web API** | New integration | OAuth login, profile, listening history, library, album/track metadata. Load-bearing per problem statement. |
| Catalog (optional later) | **Apple Music API** | Future | Mirror of Spotify integration for Apple users. Decide MVP inclusion in Phase 5. |
| Metadata fallback | **MusicBrainz** (and/or Discogs) | New integration | Album metadata when Spotify lacks a release; canonical release-group IDs to dedupe deluxe/remasters. |
| Auth (provider) | **Spotify OAuth 2.0** | New integration | Primary identity provider. |
| Email (transactional) | TBD (Postmark / SES / Resend) | New integration | Magic-link fallback, notifications. Pick in Phase 5. |
| Storage (images) | **Spotify CDN passthrough** | New integration | Reuse Spotify's hosted album art via the URLs Spotify returns. Self-hosted only if catalog moves off Spotify. |
| Analytics | TBD (PostHog / Amplitude / NewRelic Browser) | New integration | Wire in alongside tracking-plan phase. |
| Hosting | TBD (Vercel for web, Fly.io / Railway / Render for FastAPI, MongoDB Atlas) | New integration | Pick in Phase 5. |

---

## 10. Codebase Constraints

Greenfield — there are no constraints discovered in the codebase. Constraints below are **placeholders** that Phase 5 must turn into ratified entries (either in the constitution or as ADRs).

| Constraint | Source | Impact on Feature Design |
|---|---|---|
| *(none discovered)* | N/A — greenfield; established in Phase 5 | Plan must (a) ratify a constitution or (b) record initial ADRs covering: external-call resilience, MongoDB schema versioning, structured logging, request-IDs, secret management, naming conventions for collections/routes. |

**Specific items Phase 5 must decide and record:**

1. Resilience policy for outbound HTTP (retries, timeouts, circuit breakers around Spotify/Apple/MusicBrainz).
2. ID strategy — Spotify IDs as canonical vs internal UUIDs with Spotify-ID as secondary.
3. Mongo collection naming and `schema_version` policy.
4. Auth session model — opaque session token vs JWT, refresh strategy for Spotify tokens.
5. CORS, CSRF, and same-site cookie policy across the React/FastAPI split.
6. Rate-limiting policy at the API edge.
7. Secrets management (env vars + a secrets manager such as Doppler, AWS SM, or 1Password Secrets Automation).

---

## 11. Event / Message Patterns

**N/A — no EDA patterns detected (no codebase).**

MVP scale (a few thousand users) should not require an event bus. Likely-needed asynchronous workflows can be served by background jobs in-process or a single Redis-backed queue:

- Spotify listening-history poll per user (scheduled).
- Review-posted → follower-feed precomputation (fan-out-on-write OR fan-out-on-read; decide in Phase 5).
- Notification dispatch (in-app + email).

Phase 5 should explicitly call out *not* introducing Kafka/RabbitMQ/SQS at MVP — defer until traffic or feature requirements demand it.

---

## 12. Data Model Impact

High-level proposed MongoDB collections (Phase 5 will finalise; document modelling and denormalization are the load-bearing decisions).

| Collection | Purpose | Key fields | Denormalization notes |
|---|---|---|---|
| `users` | Identity, profile, settings | `_id`, `spotify_id`, `display_name`, `handle`, `avatar_url`, `bio`, `joined_at`, `counts.{followers,following,reviews,ratings}` | Counts denormalized for cheap profile reads; rebuild via background job. |
| `albums` | Canonical album resource | `_id` (Spotify ID or internal UUID), `title`, `artist_ids[]`, `release_date`, `total_tracks`, `cover_url`, `external_ids.{spotify,musicbrainz,apple}` | Cache subset of Spotify metadata; refresh on access if stale. |
| `artists` | Canonical artist resource | `_id`, `name`, `external_ids` | Optional MVP — could be embedded into `albums.artists[]` instead. |
| `ratings` | User rating of an album (one per user/album) | `user_id`, `album_id`, `score`, `created_at`, `updated_at` | Unique compound key `(user_id, album_id)`. |
| `reviews` | Long-form review | `_id`, `user_id`, `album_id`, `rating` (denormalized snapshot), `body`, `created_at`, `reactions.counts` | Review text + reaction counts denormalized for fast feed reads. |
| `listens` | Listening history entries from Spotify | `user_id`, `album_id`, `track_id`, `played_at`, `source` | High write volume; consider TTL or aggregation rollup. |
| `backlog` | "to-listen" list | `user_id`, `album_id`, `added_at`, `note` | Unique `(user_id, album_id)`. |
| `follows` | Social edges | `follower_id`, `followee_id`, `created_at` | Compound index on both directions. |
| `feed_entries` *(optional)* | Precomputed home feed | `user_id`, `entry_type`, `payload`, `created_at` | Only if fan-out-on-write chosen for feeds. |
| `notifications` | In-app notifications | `user_id`, `kind`, `payload`, `read_at` | Standard inbox pattern. |

**Decisions with the largest cost-of-being-wrong:**

1. **Feed strategy: fan-out-on-write vs fan-out-on-read.** Fan-out-on-write is simpler at low scale and is the recommended MVP default. Document the decision so it can be revisited at scale.
2. **Whether to model `artists` as a separate collection.** Embedding inside `albums` is cheaper for MVP; extraction can be deferred until artist pages are built.
3. **Listening-history granularity.** Per-track vs per-listen-session aggregation. Per-track is faithful to Spotify's data and simplest; aggregation is a later optimisation.

---

## 13. Technical Complexity

- **Overall:** **High** — greenfield MVP with multiple external integrations, social-graph semantics, and a Spotify-dependent critical path.
- **Backend complexity:** Medium-High — modular monolith, async I/O, OAuth + token refresh, periodic background sync, resilience boundary around three external services.
- **Frontend complexity:** Medium — five-to-eight primary surfaces (feed, album, profile, search, compose-review, backlog, social lists, settings), real-time-ish updates not strictly required for MVP.
- **Integration complexity:** High — Spotify OAuth + Web API consent scoping, rate limiting, token refresh races; MusicBrainz mapping and edition deduplication; optional Apple Music adds another full integration.
- **Data complexity:** Medium — straightforward documents, but feed strategy and album-identity normalization are real decisions.
- **New modules:** all of them — backend domain modules listed in §6 and frontend feature folders.
- **Breaking change risk:** N/A (no existing API to break). Forward-compatibility risk is medium — Spotify is the single point of failure; abstract it behind an integration interface.
- **Estimated touch points:** Phase 5 should plan for ~80–150 files across backend + frontend at MVP. Phase 5B (tasks) will refine.

---

## 14. Current Tech Capabilities

The project already supports:

- **Spec Kit lifecycle automation** — `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, etc., with Git hooks pre-wired for every transition.
- **Product Forge orchestration** — research, product-spec, revalidation, bridge, plan, tasks, pre-impl review, implement, code-review, verify-full, test-plan, test-run, release-readiness, retrospective, plus cross-cutting sync-verify / change-request / portfolio commands.
- **V-Model artifact generation** — optional path to IEEE/ISO-grade artifacts and a traceability matrix if the feature is ever promoted to `feature_mode: v-model`.
- **Sequential branch naming** (`001-auxd-mvp`, etc.) with auto-commit hooks before/after each Spec Kit phase.

The project does **not** yet support: building, testing, linting, packaging, deploying, or running any code. Those capabilities are first introduced by the Phase 5 plan.

---

## 15. Implementation Guidance (key decisions for Phase 5)

1. **Foundation comes before features.** The plan must front-load a "Task 0 / Phase 0" of infrastructure work: repo skeleton (FastAPI app factory, MongoDB connector, settings loader, logging baseline), React app skeleton (chosen framework, routing, design-system primitives, OpenAPI client generation), CI baseline (lint + tests + type-check), and Spotify OAuth happy-path. Without this, every feature task ends up reinventing primitives. Recommend this be the single biggest discrete chunk of plan effort.

2. **Constitution before plan, or constitution as Task 0.** Either run `/speckit-constitution` to ratify a minimum set of principles before `/speckit-plan`, or include constitution ratification as the first plan task. Otherwise the plan's Constitution Check gate is vacuous and downstream phases lose their compliance hook. Recommend the former: it's a 30-minute investment that unlocks the rest of the lifecycle.

3. **Decide the Spotify-only vs multi-provider boundary at Phase 5, not later.** Spotify-as-identity, Spotify-as-catalog, and Spotify-as-listening-source can all be the same integration at MVP (single OAuth flow). Decide explicitly whether (a) Apple Music is in scope for the MVP, (b) MusicBrainz is the metadata fallback or the primary catalog, and (c) whether listening-history is mandatory or optional for first-launch. Each of these choices fans out to ~10–20 plan tasks; the cost of late reversal is high.

---

## Summary

auxd is a greenfield React + FastAPI + MongoDB project with no application code and a constitution that is still the unfilled template. The Spec Kit + Product Forge + V-Model + Git scaffolding is complete and fully wired with automation hooks, and Phase 0 (problem discovery) is approved. Phase 5 (plan) must (1) ratify a minimum constitution, (2) front-load foundational infrastructure tasks before any feature work, and (3) lock the Spotify-only vs multi-provider boundary before the task breakdown is generated. External integration risk (Spotify dependency) and album-identity normalization are the top non-obvious risks already visible from the scaffolding alone.
