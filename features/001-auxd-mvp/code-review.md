# Code Review: auxd MVP — Phase 6B

> Feature: `001-auxd-mvp` | Date: 2026-05-24 | Phase: 6B (Code Review)
> Files reviewed: **~458 source files** (203 backend Python + 175 frontend TS/TSX + ~80 test files)
> Status: **APPROVED** — all 10 HIGH findings fixed inline

## Resolution status (post-fix)

| ID | Status | Resolution |
|---|---|---|
| REV-001 | ✅ FIXED | One-line field rename `follower_id/followee_id` → `requester_id/requestee_id` in users/routes.py + new test_users_profile_endpoint.py |
| REV-002 | ✅ FIXED | `lib/visibility.can_read*` extended with `owner_is_private` kwarg; 4 read-endpoint call sites updated (diary/reviews/albums/feed); 14 private-profile-gating tests added |
| REV-003 | ✅ FIXED | `diary.delete_entry` now soft-deletes attached Review; `restore_entry` cascades restore via same-instant heuristic; 3 new cascade tests |
| REV-100 | ✅ FIXED | New `apiFetchMultipart` helper in api-client.ts lifts auxd_csrf cookie → X-CSRF-Token header (no Content-Type set; browser writes boundary). Avatar upload refactored. +3 regression unit tests. |
| REV-101 | ✅ FIXED | Cover-art route allow-list (`coverartarchive.org` + `img.discogs.com`, https-only, exact hostname). REV-122 MBID regex tightened to strict UUID pattern. +17 cover-route unit tests. |
| REV-120 | ✅ FIXED | Added `app/{error,global-error,not-found}.tsx` + segment not-founds for `/album/[id]` and `/review/[id]` (REV-123). Wired `captureClientError` via useEffect with `digest` + boundary name as Sentry extra context. |
| REV-126 | ✅ FIXED | `standalone.spec.ts` extended with DOM assertions for `/suspended` mailto + `/legal/*` placeholder banner. |
| REV-200 | ✅ FIXED | Vitest include broadened to `.ts` + `.tsx`; a11y/perf folders excluded; new `scripts/lint-test-location.mjs` + npm script + CI step after Biome lint. |
| REV-201 | ✅ FIXED | New `test_avatar_upload_rate_limit_boundary` (5 successful → 200; 6th → 429), matching the deterministic-counter monkeypatch pattern from test_reports_endpoints.py. |
| REV-202 | ✅ FIXED | `FakeAuthMiddleware` extracted to `apps/api/tests/integration/_auth_helpers.py`; **28 integration test files** refactored to import the shared class. Supports parameterized `session_factory` for future variations. |

**Final gate**: backend pytest 964 → **1003** (+39); frontend vitest 81 → **102** (+21); Biome 175 → 182 files; tsc 0; next build 26 routes; test-location lint OK.

All 10 HIGH findings resolved. **Recommendation: APPROVED — ready for Phase 7 verify-full from a green baseline.**

This review consolidates three parallel sub-agent reviews:
- **Backend**: `apps/api/src/auxd_api/` + `apps/api/scripts/` + `apps/api/pyproject.toml` — REV-001..099
- **Frontend**: `apps/web/src/` + `apps/web/public/sw.js` + config files — REV-100..199
- **Tests + Shared-types**: `apps/api/tests/` + `apps/web/tests/` + `packages/shared-types/` — REV-200..249

## Consolidated Summary

| Dimension | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|:-:|:-:|:-:|:-:|:-:|
| Quality | 0 | 2 | 15 | 14 | 31 |
| Security | 0 | 4 | 8 | 4 | 16 |
| Patterns | 0 | 2 | 9 | 9 | 20 |
| Tests (coverage + quality + codegen) | 0 | 2 | 10 | 4 | 16 |
| **Total** | **0** | **10** | **42** | **31** | **83** |

**Zero CRITICAL findings** confirm the 13 sync-verify runs + T173 OWASP review + T171 a11y audit + 26 progressive-verify checkpoints did their job.

**Recommendation:** **APPROVED WITH CONDITIONS** — fix the 10 HIGH findings before Phase 7 verify-full. The MEDIUM + LOW items can be batched as a sync-fix follow-up.

## Required Before Phase 7 Verification (10 HIGH)

### Backend (3)

- **REV-001** [Quality] `users/routes.py:430` queries `FollowRequest` with wrong field names (`follower_id`/`followee_id`) — should be `requester_id`/`requestee_id`. The `relation: "pending"` branch never fires, breaking US-G2 private-profile UX. **Definite bug. ~1-line fix.**
- **REV-002** [Security] `User.private_profile` is never checked by `lib/visibility.can_read` or by diary/reviews/album-detail read endpoints. A user with `private_profile=True` still has their PUBLIC-visibility diary/reviews served to anonymous viewers. **Privacy contract regression.**
- **REV-003** [Quality] `diary.delete_entry` hard-deletes the attached `Review` while the rest of the codebase soft-deletes. The 30-day restore window for diary entries leaves orphan `review_id` pointers and irrecoverable review bodies. **Data-loss bug.**

### Frontend (4)

- **REV-100** [Security] Avatar upload at `edit-profile-form.tsx:92` bypasses `api-client.ts` — no CSRF header injected on the multipart POST. T173's cookie→header lift covers every JSON mutation but the only multipart write path is missed. **Production avatar upload would 403.**
- **REV-101** [Security] `cover/[size]/[mbid]/route.ts:37-43` does an open-redirect to any `https://` URL passed in `?fallback=`. Composes with REV-122 (lax MBID regex). **Allow-list known cover hosts (coverartarchive, discogs CDN, R2 bucket).**
- **REV-120** [Quality] No `error.tsx`, `global-error.tsx`, or `not-found.tsx` anywhere under `apps/web/src/app/`. Uncaught render errors fall to Next's default UI; `lib/sentry.ts.captureClientError` is exported but never wired to an ErrorBoundary.
- **REV-126** [Tests-Coverage] *(secondary HIGH from frontend review)* No a11y spec for `/suspended` or `/legal/*` standalone routes.

### Tests + Shared-types (3)

- **REV-200** [Quality] Vitest config restricts discovery to `tests/unit/**` with no CI guard catching misplaced tests outside that path. Tests placed elsewhere silently never run.
- **REV-201** [Coverage] Avatar upload test claims 5/min rate-limit boundary in its docstring but the actual boundary assertion is absent. Reports/album-reports DO cover their rate-limit; avatar is the only gap. **30-minute fix.**
- **REV-202** [Patterns] `FakeAuthMiddleware` is duplicated across 26 integration test files. A `Session` shape change would require 26 simultaneous edits. **Extract to a shared conftest fixture.**

## Positive Highlights (consolidated across all 3 reviews)

1. **`lib/visibility` is genuinely clean.** Pure policy with no I/O, well-typed Protocols, clear matrix table in the docstring, `can_read_with_relation` separation lets callers batch-resolve relations efficiently.
2. **Resilience composition is textbook.** `lib/resilience` enforces the exact `circuit_breaker → retry → timeout` order Constitution P1 demands; `providers/transport.ResilienceTransport` wraps every httpx provider call uniformly with explicit `_Retryable429` sentinel preventing retry on 429.
3. **Fail-mode discipline is explicit and consistent.** Defensive layers FAIL OPEN with Sentry tags (`rate_limit.redis_down`, `notif_limiter.redis_down`, `jobs.redis_down`, `cache.redis_down`); load-bearing layers FAIL CLOSED with typed exceptions + 503 handler.
4. **CSRF wiring on the backend is correctly defensive.** SessionMiddleware enforces double-submit on every non-safe method, `X-CSRF-Token` in CORS `allow_headers`, tampered cookies → 401 (no silent downgrade). The T173 frontend fix lifts the cookie correctly **for every JSON mutation** (multipart is the gap — REV-100).
5. **Optimistic-update + invalidate pattern is consistent** across all React Query mutations. Strong sidecar denormalization (UserCard / AlbumCard).
6. **Conftest pattern** with documented mongomock-motor workarounds (partial-filter index drop, backlog compound-index reconstruction) — single source of truth wired to `ALL_DOCUMENT_MODELS`.
7. **Dispatcher unit test depth.** 21 distinct assertions across send/coalesce/drop/suppressed paths, including the T144 PostHog contract.
8. **GDPR cascade test is one monolithic test** seeding 13+ owned collections + bystander rows + reports in 3 flavours, asserting reporter anonymisation + target-side retention + audit log + bystander survival.
9. **Coalescer integration test uses fakeredis** + 4 key-shape regression tests preventing silent bucket-naming refactors.
10. **The 2 T171 TabsContent fixes** (feed-list, diary-list) are verified intact post-Run #13.

## Review Checklist

- [x] **CRITICAL findings addressed**: 0 found ✅
- [ ] **HIGH findings addressed or acknowledged**: 10 found — see "Required Before Phase 7" above
- [ ] **Test coverage adequate for Must Have stories**: gaps noted in §14 avatar rate-limit (REV-201), §18 a11y for /suspended + /legal (REV-126), TC-E2E-010..013 only cover UI shell (REV-223)
- [x] **No security vulnerabilities in new code**: T173 OWASP review closed; this Phase 6B found 4 HIGH security items (3 surface gaps + 1 layered defense gap) — none are CRITICAL

---

## Full Findings — Detail

The full per-finding detail (REV-001..225b with file:line + before/after code snippets + suggested fixes) is split across three appendices below. Each preserves its original sub-agent structure.


## Appendix A — Backend Findings Detail (REV-001..099)


### REV-001: `get_user_profile` queries FollowRequest with wrong field names

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | HIGH |
| File | apps/api/src/auxd_api/modules/users/routes.py:430-436 |
| Rule | Type-safe field names; broken contract |

**What:** The "pending" relation check uses `follower_id`/`followee_id` but the `FollowRequest` document defines its fields as `requester_id`/`requestee_id`. Beanie/MongoDB will silently match zero rows (the wrong field names are absent from the document). Other call sites (users/routes.py:770, social/service.py) correctly use `requester_id`/`requestee_id`.

```python
# WRONG (apps/api/src/auxd_api/modules/users/routes.py:430-436)
pending = await FollowRequest.find_one(
    {
        "follower_id": viewer_id,
        "followee_id": target.id,
        "status": FollowRequestStatus.PENDING.value,
    }
)
relation = "pending" if pending is not None else "none"
```

**Why it matters:** Users who request to follow a private profile will see the UI show "Follow" (relation=none) instead of "Pending" because the GET /users/{handle} endpoint will always report `relation="none"` even when a `FollowRequest` exists. The frontend will let them re-trigger the follow → the social service's idempotency catches it but the relation status surfaced to the UI is wrong, undermining the US-G2 private-profile UX.

**Suggested fix:**
```python
pending = await FollowRequest.find_one(
    {
        "requester_id": viewer_id,
        "requestee_id": target.id,
        "status": FollowRequestStatus.PENDING.value,
    }
)
```

Add an integration test that covers `GET /users/{handle}` after a follow request to a private profile.

---

### REV-002: `private_profile` flag has no effect on diary / reviews / album-detail read endpoints

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | HIGH |
| File | apps/api/src/auxd_api/lib/visibility.py + apps/api/src/auxd_api/modules/diary/routes.py + apps/api/src/auxd_api/modules/reviews/routes.py + apps/api/src/auxd_api/modules/albums/routes.py |
| Rule | Authorization completeness; private profile contract |

**What:** `User.private_profile=True` is enforced only at one place: `social.follow_user` switches public-vs-pending follow on it (`if followee.private_profile: ... pending`). However:

- `GET /users/{handle}/diary` (diary/routes.py:get_user_diary) only filters by per-entry `Visibility`; a private-profile user's PUBLIC-visibility entries are still returned to anonymous viewers and to non-followers.
- `GET /users/{handle}/reviews` (reviews/routes.py:get_user_reviews) similarly returns PUBLIC-visibility reviews of a private user.
- `GET /albums/{album_id}` and `GET /albums/{album_id}/reviews` likewise include private-user PUBLIC content in the friends / public-reviews rollups.
- `GET /users/{handle}` does NOT 404 anonymous viewers of a private profile (only blocked viewers see 404).

**Why it matters:** The contract for "private profile" per the spec (US-G2) is "non-followers cannot see my content even when an individual entry's visibility is public". The current implementation lets a private-profile user's old PUBLIC-marked entries leak to anonymous viewers. This is a privacy regression: a user who flips `private_profile=true` reasonably expects their old content to become followers-only. The `lib/visibility` matrix has no input for the owner's `private_profile` flag, so every route consumer is silently broken.

**Suggested fix:** Extend `lib/visibility` so `OwnedContent` carries an `owner_is_private: bool` (or pass a `ContentContext` with that flag), and treat `private_profile=True` as if every content visibility were demoted to `FOLLOWERS`. Then update every route's resolver to load and pass that flag.

