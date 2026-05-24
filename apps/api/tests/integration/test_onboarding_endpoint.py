"""Integration tests for ``GET /api/v1/onboarding/cards`` (T117a HTTP surface)."""

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
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.seeding.routes import router as seeding_router
from auxd_api.modules.users.models import User
from tests.integration._auth_helpers import FakeAuthMiddleware


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT", "DISCOGS_API_TOKEN"):
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
    app.include_router(seeding_router, prefix="/api/v1")
    return app


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await CriticSeed.delete_all()
    await User.delete_all()
    yield
    await CriticSeed.delete_all()
    await User.delete_all()


async def _seed_critic(handle: str, *, priority: int = 50, active: bool = True) -> User:
    user = User(
        id=f"user-{handle}",
        handle=handle,
        email=f"{handle}@ex.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.replace("_", " ").title(),
        avatar_url=None,
        bio=f"{handle} bio",
    )
    await user.insert()
    await CriticSeed(
        id=f"seed-{handle}",
        user_id=user.id,
        priority=priority,
        active=active,
        genre_signature=["pop"],
        public_bio=f"public bio for {handle}",
    ).insert()
    return user


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/onboarding/cards")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_returns_pre_checked_primary_and_unchecked_secondary(
    _clean_env: None, _clean_db: None
) -> None:
    for i in range(10):
        await _seed_critic(f"crit_{i:02d}", priority=100 - i)
    # Also create the viewer (not a critic).
    await _seed_critic("viewer", priority=0, active=False)
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/onboarding/cards",
        headers={"X-User-Id": "user-viewer"},
    )
    assert response.status_code == 200
    body = response.json()
    cards = body["cards"]
    assert len(cards) == 10
    assert sum(1 for c in cards if c["pre_checked"]) == 6
    assert sum(1 for c in cards if not c["pre_checked"]) == 4


@pytest.mark.asyncio
async def test_card_payload_includes_user_fields(_clean_env: None, _clean_db: None) -> None:
    """Each card carries denormalised user info — handle, display_name, bio, avatar."""
    await _seed_critic("featured_critic", priority=99)
    await _seed_critic("viewer", priority=0, active=False)
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/onboarding/cards",
        headers={"X-User-Id": "user-viewer"},
    )
    body = response.json()
    card = body["cards"][0]
    assert card["user"]["handle"] == "featured_critic"
    assert card["user"]["display_name"] == "Featured Critic"
    assert card["user"]["bio"] == "public bio for featured_critic"
    assert card["pre_checked"] is True
    assert card["source"] == "onboarding_preselected"
    assert "score" in card
    assert "genre_signature" in card


@pytest.mark.asyncio
async def test_smaller_roster_returns_smaller_deck(_clean_env: None, _clean_db: None) -> None:
    """3 critics in the DB → 3 cards in the response (no padding)."""
    for i in range(3):
        await _seed_critic(f"crit_{i}", priority=80 - i)
    await _seed_critic("viewer", priority=0, active=False)
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/onboarding/cards",
        headers={"X-User-Id": "user-viewer"},
    )
    assert response.status_code == 200
    assert len(response.json()["cards"]) == 3


@pytest.mark.asyncio
async def test_orphan_critic_seed_skipped_not_500(_clean_env: None, _clean_db: None) -> None:
    """A CriticSeed whose underlying User was hard-deleted is silently dropped."""
    await CriticSeed(
        id="seed-orphan",
        user_id="user-deleted",
        priority=99,
        active=True,
        genre_signature=[],
        public_bio="orphan bio",
    ).insert()
    await _seed_critic("real_critic", priority=50)
    await _seed_critic("viewer", priority=0, active=False)
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/onboarding/cards",
        headers={"X-User-Id": "user-viewer"},
    )
    assert response.status_code == 200
    handles = [card["user"]["handle"] for card in response.json()["cards"]]
    assert "real_critic" in handles
    assert len(handles) == 1
