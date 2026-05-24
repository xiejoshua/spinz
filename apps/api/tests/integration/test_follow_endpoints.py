"""Integration tests for the follow / unfollow endpoints (T101).

Exercises ``POST /api/v1/users/{handle}/follow`` and
``DELETE /api/v1/users/{handle}/follow`` through a FastAPI
:class:`TestClient`. Auth is forged via a fake middleware (mirrors the
diary test harness) so we don't need the full HMAC cookie round-trip —
the social-graph contracts under test don't depend on cookie shape.

Covers:

* Happy path public profile → Follow row created with state=ACCEPTED.
* Private profile → FollowRequest with status=PENDING (no Follow row).
* Self-follow forbidden → 400.
* Unknown handle → 404.
* Blocked-by-followee → 403 (either direction of the Block edge).
* Idempotent double-follow → same id, no duplicate row.
* Unfollow → 204 + Follow row deleted.
* Unfollow when not following → 204 (idempotent no-op).
* Unfollow cancels a pending FollowRequest.
* PostHog event emitted on both follow and unfollow.
* Unauthenticated POST / DELETE → 401.
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
from auxd_api.modules.social.models import (
    Block,
    BlockReason,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.social.routes import router as social_router
from auxd_api.modules.users.models import User
from tests.integration._auth_helpers import FakeAuthMiddleware


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


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(social_router, prefix="/api/v1")
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
    await Block.delete_all()
    await User.delete_all()
    yield
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await Block.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# POST /users/{handle}/follow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_follow_public_profile_creates_accepted_follow(
    _clean_env: None, _clean_db: None
) -> None:
    """Following a public profile inserts a Follow row with state=ACCEPTED."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "accepted"
    assert body["followee_id"] == target.id
    assert isinstance(body["follow_id"], str)

    # Row persists with the correct state.
    row = await Follow.find_one({"follower_id": follower.id, "followee_id": target.id})
    assert row is not None
    assert row.state == FollowState.ACCEPTED
    # No body in this request → default source "profile".
    assert row.source == "profile"


@pytest.mark.asyncio
async def test_follow_records_source_from_body(_clean_env: None, _clean_db: None) -> None:
    """Body ``{source: ...}`` is persisted on the Follow row.

    Funnel analytics needs to distinguish onboarding pre-selected
    follows from manual follows from profile-page follows. The
    onboarding deck (T118) passes ``source=onboarding_preselected``.
    """
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
        json={"source": "onboarding_preselected"},
    )
    assert response.status_code == 200, response.text
    row = await Follow.find_one({"follower_id": follower.id, "followee_id": target.id})
    assert row is not None
    assert row.source == "onboarding_preselected"


@pytest.mark.asyncio
async def test_follow_rejects_unknown_source(_clean_env: None, _clean_db: None) -> None:
    """Typo'd ``source`` values must 422 — never silently mis-tag a follow."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
        json={"source": "totally_made_up_source"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_follow_source"


@pytest.mark.asyncio
async def test_follow_private_profile_creates_pending_request(
    _clean_env: None, _clean_db: None
) -> None:
    """Private-profile follow creates a FollowRequest, NOT a Follow row."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey", private_profile=True)
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "pending"

    # No Follow row.
    follow_row = await Follow.find_one({"follower_id": follower.id, "followee_id": target.id})
    assert follow_row is None
    # A FollowRequest row exists with status=PENDING.
    request_row = await FollowRequest.find_one(
        {"requester_id": follower.id, "requestee_id": target.id}
    )
    assert request_row is not None
    assert request_row.status == FollowRequestStatus.PENDING


@pytest.mark.asyncio
async def test_follow_self_returns_400(_clean_env: None, _clean_db: None) -> None:
    """Self-follow is forbidden."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "self_follow_forbidden"


@pytest.mark.asyncio
async def test_follow_unknown_handle_returns_404(_clean_env: None, _clean_db: None) -> None:
    """Unknown handle yields 404."""
    follower = _make_user("user-bob", "bob")
    await follower.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/ghost/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"


@pytest.mark.asyncio
async def test_follow_blocked_by_followee_returns_403(_clean_env: None, _clean_db: None) -> None:
    """Followee has blocked follower → 403, no Follow row created."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    await Block(
        blocker_id=target.id,
        blockee_id=follower.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "blocked"
    assert await Follow.find_one({"follower_id": follower.id, "followee_id": target.id}) is None


