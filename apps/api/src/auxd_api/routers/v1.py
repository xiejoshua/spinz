"""Aggregator for the ``/api/v1`` surface (T011 scaffold).

Feature modules contribute their own routers via ``include_router`` so
that every endpoint shares a common prefix, tag namespace, and any
future version-wide dependencies (auth, rate-limit, ...). The aggregator
itself is mounted by :mod:`auxd_api.main` at the application root.

Mounted feature routers:

* ``/api/v1/albums/{album_id}`` (T067) — album detail with visibility
  filtering, edition aggregation, and friends/public-reviews rollup.
* ``/api/v1/search`` (T069) — three-tier search (Atlas + MusicBrainz +
  Discogs fallback merge).
"""

from __future__ import annotations

from fastapi import APIRouter

from auxd_api.modules.albums.routes import router as albums_router
from auxd_api.modules.search.routes import router as search_router

router = APIRouter(prefix="/api/v1")
router.include_router(albums_router)
router.include_router(search_router)

__all__ = ["router"]
