"""Per-type notification registry (T137).

Single source of truth for every active :class:`NotificationType` value at
MVP. For each type the registry pins:

* ``required_payload_keys`` — caller-supplied dict keys validated up-front
  by :func:`validate_payload` so a typo in a producer never lands as a
  half-rendered notification in the inbox.
* ``default_in_app`` / ``default_email`` / ``default_push`` — the
  per-channel default ON/OFF mirroring the taxonomy table in
  ``features/001-auxd-mvp/product-spec/notification-taxonomy.md``. The
  :func:`is_notifiable` predicate (see :mod:`dispatcher`) falls back to
  these when the user's ``NotificationPreferences`` dict has no explicit
  toggle for the type.
* Copy templates per channel — ``in_app_copy``, ``email_subject``,
  ``email_preheader``, ``push_body``. Each is a plain ``str.format()``
  template at MVP; the T135 email adapter will swap email fields out for
  Jinja-rendered HTML next session. Push bodies are length-capped at 120
  chars by spec (notification-taxonomy.md §Push).

The 16 active types are exactly the members of :class:`NotificationType`.
Reserved-gap slots (N-009/N-010/N-011/N-018) are NOT registered here —
the enum doesn't include them, so the parametrised assertion that
``set(TYPES.keys()) == set(NotificationType)`` defends against future
drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auxd_api.modules.notifications.models import NotificationType


@dataclass(frozen=True, slots=True)
class NotificationTypeSpec:
    """Spec for one notification type — what the dispatcher needs to know.

    Defaults declared here mirror notification-taxonomy.md exactly. The
    dispatcher reads them via :func:`is_notifiable` when the user has no
    explicit preference for the (type, channel) pair.
    """

    type: NotificationType
    required_payload_keys: tuple[str, ...]
    default_in_app: bool
    default_email: bool
    default_push: bool
    in_app_copy: str
    email_subject: str | None  # None when channel default OFF + no template needed
    email_preheader: str | None
    push_body: str | None  # <=120 chars per push spec


# ---------------------------------------------------------------------------
# Registry — the 16 active types
# ---------------------------------------------------------------------------
#
# Ordering follows notification-taxonomy.md so a reviewer can diff the file
# against the spec table top-to-bottom. Default flags mirror the table cells
# verbatim; copy text is the dispatcher's first-cut at MVP and can be
# refined by the T135 email-template work without changing this shape.

TYPES: dict[NotificationType, NotificationTypeSpec] = {
    NotificationType.N001_FOLLOW_NEW: NotificationTypeSpec(
        type=NotificationType.N001_FOLLOW_NEW,
        required_payload_keys=("actor_handle", "actor_display_name"),
        default_in_app=True,
        default_email=False,
        default_push=True,
        in_app_copy="{actor_display_name} (@{actor_handle}) followed you.",
        email_subject=None,
        email_preheader=None,
        push_body="{actor_display_name} followed you on auxd.",
    ),
    NotificationType.N002_FOLLOW_REQUEST_PENDING: NotificationTypeSpec(
        type=NotificationType.N002_FOLLOW_REQUEST_PENDING,
        required_payload_keys=("actor_handle", "actor_display_name"),
        default_in_app=True,
        default_email=False,
        default_push=True,
        in_app_copy="{actor_display_name} (@{actor_handle}) wants to follow you.",
        email_subject=None,
        email_preheader=None,
        push_body="{actor_display_name} wants to follow you.",
    ),
    NotificationType.N003_FOLLOW_REQUEST_APPROVED: NotificationTypeSpec(
        type=NotificationType.N003_FOLLOW_REQUEST_APPROVED,
        required_payload_keys=("actor_handle",),
        default_in_app=True,
        default_email=False,
        default_push=False,
        in_app_copy="@{actor_handle} approved your follow request.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N004_REVIEW_LIKED: NotificationTypeSpec(
        type=NotificationType.N004_REVIEW_LIKED,
        required_payload_keys=("actor_handle", "review_id", "album_title"),
        default_in_app=True,
        default_email=False,
        default_push=False,
        in_app_copy="@{actor_handle} liked your review of {album_title}.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N005_REVIEW_REPLY: NotificationTypeSpec(
        # v2-reserved: spec exists for forward compat, but no MVP producer
        # writes this. Integration test asserts the dispatcher honours the
        # registry shape even for v2-reserved entries.
        type=NotificationType.N005_REVIEW_REPLY,
        required_payload_keys=("actor_handle", "review_id"),
        default_in_app=True,
        default_email=False,
        default_push=False,
        in_app_copy="@{actor_handle} replied to your review.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N006_FRIEND_LOGGED_ALBUM: NotificationTypeSpec(
        type=NotificationType.N006_FRIEND_LOGGED_ALBUM,
        required_payload_keys=("actor_handle", "album_title", "album_id"),
        default_in_app=True,
        default_email=False,
        default_push=False,
        in_app_copy="@{actor_handle} logged {album_title} from your Up Next.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N007_FRIEND_HIGH_RATED: NotificationTypeSpec(
        # Opt-in everywhere; defaults OFF on all three channels.
        type=NotificationType.N007_FRIEND_HIGH_RATED,
        required_payload_keys=("actor_handle", "album_title", "rating"),
        default_in_app=False,
        default_email=False,
        default_push=False,
        in_app_copy="@{actor_handle} rated {album_title} {rating}/5.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N008_WEEKLY_DIGEST: NotificationTypeSpec(
        # Email-primary surface; the in-app + push channels are off.
        type=NotificationType.N008_WEEKLY_DIGEST,
        required_payload_keys=("summary_url", "hero_count"),
        default_in_app=False,
        default_email=True,
        default_push=False,
        in_app_copy="Your weekly digest is ready.",
        email_subject="Your week on auxd",
        email_preheader="{hero_count} highlights from your follow graph",
        push_body=None,
    ),
    NotificationType.N009_IMPORT_COMPLETED: NotificationTypeSpec(
        # CR-001: import flows DEFERRED-TO-V2; the enum slot is retained
        # to keep parametrised tests honest. Defaults are OFF on every
        # channel so an accidental dispatch is suppressed.
        type=NotificationType.N009_IMPORT_COMPLETED,
        required_payload_keys=(),
        default_in_app=False,
        default_email=False,
        default_push=False,
        in_app_copy="Your import has completed.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N010_IMPORT_FAILED: NotificationTypeSpec(
        # CR-001 DEFERRED-TO-V2 — see N009 note.
        type=NotificationType.N010_IMPORT_FAILED,
        required_payload_keys=(),
        default_in_app=False,
        default_email=False,
        default_push=False,
        in_app_copy="Your import did not complete.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N012_REPORT_ACKNOWLEDGED: NotificationTypeSpec(
        type=NotificationType.N012_REPORT_ACKNOWLEDGED,
        required_payload_keys=("report_id",),
        default_in_app=True,
        default_email=False,
        default_push=False,
        in_app_copy="A report you filed has been reviewed.",
        email_subject=None,
        email_preheader=None,
        push_body=None,
    ),
    NotificationType.N013_ACCOUNT_DELETION_SCHEDULED: NotificationTypeSpec(
        type=NotificationType.N013_ACCOUNT_DELETION_SCHEDULED,
        required_payload_keys=("scheduled_for_iso",),
        default_in_app=True,
        default_email=True,
        default_push=False,
        in_app_copy="Your account is scheduled for deletion on {scheduled_for_iso}.",
        email_subject="Your auxd account is scheduled for deletion",
        email_preheader="Deletion scheduled for {scheduled_for_iso}. Cancel anytime.",
        push_body=None,
    ),
    NotificationType.N014_ACCOUNT_DELETION_REMINDER_7D: NotificationTypeSpec(
        type=NotificationType.N014_ACCOUNT_DELETION_REMINDER_7D,
        required_payload_keys=("scheduled_for_iso",),
        default_in_app=True,
        default_email=True,
        default_push=False,
        in_app_copy="Your account will be deleted in 7 days ({scheduled_for_iso}).",
        email_subject="Your auxd account will be deleted in 7 days",
        email_preheader="Cancel deletion before {scheduled_for_iso}.",
        push_body=None,
    ),
    NotificationType.N015_SYSTEM_ANNOUNCEMENT: NotificationTypeSpec(
        # Opt-in everywhere.
        type=NotificationType.N015_SYSTEM_ANNOUNCEMENT,
        required_payload_keys=("title", "body", "link"),
        default_in_app=False,
        default_email=False,
        default_push=False,
        in_app_copy="{title}",
        email_subject="{title}",
        email_preheader="{body}",
        push_body="{title}",
    ),
    NotificationType.N016_SECURITY_NEW_SESSION: NotificationTypeSpec(
        # Email channel is LOCKED ON regardless of user pref — see
        # :mod:`dispatcher`.is_notifiable for the lock enforcement.
        type=NotificationType.N016_SECURITY_NEW_SESSION,
        required_payload_keys=("device", "ip", "location"),
        default_in_app=True,
        default_email=True,
        default_push=False,
        in_app_copy="New sign-in from {device} ({location}).",
        email_subject="New sign-in to your auxd account",
        email_preheader="From {device} at {location}",
        push_body=None,
    ),
    NotificationType.N017_SECURITY_PASSWORD_CHANGED: NotificationTypeSpec(
        # Email channel LOCKED ON — see N016 note.
        type=NotificationType.N017_SECURITY_PASSWORD_CHANGED,
        required_payload_keys=("changed_at_iso",),
        default_in_app=True,
        default_email=True,
        default_push=False,
        in_app_copy="Your password was changed at {changed_at_iso}.",
        email_subject="Your auxd password was changed",
        email_preheader="Changed at {changed_at_iso}",
        push_body=None,
    ),
}


# Security types that ignore the email-channel preference — the email
# channel is LOCKED ON for these regardless of user opt-out. Taxonomy doc:
# "Always-on (cannot disable email channel)" for N-016 and "Always-on
# email" for N-017.
EMAIL_LOCKED_TYPES: frozenset[NotificationType] = frozenset(
    {
        NotificationType.N016_SECURITY_NEW_SESSION,
        NotificationType.N017_SECURITY_PASSWORD_CHANGED,
    }
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_payload(notif_type: NotificationType, payload: dict[str, Any]) -> None:
    """Raise :class:`ValueError` if ``payload`` is missing required keys.

    The dispatcher (T131) calls this before any channel work so a producer
    bug surfaces at dispatch-time with a clear message rather than as a
    half-rendered template downstream.
    """
    spec = TYPES.get(notif_type)
    if spec is None:
        raise ValueError(f"unknown notification type: {notif_type!r}")
    missing = [k for k in spec.required_payload_keys if k not in payload]
    if missing:
        raise ValueError(f"payload for {notif_type.value} is missing required keys: {missing}")


def get_spec(notif_type: NotificationType) -> NotificationTypeSpec:
    """Return the :class:`NotificationTypeSpec` for ``notif_type`` or raise."""
    spec = TYPES.get(notif_type)
    if spec is None:
        raise ValueError(f"unknown notification type: {notif_type!r}")
    return spec


def render_in_app(notif_type: NotificationType, payload: dict[str, Any]) -> str:
    """Render the in-app copy for ``notif_type`` using ``payload``.

    Missing format keys raise :class:`KeyError` from ``str.format`` —
    :func:`validate_payload` guards against this, but the raise is
    intentional for any caller that bypasses validation.
    """
    return get_spec(notif_type).in_app_copy.format(**payload)


__all__ = [
    "EMAIL_LOCKED_TYPES",
    "NotificationTypeSpec",
    "TYPES",
    "get_spec",
    "render_in_app",
    "validate_payload",
]
