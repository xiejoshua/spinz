"""Social-graph Documents: :class:`Follow`, :class:`FollowRequest`, :class:`Block` (T025).

These three Beanie collections back the social module described in
plan §3.1 (collection rows ``follows`` / ``follow_requests`` / ``blocks``)
and §4.6 (social-graph service surface). They are pure data shapes —
the cascade-on-block semantics noted in the docstrings live in the
service layer (T101); this module just stores the rows.

Design notes:

* **Follow vs FollowRequest split.** Sync-fix L3-002 introduced the
  separate ``FollowRequest`` collection so that pending requests against
  *private* profiles (US-G2) live in their own queue without polluting
  the accepted-follow graph. Public-profile follows go straight to a
  ``Follow`` row with ``state=ACCEPTED``. The ``FollowState`` enum on
  the ``Follow`` doc therefore retains ``pending`` / ``rejected``
  primarily for transition-history / audit and for any legacy data
  written before the request collection existed.

* **Cascade-on-block.** Creating a ``Block`` must remove any existing
  ``Follow`` and any open ``FollowRequest`` in *either* direction
  between the two users. That logic is the responsibility of the
  ``social.block`` service in T101 — this module just stores the
  ``Block`` record. Indexes here are sized accordingly (the
  ``blocker_id``-prefixed unique index is the lookup the cascade uses).

* **Indexes** are declared via :class:`pymongo.operations.IndexModel`
  rather than the Beanie ``Indexed`` annotation to keep the compound +
  unique semantics explicit and grep-able.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid

# Field-length constant — kept module-level so the service layer (T101) and
# tests can import a single source of truth rather than duplicating the limit.
BLOCK_OTHER_REASON_MAX_LEN = 500


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime.now`` factory.

    Mirrors :func:`auxd_api.modules.users.models._utcnow` — BSON stores
    timestamps in UTC but strips ``tzinfo`` on read, so we set it
    explicitly to keep application-level comparisons unambiguous.
    """
    return datetime.now(UTC)


