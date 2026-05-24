"""Auth token Beanie Documents — email verification + password reset.

Feature ``002-auth-email-flows``. Two structurally-identical collections,
one per token kind, intentionally kept separate (NOT a polymorphic
``AuthToken`` with a ``kind`` field) because:

* Cleanup cadence + retention windows differ over time.
* Rate-limit windows differ at the route layer.
* Future divergence (e.g., 2FA challenge tokens) is easier with
  separate collections than with a polymorphic one.

Both collections store the **hash** of the raw token (SHA-256 with a
per-deploy pepper) — the raw token is only ever emitted into the email
payload and lives nowhere else. See :mod:`auxd_api.lib.auth_tokens` for
the crypto primitive.

Indexes
=======

* ``token_hash`` UNIQUE — drives the lookup on verify/reset.
* ``user_id, used_at`` partial (``used_at: null``) — covers the
  invalidate-prior-tokens-on-resend path.
* ``expires_at`` — drives the cleanup cron sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory.

    Used by ``default_factory`` on the token documents so timestamps are
    always tz-aware and round-trip cleanly through BSON (MongoDB stores
    datetimes in UTC but does not preserve tzinfo on read — we set UTC
    explicitly so application-level comparisons remain unambiguous).
    """
    return datetime.now(UTC)


class EmailVerificationToken(Document):
    """Single-use token sent in the signup / resend-verification email.

    See module docstring for the kind-split rationale. Lifecycle:

    1. ``POST /api/v1/auth/signup`` or ``POST /api/v1/auth/resend-
       verification`` issues a token; the raw token is emailed and the
       hash is persisted here.
    2. ``POST /api/v1/auth/verify-email`` consumes the token by stamping
       ``used_at`` + flipping the linked :class:`User.email_verified` to
       ``True``.
    3. The daily cleanup cron sweeps rows older than 7 days post-use or
       post-expiry.
    """

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    user_id: str = Field(..., description="KSUID of the linked User.")
    token_hash: str = Field(
        ...,
        description="SHA-256(raw_token + pepper), hex. Unique index — the lookup key on verify.",
    )
    expires_at: datetime = Field(
        ...,
        description="Hard expiry — typically created_at + 24h.",
    )
    used_at: datetime | None = Field(
        default=None,
        description="Set when the token is consumed (or invalidated as superseded).",
    )
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        Index rationale mirrors plan §1B:

        * ``token_hash`` unique — drives the verify lookup. A duplicate
          hash collision would be a programming error (broken pepper) or
          a 256-bit collision; either way, refuse the write.
        * ``(user_id, used_at)`` partial — covers the "invalidate prior
          unused tokens" path on resend; partial filter keeps the index
          small by ignoring already-consumed rows.
        * ``expires_at`` — drives the cleanup cron sweep that deletes
          tokens older than 7 days past expiry.
        """

        name = "email_verification_tokens"
        indexes: list[IndexModel] = [
            IndexModel([("token_hash", ASCENDING)], unique=True),
            IndexModel(
                [("user_id", ASCENDING), ("used_at", ASCENDING)],
                partialFilterExpression={"used_at": None},
            ),
            IndexModel([("expires_at", ASCENDING)]),
        ]


class PasswordResetToken(Document):
    """Single-use token sent in the forgot-password email.

    Structurally identical to :class:`EmailVerificationToken` but the TTL
    is shorter (1h vs 24h) and the cleanup cadence is independent. Kept
    in a separate collection per the kind-split rationale in the module
    docstring.
    """

    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    schema_version: int = Field(default=1, alias="_schema_version")

    user_id: str = Field(..., description="KSUID of the linked User.")
    token_hash: str = Field(
        ...,
        description="SHA-256(raw_token + pepper), hex. Unique index — the lookup key on reset.",
    )
    expires_at: datetime = Field(
        ...,
        description="Hard expiry — typically created_at + 1h.",
    )
    used_at: datetime | None = Field(
        default=None,
        description="Set when the token is consumed (or invalidated as superseded).",
    )
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        """Beanie collection settings — name + index declarations.

        Index shape mirrors :class:`EmailVerificationToken.Settings` (see
        plan §1C). Separate collection so the indexes don't share an
        ``expires_at`` partition with verification tokens (cleanup
        sweeps each independently).
        """

        name = "password_reset_tokens"
        indexes: list[IndexModel] = [
            IndexModel([("token_hash", ASCENDING)], unique=True),
            IndexModel(
                [("user_id", ASCENDING), ("used_at", ASCENDING)],
                partialFilterExpression={"used_at": None},
            ),
            IndexModel([("expires_at", ASCENDING)]),
        ]


__all__: Annotated[list[str], "public surface for from-imports"] = [
    "EmailVerificationToken",
    "PasswordResetToken",
]
