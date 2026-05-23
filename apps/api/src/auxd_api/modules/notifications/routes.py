"""Notifications HTTP routes (T136 + T139 + T140).

Endpoints (all mounted under ``/api/v1`` via :mod:`auxd_api.routers.v1`):

Push subscription (T136) — pre-existing:
* ``POST /users/me/push-subscriptions`` — register / refresh a Web Push
  subscription. Idempotent on ``endpoint``.
* ``DELETE /users/me/push-subscriptions/{subscription_id}`` — owner-only
  delete.

Inbox surface (T140):
* ``GET /notifications`` — paginated current-user inbox by ``created_at``
  DESC. Actor display fields are denormalised onto each row so the UI
  doesn't N+1 lookup.
* ``GET /notifications/unread-count`` — cheap badge-poll endpoint.
* ``POST /notifications/{notification_id}/read`` — mark one row read
  (idempotent; owner-only).
* ``POST /notifications/mark-all-read`` — bulk mark every unread row.

Preferences (T139):
* ``GET /users/me/notification-preferences`` — returns the embedded
  pref subdoc + quiet-hours fields flattened into a nested ``quiet_hours``
  object.
* ``PUT /users/me/notification-preferences`` — replace prefs + quiet
  hours. Locks the email channel ON for N-016 / N-017 (security types);
  validates that quiet-hours start/end are set when ``enabled`` is true
  and that the timezone is a valid IANA name.

Rate limits (T020) — picked per call frequency:
* push-subscription POST/DELETE: per-user 10/min (browser cadence).
* notifications list: per-user 60/min (polled by the UI).
* unread-count: per-user 120/min (badge poll).
* mark-read single: per-user 60/min.
* mark-all-read: per-user 10/min (bulk op).
* prefs GET: per-user 30/min.
* prefs PUT: per-user 10/min.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import UTC, datetime, time
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.notifications.models import (
    Notification,
    NotificationPreferences,
    NotificationType,
)
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.notifications.types import EMAIL_LOCKED_TYPES
from auxd_api.modules.users.models import NotificationPreferencesSubDoc, User

_LOGGER = logging.getLogger("auxd.notifications.routes")

router = APIRouter(tags=["notifications"])


_PUSH_RATE_LIMIT = rate_limit(
    endpoint="notifications.push_subscription",
    per_user=RateLimit(limit=10, window_seconds=60),
)
_LIST_RATE_LIMIT = rate_limit(
    endpoint="notifications.list",
    per_user=RateLimit(limit=60, window_seconds=60),
)
_UNREAD_COUNT_RATE_LIMIT = rate_limit(
    endpoint="notifications.unread_count",
    per_user=RateLimit(limit=120, window_seconds=60),
)
_MARK_READ_RATE_LIMIT = rate_limit(
    endpoint="notifications.mark_read",
    per_user=RateLimit(limit=60, window_seconds=60),
)
_MARK_ALL_READ_RATE_LIMIT = rate_limit(
    endpoint="notifications.mark_all_read",
    per_user=RateLimit(limit=10, window_seconds=60),
)
_PREFS_GET_RATE_LIMIT = rate_limit(
    endpoint="notifications.prefs_get",
    per_user=RateLimit(limit=30, window_seconds=60),
)
_PREFS_PUT_RATE_LIMIT = rate_limit(
    endpoint="notifications.prefs_put",
    per_user=RateLimit(limit=10, window_seconds=60),
)


# Bound on list page size — picked to match the diary list endpoint default.
_DEFAULT_LIST_LIMIT = 20
_MAX_LIST_LIMIT = 50


def _require_session(request: Request) -> Session:
    """Lift the authenticated session off ``request.state`` or 401."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# ---------------------------------------------------------------------------
# Push subscription endpoints (T136)
# ---------------------------------------------------------------------------


class _PushKeys(BaseModel):
    """Inner ``keys`` block of the browser PushSubscription JSON shape."""

    p256dh: str = Field(..., min_length=1, max_length=512)
    auth: str = Field(..., min_length=1, max_length=128)


class _PushSubscriptionRequest(BaseModel):
    """Wire shape mirrors the browser PushSubscription.toJSON() output."""

    endpoint: str = Field(..., min_length=1, max_length=2048)
    keys: _PushKeys


class _PushSubscriptionResponse(BaseModel):
    """Slim response — id + endpoint suffice for the client cache."""

    id: str
    endpoint: str
    created: bool


