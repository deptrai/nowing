"""Pydantic schemas for Workspace Tables and Lead Export Hub (Story 21.13)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceTableCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    icon: str = Field(default="table", max_length=50)
    filter_preset: dict[str, Any] = Field(default_factory=dict)
    columns_config: dict[str, Any] = Field(default_factory=dict)


class WorkspaceTableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = Field(default=None, max_length=50)
    filter_preset: dict[str, Any] | None = None
    columns_config: dict[str, Any] | None = None


class WorkspaceTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    name: str
    icon: str
    filter_preset: dict[str, Any]
    columns_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None = None


class AssignLeadsRequest(BaseModel):
    lead_ids: list[UUID] = Field(..., min_length=1)
    table_id: UUID | None = None


class ExportRequest(BaseModel):
    export_type: str = Field(
        ..., description="csv, lark_base, google_sheets, share_link"
    )
    table_id: UUID | None = None
    lead_ids: list[UUID] | None = None
    mask_pii: bool = True
    target_config: dict[str, Any] = Field(default_factory=dict)


class ExportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: str
    export_type: str
    total_rows: int
    processed_rows: int
    target_url: str | None = None
    error_message: str | None = None
    created_at: datetime
