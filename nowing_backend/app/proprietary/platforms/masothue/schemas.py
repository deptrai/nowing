# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the masothue.com company scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MasothueSearchInput(BaseModel):
    """Proprietary scraper input."""

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

    @property
    def estimated_units(self) -> int:
        """Worst-case billable units for the pre-flight credit gate."""
        return self.max_items


class MasothueDegradationReason:
    """Allowed degradation reasons."""

    API_ERROR = "api_error"
    RATE_LIMITED = "rate_limited"
    ACCESS_BLOCKED = "access_blocked"
    DECODE_ERROR = "decode_error"
    EMPTY = "empty"
    AMBIGUOUS_QUERY = "ambiguous_query"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"


class MasothueCompany(BaseModel):
    """One company record from masothue.com."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["masothue_company"] = "masothue_company"
    tax_code: str | None = None
    name: str | None = None
    address: str | None = None
    tax_address: str | None = None
    legal_representative: str | None = None
    status: str | None = None
    company_type: str | None = None
    main_industry: str | None = None
    active_date: str | None = None
    managed_by: str | None = None
    international_name: str | None = None
    short_name: str | None = None
    phone: str | None = None
    detail_url: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to a flat dict for downstream consumers."""
        return self.model_dump(exclude_none=False)


class MasothueScrapeOutput(BaseModel):
    """Scraper-level output (not the capability contract)."""

    model_config = ConfigDict(extra="allow")

    items: list[MasothueCompany] = Field(default_factory=list)
    total_items: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """One returned company = one billable unit."""
        return self.total_items
