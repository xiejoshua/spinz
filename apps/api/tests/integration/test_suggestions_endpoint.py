"""Integration tests for the suggested-follow API surface (T105).

Exercises:

* ``GET /api/v1/users/me/suggestions`` — paginated read of the
  precomputed :class:`Suggestion` rows, joined with :class:`User` for
  card rendering. The handler re-applies the follow / block / dismissal
  filters as defence in depth.
* ``POST /api/v1/users/me/suggestions/{suggested_user_id}/dismiss`` —
  idempotent dismissal that inserts a TTL'd :class:`SuggestionDismissal`
  row and clears the matching ``Suggestion`` row.

Auth is forged via the same :class:`_FakeAuthMiddleware` pattern used by
the diary + follow integration tests.
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
from auxd_api.modules.social.models import (
    Block,
    BlockReason,
    Follow,
    FollowState,
)
from auxd_api.modules.social.routes import router as social_router
from auxd_api.modules.social.suggestions_models import (
    Suggestion,
    SuggestionDismissal,
)
from auxd_api.modules.users.models import User


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
    app.include_router(social_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        avatar_url=f"https://cdn.example.com/{handle}.png",
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Suggestion.delete_all()
    await SuggestionDismissal.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    yield
    await Suggestion.delete_all()
    await SuggestionDismissal.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# GET /users/me/suggestions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggestions_happy_path_returns_top_scored_with_user_card(
    _clean_env: None, _clean_db: None
) -> None:
    """Three precomputed rows return in score-DESC order with card fields."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    carol = _make_user("user-carol", "carol")
    for user in (viewer, alice, bob, carol):
        await user.insert()

    now = datetime.now(UTC)
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=alice.id,
        score=0.9,
        reasons=["mutual_taste"],
        computed_at=now,
    ).insert()
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=bob.id,
        score=0.6,
        reasons=["followed_by_followed"],
        computed_at=now,
    ).insert()
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=carol.id,
        score=0.3,
        reasons=["recency"],
        computed_at=now,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/suggestions",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["suggestions"]) == 3
    ordered_ids = [entry["user"]["id"] for entry in body["suggestions"]]
    assert ordered_ids == [alice.id, bob.id, carol.id]
    # Each entry has the full user-card + score/reasons.
    first = body["suggestions"][0]
    assert first["user"]["handle"] == "alice"
    assert first["user"]["display_name"] == "Alice"
    assert first["user"]["avatar_url"] == "https://cdn.example.com/alice.png"
    assert first["score"] == 0.9
    assert first["reasons"] == ["mutual_taste"]
    assert "computed_at" in first


@pytest.mark.asyncio
async def test_suggestions_filters_already_followed_at_read_time(
    _clean_env: None, _clean_db: None
) -> None:
    """A Follow row that landed after the worker run shadows the stale suggestion."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    for user in (viewer, alice, bob):
        await user.insert()

    # Both alice + bob precomputed; viewer has since followed alice.
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=alice.id,
        score=0.9,
        reasons=["mutual_taste"],
    ).insert()
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=bob.id,
        score=0.6,
        reasons=["followed_by_followed"],
    ).insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=alice.id,
        state=FollowState.ACCEPTED,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/suggestions",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = [entry["user"]["id"] for entry in response.json()["suggestions"]]
    assert ids == [bob.id]


@pytest.mark.asyncio
async def test_suggestions_filters_blocked_in_either_direction(
    _clean_env: None, _clean_db: None
) -> None:
    """Suggestions across a Block edge (either direction) are filtered out."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    carol = _make_user("user-carol", "carol")
    for user in (viewer, alice, bob, carol):
        await user.insert()

    for candidate in (alice, bob, carol):
        await Suggestion(
            user_id=viewer.id,
            suggested_user_id=candidate.id,
            score=0.5,
            reasons=["mutual_taste"],
        ).insert()

    # viewer → alice block; carol → viewer block. Both should be filtered.
    await Block(
        blocker_id=viewer.id,
        blockee_id=alice.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    await Block(
        blocker_id=carol.id,
        blockee_id=viewer.id,
        reason=BlockReason.SPAM,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/suggestions",
        headers={"X-User-Id": viewer.id},
    )
    ids = [entry["user"]["id"] for entry in response.json()["suggestions"]]
    assert ids == [bob.id]


@pytest.mark.asyncio
async def test_suggestions_caps_limit_to_max(_clean_env: None, _clean_db: None) -> None:
    """Limit above the ceiling is silently capped — no 4xx."""
    viewer = _make_user("user-viewer", "viewer")
    await viewer.insert()
    # Seed 25 suggestions.
    for i in range(25):
        candidate = _make_user(f"user-cand-{i:02d}", f"cand{i:02d}")
        await candidate.insert()
        await Suggestion(
            user_id=viewer.id,
            suggested_user_id=candidate.id,
            score=1.0 - i * 0.01,
            reasons=["mutual_taste"],
        ).insert()

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/suggestions?limit=100",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    # Capped at MAX_SUGGESTIONS_LIMIT (20).
    assert len(response.json()["suggestions"]) == 20


@pytest.mark.asyncio
async def test_suggestions_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/me/suggestions")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /users/me/suggestions/{suggested_user_id}/dismiss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_removes_from_suggestions_list(_clean_env: None, _clean_db: None) -> None:
    """Dismissing a candidate drops them from the read endpoint immediately."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    bob = _make_user("user-bob", "bob")
    for user in (viewer, alice, bob):
        await user.insert()

    for candidate, score in ((alice, 0.9), (bob, 0.6)):
        await Suggestion(
            user_id=viewer.id,
            suggested_user_id=candidate.id,
            score=score,
            reasons=["mutual_taste"],
        ).insert()

    client = TestClient(_make_app())
    response = client.post(
        f"/api/v1/users/me/suggestions/{alice.id}/dismiss",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 204, response.text

    # alice is gone from the list.
    list_response = client.get(
        "/api/v1/users/me/suggestions",
        headers={"X-User-Id": viewer.id},
    )
    ids = [entry["user"]["id"] for entry in list_response.json()["suggestions"]]
    assert ids == [bob.id]

    # The Suggestion row itself is gone from the collection.
    assert (
        await Suggestion.find_one({"user_id": viewer.id, "suggested_user_id": alice.id})
    ) is None
    # And a SuggestionDismissal exists for the cooling-off window.
    dismissal = await SuggestionDismissal.find_one(
        {"user_id": viewer.id, "suggested_user_id": alice.id}
    )
    assert dismissal is not None


@pytest.mark.asyncio
async def test_dismiss_is_idempotent(_clean_env: None, _clean_db: None) -> None:
    """Double-dismissing returns 204 both times and writes exactly one TTL row."""
    viewer = _make_user("user-viewer", "viewer")
    alice = _make_user("user-alice", "alice")
    await viewer.insert()
    await alice.insert()
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=alice.id,
        score=0.9,
        reasons=["mutual_taste"],
    ).insert()

    client = TestClient(_make_app())
    first = client.post(
        f"/api/v1/users/me/suggestions/{alice.id}/dismiss",
        headers={"X-User-Id": viewer.id},
    )
    second = client.post(
        f"/api/v1/users/me/suggestions/{alice.id}/dismiss",
        headers={"X-User-Id": viewer.id},
    )
    assert first.status_code == 204
    assert second.status_code == 204
    rows = await SuggestionDismissal.find(
        {"user_id": viewer.id, "suggested_user_id": alice.id}
    ).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_dismiss_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post("/api/v1/users/me/suggestions/user-anything/dismiss")
    assert response.status_code == 401
