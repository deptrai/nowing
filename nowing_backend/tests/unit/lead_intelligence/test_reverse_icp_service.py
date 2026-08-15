"""Red-phase unit tests for ReverseIcpService (Story 21.10)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

# Target module to be implemented in Story 21.10:
# from app.lead_intelligence.reverse_icp import ReverseIcpService
# from app.lead_intelligence.schemas import ReverseIcpResponse

pytestmark = pytest.mark.unit


MOCK_CRAWLED_DATA = {
    "url": "https://vinhomes.vn",
    "domain": "vinhomes.vn",
    "title": "Vinhomes Ocean Park - Thành phố Biển Hồ",
    "meta_description": "Đại đô thị sinh thái thông minh đẳng cấp quốc tế.",
    "og_tags": {
        "og:title": "Vinhomes Ocean Park",
        "og:description": "Khu đô thị sinh thái",
        "og:image": "https://vinhomes.vn/og.jpg",
        "og:site_name": "Vinhomes",
    },
    "json_ld": [
        {
            "@type": "RealEstateListing",
            "name": "Vinhomes Ocean Park",
            "description": "Biệt thự & Chung cư cao cấp",
        }
    ],
    "headings": ["Vinhomes Ocean Park", "Tiện ích đẳng cấp 5 sao", "Chính sách bán hàng 2026"],
    "clean_text": "Vinhomes Ocean Park mang đến chuẩn sống nghỉ dưỡng giữa lòng thủ đô...",
    "crawl_latency_ms": 320,
}

MOCK_LLM_JSON_PAYLOAD = {
    "company_name": "Vinhomes",
    "domain": "vinhomes.vn",
    "value_proposition": "Chủ đầu tư bất động sản đô thị phức hợp và nghỉ dưỡng số 1 Việt Nam với hệ sinh thái All-In-One.",
    "industry": "Bất động sản cao cấp",
    "target_buyer_personas": [
        {
            "title": "Nhà đầu tư cá nhân / Mua ở thực",
            "industry": "Kinh doanh tự do / C-Level",
            "company_size": "Cá nhân có tài chính > 5 tỷ",
            "pain_points": ["Thiếu không gian sống xanh", "Áp lực giao thông nội đô"],
            "buying_triggers": ["Chính sách hỗ trợ lãi suất 0%", "Khai trương Vincom/Trường học"],
        },
        {
            "title": "Giám đốc Sàn Giao Dịch BĐS",
            "industry": "Môi giới BĐS",
            "company_size": "20-100 nhân viên",
            "pain_points": ["Khó khăn tìm nguồn hàng sạch", "Cạnh tranh hoa hồng"],
            "buying_triggers": ["Dự án mở bán phân khu mới"],
        },
        {
            "title": "Chủ doanh nghiệp tìm mặt bằng Shophouse",
            "industry": "F&B / Bán lẻ",
            "company_size": "10-50 nhân viên",
            "pain_points": ["Mặt bằng phố cổ đắt đỏ", "Thiếu bãi đỗ xe"],
            "buying_triggers": ["Cư dân lấp đầy phân khu cao tầng"],
        },
    ],
    "suggested_search_queries": [
        "Mua biệt thự Vinhomes Ocean Park Gia Lâm",
        "Chính chủ bán chung cư Sapphire Ocean Park",
        "Mặt bằng kinh doanh Shophouse Vinhomes",
        "Nhà đầu tư tìm mua biệt thự song lập Hà Nội",
        "Tìm môi giới F1 Vinhomes 2026",
    ],
    "negative_keywords": ["nhà trọ sinh viên", "cho thuê phòng trọ", "đất nông nghiệp"],
    "filter_presets": {
        "platforms": ["batdongsan", "chotot", "facebook"],
        "intent": "BÁN",
        "target_industries": ["Bất động sản", "Đầu tư", "F&B"],
        "locations": ["Hà Nội", "Hưng Yên"],
        "company_size_range": "Cá nhân & Doanh nghiệp vừa",
    },
    "chat_starter_prompts": [
        "Tìm 30 bài đăng rao bán biệt thự Vinhomes Ocean Park trong 7 ngày qua kèm SĐT",
        "Quét nhóm Facebook BĐS Hà Nội tìm khách hàng có nhu cầu mua nhà trên 5 tỷ",
        "Lọc danh sách các sàn giao dịch BĐS đang phân phối dự án Vinhomes",
    ],
    "raw_metadata": {"crawl_latency_ms": 320},
}


class TestReverseIcpService:
    """Test ReverseIcpService LLM execution, caching, and fallback parsing."""

    @pytest.mark.asyncio
    async def test_analyze_url_returns_cached_result_if_exists(self) -> None:
        """Should return cached ReverseIcpResponse if found in Redis."""
        from app.lead_intelligence.reverse_icp import ReverseIcpService
        from app.lead_intelligence.schemas import ReverseIcpResponse

        service = ReverseIcpService()

        with patch.object(
            service, "_get_from_cache", AsyncMock(return_value=MOCK_LLM_JSON_PAYLOAD)
        ), patch.object(service, "_fetch_and_parse_crawl", AsyncMock()) as mock_crawl:
            result = await service.analyze_url("https://vinhomes.vn")

            assert isinstance(result, ReverseIcpResponse)
            assert result.company_name == "Vinhomes"
            assert result.domain == "vinhomes.vn"
            # Crawler should NOT be called on cache hit
            mock_crawl.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_url_executes_crawl_and_llm_on_cache_miss(self) -> None:
        """Should crawl web, call LLM, cache result, and return ReverseIcpResponse on cache miss."""
        from app.lead_intelligence.reverse_icp import ReverseIcpService
        from app.lead_intelligence.schemas import ReverseIcpResponse

        service = ReverseIcpService()

        with patch.object(service, "_get_from_cache", AsyncMock(return_value=None)), patch.object(
            service, "_fetch_and_parse_crawl", AsyncMock(return_value=MOCK_CRAWLED_DATA)
        ), patch.object(
            service, "_call_llm_for_icp", AsyncMock(return_value=MOCK_LLM_JSON_PAYLOAD)
        ), patch.object(service, "_save_to_cache", AsyncMock()) as mock_save_cache:
            result = await service.analyze_url("https://vinhomes.vn")

            assert isinstance(result, ReverseIcpResponse)
            assert result.company_name == "Vinhomes"
            assert len(result.target_buyer_personas) == 3
            assert len(result.suggested_search_queries) == 5
            assert result.filter_presets.intent == "BÁN"
            assert len(result.chat_starter_prompts) == 3
            # Cache save should be triggered with TTL 3600
            mock_save_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_parser_handles_markdown_codeblocks(self) -> None:
        """Should parse raw LLM output wrapped in ```json ... ``` fences."""
        from app.lead_intelligence.reverse_icp import ReverseIcpService

        service = ReverseIcpService()
        raw_output = f"Here is the ICP analysis:\n```json\n{json.dumps(MOCK_LLM_JSON_PAYLOAD)}\n```\nHope this helps!"

        parsed = service._parse_llm_json_response(raw_output)
        assert parsed["company_name"] == "Vinhomes"
        assert parsed["industry"] == "Bất động sản cao cấp"

    @pytest.mark.asyncio
    async def test_json_parser_handles_trailing_comments_and_dirty_text(self) -> None:
        """Should extract valid JSON even with leading or trailing text."""
        from app.lead_intelligence.reverse_icp import ReverseIcpService

        service = ReverseIcpService()
        raw_output = f"Analysis result: {json.dumps(MOCK_LLM_JSON_PAYLOAD)} (End of JSON)"

        parsed = service._parse_llm_json_response(raw_output)
        assert parsed["company_name"] == "Vinhomes"
        assert len(parsed["target_buyer_personas"]) == 3
