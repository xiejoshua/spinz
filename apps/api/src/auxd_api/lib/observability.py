"""Observability primitives — Constitution Principle V (NON-NEGOTIABLE).

Every external API call, every notification dispatch, and every uncaught
error in the auxd backend MUST route through one of the three primitives
exposed here. The module deliberately keeps a tiny surface so feature code
has no excuse to bypass it.

Public surface
==============
* :func:`log_call` — emit a single structured ``external_call`` JSON log
  line capturing provider, endpoint, latency, status, and optional
  correlation id + arbitrary ``extra`` fields. The plan's contract for
  every outbound call (provider HTTP, Postmark, even PostHog itself).
* :func:`emit_event` — fire-and-forget PostHog wrapper. No-op when the
  ``POSTHOG_API_KEY`` env var is unset, and *never* raises into the
  request path even if PostHog itself fails. Anonymous events are
  supported by mapping ``user_id=None`` to the sentinel
  ``distinct_id="anonymous"`` (PostHog requires a non-empty distinct_id).
* :func:`init_sentry` — idempotent Sentry SDK initialiser with the
  FastAPI + AsyncIO integrations wired in. Returns ``True`` when init
  happens, ``False`` when ``dsn`` is unset (no-op mode) — so the caller
  in ``main.py`` (T015a) can emit a clear startup log line either way.

Design notes
============
- ``log_call`` writes plain ``logging.INFO`` records but installs (once,
  idempotently) a :class:`_JSONFormatter` on a dedicated logger named
  ``auxd.observability``. We use stdlib ``logging`` — no extra deps —
  because Fly captures stdout. The formatter emits a compact one-line
  JSON object per record so log shippers can parse without a regex.
- ``emit_event`` lazy-constructs the PostHog client on first use. Doing
  it at import-time would couple module load to settings being valid,
  which makes test setup painful and is unnecessary: the first event
  fires plenty late.
- ``init_sentry`` tracks its own ``_sentry_initialized`` flag so a second
  call is a true no-op (important: ``sentry_sdk.init`` itself is *not*
  idempotent in the "do nothing" sense — calling it twice re-installs
  the hub. We must guard externally).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

import sentry_sdk
from posthog import Posthog
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from auxd_api.settings import get_settings

__all__ = ["emit_event", "init_sentry", "log_call"]


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


_LOGGER_NAME = "auxd.observability"
_handler_installed = False


class _JSONFormatter(logging.Formatter):
    """Format every log record as a one-line JSON object.

    Standard ``LogRecord`` attributes are skipped; everything we want
    surfaced is pushed in via ``logging.LogRecord.__dict__`` by the
    ``extra=`` kwarg in :func:`log_call`. Field ordering is best-effort:
    we emit ``event`` and ``timestamp`` first so a human grepping
    stdout sees the most useful fields up front.
    """

    # Attributes that always exist on a LogRecord and that we don't want
    # to mirror into the JSON payload (they'd just be noise).
    _RESERVED: frozenset[str] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {}
        # Pull caller-supplied fields first; the canonical "event" key may
        # have been provided via extra=, and we want it (plus timestamp)
        # to lead the JSON document.
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in self._RESERVED and not k.startswith("_")
        }
        if "event" in extras:
            payload["event"] = extras.pop("event")
        payload["timestamp"] = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload.update(extras)
        # ``record.getMessage()`` is the rendered ``msg % args`` string; we
        # include it under ``message`` only if it differs from ``event`` to
        # avoid duplication when callers pass the same string for both.
        rendered = record.getMessage()
        if rendered and rendered != payload.get("event"):
            payload["message"] = rendered
        return json.dumps(payload, default=str, separators=(",", ":"))


def _install_handler_once() -> logging.Logger:
    """Attach the JSON formatter to ``auxd.observability`` on first use."""
    global _handler_installed
    logger = logging.getLogger(_LOGGER_NAME)
    if not _handler_installed:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # Don't let parent loggers double-emit our structured line in
        # tests / dev where the root logger is configured with a basic
        # formatter. ``caplog`` still captures records via its own
        # handler that gets attached at the root level.
        logger.propagate = True
        _handler_installed = True
    return logger


def log_call(
    *,
    provider: str,
    endpoint: str,
    latency_ms: float,
    status: int | str,
    request_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured ``external_call`` log line at INFO.

    The single canonical observability event for every outbound call —
    HTTP to Spotify/MusicBrainz, Postmark email dispatch, even PostHog
    failures (yes, we log PostHog failures via this same helper).

    Args:
        provider: Stable short name of the external dependency.
            Examples: ``"spotify"``, ``"musicbrainz"``, ``"postmark"``,
            ``"posthog"``, ``"sentry"``.
        endpoint: Identifier of the specific operation invoked — usually
            a URL path or a logical command name (``"send_email"``).
        latency_ms: Wall-clock duration of the call in milliseconds.
        status: HTTP status code (int) or a string sentinel describing
            an outcome that isn't a status code (``"ok"``, ``"timeout"``,
            ``"circuit_open"``, ``"failed"``).
        request_id: Optional correlation id from the inbound request.
            Omitted entirely from the JSON output when ``None`` so log
            ingestors don't index a useless null column.
        extra: Optional bag of additional non-secret fields to attach.
            Caller-owned: do not pass tokens, raw payloads, or PII.
    """
    logger = _install_handler_once()
    fields: dict[str, Any] = {
        "event": "external_call",
        "provider": provider,
        "endpoint": endpoint,
        "latency_ms": latency_ms,
        "status": status,
    }
    if request_id is not None:
        fields["request_id"] = request_id
    if extra:
        fields.update(extra)
    logger.info("external_call", extra=fields)


