"""Integration tests for the email-change + password-change endpoints (T150).

Exercises:

* ``POST /api/v1/users/me/email`` — change email after re-auth; bumps
  ``session_version``; rejects on duplicate / wrong password.
* ``POST /api/v1/users/me/password`` — change password after re-auth;
  bumps ``session_version``; dispatches N-017; enforces the same
  weak-password policy as signup.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.auth.password import hash_password, verify_password
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.users import routes as users_routes
from auxd_api.modules.users.models import User
from auxd_api.modules.users.routes import router as users_router
from tests.integration._auth_helpers import FakeAuthMiddleware


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "DISCOGS_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(users_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str, *, password: str = "correct-horse-battery-1") -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash=hash_password(password),
        display_name=handle.capitalize(),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await User.delete_all()
    yield
    await User.delete_all()


@pytest.fixture
def _capture_dispatches(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    async def _fake_dispatch(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(users_routes, "dispatch_notification", _fake_dispatch)
    return captured


# ---------------------------------------------------------------------------
# Email change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_change_happy_path(_clean_env: None, _clean_db: None) -> None:
    """Valid email + correct current password updates the row and bumps session_version."""
    pw = "correct-horse-battery-1"
    user = _make_user("user-alice", "alice", password=pw)
    await user.insert()
    initial_version = user.session_version

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/email",
        json={"new_email": "Alice2@Example.com", "current_password": pw},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "alice2@example.com"
    assert body["session_version"] == initial_version + 1

    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.email == "alice2@example.com"
    assert refreshed.session_version == initial_version + 1


@pytest.mark.asyncio
async def test_email_change_wrong_current_password(_clean_env: None, _clean_db: None) -> None:
    """Wrong current_password returns 422 with invalid_credentials."""
    user = _make_user("user-alice", "alice", password="correct-horse-battery-1")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/email",
        json={"new_email": "alice2@example.com", "current_password": "wrong-password"},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "invalid_credentials"
    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.email == "alice@example.com"


@pytest.mark.asyncio
async def test_email_change_duplicate_email_returns_409(_clean_env: None, _clean_db: None) -> None:
    """Cannot change to an email that is already registered."""
    pw = "correct-horse-battery-1"
    alice = _make_user("user-alice", "alice", password=pw)
    bob = _make_user("user-bob", "bob", password=pw)
    await alice.insert()
    await bob.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/email",
        json={"new_email": bob.email, "current_password": pw},
        headers={"X-User-Id": alice.id},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "duplicate_email"


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_change_happy_path(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """Valid current+new password updates the hash, bumps session_version, dispatches N-017."""
    old_pw = "correct-horse-battery-1"
    user = _make_user("user-alice", "alice", password=old_pw)
    await user.insert()
    initial_version = user.session_version

    new_pw = "another-correct-horse-9"
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": old_pw, "new_password": new_pw},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_version"] == initial_version + 1

    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.password_hash is not None
    assert verify_password(new_pw, refreshed.password_hash) is True
    assert verify_password(old_pw, refreshed.password_hash) is False
    assert refreshed.session_version == initial_version + 1

    # N-017 dispatched.
    assert len(_capture_dispatches) == 1
    call = _capture_dispatches[0]
    assert call["user_id"] == user.id
    assert call["type"] is NotificationType.N017_SECURITY_PASSWORD_CHANGED
    assert "changed_at_iso" in call["payload"]


@pytest.mark.asyncio
async def test_password_change_wrong_current_password(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """Wrong current_password returns 422; nothing is mutated."""
    user = _make_user("user-alice", "alice", password="correct-horse-battery-1")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "wrong-pass-12", "new_password": "totally-fresh-99"},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "invalid_credentials"
    assert _capture_dispatches == []


@pytest.mark.asyncio
async def test_password_change_too_short_returns_422(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """The 12-char minimum is enforced at the wire level."""
    pw = "correct-horse-battery-1"
    user = _make_user("user-alice", "alice", password=pw)
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": pw, "new_password": "short1!"},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 422, response.text
    assert _capture_dispatches == []


@pytest.mark.asyncio
async def test_password_change_missing_letter_returns_422(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """All-digit passwords pass the min_length but fail the letter rule."""
    pw = "correct-horse-battery-1"
    user = _make_user("user-alice", "alice", password=pw)
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": pw, "new_password": "1234567890123"},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "weak_password"
    assert _capture_dispatches == []


# ---------------------------------------------------------------------------
# Auth + rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_email_requires_session(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/email",
        json={"new_email": "x@example.com", "current_password": "x"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_session(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "x", "new_password": "x" * 12},
    )
    assert response.status_code == 401
