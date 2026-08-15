"""Pydantic schemas for Spatial Planning and Land Zoning queries (Story 10.8 / AD-GIS-2 / AD-GIS-5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LandZoningPolarity(StrEnum):
    """UI Polarity classification for zoning categories (Widget U5 / AD-GIS-7)."""

    SAFE = "safe"              # Green: ODT, ONT (Residential)
    DANGER = "danger"          # Red: DGT (Road expansion clearance risk)
    WARNING = "warning"        # Yellow/Orange: CX (Greenery), CLN, HNK
    COMMERCIAL = "commercial"  # Blue: TMD, SKC (Commercial / Industrial)
    AGRICULTURAL = "agricultural"  # Yellow: CLN, HNK, NTS, RSX
    OTHER = "other"            # Gray: Other types


class PlanningZoneItem(BaseModel):
    """Represents a single intersecting cadastral planning zone."""

    id: int | None = None
    province: str
    district: str | None = None
    ward: str | None = None
    zone_code: str
    zone_name: str
    planning_period: str | None = None
    effective_year: int | None = None
    expiry_year: int | None = None
    legal_document_ref: str | None = None
    polarity: LandZoningPolarity = LandZoningPolarity.OTHER
    polarity_color: str = Field(
        default="gray",
        description="Hex or CSS color code (e.g. green, red, blue, yellow, gray)",
    )


class ZoningCheckResult(BaseModel):
    """Aggregated result of a spatial land zoning verification query."""

    latitude: float
    longitude: float
    has_road_expansion_risk: bool = False
    zones: list[PlanningZoneItem] = Field(default_factory=list)
    summary: str = ""
    risk_notes: list[str] = Field(default_factory=list)
    query_latency_ms: float | None = None
