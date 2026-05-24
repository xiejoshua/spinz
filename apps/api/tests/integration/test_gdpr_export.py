"""TC-030: Data export endpoint + worker tests (T153).

Covers:

* ``POST /api/v1/users/me/data-export`` returns 202 with job + audit
  ids; the EXPORT_REQUESTED audit row exists post-call.
* The endpoint requires authentication (401 anonymous).
* The worker happy path: aggregates rows, uploads to R2 (boto3
  monkeypatched), sends email via Resend (monkeypatched), writes the
  EXPORT_COMPLETED audit row.
* Sensitive fields (``password_hash``, ``admin_notes``,
  ``session_version``) are stripped from the export.
* Empty-user happy path: a brand-new account with no diary entries
  still produces a valid export with empty arrays.
* 24h presigned URL TTL is what the worker requests.
"""

from __future__ import annotations

import base64
import json
import secrets
import zipfile
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.gdpr.models import GdprAuditAction, GdprAuditLog
from auxd_api.modules.users.models import User
from auxd_api.modules.users.routes import router as users_router
from auxd_api.workers import gdpr_export as export_module
from auxd_api.workers.gdpr_export import generate_user_data_export
from tests.integration._auth_helpers import FakeAuthMiddleware


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in ("SESSION_HMAC_KEY", "TOKEN_ENCRYPTION_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await User.delete_all()
    await DiaryEntry.delete_all()
    await Album.delete_all()
    await GdprAuditLog.delete_all()
    yield
    await User.delete_all()
    await DiaryEntry.delete_all()
    await Album.delete_all()
    await GdprAuditLog.delete_all()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(users_router, prefix="/api/v1")
    return app


def _make_user(user_id: str = "user-export", handle: str = "exporter") -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
        admin_notes="should-not-leak",
        session_version=5,
    )


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from auxd_api.lib import rate_limit as rate_limit_module

    async def _allow_all(**_: object) -> bool:
        return True

    monkeypatch.setattr(rate_limit_module, "_check_and_record", _allow_all)


class _StubArqJob:
    job_id: str = "job-fake-export"


