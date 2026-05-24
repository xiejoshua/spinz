"""Diary HTTP routes — log, read, edit, delete, restore (T073, T074, T075).

The diary is THE wedge: ``POST /api/v1/diary/entries`` is the endpoint
Casey uses to log an album in under 8 seconds. The other endpoints round
out the resource so the wedge has an obvious surface for follow-up
edits, the chronological diary feed, and the 30-day undo-delete window.

Endpoints (all under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``POST /diary/entries`` (T073) — create a diary entry with optional
  review, idempotent on a 60-second double-tap window.
* ``GET /users/{handle}/diary`` (T074) — paginated chronological diary
  for a user, visibility-filtered for the viewer.
* ``PATCH /diary/entries/{id}`` (T075) — owner-only patch.
* ``DELETE /diary/entries/{id}`` (T075) — owner-only soft-delete.
* ``POST /diary/entries/{id}/restore`` (T075) — owner-only un-delete
  inside the 30-day grace window.

Rate limiting (T020):

* log endpoint: per-user 30/min — comfortable for normal use, defends
  against double-tap spam beyond the 60-second idempotency window.

Observability (Constitution P5):

* ``log_entry`` emits ``log.commit`` to PostHog with timing + flags so
  the wedge funnel (clicked → committed) lights up in analytics. The
  durations are server-side commit only — front-end captures the user-
  visible latency from input to acknowledgement.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.lib.visibility import OwnedContent, Viewer, ViewerRelation, can_read_with_relation
from auxd_api.lib.visibility import Visibility as LibVisibility
from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.diary.service import (
    DiaryEntryAlreadyDeletedError,
    DiaryEntryNotFoundError,
    DiaryEntryNotOwnedError,
    DiaryError,
    DiaryRestoreExpiredError,
    RatingNotInHalvesError,
    UnknownAlbumError,
    delete_entry,
    edit_entry,
    log_entry,
    restore_entry,
)
from auxd_api.modules.social.models import Block, Follow, FollowState
from auxd_api.modules.users.redirect import resolve_handle

_LOGGER = logging.getLogger("auxd.diary.routes")

router = APIRouter(tags=["diary"])

# Per-user 30 logs/minute is the upper bound for normal use. The
# 60-second idempotency window inside the service swallows true double-
# taps; this limit is the second-line guard against scripted abuse.
_LOG_RATE_LIMIT = rate_limit(
    endpoint="diary.log",
    per_user=RateLimit(limit=30, window_seconds=60),
)

# Edit / delete / restore share a single user-budget pool — most users
# touch their diary a few times per day.
_DIARY_EDIT_RATE_LIMIT = rate_limit(
    endpoint="diary.edit",
    per_user=RateLimit(limit=60, window_seconds=60),
)

# Diary list endpoint — anonymous-callable, so per-IP only. Generous so a
# scroll-heavy user can warm their feed quickly.
_DIARY_READ_RATE_LIMIT = rate_limit(
    endpoint="diary.read",
    per_ip=RateLimit(limit=120, window_seconds=60),
)

# Bound on the diary-list page size. The service supports cursor
# pagination so the absolute ceiling here is mostly about response bytes.
_MAX_DIARY_LIMIT = 100
_DEFAULT_DIARY_LIMIT = 25


def _encode_cursor(*, logged_at: str, entry_id: str) -> str:
    """Encode the ``(logged_at, _id)`` pair as a single URL-safe token.

    Diary entries are sorted by ``logged_at DESC`` with ``_id`` as the
    tiebreaker. KSUIDs are *roughly* chronological, but for Last.fm
    imports (T076 future ticket) ``logged_at`` is historical while
    ``_id`` reflects import time — using ``_id`` alone as the cursor
    would scramble the page boundary. The composite cursor preserves
    the sort key end-to-end so paging is correct under any insert
    pattern.
    """
    payload = json.dumps({"l": logged_at, "i": entry_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    """Inverse of :func:`_encode_cursor`. Returns ``None`` on malformed input.

    Malformed cursors are treated as "no cursor" rather than 400 — this
    keeps URL-tampering clients from getting a useful error signal and
    lets the caller silently restart from the top of the feed.
    """
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    logged_at = payload.get("l")
    entry_id = payload.get("i")
    if not isinstance(logged_at, str) or not isinstance(entry_id, str):
        return None
    return logged_at, entry_id


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class _LogEntryRequest(BaseModel):
    """Wire shape for ``POST /diary/entries``."""

    album_id: str = Field(min_length=1, max_length=80)
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    auxed: bool = False
    review_body: str | None = Field(default=None, min_length=1, max_length=10_000)
    visibility: Visibility = Visibility.PUBLIC


class _EditEntryRequest(BaseModel):
    """Wire shape for ``PATCH /diary/entries/{id}``.

    Every field is optional. The route layer reads ``model_fields_set``
    to distinguish "omit this field" from "set this field to null/empty".
    """

    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    auxed: bool | None = None
    # Empty string is a sentinel meaning "delete the review". Pydantic
    # would otherwise complain about an empty string under ``min_length=1``,
    # so we deliberately don't constrain it here.
    review_body: str | None = Field(default=None, max_length=10_000)
    visibility: Visibility | None = None


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


_DIARY_ERROR_STATUS_MAP: dict[type[DiaryError], int] = {
    UnknownAlbumError: status.HTTP_404_NOT_FOUND,
    RatingNotInHalvesError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DiaryEntryNotFoundError: status.HTTP_404_NOT_FOUND,
    DiaryEntryNotOwnedError: status.HTTP_403_FORBIDDEN,
    DiaryEntryAlreadyDeletedError: status.HTTP_410_GONE,
    DiaryRestoreExpiredError: status.HTTP_410_GONE,
}


def _diary_error_response(exc: DiaryError) -> HTTPException:
    status_code = _DIARY_ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.code)


# ---------------------------------------------------------------------------
# Session helper (mirrors auth/routes.py pattern)
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


def _optional_session(request: Request) -> Session | None:
    session = getattr(request.state, "session", None)
    return session if isinstance(session, Session) else None


# ---------------------------------------------------------------------------
# Visibility adapters — mirrors albums/routes.py pattern
# ---------------------------------------------------------------------------


class _SessionViewer:
    """Minimal :class:`Viewer` adapter wrapping a session user id."""

    __slots__ = ("id",)

    id: str

    def __init__(self, user_id: str) -> None:
        self.id = user_id


class _DiaryContent:
    """Adapter exposing :class:`OwnedContent` for a :class:`DiaryEntry`."""

    __slots__ = ("deleted_at", "owner_id", "visibility")

    def __init__(self, entry: DiaryEntry) -> None:
        self.owner_id = entry.user_id
        self.visibility = LibVisibility(entry.visibility.value)
        self.deleted_at = entry.deleted_at


async def _resolve_relations(
    viewer_id: str | None,
    owner_ids: set[str],
) -> dict[str, ViewerRelation]:
    """Compute the viewer's relation to every owner id in one batch.

    Mirrors the implementation in ``albums/routes.py`` — kept inlined
    rather than shared because the album-detail and diary endpoints have
    different sort/paging requirements that make a shared helper more
    awkward than a thin duplicate.
    """
    relations: dict[str, ViewerRelation] = {}
    if viewer_id is None:
        return {owner: ViewerRelation.ANONYMOUS for owner in owner_ids}

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


def _serialize_entry(entry: DiaryEntry) -> dict[str, Any]:
    """Return the wire shape for a diary entry.

    Mirrors the ``_serialize_diary`` helper in ``albums/routes.py`` but
    adds the four fields the diary-resource endpoints expose that the
    album-detail rollup omits: ``relisten``, ``created_at``, plus an
    explicit ``deleted_at`` for the restore-path response.
    """
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "album_id": entry.album_id,
        "logged_at": entry.logged_at.isoformat(),
        "rating": entry.rating,
        "auxed": entry.auxed,
        "review_id": entry.review_id,
        "visibility": entry.visibility.value,
        "relisten": entry.relisten,
        "edited_at": entry.edited_at.isoformat() if entry.edited_at is not None else None,
        "created_at": entry.created_at.isoformat(),
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at is not None else None,
    }


def _serialize_album_card(album: Album) -> dict[str, Any]:
    """Return the minimal album-card payload bundled in the diary sidecar.

    Diary surfaces (profile diary, future feed) need just enough album
    metadata to render a card with cover + title + artist. The full
    album detail lives behind ``GET /api/v1/albums/{id}``.
    """
    return {
        "id": album.id,
        "mbid": album.mbid,
        "title": album.title,
        "artist_credit": album.artist_credit,
        "release_year": album.release_year,
        "cover_art_url": album.cover_art_url,
    }


# ---------------------------------------------------------------------------
# T073 — POST /diary/entries
# ---------------------------------------------------------------------------


@router.post(
    "/diary/entries",
    dependencies=[Depends(_LOG_RATE_LIMIT)],
)
async def post_diary_entry(
    payload: _LogEntryRequest,
    response: Response,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Log an album to the diary.

    Returns ``201`` on a fresh insert, ``200`` when the idempotency
    window swallows a double-tap (same ``(user_id, album_id)`` inside
    60 seconds). Failure modes:

    * ``404`` — unknown album.
    * ``422`` — rating not in 0.5 increments (Pydantic bounds catch
      out-of-range first).
    """
    started = time.perf_counter()
    try:
        result = await log_entry(
            user_id=session.user_id,
            album_id=payload.album_id,
            rating=payload.rating,
            auxed=payload.auxed,
            review_body=payload.review_body,
            visibility=payload.visibility,
        )
    except DiaryError as exc:
        log_call(
            provider="auxd",
            endpoint="diary.log_rejected",
            latency_ms=(time.perf_counter() - started) * 1000,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id},
        )
        raise _diary_error_response(exc) from exc

    duration_ms = (time.perf_counter() - started) * 1000
    log_call(
        provider="auxd",
        endpoint="diary.log_committed",
        latency_ms=duration_ms,
        status="ok",
        extra={
            "user_id": session.user_id,
            "entry_id": result.entry.id,
            # ``created`` collides with the reserved LogRecord attribute
            # of the same name — use ``was_created`` in the extras bag.
            "was_created": result.created,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="log.commit",
        properties={
            "duration_ms": duration_ms,
            "has_rating": result.entry.rating is not None,
            "has_review": result.entry.review_id is not None,
            "auxed": result.entry.auxed,
            "relisten": result.entry.relisten,
            "source": result.entry.source.value,
            "idempotent_hit": not result.created,
        },
    )
    # T100 — emit the backlog conversion event when the auto-remove
    # actually fired. The service guarantees ``backlog_item_removed``
    # is only True on a fresh insert (not on the idempotent path), so
    # one log = at most one conversion event.
    if result.backlog_item_removed:
        emit_event(
            user_id=session.user_id,
            event="backlog.converted_to_log",
            properties={
                "entry_id": result.entry.id,
                "album_id": result.entry.album_id,
                "source": "manual",
            },
        )
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return _serialize_entry(result.entry)


# ---------------------------------------------------------------------------
# T074 — GET /users/{handle}/diary
# ---------------------------------------------------------------------------


@router.get(
    "/users/{handle}/diary",
    dependencies=[Depends(_DIARY_READ_RATE_LIMIT)],
)
async def get_user_diary(
    handle: str,
    request: Request,
    cursor: str | None = None,
    limit: int = _DEFAULT_DIARY_LIMIT,
    auxed: bool | None = None,
) -> dict[str, Any]:
    """Paginated chronological diary for a user, visibility-filtered.

    Query params:

    * ``cursor`` — KSUID of the last entry from the previous page.
      Entries with ``_id < cursor`` are returned; KSUIDs sort
      chronologically so this is a stable cursor.
    * ``limit`` — page size, default 25, capped at 100.
    * ``auxed`` — when ``true``, restricts to entries with ``auxed=True``
      (the "Aux'd" profile tab).

    The visibility filter delegates to
    :func:`auxd_api.lib.visibility.can_read_with_relation` so the same
    matrix used everywhere else (followers must follow, private = owner
    only, blocks are mutual) is honoured here. The implementation
    intentionally over-fetches a small buffer when applying client-side
    visibility filtering would otherwise short-cut a page.
    """
    if limit < 1:
        limit = _DEFAULT_DIARY_LIMIT
    if limit > _MAX_DIARY_LIMIT:
        limit = _MAX_DIARY_LIMIT

    target, _canonical = await resolve_handle(handle)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    session = _optional_session(request)
    viewer: Viewer | None = None
    viewer_id: str | None = None
    if session is not None:
        viewer_id = session.user_id
        viewer = _SessionViewer(viewer_id)

    # Build the base query. ``deleted_at: None`` keeps soft-deleted
    # rows out of the public feed; the owner gets them via a separate
    # "trash" surface (out of scope here).
    query: dict[str, Any] = {
        "user_id": target.id,
        "deleted_at": None,
    }
    if auxed is True:
        query["auxed"] = True

    # Composite-cursor filter: rows whose ``(logged_at, _id)`` tuple
    # comes strictly after the cursor's tuple in the DESC sort. Expanded
    # to a Mongo-grammar ``$or`` because Mongo can't compare tuples
    # natively.
    if cursor is not None:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            cursor_logged_at, cursor_id = decoded
            try:
                cursor_logged_dt: datetime | None = datetime.fromisoformat(cursor_logged_at)
            except ValueError:
                cursor_logged_dt = None
            if cursor_logged_dt is not None:
                query["$or"] = [
                    {"logged_at": {"$lt": cursor_logged_dt}},
                    {
                        "logged_at": cursor_logged_dt,
                        "_id": {"$lt": cursor_id},
                    },
                ]

    # ``logged_at`` is the primary chronological key; ``_id`` (KSUID) is a
    # stable tiebreaker so two entries with identical ``logged_at`` page
    # deterministically. Beanie's typed query API accepts the string form
    # for compound sorts (``"-field"`` for DESC).
    rows: list[DiaryEntry] = (
        await DiaryEntry.find(query).sort("-logged_at", "-_id").limit(limit).to_list()
    )

    # Visibility filter — for the owner this is a no-op (every row is
    # readable). For other viewers we resolve relations in a single
    # batch and use the matrix.
    #
    # ``owner_is_private`` (REV-002): when the profile owner has
    # ``private_profile=True``, the matrix demotes PUBLIC entries to
    # FOLLOWERS scope so non-followers and anonymous viewers cannot
    # read content authored by a user who flipped their profile
    # private.
    visible_entries: list[DiaryEntry] = []
    if viewer_id is not None and viewer_id == target.id:
        visible_entries = list(rows)
    else:
        owner_ids = {target.id}
        relations = await _resolve_relations(viewer_id, owner_ids)
        for row in rows:
            content = _DiaryContent(row)
            relation = relations.get(
                row.user_id,
                ViewerRelation.ANONYMOUS if viewer_id is None else ViewerRelation.NOT_FOLLOWER,
            )
            if can_read_with_relation(
                viewer,
                content,
                relation,
                owner_is_private=target.private_profile,
            ):
                visible_entries.append(row)

    next_cursor: str | None = None
    if len(rows) == limit and rows:
        # Use the last *queried* row, not the last *visible* row, so the
        # client always advances even when the page was all blocked /
        # private content.
        last = rows[-1]
        next_cursor = _encode_cursor(
            logged_at=last.logged_at.isoformat(),
            entry_id=last.id,
        )

    # Sidecar: a map of {album_id: card-payload} so the client can render
    # entries with title + cover without a per-row roundtrip. Dedup on
    # ``album_id`` so repeated relistens cost one album lookup, not N.
    album_ids = {entry.album_id for entry in visible_entries}
    albums_payload: dict[str, dict[str, Any]] = {}
    if album_ids:
        album_rows = await Album.find({"_id": {"$in": list(album_ids)}}).to_list()
        albums_payload = {album.id: _serialize_album_card(album) for album in album_rows}

    return {
        "entries": [_serialize_entry(entry) for entry in visible_entries],
        "next_cursor": next_cursor,
        "albums": albums_payload,
    }


# ---------------------------------------------------------------------------
# T075 — PATCH / DELETE / restore
# ---------------------------------------------------------------------------


@router.patch(
    "/diary/entries/{entry_id}",
    dependencies=[Depends(_DIARY_EDIT_RATE_LIMIT)],
)
async def patch_diary_entry(
    entry_id: str,
    payload: _EditEntryRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Patch an entry — owner-only, active-only."""
    provided = payload.model_fields_set
    try:
        entry, _review = await edit_entry(
            entry_id=entry_id,
            user_id=session.user_id,
            rating=payload.rating,
            auxed=payload.auxed,
            review_body=payload.review_body,
            visibility=payload.visibility,
            rating_provided="rating" in provided,
            review_body_provided="review_body" in provided,
        )
    except DiaryError as exc:
        log_call(
            provider="auxd",
            endpoint="diary.edit_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id, "entry_id": entry_id},
        )
        raise _diary_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="diary.edit_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "entry_id": entry.id},
    )
    emit_event(
        user_id=session.user_id,
        event="log.edit",
        properties={
            "entry_id": entry.id,
            "has_rating": entry.rating is not None,
            "has_review": entry.review_id is not None,
        },
    )
    return _serialize_entry(entry)


@router.delete(
    "/diary/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_DIARY_EDIT_RATE_LIMIT)],
)
async def delete_diary_entry(
    entry_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Soft-delete an entry — owner-only. Returns 204 on success."""
    try:
        entry = await delete_entry(entry_id=entry_id, user_id=session.user_id)
    except DiaryError as exc:
        log_call(
            provider="auxd",
            endpoint="diary.delete_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id, "entry_id": entry_id},
        )
        raise _diary_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="diary.delete_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "entry_id": entry.id},
    )
    emit_event(
        user_id=session.user_id,
        event="log.delete",
        properties={"entry_id": entry.id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/diary/entries/{entry_id}/restore",
    dependencies=[Depends(_DIARY_EDIT_RATE_LIMIT)],
)
async def restore_diary_entry(
    entry_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Restore a soft-deleted entry within the 30-day grace window."""
    try:
        entry = await restore_entry(entry_id=entry_id, user_id=session.user_id)
    except DiaryError as exc:
        log_call(
            provider="auxd",
            endpoint="diary.restore_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id, "entry_id": entry_id},
        )
        raise _diary_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="diary.restore_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "entry_id": entry.id},
    )
    emit_event(
        user_id=session.user_id,
        event="log.restore",
        properties={"entry_id": entry.id},
    )
    return _serialize_entry(entry)


# Static reference so OwnedContent + Visibility imports never appear unused.
_ = OwnedContent

__all__ = ["router"]
