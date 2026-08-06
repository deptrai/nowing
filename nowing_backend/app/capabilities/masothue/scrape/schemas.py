"""``masothue.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.proprietary.platforms.masothue.schemas import MasothueCompany


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``masothue.scrape``."""

    model_config = ConfigDict(extra="allow")

    query: str
    search_type: Literal[
        "auto",
        "enterpriseTax",
        "enterpriseName",
        "legalName",
        "personalTax",
        "identity",
    ] = "auto"
    tax_code: str | None = None
    max_pages: int = Field(default=5, ge=0)
    max_items: int = Field(default=10, ge=0)
    resolve_detail: bool = True
    include_phone: bool = False

    @model_validator(mode="after")
    def _clamp_caps(self) -> ScrapeInput:
        # AC-3: over-cap values are clamped, not rejected; 0 is allowed.
        if self.max_items > 100:
            self.max_items = 100
        if self.max_pages > 20:
            self.max_pages = 20
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable units for the pre-flight credit gate."""
        return self.max_items


class ScrapeOutput(BaseModel):
    """Capability-level output, extended by the proprietary typed models."""

    model_config = ConfigDict(extra="allow")

    items: list[MasothueCompany] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        """One returned company = one billable unit."""
        return len(self.items)

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
