# Change Log: auxd MVP (`001-auxd-mvp`)

Formal record of in-flight scope changes captured during the lifecycle.
Each entry has a `CR-NNN` identifier. The same ID appears as a marker
(`<!-- CR-NNN -->`) on every individual edit in the affected artifacts,
so `grep -r "CR-001"` surfaces the full blast radius.

---

## CR-001: Remove all Spotify integration; pivot to Letterboxd-style manual search — 2026-05-22

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Priority** | Must Have |
| **Requested at phase** | Phase 6 (Implement) — in-progress, 27/183 tasks completed at the time of the CR |
| **Decision-maker** | Joshua Xie (founder, solo mode) |
| **Decision date** | 2026-05-22 |

### Rationale

Spotify Extended Quota Mode now requires **250,000 Monthly Active Users**
to apply (policy change observed 2026-05). The previous MVP design
treated Spotify as the catalog backbone, the signup-shortcut OAuth
provider, and the source of the "just-finished" auto-prompt wedge. A
250k MAU gate is structurally unreachable pre-launch — the app would be
capped at Spotify's 25-user Development Mode bucket forever.

Rather than wait for Spotify's policy to change (no signal it will) or
attempt a viral pre-launch channel to clear the gate (out of scope for
a solo-founder MVP), we deferred all Spotify integration to v2 and
pivoted the MVP to a Letterboxd-style manual search + rating model.
The provider-interface abstraction (`MusicProvider` and
`CatalogProvider` Protocols from `plan.md §4.4`) was retained so a
future Last.fm / Apple Music / Spotify re-add is a cheap addition
rather than a full replatform.

### Locked decisions (answers to the CR-001 clarifying-question gate)

1. **Catalog source:** MusicBrainz primary + Discogs fallback. Atlas
   Search indexes a cached MusicBrainz subset; live MusicBrainz lookup
   on cache-miss; Discogs queried for releases not in MusicBrainz
   (rare-pressing / vinyl-specific path). Cover art via Cover Art
   Archive.
2. **Just-finished auto-prompt cluster** (US-B6, FR-026, the §12
   detection cluster, JustFinishedPrompt Beanie collection): **DEFERRED
   TO V2**. Models stay importable for forward compatibility but are
   not registered with Beanie's `ALL_DOCUMENT_MODELS` at MVP.
3. **Provider-interface abstraction:** kept. MVP ships with one
   `CatalogProvider` impl (MusicBrainz + Discogs fallback as a single
   composite) and the `MusicProvider` Protocol remains defined for
   future-stream-platform integrations.
4. **Priority + timing:** Must Have, in-release. Spotify Extended
   Quota was the longest-tail blocker (was 2–6 wk external review);
   removing it nets out to a *negative* schedule impact (i.e., the
   pivot ships sooner than the original plan).

### Impact summary

```
Tasks removed:                16    (T002, T042–T047, T054–T056, T114–T116, T121,
                                     T122, T177 — T177 = orphan from T002)
Tasks deferred to v2:          9    (T123–T130 §12 cluster + T169 Pull-more-history,
                                     orphan of removed T115)
Tasks amended (completed):     5    (T021, T022, T026, T027, T029)
Tasks added:                   3    (T049a/b Discogs + T053a "report missing album")
Net task count:              170    (was 183 → 183 − 16 + 3 = 170; 162 active MVP +
                                     8 §12 deferred)
Artifacts touched:            17    (10 product-spec/* + spec.md + plan.md + tasks.md
                                     + change-log.md NEW + 5 wireframes)
Code/test files patched:      22    (settings.py + db.py + 5 model files + 4 lib
                                     docstrings + .env.example + 10 test files)
Tests:                       306 pass / 3 skip (3 skips are the deferred
                                     JustFinishedPrompt instantiation tests)
```

### Schedule impact

**Negative.** Removing Spotify lifts the previous longest-tail blocker
(Extended Quota review, 2–6 weeks of external waiting). Net effect:
launch becomes feasible earlier, not later.

### Risk

