"""Unit tests for TelegramEntityExtractor (Story 22.3 / AC-1).

Tests extract Vietnamese phone numbers, price patterns, emails, and location keywords
from raw Telegram message text and normalize them into a structured raw_entities JSONB schema.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-1: Vietnamese Entity Extraction & Schema Normalization
# ---------------------------------------------------------------------------


class TestTelegramEntityExtractorPhone:
    """Test Vietnamese phone number extraction across multiple standard and obfuscated formats."""

    def test_extract_standard_phone_formats(self) -> None:
        """Should extract standard 10-digit VN phone numbers with dots, spaces, dashes, and +84 prefix."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = (
            "Liên hệ chính chủ: 0912.345.678 hoặc +84987654321. "
            "Zalo phụ: 090 123 4567, Hotline: 093-456-7890."
        )
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "phones" in entities
        phones = entities["phones"]
        assert "0912345678" in phones
        assert "0987654321" in phones
        assert "0901234567" in phones
        assert "0934567890" in phones

    def test_extract_obfuscated_phone_formats(self) -> None:
        """Should extract phone numbers with obfuscated letter 'o' or 'O' instead of zero."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Nhắn tin qua Zalo o912.345.678 hoặc O987.654.321 để xem nhà."
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "phones" in entities
        assert "0912345678" in entities["phones"]
        assert "0987654321" in entities["phones"]


class TestTelegramEntityExtractorPrice:
    """Test Vietnamese price pattern extraction and numeric normalization."""

    def test_extract_billion_vnd_prices(self) -> None:
        """Should extract prices in 'tỷ' / 'ty' and normalize to numeric VND value."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Bán gấp biệt thự Ciputra giá 25.5 tỷ, có thương lượng. Căn liền kề 18 tỷ 500tr."
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "prices" in entities
        prices = entities["prices"]
        assert len(prices) >= 2
        # Verify first price
        p1 = next((p for p in prices if p.get("raw_text") == "25.5 tỷ"), None)
        assert p1 is not None
        assert p1["amount_vnd"] == 25_500_000_000
        assert p1["unit"] == "tỷ"

    def test_extract_million_and_thousand_prices(self) -> None:
        """Should extract rental prices in 'triệu/tháng', 'tr/tháng', 'k'."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Cho thuê căn hộ Studio 8.5 triệu/tháng, cọc 1 tháng. Phí dịch vụ 500k/tháng."
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "prices" in entities
        rental = next(
            (p for p in entities["prices"] if "8.5" in p.get("raw_text", "")), None
        )
        assert rental is not None
        assert rental["amount_vnd"] == 8_500_000
        assert rental.get("is_rental") is True


class TestTelegramEntityExtractorEmailAndLocation:
    """Test email and location entity extraction."""

    def test_extract_emails(self) -> None:
        """Should extract valid email addresses from message body."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Gửi CV về hr.nowing@nowing.net hoặc admin@batdongsan-hanoi.vn để ứng tuyển."
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "emails" in entities
        assert "hr.nowing@nowing.net" in entities["emails"]
        assert "admin@batdongsan-hanoi.vn" in entities["emails"]

    def test_extract_location_keywords(self) -> None:
        """Should extract administrative locations (district, province)."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Bán nhà mặt phố Trung Kính, Cầu Giấy, Hà Nội diện tích 60m2."
        entities = TelegramEntityExtractor.extract_entities(text)

        assert "locations" in entities
        locations = entities["locations"]
        assert any("Cầu Giấy" in loc for loc in locations)
        assert any("Hà Nội" in loc for loc in locations)


class TestTelegramEntityExtractorEdgeCases:
    """Test edge cases and defensive fallbacks."""

    def test_empty_or_none_text_returns_empty_schema(self) -> None:
        """Should return a valid empty dictionary schema when input text is empty or None."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        empty_res = TelegramEntityExtractor.extract_entities("")
        assert empty_res == {"phones": [], "prices": [], "emails": [], "locations": []}

        none_res = TelegramEntityExtractor.extract_entities(None)  # type: ignore[arg-type]
        assert none_res == {"phones": [], "prices": [], "emails": [], "locations": []}

    def test_jsonb_schema_structure_compliance(self) -> None:
        """Extracted entity dictionary must adhere to the raw_entities JSONB schema."""
        from app.proprietary.platforms.telegram.entity_extractor import (
            TelegramEntityExtractor,
        )

        text = "Bán nhà Cầu Giấy 10 tỷ, liên hệ 0912345678 email test@example.com"
        entities = TelegramEntityExtractor.extract_entities(text)

        assert isinstance(entities, dict)
        assert isinstance(entities.get("phones"), list)
        assert isinstance(entities.get("prices"), list)
        assert isinstance(entities.get("emails"), list)
        assert isinstance(entities.get("locations"), list)
