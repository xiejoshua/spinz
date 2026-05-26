"""Shared FastAPI dependency helpers.

Currently holds the MB-mirror service injector. Lives outside of any
specific module because the mirror is consumed by several routers
(search, albums) and putting the helper inside any one of them would
create a coupling cycle.

Add other cross-cutting Depends helpers here as they accumulate.
"""

from __future__ import annotations

from fastapi import Request

from auxd_api.modules.mb_mirror.service import AlbumMirrorService


def get_mirror_service(request: Request) -> AlbumMirrorService:
    """Return the process-wide MB-mirror service, wrapping the long-lived
    Turso client opened at app startup.

    The :class:`AlbumMirrorService` constructor accepts ``None`` for the
    underlying client and degrades cleanly when the mirror is disabled
    (``TURSO_DATABASE_URL`` unset), so this helper always returns a
    usable instance — callers don't need to branch on configuration.
    Each request gets a fresh service wrapping the shared client; the
    client itself owns the httpx connection pool and is reused.

    Use via ``Depends`` in route signatures::

        @router.get(...)
        async def my_route(
            mirror: Annotated[AlbumMirrorService, Depends(get_mirror_service)],
        ) -> ...:
            row = await mirror.find_by_mbid(some_mbid)
    """
    client = getattr(request.app.state, "mirror_client", None)
    return AlbumMirrorService(client)


__all__ = ["get_mirror_service"]
