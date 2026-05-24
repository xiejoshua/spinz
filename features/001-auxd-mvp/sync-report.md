# Sync & Verify Report: auxd MVP — Social Album Platform

> Feature: `001-auxd-mvp` | **Latest run: #12 — 2026-05-24 (post-Sessions 23-25: §14 Profile/Settings + §15 GDPR/Moderation + §16 Seeding admin + §17 Should-have)**

---

## Run #12 (2026-05-24, post-§14-§15-§16-§17)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **155/172** tasks complete (90%)
> Prior run: #11 (2026-05-23, post-§11+§13+stranded) — DRIFT_DETECTED, applied_split_with_override (17 inline + 5 deferred — pending user confirmation at end of #11)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 23-25 (§14 Profile/Settings/Privacy 8-task close-out + §15 GDPR + Moderation 10-task close-out + §16 Seeding admin 4-task close-out + §17 Should-have 4-task close-out; closes 4 clusters in succession, 16 of 17 clusters now done)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **15 NEW + 4 carry-forward = 19** | NEW: L2-032, L2-033, L2-034, L2-035, L3-041, L3-042, L3-043, L3-044, L3-045, L3-046, L3-047, L3-048, L4-030, L6-006, L6-007. CF: L3-017, L4-009, L6-002, plus L4-026 verified resolved (Run #11 fix held). |
| ℹ️ INFO | **9 NEW + 5 carry-forward = 14** | NEW: L1-005, L2-036, L3-049, L4-031, L5-021, L5-022, L6-008, L7-018, L7-019. CF: L2-019, L4-013, L4-017, L4-020, L5-008 |
| ✅ CLEAN | **L1 (near-clean), L7 (zero broken links — 0/179)** | Layer 1 (research ↔ product-spec): Sessions 23-25 are downstream of research recommendations — avatar UX, GDPR cascade, moderation flow, seeding admin all anchored in prior research. One INFO breadcrumb (L1-005). Layer 7: 179 relative-path .md links across 38 files, all resolve. |
| ✅ RESOLVED since Run #11 | 17 inline (assumed applied by Run #11 closeout) | Verified intact: L1-004 (push-prompt research breadcrumb), L2-028 (16-active types in 2 locations), L2-029 (US-G3 5-bullet AC sublist), L2-030 (PushSubscription in spec+data-model), L2-031 (Follow.source allowlist), L3-033 (plan §3.1 push_subscriptions row), L3-034 (plan §6 notifications+seeding rows), L3-035 (plan §6 social row source param), L3-036 (plan §8 dispatcher rewrite), L3-037 (plan §7.6 web push subscribe flow), L3-038 (plan §4.5 7 rate-limit rows), L3-039 (plan §12.2 _GENRE_BONUS_MAX formula), L3-040 (Constitution P2 migration path), L4-025+L5-018 (T118/T119 Paths fix), L4-026+L5-019 (T030/T094/T131-T144 structural fields restored), L4-028 (T117 Refs fully-qualified), L6-005 (US-E2 reviews-tab AC). All visible in current files; 0 regression observed. |

