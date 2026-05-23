"""Account-deletion cascade worker (T058).

Daily 02:00 UTC arq cron job that finds every User with
``status == DELETION_PENDING`` and ``deletion_scheduled_for <= now`` then
cascade-hard-deletes all owned content before removing the User row
itself. US-G5 / FR-019 governs the policy; the grace window is set by
:data:`auxd_api.modules.users.service.ACCOUNT_DELETION_GRACE` (30 days).

Cascade order matters: child rows go first so a partial failure leaves
the User row intact (the next sweep will retry). Specifically:

1. DiaryEntry — soft-deleted entries are wiped too; the 30-day grace
   already covered the user-side undo affordance.
2. Review / ReviewLike / ReviewEditHistory — review edit history is
   preserved while the review still exists; once the review is gone the
   audit log is meaningless.
3. Backlog + BacklogItem — fetch the user's Backlog id first so we can
   delete its children in a single query.
4. Follow / FollowRequest — both directions.
5. Block — both directions.
6. Notification — recipient-side cleanup.
7. HandleRedirect — drop any redirects owned by this user.
8. Finally, delete the User row.

Per-step ``log_call`` lines preserve an audit trail in the structured
log stream so ops can reconstruct exactly what cascade ran on which
user. A single PostHog ``account.deleted`` event closes the funnel.

Bounded per run (max 25 users) so a flood of expired schedules can't
exhaust the worker's wall-clock budget; the next run picks up any
leftovers tomorrow.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.notifications.models import Notification
from auxd_api.modules.reviews.models import Review, ReviewEditHistory, ReviewLike
from auxd_api.modules.social.models import Block, Follow, FollowRequest
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus

_LOGGER = logging.getLogger("auxd.worker.users")

# Cap per-run row count. 25 users × ~9 cascade steps = ~225 collection
# ops per sweep — comfortably under the daily window without risking
# the worker spinning on a backlog.
_BATCH_LIMIT = 25

__all__ = [
    "_cascade_user_content",  # exported for unit tests
    "process_scheduled_deletions",
]


async def _cascade_user_content(user_id: str) -> dict[str, int]:
    """Delete every row owned by ``user_id`` across the data model.

    Returns a per-collection deletion count for observability. The User
    row itself is NOT deleted here — the caller decides whether to
    finish the cascade or hold off (e.g. for tests that want to assert
    cascade behaviour separately from user removal).
    """
    counts: dict[str, int] = {}

    # 1. Diary entries (including soft-deleted ones — the 30-day undo
    #    window already covered the user-side affordance).
    diary_result = await DiaryEntry.find(DiaryEntry.user_id == user_id).delete()
    counts["diary_entries"] = (diary_result.deleted_count if diary_result else 0) or 0

    # 2. Reviews + likes + edit history.
    review_ids = [review.id async for review in Review.find(Review.user_id == user_id)]
    review_result = await Review.find(Review.user_id == user_id).delete()
    counts["reviews"] = (review_result.deleted_count if review_result else 0) or 0
    like_result = await ReviewLike.find(ReviewLike.user_id == user_id).delete()
    counts["review_likes"] = (like_result.deleted_count if like_result else 0) or 0
    if review_ids:
        edit_result = await ReviewEditHistory.find({"review_id": {"$in": review_ids}}).delete()
        counts["review_edit_history"] = (edit_result.deleted_count if edit_result else 0) or 0
    else:
        counts["review_edit_history"] = 0

    # 3. Backlog container + items.
    backlog_ids = [b.id async for b in Backlog.find(Backlog.user_id == user_id)]
    backlog_result = await Backlog.find(Backlog.user_id == user_id).delete()
    counts["backlogs"] = (backlog_result.deleted_count if backlog_result else 0) or 0
    if backlog_ids:
        item_result = await BacklogItem.find({"backlog_id": {"$in": backlog_ids}}).delete()
        counts["backlog_items"] = (item_result.deleted_count if item_result else 0) or 0
    else:
        counts["backlog_items"] = 0

    # 4. Follows in either direction.
    follow_result = await Follow.find(
        {"$or": [{"follower_id": user_id}, {"followee_id": user_id}]}
    ).delete()
    counts["follows"] = (follow_result.deleted_count if follow_result else 0) or 0
    request_result = await FollowRequest.find(
        {"$or": [{"requester_id": user_id}, {"requestee_id": user_id}]}
    ).delete()
    counts["follow_requests"] = (request_result.deleted_count if request_result else 0) or 0

    # 5. Blocks in either direction.
    block_result = await Block.find(
        {"$or": [{"blocker_id": user_id}, {"blockee_id": user_id}]}
    ).delete()
    counts["blocks"] = (block_result.deleted_count if block_result else 0) or 0

    # 6. Notifications recipient-side.
    notif_result = await Notification.find(Notification.user_id == user_id).delete()
    counts["notifications"] = (notif_result.deleted_count if notif_result else 0) or 0

    # 7. Handle redirects owned by this user.
    redirect_result = await HandleRedirect.find(HandleRedirect.user_id == user_id).delete()
    counts["handle_redirects"] = (redirect_result.deleted_count if redirect_result else 0) or 0

    return counts


async def process_scheduled_deletions(ctx: dict[str, Any]) -> int:
    """Cascade-hard-delete every user whose grace window has expired.

    Returns the count of users actually deleted on this run. Per-user
    failures are not currently retried inline — a future iteration may
    move the loop into individual try/except blocks once we have
    representative data on which collections fail.
    """
    _ = ctx  # arq passes the worker context; this job needs no resources from it.
    now = datetime.now(UTC)
    due = (
        await User.find(
            {
                "status": UserStatus.DELETION_PENDING.value,
                "deletion_scheduled_for": {"$lte": now},
            }
        )
        .limit(_BATCH_LIMIT)
        .to_list()
    )
    deleted = 0
    for user in due:
        user_id = user.id
        counts = await _cascade_user_content(user_id)
        # Finally drop the User row.
        await user.delete()
        deleted += 1
        log_call(
            provider="auxd",
            endpoint="users.account_deleted",
            latency_ms=0.0,
            status="ok",
            extra={"user_id": user_id, **counts},
        )
        emit_event(
            user_id=user_id,
            event="account.deleted",
            properties=counts,
        )
    log_call(
        provider="auxd",
        endpoint="users.deletion_sweep_completed",
        latency_ms=0.0,
        status="ok",
        extra={"deleted": deleted, "scanned": len(due)},
    )
    return deleted
