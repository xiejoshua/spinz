"""Background workers for the auxd API.

The arq worker process imports :class:`auxd_api.workers.main.WorkerSettings`
to enumerate the jobs it can run. Routes in :mod:`auxd_api` use
:func:`auxd_api.redis_client.enqueue_job` to push work onto the queue;
the worker pulls and executes it from the same Redis broker.
"""
