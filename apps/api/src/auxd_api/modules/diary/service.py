"""Diary service layer — pure business logic for the wedge interaction (T073-T075).

The service owns the four mutation paths invoked by ``modules/diary/routes.py``:

* :func:`log_entry` — create a new diary entry (with optional review),
  enforcing the 60-second idempotency window and the relisten flag.
* :func:`edit_entry` — owner-only patch over an active entry (with
  optional review create/update/delete).
* :func:`delete_entry` — owner-only soft-delete with cascade to any
  attached review.
* :func:`restore_entry` — owner-only un-delete inside the 30-day grace
  window (per data-model.md DM-5 and plan §3.1).

Why a separate service?
=======================
Diary touches three collections (DiaryEntry, Review, optionally
Backlog-via-relisten signal in a future ticket) and has non-trivial
sequencing (idempotency window, relisten lookup, cascading review
writes). Keeping that logic in pure ``async def`` functions makes it
testable in isolation and lets the route layer focus on HTTP shape +
auth + rate-limit concerns.

The service raises a small set of dedicated exceptions
(:class:`DiaryError` subclasses). The route layer translates each to the
appropriate HTTPException — see ``routes.py``'s ``_DIARY_ERROR_STATUS_MAP``.

Idempotency model (T073)
========================
Within a 60-second window, a duplicate ``log_entry`` call with the same
``(user_id, album_id)`` returns the **existing** entry instead of
creating a new row. This is double-tap protection — the wedge UX has a
single round button and the worst failure mode is two rows per actual
listen. The 60-second window is wider than any plausible user-induced
double-tap but narrower than the 8-second "log a listen" budget.

Relisten flag (T076 — covered here)
===================================
``relisten=True`` when the user has any prior, non-deleted DiaryEntry
for the same album. The lookup uses the existing
``(user_id, album_id, logged_at)`` index and excludes the new entry
itself by checking before insert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from auxd_api.modules.albums.models import Album
from auxd_api.modules.backlog.service import auto_remove_on_log
from auxd_api.modules.diary.models import DiaryEntry, DiaryEntrySource, Visibility
from auxd_api.modules.reviews.models import Review

# Idempotency window: a second log_entry within this many seconds returns
# the existing entry instead of creating a new one. Chosen wide enough
# to soak up double-tap UX without swallowing two genuine listens.
IDEMPOTENCY_WINDOW_SECONDS: Final[int] = 60

# Soft-delete grace window — entries can be restored within this window
# after deletion (DM-5). Beyond this the cleanup cron hard-deletes; the
# restore endpoint returns 410 gone.
RESTORE_GRACE_DAYS: Final[int] = 30


__all__ = [
    "DiaryError",
    "DiaryEntryAlreadyDeletedError",
    "DiaryEntryDeletedError",
    "DiaryEntryNotFoundError",
    "DiaryEntryNotOwnedError",
    "DiaryRestoreExpiredError",
    "IDEMPOTENCY_WINDOW_SECONDS",
    "LogEntryResult",
    "RESTORE_GRACE_DAYS",
    "RatingNotInHalvesError",
    "UnknownAlbumError",
    "delete_entry",
    "edit_entry",
    "log_entry",
    "restore_entry",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiaryError(Exception):
    """Base class for diary-service errors. ``code`` is the wire identifier."""

    code: str = "diary_error"


class UnknownAlbumError(DiaryError):
    code = "album_not_found"


class RatingNotInHalvesError(DiaryError):
    code = "rating_not_in_halves"


class DiaryEntryNotFoundError(DiaryError):
    code = "entry_not_found"


class DiaryEntryNotOwnedError(DiaryError):
    code = "forbidden"


class DiaryEntryDeletedError(DiaryError):
    """Raised when an edit is attempted against a soft-deleted entry."""

    code = "entry_deleted"


class DiaryEntryAlreadyDeletedError(DiaryError):
    """Raised when delete is called against an entry that is already deleted."""

    code = "already_deleted"


class DiaryRestoreExpiredError(DiaryError):
    """Raised when restore is called outside the 30-day grace window."""

    code = "restore_expired"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Return ``datetime.now(UTC)`` — wrapped for monkeypatch-friendliness."""
    return datetime.now(UTC)


def _validate_rating_halves(rating: float | None) -> None:
    """Raise :class:`RatingNotInHalvesError` if ``rating`` is not a 0.5 step.

    The wire bound (0.5..5.0) is already enforced by the Pydantic field
    constraints; this layer adds the halves-only check (``2.0`` and ``2.5``
    are valid; ``2.7`` is not).
    """
    if rating is None:
        return
    # Multiply by 2 and check integer — avoids float modulo precision noise.
    doubled = rating * 2
    if doubled != int(doubled):
        raise RatingNotInHalvesError("rating must be in 0.5 increments")


