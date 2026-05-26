"""Quick verification script for the MB mirror.

Usage::

    cd apps/api
    uv run python scripts/mb_mirror_verify.py

Sanity checks:
1. Connect to Turso using ``TURSO_DATABASE_URL`` / ``TURSO_AUTH_TOKEN``.
2. Report the row count in ``albums_mirror`` (should match the
   ``kept=`` number from the last ingest run).
3. Run a few sample text searches that should hit a populated
   mirror; print results.

Failure modes the script catches:
* No credentials → exits with a clear message
* Mirror empty → row count is 0
* FTS5 degraded → empty result lists (check logs for the underlying error)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Bootstrap sys.path so direct invocation works without PYTHONPATH.
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

try:
    import truststore  # type: ignore[import-not-found]

    truststore.inject_into_ssl()
except ImportError:
    pass

from auxd_api.modules.mb_mirror.client import TursoClient  # noqa: E402
from auxd_api.modules.mb_mirror.service import AlbumMirrorService  # noqa: E402
from auxd_api.settings import get_settings  # noqa: E402

# Sample queries spanning era / genre / popularity. If any of these
# returns nothing on a 50k-row mirror it's a sign that either
# (a) the smoke ingest happened to pick obscure release-groups, or
# (b) FTS5 still has a parse issue. Sample size doesn't matter for
# the parse-error case; both will surface here.
_SAMPLE_QUERIES: list[str] = [
    "blonde",
    "innervisions",
    "kanye",
    "abbey road",
    "ok computer",
]


async def main() -> int:
    settings = get_settings()
    client = TursoClient.from_settings(settings)
    if client is None:
        sys.stderr.write(
            "TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not set — "
            "mirror is disabled in this environment.\n"
        )
        return 2

    async with client as turso:
        svc = AlbumMirrorService(turso)

        # 1) Row count — quickest "is the mirror populated?" check.
        row_count = await svc.count_rows()
        if row_count is None:
            print("ERROR: count_rows() returned None — connection / auth issue")
            return 1
        print(f"rows in mirror: {row_count}")

        if row_count == 0:
            print("ERROR: mirror is empty — run scripts/mb_mirror_ingest.py first")
            return 1

        # 2) Sample queries — exercise the FTS5 path.
        print("\nSample searches:")
        for query in _SAMPLE_QUERIES:
            results = await svc.search_text(query, limit=3)
            print(f"  q={query!r} → {len(results)} hits")
            for row in results:
                print(
                    f"    {row.artist_credit} - {row.title} "
                    f"({row.release_year}) [{row.genres or '-'}]"
                )

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    raise SystemExit(asyncio.run(main()))
