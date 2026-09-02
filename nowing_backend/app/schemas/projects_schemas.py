"""Pydantic schemas for the projects workspace domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import IDModel, TimestampModel


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    master_instructions: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    master_instructions: str | None = None
    is_archived: bool | None = None


class ProjectPinnedDocumentRead(IDModel):
    project_id: int
    document_id: int
    pinned_at: datetime
    document_title: str | None = None
    document_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectSkillLinkRead(IDModel):
    project_id: int
    skill_id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectRead(ProjectBase, IDModel, TimestampModel):
    workspace_id: int
    created_by_id: UUID | None = None
    is_archived: bool
    updated_at: datetime
    pinned_documents: list[ProjectPinnedDocumentRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectListParams(BaseModel):
    include_archived: bool = False
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
