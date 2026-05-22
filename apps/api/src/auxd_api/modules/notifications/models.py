"""Beanie Documents for the Notifications module (T026).

Covers four collections from plan §3.1:

* :class:`Notification` — one row per in-app/email/push notification, with a
  90-day TTL on ``created_at`` (plan §3.1 ``notifications`` row).
* :class:`FailedEmail` — append-only audit row written by the Resend adapter
  (T135) when a transactional send finally fails after retry exhaustion
  (sync-fix L4-003). Surfaces in the founder-side ops console for manual
  retry or refund.

Plus two embedded sub-documents / value types:

* :class:`ChannelDispatchState` — per-channel send/read state for a single
  ``Notification`` (in-app/email/push delivery timestamps, coalescing pointer).
* :class:`NotificationPreferences` — canonical embedded shape persisted on
  the ``User`` Document (T021). T021 ships its own structurally-identical
  ``NotificationPreferencesSubDoc`` to avoid a circular import at module load
  time; both shapes share field names + types and a downstream cleanup pass
  will dedupe.

The :class:`NotificationType` enum is the **source of truth** for the 18
active notification taxonomy keys (N-001..N-018). The string values mirror
``features/001-auxd-mvp/product-spec/notification-taxonomy.md`` exactly so
the Notifications dispatcher (T131), preference UI, and analytics tracking
plan can pivot on a single identifier set. N-019 and N-020 were reserved
for the Lists feature in Revision #1 and removed in Revision #3 when Lists
were deferred to v2; their IDs are **not** reassigned.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


class NotificationType(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """All 18 ACTIVE notification types (N-001..N-018).

    String values are the canonical taxonomy identifiers from
    ``product-spec/notification-taxonomy.md``. Do not rename without
    updating the taxonomy doc and writing a migration for any Notification
    rows already persisted with the old key.

    N-019 (``list.auxed``) and N-020 (``list.added_to``) were added in
    Revision #1 and removed in Revision #3 when Lists were deferred to v2.
    Their IDs are **reserved** (not reassigned) for audit and future Lists
    reactivation.
    """

    N001_FOLLOW_NEW = "follow.new"
    N002_FOLLOW_REQUEST_PENDING = "follow.request_pending"
    N003_FOLLOW_REQUEST_APPROVED = "follow.request_approved"
    N004_REVIEW_LIKED = "review.liked"  # R3 rename from review.auxed / review.hearted
    N005_REVIEW_REPLY = "review.reply"  # v2 feature; schema reserved
    N006_FRIEND_LOGGED_ALBUM = "friend.logged_album"
    N007_FRIEND_HIGH_RATED = "friend.high_rated"
    N008_WEEKLY_DIGEST = "weekly.digest"
    N009_IMPORT_COMPLETED = "import.completed"
    N010_IMPORT_FAILED = "import.failed"
    N011_SPOTIFY_RECONNECT_REQUIRED = "spotify.reconnect_required"
    N012_REPORT_ACKNOWLEDGED = "report.acknowledged"
    N013_ACCOUNT_DELETION_SCHEDULED = "account.deletion_scheduled"
    N014_ACCOUNT_DELETION_REMINDER_7D = "account.deletion_reminder_7d"
    N015_SYSTEM_ANNOUNCEMENT = "system.announcement"
    N016_SECURITY_NEW_SESSION = "security.new_session"
    N017_SECURITY_PASSWORD_CHANGED = "security.password_changed"
    N018_JUST_FINISHED_PROMPT = "just_finished.prompt"


class ChannelDispatchState(BaseModel):
    """Per-channel send/read state for a single :class:`Notification`.

    The dispatcher (T131) flips these flags as it fans a notification out
    to each enabled channel. ``coalesced_into`` is set when this row was
    rolled up into a parent (e.g. five ``follow.new`` events collapsed into
    one "Alex + 4 others followed you" surface) — the parent's id goes here
    so analytics can still attribute the original signal.
    """

    in_app_delivered: bool = False
    in_app_read_at: datetime | None = None
    email_sent_at: datetime | None = None
    push_sent_at: datetime | None = None
    coalesced_into: str | None = None  # parent Notification.id if rolled up


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory shared by every default_factory."""
    return datetime.now(UTC)


