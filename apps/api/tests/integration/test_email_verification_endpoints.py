"""Integration tests for verify-email + resend-verification (002-auth-email-flows).

Drives ``POST /api/v1/auth/verify-email`` and ``POST /api/v1/auth/resend-
verification`` end-to-end through the :class:`SessionMiddleware`-mounted
TestClient. Uses the standard ``_clean_env`` / ``_clean_users`` /
``_clean_db`` pattern from :mod:`tests.integration.test_auth_endpoints`.

Verification-token introspection pattern
========================================
``generate_token`` returns ``(raw, hash)``; the raw is what's stored in
the email, the hash is what's persisted. Tests need the raw to drive
the verify-email endpoint, but the production signup path never returns
it to the caller. We monkeypatch the *symbols imported by the email-
verification module* (NOT the lib-level ones — the module captured the
binding at import time) to substitute a stub that:

1. Picks the next raw token from a controlled list.
2. Calls the real ``hash_token`` so the stored hash + the test's raw
   round-trip correctly through the lookup path.

The lookup path inside ``consume_verification_token`` re-hashes the
inbound raw and queries by hash, so the stub's deterministic raws must
hash to the same value the DB row carries.
"""

from __future__ import annotations

import base64
import logging
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
from auxd_api.lib.sessions import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from auxd_api.middleware import SessionMiddleware
from auxd_api.modules.auth import email_verification as email_verification_module
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


def _make_app() -> FastAPI:
    """Mount auth + users routers under the production /api/v1 prefix."""
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


class _TokenSpy:
    """Capture every raw token issued via :func:`generate_token`.

    The stub mirrors the real ``generate_token`` shape — ``() -> (raw,
    hash)`` — but pulls raws from a deterministic list when supplied,
    or generates fresh ones otherwise. In both modes the captured raws
    are exposed so tests can drive the consume path with the known
    secret.
    """

    def __init__(self, raws: list[str] | None = None) -> None:
        # ``raws`` lets tests pin specific values (e.g., for the
        # idempotent re-click case where two POSTs need to round-trip
        # against the same raw); when ``None`` the spy uses the real
        # generator so each issued token is unique.
        self._raws_iter = iter(raws) if raws is not None else None
        self.captured: list[str] = []

    def __call__(self) -> tuple[str, str]:
        if self._raws_iter is not None:
            try:
                raw = next(self._raws_iter)
            except StopIteration:
                raw = secrets.token_urlsafe(32)
        else:
            raw = secrets.token_urlsafe(32)
        token_hash = auth_tokens_lib.hash_token(raw)
        self.captured.append(raw)
        return raw, token_hash


@pytest.fixture
def _verification_token_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> _TokenSpy:
    """Spy on generate_token within the email_verification module.

    The module captures the imported symbol at import time
    (``from auxd_api.lib.auth_tokens import generate_token``), so we
    have to monkeypatch ``email_verification.generate_token`` —
    monkeypatching the lib-level symbol would not take effect.
    """
    spy = _TokenSpy()
    monkeypatch.setattr(email_verification_module, "generate_token", spy)
    return spy


# ---------------------------------------------------------------------------
# Signup bootstraps verification token + email send signal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_bootstraps_verification_token(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Signup writes exactly one unused EmailVerificationToken for the new user."""
    client = TestClient(_make_app())
    with caplog.at_level(logging.INFO):
        response = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]

    # Exactly one verification token row exists, linked to this user.
    tokens = await EmailVerificationToken.find(EmailVerificationToken.user_id == user_id).to_list()
    assert len(tokens) == 1, tokens
    token = tokens[0]
    assert token.used_at is None
    # expires_at is timezone-aware and at least an hour in the future
    # (the contract is 24h; we keep the assertion loose to avoid clock
    # flakes in CI).
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > datetime.now(UTC) + timedelta(hours=1)

    # The spy captured exactly one raw token issued during signup.
    assert len(_verification_token_spy.captured) == 1


