"""Aggregator for the ``/api/v1`` surface (T011 scaffold).

Feature modules contribute their own routers via ``include_router`` so
that every endpoint shares a common prefix, tag namespace, and any
future version-wide dependencies (auth, rate-limit, ...). The aggregator
itself is mounted by :mod:`auxd_api.main` at the application root.

Mounted feature routers:

* ``/api/v1/albums/{album_id}`` (T067) — album detail with visibility
  filtering, edition aggregation, and friends/public-reviews rollup.
* ``/api/v1/auth/...`` (T053, T059) — email/password signup, login,
  logout, logout-all-devices.
* ``/api/v1/reports/missing-album`` (T053a) — anonymous + authenticated
  missing-album reports from the manual-search empty state.
* ``/api/v1/search`` (T069) — three-tier search (Atlas + MusicBrainz +
  Discogs fallback merge).
* ``/api/v1/users/me/...`` (T057, T058) — handle change, account
  deletion schedule + cancel.
"""

from __future__ import annotations

from fastapi import APIRouter

from auxd_api.modules.albums.routes import router as albums_router
from auxd_api.modules.auth.routes import router as auth_router
from auxd_api.modules.reports.routes import router as reports_router
from auxd_api.modules.search.routes import router as search_router
from auxd_api.modules.users.routes import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(albums_router)
router.include_router(auth_router)
router.include_router(reports_router)
router.include_router(search_router)
router.include_router(users_router)

__all__ = ["router"]
