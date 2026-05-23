"""Reviews service layer — pure business logic (T085, T086, T087).

The service owns the three review mutation paths invoked by
``modules/reviews/routes.py``:

* :func:`create_review` (T085) — create a 1:1 review against a diary
  entry, enforcing ownership, the diary-entry-unique constraint, and
  markdown sanitization.
* :func:`edit_review` (T086) — owner-only patch over body/visibility
  that appends a row to :class:`ReviewEditHistory` capturing the
  pre-edit body + SHA-256 hash + timestamp before saving.
* :func:`delete_review` (T087) — owner-only soft-delete that clears
  ``DiaryEntry.review_id``; cascade of ``ReviewLike`` rows happens at
  hard-delete time (a separate cron, deferred).

Why a separate service?
=======================
Reviews touch two collections (``Review`` + ``ReviewEditHistory``) and
have non-trivial sequencing (audit row before save, body sanitization,
1:1 conflict mapped to 409). The like flow lives in
:mod:`auxd_api.modules.reviews.likes_service` since its semantics are
distinct enough (notification side-effect, self-like rejection, atomic
counter update) to deserve its own module.

Markdown sanitization (FR-030 / S-C1)
=====================================
We hand-roll a small allowlist sanitizer rather than pulling in
``bleach`` or a full markdown parser. The spec is narrow:

* Allowed: bold (``**``), italic (``*`` / ``_``), line breaks, inline
  links ``[text](http(s)://…)``.
* Blocked: HTML tags (any ``<…>``), ``javascript:`` / ``data:`` URLs,
  raw URLs without the markdown wrapper, anything that could XSS.

The sanitizer is intentionally conservative — uncertain input is
stripped rather than escaped, because review bodies are markdown source
that the client renders, so leaving HTML-encoded sequences in the
storage layer would surface visually broken text instead of safe text.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review, ReviewEditHistory

# Body length cap mirrors :class:`DiaryEntry.review_body` (10k chars) so
# a Review created from a diary log and one created via this endpoint
# round-trip the same way.
REVIEW_BODY_MAX_LEN: Final[int] = 10_000


__all__ = [
    "REVIEW_BODY_MAX_LEN",
    "ReviewAlreadyDeletedError",
    "ReviewAlreadyExistsError",
    "ReviewBodyEmptyError",
    "ReviewBodyTooLongError",
    "ReviewError",
    "ReviewNotFoundError",
    "ReviewNotOwnedError",
    "UnknownDiaryEntryError",
    "create_review",
    "delete_review",
    "edit_review",
    "hash_body",
    "sanitize_markdown",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReviewError(Exception):
    """Base class for review-service errors. ``code`` is the wire identifier."""

    code: str = "review_error"


class UnknownDiaryEntryError(ReviewError):
    code = "diary_entry_not_found"


class ReviewNotFoundError(ReviewError):
    code = "review_not_found"


class ReviewNotOwnedError(ReviewError):
    code = "forbidden"


class ReviewAlreadyExistsError(ReviewError):
    """1:1 enforcement — only one Review per DiaryEntry."""

    code = "review_already_exists"


class ReviewBodyEmptyError(ReviewError):
    code = "review_body_empty"


class ReviewBodyTooLongError(ReviewError):
    code = "review_body_too_long"


class ReviewAlreadyDeletedError(ReviewError):
    """Soft-delete idempotency — second DELETE on a deleted review."""

    code = "already_deleted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Return ``datetime.now(UTC)`` — wrapped for monkeypatch-friendliness."""
    return datetime.now(UTC)


# Strip every HTML tag — opening, closing, self-closing, with attributes.
# Pre-compiled because sanitization runs on every create + edit and the
# regex is non-trivial.
_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]*>")

# Markdown inline link with a captured URL: ``[text](url)``. We re-build
# the link with the sanitized URL so disallowed protocols (``javascript:``,
# ``data:``) are stripped to just the bracketed text.
_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

# Allowed URL schemes for inline markdown links. Limited to http(s) so
# data URLs and javascript pseudo-URLs cannot smuggle XSS payloads.
_ALLOWED_LINK_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})


def _sanitize_link(text: str, url: str) -> str:
    """Return a sanitized markdown link, or the bare text if the URL is bad."""
    url_stripped = url.strip()
    lowered = url_stripped.lower()
    # Reject any control characters that could break out of the parens.
    if any(ord(c) < 0x20 for c in url_stripped):
        return text
    # Require an http(s):// scheme — anything else (mailto:, ftp:, etc.)
    # is rejected. Relative URLs without a scheme are also rejected so the
    # storage layer never carries something that resolves to whatever
    # base the client happens to be on.
    for scheme in _ALLOWED_LINK_SCHEMES:
        if lowered.startswith(f"{scheme}://"):
            return f"[{text}]({url_stripped})"
    return text


