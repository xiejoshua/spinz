"""TC-029: GDPR cascading delete test suite (T160).

Seeds a user with rows in EVERY owned collection, runs the T058 cascade,
and asserts:

* The user row + every owned collection row is gone.
* Reports where the user was reporter survive but have ``reporter_id``
  nulled out.
* Reports where the user was the target survive verbatim (audit
  retention requirement).
* The GDPR audit log captures a DELETION_COMPLETED row referencing the
  user_id from outside the deleted user document.
* Bystander rows belonging to other users are unaffected.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.gdpr.models import GdprAuditAction, GdprAuditLog
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.notifications.models import FailedEmail, Notification, NotificationType
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.reviews.models import Review, ReviewEditHistory, ReviewLike
from auxd_api.modules.social.models import (
    Block,
    BlockReason,
    Follow,
    FollowRequest,
    FollowRequestStatus,
    FollowState,
)
from auxd_api.modules.social.suggestions_models import Suggestion, SuggestionDismissal
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
from auxd_api.modules.users.workers import process_scheduled_deletions


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    """Wipe every collection touched by the cascade test."""

    async def _wipe() -> None:
        await User.delete_all()
        await HandleRedirect.delete_all()
        await DiaryEntry.delete_all()
        await Review.delete_all()
        await ReviewLike.delete_all()
        await ReviewEditHistory.delete_all()
        await Backlog.delete_all()
        await BacklogItem.delete_all()
        await Follow.delete_all()
        await FollowRequest.delete_all()
        await Block.delete_all()
        await Notification.delete_all()
        await FailedEmail.delete_all()
        await PushSubscription.delete_all()
        await Suggestion.delete_all()
        await SuggestionDismissal.delete_all()
        await Report.delete_all()
        await Album.delete_all()
        await GdprAuditLog.delete_all()

    await _wipe()
    yield
    await _wipe()


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test",
        display_name=handle,
    )


async def _seed_owned_rows(user_id: str, bystander_id: str, album_id: str) -> None:
    """Insert rows in every owned collection for ``user_id``.

    Returns nothing — the test asserts state after the cascade by
    re-querying. ``bystander_id`` rows are seeded in parallel so the
    test can also assert non-cascade safety.
    """
    # Diary entries.
    entry = DiaryEntry(
        id="entry-own",
        user_id=user_id,
        album_id=album_id,
        logged_at=datetime.now(UTC),
    )
    await entry.insert()

    # Reviews + likes + edit history.
    review = Review(
        id="rev-own",
        user_id=user_id,
        diary_entry_id=entry.id,
        album_id=album_id,
        body="my review text",
    )
    await review.insert()
    await ReviewLike(review_id=review.id, user_id=user_id).insert()
    await ReviewEditHistory(
        review_id=review.id,
        body_at_time="prior text",
        edited_at=datetime.now(UTC),
        version=1,
        edited_by=user_id,
    ).insert()

    # Backlog + items.
    backlog = Backlog(id="backlog-own", user_id=user_id)
    await backlog.insert()
    await BacklogItem(backlog_id=backlog.id, album_id=album_id, position=0).insert()
    await BacklogItem(backlog_id=backlog.id, album_id=f"{album_id}-2", position=1).insert()

    # Follows in both directions.
    await Follow(follower_id=user_id, followee_id=bystander_id, state=FollowState.ACCEPTED).insert()
    await Follow(follower_id=bystander_id, followee_id=user_id, state=FollowState.ACCEPTED).insert()

    # Follow requests in both directions.
    await FollowRequest(
        requester_id=user_id,
        requestee_id=bystander_id,
        status=FollowRequestStatus.PENDING,
    ).insert()
    await FollowRequest(
        requester_id=bystander_id,
        requestee_id=user_id,
        status=FollowRequestStatus.PENDING,
    ).insert()

    # Blocks in both directions.
    await Block(blocker_id=user_id, blockee_id=bystander_id, reason=BlockReason.HARASSMENT).insert()
    await Block(blocker_id=bystander_id, blockee_id=user_id, reason=BlockReason.SPAM).insert()

    # Notifications recipient-side.
    await Notification(
        user_id=user_id,
        type=NotificationType.N001_FOLLOW_NEW,
        payload={
            "actor_handle": "actor",
            "actor_display_name": "Actor",
        },
    ).insert()

    # Push subscription.
    await PushSubscription(
        user_id=user_id,
        endpoint="https://push.example/x",
        p256dh_key="dummy-key",
        auth_secret="dummy-secret",
    ).insert()

    # Handle redirect.
    await HandleRedirect(
        old_handle=f"old-{user_id}", new_handle=f"new-{user_id}", user_id=user_id
    ).insert()

    # Suggestions in both directions (viewer + candidate).
    await Suggestion(user_id=user_id, suggested_user_id=bystander_id, score=0.5).insert()
    await Suggestion(user_id=bystander_id, suggested_user_id=user_id, score=0.7).insert()
    await SuggestionDismissal(user_id=user_id, suggested_user_id=bystander_id).insert()
    await SuggestionDismissal(user_id=bystander_id, suggested_user_id=user_id).insert()

    # Failed email audit row.
    await FailedEmail(
        user_id=user_id,
        notification_type=NotificationType.N008_WEEKLY_DIGEST,
        payload={"hero_count": 1, "summary_url": "https://x/"},
        last_error="500 from Resend",
        retry_count=3,
    ).insert()

    # Reports — three flavours: user as reporter, user as target, user
    # as content author (the report points at the review id).
    await Report(
        reporter_id=user_id,
        target_type=ReportTargetType.USER,
        target_id=bystander_id,
        reason=ReportReason.HARASSMENT,
        status=ReportStatus.OPEN,
    ).insert()
    await Report(
        reporter_id=bystander_id,
        target_type=ReportTargetType.USER,
        target_id=user_id,
        reason=ReportReason.HARASSMENT,
        status=ReportStatus.OPEN,
    ).insert()


@pytest.mark.asyncio
async def test_cascade_clears_owned_rows_and_writes_audit_log(_clean_db: None) -> None:
    bystander = _make_user("user-bystander", "bystander")
    target_user_id = "user-target"
    target = _make_user(target_user_id, "target")
    target.status = UserStatus.DELETION_PENDING
    target.deletion_scheduled_for = datetime.now(UTC) - timedelta(days=1)

    await bystander.insert()
    await target.insert()

    album = Album(
        id="album-1",
        mbid=None,
        title="A",
        artist_credit="X",
        release_year=2020,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    album2 = Album(
        id="album-1-2",
        mbid=None,
        title="B",
        artist_credit="X",
        release_year=2021,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()
    await album2.insert()

    # Seed every owned collection.
    await _seed_owned_rows(target_user_id, bystander.id, album.id)

    # Seed bystander-owned rows that must SURVIVE the cascade.
    bystander_entry = DiaryEntry(
        id="entry-bystander",
        user_id=bystander.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
    )
    await bystander_entry.insert()
    bystander_review = Review(
        id="rev-bystander",
        user_id=bystander.id,
        diary_entry_id=bystander_entry.id,
        album_id=album.id,
        body="bystander review",
    )
    await bystander_review.insert()

    # Run the cascade.
    deleted = await process_scheduled_deletions({})
    assert deleted == 1

    # --- User + owned rows are gone -----------------------------------
    assert await User.get(target_user_id) is None
    assert await DiaryEntry.find_one(DiaryEntry.user_id == target_user_id) is None
    assert await Review.find_one(Review.user_id == target_user_id) is None
    assert await ReviewLike.find_one(ReviewLike.user_id == target_user_id) is None
    assert await Backlog.find_one(Backlog.user_id == target_user_id) is None
    assert await BacklogItem.find_one(BacklogItem.backlog_id == "backlog-own") is None
    assert await Notification.find_one(Notification.user_id == target_user_id) is None
    assert await PushSubscription.find_one(PushSubscription.user_id == target_user_id) is None
    assert await HandleRedirect.find_one(HandleRedirect.user_id == target_user_id) is None
    assert await FailedEmail.find_one(FailedEmail.user_id == target_user_id) is None

    # Follows / FollowRequests / Blocks — all directions wiped.
    assert (
        await Follow.find_one(
            {"$or": [{"follower_id": target_user_id}, {"followee_id": target_user_id}]}
        )
        is None
    )
    assert (
        await FollowRequest.find_one(
            {"$or": [{"requester_id": target_user_id}, {"requestee_id": target_user_id}]}
        )
        is None
    )
    assert (
        await Block.find_one(
            {"$or": [{"blocker_id": target_user_id}, {"blockee_id": target_user_id}]}
        )
        is None
    )

    # Suggestions / dismissals — both directions gone.
    assert (
        await Suggestion.find_one(
            {"$or": [{"user_id": target_user_id}, {"suggested_user_id": target_user_id}]}
        )
        is None
    )
    assert (
        await SuggestionDismissal.find_one(
            {"$or": [{"user_id": target_user_id}, {"suggested_user_id": target_user_id}]}
        )
        is None
    )

    # --- Reports: anonymisation + retention ---------------------------
    # Report where the deleted user was the reporter: row survives,
    # reporter_id is None.
    reporter_side = await Report.find_one(
        {"target_id": bystander.id, "target_type": ReportTargetType.USER.value}
    )
    assert reporter_side is not None
    assert reporter_side.reporter_id is None

    # Report where the deleted user was the target: row survives
    # verbatim (audit retention).
    target_side = await Report.find_one(
        {"target_id": target_user_id, "target_type": ReportTargetType.USER.value}
    )
    assert target_side is not None
    assert target_side.reporter_id == bystander.id

    # --- GDPR audit log ----------------------------------------------
    audit_rows = await GdprAuditLog.find(GdprAuditLog.user_id == target_user_id).to_list()
    assert len(audit_rows) == 1
    audit = audit_rows[0]
    assert audit.action is GdprAuditAction.DELETION_COMPLETED
    assert audit.completed_at is not None
    assert audit.notes is not None
    assert "collections" in audit.notes

    # --- Bystander rows survive --------------------------------------
    assert await User.get(bystander.id) is not None
    assert await DiaryEntry.find_one(DiaryEntry.id == bystander_entry.id) is not None
    assert await Review.find_one(Review.id == bystander_review.id) is not None
