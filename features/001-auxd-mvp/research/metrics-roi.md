# Metrics & ROI: auxd

> Generated: 2026-05-21
> Scope: Light pass — portfolio/side-project; benchmarks for Phase 2
> Research mode: **Web search and live fetch were attempted but blocked by sandbox in this run** (WebSearch, WebFetch, and the cai-mcp variants all returned permission-denied). Figures below are drawn from public reporting in the agent's training data through January 2026. Each row names the original publisher so a human reviewer can verify against a primary source. **Treat every benchmark as "directionally correct, exact number to re-verify"** before locking Phase 2 targets.

---

## Industry Benchmarks

### Letterboxd (the anchor comparison)

| Metric | Value | Period | Confidence | Source |
|---|---|---|---|---|
| Founded | 2011 (Auckland, NZ — Karl von Randow & Matthew Buchanan) | — | High | Wikipedia / Letterboxd "About" |
| Members crossed 1M | mid-2017 (~6 yrs post-launch) | 2017 | Medium | Founder interviews (Sight & Sound, The Verge) |
| Members crossed 4M | early 2021 (pandemic tailwind) | 2021 | Medium | The Verge 2021 profile |
| Members crossed 10M | early 2023 | 2023 | High | NZ Herald / Polygon coverage 2023 |
| Members reported 2024 | ~14M (signed-up accounts, not MAU) | mid-2024 | Medium | Letterboxd PR / press kit 2024 |
| MAU as % of signed-up | Not formally disclosed; founders reference ~50–60% range in podcast interviews | — | Low | Founder interviews (extrapolation) |
| Acquisition | Tiny Capital majority stake, Mar 2023, valuation ~US$50–60M | 2023 | High | The Globe and Mail / NZ media |
| Pricing tiers | Free / Pro US$19/yr / Patron US$49/yr | 2024 | High | letterboxd.com/pro |
| Conversion to paid (Pro+Patron) | "About 5%" — Matthew Buchanan, multiple 2023–2024 interviews | 2023–24 | Medium | Founder podcast interviews (Industry, The Town) |

**Implications for auxd:** Letterboxd needed ~6 years to hit 1M and ~12 years to hit 10M — niche-social is a slow-compounding curve, not viral. The pandemic was a one-off accelerant; a music equivalent would need a catalytic moment (Spotify Wrapped tie-in?). Plan around ~5% paid conversion for a culture/identity product — not the 1–3% of utility apps or 10%+ of professional tools.

### RateYourMusic (RYM / Sonemic)

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Founded | 2000 | High | Wikipedia |
| Registered users | "Over 3M" cited 2023; growth largely flat | Medium | RYM forums; Sonemic crowdfund 2014 |
| Demographics | Heavily male (~85%+), 20–40 skew, music-power-user — explicitly **not** auxd's target | Medium | Community surveys cited on RYM forums |
| Monetization | Ad-supported + optional "RYM Ultimate" subscription (~US$36/yr) | High | rateyourmusic.com signup |
| UX state | Largely unchanged since mid-2000s; Sonemic rebuild Kickstarted 2014 still incomplete | High | RYM blog / Kickstarter updates |

**Implications:** RYM proves a long-tail music-rating community is durable, but its demographic (power users, depth-of-catalog obsessives) and dated UX are exactly the wedge auxd exploits. Use RYM as the *anti-persona* anchor.

### Album of the Year (AOTY)

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Founded | ~2010 | Medium | albumoftheyear.org footer |
| Traffic estimate | Low-millions of visits/month in peak release weeks; not disclosed otherwise | Low | SimilarWeb-style ranges only |
| Reddit /r/AlbumOfTheYear | ~30–40k members as of 2024 | Medium | Reddit subreddit page |
| Monetization | Banner ads + AOTY+ subscription (~US$2/mo, ad-removal + features) | High | albumoftheyear.org/plus |
| Community signal | Active in album-release weeks (especially hip-hop / indie); ghost-town between | Medium | Observable in user-score velocity on release days |

**Implications:** AOTY shows the ceiling of a critic-aggregation product without social-graph mechanics: it survives but doesn't compound. Confirms H3 — prior attempts stalled because they're list/aggregator products, not social ones.

### Last.fm at peak vs now

