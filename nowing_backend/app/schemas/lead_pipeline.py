"""Schemas for Multi-Seat Team CRM Pipeline, OCC, and Timeline Logs (Story 24.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeadPipelineStageBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=50)
    position: int = 0
    color: str | None = "#3B82F6"
    is_system: bool = False


class LeadPipelineStageCreate(LeadPipelineStageBase):
    pass


class LeadPipelineStageUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    position: int | None = None


class LeadPipelineStageRead(LeadPipelineStageBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    created_at: datetime
    updated_at: datetime | None = None


class LeadStageTransitionRequest(BaseModel):
    """Optimistic Concurrency Control (OCC) stage transition payload."""

    stage_id: UUID
    expected_version: int = Field(..., ge=1, description="Expected OCC version of lead before drag")
    note: str | None = None


class LeadStageTransitionResponse(BaseModel):
    lead_id: UUID
    workspace_id: int
    stage_id: UUID
    version: int
    previous_version: int
    status: str


class LeadActivityLogCreate(BaseModel):
    activity_type: str = Field(..., max_length=50)
    title: str = Field(..., max_length=255)
    details: dict[str, Any] = Field(default_factory=dict)


class LeadActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    lead_id: UUID
    actor_user_id: UUID | None = None
    activity_type: str
    title: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class LeadAssignmentRequest(BaseModel):
    target_user_id: UUID
    reason: str | None = "manual_assignment"


class BatchLeadAssignmentRequest(BaseModel):
    lead_ids: list[UUID]


class MemberSpendCapUpdateRequest(BaseModel):
    monthly_spend_cap_micros: int | None = Field(None, ge=0)


class MemberLeadCapacityUpdateRequest(BaseModel):
    is_accepting_leads: bool
    lead_capacity: int = Field(50, ge=1, le=1000)
