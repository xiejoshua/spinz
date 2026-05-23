"""Backlog service layer — pure business logic for the "Up Next" queue (T095).

The Backlog is the §9 sister-surface to the diary wedge: a user-curated
queue of albums they intend to listen to. Where the diary is *historical*
(what I heard), the backlog is *aspirational* (what I plan to hear). The
two collections share several invariants — owner-only mutations,
visibility scoping, soft-friendly cascades — but the queue has its own
shape: user-defined ordering with contiguous 1-indexed positions, and
auto-removal on log (S-D3 alt-path) so logging an album removes it from
the queue unless the user opts to keep it.

Why a separate service?
=======================
* The mutation paths (add, remove, reorder) all touch two collections
  (``Backlog`` + ``BacklogItem``) and need to keep positions contiguous
  across delete + reorder. Pulling that bookkeeping into pure async
  functions makes it testable in isolation and lets the route layer
  focus on HTTP shape + auth + rate-limit.
* The auto-remove-on-log behavior (T096) lives inside the diary service
  but reads through this module's :func:`auto_remove_on_log` helper so
  the logic stays in one place.

Container singleton contract
============================
Every user has at most one :class:`Backlog` row (enforced by the unique
``user_id`` index — see ``modules/backlog/models.py``). :func:`get_or_create_backlog`
is the canonical accessor: it looks for an existing row, inserts a fresh
one if absent, and re-fetches on :class:`DuplicateKeyError` so a race
between two parallel "first add" requests still resolves to the single
existing container.

Position invariant
==================
After every mutation that affects the queue (add, remove, reorder),
positions are guaranteed to be a contiguous 1-indexed sequence
(``1, 2, 3, ...``). The invariant is held by the service — callers never
manipulate positions directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from auxd_api.lib.visibility import Visibility
from auxd_api.modules.albums.models import Album
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.users.models import User

__all__ = [
    "BacklogAlreadyHasAlbumError",
    "BacklogError",
    "BacklogItemNotFoundError",
    "BacklogItemNotOwnedError",
    "BacklogReorderMismatchError",
    "ListBacklogResult",
    "UnknownAlbumError",
    "add_backlog_item",
    "auto_remove_on_log",
    "get_or_create_backlog",
    "list_backlog_items",
    "lookup_backlog_membership",
    "remove_backlog_item",
    "reorder_backlog_items",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BacklogError(Exception):
    """Base class for backlog-service errors. ``code`` is the wire identifier."""

    code: str = "backlog_error"


class UnknownAlbumError(BacklogError):
    """The album the caller referenced does not exist in the local catalog."""

    code = "album_not_found"


class BacklogItemNotFoundError(BacklogError):
    """The backlog item id was not found (or doesn't belong to the caller)."""

    code = "item_not_found"


class BacklogItemNotOwnedError(BacklogError):
    """The caller is not the owner of the referenced backlog item."""

    code = "forbidden"


class BacklogAlreadyHasAlbumError(BacklogError):
    """The album is already in the caller's backlog (one row per album)."""

    code = "already_in_backlog"


class BacklogReorderMismatchError(BacklogError):
    """The reorder body does not match the caller's current backlog exactly."""

    code = "reorder_mismatch"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Return ``datetime.now(UTC)`` — wrapped for monkeypatch-friendliness."""
    return datetime.now(UTC)


async def get_or_create_backlog(*, user_id: str) -> Backlog:
    """Return the user's :class:`Backlog`, creating it on first use.

    The unique index on ``user_id`` enforces the singleton invariant at
    the database level. If two callers race "first add", the loser
    catches :class:`DuplicateKeyError` and re-fetches the row that the
    winner committed.
    """
    existing = await Backlog.find_one({"user_id": user_id})
    if existing is not None:
        return existing
    backlog = Backlog(user_id=user_id, created_at=_now(), updated_at=_now())
    try:
        await backlog.insert()
    except DuplicateKeyError:
        refreshed = await Backlog.find_one({"user_id": user_id})
        if refreshed is None:
            # Vanishingly improbable: the duplicate fired and the row
            # subsequently vanished. Re-raise so the caller sees the
            # failure rather than a phantom backlog.
            raise
        return refreshed
    return backlog


async def _max_position(backlog_id: str) -> int:
    """Return the largest ``position`` in ``backlog_id`` or 0 if empty."""
    rows = await BacklogItem.find({"backlog_id": backlog_id}).sort("-position").limit(1).to_list()
    return rows[0].position if rows else 0


async def _compact_positions(backlog_id: str) -> None:
    """Renumber positions to a contiguous 1-indexed sequence.

    Called after delete / auto-remove. Reads every item in current
    order, walks the list, and saves each row whose new position
    differs from its old one (no-op writes are skipped to keep churn
    low on a no-gap reorder).
    """
    items = await BacklogItem.find({"backlog_id": backlog_id}).sort("+position").to_list()
    now = _now()
    for index, item in enumerate(items, start=1):
        if item.position != index:
            item.position = index
            item.added_at = item.added_at  # untouched; keep field warm
            await item.save()
        # The model has no ``updated_at``; the parent Backlog stamp covers
        # "the queue changed" for any caller that tracks freshness on the
        # container.
    if items:
        # Touch the parent so cache-busters that watch container freshness
        # invalidate. Tolerant if the parent has gone missing (defensive).
        parent = await Backlog.find_one({"_id": items[0].backlog_id})
        if parent is not None:
            parent.updated_at = now
            await parent.save()


# ---------------------------------------------------------------------------
# add_backlog_item
# ---------------------------------------------------------------------------


async def add_backlog_item(
    *,
    user_id: str,
    album_id: str,
    notes: str | None,
    per_item_visibility: Visibility | None,
) -> BacklogItem:
    """Add ``album_id`` to the user's backlog at the tail (max(position) + 1).

    Behavior:

    * Auto-creates the user's :class:`Backlog` on first add.
    * Validates the album exists; otherwise :class:`UnknownAlbumError`.
    * Catches :class:`DuplicateKeyError` from the unique
      ``(backlog_id, album_id)`` index and maps to
      :class:`BacklogAlreadyHasAlbumError` so the route can emit 409.
    * Returns the freshly inserted :class:`BacklogItem` with its
      assigned position.
    """
    album = await Album.get(album_id)
    if album is None:
        raise UnknownAlbumError("album not found")

    backlog = await get_or_create_backlog(user_id=user_id)
    next_position = await _max_position(backlog.id) + 1
    item = BacklogItem(
        backlog_id=backlog.id,
        album_id=album_id,
        position=next_position,
        per_item_visibility=per_item_visibility,
        notes=notes,
        added_at=_now(),
    )
    try:
        await item.insert()
    except DuplicateKeyError as exc:
        raise BacklogAlreadyHasAlbumError("album already in backlog") from exc

    backlog.updated_at = _now()
    await backlog.save()
    return item


# ---------------------------------------------------------------------------
# remove_backlog_item
# ---------------------------------------------------------------------------


async def remove_backlog_item(*, item_id: str, user_id: str) -> None:
    """Hard-delete a backlog item; reorder remaining items contiguously.

    Owner-only. Raises :class:`BacklogItemNotFoundError` on unknown id
    and :class:`BacklogItemNotOwnedError` on cross-user access.
    """
    item = await BacklogItem.get(item_id)
    if item is None:
        raise BacklogItemNotFoundError("item not found")

    backlog = await Backlog.find_one({"_id": item.backlog_id})
    if backlog is None or backlog.user_id != user_id:
        raise BacklogItemNotOwnedError("not owner")

    await item.delete()
    await _compact_positions(item.backlog_id)


# ---------------------------------------------------------------------------
# reorder_backlog_items
# ---------------------------------------------------------------------------


async def reorder_backlog_items(
    *,
    user_id: str,
    item_ids: list[str],
) -> list[BacklogItem]:
    """Replace the queue's ordering with ``item_ids`` (full ordering required).

    Each ``item_ids[i]``'s ``position`` becomes ``i + 1``. The body must
    match the user's current backlog **exactly** — no missing items, no
    extras, no duplicates. Mismatches raise
    :class:`BacklogReorderMismatchError`; unknown ids raise
    :class:`BacklogItemNotFoundError`.

    Returns the reordered items sorted by ascending position.
    """
    backlog = await get_or_create_backlog(user_id=user_id)
    current = await BacklogItem.find({"backlog_id": backlog.id}).to_list()
    current_by_id = {row.id: row for row in current}

    # Duplicate-id guard. ``len(set) != len(list)`` is the cheapest check.
    if len(set(item_ids)) != len(item_ids):
        raise BacklogReorderMismatchError("duplicate item ids in reorder body")

    # Unknown ids surface as 404; the route layer prefers the more
    # specific signal over the generic "mismatch".
    for item_id in item_ids:
        if item_id not in current_by_id:
            raise BacklogItemNotFoundError("item not found")

    # Exact-match check — we already know every id in ``item_ids`` is
    # present; what's left is "no extras in the DB".
    if len(item_ids) != len(current_by_id):
        raise BacklogReorderMismatchError("reorder body misses backlog items")

    now = _now()
    updated: list[BacklogItem] = []
    for index, item_id in enumerate(item_ids, start=1):
        row = current_by_id[item_id]
        if row.position != index:
            row.position = index
            await row.save()
        updated.append(row)

    backlog.updated_at = now
    await backlog.save()
    return updated


# ---------------------------------------------------------------------------
# list_backlog_items
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListBacklogResult:
    """Return shape for :func:`list_backlog_items`.

    ``next_cursor`` is None when there are no more pages. ``albums`` is
    the dedup'd ``{id: Album}`` map the route layer serializes into the
    sidecar.
    """

    items: list[BacklogItem]
    next_cursor: str | None
    albums: dict[str, Album]


async def list_backlog_items(
    *,
    user_id: str,
    cursor_position: int | None,
    cursor_item_id: str | None,
    limit: int,
) -> ListBacklogResult:
    """Paginated list of the user's backlog items, sorted by position ASC.

    The cursor is a ``(position, item_id)`` tuple so two items with the
    same position (vanishingly unlikely under the contiguous invariant
    but defensive) still page deterministically.
    """
    backlog = await get_or_create_backlog(user_id=user_id)

    query: dict[str, object] = {"backlog_id": backlog.id}
    if cursor_position is not None and cursor_item_id is not None:
        # Rows whose ``(position, item_id)`` tuple strictly follows the
        # cursor in ASC order — expanded to an ``$or`` because Mongo
        # cannot compare tuples natively.
        query["$or"] = [
            {"position": {"$gt": cursor_position}},
            {"position": cursor_position, "_id": {"$gt": cursor_item_id}},
        ]

    rows = await BacklogItem.find(query).sort("+position", "+_id").limit(limit).to_list()

    next_cursor_value: str | None = None  # the route layer encodes the token
    has_next = len(rows) == limit

    album_ids = {row.album_id for row in rows}
    albums: dict[str, Album] = {}
    if album_ids:
        album_rows = await Album.find({"_id": {"$in": list(album_ids)}}).to_list()
        albums = {album.id: album for album in album_rows}

    # The route layer encodes the cursor token; here we just decide
    # whether one is needed and surface the last row's keys for that.
    if has_next:
        last = rows[-1]
        next_cursor_value = f"{last.position}|{last.id}"

    return ListBacklogResult(items=rows, next_cursor=next_cursor_value, albums=albums)


# ---------------------------------------------------------------------------
# lookup_backlog_membership
# ---------------------------------------------------------------------------


async def lookup_backlog_membership(
    *,
    user_id: str,
    album_id: str,
) -> BacklogItem | None:
    """Return the :class:`BacklogItem` for ``(user, album)`` or None.

    Used by the album-detail page's "+ Up Next" button to decide whether
    to render the add or remove affordance on mount.
    """
    backlog = await Backlog.find_one({"user_id": user_id})
    if backlog is None:
        return None
    return await BacklogItem.find_one({"backlog_id": backlog.id, "album_id": album_id})


# ---------------------------------------------------------------------------
# auto_remove_on_log (T096)
# ---------------------------------------------------------------------------


async def auto_remove_on_log(*, user_id: str, album_id: str) -> bool:
    """Remove the album from the user's backlog after a fresh log (S-D3).

    Behavior:

    * No-op (returns False) when the user has no Backlog yet.
    * No-op (returns False) when the album is not in the backlog.
    * No-op (returns False) when ``User.keep_backlog_after_log`` is True
      — the user opted out of auto-removal.
    * Otherwise deletes the matching :class:`BacklogItem` and compacts
      positions; returns True so the caller (the diary service) can
      emit the T100 conversion event.

    Robustness: every branch swallows the missing-record case so a fresh
    log against an album that was never queued is a clean no-op.
    """
    user = await User.get(user_id)
    if user is None:
        return False
    if user.keep_backlog_after_log:
        return False

    backlog = await Backlog.find_one({"user_id": user_id})
    if backlog is None:
        return False

    item = await BacklogItem.find_one({"backlog_id": backlog.id, "album_id": album_id})
    if item is None:
        return False

    await item.delete()
    await _compact_positions(backlog.id)
    return True
