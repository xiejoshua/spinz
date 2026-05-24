# Pre-Launch Checklist + Readiness Review (T179)

> Last reviewed: 2026-05-23 (Session 26).
> Lifecycle phase: §18 hardening complete; M0 launch ceremony (T180) on deck.
> Reviewer: Joshua Xie (founder, operator).

This is the consolidated "are we shippable?" gate. Every section
links to the canonical source document; this checklist gathers
sign-offs in one place.

## 1. Code quality gates

All gates must be GREEN immediately before T0 (launch ceremony):

| Gate | Command | Expected | Status (S26) |
|---|---|---|---|
| Backend ruff lint | `cd apps/api && uv run ruff check .` | All checks passed | ✅ |
| Backend ruff format | `cd apps/api && uv run ruff format --check .` | All files formatted | ✅ |
| Backend mypy strict | `cd apps/api && uv run mypy --strict src tests` | Success — no issues found in 203 source files | ✅ |
| Backend pytest | `cd apps/api && uv run pytest` | 964 passed, 3 skipped | ✅ |
| Frontend Biome | `cd apps/web && pnpm exec biome check .` | Checked 175 files. No fixes applied. | ✅ |
| Frontend typecheck | `cd apps/web && pnpm typecheck` | No output (tsc --noEmit clean) | ✅ |
| Frontend vitest | `cd apps/web && pnpm test:unit` | 81 passed | ✅ |
| Frontend next build | `cd apps/web && pnpm build` | 26 routes built (24 visible + 2 OG) | ✅ |
| Codegen (OpenAPI ↔ shared-types) | `.github/workflows/codegen.yml` | No drift | ✅ — last green in Run #12 |
| Broken markdown links | manual scan | 0 broken | ✅ |

## 2. Spec coverage

