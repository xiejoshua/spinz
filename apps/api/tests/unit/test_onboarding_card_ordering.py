"""Unit tests for the synchronous onboarding card-ordering service (T117a)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.seeding.onboarding_service import (
    _PRIMARY_CARD_COUNT,
    _SECONDARY_CARD_COUNT,
    _TOTAL_CARD_COUNT,
    get_onboarding_cards,
)


def _make_seed(handle: str, *, priority: int = 50, active: bool = True) -> CriticSeed:
    return CriticSeed(
        id=f"seed-{handle}",
        user_id=f"user-{handle}",
        priority=priority,
        active=active,
        genre_signature=["pop"],
        public_bio=f"{handle} bio",
        added_at=datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await CriticSeed.delete_all()
    yield
    await CriticSeed.delete_all()


@pytest.mark.asyncio
async def test_returns_at_most_10_cards(_clean_db: None) -> None:
    # Seed 15 active critics; we should only see the top 10.
    for i in range(15):
        await _make_seed(f"c{i:02d}", priority=100 - i).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    assert len(deck.cards) == _TOTAL_CARD_COUNT == 10


@pytest.mark.asyncio
async def test_primary_count_is_pre_checked_and_secondary_is_not(_clean_db: None) -> None:
    for i in range(10):
        await _make_seed(f"c{i:02d}", priority=100 - i).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    primary = [c for c in deck.cards if c.pre_checked]
    secondary = [c for c in deck.cards if not c.pre_checked]
    assert len(primary) == _PRIMARY_CARD_COUNT == 6
    assert len(secondary) == _SECONDARY_CARD_COUNT == 4


@pytest.mark.asyncio
async def test_smaller_roster_returns_smaller_deck(_clean_db: None) -> None:
    """If only 3 critics are active, we get a 3-card deck — no padding, no errors."""
    for i in range(3):
        await _make_seed(f"c{i:02d}", priority=100 - i).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    assert len(deck.cards) == 3
    # All 3 land in the primary tier since 3 < _PRIMARY_CARD_COUNT.
    assert all(card.pre_checked for card in deck.cards)


@pytest.mark.asyncio
async def test_deck_ordered_by_priority_descending(_clean_db: None) -> None:
    # Intentionally insert in scrambled priority order.
    for handle, priority in [("low", 10), ("mid", 50), ("high", 90), ("hi2", 80)]:
        await _make_seed(handle, priority=priority).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    handles_in_order = [card.scored.seed.user_id.removeprefix("user-") for card in deck.cards]
    assert handles_in_order == ["high", "hi2", "mid", "low"]


@pytest.mark.asyncio
async def test_inactive_seeds_excluded(_clean_db: None) -> None:
    """Deactivated critics never appear in the deck."""
    for handle, priority, active in [
        ("active1", 90, True),
        ("retired", 95, False),  # higher priority but inactive — should NOT appear
        ("active2", 70, True),
    ]:
        await _make_seed(handle, priority=priority, active=active).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    handles = {card.scored.seed.user_id for card in deck.cards}
    assert handles == {"user-active1", "user-active2"}


@pytest.mark.asyncio
async def test_uj_2_three_critics_in_top_6(_clean_db: None) -> None:
    """UJ-2 AC: at least 3 critic-seeds in the top 6 of the deck.

    At MVP the cards are all critics so this is trivially satisfied,
    but pinning the guarantee as a test means a future regression
    (e.g., mixing mutual-taste candidates into the top 6 without
    quota enforcement) will fail loudly here.
    """
    for i in range(10):
        await _make_seed(f"c{i:02d}", priority=100 - i).insert()
    deck = await get_onboarding_cards(user_id="user-viewer")
    primary = [c for c in deck.cards if c.pre_checked]
    critic_count_in_top_6 = sum(
        1 for card in primary if card.source.startswith("onboarding_preselected")
    )
    assert critic_count_in_top_6 >= 3


@pytest.mark.asyncio
async def test_deterministic_ordering_for_fixed_signal(_clean_db: None) -> None:
    """Same input → same output (no randomness in the algorithm)."""
    for i in range(5):
        await _make_seed(f"c{i:02d}", priority=80 + i).insert()
    deck_a = await get_onboarding_cards(user_id="user-viewer")
    deck_b = await get_onboarding_cards(user_id="user-viewer")
    a_ids = [card.scored.seed.id for card in deck_a.cards]
    b_ids = [card.scored.seed.id for card in deck_b.cards]
    assert a_ids == b_ids
