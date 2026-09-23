"""Schemas for Multi-Seat Team CRM Pipeline, OCC, and Timeline Logs (Story 24.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    lead_ids: list[UUID] = Field(..., min_length=1)

    @field_validator("lead_ids", mode="after")
    @classmethod
    def _dedupe_lead_ids(cls, v: list[UUID]) -> list[UUID]:
        """Remove duplicate IDs while preserving submission order."""
        seen: set[UUID] = set()
        deduped: list[UUID] = []
        for x in v:
            if x not in seen:
                seen.add(x)
                deduped.append(x)
        return deduped


class MemberSpendCapUpdateRequest(BaseModel):
    monthly_spend_cap_micros: int | None = Field(None, ge=0)


class MemberLeadCapacityUpdateRequest(BaseModel):
    is_accepting_leads: bool
    lead_capacity: int = Field(50, ge=1, le=1000)


class MeetingSlotProposal(BaseModel):
    """One proposed meeting slot (Story 37.3 / AC-3)."""

    start: datetime
    end: datetime
    label: str  # ICT rendering, e.g. "14:00 Thứ Ba"


class MeetingSlotsResponse(BaseModel):
    slots: list[MeetingSlotProposal]
    provider: str | None = None


class MeetingBookRequest(BaseModel):
    """Manual/CRM booking of a concrete slot for a lead (Story 37.3 / AC-4)."""

    start: datetime
    duration_minutes: int = Field(30, ge=15, le=240)
    summary: str | None = Field(None, max_length=200)
    attendee_email: EmailStr | None = None

    @field_validator("start", mode="after")
    @classmethod
    def _start_must_be_aware_and_future(cls, v: datetime) -> datetime:
        """Backend stores tz-aware UTC; naive values are rejected (422)."""
        if v.tzinfo is None:
            raise ValueError("start must be timezone-aware (ISO-8601)")
        # Same minimum notice as the auto-reply proposal flow.
        from app.services.meeting_booking import MIN_NOTICE_MINUTES

        if v <= datetime.now(UTC) + timedelta(minutes=MIN_NOTICE_MINUTES):
            raise ValueError(
                f"start must be at least {MIN_NOTICE_MINUTES} minutes "
                "in the future"
            )
        return v


class MeetingBookResponse(BaseModel):
    booked: bool
    event_id: str | None = None
    meeting_link: str | None = None
    lead_status: str | None = None
    reason: str | None = None
