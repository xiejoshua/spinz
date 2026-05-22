"""Unit tests for :mod:`auxd_api.settings`."""

from __future__ import annotations

import base64
import logging
import secrets
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from auxd_api import settings as settings_module
from auxd_api.settings import (
    Environment,
    LogLevel,
    Settings,
    emit_startup_audit,
    get_settings,
)


def _b64(num_bytes: int) -> str:
    """Return a base64-encoded random key of exactly ``num_bytes`` decoded length."""
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


# All env vars that Settings recognises. We clear all of them at the start of
# every test so each case has a clean slate independent of CI runner env.
_ALL_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "SPOTIFY_INTEGRATION_ENABLED",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:  # type: ignore[no-untyped-def]
    """Strip all auxd env vars and disable .env file discovery during tests."""
    for key in _ALL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    # Switch CWD to a tmp dir so pydantic-settings won't pick up a real .env.
    monkeypatch.chdir(tmp_path)
    # Reset the lru_cache between tests.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_minimum_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the smallest env that allows Settings() to construct (Spotify disabled)."""
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")


def test_minimal_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_required(monkeypatch)

    cfg = Settings()

    assert cfg.ENVIRONMENT is Environment.LOCAL
    assert cfg.LOG_LEVEL is LogLevel.INFO
    assert cfg.MONGODB_URI == "mongodb://localhost:27017/auxd_dev"
    assert cfg.REDIS_URL == "redis://localhost:6379/0"
    assert cfg.POSTHOG_HOST == "https://us.i.posthog.com"
    assert cfg.SPOTIFY_INTEGRATION_ENABLED is False
    assert cfg.SENTRY_DSN is None
    assert cfg.POSTHOG_API_KEY is None
    assert cfg.RESEND_API_KEY is None
    assert cfg.R2_ACCESS_KEY_ID is None
    assert cfg.R2_BUCKET_NAME == "auxd-backups"
    assert cfg.VAPID_PRIVATE_KEY is None


def test_missing_session_hmac_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "SESSION_HMAC_KEY" in str(exc_info.value)


def test_invalid_session_hmac_key_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(16))  # only 16 bytes after decode
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    msg = str(exc_info.value)
    assert "SESSION_HMAC_KEY" in msg
    assert "at least 32 bytes" in msg


def test_invalid_token_encryption_key_wrong_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(31))  # off-by-one short
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    msg_short = str(exc_info.value)
    assert "TOKEN_ENCRYPTION_KEY" in msg_short
    assert "exactly 32 bytes" in msg_short

    # And also reject 33 bytes (too long).
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(33))
    with pytest.raises(ValidationError) as exc_info_long:
        Settings()
    assert "exactly 32 bytes" in str(exc_info_long.value)


def test_spotify_enabled_requires_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "true")
    # Intentionally omit SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET.

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    msg = str(exc_info.value)
    assert "SPOTIFY_CLIENT_ID" in msg
    assert "SPOTIFY_CLIENT_SECRET" in msg


def test_spotify_disabled_no_secrets_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")

    cfg = Settings()

    assert cfg.SPOTIFY_INTEGRATION_ENABLED is False
    assert cfg.SPOTIFY_CLIENT_ID is None
    assert cfg.SPOTIFY_CLIENT_SECRET is None


def test_emit_startup_audit_logs_one_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_key = _b64(32)
    token_key = _b64(32)
    monkeypatch.setenv("SESSION_HMAC_KEY", session_key)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", token_key)
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-secret")
    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.example/1")

    cfg = Settings()
    logger = logging.getLogger("auxd_api.test_settings")

    with caplog.at_level(logging.INFO, logger=logger.name):
        emit_startup_audit(cfg, logger)

    records = [r for r in caplog.records if r.name == logger.name]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.INFO
    assert record.message == "config.loaded"
    assert record.event == "config.loaded"  # type: ignore[attr-defined]
    assert record.spotify_enabled is True  # type: ignore[attr-defined]
    assert record.sentry_enabled is True  # type: ignore[attr-defined]
    assert record.posthog_enabled is False  # type: ignore[attr-defined]
    assert record.environment == "local"  # type: ignore[attr-defined]

    # Make sure no secret values leaked into any field of the log record.
    record_dump = repr(record.__dict__)
    assert session_key not in record_dump
    assert token_key not in record_dump
    assert "spotify-secret" not in record_dump
    assert "https://public@sentry.example/1" not in record_dump


def test_get_settings_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_required(monkeypatch)

    # Ensure the cache is empty (fixture already does this, but be explicit).
    settings_module.get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
