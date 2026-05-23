"""R2 (S3-compatible) storage client wrapper (T146).

Thin facade over ``boto3.client("s3", ...)`` so the avatar upload
endpoint doesn't need to thread credentials, endpoint URLs, and bucket
names through every call. The mongodump backup pipeline (T010a) uses
``boto3`` directly because its surface is a single one-shot upload from
a shell-out; the avatar pipeline runs in-process and benefits from a
typed helper.

Bucket convention:

* ``settings.R2_BUCKET_NAME`` (default ``auxd-backups``) — nightly
  mongodump dumps. Owned by the backup workflow.
* ``settings.R2_AVATAR_BUCKET`` (default ``auxd-avatars``) — public
  user avatar JPEGs. Owned by this module.

Avatar object keys are ``avatars/{user_id}/{size}.jpg``. The returned
URL is built from ``R2_ENDPOINT_URL`` plus the bucket + key — at MVP
we serve avatars via the same R2 endpoint that backups use; once we
front R2 with a custom CDN domain the URL builder swaps without
touching the upload sites.

The module deliberately does NOT register a Beanie / FastAPI surface —
it is a pure helper.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import boto3  # type: ignore[import-untyped]

from auxd_api.settings import Settings, get_settings

__all__ = [
    "AVATAR_SIZES",
    "MissingR2ConfigurationError",
    "build_avatar_url",
    "get_avatar_bucket",
    "upload_avatar",
]

_LOGGER = logging.getLogger("auxd.storage")

# Avatar pixel sizes shipped at upload time. Ordered largest-first so the
# primary URL (256px) is always the canonical reference and the smaller
# sizes are derived. Mutating this tuple is a schema change — older rows
# would still link to dropped sizes.
AVATAR_SIZES: Final[tuple[int, ...]] = (256, 128, 64)


class MissingR2ConfigurationError(RuntimeError):
    """Raised when the avatar uploader is invoked without R2 credentials.

    Distinguishes "ops forgot to set the env vars" from any runtime AWS
    error so the route layer can surface a clean 503 rather than a 500.
    """


def _require_settings() -> Settings:
    """Return :class:`Settings` or raise the typed error.

    Wraps ``get_settings()`` so a corrupt env raises a sentinel the
    route layer can recognise.
    """
    return get_settings()


def get_avatar_bucket() -> str:
    """Return the configured avatar bucket name.

    Centralised so the constant is a single import for tests + route
    code, and so unit tests can monkeypatch a fake bucket without
    rebuilding the whole settings object.
    """
    return _require_settings().R2_AVATAR_BUCKET


def _build_s3_client() -> Any:
    """Construct a boto3 S3 client pointed at the R2 endpoint.

    Raises :class:`MissingR2ConfigurationError` when any of the three
    required credentials are unset. Boto3's typing is too loose to give
    a precise return annotation here — the route layer treats this as
    an opaque handle.
    """
    settings = _require_settings()
    if (
        settings.R2_ACCESS_KEY_ID is None
        or settings.R2_SECRET_ACCESS_KEY is None
        or settings.R2_ENDPOINT_URL is None
    ):
        raise MissingR2ConfigurationError(
            "R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ENDPOINT_URL must all be set"
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def build_avatar_url(user_id: str, size: int) -> str:
    """Return the public URL of an avatar at ``size`` pixels.

    Pure: does not consult R2; builds the URL from ``R2_ENDPOINT_URL``
    plus the bucket + object key convention. Used both by the upload
    path (after the put) and by any read-side caller that wants to
    surface the URL without re-fetching from the User document.
    """
    settings = _require_settings()
    base = (settings.R2_ENDPOINT_URL or "").rstrip("/")
    bucket = settings.R2_AVATAR_BUCKET
    return f"{base}/{bucket}/avatars/{user_id}/{size}.jpg"


def upload_avatar(
    user_id: str,
    sized_blobs: dict[int, bytes],
    content_type: str = "image/jpeg",
) -> dict[str, str]:
    """Upload one or more sized avatar blobs and return the URL map.

    ``sized_blobs`` maps pixel size → encoded JPEG bytes. The function
    iterates :data:`AVATAR_SIZES` so the output dict always has the
    canonical keys (any missing size in the input raises ``KeyError``
    at the route layer's contract — the upload endpoint always supplies
    all three).

    Returns a ``{str(size): url}`` map (str keys for JSON-safety).
    """
    client = _build_s3_client()
    bucket = get_avatar_bucket()
    out: dict[str, str] = {}
    for size in AVATAR_SIZES:
        blob = sized_blobs[size]
        key = f"avatars/{user_id}/{size}.jpg"
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=blob,
            ContentType=content_type,
            CacheControl="public, max-age=86400",
        )
        out[str(size)] = build_avatar_url(user_id, size)
    return out
