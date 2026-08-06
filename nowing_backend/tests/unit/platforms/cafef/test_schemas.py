"""Pydantic schema checks for the CafeF scraper."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.cafef.schemas import (
    CafeFFinancials,
    CafeFNewsItem,
    CafeFQuote,
    CafeFScrapeInput,
    CafeFScrapeOutput,
)


def test_input_defaults() -> None:
    inp = CafeFScrapeInput(symbol="VCB")
    assert inp.symbol == "VCB"
    assert inp.include_financials is True
    assert inp.include_news is False
    assert inp.max_news == 10


def test_input_max_news_validation() -> None:
    with pytest.raises(ValueError):
        CafeFScrapeInput(symbol="VCB", max_news=-1)


def test_quote_to_output() -> None:
    q = CafeFQuote(symbol="VCB", current_price=80.5)
    out = q.to_output()
    assert out["symbol"] == "VCB"
    assert out["current_price"] == 80.5
    assert out["dataType"] == "cafef_quote"


def test_financials_with_empty_reports() -> None:
    f = CafeFFinancials(symbol="VCB")
    assert f.symbol == "VCB"
    assert f.balance_sheet.periods == []


def test_news_item_defaults() -> None:
    n = CafeFNewsItem(title="test", symbol="VCB")
    assert n.source == "cafef"
    assert n.dataType == "cafef_news_item"


def test_scrape_output_billable_units() -> None:
    out = CafeFScrapeOutput(
        quote=CafeFQuote(symbol="VCB"),
        degraded=False,
    )
    assert out.billable_units == 1

    degraded = CafeFScrapeOutput(degraded=True)
    assert degraded.billable_units == 0

    empty = CafeFScrapeOutput(degraded=False)
    assert empty.billable_units == 0
