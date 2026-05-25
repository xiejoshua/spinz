"""Integration tests for the email-unverified write gate (002-auth-email-flows).

The :class:`SessionMiddleware` was extended in chunk 3 with an
``email_unverified`` 403 short-circuit. The shape mirrors the
SUSPENDED path:

* Triggers only on state-changing methods (POST/PATCH/PUT/DELETE).
* Allow-lists the verification + resend endpoints, logout, GDPR data-
  export / delete, and the password-reset surface.
* Reads (GET / HEAD / OPTIONS) always pass.
* Anonymous requests are unaffected — the existing CSRF/401 path
  applies first.

This test mounts a small sentinel router with a state-changing POST
endpoint so we don't entangle the assertion with any other route's
business logic. The auth + users routers are also mounted so the
existing allow-listed paths can be exercised.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.auth.tokens_models import EmailVerificationToken
from auxd_api.modules.users.models import HandleRedirect, User
from auxd_api.modules.users.routes import router as users_router


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "AUTH_TOKEN_PEPPER",
        "ENVIRONMENT",
        "RESEND_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await User.delete_all()
    await HandleRedirect.delete_all()
    await EmailVerificationToken.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()
    await EmailVerificationToken.delete_all()


# A sentinel router with one state-changing endpoint we can prod
# without coupling to any production route's input shape. Mounted
# under /api/v1 so the middleware's path-matching sees the same shape
# as a real endpoint.
_sentinel_router = APIRouter(prefix="/sentinel", tags=["sentinel"])


@_sentinel_router.post("/echo")
async def _sentinel_echo() -> dict[str, Any]:
    return {"ok": True}


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(_sentinel_router, prefix="/api/v1")
    return app


_VALID_PAYLOAD = {
    "email": "alice@example.com",
    "password": "correct-horse-battery-staple-9",
    "handle": "alice42",
    "display_name": "Alice",
}


async def _flip_verified(user_id: str, *, verified: bool) -> None:
    """Force the user's verification state via direct DB write."""
    user = await User.get(user_id)
    assert user is not None
    user.email_verified = verified
    user.email_verified_at = datetime.now(UTC) if verified else None
    await user.save()


# ---------------------------------------------------------------------------
# Read methods always pass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_users_me_passes_when_unverified(_clean_env: None, _clean_db: None) -> None:
    """``GET /api/v1/users/me`` works even when the user is unverified."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    # By default the new user is NOT verified.
    response = client.get("/api/v1/users/me")
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Writes 403 when unverified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_changing_route_403s_when_unverified(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None

    response = client.post(
        "/api/v1/sentinel/echo",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["error"] == "email_unverified"
    assert body["resend_endpoint"] == "/api/v1/auth/resend-verification"


# ---------------------------------------------------------------------------
# Allow-listed paths bypass the gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_verification_bypasses_gate_when_unverified(
    _clean_env: None, _clean_db: None
) -> None:
    """POST /auth/resend-verification is allow-listed: must NOT 403."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None

    response = client.post(
        "/api/v1/auth/resend-verification",
        headers={CSRF_HEADER_NAME: csrf},
    )
    # 200 (already verified branch in the route would return ok); here
    # the user is unverified so the resend logic returns the fresh-token
    # branch.
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True


@pytest.mark.asyncio
async def test_logout_bypasses_gate_when_unverified(_clean_env: None, _clean_db: None) -> None:
    """POST /auth/logout is allow-listed so the user can walk away."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None

    response = client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 200, response.text
    # Body contract from logout.
    assert response.json() == {"signed_out": True}


# ---------------------------------------------------------------------------
# Writes pass once verified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_changing_route_passes_after_verification(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    await _flip_verified(user_id, verified=True)

    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post(
        "/api/v1/sentinel/echo",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Anonymous + verify-email path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_post_returns_401_not_email_unverified(
    _clean_env: None, _clean_db: None
) -> None:
    """An anonymous POST never hits the unverified gate.

    The middleware's verification check is keyed off ``request.state
    .session`` — when there's no session, it falls straight through to
    the route, which returns 401 (or whatever the route's auth check
    decides). The new gate must NOT trip on anonymous traffic.
    """
    client = TestClient(_make_app())
    # No prior signup → no session → no CSRF cookie. The route's own
    # auth check returns 401 for /resend-verification (already covered
    # in the verification endpoints suite); the assertion here is just
    # that the body is NOT the ``email_unverified`` 403.
    response = client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 401, response.text
    assert "email_unverified" not in response.text


@pytest.mark.asyncio
async def test_verify_email_bypasses_gate(_clean_env: None, _clean_db: None) -> None:
    """POST /auth/verify-email is allow-listed so the user can complete the flow.

    The exact verification body is exercised in the verify-email suite;
    here we only assert that the path doesn't trip the gate even when
    the caller is an unverified, authenticated user.
    """
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    # Unknown token → route returns 410 (verification_token_invalid).
    # The point of this assertion is that the gate doesn't pre-empt
    # that 410 with a 403.
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": "definitely-not-a-real-token"},
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 410, response.text
    assert "email_unverified" not in response.text


# ---------------------------------------------------------------------------
# Forgot/reset password are allow-listed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_bypasses_gate_when_unverified(
    _clean_env: None, _clean_db: None
) -> None:
    """Forgot-password is anonymous, but an unverified session must also pass through."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": _VALID_PAYLOAD["email"]},
        headers={CSRF_HEADER_NAME: csrf},
    )
    # Always-200 generic body per FR-141.
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
