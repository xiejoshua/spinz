# Problem Statement Canvas: Spinz (Social Album Platform)

> Feature: `001-spinz-mvp`
> Generated: 2026-05-21 (Phase 0 — Problem Discovery)
> Status: Draft pending Phase 1 research validation

---

## The Problem

**In one sentence:**
Casual streaming-era listeners have no low-friction way to record, share, and discover album experiences with people whose taste they actually trust — so their listening stays passive and ephemeral.

**Affected user segment:**
Casual-to-engaged Spotify (and Apple Music) listeners, roughly 18–35, who already form taste identity through music but consume passively. They post about albums on TikTok/Reddit, screenshot Spotify Wrapped, and bookmark songs in Notes — but their "music life" lives in five disconnected places.

**Current situation:**
- "Liking" songs in Spotify (no album-level signal, no review, no friends-of-friends).
- Last.fm scrobbles (data without community — the social layer froze in ~2010).
- RateYourMusic for the few who tolerate a 2005 UX.
- Album of the Year (AOTY), Albums.fm, and similar attempts — small communities, fragmented.
- Notes app / Apple Notes / Discord servers for personal lists.
- Most casual listeners do none of the above.

**The friction:**
The exact pain moment is *after* finishing a great album: the listener has a reaction, wants to record it for themselves and surface it to people whose taste they trust — and there is no single place that combines (a) album-first context, (b) social-graph based, not algorithm-based, and (c) doesn't feel like a chore. They drop the impulse, listen to another playlist, and the moment evaporates.

**Consequence of not solving:**
- Streaming era has flattened music into background utility. Listeners lose the sense of a personal music library / identity.
- Discovery devolves to Spotify algorithms (homogeneous) or random TikTok virality (chaotic) — neither rewards depth.
- Critics, curators, and tastemakers have no native home → the conversation lives in low-fidelity channels (tweets, Reddit threads, group chats).
- Founders/casual-music-lovers lose the "Letterboxd moment" — the joy of seeing your friend post a 5-star review and being prompted to listen.

---

## The Job (JTBD)

**When:** I just finished an album that left an impression (good or bad), or I'm wondering "what should I listen to next."
**I want to:** record my reaction in a place that remembers it, see what people whose taste I trust thought of it, and find what to play next from them — not from an algorithm.
**So I can:** build a personal music identity over time, deepen my taste through people I respect, and rediscover joy in albums as a unit.

**Functional job:** Log albums listened to, rate them, write/read reviews, maintain a backlog/wishlist, get recommendations.
**Emotional job:** Feel like an intentional listener, not a passive consumer. Feel connected to a music community without the toxicity of mainstream socials. Feel cultured / in-the-know.
**Social job:** Be perceived by my circle as someone with thoughtful taste; share discoveries; participate in the music conversation; be findable as "the one who's always on the new stuff."

---

## Problem Validation Score

| Signal | Evidence | Weight |
|---|---|---|
| User interviews | None yet (planned in Phase 1) | High |
| Support tickets / churn data | N/A (pre-product) | High |
| Competitor evidence | **Strong.** Letterboxd valued ~$50M for film/TV. RateYourMusic exists but stagnated. AOTY, Albums.fm, MusicBoard, hi-fi.cafe — multiple small attempts, no winner has emerged. Spotify Wrapped's annual virality confirms music identity is culturally important. | Medium |
| Own observation | Reported as personal need ("dogfooding"-adjacent — competitor evidence over personal pain) | Low |
| Assumption | Hypothesis that "casual" segment (not power users) is the under-served wedge | Very Low |

**Validation strength:** **Moderate** — competitor pattern is well-documented; absence of clear winner suggests open market. Direct user research is the main gap and is the central task of Phase 1.

---

## Problem Severity

**Impact:** Medium — this is a latent / aspirational need (build music identity), not a burning pain (revenue, time, blocked work).
**Frequency:** Regular — most target users finish at least 1–3 albums per week.
**Workaround quality:** Painful-but-tolerated — most casual users have no workaround at all (the dropped-moment scenario); engaged users juggle Spotify + Last.fm + Notes.

**Severity score:** **6/10**
A latent cultural need rather than an acute pain. Severity is bounded; product success will depend more on delightful execution and community seed than on solving an emergency.

---

## Key Risks

1. **Habit-formation risk (highest).** Casual users don't currently track albums at all. The product must reduce friction below the threshold where tracking feels like "another social app to maintain." If the streaming-history integration is the wedge, getting Spotify API permissions right is load-bearing.

2. **Cold-start / network-effect risk.** A social platform delivering "social-first discovery" is worthless without a critical mass of friends/critics on it. Need a clear seeding strategy (invite mechanics, critic seeding, importable Last.fm history, etc.).

3. **Differentiation thinness vs. AOTY / Letterboxd-for-music attempts.** Several small competitors exist. "Modern UX + social-first" is a positioning, not a moat. Phase 1 must identify *why* prior attempts stalled and what concrete capability separates Spinz.

4. **Streaming-API dependency risk.** Spotify can change terms, rate limits, or build their own social layer at any time. The product is structurally exposed to platform risk.

5. **Music metadata + licensing risk.** Album metadata at scale (MusicBrainz, Discogs, Spotify catalog) has gotchas — duplicate releases, regional variants, deluxe editions, missing data. Review text + cover art may have copyright considerations.

6. **Target-segment overshoot.** "Casual Spotify users" is broad. The risk is launching to no one in particular. May need to narrow further during Phase 2 (e.g., "casual listeners who already post about music on social media").

---

## Hypotheses to Validate in Phase 1 Research

- **H1 (User behavior):** Casual Spotify listeners aged 18–35 finish ≥1 full album per week and have a recurring (>1×/week) moment of wanting to share or remember a reaction — currently unmet by Spotify.
- **H2 (Differentiator):** Recommendations from a follow-graph of trusted listeners feel *more* trustworthy / actionable than algorithmic recommendations (Spotify Discover Weekly), even if less personalized in raw signal quality.
- **H3 (Competitor gap):** Prior Letterboxd-for-music attempts (AOTY, MusicBoard, Albums.fm, hi-fi.cafe, RateYourMusic) have stalled due to specific identifiable causes: (a) UX dated, (b) power-user-only positioning, (c) absent streaming integration, (d) absent social graph mechanics, or (e) all of the above. Phase 1 must identify which.
- **H4 (Integration feasibility):** Spotify Web API supports the listening-history, playback-context, and library-sync endpoints Spinz needs, under stable rate limits and ToS-permitted use. Apple Music likewise.
- **H5 (Monetization compatibility):** A free tier with optional premium (custom lists, extended stats, no ads, importer) is acceptable to the target segment — corroborated by Letterboxd's similar model and its conversion rates.

---

## Notes on the Decision

This Problem Discovery rests on **competitor evidence**, not user research. That's an explicit choice for a side-project / portfolio scope. For a venture-backed pursuit, the Go/No-go bar would require 10–20 user interviews via the included interview script before Phase 1.

The recommendation below assumes the founder is operating in a portfolio / side-project mode where building-to-learn is the strategy.
