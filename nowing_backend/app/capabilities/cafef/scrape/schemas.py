"""``cafef.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.proprietary.platforms.cafef.schemas import (
    CafeFFinancials,
    CafeFNewsItem,
    CafeFQuote,
)


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``cafef.scrape``."""

    model_config = ConfigDict(extra="allow")

    symbol: str = Field(..., min_length=1, max_length=20)
    include_financials: bool = True
    include_news: bool = False
    max_news: int = Field(default=10, ge=0, le=50)

    @property
    def estimated_units(self) -> int:
        """One successful CafeF scrape is one billable unit."""
        return 1


class ScrapeOutput(BaseModel):
    """Capability-level output, extended by the proprietary typed models."""

    model_config = ConfigDict(extra="allow")

    quote: CafeFQuote | None = None
    financials: CafeFFinancials | None = None
    news: list[CafeFNewsItem] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    total_items: int = 0

    @computed_field
    @property
    def billable_units(self) -> int:
        """One returned quote = one billable unit."""
        return 0 if self.degraded or self.quote is None else 1

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
