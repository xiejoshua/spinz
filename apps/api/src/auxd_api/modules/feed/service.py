"""Feed service layer — friends-on-album rollup (T103) and home feed (T106).

Pure async business logic for both feed surfaces. The route layer in
:mod:`auxd_api.modules.feed.routes` is thin glue; the visibility filter,
the relation resolver, and the user-denormalisation join all live here
so they can be unit-tested without HTTP.

Surface ownership:

* ``list_friends_who_rated`` (T103) — diary slice from followed users
  who rated a given album. Lightweight; used by surfaces that don't
  fetch the full album payload.
* ``build_home_feed`` (T106) — the home-feed fan-out: followed-user
  diary entries, optionally weighted for "For You" mode, with critic-
  seed padding when the follow graph is thin.

For-you weighting (plan §10.2):

* base score = 1.0
* +20% if entry has a Review attached
* +15% if rating is in {5.0, 1.0} (extreme ratings)
* +10% if entry author is one of the viewer's top-5 most-interacted-
  with (proxy: top-5 by ``Follow.created_at DESC`` at MVP — see TODO
  in :func:`_load_top_authors`)
* half-life decay: ``score *= 0.5 ^ (age_hours / 72)`` (3-day half-life)

Latest mode disables all weights and sorts by ``logged_at DESC`` only.

Sort order:

* Friends-on-album: ``rating DESC, logged_at DESC``.
* Home feed for_you: ``score DESC, logged_at DESC``.
* Home feed latest: ``logged_at DESC`` only.

Entries without a rating (``rating IS NULL``) sort last in the friends
endpoint; null-rating but ``auxed=True`` entries still show up at the
bottom of the rated cluster because the social signal "my friend
listened to this album" still has value.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from auxd_api.lib.visibility import (
    OwnedContent,
    ViewerRelation,
    Visibility,
    can_read_with_relation,
)
from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.seeding.service import critic_seed_user_ids
from auxd_api.modules.social.models import Block, Follow, FollowState
from auxd_api.modules.users.models import User

__all__ = [
    "DEFAULT_HOME_FEED_LIMIT",
    "FeedEntry",
    "FeedMode",
    "FriendActivityEntry",
    "FriendsAlbumNotFoundError",
    "FriendsFeedError",
    "HomeFeedResult",
    "MAX_HOME_FEED_LIMIT",
    "MIN_FEED_BEFORE_PADDING",
    "build_home_feed",
    "decode_home_feed_cursor",
    "encode_home_feed_cursor",
    "list_friends_who_rated",
]


# Home feed bounds (plan §10).
DEFAULT_HOME_FEED_LIMIT = 25
MAX_HOME_FEED_LIMIT = 100
# When the follow-graph fan-out returns fewer than this, the service
# pads with recent critic-seed activity so the empty-feed state is
# never shown to a user with > 0 follows.
MIN_FEED_BEFORE_PADDING = 5
# Top-N proxy for "most-interacted-with" — MVP heuristic uses most-
# recently-followed since we don't have read-receipts / engagement
# counts yet.
TOP_AUTHORS_PROXY_N = 5


class FeedMode(str):
    """Wire-stable enum-like for the ``mode`` query parameter.

    A bare string subclass rather than :class:`enum.Enum` to keep
    Pydantic + FastAPI happy without a custom validator. Two modes:

    * ``for_you`` — apply the weighting model.
    * ``latest`` — plain reverse-chronological.
    """

    FOR_YOU = "for_you"
    LATEST = "latest"

    @classmethod
    def parse(cls, value: str | None) -> str:
        """Coerce a wire value to a known mode; unknowns fall back to FOR_YOU."""
        if value == cls.LATEST:
            return cls.LATEST
        return cls.FOR_YOU


# Bounded page size — same ceiling as the album-detail friends array so
# both surfaces have the same worst-case payload.
_FRIENDS_LIMIT = 50


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FriendsFeedError(Exception):
    """Base class for the feed service. ``code`` is the wire identifier."""

    code: str = "feed_error"


class FriendsAlbumNotFoundError(FriendsFeedError):
    """Raised when the album id resolves to nothing."""

    code = "album_not_found"


# ---------------------------------------------------------------------------
# Wire shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FriendActivityEntry:
    """A single row in the friends-on-album response."""

    user_id: str
    handle: str
    display_name: str
    avatar_url: str | None
    rating: float | None
    auxed: bool
    logged_at: datetime
    review_id: str | None

    def to_wire(self) -> dict[str, Any]:
        """Return the JSON-serialisable payload for the route layer."""
        return {
            "user_id": self.user_id,
            "handle": self.handle,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "rating": self.rating,
            "auxed": self.auxed,
            "logged_at": self.logged_at.isoformat(),
            "review_id": self.review_id,
        }


# ---------------------------------------------------------------------------
# Visibility adapters — mirror diary/albums routes
# ---------------------------------------------------------------------------


class _Viewer:
    __slots__ = ("id",)

    id: str

    def __init__(self, user_id: str) -> None:
        self.id = user_id


class _DiaryContent:
    """Adapter exposing :class:`OwnedContent` for a :class:`DiaryEntry`."""

    __slots__ = ("deleted_at", "owner_id", "visibility")

    owner_id: str
    visibility: Visibility
    deleted_at: datetime | None

    def __init__(self, entry: DiaryEntry) -> None:
        self.owner_id = entry.user_id
        self.visibility = Visibility(entry.visibility.value)
        self.deleted_at = entry.deleted_at


# ---------------------------------------------------------------------------
# Relation resolver — mirror diary's pattern
# ---------------------------------------------------------------------------


async def _resolve_relations(
    viewer_id: str,
    owner_ids: set[str],
) -> dict[str, ViewerRelation]:
    """Resolve the viewer's relation to every owner id in one batch.

    Identical shape to ``diary/routes._resolve_relations`` — kept inline
    so the feed module is independently testable. Two queries answer
    the whole set: one Block scan, one Follow scan.
    """
    relations: dict[str, ViewerRelation] = {}
    others = {owner_id for owner_id in owner_ids if owner_id != viewer_id}
    if viewer_id in owner_ids:
        relations[viewer_id] = ViewerRelation.OWNER
    if not others:
        return relations

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def list_friends_who_rated(
    *,
    album_id: str,
    viewer_id: str,
) -> list[FriendActivityEntry]:
    """Return the diary slice from users ``viewer_id`` follows on ``album_id``.

    Behaviour:

    * 404 (raised) if the album is unknown.
    * Reads the viewer's accepted Follow rows; if the viewer follows
      nobody, the result is an empty list (cheap fast-path).
    * Pulls DiaryEntry rows by ``album_id`` for that follow set.
    * Filters via :func:`can_read_with_relation` so block edges and
      private-visibility entries are honoured.
    * Joins User to denormalise handle / display_name / avatar_url.
    * Sorts ``rating DESC, logged_at DESC`` after filtering.
    """
    album = await Album.get(album_id)
    if album is None:
        raise FriendsAlbumNotFoundError("album not found")

    follows = await Follow.find(
        {
            "follower_id": viewer_id,
            "state": FollowState.ACCEPTED.value,
        }
    ).to_list()
    followee_ids = {row.followee_id for row in follows}
    if not followee_ids:
        return []

    entries = await DiaryEntry.find(
        {
            "album_id": album_id,
            "user_id": {"$in": list(followee_ids)},
            "deleted_at": None,
        }
    ).to_list()
    if not entries:
        return []

    viewer = _Viewer(viewer_id)
    owner_ids = {entry.user_id for entry in entries}
    relations = await _resolve_relations(viewer_id, owner_ids)

    visible: list[DiaryEntry] = []
    for entry in entries:
        content: OwnedContent = _DiaryContent(entry)
        relation = relations.get(entry.user_id, ViewerRelation.NOT_FOLLOWER)
        if can_read_with_relation(viewer, content, relation):
            visible.append(entry)

    if not visible:
        return []

    # Sort: rating DESC (None last among rated rows), logged_at DESC.
    # ``-rating`` won't work in Python because ``None`` is unorderable;
    # we explicitly bin entries with no rating to the end. Within each
    # bin, ``logged_at DESC`` is the tie-breaker, expressed as a negated
    # epoch float so a plain ascending tuple compare yields DESC order.
    def _sort_key(entry: DiaryEntry) -> tuple[int, float, float]:
        # bin: 0 = has rating, 1 = no rating
        bin_idx = 0 if entry.rating is not None else 1
        rating_score = -(entry.rating or 0.0)
        epoch = entry.logged_at.timestamp()
        return (bin_idx, rating_score, -epoch)

    visible.sort(key=_sort_key)

    # Join users in a single batch.
    users = await User.find({"_id": {"$in": list({e.user_id for e in visible})}}).to_list()
    user_map = {user.id: user for user in users}

    out: list[FriendActivityEntry] = []
    for entry in visible[:_FRIENDS_LIMIT]:
        user = user_map.get(entry.user_id)
        if user is None:
            # Should not happen — if the user has been hard-deleted, the
            # diary entries should have been cascade-deleted by T058.
            # Skip defensively rather than emit a half-populated row.
            continue
        out.append(
            FriendActivityEntry(
                user_id=user.id,
                handle=user.handle,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                rating=entry.rating,
                auxed=entry.auxed,
                logged_at=entry.logged_at,
                review_id=entry.review_id,
            )
        )
    return out


# ---------------------------------------------------------------------------
# T106 — Home feed (fan-out-on-read + weighting)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FeedEntry:
    """A single home-feed row (currently always wraps a DiaryEntry).

    The ``kind`` field is a forward-compat hook: when reviews-only or
    backlog activity surface in the feed we extend the kind set without
    touching the wire shape. At MVP every entry is a ``diary_entry``.

    ``score`` / ``score_components`` are populated only for the for-you
    mode. The frontend uses ``score_components`` for transparency (small
    "Because you follow X" hints).
    """

    kind: str
    id: str
    user_id: str
    album_id: str
    logged_at: datetime
    rating: float | None
    auxed: bool
    review_id: str | None
    score: float | None = None
    score_components: dict[str, Any] = field(default_factory=dict)

    def to_wire(self, *, include_score: bool) -> dict[str, Any]:
        """Return the JSON-serialisable payload for the route layer.

        ``include_score`` is False for latest mode so the wire shape
        doesn't carry pseudo-relevance signals that don't apply.
        """
        payload: dict[str, Any] = {
            "kind": self.kind,
            "id": self.id,
            "user_id": self.user_id,
            "album_id": self.album_id,
            "logged_at": self.logged_at.isoformat(),
            "rating": self.rating,
            "auxed": self.auxed,
            "review_id": self.review_id,
        }
        if include_score and self.score is not None:
            payload["score"] = self.score
            payload["score_components"] = dict(self.score_components)
        return payload


@dataclass(frozen=True, slots=True)
class HomeFeedResult:
    """Return shape for :func:`build_home_feed`.

    Bundles the entries plus three sidecars (users / albums / reviews)
    so the frontend can render a card without per-row roundtrips. The
    sidecars are keyed maps for stable lookups on the client side.
    """

    entries: list[FeedEntry]
    next_cursor: str | None
    users: dict[str, dict[str, Any]]
    albums: dict[str, dict[str, Any]]
    reviews: dict[str, dict[str, Any]]


# ---------------------------------------------------------------------------
# Cursor (base64 JSON) — composite (logged_at, entry_id) plus optional score.
# ---------------------------------------------------------------------------


def encode_home_feed_cursor(
    *,
    logged_at: datetime,
    entry_id: str,
    score: float | None = None,
) -> str:
    """Encode a composite cursor for the home feed.

    Same shape as the diary cursor — a JSON ``{l, i}`` payload base64-
    URL-safe-encoded — with an optional ``s`` field for the for-you
    score. Malformed cursors decoded later treat as "no cursor" so URL
    tampering can't surface meaningful errors.
    """
    payload: dict[str, Any] = {"l": logged_at.isoformat(), "i": entry_id}
    if score is not None:
        payload["s"] = score
    raw = json.dumps(payload, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).rstrip(b"=").decode("ascii")


def decode_home_feed_cursor(cursor: str | None) -> tuple[datetime, str, float | None] | None:
    """Inverse of :func:`encode_home_feed_cursor`. Returns ``None`` on bad input."""
    if cursor is None:
        return None
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    logged_at_str = payload.get("l")
    entry_id = payload.get("i")
    score = payload.get("s")
    if not isinstance(logged_at_str, str) or not isinstance(entry_id, str):
        return None
    if score is not None and not isinstance(score, (int, float)):
        return None
    try:
        logged_at = datetime.fromisoformat(logged_at_str)
    except ValueError:
        return None
    return logged_at, entry_id, (float(score) if score is not None else None)


# ---------------------------------------------------------------------------
# Helper — viewer top authors proxy
# ---------------------------------------------------------------------------


async def _load_top_authors(viewer_id: str) -> set[str]:
    """Return the viewer's top-N "most-interacted-with" author ids.

    MVP proxy: the 5 most-recently-followed users. We don't have read-
    receipt or like-engagement counts yet; once we do, the proxy
    upgrades to "top-5 by interaction frequency" without changing the
    public surface.

    TODO: upgrade to true interaction-count ranking once review/likes +
    profile-page-views telemetry lands.
    """
    rows = (
        await Follow.find({"follower_id": viewer_id, "state": FollowState.ACCEPTED.value})
        .sort("-created_at")
        .limit(TOP_AUTHORS_PROXY_N)
        .to_list()
    )
    return {row.followee_id for row in rows}


def _coerce_aware(value: datetime) -> datetime:
    """Coerce a naive datetime to UTC.

    mongomock-motor strips ``tzinfo`` on read; production Mongo also
    stores UTC. Stamping UTC when missing is a no-op for real reads and
    keeps in-memory tests honest.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _score_entry(
    entry: DiaryEntry,
    *,
    now: datetime,
    top_authors: set[str],
) -> tuple[float, dict[str, Any]]:
    """Compute the for-you score + ``score_components`` for one entry.

    Components (per plan §10.2):

    * base 1.0
    * +20% if review attached
    * +15% if rating in {5.0, 1.0}
    * +10% if author in top-N
    * half-life decay: ``score *= 0.5 ^ (age_hours / 72)``
    """
    components: dict[str, Any] = {"base": 1.0}
    score = 1.0
    if entry.review_id is not None:
        score *= 1.20
        components["review_attached"] = 1.20
    if entry.rating in (5.0, 1.0):
        score *= 1.15
        components["extreme_rating"] = 1.15
    if entry.user_id in top_authors:
        score *= 1.10
        components["top_author"] = 1.10

    logged_at_aware = _coerce_aware(entry.logged_at)
    age_hours = (now - logged_at_aware).total_seconds() / 3600.0
    if age_hours < 0:
        # Defence: clock-skew or future-dated import (Last.fm logs from a
        # device whose clock is ahead). Treat as "just now" — no decay.
        age_hours = 0.0
    decay = math.pow(0.5, age_hours / 72.0)
    score *= decay
    components["decay"] = decay

    return score, components


