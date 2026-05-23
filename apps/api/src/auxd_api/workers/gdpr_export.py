"""GDPR data-export worker (T153).

End-to-end pipeline for the "export my data" affordance: aggregates
every row owned by a user, builds a JSON + a ZIP (containing per-
collection CSVs), uploads both to R2 with 24-hour signed URLs, and
emails the user the download links via Resend.

The pipeline is invoked via :func:`auxd_api.redis_client.enqueue_job`
from the ``POST /api/v1/users/me/data-export`` endpoint — the endpoint
fires-and-returns 202 immediately so the user doesn't wait on the
build.

Sensitive fields stripped from the export:

* ``User.password_hash``
* ``User.admin_notes``
* ``User.session_version``

These are internal — including them in a self-service export would
leak information about how account state is enforced internally.

Output shape:

* ``exports/{user_id}/{job_id}/export.json`` — one JSON object with one
  key per collection; values are arrays of serialised rows.
* ``exports/{user_id}/{job_id}/export.zip`` — a ZIP archive with one
  CSV per collection that's row-shaped (anything with an ``id`` field).

URLs are 24-hour presigned R2 / S3 GET URLs. The bucket itself is
private; the signed URLs are the only path through which the user
accesses the archive.

Email template is one-off transactional text (NOT routed through the
notification dispatcher) because the export shape doesn't map cleanly
to a :class:`NotificationType` — it carries two URLs and size
metadata, none of which fit the existing email-template registry.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import boto3  # type: ignore[import-untyped]
import resend
from beanie import Document

from auxd_api.lib.audit import record_gdpr_event
from auxd_api.lib.observability import log_call
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.gdpr.models import GdprAuditAction
from auxd_api.modules.notifications.models import Notification
from auxd_api.modules.notifications.push_models import PushSubscription
from auxd_api.modules.reviews.models import Review, ReviewEditHistory, ReviewLike
from auxd_api.modules.social.models import Block, Follow, FollowRequest
from auxd_api.modules.users.models import HandleRedirect, User
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.worker.gdpr_export")

# 24-hour presigned URL TTL.
_URL_TTL_SECONDS = 24 * 60 * 60

# Fields stripped from the User row before serialisation.
_USER_REDACTED_FIELDS = frozenset({"password_hash", "admin_notes", "session_version"})


def _serialise_doc(doc: Document) -> dict[str, Any]:
    """Convert a Beanie Document to a JSON-safe dict.

    Pydantic's ``model_dump`` produces an ``id`` field instead of ``_id``
    which is what humans want to see in their export. ``mode="json"``
    triggers serialisation of datetimes + enums to JSON-compatible
    primitives.
    """
    payload: dict[str, Any] = doc.model_dump(mode="json", by_alias=False)
    return payload


def _strip_sensitive_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in _USER_REDACTED_FIELDS}


async def _aggregate_user_data(user_id: str) -> dict[str, list[dict[str, Any]]]:
    """Lift every owned collection's rows for ``user_id`` into a dict.

    Each value is an array of JSON-safe row dicts. Keys are stable
    snake_case collection names — the JSON consumer (the user / their
    lawyer / their next service) can rely on them.
    """
    user = await User.find_one(User.id == user_id)
    if user is None:
        return {}

    out: dict[str, list[dict[str, Any]]] = {}
    out["user"] = [_strip_sensitive_fields(_serialise_doc(user))]

    out["diary_entries"] = [
        _serialise_doc(d) async for d in DiaryEntry.find(DiaryEntry.user_id == user_id)
    ]
    out["reviews"] = [_serialise_doc(r) async for r in Review.find(Review.user_id == user_id)]
    review_ids = [r["id"] for r in out["reviews"]]
    out["review_likes"] = [
        _serialise_doc(rl) async for rl in ReviewLike.find(ReviewLike.user_id == user_id)
    ]
    out["review_edit_history"] = (
        [
            _serialise_doc(r)
            async for r in ReviewEditHistory.find({"review_id": {"$in": review_ids}})
        ]
        if review_ids
        else []
    )

    out["backlogs"] = [_serialise_doc(b) async for b in Backlog.find(Backlog.user_id == user_id)]
    backlog_ids = [b["id"] for b in out["backlogs"]]
    out["backlog_items"] = (
        [_serialise_doc(bi) async for bi in BacklogItem.find({"backlog_id": {"$in": backlog_ids}})]
        if backlog_ids
        else []
    )

    out["follows"] = [
        _serialise_doc(f)
        async for f in Follow.find({"$or": [{"follower_id": user_id}, {"followee_id": user_id}]})
    ]
    out["follow_requests"] = [
        _serialise_doc(fr)
        async for fr in FollowRequest.find(
            {"$or": [{"requester_id": user_id}, {"requestee_id": user_id}]}
        )
    ]
    out["blocks"] = [_serialise_doc(b) async for b in Block.find(Block.blocker_id == user_id)]
    out["notifications"] = [
        _serialise_doc(n) async for n in Notification.find(Notification.user_id == user_id)
    ]
    out["push_subscriptions"] = [
        _serialise_doc(ps)
        async for ps in PushSubscription.find(PushSubscription.user_id == user_id)
    ]
    out["handle_redirects"] = [
        _serialise_doc(h) async for h in HandleRedirect.find(HandleRedirect.user_id == user_id)
    ]
    return out


def _csv_rows_for_collection(rows: Iterable[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    """Flatten a list of row dicts into ``(header, body)`` for csv.writer.

    Header is the union of every row's keys (preserving insertion order
    of the first occurrence). Cell values that are dicts / lists are
    JSON-stringified so the CSV stays single-cell.
    """
    seen_keys: list[str] = []
    keys_set: set[str] = set()
    rows_list = list(rows)
    for row in rows_list:
        for k in row:
            if k not in keys_set:
                seen_keys.append(k)
                keys_set.add(k)
    body: list[list[Any]] = []
    for row in rows_list:
        body.append([_csv_cell(row.get(k)) for k in seen_keys])
    return seen_keys, body


def _csv_cell(value: Any) -> Any:
    if isinstance(value, dict | list):
        return json.dumps(value, default=str)
    return value


def _build_export_files(data: dict[str, list[dict[str, Any]]]) -> tuple[bytes, bytes]:
    """Return ``(json_bytes, zip_bytes)`` for the aggregated payload."""
    json_bytes = json.dumps(data, default=str, indent=2).encode("utf-8")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for collection_name, rows in data.items():
            if not rows:
                # Still include an empty CSV so the schema is documented.
                zipf.writestr(f"{collection_name}.csv", "")
                continue
            csv_buf = io.StringIO()
            writer = csv.writer(csv_buf)
            header, body = _csv_rows_for_collection(rows)
            writer.writerow(header)
            writer.writerows(body)
            zipf.writestr(f"{collection_name}.csv", csv_buf.getvalue())
    return json_bytes, zip_buf.getvalue()


def _build_r2_client() -> Any:
    """Construct a boto3 S3 client pointed at R2.

    Mirrors :func:`auxd_api.lib.storage._build_s3_client` — duplicated
    here (small) so the export worker doesn't import an avatar-specific
    helper. A future refactor can consolidate when a third bucket
    appears.
    """
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _upload_and_presign(
    *,
    client: Any,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    """Upload an object and return a 24h GET-presigned URL."""
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    url: str = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=_URL_TTL_SECONDS,
    )
    return url


def _send_export_email(
    *,
    user: User,
    json_url: str,
    zip_url: str,
    json_kb: int,
    zip_kb: int,
) -> None:
    """Send the one-off transactional email with download links.

    Resend is the SDK; we hop the sync ``Emails.send`` into a thread at
    the call site (the worker is async). Failures log + return; the
    export blobs are still in R2 so the user can be re-emailed by hand
    if needed.
    """
    settings = get_settings()
    if settings.RESEND_API_KEY is None:
        # No live email — log the URLs so an operator can hand-deliver.
        log_call(
            provider="resend",
            endpoint="export_email_noop",
            latency_ms=0.0,
            status="ok",
            extra={
                "user_id": user.id,
                "json_url": json_url,
                "zip_url": zip_url,
            },
        )
        return
    resend.api_key = settings.RESEND_API_KEY
    body = (
        f"Hi {user.display_name},\n\n"
        f"Your auxd data export is ready. Download links (valid for 24 hours):\n\n"
        f"  - JSON: {json_url}\n"
        f"  - CSV (ZIP): {zip_url}\n\n"
        f"Sizes: {json_kb} KB JSON + {zip_kb} KB ZIP.\n\n"
        f"If you didn't request this export, please contact us at "
        f"appeals@auxd.xiejoshua.com.\n"
    )
    try:
        resend.Emails.send(
            {
                "from": settings.RESEND_FROM_ADDRESS,
                "to": [user.email],
                "subject": "Your auxd data export is ready",
                "text": body,
            }
        )
    except Exception as exc:  # noqa: BLE001 — best-effort email
        log_call(
            provider="resend",
            endpoint="export_email_failed",
            latency_ms=0.0,
            status="failed",
            extra={"user_id": user.id, "error": str(exc)},
        )


async def generate_user_data_export(ctx: dict[str, Any], user_id: str) -> dict[str, Any]:
    """End-to-end worker job: aggregate → upload → email.

    Returns a small summary dict the result-store can surface (mostly
    for tests / ops debugging — production callers don't read the
    return value).
    """
    job_id = ctx.get("job_id", "manual")
    started = datetime.now(UTC)

    user = await User.find_one(User.id == user_id)
    if user is None:
        log_call(
            provider="auxd",
            endpoint="gdpr_export.user_missing",
            latency_ms=0.0,
            status="failed",
            extra={"user_id": user_id},
        )
        return {"status": "user_missing"}

    data = await _aggregate_user_data(user_id)
    json_bytes, zip_bytes = _build_export_files(data)
    json_kb = max(1, len(json_bytes) // 1024)
    zip_kb = max(1, len(zip_bytes) // 1024)

    settings = get_settings()
    bucket = settings.R2_EXPORT_BUCKET

    client = _build_r2_client()
    base_key = f"exports/{user_id}/{job_id}"
    json_url = _upload_and_presign(
        client=client,
        bucket=bucket,
        key=f"{base_key}/export.json",
        body=json_bytes,
        content_type="application/json",
    )
    zip_url = _upload_and_presign(
        client=client,
        bucket=bucket,
        key=f"{base_key}/export.zip",
        body=zip_bytes,
        content_type="application/zip",
    )

    _send_export_email(
        user=user,
        json_url=json_url,
        zip_url=zip_url,
        json_kb=json_kb,
        zip_kb=zip_kb,
    )

    await record_gdpr_event(
        user_id,
        GdprAuditAction.EXPORT_COMPLETED,
        notes=f"json: {json_kb} KB, zip: {zip_kb} KB",
        completed=True,
    )

    log_call(
        provider="auxd",
        endpoint="gdpr_export.completed",
        latency_ms=(datetime.now(UTC) - started).total_seconds() * 1000,
        status="ok",
        extra={
            "user_id": user_id,
            "json_kb": json_kb,
            "zip_kb": zip_kb,
            "collections": len(data),
        },
    )
    return {
        "status": "completed",
        "json_kb": json_kb,
        "zip_kb": zip_kb,
        "collections": len(data),
    }


__all__ = ["generate_user_data_export"]
