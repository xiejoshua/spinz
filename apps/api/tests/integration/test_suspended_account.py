"""Integration tests for the suspended-account UX flow (T159).

Covers the :class:`SessionMiddleware` short-circuit when
``User.status == SUSPENDED``:

* Suspended user → 403 with ``error: "account_suspended"`` on the
  default endpoint.
* Suspended user → still allowed to hit the allow-listed paths
  (logout, delete-account, GET /me probe).
* Active user → no 403; control endpoints respond normally.
* ``DELETION_PENDING`` status → still no 403 (different lifecycle path).
* The 403 body carries an ``appeal_url``.
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
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.users.models import User, UserStatus
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
async def _clean_db() -> AsyncIterator[None]:
    await User.delete_all()
    yield
    await User.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    return app


_SIGNUP_PAYLOAD = {
    "email": "suspended@example.com",
    "password": "correct-horse-battery-staple-9",
    "handle": "suspended_user",
    "display_name": "Suspended",
}


def _sign_up(client: TestClient) -> tuple[str, str]:
    response = client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("auxd_csrf")
    assert csrf is not None
    return response.json()["id"], csrf


@pytest.mark.asyncio
async def test_suspended_user_403s_on_default_endpoint(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    user = await User.get(user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await user.save()

    # Any non-allow-listed authenticated POST should now 403 with the
    # canonical body. Use the handle-change endpoint as a representative
    # state-changing route.
    response = client.post(
        "/api/v1/users/me/handle",
        json={"new_handle": "new_handle"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["error"] == "account_suspended"
    assert "appeal_url" in body
    assert body["appeal_url"].startswith("mailto:")


@pytest.mark.asyncio
async def test_suspended_user_can_still_logout(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    user = await User.get(user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await user.save()

    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"signed_out": True}


@pytest.mark.asyncio
async def test_suspended_user_can_still_schedule_deletion(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    user = await User.get(user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await user.save()

    response = client.post(
        "/api/v1/users/me/delete",
        headers={"X-CSRF-Token": csrf},
    )
    # The delete-schedule endpoint sets status to DELETION_PENDING, but
    # the middleware allow-list ensures the call goes through even
    # while the user is still SUSPENDED at request time. Once the
    # status transitions, the user is no longer subject to the 403
    # short-circuit on subsequent requests (different status path).
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_active_user_unaffected(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    # No status change — ACTIVE by default. PATCH /users/me always
    # works for an active user; the route returns 200 with the updated
    # display_name. The relevant assertion is "no account_suspended
    # 403 body", not a specific endpoint outcome.
    response = client.patch(
        "/api/v1/users/me",
        json={"display_name": "Renamed"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    assert "account_suspended" not in response.text
    _ = user_id


@pytest.mark.asyncio
async def test_deletion_pending_user_not_suspended(_clean_env: None, _clean_db: None) -> None:
    """``DELETION_PENDING`` is a separate status — no 403 short-circuit."""
    client = TestClient(_make_app())
    user_id, csrf = _sign_up(client)
    user = await User.get(user_id)
    assert user is not None
    user.status = UserStatus.DELETION_PENDING
    await user.save()

    response = client.post(
        "/api/v1/users/me/delete",
        headers={"X-CSRF-Token": csrf},
    )
    # Should hit the route itself (200), not the suspended-account 403.
    assert response.status_code == 200, response.text
