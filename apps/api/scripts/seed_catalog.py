"""CLI runner for the catalog-seed pipeline.

Usage::

    uv run python scripts/seed_catalog.py <source_name>

    # example:
    uv run python scripts/seed_catalog.py grammy_aoty

Spins up the Beanie DB connection, hydrates the named source's
entries, runs the ingest, and prints a one-line summary to stdout.
Errors during individual entries are absorbed by the service (and
logged to the :class:`SeedRun` document); only fatal startup errors
make it back here as a non-zero exit code.

For the quarterly cron equivalent, see
:mod:`auxd_api.workers.catalog_seed_job`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

# Use the OS-native trust store via :mod:`truststore` so Discogs +
# MusicBrainz HTTPS calls work inside corp TLS-MITM environments
# (Zscaler, Bluecoat, Cisco Umbrella) that inject a custom root CA
# into the macOS Keychain. Without this, the provider clients' httpx
# defaults fail to validate the upstream cert chain and every call
# returns "status: failed" with high latency.
#
# Must run BEFORE any module imports that construct ``ssl.SSLContext``
# at import time. The provider modules don't, but threading this in
# at the top is the safest seam.
try:
    import truststore  # type: ignore[import-not-found]

    truststore.inject_into_ssl()
except ImportError:
    # ``truststore`` ships with the ``seed-scripts`` extra. If it's
    # missing, fall through to Python's default trust store — works
    # fine outside corp networks; useful for CI.
    pass

from auxd_api.db import close_db, init_db
from auxd_api.modules.catalog_seed.service import ingest_seed_list
from auxd_api.modules.catalog_seed.sources import SOURCES
from auxd_api.providers.discogs import DiscogsCatalogProvider
from auxd_api.providers.musicbrainz import MusicBrainzCatalogProvider
from auxd_api.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
_LOGGER = logging.getLogger("auxd.catalog_seed.cli")


async def main(source_name: str) -> int:
    if source_name not in SOURCES:
        sys.stderr.write(f"unknown source: {source_name!r}\navailable: {sorted(SOURCES)}\n")
        return 2

    settings = get_settings()
    await init_db(settings.MONGODB_URI)
    try:
        entries = SOURCES[source_name]()
        _LOGGER.info("loaded %d entries from %s", len(entries), source_name)

        if not getattr(settings, "DISCOGS_API_TOKEN", None):
            _LOGGER.warning(
                "DISCOGS_API_TOKEN not set — running with the unauthenticated "
                "25 req/min limit. Expect ~2.5s pacing per entry; the ingest "
                "service handles the throttling. To go faster, set the env "
                "var and re-run."
            )

        mb = MusicBrainzCatalogProvider()
        discogs = DiscogsCatalogProvider()

        run = await ingest_seed_list(
            source_name=source_name,
            entries=entries,
            mb_provider=mb,
            discogs_provider=discogs,
        )
        print(
            f"[{source_name}] status={run.status.value} "
            f"attempted={run.entries_attempted} "
            f"succeeded={run.entries_succeeded} "
            f"failed={run.entries_failed} "
            f"run_id={run.id}"
        )
        return 0 if run.status.value == "completed" else 1
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a catalog seed ingest pass.")
    parser.add_argument(
        "source",
        help="Source name registered in catalog_seed.sources.SOURCES (e.g. grammy_aoty).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.source)))
