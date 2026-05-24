"""Token primitive for verify-email + password-reset flows.

Single import surface so both flows use identical crypto. The raw token
is what the user sees (in their email link); the hash is what we
persist (in the database). Pepper raises the cost of an offline attack
against a leaked token table.

Threat model
============
* **Raw token entropy.** ``secrets.token_urlsafe(32)`` yields a 256-bit
  cryptographically-random secret encoded as ~43 base64url characters.
  Online brute-force against the verify/reset endpoints is bounded by
  per-IP rate limits; offline brute-force against the hash column would
  require ~2^128 hash evaluations (SHA-256 with a server-only pepper).
* **Server pepper.** Stored in ``AUTH_TOKEN_PEPPER`` env var. Validated
  at boot to decode to >=32 bytes. Operator MUST provision + rotate
  independently of ``SESSION_HMAC_KEY`` — they protect different
  primitives.
* **Constant-time compare.** :func:`verify_token` uses
  :func:`secrets.compare_digest` to defeat hash-comparison timing
  oracles; even though the hash is non-secret, the discipline costs
  nothing.

Public surface
==============
* :func:`generate_token` — return ``(raw, hash)``. Raw → email; hash → DB.
* :func:`hash_token` — re-hash a raw token (used by lookup paths).
* :func:`verify_token` — constant-time compare between raw + stored hash.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Final

from auxd_api.settings import get_settings

# 256-bit secret; URL-safe base64 → ~43 chars. token_urlsafe(N) returns
# ceil(N*4/3) base64 chars (minus padding), so 32 → 43 characters.
TOKEN_BYTES: Final[int] = 32


def generate_token() -> tuple[str, str]:
    """Return ``(raw_token, token_hash)`` for a fresh single-use secret.

    The raw token is the value that goes into the email payload (link
    fragment); the hash is what's persisted in the database. Both are
    returned in one shot so callers can't accidentally drift the two
    apart.
    """
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    """Return ``SHA-256(raw + pepper)`` as a lowercase hex string.

    Deterministic — the same raw token always hashes to the same value,
    so a lookup path can re-hash an inbound token and find the matching
    row by ``token_hash``. The pepper is loaded fresh on every call
    (cheap; :func:`get_settings` is ``lru_cache``'d) so rotation can be
    rolled out by changing the env var without touching this module.

    Args:
        raw: The URL-safe base64 secret as returned by
            :func:`generate_token`.

    Returns:
        Lowercase hex SHA-256 digest, 64 chars long.
    """
    pepper = get_settings().AUTH_TOKEN_PEPPER
    return hashlib.sha256((raw + pepper).encode("utf-8")).hexdigest()


def verify_token(raw: str, expected_hash: str) -> bool:
    """Constant-time compare a raw token against a stored hash.

    Args:
        raw: Raw token as supplied by the caller (e.g. from the URL).
        expected_hash: Hash previously persisted via :func:`hash_token`.

    Returns:
        ``True`` iff ``hash_token(raw) == expected_hash`` under a
        constant-time comparison.
    """
    return secrets.compare_digest(hash_token(raw), expected_hash)


__all__ = [
    "TOKEN_BYTES",
    "generate_token",
    "hash_token",
    "verify_token",
]
