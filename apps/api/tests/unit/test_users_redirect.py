"""Unit tests for :mod:`auxd_api.modules.users.redirect` (T060)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from auxd_api.modules.users.models import HandleRedirect, User
from auxd_api.modules.users.redirect import resolve_handle


@pytest_asyncio.fixture
async def _clean() -> AsyncIterator[None]:
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()


async def _make_user(handle: str, email: str | None = None) -> User:
    user = User(
        handle=handle,
        email=email if email is not None else f"{handle}@example.com",
        display_name=handle,
        password_hash="$argon2id$dummy",
    )
    await user.insert()
    return user


@pytest.mark.asyncio
async def test_current_handle_returns_self(_clean: None) -> None:
    user = await _make_user("alice_canonical")
    resolved, canonical = await resolve_handle("alice_canonical")
    assert resolved is not None
    assert resolved.id == user.id
    assert canonical == "alice_canonical"


@pytest.mark.asyncio
async def test_old_handle_returns_redirect_target(_clean: None) -> None:
    user = await _make_user("alice_v2")
    await HandleRedirect(
        old_handle="alice_v1",
        new_handle="alice_v2",
        user_id=user.id,
    ).insert()
    resolved, canonical = await resolve_handle("alice_v1")
    assert resolved is not None
    assert resolved.id == user.id
    # Canonical handle is the user's *current* one, not the redirect's
    # ``new_handle`` field — defends against multiple renames.
    assert canonical == "alice_v2"


@pytest.mark.asyncio
async def test_handle_lookup_is_case_insensitive(_clean: None) -> None:
    """Handles are stored lowercase; resolver must lowercase its input."""
    await _make_user("alice_canonical")
    resolved, canonical = await resolve_handle("Alice_Canonical")
    assert resolved is not None
    assert canonical == "alice_canonical"


@pytest.mark.asyncio
async def test_unknown_handle_returns_none_tuple(_clean: None) -> None:
    resolved, canonical = await resolve_handle("ghost")
    assert resolved is None
    assert canonical is None


@pytest.mark.asyncio
async def test_empty_handle_returns_none_tuple(_clean: None) -> None:
    resolved, canonical = await resolve_handle("")
    assert resolved is None
    assert canonical is None


@pytest.mark.asyncio
async def test_orphan_redirect_returns_none(_clean: None) -> None:
    """If the redirect's user_id no longer exists, treat the handle as unknown."""
    await HandleRedirect(
        old_handle="ghost_v1",
        new_handle="ghost_v2",
        user_id="nonexistent-user-id",
    ).insert()
    resolved, canonical = await resolve_handle("ghost_v1")
    assert resolved is None
    assert canonical is None
