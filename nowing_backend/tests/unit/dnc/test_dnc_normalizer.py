"""Unit tests for DNC Normalizer & HMAC Hasher (Story 21.14).

Tests E.164 phone normalization, Keyed HMAC-SHA256 hashing, wildcard domain matching,
and case-insensitive email/domain matching.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestPhoneNormalization:
    """Test canonical international E.164 normalization for VN and international numbers."""

    def test_normalize_vietnamese_mobile_formats(self) -> None:
        """Should convert standard local Vietnamese numbers (0908, 091, 098) to E.164 (+84...)."""
        from app.lead_intelligence.dnc.normalizer import normalize_phone_e164

        assert normalize_phone_e164("0908123456") == "+84908123456"
        assert normalize_phone_e164("090.812.3456") == "+84908123456"
        assert normalize_phone_e164("090 812 3456") == "+84908123456"
        assert normalize_phone_e164("(090) 812-3456") == "+84908123456"
        assert normalize_phone_e164("84908123456") == "+84908123456"
        assert normalize_phone_e164("+84 908 123 456") == "+84908123456"

    def test_normalize_invalid_phone_returns_none(self) -> None:
        """Should return None on malformed, incomplete or non-phone strings."""
        from app.lead_intelligence.dnc.normalizer import normalize_phone_e164

        assert normalize_phone_e164("") is None
        assert normalize_phone_e164("abc") is None
        assert normalize_phone_e164("123") is None
        assert normalize_phone_e164("012345") is None

    def test_keyed_hmac_hash_phone(self) -> None:
        """Should generate deterministic HMAC-SHA256 hex string with secret key."""
        from app.lead_intelligence.dnc.normalizer import hash_phone_hmac

        phone_e164 = "+84908123456"
        hash_1 = hash_phone_hmac(phone_e164, secret_key="test-secret-key-123")
        hash_2 = hash_phone_hmac(phone_e164, secret_key="test-secret-key-123")
        hash_other = hash_phone_hmac(phone_e164, secret_key="different-secret-key")

        assert len(hash_1) == 64
        assert hash_1 == hash_2
        assert hash_1 != hash_other


class TestDomainAndEmailNormalization:
    """Test normalization and wildcard matching for domains and emails."""

    def test_normalize_domain(self) -> None:
        """Should strip protocol, paths, ports, and lowercase domain names."""
        from app.lead_intelligence.dnc.normalizer import normalize_domain

        assert normalize_domain("https://Vinhomes.vn/du-an") == "vinhomes.vn"
        assert normalize_domain("http://sub.company.com:8080/") == "sub.company.com"
        assert normalize_domain("  HARAVAN.COM  ") == "haravan.com"
        assert (
            normalize_domain("http://user:pass@example.com:8080/path") == "example.com"
        )
        assert normalize_domain("user:pass@example.com:8080/path") == "example.com"
        assert normalize_domain("example.com:8080/path") == "example.com"

    def test_wildcard_domain_match(self) -> None:
        """Should support exact match and wildcard subdomains (e.g. *.vinhomes.vn)."""
        from app.lead_intelligence.dnc.normalizer import is_domain_matching

        assert is_domain_matching("vinhomes.vn", "vinhomes.vn") is True
        assert is_domain_matching("oceanpark.vinhomes.vn", "*.vinhomes.vn") is True
        assert is_domain_matching("other.vn", "*.vinhomes.vn") is False
        assert is_domain_matching("vinhomes.vn.fake.com", "vinhomes.vn") is False

    def test_normalize_email(self) -> None:
        """Should trim and lowercase email addresses."""
        from app.lead_intelligence.dnc.normalizer import normalize_email

        assert normalize_email("  CEO@Vinhomes.VN  ") == "ceo@vinhomes.vn"
        assert normalize_email("invalid-email") is None
