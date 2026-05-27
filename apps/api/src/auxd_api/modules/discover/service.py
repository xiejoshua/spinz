"""Discover service — popular-this-week + from-follows aggregations.

Two read paths backing the new ``/discover`` editorial homepage:

* :func:`get_popular_this_week` — top albums by public log count in the
  trailing 7 days. Excludes albums the viewer has already logged so
  the surface stays "things you might want to try."
* :func:`get_from_follows` — recent public album activity from the
  viewer's follow graph. Deduped by album with the most-recent
  activity carried as an annotation byline ("@handle rated · 4/5").

Both responses are cached in Redis with a per-viewer key. Cache is
fail-open via :func:`auxd_api.redis_client.cache_get` /
:func:`cache_set` — a Redis blip degrades to a slow path, never a 500.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import User, UserStatus
from auxd_api.redis_client import cache_get, cache_set

_LOGGER = logging.getLogger("auxd.discover")

_POPULAR_WINDOW = timedelta(days=7)
_FROM_FOLLOWS_WINDOW = timedelta(days=30)

# Cache TTLs match the freshness targets in plan §NFR.
_POPULAR_CACHE_TTL = 5 * 60  # 5 minutes
_FROM_FOLLOWS_CACHE_TTL = 60  # 1 minute


def _popular_cache_key(viewer_id: str) -> str:
    # v3 bumped 2026-05-24: started filtering coverless albums out of
    # the payload. v2 dropped viewer-already-logged; v1 was the initial
    # shape. Bumping ensures stale v2 cache entries don't keep serving
    # rows that the new logic would now hide.
    return f"discover:popular:v3:{viewer_id}"


def _from_follows_cache_key(viewer_id: str) -> str:
    # v2 bumped 2026-05-24 alongside the coverless-row filter; same
    # rationale as the popular cache key bump.
    return f"discover:from_follows:v2:{viewer_id}"


def _serialize_album_summary(album: Album) -> dict[str, Any]:
    """Compact album payload for the Discover surface.

    Mirrors :func:`auxd_api.modules.search.service._serialize_album`
    so the frontend can reuse the same ``AlbumCard`` shape across
    search and discover.
    """
    return {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_name": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
    }


async def _hydrate_albums(album_ids: list[str]) -> dict[str, Album]:
    """Batch-fetch albums by id. Returns a {id: Album} map.

    Atlas / Mongo returns the rows out of order; we keep the caller-
    chosen ordering by indexing into this map rather than relying on
    Mongo's return order.
    """
    if not album_ids:
        return {}
    rows = await Album.find({"_id": {"$in": album_ids}}).to_list()
    return {a.id: a for a in rows}


# ---------------------------------------------------------------------------
# Popular this week
# ---------------------------------------------------------------------------


async def get_popular_this_week(*, viewer_id: str, limit: int) -> list[dict[str, Any]]:
    """Top public album logs in the trailing 7 days.

    Result list is cached per-viewer for 5 minutes. Earlier revisions
    excluded albums the viewer had already logged on the theory that
    "Popular" should mean "try something new" — but on a small / early
    catalog that filter swallowed the section entirely whenever the
    viewer was also the only logger. Popular now means popular, period;
    the user can revisit albums they've already logged here without
    issue (Letterboxd works the same way).
    """
    cache_key = _popular_cache_key(viewer_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        try:
            cached_payload = json.loads(cached)
            if isinstance(cached_payload, list):
                hits: list[dict[str, Any]] = cached_payload[:limit]
                return hits
        except (json.JSONDecodeError, ValueError):
            # Stale / corrupt cache row — fall through to recompute.
            _LOGGER.info(
                "discover.popular.cache_parse_error",
                extra={"event": "discover.popular.cache_parse_error"},
            )

    cutoff = datetime.now(UTC) - _POPULAR_WINDOW

    # Slight over-fetch leaves headroom for occasional dangling album
    # references (rows whose Album doc has since been hard-deleted).
    over_fetch = limit + 4

    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "logged_at": {"$gte": cutoff},
                "visibility": Visibility.PUBLIC.value,
                "deleted_at": None,
            }
        },
        {
            "$group": {
                "_id": "$album_id",
                "log_count": {"$sum": 1},
                "latest_logged_at": {"$max": "$logged_at"},
            }
        },
        {"$sort": {"log_count": -1, "latest_logged_at": -1}},
        {"$limit": over_fetch},
    ]
    rows: list[dict[str, Any]] = await DiaryEntry.aggregate(pipeline).to_list()

    keep: list[tuple[str, int]] = []
    for row in rows:
        album_id = row.get("_id")
        if not isinstance(album_id, str):
            continue
        keep.append((album_id, int(row.get("log_count", 0))))
        if len(keep) >= limit:
            break

    if not keep:
        # Empty result — still cache so we don't repeatedly recompute a
        # cold start. Short TTL keeps the cold state from sticking too
        # long if data arrives mid-window.
        await cache_set(cache_key, json.dumps([]), ex_seconds=60)
        return []

    album_map = await _hydrate_albums([aid for aid, _ in keep])
    payload: list[dict[str, Any]] = []
    for album_id, log_count in keep:
        album = album_map.get(album_id)
        if album is None:
            continue
        # Discover surfaces hide coverless rows — an empty grid cell
        # reads as broken, whereas the Log sheet keeps full coverage
        # so users can log obscure releases.
        if not (album.mbid or album.cover_art_url):
            continue
        item = _serialize_album_summary(album)
        item["log_count"] = log_count
        payload.append(item)

    await cache_set(cache_key, json.dumps(payload), ex_seconds=_POPULAR_CACHE_TTL)
    return payload


# ---------------------------------------------------------------------------
# From your follows
# ---------------------------------------------------------------------------


def _build_annotation(
    *,
    entry: DiaryEntry,
    review_body: str | None,
    actor: User,
) -> dict[str, Any]:
    """Compose the byline payload for a from-follows album.

    Verb is "rated" when the entry carries a rating, "reviewed" when a
    review is attached without a rating, else plain "logged". The
    rating value is included verbatim so the frontend can render the
    star micro-control without a second roundtrip.
    """
    if entry.rating is not None:
        verb = "rated"
    elif review_body:
        verb = "reviewed"
    else:
        verb = "logged"
    return {
        "actor_handle": actor.handle,
        "actor_display_name": actor.display_name,
        "actor_avatar_url": actor.avatar_url,
        "verb": verb,
        "rating": entry.rating,
        "logged_at": entry.logged_at.isoformat(),
    }


async def get_from_follows(*, viewer_id: str, limit: int) -> list[dict[str, Any]]:
    """Recent public album activity from the viewer's follow graph.

    Pulls the followee user_ids, fetches their public diary entries
    in the trailing 30 days, dedupes by album (most recent activity
    wins), and returns the top N with an annotation byline. Result
    list is cached per-viewer for 60 seconds.
    """
    cache_key = _from_follows_cache_key(viewer_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        try:
            cached_payload = json.loads(cached)
            if isinstance(cached_payload, list):
                hits: list[dict[str, Any]] = cached_payload[:limit]
                return hits
        except (json.JSONDecodeError, ValueError):
            _LOGGER.info(
                "discover.from_follows.cache_parse_error",
                extra={"event": "discover.from_follows.cache_parse_error"},
            )

    follows = await Follow.find(
        {"follower_id": viewer_id, "state": FollowState.ACCEPTED.value}
    ).to_list()
    followee_ids = [f.followee_id for f in follows]

    if not followee_ids:
        await cache_set(cache_key, json.dumps([]), ex_seconds=_FROM_FOLLOWS_CACHE_TTL)
        return []

    cutoff = datetime.now(UTC) - _FROM_FOLLOWS_WINDOW

    # Over-fetch by 5x to leave headroom for the album dedup pass.
    over_fetch = max(limit * 5, limit + 20)

    recent_entries = (
        await DiaryEntry.find(
            {
                "user_id": {"$in": followee_ids},
                "logged_at": {"$gte": cutoff},
                "visibility": Visibility.PUBLIC.value,
                "deleted_at": None,
            }
        )
        .sort("-logged_at")
        .limit(over_fetch)
        .to_list()
    )

    if not recent_entries:
        await cache_set(cache_key, json.dumps([]), ex_seconds=_FROM_FOLLOWS_CACHE_TTL)
        return []

    # Dedup by album, keep most recent activity per album.
    seen_albums: set[str] = set()
    keep_entries: list[DiaryEntry] = []
    for entry in recent_entries:
        if entry.album_id in seen_albums:
            continue
        seen_albums.add(entry.album_id)
        keep_entries.append(entry)
        if len(keep_entries) >= limit:
            break

    # Batch-load albums, actors, and any attached reviews.
    album_map = await _hydrate_albums([e.album_id for e in keep_entries])
    actor_rows = await User.find(
        {"_id": {"$in": [e.user_id for e in keep_entries]}, "status": UserStatus.ACTIVE.value}
    ).to_list()
    actor_map = {u.id: u for u in actor_rows}

    review_ids = [e.review_id for e in keep_entries if e.review_id]
    review_rows: list[Review] = []
    if review_ids:
        review_rows = await Review.find({"_id": {"$in": review_ids}, "deleted_at": None}).to_list()
    review_map = {r.id: r for r in review_rows}

    payload: list[dict[str, Any]] = []
    for entry in keep_entries:
        album = album_map.get(entry.album_id)
        actor = actor_map.get(entry.user_id)
        if album is None or actor is None:
            # Dangling reference — actor was deleted or album row gone.
            # Skip silently; the caller paginates by count so a hole here
            # just thins the surface for this viewer.
            continue
        # Hide coverless rows (see ``get_popular_this_week`` for the
        # same rationale). A follow-graph activity for an album with no
        # cover art renders as a broken grid cell.
        if not (album.mbid or album.cover_art_url):
            continue
        review = review_map.get(entry.review_id) if entry.review_id else None
        review_body = review.body if review is not None else None
        item = {
            "album": _serialize_album_summary(album),
            "annotation": _build_annotation(entry=entry, review_body=review_body, actor=actor),
        }
        payload.append(item)

    await cache_set(cache_key, json.dumps(payload), ex_seconds=_FROM_FOLLOWS_CACHE_TTL)
    return payload


__all__ = ["get_popular_this_week", "get_from_follows"]
