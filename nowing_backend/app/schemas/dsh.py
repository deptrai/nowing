from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DshMissionPayload(BaseModel):
    """The sidecar-visible payload that drives the mission."""

    query: str | None = None
    workspace_id: int | None = None
    extras: dict = Field(default_factory=dict)


class DshMissionRequest(BaseModel):
    """Create a new long-running DSH mission."""

    mission_type: str = "deep_lead_research"
    payload: dict = Field(default_factory=dict)


class DshMissionCheckpointUpdate(BaseModel):
    """Patch a mission checkpoint from the sidecar."""

    checkpoint: dict | None = None
    phase: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    current_subtask_id: str | None = None
    status: str | None = None
    retry_count: int | None = None
    error: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DshMissionResponse(BaseModel):
    """Public, PII-safe mission summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    user_id: UUID | None
    mission_type: str
    status: str
    phase: str | None
    progress_percent: int | None
    current_subtask_id: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
