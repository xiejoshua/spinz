"""Beanie Documents for the Backlog module.

Per data-model.md and plan §3.1:
  * ``Backlog`` — singleton per User (the "Up Next" container).
  * ``BacklogItem`` — one album in the user's backlog, with user-defined ordering.

The ``Backlog`` row owns container-level settings (e.g. ``keep_after_logging``).
The actual queue of albums lives in ``BacklogItem`` documents linked via
``backlog_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid
from auxd_api.lib.visibility import Visibility


class Backlog(Document):
    """Singleton per User — the user's "Up Next" backlog container.

    One ``Backlog`` per user; auto-created on first use. The actual queue
    of albums lives in :class:`BacklogItem` documents linked via
    ``backlog_id``. The unique index on ``user_id`` enforces the singleton
    invariant at the database level.
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str  # owner; unique index enforces 1:1 with User
    keep_after_logging: bool = False  # S-D3 alt-path setting; default = auto-remove on log
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "backlogs"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("user_id", ASCENDING)], unique=True),
        ]


class BacklogItem(Document):
    """A single album in a user's backlog ('Up Next' queue).

    ``position`` is 1-indexed and user-defined; defaults to insertion order
    at the service layer. ``per_item_visibility`` is the per-album override
    described in plan §3.1: ``None`` means "inherit from the parent Backlog's
    default visibility"; an explicit :class:`Visibility` overrides it.

    Indexes:

    * ``(backlog_id, album_id)`` **unique** — enforces the "one row per album
      in any backlog" invariant; also serves backlog→items reads via the
      leading key.
    * ``(backlog_id, position)`` — list-in-order reads for the backlog UI.
    * ``(album_id, backlog_id)`` — "is this album in any backlog?" reverse
      lookups (e.g. "remove from all backlogs on hard-delete").
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    backlog_id: str  # FK → Backlog.id
    album_id: str  # FK → Album.id
    position: int  # 1-indexed user-defined order; default == added order
    per_item_visibility: Visibility | None = None  # None = inherit from Backlog default
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None  # optional per-item private note (future UX surface)

    class Settings:
        name = "backlog_items"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("backlog_id", ASCENDING), ("album_id", ASCENDING)], unique=True),
            IndexModel([("backlog_id", ASCENDING), ("position", ASCENDING)]),
            IndexModel([("album_id", ASCENDING), ("backlog_id", ASCENDING)]),
        ]
