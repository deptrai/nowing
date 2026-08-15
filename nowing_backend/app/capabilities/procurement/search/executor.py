"""Executor for procurement.search capability (Story 16.5 / AC-5 / AD-PROC-7)."""

from __future__ import annotations

import logging
from typing import Any

from app.capabilities.procurement.search.schemas import (
    ProcurementSearchInput,
    ProcurementSearchOutput,
)
from app.proprietary.platforms.muasamcong.scraper import MuasamcongScraper

logger = logging.getLogger(__name__)


def build_procurement_search_executor(scraper: MuasamcongScraper | None = None):
    """Factory creating the async executor for searching tenders."""
    _scraper = scraper or MuasamcongScraper()

    async def execute_procurement_search(input_data: ProcurementSearchInput | dict[str, Any]) -> ProcurementSearchOutput:
        if isinstance(input_data, dict):
            input_data = ProcurementSearchInput.model_validate(input_data)

        result = await _scraper.search_tenders(
            keyword=input_data.keyword,
            field=input_data.field,
            min_price=input_data.min_price,
            max_price=input_data.max_price,
            location=input_data.location,
            page=input_data.page,
            size=input_data.size,
        )

        return ProcurementSearchOutput(
            tenders=result.items,
            total_count=result.total_elements,
            page=result.page_number,
            size=result.page_size,
            degraded=result.degraded,
            degradation_reason=result.degradation_reason,
        )

    return execute_procurement_search
