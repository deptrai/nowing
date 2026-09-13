"""Encryption-at-rest service for Memory content, source_input PII, and versions.

This service implements a tiered encryption model:
- Tier 1 (v1): encrypt ``Memory.content``, PII leaf strings in ``Memory.source_input``,
  and ``MemoryVersion`` content columns.
- Tier 2 (v2, deferred): encrypt ``Memory.embedding`` only after a searchable-encryption
  benchmark is accepted.

Provider modes:
- ``none``: pass-through (self-host default).
- ``managed``: derive data-encryption key from a master secret.
- ``byok``: customer-managed key + optional Nowing envelope key.

Row-level metadata ``key_id``, ``encryption_iv``, and ``encryption_algo`` are stored
per row so a single compromised key does not force a full restore.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.services.pii.redact import _EMAIL_PATTERN, _PHONE_PATTERNS

logger = logging.getLogger(__name__)

#: Default algorithm for managed v1. Fernet gives us authenticated encryption
#: with a stable, URL-safe base64 format and includes the IV/salt in the token.
#: ``fernet-v1`` uses single-round SHA-256 key derivation (legacy).  New rows
#: use ``fernet-v1-hkdf`` which derives the key with HKDF-SHA256.
_DEFAULT_ALGO = "fernet-v1-hkdf"

#: Recognized ciphertext prefixes.  Multiple algo versions can coexist.
_ALGO_PREFIXES = ("fernet-v1-hkdf:", "fernet-v1:")

#: Legacy algorithm name for rows written before the HKDF change.
_LEGACY_ALGO = "fernet-v1"

#: Namespace prefixes for key identifiers.
_MANAGED_PREFIX = "managed:v1:"
_MANAGED_LEGACY_PREFIX = "managed:v1:legacy:"
_BYOK_PREFIX = "byok:"

#: HKDF application info string for memory data-encryption keys.
_HKDF_INFO = b"nowing-memory-v1"

#: Maximum recursion depth when walking source_input JSON.
_MAX_SOURCE_INPUT_DEPTH = 20

#: PII keys that should be encrypted at rest when they appear as leaf string values.
_PII_KEYS = frozenset(
    {
        "name",
        "title",
        "email",
        "phone",
        "address",
        "tax_id",
        "tax",
        "domain",
        "identity",
        "contact",
        "verified_contact",
    }
)


def _to_tsvector_text(text: str) -> str:
    """Approximate PostgreSQL to_tsvector('english', text) output in Python.

    This is used to populate ``Memory.content_search`` before the content is
    encrypted, so ``MemoryHybridSearch`` can rank keyword matches over the
    plaintext token stream without storing the full plaintext.  The result is
    a tsvector literal that PostgreSQL can cast back to tsvector.
    """
    # Lower-case, strip punctuation, split on whitespace.
    if not text:
        return ""
    words = re.findall(r"[a-z0-9]+", text.lower())
    # Postgres stop words for english (simplified).  A more complete list can
    # be added, but for ranking the missing stop words just lower IDF weight.
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
        "to", "was", "will", "with",
    }
    filtered = [w for w in words if w not in stop and len(w) > 1]
    if not filtered:
        return ""
    # tsvector format: "word1 word2" with default positional weight.
    return " ".join(filtered)


class EncryptionError(Exception):
    """Raised when encryption configuration or operation fails."""


class DecryptionError(Exception):
    """Raised when decryption of stored ciphertext fails."""


class KeyRegistryService:
    """Resolve key material for a given ``key_id``.

    Supports a historical keyring for managed key rotation and per-workspace
    BYOK keys.  ``key_id`` examples:

    - ``managed:v1:0`` — active managed key.
    - ``managed:v1:<uuid>`` — historical managed key.
    - ``managed:v1:legacy:0`` — legacy managed key that used SHA-256 KDF.
    - ``byok:<workspace_id>:<uuid>`` — workspace-scoped BYOK key.
    - ``byok:0`` / ``byok:<workspace_id>:0`` — legacy/single-key BYOK alias.
    """

    def __init__(
        self,
        *,
        managed_key: str | None = None,
        managed_legacy_key: str | None = None,
    ) -> None:
        self._managed_keys: dict[str, str] = {}
        if managed_key is not None:
            self._managed_keys[f"{_MANAGED_PREFIX}0"] = managed_key
        self._managed_legacy_keys: dict[str, str] = {}
        if managed_legacy_key is not None:
            self._managed_legacy_keys[f"{_MANAGED_LEGACY_PREFIX}0"] = managed_legacy_key
        self._byok_keys: dict[str, str] = {}

    def get_key(self, key_id: str | None) -> str:
        """Return the raw key bytes/secret for ``key_id``.

        ``None`` or ``legacy`` means plaintext and should not call this method.
        """
        if key_id is None or key_id == "legacy":
            raise DecryptionError("key_id is None or legacy; no key material needed")

        if key_id.startswith(_MANAGED_LEGACY_PREFIX):
            if key_id in self._managed_legacy_keys:
                return self._managed_legacy_keys[key_id]
            raise DecryptionError(f"no legacy managed key registered for {key_id}")

        if key_id.startswith(_MANAGED_PREFIX):
            if key_id in self._managed_keys:
                return self._managed_keys[key_id]
            # Fallback: if the active key is requested and no historical ring
            # has it, fail closed rather than guess.
            raise DecryptionError(f"no managed key registered for {key_id}")

        if key_id.startswith(_BYOK_PREFIX):
            if key_id in self._byok_keys:
                return self._byok_keys[key_id]
            # Per-workspace keys fall back to the single BYOK master key.
            byok_fallback = key_id.split(":")[0] + ":0"
            if byok_fallback in self._byok_keys and byok_fallback != key_id:
                return self._byok_keys[byok_fallback]
            if f"{_BYOK_PREFIX}0" in self._byok_keys:
                return self._byok_keys[f"{_BYOK_PREFIX}0"]
            raise DecryptionError(f"BYOK key not registered: {key_id}")

        raise DecryptionError(f"unknown key_id namespace: {key_id}")

    def register_managed_key(self, key_id: str, key: str) -> None:
        """Register a managed key for testing or key rotation."""
        if not key_id.startswith(_MANAGED_PREFIX) and not key_id.startswith(_MANAGED_LEGACY_PREFIX):
            raise EncryptionError(f"invalid managed key_id: {key_id}")
        if key_id.startswith(_MANAGED_LEGACY_PREFIX):
            self._managed_legacy_keys[key_id] = key
        else:
            self._managed_keys[key_id] = key

    def register_byok_key(self, key_id: str, key: str) -> None:
        """Register a BYOK key for testing or customer onboarding."""
        if not key_id.startswith(_BYOK_PREFIX):
            raise EncryptionError(f"invalid BYOK key_id: {key_id}")
        self._byok_keys[key_id] = key

    @property
    def active_managed_key_id(self) -> str:
        """Active key identifier for the managed provider."""
        return f"{_MANAGED_PREFIX}0"


def _derive_fernet_key_legacy(secret: str) -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from a secret string."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _derive_fernet_key_hkdf(secret: str) -> bytes:
    """Derive a Fernet key using HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    )
    return base64.urlsafe_b64encode(hkdf.derive(secret.encode()))


