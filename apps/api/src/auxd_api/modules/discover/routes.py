"""HTTP routes for the Discover surface (feature 003).

Both endpoints are authenticated, per-user rate-limited, and delegate
to :mod:`auxd_api.modules.discover.service` for the underlying
aggregations. Cache lifetime is owned by the service layer.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.discover.service import get_from_follows, get_popular_this_week

router = APIRouter(prefix="/discover", tags=["discover"])


def _require_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# Discover GETs are cheap enough on the server (cache-first) that the
# per-user budget can stay generous. Tighter than the feed so a runaway
# poll loop doesn't blow the Atlas read budget either.
_DISCOVER_RATE_LIMIT = rate_limit(
    endpoint="discover.read",
    per_user=RateLimit(limit=60, window_seconds=60),
)


@router.get(
    "/popular-this-week",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_DISCOVER_RATE_LIMIT)],
)
async def popular_this_week(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
) -> dict[str, Any]:
    """Top public album logs in the trailing 7 days (003 / FR-007..FR-009).

    Excludes albums the viewer has already logged. Response cached
    per-viewer for 5 minutes inside the service layer.
    """
    session = _require_session(request)
    albums = await get_popular_this_week(viewer_id=session.user_id, limit=limit)
    return {"albums": albums}


@router.get(
    "/from-follows",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_DISCOVER_RATE_LIMIT)],
)
async def from_follows(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
) -> dict[str, Any]:
    """Recent public album activity from the viewer's follow graph
    (003 / FR-010..FR-012).

    Each item carries an annotation byline (e.g. "@lily rated · 4/5")
    derived from the followee's most recent diary entry for the album.
    Empty list when the viewer follows nobody.
    """
    session = _require_session(request)
    items = await get_from_follows(viewer_id=session.user_id, limit=limit)
    return {"items": items}


__all__ = ["router"]
