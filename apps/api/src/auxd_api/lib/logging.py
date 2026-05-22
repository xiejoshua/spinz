"""Root-logger JSON formatter — Constitution Principle V (T011).

Production logs land on Fly's stdout collector. Fly does line-based
ingestion, so emitting one JSON object per line makes every log line
queryable without bespoke parsers. :func:`configure_logging` installs
the formatter on the root logger so anything routed through stdlib
``logging`` — FastAPI's own log records, uvicorn access logs, third-party
libraries — gets the same treatment.

This complements :mod:`auxd_api.lib.observability`, which owns the
narrower ``auxd.observability`` logger used by :func:`log_call`. Splitting
the two keeps the high-cardinality ``external_call`` event distinct from
generic application logs while sharing the same JSON shape.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

__all__ = ["JSONFormatter", "configure_logging"]


# Attributes that ``logging.LogRecord`` always carries. The JSON formatter
# strips these so the emitted payload only contains caller-supplied fields
# plus our canonical envelope keys (``timestamp``, ``level``, ``logger``,
# ``message``).
_RESERVED_LOG_RECORD_ATTRS: Final[frozenset[str]] = frozenset(
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


class JSONFormatter(logging.Formatter):
    """Format every log record as a one-line JSON object.

    Envelope keys (always present, always first): ``timestamp``,
    ``level``, ``logger``, ``message``. Anything passed via ``extra=`` on
    the call site is merged on top. Exception info, if any, is rendered
    via :meth:`logging.Formatter.formatException` and attached under
    ``exception`` so a single grep on ``"level":"ERROR"`` yields the
    stack trace alongside the structured fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED_LOG_RECORD_ATTRS and not k.startswith("_")
        }
        payload.update(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str | int = "INFO") -> None:
    """Install :class:`JSONFormatter` on the root logger.

    Idempotent: re-running with a different ``level`` adjusts the level
    in place without stacking handlers. Existing handlers attached to
    the root logger (e.g. ``pytest``'s caplog) are replaced by the JSON
    stdout handler so the test suite sees the structured output the
    rest of the process emits.

    Args:
        level: Logging level as a stdlib level name (``"DEBUG"``,
            ``"INFO"`` etc.) or numeric constant.
    """
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Remove any pre-existing handlers so the JSON stream is canonical.
    # uvicorn / pytest may have wired their own; we want our format.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