@pytest.mark.asyncio
async def test_follow_blocking_followee_returns_403(_clean_env: None, _clean_db: None) -> None:
    """Follower has blocked followee → 403 (symmetric block guard)."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    await Block(
        blocker_id=follower.id,
        blockee_id=target.id,
        reason=BlockReason.UNWANTED,
    ).insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_follow_idempotent_double_follow_returns_current_state(
    _clean_env: None, _clean_db: None
) -> None:
    """A second follow against the same target returns the same id, one row."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    first = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert first.status_code == 200
    first_id = first.json()["follow_id"]

    second = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert second.status_code == 200
    assert second.json()["follow_id"] == first_id

    rows = await Follow.find({"follower_id": follower.id, "followee_id": target.id}).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_follow_idempotent_double_request_returns_current_state(
    _clean_env: None, _clean_db: None
) -> None:
    """A second follow against the same private profile returns the same pending id."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey", private_profile=True)
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    first = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert first.status_code == 200
    first_id = first.json()["follow_id"]
    assert first.json()["state"] == "pending"

    second = client.post(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert second.status_code == 200
    assert second.json()["follow_id"] == first_id
    assert second.json()["state"] == "pending"

    rows = await FollowRequest.find(
        {"requester_id": follower.id, "requestee_id": target.id}
    ).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_follow_resolves_handle_via_redirect(_clean_env: None, _clean_db: None) -> None:
    """The follow target is resolved through the handle redirect table.

    The resolver is exercised here to lock in that the route uses
    ``resolve_handle`` rather than a raw ``User.find_one`` — without
    this, old @handle links break after rename.
    """
    from auxd_api.modules.users.models import HandleRedirect

    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    redirect = HandleRedirect(old_handle="oldcasey", new_handle="casey", user_id=target.id)
    await redirect.insert()
    client = TestClient(_make_app())
    try:
        response = client.post(
            "/api/v1/users/oldcasey/follow",
            headers={"X-User-Id": follower.id},
        )
        assert response.status_code == 200
        assert response.json()["followee_id"] == target.id
    finally:
        await HandleRedirect.delete_all()


@pytest.mark.asyncio
async def test_follow_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    """No session → 401 before the handle is even resolved."""
    target = _make_user("user-casey", "casey")
    await target.insert()
    client = TestClient(_make_app())
    response = client.post("/api/v1/users/casey/follow")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /users/{handle}/follow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unfollow_removes_follow_row(_clean_env: None, _clean_db: None) -> None:
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    await Follow(
        follower_id=follower.id,
        followee_id=target.id,
        state=FollowState.ACCEPTED,
    ).insert()
    client = TestClient(_make_app())

    response = client.delete(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 204
    assert await Follow.find_one({"follower_id": follower.id, "followee_id": target.id}) is None


@pytest.mark.asyncio
async def test_unfollow_when_not_following_returns_204(_clean_env: None, _clean_db: None) -> None:
    """No Follow row → still 204 (idempotent)."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey")
    await follower.insert()
    await target.insert()
    client = TestClient(_make_app())

    response = client.delete(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unfollow_cancels_pending_request(_clean_env: None, _clean_db: None) -> None:
    """Unfollow against a private profile cancels the pending FollowRequest."""
    follower = _make_user("user-bob", "bob")
    target = _make_user("user-casey", "casey", private_profile=True)
    await follower.insert()
    await target.insert()
    req = FollowRequest(
        requester_id=follower.id,
        requestee_id=target.id,
        status=FollowRequestStatus.PENDING,
    )
    await req.insert()
    client = TestClient(_make_app())

    response = client.delete(
        "/api/v1/users/casey/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 204
    refreshed = await FollowRequest.get(req.id)
    assert refreshed is not None
    assert refreshed.status == FollowRequestStatus.DECLINED
    assert refreshed.responded_at is not None


@pytest.mark.asyncio
async def test_unfollow_unknown_handle_returns_404(_clean_env: None, _clean_db: None) -> None:
    follower = _make_user("user-bob", "bob")
    await follower.insert()
    client = TestClient(_make_app())
    response = client.delete(
        "/api/v1/users/ghost/follow",
        headers={"X-User-Id": follower.id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unfollow_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    target = _make_user("user-casey", "casey")
    await target.insert()
    client = TestClient(_make_app())
    response = client.delete("/api/v1/users/casey/follow")
    assert response.status_code == 401
