"""Pydantic schemas for ZNS templates, sending requests, and logs (Story 23.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ZnsTemplateResponse(BaseModel):
    """Approved ZNS template schema."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    template_id: str
    template_name: str
    preview_image: str | None = None
    price: int = Field(
        default=300, description="Cost in VND per message (approx 0.3 credits)"
    )
    template_schema: list[str] = Field(
        default_factory=list,
        alias="schema",
        description="Required parameter keys",
    )
    sample_data: dict[str, Any] = Field(default_factory=dict)
    status: str = "APPROVED"


class ZnsSendRequest(BaseModel):
    """Request payload to dispatch a ZNS template message."""

    lead_id: UUID | None = None
    phone: str = Field(
        ..., description="Recipient mobile phone number (09xx, 08xx, etc.)"
    )
    template_id: str = Field(..., description="ID of the approved ZNS template")
    template_data: dict[str, Any] = Field(
        default_factory=dict, description="Dynamic parameters for the template"
    )


class ZnsSendResponse(BaseModel):
    """Response returned upon successful ZNS message dispatch."""

    status: str
    msg_id: str
    log_id: str | None = None
    phone: str
    template_id: str
    cost_micros: int


class ZnsLogItem(BaseModel):
    """ZNS sent message log item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    lead_id: UUID | None = None
    recipient_phone: str | None = None
    message_type: str
    content: str | None = None
    status: str
    external_message_id: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
