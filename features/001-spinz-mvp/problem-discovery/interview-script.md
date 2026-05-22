# User Interview Script: Spinz

> **Goal:** Validate that casual Spotify listeners (18–35) actually want a low-friction, social-graph-based way to log/share/discover albums — and that the "wanting to remember an album reaction" moment is real and frequent.
> **Duration:** 30 minutes | **Format:** 1:1 semi-structured, recorded with consent
> **Recruit:** 8–12 participants. Mix:
>   - 4× heavy Spotify users with no current music-tracking habit ("casual")
>   - 3× current users of RateYourMusic / Last.fm / AOTY ("engaged comparison")
>   - 2× active TikTok/Reddit music posters ("tastemakers")
>   - 2–3× lapsed users who abandoned Last.fm or RateYourMusic ("graveyard")

---

## Pre-interview Setup

- Confirm consent to record.
- Tell them: "I'm exploring how people discover and remember music in the streaming era. There are no wrong answers. I'm not here to pitch a product — just to learn about your habits."
- Ask for 1 sentence on how they use music day-to-day.

---

## Warm-up (5 min)

1. Walk me through how you typically discover new music. What was the last album/song you got into — how did you find it?
2. How often do you listen to a full album front-to-back, vs. shuffle/playlists/single tracks?
3. When you finish an album you really liked (or really didn't), what do you usually do next — anything? Tell anyone?

---

## Problem Exploration (10 min)

4. Tell me about the last album that made an impression on you. What happened in the next few hours / days?
5. Was there a moment where you wanted to remember your reaction or tell someone, but it didn't happen? What got in the way?
6. Where (if anywhere) do you currently keep track of music you like or want to listen to? Walk me through it.
7. When you want a recommendation for what to listen to next, where do you go? How well does it work?
8. Have you ever lost track of an album you wanted to come back to? What happened?

---

## Current Solution Probe (10 min)

9. Have you ever used Last.fm, RateYourMusic, AOTY, MusicBoard, Letterboxd, or Discord music servers? What did you like / dislike?
10. (If yes to any) Why did you stop / use less? *(If they say "felt like work" or "no one I knew was on it" — explore deeply.)*
11. Imagine the perfect tool that lived between Spotify and Letterboxd-for-music. What would it do? What would it NOT do?
12. How important is it that your friends are also on a music-tracking platform? Would you use it solo?

---

## Validation Probe (5 min)

13. If something existed where you could (in 5 seconds) log an album you just finished, rate it, and see what 3 friends thought of it — would you use it weekly? Daily? Rarely?
14. On a scale of 1–10, how much would it matter to you?
15. Would you pay for it? At what price would it feel reasonable?
16. Would you switch from your current setup (Spotify/Last.fm/Notes) — or would it have to live alongside?

---

## Wrap-up

17. Who else in your circle do you think would be into this? Why?
18. What's the biggest reason you might *not* use it, even if the features were great?
19. Anything I haven't asked that you think is important?

---

## Scoring Rubric (fill after each interview)

| Signal | Score 1–5 | Notes |
|---|---|---|
| **Frequency of "wanted to remember/share" moment** (Q4–5) | | |
| **Quality of current workaround** (Q6) — inverse: worse = higher score | | |
| **Willingness to use weekly** (Q13) | | |
| **Friend dependency / network seed potential** (Q12, Q17) | | |
| **Total** | / 20 | |

> **Score ≥ 15/20** → Strong signal. Proceed to research / build.
> **Score 10–14** → Moderate. Validate with 3–5 more interviews.
> **Score < 10** → Weak. Reconsider problem framing or target segment.

---

## Signals to Listen For

**Positive signals (note timestamp + verbatim quote):**
- They describe the "dropped moment" unprompted (Q4–5).
- They mention a workaround stack (Spotify + Notes + screenshots + Discord).
- They light up when discussing "what my friend recommended" vs. "what Spotify recommended".
- They've actively tried and abandoned a tracker — meaning the *need* is real, prior execution was wrong.

**Negative signals (red flags):**
- "I just put on Spotify and don't think about it" — no latent need.
- "If it's not in Spotify I won't use it" — feature must live where they already are.
- "I don't really know what my friends listen to and I don't care" — kills social-first thesis for this person.
- "I tried RateYourMusic and it was great" — they're not the casual segment.

---

## After All Interviews — Synthesis Tasks

1. **Affinity-map quotes** by theme: dropped moment, friend influence, workaround pain, discovery dissatisfaction.
2. **Refine JTBD statement** from verbatim language. The current draft is from the founder's framing — interviews should rewrite "When I just finished an album that left an impression…" into the user's actual words.
3. **Identify** the 2–3 *specific* hooks that came up repeatedly. These become the wedge features for the MVP.
4. **Re-score severity** in `problem-statement.md` based on aggregate signal.
5. **Update hypotheses H1–H5** as confirmed / refuted / refined.