class FollowState(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """State of a :class:`Follow` record.

    Public-profile follows go straight to :attr:`ACCEPTED`. The
    :attr:`PENDING` / :attr:`REJECTED` values exist primarily for audit /
    transition-history and for any pre-:class:`FollowRequest` data; the
    live private-profile flow goes through :class:`FollowRequest` and
    only writes a ``Follow`` row on approval.
    """

    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"


class FollowRequestStatus(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """Lifecycle of a :class:`FollowRequest` against a private profile."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class BlockReason(str, Enum):  # noqa: UP042 — spec mandates `(str, Enum)` form
    """User-supplied reason for a :class:`Block`.

    When :attr:`OTHER` is selected, the free-text rationale lives in
    :attr:`Block.other_reason` (length-capped at
    :data:`BLOCK_OTHER_REASON_MAX_LEN` by the service layer).
    """

    HARASSMENT = "harassment"
    SPAM = "spam"
    UNWANTED = "unwanted_contact"
    OTHER = "other"


class Follow(Document):
    """Asymmetric follow edge — ``follower_id`` follows ``followee_id``.

    No reciprocity is implied: a Follow row from A→B exists independently
    of any B→A row. The :attr:`state` field is kept on the Follow doc
    itself rather than offloaded to a side-channel so transition history
    (accepted → revoked, etc.) is queryable via the same index.
    """

    # Identity ---------------------------------------------------------------
    # Override Beanie's default ObjectId ``_id`` with a KSUID string so IDs
    # are chronologically sortable and URL-safe (Constitution P2 + plan §3.1).
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Edge -------------------------------------------------------------------
    follower_id: str = Field(..., description="KSUID of the user doing the following.")
    followee_id: str = Field(..., description="KSUID of the user being followed.")
    state: FollowState = FollowState.ACCEPTED

    # Provenance -------------------------------------------------------------
    # Free-form tag identifying where the follow originated. Values used in
    # MVP: ``onboarding_preselected`` | ``suggestion`` | ``profile`` |
    # ``invite``. Left as ``str | None`` so analytics can iterate without a
    # schema migration; values are validated at the service-layer boundary.
    source: str | None = None

    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        Indexes mirror plan §3.1 row ``follows``:

        * ``(follower_id, followee_id)`` unique — at most one Follow row
          per ordered pair; the cascade-on-block path uses this index to
          locate-and-delete in O(log n).
        * ``(followee_id, state, created_at DESC)`` — "who follows me"
          listing with recency ordering and an in-line state filter.
        * ``(follower_id, created_at DESC)`` — "who am I following"
          listing with recency ordering.
        """

        name = "follows"
        indexes: list[IndexModel] = [
            IndexModel(
                [("follower_id", ASCENDING), ("followee_id", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [
                    ("followee_id", ASCENDING),
                    ("state", ASCENDING),
                    ("created_at", DESCENDING),
                ],
            ),
            IndexModel(
                [("follower_id", ASCENDING), ("created_at", DESCENDING)],
            ),
        ]


class FollowRequest(Document):
    """Pending follow-request against a private profile (US-G2 / sync-fix L3-002).

    Lifecycle:

    * **Approve.** Status transitions to :attr:`FollowRequestStatus.ACCEPTED`
      and the service layer (T101) writes a new :class:`Follow` row with
      ``state=ACCEPTED``. The request row is retained for audit.
    * **Decline.** Status transitions to :attr:`FollowRequestStatus.DECLINED`;
      no ``Follow`` row is ever created.
    * **Expire.** Status transitions to :attr:`FollowRequestStatus.EXPIRED`
      after 30 days of inactivity via a background sweep job.
    """

    # Identity
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Edge
    requester_id: str = Field(..., description="KSUID of the user asking to follow.")
    requestee_id: str = Field(..., description="KSUID of the private-profile user.")
    status: FollowRequestStatus = FollowRequestStatus.PENDING

    created_at: datetime = Field(default_factory=_utcnow)
    responded_at: datetime | None = None  # set on accept/decline/expire

    class Settings:
        """Beanie collection settings — name + index declarations.

        Indexes mirror plan §3.1 row ``follow_requests``:

        * ``(requester_id, requestee_id)`` unique — at most one open
          request per ordered pair (re-requests after decline reuse the
          row by transitioning status, rather than inserting a duplicate).
        * ``(requestee_id, status, created_at DESC)`` — drives the
          "pending requests inbox" listing for the requestee.
        """

        name = "follow_requests"
        indexes: list[IndexModel] = [
            IndexModel(
                [("requester_id", ASCENDING), ("requestee_id", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [
                    ("requestee_id", ASCENDING),
                    ("status", ASCENDING),
                    ("created_at", DESCENDING),
                ],
            ),
        ]


class Block(Document):
    """User-initiated block — ``blocker_id`` blocks ``blockee_id``.

    Symmetric visibility hiding is enforced by ``lib/visibility`` at read
    time, so the row only needs to record the directional intent.

    Cascade-on-block (service-layer, T101): creating a Block dissolves
    any existing :class:`Follow` and any open :class:`FollowRequest` in
    *either* direction between the two users. This model only stores the
    Block record; the cascade is intentionally not implemented here.
    """

    # Identity
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    # Edge
    blocker_id: str = Field(..., description="KSUID of the user initiating the block.")
    blockee_id: str = Field(..., description="KSUID of the user being blocked.")

    # Reason
    reason: BlockReason = BlockReason.OTHER
    # Free-text rationale when ``reason == BlockReason.OTHER``. The 500-char
    # cap (:data:`BLOCK_OTHER_REASON_MAX_LEN`) is enforced at the service
    # layer alongside the conditional-required check.
    other_reason: str | None = None

    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        Indexes mirror plan §3.1 row ``blocks``:

        * ``(blocker_id, blockee_id)`` unique — at most one Block row per
          ordered pair; the cascade lookup also uses this index.
        * ``(blockee_id,)`` — admin / audit query "who has blocked this
          user". Non-unique because the same user can be blocked by many
          others.
        """

        name = "blocks"
        indexes: list[IndexModel] = [
            IndexModel(
                [("blocker_id", ASCENDING), ("blockee_id", ASCENDING)],
                unique=True,
            ),
            IndexModel([("blockee_id", ASCENDING)]),
        ]


# Re-export the most commonly imported symbols so callers can write
# ``from auxd_api.modules.social.models import Follow, FollowRequest, Block``
# without pulling in the full module surface.
__all__: Annotated[list[str], "public surface for from-imports"] = [
    "BLOCK_OTHER_REASON_MAX_LEN",
    "Block",
    "BlockReason",
    "Follow",
    "FollowRequest",
    "FollowRequestStatus",
    "FollowState",
]
