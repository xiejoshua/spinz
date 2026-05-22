# Plan — Digest

> **Feature:** 001-auxd-mvp
> **Phase:** plan
> **Generated at:** 2026-05-22T00:25:00Z
> **Artifact owner:** speckit.product-forge.plan

## Key decisions

- **Repository topology:** pnpm monorepo with `apps/api` (FastAPI) + `apps/web` (Next.js 15) + `packages/shared-types` (TS from OpenAPI). Deploys independently (Vercel for web, Fly.io for api).
- **Backend stack confirmed:** FastAPI async + Pydantic v2 + Beanie ODM + Authlib (custom session cookies, no JWT) + arq/Redis (background jobs) + `httpx.AsyncClient` with resilience transport.
- **Frontend stack confirmed:** Next.js 15 App Router (SSR for album-detail OG + SEO) + TanStack Query + Zustand + shadcn/ui + Vitest + Playwright.
- **Data layer locked:** MongoDB Atlas (M0 shared at MVP, M10 at WAL ~3k) + Atlas Search + Upstash Redis. KSUID IDs, `_schema_version` on every doc, single `lib/visibility.can_read()` source of truth for all visibility checks.
- **Provider abstraction:** `MusicProvider` protocol + `CatalogProvider` protocol; Spotify and MusicBrainz are concrete implementations; the interface deliberately omits deprecated Spotify endpoints (audio-features, recs, related-artists removed 2024-11-27).
- **Feed strategy:** Fan-out-on-read at MVP with weighted score (reviews +20%, extreme ratings +15%, top-5-interacted +10%, recency half-life ~3 days); switch criteria to fan-out-on-write documented (>200ms p95 trigger).
- **Notification dispatcher:** dedicated dispatcher + coalescer + per-channel adapters (InApp / Email via Postmark / WebPush via VAPID) + Redis-backed rate limiter (≤5/hr, ≤25/day per user; per-actor coalescing ≤3/24h). Anti-firehose by design.
- **Just-finished detection:** arq scheduled per-user polling against Spotify recently-played; cadence 5–15min based on activity; heuristic = ≥4 tracks from same album in 1h; lifecycle pending→logged/dismissed/expired with 24h TTL.
- **Hosting:** Fly.io (single region sjc, multi-region post-M3) for api + arq worker; Vercel for web; domain `TBD.app`.
- **Two Phase 5B prerequisite tasks (Task 0 and Task 1):** ratify the 6-principle constitution; submit Spotify Extended Quota Mode application Day 1 (parallel work, 2–6 week external review window).

## Artifacts produced

- `plan.md` — 22-section technical blueprint (~6,500 words).
- `plan/digest.md` — this file.

## Open risks

- **Spotify Extended Quota Mode timing.** 2–6 week external review; M0–M2 must operate inside Development Mode quotas. Mitigation: closed-beta + soft launch waves inside dev quotas; production-tier only needed for public M0.
- **Feed performance unknown until live.** Fan-out-on-read is the MVP choice but not load-tested at scale; weekly PostHog dashboard "p95 home feed load" with alert at 200ms triggers the fan-out-on-write switch documented in §10.3.
- **Just-finished detection heuristic accuracy.** ≥4-tracks-in-1h is a reasonable proxy for "album finished" but unverified. Mitigation: user can dismiss per-album (30d sticky) and disable globally — false-positive damage is bounded.
- **Atlas Search index quality tuning.** Spotify search fallback merge mitigates cold-catalog gaps; post-launch tuning based on PostHog `search.executed.result_count` distribution.
- **Self-hosted PostHog operational risk.** Single Fly container is cheap but operationally fragile; documented fallback to PostHog Cloud if it goes flaky.
- **MongoDB M0 free tier limits.** Sized for M3 target (~500 WAL); upgrade trigger documented at WAL ~3k.

## Handoff notes for next phase

- **Phase 5B (tasks.md) should generate ~80–120 tasks** following the Phase M-2 build order in plan §18. Front-load Tasks 0–5 (constitution, Extended Quota Mode, monorepo scaffold, infra provisioning, CI baseline, healthz) BEFORE any feature work.
- **Module-by-module sequencing exists in §6 + §18.** Tasks can parallelize within a module but the build order across modules respects dependency chains (auth → albums → diary → reviews → social → feed → search → notifications → prompts → onboarding → seeding → moderation → gdpr).
- **NFR Measurement Contract (§15)** instrumentation is woven through every module; tasks.md should NOT separate "build the feature" from "instrument the feature" — they're the same task. Constitution Principle 5 (Observability mandatory) makes this non-negotiable.
- **Contract tests (§16.3) for Spotify + MusicBrainz are gating** — Principle 4 says tests-first for catalog/auth edges, so the Spotify provider task chain is contract-test-first.
- **The 6-principle constitution is the architecture's load-bearing contract** — every module that violates a principle should be flagged in code review (Phase 6B). Phase 5B should reference principles in task descriptions where relevant.
- **Lists work must NOT appear in tasks.md.** Lists were elevated in R1 and reverted to v2 in R3. The plan correctly omits them; tasks.md should too.
- **The Aux (🏅) vs Like (👍) split must be preserved in implementation.** Don't let a well-meaning task collapse them — they're distinct data fields, distinct UI icons, distinct notification types.
- **Phase 5.5 (Migration Plan)** will trigger after tasks.md because the data model has a non-empty "Data Model" section (per plan §3). For greenfield, the "migration" is the initial schema setup; for downstream changes it's the standard schema-versioned migration pattern from Constitution Principle 2.
