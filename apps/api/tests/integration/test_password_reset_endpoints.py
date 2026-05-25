"""Integration tests for forgot-password + reset-password (002-auth-email-flows).

Covers ``POST /api/v1/auth/forgot-password`` and ``POST /api/v1/auth/
reset-password`` end-to-end through the :class:`SessionMiddleware`-mounted
TestClient. The forgot-password surface always returns the same generic
200 body regardless of input (no enumeration); structural assertions
check whether a token actually got written to the DB instead of relying
on response bodies to leak the outcome.

Token-introspection pattern
===========================
Same approach as :mod:`tests.integration.test_email_verification_endpoints`
— monkeypatch :data:`password_reset.generate_token` with a stub that
captures the raw token while still calling the real :func:`hash_token`.
The lookup path in :func:`consume_reset_token` re-hashes the inbound raw
and looks up by hash, so deterministic raws round-trip cleanly.
"""

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
from auxd_api.lib import auth_tokens as auth_tokens_lib
from auxd_api.lib.sessions import SESSION_COOKIE_NAME
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth import password_reset as password_reset_module
from auxd_api.modules.auth import routes as auth_routes_module
from auxd_api.modules.auth.password import hash_password, verify_password
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.auth.tokens_models import PasswordResetToken
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
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
    await PasswordResetToken.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()
    await PasswordResetToken.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    return app


_VALID_PASSWORD = "correct-horse-battery-staple-9"
_VALID_PAYLOAD = {
    "email": "alice@example.com",
    "password": _VALID_PASSWORD,
    "handle": "alice42",
    "display_name": "Alice",
}


