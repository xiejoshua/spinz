"""Unit tests for :mod:`auxd_api.lib.auth_tokens` (feature 002-auth-email-flows).

Covers the token primitive contract:

* :func:`generate_token` produces high-entropy URL-safe raw secrets +
  matching hashes; each call is unique.
* :func:`hash_token` is deterministic for a given pepper and pepper-
  sensitive (a different pepper produces a different hash).
* :func:`verify_token` returns ``True`` for matching pairs, ``False`` for
  mismatches, and uses constant-time compare (verified structurally —
  malformed-but-same-length input returns ``False`` without raising).
"""

from __future__ import annotations

import base64
import secrets
import string
from collections.abc import Iterator
from typing import Any

import pytest

from auxd_api import settings as settings_module
from auxd_api.lib.auth_tokens import (
    TOKEN_BYTES,
    generate_token,
    hash_token,
    verify_token,
)


def _b64(num_bytes: int) -> str:
    return base64.b64encode(secrets.token_bytes(num_bytes)).decode("ascii")


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    """Set a known AUTH_TOKEN_PEPPER for deterministic hashing in tests."""
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "AUTH_TOKEN_PEPPER",
        "ENVIRONMENT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# generate_token
# ---------------------------------------------------------------------------


def test_generate_token_returns_url_safe_high_entropy_raw(_clean_env: None) -> None:
    """The raw token is URL-safe base64 of ``TOKEN_BYTES`` bytes (~43 chars).

    secrets.token_urlsafe(32) yields ceil(32 * 4 / 3) = 43 base64-url chars
    minus any '=' padding, so it lands at exactly 43 chars.
    """
    raw, _ = generate_token()
    # 256-bit entropy → ~43 URL-safe chars. Plan §11 calls out ≥40.
    assert len(raw) >= 40
    # URL-safe base64 alphabet (RFC 4648 §5) is letters + digits + - and _.
    allowed = set(string.ascii_letters + string.digits + "-_")
    assert set(raw).issubset(allowed), f"raw token contained non-URL-safe chars: {raw!r}"
    # token_urlsafe never includes padding.
    assert "=" not in raw
    # The constant is the source of truth for the byte budget.
    assert TOKEN_BYTES == 32


def test_generate_token_returns_unique_raw_and_hash(_clean_env: None) -> None:
    """Two calls produce different raw tokens AND different hashes."""
    raw_a, hash_a = generate_token()
    raw_b, hash_b = generate_token()
    assert raw_a != raw_b
    assert hash_a != hash_b


def test_generate_token_hash_matches_hash_token(_clean_env: None) -> None:
    """The returned hash equals ``hash_token(raw)`` — single source of truth."""
    raw, returned_hash = generate_token()
    assert returned_hash == hash_token(raw)


# ---------------------------------------------------------------------------
# hash_token
# ---------------------------------------------------------------------------


def test_hash_token_is_deterministic(_clean_env: None) -> None:
    """Same input + same pepper → same hash, byte-for-byte."""
    raw, _ = generate_token()
    first = hash_token(raw)
    second = hash_token(raw)
    assert first == second
    # SHA-256 produces 64 hex chars.
    assert len(first) == 64
    assert all(ch in "0123456789abcdef" for ch in first)


def test_hash_token_is_sensitive_to_pepper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Different pepper → different hash for the same raw token.

    Pepper is loaded fresh on every call via the lru_cached
    :func:`get_settings`, so flipping it requires bouncing the cache.
    """
    for key in (
        "SESSION_HMAC_KEY",
        "TOKEN_ENCRYPTION_KEY",
        "AUTH_TOKEN_PEPPER",
        "ENVIRONMENT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_HMAC_KEY", _b64(32))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _b64(32))
    monkeypatch.setenv("ENVIRONMENT", "local")

    pepper_a = _b64(32)
    pepper_b = _b64(32)
    assert pepper_a != pepper_b  # sanity

    raw = "static-raw-token-for-this-test"

    monkeypatch.setenv("AUTH_TOKEN_PEPPER", pepper_a)
    settings_module.get_settings.cache_clear()
    hash_under_a = hash_token(raw)

    monkeypatch.setenv("AUTH_TOKEN_PEPPER", pepper_b)
    settings_module.get_settings.cache_clear()
    hash_under_b = hash_token(raw)

    assert hash_under_a != hash_under_b
    settings_module.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# verify_token
# ---------------------------------------------------------------------------


def test_verify_token_accepts_matching_pair(_clean_env: None) -> None:
    raw, hashed = generate_token()
    assert verify_token(raw, hashed) is True


def test_verify_token_rejects_mismatched_pair(_clean_env: None) -> None:
    raw_a, _ = generate_token()
    _, hash_b = generate_token()
    assert verify_token(raw_a, hash_b) is False


def test_verify_token_rejects_corrupted_raw(_clean_env: None) -> None:
    """A single-char-mutated raw fails verification."""
    raw, hashed = generate_token()
    # Flip the last character to a different URL-safe char.
    mutated = raw[:-1] + ("A" if raw[-1] != "A" else "B")
    assert verify_token(mutated, hashed) is False


def test_verify_token_constant_time_path_handles_malformed_input(
    _clean_env: None,
) -> None:
    """Same-length malformed input returns ``False`` without raising.

    ``secrets.compare_digest`` requires both arguments to be the same
    type and length to operate in constant time. We feed it a same-
    length hex string that is NOT a real hash; verify_token should
    re-hash + compare and return ``False`` cleanly.
    """
    raw = "definitely-not-a-real-token"
    bogus_hash = "0" * 64  # 64 hex chars, never matches a real SHA-256 digest.
    # No exception raised — and never claims a match.
    result = verify_token(raw, bogus_hash)
    assert result is False


def test_verify_token_rejects_empty_strings(_clean_env: None) -> None:
    """Empty raw / empty hash never accidentally validates."""
    assert verify_token("", "") is False
    raw, hashed = generate_token()
    assert verify_token("", hashed) is False
    assert verify_token(raw, "") is False