@router.post(
    "/users/me/push-subscriptions",
    dependencies=[Depends(_PUSH_RATE_LIMIT)],
    response_model=_PushSubscriptionResponse,
)
async def register_push_subscription(
    request: Request,
    payload: _PushSubscriptionRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> _PushSubscriptionResponse:
    """Register a new Web Push subscription for the authenticated user.

    Idempotent on ``endpoint``: if a row with the same endpoint exists,
    its ``last_used_at`` is refreshed and the row is returned with
    ``created=False``.
    """
    existing = await PushSubscription.find_one(PushSubscription.endpoint == payload.endpoint)
    user_agent = request.headers.get("user-agent")

    if existing is not None:
        existing.user_id = session.user_id
        existing.p256dh_key = payload.keys.p256dh
        existing.auth_secret = payload.keys.auth
        existing.user_agent = user_agent
        existing.last_used_at = datetime.now(UTC)
        await existing.save()
        return _PushSubscriptionResponse(id=existing.id, endpoint=existing.endpoint, created=False)

    fresh = PushSubscription(
        user_id=session.user_id,
        endpoint=payload.endpoint,
        p256dh_key=payload.keys.p256dh,
        auth_secret=payload.keys.auth,
        user_agent=user_agent,
        last_used_at=datetime.now(UTC),
    )
    await fresh.insert()
    return _PushSubscriptionResponse(id=fresh.id, endpoint=fresh.endpoint, created=True)


@router.delete(
    "/users/me/push-subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_PUSH_RATE_LIMIT)],
)
async def delete_push_subscription(
    subscription_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> Response:
    """Owner-only delete of a registered push subscription."""
    sub = await PushSubscription.find_one(PushSubscription.id == subscription_id)
    if sub is None or sub.user_id != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="push_subscription_not_found",
        )
    await sub.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Inbox list + unread count + mark-read (T140)
# ---------------------------------------------------------------------------


class _NotificationOut(BaseModel):
    """One row in the inbox list response.

    Mirrors :class:`Notification` plus the actor display fields denormalised
    so the UI doesn't N+1 lookup the actor on every card. ``coalesced_count``
    surfaces the rollup counter the in-app adapter stashes in payload.
    """

    id: str
    type: str
    payload: dict[str, Any]
    actor_id: str | None
    actor_handle: str | None
    actor_display_name: str | None
    actor_avatar_url: str | None
    read_at: datetime | None
    created_at: datetime
    coalesced_count: int = 0


class _NotificationsListResponse(BaseModel):
    notifications: list[_NotificationOut]
    next_cursor: str | None = None


class _UnreadCountResponse(BaseModel):
    count: int


class _MarkReadResponse(BaseModel):
    ok: bool = True


class _MarkAllReadResponse(BaseModel):
    ok: bool = True
    marked: int = 0


def _encode_cursor(*, created_at: datetime, notification_id: str) -> str:
    """Encode the ``(created_at, _id)`` pair as a single URL-safe token.

    Mirrors the diary list cursor: a JSON ``{c, i}`` payload base64-encoded
    so client tampering produces a malformed cursor (decoded as "no cursor"
    rather than 4xx).
    """
    payload = json.dumps(
        {"c": created_at.isoformat(), "i": notification_id},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """Inverse of :func:`_encode_cursor`. Returns ``None`` on malformed input."""
    padding = "=" * ((4 - len(cursor) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    created_at_raw = payload.get("c")
    notification_id = payload.get("i")
    if not isinstance(created_at_raw, str) or not isinstance(notification_id, str):
        return None
    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at, notification_id


@router.get(
    "/notifications",
    dependencies=[Depends(_LIST_RATE_LIMIT)],
    response_model=_NotificationsListResponse,
)
async def list_notifications(
    session: Annotated[Session, Depends(_require_session)],
    cursor: str | None = None,
    limit: int = Query(default=_DEFAULT_LIST_LIMIT, ge=1, le=_MAX_LIST_LIMIT),
) -> _NotificationsListResponse:
    """Paginated current-user inbox sorted by ``created_at`` DESC.

    Page size is capped at :data:`_MAX_LIST_LIMIT` (50). The cursor is a
    composite ``(created_at, _id)`` token; malformed cursors restart from
    the top of the inbox.
    """
    query: dict[str, Any] = {"user_id": session.user_id}
    if cursor is not None:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            cursor_created_at, cursor_id = decoded
            query["$or"] = [
                {"created_at": {"$lt": cursor_created_at}},
                {"created_at": cursor_created_at, "_id": {"$lt": cursor_id}},
            ]

    rows = await Notification.find(query).sort("-created_at", "-_id").limit(limit + 1).to_list()
    has_more = len(rows) > limit
    rows = rows[:limit]

    # Denormalise actor cards in one batch — at most ``limit`` distinct ids,
    # so the User.find lookup is O(page-size).
    actor_ids = {row.actor_id for row in rows if row.actor_id is not None}
    actors_by_id: dict[str, User] = {}
    if actor_ids:
        actor_rows = await User.find({"_id": {"$in": list(actor_ids)}}).to_list()
        actors_by_id = {actor.id: actor for actor in actor_rows}

    items: list[_NotificationOut] = []
    for row in rows:
        actor = actors_by_id.get(row.actor_id) if row.actor_id is not None else None
        coalesced_raw = row.payload.get("coalesced_count", 0)
        coalesced_count = coalesced_raw if isinstance(coalesced_raw, int) else 0
        items.append(
            _NotificationOut(
                id=row.id,
                type=row.type.value,
                payload=row.payload,
                actor_id=row.actor_id,
                actor_handle=actor.handle if actor is not None else None,
                actor_display_name=actor.display_name if actor is not None else None,
                actor_avatar_url=actor.avatar_url if actor is not None else None,
                read_at=row.read_at,
                created_at=row.created_at,
                coalesced_count=coalesced_count,
            )
        )

    next_cursor: str | None = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(
            created_at=last.created_at,
            notification_id=last.id,
        )

    return _NotificationsListResponse(notifications=items, next_cursor=next_cursor)


@router.get(
    "/notifications/unread-count",
    dependencies=[Depends(_UNREAD_COUNT_RATE_LIMIT)],
    response_model=_UnreadCountResponse,
)
async def get_unread_count(
    session: Annotated[Session, Depends(_require_session)],
) -> _UnreadCountResponse:
    """Return the count of unread notifications for the bell-badge poll."""
    count = await Notification.find({"user_id": session.user_id, "read_at": None}).count()
    return _UnreadCountResponse(count=count)


@router.post(
    "/notifications/{notification_id}/read",
    dependencies=[Depends(_MARK_READ_RATE_LIMIT)],
    response_model=_MarkReadResponse,
)
async def mark_notification_read(
    notification_id: str,
    session: Annotated[Session, Depends(_require_session)],
) -> _MarkReadResponse:
    """Mark a single notification read. Owner-only; idempotent."""
    notif = await Notification.find_one(Notification.id == notification_id)
    if notif is None or notif.user_id != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="notification_not_found",
        )
    if notif.read_at is None:
        notif.read_at = datetime.now(UTC)
        await notif.save()
    return _MarkReadResponse()


@router.post(
    "/notifications/mark-all-read",
    dependencies=[Depends(_MARK_ALL_READ_RATE_LIMIT)],
    response_model=_MarkAllReadResponse,
)
async def mark_all_notifications_read(
    session: Annotated[Session, Depends(_require_session)],
) -> _MarkAllReadResponse:
    """Mark every unread notification for the current user as read."""
    now = datetime.now(UTC)
    result = await Notification.find({"user_id": session.user_id, "read_at": None}).update_many(
        {"$set": {"read_at": now}}
    )
    # Beanie returns the underlying pymongo result; modified_count is the
    # source of truth for "how many rows were just flipped".
    raw_result = getattr(result, "raw_result", None)
    marked = 0
    if isinstance(raw_result, dict):
        modified = raw_result.get("nModified")
        if isinstance(modified, int):
            marked = modified
    if marked == 0:
        modified_attr = getattr(result, "modified_count", None)
        if isinstance(modified_attr, int):
            marked = modified_attr
    return _MarkAllReadResponse(marked=marked)


# ---------------------------------------------------------------------------
# Notification preferences (T139)
# ---------------------------------------------------------------------------


class _QuietHoursIO(BaseModel):
    """Flattened quiet-hours sub-payload for both GET and PUT.

    On disk the user row carries ``quiet_hours_start: time | None``,
    ``quiet_hours_end: time | None``, ``quiet_hours_tz: str`` as three
    separate fields. The route flattens them into one ``quiet_hours``
    object for cleaner UI binding. ``enabled`` is computed on GET as
    ``True`` iff both start AND end are set; on PUT it's the request
    flag, validated against the presence of start/end.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    start: str | None = None  # "HH:MM"
    end: str | None = None  # "HH:MM"
    tz: str = "UTC"


class _PreferencesIO(BaseModel):
    """Wire shape for both GET response and PUT request body.

    ``in_app`` / ``email`` / ``push`` are keyed by the canonical
    :class:`NotificationType` string value (e.g. ``"follow.new"``).
    """

    model_config = ConfigDict(extra="forbid")

    in_app: dict[str, bool] = Field(default_factory=dict)
    email: dict[str, bool] = Field(default_factory=dict)
    push: dict[str, bool] = Field(default_factory=dict)
    weekly_digest: bool = True
    quiet_hours: _QuietHoursIO = Field(default_factory=_QuietHoursIO)

    @field_validator("in_app", "email", "push")
    @classmethod
    def _reject_unknown_type_keys(cls, value: dict[str, bool]) -> dict[str, bool]:
        valid = {member.value for member in NotificationType}
        unknown = [key for key in value if key not in valid]
        if unknown:
            raise ValueError(f"unknown notification type keys: {sorted(unknown)}")
        return value


def _parse_hhmm(raw: str) -> time:
    """Parse ``"HH:MM"`` strings into :class:`datetime.time`."""
    try:
        return time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("quiet_hours times must be HH:MM (24h)") from exc


def _format_hhmm(value: time | None) -> str | None:
    """Inverse of :func:`_parse_hhmm` — emit ``"HH:MM"`` or ``None``."""
    if value is None:
        return None
    return value.strftime("%H:%M")


def _serialize_preferences(user: User) -> _PreferencesIO:
    """Build the response shape from the on-disk User row."""
    prefs = user.notification_preferences
    enabled = user.quiet_hours_start is not None and user.quiet_hours_end is not None
    return _PreferencesIO(
        in_app=dict(prefs.in_app),
        email=dict(prefs.email),
        push=dict(prefs.push),
        weekly_digest=prefs.weekly_digest,
        quiet_hours=_QuietHoursIO(
            enabled=enabled,
            start=_format_hhmm(user.quiet_hours_start),
            end=_format_hhmm(user.quiet_hours_end),
            tz=user.quiet_hours_tz,
        ),
    )


@router.get(
    "/users/me/notification-preferences",
    dependencies=[Depends(_PREFS_GET_RATE_LIMIT)],
    response_model=_PreferencesIO,
)
async def get_notification_preferences(
    session: Annotated[Session, Depends(_require_session)],
) -> _PreferencesIO:
    """Return the current-user's notification preferences + quiet hours."""
    user = await User.find_one(User.id == session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )
    return _serialize_preferences(user)


@router.put(
    "/users/me/notification-preferences",
    dependencies=[Depends(_PREFS_PUT_RATE_LIMIT)],
    response_model=_PreferencesIO,
)
async def put_notification_preferences(
    payload: _PreferencesIO,
    session: Annotated[Session, Depends(_require_session)],
) -> _PreferencesIO:
    """Replace the current-user's notification preferences + quiet hours.

    Validates:

    * ``quiet_hours.enabled=True`` requires both ``start`` and ``end`` set.
    * ``quiet_hours.tz`` must be a valid IANA timezone.
    * Email channel for N-016 / N-017 cannot be turned off (rejects 422
      with ``security_email_locked``).
    """
    user = await User.find_one(User.id == session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )

    # Defend the locked security email channel — rejects an attempt to
    # set False for any locked type.
    for locked_type in EMAIL_LOCKED_TYPES:
        explicit = payload.email.get(locked_type.value)
        if explicit is False:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "security_email_locked",
                    "message": ("Security notifications cannot have email turned off."),
                    "field": "email",
                    "type": locked_type.value,
                },
            )

    # Quiet hours validation: enabled requires both bounds; tz must be IANA.
    qh = payload.quiet_hours
    if qh.enabled and (qh.start is None or qh.end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "quiet_hours_incomplete",
                "message": "Quiet hours require both start and end when enabled.",
                "field": "quiet_hours",
            },
        )
    try:
        ZoneInfo(qh.tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_timezone",
                "message": f"Unknown IANA timezone: {qh.tz}",
                "field": "quiet_hours.tz",
            },
        ) from exc

    parsed_start: time | None = None
    parsed_end: time | None = None
    if qh.enabled and qh.start is not None and qh.end is not None:
        try:
            parsed_start = _parse_hhmm(qh.start)
            parsed_end = _parse_hhmm(qh.end)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "invalid_quiet_hours_format",
                    "message": str(exc),
                    "field": "quiet_hours",
                },
            ) from exc
    elif not qh.enabled:
        # Allow the client to clear the window by setting enabled=False;
        # ignore any start/end the request may still carry.
        parsed_start = None
        parsed_end = None

    # Build a fresh subdoc and persist. The on-disk model has two parallel
    # shapes (NotificationPreferencesSubDoc on User, NotificationPreferences
    # in notifications.models) — both have the same field surface, so a
    # ``model_dump()`` round-trip keeps them in sync.
    new_prefs = NotificationPreferencesSubDoc(
        in_app=payload.in_app,
        email=payload.email,
        push=payload.push,
        weekly_digest=payload.weekly_digest,
        version=user.notification_preferences.version,
    )
    # Defensive cross-check — ensure the structural twin in
    # notifications.models is still parseable from the same fields.
    NotificationPreferences.model_validate(new_prefs.model_dump())

    user.notification_preferences = new_prefs
    user.quiet_hours_start = parsed_start
    user.quiet_hours_end = parsed_end
    user.quiet_hours_tz = qh.tz
    user.updated_at = datetime.now(UTC)
    await user.save()

    return _serialize_preferences(user)


__all__ = ["router"]
