"""Unit tests for ``VerifiedContactEncryption`` (Story 21.3, Task 2)."""

from __future__ import annotations

import pytest

from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = pytest.mark.unit


@pytest.fixture()
def crypto() -> VerifiedContactEncryption:
    return VerifiedContactEncryption("test-secret-key-for-unit-tests")


async def test_encrypt_decrypt_roundtrip(crypto: VerifiedContactEncryption) -> None:
    """Encrypted values decrypt back to the original plaintext."""
    raw = "nguyen.van.a@example.com"
    encrypted = crypto.encrypt(raw)
    assert encrypted != raw
    assert crypto.is_encrypted(encrypted)
    assert crypto.decrypt(encrypted) == raw


async def test_encrypt_decrypt_contact_dict(crypto: VerifiedContactEncryption) -> None:
    """``encrypt_contact``/``decrypt_contact`` round-trip the PII fields."""
    contact = {
        "name": "Nguyen Van A",
        "title": "Head of Sales",
        "email": "nguyen.van.a@example.com",
        "phone": "+84901234567",
        "verification_status": "verified",
        "confidence": 0.95,
        "source_provider": "cleanlist",
    }
    encrypted = crypto.encrypt_contact(dict(contact))
    assert encrypted["email"] != contact["email"]
    assert encrypted["phone"] != contact["phone"]
    assert encrypted["name"] != contact["name"]
    # Non-PII fields pass through untouched.
    assert encrypted["verification_status"] == "verified"
    assert encrypted["source_provider"] == "cleanlist"

    decrypted = crypto.decrypt_contact(encrypted)
    assert decrypted == contact


async def test_none_values_pass_through(crypto: VerifiedContactEncryption) -> None:
    """None and empty strings are left as-is (no ciphertext churn)."""
    assert crypto.encrypt(None) is None
    assert crypto.decrypt(None) is None
    assert crypto.encrypt("") == ""
    assert crypto.decrypt("") == ""


async def test_decrypt_plaintext_raises(crypto: VerifiedContactEncryption) -> None:
    """Decrypting a non-encrypted value surfaces a ValueError."""
    with pytest.raises(ValueError):
        crypto.decrypt("not-encrypted@example.com")


async def test_empty_secret_falls_back_to_config(monkeypatch) -> None:
    """A falsy explicit secret falls back to ``config.SECRET_KEY`` (not ``and``)."""
    from app.config import config

    monkeypatch.setattr(config, "SECRET_KEY", "config-fallback-secret-key")
    empty = VerifiedContactEncryption("")
    none = VerifiedContactEncryption(None)

    raw = "fallback@example.com"
    ciphertext = empty.encrypt(raw)
    assert ciphertext != raw
    assert none.decrypt(ciphertext) == raw