@pytest.fixture
def _stub_enqueue(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple[Any, ...]]]:
    """Intercept ``enqueue_job`` and return a deterministic stub job."""
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def _fake_enqueue(name: str, *args: Any, **kwargs: Any) -> _StubArqJob:
        _ = kwargs
        calls.append((name, args))
        return _StubArqJob()

    from auxd_api import redis_client as redis_module

    monkeypatch.setattr(redis_module, "enqueue_job", _fake_enqueue)
    return calls


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_export_endpoint_unauthenticated_returns_401(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    response = client.post("/api/v1/users/me/data-export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_data_export_endpoint_returns_202_and_writes_audit(
    _clean_env: None,
    _clean_db: None,
    _stub_enqueue: list[tuple[str, tuple[Any, ...]]],
) -> None:
    user = _make_user()
    await user.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/data-export",
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["eta_seconds"] == 60
    assert body["job_id"] == "job-fake-export"
    assert body["audit_log_id"] is not None

    # The enqueue captured the job with the user id.
    assert _stub_enqueue == [("generate_user_data_export", (user.id,))]

    # Audit row exists.
    audit = await GdprAuditLog.find_one(
        {"user_id": user.id, "action": GdprAuditAction.EXPORT_REQUESTED.value}
    )
    assert audit is not None
    assert audit.completed_at is None  # intent row.


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------


class _FakeS3Client:
    """In-memory S3 stub recording every put_object + presign call."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.presigns: list[dict[str, Any]] = []

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = {"body": Body, "content_type": ContentType}

    def generate_presigned_url(
        self,
        operation: str,
        *,
        Params: dict[str, Any],  # noqa: N803
        ExpiresIn: int,  # noqa: N803
    ) -> str:
        _ = operation
        self.presigns.append({"params": Params, "expires_in": ExpiresIn})
        return f"https://r2.example/{Params['Bucket']}/{Params['Key']}?signed=1"


@pytest.fixture
def _stub_r2(monkeypatch: pytest.MonkeyPatch) -> _FakeS3Client:
    client = _FakeS3Client()
    monkeypatch.setattr(export_module, "_build_r2_client", lambda: client)
    return client


@pytest.fixture
def _capture_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the Resend Emails.send call with an in-memory capture."""
    sent: list[dict[str, Any]] = []

    def _fake_send_export_email(**kwargs: Any) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(export_module, "_send_export_email", _fake_send_export_email)
    return sent


def _find_object(stub: _FakeS3Client, suffix: str) -> bytes:
    """Return the body bytes of the single object whose key ends in ``suffix``."""
    for (_bucket, key), payload in stub.objects.items():
        if key.endswith(suffix):
            body: bytes = payload["body"]
            return body
    raise AssertionError(f"no object with suffix {suffix!r} in stub R2")


@pytest.mark.asyncio
async def test_worker_happy_path_uploads_and_emails(
    _clean_env: None,
    _clean_db: None,
    _stub_r2: _FakeS3Client,
    _capture_emails: list[dict[str, Any]],
) -> None:
    user = _make_user()
    await user.insert()
    album = Album(
        id="album-1",
        mbid=None,
        title="A",
        artist_credit="X",
        release_year=2020,
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await album.insert()
    entry = DiaryEntry(
        id="entry-1",
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
    )
    await entry.insert()

    result = await generate_user_data_export({"job_id": "job-test"}, user.id)
    assert result["status"] == "completed"
    assert result["collections"] > 0

    # R2 received both blobs at the expected key prefix.
    keys = sorted(k for _bucket, k in _stub_r2.objects)
    assert any("export.json" in k for k in keys)
    assert any("export.zip" in k for k in keys)
    assert all(k.startswith(f"exports/{user.id}/job-test/") for k in keys)

    # 24h presigned URL TTL is what the worker requested.
    assert _stub_r2.presigns
    for sig in _stub_r2.presigns:
        assert sig["expires_in"] == 24 * 60 * 60

    # Email was dispatched.
    assert len(_capture_emails) == 1
    sent = _capture_emails[0]
    assert sent["user"].id == user.id
    assert sent["json_url"].endswith("export.json?signed=1")
    assert sent["zip_url"].endswith("export.zip?signed=1")

    # EXPORT_COMPLETED audit row written.
    audit = await GdprAuditLog.find_one(
        {"user_id": user.id, "action": GdprAuditAction.EXPORT_COMPLETED.value}
    )
    assert audit is not None
    assert audit.completed_at is not None
    assert audit.notes is not None
    assert "KB" in audit.notes


@pytest.mark.asyncio
async def test_worker_strips_sensitive_fields_from_user_payload(
    _clean_env: None,
    _clean_db: None,
    _stub_r2: _FakeS3Client,
    _capture_emails: list[dict[str, Any]],
) -> None:
    user = _make_user()
    await user.insert()
    await generate_user_data_export({"job_id": "job-1"}, user.id)

    json_blob = _find_object(_stub_r2, ".json")
    parsed = json.loads(json_blob)
    user_export = parsed["user"][0]
    # All three sensitive fields must be absent.
    assert "password_hash" not in user_export
    assert "admin_notes" not in user_export
    assert "session_version" not in user_export
    # But the handle / display_name remain.
    assert user_export["handle"] == "exporter"


@pytest.mark.asyncio
async def test_worker_handles_empty_user_gracefully(
    _clean_env: None,
    _clean_db: None,
    _stub_r2: _FakeS3Client,
    _capture_emails: list[dict[str, Any]],
) -> None:
    """A user with no diary / reviews / etc. still produces a valid export."""
    user = _make_user()
    await user.insert()

    result = await generate_user_data_export({"job_id": "job-empty"}, user.id)
    assert result["status"] == "completed"

    parsed = json.loads(_find_object(_stub_r2, ".json"))
    # User row is present; every other collection's array is empty.
    assert len(parsed["user"]) == 1
    assert parsed["diary_entries"] == []
    assert parsed["reviews"] == []
    assert parsed["follows"] == []


@pytest.mark.asyncio
async def test_worker_zip_archive_contains_per_collection_csvs(
    _clean_env: None,
    _clean_db: None,
    _stub_r2: _FakeS3Client,
    _capture_emails: list[dict[str, Any]],
) -> None:
    """The ZIP holds one CSV per collection, even for empty ones."""
    user = _make_user()
    await user.insert()
    await generate_user_data_export({"job_id": "job-z"}, user.id)

    zip_blob = _find_object(_stub_r2, ".zip")
    with zipfile.ZipFile(BytesIO(zip_blob)) as zf:
        names = set(zf.namelist())
        assert "user.csv" in names
        assert "diary_entries.csv" in names
        assert "follows.csv" in names


@pytest.mark.asyncio
async def test_worker_returns_user_missing_when_user_gone(
    _clean_env: None,
    _clean_db: None,
    _stub_r2: _FakeS3Client,
    _capture_emails: list[dict[str, Any]],
) -> None:
    result = await generate_user_data_export({"job_id": "job-x"}, "does-not-exist")
    assert result == {"status": "user_missing"}
    assert _capture_emails == []
