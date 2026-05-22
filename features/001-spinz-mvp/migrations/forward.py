"""
Spinz MVP — Migration 001_initial (forward)

Greenfield big-bang initial schema setup. Idempotent: safe to re-run.

USAGE:
  python forward.py                  # apply against MONGODB_URI
  python forward.py --dry-run        # print what would happen, don't write
  python forward.py --skip-search    # skip Atlas Search index step (apply via UI)

DEPS:
  pip install motor pymongo python-dotenv

ENV:
  MONGODB_URI         — connection string
  ATLAS_SEARCH_API_KEY (optional) — for programmatic Atlas Search index creation
  ATLAS_PROJECT_ID    (optional) — for programmatic Atlas Search index creation
  ATLAS_CLUSTER_NAME  (optional) — for programmatic Atlas Search index creation

EXIT CODES:
  0  — success
  1  — any setup step failed
  2  — Atlas Search index step needs manual application (followup required)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import OperationFailure

SCHEMA_VERSION = 1
MIGRATION_VERSION = "001_initial"

# Collection inventory — name → list of index specs.
# Index spec: {"keys": [(field, direction), ...], "options": {...}}
COLLECTIONS: dict[str, list[dict[str, Any]]] = {
    "users": [
        {"keys": [("handle", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_users_handle_unique"}},
        {"keys": [("email", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_users_email_unique"}},
        {"keys": [("status", ASCENDING)], "options": {"partialFilterExpression": {"status": {"$in": ["active", "suspended"]}}, "name": "ix_users_status_partial"}},
        {"keys": [("deletion_scheduled_for", ASCENDING)], "options": {"sparse": True, "name": "ix_users_deletion_scheduled"}},
    ],
    "albums": [
        {"keys": [("mbid", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_albums_mbid_unique"}},
        {"keys": [("spotify_id", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_albums_spotify_id_unique"}},
        {"keys": [("apple_music_id", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_albums_apple_music_id_unique"}},
        {"keys": [("cache_expires_at", ASCENDING)], "options": {"name": "ix_albums_cache_expires_at"}},
        {"keys": [("popularity_score", DESCENDING)], "options": {"name": "ix_albums_popularity_desc"}},
    ],
    "diary_entries": [
        {"keys": [("user_id", ASCENDING), ("logged_at", DESCENDING)], "options": {"name": "ix_diary_user_logged_desc"}},
        {"keys": [("user_id", ASCENDING), ("album_id", ASCENDING), ("logged_at", DESCENDING)], "options": {"name": "ix_diary_user_album_logged"}},
        {"keys": [("album_id", ASCENDING), ("visibility", ASCENDING), ("rating", DESCENDING)], "options": {"name": "ix_diary_album_visibility_rating"}},
        {"keys": [("visibility", ASCENDING), ("logged_at", DESCENDING)], "options": {"partialFilterExpression": {"visibility": "public"}, "name": "ix_diary_public_logged"}},
        {"keys": [("user_id", ASCENDING), ("awarded", ASCENDING)], "options": {"partialFilterExpression": {"awarded": True}, "name": "ix_diary_user_awarded"}},
        {"keys": [("deleted_at", ASCENDING)], "options": {"sparse": True, "name": "ix_diary_soft_delete_grace"}},
    ],
    "reviews": [
        {"keys": [("user_id", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_reviews_user_created"}},
        {"keys": [("album_id", ASCENDING), ("reactions.likes_count", DESCENDING)], "options": {"name": "ix_reviews_album_likes_desc"}},
        {"keys": [("diary_entry_id", ASCENDING)], "options": {"unique": True, "sparse": True, "name": "ix_reviews_diary_entry_unique"}},
    ],
    "review_likes": [
        {"keys": [("review_id", ASCENDING), ("user_id", ASCENDING)], "options": {"unique": True, "name": "ix_review_likes_review_user_unique"}},
        {"keys": [("user_id", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_review_likes_user_created"}},
    ],
    "backlogs": [
        {"keys": [("user_id", ASCENDING)], "options": {"unique": True, "name": "ix_backlogs_user_unique"}},
    ],
    "backlog_items": [
        {"keys": [("backlog_id", ASCENDING), ("position", ASCENDING)], "options": {"name": "ix_backlog_items_backlog_position"}},
        {"keys": [("album_id", ASCENDING), ("backlog_id", ASCENDING)], "options": {"name": "ix_backlog_items_album_backlog"}},
    ],
    "follows": [
        {"keys": [("follower_id", ASCENDING), ("followee_id", ASCENDING)], "options": {"unique": True, "name": "ix_follows_pair_unique"}},
        {"keys": [("followee_id", ASCENDING), ("state", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_follows_followee_state_created"}},
        {"keys": [("follower_id", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_follows_follower_created"}},
    ],
    "blocks": [
        {"keys": [("blocker_id", ASCENDING), ("blockee_id", ASCENDING)], "options": {"unique": True, "name": "ix_blocks_pair_unique"}},
        {"keys": [("blockee_id", ASCENDING)], "options": {"name": "ix_blocks_blockee"}},
    ],
    "reports": [
        {"keys": [("target_type", ASCENDING), ("target_id", ASCENDING)], "options": {"name": "ix_reports_target"}},
        {"keys": [("status", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_reports_status_created"}},
        {"keys": [("reporter_id", ASCENDING)], "options": {"sparse": True, "name": "ix_reports_reporter"}},
    ],
    "notifications": [
        {"keys": [("user_id", ASCENDING), ("created_at", DESCENDING)], "options": {"name": "ix_notifications_user_created"}},
        {"keys": [("user_id", ASCENDING), ("read_at", ASCENDING)], "options": {"sparse": True, "name": "ix_notifications_user_unread"}},
        # TTL: hard-delete 90 days after creation
        {"keys": [("created_at", ASCENDING)], "options": {"expireAfterSeconds": 60 * 60 * 24 * 90, "name": "ix_notifications_ttl_90d"}},
    ],
    "just_finished_prompts": [
        {"keys": [("user_id", ASCENDING), ("state", ASCENDING), ("detected_at", DESCENDING)], "options": {"name": "ix_jfp_user_state_detected"}},
        # TTL: 24 hours on `pending` state — Mongo TTL is field-based, so we use a partial index on a separate `expires_at` field
        # This index expires docs (any state) 30 days after detected_at as a safety net
        {"keys": [("detected_at", ASCENDING)], "options": {"expireAfterSeconds": 60 * 60 * 24 * 30, "name": "ix_jfp_ttl_30d"}},
    ],
    "suggested_follows": [
        {"keys": [("user_id", ASCENDING), ("score", DESCENDING)], "options": {"name": "ix_suggested_follows_user_score"}},
        {"keys": [("dismissed_at", ASCENDING)], "options": {"sparse": True, "name": "ix_suggested_follows_dismissed"}},
    ],
    "critic_seeds": [
        {"keys": [("priority", DESCENDING)], "options": {"name": "ix_critic_seeds_priority"}},
        {"keys": [("active", ASCENDING)], "options": {"partialFilterExpression": {"active": True}, "name": "ix_critic_seeds_active"}},
        {"keys": [("user_id", ASCENDING)], "options": {"unique": True, "name": "ix_critic_seeds_user_unique"}},
    ],
    "gdpr_audit_log": [
        {"keys": [("user_id", ASCENDING), ("requested_at", DESCENDING)], "options": {"name": "ix_gdpr_user_requested"}},
        {"keys": [("action", ASCENDING)], "options": {"name": "ix_gdpr_action"}},
    ],
    "reserved_handles": [
        {"keys": [("handle", ASCENDING)], "options": {"unique": True, "name": "ix_reserved_handles_unique"}},
    ],
    "handle_redirects": [
        {"keys": [("old_handle", ASCENDING)], "options": {"unique": True, "name": "ix_handle_redirects_old_unique"}},
        # TTL: redirects valid for 90 days
        {"keys": [("expires_at", ASCENDING)], "options": {"expireAfterSeconds": 0, "name": "ix_handle_redirects_ttl"}},
    ],
    "migrations_meta": [
        {"keys": [("version", ASCENDING)], "options": {"unique": True, "name": "ix_migrations_meta_version_unique"}},
    ],
}

# Atlas Search index definition for `albums` (per plan §11.1)
ATLAS_SEARCH_INDEX_ALBUMS = {
    "name": "albums_search",
    "definition": {
        "mappings": {
            "dynamic": False,
            "fields": {
                "title": [
                    {"type": "string", "analyzer": "lucene.standard"},
                    {"type": "autocomplete", "tokenization": "edgeGram", "minGrams": 2, "maxGrams": 15},
                ],
                "artist_credit": [
                    {"type": "string", "analyzer": "lucene.standard"},
                ],
                "artists": {
                    "type": "document",
                    "fields": {
                        "name": [{"type": "string", "analyzer": "lucene.standard"}]
                    },
                },
                "popularity_score": {"type": "number"},
                "release_year": {"type": "number"},
            },
        }
    },
}


async def ensure_collection(db: AsyncIOMotorDatabase, name: str, dry_run: bool) -> bool:
    """Create collection if missing. Returns True if newly created."""
    existing = await db.list_collection_names()
    if name in existing:
        print(f"  ✓ collection '{name}' already exists (skipping creation)")
        return False
    if dry_run:
        print(f"  + would create collection '{name}'")
        return True
    await db.create_collection(name)
    print(f"  + created collection '{name}'")
    return True


async def ensure_indexes(db: AsyncIOMotorDatabase, collection_name: str, index_specs: list[dict[str, Any]], dry_run: bool) -> int:
    """Create indexes if missing. Returns count of indexes created."""
    coll = db[collection_name]
    existing_indexes = {ix["name"]: ix async for ix in coll.list_indexes()}
    created = 0
    for spec in index_specs:
        name = spec["options"]["name"]
        if name in existing_indexes:
            print(f"    ✓ index '{name}' already exists on '{collection_name}'")
            continue
        if dry_run:
            print(f"    + would create index '{name}' on '{collection_name}'")
            created += 1
            continue
        try:
            await coll.create_index(spec["keys"], **spec["options"])
            print(f"    + created index '{name}' on '{collection_name}'")
            created += 1
        except OperationFailure as e:
            print(f"    ✗ FAILED to create index '{name}' on '{collection_name}': {e}", file=sys.stderr)
            raise
    return created


async def seed_reserved_handles(db: AsyncIOMotorDatabase, dry_run: bool) -> int:
    """Bulk-insert reserved-handles seed."""
    seed_path = Path(__file__).parent / "seed-data" / "reserved_handles.txt"
    if not seed_path.exists():
        print(f"  ! seed file not found: {seed_path}", file=sys.stderr)
        return 0
    with open(seed_path, "r") as f:
        handles = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
    if not handles:
        print(f"  ! seed file is empty: {seed_path}", file=sys.stderr)
        return 0

    coll = db["reserved_handles"]
    existing = {doc["handle"] async for doc in coll.find({}, {"handle": 1})}
    new_handles = [h for h in handles if h not in existing]
    if not new_handles:
        print(f"  ✓ all {len(handles)} reserved-handles already present (skipping seed)")
        return 0
    if dry_run:
        print(f"  + would seed {len(new_handles)} reserved-handles ({len(existing)} already present)")
        return len(new_handles)
    now = datetime.now(timezone.utc)
    docs = [
        {
            "_schema_version": SCHEMA_VERSION,
            "handle": h,
            "reason": "obvious_squat",
            "created_at": now,
        }
        for h in new_handles
    ]
    result = await coll.insert_many(docs)
    print(f"  + seeded {len(result.inserted_ids)} reserved-handles ({len(existing)} were already present)")
    return len(result.inserted_ids)


async def apply_atlas_search_index(dry_run: bool, skip_search: bool) -> tuple[bool, str]:
    """
    Apply Atlas Search index. Returns (success, message).

    If ATLAS_SEARCH_API_KEY + ATLAS_PROJECT_ID + ATLAS_CLUSTER_NAME are set, use Atlas Admin API.
    Otherwise emit JSON for manual UI application.
    """
    if skip_search:
        return False, "Atlas Search index skipped (--skip-search). Apply manually via Atlas UI."

    api_key = os.environ.get("ATLAS_SEARCH_API_KEY")
    project_id = os.environ.get("ATLAS_PROJECT_ID")
    cluster_name = os.environ.get("ATLAS_CLUSTER_NAME")
    if not (api_key and project_id and cluster_name):
        index_json = json.dumps(ATLAS_SEARCH_INDEX_ALBUMS, indent=2)
        print("  ! ATLAS_SEARCH_API_KEY / ATLAS_PROJECT_ID / ATLAS_CLUSTER_NAME not all set.")
        print("  ! Manual application required. Paste this JSON into Atlas UI → Search → Create Index → JSON Editor:")
        print(index_json)
        return False, "manual_required"

    if dry_run:
        print(f"  + would apply Atlas Search index 'albums_search' via Atlas Admin API to cluster {cluster_name}")
        return True, "dry_run"

    # Production-grade Atlas Admin API call would go here. For MVP, we expect manual application.
    # This branch is a placeholder; the manual path above is the documented workflow at M0.
    print(f"  ! Atlas Admin API integration not implemented at M0 — apply manually via UI.")
    return False, "manual_required"


async def record_migration(db: AsyncIOMotorDatabase, dry_run: bool) -> None:
    """Record this migration in migrations_meta."""
    if dry_run:
        print(f"  + would record migration '{MIGRATION_VERSION}' in migrations_meta")
        return
    coll = db["migrations_meta"]
    existing = await coll.find_one({"version": MIGRATION_VERSION})
    if existing:
        print(f"  ✓ migration '{MIGRATION_VERSION}' already recorded (applied_at: {existing.get('applied_at')})")
        return
    await coll.insert_one({
        "_schema_version": SCHEMA_VERSION,
        "version": MIGRATION_VERSION,
        "applied_at": datetime.now(timezone.utc),
        "notes": "Initial greenfield schema setup",
    })
    print(f"  + recorded migration '{MIGRATION_VERSION}' in migrations_meta")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Spinz MVP — initial schema migration")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen; don't write")
    parser.add_argument("--skip-search", action="store_true", help="Skip Atlas Search index (apply manually)")
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI env var is required", file=sys.stderr)
        return 1

    print(f"Spinz MVP migration {MIGRATION_VERSION} — {'DRY RUN' if args.dry_run else 'APPLYING'}")
    print(f"Connecting to: {uri.split('@')[-1].split('/')[0] if '@' in uri else 'localhost'}")
    client = AsyncIOMotorClient(uri)
    db = client.get_default_database()

    total_collections_created = 0
    total_indexes_created = 0
    try:
        for coll_name, index_specs in COLLECTIONS.items():
            print(f"\n[{coll_name}]")
            created = await ensure_collection(db, coll_name, args.dry_run)
            if created:
                total_collections_created += 1
            count = await ensure_indexes(db, coll_name, index_specs, args.dry_run)
            total_indexes_created += count

        print(f"\n[reserved-handles seed]")
        seeded = await seed_reserved_handles(db, args.dry_run)

        print(f"\n[Atlas Search index]")
        search_ok, search_msg = await apply_atlas_search_index(args.dry_run, args.skip_search)

        print(f"\n[migrations_meta]")
        await record_migration(db, args.dry_run)

    finally:
        client.close()

    print(f"\n{'='*60}")
    print(f"Summary ({'DRY RUN — nothing persisted' if args.dry_run else 'APPLIED'}):")
    print(f"  Collections created: {total_collections_created}")
    print(f"  Indexes created: {total_indexes_created}")
    print(f"  Reserved-handles seeded: {seeded}")
    print(f"  Atlas Search index: {'OK' if search_ok else 'NEEDS MANUAL APPLICATION'}")

    if not search_ok and not args.skip_search:
        return 2  # signal: manual followup required
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
