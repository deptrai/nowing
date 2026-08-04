"""Pydantic I/O schemas for the Vietnam BĐS aggregator."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class VnBdsProvenance(BaseModel):
    """Soft provenance link so each fact can be re-validated (AD-11.1)."""

    model_config = ConfigDict(extra="allow")

    source_capability: str = "vn_bds.aggregate"
    source_input: dict[str, Any] | None = None
    source_run_id: str | None = None


class ConflictFlag(BaseModel):
    """One detected conflict on an aggregated listing."""

    model_config = ConfigDict(extra="allow")

    type: Literal["price_conflict"] = "price_conflict"
    reason: str
    price_range: dict[str, int | None] = Field(default_factory=dict)
    price_sources: dict[str, int | None] = Field(default_factory=dict)


class VnBdsAggregatedListing(BaseModel):
    """A single normalized listing that may be backed by multiple sources."""

    model_config = ConfigDict(extra="allow")

    canonical_id: str
    source_ids: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    price: str | None = None
    price_value: int | None = None
    price_per_m2: float | None = None
    area: str | None = None
    area_value: float | None = None
    location: str | None = None
    district: str | None = None
    ward: str | None = None
    city: str | None = None
    project: str | None = None
    legal: str | None = None
    post_date: str | None = None
    contact: str | None = None
    phone_key: str | None = Field(default=None, exclude=True)
    address_key: str | None = Field(default=None, exclude=True)
    image_key: str | None = Field(default=None, exclude=True)
    source_prices: dict[str, int | None] = Field(default_factory=dict, exclude=True)
    thumbnail_url: str | None = None
    detail_urls: dict[str, str | None] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    source_count: int = Field(default=0)
    source_trust: float | None = None
    overlap_score: float | None = None
    freshness_score: float | None = None
    price_consistency_score: float | None = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    conflict_flags: list[ConflictFlag] = Field(default_factory=list)
    provenance: VnBdsProvenance | None = None


class VnBdsAggregateInput(BaseModel):
    """Input for ``vn_bds.aggregate``."""

    model_config = ConfigDict(extra="allow")

    sources: list[Literal["batdongsan", "chotot_bds", "muaban_bds"]] = Field(
        default_factory=lambda: ["batdongsan", "chotot_bds", "muaban_bds"]
    )
    listing_type: Literal["buy", "rent"] = "buy"
    property_type: Literal["apartment", "house", "land", "office", "all"] = "all"
    city: str
    district: str | None = None
    district_id: int | None = None
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_area: int | None = Field(default=None, ge=0)
    max_area: int | None = Field(default=None, ge=0)
    max_items_per_source: int = Field(default=10, ge=0, le=100)
    max_pages: int = Field(default=5, ge=0, le=20)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    resolve_phones: bool = True

    @field_validator("sources")
    @classmethod
    def _sources_must_be_nonempty_and_known(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sources cannot be empty")
        allowed = {"batdongsan", "chotot_bds", "muaban_bds"}
        invalid = [s for s in value if s not in allowed]
        if invalid:
            raise ValueError(f"invalid sources: {invalid}")
        return value

    @model_validator(mode="after")
    def _price_and_area_bounds(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")
        if (
            self.min_area is not None
            and self.max_area is not None
            and self.min_area > self.max_area
        ):
            raise ValueError("min_area cannot be greater than max_area")
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable child items for the pre-flight gate."""
        return self.max_items_per_source * len(self.sources)


class VnBdsAggregateOutput(BaseModel):
    """Output of ``vn_bds.aggregate``."""

    model_config = ConfigDict(extra="allow")

    items: list[VnBdsAggregatedListing] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)
    source_breakdown: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        """Return the aggregate listing count for any generic biller."""
        return self.total_items
