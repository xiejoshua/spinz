"""Lazy schema-migration runner (T030, Constitution P2).

This module owns three concerns and nothing else:

1. **Discovery** — walk the :mod:`auxd_api.migrations` package and
   collect every sibling module whose filename matches the
   ``NNN_*.py`` pattern, sorted by the numeric prefix.
2. **Execution** — call each module's ``apply(db) -> int`` coroutine
   in order. Each migration is responsible for selecting only the
   documents at its ``from_version`` and bumping them to
   ``to_version`` (no-op when there's nothing to do).
3. **Observability** — emit a structured ``migration.applied`` event
   through :func:`auxd_api.lib.observability.log_call` for every
   migration that ran, regardless of how many documents it touched.

Adding a new migration
----------------------

1. Create ``NNN_short_description.py`` in this package. Choose
   ``NNN`` as the next free integer (e.g. ``002`` after
   ``001_initial``).
2. Export module-level constants:

   * ``name: str`` (filename stem is fine; kept explicit to survive
     accidental rename).
   * ``from_version: int`` — the version each document must currently
     be at to be selected.
   * ``to_version: int`` — the version each document carries once the
     migration has finished. Usually ``from_version + 1``.

3. Implement ``async def apply(db: AsyncIOMotorDatabase) -> int``
   that:

   * Selects documents at ``from_version`` (via the relevant
     collection — Beanie's ``Document.find`` is fine).
   * Performs whatever transformation is required.
   * Sets ``_schema_version`` to ``to_version`` on each modified
     document.
   * Returns the count of modified documents.

4. The migration MUST be idempotent: re-running on a cluster where
   every document is already at ``to_version`` must select zero rows
   and return ``0``.

Breaking schema changes
-----------------------

For renames or removals that can't be expressed safely as a lazy
upgrade (e.g. dropping a required field a runtime model relies on),
ship the change in two waves:

* Wave 1 — runtime code reads from BOTH the old and the new field.
  Ship a migration that backfills the new field on every existing
  document and bumps ``_schema_version``.
* Wave 2 — once every document is at the new version, remove the
  legacy read path. Optionally a follow-up migration drops the old
  field entirely.

This keeps the runner's single rule honoured: a migration that
raises must crash the app so the operator sees the failure
immediately (Constitution P5 fail-loud).
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from auxd_api.lib.observability import log_call

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

_LOGGER = logging.getLogger("auxd.migrations.runner")

# ``001_initial`` matches; ``__init__``, ``runner``, and other helper
# modules in this package do not.
_MIGRATION_FILENAME_RE = re.compile(r"^(\d{3})_[A-Za-z0-9_]+$")


class _MigrationModule(Protocol):
    """Structural contract every migration module must satisfy."""

    name: str
    from_version: int
    to_version: int

    async def apply(  # pragma: no cover - protocol body
        self, db: AsyncIOMotorDatabase[dict[str, object]]
    ) -> int: ...


@dataclass(frozen=True)
class DiscoveredMigration:
    """A migration loaded from disk, ready to be executed.

    The :attr:`order` field is the numeric prefix on the filename,
    parsed once at discovery so execution doesn't need to re-parse it.
    """

    order: int
    name: str
    from_version: int
    to_version: int
    module: _MigrationModule


class MigrationError(RuntimeError):
    """Raised when discovery or execution detects an invariant violation.

    Examples: a migration module missing a required attribute, a
    migration's ``apply`` raising during execution. The runner re-raises
    after logging so the FastAPI lifespan crashes the process (fail-loud,
    Constitution P5) — a broken migration MUST NOT allow the app to
    start serving traffic against an inconsistent data layer.
    """


def discover_migrations(package_name: str = "auxd_api.migrations") -> list[DiscoveredMigration]:
    """Walk the migrations package and return every migration in order.

    The runner imports each migration module lazily — discovery alone
    is cheap (one ``importlib.import_module`` per matching filename)
    and the loaded modules are cached by Python so repeat calls are
    free.

    Sort order is the numeric prefix on the filename. That keeps
    ``002_foo`` after ``001_initial`` regardless of import-time
    side-effects or filesystem ordering.

    Args:
        package_name: Fully-qualified dotted path. Override only for
            tests that want to point at a fixture package.

    Returns:
        Migrations sorted ascending by ``order``. Empty when no
        migration files exist.

    Raises:
        MigrationError: A discovered module is missing one of the
            required attributes (``name``, ``from_version``,
            ``to_version``, ``apply``).
    """
    package = importlib.import_module(package_name)
    package_path = getattr(package, "__path__", None)
    if package_path is None:  # pragma: no cover - defensive
        raise MigrationError(f"Package '{package_name}' is not a package (no __path__).")

    discovered: list[DiscoveredMigration] = []
    for module_info in pkgutil.iter_modules(package_path):
        match = _MIGRATION_FILENAME_RE.match(module_info.name)
        if match is None:
            continue
        order = int(match.group(1))
        fully_qualified = f"{package_name}.{module_info.name}"
        module = importlib.import_module(fully_qualified)
        for required in ("name", "from_version", "to_version", "apply"):
            if not hasattr(module, required):
                raise MigrationError(
                    f"Migration {fully_qualified!r} is missing required attribute '{required}'."
                )
        discovered.append(
            DiscoveredMigration(
                order=order,
                name=str(module.name),
                from_version=int(module.from_version),
                to_version=int(module.to_version),
                module=module,
            )
        )

    discovered.sort(key=lambda m: m.order)
    return discovered


async def run_migrations(db: AsyncIOMotorDatabase[dict[str, object]]) -> list[DiscoveredMigration]:
    """Execute every discovered migration in order.

    Each migration's ``apply`` is awaited in turn. The number of
    documents it touched is logged via the standard
    ``external_call`` observability shape (``provider="migrations"``)
    so dashboards can spot a migration that should have been a no-op
    but suddenly modified rows on a quiet cluster.

    Idempotency contract: every migration must return without writes
    if there are no documents at its ``from_version``. This function
    does NOT track which migrations have already run — re-execution
    on a stable cluster is expected to be a sequence of no-ops.

    Args:
        db: The Motor database handle to pass through to each
            migration's ``apply``.

    Returns:
        The list of migrations that were executed, in execution
        order.

    Raises:
        MigrationError: A migration's ``apply`` raised. The original
            exception is chained via ``__cause__`` and the FastAPI
            lifespan will propagate the failure so the process
            crashes before accepting traffic.
    """
    discovered = discover_migrations()
    for migration in discovered:
        started = time.perf_counter()
        try:
            modified = await migration.module.apply(db)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            # ``migration_name`` (not ``name``) — the stdlib LogRecord
            # already owns a ``name`` attribute and ``extra=`` collisions
            # raise ``KeyError`` inside the logging module.
            log_call(
                provider="migrations",
                endpoint="migration.failed",
                latency_ms=duration_ms,
                status="failed",
                extra={
                    "migration_name": migration.name,
                    "from_version": migration.from_version,
                    "to_version": migration.to_version,
                    "error": str(exc),
                },
            )
            raise MigrationError(
                f"Migration {migration.name!r} failed: {exc}",
            ) from exc

        duration_ms = (time.perf_counter() - started) * 1000
        log_call(
            provider="migrations",
            endpoint="migration.applied",
            latency_ms=duration_ms,
            status="ok",
            extra={
                "migration_name": migration.name,
                "from_version": migration.from_version,
                "to_version": migration.to_version,
                "modified_count": int(modified),
                "duration_ms": duration_ms,
            },
        )
    return discovered


__all__ = [
    "DiscoveredMigration",
    "MigrationError",
    "discover_migrations",
    "run_migrations",
]
