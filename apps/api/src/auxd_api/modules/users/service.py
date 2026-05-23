"""User-account service layer — handle change + account deletion (T057, T058).

Splits the business logic out of the routes module so unit tests can
exercise the policy decisions (30-day cooldown, cascade order) without
HTTP plumbing. Errors are encoded as ``UserError`` subclasses so the
route layer can map them to precise HTTP responses.

Lifecycle covered here:

* :func:`change_handle` — enforce the 30-day cooldown, reserved-list
  rejection, uniqueness check; on success, write a
  :class:`HandleRedirect` row and mutate the User in place.
* :func:`schedule_account_deletion` — flip ``status`` to
  ``DELETION_PENDING``, set ``deletion_scheduled_for = now + 30d``,
  bump ``session_version`` so other devices log out.
* :func:`cancel_account_deletion` — flip back to ``ACTIVE`` and clear
  the scheduled-for timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from auxd_api.modules.auth.service import (
    AuthError,
    DuplicateHandleError,
    ReservedHandleError,
    validate_handle_format,
)
from auxd_api.modules.users.models import HandleRedirect, User, UserStatus
from auxd_api.modules.users.reserved import is_reserved_handle

__all__ = [
    "AccountDeletionState",
    "HandleChangeResult",
    "HandleChangeTooSoonError",
    "UserError",
    "cancel_account_deletion",
    "change_handle",
    "schedule_account_deletion",
]


# Policy constant — the 30-day cooldown is shared between
# initial-creation lock and post-change cooldown (FR-029 / Q16).
HANDLE_CHANGE_COOLDOWN = timedelta(days=30)

# Account-deletion grace window per US-G5 / FR-019.
ACCOUNT_DELETION_GRACE = timedelta(days=30)


class UserError(AuthError):
    """Base class for user-service errors. Inherits :class:`AuthError` so
    the auth route layer can reuse :func:`_auth_error_response`-style
    mapping if a future endpoint wants symmetric behaviour."""

    code: str = "user_error"


class HandleChangeTooSoonError(UserError):
    """Raised when the user tries to change their handle inside the 30-day window.

    Carries the number of days that still need to elapse so the route
    layer can surface ``retry_after_days`` in the response body.
    """

    code = "handle_change_too_soon"

    def __init__(self, retry_after_days: int) -> None:
        super().__init__(f"handle change available again in {retry_after_days} days")
        self.retry_after_days = retry_after_days


@dataclass(frozen=True, slots=True)
class HandleChangeResult:
    """Successful-handle-change payload."""

    user: User
    redirect: HandleRedirect


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    """Re-attach UTC if BSON stripped tzinfo on a read.

    Beanie/Motor + mongomock both deserialise BSON datetimes as naive
    objects in this codebase (production Atlas behaves the same way).
    Wrapping every read with this helper keeps service-layer
    comparisons tzinfo-clean.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _days_remaining(reference: datetime, now: datetime) -> int:
    """Round up to whole days so a "29 days, 12 hours" response says 30."""
    elapsed = now - reference
    remaining = HANDLE_CHANGE_COOLDOWN - elapsed
    if remaining <= timedelta(0):
        return 0
    # Ceil division by one day. ``total_seconds()`` keeps the precision
    # of sub-day intervals so we don't undercount when a user retries
    # right after the cooldown ticked over.
    return max(1, int((remaining.total_seconds() + 86399) // 86400))


# ---------------------------------------------------------------------------
# Handle change (T057)
# ---------------------------------------------------------------------------


async def change_handle(*, user: User, new_handle: str) -> HandleChangeResult:
    """Apply the FR-029 handle-change policy and persist the rename.

    Order of checks (each raises a specific :class:`UserError` so the
    route layer can map to a precise HTTP code):

    1. New handle satisfies the format rules
       (:func:`auxd_api.modules.auth.service.validate_handle_format`).
    2. New handle is not on the reserved-squat list.
    3. 30 days have elapsed since the most recent of
       ``handle_changed_at`` or ``handle_created_at``.
    4. The new handle is not already taken by another user.

    On success, this function writes a :class:`HandleRedirect` row for
    the old handle, mutates ``user.handle`` + ``user.handle_changed_at``,
    persists the User, and returns the redirect alongside the updated
    User.
    """
    # Handle changes use the same validation discipline as signup —
    # uppercase input is rejected, not silently downcased (FR-029).
    normalised = new_handle.strip()
    validate_handle_format(normalised)
    if is_reserved_handle(normalised):
        raise ReservedHandleError("handle is reserved")
    if normalised == user.handle:
        # No-op; treat as already-taken so the caller surfaces a
        # consistent conflict response instead of silently succeeding.
        raise DuplicateHandleError("handle is already in use")

    now = _utcnow()
    # The cooldown anchor is the most recent of "last change" or "creation".
    last_change: datetime | None = user.handle_changed_at
    anchor_raw = last_change if last_change is not None else user.handle_created_at
    anchor = _ensure_utc(anchor_raw)
    if now - anchor < HANDLE_CHANGE_COOLDOWN:
        raise HandleChangeTooSoonError(retry_after_days=_days_remaining(anchor, now))

    # Uniqueness — last so we don't burn a DB round-trip on requests
    # that fail the cheaper checks above.
    if await User.find_one(User.handle == normalised) is not None:
        raise DuplicateHandleError("handle is already taken")

    old_handle = user.handle
    redirect = HandleRedirect(
        old_handle=old_handle,
        new_handle=normalised,
        user_id=user.id,
    )
    await redirect.insert()
    user.handle = normalised
    user.handle_changed_at = now
    user.updated_at = now
    await user.save()
    return HandleChangeResult(user=user, redirect=redirect)


# ---------------------------------------------------------------------------
# Account deletion (T058)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AccountDeletionState:
    """Returned by the schedule/cancel helpers; mirrors the response body."""

    status: UserStatus
    scheduled_for: datetime | None


async def schedule_account_deletion(user: User) -> AccountDeletionState:
    """Mark ``user`` for deletion 30 days from now (idempotent).

    Idempotent: a second call returns the existing schedule without
    extending the window. Bumps ``session_version`` on the first call so
    any other open sessions are invalidated next refresh — the user
    initiating deletion presumably wants their other devices logged out.
    """
    if user.status is UserStatus.DELETION_PENDING and user.deletion_scheduled_for is not None:
        return AccountDeletionState(
            status=user.status,
            scheduled_for=_ensure_utc(user.deletion_scheduled_for),
        )

    now = _utcnow()
    scheduled_for = now + ACCOUNT_DELETION_GRACE
    user.status = UserStatus.DELETION_PENDING
    user.deletion_scheduled_for = scheduled_for
    user.session_version += 1
    user.updated_at = now
    await user.save()
    # Beanie/Motor + BSON can strip the tzinfo on a write-then-read cycle.
    # Return the original tz-aware ``scheduled_for`` so the API surface is
    # always normalised regardless of the persistence layer's quirks.
    return AccountDeletionState(status=user.status, scheduled_for=scheduled_for)


async def cancel_account_deletion(user: User) -> AccountDeletionState:
    """Cancel a pending deletion and return the user to ``ACTIVE`` state.

    Idempotent for already-active users — returns the current state
    without writing.
    """
    if user.status is UserStatus.ACTIVE and user.deletion_scheduled_for is None:
        return AccountDeletionState(status=user.status, scheduled_for=None)
    user.status = UserStatus.ACTIVE
    user.deletion_scheduled_for = None
    user.updated_at = _utcnow()
    await user.save()
    return AccountDeletionState(status=user.status, scheduled_for=None)
