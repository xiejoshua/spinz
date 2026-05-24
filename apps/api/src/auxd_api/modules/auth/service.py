"""Auth service layer — pure business logic for signup + login (T053).

Routes-layer code in :mod:`auxd_api.modules.auth.routes` deals with HTTP
shape (status codes, request parsing, cookies); this module deals with
the *what* (validate handle, hash password, check duplicates). Keeping
the split sharp means service functions are trivially unit-testable
without spinning up a TestClient.

Failure modes are encoded as :class:`AuthError` subclasses so callers
can map each one to a precise HTTP status without leaking Mongo or
Beanie types past the boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from auxd_api.modules.auth.password import hash_password, verify_password
from auxd_api.modules.users.models import (
    HANDLE_MAX_LEN,
    HANDLE_MIN_LEN,
    User,
    UserStatus,
)
from auxd_api.modules.users.reserved import is_reserved_handle

__all__ = [
    "AccountDeletionPendingError",
    "AccountSuspendedError",
    "AuthError",
    "AuthSignupResult",
    "DuplicateEmailError",
    "DuplicateHandleError",
    "InvalidCredentialsError",
    "InvalidEmailError",
    "InvalidHandleError",
    "ReservedHandleError",
    "WeakPasswordError",
    "authenticate_user",
    "create_user_account",
    "validate_handle_format",
    "validate_password_policy",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Base class for auth-service errors. Carries a stable ``code`` slug."""

    code: str = "auth_error"


class InvalidEmailError(AuthError):
    code = "invalid_email"


class WeakPasswordError(AuthError):
    code = "weak_password"


class InvalidHandleError(AuthError):
    code = "invalid_handle"


class ReservedHandleError(AuthError):
    code = "reserved_handle"


class DuplicateHandleError(AuthError):
    code = "duplicate_handle"


class DuplicateEmailError(AuthError):
    code = "duplicate_email"


class InvalidCredentialsError(AuthError):
    """Raised on login when the email/password pair does not authenticate.

    Deliberately covers both "unknown email" and "wrong password" with
    the same code — distinguishing them would let attackers enumerate
    which emails are registered on auxd. Per-IP rate limits on the
    /login route are the second line of defence against brute force.
    """

    code = "invalid_credentials"


class AccountSuspendedError(AuthError):
    """Raised on login when password is correct but the account is suspended.

    The account-status branch fires only AFTER password verification, so
    this code never leaks for a wrong-password attempt — preserving the
    enumeration-resistance of ``InvalidCredentialsError``.
    """

    code = "account_suspended"


class AccountDeletionPendingError(AuthError):
    """Raised on login when password is correct + account is in the deletion grace window.

    Carries ``scheduled_for`` so the route layer can surface the date to
    the legitimate owner with a "cancel deletion and sign in" CTA. The
    payload only fires after password verification — wrong-password
    attempts still see the generic ``InvalidCredentialsError``.
    """

    code = "account_deletion_pending"

    def __init__(self, message: str, *, scheduled_for: datetime | None) -> None:
        super().__init__(message)
        self.scheduled_for = scheduled_for


# ---------------------------------------------------------------------------
# Validation primitives
# ---------------------------------------------------------------------------


# Handles: lowercase alphanumeric + underscore, 3-30 chars (matches the
# User model's field-length constraints exactly).
_HANDLE_PATTERN = re.compile(r"^[a-z0-9_]+$")

# Password policy (T053 brief): >=12 chars, at least 1 letter + 1 digit.
_PASSWORD_MIN_LEN = 12
_PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")

# Loose email regex — Pydantic's ``EmailStr`` handles the heavy lifting
# at the request layer; this regex is the defence-in-depth fallback for
# direct service callers (tests, future internal callers).
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_handle_format(handle: str) -> None:
    """Raise :class:`InvalidHandleError` when ``handle`` violates the format rules.

    Length + character-class only; "is this handle taken?" /
    "is this handle reserved?" are checked in :func:`create_user_account`
    and the handle-change service so the format check stays pure.
    """
    if not (HANDLE_MIN_LEN <= len(handle) <= HANDLE_MAX_LEN):
        raise InvalidHandleError(
            f"handle must be {HANDLE_MIN_LEN}-{HANDLE_MAX_LEN} characters long"
        )
    if not _HANDLE_PATTERN.fullmatch(handle):
        raise InvalidHandleError(
            "handle may only contain lowercase letters, digits, and underscores"
        )


