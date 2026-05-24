# Seed-Content Workflow (T166)

The auxd MVP is bootstrapped by a small editorial roster of music critics.
Their reviews, ratings, and follows seed the recommendation graph for
every new user during the first 6 months. This document covers the
end-to-end workflow for sourcing, onboarding, and pruning that roster.

The mechanical roster operations (add / remove / activate / deactivate)
live in `docs/critic-seed-runbook.md` — this doc is the human-side
workflow that wraps them.

## 1. Identifying critic candidates

We're looking for people whose recommendation would carry weight with a
new user discovering auxd cold. Three signals matter:

* **Domain expertise** — they write about music professionally, run a
  recognised reviews outlet, or have a track record of taste-making in
  a specific genre community.
* **Active output** — they're posting/reviewing/curating ≥ 1× per week
  in public. A dormant byline doesn't generate diary entries on auxd.
* **Tone alignment** — auxd is generative, not snarky. We avoid critics
  whose public voice is built around tearing music down; a few sharp
  takes are fine, but the centre of gravity should be enthusiasm.

### Sourcing channels (in priority order)

1. **RYM (RateYourMusic)** — search for top-rated reviewers in genres
   we want to seed (indie, hip-hop, jazz, electronic). Their public
   profiles already have a diary-style cadence; many will recognise
   auxd as the missing tool.
2. **Anthony Fantano-adjacent reviewers** — TheNeedleDrop's orbit
   produces dozens of high-output reviewers across formats (YouTube,
   newsletters, podcasts). Cross-reference with their RYM accounts.
3. **Music journalism Twitter / Bluesky** — Pitchfork, Resident Advisor,
   Stereogum, FACT alumni. Many freelancers welcome a side platform
   that values their commentary.
4. **Indie blog circle** — niche-genre blog runners (e.g., Boomkat for
   electronic, Passion of the Weiss for hip-hop). Smaller followings
   but their followers ARE our target user persona.

### Minimum activity bar

A candidate has either:

* **≥ 10 published reviews** in the trailing 12 months on any platform
  (RYM, blog, newsletter, podcast notes), OR
* **≥ 50 ratings/diary entries** on RYM in the trailing 12 months.

Lower the bar for high-prestige candidates (e.g., a former Pitchfork
editor with one essay/quarter) but document the exception in the
seed's `CriticSeed.notes` field.

## 2. Cold outreach template

Use the following email template. Personalise the first sentence — the
template is intentionally short so the human touch isn't drowned out.

> Subject: a music diary for {their style of reviewing}
>
> Hi {name},
>
> I've been reading {specific piece they wrote, with one concrete
> reaction} and it crystallised something I'm building. auxd is a
> diary-first music app — Letterboxd for albums, basically. No
> algorithm-driven recommendations, no streaming integration; just
> ratings, reviews, and a small graph of people whose taste you trust.
>
> I'm assembling a founding roster of ~50 critics whose accounts seed
> the recommendation graph for everyone who joins. Your taste would be
> central to the {genre/scene} corner of it. The ask is light: pre-fill
> 10–15 albums from your diary so you have a presence on day one, and
> aim for ~2 reviews/week your first month.
>
> Reply with "in" and I'll send the sign-up link + a short onboarding
> call invite.
>
> — {founder}

Track responses in a spreadsheet (`outreach.csv` in the founder Drive
folder). Columns: candidate / channel / sent_at / replied_at / status
(declined / pending / accepted) / seeded_at.

## 3. Onboarding script

When a candidate accepts, schedule a 20-minute call (Calendly link).
Run the following script:

1. **Handle setup (2 min)** — confirm the username they want; explain
   the handle-redirect window if they change their mind. (Backend
   honours redirects via `auxd_api.modules.users.redirect.resolve_handle`.)
2. **10–15 album diary seed (8 min)** — walk them through the manual
   search → log flow. Encourage a mix of recent + older albums so the
   genre signature has breadth. Confirm they understand the rating
   scale (0.5 stars, 5★ max).
3. **Review guidance (6 min)** — markdown is supported; show the
   review composer's preview. Tone: 100–400 words is the sweet spot;
   a 2-paragraph reaction beats a 1000-word essay. Avoid spoilers for
   visual albums (rare but real).
4. **Tagging conventions (3 min)** — auxd uses album-level genre tags
   from MusicBrainz + Discogs; we don't tag user reviews. Their
   `CriticSeed.genre_signature` is operator-set via the runbook; ask
   what 3–5 genre tags best describe their roster.
5. **Wrap (1 min)** — share the founder Slack DM channel for fast
   questions; promise an email recap.

After the call, the founder runs:

```
uv run python apps/api/scripts/manage_critic_seed.py add <handle> \\
    --priority {50..85 per call notes} \\
    --genres {3..5 tags from §4}
```

Send the recap email within 24 hours.

## 4. Activity expectations

* **Month 1** — at least 2 reviews/week and ≥ 5 new diary entries/week.
* **Month 2 onward** — at least 1 review/week.
* **Engagement** — like + comment on ≥ 3 non-seeded user reviews per
  week so the social graph feels alive to new users.

These are expectations, not contractual minimums. We don't enforce them
mechanically; they're the bar for staying in the active roster.

Run a monthly health check (1st of each month):

```
uv run python apps/api/scripts/manage_critic_seed.py list --active-only
```

Cross-reference with a quick "any diary entries in the last 30 days"
query (TBD via direct Mongo connect; not part of the CLI yet). Anyone
below threshold gets a short check-in email — don't deactivate without
the human touch unless they've gone fully silent for 60 days.

## 5. Cull cadence

Two states, in order:

1. **Soft-deactivate** at **60 days** of complete silence (no diary, no
   reviews, no logins). Use:

   ```
   uv run python apps/api/scripts/manage_critic_seed.py deactivate <handle>
   ```

   Their seed stays in the collection but won't appear in the
   onboarding deck or suggestions worker. They CAN log back in and
   start fresh — the founder runs `activate` to flip them back.

2. **Hard-remove** at **180 days** silent if soft-deactivate hasn't
   been reversed:

   ```
   uv run python apps/api/scripts/manage_critic_seed.py remove <handle>
   ```

   This deletes the CriticSeed row only; the underlying user account
   is untouched. A future return is functionally a fresh add — that's
   fine; we don't gain from tracking dormant editorial history.

## 6. Self-removal requests

If a critic asks to be removed:

1. Acknowledge within 24 hours.
2. Run `manage_critic_seed.py deactivate <handle>` immediately.
3. Send a follow-up email confirming they can stay an account holder
   (just not on the editorial surface).
4. If they want full GDPR deletion, queue the standard delete flow —
   that's a separate workflow, not a CriticSeed operation.

## Related docs

* `docs/critic-seed-runbook.md` — CLI command reference.
* `features/001-auxd-mvp/product-spec/seeding-strategy.md` — the
  product-spec rationale for the editorial-first cold-start.
