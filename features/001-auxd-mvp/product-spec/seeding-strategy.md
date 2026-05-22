# Cold-Start Seeding Strategy: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> **Why a first-class document:** A social product without a seed graph is a ghost town. This is launch infrastructure, not marketing. Research H3 identified "no tastemaker seeding" as one of the six failure causes across prior Letterboxd-for-music attempts.
> Related: [product-spec.md](./product-spec.md) | [user-stories.md §A4](./user-stories.md) | [data-model.md §CriticSeed](./data-model.md)

---

<!-- CR-001: critic-seed is now load-bearing for the first-session non-empty experience because there is no streaming auto-import to pre-populate the diary. -->
## Goal

When a brand-new user finishes onboarding, their home feed has content **even though their own diary is empty** (CR-001 / R4 removed the streaming auto-import that previously pre-populated the diary; critic-seed activity is now the *only* source of first-session non-empty content). When they search for "Kendrick" or "Radiohead", the album pages show ratings from someone whose taste they recognize as legitimate. Without this, the social-graph thesis (H2) cannot compound — there is no graph to walk *and* the empty-diary state has nothing to lean on.

---

<!-- CR-001: still framed as four-pronged for historical continuity, but prong 2 (Last.fm import) is deferred to v2; effective MVP shape is three-pronged. -->
## The four-pronged approach *(at MVP: effectively three-pronged — prong 2 deferred per CR-001 / R4)*

### 1. Founder-curated critic seed roster (PRIMARY — launch blocker)

A roster of ~50 real-world music critics, curators, and tastemakers given auxd accounts and a soft incentive to use them. **This must be alive before public-access wave.** Without it, auxd launches as an empty room.

#### Recruit profile

Each seed should be:
- A real, identifiable person with existing audience in music (Twitter/X ≥5k music-context followers, or Substack ≥1k music subs, or known critic at recognized publication).
- Active currently (not retired, not dormant) — must plausibly post on auxd within the launch month.
- Spans genre clusters: 8–10 each in indie/alt, hip-hop, electronic, rock, pop, R&B, jazz/classical, global/Latin, country/folk, ambient/experimental.
- Diverse demographically (age, gender, location, race) — the seed is what new users will see; under-represented voices in music criticism deserve over-representation here.

#### Recruitment playbook (founder responsibility)

1. **Identify 80–100 candidates** via: existing music-twitter follows, Pitchfork/Substack writers, niche-genre podcasters, college-radio DJs, label A&R people, scene bloggers.
2. **Personal cold outreach** (DM/email): one-paragraph pitch, "early access + 6 months auxd Pro free + founder Slack access".
3. **Convert ~25–35** to active seed members (40% conversion is realistic for cold music-Twitter outreach).
4. **Onboard them privately** during closed-beta wave (M-2 of launch): give them the app, ask for ≥10 reviews each, observe + iterate.
5. **Soft incentive at launch**: featured-critic badge, "top 10 reviews this week" surface, future revenue share if/when auxd monetizes.

#### Seed activity guarantee

Each seed account is asked (not required) to produce, before public launch:
- 10 ratings minimum
- 3 reviews of ≥100 words each
- 2 follows of other seed accounts (so the seed graph is internally connected)

If a seed produces zero activity within their first 4 weeks, they're moved to `CriticSeed.active=false` and not surfaced to new users. The roster is curated, not collected.

#### Surfacing in product

