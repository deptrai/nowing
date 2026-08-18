"""Red-phase unit tests for PII HMAC and masking helpers (Story 26.4)."""

from __future__ import annotations

import pytest

from app.config import config
from app.lead_intelligence.dnc.normalizer import (
    compute_email_hmac,
    compute_phone_hmac,
    compute_verified_contact_hmac,
    hash_phone_hmac,
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
)
from app.services.export_service import mask_email, mask_phone

pytestmark = pytest.mark.unit

SECRET = "test-secret-key-26-4"


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SECRET_KEY", SECRET)


class TestComputeVerifiedContactHmac:
    """AC-2: canonical composite HMAC for deduplication."""

    def test_canonical_form(self) -> None:
        phone = normalize_phone_e164("+84 908 123 456")
        email = normalize_email("Alice@Acme.COM")
        domain = normalize_domain("https://acme.com/about")
        assert phone == "+84908123456"
        assert email == "alice@acme.com"
        assert domain == "acme.com"

        h = compute_verified_contact_hmac(phone, email, domain)
        expected = hash_phone_hmac(
            f"phone={phone}|email={email}|domain={domain}",
            SECRET,
        )
        assert h == expected
        assert len(h) == 64

    def test_missing_phone_uses_empty_string(self) -> None:
        h = compute_verified_contact_hmac(None, "alice@acme.com", "acme.com")
        expected = hash_phone_hmac(
            "phone=|email=alice@acme.com|domain=acme.com",
            SECRET,
        )
        assert h == expected

    def test_missing_email_uses_empty_string(self) -> None:
        h = compute_verified_contact_hmac("+84908123456", None, "acme.com")
        expected = hash_phone_hmac(
            "phone=+84908123456|email=|domain=acme.com",
            SECRET,
        )
        assert h == expected

    def test_missing_domain_uses_empty_string(self) -> None:
        h = compute_verified_contact_hmac("+84908123456", "alice@acme.com", None)
        expected = hash_phone_hmac(
            "phone=+84908123456|email=alice@acme.com|domain=",
            SECRET,
        )
        assert h == expected

    def test_degenerate_all_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="degenerate contact"):
            compute_verified_contact_hmac(None, None, None)

    def test_secret_not_configured_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "SECRET_KEY", "")
        with pytest.raises(ValueError, match="SECRET_KEY"):
            compute_verified_contact_hmac("+84908123456", "a@b.com", "b.com")

    def test_normalization_variants_produce_same_hmac(self) -> None:
        """Boundary: +84 vs 0-prefix vs legacy 11-digit all normalize to same E.164."""
        variants = ["+84908123456", "0908 123 456", "0908123456", "84908123456"]
        hmacs = {
            compute_verified_contact_hmac(v, "alice@acme.com", "acme.com")
            for v in variants
        }
        assert len(hmacs) == 1


class TestBlindIndexHmacs:
    """AC-2: phone_hmac and email_hmac match DNC hash_phone_hmac."""

    def test_compute_phone_hmac_matches_dnc(self) -> None:
        phone = normalize_phone_e164("+84908123456")
        assert compute_phone_hmac(phone) == hash_phone_hmac(phone, SECRET)

    def test_compute_email_hmac_matches_dnc(self) -> None:
        email = normalize_email("Alice@Acme.com")
        assert compute_email_hmac(email) == hash_phone_hmac(email, SECRET)

    def test_phone_hmac_is_64_hex(self) -> None:
        h = compute_phone_hmac("+84908123456")
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_email_hmac_is_64_hex(self) -> None:
        h = compute_email_hmac("alice@acme.com")
        assert len(h) == 64
        int(h, 16)  # valid hex


class TestMaskPhone:
    """AC-7: phone masking for non-privileged display."""

    @pytest.mark.parametrize(
        "phone,expected",
        [
            ("+84908123456", "+84908***456"),
            ("0908123456", "0908***456"),
            ("090 123 45 67", "0901***567"),
        ],
    )
    def test_masks_phone(self, phone: str, expected: str) -> None:
        assert mask_phone(phone) == expected

    def test_returns_empty_for_none(self) -> None:
        assert mask_phone(None) == ""

    def test_returns_original_for_short_phone(self) -> None:
        assert mask_phone("12345") == "12345"


class TestMaskEmail:
    """AC-7: email masking for non-privileged display."""

    def test_masks_email(self) -> None:
        assert mask_email("alice@example.com") == "a***@example.com"

    def test_returns_empty_for_none(self) -> None:
        assert mask_email(None) == ""

    def test_returns_original_for_no_at(self) -> None:
        assert mask_email("notanemail") == "notanemail"
