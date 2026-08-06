"""``cafef.scrape`` executor unit tests."""

from __future__ import annotations

import pytest

from app.capabilities.cafef.scrape.executor import build_scrape_executor
from app.capabilities.cafef.scrape.schemas import ScrapeInput
from app.config import config
from app.proprietary.platforms.cafef.schemas import (
    CafeFFinancials,
    CafeFNewsItem,
    CafeFQuote,
    CafeFScrapeInput,
    CafeFScrapeOutput,
)


async def _fake_scrape(*args, **kwargs) -> CafeFScrapeOutput:
    inp = args[0] if args else kwargs.get("input_model")
    return CafeFScrapeOutput(
        quote=CafeFQuote(symbol=inp.symbol, current_price=80.0),
        financials=CafeFFinancials(symbol=inp.symbol) if inp.include_financials else None,
        news=[CafeFNewsItem(title="n1", symbol=inp.symbol)] if inp.include_news else [],
        degraded=False,
    )


@pytest.fixture
def exec():
    return build_scrape_executor(scrape_fn=_fake_scrape)


async def test_executor_returns_quote_and_financials(exec) -> None:
    out = await exec(ScrapeInput(symbol="VCB", include_financials=True))
    assert out.quote is not None
    assert out.financials is not None
    assert out.quote.symbol == "VCB"
    assert out.degraded is False
    assert out.total_items == 1
    assert out.billable_units == 1


async def test_executor_cost_micros(exec, monkeypatch) -> None:
    monkeypatch.setattr(config, "CAFEF_DATA_MICROS_PER_ITEM", 7500)
    out = await exec(ScrapeInput(symbol="VCB"))
    assert out.cost_micros == 7500


async def test_executor_degraded_is_free() -> None:
    async def _bad(inp: CafeFScrapeInput) -> CafeFScrapeOutput:
        return CafeFScrapeOutput(degraded=True, degradation_reason="api_error")

    exec = build_scrape_executor(scrape_fn=_bad)
    out = await exec(ScrapeInput(symbol="VCB"))
    assert out.degraded is True
    assert out.cost_micros == 0
    assert out.total_items == 0
    assert out.billable_units == 0
