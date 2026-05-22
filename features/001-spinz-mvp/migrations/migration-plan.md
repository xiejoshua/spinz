# Migration Plan — Spinz MVP

> Generated: 2026-05-22 | DB: MongoDB Atlas (Beanie ODM via Pydantic v2)
> **Strategy: big-bang (greenfield)** — see rationale below
>
> **Source:** [plan.md §3 (Data Model)](../plan.md) · [data-model.md](../product-spec/data-model.md)
> **Files produced:** `forward.py` · `rollback.py` · `validation.py` · `risk-matrix.md` · `seed-data/reserved_handles.txt` · `digest.md`

---

## 0. Why big-bang is appropriate here (greenfield)

For a typical migration plan, big-bang is rejected in favor of shadow-column + dual-write or expand-migrate-contract. **Greenfield projects are the exception:** there is no production data to preserve, no live writers to dual-write through, and no replicas to drag through lag. The "migration" is the initial collection creation + index setup + Atlas Search index application + reserved-handles seed.

This plan establishes:
1. **Today's migration (M0):** big-bang initial setup, fully documented + idempotent + rollback-able.
2. **The framework for future migrations** (post-MVP, with real production data): per-document `_schema_version` + lazy-upgrade-on-write per Constitution Principle 2, with shadow-column + expand-migrate-contract patterns documented.

Zero-downtime framing applies to **all migrations after M0**. After public launch, no migration may use big-bang.

---

## 1. Schema diff (Before → After)

**Before:** empty MongoDB Atlas cluster (no collections, no indexes, no Atlas Search indexes).

**After:** the data model in [plan §3.1](../plan.md). Summary:

| Change | Collection / Field | Type | Reversible? |
|---|---|---|---|
| CREATE | `users` collection | — | ✅ (drop) |
| CREATE | `albums` collection | — | ✅ |
| CREATE | `diary_entries` collection | — | ✅ |
| CREATE | `reviews` collection | — | ✅ |
| CREATE | `review_likes` collection (new in R3) | — | ✅ |
| CREATE | `backlogs` collection | — | ✅ |
| CREATE | `backlog_items` collection | — | ✅ |
| CREATE | `follows` collection | — | ✅ |
| CREATE | `blocks` collection | — | ✅ |
| CREATE | `reports` collection | — | ✅ |
| CREATE | `notifications` collection (TTL 90d) | — | ✅ |
| CREATE | `just_finished_prompts` collection (TTL 24h on pending) | — | ✅ |
| CREATE | `suggested_follows` collection | — | ✅ |
| CREATE | `critic_seeds` collection | — | ✅ |
| CREATE | `gdpr_audit_log` collection | — | ✅ |
| CREATE | `migrations_meta` collection (records applied versions) | — | ✅ |
| CREATE | Atlas Search index on `albums` (`title + artist_credit + artists.name`) | — | ✅ (drop via Atlas UI / API) |
| CREATE | 25+ MongoDB indexes per plan §3.1 (compound, unique, sparse, TTL) | — | ✅ (drop) |
| SEED | 200 reserved-handles (`reserved_handles` collection) | — | ✅ (drop) |
| ESTABLISH | `_schema_version: int = 1` invariant for all new documents | — | (not data; pattern only) |

**No destructive changes** in M0 — all operations are CREATE. The rollback script drops everything (acceptable because no data exists yet).

---

## 2. Strategy per change

For M0 (greenfield):

