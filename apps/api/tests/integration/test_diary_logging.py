"""Integration tests for the diary log endpoint (T073 + T076 + T074 read path).

Drives ``POST /api/v1/diary/entries`` and ``GET /api/v1/users/{handle}/diary``
through a FastAPI :class:`TestClient`. Auth is forged by attaching a
:class:`Session` directly via a fake middleware so the tests don't need
the full HMAC cookie round-trip — the visibility / idempotency /
relisten logic doesn't depend on cookie shape.

Covers:

* Happy-path log: 201 + payload shape + persisted row.
* Album-not-found: 404.
* Rating not in 0.5 halves: 422.
* Idempotency: double-tap returns 200 with the same id.
* Relisten flag: second log for the same album flips the flag.
* Review attachment: review document created + linked.
* Unauthenticated request: 401.
* Visibility matrix on the diary read endpoint (T074):
  - owner sees their private entries
  - follower sees followers-vis entries
  - anonymous sees only public entries
  - unknown handle: 404
  - auxed filter: ``?auxed=true`` returns only auxed rows
  - cursor pagination: next_cursor advances the page
"""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auxd_api import settings as settings_module
from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.diary.routes import router as diary_router
from auxd_api.modules.reviews.models import Review
from auxd_api.modules.social.models import Follow, FollowState
from auxd_api.modules.users.models import User
from tests.integration._auth_helpers import FakeAuthMiddleware


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


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(diary_router, prefix="/api/v1")
    return app


def _make_album(album_id: str = "album-001") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title="Test Album",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_user(user_id: str, handle: str) -> User:
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
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await User.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await Follow.delete_all()
    await User.delete_all()


# ---------------------------------------------------------------------------
# T073 — log endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_happy_path_returns_201(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 4.5, "auxed": True},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["album_id"] == album.id
    assert body["rating"] == 4.5
    assert body["auxed"] is True
    assert body["relisten"] is False
    assert body["review_id"] is None
    assert body["visibility"] == "public"
    # Row is persisted.
    persisted = await DiaryEntry.get(body["id"])
    assert persisted is not None
    assert persisted.user_id == "user-casey"


@pytest.mark.asyncio
async def test_log_unauthenticated_returns_401(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        json={"album_id": album.id, "rating": 4.0},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_log_unknown_album_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": "nonexistent-album", "rating": 4.0},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "album_not_found"


@pytest.mark.asyncio
async def test_log_rating_not_in_halves_returns_422(_clean_env: None, _clean_db: None) -> None:
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 3.7},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "rating_not_in_halves"


@pytest.mark.asyncio
async def test_log_rating_below_minimum_returns_422(_clean_env: None, _clean_db: None) -> None:
    """Pydantic bounds reject rating below 0.5 with the standard 422 shape."""
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 0.0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_log_idempotent_within_60_seconds_returns_200(
    _clean_env: None, _clean_db: None
) -> None:
    """Double-tap within 60s returns the same entry with status 200."""
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    first = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_id
    # Only one row persisted.
    rows = await DiaryEntry.find({"user_id": "user-casey", "album_id": album.id}).to_list()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_log_relisten_flag_flips_on_second_distinct_log(
    _clean_env: None, _clean_db: None
) -> None:
    """A prior entry (outside the idempotency window) sets relisten=True on the next log."""
    album = _make_album()
    await album.insert()
    # Backdate a prior entry so the 60s idempotency window doesn't catch it.
    older = datetime.now(UTC) - timedelta(minutes=10)
    prior = DiaryEntry(
        user_id="user-casey",
        album_id=album.id,
        logged_at=older,
        rating=4.0,
        created_at=older,
        updated_at=older,
    )
    await prior.insert()

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={"album_id": album.id, "rating": 4.5},
    )
    assert response.status_code == 201
    assert response.json()["relisten"] is True


@pytest.mark.asyncio
async def test_log_creates_attached_review(_clean_env: None, _clean_db: None) -> None:
    """When ``review_body`` is provided, a Review is created and linked."""
    album = _make_album()
    await album.insert()
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/diary/entries",
        headers={"X-User-Id": "user-casey"},
        json={
            "album_id": album.id,
            "rating": 5.0,
            "review_body": "An all-timer",
            "visibility": "followers",
        },
    )
    assert response.status_code == 201
    review_id = response.json()["review_id"]
    assert review_id is not None
    review = await Review.get(review_id)
    assert review is not None
    assert review.body == "An all-timer"
    assert review.diary_entry_id == response.json()["id"]
    # Visibility mirrors the entry's visibility.
    assert review.visibility == "followers"


