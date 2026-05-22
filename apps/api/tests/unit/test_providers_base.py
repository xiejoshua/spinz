"""Unit tests for :mod:`auxd_api.providers.base` (T041)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from auxd_api.providers.base import (
    CatalogAlbum,
    CatalogProvider,
    ListeningEvent,
    MusicProvider,
)


class TestCatalogAlbum:
    def test_minimal_construction(self) -> None:
        album = CatalogAlbum(title="OK Computer", artist_name="Radiohead")
        assert album.title == "OK Computer"
        assert album.artist_name == "Radiohead"
        assert album.mbid is None
        assert album.discogs_release_id is None
        assert album.release_year is None
        assert album.cover_art_url is None
        assert album.external_ids == {}

    def test_full_construction(self) -> None:
        album = CatalogAlbum(
            mbid="b1392450-e666-3926-a536-22c65f834433",
            discogs_release_id="249504",
            title="OK Computer",
            artist_name="Radiohead",
            release_year=1997,
            cover_art_url="https://coverartarchive.org/release-group/abc/front",
            external_ids={"mbid": "b1392450-e666-3926-a536-22c65f834433", "discogs": "249504"},
        )
        assert album.mbid == "b1392450-e666-3926-a536-22c65f834433"
        assert album.release_year == 1997

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            CatalogAlbum(title="x", artist_name="y", junk="nope")  # type: ignore[call-arg]

    def test_is_frozen(self) -> None:
        album = CatalogAlbum(title="A", artist_name="B")
        with pytest.raises(ValidationError):
            album.title = "C"  # type: ignore[misc]

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            CatalogAlbum(artist_name="Radiohead")  # type: ignore[call-arg]


class TestListeningEvent:
    def test_construction(self) -> None:
        evt = ListeningEvent(
            provider="spotify",
            track_name="Paranoid Android",
            artist_name="Radiohead",
            played_at="2026-05-22T12:00:00Z",
        )
        assert evt.provider == "spotify"
        assert evt.album_title is None


# ---------------------------------------------------------------------------
# Protocol structural typing — fake implementations should satisfy
# isinstance(runtime=False) and type-check against the Protocol.
# ---------------------------------------------------------------------------


class _FakeCatalog:
    """Minimal stand-in that matches the :class:`CatalogProvider` shape."""

    async def search_albums(self, query: str, limit: int = 10) -> list[CatalogAlbum]:
        return [CatalogAlbum(title=query, artist_name="Test")]

    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None:
        return None

    async def get_album_by_external_id(
        self, provider: str, external_id: str
    ) -> CatalogAlbum | None:
        return None


class _FakeMusic:
    """Minimal stand-in that matches the :class:`MusicProvider` shape."""

    async def get_recently_played(self, user_token: str, limit: int = 50) -> list[ListeningEvent]:
        return []

    async def get_currently_playing(self, user_token: str) -> ListeningEvent | None:
        return None


class TestProtocolStructuralTyping:
    async def test_catalog_provider_accepts_fake_impl(self) -> None:
        provider: CatalogProvider = _FakeCatalog()
        result = await provider.search_albums("OK Computer")
        assert len(result) == 1
        assert result[0].title == "OK Computer"

    async def test_music_provider_accepts_fake_impl(self) -> None:
        provider: MusicProvider = _FakeMusic()
        recent = await provider.get_recently_played(user_token="tok")
        now_playing = await provider.get_currently_playing(user_token="tok")
        assert recent == []
        assert now_playing is None
