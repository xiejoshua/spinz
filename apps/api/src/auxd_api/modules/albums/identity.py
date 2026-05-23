"""Album identity normalization service (T063).

The single entry-point ``resolve_identity`` accepts a MusicBrainz MBID
and/or a Discogs release id, returns a canonical :class:`Album` document,
and lazily materialises the row when the cache misses. The flow exists
because the auxd MVP draws catalog data from two providers with no
guaranteed cross-link:

1. **MBID-first.** When the caller has an MBID, we look it up in the
   local catalog (``Album.find_one(mbid=...)``). On a hit we return the
   cached row directly. On a miss we fetch the record from MusicBrainz
   via the injected :class:`CatalogProvider`, materialise it into a new
   :class:`Album` with a 7-day cache window, persist, and return.

2. **Discogs-fallback.** When the caller only has a Discogs release id,
   the same lookup-then-fetch pattern runs against Discogs. The newly
   materialised row is marked ``candidate=True`` so the weekly MBID
   reconciliation worker (T065) can attempt to attach a real MBID later.

3. **Hard miss.** When MusicBrainz returns ``None`` for a known MBID, or
   Discogs returns ``None`` for a known release id, we raise
   :class:`AlbumNotFoundError` — translates to ``HTTP 404`` at the route
   layer.

Constitution P6 requires providers to be passed in as the
:class:`CatalogProvider` Protocol (not the concrete class) so test
doubles + future provider swaps remain trivial. Every external call
flows through that Protocol's resilient transport (Constitution P1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from auxd_api.modules.albums.errors import AlbumNotFoundError
from auxd_api.modules.albums.models import (
    Album,
    AlbumSource,
    ArtistRefSubDoc,
)
from auxd_api.providers.base import CatalogAlbum, CatalogProvider

# Cache TTL — plan §3.1 mandates a 7-day window for lazy refresh. Identity
# materialisation seeds the field on insert; the T064 worker keeps it
# fresh on a daily cron.
_CACHE_TTL = timedelta(days=7)


def _cache_expiry(now: datetime | None = None) -> datetime:
    """Return ``now + 7d`` — single source of truth for the cache TTL."""
    base = now if now is not None else datetime.now(UTC)
    return base + _CACHE_TTL


def _materialize_album(
    catalog: CatalogAlbum,
    *,
    source: AlbumSource,
    candidate: bool,
) -> Album:
    """Translate a provider-returned :class:`CatalogAlbum` into an :class:`Album`.

    The mapping is intentionally narrow — only the fields a provider
    actually populates are copied. Tracklist + label + genres land later
    via the enrichment workers (T064 refresh path).
    """
    artists: list[ArtistRefSubDoc] = []
    if catalog.artist_name:
        artists.append(ArtistRefSubDoc(name=catalog.artist_name))
    return Album(
        mbid=catalog.mbid,
        discogs_release_id=catalog.discogs_release_id,
        title=catalog.title,
        artist_credit=catalog.artist_name,
        artists=artists,
        release_year=catalog.release_year,
        cover_art_url=catalog.cover_art_url,
        source=source,
        cache_expires_at=_cache_expiry(),
        candidate=candidate,
    )


async def resolve_identity(
    *,
    mbid: str | None = None,
    discogs_release_id: str | None = None,
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
) -> Album:
    """Return the canonical :class:`Album` for the supplied identifier(s).

    Args:
        mbid: MusicBrainz release-group MBID. Preferred when present.
        discogs_release_id: Discogs release id. Used only when ``mbid`` is ``None``.
        mb_provider: Injected MusicBrainz :class:`CatalogProvider`.
        discogs_provider: Injected Discogs :class:`CatalogProvider`.

    Returns:
        The canonical :class:`Album` document — either freshly fetched
        and materialised, or the cached row when present.

    Raises:
        ValueError: Neither ``mbid`` nor ``discogs_release_id`` was supplied.
        AlbumNotFoundError: The upstream provider returned ``None`` for the id.
    """
    if mbid is not None:
        cached = await Album.find_one(Album.mbid == mbid)
        if cached is not None:
            return cached
        fetched = await mb_provider.get_album_by_mbid(mbid)
        if fetched is None:
            raise AlbumNotFoundError(f"musicbrainz: no release-group for mbid={mbid!r}")
        album = _materialize_album(
            fetched,
            source=AlbumSource.MUSICBRAINZ,
            candidate=False,
        )
        await album.insert()
        return album

    if discogs_release_id is not None:
        cached = await Album.find_one(Album.discogs_release_id == discogs_release_id)
        if cached is not None:
            return cached
        fetched = await discogs_provider.get_album_by_external_id("discogs", discogs_release_id)
        if fetched is None:
            raise AlbumNotFoundError(
                f"discogs: no release for discogs_release_id={discogs_release_id!r}"
            )
        album = _materialize_album(
            fetched,
            source=AlbumSource.DISCOGS,
            candidate=True,
        )
        await album.insert()
        return album

    raise ValueError("resolve_identity requires either mbid or discogs_release_id")


__all__ = ["resolve_identity"]
