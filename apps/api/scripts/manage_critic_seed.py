"""CLI: manage the CriticSeed roster (T162).

Subcommands::

    uv run python apps/api/scripts/manage_critic_seed.py add <handle> [--priority N] [--genres g1,g2]
    uv run python apps/api/scripts/manage_critic_seed.py remove <handle>
    uv run python apps/api/scripts/manage_critic_seed.py activate <handle>
    uv run python apps/api/scripts/manage_critic_seed.py deactivate <handle>
    uv run python apps/api/scripts/manage_critic_seed.py list [--active-only]

Each subcommand resolves the operator-supplied handle through
:func:`auxd_api.modules.users.redirect.resolve_handle` so old handles
(post-rename) still work. CriticSeed rows are upserted on ``user_id``
(unique index) so calling ``add`` twice for the same user updates the
existing row rather than failing on a dup.

Exit codes:

* ``0`` — success
* ``1`` — user not found / row not found / DB unreachable

All errors print to stderr; the success line goes to stdout. Founders can
pipe `list` output through `grep` / `awk` without log noise interfering.

See ``docs/critic-seed-runbook.md`` for the surrounding workflow + roster
size guidance.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from auxd_api.db import close_db, init_db
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.users.redirect import resolve_handle
from auxd_api.settings import get_settings


class _CliError(Exception):
    """Raised by subcommand handlers for operator-friendly failure messages."""


def _parse_genres(raw: str | None) -> list[str]:
    """Split ``--genres a,b,c`` into a lowercase tag list, ignoring blanks."""
    if not raw:
        return []
    return [tag.strip().lower() for tag in raw.split(",") if tag.strip()]


async def _resolve_user_id(handle: str) -> str:
    """Resolve handle → user_id, raising :class:`_CliError` on miss."""
    user, _canonical = await resolve_handle(handle)
    if user is None:
        raise _CliError(f"user @{handle} not found")
    return user.id


async def _cmd_add(handle: str, *, priority: int, genres: list[str]) -> str:
    user_id = await _resolve_user_id(handle)
    existing = await CriticSeed.find_one({"user_id": user_id})
    if existing is not None:
        existing.priority = priority
        if genres:
            existing.genre_signature = genres
        existing.active = True
        existing.deactivated_at = None
        await existing.save()
        return f"updated CriticSeed for @{handle} (priority={priority}, active=True)"
    seed = CriticSeed(
        user_id=user_id,
        priority=priority,
        genre_signature=genres,
        active=True,
    )
    await seed.insert()
    return f"added CriticSeed for @{handle} (priority={priority}, active=True)"


async def _cmd_remove(handle: str) -> str:
    user_id = await _resolve_user_id(handle)
    row = await CriticSeed.find_one({"user_id": user_id})
    if row is None:
        raise _CliError(f"no CriticSeed row for @{handle}")
    await row.delete()
    return f"removed CriticSeed for @{handle}"


async def _cmd_activate(handle: str) -> str:
    user_id = await _resolve_user_id(handle)
    row = await CriticSeed.find_one({"user_id": user_id})
    if row is None:
        raise _CliError(f"no CriticSeed row for @{handle} — use `add` first")
    if row.active:
        return f"@{handle} is already active"
    row.active = True
    row.deactivated_at = None
    await row.save()
    return f"activated @{handle}"


async def _cmd_deactivate(handle: str) -> str:
    user_id = await _resolve_user_id(handle)
    row = await CriticSeed.find_one({"user_id": user_id})
    if row is None:
        raise _CliError(f"no CriticSeed row for @{handle}")
    if not row.active:
        return f"@{handle} is already deactivated"
    row.active = False
    row.deactivated_at = datetime.now(UTC)
    await row.save()
    return f"deactivated @{handle}"


async def _cmd_list(*, active_only: bool) -> str:
    query: dict[str, object] = {"active": True} if active_only else {}
    rows = await CriticSeed.find(query).to_list()
    rows.sort(key=lambda r: (-r.priority, r.user_id))
    if not rows:
        return "no CriticSeed rows" if not active_only else "no active CriticSeed rows"
    lines = [
        f"{'user_id':<28} {'priority':>8} {'active':>6}  genres",
        "-" * 60,
    ]
    for row in rows:
        genres_repr = ",".join(row.genre_signature) if row.genre_signature else "-"
        lines.append(
            f"{row.user_id:<28} {row.priority:>8} {str(row.active):>6}  {genres_repr}"
        )
    lines.append(f"total: {len(rows)}")
    return "\n".join(lines)


async def _amain(args: argparse.Namespace) -> int:
    settings = get_settings()
    await init_db(settings.MONGODB_URI)
    try:
        if args.command == "add":
            message = await _cmd_add(
                args.handle,
                priority=args.priority,
                genres=_parse_genres(args.genres),
            )
        elif args.command == "remove":
            message = await _cmd_remove(args.handle)
        elif args.command == "activate":
            message = await _cmd_activate(args.handle)
        elif args.command == "deactivate":
            message = await _cmd_deactivate(args.handle)
        elif args.command == "list":
            message = await _cmd_list(active_only=args.active_only)
        else:  # pragma: no cover — argparse rejects unknown subcommands
            raise _CliError(f"unknown command: {args.command!r}")
    except _CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_db()
    print(message)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the CriticSeed roster (T162). "
        "See docs/critic-seed-runbook.md for the surrounding workflow.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add or upsert a CriticSeed row by user handle.")
    add.add_argument("handle", help="User handle of the critic to seed.")
    add.add_argument(
        "--priority",
        type=int,
        default=50,
        help="Ranking priority (1..100). Default 50.",
    )
    add.add_argument(
        "--genres",
        default=None,
        help="Comma-separated genre tags (lowercased on insert), e.g. 'indie,hip-hop'.",
    )

    remove = sub.add_parser("remove", help="Hard-delete the CriticSeed row.")
    remove.add_argument("handle")

    activate = sub.add_parser("activate", help="Flip ``active=True`` on an existing row.")
    activate.add_argument("handle")

    deactivate = sub.add_parser("deactivate", help="Soft-deactivate without deleting.")
    deactivate.add_argument("handle")

    listc = sub.add_parser("list", help="List the roster.")
    listc.add_argument(
        "--active-only",
        action="store_true",
        help="Restrict to ``active=True`` rows.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":  # pragma: no cover — invoked from the CLI only.
    raise SystemExit(main())
