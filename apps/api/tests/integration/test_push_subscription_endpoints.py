"""Integration tests for the push-subscription endpoints (T136).

Covers:

* POST creates a fresh subscription.
* POST idempotency: re-posting the same endpoint updates ``last_used_at``
  rather than erroring.
* DELETE: owner can remove their own subscription.
* DELETE: another user gets 404 (no existence leak).
* Auth gate: unauthenticated requests get 401.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.notifications.routes import router as notifications_router


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


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    """Test-only auth bridge — sets ``request.state.session`` from a header."""

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
    app.include_router(notifications_router, prefix="/api/v1")
    return app


@pytest_asyncio.fixture(autouse=True)
async def _clean_subscriptions() -> AsyncIterator[None]:
    await PushSubscription.delete_all()
    yield
    await PushSubscription.delete_all()


@pytest.mark.asyncio
async def test_post_subscription_creates_row(_clean_env: None) -> None:
    """POST → fresh row with the supplied keys."""
    app = _make_app()
    client = TestClient(app)
    body = {
        "endpoint": "https://fcm.googleapis.com/wp/test-001",
        "keys": {"p256dh": "p256dh_test", "auth": "auth_test"},
    }
    response = client.post(
        "/api/v1/users/me/push-subscriptions",
        json=body,
        headers={"X-User-Id": "user_recipient"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] is True
    rows = await PushSubscription.find_all().to_list()
    assert len(rows) == 1
    assert rows[0].endpoint == body["endpoint"]
    assert rows[0].user_id == "user_recipient"


@pytest.mark.asyncio
async def test_post_subscription_idempotent_on_endpoint(_clean_env: None) -> None:
    """Re-posting the same endpoint updates last_used_at; row count = 1."""
    app = _make_app()
    client = TestClient(app)
    body = {
        "endpoint": "https://fcm.googleapis.com/wp/test-002",
        "keys": {"p256dh": "p1", "auth": "a1"},
    }
    headers = {"X-User-Id": "user_recipient"}
    first = client.post("/api/v1/users/me/push-subscriptions", json=body, headers=headers)
    assert first.json()["created"] is True

    second = client.post("/api/v1/users/me/push-subscriptions", json=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["created"] is False

    rows = await PushSubscription.find_all().to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_delete_subscription_owner_succeeds(_clean_env: None) -> None:
    """Owner can delete their own subscription."""
    sub = PushSubscription(
        user_id="user_owner",
        endpoint="https://fcm.googleapis.com/wp/test-del",
        p256dh_key="p",
        auth_secret="a",
    )
    await sub.insert()
    app = _make_app()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/users/me/push-subscriptions/{sub.id}",
        headers={"X-User-Id": "user_owner"},
    )
    assert response.status_code == 204
    assert (await PushSubscription.find_one(PushSubscription.id == sub.id)) is None


@pytest.mark.asyncio
async def test_delete_subscription_non_owner_gets_404(_clean_env: None) -> None:
    """Non-owner sees a 404 with no existence leak."""
    sub = PushSubscription(
        user_id="user_owner",
        endpoint="https://fcm.googleapis.com/wp/test-protect",
        p256dh_key="p",
        auth_secret="a",
    )
    await sub.insert()
    app = _make_app()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/users/me/push-subscriptions/{sub.id}",
        headers={"X-User-Id": "user_other"},
    )
    assert response.status_code == 404
    # Row still exists.
    assert (await PushSubscription.find_one(PushSubscription.id == sub.id)) is not None


@pytest.mark.asyncio
async def test_post_subscription_requires_session(_clean_env: None) -> None:
    """Unauthenticated POST → 401."""
    app = _make_app()
    client = TestClient(app)
    body = {
        "endpoint": "https://fcm.googleapis.com/wp/test-anon",
        "keys": {"p256dh": "p", "auth": "a"},
    }
    response = client.post("/api/v1/users/me/push-subscriptions", json=body)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_subscription_requires_session(_clean_env: None) -> None:
    """Unauthenticated DELETE → 401."""
    app = _make_app()
    client = TestClient(app)
    response = client.delete("/api/v1/users/me/push-subscriptions/some-id")
    assert response.status_code == 401
