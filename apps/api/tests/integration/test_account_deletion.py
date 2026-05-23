"""Integration tests for ``POST/DELETE /api/v1/users/me/delete`` (T058)."""

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
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
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


def _sign_up(client: TestClient) -> tuple[str, str]:
    """Sign up and return ``(user_id, csrf_token)``."""
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("auxd_csrf")
    assert csrf is not None
    return response.json()["id"], csrf


@pytest.mark.asyncio
async def test_schedule_deletion_sets_fields_and_bumps_session_version(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    response = client.post(
        "/api/v1/users/me/delete",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == UserStatus.DELETION_PENDING.value
    assert body["scheduled_for"] is not None
    persisted = await User.get(user_id)
    assert persisted is not None
    assert persisted.status is UserStatus.DELETION_PENDING
    assert persisted.deletion_scheduled_for is not None
    assert persisted.session_version >= 2


@pytest.mark.asyncio
async def test_cancel_deletion_clears_fields(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    # Schedule then cancel.
    assert client.post("/api/v1/users/me/delete", headers={"X-CSRF-Token": csrf}).status_code == 200
    cancel = client.delete("/api/v1/users/me/delete", headers={"X-CSRF-Token": csrf})
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["status"] == UserStatus.ACTIVE.value
    assert body["scheduled_for"] is None
    persisted = await User.get(user_id)
    assert persisted is not None
    assert persisted.status is UserStatus.ACTIVE
    assert persisted.deletion_scheduled_for is None


@pytest.mark.asyncio
async def test_schedule_deletion_is_idempotent(
    _clean_env: None,
    _clean_users: None,
) -> None:
    from datetime import datetime as _dt

    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    first = client.post("/api/v1/users/me/delete", headers={"X-CSRF-Token": csrf})
    assert first.status_code == 200
    first_schedule = _dt.fromisoformat(first.json()["scheduled_for"])
    second = client.post("/api/v1/users/me/delete", headers={"X-CSRF-Token": csrf})
    assert second.status_code == 200
    second_schedule = _dt.fromisoformat(second.json()["scheduled_for"])
    # BSON storage truncates sub-millisecond precision so we compare at
    # 10ms resolution rather than identity — the idempotent path must
    # not extend the window.
    delta = abs((first_schedule - second_schedule).total_seconds())
    assert delta < 0.01, f"schedules drifted by {delta}s"
    persisted = await User.get(user_id)
    assert persisted is not None
    # session_version bumped exactly once on the first schedule call.
    assert persisted.session_version == 2


@pytest.mark.asyncio
async def test_schedule_deletion_unauthenticated_returns_401(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post("/api/v1/users/me/delete")
    assert response.status_code == 401
    response_del = client.delete("/api/v1/users/me/delete")
    assert response_del.status_code == 401
