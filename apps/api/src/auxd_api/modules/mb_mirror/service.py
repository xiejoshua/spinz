"""High-level read + write surface for the MB mirror.

Splits cleanly into two halves:

* **Read** — :meth:`AlbumMirrorService.find_by_mbid` and
  :meth:`search_text` are the query entry points called from the
  hot search-flow tier-0 path. They're built to be fast (single
  Turso round trip, no Python-side filtering) and silently
  graceful — any error or "mirror disabled" state returns ``None``
  / ``[]`` so the caller falls through to Atlas / Discogs / MB-API
  without exception handling.
* **Write** — :meth:`upsert_many` batches the ETL's row writes
  through a single Turso pipeline request. Used by
  :mod:`scripts.mb_mirror_ingest` and the monthly arq cron.

Anything router-layer or worker-layer reaches for this module
rather than touching :class:`auxd_api.modules.mb_mirror.client.TursoClient`
directly — keeps the SQL strings + parameter binding in one
place and makes future schema changes a one-file diff.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx

from auxd_api.modules.mb_mirror.client import (
    TursoClient,
    TursoExecutionError,
)
from auxd_api.modules.mb_mirror.schema import (
    SCHEMA_VERSION,
    all_ddl,
    core_ddl,
    drop_fts_statements,
    fts_ddl,
    rebuild_fts_statement,
)
from auxd_api.modules.mb_mirror.types import MirrorRow

_LOGGER = logging.getLogger("auxd.mb_mirror.service")

# Default text-search page size. The mirror's FTS5 index returns
# results in relevance order; 10 hits is enough for the dropdown
# autocomplete and the advanced-search initial page (which still
# falls back to the merged provider pipeline for deeper paging).
_DEFAULT_TEXT_SEARCH_LIMIT = 10

# Smallest sub-batch we'll attempt before giving up on a timeout. If
# 25-row batches still time out we treat that as a genuine outage
# rather than retry-amplifying the load.
_MIN_RETRY_BATCH = 25

# Timeout used for the FTS5 rebuild call. The statement scans every
# row in albums_mirror, tokenizes both indexed columns, and
# populates the inverted index — on a 1.5M-row mirror this takes
# ~3-5min on Turso free tier. 10min ceiling absorbs slower instances
# without retry amplification.
_FTS_REBUILD_TIMEOUT_S = 600.0

# FTS5 reserves these chars in its query grammar; users typing them
# into the search box mean them literally, so we strip rather than
# attempt to escape (whitespace replacement preserves token boundaries).
_FTS_RESERVED_RE = re.compile(r'[*"():+\-^]')

# Hard ceiling on the result count we return to the client (FR-008).
# A COUNT(*) over a wide MATCH can exceed five digits on the 1.3M-row
# mirror; the UI's "Showing X of Y+" string only needs a sane upper
# bound, not a precise number past the point of utility.
_TOTAL_DISPLAY_CAP = 10_000


class AlbumMirrorService:
    """Lookup + bulk-write surface for the MB mirror table.

    Construct from a :class:`TursoClient` obtained via
    :meth:`TursoClient.from_settings`. When ``client`` is ``None``
    (mirror disabled in this environment) every read returns the
    "empty" sentinel and every write is a no-op — callers can wire
    this service unconditionally without per-environment branching.
    """

    def __init__(self, client: TursoClient | None) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        """True when the mirror is configured + reachable.

        Cheap predicate the search service uses to decide whether
        to bother making the tier-0 round trip.
        """
        return self._client is not None

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def initialize_schema(self) -> None:
        """Apply the full DDL (core + FTS5) idempotently.

        Used by single-row writers (the refresh-cron worker) where
        each insert needs FTS5 in sync immediately and the per-row
        trigger overhead is negligible. Bulk-load callers should
        use :meth:`initialize_core_schema` +
        :meth:`prepare_for_bulk_load` + :meth:`finalize_after_bulk_load`
        instead — ~14× faster ingest.

        Safe to call on every process boot — the ``IF NOT EXISTS``
        guards make this a no-op on an already-bootstrapped database.
        """
        if self._client is None:
            raise RuntimeError("initialize_schema called on a disabled mirror")
        statements: list[tuple[str, list[Any]]] = [(ddl, []) for ddl in all_ddl()]
        statements.append(self._meta_upsert_statement())
        await self._client.execute_batch(statements)

    async def initialize_core_schema(self) -> None:
        """Apply only the canonical table + indexes (no FTS5 work).

        Bulk-load preamble: pairs with :meth:`prepare_for_bulk_load`
        (drops any existing FTS5 surface) and
        :meth:`finalize_after_bulk_load` (rebuilds FTS5 in one shot
        once all rows are loaded).
        """
        if self._client is None:
            raise RuntimeError("initialize_core_schema called on a disabled mirror")
        statements: list[tuple[str, list[Any]]] = [(ddl, []) for ddl in core_ddl()]
        statements.append(self._meta_upsert_statement())
        await self._client.execute_batch(statements)

    async def prepare_for_bulk_load(self) -> None:
        """Drop FTS5 sync triggers + the FTS5 virtual table.

        Each row insert during bulk load would otherwise fire the
        FTS5 sync trigger and pay the per-token index-update cost.
        Stripping FTS5 entirely for the load lets every insert hit
        the canonical table directly; the FTS5 surface is rebuilt
        once at the end via :meth:`finalize_after_bulk_load`.

        Idempotent (``IF EXISTS``-guarded) so safe to call against
        a mirror that's never been bulk-loaded or one that's been
        through several prior loads.
        """
        if self._client is None:
            raise RuntimeError("prepare_for_bulk_load called on a disabled mirror")
        statements: list[tuple[str, list[Any]]] = [(sql, []) for sql in drop_fts_statements()]
        await self._client.execute_batch(statements)
        _LOGGER.info(
            "mb_mirror.bulk_load.fts_dropped",
            extra={"event": "mb_mirror.bulk_load.fts_dropped"},
        )

    async def finalize_after_bulk_load(self) -> None:
        """Recreate FTS5 + repopulate from albums_mirror + restore triggers.

        Three-phase wrap-up:

        1. Recreate the FTS5 virtual table (without triggers yet —
           those would fire on the rebuild INSERT below).
        2. Run :func:`rebuild_fts_statement` — one
           ``INSERT INTO fts SELECT ... FROM canonical`` call that
           tokenizes every row server-side. Takes ~3-5min on a 1.5M-row
           mirror, well under the 10-min ceiling.
        3. Create the sync triggers so future single-row writes
           (refresh cron, ad-hoc upserts) keep FTS5 in sync.

        Steps 1 + 3 share the same DDL set (FTS5 table + triggers)
        but with the rebuild between them so the triggers never see
        the bulk SELECT INSERT and accidentally double-populate.
        """
        if self._client is None:
            raise RuntimeError("finalize_after_bulk_load called on a disabled mirror")

        # 1) Recreate FTS5 virtual table only — defer triggers until
        # after the rebuild SELECT so they don't fire on it.
        await self._client.execute(fts_ddl()[0])
        _LOGGER.info(
            "mb_mirror.bulk_load.fts_table_recreated",
            extra={"event": "mb_mirror.bulk_load.fts_table_recreated"},
        )

        # 2) Single-shot rebuild — slowest step, ~3-5min for 1.5M rows.
        _LOGGER.info(
            "mb_mirror.bulk_load.fts_rebuild_started",
            extra={"event": "mb_mirror.bulk_load.fts_rebuild_started"},
        )
        await self._client.execute(rebuild_fts_statement(), timeout=_FTS_REBUILD_TIMEOUT_S)
        _LOGGER.info(
            "mb_mirror.bulk_load.fts_rebuild_complete",
            extra={"event": "mb_mirror.bulk_load.fts_rebuild_complete"},
        )

        # 3) Restore sync triggers for ongoing single-row maintenance.
        for trigger_ddl in fts_ddl()[1:]:
            await self._client.execute(trigger_ddl)
        _LOGGER.info(
            "mb_mirror.bulk_load.fts_triggers_restored",
            extra={"event": "mb_mirror.bulk_load.fts_triggers_restored"},
        )

    @staticmethod
    def _meta_upsert_statement() -> tuple[str, list[Any]]:
        """Standardized ``mirror_meta`` schema-version row upsert.

        Shared by :meth:`initialize_schema` and
        :meth:`initialize_core_schema` so the meta row always reflects
        the running SCHEMA_VERSION regardless of which bootstrap path
        was used.
        """
        return (
            """
            INSERT INTO mirror_meta (id, schema_version)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET schema_version = excluded.schema_version
            """,
            [SCHEMA_VERSION],
        )

    # ------------------------------------------------------------------
    # Read surface
    # ------------------------------------------------------------------

    async def find_by_mbid(self, mbid: str) -> MirrorRow | None:
        """Return the mirror row for ``mbid`` or ``None``.

        Failure-tolerant: returns ``None`` on disabled mirror, network
        error, or SQL error. The search-flow caller treats ``None`` as
        "tier-0 miss, fall through to Atlas" — never as fatal.
        """
        if self._client is None or not mbid:
            return None
        try:
            result = await self._client.execute(
                """
                SELECT mbid, title, artist_credit, release_year,
                       primary_type, genres, cover_art_url
                FROM albums_mirror
                WHERE mbid = ?
                """,
                params=[mbid],
            )
        except (httpx.HTTPError, TursoExecutionError) as exc:
            _LOGGER.warning(
                "mb_mirror.find_by_mbid_degraded",
                extra={"event": "mb_mirror.find_by_mbid_degraded", "error": repr(exc)},
            )
            return None
        if not result.rows:
            return None
        return _row_to_mirror(result.rows[0])

    async def search_text(
        self,
        query: str,
        *,
        limit: int = _DEFAULT_TEXT_SEARCH_LIMIT,
    ) -> list[MirrorRow]:
        """Full-text search against the FTS5 index.

        Returns up to ``limit`` rows in BM25-relevance order. Uses
        implicit-AND across user tokens with a prefix marker on the
        last token — typing ``"blon"`` hits ``"Blonde"``,
        ``"blonde frank oce"`` hits Frank Ocean's Blonde with strong
        relevance because all three tokens match. Earlier revision
        used ``"<phrase>"*`` which isn't valid FTS5 grammar and
        produced a parser error on every call.

        Degrades silently on any error (same rationale as
        :meth:`find_by_mbid`).
        """
        if self._client is None:
            return []
        match_expr = self._build_fts_match(query)
        if not match_expr:
            return []
        try:
            result = await self._client.execute(
                """
                SELECT albums_mirror.mbid, albums_mirror.title,
                       albums_mirror.artist_credit, albums_mirror.release_year,
                       albums_mirror.primary_type, albums_mirror.genres,
                       albums_mirror.cover_art_url
                FROM albums_mirror_fts
                JOIN albums_mirror ON albums_mirror.rowid = albums_mirror_fts.rowid
                WHERE albums_mirror_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                params=[match_expr, limit],
            )
        except (httpx.HTTPError, TursoExecutionError) as exc:
            _LOGGER.warning(
                "mb_mirror.search_text_degraded",
                extra={
                    "event": "mb_mirror.search_text_degraded",
                    "error": repr(exc),
                    "query": query,
                    "match_expr": match_expr,
                },
            )
            return []
        return [_row_to_mirror(row) for row in result.rows]

    @staticmethod
    def _build_fts_match(query: str) -> str:
        """Build a valid FTS5 MATCH expression for ``query``.

        Rules:
        * Strip FTS5-reserved punctuation (``*"():+-^``); users
          typing them mean them literally, so replacing with
          whitespace preserves token boundaries.
        * Split on whitespace; lowercase isn't necessary (FTS5's
          unicode61 tokenizer folds case at index + match time).
        * Append ``*`` to the **last** token only — gives us
          autocomplete-as-you-type behaviour (``"blon"`` → matches
          ``"Blonde"``) without making every token a prefix match
          (which would inflate the match set + tank relevance).
        * If only one token is present, that token IS the prefix
          target.
        * Empty after stripping → return ``""`` and the caller
          short-circuits without touching the database.
        """
        if not query:
            return ""
        safe = _FTS_RESERVED_RE.sub(" ", query)
        tokens = [t for t in safe.split() if t]
        if not tokens:
            return ""
        # All tokens but the last enforce a full-token match;
        # last token becomes a prefix match for live-typing UX.
        return " ".join([*tokens[:-1], f"{tokens[-1]}*"])

    async def search_text_with_filters(
        self,
        *,
        query: str,
        year_min: int | None,
        year_max: int | None,
        decade_buckets: set[int] | None,
        genre: str | None,
        sort_key: str,
        limit: int,
        offset: int,
    ) -> tuple[list[MirrorRow], int]:
        """FTS5-text + filter combined query against the mirror.

        Combines the FTS5 ``MATCH`` expression (via :meth:`_build_fts_match`)
        with the year/decade/genre ``WHERE`` clause (via
        :meth:`_build_filter_where`) in a single SQL pass. Returns
        ``(rows, total)`` where rows are in BM25-relevance order for
        ``sort_key='relevance'`` and in the sort_key's natural order
        otherwise.

        ``total`` is the COUNT(*) over the combined MATCH + WHERE,
        capped at ``_TOTAL_DISPLAY_CAP`` per FR-008 to avoid leaking
        unbounded counts to the client. ``sort_key='surprise'`` runs
        ``ORDER BY RANDOM()`` with no separate count (returns
        ``len(rows)`` as total — no pagination concept).

        Degrades silently to ``([], 0)`` on disabled mirror, empty
        query, network error, or SQL error. Caller falls through to
        the legacy Discogs-primary search.
        """
        if self._client is None:
            return [], 0
        match_expr = self._build_fts_match(query)
        if not match_expr:
            return [], 0

        where_clause, where_params = self._build_filter_where(
            year_min=year_min,
            year_max=year_max,
            decade_buckets=decade_buckets,
            genre=genre,
        )
        if where_clause is None:
            return [], 0

        # FTS5 needs the MATCH param first; downstream filter params
        # bind to the WHERE placeholders in order.
        match_and_where = f"albums_mirror_fts MATCH ? AND ({where_clause})"

        try:
            if sort_key == "surprise":
                rows_result = await self._client.execute(
                    f"""
                    SELECT albums_mirror.mbid, albums_mirror.title,
                           albums_mirror.artist_credit, albums_mirror.release_year,
                           albums_mirror.primary_type, albums_mirror.genres,
                           albums_mirror.cover_art_url
                    FROM albums_mirror_fts
                    JOIN albums_mirror ON albums_mirror.rowid = albums_mirror_fts.rowid
                    WHERE {match_and_where}
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    params=[match_expr, *where_params, limit],
                )
                rows = [_row_to_mirror(row) for row in rows_result.rows]
                return rows, len(rows)

            order_clause = "rank" if sort_key == "relevance" else self._sort_clause_for(sort_key)

            count_result = await self._client.execute(
                f"""
                SELECT COUNT(*)
                FROM albums_mirror_fts
                JOIN albums_mirror ON albums_mirror.rowid = albums_mirror_fts.rowid
                WHERE {match_and_where}
                """,
                params=[match_expr, *where_params],
            )
            raw_total = int(count_result.rows[0][0] or 0) if count_result.rows else 0
            total = min(raw_total, _TOTAL_DISPLAY_CAP)

            page_result = await self._client.execute(
                f"""
                SELECT albums_mirror.mbid, albums_mirror.title,
                       albums_mirror.artist_credit, albums_mirror.release_year,
                       albums_mirror.primary_type, albums_mirror.genres,
                       albums_mirror.cover_art_url
                FROM albums_mirror_fts
                JOIN albums_mirror ON albums_mirror.rowid = albums_mirror_fts.rowid
                WHERE {match_and_where}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
                """,
                params=[match_expr, *where_params, limit, offset],
            )
            return [_row_to_mirror(row) for row in page_result.rows], total
        except (httpx.HTTPError, TursoExecutionError) as exc:
            _LOGGER.warning(
                "mb_mirror.search_text_with_filters_degraded",
                extra={
                    "event": "mb_mirror.search_text_with_filters_degraded",
                    "error": repr(exc),
                    "query": query,
                    "match_expr": match_expr,
                    "where": where_clause,
                },
            )
            return [], 0

    async def filter_search(
        self,
        *,
        year_min: int | None,
        year_max: int | None,
        decade_buckets: set[int] | None,
        genre: str | None,
        sort_key: str,
        limit: int,
        offset: int,
    ) -> tuple[list[MirrorRow], int]:
        """SQL-backed browse-mode search against the mirror.

        Mirrors the contract of
        :func:`auxd_api.modules.search.service.filter_only_search`
        (decade-bucket year ranges, optional genre substring, sort key,
        pagination) but executes against Turso instead of Mongo. The
        mirror's ~1.3M release-groups make decade/genre browse feel
        actually populated; the local Mongo ``albums`` collection at
        ~5k rows alone never could.

        Returns ``(rows, total)`` where ``total`` is the unfiltered
        match count for paginate-by-position to work. Failure-tolerant
        (``([], 0)`` on disabled mirror, network error, or SQL error).

        Sort key mapping mirrors ``_filter_only_sort_spec`` so the
        downstream serialiser doesn't have to special-case the source.
        """
        if self._client is None:
            return [], 0

        where_clause, params = self._build_filter_where(
            year_min=year_min,
            year_max=year_max,
            decade_buckets=decade_buckets,
            genre=genre,
        )
        if where_clause is None:
            # Impossible-intersection (e.g. decade=2010s + year_max=1999).
            # Return an empty page rather than running a query that will
            # never match — saves a round trip.
            return [], 0

        order_clause = self._sort_clause_for(sort_key)

        try:
            if sort_key == "surprise":
                # ``ORDER BY RANDOM()`` is fine on SQLite — for our row
                # counts (≤1.3M filtered) it's a sub-second scan. No
                # pagination concept for random; cap at ``limit``.
                rows_result = await self._client.execute(
                    f"""
                    SELECT mbid, title, artist_credit, release_year,
                           primary_type, genres, cover_art_url
                    FROM albums_mirror
                    WHERE {where_clause}
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    params=[*params, limit],
                )
                rows = [_row_to_mirror(row) for row in rows_result.rows]
                return rows, len(rows)

            count_result = await self._client.execute(
                f"SELECT COUNT(*) FROM albums_mirror WHERE {where_clause}",
                params=params,
            )
            total = int(count_result.rows[0][0] or 0) if count_result.rows else 0
            page_result = await self._client.execute(
                f"""
                SELECT mbid, title, artist_credit, release_year,
                       primary_type, genres, cover_art_url
                FROM albums_mirror
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
                """,
                params=[*params, limit, offset],
            )
            return [_row_to_mirror(row) for row in page_result.rows], total
        except (httpx.HTTPError, TursoExecutionError) as exc:
            _LOGGER.warning(
                "mb_mirror.filter_search_degraded",
                extra={
                    "event": "mb_mirror.filter_search_degraded",
                    "error": repr(exc),
                    "where": where_clause,
                },
            )
            return [], 0

    @staticmethod
    def _build_filter_where(
        *,
        year_min: int | None,
        year_max: int | None,
        decade_buckets: set[int] | None,
        genre: str | None,
    ) -> tuple[str | None, list[Any]]:
        """Build a SQL WHERE clause for :meth:`filter_search`.

        Returns ``(clause, params)`` for caller string-interpolation
        into the final SQL, or ``(None, [])`` when the filter
        intersection is empty (e.g. ``decade=2010s, year_max=1999``).

        The clause is composed AND-style: every active filter adds a
        sub-condition. Decade-bucket → year-range expansion is done
        Python-side so the resulting SQL stays a flat conjunction
        with no subqueries.
        """
        clauses: list[str] = []
        params: list[Any] = []

        # Year + decade ranges, intersected.
        derived_min = year_min
        derived_max = year_max
        if decade_buckets:
            ranges: list[tuple[int, int]] = []
            for decade_start in sorted(decade_buckets):
                eff_min = decade_start if year_min is None else max(decade_start, year_min)
                eff_max = decade_start + 9 if year_max is None else min(decade_start + 9, year_max)
                if eff_min > eff_max:
                    continue
                ranges.append((eff_min, eff_max))
            if not ranges:
                return None, []
            if len(ranges) == 1:
                eff_min, eff_max = ranges[0]
                clauses.append("release_year BETWEEN ? AND ?")
                params.extend([eff_min, eff_max])
            else:
                or_terms = " OR ".join(["(release_year BETWEEN ? AND ?)"] * len(ranges))
                clauses.append(f"({or_terms})")
                for eff_min, eff_max in ranges:
                    params.extend([eff_min, eff_max])
        elif derived_min is not None or derived_max is not None:
            if derived_min is not None and derived_max is not None:
                clauses.append("release_year BETWEEN ? AND ?")
                params.extend([derived_min, derived_max])
            elif derived_min is not None:
                clauses.append("release_year >= ?")
                params.append(derived_min)
            else:
                clauses.append("release_year <= ?")
                params.append(derived_max)

        if genre:
            # Mirror stores genres as a comma-joined CSV; substring
            # match on the lowercased column catches every encoding
            # variant ("Hip Hop" stored, user typed "hip"). The CSV
            # form is already normalised lower-case at ingest time
            # (see ``scripts/mb_mirror_ingest._tags_to_csv``).
            clauses.append("genres LIKE ?")
            params.append(f"%{genre.lower()}%")

        if not clauses:
            # No active filters → match everything. ``1=1`` is the
            # standard SQLite placeholder for "always true" so the
            # caller can string-interpolate without special-casing.
            return "1=1", []
        return " AND ".join(clauses), params

    @staticmethod
    def _sort_clause_for(sort_key: str) -> str:
        """Map a UI sort key to a libSQL ``ORDER BY`` fragment.

        Mirror rows don't carry the same auxd-specific signals the
        Mongo ``albums`` collection does (``rating_count``,
        ``created_at``), so popularity / recently_added gracefully
        degrade to release-year ordering. Once a user actually engages
        with a mirror row (logs / rates / reviews it), the row
        materialises into Mongo where the real signals are kept.
        """
        if sort_key == "year_newest":
            return "release_year DESC"
        if sort_key == "year_oldest":
            return "release_year ASC"
        # Popular / recently_added / relevance — no Turso-side proxy
        # for any of these, so we fall back to a deterministic order
        # that's at least useful (newest first within a decade).
        return "release_year DESC"

    async def count_rows(self) -> int | None:
        """Return the row count in ``albums_mirror`` or ``None`` on error.

        Diagnostic helper for operators verifying the mirror has
        actually populated (e.g. after the initial ingest run).
        Same failure semantics as the other reads — never raises.
        """
        if self._client is None:
            return None
        try:
            result = await self._client.execute("SELECT COUNT(*) FROM albums_mirror")
        except (httpx.HTTPError, TursoExecutionError) as exc:
            _LOGGER.warning(
                "mb_mirror.count_rows_degraded",
                extra={"event": "mb_mirror.count_rows_degraded", "error": repr(exc)},
            )
            return None
        if not result.rows or not result.rows[0]:
            return 0
        return int(result.rows[0][0] or 0)

    # ------------------------------------------------------------------
    # Write surface (ETL + refresh)
    # ------------------------------------------------------------------

    async def upsert_many(self, rows: Iterable[MirrorRow]) -> int:
        """Upsert ``rows`` as a single multi-row INSERT statement.

        Earlier revisions issued N separate ``INSERT`` statements per
        batch; each fired the FTS5 sync trigger independently and on
        Turso's free tier a 500-row batch could exceed the 15s read
        timeout. Folding the whole batch into one statement keeps the
        SQL parse + transaction commit single-shot — same row count,
        ~one-tenth the server-side work.

        Conflict on ``mbid`` updates every column except the primary
        key, so a refresh run silently corrects metadata drift
        (titles fixed in MB, artist-credit reattribution, etc.).

        Returns the number of rows touched. The implementation
        recursively halves the batch and retries on timeout, so a
        transient slow response on one 500-row batch self-recovers
        into two 250-row batches without dropping data. Aborts when
        sub-batches reach :data:`_MIN_RETRY_BATCH` — at that point
        the issue is the server, not the batch size.
        """
        if self._client is None:
            return 0
        batch = list(rows)
        if not batch:
            return 0
        await self._upsert_chunk(batch)
        return len(batch)

    async def _upsert_chunk(self, batch: list[MirrorRow]) -> None:
        """Issue a single multi-row INSERT for ``batch``; split-retry on timeout.

        Separated from :meth:`upsert_many` so the recursion lives on
        a private helper and the public surface stays "give me rows,
        I'll get them all in."
        """
        if not batch:
            return
        # Invariant: callers (upsert_many + recursive self-call) only reach
        # this point after the disabled-mirror early-return upstream.
        assert self._client is not None
        sql = self._build_multi_row_upsert(len(batch))
        params: list[Any] = []
        for row in batch:
            params.extend(
                [
                    row.mbid,
                    row.title,
                    row.artist_credit,
                    row.release_year,
                    row.primary_type,
                    row.genres,
                    row.cover_art_url,
                ]
            )
        try:
            await self._client.execute(sql, params=params)
            return
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout) as exc:
            if len(batch) <= _MIN_RETRY_BATCH:
                _LOGGER.error(
                    "mb_mirror.upsert_timeout_at_floor",
                    extra={
                        "event": "mb_mirror.upsert_timeout_at_floor",
                        "batch_size": len(batch),
                        "error": repr(exc),
                    },
                )
                raise
            half = len(batch) // 2
            _LOGGER.warning(
                "mb_mirror.upsert_timeout_split_retry",
                extra={
                    "event": "mb_mirror.upsert_timeout_split_retry",
                    "batch_size": len(batch),
                    "next_batch_size": half,
                },
            )
            await self._upsert_chunk(batch[:half])
            await self._upsert_chunk(batch[half:])

    @staticmethod
    def _build_multi_row_upsert(row_count: int) -> str:
        """Compose the multi-row INSERT...ON CONFLICT statement.

        SQLite supports comma-separated ``VALUES`` tuples in a single
        INSERT; the ON CONFLICT clause resolves per row, so this is
        functionally identical to N separate INSERT...ON CONFLICT
        statements but executes server-side as one transaction.
        """
        placeholder = "(?, ?, ?, ?, ?, ?, ?)"
        all_placeholders = ", ".join([placeholder] * row_count)
        return f"""
            INSERT INTO albums_mirror
                (mbid, title, artist_credit, release_year,
                 primary_type, genres, cover_art_url)
            VALUES {all_placeholders}
            ON CONFLICT(mbid) DO UPDATE SET
                title = excluded.title,
                artist_credit = excluded.artist_credit,
                release_year = excluded.release_year,
                primary_type = excluded.primary_type,
                genres = excluded.genres,
                cover_art_url = excluded.cover_art_url
        """

    async def record_ingest_start(self, *, dump_date: str) -> None:
        """Mark a new ingest pass as starting on ``mirror_meta``.

        Useful for the operator dashboard query "when was the
        mirror last refreshed, and from which dump?". ETL calls
        this on bootstrap.
        """
        if self._client is None:
            return
        await self._client.execute_named(
            """
            INSERT INTO mirror_meta (id, schema_version, dump_date, last_ingest_started_at)
            VALUES (1, :schema_version, :dump_date, :ts)
            ON CONFLICT(id) DO UPDATE SET
                schema_version = excluded.schema_version,
                dump_date = excluded.dump_date,
                last_ingest_started_at = excluded.last_ingest_started_at
            """,
            params={
                "schema_version": SCHEMA_VERSION,
                "dump_date": dump_date,
                "ts": datetime.now(UTC).isoformat(),
            },
        )

    async def record_ingest_finish(self, *, row_count: int) -> None:
        """Stamp the ingest as completed and update the row count."""
        if self._client is None:
            return
        await self._client.execute_named(
            """
            UPDATE mirror_meta
               SET last_ingest_finished_at = :ts,
                   row_count = :row_count
             WHERE id = 1
            """,
            params={"ts": datetime.now(UTC).isoformat(), "row_count": row_count},
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_mirror(row: list[Any]) -> MirrorRow:
    """Coerce one Turso row tuple into a :class:`MirrorRow`.

    Column order MUST match the SELECT in :meth:`AlbumMirrorService.find_by_mbid`
    + :meth:`search_text`; if you reorder one, reorder both.
    """
    return MirrorRow(
        mbid=row[0],
        title=row[1] or "",
        artist_credit=row[2] or "",
        release_year=row[3] if isinstance(row[3], int) else None,
        primary_type=row[4],
        genres=row[5] or "",
        cover_art_url=row[6],
    )


__all__ = ["AlbumMirrorService"]
