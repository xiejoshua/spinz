"""Reports HTTP routes (T053a + T155 + T163a + T167).

Endpoints under ``/api/v1/reports``:

* ``POST /reports/missing-album`` (T053a) — anonymous or authenticated
  users submit a structured "report missing album" entry from the
  manual-search empty state. Writes a :class:`Report` row with
  ``target_type=missing_album`` so the moderation queue can process
  catalog gaps in the same review pipeline as content/abuse reports
  (sync-fix L3-006).

* ``POST /reports/user`` (T155) — authenticated user reports another
  user account. Closes the T111 BlockReportMenu's graceful-404
  fallback — the frontend POST now returns 201 with the report id
  instead of failing through to "deferred-success" toast.

* ``POST /reports/review`` (T155) — authenticated user reports a
  review. Validates the review exists (FK).

* ``POST /reports/diary-entry`` (T163a) — authenticated user reports
  a diary entry. Validates the entry exists (FK).

* ``POST /reports/album`` (T167) — authenticated user reports an
  album entry as having wrong metadata or being a duplicate. Feeds the
  founder-run merge CLI at ``apps/api/scripts/merge_albums.py``.

Rate limits:

* Missing-album: per-IP 3/min (existing, anonymous-friendly).
* Content reports: per-reporter 10/day — small enough to deter
  spam-flooding the moderation queue, large enough that a power user
  legitimately calling out a few bad actors in a session is allowed.

Idempotency: same (reporter_id, target_type, target_id) triple within
24h returns the existing row with 200 (not 201 + duplicate).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.moderation.models import (
    REPORT_DETAIL_MAX_LEN,
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from auxd_api.modules.reports.service import (
    SelfReportError,
    TargetNotFoundError,
    submit_report,
)

_LOGGER = logging.getLogger("auxd.reports.routes")

router = APIRouter(prefix="/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _require_session(request: Request) -> Session:
    """Pull a :class:`Session` from ``request.state`` or raise 401."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, Session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "session required"},
        )
    return session


# Content-report reasons — the catalog_gap reason is reserved for the
# missing-album path so we expose a narrower enum to clients of the
# user/review/diary-entry endpoints.
_CONTENT_REPORT_REASONS: frozenset[ReportReason] = frozenset(
    {
        ReportReason.HARASSMENT,
        ReportReason.SPAM,
        ReportReason.IMPERSONATION,
        ReportReason.HATE_SPEECH,
        ReportReason.NSFW,
        ReportReason.OTHER,
    }
)


def _validate_content_reason(reason: ReportReason) -> ReportReason:
    """Defend against a client smuggling ``CATALOG_GAP`` onto a content report."""
    if reason not in _CONTENT_REPORT_REASONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_reason",
                "message": f"{reason.value!r} is not a valid content-report reason",
            },
        )
    return reason


# Per-reporter 10/day. The catalog-gap path keeps its own per-IP limit;
# the content-report budget is keyed on the authenticated user.
_CONTENT_REPORT_RATE_LIMIT = rate_limit(
    endpoint="reports.content_submit",
    per_user=RateLimit(limit=10, window_seconds=24 * 60 * 60),
)


# ---------------------------------------------------------------------------
# Missing-album report (T053a) — preserved verbatim.
# ---------------------------------------------------------------------------


class _MissingAlbumRequest(BaseModel):
    """Wire shape for ``POST /reports/missing-album``.

    ``artist`` + ``album`` are mandatory because they're the minimum the
    catalog team needs to triage. ``query`` mirrors the original search
    term verbatim so duplicate-detection in the moderation queue can
    group "users tried X and missed" reports together. ``mbid_hint`` and
    ``discogs_url_hint`` are user-supplied breadcrumbs the T065 worker
    consumes to short-circuit upstream search when the user already
    knows the canonical id.
    """

    artist: str = Field(min_length=1, max_length=200)
    album: str = Field(min_length=1, max_length=200)
    mbid_hint: str | None = Field(default=None, max_length=80)
    discogs_url_hint: str | None = Field(default=None, max_length=500)
    query: str | None = Field(default=None, max_length=500)