async def _has_prior_entry(user_id: str, album_id: str) -> bool:
    """Return True when a non-deleted entry exists for ``(user_id, album_id)``."""
    existing = await DiaryEntry.find_one(
        {
            "user_id": user_id,
            "album_id": album_id,
            "deleted_at": None,
        }
    )
    return existing is not None


async def _find_idempotent_match(
    user_id: str,
    album_id: str,
    window_seconds: int = IDEMPOTENCY_WINDOW_SECONDS,
) -> DiaryEntry | None:
    """Return the most recent active entry within the idempotency window.

    The query uses the ``(user_id, album_id, logged_at)`` compound index;
    the ``created_at`` filter is the actual idempotency boundary (we care
    about wall-clock recency, not the user's chosen ``logged_at``).
    """
    cutoff = _now() - timedelta(seconds=window_seconds)
    rows = (
        await DiaryEntry.find(
            {
                "user_id": user_id,
                "album_id": album_id,
                "deleted_at": None,
                "created_at": {"$gte": cutoff},
            }
        )
        .sort("-created_at")
        .limit(1)
        .to_list()
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# log_entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LogEntryResult:
    """Return shape for :func:`log_entry`.

    ``created`` is False when the idempotency window returned an existing
    entry — the route layer maps this to ``HTTP 200`` instead of ``201``.
    ``backlog_item_removed`` is True only when the diary insert was fresh
    AND the matching backlog item was auto-removed under S-D3 (see T096).
    Idempotent hits never re-remove a backlog item so the route layer
    can emit the T100 conversion event exactly once per real log.
    """

    entry: DiaryEntry
    review: Review | None
    created: bool
    backlog_item_removed: bool = False


async def log_entry(
    *,
    user_id: str,
    album_id: str,
    rating: float | None,
    auxed: bool,
    review_body: str | None,
    visibility: Visibility,
    device: str | None = None,
) -> LogEntryResult:
    """Create a diary entry (with optional review) for ``user_id`` on ``album_id``.

    Behaviour:

    * Validates the album exists (otherwise :class:`UnknownAlbumError`).
    * Validates rating is a 0.5 step (otherwise :class:`RatingNotInHalvesError`).
    * Within the 60-second idempotency window, returns an existing entry
      for the same ``(user_id, album_id)`` pair with ``created=False`` —
      so the route layer can respond with ``200`` instead of ``201``.
      Importantly, the idempotency path does NOT mutate the existing
      entry; the client is expected to follow up with PATCH if their
      intent was an edit.
    * Sets ``relisten=True`` when the user has any prior non-deleted
      entry for the same album (T076).
    * When ``review_body`` is provided, also creates a :class:`Review`
      mirroring the entry's visibility and links it via
      ``DiaryEntry.review_id`` + ``Review.diary_entry_id``.
    """
    _validate_rating_halves(rating)

    album = await Album.get(album_id)
    if album is None:
        raise UnknownAlbumError("album not found")

    # Idempotency check — early return without mutation. Per T096, the
    # idempotent path NEVER re-removes a backlog item: a double-tap log
    # within 60s of the first one should not emit a second
    # backlog.converted_to_log event.
    duplicate = await _find_idempotent_match(user_id, album_id)
    if duplicate is not None:
        attached_review: Review | None = None
        if duplicate.review_id is not None:
            attached_review = await Review.get(duplicate.review_id)
        return LogEntryResult(
            entry=duplicate,
            review=attached_review,
            created=False,
            backlog_item_removed=False,
        )

    relisten = await _has_prior_entry(user_id, album_id)
    now = _now()

    entry = DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=now,
        rating=rating,
        auxed=auxed,
        visibility=visibility,
        source=DiaryEntrySource.MANUAL,
        relisten=relisten,
        device=device,
        created_at=now,
        updated_at=now,
    )
    await entry.insert()

    review: Review | None = None
    if review_body is not None and review_body.strip():
        review = Review(
            user_id=user_id,
            diary_entry_id=entry.id,
            album_id=album_id,
            body=review_body,
            visibility=visibility.value,
        )
        await review.insert()
        entry.review_id = review.id
        entry.updated_at = _now()
        await entry.save()

    # T096 — auto-remove the album from the user's backlog after a
    # successful, fresh log. The helper is tolerant of "no backlog"
    # and "album not queued" so the common case (user logs an album
    # they never queued) is a clean no-op. Honors
    # ``User.keep_backlog_after_log`` (S-D3 alt-path).
    backlog_item_removed = await auto_remove_on_log(user_id=user_id, album_id=album_id)

    return LogEntryResult(
        entry=entry,
        review=review,
        created=True,
        backlog_item_removed=backlog_item_removed,
    )


# ---------------------------------------------------------------------------
# edit_entry
# ---------------------------------------------------------------------------


