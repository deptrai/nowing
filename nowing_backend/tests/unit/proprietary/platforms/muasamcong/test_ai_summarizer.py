"""Unit tests for AI Summarizer & Countdown Timer (Story 16.5 / AC-4 / AD-PROC-8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.proprietary.platforms.muasamcong.ai_summarizer import (
    CountdownInfo,
    ExecutiveSummary,
    ProcurementAISummarizer,
)

pytestmark = pytest.mark.unit


class TestProcurementAISummarizer:
    """AC-4: 4 core qualification criteria extraction & countdown status calculation."""

    def test_countdown_calculation_future_urgent(self):
        summarizer = ProcurementAISummarizer()
        # Closing in 24 hours -> urgent (< 48h)
        close_time = datetime.now(UTC) + timedelta(hours=24)
        info: CountdownInfo = summarizer.calculate_countdown(close_time)

        assert info.is_closed is False
        assert info.is_urgent is True
        assert info.hours_remaining < 48
        assert "giờ" in info.countdown_text or "ngày" in info.countdown_text

    def test_countdown_calculation_future_normal(self):
        summarizer = ProcurementAISummarizer()
        # Closing in 5 days -> normal (not urgent)
        close_time = datetime.now(UTC) + timedelta(days=5, hours=2)
        info: CountdownInfo = summarizer.calculate_countdown(close_time)

        assert info.is_closed is False
        assert info.is_urgent is False
        assert info.hours_remaining > 48
        assert "ngày" in info.countdown_text

    def test_countdown_calculation_closed(self):
        summarizer = ProcurementAISummarizer()
        # Past closing time
        close_time = datetime.now(UTC) - timedelta(hours=2)
        info: CountdownInfo = summarizer.calculate_countdown(close_time)

        assert info.is_closed is True
        assert info.is_urgent is False
        assert info.hours_remaining == 0
        assert "Đã đóng thầu" in info.countdown_text

    @pytest.mark.asyncio
    async def test_extract_qualification_criteria_rule_and_llm(self):
        summarizer = ProcurementAISummarizer()

        raw_hsmt_text = """
        Chương III. TIÊU CHUẨN ĐÁNH GIÁ
        1. Năng lực tài chính:
        - Doanh thu bình quân 3 năm gần nhất (2023, 2024, 2025): tối thiểu 50.000.000.000 VND.
        2. Kinh nghiệm thực hiện hợp đồng tương tự:
        - Đã thực hiện tối thiểu 2 hợp đồng xây lắp công trình cấp 2 tương tự, giá trị >= 25 tỷ VND.
        3. Nhân sự chủ chốt:
        - 01 Chỉ huy trưởng có chứng chỉ hành nghề, kinh nghiệm >= 5 năm.
        - 01 Cán bộ kỹ thuật phụ trách ATLĐ.
        4. Bảo đảm dự thầu:
        - Số tiền bảo đảm dự thầu: 500.000.000 VND bằng thư bảo lãnh ngân hàng.
        """

        summary: ExecutiveSummary = await summarizer.summarize_hsmt(
            bid_no="IB2400123456",
            raw_text=raw_hsmt_text,
            bid_closing_at=datetime.now(UTC) + timedelta(hours=36),
        )

        assert summary.bid_no == "IB2400123456"
        assert summary.countdown.is_urgent is True
        assert "50.000.000.000" in summary.qualification.annual_turnover or "50" in summary.qualification.annual_turnover
        assert "2 hợp đồng" in summary.qualification.similar_contracts or "2" in summary.qualification.similar_contracts
        assert "Chỉ huy trưởng" in summary.qualification.key_personnel
        assert "500.000.000" in summary.qualification.bid_security
