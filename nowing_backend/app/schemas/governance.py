"""Pydantic schemas for governance console (Story 29.6 / FR-97)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import MemorySourceType


class RetentionPolicyRead(BaseModel):
    """Current retention policy for a workspace."""

    document_retention_days: int | None = None
    auto_archive_enabled: bool = False
    document_retention_action: Literal["archive", "delete"] = "archive"
    memory_retention_days: int | None = None
    memory_auto_archive_enabled: bool = False
    memory_retention_action: Literal["archive", "delete"] = "archive"


class RetentionPolicyUpdate(BaseModel):
    """Payload to update workspace retention policy."""

    document_retention_days: int | None = Field(
        default=None, ge=1, le=36500, description="Days to keep documents"
    )
    auto_archive_enabled: bool | None = None
    document_retention_action: Literal["archive", "delete"] | None = None
    memory_retention_days: int | None = Field(
        default=None, ge=1, le=36500, description="Days to keep memories"
    )
    memory_auto_archive_enabled: bool | None = None
    memory_retention_action: Literal["archive", "delete"] | None = None


class SourceRiskTierRead(BaseModel):
    """Source risk tier mapping for a memory source type."""

    model_config = ConfigDict(from_attributes=True)

    source_type: str
    risk_tier: Literal["low", "medium", "high"] = "low"
    recommended_retention_days: int | None = None
    notes: str | None = None


class SourceRiskTierUpdate(BaseModel):
    """Payload to update a source risk tier."""

    source_type: MemorySourceType
    risk_tier: Literal["low", "medium", "high"]
    recommended_retention_days: int | None = Field(default=None, ge=1, le=36500)
    notes: str | None = Field(default=None, max_length=2000)


class DncRecordRead(BaseModel):
    """Workspace DNC record exposed to governance UI."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_type: str
    value: str | None
    value_hmac: str
    reason: str | None
    source: str
    created_at: datetime
    updated_at: datetime
    superseded_by_global: bool = False


class DncRecordCreate(BaseModel):
    """Payload to add a workspace DNC record."""

    record_type: Literal["phone", "email", "domain", "tax_id"]
    value: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(default="Opt-out requested", max_length=255)


class RightToDeleteRequest(BaseModel):
    """Payload for right-to-delete single or bulk memory."""

    type: Literal["single_memory", "bulk"] = "single_memory"
    memory_id: int | None = None
    source_type: MemorySourceType | None = None
    source_id: int | None = None
    source_entity_type: str | None = None
    created_before: datetime | None = None
    created_after: datetime | None = None
    dry_run: bool = False
    reason: str = Field(..., min_length=1, max_length=500)


class RightToDeleteResponse(BaseModel):
    """Response for right-to-delete request."""

    dry_run: bool
    affected_count: int
    preview_memory_ids: list[int] = []
    job_id: str | None = None
    status: str | None = None


class AuditLogFilter(BaseModel):
    """Query params for workspace audit log."""

    action_prefix: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class AuditLogRead(BaseModel):
    """Single audit event row for governance console."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor_id: UUID | None
    subject_id: UUID | None
    diff_payload: dict | None
    created_at: datetime


class WorkspaceStatusRead(BaseModel):
    """Workspace lifecycle status for governance console."""

    archived_at: datetime | None = None
    can_restore: bool = True
    scrape_paused_at: datetime | None = None


class GovernanceOverviewRead(BaseModel):
    """Top-level governance console payload."""

    retention_policy: RetentionPolicyRead
    source_risk_tiers: list[SourceRiskTierRead] = []
    dnc_records: list[DncRecordRead] = []
    workspace_status: WorkspaceStatusRead
    deployment_mode: str = "cloud"
