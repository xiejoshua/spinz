# Review Log: Spinz MVP

> Feature: `001-spinz-mvp` | Status: OPEN
> Started: 2026-05-21

## Current Status: ✅ APPROVED — LOCKED 2026-05-21T23:55:00Z

**Approved by user after 3 revisions.**

**Final document inventory:**

| Document | Status | Last Modified |
|---|---|---|
| product-spec.md (main PRD) | LOCKED v1.3 | 2026-05-21 |
| user-stories.md (32 stories) | LOCKED v1.3 | 2026-05-21 |
| user-journeys.md (5 journeys) | LOCKED v1.3 | 2026-05-21 |
| data-model.md (15 entities) | LOCKED v1.3 | 2026-05-21 |
| notification-taxonomy.md (18 active types) | LOCKED v1.3 | 2026-05-21 |
| seeding-strategy.md | LOCKED v1.3 | 2026-05-21 |
| success-metrics.md | LOCKED v1.3 | 2026-05-21 |
| out-of-scope.md | LOCKED v1.3 | 2026-05-21 |
| decision-log.md (45+ decisions) | LOCKED v1.3 | 2026-05-21 |
| wireframes/ (5 HTML files) | LOCKED v1.3 | 2026-05-21 |
| README.md (index) | LOCKED v1.3 | 2026-05-21 |
| digest.md | LOCKED v1.3 | 2026-05-21 |

**Status: LOCKED — Ready for SpecKit Bridge (Phase 4)**

---

## Current Status (historical lines above this point, until lock): UNDER REVIEW (Revisions #1 + #2 + #3 applied — awaiting approval)

## Open Questions Resolution

