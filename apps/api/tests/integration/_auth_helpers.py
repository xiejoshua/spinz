"""Shared FastAPI auth-bridge middleware for integration tests.

Centralises the ``_FakeAuthMiddleware`` pattern that — pre-REV-202 — was
copy-pasted across ~26 integration-test modules. Each copy did the same
thing: read an ``X-User-Id`` header, build a :class:`Session` with
test-shaped fields, and attach it to ``request.state.session``. When the
real session schema changes, the duplication forces a 26-way edit.

Tests use this module by importing :class:`FakeAuthMiddleware` (the
public name) and registering it on the app under test::

    from tests.integration._auth_helpers import FakeAuthMiddleware

    def _make_app() -> FastAPI:
        app = FastAPI()
        app.add_middleware(FakeAuthMiddleware)
        ...

Tests that need a non-default session shape (e.g. a 1-hour expiry to
exercise refresh logic, a non-default ``session_version``, a different
``csrf_token``) construct the class with a custom ``session_factory``::

    def _short_expiry(user_id: str) -> Session:
        return Session(
            user_id=user_id,
            csrf_token="test-csrf",
            issued_at=0,
            expires_at=int(datetime.now(UTC).timestamp()) + 3600,
            session_version=1,
        )

    app.add_middleware(FakeAuthMiddleware, session_factory=_short_expiry)

The default factory matches the historical 26-file shape (1-day expiry,
``csrf_token="test-csrf"``, ``session_version=1``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from auxd_api.lib.sessions import Session

SessionFactory = Callable[[str], Session]


def _default_session_factory(user_id: str) -> Session:
    """Build a :class:`Session` with the historical default shape.

    Mirrors what ~26 copies of ``_FakeAuthMiddleware`` did inline:
    fresh CSRF token, ``issued_at=0`` epoch, 1-day expiry,
    ``session_version=1``.
    """
    return Session(
        user_id=user_id,
        csrf_token="test-csrf",
        issued_at=0,
        expires_at=int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
        session_version=1,
    )


class FakeAuthMiddleware(BaseHTTPMiddleware):
    """Reads ``X-User-Id`` and injects a fake :class:`Session` into ``request.state``.

    Shared across integration tests to avoid 26-way duplication of the
    same boilerplate (REV-202 from Phase 6B code review). When the
    header is absent ``request.state.session`` is set to ``None`` so the
    route's auth dependency raises 401 — matching the production
    middleware's contract.

    Override the session shape per-app by passing ``session_factory``::

        app.add_middleware(FakeAuthMiddleware, session_factory=my_factory)
    """

    def __init__(
        self,
        app: ASGIApp,
        session_factory: SessionFactory = _default_session_factory,
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            request.state.session = self._session_factory(user_id)
        else:
            request.state.session = None
        return await call_next(request)


__all__ = ["FakeAuthMiddleware", "SessionFactory"]
