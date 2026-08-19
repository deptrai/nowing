"""Unit tests for LeadExtractionService hermetic local extraction."""

import pytest

pytestmark = pytest.mark.unit


class TestLeadExtractionService:
    """Hermetic unit tests for LeadExtractionService extracting phones and tax codes."""

    async def test_extract_from_text_with_phones_and_tax_code(self):
        """Extracts normalized phones, tax IDs, company name, and tax_ids_valid flags."""
        from app.services.lead_extraction_service import LeadExtractionService

        text = """
        TẬP ĐOÀN VIỄN THÔNG QUÂN ĐỘI
        Mã số thuế: 0100109106
        Hotline hỗ trợ: o908 123 456 hoặc +84 912 345 678
        Địa chỉ: Số 1 Giang Văn Minh, Ba Đình, Hà Nội
        """
        service = LeadExtractionService()
        result = await service.extract_from_text(text)

        assert "0908123456" in result.phones
        assert "0912345678" in result.phones
        assert "0100109106" in result.tax_ids
        assert result.tax_ids_valid == [True]
        assert result.company_name is not None

    async def test_extract_from_text_empty_returns_empty_entities(self):
        """Empty input text returns empty entity lists without errors."""
        from app.services.lead_extraction_service import LeadExtractionService

        service = LeadExtractionService()
        result = await service.extract_from_text("")

        assert result.phones == []
        assert result.tax_ids == []
        assert result.tax_ids_valid == []
        assert result.company_name is None

    async def test_extract_from_text_invalid_tax_code_flagged_false(self):
        """Tampered tax code is returned in tax_ids but marked False in tax_ids_valid."""
        from app.services.lead_extraction_service import LeadExtractionService

        text = "Mã số doanh nghiệp giả mạo: 0100109105 liên hệ 0988776655"
        service = LeadExtractionService()
        result = await service.extract_from_text(text)

        assert "0100109105" in result.tax_ids
        assert result.tax_ids_valid == [False]
        assert "0988776655" in result.phones