| Risk | Likelihood | Impact | Mitigation |
|---|:-:|:-:|---|
| Product positioning weakens | M | H | Letterboxd's traction (4M+ users, album-/film-grain manual logging) is the empirical proof that the manual model works. The wedge shifts from "8-second log via auto-detect" → "social-graph music discovery + clean manual logging". |
| Scope creep on manual-search UX | M | M | Manual-search empty-state, dup-detection, manual-album-creation flows are surface area we hadn't fully designed. Address as sub-CRs against the manual-search cluster if they emerge. |
| Test invalidation | M | L | 9 test files set `SPOTIFY_*` env vars. Mechanical sweep handled by the CR-001 code patch (see code subagent report). |
| Regression on completed tasks | L | M | 5 already-completed tasks (T021/T022/T026/T027/T029) need code edits. mongomock-motor + Pydantic + ruff + mypy caught the regressions during the patch. |

### Artifacts modified

| Artifact | Change Type | Edits |
|----------|:----------:|------:|
| `features/001-auxd-mvp/product-spec/out-of-scope.md` | Modified | 2 |
| `features/001-auxd-mvp/product-spec/product-spec.md` | Modified | 14 |
| `features/001-auxd-mvp/product-spec/user-stories.md` | Modified | 9 |
| `features/001-auxd-mvp/product-spec/user-journeys.md` | Modified | 7 |
| `features/001-auxd-mvp/product-spec/data-model.md` | Modified | 10 |
| `features/001-auxd-mvp/product-spec/decision-log.md` | Modified | 16 |
| `features/001-auxd-mvp/product-spec/success-metrics.md` | Modified | 6 |
| `features/001-auxd-mvp/product-spec/notification-taxonomy.md` | Modified | 6 |
| `features/001-auxd-mvp/product-spec/seeding-strategy.md` | Modified | 4 |
| `features/001-auxd-mvp/product-spec/README.md` | Modified | 6 |
| `features/001-auxd-mvp/product-spec/digest.md` | Modified | 4 |
| `features/001-auxd-mvp/product-spec/wireframes/01-onboarding.html` | Rewritten | 1 (full file) |
| `features/001-auxd-mvp/product-spec/wireframes/02-home-feed.html` | Modified | 4 |
| `features/001-auxd-mvp/product-spec/wireframes/03-log-sheet.html` | Rewritten | 1 (full file) |
| `features/001-auxd-mvp/product-spec/wireframes/04-album-detail.html` | Modified | 1 |
| `features/001-auxd-mvp/product-spec/wireframes/index.html` | Modified | 1 |
| `features/001-auxd-mvp/spec.md` | Modified | 78 inline markers + 32 DEFERRED labels |
| `features/001-auxd-mvp/plan.md` | Modified | ~65 (75 hits → 11 expected residuals, +37 net lines) |
| `features/001-auxd-mvp/tasks.md` | Modified | 16 removes + 9 defers + 5 amends + 3 adds + 25 downstream |
| `apps/api/src/auxd_api/settings.py` | Modified | 6 |
| `apps/api/src/auxd_api/db.py` | Modified | 1 |
| `apps/api/src/auxd_api/modules/users/models.py` | Modified | 5 |
| `apps/api/src/auxd_api/modules/albums/models.py` | Modified | 8 |
| `apps/api/src/auxd_api/modules/notifications/models.py` | Modified | 3 |
| `apps/api/src/auxd_api/modules/prompts/models.py` | Modified (no code change; CR-001 deferred-to-v2 note) | 2 |
| `apps/api/src/auxd_api/modules/diary/models.py` | Modified (judgment: source enum cleanup) | 1 |
| `apps/api/src/auxd_api/lib/observability.py` | Modified (docstring exemplar rename) | 1 |
| `apps/api/src/auxd_api/lib/resilience.py` | Modified (docstring exemplar rename) | 1 |
| `apps/api/src/auxd_api/lib/rate_limit.py` | Modified (docstring exemplar rename) | 1 |
| `apps/api/src/auxd_api/lib/otel.py` | Modified (docstring exemplar rename) | 1 |
| `apps/api/.env.example` | Modified | 1 |
| `apps/api/tests/test_otel.py` | Modified | 1 |
| `apps/api/tests/test_healthz.py` | Modified | 1 |
| `apps/api/tests/integration/test_session_middleware.py` | Modified | 1 |
| `apps/api/tests/unit/test_observability.py` | Modified | 1 |
| `apps/api/tests/unit/test_settings.py` | Modified | 3 (drop spotify validator tests; add discogs round-trip + audit-log check) |
| `apps/api/tests/unit/test_users_model.py` | Modified | 2 |
| `apps/api/tests/unit/test_albums_model.py` | Modified | 2 (add discogs sparse-unique; anti-regression spotify_id check) |
| `apps/api/tests/unit/test_notifications_moderation_models.py` | Modified | 2 (count 18→16; reserved-slot regression guard) |
| `apps/api/tests/unit/test_db.py` | Modified | 2 (count 17→16; importable-but-unregistered test) |
| `apps/api/tests/unit/test_prompts_seeding_models.py` | Modified | 1 (3× `@pytest.mark.skip` for instantiation; enum test stays) |
| `apps/api/tests/unit/test_secrets.py` | Modified | 1 (exemplar string rename) |

