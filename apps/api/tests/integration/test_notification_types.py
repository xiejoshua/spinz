"""Integration tests for the notification type registry (T137).

Covers:

* Every active :class:`NotificationType` enum value has a matching entry
  in :data:`TYPES`.
* Per-channel defaults match the taxonomy table (parametrised over the
  16 types).
* :func:`validate_payload` raises on missing keys and succeeds on a
  complete payload.
* :func:`render_in_app` produces a non-empty string per type using a
  representative payload.
* End-to-end: for each active type, the dispatcher chain accepts a
  stock payload and writes the right Notification fields (uses
  fakeredis to keep the coalescer happy).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import fakeredis.aioredis
import pytest
import pytest_asyncio

from auxd_api import redis_client as redis_module
from auxd_api.modules.notifications.dispatcher import dispatch
from auxd_api.modules.notifications.models import (
    Notification,
    NotificationType,
)
from auxd_api.modules.notifications.types import (
    EMAIL_LOCKED_TYPES,
    TYPES,
    NotificationTypeSpec,
    get_spec,
    render_in_app,
    validate_payload,
)
from auxd_api.modules.users.models import User

# Stock payloads per type — minimum required keys per the registry.
_STOCK_PAYLOADS: dict[NotificationType, dict[str, Any]] = {
    NotificationType.N001_FOLLOW_NEW: {
        "actor_handle": "alice",
        "actor_display_name": "Alice",
    },
    NotificationType.N002_FOLLOW_REQUEST_PENDING: {
        "actor_handle": "alice",
        "actor_display_name": "Alice",
    },
    NotificationType.N003_FOLLOW_REQUEST_APPROVED: {"actor_handle": "alice"},
    NotificationType.N004_REVIEW_LIKED: {
        "actor_handle": "alice",
        "review_id": "rev_abc",
        "album_title": "OK Computer",
    },
    NotificationType.N005_REVIEW_REPLY: {
        "actor_handle": "alice",
        "review_id": "rev_abc",
    },
    NotificationType.N006_FRIEND_LOGGED_ALBUM: {
        "actor_handle": "alice",
        "album_title": "OK Computer",
        "album_id": "alb_abc",
    },
    NotificationType.N007_FRIEND_HIGH_RATED: {
        "actor_handle": "alice",
        "album_title": "OK Computer",
        "rating": 4.5,
    },
    NotificationType.N008_WEEKLY_DIGEST: {
        "summary_url": "https://auxd.fm/d/u1",
        "hero_count": 3,
    },
    NotificationType.N009_IMPORT_COMPLETED: {},
    NotificationType.N010_IMPORT_FAILED: {},
    NotificationType.N012_REPORT_ACKNOWLEDGED: {"report_id": "rep_abc"},
    NotificationType.N013_ACCOUNT_DELETION_SCHEDULED: {"scheduled_for_iso": "2026-07-01T00:00:00Z"},
    NotificationType.N014_ACCOUNT_DELETION_REMINDER_7D: {
        "scheduled_for_iso": "2026-07-01T00:00:00Z"
    },
    NotificationType.N015_SYSTEM_ANNOUNCEMENT: {
        "title": "Welcome",
        "body": "Auxd v1.0 is live.",
        "link": "https://auxd.fm",
    },
    NotificationType.N016_SECURITY_NEW_SESSION: {
        "device": "Chrome on macOS",
        "ip": "203.0.113.5",
        "location": "Brooklyn, NY",
    },
    NotificationType.N017_SECURITY_PASSWORD_CHANGED: {"changed_at_iso": "2026-05-23T12:00:00Z"},
}


# ---------------------------------------------------------------------------
# Registry shape.
# ---------------------------------------------------------------------------


def test_every_notification_type_has_registry_entry() -> None:
    """All 16 active enum members are present in TYPES."""
    assert set(TYPES.keys()) == set(NotificationType)
    assert len(TYPES) == 16


@pytest.mark.parametrize("notif_type", list(NotificationType))
def test_registry_entries_match_taxonomy_defaults(
    notif_type: NotificationType,
) -> None:
    """Defaults per channel match the taxonomy table (parametrised)."""
    expected: dict[NotificationType, tuple[bool, bool, bool]] = {
        # (in_app, email, push)
        NotificationType.N001_FOLLOW_NEW: (True, False, True),
        NotificationType.N002_FOLLOW_REQUEST_PENDING: (True, False, True),
        NotificationType.N003_FOLLOW_REQUEST_APPROVED: (True, False, False),
        NotificationType.N004_REVIEW_LIKED: (True, False, False),
        NotificationType.N005_REVIEW_REPLY: (True, False, False),
        NotificationType.N006_FRIEND_LOGGED_ALBUM: (True, False, False),
        NotificationType.N007_FRIEND_HIGH_RATED: (False, False, False),
        NotificationType.N008_WEEKLY_DIGEST: (False, True, False),
        # CR-001 deferred — defaults off everywhere.
        NotificationType.N009_IMPORT_COMPLETED: (False, False, False),
        NotificationType.N010_IMPORT_FAILED: (False, False, False),
        NotificationType.N012_REPORT_ACKNOWLEDGED: (True, False, False),
        NotificationType.N013_ACCOUNT_DELETION_SCHEDULED: (True, True, False),
        NotificationType.N014_ACCOUNT_DELETION_REMINDER_7D: (True, True, False),
        NotificationType.N015_SYSTEM_ANNOUNCEMENT: (False, False, False),
        NotificationType.N016_SECURITY_NEW_SESSION: (True, True, False),
        NotificationType.N017_SECURITY_PASSWORD_CHANGED: (True, True, False),
    }
    spec = TYPES[notif_type]
    expected_in_app, expected_email, expected_push = expected[notif_type]
    assert spec.default_in_app is expected_in_app
    assert spec.default_email is expected_email
    assert spec.default_push is expected_push


def test_email_locked_types_are_only_n016_n017() -> None:
    """Email lock applies only to the two security types."""
    assert (
        frozenset(
            {
                NotificationType.N016_SECURITY_NEW_SESSION,
                NotificationType.N017_SECURITY_PASSWORD_CHANGED,
            }
        )
        == EMAIL_LOCKED_TYPES
    )


def test_get_spec_returns_correct_entry() -> None:
    spec = get_spec(NotificationType.N001_FOLLOW_NEW)
    assert isinstance(spec, NotificationTypeSpec)
    assert spec.type is NotificationType.N001_FOLLOW_NEW


# ---------------------------------------------------------------------------
# validate_payload.
# ---------------------------------------------------------------------------


def test_validate_payload_raises_on_missing_required() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        validate_payload(NotificationType.N001_FOLLOW_NEW, {"actor_handle": "alice"})


def test_validate_payload_passes_on_complete_payload() -> None:
    validate_payload(
        NotificationType.N001_FOLLOW_NEW,
        {"actor_handle": "alice", "actor_display_name": "Alice"},
    )


def test_validate_payload_passes_for_types_with_no_required_keys() -> None:
    """N-009/N-010 are deferred — empty payload is valid."""
    validate_payload(NotificationType.N009_IMPORT_COMPLETED, {})


# ---------------------------------------------------------------------------
# render_in_app — every type produces a non-empty string.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("notif_type", list(NotificationType))
def test_render_in_app_for_each_type(notif_type: NotificationType) -> None:
    payload = _STOCK_PAYLOADS[notif_type]
    rendered = render_in_app(notif_type, payload)
    assert isinstance(rendered, str)
    assert rendered  # non-empty


# ---------------------------------------------------------------------------
# End-to-end dispatch per type.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module._client = client
    try:
        yield client
    finally:
        await client.aclose()
        redis_module._client = None


@pytest_asyncio.fixture
async def recipient() -> AsyncIterator[User]:
    """A user opted into EVERY type on EVERY channel for the type-parametrised path.

    This is the bluntest opt-in so the dispatcher's only suppression path
    becomes the coalescer (which the fake_redis fixture keeps under-limit).
    """
    user = User(
        handle="typetest",
        email="typetest@example.com",
        display_name="Type Test",
        password_hash="$argon2id$test",
    )
    # Explicitly opt in to every type on every channel.
    for notif_type in NotificationType:
        user.notification_preferences.in_app[notif_type.value] = True
        user.notification_preferences.email[notif_type.value] = True
        user.notification_preferences.push[notif_type.value] = True
    await user.insert()
    yield user
    await user.delete()
    await Notification.delete_all()


# Only test types that have default in_app = True (or are explicitly opted
# in by the fixture) to keep the parametrised assertion simple — we're
# verifying the dispatch chain accepts every type's payload shape, not
# the suppression branches.
_DISPATCHABLE_TYPES = [t for t in NotificationType]


@pytest.mark.parametrize("notif_type", _DISPATCHABLE_TYPES)
@pytest.mark.asyncio
async def test_dispatch_each_type_writes_in_app_row(
    fake_redis: fakeredis.aioredis.FakeRedis,
    recipient: User,
    notif_type: NotificationType,
) -> None:
    """Each active type dispatches end-to-end with its stock payload."""
    payload = _STOCK_PAYLOADS[notif_type]
    result = await dispatch(
        user_id=recipient.id,
        type=notif_type,
        payload=payload,
        actor_id=None,  # bypass per-actor bucket so the test fans out cleanly
    )
    assert result is not None, f"dispatch returned None for {notif_type.value}"
    assert result.type is notif_type
    assert result.user_id == recipient.id