class _ResetTokenSpy:
    """Capture every raw reset token issued via the password_reset module."""

    def __init__(self) -> None:
        self.captured: list[str] = []

    def __call__(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(32)
        token_hash = auth_tokens_lib.hash_token(raw)
        self.captured.append(raw)
        return raw, token_hash


@pytest.fixture
def _reset_token_spy(monkeypatch: pytest.MonkeyPatch) -> _ResetTokenSpy:
    """Spy on generate_token within the password_reset module."""
    spy = _ResetTokenSpy()
    monkeypatch.setattr(password_reset_module, "generate_token", spy)
    return spy


@pytest.fixture
def _capture_notification_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    """Capture ``dispatch_notification`` invocations from the auth.routes module.

    Mirrors the pattern in :mod:`tests.integration.test_account_settings_endpoints`.
    """
    captured: list[dict[str, Any]] = []

    async def _fake_dispatch(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(auth_routes_module, "dispatch_notification", _fake_dispatch)
    return captured


async def _signup_and_verify(client: TestClient) -> User:
    """Sign up a user and flip them to verified directly in the DB.

    Most reset tests need a verified, ACTIVE user — go straight to the
    end-state without round-tripping through the full verification flow.
    The reset path doesn't care about ``email_verified_at`` precision.
    """
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    user = await User.find_one(User.email == _VALID_PAYLOAD["email"])
    assert user is not None
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await user.save()
    return user


# ---------------------------------------------------------------------------
# Forgot-password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_happy_path_issues_token(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    # Generic body — exposed regardless of outcome.
    assert "If that email is registered" in body["message"]

    # Exactly one unused PasswordResetToken now exists for this user.
    tokens = await PasswordResetToken.find(PasswordResetToken.user_id == user.id).to_list()
    assert len(tokens) == 1, tokens
    assert tokens[0].used_at is None
    assert len(_reset_token_spy.captured) == 1


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_no_token_created(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    """Generic 200 + no token row — the timing-leak fake-hash branch is exercised internally."""
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@example.com"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    # No matching user → no token row anywhere in the collection.
    tokens = await PasswordResetToken.find_all().to_list()
    assert tokens == []
    assert _reset_token_spy.captured == []


@pytest.mark.asyncio
async def test_forgot_password_unverified_email_silent_skip(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    """An unverified-email user → FR-120 silent skip, no token issued."""
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201
    # User exists but ``email_verified=False`` (the signup default).
    client.cookies.clear()
    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": _VALID_PAYLOAD["email"]},
    )
    assert forgot.status_code == 200, forgot.text
    tokens = await PasswordResetToken.find_all().to_list()
    assert tokens == []
    assert _reset_token_spy.captured == []


@pytest.mark.asyncio
async def test_forgot_password_suspended_user_silent_skip(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    # Move the user to SUSPENDED — reset path should skip silently.
    user.status = UserStatus.SUSPENDED
    await user.save()
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert response.status_code == 200
    tokens = await PasswordResetToken.find_all().to_list()
    assert tokens == []
    assert _reset_token_spy.captured == []


@pytest.mark.asyncio
async def test_forgot_password_deletion_pending_silent_skip(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    user.status = UserStatus.DELETION_PENDING
    user.deletion_scheduled_for = datetime.now(UTC) + timedelta(days=30)
    await user.save()
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert response.status_code == 200
    tokens = await PasswordResetToken.find_all().to_list()
    assert tokens == []
    assert _reset_token_spy.captured == []


@pytest.mark.asyncio
async def test_forgot_password_invalidates_prior_unused_token(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    """Two consecutive happy-path requests leave one unused + one used token."""
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()

    first = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert first.status_code == 200
    second = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert second.status_code == 200

    tokens = await PasswordResetToken.find(PasswordResetToken.user_id == user.id).to_list()
    assert len(tokens) == 2, tokens
    used = [t for t in tokens if t.used_at is not None]
    unused = [t for t in tokens if t.used_at is None]
    assert len(used) == 1
    assert len(unused) == 1
    assert len(_reset_token_spy.captured) == 2


# ---------------------------------------------------------------------------
# Reset-password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_happy_path_issues_session_and_bumps_version(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
    _capture_notification_dispatches: list[dict[str, Any]],
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()
    initial_version = user.session_version
    initial_hash = user.password_hash

    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert forgot.status_code == 200
    raw = _reset_token_spy.captured[-1]

    new_password = "fresh-password-with-1-digit"
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": new_password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == user.email
    assert "password_hash" not in body

    # Session cookie was set on the response.
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{SESSION_COOKIE_NAME}=") for c in cookies)

    # User row reflects the change.
    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.password_hash is not None
    assert refreshed.password_hash != initial_hash
    assert verify_password(new_password, refreshed.password_hash) is True
    assert refreshed.session_version == initial_version + 1

    # Token row is consumed.
    token_row = await PasswordResetToken.find_one(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at != None,  # noqa: E711 — Beanie query operator
    )
    assert token_row is not None
    assert token_row.used_at is not None

    # N017 password-changed notification was dispatched.
    n017_calls = [
        c
        for c in _capture_notification_dispatches
        if c.get("type") is not None and c["type"].value == "security.password_changed"
    ]
    assert len(n017_calls) == 1, _capture_notification_dispatches


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_410(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    raw = _reset_token_spy.captured[-1]

    # Manually expire the token.
    token = await PasswordResetToken.find_one(PasswordResetToken.user_id == user.id)
    assert token is not None
    token.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    await token.save()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "fresh-password-with-1-digit"},
    )
    assert response.status_code == 410, response.text
    assert response.json()["detail"]["error"] == "reset_token_expired"


@pytest.mark.asyncio
async def test_reset_password_used_token_returns_410(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    raw = _reset_token_spy.captured[-1]

    # Manually mark used.
    token = await PasswordResetToken.find_one(PasswordResetToken.user_id == user.id)
    assert token is not None
    token.used_at = datetime.now(UTC)
    await token.save()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "fresh-password-with-1-digit"},
    )
    assert response.status_code == 410, response.text
    assert response.json()["detail"]["error"] == "reset_token_used"


@pytest.mark.asyncio
async def test_reset_password_unknown_token_returns_410(
    _clean_env: None,
    _clean_db: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "fresh-password-with-1-digit"},
    )
    assert response.status_code == 410, response.text
    assert response.json()["detail"]["error"] == "reset_token_invalid"


@pytest.mark.asyncio
async def test_reset_password_weak_password_returns_422(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    """Pydantic catches < 12 chars first — generic 422 with the field-level shape."""
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    raw = _reset_token_spy.captured[-1]

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "short"},
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_reset_password_letters_only_returns_422_policy(
    _clean_env: None,
    _clean_db: None,
    _reset_token_spy: _ResetTokenSpy,
) -> None:
    """A length-passing but no-digit password exercises the service-layer policy 422."""
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    raw = _reset_token_spy.captured[-1]

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "alllowercasenodigit"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "weak_password"


@pytest.mark.asyncio
async def test_reset_password_unrelated_password_unchanged_on_invalid_token(
    _clean_env: None,
    _clean_db: None,
) -> None:
    """If the token is invalid, the user's password must NOT change.

    Defence-in-depth — a leaked / unknown token must not be a side-
    channel that mutates account state.
    """
    client = TestClient(_make_app())
    user = await _signup_and_verify(client)
    pre_hash = user.password_hash

    client.post(
        "/api/v1/auth/reset-password",
        json={"token": "bogus", "new_password": "another-fresh-pw-12"},
    )

    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.password_hash is not None
    assert refreshed.password_hash == pre_hash
    # And the original password still verifies.
    assert verify_password(_VALID_PASSWORD, refreshed.password_hash) is True
    # Unused symbol guard so the helper import path stays referenced.
    _ = hash_password
