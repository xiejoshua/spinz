"""arq worker entry point (T013 scaffold).

Run with::

    uv run arq auxd_api.workers.main.WorkerSettings

The arq worker connects to Redis using ``REDIS_URL`` from the
environment, pulls jobs enqueued by the API process via
:func:`auxd_api.redis_client.enqueue_job`, and executes them
sequentially per the arq job model.

At T013 the worker registers a single :func:`noop_job` so the
end-to-end pipeline (API enqueue → worker dequeue → log line) can be
verified before downstream tasks add real jobs (GDPR export, weekly
digest, just-finished detection, suggested-follows recompute — plan
§8.4).

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

from arq.connections import RedisSettings

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

    functions = [noop_job]
    redis_settings: RedisSettings = _redis_settings_from_env()
    # Keep results for 10 minutes (arq default) — long enough for tests
    # and short enough that we don't accumulate cruft in Redis.
    keep_result = 600
