"""Integration test: app lifespan invokes the migration runner (T030).

Boots a :class:`TestClient` against the real :mod:`auxd_api.main` app
with the data-layer init no-ops patched in, then asserts the
``migration.applied`` event for ``001_initial`` was emitted exactly
once. Mirror of the contract baked into the FastAPI lifespan:
``init_db`` → ``run_migrations`` → ``init_redis``.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auxd_api import main as main_module
from auxd_api import settings as settings_module
from auxd_api.migrations import runner as runner_module
from auxd_api.migrations.runner import DiscoveredMigration

_REQUIRED_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "DISCOGS_API_TOKEN",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
)


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def test_lifespan_invokes_migration_runner(
    monkeypatch: pytest.MonkeyPatch,
    _clean_env: None,
) -> None:
    """Booting the app fires ``run_migrations`` and the structured event lands.

    The lifespan's :func:`auxd_api.lib.logging.configure_logging` wipes the
    root logger's handlers — including pytest's :class:`caplog` — so this
    test spies on the canonical observability primitive directly rather
    than asserting against captured log records. The unit test for
    :mod:`auxd_api.migrations.runner` already covers the JSON-line shape.
    """

    async def _noop_async(*_args: object, **_kwargs: object) -> None:
        return None

    # Bypass the real data-layer / observability inits — we're testing
    # the lifespan wiring, not those dependencies (their own tests
    # cover them). The DB is replaced with a sentinel so that the
    # migration runner is observably the only thing that walks the
    # bundled package on boot.
    monkeypatch.setattr(main_module, "init_db", _noop_async)
    monkeypatch.setattr(main_module, "close_db", _noop_async)
    monkeypatch.setattr(main_module, "init_redis", _noop_async)
    monkeypatch.setattr(main_module, "close_redis", _noop_async)
    monkeypatch.setattr(main_module, "init_arq_pool", _noop_async)
    monkeypatch.setattr(main_module, "close_arq_pool", _noop_async)

    captured: dict[str, Any] = {}

    def _fake_get_database(_uri: str) -> object:
        sentinel = object()
        captured["db"] = sentinel
        return sentinel

    monkeypatch.setattr(main_module, "get_database", _fake_get_database)

    invocations: list[object] = []

    async def _spy_run(db: Any) -> list[DiscoveredMigration]:
        invocations.append(db)
        # Defer to the real runner via the canonical module reference —
        # mypy --strict prefers an explicit module attribute over a
        # ``getattr`` cast, and ``runner_module`` re-exports the symbol.
        result: list[DiscoveredMigration] = await runner_module.run_migrations(db)
        return result

    monkeypatch.setattr(main_module, "run_migrations", _spy_run)

    # Spy on the canonical observability primitive that ``run_migrations``
    # uses for ``migration.applied``. The runner reaches this module via
    # ``runner_module.log_call``, which it imported into its own namespace
    # at module-load time — patch THAT alias, not the source module.
    structured_events: list[dict[str, Any]] = []

    def _spy_log_call(
        *,
        provider: str,
        endpoint: str,
        latency_ms: float,
        status: str | int,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        structured_events.append(
            {
                "provider": provider,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "status": status,
                "request_id": request_id,
                "extra": dict(extra) if extra else {},
            }
        )

    monkeypatch.setattr(runner_module, "log_call", _spy_log_call)

    with TestClient(main_module.app) as client:
        client.get("/healthz")

    # Spy fired exactly once with the database handle we stubbed.
    assert len(invocations) == 1
    assert invocations[0] is captured["db"]

    # 001_initial logged the canonical structured event.
    applied = [
        event
        for event in structured_events
        if event["endpoint"] == "migration.applied"
        and event["extra"].get("migration_name") == "001_initial"
    ]
    assert len(applied) == 1
    assert applied[0]["status"] == "ok"
    assert applied[0]["provider"] == "migrations"
    assert applied[0]["extra"]["from_version"] == 0
    assert applied[0]["extra"]["to_version"] == 1
    assert applied[0]["extra"]["modified_count"] == 0


# Defensive: ensure the global runner-module is the same object the
# lifespan imports — guards against an accidental re-export drift.
def test_main_uses_canonical_run_migrations() -> None:
    # ``main_module`` doesn't re-export ``run_migrations`` in ``__all__``,
    # so reach for the attribute dynamically — mypy --strict otherwise
    # flags the access even though the attribute exists at runtime.
    main_run = getattr(main_module, "run_migrations")  # noqa: B009
    assert main_run is runner_module.run_migrations
