"""Unit tests for :mod:`auxd_api.modules.users.models`.

These tests construct the Pydantic/Beanie ``User`` model directly and
exercise field defaults + validation behaviour. They do **not** touch
MongoDB — integration coverage of the indexes and persistence lives in
T012's connection-test suite.
"""

from __future__ import annotations

import json
import string
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from auxd_api.lib.visibility import Visibility
from auxd_api.modules.users.models import (
    MusicProviderSubDoc,
    NotificationPreferencesSubDoc,
    User,
    UserStatus,
)

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


def _make_user(**overrides: object) -> User:
    """Factory: build a minimal valid User, overriding fields as needed."""
    base: dict[str, object] = {
        "handle": "alice",
        "email": "alice@example.com",
        "display_name": "Alice",
    }
    base.update(overrides)
    return User(**base)


# ---------------------------------------------------------------------------
# ID + schema version
# ---------------------------------------------------------------------------


def test_user_has_ksuid_id_by_default() -> None:
    """A newly constructed User receives a fresh 27-char base62 KSUID."""
    user = _make_user()
    assert isinstance(user.id, str)
    assert len(user.id) == 27
    assert set(user.id).issubset(BASE62_ALPHABET)


def test_schema_version_field() -> None:
    """Constitution P2 — every doc carries _schema_version: int = 1."""
    user = _make_user()
    assert user.schema_version == 1


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


def test_user_handle_required() -> None:
    """Missing ``handle`` raises :class:`ValidationError`."""
    with pytest.raises(ValidationError) as excinfo:
        User(email="bob@example.com", display_name="Bob")
    assert any(err["loc"] == ("handle",) for err in excinfo.value.errors())


def test_user_email_required() -> None:
    """Missing ``email`` raises :class:`ValidationError`."""
    with pytest.raises(ValidationError) as excinfo:
        User(handle="bob", display_name="Bob")
    assert any(err["loc"] == ("email",) for err in excinfo.value.errors())


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_user_defaults() -> None:
    """Default values per spec — feature opt-ins, status, bio, sub-docs."""
    user = _make_user()
    assert user.auto_prompt_enabled is True
    assert user.auto_prompt_push_enabled is False
    assert user.private_profile is False
    assert user.status == UserStatus.ACTIVE
    assert user.bio == ""
    assert user.music_providers == []
    assert user.password_hash is None
    assert user.avatar_url is None
    assert user.deletion_scheduled_for is None
    assert user.last_seen_at is None
    assert user.quiet_hours_start is None
    assert user.quiet_hours_end is None
    assert user.quiet_hours_tz == "UTC"


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


def test_user_status_enum() -> None:
    """``status`` accepts the three valid enum values and rejects junk."""
    assert _make_user(status=UserStatus.ACTIVE).status is UserStatus.ACTIVE
    assert _make_user(status=UserStatus.DELETED).status is UserStatus.DELETED
    assert _make_user(status=UserStatus.SUSPENDED).status is UserStatus.SUSPENDED
    # Wire-format string values are accepted (Pydantic coerces str → Enum).
    assert _make_user(status="active").status is UserStatus.ACTIVE
    with pytest.raises(ValidationError):
        _make_user(status="archived")


# ---------------------------------------------------------------------------
# Embedded sub-documents
# ---------------------------------------------------------------------------


def test_user_with_music_provider() -> None:
    """Music provider sub-doc round-trips through ``model_dump_json``."""
    connected = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)
    provider = MusicProviderSubDoc(
        provider="spotify",
        provider_user_id="spotify-user-123",
        display_name="Alice on Spotify",
        connected_at=connected,
        access_token_encrypted="ciphertext-access",
        refresh_token_encrypted="ciphertext-refresh",
        token_expires_at=datetime(2026, 5, 22, 13, 0, 0, tzinfo=UTC),
        scopes=["user-read-email", "user-read-recently-played"],
    )
    user = _make_user(music_providers=[provider])

    payload = json.loads(user.model_dump_json())
    assert len(payload["music_providers"]) == 1
    serialised = payload["music_providers"][0]
    assert serialised["provider"] == "spotify"
    assert serialised["provider_user_id"] == "spotify-user-123"
    assert serialised["access_token_encrypted"] == "ciphertext-access"
    assert serialised["refresh_token_encrypted"] == "ciphertext-refresh"
    assert serialised["scopes"] == [
        "user-read-email",
        "user-read-recently-played",
    ]


def test_notification_preferences_default() -> None:
    """Default prefs — weekly digest on, per-channel dicts empty."""
    prefs = NotificationPreferencesSubDoc()
    assert prefs.weekly_digest is True
    assert prefs.in_app == {}
    assert prefs.email == {}
    assert prefs.push == {}
    assert prefs.version == 1

    user = _make_user()
    assert user.notification_preferences.weekly_digest is True
    assert user.notification_preferences.in_app == {}
    assert user.notification_preferences.email == {}
    assert user.notification_preferences.push == {}


# ---------------------------------------------------------------------------
# Handle policy fields (FR-029)
# ---------------------------------------------------------------------------


def test_handle_change_tracking_fields() -> None:
    """``handle_created_at`` always set; ``handle_changed_at`` None on a fresh user."""
    before = datetime.now(UTC)
    user = _make_user()
    after = datetime.now(UTC)

    assert user.handle_created_at is not None
    assert user.handle_created_at.tzinfo is not None
    assert before <= user.handle_created_at <= after
    assert user.handle_changed_at is None


# ---------------------------------------------------------------------------
# Visibility defaults + session bookkeeping (US-G1, FR-029)
# ---------------------------------------------------------------------------


def test_visibility_defaults() -> None:
    """Data-model.md §User: public diary, private backlog, opt-in keep-after-log."""
    user = _make_user()
    assert user.default_entry_visibility is Visibility.PUBLIC
    assert user.default_backlog_visibility is Visibility.PRIVATE
    assert user.keep_backlog_after_log is False


def test_session_version_default() -> None:
    """``session_version`` starts at 1; a bump invalidates all prior cookies."""
    user = _make_user()
    assert user.session_version == 1
