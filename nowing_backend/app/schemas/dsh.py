from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

DshMissionStatus = Literal[
    "pending",
    "running",
    "success",
    "error",
    "cancelled",
    "dlq",
]
DshMissionType = Literal[
    "deep_lead_research",
    "cdp_browser_operator",
    "recurring_report",
    "noop",
]


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


class BrowserOperatorCdpPayload(BaseModel):
    """Validated payload for a CDP browser operator mission."""

    model_config = ConfigDict(extra="forbid")

    target_url: AnyUrl = Field(..., description="URL the browser operator should navigate to.")
    workspace_id: int | None = None
    extras: dict = Field(default_factory=dict)

    @field_validator("target_url", mode="before")
    @classmethod
    def _reject_non_browser_schemes(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v_str = str(v)
        allowed = ("http://", "https://")
        if not any(v_str.lower().startswith(scheme) for scheme in allowed):
            raise ValueError("target_url must start with http:// or https://")
        return v


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
        elif self.mission_type == "cdp_browser_operator":
            payload_model = BrowserOperatorCdpPayload.model_validate(self.payload)
            # Persist as plain dict, not Pydantic model, for downstream compatibility
            self.payload = payload_model.model_dump(mode="json")
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


class DshMissionDeliverable(BaseModel):
    """Redacted deliverable reference shown in the public control view."""

    model_config = ConfigDict(extra="ignore")

    type: str
    filename: str
    size: int = 0
    created_at: str | None = None
    include_pii: bool = False
    sources_count: int = 0
    topics_count: int = 0


class DshMissionControlResponse(DshMissionResponse):
    """Public, PII-safe mission control payload with token velocity, subtasks, and deliverables."""

    token_velocity: TokenVelocity
    subtasks: list[DshMissionSubtask]
    deliverables: list[DshMissionDeliverable] = []
    challenge: str | None = None
    takeover_target_url: str | None = None
    takeover_expires_at: datetime | None = None


class DshMissionListResponse(BaseModel):
    """Paginated list of DSH missions."""

    items: list[DshMissionResponse]
    total: int
    limit: int
    offset: int


class DshNotifyHighFitRequest(BaseModel):
    """Request payload for internal worker notification of high-fit lead."""

    model_config = ConfigDict(extra="forbid")

    lead_id: UUID
    contact_id: UUID | None = None


class DshNotifyHighFitResponse(BaseModel):
    """Response payload for internal high-fit lead notification."""

    status: Literal["sent", "skipped", "failed"]
    callback_token: str | None = None
    contact_id: UUID | None = None
    message_id: str | None = None
    reason: str | None = None
    error: str | None = None

class CdpResultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
    result: dict | None = None
    error: str | None = None
    requires_human: bool = False
    challenge: str | None = None

    @field_validator("result", mode="before")
    @classmethod
    def _limit_result_size(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        # Whitelist top-level keys and drop arbitrary large blobs; cap string values
        allowed = {"navigatedUrl", "tabId", "title", "url", "html", "text", "data", "selector", "command_id", "challenge"}
        sanitized: dict = {}
        for key, value in v.items():
            if key not in allowed:
                continue
            if isinstance(value, str) and len(value) > 1_000_000:
                value = value[:1_000_000]
            sanitized[key] = value
        return sanitized


class ResumeMissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
