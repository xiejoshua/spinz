# Problem Discovery — Digest

> **Feature:** 001-spinz-mvp
> **Phase:** problem-discovery
> **Generated at:** 2026-05-21T22:46:47Z
> **Artifact owner:** speckit.product-forge.problem-discovery

## Key decisions

- **Target segment:** casual Spotify listeners 18–35 (not music power users) — wedge into RYM/AOTY's underserved customer base.
- **Differentiator:** social-graph-based recommendations (follow friends/critics) — not algorithmic recs, not chart-based.
- **Validation basis:** competitor evidence (Letterboxd's success, absence of music winner) — not user interviews. Acknowledged moderate validation strength.
- **Severity assessment:** 6/10 — latent cultural need (build music identity), not acute pain. Adoption will depend on execution and seed strategy, not problem urgency.
- **Go/No-go recommendation:** **GO with conditions** — proceed to Phase 1 research, treating it as a competitor + UX pattern deep-dive that must close the user-research gap before Phase 2 product-spec locks the wedge.

## Artifacts produced

- `problem-discovery/problem-statement.md` — Problem Statement Canvas, JTBD analysis, competing forces, 6 risks, 5 hypotheses H1–H5.
- `problem-discovery/interview-script.md` — 30-min 1:1 script targeting 8–12 participants across 4 recruit segments, with scoring rubric (≥15/20 = strong).
- `problem-discovery/digest.md` — this file.

## Open risks

- **Unmitigated: habit-formation risk.** Casual listeners don't currently track albums; product friction must be sub-Spotify-saving low to overcome inertia. Phase 1 UX research must address.
- **Unmitigated: cold-start network effect.** Social-first thesis requires critical mass; needs an explicit seeding strategy from Phase 2 product-spec onwards.
- **Unmitigated: differentiation thinness.** Multiple prior attempts (AOTY, Albums.fm, MusicBoard) exist — Phase 1 must identify *why* they stalled to define Spinz's moat.
- **Accepted: validation by competitor evidence only.** Direct user interviews deferred — appropriate for portfolio/side-project scope, would be a Go/No-go bar for venture stage.

## Handoff notes for next phase

- Phase 1 (Research) should prioritize: (a) post-mortem of failed Letterboxd-for-music attempts, (b) UX pattern study of Letterboxd / Goodreads / Discogs for casual-tier engagement, (c) Spotify + Apple Music API capability/policy audit, (d) social-graph mechanics in successful niche socials (Letterboxd, Strava, Goodreads).
- Hypotheses H1–H5 in problem-statement.md are the test plan for research — every research artifact should map to one or more.
- Target segment is *explicitly* casual listeners — research should not over-weight RateYourMusic-style power-user signals.
- Spinz competes with passive defaults (Spotify-only) as much as with active trackers — research framing should reflect "switching cost from doing nothing" not just "switching cost from existing tools."