def validate_password_policy(password: str) -> None:
    """Raise :class:`WeakPasswordError` when ``password`` fails policy.

    Public alias for the T053 signup-time check so the T150 password-change
    route can apply identical rules (>=12 chars, >=1 letter, >=1 digit)
    without depending on a private symbol.
    """
    if len(password) < _PASSWORD_MIN_LEN:
        raise WeakPasswordError(f"password must be at least {_PASSWORD_MIN_LEN} characters")
    if not _PASSWORD_LETTER_RE.search(password):
        raise WeakPasswordError("password must contain at least one letter")
    if not _PASSWORD_DIGIT_RE.search(password):
        raise WeakPasswordError("password must contain at least one digit")


# Backwards-compatible private alias — pre-existing call sites import
# this name; the public helper above is the canonical one for new code.
_validate_password = validate_password_policy


def _validate_email(email: str) -> None:
    """Raise :class:`InvalidEmailError` when ``email`` is malformed."""
    if not _EMAIL_PATTERN.fullmatch(email):
        raise InvalidEmailError("email is not a valid address")


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthSignupResult:
    """The successful-signup payload returned to the route layer."""

    user: User


async def create_user_account(
    *,
    email: str,
    password: str,
    handle: str,
    display_name: str | None = None,
) -> AuthSignupResult:
    """Validate, hash, and persist a new :class:`User`.

    Raises the appropriate :class:`AuthError` subclass for any failure
    detected before the DB write so the caller can map it onto a clean
    HTTP response. Email + handle are persisted lowercased so the unique
    index never disagrees with case-insensitive lookups.
    """
    normalised_email = email.strip().lower()
    # Handles are user-facing and case-sensitive in the rule book: the
    # signup must REJECT uppercase rather than silently downcase, so we
    # validate the stripped-but-not-lowercased form first.
    stripped_handle = handle.strip()
    validate_handle_format(stripped_handle)
    normalised_handle = stripped_handle  # validated lowercase pattern above

    _validate_email(normalised_email)
    _validate_password(password)

    if is_reserved_handle(normalised_handle):
        raise ReservedHandleError("handle is reserved")

    # Duplicate checks — the unique indexes back-stop these, but checking
    # up-front lets us return a clean 409 instead of relying on the
    # DuplicateKeyError message shape.
    if await User.find_one(User.handle == normalised_handle) is not None:
        raise DuplicateHandleError("handle is already taken")
    if await User.find_one(User.email == normalised_email) is not None:
        raise DuplicateEmailError("email is already registered")

    user = User(
        handle=normalised_handle,
        email=normalised_email,
        display_name=(display_name.strip() if display_name else normalised_handle),
        password_hash=hash_password(password),
    )
    await user.insert()
    return AuthSignupResult(user=user)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def authenticate_user(
    *,
    email: str,
    password: str,
    allow_deletion_pending: bool = False,
) -> User:
    """Look up ``email`` and verify ``password``; return the matched :class:`User`.

    Failure mapping (enumeration-aware):

    * Unknown email OR wrong password → :class:`InvalidCredentialsError`.
      The two sub-cases are deliberately collapsed onto the same code so
      attackers can't probe which addresses are registered. The caller
      logs the distinction internally for ops debugging.
    * Correct password + ``UserStatus.SUSPENDED`` → :class:`AccountSuspendedError`.
    * Correct password + ``UserStatus.DELETION_PENDING`` →
      :class:`AccountDeletionPendingError` (carries ``scheduled_for``)
      unless ``allow_deletion_pending=True`` is passed by the cancel-
      deletion login path, in which case the user is returned and the
      caller is expected to invoke ``cancel_account_deletion`` before
      issuing a session.
    * Correct password + ``UserStatus.ACTIVE`` → return the user.

    The status branches are evaluated only AFTER password verification.
    A wrong-password attempt against a suspended/deletion-pending
    account therefore still sees ``InvalidCredentialsError`` — never the
    state-specific codes.
    """
    normalised_email = email.strip().lower()
    user = await User.find_one(User.email == normalised_email)
    if user is None:
        raise InvalidCredentialsError("invalid email or password")
    if user.password_hash is None:
        # Account exists but has no password — defence-in-depth; should
        # not happen at MVP since signup always sets one.
        raise InvalidCredentialsError("invalid email or password")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("invalid email or password")
    # Password OK from here — safe to surface state-specific errors.
    if user.status is UserStatus.SUSPENDED:
        raise AccountSuspendedError("account is suspended")
    if user.status is UserStatus.DELETION_PENDING:
        if allow_deletion_pending:
            return user
        raise AccountDeletionPendingError(
            "account is scheduled for deletion",
            scheduled_for=user.deletion_scheduled_for,
        )
    if user.status is not UserStatus.ACTIVE:
        # Legacy ``DELETED`` status — pre-DELETION_PENDING soft-delete
        # rows. Should never appear for active logins, but if it does
        # the safest default is generic credentials failure (legitimate
        # owners of these rows can't recover via login anyway).
        raise InvalidCredentialsError("invalid email or password")
    return user
