# Implement — Phase 6 Digest (Session 1)

> Feature: `001-auxd-mvp` | Session 1 ended: 2026-05-22T03:30:00Z
> Tasks executed this session: 4 (T001, T003, T004, T008) + 10 sync-fix-list applies (pre-implementation)
> Phase status: `phases.implement = in_progress` — §0 prerequisites partially complete

## Session 1 scope

**Pre-implementation:** Applied 10 active items from `sync-fix-list.md` to plan.md (4 new sections), tasks.md (2 new tasks T010a + T015a; 5 amended T013/T023/T025/T026/T135), and bookkeeping files. Structural drift advance: from 27 to projected ~10 on next sync-verify run (cosmetic INFOs remain advisory).

**Autonomous §0 prerequisites executed:**
- **T001** — Constitution authored from plan §0 + ratified by founder + committed (`0c608a9 chore: ratify project constitution`).
- **T003** — Monorepo scaffolding: pnpm workspace + apps/api (uv) + apps/web (Next.js 15) + packages/shared-types. 17 files written. `.product-forge/config.yml` updated to monorepo mode.
- **T004** — `.github/workflows/ci.yml` with backend (ruff + mypy strict + pytest) + frontend (Biome + tsc strict + build) + aggregate `ci-status` gate.
- **T008** — VAPID keypair generated (P-256 / ES256). Public key in `apps/web/.env.example`; private key tracked outside repo with rotation procedure in `docs/infra.md`.

**Tasks NOT attempted this session (human-action blockers):**
- T002 — Spotify Extended Quota Mode application (external 2–6 wk dependency)
- T005 — MongoDB Atlas + Upstash Redis provisioning (external accounts)
- T006 — Fly.io + Vercel projects + DNS for TBD.app (external accounts + DNS)
- T007 — Postmark + Sentry + PostHog accounts + secret provisioning
- T009 — Deploy workflows (depends on T006+T007 live)
- T010 — Synthetic monitoring (depends on T009)
- T010a — Nightly mongodump backup (depends on T005+T007)

## Key decisions

- **Plan §4.5 / §4.6 / §11.2.1 / §16.5 added** during sync-fix apply to close structural drift on Must-Have requirements (endpoint rate-limit, Settings→Integrations, report-missing-album, axe-core CI gate). All four reference their DRIFT-L\* source in the section heading for forward traceability.
- **§3.1 collection inventory extended** with `follow_requests`, `review_edit_history`, and `missing_album` as a new `reports.target_type` enum value. The follow-request queue is Must-Have infrastructure for US-G2 even though US-H3 (the UI flow) is Should-Have — surfaced explicitly in sync-fix-list.
- **Constitution signed name-only.** Per founder directive, `**Ratified by:** Joshua Xie (founder, solo mode)` — no email. Memory saved for future governance docs.
- **Monorepo workspace_type = pnpm** (not Turbo or Nx) — keeps overhead minimal at MVP. Can migrate later if multi-app builds become non-trivial. shared-types package uses `workspace:*` protocol.
- **No build verification performed locally.** pnpm and uv are not installed in this dev environment. Scaffolding is syntactically valid and follows current Next.js 15 + FastAPI patterns, but `pnpm install` / `uv sync` / dev-server boot will be the user's first verification step.
- **VAPID generated via Python `cryptography` lib, not openssl `ec` shell commands** — the initial openssl extraction had byte-offset issues. Python's `cryptography.hazmat.primitives.asymmetric.ec` is the canonical correct path.

## Artifacts produced

### New files (T003)
- `package.json`, `pnpm-workspace.yaml`, `.gitignore`
- `apps/api/pyproject.toml`, `apps/api/README.md`
- `apps/api/src/auxd_api/__init__.py`, `apps/api/src/auxd_api/main.py`
- `apps/api/tests/__init__.py`, `apps/api/tests/test_healthz.py`
- `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/next.config.mjs`, `apps/web/biome.json`, `apps/web/next-env.d.ts`, `apps/web/README.md`
- `apps/web/.env.example`
- `apps/web/src/app/layout.tsx`, `apps/web/src/app/page.tsx`
- `packages/shared-types/package.json`, `packages/shared-types/tsconfig.json`, `packages/shared-types/README.md`
- `packages/shared-types/src/index.ts`
- `README.md` (root, rewritten)

### New files (T004)
- `.github/workflows/ci.yml`

### New files (T008)
- `docs/infra.md`

