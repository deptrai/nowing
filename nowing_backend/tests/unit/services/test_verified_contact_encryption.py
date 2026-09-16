"""Unit tests for VerifiedContactEncryption dual-key fallback (Story 33.1)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [pytest.mark.unit]


class TestVerifiedContactEncryption:
    """Test dual-key encryption/decryption for SECRET_KEY rotation."""

    def test_encrypt_decrypt_with_primary_key(self):
        """Encrypt and decrypt with primary key works."""
        enc = VerifiedContactEncryption(secret_key="primary-secret-123")
        original = "test@example.com"
        encrypted = enc.encrypt(original)
        decrypted = enc.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_with_secondary_key_fallback(self):
        """Decrypt falls back to secondary key when primary fails."""
        # Create encryption with old key
        old_enc = VerifiedContactEncryption(secret_key="old-secret-456")
        encrypted = old_enc.encrypt("legacy@data.com")

        # New encryption with different primary + old as secondary
        new_enc = VerifiedContactEncryption(
            secret_key="new-secret-789",
            secondary_secret_key="old-secret-456",
        )
        decrypted = new_enc.decrypt(encrypted)
        assert decrypted == "legacy@data.com"

    def test_decrypt_fails_without_secondary_key(self):
        """Decryption fails when only primary key is wrong."""
        old_enc = VerifiedContactEncryption(secret_key="old-secret")
        encrypted = old_enc.encrypt("data")

        new_enc = VerifiedContactEncryption(secret_key="new-secret")
        with pytest.raises(ValueError, match="Token decryption failed"):
            new_enc.decrypt(encrypted)

    def test_rotate_encryption_upgrades_to_primary(self):
        """rotate_encryption re-encrypts legacy data with primary key."""
        old_enc = VerifiedContactEncryption(secret_key="old-secret")
        encrypted = old_enc.encrypt("rotate-me")

        new_enc = VerifiedContactEncryption(
            secret_key="new-secret",
            secondary_secret_key="old-secret",
        )
        rotated = new_enc.rotate_encryption({"email": encrypted})

        # Should decrypt to original with new key only
        assert new_enc.decrypt(rotated["email"]) == "rotate-me"
        # Old key should no longer work on rotated value
        with pytest.raises(ValueError):
            old_enc.decrypt(rotated["email"])

    def test_encrypt_contact_all_fields(self):
        """encrypt_contact encrypts all PII fields."""
        enc = VerifiedContactEncryption(secret_key="test-key")
        contact = {
            "name": "John Doe",
            "title": "CEO",
            "email": "john@example.com",
            "phone": "0908123456",
            "verification_status": "verified",
        }
        encrypted = enc.encrypt_contact(contact)

        assert encrypted["name"] != contact["name"]
        assert encrypted["title"] != contact["title"]
        assert encrypted["email"] != contact["email"]
        assert encrypted["phone"] != contact["phone"]
        assert encrypted["verification_status"] == contact["verification_status"]

        # Decrypt back
        decrypted = enc.decrypt_contact(encrypted)
        assert decrypted["name"] == contact["name"]
        assert decrypted["email"] == contact["email"]

    def test_decrypt_contact_with_secondary(self):
        """decrypt_contact uses secondary key for legacy records."""
        old_enc = VerifiedContactEncryption(secret_key="old-key")
        contact = {"name": "Jane", "email": "jane@old.com"}
        encrypted = old_enc.encrypt_contact(contact)

        new_enc = VerifiedContactEncryption(
            secret_key="new-key",
            secondary_secret_key="old-key",
        )
        decrypted = new_enc.decrypt_contact(encrypted)
        assert decrypted["name"] == "Jane"
        assert decrypted["email"] == "jane@old.com"

    def test_is_encrypted_heuristic(self):
        """is_encrypted returns True for Fernet ciphertexts."""
        enc = VerifiedContactEncryption(secret_key="test")
        assert enc.is_encrypted(enc.encrypt("test")) is True
        assert enc.is_encrypted("plaintext") is False
        assert enc.is_encrypted(None) is False
        assert enc.is_encrypted("") is False