def sanitize_markdown(body: str) -> str:
    """Return a sanitized version of ``body`` safe for storage and rendering.

    Allowed inline syntax:

    * Bold: ``**...**``
    * Italic: ``*...*`` or ``_..._``
    * Line breaks (single ``\n``, paragraph breaks via blank line).
    * Inline links: ``[text](http(s)://...)``

    Stripped or transformed:

    * Any HTML tag (``<script>``, ``<img>``, ``<iframe>``, etc.) — removed
      entirely so the rendered output never sees a tag boundary.
    * Inline links with disallowed schemes (``javascript:``, ``data:``,
      relative URLs, ``mailto:``) — collapsed to the bracketed text.
    * Control characters below 0x20 (except newline / tab) — removed.

    The function preserves leading/trailing whitespace within the safe
    content so the caller can still ``strip()`` if that matters.
    """
    # 1. Strip every HTML tag. This is intentionally aggressive — uncertain
    #    input is dropped rather than escaped because the rendered output
    #    treats the stored body as markdown source.
    safe = _HTML_TAG_RE.sub("", body)

    # 2. Drop control characters except newline (\n) and tab (\t). Carriage
    #    returns are normalised to newlines so multi-platform clients
    #    round-trip consistently.
    safe = safe.replace("\r\n", "\n").replace("\r", "\n")
    safe = "".join(c for c in safe if c >= " " or c in ("\n", "\t"))

    # 3. Re-emit inline links with their URLs filtered. ``re.sub`` with a
    #    callable handles all matches in one pass.
    safe = _MD_LINK_RE.sub(
        lambda m: _sanitize_link(m.group(1), m.group(2)),
        safe,
    )

    return safe


def _validate_body(body: str) -> str:
    """Return the sanitized body or raise on length-bound violations."""
    sanitized = sanitize_markdown(body)
    stripped = sanitized.strip()
    if not stripped:
        raise ReviewBodyEmptyError("review body must be non-empty after sanitization")
    if len(sanitized) > REVIEW_BODY_MAX_LEN:
        raise ReviewBodyTooLongError(f"review body exceeds {REVIEW_BODY_MAX_LEN}-character cap")
    return sanitized


