"""Integration tests for :class:`auxd_api.middleware.SessionMiddleware` (T019).

Builds a self-contained FastAPI app that mounts the middleware plus three
fake routes (login / me / logout) so the full sign-in → call → sign-out
loop required by the T019 Done criterion can be exercised against a real
:class:`TestClient`.

Tests deliberately avoid importing the production ``app`` to keep the
session-middleware behaviour decoupled from the global DB/Redis lifespan.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from auxd_api.middleware import (
    SessionMiddleware,
    clear_session_cookies,
    issue_session,
)


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


_REQUIRED_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "MONGODB_URI",
    "REDIS_URL",
    "SESSION_HMAC_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "SPOTIFY_INTEGRATION_ENABLED",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
)


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("SPOTIFY_INTEGRATION_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _make_app() -> FastAPI:
    """Build a minimal app exercising the session middleware.

    Routes:
        POST /test/login      — issues a session cookie for user ``alice``
        GET  /test/me         — echoes ``request.state.session`` if any
        POST /test/echo       — protected POST (requires CSRF)
        POST /test/logout     — clears the cookies
    """
    app = FastAPI()
    app.add_middleware(SessionMiddleware)

    @app.post("/test/login")
    async def _login() -> Response:
        response = JSONResponse({"signed_in_as": "alice"})
        issue_session(response, user_id="alice", session_version=1)
        return response

    @app.get("/test/me")
    async def _me(request: Request) -> dict[str, str | None]:
        session = getattr(request.state, "session", None)
        return {"user_id": session.user_id if session else None}

    @app.post("/test/echo")
    async def _echo(request: Request) -> dict[str, str]:
        session = getattr(request.state, "session", None)
        return {"user_id": session.user_id if session else "anonymous"}

    @app.post("/test/logout")
    async def _logout() -> Response:
        response = JSONResponse({"signed_out": True})
        clear_session_cookies(response)
        return response

    return app


def test_anonymous_request_has_no_session(_clean_env: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/test/me")
    assert response.status_code == 200
    assert response.json() == {"user_id": None}


def test_sign_in_sets_session_and_csrf_cookies(_clean_env: None) -> None:
    client = TestClient(_make_app())
    response = client.post("/test/login")
    assert response.status_code == 200
    # ``set_cookie`` headers — there must be one for each cookie name.
    cookie_headers = response.headers.get_list("set-cookie")
    assert any(h.startswith(f"{SESSION_COOKIE_NAME}=") for h in cookie_headers)
    assert any(h.startswith(f"{CSRF_COOKIE_NAME}=") for h in cookie_headers)
    # Session cookie must be HttpOnly; CSRF cookie must NOT be HttpOnly.
    session_header = next(h for h in cookie_headers if h.startswith(f"{SESSION_COOKIE_NAME}="))
    csrf_header = next(h for h in cookie_headers if h.startswith(f"{CSRF_COOKIE_NAME}="))
    assert "httponly" in session_header.lower()
    assert "httponly" not in csrf_header.lower()
    assert "samesite=lax" in session_header.lower()


def test_authenticated_get_request_carries_session(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    response = client.get("/test/me")
    assert response.status_code == 200
    assert response.json() == {"user_id": "alice"}


def test_tampered_session_cookie_returns_401(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    original = client.cookies.get(SESSION_COOKIE_NAME) or ""
    body, _sig = original.split(".", 1)
    # Replace the signature with a clearly invalid one. Single-byte flips
    # against a base64 alphabet are too easily nullified by httpx's cookie
    # normalization; this guarantees the HMAC compare fails.
    tampered = f"{body}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    client.cookies.set(SESSION_COOKIE_NAME, tampered)
    response = client.get("/test/me")
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_session"


def test_post_without_csrf_token_returns_403(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    response = client.post("/test/echo")
    assert response.status_code == 403
    assert response.json()["error"] == "csrf_token_invalid"


def test_post_with_mismatched_csrf_token_returns_403(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    response = client.post(
        "/test/echo",
        headers={CSRF_HEADER_NAME: "not-the-cookie-value"},
    )
    assert response.status_code == 403


def test_post_with_matching_csrf_token_succeeds(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post("/test/echo", headers={CSRF_HEADER_NAME: csrf})
    assert response.status_code == 200
    assert response.json() == {"user_id": "alice"}


def test_logout_clears_cookies(_clean_env: None) -> None:
    client = TestClient(_make_app())
    client.post("/test/login")
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post("/test/logout", headers={CSRF_HEADER_NAME: csrf})
    assert response.status_code == 200
    # After logout, the cookies should be unset and subsequent /me reports anonymous.
    me = client.get("/test/me")
    assert me.json() == {"user_id": None}


def test_sign_in_call_logout_round_trip_invalidates_session(_clean_env: None) -> None:
    """The Done criterion verbatim: signs in, calls, signs out, verifies invalidation."""
    client = TestClient(_make_app())
    # 1. Sign in
    login = client.post("/test/login")
    assert login.status_code == 200
    # 2. Authenticated call
    me = client.get("/test/me")
    assert me.json() == {"user_id": "alice"}
    # 3. Sign out (with the CSRF header — protected POST)
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    logout = client.post("/test/logout", headers={CSRF_HEADER_NAME: csrf})
    assert logout.status_code == 200
    # 4. Verify invalidation — next call has no session.
    me_after = client.get("/test/me")
    assert me_after.json() == {"user_id": None}


def test_safe_methods_bypass_csrf(_clean_env: None) -> None:
    """GET / HEAD / OPTIONS never require the CSRF header."""
    client = TestClient(_make_app())
    client.post("/test/login")
    # Authenticated GET with no CSRF header — must succeed.
    response = client.get("/test/me")
    assert response.status_code == 200