# ---------------------------------------------------------------------------
# T074 — read endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_unknown_handle_returns_404(_clean_env: None, _clean_db: None) -> None:
    client = TestClient(_make_app())
    response = client.get("/api/v1/users/ghost/diary")
    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"


@pytest.mark.asyncio
async def test_read_owner_sees_own_private_entries(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    private_entry = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PRIVATE,
    )
    await private_entry.insert()
    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{user.handle}/diary",
        headers={"X-User-Id": user.id},
    )
    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()["entries"]}
    assert private_entry.id in ids


@pytest.mark.asyncio
async def test_read_anonymous_sees_only_public_entries(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    public = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    private = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PRIVATE,
    )
    followers_only = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=3.0,
        visibility=Visibility.FOLLOWERS,
    )
    await public.insert()
    await private.insert()
    await followers_only.insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()["entries"]}
    assert public.id in ids
    assert private.id not in ids
    assert followers_only.id not in ids


@pytest.mark.asyncio
async def test_read_follower_sees_followers_visibility_entries(
    _clean_env: None, _clean_db: None
) -> None:
    owner = _make_user("user-casey", "casey")
    viewer = _make_user("user-bob", "bob")
    await owner.insert()
    await viewer.insert()
    await Follow(
        follower_id=viewer.id,
        followee_id=owner.id,
        state=FollowState.ACCEPTED,
    ).insert()
    album = _make_album()
    await album.insert()
    followers_only = DiaryEntry(
        user_id=owner.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.FOLLOWERS,
    )
    private = DiaryEntry(
        user_id=owner.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PRIVATE,
    )
    await followers_only.insert()
    await private.insert()

    client = TestClient(_make_app())
    response = client.get(
        f"/api/v1/users/{owner.handle}/diary",
        headers={"X-User-Id": viewer.id},
    )
    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()["entries"]}
    assert followers_only.id in ids
    assert private.id not in ids


@pytest.mark.asyncio
async def test_read_excludes_deleted_entries(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    soft_deleted = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
        deleted_at=datetime.now(UTC),
    )
    await soft_deleted.insert()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    assert response.status_code == 200
    assert response.json()["entries"] == []


@pytest.mark.asyncio
async def test_read_auxed_filter_returns_only_auxed_entries(
    _clean_env: None, _clean_db: None
) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    auxed_entry = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.5,
        auxed=True,
        visibility=Visibility.PUBLIC,
    )
    not_auxed = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=3.0,
        auxed=False,
        visibility=Visibility.PUBLIC,
    )
    await auxed_entry.insert()
    await not_auxed.insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary?auxed=true")
    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()["entries"]}
    assert ids == {auxed_entry.id}


