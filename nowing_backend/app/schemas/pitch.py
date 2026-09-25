"""Schemas for the public pitch-portal engagement endpoints (Story 37.6)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PitchBeaconPayload(BaseModel):
    """Cookieless telemetry body sent via ``navigator.sendBeacon``.

    The beacon POSTs raw JSON (sendBeacon uses ``text/plain``/Blob), so the
    route parses the body manually and validates it with this model.
    """

    dwell_seconds: float = Field(default=0.0, ge=0.0, le=86_400.0)
    sections_viewed: list[str] = Field(default_factory=list, max_length=20)
    device_type: str | None = Field(default=None, max_length=20)
    session_id: str | None = Field(default=None, max_length=64)
    event: Literal["open", "heartbeat", "close"] | None = None


class PitchExecCard(BaseModel):
    """One card in the 30-second executive card stack (Story 37.5 / AC-2)."""

    tone: Literal["red", "yellow", "green"]
    title: str = Field(max_length=120)
    body: str = Field(max_length=500)


class PitchRoiDefaults(BaseModel):
    """Seed values for the interactive ROI slider (Story 37.5 / AC-2)."""

    default_sales_reps: int = Field(default=3, ge=1, le=100)
    min_sales_reps: int = Field(default=1, ge=1, le=100)
    max_sales_reps: int = Field(default=20, ge=1, le=500)
    meetings_per_rep_per_month: float = Field(default=5.0, ge=0.0)
    data_saving_per_rep_vnd: int = Field(default=8_000_000, ge=0)

    @model_validator(mode="after")
    def _check_range(self) -> PitchRoiDefaults:
        if not (
            self.min_sales_reps
            <= self.default_sales_reps
            <= self.max_sales_reps
        ):
            raise ValueError(
                "roi defaults require min <= default <= max sales_reps"
            )
        return self


class PitchPortalMetaResponse(BaseModel):
    """Public metadata the SSR pitch page needs to render (sanitized)."""

    lead_id: UUID
    workspace_id: int
    company_name: str
    industry: str | None = None
    location: str | None = None
    workspace_name: str
    booking_path: str
    opt_out_path: str | None = None
    # Generated portal content (Story 37.5).  Optional so the SSR shell still
    # renders when generation was skipped or the cache is cold.
    headline: str | None = None
    exec_summary: str | None = None
    exec_cards: list[PitchExecCard] = Field(default_factory=list)
    logo_url: str | None = None
    roi: PitchRoiDefaults | None = None
