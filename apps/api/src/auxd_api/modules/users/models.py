"""User Document + handle policy fields (T021).

Implements the Beanie :class:`User` Document plus its embedded sub-documents
per plan §3.1 (``users`` collection) and §4.3 (FR-029 handle policy).

Key invariants enforced by this module:

* KSUID ``_id`` (27-char base62, chronologically sortable) generated via
  :func:`auxd_api.lib.ids.new_ksuid`.
* Constitution P2 — every document carries ``_schema_version: int = 1`` so
  future migrations can fan out on schema_version.
* Handle policy (FR-029): the model exposes ``handle_created_at`` (set on
  account creation) and ``handle_changed_at`` (None until the first change)
  so ``modules/auth/handle_service.py`` can enforce "immutable first 30 days,
  then ≤1 change per 30 days" without re-reading audit logs.
* OAuth tokens for music providers are **only** persisted in the encrypted
  form produced by :class:`auxd_api.lib.secrets.TokenEncryptor`. The model
  intentionally does not carry plaintext fields; conversion happens at the
  service-layer boundary.

Indexes are declared via :class:`pymongo.operations.IndexModel` rather than
the Beanie ``Indexed`` annotation because two of the four indexes require
``partialFilterExpression`` / ``sparse=True`` options that ``Indexed``
cannot express compactly.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from enum import Enum
from typing import Annotated

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid
from auxd_api.lib.visibility import Visibility

# Field-length constants — kept module-level so tests and callers can import
# them rather than duplicating magic numbers.
HANDLE_MIN_LEN = 3
HANDLE_MAX_LEN = 30
DISPLAY_NAME_MAX_LEN = 80
BIO_MAX_LEN = 500


class UserStatus(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """Lifecycle state of a user account.

    * ``ACTIVE`` — normal, usable account.
    * ``DELETED`` — soft-deleted, inside the 30-day GDPR grace window
      (US-G5 / FR-019). Recoverable by the owner; invisible to everyone else.
    * ``SUSPENDED`` — moderation action; account is read-only / hidden until
      a moderator restores it.
    """

    ACTIVE = "active"
    DELETED = "deleted"
    SUSPENDED = "suspended"


class MusicProviderSubDoc(BaseModel):
    """Per-user, per-provider credential block (embedded on :class:`User`).

    One entry per connected provider. Tokens are **always** stored encrypted
    via :class:`auxd_api.lib.secrets.TokenEncryptor` — this model has no
    plaintext-token field by design.
    """

    provider: str  # "spotify" | "lastfm" | future providers
    provider_user_id: str
    display_name: str | None = None
    connected_at: datetime
    access_token_encrypted: str  # base64 ciphertext from TokenEncryptor.encrypt()
    refresh_token_encrypted: str | None = None
    token_expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)


class NotificationPreferencesSubDoc(BaseModel):
    """Per-user notification preferences (embedded on :class:`User`).

    The three per-channel dicts are keyed by notification *type* (e.g.
    ``"new_follower"``, ``"review_liked"``) and map to a boolean opt-in.
    Missing keys are treated as opt-in / opt-out per the channel default
    in :mod:`auxd_api.lib.notifications` (defined separately).
    """

    in_app: dict[str, bool] = Field(default_factory=dict)
    email: dict[str, bool] = Field(default_factory=dict)
    push: dict[str, bool] = Field(default_factory=dict)
    weekly_digest: bool = True
    version: int = 1


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory.

    Used by every ``default_factory`` on :class:`User` so timestamps are
    always tz-aware and round-trip cleanly through BSON (MongoDB stores
    datetimes in UTC but does not preserve tzinfo on read — we set UTC
    explicitly so application-level comparisons remain unambiguous).
    """
    return datetime.now(UTC)


