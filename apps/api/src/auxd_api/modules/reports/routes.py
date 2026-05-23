"""Reports HTTP routes (T053a).

Single endpoint at MVP:

* ``POST /api/v1/reports/missing-album`` — anonymous or authenticated
  users can submit a structured "report missing album" entry from the
  manual-search empty state. Writes a :class:`Report` row with
  ``target_type=missing_album`` so the moderation queue can process
  catalog gaps in the same review pipeline as content/abuse reports
  (sync-fix L3-006).

The endpoint is anonymous-friendly because the search empty-state can
be hit pre-signup (Letterboxd-style critic-seed feed). When a session
is present, the reporter id is captured for trust-graph weighting and
to allow the user to see their own reports in a future personal-history
surface. The optional MBID / Discogs URL hints feed the T065 MBID-
reconciliation worker so user-submitted reports can short-circuit the
upstream-search step.

Rate limit: per-IP 3/min — small enough to deter spam-flooding the
moderation queue, large enough that a power user reporting a handful of
gaps in a session doesn't get blocked.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from auxd_api.lib.observability import emit_event, log_call
from auxd_api.lib.rate_limit import RateLimit, rate_limit
from auxd_api.lib.sessions import Session
from auxd_api.modules.moderation.models import (
    Report,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)

_LOGGER = logging.getLogger("auxd.reports.routes")

router = APIRouter(prefix="/reports", tags=["reports"])


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


_REPORT_RATE_LIMIT = rate_limit(
    endpoint="reports.missing_album",
    per_ip=RateLimit(limit=3, window_seconds=60),
)

# Friendly canned message returned with every successful submission —
# kept centralised so copy edits don't drift between code and tests.
_THANK_YOU_MESSAGE = "Thanks — we'll add it to the catalog."


@router.post(
    "/missing-album",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_REPORT_RATE_LIMIT)],
)
async def report_missing_album(
    payload: _MissingAlbumRequest,
    request: Request,
) -> dict[str, Any]:
    """Persist a missing-album report and return a friendly confirmation.

    The endpoint accepts anonymous calls; ``reporter_id`` is set to the
    session user id when an authenticated session is present, otherwise
    ``None``. Returns ``201`` with the new ``report_id`` and a copy-
    deck-controlled thank-you string.
    """
    session: Session | None = getattr(request.state, "session", None)
    reporter_id: str | None = session.user_id if isinstance(session, Session) else None

    artist = payload.artist.strip()
    album = payload.album.strip()
    target_id = payload.query.strip() if payload.query else f"{artist} - {album}"

    # The Report.detail field is a short structured note — embed the
    # hints there so the moderation queue can see them without joining
    # to a second collection.
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


__all__ = ["router"]
