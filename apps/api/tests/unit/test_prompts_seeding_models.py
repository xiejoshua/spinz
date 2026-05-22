"""Unit tests for prompts + seeding Beanie Documents.

These tests exercise Pydantic-level validation only (no MongoDB connection):
Beanie ``Document`` inherits from ``pydantic.BaseModel``, so default factories,
required-field validation, and basic type-coercion all run without a live
database.
"""

from __future__ import annotations

import string
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from auxd_api.modules.prompts.models import JustFinishedPrompt, JustFinishedPromptState
from auxd_api.modules.seeding.models import CriticSeed, SuggestedFollow, SuggestionSource

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


# ---------------------------------------------------------------------------
# JustFinishedPrompt
# ---------------------------------------------------------------------------


def _now_and_expiry() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now, now + timedelta(hours=24)


def test_just_finished_prompt_ksuid_id() -> None:
    """A new ``JustFinishedPrompt`` gets an auto-generated 27-char base62 KSUID."""
    detected_at, expires_at = _now_and_expiry()
    prompt = JustFinishedPrompt(
        user_id="user_abc",
        album_id="album_1",
        detected_at=detected_at,
        expires_at=expires_at,
    )
    assert isinstance(prompt.id, str)
    assert len(prompt.id) == 27
    assert set(prompt.id).issubset(BASE62_ALPHABET)

    other = JustFinishedPrompt(
        user_id="user_xyz",
        album_id="album_2",
        detected_at=detected_at,
        expires_at=expires_at,
    )
    assert prompt.id != other.id


def test_just_finished_prompt_required_fields() -> None:
    """``user_id``, ``album_id``, ``detected_at``, and ``expires_at`` are required."""
    with pytest.raises(ValidationError) as exc_info:
        JustFinishedPrompt()
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert {"user_id", "album_id", "detected_at", "expires_at"}.issubset(missing)

    detected_at, expires_at = _now_and_expiry()

    # Each individually missing also raises.
    with pytest.raises(ValidationError):
        JustFinishedPrompt(
            album_id="album_1",
            detected_at=detected_at,
            expires_at=expires_at,
        )
    with pytest.raises(ValidationError):
        JustFinishedPrompt(
            user_id="user_abc",
            detected_at=detected_at,
            expires_at=expires_at,
        )
    with pytest.raises(ValidationError):
        JustFinishedPrompt(
            user_id="user_abc",
            album_id="album_1",
            expires_at=expires_at,
        )
    with pytest.raises(ValidationError):
        JustFinishedPrompt(
            user_id="user_abc",
            album_id="album_1",
            detected_at=detected_at,
        )


def test_just_finished_prompt_state_default_pending() -> None:
    """``state`` defaults to :attr:`JustFinishedPromptState.PENDING`."""
    detected_at, expires_at = _now_and_expiry()
    prompt = JustFinishedPrompt(
        user_id="user_abc",
        album_id="album_1",
        detected_at=detected_at,
        expires_at=expires_at,
    )
    assert prompt.state is JustFinishedPromptState.PENDING
    assert prompt.state.value == "pending"

    # Optional lifecycle fields default to None.
    assert prompt.surfaced_at is None
    assert prompt.acted_at is None
    assert prompt.logged_diary_entry_id is None
    assert prompt.push_sent_at is None


def test_just_finished_prompt_state_enum_five_values() -> None:
    """``JustFinishedPromptState`` exposes exactly the five documented values."""
    expected = {"pending", "logged", "dismissed", "expired", "suppressed"}
    actual = {member.value for member in JustFinishedPromptState}
    assert actual == expected
    assert len(JustFinishedPromptState) == 5


# ---------------------------------------------------------------------------
# SuggestedFollow
# ---------------------------------------------------------------------------


def test_suggested_follow_ksuid_id() -> None:
    """A new ``SuggestedFollow`` gets an auto-generated 27-char base62 KSUID."""
    suggestion = SuggestedFollow(
        user_id="user_abc",
        suggested_user_id="user_xyz",
        score=0.85,
        source=SuggestionSource.MUTUAL_TASTE,
    )
    assert isinstance(suggestion.id, str)
    assert len(suggestion.id) == 27
    assert set(suggestion.id).issubset(BASE62_ALPHABET)


