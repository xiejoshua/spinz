"""Unit tests for :mod:`auxd_api.migrations.runner` (T030).

Coverage:

* Discovery finds the bundled ``001_initial`` migration and parses its
  front-matter (``from_version=0``, ``to_version=1``).
* Sort order: ``002_*`` runs after ``001_*`` regardless of import-time
  side-effects.
* No-op happy path: 001 on an empty DB returns ``0`` and a
  ``migration.applied`` event is logged.
* Skip-already-applied: a migration whose ``from_version`` does not
  match any document selects zero rows and reports ``modified_count=0``.
* Fail-loud: a migration that raises bubbles a :class:`MigrationError`
  out of the runner — the runtime app must crash, not swallow.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest
from mongomock_motor import AsyncMongoMockClient

from auxd_api import migrations as migrations_pkg
from auxd_api.migrations import runner as runner_module
from auxd_api.migrations.runner import (
    DiscoveredMigration,
    MigrationError,
    discover_migrations,
    run_migrations,
)


def _capture_log_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace :func:`runner_module.log_call` with an in-memory recorder.

    Returns a list each ``log_call`` invocation appends a dict to. We
    spy on the runner's namespaced import (not the source module) so
    the production code path is exercised exactly as it would be at
    runtime, without depending on a global-logger handler state that
    the production lifespan re-installs via ``configure_logging``.
    """
    events: list[dict[str, Any]] = []

    def _spy(
        *,
        provider: str,
        endpoint: str,
        latency_ms: float,
        status: str | int,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            {
                "provider": provider,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "status": status,
                "request_id": request_id,
                "extra": dict(extra) if extra else {},
            }
        )

    monkeypatch.setattr(runner_module, "log_call", _spy)
    return events


def _fresh_db() -> Any:
    """Return a fresh mongomock database — no global state shared."""
    return AsyncMongoMockClient()["auxd_migration_test"]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discover_migrations_finds_initial() -> None:
    """The bundled ``001_initial`` migration is discoverable and parsed."""
    discovered = discover_migrations()
    assert any(m.name == "001_initial" for m in discovered)
    initial = next(m for m in discovered if m.name == "001_initial")
    assert initial.from_version == 0
    assert initial.to_version == 1
    assert initial.order == 1


@pytest.fixture
def _virtual_002_migration() -> Iterator[None]:
    """Inject a stub ``002_stub`` module under :mod:`auxd_api.migrations`.

    The package's filesystem is walked via :func:`pkgutil.iter_modules`
    which honours module attributes installed via :data:`sys.modules`.
    By assigning a synthetic module to the package namespace + the
    parent package's ``__path__`` we add a sortable migration without
    writing a real file (and without polluting the source tree).
    """
    # ``pkgutil.iter_modules`` walks the package's ``__path__`` on
    # disk, so we can't fake a new module through ``sys.modules`` alone.
    # Instead, write the stub into a fresh temporary directory and
    # monkeypatch ``auxd_api.migrations.__path__``.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        # Mirror the real ``001_initial`` so discovery sees an ordered pair.
        (tmp / "__init__.py").write_text("", encoding="utf-8")
        (tmp / "001_alpha.py").write_text(
            "name = '001_alpha'\n"
            "from_version = 0\n"
            "to_version = 1\n"
            "async def apply(db):\n"
            "    return 0\n",
            encoding="utf-8",
        )
        (tmp / "002_beta.py").write_text(
            "name = '002_beta'\n"
            "from_version = 1\n"
            "to_version = 2\n"
            "async def apply(db):\n"
            "    return 0\n",
            encoding="utf-8",
        )

        # Build a fresh in-memory package pointing at the temp dir.
        pkg_name = "auxd_test_migrations_stub"
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(tmp)]
        sys.modules[pkg_name] = pkg
        try:
            yield None
        finally:
            for mod_name in list(sys.modules):
                if mod_name.startswith(pkg_name):
                    sys.modules.pop(mod_name, None)


