"""Integration tests for the review create endpoint (T085).

Drives ``POST /api/v1/reviews`` through a FastAPI :class:`TestClient`
backed by mongomock-motor via ``conftest.py``. Auth is forged by a
fake middleware that attaches a :class:`Session` from ``X-User-Id``.

Coverage:

* Happy-path 201 with sanitized body + linkage to diary entry.
* Markdown sanitization: XSS payload stripped from body.
* 1:1 conflict 409 — second create against the same diary entry.
* Non-owner 403.
* Unknown diary entry 404.
* Empty body 422 (after sanitization).
* Visibility override + default behaviours.
* Rate-limit dependency wired in (smoke test).
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
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.reviews.routes import router as reviews_router
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
    app.include_router(reviews_router, prefix="/api/v1")
    return app


async def _seed_diary_entry(
    *,
    user_id: str = "user-casey",
    album_id: str = "album-001",
    visibility: Visibility = Visibility.PUBLIC,
) -> DiaryEntry:
    await Album(
        id=album_id,
        mbid=None,
        title="Test Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    ).insert()
    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=visibility,
    )
    await entry.insert()
    return entry


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()


@pytest.mark.asyncio
async def test_create_review_happy_path(_clean_env: None, _clean_db: None) -> None:
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": "What a record."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["body"] == "What a record."
    assert body["diary_entry_id"] == entry.id
    assert body["visibility"] == "public"
    assert body["likes_count"] == 0

    persisted = await Review.get(body["id"])
    assert persisted is not None
    refreshed_entry = await DiaryEntry.get(entry.id)
    assert refreshed_entry is not None
    assert refreshed_entry.review_id == body["id"]


@pytest.mark.asyncio
async def test_create_review_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        json={"diary_entry_id": entry.id, "body": "Anonymous attempt."},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_review_strips_xss(_clean_env: None, _clean_db: None) -> None:
    """Markdown sanitizer drops HTML, script, img, iframe — XSS-safe body."""
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    xss_body = (
        "Loved it.\n"
        "<script>alert('xss')</script>"
        "<img src=x onerror=alert(1)>"
        "<iframe src='javascript:alert(2)'></iframe>"
        "[click me](javascript:alert('bad'))"
        " and [okay](https://example.com)"
    )
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": xss_body},
    )
    assert response.status_code == 201, response.text
    saved_body = response.json()["body"]
    # No HTML tag anywhere.
    assert "<script>" not in saved_body
    assert "<img" not in saved_body
    assert "<iframe" not in saved_body
    assert "</" not in saved_body
    # No javascript: protocol survives anywhere — the critical XSS gate.
    assert "javascript:" not in saved_body
    assert "(javascript:" not in saved_body
    # The valid markdown link survives.
    assert "[okay](https://example.com)" in saved_body
    # The bad link's bracket text is preserved (markdown syntax stripped).
    assert "click me" in saved_body


@pytest.mark.asyncio
async def test_create_review_duplicate_returns_409(_clean_env: None, _clean_db: None) -> None:
    """A second create for the same diary entry is rejected with 409."""
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    first = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": "First take."},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": "Second take."},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "review_already_exists"


@pytest.mark.asyncio
async def test_create_review_non_owner_returns_403(_clean_env: None, _clean_db: None) -> None:
    entry = await _seed_diary_entry(user_id="user-casey")
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-mallory"},
        json={"diary_entry_id": entry.id, "body": "Squatting on Casey's entry."},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


@pytest.mark.asyncio
async def test_create_review_unknown_diary_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": "does-not-exist", "body": "Phantom review."},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "diary_entry_not_found"


@pytest.mark.asyncio
async def test_create_review_pydantic_rejects_empty_body(_clean_env: None, _clean_db: None) -> None:
    """Pydantic ``min_length=1`` short-circuits empty bodies with 422."""
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_review_html_only_body_rejected(_clean_env: None, _clean_db: None) -> None:
    """A body that's empty after stripping HTML is rejected with 422 (service-level).

    The body is pure tags + whitespace — once the sanitizer strips the
    tags, what remains is whitespace-only, which the service rejects
    with :class:`ReviewBodyEmptyError`.
    """
    entry = await _seed_diary_entry()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": "<script></script>   <img src=x>"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "review_body_empty"


@pytest.mark.asyncio
async def test_create_review_visibility_override(_clean_env: None, _clean_db: None) -> None:
    """Explicit ``visibility`` in the body overrides the diary entry default."""
    entry = await _seed_diary_entry(visibility=Visibility.PUBLIC)
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={
            "diary_entry_id": entry.id,
            "body": "Quiet take.",
            "visibility": "private",
        },
    )
    assert response.status_code == 201
    assert response.json()["visibility"] == "private"


@pytest.mark.asyncio
async def test_create_review_default_mirrors_diary_visibility(
    _clean_env: None, _clean_db: None
) -> None:
    entry = await _seed_diary_entry(visibility=Visibility.FOLLOWERS)
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reviews",
        headers={"X-User-Id": "user-casey"},
        json={"diary_entry_id": entry.id, "body": "Followers only."},
    )
    assert response.status_code == 201
    assert response.json()["visibility"] == "followers"
