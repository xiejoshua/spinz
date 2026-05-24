"""Integration tests for the content-report endpoints (T155 + T163a).

Covers ``POST /api/v1/reports/user``, ``POST /api/v1/reports/review``,
``POST /api/v1/reports/diary-entry``:

* 401 unauthenticated on all three.
* 201 happy path each route with the right target_type set.
* 422 invalid reason (e.g. ``catalog_gap`` smuggled into a content
  report).
* 422 target_id doesn't exist (FK validation).
* Idempotency: same reporter+target within 24h returns the existing
  report with 200 (not a duplicate 201).
* Per-day rate-limit boundary (11th report in 24h → 429).
* Cannot self-report (reporter_id == target_id → 422).
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
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportTargetType,
)
from auxd_api.modules.reports.routes import router as reports_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User
from tests.integration._auth_helpers import FakeAuthMiddleware


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


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Report.delete_all()
    await User.delete_all()
    await Review.delete_all()
    await DiaryEntry.delete_all()
    await Album.delete_all()
    yield
    await Report.delete_all()
    await User.delete_all()
    await Review.delete_all()
    await DiaryEntry.delete_all()
    await Album.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(reports_router, prefix="/api/v1")
    return app


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test",
        display_name=handle.capitalize(),
    )


def _make_album(album_id: str = "album-1") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="Test Album",
        artist_credit="Test Artist",
        release_year=2020,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_review(
    review_id: str,
    user_id: str,
    *,
    diary_entry_id: str,
    album_id: str = "album-1",
) -> Review:
    return Review(
        id=review_id,
        user_id=user_id,
        diary_entry_id=diary_entry_id,
        album_id=album_id,
        body="Loved it",
    )


def _make_diary_entry(entry_id: str, user_id: str, album_id: str = "album-1") -> DiaryEntry:
    return DiaryEntry(
        id=entry_id,
        user_id=user_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: skip the rate-limit check so per-test setup is simple.

    Individual tests that want to exercise the limit override
    :func:`_check_and_record` directly. Without this autouse, every test
    would need to monkeypatch Redis to avoid the limiter's "no Redis →
    fail open" path emitting Sentry alerts in test logs.
    """
    from auxd_api.lib import rate_limit as rate_limit_module

    async def _allow_all(**_: object) -> bool:
        return True

    monkeypatch.setattr(rate_limit_module, "_check_and_record", _allow_all)


