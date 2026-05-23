"""Per-document lazy schema migrations (T030, Constitution P2).

Beanie Documents under :mod:`auxd_api.modules` carry a private
``_schema_version: int = 1`` field so that operationally-evolving
schemas can be rolled forward in place rather than via a single
big-bang ETL.

The :mod:`auxd_api.migrations.runner` module loads every
``NNN_*.py`` sibling in declaration order (``001_initial.py``,
``002_*.py``, ...). The :func:`auxd_api.main.lifespan` invokes the
runner once on startup, between :func:`auxd_api.db.init_db` and
:func:`auxd_api.redis_client.init_redis`, so the data layer is fully
wired before any background workers or HTTP requests touch a
document.

A migration module exports:

* ``name: str`` — human-readable identifier, mirrors the filename.
* ``from_version: int`` — the schema version a document must be at
  for this migration to ``apply``.
* ``to_version: int`` — what ``_schema_version`` the document
  carries once the migration has run.
* ``async def apply(db) -> int`` — returns the number of documents
  modified. May be ``0`` (no-op / clean-tree) and that's fine.

Every migration must be idempotent — re-running on an already-current
schema is required to return ``0`` and make zero writes. This lets the
runner execute on every boot without operator coordination.
"""

from __future__ import annotations

from auxd_api.migrations.runner import (
    DiscoveredMigration,
    MigrationError,
    discover_migrations,
    run_migrations,
)

__all__ = [
    "DiscoveredMigration",
    "MigrationError",
    "discover_migrations",
    "run_migrations",
]
