"""Integration tests for ``POST /api/v1/users/me/handle`` (T057)."""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.users.models import HandleRedirect, User
from auxd_api.modules.users.routes import router as users_router


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def _clean_users() -> AsyncIterator[None]:
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    return app


_VALID_PAYLOAD = {
    "email": "alice@example.com",
    "password": "correct-horse-battery-staple-9",
    "handle": "alice42",
    "display_name": "Alice",
}


def _sign_up(client: TestClient) -> str:
    """Sign up the default test user and return the CSRF token.

    Feature 002-auth-email-flows: the middleware now 403s state-changing
    writes for users with ``email_verified=False``. The async helper
    below flips the freshly-created user to verified so handle-change
    tests can exercise their actual subject without colliding with the
    verification gate.
    """
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("auxd_csrf")
    assert csrf is not None
    return csrf


async def _mark_email_verified(handle: str) -> None:
    """Flip the user identified by ``handle`` to ``email_verified=True``.

    Test-only escape hatch around the feature 002-auth-email-flows
    write-gate. The plan §14 risk register explicitly allows this
    pattern for pre-existing E2E flows that don't exercise the
    verification path.
    """
    user = await User.find_one(User.handle == handle)
    assert user is not None
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await user.save()


async def _force_past_cooldown(handle: str) -> None:
    """Backdate ``handle_created_at`` so the user can change their handle."""
    user = await User.find_one(User.handle == handle)
    assert user is not None
    user.handle_created_at = datetime.now(UTC) - timedelta(days=60)
    await user.save()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_writes_redirect_and_updates_user(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    csrf = _sign_up(client)
    await _mark_email_verified("alice42")
    await _force_past_cooldown("alice42")

    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "alice_canonical"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handle"] == "alice_canonical"
    assert body["handle_changed_at"] is not None
    # The User row reflects the rename.
    persisted = await User.find_one(User.handle == "alice_canonical")
    assert persisted is not None
    assert persisted.handle_changed_at is not None
    # The redirect row is in place.
    redirect = await HandleRedirect.find_one(HandleRedirect.old_handle == "alice42")
    assert redirect is not None
    assert redirect.new_handle == "alice_canonical"
    assert redirect.user_id == persisted.id


# ---------------------------------------------------------------------------
# 429 cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_too_soon_returns_429(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    csrf = _sign_up(client)
    await _mark_email_verified("alice42")
    # Don't backdate — the user just signed up so the cooldown is active.
    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "alice_v2"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["error"] == "handle_change_too_soon"
    assert 1 <= detail["retry_after_days"] <= 30


# ---------------------------------------------------------------------------
# 422 reserved + 422 invalid format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_reserved_returns_422(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    csrf = _sign_up(client)
    await _mark_email_verified("alice42")
    await _force_past_cooldown("alice42")
    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "reserved_handle"


# ---------------------------------------------------------------------------
# 409 already taken
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_already_taken_returns_409(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    csrf = _sign_up(client)
    await _mark_email_verified("alice42")
    await _force_past_cooldown("alice42")
    # Create a second user that already owns the target handle.
    second = User(
        handle="taken_already",
        email="other@example.com",
        display_name="Other",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$abc$def",
    )
    await second.insert()
    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "taken_already"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "duplicate_handle"


# ---------------------------------------------------------------------------
# 401 unauthenticated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_handle_unauthenticated_returns_401(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "anybody"},
    )
    assert response.status_code == 401
