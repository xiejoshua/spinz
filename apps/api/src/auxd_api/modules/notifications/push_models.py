"""Web Push subscription Beanie Document (T136).

Lives next to :mod:`auxd_api.modules.notifications.models` rather than
inside it because :class:`PushSubscription` is owned by the push
delivery channel and has a different lifecycle from the audit-trail
:class:`Notification` row — separating modules keeps the imports clean
and lets the :mod:`web_push` adapter own its persistence type without
pulling the full notifications surface into scope.

Lifecycle:

* **Create / refresh.** Browser opt-in flow calls
  ``POST /api/v1/users/me/push-subscriptions`` with the standard
  :class:`PushSubscription` JSON
  (``{endpoint, keys: {p256dh, auth}}``). The endpoint URL is unique
  per browser instance; if the row already exists the route updates
  ``last_used_at`` instead of erroring (the browser may re-send the
  same endpoint at any time).
* **Delete.** The owner can remove a subscription via
  ``DELETE /api/v1/users/me/push-subscriptions/{subscription_id}``.
* **Reap-on-410.** The :class:`WebPushAdapter` deletes a row when the
  push service responds 410 Gone / 404 — the browser revoked the
  subscription out-of-band.

Indexes:

* ``user_id`` — fan-out lookup by recipient.
* ``endpoint`` unique — at most one row per browser instance.
"""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING
from pymongo.operations import IndexModel

from auxd_api.lib.ids import new_ksuid


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` factory shared by every default_factory."""
    return datetime.now(UTC)


class PushSubscription(Document):
    """One browser-registered Web Push subscription.

    The triple ``(endpoint, p256dh_key, auth_secret)`` is everything the
    :class:`WebPushAdapter` needs to encrypt + deliver a push payload
    via :func:`pywebpush.webpush`.
    """

    _schema_version: int = 1

    # See :class:`Notification.id` for the rationale on the KSUID
    # override and the accepted mypy ``[assignment]`` mismatch.
    id: str = Field(default_factory=new_ksuid, alias="_id")  # type: ignore[assignment]
    user_id: str = Field(..., description="Recipient KSUID.")
    endpoint: str = Field(
        ...,
        description=(
            "Browser-provided push service URL (e.g. https://fcm.googleapis.com/wp/...). "
            "Unique per (user, browser instance)."
        ),
    )
    p256dh_key: str = Field(
        ...,
        description="Client public key used for payload encryption (base64-encoded).",
    )
    auth_secret: str = Field(
        ...,
        description="Client auth secret used for payload encryption (base64-encoded).",
    )
    user_agent: str | None = Field(
        default=None,
        description="Diagnostic User-Agent string captured at subscribe time.",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime | None = Field(
        default=None,
        description="Updated whenever the browser re-asserts the subscription.",
    )

    class Settings:
        """Beanie collection settings — name + index declarations."""

        name = "push_subscriptions"
        indexes = [  # noqa: RUF012 — Beanie Settings expects a plain list
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("endpoint", ASCENDING)], unique=True),
        ]


__all__ = ["PushSubscription"]
