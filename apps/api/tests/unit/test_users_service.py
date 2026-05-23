"""Unit tests for :mod:`auxd_api.modules.users.service` (T057, T058)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from auxd_api.modules.auth.service import (
    DuplicateHandleError,
    InvalidHandleError,
    ReservedHandleError,
)
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
from auxd_api.modules.users.service import (
    ACCOUNT_DELETION_GRACE,
    HandleChangeTooSoonError,
    cancel_account_deletion,
    change_handle,
    schedule_account_deletion,
)


@pytest_asyncio.fixture
async def _clean() -> AsyncIterator[None]:
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()


async def _make_user(
    *,
    handle: str = "alice",
    email: str | None = None,
    handle_created_at: datetime | None = None,
    handle_changed_at: datetime | None = None,
) -> User:
    user = User(
        handle=handle,
        email=email if email is not None else f"{handle}@example.com",
        display_name=handle,
        password_hash="$argon2id$dummy",
    )
    if handle_created_at is not None:
        user.handle_created_at = handle_created_at
    if handle_changed_at is not None:
        user.handle_changed_at = handle_changed_at
    await user.insert()
    return user


# ---------------------------------------------------------------------------
# change_handle policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_blocked_within_cooldown(_clean: None) -> None:
    """A fresh signup is inside the 30-day immutability window."""
    user = await _make_user()
    with pytest.raises(HandleChangeTooSoonError) as excinfo:
        await change_handle(user=user, new_handle="alice_v2")
    assert excinfo.value.retry_after_days >= 1


@pytest.mark.asyncio
async def test_change_handle_allowed_after_cooldown_creates_redirect(_clean: None) -> None:
    """30+ days post-creation, the change succeeds and writes a redirect."""
    user = await _make_user(
        handle_created_at=datetime.now(UTC) - timedelta(days=60),
    )
    result = await change_handle(user=user, new_handle="alice_v2")
    assert result.user.handle == "alice_v2"
    assert result.user.handle_changed_at is not None
    assert result.redirect.old_handle == "alice"
    assert result.redirect.new_handle == "alice_v2"


@pytest.mark.asyncio
async def test_change_handle_uses_last_change_as_cooldown_anchor(_clean: None) -> None:
    """A recent change anchors the cooldown (later than creation)."""
    now = datetime.now(UTC)
    user = await _make_user(
        handle_created_at=now - timedelta(days=400),
        handle_changed_at=now - timedelta(days=5),
    )
    with pytest.raises(HandleChangeTooSoonError):
        await change_handle(user=user, new_handle="alice_v3")


@pytest.mark.asyncio
async def test_change_handle_rejects_reserved(_clean: None) -> None:
    user = await _make_user(handle_created_at=datetime.now(UTC) - timedelta(days=60))
    with pytest.raises(ReservedHandleError):
        await change_handle(user=user, new_handle="admin")


@pytest.mark.asyncio
async def test_change_handle_rejects_invalid_format(_clean: None) -> None:
    user = await _make_user(handle_created_at=datetime.now(UTC) - timedelta(days=60))
    with pytest.raises(InvalidHandleError):
        await change_handle(user=user, new_handle="HasUpper")
    with pytest.raises(InvalidHandleError):
        await change_handle(user=user, new_handle="ab")  # too short


@pytest.mark.asyncio
async def test_change_handle_rejects_duplicate_other_user(_clean: None) -> None:
    user = await _make_user(handle_created_at=datetime.now(UTC) - timedelta(days=60))
    await _make_user(handle="taken", email="t@example.com")
    with pytest.raises(DuplicateHandleError):
        await change_handle(user=user, new_handle="taken")


@pytest.mark.asyncio
async def test_change_handle_rejects_self_handle(_clean: None) -> None:
    """Asking to set the handle to its current value is treated as a conflict."""
    user = await _make_user(handle_created_at=datetime.now(UTC) - timedelta(days=60))
    with pytest.raises(DuplicateHandleError):
        await change_handle(user=user, new_handle="alice")


# ---------------------------------------------------------------------------
# schedule / cancel deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_account_deletion_sets_fields(_clean: None) -> None:
    user = await _make_user()
    state = await schedule_account_deletion(user)
    assert state.status is UserStatus.DELETION_PENDING
    assert state.scheduled_for is not None
    # ~30 days out, within a few seconds of "now + 30d".
    delta = state.scheduled_for - datetime.now(UTC)
    assert ACCOUNT_DELETION_GRACE - timedelta(seconds=5) <= delta <= ACCOUNT_DELETION_GRACE


@pytest.mark.asyncio
async def test_schedule_account_deletion_idempotent(_clean: None) -> None:
    user = await _make_user()
    first = await schedule_account_deletion(user)
    second = await schedule_account_deletion(user)
    # BSON storage truncates sub-millisecond precision on the roundtrip,
    # so we compare to millisecond resolution rather than identity.
    assert first.scheduled_for is not None
    assert second.scheduled_for is not None
    delta = abs((first.scheduled_for - second.scheduled_for).total_seconds())
    assert delta < 0.01, f"schedules drifted by {delta}s"
    # session_version bumped exactly once.
    persisted = await User.get(user.id)
    assert persisted is not None
    assert persisted.session_version == 2


@pytest.mark.asyncio
async def test_cancel_account_deletion_restores_active(_clean: None) -> None:
    user = await _make_user()
    await schedule_account_deletion(user)
    state = await cancel_account_deletion(user)
    assert state.status is UserStatus.ACTIVE
    assert state.scheduled_for is None
    persisted = await User.get(user.id)
    assert persisted is not None
    assert persisted.deletion_scheduled_for is None


@pytest.mark.asyncio
async def test_cancel_account_deletion_noop_on_active(_clean: None) -> None:
    user = await _make_user()
    state = await cancel_account_deletion(user)
    assert state.status is UserStatus.ACTIVE
    assert state.scheduled_for is None
