"""Albums module errors (T063).

Local error taxonomy for identity resolution + album-detail flows. These
sit alongside (not inside) :mod:`auxd_api.providers.errors`: the provider
hierarchy describes external-API failures (``ProviderUnavailable``,
``ProviderRateLimited``, ...), whereas this module describes
album-domain semantic failures (a known MBID resolves to no record).

Keeping them separate lets the FastAPI exception handler distinguish a
provider outage (HTTP 503, with circuit-breaker implications) from a
genuine catalog miss (HTTP 404).
"""

from __future__ import annotations


class AlbumNotFoundError(Exception):
    """Raised when an identity resolution cannot find a matching album.

    ``resolve_identity`` raises this when neither the local cache nor the
    upstream MusicBrainz / Discogs lookup yields a record for the supplied
    identifier(s). Translates to ``HTTP 404`` at the route layer.
    """

    def __init__(self, message: str = "album not found") -> None:
        super().__init__(message)


__all__ = ["AlbumNotFoundError"]