### Tasks removed (with reason)

| Task | Title | Reason |
|------|-------|--------|
| T002 | Submit Spotify Extended Quota Mode application | No longer applicable; Spotify deferred entirely |
| T042 | Spotify provider — contract tests | Spotify provider eliminated |
| T043 | Spotify provider — implementation | " |
| T044 | Spotify provider — token refresh + revoke handling | " |
| T045 | Spotify provider — `get_recently_played` | " |
| T046 | Spotify provider — `search_albums` | " |
| T047 | Spotify provider — `get_album` + tracklist | " |
| T054 | Spotify OAuth signup/login shortcut | Email-only signup (T053) is sole path |
| T055 | Connect-Spotify-later flow | No Spotify to connect |
| T056 | Disconnect Spotify (immutability) | " |
| T114 | Onboarding step 2: Spotify connect | Replaced by critic-follow step |
| T115 | Auto-import worker (30-day Spotify history) | No source data |
| T116 | Onboarding step 3: Confirm last 30 days | Depended on T115 |
| T121 | Settings → Integrations | No integrations to manage at MVP |
| T122 | Last.fm import (Should-Have) | Was a Spotify alternative; pivot mooted both |
| T177 | Extended Quota Mode follow-through | Orphan: depended on the removed T002 |

### Tasks deferred to v2

| Task | Title | Resume condition |
|------|-------|------------------|
| T123 | Spotify polling worker | Streaming-platform integration becomes available |
| T124 | Just-finished detection heuristic | " |
| T125 | JustFinishedPrompt lifecycle endpoints | " |
| T126 | Quiet hours enforcement (prompts + push) | Prompt-specific bit defers; general quiet-hours infra stays under §13 |
| T127 | Just-finished prompt component (frontend) | Streaming-platform integration becomes available |
| T128 | Web push notification dispatch (auto-prompt) | Prompt-specific bit defers; general web-push adapter now owned by new T136 |
| T129 | Disable auto-prompts UI | Streaming-platform integration becomes available |
| T130 | Auto-prompt analytics | " |
| T169 | Pull-more-history | Orphan: depended on the removed T115; v2 may revisit if a non-Spotify "more history" path materializes |

### Tasks amended (already completed; code patch lands alongside this CR)

| Task | Change |
|------|--------|
| T021 | User Document `music_providers` field type changed; `auto_prompt_enabled`/`auto_prompt_push_enabled` fields removed |
| T022 | Album Document `spotify_id` field + sparse index dropped; added `discogs_release_id` sparse-unique |
| T026 | NotificationType enum: removed Spotify-revoked + just-finished-prompt values |
| T027 | JustFinishedPrompt removed from `ALL_DOCUMENT_MODELS` in `db.py`; class kept importable for v2 |
| T029 | Settings: removed `SPOTIFY_INTEGRATION_ENABLED`/`SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` + their validator; added optional `DISCOGS_API_TOKEN` |

### Tasks added

| Task | Title | Cluster |
|------|-------|---------|
| T049a | Discogs catalog provider — contract tests (FAIL state) [TEST-FIRST] | §4 Providers |
| T049b | Discogs catalog provider — implementation | §4 Providers |
| T053a | "Report missing album" endpoint + UI (manual-search empty-state) | §5/§6 boundary |

