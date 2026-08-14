"""Input/output models for the Vietstock financial data scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VietstockKeyRatios(BaseModel):
    """Normalized P/E, P/B, ROE, ROA for a stock."""

    model_config = ConfigDict(extra="ignore")

    pe: float | None = None
    pb: float | None = None
    roe: float | None = None
    roa: float | None = None


class VietstockQuote(BaseModel):
    """Current price, OHLCV, and key ratios for a stock."""

    model_config = ConfigDict(extra="ignore")

    dataType: Literal["vietstock_quote"] = "vietstock_quote"  # noqa: N815
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
    key_ratios: VietstockKeyRatios = Field(default_factory=VietstockKeyRatios)
    source_url: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class VietstockFinancialLineItem(BaseModel):
    """One named financial metric across reporting periods."""

    model_config = ConfigDict(extra="allow")

    code: str
    name: str
    values: list[float | None] = Field(default_factory=list)

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class VietstockFinancialReport(BaseModel):
    """A single report (balance sheet, income statement, cash flow)."""

    model_config = ConfigDict(extra="allow")

    statement_type: Literal["balance_sheet", "income_statement", "cash_flow"] | None = (
        None
    )
    periods: list[str] = Field(default_factory=list)
    items: list[VietstockFinancialLineItem] = Field(default_factory=list)
    key_metrics: dict[str, list[float | None]] = Field(default_factory=dict)
    unit: str = "VND"
    source_url: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class VietstockFinancials(BaseModel):
    """Balance sheet, income statement, and cash flow for one symbol."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["vietstock_financials"] = "vietstock_financials"  # noqa: N815
    symbol: str
    balance_sheet: VietstockFinancialReport = Field(
        default_factory=VietstockFinancialReport
    )
    income_statement: VietstockFinancialReport = Field(
        default_factory=VietstockFinancialReport
    )
    cash_flow: VietstockFinancialReport = Field(
        default_factory=VietstockFinancialReport
    )

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class VietstockScrapeInput(BaseModel):
    """Proprietary scraper input."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    include_financials: bool = True

    @property
    def estimated_units(self) -> int:
        """One successful Vietstock scrape is one billable unit."""
        return 1


class VietstockScrapeOutput(BaseModel):
    """Scraper-level output."""

    model_config = ConfigDict(extra="allow")

    quote: VietstockQuote | None = None
    financials: VietstockFinancials | None = None
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """Quote returned successfully = one billable unit."""
        return 0 if self.degraded or self.quote is None else 1
