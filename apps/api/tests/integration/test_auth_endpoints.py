"""Integration tests for the auth endpoints (T053 + T059).

Drives ``POST /api/v1/auth/signup``, ``POST /api/v1/auth/login``,
``POST /api/v1/auth/logout``, and ``POST /api/v1/auth/logout-all-devices``
through a FastAPI :class:`TestClient` against the mongomock-motor backing
store set up in ``conftest.py``. The SessionMiddleware is mounted live
so the cookie + CSRF round-trip is exercised end-to-end.
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
from auxd_api.lib.sessions import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.users.models import HandleRedirect, User


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


_REQUIRED_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "DISCOGS_API_TOKEN",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
)


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
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
    """Mount the auth router under the prefix the production router uses."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    return app


_VALID_PASSWORD = "correct-horse-battery-staple-9"
_VALID_PAYLOAD = {
    "email": "alice@example.com",
    "password": _VALID_PASSWORD,
    "handle": "alice42",
    "display_name": "Alice",
}


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_happy_path_creates_user_and_issues_session(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["handle"] == "alice42"
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    assert "id" in body
    # The hash MUST NOT appear in the response.
    assert "password_hash" not in body
    # Session cookies emitted.
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{SESSION_COOKIE_NAME}=") for c in cookies)
    assert any(c.startswith(f"{CSRF_COOKIE_NAME}=") for c in cookies)
    # User is persisted.
    persisted = await User.find_one(User.email == "alice@example.com")
    assert persisted is not None
    assert persisted.password_hash is not None
    assert persisted.password_hash != _VALID_PASSWORD


@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_409(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    first = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert first.status_code == 201
    # Clear cookies — the second signup must re-enter the anonymous-POST
    # branch of the middleware (signup is anonymous-only by contract).
    client.cookies.clear()
    payload = {**_VALID_PAYLOAD, "handle": "bob42"}
    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "duplicate_email"


@pytest.mark.asyncio
async def test_signup_duplicate_handle_returns_409(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    first = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert first.status_code == 201
    client.cookies.clear()
    payload = {**_VALID_PAYLOAD, "email": "alice2@example.com"}
    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "duplicate_handle"


@pytest.mark.asyncio
async def test_signup_reserved_handle_returns_422(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    # ``admin`` is in the seed reserved file.
    payload = {**_VALID_PAYLOAD, "handle": "admin"}
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "reserved_handle"


@pytest.mark.asyncio
async def test_signup_weak_password_returns_422(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    # Pydantic catches <12 chars first — returns standard 422 shape.
    short_payload = {**_VALID_PAYLOAD, "password": "tooshort1"}
    short_resp = client.post("/api/v1/auth/signup", json=short_payload)
    assert short_resp.status_code == 422
    # Length-passing but letters-only — the service layer catches it.
    no_digit_payload = {**_VALID_PAYLOAD, "password": "alllowercasenodigit"}
    no_digit_resp = client.post("/api/v1/auth/signup", json=no_digit_payload)
    assert no_digit_resp.status_code == 422
    assert no_digit_resp.json()["detail"]["error"] == "weak_password"


@pytest.mark.asyncio
async def test_signup_invalid_handle_chars_returns_422(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    payload = {**_VALID_PAYLOAD, "handle": "Alice-42"}  # uppercase + dash
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_handle"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_happy_path_issues_session(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    # Clear cookies so we're starting fresh — login should re-issue.
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": _VALID_PAYLOAD["email"], "password": _VALID_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handle"] == "alice42"
    assert "password_hash" not in body
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{SESSION_COOKIE_NAME}=") for c in cookies)


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": _VALID_PAYLOAD["email"], "password": "wrongpassword-123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": _VALID_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Logout (T059)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_clears_cookies(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post("/api/v1/auth/logout", headers={CSRF_HEADER_NAME: csrf})
    assert response.status_code == 200
    # The Set-Cookie headers include the deletion (Max-Age=0).
    cookie_headers = response.headers.get_list("set-cookie")
    assert any(SESSION_COOKIE_NAME in h and "max-age=0" in h.lower() for h in cookie_headers)


@pytest.mark.asyncio
async def test_logout_anonymous_returns_200(
    _clean_env: None,
    _clean_users: None,
) -> None:
    """Anonymous logout is a no-op but still returns 200 for client simplicity."""
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_devices_bumps_session_version(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post(
        "/api/v1/auth/logout-all-devices",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 200
    assert response.json()["session_version"] >= 2
    # The persisted user must agree.
    persisted = await User.get(user_id)
    assert persisted is not None
    assert persisted.session_version >= 2


@pytest.mark.asyncio
async def test_logout_all_devices_unauthenticated_returns_401(
    _clean_env: None,
    _clean_users: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/logout-all-devices")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_signup_password_hash_never_echoed_anywhere(
    _clean_env: None,
    _clean_users: None,
) -> None:
    """Defence-in-depth: the literal password and the hash must not appear in the response body."""
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201
    assert _VALID_PASSWORD not in response.text
    # Argon2 hashes start with ``$argon2``.
    assert "$argon2" not in response.text
