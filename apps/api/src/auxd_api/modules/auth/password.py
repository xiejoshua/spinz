"""Argon2-id password hashing helpers (T053 / NFR Security).

Wraps :mod:`argon2.PasswordHasher` with the auxd-wide default parameters
so callers never instantiate the hasher themselves and can't drift from
the agreed cost. The hasher is module-singleton because constructing it
allocates a small amount of state; ``hash`` / ``verify`` are thread-safe
per the upstream docs.

The default Argon2-id parameters used here come straight from the
``argon2-cffi`` library's recommended defaults (time_cost=3, memory=64MB,
parallelism=4) which target ~50ms hash time on commodity hardware. That
is the right cost for the MVP — high enough to deter offline dictionary
attacks, low enough that signup/login latency stays under the NFR p95
budget.

The module exposes two functions and one custom exception:

* :func:`hash_password` — pure CPU-bound encode. Async callers should
  wrap it via ``asyncio.to_thread`` if the call latency becomes
  measurable on a request thread; at MVP traffic it's fine inline.
* :func:`verify_password` — returns ``True`` only when the supplied
  password verifies against the supplied hash. Constant-time wrt the
  hash + supplied password pair (argon2-cffi handles the timing).
* :class:`InvalidPasswordHashError` — narrows ``argon2.exceptions``
  failures into a single sentinel so callers can react uniformly.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

__all__ = [
    "InvalidPasswordHashError",
    "hash_password",
    "verify_password",
]


class InvalidPasswordHashError(ValueError):
    """Raised when a stored hash is structurally invalid (corrupt / wrong algorithm)."""


# Module-singleton hasher with library defaults; cheap to construct but
# we keep it shared so test imports don't pay the cost N times.
_HASHER: PasswordHasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return the Argon2-id hash of ``plain`` in PHC-string format.

    Argon2 generates a fresh per-call salt so identical inputs yield
    different hashes — verify with :func:`verify_password`, never with
    direct string comparison.
    """
    return _HASHER.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """Verify ``plain`` against the stored ``password_hash``.

    Returns ``True`` on a clean match, ``False`` on mismatch. Raises
    :class:`InvalidPasswordHashError` only when the stored hash itself
    is structurally broken (e.g. truncated, wrong algorithm prefix) so
    callers can distinguish "user typed the wrong password" (return
    ``False``) from "the DB row is corrupted and this is a 500" (raise).
    """
    try:
        return _HASHER.verify(password_hash, plain)
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHashError) as exc:
        raise InvalidPasswordHashError(str(exc)) from exc
