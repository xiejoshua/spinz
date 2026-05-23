"""Application configuration via Pydantic Settings.

All runtime configuration for the auxd backend is modelled as a single
:class:`Settings` instance loaded from environment variables (and ``.env`` for
local development). The app refuses to start if any required value is missing
or fails validation — there are no silent defaults for secrets.

Highlights:

* ``SESSION_HMAC_KEY`` and ``TOKEN_ENCRYPTION_KEY`` are base64-encoded and
  validated for decoded byte length at construction time (fail loudly with a
  clear message if an operator misconfigures them).
* :func:`get_settings` is :func:`functools.lru_cache`-wrapped so FastAPI
  dependency-injection always sees the same instance.
* :func:`emit_startup_audit` writes a single structured log line at INFO
  (``event=config.loaded``) summarising which integrations are enabled. No
  secret values are ever logged — only booleans / non-sensitive identifiers.

CR-001 (2026-05-22): removed Spotify integration (SPOTIFY_* fields +
``_check_conditional_requirements`` validator) — see
``features/001-auxd-mvp/change-log.md``. The MVP now uses a Letterboxd-style
manual catalog search; an optional Discogs Personal Access Token can be
supplied via ``DISCOGS_API_TOKEN`` to enable the catalog fallback.
"""

from __future__ import annotations

import base64
import binascii
import logging
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    # --- Catalog providers (optional) ------------------------------------
    # CR-001: removed Spotify integration (SPOTIFY_INTEGRATION_ENABLED /
    # SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET fields gone). The MVP catalog
    # is now MusicBrainz-only by default; supplying a Discogs token enables
    # the secondary fallback (see features/001-auxd-mvp/change-log.md).
    DISCOGS_API_TOKEN: str | None = Field(
        default=None,
        description=(
            "Discogs Personal Access Token for catalog fallback. Optional — "
            "without it, the MusicBrainz catalog runs solo."
        ),
    )

    # --- CORS ------------------------------------------------------------
    # `Annotated[..., NoDecode]` opts this field out of pydantic-settings'
    # default JSON decoding for list types. Without it, an env var like
    # `https://a.com,https://b.com` raises SettingsError because the source
    # tries to JSON-parse it before the field validator can intercept.
    # With NoDecode, the raw string reaches `_split_allowed_origins` below.
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description=(
            "Origins permitted to call the API with credentials. "
            "Production: https://xiejoshua.com (the Vercel-deployed frontend). "
            "Local dev: http://localhost:3000 (Next.js dev server). "
            "Accepts comma-separated string OR JSON array via env var."
        ),
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
        default="https://us.i.posthog.com",
        description=(
            "PostHog ingest host. Defaults to PostHog Cloud US ingest endpoint. "
            "EU Cloud: https://eu.i.posthog.com. Self-hosted is no longer the recommended path."
        ),
    )

    # --- Email (optional) ------------------------------------------------
    RESEND_API_KEY: str | None = Field(
        default=None,
        description=(
            "Resend API key (`re_…`). Leave unset to log emails locally instead of sending."
        ),
    )

    # --- Backups (R2, S3-compatible) ------------------------------------
    R2_ACCESS_KEY_ID: str | None = Field(
        default=None,
        description="Cloudflare R2 access key ID. Required for nightly mongodump backup (T010a).",
    )
    R2_SECRET_ACCESS_KEY: str | None = Field(
        default=None,
        description="Cloudflare R2 secret access key. Pair with R2_ACCESS_KEY_ID.",
    )
    R2_ENDPOINT_URL: str | None = Field(
        default=None,
        description="Cloudflare R2 S3-compatible endpoint URL (https://<account>.r2.cloudflarestorage.com).",
    )
    R2_BUCKET_NAME: str = Field(
        default="auxd-backups",
        description="R2 bucket name for mongodump backups (T010a).",
    )
    R2_AVATAR_BUCKET: str = Field(
        default="auxd-avatars",
        description=(
            "R2 bucket name for user-uploaded avatar images (T146). Kept distinct "
            "from R2_BUCKET_NAME so the avatar bucket's public-read ACL doesn't leak "
            "to the (private) mongodump archive."
        ),
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
    VAPID_SUBJECT: str = Field(
        default="mailto:ops@auxd.xiejoshua.com",
        description=(
            "VAPID 'sub' claim — mailto: address or URL identifying the push originator. "
            "Sent on every signed push so upstream services can reach the operator if "
            "anything goes wrong with the subscription."
        ),
    )

    # --- Operator alerting (optional) ------------------------------------
    DISCORD_WEBHOOK_URL: str | None = Field(
        default=None,
        description=(
            "Discord webhook URL for operator alerts (T010 synthetic monitoring + T156 "
            "moderation scan). Leave unset to disable Discord posts; the alert still "
            "lands as a structured log line."
        ),
    )

    # --- Exports (R2 GDPR) -----------------------------------------------
    R2_EXPORT_BUCKET: str = Field(
        default="auxd-exports",
        description=(
            "R2 bucket name for GDPR data-export archives (T153). 24h "
            "signed URLs are issued; the bucket itself is private."
        ),
    )

    # --- Public app URL --------------------------------------------------
    PUBLIC_APP_URL: str = Field(
        default="https://auxd.xiejoshua.com",
        description=(
            "Public frontend base URL used to build click-action deep-links in "
            "push payloads and email CTAs. Override per environment."
        ),
    )
    RESEND_FROM_ADDRESS: str = Field(
        default="auxd <hello@auxd.xiejoshua.com>",
        description=(
            "Default 'from' address used by the Resend email adapter. Format follows "
            "RFC-5322 (e.g. ``auxd <hello@auxd.xiejoshua.com>``)."
        ),
    )

    # --- Validators ------------------------------------------------------
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_allowed_origins(cls, v: object) -> object:
        """Normalise env-string input into a list[str].

        Pairs with the ``NoDecode`` annotation on the field. With NoDecode,
        the raw env string reaches this validator instead of being JSON-
        decoded by the env source. We accept either comma-separated
        (``a,b,c``) or JSON-array (``["a","b","c"]``) forms; lists pass
        through untouched (e.g. when an init kwarg is used in tests).
        """
        if isinstance(v, str):
            stripped = v.strip()
            # Try JSON first for the array form — preserves the legacy contract.
            if stripped.startswith("["):
                import json

                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except json.JSONDecodeError:
                    pass  # fall through to comma-split
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

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

    # CR-001: removed ``_check_conditional_requirements`` model_validator that
    # enforced Spotify client credentials — there are no Spotify-specific
    # conditional requirements at MVP anymore.


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
            # CR-001: ``spotify_enabled`` removed; ``discogs_enabled`` replaces it
            # as the catalog-fallback signal.
            "discogs_enabled": settings.DISCOGS_API_TOKEN is not None,
            "sentry_enabled": settings.SENTRY_DSN is not None,
            "posthog_enabled": settings.POSTHOG_API_KEY is not None,
            "resend_enabled": settings.RESEND_API_KEY is not None,
            "r2_backups_enabled": (
                settings.R2_ACCESS_KEY_ID is not None
                and settings.R2_SECRET_ACCESS_KEY is not None
                and settings.R2_ENDPOINT_URL is not None
            ),
            "web_push_enabled": settings.VAPID_PRIVATE_KEY is not None,
            "posthog_host": settings.POSTHOG_HOST,
        },
    )