class Notification(Document):
    """A single notification surfaced to a user across in-app/email/push.

    Indexed for the two dominant read paths plus a 90-day TTL purge:

    * ``(user_id, created_at desc)`` — paginated inbox.
    * ``(user_id, read_at)`` sparse — unread badge count.
    * ``created_at`` TTL (90 days) — MongoDB auto-expires old rows so the
      collection doesn't grow unbounded (plan §3.1 ``notifications`` row).
    """

    _schema_version: int = 1

    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (plan §3.1 + Constitution P2).
    # The mypy ``[assignment]`` mismatch with ``Document.id: PydanticObjectId | None``
    # is a known and accepted pattern across all sibling model modules.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str  # recipient
    type: NotificationType
    payload: dict[str, Any] = Field(default_factory=dict)
    # ^ type-specific data (e.g. {"album_id": ..., "actor_handle": ...}).
    actor_id: str | None = None  # who triggered (None for system notifs)
    dispatch: ChannelDispatchState = Field(default_factory=ChannelDispatchState)
    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "notifications"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel(
                [("user_id", ASCENDING), ("read_at", ASCENDING)],
                sparse=True,
            ),
            IndexModel(
                [("created_at", ASCENDING)],
                expireAfterSeconds=int(timedelta(days=90).total_seconds()),
                name="ttl_notifications_90d",
            ),
        ]


class NotificationPreferences(BaseModel):
    """Canonical embedded sub-document for User notification preferences.

    Persisted on :class:`auxd_api.modules.users.models.User`. The three
    per-channel dicts are keyed by :class:`NotificationType` *value*
    (e.g. ``"review.liked"``) and map to an explicit opt-in/opt-out
    boolean. A missing key falls back to the per-channel default declared
    in ``product-spec/notification-taxonomy.md``.

    T021's ``NotificationPreferencesSubDoc`` is the structural twin of
    this model; both are kept in sync manually until a follow-up dedupe
    consolidates them under this name.
    """

    in_app: dict[str, bool] = Field(default_factory=dict)
    email: dict[str, bool] = Field(default_factory=dict)
    push: dict[str, bool] = Field(default_factory=dict)
    weekly_digest: bool = True
    version: int = 1


class FailedEmail(Document):
    """Audit row written by the Resend adapter (T135) on final send failure.

    Sync-fix L4-003: when a transactional email exhausts its retry budget
    (DNS failure, persistent 5xx, hard bounce), the adapter writes one
    :class:`FailedEmail` row so the founder ops console can surface it for
    manual replay or user outreach. The payload is captured verbatim so a
    retry can re-render the exact same email body.

    ``notification_type`` is typed as :class:`NotificationType` because every
    MVP transactional email is keyed off an entry in the notification
    taxonomy (digest, reconnect-required, deletion reminders, etc.). If a
    future non-notification email — e.g. a billing receipt — needs to land
    here, widen this to ``NotificationType | str``.
    """

    _schema_version: int = 1

    # See :class:`Notification.id` for the rationale on the KSUID override
    # and the accepted mypy ``[assignment]`` mismatch.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str
    notification_type: NotificationType
    payload: dict[str, Any]
    attempted_at: datetime = Field(default_factory=_utcnow)
    last_error: str
    retry_count: int = 0  # final attempt count after retry-budget exhaustion

    class Settings:
        name = "failed_emails"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("user_id", ASCENDING), ("attempted_at", DESCENDING)]),
            IndexModel([("attempted_at", DESCENDING)]),
        ]


__all__ = [
    "ChannelDispatchState",
    "FailedEmail",
    "Notification",
    "NotificationPreferences",
    "NotificationType",
]