_MISSING_ALBUM_RATE_LIMIT = rate_limit(
    endpoint="reports.missing_album",
    per_ip=RateLimit(limit=3, window_seconds=60),
)

# Friendly canned message returned with every successful submission —
# kept centralised so copy edits don't drift between code and tests.
_THANK_YOU_MESSAGE = "Thanks — we'll add it to the catalog."


@router.post(
    "/missing-album",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_MISSING_ALBUM_RATE_LIMIT)],
)
async def report_missing_album(
    payload: _MissingAlbumRequest,
    request: Request,
) -> dict[str, Any]:
    """Persist a missing-album report and return a friendly confirmation."""
    session: Session | None = getattr(request.state, "session", None)
    reporter_id: str | None = session.user_id if isinstance(session, Session) else None

    artist = payload.artist.strip()
    album = payload.album.strip()
    target_id = payload.query.strip() if payload.query else f"{artist} - {album}"

    detail_parts: list[str] = [f"artist={artist}", f"album={album}"]
    if payload.mbid_hint:
        detail_parts.append(f"mbid_hint={payload.mbid_hint.strip()}")
    if payload.discogs_url_hint:
        detail_parts.append(f"discogs_url_hint={payload.discogs_url_hint.strip()}")
    detail = "; ".join(detail_parts)

    report = Report(
        reporter_id=reporter_id,
        target_type=ReportTargetType.MISSING_ALBUM,
        target_id=target_id,
        reason=ReportReason.CATALOG_GAP,
        detail=detail,
        status=ReportStatus.OPEN,
    )
    await report.insert()

    log_call(
        provider="auxd",
        endpoint="reports.missing_album",
        latency_ms=0.0,
        status="ok",
        extra={
            "report_id": report.id,
            "reporter_id": reporter_id,
            "anonymous": reporter_id is None,
        },
    )
    emit_event(
        user_id=reporter_id,
        event="report.missing_album_submitted",
        properties={
            "report_id": report.id,
            "artist": artist,
            "album": album,
            "has_mbid_hint": payload.mbid_hint is not None,
            "has_discogs_hint": payload.discogs_url_hint is not None,
        },
    )

    return {"report_id": report.id, "message": _THANK_YOU_MESSAGE}


# ---------------------------------------------------------------------------
# Content reports (T155 + T163a)
# ---------------------------------------------------------------------------


class _UserReportRequest(BaseModel):
    """Wire shape for ``POST /reports/user``."""

    user_id: str = Field(min_length=1, max_length=80)
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=REPORT_DETAIL_MAX_LEN)


class _ReviewReportRequest(BaseModel):
    """Wire shape for ``POST /reports/review``."""

    review_id: str = Field(min_length=1, max_length=80)
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=REPORT_DETAIL_MAX_LEN)


class _DiaryEntryReportRequest(BaseModel):
    """Wire shape for ``POST /reports/diary-entry``."""

    entry_id: str = Field(min_length=1, max_length=80)
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=REPORT_DETAIL_MAX_LEN)


class _AlbumReportRequest(BaseModel):
    """Wire shape for ``POST /reports/album`` (T167)."""

    album_id: str = Field(min_length=1, max_length=80)
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=REPORT_DETAIL_MAX_LEN)


# Album-report reasons — narrower than content reasons; only the album-
# specific values + ``OTHER`` are accepted.
_ALBUM_REPORT_REASONS: frozenset[ReportReason] = frozenset(
    {
        ReportReason.WRONG_METADATA,
        ReportReason.DUPLICATE,
        ReportReason.OTHER,
    }
)


def _validate_album_reason(reason: ReportReason) -> ReportReason:
    """Reject a content/catalog reason smuggled onto an album report."""
    if reason not in _ALBUM_REPORT_REASONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_reason",
                "message": f"{reason.value!r} is not a valid album-report reason",
            },
        )
    return reason


