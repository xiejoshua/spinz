"""Channel adapters for the notification dispatcher (T131).

Each adapter conforms to :class:`NotificationAdapter` and is registered
into a small in-process dict keyed by channel name. The dispatcher looks
up adapters by channel and fans out in parallel via :func:`asyncio.gather`.

At MVP only :class:`InAppAdapter` is wired. T135 (email) and T136 (push)
land their own adapter classes against this same Protocol — registering
them is a single :func:`register_adapter` call from their module's
``__init__``.
"""

from __future__ import annotations

from typing import Any, Protocol

from auxd_api.modules.notifications.adapters.in_app import InAppAdapter
from auxd_api.modules.notifications.models import Notification, NotificationType


class NotificationAdapter(Protocol):
    """Common shape every channel adapter must implement.

    The dispatcher invokes :meth:`send` with kwargs only — that's
    deliberate so future channels can add channel-specific kwargs without
    breaking the call site by position.
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
    ) -> Notification:
        """Deliver a single notification on this channel.

        Returns the persisted :class:`Notification` so the dispatcher can
        surface it back to the caller. Adapters that don't write a row
        (the future push adapter, for instance) still return the parent
        notification their caller supplied.
        """
        ...


# In-process adapter registry — keyed by channel name. The dispatcher
# imports this dict and fans out to whichever channels are registered.
# T135/T136 add their entries via :func:`register_adapter` at their
# module-load time so the dispatcher needs no per-channel knowledge.
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


# Register the in-app adapter at import time. Email + push adapters land
# in T135/T136 and self-register from their own modules.
register_adapter(InAppAdapter())


__all__ = [
    "InAppAdapter",
    "NotificationAdapter",
    "adapters",
    "get_adapter",
    "register_adapter",
    "reset_registry",
]
