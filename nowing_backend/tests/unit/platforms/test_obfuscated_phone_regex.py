"""Unit test for obfuscated phone regex variations (Story 21.8 / Task 6.1)."""

import pytest

from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor


@pytest.mark.parametrize(
    "raw_input,expected_phone",
    [
        ("o912345678", "0912345678"),
        ("O90.123.4567", "0901234567"),
        ("09 12 34 56 78", "0912345678"),
        ("+84 987 654 321", "0987654321"),
        ("84912345678", "0912345678"),
        ("038-123-4567", "0381234567"),
        ("o79-888-9999", "0798889999"),
        ("056.789.1234", "0567891234"),
        ("không chín 1 2 ba bốn 5 6 bảy tám", "0912345678"),
        ("o chín o tám 123 456", "0908123456"),
        ("083.456.7890", "0834567890"),
        ("09l2345678", "0912345678"),
    ],
)
def test_obfuscated_phone_regex_variants(raw_input: str, expected_phone: str):
    extractor = SocialEntityExtractor()
    extracted = extractor.extract_phones(f"Liên hệ: {raw_input} để biết thêm chi tiết")
    assert expected_phone in extracted