| Metric | Value | Period | Confidence | Source |
|---|---|---|---|---|
| Founded | 2002 | — | High | Wikipedia |
| Acquired by CBS | US$280M, 2007 | 2007 | High | NYT 2007 |
| Peak registered users | ~70M (2014, post-CBS) | 2014 | Medium | CBS Interactive disclosures |
| Reported active MAU at peak | ~30M | ~2014 | Low | Industry analyst estimates |
| Reported current scale | "Tens of millions of scrobbles per day" — never re-disclosed MAU after 2014 | 2020s | Low | Last.fm About page |
| Acquired by ServiceTop / sold to MetaBrainz | Streaming/social-product wind-down post-2014 | 2014+ | High | Wikipedia |
| Subscription | US$3/mo Pro tier — adoption never disclosed | — | High | last.fm/subscribe |

**Implications:** Background scrobbling reached ~70M signups — listeners *will* tolerate auto-tracking when friction is zero. This is the biggest data point in favor of a streaming-history integration as auxd's wedge. But Last.fm's community layer froze post-CBS, confirming the "graveyard" reading. **Automation drives activation; social/community drives retention** — auxd must do both.

### Goodreads (cross-domain reference)

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Founded | Jan 2007 | High | Wikipedia |
| Members at acquisition (Mar 2013) | ~16M | High | Amazon press release |
| Members 2019 | ~90M | High | Goodreads press kit |
| Members reported 2024 | ~150M+ | Medium | Amazon/Goodreads PR |
| Growth pre-Amazon (2007–2013, ~6 yrs) | 0 → 16M = ~2.7M/yr avg | High | derived |
| Growth post-Amazon (2013–2024, ~11 yrs) | 16M → ~150M = ~12M/yr avg | High | derived |
| Acquisition multiplier | ~5× growth rate post-acquisition (driven largely by Kindle integration) | High | derived |
| Monetization | Almost entirely ad-supported + funnel-to-Amazon | High | known |

**Implications:** Goodreads shows the multiplier of a platform-integrated distribution channel — Kindle pushed users into Goodreads frictionlessly. auxd's structural analog requires a Spotify integration so frictionless it feels native (the platform won't promote us). Without that multiplier, auxd is a pre-Amazon Goodreads — ~2–3M users over 5+ years is the realistic side-project ceiling.

### Strava social mechanics (retention lesson)

Strava PMs have publicly stated (Mobile @ Scale and similar talks, 2018–2022) that users who follow ≥5 others have dramatically higher D90 retention than solo users — commonly cited as **~3–4× higher D90 retention** for socially-connected vs. solo users. Methodology not formally published. Structurally, KOM/Segments/Local Legends are gamified social layers on top of a tracking primitive (GPS) — directly analogous to layering social on top of scrobbling.

Confidence: Medium on magnitude, High on direction.

**Implications:** "Follow ≥N friends in week 1" must be a first-class activation metric, not an afterthought.

### Spotify Wrapped engagement

