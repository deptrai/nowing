"""Unit tests for Telegram Entity Extractor & Intent Classifier (Story 22.1 / AD-4)."""

from __future__ import annotations

from app.proprietary.platforms.telegram.entity_extractor import (
    TelegramEntityExtractor,
    classify_intent,
    extract_emails,
    extract_hashtags,
    extract_phone_numbers,
    extract_prices,
)


def test_extract_phone_numbers() -> None:
    """Test extracting Vietnamese phone numbers in various formats."""
    text = (
        "Liên hệ chính chủ: 0912345678 hoặc +84988123456 hoặc 84901234567. "
        "Số phụ: 098.765.4321, 093 111 2222, 079-888-9999. "
        "Không bắt nhầm ngày 20260815 hay mã 123456."
    )
    phones = extract_phone_numbers(text)
    assert "0912345678" in phones
    assert "0988123456" in phones or "+84988123456" in phones
    assert "0987654321" in phones
    assert "0931112222" in phones
    assert "0798889999" in phones
    assert "20260815" not in phones
    assert "123456" not in phones


def test_extract_emails() -> None:
    """Test extracting email addresses from text."""
    text = "Mọi thông tin xin gửi về email: contact@batdongsan.vn hoặc support.team@domain.com.vn"
    emails = extract_emails(text)
    assert "contact@batdongsan.vn" in emails
    assert "support.team@domain.com.vn" in emails


def test_extract_prices() -> None:
    """Test extracting real estate & transaction prices in VND / USD."""
    text = (
        "Bán nhà 12.5 tỷ, cho thuê 15 triệu/tháng (hoặc 15tr/th). "
        "Căn hộ 850 triệu. Dự án đơn giá 120 tr/m2. Biệt thự $2,500/tháng."
    )
    prices = extract_prices(text)
    assert any("12.5 tỷ" in p or "12.5 ty" in p.lower() for p in prices)
    assert any("15 triệu" in p or "15tr" in p.lower() for p in prices)
    assert any("850 triệu" in p or "850tr" in p.lower() for p in prices)


def test_extract_hashtags() -> None:
    """Test extracting hashtags."""
    text = "Bán nhà đẹp #bds #caugiay #nha_mat_pho #Hanoi2026"
    tags = extract_hashtags(text)
    assert "#bds" in tags
    assert "#caugiay" in tags
    assert "#nha_mat_pho" in tags
    assert "#Hanoi2026" in tags


def test_classify_intent() -> None:
    """Test intent classification logic."""
    assert classify_intent("Bán gấp nhà Cầu Giấy 5 tầng chính chủ...") == "sell"
    assert classify_intent("Chính chủ nhượng lại quán cafe mặt phố...") == "sell"
    assert classify_intent("Pass lại bộ bàn ghế sofa mới 99%...") == "sell"
    assert classify_intent("Cần mua đất nền ven đô tài chính 2 tỷ...") == "buy"
    assert classify_intent("Tìm mua căn hộ 2 phòng ngủ Royal City...") == "buy"
    assert classify_intent("Cần tìm thuê mặt bằng kinh doanh diện tích 100m2...") == "seeking"
    assert classify_intent("Tìm người ở ghép khu vực Cầu Giấy...") == "seeking"
    assert classify_intent("Tin tức thị trường BĐS quý 3/2026: Diễn biến mới...") == "news"
    assert classify_intent("Thông báo lịch cắt điện khu vực...") == "news"


def test_telegram_entity_extractor_full() -> None:
    """Test full extraction pipeline with structured raw_entities."""
    extractor = TelegramEntityExtractor()
    sample_text = (
        "Bán nhà riêng phố Nguyễn Khang, Yên Hòa, Cầu Giấy 45m2 x 4 tầng.\n"
        "Giá bán nhanh: 8.5 tỷ có thương lượng.\n"
        "SĐT / Zalo liên hệ: 0912.888.999 (Mr. Nam).\n"
        "Email nhận sổ đỏ: nam.land@vietnam.vn\n"
        "#bds_caugiay #nhadep"
    )
    result = extractor.extract(sample_text)

    assert result.intent_tag == "sell"
    assert len(result.phone_numbers) == 1
    assert "0912888999" in result.phone_numbers
    assert "nam.land@vietnam.vn" in result.emails
    assert len(result.prices) >= 1
    assert len(result.hashtags) == 2

    # Check raw_entities structure for JSONB compatibility
    entity_types = {e["type"] for e in result.raw_entities}
    assert "phone" in entity_types
    assert "email" in entity_types
    assert "price" in entity_types
    assert "hashtag" in entity_types
