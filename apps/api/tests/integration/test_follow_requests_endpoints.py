"""Integration tests for the follow-request inbox endpoints (T148).

Exercises:

* ``GET /api/v1/users/me/follow-requests`` — list my pending requests
  with the requester user-card sidecar.
* ``POST /api/v1/users/me/follow-requests/{id}/approve`` — transitions
  the row to ``ACCEPTED``, writes a ``Follow`` row, dispatches N-003.
* ``POST /api/v1/users/me/follow-requests/{id}/decline`` — transitions
  to ``DECLINED``, no Follow row created, no notification dispatched.

The notifications dispatcher is monkeypatched at the route-module level
so we can assert on the N-003 dispatch without spinning up the full
adapter chain.
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
from auxd_api.modules.notifications.models import NotificationType
from auxd_api.modules.social.models import (
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.users import routes as users_routes
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


def _make_user(user_id: str, handle: str, *, private_profile: bool = False) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        private_profile=private_profile,
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await User.delete_all()
    yield
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await User.delete_all()


@pytest.fixture
def _capture_dispatches(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    async def _fake_dispatch(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(users_routes, "dispatch_notification", _fake_dispatch)
    return captured


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_requests_unauthenticated(_clean_env: None, _clean_db: None) -> None:
    """Anonymous callers cannot read the inbox."""
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/me/follow-requests")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_approve_request_unauthenticated(_clean_env: None, _clean_db: None) -> None:
    """Anonymous callers cannot approve."""
    client = TestClient(_make_app())
    response = client.post("/api/v1/users/me/follow-requests/anything/approve")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_own_pending_requests_only(_clean_env: None, _clean_db: None) -> None:
    """Listing returns rows where ``requestee_id == me`` and ``status == pending``.

    Other users' rows and any non-pending state for the caller are excluded.
    """
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    other = _make_user("user-other", "other")
    await me.insert()
    await alice.insert()
    await bob.insert()
    await other.insert()

    # Two pending requests for me + one declined for me + one for someone else.
    req_alice = FollowRequest(
        requester_id=alice.id,
        requestee_id=me.id,
        status=FollowRequestStatus.PENDING,
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )
    req_bob = FollowRequest(
        requester_id=bob.id,
        requestee_id=me.id,
        status=FollowRequestStatus.PENDING,
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    req_declined = FollowRequest(
        requester_id=other.id,
        requestee_id=me.id,
        status=FollowRequestStatus.DECLINED,
        created_at=datetime.now(UTC),
    )
    req_other = FollowRequest(
        requester_id=me.id,
        requestee_id=other.id,
        status=FollowRequestStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    await req_alice.insert()
    await req_bob.insert()
    await req_declined.insert()
    await req_other.insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/follow-requests",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [row["id"] for row in body["requests"]]
    # Newer first (bob > alice in created_at).
    assert ids == [req_bob.id, req_alice.id]
    # Sidecar user cards.
    assert body["users"][alice.id]["handle"] == "alice"
    assert body["users"][bob.id]["handle"] == "bob"


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_creates_follow_row_and_dispatches_n003(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """Approving a pending request flips state, writes Follow, dispatches N-003."""
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    await me.insert()
    await alice.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=me.id,
        status=FollowRequestStatus.PENDING,
    )
    await request.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/approve",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"

    refreshed = await FollowRequest.get(request.id)
    assert refreshed is not None
    assert refreshed.status is FollowRequestStatus.ACCEPTED
    follow = await Follow.find_one({"follower_id": alice.id, "followee_id": me.id})
    assert follow is not None
    assert follow.state is FollowState.ACCEPTED
    assert follow.source == "invite"

    # N-003 dispatched to the requester.
    assert len(_capture_dispatches) == 1
    call = _capture_dispatches[0]
    assert call["user_id"] == alice.id
    assert call["type"] is NotificationType.N003_FOLLOW_REQUEST_APPROVED
    assert call["payload"]["actor_handle"] == "alpha"


@pytest.mark.asyncio
async def test_approve_idempotent_when_already_accepted(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """Re-approving an already-accepted row is a no-op: no duplicate Follow, no dispatch."""
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    await me.insert()
    await alice.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=me.id,
        status=FollowRequestStatus.ACCEPTED,
    )
    await request.insert()
    # Pre-existing Follow as the approve handler would have written.
    await Follow(
        follower_id=alice.id,
        followee_id=me.id,
        state=FollowState.ACCEPTED,
        source="invite",
    ).insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/approve",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    # Still exactly one Follow row.
    rows = await Follow.find({"follower_id": alice.id, "followee_id": me.id}).to_list()
    assert len(rows) == 1
    # No duplicate dispatch.
    assert _capture_dispatches == []


@pytest.mark.asyncio
async def test_approve_404_when_not_owner(_clean_env: None, _clean_db: None) -> None:
    """The caller cannot approve someone else's request."""
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    other = _make_user("user-other", "other", private_profile=True)
    await me.insert()
    await alice.insert()
    await other.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=other.id,
        status=FollowRequestStatus.PENDING,
    )
    await request.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/approve",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Decline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decline_transitions_state_no_follow_no_notif(
    _clean_env: None, _clean_db: None, _capture_dispatches: list[dict[str, Any]]
) -> None:
    """Declining flips state to DECLINED, doesn't create a Follow, doesn't notify."""
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    await me.insert()
    await alice.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=me.id,
        status=FollowRequestStatus.PENDING,
    )
    await request.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/decline",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "declined"

    refreshed = await FollowRequest.get(request.id)
    assert refreshed is not None
    assert refreshed.status is FollowRequestStatus.DECLINED
    # No Follow row created.
    assert await Follow.find_one({"follower_id": alice.id, "followee_id": me.id}) is None
    # No notification fired on decline (taxonomy).
    assert _capture_dispatches == []


@pytest.mark.asyncio
async def test_decline_idempotent(_clean_env: None, _clean_db: None) -> None:
    """Re-declining an already-declined row returns 200 with the same state."""
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    await me.insert()
    await alice.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=me.id,
        status=FollowRequestStatus.DECLINED,
    )
    await request.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/decline",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "declined"


@pytest.mark.asyncio
async def test_decline_404_when_not_owner(_clean_env: None, _clean_db: None) -> None:
    me = _make_user("user-me", "alpha", private_profile=True)
    alice = _make_user("user-alice", "alice")
    other = _make_user("user-other", "other", private_profile=True)
    await me.insert()
    await alice.insert()
    await other.insert()
    request = FollowRequest(
        requester_id=alice.id,
        requestee_id=other.id,
        status=FollowRequestStatus.PENDING,
    )
    await request.insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/follow-requests/{request.id}/decline",
        headers={"X-User-Id": me.id},
    )
    assert response.status_code == 404
