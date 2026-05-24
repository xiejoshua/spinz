"""Integration tests for the block / un-block endpoints (T102).

Exercises ``POST /api/v1/users/{handle}/block``,
``DELETE /api/v1/users/{handle}/block``, and ``GET /api/v1/users/me/blocks``
through a FastAPI :class:`TestClient`. Auth is forged via the same fake
middleware used by the diary + follow integration tests.

Covers (TC-028):

* Block dissolves Follow rows in BOTH directions.
* Block cancels pending FollowRequest in BOTH directions.
* Idempotent double-block: same row, no duplicate insert, cascade
  re-runs cleanly.
* Self-block returns 400.
* Unknown handle returns 404.
* Un-block does NOT auto-restore the cascaded follows.
* ``GET /users/me/blocks`` returns the viewer's outgoing blocks with
  denormalised blockee handle / display_name fields.
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
    await Block.delete_all()
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await User.delete_all()
    yield
    await Block.delete_all()
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# POST /users/{handle}/block — happy path + cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_block_creates_row_and_returns_204(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "harassment"},
    )
    assert response.status_code == 204, response.text
    row = await Block.find_one({"blocker_id": blocker.id, "blockee_id": blockee.id})
    assert row is not None
    assert row.reason == BlockReason.HARASSMENT


@pytest.mark.asyncio
async def test_block_cascade_dissolves_follow_both_directions(
    _clean_env: None, _clean_db: None
) -> None:
    """TC-028: a Block between A and B deletes any Follow A→B AND B→A."""
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    # Mutual follow.
    await Follow(
        follower_id=blocker.id,
        followee_id=blockee.id,
        state=FollowState.ACCEPTED,
    ).insert()
    await Follow(
        follower_id=blockee.id,
        followee_id=blocker.id,
        state=FollowState.ACCEPTED,
    ).insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "spam"},
    )
    assert response.status_code == 204
    # Both Follow rows are gone.
    assert await Follow.find_one({"follower_id": blocker.id, "followee_id": blockee.id}) is None
    assert await Follow.find_one({"follower_id": blockee.id, "followee_id": blocker.id}) is None


@pytest.mark.asyncio
async def test_block_cascade_cancels_pending_follow_request_either_direction(
    _clean_env: None, _clean_db: None
) -> None:
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    # Pending request in either direction.
    req_a = FollowRequest(
        requester_id=blocker.id,
        requestee_id=blockee.id,
        status=FollowRequestStatus.PENDING,
    )
    req_b = FollowRequest(
        requester_id=blockee.id,
        requestee_id=blocker.id,
        status=FollowRequestStatus.PENDING,
    )
    await req_a.insert()
    await req_b.insert()
    client = TestClient(_make_app())

    response = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "unwanted_contact"},
    )
    assert response.status_code == 204
    refreshed_a = await FollowRequest.get(req_a.id)
    refreshed_b = await FollowRequest.get(req_b.id)
    assert refreshed_a is not None and refreshed_a.status == FollowRequestStatus.DECLINED
    assert refreshed_b is not None and refreshed_b.status == FollowRequestStatus.DECLINED
    assert refreshed_a.responded_at is not None
    assert refreshed_b.responded_at is not None


@pytest.mark.asyncio
async def test_block_idempotent_double_block_keeps_single_row(
    _clean_env: None, _clean_db: None
) -> None:
    """A second block call against the same target keeps the original row."""
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    client = TestClient(_make_app())

    first = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "harassment"},
    )
    assert first.status_code == 204
    second = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "spam"},
    )
    assert second.status_code == 204

    rows = await Block.find({"blocker_id": blocker.id, "blockee_id": blockee.id}).to_list()
    assert len(rows) == 1
    # The original reason wins — the second call does NOT overwrite the
    # original moderator intent.
    assert rows[0].reason == BlockReason.HARASSMENT


@pytest.mark.asyncio
async def test_block_self_returns_400(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": user.id},
        json={"reason": "other"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "self_block_forbidden"


@pytest.mark.asyncio
async def test_block_unknown_handle_returns_404(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    await blocker.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/ghost/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "spam"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"


@pytest.mark.asyncio
async def test_block_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    target = _make_user("user-casey", "casey")
    await target.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/casey/block",
        json={"reason": "spam"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /users/{handle}/block — un-block + no restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unblock_removes_block_row(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    await Block(
        blocker_id=blocker.id,
        blockee_id=blockee.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    client = TestClient(_make_app())

    response = client.delete(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
    )
    assert response.status_code == 204
    assert await Block.find_one({"blocker_id": blocker.id, "blockee_id": blockee.id}) is None


@pytest.mark.asyncio
async def test_unblock_does_not_restore_cascaded_follow(_clean_env: None, _clean_db: None) -> None:
    """Un-block leaves the cascaded follows gone — user has to re-follow."""
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    await Follow(
        follower_id=blocker.id,
        followee_id=blockee.id,
        state=FollowState.ACCEPTED,
    ).insert()
    client = TestClient(_make_app())

    # Block (deletes the Follow row).
    block_resp = client.post(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
        json={"reason": "harassment"},
    )
    assert block_resp.status_code == 204
    # Un-block (should NOT recreate the Follow row).
    unblock_resp = client.delete(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
    )
    assert unblock_resp.status_code == 204

    assert await Follow.find_one({"follower_id": blocker.id, "followee_id": blockee.id}) is None


@pytest.mark.asyncio
async def test_unblock_idempotent_when_no_block_row(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    blockee = _make_user("user-casey", "casey")
    await blocker.insert()
    await blockee.insert()
    client = TestClient(_make_app())
    response = client.delete(
        "/api/v1/users/casey/block",
        headers={"X-User-Id": blocker.id},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unblock_unknown_handle_returns_404(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    await blocker.insert()
    client = TestClient(_make_app())
    response = client.delete(
        "/api/v1/users/ghost/block",
        headers={"X-User-Id": blocker.id},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /users/me/blocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_my_blocks_returns_outgoing_blocks_with_handle(
    _clean_env: None, _clean_db: None
) -> None:
    blocker = _make_user("user-bob", "bob")
    blockee_a = _make_user("user-casey", "casey")
    blockee_b = _make_user("user-dee", "dee")
    await blocker.insert()
    await blockee_a.insert()
    await blockee_b.insert()
    await Block(
        blocker_id=blocker.id,
        blockee_id=blockee_a.id,
        reason=BlockReason.HARASSMENT,
        other_reason=None,
    ).insert()
    await Block(
        blocker_id=blocker.id,
        blockee_id=blockee_b.id,
        reason=BlockReason.OTHER,
        other_reason="spamming my feed",
    ).insert()
    client = TestClient(_make_app())

    response = client.get(
        "/api/v1/users/me/blocks",
        headers={"X-User-Id": blocker.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    blockee_handles = {row["blockee_handle"] for row in body["blocks"]}
    assert blockee_handles == {"casey", "dee"}
    for row in body["blocks"]:
        if row["blockee_handle"] == "dee":
            assert row["reason"] == "other"
            assert row["notes"] == "spamming my feed"
        if row["blockee_handle"] == "casey":
            assert row["reason"] == "harassment"
            assert row["notes"] is None
        assert "blocked_at" in row
        assert row["blockee_display_name"] != ""


@pytest.mark.asyncio
async def test_list_my_blocks_empty_when_no_rows(_clean_env: None, _clean_db: None) -> None:
    blocker = _make_user("user-bob", "bob")
    await blocker.insert()
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/blocks",
        headers={"X-User-Id": blocker.id},
    )
    assert response.status_code == 200
    assert response.json() == {"blocks": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_list_my_blocks_unauthenticated_returns_401(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/me/blocks")
    assert response.status_code == 401
