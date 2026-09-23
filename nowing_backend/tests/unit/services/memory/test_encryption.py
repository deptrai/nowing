"""Unit tests for MemoryEncryptionService."""

from __future__ import annotations

import pytest

from app.services.memory.encryption import (
    DecryptionError,
    EncryptionError,
    KeyRegistryService,
    MemoryEncryptionService,
)


class TestMemoryEncryptionServiceModes:
    """Pattern 1/2/3: service must encrypt, decrypt, and handle missing keys."""

    def test_none_mode_is_pass_through(self):
        service = MemoryEncryptionService(provider="none")
        assert not service.is_enabled()

    def test_managed_mode_is_enabled(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="a" * 32
        )
        assert service.is_enabled()

    def test_byok_mode_is_enabled(self):
        service = MemoryEncryptionService(
            provider="byok", master_key="a" * 32, byok_key="b" * 32
        )
        assert service.is_enabled()

    def test_managed_missing_master_key_raises_configuration_error(self):
        with pytest.raises(EncryptionError):
            MemoryEncryptionService(provider="managed")

    def test_byok_missing_byok_key_raises_configuration_error(self):
        with pytest.raises(EncryptionError):
            MemoryEncryptionService(
                provider="byok", master_key="a" * 32
            )


class TestEncryptDecryptRoundTrip:
    """Pattern 1/4: ciphertext must round-trip byte-for-byte."""

    def test_encrypt_decrypt_content(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="a" * 32
        )
        plaintext = "This is a memory fact."
        ciphertext = service.encrypt_value(plaintext)
        assert ciphertext != plaintext
        assert service.decrypt_value(ciphertext, key_id=service.active_key_id) == plaintext

    def test_encrypt_source_input_pii(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="a" * 32
        )
        source_input = {
            "url": "https://example.com",
            "run_id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Nguyen Van A",
            "email": "test@example.com",
            "phone": "0909123456",
            "verified_contact": {"name": "Le Thi B", "title": "CEO"},
        }
        encrypted = service.encrypt_source_input_pii(source_input)

        # Non-sensitive keys stay plaintext.
        assert encrypted["url"] == source_input["url"]
        assert encrypted["run_id"] == source_input["run_id"]

        # Sensitive values are encrypted and can be decrypted back.
        assert encrypted["name"] != source_input["name"]
        assert (
            service.decrypt_value(encrypted["name"], key_id=service.active_key_id)
            == source_input["name"]
        )
        assert (
            service.decrypt_value(encrypted["email"], key_id=service.active_key_id)
            == source_input["email"]
        )
        assert (
            service.decrypt_value(encrypted["phone"], key_id=service.active_key_id)
            == source_input["phone"]
        )

    def test_empty_and_null_values_passthrough(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="a" * 32
        )
        assert service.encrypt_value("") == ""
        assert service.encrypt_value(None) is None

    def test_double_encryption_guard(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="a" * 32
        )
        plaintext = "Fact"
        ciphertext = service.encrypt_value(plaintext)
        assert service.encrypt_value(ciphertext) == ciphertext


