"""One-shot ETL: MusicBrainz JSON dump → Turso mirror.

Usage::

    cd apps/api
    uv run --extra seed-scripts python scripts/mb_mirror_ingest.py
    uv run --extra seed-scripts python scripts/mb_mirror_ingest.py --dump-date 20260523-001002
    uv run --extra seed-scripts python scripts/mb_mirror_ingest.py --limit 50000  # smoke run

Pulls the latest release-group JSON dump from
``data.metabrainz.org``, streams it through xz + tar decompression,
filters to "release-groups with at least a known year" (and
optionally with cover art / above a tag-vote threshold), maps each
to a :class:`MirrorRow`, and batch-upserts into Turso.

Streaming + filtering
=====================
The release-group dump is ~1.1GB compressed / ~10GB raw JSONL. We
never materialise the full uncompressed stream — pipes through
xz → tar → JSONL, line by line. Each JSON object is one
release-group; we map + filter + drop the parsed object before
moving on.

Idempotency
===========
The upsert path uses ``ON CONFLICT(mbid) DO UPDATE`` so re-running
the ingest is safe — already-mirrored rows update in place if MB
has issued metadata corrections. Use ``--limit`` to truncate a
test run early; the resulting partial mirror is consistent (every
inserted row is fully populated), just narrower.

Cover-art note
==============
MB doesn't carry cover art URLs inside the release-group JSON
dump — those live at ``coverartarchive.org``. The mirror's
``cover_art_url`` field is populated lazily for now; the search
service can still surface ``/api/cover/{mbid}`` from the mbid
alone, falling back to the gradient placeholder when CAA has
no art.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import lzma
import re
import sys
import tarfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

try:
    import truststore  # type: ignore[import-not-found]

    truststore.inject_into_ssl()
except ImportError:
    pass

import httpx  # noqa: E402

from auxd_api.modules.mb_mirror.client import TursoClient  # noqa: E402
from auxd_api.modules.mb_mirror.service import AlbumMirrorService  # noqa: E402
from auxd_api.modules.mb_mirror.types import MirrorRow  # noqa: E402
from auxd_api.settings import get_settings  # noqa: E402

_LOGGER = logging.getLogger("auxd.mb_mirror.ingest")

# MB publishes dumps under date-stamped directories. We default to
# "latest" by scraping the listing; the operator can pin a specific
# date via ``--dump-date`` for reproducibility.
_DUMP_INDEX_URL = "https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/"
_DUMP_DATE_RE = re.compile(r'href="(\d{8}-\d{6})/"')
_DUMP_FILE_NAME = "release-group.tar.xz"

# Batch size for Turso pipeline upserts. 500 rows is the sweet spot:
# big enough to amortise the HTTP round-trip across many writes,
# small enough that one batch stays under the request body cap.
_BATCH_SIZE = 500

# Emit a progress line every N records seen. Tighter than the
# default 50k because the visibility matters more than log volume
# on a multi-hour operation — at 5k/iter the log fires every
# ~10-30s on a healthy bulk-load path, every ~3-5min on a slow one.
_PROGRESS_INTERVAL = 5000

# How many batches we allow in-flight at once. The serial path
# (concurrency=1) hit ~50 rows/sec on Turso free tier, well below
# any documented per-row throughput limit — the bottleneck was
# round-trip serialization, not write rate. Firing batches in
# parallel via asyncio.Semaphore lets multiple INSERT pipelines
# overlap their network + commit phases.
#
# 4 is conservative; values up to ~8 work well empirically. Higher
# values risk hitting libSQL's per-connection request queue limit
# or saturating the free tier's concurrent-connection budget.
_DEFAULT_CONCURRENCY = 4

# Minimum tag-vote threshold for surfacing a tag in ``genres``. MB
# user-submitted tags can be very noisy; ≥2 votes filters out the
# truly random one-offs without dropping legitimate niche genres.
_MIN_TAG_VOTES = 2

# Cap the genre CSV length so a release-group with 100+ tags doesn't
# bloat one row. 200 chars is plenty for ~10-15 tags worth of signal.
_GENRES_CHAR_CAP = 200


def _latest_dump_date(client: httpx.Client) -> str:
    """Scrape the listing page and return the most recent dump dir."""
    resp = client.get(_DUMP_INDEX_URL, timeout=15.0)
    resp.raise_for_status()
    dates = _DUMP_DATE_RE.findall(resp.text)
    if not dates:
        raise RuntimeError(
            f"no dump dates found at {_DUMP_INDEX_URL} — has MB's URL layout changed?"
        )
    return sorted(dates)[-1]


def _dump_url(dump_date: str) -> str:
    return f"{_DUMP_INDEX_URL}{dump_date}/{_DUMP_FILE_NAME}"


# Default location for the cached dump on disk. ``/tmp`` survives a
# single run but vanishes on reboot; that's fine because the dump is
# downloadable in ~5 min and we don't want to wedge a long-lived
# resource on the user's machine. Override via ``--dump-file PATH``
# to keep it somewhere durable for repeat re-runs.
_DEFAULT_LOCAL_DUMP = Path("/tmp/auxd_mb_release_group.tar.xz")


def _download_dump(client: httpx.Client, url: str, target: Path) -> Path:
    """Stream-download the MB dump to ``target``, validating size.

    Earlier revision held an HTTP stream open for the entire hour-long
    parse + ingest, which the user hit when ``data.metabrainz.org``
    (or an intermediate proxy) reset the connection mid-flight. Now
    the network phase is decoupled: we download to disk first (~5 min
    on a typical connection), then the parse phase reads from the
    local file with no network exposure.

    Idempotent: if ``target`` already exists and matches the server's
    Content-Length, we skip the download and reuse the file. Use
    ``--force-download`` to override.

    Validates downloaded size against Content-Length and raises on
    mismatch — a truncated file would crash the lzma/tar decoder
    halfway through ingest, much worse to discover late.
    """
    head_response = client.head(url, timeout=30.0)
    head_response.raise_for_status()
    expected_size_header = head_response.headers.get("content-length")
    if not expected_size_header:
        raise RuntimeError(
            f"server returned no Content-Length for {url} — refusing to "
            "download without a size to validate against"
        )
    expected_size = int(expected_size_header)

    if target.exists() and target.stat().st_size == expected_size:
        _LOGGER.info(
            "mb_mirror.ingest.dump_local_reused",
            extra={
                "event": "mb_mirror.ingest.dump_local_reused",
                "path": str(target),
                "size": expected_size,
            },
        )
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    _LOGGER.info(
        "mb_mirror.ingest.download_started",
        extra={
            "event": "mb_mirror.ingest.download_started",
            "url": url,
            "expected_size": expected_size,
            "target": str(target),
        },
    )
    bytes_received = 0
    with tmp.open("wb") as fh, client.stream("GET", url, timeout=60.0) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=1 << 20):
            fh.write(chunk)
            bytes_received += len(chunk)
    if bytes_received != expected_size:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"download truncated: got {bytes_received} bytes, "
            f"expected {expected_size}. Try re-running; transient drops "
            "from data.metabrainz.org happen occasionally."
        )
    tmp.replace(target)
    _LOGGER.info(
        "mb_mirror.ingest.download_complete",
        extra={
            "event": "mb_mirror.ingest.download_complete",
            "bytes": bytes_received,
            "target": str(target),
        },
    )
    return target


def _stream_release_groups(dump_path: Path) -> Iterator[dict[str, Any]]:
    """Stream-yield one parsed release-group JSON object at a time.

    The pipeline is local-file → xz-decompress → tar-extract → JSONL
    parse. We never materialise the full uncompressed dump.

    Notes on the tar member iteration: MB's release-group dump is a
    tarball containing a small directory tree (release-group +
    metadata files); the actual JSONL records live in one file we
    locate by name suffix. The directory file (``COPYING``,
    ``mbdump/release-group``, etc.) is skipped silently.
    """
    with (
        dump_path.open("rb") as fp,
        lzma.open(fp, "rb") as xz_stream,
        tarfile.open(fileobj=xz_stream, mode="r|") as tar,
    ):
        for member in tar:
            if not member.isfile():
                continue
            if not member.name.endswith("release-group"):
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    _LOGGER.warning(
                        "mb_mirror.ingest.bad_json",
                        extra={
                            "event": "mb_mirror.ingest.bad_json",
                            "preview": line[:80].decode("utf-8", "replace"),
                        },
                    )
                    continue


def _map_release_group(rg: dict[str, Any]) -> MirrorRow | None:
    """Filter + map one MB release-group JSON object into a mirror row.

    Filters:
    * Must carry a ``first-release-date`` with a parseable year.
    * Must carry at least an ``artist-credit`` and a ``title``.

    Anything that fails the filter returns ``None`` and the caller
    drops it. Tag-vote threshold + char cap are applied here so the
    ETL never persists noise downstream readers would have to filter
    again.
    """
    mbid = rg.get("id")
    title = (rg.get("title") or "").strip()
    if not mbid or not title:
        return None

    year = _extract_year(rg.get("first-release-date"))
    if year is None:
        return None

    artist_credit = _artist_credit_string(rg.get("artist-credit"))
    if not artist_credit:
        return None

    primary_type = rg.get("primary-type")
    genres_csv = _tags_to_csv(rg.get("tags") or [])

    return MirrorRow(
        mbid=mbid,
        title=title,
        artist_credit=artist_credit,
        release_year=year,
        primary_type=primary_type,
        genres=genres_csv,
        cover_art_url=None,  # populated lazily via the cover proxy at read time
    )


def _extract_year(date_str: Any) -> int | None:
    """Pull a 4-digit year off ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``."""
    if not isinstance(date_str, str) or not date_str:
        return None
    head = date_str.split("-", 1)[0]
    if not head.isdigit():
        return None
    year = int(head)
    if 1900 <= year <= 2100:
        return year
    return None


def _artist_credit_string(credit: Any) -> str:
    """Flatten MB's artist-credit list into a joined string.

    MB structures this as ``[{"name": "Lennon", "joinphrase": " & "},
    {"name": "McCartney"}]`` so collaboration credits read naturally.
    We preserve the joinphrases so "Stan Getz / João Gilberto" stays
    intact end-to-end.
    """
    if not isinstance(credit, list):
        return ""
    parts: list[str] = []
    for entry in credit:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            artist = entry.get("artist") or {}
            name = (artist.get("name") or "").strip()
        if not name:
            continue
        parts.append(name)
        join = entry.get("joinphrase")
        if join:
            parts.append(join)
    return "".join(parts).strip()


def _tags_to_csv(tags: list[Any]) -> str:
    """Project MB tags into a comma-joined string, capped + filtered."""
    if not tags:
        return ""
    accepted: list[str] = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if (tag.get("count") or 0) < _MIN_TAG_VOTES:
            continue
        name = (tag.get("name") or "").strip().lower()
        if not name:
            continue
        accepted.append(name)
    if not accepted:
        return ""
    csv = ",".join(accepted)
    if len(csv) > _GENRES_CHAR_CAP:
        # Re-truncate on whole tags rather than mid-string.
        truncated: list[str] = []
        running = 0
        for tag in accepted:
            if running + len(tag) + 1 > _GENRES_CHAR_CAP:
                break
            truncated.append(tag)
            running += len(tag) + 1
        csv = ",".join(truncated)
    return csv


async def _run(
    *,
    dump_date: str | None,
    limit: int | None,
    dump_file: Path | None,
    force_download: bool,
    keep_dump: bool,
    concurrency: int,
) -> int:
    settings = get_settings()
    client = TursoClient.from_settings(settings)
    if client is None:
        sys.stderr.write(
            "TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not set — "
            "set them in apps/api/.env to enable the mirror.\n"
        )
        return 2

    # Phase 1 — resolve the dump URL + download (or reuse) the local
    # file. Done OUTSIDE the Turso ``async with`` so the network and
    # database lifecycles don't entangle; if the download fails, no
    # half-open Turso connection lingers.
    with httpx.Client(timeout=60.0, follow_redirects=True) as http:
        if dump_file is not None:
            # User provided a pre-downloaded file — skip the download.
            local_dump = dump_file
            if not local_dump.exists():
                sys.stderr.write(f"--dump-file {local_dump} does not exist\n")
                return 2
            resolved_date = dump_date or "user-provided"
            _LOGGER.info(
                "mb_mirror.ingest.using_user_dump",
                extra={
                    "event": "mb_mirror.ingest.using_user_dump",
                    "path": str(local_dump),
                },
            )
        else:
            resolved_date = dump_date or _latest_dump_date(http)
            url = _dump_url(resolved_date)
            _LOGGER.info(
                "mb_mirror.ingest.dump_resolved",
                extra={
                    "event": "mb_mirror.ingest.dump_resolved",
                    "dump_date": resolved_date,
                    "url": url,
                },
            )
            target = _DEFAULT_LOCAL_DUMP
            if force_download and target.exists():
                target.unlink()
            local_dump = _download_dump(http, url, target)

    # Phase 2 — open Turso + stream the local dump through the
    # filter/upsert pipeline. No more network exposure beyond Turso's
    # HTTP API, and that's individual short-lived requests rather
    # than a long-lived stream.
    #
    # The flow is FTS5-deferred: drop the FTS5 surface during bulk
    # load so per-row trigger fires don't dominate write latency,
    # then rebuild FTS5 in one shot once all rows are in. This is
    # the ~14× speed-up over the naive "triggers fire on every
    # insert" path — without it, full ingest runs ~17h instead of ~45min.
    async with client as turso:
        service = AlbumMirrorService(turso)
        _LOGGER.info("mb_mirror.ingest.init_core_schema")
        await service.initialize_core_schema()

        _LOGGER.info("mb_mirror.ingest.prepare_for_bulk_load")
        await service.prepare_for_bulk_load()

        await service.record_ingest_start(dump_date=resolved_date)

        seen = 0
        kept = 0
        batches_committed = 0
        last_progress_time = time.monotonic()
        ingest_started_at = last_progress_time
        buffer: list[MirrorRow] = []
        bulk_load_succeeded = False

        # Bounded-concurrency upsert with PRODUCER-side semaphore.
        #
        # Earlier revision acquired the semaphore INSIDE the task
        # (``async with sem`` in the consumer body). That bounded
        # concurrent execution but not the size of the pending task
        # queue — ``asyncio.create_task`` returns instantly, so the
        # JSON-parsing producer raced ahead of Turso's commit rate
        # and accumulated thousands of pending tasks (the user saw
        # ``in_flight=8231`` at drain time, ~3h of backed-up work).
        #
        # Acquiring the semaphore in the producer before
        # ``create_task`` makes the producer naturally throttle
        # to the consumer's rate: ``in_flight`` stays at ≤
        # ``concurrency`` and memory + drain time stay predictable.
        sem = asyncio.Semaphore(concurrency)
        in_flight: set[asyncio.Task[None]] = set()
        commit_counter = {"value": 0}

        async def _upsert_then_release(rows: list[MirrorRow]) -> None:
            """Upsert one batch, then release the semaphore slot.

            Releases in a ``finally`` so a Turso outage that raises
            (e.g. timeout-at-floor on the split-retry) doesn't
            permanently consume a slot. The exception still bubbles
            up to cancel the rest of the run via
            ``asyncio.gather`` at drain time.
            """
            try:
                batch_start = time.monotonic()
                await service.upsert_many(rows)
                commit_counter["value"] += 1
                _LOGGER.debug(
                    "mb_mirror.ingest.batch_committed "
                    f"batch={commit_counter['value']} rows={len(rows)} "
                    f"latency_s={time.monotonic() - batch_start:.2f}"
                )
            finally:
                sem.release()

        async def _schedule_batch(rows: list[MirrorRow]) -> None:
            """Block the producer until a consumer slot frees up, then queue.

            This is the actual backpressure mechanism — the call
            awaits ``sem.acquire()``, which suspends the JSON
            streaming loop whenever ``concurrency`` batches are
            already in flight. Without this, the producer races
            ahead and the queue grows unbounded.
            """
            await sem.acquire()
            task = asyncio.create_task(_upsert_then_release(rows))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)

        try:
            for raw in _stream_release_groups(local_dump):
                seen += 1
                if seen % _PROGRESS_INTERVAL == 0:
                    now = time.monotonic()
                    interval_s = now - last_progress_time
                    total_s = now - ingest_started_at
                    batches_committed = commit_counter["value"]
                    # Embed numbers directly in the log message so
                    # the default ``%(message)s`` formatter surfaces
                    # them without needing a custom format string.
                    _LOGGER.info(
                        "mb_mirror.ingest.progress "
                        f"seen={seen} kept={kept} "
                        f"batches={batches_committed} "
                        f"in_flight={len(in_flight)} "
                        f"interval_s={interval_s:.1f} total_s={total_s:.0f}"
                    )
                    last_progress_time = now
                row = _map_release_group(raw)
                if row is None:
                    continue
                buffer.append(row)
                kept += 1
                if len(buffer) >= _BATCH_SIZE:
                    # ``await`` here is the backpressure point —
                    # blocks the streaming loop when all ``concurrency``
                    # slots are taken, resumes when one frees.
                    await _schedule_batch(buffer)
                    buffer = []  # fresh list so the scheduled task owns its copy
                if limit is not None and kept >= limit:
                    break

            if buffer:
                await _schedule_batch(buffer)
                buffer = []

            # Wait for every in-flight batch before claiming success;
            # bailing here would leave the last few hundred rows
            # un-committed and the SeedRun's row_count off by a batch
            # or two.
            if in_flight:
                _LOGGER.info(f"mb_mirror.ingest.draining in_flight={len(in_flight)}")
                await asyncio.gather(*in_flight)
            batches_committed = commit_counter["value"]
            bulk_load_succeeded = True
        finally:
            await service.record_ingest_finish(row_count=kept)
            if bulk_load_succeeded:
                # Rebuild FTS5 from albums_mirror and restore triggers.
                # Only runs on success so a mid-ingest crash leaves
                # albums_mirror partially populated but no FTS5 (so
                # the next re-run starts from a clean slate and the
                # FTS5 search path won't return stale partial state).
                _LOGGER.info("mb_mirror.ingest.finalize_after_bulk_load")
                await service.finalize_after_bulk_load()
            else:
                _LOGGER.warning(
                    "mb_mirror.ingest.bulk_load_failed_skipping_fts",
                    extra={
                        "event": "mb_mirror.ingest.bulk_load_failed_skipping_fts",
                        "rows_persisted": kept,
                    },
                )

        _LOGGER.info(
            "mb_mirror.ingest.complete",
            extra={
                "event": "mb_mirror.ingest.complete",
                "seen": seen,
                "kept": kept,
                "dump_date": resolved_date,
            },
        )
        print(f"ingest complete: seen={seen} kept={kept} dump_date={resolved_date}")

    # Phase 3 — optionally clean up the local dump. Keeping it is
    # safe (it's just a tar.xz on disk) and dramatically speeds up
    # re-runs since the next invocation skips the download.
    if not keep_dump and dump_file is None and local_dump.exists():
        try:
            local_dump.unlink()
            _LOGGER.info(
                "mb_mirror.ingest.dump_cleaned",
                extra={"event": "mb_mirror.ingest.dump_cleaned", "path": str(local_dump)},
            )
        except OSError as exc:
            _LOGGER.warning(
                "mb_mirror.ingest.cleanup_failed",
                extra={
                    "event": "mb_mirror.ingest.cleanup_failed",
                    "path": str(local_dump),
                    "error": repr(exc),
                },
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest MB release-group dump into Turso.")
    parser.add_argument(
        "--dump-date",
        default=None,
        help=(
            "Pin to a specific dump date (format ``YYYYMMDD-HHMMSS``). "
            "Defaults to the latest available."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Stop after upserting N rows. Useful for smoke runs; the "
            "partial mirror is consistent (every row fully populated)."
        ),
    )
    parser.add_argument(
        "--dump-file",
        type=Path,
        default=None,
        help=(
            "Path to a pre-downloaded tar.xz dump. Skips the download "
            "phase entirely and parses the local file. Use this to "
            "resume after a successful download + failed parse/upsert."
        ),
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help=(
            "Re-download the dump even if a matching local copy exists "
            "at the default cache path. Otherwise reused for free."
        ),
    )
    parser.add_argument(
        "--keep-dump",
        action="store_true",
        help=(
            "Don't delete the downloaded dump after a successful ingest. "
            "Useful when you might want to re-run; the next invocation "
            "will reuse the cached file (saves ~5 min)."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=_DEFAULT_CONCURRENCY,
        help=(
            f"Max in-flight upsert batches (default: {_DEFAULT_CONCURRENCY}). "
            "Higher values speed up Turso writes by overlapping HTTP "
            "round-trips, capped by libSQL's per-connection queue. "
            "Try 8 if 4 looks bottlenecked; back off to 2 on rate-limit "
            "errors."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Silence httpx + httpcore per-request INFO chatter — at
    # concurrency=4 the dump phase emits 4× the request volume and
    # the actual ``mb_mirror.ingest.progress`` lines get buried in
    # ``HTTP Request: POST .../v2/pipeline "HTTP/1.1 200 OK"`` noise.
    # We still want WARNING/ERROR from httpx so a real failure
    # surfaces; just not the success line on every batch.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return asyncio.run(
        _run(
            dump_date=args.dump_date,
            limit=args.limit,
            dump_file=args.dump_file,
            force_download=args.force_download,
            keep_dump=args.keep_dump,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
