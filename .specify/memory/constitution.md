# Spinz Constitution

> Project: **Spinz** — social album-tracking platform for casual streaming listeners
> Repo: `spinz/` monorepo · Feature `001-spinz-mvp` is the first feature
> Source-of-truth for principles cross-validated in every Phase 5 plan and every PR review.

## Core Principles

### I. External-call resilience (NON-NEGOTIABLE)

Every provider/API call wraps in **retry + timeout + circuit-breaker**.
No bare `httpx.get(...)`, `requests.get(...)`, or equivalent in feature code — all
outbound calls route through `apps/api/src/spinz_api/lib/resilience.py` helpers
(`retry`, `timeout`, `circuit_breaker`).

- **Why:** Spotify, MusicBrainz, Postmark, and PostHog are all third-party SLAs we
  do not control. The 2024-11-27 Spotify audio-features deprecation is the proof
  of why this principle exists: a wrapper layer turned what would have been a
  cascading outage into a degraded surface.
- **How to apply:** Failures degrade gracefully with documented fallback behavior
  per §1.1.1 of plan.md (e.g., Spotify down → cached metadata + paused
  auto-prompt; Postmark down → 3-attempt retry then `failed_emails` queue;
  Redis cache down → FAIL OPEN; Redis arq queue down → FAIL CLOSED 503).
  External failures never propagate to the user as raw 500s.

### II. Schema-versioned MongoDB documents (NON-NEGOTIABLE)

Every Beanie `Document` carries a `_schema_version: int` field.
Readers tolerate `current_version` and `current_version − 1`; **lazy-upgrade on next write**.
Migration code lives in `apps/api/migrations/{collection}_v{N}_to_v{N+1}.py`.
**No big-bang migrations** (except the M0 greenfield seed in `migrations/forward.py`).

- **Why:** Document schemas drift in MongoDB by design. Big-bang migrations on a
  multi-million-row collection are an availability hazard and risk irreversible
  loss. Lazy upgrade lets schema evolution happen continuously, gives us
  rollback windows, and forces every feature to think about backward
  compatibility before it ships.
- **How to apply:** Every new field on an existing Document goes with a
  migration helper that upgrades stale documents on read or write. Every
  `Document` class declares its current `_schema_version` as a class attribute.
  PRs that change a Document without a migration get blocked at review.

### III. Library-first modules (NON-NEGOTIABLE)

Backend is organized as **composable libraries**, not god-objects.
Each `apps/api/src/spinz_api/modules/<module>/` exposes a single public surface
(`<module>.service.py` with public functions, `<module>.routes.py` with FastAPI
routes, `<module>.schemas.py` with Pydantic IO models, `<module>.models.py` with
Beanie Documents).

**Internals are private** — files prefixed with `_` (e.g.,
`_weighting_helpers.py`) are not importable across module boundaries.
Cross-module calls go through public services, not internal helpers.

- **Why:** Spinz's wedge thesis spans many features (log, review, feed, prompts,
  notifications, seeding, moderation). Each is a load-bearing slice that needs
  its own boundary. God-object services rot fast under that pressure; module
  boundaries enable independent testing, parallel development, and clean
  deprecation paths.
- **How to apply:** When you find yourself reaching into another module's
  private helper, add the function to that module's public service first.
  Lint rule (ruff custom) flags cross-module imports that bypass `service.py`.

### IV. Test-first for catalog/auth edges (NON-NEGOTIABLE)

Spotify integration, MusicBrainz integration, and OAuth flows have
**contract tests written BEFORE implementation**. Integration tests against
Spotify's sandbox / Development Mode must pass before any feature using those
edges merges to main.

- **Why:** Catalog correctness and auth correctness are user-trust-critical
  surfaces. An incorrect album merge or a leaked OAuth token destroys
  product credibility faster than any feature can recover. Test-first on
  these edges is non-negotiable because the alternative is shipping
  silent corruption.
- **How to apply:** For tasks T042/T048 (provider contract tests), assertions
  land BEFORE T043/T049 (provider implementation). CI workflow gates merges
  to main on contract-test pass. Sandbox creds in Fly secrets,
  rotated monthly.

### V. Observability mandatory (NON-NEGOTIABLE)

Every external API call emits a **structured log line** with
`provider`, `endpoint`, `latency_ms`, `status_code`, `request_id`.
Every notification dispatch emits a **PostHog event** (`notification.dispatched`
with `type`, `channel`, `user_id`, `coalesced_count`).
Every error captures to **Sentry** with feature + module tags.
**OpenTelemetry** traces every HTTP request, outbound httpx call, and DB op
(per T015a + plan §15.4).

