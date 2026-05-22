"""Beanie Documents for the Seeding module.

Per FR-015, plan §12, and product-spec/seeding-strategy.md:

* :class:`SuggestedFollow` — precomputed follow suggestions, refreshed
  nightly by a background job. Read-heavy: served as the onboarding "who
  to follow" card stack and on the empty-state of the social feed.
* :class:`CriticSeed` — founder-curated tastemaker roster. Each row links
  to a real ``User`` that has been editorially approved as a tastemaker.

The nightly refresh job and ranking service live in separate tasks; this
module only defines the persistence shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class SuggestionSource(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """Where a :class:`SuggestedFollow` came from.

    Used by analytics (to measure which signals convert) and by ranking
    (to diversify the card stack so it isn't 100% critic seeds).
    """

    CRITIC_SEED = "critic_seed"  # from the founder-curated CriticSeed roster
    MUTUAL_TASTE = "mutual_taste"  # taste-graph overlap on logged albums / genres
    INVITE_GRAPH = "invite_graph"  # someone who already invited you / vice versa
    CO_LOG = "co_log"  # logged the same album recently (lightweight signal)


class SuggestedFollow(Document):
    """Precomputed follow suggestion. Refreshed nightly by a background job.

    One row per (user, suggested_user) pair. The nightly job upserts on
    ``(user_id, suggested_user_id)`` and recomputes ``score`` + ``reason``;
    ``dismissed_at`` / ``followed_at`` survive across refreshes so the UI
    can keep hiding dismissed cards.
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str  # FK → User; the user we're suggesting follows TO
    suggested_user_id: str  # FK → User; the candidate to follow
    score: float  # ranking score in [0, 1]; higher = stronger suggestion
    source: SuggestionSource
    reason: str | None = None  # short copy for the card ("writes about indie hip-hop")
    dismissed_at: datetime | None = None  # set when the user taps "Not now"
    followed_at: datetime | None = None  # set if the user actually clicked Follow
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "suggested_follows"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            # Primary read pattern: top-N suggestions for a user by score.
            IndexModel([("user_id", ASCENDING), ("score", DESCENDING)]),
            # Sparse index on ``dismissed_at`` — only non-null values are
            # indexed, keeping the index small (most rows have no dismissal).
            IndexModel([("dismissed_at", ASCENDING)], sparse=True),
        ]


class CriticSeed(Document):
    """Founder-curated tastemaker roster (FR-015, plan §12.1).

    Each ``CriticSeed`` row links to a real ``User`` account (referenced
    via ``user_id``) that has been editorially approved as a tastemaker.
    The ``unique`` index on ``user_id`` prevents accidental double-listing
    of the same critic.
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str  # FK → User; the underlying tastemaker account
    priority: int = 50  # 1..100; higher = ranked higher in the onboarding stack
    active: bool = True  # founder can deactivate without deleting
    genre_signature: list[str] = Field(
        default_factory=list,
    )  # tags for matching to user taste
    public_bio: str | None = None  # short copy shown on the onboarding card
    notes: str | None = None  # internal-only founder notes
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deactivated_at: datetime | None = None  # set when ``active`` flips to False

    class Settings:
        name = "critic_seeds"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            # Default ranking read: highest-priority critics first.
            IndexModel([("priority", DESCENDING)]),
            # Partial index over active rows only — the hot read filter is
            # ``active == True`` and most queries don't care about the
            # deactivated roster.
            IndexModel(
                [("active", ASCENDING)],
                partialFilterExpression={"active": True},
            ),
            # One CriticSeed per underlying User account.
            IndexModel([("user_id", ASCENDING)], unique=True),
        ]
