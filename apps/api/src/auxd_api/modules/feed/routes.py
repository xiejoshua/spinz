"""Feed HTTP routes — friends-who-rated endpoint (T103) + home feed (T106).

Exposes two endpoints::

    GET /api/v1/albums/{album_id}/friends   (T103)
    GET /api/v1/feed                         (T106)

The album-detail rollup (``/api/v1/albums/{album_id}``) already returns
a ``friends`` array; the T103 endpoint exists for surfaces that don't
fetch the full album payload (e.g., a "friends activity on this album"
modal). The T106 home feed is the social spine — it fans-out followee
diary entries, applies the for-you weighting model (or skips it for
``mode=latest``), and pads with critic-seed activity when the follow
graph is thin.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auxd_api.lib.observability import log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.feed.service import (
    DEFAULT_HOME_FEED_LIMIT,
    MAX_HOME_FEED_LIMIT,
    FeedMode,
    FriendsAlbumNotFoundError,
    FriendsFeedError,
    build_home_feed,
    list_friends_who_rated,
)

_LOGGER = logging.getLogger("auxd.feed.routes")

router = APIRouter(tags=["feed"])


# Per-user 120/min — list endpoint; this is a read surface so a scroll-
# heavy client can warm the page quickly. Matches the diary read budget.
_FRIENDS_READ_RATE_LIMIT = rate_limit(
    endpoint="feed.friends",
    per_user=RateLimit(limit=120, window_seconds=60),
)

# Home feed is the dominant read surface; pull-to-refresh + scroll
# means the per-user budget is generous (180/min ≈ once every 333ms).
_HOME_FEED_READ_RATE_LIMIT = rate_limit(
    endpoint="feed.home",
    per_user=RateLimit(limit=180, window_seconds=60),
)


def _require_session(request: Request) -> Session:
    """Mirror diary routes — fail loudly when no session is attached."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


@router.get(
    "/albums/{album_id}/friends",
    dependencies=[Depends(_FRIENDS_READ_RATE_LIMIT)],
)
async def get_friends_for_album(
    album_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Return the diary entries from followed users on ``album_id``.

    Response shape::

        {
          "entries": [
            {"user_id", "handle", "display_name", "avatar_url",
             "rating", "auxed", "logged_at", "review_id"},
            ...
          ],
          "next_cursor": null
        }

    Sort order: ``rating DESC, logged_at DESC``. Visibility filtering
    uses the standard ``can_read_with_relation`` matrix so private and
    follower-visibility entries follow the same rules as the rest of
    the API.

    No pagination at MVP — friends-who-rated lists are small per album.
    """
    try:
        entries = await list_friends_who_rated(
            album_id=album_id,
            viewer_id=session.user_id,
        )
    except FriendsAlbumNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.code,
        ) from exc
    except FriendsFeedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.code,
        ) from exc
    return {
        "entries": [entry.to_wire() for entry in entries],
        "next_cursor": None,
    }


# ---------------------------------------------------------------------------
# T106 — Home feed
# ---------------------------------------------------------------------------


@router.get(
    "/feed",
    dependencies=[Depends(_HOME_FEED_READ_RATE_LIMIT)],
)
async def get_home_feed(
    session: Annotated[Session, Depends(_require_session)],
    cursor: str | None = None,
    limit: int = DEFAULT_HOME_FEED_LIMIT,
    mode: str = FeedMode.FOR_YOU,
) -> dict[str, Any]:
    """Return the viewer's home feed (fan-out-on-read + weighting).

    Query params:

    * ``cursor`` — composite base64 cursor from a prior page; malformed
      cursors are silently treated as "no cursor" (matches diary).
    * ``limit`` — page size, default 25, capped at
      :data:`MAX_HOME_FEED_LIMIT`.
    * ``mode`` — ``for_you`` (default) applies the weighting model;
      ``latest`` disables weights and sorts ``logged_at DESC`` only.

    Response shape::

        {
          "entries": [FeedEntry, ...],
          "next_cursor": str | null,
          "users":  {id: UserCard},
          "albums": {id: AlbumCard},
          "reviews": {id: ReviewSnippet}
        }

    Each ``FeedEntry`` carries ``score`` / ``score_components`` only for
    ``mode=for_you``; ``latest`` strips them so the wire shape reflects
    the actual sort key.
    """
    started = time.perf_counter()
    capped_limit = max(1, min(limit, MAX_HOME_FEED_LIMIT))
    result = await build_home_feed(
        viewer_id=session.user_id,
        cursor=cursor,
        limit=capped_limit,
        mode=mode,
    )
    log_call(
        provider="auxd",
        endpoint="feed.home_read",
        latency_ms=(time.perf_counter() - started) * 1000,
        status="ok",
        extra={
            "user_id": session.user_id,
            "count": len(result.entries),
            "mode": FeedMode.parse(mode),
            "has_cursor": cursor is not None,
        },
    )
    include_score = FeedMode.parse(mode) == FeedMode.FOR_YOU
    return {
        "entries": [entry.to_wire(include_score=include_score) for entry in result.entries],
        "next_cursor": result.next_cursor,
        "users": result.users,
        "albums": result.albums,
        "reviews": result.reviews,
        "mode": FeedMode.parse(mode),
    }


__all__ = ["router"]
