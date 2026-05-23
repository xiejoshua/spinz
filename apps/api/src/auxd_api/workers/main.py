"""arq worker entry point (T013 scaffold).

Run with::

    uv run arq auxd_api.workers.main.WorkerSettings

The arq worker connects to Redis using ``REDIS_URL`` from the
environment, pulls jobs enqueued by the API process via
:func:`auxd_api.redis_client.enqueue_job`, and executes them
sequentially per the arq job model.

Job registry (mirrors plan §8.4 + the §6 album backbone):

* :func:`noop_job` (T013) — connectivity smoke test.
* :func:`refresh_stale_album_metadata` (T064) — daily 04:00 UTC sweep
  that refreshes Albums whose ``cache_expires_at`` has elapsed.
* :func:`reconcile_candidate_albums` (T065) — weekly Sunday 03:00 UTC
  sweep that attempts MBID reconciliation on Discogs-sourced candidates.

Cron jobs share the ``mb_provider`` injected on startup so the
MusicBrainz client is reused across runs rather than rebuilt per
invocation (which would compound the 1 req/sec etiquette policy).

REDIS_URL is read directly from :mod:`os.environ` rather than via
:func:`auxd_api.settings.get_settings` because :class:`WorkerSettings`
is evaluated at module-import time (arq's discovery mechanism). Going
through the full :class:`Settings` validator would also require
``SESSION_HMAC_KEY`` and ``TOKEN_ENCRYPTION_KEY`` to be set just to
import the module — which breaks CI's collection step. Job code that
needs the full settings stack should call ``get_settings()`` lazily
inside the job function.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Final

from arq import cron
from arq.connections import RedisSettings

from auxd_api.db import init_db
from auxd_api.modules.albums.workers import (
    reconcile_candidate_albums,
    refresh_stale_album_metadata,
)
from auxd_api.modules.users.workers import process_scheduled_deletions
from auxd_api.providers.musicbrainz import MusicBrainzCatalogProvider
from auxd_api.settings import get_settings
from auxd_api.workers.digest_dispatch import dispatch_weekly_digests
from auxd_api.workers.gdpr_export import generate_user_data_export
from auxd_api.workers.moderation_scan import scan_reports_for_flags

_LOGGER = logging.getLogger("auxd.worker")

_DEFAULT_REDIS_URL: Final[str] = "redis://localhost:6379/0"


async def noop_job(ctx: dict[str, Any]) -> str:
    """Trivial job used to validate the enqueue → dequeue → execute path.

    Emits a structured log line at INFO so an operator running
    ``fly logs --proc worker`` can confirm the worker is healthy after a
    deploy. Returns the literal string ``"ok"`` so arq's result store
    surfaces a non-trivial value the API process could read back.
    """
    _LOGGER.info(
        "worker.noop_job.executed",
        extra={
            "event": "worker.noop_job.executed",
            "job_id": ctx.get("job_id"),
            "enqueue_time": str(ctx.get("enqueue_time")),
        },
    )
    return "ok"


async def _on_startup(ctx: dict[str, Any]) -> None:
    """Initialise long-lived resources used by jobs.

    Sets up:

    * Beanie + Motor against ``MONGODB_URI`` so Document queries inside
      jobs Just Work without each job re-running ``init_beanie``.
    * A reusable :class:`MusicBrainzCatalogProvider` injected as
      ``ctx["mb_provider"]`` — both album workers share it (T064/T065).

    arq calls this once when the worker process boots; the matching
    teardown lives in :func:`_on_shutdown`.
    """
    settings = get_settings()
    await init_db(settings.MONGODB_URI)
    ctx["mb_provider"] = MusicBrainzCatalogProvider()


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    """Release long-lived resources from :func:`_on_startup`.

    Closes the MusicBrainz provider's httpx client so the worker exits
    cleanly. Mongo client teardown lives inside the db module and is
    triggered separately by arq's signal handler.
    """
    provider = ctx.pop("mb_provider", None)
    if provider is not None:
        await provider.aclose()


def _redis_settings_from_env() -> RedisSettings:
    """Build the worker's :class:`RedisSettings` from ``REDIS_URL``.

    Reads :envvar:`REDIS_URL` directly from :mod:`os.environ` (not via
    :func:`get_settings`) so module import does not require the
    encryption-key env vars to be set. Falls back to the same local
    default that :class:`Settings.REDIS_URL` would use.
    """
    return RedisSettings.from_dsn(os.environ.get("REDIS_URL", _DEFAULT_REDIS_URL))


class WorkerSettings:
    """arq's discovery surface — names every job and how to reach Redis.

    arq imports this class by dotted path (the CLI form is
    ``arq auxd_api.workers.main.WorkerSettings``) and uses it both to
    open the broker connection and to enumerate the callable jobs.
    Adding a new job means importing it and appending to
    :attr:`functions` — no other registration step.
    """

    functions = [
        noop_job,
        refresh_stale_album_metadata,
        reconcile_candidate_albums,
        process_scheduled_deletions,
        dispatch_weekly_digests,
        scan_reports_for_flags,
        generate_user_data_export,
    ]
    cron_jobs = [
        # T064 — daily 04:00 UTC album cache refresh.
        cron(
            refresh_stale_album_metadata,
            hour=4,
            minute=0,
            run_at_startup=False,
        ),
        # T065 — weekly Sunday 03:00 UTC MBID reconciliation.
        cron(
            reconcile_candidate_albums,
            weekday="sun",
            hour=3,
            minute=0,
            run_at_startup=False,
        ),
        # T058 — daily 02:00 UTC account-deletion cascade.
        cron(
            process_scheduled_deletions,
            hour=2,
            minute=0,
            run_at_startup=False,
        ),
        # T138 — weekly digest sweep. Runs every 5 minutes; the per-user
        # eligibility predicate (``_is_eligible_now``) filters to users
        # whose local Monday 09:00–09:04 window aligns with the current
        # invocation.
        cron(
            dispatch_weekly_digests,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=False,
        ),
        # T156 — daily 03:00 UTC moderation log-scan. Flags users with
        # >=3 reports in the trailing 7d.
        cron(
            scan_reports_for_flags,
            hour=3,
            minute=0,
            run_at_startup=False,
        ),
    ]
    redis_settings: RedisSettings = _redis_settings_from_env()
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    # Keep results for 10 minutes (arq default) — long enough for tests
    # and short enough that we don't accumulate cruft in Redis.
    keep_result = 600
