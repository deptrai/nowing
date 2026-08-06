"""Unit tests for masothue.scrape executor."""

from __future__ import annotations

from typing import Any

import pytest

from app.capabilities.masothue.scrape.executor import build_scrape_executor
from app.capabilities.masothue.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def _company_data(tax_code: str, name: str) -> dict[str, Any]:
    return {
        "tax_code": tax_code,
        "name": name,
        "address": "10 Đường 3/2",
        "main_industry": "Sản xuất sữa",
    }


@pytest.mark.asyncio
async def test_executor_returns_output_and_cost(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000, raising=False
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn"),
                _company_data("0314539065", "Công ty Cổ phần Sữa Việt Nam"),
            ],
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=2, max_pages=1))

    assert isinstance(out, ScrapeOutput)
    assert out.degraded is False
    assert out.total_items == 2
    assert out.billable_units == 2
    assert out.cost_micros == 2 * 3000



@pytest.mark.asyncio
async def test_executor_returns_zero_cost_when_degraded(monkeypatch: Any) -> None:
    """A degraded run reports cost_micros=0 even when items were returned."""
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000, raising=False
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                {"tax_code": "0314539064", "name": "Công ty TNHH Vinamilk Tân Sơn"},
            ],
            "degraded": True,
            "degradation_reason": "rate_limited",
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.total_items == 1
    assert out.cost_micros == 0