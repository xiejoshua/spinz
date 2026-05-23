"""Backlog HTTP routes — Up Next CRUD surface (T095).

Endpoints (all under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

* ``POST   /users/me/backlog/items`` — add an album to the queue.
* ``DELETE /users/me/backlog/items/{item_id}`` — remove an item.
* ``PATCH  /users/me/backlog/items/reorder`` — full-ordering reorder.
* ``GET    /users/me/backlog/items`` — paginated queue read with album
  sidecar.
* ``GET    /users/me/backlog/contains`` — boolean membership check used
  by the album-detail "+ Up Next" affordance.

Every route requires an authenticated session; ``user_id`` is always the
session's user id (never derived from a path parameter). Auto-creates
the singleton :class:`Backlog` row on first add — the user never needs
to "open the backlog" explicitly.

Rate limiting (T020):

* All backlog mutations + reads share a per-user 60/min budget — mirrors
  diary edit limits. Backlog operations are bursty (add three albums in
  a row then drag-reorder) so 60/min is comfortable while still
  defending against scripted abuse.

Observability (Constitution P5):

* Every mutation emits a structured ``log_call`` line with the
  ``backlog.*`` endpoint family and an analytics event capturing the
  user-facing intent (add, remove, reorder).

Sidecar shape
=============
The list endpoint returns ``{items, next_cursor, albums}`` mirroring the
diary endpoint's sidecar contract (T080). The :class:`Album` card shape
is identical — title, artist, year, cover — so a frontend that already
renders the diary feed can reuse its album-card component for the
backlog feed without a second adapter.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.lib.visibility import Visibility
from auxd_api.modules.albums.models import Album
from auxd_api.modules.backlog.models import BacklogItem
from auxd_api.modules.backlog.service import (
    BacklogAlreadyHasAlbumError,
    BacklogError,
    BacklogItemNotFoundError,
    BacklogItemNotOwnedError,
    BacklogReorderMismatchError,
    UnknownAlbumError,
    add_backlog_item,
    list_backlog_items,
    lookup_backlog_membership,
    remove_backlog_item,
    reorder_backlog_items,
)

_LOGGER = logging.getLogger("auxd.backlog.routes")

router = APIRouter(tags=["backlog"])


# Backlog mutations + reads share a per-user budget. Backlog ops are
# similar-frequency to diary edits — 60/min is comfortable for normal
# use and defends against scripted abuse.
_BACKLOG_RATE_LIMIT = rate_limit(
    endpoint="backlog.write",
    per_user=RateLimit(limit=60, window_seconds=60),
)


# Page-size guard for the list endpoint. The service's cursor pagination
# already handles larger backlogs, but a sensible upper bound keeps the
# response body bounded under pathological queries.
_MAX_BACKLOG_LIMIT = 100
_DEFAULT_BACKLOG_LIMIT = 25


# ---------------------------------------------------------------------------
# Cursor encoding (mirrors diary _encode_cursor / _decode_cursor shape)
# ---------------------------------------------------------------------------


def _encode_cursor(*, position: int, item_id: str) -> str:
    """Encode the ``(position, item_id)`` tuple as a URL-safe token.

    Backlog rows sort by ``position ASC`` with ``_id`` as the tiebreaker.
    The composite cursor preserves the sort key end-to-end so inserts
    or reorders mid-paging don't scramble the page boundary.
    """
    payload = json.dumps({"p": position, "i": item_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[int, str] | None:
    """Inverse of :func:`_encode_cursor`. Returns ``None`` on malformed input.

    Mirrors the diary endpoint's "silently treat malformed cursor as no
    cursor" semantics (URL tampering yields no useful signal to the
    client; the caller restarts from the head of the queue).
    """
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    position = payload.get("p")
    item_id = payload.get("i")
    if not isinstance(position, int) or not isinstance(item_id, str):
        return None
    return position, item_id


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class _AddItemRequest(BaseModel):
    """Wire shape for ``POST /users/me/backlog/items``."""

    album_id: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    per_item_visibility: Visibility | None = None


class _ReorderRequest(BaseModel):
    """Wire shape for ``PATCH /users/me/backlog/items/reorder``.

    The body carries the FULL new ordering — every existing item id must
    appear exactly once. The service validates the exact-match invariant
    and raises :class:`BacklogReorderMismatchError` on any deviation.
    """

    item_ids: list[str] = Field(min_length=0, max_length=10_000)


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


_BACKLOG_ERROR_STATUS_MAP: dict[type[BacklogError], int] = {
    UnknownAlbumError: status.HTTP_404_NOT_FOUND,
    BacklogItemNotFoundError: status.HTTP_404_NOT_FOUND,
    BacklogItemNotOwnedError: status.HTTP_403_FORBIDDEN,
    BacklogAlreadyHasAlbumError: status.HTTP_409_CONFLICT,
    BacklogReorderMismatchError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _backlog_error_response(exc: BacklogError) -> HTTPException:
    status_code = _BACKLOG_ERROR_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.code)


# ---------------------------------------------------------------------------
# Session helper (mirrors diary/routes.py pattern)
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_item(item: BacklogItem) -> dict[str, Any]:
    """Return the wire shape for a backlog item.

    The shape intentionally mirrors the diary entry shape on overlapping
    fields (``id``, ``album_id``, ``visibility``-style, timestamps) so a
    frontend that renders both can share a base row component.
    """
    return {
        "id": item.id,
        "backlog_id": item.backlog_id,
        "album_id": item.album_id,
        "position": item.position,
        "per_item_visibility": (
            item.per_item_visibility.value if item.per_item_visibility is not None else None
        ),
        "notes": item.notes,
        "added_at": item.added_at.isoformat(),
    }


def _serialize_album_card(album: Album) -> dict[str, Any]:
    """Return the minimal album-card payload bundled in the backlog sidecar.

    Identical shape to ``diary/routes.py:_serialize_album_card`` — kept
    duplicated rather than imported because the helper is tiny (six
    fields) and cross-module imports between sibling routers would
    introduce circular-import risk during Beanie init.
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
# POST /users/me/backlog/items
# ---------------------------------------------------------------------------


