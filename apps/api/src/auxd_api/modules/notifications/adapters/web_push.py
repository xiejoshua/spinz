"""Web push notification adapter (T136).

VAPID-signed Web Push delivery via :func:`pywebpush.webpush`. The
adapter is send-and-forget: failures are observability events, not
exceptions into the caller.

Updater-shape adapter (see :mod:`adapters.__init__` docstring):

* Reads :class:`PushSubscription` rows for the recipient.
* Posts an encrypted JSON payload to each subscription endpoint.
* On 410 Gone / 404 Not Found: deletes the subscription row (the
  browser revoked the subscription out-of-band).
* On other failures: logs + Sentry alert tagged ``web_push.send_failed``,
  swallows so a bad endpoint doesn't poison the fan-out.
* Stamps ``Notification.dispatch.push_sent_at`` on the supplied
  ``notification_id`` row when at least one send landed.

Disabled mode: when ``settings.VAPID_PRIVATE_KEY`` is unset (local dev,
CI), the adapter NOOPs and logs a warning so the dispatcher's push
branch stays graceful rather than crashing the test suite.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Final

import sentry_sdk
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from auxd_api.lib.observability import log_call
from auxd_api.modules.notifications.models import (
    Notification,
    NotificationType,
)
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.notifications.types import TYPES
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.notifications.web_push")

# Dead-subscription HTTP codes. The browser revoked the subscription
# out-of-band; the only correct response is to delete our row so the
# fan-out doesn't keep retrying.
_DEAD_SUBSCRIPTION_CODES: Final[frozenset[int]] = frozenset({404, 410})


def _alert_push_send_failed(
    *,
    user_id: str,
    notif_type: NotificationType,
    endpoint: str,
    error: str,
) -> None:
    """Emit a Sentry warning tagged ``web_push.send_failed``."""
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("subsystem", "notifications")
        scope.set_tag("status", "web_push.send_failed")
        scope.set_extra("user_id", user_id)
        scope.set_extra("type", notif_type.value)
        scope.set_extra("endpoint_host", endpoint.split("/")[2] if "/" in endpoint else endpoint)
        scope.set_extra("error", error)
        sentry_sdk.capture_message("web_push.send_failed", level="warning")


def _click_url_for(
    notif_type: NotificationType,
    payload: dict[str, Any],
    *,
    base_url: str,
) -> str:
    """Build the deep-link URL the OS should open when the push is tapped.

    Per-type routing — values mirror the frontend route map. Defaults to
    ``base_url`` for types without a specific landing surface.
    """
    if notif_type in (
        NotificationType.N004_REVIEW_LIKED,
        NotificationType.N005_REVIEW_REPLY,
    ):
        review_id = payload.get("review_id")
        if review_id:
            return f"{base_url}/review/{review_id}"
    if notif_type in (
        NotificationType.N001_FOLLOW_NEW,
        NotificationType.N002_FOLLOW_REQUEST_PENDING,
        NotificationType.N003_FOLLOW_REQUEST_APPROVED,
    ):
        actor_handle = payload.get("actor_handle")
        if actor_handle:
            return f"{base_url}/@{actor_handle}"
    if notif_type in (
        NotificationType.N006_FRIEND_LOGGED_ALBUM,
        NotificationType.N007_FRIEND_HIGH_RATED,
    ):
        album_id = payload.get("album_id")
        if album_id:
            return f"{base_url}/album/{album_id}"
    return base_url


def _title_for(notif_type: NotificationType, payload: dict[str, Any]) -> str:
    """Build the push title — short, scannable copy keyed by type."""
    actor_display = payload.get("actor_display_name") or payload.get("actor_handle") or ""
    if notif_type is NotificationType.N001_FOLLOW_NEW:
        return f"{actor_display} followed you"
    if notif_type is NotificationType.N002_FOLLOW_REQUEST_PENDING:
        return f"{actor_display} wants to follow you"
    if notif_type is NotificationType.N015_SYSTEM_ANNOUNCEMENT:
        return str(payload.get("title", "auxd"))
    return "auxd"


def _build_payload(
    *,
    notif_type: NotificationType,
    payload: dict[str, Any],
    base_url: str,
) -> dict[str, Any]:
    """Build the JSON payload the service worker receives + renders."""
    spec = TYPES.get(notif_type)
    body_template = spec.push_body if spec is not None else None
    body = body_template.format(**payload) if body_template is not None else ""
    return {
        "title": _title_for(notif_type, payload),
        "body": body,
        "click_url": _click_url_for(notif_type, payload, base_url=base_url),
        "type": notif_type.value,
        # ``tag`` lets the OS coalesce same-type pushes — only the latest
        # is shown in the system tray.
        "tag": notif_type.value,
    }


def _webpush_sync(
    *,
    subscription_info: dict[str, Any],
    data: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
) -> Any:
    """Blocking pywebpush call. Wrapped in :func:`asyncio.to_thread`."""
    return webpush(
        subscription_info=subscription_info,
        data=data,
        vapid_private_key=vapid_private_key,
        vapid_claims=dict(vapid_claims),
    )


class WebPushAdapter:
    """VAPID-signed Web Push channel adapter."""

    channel: str = "push"

    async def send(
        self,
        *,
        user_id: str,
        type: NotificationType,  # noqa: A002 — Protocol param name
        payload: dict[str, Any],
        actor_id: str | None = None,
        coalesced_count: int = 0,
        notification_id: str | None = None,
    ) -> Notification | None:
        """Fan a push out to every subscription registered for ``user_id``.

        Returns the updated :class:`Notification` row with
        ``dispatch.push_sent_at`` stamped when at least one send landed.
        Returns ``None`` when push is disabled (no VAPID private key),
        when the user has no subscriptions, or when every send failed.
        """
        _ = coalesced_count
        _ = actor_id

        settings = get_settings()
        if settings.VAPID_PRIVATE_KEY is None:
            _LOGGER.warning(
                "notifications.push.disabled",
                extra={
                    "event": "notifications.push.disabled",
                    "type": type.value,
                    "user_id": user_id,
                },
            )
            return None

        # Push types that resolve to no body should NOOP — defense in depth.
        spec = TYPES.get(type)
        if spec is None or spec.push_body is None:
            _LOGGER.info(
                "notifications.push.noop_no_body",
                extra={
                    "event": "notifications.push.noop_no_body",
                    "type": type.value,
                },
            )
            return None

        subscriptions = await PushSubscription.find(
            PushSubscription.user_id == user_id,
        ).to_list()
        if not subscriptions:
            return None

        wire_payload = _build_payload(
            notif_type=type, payload=payload, base_url=settings.PUBLIC_APP_URL
        )
        data = json.dumps(wire_payload)
        vapid_claims = {"sub": settings.VAPID_SUBJECT}

        sent_count = 0
        dead_subscription_ids: list[str] = []
        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_secret},
            }
            try:
                await asyncio.to_thread(
                    _webpush_sync,
                    subscription_info=subscription_info,
                    data=data,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
                sent_count += 1
                # Refresh last_used_at so dormant subscriptions don't
                # accumulate stale timestamps.
                sub.last_used_at = datetime.now(UTC)
                await sub.save()
            except WebPushException as exc:
                response_status = (
                    exc.response.status_code if getattr(exc, "response", None) else None
                )
                if response_status in _DEAD_SUBSCRIPTION_CODES:
                    dead_subscription_ids.append(sub.id)
                    _LOGGER.info(
                        "notifications.push.subscription_dead",
                        extra={
                            "event": "notifications.push.subscription_dead",
                            "type": type.value,
                            "user_id": user_id,
                            "subscription_id": sub.id,
                            "status_code": response_status,
                        },
                    )
                else:
                    _alert_push_send_failed(
                        user_id=user_id,
                        notif_type=type,
                        endpoint=sub.endpoint,
                        error=str(exc),
                    )
                    log_call(
                        provider="web_push",
                        endpoint="send",
                        latency_ms=0.0,
                        status="failed",
                        extra={
                            "user_id": user_id,
                            "type": type.value,
                            "status_code": response_status,
                            "error": str(exc),
                        },
                    )
            except Exception as exc:  # noqa: BLE001 — swallow per send-and-forget contract
                _alert_push_send_failed(
                    user_id=user_id,
                    notif_type=type,
                    endpoint=sub.endpoint,
                    error=str(exc),
                )
                log_call(
                    provider="web_push",
                    endpoint="send",
                    latency_ms=0.0,
                    status="failed",
                    extra={
                        "user_id": user_id,
                        "type": type.value,
                        "error": str(exc),
                    },
                )

        # Clean up revoked subscriptions.
        for sub_id in dead_subscription_ids:
            try:
                row = await PushSubscription.find_one(PushSubscription.id == sub_id)
                if row is not None:
                    await row.delete()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "notifications.push.dead_subscription_delete_failed",
                    extra={
                        "event": "notifications.push.dead_subscription_delete_failed",
                        "subscription_id": sub_id,
                        "error": str(exc),
                    },
                )

        if sent_count == 0:
            return None

        log_call(
            provider="web_push",
            endpoint="send",
            latency_ms=0.0,
            status="ok",
            extra={
                "user_id": user_id,
                "type": type.value,
                "sent_count": sent_count,
                "dead_count": len(dead_subscription_ids),
            },
        )

        if notification_id is not None:
            notif = await Notification.find_one(Notification.id == notification_id)
            if notif is not None:
                notif.dispatch.push_sent_at = datetime.now(UTC)
                await notif.save()
                return notif
        return None


__all__ = ["WebPushAdapter"]
