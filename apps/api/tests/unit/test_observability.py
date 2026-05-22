"""Unit tests for :mod:`auxd_api.lib.observability` (Constitution Principle V)."""

from __future__ import annotations

import base64
import json
import logging
import secrets
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock

import pytest

from auxd_api import settings as settings_module
from auxd_api.lib import observability
from auxd_api.lib.observability import emit_event, init_sentry, log_call

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_REQUIRED_ENV_KEYS = (
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
    "POSTMARK_API_KEY",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
)


def _b64(num_bytes: int) -> str:
    """Return a base64-encoded random key of exactly ``num_bytes`` decoded length."""
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """Reset module-level state and env between tests so each starts clean."""
    # Wipe env so settings construction is deterministic.
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")
    settings_module.get_settings.cache_clear()

    # Reset observability module globals so e.g. PostHog client is not
    # leaked between tests.
    observability._posthog_client = None
    observability._posthog_init_attempted = False
    observability._sentry_initialized = False

    yield

    settings_module.get_settings.cache_clear()
    observability._posthog_client = None
    observability._posthog_init_attempted = False
    observability._sentry_initialized = False


def _parse_observability_record(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    """Extract and JSON-parse the structured record emitted by ``log_call``."""
    records = [r for r in caplog.records if r.name == "auxd.observability"]
    assert len(records) == 1, f"expected one record, got {len(records)}: {records}"
    record = records[0]
    formatter = observability._JSONFormatter()
    payload: dict[str, Any] = json.loads(formatter.format(record))
    return payload


# ---------------------------------------------------------------------------
# log_call
# ---------------------------------------------------------------------------


class TestLogCall:
    def test_log_call_emits_json_line_at_info(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="spotify",
                endpoint="/me/player/recently-played",
                latency_ms=123.4,
                status=200,
            )

        records = [r for r in caplog.records if r.name == "auxd.observability"]
        assert len(records) == 1
        record = records[0]
        assert record.levelno == logging.INFO

        payload = _parse_observability_record(caplog)
        assert payload["event"] == "external_call"
        assert payload["provider"] == "spotify"
        assert payload["endpoint"] == "/me/player/recently-played"
        assert payload["latency_ms"] == 123.4
        assert payload["status"] == 200
        assert "timestamp" in payload
        # ISO-8601 with timezone offset.
        assert "T" in payload["timestamp"]
        assert payload["timestamp"].endswith("+00:00")

    def test_log_call_includes_request_id_when_provided(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="spotify",
                endpoint="/v1/me",
                latency_ms=42.0,
                status=200,
                request_id="req-abc-123",
            )

        payload = _parse_observability_record(caplog)
        assert payload["request_id"] == "req-abc-123"

    def test_log_call_omits_request_id_when_none(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="spotify",
                endpoint="/v1/me",
                latency_ms=42.0,
                status=200,
                request_id=None,
            )

        payload = _parse_observability_record(caplog)
        # Field must be absent (not present with a null value).
        assert "request_id" not in payload

    def test_log_call_includes_extra_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="musicbrainz",
                endpoint="/ws/2/recording",
                latency_ms=212.5,
                status=200,
                extra={"retry_count": 2, "cached": False},
            )

        payload = _parse_observability_record(caplog)
        assert payload["retry_count"] == 2
        assert payload["cached"] is False

    def test_log_call_status_can_be_string_or_int(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="spotify",
                endpoint="/v1/me",
                latency_ms=10.0,
                status=200,
            )
        payload_int = _parse_observability_record(caplog)
        assert payload_int["status"] == 200

        caplog.clear()

        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            log_call(
                provider="spotify",
                endpoint="/v1/me",
                latency_ms=10000.0,
                status="timeout",
            )
        payload_str = _parse_observability_record(caplog)
        assert payload_str["status"] == "timeout"


# ---------------------------------------------------------------------------
# emit_event
# ---------------------------------------------------------------------------


