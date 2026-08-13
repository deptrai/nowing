"""Input/output models for the CafeF financial data scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CafeFFinancialLineItem(BaseModel):
    """One named financial metric across reporting periods."""

    model_config = ConfigDict(extra="allow")

    code: str
    name: str
    values: list[float | None] = Field(default_factory=list)


class CafeFFinancialReport(BaseModel):
    """A single report (balance sheet, income statement, cash flow)."""

    model_config = ConfigDict(extra="allow")

    periods: list[str] = Field(default_factory=list)
    items: list[CafeFFinancialLineItem] = Field(default_factory=list)
    key_metrics: dict[str, list[float | None]] = Field(default_factory=dict)
    unit: str = "VND"
    source_url: str | None = None


class CafeFFinancials(BaseModel):
    """Balance sheet, income statement, and cash flow for one symbol."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["cafef_financials"] = "cafef_financials"  # noqa: N815
    symbol: str
    balance_sheet: CafeFFinancialReport = Field(default_factory=CafeFFinancialReport)
    income_statement: CafeFFinancialReport = Field(default_factory=CafeFFinancialReport)
    cash_flow: CafeFFinancialReport = Field(default_factory=CafeFFinancialReport)

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class CafeFQuote(BaseModel):
    """Current price, OHLCV, and key ratios for a stock."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["cafef_quote"] = "cafef_quote"  # noqa: N815
    symbol: str
    name: str | None = None
    exchange: str | None = None
    current_price: float | None = None
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    change: float | None = None
    change_percent: float | None = None
    timestamp: str | None = None
    key_ratios: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class CafeFNewsItem(BaseModel):
    """One CafeF market-news article."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["cafef_news_item"] = "cafef_news_item"  # noqa: N815
    title: str
    url: str | None = None
    published_at: str | None = None
    summary: str | None = None
    source: str = "cafef"
    symbol: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class CafeFScrapeInput(BaseModel):
    """Proprietary scraper input."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    include_financials: bool = True
    include_news: bool = False
    max_news: int = Field(default=10, ge=0, le=50)

    @property
    def estimated_units(self) -> int:
        """One successful CafeF scrape is one billable unit."""
        return 1


class CafeFScrapeOutput(BaseModel):
    """Scraper-level output."""

    model_config = ConfigDict(extra="allow")

    quote: CafeFQuote | None = None
    financials: CafeFFinancials | None = None
    news: list[CafeFNewsItem] = Field(default_factory=list)
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """Quote returned successfully = one billable unit."""
        return 0 if self.degraded or self.quote is None else 1
