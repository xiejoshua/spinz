"""Quarterly catalog-seed cron job (feature 003 — Bundle Y growth).

Walks every registered source in
:mod:`auxd_api.modules.catalog_seed.sources.SOURCES` and runs the
ingest service against each. Idempotent (the existing
``resolve_identity`` MBID dedupe makes re-runs cheap — already-cached
albums short-circuit on the first DB query and don't burn provider
quota).

Schedule + opt-in
=================
The cron registration in :class:`auxd_api.workers.main.WorkerSettings`
is gated by the ``CATALOG_SEED_CRON_ENABLED`` settings flag (defaults
to ``False``). The founder flips that flag on once they're comfortable
with the seed pipeline — until then the job is dead code in the
worker's registry but won't actually fire on schedule.

Rationale: the first run of every source can take ~10 minutes per
hundred entries (bounded by MB's 1 req/sec etiquette), so a careless
opt-in could burn the worker's CPU budget for an hour. Gating behind
an explicit env flag keeps the foot-gun visible.
"""

from __future__ import annotations

import logging
from typing import Any

from auxd_api.modules.catalog_seed.service import ingest_seed_list
from auxd_api.modules.catalog_seed.sources import SOURCES
from auxd_api.providers.discogs import DiscogsCatalogProvider
from auxd_api.providers.musicbrainz import MusicBrainzCatalogProvider
from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.catalog_seed.cron")


async def run_catalog_seed_quarterly(ctx: dict[str, Any]) -> dict[str, int]:
    """Iterate every registered source and run an ingest pass for each.

    Returns a per-source ``{source_name: entries_succeeded}`` summary
    in arq's job-result store so an operator running
    ``arq --check`` can confirm the last quarter's catalog growth at a
    glance.

    Errors at the source level (missing CSV, parse error) are logged
    and skipped — the loop keeps going so one broken source doesn't
    starve the rest. Per-entry failures inside ``ingest_seed_list``
    are absorbed by the service.
    """
    # Opt-in gate — see the module docstring for the rationale. The
    # cron is always registered (so an operator can flip the flag and
    # get coverage on the next quarter without a deploy), but stays
    # inert until they're ready.
    settings = get_settings()
    if not settings.CATALOG_SEED_CRON_ENABLED:
        _LOGGER.info(
            "catalog_seed.cron.skipped_disabled",
            extra={"event": "catalog_seed.cron.skipped_disabled"},
        )
        return {}

    # The startup hook (auxd_api.workers.main._on_startup) already
    # initialised Beanie + an MB provider on ctx; we construct our own
    # Discogs provider per-run because the existing services do that
    # too (Discogs has a much-looser 60/min limit, so per-request
    # construction is fine).
    mb_provider = ctx.get("mb_provider") or MusicBrainzCatalogProvider()
    discogs_provider = DiscogsCatalogProvider()

    summary: dict[str, int] = {}
    for source_name, loader in SOURCES.items():
        try:
            entries = loader()
        except FileNotFoundError as exc:
            _LOGGER.info(
                "catalog_seed.cron.source_missing",
                extra={
                    "event": "catalog_seed.cron.source_missing",
                    "source": source_name,
                    "reason": str(exc),
                },
            )
            continue
        except Exception as exc:  # noqa: BLE001 — keep loop alive
            _LOGGER.exception(
                "catalog_seed.cron.loader_failed",
                extra={
                    "event": "catalog_seed.cron.loader_failed",
                    "source": source_name,
                    "error": repr(exc),
                },
            )
            continue

        _LOGGER.info(
            "catalog_seed.cron.source_started",
            extra={
                "event": "catalog_seed.cron.source_started",
                "source": source_name,
                "entries": len(entries),
            },
        )
        run = await ingest_seed_list(
            source_name=source_name,
            entries=entries,
            mb_provider=mb_provider,
            discogs_provider=discogs_provider,
        )
        summary[source_name] = run.entries_succeeded

    _LOGGER.info(
        "catalog_seed.cron.completed",
        extra={"event": "catalog_seed.cron.completed", "summary": summary},
    )
    return summary


__all__ = ["run_catalog_seed_quarterly"]