- **Onboarding step "Follow 3 to fill your feed"** shows: 6 critic-seed accounts (highest-priority + relevant to user's just-imported listens) + 4 mutual-taste suggestions from regular users.
- **Album detail pages** surface critic-seed reviews under "Critics" if no friends-graph signal exists yet.
- **Featured Critics directory** at `/critics` (low-priority page) lists the full active roster.
- Critic-seed accounts have a small visible badge ("featured critic" — copywriting TBD, no checkmark imagery to avoid the Twitter-blue-checkmark association).

---

<!-- CR-001: Section 2 entirely deferred to v2 — bundled with streaming-integration cluster. Preserved with DEFERRED-TO-V2 marker so the four-pronged framing remains discoverable; section content omitted to keep the MVP surface honest. -->
### 2. *(DEFERRED-TO-V2)* Last.fm history import (SECONDARY)

**Status:** DEFERRED-TO-V2 (CR-001 / R4). Was originally the OAuth-averse-user activation primitive. CR-001 deferred all streaming-history imports — both streaming-OAuth and Last.fm — to v2. At MVP the only activation primitive is manual logging. The section content (Last.fm username flow, 365-day scrobble fetch, album-grain dedup) is preserved in git history at v1.3; intentionally not re-displayed here to keep the MVP surface honest.

Re-eval trigger: streaming integration returns in v2.

---

### 3. Invite mechanics (TERTIARY — user-driven graph growth)

Users want to bring their friends. The invite flow is shaped to maximize that conversion without being spammy.

#### Mechanics

- Every user gets a personal invite link: `xiejoshua.com/i/{handle}` (vanity, redirects to signup with referrer tracking).
- The link displays the inviter's profile card on the landing page: "Casey invited you to auxd" + their 5 recent ratings.
- After signup via invite, the new user **automatically gets the inviter and 2 of the inviter's followed accounts pre-suggested** during onboarding (not auto-followed — they still confirm).
- Both parties see a "Casey joined auxd" notification when the invitee logs their first album (closes the loop, encourages mutual-follow).

#### Invite limits

- No artificial gating ("invites limited to 5/week" creates urgency but also resentment). Open invites at MVP.
- Spam protection: rate-limit signups from a single invite link to ≤50/day, ≤500/week.
- Abuse: invite links can be revoked by their owner (account → invite history → revoke).

---

### 4. Mutual-follow nudge (QUATERNARY — graph compounding)

Once a user follows N people, surface "people you might know who already follow you back" prompts.

#### Trigger

- After user follows their 3rd account → suggest "These 5 people are followed by people you follow":
  - Mutual-taste score = % of followed users who also follow each candidate, weighted by user's interaction frequency
  - Candidate must not be blocked, dismissed, or already followed
- After every 10 logs the user adds → re-run the suggestion job, show fresh suggestions

This is covered by user story [S-E5](./user-stories.md#s-e5-get-suggested-follows).

#### Suggestion ranking

Score = weighted sum of:
- Mutual-taste overlap (40%) — how many albums you both rated highly
- Followed-by-followed (30%) — how many of your follows also follow them
- Shared seed (15%) — both followed by ≥2 critic-seed accounts
- Local label / genre overlap (10%) — based on user's diary signal
- Recency boost (5%) — recent activity preferred

Algorithm is heuristic at MVP. ML-based suggestion (collaborative filtering) deferred to v2.

---

## Pre-launch playbook (founder timeline)

| Week | Action |
|---|---|
| **L-12** | Begin candidate-list assembly for critic seed. |
| **L-10** | Begin cold outreach (20–30 candidates per week). |
| **L-6** | Closed-beta wave: ~30 critic seeds + ~50 friends-of-founder onboard. |
| **L-4** | Validate seed activity (each seed has ≥10 ratings, ≥3 reviews). Cull inactive. |
<!-- CR-001 removed: Spotify Extended Quota Mode application — N/A at MVP, was the trigger for CR-001 itself. -->
| **L-3** | *(was: Spotify Extended Quota Mode application submitted — N/A per CR-001 / R4. Slot retained as buffer for catalog-quality bug-bash.)* |
| **L-2** | Internal-only testing wave; bug-bash. |
| **L-1** | Soft launch — public signups behind waitlist (controlled ramp). |
| **L 0** | Open public launch. Critic seed pre-recommended in onboarding. |

---

## Operational levers post-launch

| Lever | When to pull |
|---|---|
| **Activate more seeds** | If seed coverage of new-user's top-listens is < 60% |
| **Bump seed priority** | If a critic's activity is driving disproportionate sign-ups |
| **Suggest different counterweight** | If feed becomes monocultural (e.g., 80% indie-rock seed-driven) — bias suggestion ranking toward under-represented genres |
| **Pause new seed onboarding** | If active seed roster exceeds ~80 — diminishing returns and dilutes featured surface |
| **Critic of the Week** | Weekly editorial surface highlighting one seed account; v1.x feature, not MVP |

---

## Anti-patterns we are explicitly NOT doing

| Anti-pattern | Why banned |
|---|---|
| Buying critic accounts / paying for reviews | Erodes trust the second it's discovered |
| Auto-following critic seeds without user consent | Surveillance-y; violates user agency |
| Fake / sock-puppet accounts to "fill" the feed | If discovered, brand-killing; explicitly forbidden |
| Importing other platforms' user data (RYM scraping, etc.) | Legally fraught; reputation risk |
| Pressuring critics to post on a schedule | Critics' authenticity is the product |

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Critic seed roster never reaches critical mass at recruitment | Founder owns this directly; if conversion is <20% after 4 weeks of outreach, delay public launch |
| A seed critic becomes inactive / leaves the platform | `CriticSeed.active=false` toggle; rotate in a backup from the candidate list |
| Genre coverage is uneven (e.g., 70% indie-rock heavy) | Coverage dashboard reviewed weekly during launch; gap-fill outreach |
| Onboarding step becomes a follow-grinder ("must follow 10 to advance") | Cap minimum at 1; never gate on follow count >1 |
| Critic-seed reviews flood the global album-detail pages, drowning out user reviews | Sort: friends > recent public > critic-seed (lowest tier); this is the recommended order in [user-stories.md S-C2] |
| Critic seed account is hacked / posts inappropriate content | Standard account-recovery + suspend flow; critic-seed badge can be removed by admin instantly |

---

## Resolved decisions (Phase 3 Revision #2)

All 5 prior open questions resolved. See [decision-log.md §Seeding strategy](./decision-log.md) for full table.

1. **SS-1 — Critic seeds appear as PRE-CHECKED checkbox cards on the "Follow 3" onboarding screen** (per Q13). Technically opt-in (user can untick); practically achieves "instant feed" outcome.
2. **SS-2 — "Featured Critic" badge is an inline subtle "· Critic" text suffix** next to the display name everywhere. No icon, no checkmark. Provides social proof; avoids class-hierarchy feel.
3. **SS-3 — Invite links do NOT include "X just joined" social-proof line at MVP.** Adds privacy surface; founder wants tight control over launch-wave narrative.
4. **SS-4 — Critic seeds receive free Pro only at MVP** (no monthly stipend). Stipend is a v1.x lever for top-engagement seeds once retention is proven.
5. **SS-5 — Off-ramp for a leaving seed: standard account, badge removed silently.** No public announcement.
