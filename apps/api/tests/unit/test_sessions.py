"""Unit tests for :mod:`auxd_api.lib.sessions` (T019).

Covers the encode/decode round-trip, signature tamper detection, expiry
+ refresh helpers, and the CSRF token generator.
"""

from __future__ import annotations

import secrets
import time

import pytest

from auxd_api.lib.sessions import (
    SESSION_REFRESH_THRESHOLD_SECONDS,
    SESSION_TTL_SECONDS,
    Session,
    create_session_token,
    decode_session,
    encode_session,
    generate_csrf_token,
    refresh_session_token,
)


@pytest.fixture
def hmac_key() -> bytes:
    return secrets.token_bytes(32)


def test_round_trip_preserves_all_fields(hmac_key: bytes) -> None:
    now = int(time.time())
    token = encode_session(
        user_id="u-abc",
        csrf_token="csrf-xyz",
        issued_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
        session_version=7,
        hmac_key=hmac_key,
    )
    decoded = decode_session(token, hmac_key=hmac_key)
    assert decoded is not None
    assert decoded.user_id == "u-abc"
    assert decoded.csrf_token == "csrf-xyz"
    assert decoded.issued_at == now
    assert decoded.expires_at == now + SESSION_TTL_SECONDS
    assert decoded.session_version == 7


def test_decode_rejects_tampered_payload(hmac_key: bytes) -> None:
    now = int(time.time())
    token = encode_session(
        user_id="alice",
        csrf_token="c",
        issued_at=now,
        expires_at=now + 100,
        session_version=1,
        hmac_key=hmac_key,
    )
    body, sig = token.split(".", 1)
    # Flip one byte in the body — any single-byte change should fail HMAC.
    altered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    assert decode_session(f"{altered_body}.{sig}", hmac_key=hmac_key) is None


def test_decode_rejects_tampered_signature(hmac_key: bytes) -> None:
    now = int(time.time())
    token = encode_session(
        user_id="alice",
        csrf_token="c",
        issued_at=now,
        expires_at=now + 100,
        session_version=1,
        hmac_key=hmac_key,
    )
    body, _sig = token.split(".", 1)
    # Replace the entire signature with all-A's of the right length. Flipping
    # a single base64 character can land on padding-bits that decode to the
    # same byte sequence; a full replacement guarantees a different HMAC.
    altered_sig = "A" * 43
    assert decode_session(f"{body}.{altered_sig}", hmac_key=hmac_key) is None


def test_decode_rejects_token_signed_with_different_key(hmac_key: bytes) -> None:
    now = int(time.time())
    token = encode_session(
        user_id="alice",
        csrf_token="c",
        issued_at=now,
        expires_at=now + 100,
        session_version=1,
        hmac_key=hmac_key,
    )
    other_key = secrets.token_bytes(32)
    assert decode_session(token, hmac_key=other_key) is None


@pytest.mark.parametrize("bogus", ["", "no-dot", "a.b.c", "garbage"])
def test_decode_rejects_malformed_tokens(bogus: str, hmac_key: bytes) -> None:
    assert decode_session(bogus, hmac_key=hmac_key) is None


def test_session_is_expired_threshold() -> None:
    now = 1_000_000
    not_yet = Session(
        user_id="u",
        csrf_token="c",
        issued_at=now - 10,
        expires_at=now + 1,
        session_version=1,
    )
    expired = Session(
        user_id="u",
        csrf_token="c",
        issued_at=now - 10,
        expires_at=now,
        session_version=1,
    )
    assert not not_yet.is_expired(now=now)
    assert expired.is_expired(now=now)


def test_session_needs_refresh_threshold() -> None:
    now = 1_000_000
    fresh = Session(
        user_id="u",
        csrf_token="c",
        issued_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
        session_version=1,
    )
    nearly = Session(
        user_id="u",
        csrf_token="c",
        issued_at=now - (SESSION_TTL_SECONDS - SESSION_REFRESH_THRESHOLD_SECONDS) - 1,
        expires_at=now + (SESSION_REFRESH_THRESHOLD_SECONDS - 1),
        session_version=1,
    )
    assert not fresh.needs_refresh(now=now)
    assert nearly.needs_refresh(now=now)


def test_create_session_token_includes_csrf_and_expiry(hmac_key: bytes) -> None:
    now = 1_000_000
    token, csrf, expires_at = create_session_token(
        user_id="alice",
        session_version=3,
        hmac_key=hmac_key,
        now=now,
    )
    assert expires_at == now + SESSION_TTL_SECONDS
    decoded = decode_session(token, hmac_key=hmac_key)
    assert decoded is not None
    assert decoded.user_id == "alice"
    assert decoded.session_version == 3
    assert decoded.csrf_token == csrf
    assert decoded.expires_at == expires_at


def test_refresh_session_token_extends_expiry_only(hmac_key: bytes) -> None:
    now = 1_000_000
    token, csrf, _ = create_session_token(
        user_id="bob",
        session_version=4,
        hmac_key=hmac_key,
        now=now,
    )
    original = decode_session(token, hmac_key=hmac_key)
    assert original is not None

    later = now + 1000
    refreshed_token, expires_at = refresh_session_token(original, hmac_key=hmac_key, now=later)
    refreshed = decode_session(refreshed_token, hmac_key=hmac_key)
    assert refreshed is not None
    assert refreshed.user_id == original.user_id
    assert refreshed.csrf_token == original.csrf_token  # preserved
    assert refreshed.session_version == original.session_version
    assert refreshed.issued_at == original.issued_at  # NOT bumped
    assert refreshed.expires_at == later + SESSION_TTL_SECONDS == expires_at


def test_generate_csrf_token_is_unique() -> None:
    tokens = {generate_csrf_token() for _ in range(100)}
    assert len(tokens) == 100
