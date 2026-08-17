"""Pydantic schemas for Sequence Bounded Context (Story 24.1 / AD-39 / AD-41)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SequenceStatus = Literal["active", "paused", "archived"]
SequenceStepType = Literal["send_email", "wait", "condition", "update_lead_score", "update_crm", "tag"]
SequenceChannel = Literal["email"]
SequenceEventType = Literal["sent", "delivered", "opened", "replied", "bounced", "meeting_booked", "failed", "skipped"]
SequenceEnrollmentStatus = Literal["scheduled", "executing", "paused", "responded", "unsubscribed", "failed", "completed"]


class SequenceStepBase(BaseModel):
    step_order: int = Field(..., ge=1, description="1-indexed step order in sequence")
    step_type: SequenceStepType = Field(..., description="send_email, wait, condition, update_lead_score, update_crm, tag")
    channel: SequenceChannel = Field("email", description="Outbound channel (email only in MVP)")
    template: dict[str, Any] = Field(default_factory=dict, description="Template config, subject, body, variables")
    wait_duration_seconds: int | None = Field(None, ge=0, description="Delay duration in seconds for wait steps")
    condition_config: dict[str, Any] = Field(default_factory=dict, description="Branching rules and predicate")
    is_enabled: bool = True


class SequenceStepCreate(SequenceStepBase):
    pass


class SequenceStepUpdate(BaseModel):
    step_order: int | None = None
    step_type: SequenceStepType | None = None
    channel: SequenceChannel | None = None
    template: dict[str, Any] | None = None
    wait_duration_seconds: int | None = None
    condition_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class SequenceStepRead(SequenceStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None
    sequence_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class SequenceBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the outreach sequence")
    description: str | None = None
    status: SequenceStatus = Field("active", description="active, paused, archived")
    shared: bool = Field(False, description="Whether sequence is shared across client_ids")
    entry_step_order: int = Field(1, ge=1)


class SequenceCreate(SequenceBase):
    steps: list[SequenceStepCreate] = Field(default_factory=list, description="Ordered step definitions")


class SequenceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: SequenceStatus | None = None
    shared: bool | None = None
    entry_step_order: int | None = None
    steps: list[SequenceStepCreate] | None = None


class SequenceRead(SequenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SequenceDetailRead(SequenceRead):
    steps: list[SequenceStepRead] = Field(default_factory=list)


class SequenceEnrollRequest(BaseModel):
    """Payload to enroll one or more leads into a sequence."""

    lead_ids: list[UUID] = Field(..., min_length=1, description="List of lead UUIDs to enroll")


class SequenceEnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None
    sequence_id: UUID
    lead_id: UUID
    sequence_run_id: UUID | None = None
    current_step: int
    status: SequenceEnrollmentStatus
    scheduled_at: datetime | None = None
    version: int
    last_event_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SequenceEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None
    enrollment_id: UUID
    sequence_id: UUID
    step_id: UUID | None = None
    event_type: SequenceEventType
    event_subtype: str | None = None
    channel: SequenceChannel
    cost_micros: int
    event_metadata: dict[str, Any] | None = None
    provider_msg_id: str | None = None
    created_at: datetime


class SequenceAnalyticsResponse(BaseModel):
    """Aggregated sequence analytics (AC-8)."""

    sequence_id: UUID
    total_enrolled: int = 0
    active_scheduled: int = 0
    delivered_count: int = 0
    responded_count: int = 0
    unsubscribed_count: int = 0
    failed_count: int = 0
    total_cost_micros: int = 0
