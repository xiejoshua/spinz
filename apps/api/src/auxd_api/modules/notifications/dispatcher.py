"""Notification dispatcher core (T131 + T132 + T142 + T144 wiring).

Single entry point for every producer that wants to surface something to
a user. Per plan §8.1 the flow is:

    event source
        |
        v
    dispatch(user_id, type, payload, actor_id=..., follow_source=...)
        |
        v
    [T142] critic-seed N-001 onboarding suppression
        |
        v
    [T132] is_notifiable(user, type, channel) per channel
        |
        v
    [T133] coalescer.allow_dispatch(...) -> send | coalesce | drop
        |
        v
    fan out to registered adapters in parallel (asyncio.gather)
        |
        v
    [T144] emit notification.dispatched PostHog event

The dispatcher is INTERNAL — it does NOT register a FastAPI route. It is
invoked from other modules' services (social.follow → N-001, reviews →
N-004 once those producers land in later sessions).

T144 measurement contract: every dispatch — send, coalesce, drop, or
suppressed — emits a single ``notification.dispatched`` PostHog event so
the operator dashboard "notification rate per user per week" (alert at
p95 > 12 events/user/week, excluding weekly.digest) can be built on a
stable schema. See ``posthog_dashboard.yml`` in this module for the
descriptive config.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sentry_sdk

from auxd_api.lib.observability import emit_event
from auxd_api.modules.notifications import coalescer as coalescer_module
from auxd_api.modules.notifications.adapters import get_adapter
from auxd_api.modules.notifications.coalescer import CoalesceDecision
from auxd_api.modules.notifications.models import Notification, NotificationType
from auxd_api.modules.notifications.types import (
    EMAIL_LOCKED_TYPES,
    TYPES,
    validate_payload,
)
from auxd_api.modules.social.models import Block
from auxd_api.modules.users.models import User, UserStatus

_LOGGER = logging.getLogger("auxd.notifications.dispatcher")

# Suppressed-via-onboarding follow source — see T142 / NT-1. When a Follow
# is created with this source, it represents the critic-seed onboarding
# wave (every new user pre-follows the seed accounts) and N-001 dispatch
# is silently dropped so seed accounts don't get a notification storm.
ONBOARDING_PRESELECTED_SOURCE = "onboarding_preselected"

CHANNELS: tuple[str, ...] = ("in_app", "email", "push")


# ---------------------------------------------------------------------------
# Per-channel decision value object (T132).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChannelDecision:
    """Outcome of :func:`is_notifiable` for one ``(user, type, channel)``.

    Attributes:
        channel: ``"in_app"``, ``"email"``, or ``"push"``.
        allowed: ``True`` if the dispatcher should attempt this channel.
        reason: Short tag explaining a suppression. Populated only when
            ``allowed`` is ``False``; otherwise ``None``. Values used:
            ``"user_status"``, ``"blocked"``, ``"user_pref_off"``,
            ``"channel_default_off"``, ``"quiet_hours"``.
    """

    channel: str
    allowed: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _channel_default(notif_type: NotificationType, channel: str) -> bool:
    """Look up the per-channel default from the type registry."""
    spec = TYPES.get(notif_type)
    if spec is None:
        # Unknown type — be conservative (off) so a bad producer can't
        # accidentally light up every channel. validate_payload upstream
        # would normally have raised before we got here.
        return False
    if channel == "in_app":
        return spec.default_in_app
    if channel == "email":
        return spec.default_email
    if channel == "push":
        return spec.default_push
    return False


def _quiet_hours_active(user: User, now: datetime) -> bool:
    """Return ``True`` if ``now`` falls inside the user's quiet-hours window.

    The user's quiet-hours start/end are expressed as ``datetime.time``
    objects in ``user.quiet_hours_tz``. Both wrap-around (start < end —
    e.g. 13:00–17:00) and overnight (start > end — e.g. 22:00–08:00)
    windows are supported. Equal start + end (no window configured)
    returns ``False``.
    """
    start = user.quiet_hours_start
    end = user.quiet_hours_end
    if start is None or end is None:
        return False
    try:
        tz = ZoneInfo(user.quiet_hours_tz)
    except (ZoneInfoNotFoundError, ValueError):
        # Bad TZ string on the user row — treat as no quiet hours rather
        # than crashing the dispatcher. The settings UI validates IANA
        # tz strings on write; this branch is defensive.
        return False
    local_now = now.astimezone(tz).time()
    if start == end:
        return False
    if start < end:
        return start <= local_now < end
    # Overnight window: e.g. 22:00–08:00 → active if now >= 22:00 OR now < 08:00.
    return local_now >= start or local_now < end


async def _user_is_blocked(blocker_id: str, blocked_id: str) -> bool:
    """Return ``True`` if ``blocker_id`` has blocked ``blocked_id``.

    Used by :func:`is_notifiable` to suppress notifications from a user
    that the recipient blocked. Direction-sensitive: only the
    recipient → actor direction matters here (a notification *from* a
    user the recipient blocked should not fire).
    """
    existing = await Block.find_one(
        Block.blocker_id == blocker_id,
        Block.blockee_id == blocked_id,
    )
    return existing is not None


# ---------------------------------------------------------------------------
# T132 — is_notifiable predicate.
# ---------------------------------------------------------------------------


async def is_notifiable(
    user: User,
    notif_type: NotificationType,
    channel: str,
    *,
    actor_id: str | None = None,
    now: datetime | None = None,
) -> ChannelDecision:
    """Return the per-channel dispatch decision for ``(user, type, channel)``.

    Decision precedence (any one suppresses):
        1. ``user.status != ACTIVE`` — entire account is dark.
        2. ``actor_id`` is blocked by ``user``.
        3. Security types N-016 / N-017 on email channel are LOCKED ON
           — user preference is ignored. (Taxonomy doc: "Always-on
           (cannot disable email channel)".)
        4. Explicit per-channel pref dict — if the key is present, use it.
        5. Channel default from the type registry.
        6. Quiet hours on the push channel only — taxonomy NT-3 carves
           out email and in-app from quiet-hours suppression.

    Args:
        user: The recipient :class:`User` document.
        notif_type: Type from the taxonomy.
        channel: ``"in_app"`` | ``"email"`` | ``"push"``.
        actor_id: Optional KSUID of the originator — used for the block
            check. ``None`` for system notifications.
        now: Optional override for the current time (UTC, tz-aware). Used
            by tests to exercise quiet-hours math deterministically.

    Returns:
        :class:`ChannelDecision` with ``allowed`` + a short suppression
        ``reason`` when applicable.
    """
    if user.status is not UserStatus.ACTIVE:
        return ChannelDecision(channel=channel, allowed=False, reason="user_status")

    if actor_id is not None and await _user_is_blocked(user.id, actor_id):
        return ChannelDecision(channel=channel, allowed=False, reason="blocked")

    # Security-types email lock — defended ahead of pref lookup so a
    # user's accidental opt-out can't break audit-trail notifications.
    if channel == "email" and notif_type in EMAIL_LOCKED_TYPES:
        # Locked on; still check quiet hours? No — taxonomy NT-3:
        # email/digest bypasses quiet hours. Return allowed unconditionally.
        return ChannelDecision(channel=channel, allowed=True)

    # Explicit user pref lookup. Pref dicts on the User sub-doc are
    # keyed by the canonical type *string value* — see
    # ``NotificationPreferencesSubDoc``.
    prefs = user.notification_preferences
    pref_dict: dict[str, bool]
    if channel == "in_app":
        pref_dict = prefs.in_app
    elif channel == "email":
        pref_dict = prefs.email
    elif channel == "push":
        pref_dict = prefs.push
    else:
        # Unknown channel — be conservative (off).
        return ChannelDecision(
            channel=channel,
            allowed=False,
            reason="channel_default_off",
        )

    type_key = notif_type.value
    if type_key in pref_dict:
        if not pref_dict[type_key]:
            return ChannelDecision(channel=channel, allowed=False, reason="user_pref_off")
        # Pref says ON — fall through to the quiet-hours guard.
    else:
        if not _channel_default(notif_type, channel):
            return ChannelDecision(channel=channel, allowed=False, reason="channel_default_off")
        # Default says ON — fall through to the quiet-hours guard.

    # Quiet hours apply to push only (NT-3: email + digest bypass).
    if channel == "push":
        now_utc = now if now is not None else datetime.now(UTC)
        if _quiet_hours_active(user, now_utc):
            return ChannelDecision(channel=channel, allowed=False, reason="quiet_hours")

    return ChannelDecision(channel=channel, allowed=True)


# ---------------------------------------------------------------------------
# T131 — dispatch entry point.
# ---------------------------------------------------------------------------


async def _run_adapter(
    channel: str,
    *,
    user_id: str,
    notif_type: NotificationType,
    payload: dict[str, Any],
    actor_id: str | None,
    coalesced_count: int,
) -> Notification | None:
    """Invoke the channel adapter if one is registered.

    Wrapped here so the dispatcher's ``asyncio.gather`` can pass a clean
    awaitable per channel and so unknown channels (registry miss)
    silently produce ``None`` rather than raising.
    """
    adapter = get_adapter(channel)
    if adapter is None:
        return None
    return await adapter.send(
        user_id=user_id,
        type=notif_type,
        payload=payload,
        actor_id=actor_id,
        coalesced_count=coalesced_count,
    )


def _emit_dispatched(
    *,
    user_id: str,
    actor_id: str | None,
    notif_type: NotificationType,
    decision: str,
    channels: list[str],
) -> None:
    """Emit the unified ``notification.dispatched`` PostHog event (T144).

    Fires on EVERY path — send, coalesce, drop, or suppressed — so the
    rates dashboard ("notification rate per user per week", alert at
    p95 > 12 excluding weekly.digest) can be built on a single event
    schema. Channels list is empty for suppressed/drop paths.
    """
    emit_event(
        user_id=user_id,
        event="notification.dispatched",
        properties={
            "recipient_id": user_id,
            "actor_id": actor_id,
            "type": notif_type.value,
            "decision": decision,
            "channels": channels,
        },
    )


async def dispatch(
    *,
    user_id: str,
    type: NotificationType,  # noqa: A002 — public API mirrors plan §8
    payload: dict[str, Any],
    actor_id: str | None = None,
    follow_source: str | None = None,
) -> Notification | None:
    """Dispatch a notification through the full chain.

    Returns the persisted :class:`Notification` on a successful in-app
    write, or ``None`` for every suppression / drop / unknown-recipient
    path. The return value is best-effort: even on success the in-app
    row is the only Document write that happens at MVP — email + push
    adapters are not registered until T135/T136.

    The function NEVER raises into the caller. Exceptions inside the
    chain are absorbed:

    * Recipient validation failures log a warning and return ``None``.
    * Adapter exceptions are gathered with ``return_exceptions=True`` so
      one bad adapter doesn't poison the others.
    * Any catch-all unexpected exception fires a Sentry alert with tag
      ``notification.dispatcher_failed`` and returns ``None``.

    Args:
        user_id: Recipient KSUID.
        type: Notification type from the taxonomy.
        payload: Type-specific payload dict. Validated via
            :func:`validate_payload` before any channel work.
        actor_id: Optional originator KSUID. ``None`` for system
            notifications.
        follow_source: Only meaningful for ``N-001 follow.new``. When the
            originating ``Follow.source == "onboarding_preselected"``
            (the critic-seed onboarding wave per NT-1 / T142), N-001 is
            suppressed without any DB write.
    """
    try:
        return await _dispatch_inner(
            user_id=user_id,
            notif_type=type,
            payload=payload,
            actor_id=actor_id,
            follow_source=follow_source,
        )
    except Exception as exc:  # noqa: BLE001 — defensive catch-all per docstring
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("subsystem", "notifications")
            scope.set_tag("status", "dispatcher_failed")
            scope.set_extra("user_id", user_id)
            scope.set_extra("type", type.value)
            scope.set_extra("error", str(exc))
            sentry_sdk.capture_message("notification.dispatcher_failed", level="error")
        _LOGGER.exception(
            "notification.dispatch_failed",
            extra={
                "event": "notification.dispatch_failed",
                "recipient_id": user_id,
                "type": type.value,
            },
        )
        return None


async def _dispatch_inner(
    *,
    user_id: str,
    notif_type: NotificationType,
    payload: dict[str, Any],
    actor_id: str | None,
    follow_source: str | None,
) -> Notification | None:
    """Inner implementation. Wrapped by :func:`dispatch` for crash safety."""

    # Validate payload up-front so a producer typo surfaces here, not later.
    validate_payload(notif_type, payload)

    # T142 — suppress N-001 follow.new for the critic-seed onboarding wave.
    # The Follow row is still written upstream; we just don't notify.
    if (
        notif_type is NotificationType.N001_FOLLOW_NEW
        and follow_source == ONBOARDING_PRESELECTED_SOURCE
    ):
        _LOGGER.info(
            "notification.suppressed_onboarding_preselected",
            extra={
                "event": "notification.suppressed_onboarding",
                "recipient_id": user_id,
                "actor_id": actor_id,
                "type": notif_type.value,
            },
        )
        _emit_dispatched(
            user_id=user_id,
            actor_id=actor_id,
            notif_type=notif_type,
            decision="suppressed",
            channels=[],
        )
        return None

    # Lift the recipient. Missing or inactive users are silently skipped.
    user = await User.find_one(User.id == user_id)
    if user is None:
        _LOGGER.warning(
            "notification.recipient_missing",
            extra={
                "event": "notification.recipient_missing",
                "recipient_id": user_id,
                "type": notif_type.value,
            },
        )
        _emit_dispatched(
            user_id=user_id,
            actor_id=actor_id,
            notif_type=notif_type,
            decision="suppressed",
            channels=[],
        )
        return None

    # Resolve per-channel decisions.
    allowed_channels: list[str] = []
    for channel in CHANNELS:
        decision = await is_notifiable(user, notif_type, channel, actor_id=actor_id)
        if decision.allowed:
            allowed_channels.append(channel)
        else:
            _LOGGER.info(
                "notification.channel_suppressed",
                extra={
                    "event": "notification.channel_suppressed",
                    "recipient_id": user_id,
                    "type": notif_type.value,
                    "channel": channel,
                    "reason": decision.reason,
                },
            )

    if not allowed_channels:
        _emit_dispatched(
            user_id=user_id,
            actor_id=actor_id,
            notif_type=notif_type,
            decision="suppressed",
            channels=[],
        )
        return None

    # Coalescer / dedup gate. ``target_id`` is folded into dedup; we read
    # it from the payload under common keys without making the dispatcher
    # care about per-type schema (validate_payload already guarded shape).
    target_id_value = (
        payload.get("review_id") or payload.get("album_id") or payload.get("report_id")
    )
    target_id_str: str | None = str(target_id_value) if target_id_value is not None else None

    coalesce_decision: CoalesceDecision = await coalescer_module.allow_dispatch(
        user_id=user_id,
        actor_id=actor_id,
        notif_type=notif_type,
        target_id=target_id_str,
    )

    if coalesce_decision.verdict == "drop":
        _LOGGER.info(
            "notification.dedup_dropped",
            extra={
                "event": "notification.dedup_dropped",
                "recipient_id": user_id,
                "actor_id": actor_id,
                "type": notif_type.value,
            },
        )
        _emit_dispatched(
            user_id=user_id,
            actor_id=actor_id,
            notif_type=notif_type,
            decision="drop",
            channels=[],
        )
        return None

    if coalesce_decision.verdict == "coalesce":
        # Write a single in-app rollup row tagged with coalesced_count.
        # Email/push are NOT fanned out for coalesced rows — the user
        # already has the prior rows, this is the "X new updates today"
        # placeholder. TODO(T133-followup): a sweep job should attach
        # this coalesced row's id back onto the children via
        # ChannelDispatchState.coalesced_into — out of scope this PR.
        rollup_payload = dict(payload)
        rollup_payload["coalesced_from"] = [notif_type.value]
        adapter = get_adapter("in_app")
        notif: Notification | None = None
        if adapter is not None and "in_app" in allowed_channels:
            try:
                notif = await adapter.send(
                    user_id=user_id,
                    type=notif_type,
                    payload=rollup_payload,
                    actor_id=actor_id,
                    coalesced_count=1,
                )
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception(
                    "notification.adapter_failed",
                    extra={
                        "event": "notification.adapter_failed",
                        "channel": "in_app",
                        "recipient_id": user_id,
                        "type": notif_type.value,
                        "error": str(exc),
                    },
                )
        _emit_dispatched(
            user_id=user_id,
            actor_id=actor_id,
            notif_type=notif_type,
            decision="coalesce",
            channels=["in_app"] if "in_app" in allowed_channels else [],
        )
        return notif

    # send verdict — fan out to enabled adapters in parallel.
    awaitables = [
        _run_adapter(
            channel,
            user_id=user_id,
            notif_type=notif_type,
            payload=payload,
            actor_id=actor_id,
            coalesced_count=0,
        )
        for channel in allowed_channels
    ]
    results = await asyncio.gather(*awaitables, return_exceptions=True)

    fanned_out: list[str] = []
    in_app_notif: Notification | None = None
    for channel, result in zip(allowed_channels, results, strict=True):
        if isinstance(result, BaseException):
            _LOGGER.exception(
                "notification.adapter_failed",
                extra={
                    "event": "notification.adapter_failed",
                    "channel": channel,
                    "recipient_id": user_id,
                    "type": notif_type.value,
                    "error": str(result),
                },
            )
            continue
        if result is None:
            # Adapter not registered yet (email/push at MVP). Channel was
            # allowed, but there's no live wire — that's expected during
            # the staged rollout. Don't count it.
            continue
        fanned_out.append(channel)
        if channel == "in_app":
            in_app_notif = result

    _emit_dispatched(
        user_id=user_id,
        actor_id=actor_id,
        notif_type=notif_type,
        decision="send",
        channels=fanned_out,
    )
    return in_app_notif


# Re-export the test-only helper for callers that want to inject a fake
# datetime into the quiet-hours math without going through the public
# is_notifiable signature.
def _build_quiet_hours_datetime(
    *,
    tz_name: str,
    hour: int,
    minute: int = 0,
    on_date: datetime | None = None,
) -> datetime:
    """Test helper: produce a tz-aware datetime in ``tz_name`` at ``hour:minute``.

    Convenience so the integration tests can express times relative to a
    user's local timezone without hand-rolling :class:`ZoneInfo`
    arithmetic.
    """
    tz = ZoneInfo(tz_name)
    base = on_date or datetime.now(UTC)
    local = base.astimezone(tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(UTC)


# Trivial re-exports used by lib/observability documentation.
_QUIET_HOURS_PLACEHOLDER = time(0, 0)  # pragma: no cover — referenced by docs
_QUIET_HOURS_DAY = timedelta(days=1)  # pragma: no cover


__all__ = [
    "CHANNELS",
    "ChannelDecision",
    "ONBOARDING_PRESELECTED_SOURCE",
    "dispatch",
    "is_notifiable",
]