```python
# proposed shape in lib/visibility.py
def can_read_with_relation(
    viewer: Viewer | None,
    content: OwnedContent,
    relation: ViewerRelation,
    *,
    owner_is_private: bool = False,
) -> bool:
    # If owner is private, treat PUBLIC content as FOLLOWERS-scoped.
    effective_visibility = (
        Visibility.FOLLOWERS
        if (owner_is_private and content.visibility is Visibility.PUBLIC)
        else content.visibility
    )
    ...
```

Note: this also requires the user-profile route to demote `relation` for non-follower anonymous viewers of private profiles (return 404, not just empty diary).

---

### REV-003: `diary.delete_entry` hard-deletes the attached Review, bypassing soft-delete + 30-day restore

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | HIGH |
| File | apps/api/src/auxd_api/modules/diary/service.py:440-448 |
| Rule | Cascade semantics consistent with soft-delete contract |

**What:** When a user soft-deletes a diary entry (sets `deleted_at`), the cascade on the attached review calls `await review.delete()` — a hard delete. But the Review model also has its own `deleted_at` column and the standalone `reviews.delete_review` service uses soft-delete with a 30-day grace.

```python
# apps/api/src/auxd_api/modules/diary/service.py:440-448
if entry.review_id is not None:
    review = await Review.get(entry.review_id)
    if review is not None:
        # Reviews don't have a deleted_at column today; the strongest
        # cascade we can express without a schema change is to drop
        # the row entirely. ...
        await review.delete()
```

The comment "Reviews don't have a deleted_at column today" is stale — the Review model (reviews/models.py:54) has had `deleted_at: datetime | None = None` since T087 / sync-fix L3-022. So:

1. The 30-day restore window (`restore_entry`) restores the DiaryEntry but the original Review is gone forever.
2. Likes on the deleted Review are orphaned but the comment claims the read endpoint hides them — true via the `deleted_at` filter, but the cascade ran before the filter could help.
3. Inconsistent: `DELETE /reviews/{id}` is soft-delete + restorable; `DELETE /diary/entries/{id}` cascades the attached review as a hard-delete.

**Why it matters:** Loss of review body when the user just intended a 30-day undo. Also breaks the GDPR audit trail principle a tiny bit because the review row is gone before the 30-day grace expires.

**Suggested fix:** Switch the cascade to soft-delete and let the same restore path bring it back:
```python
if entry.review_id is not None:
    review = await Review.get(entry.review_id)
    if review is not None and review.deleted_at is None:
        review.deleted_at = now
        review.updated_at = now
        await review.save()
```

Then update `restore_entry` to also restore the attached review (if it was soft-deleted within the same grace window). The 30-day hard-delete cron sweep on `Review.deleted_at` (already configured per the sparse index) will handle eventual cleanup.

---

### REV-004: `_require_session` is duplicated across 10 router modules

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/{auth,backlog,seeding,social,feed,users,diary,notifications,reports,reviews}/routes.py |
| Rule | DRY; cross-module helpers belong in lib |

**What:** 10 separate copies of the same 8-line `_require_session(request: Request) -> Session` helper. Plus three modules (users, reviews, diary) also re-declare a private `_optional_session` helper with identical body. Plus three modules duplicate the `_SessionViewer` / `_DiaryContent` / `_ReviewContent` adapter classes verbatim.

**Why it matters:** A future change to the unauthenticated error shape, the 401 detail format, or the "what counts as a session" definition has to land 10 times. The visibility-adapter duplication multiplies that for the relation-resolver helpers.

**Suggested fix:** Move `_require_session` + `_optional_session` to `lib/sessions` (alongside the existing `Session` type) so every module imports from one source of truth. Move the `_SessionViewer` and `_DiaryContent` / `_ReviewContent` adapters either to `lib/visibility` (they're already coupled to its Protocols) or to a new `lib/visibility_adapters.py`. Replace the 10 `_resolve_relations` near-duplicates (currently in diary/routes, reviews/routes, albums/routes, feed/service, users/routes albeit slightly different) with a single helper that takes a viewer_id + owner_ids set.

---

### REV-005: `users.routes.get_user_profile` does not gate follower/following counts on the target's private_profile

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/users/routes.py:402-407 |
| Rule | Information disclosure / private-profile contract |

**What:** Even when `target.private_profile=True`, anonymous and non-follower viewers can see the full `followers`/`following` counts. Combined with REV-002, this leaks the social graph size of a user who deliberately marked themselves private.

**Why it matters:** Minor info-disclosure but contrary to the spirit of US-G2. Users who go private generally don't expect their network size to be visible to non-followers.

**Suggested fix:** When `target.private_profile=True` AND viewer is not the target, follower, or admin, return `counts: null` (or counts limited to "followers: N+ where N rounds to nearest power of 10"). Simpler: just omit the counts block for non-readers entirely.

---

### REV-006: N-002 follow-request notification is never dispatched (only a TODO)

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/social/service.py:352-353 (TODO marker) + apps/api/src/auxd_api/modules/social/routes.py:232 |
| Rule | Notification taxonomy completeness |

**What:** When user A follows user B (private profile), a FollowRequest is created. The taxonomy at `modules/notifications/types.py:N002_FOLLOW_REQUEST_PENDING` is registered with payload schema + copy + push template, and `is_notifiable` will accept it, but `social.service._request_follow_private` writes the row and returns without calling `dispatch_notification`. The route layer has a matching `# TODO: N-002 follow request notification` (social/routes.py:232).

**Why it matters:** Users with private profiles will not be alerted to incoming follow requests — they'd only see them by polling the `/users/me/follow-requests` inbox manually. This breaks the US-G2 expected flow where the requestee is notified of pending requests.

**Suggested fix:** In `_request_follow_private`, after `await row.insert()` (or after the re-open-existing branch), call:
```python
await dispatch_notification(
    user_id=followee.id,
    type=NotificationType.N002_FOLLOW_REQUEST_PENDING,
    payload={"actor_handle": ..., "actor_display_name": ...},
    actor_id=follower_id,
)
```
Note this needs the actor's display_name; service-layer should accept it as a kwarg from the route layer, or look up the actor row inside the function. Make sure the dispatch is gated on the "fresh insert / re-open" path (don't fire for the already-pending no-op idempotent case).

---

### REV-007: Account-deletion sweep does not anonymise the deleted user's outgoing report rows but the `Suggestion`/`SuggestionDismissal` cascade catches every direction

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/users/workers.py:154-160 |
| Rule | GDPR cascade completeness |

**What:** The deletion cascade anonymises `reports.reporter_id` to `None` when the deleted user is the *reporter* (good — keeps moderation history intact), but the cascade does NOT touch:
- `Notification.actor_id` references to the deleted user across other users' inboxes (a deleted user's @handle/display_name is in the payload and would leak)
- `ReviewLike.user_id` for likes the deleted user gave to OTHER users' reviews (the `ReviewLike` cascade only catches likes WHERE `user_id == deleted_user` — but the review's `reactions.recent_likers` array on OTHER users' reviews still contains the deleted user_id)
- `Follow` rows in either direction ARE deleted, so the follow graph is clean

Notification audit rows that reference the deleted user (`actor_id`) in OTHER users' inboxes will continue to display the actor's `actor_handle` from `payload` even after the row is gone — a stale string reference rather than data leak, but still a privacy edge.

**Why it matters:** Right of erasure (FR-019) is "comprehensive" per the cascade comment, but two specific reverse-FK cases survive: (a) historical notification payloads in followers' inboxes carry the deleted user's denormalised display fields; (b) `reactions.recent_likers` arrays carry stranded user_ids. Neither is a hard violation since `actor_id` is a KSUID with no PII outside the User row itself; but the `actor_handle` in the payload IS PII and not redacted.

**Suggested fix:** Either:
1. Wipe `actor_id` + `actor_handle` from all other users' `Notification` rows where `actor_id == deleted_user_id` during the cascade (add an `update_many` step), and likewise scrub `reactions.recent_likers` arrays.
2. OR: have the inbox serializer treat unknown `actor_id` references defensively — actors that no longer resolve render as "Deleted user" instead of the cached `actor_handle`.

Option 2 is cheaper and more robust against future reverse-FK additions. Option 1 is more thorough but adds N collections to the cascade.

---

### REV-008: Avatar upload's `MissingR2ConfigurationError` returned as 503 even when correct policy is 500 (server-side misconfig)

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/users/routes.py:638-651 + apps/api/src/auxd_api/lib/storage.py:53 |
| Rule | HTTP status semantics |

**What:** When `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_ENDPOINT_URL` are unset, the avatar upload returns 503 (Service Unavailable). 503 is for "temporarily unavailable / retry later"; a missing-credential config is "the operator never set up the service" which is a 500-class condition the client can't fix by retrying.

**Why it matters:** Minor; clients will retry on 503 which is wasteful. The Sentry alert for `r2.misconfigured` doesn't exist (no Sentry alert is fired here at all).

**Suggested fix:** Either change to 500 (and fire a Sentry tag `r2.misconfigured`), or document explicitly that R2 missing keys is treated as a transient outage and add a Sentry alert. Personally I'd go with 500 + Sentry — config errors deserve a louder signal.

---

### REV-009: Email upload pipeline content-type allowlist accepts `image/jpg` (non-standard MIME)

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/users/routes.py:533 |
| Rule | Content-type validation |

**What:** `_AVATAR_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})`. The standard JPEG MIME is `image/jpeg`; `image/jpg` is a common but non-standard alias.

**Why it matters:** Adding `image/jpg` doesn't introduce a real vulnerability (the file is still Pillow-decoded and re-encoded to JPEG), but it does let a client legitimately disagree with the spec. A future tightening (e.g., a CDN that rejects non-canonical MIMEs) would suddenly reject avatars from clients sending `image/jpg`.

**Suggested fix:** Drop `image/jpg` from the allowlist (every modern browser sends `image/jpeg`); or normalise: `if content_type == "image/jpg": content_type = "image/jpeg"` before the membership check. Pillow's actual decoder doesn't care about the Content-Type — it sniffs bytes — so this is purely for the consistency of the API surface.

---

### REV-010: `Notification.user_id` index missing tzinfo-aware sort guarantee combined with `Notification._schema_version` using bare class attribute

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/notifications/models.py:125, 194 + apps/api/src/auxd_api/modules/diary/models.py:52, 65, 78, 104 |
| Rule | Schema-version pattern consistency |

**What:** The codebase mixes two patterns for `_schema_version`:

- `social/models.py`, `users/models.py`, `albums/models.py`, `social/suggestions_models.py` use `schema_version: int = Field(default=1, alias="_schema_version")`.
- `diary/models.py`, `reviews/models.py`, `notifications/models.py`, `notifications/push_models.py`, `backlog/models.py`, `seeding/models.py`, `prompts/models.py`, `moderation/models.py`, `gdpr/models.py` use bare class attribute `_schema_version: int = 1`.

A bare class attribute `_schema_version: int = 1` on a Pydantic Document does NOT get serialised to MongoDB (Pydantic strips underscore-prefixed attrs) unless explicitly aliased. So half the documents are NOT persisting their schema_version field. This was Constitution P2's main point — readers tolerate `current_version` and `current_version − 1`.

**Why it matters:** When a future migration ships, the runner needs to find documents at `from_version`. If `_schema_version` was never persisted (because it was a bare class attr), every document selects as the default value at read time — but the migration's `update_many({"_schema_version": from_version})` query selects zero rows because the field doesn't exist on disk. This silently breaks lazy migrations.

**Suggested fix:** Audit all `_schema_version: int = 1` class attributes; convert them to `schema_version: int = Field(default=1, alias="_schema_version")` to actually persist the field. Verify by checking a writeback in mongomock + asserting `"_schema_version" in raw_dict`.

---

### REV-011: Diary `_resolve_relations` block-direction-aware logic duplicated 4× in diary, reviews, feed, albums

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/diary/routes.py:235-291, apps/api/src/auxd_api/modules/reviews/routes.py:219-274, apps/api/src/auxd_api/modules/feed/service.py:204-255, apps/api/src/auxd_api/modules/albums/routes.py:115-178 |
| Rule | DRY; shared resolver in lib/visibility |

**What:** Four near-identical implementations of `async def _resolve_relations(viewer_id, owner_ids) -> dict[str, ViewerRelation]`. Bodies vary only by Python-style trivia (slot order, comment wording) — the underlying queries are the same Block + Follow scan with the same edge handling.

**Why it matters:** A bug fix to one (e.g., adding a "self-follow" guard or extending block semantics) would have to land 4 times. Future modules (prompts, listening-history v2) will copy a 5th.

**Suggested fix:** Move `_resolve_relations` to `lib/visibility.py` as a public async helper since it's the canonical relation resolver that the matrix consumes. Signature:
```python
async def resolve_relations(viewer_id: str | None, owner_ids: set[str]) -> dict[str, ViewerRelation]:
    ...
```
Then every route imports it.

---

### REV-012: Atlas Search index json missing the `lucene.standard` analyzer on `popularity_score`/`rating_count` (numeric fields don't need analyzers — but the plan §6 mentions a `log1p(rating_count)` popularity boost which the search service doesn't use)

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/api/migrations/atlas_search/albums_index.json + apps/api/src/auxd_api/modules/search/service.py |
| Rule | Plan ↔ code alignment |

