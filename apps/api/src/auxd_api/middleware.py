"""Session middleware (T019).

Wires the HMAC session cookie + CSRF double-submit cookie into the
FastAPI request lifecycle:

* On every request, decodes the session cookie and exposes the typed
  :class:`auxd_api.lib.sessions.Session` on ``request.state.session``
  (or ``None`` when the request is anonymous).
* On non-GET / non-HEAD / non-OPTIONS requests carrying a valid session,
  enforces the CSRF contract: the request must include the ``X-CSRF-Token``
  header AND its value must match the ``auxd_csrf`` cookie. Mismatches
  raise ``HTTP 403``.
* When the cookie is present-but-broken (tampered / expired / wrong
  signature), the middleware returns ``HTTP 401`` instead of silently
  treating the caller as anonymous. This avoids the trap where a
  weakened key rotation could fall back to anonymous mode for everyone.
* Sliding expiry: any decoded session with less than
  :data:`SESSION_REFRESH_THRESHOLD_SECONDS` of life left is re-issued
  on the response. The refresh path preserves the CSRF token so
  in-flight forms keep working.

Cookies are emitted with::

    HttpOnly; SameSite=Lax; Secure (when ENVIRONMENT != local); Path=/

``SameSite=Lax`` is the right default for a top-level site that mostly
sends top-level navigations + same-origin XHR; ``Strict`` would break
incoming OAuth redirects. The login flow is responsible for clearing
the cookie on logout (typically via a 200 response with an empty
``Set-Cookie``).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from auxd_api.lib.sessions import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    Session,
    create_session_token,
    decode_session,
    refresh_session_token,
)
from auxd_api.settings import Environment, get_settings

_LOGGER = logging.getLogger("auxd.middleware.sessions")

# Methods that bypass CSRF entirely — they are safe per RFC 9110 §9.2.1
# (read-only) and exercising CSRF on them produces false positives for
# any tool that prefetches links.
_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})


def _hmac_key_bytes() -> bytes:
    """Decode the configured base64 SESSION_HMAC_KEY into raw bytes.

    The settings layer enforces ``>=32 bytes after decode``, so this
    function never raises in normal operation.
    """
    return base64.b64decode(get_settings().SESSION_HMAC_KEY)


def _cookie_secure() -> bool:
    """``True`` outside ``local`` so cookies only travel over HTTPS in deploys."""
    return get_settings().ENVIRONMENT is not Environment.LOCAL


def _attach_session_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
    max_age: int,
) -> None:
    """Write both cookies onto ``response`` with the shared security flags.

    Cookies are host-scoped (no Domain= attribute) and the browser stores
    them against whatever host the response came from. With the Next.js
    rewrites pattern (frontend proxies ``/api/v1/*`` to the backend), the
    browser only sees the frontend origin so the cookie ends up first-party
    on the frontend host. No cross-subdomain Domain= sharing is needed.
    """
    secure = _cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        # JS must be able to read this cookie to populate the X-CSRF-Token
        # header — the entire point of the double-submit pattern.
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    """Issue empty cookies with Max-Age=0 to remove session state.

    Called by the logout handler (lands in a later task) to terminate
    the session on the response side. The next request will have no
    cookie and therefore no ``request.state.session``.
    """
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def issue_session(
    response: Response,
    *,
    user_id: str,
    session_version: int,
) -> str:
    """Mint a fresh session, attach the cookies, and return the CSRF token.

    Login handlers call this once the credential check has passed. The
    returned CSRF token is also written to the ``auxd_csrf`` cookie;
    callers may want to surface it in the response body (e.g., for
    SPA forms that read it eagerly without waiting for the next request).
    """
    token, csrf, _ = create_session_token(
        user_id=user_id,
        session_version=session_version,
        hmac_key=_hmac_key_bytes(),
    )
    _attach_session_cookies(
        response,
        session_token=token,
        csrf_token=csrf,
        max_age=SESSION_TTL_SECONDS,
    )
    return csrf


class SessionMiddleware(BaseHTTPMiddleware):
    """Validate session cookies + enforce CSRF on state-changing requests."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        session: Session | None = None
        if session_cookie:
            hmac_key = _hmac_key_bytes()
            session = decode_session(session_cookie, hmac_key=hmac_key)
            now = int(time.time())
            if session is None or session.is_expired(now):
                # Cookie was sent but is broken/expired. Refuse the
                # request — silently downgrading to anonymous would
                # hide HMAC-rotation regressions in prod.
                _LOGGER.info(
                    "session.invalid_cookie",
                    extra={
                        "event": "session.invalid_cookie",
                        "reason": "expired" if session and session.is_expired(now) else "tampered",
                    },
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "invalid_session",
                        "detail": "session cookie was rejected by the signature check",
                    },
                )

        # Expose the (possibly None) session to handlers.
        request.state.session = session

        # CSRF check — only enforced for state-changing methods AND only
        # when an authenticated session is present. Anonymous POSTs
        # (e.g., /login) are exempt by design; login CSRF is mitigated
        # by the SameSite=Lax cookie default.
        if session is not None and request.method not in _SAFE_METHODS:
            header_token = request.headers.get(CSRF_HEADER_NAME)
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            if not header_token or not cookie_token or header_token != cookie_token:
                _LOGGER.info(
                    "session.csrf_mismatch",
                    extra={
                        "event": "session.csrf_mismatch",
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_token_invalid",
                        "detail": (
                            "request must include matching X-CSRF-Token header and auxd_csrf cookie"
                        ),
                    },
                )

        response = await call_next(request)

        # Sliding expiry — re-issue when the session is closer to expiry
        # than the refresh threshold. We refresh on the response so the
        # new cookie is bundled with whatever the handler returned.
        if session is not None and session.needs_refresh():
            new_token, _ = refresh_session_token(session, hmac_key=_hmac_key_bytes())
            _attach_session_cookies(
                response,
                session_token=new_token,
                csrf_token=session.csrf_token,
                max_age=SESSION_TTL_SECONDS,
            )

        return response


__all__ = [
    "SessionMiddleware",
    "clear_session_cookies",
    "issue_session",
]