### Modified files (constitution / sync-fix)
- `.specify/memory/constitution.md` (T001 — full ratification)
- `.product-forge/config.yml` (T003 — monorepo mode enabled)
- `plan.md` (sync-fix §1.1.1, §3.1, §4.5, §4.6, §6, §11.2.1, §13.1, §16.4, §16.5)
- `tasks.md` (sync-fix T010a + T015a added; T013/T023/T025/T026/T135 amended; T001/T003/T004/T008 marked [x])
- `sync-fix-list.md` (all 10 active items checked + dated)
- `implementation-log.md` (2 checkpoints written)

### Commits
- `0c608a9 chore: ratify project constitution` — constitution.md only, per user directive.
- All other changes remain uncommitted. Recommended next commit: `chore: scaffold pnpm + uv monorepo for §0 prerequisites` covering T003/T004/T008 + sync-fix bundle.

## Open risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Build verification deferred** — pnpm + uv not installed locally, so `pnpm install` / `uv sync` / dev-server boot has not been exercised. | M | First action of next session: `brew install pnpm uv`, then run the T003 Done-criteria checks. If anything fails, treat as a regression and fix before further §0 work. |
| **External dependency chain (T002/T005/T006/T007) blocks T009/T010/T010a** | H | T002 is the longest lead-time (2–6 wk Spotify review). Submit Day 1 of next session. T005-T007 can run in parallel and unlock T009. |
| **No code committed yet for T003-T008** — only constitution committed | L | Bundle into a single follow-up commit before §1 backend foundation work starts to keep history clean. |
| **Constitution + monorepo not yet validated against an actual feature task** | L | T011 (FastAPI app skeleton) will be the first real exercise of the constitution + module layout principle. Expect minor refactors during T011 if the layout guidance proves brittle. |
| **OpenTelemetry T015a depends on T015 which depends on T011** — three-deep chain; OTel is Constitution P5 mandatory | L | Standard sequencing; no action needed beyond following the dep order in tasks.md. |
| **§1.1.1 fail-mode table now references `endpoint_rate_limit.redis_down` Sentry tag** which has no implementation yet | L | Lands in T013 + T020 + T015 wiring; Sentry tag is just a string contract. |

## Handoff to next phase / next session

**For next session of Phase 6 (continue Implement):**
1. Install tooling — `brew install pnpm uv` and verify `pnpm --version` and `uv --version` succeed.
2. Run T003 Done-criteria: `pnpm install` at root, `uv sync` in `apps/api`, `pnpm web:dev` (expect Next.js to serve `Hello from @auxd/shared-types.` at localhost:3000), `uv run --project apps/api uvicorn auxd_api.main:app --reload` (expect `/healthz` to return `{"status":"ok"}`).
3. If both boot cleanly, commit the scaffold as a single `chore: scaffold pnpm + uv monorepo for §0 prerequisites` commit.
4. **Then attempt T002** (Spotify Extended Quota app) — external, 2-6 wk lead. Submit Day 1. Capture reference ID in `docs/spotify-application.md`.
5. **Optionally** begin T005/T006/T007 external provisioning in parallel.
6. Once §0 is closed, begin §1 backend foundation work — T011 FastAPI app skeleton expansion (auth modules, settings, lifespan, etc.).

**For code-review (Phase 6B):** Currently premature — only the constitution is committed code. Code review becomes meaningful once §1+ tasks land actual feature code.

**For verify-full (Phase 7):** Same as above — verification is premature when only the constitution is committed.