@pytest.mark.asyncio
async def test_read_cursor_pagination_advances_pages(_clean_env: None, _clean_db: None) -> None:
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    # Five public entries — we'll page through with limit=2.
    entries: list[DiaryEntry] = []
    for i in range(5):
        entry = DiaryEntry(
            user_id=user.id,
            album_id=album.id,
            logged_at=datetime.now(UTC) - timedelta(minutes=i),
            rating=4.0,
            visibility=Visibility.PUBLIC,
        )
        await entry.insert()
        entries.append(entry)

    client = TestClient(_make_app())
    first = client.get(f"/api/v1/users/{user.handle}/diary?limit=2")
    assert first.status_code == 200
    body1 = first.json()
    assert len(body1["entries"]) == 2
    assert body1["next_cursor"] is not None

    second = client.get(f"/api/v1/users/{user.handle}/diary?limit=2&cursor={body1['next_cursor']}")
    body2 = second.json()
    # Pages don't overlap.
    page1_ids = {e["id"] for e in body1["entries"]}
    page2_ids = {e["id"] for e in body2["entries"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_read_limit_capped_at_hundred(_clean_env: None, _clean_db: None) -> None:
    """limit=500 is silently capped to 100 so the response stays bounded."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary?limit=500")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_read_includes_album_sidecar_for_referenced_albums(
    _clean_env: None, _clean_db: None
) -> None:
    """Diary response carries a deduped map of album cards keyed by id (T080)."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    album_a = _make_album("album-aaa")
    album_b = _make_album("album-bbb")
    # _make_album uses fixed title/artist defaults — overwrite to make the
    # response easy to assert against.
    album_a.title = "Carrie & Lowell"
    album_a.artist_credit = "Sufjan Stevens"
    album_b.title = "To Pimp a Butterfly"
    album_b.artist_credit = "Kendrick Lamar"
    await album_a.insert()
    await album_b.insert()

    # Two entries on album_a (relisten), one on album_b. The sidecar
    # should still report two album entries, not three.
    for rating in (4.0, 4.5):
        await DiaryEntry(
            user_id=user.id,
            album_id=album_a.id,
            logged_at=datetime.now(UTC),
            rating=rating,
            visibility=Visibility.PUBLIC,
        ).insert()
    await DiaryEntry(
        user_id=user.id,
        album_id=album_b.id,
        logged_at=datetime.now(UTC),
        rating=5.0,
        visibility=Visibility.PUBLIC,
    ).insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    body = response.json()
    assert response.status_code == 200
    assert set(body["albums"].keys()) == {album_a.id, album_b.id}
    assert body["albums"][album_a.id]["title"] == "Carrie & Lowell"
    assert body["albums"][album_a.id]["artist_credit"] == "Sufjan Stevens"
    # Every entry's album_id resolves to an album-card row in the sidecar.
    for entry in body["entries"]:
        assert entry["album_id"] in body["albums"]


@pytest.mark.asyncio
async def test_read_albums_sidecar_empty_when_no_entries(_clean_env: None, _clean_db: None) -> None:
    """A user with zero diary rows returns an empty albums map, not missing."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["albums"] == {}
    assert body["reviews"] == {}


@pytest.mark.asyncio
async def test_read_reviews_sidecar_includes_body_for_attached_reviews(
    _clean_env: None, _clean_db: None
) -> None:
    """Diary entries with attached reviews surface body via reviews sidecar."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    entry = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.5,
        visibility=Visibility.PUBLIC,
    )
    await entry.insert()
    review = Review(
        user_id=user.id,
        album_id=album.id,
        diary_entry_id=entry.id,
        body="a personal **favorite**.",
        visibility=Visibility.PUBLIC,
    )
    await review.insert()
    entry.review_id = review.id
    await entry.save()
    # Plain diary entry with no review attached — should not appear in sidecar.
    bare = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=3.0,
        visibility=Visibility.PUBLIC,
    )
    await bare.insert()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    assert response.status_code == 200
    body = response.json()
    assert review.id in body["reviews"]
    assert body["reviews"][review.id]["body"] == "a personal **favorite**."
    assert body["reviews"][review.id]["id"] == review.id
    # Sidecar contains exactly the reviews attached to visible entries.
    assert set(body["reviews"].keys()) == {review.id}


@pytest.mark.asyncio
async def test_read_reviews_sidecar_excludes_soft_deleted(
    _clean_env: None, _clean_db: None
) -> None:
    """Soft-deleted reviews stay out of the sidecar even when the parent entry is visible."""
    user = _make_user("user-casey", "casey")
    await user.insert()
    album = _make_album()
    await album.insert()
    entry = DiaryEntry(
        user_id=user.id,
        album_id=album.id,
        logged_at=datetime.now(UTC),
        rating=4.0,
        visibility=Visibility.PUBLIC,
    )
    await entry.insert()
    review = Review(
        user_id=user.id,
        album_id=album.id,
        diary_entry_id=entry.id,
        body="removed.",
        visibility=Visibility.PUBLIC,
        deleted_at=datetime.now(UTC),
    )
    await review.insert()
    entry.review_id = review.id
    await entry.save()

    client = TestClient(_make_app())
    response = client.get(f"/api/v1/users/{user.handle}/diary")
    assert response.status_code == 200
    body = response.json()
    # Entry still surfaces; its review row does not.
    assert any(e["id"] == entry.id for e in body["entries"])
    assert body["reviews"] == {}
