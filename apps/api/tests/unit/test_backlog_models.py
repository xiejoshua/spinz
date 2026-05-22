"""Unit tests for :mod:`auxd_api.modules.backlog.models`.

These tests exercise Pydantic-level validation only. Beanie's collection
init is handled by the session-scoped fixture in ``tests/conftest.py``.
"""

from __future__ import annotations

import string
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from auxd_api.lib.visibility import Visibility
from auxd_api.modules.backlog.models import Backlog, BacklogItem

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


# ---------------------------------------------------------------------------
# Backlog
# ---------------------------------------------------------------------------


def test_backlog_ksuid_id() -> None:
    """A new ``Backlog`` gets an auto-generated 27-char base62 KSUID ``id``."""
    backlog = Backlog.model_validate({"user_id": "user_abc"})
    assert isinstance(backlog.id, str)
    assert len(backlog.id) == 27
    assert set(backlog.id).issubset(BASE62_ALPHABET)
    # Two backlogs constructed back-to-back must get distinct ids.
    other = Backlog.model_validate({"user_id": "user_xyz"})
    assert backlog.id != other.id


def test_backlog_user_id_required() -> None:
    """``user_id`` has no default and must be supplied explicitly."""
    with pytest.raises(ValidationError) as exc_info:
        Backlog.model_validate({})
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert "user_id" in missing


def test_backlog_keep_after_logging_default_false() -> None:
    """``keep_after_logging`` defaults to ``False`` (auto-remove on log).

    Also confirms ``created_at`` / ``updated_at`` default to a tz-aware
    ``datetime`` very close to ``datetime.now(UTC)``.
    """
    before = datetime.now(UTC)
    backlog = Backlog.model_validate({"user_id": "user_abc"})
    after = datetime.now(UTC)

    assert backlog.keep_after_logging is False
    assert backlog.created_at.tzinfo is not None
    assert before <= backlog.created_at <= after
    assert backlog.updated_at.tzinfo is not None
    assert before <= backlog.updated_at <= after


# ---------------------------------------------------------------------------
# BacklogItem
# ---------------------------------------------------------------------------


def test_backlog_item_ksuid_id() -> None:
    """A new ``BacklogItem`` gets an auto-generated 27-char base62 KSUID ``id``."""
    item = BacklogItem.model_validate({"backlog_id": "bl_1", "album_id": "al_1", "position": 1})
    assert isinstance(item.id, str)
    assert len(item.id) == 27
    assert set(item.id).issubset(BASE62_ALPHABET)


def test_backlog_item_required_fields() -> None:
    """``backlog_id``, ``album_id``, and ``position`` are all required."""
    # All three missing.
    with pytest.raises(ValidationError) as exc_info:
        BacklogItem.model_validate({})
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert {"backlog_id", "album_id", "position"}.issubset(missing)

    # Each individually missing also raises.
    with pytest.raises(ValidationError):
        BacklogItem.model_validate({"album_id": "al_1", "position": 1})
    with pytest.raises(ValidationError):
        BacklogItem.model_validate({"backlog_id": "bl_1", "position": 1})
    with pytest.raises(ValidationError):
        BacklogItem.model_validate({"backlog_id": "bl_1", "album_id": "al_1"})


def test_backlog_item_added_at_default_now() -> None:
    """``added_at`` defaults to a tz-aware ``datetime`` close to ``now(UTC)``."""
    before = datetime.now(UTC)
    item = BacklogItem.model_validate({"backlog_id": "bl_1", "album_id": "al_1", "position": 1})
    after = datetime.now(UTC)

    assert item.added_at.tzinfo is not None
    assert before <= item.added_at <= after


def test_backlog_item_notes_optional() -> None:
    """``notes`` is optional; default ``None``, accepts a string when supplied."""
    item_without = BacklogItem.model_validate(
        {"backlog_id": "bl_1", "album_id": "al_1", "position": 1}
    )
    assert item_without.notes is None

    item_with = BacklogItem.model_validate(
        {
            "backlog_id": "bl_1",
            "album_id": "al_1",
            "position": 1,
            "notes": "must-listen on a long drive",
        }
    )
    assert item_with.notes == "must-listen on a long drive"


def test_backlog_item_per_item_visibility_defaults_to_inherit() -> None:
    """``per_item_visibility`` defaults to ``None`` (inherit Backlog default)."""
    item = BacklogItem.model_validate({"backlog_id": "bl_1", "album_id": "al_1", "position": 1})
    assert item.per_item_visibility is None

    overridden = BacklogItem.model_validate(
        {
            "backlog_id": "bl_1",
            "album_id": "al_1",
            "position": 2,
            "per_item_visibility": Visibility.PUBLIC,
        }
    )
    assert overridden.per_item_visibility is Visibility.PUBLIC


def test_backlog_item_has_unique_backlog_album_index() -> None:
    """Plan §3.1 invariant: one row per (backlog_id, album_id) pair."""
    indexes = BacklogItem.Settings.indexes
    unique_compound = [
        ix
        for ix in indexes
        if getattr(ix, "document", {}).get("unique") is True
        and list(ix.document.get("key", {}).keys()) == ["backlog_id", "album_id"]
    ]
    assert len(unique_compound) == 1, (
        f"expected exactly one unique (backlog_id, album_id) index; got {indexes}"
    )