| # | Question | Decision | Rationale | Resolved in Revision |
|---|---|---|---|---|
| Q (decision-log #7) | Curated user-created Lists in MVP or v2? | **MVP** (full Letterboxd parity) | Founder elevated Lists as load-bearing for the wedge — without Lists, the social-graph discovery loses an expressive surface | Revision #1 |
| Q (decision-log #10) | Just-finished auto-detection: manual only, or auto-prompt? | **Auto-prompt at MVP** (opt-out default ON) | Founder accepted privacy tradeoff; moments captured by auto-prompt are highest-value moments | Revision #1 |
| Q (decision-log #12) | Onboarding Spotify connect required or skippable? | **Skippable, no degraded-mode framing** | Forcing OAuth at signup tanks signups; product works fully without Spotify | Revision #1 |
| Q (decision-log structural) | Terminology — "Liked" / "Heart" vs alternative? | **Renamed to "Awarded" / "Award"** | Founder preferred terminology that implies curation, not casual reaction | Revision #1 |

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-21 | Lists elevated from v2 to MVP scope | Load-bearing for the social-graph + album-as-unit wedge |
| 2026-05-21 | Auto-prompt for just-finished detection enabled at MVP (opt-out default ON) | Highest-value moments are immediate post-listen; manual-only loses them silently |
| 2026-05-21 | Spotify connect explicitly skippable at signup | Avoid OAuth-friction signup loss; product works fully without Spotify |
| 2026-05-21 | Rename "Liked"/"heart"/"hearted" → "Awarded"/"Award" globally | More-deliberate connotation aligns with curated personal-standouts signal |

## Change History

v1.0 → v1.1: Lists added to MVP (6 stories, 2 entities, 1 journey); Auto-prompt added (1 story, 1 entity, 1 notification type, 1 journey); Spotify skip elevated to first-class; Heart → Award rename across all docs.

v1.1 → v1.2: All 30 open questions resolved with locked decisions (10 main + 20 supporting-doc). FRs 028–030 added. User stories S-A4, S-C3, S-F1, S-G1, S-G4 expanded with new acceptance criteria. Supporting-doc "Open questions" sections converted to "Resolved decisions". Zero open questions remain at spec level.

v1.2 → v1.3: Removed soft "say more" prompt; split Award/Like terminology (Award = self-curation 🏅, Like = social engagement 👍); added Likes on reviews + Most Liked sort + S-C4 user story + ReviewLike entity + FR-031/032; reverted Lists from MVP back to v2 (de-elevated R1 — removed FR-021..025, Cluster I S-I1..S-I6, List+ListItem entities, N-019/020, Journey 4.5). Net: 32 stories, 15 entities, 5 journeys, 18 active notifications, 27 active FRs.

## Revision History

## Revision #1 — 2026-05-21

**User feedback (verbatim):**
> Onboarding flow should prompt for Spotify auth + auto-import last 30 days, but this step should be skippable. The rating scale should be 1/2 star, like Letterboxd. Enable auto-prompt for MVP. Lists should not be deferred. Ratings/reviews are public by default. "Liked" hearts are public signals - they should be called "Awards".

**Changes applied:**

| File | Change Type | Description |
|---|---|---|
| decision-log.md | Modify | Updated rows 7 (Lists → MVP), 10 (auto-prompt enabled), 12 (skippable Spotify); added terminology row; added Revision row v1.1 |
| product-spec.md | Modify | §3.1 (Award rename), §3.2 (auto-prompt added), §3.6 (skippable Spotify), §3.7 (Lists ref); ADD §3.8 (Lists capability); FR-002 (skippable), FR-004 (Award rename); ADD FR-021–FR-027 (Lists + auto-prompt + Settings→Integrations); §6 out-of-scope (remove Lists + auto-prompt, add collaborative-lists to v1.x); §9 (top decisions reflected) |
| user-stories.md | Modify + Add | S-A2 reworded for skippable; S-B3 renamed Heart→Award; S-B5 Award rename; S-G3 expanded (auto-prompt opt-out + quiet hours); ADD S-B6 (auto-prompt user story); ADD Cluster I with S-I1–S-I6 (Lists); coverage table + counts updated |
| user-journeys.md | Add + Modify | Journey 1 alt-path rewritten (no degraded-mode); ADD Journey 1.5 (auto-prompt); ADD Journey 4.5 (Lists creation); cross-journey notes updated |
| data-model.md | Modify + Add | Entity inventory + User block + DiaryEntry.hearted→awarded + Review.reactions renamed; ADD List, ListItem, JustFinishedPrompt entities; relationship diagram + indexes updated |
| notification-taxonomy.md | Modify + Add | N-004 renamed review.hearted→review.awarded; ADD N-018 (just_finished.prompt), N-019 (list.awarded), N-020 (list.added_to); defaults summary + settings UI updated for new types and auto-prompts |
| out-of-scope.md | Remove + Add | Removed Lists + Auto-prompt from v2 deferrals; added Collaborative Lists + Auto-list-generation to v1.x candidates |
| wireframes/03-log-sheet.html | Modify | "Heart" row → "Award" row; ♡ → 🏅 |
| wireframes/02-home-feed.html | Modify | ♥ heart icons → 🏅 award icons in all 4 feed entries; CSS class heart→award |
| wireframes/04-album-detail.html | Modify | "Friends who rated this" → "Friends who rated & awarded this" |
| product-spec/README.md | Modify | Counts updated (37 stories, 20 notifications, 16 entities, 6 journeys); top-decisions list reflects Revision #1 |
| product-spec/digest.md | Modify | Revision #1 changes noted in header; scope + structural decisions updated |
| README.md (feature root) | Modify | Top-decisions section reflects Revision #1 |

**Agent notes:**
- "Award" terminology applied to both DiaryEntry-level (personal standout signal, boolean) and Review-level (engagement count from other users) for consistency. Same semantic primitive, contextually distinguished.
- Auto-prompt scope is conservative: in-app default ON, push default OFF, opt-out is one-tap from the prompt itself.
- Lists at MVP includes: create, add albums, reorder when ranked, per-list visibility, share with OG card, browse from social graph, award lists. Excludes: collaborative editing (v1.x), auto-generated lists (v1.x), drag-and-drop covers (v1.x — using picker-from-existing-items at MVP).
- "Awards" on different objects: a User can Award an Album (in their DiaryEntry — personal signal); other Users can Award the User's Review (engagement); other Users can Award a User's List (engagement). Same UI primitive (medal icon), three contexts.
- Out-of-scope.md uses HTML comment markers to preserve the removed rows for audit trail rather than deleting them outright.

---

## Revision #2 — 2026-05-21

**User feedback (verbatim):**
> Lock in these as decisions. Follow your recommendations.

**Context:** After Revision #1, the orchestrator surfaced the 10 product-spec.md §10 open questions and 20 supporting-doc open questions with concrete recommendations. Founder chose to lock all 30 as decisions.

**Changes applied:**

| File | Change Type | Description |
|---|---|---|
| decision-log.md | Add + Modify | Renamed "Twelve" Open Questions → "Open Questions"; added Q13–Q22 (10 rows) with locked decisions and rationale; added 4 new subsection tables (Notification taxonomy NT-1..5, Seeding strategy SS-1..5, Data model DM-1..5, User journeys UJ-1..5); added Revision v1.2 row |
| product-spec.md | Modify + Add | §10 converted from "10 open questions" to "10 resolved questions" summary; FR-002 scopes locked; FR-027 expanded with disconnect immutability; ADD FR-028 (Edition selector), FR-029 (handle policy), FR-030 (review edit policy) |
| user-stories.md | Modify | S-A4: critic-seed pre-checked + ≥3 critics in top 6 (Q13, UJ-2); S-C3: edit history hidden, latest+badge surface (Q17); S-F1: Edition selector AC + fresh-release lazy-fetch (Q15, Q21); S-G1: full handle policy AC (Q16); S-G4: report→moderation flow clarified |
| notification-taxonomy.md | Replace | "Open questions" section → "Resolved decisions" section with NT-1..5 each crisp one-liner |
| seeding-strategy.md | Replace | "Open questions" section → "Resolved decisions" section with SS-1..5 |
| data-model.md | Replace | "Open questions deferred to Phase 5" → "Spec-level decisions locked" (DM-1..5) + "Remaining Phase 5 (technical) decisions" |
| user-journeys.md | Replace | "Open questions" section → "Resolved decisions" section with UJ-1..5 |
| product-spec/README.md | Modify | Status v1.1 → v1.2; counts updated (30 FRs; 0 open questions at spec level); "Open questions for Phase 3" section converted to "Open questions resolved" |
| product-spec/digest.md | Modify | Revision #2 changes added to header |
| README.md (feature root) | Modify | Top-decisions list extended with 6 new Revision #2 locks |

**Agent notes:**
- All 30 open questions surfaced were resolved; none re-opened during the revision pass.
- Several FRs were ADDED (028–030) rather than modifying existing ones, because the resolved questions introduced behavior that wasn't previously covered (Edition selector for album detail, handle change policy, review edit policy).
- Story expansions kept the G/W/T pattern; ACs added to existing stories rather than creating new stories.
- Phase 5 (Plan) still has technical decisions to make (Atlas Search tuning, fan-out load test, GDPR audit log schema, etc.). Those are technical, not spec-level, and are documented in decision-log.md §Decisions deferred to Phase 5.
- The spec is now production-grade in terms of clarity — every behavior has either an FR, a user story AC, or a decision-log entry pointing to the authoritative source.

---

## Revision #3 — 2026-05-21

**User feedback (verbatim):**
> No need for the soft prompt to "say more" if review <20 chars. Users should also be able to like reviews, and reviews should be able to be sorted by Most Liked. Let's also push Lists to v2.

**Changes applied:**

| File | Change Type | Description |
|---|---|---|
| decision-log.md | Modify | Row 5 (review prompt) updated; row 7 (Lists) reverted to v2; terminology row updated for Award/Like semantic split; Revision v1.3 row added |
| product-spec.md | Modify + Add | §3.1 (Award clarified as self-only); §3.3 (drop "say more" prompt; add Likes + sort); §3.7 (Lists ref removed); §3.8 (Lists removed); §6 out-of-scope (Lists back to v2); FR-004 wording; REMOVE FR-021..FR-025 (Lists); ADD FR-031 (Like a review) + FR-032 (Sort reviews); top decisions list refreshed |
| user-stories.md | Modify + Add + Remove | S-B3 reworded (Award = self-only); S-C1 (drop soft prompt AC); S-C2 (add sort options AC); ADD S-C4 (Like a review); REMOVE Cluster I S-I1..S-I6 (Lists); coverage table + counts updated |
| user-journeys.md | Remove | Journey 4.5 (Lists) removed; cross-journey notes updated to clarify Award/Like distinction |
| data-model.md | Modify + Add + Remove | Entity inventory: List+ListItem marked removed; Review.reactions renamed (award_count→likes_count, recent_awarders→recent_likers); REMOVE List+ListItem entities; ADD ReviewLike entity; relationship diagram + indexes updated |
| notification-taxonomy.md | Modify + Remove | N-004 renamed (review.awarded→review.liked); REMOVE N-019 + N-020 (list notifications); settings UI updated; defaults summary recount |
| out-of-scope.md | Add + Remove | Lists row added back to v2 deferrals (with R1↔R3 history); collaborative-lists + auto-list-generation removed from v1.x (rolls up into v2 Lists capability) |
| wireframes/02-home-feed.html | Modify | Action-row engagement counts: 🏅 N → 👍 N (4 entries) — entry-owner Award badge in stars row stays as 🏅 |
| wireframes/04-album-detail.html | Modify | Reviews section: added "Sort: Newest ▾ · Most Liked · Highest-Rated" header; added 👍 N count per review snippet |
| product-spec/README.md | Modify | Status v1.2 → v1.3; counts updated (32 stories, 27 active FRs, 15 entities, 5 journeys); top decisions extended |
| product-spec/digest.md | Modify | Revision #3 changes in header |
| README.md (feature root) | Modify | Top decisions extended for R3 changes |

**Agent notes:**
- The Award/Like semantic split is the most consequential change. Award (🏅) is now strictly a self-directed signal on your own DiaryEntry ("this is one of my standouts in my diary"). Like (👍) is strictly an other-directed signal on someone else's Review ("I appreciate this writeup"). The two are unrelated data fields, unrelated icons, unrelated notification types. This matches Letterboxd's "heart on log + like on review" model rather than our unified-Award attempt in R1.
- A new entity `ReviewLike` was introduced (separate from the counter on Review) to support idempotent like-toggle, "did this user like this review" check, and un-like behavior. Counter on Review is denormalized for the Most-Liked sort.
- Lists were elevated → returned: R1's work (Cluster I stories, FR-021..025, List/ListItem entities, N-019/020, Journey 4.5) is preserved in git history at commit-of-R1 if Lists return in a future revision. The current spec deliberately leaves FR-021..025 and N-019/020 as reserved-gaps rather than renumbering, to preserve audit trail.
- The build estimate is back to 3–6 months — the R3 scope reduction (~5–8 weeks of Lists work) nets out against the small S-C4/FR-031/FR-032 addition.
- Wireframes were updated to distinguish the two icons: 🏅 next to the rating stars = entry owner's Award badge; 👍 N as a count on the review = social Like engagement.

---
