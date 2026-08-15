"""Unit tests for SocialEntityExtractor (Vietnamese obfuscated phone numbers & entities)."""

import time

import pytest

from app.proprietary.platforms.xactions.phone_extractor import (
    SocialEntityExtractor,
)


class TestPhoneExtractorObfuscatedVariants:
    """Test 10+ variations of Vietnamese obfuscated phone numbers."""

    @pytest.fixture
    def extractor(self):
        return SocialEntityExtractor()

    def test_phone_variant_1_lowercase_o(self, extractor):
        """o912345678 -> 0912345678"""
        text = "Liên hệ chính chủ: o912345678 để xem nhà"
        phones = extractor.extract_phones(text)
        assert "0912345678" in phones

    def test_phone_variant_2_uppercase_o_with_dots(self, extractor):
        """O90.123.4567 -> 0901234567"""
        text = "Inbox hoặc alo O90.123.4567 nhé mọi người"
        phones = extractor.extract_phones(text)
        assert "0901234567" in phones

    def test_phone_variant_3_spaces_between_digits(self, extractor):
        """09 12 34 56 78 -> 0912345678"""
        text = "SĐT: 09 12 34 56 78 gặp anh Tuấn"
        phones = extractor.extract_phones(text)
        assert "0912345678" in phones

    def test_phone_variant_4_country_code_plus_84(self, extractor):
        """+84 987 654 321 -> 0987654321"""
        text = "Call me at +84 987 654 321 for details"
        phones = extractor.extract_phones(text)
        assert "0987654321" in phones

    def test_phone_variant_5_prefix_84_without_plus(self, extractor):
        """84912345678 -> 0912345678"""
        text = "Số Zalo 84912345678 tư vấn 24/7"
        phones = extractor.extract_phones(text)
        assert "0912345678" in phones

    def test_phone_variant_6_prefix_03_with_hyphens(self, extractor):
        """038-123-4567 -> 0381234567"""
        text = "Chính chủ gửi bán 038-123-4567"
        phones = extractor.extract_phones(text)
        assert "0381234567" in phones

    def test_phone_variant_7_prefix_07_with_letter_o(self, extractor):
        """o79-888-9999 -> 0798889999"""
        text = "Hotline: o79-888-9999"
        phones = extractor.extract_phones(text)
        assert "0798889999" in phones

    def test_phone_variant_8_prefix_05_with_dots(self, extractor):
        """056.789.1234 -> 0567891234"""
        text = "Zalo liên hệ: 056.789.1234"
        phones = extractor.extract_phones(text)
        assert "0567891234" in phones

    def test_phone_variant_9_vietnamese_words_mixed(self, extractor):
        """không chín 1 2 ba bốn 5 6 bảy tám -> 0912345678"""
        text = "SĐT chống quét bot: không chín 1 2 ba bốn 5 6 bảy tám"
        phones = extractor.extract_phones(text)
        assert "0912345678" in phones

    def test_phone_variant_10_spelled_out_words(self, extractor):
        """lh o chín o tám 123 456 -> 0908123456"""
        text = "Lh o chín o tám 123 456 để xem hợp đồng"
        phones = extractor.extract_phones(text)
        assert "0908123456" in phones

    def test_phone_variant_11_parentheses_and_prefix_08(self, extractor):
        """083.456.7890 (zalo) -> 0834567890"""
        text = "Alo 083.456.7890 (zalo chính chủ)"
        phones = extractor.extract_phones(text)
        assert "0834567890" in phones

    def test_phone_variant_12_letter_substitution_one(self, extractor):
        """09l2345678 (l for 1) -> 0912345678"""
        text = "Số đẹp 09l2345678 giá rẻ"
        phones = extractor.extract_phones(text)
        assert "0912345678" in phones


class TestReDoSSafety:
    """Test anti-ReDoS protection with 50ms timeout bound."""

    @pytest.fixture
    def extractor(self):
        return SocialEntityExtractor()

    def test_pathological_repetitive_input_completes_within_50ms(self, extractor):
        """Pathological regex input string should not lock CPU and finish <= 50ms."""
        pathological_str = "09" + " " * 5000 + "12345678"
        start_time = time.perf_counter()
        phones = extractor.extract_phones(pathological_str, timeout_sec=0.05)
        duration = time.perf_counter() - start_time
        assert duration < 0.05  # enforce the 50ms spec bound
        assert isinstance(phones, list)

    def test_long_random_content_safety(self, extractor):
        """Extracting on 50KB text should complete safely."""
        long_text = "Bán nhà đất giá rẻ tại Hà Nội. " * 2000 + " Liên hệ 0912345678 " + "Mua bán BĐS " * 1000
        start_time = time.perf_counter()
        result = extractor.extract_all(long_text)
        duration = time.perf_counter() - start_time
        assert duration < 0.20
        assert "0912345678" in result["phones"]


class TestIntentClassification:
    """Test Intent Classification into sell, buy, hiring, seeking, news, other."""

    @pytest.fixture
    def extractor(self):
        return SocialEntityExtractor()

    def test_intent_sell(self, extractor):
        text = "Chính chủ cần bán gấp căn hộ 2PN 70m2 chung cư Vinhomes Smart City giá 3.2 tỷ. LH 0912345678"
        intent = extractor.classify_intent(text)
        assert intent == "sell"

    def test_intent_buy(self, extractor):
        text = "Cần tìm mua đất nền khu vực Hoài Đức, tài chính 2-3 tỷ. Ai có nguồn inbox mình."
        intent = extractor.classify_intent(text)
        assert intent == "buy"

    def test_intent_hiring(self, extractor):
        text = "Tuyển dụng 5 nhân viên kinh doanh BĐS tại Quận 1, hoa hồng cao, gửi CV qua email hr@realestate.vn"
        intent = extractor.classify_intent(text)
        assert intent == "hiring"

    def test_intent_seeking(self, extractor):
        text = "Mình đang tìm việc làm môi giới bất động sản hoặc tìm thuê nhà trọ gần Cầu Giấy."
        intent = extractor.classify_intent(text)
        assert intent == "seeking"

    def test_intent_other(self, extractor):
        text = "Hôm nay trời đẹp quá, chúc mọi người ngày mới tràn đầy năng lượng!"
        intent = extractor.classify_intent(text)
        assert intent in ("news", "other")


class TestEntityExtraction:
    """Test extraction of prices, emails, locations and full raw_entities."""

    @pytest.fixture
    def extractor(self):
        return SocialEntityExtractor()

    def test_extract_all_entities(self, extractor):
        text = (
            "Bán nhà phố 5 tầng tại Cầu Giấy, Hà Nội. Diện tích 50m2, giá 12.5 tỷ. "
            "Liên hệ O912.345.678 hoặc email bds.hanoi@gmail.com. Chính chủ bán gấp."
        )
        entities = extractor.extract_all(text)
        assert "0912345678" in entities["phones"]
        assert "bds.hanoi@gmail.com" in entities["emails"]
        assert any("12.5 tỷ" in p.lower() or "12.5" in p for p in entities["prices"])
        assert any("Hà Nội" in loc or "Cầu Giấy" in loc for loc in entities["locations"])
        assert entities["intent"] == "sell"

    def test_email_regex_rejects_invalid_addresses(self, extractor):
        """The email regex should not match obviously invalid addresses."""
        assert extractor.extract_emails("user@.com") == []
        assert extractor.extract_emails("user@com") == []
        assert extractor.extract_emails("@nowhere.com") == []
        assert "valid@example.com" in extractor.extract_emails("valid@example.com")
