"""Unit tests for :mod:`auxd_api.modules.notifications.models` and
:mod:`auxd_api.modules.moderation.models` (T026).

Pydantic-level only — Beanie ``Document`` is a ``pydantic.BaseModel``
subclass, so default factories, required-field validation, and
type-coercion all run without spinning up MongoDB.
"""

from __future__ import annotations

import string

import pytest
from pydantic import ValidationError

from auxd_api.modules.moderation.models import (
    REPORT_DETAIL_MAX_LEN,
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.notifications.models import (
    ChannelDispatchState,
    FailedEmail,
    Notification,
    NotificationPreferences,
    NotificationType,
)

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


# ---------------------------------------------------------------------------
# NotificationType
# ---------------------------------------------------------------------------


def test_notification_type_has_18_active_values() -> None:
    """Per ``notification-taxonomy.md``, exactly 18 active types (N-001..N-018)."""
    assert len(list(NotificationType)) == 18


def test_notification_type_string_values_match_taxonomy() -> None:
    """Spot-check canonical taxonomy string values.

    The taxonomy doc is the single source of truth for these identifiers
    — any drift here means the dispatcher (T131), preference UI, and
    analytics tracking plan will all silently disagree.
    """
    # N-004 was renamed twice (review.hearted → review.auxed → review.liked
    # in R3); pin the post-R3 value.
    assert NotificationType.N004_REVIEW_LIKED.value == "review.liked"
    # A handful of others worth pinning explicitly so a typo in the enum
    # name doesn't sneak through.
    assert NotificationType.N001_FOLLOW_NEW.value == "follow.new"
    assert NotificationType.N008_WEEKLY_DIGEST.value == "weekly.digest"
    assert NotificationType.N011_SPOTIFY_RECONNECT_REQUIRED.value == "spotify.reconnect_required"
    assert NotificationType.N018_JUST_FINISHED_PROMPT.value == "just_finished.prompt"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


def test_notification_ksuid_id() -> None:
    """A new ``Notification`` gets an auto-generated 27-char base62 KSUID ``id``."""
    notif = Notification(user_id="user_abc", type=NotificationType.N001_FOLLOW_NEW)
    assert isinstance(notif.id, str)
    assert len(notif.id) == 27
    assert set(notif.id).issubset(BASE62_ALPHABET)
    other = Notification(user_id="user_xyz", type=NotificationType.N001_FOLLOW_NEW)
    assert notif.id != other.id


def test_notification_required_fields() -> None:
    """``user_id`` and ``type`` are both required."""
    with pytest.raises(ValidationError) as exc_info:
        Notification()
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert {"user_id", "type"}.issubset(missing)

    with pytest.raises(ValidationError):
        Notification(user_id="user_abc")
    with pytest.raises(ValidationError):
        Notification(type=NotificationType.N001_FOLLOW_NEW)


def test_notification_payload_default_empty() -> None:
    """``payload`` defaults to an empty dict, not ``None``."""
    notif = Notification(user_id="user_abc", type=NotificationType.N001_FOLLOW_NEW)
    assert notif.payload == {}


def test_notification_actor_id_nullable() -> None:
    """``actor_id`` defaults to ``None`` for system-triggered notifs."""
    notif = Notification(user_id="user_abc", type=NotificationType.N008_WEEKLY_DIGEST)
    assert notif.actor_id is None

    notif_with = Notification(
        user_id="user_abc",
        type=NotificationType.N001_FOLLOW_NEW,
        actor_id="user_def",
    )
    assert notif_with.actor_id == "user_def"


# ---------------------------------------------------------------------------
# ChannelDispatchState
# ---------------------------------------------------------------------------


def test_dispatch_defaults() -> None:
    """All flags/timestamps default to ``False`` / ``None``."""
    dispatch = ChannelDispatchState()
    assert dispatch.in_app_delivered is False
    assert dispatch.in_app_read_at is None
    assert dispatch.email_sent_at is None
    assert dispatch.push_sent_at is None
    assert dispatch.coalesced_into is None


# ---------------------------------------------------------------------------
# NotificationPreferences
# ---------------------------------------------------------------------------


def test_prefs_default_weekly_digest_true() -> None:
    """Weekly digest is opt-out, so the default must be ``True``."""
    prefs = NotificationPreferences()
    assert prefs.weekly_digest is True
    assert prefs.version == 1


def test_prefs_per_channel_dicts_default_empty() -> None:
    """The three per-channel dicts default to empty (missing key == default)."""
    prefs = NotificationPreferences()
    assert prefs.in_app == {}
    assert prefs.email == {}
    assert prefs.push == {}


# ---------------------------------------------------------------------------
# FailedEmail
# ---------------------------------------------------------------------------


def test_failed_email_ksuid_id() -> None:
    """A new ``FailedEmail`` gets a 27-char base62 KSUID ``id``."""
    row = FailedEmail(
        user_id="user_abc",
        notification_type=NotificationType.N008_WEEKLY_DIGEST,
        payload={"subject": "Your week in music"},
        last_error="resend: 5xx after 5 retries",
    )
    assert isinstance(row.id, str)
    assert len(row.id) == 27
    assert set(row.id).issubset(BASE62_ALPHABET)


def test_failed_email_required_fields() -> None:
    """``user_id``, ``notification_type``, ``payload``, ``last_error`` all required."""
    with pytest.raises(ValidationError) as exc_info:
        FailedEmail()
    missing = {err["loc"][0] for err in exc_info.value.errors() if err["type"] == "missing"}
    assert {"user_id", "notification_type", "payload", "last_error"}.issubset(missing)


def test_failed_email_retry_count_default_zero() -> None:
    """``retry_count`` defaults to 0 (write happens after exhaustion; service sets actual count)."""
    row = FailedEmail(
        user_id="user_abc",
        notification_type=NotificationType.N011_SPOTIFY_RECONNECT_REQUIRED,
        payload={},
        last_error="bounce",
    )
    assert row.retry_count == 0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_report_ksuid_id() -> None:
    """A new ``Report`` gets a 27-char base62 KSUID ``id``."""
    report = Report(
        reporter_id="user_abc",
        target_type=ReportTargetType.REVIEW,
        target_id="rev_xyz",
        reason=ReportReason.SPAM,
    )
    assert isinstance(report.id, str)
    assert len(report.id) == 27
    assert set(report.id).issubset(BASE62_ALPHABET)


def test_report_target_type_enum_includes_missing_album() -> None:
    """sync-fix L3-006: catalog-gap reports reuse ``Report`` via ``missing_album``."""
    assert ReportTargetType.MISSING_ALBUM.value == "missing_album"
    assert ReportTargetType.MISSING_ALBUM in set(ReportTargetType)


def test_report_reason_enum_includes_catalog_gap() -> None:
    """``catalog_gap`` reason pairs with the missing_album target type."""
    assert ReportReason.CATALOG_GAP.value == "catalog_gap"
    assert ReportReason.CATALOG_GAP in set(ReportReason)


def test_report_detail_max_2000() -> None:
    """``detail`` accepts exactly 2000 chars; 2001 raises ValidationError."""
    assert REPORT_DETAIL_MAX_LEN == 2000

    # 2000 chars OK.
    report = Report(
        reporter_id="user_abc",
        target_type=ReportTargetType.REVIEW,
        target_id="rev_xyz",
        reason=ReportReason.HARASSMENT,
        detail="x" * 2000,
    )
    assert len(report.detail) == 2000

    # 2001 chars rejected.
    with pytest.raises(ValidationError):
        Report(
            reporter_id="user_abc",
            target_type=ReportTargetType.REVIEW,
            target_id="rev_xyz",
            reason=ReportReason.HARASSMENT,
            detail="x" * 2001,
        )


def test_report_status_default_open() -> None:
    """New reports default to ``OPEN`` — the daily aggregator only scans these."""
    report = Report(
        reporter_id="user_abc",
        target_type=ReportTargetType.USER,
        target_id="user_def",
        reason=ReportReason.HARASSMENT,
    )
    assert report.status is ReportStatus.OPEN


def test_report_reporter_id_nullable() -> None:
    """``reporter_id`` is nullable so GDPR erasure can blank it (FR-019)."""
    report = Report(
        reporter_id=None,
        target_type=ReportTargetType.USER,
        target_id="user_def",
        reason=ReportReason.HARASSMENT,
    )
    assert report.reporter_id is None
