"""arq worker entry point (T013 scaffold).

Run with::

    uv run arq auxd_api.workers.main.WorkerSettings

The arq worker connects to Redis using :class:`Settings.REDIS_URL`,
pulls jobs enqueued by the API process via
:func:`auxd_api.redis_client.enqueue_job`, and executes them
sequentially per the arq job model.

At T013 the worker registers a single :func:`noop_job` so the
end-to-end pipeline (API enqueue → worker dequeue → log line) can be
verified before downstream tasks add real jobs (GDPR export, weekly
digest, just-finished detection, suggested-follows recompute — plan
§8.4).
"""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from auxd_api.settings import get_settings

_LOGGER = logging.getLogger("auxd.worker")


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


def _redis_settings_from_env() -> RedisSettings:
    """Build the worker's :class:`RedisSettings` from the standard settings."""
    return RedisSettings.from_dsn(get_settings().REDIS_URL)


class WorkerSettings:
    """arq's discovery surface — names every job and how to reach Redis.

    arq imports this class by dotted path (the CLI form is
    ``arq auxd_api.workers.main.WorkerSettings``) and uses it both to
    open the broker connection and to enumerate the callable jobs.
    Adding a new job means importing it and appending to
    :attr:`functions` — no other registration step.
    """

    functions = [noop_job]
    redis_settings: RedisSettings = _redis_settings_from_env()
    # Keep results for 10 minutes (arq default) — long enough for tests
    # and short enough that we don't accumulate cruft in Redis.
    keep_result = 600
