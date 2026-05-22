"""Beanie Documents for the Prompts module.

Per data-model.md, plan §3.1 + §9, and FR-026:

* :class:`JustFinishedPrompt` — a per-user, per-album "you just listened to
  X — log it?" card that originally surfaced shortly after a music
  provider reported the album as finished. Pending prompts are dropped
  automatically after 24h via a TTL index scoped to ``state == "pending"``.

The polling job that *creates* these rows and the card-ordering service
that *consumes* them live in separate tasks (T123 / T117 / T117a).

# CR-001 (2026-05-22): JustFinishedPrompt is DEFERRED-TO-V2 — the model
# class is kept for v2 reactivation but is NOT registered with Beanie via
# ALL_DOCUMENT_MODELS at MVP. SuggestedFollow + CriticSeed remain in MVP
# scope. See features/001-auxd-mvp/change-log.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class JustFinishedPromptState(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """Lifecycle states for a :class:`JustFinishedPrompt`.

    The TTL index on ``expires_at`` is scoped to ``PENDING`` only — once a
    prompt has been ``LOGGED``, ``DISMISSED``, ``EXPIRED``, or ``SUPPRESSED``
    it must remain in the collection as part of the user's prompt history
    (so we can honour the 30-day re-prompt cooldown after a dismissal, and
    so analytics can attribute logged diary entries back to the prompt
    that triggered them).
    """

    PENDING = "pending"  # detected, prompt card not yet shown or not yet acted on
    LOGGED = "logged"  # user accepted prompt; diary entry created
    DISMISSED = "dismissed"  # user tapped "Not now"; same album won't re-prompt for 30d
    EXPIRED = "expired"  # 24h elapsed without action (TTL drops these)
    SUPPRESSED = "suppressed"  # blocked by quiet hours or per-album mute or global opt-out


class JustFinishedPrompt(Document):
    """Pending 'just listened to X — log it?' card.

    Per FR-026 + S-B6 + plan §9. One row per (user, album, detected
    listening session). When this feature reactivates in v2, the polling
    job sets ``detected_at`` + ``expires_at`` when a music provider's
    recently-played feed first reports the finished album; the UI layer
    sets ``surfaced_at`` when the card is first shown; user action moves
    the row out of ``PENDING`` and stamps ``acted_at``.

    CR-001 (2026-05-22): DEFERRED-TO-V2. The original v1 design polled
    Spotify recently-played; the v2 design will re-pick the source
    provider at activation time.
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str  # FK → User; the user we're prompting
    album_id: str  # FK → Album; the album they just finished
    state: JustFinishedPromptState = JustFinishedPromptState.PENDING
    # CR-001: provider-source comment updated — v2 reactivation will
    # repick the provider feed. Field semantics unchanged.
    detected_at: datetime  # when the provider's recently-played first reported the album
    surfaced_at: datetime | None = None  # when the card was first shown in the UI
    acted_at: datetime | None = None  # when state moved out of PENDING
    logged_diary_entry_id: str | None = None  # FK → DiaryEntry if state == LOGGED
    push_sent_at: datetime | None = None  # when the push notification (if any) went out
    expires_at: datetime  # 24h after detected_at; TTL drops PENDING rows at this point

    class Settings:
        name = "just_finished_prompts"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            # Primary read pattern: "show me this user's pending prompts, newest first."
            IndexModel(
                [("user_id", ASCENDING), ("state", ASCENDING), ("detected_at", DESCENDING)],
            ),
            # TTL: drop pending prompts 24h after detection. The partial filter
            # is critical — we keep LOGGED / DISMISSED / SUPPRESSED rows so we
            # can enforce the 30-day per-album cooldown and attribute analytics.
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                partialFilterExpression={"state": "pending"},
                name="ttl_just_finished_prompts_24h",
            ),
        ]