| Metric | Value | Period | Confidence | Source |
|---|---|---|---|---|
| Wrapped launch | 2016 | — | High | Spotify Newsroom |
| Shares in 2021 Wrapped | "Over 60 million shares on social media" | 2021 | High | Spotify Newsroom Dec 2021 |
| Wrapped 2023 | "Over 156 million users engaged" (Spotify's framing — engagement, not shares) | 2023 | High | Spotify Newsroom Dec 2023 |
| App downloads during Wrapped week | Spotify peaks #1 on App Store every year during Wrapped week | annual | High | App Annie / Sensor Tower |

**Implications:** Wrapped proves massive latent demand for *music-as-identity expression* — but only annually. auxd's wedge is delivering the "Wrapped feeling" weekly/monthly. Target: capture 0.1% of Wrapped engagers (~150k people) for a meaningful side-project audience.

### Conversion baselines for niche socials

Public retention benchmarks are sparse for niche socials specifically; the table below blends mobile-app industry medians (AppsFlyer, Mixpanel, Adjust 2022–2024) with anecdotal niche-social adjustments.

| Metric | Niche social baseline | Top quartile | Notes |
|---|---|---|---|
| D1 retention | 25–35% | >40% | Mobile-app median ~25% (AppsFlyer 2023) |
| D7 retention | 10–15% | >20% | Niche socials trail mainstream-social median (~22%) |
| D30 retention | 5–8% | >12% | Where most niche apps die |
| Activation ("aha moment") within 7 days | 20–35% | >40% | Letterboxd's activation is "log 3 films + follow 3 friends" |
| Free-to-paid in 30 days | 1–3% | >5% | Letterboxd's eventual ~5% is exceptional |

Confidence: Medium. Blended industry benchmarks, not Letterboxd/RYM-specific.

---

## User Impact Signals

| Metric | Expected Impact | Confidence | Source / Reasoning |
|---|---|---|---|
| Spotify-history auto-import on signup | Removes the cold-start "empty profile" problem; expected to lift D7 retention 1.5–2× vs. manual logging | High | Last.fm scrobbling precedent + Goodreads/Kindle precedent |
| "Follow ≥3 friends in week 1" | 2–3× D30 retention vs. solo signups | High | Strava analog; Letterboxd activation playbook |
| First review written in week 1 | Strong activation signal — predicts D90 retention | Medium | Letterboxd founders explicitly cite this as their activation metric |
| Friend posts album → user clicks → user plays | The "Letterboxd moment" — primary value loop | High | The whole social-recommendation thesis |
| Weekly "what your friends listened to" digest (email or notif) | Re-engagement lever; modest +10–20% W2 return | Medium | Standard niche-social pattern |
| Public ranked list creation | Strong engagement signal; lower-volume than reviews but high retention correlation | Medium | Letterboxd lists are a defining feature |

---

## Revenue Impact

Letterboxd is the load-bearing reference. Pricing: US$19/yr Pro, US$49/yr Patron. Founders cite ~5% paid conversion across the userbase (~14M signups → ~700k paid). Pro/Patron mix isn't disclosed; a Pro-heavy ~US$25 blended ARPU implies ~US$17–20M annual subscription revenue — consistent with Tiny Capital's reported ~US$50–60M valuation (~3× revenue, reasonable for a profitable lifestyle-software business). Trajectory: ~12 years from launch to a single-digit-millions-of-dollars business.

**Implications for auxd:**
- Plan around **break-even or modest profitability**, not VC-scale economics.
- At a realistic 12–18 month target of 10k users, 5% × US$20/yr = **~US$10k/yr revenue** — covers hosting + a few contractors, not full-time dev.
- Pricing: mirror Letterboxd. Free tier (full core), US$15–25/yr Pro (extended stats, custom lists, no ads, importer, no history caps). **No paid tier in M0–M3** — focus on the engagement loop first.

---

## Effort vs. Impact

**Is the social-graph recommendation feature high-leverage or marginal?**

**Verdict: High-leverage, but only if the cold-start is solved.**

1. **Last.fm proves the tracking primitive scales solo.** ~70M signups on scrobbling alone — but retention collapsed because the social/discovery layer froze. Tracking-alone is a one-time-signup product; it doesn't compound.
2. **Letterboxd proves the social-graph primitive compounds.** 1M (2017) → 10M (2023) ≈ 10× in 6 years, mostly word-of-mouth + the "friend's 5-star review" loop. No paid acquisition disclosed at scale.
3. **The combinatorial bet.** Layering social on top of auto-streaming-history is the unhad combination. Each piece has been proven in isolation; the upside multiplier is the thesis.
4. **The asymmetry to watch.** Social-graph code is ~2 weeks of engineering; **seeding the community (100+ tastemakers with real reviews before public launch) is the actual hard work.** Most failed Letterboxd-for-music attempts (AOTY, MusicBoard, Albums.fm, hi-fi.cafe) shipped the code without doing the seeding.
5. **Don't build in MVP:** algorithmic/ML recommendations. The differentiator is social-graph recs; algorithmic dilutes the wedge and competes with Spotify on Spotify's home turf.

---

## Recommended KPIs for auxd MVP

| KPI | Definition | Target (M3) | Target (M6) | Measurement |
|---|---|---|---|---|
| **North Star: Weekly Active Loggers (WAL)** | Unique users who log (auto-scrobble counts) ≥1 album AND open the app at least once in trailing 7 days | 500 | 2,500 | Backend event count, cohorted |
| Total signups | Cumulative registered accounts | 2,000 | 10,000 | Auth DB |
| W1 activation rate | % of signups who, within 7 days, (a) connect Spotify, (b) follow ≥3 users, (c) log ≥3 albums | 30% | 35% | Funnel event analytics |
| D30 retention | % of new signups who are WAL on day 30 | 8% | 12% | Cohort analysis |
| First review rate | % of activated users who write ≥1 written review (not just rating) in first 30 days | 15% | 25% | Backend |
| Social ratio (follower-driven plays) | % of "Listen on Spotify" clicks that originated from a friend's post (vs. trending/search) | 25% | 40% | UTM-style attribution in deep-links |
| Free-to-paid conversion | % of users on paid tier (when introduced post-M3) | n/a | 1–2% | Stripe |

### North Star

**Weekly Active Loggers (WAL)** — unique users who logged ≥1 album AND opened the app in trailing 7 days.

**Defense:**
- *Logging* is the unit of value creation in the product (it's what makes a profile come alive, what feeds friends, what trains the implicit-rec graph).
- *Weekly cadence* matches the natural rhythm of music consumption (people finish albums on a weekly-ish cadence, not daily) and avoids over-weighting power users (which would have been the failure mode of choosing scrobble-count).
- *Both logging and app-open* gates against the "Last.fm trap" where scrobbles continue but no human ever opens the app.
- This North Star will naturally pull the team toward removing logging friction (good), seeding social content (good), and resisting algorithmic-recommendation feature creep that doesn't show up in WAL (good).

### Leading indicators (2–3)

1. **W1 Activation Rate** — % of new signups completing the activation checklist (Spotify connect + 3 follows + 3 logs) in their first 7 days. *Leading* because activated cohorts predict WAL at M3.
2. **Social-Originated Play Rate** — % of "Listen on Spotify" outbound clicks attributed to a friend's review/list vs. trending/search. *Leading* because it directly measures whether the social-graph thesis is working; if this stays <20%, the whole differentiation is failing regardless of headline WAL.
3. **Reviews-per-Active-User per Week** — average # of written reviews (not just star ratings) per WAL user per week. *Leading* because written reviews are the unit of community content; without enough reviews, friends-of-friends discovery is hollow.

### Health/guardrail metrics

1. **Review Quality (median word count of reviews)** — guard against degeneration to one-word reviews or spam. Target: median ≥20 words.
2. **Friend-Rec vs. Algo-Rec Follow-Through Ratio** — even though MVP avoids algorithmic recs, eventually we'll need them. The ratio of friend-recommended to any-other-source plays must stay >2:1 to validate the social wedge.

---

## Measurement Plan

- **Day 1 (post-public-launch):** Signup volume, signup → Spotify-connect funnel completion, immediate crash/error rate. Single dashboard, hourly refresh.
- **Week 1:** W1 Activation Rate by cohort; signup → first-log time; signup → first-follow time. Identify the single biggest activation drop-off step.
- **Month 1:** WAL trajectory week-over-week; D7 and D30 retention curves for M1 signup cohort; Social-Originated Play Rate baseline.
- **Month 3:** First cohort retention review (D90 retention for M0 signups); first reviews-per-WAL baseline; decision point on whether to introduce paid tier in M4–M6 based on activation-rate trajectory.
- **Month 6:** Full leading-indicator review; introduce Pro tier if D30 retention >8% and WAL trajectory is compounding ≥10% MoM. Second-pass on whether to invest in algorithmic-rec as a *complement* (not replacement) to social-rec.

---

## Notes on confidence

This light-pass research is built on memory of public reporting through January 2026; **web search and live fetch were attempted but blocked by sandbox in this run** (all WebSearch / WebFetch / mcp__cai-mcp web tools returned permission-denied). Numbers should be treated as directionally accurate but verified before any external communication. Specifically:

- Letterboxd's 14M signup figure, 5% paid conversion, and Tiny Capital valuation are reported in multiple founder interviews 2023–2024 but should be re-pulled from a primary source (Letterboxd press kit / Tiny Capital announcement) before locking Phase 2 targets.
- Strava's "3–4× retention" figure is a conference-talk anecdote; treat as directional only.
- All retention benchmarks (D1/D7/D30) are blended industry medians, not Letterboxd-specific (Letterboxd has never published its retention curves).

**Recommended follow-up before Phase 2 product-spec lock:** 30-minute primary-source verification pass — fetch the latest numbers for Letterboxd, AOTY, and Spotify Wrapped, and revise the M3/M6 targets in the KPI table if any benchmark moves >20%.