### Phase rollback

None. Per the change-request skill's contract, edits land in place with
`<!-- CR-001 -->` markers and the `.forge-status.yml` `phases.*.status`
fields remain at their pre-CR values (the *phase* ran; the *content*
changed and the CR records the diff).

### Sync-verify run

Run #4 of `speckit.product-forge.sync-verify` follows this CR (Layer 1
through Layer 7 as applicable; expected to surface the planned drift as
RESOLVED-since-CR-001 and no new drift). See `sync-report.md` (Run #4).

### Decision notes

The pivot reduces the original "unhad combination" of four
differentiators (auto-imported streaming history + social-graph-primary
feed + album-as-unit + casual-first onboarding) to three — auto-import
drops. The remaining three are still each individually validated by
Letterboxd-for-film as a category proof point. The honest framing is
that auxd v0 is now "Letterboxd-style social album tracking" rather
than "your music auto-logged"; the latter framing returns in v1.x if a
streaming-platform integration ever reopens.

### Cross-agent risk consensus

All three doc-rewriting agents (spec.md, plan.md, product-spec/*),
working in parallel with no shared state beyond the locked CR-001
decisions, independently surfaced the same new failure mode:

> **Critic-seed recruitment is now load-bearing for first-session
> non-emptiness.** v1.3 used Spotify 30-day import to mask an empty
> initial diary; v0 leans entirely on the critic-seed roster being
> live pre-launch. If critic-seed under-delivers, MVP launches with
> a quiet empty-diary problem.

This consensus is now reflected in `spec.md §11 (new High-criticality
risk row)`, `plan.md §21 (new "manual-search-only logging dropoff" risk
+ "cold-start critic-seed under-delivery" risk)`, and `product-spec/
seeding-strategy.md Goal section (explicitly marked load-bearing)`.

**Actionable instrumentation flagged by the agents:** if
`log.commit.duration_ms` p50 exceeds ~3 minutes during M-2 closed beta,
a UX intervention on the manual-search affordance is required before
public launch.

### Approved

Joshua Xie

---

## CR-002: Phase 2 decision review pass — 2026-05-22

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Priority** | Must Have (rationale + UX correctness) |
| **Requested at phase** | Phase 6 (Implement) — in-progress, 48/170 tasks completed at the time of the CR |
| **Decision-maker** | Joshua Xie (founder, solo mode) |
| **Decision date** | 2026-05-22 |

### Rationale

During the Phase 2 product-spec creation (2026-05-21), founder issued
`continue where you left off` mid-question-flow, which the Phase-2 agent
interpreted as approval to auto-resolve all 22 main + 14 supporting
(20 minus the 6 superseded by CR-001 and the SS-1 dupe of Q13)
open-questions with research-recommended defaults. The defaults were
logged in `decision-log.md` for Phase-3 revisitation, where 3 revisions
applied changes but did not re-walk the auto-resolved questions
explicitly.

Now, 48 tasks into Phase 6 implementation, founder requested an
explicit re-walk of every auto-resolved decision to confirm or correct.
29 of 36 questions were confirmed at their current resolution. 5
substantive changes + 1 v2 roadmap note emerged. None of the 48 shipped
tasks (T001 through Session-9 §5 Auth wave) are touched — every changed
decision affects an unbuilt surface.

This CR captures the four substantive changes + the v2 roadmap note as
a single bundle, mirroring the CR-001 pattern, so future search anchors
on "Phase 2 decision review pass" surface every related artifact edit.

### Locked decisions (post-review confirmations)

The 29 confirmed-at-current-resolution decisions are NOT re-stated here
— they remain at the values logged in
`product-spec/decision-log.md` (Phase 2 v1.0 + R1/R2/R3 + CR-001).

The 5 changed decisions are:

1. **Q3 — Feed composition algorithm rationale softened.** MVP behavior
   unchanged (reverse-chronological + weighted by review-attached,
   extreme ratings, viewer-interaction-strength). Rationale dropped the
   "avoids algorithm distrust" framing — the wedge is data-stage-aware,
   not anti-algorithm. ML returns in v2 when scale + data earn its
   keep. Differentiator row in `decision-log.md` reworded for the same
   reason.

2. **NT-2 — Weekly digest hero: single → three-hero carousel.**
   Carousel features most-rated, most-reviewed, and most-Aux'd in your
   follow graph this week. Three cheap aggregate queries instead of
   one. Stronger email-open hook; digest layout reflows to fit three
   callouts above the chronological body.

3. **SS-3 — Invite landing shows "X just joined" social-proof line.**
   Reversed from "no at MVP." Gated by new `User.visible_in_just_joined`
   opt-in flag (default OFF for closed-beta cohorts L-12 through L-1
   so the launch-wave narrative stays under founder control; default
   ON for L 0 and later). Users flip the flag in Settings → Privacy.
   Surfaces: `/i/{handle}` invite landing (3-name ticker, 15-min cache)
   + `/joined` ticker in onboarding step 1 (~15 names).

4. **UJ-3 — Reviews: dedicated `/review/:id` route only, no inline
   expand.** Letterboxd parity. Feed shows rating + album thumbnail +
   first ~80 chars of review text as preview; the entire card is
   tappable and navigates to the route. Reading view surface: full
   hero (album cover, title, artist, viewer's rating context, Aux
   badge if any, Like button, share). Route is URL-shareable with OG
   meta; naturally hosts the v2 screenshot image-gen surface.

5. **UJ-4 v2 roadmap note — screenshot image-gen.** Server-side PNG
   rendering of the `/review/:id` hero, queued for v2 once the route
   exists. ~5–7 day add. Re-eval trigger: M3 milestone hit AND
   share-card-share rate <15% of published reviews.

### Considered-then-reverted

**DM-1 — Redis feed-page cache from Day 1.** Initially picked during
the review pass, then walked back after surfacing implementation
complexity (cache invalidation, stampede protection, cold-path
behavior is identical to no-cache anyway, debug surface). Original
default preserved: fan-out-on-read with a p95 > 200ms switch trigger.

### Impact summary

```
Tasks removed:                 0
Tasks deferred to v2:          0
Tasks amended:                 2    (T-future digest builder note + T-future
                                     invite landing note — to be picked up when
                                     those clusters land)
Tasks added:                   2    (T-future review route + T-future reading-view
                                     component — to be picked up in §6/§7 frontend
                                     wave)
Net task count:              170    (unchanged at the time of this CR; +2 will
                                     land when the affected clusters are sequenced)
Artifacts touched (this CR):   8    (5 product-spec/* + change-log.md + .forge-status.yml
                                     + this row; out-of-scope.md also touched for
                                     the v2-roadmap entry)
Code/test files patched:       0    (all changes affect unbuilt surfaces)
Tests:                       460 pass / 3 skip (unchanged)
```

### Schedule impact

**Mildly positive at MVP** (rationale-only Q3 change is free; NT-2 is
+0.5 day to the digest builder; SS-3 is +1 day for the invite-landing
ticker + privacy flag; UJ-3 is +3–5 days for the route + reading-view
component). Total: **~5–7 days added** to clusters that are not yet
sequenced. UJ-4 v2-roadmap note carries no MVP cost.

### Risk

| Risk | Likelihood | Impact | Mitigation |
|---|:-:|:-:|---|
| SS-3 cohort gate misfires (closed-beta names leak to public landing) | L | M | `User.visible_in_just_joined` defaults to `false` for users with `signup_cohort ∈ {L-12 .. L-1}`. Default ON only flips at L 0 cohort tag. Anti-regression test on the defaults-by-cohort matrix is part of the invite-landing task. |
| UJ-3 reading-view component bloats scope ("just one more thing") | M | M | Hero scope locked in `decision-log.md` UJ-3: album hero + Like + share. Comments thread explicitly NOT in scope (v2). |
| NT-2 three-hero carousel adds materially to digest render time | L | L | Three aggregate queries instead of one; each is a count over `DiaryEntry.created_at ≥ now()-7d` filtered by follow-graph. Indexed; cheap. Worst-case render time is still <500ms for the email render job. |
| Drift between this CR's source-doc edits and the derived docs (product-spec.md, spec.md, plan.md, tasks.md, research/competitors.md) | M | M | Sync-verify Run #6 immediately after this CR; any derived-doc drift surfaces as Layer-2/3/4 findings. |

### Artifacts modified

| Artifact | Change Type | Edits |
|----------|:----------:|------:|
| `features/001-auxd-mvp/product-spec/decision-log.md` | Modified | 6 (Q3 + Differentiator + NT-2 + SS-3 + UJ-3 + UJ-4 v2-note + revision-history row) |
| `features/001-auxd-mvp/product-spec/notification-taxonomy.md` | Modified | 3 (NT-2 resolution row + N-008 layout note + "Algorithm-distrust" anti-pattern row softened) |
| `features/001-auxd-mvp/product-spec/seeding-strategy.md` | Modified | 2 (Invite mechanics block + SS-3 resolution row) |
| `features/001-auxd-mvp/product-spec/user-journeys.md` | Modified | 3 (Journey 3 steps 2/5 + Journey 5 step 6 share URL + UJ-3/UJ-4 resolution rows) |
| `features/001-auxd-mvp/product-spec/data-model.md` | Modified | 1 (new `User.visible_in_just_joined` field) |
| `features/001-auxd-mvp/product-spec/out-of-scope.md` | Modified | 2 (UJ-4 v2-roadmap row + "algorithmic-rec engine" row softened) |
| `features/001-auxd-mvp/change-log.md` | Appended | 1 (this entry) |
| `features/001-auxd-mvp/.forge-status.yml` | Modified | 2 (change_requests append + last_updated bump) |

### Tasks amendments / additions

| Action | Task | Status | Notes |
|--------|------|--------|-------|
| Amend | T138 weekly digest job | **Applied inline** | Hero count 1 → 3; carousel queries (most-rated / most-reviewed / most-Aux'd) above the chronological body |
| Amend | T090 review card component | **Applied inline** | "Body with read-more" → "preview first ~80 chars; whole-card tap navigates to `/review/:id`"; like button stops nav propagation |
| Add | T093a `/review/[id]` route (SSR + OG meta) | **Applied inline** | SSR fetching Review + Album + viewer-context; visibility-checked; OG meta with album+rating; v2 image-gen slot reserved |
| Add | T093b review reading-view component | **Applied inline** | Letterboxd-parity hero + body; Like + share; comments thread NOT in scope (v2) |
| Add | Invite-landing ticker (SS-3) | **Pending cluster sequencing** | `/i/{handle}` landing page is not yet a tasks.md row; gets picked up when the invite-mechanics cluster is sequenced. The CR's job is to ensure the ticker + `User.visible_in_just_joined` consumer get added when that cluster lands. Sync-verify Run #6 flags this as pending coverage. |

The four review/digest items landed in `tasks.md` inline because the
affected clusters (§8 reviews + likes + sort, §13 notifications) are
already sequenced in the file and the new task IDs slot cleanly. The
invite-landing ticker is deliberately deferred — the `/i/{handle}`
landing page doesn't yet have a tasks.md row to amend, and inventing
the row mid-implementation would create a placeholder with no
sequencing context. Sync-verify Run #6 will flag this as a Layer-5
coverage gap for the next cluster sequencing pass.

Net task count after CR-002: **170 → 172** (164 active MVP + 8
DEFERRED-TO-V2). Active count: 162 → 164.

### Phase rollback

None. All artifact edits land in place with `<!-- CR-002 -->` markers;
`.forge-status.yml` `phases.*.status` fields remain at their pre-CR
values.

### Sync-verify run

Run #6 of `speckit.product-forge.sync-verify` follows this CR. Expected
findings: Layer-2/3 drift in product-spec.md / spec.md / plan.md /
tasks.md / research/competitors.md as the derived-doc propagation
catches up. No Layer-6 (spec ↔ code) impact expected because no
shipped code is touched.

### Decision notes

This CR is structurally lighter than CR-001: zero code touched, zero
tasks removed, four substantive doc-level decision changes + one v2
roadmap note. The Differentiator row softening (Q3 rationale) is the
most strategic edit — it preserves the social-graph-first posture at
MVP while removing the "anti-algorithm" framing that was both
historically inaccurate (auxd was always pro-heuristic, not
pro-no-algorithm) and risked closing the door on graph-aware ML in
v2.

### Approved

Joshua Xie