**What:** The Atlas Search index json declares `popularity_score` and `rating_count` as numeric fields (correct — these don't need analyzers). But the search service `_atlas_search()` only uses `autocomplete` on `title` and `artist_credit` — there's no `compound.should` clause with a `function` score boost referencing `log1p(rating_count)`, contrary to what plan §6 describes. The service docstring acknowledges this as "current ``_atlas_search`` query is relevance-only at MVP" but it's a drift from the plan: the index indexes a field the service never queries.

**Why it matters:** Wasted index space on a field that's never queried. Also a minor lock-in risk: when the plan-mandated popularity boost is finally wired (a one-liner change to the pipeline), the existing index will support it without re-indexing — so at least no migration is needed. But documenting the drift would clarify intent.

**Suggested fix:** Either:
1. Wire the popularity boost in `_atlas_search` so the index serves its plan-stated purpose. The pipeline addition is a few lines.
2. Add an inline comment to `_atlas_search` linking to plan §6 with a TODO and the date, mark the `rating_count` field in the json as "reserved for popularity boost (plan §6)".

---

### REV-013: `digest_dispatch._dispatch_for_user` iterates `User.find(...)` async-for, but for each user spins multiple aggregation queries — risk of cron-step exceeding the 5-min window at scale

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/workers/digest_dispatch.py:366-407 |
| Rule | Bounded resource use; cron idempotency |

**What:** The weekly digest cron runs every 5 minutes (12 minute-buckets); `dispatch_weekly_digests` streams `async for user in User.find(...)` and for each user that's eligible NOW fires:
- 1 follow query
- 3 aggregation pipelines (one per hero)
- 1 review-likes count
- 1 diary entries query + N user/album joins
- 1 N-008 dispatch (which itself can fire Resend SDK + DB write)

At 5k–10k users (M6 target), each Monday-9-AM-local window touches ~700 users (rough — depends on TZ distribution). 700 users × 6 queries each = 4200 Mongo round-trips per cron firing, all within the 5-min window. This is likely fine at MVP scale but there's no per-cron-firing cap or "I've processed X users this run, defer rest to next-bucket" check.

**Why it matters:** A timezone clustered around a single hour (e.g., America/New_York at 9 AM ET) could overshoot the 5-minute window. The cron will then fire again at the next 5-minute mark and re-process the same users — eligibility check is `0 <= local.minute < 5` so the next firing at minute 5 would NOT re-process them. But if the previous firing was killed mid-batch by a process restart, those users miss their digest entirely (no retry / idempotency anchor on `User.last_digest_sent_at`).

**Suggested fix:** Add a `User.last_digest_sent_at: datetime | None` field; set it on successful dispatch; check `> now - 6 days` to skip in subsequent firings. This makes the digest cron idempotent across process restarts. Also add a per-firing budget (`MAX_DIGESTS_PER_FIRING = 500`) so a single firing has a hard ceiling.

---

### REV-014: `lib/observability.emit_event` swallows EVERY Exception including KeyboardInterrupt-like

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/lib/observability.py:265-310 |
| Rule | Catch specific exceptions, not BaseException |

**What:** `emit_event` wraps the PostHog call in `except Exception` (line 302). That's actually fine — PostHog client failures should never break a request. But the `_get_posthog_client` helper does the same broad catch (line 235, 253). Both are tagged `# noqa` or implicit. The cumulative effect is that any non-PostHog error in the call chain (e.g., a TypeError from the caller passing a non-string `user_id`) is silently absorbed.

**Why it matters:** Caller-side bugs (typos in event names, wrong property types) are silently dropped instead of surfacing in tests. Could mask real bugs during development.

**Suggested fix:** Narrow the catch to `posthog.client.PosthogException` (or similar PostHog-specific exception) + `RequestException` for network errors. Let TypeErrors and KeyErrors propagate to the caller. The "fire-and-forget" contract is about NETWORK / SERVICE failures, not about taking PYTHON bugs as input.

---

### REV-015: Hard-coded `mailto:` strings, brand name, URL conventions scattered across modules (should be Settings or constants module)

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/middleware.py:107, apps/api/src/auxd_api/workers/gdpr_export.py:280, apps/api/src/auxd_api/providers/musicbrainz.py:36, apps/api/src/auxd_api/providers/discogs.py:38 |
| Rule | Magic-string discipline |

**What:** `"mailto:appeals@auxd.xiejoshua.com"`, `"appeals@auxd.xiejoshua.com"`, `"https://auxd.xiejoshua.com"`, the User-Agent string `"auxd/0.0.0 (https://auxd.xiejoshua.com)"` — all hardcoded in multiple files. Renaming the product or domain requires touching 4+ places.

**Why it matters:** Minor. Settings already has `PUBLIC_APP_URL` for the deep-link case (the export worker uses it correctly). But the suspension appeals address is hardcoded in middleware as well as elsewhere; the User-Agent string is hardcoded in both provider modules.

**Suggested fix:** Add `APPEALS_EMAIL`, `BRAND_USER_AGENT` (or `USER_AGENT_VERSION`) to Settings. The User-Agent string in particular should use `auxd_api.__version__` instead of `"0.0.0"` so each release rolls a fresh UA.

---

### REV-016: `lib/rate_limit._check_and_record` records the hit BEFORE the response — fail-open returns True even when count would have exceeded but Redis failed

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/lib/rate_limit.py:137-152 |
| Rule | Fail-open is documented; but record happens before check passes |

**What:** Within the try block, the sequence is: trim → count → check-against-limit → `await client.zadd(bucket_key, ...)` → `await client.expire(...)`. If the `expire` call fails (e.g., Redis was briefly available for the trim+count but then connection dropped before the expire), the function falls into `except RedisError` and returns True (fail open). But the `zadd` may have already landed. On the NEXT request after Redis recovers, the bucket has a phantom entry that didn't get an expire — though `zadd` followed by `expire` failure means the key may persist forever (or until manual eviction). For a hot endpoint this could pin a key in Redis with stale entries.

**Why it matters:** Tiny memory leak. Sliding-window semantics are still correct because the `zremrangebyscore` trim removes expired entries on the next call. But it's a robustness wart.

**Suggested fix:** Either (a) use a single Lua script that does trim+count+zadd+expire atomically, or (b) re-issue `expire` opportunistically on every call regardless of zadd success. Option (a) is cleaner and also makes the limiter rate-limit-resistant to network blips.

---

### REV-017: No tests assertions found for backend modules — assessment based on test scope hand-off

| Field | Value |
|---|---|
| Dimension | Tests-coverage |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/ (production code) |
| Rule | Test coverage |

**What:** Based on the spec scope, the tests directory is reviewed by the sibling sub-agent. This finding only assesses that the production modules have testable surface area:
- All service-layer functions are pure-async + dependency-injected (CatalogProviders, no module-level state in services). ✓
- All route-layer functions take FastAPI `Request` + Pydantic models; testable via TestClient. ✓
- Workers (`_dispatch_for_user`, `_cascade_user_content`, `scan_reports_for_flags`) export the public function. ✓
- However, `digest_dispatch._build_three_hero_carousel` couples DB aggregation pipelines with business logic — hard to test without mongomock. Same for the suggestions_job's full materialisation pass.

**Why it matters:** Worker-level integration tests need mongomock fixtures, which slows the test suite. But the algorithms are otherwise testable via the pure scoring functions (`score_candidate`, `score_critics_by_genre_signature`).

**Suggested fix:** Extract the aggregation pipelines from `_build_three_hero_carousel` into a parameterised helper that takes a list of rows + returns the formatted hero dict — then test the helper without DB.

---

### REV-018: Suggestions worker imports `datetime` twice in nested scope

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/workers/suggestions_job.py:403, 498-499 |
| Rule | Dead-code / nested imports |

**What:**
```python
# inside compute_suggestions_for_user, line ~403
from datetime import UTC, datetime, timedelta
recency_cutoff = datetime.now(UTC) - timedelta(days=RECENT_LOG_WINDOW_DAYS)
# ... later, inside the same function's DuplicateKeyError branch, line ~498-499
from datetime import UTC as _UTC
from datetime import datetime as _datetime
existing.computed_at = _datetime.now(_UTC)
```

Three things wrong:
1. `datetime`, `UTC`, `timedelta` are imported inside a function body when they're available at module level (cf. how the rest of the codebase imports them at the top).
2. The fallback rename `as _UTC` / `as _datetime` is unnecessary — the outer `datetime` is the stdlib module, the inner `datetime` is the class. No name collision.
3. Both blocks are redundant with the module-level imports that already exist throughout the codebase.

**Why it matters:** Style noise; slightly slower function entry (Python caches imports so the runtime cost is negligible).

**Suggested fix:** Move the `from datetime import UTC, datetime, timedelta` to module-top; delete the renamed-alias second import.

---

### REV-019: Notification routes mix `/notifications/...` and `/users/me/...` namespaces in the same router

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/notifications/routes.py:66 (router with no prefix) |
| Rule | Router namespace consistency |

**What:** Most modules' routers carry a `prefix=` (auth, users, search, social/...). The notifications router declares `APIRouter(tags=["notifications"])` with NO prefix, then mounts endpoints at both `/notifications/...` and `/users/me/push-subscriptions`, `/users/me/notification-preferences`. This is correct from a URL-design perspective (push subs ARE on the user resource) but breaks the "one prefix per module" convention.

**Why it matters:** When the v1.py aggregator does `router.include_router(notifications_router)`, the notification routes land at multiple URL prefixes. Future router-level rate-limit or auth middleware would need per-path matching rather than per-prefix.

**Suggested fix:** Split into two routers: `notifications_router` at `/notifications`, `notification_preferences_router` at `/users/me/notification-preferences` and `/users/me/push-subscriptions`. Or document the deliberate exception in the module docstring.

---

### REV-020: `Reviews.delete_review` cascades by `await review.delete()` on the in-memory model — but uses soft-delete; double-cascade with diary.delete_entry creates orphans

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/modules/reviews/service.py:399-437 |
| Rule | Cascade ordering |

**What:** `reviews.delete_review` (T087) does the soft-delete dance correctly (`review.deleted_at = now`). But it ALSO clears `DiaryEntry.review_id` (line 431) — which means after a review is soft-deleted, the diary entry no longer points at it. Then if the user soft-deletes the diary entry, the cascade in `diary.delete_entry:440` reads `entry.review_id` and finds None, so doesn't touch the (already soft-deleted) review. ✓ That part works.

However: when `diary.delete_entry` is called FIRST on an entry that still has `review_id`, the cascade hard-deletes the review (REV-003). The Diary entry's `review_id` is NOT cleared in `diary.delete_entry` — so a `restore_entry` brings back the diary entry with a `review_id` pointing at a now-deleted Review row.

**Why it matters:** Stale FK after restore. The diary entry will display "review" UI affordances pointing at a non-existent row.

**Suggested fix:** Either soft-delete the review (REV-003 fix) AND clear `review_id` on the diary entry inside delete_entry, OR keep `review_id` but check `Review.get(...)` is non-null + non-soft-deleted before rendering. Better fix is REV-003 (use soft-delete) and clear `review_id` only on hard-delete cron sweep.

---

### REV-021: `notifications.routes.put_notification_preferences` mutates `User.notification_preferences.version` without bumping

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/notifications/routes.py:607-625 |
| Rule | Optimistic concurrency / version semantics |

**What:** The PUT endpoint replaces `user.notification_preferences` with a new subdoc, copying `version=user.notification_preferences.version` (the previous value). So the version never increments. The presence of a `version: int` field in the model implies it's meant to detect optimistic-concurrency conflicts (or to drive a migration when defaults change).

**Why it matters:** Dead field. If left, future code that depends on version-monotonic ordering will be surprised. If the intent IS to ship versioned prefs (e.g., for migrations or last-write-wins arbitration), the bump is missing.

**Suggested fix:** Either:
1. Bump on every PUT: `new_prefs.version = user.notification_preferences.version + 1`. Then document the contract in the model docstring.
2. Remove the field entirely if it's not actually load-bearing.

---

### REV-022: Workers' `_on_startup` initialises Beanie + builds providers but NEVER inits Redis (the worker process needs Redis for any cache_get / cache_set call inside a job)

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/api/src/auxd_api/workers/main.py:79-95 |
| Rule | Worker subsystem completeness |

**What:** `_on_startup(ctx)` runs `init_db()` and constructs `MusicBrainzCatalogProvider`. It does NOT call `init_redis(REDIS_URL)`. Workers that use `cache_get` / `cache_set` (e.g., `genre_signature.compute_genre_signature` reads the cache for suggestions, but also the worker job `compute_suggestions_for_user` is the caller chain) will silently get None back because `redis_client._client is None`.

The arq worker DOES connect to Redis (for job dispatch) via `WorkerSettings.redis_settings`, but that's the arq-internal connection — not the same as the `_client` module-level singleton in `redis_client.py`.

**Why it matters:** The genre signature cache is silently disabled inside workers. Every suggestions_job worker invocation re-computes a user's genre signature from scratch (500 diary rows + N albums) instead of reading from cache. At MVP scale this is fine but suggests latent waste.

**Suggested fix:** Add `await init_redis(get_settings().REDIS_URL)` to `_on_startup` and `await close_redis()` to `_on_shutdown`. The worker process gains a separate cache client + the arq one; both connect to the same Redis but serve different roles.

---

### REV-023: `merge_albums.py` does `find().to_list()` then loops `save()` instead of `update_many({$set: {album_id: winning}})` — N+1 writes

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/scripts/merge_albums.py:67-93 |
| Rule | Bulk operation efficiency |

**What:** The merge CLI does per-row Beanie .save() calls. The comment says "Uses the Beanie find+save loop rather than a raw `update_many` so the updated_at columns (and any subclass hooks) fire correctly." But none of the FK collections (DiaryEntry, Review, BacklogItem) have non-default Beanie save hooks; they all just bump `updated_at` which `update_many` can set explicitly.

For a popular album that's been logged 5k times, the merge takes 5k Mongo write round-trips ≈ many seconds; an `update_many` would be one round-trip.

**Why it matters:** Operator latency. If the founder merges a duplicate album during peak hours, the script blocks until 5k writes land. Not a correctness issue.

**Suggested fix:** Switch to `await Collection.find({"album_id": album_id_from}).update_many({"$set": {"album_id": album_id_to, "updated_at": now}})` and document that no model has a save() hook that's bypassed.

---

### REV-024: `notifications.routes.list_notifications` uses `Notification.find` with `query["$or"]` for cursor but no fallback handling for malformed cursors that returns a JSON cursor instead of a date

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/api/src/auxd_api/modules/notifications/routes.py:281-307 |
| Rule | Cursor robustness |

**What:** `_decode_cursor` returns `None` on malformed input (good). The route handler then proceeds with no cursor (no `$or` clause added to the query). However, it also doesn't increment any logger / Sentry breadcrumb — so a deliberate URL-tamper goes unnoticed. The notifications inbox cursor uses `{"c": created_at_iso, "i": notification_id}` shape; other endpoints use `{"l": ..., "i": ...}`. Inconsistent.

**Why it matters:** Cursor shape divergence makes a single shared cursor utility harder to extract later. Tampering goes unnoticed.

**Suggested fix:** Standardize cursor shapes across endpoints. Either every cursor uses `{"c": ..., "i": ...}` or every cursor uses `{"l": ..., "i": ...}`. Add a `log_call(..., event="cursor.malformed")` breadcrumb when decode returns None.

---

### REV-025: Tests sub-agent will audit `tests/`; this finding flags one production-code surface where test isolation is fragile

| Field | Value |
|---|---|
| Dimension | Tests-coverage |
| Severity | LOW |
| File | apps/api/src/auxd_api/lib/resilience.py:128-130 (`_default_store`) + apps/api/src/auxd_api/lib/observability.py:205-206 (`_posthog_client`) + apps/api/src/auxd_api/lib/observability.py:318 (`_sentry_initialized`) + apps/api/src/auxd_api/lib/otel.py:59 (`_initialized`) + apps/api/src/auxd_api/modules/notifications/adapters/__init__.py:72 (`_ADAPTERS`) |
| Rule | Module-level mutable state for tests |

**What:** Five module-level mutable singletons that tests need to reset between runs:

- `lib/resilience._default_store` — circuit-breaker state. Has `set_default_store`; tests reset.
- `lib/observability._posthog_client + _posthog_init_attempted` — PostHog client cache. No public reset; tests would need to `import auxd_api.lib.observability as obs; obs._posthog_client = None; obs._posthog_init_attempted = False`.
- `lib/observability._sentry_initialized` — Sentry init guard. No public reset; same monkey-patch problem.
- `lib/otel._initialized` — OTel init guard. Same.
- `adapters/__init__._ADAPTERS` — adapter registry. Has `reset_registry()` + `_register_defaults()`.

**Why it matters:** Test isolation fragility. A test that triggers Sentry init bleeds across to subsequent tests in the same pytest session.

**Suggested fix:** For the 3 init guards (`_sentry_initialized`, `_posthog_client/_posthog_init_attempted`, `lib/otel._initialized`), expose a `reset_for_tests()` helper in each module. Document in the conftest that integration tests must call them in their fixture teardown.

---

## End of findings

---

## Appendix B — Frontend Findings Detail (REV-100..199)


(REV-100 through REV-199; use this ID range only)

---

### REV-100: Avatar upload bypasses `api-client.ts` — no CSRF header on `POST`

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | HIGH |
| File | apps/web/src/components/settings/edit-profile-form.tsx:92 |
| Rule | CSRF — every state-changing call must lift the `auxd_csrf` cookie |

**What:** The avatar upload mutation calls raw `fetch("/api/v1/users/me/avatar", { method: "POST", body, credentials: "include" })` directly because `FormData` doesn't fit the JSON-only `apiClient.post()` signature. This skips `readCsrfToken()` + `X-CSRF-Token` injection. If the backend's `SessionMiddleware` actually enforces CSRF on this endpoint, every avatar upload will 403 in prod. If the backend exempts multipart routes, an attacker can craft a cross-site multipart form and submit on behalf of the victim.

**Why it matters:** This is precisely the regression the T173 lift was meant to prevent. T173's security-review fix protects every documented JSON mutation but the avatar route is the only multipart write surface in the app — easy to miss.

**Suggested fix:**

```ts
// Add a multipart variant to api-client.ts that re-uses readCsrfToken():
export async function apiFetchMultipart<T>(path: string, formData: FormData): Promise<T> {
  const csrfHeaders: Record<string, string> = {};
  const token = readCsrfToken();  // already exported or move it to a shared module
  if (token) csrfHeaders["X-CSRF-Token"] = token;
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json", ...csrfHeaders },
    body: formData,
  });
  // ... same error-handling as apiFetch
}
```
Then in `edit-profile-form.tsx`:
```ts
const data = await apiFetchMultipart<AvatarUploadResponse>("/api/v1/users/me/avatar", body);
```

---

### REV-101: `/api/cover/[size]/[mbid]/route.ts` — open redirect via `fallback` query param

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | HIGH |
| File | apps/web/src/app/api/cover/[size]/[mbid]/route.ts:37-43 |
| Rule | OWASP A1 — Server-Side Request Forgery / open redirect |

**What:** When `coverartarchive.org` returns 404, the route reads `?fallback=...` and issues a 302 redirect to any URL that starts with `https://`. An attacker controlling a third-party cover URL (or any user input that flows into the `fallback` param) can use auxd as an open-redirect oracle. Worse, social/embed crawlers fetching the cover URL may be steered to attacker-controlled content with auxd's first-party caching headers attached.

```ts
if (fallback?.startsWith("https://")) {
  return NextResponse.redirect(fallback, { ... });
}
```

**Why it matters:** Open redirects bypass anti-phishing email filters and OAuth state checks. The current code accepts *any* https URL — this is the canonical anti-pattern called out in OWASP A1.

**Suggested fix:** Allow-list the known cover hosts (MusicBrainz, Discogs, the configured R2 bucket):
```ts
const ALLOWED_FALLBACK_HOSTS = new Set([
  "coverartarchive.org",
  "i.discogs.com",
  "img.discogs.com",
  // plus any S3/R2 hosts the backend can return
]);

if (fallback?.startsWith("https://")) {
  try {
    const url = new URL(fallback);
    if (ALLOWED_FALLBACK_HOSTS.has(url.hostname)) {
      return NextResponse.redirect(fallback, { ... });
    }
  } catch { /* malformed URL */ }
}
return new NextResponse(null, { status: 404, headers: { "Cache-Control": NEGATIVE_CACHE_HEADER } });
```

---

### REV-102: Service worker `notificationclick` opens any server-supplied URL without same-origin check

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/web/public/sw.js:46-55 |
| Rule | Untrusted URL navigation in service-worker context |

**What:** The `notificationclick` handler reads `event.notification.data.click_url` (set in `push` from the payload) and calls `self.clients.openWindow(click_url)`. Because the backend computes `click_url` from notification payloads (some of which contain user-supplied fields — `payload.link` for `system.announcement`, `payload.summary_url` for `weekly.digest`), a misconfigured backend or a row written by a future admin tool could let a third-party URL be opened from the auxd notification context with the auxd origin permissions used to match existing windows.

**Why it matters:** Defense-in-depth. The backend should already sanitize these but the service worker is the last line of defense — and `openWindow` from an SW can launch arbitrary URLs. Browser tracking/phishing from a notification is a known abuse pattern.

**Suggested fix:**
```js
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  let click_url = event.notification.data?.click_url || "/";
  // Force same-origin: drop schemes/hosts entirely and treat as path.
  try {
    const url = new URL(click_url, self.location.origin);
    if (url.origin !== self.location.origin) {
      click_url = "/";  // or url.pathname + url.search + url.hash
    } else {
      click_url = url.pathname + url.search + url.hash;
    }
  } catch {
    click_url = "/";
  }
  event.waitUntil(/* existing matchAll + openWindow */);
});
```

---

### REV-103: `clickUrlFor` returns user-controllable payload URLs as `Link` `href`

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/web/src/lib/notifications.ts:94-110 |
| Rule | XSS / phishing via `<a href=javascript:...>` |

**What:** `clickUrlFor` returns `payload.link` (for `system.announcement`) and `payload.summary_url` (for `weekly.digest`) verbatim as the `href` of `NotificationCard`'s `<Link>`. Today only the backend writes these but there's no validation that the URL is HTTPS or same-origin. A `javascript:` URI would not be triggered by Next's `Link` (it requires path-like hrefs) but `data:text/html`-style payloads in older browsers or third-party hosts could open phishing UI inside the notification list. Next's `Link` does not normalize external URLs into safe `<a target=_blank rel=noopener>` either.

**Why it matters:** `system.announcement` payloads are founder-controlled today, but the field is a generic record; any future writer (admin tool, ops script) that doesn't pre-validate creates a phishing-vector vulnerability.

**Suggested fix:**
```ts
function safeClickUrl(rawUrl: string): string {
  try {
    const url = new URL(rawUrl, "http://example.com"); // dummy base for relatives
    if (rawUrl.startsWith("/")) return rawUrl;
    if (url.protocol !== "https:" && url.protocol !== "http:") return "/";
    return url.toString();
  } catch {
    return "/";
  }
}

case "weekly.digest": {
  const url = payload.summary_url;
  if (typeof url === "string" && url.length > 0) return safeClickUrl(url);
  return "/";
}
// same for system.announcement
```
Additionally, render external URLs in `NotificationCard` with `<a rel="noopener noreferrer">` rather than Next's `<Link>` (which assumes same-origin path routing).

---

### REV-104: `posthog-js` persistence set to `localStorage+cookie` — survives logout

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/web/src/lib/posthog.ts:19 |
| Rule | PII / identity persistence after sign-out |

**What:** `posthog.init({ persistence: "localStorage+cookie" })` keeps the PostHog `distinct_id` in localStorage. There is no `posthog.reset()` call in any logout flow I could find (account-settings.tsx logout-all + suspended.tsx logout + data-settings.tsx delete all call `clearUser()` but never `reset()` from `lib/posthog.ts`). Result: a subsequent user on a shared device inherits the previous distinct_id, conflating two users in analytics and (if PostHog is identified with a real user_id) leaking activity attribution.

**Why it matters:** `lib/posthog.ts` exports `reset()` but no caller imports it. The taxonomy doc explicitly calls for analytics-state cleanup on session termination.

**Suggested fix:** Call `reset()` from `lib/posthog` inside every logout path:
```ts
// In account-settings.tsx logoutAllMutation.onSuccess:
import { reset as posthogReset } from "@/lib/posthog";
// ...
onSuccess: () => {
  posthogReset();
  clearUser();
  toast({ title: "Signed out everywhere" });
  router.push("/login");
},
```
And mirror in `suspended/page.tsx` `onLogout` and `data-settings.tsx` delete flow.

---

### REV-105: `useAuthStore` never reacts to 401/403 — no auto-logout on session expiry

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | MEDIUM |
| File | apps/web/src/stores/auth.ts:18-22 + apps/web/src/lib/api-client.ts (no 401 handler) |
| Rule | Stale auth state after server invalidates session |

**What:** When the session cookie expires or the user is logged out from another device (logout-all-devices bumps `session_version`), the next API call gets 401/403 — but `api-client.ts` only handles the `account_suspended` 403 case. There's no 401 → `clearUser()` + redirect path. The stale `useAuthStore.user` keeps the bottom tabs pointing at `/profile/<handle>`, the FAB visible, etc. — until the layout re-renders and `cookies().get('auxd_session')` finally returns undefined.

**Why it matters:** Spec NFR row "auth state must converge with server within 60s" (implied by the 60s `refetchInterval` on the unread-count). Currently the user sees a broken UI for up to that window after backend invalidation, and `LogSheet` will still mount and try to POST.

**Suggested fix:** In `apiFetch`, after parsing `response.status === 401`, clear the auth store and redirect:
```ts
if (response.status === 401 && typeof window !== "undefined") {
  // Lazy import to avoid SSR coupling.
  const { useAuthStore } = await import("@/stores/auth");
  useAuthStore.getState().clear();
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign("/login");
  }
}
```

---

### REV-106: `prefs-form.tsx` is 552 LOC with embedded ~100-line `GROUPS` config + 3 helpers + form — split it

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | HIGH |
| File | apps/web/src/components/notifications/prefs-form.tsx |
| Rule | Component > 300 LOC; functions > 50 LOC; concerns mixed |

**What:** `prefs-form.tsx` packs:
- The 100-line `GROUPS` taxonomy table (data)
- `emptyPrefs`, `resolveChannel`, `setChannel`, `muteAll`, `buildDiff` (pure helpers)
- Browser-tz resolution helpers
- The 280-line `NotificationPrefsForm` component with two layouts (groups, quiet hours)

Reading and changing one row (e.g. add `friend.high_rated` push) requires scrolling through unrelated code.

**Why it matters:** The taxonomy doc (`notification-taxonomy.md`) is the authoritative source for the GROUPS table — every edit there must propagate here. Splitting reduces the diff size for those edits and makes the form trivially testable in isolation.

**Suggested fix:** Extract three modules:
- `lib/notification-prefs-config.ts` — `GROUPS`, `TypeRow`, `Channel`, defaults
- `lib/notification-prefs-helpers.ts` — `emptyPrefs`, `resolveChannel`, `setChannel`, `muteAll`, `buildDiff`, `getBrowserTimezone`, `buildTimezoneOptions`
- `components/notifications/prefs-form.tsx` — UI component only, ~150 LOC

---

### REV-107: `setApiFormErrors` 422 detail-unwrap pattern duplicated across forms

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/web/src/components/settings/account-settings.tsx:75-79, 101-105; apps/web/src/components/settings/edit-profile-form.tsx:116, 145, 172-175 |
| Rule | DRY |

**What:** Each settings form does its own ad-hoc unwrap of the doubly-nested `error.detail.detail.message` shape:
```ts
const detail = error.detail as { detail?: unknown } | undefined;
if (!setApiFormErrors(emailForm, detail)) {
  const message = (detail?.detail as { message?: string } | undefined)?.message ?? error.statusText;
  toast({ ... });
}
```
The `as { detail?: unknown }` cast is repeated, the `(detail?.detail as { message?: string })` cast is repeated, and the fallback toast pattern is the same.

**Why it matters:** A new settings form will copy-paste the pattern, and any change to the backend error envelope shape requires updating ~5 callsites.

**Suggested fix:** Extend `lib/forms.ts` with a helper that returns the unwrapped message string:
```ts
export function extractApiErrorMessage(error: ApiError): string {
  const payload = error.detail as { detail?: unknown } | undefined;
  if (payload?.detail && typeof payload.detail === "object") {
    const inner = payload.detail as { message?: unknown };
    if (typeof inner.message === "string") return inner.message;
  }
  return error.statusText;
}
```
Then each form is just:
```ts
if (!setApiFormErrors(emailForm, error.detail as ApiErrorPayload)) {
  toast({ title: "Could not change email", description: extractApiErrorMessage(error), variant: "destructive" });
}
```

---

### REV-108: `useEffect` in `edit-profile-form.tsx:76-84` ignores `form` in deps — biome-ignore suppresses

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/web/src/components/settings/edit-profile-form.tsx:75-84 |
| Rule | exhaustive-deps adherence |

**What:**
```ts
// biome-ignore lint/correctness/useExhaustiveDependencies: only rehydrate when the viewer identity changes
useEffect(() => {
  if (viewer) {
    form.reset({ display_name: viewer.display_name, bio: form.getValues("bio"), handle: viewer.handle });
  }
}, [viewer?.id, viewer?.handle, viewer?.display_name]);
```
The intent is documented but the closure also reads `form.getValues("bio")` — if the user has typed in `bio` before the viewer hydrates, that value is preserved (correct), but the rule suppression hides a real subtle bug: if `viewer` itself reference-changes without the watched fields changing (e.g. setUser fires with a fresh object on a refetch), the effect *doesn't* run and the form may end up displaying values not matching what the user expects after a profile-edit roundtrip elsewhere.

**Why it matters:** This pattern is hard to test and prone to subtle regression. The current code happens to work because `setUser` is only called with structurally different objects, but that's a callsite invariant, not an enforced one.

**Suggested fix:** Replace the `useEffect` + biome-ignore with an explicit "key" that triggers reset only when identity changes:
```ts
const viewerKey = `${viewer?.id ?? ""}-${viewer?.handle ?? ""}-${viewer?.display_name ?? ""}`;
useEffect(() => {
  if (viewer) form.reset({ display_name: viewer.display_name, bio: form.getValues("bio"), handle: viewer.handle });
  // safe: form is stable across renders per RHF docs; viewerKey is a primitive
}, [viewerKey, form]);
```

---

### REV-109: `_ = initialFollowerCount` dead-code marker

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/social/follow-button.tsx:107 |
| Rule | Dead code |

**What:**
```ts
const _ = initialFollowerCount; // surfaced for parent UI; not consumed in this button
```
This pattern silences TS-unused-prop warnings but achieves nothing else. If the prop isn't used, it shouldn't be in the type. The comment "surfaced for parent UI" hints that the parent passes it but the button doesn't need it.

**Why it matters:** Confusing for new readers; suggests the prop was supposed to drive an in-button display.

**Suggested fix:** Remove `initialFollowerCount` from `Props`, update the only caller (`profile-client.tsx`) to drop the prop. If the parent UI consumes it, it can read directly from the profile query.

---

### REV-110: Mass-assignment risk on `settings/data-settings.tsx` `apiClient.post("/users/me/data-export")`

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | LOW |
| File | apps/web/src/components/settings/data-settings.tsx:46 |
| Rule | Mass assignment / body shape |

**What:** No body is passed but the form is described in plan §4 to include `format` (csv/json). Today it's not in the UI, so the backend default is used — fine. But if a future change adds a format select, the developer might `body: { format }` directly from state, opening mass-assignment. The other write paths in this file follow the same pattern.

**Why it matters:** This is a forward-looking nit, not a current bug. The codebase consistently doesn't double-check that `body` only contains the documented allow-list keys.

**Suggested fix:** Add a Zod schema for the export body and validate before POST:
```ts
const exportBodySchema = z.object({ format: z.enum(["json", "csv"]).optional() });
exportMutation: async () => apiClient.post<...>("/api/v1/users/me/data-export", exportBodySchema.parse({ format })),
```
The team can defer this until format is added but it should be the explicit convention.

---

### REV-111: `aria-label` of bottom-tabs profile tab routes to `/login` when viewer is null — a11y label drift

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/nav/bottom-tabs.tsx:20 |
| Rule | a11y label / behaviour mismatch |

**What:** `profileHref = viewer?.handle ? \`/profile/${viewer.handle}\` : "/login"` — but the label is still "Profile". Screen reader users see "Profile" link that takes them to a sign-in. Since this layout is inside `(app)/layout.tsx` which requires an `auxd_session` cookie, the case is rare but reachable: stale cookie, hydration gap, the user store hasn't been populated yet.

**Why it matters:** A11y nit, minor edge case. The (app) layout cookie gate should make this unreachable in practice — but the layout uses a different cookie check than the store hydration, so there's a race.

**Suggested fix:** Either hide the tab or relabel:
```ts
{ href: profileHref, label: viewer ? "Profile" : "Sign in", Icon: User, match: ... }
```
Or skip the profile tab entry entirely when `viewer == null`.

---

### REV-112: `<a href="/onboarding/step-3">` raw anchor in client-rendered React tree

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/web/src/components/onboarding/follow-critics-deck.tsx:158 |
| Rule | Use `next/link` for in-app navigation |

**What:** The "Skip for now" button uses `<Button asChild><a href="/onboarding/step-3">…</a></Button>`. Every other in-app navigation uses `<Link>`. The raw `<a>` will trigger a full document reload instead of client-side navigation, losing TanStack Query cache and PostHog session continuity.

**Why it matters:** Inconsistent with the rest of the codebase (8 `<Link>` usages within onboarding/ alone). Causes a full page reload at the exact moment the user is mid-onboarding-funnel.

**Suggested fix:**
```tsx
<Button asChild variant="outline">
  <Link href="/onboarding/step-3">Skip for now</Link>
</Button>
```

---

### REV-113: Optimistic local update in `LikeButton` can drift from server when `recent_likers` heuristic is wrong

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/review-card/like-button.tsx:30-37 |
| Rule | Error handling / state convergence |

**What:** Comment in the file acknowledges this:
> The viewer-has-liked state is derived heuristically from the parent's `recent_likers` array (only the last ~10 likers are tracked server-side) so the first click after a long gap may show "Like" when the server already records a like — the POST is idempotent and the server response heals the UI.

The optimistic flip + count adjustment will momentarily display the wrong state before the response. For a viewer who has liked an old review, clicking "Like" decrements the counter (because `liked` starts false), then the server response sets the correct state. Visible flicker.

**Why it matters:** Documented trade-off but the count flicker is visible. Easy to fix: read the server's response synchronously and don't apply the optimistic count delta until we know we'd be right.

**Suggested fix:** Disable optimistic count delta for `initialLiked === false` (since we don't trust it) and only update count on `onSuccess`:
```ts
onMutate: (nextLiked) => {
  const prev = { liked, count };
  setLiked(nextLiked); // optimistic UI flip is fine
  // Don't optimistically change count — wait for server response.
  return prev;
},
```

---

### REV-114: Two TabsContent fixes (T171) — verified stuck

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/web/src/components/feed/feed-list.tsx:54-63; apps/web/src/components/diary/diary-list.tsx:157-166 |
| Rule | Radix Tabs invariants — TabsContent must exist for each TabsTrigger value |

**What:** Both files include `<TabsContent value="..." className="sr-only" />` with comments referencing T171. Looks correct — `feed-list.tsx` lines 62-63 (for_you / latest), `diary-list.tsx` lines 164-165 (all / auxed). The class `sr-only` is the right choice (Radix needs a DOM node for `aria-controls` to resolve; visual content is rendered elsewhere). Verified the fix is in place.

**Why it matters:** Just confirming the T171 fix didn't get reverted. The pattern could be extracted into a custom hook if more Tabs surfaces appear, but for two callsites it's fine inline.

**Suggested fix:** None needed — the fix is correctly applied. Consider documenting this pattern in the codebase analysis doc so future Tabs usages don't omit it.

---

### REV-115: `LogSheet` `useEffect` resets state on `[open, seed]` — seed-change-without-open mutates UI

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/web/src/components/log-sheet/index.tsx:64-84 |
| Rule | useEffect dependency drift |

**What:**
```ts
useEffect(() => {
  if (!open) { /* reset everything */ return; }
  setOpenedAt(performance.now());
  if (seed?.edit) { setRating(...); setAuxed(...); ... }
}, [open, seed]);
```
The dep array includes `seed` (an object). If the parent passes a *new* seed object reference while the sheet is open (e.g. after a feed refresh), this effect runs, resets the openedAt timestamp, and overwrites the user's in-progress rating/aux/visibility selections with whatever's in the new seed. The user loses unsaved input.

**Why it matters:** This is a known gotcha with object-typed deps. The `openLogSheet({...})` pattern in the codebase always creates a fresh object via spread, so reference equality is broken on every parent re-render.

**Suggested fix:** Either:
- Depend on stable primitives: `[open, seed?.album_id, seed?.edit?.entry_id]`
- Or split into two effects (one for `open` toggling reset, one for explicit seed changes via id)

```ts
useEffect(() => {
  if (!open) {
    setRating(null); setAuxed(false); setReviewBody(""); setVisibility("public");
    setOpenedAt(null); setSubmitting(false);
  } else {
    setOpenedAt(performance.now());
  }
}, [open]);

useEffect(() => {
  if (open && seed?.edit) {
    setRating(seed.edit.rating);
    setAuxed(seed.edit.auxed);
    setVisibility(seed.edit.visibility);
    setReviewBody("");
  }
}, [open, seed?.edit?.entry_id]);
```

---

### REV-116: `notification-list.tsx` `markReadMutation` doesn't pass mutation key — duplicate clicks fire duplicate POSTs

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/notifications/notification-list.tsx:29-39 |
| Rule | Mutation idempotency |

**What:** Clicking a notification calls `markReadMutation.mutate(id)`. If the user double-clicks (or the click handler races the navigation), two POSTs go out. The mutation is idempotent on the server but the request spam is wasteful.

**Why it matters:** Not a bug but minor performance / observability noise.

**Suggested fix:** Use `useMutation`'s `mutationKey` or check `markReadMutation.isPending` before firing:
```ts
function handleActivate(notification: NotificationItem) {
  if (notification.read_at === null && !markReadMutation.isPending) {
    markReadMutation.mutate(notification.id);
  }
  capture("notifications.opened", { ... });
}
```

---

### REV-117: `formError` set then never reset in `prefs-form.tsx` `onSuccess`

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/notifications/prefs-form.tsx:300-329 |
| Rule | State cleanup |

**What:** On a successful save, `onSuccess` calls `setFormError(null)` — good. But `formError` is then displayed as `<p role="alert">...`. If the form errors, then the user fixes and saves successfully, the previous error state IS cleared. However, *navigating away and back* doesn't because `formError` is local component state that's re-mounted fresh. The display is fine.

**Why it matters:** Actually this one is fine on closer inspection. Keeping the finding to document the verification.

**Suggested fix:** None — the code is correct. Leaving the finding number reserved.

---

### REV-118: `aria-busy` not set on multi-mutation forms when only handle is saving

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/web/src/components/settings/edit-profile-form.tsx:235 |
| Rule | A11y `aria-busy` consistency |

**What:** The form sets `aria-busy={profileMutation.isPending || handleMutation.isPending}` but doesn't include `avatarMutation.isPending` — uploading the avatar via the file picker doesn't signal busy state to AT. Minor.

**Why it matters:** Screen reader users uploading a large avatar won't get the busy announcement.

**Suggested fix:**
```tsx
aria-busy={profileMutation.isPending || handleMutation.isPending || avatarMutation.isPending}
```
And consider disabling the save button while avatar upload is pending, since the user expects "Save" to capture all changes including avatar.

---

### REV-119: `PromptCriteriaInput.now` defaults to `Date.now()` at call site — non-deterministic in jest tests if not passed

| Field | Value |
|---|---|
| Dimension | Tests (coverage) |
| Severity | LOW |
| File | apps/web/src/components/notifications/push-prompt.tsx:44 |
| Rule | Time-dependent behavior should accept clock injection |

**What:** `push-prompt.tsx` calls `shouldShowPushPrompt({ ..., now: Date.now() })` — but the helper accepts `now` as a parameter (good). The component itself reads `Date.now()` at the call site. Unit tests of the component (none exist; only the helper is tested) would need to mock `Date.now`. The helper itself is well-tested per `push-subscription.test.ts`.

**Why it matters:** Most components rely on `Date.now()` directly — would be useful to add a `useNow()` hook or pass `now` explicitly in tests. Not a blocker.

**Suggested fix:** None required. The helper is correctly designed; only the consumer skirts deterministic testing. If you add component tests later, mock `Date.now`.

---

### REV-120: No `error.boundary.tsx` anywhere — uncaught errors crash the route

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | HIGH |
| File | apps/web/src/app/* (no `error.tsx` files) |
| Rule | Error boundaries for App Router routes |

**What:** A search of `apps/web/src/app` finds no `error.tsx`, `global-error.tsx`, or `not-found.tsx` files. Any uncaught render error in a server or client component bubbles to Next's default error UI ("Something went wrong"), which is not branded and doesn't capture to Sentry from the client side reliably.

**Why it matters:** This is one of the standard Next.js 15 App Router conventions — `error.tsx` adjacent to a route segment catches all errors in that subtree and renders fallback UI plus calls Sentry. Without it, the user sees a blank "Something went wrong" page with no retry path. `lib/sentry.ts` exports `captureClientError` but there's no client-side ErrorBoundary using it.

**Suggested fix:** Add at minimum:
- `apps/web/src/app/(app)/error.tsx` — branded "Something went wrong" with retry button and Sentry capture
- `apps/web/src/app/global-error.tsx` — last-resort root error UI
- `apps/web/src/app/not-found.tsx` — branded 404

Template:
```tsx
"use client";
import { Button } from "@/components/ui/button";
import { captureClientError } from "@/lib/sentry";
import { useEffect } from "react";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { captureClientError(error, { digest: error.digest }); }, [error]);
  return (
    <div className="container max-w-3xl py-6">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="text-sm text-muted-foreground">We logged the error. Try again or head back home.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
```

---

### REV-121: Reviews list in `album-detail/reviews-list.tsx` reuses `feedSort` from UI store — coupling

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | MEDIUM |
| File | apps/web/src/components/album-detail/reviews-list.tsx:27 + apps/web/src/components/profile-reviews/profile-reviews-list.tsx:49 |
| Rule | Single-state-key for two unrelated UI surfaces |

**What:** Both album-detail reviews list and profile-reviews list read `feedSort` from `useUiStore`. They share the same persisted state key. Changing the sort on an album page changes the sort on profile reviews and vice versa. The home feed list does NOT consume `feedSort` (it has its own `mode` state), so the key is misleadingly named.

**Why it matters:** User flips sort on album X to "Most Liked", goes to profile, sees "Most Liked" already selected. That might be intentional (consistency) or surprising (each surface has different optimal sort defaults). The store key name `feedSort` doesn't reflect its scope.

**Suggested fix:** Either:
- Rename to `reviewsSort` to reflect actual usage (and update both consumers + persist key migration)
- Or split into two store entries: `albumReviewsSort` and `profileReviewsSort`

The product spec doesn't explicitly state the intent, so this needs a product call.

---

### REV-122: `cover/[size]/[mbid]/route.ts` uses lax MBID regex (`{20,}` chars)

| Field | Value |
|---|---|
| Dimension | Security |
| Severity | LOW |
| File | apps/web/src/app/api/cover/[size]/[mbid]/route.ts:20 |
| Rule | Strict input validation |

**What:** MBIDs are UUIDs (exactly 36 chars, format `8-4-4-4-12`). The current regex `/^[a-f0-9-]{20,}$/i` accepts anything 20+ chars containing only hex+dash. Attackers can probe with `aaaaaaaaaaaaaaaaaaaa` (20 a's) which passes validation, gets passed to coverartarchive.org as a release-group identifier, returns 404, then triggers the `fallback` redirect path (see REV-101).

**Why it matters:** Composes with REV-101 to amplify the open-redirect attack surface.

**Suggested fix:** Use the canonical UUID regex:
```ts
const MBID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
if (!MBID_RE.test(mbid)) {
  return NextResponse.json({ error: "invalid_mbid" }, { status: 400 });
}
```

---

### REV-123: Missing `not-found.tsx` for `/album/[id]` and `/review/[id]` 404 cases

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/web/src/app/(app)/album/[id]/page.tsx:53 + apps/web/src/app/(app)/review/[id]/page.tsx:69 |
| Rule | UX on missing resources |

**What:** Both routes call `notFound()` when the backend returns 404, which renders Next's default 404 page. No branded "Album not found" or "Review removed" UI.

**Why it matters:** Reviews can be deleted (30-day trash). Album IDs can be merged away or removed by founder CLI. User clicking a stale link gets a generic 404.

**Suggested fix:** Add `apps/web/src/app/(app)/album/[id]/not-found.tsx` and `apps/web/src/app/(app)/review/[id]/not-found.tsx`:
```tsx
import Link from "next/link";
export default function ReviewNotFound() {
  return (
    <div className="container max-w-2xl py-12 text-center space-y-3">
      <h2 className="text-xl font-semibold">Review unavailable</h2>
      <p className="text-sm text-muted-foreground">It may have been deleted or set to private.</p>
      <Link href="/" className="underline">Back to home</Link>
    </div>
  );
}
```

---

### REV-124: `recent-searches.tsx` doesn't cap blob size — localStorage quota DoS

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/components/log-sheet/recent-searches.tsx:23-30 |
| Rule | Bounded persisted state |

**What:** `recent` array is capped at `MAX_RECENT = 5` and the album cover URL is the only large field. Each `RecentSearch` is `LogSheetSeed & { query: string; title: string; artist_name: string }`. Five entries in localStorage is bounded; no DoS risk. Verified correct.

**Why it matters:** Documenting the audit.

**Suggested fix:** None. Keeping the finding to record the explicit verification.

---

### REV-125: Tests (coverage) — `LogSheet` (250 LOC, payment-critical interaction) has no component test

| Field | Value |
|---|---|
| Dimension | Tests (coverage) |
| Severity | HIGH |
| File | apps/web/tests/unit/ — no `log-sheet.test.ts*` |
| Rule | Test coverage of the wedge UI |

**What:** Tests exist for: `api-client`, `analytics`, `forms`, `notifications-copy`, `og-route`, `profile-reviews`, `push-subscription`, `social-types`. The log sheet is the conversion wedge for the whole product and has 250 LOC of state management (rating, aux, visibility, review body, edit vs create branches, optimistic invalidation). E2E specs cover the happy path (`log-wedge.spec.ts`, `tc-e2e-003-wedge-log.spec.ts`) but there's no unit test that pins:
- The 4 different toast messages (logged/already-logged/relisten/error)
- The edit-vs-create body shape
- The reset-on-close behaviour
- The "openedAt + commitMs" PostHog property emission

**Why it matters:** This is the highest-value interaction in the app. Refactors to the LogSheet currently rely solely on E2E for catching regressions, which is slow and high-flake.

**Suggested fix:** Add `tests/unit/log-sheet.test.tsx` that renders the component with mocked queryClient + apiClient and exercises:
- Submitting in create mode emits `log.commit` with the right properties
- Submitting in edit mode emits `log.edit`
- 404 in create shows the "not in catalog" toast
- 403 in edit shows the "own entries" toast

---

### REV-126: Tests (coverage) — no a11y spec for `/suspended` or `/legal/*` standalone routes

| Field | Value |
|---|---|
| Dimension | Tests (coverage) |
| Severity | MEDIUM |
| File | apps/web/tests/a11y/standalone.spec.ts |
| Rule | T171 covered 23 routes; verify suspended/legal pages covered |

**What:** Checked `tests/a11y/`: `app.spec.ts`, `auth.spec.ts`, `onboarding.spec.ts`, `settings.spec.ts`, `standalone.spec.ts`. Without reading the test files (out of scope), I can verify the route list in `standalone.spec.ts` covers `/suspended`, `/legal/privacy`, `/legal/terms` only if those exist. The directory enumeration suggests yes, but the explicit verification belongs to the tests sub-agent.

**Why it matters:** /suspended is reached on suspended-account 403 (T159) — a critical compliance/UX surface that must be a11y-clean.

**Suggested fix:** Tests sub-agent should verify standalone.spec.ts iterates `["/suspended", "/legal/privacy", "/legal/terms"]`. If any is missing, add. Flagging here for cross-reference.

---

### REV-127: Tests (coverage) — `cover/[size]/[mbid]/route.ts` has no unit test (handles open-redirect logic)

| Field | Value |
|---|---|
| Dimension | Tests (coverage) |
| Severity | MEDIUM |
| File | apps/web/tests/unit/ — no `cover-route.test.ts` |
| Rule | Route handler coverage for security-relevant code |

**What:** The cover proxy route is the only frontend code with a `NextResponse.redirect` to an externally-supplied URL (see REV-101). No unit test exercises:
- 200 path (upstream OK)
- 404 with fallback redirect (the security-relevant case)
- 404 without fallback (clean 404)
- Invalid MBID rejection
- Invalid size rejection
- Network failure → 502

**Why it matters:** Without coverage, the open-redirect fix (REV-101) will be hard to verify.

**Suggested fix:** Add `tests/unit/cover-route.test.ts` mocking `global.fetch`. Use the same shape as `og-route.test.ts`.

---

### REV-128: `prefs-form.tsx` `select` element uses raw HTML, not the `Select` shadcn primitive

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/web/src/components/notifications/prefs-form.tsx:516-533 |
| Rule | shadcn primitives consistency |

**What:** Quiet-hours timezone selector is `<select>` (raw HTML) — every other dropdown in the codebase uses the `Select` primitive from `@/components/ui/select`. Visual inconsistency + no Radix portal => no keyboard nav parity.

**Why it matters:** Inconsistent styling and accessibility behavior (no `aria-listbox`, no typeahead).

**Suggested fix:**
```tsx
<Select value={prefs.quiet_hours.tz} onValueChange={(v) => setPrefs(current => ({ ...current, quiet_hours: { ...current.quiet_hours, tz: v } }))}>
  <SelectTrigger id="quiet-hours-tz" className="h-9">
    <SelectValue />
  </SelectTrigger>
  <SelectContent>
    {tzOptions.map(tz => <SelectItem key={tz} value={tz}>{tz}</SelectItem>)}
  </SelectContent>
</Select>
```

---

### REV-129: Optimistic update in `PrivacySettingsForm` reads but never re-fetches profile query key

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | MEDIUM |
| File | apps/web/src/components/settings/privacy-settings-form.tsx:56-61, 81 |
| Rule | TanStack Query cache invalidation pattern |

**What:** The `profileQuery` is `enabled: false` (never runs) — the form uses `DEFAULT_STATE` as initial state, then the PUT response becomes the source of truth. On `onSuccess`, the code calls `queryClient.invalidateQueries({ queryKey: ["profile"] })` — but the `profileQuery` key here is `PRIVACY_QUERY_KEY = ["settings", "privacy"]`, not `["profile"]`. The invalidation targets a different query entirely (the profile_client.tsx one).

**Why it matters:** This works in practice because profile pages will refetch when navigated to. But the local form initial state is `DEFAULT_STATE`, not the user's saved values — every time the user opens /settings/privacy fresh, the toggles show the defaults until they save once. The user-friendly behavior would be to fetch the current state from `/api/v1/users/me` and populate the form.

**Suggested fix:** Either:
- Enable the query and use the `/users/me` (or a real `privacy/state` endpoint) to seed the form
- Or explicitly state in the UI that "currently saved values are shown after you save"

```ts
const profileQuery = useQuery({
  queryKey: PRIVACY_QUERY_KEY,
  queryFn: async () => apiClient.get<ProfileResponse>("/api/v1/users/me"),
  enabled: true,
  staleTime: 30_000,
});
```

---

### REV-130: `feedSort` cast pattern `(value: string) => value as "newest" | ...` repeated

| Field | Value |
|---|---|
| Dimension | Patterns |
| Severity | LOW |
| File | apps/web/src/components/album-detail/review-sort-select.tsx:16 + apps/web/src/components/log-sheet/index.tsx:185 + apps/web/src/components/diary/diary-list.tsx:157 |
| Rule | DRY type casting |

**What:** Multiple components use the pattern `onValueChange={(v) => setFoo(v as FooType)}` to coerce a Radix Select value back into a typed enum. The cast is unsafe — if the Select is misconfigured, an invalid string slips through.

**Why it matters:** Minor type-safety nit.

**Suggested fix:** Wrap with a parser:
```ts
function parseFeedSort(v: string): FeedSort {
  return v === "most_liked" || v === "highest_rated" ? v : "newest";
}
// ...
onValueChange={(v) => setFeedSort(parseFeedSort(v))}
```
Or build a small generic helper in `lib/utils.ts`.

---

### REV-131: `analytics.ts` writes onboarding stash to localStorage with no expiration

| Field | Value |
|---|---|
| Dimension | Quality |
| Severity | LOW |
| File | apps/web/src/lib/analytics.ts:21, 50 |
| Rule | Bounded persisted state |

**What:** `auxd:onboarding:started_at` and `auxd:onboarding:follows_summary` are written without a TTL. If a user abandons onboarding partway through, then signs up *again* with a different account on the same device months later, the old `started_at` is still there. `emitOnboardingCompleted` will compute a `time_to_complete_ms` of years.

**Why it matters:** Data-quality nit. Affects the funnel metrics for the cohort that abandons + retries.

**Suggested fix:** On `markOnboardingStart`, check the existing timestamp and overwrite if it's > 30 days old:
```ts
export function markOnboardingStart(): void {
  if (typeof window === "undefined") return;
  const existing = window.localStorage.getItem(ONBOARDING_START_TS_KEY);
  if (existing !== null) {
    const startedAt = Number(existing);
    if (Number.isFinite(startedAt) && Date.now() - startedAt < 30 * 24 * 60 * 60 * 1000) {
      return; // recent — keep
    }
  }
  window.localStorage.setItem(ONBOARDING_START_TS_KEY, String(Date.now()));
}
```

---

---

## Appendix C — Tests + Shared-Types Findings Detail (REV-200..249)


(REV-200..249 reserved for tests/shared-types layer.)

### REV-200 — HIGH — Quality — Vitest config excludes web/tests outside `tests/unit/`
**File:** `apps/web/vitest.config.ts`
**Issue:** `include: ["tests/unit/**/*.test.ts"]` is correct for the unit tests, but the config also sets `exclude: ["tests/e2e/**", ...]` and runs in `environment: "node"`. CI step `pnpm --filter @auxd/web test:unit` therefore can only ever pick up `tests/unit/`. Today that's fine. The HIGH severity comes from the fact that **no** vitest run will ever detect a stray Vitest test placed under `tests/a11y/`, `tests/perf/`, or `tests/components/`. There's no positive guard in CI catching the misplacement.
**Fix:** Add a sanity assertion in CI (or a pre-commit hook) that searches for `*.test.ts` outside `tests/unit/**` and fails loudly. Alternatively, add a `*.test.ts` glob test in `vitest.config.ts` that errors when a non-unit test file is discovered.

### REV-201 — HIGH — Coverage — Avatar rate-limit test missing despite docstring claim
**File:** `apps/api/tests/integration/test_avatar_upload.py` (lines 1-263)
**Issue:** The module docstring lists "5/min per-user rate limit (boundary check)" as covered, but the file contains only 6 tests (auth/415/413/200/422/415-corrupt). No test exercises the rate-limit dimension on `POST /api/v1/users/me/avatar`. T146 implementation should have a per-user limit (most write endpoints do), and the boundary case is exactly the regression a future refactor would silently break. Reports endpoints (`test_reports_endpoints.py:439`) and album reports (`test_reports_album_endpoint.py:289`) DO assert their rate-limit boundaries — avatar is the odd one out.
**Fix:** Add `test_avatar_upload_rate_limited_after_five_in_one_minute` that posts 5 valid uploads then asserts the 6th returns 429. Use the same `_bypass_rate_limit`-style pattern but bypassed-by-default and explicitly opt-in for this test, OR drive the real rate-limit dependency with a fakeredis client. Either way, the docstring promise should match reality.

### REV-202 — HIGH — Patterns — `FakeAuthMiddleware` is duplicated across 26 integration tests
**Files:** 26 integration files (verified via grep: `_FakeAuthMiddleware` defined inline in 26 different files including `test_avatar_upload.py`, `test_diary_logging.py`, `test_log_perf.py`, `test_gdpr_export.py`, `test_feed_perf.py`, etc.)
**Issue:** Every integration test that needs a forged session re-implements the same ~15-line middleware class identically (same `Session(...)` construction, same `X-User-Id` header semantics, same UTC delta on `expires_at`). A drift in `Session` shape — e.g. adding a new required field — would cause 26 simultaneous fixes. The codebase-analysis.md called this out as "the FakeAuthMiddleware pattern from `test_suggestions_endpoint.py`"; in practice it was copy-pasted, not centralised.
**Fix:** Extract to `apps/api/tests/_fixtures/fake_auth.py` (or `tests/conftest.py` as a `pytest.fixture` returning a configured `FastAPI` app, or a helper `make_test_app(routers=[...])`). New tests would `from tests._fixtures.fake_auth import FakeAuthMiddleware`. Reduces ~390 lines of duplication and makes session-shape drift a single-file fix.

### REV-203 — MED — Quality — Lighthouse perf test skips by default with no CI signal
**File:** `apps/web/tests/perf/lighthouse.spec.ts`
**Issue:** All 4 Lighthouse tests are gated on `process.env.E2E_BACKEND_REACHABLE === "true"`. In CI (where backend isn't co-deployed), the test simply skips with no warning. As of T172, the actual perf-audit.md is "Some staging metrics N/A pending T175 staging provisioning". This means perf SLOs (Performance ≥80, A11y ≥90, Best-Practices ≥90) are currently un-enforced — a regression to 60/70/80 on any of the 4 critical screens would ship without anyone noticing until production PostHog metrics flag it days later.
**Fix:** Add a CI workflow `lighthouse.yml` that runs against the staging URL on a schedule (cron weekly is enough for MVP) using `vars.E2E_BACKEND_REACHABLE: "true"` and `vars.PLAYWRIGHT_BASE_URL: https://staging.auxd.xiejoshua.com`. Failure should post to the Discord webhook (same as moderation_scan does). Without this loop closed, T172 is implemented but not exercised.

### REV-204 — MED — Quality — k6 perf scripts not run from CI
**Files:** `apps/api/tests/perf/k6_baseline.js`, `k6_feed_home.js`, `k6_search.js`, `k6_unread_count.js`
**Issue:** The 4 k6 scripts encode the right thresholds (matched against spec.md §6.1 — verified: baseline p95<500, feed p95<300, search p95<400, unread_count p95<400). But they are pure operator-driven scripts with no CI invocation. The "T172 perf audit" therefore proves the scripts exist and run; it does not prove the deployed system meets the thresholds week-over-week.
**Fix:** Add a `perf-nightly.yml` GitHub workflow that runs k6 against staging on a schedule and uploads results to GitHub artifacts. Use the official `grafana/setup-k6-action`. Threshold violations should fail the workflow.

### REV-205 — MED — Patterns — `_clean_env` fixture duplicated across ~50 integration tests
**Files:** Almost every integration test file
**Issue:** `_clean_env` (env hygiene + `monkeypatch.chdir(tmp_path)` + `settings_module.get_settings.cache_clear()`) repeats with minor variations across ~50 files. The variation matters: `test_avatar_upload.py` adds `R2_*` env, `test_email_adapter.py` adds `RESEND_*`, etc. — but the core 4-line preamble is identical.
**Fix:** Promote a base `_clean_env` to `conftest.py` and have specialised tests extend it (`@pytest.fixture` that wraps it and adds the test-specific env). Reduces a known source of pyflake noise and CR-001 cleanup pain (the SPOTIFY removal touched 11 of these fixtures).

### REV-206 — MED — Quality — Feed perf test is misplaced — not under `tests/perf/`
**File:** `apps/api/tests/integration/test_log_perf.py`
**Issue:** The log-wedge p95 test (T084) lives under `tests/integration/`, while the feed perf test (T107) is under `tests/perf/`. Both are `@pytest.mark.perf`-marked (well, only the feed one — `test_log_perf.py` is NOT marked, so `-m 'not perf'` won't exclude it from fast-feedback runs). This inconsistency means:
1. Naming says "perf" but the marker doesn't.
2. The fast-feedback CI run (`uv run pytest -m 'not perf'`) will run the log-wedge perf check on every PR — running 10 logs through TestClient takes ~1-3s typically but is unnecessary noise.
**Fix:** Move `test_log_perf.py` to `tests/perf/test_log_perf.py` (matching the feed) and add `@pytest.mark.perf` to both files' tests. Update CI to either always run with the marker or exclude it; pick a posture and document it in `apps/api/README.md`.

### REV-207 — MED — Coverage — TC-E2E-005 (like → N-004 notif) only covers the actor side
**File:** `apps/web/tests/e2e/tc-e2e-005-like-notif.spec.ts`
**Issue:** TC-E2E-005 is one of the load-bearing notification contracts (spec §10 row 5: "Like → reviewer sees N-004"). The Playwright spec only clicks the like button on A's session and asserts the counter increments. The spec admits this in a comment: "Switch to recipient's session (out of scope for this single-session harness — recommend a separate 'two-browser' test when test-account creation is automated)." Recipient-side N-004 surfacing is the actual user-facing assertion.
**Fix:** Either (a) extend the spec to use a second Playwright `context` for user B and assert the `/notifications` list contains an N-004 entry after A's like, OR (b) downgrade the test name from "TC-E2E-005: like → review-owner gets notified" to "TC-E2E-005-actor: like-side increment" and add a backend `integration/test_review_likes_emits_n004.py` that asserts the dispatcher writes a Notification row to B's collection.

### REV-208 — MED — Coverage — TC-E2E-002 onboarding spec has no negative-path assertion
**File:** `apps/web/tests/e2e/tc-e2e-002-onboarding-mvp.spec.ts`
**Issue:** Asserts the happy path (signup → step-1 → step-2 → step-3 → feed has ≥5 entries). Doesn't assert step-2 enforces ≥3 critic follows before allowing "Next" — a regression that lets users through with 0 follows would land them on an empty feed and silently break the funnel. Spec.md §4.2 makes ≥3 a hard gate.
**Fix:** Add a sub-test (or new TC-E2E-002b) that clicks Next on step-2 with 0/1/2 follows selected and asserts the button is `disabled` (or a validation message appears). Cheap to add; high-value gate.

### REV-209 — MED — Patterns — Tests use direct `BoomAdapter` injection but no shared registry-reset fixture
**File:** `apps/api/tests/unit/test_dispatcher.py:464-498`
**Issue:** `test_dispatch_adapter_exception_does_not_crash` calls `adapters_module.reset_registry()` and `register_adapter(BoomAdapter())` in the test body, with a `try/finally` to restore. If the test errors before the `try` (e.g. fixture raises), the registry stays mutated and EVERY subsequent test in the session uses the boom adapter — silent cross-test pollution.
**Fix:** Promote this to an autouse fixture for the dispatcher module, or use `monkeypatch.setattr(adapters_module, "_registry", ...)` so pytest's teardown handles restoration deterministically.

### REV-210 — MED — Quality — Feed perf test budget masks Atlas-vs-mongomock disparity
**File:** `apps/api/tests/perf/test_feed_perf.py:56`
**Issue:** `P95_BUDGET_MS = 2500.0`. The docstring acknowledges this is generous because "mongomock-motor uses sorted Python lists rather than B-tree indexes". That's defensible, but a 2500 ms budget against a 500-followee fake dataset is so far from production (real spec target <500 ms over the wire on real Atlas) that the test won't catch a 5×-regression from O(N) to O(N²) — it would still come in under 2500 ms on a 500-row fake DB.
**Fix:** Either tighten the budget (try 500 ms — the test runs locally in ~80-150 ms today so there's significant headroom) and let it fail loudly if a regression lands, OR keep the wide budget but add a second assertion that compares each trial against the median (e.g. assert no trial exceeds 3× median) — that catches algorithmic regressions without flaking on cold-CI runs.

### REV-211 — MED — Quality — `test_dispatch_inner_exception_returns_none` patches Sentry SDK on the module
**File:** `apps/api/tests/unit/test_dispatcher.py:507-530`
**Issue:** `monkeypatch.setattr(sentry_sdk, "capture_message", _fake_capture)` patches the SDK globally. While monkeypatch reverses it, the assertion is just `"notification.dispatcher_failed" in captured_calls` — there's no assertion on `level="error"` or message arguments. A regression that changed the message format would not be caught.
**Fix:** Tighten the assertion: `assert captured_calls == ["notification.dispatcher_failed"]` (exact equality), or use `assert any("dispatcher_failed" in msg for msg in captured_calls)` with `len(captured_calls) == 1` so a duplicate or omitted call surfaces.

### REV-212 — LOW — Quality — Smoke spec is a duplicate of `auth.spec.ts` form-validation block
**File:** `apps/web/tests/e2e/smoke.spec.ts`
**Issue:** The 3 smoke tests are functional duplicates of the validation block in `auth.spec.ts`. Both run on every PR (`testMatch: e2e/**/*.spec.ts`), so we pay double the time on the same surface.
**Fix:** Delete `smoke.spec.ts` OR delete the duplicate block from `auth.spec.ts`. The smoke file is the better keep — keep it as the "fastest possible signal" and have `auth.spec.ts` only do the auth-specific bits.

### REV-213 — LOW — Patterns — Tests use `time.perf_counter()` for wall-time but no monkeypatch for time.sleep stubbing
**Files:** `apps/api/tests/perf/test_feed_perf.py`, `tests/integration/test_log_perf.py`
**Issue:** Both files do `time.perf_counter()` deltas and `assert p95 < BUDGET`. Neither uses `freezegun` or stubbing — if the host CI runner happens to hit a noisy minute, the test flakes. Already mitigated by generous budgets (see REV-210), but the pattern means tightening the budget makes flakiness worse.
**Fix:** No immediate action required — but if budgets are tightened, consider re-running each trial twice and using the median sample, OR running the trial loop inside a process with a known CPU affinity. Pure CI infra concern; document the trade-off.

### REV-214 — LOW — Quality — A11y tests assume axe-core impacts are stable
**File:** `apps/web/tests/a11y/helpers.ts:72-93`
**Issue:** The helper hard-codes `"critical" | "serious" | "moderate" | "minor"` impact strings. If axe-core ever adds a 5th impact ("blocker", or renames "critical" to "high"), the test would silently miss violations because the `if (v.impact && v.impact in byImpact)` check filters unknown impacts to no-op.
**Fix:** Add an `else` branch logging unknown impacts: `console.warn(\`unknown axe impact: ${v.impact}\`)` so an axe-core upgrade can't silently bypass the gate.

### REV-215 — LOW — Patterns — Backend `_b64()` helper is duplicated in 25+ files
**Files:** Most integration test files
**Issue:** `def _b64(num_bytes: int) -> str: return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")` is the same 3-line helper copy-pasted everywhere it's needed for env-key generation in test fixtures.
**Fix:** Move to `apps/api/tests/_fixtures/env.py` and import; trivial DRY.

### REV-216 — MED — Coverage — No test asserts `csrf_token_invalid` body shape for POST without header
**File:** `apps/api/tests/integration/test_session_middleware.py`
**Issue:** `test_post_without_csrf_token_returns_403` asserts the 403 status code but I didn't see a body-shape assertion ensuring the response carries `detail.error == "csrf_token_invalid"`. The Vitest CSRF test (`api-client.test.ts`) hard-codes this marker — frontend client behaviour depends on it. If the backend ever drifts from this contract, the frontend would silently fail to recover from CSRF errors.
**Fix:** Add `assert response.json()["detail"]["error"] == "csrf_token_invalid"` to the two `test_post_without_csrf_token_returns_403` and `test_post_with_mismatched_csrf_token_returns_403` cases. Pins the API↔UI contract from both sides.

### REV-217 — MED — Shared-types codegen — No type-level contract test that frontend imports survive
**File:** `packages/shared-types/src/index.ts`
**Issue:** `index.ts` is just `export * from "./api"` plus the legacy `greeting()` smoke export. There's no test that asserts the named exports the frontend actually uses (e.g. `paths`, `components`, `operations`, plus the `ProfileResponse` / `FollowRequestsListResponse` literals consumed by `social-types.test.ts`) are present after codegen. If a future OpenAPI schema change drops a path or renames a component, the codegen succeeds, the codegen:check passes (no diff vs committed file), but the frontend would compile-fail at build time — too late.
**Fix:** Add `packages/shared-types/src/__tests__/exports.test.ts` (or co-locate under `apps/web/tests/unit/shared-types-contract.test.ts`) that imports a few load-bearing types (`paths`, `components`, the `ProfileResponse` literal) and asserts they're typeof `'object'` / truthy. Cheap compile-time + runtime guard.

### REV-218 — MED — Shared-types codegen — Codegen workflow has no `paths:` for `.github/workflows/codegen.yml`
**File:** `.github/workflows/codegen.yml:11-20`
**Issue:** Triggers on changes to `apps/api/**`, `packages/shared-types/**`, and the workflow itself. Good. But the workflow runs `pnpm install --frozen-lockfile` at root, which means a `pnpm-lock.yaml` change anywhere can also drift codegen output if a transitive update changes openapi-typescript's serialisation. There's no version pin beyond the package.json semver range (`"openapi-typescript": "^7.4.0"`). A minor bump from 7.4.0 to 7.5.0 could produce a slightly different `api.ts` and the codegen:check would fail spuriously across all PRs until someone re-runs codegen.
**Fix:** Pin `openapi-typescript` exactly (no `^`) in `packages/shared-types/package.json`, OR add a comment in the workflow that says "if codegen:check fails after a dep bump, run codegen locally and commit". Better: switch to `pnpm install --frozen-lockfile --strict-peer-dependencies` and ensure the lockfile is the canonical version source.

### REV-219 — LOW — Shared-types codegen — README is stale (T028 marked as "real types land in T028" but T028 has shipped)
**File:** `packages/shared-types/README.md`
**Issue:** Reads: "Currently a placeholder — real types land in **T028 (OpenAPI → TS codegen)**". Feature is at 172/172 and api.ts is 3929 lines of real generated types. The README still says it's a placeholder.
**Fix:** Update README to describe the actual pipeline (`codegen.sh` regenerates `src/api.ts` from `auxd_api.main:app.openapi()`, codegen:check enforces freshness in CI, T173 added X-CSRF-Token to allowlist). 5-minute fix; high signal-to-noise on every new contributor's first read.

### REV-220 — MED — Quality — `test_otel.py` mutates OTel SDK internals via underscore-prefixed attributes
**File:** `apps/api/tests/test_otel.py:80-83`
**Issue:** `_reset_global_tracer_provider()` pokes `trace._TRACER_PROVIDER_SET_ONCE._done = False` and re-creates `trace._PROXY_TRACER_PROVIDER`. The docstring acknowledges this. The risk: an OTel SDK minor upgrade could rename or restructure these privates and the test would crash with `AttributeError` — at least it's loud. But there's no upper-bound version pin on `opentelemetry-sdk` in `pyproject.toml`. A passive `uv sync` could promote a minor version and break the suite.
**Fix:** Add an explicit upper-bound pin on `opentelemetry-sdk` (e.g. `>=1.27,<2.0`) so a major SDK change is gated through a deliberate test review. Alternatively, file an issue with OpenTelemetry's Python SDK requesting a public `reset_tracer_provider()` API — there are several other projects with the same need.

### REV-221 — LOW — Quality — Search test docstring claims "Atlas + MusicBrainz + Discogs fallback" but mock injection makes the providers indistinguishable
**File:** `apps/api/tests/integration/test_search_endpoint.py:8-14`
**Issue:** Tests use `AsyncMock` for both `_mb_provider` and `_discogs_provider` via `dependency_overrides`. The test exercises the merge logic (Atlas + MB + Discogs hits) but the AsyncMock doesn't differentiate provider identity at the integration boundary — a regression that called Discogs before MusicBrainz would still pass.
**Fix:** Tag each `CatalogAlbum` mock return with a `source=` discriminator (e.g. `AlbumSource.MUSICBRAINZ` vs `AlbumSource.DISCOGS`) and assert the merge order in the response prefers MB hits ahead of Discogs hits. Cheap precision improvement.

### REV-222 — LOW — Patterns — Some tests use `pytest_asyncio.fixture` while others use `pytest.fixture` with async body
**Files:** Several integration tests
**Issue:** `apps/api/pyproject.toml` sets `asyncio_mode = "auto"`. Under auto mode, `@pytest.fixture` on an async function works, but the conventional `@pytest_asyncio.fixture` is more explicit. The codebase mixes both styles freely. Functionally identical; just a style inconsistency.
**Fix:** Pick one and ruff-enforce. Either standardise on `@pytest_asyncio.fixture` (more explicit) or `@pytest.fixture` (drop the extra import). The codebase-analysis.md called for `@pytest_asyncio.fixture` — that's the documented convention.

### REV-223 — MED — Coverage — TC-E2E-010 to TC-E2E-013 only cover the UI form-shell, not the backend round-trip
**Files:** `tc-e2e-010-handle-change.spec.ts`, `tc-e2e-011-block.spec.ts`, `tc-e2e-012-data-export.spec.ts`, `tc-e2e-013-account-deletion.spec.ts`
**Issue:** Each spec has a UI-only branch (no backend) that asserts the heading + button visibility, then a backend-required branch skipped by default. In practice the UI-only branch is the only thing exercised in PR CI. The end-to-end contracts (handle redirect persists, block reciprocates, export email arrives, deletion grace banner appears) are only exercised when an operator runs against staging — and there's no scheduled job doing so.
**Fix:** This is acceptable for MVP given staging isn't provisioned, but the launch checklist should include "manually exercise TC-E2E-010..013 against staging post-deploy" and the result should be appended to `docs/launch.md`. Without that, these 4 tests are giving false confidence in CI.

### REV-224 — LOW — Quality — `test_avatar_upload_happy_path` doesn't assert on the rate-widget side effects
**File:** `apps/api/tests/integration/test_avatar_upload.py:217-218`
**Issue:** `assert set(body["sizes"].keys()) == {"256", "128", "64"}` confirms three sizes were generated, but the test doesn't assert that the actual image bytes uploaded to R2 differ between sizes. A regression that uploads the same image to all three keys would pass.
**Fix:** Assert `_stub_r2.calls[0]["Body"] != _stub_r2.calls[1]["Body"]` or, better, assert each call's `Body` decodes to a JPEG of the expected dimensions.

### REV-225 — MED — Patterns — `apps/web/tests/perf/lighthouse.spec.ts` spawns Chromium 4 times (1 per test)
**File:** `apps/web/tests/perf/lighthouse.spec.ts:48-99`
**Issue:** Each of the 4 tests does `chromium.launch({ args: [\`--remote-debugging-port=${LH_PORT}\`] })`. With `LH_PORT = 9222` fixed and `describe.serial`, this should work — but 4 sequential browser launches at 5-10s each adds 20-40s to the CI run. If the test ever drops `.serial`, two simultaneous launches on port 9222 will collide and the second fails opaquely.
**Fix:** Move browser launch + teardown into a `test.beforeAll/afterAll` hook; reuse one Chromium across all 4 URLs. Bonus: also surface the actual Lighthouse score numbers (today the spec swallows them — only the threshold pass/fail is visible).

### REV-225b — LOW — Coverage — No test asserts the OG route renders without backend
**File:** `apps/web/tests/unit/og-route.test.ts`
**Issue:** Tests `truncate`, `backendUrl`, and the constants. Doesn't render the actual OG image route. The OG image generation has a known failure mode (Vercel cold-start + edge function timeout) and the SEO impact is high (album-share Open Graph preview).
**Fix:** Optional — add a Playwright-driven smoke test that loads `/api/og?album_id=test-album` and asserts a 200 + `content-type: image/png`. Possibly out of scope for the unit-test layer; defer if the e2e doesn't run against deployed Vercel.

## Out of scope notes

- I noticed `apps/api/tests/integration/test_reports_endpoint.py` (singular) AND `test_reports_endpoints.py` (plural) coexist; appears intentional (different concerns — singular is the older T155, plural is T156). Confirmed not duplicates.
- Conftest's `backlog_id_1_album_id_1` index reconstruction is a load-bearing mongomock workaround. Tested via `test_backlog_endpoints.py` 409 assertions on duplicate adds — without the conftest fix, those tests would silently pass for the wrong reason. This is exactly the kind of mock quirk-handling that should be commented as it is.
- `test_app_lifespan_migrations.py` correctly exercises the T030 migration runner pre-route-handlers. Not flagged.