def _serialize_submit_response(report: Report, created: bool) -> dict[str, Any]:
    """Common response shape for all three content-report endpoints."""
    return {
        "report_id": report.id,
        "target_type": report.target_type.value,
        "target_id": report.target_id,
        "status": report.status.value,
        "created": created,
    }


async def _submit_content_report(
    *,
    reporter_id: str,
    target_type: ReportTargetType,
    target_id: str,
    reason: ReportReason,
    detail: str | None,
) -> tuple[dict[str, Any], int]:
    """Shared core: invoke the service, translate errors → HTTPException."""
    try:
        result = await submit_report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            detail=detail,
        )
    except SelfReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": exc.code, "message": str(exc)},
        ) from exc
    except TargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": exc.code, "message": str(exc)},
        ) from exc

    log_call(
        provider="auxd",
        endpoint=f"reports.{target_type.value}",
        latency_ms=0.0,
        status="ok",
        extra={
            "report_id": result.report.id,
            "reporter_id": reporter_id,
            "target_type": target_type.value,
            "target_id": target_id,
            "is_new_report": result.created,
        },
    )
    emit_event(
        user_id=reporter_id,
        event="report.content_submitted",
        properties={
            "report_id": result.report.id,
            "target_type": target_type.value,
            "reason": reason.value,
            "is_new_report": result.created,
        },
    )
    payload = _serialize_submit_response(result.report, created=result.created)
    status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return payload, status_code


@router.post(
    "/user",
    dependencies=[Depends(_CONTENT_REPORT_RATE_LIMIT)],
)
async def report_user(
    payload: _UserReportRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> Any:
    """Persist a report against another user account (T155)."""
    reason = _validate_content_reason(payload.reason)
    body, status_code = await _submit_content_report(
        reporter_id=session.user_id,
        target_type=ReportTargetType.USER,
        target_id=payload.user_id,
        reason=reason,
        detail=payload.detail,
    )
    # FastAPI's typing on a dynamic-status return is loose — wrap in a
    # JSONResponse only when we need a non-default code.
    from fastapi.responses import JSONResponse

    return JSONResponse(content=body, status_code=status_code)


@router.post(
    "/review",
    dependencies=[Depends(_CONTENT_REPORT_RATE_LIMIT)],
)
async def report_review(
    payload: _ReviewReportRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> Any:
    """Persist a report against a review (T155)."""
    reason = _validate_content_reason(payload.reason)
    body, status_code = await _submit_content_report(
        reporter_id=session.user_id,
        target_type=ReportTargetType.REVIEW,
        target_id=payload.review_id,
        reason=reason,
        detail=payload.detail,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(content=body, status_code=status_code)


@router.post(
    "/diary-entry",
    dependencies=[Depends(_CONTENT_REPORT_RATE_LIMIT)],
)
async def report_diary_entry(
    payload: _DiaryEntryReportRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> Any:
    """Persist a report against a diary entry (T163a)."""
    reason = _validate_content_reason(payload.reason)
    body, status_code = await _submit_content_report(
        reporter_id=session.user_id,
        target_type=ReportTargetType.DIARY_ENTRY,
        target_id=payload.entry_id,
        reason=reason,
        detail=payload.detail,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(content=body, status_code=status_code)


@router.post(
    "/album",
    dependencies=[Depends(_CONTENT_REPORT_RATE_LIMIT)],
)
async def report_album(
    payload: _AlbumReportRequest,
    session: Annotated[Session, Depends(_require_session)],
) -> Any:
    """Persist a report against an album (T167).

    Album reports feed the founder-run album-merge CLI at
    ``apps/api/scripts/merge_albums.py``. Reasons are narrowed to
    album-specific values; smuggling a content reason (e.g.
    ``harassment``) returns a 422.
    """
    reason = _validate_album_reason(payload.reason)
    body, status_code = await _submit_content_report(
        reporter_id=session.user_id,
        target_type=ReportTargetType.ALBUM,
        target_id=payload.album_id,
        reason=reason,
        detail=payload.detail,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(content=body, status_code=status_code)


__all__ = ["router"]
