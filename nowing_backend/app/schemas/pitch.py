"""Schemas for the public pitch-portal engagement endpoints (Story 37.6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PitchBeaconPayload(BaseModel):
    """Cookieless telemetry body sent via ``navigator.sendBeacon``.

    The beacon POSTs raw JSON (sendBeacon uses ``text/plain``/Blob), so the
    route parses the body manually and validates it with this model.
    """

    dwell_seconds: float = Field(default=0.0, ge=0.0, le=86_400.0)
    sections_viewed: list[str] = Field(default_factory=list, max_length=20)
    device_type: str | None = Field(default=None, max_length=20)
    session_id: str | None = Field(default=None, max_length=64)
    event: str | None = Field(default=None, max_length=20)  # open/heartbeat/close
    extra: dict[str, Any] | None = None


class PitchPortalMetaResponse(BaseModel):
    """Public metadata the SSR pitch page needs to render (sanitized)."""

    lead_id: UUID
    workspace_id: int
    company_name: str
    industry: str | None = None
    location: str | None = None
    workspace_name: str
    booking_path: str
