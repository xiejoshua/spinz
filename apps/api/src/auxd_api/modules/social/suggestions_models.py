"""Suggestion Documents — precomputed who-to-follow rows (T104).

Two collections back the suggested-follow surface:

* :class:`Suggestion` — precomputed by the
  :func:`auxd_api.workers.suggestions_job.compute_suggestions_for_user`
  job every N hours per user. The API surface (``GET /users/me/suggestions``)
  reads from this collection rather than recomputing on demand so the
  hot path is a single indexed query.
* :class:`SuggestionDismissal` — records "Not now" actions from the
  user. A 30-day TTL on ``dismissed_at`` keeps the row out of the
  algorithm's candidate set while it's fresh, then lets it expire so the
  candidate becomes re-eligible after a cooling-off window.

Both collections are NEW relative to the legacy :class:`SuggestedFollow`
in ``seeding/models.py``. ``SuggestedFollow`` was authored for the
onboarding "follow 3 to fill your feed" surface (FR-015) and stores its
own ``dismissed_at`` / ``followed_at`` lifecycle on the row itself; the
T104 worker writes to the dedicated ``Suggestion`` collection so the two
surfaces don't fight over ``score`` rewrites. If a future consolidation
makes sense, the merge happens at the service layer (read both, prefer
the newer row) rather than by mutating the legacy schema.

Indexes match the read patterns documented in plan §10.3:

* ``Suggestion``:
    * ``(user_id, score DESC)`` — the dominant read for the API surface,
      "top-N suggestions for this user by score".
    * ``(user_id, suggested_user_id)`` unique — the worker upserts by this
      compound, also drives the "delete this suggestion on dismiss" path
      from the API.
    * ``computed_at`` TTL 7 days — keeps stale precomputes from
      lingering; the worker rewrites fresh rows on its scheduled cadence,
      and any row older than 7 days is presumed orphaned (the user might
      have churned, the algorithm might have shipped a fix).
* ``SuggestionDismissal``:
    * ``(user_id, suggested_user_id)`` unique compound — the dismiss
      endpoint upserts by this; the worker reads it as an "exclude this
      candidate" filter.
    * ``dismissed_at`` TTL 30 days — auto-clean once the cooling-off
      window passes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime.now`` factory.

    Mirrors the sibling helpers in ``social/models.py`` and
    ``users/models.py`` — BSON stores datetimes in UTC but strips
    ``tzinfo`` on read, so we set it explicitly to keep application-level
    comparisons unambiguous.
    """
    return datetime.now(UTC)


class Suggestion(Document):
    """Precomputed follow suggestion (T104).

    One row per ``(user_id, suggested_user_id)`` pair. The worker upserts
    on the unique compound and overwrites ``score`` / ``reasons`` /
    ``computed_at`` every time it re-runs for the user.
    """

    # Identity ---------------------------------------------------------------
    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (Constitution P2 + plan §3.1).
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Edge -------------------------------------------------------------------
    user_id: str = Field(..., description="KSUID of the viewer; who is receiving the suggestion.")
    suggested_user_id: str = Field(..., description="KSUID of the candidate to follow.")

    # Ranking ---------------------------------------------------------------
    score: float = Field(..., description="Ranking score in [0, 1]; higher = stronger.")
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable rationale tags ('mutual_taste', 'followed_by_followed', ...).",
    )

    computed_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        Indexes (plan §10.3):

        * ``(user_id, score DESC)`` — dominant read for the API surface.
        * ``(user_id, suggested_user_id)`` unique compound — the worker
          upserts on this; also drives "remove on dismiss".
        * ``computed_at`` TTL 7 days — stale precomputes auto-clean so
          the collection size matches recent active users.
        """

        name = "suggestions"
        indexes: list[IndexModel] = [
            IndexModel(
                [("user_id", ASCENDING), ("score", DESCENDING)],
                name="ix_suggestions_user_score",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("suggested_user_id", ASCENDING)],
                unique=True,
                name="ix_suggestions_user_candidate_unique",
            ),
            IndexModel(
                [("computed_at", ASCENDING)],
                expireAfterSeconds=60 * 60 * 24 * 7,  # 7 days
                name="ix_suggestions_computed_at_ttl",
            ),
        ]


class SuggestionDismissal(Document):
    """Per-user "Not now" record (T104).

    Created by ``POST /users/me/suggestions/{suggested_user_id}/dismiss``.
    The worker reads this collection as an "exclude this candidate"
    filter for 30 days, then the TTL expires the row and the candidate
    re-enters the pool.
    """

    # Identity
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Edge
    user_id: str = Field(..., description="KSUID of the viewer who dismissed.")
    suggested_user_id: str = Field(..., description="KSUID of the candidate that was dismissed.")

    dismissed_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        * ``(user_id, suggested_user_id)`` unique compound — upsert key
          for the dismiss endpoint; the duplicate insert path catches
          ``DuplicateKeyError`` and returns 204 so the endpoint is
          idempotent.
        * ``dismissed_at`` TTL 30 days — auto-clean so candidates
          re-enter the suggestion pool after a cooling-off window.
        """

        name = "suggestion_dismissals"
        indexes: list[IndexModel] = [
            IndexModel(
                [("user_id", ASCENDING), ("suggested_user_id", ASCENDING)],
                unique=True,
                name="ix_suggestion_dismissals_user_candidate_unique",
            ),
            IndexModel(
                [("dismissed_at", ASCENDING)],
                expireAfterSeconds=60 * 60 * 24 * 30,  # 30 days
                name="ix_suggestion_dismissals_dismissed_at_ttl",
            ),
        ]


__all__: Annotated[list[str], "public surface for from-imports"] = [
    "Suggestion",
    "SuggestionDismissal",
]
