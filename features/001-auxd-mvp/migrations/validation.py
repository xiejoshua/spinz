"""
auxd MVP — Migration 001_initial (validation)

Post-migration verification queries. Run AFTER forward.py.

USAGE:
  python validation.py             # validate post-migration state
  python validation.py --pre       # validate pre-migration state (cluster should be empty)

EXIT CODES:
  0  — all checks passed
  1  — one or more checks failed
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

EXPECTED_COLLECTIONS = [
    "users",
    "albums",
    "diary_entries",
    "reviews",
    "review_likes",
    "backlogs",
    "backlog_items",
    "follows",
    "blocks",
    "reports",
    "notifications",
    "just_finished_prompts",
    "suggested_follows",
    "critic_seeds",
    "gdpr_audit_log",
    "reserved_handles",
    "handle_redirects",
    "migrations_meta",
]

# Per-collection: list of expected index names. Must match forward.py.
EXPECTED_INDEXES: dict[str, list[str]] = {
    "users": [
        "_id_",
        "ix_users_handle_unique",
        "ix_users_email_unique",
        "ix_users_status_partial",
        "ix_users_deletion_scheduled",
    ],
    "albums": [
        "_id_",
        "ix_albums_mbid_unique",
        "ix_albums_spotify_id_unique",
        "ix_albums_apple_music_id_unique",
        "ix_albums_cache_expires_at",
        "ix_albums_popularity_desc",
    ],
    "diary_entries": [
        "_id_",
        "ix_diary_user_logged_desc",
        "ix_diary_user_album_logged",
        "ix_diary_album_visibility_rating",
        "ix_diary_public_logged",
        "ix_diary_user_auxed",
        "ix_diary_soft_delete_grace",
    ],
    "reviews": [
        "_id_",
        "ix_reviews_user_created",
        "ix_reviews_album_likes_desc",
        "ix_reviews_diary_entry_unique",
    ],
    "review_likes": [
        "_id_",
        "ix_review_likes_review_user_unique",
        "ix_review_likes_user_created",
    ],
    "backlogs": [
        "_id_",
        "ix_backlogs_user_unique",
    ],
    "backlog_items": [
        "_id_",
        "ix_backlog_items_backlog_position",
        "ix_backlog_items_album_backlog",
    ],
    "follows": [
        "_id_",
        "ix_follows_pair_unique",
        "ix_follows_followee_state_created",
        "ix_follows_follower_created",
    ],
    "blocks": [
        "_id_",
        "ix_blocks_pair_unique",
        "ix_blocks_blockee",
    ],
    "reports": [
        "_id_",
        "ix_reports_target",
        "ix_reports_status_created",
        "ix_reports_reporter",
    ],
    "notifications": [
        "_id_",
        "ix_notifications_user_created",
        "ix_notifications_user_unread",
        "ix_notifications_ttl_90d",
    ],
    "just_finished_prompts": [
        "_id_",
        "ix_jfp_user_state_detected",
        "ix_jfp_ttl_30d",
    ],
    "suggested_follows": [
        "_id_",
        "ix_suggested_follows_user_score",
        "ix_suggested_follows_dismissed",
    ],
    "critic_seeds": [
        "_id_",
        "ix_critic_seeds_priority",
        "ix_critic_seeds_active",
        "ix_critic_seeds_user_unique",
    ],
    "gdpr_audit_log": [
        "_id_",
        "ix_gdpr_user_requested",
        "ix_gdpr_action",
    ],
    "reserved_handles": [
        "_id_",
        "ix_reserved_handles_unique",
    ],
    "handle_redirects": [
        "_id_",
        "ix_handle_redirects_old_unique",
        "ix_handle_redirects_ttl",
    ],
    "migrations_meta": [
        "_id_",
        "ix_migrations_meta_version_unique",
    ],
}

MIN_RESERVED_HANDLES = 200


class CheckResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def ok(self, label: str) -> None:
        self.passed.append(label)
        print(f"  ✓ {label}")

    def fail(self, label: str, detail: str) -> None:
        self.failed.append((label, detail))
        print(f"  ✗ {label}: {detail}", file=sys.stderr)

    def summary(self) -> tuple[int, int]:
        return len(self.passed), len(self.failed)


async def validate_pre(db: AsyncIOMotorDatabase, results: CheckResult) -> None:
    """Pre-migration: cluster should be empty of our collections."""
    print("[Pre-migration validation: cluster should be empty of auxd collections]")
    existing = await db.list_collection_names()
    auxd_present = [c for c in existing if c in EXPECTED_COLLECTIONS]
    if auxd_present:
        results.fail(
            "Pre-migration empty check",
            f"Found existing auxd collections: {auxd_present}. Cluster is not empty.",
        )
    else:
        results.ok("Pre-migration empty check: no auxd collections present")


async def validate_post(db: AsyncIOMotorDatabase, results: CheckResult) -> None:
    """Post-migration: all collections + indexes + seed present."""
    print("[Post-migration validation]")

    # 1. Collections exist
    existing = set(await db.list_collection_names())
    for coll_name in EXPECTED_COLLECTIONS:
        if coll_name in existing:
            results.ok(f"Collection '{coll_name}' exists")
        else:
            results.fail(f"Collection '{coll_name}'", "missing")

    # 2. Indexes per collection
    for coll_name, expected_index_names in EXPECTED_INDEXES.items():
        if coll_name not in existing:
            continue  # collection missing — already reported
        actual_indexes = {ix["name"] async for ix in db[coll_name].list_indexes()}
        for ix_name in expected_index_names:
            if ix_name in actual_indexes:
                results.ok(f"Index '{coll_name}.{ix_name}'")
            else:
                results.fail(f"Index '{coll_name}.{ix_name}'", f"missing (actual: {sorted(actual_indexes)})")

    # 3. Reserved-handles seed count
    if "reserved_handles" in existing:
        count = await db["reserved_handles"].count_documents({})
        if count >= MIN_RESERVED_HANDLES:
            results.ok(f"reserved_handles count = {count} (>= {MIN_RESERVED_HANDLES})")
        else:
            results.fail("reserved_handles seed", f"only {count} present (expected >= {MIN_RESERVED_HANDLES})")

    # 4. migrations_meta has 001_initial
    if "migrations_meta" in existing:
        rec = await db["migrations_meta"].find_one({"version": "001_initial"})
        if rec:
            results.ok(f"migrations_meta has '001_initial' applied_at {rec.get('applied_at')}")
        else:
            results.fail("migrations_meta", "no record of '001_initial'")

    # 5. Atlas Search index — assert at least one search index exists on `albums` if queryable
    if "albums" in existing:
        try:
            # Try a search query; if Atlas Search index missing, this will error
            cursor = db["albums"].aggregate([
                {"$search": {"index": "albums_search", "text": {"query": "test", "path": ["title"]}}},
                {"$limit": 1},
            ])
            _ = [doc async for doc in cursor]  # consume
            results.ok("Atlas Search index 'albums_search' is queryable")
        except Exception as e:
            results.fail("Atlas Search index 'albums_search'", f"not queryable: {e!r}. Apply manually via Atlas UI.")


async def main() -> int:
    parser = argparse.ArgumentParser(description="auxd MVP — migration validation")
    parser.add_argument("--pre", action="store_true", help="Validate PRE-migration state (cluster empty)")
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI env var is required", file=sys.stderr)
        return 1

    client = AsyncIOMotorClient(uri)
    db = client.get_default_database()
    results = CheckResult()

    try:
        if args.pre:
            await validate_pre(db, results)
        else:
            await validate_post(db, results)
    finally:
        client.close()

    passed, failed = results.summary()
    print()
    print("=" * 60)
    print(f"Validation complete: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
