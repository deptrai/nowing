"""Input and output schemas for realestate.zoning capability (Story 10.8 / AD-GIS-6)."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator

from app.proprietary.platforms.spatial_planning.schemas import PlanningZoneItem


class ZoningCheckInput(BaseModel):
    """Input payload for real estate land zoning verification."""

    latitude: float = Field(
        ...,
        ge=8.5,
        le=23.5,
        description="Latitude coordinate in decimal degrees (e.g. 21.0285 for Hanoi, 10.8231 for HCM)",
    )
    longitude: float = Field(
        ...,
        ge=102.0,
        le=109.5,
        description="Longitude coordinate in decimal degrees (e.g. 105.8542 for Hanoi, 106.6297 for HCM)",
    )
    address: str | None = Field(
        default=None,
        description="Optional human-readable cadastral address for display and reporting context",
    )

    @field_validator("latitude", "longitude")
    @classmethod
    def _finite_float(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("Coordinate must be a finite number")
        return value


class ZoningCheckOutput(BaseModel):
    """Output payload summarizing land zoning classification and road clearance risks."""

    latitude: float
    longitude: float
    address: str | None = None
    has_road_expansion_risk: bool = Field(
        default=False,
        description="True if the coordinates intersect a road widening or transportation zone (DGT)",
    )
    zones: list[PlanningZoneItem] = Field(
        default_factory=list,
        description="List of all intersecting planning zones with classification polarity",
    )
    summary: str = Field(
        default="",
        description="Human-readable executive summary of the zoning and legal status in Vietnamese",
    )
    risk_notes: list[str] = Field(
        default_factory=list,
        description="Detailed legal or infrastructure clearance risk warnings",
    )
    query_latency_ms: float | None = Field(
        default=None,
        description="Spatial intersection query latency in milliseconds",
    )
