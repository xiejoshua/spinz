"""Schema definitions for the MB mirror.

The mirror lives in one SQLite/libSQL database with two tables:

* ``albums_mirror`` — the canonical row, keyed by MBID
* ``albums_mirror_fts`` — FTS5 virtual table for sub-10ms text
  search on ``(title, artist_credit)``

Indexing decisions
------------------
* ``mbid`` is the primary key (covered by SQLite's rowid alias).
* ``artist_credit`` gets a non-unique index for "browse by artist"
  scans — small index cost, useful for future features.
* ``release_year`` gets an index for decade/year filtering once we
  wire that surface against the mirror.
* The FTS5 table lets us answer "type 'blon'" ⇒ "Blonde, Frank
  Ocean" in O(matching-prefixes) time, the same shape our existing
  Atlas Search index gives us in cloud mode.

Schema versioning
-----------------
``schema_version`` is stored in a single-row ``mirror_meta``
table so the ETL can detect drift and abort cleanly (rather than
silently writing into a stale schema). Bump :data:`SCHEMA_VERSION`
whenever the shape changes; the ingest worker will pick up on the
next run.
"""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final[int] = 1

# Single-row metadata table used by the ETL to verify schema parity
# before bulk-loading. Also a useful spot for the ETL to stash the
# source dump's date so we can tell when the mirror was last
# refreshed without an external monitoring system.
META_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS mirror_meta (
    -- Single-row table — keyed by a literal sentinel so a stray
    -- second insert errors cleanly instead of silently corrupting state.
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    dump_date TEXT,        -- ISO-8601 date of the MB dump used for ingest
    row_count INTEGER NOT NULL DEFAULT 0,
    last_ingest_started_at TEXT,
    last_ingest_finished_at TEXT
)
"""

# Canonical mirror table. Column ordering matches the ETL's INSERT
# binding order so the bulk-load path stays trivially readable.
ALBUMS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS albums_mirror (
    mbid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist_credit TEXT NOT NULL,
    release_year INTEGER,
    primary_type TEXT,                  -- "Album", "EP", "Single", "Compilation", ...
    genres TEXT NOT NULL DEFAULT '',    -- CSV of MB tag names above cutoff
    cover_art_url TEXT                  -- coverartarchive.org URL when known
)
"""

INDEXES: Final[tuple[str, ...]] = (
    "CREATE INDEX IF NOT EXISTS idx_albums_mirror_artist ON albums_mirror(artist_credit)",
    "CREATE INDEX IF NOT EXISTS idx_albums_mirror_year ON albums_mirror(release_year)",
)

# FTS5 virtual table — backed by the same content via ``content``
# directive so we don't double-store the strings. Tokenisation uses
# the ``unicode61`` analyzer with diacritic-fold so "Beyoncé" matches
# "beyonce".
FTS_TABLE: Final[str] = """
CREATE VIRTUAL TABLE IF NOT EXISTS albums_mirror_fts USING fts5(
    title,
    artist_credit,
    content='albums_mirror',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
)
"""

# Triggers keep the FTS index in sync with the canonical table on
# INSERT / UPDATE / DELETE. SQLite's docs recommend this pattern for
# content-linked FTS5 tables and the ETL relies on it staying
# consistent without manual rebuilds.
FTS_SYNC_TRIGGERS: Final[tuple[str, ...]] = (
    """
    CREATE TRIGGER IF NOT EXISTS albums_mirror_ai
    AFTER INSERT ON albums_mirror BEGIN
        INSERT INTO albums_mirror_fts(rowid, title, artist_credit)
        VALUES (new.rowid, new.title, new.artist_credit);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS albums_mirror_ad
    AFTER DELETE ON albums_mirror BEGIN
        INSERT INTO albums_mirror_fts(albums_mirror_fts, rowid, title, artist_credit)
        VALUES('delete', old.rowid, old.title, old.artist_credit);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS albums_mirror_au
    AFTER UPDATE ON albums_mirror BEGIN
        INSERT INTO albums_mirror_fts(albums_mirror_fts, rowid, title, artist_credit)
        VALUES('delete', old.rowid, old.title, old.artist_credit);
        INSERT INTO albums_mirror_fts(rowid, title, artist_credit)
        VALUES (new.rowid, new.title, new.artist_credit);
    END
    """,
)


def core_ddl() -> list[str]:
    """Return DDL for the canonical table + indexes (no FTS5 work).

    Used by the bulk-load path which temporarily defers FTS5 setup
    until after the rows are loaded. Each row insert during bulk
    load would otherwise fire the FTS5 sync trigger and pay the
    per-token index-update cost — for 1.5M rows that ~14× the
    ingest wall-clock.
    """
    return [META_TABLE, ALBUMS_TABLE, *INDEXES]


def fts_ddl() -> list[str]:
    """Return DDL for the FTS5 virtual table + sync triggers.

    Applied AFTER bulk-load completes (the population step happens
    via :func:`rebuild_fts_statements`). The triggers are needed
    going forward so the single-row refresh-cron writes keep FTS5
    in sync without another rebuild.
    """
    return [FTS_TABLE, *FTS_SYNC_TRIGGERS]


def all_ddl() -> list[str]:
    """Return every DDL statement, in safe execution order.

    Single-row writers (the refresh-cron worker, ad-hoc upserts)
    use this to ensure both the canonical table AND the FTS5
    surface are in place. Bulk-load callers reach for
    :func:`core_ddl` + :func:`fts_ddl` separately.
    """
    return [*core_ddl(), *fts_ddl()]


def drop_fts_statements() -> list[str]:
    """Drop the FTS5 sync triggers + the FTS5 virtual table.

    Order matters: triggers first because they reference the FTS5
    table; dropping the table while a trigger still mentions it
    would error. ``IF EXISTS``-guarded so safe to call against a
    fresh mirror that hasn't yet provisioned FTS5.
    """
    return [
        "DROP TRIGGER IF EXISTS albums_mirror_ai",
        "DROP TRIGGER IF EXISTS albums_mirror_ad",
        "DROP TRIGGER IF EXISTS albums_mirror_au",
        "DROP TABLE IF EXISTS albums_mirror_fts",
    ]


def rebuild_fts_statement() -> str:
    """Single ``INSERT...SELECT`` that populates FTS5 from albums_mirror.

    Run after the FTS5 table has been (re-)created. SQLite processes
    this server-side as one tokenization pass — orders of magnitude
    faster than per-row trigger fires during bulk load. For ~1.5M
    rows the rebuild takes ~3-5min on Turso's free tier.
    """
    return """
        INSERT INTO albums_mirror_fts(rowid, title, artist_credit)
        SELECT rowid, title, artist_credit FROM albums_mirror
    """


__all__ = [
    "SCHEMA_VERSION",
    "all_ddl",
    "core_ddl",
    "drop_fts_statements",
    "fts_ddl",
    "rebuild_fts_statement",
]
