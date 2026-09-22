"""Encryption at rest for ``VerifiedContact`` PII (Story 21.3, Task 2).

Raw contact PII (``name`` / ``title`` / ``email`` / ``phone``) is stored
encrypted in ``verified_contacts`` (AD-42 / AD-49). ``VerifiedContact`` is the
access-controlled PII vault: values are decrypted only when building
``VerifiedContactRead`` responses for authorized callers (``CONTACTS_READ``).
``redact_pii`` is never applied to these raw values.

Story 33.1 adds dual-key fallback for zero-downtime SECRET_KEY rotation:
- ``SECRET_KEY`` remains the primary encryption key.
- ``SECONDARY_SECRET_KEY`` (optional) is used to decrypt legacy records that
  were encrypted with the previous key. On successful decrypt, values are
  re-encrypted with the primary key on next write.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from app.config import config
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


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
    """Fernet-based encryption wrapper for verified-contact PII fields.

    Supports dual-key fallback for zero-downtime SECRET_KEY rotation
    (Story 33.1). When ``SECONDARY_SECRET_KEY`` is configured, decryption
    tries the primary key first, then falls back to the secondary key.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        secondary_secret_key: str | None = None,
    ) -> None:  # pragma: no mutate
        primary = secret_key or config.SECRET_KEY
        secondary = secondary_secret_key or getattr(
            config, "SECONDARY_SECRET_KEY", None
        )

        self._cipher = TokenEncryption(primary)
        self._secondary_cipher = (
            TokenEncryption(secondary) if secondary else None
        )
        self._primary_key = primary
        self._secondary_key = secondary

    def encrypt(self, value: str | None) -> str | None:  # pragma: no mutate
        """Encrypt a single PII value with the primary key; None/empty pass through."""
        if not value:
            return value
        return self._cipher.encrypt_token(value)

    def decrypt(self, value: str | None) -> str | None:  # pragma: no mutate
        """Decrypt a single stored ciphertext; None/empty pass through.

        Tries primary key first, then secondary key for legacy records.
        """
        if not value:
            return value
        if not self.is_encrypted(value):
            raise ValueError("Value is not encrypted; refusing to return it as-is")

        # Try primary key first
        try:
            return self._cipher.decrypt_token(value)
        except Exception as primary_exc:
            if self._secondary_cipher is None:
                raise ValueError(
                    f"Token decryption failed with primary key: {primary_exc}"
                ) from primary_exc

        # Fallback to secondary key for legacy records
        try:
            decrypted = self._secondary_cipher.decrypt_token(value)
            logger.info(
                "Decrypted PII with secondary key; will re-encrypt with primary on next write"
            )
            return decrypted
        except Exception as secondary_exc:
            raise ValueError(
                f"Token decryption failed with both primary and secondary keys: "
                f"primary={primary_exc}, secondary={secondary_exc}"
            ) from secondary_exc

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

    def rotate_encryption(self, contact: VerifiedContactDict) -> VerifiedContactDict:
        """Decrypt with secondary key (if needed) and re-encrypt with primary.

        Used during SECRET_KEY rotation to upgrade legacy records.
        """
        rotated = dict(contact)
        for field in _PII_FIELDS:
            value = rotated.get(field)
            if isinstance(value, str) and self.is_encrypted(value):
                # Try primary first; if it fails, decrypt with secondary and re-encrypt
                try:
                    decrypted = self._cipher.decrypt_token(value)
                except Exception:
                    if self._secondary_cipher is not None:
                        decrypted = self._secondary_cipher.decrypt_token(value)
                    else:
                        raise
                rotated[field] = self.encrypt(decrypted)
        return rotated