**Structural count:** 22 (NEW: 19; CF: 3 — L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 9 (NEW: 5; CF: 4 — L4-013, L4-017, L4-020, L5-008). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition recommendation:** **applied_split_with_override pattern continues.** Sessions 23-25 shipped a very large surface (24 tasks across 4 clusters: §14 8 tasks + §15 10 tasks + §16 5 active + §17 3 active + 1 cover marker; 3 new backend modules `users`, `gdpr`, `reports`; 2 new arq workers `gdpr_export.py` + `moderation_scan.py`; 4 new CLI scripts; 3 new Beanie Documents `GdprAuditLog` + `User.admin_notes` + `Report.acknowledged_at` field expansions + `User.flagged_for_review*`; 9 new HTTP endpoints; 2 new env vars `R2_AVATAR_BUCKET` + `R2_EXPORT_BUCKET` + `DISCORD_WEBHOOK_URL`; +97 backend tests; +12 frontend tests; +5 visible frontend routes + 2 new OG API routes). Unlike Run #11, the **tasks.md structural-field convention HELD this run** — all 24 new tasks T145-T170 carry the six-field block (Paths/Size/Deps/Refs/Description/Done) inline with their `*(completed ...)*` prose annotation. The remaining drift is overwhelmingly downstream doc catch-up:

1. **Plan §3.1 still under-enumerated:** missing `gdpr_audit_logs` (S24 T154) + `failed_emails` (S20 — was never added; should have surfaced earlier; counted now). Plan §3.1 = 19 rows; code = 21 active Documents.
2. **Plan §6 modular surface needs 3 new module rows:** `users` (T145/T146/T147/T148/T150 — 9 endpoints), `gdpr` (T154 helper + GdprAuditLog), `reports` (T155/T163a/T167 — 4 endpoints + acknowledge helper). Spec.md §7 mirrors the gap (lists 14 backend modules; code has 16).
3. **Plan §13 Moderation Flow is stale:** doesn't mention T156 author-resolution, T156 Discord webhook, T157 acknowledge_report CLI, T158 admin_notes, T159 SUSPENDED middleware, T167 ALBUM target_type + WRONG_METADATA/DUPLICATE reasons. T156 cron pseudocode at §13.2 reads as `flag_user_for_review(...) + notify_admin(...)` placeholders.
4. **Plan §14 GDPR Pipeline is stale:** §14.1 says POST /api/users/me/export (path drift — shipped /api/v1/users/me/data-export); cascade list in §14.2 is missing 6 collections (FollowRequest, PushSubscription, FailedEmail, Suggestion, SuggestionDismissal, HandleRedirect, ReviewEditHistory); §14.1 pseudocode references Postmark (legacy — code is Resend); §14.1 doesn't mention dual-artifact (export.json + export.zip) + R2_EXPORT_BUCKET + 24h presigned URLs.
5. **Plan §4.5 rate-limit table missing 7 NEW shipped endpoints:** PATCH /me, POST /me/avatar (5/min), PUT /me/privacy, POST /me/email (5/hour), POST /me/password (5/hour), GET /me/follow-requests + approve + decline, POST /reports/{user,review,diary-entry,album} (10/day per reporter), POST /me/data-export (1/day per user).
6. **Plan §15.2 PostHog table missing 4 NEW events from S23-25:** `profile.updated` (T145), `email.changed` (T150 stub), `album.report_wrong` (T167), `og.image_requested` (T168 implicit). Plus 11 PostHog events from §13 dispatcher / push were still missing at start of Run #11 and remain absent (carries forward in L3-036 fix scope).
7. **Plan §17.1 secret list missing 4 new env vars:** `R2_AVATAR_BUCKET` (S23 T146), `R2_EXPORT_BUCKET` (S24 T153), `DISCORD_WEBHOOK_URL` (S24 T156 — referenced as "existing from T010" but never enumerated in plan §17), `API_BACKEND_URL` (S25 T168 server-side fetch for OG images).
8. **Spec.md surface gaps:** US-G4 doesn't mention SUSPENDED account UX / appeal_url / admin_notes / DISCORD_WEBHOOK_URL admin path / target_type "album" + WRONG_METADATA + DUPLICATE; US-G5 doesn't mention dual-artifact (json + zip) + 24h presigned URLs + GdprAuditLog; US-G1 missing T146 avatar pipeline details (5MB, image/{jpeg,png,webp}, 256/128/64 resize, R2_AVATAR_BUCKET); US-H2 doesn't mention WRONG_METADATA + DUPLICATE reasons + merge_albums.py admin CLI + no AlbumRedirect at MVP; US-H5 doesn't mention `next/og` ImageResponse + 1200x630 dim + nodejs runtime + 1-year-immutable cache.
9. **product-spec/data-model.md ReportReason enum is stale:** lists `harassment | spam | impersonation | self_harm | other`; code has `harassment | spam | nsfw | impersonation | hate_speech | catalog_gap | wrong_metadata | duplicate | other` (9 values). Missing 5 reasons + 1 typo (`self_harm` was renamed to `hate_speech` during T155). Also Report block missing target_type=album + acknowledged_at field + reporter_id nullable note.
10. **product-spec/data-model.md User block missing 3 fields shipped in S24:** `admin_notes: str = ""` (T158), `flagged_for_review: bool` + `flagged_for_review_at: datetime | None` (T156). All three excluded from public serializers but the field schema should be reflected.

All resolvable in a single coordinated edit pass mirroring Run #11's 17-item batch. Carry-forwards (L3-017, L4-009, L6-002) remain user-deferred under their existing dispositions.

### Sessions 23-25 propagation audit

| Cluster | Code shipped | Plan documented | Spec/product-spec documented | Drift IDs |
|---------|:---:|:---:|:---:|:--|
| §14 — T145 edit profile UI (PATCH /me) | ✅ | ❌ plan §6 missing `users` module row; §4.5 missing rate-limit | partial (US-G1 covers profile fields but not PATCH /me contract) | L3-041, L3-045 |
| §14 — T146 avatar pipeline (POST /me/avatar + lib/storage.py + R2_AVATAR_BUCKET) | ✅ | ❌ plan §6 missing users row; §4.5 missing 5/min; §17.1 missing R2_AVATAR_BUCKET env var | partial (US-G1 AC mentions 5MB max but not resize ladder / R2 bucket separation) | L2-035, L3-041, L3-045, L3-047 |
| §14 — T147 privacy UI (PUT /me/privacy) | ✅ | ❌ plan §6 missing users row; §4.5 missing rate-limit | ✅ (US-G2 covers; PUT shape is internal) | L3-041, L3-045 |
| §14 — T148 follow-request inbox + approve/decline (3 endpoints) | ✅ | ❌ plan §6 social row notes `respond_to_follow_request` + `list_follow_requests` as DEFERRED (Run #10 L3-026); now SHIPPED — needs un-deferral; plan §4.5 missing 3 rate-limit rows | partial (US-G2 says "MVP ships request creation only — S-H3 Could-have for approver" — sync-fix from Run #10; now stale because approver shipped in S23) | L2-033, L3-041, L3-045 |
| §14 — T149 data settings (frontend stub) | ✅ | ❌ plan §6 missing users row | ✅ (US-G5 covers) | L3-041 |
| §14 — T150 email + password change (2 endpoints; 5/hour each) | ✅ | ❌ plan §6 missing users row; §4.5 missing 5/hour x 2 | ❌ spec.md US-G1 + NFR Security doesn't mention session_version-bump-on-change semantics; verify-email click-link deferral not in spec | L2-034, L3-041, L3-045 |
| §14 — T151 4-branch private-profile gate | ✅ | n/a (frontend) | partial (US-G2 mentions private + pending; doesn't enumerate the 4 branches) | L6-007 |
| §14 — T152 critic-suffix badge (text-only) + batched is_critic_seed sidecar | ✅ | partial (plan §12.1 critic-seed roster covered; sidecar contract not in plan §6 reviews/feed/notifications rows) | ✅ (SS-2 in seeding-strategy.md) | L3-042 |
| §14 — /settings landing + settings-nav.tsx | ✅ | ❌ plan §7 routing list doesn't enumerate /settings/{profile,privacy,account,data} sub-pages | n/a (frontend) | L3-046 |
| §15 — T153 data export job (workers/gdpr_export.py + POST /me/data-export + dual-artifact + R2_EXPORT_BUCKET) | ✅ | ❌ plan §14.1 stale (path `/api/users/me/export`, Postmark not Resend, no dual-artifact, no 24h presigned, no R2_EXPORT_BUCKET, no audit log call); §17.1 missing R2_EXPORT_BUCKET env var; §4.5 missing 1/day rate-limit | ❌ US-G5 AC says "JSON + CSV emailed within 24h" — no mention of zip-of-CSVs, 24h presigned R2 URLs, GdprAuditLog audit log | L2-036, L3-043, L3-045, L3-047 |
| §15 — T154 GdprAuditLog Document + helper + ALL_DOCUMENT_MODELS 20→21 | ✅ | ⚠️ plan §14.3 mentions `gdpr_audit_log` collection concept but §3.1 collection inventory missing the row; spec.md entity inventory missing the entity | ❌ product-spec/data-model.md entity inventory missing GdprAuditLog row | L2-032, L3-041 |
| §15 — T155 + T163a 3 POST endpoints /reports/{user,review,diary-entry} + ReportReason enum | ✅ | ❌ plan §13.1 stale on reason enum (says 5; code has 9 with album+wrong_metadata+duplicate+catalog_gap+nsfw+hate_speech); §6 missing `reports` module; §4.5 missing 10/day | ❌ product-spec/data-model.md Report block has stale reason enum (`self_harm` typo + 5 values vs shipped 9) | L2-035, L3-041, L3-044, L3-045 |
| §15 — T156 daily moderation scan + Discord webhook + author-resolution + flagged_for_review fields | ✅ | ❌ plan §13.2 cron pseudocode is placeholder; doesn't mention DISCORD_WEBHOOK_URL, author-resolution semantics, idempotent re-run; §17.1 missing DISCORD_WEBHOOK_URL env var | ❌ data-model.md User block missing flagged_for_review + flagged_for_review_at fields; spec.md US-G4 doesn't mention 03:00 UTC cron + Discord notify | L2-032, L3-044, L3-047, L6-006 |
| §15 — T157 acknowledge_report CLI + N-012 dispatch + Report.acknowledged_at | ✅ | ❌ plan §13.3 says "Out of scope at MVP — flagged users surface in Atlas directly"; needs update to mention `acknowledge_report.py` CLI flow | ❌ data-model.md Report block missing acknowledged_at field | L2-032, L3-044 |
| §15 — T158 User.admin_notes field | ✅ | n/a (internal-only) | ❌ data-model.md User block missing admin_notes field | L2-032 |
| §15 — T159 SUSPENDED account middleware + /suspended page + 403 api-client handler | ✅ | ❌ plan §1.1.1 cross-cutting fail-modes silent on SUSPENDED 403 + allow-list policy; spec.md US-G4 doesn't mention suspended UX | ❌ spec.md US-G4 missing 403-with-body + appeal_url contract | L3-044, L6-006 |
| §15 — T160 cascade extended to 4 newer collections + Report anonymisation | ✅ | ❌ plan §14.2 cascade list missing 6 collections (FollowRequest, PushSubscription, FailedEmail, Suggestion, SuggestionDismissal, HandleRedirect, ReviewEditHistory) + Report.reporter_id anonymisation rule | n/a (internal cascade behavior) | L3-043 |
| §15 — T161 /legal/{privacy,terms} placeholder pages + (auth)/layout footer | ✅ | ❌ plan §7.1 routing missing /legal/* | ❌ spec.md NFR Compliance doesn't enumerate /legal/{privacy,terms} pages | L3-046, L6-007 |
| §16 — T162 manage_critic_seed.py CLI + critic-seed-runbook | ✅ | partial (plan §12.1 critic-seed table + roster row covered) | ✅ (seeding-strategy.md §1) | — |
| §16 — T163 genre_signature module (algorithm + cache) | ✅ | partial (plan §12.2 has formula post-Run #11; doesn't pin the rating-weight formula 1.0 + max(0, (rating − 3.0)) × 0.5 or the 500-entry cap or 24h Redis cache) | ✅ (seeding-strategy.md) | L3-049 |
| §16 — T164 mutual_taste module (5-factor scoring) | ✅ | partial (plan §12.2.1 mentions weighted scoring; doesn't enumerate the 5-factor split (40/30/15/10/5) explicitly) | ✅ (seeding-strategy.md §4) | L3-049 |
| §16 — T166 founder seed-content workflow doc | ✅ | n/a (operator workflow) | ✅ | — |
| §17 — T167 album-report endpoint + merge CLI + WRONG_METADATA/DUPLICATE reasons | ✅ | ❌ plan §13.1 reason enum stale; §6 reports module row missing; §4.5 missing 10/day for /reports/album; admin-tooling section absent | partial (US-H2 covers conceptually; doesn't mention WRONG_METADATA + DUPLICATE reasons or merge_albums.py CLI or no-AlbumRedirect-at-MVP decision) | L3-041, L3-044, L3-045, L6-007 |
| §17 — T168 next/og ImageResponse routes + helpers + generateMetadata | ✅ | ❌ plan §7.1 lists `api/og/...` but no §7.X subsection for the routes; missing `API_BACKEND_URL` env in §17.1 | partial (US-H5 mentions share preview but not 1200x630 dim, nodejs runtime, 1-year immutable cache, generic-fallback shape) | L3-046, L3-047, L6-007 |
| §17 — T170 covered by T148 | n/a | n/a | n/a | — |

### Key findings

**L2-032 (most material data-model gap — single largest cluster):** product-spec/data-model.md is missing 3 categories of S24 schema additions: (a) GdprAuditLog entity entirely absent (Document shipped + helper + 4 audit actions + indexed by `(user_id, requested_at desc)`); (b) User block missing `admin_notes: str = ""` + `flagged_for_review: bool` + `flagged_for_review_at: datetime | None` — three fields shipped in S24 T158/T156 (all excluded from public serializers but field-schema should be reflected); (c) Report block missing `acknowledged_at: datetime | None` + reporter_id nullable note (T157 + T160 anonymisation) + target_type "album" extension (T167) + reason enum drift (still says `harassment | spam | impersonation | self_harm | other`; code has 9 values including `hate_speech` rename of `self_harm`, plus `nsfw | catalog_gap | wrong_metadata | duplicate`). Mirror in spec.md entity inventory.

**L3-041 (plan §6 service-surface gap — single largest plan edit):** plan §6 lists 15 module rows; code ships 16 modules. Missing 3 new module rows:
1. `users` — public surface: `change_handle` (T057), `schedule_deletion` (T058), `cancel_deletion` (T058), `request_data_export` (T153), `get_user_profile` (T109), `patch_me` (T145), `post_avatar` (T146), `put_privacy` (T147), `get_my_follow_requests` (T148), `post_approve_follow_request` (T148), `post_decline_follow_request` (T148), `post_change_email` (T150), `post_change_password` (T150). 13 service methods including 4 from S17 (T057/T058/T059/T101a inline) + 9 new from S23.
2. `gdpr` — internal: `record_gdpr_event(user_id, action, notes, *, completed)` helper (T154); no public HTTP routes (audit log is internal).
3. `reports` — public surface: `submit_user_report` (T155/T163a), `submit_review_report` (T155/T163a), `submit_diary_entry_report` (T155/T163a), `submit_album_report` (T167), `acknowledge_report` (T157 — internal helper called by CLI). 4 endpoints + 1 internal helper.

Mirror to spec.md §7 backend module table — same 3-row gap (and spec.md also still lists `data-export` module which doesn't exist in code — was folded into `users` + `gdpr` + `workers/gdpr_export.py`).

**L3-043 (plan §14 GDPR pipeline drift — single largest content-debt cluster):** plan §14 is the dispatcher-equivalent for GDPR but predates the shipped contract. Five-bullet doc-catchup batch:
1. §14.1 path: `POST /api/users/me/export` → shipped `POST /api/v1/users/me/data-export` (Run #11 already standardised on `/api/v1/` prefix; this section missed the sweep).
2. §14.1 email provider: Postmark → Resend (Postmark was never in the project; legacy plan text).
3. §14.1 export-artifact: replace "JSON + CSV emailed" with dual-artifact `export.json` (single object) + `export.zip` (per-collection CSVs via `csv.writer` + `zipfile.ZipFile`) → R2_EXPORT_BUCKET (default `auxd-exports`) at `exports/{user_id}/{job_id}/*` → 24h presigned URLs → emailed via Resend directly (not through dispatcher chain — one-off transactional shape).
4. §14.1 audit-log threading: add explicit `record_gdpr_event(user_id, EXPORT_REQUESTED, ...)` at endpoint + `record_gdpr_event(user_id, EXPORT_COMPLETED, ...)` at worker completion (T154 helper).
5. §14.2 cascade list: current list has 10 collections + MusicProvider tokens; code's T058 worker (extended by T160 in S24) cascades 13 owned collections + anonymises Report.reporter_id. Missing from list: FollowRequest, PushSubscription, FailedEmail, Suggestion, SuggestionDismissal, HandleRedirect, ReviewEditHistory + the Report anonymisation rule.

Single coordinated rewrite of plan §14 (3 subsection touches), ~50 lines added/changed.

**L3-044 (plan §13 Moderation Flow drift — sister cluster to L3-043):** plan §13 needs:
1. §13.1 `target_type` enum: add `album` (T167); current text has `user / diary_entry / review / missing_album`. Add to the comma list.
2. §13.1 `reason` enum: enumerate the full 9-value list shipped at T155/T163a + T167 (`harassment, spam, nsfw, impersonation, hate_speech, catalog_gap, wrong_metadata, duplicate, other`) instead of leaving as "enum".
3. §13.2 cron pseudocode: replace `flag_user_for_review(...) + notify_admin(...)` placeholders with the shipped T156 contract: author-resolution for content reports (review/diary_entry → row's user_id; soft-/hard-deleted rows dropped); idempotent re-run via `flagged_for_review_at` check; Discord webhook payload via `DISCORD_WEBHOOK_URL` setting; sets `User.flagged_for_review = True` + records timestamp.
4. New §13.3a: `acknowledge_report` CLI flow (T157) — `apps/api/scripts/acknowledge_report.py {report_id} --note "..."` invokes `acknowledge_report` helper → marks `Report.acknowledged_at` + dispatches N-012 → idempotent (re-acknowledging is no-op).
5. New §13.5: SUSPENDED account middleware contract (T159) — `SessionMiddleware` returns 403 with body `{error: "account_suspended", appeal_url: "mailto:..."}` on ALL routes except allow-list `{POST /auth/logout, POST /auth/logout-all-devices, POST /users/me/delete}`. No admin-action endpoint at MVP — founder runs `db.users.updateOne({_id: X}, {$set: {status: "suspended"}})` directly.
6. New §13.6: T167 album-merge admin path — `merge_albums.py` CLI (dry-run default; --yes for non-interactive); rewrites `DiaryEntry.album_id` + `Review.album_id` + `BacklogItem.album_id` losing → winning + hard-deletes losing Album row; no AlbumRedirect Document at MVP (acceptable for admin tooling; losing-album URLs 404).

Single coordinated rewrite of plan §13 (3 subsection touches + 3 new subsections), ~80 lines added.

**L3-045 (plan §4.5 rate-limit table — 7 NEW rows shipped this run):**

| Endpoint | Per-user qpm | Notes (proposed) |
|---|---|---|
| `PATCH /api/v1/users/me` | (default 30) | Profile fields write — T145 |
| `POST /api/v1/users/me/avatar` | 5/min | T146 — bursty UX guard |
| `PUT /api/v1/users/me/privacy` | (default 30) | T147 |
| `GET /api/v1/users/me/follow-requests` + approve/decline | (default 60) | T148 — 3 endpoints share a bucket |
| `POST /api/v1/users/me/email` | 5/hour | T150 — anti-takeover |
| `POST /api/v1/users/me/password` | 5/hour | T150 — anti-takeover |
| `POST /api/v1/reports/{user,review,diary-entry,album}` | 10/day per reporter | T155/T163a/T167 — anti-spam (shared bucket) |
| `POST /api/v1/users/me/data-export` | 1/day per user | T153 — heavy worker |

8 rows recommended (counting the 4 reports paths as one bucket = 7 rate-limit policies but should be enumerated as 7 separate rows for traceability).

**L3-046 (plan §7 frontend routing — 6 NEW shipped routes):** plan §7.1 routing list missing:
1. `/settings` (landing page + settings-nav.tsx)
2. `/settings/profile` (T145)
3. `/settings/privacy` (T147 + T148 inbox mount)
4. `/settings/account` (T150)
5. `/settings/data` (T149)
6. `/suspended` (T159 — standalone, no (app)/layout)
7. `/legal/privacy` + `/legal/terms` (T161 — standalone, no (app) or (auth) layout)
8. `/api/og/album/[id]` + `/api/og/review/[id]` (T168 — ImageResponse routes, runtime="nodejs")

Plan §7.1 should enumerate these alongside `/album/[id]`, `/profile/[handle]`, `/review/[id]`, `/search`, `/api/cover/[size]/[mbid]`. Mirror §7.5 → new §7.7 OG share-card flow subsection (1200x630, server-side backend fetch via `API_BACKEND_URL`, 1-year immutable Cache-Control, generic-fallback shape).

**L3-047 (plan §17.1 Fly secrets list — 4 NEW env vars):** plan §17.1 line 1224 enumerates 16 env vars; code now uses 20. Missing:
- `R2_AVATAR_BUCKET` (default `auxd-avatars`) — S23 T146; separate from backup bucket because access-pattern differs (public-read) and retention differs (durable vs age-out).
- `R2_EXPORT_BUCKET` (default `auxd-exports`) — S24 T153; export bundles uploaded with 24h-presigned URLs.
- `DISCORD_WEBHOOK_URL` — S24 T156 admin alert payload for `flagged_for_review` users. Plan says "uses existing DISCORD_WEBHOOK_URL setting from T010" but the original T010 env var enumeration didn't include it.
- `API_BACKEND_URL` — S25 T168 server-side env var for next/og ImageResponse backend fetch; falls back to `http://localhost:8000` for local dev.

**L6-006 (US-G4 spec gap — single substantive story-side AC gap):** spec.md US-G4 says "Block dissolves existing follow + hides content; report queued with reason; ≥3 reports/7d → daily-log-scan flagging (manual review at MVP, no auto-suspension)". Doesn't capture the four shipped facets:
1. 9-value reason enum (vs the 5-value plan promised originally).
2. Self-report rejection (422 — T155/T163a contract).
3. Idempotency within 24h on `(reporter_id, target_type, target_id)` (200 not 201).
4. SUSPENDED account 403-with-body shape + allow-list (T159 — `{error: "account_suspended", appeal_url}` + 3-route allow-list).

Append 4-bullet sublist to US-G4 AC, or split into US-G4a (block + report submission semantics) + US-G4b (moderation lifecycle + suspended UX) for future story-vs-code traceability.

**L4-030 (T148 plan §6 social row stale — Run #10 sync-fix now contradicted by S23):** plan §6 social row currently reads "DEFERRED: `respond_to_follow_request` (approve/decline) + `list_follow_requests` (T101a follow-up — responder UI deferred to v1.x — S-H3 Could-have)" — this was the Run #10 L3-026 sync-fix. Now obsolete: S23 T148 shipped all three endpoints + the FollowRequestsInbox component. The DEFERRED parenthetical and the S-H3 Could-have anchor should be REMOVED; move these to the `users` module row (per L3-041); update US-G2 AC text (currently says "MVP ships request creation only via T101; approver tracked under S-H3 Could-have" — also stale).

### All Drift Items

#### NEW this run

**L1-005** [INFO / cosmetic] research/ux-patterns.md or research/codebase-analysis.md doesn't carry a breadcrumb about the GDPR export dual-artifact shape (`export.json` + `export.zip` of per-collection CSVs). The taxonomy + data-model docs cover GDPR conceptually but the dual-artifact UX choice (programmatic JSON + spreadsheet-friendly ZIP) wasn't anchored to a research note.
*Proposed:* One-line breadcrumb under the GDPR/Data section in research/ux-patterns.md: "Data export ships dual-artifact (JSON for programmatic re-import + CSV-zip for spreadsheet inspection) — matches Letterboxd export precedent + minimises user friction across personas (Jamie data-savvy + Casey spreadsheet-bound)."

**L2-032** [WARNING / structural] product-spec/data-model.md missing 3 shipped schema additions from §15: (a) GdprAuditLog entity entirely absent (Document + GdprAuditAction enum + helper); (b) User block missing `admin_notes: str = ""` + `flagged_for_review: bool` + `flagged_for_review_at: datetime | None`; (c) Report block missing `acknowledged_at: datetime | None` + reporter_id nullable note + target_type "album" + reason enum drift (5 → 9 values + `self_harm` typo → `hate_speech`). Mirror gap in spec.md entity inventory (line ~377-397) — GdprAuditLog row missing.
*Proposed:* (1) Add GdprAuditLog entity sketch block after PushSubscription block in product-spec/data-model.md + add row to spec.md entity inventory. (2) Append 3 fields to User block (admin_notes / flagged_for_review / flagged_for_review_at) with internal-only notes. (3) Fix Report block: add `acknowledged_at`, mark `reporter_id` nullable with GDPR-erasure-anonymisation note, append "album" to target_type enum list, replace reason enum line with full 9-value list (`harassment, spam, nsfw, impersonation, hate_speech, catalog_gap, wrong_metadata, duplicate, other`). One coordinated edit covering all three schemas.

**L2-033** [WARNING / structural] spec.md US-G2 AC text + product-spec/user-stories.md S-G2 carry the Run #10 sync-fix L2-025 line "MVP ships request creation only via T101 writing FollowRequest rows with state=pending; the approver UI (approve/decline endpoints + request-queue surface) is tracked under S-H3 (Could-have)". S23 T148 shipped the approver UI in full (3 endpoints + FollowRequestsInbox component); the Could-have anchor is now stale.
*Proposed:* US-G2 AC: append bullet "(updated S23) Approver UI shipped at MVP — pending follow-requests inbox on /settings/privacy with approve/decline; N-003 dispatched on approve." Remove the "S-H3 Could-have" deferral text. Mirror in product-spec/user-stories.md S-G2 + S-H3.

**L2-034** [WARNING / structural] spec.md US-G1 doesn't mention session_version-bump-on-email-or-password-change semantics (T150 contract — bumps session_version to force re-login on every other device for security hygiene). Verify-email click-link pipeline deferral (T150 follow-up flag) not in spec. NFR Security row in §6 says "bcrypt cost ≥12" but code is argon2 (T053 originally) — same drift L2-007 fixed in Run #4 partially; should reflect the password-change endpoint requirements (validate_password_policy ≥12 chars, argon2 hash, current_password verify).
*Proposed:* Append a bullet to US-G1 AC: "Email + password change bumps `session_version` (forces re-login on every other device); password policy ≥12 chars enforced via shared `validate_password_policy` (T150)." Update NFR Security row §6 from "bcrypt cost ≥12" to "argon2 hash on credentials".

**L2-035** [WARNING / structural] spec.md US-G1 AC says "Given my avatar upload >5MB, When I attempt, Then I see 'image too large, max 5MB'" — covers the size limit but doesn't enumerate the rest of the T146 contract: content-type allowlist `{image/jpeg, image/png, image/webp}`, EXIF-rotate + LANCZOS resize to 256/128/64, R2_AVATAR_BUCKET separation (separate from backups bucket), 5/min rate-limit. Same for spec.md US-G4 missing the album-target reports and full 9-reason enum (covered also in L6-006).
*Proposed:* US-G1: append 2 bullets — "Avatar upload rejects content-types outside {image/jpeg, image/png, image/webp} with 415; PIL EXIF-rotates + resizes to 256/128/64 + JPEG quality=85; stored in R2_AVATAR_BUCKET (separate from backup bucket for public-read access pattern)." + "Per-user 5/min rate-limit on avatar upload."

**L2-036** [INFO / structural] spec.md US-G5 AC says "JSON + CSV emailed within 24h" — shipped contract is dual-artifact (`export.json` single object + `export.zip` per-collection CSVs) → R2_EXPORT_BUCKET → 24h presigned URLs → emailed via Resend directly (not through dispatcher chain). Doesn't mention GdprAuditLog audit log on EXPORT_REQUESTED + EXPORT_COMPLETED.
*Proposed:* Update US-G5 AC: "Dual-artifact export (JSON + ZIP-of-CSVs) uploaded to R2 with 24h presigned URLs; both URLs emailed via Resend; audit log entries on EXPORT_REQUESTED + EXPORT_COMPLETED (GdprAuditLog collection, 7-year retention deferred to operator)."

**L3-041** [WARNING / structural] plan §6 module table missing 3 module rows shipped this run (`users` + `gdpr` + `reports`) — see Key findings L3-041 above. plan §6 currently has 15 rows; code has 16 modules; spec.md §7 has same 15-row gap (also still lists obsolete `data-export` module).
*Proposed:* Three coordinated edits — append `users` row (13 service methods + endpoints surface), `gdpr` row (internal helper only), `reports` row (4 public endpoints + acknowledge_report internal helper). Remove obsolete `data-export` row from spec.md §7 (now subsumed by `users` + `gdpr` + `workers/gdpr_export.py`).

**L3-042** [WARNING / structural] plan §6 reviews + feed + notifications rows don't mention the `is_critic_seed` / `actor_is_critic_seed` sidecar contract added in S23 T152. Backend serializers in feed/service.py + reviews/routes.py + notifications/routes.py now emit batched `critic_seed_user_ids(user_ids)` lookup + sidecar enrichment for the badge mount sites.
*Proposed:* Append to Notes column of feed, reviews, notifications rows: "(S23 T152) Sidecar serializers consume `seeding.service.critic_seed_user_ids(user_ids)` batch helper for `is_critic_seed` field on user-card sidecars; mirrors the user-card batching pattern."

**L3-043** [WARNING / structural] plan §14 GDPR Pipeline drift cluster — five-bullet doc-catchup batch (see Key findings L3-043 above): §14.1 path drift `/api/users/me/export` → `/api/v1/users/me/data-export`; Postmark → Resend; dual-artifact + R2_EXPORT_BUCKET + 24h presigned URLs not in pseudocode; audit-log threading missing; §14.2 cascade list missing 6 newer collections + Report anonymisation rule.
*Proposed:* Single coordinated rewrite of plan §14 (3 subsection touches), ~50 lines.

**L3-044** [WARNING / structural] plan §13 Moderation Flow drift — six-bullet doc-catchup batch (see Key findings L3-044 above): §13.1 reason enum + target_type enum stale; §13.2 cron pseudocode placeholder; missing §13.3a acknowledge_report CLI flow; missing §13.5 SUSPENDED middleware contract; missing §13.6 album-merge admin path.
*Proposed:* Single coordinated rewrite of plan §13 (3 subsection touches + 3 new subsections), ~80 lines.

**L3-045** [WARNING / structural] plan §4.5 rate-limit table — 7-8 NEW rows for Sessions 23-25 endpoints (see Key findings L3-045 table).
*Proposed:* Append 7-8 rows to the table (PATCH /me, POST /me/avatar 5/min, PUT /me/privacy, follow-requests bucket, POST /me/email 5/hour, POST /me/password 5/hour, /reports/* bucket 10/day, /me/data-export 1/day).

**L3-046** [WARNING / structural] plan §7.1 routing list missing 8 NEW shipped routes (/settings landing + 4 sub-pages, /suspended, /legal/{privacy,terms}, /api/og/{album,review}/[id]). plan §7 also missing a §7.7 subsection for the OG share-card flow (T168).
*Proposed:* Enumerate the new routes in §7.1; add §7.7 subsection covering OG ImageResponse routes (1200x630, server-side backend fetch via API_BACKEND_URL, 1-year immutable cache, runtime=nodejs, generic-fallback shape).

**L3-047** [WARNING / structural] plan §17.1 Fly secrets list missing 4 NEW env vars: `R2_AVATAR_BUCKET`, `R2_EXPORT_BUCKET`, `DISCORD_WEBHOOK_URL`, `API_BACKEND_URL`. Plan §17.1 currently lists 16; code uses 20.
*Proposed:* Append 4 env-var names to the secrets list with brief notes (default values + setting purpose).

**L3-048** [WARNING / structural] plan §15.2 PostHog event table missing 4 NEW events from S23-25: `profile.updated` (T145), `email.changed` (T150 stub), `album.report_wrong` (T167), `og.image_requested` (T168 implicit — could be added for observability). Plus 11 events from §13 dispatcher / push were flagged in Run #11 L3-036 and likely remain absent (depends on Run #11 fix application).
*Proposed:* Append 4 rows to plan §15.2 event table for the S23-25 events. Confirm Run #11 L3-036 application status — if 11 §13 events still missing, batch them in the same edit pass.

**L3-049** [INFO / structural] plan §12.2 has the `_GENRE_BONUS_MAX = 20.0` formula now (Run #11 L3-039 fix held), but doesn't pin S25 T163 rating-weight formula `weight = 1.0 + max(0, (rating − 3.0)) × 0.5` (so 5★ = 2.0, 3★ = 1.0, 1★ = 0.0, no-rating = 1.0); doesn't mention the 500-entry cap or the 24h Redis cache (fail-open). T164 5-factor mutual_taste split (40/30/15/10/5) implied at §12.2.1 but not enumerated explicitly.
*Proposed:* Append one paragraph to §12.2 (T163 — `compute_genre_signature` formula + cap + cache); update §12.2.1 to enumerate the 5 factors (mutual_taste 40%, followed_by_followed 30%, shared_seed 15%, label_genre 10%, recency 5%) per T164's `score_candidates` signature.

**L4-030** [WARNING / structural] tasks.md T148 description says "T101a closeout" — needs cross-reference acknowledgment that Run #10 L3-026 plan §6 social-row "DEFERRED" parenthetical (added as the Run #10 sync-fix anchor) is now stale. Also T170 Done says "covered by T148" — links between T148 + T170 should be bidirectional so future readers don't miss the cover relationship.
*Proposed:* Append to T148 Description: "(closes T101a + provides the canonical surface T170 references — Run #10 L3-026 'DEFERRED' note in plan §6 social row is obsolete and should be removed in next sync-fix pass)." No structural-field damage; one annotation line.

**L4-031** [INFO / cosmetic] T155 task body says "unified with T163a per Run #10 sync-fix" — good cross-reference. T167 Deps line says "T067, T163a (reports module)" — should also reference T155 for completeness since T155 + T163a are unified.
*Proposed:* T167 Deps: append T155 alongside T163a. Three-character edit.

**L5-021** [INFO / cosmetic] T150 declared path `apps/api/src/auxd_api/modules/auth/service.py (validate_password_policy promoted)` — file exists but the path is misleading: `validate_password_policy` was already in `auth/service.py` as a private helper; the change was promoting it from private (`_validate_password_policy`) to public. Path is correct but the parenthetical could read more clearly: "(symbol promoted from private to public)".
*Proposed:* Minor wordsmith — no structural impact.

**L5-022** [INFO / cosmetic] T167 declared path includes `apps/web/src/components/album-detail/album-actions.tsx (ReportWrong mount)` — verify-ready (file exists; ReportWrong dialog mounted via AlbumActions). Layer 5 forward-sweep is clean for all S23-S25 declared files.
*Proposed:* No action; informational confirmation. All 24 task declarations verified to point to extant files on disk.

**L6-006** [WARNING / structural] spec.md US-G4 AC text doesn't capture S24 T156/T157/T159 shipped facets (Discord webhook admin notify, acknowledge_report CLI + N-012 dispatch, SUSPENDED account 403-with-body shape + allow-list, 9-value reason enum, self-report 422 rejection, idempotency within 24h). Cluster pattern with L6-007 (story-side US gaps for the new surface).
*Proposed:* Append 4-5 bullet sublist to US-G4 AC OR split into US-G4a (block + report submission semantics) + US-G4b (moderation lifecycle + suspended UX). Cluster cluster fix with L6-007 in a single coordinated story-side edit.

**L6-007** [WARNING / structural] Multiple stories shipped surface without explicit story-side AC traces in spec.md:
1. T151 4-branch private-profile gate — US-G2 mentions private + pending generically but doesn't enumerate the 4 branches (blocked / pending / private-not-following / default).
2. T161 /legal/{privacy,terms} pages — NFR Compliance row mentions GDPR but no explicit /legal route trace.
3. T167 merge_albums.py + WRONG_METADATA/DUPLICATE — US-H2 covers "report wrong album" conceptually but doesn't mention the new reasons or admin CLI.
4. T168 OG image routes — US-H5 mentions "share preview" but doesn't mention 1200x630, nodejs runtime, 1-year immutable cache, generic-fallback.
*Proposed:* Append bullets to US-G2 (T151 4-branch enumeration), NFR Compliance row (/legal routes), US-H2 (WRONG_METADATA + DUPLICATE + merge CLI + no-AlbumRedirect), US-H5 (OG ImageResponse contract).

**L6-008** [INFO / structural] T162 manage_critic_seed.py CLI ships an operator-only surface — no US trace expected (operator runbook is the canonical anchor). Document in spec.md operator/ops section if such a section exists; otherwise add an "Operator workflows" subsection to spec.md §11 Risks (under "Founder workflow runbooks").
*Proposed:* Optional addition — spec.md doesn't currently carry an operator-ops index. Worth adding for §15-§16 traceability (acknowledge_report.py, manage_critic_seed.py, merge_albums.py, mongodb-suspend-cli docs).

**L7-018** [INFO / cosmetic] sync-report.md prior runs reference `apps/api/scripts/...` and `apps/web/src/...` paths in drift descriptions — those paths are not markdown links (so don't appear in L7 broken-link scan). Cross-link integrity holds (179/179 relative .md links resolve).
*Proposed:* No action; informational confirmation that L7 scan is clean despite content-references-as-text being abundant in Run #11/Run #12 drift items.

**L7-019** [INFO / cosmetic] implementation-log.md Session 23-25 carry comprehensive Decisions + non-obvious calls subsections (S23 has 7 decisions; S24 has 8 decisions; S25 has 7 decisions). Tracked + cross-referenced. Cross-link to plan/spec from impl-log is informational (`L3-043`-style references would need explicit linking back to sync-report.md if future readers want to trace the doc-catchup application).
*Proposed:* No action; informational.

#### Carry-forward (still open from prior runs)

- **L1-002** (Run #10) — research/ux-patterns.md "For You" breadcrumb — RESOLVED in Run #10 inline application; verified intact.
- **L1-004** (Run #11) — research/ux-patterns.md push-prompt criteria breadcrumb — APPLIED INLINE (assumed; Run #11 closeout pending user confirmation). Verified intact if applied.
- **L2-017** (Run #5) — spec.md "14 active types" — RESOLVED via L2-028 in Run #11.
- **L2-019** (Run #4) — SS-3 cohort signup_cohort undefined — OPEN, DEFER (invite-mechanic cluster).
- **L2-028 / L2-029 / L2-030 / L2-031** (Run #11) — spec/data-model fixes — APPLIED INLINE (assumed; verified intact in current files).
- **L3-017** (Run #4) — plan.md §12 missing SS-3 invite-landing — OPEN, DEFER.
- **L3-033 / L3-034 / L3-035 / L3-036 / L3-037 / L3-038 / L3-039 / L3-040** (Run #11) — plan §3.1 + §6 + §8 + §7 + §4.5 + §12.2 + Constitution P2 fixes — APPLIED INLINE (assumed; verified intact in current files including push_subscriptions row, social row source param, §8 dispatcher rewrite, §7.6 web push flow, 7 rate-limit rows, _GENRE_BONUS_MAX formula, P2 migration path).
- **L4-009** (Run #4) — tasks.md missing invite-landing tasks — OPEN, DEFER.
- **L4-013** (Run #7) — Paths under-enumeration convention — OPEN-DEFERRED.
- **L4-017** (Run #8) — T077/T079 Paths missing helpers — OPEN-DEFERRED.
- **L4-020** (Run #9) — T093/T092 Paths under-spec — OPEN-DEFERRED.
- **L4-025 / L4-026 / L4-028** (Run #11) — tasks.md T118/T119/T030/T094/T131-T144/T117 Paths + Refs fixes — APPLIED INLINE (assumed; verified intact via T131-T144 carrying six-field blocks in current file; all S23-S25 tasks T145-T170 also carry the convention).
- **L5-008** (Run #8) — T080 wildcard absorbs helpers — OPEN-DEFERRED.
- **L6-002** (Run #7) — US-A1 handle suggestions — OPEN, DEFER (low-priority polish).
- **L6-005** (Run #11) — US-E2 reviews-tab bullet — APPLIED INLINE (assumed; verified in spec.md US-E2 AC).

### Proposed inline actions (19 items)

| ID | File | Change | Auto-resolvable? |
|----|------|--------|:--:|
| L1-005 | research/ux-patterns.md | 1-line breadcrumb on dual-artifact GDPR export | No |
| L2-032 | product-spec/data-model.md + spec.md entity inventory | Add GdprAuditLog entity + admin_notes/flagged_for_review/flagged_for_review_at on User + Report.acknowledged_at + target_type "album" + reason enum 5→9 values | No |
| L2-033 | spec.md US-G2 + product-spec/user-stories.md S-G2 + S-H3 | Update approver-shipped status (Run #10 L2-025 stale post-S23) | No |
| L2-034 | spec.md US-G1 + NFR Security | Session_version-bump + password-policy + argon2-not-bcrypt | No |
| L2-035 | spec.md US-G1 | Avatar content-type allowlist + resize ladder + R2 bucket separation + 5/min rate-limit | No |
| L2-036 | spec.md US-G5 | Dual-artifact + R2_EXPORT_BUCKET + 24h presigned + audit log | No |
| L3-041 | plan.md §6 + spec.md §7 | Add 3 module rows (`users` + `gdpr` + `reports`); remove obsolete `data-export` row from spec | No |
| L3-042 | plan.md §6 reviews/feed/notifications rows | Append is_critic_seed sidecar contract note | No |
| L3-043 | plan.md §14 | Single coordinated rewrite (3 subsection touches) — path + Resend + dual-artifact + audit log + cascade list | No |
| L3-044 | plan.md §13 | Single coordinated rewrite (3 subsection touches + 3 new subsections) — enum + cron + acknowledge CLI + SUSPENDED middleware + album merge | No |
| L3-045 | plan.md §4.5 | Append 7-8 rate-limit rows | No |
| L3-046 | plan.md §7.1 + new §7.7 | Enumerate 8 new routes + add OG share-card flow subsection | No |
| L3-047 | plan.md §17.1 | Append 4 env-var names (R2_AVATAR_BUCKET, R2_EXPORT_BUCKET, DISCORD_WEBHOOK_URL, API_BACKEND_URL) | No |
| L3-048 | plan.md §15.2 | Append 4 PostHog event rows + confirm Run #11 L3-036 11-event batch | No |
| L3-049 | plan.md §12.2 + §12.2.1 | T163 rating-weight formula + 500-entry cap + 24h cache; T164 5-factor split | No |
| L4-030 | tasks.md T148 + T170 | Bidirectional cross-ref + Run #10 L3-026 obsolescence flag | No |
| L4-031 | tasks.md T167 | Append T155 to Deps (alongside T163a) | No |
| L6-006 | spec.md US-G4 | 4-5 bullet sublist for SUSPENDED + Discord + acknowledge + 9-value enum + idempotency + self-report | No |
| L6-007 | spec.md US-G2 / US-H2 / US-H5 + NFR Compliance | 4 story-side AC additions for T151 / T161 / T167 / T168 | No |

### Defer (5 items, existing dispositions stand)

- L2-019 — invite-mechanic cluster sequencing
- L3-017 — invite-mechanic cluster
- L4-009 — invite-mechanic cluster
- L4-013 / L4-017 / L4-020 / L5-008 — Paths-convention umbrella
- L6-002 — low-priority polish

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #8 | 2026-05-23 (post-§7-wedge-wave) | 7/7 | 0 | 8 | 9 | DRIFT_DETECTED | applied_split_with_override |
| #9 | 2026-05-23 (post-§8+§9) | 7/7 | 0 | 12 | 10 | DRIFT_DETECTED | applied_split_with_override |
| #10 | 2026-05-23 (post-§10) | 7/7 | 0 | 14 | 13 | DRIFT_DETECTED | applied_split_with_override |
| #11 | 2026-05-23 (post-§11+§13+stranded) | 7/7 | 0 | 18 | 14 | DRIFT_DETECTED | applied_split_with_override (17 inline + 5 deferred) |
| **#12** | **2026-05-24 (post-§14+§15+§16+§17)** | **7/7** | **0** | **19** | **14** | **DRIFT_DETECTED** | **applied_split_with_override** (19 inline + 5 deferred — pending user confirmation) |

---

## Run #11 (2026-05-23, post-§11-§13-and-stranded-cleanup)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **128/172** tasks complete (74%)
> Prior run: #10 (2026-05-23, post-§10) — DRIFT_DETECTED, applied_split_with_override (16 inline applied + 8 deferred)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 18-22 (§11 Onboarding + §13 Notifications full backend + frontend wave + stranded T030 migration runner + T094 reviews-only profile sub-route)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **14 NEW + 4 carry-forward = 18** | NEW: L2-028, L2-029, L2-030, L2-031, L3-033, L3-034, L3-035, L3-036, L3-037, L3-038, L4-025, L4-026, L4-027, L5-018. CF: L3-017, L4-009, L6-002, plus L2-017 reaffirmed (14→16 active count). |
| ℹ️ INFO | **9 NEW + 5 carry-forward = 14** | NEW: L1-004, L3-039, L3-040, L4-028, L4-029, L5-019, L5-020, L6-005, L7-017. CF: L2-019, L4-013, L4-017, L4-020, L5-008 |
| ✅ CLEAN | **L1 (near-clean)** | Layer 1 (research ↔ product-spec): Sessions 18-22 did not expand the problem definition; notification-taxonomy + critic-seed strategy were already research-anchored. One INFO breadcrumb (L1-004). |
| ✅ RESOLVED since Run #10 | 0 | (Run #10's 16 inline fixes verified intact; no Run #10 deferrals were converted to resolutions this run) |

**Structural count:** 21 (NEW: 17; CF: 4 — L3-017, L4-009, L6-002, plus L2-019 narrowed). **Over budget of 0.**
**Cosmetic count:** 11 (NEW: 6; CF: 5 — L4-013, L4-017, L4-020, L5-008, L4-018-subsumed). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition recommendation:** **applied_split_with_override pattern continues.** Sessions 18-22 shipped a very large surface (§11 closeout + the entire §13 14-task cluster including 6 new REST endpoints + Email + WebPush adapters + dispatcher contract change + weekly digest job + frontend prefs/inbox/bell/push UIs + migration runner + reviews sub-route + codegen +630 lines), and the structural fields of the §13 tasks themselves regressed: T131-T144 + T030 are now COMPLETION-ANNOTATION-ONLY, with their original `Paths:/Size:/Deps:/Refs:/Description:/Done:` lines DROPPED in favor of prose annotations. Code is healthy (867 pass / 3 skip; +176 backend tests; +39 frontend tests; 0 orphan files; 16 visible frontend routes + 2 new for §13). Five clusters of doc-catch-up debt:

1. **Notification taxonomy count drift (14 vs 16):** spec.md US-G3 (line 199) + entity inventory (line 381) still say "14 active notification types"; code/registry has 16 active (N-009/N-010 are registered with all defaults OFF). This is the carry-forward of L2-017 from Run #5 that was partially fixed at the time. Now contradicts the code post-S19.
2. **PushSubscription entity missing from spec + plan:** new collection shipped in S20; not in spec.md entity inventory, not in plan §3.1 collection inventory.
3. **Plan §6 service surface + §3.1 + §15.2 PostHog table + §4.5 rate-limit table all under-enumerate the shipped notification surface:** 6 new endpoints + ~10 new PostHog events + new rate-limit rows are absent from plan.
4. **Tasks.md §13 (T131-T144) + T030 lost their structural fields:** completion-annotation prose is now the only source of `Paths:` info, breaking the task-doc convention used for every other task in the file.
5. **T118/T119 Paths stale post-route-rename:** declared `(onboarding)/follow-3/page.tsx` + `(onboarding)/complete/page.tsx` shipped as `(onboarding)/onboarding/step-2/page.tsx` + `step-3/page.tsx` respectively.

All resolvable in a single coordinated edit pass. Carry-forwards (L3-017, L4-009, L6-002) remain user-deferred under their existing dispositions.

### Sessions 18-22 propagation audit

| Cluster | Code shipped | Plan documented | Spec/product-spec documented | Drift IDs |
|---------|:---:|:---:|:---:|:--|
| §11 Onboarding — T117 critic-seed scoring | ✅ | partial (plan §12.2 mentions algorithm but not `_GENRE_BONUS_MAX = 20.0` knob; no scoring formula in plan) | ✅ | L3-039 |
| §11 — T117a `GET /api/v1/onboarding/cards` HTTP surface | ✅ | ❌ plan §6 seeding row missing route + plan §4.5 missing rate-limit | n/a (HTTP-internal) | L3-034, L3-038 |
| §11 — T117a `_FollowRequestBody.source` allowlist on `POST /users/{handle}/follow` | ✅ | ❌ plan §6 social row doesn't mention `source` allowlist | partial (product-spec follow-source not enumerated) | L2-031, L3-035 |
| §11 — T118/T119 onboarding step-2 + step-3 frontend | ✅ | n/a (frontend) | n/a | L4-025 (Paths stale) |
| §11 — T120 `onboarding.completed` PostHog | ✅ | ✅ (plan §15.2 line 1005 carries the row) | n/a | — |
| §13 — T131-T134 dispatcher + coalescer + InApp adapter (S19) | ✅ | partial (plan §8.1-§8.3 high-level only; no contract details — `is_notifiable` decision order, `SET NX EX` dedup, `ChannelDecision` types missing) | ✅ (taxonomy doc is canonical) | L3-036, L4-026 (Paths fields stripped) |
| §13 — T135 Email adapter (S20) | ✅ | partial (plan §8.3 says "Resend" but doesn't mention Jinja templates, FailedEmail retry contract, dispatcher contract change `notification_id` threading) | n/a (taxonomy holds copy) | L3-036, L4-026 |
| §13 — T136 WebPush adapter + PushSubscription model + endpoints (S20) | ✅ | ❌ plan §3.1 missing `push_subscriptions` row; §6 missing register/delete routes; §4.5 missing rate-limit; §8.3 doesn't mention `asyncio.to_thread` wrap or 410-Gone cleanup | ❌ PushSubscription not in spec.md entity inventory; product-spec/data-model.md not updated | L2-030, L3-033, L3-036, L3-038, L4-026 |
| §13 — T137 16-active-type registry (S19) | ✅ | n/a (registry is in code; taxonomy is canonical) | ❌ spec.md still says "14 active" in US-G3 + entity table | L2-028 |
| §13 — T138 + T143 weekly digest + review-likes hero (S20) | ✅ | partial (plan §8.4 mentions three-hero carousel; no T143 review-likes hero; no `digest.sent` properties enumerated) | ✅ (taxonomy NT-2 + NT-4 cover) | L3-036 |
| §13 — T139 prefs UI + 2 prefs endpoints (S21) | ✅ | ❌ plan §6 notifications row missing `get/update_preferences` (calls are there but route names absent); plan §4.5 missing rate-limit | partial (spec.md US-G3 AC mentions per-channel toggles + quiet hours but not security-types email lock, not coalesced rollup copy, not the curated tz select) | L2-029, L3-034, L3-038 |
| §13 — T140 inbox + bell + 4 list/read endpoints (S21) | ✅ | ❌ plan §6 missing `list_notifications`, `unread_count`, `mark_read`, `mark_all_read`; §4.5 missing 4 rate-limit rows; §15.2 missing `notifications.opened` + `notifications.mark_all_read` | ❌ spec.md doesn't capture inbox page as a US-G3 acceptance criterion | L2-029, L3-034, L3-038, L4-027 |
| §13 — T141 push-prompt + sw.js + criteria (S21) | ✅ | ❌ plan doesn't describe the prompt criteria `follows_count>=3 OR 7d activity`, the 14d re-show window, the `markFollow()` counter, or sw.js | ❌ spec.md doesn't mention push-prompt criteria as an AC | L2-029, L3-037 |
| §13 — T144 `notification.dispatched` + `posthog_dashboard.yml` (S19) | ✅ | partial (plan §15.2 prose mentions "notification dispatch emits PostHog event" but no row in event table; alert threshold p95>12/wk not in plan) | n/a | L3-036 |
| T030 — migration runner (S22) | ✅ | ❌ Constitution P2 (plan line 25) says `backend/migrations/{collection}_v{N}_to_v{N+1}.py`; shipped `apps/api/src/auxd_api/migrations/00N_*.py` filename-order | n/a (infra) | L3-040 |
| T030 — Paths field stripped | n/a | n/a | n/a | L4-026 (umbrella) |
| T094 — reviews-only profile sub-route (S22) | ✅ | partial (plan §6 reviews row mentions `users-sidecar` from Run #9 but doesn't enumerate the new endpoint or albums sidecar; new GET adds `albums` sidecar) | partial (no dedicated FR; US-E2 references diary; T094 reviews-list is implicitly under US-G1/US-E1) | L2-030 (albums sidecar parallel), L3-038 (rate-limit row), L6-005 (no story trace) |

### Key findings

**L2-028 (most material correctness gap):** spec.md US-G3 says "14 active notification types"; entity inventory line 381 says "14 active types (+ 6 reserved-gap IDs)"; code/registry has 16 active types — N-009/N-010 are kept in the `NotificationType` enum with all defaults OFF (taxonomy-doc declares them DEFERRED-TO-V2 but the enum + registry retain them). Either (a) bump spec text 14 → 16 and add a note about N-009/N-010 being "registered but all defaults OFF", or (b) remove N-009/N-010 from the enum + registry (would write a schema migration touchpoint — heavier). Recommended: option (a), one-line fix in two locations.

**L3-033 (data-model PushSubscription gap):** plan §3.1 collection inventory has 19 rows (post-Run #10); code's `ALL_DOCUMENT_MODELS` now has 20 — PushSubscription is the missing row. Fix: add a new row to plan §3.1 with the index spec (`user_id` indexed, `endpoint` unique), volume estimate (5k–20k), and 410-Gone cleanup semantics. Also add `PushSubscription` to spec.md §entity-inventory.

**L3-036 (plan §8 doc-catchup batch — single largest cluster):** plan §8 (Notification Dispatcher) is high-level prose only and predates the shipped contract. At minimum needs:
- §8.1 architecture diagram updated: in_app adapter writes the row FIRST and threads `notification_id` to email + push adapters (S20 dispatcher contract change).
- §8.3 Adapters: add `EmailAdapter` Jinja2 template paths + FailedEmail row on retry exhaustion; add `WebPushAdapter` `pywebpush + asyncio.to_thread` pattern + 410-Gone subscription cleanup; document the `TYPES` registry (T137) and `NotificationTypeSpec` as the per-type defaults source.
- §8.4 Weekly digest: add T143 review-likes hero ("Your reviews got X likes this week" prepended above three-hero carousel) + `digest.sent` properties (`hero_count, body_count, has_review_likes_hero`).
- New §8.5 needed: `is_notifiable` predicate decision order + security-types email lock for N-016/N-017 + quiet-hours TZ math.
- New §8.6 needed: `allow_dispatch` four-bucket Redis scheme (per-user/type/hour + day + per-actor/cross-type/day + per-event dedup with `SET NX EX 1h`).

**L4-026 (tasks.md §13 + T030 + T094 lost their structural fields — single largest task-doc gap):** Every task from T131 through T144 plus T030 plus T094 is now annotated as `*(completed... long prose...)*` ONLY. The original `Paths:/Size:/Deps:/Refs:/Description:/Done:` six-field convention is GONE for these 16 tasks. This breaks every Layer 5 forward-sweep that tries to map `[x]` tasks → declared file paths. Other shipped tasks (T101-T112, T085-T100, T070-T084, T031-T040, T011-T029, T053-T062, T063-T069, T073-T078, T117-T120) all preserve the structural fields with parenthetical annotations alongside. The §13/T030 pattern is the outlier. Fix: restore the six-field block for each of those 16 tasks; keep the prose annotation as a `*(completed ...)*` line after the task title (matches the convention from T117 / T101 / T077 etc.).

**L4-025 (T118/T119 Paths stale — single one-line edit each):** T118 declares `apps/web/src/app/(onboarding)/follow-3/page.tsx`; ships `(onboarding)/onboarding/step-2/page.tsx`. T119 declares `(onboarding)/complete/page.tsx`; ships `(onboarding)/onboarding/step-3/page.tsx`. The route layout uses `(onboarding)` route-group + `onboarding/` directory + `step-N/` sub-route. Mirror the T039 convention pattern; missed when CR-001 reflowed the onboarding step count.

**L3-034 (plan §6 + §4.5 + §15.2 — three under-enumerated tables):**

| Plan table | Missing entries | Count |
|------------|-----------------|:-:|
| §6 service surface table — `notifications` row | `get_preferences`, `update_preferences`, `list_user_notifications`, `unread_count`, `mark_read`, `mark_all_read`, `register_push_subscription`, `delete_push_subscription` (plus internal `is_notifiable`, `allow_dispatch`, `validate_payload`, `render_in_app`) | 8 public + 4 internal |
| §6 service surface table — `seeding` row | `score_critics_by_genre_signature`, `get_card_recommendations_for_user`, `get_onboarding_cards`, HTTP route `GET /api/v1/onboarding/cards` | 4 |
| §4.5 rate-limit table | `GET /api/v1/notifications/unread-count` (120/min); `POST /api/v1/notifications/mark-all-read` (10/min); `PUT /api/v1/users/me/notification-preferences` (per-user); `POST /api/v1/users/me/push-subscriptions` (10/min); `GET /api/v1/onboarding/cards` (30/min); `GET /api/v1/notifications` (list endpoint); `GET /api/v1/users/{handle}/reviews` (T094) | 7 |
| §15.2 PostHog event table | `notification.dispatched`, `notification.suppressed_onboarding_preselected`, `onboarding.cards_loaded`, `settings.notifications_updated`, `notifications.mark_all_read`, `notifications.opened`, `push.prompt_shown`, `push.permission_granted`, `push.permission_denied`, `push.dismissed`, `push.subscribe_failed` | 11 |

Total: 30 enumeration entries missing across 4 plan tables.

**L3-040 (Constitution P2 phrasing diverges from shipped migration runner):** plan line 25 (Constitution Principle 2): "Migration code lives in `backend/migrations/{collection}_v{N}_to_v{N+1}.py`. No big-bang migrations." Shipped at `apps/api/src/auxd_api/migrations/00N_*.py` with filename-ordered numeric prefix (T030 / Session 22). The shipped pattern is in line with the runner's discovery semantics (it scans `00N_*.py`) but the Constitution text is stale. Fix: update the principle to read "Migration code lives in `apps/api/src/auxd_api/migrations/00N_<name>.py`. Filename-ordered numeric prefix; runner skips already-applied; fail-loud on apply error."

### All Drift Items

#### NEW this run

**L1-004** [INFO / cosmetic] research/ux-patterns.md or research/codebase-analysis.md doesn't carry a breadcrumb about the "non-modal push-prompt banner" criteria (`follows_count >= 3 OR 7d activity`). taxonomy doc covers it but the up-stream UX research doesn't.
*Proposed:* One-line breadcrumb under the Notifications section in research/ux-patterns.md: "Push permission prompt is non-modal — fires when follows_count ≥ 3 OR 7d active; 14d re-show after dismiss. Avoids first-session interruption (Goodreads anti-pattern)."

**L2-028** [WARNING / structural] spec.md US-G3 (line 199) + entity inventory (line 381) both say "14 active notification types"; shipped `NotificationType` enum + registry has 16 active types (N-009 + N-010 registered with all defaults OFF per taxonomy DEFERRED-TO-V2). Carry-forward of L2-017 (Run #5).
*Proposed:* Both lines say "16 active notification types (N-009 / N-010 registered with all defaults OFF per CR-001 deferral) + 4 reserved-gap IDs (N-011, N-018, N-019, N-020)". Two-line edit.

**L2-029** [WARNING / structural] spec.md US-G3 AC text doesn't mention three load-bearing facets of the shipped UI: (a) N-008 weekly_digest push is hardcoded-off; (b) N-016/N-017 email is locked-on (cannot be disabled — returns 422 `security_email_locked`); (c) coalesced rollup copy "X and N others did something" in the inbox; (d) curated IANA timezone select (not the full Intl.supportedValuesOf dropdown); (e) push-prompt criteria `follows_count >= 3 OR 7d activity`.
*Proposed:* Append a bullet to US-G3 AC capturing these constraints, or split into US-G3a (prefs UI semantics) + US-G3b (inbox UX) so future story-vs-code traceability is preserved.

**L2-030** [WARNING / structural] PushSubscription entity missing from spec.md entity inventory (line ~370-385). Shipped collection with KSUID id, user_id, endpoint UNIQUE, p256dh_key, auth_secret, user_agent?, created_at, last_used_at.
*Proposed:* Add row to spec.md entity inventory: `| PushSubscription | Per-device VAPID push registration. 410-Gone deletes dead sub on send. |`. Mirror in product-spec/data-model.md.

**L2-031** [WARNING / structural] product-spec doesn't enumerate the `Follow.source` field allowlist (`{onboarding_preselected, onboarding_mutual_taste, suggestion, profile, invite, manual}`) that shipped in Session 18. Used by T142 (suppression) and PostHog funnel facets.
*Proposed:* Add a row to product-spec/data-model.md Follow block: `source: literal allowlist of 6 values; defaults to "profile" when not specified; persisted to drive (a) T142 onboarding-wave N-001 suppression, (b) PostHog `social.follow` funnel facet.`

**L3-033** [WARNING / structural] plan.md §3.1 collection inventory has 19 rows; code's `ALL_DOCUMENT_MODELS` has 20 (PushSubscription added in S20).
*Proposed:* Add a row to plan §3.1 between `notification_preferences` and `just_finished_prompts`: `| push_subscriptions | 5k–20k | user_id · endpoint unique · last_used_at | Per-device VAPID; 410-Gone DELETE on dead send (web_push adapter cleanup). |`

**L3-034** [WARNING / structural] plan §6 service surface table — `notifications` row + `seeding` row dramatically under-enumerated vs shipped routes (see findings table above; 8 public + 4 internal notifications, 4 seeding).
*Proposed:* Two edits — append the missing methods to each row's `Verbs` column. Update `Notes` column for `notifications` to flag the in-app-first-then-email+push contract (S20).

**L3-035** [WARNING / structural] plan §6 social row doesn't mention the `source` allowlist body field added to `POST /users/{handle}/follow` in S18.
*Proposed:* Append parenthetical to the social row Verbs: `follow *(optional body {source: literal allowlist[6]})*`.

**L3-036** [WARNING / structural] plan §8 (Notification Dispatcher) — five-bullet doc-catchup batch:
1. §8.1 architecture: in-app-first row creation + `notification_id` thread to email/push adapters (S20 contract change).
2. §8.3 Adapters: Jinja2 template stack + FailedEmail retry retention; `pywebpush + asyncio.to_thread` wrapping + 410-Gone cleanup; `TYPES` registry as the per-type defaults source.
3. §8.4 Weekly digest: T143 review-likes hero + `digest.sent` properties.
4. New §8.5: `is_notifiable` decision order + security-types email lock (N-016/N-017) + quiet-hours TZ math.
5. New §8.6: `allow_dispatch` four-bucket Redis scheme + `SET NX EX 1h` atomic dedup + FAIL-OPEN semantics on Redis down with `notif_limiter.redis_down` Sentry tag.
*Proposed:* Single coordinated rewrite of plan §8 (5 subsection touches), ~80 lines added.

**L3-037** [WARNING / structural] plan doesn't carry a §7.X subsection for the web-push subscribe flow (criteria, sw.js, markFollow counter, 14d re-show window). Frontend architecture §7 is silent on the bootstrap flow.
*Proposed:* Add §7.6 "Web push subscribe flow" subsection covering: prompt criteria (`follows_count >= 3 OR 7d`), localStorage counters (`first_visit_at`, `follows_count`, `dismissed_at` with 14d re-show), the `push-bootstrap.tsx` silent SW registration at app boot, and `sw.js` push + notificationclick handlers.

**L3-038** [WARNING / structural] plan §4.5 rate-limit table — 7 missing rows for shipped endpoints (see findings table above).
*Proposed:* Append 7 rows to the table.

**L3-039** [INFO / structural] plan §12.2 (Pre-checked card algorithm) references "score critic-seeds" but doesn't pin the `_GENRE_BONUS_MAX = 20.0` knob or document the `priority + (jaccard_overlap × _GENRE_BONUS_MAX)` formula.
*Proposed:* Append one paragraph: "Score = `priority + (jaccard_overlap_with_viewer_genre_signature × _GENRE_BONUS_MAX)` where `_GENRE_BONUS_MAX = 20.0` — caps the genre-overlap bonus so a perfect-match closes a 20-point priority gap; bumping above 30 would let niche-genre critic with priority=50 outrank generalist with priority=80, which the founder doesn't want until per-user signal is much richer (codified in seeding-strategy.md §3)."

**L3-040** [INFO / cosmetic] plan line 25 (Constitution Principle 2): "Migration code lives in `backend/migrations/{collection}_v{N}_to_v{N+1}.py`." Shipped at `apps/api/src/auxd_api/migrations/00N_*.py` with filename-ordered numeric prefix. Stale phrasing.
*Proposed:* Update P2 text to: "Migration code lives in `apps/api/src/auxd_api/migrations/00N_<name>.py`. Filename-ordered numeric prefix; runner skips already-applied (by `_schema_version` threshold); fail-loud on apply error (re-raises so a botched migration cannot serve traffic)."

**L4-025** [WARNING / structural] tasks.md T118 Paths declares `apps/web/src/app/(onboarding)/follow-3/page.tsx`; ships `(onboarding)/onboarding/step-2/page.tsx`. T119 Paths declares `(onboarding)/complete/page.tsx`; ships `(onboarding)/onboarding/step-3/page.tsx`.
*Proposed:* Two one-line edits — rename both Paths to the shipped `step-N/` form. Also append the new `apps/web/src/components/onboarding/{follow-critics-deck,onboarding-complete}.tsx` to T118 / T119 Paths respectively.

**L4-026** [WARNING / structural] T131-T144 (14 tasks) + T030 + T094 (16 total) have their structural fields stripped — completion annotation prose replaced the `Paths:/Size:/Deps:/Refs:/Description:/Done:` six-field convention. Other shipped tasks preserve the convention with `*(completed ...)*` annotations alongside.
*Proposed:* Restore the six-field block for each of T030, T094, T131-T144. Keep the prose annotation as a `*(completed ...)*` line after the task title (matches T117 / T101 / T077 pattern). Heaviest single fix in the inline list but unblocks Layer 5 forward-sweeps for the entire §13 cluster.

**L4-027** [WARNING / structural] T140 inbox endpoints not enumerated in any plan §6 table or §4.5 row (covered above under L3-034/L3-038 but worth a tasks.md cross-reference). T140 ships 4 new public endpoints: `GET /api/v1/notifications`, `GET /api/v1/notifications/unread-count`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications/mark-all-read` plus the 2 prefs endpoints under T139.
*Proposed:* When restoring T140's Paths field (per L4-026), explicitly enumerate the 4 new public endpoint paths in the description.

**L4-028** [INFO / cosmetic] T117 Refs claims "decision-log Q13; UJ-2" — file path missing. Should be `product-spec/decision-log.md` (Q13) + `product-spec/user-journeys.md` (UJ-2) for navigability.
*Proposed:* Expand to fully-qualified relative paths.

**L4-029** [INFO / cosmetic] T117a Refs claims "A-005 from pre-impl-review" — A-005 was the inline-vs-batch architecture finding, but pre-impl-review.md line 141 isn't called out explicitly; could reference pre-impl-review.md A-005 section.
*Proposed:* No change unless future readers ask; the line-number ref is good enough.

**L5-018** [WARNING / structural] T118 + T119 Paths reference files that DON'T EXIST on disk (`follow-3/page.tsx`, `complete/page.tsx`). Projection of L4-025; flagged here because Layer 5 forward-sweep falsely reports "claimed files missing".
*Proposed:* Same fix as L4-025 (resolves both L4 and L5 simultaneously).

**L5-019** [INFO / cosmetic] §13 cluster (T131-T144) + T030 + T094 have NO declared Paths fields, so Layer 5 forward-sweep can't run on them at all. All files actually do exist on disk (confirmed via direct `ls`); the convention regression masks them.
*Proposed:* Subsumed by L4-026 fix.

**L5-020** [INFO / cosmetic] T138 description mentions "templates/email/*" without full path. Templates actually live at `apps/api/src/auxd_api/templates/email/` (NOT under the notifications module). Minor ambiguity.
*Proposed:* When restoring T138 Paths (per L4-026), use the full path: `apps/api/src/auxd_api/templates/email/{base,n008_weekly_digest,n013_account_deletion_scheduled,n014_account_deletion_reminder_7d,n016_security_new_session,n017_security_password_changed}.html`.

**L6-005** [INFO / structural] T094 reviews-only profile sub-route shipped without a dedicated US-NNN. The story is implicitly under US-E2 (chronological diary) + US-G1 (profile editing) but neither explicitly mentions a reviews-only sub-page. Run #9's L4-019 restored the T094 header; this run finds the story-side gap.
*Proposed:* Add a new bullet to spec.md US-E2 AC: "Profile diary view has a Reviews tab that filters to entries with attached reviews — backed by `GET /api/v1/users/{handle}/reviews` and the `/profile/{handle}/reviews` SSR route." OR carve a separate US (e.g., US-E2a). Single-line edit recommended.

**L7-017** [INFO / cosmetic] implementation-log.md Session 22 references "T094 — Reviews-only profile sub-route" but the Diary/Reviews tab nav mentioned therein lives in `apps/web/src/components/diary/profile-client.tsx` — Session 22 prose says "Diary/Reviews tab nav added to existing profile-client.tsx" but the canonical implementation-log structure usually carries an "Added files" + "Modified files" enumeration. Cross-link is intact; just convention drift.
*Proposed:* No edit required; flag for awareness only.

#### Carry-forward (still open from prior runs)

- **L1-002** (Run #10) — research/ux-patterns.md "For You" breadcrumb — RESOLVED in Run #10 inline application; verified intact.
- **L2-017** (Run #5) — spec.md "14 active types" — PARTIALLY RESOLVED in Run #5 (text was 18 → 14), now REOPENED as L2-028 (14 → 16 needed).
- **L2-019** (Run #4) — SS-3 cohort signup_cohort undefined — OPEN, DEFER (invite-mechanic cluster).
- **L3-017** (Run #4) — plan.md §12 missing SS-3 invite-landing — OPEN, DEFER.
- **L4-009** (Run #4) — tasks.md missing invite-landing tasks — OPEN, DEFER.
- **L4-013** (Run #7) — Paths under-enumeration convention — OPEN-DEFERRED.
- **L4-017** (Run #8) — T077/T079 Paths missing helpers — OPEN-DEFERRED.
- **L4-020** (Run #9) — T093/T092 Paths under-spec — OPEN-DEFERRED.
- **L5-008** (Run #8) — T080 wildcard absorbs helpers — OPEN-DEFERRED.
- **L6-002** (Run #7) — US-A1 handle suggestions — OPEN, DEFER (low-priority polish).

### Proposed inline actions (17 items)

| ID | File | Change | Auto-resolvable? |
|----|------|--------|:--:|
| L1-004 | research/ux-patterns.md | 1-line breadcrumb on push-prompt criteria | No |
| L2-028 | spec.md US-G3 + entity inventory | 14 → 16 active types in 2 locations | No |
| L2-029 | spec.md US-G3 AC | Append 5-bullet sub-list for prefs UI + inbox + push-prompt facets | No |
| L2-030 | spec.md entity inventory + product-spec/data-model.md | Add PushSubscription row to both | No |
| L2-031 | product-spec/data-model.md Follow block | Append `source: literal[6]` allowlist line | No |
| L3-033 | plan.md §3.1 | Insert `push_subscriptions` row between notification_preferences and just_finished_prompts | No |
| L3-034 | plan.md §6 notifications + seeding rows | Expand Verbs columns (8 public + 4 internal + 4 seeding) | No |
| L3-035 | plan.md §6 social row | Append `source` body field parenthetical to `follow` verb | No |
| L3-036 | plan.md §8 (single coordinated rewrite) | 5-subsection batch (§8.1, §8.3, §8.4, new §8.5, new §8.6) | No |
| L3-037 | plan.md §7 | Add new §7.6 Web push subscribe flow | No |
| L3-038 | plan.md §4.5 rate-limit table | 7 new rows | No |
| L3-039 | plan.md §12.2 | Append `_GENRE_BONUS_MAX = 20.0` formula paragraph | No |
| L3-040 | plan.md Constitution P2 | Update migration code location + filename pattern | No |
| L4-025 + L5-018 | tasks.md T118 + T119 Paths | Rename to `onboarding/step-N/page.tsx`; add components | No |
| L4-026 + L5-019 | tasks.md T030, T094, T131-T144 | Restore six-field block for 16 tasks; preserve `*(completed ...)*` annotation as a separate line after the task title | No |
| L4-028 | tasks.md T117 Refs | Expand to fully-qualified relative paths | No |
| L6-005 | spec.md US-E2 AC | Append Reviews-tab line | No |

### Defer (5 items, existing dispositions stand)

- L2-019 — invite-mechanic cluster sequencing
- L3-017 — invite-mechanic cluster
- L4-009 — invite-mechanic cluster
- L4-013 / L4-017 / L4-020 / L5-008 — Paths-convention umbrella
- L6-002 — low-priority polish

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #8 | 2026-05-23 (post-§7-wedge-wave) | 7/7 | 0 | 8 | 9 | DRIFT_DETECTED | applied_split_with_override |
| #9 | 2026-05-23 (post-§8+§9) | 7/7 | 0 | 12 | 10 | DRIFT_DETECTED | applied_split_with_override |
| #10 | 2026-05-23 (post-§10) | 7/7 | 0 | 14 | 13 | DRIFT_DETECTED | applied_split_with_override |
| **#11** | **2026-05-23 (post-§11+§13+stranded)** | **7/7** | **0** | **18** | **14** | **DRIFT_DETECTED** | **applied_split_with_override** (17 inline + 5 deferred — pending user confirmation) |

---

## Run #10 (2026-05-23, post-§10-social-graph-and-feed)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **107/172** tasks complete (62%)
> Prior run: #9 (2026-05-23T15:45Z) — DRIFT_DETECTED, applied_split_with_override (12 inline + 8 deferred; Sessions 15-16 doc catch-up)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Session 17 (§10 Social graph + Feed: T101-T112 + inline GET /users/{handle})

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **11 NEW + 3 carry-forward = 14** | NEW: L1-002, L2-023, L2-024, L2-026, L3-025, L3-026, L3-027, L3-028, L3-030, L3-031, L4-021, L5-014. CF: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **8 NEW + 5 carry-forward = 13** | NEW: L2-025, L2-027, L3-023, L3-029, L3-032, L4-022, L4-023, L4-024, L5-015, L5-016, L5-017. CF: L2-019, L4-013, L4-017, L4-020, L5-008 |
| ✅ CLEAN | **L6 + L7** | Layer 6 verified clean for all Session 17 Must Have stories; L7 168 links across 38 files all resolve |
| ✅ RESOLVED since Run #9 | 0 new resolutions | (Run #9's 12 inline fixes all verified intact) |

**Structural count:** 17 (NEW: 13; CF: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 9 (NEW: 5; CF: 4 — L4-013, L4-017, L4-020, L5-008). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override (Applied — 16 inline + 8 deferred).** Same doc-catch-up pattern as Runs #8/#9. Session 17 shipped a large net-new surface (8 social routes + 4 feed routes + 1 inline profile endpoint + 2 collections + 5 PostHog events + for_you/latest mode split + multiplicative score formula) — plan.md, spec.md, and product-spec/ hadn't been amended for any of it. Code is healthy (667 pass/3 skip; +75 tests; 13 frontend routes; 0 orphan files). Resolved in a single coordinated edit pass covering plan.md (7 locations) + spec.md/product-spec (5 locations) + tasks.md (4 small fixes + 2 new deferred-task placeholders T101a + T163a) + 1 research breadcrumb. Carry-forwards remain user-deferred. Post-apply gates: ruff + mypy strict + Biome 104 files + tsc all clean (no source code touched).

### Sessions 17 propagation audit

| Cluster | Code shipped | Plan documented | Spec/product-spec documented | Drift IDs |
|---------|:---:|:---:|:---:|:--|
| Follow / unfollow (T101) | ✅ | ✅ | ✅ | — |
| Block (T102) | ✅ | ✅ | ✅ | — |
| Friends-who-rated (T103) | ✅ | ✅ | ✅ | — |
| Suggestions worker (T104) | ✅ | ⚠️ algorithm not in plan §12 | ⚠️ collection name + reason field drift | L2-026, L2-027, L3-025, L3-032 |
| Suggestions API + dismiss (T105) | ✅ | ❌ not in plan §6 | ✅ | L3-027, L4-024 |
| Home feed for_you/latest (T106) | ✅ | ❌ §10 has wrong contract + formula | ❌ "For You" name not in spec; mode toggle not described | L1-002, L2-023, L3-029, L3-030 |
| Feed perf (T107) | ✅ | ✅ | ✅ | — |
| Inline `GET /users/{handle}` | ✅ | partial (plan §6 mentions `user_profile`; relation enum absent) | ❌ no FR row | L2-024, L4-021 |
| FollowRequest approve/decline | partial (pending writes; responder UI not shipped) | ⚠️ plan §6 over-promises | ⚠️ US-G2 / S-H3 ambiguous | L2-025, L3-026, L4-022 |
| POST /reports/user (T111 frontend stub) | not shipped | ❌ no task | ❌ no task | L4-023 |
| Rate-limit table (§4.5) | shipped | ❌ stale | n/a | L3-028 |
| PostHog events | shipped | ❌ social events absent from §15.2 | n/a | L3-031 |
| Frontend feed UI + profile + follow + block-report + discover | ✅ | n/a (frontend) | ✅ | minor Paths under-enumeration (L5-015/16/17 under L5-008 umbrella) |
| Test filename match | shipped | ❌ T106 cites wrong filename | n/a | L5-014 |

### Key findings

**L1-002 (most substantive product question):** ux-patterns research explicitly said "resist any 'For You' injection until late v2" — code shipped `?mode=for_you|latest`. Weights ARE the "weight the activity types" anti-noise design research called for, but the LABEL is the exact phrase research warned against. Two options: (1) rename query param to `weighted|latest` (code churn), (2) amend ux-patterns with a breadcrumb clarifying "For You" here = interaction-weight reordering only, no out-of-graph injection. Recommended: option 2 (cheaper + faithful to research intent).

**L3-030 (plan vs shipped algorithm formula mismatch):** plan §10.2 says additive `score = base_recency + 0.20*has_review + ...`; shipped is multiplicative `score = 1.0 * 1.20(if review) * 1.15(if extreme) * ... * 0.5^(age_hours/72)`. These compose differently. Plan needs to match shipped (or vice versa — multiplicative is the better composer for stacking weights).

**L3-026 (plan over-promise):** plan §6 lists `respond_to_follow_request` + `list_follow_requests` as part of `social` module surface — neither shipped. Fix: mark as DEFERRED in plan.

**L4-022 + L4-023 (no T-id for deferred work):** FollowRequest approve/decline UI + `POST /reports/user` endpoint are both real future work with no tasks tracking them. Fix: add `T101a` (FollowRequest responder) and `T163a` (submit-report endpoints).

**L5-014 (filename typo):** T106 Paths cite `test_feed.py`; actual is `test_feed_endpoint.py`. One-line fix.

### Proposed inline actions (16 items)

| ID | File | Change |
|----|------|--------|
| L1-002 | research/ux-patterns.md | 1-line breadcrumb: "For You here = interaction-weight reordering; no out-of-graph injection" |
| L2-023 | spec.md US-E3 + product-spec S-E3 | Name both modes ("For You" weighted default + "Latest" chronological) in AC |
| L2-024 | spec.md §5 FR table | Add FR-036 (profile read with viewer-relation classifier, 404-on-blocked) |
| L2-025 | product-spec S-G2 + spec.md US-G2 | Append breadcrumb that approve/decline UI is tracked under S-H3 (Could-have) — MVP ships creation only |
| L2-026 | product-spec/data-model.md | Rename SuggestedFollow → Suggestion; add SuggestionDismissal block |
| L2-027 | product-spec/data-model.md | Suggestion reason field → `reasons: list[str]` (multiple) with shipped tag labels |
| L3-025 | plan.md §3.1 | Replace `suggested_follows` row with `suggestions` + `suggestion_dismissals` rows |
| L3-026 | plan.md §6 social row | Append shipped surface; mark `respond_to_follow_request` + `list_follow_requests` DEFERRED |
| L3-027 | plan.md §6 social row | Add `list_suggestions`, `dismiss_suggestion`, `list_blocks`, `get_user_profile` |
| L3-028 | plan.md §4.5 rate-limit table | Add 5 social/feed rows; correct stale `POST /follow` 30/min → 60/min |
| L3-029 | plan.md §10.1 | Replace `viewer.feed_latest_only` (User field) with `?mode=for_you|latest` query param |
| L3-030 | plan.md §10.2 | Rewrite score formula to match shipped (multiplicative + 0.5^(age_hours/72) half-life) |
| L3-031 | plan.md §15.2 PostHog table | Add 5 shipped social events (follow/unfollow/block/unblock/suggestion.dismiss) |
| L4-021 | tasks.md T109 Paths | Append `apps/api/src/auxd_api/modules/users/routes.py` (inline `get_user_profile`) |
| L5-014 | tasks.md T106 Paths | Rename `test_feed.py` → `test_feed_endpoint.py` |
| L4-022 + L4-023 | tasks.md §10/§15 | Insert `T101a` (FollowRequest approve/decline; DEFERRED) + `T163a` (POST /reports/user) |

### Defer (8 items)

- L2-019, L3-017, L4-009 — invite-mechanic cluster
- L4-013, L4-017, L4-020, L5-008, L5-015, L5-016, L5-017 — Paths-convention umbrella
- L6-002 — low-priority polish (US-A1 handle suggestions)

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1-#8 | (rows preserved below) | | | | | | |
| #9 | 2026-05-23 (post-§8+§9) | 7/7 | 0 | 12 | 10 | DRIFT_DETECTED | applied_split_with_override |
| **#10** | **2026-05-23 (post-§10)** | **7/7** | **0** | **14** | **13** | **DRIFT_DETECTED** | **applied_split_with_override** (16 inline applied + 8 deferred) |

---

## Run #9 (2026-05-23, post-§8-reviews-and-§9-backlog)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **95/171** tasks complete (56%)
> Prior run: #8 (2026-05-23T12:30Z) — DRIFT_DETECTED, applied_split_with_override (8 inline + 1 sweep fix; 6 deferred)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 15–16 (§8 Reviews + Likes + sort, §9 Backlog / Up Next)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **9 NEW + 3 carry-forward = 12** | NEW: L2-020, L2-021, L3-020, L3-021, L3-022, L3-024, L4-019, L5-013, L6-004. Carry-forward: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **6 NEW + 4 carry-forward = 10** | NEW: L1-001, L2-022, L3-023, L4-018, L4-020, L5-012. Carry-forward: L2-019, L4-013, L4-017, L5-008 |
| ✅ RESOLVED | **0 NEW resolutions** | Sessions 15–16 introduced new doc drift; carry-forward items from prior runs all still open. |
| ✅ CLEAN | **L7 only** | Cross-link integrity holds; L7-016 confirmed resolved since Run #8 |

**Structural count:** 13 (NEW: 9; carry-forward: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 9 (NEW: 6; carry-forward: 3 — L4-013, L4-017, L5-008). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override (Applied this run — 12 inline + 7 deferred).** Sessions 15–16 shipped 9 new REST endpoints (7 reviews, 2 backlog reads), the `albums`/`users` sidecar pattern, `Review.deleted_at` soft-delete, 4 new PostHog events, and `@dnd-kit` drag-reorder UX — none of which were documented in plan.md §6 (service surface), §3.1 (collection inventory), or §15.2 (analytics events). The shipped code is healthy; the gap was downstream doc catch-up. 9 of the 9 NEW WARNs resolved in a single coordinated edit pass:
1. **plan.md** catch-up to Session 15/16 reality (§6 rows for reviews + backlog; §3.1 reviews index; §15.2 PostHog event table; §12.1 CriticSeed correction).
2. **spec.md / product-spec** add FR-034 + FR-035 + US-C3 delete AC + Review schema fields.
3. **tasks.md** insert orphan T094 header + fix T093a / T100 stale Paths.
4. **Sessions 15-16 frontend gap** — L6-004 (US-C3 edit affordance not mounted) — add a small inline "Edit" button to the review reading-view footer.

Remaining carry-forwards (L2-019, L3-017, L4-009, L6-002) keep their existing dispositions — invite-mechanic cluster + low-priority polish.

### Sessions 15–16 propagation audit (the headline check)

| Cluster | Status | Notes |
|---------|:------:|-------|
| §8 Reviews + Likes + sort | ✅ Code shipped; 11/11 tasks complete; **plan + spec doc gaps** (L2-021, L3-020, L3-022, L6-004) |
| §9 Backlog / Up Next | ✅ Code shipped; 6/6 tasks complete; **plan + spec doc gaps** (L2-020, L3-021, L3-024, L5-013) |
| Must Have stories with implementation evidence | ✅ US-C1, US-C2, US-C4, US-D1, US-D2, US-D3 all have route + component + test. **US-C3 partial — edit dialog built but not yet mounted (L6-004)**. |
| Layer 5 forward sweep | ✅ All Session 15-16 declared Paths exist on disk; no orphan files |
| Layer 7 cross-links | ✅ CLEAN — 154 links across 37 files all resolve |

### New drift cluster: plan.md doc-catch-up to shipped reality

The single dominant root cause for 5 NEW WARNs (L3-020, L3-021, L3-022, L3-024, L4-019) is the plan.md not being amended after Sessions 15-16 shipped:

| plan.md location | What's missing | DRIFT ID |
|------------------|----------------|:--------:|
| §6 `reviews` row | `delete_review`, `get_review`, users-sidecar note | L3-020 |
| §6 `backlog` row | `list_backlog_items`, `contains_album`, albums-sidecar note | L3-021 |
| §3.1 `reviews` row | `deleted_at` sparse index + 30d-grace note | L3-022 |
| §12.1 critic-seed | "marked `critic_seed_active=true`" — should be CriticSeed table FK | L3-023 |
| §15.2 PostHog events | `backlog.added` → 4 shipped events: item_added, item_removed, reordered, converted_to_log | L3-024 |
| tasks.md §8 index | T094 header eaten (orphan task body at line 861) | L4-019 |

**Recommended inline resolution:** single coordinated pass amending plan.md (5 locations) + tasks.md (insert T094 header).

### New spec + product-spec gaps

| spec.md / product-spec | What's missing | DRIFT ID |
|------------------------|----------------|:--------:|
| spec.md §5 FR table | FR-034 (drag-reorder backlog with persisted order — US-D2) + FR-035 (auto-remove on log with `keep_backlog_after_log` setting — US-D3) | L2-020 |
| product-spec US-C3 AC + spec US-C3 | Delete-review AC (soft-delete 30d grace, confirmation dialog, idempotent 410) — currently shipped without story trace | L2-021 |
| product-spec/data-model.md Review block | `edited_at` + `deleted_at` field enumeration (DiaryEntry has both; Review is implicit via umbrella line) | L2-022 |

### New small-task / stale-path findings

| Where | What | DRIFT ID |
|-------|------|:--------:|
| tasks.md T093a Paths | `opengraph-image.tsx` listed but never shipped (deferred to T093c per impl-log Session 15) | L4-018 / L5-012 |
| tasks.md T100 Paths | Claims `apps/web/src/lib/analytics.ts` — emission is server-side via `emit_event`; no frontend analytics module exists | L5-013 |
| tasks.md T092 / T093 Paths | Helper files (`delete-confirmation.tsx`, `review-sort-select.tsx`, `recent-searches.tsx`) not enumerated — same Paths-convention umbrella as L4-013 | L4-020 |

### Layer 6 finding: US-C3 surface gap

**L6-004:** `EditReviewDialog` is implemented and exported (`apps/web/src/components/review-card/edit-review.tsx`) but never imported by any live route. The `review-reading-view` footer has no Edit button on the owner branch. Documented in implementation-log.md Session 15 as "ready-to-plug; activates when /profile/[handle]/reviews ships." A small ~10-line patch to surface it on the reading-view footer (when `isOwn`) would close the spec→code gap immediately.

### Carry-forward status snapshot

| ID | Description | Status | Disposition |
|----|-------------|:------:|-------------|
| L1-001 (NEW) | Backlog sort alternatives (rating/year) silently omitted vs research | OPEN | Apply inline (1-line breadcrumb) |
| L2-019 | SS-3 cohort `signup_cohort` undefined | OPEN | DEFER (invite-mechanic cluster) |
| L3-017 | plan.md §12 missing SS-3 invite-landing section | OPEN | DEFER (invite-mechanic cluster) |
| L4-009 | tasks.md missing invite-landing tasks | OPEN | DEFER (invite-mechanic cluster) |
| L4-013 | Paths under-enumeration convention | OPEN-DEFERRED | DEFER (convention umbrella) |
| L4-017 | T077/T079 Paths missing `recent-searches.tsx` | OPEN-DEFERRED | DEFER (convention umbrella) |
| L5-008 | T080 wildcard absorbs helpers; convention not written | OPEN-DEFERRED | DEFER (convention umbrella) |
| L6-002 | US-A1 auto-handle suggestions on collision | OPEN | DEFER (low-priority polish) |

### Proposed actions (inline + deferred)

**Applied inline this run (12 items, single coordinated pass — all green):**

| ID | File(s) | Change | Status |
|----|---------|--------|:------:|
| L1-001 | product-spec/user-stories.md | S-D2 breadcrumb deferring rating/year/added-date sort modes to v2 | ✅ APPLIED |
| L2-020 | spec.md §5 FR table | Added FR-034 (drag-reorder) + FR-035 (auto-remove on log) | ✅ APPLIED |
| L2-021 | product-spec/user-stories.md S-C3 (retitled "Edit (or delete)") + spec.md US-C3 | Delete-review AC line appended | ✅ APPLIED |
| L2-022 | product-spec/data-model.md Review block | `edited_at` + `deleted_at` field lines added | ✅ APPLIED |
| L3-020 | plan.md §6 reviews row | `delete_review` + `get_review` + users-sidecar note appended | ✅ APPLIED |
| L3-021 | plan.md §6 backlog row | `list_backlog_items` + `contains_album` + albums-sidecar note appended | ✅ APPLIED |
| L3-022 | plan.md §3.1 reviews row | `deleted_at sparse` index + 30d-grace note | ✅ APPLIED |
| L3-023 | plan.md §12.1 critic-seed | "critic_seed_active=true" replaced with CriticSeed FK truth | ✅ APPLIED |
| L3-024 | plan.md §15.2 PostHog table | `backlog.added` row replaced with 4 shipped events (item_added, item_removed, reordered, converted_to_log) | ✅ APPLIED |
| L4-019 / L4-018 / L5-012 | tasks.md §8 | Orphan T094 header restored at line 860 ("Reviews-only profile sub-route"); T093a Paths fixed (opengraph-image.tsx dropped, T093c follow-up note added) | ✅ APPLIED |
| L5-013 | tasks.md T100 Paths | `apps/web/src/lib/analytics.ts` dropped; cite `apps/api/.../diary/routes.py` | ✅ APPLIED |
| L6-004 | apps/web/src/components/review-reading-view/index.tsx | "Edit" button on owner footer opens `EditReviewDialog` (~10-line patch; build green) | ✅ APPLIED |

Build verification post-apply: Biome 96 files clean; tsc 0 errors; next build 11 routes (no bundle-size regression for `/review/[id]`).

**Defer (7 items, existing dispositions stand):**
- L2-019, L3-017, L4-009 — invite-mechanic cluster sequencing
- L4-013, L4-017, L5-008 — Paths-convention umbrella
- L6-002 — low-priority polish
- L4-018, L5-012 — overlapping with the inline T100 + T093a fixes (will be subsumed)
- L3-023 — short cosmetic edit included in the inline pass

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #8 | 2026-05-23 (post-§7-wedge-wave) | 7/7 | 0 | 8 | 9 | DRIFT_DETECTED | applied_split_with_override |
| **#9** | **2026-05-23 (post-§8+§9 waves)** | **7/7** | **0** | **12** | **10** | **DRIFT_DETECTED** | **applied_split_with_override** (pending user confirmation) |

---

## Run #8 (2026-05-23, post-§7-wedge-wave)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **75/172** tasks complete (44%)
> Prior run: #7 (2026-05-23T09:30Z) — DRIFT_DETECTED, applied_split_with_override (4 WARN + 4 INFO; 2 deferred to invite-mechanic cluster, 2 NEW spec-vs-code gaps tracked for next wave)
> Trigger: user invoked `/speckit.product-forge.sync-verify` after Sessions 13–14 (§7 Diary + Log sheet wedge wave: T073–T084 — wedge interaction now end-to-end live)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **5 NEW + 3 carry-forward = 8** | NEW: L3-019, L4-014, L4-015, L5-007, L7-016. Carry-forward: L3-017, L4-009, L6-002 |
| ℹ️ INFO | **7 NEW + 2 carry-forward = 9** | NEW: L3-018, L4-016, L4-017, L5-008, L5-009, L5-010, L5-011. Carry-forward: L2-019, L4-013 |
| ✅ RESOLVED | **3** | L4-010 (plan §7.1 routes added inline post-Run #7), L4-011 (T072 ref to §11.4 verified), **L6-003 (T081 my-history.tsx shipped)** |
| ✅ CLEAN | **1 layer** | L1 — research ↔ product-spec consistent under CR-002 propagation |

**Structural count:** 10 (NEW: 6 — L3-019, L4-014, L4-015, L4-016, L5-007, L7-016; carry-forward: 4 — L2-019, L3-017, L4-009, L6-002). **Over budget of 0.**
**Cosmetic count:** 7 (NEW: 6 — L3-018, L4-017, L5-008, L5-009, L5-010, L5-011; carry-forward: 1 — L4-013). Under budget of 20.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of Runs #2–#7 pattern. Override granted because (1) zero CRITICAL findings, (2) 4 of the 5 NEW WARN items (L3-019, L4-014, L5-007, L7-016) are projections of the same root cause — the Session 14 `/profile/[handle]` vs `/@[handle]` routing decision; these resolve in a single coordinated edit pass and are applied inline below, (3) L4-015 (diary `albums` sidecar) is a fresh API contract worth documenting before §8 reviews land — applied inline, (4) L6-002 (US-A1 handle suggestions) and L3-017 / L4-009 (invite-mechanic cluster) remain user-deferred under their existing dispositions, (5) Sessions 13–14 themselves landed cleanly across L1, L2 (CLEAN), and L5/L6 forward checks (every shipped Must Have story has route + component + test evidence).

**Inline application (Run #8 close-out):** All 8 planned inline items applied without errors; verified by post-edit grep. spec.md:350 (frontend module table) had a missed `app/@[handle]` reference caught in the post-edit sweep — also fixed under the L3-019 umbrella.

### Sessions 13–14 propagation audit (the headline check)

The two wedge-wave sessions (Session 13 backend wave + Session 14 §7 close-out) introduced 12 new code modules across backend and frontend. **L5 backward sweep confirms zero orphan files** — every modified or new file traces to a `[x]` task in tasks.md. **L6 forward sweep confirms every Must Have story shipped in this wave has implementation evidence:**

| Story | Wave evidence | Status |
|-------|--------------|:------:|
| US-B1 (log <8s) | T077 log-sheet + T084 NFR test (10-trial p95 <8000ms; backend <1500ms in-process) | ✅ |
| US-B2 (½-star rating) | T077 `rating-widget.tsx` with ARIA slider | ✅ |
| US-B3 (Aux toggle) | T077 `aux-toggle.tsx` + T073 `auxed` bool persisted | ✅ |
| US-B4 (relisten + my history) | T073 relisten flag + T081 `my-history.tsx` (resolves L6-003) | ✅ |
| US-B5 (edit/delete diary entry) | T075 backend (PATCH+DELETE+restore) + T082 edit UI + T083 delete-confirmation + 8s undo toast | ✅ |
| US-E2 (chronological diary on profile) | T074 backend cursor pagination + T080 `/profile/[handle]` SSR + client `DiaryList` | ✅ |
| US-F1 (album-detail my history) | T081 `my-history.tsx` + `album/[id]/page.tsx` wires `<MyHistory>` | ✅ |

### New drift cluster: the `/profile/[handle]` ↔ `/@[handle]` route decision

The single dominant root cause for 4 of 5 NEW WARNs (L3-019, L4-014, L5-007, plus the parenthetical L3-018) is the Session 14 routing decision documented in implementation-log.md (line 220, 236):

> "Next.js cannot use `@<segment>` as a folder name (the `@` prefix is reserved for parallel routes). Going with `/profile/<handle>` for now; the `/@handle` SEO/sharing URL can land later via middleware rewrite."

This single decision affects:

| Artifact | Locations | Drift ID |
|----------|-----------|:--------:|
| plan.md | §1.2 (file tree), §7.1 (routing bullet), §11.3 (share URL), §16.5 (a11y page list) | L3-019 |
| tasks.md | T080 Paths, T093d Paths, T101 Paths | L4-014 / L5-007 |
| implementation-log.md | Session 14 references "plan §16" (wrong — §16 is testing) | L3-018 |

**Recommended inline resolution (single coordinated pass):**
1. plan.md — update 4 locations to cite `/profile/[handle]` as canonical; add a Handle-URL-Aliasing subsection noting the deferred middleware rewrite.
2. tasks.md — fix 3 stale Paths entries (T080, T093d, T101).
3. implementation-log.md — fix Session 14 "plan §16" → "plan §7.1 / §1.2" (3 occurrences).

### New finding: diary `albums` sidecar contract

L4-015: Session 14 added a server-side `albums: {[id]: AlbumCard}` sidecar to `GET /users/{handle}/diary` (one Album lookup per page, deduped on `_id`). 2 new integration tests lock the contract. But T074 description and plan.md §6 still describe only `{entries, next_cursor}`. Worth documenting now because §8 reviews-list will likely want the same sidecar pattern (or a parallel reviewers sidecar).

**Recommended inline resolution:**
1. tasks.md T074 — append response envelope `{entries, next_cursor, albums: {id: AlbumCard}}` with `AlbumCard = {id, mbid, title, artist_credit, release_year, cover_art_url}`.
2. plan.md §6 — add a brief note next to the `diary` row about the sidecar pattern.

### Carry-forward status snapshot

| ID | Description | Status | Disposition |
|----|-------------|:------:|-------------|
| L2-019 | SS-3 cohort-gate derivation underspecified (signup_cohort not defined) | **OPEN — narrowed in Run #8** (data-model.md now references `signup_cohort` via `visible_in_just_joined` default without defining it) | DEFER to invite-mechanic cluster sequencing (alongside L3-017 + L4-009) |
| L3-017 | Plan §12 missing SS-3 invite-landing ticker section | **OPEN** | DEFER (invite-mechanic cluster) |
| L4-009 | tasks.md missing invite-landing tasks | **OPEN** | DEFER (invite-mechanic cluster) |
| L4-010 | Plan §7.1 routing should enumerate `/search` and `/api/cover` | **RESOLVED** (inline added post-Run #7) | — |
| L4-011 | T072 references plan §17.5 (should be §11.4) | **RESOLVED** | — |
| L4-013 | Multiple task Paths under-specify helper files | OPEN-DEFERRED | Project-level convention note ("Paths = primary surfaces") still unwritten; Run #7 disposition stands |
| L6-002 | US-A1 auto-handle suggestions on collision unimplemented | **OPEN** | DEFER (low-priority polish; no first-launch collision impact) |
| L6-003 | US-F1 my-history section on album detail unimplemented | **RESOLVED** by T081 | — |

### All Drift Items

#### NEW this run

**L3-018** [INFO / cosmetic] implementation-log Session 14 cites "plan §16" — plan §16 is Testing Strategy, not Routing. Should cite §7.1 (routing enumeration) + §1.2 (file-tree). 3 occurrences.
*Proposed:* Edit `implementation-log.md` Session 14 occurrences of "plan §16" → "plan §7.1 / §1.2". Trivial.

**L3-019** [WARNING / structural] Plan §1.2, §7.1, §11.3, §16.5 still enumerate `/@[handle]/` as a Next.js route folder. Shipped code at `apps/web/src/app/(app)/profile/[handle]/page.tsx`.
*Proposed:* Update 4 plan.md locations to `/profile/[handle]` as canonical; add a follow-up note about a future middleware rewrite for `/@handle`.

**L4-014** [WARNING / structural] T080, T093d, T101 declare paths under `(app)/@[handle]/` — folder name Next.js can't create.
*Proposed:* Update T080, T093d, T101 Paths to `(app)/profile/[handle]/`. Single-line edit per task.

**L4-015** [WARNING / structural] GET `/users/{handle}/diary` now returns `{entries, next_cursor, albums: {id: AlbumCard}}` sidecar (Session 14 contract addition). T074 description and plan §6 don't mention it.
*Proposed:* Append response envelope to T074 description; add one-line note to plan §6 row for `diary` cross-referencing T074.

**L4-016** [INFO / structural] T082 description says "pre-fill the entry's current values" — Session 14 shipped rating/aux/visibility only (review-body edit deferred to §8 T086).
*Proposed:* One-line clarification to T082 Description: "pre-fill rating + aux + visibility; review-body edit lands with T086."

**L4-017** [INFO / cosmetic] T077 / T079 Paths don't list `recent-searches.tsx` (Session 13). Same pattern as L4-013.
*Proposed:* Same disposition as L4-013 (convention note). No edit required.

**L5-007** [WARNING / structural] T080/T093d/T101 declare `(app)/@[handle]/` — folder name Next.js can't create. Projection of L3-019/L4-014.
*Proposed:* Same fix as L4-014 (resolves both L4 and L5 simultaneously).

**L5-008** [INFO / cosmetic] T080's `components/diary/*` wildcard absorbs 3 of 4 new diary helpers; `recent-searches.tsx` on T079 is the only real omission.
*Proposed:* No edit required if wildcard convention holds; track under the L4-013 convention disposition.

**L5-009** [INFO / cosmetic] T083 Paths declares frontend-only; the backend restore endpoint (T075 ships it) isn't called out in any task that references restoration.
*Proposed:* One-line note in T075 description: "T075 also delivers `POST /diary/entries/{id}/restore`."

**L5-010** [INFO / cosmetic] T079 declares `album-prefill.tsx` — file never shipped (prefill logic inlined into `album-search.tsx` + `log-sheet/index.tsx`).
*Proposed:* T079 Paths — replace `album-prefill.tsx` with `recent-searches.tsx`.

**L5-011** [INFO / cosmetic] T082 declares `components/diary/edit-entry.tsx` — file never shipped (edit functionality reused `log-sheet/index.tsx` via `LogSheetSeed.edit`).
*Proposed:* T082 Paths — replace `edit-entry.tsx` with `log-sheet/index.tsx (edit-mode), diary/diary-entry-card.tsx (edit trigger)`.

**L7-016** [WARNING / structural] spec.md:138 has a broken anchor `[sync-report.md](./sync-report.md#drift-l2-003-story-count-claim-32-vs-enumerated-bodies-30)` — no DRIFT-L2-003 heading exists in the current sync-report.md (Run #1 was compacted).
*Proposed:* Drop the anchor; leave the bare `[sync-report.md](./sync-report.md)` link plus the parenthetical "sync-verify Run #1" prose.

#### Carry-forward (still open from prior runs)

- **L2-019** — INFO structural — SS-3 cohort gate references undefined `signup_cohort` field. DEFER (invite-mechanic cluster).
- **L3-017** — WARNING structural — plan.md §12 missing SS-3 invite-landing ticker section. DEFER (invite-mechanic cluster).
- **L4-009** — WARNING structural — tasks.md missing invite-landing tasks. DEFER (invite-mechanic cluster).
- **L4-013** — INFO cosmetic — multiple task Paths under-specify helper files. OPEN-DEFERRED under unwritten convention note.
- **L6-002** — WARNING structural — US-A1 auto-handle suggestions on collision unimplemented. DEFER (no first-launch impact).

#### Resolved this run

- **L4-010** — RESOLVED — plan §7.1 enumerates `/search` and `/api/cover/[size]/[mbid]` (lines 555–557, inline-applied post-Run #7).
- **L4-011** — RESOLVED — T072 reference to plan §11.4 (cover-art proxy section) verified intact.
- **L6-003** — RESOLVED — T081 shipped `apps/web/src/components/album-detail/my-history.tsx` and wired it into `app/(app)/album/[id]/page.tsx`.

### Proposed actions (inline + deferred)

**Applied inline this run (8 items + 1 missed-ref caught in post-edit sweep):**

| ID | File(s) | Change | Status |
|----|---------|--------|:------:|
| L3-018 | implementation-log.md | "plan §16" → "plan §1.2 / §7.1 / §11.3" in 3 Session 14 occurrences | ✅ APPLIED |
| L3-019 | plan.md | §1.2 file-tree, §7.1 routing bullet (+ new §7.1.1 Handle-URL-Aliasing subsection), §11.3 share URL, §16.5 a11y page list all repointed to `/profile/[handle]` | ✅ APPLIED |
| L4-014 / L5-007 | tasks.md | T080, T093d, T101 Paths: `(app)/@[handle]/` → `(app)/profile/[handle]/` | ✅ APPLIED |
| L4-015 | tasks.md + plan.md | T074 description: appended response envelope `{entries, next_cursor, albums}` + AlbumCard shape. plan.md §6 diary row: appended sidecar note + cross-ref to T074 | ✅ APPLIED |
| L4-016 | tasks.md | T082 description amended: "review-body editing lands with T086" + Refs aligned to actual shipped files | ✅ APPLIED |
| L5-009 | tasks.md | T075 description amended: explicitly enumerates `POST /diary/entries/{id}/restore` as part of T075's scope | ✅ APPLIED |
| L5-010 | tasks.md | T079 Paths: `album-prefill.tsx` → `recent-searches.tsx` | ✅ APPLIED |
| L5-011 | tasks.md | T082 Paths: `diary/edit-entry.tsx` → `log-sheet/index.tsx (edit-mode), diary/diary-entry-card.tsx (edit trigger), stores/ui.ts (LogSheetSeed.edit)` | ✅ APPLIED |
| L7-016 | spec.md | Broken `#drift-l2-003` anchor dropped; bare link + Run #1 prose preserved | ✅ APPLIED |
| (caught in sweep) | spec.md:350 | Frontend module table row `app/@[handle]` → `app/profile/[handle]` + middleware-rewrite cross-ref to plan §7.1.1 | ✅ APPLIED |

**Defer (6 items, existing dispositions stand):**

- L2-019, L3-017, L4-009, L4-013 — invite-mechanic cluster sequencing
- L4-017, L5-008, L5-009 — convention-note umbrella (track under L4-013)
- L6-002 — low-priority polish

### Sync History (updated)

| Run | Date | Layers | CRITICAL | WARN | INFO | Verdict | Disposition |
|-----|------|:------:|:--------:|:----:|:----:|---------|-------------|
| #1 | 2026-05-22 | 5/7 | 0 | 19 | 14 | CRITICAL_DRIFT_BUDGET_RULE | applied_split_with_override |
| #2 | 2026-05-22 PM | 7/7 | 0 | 7 | 5 | DRIFT_DETECTED | applied_split_with_override |
| #3 | 2026-05-22 (post-T002) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #4 | 2026-05-23 (early) | 7/7 | 0 | 6 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #5 | 2026-05-22 (late) | 7/7 | 0 | 7 | 4 | DRIFT_DETECTED | applied_split_with_override |
| #6 | 2026-05-23 (post-CR-002) | 7/7 | 0 | 7 | 6 | DRIFT_DETECTED | applied_split_with_override |
| #7 | 2026-05-23 (post-frontend-wave) | 7/7 | 0 | 4 | 4 | DRIFT_DETECTED | applied_split_with_override |
| **#8** | **2026-05-23 (post-§7-wedge-wave)** | **7/7** | **0** | **8** | **9** | **DRIFT_DETECTED** | **applied_split_with_override** (pending user confirmation) |

---

## Run #7 (2026-05-23, post-frontend-wave)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — **63/172** tasks complete (37%)
> Prior run: #6 (2026-05-23T04:45Z) — DRIFT_DETECTED, applied_split_with_override (3 items deferred to invite-mechanic cluster sequencing)
> Trigger: user invoked `/speckit.product-forge.sync-verify` with "Verify the new code" after Sessions 10–12 (§3 + §5 + §6 frontend completion)

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **4** | 2 NEW (L6-002, L6-003 — US-A1/US-F1 spec ↔ code gaps) + 2 carry-forward (L3-017, L4-009 — Run #6 deferred) |
| ℹ️ INFO | **4** | 3 NEW (L4-010 plan §7.1 routes catch-up; L4-011 T072 ref to wrong plan §; L4-013 task Paths under-specified) + 1 carry-forward (L2-019 cohort rule) |
| ✅ CLEAN | 3 layers fully clean (L1, L2, L7) | |

**Structural count:** 6 (over budget of 0) — 3 NEW + 3 carry-forward.
**Cosmetic count:** 2 (under budget of 20) — L4-012 instrumentation-client.ts + L4-013 helper-file paths.

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of Run #2/#3/#4/#5/#6 pattern. Override granted because (1) zero CRITICAL findings, (2) all 4 NEW WARN items are doc-catch-up after the frontend wave (no broken contracts), (3) Sessions 10–12 themselves landed cleanly across L1/L2/L5/L7, (4) the 2 NEW L6 spec-vs-code gaps are tracked refinements for the next §6/§7 wave rather than show-stoppers.

### Sessions 10–12 propagation audit (the headline check)

| Wave | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Session 10 (§3 core, T031–T036) | n/a | ✅ | ✅ | ⚠️ L4-013 (helper paths) | ✅ | n/a (foundation) | ✅ |
| Session 11 (§3 + §5 UI, T037–T040, T061, T062) | n/a | ✅ | ⚠️ L4-010 (plan §7.1) | ⚠️ L4-012/L4-013 | ✅ | ⚠️ L6-002 (US-A1 handle suggestions) | ✅ |
| Session 12 (§6 frontend, T070–T072) | n/a | ✅ | ⚠️ L4-010/L4-011 | ⚠️ L4-013 | ✅ | ⚠️ L6-003 (US-F1 my-history list) | ✅ |
| Operator-side .env.local fix (between S11 and S12) | n/a | n/a | n/a | n/a | ✅ | ✅ | n/a |

L5 forward (completed tasks → code) is CLEAN — all 37 expected files from T031–T040, T061, T062, T070–T072 exist on disk. L5 backward (code → tasks) is CLEAN — every modified file is inside a completed-task scope. L7 is CLEAN — zero broken links in new doc sections.

### NEW findings (Run #7)

#### DRIFT-L4-010 — plan.md §7.1 missing `/search` + `/api/cover` route enumeration
- **Layer:** 4 (forward, tasks → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `tasks.md` T071 (search page) + T072 (cover-art proxy) — both shipped
- **Target:** `plan.md` §7.1 Routing (Next.js App Router) — enumerates `/album/[id]`, `/@[handle]`, `/review/[id]`, `/`, `api/og/...` but not `/search` or `/api/cover/[size]/[mbid]`
- **Evidence:** plan.md:546–555 lists routes; absent are `/search` and `/api/cover/[size]/[mbid]/route.ts`.
- **Expected:** Add two bullets to §7.1: (a) `/search` SSR'd page with debounced client-side query; (b) `/api/cover/[size]/[mbid]` Route Handler proxying Cover Art Archive with `?fallback=...` redirect.
- **Proposed resolution:** Two-line addition to plan.md §7.1.
- **Auto-resolvable:** No.
- **Disposition:** APPLY INLINE — doc-only catch-up; low risk; isolates the routes for future readers.

#### DRIFT-L4-011 — T072 references plan §17.5 (Redis), not the cover-art proxy
- **Layer:** 4 (forward, tasks → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `tasks.md` T072 `Refs: plan §17.5; DM-2; CR-001`
- **Target:** `plan.md` §17.5 — currently titled "Redis" and describes Upstash. No cover-art-proxy subsection exists.
- **Evidence:** T072 ref string says "plan §17.5"; plan §17.5 is Redis hosting; cover-art proxy implementation pattern has no dedicated plan section. CAA usage IS described in `plan.md §1.2`, `§6 module table`, `§15.4 (CAA 404 rate metric)`, and `§17.4 (CAA hot-link policy)` — but no §X.Y for the Next.js proxy route handler.
- **Expected:** Either (a) add a `§11.3 Cover-art proxy (route handler)` subsection describing the `/api/cover/[size]/[mbid]` proxy pattern + CAA 404 fallback chain + 7-day cache headers, or (b) update T072's `Refs:` line to point to whichever existing plan section best fits (likely `§17.4 / §6.5`).
- **Proposed resolution:** Add `§11.3` subsection to plan.md and update T072 Refs.
- **Auto-resolvable:** No.
- **Disposition:** APPLY INLINE — minor doc structure addition.

#### DRIFT-L4-012 — T036 Paths missing `instrumentation-client.ts`
- **Layer:** 4 (forward, tasks → plan/Paths)
- **Severity:** ℹ️ INFO — **Category:** cosmetic
- **Source:** `tasks.md` T036 Paths list (`apps/web/src/lib/sentry.ts, apps/web/src/lib/posthog.ts, apps/web/instrumentation.ts`)
- **Target:** Actual code includes `apps/web/instrumentation-client.ts` (required by @sentry/nextjs v8+ for browser-runtime init).
- **Evidence:** File exists; not in T036 Paths.
- **Expected:** T036 Paths should add `apps/web/instrumentation-client.ts` for completeness.
- **Proposed resolution:** Append to T036 Paths line.
- **Auto-resolvable:** No (per Step 3A — task descriptions are structural).
- **Disposition:** APPLY INLINE — single-line update.

#### DRIFT-L4-013 — Multiple task Paths under-specified vs actual shipped infrastructure
- **Layer:** 4 (forward, tasks → code)
- **Severity:** ℹ️ INFO — **Category:** cosmetic (no contract change; just under-enumeration)
- **Source:** Various tasks (T037, T038, T039, T070, T071, T036, T033)
- **Target:** `tasks.md` Paths lines for each
- **Evidence:** Shipped infrastructure files not in any task's declared Paths:
  - `apps/web/src/components/ui/label.tsx` (T038 — needed by Form composition, missing from T032 scaffold)
  - `apps/web/src/components/nav/log-fab.tsx` (T037 — companion to bottom-tabs)
  - `apps/web/src/components/nav/onboarding-progress.tsx` (T039 — companion to onboarding layout)
  - `apps/web/src/components/health-check.tsx` (T033 — smoke surface)
  - `apps/web/src/lib/album-types.ts` (T070 — shared TypeScript types)
  - `apps/web/src/lib/api-server.ts` (T070 — `server-only` fetch helper)
  - `apps/web/src/lib/auth-schemas.ts` (T038 — Zod schemas)
  - `apps/web/src/lib/posthog-server.ts` (T036 — server-only PostHog client, split for webpack bundling fix)
- **Expected:** Each task's Paths list should be updated to reflect actual shipped files (or accept that ancillary helpers are out-of-scope for Paths).
- **Proposed resolution:** Add a project-level convention note clarifying that Paths is "primary surfaces only", not "every file touched". This bypasses needing to amend every task.
- **Auto-resolvable:** No.
- **Disposition:** DEFER — a convention note is the right fix but it's not a per-task amendment. Track in implementation-log as a process improvement.

#### DRIFT-L6-002 — US-A1 AC "auto-handle suggestions on collision" not implemented
- **Layer:** 6 (forward, spec → code)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `spec.md:145` US-A1 AC: *"email + password + handle (no music-service OAuth shortcut); auto-handle suggestions on collision."*
- **Target:** `apps/web/src/app/(auth)/signup/signup-form.tsx` — on backend 422 returns generic error message; doesn't render suggested-alternate handles.
- **Evidence:** signup-form's `setApiFormErrors` maps backend errors to field-level errors. If backend returns `{detail: [{msg: "handle taken", loc: ["body", "handle"]}]}`, the form shows the msg. But there's no separate "suggested handles" rendering path.
- **Expected:** Either backend `/api/v1/auth/signup` returns 422 with a `suggested_handles: [...]` extension, OR backend exposes `GET /api/v1/users/handle-suggestions?email=...` that frontend calls on collision. Frontend then renders 3 suggested chips below the handle field.
- **Actual:** Neither. Backend currently returns a plain error; frontend has no UI affordance for suggestions.
- **Proposed resolution:** Two-part:
  1. Backend: extend signup endpoint error response (or add a sibling endpoint) to return suggestions.
  2. Frontend: signup-form renders 3 suggested chips on collision; clicking a chip pre-fills the handle field.
- **Auto-resolvable:** No.
- **Disposition:** DEFER to a §5 polish task or a §11 onboarding task. Tracked as a spec-acceptance gap; not critical until first user actually hits a collision.

#### DRIFT-L6-003 — US-F1 AC "my history" section absent from album-detail page
- **Layer:** 6 (forward, spec → code)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `spec.md:190` US-F1 AC: *"SSR; cover, metadata, tracklist, **my history**, friends' ratings + Aux'd, public reviews list..."*
- **Target:** `apps/web/src/app/(app)/album/[id]/page.tsx` + `components/album-detail/*` — renders cover, metadata, tracklist, friends, public reviews, edition selector, OG meta. **Does NOT render a "my history" section.** Only the latest entry is shown via `<AlbumActions>` ("You rated this 4★ · Aux'd").
- **Evidence:** Backend response includes `my_history: DiaryRow[]` (up to `_MY_HISTORY_LIMIT` entries). The page consumes `my_history[0]` for the latest-entry chip but doesn't render the full history list.
- **Expected:** A `<MyHistorySection>` component rendering all `my_history` entries (logged_at + rating + auxed flag + visibility) as a list when `my_history.length > 1`. Single entry continues to show as the chip in AlbumActions.
- **Proposed resolution:** Add `components/album-detail/my-history-section.tsx` (small component, ~30 LOC) + render in `album/[id]/page.tsx` when `my_history.length > 1`.
- **Auto-resolvable:** No.
- **Disposition:** APPLY in next §7 wave alongside the log-sheet (which will be the primary way users add diary entries — having the history rendered there closes the loop visually).

### Carry-forward (Run #6 — unchanged, still deferred per Run #6's disposition)

- **DRIFT-L3-017** — plan.md §12 missing SS-3 invite-landing ticker logic. Still deferred to invite-mechanic cluster sequencing.
- **DRIFT-L4-009** — tasks.md missing invite-landing tasks. Still deferred.
- **DRIFT-L2-019** — SS-3 cohort-gate derivation underspecified. Still deferred.

### Recurring advisory (unchanged from Runs #2–#6)

11 items: L1-001, L1-002, L2-004/005, L2-006, L2-009, L3-009, L3-010, L4-005, L7-004..008 (5 items), L7-013. See Run #6 for descriptions.

### Next action

User to disposition the 4 NEW WARN/INFO items. Recommended order:
1. **L4-010** + **L4-011** apply inline now — small doc adds to plan.md §7.1 (+ new §11.4 cover-art-proxy subsection).
2. **L4-012** apply inline now — single-line T036 Paths update.
3. **L6-003** defer to next §7 wave (alongside log-sheet) — natural sequencing.
4. **L6-002** defer to a §5 polish task — handle suggestions are nice-to-have, not first-launch blockers.
5. **L4-013** convention note (defer; track as process improvement, not per-task amendment).
6. Carry-forward Run #6 items remain deferred to invite-mechanic cluster.

### Applied resolutions (Run #7 — user-approved inline)

| ID | File(s) touched | Change |
|---|---|---|
| **L4-010** | `plan.md` §7.1 | Added two bullets enumerating `/search` (debounced TanStack Query client page) and `/api/cover/[size]/[mbid]` (CAA Route Handler), with cross-refs to §11.2/§11.4. |
| **L4-011** | `plan.md` §11.4 (new) + `tasks.md` T072 | Added new §11.4 "Cover-art proxy (Next.js Route Handler)" — full subsection covering request shape, behavior, param-naming note, consumer pattern, observability. Updated T072 Refs from `plan §17.5` → `plan §11.4`; renamed Paths param `[albumId]` → `[mbid]`; documented rename rationale in description. |
| **L4-012** | `tasks.md` T036 | Appended `apps/web/instrumentation-client.ts` to T036 Paths (required by @sentry/nextjs v8+ for browser-runtime init). |

**Deferred (per user disposition):**
- **L4-013** — convention note about Paths being "primary surfaces only" — tracked here as a process improvement, not a per-task amendment.
- **L6-002** — US-A1 auto-handle suggestions → defer to §5 polish or §11 onboarding task. Needs backend coordination first.
- **L6-003** — US-F1 my-history section → defer to next §7 wave (will land alongside the log-sheet — natural sequencing since the log-sheet writes diary entries that populate my_history).
- **Run #6 carry-forward** (L3-017, L4-009, L2-019) — unchanged; tied to invite-mechanic cluster sequencing.

**Gate:** override granted; verdict `applied_split_with_override`. Phase 6 unblocked.

---

## Run #6 (2026-05-23, post-CR-002)

> Layers checked: 7/7
> Phase: 6 (Implementation, in progress) — 48/170 tasks complete (164 active + 8 deferred after CR-002 added T093a/b)
> Prior run: #5 (2026-05-23T03:00Z) — DRIFT_DETECTED, applied_split_with_override
> Trigger: CR-002 (Phase 2 decision review pass) filed; user invoked `/speckit.product-forge.sync-verify`

### Summary

| Severity | Count | Notes |
|----------|-------|-------|
| ❌ CRITICAL | **0** | |
| ⚠️ WARNING | **2** | Both are L3/L4 projections of the same single gap (SS-3 invite-mechanic not yet sequenced) |
| ℹ️ INFO | **1** | SS-3 cohort-derivation rule underspecified |
| ✅ CLEAN | 5/7 layers (L1, L2, L5, L6, L7) | |

**Structural:** 3 (over budget of 0) — all three express the same SS-3-cluster-pending-sequencing gap from different layer-projections.
**Cosmetic:** 0 (under budget of 20).

**Verdict:** **DRIFT_DETECTED**

**Disposition:** **applied_split_with_override** — carry-forward of the Run #2/#3/#4/#5 pattern. Override granted because (1) zero CRITICAL findings, (2) the 3 NEW items are pre-acknowledged in CR-002 under `tasks_followup_pending_cluster: ["invite-landing /i/{handle} ticker (SS-3) — cluster not yet sequenced in tasks.md"]`, and (3) CR-002 itself was applied cleanly across 14 artifacts with full forward propagation everywhere else.

### CR-002 application audit

| CR-002 Change | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Q3 rationale softening | ✅ | ✅ | ✅ | n/a | n/a | n/a | ✅ |
| Differentiator row softening | ✅ | ✅ | ✅ | n/a | n/a | n/a | ✅ |
| NT-2 three-hero carousel | n/a | ✅ | ✅ | ✅ | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| SS-3 invite ticker + opt-in flag | n/a | ✅ | ⚠️ L3-017 | ⚠️ L4-009 | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| UJ-3 `/review/:id` route only | n/a | ✅ | ✅ | ✅ | ⏸ unbuilt | ⏸ unbuilt | ✅ |
| UJ-4 v2 roadmap note | n/a | ✅ | n/a | n/a | n/a | n/a | ✅ |

Only the SS-3 column has open drift — same single gap viewed from two layers + one internal-consistency note. The CR-002 itself pre-flagged this, so Run #6 completes its job: surface the deliberate gap as a tracked finding for the next cluster-sequencing pass.

### NEW findings (Run #6)

#### DRIFT-L3-017 — plan.md §12 missing SS-3 invite-landing ticker logic
- **Layer:** 3 (forward, spec/product-spec → plan)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `product-spec/seeding-strategy.md:74-78` (Mechanics block, CR-002)
- **Target:** `plan.md` §12 Seeding-Strategy Backend (no §12.4 / §12.5 for invite-mechanic)
- **Evidence:** seeding-strategy.md describes the "Recently joined" ticker with 15-min cache + cohort-gate defaults; plan.md §12 only covers CriticSeed roster + pre-checked card algorithm.
- **Expected:** Plan.md §12.4 (or §12.5) subsection with query (`User.find({visible_in_just_joined: True}).sort(handle_created_at desc).limit(3)`), 15-min Redis cache key shape, and cohort-gate logic for the default flag value on signup.
- **Proposed resolution:** Add §12.4 when invite-mechanic cluster is sequenced. Mirror §12.2 algorithm-block style.
- **Auto-resolvable:** No.
- **Disposition:** DEFERRED — pre-flagged in CR-002.

#### DRIFT-L4-009 — tasks.md missing invite-landing + visible_in_just_joined task(s)
- **Layer:** 4 (forward, plan → tasks)
- **Severity:** ⚠️ WARNING — **Category:** structural
- **Source:** `product-spec/data-model.md:53` (`User.visible_in_just_joined` field, CR-002) + `product-spec/seeding-strategy.md:74-78`
- **Target:** `tasks.md` (no row matches)
- **Expected:** Minimum 3 tasks when the cluster is sequenced — (a) backend `GET /api/v1/seeds/just-joined` endpoint + 15-min cache + Field migration on User; (b) frontend landing-page ticker component + onboarding-step-1 ticker placement; (c) settings task — Settings → Privacy toggle for `visible_in_just_joined`.
- **Proposed resolution:** Insert when the invite-mechanic cluster (likely §11/§12 backend wave) is sequenced. Task IDs reserved-but-not-allocated.
- **Auto-resolvable:** No.
- **Disposition:** DEFERRED — pre-flagged in CR-002 (`tasks_followup_pending_cluster`).

#### DRIFT-L2-019 — SS-3 cohort-gate derivation underspecified
- **Layer:** 2 (internal — seeding-strategy.md ↔ data-model.md)
- **Severity:** ℹ️ INFO — **Category:** structural
- **Source:** seeding-strategy.md SS-3 row references "L-12..L-1 cohorts"
- **Target:** data-model.md User document — no `signup_cohort` field; no derivation rule
- **Expected:** Either (a) add `User.signup_cohort` field, OR (b) explicit "derive from `handle_created_at` against a `LAUNCH_DATE` constant" rule.
- **Proposed resolution:** Add a one-line derivation rule to data-model.md User block AND seeding-strategy.md SS-3 row. Recommended: derivation from `handle_created_at` against a `LAUNCH_DATE` settings constant — avoids storing redundant data and matches the Phase 5 pattern.
- **Auto-resolvable:** No.
- **Disposition:** DEFER to invite-mechanic cluster pass alongside L3-017 + L4-009.

### Recurring advisory (carry-forward from Run #5 — unchanged)

| ID | Description | Last seen |
|---|---|---|
| DRIFT-L1-001 | W1 activation narrowing | Run #5 |
| DRIFT-L1-002 | Apple Music re-eval threshold drift 15% → 30% (deferred since Run #2) | Run #5 |
| DRIFT-L2-004 / L2-005 | FR trace tags | Run #5 |
| DRIFT-L2-006 | Cluster name enrichment | Run #5 |
| DRIFT-L2-009 | Entity inventory ReviewLike row | Run #5 |
| DRIFT-L3-009 | `/critics` route in plan, no spec backing | Run #5 |
| DRIFT-L3-010 | Handle collision suggestion algorithm incomplete | Run #5 |
| DRIFT-L4-005 | 4 satellite collections in product-spec/data-model.md inventory | Run #5 |
| DRIFT-L7-004..008 | 5 phase-digest orphans (convention class) | Run #5 |
| DRIFT-L7-013 | implementation-log.md orphan (convention class) | Run #5 |

### Next action (Run #6 → Run #7)

Continue Phase 6 implementation. Re-run sync-verify between Phase 6B (code-review) and Phase 7 (full verify). When the invite-mechanic cluster gets sequenced (likely alongside §11/§12 backend wave or the onboarding wave), the three deferred items (DRIFT-L3-017 + DRIFT-L4-009 + DRIFT-L2-019) should be resolved together in a single coherent cluster pass.

---

## Run #5 (2026-05-22, late)

> Phase: 6 (Implementation, in progress) — 42/170 tasks complete
> Drift budget: cosmetic ≤ 20, structural = 0
> **Trigger:** post-§6 Albums + Search backend wave (commit `3e8a602` + shared-types regen `bbd1f4e`) + post-deploy partial-filter fix (commit `66f0403`). First run where Layer 6 (spec ↔ code backward) is meaningful — §6 added the first end-to-end product surfaces (album-detail endpoint + search endpoint).
> **Layers checked:** 7/7 (1, 2, 3, 4, 5, 6, 7). **Skipped:** none.
> **Focus per user prompt:** structural-drift detection on all layers with Layer 6 elevated as the headline; verify Run #4 dispositions still hold; check for §6 fallout the user pre-suspects (partial-filter not in implementation-log; artist_credit data-shape gap; Atlas Search operator follow-up; data-model.md `candidate` semantics).

### Summary

| Severity | Count | Net of recurring | New this run |
|----------|-------|-----------------:|-------------:|
| CRITICAL | 0 | — | — |
| WARNING | 1 | 0 recurring + 1 new | L3-015 (plan.md §11.2.1 report-missing-album URL diverges from code + tasks.md) |
| INFO | 17 | 11 recurring + 6 new | L2-017, L2-018, L3-016, L4-008, L5-006, L7-015 |
| CLEAN | Layer 6 substantially clean (forward-only paths, no backward drift); Run #4 dispositions all holding | — | — |

**Verdict: DRIFT_DETECTED (NOT CRITICAL).** No CRITICAL finding. 1 new WARNING + 6 new INFOs are concentrated on the boundaries §6 opened — and on a Run #4 finding (L4-005 satellite-collection inventory) that the §6 wave touched but didn't fully reconcile. The strict `structural: 0` budget trips again on 7 structural items (1 WARN + 6 INFO); the picture is narrower than Run #4's 7-structural baseline once recurring advisory is excluded.

Structural count: **7** (1 new WARN + 6 new INFO). Cosmetic count: **0**. Strict `structural: 0` budget trips.

### Run #4 disposition — VERIFIED RESOLVED

All 7 Run #4 items applied per commit `aa98618` (sync-fix-run-4 doc propagation):

| Run #4 finding | Verified at |
|----------------|-------------|
| L2-014 (FR-033 propagation) | product-spec/product-spec.md:174 (FR-033 row added); product-spec/README.md:62 ("23 functional requirements active … FR-033"); tasks.md:522 T053a Refs line includes `FR-033` |
| L3-013 (plan §5.1 Protocol names) | plan.md:455-482 — Protocol now reads `get_album_by_mbid` + `get_album_by_external_id`; cover-art as field; `provider_id` dropped; `get_user_library` out of MVP. plan.md:538 services-table row aligned. |
| L3-014 (plan §5.2 rate-limit symbol) | plan.md:487 — "enforced in-class via an `asyncio.Lock` + `time.monotonic()` pacing pair". plan.md:489 — Discogs graceful-disabled-when-token-unset. |
| L4-006 (`discogs_id` → `discogs_release_id`) | product-spec/data-model.md:88, 95, 99, 403 — all `discogs_release_id`. tasks.md:584 T063 description uses `discogs_release_id`. |
| L2-015 (wireframe 01 label) | spec.md:203-204 — "Follow-Critics screen (the new onboarding activation step)". |
| L2-016 (entity count narrative) | spec.md:355-357 ("14 active at MVP") + spec.md:582-583 (mirror). |
| L4-007 (tasks.md FR math) | tasks.md:65 + tasks.md:1588 — "23 active FRs … 28 base (27 originals + FR-033) − 5 deferred". |

### §6 Albums + Search wave — VERIFIED LANDED

| Task | Code/test landing | Notes |
|------|-------------------|-------|
| T063 | `modules/albums/identity.py` + `modules/albums/errors.py` + `Album.candidate` field + `tests/unit/test_albums_identity.py` (8 tests) | `resolve_identity(mbid?, discogs_release_id?, mb_provider, discogs_provider)` → Album; MBID-first; Discogs fallback materialises with `candidate=True`. |
| T064 | `modules/albums/workers.py:refresh_stale_album_metadata` + `workers/main.py` cron registration | arq cron daily 04:00 UTC; cap 100/run; provider shared across runs via `_on_startup`. Code path is `modules/albums/workers.py`, not `workers/album_cache_refresh.py` per tasks.md Paths — inline-noted on tasks.md `[x]` line per locked decision #5. |
| T065 | `modules/albums/workers.py:reconcile_candidate_albums` | arq cron weekly Sun 03:00 UTC; fuzzy artist+title match against MB; threshold 0.8; promotes matched candidates to `MUSICBRAINZ` source. |
| T066 | `modules/albums/editions.py` + `tests/unit/test_albums_editions.py` (11 tests) | `get_editions` + `get_canonical_edition` (earliest year + longest tracklist tiebreak) + `aggregate_ratings` across editions. Known MVP limitation: `Album.mbid` unique constraint collapses editions to 1 row per release-group — documented in module docstring + flagged as follow-up CR. |
| T067 | `modules/albums/routes.py` + `routers/v1.py` mount + `tests/integration/test_album_detail_endpoint.py` (6 tests) | `GET /api/v1/albums/{album_id}` returns `{album, editions, aggregate, my_history, friends, public_reviews}`. Visibility filtered via `can_read_with_relation` adapters; bulk relation resolver minimises Mongo round-trips. |
| T068 | `migrations/atlas_search/albums_index.json` extended + `migrations/README.md` + `tests/unit/test_albums_atlas_index.py` (5 tests) | `lucene.standard` analyzer + edgeNgram autocomplete (2-8) + `foldDiacritics` + `rating_count` field + `scoreDetails.popularity = log1p(rating_count)`. Operator follow-up: apply updated index to dev Atlas cluster via UI/atlas-cli. |
| T069 | `modules/search/routes.py` + `modules/search/service.py` + `routers/v1.py` mount + `tests/integration/test_search_endpoint.py` (7 tests) | `GET /api/v1/search?q=...&type=album&limit=N`. Three-tier: Atlas $search (graceful-degrades on mongomock) → MB → Discogs. Dedupe by mbid OR casefolded `(title, artist)`. Empty result returns `{report_missing_album_url: "/api/v1/reports/missing-album"}` hint pointing at T053a stub. |
| shared-types regen | `packages/shared-types/src/api.ts` (commit `bbd1f4e`) | OpenAPI codegen ran; api.ts updated for the 2 new endpoints; tsc strict clean. |
| partial-filter fix | `Album.Settings.indexes` migrated from `sparse=True` → `partialFilterExpression={field: {$exists: True, $ne: None}}` (commit `66f0403`) | Post-deploy production bug: Pydantic serialises `None` → BSON `null`, sparse-unique indexes both null values, second null insert collides. Fix excludes `null` from the unique constraint. Conftest drops the two indexes post-`init_beanie` since mongomock-motor doesn't honor partial filters. |

### Layer-by-layer

| Layer | Pair | Verdict | Notes |
|-------|------|---------|-------|
| 1 | research ↔ product-spec | recurring only | L1-001 + L1-002 still carried unchanged. No new drift; §6 wave did not touch the research layer. |
| 2 | product-spec ↔ spec.md | **2 NEW INFO** | L2-017 (spec.md "18 active notification types" stale post-CR-001 — should be 14 active per notification-taxonomy + product-spec/README); L2-018 (`Album.candidate` field semantics drift — data-model.md says "candidate album record flagged for admin merge" but code/T063 use it for the Discogs-fallback path with automated T065 reconciliation). Recurring INFO L2-004/005/006/009 unchanged. |
| 3 | spec.md ↔ plan.md | **1 NEW WARN + 1 NEW INFO** | L3-015 (plan §11.2.1 says `POST /api/search/report-missing` but code search-endpoint hint + tasks.md T053a both use `/api/v1/reports/missing-album`); L3-016 (plan §3.1 `albums` row says "`mbid` unique sparse · `discogs_release_id` unique sparse" but code uses `partialFilterExpression` per commit `66f0403` — sparse was the production bug). Recurring INFO L3-009/010 unchanged. |
| 4 | plan.md ↔ tasks.md | **1 NEW INFO** | L4-008 — recurring L4-005 narrowed (the §6 wave's `albums_text_search` Atlas index + `migrations/README.md` are new artifacts neither plan §3.1 inventory nor product-spec/data-model.md indexes table acknowledge). Recurring L4-005 (4 satellite collections inventory) unchanged. |
| 5 | tasks.md ↔ code | **1 NEW INFO** | L5-006 — partial-filter fix (commit `66f0403`) not captured in `implementation-log.md`. Session 8 entry stops at 400/400 tests + the lingering Operator-follow-up bullet for the Atlas index; the post-deploy index migration + conftest drop pattern + bump to 401/401 tests has no Session 8.5 entry. The commit body explains it; the implementation log does not. Also: tasks.md T067/T068/T069 Paths lines reference `tests/integration/test_album_detail.py` / `docs/atlas-search-setup.md` / `tests/integration/test_search.py` but the actual files are `test_album_detail_endpoint.py` / `apps/api/migrations/README.md` / `test_search_endpoint.py` — same path-divergence class as §4 (locked decision #5) but here NOT inline-noted on the `[x]` lines. |
| 6 | spec.md ↔ code | **1 NEW INFO** | First meaningful Layer 6 sweep. L6-001 (response shape advisory) — US-F1 AC mentions "SSR; cover, metadata, tracklist, my history, friends' ratings + Aux'd, public reviews list (sortable), Log + Up Next CTAs, OG meta. Edition selector chip". Backend T067 covers album/tracklist/my_history/friends/public_reviews/editions/aggregate cleanly. The frontend-bound concerns (SSR, OG meta, sort selector, Log/Up Next CTAs) are deferred to T070+ as expected — not drift, but worth marking the surface dependency explicitly. US-F2 AC ("Atlas Search (cached MusicBrainz subset) + live MusicBrainz lookup on cache-miss + Discogs fallback for obscure pressings; ≥3 chars + 200ms debounce; 'Report missing album' link on empty result") is satisfied by T069 (Atlas → MB → Discogs fallback merge with materialise + dedupe + report-missing hint on empty). The ≥3 chars + 200ms debounce are frontend concerns (T071+); the route accepts `q.min_length=1` for forward-compat. FR-005 + FR-010 traceability: clean. FR-033 traceability: spec.md → tasks.md T053a (Refs FR-005;FR-033) → search route's report-missing URL hint (T053a stub) — chain is consistent. **Backward direction substantially clean. No regression-class drift detected.** |
| 7 | cross-link integrity | **1 NEW INFO** | L7-015 — `migrations/README.md` (new this wave) is not indexed by any other markdown doc in the feature folder, mirrors the L7-013 / L7-004..008 phase-digest-orphan convention class. Recurring 5 phase-digest orphans + L7-013 unchanged. |

---

## New findings (Run #5)

### DRIFT-L3-015 — plan §11.2.1 report-missing-album URL diverges from code + tasks.md

| Field | Value |
|-------|-------|
| Layer | 3 (plan.md ↔ code; also plan.md ↔ tasks.md) |
| Direction | Forward (plan → code/tasks) |
| Severity | WARNING |
| Category | structural |
| Source | `plan.md:766` — "Tapping submits a `POST /api/search/report-missing` request that creates a `reports` document with `target_type: 'missing_album'`, `target_id: query_string`, and submitter user id." |
| Target | `apps/api/src/auxd_api/modules/search/routes.py:48` — `_REPORT_MISSING_ALBUM_URL = "/api/v1/reports/missing-album"`; `tasks.md:523` T053a Description — "`POST /api/v1/reports/missing-album` accepts `query` …" |
| Authoritative | `/api/v1/reports/missing-album` per code (currently in the search response hint) + tasks.md T053a (the future endpoint task). |
| Actual | plan.md §11.2.1 narrative still uses the unversioned `/api/search/report-missing` form, which (a) lives outside `/api/v1` (inconsistent with the rest of the API surface) and (b) is conceptually `reports/missing-album` (Report-entity-owned), not `search/report-missing` (search-module-owned). The §13 reading list reference + the §11.2.1 elevation note + the CR-001 changelog row all repeat this stale path. |
| Cross-check | `tasks.md:1588` coverage matrix and `tasks.md:523` T053a path agree on `/api/v1/reports/missing-album`. The search route's `_REPORT_MISSING_ALBUM_URL` constant is the live shape exposed via OpenAPI today. |
| Proposed resolution | Update plan.md:766 to `POST /api/v1/reports/missing-album` (matches code + tasks.md T053a). Optionally also rename the `target_id` semantics: plan currently says "`target_id: query_string`" but T053a stores `query`/`artist`/`title`/`release_year` as separate fields on the Report payload — recommend "`target_id: query_string; additional structured hints in detail/payload`". |

### DRIFT-L2-017 — spec.md "18 active notification types" stale post-CR-001

| Field | Value |
|-------|-------|
| Layer | 2 (spec.md ↔ product-spec/notification-taxonomy.md) |
| Direction | Backward (taxonomy → spec.md narrative) |
| Severity | INFO |
| Category | structural |
| Source | `spec.md:195` (US-G3 AC: "18 active notification types with per-channel toggles"); `spec.md:371` (§7 data-model entity narrative: "Notification, NotificationPreferences — 18 active types"); `spec.md:584` (§13 reading list: "18 active notification types with defaults") |
| Target | `product-spec/notification-taxonomy.md` — 14 active rows (N-001..N-008, N-012..N-017); reserved-gap IDs N-009/N-010/N-011/N-018/N-019/N-020; `product-spec/README.md:64` correctly says "14 notification types active"; `product-spec/user-stories.md:289-290` correctly references "every active notification type from notification-taxonomy.md" + lists reserved-gap IDs explicitly. |
| Actual | spec.md narrative claims 18 active across three locations; the canonical count is 14 active + 6 reserved-gap = 20 IDs allocated. The "18 active" was a v1.3 number reduced by CR-001 (which moved N-009/N-010/N-011 + N-018 to deferred-to-v2 reserved-gap status). README.md already reflects the corrected count; spec.md never caught up. |
| Proposed resolution | Update 3 spec.md locations from "18 active notification types" to "14 active notification types (N-009/N-010/N-011 + N-018 deferred to v2 per CR-001; N-019/N-020 deferred with R3 Lists deferral; IDs preserved as reserved-gap)". |

### DRIFT-L2-018 — `Album.candidate` field semantics diverge between data-model.md and code/T063

| Field | Value |
|-------|-------|
| Layer | 2 (product-spec/data-model.md ↔ code/tasks T063) |
| Direction | Backward (code → data-model.md) |
| Severity | INFO |
| Category | structural (field-meaning) |
| Source | `product-spec/data-model.md:355-359` — "Album identity normalization (load-bearing) … 3. Else (rare — e.g., a user manually typed an album title with no provider hit) → create a 'candidate' album record flagged for **admin merge**." |
| Target | `apps/api/src/auxd_api/modules/albums/models.py:199-204` — "`candidate` marks Discogs-sourced rows that still need MBID reconciliation by the T065 worker"; `apps/api/src/auxd_api/modules/albums/identity.py:122-137` — Discogs path materialises with `candidate=True`; `apps/api/src/auxd_api/modules/albums/workers.py:174-237` — `reconcile_candidate_albums` automatically promotes candidates via fuzzy MBID match (no admin step). Also `product-spec/user-stories.md:249` correctly says "If MusicBrainz MBID is not yet available, the album is created as a `candidate` record (flagged for MBID reconciliation when MusicBrainz catches up)". |
| Actual | data-model.md says "candidate" means "manually-entered album, flagged for admin merge". Code + T063/T065 + S-F1 AC say "candidate" means "Discogs-sourced album awaiting automated MBID reconciliation by the T065 weekly worker". The data-model narrative case (rare manual entry, no provider hit) doesn't currently exist in code at all — manual album creation lands via T053a's future Report flow, not via `resolve_identity`. |
| Proposed resolution | Update data-model.md §"Album identity normalization" step 3 to: "Else if Discogs ID is present → materialise `Album(candidate=True, source=DISCOGS)` to be reconciled by the weekly T065 MBID-reconciliation worker." Also add a brief mention of the new `Album.candidate: bool` field to the Album entity sketch (line 89-114). |

### DRIFT-L3-016 — plan §3.1 `albums` index spec says "unique sparse" but code uses partialFilterExpression

| Field | Value |
|-------|-------|
| Layer | 3 (plan.md ↔ code) + Layer 2 (product-spec/data-model.md ↔ code) |
| Direction | Forward (plan → code) — and post-fix, backward (code → plan) |
| Severity | INFO |
| Category | structural (index-shape) |
| Source | `plan.md:264` — "`albums` … `mbid` unique sparse · `discogs_release_id` unique sparse · Atlas Search index on `title + artist_credit + artists.name`". Same wording in `product-spec/data-model.md:402-404`. |
| Target | `apps/api/src/auxd_api/modules/albums/models.py:215-237` — both indexes now use `partialFilterExpression={field: {$exists: True, $ne: None}}` per commit `66f0403`. |
| Actual | The original plan + data-model wording is the bug that was caught in prod: sparse-unique still indexes null values (because Pydantic emits `None` → BSON `null`, which is *present*, not *missing*), and the second null insert collides on the unique constraint. The fix uses `partialFilterExpression` to exclude both missing and null. The plan + data-model wording reflects the *pre-fix* design intent; code now reflects the *post-fix* shape. |
| Cross-check | Conftest at `apps/api/tests/conftest.py:43-61` drops both indexes post-`init_beanie` because mongomock-motor doesn't honor `partialFilterExpression` — a real-MongoDB testcontainers smoke test is the documented mitigation (per commit `66f0403` body). |
| Proposed resolution | Update plan.md:264 + product-spec/data-model.md:402-403 from "unique sparse" to "unique partial-filter (`{$exists: true, $ne: null}`) — sparse was insufficient because Pydantic serialises `None` to BSON `null`". The decision row should also be captured in `product-spec/decision-log.md` as DM-6 ("Album identity index shape — partialFilter not sparse") for v2 forward-compat. |

### DRIFT-L4-008 — §6 wave artifacts not in plan §3.1 / data-model.md inventory tables

| Field | Value |
|-------|-------|
| Layer | 4 (plan.md ↔ tasks.md) + Layer 2 (product-spec/data-model.md) |
| Direction | Forward (tasks/code → plan + data-model) |
| Severity | INFO |
| Category | structural (inventory completeness) |
| Source | `apps/api/migrations/atlas_search/albums_index.json` (T068, extended this wave); `apps/api/migrations/README.md` (T068, NEW this wave); `Album.candidate: bool` field (T063, NEW this wave) |
| Target | `plan.md:264` (`albums` indexes row); `product-spec/data-model.md:89-114` (Album sketch); `product-spec/data-model.md:395-419` (Indexes table) |
| Actual | The new `Album.candidate` field is invisible to data-model.md's Album sketch. The Atlas Search index `albums_text_search` has a `rating_count` field + `scoreDetails.popularity = log1p(rating_count)` block — neither shows up in plan.md or data-model.md's index narrative. plan.md §3.1 still says "Atlas Search index on `title + artist_credit + artists.name`" — accurate as far as it goes, but understates the actual shape now in production. |
| Cross-check | Narrows the recurring L4-005 finding ("4 satellite collections missing from product-spec/data-model.md inventory") rather than replacing it — L4-005 still tracks FollowRequest + ReviewEditHistory + FailedEmail; L4-008 tracks the §6 wave artifacts. |
| Proposed resolution | Add `Album.candidate: bool` to the Album sketch in data-model.md:89-114. Update plan.md:264's `albums` indexes row to mention the popularity-boost index field. Optionally add a "Migration artifacts" subsection to plan §3 or §11 enumerating `migrations/atlas_search/albums_index.json` + `migrations/README.md` so future readers can find them from the plan. |

### DRIFT-L5-006 — partial-filter fix (commit `66f0403`) not in implementation-log.md Session 8

| Field | Value |
|-------|-------|
| Layer | 5 (tasks.md/code ↔ implementation-log.md) |
| Direction | Backward (code commit → log) |
| Severity | INFO |
| Category | structural (audit trail) |
| Source | commit `66f0403` body — "Found in prod after §6 wave deploy: GET /api/v1/search?q=... → HTTP 500 with DuplicateKeyError … Fix: change both mbid_1 and discogs_release_id_1 unique indexes from `sparse=True` to `partialFilterExpression={field: {$exists: true, $ne: null}}`." |
| Target | `features/001-auxd-mvp/implementation-log.md` — last entry is Session 8 mini-verify at 400/400 + the lingering "Operator follow-up: apply Atlas Search index" bullet. Test count post-fix is 401/401 per commit body; the log still says 400/400. |
| Actual | The 66f0403 commit is a Session-8-follow-up bug-fix-after-deploy event that is materially relevant to: (a) the partial-filter design decision (DM-6 candidate), (b) the conftest drop pattern + v1.x real-MongoDB-testcontainers note, (c) the 400→401 test count. None of those land in the implementation-log. Future readers reconstructing Session 8 from the log alone will see "shipped, 400/400 green" and miss the post-deploy production incident + fix. |
| Cross-check | tasks.md doesn't acknowledge it either (T022 + T063 + the workers/T064/T065 all stay `[x]` with their original Session-8 notes). T067 + T069 paths still reference test file basenames that don't match the actual landed files (`test_album_detail.py` vs `test_album_detail_endpoint.py`; `test_search.py` vs `test_search_endpoint.py`). T068 references `docs/atlas-search-setup.md` not `apps/api/migrations/README.md`. |
| Proposed resolution | Add a "Session 8.5 — Post-deploy partial-filter fix (2026-05-23 morning)" subsection to implementation-log.md capturing (a) the production incident shape, (b) the partial-filter fix, (c) the conftest drop pattern + the real-MongoDB testcontainers v1.x note, (d) the 401/401 new test count. Optionally also add inline `[x]`-line notes to T067/T068/T069 acknowledging the test/doc path divergences (parallel to the §4 wave's inline notes on T049/T064/etc.). |

### DRIFT-L7-015 — `apps/api/migrations/README.md` is not indexed by any other doc

| Field | Value |
|-------|-------|
| Layer | 7 (cross-link integrity) |
| Direction | Internal |
| Severity | INFO |
| Category | structural (convention orphan) |
| Source | `apps/api/migrations/README.md` (NEW this wave) — documents the manual UI + `atlas-cli` apply paths for the `albums_text_search` Atlas Search index |
| Target | `apps/api/migrations/migration-plan.md` — the parent migration doc — does not link to `apps/api/migrations/README.md`. Likewise the feature-level docs (plan.md §11.1, tasks.md T068 Done criterion, implementation-log Session 8 Operator-follow-up) all reference "the README" but as a path, not a markdown link. |
| Actual | Same convention class as L7-004..008 (5 phase-digest orphans) + L7-013 (implementation-log orphan). Not a user-visible defect; flagged because the runbook for applying the Atlas index lives only in the new README and the discoverability path from plan → migrations is currently a grep, not a link. |
| Proposed resolution | Add a markdown link to `apps/api/migrations/README.md` from `apps/api/migrations/migration-plan.md` §"Atlas Search indexes" (or equivalent). Optionally also link it from plan.md §11.1 + tasks.md T068 Done line. |

---

## Drift table

| ID | Layer | Severity | Category | Title | Status |
|----|:-:|:-:|:-:|---|---|
| L3-015 | 3 | WARN | struct | plan §11.2.1 `POST /api/search/report-missing` vs code/tasks `/api/v1/reports/missing-album` | NEW |
| L2-017 | 2 | INFO | struct | spec.md "18 active notification types" stale post-CR-001 (should be 14 active) | NEW |
| L2-018 | 2 | INFO | struct | `Album.candidate` field semantics drift — data-model.md says "admin merge", code/T063 say "T065 reconciliation" | NEW |
| L3-016 | 3 | INFO | struct | plan §3.1 + data-model.md indexes "unique sparse" vs code `partialFilterExpression` (post-`66f0403` fix) | NEW |
| L4-008 | 4 | INFO | struct | §6 wave artifacts (`Album.candidate`, Atlas index `rating_count` field, migrations/README.md) not in plan §3.1 + data-model.md inventory | NEW |
| L5-006 | 5 | INFO | struct | partial-filter fix (commit `66f0403`) not in implementation-log.md; also tasks.md T067/T068/T069 Paths divergences not inline-noted | NEW |
| L6-001 | 6 | INFO | advisory | First Layer-6 sweep: §6 backend endpoints satisfy US-F1/US-F2 backward path; frontend-bound concerns (SSR/OG meta/sort selector/debounce) deferred to T070+ — not drift, surface marker | NEW (advisory) |
| L7-015 | 7 | INFO | struct | `apps/api/migrations/README.md` orphan (no markdown link from migration-plan.md or plan.md) | NEW |
| L1-001 | 1 | INFO | struct | W1 activation definition narrowed | RECURRING |
| L1-002 | 1 | INFO | struct | Apple Music re-eval threshold 15% → 30% | RECURRING (deferred) |
| L2-004 | 2 | INFO | struct | FR-003 trace tag US-A3 → US-A2 (FR-003 DEFERRED-TO-V2 — moot candidate) | RECURRING (CR-001 mooted) |
| L2-005 | 2 | INFO | struct | FR-027 trace tag US-G2 removal (FR-027 DEFERRED-TO-V2 — moot candidate) | RECURRING (CR-001 mooted) |
| L2-006 | 2 | INFO | struct | Cluster name enrichment | RECURRING |
| L2-009 | 2 | INFO | struct | Entity inventory ReviewLike row | RECURRING (partially mooted) |
| L3-009 | 3 | INFO | struct | /critics route in plan, not spec | RECURRING |
| L3-010 | 3 | INFO | struct | Handle collision suggestion incomplete | RECURRING |
| L4-005 | 4 | INFO | struct | 4 satellite collections (FollowRequest + ReviewEditHistory + FailedEmail + NotificationPreferences-embedded) still missing from product-spec/data-model.md inventory | RECURRING (narrowed by L4-008) |
| L7-004..008 | 7 | INFO | struct | 5 phase-digest orphans | RECURRING (convention class) |
| L7-013 | 7 | INFO | struct | implementation-log.md orphan | RECURRING (convention class) |

---

## Verdict

**DRIFT_DETECTED (NOT CRITICAL).**

- 0 individual finding is CRITICAL-severity. No data-loss / runtime regression. Test suite is green (401/401 pass + 3 skip per commit `66f0403`).
- Structural count: **7** (1 new structural WARN + 6 new structural INFO). With strict `structural: 0` budget, the budget rule trips.
- Cosmetic count: **0** — well within the 20 budget.
- Net drift narrowed materially since Run #4 (was 7 structural items with 4 WARN; now 7 structural items with 1 WARN). The §6 wave's headline edge — the partial-filter production-bug fix — landed cleanly and is properly captured in the commit body; the implementation-log + plan + data-model inventory updates are the only places it didn't propagate.
- Layer 6 is meaningful for the first time. Backward direction is substantially clean: US-F1 + US-F2 + FR-005 + FR-010 + FR-033 traceability through `/api/v1/albums/{album_id}` + `/api/v1/search` + the future T053a stub is well-formed. The frontend-bound parts of those stories (SSR, OG meta, sort UI, debounce) are still pending and properly out-of-scope for this run.
- Recommended disposition (carrying forward Run #2/#3/#4's `applied_split_with_override` pattern):
  1. Apply **L3-015** (plan §11.2.1 report-missing URL alignment) — single highest-value cleanup; closes the only WARN.
  2. Apply **L3-016** + **L4-008** as a single index-shape + inventory commit — both touch plan.md §3.1 and data-model.md indexes-table + Album sketch; the partial-filter shape change is also a candidate for a new DM-6 decision-log entry.
  3. Apply **L2-017** (notification-count narrative) + **L2-018** (`Album.candidate` semantics) — both pure documentation cleanup.
  4. Apply **L5-006** (Session 8.5 implementation-log entry) — captures the post-deploy production incident + fix + 401/401 test count; also wraps up the small tasks.md path-divergence notes for T067/T068/T069 in the same edit.
  5. **L7-015** (migration README orphan) is opportunistic — add a single markdown link from `migrations/migration-plan.md` and the convention class shrinks by 1.
  6. **L6-001** is advisory (forward surface marker) — no action; will fold back in once frontend wave (T070+) lands and Layer 6 backward gets a second pass.
  7. Recurring advisory (L1-001/L1-002/L2-004/005/006/009/L3-009/010/L4-005/L7-004..008/L7-013) — skipped as in Runs #2/#3/#4. Mootness of L2-004/L2-005 since CR-001 is a candidate for explicit retirement; recommend grouping into a single "retire-as-moot" disposition in the parent agent's approval flow.
  8. Override on the budget rule (structural ≠ 0) as in Runs #2/#3/#4 — the picture is narrow, well-scoped, and all WARN/INFO items are documentation drift, not runtime drift.

### Outlook to Run #6

If L3-015 + L3-016 + L4-008 + L2-017 + L2-018 + L5-006 + L7-015 land (1 WARN + 6 INFO), Run #6 structural count projects to **~3** (4 satellite collections inventory gap if not folded into L4-008's data-model.md edit, + L7-004..008 phase-digest orphans + L7-013 if convention is not formalised, + advisory L6-001 surface marker). Layer 6 backward becomes more meaningful as soon as frontend wave (T070+ Next.js scaffold + album-detail page + search UI + cover-art proxy) lands. Frontend wave will also retire L6-001 advisory once SSR / OG meta / sort UI / debounce are wired.

**Honest shape assessment: the artifact set is in a coherent shape post-§6.** All the new structural items are documentation-tier drift — narratives that didn't catch up with the §6 wave's code and the post-deploy partial-filter fix. No misalignment requires human-in-the-loop resolution before §3 / §5 begin. The §6 wave proved the data-layer + provider-scaffolding + route-pattern + visibility-filtering composition all hang together; the next wave can proceed.

---

## Sync History

| Run | Date | Layers | CRITICAL | WARNING | INFO | Initial verdict | Final disposition |
|-----|------|--------|---------:|--------:|-----:|------------------|-------------------|
| #1 | 2026-05-21 | 5/7 | 0 | 19 | 14 | CRITICAL DRIFT (budget rule) | RESOLVED WITH OVERRIDE — 10 applied / 10 backlogged / 2 deferred / 14 INFO skipped |
| #2 | 2026-05-22 | 6/7 | 0 | 3 | 22 | DRIFT_DETECTED | RESOLVED WITH OVERRIDE — 10 applied (incl. L1-003 OAuth widening) / 13 advisory recurring / gate overridden |
| #3 | 2026-05-22 | 6/7 | 0 | 2 | 17 | DRIFT_DETECTED | RESOLVED_WITH_OVERRIDE @ 2026-05-22T22:30:00Z — 6 inline cleanups applied (L5-001..005 + L7-014); 13 advisory recurring skipped; gate overridden |
| #4 | 2026-05-22 | 6/7 | 0 | 4 | 14 | DRIFT_DETECTED | RESOLVED_WITH_OVERRIDE @ 2026-05-23T01:00:00Z — applied_split_with_override (L2-014/015/016 + L3-013/014 + L4-006/007 applied inline via commit `aa98618`); 11 advisory recurring skipped |
| #5 | 2026-05-22 | 7/7 | 0 | 1 | 17 | DRIFT_DETECTED | TBD — read-only scan; user to disposition L3-015 (1 WARN) + L2-017/L2-018/L3-016/L4-008/L5-006/L6-001/L7-015 (7 new INFO + 11 recurring) |

---

## Disposition checkboxes (user-driven)

> Run #5 is a read-only scan. The skill explicitly does NOT modify any artifact. Disposition decisions go below; an interactive follow-up should apply them and update `.forge-status.yml` + `sync-fix-list.md`.

- [ ] **L3-015** — Update plan.md:766 report-missing-album URL `POST /api/search/report-missing` → `POST /api/v1/reports/missing-album` (matches code + tasks.md T053a). Optionally clarify `target_id` semantics to acknowledge T053a's structured payload fields.
- [ ] **L2-017** — Reconcile spec.md narrative counts (3 locations: US-G3 AC, §7 data-model, §13 reading list) from "18 active notification types" to "14 active notification types (with N-009/N-010/N-011/N-018/N-019/N-020 reserved-gap)"; aligns with notification-taxonomy.md + product-spec/README.md.
- [ ] **L2-018** — Update data-model.md §"Album identity normalization" step 3 from "manually-entered → admin merge" to "Discogs-sourced → automated T065 reconciliation"; add `Album.candidate: bool` to the Album sketch.
- [ ] **L3-016** — Update plan.md:264 + data-model.md:402-403 from "unique sparse" to "unique partial-filter ({$exists, $ne: null}) — sparse was insufficient because Pydantic serialises None to BSON null"; add new DM-6 decision-log entry capturing the partial-filter design.
- [ ] **L4-008** — Add `Album.candidate` to data-model.md Album sketch; extend plan.md:264 to mention the Atlas index's `rating_count` + popularity-boost. Bundles cleanly with L3-016 in a single index-shape commit.
- [ ] **L5-006** — Add "Session 8.5 — Post-deploy partial-filter fix" subsection to implementation-log.md (incident → fix → conftest drop pattern → 401/401 test count → v1.x testcontainers note). Add inline-divergence notes to tasks.md T067/T068/T069 path lines per locked decision #5 pattern.
- [ ] **L7-015** — Link `apps/api/migrations/README.md` from `apps/api/migrations/migration-plan.md`. Optionally also from plan.md §11.1 + tasks.md T068 Done line.
- [ ] **L6-001** — (Advisory, no action) — Frontend-bound surface marker; revisit in Run #6 once T070+ lands.
- [ ] (recurring) **L4-005** — Add FollowRequest + ReviewEditHistory + FailedEmail to product-spec/data-model.md inventory table; bundles cleanly with L4-008.
- [ ] (recurring, mootness candidate) **L2-004 / L2-005** — Retire as moot since CR-001 (FR-003 + FR-027 both DEFERRED-TO-V2; FR-row tags moot when the FR itself is deferred).
- [ ] (recurring, convention class) **L7-004..008 + L7-013 + L7-015** — Consider a single "phase-digest + implementation-log + migrations-README convention call" disposition: either index all from feature README, or formally exempt the convention class.
