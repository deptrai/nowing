"""Encryption at rest for ``VerifiedContact`` PII (Story 21.3, Task 2).

Raw contact PII (``name`` / ``title`` / ``email`` / ``phone``) is stored
encrypted in ``verified_contacts`` (AD-42 / AD-49). ``VerifiedContact`` is the
access-controlled PII vault: values are decrypted only when building
``VerifiedContactRead`` responses for authorized callers (``CONTACTS_READ``).
``redact_pii`` is never applied to these raw values.
"""

from __future__ import annotations

from typing import TypedDict

from app.config import config
from app.utils.oauth_security import TokenEncryption


class VerifiedContactDict(TypedDict, total=False):  # pragma: no mutate
    """A verified-contact result as produced by enrichment providers.

    PII fields (``name``, ``title``, ``email``, ``phone``) are plaintext in
    this in-memory contract; they are encrypted before any persistence.
    """

    name: str | None
    title: str | None
    email: str
    phone: str | None
    verification_status: str
    confidence: float
    source_provider: str


_PII_FIELDS = ("name", "title", "email", "phone")


class VerifiedContactEncryption:
    """Fernet-based encryption wrapper for verified-contact PII fields."""

    def __init__(self, secret_key: str | None = None) -> None:  # pragma: no mutate
        self._cipher = TokenEncryption(secret_key or config.SECRET_KEY)

    def encrypt(self, value: str | None) -> str | None:  # pragma: no mutate
        """Encrypt a single PII value; None/empty pass through unchanged."""
        if not value:
            return value
        return self._cipher.encrypt_token(value)

    def decrypt(self, value: str | None) -> str | None:  # pragma: no mutate
        """Decrypt a single stored ciphertext; None/empty pass through."""
        if not value:
            return value
        if not self.is_encrypted(value):
            raise ValueError("Value is not encrypted; refusing to return it as-is")
        return self._cipher.decrypt_token(value)

    def is_encrypted(self, value: str | None) -> bool:  # pragma: no mutate
        """True when the value looks like a Fernet ciphertext."""
        return self._cipher.is_encrypted(value or "")

    def encrypt_contact(self, contact: VerifiedContactDict) -> VerifiedContactDict:
        """Return a copy of ``contact`` with PII fields encrypted in place."""
        encrypted = dict(contact)
        for field in _PII_FIELDS:
            value = encrypted.get(field)
            if isinstance(value, str):
                encrypted[field] = self.encrypt(value)
        return encrypted

    def decrypt_contact(self, contact: VerifiedContactDict) -> VerifiedContactDict:
        """Return a copy of ``contact`` with PII fields decrypted."""
        decrypted = dict(contact)
        for field in _PII_FIELDS:
            value = decrypted.get(field)
            if isinstance(value, str):
                decrypted[field] = self.decrypt(value)
        return decrypted