# ---------------------------------------------------------------------------
# Sidecar builders
# ---------------------------------------------------------------------------


def _serialize_user_card(user: User, *, critic_seed_ids: set[str] | None = None) -> dict[str, Any]:
    """Return the public user card, including the T152 ``is_critic_seed`` flag.

    ``critic_seed_ids`` is the per-batch set of user-ids that are active
    critic seeds, computed once by the caller via
    :func:`auxd_api.modules.seeding.service.critic_seed_user_ids`.
    """
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_critic_seed": (user.id in critic_seed_ids if critic_seed_ids is not None else False),
    }


def _serialize_album_card(album: Album) -> dict[str, Any]:
    return {
        "id": album.id,
        "mbid": album.mbid,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
    }


def _serialize_review_snippet(review: Review, *, snippet_len: int = 280) -> dict[str, Any]:
    """Return a short review payload — body is truncated for the feed card."""
    body = review.body or ""
    truncated = body[:snippet_len]
    return {
        "id": review.id,
        "user_id": review.user_id,
        "diary_entry_id": review.diary_entry_id,
        "album_id": review.album_id,
        "body": truncated,
        "truncated": len(body) > snippet_len,
        "likes_count": review.reactions.likes_count,
        "created_at": review.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def build_home_feed(
    *,
    viewer_id: str,
    cursor: str | None = None,
    limit: int = DEFAULT_HOME_FEED_LIMIT,
    mode: str = FeedMode.FOR_YOU,
) -> HomeFeedResult:
    """Build the home feed for ``viewer_id`` with optional ``mode`` weighting.

    Fan-out-on-read: read viewer's accepted Follow rows, then load the
    diary entries from those followees. Visibility is filtered via the
    standard relation matrix. The result is sorted per ``mode`` and
    paginated via the composite cursor.

    Critic-seed padding: if the visible follow-graph yields fewer than
    :data:`MIN_FEED_BEFORE_PADDING` entries, the service tops up with
    recent critic-seed activity so the empty-state is never the first
    impression.
    """
    safe_mode = FeedMode.parse(mode)
    limit = max(1, min(limit, MAX_HOME_FEED_LIMIT))
    decoded_cursor = decode_home_feed_cursor(cursor)

    follows = await Follow.find(
        {"follower_id": viewer_id, "state": FollowState.ACCEPTED.value}
    ).to_list()
    followee_ids = {row.followee_id for row in follows}

    # Build the diary query. Even with an empty follow set we still
    # query critic-seed padding below.
    diary_query: dict[str, Any] = {
        "user_id": {"$in": list(followee_ids)},
        "deleted_at": None,
    }
    # Visibility filter at the DB layer: skip rows the viewer cannot
    # possibly see. The full matrix still runs in Python (private +
    # follower checks need relation context); pre-filtering ``private``
    # rows is just a cheap shortcut.
    diary_query["visibility"] = {"$ne": Visibility.PRIVATE.value}

    # Cursor predicate — composite ``(logged_at, _id)`` paging.
    if decoded_cursor is not None:
        cursor_logged_at, cursor_id, _cursor_score = decoded_cursor
        cursor_logged_at = _coerce_aware(cursor_logged_at)
        diary_query["$or"] = [
            {"logged_at": {"$lt": cursor_logged_at}},
            {"logged_at": cursor_logged_at, "_id": {"$lt": cursor_id}},
        ]

    # Overfetch a buffer so post-visibility-filter we can still honour
    # the requested limit.
    fetch_limit = limit * 3 + 10
    raw_entries: list[DiaryEntry] = []
    if followee_ids:
        raw_entries = (
            await DiaryEntry.find(diary_query)
            .sort("-logged_at", "-_id")
            .limit(fetch_limit)
            .to_list()
        )

    # Visibility filter via the relation matrix (handles block + private +
    # follower-only edges; the DB filter above already pre-dropped the
    # private-visibility rows).
    viewer = _Viewer(viewer_id)
    owner_ids = {entry.user_id for entry in raw_entries}
    relations = await _resolve_relations(viewer_id, owner_ids)
    visible: list[DiaryEntry] = []
    for entry in raw_entries:
        content: OwnedContent = _DiaryContent(entry)
        relation = relations.get(entry.user_id, ViewerRelation.NOT_FOLLOWER)
        if can_read_with_relation(viewer, content, relation):
            visible.append(entry)

    # Critic-seed padding — if the visible set is thin, pull recent
    # CriticSeed-author entries that the viewer isn't blocking and that
    # are public.
    padding_entry_ids: set[str] = set()
    if len(visible) < MIN_FEED_BEFORE_PADDING:
        padding_seed_authors = await _critic_seed_author_ids(
            viewer_id=viewer_id, exclude_user_ids=followee_ids | {viewer_id}
        )
        if padding_seed_authors:
            pad_query: dict[str, Any] = {
                "user_id": {"$in": list(padding_seed_authors)},
                "deleted_at": None,
                "visibility": Visibility.PUBLIC.value,
            }
            padded_rows = (
                await DiaryEntry.find(pad_query)
                .sort("-logged_at", "-_id")
                .limit(fetch_limit)
                .to_list()
            )
            for entry in padded_rows:
                # Mark for tagging in score_components below.
                padding_entry_ids.add(entry.id)
                visible.append(entry)

    if not visible:
        return HomeFeedResult(
            entries=[],
            next_cursor=None,
            users={},
            albums={},
            reviews={},
        )

    # Apply the mode-specific scoring + sort.
    now = datetime.now(UTC)
    top_authors: set[str] = set()
    if safe_mode == FeedMode.FOR_YOU:
        top_authors = await _load_top_authors(viewer_id)

    feed_entries: list[FeedEntry] = []
    for entry in visible:
        if safe_mode == FeedMode.FOR_YOU:
            score, components = _score_entry(entry, now=now, top_authors=top_authors)
        else:
            score, components = None, {}
        if entry.id in padding_entry_ids:
            components = dict(components)
            components["source"] = "critic_seed_padding"
        feed_entries.append(
            FeedEntry(
                kind="diary_entry",
                id=entry.id,
                user_id=entry.user_id,
                album_id=entry.album_id,
                logged_at=_coerce_aware(entry.logged_at),
                rating=entry.rating,
                auxed=entry.auxed,
                review_id=entry.review_id,
                score=score,
                score_components=components,
            )
        )

    if safe_mode == FeedMode.FOR_YOU:
        feed_entries.sort(
            key=lambda fe: (
                -(fe.score if fe.score is not None else 0.0),
                -fe.logged_at.timestamp(),
                fe.id,
            )
        )
    else:
        feed_entries.sort(key=lambda fe: (-fe.logged_at.timestamp(), fe.id))

    # Trim to limit + compute next_cursor.
    page = feed_entries[:limit]
    next_cursor: str | None = None
    if len(feed_entries) > limit and page:
        last = page[-1]
        next_cursor = encode_home_feed_cursor(
            logged_at=last.logged_at,
            entry_id=last.id,
            score=last.score if safe_mode == FeedMode.FOR_YOU else None,
        )

    # Build the three sidecars in one batch per collection.
    page_user_ids = {fe.user_id for fe in page}
    page_album_ids = {fe.album_id for fe in page}
    page_review_ids = {fe.review_id for fe in page if fe.review_id is not None}

    users_payload: dict[str, dict[str, Any]] = {}
    if page_user_ids:
        user_rows = await User.find({"_id": {"$in": list(page_user_ids)}}).to_list()
        critic_seed_ids = await critic_seed_user_ids([row.id for row in user_rows])
        users_payload = {
            row.id: _serialize_user_card(row, critic_seed_ids=critic_seed_ids) for row in user_rows
        }

    albums_payload: dict[str, dict[str, Any]] = {}
    if page_album_ids:
        album_rows = await Album.find({"_id": {"$in": list(page_album_ids)}}).to_list()
        albums_payload = {row.id: _serialize_album_card(row) for row in album_rows}

    reviews_payload: dict[str, dict[str, Any]] = {}
    if page_review_ids:
        review_rows = await Review.find({"_id": {"$in": list(page_review_ids)}}).to_list()
        reviews_payload = {
            row.id: _serialize_review_snippet(row) for row in review_rows if row.deleted_at is None
        }

    return HomeFeedResult(
        entries=page,
        next_cursor=next_cursor,
        users=users_payload,
        albums=albums_payload,
        reviews=reviews_payload,
    )


async def _critic_seed_author_ids(
    *,
    viewer_id: str,
    exclude_user_ids: set[str],
) -> set[str]:
    """Return active CriticSeed user_ids, minus those the viewer should not see.

    Excludes the viewer themselves and anyone the viewer already
    follows (those rows already arrived via the main fan-out and we
    don't want duplicates in the feed). Also excludes blocked users in
    either direction so the visibility matrix stays consistent.
    """
    seeds = await CriticSeed.find({"active": True}).to_list()
    candidate_ids = {seed.user_id for seed in seeds if seed.user_id not in exclude_user_ids}
    if not candidate_ids:
        return set()
    blocks = await Block.find(
        {
            "$or": [
                {"blocker_id": viewer_id, "blockee_id": {"$in": list(candidate_ids)}},
                {"blocker_id": {"$in": list(candidate_ids)}, "blockee_id": viewer_id},
            ]
        }
    ).to_list()
    blocked_ids: set[str] = set()
    for block in blocks:
        if block.blocker_id == viewer_id:
            blocked_ids.add(block.blockee_id)
        else:
            blocked_ids.add(block.blocker_id)
    return candidate_ids - blocked_ids