def _derive_fernet_key(secret: str, algo: str = _DEFAULT_ALGO) -> bytes:
    """Derive a Fernet key for ``algo``."""
    if algo == _LEGACY_ALGO:
        return _derive_fernet_key_legacy(secret)
    return _derive_fernet_key_hkdf(secret)


def _build_cipher(secret: str, algo: str = _DEFAULT_ALGO) -> Fernet:
    """Build a Fernet cipher from a secret and algorithm."""
    return Fernet(_derive_fernet_key(secret, algo))


def _has_pii_pattern(value: str) -> bool:
    """Return True when ``value`` looks like an email or phone number."""
    if _EMAIL_PATTERN.search(value):
        return True
    return any(pattern.search(value) for pattern in _PHONE_PATTERNS)


class MemoryEncryptionService:
    """Centralized encryption/decryption service for Memory Tier-1 fields."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        master_key: str | None = None,
        legacy_key: str | None = None,
        byok_key: str | None = None,
        managed_key_id: str | None = None,
        byok_key_id: str | None = None,
        enabled: bool = True,
    ) -> None:
        raw_provider = (provider or "none").lower().strip()
        if raw_provider not in ("none", "managed", "byok"):
            logger.warning(
                "Unknown NOWING_ENCRYPTION_KEY_PROVIDER=%r; falling back to none",
                provider,
            )
            raw_provider = "none"
        self._provider = raw_provider
        self._enabled = enabled and self._provider in ("managed", "byok")
        self._master_key = master_key or os.getenv("MANAGED_ENCRYPTION_MASTER_KEY")
        self._legacy_key = legacy_key or os.getenv("MANAGED_ENCRYPTION_LEGACY_KEY")
        self._byok_key = byok_key or os.getenv("BYOK_KEY")
        self._managed_key_id = managed_key_id or f"{_MANAGED_PREFIX}0"
        self._byok_key_id = byok_key_id

        if self._enabled and self._provider == "managed" and not self._master_key:
            raise EncryptionError(
                "NOWING_ENCRYPTION_KEY_PROVIDER=managed requires MANAGED_ENCRYPTION_MASTER_KEY"
            )

        if self._enabled and self._provider == "byok" and not self._byok_key:
            raise EncryptionError(
                "NOWING_ENCRYPTION_KEY_PROVIDER=byok requires BYOK_KEY"
            )

        if self._enabled and self._provider == "managed" and self._master_key:
            self._registry = KeyRegistryService(
                managed_key=self._master_key,
                managed_legacy_key=self._legacy_key,
            )
            # Ensure the configured active key id resolves to this master key.
            self._registry.register_managed_key(self._managed_key_id, self._master_key)
        elif self._enabled and self._provider == "byok" and self._byok_key:
            self._registry = KeyRegistryService(
                managed_key=self._master_key,
                managed_legacy_key=self._legacy_key,
            )
            # Register the default BYOK alias so any workspace-scoped key_id can
            # resolve back to the single customer key.
            self._registry.register_byok_key(f"{_BYOK_PREFIX}0", self._byok_key)
            if self._byok_key_id is not None:
                self._registry.register_byok_key(self._byok_key_id, self._byok_key)
        else:
            self._registry = KeyRegistryService()

    @classmethod
    def from_env(cls) -> MemoryEncryptionService:
        """Build the service from ``app.config.memory`` settings.

        Kept as a classmethod so tests can still inject explicit keys via
        ``__init__`` without touching module-level config.
        """
        from app.config.memory import (
            BYOK_KEY,
            MANAGED_ENCRYPTION_LEGACY_KEY,
            MANAGED_ENCRYPTION_MASTER_KEY,
            MEMORY_ENCRYPTION_V1,
            NOWING_ENCRYPTION_KEY_PROVIDER,
        )

        return cls(
            provider=NOWING_ENCRYPTION_KEY_PROVIDER,
            master_key=MANAGED_ENCRYPTION_MASTER_KEY,
            legacy_key=MANAGED_ENCRYPTION_LEGACY_KEY,
            byok_key=BYOK_KEY,
            enabled=MEMORY_ENCRYPTION_V1,
        )

    @property
    def active_key_id(self) -> str | None:
        """The key identifier that should be written for new ciphertext."""
        if not self._enabled:
            return None
        if self._provider == "managed":
            return self._managed_key_id
        if self._provider == "byok":
            return self._byok_key_id or f"{_BYOK_PREFIX}0"
        return None

    def active_key_id_for(self, *, memory: Any | None = None, workspace_id: int | None = None) -> str | None:
        """Active key id scoped to a workspace for BYOK."""
        if not self._enabled:
            return None
        if self._provider == "managed":
            return self._managed_key_id
        if self._provider == "byok":
            ws = workspace_id
            if ws is None and memory is not None:
                ws = getattr(memory, "workspace_id", None)
            if ws is not None:
                return f"{_BYOK_PREFIX}{ws}:0"
            return f"{_BYOK_PREFIX}0"
        return None

    def is_enabled(self) -> bool:
        return self._enabled

    def _algo_from_value(self, value: str) -> str:
        """Infer algorithm from the ciphertext prefix."""
        for prefix in _ALGO_PREFIXES:
            if value.startswith(prefix):
                return prefix[:-1]
        return _DEFAULT_ALGO

    def _split_ciphertext(self, value: str) -> tuple[str, str]:
        """Return (algo, ciphertext) from a stored value."""
        for prefix in _ALGO_PREFIXES:
            if value.startswith(prefix):
                return prefix[:-1], value[len(prefix):]
        # No prefix: legacy or unencrypted.
        if value.startswith("fernet-v1:"):
            return _LEGACY_ALGO, value[10:]
        return _DEFAULT_ALGO, value

    def encrypt_value(self, value: str | None) -> str | None:
        """Encrypt a single string value."""
        if not self._enabled or value is None or value == "":
            return value
        if self.is_ciphertext(value, key_id=self.active_key_id):
            return value

        key = self._registry.get_key(self.active_key_id)
        cipher = _build_cipher(key, _DEFAULT_ALGO)
        ciphertext = cipher.encrypt(value.encode()).decode()
        return f"{_DEFAULT_ALGO}:{ciphertext}"

    def _looks_like_ciphertext(self, value: str) -> bool:
        """Return True when value has a recognized algorithm prefix."""
        return any(value.startswith(prefix) for prefix in _ALGO_PREFIXES)

    def decrypt_value(self, value: str | None, *, key_id: str | None = None, algo: str | None = None) -> str | None:
        """Decrypt a single string value."""
        if value is None or value == "":
            return value
        if not self._looks_like_ciphertext(value):
            return value

        if key_id is None or key_id == "legacy" or key_id == "":
            raise DecryptionError("cannot decrypt ciphertext without key_id")

        value_algo, ciphertext = self._split_ciphertext(value)
        effective_algo = algo if algo is not None else value_algo

        if effective_algo not in (_LEGACY_ALGO, _DEFAULT_ALGO):
            raise DecryptionError(f"unsupported encryption algorithm: {effective_algo}")

        key = self._registry.get_key(key_id)
        cipher = _build_cipher(key, effective_algo)
        try:
            return cipher.decrypt(ciphertext.encode()).decode()
        except Exception as exc:  # Fernet/cipher raises broadly; wrap as DecryptionError with key context
            raise DecryptionError(f"decryption failed for key_id={key_id}: {exc}") from exc

    def is_ciphertext(self, value: str | None, key_id: str | None = None) -> bool:
        """Return True when ``value`` appears to be encrypted ciphertext.

        ``key_id`` is optional for legacy-compatibility checks: rows whose
        ``key_id`` is ``None``/``legacy`` are treated as plaintext even when the
        stored string happens to carry a recognized prefix.
        """
        if value is None or value == "":
            return False
        if key_id is None or key_id == "" or key_id == "legacy":
            return False
        return any(value.startswith(prefix) for prefix in _ALGO_PREFIXES)

    def encrypt_source_input_pii(self, source_input: Any) -> Any:
        """Walk ``source_input`` JSON and encrypt PII leaf strings."""
        if not self._enabled or source_input is None:
            return source_input
        return self._encrypt_json_value(source_input, depth=0)

    def decrypt_source_input_pii(self, source_input: Any, key_id: str | None = None, algo: str | None = None) -> Any:
        """Walk ``source_input`` JSON and decrypt any encrypted PII leaf strings.

        ``key_id`` must be supplied so leaf ciphertexts can be resolved to the
        correct key; when omitted the parent row's ``key_id`` is used.
        """
        if source_input is None:
            return source_input
        return self._decrypt_json_value(source_input, key_id=key_id, algo=algo)

    def _encrypt_json_value(self, value: Any, depth: int) -> Any:
        if depth > _MAX_SOURCE_INPUT_DEPTH:
            return value

        if isinstance(value, dict):
            return {
                k: self._maybe_encrypt_json_leaf(k, v, depth + 1)
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [
                self._encrypt_json_value(item, depth + 1) for item in value
            ]

        # A string at the top level (or inside a list) may still be PII.
        if (
            isinstance(value, str)
            and value
            and _has_pii_pattern(value)
            and not self.is_ciphertext(value, key_id=self.active_key_id)
        ):
            return self.encrypt_value(value)

        return value

    def _maybe_encrypt_json_leaf(self, key: str, value: Any, depth: int) -> Any:
        if isinstance(value, dict | list):
            return self._encrypt_json_value(value, depth)

        if not isinstance(value, str) or not value:
            return value

        # Already encrypted? skip.
        if self.is_ciphertext(value, key_id=self.active_key_id):
            return value

        # Encrypt if key is in PII list or value matches PII regex.
        if key.lower() in _PII_KEYS or _has_pii_pattern(value):
            return self.encrypt_value(value)

        return value

    def _decrypt_json_value(self, value: Any, *, key_id: str | None = None, algo: str | None = None) -> Any:
        if isinstance(value, dict):
            return {
                k: self._decrypt_json_value(v, key_id=key_id, algo=algo)
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [
                self._decrypt_json_value(item, key_id=key_id, algo=algo)
                for item in value
            ]

        if isinstance(value, str) and value:
            return self.decrypt_value(value, key_id=key_id, algo=algo)

        return value

    def _default_content_search(self, memory: Any) -> str | None:
        """Return a tsvector text from plaintext content, if the column exists."""
        if not hasattr(memory, "content_search"):
            return None
        content = getattr(memory, "content", None) or ""
        return _to_tsvector_text(content)

    def encrypt_memory(self, memory: Any) -> None:
        """Encrypt in-place the Tier-1 fields of a Memory ORM object."""
        if not self._enabled:
            return

        active_key = self.active_key_id_for(memory=memory)

        # Populate ``content_search`` from plaintext before encryption so
        # hybrid keyword search still has a tokenized index.
        if hasattr(memory, "content_search"):
            memory.content_search = _to_tsvector_text(getattr(memory, "content", None) or "")

        content = getattr(memory, "content", None)
        if content and not self.is_ciphertext(content, key_id=getattr(memory, "key_id", None)):
            memory.content = self.encrypt_value(content)
            memory.key_id = active_key
            memory.encryption_algo = _DEFAULT_ALGO
            memory.encryption_iv = ""

        source_input = getattr(memory, "source_input", None)
        if source_input is not None:
            memory.source_input = self.encrypt_source_input_pii(source_input)
            # Ensure the row carries the active key id even when ``content`` is
            # empty/None; otherwise the encrypted source_input is orphaned.
            if getattr(memory, "key_id", None) is None:
                memory.key_id = active_key
                memory.encryption_algo = _DEFAULT_ALGO
                memory.encryption_iv = ""

    def decrypt_memory(self, memory: Any) -> None:
        """Decrypt in-place the Tier-1 fields of a Memory ORM object."""
        content = getattr(memory, "content", None)
        key_id = getattr(memory, "key_id", None)
        algo = getattr(memory, "encryption_algo", None)
        if content and self.is_ciphertext(content, key_id=key_id):
            memory.content = self.decrypt_value(
                content, key_id=key_id, algo=algo
            )

        source_input = getattr(memory, "source_input", None)
        if source_input is not None:
            memory.source_input = self.decrypt_source_input_pii(
                source_input, key_id=key_id, algo=algo
            )

    def encrypt_memory_version(self, version: Any) -> None:
        """Encrypt in-place the content columns of a MemoryVersion ORM object."""
        if not self._enabled:
            return

        active_key = self.active_key_id

        for col in ("previous_content", "corrected_content"):
            value = getattr(version, col, None)
            if value and not self.is_ciphertext(value, key_id=version.key_id):
                setattr(version, col, self.encrypt_value(value))
                version.key_id = active_key
                version.encryption_algo = _DEFAULT_ALGO
                version.encryption_iv = ""

    def decrypt_memory_version(self, version: Any) -> None:
        """Decrypt in-place the content columns of a MemoryVersion ORM object."""
        for col in ("previous_content", "corrected_content"):
            value = getattr(version, col, None)
            if value and self.is_ciphertext(value, key_id=version.key_id):
                setattr(
                    version,
                    col,
                    self.decrypt_value(value, key_id=version.key_id, algo=version.encryption_algo),
                )

    def reencrypt_if_needed(self, memory: Any) -> bool:
        """Re-encrypt ``memory`` if its ``key_id`` is not the active key.

        Returns True if the row was re-encrypted. Legacy rows (``key_id`` is
        ``None`` or ``'legacy'``) are treated as plaintext and are never
        re-encrypted; only rows that already carry a managed key are rotated.
        """
        if not self._enabled:
            return False

        if memory.key_id is None or memory.key_id == "legacy":
            return False
        active = self.active_key_id_for(memory=memory)
        if memory.key_id == active and memory.encryption_algo == _DEFAULT_ALGO:
            return False

        # Fail closed: if we cannot decrypt (key missing/rotated), do not leave
        # stale ciphertext in place.
        self.decrypt_memory(memory)
        self.encrypt_memory(memory)
        return True

    def to_plaintext(self, memory: Any) -> None:
        """Convenience helper: decrypt a memory in place for direct readers."""
        self.decrypt_memory(memory)


__all__ = [
    "DecryptionError",
    "EncryptionError",
    "KeyRegistryService",
    "MemoryEncryptionService",
]
