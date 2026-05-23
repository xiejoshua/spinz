"""Channel adapters for the notification dispatcher (T131).

Each adapter conforms to :class:`NotificationAdapter` and is registered
into a small in-process dict keyed by channel name. The dispatcher looks
up adapters by channel and fans out in parallel via :func:`asyncio.gather`.

Two adapter shapes live behind the same Protocol:

* **Creator adapters** (in-app) — write a fresh :class:`Notification`
  row and return it. Called with ``notification_id=None``.
* **Updater adapters** (email, push) — receive ``notification_id`` from
  the dispatcher (the in-app row's id) and stamp the channel-specific
  ``dispatch.email_sent_at`` / ``dispatch.push_sent_at`` field on that
  existing row. Returns the updated row (or ``None`` when the channel
  is short-circuited — e.g. the email adapter on a type with no
  ``email_subject``).

The dispatcher threads ``notification_id`` through after the in-app
adapter persists its row, so audit + inbox state remain on a single
Notification Document per dispatch.
"""

from __future__ import annotations

from typing import Any, Protocol

from auxd_api.modules.notifications.adapters.email import EmailAdapter
from auxd_api.modules.notifications.adapters.in_app import InAppAdapter
from auxd_api.modules.notifications.adapters.web_push import WebPushAdapter
from auxd_api.modules.notifications.models import Notification, NotificationType


class NotificationAdapter(Protocol):
    """Common shape every channel adapter must implement.

    The dispatcher invokes :meth:`send` with kwargs only — that's
    deliberate so future channels can add channel-specific kwargs without
    breaking the call site by position.

    ``notification_id`` is the id of the in-app row the dispatcher
    already persisted. Creator adapters (in-app) ignore it; updater
    adapters (email, push) use it to stamp the channel's ``*_sent_at``
    field on the existing row so the audit trail stays on one Document.
    """

    channel: str

    async def send(
        self,
        *,
        user_id: str,
        type: NotificationType,
        payload: dict[str, Any],
        actor_id: str | None = None,
        coalesced_count: int = 0,
        notification_id: str | None = None,
    ) -> Notification | None:
        """Deliver a single notification on this channel.

        Returns the persisted :class:`Notification` so the dispatcher can
        surface it back to the caller. Returns ``None`` when the adapter
        is a no-op for this dispatch (e.g. email adapter on a type with
        no ``email_subject`` set).
        """
        ...


# In-process adapter registry — keyed by channel name. The dispatcher
# imports this dict and fans out to whichever channels are registered.
# T135 (email) + T136 (push) self-register from their modules at import
# time; the imports above pull them in eagerly.
_ADAPTERS: dict[str, NotificationAdapter] = {}


def register_adapter(adapter: NotificationAdapter) -> None:
    """Register ``adapter`` under its ``channel`` name.

    Subsequent calls for the same channel replace the entry — this lets
    tests swap a real adapter for a stub without monkeypatching the
    dispatcher.
    """
    _ADAPTERS[adapter.channel] = adapter


def get_adapter(channel: str) -> NotificationAdapter | None:
    """Return the adapter registered for ``channel``, or ``None``."""
    return _ADAPTERS.get(channel)


def adapters() -> dict[str, NotificationAdapter]:
    """Return a shallow copy of the live registry (mostly for tests)."""
    return dict(_ADAPTERS)


def reset_registry() -> None:
    """Clear the registry. Test helper only; production never calls this."""
    _ADAPTERS.clear()


def _register_defaults() -> None:
    """Register the three MVP adapters under their canonical channels.

    Kept as a function so :func:`reset_registry` callers (tests) can
    restore the default registry by invoking this helper.
    """
    register_adapter(InAppAdapter())
    register_adapter(EmailAdapter())
    register_adapter(WebPushAdapter())


# Register the in-app + email + push adapters at import time.
_register_defaults()


__all__ = [
    "EmailAdapter",
    "InAppAdapter",
    "NotificationAdapter",
    "WebPushAdapter",
    "_register_defaults",
    "adapters",
    "get_adapter",
    "register_adapter",
    "reset_registry",
]
