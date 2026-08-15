"""Unit tests for Procurement Capabilities and Agent Tools (Story 16.5 / AC-5 / AD-PROC-7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.procurement.search.executor import (
    build_procurement_search_executor,
)
from app.capabilities.procurement.search.schemas import (
    ProcurementSearchInput,
    ProcurementSearchOutput,
)
from app.capabilities.procurement.summarize.executor import (
    build_procurement_summarize_executor,
)
from app.capabilities.procurement.summarize.schemas import (
    ProcurementSummarizeInput,
    ProcurementSummarizeOutput,
)
from app.proprietary.platforms.muasamcong.ai_summarizer import (
    CountdownInfo,
    ExecutiveSummary,
    QualificationCriteria,
)
from app.proprietary.platforms.muasamcong.scraper import (
    ProcurementTenderItem,
    ScrapeResult,
)

pytestmark = pytest.mark.unit


class TestProcurementCapabilities:
    """AC-5: Capability registration and executor mapping for agent tools."""

    @pytest.mark.asyncio
    async def test_procurement_search_executor(self):
        executor = build_procurement_search_executor()

        mock_item = ProcurementTenderItem(
            bid_no="IB2400123456",
            bid_turn_no="00",
            project_name="Gói thầu thiết bị y tế",
            procuring_entity="Bệnh viện Đa khoa",
            investor="Sở Y tế",
            bid_price=5000000000.0,
            field="Thiết bị y tế",
            location="Hà Nội",
            status="active",
        )

        mock_result = ScrapeResult(
            items=[mock_item],
            total_elements=1,
            degraded=False,
        )

        with patch("app.proprietary.platforms.muasamcong.scraper.MuasamcongScraper.search_tenders", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result

            input_data = ProcurementSearchInput(
                keyword="thiết bị y tế",
                field="Thiết bị y tế",
                min_price=1000000000.0,
                max_price=10000000000.0,
                location="Hà Nội",
                page=0,
                size=10,
            )

            output: ProcurementSearchOutput = await executor(input_data)
            assert output.total_count == 1
            assert len(output.tenders) == 1
            assert output.tenders[0].bid_no == "IB2400123456"
            assert output.tenders[0].project_name == "Gói thầu thiết bị y tế"

    @pytest.mark.asyncio
    async def test_procurement_summarize_executor(self):
        executor = build_procurement_summarize_executor()

        mock_item = ProcurementTenderItem(
            bid_no="IB2400123456",
            bid_turn_no="00",
            project_name="Gói thầu xây lắp",
            procuring_entity="Ban Quản lý DA",
            bid_price=20000000000.0,
            field="Xây lắp",
            location="Đà Nẵng",
            status="active",
            raw_specs={"baoDamDuThau": "300.000.000 VND"},
        )

        mock_summary = ExecutiveSummary(
            bid_no="IB2400123456",
            bid_turn_no="00",
            qualification=QualificationCriteria(
                annual_turnover="Tối thiểu 30 tỷ VND",
                similar_contracts="Ít nhất 2 hợp đồng xây lắp",
                key_personnel="01 Chỉ huy trưởng",
                bid_security="300.000.000 VND",
            ),
            countdown=CountdownInfo(
                is_closed=False,
                is_urgent=True,
                hours_remaining=20.5,
                countdown_text="20 giờ 30 phút",
            ),
            procuring_entity="Ban Quản lý DA",
            summary_notes="Gói thầu yêu cầu năng lực xây lắp dân dụng cấp II.",
        )

        with patch("app.proprietary.platforms.muasamcong.scraper.MuasamcongScraper.get_tender_detail", new_callable=AsyncMock) as mock_get_detail, \
             patch("app.proprietary.platforms.muasamcong.ai_summarizer.ProcurementAISummarizer.summarize_hsmt", new_callable=AsyncMock) as mock_sum:

            mock_get_detail.return_value = mock_item
            mock_sum.return_value = mock_summary

            input_data = ProcurementSummarizeInput(
                bid_no="IB2400123456",
                bid_turn_no="00",
            )

            output: ProcurementSummarizeOutput = await executor(input_data)
            assert output.bid_no == "IB2400123456"
            assert output.qualification.annual_turnover == "Tối thiểu 30 tỷ VND"
            assert output.countdown.is_urgent is True
            assert output.qualification.bid_security == "300.000.000 VND"