- **Why:** Spinz operates against three black-box external systems (Spotify,
  MusicBrainz, Postmark). Without forensic observability we cannot debug
  user-reported issues, can't validate the wedge metrics (sub-8s log,
  sub-500ms feed p95), and can't prove the notification system is not
  the Goodreads firehose we exist to prevent. Observability is the cost
  of building on third-party rails.
- **How to apply:** `lib/observability.log_call(...)` is the only sanctioned
  log entry point for external calls; bare `logger.info(...)` for
  cross-cutting concerns is flagged at review. Sentry init is mandatory
  on app start (T015). OTel auto-instrumentors run on T015a.

### VI. Provider abstraction (project-specific)

Every music-provider integration goes through the
`apps/api/src/spinz_api/lib/providers/MusicProvider` interface.
Provider-specific code lives in `apps/api/src/spinz_api/lib/providers/<provider>/`.
**Feature code never imports `spotify_sdk` (or equivalent) directly.**

- **Why:** The 2024-11-27 audio-features deprecation removed a public Spotify
  endpoint with 30 days notice. Apple Music is on the v2 roadmap; Last.fm is
  Should-Have at MVP. Provider abstraction is the only structural protection
  against any of these third parties shipping breaking changes mid-launch.
  Without it, every provider deprecation forces a search-and-replace across
  the codebase; with it, the blast radius is one file.
- **How to apply:** The `MusicProvider` interface (plan §5.1) defines
  `search_albums`, `get_album_by_id`, `get_recently_played`, etc. Concrete
  implementations live in `lib/providers/spotify/`, `lib/providers/musicbrainz/`,
  and (future) `lib/providers/apple_music/`. Lint rule (ruff custom) flags any
  direct provider-SDK import outside `lib/providers/<provider>/`.

## Project-specific constraints

### Security
- All OAuth tokens encrypted at rest with envelope encryption (T017).
- HMAC-signed session cookies; `httpOnly`, `SameSite=Lax`, `Secure` in prod.
- No refresh tokens in client-accessible storage.
- bcrypt password hashing cost ≥12.
- Endpoint rate-limiting on write endpoints per §4.5.
- CSRF protection via double-submit cookie (T019).

### Privacy & GDPR
- Public-by-default with per-entry visibility override.
- 30-day soft-delete grace period before hard-delete (account + diary entries).
- User-initiated data export within 30 days of request (T149/T153).
- 7-year retention on `gdpr_audit_log` collection.
- Review edit history (90-day audit log) **never exposed publicly** — readers see only the latest version (FR-030).

### Performance NFRs (locked at spec.md §6.1)
- Home feed render: p95 < 500ms
- Log commit (server-side from log-button-tap to confirmed entry): median < 8s
- Album detail SSR: p95 < 800ms
- Search-as-you-type: debounced 200ms; p95 < 300ms

## Development Workflow

### Code review gates
- **Constitution compliance:** every PR review checks the 6 principles above.
- **Test coverage:** lib/* libraries ≥90%, modules ≥80%, integration tests must pass against MongoDB + Redis containers.
- **Accessibility:** axe-core 0 violations per §16.5.
- **Type safety:** `mypy --strict` on backend, `tsc --strict` on frontend; no untyped externs without an issue tracked.
- **Lint:** Ruff + Biome must pass without `# noqa` / `// biome-ignore` unless paired with a comment explaining the exception.

### Migration discipline
- Every Mongo schema change ships with a `migrations/<collection>_v{N}_to_v{N+1}.py` helper.
- Lazy-upgrade-on-write is the only sanctioned migration pattern for post-M0 changes.
- Big-bang migrations require an explicit ADR in `docs/adr/`.

## Governance

This constitution **supersedes informal conventions**. Amendments require:

1. A documented ADR in `docs/adr/<NNN>-<title>.md` describing the change and rationale.
2. Founder sign-off (solo mode at MVP; expands to engineering lead + 1 reviewer post-team).
3. A migration plan if the amendment is breaking (e.g., removing a principle that existing code depends on).

All PRs and reviews must verify compliance with the principles above before merge. Complexity beyond a principle's scope must be justified in the PR description.

For runtime development guidance (project structure, conventions, day-to-day patterns), see:
- `features/001-spinz-mvp/plan.md` — current technical plan
- `features/001-spinz-mvp/tasks.md` — task breakdown with dependency ordering
- `.product-forge/config.yml` — Product Forge runtime configuration
- `docs/infra.md` — operational runbook (created in T010 + T010a)

---

**Version:** 1.0.0 | **Ratified:** 2026-05-22 | **Last Amended:** 2026-05-22

> **Ratified by:** Joshua Xie (founder, solo mode)
> **Commit:** `chore: ratify project constitution` — T001 completion gate satisfied.
> **Amendment process:** see Governance section above (ADR + founder sign-off + migration plan if breaking).
