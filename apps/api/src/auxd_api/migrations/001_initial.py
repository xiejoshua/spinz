"""Initial no-op migration (T030).

The migrations directory needs at least one file so the runner has a
non-empty discovery surface and operators can confirm the wiring is
live. Every Document already declares ``_schema_version: int = 1``, so
there is literally nothing to migrate yet — this module exists to
demonstrate the pattern and to keep the boot-time runner invocation
honest.

When a future schema change ships, copy this file to
``002_<short_description>.py`` and replace the body of :func:`apply`
with the real upgrade. The contract is:

* Find every document at ``from_version``.
* Apply the transformation.
* Set ``_schema_version`` to ``to_version`` on each modified document.
* Return the count of modified documents.

Idempotency is non-negotiable: re-running this module on the same
cluster must return ``0`` and make zero writes. The runner re-invokes
every migration on every boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


name: str = "001_initial"
from_version: int = 0
to_version: int = 1


async def apply(_db: AsyncIOMotorDatabase[dict[str, object]]) -> int:
    """Seed the migration registry without touching any documents.

    Every Document model in :mod:`auxd_api.modules` declares
    ``_schema_version: int = 1`` as its default, so any document
    written by the runtime app already carries the current version.
    There are no documents at ``from_version=0`` to upgrade, and the
    function returns ``0`` to signal that no writes occurred.

    Args:
        _db: Reserved for future migrations that need direct
            collection access — unused here.

    Returns:
        ``0``. This migration is a no-op by design.
    """
    return 0


__all__ = ["apply", "from_version", "name", "to_version"]
