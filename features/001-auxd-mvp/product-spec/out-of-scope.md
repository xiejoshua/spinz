# Out of Scope (v1): auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 | Date: 2026-05-21
> Source: [decision-log.md](./decision-log.md)
> Related: [product-spec.md](./product-spec.md)

This document lists capabilities deliberately **out of scope** for the MVP. Each row notes the rationale for deferring and the trigger condition that would prompt re-evaluation.

## v2 candidates — re-evaluate after M6

| Feature | Why deferred | Re-eval trigger |
|---|---|---|
| **Apple Music integration** | Spotify-only at MVP. Apple Music adds 2–3 weeks of work for marginal addressable-market gain on a casual-streamer wedge. | Onboarding drop at Spotify OAuth >25%, OR ≥30% of waitlist users specify Apple Music primary |
| **Native iOS / Android apps** | PWA + responsive web at MVP. Native apps add ~6 months of work + platform-policy surface. | PWA install rate <20% of MAU and qualitative feedback consistently asks for native |
| **Curated user-created Lists (Letterboxd-style)** | Significant UI/data complexity (drag-order, collab, cover-pickers, list-of-the-week surfacing). De-elevated from MVP back to v2 in Revision #3 after weighing scope cost vs wedge focus — the wedge (log + rate + Award + review + backlog + social-feed) holds without Lists at MVP. *Revision history:* elevated to MVP in R1, returned to v2 in R3. | M3 milestone hit AND ≥10% of users ask for lists in feedback |

| **ALS / collaborative-filtering recommendation engine** | Heuristic social-graph recs are sufficient at MVP scale. ML-based recs need data and scale first. | DAU > 5k AND social-originated play rate plateaus |
| **Wrapped-style year-end retrospective** | High-polish, seasonal feature. Powerful for virality but not blocking. | First-year cohort exists (Q4 2027) and engineering capacity is available |
<!-- Removed in Revision #1: Auto-prompt elevated from v2 to MVP -->
<!-- (was: Auto-prompt deferred to v2; founder accepted the privacy tradeoff and elevated to MVP with opt-out default ON.) -->

| **Editorial / curated content surface** (Pitchfork-style) | Out of scope for product team to operate. May reconsider if a critic-seed offers to curate. | An identified editorial partner volunteers |
| **In-app messaging / DMs** | Out **forever** unless explicit product pivot. auxd is a social-tracking product, not a chat app. The notification surface stays focused. | N/A |
| **Embed/widget API** | "Embed my auxd diary on my Substack" — niche feature. | Embed-able-content requests show up consistently in feedback |
| **Group / shared diaries** ("us listening together") | Adds coordination complexity, low validated demand. | Multi-user feature requested in ≥5% of feedback |
| **Annual events / "watch parties"** | High-touch operational feature. | Community organically requests it; engineering capacity available |
| **Email-based composition** ("reply to this email to log") | Cute but niche. | Power-user request frequency |
| **Spotify-DJ collab** (cross-product) | Spotify-side feature, requires partnership. | Spotify reaches out (low probability) |
| **Multi-language UI** | English-only at MVP. Copy is key-extracted for future locales. | First localized cohort identified (likely Spanish or Portuguese given music-listening demographics) |

## Explicitly **not** going to do

These are out **permanently** unless a strategic pivot:

| Feature | Why never |
|---|---|
| **Algorithmic-rec engine that doesn't use social graph** | auxd's positioning is anti-algorithm; building a generic algo-rec contradicts the wedge |
| **Ads / sponsored entries in the feed** | Brand-killing for the casual-trust thesis; we are subscription-only if/when we monetize |
| **Scraping / importing data from RYM, AOTY, others without explicit user consent** | Legally fraught and reputationally toxic |
| **Sock-puppet / "fake users to fill the feed"** | If discovered, brand-killing; explicit operating principle |
| **Influencer-marketplace / pay-for-review surfaces** | Erodes trust; opposed to wedge |
| **NFT / blockchain / Web3 features** | Casual segment doesn't want this |
| **Generative-AI auto-generated reviews** | Authenticity is the wedge; AI-text on the platform is forbidden |
| **Audio uploads / DIY music distribution** | Out of category; Bandcamp owns that |

## v1.x candidates — possible within first year

These could plausibly land in a v1.1, v1.2, v1.3 incremental release before a "v2":

- Friend-request flow for private profiles (user story S-H3)
- Album merge / report-wrong-album admin tooling (user story S-H2)
- Weekly emailed digest UI improvements (user story S-H4)
- Share-card design refinements (user story S-H5)
<!-- Removed in R3 since Lists themselves moved back to v2 — collaborative-lists and auto-list-generation roll up into the v2 Lists capability instead of being v1.x. -->
- Spotify scope reduction (start with read-only listening, ask for library when needed)
- A `/critics` directory page
- Profile "pinned reviews" feature
- A "review of the week" newsletter
- iCal export of diary entries for calendar nerds

## Removed from scope during Phase 2

These were considered and explicitly cut:

| Considered | Cut because |
|---|---|
| Album-rating "tier list" (S-tier, A-tier...) | Confuses the ½-star primary signal; could explore in a v2 alternate-scale toggle |
| Playlist-based logging ("I listened to this playlist") | Album-as-unit is the wedge; playlists dilute |
| Group chat per album | Out of scope; we don't chat |
| Cross-post-to-Twitter on every rating | Auto-cross-posting is spammy; share is opt-in per review |
| "Top 10 of [genre] this week" auto-generated lists | Editorial surface, deferred to v2 |
| Track-level rating ("I love song 3, hate song 7") | Adds significant data model + UI complexity for marginal value at MVP |

---

## Note for Phase 3 reviewers

If during Revalidation you find a feature missing from this list that *should* be deferred, or one listed here that *should* be MVP, raise it explicitly. Scope creep is the silent killer of MVPs — the goal of this document is to make every "yes, but…" conversation explicit.
