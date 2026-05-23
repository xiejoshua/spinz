# Data Model: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 (high-level — final schemas in Phase 5)
> Related: [product-spec.md](./product-spec.md) | [user-stories.md](./user-stories.md) | [decision-log.md](./decision-log.md)

This is the **conceptual** data model — entities, relationships, and key fields needed to support all user stories. Final MongoDB collection design, indexes, denormalization choices, and migration plan are deferred to Phase 5.

---

## Entity Inventory

| Entity | Purpose | Owner |
|---|---|---|
| **User** | Account identity, profile, settings | self |
<!-- CR-001: MusicProvider remains in the schema but its purpose at MVP is empty-array; entity is preserved for v2 streaming integration. -->
| **MusicProvider** | Per-user credential block for an external streaming provider — *empty at MVP per CR-001; preserved as deferred surface area for v2 streaming integration* | User |
| **Album** | Canonical album record (catalog cache; MusicBrainz primary + Discogs fallback per CR-001) | system |
| **DiaryEntry** | A single logged listen — the central activity record | User |
| **Backlog** | A user's private "Up Next" list of albums | User |
| **BacklogItem** | One album on a Backlog | User |
| ~~**List**~~ | ~~A user-created curated list of albums (Letterboxd-style)~~ — *added R1, removed R3 (deferred to v2)* | — |
| ~~**ListItem**~~ | ~~One album on a List~~ — *added R1, removed R3* | — |
| **Review** | The text content attached to a DiaryEntry (1:1 optional) | User |
| **Follow** | Asymmetric follow relationship between two Users | User |
| **Block** | Block relationship between two Users | User |
| **Report** | User-filed report of content or another user | User → system |
| **Notification** | A notification record (in-app/email/push surfaces derived) | User |
| **NotificationPreferences** | Per-user, per-type notification settings | User |
<!-- sync-fix L2-030 (Run #11): PushSubscription added — shipped Session 20 (T136 WebPush adapter). -->
| **PushSubscription** | Per-device VAPID push registration; 410-Gone deletes dead sub on send | User |
<!-- CR-001: JustFinishedPrompt marked DEFERRED-TO-V2 — entity preserved in schema; nothing wires it at MVP. -->
| **JustFinishedPrompt** | *(DEFERRED-TO-V2)* Pending or dismissed "just-finished" auto-prompt for the user — preserved as deferred surface area for v2 streaming integration | User |
| **SuggestedFollow** | A precomputed follow suggestion (refreshed offline) | system |
| **CriticSeed** | Editorial seed roster pre-followed/recommended for new users | system |

---

## Entity Sketches

> All entities carry: `_id` (ObjectId or KSUID), `_schema_version: int`, `created_at: datetime`, `updated_at: datetime`. Soft-delete uses `deleted_at: datetime?` (null = active).

### User
```
User {
  id                       # KSUID, used in URLs as `@handle` resolves to id
  handle                   # @-name, unique, 3–24 chars, /^[a-z0-9_]+$/
  email                    # unique, lowercased
  # CR-001: nullable-if-OAuth-only branch deferred — all MVP users have a password_hash (email+password is the only signup path).
  password_hash            # bcrypt, NOT NULL at MVP per CR-001; nullable branch returns in v2 when streaming-OAuth signup returns
  display_name             # human-readable, ≤40 chars
  bio                      # ≤140 chars
  avatar_url               # CDN URL
  private_profile          # bool, default false  (sync-fix Run #3 L5-004: was is_private_profile in earlier drafts; aligned to code)
  # CR-002: SS-3 opt-in flag for the "X just joined" invite-landing ticker. Default OFF for L-12..L-1 cohorts (preserves launch-wave narrative), ON for L 0 and later. Settings → Privacy surface.
  visible_in_just_joined   # bool, default depends on signup_cohort (false for cohorts L-12..L-1, true for L 0+); user-tunable in Settings → Privacy
  default_entry_visibility # enum: public | followers | private, default "public"
  default_backlog_visibility # enum: public | followers | private, default "private"
  keep_backlog_after_log   # bool, default false
  status                   # enum: active | suspended | deleted (grace period) | hard_deleted
  deletion_scheduled_for   # datetime, set when user requests deletion
  last_seen_at             # datetime  (sync-fix Run #3 L5-004: was last_login_at; renamed since field updates on activity, not just login)
  handle_created_at        # datetime, set on account creation
  handle_changed_at        # datetime, None until first handle change (FR-029)  (sync-fix Run #3 L5-004: was last_handle_change; symmetric with created_at)
  session_version          # int, default 1 — incremented on password change / forced logout to invalidate prior cookies
  # CR-001: auto_prompt_* fields deferred to v2 with the just-finished prompt cluster. Fields preserved in schema; writers default them but no MVP reader consumes them.
  auto_prompt_enabled      # bool, default true — *(DEFERRED-TO-V2: show in-app prompt when streaming provider detects a finished album)*
  auto_prompt_push_enabled # bool, default false — *(DEFERRED-TO-V2: also send push for auto-prompts)*
  notification_preferences # ref → NotificationPreferences
  # CR-001: music_providers is an empty array at MVP. Field preserved so v2 streaming integration can attach without a migration.
  music_providers          # array<MusicProvider>, ALWAYS [] at MVP (no streaming integration; see decision-log R4 / CR-001)
  counts (derived/cached): { followers, following, entries, auxed, backlog_size, reviews, likes_given }
}
```

<!-- CR-001: MusicProvider sub-doc schema preserved verbatim for v2 streaming integration. At MVP the User.music_providers array is always []; no instances of this sub-doc exist in the database. -->
### MusicProvider *(DEFERRED-TO-V2 sub-document — schema preserved)*
Stored as an embedded sub-document on User (one per provider). **At MVP no user has any MusicProvider sub-docs — `User.music_providers` is always `[]`. The schema is preserved so v2 streaming integration can attach instances without a migration.**
```
MusicProvider {
  provider                 # enum: spotify | apple_music | lastfm_import (all v2; none populated at MVP)
  external_id              # provider's user ID
  display_name             # provider's display name at connect time
  access_token_encrypted   # symmetric-encrypted with KMS key
  refresh_token_encrypted  # symmetric-encrypted; null for lastfm_import (no refresh)
  scopes                   # array of scope strings
  connected_at             # datetime
  last_synced_at           # datetime
  status                   # enum: active | revoked | error
}
```

<!-- CR-001: Album entity — spotify_id dropped from MVP schema; discogs_release_id added as fallback identifier. -->
### Album
Canonical catalog cache (MusicBrainz primary + Discogs fallback). Records are the album identity anchor.
```
Album {
  id                       # KSUID
  mbid                     # MusicBrainz release-group MBID (canonical key when available)
  discogs_release_id               # Discogs release ID (fallback identifier when MBID unavailable) — added by CR-001 (replaces spotify_id)
  apple_music_id           # nullable, populated when Apple Music ships (v2)
  title
  artist_credit            # display string, e.g. "Kendrick Lamar & SZA"
  artists                  # array<{ name, mbid?, discogs_release_id? }>
  release_date             # YYYY-MM-DD or YYYY-MM or YYYY (granularity preserved)
  release_year             # int, denormalized for sort
  primary_type             # enum: album | ep | single | compilation | live | other
  cover_art_url            # primary, CDN URL (Cover Art Archive at MVP per CR-001)
  cover_art_blurhash       # for placeholder
  tracklist                # array<{ position, title, duration_ms }>  # CR-001: per-track streaming IDs dropped
  duration_ms              # total
  label
  source_provider          # enum: musicbrainz | discogs (which provider seeded this record — for audit)
  cached_at                # datetime
  cache_expires_at         # datetime (7d default)
  popularity_score         # 0–100, derived (used for search ranking)
  rating_count             # int, denormalized (used by Atlas Search popularity boost via log1p(rating_count))
  rating_counts_cache      # { 0_5: int, 0_5: int, ... }  (precomputed histogram for album detail page)
  candidate                # bool, default false — true marks Discogs-sourced rows pending MBID reconciliation by the T065 weekly worker (CR-001 + §6)
}
```

<!-- sync-fix L4-008 (Run #5): inventory caught up to the §6 wave. `Album.candidate` (T063), `rating_count` denormalization (T068 Atlas index popularity boost), and the supporting Atlas Search index runbook at `apps/api/migrations/README.md` are all in code; the schema sketch + index table above now reflect them. -->


### DiaryEntry — the central activity record
```
DiaryEntry {
  id                       # KSUID
  user_id                  # FK → User
  album_id                 # FK → Album
  logged_at                # datetime (the listen date, not creation date)
  rating                   # decimal 0.5–5.0 in 0.5 increments, nullable
  auxed                    # bool, default false — user's "this is one of my standouts" signal
                           # (renamed from "hearted" in Revision #1, 2026-05-21)
  review_id                # FK → Review, nullable
  visibility               # enum: public | followers | private, default = user's default
  # CR-001: source enum reduced to manual at MVP. The reserved values (streaming_import, just_finished_prompt, lastfm_import, streaming_prefill) are kept in the enum for v2 forward-compatibility but no MVP writer emits them.
  source                   # enum at MVP: manual (only). Reserved for v2: streaming_import | just_finished_prompt | lastfm_import | streaming_prefill
  relisten                 # bool, true if user has a prior entry for this album
  device                   # enum: web | mobile_web | api (for analytics)
  edited_at                # datetime, nullable
  deleted_at               # datetime, nullable (soft delete; 30d grace)
}
```

### Review
Separate document so we can support edit history / soft deletes without cluttering DiaryEntry.
```
Review {
  id                       # KSUID
  user_id                  # denormalized for fast access checks
  album_id                 # denormalized
  diary_entry_id           # FK → DiaryEntry
  body                     # markdown-safe subset (bold, italic, line breaks; ≤4000 chars)
  body_html_cached         # rendered HTML (server-side render at write time)
  visibility               # inherits from DiaryEntry but kept here for filterability
  word_count               # derived
  reactions                # nested: { likes_count, recent_likers: [user_ids] }
                           # rename history: heart_count (v1.0)
                           #   → aux_count (Revision #1)
                           #   → likes_count (Revision #3 — Aux/Like semantic split)
                           # Likes are social engagement from OTHER users on this review.
                           # The DiaryEntry.auxed field is a separate concept (self-curation).
  edited_at                # datetime, nullable; set on each edit (sync-fix L2-022, Run #9)
  deleted_at               # datetime, nullable; soft-delete with 30d grace before hard-delete cascades ReviewLikes (sync-fix L2-022, Run #9)
}

### ReviewLike
A per-user record of who liked which review, used for: idempotent toggle, "most liked" sort within follow-graph, and unlike behavior. Added in Revision #3.
```
ReviewLike {
  id                       # KSUID
  review_id                # FK → Review
  user_id                  # FK → User (the liker)
  created_at
  # uniqueness: (review_id, user_id) — a user can like a review at most once
  # delete on un-like; soft-delete not required (the social signal is the count, not the history)
}
```
```

### Follow
Asymmetric: A → B means A follows B.
```
Follow {
  id                       # KSUID
  follower_id              # FK → User (A)
  followee_id              # FK → User (B)
  state                    # enum: active | pending (if followee is private) | rejected
  created_at
  approved_at              # datetime, nullable
  # sync-fix L2-031 (Run #11): source allowlist added — shipped Session 18 on POST /users/{handle}/follow body.
  source                   # literal allowlist of 6 values {onboarding_preselected, onboarding_mutual_taste, suggestion, profile, invite, manual}; defaults to "profile" when not specified. Drives (a) T142 onboarding-wave N-001 suppression and (b) PostHog `social.follow` funnel facet.
}
```

### Backlog & BacklogItem
Backlog is a per-user singleton (one Backlog per User). Each item is an album reference with ordering.
```
Backlog {
  id                       # KSUID
  user_id                  # unique (1:1 with User)
  visibility               # enum: public | followers | private, default = user's default_backlog_visibility
}

BacklogItem {
  id
  backlog_id               # FK → Backlog
  album_id                 # FK → Album
  added_at
  position                 # int, user-defined order
  per_item_visibility      # enum: inherit | public | followers | private (override)
  notes                    # text, optional (≤500 chars)
}
```

<!-- List & ListItem entities were added in Revision #1 and removed in Revision #3.
     Lists deferred to v2 — see out-of-scope.md and decision-log.md row 7.
     Schema preserved in git history (R1 = v1.1). -->

<!-- CR-001: JustFinishedPrompt status changed to DEFERRED-TO-V2. Schema and semantics preserved verbatim so v2 streaming integration can re-wire the collection without a migration. The polling worker (T123 in tasks.md) and prompt-card UI are unwired from the MVP. -->
### JustFinishedPrompt *(DEFERRED-TO-V2 entity — schema preserved)*

**Status:** DEFERRED-TO-V2 (CR-001 / R4, 2026-05-22). Originally added in Revision #1 to support the just-finished auto-prompt at MVP. CR-001 deferred the streaming integration this entity depends on, so the entity is unwired from the MVP. The collection schema, index, and any backing code remain so v2 can re-activate without a migration. No MVP code path writes or reads JustFinishedPrompt instances.

```
JustFinishedPrompt {
  id
  user_id                  # FK → User
  album_id                 # FK → Album (the detected just-finished album)
  detected_at              # datetime (when the streaming provider's recently-played showed it finished)
  source                   # enum: streaming_recently_played | streaming_currently_playing_done  (CR-001: renamed from spotify_*)
  state                    # enum: pending | dismissed | logged | expired
                           # expired = >24h since detected without action
  dismissed_at             # datetime, nullable
  logged_diary_entry_id    # FK → DiaryEntry, nullable (set when user logs from this prompt)
}
```

**Semantics (preserved for v2 re-activation):**
- Auto-prompt generation runs as a background task per user (poll interval: 5–15 min while user has an active session in last 24h; lower otherwise).
- A user sees at most one active prompt at a time (latest finished album).
- Prompts expire after 24h; dismissed prompts don't re-fire for the same album for 30 days.
- Respects `User.auto_prompt_enabled` (default ON) and quiet hours.

### Block
```
Block {
  id
  blocker_id               # FK → User
  blockee_id               # FK → User
  created_at
}
```

### Report
```
Report {
  id
  reporter_id              # FK → User
  target_type              # enum: user | diary_entry | review
  target_id                # KSUID of target
  reason                   # enum: harassment | spam | impersonation | self_harm | other
  detail                   # text, ≤2000 chars
  status                   # enum: open | reviewing | actioned | dismissed
  resolved_at              # datetime, nullable
  resolution_note          # text, nullable (admin-only)
}
```

### Notification
A single notification record; surfaces (in-app / email / push) are derived from prefs.
```
Notification {
  id
  user_id                  # recipient
  type                     # enum: follow | review_reply | follow_request_approved | digest_weekly | system_announcement | ...
  payload                  # type-specific structured data (actor_user_id, album_id, etc.)
  channel_dispatch_state   # { in_app: pending|sent|read, email: pending|sent|skipped, push: pending|sent|skipped }
  created_at
  read_at                  # datetime, nullable
}
```

Notification taxonomy enumeration is in [notification-taxonomy.md](./notification-taxonomy.md).

<!-- CR-001: NotificationPreferences — review_heart is now review_liked (R3 split, preserved); just-finished and spotify-reconnect lines removed because those types are deferred. -->
### NotificationPreferences
Embedded on User, but extracted here for clarity.
```
NotificationPreferences {
  per_type: {
    follow:           { in_app: true,  email: false, push: true  }   # default
    follow_request:   { in_app: true,  email: false, push: true  }
    review_liked:     { in_app: true,  email: false, push: false }
    review_reply:     { in_app: true,  email: false, push: false }  # v2 feature, accepted
    weekly_digest:    { in_app: false, email: true,  push: false }
    system_announce:  { in_app: true,  email: true,  push: false }
  }
  quiet_hours: { enabled: false, start: "22:00", end: "08:00", tz: "user_tz" }
  email_address: # falls back to User.email when unset
}
```

<!-- sync-fix L2-030 (Run #11): PushSubscription entity added — shipped Session 20 (T136 WebPush adapter). Adapter deletes the row on 410-Gone responses; one row per device endpoint. -->
### PushSubscription
Per-device VAPID web-push registration. The web-push adapter loads these rows per-recipient and fans out a push for each; the adapter DELETEs any row that returns 410 Gone (the browser revoked the subscription). One row per device per user.
```
PushSubscription {
  id                       # KSUID
  user_id                  # FK → User; indexed
  endpoint                 # str — browser-provided push URL; UNIQUE
  p256dh_key               # str — client public key
  auth_secret              # str
  user_agent               # str | None — diagnostic
  created_at               # datetime
  last_used_at             # datetime | None — bumped on successful send (re-POST is idempotent: updates last_used_at instead of inserting)
}
```
Indexes: `(user_id)` indexed for fan-out; `(endpoint)` UNIQUE for dedup.

<!-- sync-fix L2-026 (Run #10): SuggestedFollow → Suggestion + separate SuggestionDismissal. Session 17 T104 shipped two collections (suggestions + suggestion_dismissals) with TTL indexes 7d / 30d. The original single-entity sketch is preserved below as historical note. -->
### Suggestion
Precomputed by the `compute_suggestions_for_user` worker (T104); refreshed N hours per user via arq cron.
```
Suggestion {
  id
  user_id                  # who the suggestion is for
  suggested_user_id        # who is being suggested
  score                    # float in [0, 1] — weighted combo of mutual-taste 40% + followed-by-followed 30% + shared-seed 15% + label/genre 10% + recency 5%
  reasons                  # list of rationale tags: mutual_taste | followed_by_followed | shared_seed | label_genre | recency (sync-fix L2-027, Run #10 — multiple co-firing rationales per suggestion)
  computed_at              # datetime; TTL 7 days (auto-clean stale rows)
}
```
Indexes: `(user_id, score DESC)` for read; `(user_id, suggested_user_id)` unique; `computed_at` TTL 7 days.

### SuggestionDismissal
User-dismissed suggestions; the read endpoint excludes these for 30 days. Separate collection (rather than a `dismissed_at` field on `Suggestion`) so the TTL semantics can differ (Suggestions: 7d staleness; Dismissals: 30d cool-down).
```
SuggestionDismissal {
  id
  user_id                  # the viewer who dismissed
  suggested_user_id        # whose suggestion was dismissed
  dismissed_at             # datetime; TTL 30 days
}
```
Indexes: `(user_id, suggested_user_id)` unique compound; `dismissed_at` TTL 30 days.

<!-- HISTORICAL — pre-Session-17 single-entity sketch (kept for changelog clarity):
SuggestedFollow { id, user_id, suggested_user_id, score, reason: enum {mutual_taste|followed_by_followed|shared_label|critic_seed|invited}, dismissed_at, created_at }
The shipped split is two collections (different TTL semantics) and `reasons: list[str]` (multiple co-firing labels per row).
-->


### CriticSeed
Static-ish editorial list of accounts pre-recommended/pre-followed at onboarding.
```
CriticSeed {
  id
  user_id                  # the actual User account that is a seed; strict unique index (one CriticSeed per User)
  priority                 # 1–100, used for ranking in the onboarding card stack; default 50
  active                   # bool, default true — founder can deactivate without deleting
  genre_signature          # array<string>, optional — tags for matching to a viewing user's taste graph  (sync-fix Run #3 L5-005: replaces earlier `category` enum sketch — richer taxonomy)
  public_bio               # ≤200 chars, optional — short copy shown on the onboarding card  (sync-fix Run #3 L5-005: replaces earlier `description` sketch)
  notes                    # internal-only founder notes
  added_at                 # datetime
  deactivated_at           # datetime, None until `active` flips to False
}
```

---

## Key relationships

```
User 1──N MusicProvider
User 1──1 Backlog 1──N BacklogItem N──1 Album
User 1──N DiaryEntry N──1 Album
User 1──N JustFinishedPrompt N──1 Album
DiaryEntry 1──0..1 Review
User 1──N ReviewLike (liker) — Revision #3
Review 1──N ReviewLike (target) — Revision #3
User 1──N Follow (follower)
User 1──N Follow (followee)
User 1──N Block (blocker)
User 1──N Block (blockee)
User 1──N Report (reporter)
User 1──1 NotificationPreferences (embedded)
User 1──N Notification (recipient)
User 1──N SuggestedFollow (target)
User 1──0..1 CriticSeed (decoration, not required)
```
<!-- List + ListItem relationships removed in Revision #3 (Lists deferred to v2). -->

---

## Cross-cutting concerns

### Album identity normalization (load-bearing)

<!-- CR-001: identity-normalization cascade updated — Discogs ID replaces Spotify ID as the secondary canonical key. -->
When the system encounters an album reference, it must resolve to a single canonical Album record:

<!-- sync-fix L2-018 (Run #5): Album.candidate semantics aligned to actual T063 + T065 implementation. The candidate flag now marks Discogs-sourced rows pending automated MBID reconciliation by the T065 weekly worker — NOT manually-entered albums waiting on admin merge. (Manual-entry empty-search path lives in T053a "Report missing album" → admin queue, separate flow.) -->
```
1. If MBID is present (or resolvable via MusicBrainz lookup) → use MBID as the canonical key; Album persists with mbid set + candidate=false.
2. Else if Discogs ID is present (or resolvable via Discogs lookup) → use Discogs ID as the canonical key; Album persists with discogs_release_id set + candidate=TRUE (T065 worker periodically searches MusicBrainz by artist+title to find the MBID and merges).
3. Else (rare — e.g., a user manually typed an album title with no provider hit) → the empty-search-result path surfaces the FR-033 "Report missing album" link instead of auto-creating a candidate; the founder admin queue handles those manually.
```

Deluxe / remaster / regional variants: Phase 5 must decide whether to **merge under release-group MBID** (preferred — fewer duplicates, cleaner social signal) or **keep as separate albums** (preferred for power-users tracking specific editions). Default recommendation: **merge under release-group**.

### Visibility evaluation

Reading any user's DiaryEntry / Review / BacklogItem / Backlog involves a visibility check:

```
can_read(viewer, content) =
  IF content.deleted_at IS NOT NULL                         → false
  IF viewer is blocked by content.owner                     → false
  IF content.visibility == "public"                         → true
  IF content.visibility == "followers" AND
     Follow(follower=viewer, followee=content.owner) exists
     AND Follow.state == "active"                           → true
  IF content.visibility == "private" AND viewer == owner    → true
  ELSE → false
```

This rule is implemented once in a `visibility_check()` utility and called everywhere; lifting it into a single function is a constitution candidate.

### Soft delete vs hard delete

DiaryEntry and Review: soft-delete (set `deleted_at`); hard-delete on cron after 30 days.
User account deletion: 30-day grace period, then cascade hard-delete of all owned content.
Follow / Block: hard-delete only.
Notification: hard-delete after 90 days (privacy hygiene).
Report: never auto-deleted (audit trail).

### Schema versioning

Every document has `_schema_version: int`. Writers always write the current version. Readers tolerate one version below current and lazy-upgrade on next write. Migration code lives in `backend/migrations/`. No big-bang migrations.

---

## Indexes (preliminary — Phase 5 finalizes)

| Collection | Index | Purpose |
|---|---|---|
| User | `{ handle: 1 } unique` | Handle lookup |
| User | `{ email: 1 } unique` | Login |
<!-- CR-001: index on spotify_id replaced with index on discogs_release_id. -->
<!-- sync-fix L3-016 (Run #5): index shape corrected post-commit-66f0403. Sparse-unique fired on the second null insert in production because Pydantic serialises None→null (not "missing"); partialFilterExpression excludes both for the unique constraint. -->
| Album | `{ mbid: 1 } unique partial: {mbid: {$exists, $ne: null}}` | MBID lookup |
| Album | `{ discogs_release_id: 1 } unique partial: {discogs_release_id: {$exists, $ne: null}}` | Discogs ID lookup (fallback identifier per CR-001) |
| Album | Atlas Search index on `{ title, artist_credit, artists.name }` | Catalog search |
| DiaryEntry | `{ user_id: 1, logged_at: -1 }` | User diary timeline |
| DiaryEntry | `{ user_id: 1, album_id: 1, logged_at: -1 }` | "Have I logged this before?" check |
| DiaryEntry | `{ visibility: 1, logged_at: -1 }` | Public global feed (if shipped) |
| DiaryEntry | `{ album_id: 1, visibility: 1, rating: -1 }` | Album detail page reviews list |
| Review | `{ album_id: 1, reactions.likes_count: -1 }` | "Most Liked" sort on album detail (Revision #3) |
| ReviewLike | `{ review_id: 1, user_id: 1 } unique` | Idempotent like toggle + "did this user like this review" check |
| ReviewLike | `{ user_id: 1, created_at: -1 }` | "Likes I've given" view if surfaced |
| JustFinishedPrompt | `{ user_id: 1, state: 1, detected_at: -1 }` | Active prompts per user |
<!-- List + ListItem indexes removed in Revision #3 (Lists deferred to v2). -->
| Follow | `{ follower_id: 1, followee_id: 1 } unique` | Dedup follows |
| Follow | `{ followee_id: 1, state: 1 }` | "Who follows me" / pending requests |
| Review | `{ user_id: 1, created_at: -1 }` | Profile reviews list |
| Notification | `{ user_id: 1, created_at: -1 }` | In-app notification feed |
| SuggestedFollow | `{ user_id: 1, score: -1 }` | Suggestion query |

---

## Spec-level decisions locked (Phase 3 Revision #2)

Decisions previously deferred have been resolved at spec level. Final implementation specifics remain Phase 5. See [decision-log.md §Data model](./decision-log.md) for full table.

- **DM-1 — Fan-out-on-read at MVP.** Switch to fan-out-on-write only if feed query p95 exceeds 200ms (re-evaluate in Phase 5 from load model).
<!-- CR-001: cover-art source changed from Spotify CDN to Cover Art Archive. -->
- **DM-2 — Cover-art: proxy Cover Art Archive.** No S3 cache; client-side blurhash placeholders only. (Was "proxy Spotify CDN" pre-CR-001.)
- **DM-3 — Reactions on Reviews (`likes_count`, R3 rename — was `aux_count` in R1): ship visible at MVP.** No feature-flag gating; volume will be low and that's fine.
- **DM-4 — Tracklist denormalized into Album docs at MVP.** Revisit if Album docs balloon (>~20KB).
- **DM-5 — Soft-deleted DiaryEntry: cascade reactions.** Don't leave orphan ReviewLike rows or stale `likes_count` aggregates.

## Remaining Phase 5 (technical) decisions

<!-- CR-001: Atlas Search tuning now depends on MusicBrainz subset, not streaming-catalog sample. -->
- Atlas Search index tuning (analyzer, synonyms, autocomplete) — depends on the MusicBrainz subset selected for caching.
- GDPR audit log schema (every export / delete request is logged) — schema final in Phase 5.
- Specific MongoDB indexes (the table in §Indexes is preliminary; Phase 5 finalizes after query-load modeling).
- Provider-interface abstraction's exact method signatures.
