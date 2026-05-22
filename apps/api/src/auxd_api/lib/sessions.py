"""HMAC-signed session tokens (T019).

T019 owns the encode/decode primitives used by the session middleware
(:mod:`auxd_api.middleware`). The token format is deliberately small:

    base64url(payload) . base64url(hmac_sha256(payload))

where ``payload`` is a UTF-8 JSON document::

    {
        "u":  user_id (str)         # KSUID
        "c":  csrf_token (str)      # 22-char base64url, 16 random bytes
        "i":  issued_at (int, UTC unix seconds)
        "e":  expires_at (int, UTC unix seconds)
        "v":  session_version (int) # bumped on logout / password change
    }

Self-contained signed tokens avoid a server-side session store at the
cost of size (~250 bytes). Sliding expiry is achieved by re-issuing the
token whenever the middleware sees the remaining lifetime drop below
:data:`SESSION_REFRESH_THRESHOLD_SECONDS`.

Constant-time signature comparison (``hmac.compare_digest``) protects
against timing oracles on the validation path. Every error path returns
``None`` rather than raising so the middleware can treat decode failures
as "no valid session" without try/except boilerplate.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Final

# 30 days — matches the tasks.md T019 spec for sliding expiry.
SESSION_TTL_SECONDS: Final[int] = 30 * 24 * 60 * 60

# Re-issue the cookie whenever it has less than 7 days left. The 7-day
# value is chosen so a user who logs in once a week stays logged in
# indefinitely without renewing on every request (which would flood the
# Set-Cookie header).
SESSION_REFRESH_THRESHOLD_SECONDS: Final[int] = 7 * 24 * 60 * 60

# Cookie names — kept short to fit in the 4kB cookie budget alongside
# any future analytics cookies.
SESSION_COOKIE_NAME: Final[str] = "auxd_session"
CSRF_COOKIE_NAME: Final[str] = "auxd_csrf"
CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"


@dataclass(frozen=True, slots=True)
class Session:
    """Decoded session payload."""

    user_id: str
    csrf_token: str
    issued_at: int
    expires_at: int
    session_version: int

    def is_expired(self, now: int | None = None) -> bool:
        return self.expires_at <= (now if now is not None else int(time.time()))

    def needs_refresh(self, now: int | None = None) -> bool:
        """True when the session is closer to expiry than the refresh threshold."""
        now = now if now is not None else int(time.time())
        return (self.expires_at - now) < SESSION_REFRESH_THRESHOLD_SECONDS


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 with no padding — keeps the cookie ASCII-safe."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def generate_csrf_token() -> str:
    """Return a fresh 16-byte CSRF token, base64url-encoded."""
    return _b64url_encode(secrets.token_bytes(16))


def encode_session(
    *,
    user_id: str,
    csrf_token: str,
    issued_at: int,
    expires_at: int,
    session_version: int,
    hmac_key: bytes,
) -> str:
    """Return the wire-format session token.

    The HMAC is computed over the URL-safe base64 *envelope* of the
    JSON payload, not the raw JSON, so the signing input is a single
    ASCII string that survives any whitespace re-encoding by an
    intermediary.
    """
    payload = {
        "u": user_id,
        "c": csrf_token,
        "i": issued_at,
        "e": expires_at,
        "v": session_version,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64url_encode(raw)
    signature = hmac.new(hmac_key, body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(signature)}"


def decode_session(token: str, *, hmac_key: bytes) -> Session | None:
    """Verify the HMAC and decode the payload.

    Returns ``None`` on any failure (wrong shape, bad signature,
    malformed JSON, missing fields, wrong types). The caller is expected
    to also check expiry via :meth:`Session.is_expired`.
    """
    if not token or token.count(".") != 1:
        return None
    body, sig_b64 = token.split(".", 1)
    try:
        expected_sig = hmac.new(hmac_key, body.encode("ascii"), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
    except (ValueError, UnicodeEncodeError):
        return None
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return Session(
            user_id=str(payload["u"]),
            csrf_token=str(payload["c"]),
            issued_at=int(payload["i"]),
            expires_at=int(payload["e"]),
            session_version=int(payload["v"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def create_session_token(
    *,
    user_id: str,
    session_version: int,
    hmac_key: bytes,
    now: int | None = None,
) -> tuple[str, str, int]:
    """Mint a fresh session token + CSRF token.

    Returns ``(token, csrf_token, expires_at)`` so the caller can attach
    both cookies and report the expiry to clients that care (rare —
    browsers handle cookie expiry transparently via ``Max-Age``).
    """
    now = now if now is not None else int(time.time())
    csrf = generate_csrf_token()
    expires_at = now + SESSION_TTL_SECONDS
    token = encode_session(
        user_id=user_id,
        csrf_token=csrf,
        issued_at=now,
        expires_at=expires_at,
        session_version=session_version,
        hmac_key=hmac_key,
    )
    return token, csrf, expires_at


def refresh_session_token(
    session: Session,
    *,
    hmac_key: bytes,
    now: int | None = None,
) -> tuple[str, int]:
    """Re-issue the same session with a fresh ``expires_at``.

    Preserves the CSRF token and the session version — only the lifetime
    is extended. Returns ``(token, expires_at)``.
    """
    now = now if now is not None else int(time.time())
    expires_at = now + SESSION_TTL_SECONDS
    token = encode_session(
        user_id=session.user_id,
        csrf_token=session.csrf_token,
        issued_at=session.issued_at,
        expires_at=expires_at,
        session_version=session.session_version,
        hmac_key=hmac_key,
    )
    return token, expires_at


__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "SESSION_COOKIE_NAME",
    "SESSION_REFRESH_THRESHOLD_SECONDS",
    "SESSION_TTL_SECONDS",
    "Session",
    "create_session_token",
    "decode_session",
    "encode_session",
    "generate_csrf_token",
    "refresh_session_token",
]