| Change set | Strategy | Rationale |
|---|---|---|
| All collection creations | Big-bang in one transaction-like sequence (Mongo doesn't have cross-collection transactions at M0 tier, but ordering is idempotent — see §3) | No existing data; ordering is enforced by the forward script |
| MongoDB indexes | Build via `db.collection.create_index(...)` on each new collection at startup; non-blocking on M0 because no data | Idempotent and fast on empty collections |
| Atlas Search index | Apply via Atlas UI manually (one-time) OR via Atlas Search API — documented in `forward.py` as a follow-up step | Atlas Search index propagation can take 1–5 minutes; must complete before public Atlas Search queries hit |
| Reserved-handles seed | Bulk insert into `reserved_handles` collection | Must be in place before any signups |
| Schema-versioning pattern | All Beanie models set `_schema_version: int = 1` by default (enforced by base class in app code, not migration) | Constitution P2 — established once, used forever |

For all migrations **after M0** (post-launch), the default strategy is **expand–migrate–contract** with the Constitution P2 per-doc schema-versioning pattern. See §6 below.

---

## 3. Files produced

| File | Purpose |
|---|---|
| [`forward.py`](./forward.py) | Initial-setup script: creates all collections + indexes + Atlas Search index + reserved-handles seed. **Idempotent** (safe to re-run). |
| [`rollback.py`](./rollback.py) | **DESTRUCTIVE** drop-everything script. Drops all collections, all indexes, the Atlas Search index, and the reserved-handles seed. Should never be run against a database with real user data. |
| [`validation.py`](./validation.py) | Post-migration verification: asserts every collection exists, every index is present, Atlas Search index is queryable, reserved-handles count ≥ 200. Returns non-zero exit code on any failure. |
| [`seed-data/reserved_handles.txt`](./seed-data/reserved_handles.txt) | 200 obvious-squat reservations (major artist names, brands, system handles). Read by `forward.py`. |
| [`risk-matrix.md`](./risk-matrix.md) | Per-risk severity + mitigation table. |
| [`digest.md`](./digest.md) | Phase digest. |

---

## 4. Pre-migration checklist (M0)

- [ ] MongoDB Atlas cluster provisioned (per [tasks.md T005](../tasks.md))
- [ ] Connection string available as `MONGODB_URI` env var
- [ ] Connection allowed from local dev + Fly.io IPs
- [ ] Atlas Search index definition reviewed against `albums` collection schema
- [ ] Reserved-handles list reviewed by founder (per [tasks.md T057](../tasks.md))
- [ ] `python forward.py --dry-run` printed expected operations
- [ ] (Production deploy only) Backup snapshot taken — even though greenfield has no data, take a snapshot anyway to establish the operational pattern

---

## 5. Migration runbook (M0)

```bash
# 1. Verify connectivity
python validation.py --pre  # Should report: "expected 0 collections, found 0 — empty cluster"

# 2. Apply forward migration
python forward.py
# Expected output: "Created 16 collections, 25+ indexes, seeded 200 reserved-handles."

# 3. Apply Atlas Search index (if not done via Atlas UI)
# Use Atlas CLI or web UI to apply the JSON definition embedded in forward.py output

# 4. Verify
python validation.py
# Expected: all checks pass; exit code 0

# 5. Record in migrations_meta
# Forward script writes a row: { version: "001_initial", applied_at: <now> }
```

**Rollback (M0 only — never re-run after data exists):**

```bash
python rollback.py --confirm-destruction
# Drops everything. Type "I UNDERSTAND" at the prompt to proceed.
```

---

## 6. Future migration pattern (post-M0)

Once Spinz has live users, ALL schema changes follow the Constitution Principle 2 pattern:

### 6.1 The pattern

1. **Bump the version.** Every Beanie model class has a class attribute `_schema_version: int = N`. New writes go out at version `N`.
2. **Tolerate two versions.** Application code can read documents at version `N-1` or `N`. If reader sees `_schema_version < N`, it transforms in-memory to version-`N` shape before use.
3. **Lazy upgrade on write.** When any document at version `N-1` is written, the writer applies the upgrade transform and persists at version `N`.
4. **No big-bang migration.** No backfill job that rewrites all existing documents in one go.
5. **Old code stays compatible during deploy window.** Old replicas write at version `N-1`; new replicas write at version `N`. Both tolerate both.

### 6.2 Example: future migration "v1 → v2: add `User.timezone`"

```python
# apps/api/src/spinz_api/modules/auth/models.py
class User(Document):
    _schema_version: int = 2          # bumped from 1
    # ... existing fields ...
    timezone: str = "UTC"             # new field with default

    @classmethod
    async def upgrade_v1_to_v2(cls, doc: dict) -> dict:
        if doc.get("_schema_version", 1) < 2:
            doc["timezone"] = "UTC"   # default for legacy docs
            doc["_schema_version"] = 2
        return doc
```

```python
# Beanie reader middleware (in db.py):
# - On every find_one / find_many result, dispatch through upgrade_v1_to_v2 if needed.
# - On every save / update, run upgrade_v1_to_v2 before persisting.
```

**Backfill job** is OPTIONAL post-launch — only run it if you want to retire the `< N` reader code. Most fields can be lazily upgraded forever with negligible cost.

### 6.3 Forward + rollback pattern for non-greenfield changes

| Strategy | When to use | Rollback approach |
|---|---|---|
| Field addition (nullable / with default) | Adding new optional fields | No rollback needed — readers tolerate absence |
| Field rename | Always | Shadow rename: write both old + new for one release; readers prefer new; drop old in subsequent release |
| Field type change (e.g., string → enum) | Always | Expand-migrate-contract: add new field, migrate writers, dual-read, drop old field |
| Field removal | Rare; only when usage is confirmed zero | Backup snapshot before applying; rollback = restore from snapshot |
| Index addition | Build with `background=True` on M10+ tiers; M0 tier auto-builds in-place | Drop index |
| Index removal | After confirming via query analyzer that it's unused | Re-create from migration history |
| Atlas Search index change | Apply new index alongside old; switch reader endpoint; drop old | Reverse |

---

## 7. Rollback trigger criteria

For **M0 only** (greenfield big-bang):

- `validation.py` fails after `forward.py` runs.
- Application boot fails with `Connection refused: Atlas Search index not ready` and >10 minutes elapsed.
- Atlas Search index returns 0 results for a known-good query 5 minutes after creation.

For **post-M0 migrations**:

- Validation query fails.
- Application error rate > 2× baseline within 1 hour of migration.
- p95 latency > 2× baseline within 1 hour of migration.
- Replication lag > 30 seconds (only relevant when we move to multi-region M10+).

---

## 8. Owner

**Migration owner:** Founder + Implementation team (Phase 6)
**Approved by:** Phase 5.5 gate (this document)
**Re-validate before applying:** Phase 6 Task T012 + T030 will reference this plan.

---

## 9. Notes for Phase 6 implementation team

- `forward.py` and `validation.py` should be wired into the **CI pipeline** (per [tasks.md T004](../tasks.md)) so they run against a fresh Atlas test cluster on every PR. Catches drift between models and migration script.
- The `migrations_meta` collection acts as our "Alembic history" equivalent. Future migrations read it to determine which to apply.
- For the **rollback script**, do NOT make it accessible in production without a manual `--confirm-destruction` flag + an interactive "I UNDERSTAND" prompt. We never want this firing by accident.
- Atlas Search index application **must complete before** the catalog search feature ships (per tasks.md T068). Build it into deploy automation.
- The reserved-handles seed loads from `seed-data/reserved_handles.txt` — keep that file under version control and update via PR (no admin UI for editing the list at MVP).
