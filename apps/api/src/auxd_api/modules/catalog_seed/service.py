"""Catalog-seed ingest service.

Walks a list of ``(artist, title)`` tuples through the existing
3-tier search pipeline (Atlas → Discogs masters → MusicBrainz). Each
hit triggers :func:`auxd_api.modules.albums.identity.resolve_identity`
as a side-effect — that's where materialisation into the local
``albums`` collection lives, including the dedupe-by-MBID + reuse of
already-cached rows.

Failure modes are intentionally per-entry: a malformed name, a
provider 5xx, or a "not in either catalog" miss bumps
``entries_failed`` and the loop continues. The seed pipeline is a
batch backfill — one rough entry shouldn't poison the entire run.

Rate awareness
==============
MusicBrainz enforces 1 req/sec; Discogs allows ~60/min authenticated.
``ingest_seed_list`` doesn't add a sleep of its own — the providers'
own clients are responsible. We do, however, persist the
:class:`SeedRun` row every ``CHECKPOINT_INTERVAL`` entries so a
long-running pass can be resumed / inspected mid-flight.
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auxd_api.modules.catalog_seed.models import SeedRun, SeedRunStatus
from auxd_api.modules.search.service import search_albums
from auxd_api.providers.base import CatalogProvider

_LOGGER = logging.getLogger("auxd.catalog_seed")

# Persist the SeedRun document every N processed entries so progress
# is visible during a long pass. Smaller = more writes (cheap); larger
# = less chatty. 25 strikes a reasonable balance for ~hour-long runs.
CHECKPOINT_INTERVAL = 25

# Cap the retained error log so a misbehaving source can't bloat the
# SeedRun doc with thousands of identical error strings.
_MAX_ERROR_LOG = 50

# Sleep between entries so we stay under the Discogs unauthenticated
# rate limit (25 req/min ≈ one call per 2.4s). With an API token set
# the limit lifts to 60/min and the floor here just becomes a polite
# pacing floor. Safe to lower if DISCOGS_API_TOKEN is configured —
# but defending against the unauth case is the conservative default.
_ENTRY_PACING_S = 2.5

# Match thresholds for verifying a search hit against the requested
# entry. The seed pipeline used to count "any hit" as success, which
# meant Discogs's fuzzy results would materialise wrong albums
# (querying "Henry Mancini Peter Gunn" returned Blues Brothers as the
# top hit). Requiring both artist + title to reach a similarity floor
# rejects those false positives.
_MIN_ARTIST_SIMILARITY = 0.55
_MIN_TITLE_SIMILARITY = 0.55

_NON_WORD_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_STOPWORDS = frozenset({"the", "a", "an", "of", "and", "&", "with", "on", "in", "for", "to"})


@dataclass(frozen=True, slots=True)
class AlbumSeedEntry:
    """One album to attempt resolution against the provider stack.

    ``artist`` + ``title`` are concatenated into a single query string
    passed through :func:`search_albums`. ``year_hint`` is currently
    informational only — the existing 3-tier merge doesn't accept a
    year filter directly. ``source_rank`` records the entry's position
    in the originating list for later dashboards.
    """

    artist: str
    title: str
    year_hint: int | None = None
    source_rank: int | None = None


async def ingest_seed_list(
    *,
    source_name: str,
    entries: Iterable[AlbumSeedEntry],
    mb_provider: CatalogProvider,
    discogs_provider: CatalogProvider,
    progress: AsyncIterator[None] | None = None,
) -> SeedRun:
    """Resolve every entry through the existing search pipeline.

    Returns the persisted :class:`SeedRun` row. The function is
    awaitable but doesn't yield to its own caller between entries
    (that's the providers' rate-limit clients' job).

    ``progress`` is an optional sink for live updates the CLI runner
    pipes to its progress bar; passing ``None`` is fine for headless
    cron / worker invocations.
    """
    run = SeedRun(source_name=source_name, status=SeedRunStatus.RUNNING)
    await run.insert()
    _LOGGER.info(
        "catalog_seed.run_started",
        extra={
            "event": "catalog_seed.run_started",
            "source": source_name,
            "run_id": run.id,
        },
    )

    try:
        for index, entry in enumerate(entries):
            run.entries_attempted += 1
            if not entry.artist or not entry.title:
                run.entries_failed += 1
                _append_error(run, "empty entry")
                continue

            # Pacing — except on the very first call, sleep before each
            # next-entry search so we don't burst past Discogs's
            # unauthenticated rate limit.
            if index > 0:
                await asyncio.sleep(_ENTRY_PACING_S)

            # Title-only query: the merged 3-tier search treats this
            # as a precise lookup. Combined "Artist Title" queries
            # break MusicBrainz's Lucene parser (returns 0 hits) and
            # cause Discogs's fuzzy ranker to surface unrelated
            # popular masters as top results.
            query = entry.title

            try:
                hits = await search_albums(
                    query=query,
                    limit=10,
                    mb_provider=mb_provider,
                    discogs_provider=discogs_provider,
                )
            except Exception as exc:  # noqa: BLE001 — defensive batch loop
                run.entries_failed += 1
                _append_error(run, f"{query!r}: search raised {exc!r}")
                _LOGGER.warning(
                    "catalog_seed.entry_failed",
                    extra={
                        "event": "catalog_seed.entry_failed",
                        "source": source_name,
                        "query": query,
                        "error": str(exc),
                    },
                )
                continue

            matched = _pick_matching_hit(entry, hits)
            if matched is not None:
                run.entries_succeeded += 1
            else:
                run.entries_failed += 1
                _append_error(
                    run,
                    f"{entry.artist!r} / {entry.title!r}: {len(hits)} candidate(s), none matched",
                )

            # Periodic checkpoint — write progress so an operator
            # tailing the SeedRun document can watch ingest health
            # mid-pass and so a worker crash leaves a useful diagnostic
            # snapshot rather than zero state.
            if run.entries_attempted % CHECKPOINT_INTERVAL == 0:
                await run.save()
                _LOGGER.info(
                    "catalog_seed.checkpoint",
                    extra={
                        "event": "catalog_seed.checkpoint",
                        "source": source_name,
                        "attempted": run.entries_attempted,
                        "succeeded": run.entries_succeeded,
                        "failed": run.entries_failed,
                    },
                )

        run.status = SeedRunStatus.COMPLETED
    except Exception as exc:  # noqa: BLE001 — final guard
        run.status = SeedRunStatus.FAILED
        _append_error(run, f"fatal: {exc!r}")
        _LOGGER.exception(
            "catalog_seed.run_failed",
            extra={
                "event": "catalog_seed.run_failed",
                "source": source_name,
                "run_id": run.id,
            },
        )
    finally:
        run.finished_at = datetime.now(UTC)
        await run.save()

    _LOGGER.info(
        "catalog_seed.run_finished",
        extra={
            "event": "catalog_seed.run_finished",
            "source": source_name,
            "run_id": run.id,
            "status": run.status.value,
            "succeeded": run.entries_succeeded,
            "failed": run.entries_failed,
            "attempted": run.entries_attempted,
        },
    )
    return run


def _normalize(value: str) -> str:
    """Lowercase + strip punctuation + drop common stopwords + collapse whitespace.

    Used by :func:`_pick_matching_hit` so cosmetic differences ("The
    Beatles" vs "Beatles", "Sgt. Pepper's" vs "Sgt Peppers") don't
    drag the similarity score under the match threshold.
    """
    cleaned = _NON_WORD_RE.sub(" ", value.lower())
    tokens = [tok for tok in _WHITESPACE_RE.split(cleaned) if tok and tok not in _STOPWORDS]
    return " ".join(tokens)


def _similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio after normalising both inputs."""
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _pick_matching_hit(entry: AlbumSeedEntry, hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first hit whose artist + title both clear the
    similarity thresholds, else ``None``.

    The seed pipeline previously counted "any hit" as success, which
    let Discogs's fuzzy ranker materialise unrelated albums into the
    catalog for queries like "Henry Mancini Peter Gunn" (top Discogs
    result: Blues Brothers Soundtrack). Verifying both fields against
    the requested entry rejects those false positives — and crucially,
    materialisation already happened as a side-effect of the search,
    so a non-match doesn't waste a successful provider fetch (the
    wrong-album row is still in the catalog; the seed just doesn't
    take credit for it).
    """
    for hit in hits:
        hit_artist = hit.get("artist_name") or ""
        hit_title = hit.get("title") or ""
        if not hit_artist or not hit_title:
            continue
        artist_score = _similarity(entry.artist, hit_artist)
        title_score = _similarity(entry.title, hit_title)
        if artist_score >= _MIN_ARTIST_SIMILARITY and title_score >= _MIN_TITLE_SIMILARITY:
            return hit
    return None


def _append_error(run: SeedRun, message: str) -> None:
    """Append to the run's error log with a hard cap.

    Caps at :data:`_MAX_ERROR_LOG` so a pathological source list (e.g.
    "every entry fails resolution") doesn't balloon the document past
    Mongo's 16MB limit. Truncates from the *end* — earliest errors are
    usually the most diagnostic for "why did this start going wrong".
    """
    if len(run.error_log) >= _MAX_ERROR_LOG:
        return
    run.error_log.append(message)


__all__ = ["AlbumSeedEntry", "ingest_seed_list"]
