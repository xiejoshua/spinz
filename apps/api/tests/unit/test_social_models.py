"""Unit tests for :mod:`auxd_api.modules.social.models` (T025).

These tests construct the Pydantic/Beanie ``Follow`` / ``FollowRequest`` /
``Block`` models directly and exercise field defaults + validation
behaviour. They do **not** touch MongoDB — integration coverage of the
compound unique indexes and persistence lives in T012's connection-test
suite.
"""

from __future__ import annotations

import string
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from auxd_api.modules.social.models import (
    Block,
    BlockReason,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


# ---------------------------------------------------------------------------
# Follow
# ---------------------------------------------------------------------------


def test_follow_ksuid_id() -> None:
    """A newly constructed Follow receives a fresh 27-char base62 KSUID."""
    follow = Follow(follower_id="u1", followee_id="u2")
    assert isinstance(follow.id, str)
    assert len(follow.id) == 27
    assert set(follow.id).issubset(BASE62_ALPHABET)


def test_follow_required_fields() -> None:
    """``follower_id`` and ``followee_id`` are both required."""
    with pytest.raises(ValidationError) as excinfo:
        Follow(followee_id="u2")
    assert any(err["loc"] == ("follower_id",) for err in excinfo.value.errors())

    with pytest.raises(ValidationError) as excinfo:
        Follow(follower_id="u1")
    assert any(err["loc"] == ("followee_id",) for err in excinfo.value.errors())


def test_follow_state_default_accepted() -> None:
    """Public-profile follows default to ``state=accepted`` per plan §4.6."""
    follow = Follow(follower_id="u1", followee_id="u2")
    assert follow.state is FollowState.ACCEPTED


def test_follow_state_enum_accepts_three_values() -> None:
    """``state`` accepts the three valid enum values and rejects junk."""
    assert (
        Follow(follower_id="u1", followee_id="u2", state=FollowState.ACCEPTED).state
        is FollowState.ACCEPTED
    )
    assert (
        Follow(follower_id="u1", followee_id="u2", state=FollowState.PENDING).state
        is FollowState.PENDING
    )
    assert (
        Follow(follower_id="u1", followee_id="u2", state=FollowState.REJECTED).state
        is FollowState.REJECTED
    )
    # Wire-format string values are accepted (Pydantic coerces str → Enum).
    assert Follow(follower_id="u1", followee_id="u2", state="pending").state is FollowState.PENDING
    with pytest.raises(ValidationError):
        Follow(follower_id="u1", followee_id="u2", state="approved")


def test_follow_source_optional() -> None:
    """``source`` defaults to ``None`` and accepts any string."""
    follow = Follow(follower_id="u1", followee_id="u2")
    assert follow.source is None

    with_source = Follow(follower_id="u1", followee_id="u2", source="onboarding_preselected")
    assert with_source.source == "onboarding_preselected"


# ---------------------------------------------------------------------------
# FollowRequest
# ---------------------------------------------------------------------------


def test_follow_request_ksuid_id() -> None:
    """A newly constructed FollowRequest receives a fresh 27-char base62 KSUID."""
    req = FollowRequest(requester_id="u1", requestee_id="u2")
    assert isinstance(req.id, str)
    assert len(req.id) == 27
    assert set(req.id).issubset(BASE62_ALPHABET)


def test_follow_request_required_fields() -> None:
    """``requester_id`` and ``requestee_id`` are both required."""
    with pytest.raises(ValidationError) as excinfo:
        FollowRequest(requestee_id="u2")
    assert any(err["loc"] == ("requester_id",) for err in excinfo.value.errors())

    with pytest.raises(ValidationError) as excinfo:
        FollowRequest(requester_id="u1")
    assert any(err["loc"] == ("requestee_id",) for err in excinfo.value.errors())


def test_follow_request_status_default_pending() -> None:
    """Newly created FollowRequest rows start as ``pending`` (sync-fix L3-002)."""
    req = FollowRequest(requester_id="u1", requestee_id="u2")
    assert req.status is FollowRequestStatus.PENDING


def test_follow_request_status_enum_accepts_four_values() -> None:
    """``status`` accepts the four valid enum values and rejects junk."""
    for value in (
        FollowRequestStatus.PENDING,
        FollowRequestStatus.ACCEPTED,
        FollowRequestStatus.DECLINED,
        FollowRequestStatus.EXPIRED,
    ):
        req = FollowRequest(requester_id="u1", requestee_id="u2", status=value)
        assert req.status is value

    # Wire-format string values are accepted (Pydantic coerces str → Enum).
    assert (
        FollowRequest(requester_id="u1", requestee_id="u2", status="expired").status
        is FollowRequestStatus.EXPIRED
    )
    with pytest.raises(ValidationError):
        FollowRequest(requester_id="u1", requestee_id="u2", status="ignored")


def test_follow_request_responded_at_nullable() -> None:
    """``responded_at`` is ``None`` on fresh rows and accepts a tz-aware datetime."""
    req = FollowRequest(requester_id="u1", requestee_id="u2")
    assert req.responded_at is None

    answered_at = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)
    req_resp = FollowRequest(
        requester_id="u1",
        requestee_id="u2",
        status=FollowRequestStatus.ACCEPTED,
        responded_at=answered_at,
    )
    assert req_resp.responded_at == answered_at


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------


def test_block_ksuid_id() -> None:
    """A newly constructed Block receives a fresh 27-char base62 KSUID."""
    block = Block(blocker_id="u1", blockee_id="u2")
    assert isinstance(block.id, str)
    assert len(block.id) == 27
    assert set(block.id).issubset(BASE62_ALPHABET)


def test_block_required_fields() -> None:
    """``blocker_id`` and ``blockee_id`` are both required."""
    with pytest.raises(ValidationError) as excinfo:
        Block(blockee_id="u2")
    assert any(err["loc"] == ("blocker_id",) for err in excinfo.value.errors())

    with pytest.raises(ValidationError) as excinfo:
        Block(blocker_id="u1")
    assert any(err["loc"] == ("blockee_id",) for err in excinfo.value.errors())


def test_block_reason_default_other() -> None:
    """``reason`` defaults to :attr:`BlockReason.OTHER` so the field is always set."""
    block = Block(blocker_id="u1", blockee_id="u2")
    assert block.reason is BlockReason.OTHER


def test_block_other_reason_nullable() -> None:
    """``other_reason`` is ``None`` on fresh rows and accepts a free-text string."""
    block = Block(blocker_id="u1", blockee_id="u2")
    assert block.other_reason is None

    with_text = Block(
        blocker_id="u1",
        blockee_id="u2",
        reason=BlockReason.OTHER,
        other_reason="repeated unwanted DMs after explicit refusal",
    )
    assert with_text.other_reason == "repeated unwanted DMs after explicit refusal"
