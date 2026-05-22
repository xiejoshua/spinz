"""Beanie documents for the diary module.

The diary is the wedge interaction (S-B1): a user logs a listen to an album,
optionally with a rating, the "Aux'd" self-curation flag, and an attached
review. Diary entries support soft-deletion with a 30-day grace window before
hard-deletion (see plan §3.1 and data-model.md DM-5).

Aux/Like split (R3 decision #9): the ``auxed`` field on :class:`DiaryEntry`
represents self-curation on a user's own entry (🏅). Likes on reviews live on
:class:`auxd_api.modules.reviews.models.ReviewLike` and are a separate
concept (social engagement, 👍).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class Visibility(StrEnum):
    """Per-entry visibility scope; mirrored onto :class:`Review` for filterability."""

    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class DiaryEntrySource(StrEnum):
    """How a diary entry was created. Used for analytics + behavior toggles.

    CR-001 (2026-05-22): removed Spotify-derived sources
    (``SPOTIFY_IMPORT``, ``SPOTIFY_JUST_FINISHED_PROMPT``,
    ``SPOTIFY_PREFILL``) along with the Spotify integration. Diary
    entries at MVP are either ``MANUAL`` or ``LASTFM_IMPORT`` (Should-Have
    FR-017); just-finished prompts are deferred to v2.
    """

    MANUAL = "manual"
    LASTFM_IMPORT = "lastfm_import"  # Should-Have FR-017


class DiaryEntry(Document):
    """A single album listen log entry. The wedge interaction (S-B1)."""

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str
    album_id: str
    logged_at: datetime
    rating: float | None = Field(default=None, ge=0.5, le=5.0)  # 0.5..5.0 in 0.5 steps
    auxed: bool = False  # Aux (🏅): personal curation on own entry. Distinct from Like.
    review_id: str | None = None  # 1:1 optional FK to Review
    visibility: Visibility = Visibility.PUBLIC
    source: DiaryEntrySource = DiaryEntrySource.MANUAL
    relisten: bool = False  # True if user has logged this album before
    device: str | None = None  # "web" | "ios" | "android" — UA hint
    edited_at: datetime | None = None
    deleted_at: datetime | None = None  # soft delete; 30d grace
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "diary_entries"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("logged_at", DESCENDING)]),
            IndexModel(
                [("user_id", ASCENDING), ("album_id", ASCENDING), ("logged_at", DESCENDING)]
            ),
            IndexModel(
                [("album_id", ASCENDING), ("visibility", ASCENDING), ("rating", DESCENDING)]
            ),
            IndexModel(
                [("visibility", ASCENDING), ("logged_at", DESCENDING)],
                partialFilterExpression={"visibility": "public"},
            ),
            # Sync-fix L4-002 / Run #1: aux'd-filter index for profile Aux'd tab.
            IndexModel(
                [("user_id", ASCENDING), ("auxed", ASCENDING)],
                partialFilterExpression={"auxed": True},
                name="ix_diary_user_auxed",
            ),
            IndexModel(
                [("deleted_at", ASCENDING)],
                sparse=True,
                name="ix_diary_soft_delete_grace",
            ),
        ]
