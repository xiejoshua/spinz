"""Aggregator for the ``/api/v1`` surface (T011 scaffold).

Feature modules contribute their own routers via ``include_router`` so
that every endpoint shares a common prefix, tag namespace, and any
future version-wide dependencies (auth, rate-limit, ...). The aggregator
itself is mounted by :mod:`auxd_api.main` at the application root.

At T011 the router is intentionally empty — endpoints are wired in
later clusters (auth in T030s, social in T100s, ...). An OpenAPI client
that hits ``/openapi.json`` still sees the ``/api/v1`` namespace so the
T028 codegen pipeline has something concrete to consume.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

__all__ = ["router"]
