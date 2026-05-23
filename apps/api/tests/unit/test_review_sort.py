"""Unit tests for the review-sort tier classifier (T089).

The sort comparator splits visible reviews into three tiers — friends,
public, critic-seed — and the inner sort is delegated to the upstream
Mongo query. These tests pin the tier classification behaviour so a
future refactor of the route layer cannot silently break the contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from auxd_api.modules.reviews.models import ReactionsSubDoc, Review
from auxd_api.modules.reviews.routes import _tier_key


def _make_review(
    review_id: str,
    user_id: str,
    *,
    likes: int = 0,
    created_at: datetime | None = None,
) -> Review:
    """Build a freshly constructed :class:`Review` with sane defaults."""
    return Review(
        id=review_id,
        user_id=user_id,
        diary_entry_id=f"diary-{review_id}",
        album_id="album-001",
        body="body",
        reactions=ReactionsSubDoc(likes_count=likes),
        visibility="public",
        created_at=created_at or datetime.now(UTC),
        updated_at=created_at or datetime.now(UTC),
    )


def test_tier_friends_classified_zero() -> None:
    """Reviews authored by a friend get tier=0."""
    review = _make_review("r-1", "u-friend")
    tier = _tier_key(
        review,
        friend_owner_ids=frozenset({"u-friend"}),
        critic_seed_owner_ids=frozenset(),
    )
    assert tier == 0


def test_tier_public_classified_one() -> None:
    """A non-friend, non-critic-seed author is the public tier."""
    review = _make_review("r-1", "u-rando")
    tier = _tier_key(
        review,
        friend_owner_ids=frozenset(),
        critic_seed_owner_ids=frozenset(),
    )
    assert tier == 1


def test_tier_critic_seed_classified_two() -> None:
    """A critic-seed author falls into tier=2."""
    review = _make_review("r-1", "u-critic")
    tier = _tier_key(
        review,
        friend_owner_ids=frozenset(),
        critic_seed_owner_ids=frozenset({"u-critic"}),
    )
    assert tier == 2


def test_tier_friend_beats_critic_seed() -> None:
    """When the same author is BOTH a friend and a critic seed, friend wins.

    A friend who happens to be on the curated CriticSeed roster is
    closer to the viewer than a generic critic. The tier order is a
    relevance signal — the viewer's friend-ness is the strongest one.
    """
    review = _make_review("r-1", "u-known-critic")
    tier = _tier_key(
        review,
        friend_owner_ids=frozenset({"u-known-critic"}),
        critic_seed_owner_ids=frozenset({"u-known-critic"}),
    )
    assert tier == 0


def test_tier_sort_stability_orders_within_tier() -> None:
    """``sorted(..., key=_tier_key)`` is stable — in-tier order is preserved.

    The route layer relies on Python's stable sort to keep the upstream
    Mongo sort intact within each tier.
    """
    now = datetime.now(UTC)
    reviews = [
        _make_review("r-friend-recent", "u-friend", created_at=now),
        _make_review("r-friend-old", "u-friend", created_at=now - timedelta(hours=1)),
        _make_review("r-public-recent", "u-rando", created_at=now),
    ]
    sorted_reviews = sorted(
        reviews,
        key=lambda r: _tier_key(
            r,
            friend_owner_ids=frozenset({"u-friend"}),
            critic_seed_owner_ids=frozenset(),
        ),
    )
    assert [r.id for r in sorted_reviews] == [
        "r-friend-recent",
        "r-friend-old",
        "r-public-recent",
    ]


@pytest.mark.parametrize(
    ("friends", "critics", "expected"),
    [
        (frozenset(), frozenset(), 1),  # nobody — public
        (frozenset({"u-rando"}), frozenset(), 0),
        (frozenset(), frozenset({"u-rando"}), 2),
        (frozenset({"u-rando"}), frozenset({"u-rando"}), 0),
    ],
)
def test_tier_parametric(
    friends: frozenset[str],
    critics: frozenset[str],
    expected: int,
) -> None:
    review = _make_review("r-1", "u-rando")
    assert (
        _tier_key(
            review,
            friend_owner_ids=friends,
            critic_seed_owner_ids=critics,
        )
        == expected
    )
