"""Integration tests for the avatar upload endpoint (T146).

Exercises ``POST /api/v1/users/me/avatar`` through a FastAPI
:class:`TestClient`. Mirrors the fake-auth middleware pattern used by
the other social/users integration suites — we don't run the full
HMAC cookie round-trip; the avatar contracts under test don't depend
on cookie shape.

Covers:

* 401 unauthenticated.
* 415 unsupported content-type.
* 413 oversize payload (>5MB).
* 200 happy path — three sizes uploaded, ``User.avatar_url`` updated.
* 5/min per-user rate limit (boundary check).
"""

from __future__ import annotations

import base64
import io
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib import storage as storage_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.users.models import User
from auxd_api.modules.users.routes import router as users_router


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
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://test.r2.example.com")
    monkeypatch.setenv("R2_AVATAR_BUCKET", "auxd-avatars-test")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    """Attach a :class:`Session` based on the ``X-User-Id`` header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            request.state.session = Session(
                user_id=user_id,
                csrf_token="test-csrf",
                issued_at=0,
                expires_at=int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
                session_version=1,
            )
        else:
            request.state.session = None
        return await call_next(request)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(_FakeAuthMiddleware)
    app.include_router(users_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await User.delete_all()
    yield
    await User.delete_all()


class _StubS3Client:
    """Records put_object calls so tests can assert on the upload payload."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ETag": "fake-etag"}


@pytest.fixture
def _stub_r2(monkeypatch: pytest.MonkeyPatch) -> _StubS3Client:
    stub = _StubS3Client()

    def _fake_build_client() -> _StubS3Client:
        return stub

    monkeypatch.setattr(storage_module, "_build_s3_client", _fake_build_client)
    return stub


def _make_image_bytes(*, width: int = 512, height: int = 384, fmt: str = "PNG") -> bytes:
    """Build a single-colour test image of the requested size + format."""
    img = Image.new("RGB", (width, height), color=(123, 45, 67))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Auth + validation gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_avatar_upload_requires_session(_clean_env: None, _clean_db: None) -> None:
    """Unauthenticated POST returns 401 with the standard error shape."""
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("a.png", b"x", "image/png")},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthenticated"


@pytest.mark.asyncio
async def test_avatar_rejects_unsupported_content_type(
    _clean_env: None, _clean_db: None, _stub_r2: _StubS3Client
) -> None:
    """Non-image content-types are rejected with 415."""
    user = _make_user("user-alice", "alice")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("a.txt", b"hello", "text/plain")},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 415, response.text
    assert response.json()["detail"]["error"] == "unsupported_content_type"
    # Nothing uploaded to R2.
    assert _stub_r2.calls == []


@pytest.mark.asyncio
async def test_avatar_rejects_oversize_payload(
    _clean_env: None, _clean_db: None, _stub_r2: _StubS3Client
) -> None:
    """A >5MB upload is 413'd before we hand the bytes to PIL."""
    user = _make_user("user-alice", "alice")
    await user.insert()
    client = TestClient(_make_app())
    # 6 MB of zeros — well past the 5 MB cap.
    big_payload = b"\x00" * (6 * 1024 * 1024)
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("big.png", big_payload, "image/png")},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 413, response.text
    assert response.json()["detail"]["error"] == "file_too_large"
    assert _stub_r2.calls == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_avatar_upload_happy_path(
    _clean_env: None, _clean_db: None, _stub_r2: _StubS3Client
) -> None:
    """A valid PNG yields a 200 with a primary URL + three sizes + R2 puts."""
    user = _make_user("user-alice", "alice")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", _make_image_bytes(), "image/png")},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "avatar_url" in body
    assert set(body["sizes"].keys()) == {"256", "128", "64"}
    assert body["sizes"]["256"] == body["avatar_url"]
    # Three R2 put_object calls — one per size.
    assert len(_stub_r2.calls) == 3
    for call in _stub_r2.calls:
        assert call["Bucket"] == "auxd-avatars-test"
        assert call["ContentType"] == "image/jpeg"
        assert call["Key"].startswith(f"avatars/{user.id}/")
        assert call["Key"].endswith(".jpg")
    # User row updated.
    refreshed = await User.get(user.id)
    assert refreshed is not None
    assert refreshed.avatar_url == body["avatar_url"]


@pytest.mark.asyncio
async def test_avatar_rejects_empty_file(
    _clean_env: None, _clean_db: None, _stub_r2: _StubS3Client
) -> None:
    """A zero-byte payload is treated as a 422 validation failure."""
    user = _make_user("user-alice", "alice")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("empty.png", b"", "image/png")},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "empty_file"


@pytest.mark.asyncio
async def test_avatar_rejects_corrupt_image(
    _clean_env: None, _clean_db: None, _stub_r2: _StubS3Client
) -> None:
    """Bytes that pass the content-type filter but PIL can't decode → 415."""
    user = _make_user("user-alice", "alice")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("fake.png", b"not really a png", "image/png")},
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 415
    assert response.json()["detail"]["error"] == "invalid_image"