| Item | Source | Status |
|---|---|---|
| Sync-verify Run #N applied | `features/001-auxd-mvp/sync-report.{md,json}` | ✅ Run #12 applied (`applied_split_with_override`) |
| Structural budget | `sync-report.json` | ✅ 0 |
| Carry-forwards documented | `features/001-auxd-mvp/sync-fix-list.md` | ✅ all dispositioned |
| All Must-Have user stories covered by ≥1 task | `tasks.md` cross-check | ✅ (verify-full Run #12) |
| All functional requirements covered | `spec.md` ↔ `tasks.md` | ✅ |

## 3. Accessibility (T171)

| Check | Status |
|---|---|
| `docs/a11y-audit.md` authored | ✅ |
| `@axe-core/playwright` dev-dep installed | ✅ |
| Per-route specs at `apps/web/tests/a11y/*.spec.ts` | ✅ — 23 routes covered |
| 0 CRITICAL violations confirmed | ⚠️ pending operator run — gate enforced in spec assertions |

## 4. Performance (T172)

| Check | Status |
|---|---|
| `docs/perf-audit.md` authored | ✅ |
| k6 scripts shipped: baseline, unread_count, feed_home, search | ✅ — `apps/api/tests/perf/k6_*.js` |
| Lighthouse spec shipped | ✅ — `apps/web/tests/perf/lighthouse.spec.ts` |
| In-CI perf guards (T084 + T107) green | ✅ |
| Spec.md §6.1 NFR p95 thresholds | ⚠️ partial — pre-staging-deploy metrics marked "N/A pending T175 staging" |

## 5. Security (T173)

| Check | Status |
|---|---|
| `docs/security-review.md` authored | ✅ |
| 0 CRITICAL findings open | ✅ |
| 0 HIGH findings open | ✅ — A07 CSRF wiring fix applied this session |
| MEDIUM findings documented + mitigations recorded | ✅ — A05 CORS lint, A06 dependabot wiring (both LOW follow-ups) |

## 6. E2E coverage (T174)

| Check | Status |
|---|---|
| 13 TC-E2E-NNN spec files present | ✅ — `apps/web/tests/e2e/tc-e2e-{001..013}-*.spec.ts` |
| MVP-active scenarios (002, 003, 005, 006, 007, 010, 011, 012, 013) wired | ✅ |
| DEFERRED-TO-V2 scenarios (001, 004, 008, 009) explicitly skipped with CR-001 rationale | ✅ |
| Backend-required tests gated behind `E2E_BACKEND_REACHABLE` | ✅ |
| Form-validation-only paths runnable against dev server (no backend) | ✅ — TC-E2E-010 + TC-E2E-012 + TC-E2E-013 have UI-only variants |

## 7. Monitoring

| Check | Source | Status |
|---|---|---|
| Sentry init verified in prod | `apps/api/src/auxd_api/main.py:71` | ✅ |
| OTel init verified | `apps/api/src/auxd_api/main.py:76` | ✅ |
| PostHog dispatcher live | `apps/api/src/auxd_api/lib/observability.py` | ✅ |
| Discord moderation webhook configured | `apps/api/src/auxd_api/modules/moderation/service.py` | ✅ |
| Notification firehose alert (T144) wired | `apps/api/src/auxd_api/workers/notification_rate_alert.py` | ✅ |
| Rate-limit Redis-down warning | `apps/api/src/auxd_api/lib/rate_limit.py:80` | ✅ |
| PostHog dashboards bookmarked | `docs/closed-beta-runbook.md §3` | ✅ |

## 8. Runbooks

| Runbook | Path |
|---|---|
| Critic-seed | `docs/critic-seed-runbook.md` (T162) |
| Founder seed-content workflow | `docs/founder-workflows/seed-content.md` |
| Staging environment | `docs/staging.md` (T175) |
| Closed-beta wave | `docs/closed-beta-runbook.md` (T176) |
| Launch ceremony | `docs/launch.md` (T180) |
| Acknowledge report | `apps/api/scripts/acknowledge_report.py` (CLI) |
| Merge albums | (manual via `apps/api/scripts/` if/when needed) |
| Infrastructure | `docs/infra.md` |
| A11y audit | `docs/a11y-audit.md` (T171) |
| Perf audit | `docs/perf-audit.md` (T172) |
| Security review | `docs/security-review.md` (T173) |
| Design polish | `docs/design-polish-notes.md` (T178) |

## 9. Rollback plan

### Backend

- `flyctl releases list -a auxd-api` to identify the previous-good release.
- `flyctl releases rollback -a auxd-api <release-number>` to revert.
- Beanie migrations are mostly additive (`features/001-auxd-mvp/migrations/`). Forward-only migrations are flagged in the migration files. No forward-only migrations were shipped after the wave-1 deploy point.

### Frontend

- Vercel dashboard → Deployments → pick previous green → "Promote to Production".
- CLI alternative: `vercel promote <deployment-url>`.

### Data hazards

- **GDPR export bucket lifecycle** — R2 has a 30-day TTL on export blobs (T153). Rollback does not affect existing exports.
- **Notification dispatch coalescer** — cancels in-flight in-memory state on restart; missed dispatches don't double-fire because of the 24h idempotency window.
- **Reports queue** — Discord webhook is fire-and-forget; rollback does not lose reports themselves (they're in MongoDB).

## 10. Known issues — open follow-ups carried into M0

Each item below is acceptable for launch per founder review. Items
marked 🟡 are post-launch; items marked ⚠️ are pre-launch operator
actions.

### 🟡 Post-launch (acceptable for M0)

| ID | Description | Source |
|---|---|---|
| A11Y-01 | `prefers-reduced-motion` not honored by `tailwindcss-animate` | `docs/a11y-audit.md` |
| A11Y-02 | Focus visibility on rounded icon buttons clipped on mobile Safari | `docs/a11y-audit.md` |
| A11Y-03 | `text-muted-foreground` contrast at 12px borderline | `docs/a11y-audit.md` |
| PERF-01 | Lighthouse mobile profile not yet run | `docs/perf-audit.md` |
| PERF-02 | k6 cloud (Grafana k6) not wired | `docs/perf-audit.md` |
| PERF-03 | Push-notification dispatcher fan-out not load-tested | `docs/perf-audit.md` |
| SEC-01 | CI lint that rejects `*` in `ALLOWED_ORIGINS` for production | `docs/security-review.md` (A05) |
| SEC-02 | Dependabot / Renovate wiring | `docs/security-review.md` (A06) |
| POLISH-01 | `text-badge` token promotion | `docs/design-polish-notes.md` |
| POLISH-02 | Notification dropdown `align="end"` for mobile | `docs/design-polish-notes.md` |
| POLISH-03 | Empty-state illustrations + skeleton refinement | `docs/design-polish-notes.md` |
| FF-01 | `InviteCode` mechanism for v1.x if uncontrolled spread becomes a risk | `docs/closed-beta-runbook.md` |

### ⚠️ Pre-launch operator actions (NOT code)

| ID | Action |
|---|---|
| OP-01 | Run `pnpm install` on web to materialise `@axe-core/playwright` + `playwright-lighthouse` |
| OP-02 | Run the a11y suite once locally and confirm 0 CRITICAL violations on every route |
| OP-03 | Provision staging environment per `docs/staging.md` and run the §5 smoke checklist |
| OP-04 | Run k6 baseline + unread-count + feed-home against staging; confirm thresholds met |
| OP-05 | Run T117 critic-seed CLI against production database |
| OP-06 | Distribute wave-1 invites per `docs/closed-beta-runbook.md §1.3` |

## 11. Sign-off block

| Role | Name | Sign-off | Date |
|---|---|---|---|
| Founder | Joshua Xie | applied | 2026-05-23 |
| Operator | (founder; same person at MVP) | applied | 2026-05-23 |
| Designer | (not involved at MVP) | n/a | n/a |

Decision: **GO for M0 launch ceremony (T180)** subject to the
⚠️ pre-launch operator actions in §10.
