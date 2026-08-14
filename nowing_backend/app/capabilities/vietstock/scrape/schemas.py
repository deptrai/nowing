"""``vietstock.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.proprietary.platforms.vietstock.schemas import (
    VietstockFinancials,
    VietstockQuote,
)


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``vietstock.scrape``."""

    model_config = ConfigDict(extra="allow")

    symbol: str = Field(..., min_length=1, max_length=20)
    include_financials: bool = True

    @property
    def estimated_units(self) -> int:
        """One successful Vietstock scrape is one billable unit."""
        return 1


class ScrapeOutput(BaseModel):
    """Capability-level output, extended by the proprietary typed models."""

    model_config = ConfigDict(extra="allow")

    quote: VietstockQuote | None = None
    financials: VietstockFinancials | None = None
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None
    total_items: int = 0
    ingest_job_id: str | None = None
    ingest_status: str | None = None

    @computed_field
    @property
    def billable_units(self) -> int:
        """One returned quote = one billable unit."""
        return 0 if self.degraded or self.quote is None else 1

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
