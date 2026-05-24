"""Integration tests for ``GET /api/v1/users/{handle}`` (T143 / REV-001).

The profile endpoint surfaces the viewer's *relation* to the target user
— ``self`` / ``following`` / ``pending`` / ``blocked`` / ``none`` /
``anonymous``. REV-001 fixed a field-name typo that prevented the
``pending`` branch from ever firing: the query against
:class:`FollowRequest` was using ``follower_id`` / ``followee_id``
(``Follow`` field names) instead of ``requester_id`` / ``requestee_id``.

These tests pin the corrected behaviour so the regression cannot
recur:

* A pending follow-request against a private profile surfaces as
  ``relation == "pending"`` on the GET.
* An accepted follow surfaces as ``relation == "following"``.
* Self / anonymous / blocked relations continue to return the
  expected strings.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
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
from auxd_api.modules.users.models import HandleRedirect, User
from auxd_api.modules.users.routes import router as users_router
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
    await Block.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()
    yield
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await Block.delete_all()
    await User.delete_all()
    await HandleRedirect.delete_all()


# ---------------------------------------------------------------------------
# REV-001: pending FollowRequest must surface as relation=="pending"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_profile_surfaces_pending_relation_for_open_follow_request(
    _clean_env: None, _clean_db: None
) -> None:
    """A pending FollowRequest to a private profile surfaces relation=='pending'.

    Before REV-001 the query used the wrong field names
    (``follower_id`` / ``followee_id``) so the lookup always missed and
    the response reported ``relation == "none"``, leaving the UI to
    show a "Follow" button when "Pending" was correct.
    """
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target", private_profile=True)
    await viewer.insert()
    await target.insert()
    # Open follow request from viewer → target. Matches the row that
    # ``social.follow_user`` writes for a private-profile target.
    await FollowRequest(
        requester_id=viewer.id,
        requestee_id=target.id,
        status=FollowRequestStatus.PENDING,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["relation"] == "pending"


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_no_follow_request(
    _clean_env: None, _clean_db: None
) -> None:
    """No request, no follow → relation=='none' (not pending, not following)."""
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target", private_profile=True)
    await viewer.insert()
    await target.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    assert response.json()["relation"] == "none"


@pytest.mark.asyncio
async def test_get_profile_ignores_non_pending_follow_requests(
    _clean_env: None, _clean_db: None
) -> None:
    """A declined / accepted / expired FollowRequest must not surface as 'pending'.

    The pending lookup filters on ``status == PENDING``; only an open
    request flips the relation.
    """
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target", private_profile=True)
    await viewer.insert()
    await target.insert()
    await FollowRequest(
        requester_id=viewer.id,
        requestee_id=target.id,
        status=FollowRequestStatus.DECLINED,
        responded_at=datetime.now(UTC),
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.json()["relation"] == "none"


# ---------------------------------------------------------------------------
# Companion relation branches — keep the other return values pinned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_profile_following_relation(_clean_env: None, _clean_db: None) -> None:
    """An accepted Follow row surfaces relation=='following'."""
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target")
    await viewer.insert()
    await target.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=target.id,
        state=FollowState.ACCEPTED,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    assert response.json()["relation"] == "following"


@pytest.mark.asyncio
async def test_get_profile_self_relation(_clean_env: None, _clean_db: None) -> None:
    """Viewer == target → relation=='self'."""
    user = _make_user("u-target", "target")
    await user.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{user.handle}",
        headers={"X-User-Id": user.id},
    )
    assert response.json()["relation"] == "self"


@pytest.mark.asyncio
async def test_get_profile_anonymous_relation(_clean_env: None, _clean_db: None) -> None:
    """No session → relation=='anonymous'."""
    target = _make_user("u-target", "target")
    await target.insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{target.handle}")
    assert response.status_code == 200
    assert response.json()["relation"] == "anonymous"


@pytest.mark.asyncio
async def test_get_profile_viewer_blocked_target_relation(
    _clean_env: None, _clean_db: None
) -> None:
    """Viewer has blocked target → relation=='blocked'.

    The target has not blocked the viewer (existence remains visible);
    the viewer simply chose to hide them.
    """
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target")
    await viewer.insert()
    await target.insert()
    await Block(
        blocker_id=viewer.id,
        blockee_id=target.id,
        reason=BlockReason.OTHER,
        other_reason="testing",
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    assert response.json()["relation"] == "blocked"


@pytest.mark.asyncio
async def test_get_profile_target_blocked_viewer_returns_404(
    _clean_env: None, _clean_db: None
) -> None:
    """When the target has blocked the viewer, 404 (existence-leak prevention)."""
    viewer = _make_user("u-viewer", "viewer")
    target = _make_user("u-target", "target")
    await viewer.insert()
    await target.insert()
    await Block(
        blocker_id=target.id,
        blockee_id=viewer.id,
        reason=BlockReason.OTHER,
        other_reason="testing",
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{target.handle}",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"
