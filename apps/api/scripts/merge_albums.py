"""CLI: merge two album records (T167).

Usage::

    uv run python apps/api/scripts/merge_albums.py <losing> <winning> [--dry-run] [--yes]

When a user reports an album as a duplicate (via ``POST /reports/album``
with ``reason=duplicate``), or the founder finds two albums with
divergent metadata that should be unified, this script:

1. Loads both ``Album`` documents (KSUID strings).
2. Counts references in the three FK collections that link to Album:
   :class:`DiaryEntry`, :class:`Review`, :class:`BacklogItem`.
3. Prints a summary so the operator can sanity-check before mutating.
4. With ``--dry-run``, stops after the summary (no writes).
5. Otherwise (prompting unless ``--yes``) rewrites every FK from the
   losing album_id to the winning one and hard-deletes the losing row.

There is **no AlbumRedirect** at MVP. Old URLs to the losing album
will start returning 404 after the merge — that's acceptable for admin
tooling at this scale; a future feature could add a redirect layer.

Exit codes: ``0`` on success, ``1`` on any error (album not found,
identical ids, DB unreachable, operator declines prompt).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from auxd_api.db import close_db, init_db
from auxd_api.modules.albums.models import Album
from auxd_api.modules.backlog.models import BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.reviews.models import Review
from auxd_api.settings import get_settings


class _CliError(Exception):
    """Operator-friendly failure surface."""


async def _count_refs(album_id: str) -> dict[str, int]:
    """Count rows in each FK collection that reference ``album_id``."""
    diary_count = await DiaryEntry.find({"album_id": album_id}).count()
    review_count = await Review.find({"album_id": album_id}).count()
    backlog_count = await BacklogItem.find({"album_id": album_id}).count()
    return {
        "diary_entries": diary_count,
        "reviews": review_count,
        "backlog_items": backlog_count,
    }


def _format_album(album: Album, counts: dict[str, int]) -> str:
    return (
        f"  id={album.id}\n"
        f"  title={album.title}\n"
        f"  artist={album.artist_credit}\n"
        f"  diary_entries={counts['diary_entries']}, "
        f"reviews={counts['reviews']}, "
        f"backlog_items={counts['backlog_items']}"
    )


async def _rewrite_fk(collection_label: str, album_id_from: str, album_id_to: str) -> int:
    """Update every FK row pointing at ``album_id_from`` to ``album_id_to``.

    Returns the number of rows touched. Uses the Beanie find+save loop
    rather than a raw ``update_many`` so the updated_at columns
    (and any subclass hooks) fire correctly.
    """
    if collection_label == "diary_entries":
        rows = await DiaryEntry.find({"album_id": album_id_from}).to_list()
        for row in rows:
            row.album_id = album_id_to
            await row.save()
        return len(rows)
    if collection_label == "reviews":
        rows = await Review.find({"album_id": album_id_from}).to_list()
        for row in rows:
            row.album_id = album_id_to
            await row.save()
        return len(rows)
    if collection_label == "backlog_items":
        rows = await BacklogItem.find({"album_id": album_id_from}).to_list()
        for row in rows:
            row.album_id = album_id_to
            await row.save()
        return len(rows)
    raise _CliError(f"unknown collection {collection_label!r}")


async def _amain(
    losing_id: str,
    winning_id: str,
    *,
    dry_run: bool,
    yes: bool,
) -> int:
    if losing_id == winning_id:
        print("error: losing and winning album ids must differ", file=sys.stderr)
        return 1

    settings = get_settings()
    await init_db(settings.MONGODB_URI)
    try:
        losing = await Album.find_one(Album.id == losing_id)
        winning = await Album.find_one(Album.id == winning_id)
        if losing is None:
            print(f"error: losing album {losing_id!r} not found", file=sys.stderr)
            return 1
        if winning is None:
            print(f"error: winning album {winning_id!r} not found", file=sys.stderr)
            return 1

        losing_counts = await _count_refs(losing_id)
        winning_counts = await _count_refs(winning_id)

        print("losing album:")
        print(_format_album(losing, losing_counts))
        print("winning album:")
        print(_format_album(winning, winning_counts))

        if dry_run:
            print("dry-run: no writes performed")
            return 0

        if not yes:
            answer = input("proceed with merge? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("aborted")
                return 1

        touched = {
            label: await _rewrite_fk(label, losing_id, winning_id)
            for label in ("diary_entries", "reviews", "backlog_items")
        }
        await losing.delete()
        total = sum(touched.values())
        print(
            "merge complete: "
            f"diary={touched['diary_entries']}, "
            f"reviews={touched['reviews']}, "
            f"backlog={touched['backlog_items']}, "
            f"deleted=1 (losing album), "
            f"total_rows_touched={total + 1}"
        )
        return 0
    finally:
        await close_db()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge two Album records (T167). The losing album row is "
        "hard-deleted after every FK is rewritten to the winning id.",
    )
    parser.add_argument("losing_album_id", help="KSUID of the album to retire.")
    parser.add_argument("winning_album_id", help="KSUID of the album to keep.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the summary without mutating any rows.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt (useful in scripts).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(
        _amain(
            args.losing_album_id,
            args.winning_album_id,
            dry_run=args.dry_run,
            yes=args.yes,
        )
    )


if __name__ == "__main__":  # pragma: no cover — invoked from the CLI only.
    raise SystemExit(main())
