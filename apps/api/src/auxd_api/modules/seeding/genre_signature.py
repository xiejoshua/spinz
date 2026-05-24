"""Per-user genre signature computation (T163).

Produces a normalized weight map ``{genre: weight}`` for a user based on
their diary entries joined to album genres. The weight map is the input
to:

* :func:`auxd_api.modules.seeding.service.score_critics_by_genre_signature`
  — onboarding card ordering & Discover suggestions.
* :func:`auxd_api.modules.seeding.mutual_taste.score_candidates` — the
  4-factor mutual-taste scoring used by the suggestions worker.

Algorithm:

1. Load up to ``_MAX_DIARY_ENTRIES`` (500) most-recent non-deleted diary
   entries for the user.
2. Batch-load referenced album rows; skip entries whose album has no
   genres (or whose album row is missing — defensive: the join could be
   stale).
3. For each (entry, album) pair compute:

   * baseline ``weight = 1.0``
   * rating boost: ``+ max(0, (rating - 3.0)) * 0.5`` when rating
     is set. A 5★ entry contributes 2.0, a 1★ entry stays at 1.0
     (we don't penalise low ratings — the user still consumed the
     genre).
   * Distribute the entry's weight evenly across the album's genres.

4. Normalise so the dominant genre = 1.0. Empty input returns ``{}``.

Cache: results are cached in Redis for 24 hours under
``genre_signature:{user_id}``. The cache is fail-open (Redis down →
recompute), and a cache miss writes the result back without blocking
the caller on the network round-trip.

The compute is read-only and idempotent so a race between two callers
just produces the same value twice; the cache write is the only
side-effect.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.redis_client import cache_get, cache_set

_LOGGER = logging.getLogger("auxd.seeding.genre_signature")

# Cap on diary rows considered. Power users with 10k+ entries don't need
# to load everything — the recent slice dominates the signature anyway
# and the cap keeps the compute bounded.
_MAX_DIARY_ENTRIES: Final[int] = 500

# 24-hour TTL: the signature only drifts as the user logs more albums,
# and a one-day staleness window is well within tolerance for onboarding /
# suggestions ranking.
_CACHE_TTL_SECONDS: Final[int] = 60 * 60 * 24

_CACHE_KEY_PREFIX: Final[str] = "genre_signature:"


__all__ = ["compute_genre_signature"]


def _compute_rating_weight(rating: float | None) -> float:
    """Return the per-entry weight contribution (baseline 1.0 + rating boost)."""
    if rating is None:
        return 1.0
    return 1.0 + max(0.0, (rating - 3.0)) * 0.5


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    """Divide every weight by max(weights) so the dominant genre = 1.0."""
    if not raw:
        return {}
    peak = max(raw.values())
    if peak <= 0.0:
        return {}
    return {genre: weight / peak for genre, weight in raw.items()}


def _cache_key(user_id: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{user_id}"


async def _load_cached(user_id: str) -> dict[str, float] | None:
    """Return a cached signature, or ``None`` on miss / parse failure."""
    raw = await cache_get(_cache_key(user_id))
    if raw is None:
        return None
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        # Corrupted entry — drop through to recompute.
        return None
    if not isinstance(decoded, dict):
        return None
    out: dict[str, float] = {}
    for key, value in decoded.items():
        if isinstance(key, str) and isinstance(value, int | float):
            out[key] = float(value)
    return out


async def _write_cache(user_id: str, signature: dict[str, float]) -> None:
    """Best-effort cache write. Failures are alerted by the redis wrapper."""
    try:
        encoded = json.dumps(signature)
    except (TypeError, ValueError):  # pragma: no cover — defensive
        return
    await cache_set(_cache_key(user_id), encoded, ex_seconds=_CACHE_TTL_SECONDS)


async def _compute_uncached(user_id: str) -> dict[str, float]:
    """Pull diary + albums and run the weighted-aggregation pass."""
    entries = (
        await DiaryEntry.find({"user_id": user_id, "deleted_at": None})
        .sort("-logged_at")
        .limit(_MAX_DIARY_ENTRIES)
        .to_list()
    )
    if not entries:
        return {}

    album_ids = sorted({entry.album_id for entry in entries})
    albums = await Album.find({"_id": {"$in": album_ids}}).to_list()
    album_by_id: dict[str, Album] = {album.id: album for album in albums}

    totals: dict[str, float] = {}
    for entry in entries:
        album = album_by_id.get(entry.album_id)
        if album is None or not album.genres:
            continue
        weight = _compute_rating_weight(entry.rating)
        per_genre = weight / len(album.genres)
        for genre in album.genres:
            key = genre.strip().lower()
            if not key:
                continue
            totals[key] = totals.get(key, 0.0) + per_genre

    return _normalize(totals)


async def compute_genre_signature(user_id: str) -> dict[str, float]:
    """Return the per-user normalized genre weight map.

    Empty dict when the user has no diary entries or no entries reference
    albums with known genres. Otherwise weights are in ``(0, 1]`` with the
    dominant genre at exactly ``1.0``.

    Caches the result for 24 hours under ``genre_signature:{user_id}``;
    Redis failures are fail-open via the cache wrappers so the function
    always returns a valid signature on a happy DB path.
    """
    cached = await _load_cached(user_id)
    if cached is not None:
        return cached
    signature = await _compute_uncached(user_id)
    await _write_cache(user_id, signature)
    return signature
