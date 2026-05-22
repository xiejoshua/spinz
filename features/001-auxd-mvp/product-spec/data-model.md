# Data Model: auxd MVP

> Feature: `001-auxd-mvp` | Phase: 2 (high-level — final schemas in Phase 5)
> Related: [product-spec.md](./product-spec.md) | [user-stories.md](./user-stories.md) | [decision-log.md](./decision-log.md)

This is the **conceptual** data model — entities, relationships, and key fields needed to support all user stories. Final MongoDB collection design, indexes, denormalization choices, and migration plan are deferred to Phase 5.

---

## Entity Inventory

| Entity | Purpose | Owner |
|---|---|---|
| **User** | Account identity, profile, settings | self |
| **MusicProvider** | Per-user credential block for an external provider (Spotify, Last.fm-import) | User |
| **Album** | Canonical album record (catalog cache) | system |
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
| **JustFinishedPrompt** | Pending or dismissed "just-finished" auto-prompt for the user | User |
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
  password_hash            # bcrypt, nullable if Spotify-OAuth-only
  display_name             # human-readable, ≤40 chars
  bio                      # ≤140 chars
  avatar_url               # CDN URL
  is_private_profile       # bool, default false
  default_entry_visibility # enum: public | followers | private, default "public"
  default_backlog_visibility # enum: public | followers | private, default "private"
  keep_backlog_after_log   # bool, default false
  status                   # enum: active | suspended | deleted (grace period) | hard_deleted
  deletion_scheduled_for   # datetime, set when user requests deletion
  last_login_at            # datetime
  auto_prompt_enabled      # bool, default true — show in-app prompt when Spotify detects a finished album
  auto_prompt_push_enabled # bool, default false — also send push for auto-prompts
  notification_preferences # ref → NotificationPreferences
  music_providers          # array<MusicProvider> (embedded or referenced)
  counts (derived/cached): { followers, following, entries, auxed, backlog_size, reviews, likes_given }
}
```

### MusicProvider
Stored as an embedded sub-document on User (one per provider).
```
MusicProvider {
  provider                 # enum: spotify | apple_music | lastfm_import
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

### Album
Canonical catalog cache. Records survive disconnects from Spotify; act as the album identity anchor.
```
Album {
  id                       # KSUID
  mbid                     # MusicBrainz release-group MBID (canonical key when available)
  spotify_id               # Spotify album ID (canonical when MBID unavailable)
  apple_music_id           # nullable, populated when Apple Music ships (v2)
  title
  artist_credit            # display string, e.g. "Kendrick Lamar & SZA"
  artists                  # array<{ name, mbid?, spotify_id? }>
  release_date             # YYYY-MM-DD or YYYY-MM or YYYY (granularity preserved)
  release_year             # int, denormalized for sort
  primary_type             # enum: album | ep | single | compilation | live | other
  cover_art_url            # primary, CDN URL (Spotify CDN at MVP)
  cover_art_blurhash       # for placeholder
  tracklist                # array<{ position, title, duration_ms, spotify_id? }>
  duration_ms              # total
  label
  source_provider          # which provider seeded this record (for audit)
  cached_at                # datetime
  cache_expires_at         # datetime (7d default)
  popularity_score         # 0–100, derived (used for search ranking)
  rating_counts_cache      # { 0_5: int, 0_5: int, ... }  (precomputed histogram for album detail page)
}
```

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
  source                   # enum: manual | spotify_import | lastfm_import | spotify_prefill
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

### JustFinishedPrompt
Pending or dismissed auto-prompt from Spotify-detection. Added in Revision #1.
```
JustFinishedPrompt {
  id
  user_id                  # FK → User
  album_id                 # FK → Album (the detected just-finished album)
  detected_at              # datetime (when Spotify's recently-played showed it finished)
  source                   # enum: spotify_recently_played | spotify_currently_playing_done
  state                    # enum: pending | dismissed | logged | expired
                           # expired = >24h since detected without action
  dismissed_at             # datetime, nullable
  logged_diary_entry_id    # FK → DiaryEntry, nullable (set when user logs from this prompt)
}
```

**Semantics:**
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

### NotificationPreferences
Embedded on User, but extracted here for clarity.
```
NotificationPreferences {
  per_type: {
    follow:           { in_app: true,  email: false, push: true  }   # default
    follow_request:   { in_app: true,  email: false, push: true  }
    review_heart:     { in_app: true,  email: false, push: false }
    review_reply:     { in_app: true,  email: false, push: false }  # v2 feature, accepted
    weekly_digest:    { in_app: false, email: true,  push: false }
    system_announce:  { in_app: true,  email: true,  push: false }
  }
  quiet_hours: { enabled: false, start: "22:00", end: "08:00", tz: "user_tz" }
  email_address: # falls back to User.email when unset
}
```

### SuggestedFollow
Precomputed by an offline job; refreshed N times per day.
```
SuggestedFollow {
  id
  user_id                  # who the suggestion is for
  suggested_user_id        # who is being suggested
  score                    # float, suggestion strength
  reason                   # enum: mutual_taste | followed_by_followed | shared_label | critic_seed | invited
  dismissed_at             # datetime, nullable (user-dismissed suggestions excluded for 30d)
  created_at
}
```

### CriticSeed
Static-ish editorial list of accounts pre-recommended/pre-followed at onboarding.
```
CriticSeed {
  id
  user_id                  # the actual User account that is a seed
  category                 # enum: critic | curator | label_account | artist
  description              # ≤140 chars, why this account is seeded
  priority                 # 0–100, used for ranking in onboarding
  active                   # bool, soft-disable
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

When the system encounters an album reference, it must resolve to a single canonical Album record:

```
1. If MBID is present (or resolvable via MusicBrainz lookup) → use MBID as the canonical key.
2. Else if Spotify ID is present → use Spotify ID as the canonical key.
3. Else (rare — e.g., user typed a manual title in a v2 flow) → create a "candidate" album record flagged for admin merge.
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
| Album | `{ mbid: 1 } sparse unique` | MBID lookup |
| Album | `{ spotify_id: 1 } sparse unique` | Spotify ID lookup |
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
- **DM-2 — Cover-art: proxy Spotify CDN.** No S3 cache; client-side blurhash placeholders only.
- **DM-3 — Reactions on Reviews (aux_count): ship visible at MVP.** No feature-flag gating; volume will be low and that's fine.
- **DM-4 — Tracklist denormalized into Album docs at MVP.** Revisit if Album docs balloon (>~20KB).
- **DM-5 — Soft-deleted DiaryEntry: cascade reactions.** Don't leave orphan aux counts.

## Remaining Phase 5 (technical) decisions

- Atlas Search index tuning (analyzer, synonyms, autocomplete) — depends on Spotify catalog sample data.
- GDPR audit log schema (every export / delete request is logged) — schema final in Phase 5.
- Specific MongoDB indexes (the table in §Indexes is preliminary; Phase 5 finalizes after query-load modeling).
- Provider-interface abstraction's exact method signatures.