class TestEmitEvent:
    def test_emit_event_no_op_without_api_key(self, caplog: pytest.LogCaptureFixture) -> None:
        # Default fixture leaves POSTHOG_API_KEY unset.
        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            emit_event(user_id="user_123", event="recap_viewed")

        # No PostHog records should be emitted because the client is a no-op.
        assert observability._posthog_client is None
        # And no failure log line was generated either.
        ph_records = [
            r
            for r in caplog.records
            if r.name == "auxd.observability" and getattr(r, "provider", None) == "posthog"
        ]
        assert ph_records == []

    def test_emit_event_calls_posthog_capture_when_key_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test_key")
        monkeypatch.setenv("POSTHOG_HOST", "https://posthog.example")
        settings_module.get_settings.cache_clear()

        captured: dict[str, Any] = {}

        def fake_capture(self: Any, **kwargs: Any) -> str:
            captured.update(kwargs)
            return "event-uuid"

        monkeypatch.setattr("posthog.Posthog.capture", fake_capture)

        emit_event(
            user_id="user_123",
            event="recap_viewed",
            properties={"week": "2026-W21"},
        )

        assert captured["event"] == "recap_viewed"
        assert captured["distinct_id"] == "user_123"
        assert captured["properties"] == {"week": "2026-W21"}

    def test_emit_event_swallows_posthog_failures(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test_key")
        settings_module.get_settings.cache_clear()

        def boom(self: Any, **kwargs: Any) -> str:
            raise RuntimeError("posthog exploded")

        monkeypatch.setattr("posthog.Posthog.capture", boom)

        with caplog.at_level(logging.INFO, logger="auxd.observability"):
            # Must not raise.
            emit_event(user_id="user_123", event="recap_viewed")

        # A failure log line must have been written.
        failures = [
            r
            for r in caplog.records
            if r.name == "auxd.observability"
            and getattr(r, "provider", None) == "posthog"
            and getattr(r, "status", None) == "failed"
        ]
        assert len(failures) == 1
        assert getattr(failures[0], "endpoint", None) == "recap_viewed"

    def test_emit_event_anonymous_user_id_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``user_id=None`` is mapped to the sentinel ``distinct_id='anonymous'``."""
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test_key")
        settings_module.get_settings.cache_clear()

        captured: dict[str, Any] = {}

        def fake_capture(self: Any, **kwargs: Any) -> str:
            captured.update(kwargs)
            return "event-uuid"

        monkeypatch.setattr("posthog.Posthog.capture", fake_capture)

        emit_event(user_id=None, event="login_page_viewed")

        assert captured["distinct_id"] == "anonymous"
        assert captured["event"] == "login_page_viewed"


# ---------------------------------------------------------------------------
# init_sentry
# ---------------------------------------------------------------------------


class TestInitSentry:
    def test_init_sentry_returns_false_when_dsn_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = Mock()
        monkeypatch.setattr("sentry_sdk.init", mock_init)

        assert init_sentry(dsn=None, environment="local") is False
        assert mock_init.call_count == 0

        # Empty string is also treated as no-op.
        assert init_sentry(dsn="", environment="local") is False
        assert mock_init.call_count == 0

    def test_init_sentry_returns_true_when_dsn_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = Mock()
        monkeypatch.setattr("sentry_sdk.init", mock_init)

        result = init_sentry(
            dsn="https://public@sentry.example/1",
            environment="production",
        )
        assert result is True
        assert mock_init.call_count == 1

    def test_init_sentry_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = Mock()
        monkeypatch.setattr("sentry_sdk.init", mock_init)

        first = init_sentry(dsn="https://public@sentry.example/1", environment="production")
        second = init_sentry(dsn="https://public@sentry.example/1", environment="production")
        assert first is True
        assert second is False
        assert mock_init.call_count == 1

    def test_init_sentry_passes_environment_and_release(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_init = Mock()
        monkeypatch.setattr("sentry_sdk.init", mock_init)

        init_sentry(
            dsn="https://public@sentry.example/1",
            environment="staging",
            release="git-abc123",
        )

        assert mock_init.call_count == 1
        kwargs = mock_init.call_args.kwargs
        assert kwargs["dsn"] == "https://public@sentry.example/1"
        assert kwargs["environment"] == "staging"
        assert kwargs["release"] == "git-abc123"
        assert kwargs["traces_sample_rate"] == 0.0
        assert kwargs["profiles_sample_rate"] == 0.0
        # Integrations include FastAPI + AsyncIO.
        integration_names = {type(i).__name__ for i in kwargs["integrations"]}
        assert "FastApiIntegration" in integration_names
        assert "AsyncioIntegration" in integration_names
