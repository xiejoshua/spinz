"""Envelope encryption for short secret strings (OAuth tokens, session payloads).

Per plan §4.1 and §17.2, OAuth tokens are encrypted at rest using a single
master key (the "key encryption key", KEK) loaded from the Fly secret
``TOKEN_ENCRYPTION_KEY`` — a standard-base64-encoded 32-byte (AES-256) key.

The implementation uses :class:`cryptography.fernet.MultiFernet` to support
key rotation: callers may construct an encryptor with the current key first
and any older keys after. New ciphertexts are produced with the current key;
on decrypt, every configured key is tried (current first) so old ciphertexts
remain readable until a sweep job re-encrypts them with the new key.

This module deliberately exposes no module-level state — callers build a
:class:`TokenEncryptor` from already-decoded key material and pass it in.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class SecretsError(Exception):
    """Raised on malformed key material or decryption failure."""


class MissingKeyError(SecretsError):
    """Raised when no encryption key is configured."""


class DecryptionError(SecretsError):
    """Raised when ciphertext is malformed, tampered, or no key can decrypt it."""


@dataclass(frozen=True)
class TokenEncryptor:
    """Envelope encryption for short secret strings (OAuth tokens, etc.).

    Key material is a tuple of raw 32-byte keys, current first. The first key
    is the "active" encryption key; all keys are tried on decrypt to support
    rotation (write with new key, retire the old key only after a sweep job
    re-encrypts every ciphertext).

    Each call to :meth:`encrypt` returns a self-contained URL-safe base64
    ciphertext string (Fernet's format: version || timestamp || IV || ct || HMAC).
    """

    keys: tuple[bytes, ...]  # raw 32-byte keys, current first

    def __post_init__(self) -> None:
        if not self.keys:
            raise MissingKeyError("TokenEncryptor requires at least one 32-byte key")
        for k in self.keys:
            if len(k) != 32:
                raise SecretsError(f"All keys must be exactly 32 bytes; got {len(k)}")

    @classmethod
    def from_base64_strings(cls, b64_keys: list[str]) -> TokenEncryptor:
        """Build from standard-base64-encoded key strings (the env-var form).

        Raises:
            MissingKeyError: If ``b64_keys`` is empty.
            SecretsError: If any string fails to base64-decode or decodes to a
                value that is not exactly 32 bytes.
        """
        if not b64_keys:
            raise MissingKeyError("from_base64_strings requires at least one key")
        try:
            decoded = tuple(base64.b64decode(s, validate=True) for s in b64_keys)
        except (ValueError, TypeError) as exc:  # base64 decoding failures
            raise SecretsError(f"Failed to base64-decode key material: {exc}") from exc
        return cls(keys=decoded)

    def _fernet(self) -> MultiFernet:
        # Fernet expects urlsafe-base64 of the raw 32-byte key.
        return MultiFernet([Fernet(base64.urlsafe_b64encode(k)) for k in self.keys])

    def encrypt(self, plaintext: str) -> str:
        """Encrypt ``plaintext`` (utf-8) and return a URL-safe base64 ciphertext."""
        token = self._fernet().encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext produced by :meth:`encrypt`.

        Tries each configured key in order (current first). Raises
        :class:`DecryptionError` if the input is malformed, tampered with, or
        no key can authenticate it.
        """
        try:
            raw = self._fernet().decrypt(ciphertext.encode("ascii"))
        except InvalidToken as exc:
            raise DecryptionError("Ciphertext is invalid, tampered, or no key matched") from exc
        except (ValueError, TypeError) as exc:  # bad base64 input, etc.
            raise DecryptionError(f"Malformed ciphertext: {exc}") from exc
        return raw.decode("utf-8")

    def rotate_to(self, new_key_b64: str) -> TokenEncryptor:
        """Return a new :class:`TokenEncryptor` with ``new_key_b64`` as the current key.

        Existing keys are kept in order behind the new one so old ciphertexts
        still decrypt until a sweep job re-encrypts them with the new key.
        """
        existing_b64 = [base64.b64encode(k).decode("ascii") for k in self.keys]
        return TokenEncryptor.from_base64_strings([new_key_b64, *existing_b64])
