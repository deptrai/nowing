"""Unit tests for B2B Corporate Email Prediction & DNS MX Verification (Story 21.9 / AD-LI-7)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.email_pattern_service import (
    check_domain_mx,
    generate_email_candidates,
    normalize_name_for_email,
    predict_executive_email,
)


def test_normalize_name_for_email_vietnamese_diacritics() -> None:
    """Normalize Vietnamese names with diacritics into clean ASCII tokens."""
    first, last, full_clean = normalize_name_for_email("Nguyễn Văn An")
    assert first == "an" or first == "van"
    assert last == "nguyen" or last == "an"
    assert "nguyen" in full_clean.lower()
    assert "an" in full_clean.lower()

    # Prefix removal
    f2, l2, clean2 = normalize_name_for_email("Dr. Đặng Hoàng Nam")
    assert "dr" not in f2 and "dr" not in l2
    assert "dang" in clean2.lower()
    assert "nam" in clean2.lower()


def test_generate_email_candidates_patterns() -> None:
    """Generate canonical B2B corporate email patterns."""
    candidates = generate_email_candidates("Nguyen Van An", "vingroup.net")
    assert len(candidates) >= 4
    # Expected patterns:
    # an.nguyen@vingroup.net, nguyen.an@vingroup.net, an@vingroup.net,
    # a.nguyen@vingroup.net, nguyenva@vingroup.net, etc.
    emails_joined = " ".join(candidates)
    assert "@vingroup.net" in emails_joined
    assert "an.nguyen@vingroup.net" in candidates or "nguyen.an@vingroup.net" in candidates
    assert "an@vingroup.net" in candidates or "nguyen@vingroup.net" in candidates


def test_check_domain_mx_success() -> None:
    """DNS MX check returns True when MX records are found."""
    mock_mx = MagicMock()
    mock_mx.exchange = "mail.vingroup.net"

    with patch("dns.resolver.resolve", return_value=[mock_mx]):
        assert check_domain_mx("vingroup.net") is True


def test_check_domain_mx_nxdomain_or_exception() -> None:
    """DNS MX check returns False on resolution error or NXDOMAIN."""
    import dns.resolver

    with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
        assert check_domain_mx("nonexistent-domain-12345.vn") is False

    with patch("dns.resolver.resolve", side_effect=Exception("DNS Timeout")):
        assert check_domain_mx("timeout-domain.com") is False


def test_predict_executive_email_with_valid_mx() -> None:
    """Prediction with valid MX returns high confidence score."""
    with patch("app.services.email_pattern_service.check_domain_mx", return_value=True):
        best_email, candidates, confidence, mx_valid = predict_executive_email(
            "Tran Van Binh",
            "fpt.com",
            check_mx=True,
        )
        assert best_email is not None
        assert "@fpt.com" in best_email
        assert len(candidates) > 0
        assert confidence >= 0.8
        assert mx_valid is True


def test_predict_executive_email_with_invalid_mx() -> None:
    """Prediction with invalid MX returns low confidence score."""
    with patch("app.services.email_pattern_service.check_domain_mx", return_value=False):
        best_email, _candidates, confidence, mx_valid = predict_executive_email(
            "Le Thi Cam",
            "fake-invalid-company.xyz",
            check_mx=True,
        )
        assert best_email is not None
        assert confidence < 0.6
        assert mx_valid is False