# ---------------------------------------------------------------------------
# Verify-email happy path + idempotent re-click
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_email_happy_path_marks_user_verified(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    raw_token = _verification_token_spy.captured[-1]

    # Verify-email is anonymous-callable; clearing cookies models the
    # "user clicked the link from a different device" branch.
    client.cookies.clear()
    response = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verified"] is True
    assert body["idempotent"] is False
    assert body["user"]["id"] == user_id

    # User row reflects the verification state.
    user = await User.get(user_id)
    assert user is not None
    assert user.email_verified is True
    assert user.email_verified_at is not None

    # Token row marked consumed.
    token = await EmailVerificationToken.find_one(EmailVerificationToken.user_id == user_id)
    assert token is not None
    assert token.used_at is not None


@pytest.mark.asyncio
async def test_verify_email_idempotent_reclick(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    """A second POST with the same raw token surfaces idempotent=True."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    raw_token = _verification_token_spy.captured[-1]
    client.cookies.clear()

    first = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert first.status_code == 200, first.text
    assert first.json()["idempotent"] is False

    second = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["verified"] is True
    assert body["idempotent"] is True


# ---------------------------------------------------------------------------
# Verify-email failure modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_email_expired_token_returns_422(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    """A past-its-expiry token surfaces ``verification_token_expired``.

    The plan locks expired → 422 (not 410) because the user can recover
    via the resend path; the link wasn't malformed, it just timed out.
    """
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    raw_token = _verification_token_spy.captured[-1]
    client.cookies.clear()

    # Reach into the DB and back-date expires_at to the past.
    token = await EmailVerificationToken.find_one(EmailVerificationToken.user_id == user_id)
    assert token is not None
    token.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await token.save()

    response = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "verification_token_expired"


@pytest.mark.asyncio
async def test_verify_email_used_token_returns_410(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    """A used token against a NOT-already-verified user surfaces 410.

    The idempotent re-click branch only fires when the linked user is
    already verified. Forcing ``used_at`` without flipping
    ``email_verified`` exercises the raw 410 path.
    """
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    raw_token = _verification_token_spy.captured[-1]
    client.cookies.clear()

    token = await EmailVerificationToken.find_one(EmailVerificationToken.user_id == user_id)
    assert token is not None
    token.used_at = datetime.now(UTC)
    await token.save()
    # Ensure the user is still NOT verified (so the idempotent branch
    # cannot trigger).
    user = await User.get(user_id)
    assert user is not None
    user.email_verified = False
    user.email_verified_at = None
    await user.save()

    response = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 410, response.text
    assert response.json()["detail"]["error"] == "verification_token_used"


@pytest.mark.asyncio
async def test_verify_email_unknown_token_returns_410(
    _clean_env: None,
    _clean_db: None,
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": "definitely-not-a-real-token"},
    )
    assert response.status_code == 410, response.text
    assert response.json()["detail"]["error"] == "verification_token_invalid"


# ---------------------------------------------------------------------------
# Resend verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_verification_invalidates_prior_and_issues_fresh(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    first_raw = _verification_token_spy.captured[-1]

    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    response = client.post(
        "/api/v1/auth/resend-verification",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["verified"] is False

    # The prior unused token now has used_at set (invalidated as
    # superseded). A fresh, unused token also exists.
    tokens = await EmailVerificationToken.find(EmailVerificationToken.user_id == user_id).to_list()
    assert len(tokens) == 2, tokens
    used = [t for t in tokens if t.used_at is not None]
    unused = [t for t in tokens if t.used_at is None]
    assert len(used) == 1
    assert len(unused) == 1
    # The captured raws now include both the signup + the resend.
    assert len(_verification_token_spy.captured) == 2
    assert _verification_token_spy.captured[0] == first_raw


@pytest.mark.asyncio
async def test_resend_verification_already_verified_noop(
    _clean_env: None,
    _clean_db: None,
    _verification_token_spy: _TokenSpy,
) -> None:
    """When user is already verified, resend is a benign no-op (no new token)."""
    client = TestClient(_make_app())
    signup = client.post("/api/v1/auth/signup", json=_VALID_PAYLOAD)
    assert signup.status_code == 201
    user_id = signup.json()["id"]

    # Flip the user to verified directly so the resend path sees the
    # already-verified branch.
    user = await User.get(user_id)
    assert user is not None
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await user.save()

    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    initial_raws = list(_verification_token_spy.captured)
    response = client.post(
        "/api/v1/auth/resend-verification",
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["verified"] is True

    # No fresh token was issued — the spy's captured list is unchanged.
    assert _verification_token_spy.captured == initial_raws
    # And the DB still holds exactly the signup-time token.
    tokens = await EmailVerificationToken.find(EmailVerificationToken.user_id == user_id).to_list()
    assert len(tokens) == 1, tokens


@pytest.mark.asyncio
async def test_resend_verification_anonymous_returns_401(
    _clean_env: None,
    _clean_db: None,
) -> None:
    """Anonymous callers can't trigger resend — there's no user to email."""
    client = TestClient(_make_app())
    response = client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 401