class User(Document):
    """User account document.

    See module docstring for invariants. Field ordering mirrors the
    product-spec sketch in ``data-model.md`` lines 33-67 grouped by concern:
    identity → profile → status → preferences → timestamps → embedded.
    """

    # Identity ---------------------------------------------------------------
    # We override Beanie's default ObjectId ``_id`` with a KSUID string so
    # IDs are chronologically sortable and URL-safe (Constitution P2 + plan §3.1).
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Profile ----------------------------------------------------------------
    handle: str = Field(
        ...,
        min_length=HANDLE_MIN_LEN,
        max_length=HANDLE_MAX_LEN,
        description="Username; lowercase alphanumeric + underscore, 3-30 chars.",
    )
    email: str = Field(..., description="Primary email; lowercased upstream.")
    display_name: str = Field(..., max_length=DISPLAY_NAME_MAX_LEN)
    password_hash: str | None = None
    bio: str = Field(default="", max_length=BIO_MAX_LEN)
    avatar_url: str | None = None

    # Lifecycle / moderation -------------------------------------------------
    status: UserStatus = UserStatus.ACTIVE

    # Feature opt-ins --------------------------------------------------------
    auto_prompt_enabled: bool = True  # FR-026 just-finished in-app prompt
    auto_prompt_push_enabled: bool = False  # FR-026 push surface for prompt
    private_profile: bool = False  # US-G2 / FR-013

    # Visibility defaults (US-G1 / data-model.md §User) ---------------------
    default_entry_visibility: Visibility = Visibility.PUBLIC
    default_backlog_visibility: Visibility = Visibility.PRIVATE
    keep_backlog_after_log: bool = False  # S-D3 alt-path: default = auto-remove on log

    # Session bookkeeping ----------------------------------------------------
    # Incremented on password change / forced logout; every cookie carries
    # the version at issue time so a bump invalidates all prior sessions.
    session_version: int = 1

    # Timestamps -------------------------------------------------------------
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    handle_created_at: datetime = Field(default_factory=_utcnow)
    handle_changed_at: datetime | None = None  # None until first change (FR-029)
    deletion_scheduled_for: datetime | None = None  # US-G5 / FR-019 — 30d grace
    last_seen_at: datetime | None = None

    # Notification quiet hours ----------------------------------------------
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    quiet_hours_tz: str = "UTC"  # IANA timezone string

    # Embedded sub-documents -------------------------------------------------
    music_providers: list[MusicProviderSubDoc] = Field(default_factory=list)
    notification_preferences: NotificationPreferencesSubDoc = Field(
        default_factory=NotificationPreferencesSubDoc
    )

    class Settings:
        """Beanie collection settings — name + index declarations.

        Indexes mirror plan §3.1 row ``users``:

        * ``handle`` unique sparse — enforces global uniqueness; sparse so
          documents missing the field (none expected, defence-in-depth)
          don't collide on ``null``.
        * ``email`` unique sparse — same rationale.
        * ``status`` partial — only index ``active`` rows; lets us run a fast
          status filter on the dominant query path without the index ballooning
          to cover deleted / suspended accounts.
        * ``deletion_scheduled_for`` sparse — drives the daily GDPR sweep job
          that hard-deletes accounts past their 30-day grace window.
        """

        name = "users"
        indexes: list[IndexModel] = [
            IndexModel([("handle", ASCENDING)], unique=True, sparse=True),
            IndexModel([("email", ASCENDING)], unique=True, sparse=True),
            IndexModel(
                [("status", ASCENDING)],
                partialFilterExpression={"status": "active"},
            ),
            IndexModel([("deletion_scheduled_for", ASCENDING)], sparse=True),
        ]


# Re-export the most commonly imported symbols so callers can write
# ``from auxd_api.modules.users.models import User, UserStatus`` without
# pulling in the full module surface.
__all__: Annotated[list[str], "public surface for from-imports"] = [
    "BIO_MAX_LEN",
    "DISPLAY_NAME_MAX_LEN",
    "HANDLE_MAX_LEN",
    "HANDLE_MIN_LEN",
    "MusicProviderSubDoc",
    "NotificationPreferencesSubDoc",
    "User",
    "UserStatus",
]
