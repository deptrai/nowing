"""Admin anti-bot escalation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


from typing_extensions import Self
from pydantic import model_validator


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
    escalation_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Explicit alias matching SQLAlchemy model attribute",
    )
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _prepare_metadata(cls, data: Any) -> Any:
        if isinstance(data, dict):
            meta = data.get("metadata")
            esc_meta = data.get("escalation_metadata")
            if meta is not None and esc_meta is None:
                data["escalation_metadata"] = meta
            elif esc_meta is not None and meta is None:
                data["metadata"] = esc_meta
        return data

    @model_validator(mode="after")
    def _sync_metadata_aliases(self) -> Self:
        if self.metadata is not None and self.escalation_metadata is None:
            object.__setattr__(self, "escalation_metadata", self.metadata)
        elif self.escalation_metadata is not None and self.metadata is None:
            object.__setattr__(self, "metadata", self.escalation_metadata)
        return self


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
