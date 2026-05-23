"""Unit tests for :mod:`auxd_api.modules.auth.password` (T053)."""

from __future__ import annotations

import pytest

from auxd_api.modules.auth.password import (
    InvalidPasswordHashError,
    hash_password,
    verify_password,
)


def test_hash_password_produces_argon2_prefix() -> None:
    """argon2-cffi always emits hashes prefixed with ``$argon2``."""
    digest = hash_password("correct-horse-battery-staple-9")
    assert digest.startswith("$argon2")


def test_hash_password_is_salted() -> None:
    """Same input twice ⇒ different hashes (proves the salt is per-call)."""
    a = hash_password("identical-password-9")
    b = hash_password("identical-password-9")
    assert a != b


def test_verify_password_matches_correct_input() -> None:
    digest = hash_password("the-truth-9")
    assert verify_password("the-truth-9", digest) is True


def test_verify_password_rejects_wrong_input() -> None:
    digest = hash_password("the-truth-9")
    assert verify_password("not-the-truth-9", digest) is False


def test_verify_password_raises_on_corrupt_hash() -> None:
    with pytest.raises(InvalidPasswordHashError):
        verify_password("anything", "this is not an argon2 string")
