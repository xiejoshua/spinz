"""Unit tests for :mod:`auxd_api.lib.logging` (T011).

Covers the JSON envelope shape, idempotent root-handler installation,
and exception rendering.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest

from auxd_api.lib.logging import JSONFormatter, configure_logging


@pytest.fixture
def _restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


def _make_record(
    *,
    msg: str = "hello",
    level: int = logging.INFO,
    extra: dict[str, object] | None = None,
    name: str = "auxd.test",
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


class TestJSONFormatter:
    def test_emits_canonical_envelope(self) -> None:
        record = _make_record(msg="hello world")
        payload = json.loads(JSONFormatter().format(record))
        assert payload["level"] == "INFO"
        assert payload["logger"] == "auxd.test"
        assert payload["message"] == "hello world"
        # Timestamp is ISO-8601 with timezone; loosely assert via fromisoformat.
        assert payload["timestamp"].endswith("+00:00") or payload["timestamp"].endswith("Z")

    def test_includes_extras(self) -> None:
        record = _make_record(extra={"request_id": "abc-123", "event": "login.attempt"})
        payload = json.loads(JSONFormatter().format(record))
        assert payload["request_id"] == "abc-123"
        assert payload["event"] == "login.attempt"

    def test_renders_exception(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="auxd.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="caught it",
            args=None,
            exc_info=exc_info,
        )
        payload = json.loads(JSONFormatter().format(record))
        assert "exception" in payload
        assert "ValueError: boom" in payload["exception"]


class TestConfigureLogging:
    def test_replaces_existing_handlers(self, _restore_root_logger: None) -> None:
        root = logging.getLogger()
        # Pre-install a handler we can detect.
        sentinel = logging.StreamHandler(io.StringIO())
        root.addHandler(sentinel)
        configure_logging(level="DEBUG")
        assert sentinel not in root.handlers
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)
        assert root.level == logging.DEBUG

    def test_accepts_numeric_level(self, _restore_root_logger: None) -> None:
        configure_logging(level=logging.WARNING)
        assert logging.getLogger().level == logging.WARNING

    def test_idempotent_does_not_stack(self, _restore_root_logger: None) -> None:
        configure_logging(level="INFO")
        configure_logging(level="WARNING")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert root.level == logging.WARNING

    def test_emits_json_to_stream(self, _restore_root_logger: None) -> None:
        configure_logging(level="INFO")
        root = logging.getLogger()
        # Swap the stream for capture.
        buf = io.StringIO()
        root.handlers[0].stream = buf  # type: ignore[attr-defined]
        logging.getLogger("auxd.test").info("hello", extra={"request_id": "r1"})
        line = buf.getvalue().strip()
        payload = json.loads(line)
        assert payload["message"] == "hello"
        assert payload["request_id"] == "r1"
        assert payload["logger"] == "auxd.test"
