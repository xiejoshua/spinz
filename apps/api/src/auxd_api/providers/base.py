"""Provider Protocols + canonical internal types — Constitution P6.

The two Protocols defined here are the *only* sanctioned interface between
auxd feature code and external catalog/music APIs:

* :class:`CatalogProvider` — the MVP backbone. Concrete implementations:
  :class:`auxd_api.providers.musicbrainz.MusicBrainzCatalogProvider` (primary)
  and :class:`auxd_api.providers.discogs.DiscogsCatalogProvider` (optional
  fallback). Spotify ID identity paths were removed in CR-001.
* :class:`MusicProvider` — DEFERRED-TO-V2. Declares the streaming-platform
  interface (recently-played / currently-playing) so the abstraction is
  pinned, but no MVP implementation exists. Feature code MUST NOT depend on
  it landing before v2.

The canonical internal types (:class:`CatalogAlbum`, :class:`ListeningEvent`)
intentionally use a small, MBID-centric shape — every provider maps its
native response into these types before returning. Downstream identity
normalisation (T063) operates on these shapes alone.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class CatalogAlbum(BaseModel):
    """Provider-agnostic album representation returned by catalog lookups.

    The MBID is the canonical id at MVP. Discogs lookups return records with
    ``mbid=None`` and a populated ``discogs_release_id`` — the MBID
    reconciliation worker (T065) is responsible for filling the MBID later.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mbid: str | None = Field(
        default=None,
        description="MusicBrainz release-group MBID. Sole canonical id at MVP.",
    )
    discogs_release_id: str | None = Field(
        default=None,
        description="Discogs release id. Used as candidate identity prior to MBID reconciliation.",
    )
    discogs_master_id: str | None = Field(
        default=None,
        description=(
            "Discogs master_id — canonical Discogs identifier for an album across all "
            "pressings. Searches via Discogs `type=master` populate this; lookup via "
            "`get_album_by_external_id(provider='discogs_master', ...)` resolves this "
            "back to the master."
        ),
    )
    community_have: int | None = Field(
        default=None,
        description=(
            "Discogs community.have count — number of users who own a copy in their "
            "Discogs collection. Real popularity signal exposed by Discogs's master "
            "and release endpoints. Search results from Discogs include this; MB "
            "hits leave it None."
        ),
    )
    title: str = Field(description="Album / release-group title.")
    artist_name: str = Field(
        description="Primary artist credit. Multi-artist credits use the first joined credit."
    )
    release_year: int | None = Field(
        default=None,
        description=(
            "Year of first release (release-group level). Optional — some MB records lack it."
        ),
    )
    cover_art_url: str | None = Field(
        default=None,
        description="Direct URL to front cover art (CAA for MB, images[0].uri for Discogs).",
    )
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Provider→id map. Currently 'mbid' and/or 'discogs'; future v2 may add 'spotify'."
        ),
    )
    score: int | None = Field(
        default=None,
        description=(
            "Provider-supplied relevance score (0-100). MusicBrainz returns this "
            "on search results; lookups don't include it. Used by the search "
            "service to re-rank fallback-tier hits so canonical releases beat "
            "obscure ones for popular-artist queries."
        ),
    )


class ListeningEvent(BaseModel):
    """A single listen captured from a streaming-platform MusicProvider.

    DEFERRED-TO-V2: no MVP code creates these — they exist so the
    :class:`MusicProvider` Protocol has a typed return value pinned before
    streaming integration lands.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(description="Provider short name, e.g. 'spotify'.")
    track_name: str
    artist_name: str
    album_title: str | None = None
    played_at: str = Field(description="ISO-8601 timestamp of when the track was played.")
    external_track_id: str | None = Field(
        default=None,
        description="Provider-native track id (e.g. Spotify track id).",
    )


class CatalogProvider(Protocol):
    """Catalog lookup interface — MVP backbone.

    All catalog/identity flows in auxd (search results, album-page lazy
    fetch, MBID reconciliation worker) call into this Protocol. The two
    concrete implementations are MusicBrainz (primary) and Discogs
    (optional fallback when ``DISCOGS_API_TOKEN`` is set).
    """

    async def search_albums(self, query: str, limit: int = 10) -> list[CatalogAlbum]:
        """Return up to ``limit`` albums matching ``query``.

        ``query`` is a free-text user search term (artist + title, just
        title, etc.). Returns an empty list on zero matches — never raises
        :class:`~auxd_api.providers.errors.ProviderNotFound` for searches.
        """
        ...

    async def get_album_by_mbid(self, mbid: str) -> CatalogAlbum | None:
        """Look up a single album by MusicBrainz release-group MBID.

        Returns ``None`` (not raises) when the MBID has no match — 404 is a
        normal lookup outcome, not an error.
        """
        ...

    async def get_album_by_external_id(
        self, provider: str, external_id: str
    ) -> CatalogAlbum | None:
        """Look up a single album by a provider-native id.

        ``provider`` is one of ``"mbid"`` / ``"discogs"`` at MVP. Returns
        ``None`` when the lookup yields no match.
        """
        ...


class MusicProvider(Protocol):
    """Streaming-platform interface — DEFERRED-TO-V2 (no MVP impl).

    Pinned in code so the abstraction is locked. CR-001 (2026-05-22)
    removed the planned Spotify implementation; the Protocol stays so v2
    can add a concrete provider without re-litigating the surface area.
    """

    async def get_recently_played(self, user_token: str, limit: int = 50) -> list[ListeningEvent]:
        """Return the user's most recent listens, newest first."""
        ...

    async def get_currently_playing(self, user_token: str) -> ListeningEvent | None:
        """Return the currently-playing track, or ``None`` if nothing is playing."""
        ...


__all__ = [
    "CatalogAlbum",
    "CatalogProvider",
    "ListeningEvent",
    "MusicProvider",
]
