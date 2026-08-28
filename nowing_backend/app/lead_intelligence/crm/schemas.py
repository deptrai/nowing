"""Pydantic schemas for CRM integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CrmSyncConfig(BaseModel):
    """Runtime configuration for a CRM connection."""

    dedup_enabled: bool = True
    writeback_enabled: bool = False
    bidirectional_enabled: bool = False
    owner_id: str = ""
    lead_source: str = "Nowing"
    field_mapping: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class CrmConnectionCreate(BaseModel):
    """Create a CRM connection (provider is the only required field at init)."""

    provider: str
    sync_config: CrmSyncConfig | None = None


class CrmConnectionRead(BaseModel):
    """Safe read model for a CRM connection (tokens are not exposed)."""

    id: UUID
    workspace_id: int
    client_id: str | None
    provider: str
    status: str
    sync_config: dict[str, Any]
    last_sync_at: datetime | None
    created_at: datetime


class CrmConnectionUpdate(BaseModel):
    """Update a CRM connection."""

    sync_config: CrmSyncConfig | None = None
    status: str | None = None


class CrmSyncInput(BaseModel):
    """Trigger a sync."""

    entity_ids: list[UUID] | None = None
    entity_type: str = "lead"
    direction: str = "nowing_to_crm"


class CrmSyncLogRead(BaseModel):
    """Read model for a sync log."""

    id: UUID
    workspace_id: int
    client_id: str | None
    connection_id: UUID
    direction: str
    entity_type: str
    entity_id: UUID
    status: str
    error_message: str | None
    synced_at: datetime


class CrmDedupInput(BaseModel):
    """Trigger a read-only dedup."""

    lead_ids: list[UUID] | None = None


class CrmConversionLogInput(BaseModel):
    """Log a CRM lead conversion / deal outcome event."""

    lead_id: UUID
    event_type: str = "outcome_meeting_booked"
    attribution: str = "crm_sync"
    cost_micros: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    sync_to_crm: bool = False
    connection_id: UUID | None = None


class CrmConversionRead(BaseModel):
    """Read model for a logged conversion outcome."""

    id: UUID
    workspace_id: int
    client_id: str | None
    lead_id: UUID
    event_type: str
    attribution: str
    cost_micros: int
    outcome_metadata: dict[str, Any]
    created_at: datetime

