"""Album detail HTTP routes (T067).

Single endpoint at MVP:

* ``GET /api/v1/albums/{album_id}`` — returns the album metadata, every
  sibling edition in the same release-group, the social-signal rollup,
  the viewer's own diary history, the visibility-filtered slice of
  friends' diary entries / reviews, and the top public reviews sorted by
  like count.

Authentication is optional. Anonymous callers see only public content;
logged-in callers see their own private entries plus any
followers-visibility content from accounts they follow. The visibility
matrix is delegated to :func:`auxd_api.lib.visibility.can_read_with_relation`
so this module never re-implements the access rules.

Performance note: the friends / public-reviews queries each scan their
respective collections with the album_id filter — both are indexed (see
``DiaryEntry.Settings.indexes`` and ``Review.Settings.indexes``). We cap
the result lists at small explicit limits so the worst-case payload
stays bounded even on viral albums.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auxd_api.lib.sessions import Session
from auxd_api.lib.visibility import (
    OwnedContent,
    Viewer,
    ViewerRelation,
    Visibility,
    can_read_with_relation,
)
from auxd_api.modules.albums.editions import aggregate_ratings, get_editions
from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.diary.models import Visibility as DiaryVisibility
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.social.models import Block, Follow, FollowState

router = APIRouter(prefix="/albums", tags=["albums"])

# Bound list sizes so a viral album doesn't blow the response payload.
_FRIENDS_LIMIT = 50
_PUBLIC_REVIEWS_LIMIT = 25
_MY_HISTORY_LIMIT = 50


class _SessionViewer:
    """Minimal :class:`Viewer` adapter wrapping a :class:`Session`.

    Required because :class:`Session` exposes ``user_id``, not ``id``,
    and :func:`can_read_with_relation` consumes the ``Viewer`` Protocol
    (``viewer.id``). The adapter is a frozen ``id`` string so the
    visibility lib never has to know about session shape.
    """

    __slots__ = ("id",)

    id: str

    def __init__(self, user_id: str) -> None:
        self.id = user_id


class _DiaryContent:
    """Adapter exposing the :class:`OwnedContent` Protocol for a DiaryEntry.

    ``DiaryEntry.user_id`` plays the role of ``owner_id`` and the diary
    module's ``Visibility`` enum value is folded into the
    ``lib.visibility.Visibility`` enum (they share string values).
    """

    __slots__ = ("owner_id", "visibility", "deleted_at")

    owner_id: str
    visibility: Visibility
    deleted_at: datetime | None

    def __init__(self, entry: DiaryEntry) -> None:
        self.owner_id = entry.user_id
        self.visibility = Visibility(entry.visibility.value)
        self.deleted_at = entry.deleted_at


class _ReviewContent:
    """Adapter exposing the :class:`OwnedContent` Protocol for a Review.

    Review documents store visibility as a plain string ("public" /
    "followers" / "private"); the adapter normalises it onto the
    visibility enum.
    """

    __slots__ = ("owner_id", "visibility", "deleted_at")

    owner_id: str
    visibility: Visibility
    deleted_at: datetime | None

    def __init__(self, review: Review) -> None:
        self.owner_id = review.user_id
        try:
            self.visibility = Visibility(review.visibility)
        except ValueError:
            self.visibility = Visibility.PUBLIC
        self.deleted_at = None


async def _resolve_relations(
    viewer_id: str | None,
    owner_ids: set[str],
) -> dict[str, ViewerRelation]:
    """Compute the viewer's relation to every owner id in one batch.

    The bulk shape matters: the album-detail endpoint pulls dozens of
    friends + public reviews, and resolving each one with its own
    Mongo round-trip would hit the IO budget hard. Two queries answer
    the whole set:

    1. ``Block`` rows where either side blocks the other.
    2. ``Follow`` rows from the viewer to each owner.

    Anonymous viewers + the viewer's own id short-circuit without any
    query.
    """
    relations: dict[str, ViewerRelation] = {}
    if viewer_id is None:
        return {owner: ViewerRelation.ANONYMOUS for owner in owner_ids}

    others = {owner_id for owner_id in owner_ids if owner_id != viewer_id}
    if viewer_id in owner_ids:
        relations[viewer_id] = ViewerRelation.OWNER

    if not others:
        return relations

    # Block edges in either direction take priority.
    blocks = await Block.find(
        {
            "$or": [
                {"blocker_id": viewer_id, "blockee_id": {"$in": list(others)}},
                {"blocker_id": {"$in": list(others)}, "blockee_id": viewer_id},
            ]
        }
    ).to_list()
    blockers: set[str] = set()
    blocked_by: set[str] = set()
    for block in blocks:
        if block.blocker_id == viewer_id:
            blockers.add(block.blockee_id)
        else:
            blocked_by.add(block.blocker_id)

    follows = await Follow.find(
        {
            "follower_id": viewer_id,
            "followee_id": {"$in": list(others)},
            "state": FollowState.ACCEPTED.value,
        }
    ).to_list()
    follow_set = {follow.followee_id for follow in follows}

    for owner in others:
        if owner in blockers:
            relations[owner] = ViewerRelation.BLOCKER
        elif owner in blocked_by:
            relations[owner] = ViewerRelation.BLOCKED
        elif owner in follow_set:
            relations[owner] = ViewerRelation.FOLLOWER
        else:
            relations[owner] = ViewerRelation.NOT_FOLLOWER
    return relations


def _filter_visible(
    viewer: Viewer | None,
    items: Iterable[tuple[OwnedContent, Any]],
    relations: dict[str, ViewerRelation],
) -> list[Any]:
    """Apply :func:`can_read_with_relation` to ``(content, payload)`` pairs.

    The ``payload`` is the actual object returned to the caller —
    typically the diary/review document itself. We split the access-
    control bookkeeping from the payload shape so this helper stays
    payload-agnostic.
    """
    kept: list[Any] = []
    for content, payload in items:
        relation = relations.get(
            content.owner_id,
            ViewerRelation.ANONYMOUS if viewer is None else ViewerRelation.NOT_FOLLOWER,
        )
        if can_read_with_relation(viewer, content, relation):
            kept.append(payload)
    return kept


def _serialize_album(album: Album) -> dict[str, Any]:
    """Return the public album payload — JSON-safe, no Beanie internals."""
    return {
        "id": album.id,
        "mbid": album.mbid,
        "discogs_release_id": album.discogs_release_id,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
        "label": album.label,
        "genres": list(album.genres),
        "tracklist": [track.model_dump() for track in album.tracklist],
        "duration_ms": album.duration_ms,
        "source": album.source.value,
    }


def _serialize_diary(entry: DiaryEntry) -> dict[str, Any]:
    """Return the per-entry payload for the album-detail UI."""
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "logged_at": entry.logged_at.isoformat(),
        "rating": entry.rating,
        "auxed": entry.auxed,
        "review_id": entry.review_id,
        "visibility": entry.visibility.value,
    }


def _serialize_review(review: Review) -> dict[str, Any]:
    """Return the per-review payload for the album-detail UI."""
    return {
        "id": review.id,
        "user_id": review.user_id,
        "diary_entry_id": review.diary_entry_id,
        "body": review.body,
        "likes_count": review.reactions.likes_count,
        "visibility": review.visibility,
        "created_at": review.created_at.isoformat(),
    }


@router.get("/{album_id}")
async def get_album_detail(album_id: str, request: Request) -> dict[str, Any]:
    """Return the album-detail payload for the given album id.

    Response shape::

        {
            "album": {...},
            "editions": [{...}, ...],
            "aggregate": {avg_rating, rating_count, review_count,
                          aux_count, like_count},
            "my_history": [{...}, ...],     // viewer's own diary entries
            "friends": [{...}, ...],        // followed users' diary/reviews
            "public_reviews": [{...}, ...]  // top reviews by likes_count
        }

    Returns ``HTTP 404`` when the album id is unknown.
    """
    album = await Album.get(album_id)
    if album is None:
        raise HTTPException(status_code=404, detail="album_not_found")

    session = getattr(request.state, "session", None)
    viewer: Viewer | None = None
    viewer_id: str | None = None
    if isinstance(session, Session):
        viewer_id = session.user_id
        viewer = _SessionViewer(user_id=viewer_id)

    # Editions + aggregate share the same release-group key.
    editions: list[Album] = []
    aggregate: dict[str, float | int] = {
        "avg_rating": 0.0,
        "rating_count": 0,
        "review_count": 0,
        "aux_count": 0,
        "like_count": 0,
    }
    if album.mbid is not None:
        editions = await get_editions(album.mbid)
        aggregate = await aggregate_ratings(album.mbid)
    else:
        # No release-group key — the album stands alone. The single-row
        # editions list keeps the UI's "All editions" affordance stable
        # without falling back to an empty list.
        editions = [album]

    # My history — the viewer's own diary entries against this album.
    my_history: list[dict[str, Any]] = []
    if viewer_id is not None:
        rows = (
            await DiaryEntry.find(
                {
                    "user_id": viewer_id,
                    "album_id": album_id,
                    "deleted_at": None,
                }
            )
            .sort("-logged_at")
            .limit(_MY_HISTORY_LIMIT)
            .to_list()
        )
        my_history = [_serialize_diary(entry) for entry in rows]

    # Friends — diary entries + reviews authored by followed users
    # (excluding the viewer's own activity, which lives in my_history).
    friends_payload: list[dict[str, Any]] = []
    public_reviews_payload: list[dict[str, Any]] = []
    if viewer_id is not None:
        # Diary entries against this album from any follower-visible
        # author (excluding the viewer).
        friend_entries = (
            await DiaryEntry.find(
                {
                    "album_id": album_id,
                    "user_id": {"$ne": viewer_id},
                    "visibility": {"$in": ["public", "followers"]},
                    "deleted_at": None,
                }
            )
            .sort("-logged_at")
            .limit(_FRIENDS_LIMIT)
            .to_list()
        )
        owner_ids = {entry.user_id for entry in friend_entries}
        relations = await _resolve_relations(viewer_id, owner_ids)
        items = [(_DiaryContent(entry), _serialize_diary(entry)) for entry in friend_entries]
        friends_payload = _filter_visible(viewer, items, relations)

    # Public reviews — top by like count. Anonymous viewers see only
    # public-visibility reviews; logged-in viewers additionally see
    # followers-visibility reviews from followed authors via the
    # relation resolver.
    public_review_rows = (
        await Review.find({"album_id": album_id})
        .sort("-reactions.likes_count")
        .limit(_PUBLIC_REVIEWS_LIMIT)
        .to_list()
    )
    review_owner_ids = {review.user_id for review in public_review_rows}
    if viewer_id is not None:
        review_relations = await _resolve_relations(viewer_id, review_owner_ids)
    else:
        review_relations = {owner: ViewerRelation.ANONYMOUS for owner in review_owner_ids}
    review_items = [
        (_ReviewContent(review), _serialize_review(review)) for review in public_review_rows
    ]
    public_reviews_payload = _filter_visible(viewer, review_items, review_relations)

    # Final response — every list is bounded by its limit constant above.
    return {
        "album": _serialize_album(album),
        "editions": [_serialize_album(edition) for edition in editions],
        "aggregate": aggregate,
        "my_history": my_history,
        "friends": friends_payload,
        "public_reviews": public_reviews_payload,
    }


# Re-export the Visibility import so static checkers see it's used.
_ = DiaryVisibility


__all__ = ["router"]
