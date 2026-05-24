"""Integration tests for the album-merge CLI (T167).

Exercises ``apps/api/scripts/merge_albums.py``'s :func:`_amain` directly
against the in-memory mongomock DB so we cover:

* ``--dry-run`` prints the summary but writes nothing.
* A successful merge rewrites every FK collection and deletes the
  losing Album row.
* The losing row truly disappears from the collection.

The CLI surface (argparse + ``main``) is one layer above the tested
function; argparse already has its own coverage upstream.
"""

from __future__ import annotations

import importlib.util
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.reviews.models import Review

_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "merge_albums.py"


def _load_cli_module() -> Any:
    """Import ``apps/api/scripts/merge_albums.py`` once and cache the module.

    Each test then operates on the SAME module object so any monkeypatch
    installed by the autouse fixture remains visible inside the test
    body.
    """
    spec = importlib.util.spec_from_file_location("merge_albums_cli", _CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CLI = _load_cli_module()


def _make_album(album_id: str, title: str = "Test Album") -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title=title,
        artist_credit="Test Artist",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def _make_entry(user_id: str, album_id: str, entry_id: str | None = None) -> DiaryEntry:
    kwargs: dict[str, Any] = {
        "user_id": user_id,
        "album_id": album_id,
        "logged_at": datetime.now(UTC),
        "visibility": Visibility.PUBLIC,
    }
    if entry_id is not None:
        kwargs["id"] = entry_id
    return DiaryEntry(**kwargs)


def _make_review(review_id: str, user_id: str, entry_id: str, album_id: str) -> Review:
    return Review(
        id=review_id,
        user_id=user_id,
        diary_entry_id=entry_id,
        album_id=album_id,
        body="loved it",
    )


def _make_backlog_item(item_id: str, backlog_id: str, album_id: str) -> BacklogItem:
    return BacklogItem(
        id=item_id,
        backlog_id=backlog_id,
        album_id=album_id,
        position=1,
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await BacklogItem.delete_all()
    await Backlog.delete_all()
    yield
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await Review.delete_all()
    await BacklogItem.delete_all()
    await Backlog.delete_all()


@pytest.fixture(autouse=True)
def _no_db_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI calls init_db/close_db; tests run against the shared mock."""
    cli = _CLI

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(cli, "init_db", _noop)
    monkeypatch.setattr(cli, "close_db", _noop)
    # Settings is touched too; stub it out.
    monkeypatch.setattr(cli, "get_settings", lambda: type("S", (), {"MONGODB_URI": "noop"})())


@pytest.mark.asyncio
async def test_dry_run_emits_summary_without_mutation(
    _clean_db: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _CLI
    losing = _make_album("alb-losing", title="Losing Album")
    winning = _make_album("alb-winning", title="Winning Album")
    await losing.insert()
    await winning.insert()
    entry = _make_entry("user-1", losing.id)
    await entry.insert()

    exit_code = await cli._amain(
        losing.id,
        winning.id,
        dry_run=True,
        yes=True,
    )
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "losing album" in captured
    assert "winning album" in captured
    assert "diary_entries=1" in captured
    assert "dry-run" in captured

    # Nothing got rewritten.
    diary_after = await DiaryEntry.find({"album_id": losing.id}).to_list()
    assert len(diary_after) == 1
    # Losing album still present.
    still_losing = await Album.find_one(Album.id == losing.id)
    assert still_losing is not None


@pytest.mark.asyncio
async def test_merge_updates_all_fk_and_deletes_losing(
    _clean_db: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _CLI
    losing = _make_album("alb-losing")
    winning = _make_album("alb-winning")
    await losing.insert()
    await winning.insert()

    entry = _make_entry("user-1", losing.id, entry_id="entry-1")
    await entry.insert()
    review = _make_review("rev-1", "user-1", entry.id, losing.id)
    await review.insert()
    backlog = Backlog(id="bl-1", user_id="user-1", name="Later")
    await backlog.insert()
    item = _make_backlog_item("bi-1", backlog.id, losing.id)
    await item.insert()

    exit_code = await cli._amain(
        losing.id,
        winning.id,
        dry_run=False,
        yes=True,
    )
    assert exit_code == 0

    # Every FK rewritten.
    diary_winning = await DiaryEntry.find({"album_id": winning.id}).to_list()
    assert len(diary_winning) == 1
    review_winning = await Review.find({"album_id": winning.id}).to_list()
    assert len(review_winning) == 1
    backlog_winning = await BacklogItem.find({"album_id": winning.id}).to_list()
    assert len(backlog_winning) == 1

    # Losing collections are empty.
    assert await DiaryEntry.find({"album_id": losing.id}).to_list() == []
    assert await Review.find({"album_id": losing.id}).to_list() == []
    assert await BacklogItem.find({"album_id": losing.id}).to_list() == []

    # Losing album row is gone.
    gone = await Album.find_one(Album.id == losing.id)
    assert gone is None
    # Winning row remains.
    still_winning = await Album.find_one(Album.id == winning.id)
    assert still_winning is not None


@pytest.mark.asyncio
async def test_merge_rejects_identical_ids(_clean_db: None) -> None:
    cli = _CLI
    album = _make_album("alb-1")
    await album.insert()

    exit_code = await cli._amain(album.id, album.id, dry_run=False, yes=True)
    assert exit_code == 1


@pytest.mark.asyncio
async def test_merge_errors_on_missing_album(_clean_db: None) -> None:
    cli = _CLI
    keeping = _make_album("alb-keep")
    await keeping.insert()

    exit_code = await cli._amain(
        "alb-missing",
        keeping.id,
        dry_run=False,
        yes=True,
    )
    assert exit_code == 1