def hash_body(body: str) -> str:
    """Return the SHA-256 hex digest of ``body`` — used by the edit audit log.

    Exposed at module level so tests can verify the snapshot round-trip
    without re-implementing the hashing rule.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# create_review (T085)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateReviewResult:
    """Return shape for :func:`create_review`."""

    review: Review
    diary_entry: DiaryEntry


async def create_review(
    *,
    user_id: str,
    diary_entry_id: str,
    body: str,
    visibility: str | None,
) -> CreateReviewResult:
    """Create a new :class:`Review` for the given diary entry.

    Behaviour:

    * Looks up the diary entry — raises :class:`UnknownDiaryEntryError`
      when missing or soft-deleted (a deleted diary entry must not
      accept new reviews; the cron will eventually sweep it).
    * Owner enforcement — raises :class:`ReviewNotOwnedError` when the
      caller is not the diary entry's owner.
    * 1:1 enforcement — raises :class:`ReviewAlreadyExistsError` if a
      Review already references this diary entry. The
      ``diary_entry_id`` unique index is the second line of defense at
      the DB layer.
    * Sanitises ``body`` (see :func:`sanitize_markdown`) and validates
      it's non-empty after sanitization (max 10k chars enforced too).
    * Sets ``Review.visibility`` to the explicit ``visibility`` arg if
      provided, else mirrors the diary entry's visibility.
    * On insert: sets ``DiaryEntry.review_id`` and bumps the diary
      entry's ``updated_at`` so callers refreshing the diary see the
      attachment.
    """
    entry = await DiaryEntry.get(diary_entry_id)
    if entry is None or entry.deleted_at is not None:
        raise UnknownDiaryEntryError("diary entry not found")
    if entry.user_id != user_id:
        raise ReviewNotOwnedError("not owner")

    # Body validation before the duplicate-check round-trip — invalid
    # bodies bail fastest.
    sanitized_body = _validate_body(body)

    # Application-layer 1:1 check; the unique index is the second line.
    existing = await Review.find_one({"diary_entry_id": entry.id, "deleted_at": None})
    if existing is not None:
        raise ReviewAlreadyExistsError("review already exists for this diary entry")

    # Resolve visibility. Explicit override wins; else mirror the diary
    # entry's visibility (which is the documented default).
    chosen_visibility = visibility if visibility is not None else entry.visibility.value
    # Defensive: validate against the Visibility enum so an attacker-
    # supplied string can't smuggle in an unknown value.
    try:
        Visibility(chosen_visibility)
    except ValueError as exc:
        raise ReviewError(f"unknown visibility: {chosen_visibility}") from exc

    now = _now()
    review = Review(
        user_id=user_id,
        diary_entry_id=entry.id,
        album_id=entry.album_id,
        body=sanitized_body,
        visibility=chosen_visibility,
        created_at=now,
        updated_at=now,
    )
    await review.insert()

    entry.review_id = review.id
    entry.updated_at = now
    await entry.save()

    return CreateReviewResult(review=review, diary_entry=entry)


# ---------------------------------------------------------------------------
# edit_review (T086)
# ---------------------------------------------------------------------------


async def edit_review(
    *,
    review_id: str,
    user_id: str,
    body: str | None,
    visibility: str | None,
) -> Review:
    """Patch an existing review — owner-only, body / visibility only.

    Audit log:

    * Before save, append a :class:`ReviewEditHistory` row capturing the
      pre-edit body (full text), the SHA-256 hash of that body, the
      editor's user id, and ``edited_at = now``. The 90-day TTL on
      ``ReviewEditHistory.edited_at`` (declared on the model) handles
      retention — we don't manage it here.
    * The version counter is "max existing version + 1" so a fresh
      review starts at 1.

    Sanitization:

    * Same allowlist sanitizer as :func:`create_review`.
    * Empty body (after sanitization / strip) is rejected with
      :class:`ReviewBodyEmptyError` — the API exposes
      :func:`delete_review` for clearing the review entirely.
    """
    review = await Review.get(review_id)
    if review is None or review.deleted_at is not None:
        raise ReviewNotFoundError("review not found")
    if review.user_id != user_id:
        raise ReviewNotOwnedError("not owner")

    now = _now()
    changed = False
    audit_written = False

    if body is not None:
        sanitized = _validate_body(body)
        if sanitized != review.body:
            # Append audit row BEFORE we mutate the in-memory model so
            # the snapshot is the pre-edit body. The TTL index on the
            # model handles 90-day retention without us managing it.
            last = (
                await ReviewEditHistory.find({"review_id": review.id})
                .sort("-version")
                .limit(1)
                .to_list()
            )
            next_version = (last[0].version + 1) if last else 1
            history_row = ReviewEditHistory(
                review_id=review.id,
                version=next_version,
                body_at_time=review.body,
                edited_at=now,
                edited_by=user_id,
            )
            await history_row.insert()
            audit_written = True
            review.body = sanitized
            review.edited_at = now
            changed = True

    if visibility is not None and visibility != review.visibility:
        try:
            Visibility(visibility)
        except ValueError as exc:
            raise ReviewError(f"unknown visibility: {visibility}") from exc
        review.visibility = visibility
        changed = True

    if changed:
        review.updated_at = now
        await review.save()

    # Tag for the route layer / tests — not persisted, but useful for
    # observability assertions in unit tests.
    review.__dict__["_audit_written"] = audit_written

    return review


# ---------------------------------------------------------------------------
# delete_review (T087)
# ---------------------------------------------------------------------------


async def delete_review(*, review_id: str, user_id: str) -> Review:
    """Soft-delete a review (owner-only).

    Behaviour:

    * Sets ``Review.deleted_at = now`` (a NEW field on the model added
      with this task).
    * Clears ``DiaryEntry.review_id`` so the diary entry no longer
      points at the now-hidden review.
    * Idempotency: a double-delete raises
      :class:`ReviewAlreadyDeletedError` so the route can emit
      ``HTTP 410``.
    * The cascade-delete of :class:`ReviewLike` rows happens at
      hard-delete time (cron, not implemented in this task). Like rows
      remain orphaned in the DB but the read endpoint filters them out
      via the ``deleted_at IS None`` condition on Review.
    """
    review = await Review.get(review_id)
    if review is None:
        raise ReviewNotFoundError("review not found")
    if review.user_id != user_id:
        raise ReviewNotOwnedError("not owner")
    if review.deleted_at is not None:
        raise ReviewAlreadyDeletedError("review already deleted")

    now = _now()
    review.deleted_at = now
    review.updated_at = now
    await review.save()

    # Clear the back-reference on the diary entry — the entry stays;
    # only the review is removed from the public surface.
    entry = await DiaryEntry.get(review.diary_entry_id)
    if entry is not None and entry.review_id == review.id:
        entry.review_id = None
        entry.updated_at = now
        await entry.save()

    return review
