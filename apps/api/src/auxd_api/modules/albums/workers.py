"""Album cache + reconciliation arq jobs (T064 + T065).

Two background jobs keep the local catalog cache aligned with upstream:

* :func:`refresh_stale_album_metadata` (T064) — daily 04:00 UTC sweep that
  re-fetches Albums whose ``cache_expires_at`` has elapsed. Bounded at
  100 rows per run to avoid runaway IO when a large backlog accumulates;
  the next run will pick up the leftovers.

* :func:`reconcile_candidate_albums` (T065) — weekly Sunday 03:00 UTC sweep
  that walks ``candidate=True`` rows (Discogs-sourced) and attempts to
  attach an MBID via MusicBrainz search. Confidence scoring favours
  exact title + artist matches; uncertain matches stay candidates and
  retry next cycle.

Both jobs treat per-album provider failures as soft errors (log + skip)
so a single bad MBID can't block the whole sweep. The provider Protocol
itself (Constitution P6) is injected via the arq ``ctx`` dict — the worker
entry point (:mod:`auxd_api.workers.main`) sets ``ctx["mb_provider"]`` at
startup so each job uses a long-lived client rather than rebuilding the
httpx pool for every album.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.providers.base import CatalogAlbum, CatalogProvider
from auxd_api.providers.errors import ProviderError

_LOGGER = logging.getLogger("auxd.worker.albums")

# Cap per-run row count. The same value applies to both refresh and
# reconcile jobs — keeps the worst-case wall-clock per run bounded
# (100 albums * 1s MusicBrainz rate limit = ~100s per sweep).
_BATCH_LIMIT = 100

_CACHE_TTL = timedelta(days=7)


def _get_mb_provider(ctx: dict[str, Any]) -> CatalogProvider:
    """Return the MusicBrainz provider injected by the worker startup hook.

    Raises :class:`RuntimeError` when the hook hasn't run — that's a
    misconfiguration that should surface loudly rather than fall back to
    building a one-shot client per call (which would multiply the rate-
    limit footprint by N).
    """
    provider = ctx.get("mb_provider")
    if provider is None:
        raise RuntimeError(
            "worker context missing 'mb_provider' — workers.main on_startup did not inject it"
        )
    return cast(CatalogProvider, provider)


def _merge_catalog_into_album(album: Album, catalog: CatalogAlbum) -> None:
    """Mutate ``album`` in place with the fields ``catalog`` populates.

    Centralised so both the refresh path (T064) and the reconciliation
    path (T065) apply the exact same merge semantics — keeps a future
    "what does refresh actually overwrite?" question single-source-of-
    truth.
    """
    album.title = catalog.title or album.title
    if catalog.artist_name:
        album.artist_credit = catalog.artist_name
    if catalog.release_year is not None:
        album.release_year = catalog.release_year
    if catalog.cover_art_url:
        album.cover_art_url = catalog.cover_art_url
    album.cache_expires_at = datetime.now(UTC) + _CACHE_TTL
    album.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# T064 — daily cache refresh
# ---------------------------------------------------------------------------


async def refresh_stale_album_metadata(ctx: dict[str, Any]) -> int:
    """Refresh up to 100 Albums whose ``cache_expires_at`` has elapsed.

    Only MBID-bearing rows are eligible — Discogs-only rows are handled
    by the reconciliation job (T065) instead. Returns the count of rows
    successfully refreshed; per-album failures log and skip without
    affecting the count of healthy refreshes.
    """
    provider = _get_mb_provider(ctx)
    now = datetime.now(UTC)
    stale = (
        await Album.find({"cache_expires_at": {"$lt": now}, "mbid": {"$ne": None}})
        .limit(_BATCH_LIMIT)
        .to_list()
    )
    refreshed = 0
    for album in stale:
        if album.mbid is None:  # defensive — the find() already filtered this
            continue
        try:
            fetched = await provider.get_album_by_mbid(album.mbid)
        except ProviderError as exc:
            _LOGGER.warning(
                "worker.album_refresh.provider_error",
                extra={
                    "event": "worker.album_refresh.provider_error",
                    "album_id": album.id,
                    "mbid": album.mbid,
                    "error": str(exc),
                },
            )
            continue
        if fetched is None:
            # MBID disappeared upstream — log + push the TTL out so we
            # don't re-query the same dead id every minute, but don't
            # delete the row (it's still referenced by diary entries).
            album.cache_expires_at = now + _CACHE_TTL
            await album.save()
            _LOGGER.info(
                "worker.album_refresh.upstream_missing",
                extra={
                    "event": "worker.album_refresh.upstream_missing",
                    "album_id": album.id,
                    "mbid": album.mbid,
                },
            )
            continue
        _merge_catalog_into_album(album, fetched)
        await album.save()
        refreshed += 1
    _LOGGER.info(
        "worker.album_refresh.completed",
        extra={
            "event": "worker.album_refresh.completed",
            "refreshed": refreshed,
            "scanned": len(stale),
        },
    )
    return refreshed


# ---------------------------------------------------------------------------
# T065 — weekly MBID reconciliation
# ---------------------------------------------------------------------------


def _match_score(candidate: Album, hit: CatalogAlbum) -> float:
    """Return a 0..1 confidence that ``hit`` represents the same album as ``candidate``.

    Tiny heuristic — title equality is worth 0.6, artist equality 0.4.
    Case-insensitive comparison, stripped whitespace. Anything below
    ``0.8`` means "not confident enough" and the candidate stays put.
    """
    title_match = (
        candidate.title.strip().lower() == hit.title.strip().lower()
        if hit.title and candidate.title
        else False
    )
    artist_match = (
        candidate.artist_credit.strip().lower() == hit.artist_name.strip().lower()
        if hit.artist_name and candidate.artist_credit
        else False
    )
    return (0.6 if title_match else 0.0) + (0.4 if artist_match else 0.0)


_RECONCILIATION_THRESHOLD = 0.8
"""Minimum confidence for an automatic MBID assignment."""


async def reconcile_candidate_albums(ctx: dict[str, Any]) -> int:
    """Attempt MBID reconciliation for up to 100 ``candidate=True`` albums.

    For each candidate row we search MusicBrainz for ``artist title`` and
    pick the best match by :func:`_match_score`. Hits with confidence at
    or above :data:`_RECONCILIATION_THRESHOLD` are promoted into canonical
    records (MBID attached, source flipped to ``MUSICBRAINZ``,
    ``candidate=False``). Below-threshold matches keep the row as a
    candidate so a later sweep can retry.

    Returns the count of rows successfully reconciled.
    """
    provider = _get_mb_provider(ctx)
    candidates = await Album.find({"candidate": True}).limit(_BATCH_LIMIT).to_list()
    reconciled = 0
    for album in candidates:
        query = f"{album.artist_credit} {album.title}".strip()
        if not query:
            continue
        try:
            hits = await provider.search_albums(query, limit=5)
        except ProviderError as exc:
            _LOGGER.warning(
                "worker.album_reconcile.provider_error",
                extra={
                    "event": "worker.album_reconcile.provider_error",
                    "album_id": album.id,
                    "error": str(exc),
                },
            )
            continue
        if not hits:
            continue
        best = max(hits, key=lambda hit: _match_score(album, hit))
        score = _match_score(album, best)
        if score < _RECONCILIATION_THRESHOLD or best.mbid is None:
            continue
        album.mbid = best.mbid
        album.source = AlbumSource.MUSICBRAINZ
        album.candidate = False
        if best.cover_art_url:
            album.cover_art_url = best.cover_art_url
        album.cache_expires_at = datetime.now(UTC) + _CACHE_TTL
        album.updated_at = datetime.now(UTC)
        await album.save()
        reconciled += 1
        _LOGGER.info(
            "worker.album_reconcile.success",
            extra={
                "event": "worker.album_reconcile.success",
                "album_id": album.id,
                "mbid": best.mbid,
                "confidence": score,
            },
        )
    _LOGGER.info(
        "worker.album_reconcile.completed",
        extra={
            "event": "worker.album_reconcile.completed",
            "reconciled": reconciled,
            "scanned": len(candidates),
        },
    )
    return reconciled


__all__ = [
    "reconcile_candidate_albums",
    "refresh_stale_album_metadata",
]
