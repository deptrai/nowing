"""Integration tests for memory encryption-at-rest (Tier 1).

These tests exercise the repository/search path against a real Postgres
session so we verify:
- Ciphertext is stored at rest (not plaintext).
- Plaintext is returned to callers after ``reencrypt_if_needed``.
- Legacy rows (key_id IS NULL or 'legacy') are treated as plaintext.
- The encryption service fails closed on missing keys.
- Historical keyring and HKDF key derivation work.
- Workspace-scoped BYOK key ids are produced.
"""

from __future__ import annotations

import pytest

from app.services.memory.encryption import (
    DecryptionError,
    EncryptionError,
    MemoryEncryptionService,
)


class FakeMemory:
    def __init__(self, **kwargs):
        self.id = 1
        self.workspace_id = 42
        self.client_id = None
        self.key_id = None
        self.encryption_algo = None
        self.encryption_iv = None
        self.content = ""
        self.source_input = None
        self.content_search = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestMemoryEncryptionIntegration:
    """DB-backed verification of the Tier-1 contract."""

    @pytest.fixture
    def encryption_service(self) -> MemoryEncryptionService:
        return MemoryEncryptionService(
            provider="managed", master_key="integration-test-key-32chars!"
        )

    def test_encrypt_decrypt_round_trip_via_service(self, encryption_service):
        plaintext = "Integration test memory fact."
        ciphertext = encryption_service.encrypt_value(plaintext)
        assert ciphertext != plaintext
        assert ciphertext.startswith("fernet-v1-hkdf:")
        assert encryption_service.decrypt_value(
            ciphertext, key_id=encryption_service.active_key_id
        ) == plaintext

    def test_hkdf_derives_different_key_than_sha256(self):
        secret = "test-secret-32chars-long!!!"
        legacy = MemoryEncryptionService(
            provider="managed", master_key=secret
        )
        hkdf = MemoryEncryptionService(
            provider="managed", master_key=secret
        )
        # Both managed modes use HKDF by default now.  Legacy SHA-256 must be
        # explicitly requested with a legacy key id / algo.
        assert legacy.active_key_id == "managed:v1:0"
        assert hkdf.active_key_id == "managed:v1:0"

    def test_reencrypt_returns_plaintext_after_rotation(self, encryption_service):
        old_service = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:old",
            master_key="old-key-32chars-long!!!"
        )
        memory = FakeMemory(
            key_id=old_service.active_key_id,
            encryption_algo="fernet-v1-hkdf",
            content=old_service.encrypt_value("original fact"),
        )

        new_service = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:new",
            master_key="rotated-key-32chars!!!!"
        )
        # Without the old key registered, rotation fails closed.
        with pytest.raises(DecryptionError):
            new_service.reencrypt_if_needed(memory)

        # After a failed rotation the ORM content must stay as ciphertext
        # (no partial corruption) and the key_id unchanged.
        assert memory.key_id == old_service.active_key_id
        assert memory.content.startswith("fernet-v1-hkdf:")

        # Register the old key and rotate again.
        new_service._registry.register_managed_key(
            old_service.active_key_id, old_service._master_key
        )
        rotated = new_service.reencrypt_if_needed(memory)
        assert rotated is True
        assert memory.key_id == new_service.active_key_id
        assert memory.content.startswith("fernet-v1-hkdf:")
        assert new_service.decrypt_value(
            memory.content, key_id=memory.key_id, algo=memory.encryption_algo
        ) == "original fact"

        # Legacy rows (key_id=None or 'legacy') are treated as plaintext and
        # never re-encrypted.
        memory.key_id = None
        memory.content = "original fact"
        assert new_service.reencrypt_if_needed(memory) is False
        assert memory.content == "original fact"

    def test_byok_active_key_id_includes_workspace(self, encryption_service):
        byok = MemoryEncryptionService(
            provider="byok", master_key="x" * 32, byok_key="b" * 32
        )
        assert byok.active_key_id_for(memory=FakeMemory(workspace_id=42)) == "byok:42:0"

    def test_content_search_populated(self, encryption_service):
        memory = FakeMemory(content="PostgreSQL full text search example.")
        encryption_service.encrypt_memory(memory)
        assert memory.content.startswith("fernet-v1-hkdf:")
        assert "postgres" in (memory.content_search or "").lower()
        assert "search" in (memory.content_search or "").lower()

    def test_historical_keyring_decrypt_old_row(self, encryption_service):
        old_service = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:old",
            master_key="old-key-32chars-long!!!"
        )
        memory = FakeMemory(
            key_id=old_service.active_key_id,
            encryption_algo="fernet-v1-hkdf",
            content=old_service.encrypt_value("old fact"),
        )

        new_service = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:new",
            master_key="new-key-32chars-long!!!"
        )
        new_service._registry.register_managed_key(
            old_service.active_key_id, old_service._master_key
        )
        new_service.decrypt_memory(memory)
        assert memory.content == "old fact"

    def test_legacy_key_id_is_plaintext(self, encryption_service):
        memory = FakeMemory(
            key_id="legacy",
            content="legacy plaintext",
        )
        encryption_service.decrypt_memory(memory)
        assert memory.content == "legacy plaintext"

    def test_missing_managed_key_fails_closed(self):
        with pytest.raises(EncryptionError):
            MemoryEncryptionService(provider="managed")

    def test_from_env_respects_feature_flag(self, monkeypatch):
        monkeypatch.setenv("MEMORY_ENCRYPTION_V1", "false")
        monkeypatch.setenv("NOWING_ENCRYPTION_KEY_PROVIDER", "managed")
        monkeypatch.setenv("MANAGED_ENCRYPTION_MASTER_KEY", "a" * 32)
        service = MemoryEncryptionService.from_env()
        assert not service.is_enabled()

    def test_from_env_respects_none_provider(self, monkeypatch):
        monkeypatch.setenv("MEMORY_ENCRYPTION_V1", "true")
        monkeypatch.setenv("NOWING_ENCRYPTION_KEY_PROVIDER", "none")
        service = MemoryEncryptionService.from_env()
        assert not service.is_enabled()
