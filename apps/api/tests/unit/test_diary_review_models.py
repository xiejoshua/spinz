"""Unit tests for diary + review Beanie documents (T023).

These exercise Pydantic-level validation only (no MongoDB connection). We
construct documents via :meth:`Model.model_validate` rather than the direct
``Model(...)`` constructor because Beanie 2.x's ``Document.__init__`` calls
:py:meth:`~beanie.Document.get_pymongo_collection`, which requires the ODM
to be initialised against a live database. ``model_validate`` is the
canonical Pydantic entry-point and exercises every default factory, required
field, and validator we care about here. (Matches the pattern used by
``test_backlog_models.py`` and the other sibling-module unit tests.)
"""

from __future__ import annotations

import string
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from auxd_api.modules.diary.models import (
    DiaryEntry,
    DiaryEntrySource,
    Visibility,
)
from auxd_api.modules.reviews.models import (
    Review,
    ReviewEditHistory,
    ReviewLike,
)

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


def _logged_at() -> datetime:
    return datetime(2026, 5, 22, 12, 0, tzinfo=UTC)


def _diary_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_id": "u1",
        "album_id": "a1",
        "logged_at": _logged_at(),
    }
    base.update(overrides)
    return base


def _review_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_id": "u1",
        "diary_entry_id": "d1",
        "album_id": "a1",
        "body": "hi",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# DiaryEntry                                                                  #
# --------------------------------------------------------------------------- #


def test_diary_entry_ksuid_id() -> None:
    """``id`` is auto-generated as a 27-character base62 KSUID."""
    entry = DiaryEntry.model_validate(_diary_payload())
    assert isinstance(entry.id, str)
    assert len(entry.id) == 27
    assert set(entry.id).issubset(BASE62_ALPHABET)


def test_diary_entry_required_fields() -> None:
    """``user_id``, ``album_id``, and ``logged_at`` are all required."""
    for missing_key in ("user_id", "album_id", "logged_at"):
        payload = _diary_payload()
        payload.pop(missing_key)
        with pytest.raises(ValidationError) as exc_info:
            DiaryEntry.model_validate(payload)
        missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
        assert missing_key in missing


def test_diary_entry_rating_validation() -> None:
    """Rating must be in 0.5..5.0 inclusive (or ``None``)."""
    # Boundaries OK.
    DiaryEntry.model_validate(_diary_payload(rating=0.5))
    DiaryEntry.model_validate(_diary_payload(rating=5.0))
    # None is OK.
    DiaryEntry.model_validate(_diary_payload(rating=None))
    # Out of range fails.
    with pytest.raises(ValidationError):
        DiaryEntry.model_validate(_diary_payload(rating=0.0))
    with pytest.raises(ValidationError):
        DiaryEntry.model_validate(_diary_payload(rating=5.5))


def test_diary_entry_aux_default_false() -> None:
    """``auxed`` defaults to ``False`` (Aux is opt-in self-curation)."""
    entry = DiaryEntry.model_validate(_diary_payload())
    assert entry.auxed is False


def test_diary_entry_source_default_manual() -> None:
    """``source`` defaults to :class:`DiaryEntrySource.MANUAL`."""
    entry = DiaryEntry.model_validate(_diary_payload())
    assert entry.source is DiaryEntrySource.MANUAL


def test_diary_entry_visibility_default_public() -> None:
    """``visibility`` defaults to :class:`Visibility.PUBLIC`."""
    entry = DiaryEntry.model_validate(_diary_payload())
    assert entry.visibility is Visibility.PUBLIC


def test_diary_entry_soft_delete_field() -> None:
    """``deleted_at`` is ``None`` on construction and assignable to a datetime."""
    entry = DiaryEntry.model_validate(_diary_payload())
    assert entry.deleted_at is None
    now = datetime.now(UTC)
    entry.deleted_at = now
    assert entry.deleted_at == now


# --------------------------------------------------------------------------- #
# Review                                                                      #
# --------------------------------------------------------------------------- #


def test_review_ksuid_id() -> None:
    """``id`` is auto-generated as a 27-character base62 KSUID."""
    review = Review.model_validate(_review_payload())
    assert isinstance(review.id, str)
    assert len(review.id) == 27
    assert set(review.id).issubset(BASE62_ALPHABET)


def test_review_required_fields() -> None:
    """``user_id``, ``diary_entry_id``, ``album_id``, ``body`` are required."""
    for missing_key in ("user_id", "diary_entry_id", "album_id", "body"):
        payload = _review_payload()
        payload.pop(missing_key)
        with pytest.raises(ValidationError) as exc_info:
            Review.model_validate(payload)
        missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
        assert missing_key in missing


def test_review_reactions_default_zero() -> None:
    """``reactions.likes_count`` defaults to 0 and ``recent_likers`` to ``[]``."""
    review = Review.model_validate(_review_payload())
    assert review.reactions.likes_count == 0
    assert review.reactions.recent_likers == []


def test_review_no_body_length_limit() -> None:
    """Per S-C1 AC, review body has no maximum length — a 10k-char body validates."""
    body = "x" * 10_000
    review = Review.model_validate(_review_payload(body=body))
    assert len(review.body) == 10_000


# --------------------------------------------------------------------------- #
# ReviewLike                                                                  #
# --------------------------------------------------------------------------- #


def test_review_like_ksuid_id() -> None:
    """``id`` is auto-generated as a 27-character base62 KSUID."""
    like = ReviewLike.model_validate({"review_id": "r1", "user_id": "u1"})
    assert isinstance(like.id, str)
    assert len(like.id) == 27
    assert set(like.id).issubset(BASE62_ALPHABET)


def test_review_like_required_fields() -> None:
    """Both ``review_id`` and ``user_id`` are required."""
    for payload, expected_missing in (
        ({"user_id": "u1"}, "review_id"),
        ({"review_id": "r1"}, "user_id"),
    ):
        with pytest.raises(ValidationError) as exc_info:
            ReviewLike.model_validate(payload)
        missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
        assert expected_missing in missing


# --------------------------------------------------------------------------- #
# ReviewEditHistory                                                           #
# --------------------------------------------------------------------------- #


def test_review_edit_history_ksuid() -> None:
    """``id`` is auto-generated as a 27-character base62 KSUID."""
    history = ReviewEditHistory.model_validate(
        {
            "review_id": "r1",
            "version": 1,
            "body_at_time": "prev",
            "edited_at": datetime.now(UTC),
            "edited_by": "u1",
        }
    )
    assert isinstance(history.id, str)
    assert len(history.id) == 27
    assert set(history.id).issubset(BASE62_ALPHABET)


def test_review_edit_history_required_fields() -> None:
    """All five domain fields (review_id, version, body_at_time, edited_at, edited_by) required."""
    full: dict[str, object] = {
        "review_id": "r1",
        "version": 1,
        "body_at_time": "x",
        "edited_at": datetime.now(UTC),
        "edited_by": "u1",
    }
    for missing_key in ("review_id", "version", "body_at_time", "edited_at", "edited_by"):
        payload = dict(full)
        payload.pop(missing_key)
        with pytest.raises(ValidationError) as exc_info:
            ReviewEditHistory.model_validate(payload)
        missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
        assert missing_key in missing