def test_suggested_follow_required_fields() -> None:
    """``user_id``, ``suggested_user_id``, ``score``, and ``source`` are required."""
    with pytest.raises(ValidationError) as exc_info:
        SuggestedFollow()
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert {"user_id", "suggested_user_id", "score", "source"}.issubset(missing)

    # Each individually missing also raises.
    with pytest.raises(ValidationError):
        SuggestedFollow(
            suggested_user_id="user_xyz",
            score=0.5,
            source=SuggestionSource.CRITIC_SEED,
        )
    with pytest.raises(ValidationError):
        SuggestedFollow(
            user_id="user_abc",
            score=0.5,
            source=SuggestionSource.CRITIC_SEED,
        )
    with pytest.raises(ValidationError):
        SuggestedFollow(
            user_id="user_abc",
            suggested_user_id="user_xyz",
            source=SuggestionSource.CRITIC_SEED,
        )
    with pytest.raises(ValidationError):
        SuggestedFollow(
            user_id="user_abc",
            suggested_user_id="user_xyz",
            score=0.5,
        )


def test_suggested_follow_source_enum_four_values() -> None:
    """``SuggestionSource`` exposes exactly the four documented signals."""
    expected = {"critic_seed", "mutual_taste", "invite_graph", "co_log"}
    actual = {member.value for member in SuggestionSource}
    assert actual == expected
    assert len(SuggestionSource) == 4


def test_suggested_follow_dismissed_at_nullable() -> None:
    """``dismissed_at`` and ``followed_at`` are nullable; default to None."""
    before = datetime.now(UTC)
    suggestion = SuggestedFollow(
        user_id="user_abc",
        suggested_user_id="user_xyz",
        score=0.42,
        source=SuggestionSource.CO_LOG,
    )
    after = datetime.now(UTC)

    assert suggestion.dismissed_at is None
    assert suggestion.followed_at is None
    assert suggestion.reason is None

    # ``created_at`` defaults to a tz-aware ``datetime.now(UTC)``.
    assert suggestion.created_at.tzinfo is not None
    assert before <= suggestion.created_at <= after

    # When supplied, ``dismissed_at`` is accepted as a tz-aware datetime.
    now = datetime.now(UTC)
    dismissed = SuggestedFollow(
        user_id="user_abc",
        suggested_user_id="user_xyz",
        score=0.42,
        source=SuggestionSource.CO_LOG,
        dismissed_at=now,
    )
    assert dismissed.dismissed_at == now


# ---------------------------------------------------------------------------
# CriticSeed
# ---------------------------------------------------------------------------


def test_critic_seed_ksuid_id() -> None:
    """A new ``CriticSeed`` gets an auto-generated 27-char base62 KSUID."""
    seed = CriticSeed(user_id="user_critic_1")
    assert isinstance(seed.id, str)
    assert len(seed.id) == 27
    assert set(seed.id).issubset(BASE62_ALPHABET)

    other = CriticSeed(user_id="user_critic_2")
    assert seed.id != other.id


def test_critic_seed_required_fields() -> None:
    """``user_id`` is the only required field (everything else has a default)."""
    with pytest.raises(ValidationError) as exc_info:
        CriticSeed()
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert "user_id" in missing


def test_critic_seed_priority_default_50() -> None:
    """``priority`` defaults to 50 (the midpoint of the 1..100 range)."""
    seed = CriticSeed(user_id="user_critic_1")
    assert seed.priority == 50

    # Overrides are accepted.
    high = CriticSeed(user_id="user_critic_2", priority=95)
    assert high.priority == 95


def test_critic_seed_active_default_true() -> None:
    """``active`` defaults to ``True``; ``deactivated_at`` defaults to ``None``.

    ``added_at`` defaults to a tz-aware ``datetime`` very close to ``now(UTC)``.
    """
    before = datetime.now(UTC)
    seed = CriticSeed(user_id="user_critic_1")
    after = datetime.now(UTC)

    assert seed.active is True
    assert seed.deactivated_at is None
    assert seed.public_bio is None
    assert seed.notes is None

    assert seed.added_at.tzinfo is not None
    assert before <= seed.added_at <= after


def test_critic_seed_genre_signature_default_empty() -> None:
    """``genre_signature`` defaults to an empty list (and each instance gets its own).

    The default-factory pattern guarantees we don't accidentally share a
    single mutable list across all ``CriticSeed`` instances.
    """
    seed_a = CriticSeed(user_id="user_critic_1")
    seed_b = CriticSeed(user_id="user_critic_2")

    assert seed_a.genre_signature == []
    assert seed_b.genre_signature == []

    # Mutating one must not bleed into the other.
    seed_a.genre_signature.append("indie-hip-hop")
    assert seed_a.genre_signature == ["indie-hip-hop"]
    assert seed_b.genre_signature == []

    # Explicit values are accepted.
    with_tags = CriticSeed(
        user_id="user_critic_3",
        genre_signature=["ambient", "post-rock"],
    )
    assert with_tags.genre_signature == ["ambient", "post-rock"]
