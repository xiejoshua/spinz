"""Unit tests for :mod:`auxd_api.lib.secrets`."""

from __future__ import annotations

import base64
import secrets

import pytest

from auxd_api.lib.secrets import (
    DecryptionError,
    MissingKeyError,
    SecretsError,
    TokenEncryptor,
)


def _new_key_b64() -> str:
    """Return a fresh standard-base64-encoded 32-byte key."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def test_from_base64_roundtrip() -> None:
    """A round-trip through encrypt/decrypt returns the original plaintext.

    CR-001: example plaintext switched from a Spotify-flavored exemplar
    to a generic provider OAuth token string.
    """
    enc = TokenEncryptor.from_base64_strings([_new_key_b64()])
    plaintext = "a-provider-oauth-access-token-value"
    ciphertext = enc.encrypt(plaintext)
    assert ciphertext != plaintext
    assert enc.decrypt(ciphertext) == plaintext


def test_empty_keys_list_raises_missing_key() -> None:
    """Constructing from an empty list of base64 keys raises ``MissingKeyError``."""
    with pytest.raises(MissingKeyError):
        TokenEncryptor.from_base64_strings([])


def test_empty_keys_tuple_raises_missing_key() -> None:
    """Direct construction with an empty tuple also raises ``MissingKeyError``."""
    with pytest.raises(MissingKeyError):
        TokenEncryptor(keys=())


def test_wrong_length_key_raises() -> None:
    """A base64 string that decodes to 31 or 33 bytes is rejected."""
    too_short = base64.b64encode(secrets.token_bytes(31)).decode("ascii")
    too_long = base64.b64encode(secrets.token_bytes(33)).decode("ascii")
    with pytest.raises(SecretsError):
        TokenEncryptor.from_base64_strings([too_short])
    with pytest.raises(SecretsError):
        TokenEncryptor.from_base64_strings([too_long])


def test_bad_base64_input_raises() -> None:
    """A string that is not valid standard base64 raises ``SecretsError``."""
    with pytest.raises(SecretsError):
        TokenEncryptor.from_base64_strings(["not-valid-base64-!@#"])


def test_unicode_plaintext_roundtrip() -> None:
    """Non-ASCII plaintext round-trips correctly through utf-8."""
    enc = TokenEncryptor.from_base64_strings([_new_key_b64()])
    plaintext = "héllo 🌍 — tokens with accents and emoji"
    assert enc.decrypt(enc.encrypt(plaintext)) == plaintext


def test_decrypt_invalid_ciphertext_raises_decryption_error() -> None:
    """An arbitrary non-Fernet string fails decryption as ``DecryptionError``."""
    enc = TokenEncryptor.from_base64_strings([_new_key_b64()])
    with pytest.raises(DecryptionError):
        enc.decrypt("this-is-not-a-fernet-token")


def test_decrypt_tampered_ciphertext_raises() -> None:
    """Flipping a single byte in the ciphertext causes HMAC validation to fail."""
    enc = TokenEncryptor.from_base64_strings([_new_key_b64()])
    ciphertext = enc.encrypt("sensitive-token")
    # Flip a character somewhere in the middle to avoid touching the version
    # prefix; this corrupts either the IV, body, or HMAC and must fail auth.
    idx = len(ciphertext) // 2
    flipped_char = "A" if ciphertext[idx] != "A" else "B"
    tampered = ciphertext[:idx] + flipped_char + ciphertext[idx + 1 :]
    assert tampered != ciphertext
    with pytest.raises(DecryptionError):
        enc.decrypt(tampered)


def test_rotate_to_decrypts_old_ciphertext() -> None:
    """After rotation, old ciphertexts still decrypt; new ciphertexts use the new key."""
    key_a_b64 = _new_key_b64()
    key_b_b64 = _new_key_b64()

    enc_a = TokenEncryptor.from_base64_strings([key_a_b64])
    old_ciphertext = enc_a.encrypt("legacy-token")

    rotated = enc_a.rotate_to(key_b_b64)

    # Old ciphertext is still readable through the rotation tail.
    assert rotated.decrypt(old_ciphertext) == "legacy-token"

    # New ciphertext is produced with key B; an A-only encryptor cannot read it.
    new_ciphertext = rotated.encrypt("fresh-token")
    a_only = TokenEncryptor.from_base64_strings([key_a_b64])
    with pytest.raises(DecryptionError):
        a_only.decrypt(new_ciphertext)

    # But a B-only encryptor can.
    b_only = TokenEncryptor.from_base64_strings([key_b_b64])
    assert b_only.decrypt(new_ciphertext) == "fresh-token"


def test_rotate_to_preserves_existing_keys() -> None:
    """``rotate_to`` returns an encryptor whose key tuple is [new, *old]."""
    key_a_b64 = _new_key_b64()
    key_b_b64 = _new_key_b64()
    key_c_b64 = _new_key_b64()

    enc = TokenEncryptor.from_base64_strings([key_a_b64, key_b_b64])
    rotated = enc.rotate_to(key_c_b64)

    expected = (
        base64.b64decode(key_c_b64),
        base64.b64decode(key_a_b64),
        base64.b64decode(key_b_b64),
    )
    assert rotated.keys == expected


def test_two_keys_decrypt_either() -> None:
    """An encryptor with two keys decrypts ciphertexts produced by either."""
    key_a_b64 = _new_key_b64()
    key_b_b64 = _new_key_b64()

    enc_a = TokenEncryptor.from_base64_strings([key_a_b64])
    enc_b = TokenEncryptor.from_base64_strings([key_b_b64])
    both = TokenEncryptor.from_base64_strings([key_a_b64, key_b_b64])

    ct_from_a = enc_a.encrypt("from-a")
    ct_from_b = enc_b.encrypt("from-b")

    assert both.decrypt(ct_from_a) == "from-a"
    assert both.decrypt(ct_from_b) == "from-b"