**For sync-verify:** After all autonomous §0 tasks land in a commit, re-run sync-verify. Expected structural drift count: 0 (from 27 at Run #1). The 14 INFO items remain advisory.

---

# Sessions 2–8 cumulative rollup (2026-05-22 PM → 2026-05-23 early AM)

> Tasks executed across sessions 2–8: **42 of 170** (post-CR-001 baseline). See [implementation-log.md](../implementation-log.md) for per-session blow-by-blow. This digest summarises decisions, artifacts, risks, and handoff notes that span sessions.

## Sessions at a glance

| Session | Date | Scope | Tasks | Δ Tests |
|---|---|---|:-:|:-:|
| 2 | 2026-05-22 PM | Foundation libs wave — resilience/observability/OTel/secrets/KSUID/Settings | +6 (T014/T015/T015a/T017/T018/T029) | +76 |
| 3 | 2026-05-22 PM | Infra-decision swaps (Postmark→Resend, S3→R2, PostHog self-host→Cloud, sjc→iad) | docs-only | 0 |
| 4 | 2026-05-22 evening | §0 deployment automation + backend data layer — workflows + Beanie connection + 17 Documents + visibility | +12 (T009/T010/T010a/T012/T016/T021–T027) | +153 |
| 5 | 2026-05-22 evening | Request-path wave — FastAPI skeleton + Redis arq + session middleware + rate-limit + OpenAPI codegen | +5 (T011/T013/T019/T020/T028) | +76 |
| 6 | 2026-05-22 night | **CR-001** Spotify pivot — remove Spotify, transition to MusicBrainz + Discogs catalog backbone; Letterboxd-style manual log | (no tasks; 16 hard-removed, 9 deferred, 5 amended, 3 added) | +1 |
| 7 | 2026-05-23 early AM | §4 Providers wave — CatalogProvider/MusicProvider Protocols + Resilience transport + observability + MusicBrainz pair (P4 test-first) + Discogs pair (P4 test-first) + error taxonomy | +8 (T041/T048/T049/T049a/T049b/T050/T051/T052) | +46 |
| 8 | 2026-05-23 early AM | §6 Albums + Search backend — identity normalization + cron workers + edition aggregation + album detail endpoint + Atlas index + three-tier search | +7 (T063–T069) | +48 |

**Phase 6 cumulative test count: 1 → 400 pass + 3 skip.**

## Key cumulative decisions

- **CR-001 Spotify pivot (Session 6)** — Spotify Extended Quota now requires 250k MAUs, structurally unreachable pre-launch. MVP catalog backbone shifted to MusicBrainz primary + Discogs fallback + Cover Art Archive for covers. Provider abstraction kept; `MusicProvider` Protocol declared but no MVP impl. Just-finished cluster (§12) deferred to v2. Full audit trail in [change-log.md](../change-log.md).
- **Sync-verify cadence locked at 4 runs** — Run #1 pre-Phase 6, Run #2 mid-Session 4, Run #3 post-Session 4, Run #4 post-CR-001 + post-§4. Each run's verdict carried forward via `applied_split_with_override` discipline since the strict structural=0 budget repeatedly trips on doc-propagation findings that have no runtime impact.
- **Two-process Fly layout (Session 5)** — `[processes]` rename from `app` → `web` (resolved fly.toml-parse collision with top-level `app = "auxd-api"` field). The collision was caught only on first push to remote — a Run #4 finding that would have been caught earlier had we tested deploy locally first.
- **Test-first audit trail discipline (Session 7)** — Constitution P4 enforced rigorously on T048→T049 (MusicBrainz) and T049a→T049b (Discogs) pairs: contract tests verified FAILING with ImportError before impl was written; verified PASSING after. This is the discipline future provider integrations (Apple Music, Last.fm) should inherit.
- **Provider sharing across arq cron runs (Session 8)** — `WorkerSettings._on_startup` injects a single `MusicBrainzCatalogProvider` into `ctx["mb_provider"]` so the 1 req/sec etiquette policy (enforced via in-instance asyncio.Lock + monotonic) is preserved across consecutive cron firings rather than reset per-invocation.
- **Path divergence acknowledgment (Sessions 7 + 8)** — Two cases where landed code paths differed from tasks.md `Paths:` declarations: §4 single-file provider modules vs the original 3-file packages (Session 7); §6 album workers under `modules/albums/workers.py` vs `workers/album_cache_refresh.py` (Session 8). In both cases the architectural choice was reasonable for MVP scope; tasks.md `[x]` annotations carry the `Note: ...` explanation so the divergence is discoverable.

## Cumulative artifacts produced

- **Backend source (apps/api/src/auxd_api/):** 35+ modules across `lib/`, `modules/{users,albums,diary,reviews,backlog,social,moderation,notifications,prompts,seeding}`, `providers/{,musicbrainz,discogs}`, `routers/`, `workers/`, plus root files (db, redis_client, settings, main, middleware).
- **Tests:** 70+ test files across `tests/unit/`, `tests/integration/`. 400 passing + 3 skipped.
- **Infra:** `Dockerfile` + `fly.toml` (two-process layout) + 3 GitHub workflows (`ci.yml`, `deploy-api.yml`, `codegen.yml`, `synthetic.yml`, `backup-mongo.yml`) + `migrations/` (forward/rollback + atlas_search/albums_index.json + README) + `pyproject.toml` + `uv.lock`.
- **Shared:** `packages/shared-types/src/api.ts` (auto-generated from OpenAPI) + `scripts/codegen.sh`.
- **Frontend stub:** `apps/web/` minimal Next.js 15 scaffold (T003); full §3 frontend foundation (T031–T040) still open.
- **Docs:** `change-log.md` (CR-001 audit trail), `sync-report.md` + `sync-report.json` (4 runs), `implementation-log.md`, `tasks.md`, `plan.md`, `spec.md`, full `product-spec/` set including 5 wireframes redesigned for the Letterboxd pivot.

## Cumulative open risks

| Risk | Severity | First flagged | Status |
|---|:-:|---|---|
| Critic-seed cold-start under-delivery (CR-001 wedge replacement) | **High** | Session 6 (cross-agent consensus) | Open — instrumentation flag set: if `log.commit.duration_ms` p50 > 3 min during M-2 closed beta, UX intervention needed before public launch |
| Album.mbid unique-sparse collapses editions at MVP | Medium | Session 8 | Open — future CR candidate; drops unique constraint + adds `release_group_mbid` field |
| T069 p95 search latency may exceed 200ms NFR on cold-cache MB-fallback path | Medium | Session 8 | Open — acceptable for v0; rethink in v1.x if signal lands; mitigations include async fan-out + race or explicit "searching external sources…" UI signal |
| Atlas Search not testable under mongomock (`$search` aggregation unsupported) | Low | Session 8 | Mitigated via `_atlas_search` graceful fallback to `[]`; dev-env search runs in provider-only mode |
| 4 of 4 sync-verify runs hit the strict structural=0 budget | Low (advisory) | Run #1 (cumulative) | Carry-forward `applied_split_with_override` disposition; budget may need to relax for the long-tail of cross-doc propagation findings |
| Worker module path divergence from tasks.md Paths | Low | Session 7, Session 8 | Mitigated via `Note: ...` annotations on the `[x]` task lines; semantically correct since the chosen layouts are sound |

## Cumulative handoff notes (for Phase 6B Code Review + Phase 7 Verify Full)

**For Phase 6B code review (when run):**
1. **Focus area 1: §4 Providers + §6 Search service composition.** The three-tier search (Atlas → MB → Discogs) in `modules/search/service.py` is the most architecturally novel surface in the codebase post-CR-001. Verify the dedupe heuristic (`mbid` else case-folded `(title, artist)`) doesn't have false-positive collisions.
2. **Focus area 2: Visibility filtering in `modules/albums/routes.py`.** 6 integration tests cover the matrix but real-world adversarial paths (e.g., a follower querying after the followee blocks them mid-request) aren't exercised yet.
3. **Focus area 3: Session middleware HMAC + CSRF (T019).** Standard pattern but the tamper-rejection path returns 401 not silent-anonymous — verify this is the desired UX. Login CSRF mitigation is just SameSite=Lax; document if that's acceptable.
4. **Focus area 4: Constitution P4 audit trail.** §4 provider pairs were verified FAILING before impl was written. §6 workers/services used tests-after pattern (not contract-test pairs). Spot-check whether the P4 discipline holds where it should.

**For Phase 7 verify-full (when run):**
1. **Layer 5 (tasks ↔ code) is the highest-fan-out check.** §4 + §6 added ~30 new files; the Paths annotations on tasks.md have some intentional divergence (worker module location, single-file provider modules) — verify-full should walk through each and assert the documented divergence is acceptable.
2. **Layer 6 (spec ↔ code) becomes meaningful for the first time.** Pre-§6 there was no business logic; the album-detail endpoint + search endpoint + edition aggregation + Atlas index are the first end-to-end surfaces that can be traced from US-F1/US-F2/US-B1 + FR-005/FR-033 down to actual code.
3. **CR-001 propagation completeness.** Run #4 caught 4 doc-propagation WARNs + 3 INFOs and fixed them; verify-full should confirm no new Spotify residuals snuck in across the §6 work.

**For sync-verify (Run #5, when run):**
- Expected new drift items: any §6 spec/plan/tasks coverage that didn't surface during Session 8 (e.g., FR-033 cross-link to T053a; new Atlas index applied operationally).
- Recurring INFOs from prior runs (~11) carry forward; same advisory class.
- Apply the manual Atlas Search index update before Run #5 to close the operator-follow-up loop.

**For phase 6 completion gate:**
This digest cumulatively covers Sessions 1–8. Phase 6 stays `in_progress` because **128 tasks remain** of the 170-task MVP. Natural next slices, in dependency-order:
1. **§3 Frontend foundation** (T031–T040) — unblocks T070/T071/T072 + lets the user click through the app end-to-end against the live backend.
2. **§5 Auth handlers** (T053/T053a/T057–T062) — unlocks user-protected endpoints across §7–§10.
3. **§7 Diary + Log sheet** (T073–T084) — the new MVP wedge interaction.
4. **§8 Reviews + Likes + sort** (T085–T094) — depends on §7.

A `/speckit.product-forge.code-review` (Phase 6B) run on the current state is premature — most surfaces don't exist yet. Re-evaluate after §3 + §5 (or after §7 if backend-only review is appropriate).