# ---------------------------------------------------------------------------
# 401 unauthenticated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_user_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": "user-target", "reason": "harassment"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_review_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/review",
        json={"review_id": "rev-1", "reason": "spam"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_diary_entry_unauthenticated_returns_401(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/diary-entry",
        json={"entry_id": "entry-1", "reason": "other"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 201 happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_user_creates_row_with_target_type_user(
    _clean_env: None, _clean_db: None
) -> None:
    reporter = _make_user("user-reporter", "reporter")
    target = _make_user("user-target", "target")
    await reporter.insert()
    await target.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": target.id, "reason": "harassment", "detail": "bad behaviour"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["target_type"] == "user"
    assert body["target_id"] == target.id
    assert body["created"] is True

    persisted = await Report.get(body["report_id"])
    assert persisted is not None
    assert persisted.reporter_id == reporter.id
    assert persisted.target_type is ReportTargetType.USER
    assert persisted.target_id == target.id
    assert persisted.reason is ReportReason.HARASSMENT
    assert persisted.detail == "bad behaviour"


@pytest.mark.asyncio
async def test_report_review_creates_row_with_target_type_review(
    _clean_env: None, _clean_db: None
) -> None:
    reporter = _make_user("user-reporter", "reporter")
    author = _make_user("user-author", "author")
    album = _make_album()
    entry = _make_diary_entry("entry-for-rev", author.id)
    review = _make_review("rev-1", author.id, diary_entry_id=entry.id)
    await reporter.insert()
    await author.insert()
    await album.insert()
    await entry.insert()
    await review.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/review",
        json={"review_id": review.id, "reason": "spam"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["target_type"] == "review"
    persisted = await Report.get(body["report_id"])
    assert persisted is not None
    assert persisted.target_type is ReportTargetType.REVIEW
    assert persisted.target_id == review.id


@pytest.mark.asyncio
async def test_report_diary_entry_creates_row_with_target_type_diary_entry(
    _clean_env: None, _clean_db: None
) -> None:
    reporter = _make_user("user-reporter", "reporter")
    author = _make_user("user-author", "author")
    album = _make_album()
    entry = _make_diary_entry("entry-1", author.id)
    await reporter.insert()
    await author.insert()
    await album.insert()
    await entry.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/diary-entry",
        json={"entry_id": entry.id, "reason": "nsfw"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 201, response.text
    persisted = await Report.get(response.json()["report_id"])
    assert persisted is not None
    assert persisted.target_type is ReportTargetType.DIARY_ENTRY
    assert persisted.target_id == entry.id


# ---------------------------------------------------------------------------
# 422 invalid reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_gap_reason_rejected_on_user_report(
    _clean_env: None, _clean_db: None
) -> None:
    reporter = _make_user("user-reporter", "reporter")
    target = _make_user("user-target", "target")
    await reporter.insert()
    await target.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": target.id, "reason": "catalog_gap"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_reason"


@pytest.mark.asyncio
async def test_made_up_reason_rejected_by_pydantic(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    target = _make_user("user-target", "target")
    await reporter.insert()
    await target.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": target.id, "reason": "totally_not_real"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422  # Pydantic enum-validation error


# ---------------------------------------------------------------------------
# 422 target doesn't exist (FK validation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_target_not_found_returns_422(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    await reporter.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": "does-not-exist", "reason": "harassment"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "target_not_found"


@pytest.mark.asyncio
async def test_review_target_not_found_returns_422(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    await reporter.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/review",
        json={"review_id": "does-not-exist", "reason": "spam"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "target_not_found"


@pytest.mark.asyncio
async def test_diary_entry_target_not_found_returns_422(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-reporter", "reporter")
    await reporter.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/diary-entry",
        json={"entry_id": "does-not-exist", "reason": "other"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "target_not_found"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeat_report_within_24h_returns_existing_row(
    _clean_env: None, _clean_db: None
) -> None:
    reporter = _make_user("user-reporter", "reporter")
    target = _make_user("user-target", "target")
    await reporter.insert()
    await target.insert()
    client = TestClient(_make_app())
    body = {"user_id": target.id, "reason": "harassment"}
    first = client.post("/api/v1/reports/user", json=body, headers={"X-User-Id": reporter.id})
    assert first.status_code == 201
    first_id = first.json()["report_id"]

    second = client.post("/api/v1/reports/user", json=body, headers={"X-User-Id": reporter.id})
    assert second.status_code == 200  # idempotent — not 201.
    assert second.json()["report_id"] == first_id
    assert second.json()["created"] is False

    # Only one row was actually written.
    rows = await Report.find(
        {
            "reporter_id": reporter.id,
            "target_type": ReportTargetType.USER.value,
            "target_id": target.id,
        }
    ).to_list()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Self-report rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_self_report_user(_clean_env: None, _clean_db: None) -> None:
    reporter = _make_user("user-self", "self")
    await reporter.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/reports/user",
        json={"user_id": reporter.id, "reason": "harassment"},
        headers={"X-User-Id": reporter.id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "self_report_forbidden"


# ---------------------------------------------------------------------------
# Rate limit (per-reporter 10/day)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_fires_after_ten_reports_in_24h(
    _clean_env: None,
    _clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace the autouse skip with a deterministic over-budget signal."""
    from auxd_api.lib import rate_limit as rate_limit_module

    state = {"count": 0}

    async def _counting(*, bucket_key: str, limit: rate_limit_module.RateLimit) -> bool:
        _ = bucket_key
        state["count"] += 1
        return state["count"] <= limit.limit

    monkeypatch.setattr(rate_limit_module, "_check_and_record", _counting)

    reporter = _make_user("user-reporter", "reporter")
    targets = [_make_user(f"user-target-{i}", f"trg{i}") for i in range(11)]
    await reporter.insert()
    for t in targets:
        await t.insert()

    client = TestClient(_make_app())
    last_status: int | None = None
    for i in range(11):
        resp = client.post(
            "/api/v1/reports/user",
            json={"user_id": targets[i].id, "reason": "harassment"},
            headers={"X-User-Id": reporter.id},
        )
        last_status = resp.status_code
        if i < 10:
            assert resp.status_code == 201, f"call {i}: {resp.text}"
    assert last_status == 429
