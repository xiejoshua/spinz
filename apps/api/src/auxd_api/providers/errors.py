"""Provider error taxonomy — T052.

Every external-provider failure is mapped to one of these types before
escaping the provider package. Feature code catches the precise subtype
relevant to its semantics; the FastAPI exception handler in
:mod:`auxd_api.main` translates each into the appropriate HTTP status.

Hierarchy::

    ProviderError                  (abstract base — never raised directly)
    ├── ProviderUnavailable        → HTTP 503 (network failure / 5xx-after-retries)
    ├── ProviderRateLimited        → HTTP 429 (provider returned 429; retry-after honoured)
    ├── ProviderAuthRevoked        → HTTP 401 (token revoked / consent withdrawn)
    └── ProviderNotFound           → HTTP 404 (lookup expected a hit, got none)

All subclasses carry an optional ``provider`` field so logs and Sentry
events can be filtered by upstream dependency without parsing the
exception message.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider-originated failures.

    Never raised directly — use one of the four concrete subclasses. Catch
    this base when you genuinely want to absorb any provider failure (the
    catalog fallback strategy, for instance, catches ``ProviderError`` to
    fall through MusicBrainz → Discogs).
    """

    def __init__(self, message: str = "", *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider

    def __repr__(self) -> str:
        cls = type(self).__name__
        message = str(self) or "<no message>"
        if self.provider is not None:
            return f"{cls}(provider={self.provider!r}, message={message!r})"
        return f"{cls}(message={message!r})"


class ProviderUnavailable(ProviderError):
    """Raised when a provider is unreachable or returning 5xx after retries.

    Translates to ``HTTP 503``. Network errors (connection refused, DNS
    failure), timeouts, and any 5xx response that survives the retry stack
    all funnel here. The circuit breaker (Constitution P1) will trip after
    repeated occurrences to stop hammering the upstream.
    """


class ProviderRateLimited(ProviderError):
    """Raised when a provider returns ``HTTP 429``.

    Translates to ``HTTP 429`` for the auxd caller. NOT retried by the
    resilience stack — 429 means "back off", not "try again immediately".
    Retry-After hints (when surfaced) propagate via the message.
    """


class ProviderAuthRevoked(ProviderError):
    """Raised when a token-based provider returns a non-recoverable 401.

    Translates to ``HTTP 401`` for the auxd caller. MVP has no
    user-authenticated provider integrations (CR-001 removed Spotify), so
    this type is unused at MVP — kept for v2 streaming-platform
    integration where revoked OAuth tokens are a meaningful failure mode.
    """


class ProviderNotFound(ProviderError):
    """Raised when a lookup that expected a hit returns 404 / empty.

    Translates to ``HTTP 404`` for the auxd caller. ``search_*`` methods
    never raise this — they return an empty list. Single-record lookups
    (``get_album_by_mbid``, etc.) on the :class:`CatalogProvider`
    Protocol return ``None`` for 404 by contract; this type exists for
    upstream lookups where a missing record is itself a user-visible
    error condition.
    """


__all__ = [
    "ProviderAuthRevoked",
    "ProviderError",
    "ProviderNotFound",
    "ProviderRateLimited",
    "ProviderUnavailable",
]
