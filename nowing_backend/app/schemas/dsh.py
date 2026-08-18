from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DshMissionStatus = Literal[
    "pending",
    "running",
    "success",
    "error",
    "cancelled",
    "dlq",
]
DshMissionType = Literal["deep_lead_research", "noop"]


class DshMissionPayload(BaseModel):
    """The sidecar-visible payload that drives the mission."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(
        ...,
        min_length=1,
        description="The research question or topic.",
    )
    workspace_id: int | None = None
    extras: dict = Field(default_factory=dict)


class DshMissionRequest(BaseModel):
    """Create a new long-running DSH mission."""

    mission_type: DshMissionType = "deep_lead_research"
    payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_payload(self) -> DshMissionRequest:
        if self.mission_type == "deep_lead_research":
            payload_model = DshMissionPayload.model_validate(self.payload)
            if not payload_model.query or not payload_model.query.strip():
                raise ValueError("query is required for deep_lead_research missions")
        return self


class DshMissionCheckpointUpdate(BaseModel):
    """Patch a mission checkpoint from the sidecar."""

    checkpoint: dict | None = None
    phase: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    current_subtask_id: str | None = None
    status: DshMissionStatus | None = None
    retry_count: int | None = None
    error: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DshMissionResponse(BaseModel):
    """Public, PII-safe mission summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    mission_type: str
    status: str
    phase: str | None
    progress_percent: int | None
    current_subtask_id: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class DshMissionInternalResponse(DshMissionResponse):
    """Full mission response for the authenticated sidecar."""

    user_id: UUID | None
    payload: dict
    checkpoint: dict | None
    error: dict | None
    started_at: datetime | None
    completed_at: datetime | None


class TokenVelocity(BaseModel):
    """Aggregated token/cost summary for the Glass Box widget."""

    tokens_total: int = 0
    tokens_per_second: float = 0.0
    cost_micros: int = 0
    cost_credits: float = 0.0


class DshMissionSubtask(BaseModel):
    """Redacted subtask snapshot shown in the public control view."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    status: str
    phase: str | None = None
    reasoning_content: str | None = None
    tokens_used: int = 0
    tokens_per_second: float = 0.0
    run_id: str | None = None
    cost_micros: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DshMissionControlResponse(DshMissionResponse):
    """Public, PII-safe mission control payload with token velocity and subtasks."""

    token_velocity: TokenVelocity
    subtasks: list[DshMissionSubtask]


class DshMissionListResponse(BaseModel):
    """Paginated list of DSH missions."""

    items: list[DshMissionResponse]
    total: int
    limit: int
    offset: int
