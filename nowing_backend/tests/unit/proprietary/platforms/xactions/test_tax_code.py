"""Unit tests for Vietnamese Tax Code (MST) Modulo-11 validator and extractor."""

import pytest

from app.proprietary.platforms.xactions.tax_code import (
    extract_tax_ids,
    is_valid_vietnam_tax_code,
)

pytestmark = pytest.mark.unit


class TestVietnameseTaxCodeValidation:
    """Tests for Vietnamese tax code (MST) validation using Modulo-11 algorithm."""

    def test_valid_10_digit_standard_tax_code(self):
        """Valid 10-digit tax code satisfies Modulo-11 checksum."""
        # Known valid tax codes
        assert is_valid_vietnam_tax_code("0100109106") is True  # Viettel Group
        assert is_valid_vietnam_tax_code("0300588569") is True  # FPT HCM

    def test_valid_13_digit_branch_tax_code(self):
        """Valid 13-digit tax code with 3-digit branch suffix satisfies Modulo-11 checksum on first 10 digits."""
        assert is_valid_vietnam_tax_code("0100109106-001") is True
        assert is_valid_vietnam_tax_code("0100109106001") is True

    def test_formatted_tax_code_with_spaces_or_dashes(self):
        """Punctuation and spaces inside tax code are stripped cleanly before validation."""
        assert is_valid_vietnam_tax_code("0100 109 106") is True
        assert is_valid_vietnam_tax_code("0100-109-106") is True
        assert is_valid_vietnam_tax_code("MST: 0100.109.106") is True

    def test_invalid_check_digit_rejected(self):
        """Tax code with tampered 10th check digit fails validation."""
        # Altering last digit from 6 to 5
        assert is_valid_vietnam_tax_code("0100109105") is False

    def test_invalid_lengths_rejected(self):
        """Non 10 or 13 digit lengths fail validation."""
        assert is_valid_vietnam_tax_code("123456789") is False  # 9 digits
        assert is_valid_vietnam_tax_code("12345678901") is False  # 11 digits
        assert is_valid_vietnam_tax_code("") is False
        assert is_valid_vietnam_tax_code("ABCDEFGHIJ") is False


class TestTaxCodeExtraction:
    """Tests for extracting tax code candidates from raw source text."""

    def test_extract_tax_ids_from_text(self):
        """Extracts candidate 10-digit and 13-digit tax IDs from unstructured descriptions."""
        text = """
        Công ty Cổ phần Công nghệ ABC
        Mã số thuế: 0100109106
        Chi nhánh Hà Nội: 0100109106-001
        Hotline: 0908123456
        """
        tax_ids = extract_tax_ids(text)
        assert "0100109106" in tax_ids
        assert "0100109106-001" in tax_ids or "0100109106001" in tax_ids

    def test_extract_tax_ids_empty_text(self):
        """Empty or whitespace text returns empty candidate list."""
        assert extract_tax_ids("") == []
        assert extract_tax_ids("   \n\t  ") == []

    def test_extract_tax_ids_dot_separated(self):
        """MSTs written with dots are extracted and normalized."""
        tax_ids = extract_tax_ids("MST: 0100.109.106")
        assert "0100109106" in tax_ids

    def test_extract_tax_ids_space_separated(self):
        """MSTs written with spaces are extracted and normalized."""
        tax_ids = extract_tax_ids("Mã số thuế: 0100 109 106")
        assert "0100109106" in tax_ids

    def test_extract_tax_ids_dash_separated(self):
        """MSTs written with dashes are extracted and normalized."""
        tax_ids = extract_tax_ids("Tax ID: 0100-109-106")
        assert "0100109106" in tax_ids

    def test_extract_tax_ids_prefix_and_branch(self):
        """MSTs with a branch code and mixed delimiters are extracted."""
        tax_ids = extract_tax_ids("Mã số thuế: 0100.109.106-001")
        assert "0100109106-001" in tax_ids

    def test_extract_tax_ids_does_not_extract_phones(self):
        """Standalone phone numbers are not extracted as tax IDs."""
        text = "Mã số thuế: 0100109106, liên hệ 0908123456 hoặc 0912345678"
        tax_ids = extract_tax_ids(text)
        assert "0100109106" in tax_ids
        assert "0908123456" not in tax_ids
        assert "0912345678" not in tax_ids

    def test_extract_tax_ids_rejects_arbitrary_numbers(self):
        """Random 10-digit numbers that are not valid MSTs are not extracted."""
        tax_ids = extract_tax_ids("Số tài khoản: 1234567890 hoặc 9876543211")
        assert tax_ids == []

    def test_extract_tax_ids_valid_standalone_mst(self):
        """A valid MST without a keyword prefix is still extracted."""
        tax_ids = extract_tax_ids("0100109106")
        assert tax_ids == ["0100109106"]

    def test_extract_tax_ids_excludes_phone_like_valid_mst_in_standalone(self):
        """A valid MST that also matches the mobile phone pattern is excluded when not
        in a tax-keyword context, preventing phone false-positives."""
        # 0900000002 is a valid Modulo-11 code and matches the 09x mobile pattern.
        assert is_valid_vietnam_tax_code("0900000002") is True
        tax_ids = extract_tax_ids("Gọi ngay 0900000002")
        assert "0900000002" not in tax_ids
