"""Integration tests for the backlog CRUD endpoints (T095).

Covers the full mutation + read surface added under
``/api/v1/users/me/backlog``:

* POST /items — add (happy path, 404 album, 409 duplicate, 201 status).
* DELETE /items/{id} — remove (204, 404 unknown, 403 cross-user,
  positions stay contiguous).
* PATCH /items/reorder — reorder (happy path, 422 mismatched body,
  404 unknown id, contiguous positions preserved).
* GET /items — list (sort, sidecar, cursor pagination across two pages).
* GET /contains — membership check.

Auth is forged via ``X-User-Id`` through the local fake middleware so
the tests don't depend on the HMAC cookie machinery.
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auxd_api import settings as settings_module
from auxd_api.lib.sessions import Session
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.backlog.routes import router as backlog_router
from auxd_api.modules.users.models import User


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "DISCOGS_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    """Attach a :class:`Session` based on the ``X-User-Id`` header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            request.state.session = Session(
                user_id=user_id,
                csrf_token="test-csrf",
                issued_at=0,
                expires_at=int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
                session_version=1,
            )
        else:
            request.state.session = None
        return await call_next(request)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(_FakeAuthMiddleware)
    app.include_router(backlog_router, prefix="/api/v1")
    return app


def _make_album(album_id: str = "album-bl-001", title: str = "Backlog Album") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title=title,
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_user(user_id: str = "user-casey", handle: str = "casey") -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await Backlog.delete_all()
    await BacklogItem.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# POST /items — add
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_happy_path_auto_creates_backlog(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["album_id"] == album.id
    assert body["position"] == 1
    assert body["per_item_visibility"] is None

    # Backlog row was auto-created on first add.
    backlog = await Backlog.find_one({"user_id": "user-casey"})
    assert backlog is not None
    # BacklogItem persisted.
    item = await BacklogItem.get(body["id"])
    assert item is not None
    assert item.backlog_id == backlog.id


@pytest.mark.asyncio
async def test_add_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/backlog/items",
        json={"album_id": album.id},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_unknown_album_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": "ghost-album"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "album_not_found"


@pytest.mark.asyncio
async def test_add_duplicate_returns_409(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    first = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "already_in_backlog"


@pytest.mark.asyncio
async def test_add_positions_increment_in_order(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    positions = []
    for i in range(3):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        response = client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )
        assert response.status_code == 201
        positions.append(response.json()["position"])
    assert positions == [1, 2, 3]


@pytest.mark.asyncio
async def test_add_carries_notes_and_visibility(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={
            "album_id": album.id,
            "notes": "saw on /r/indieheads — listen tonight",
            "per_item_visibility": "private",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["notes"] == "saw on /r/indieheads — listen tonight"
    assert body["per_item_visibility"] == "private"


# ---------------------------------------------------------------------------
# DELETE /items/{id} — remove
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_happy_path_returns_204(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    add = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    item_id = add.json()["id"]
    delete = client.delete(
        f"/api/v1/users/me/backlog/items/{item_id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert delete.status_code == 204
    # Item is gone.
    assert await BacklogItem.get(item_id) is None


@pytest.mark.asyncio
async def test_delete_unknown_item_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.delete(
        "/api/v1/users/me/backlog/items/does-not-exist",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_cross_user_returns_403(_clean_env: None, _clean_db: None) -> None:
    # Forge an item that belongs to user-other; user-casey tries to delete.
    album = _make_album()
    await album.insert()
    other_backlog = Backlog(user_id="user-other")
    await other_backlog.insert()
    other_item = BacklogItem(
        backlog_id=other_backlog.id,
        album_id=album.id,
        position=1,
    )
    await other_item.insert()

    client = TestClient(_make_app())
    response = client.delete(
        f"/api/v1/users/me/backlog/items/{other_item.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 403
    # Item is untouched.
    assert await BacklogItem.get(other_item.id) is not None


@pytest.mark.asyncio
async def test_delete_compacts_remaining_positions(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    ids: list[str] = []
    for i in range(4):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        response = client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )
        ids.append(response.json()["id"])

    # Remove the 2nd item — positions 1, 2, 3, 4 should compact to 1, 2, 3.
    delete = client.delete(
        f"/api/v1/users/me/backlog/items/{ids[1]}",
        headers={"X-User-Id": "user-casey"},
    )
    assert delete.status_code == 204

    list_response = client.get(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
    )
    assert list_response.status_code == 200
    positions = [item["position"] for item in list_response.json()["items"]]
    assert positions == [1, 2, 3]


# ---------------------------------------------------------------------------
# PATCH /items/reorder — reorder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reorder_happy_path(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    ids: list[str] = []
    for i in range(3):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        response = client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )
        ids.append(response.json()["id"])

    # Reverse the order.
    reversed_ids = list(reversed(ids))
    reorder = client.patch(
        "/api/v1/users/me/backlog/items/reorder",
        headers={"X-User-Id": "user-casey"},
        json={"item_ids": reversed_ids},
    )
    assert reorder.status_code == 200, reorder.text
    response_ids = [item["id"] for item in reorder.json()["items"]]
    assert response_ids == reversed_ids
    # And every position lines up 1, 2, 3.
    response_positions = [item["position"] for item in reorder.json()["items"]]
    assert response_positions == [1, 2, 3]


@pytest.mark.asyncio
async def test_reorder_missing_item_returns_422(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    ids: list[str] = []
    for i in range(3):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        response = client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )
        ids.append(response.json()["id"])

    # Only send the first two — one item is missing.
    short = client.patch(
        "/api/v1/users/me/backlog/items/reorder",
        headers={"X-User-Id": "user-casey"},
        json={"item_ids": ids[:2]},
    )
    assert short.status_code == 422
    assert short.json()["detail"] == "reorder_mismatch"


@pytest.mark.asyncio
async def test_reorder_duplicate_id_returns_422(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    ids: list[str] = []
    for i in range(2):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        response = client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )
        ids.append(response.json()["id"])

    dup = client.patch(
        "/api/v1/users/me/backlog/items/reorder",
        headers={"X-User-Id": "user-casey"},
        json={"item_ids": [ids[0], ids[0]]},
    )
    assert dup.status_code == 422


@pytest.mark.asyncio
async def test_reorder_unknown_id_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    album = _make_album()
    await album.insert()
    add = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    real_id = add.json()["id"]
    response = client.patch(
        "/api/v1/users/me/backlog/items/reorder",
        headers={"X-User-Id": "user-casey"},
        json={"item_ids": [real_id, "fake-id"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "item_not_found"


# ---------------------------------------------------------------------------
# GET /items — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty_backlog(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None
    assert body["albums"] == {}


@pytest.mark.asyncio
async def test_list_returns_items_sorted_by_position(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    for i in range(3):
        album = _make_album(album_id=f"album-{i:03d}", title=f"Album {i}")
        await album.insert()
        client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )

    response = client.get(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
    )
    body = response.json()
    positions = [item["position"] for item in body["items"]]
    assert positions == [1, 2, 3]
    # Sidecar album cards keyed by id.
    assert set(body["albums"].keys()) == {"album-000", "album-001", "album-002"}
    assert body["albums"]["album-000"]["title"] == "Album 0"


@pytest.mark.asyncio
async def test_list_cursor_paginates_across_two_pages(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    for i in range(5):
        album = _make_album(album_id=f"album-{i:03d}")
        await album.insert()
        client.post(
            "/api/v1/users/me/backlog/items",
            headers={"X-User-Id": "user-casey"},
            json={"album_id": album.id},
        )

    first = client.get(
        "/api/v1/users/me/backlog/items?limit=2",
        headers={"X-User-Id": "user-casey"},
    )
    body1 = first.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    second = client.get(
        f"/api/v1/users/me/backlog/items?limit=2&cursor={body1['next_cursor']}",
        headers={"X-User-Id": "user-casey"},
    )
    body2 = second.json()
    assert len(body2["items"]) == 2

    page1_ids = {item["id"] for item in body1["items"]}
    page2_ids = {item["id"] for item in body2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_list_malformed_cursor_is_treated_as_no_cursor(
    _clean_env: None, _clean_db: None
) -> None:
    client = TestClient(_make_app())
    album = _make_album()
    await album.insert()
    client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )

    response = client.get(
        "/api/v1/users/me/backlog/items?cursor=not-a-real-cursor",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# GET /contains — membership check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contains_returns_false_when_no_backlog(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/users/me/backlog/contains?album_id=ghost-album",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"in_backlog": False, "item_id": None}


@pytest.mark.asyncio
async def test_contains_returns_true_with_item_id(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    album = _make_album()
    await album.insert()
    add = client.post(
        "/api/v1/users/me/backlog/items",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id},
    )
    item_id = add.json()["id"]

    response = client.get(
        f"/api/v1/users/me/backlog/contains?album_id={album.id}",
        headers={"X-User-Id": "user-casey"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["in_backlog"] is True
    assert body["item_id"] == item_id


@pytest.mark.asyncio
async def test_contains_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/me/backlog/contains?album_id=any")
    assert response.status_code == 401