async def edit_entry(
    *,
    entry_id: str,
    user_id: str,
    rating: float | None,
    auxed: bool | None,
    review_body: str | None,
    visibility: Visibility | None,
    rating_provided: bool,
    review_body_provided: bool,
) -> tuple[DiaryEntry, Review | None]:
    """Patch an existing entry — owner-only, active-only.

    The ``*_provided`` boolean flags disambiguate "omit this field"
    (don't touch it) from "set this field to None / empty string". The
    route layer derives them from Pydantic's ``model_fields_set`` so a
    caller can clear ``rating`` by sending ``"rating": null`` while
    still being able to omit it entirely.

    Review semantics:

    * ``review_body`` not provided → leave any existing review untouched.
    * ``review_body == ""`` (provided, empty) → soft-delete the review.
    * ``review_body == "non-empty"`` AND no existing review → create one.
    * ``review_body == "non-empty"`` AND existing review → update body.
    """
    entry = await DiaryEntry.get(entry_id)
    if entry is None:
        raise DiaryEntryNotFoundError("entry not found")
    if entry.deleted_at is not None:
        # Deleted entries are not editable — route 404 (the entry is
        # effectively gone for non-owner viewers; for the owner, edit
        # is gated on active state because restore is the right path).
        raise DiaryEntryNotFoundError("entry not found")
    if entry.user_id != user_id:
        raise DiaryEntryNotOwnedError("not owner")

    _validate_rating_halves(rating)

    now = _now()
    changed = False
    if rating_provided:
        entry.rating = rating
        changed = True
    if auxed is not None:
        entry.auxed = auxed
        changed = True
    if visibility is not None:
        entry.visibility = visibility
        changed = True

    review: Review | None = (
        await Review.get(entry.review_id) if entry.review_id is not None else None
    )

    if review_body_provided:
        if review_body is None or review_body == "":
            # Clear the review.
            if review is not None:
                review.updated_at = now
                await review.delete()
                review = None
            entry.review_id = None
            changed = True
        else:
            if review is None:
                # Create a fresh review mirroring the entry's visibility.
                review = Review(
                    user_id=user_id,
                    diary_entry_id=entry.id,
                    album_id=entry.album_id,
                    body=review_body,
                    visibility=entry.visibility.value,
                )
                await review.insert()
                entry.review_id = review.id
                changed = True
            else:
                review.body = review_body
                review.edited_at = now
                # Keep review visibility synced with entry visibility
                # since the diary entry is the source of truth.
                review.visibility = entry.visibility.value
                review.updated_at = now
                await review.save()
                changed = True

    if changed:
        entry.edited_at = now
        entry.updated_at = now
        await entry.save()

    return entry, review


# ---------------------------------------------------------------------------
# delete_entry / restore_entry
# ---------------------------------------------------------------------------


async def delete_entry(*, entry_id: str, user_id: str) -> DiaryEntry:
    """Soft-delete an entry (owner-only); cascade to attached review.

    Idempotency: a double-delete raises :class:`DiaryEntryAlreadyDeletedError`
    so the route can emit HTTP 410. The hard-delete sweeper runs out of
    band (cron, not implemented here).
    """
    entry = await DiaryEntry.get(entry_id)
    if entry is None:
        raise DiaryEntryNotFoundError("entry not found")
    if entry.user_id != user_id:
        raise DiaryEntryNotOwnedError("not owner")
    if entry.deleted_at is not None:
        raise DiaryEntryAlreadyDeletedError("entry already deleted")

    now = _now()
    entry.deleted_at = now
    entry.updated_at = now
    await entry.save()

    if entry.review_id is not None:
        review = await Review.get(entry.review_id)
        if review is not None:
            # Reviews don't have a deleted_at column today; the strongest
            # cascade we can express without a schema change is to drop
            # the row entirely. Album-detail / profile queries already
            # filter via ``diary_entry.deleted_at IS None``, so the
            # observable behaviour is the same as a soft-delete.
            await review.delete()
    return entry


async def restore_entry(*, entry_id: str, user_id: str) -> DiaryEntry:
    """Un-delete an entry within the 30-day grace window."""
    entry = await DiaryEntry.get(entry_id)
    if entry is None:
        raise DiaryEntryNotFoundError("entry not found")
    if entry.user_id != user_id:
        raise DiaryEntryNotOwnedError("not owner")
    if entry.deleted_at is None:
        # Nothing to restore — treat as not-found from the caller's POV
        # because a healthy active entry is never the target of restore.
        raise DiaryEntryNotFoundError("entry not deleted")

    # MongoDB strips tzinfo on retrieval — coerce to UTC before comparison
    # so the cutoff math works regardless of how Beanie deserialises the
    # stored value.
    deleted_at = entry.deleted_at
    if deleted_at.tzinfo is None:
        deleted_at = deleted_at.replace(tzinfo=UTC)
    cutoff = _now() - timedelta(days=RESTORE_GRACE_DAYS)
    if deleted_at < cutoff:
        raise DiaryRestoreExpiredError("restore window expired")

    now = _now()
    entry.deleted_at = None
    entry.updated_at = now
    await entry.save()
    return entry
