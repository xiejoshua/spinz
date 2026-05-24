"""002 — Add ``discogs_master_id`` field to Album (search-fix v4).

Existing Album rows have ``discogs_master_id = None`` (the field was
added in Session 27 search-fix v4 on 2026-05-24). New rows materialised
via the search path populate it. No backfill of existing rows is
performed — old rows stay master-less; their ``discogs_release_id`` and
``mbid`` continue to serve as identity. The T065 reconciliation worker
(weekly) can be extended in a future iteration to backfill master_ids
for existing rows by querying Discogs's ``/masters`` lookup by MBID
where present.

This migration is a NO-OP by design. The new field defaults to ``None``
on the model and MongoDB tolerates missing fields. The sparse-unique
index handles existing rows that don't have the field (the
``partialFilterExpression`` excludes both ``null`` and missing-field
cases). Documents written after this migration carries the new schema
version on their next save.

Idempotency: running this migration repeatedly returns ``0`` and makes
zero writes, as required by the migration-runner contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


name: str = "002_album_discogs_master_id"
from_version: int = 1
to_version: int = 2


async def apply(_db: AsyncIOMotorDatabase[dict[str, object]]) -> int:
    """Seed the schema-version bump without touching any documents.

    The ``discogs_master_id`` field is optional and defaults to ``None``
    on the model; MongoDB tolerates the missing field on existing rows.
    The sparse-unique index applied at ``init_beanie`` time uses
    ``partialFilterExpression={"discogs_master_id": {"$type": "string"}}``
    which already excludes both null + missing-field cases, so no
    constraint violation occurs even if the migration runs against a
    cluster that has just gained the new index.

    Args:
        _db: Reserved for future migrations that need direct collection
            access — unused here.

    Returns:
        ``0``. This migration is a no-op by design.
    """
    return 0


__all__ = ["apply", "from_version", "name", "to_version"]
