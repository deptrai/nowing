"""Executor for procurement.summarize capability (Story 16.5 / AC-5 / AD-PROC-7)."""

from __future__ import annotations

import logging
from typing import Any

from app.capabilities.procurement.summarize.schemas import (
    ProcurementSummarizeInput,
    ProcurementSummarizeOutput,
)
from app.proprietary.platforms.muasamcong.ai_summarizer import ProcurementAISummarizer
from app.proprietary.platforms.muasamcong.scraper import MuasamcongScraper

logger = logging.getLogger(__name__)


def build_procurement_summarize_executor(
    scraper: MuasamcongScraper | None = None,
    summarizer: ProcurementAISummarizer | None = None,
):
    """Factory creating the async executor for summarizing tender qualification criteria."""
    _scraper = scraper or MuasamcongScraper()
    _summarizer = summarizer or ProcurementAISummarizer()

    async def execute_procurement_summarize(
        input_data: ProcurementSummarizeInput | dict[str, Any]
    ) -> ProcurementSummarizeOutput:
        if isinstance(input_data, dict):
            input_data = ProcurementSummarizeInput.model_validate(input_data)

        # 1. Fetch detail specs
        tender_item = await _scraper.get_tender_detail(
            bid_no=input_data.bid_no,
            bid_turn_no=input_data.bid_turn_no,
        )

        raw_text_parts = []
        project_name = None
        procuring_entity = None
        investor = None
        bid_price = None
        bid_closing_at = None

        if tender_item:
            project_name = tender_item.project_name
            procuring_entity = tender_item.procuring_entity
            investor = tender_item.investor
            bid_price = tender_item.bid_price
            bid_closing_at = tender_item.bid_closing_at

            if tender_item.raw_specs:
                for k, v in tender_item.raw_specs.items():
                    raw_text_parts.append(f"{k}: {v}")

        raw_text = "\n".join(raw_text_parts)

        degraded = False
        degradation_reason = None
        if not tender_item:
            degraded = True
            degradation_reason = f"Không tìm thấy thông tin gói thầu {input_data.bid_no} ({input_data.bid_turn_no}) hoặc cổng e-GP phản hồi chậm."

        # 2. Extract 4 criteria + countdown
        summary = await _summarizer.summarize_hsmt(
            bid_no=input_data.bid_no,
            bid_turn_no=input_data.bid_turn_no,
            raw_text=raw_text,
            bid_closing_at=bid_closing_at,
            procuring_entity=procuring_entity,
        )

        return ProcurementSummarizeOutput(
            bid_no=input_data.bid_no,
            bid_turn_no=input_data.bid_turn_no,
            project_name=project_name,
            procuring_entity=procuring_entity,
            investor=investor,
            bid_price=bid_price,
            qualification=summary.qualification,
            countdown=summary.countdown,
            summary_notes=summary.summary_notes,
            degraded=degraded,
            degradation_reason=degradation_reason,
        )

    return execute_procurement_summarize
