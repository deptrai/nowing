"""Admin anti-bot escalation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AntiBotEscalationRead(BaseModel):
    """Public read shape for an anti-bot escalation."""

    id: int
    run_id: UUID
    workspace_id: int
    capability: str
    domain: str
    block_type: str
    screenshot_url: str | None = None
    status: str
    detection_count: int
    last_seen_at: datetime
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="escalation_metadata",
        serialization_alias="metadata",
    )
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AntiBotEscalationListResponse(BaseModel):
    """Paginated list response for admin escalations."""

    items: list[AntiBotEscalationRead]
    total: int


class AntiBotEscalationResolveRequest(BaseModel):
    """Optional body for resolving an escalation."""

    user_id: UUID | None = None


class AntiBotEscalationRetryResponse(BaseModel):
    """Response after marking an escalation for retry."""

    id: int
    status: str
    retry_run_id: str | None = None
    message: str
