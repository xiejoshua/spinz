<!--
auxd PR template — keep sections short. Constitution lives at .specify/memory/constitution.md.
Delete sections that genuinely don't apply (e.g., NFR notes for a docs-only PR), but
explain why in one line rather than removing silently.
-->

## Summary

<!-- 1-3 bullets. Why does this PR exist? What changes? -->

-

## Linked work

<!-- Task IDs from features/<slug>/tasks.md, story IDs, FRs, or sync-fix-list items. -->

- Task(s): T___
- Story / FR: US-___ / FR-___
- Sync-fix item (if any): DRIFT-___

## Test plan

<!-- How did you verify this change? Concrete commands or test IDs. -->

- [ ] `uv run pytest` (backend) — N passed
- [ ] `pnpm --filter @auxd/web typecheck` — clean
- [ ] `pnpm --filter @auxd/web lint` — clean (Biome)
- [ ] `pnpm --filter @auxd/web build` — succeeds
- [ ] Manual smoke (describe):

## Constitution compliance — `.specify/memory/constitution.md`

<!-- Tick every applicable principle. If a principle doesn't apply, write "n/a (docs only)" etc.
     If you waived a principle, explain why and link the follow-up issue. -->

- [ ] **I. External-call resilience** — all new outbound calls go through `lib/resilience` (retry + timeout + circuit-breaker); no bare `httpx.get(...)` in feature code.
- [ ] **II. Schema-versioned MongoDB docs** — every new/changed Beanie `Document` declares `_schema_version`; readers tolerate N and N-1; migration helper exists if schema shape changed.
- [ ] **III. Library-first modules** — no cross-module imports of `_private` helpers; new code lives behind a `service.py` public surface.
- [ ] **IV. Test-first for catalog/auth edges** — if this PR touches Spotify/MusicBrainz/OAuth: contract tests written before implementation and passing against sandbox.
- [ ] **V. Observability mandatory** — every new external API call emits structured log via `lib/observability.log_call`; every notification dispatch emits a PostHog event; errors captured to Sentry with feature + module tags.
- [ ] **VI. Provider abstraction** — no direct `spotify_sdk` (or equivalent) imports outside `lib/providers/<provider>/`.

## NFR gates — `features/001-auxd-mvp/spec.md §6.1`

<!-- Only relevant rows; delete the rest with a one-line reason. -->

- [ ] **Performance** — no regression to home-feed p95 < 500ms / log-commit median < 8s / album-detail SSR p95 < 800ms (cite measurement if applicable).
- [ ] **Accessibility** — axe-core 0 violations on affected screens (per plan §16.5).
- [ ] **Security** — no secrets in code; CSRF / rate-limit middleware applied to new write endpoints; OAuth scope changes documented.
- [ ] **Privacy / GDPR** — new user data has a defined retention; export + delete paths still cascade correctly.

## Drift surfaced

<!-- Did this PR uncover a plan/spec/tasks drift? List it so sync-verify catches it.
     If you applied an inline fix, link the file:line. If you're punting, add it to sync-fix-list.md. -->

- None / Plan §___ / Spec FR-___ / Tasks T___ — [describe]

## Notes for reviewer

<!-- Anything reviewers should look at first, risky areas, follow-up issues you opened. -->

-
