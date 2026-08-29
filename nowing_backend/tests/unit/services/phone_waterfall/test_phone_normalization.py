"""Unit tests for Vietnam Phone & Contact normalization, legacy 11-digit conversion, and PII encryption (Story 21.3 / Story 24.2 / INV-24.3)."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from app.services.phone_waterfall_service import (
    get_carrier_name,
    hash_phone,
    mask_phone,
    normalize_vn_phone,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

# ─────────────────────────────────────────────────────────────
# 1. 2018 Telecom Legacy 11-to-10 Digit Conversion Tests (Story 24.2 / AC-2)
# ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLegacy11DigitConversion:
    """Validate 2018 Vietnam telecom conversion of 11-digit mobile numbers to standard 10-digit format."""

    def test_viettel_11_to_10_conversion(self):
        """Viettel 0162->032, 0163->033, 0164->034, 0165->035, 0166->036, 0167->037, 0168->038, 0169->039."""
        assert normalize_vn_phone("01621234567") == "0321234567"
        assert normalize_vn_phone("01639876543") == "0339876543"
        assert normalize_vn_phone("01641112222") == "0341112222"
        assert normalize_vn_phone("01653334444") == "0353334444"
        assert normalize_vn_phone("01665556666") == "0365556666"
        assert normalize_vn_phone("01677778888") == "0377778888"
        assert normalize_vn_phone("01689990000") == "0389990000"
        assert normalize_vn_phone("01691234567") == "0391234567"

    def test_vinaphone_11_to_10_conversion(self):
        """Vinaphone 0123->083, 0124->084, 0125->085, 0127->081, 0129->082."""
        assert normalize_vn_phone("01234567890") == "0834567890"
        assert normalize_vn_phone("01245678901") == "0845678901"
        assert normalize_vn_phone("01256789012") == "0856789012"
        assert normalize_vn_phone("01278901234") == "0818901234"
        assert normalize_vn_phone("01290123456") == "0820123456"

    def test_mobifone_11_to_10_conversion(self):
        """MobiFone 0120->070, 0121->079, 0122->077, 0126->076, 0128->078."""
        assert normalize_vn_phone("01201234567") == "0701234567"
        assert normalize_vn_phone("01212345678") == "0792345678"
        assert normalize_vn_phone("01223456789") == "0773456789"
        assert normalize_vn_phone("01264567890") == "0764567890"
        assert normalize_vn_phone("01285678901") == "0785678901"

    def test_vietnamobile_and_gmobile_11_to_10_conversion(self):
        """Vietnamobile 0186->056, 0188->058 | Gmobile 0199->059."""
        assert normalize_vn_phone("01861234567") == "0561234567"
        assert normalize_vn_phone("01881234567") == "0581234567"
        assert normalize_vn_phone("01991234567") == "0591234567"

    def test_international_prefix_with_legacy_11_digits(self):
        """International format (+84 / 84) with 11-digit legacy prefixes."""
        assert normalize_vn_phone("+841689990000") == "0389990000"
        assert normalize_vn_phone("841234567890") == "0834567890"
        assert normalize_vn_phone("+84 120 123 4567") == "0701234567"

    def test_punctuated_legacy_11_digits(self):
        """Legacy numbers formatted with dots, dashes, and spaces."""
        assert normalize_vn_phone("0168.999.0000") == "0389990000"
        assert normalize_vn_phone("0123-456-7890") == "0834567890"
        assert normalize_vn_phone("0128 567 8901") == "0785678901"


# ─────────────────────────────────────────────────────────────
# 2. Standard Normalization, Masking, Hashing & ReDoS Tests
# ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestStandardPhoneNormalization:
    """Validate standard 10-digit formats and security protections."""

    def test_normalize_vn_phone_standard_formats(self):
        assert normalize_vn_phone("0908123456") == "0908123456"
        assert normalize_vn_phone("+84908123456") == "0908123456"
        assert normalize_vn_phone("84908123456") == "0908123456"
        assert normalize_vn_phone("090.812.3456") == "0908123456"
        assert normalize_vn_phone("090 812 3456") == "0908123456"
        assert normalize_vn_phone("0987-654-321") == "0987654321"
        assert normalize_vn_phone("0389 123 456") == "0389123456"
        assert normalize_vn_phone("0778 888 999") == "0778888999"

    def test_normalize_vn_phone_vietnamese_words(self):
        assert (
            normalize_vn_phone("không chín không tám một hai ba bốn năm sáu")
            == "0908123456"
        )
        assert (
            normalize_vn_phone("khong chin tam bay sau nam bon ba hai mot")
            == "0987654321"
        )

    def test_normalize_vn_phone_invalid_prefixes_or_lengths(self):
        # Landline or invalid short numbers
        assert normalize_vn_phone("0243888888") is None
        assert normalize_vn_phone("19001560") is None
        assert normalize_vn_phone("123456") is None
        assert normalize_vn_phone("0999999999999") is None  # Too long (>11 digits)
        assert normalize_vn_phone("") is None
        assert normalize_vn_phone(None) is None

    def test_anti_redos_execution_time(self):
        evil_text = "0" * 5000 + " chín " * 500 + " !@#$%^&*() " * 100
        start = time.perf_counter()
        _ = normalize_vn_phone(evil_text, timeout_sec=0.05)
        elapsed = time.perf_counter() - start
        assert (
            elapsed < 0.1
        )  # Must execute or abort well within bound (<100ms max in test env)

    def test_mask_phone(self):
        assert mask_phone("0908123456") == "0908***456"
        assert mask_phone("0987654321") == "0987***321"
        # E.164 input also masks as domestic display
        assert mask_phone("+84908123456") == "0908***456"
        assert mask_phone("") == ""
        assert mask_phone(None) == ""

    def test_hash_phone(self, monkeypatch):
        from app.config import config

        test_key = "test-secret-key-must-be-long-enough-12345678"
        monkeypatch.setattr(config, "SECRET_KEY", test_key)
        # hash_phone now canonicalizes to E.164 before hashing
        expected = hmac.new(
            test_key.encode("utf-8"),
            b"+84908123456",
            hashlib.sha256,
        ).hexdigest()
        assert hash_phone("0908123456") == expected
        assert hash_phone("+84908123456") == expected
        assert hash_phone("84908123456") == expected
        assert hash_phone(None) is None

    def test_carrier_name(self):
        assert get_carrier_name("0981234567") == "Viettel"
        assert get_carrier_name("0861234567") == "Viettel"
        assert get_carrier_name("0911234567") == "VNPT / Vinaphone"
        assert get_carrier_name("0881234567") == "VNPT / Vinaphone"
        assert get_carrier_name("0901234567") == "MobiFone"
        assert get_carrier_name("0791234567") == "MobiFone"
        assert get_carrier_name("0921234567") == "Vietnamobile"
        assert get_carrier_name("0991234567") == "Gmobile"
        assert get_carrier_name("0551234567") == "Wintel"
        assert get_carrier_name("0871234567") == "Itelecom"


# ─────────────────────────────────────────────────────────────
# 3. PII Vault Encryption Tests (INV-21.3)
# ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPiiEncryption:
    """Validate Fernet symmetric encryption of phone numbers at rest."""

    def test_phone_encryption(self):
        enc = VerifiedContactEncryption("test-secret-key-must-be-long-enough-12345678")
        raw = "0908123456"
        ciphertext = enc.encrypt(raw)
        assert ciphertext != raw
        assert len(ciphertext) > 20
        decrypted = enc.decrypt(ciphertext)
        assert decrypted == raw