class TestIsCiphertext:
    """Pattern 3: detect legacy/plaintext vs ciphertext."""

    def test_null_key_id_is_plaintext(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        assert service.is_ciphertext("abc123", key_id=None) is False
        assert service.is_ciphertext("abc123", key_id="") is False

    def test_legacy_key_id_is_plaintext(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        assert service.is_ciphertext("abc123", key_id="legacy") is False

    def test_active_key_id_is_ciphertext(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ciphertext = service.encrypt_value("fact")
        assert service.is_ciphertext(ciphertext, key_id=service.active_key_id) is True


class TestKeyRegistryService:
    """Pattern 2/3: key archive and rotation."""

    def test_get_active_key(self):
        registry = KeyRegistryService(managed_key="a" * 32)
        key = registry.get_key("managed:v1:0")
        assert key is not None

    def test_get_missing_key_raises_decryption_error(self):
        registry = KeyRegistryService(managed_key="a" * 32)
        with pytest.raises(DecryptionError):
            registry.get_key("byok:999:missing")

    def test_register_byok_key_and_retrieve(self):
        registry = KeyRegistryService(managed_key="a" * 32)
        registry.register_byok_key("byok:1:key-1", "b" * 32)
        assert registry.get_key("byok:1:key-1") == "b" * 32

class TestSurvivingMutants:
    """Mutation-gate killers: target operators/branches that survived."""

    def test_to_tsvector_text_filters_stop_words(self):
        from app.services.memory.encryption import _to_tsvector_text
        assert _to_tsvector_text("the quick brown fox") == "quick brown fox"
        assert _to_tsvector_text("a an the") == ""
        assert _to_tsvector_text("") == ""

    def test_key_registry_get_key_raises_on_missing(self):
        registry = KeyRegistryService(managed_key="a" * 32)
        with pytest.raises(DecryptionError):
            registry.get_key("nonexistent:key")

    def test_derive_fernet_key_uses_hkdf_not_sha256(self):
        from app.services.memory.encryption import (
            _derive_fernet_key,
            _derive_fernet_key_hkdf,
            _derive_fernet_key_legacy,
        )
        secret = "test-secret-32chars-long!!!"
        assert _derive_fernet_key(secret, "fernet-v1-hkdf") == _derive_fernet_key_hkdf(secret)
        assert _derive_fernet_key(secret, "fernet-v1") == _derive_fernet_key_legacy(secret)
        assert _derive_fernet_key_hkdf(secret) != _derive_fernet_key_legacy(secret)

    def test_active_key_id_managed_override(self):
        service = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:custom", master_key="a" * 32
        )
        assert service.active_key_id == "managed:v1:custom"

    def test_active_key_id_for_byok_workspace(self):
        service = MemoryEncryptionService(
            provider="byok", master_key="a" * 32, byok_key="b" * 32
        )
        class FakeMem:
            workspace_id = 42
        assert service.active_key_id_for(memory=FakeMem()) == "byok:42:0"
        assert service.active_key_id_for(workspace_id=99) == "byok:99:0"
        assert service.active_key_id_for() == "byok:0"

    def test_active_key_id_for_disabled_returns_none(self):
        service = MemoryEncryptionService(provider="none")
        assert service.active_key_id_for() is None

    def test_algo_from_value_prefixes(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        assert service._algo_from_value("fernet-v1-hkdf:abc") == "fernet-v1-hkdf"
        assert service._algo_from_value("fernet-v1:abc") == "fernet-v1"
        assert service._algo_from_value("raw") == "fernet-v1-hkdf"

    def test_encrypt_value_rejects_ciphertext(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ct = service.encrypt_value("x")
        assert service.encrypt_value(ct) == ct

    def test_decrypt_value_rejects_plaintext(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        assert service.decrypt_value("plaintext") == "plaintext"
        assert service.decrypt_value("") == ""
        assert service.decrypt_value(None) is None

    def test_decrypt_value_missing_key_id_raises(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ct = service.encrypt_value("x")
        with pytest.raises(DecryptionError):
            service.decrypt_value(ct, key_id=None)
        with pytest.raises(DecryptionError):
            service.decrypt_value(ct, key_id="legacy")
        with pytest.raises(DecryptionError):
            service.decrypt_value(ct, key_id="")

    def test_decrypt_value_invalid_algo_raises(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ct = service.encrypt_value("x")
        with pytest.raises(DecryptionError):
            service.decrypt_value(ct, key_id=service.active_key_id, algo="aes-256")

    def test_is_ciphertext_key_id_none_returns_false(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ct = service.encrypt_value("x")
        assert service.is_ciphertext(ct, key_id=None) is False
        assert service.is_ciphertext(ct, key_id="") is False

    def test_is_ciphertext_legacy_returns_false(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        ct = service.encrypt_value("x")
        assert service.is_ciphertext(ct, key_id="legacy") is False

    def test_is_ciphertext_no_prefix_returns_false(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        assert service.is_ciphertext("plain") is False
        assert service.is_ciphertext("") is False
        assert service.is_ciphertext(None) is False

    def test_decrypt_source_input_pii_requires_key_id(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        encrypted = service.encrypt_source_input_pii({"name": "A"})
        with pytest.raises(DecryptionError):
            service.decrypt_source_input_pii(encrypted, key_id=None)

    def test_default_content_search(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        class FakeMem:
            content = "hello world"
            content_search = None
        assert service._default_content_search(FakeMem()) == "hello world"
        class NoContent:
            content = None
            content_search = None
        assert service._default_content_search(NoContent()) == ""

    def test_reencrypt_if_needed_disabled_returns_false(self):
        service = MemoryEncryptionService(provider="none")
        class FakeMem:
            key_id = "managed:v1:0"
        assert service.reencrypt_if_needed(FakeMem()) is False

    def test_reencrypt_if_needed_legacy_returns_false(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        class FakeMem:
            key_id = "legacy"
            encryption_algo = "fernet-v1-hkdf"
        assert service.reencrypt_if_needed(FakeMem()) is False

    def test_reencrypt_if_needed_rotates(self):
        old = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:old", master_key="old" * 11
        )
        new = MemoryEncryptionService(
            provider="managed", managed_key_id="managed:v1:new", master_key="new" * 11
        )
        new._registry.register_managed_key("managed:v1:old", "old" * 11)
        class FakeMem:
            key_id = "managed:v1:old"
            encryption_algo = "fernet-v1-hkdf"
            content = old.encrypt_value("fact")
            source_input = None
        mem = FakeMem()
        assert new.reencrypt_if_needed(mem) is True
        assert mem.key_id == "managed:v1:new"
        assert new.decrypt_value(mem.content, key_id=mem.key_id) == "fact"

    def test_reencrypt_if_needed_same_key_returns_false(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        class FakeMem:
            key_id = service.active_key_id
            encryption_algo = "fernet-v1-hkdf"
        assert service.reencrypt_if_needed(FakeMem()) is False

    def test_encrypt_memory_sets_key_id_when_only_source_input(self):
        service = MemoryEncryptionService(provider="managed", master_key="a" * 32)
        class FakeMem:
            content = ""
            source_input = {"name": "Nguyen Van A"}
            key_id = None
            encryption_iv = None
            encryption_algo = None
        mem = FakeMem()
        service.encrypt_memory(mem)
        assert mem.key_id == service.active_key_id
        assert mem.encryption_algo == "fernet-v1-hkdf"
        assert mem.source_input["name"] != "Nguyen Van A"
