"""Unit tests for :mod:`auxd_api.lib.ids`."""

from __future__ import annotations

import string
import time
from datetime import UTC, datetime

import pytest

from auxd_api.lib.ids import ksuid_to_datetime, new_ksuid, parse_ksuid

BASE62_ALPHABET = set(string.digits + string.ascii_letters)


def test_new_ksuid_format() -> None:
    """A new KSUID is a 27-character string drawn from the base62 alphabet."""
    kid = new_ksuid()
    assert isinstance(kid, str)
    assert len(kid) == 27
    assert set(kid).issubset(BASE62_ALPHABET)


def test_new_ksuid_uniqueness() -> None:
    """1000 KSUIDs generated in a tight loop are all unique."""
    ids = [new_ksuid() for _ in range(1000)]
    assert len(set(ids)) == 1000


def test_new_ksuid_chronological_order() -> None:
    """KSUIDs generated sequentially with a small delay sort in creation order."""
    ids: list[str] = []
    for _ in range(10):
        ids.append(new_ksuid())
        # KSUID timestamps have 1-second resolution; sleep to guarantee distinct
        # prefixes so lexicographic order is dominated by the timestamp, not by
        # the random payload tail.
        time.sleep(1.05)
    assert sorted(ids) == ids


def test_parse_ksuid_roundtrip() -> None:
    """Parsing a generated KSUID yields a consistent, non-empty payload."""
    original = new_ksuid()
    parsed = parse_ksuid(original)
    assert str(parsed) == original
    payload_hex = parsed.payload.hex()
    assert payload_hex
    assert len(payload_hex) == 32  # 16 bytes of randomness


def test_parse_ksuid_invalid() -> None:
    """An invalid KSUID string raises ``ValueError``."""
    with pytest.raises(ValueError):
        parse_ksuid("not-a-valid-ksuid!!!")


def test_ksuid_to_datetime() -> None:
    """The extracted datetime is close (within 5 seconds) to ``datetime.now(UTC)``."""
    before = datetime.now(UTC)
    kid = new_ksuid()
    extracted = ksuid_to_datetime(kid)
    after = datetime.now(UTC)
    assert extracted.tzinfo is not None
    # KSUID timestamps have 1-second resolution; allow a generous 5s window.
    assert abs((extracted - before).total_seconds()) < 5
    assert abs((extracted - after).total_seconds()) < 5
