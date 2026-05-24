# Phase 7 (Verify Full) — Digest

> Feature: `001-auxd-mvp` | Generated: 2026-05-24 | HEAD: `ad4a8ef`

## Key decisions

- **Overall verdict: PASS WITH WARNINGS** (no CRITICAL, 4 WARNING, 38 PASSED across 6 layers).
- **Drivers for the verdict:**
  - Phase 6B HIGH-clean baseline held: all 10 fixes (REV-001/002/003/100/101/120/126/200/201/202) verified on disk.
  - CR-001 (Spotify pivot) fully honored — zero production code references; `MusicProvider` Protocol kept for v2 forward-compat with no impls.
  - T173 CSRF wiring (api-client.ts cookie→header lift + CORS allow_headers + SessionMiddleware enforcement) closed pre-launch; would have 403'd every authenticated mutation in prod otherwise.
  - All 30 Must-Have user stories in scope at MVP backed by `[x]` task + on-disk code + test evidence.
  - Plan §3.1 21-collection inventory exactly matches `ALL_DOCUMENT_MODELS` in `db.py`.
  - All 11 expected operator runbooks present + cross-linked from launch-checklist.md.

## Artifacts produced

- [verify-report.md](../verify-report.md) — full 6-layer verification with traceability matrix
- This digest

## Open risks (WARNING-level, acknowledged but not fixed)

- **W1 / W2** — `T101a` + `T113` checkbox-hygiene gap: both task IDs still `[ ]` despite functional coverage shipped via T148 (W1) and T053+T061 (W2). No feature impact; tasks.md polish optional. Defer to release-readiness.
- **W3** — `T169` (Pull-more-history) explicitly DEFERRED-TO-V2 per CR-001 (depends on deferred listening-history primary). Tracked for v2 re-anchor.
- **W4** — 7 structural drift carry-forwards from sync-verify Run #13 (lowest count since Run #2). All dispositioned cosmetic, pre-existing. Re-check at Phase 9 (release readiness).

## Handoff notes

**For Phase 8 (Test Plan + Test Run):**
- 9 MVP-active TC-E2E specs (002/003/005/006/007/010/011/012/013) at `apps/web/tests/e2e/` are gated behind `E2E_BACKEND_REACHABLE` — Test Plan should pin this env var rule explicitly and document the backend reachability check for CI.
- 4 CR-001-deferred TC-E2E specs (001/004/008/009) ship as explicit-skip with DEFERRED-TO-V2 rationale; Test Plan should record them as "not in MVP scope" but keep the spec files for v2.
- 23 a11y routes covered by `tests/a11y/` (auth/onboarding/app/settings/standalone) — re-run pre-launch with `--update-snapshots` opt-out and confirm 0 CRITICAL after any UI churn.
- 4 k6 perf scripts at `apps/api/tests/perf/k6_{baseline,unread_count,feed_home,search}.js` are operator-driven (not CI). Test Plan needs to schedule manual perf runs against staging (T175) before launch ceremony (T180).
- 3 CSRF regression tests at `apps/api/tests/integration/test_csrf_*.py` are the canonical pre-flight for the T173 fix — must stay green on every PR touching auth/middleware code.

**For Phase 9 (Release Readiness):**
- launch-checklist.md (T179) is the 11-section gate doc — Phase 9 should re-tick each section against current state.
- Confirm Phase 6B HIGH-clean still holds at PR-merge time (no regression between Phase 7 and the actual cut).
- Verify CR-001 Spotify-absence one more time at cut: `grep -rn "import spotify\|SpotifyProvider\|SPOTIFY_CLIENT_ID" apps/api/src apps/web/src` must return zero hits.
- Cross-check that the 4 deferred TC-E2E specs (001/004/008/009) remain explicit-skip and the 9 MVP-active TC-E2E specs pass against staging.
- The `T101a`/`T113`/`T169` open-checkbox status is dispositioned: do NOT close them at release-readiness — they're truthful "deferred" markers for audit.

**For Phase 9.5 (Monitoring Setup) if invoked:**
- PostHog dashboard schema at `apps/api/src/auxd_api/modules/notifications/posthog_dashboard.yml` (T144) already defines `notification.dispatched` event + p95>12 alert threshold.
- Synthetic monitor at `.github/workflows/synthetic.yml` (T010) hits `/healthz` every 15min with Discord webhook on failure.
- Other dashboards (signup→onboarding→first-log funnel + WAL + retention cohort + push opt-in rate + notification rate-per-user-per-week + wedge time) are listed in `docs/closed-beta-runbook.md` — operator-curated against PostHog Cloud UI; Phase 9.5 could codify them as JSON.
