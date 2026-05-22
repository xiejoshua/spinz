"""External provider clients — Constitution Principle VI (provider abstraction).

Every outbound call to a catalog/music API in the auxd backend flows through
one of the :class:`~auxd_api.providers.base.CatalogProvider` or
:class:`~auxd_api.providers.base.MusicProvider` Protocols defined in
:mod:`auxd_api.providers.base`. Concrete providers (MusicBrainz, Discogs)
live in their own modules and are swappable — feature code depends on the
Protocol shape, never the concrete class.

The wider package layers are::

    base.py           — Protocols + canonical Pydantic models (CatalogAlbum,
                        ListeningEvent).
    errors.py         — ProviderError taxonomy (Unavailable, RateLimited,
                        AuthRevoked, NotFound).
    transport.py      — ResilienceTransport: httpx custom AsyncBaseTransport
                        that wraps every request with circuit_breaker + retry
                        + timeout (Constitution P1) and emits a single
                        log_call observation per request (Constitution P5).
    musicbrainz.py    — MusicBrainzCatalogProvider (catalog backbone).
    discogs.py        — DiscogsCatalogProvider (optional fallback).
"""

from __future__ import annotations

from auxd_api.providers.base import (
    CatalogAlbum,
    CatalogProvider,
    ListeningEvent,
    MusicProvider,
)
from auxd_api.providers.errors import (
    ProviderAuthRevoked,
    ProviderError,
    ProviderNotFound,
    ProviderRateLimited,
    ProviderUnavailable,
)

__all__ = [
    "CatalogAlbum",
    "CatalogProvider",
    "ListeningEvent",
    "MusicProvider",
    "ProviderAuthRevoked",
    "ProviderError",
    "ProviderNotFound",
    "ProviderRateLimited",
    "ProviderUnavailable",
]
