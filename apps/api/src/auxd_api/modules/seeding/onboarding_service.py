"""Synchronous onboarding card-ordering (T117a).

This service runs **inline** during the onboarding step where the user
picks who to follow — latency target p95 < 1 second per the AC. It's a
thin wrapper around :mod:`auxd_api.modules.seeding.service` that:

* Restricts the deck to the top 6 "primary" critics (the pre-checked
  cards in the onboarding UI) plus 4 secondary critics (unchecked,
  surfaced as alternatives).
* Bakes the card-tier classification into the response so the frontend
  doesn't need to re-implement the rule.
* Always satisfies UJ-2 (≥3 critic-seeds in the top 6) — at MVP every
  card IS a critic, so the constraint is trivial.

CR-001 narrowed the input signal. Before CR-001, an auto-imported
30-day Spotify diary fed the genre signature; under CR-001 we lean on
the optional inline "rate a few albums" step (T079 search-driven log
sheet). For now, the synchronous path accepts no optional ratings —
the algorithm degrades cleanly to priority-only ordering. When the
rate-a-few-albums onboarding intent ships, plug the resulting genre
signature into the existing call by passing
``viewer_genre_signature``.

Mutual-taste candidates are explicitly omitted at MVP. The spec calls
for 4 mutual-taste cards in addition to the 6 critic cards (10 total),
but mutual-taste requires the user to have rated albums — which a
fresh signup hasn't. Until T117 + T163 + the optional rating intent
combine, the four "alternate" slots are filled with the next 4 critics
by priority. This is documented as an MVP simplification in the
onboarding page copy ("Suggested critics — pick a few").
"""

from __future__ import annotations

from dataclasses import dataclass

from auxd_api.modules.seeding.service import (
    ScoredCritic,
    get_card_recommendations_for_user,
)

_PRIMARY_CARD_COUNT = 6
_SECONDARY_CARD_COUNT = 4
_TOTAL_CARD_COUNT = _PRIMARY_CARD_COUNT + _SECONDARY_CARD_COUNT


@dataclass(frozen=True, slots=True)
class OnboardingCard:
    """One card in the onboarding pick-deck.

    Wraps a :class:`ScoredCritic` with the tier classification the
    frontend uses to drive the pre-checked vs. unchecked state.
    """

    scored: ScoredCritic
    pre_checked: bool
    source: str  # "onboarding_preselected" | "onboarding_mutual_taste"


@dataclass(frozen=True, slots=True)
class OnboardingCardDeck:
    """Return shape for :func:`get_onboarding_cards`."""

    cards: list[OnboardingCard]


async def get_onboarding_cards(
    *,
    user_id: str,
    viewer_genre_signature: list[str] | None = None,
) -> OnboardingCardDeck:
    """Return the synchronous card deck for the onboarding step.

    The output ALWAYS has at most 10 cards (6 pre-checked + 4 unchecked).
    Roster size is not validated here — if the founder has fewer than 10
    active critic-seeds in the database, the deck is naturally smaller
    (no padding, no exceptions); the UI handles "<10 cards" gracefully.

    Latency-aware: a single ``CriticSeed.find({active: True})`` query
    plus an in-memory sort. With ~80 active critic-seeds at maturity,
    the whole call completes in well under 100ms in practice.
    """
    scored = await get_card_recommendations_for_user(
        user_id=user_id,
        viewer_genre_signature=viewer_genre_signature,
        limit=_TOTAL_CARD_COUNT,
    )
    cards: list[OnboardingCard] = []
    for index, candidate in enumerate(scored):
        is_primary = index < _PRIMARY_CARD_COUNT
        cards.append(
            OnboardingCard(
                scored=candidate,
                pre_checked=is_primary,
                # NOTE: until mutual-taste candidates land (T163 + a
                # rating-signal source), the "secondary" tier is still
                # critic-seeded — we tag it as `_preselected` rather than
                # `_mutual_taste` because the source is editorially
                # picked, not inferred from taste overlap.
                source="onboarding_preselected",
            )
        )
    return OnboardingCardDeck(cards=cards)


__all__ = [
    "OnboardingCard",
    "OnboardingCardDeck",
    "get_onboarding_cards",
]
