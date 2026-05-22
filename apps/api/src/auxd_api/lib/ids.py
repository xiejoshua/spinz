"""KSUID identifier helpers.

KSUIDs (K-Sortable Unique IDentifiers) are 160-bit identifiers encoded as
27-character base62 strings. The leading 32 bits encode a Unix-epoch timestamp
(using svix-ksuid's custom epoch of 2014-05-13T16:53:20Z), and the trailing
128 bits are cryptographic randomness.

Because the timestamp prefix is fixed-width and big-endian, KSUIDs are
lexicographically sortable by creation time. This makes them ideal as primary
keys for collections that need stable cursor pagination (sort by ``_id``
descending, page by the last-seen KSUID) without secondary indexes or joins.
"""

from __future__ import annotations

from datetime import datetime

import ksuid


def new_ksuid() -> str:
    """Generate a fresh KSUID and return its 27-character base62 string form."""
    return str(ksuid.Ksuid())


def parse_ksuid(s: str) -> ksuid.Ksuid:
    """Parse a base62 KSUID string into a :class:`ksuid.Ksuid` instance.

    Raises:
        ValueError: If ``s`` is not a valid base62 KSUID.
    """
    try:
        return ksuid.Ksuid.from_base62(s)
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - defensive: wrap unexpected errors
        raise ValueError(f"invalid KSUID: {s!r}") from exc


def ksuid_to_datetime(s: str) -> datetime:
    """Return the UTC :class:`datetime` embedded in the KSUID's timestamp prefix."""
    return parse_ksuid(s).datetime