# ---------------------------------------------------------------------------
# PostHog wrapper
# ---------------------------------------------------------------------------


# Sentinel used for anonymous PostHog events. PostHog requires a non-empty
# ``distinct_id`` — using a stable string lets pre-login funnels still
# group correctly while keeping users genuinely anonymous.
_ANONYMOUS_DISTINCT_ID = "anonymous"

_posthog_client: Posthog | None = None
_posthog_init_attempted = False


def _get_posthog_client() -> Posthog | None:
    """Return a memoised PostHog client, or ``None`` if disabled.

    The first call reads settings and constructs the client. If
    ``POSTHOG_API_KEY`` is not set the function permanently returns
    ``None`` (cached on ``_posthog_init_attempted``). If the
    construction itself raises we log it and disable PostHog for the
    rest of the process lifetime — we'd rather lose analytics than fail
    a request.
    """
    global _posthog_client, _posthog_init_attempted
    if _posthog_init_attempted:
        return _posthog_client
    _posthog_init_attempted = True
    settings = get_settings()
    if settings.POSTHOG_API_KEY is None:
        return None
    try:
        _posthog_client = Posthog(
            project_api_key=settings.POSTHOG_API_KEY,
            host=settings.POSTHOG_HOST,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log_call(
            provider="posthog",
            endpoint="client_init",
            latency_ms=0.0,
            status="failed",
            extra={"error": str(exc)},
        )
        _posthog_client = None
    return _posthog_client


def emit_event(
    *,
    user_id: str | None,
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget PostHog event capture.

    Per the plan's anti-Goodreads-firehose discipline (plan §15), this
    helper:

    * Is a no-op when ``POSTHOG_API_KEY`` is unset — useful for local
      dev and CI where we don't want pollution in the real PostHog
      project.
    * Never blocks the request path beyond PostHog's own in-process
      queue (the SDK ships events on a background thread).
    * Never raises. Construction errors and capture errors are routed
      through :func:`log_call` with ``provider="posthog"`` and
      ``status="failed"`` so the failure is observable without
      poisoning the caller.

    Args:
        user_id: PostHog ``distinct_id``. ``None`` is allowed for
            pre-authentication events (login page view etc.) and is
            mapped to the literal string ``"anonymous"``.
        event: Event name (e.g. ``"recap_viewed"``).
        properties: Optional event properties dict. No secrets.
    """
    client = _get_posthog_client()
    if client is None:
        return
    distinct_id = user_id if user_id is not None else _ANONYMOUS_DISTINCT_ID
    try:
        client.capture(
            event=event,
            distinct_id=distinct_id,
            properties=properties,
        )
    except Exception as exc:
        log_call(
            provider="posthog",
            endpoint=event,
            latency_ms=0.0,
            status="failed",
            extra={"error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Sentry init
# ---------------------------------------------------------------------------


_sentry_initialized = False


def init_sentry(
    *,
    dsn: str | None,
    environment: str,
    release: str | None = None,
) -> bool:
    """Initialise the Sentry SDK with our standard integration set.

    Called once from ``main.py`` (T015a) during FastAPI app setup. The
    function is idempotent: a second call with the same or different
    arguments is a no-op once the SDK has been initialised — preventing
    the hub from being re-installed (which would silently break the
    integrations attached on first init).

    Sample-rate policy (MVP):
        * ``traces_sample_rate=0.0`` — distributed tracing is delivered
          via OpenTelemetry (T015a), not Sentry, so we don't pay twice.
        * ``profiles_sample_rate=0.0`` — profiling is off (not in plan).
        * Error capture defaults to 1.0 (always capture).

    Args:
        dsn: Sentry DSN string, or ``None``/empty to run in no-op mode.
        environment: ``Environment`` enum string value
            (``"local"``/``"dev"``/``"staging"``/``"production"``).
        release: Optional release identifier (e.g. git SHA).

    Returns:
        ``True`` if Sentry was initialised on this call, ``False`` if
        ``dsn`` was missing OR if Sentry was already initialised earlier
        in the process.
    """
    global _sentry_initialized
    if not dsn:
        return False
    if _sentry_initialized:
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[FastApiIntegration(), AsyncioIntegration()],
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
    )
    _sentry_initialized = True
    return True
