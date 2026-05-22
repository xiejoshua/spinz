"""
auxd MVP — Migration 001_initial (rollback)

⚠️⚠️⚠️ DESTRUCTIVE — DROPS ALL DATA ⚠️⚠️⚠️

This script is ONLY safe to run on a greenfield cluster (no real users yet).
After public launch, running this script destroys all user data with no recovery.

USAGE:
  python rollback.py --confirm-destruction
  # Then type "I UNDERSTAND" at the prompt to proceed.

USE CASES (legitimate):
  1. M0 greenfield setup failed; clean slate for re-running forward.py
  2. Staging / dev cluster reset
  3. CI test cluster teardown

NEVER USE CASES:
  1. Production after the first real user signs up
  2. Recovery scenarios — use restore-from-backup instead
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

COLLECTIONS_TO_DROP = [
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


async def confirm_destruction(uri: str) -> bool:
    """Force interactive confirmation. Print loud warnings."""
    print("=" * 70)
    print("⚠️  DESTRUCTIVE OPERATION — ROLLBACK MIGRATION 001_initial")
    print("=" * 70)
    print(f"Target cluster: {uri.split('@')[-1].split('/')[0] if '@' in uri else 'localhost'}")
    print()
    print("This will DROP the following collections AND ALL THEIR DATA:")
    for c in COLLECTIONS_TO_DROP:
        print(f"  - {c}")
    print()
    print("The Atlas Search index 'albums_search' is NOT dropped by this script.")
    print("Delete it manually via Atlas UI if needed.")
    print()
    print("If this cluster has real user data, ABORT NOW.")
    print()
    print("Type exactly  I UNDERSTAND  to proceed (anything else aborts):")
    reply = input("> ")
    return reply.strip() == "I UNDERSTAND"


async def main() -> int:
    parser = argparse.ArgumentParser(description="auxd MVP — rollback initial migration (DESTRUCTIVE)")
    parser.add_argument("--confirm-destruction", action="store_true", help="Required acknowledgment of destruction. Plus interactive prompt.")
    parser.add_argument("--force-non-interactive", action="store_true", help="Skip interactive prompt. ONLY for CI test cluster teardown.")
    args = parser.parse_args()

    if not args.confirm_destruction:
        print("ERROR: --confirm-destruction flag required.")
        print("This is a destructive operation. Read rollback.py source before re-running.")
        return 1

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI env var is required", file=sys.stderr)
        return 1

    # Safety: refuse to run against any URI that doesn't look like a test/dev env
    # unless force-non-interactive is set
    is_obviously_test = any(token in uri.lower() for token in ["localhost", "test", "dev", "staging", "ci"])
    if not is_obviously_test and not args.force_non_interactive:
        ok = await confirm_destruction(uri)
        if not ok:
            print("Aborted — confirmation phrase not entered.")
            return 1

    client = AsyncIOMotorClient(uri)
    db = client.get_default_database()
    dropped = 0
    try:
        existing = await db.list_collection_names()
        for coll_name in COLLECTIONS_TO_DROP:
            if coll_name in existing:
                await db.drop_collection(coll_name)
                print(f"  ✗ DROPPED {coll_name}")
                dropped += 1
            else:
                print(f"  - skipped {coll_name} (not present)")
    finally:
        client.close()

    print()
    print(f"Rolled back {dropped} collections at {datetime.now(timezone.utc).isoformat()}.")
    print("Atlas Search index NOT touched — drop manually via Atlas UI if needed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
