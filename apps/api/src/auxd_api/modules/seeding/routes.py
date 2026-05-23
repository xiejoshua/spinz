"""User-facing onboarding endpoints (T117a HTTP surface).

The seeding module is dual-purpose: founder-admin surfaces (CriticSeed
roster management — T162) live alongside the user-facing onboarding
read endpoint that the front-end fetches inline during the "Follow 3
to fill your feed" step (T118).

Endpoints (all under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``GET /onboarding/cards`` — returns up to 10 cards (6 pre-checked
  primary + 4 unchecked secondary) for the signed-in user. Inline
  during onboarding (p95 < 1s per T117a AC).

Rate limiting: per-user 30/min — generous since the page only fetches
once per onboarding session under normal flow; tighter than the public
read endpoints because each call also resolves the active critic-seed
roster and is therefore more expensive than a plain album read.
"""

from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.seeding.onboarding_service import (
    OnboardingCard,
    get_onboarding_cards,
)
from auxd_api.modules.users.models import User

router = APIRouter(tags=["onboarding"])

_ONBOARDING_RATE_LIMIT = rate_limit(
    endpoint="onboarding.cards",
    per_user=RateLimit(limit=30, window_seconds=60),
)


def _require_session(request: Request) -> Session:
    """Pull a :class:`Session` from ``request.state`` or raise 401."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


def _serialize_card(card: OnboardingCard, *, user: User) -> dict[str, Any]:
    """Wire shape for one card.

    The shape is denormalised on purpose: the frontend renders entirely
    from this payload, so we bake the critic's display fields directly
    into the card row rather than asking the client to follow a
    user-id reference into a sidecar map. There are at most 10 cards
    per response — the duplication cost is negligible.
    """
    return {
        "user": {
            "id": user.id,
            "handle": user.handle,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "bio": card.scored.seed.public_bio,
        },
        "pre_checked": card.pre_checked,
        "source": card.source,
        "score": card.scored.score,
        "genre_signature": list(card.scored.seed.genre_signature),
    }


@router.get(
    "/onboarding/cards",
    dependencies=[Depends(_ONBOARDING_RATE_LIMIT)],
)
async def get_cards(
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Synchronous onboarding deck — top 6 pre-checked + 4 unchecked.

    The viewer's genre signature is not yet computed (T163 follow-up);
    the call passes ``None`` and the algorithm degrades to priority-
    only ordering, which is the documented fallback.
    """
    started = time.perf_counter()
    deck = await get_onboarding_cards(
        user_id=session.user_id,
        viewer_genre_signature=None,
    )

    # Resolve User rows for the cards in one query — every card needs
    # handle / display_name / avatar_url to render. Order-preserving:
    # the deck order from the service IS the user-facing order.
    critic_user_ids = [card.scored.seed.user_id for card in deck.cards]
    users = await User.find({"_id": {"$in": critic_user_ids}}).to_list()
    users_by_id = {user.id: user for user in users}

    payload_cards: list[dict[str, Any]] = []
    for card in deck.cards:
        user = users_by_id.get(card.scored.seed.user_id)
        if user is None:
            # Defensive: an active critic-seed whose underlying User
            # was hard-deleted. Skip it rather than 500; founder
            # tooling should keep the two tables in sync.
            continue
        payload_cards.append(_serialize_card(card, user=user))

    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="onboarding.cards",
        latency_ms=duration_ms,
        status="ok",
        extra={"user_id": session.user_id, "card_count": len(payload_cards)},
    )
    emit_event(
        user_id=session.user_id,
        event="onboarding.cards_loaded",
        properties={
            "duration_ms": duration_ms,
            "card_count": len(payload_cards),
            "primary_count": sum(1 for c in payload_cards if c["pre_checked"]),
        },
    )
    return {"cards": payload_cards}


__all__ = ["router"]
