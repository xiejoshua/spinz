"""Reserved-handle list (T057 / Q16 / FR-029).

Loads the static list of squat-blocked handles bundled at
``apps/api/migrations/seed-data/reserved_handles.txt`` and exposes it as
an O(1)-lookup ``frozenset[str]``. Loaded lazily on first access and
cached for the rest of the process lifetime — the seed file is tiny
(~200-500 entries) so the load cost is negligible.

File format:

* One handle per line.
* Lowercase, no leading ``@``.
* Lines starting with ``#`` are comments.
* Blank lines are ignored.

If the seed file is missing or empty the loader logs a warning and
returns an empty frozenset rather than crashing — early-environment
bootstraps and CI containers without the migrations payload should
still boot. Operators see the warning in startup logs and know to
populate the file.

The dedicated module exists so signup-time validation (T053) and the
handle-change service (T057) share one source of truth for "is this
handle reserved?".
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

_LOGGER = logging.getLogger("auxd.users.reserved")

# Project layout: this file lives at
# ``apps/api/src/auxd_api/modules/users/reserved.py`` and the seed file
# at ``apps/api/migrations/seed-data/reserved_handles.txt``. Resolve via
# parent traversal so the lookup works regardless of the CWD.
_DEFAULT_RESERVED_FILE: Path = (
    Path(__file__).resolve().parents[4] / "migrations" / "seed-data" / "reserved_handles.txt"
)


def _parse_lines(text: str) -> frozenset[str]:
    """Strip comments + blanks and lowercase every surviving entry."""
    handles: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        handles.add(line.lower())
    return frozenset(handles)


@lru_cache(maxsize=1)
def load_reserved_handles(source: Path | None = None) -> frozenset[str]:
    """Return the cached frozenset of reserved handles.

    ``source`` is an opt-in override used by tests — production callers
    pass nothing and pick up the default seed-file location. The
    ``lru_cache`` keys on ``source`` so a test-provided path doesn't
    poison the production cache (and vice-versa).
    """
    path = source if source is not None else _DEFAULT_RESERVED_FILE
    if not path.is_file():
        _LOGGER.warning(
            "reserved_handles.missing",
            extra={"event": "reserved_handles.missing", "path": str(path)},
        )
        return frozenset()
    text = path.read_text(encoding="utf-8")
    handles = _parse_lines(text)
    if not handles:
        _LOGGER.warning(
            "reserved_handles.empty",
            extra={"event": "reserved_handles.empty", "path": str(path)},
        )
    return handles


def is_reserved_handle(handle: str) -> bool:
    """Return ``True`` when ``handle`` (lowercased) is on the squat list."""
    return handle.lower() in load_reserved_handles()


__all__ = [
    "is_reserved_handle",
    "load_reserved_handles",
]
