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

CR-001 (2026-05-22): removed Spotify integration from
``music_providers`` (provider-specific subclass shape gone — the dict now
holds neutral :class:`MusicProviderState` values keyed by provider name).
Also dropped ``auto_prompt_enabled`` / ``auto_prompt_push_enabled`` (the
just-finished feature is DEFERRED-TO-V2). See
``features/001-auxd-mvp/change-log.md``.
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
    * ``DELETION_PENDING`` — user requested deletion; inside the 30-day
      grace window (US-G5 / FR-019). The cascade worker (T058) hard-deletes
      after the grace expires; the user can cancel at any point during
      the window via :func:`auxd_api.modules.users.service.cancel_account_deletion`.
    * ``DELETED`` — legacy soft-deleted state retained for any historical
      rows that pre-dated ``DELETION_PENDING``. New writes never set this
      value; the cascade worker either deletes the row entirely or leaves
      it in ``DELETION_PENDING``.
    * ``SUSPENDED`` — moderation action; account is read-only / hidden until
      a moderator restores it.
    """

    ACTIVE = "active"
    DELETION_PENDING = "deletion_pending"
    DELETED = "deleted"
    SUSPENDED = "suspended"


class MusicProviderState(BaseModel):
    """Per-user, per-provider linkage state (embedded on :class:`User`).

    CR-001 (2026-05-22): the original ``MusicProviderSubDoc`` carried
    Spotify OAuth fields (``provider_user_id``, ``access_token_encrypted``,
    ``refresh_token_encrypted``, ``token_expires_at``, ``scopes``). With
    Spotify removed at MVP, ``music_providers`` now holds neutral linkage
    metadata keyed by provider name (``"musicbrainz"``, ``"discogs"``,
    future providers). Token fields stay out of this shape entirely; any
    future OAuth provider can extend with its own model and store encrypted
    tokens via :class:`auxd_api.lib.secrets.TokenEncryptor`.
    """

    provider: str  # "musicbrainz" | "discogs" | future providers
    display_name: str | None = None
    connected_at: datetime


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
    # CR-001: removed ``auto_prompt_enabled`` + ``auto_prompt_push_enabled``
    # (FR-026 just-finished prompt is DEFERRED-TO-V2; the JustFinishedPrompt
    # collection stays importable but is not registered with Beanie at MVP).
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
    # CR-001: ``music_providers`` switched from
    # ``list[MusicProviderSubDoc]`` (Spotify-shaped) to a neutral
    # ``dict[str, MusicProviderState]`` keyed by provider name. The
    # provider-abstraction layer (Phase-5 plan §6) reads from this dict so
    # future providers can be added without schema migrations.
    music_providers: dict[str, MusicProviderState] = Field(default_factory=dict)
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


class HandleRedirect(Document):
    """Redirect record for a handle the user changed away from (T060).

    When a user changes their handle (T057), the old handle is parked in
    this collection for the redirect window so links pointing at
    ``/@oldhandle`` keep resolving. The retention window is governed by
    FR-029 / Q16 — 90 days post-change — but the cleanup itself runs in a
    separate sweep job (out of scope for the §5 cluster); this document
    only stores the row.

    Invariants:

    * ``old_handle`` is unique — a single previous handle resolves to at
      most one current user. If another user later claims the freed-up
      handle, the redirect must already have been swept (or the handle
      change route refuses the claim).
    * ``user_id`` is the KSUID of the User that *currently* holds
      ``new_handle``; the resolver dereferences through ``user_id`` so a
      subsequent handle change still routes old links to the latest
      identity.
    """

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    old_handle: str = Field(..., description="The handle the user moved away from.")
    new_handle: str = Field(..., description="The handle that replaced ``old_handle``.")
    user_id: str = Field(..., description="KSUID of the User that owns ``new_handle``.")
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        * ``old_handle`` unique — at most one redirect per previous handle.
        * ``user_id`` — supports the cascade-delete sweep when a user is
          hard-deleted (T058) and avoids a collection scan.
        """

        name = "handle_redirects"
        indexes: list[IndexModel] = [
            IndexModel([("old_handle", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING)]),
        ]


# Re-export the most commonly imported symbols so callers can write
# ``from auxd_api.modules.users.models import User, UserStatus`` without
# pulling in the full module surface.
__all__: Annotated[list[str], "public surface for from-imports"] = [
    "BIO_MAX_LEN",
    "DISPLAY_NAME_MAX_LEN",
    "HANDLE_MAX_LEN",
    "HANDLE_MIN_LEN",
    "HandleRedirect",
    "MusicProviderState",
    "NotificationPreferencesSubDoc",
    "User",
    "UserStatus",
]
