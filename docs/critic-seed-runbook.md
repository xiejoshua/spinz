# CriticSeed Operator Runbook (T162)

The CriticSeed roster is the founder-curated set of tastemaker accounts
that anchor onboarding "who to follow" suggestions, the Discover surface
(via the suggestions worker), and the cold-start fallback when a new
user has no diary signal yet.

This document covers when to add, deactivate, and prune critic seeds,
plus the runbook for the CLI at `apps/api/scripts/manage_critic_seed.py`.

## CLI reference

```
uv run python apps/api/scripts/manage_critic_seed.py add <handle> [--priority N] [--genres g1,g2]
uv run python apps/api/scripts/manage_critic_seed.py remove <handle>
uv run python apps/api/scripts/manage_critic_seed.py activate <handle>
uv run python apps/api/scripts/manage_critic_seed.py deactivate <handle>
uv run python apps/api/scripts/manage_critic_seed.py list [--active-only]
```

All commands take the operator-supplied user **handle** (case-insensitive,
handle-redirects honoured); the CLI resolves to the underlying user_id
internally so a renamed critic doesn't break the row.

Exit code is `0` on success and `1` on any error (unknown user, no row,
DB unreachable). Errors print to stderr; success messages print to
stdout.

## When to add a critic-seed

A user belongs in the roster when they meet **both** of the following:

1. **Domain expertise OR established tastemaker status** — they write
   public reviews / curate lists / are recognised in a music community
   we want to attract (RYM, music-journalism Twitter, an indie podcast,
   etc.). A friend of the founder who happens to like music is **not**
   enough; we are signal-boosting people whose follow recommendation
   has independent value to a new user.

2. **Minimum activity bar** — they have logged ≥ 10 diary entries OR
   published ≥ 3 reviews in the last 60 days. A profile with no
   on-platform signal can't establish a genre signature and contributes
   no taste-graph value beyond the editorial pick.

### Priority knob

`--priority` is an integer 1..100; higher ranks higher. Default is `50`.

Suggested bands:

* `80..100` — founder/strong-signal critics whose recommendation should
  appear in the **first two slots** of every new user's onboarding deck.
  Use sparingly; we want ≤ 5 of these total at MVP.
* `60..79` — high-signal critics with a clear genre niche. They surface
  in the top 6 when the viewer's genre signature overlaps.
* `40..59` — solid roster members. Default tier.
* `< 40` — experimental seeds we're trialling; they only surface for
  viewers with strong genre overlap.

### Genre signature seeding

The `--genres` flag pre-populates `CriticSeed.genre_signature` so a fresh
seed contributes the genre-overlap bonus from
`score_critics_by_genre_signature` immediately instead of waiting for
the worker to compute the critic's own diary-derived signature (T163).

Tags are normalised to lowercase. Example:

```
manage_critic_seed.py add fantano --priority 85 --genres indie,hip-hop,electronic
```

Leave `--genres` unset to defer to the worker — when the critic has
≥ 10 diary entries the nightly genre-signature compute (T163) fills it
in automatically.

## When to deactivate

Soft-deactivate (CLI `deactivate`) sets `active=False` and stamps
`deactivated_at`. The row stays in the collection — `activate` flips it
back without history loss. Deactivate when:

* **60 days silent** — no diary entries, no reviews, no logins. The
  recommendation is stale and the empty profile undermines new-user
  trust.
* **TOS violation** — the underlying user account was sanctioned. Deactivate
  the seed **before** sanctioning the user so the suggestions worker stops
  surfacing them mid-investigation.
* **Self-request** — the critic asked to be removed from the editorial
  surface. Honour immediately.

After **180 days** of silence consider `remove` (hard-delete) — by then
re-onboarding them at a later date is functionally equivalent to a new
seed and we don't gain from keeping the dormant row.

## Roster size guidance

Target **30–80 active rows** at MVP launch:

* < 20 critics → onboarding deck thins out; the suggestions worker
  fallback (priority-only) feels editorial-bare.
* 30–80 critics → the genre-overlap signal dominates and viewers with a
  diary signature see relevant critics surface organically.
* > 100 critics → the founder editorial signal weakens; consider raising
  the bar or splitting into curated sub-lists (future feature).

A monthly check-in (1st of the month) running `list --active-only` and
auditing the `deactivated_at` column is enough to keep the roster
healthy without a dedicated workflow.

## Related docs

* `docs/founder-workflows/seed-content.md` (T166) — outreach + onboarding
  workflow for new critics.
* `apps/api/src/auxd_api/modules/seeding/service.py` — the scoring
  algorithm consumes the rows this CLI manages.
* `apps/api/src/auxd_api/modules/seeding/models.py` — schema reference.