@router.post(
    "/users/me/backlog/items",
    dependencies=[Depends(_BACKLOG_RATE_LIMIT)],
)
async def post_backlog_item(
    payload: _AddItemRequest,
    response: Response,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Add ``payload.album_id`` to the user's backlog.

    Returns ``201`` on success. Failure modes:

    * ``404`` — unknown album.
    * ``409`` — album already in the user's backlog.
    """
    try:
        item = await add_backlog_item(
            user_id=session.user_id,
            album_id=payload.album_id,
            notes=payload.notes,
            per_item_visibility=payload.per_item_visibility,
        )
    except BacklogError as exc:
        log_call(
            provider="auxd",
            endpoint="backlog.add_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id},
        )
        raise _backlog_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="backlog.add_committed",
        latency_ms=0.0,
        status="ok",
        extra={
            "user_id": session.user_id,
            "item_id": item.id,
            "album_id": item.album_id,
            "position": item.position,
        },
    )
    emit_event(
        user_id=session.user_id,
        event="backlog.item_added",
        properties={
            "item_id": item.id,
            "album_id": item.album_id,
            "position": item.position,
            "has_notes": item.notes is not None and bool(item.notes.strip()),
            "per_item_visibility": (
                item.per_item_visibility.value if item.per_item_visibility is not None else None
            ),
        },
    )
    response.status_code = status.HTTP_201_CREATED
    return _serialize_item(item)


# ---------------------------------------------------------------------------
# DELETE /users/me/backlog/items/{item_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/users/me/backlog/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_BACKLOG_RATE_LIMIT)],
)
async def delete_backlog_item(
    item_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Remove an item from the user's backlog. Reorder to keep positions contiguous."""
    try:
        await remove_backlog_item(item_id=item_id, user_id=session.user_id)
    except BacklogError as exc:
        log_call(
            provider="auxd",
            endpoint="backlog.remove_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id, "item_id": item_id},
        )
        raise _backlog_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="backlog.remove_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "item_id": item_id},
    )
    emit_event(
        user_id=session.user_id,
        event="backlog.item_removed",
        properties={"item_id": item_id, "source": "manual"},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PATCH /users/me/backlog/items/reorder
# ---------------------------------------------------------------------------


@router.patch(
    "/users/me/backlog/items/reorder",
    dependencies=[Depends(_BACKLOG_RATE_LIMIT)],
)
async def patch_backlog_reorder(
    payload: _ReorderRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> dict[str, Any]:
    """Replace the queue ordering with the body's full id list.

    Returns the reordered items in their new position order.
    """
    try:
        items = await reorder_backlog_items(
            user_id=session.user_id,
            item_ids=payload.item_ids,
        )
    except BacklogError as exc:
        log_call(
            provider="auxd",
            endpoint="backlog.reorder_rejected",
            latency_ms=0.0,
            status="rejected",
            extra={"reason": exc.code, "user_id": session.user_id},
        )
        raise _backlog_error_response(exc) from exc

    log_call(
        provider="auxd",
        endpoint="backlog.reorder_committed",
        latency_ms=0.0,
        status="ok",
        extra={"user_id": session.user_id, "count": len(items)},
    )
    emit_event(
        user_id=session.user_id,
        event="backlog.reordered",
        properties={"count": len(items)},
    )
    return {"items": [_serialize_item(item) for item in items]}


# ---------------------------------------------------------------------------
# GET /users/me/backlog/items
# ---------------------------------------------------------------------------


@router.get(
    "/users/me/backlog/items",
    dependencies=[Depends(_BACKLOG_RATE_LIMIT)],
)
async def get_backlog_items(
    session: Annotated[Session, Depends(_require_session)],
    cursor: str | None = None,
    limit: int = _DEFAULT_BACKLOG_LIMIT,
) -> dict[str, Any]:
    """Paginated list of the user's backlog items.

    Sort order is ``position ASC`` (the user-defined queue order). The
    cursor is a base64-encoded ``(position, item_id)`` tuple so paging
    stays stable under inserts. Malformed cursors are silently treated
    as "no cursor".
    """
    if limit < 1:
        limit = _DEFAULT_BACKLOG_LIMIT
    if limit > _MAX_BACKLOG_LIMIT:
        limit = _MAX_BACKLOG_LIMIT

    cursor_position: int | None = None
    cursor_item_id: str | None = None
    if cursor is not None:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            cursor_position, cursor_item_id = decoded

    result = await list_backlog_items(
        user_id=session.user_id,
        cursor_position=cursor_position,
        cursor_item_id=cursor_item_id,
        limit=limit,
    )

    next_cursor: str | None = None
    if result.next_cursor is not None and result.items:
        last = result.items[-1]
        next_cursor = _encode_cursor(position=last.position, item_id=last.id)

    return {
        "items": [_serialize_item(item) for item in result.items],
        "next_cursor": next_cursor,
        "albums": {
            album_id: _serialize_album_card(album) for album_id, album in result.albums.items()
        },
    }


# ---------------------------------------------------------------------------
# GET /users/me/backlog/contains
# ---------------------------------------------------------------------------


@router.get(
    "/users/me/backlog/contains",
    dependencies=[Depends(_BACKLOG_RATE_LIMIT)],
)
async def get_backlog_contains(
    session: Annotated[Session, Depends(_require_session)],
    album_id: str,
) -> dict[str, Any]:
    """Return ``{in_backlog: bool, item_id: str|None}`` for ``album_id``.

    Drives the album-detail page's "+ Up Next" toggle. The endpoint is
    intentionally cheap (one indexed lookup) so the album-detail mount
    can call it without a perf concern.
    """
    item = await lookup_backlog_membership(user_id=session.user_id, album_id=album_id)
    return {
        "in_backlog": item is not None,
        "item_id": item.id if item is not None else None,
    }


__all__ = ["router"]
