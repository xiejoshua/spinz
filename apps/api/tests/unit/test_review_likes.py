"""Unit tests for the review-likes service (T088).

Drives :func:`auxd_api.modules.reviews.likes_service.like_review` and
:func:`unlike_review` directly against the mongomock-motor backing
store. These cover the in-memory counter math + ``recent_likers``
trimming behaviour that the integration tests rely on but don't
exercise to the same density.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.likes_service import (
    RECENT_LIKERS_CAP,
    ReviewLikeNotFoundError,
    SelfLikeError,
    like_review,
    unlike_review,
)
from auxd_api.modules.reviews.models import Review, ReviewLike


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await ReviewLike.delete_all()


async def _make_review_row(
    *,
    owner_id: str = "user-author",
    album_id: str = "album-001",
) -> Review:
    """Seed an album, diary entry, and review owned by ``owner_id``."""
    await Album(
        id=album_id,
        mbid=None,
        title="Test",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    ).insert()
    entry = DiaryEntry(
        user_id=owner_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await entry.insert()
    review = Review(
        user_id=owner_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body="Solid record.",
        visibility="public",
    )
    await review.insert()
    return review


@pytest.mark.asyncio
async def test_like_review_increments_counter_and_writes_row(_clean_db: None) -> None:
    review = await _make_review_row()
    result = await like_review(review_id=review.id, user_id="user-fan")
    assert result.liked is True
    assert result.likes_count == 1

    persisted = await Review.get(review.id)
    assert persisted is not None
    assert persisted.reactions.likes_count == 1
    assert persisted.reactions.recent_likers == ["user-fan"]

    rows = await ReviewLike.find({"review_id": review.id, "user_id": "user-fan"}).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_like_review_self_like_rejected(_clean_db: None) -> None:
    """TC-016: liking your own review is rejected with SelfLikeError."""
    review = await _make_review_row(owner_id="user-author")
    with pytest.raises(SelfLikeError):
        await like_review(review_id=review.id, user_id="user-author")


@pytest.mark.asyncio
async def test_like_review_idempotent_no_double_increment(_clean_db: None) -> None:
    review = await _make_review_row()
    first = await like_review(review_id=review.id, user_id="user-fan")
    second = await like_review(review_id=review.id, user_id="user-fan")
    assert first.likes_count == 1
    assert second.likes_count == 1
    persisted = await Review.get(review.id)
    assert persisted is not None
    assert persisted.reactions.likes_count == 1
    rows = await ReviewLike.find({"review_id": review.id, "user_id": "user-fan"}).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_like_review_recent_likers_capped(_clean_db: None) -> None:
    """``recent_likers`` is FIFO-trimmed at :data:`RECENT_LIKERS_CAP`."""
    review = await _make_review_row()
    for i in range(RECENT_LIKERS_CAP + 5):
        await like_review(review_id=review.id, user_id=f"fan-{i}")
    persisted = await Review.get(review.id)
    assert persisted is not None
    # The most recent like prepends to recent_likers, so the tail is
    # dropped — list size stays at the cap.
    assert len(persisted.reactions.recent_likers) == RECENT_LIKERS_CAP
    # The most recent liker is at the head.
    assert persisted.reactions.recent_likers[0] == f"fan-{RECENT_LIKERS_CAP + 4}"
    # The very first liker has been evicted.
    assert "fan-0" not in persisted.reactions.recent_likers


@pytest.mark.asyncio
async def test_unlike_review_decrements_and_removes_row(_clean_db: None) -> None:
    review = await _make_review_row()
    await like_review(review_id=review.id, user_id="user-fan")
    result = await unlike_review(review_id=review.id, user_id="user-fan")
    assert result.liked is False
    assert result.likes_count == 0

    persisted = await Review.get(review.id)
    assert persisted is not None
    assert persisted.reactions.likes_count == 0
    assert "user-fan" not in persisted.reactions.recent_likers

    rows = await ReviewLike.find({"review_id": review.id, "user_id": "user-fan"}).to_list()
    assert rows == []


@pytest.mark.asyncio
async def test_unlike_review_idempotent_when_never_liked(_clean_db: None) -> None:
    """Un-liking a review the user never liked is a benign no-op."""
    review = await _make_review_row()
    result = await unlike_review(review_id=review.id, user_id="user-never-liked")
    assert result.liked is False
    assert result.likes_count == 0


@pytest.mark.asyncio
async def test_like_review_missing_review_raises(_clean_db: None) -> None:
    with pytest.raises(ReviewLikeNotFoundError):
        await like_review(review_id="does-not-exist", user_id="user-fan")


@pytest.mark.asyncio
async def test_like_review_deleted_review_raises(_clean_db: None) -> None:
    review = await _make_review_row()
    review.deleted_at = datetime.now(UTC)
    await review.save()
    with pytest.raises(ReviewLikeNotFoundError):
        await like_review(review_id=review.id, user_id="user-fan")


@pytest.mark.asyncio
async def test_unlike_review_missing_review_raises(_clean_db: None) -> None:
    with pytest.raises(ReviewLikeNotFoundError):
        await unlike_review(review_id="does-not-exist", user_id="user-fan")
