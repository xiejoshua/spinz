# Tasks — Digest

> **Feature:** 001-spinz-mvp
> **Phase:** tasks
> **Generated at:** 2026-05-22T00:50:00Z
> **Artifact owner:** speckit.product-forge.tasks

## Key decisions

- **180 tasks total** across 18 clusters (§0 Prereqs through §18 Hardening), dependency-ordered per plan §18 build order.
- **Task IDs T001–T180 are unique and contiguous;** no gaps, no duplicates (validated).
- **Front-loading is strict:** T001 (constitution ratification) and T002 (Spotify Extended Quota Mode application) block all feature work. T002 runs in parallel with subsequent tasks because of the 2–6 week external review window.
- **Constitution Principle 4 enforced in sequencing:** T042 (Spotify contract tests, expected-fail state) precedes T043 (Spotify provider implementation). Same for T048 → T049 (MusicBrainz). This is test-first-for-catalog-edges, baked into the task order.
- **Constitution Principle 5 enforced:** observability is not a separate cluster — instrumentation (PostHog events, structured logs, Sentry) is woven into every relevant task. T015 builds the lib; tasks throughout call it.
- **Sizing distribution:** roughly 60% Small/Medium, 25% Extra-Small, 12% Large, 3% Extra-Large flagged for decomposition (T043 Spotify provider impl, T077 Log sheet, T106 Home feed, T123 Spotify polling worker, T131 Notification dispatcher, T138 Weekly digest, T153 GDPR export, T174 E2E suite, T178 Design polish, T104 Suggested-follow precompute). XL tasks should be split further in Phase 6 if they prove unwieldy.
- **Parallel-track opportunities documented** — once auth is done, three engineers can split across Reviews + Backlog + Social clusters; Onboarding + Feed can largely parallel each other.
- **Lists are deliberately ABSENT** — no tasks for Lists per R3 deferral (out-of-scope.md + decision-log row 7 confirm v2).
- **Award (🏅) vs Like (👍) semantic split is preserved in tasks** — T023 separates fields (DiaryEntry.awarded vs ReviewLike), T073 implements Award on diary, T088 implements Like on review, T090 distinguishes icons in UI.

## Artifacts produced

- `tasks.md` — 180-task breakdown (~6,500 words) with full coverage matrix, parallel-track guidance, and constitution + NFR coverage summary.
- `tasks/digest.md` — this file.

## Open risks

- **XL-sized tasks may need decomposition during Phase 6.** Flagged candidates: T043 (Spotify provider — many sub-methods); T077 (Log sheet — frontend wedge with deep interaction polish); T106 (Home feed — query + UI + weighting math); T123 (polling worker — cadence rules + many edge cases); T131 (notification dispatcher); T138 (weekly digest — per-tz cron); T153 (GDPR export); T174 (E2E suite); T178 (design polish — open-ended). Each is sized L/XL with the intent that they may split into 2–3 tasks at implementation time.
- **Task 0 (constitution) is a true blocker.** If founder doesn't ratify constitution promptly, NO feature tasks can begin. Recommend ratifying same-day as Phase 5B approval to unblock Phase 6 immediately.
- **Task 1 (Spotify Extended Quota Mode application) is a 2–6 week external dependency.** Submit Day 1 of Phase 6; closed-beta and soft-launch waves operate inside Development Mode quotas as the fallback.
- **Atlas Search index tuning quality** unknown until production data exists. T068 sets the initial index; iterate post-launch based on PostHog `search.executed.result_count` distribution.
- **Just-finished detection heuristic** (≥4 tracks from same album in 1h) is a reasonable proxy but unvalidated. T124 implements; verify accuracy with closed-beta users + dismiss-rate analytics from T130.
- **Frontend testing coverage at MVP** is modest (smoke + critical-flow E2E). Full E2E suite (TC-E2E-001..013) is T174 — should not be deferred past M-1 soft launch.
- **Founder bandwidth on critic-seed recruitment** (referenced in T162 + T166) is a non-engineering bottleneck. Tasks document the workflow but execution requires founder time.

## Handoff notes for next phase

- **Phase 5.5 (Migration Plan) MUST run next** — plan §3 has a Data Model section (15 entities + indexes + Atlas Search index), so the conditional trigger fires. For greenfield, "migration" = initial collection creation + Atlas Search index application + reserved-handles seed; no rollback needed for first-version creation, but the migration plan should establish the schema-versioned pattern (Constitution Principle 2) for all future changes.
- **Phase 5C (Pre-Impl Review) is recommended** — 180 tasks with significant external dependencies (Spotify, MusicBrainz, Atlas Search, web push) and a load-bearing wedge (Log sheet <8s). Pre-impl review would catch ordering / dependency mistakes before they cost a sprint.
- **Phase 6 (Implement) should start with Tasks T001–T010 (Prereqs)** before splitting into parallel tracks. Founder controls T001 + T002 ratification timing.
- **Progressive verify interval (per .product-forge/config.yml) = 3 tasks.** Every 3 completed tasks, the orchestrator should pull a quick verify checkpoint. With 180 tasks, that's ~60 checkpoints — sufficient density for early-bug-catch without overwhelming.
- **Recommended commit granularity:** one commit per task (180 commits over the build). Each commit message references the task ID + the US/FR it implements (e.g., `feat(diary): log entry endpoint (T073, US-B1, FR-004)`).
- **Tasks are dependency-ordered but parallelizable per the §Parallel-track opportunities table** — Phase 6 implementation can fan out 2–3 engineers once T030 (backend foundation) and T040 (frontend foundation) complete.
- **Constitution Principle 4 (test-first for catalog/auth) MUST be honored** — T042 and T048 are not optional preludes; they're load-bearing for catching Spotify/MusicBrainz API drift early.
- **Award vs Like distinction MUST be preserved in implementation** — flag any code-review PR that collapses them. The data model, notifications, and UI icons must stay distinct.
- **Lists must NOT appear in any task during Phase 6** — if a task or PR adds Lists, reject as scope creep (per R3 decision).
