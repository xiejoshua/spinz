"""Beanie documents for the reviews module.

Reviews are 1:1-optional attached to :class:`auxd_api.modules.diary.models.DiaryEntry`.
A like on a review is a *social* engagement (R3 decision #9 — "Aux/Like
split") and is materialised as a separate :class:`ReviewLike` row per
``(review_id, user_id)`` so the toggle is idempotent and counts are derivable.

Edits are versioned via :class:`ReviewEditHistory` (per FR-030 + sync-fix
L3-003) with a 90-day TTL on ``edited_at`` — the audit retention window.
Edit history is *not* exposed publicly; readers only see the latest version.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class ReactionsSubDoc(BaseModel):
    """Nested reactions counter on a :class:`Review`.

    Rename history:
        ``heart_count`` (v1.0) → ``award_count`` (R1 — Heart→Award rename)
        → ``aux_count`` (R1+brand rename) → ``likes_count`` (R3 — Aux/Like
        semantic split).
    """

    likes_count: int = 0
    recent_likers: list[str] = Field(default_factory=list)  # last ~10 user_ids for UI


class Review(Document):
    """A written review attached to a :class:`DiaryEntry`. 1:1 optional."""

    _schema_version: int = 1

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str
    diary_entry_id: str  # FK to DiaryEntry
    album_id: str  # denormalized for album-detail-page queries
    body: str  # markdown-safe; no length cap (per S-C1 AC)
    reactions: ReactionsSubDoc = Field(default_factory=ReactionsSubDoc)
    visibility: str = "public"  # currently mirrors DiaryEntry's visibility
    edited_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "reviews"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            # R3 Most Liked sort (FR-032).
            IndexModel([("album_id", ASCENDING), ("reactions.likes_count", DESCENDING)]),
            # 1:1 enforcement vs DiaryEntry.
            IndexModel([("diary_entry_id", ASCENDING)], unique=True),
        ]


class ReviewLike(Document):
    """Idempotent per-user-per-review like record. R3 addition (S-C4 + FR-031)."""

    _schema_version: int = 1

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    review_id: str
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "review_likes"
        indexes = [
            # Idempotent unique compound — one like per (review, user).
            IndexModel([("review_id", ASCENDING), ("user_id", ASCENDING)], unique=True),
            # User's history of liked reviews.
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
        ]


class ReviewEditHistory(Document):
    """Per-edit audit log for review revisions.

    FR-030 + sync-fix L3-003: every call to ``reviews.edit_review`` writes a
    row here with the pre-edit body. Edit history is NOT exposed publicly —
    readers see only the latest version (S-C3 AC). The 90-day TTL on
    ``edited_at`` is the audit retention window.
    """

    _schema_version: int = 1

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    review_id: str
    version: int  # 1-indexed; increments per edit
    body_at_time: str  # pre-edit snapshot
    edited_at: datetime  # used by TTL index — when this version was superseded
    edited_by: str  # user_id of the editor (always the review owner today; future-proof)

    class Settings:
        name = "review_edit_history"
        indexes = [
            IndexModel([("review_id", ASCENDING), ("version", DESCENDING)]),
            # TTL: drop edit history older than 90 days from edited_at.
            IndexModel(
                [("edited_at", ASCENDING)],
                expireAfterSeconds=int(timedelta(days=90).total_seconds()),
                name="ttl_review_edit_history_90d",
            ),
        ]
