"""Unit tests for :mod:`auxd_api.modules.users.workers` (T058).

Covers the deletion-cascade arq job: identifies due users, cascades
owned content, drops the user row, and emits observability events.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio

from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.notifications.models import Notification, NotificationType
from auxd_api.modules.reviews.models import Review, ReviewLike
from auxd_api.modules.social.models import Block, Follow, FollowRequest
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
from auxd_api.modules.users.workers import (
    _cascade_user_content,
    process_scheduled_deletions,
)


@pytest_asyncio.fixture
async def _clean() -> AsyncIterator[None]:
    await User.delete_all()
    await HandleRedirect.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await Block.delete_all()
    await Notification.delete_all()
    yield
    await User.delete_all()
    await HandleRedirect.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await Follow.delete_all()
    await FollowRequest.delete_all()
    await Block.delete_all()
    await Notification.delete_all()


async def _make_user(
    *,
    handle: str = "victim",
    email: str | None = None,
    status: UserStatus = UserStatus.ACTIVE,
    scheduled_for: datetime | None = None,
) -> User:
    user = User(
        handle=handle,
        email=email if email is not None else f"{handle}@example.com",
        display_name=handle,
        password_hash="$argon2id$dummy",
        status=status,
        deletion_scheduled_for=scheduled_for,
    )
    await user.insert()
    return user


# ---------------------------------------------------------------------------
# Sweep behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_due_deletions_cascade_clean(_clean: None) -> None:
    """Every owned row is removed and the User row is deleted."""
    now = datetime.now(UTC)
    victim = await _make_user(
        handle="victim",
        status=UserStatus.DELETION_PENDING,
        scheduled_for=now - timedelta(days=1),
    )
    bystander = await _make_user(handle="bystander", email="bystander@example.com")

    await DiaryEntry(
        user_id=victim.id,
        album_id="album-1",
        logged_at=now,
        rating=4.5,
        visibility=Visibility.PUBLIC,
    ).insert()
    review = Review(
        user_id=victim.id,
        diary_entry_id="diary-victim",
        album_id="album-1",
        body="bye",
        visibility="public",
    )
    await review.insert()
    await ReviewLike(review_id="other-review", user_id=victim.id).insert()
    backlog = Backlog(user_id=victim.id)
    await backlog.insert()
    await BacklogItem(backlog_id=backlog.id, album_id="album-2", position=1).insert()
    await Follow(follower_id=victim.id, followee_id=bystander.id).insert()
    await Follow(follower_id=bystander.id, followee_id=victim.id).insert()
    await FollowRequest(requester_id=victim.id, requestee_id=bystander.id).insert()
    await Block(blocker_id=victim.id, blockee_id=bystander.id).insert()
    await Notification(
        user_id=victim.id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={},
    ).insert()
    await HandleRedirect(
        old_handle="old_victim",
        new_handle="victim",
        user_id=victim.id,
    ).insert()
    # Bystander rows that MUST survive.
    await DiaryEntry(
        user_id=bystander.id,
        album_id="album-3",
        logged_at=now,
        rating=3.5,
        visibility=Visibility.PUBLIC,
    ).insert()

    deleted = await process_scheduled_deletions({})
    assert deleted == 1

    # The victim row + every owned doc is gone.
    assert await User.get(victim.id) is None
    assert await DiaryEntry.find(DiaryEntry.user_id == victim.id).to_list() == []
    assert await Review.find(Review.user_id == victim.id).to_list() == []
    assert await ReviewLike.find(ReviewLike.user_id == victim.id).to_list() == []
    assert await Backlog.find(Backlog.user_id == victim.id).to_list() == []
    assert await BacklogItem.find({"backlog_id": backlog.id}).to_list() == []
    assert (
        await Follow.find(
            {"$or": [{"follower_id": victim.id}, {"followee_id": victim.id}]}
        ).to_list()
        == []
    )
    assert (
        await FollowRequest.find(
            {"$or": [{"requester_id": victim.id}, {"requestee_id": victim.id}]}
        ).to_list()
        == []
    )
    assert (
        await Block.find({"$or": [{"blocker_id": victim.id}, {"blockee_id": victim.id}]}).to_list()
        == []
    )
    assert await Notification.find(Notification.user_id == victim.id).to_list() == []
    assert await HandleRedirect.find(HandleRedirect.user_id == victim.id).to_list() == []

    # The bystander is untouched.
    bystander_after = await User.get(bystander.id)
    assert bystander_after is not None
    assert await DiaryEntry.find(DiaryEntry.user_id == bystander.id).to_list(), (
        "bystander's diary survives"
    )


@pytest.mark.asyncio
async def test_not_yet_due_skipped(_clean: None) -> None:
    """Pending-deletion users whose grace hasn't expired are NOT processed."""
    future = datetime.now(UTC) + timedelta(days=10)
    user = await _make_user(
        handle="patient",
        status=UserStatus.DELETION_PENDING,
        scheduled_for=future,
    )
    deleted = await process_scheduled_deletions({})
    assert deleted == 0
    assert await User.get(user.id) is not None


@pytest.mark.asyncio
async def test_no_due_returns_zero(_clean: None) -> None:
    """No DELETION_PENDING rows → no work."""
    await _make_user(handle="alice")
    assert await process_scheduled_deletions({}) == 0


@pytest.mark.asyncio
async def test_cascade_only_helper_returns_counts(_clean: None) -> None:
    """The exported cascade helper returns the per-collection delete counts."""
    user = await _make_user(handle="counter")
    now = datetime.now(UTC)
    await DiaryEntry(
        user_id=user.id,
        album_id="album-1",
        logged_at=now,
        rating=4.0,
        visibility=Visibility.PUBLIC,
    ).insert()
    await DiaryEntry(
        user_id=user.id,
        album_id="album-2",
        logged_at=now,
        rating=4.5,
        visibility=Visibility.PUBLIC,
    ).insert()
    counts: dict[str, int] = await _cascade_user_content(user.id)
    assert counts["diary_entries"] == 2
    # All other collections empty → zero counts.
    for collection in (
        "reviews",
        "review_likes",
        "review_edit_history",
        "backlogs",
        "backlog_items",
        "follows",
        "follow_requests",
        "blocks",
        "notifications",
        "handle_redirects",
    ):
        assert counts[collection] == 0
    # The cascade helper does NOT delete the user row itself.
    assert await User.get(user.id) is not None


@pytest.mark.asyncio
async def test_ctx_is_optional(_clean: None) -> None:
    """The worker accepts any ctx shape (arq passes a dict)."""
    ctx: dict[str, Any] = {"arbitrary": "value"}
    assert await process_scheduled_deletions(ctx) == 0
