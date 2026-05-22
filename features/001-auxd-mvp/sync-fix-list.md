# Phase 6 Fix List — Drift Backlog from Sync-Verify Run #1

> Feature: `001-auxd-mvp` | Generated: 2026-05-21 | Source: [sync-report.md](./sync-report.md)
> Owner: Phase 6 implementation lead | Status: open

This file captures **plan-level drift items** that were not auto-fixed during sync-verify
because they require new plan sections, new tasks, or new collections rather than
small surgical edits. They are documented work — implementation should pick them up
during Phase 6 as **plan-update PRs** (small) and **task additions** in `tasks.md`.

Two items are explicitly **DEFERRED** (not on the Phase 6 critical path).

---

## How to use this file

1. Treat each item as a **plan/tasks amendment** to apply before or alongside the
   coding work it gates.
2. When you apply an item: edit the relevant section of `plan.md` or `tasks.md`,
   then check the box below and add a short note (commit SHA / PR link).
3. When all non-DEFERRED items are checked, re-run `/speckit.product-forge.sync-verify`
   to confirm zero structural drift before code review (Phase 6B).

---

## Active backlog (10 items — apply during Phase 6)

### Plan additions (8 items)

- [x] **L3-001 — Endpoint rate-limiting in plan §4 or §6**
      Add: HTTP endpoint rate-limiting (per-IP / per-user) on POST `/diary`, `/follow`,
      `/reviews`, `/reviews/{id}/like` via `lib/rate_limit.endpoint(...)` Redis
      token-bucket. Fail-open same policy as §1.1.1.
      Source: spec.md §6 NFR Security ("rate limiting on log/follow/review/like endpoints").
      Also add a task in §1 cluster of tasks.md ("Endpoint rate-limit middleware").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L3-002 — Follow-request queue (Must-Have US-G2 infrastructure)**
      Add to plan.md §3.1: `follow_requests` collection OR `Follow.state` enum
      (pending / accepted / declined). Add to §6 social module: `request_follow`,
      `respond_to_follow_request` services. Add task in §10 social cluster.
      Source: spec.md US-G2 ("private-profile toggle creates pending follow-requests queue").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L3-003 — Review edit history collection (FR-030 90d audit)**
      Add to plan.md §3.1: `review_edit_history` collection
      `(review_id, version, body_at_time, edited_at, edited_by)` with TTL 90d.
      Update §6 `reviews.edit_review` to write a history row on every edit.
      Add task in §8 reviews cluster.
      Source: spec.md FR-030 ("90-day internal audit log preserved").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L3-004 — Accessibility CI gate (axe-core)**
      Add to plan.md §16.4 (CI workflow): `@axe-core/playwright` run against
      built pages with 0-violations gate. Per-screen audit checklist in §16.2
      or new §16.5.
      Source: spec.md §6 NFR Accessibility + §6.1 NFR Measurement Contract
      ("axe-core automated audit + manual keyboard nav test \| Per-screen audit
      on every release \| 0 violations").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L3-006 — "Report missing album" path (FR-005, US-F2)**
      Extend plan §13.1 `reports.target_type` enum to include `missing_album`
      (or add a separate `album_requests` collection). Reference from §11
      (Search Architecture). Add task in §6 albums/search cluster.
      Source: spec.md US-F2 + FR-005 ("'Report missing album' link on empty result").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L3-007 — Settings → Integrations route + disconnect/back-fill services (FR-027)**
      Add to plan §1.2 file tree: `app/(app)/settings/integrations/` route.
      Add to plan §6 auth (or new `integrations` module): `disconnect_spotify`,
      `trigger_diary_backfill` services. Add explicit note re: diary-intact-on-disconnect.
      Add task in §14 profile/settings cluster.
      Source: spec.md FR-027 ("Settings → Integrations: Spotify status, back-fill
      diary trigger, immutability on disconnect").
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L4-003 — T135 PostMark failure-mode wiring**
      Amend T135 description in tasks.md to include: retry with exponential
      backoff (3 attempts); on final failure log to `failed_emails` collection;
      Sentry alert tag `email.send_failed`. Add `failed_emails` to either T026
      (Notifications models) or as a sibling Beanie Document model task.
      Source: plan.md §1.1.1 PostMark row.
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L4-004 — Redis cache + arq fail-mode policy in tasks**
      Expand T013 (Redis connection) or add a small task: "Wire Redis fail-mode
      semantics — cache FAIL OPEN with `cache.redis_down` Sentry tag;
      arq-enqueue endpoints FAIL CLOSED returning 503 with `jobs.redis_down`.
      Apply to GDPR export and other job-enqueue surfaces."
      Source: plan.md §1.1.1 (Redis cache + Redis arq job queue rows).
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

### Task additions (2 items)

- [x] **L4-001 — OpenTelemetry instrumentation task**
      Add to tasks.md §1 (size XS): "OpenTelemetry instrumentation — install
      OTel SDK + FastAPI/httpx/Beanie auto-instrumentors; configure span exporter
      to Fly logs." Deps: T011, T015. Refs: Constitution P5; plan §15.4; NFR Observability.
      Source: plan.md §15.4 (OTel SDK described but no task).
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

- [x] **L4-002 — Nightly mongodump backup task**
      Add to tasks.md §0 (Prereqs) or §18 (Pre-launch hardening; size XS-S):
      "Nightly mongodump backup to S3 (M0 manual backups, $1/mo) — cron job
      with retention policy." Deps: T005, T007. Refs: plan §17.4; NFR availability/durability.
      Source: plan.md §17.4 (mongodump strategy described but no task).
      Resolution note: Applied 2026-05-22 during Phase 6 setup (pre-implementation).

---

## Deferred (2 items — not on Phase 6 critical path)

- [ ] **L3-005 — i18n key extraction strategy**
      Status: DEFERRED. Project status has `i18n_harvest: not_applicable`
      (English-only at MVP). The strategy section in plan.md can be added
      if/when the `speckit-product-forge-i18n-harvest` skill is invoked later.
      Not blocking Phase 6.
      Source: spec.md §6 NFR i18n/l10n ("English-only at MVP; copy strings extracted to keys").

- [ ] **L3-008 — Last.fm provider scaffolding (Should-Have FR-017)**
      Status: DEFERRED. FR-017 is Should-Have, not Must-Have. The enum
      placeholder (`DiaryEntrySource.LASTFM_IMPORT`) is already reserved.
      Add a one-line forward-pointer to plan §5.4 when FR-017 work is scheduled.
      Source: spec.md FR-017 ("Last.fm history import as Spotify alternative").

---

## Notes from Run #1

- All 4 pre-impl-review locks (C-1 T117a, C-3 feed weighting, C-4 coalescer cross-type,
  C-5 rate-limiter fail-open) were verified present and correct.
- Lists deferral (R3 reversion) was applied cleanly to spec.md, plan.md, and tasks.md.
  One residual "Lists" mention in product-spec was cleaned in this run (DRIFT-L2-008).
- Aux/Like semantic split (R3) is correctly bridged. One stale "hearted" label
  in spec.md was cleaned in this run (DRIFT-L2-002).
- Story count claim reconciled to 30 across spec.md, product-spec/user-stories.md,
  and product-spec/digest.md (DRIFT-L2-003).
- Task T117a Refs corrected to cite A-005 (canonical architecture finding ID),
  not A-009 (DRIFT-L4-006).
- 14 INFO items were intentionally skipped — see [sync-report.md](./sync-report.md)
  for the full advisory list.

When all 10 active items are checked, the structural drift count is expected to
drop from 27 to 0 on the next sync-verify run, satisfying the strict
`structural: 0` drift budget.
