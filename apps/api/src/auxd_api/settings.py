"""Application configuration via Pydantic Settings.

All runtime configuration for the auxd backend is modelled as a single
:class:`Settings` instance loaded from environment variables (and ``.env`` for
local development). The app refuses to start if any required value is missing
or fails validation — there are no silent defaults for secrets.

Highlights:

* ``SESSION_HMAC_KEY`` and ``TOKEN_ENCRYPTION_KEY`` are base64-encoded and
  validated for decoded byte length at construction time (fail loudly with a
  clear message if an operator misconfigures them).
* Conditional requirements are enforced by a ``model_validator``: e.g. enabling
  the Spotify integration requires both client credentials.
* :func:`get_settings` is :func:`functools.lru_cache`-wrapped so FastAPI
  dependency-injection always sees the same instance.
* :func:`emit_startup_audit` writes a single structured log line at INFO
  (``event=config.loaded``) summarising which integrations are enabled. No
  secret values are ever logged — only booleans / non-sensitive identifiers.
"""

from __future__ import annotations

import base64
import binascii
import logging
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment name."""

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Standard logging level names accepted by :mod:`logging`."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


_SESSION_HMAC_MIN_BYTES = 32
_TOKEN_ENCRYPTION_BYTES = 32


def _decode_b64_key(value: str, field_name: str) -> bytes:
    """Decode a base64-encoded secret, raising a clear error on failure."""
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be valid base64-encoded bytes (got error: {exc})"
        ) from exc


class Settings(BaseSettings):
    """Validated application configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    # --- Core ------------------------------------------------------------
    ENVIRONMENT: Environment = Field(
        default=Environment.LOCAL,
        description="Deployment environment (local/dev/staging/production).",
    )
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        description="Root logger level.",
    )

    # --- Datastores ------------------------------------------------------
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017/auxd_dev",
        description="MongoDB connection string including database name.",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL used for sessions, queues, and rate limiting.",
    )

    # --- Crypto secrets (no defaults — fail loud) ------------------------
    SESSION_HMAC_KEY: Annotated[
        str,
        Field(
            description=(
                "Base64-encoded HMAC key for session cookie signing. Must decode to >= 32 bytes."
            ),
        ),
    ]
    TOKEN_ENCRYPTION_KEY: Annotated[
        str,
        Field(
            description=(
                "Base64-encoded AES-256 key for envelope-encrypting OAuth tokens. "
                "Must decode to exactly 32 bytes."
            ),
        ),
    ]

    # --- Feature flags ---------------------------------------------------
    SPOTIFY_INTEGRATION_ENABLED: bool = Field(
        default=True,
        description="Toggle Spotify OAuth + sync features.",
    )

    # --- Spotify (required iff SPOTIFY_INTEGRATION_ENABLED) --------------
    SPOTIFY_CLIENT_ID: str | None = Field(
        default=None,
        description="Spotify app client ID (required when Spotify integration is enabled).",
    )
    SPOTIFY_CLIENT_SECRET: str | None = Field(
        default=None,
        description="Spotify app client secret (required when Spotify integration is enabled).",
    )

    # --- Observability (optional) ----------------------------------------
    SENTRY_DSN: str | None = Field(
        default=None,
        description="Sentry DSN. Leave unset to disable Sentry.",
    )
    POSTHOG_API_KEY: str | None = Field(
        default=None,
        description="PostHog project API key. Leave unset to disable PostHog.",
    )
    POSTHOG_HOST: str = Field(
        default="https://app.posthog.com",
        description="PostHog ingest host (override for self-hosted deployments).",
    )

    # --- Email (optional) ------------------------------------------------
    POSTMARK_API_KEY: str | None = Field(
        default=None,
        description="Postmark server token. Leave unset to log emails locally instead of sending.",
    )

    # --- Web Push --------------------------------------------------------
    VAPID_PUBLIC_KEY: str = Field(
        default=(
            "BDiJd1rvukJ-A2OmXOFR8n3ysqxSXrLkV8zUCdG48tybCANxC7nAKx2IdgsELt_mR4BT1"
            "onkqXDTV-ZicekBDvE"
        ),
        description="VAPID public key broadcast to browsers for Web Push subscriptions.",
    )
    VAPID_PRIVATE_KEY: str | None = Field(
        default=None,
        description="VAPID private key. Required when push delivery is enabled.",
    )

    # --- Validators ------------------------------------------------------
    @field_validator("SESSION_HMAC_KEY")
    @classmethod
    def _validate_session_hmac_key(cls, v: str, info: ValidationInfo) -> str:
        decoded = _decode_b64_key(v, info.field_name or "SESSION_HMAC_KEY")
        if len(decoded) < _SESSION_HMAC_MIN_BYTES:
            raise ValueError(
                f"SESSION_HMAC_KEY must decode to at least {_SESSION_HMAC_MIN_BYTES} bytes "
                f"(got {len(decoded)} bytes after base64 decode)."
            )
        return v

    @field_validator("TOKEN_ENCRYPTION_KEY")
    @classmethod
    def _validate_token_encryption_key(cls, v: str, info: ValidationInfo) -> str:
        decoded = _decode_b64_key(v, info.field_name or "TOKEN_ENCRYPTION_KEY")
        if len(decoded) != _TOKEN_ENCRYPTION_BYTES:
            raise ValueError(
                f"TOKEN_ENCRYPTION_KEY must decode to exactly {_TOKEN_ENCRYPTION_BYTES} bytes "
                f"(got {len(decoded)} bytes after base64 decode)."
            )
        return v

    @model_validator(mode="after")
    def _check_conditional_requirements(self) -> Settings:
        if self.SPOTIFY_INTEGRATION_ENABLED:
            missing: list[str] = []
            if not self.SPOTIFY_CLIENT_ID:
                missing.append("SPOTIFY_CLIENT_ID")
            if not self.SPOTIFY_CLIENT_SECRET:
                missing.append("SPOTIFY_CLIENT_SECRET")
            if missing:
                joined = ", ".join(missing)
                raise ValueError(
                    f"SPOTIFY_INTEGRATION_ENABLED=true requires: {joined}. "
                    "Set the missing variable(s) or set SPOTIFY_INTEGRATION_ENABLED=false."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, validated :class:`Settings` instance.

    Construction is memoised so FastAPI dependency-injection (and any other
    caller) always sees the same object. To rebuild after a test mutates the
    environment, call ``get_settings.cache_clear()``.
    """
    # All values come from env vars / .env file at runtime.
    return Settings()


def emit_startup_audit(settings: Settings, logger: logging.Logger) -> None:
    """Emit a single ``config.loaded`` log line summarising active configuration.

    Only non-secret values and booleans are logged. This satisfies the
    "happy-path startup writes a config audit log line" Done criterion for
    T029 and gives operators a single grep-able anchor confirming which
    integrations are wired in a given environment.
    """
    logger.info(
        "config.loaded",
        extra={
            "event": "config.loaded",
            "environment": settings.ENVIRONMENT.value,
            "log_level": settings.LOG_LEVEL.value,
            "spotify_enabled": settings.SPOTIFY_INTEGRATION_ENABLED,
            "sentry_enabled": settings.SENTRY_DSN is not None,
            "posthog_enabled": settings.POSTHOG_API_KEY is not None,
            "postmark_enabled": settings.POSTMARK_API_KEY is not None,
            "web_push_enabled": settings.VAPID_PRIVATE_KEY is not None,
            "posthog_host": settings.POSTHOG_HOST,
        },
    )
