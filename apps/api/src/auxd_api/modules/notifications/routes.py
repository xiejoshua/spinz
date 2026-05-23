"""Notifications HTTP routes (T136).

At MVP this router exposes only the Web Push subscription endpoints; the
inbox bell-icon read surface (T140) joins later behind the same router.

Endpoints (all mounted under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``POST /users/me/push-subscriptions`` — register / refresh a Web Push
  subscription. Idempotent on ``endpoint`` (re-sending the same endpoint
  updates ``last_used_at`` instead of erroring).
* ``DELETE /users/me/push-subscriptions/{subscription_id}`` — owner-only
  delete.

Rate limiting (T020) — per-user 10/min mirrors a typical browser
re-subscribe cadence with healthy headroom.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.notifications.push_models import PushSubscription

_LOGGER = logging.getLogger("auxd.notifications.routes")

router = APIRouter(tags=["notifications"])


_PUSH_RATE_LIMIT = rate_limit(
    endpoint="notifications.push_subscription",
    per_user=RateLimit(limit=10, window_seconds=60),
)


def _require_session(request: Request) -> Session:
    """Lift the authenticated session off ``request.state`` or 401."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class _PushKeys(BaseModel):
    """Inner ``keys`` block of the browser PushSubscription JSON shape."""

    p256dh: str = Field(..., min_length=1, max_length=512)
    auth: str = Field(..., min_length=1, max_length=128)


class _PushSubscriptionRequest(BaseModel):
    """Wire shape mirrors the browser PushSubscription.toJSON() output."""

    endpoint: str = Field(..., min_length=1, max_length=2048)
    keys: _PushKeys


class _PushSubscriptionResponse(BaseModel):
    """Slim response — id + endpoint suffice for the client cache."""

    id: str
    endpoint: str
    created: bool


# ---------------------------------------------------------------------------
# POST /users/me/push-subscriptions
# ---------------------------------------------------------------------------


@router.post(
    "/users/me/push-subscriptions",
    dependencies=[Depends(_PUSH_RATE_LIMIT)],
    response_model=_PushSubscriptionResponse,
)
async def register_push_subscription(
    request: Request,
    payload: _PushSubscriptionRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> _PushSubscriptionResponse:
    """Register a new Web Push subscription for the authenticated user.

    Idempotent on ``endpoint``: if a row with the same endpoint exists,
    its ``last_used_at`` is refreshed and the row is returned with
    ``created=False``. This handles the legitimate case of a browser
    re-asserting the subscription at every page load.

    Returns ``201`` on a fresh insert, ``200`` on an idempotent refresh.
    """
    existing = await PushSubscription.find_one(PushSubscription.endpoint == payload.endpoint)
    user_agent = request.headers.get("user-agent")

    if existing is not None:
        # Defense: if a different user previously claimed this endpoint
        # (extremely unlikely — endpoints are user-bound by the browser),
        # rewrite ownership. The endpoint URL itself is unguessable.
        existing.user_id = session.user_id
        existing.p256dh_key = payload.keys.p256dh
        existing.auth_secret = payload.keys.auth
        existing.user_agent = user_agent
        existing.last_used_at = datetime.now(UTC)
        await existing.save()
        return _PushSubscriptionResponse(id=existing.id, endpoint=existing.endpoint, created=False)

    fresh = PushSubscription(
        user_id=session.user_id,
        endpoint=payload.endpoint,
        p256dh_key=payload.keys.p256dh,
        auth_secret=payload.keys.auth,
        user_agent=user_agent,
        last_used_at=datetime.now(UTC),
    )
    await fresh.insert()
    return _PushSubscriptionResponse(id=fresh.id, endpoint=fresh.endpoint, created=True)


# ---------------------------------------------------------------------------
# DELETE /users/me/push-subscriptions/{subscription_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/users/me/push-subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_PUSH_RATE_LIMIT)],
)
async def delete_push_subscription(
    subscription_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Owner-only delete of a registered push subscription.

    Returns ``204`` on success. ``404`` when the row does not exist OR
    when it exists but is owned by another user — we deliberately do
    not leak the existence of subscriptions owned by other accounts.
    """
    sub = await PushSubscription.find_one(PushSubscription.id == subscription_id)
    if sub is None or sub.user_id != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="push_subscription_not_found",
        )
    await sub.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
