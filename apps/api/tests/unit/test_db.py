"""Unit tests for :mod:`auxd_api.db` (T012).

These tests must not touch a real MongoDB. They cover:

* The canonical Beanie Document list is well-formed (17 entries, each a
  :class:`beanie.Document` subclass) and matches what the test conftest
  uses — guards the dedupe from regressing.
* :func:`get_client` raises before :func:`init_db` is called.
* :func:`init_db` rejects URIs missing a database name with a clear
  message.
* The redaction helper does not leak the password in error messages.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import Document
from pymongo.errors import ServerSelectionTimeoutError

from auxd_api import db as db_module
from auxd_api.db import (
    ALL_DOCUMENT_MODELS,
    _database_name_from_uri,
    _redact_uri,
    close_db,
    get_client,
    init_db,
    ping_db,
)


def test_all_document_models_has_seventeen_entries() -> None:
    assert len(ALL_DOCUMENT_MODELS) == 17


def test_all_document_models_are_beanie_documents() -> None:
    for model in ALL_DOCUMENT_MODELS:
        assert issubclass(model, Document), f"{model!r} is not a beanie.Document subclass"


def test_all_document_models_has_no_duplicates() -> None:
    assert len(set(ALL_DOCUMENT_MODELS)) == len(ALL_DOCUMENT_MODELS)


def test_canonical_list_matches_conftest_expectation() -> None:
    """Regression guard: ``conftest.py`` imports ``ALL_DOCUMENT_MODELS`` from
    :mod:`auxd_api.db`. If the names or count drift, the test suite's
    Beanie init will silently miss models. Pin the exact set here.
    """
    expected_names = {
        "User",
        "Album",
        "DiaryEntry",
        "Review",
        "ReviewLike",
        "ReviewEditHistory",
        "Backlog",
        "BacklogItem",
        "Follow",
        "FollowRequest",
        "Block",
        "Report",
        "Notification",
        "FailedEmail",
        "JustFinishedPrompt",
        "SuggestedFollow",
        "CriticSeed",
    }
    actual_names = {model.__name__ for model in ALL_DOCUMENT_MODELS}
    assert actual_names == expected_names


def test_get_client_before_init_raises() -> None:
    db_module._client = None
    with pytest.raises(RuntimeError, match="not initialised"):
        get_client()


def test_database_name_from_uri_extracts_name() -> None:
    assert _database_name_from_uri("mongodb://localhost:27017/auxd_dev") == "auxd_dev"


def test_database_name_from_uri_raises_when_missing() -> None:
    with pytest.raises(RuntimeError, match="must include a database name"):
        _database_name_from_uri("mongodb://localhost:27017")


def test_database_name_from_uri_redacts_password_in_error() -> None:
    uri = "mongodb://user:supersecret@host:27017"
    with pytest.raises(RuntimeError) as exc_info:
        _database_name_from_uri(uri)
    assert "supersecret" not in str(exc_info.value)
    assert "***" in str(exc_info.value)


def test_redact_uri_passes_through_when_no_password() -> None:
    assert _redact_uri("mongodb://localhost:27017/auxd_dev") == "mongodb://localhost:27017/auxd_dev"


def test_redact_uri_replaces_password() -> None:
    redacted = _redact_uri("mongodb://user:secretpass@host:27017/db")
    assert "secretpass" not in redacted
    assert "user:***@host" in redacted


@pytest.mark.asyncio
async def test_init_db_rejects_uri_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """``init_db`` must raise *before* opening any network connection when the
    URI is missing a database name.
    """

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("AsyncIOMotorClient must not be constructed for an invalid URI")

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", _explode)
    with pytest.raises(RuntimeError, match="must include a database name"):
        await init_db("mongodb://localhost:27017")


@pytest.mark.asyncio
async def test_init_db_pings_then_registers_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: ping succeeds → ``init_beanie`` is called with the canonical
    document list → singleton client is populated.
    """
    fake_admin = MagicMock()
    fake_admin.command = AsyncMock(return_value={"ok": 1})

    fake_db = MagicMock(name="database")
    fake_client = MagicMock(name="client")
    fake_client.admin = fake_admin
    fake_client.__getitem__.return_value = fake_db
    fake_client.close = MagicMock()

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", lambda _uri: fake_client)

    init_beanie_calls: list[dict[str, Any]] = []

    async def fake_init_beanie(**kwargs: Any) -> None:
        init_beanie_calls.append(kwargs)

    monkeypatch.setattr(db_module, "init_beanie", fake_init_beanie)
    db_module._client = None

    try:
        await init_db("mongodb://localhost:27017/auxd_test")

        fake_admin.command.assert_awaited_once_with("ping")
        assert len(init_beanie_calls) == 1
        assert init_beanie_calls[0]["database"] is fake_db
        assert init_beanie_calls[0]["document_models"] == list(ALL_DOCUMENT_MODELS)
        assert get_client() is fake_client
    finally:
        # Reset singleton so subsequent tests aren't polluted by the mock.
        db_module._client = None


@pytest.mark.asyncio
async def test_init_db_closes_client_when_ping_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the ping fails the (lazy) Motor client must be closed so we don't
    leak the connection pool. The original error must propagate.
    """
    fake_admin = MagicMock()
    fake_admin.command = AsyncMock(side_effect=ConnectionError("unreachable"))

    fake_client = MagicMock(name="client")
    fake_client.admin = fake_admin
    fake_client.close = MagicMock()

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", lambda _uri: fake_client)
    db_module._client = None

    with pytest.raises(ConnectionError, match="unreachable"):
        await init_db("mongodb://localhost:27017/auxd_test")

    fake_client.close.assert_called_once()
    assert db_module._client is None


@pytest.mark.asyncio
async def test_close_db_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    db_module._client = fake_client

    await close_db()
    fake_client.close.assert_called_once()
    assert db_module._client is None

    # Second call is a no-op.
    await close_db()
    fake_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_ping_db_returns_down_when_uninitialised() -> None:
    db_module._client = None
    assert await ping_db() == "down"


@pytest.mark.asyncio
async def test_ping_db_returns_ok_on_successful_ping() -> None:
    fake_admin = MagicMock()
    fake_admin.command = AsyncMock(return_value={"ok": 1})
    fake_client = MagicMock()
    fake_client.admin = fake_admin
    db_module._client = fake_client
    try:
        assert await ping_db() == "ok"
        fake_admin.command.assert_awaited_once_with("ping")
    finally:
        db_module._client = None


@pytest.mark.asyncio
async def test_ping_db_returns_down_on_pymongo_error() -> None:
    fake_admin = MagicMock()
    fake_admin.command = AsyncMock(side_effect=ServerSelectionTimeoutError("no primary available"))
    fake_client = MagicMock()
    fake_client.admin = fake_admin
    db_module._client = fake_client
    try:
        assert await ping_db() == "down"
    finally:
        db_module._client = None
