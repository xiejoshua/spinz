"""In-app notification adapter (T134).

Writes a single :class:`Notification` Beanie Document to the
``notifications`` collection per delivery. The bell-icon UI (T140, future
session) reads this collection to render the user's inbox; the 90-day
TTL declared on ``Notification.Settings.indexes`` reaps stale rows.

The adapter is intentionally thin — coalescing, dedup, and rate-limiting
all happen *upstream* in the dispatcher + coalescer chain. Each call here
creates exactly one row; producing a coalesced "X new updates" surface is
done by the dispatcher setting ``coalesced_count > 0`` so the in-app UI
can render the rollup copy.
"""

from __future__ import annotations

from typing import Any

from auxd_api.modules.notifications.models import (
    ChannelDispatchState,
    Notification,
    NotificationType,
)


class InAppAdapter:
    """Persists a notification row to the ``notifications`` collection."""

    channel: str = "in_app"

    async def send(
        self,
        *,
        user_id: str,
        type: NotificationType,  # noqa: A002 — Protocol param name
        payload: dict[str, Any],
        actor_id: str | None = None,
        coalesced_count: int = 0,
        notification_id: str | None = None,
    ) -> Notification:
        """Write a :class:`Notification` row and return it.

        Args:
            user_id: Recipient KSUID.
            type: Notification type from the taxonomy.
            payload: Type-specific data (validated upstream by
                :func:`notifications.types.validate_payload`).
            actor_id: KSUID of the user who triggered the event. ``None``
                for system-issued notifications (digest, security).
            coalesced_count: If non-zero, indicates this row represents
                a rollup of ``coalesced_count`` underlying events; the
                count is folded into ``payload`` so the in-app UI can
                render "X new updates today" copy.
            notification_id: Ignored by the in-app adapter — it always
                creates a fresh row. The kwarg exists for Protocol
                conformance with the email + push updater adapters.

        Returns:
            The persisted :class:`Notification`. The returned object
            carries the auto-generated KSUID ``id`` and tz-aware
            ``created_at`` for downstream caller use.
        """
        _ = notification_id  # creator adapter — ignores existing-row hint.

        # Make a defensive copy so adapter mutations don't leak back to
        # the caller's payload. Adding the coalesced_count alongside the
        # original payload keeps the in-app UI's "X new updates" branch
        # cheap to render — it just checks `payload.get("coalesced_count")`.
        notif_payload: dict[str, Any] = dict(payload)
        if coalesced_count > 0:
            notif_payload["coalesced_count"] = coalesced_count

        notif = Notification(
            user_id=user_id,
            type=type,
            payload=notif_payload,
            actor_id=actor_id,
            dispatch=ChannelDispatchState(in_app_delivered=True),
        )
        await notif.insert()
        return notif


__all__ = ["InAppAdapter"]
