"""Integration tests for the daily moderation log-scan worker (T156).

Covers :func:`auxd_api.workers.moderation_scan.scan_reports_for_flags`:

* Empty reports collection → no flags.
* User with 2 reports → not flagged (below threshold).
* User with 3+ reports → flagged + Discord webhook called.
* Idempotent re-run within 7d → no double-flag, no extra Discord post.
* Review / diary report counts resolve to the author and add to the
  user's report tally.
* When ``DISCORD_WEBHOOK_URL`` is unset, the flag is still applied —
  the webhook call is just skipped.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.users.models import User
from auxd_api.workers import moderation_scan as scan_module
from auxd_api.workers.moderation_scan import scan_reports_for_flags


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "DISCORD_WEBHOOK_URL",
    ):
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


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test",
        display_name=handle,
    )


def _make_report(
    reporter_id: str,
    target_type: ReportTargetType,
    target_id: str,
    reason: ReportReason = ReportReason.HARASSMENT,
) -> Report:
    return Report(
        reporter_id=reporter_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        detail="",
        status=ReportStatus.OPEN,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def _capture_discord(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the real Discord HTTP call with an in-memory capture list."""
    calls: list[dict[str, Any]] = []

    async def _fake_post(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(scan_module, "_post_discord_alert", _fake_post)
    return calls


@pytest.mark.asyncio
async def test_empty_reports_does_nothing(
    _clean_env: None, _clean_db: None, _capture_discord: list[dict[str, Any]]
) -> None:
    flagged = await scan_reports_for_flags({})
    assert flagged == 0
    assert _capture_discord == []


@pytest.mark.asyncio
async def test_two_reports_below_threshold(
    _clean_env: None, _clean_db: None, _capture_discord: list[dict[str, Any]]
) -> None:
    target = _make_user("user-target", "target")
    await target.insert()
    for reporter_id in ("u1", "u2"):
        await _make_report(reporter_id, ReportTargetType.USER, target.id).insert()

    flagged = await scan_reports_for_flags({})
    assert flagged == 0
    persisted = await User.get(target.id)
    assert persisted is not None
    assert persisted.flagged_for_review is False
    assert _capture_discord == []


@pytest.mark.asyncio
async def test_three_reports_flags_user_and_posts_discord(
    _clean_env: None,
    _clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    _capture_discord: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/hook")
    settings_module.get_settings.cache_clear()

    target = _make_user("user-target", "target")
    await target.insert()
    for reporter_id in ("u1", "u2", "u3"):
        await _make_report(reporter_id, ReportTargetType.USER, target.id).insert()

    flagged = await scan_reports_for_flags({})
    assert flagged == 1

    persisted = await User.get(target.id)
    assert persisted is not None
    assert persisted.flagged_for_review is True
    assert persisted.flagged_for_review_at is not None

    assert len(_capture_discord) == 1
    call = _capture_discord[0]
    assert call["handle"] == "target"
    assert call["user_id"] == target.id
    assert call["count"] == 3
    assert "harassment" in call["reason_summary"]


@pytest.mark.asyncio
async def test_idempotent_rerun_within_7d_does_not_double_flag(
    _clean_env: None,
    _clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    _capture_discord: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/hook")
    settings_module.get_settings.cache_clear()

    target = _make_user("user-target", "target")
    await target.insert()
    for reporter_id in ("u1", "u2", "u3"):
        await _make_report(reporter_id, ReportTargetType.USER, target.id).insert()

    first = await scan_reports_for_flags({})
    second = await scan_reports_for_flags({})
    assert first == 1
    assert second == 0  # already flagged within 7d
    assert len(_capture_discord) == 1  # no extra Discord post


@pytest.mark.asyncio
async def test_review_and_diary_reports_resolve_to_author(
    _clean_env: None,
    _clean_db: None,
    _capture_discord: list[dict[str, Any]],
) -> None:
    """Reports against a user's content count toward the user's tally."""
    author = _make_user("user-author", "author")
    await author.insert()
    album = Album(
        id="album-1",
        mbid=None,
        title="A",
        artist_credit="X",
        release_year=2020,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()
    entry = DiaryEntry(
        id="entry-1",
        user_id=author.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
    )
    await entry.insert()
    review = Review(
        id="rev-1",
        user_id=author.id,
        diary_entry_id=entry.id,
        album_id=album.id,
        body="text",
    )
    await review.insert()

    # 1 direct user report, 1 review report, 1 diary entry report → 3 total.
    await _make_report("u1", ReportTargetType.USER, author.id).insert()
    await _make_report("u2", ReportTargetType.REVIEW, review.id, ReportReason.SPAM).insert()
    await _make_report("u3", ReportTargetType.DIARY_ENTRY, entry.id, ReportReason.NSFW).insert()

    flagged = await scan_reports_for_flags({})
    assert flagged == 1
    persisted = await User.get(author.id)
    assert persisted is not None
    assert persisted.flagged_for_review is True


@pytest.mark.asyncio
async def test_no_discord_url_still_flags(
    _clean_env: None,
    _clean_db: None,
    _capture_discord: list[dict[str, Any]],
) -> None:
    """``DISCORD_WEBHOOK_URL`` unset → flag applies, Discord call skipped."""
    target = _make_user("user-target", "target")
    await target.insert()
    for reporter_id in ("u1", "u2", "u3"):
        await _make_report(reporter_id, ReportTargetType.USER, target.id).insert()

    flagged = await scan_reports_for_flags({})
    assert flagged == 1
    persisted = await User.get(target.id)
    assert persisted is not None
    assert persisted.flagged_for_review is True
    assert _capture_discord == []  # no webhook call.


@pytest.mark.asyncio
async def test_old_reports_outside_7d_window_do_not_count(
    _clean_env: None,
    _clean_db: None,
    _capture_discord: list[dict[str, Any]],
) -> None:
    """Reports older than 7 days are ignored by the aggregation."""
    target = _make_user("user-target", "target")
    await target.insert()
    old = datetime.now(UTC) - timedelta(days=10)
    for reporter_id in ("u1", "u2", "u3"):
        row = _make_report(reporter_id, ReportTargetType.USER, target.id)
        row.created_at = old
        await row.insert()

    flagged = await scan_reports_for_flags({})
    assert flagged == 0
    persisted = await User.get(target.id)
    assert persisted is not None
    assert persisted.flagged_for_review is False