def test_discover_migrations_sort_order(_virtual_002_migration: None) -> None:
    """``002_*`` migrations run after ``001_*`` regardless of import order."""
    discovered = discover_migrations(package_name="auxd_test_migrations_stub")
    names = [m.name for m in discovered]
    assert names == ["001_alpha", "002_beta"]


def test_discover_migrations_raises_when_attr_missing(tmp_path: Any) -> None:
    """A migration missing a required attribute fails discovery cleanly."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        (tmp / "__init__.py").write_text("", encoding="utf-8")
        # Missing ``to_version``.
        (tmp / "001_broken.py").write_text(
            "name = '001_broken'\nfrom_version = 0\nasync def apply(db):\n    return 0\n",
            encoding="utf-8",
        )
        pkg_name = "auxd_test_migrations_broken"
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(tmp)]
        sys.modules[pkg_name] = pkg
        try:
            with pytest.raises(MigrationError, match="to_version"):
                discover_migrations(package_name=pkg_name)
        finally:
            for mod_name in list(sys.modules):
                if mod_name.startswith(pkg_name):
                    sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_migrations_noop_initial_logs_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bundled 001 migration runs cleanly and logs a structured event."""
    events = _capture_log_calls(monkeypatch)
    db = _fresh_db()
    executed = await run_migrations(db)
    assert any(m.name == "001_initial" for m in executed)
    applied = [
        event
        for event in events
        if event["endpoint"] == "migration.applied"
        and event["extra"].get("migration_name") == "001_initial"
    ]
    assert len(applied) == 1
    record = applied[0]
    assert record["status"] == "ok"
    assert record["provider"] == "migrations"
    assert record["extra"]["from_version"] == 0
    assert record["extra"]["to_version"] == 1
    assert record["extra"]["modified_count"] == 0


@pytest.mark.asyncio
async def test_run_migrations_skip_already_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A migration whose ``from_version`` doesn't match the cluster returns 0.

    We swap in a synthetic migration list that selects against a
    ``from_version`` no document carries — the migration reports zero
    modified rows and the runner moves on without error.
    """
    fake = DiscoveredMigration(
        order=99,
        name="099_no_match",
        from_version=42,
        to_version=43,
        module=_FakeMigration(modified=0),  # type: ignore[arg-type]
    )

    def _fake_discover(_pkg: str = "auxd_api.migrations") -> list[DiscoveredMigration]:
        return [fake]

    monkeypatch.setattr(runner_module, "discover_migrations", _fake_discover)

    db = _fresh_db()
    executed = await run_migrations(db)
    assert [m.name for m in executed] == ["099_no_match"]


@pytest.mark.asyncio
async def test_run_migrations_fails_loud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A migration that raises bubbles as :class:`MigrationError`."""

    class _Boom:
        async def apply(self, _db: Any) -> int:
            raise RuntimeError("kaboom")

    fake = DiscoveredMigration(
        order=99,
        name="099_explosive",
        from_version=0,
        to_version=1,
        module=_Boom(),  # type: ignore[arg-type]
    )

    def _fake_discover(_pkg: str = "auxd_api.migrations") -> list[DiscoveredMigration]:
        return [fake]

    monkeypatch.setattr(runner_module, "discover_migrations", _fake_discover)
    events = _capture_log_calls(monkeypatch)

    db = _fresh_db()
    with pytest.raises(MigrationError, match="099_explosive"):
        await run_migrations(db)
    failed = [event for event in events if event["endpoint"] == "migration.failed"]
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert failed[0]["extra"]["migration_name"] == "099_explosive"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeMigration:
    """In-memory stand-in for a migration module used by tests."""

    def __init__(self, *, modified: int) -> None:
        self._modified = modified

    async def apply(self, _db: Any) -> int:
        return self._modified


# Keep the migration package importable even when the test suite hot-reloads
# (defensive — :mod:`auxd_api.migrations` is normally a one-shot import).
_ = migrations_pkg
