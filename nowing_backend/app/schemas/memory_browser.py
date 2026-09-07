"""Pydantic schemas for Memory Browser (Story 29.5 / FR-104)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryBrowserCreator(BaseModel):
    id: str
    email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryBrowserListItem(BaseModel):
    id: int
    content_snippet: str
    source_type: str
    source_url: str | None = None
    confidence: float
    created_at: datetime
    updated_at: datetime
    created_by: MemoryBrowserCreator | None = None
    version_count: int = 0
    flag_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryBrowserListResponse(BaseModel):
    items: list[MemoryBrowserListItem]
    total: int
    page: int
    page_size: int


class MemoryVersionRead(BaseModel):
    previous_content: str
    corrected_content: str
    corrected_by: MemoryBrowserCreator | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryBrowserDetailCitations(BaseModel):
    source_type: str
    source_url: str | None = None
    source_run_id: str | None = None
    source_uuid: str | None = None
    source_entity_type: str | None = None
    source_id: int | None = None
    source_capability: str | None = None
    source_input: Any | None = None


class ResearchThreadSummary(BaseModel):
    id: int
    title: str | None = None
    memories: list[MemoryBrowserListItem]


class MemoryRelationRead(BaseModel):
    relation_type: str
    to_memory_id: int | None = None
    weight: float

    model_config = ConfigDict(from_attributes=True)


class MemoryBrowserDetailResponse(BaseModel):
    id: int
    workspace_id: int | None = None
    content: str
    source_type: str
    source_url: str | None = None
    confidence: float
    created_at: datetime
    updated_at: datetime
    created_by: MemoryBrowserCreator | None = None
    citations: MemoryBrowserDetailCitations
    versions: list[MemoryVersionRead]
    research_thread: ResearchThreadSummary | None = None
    relations: list[MemoryRelationRead]


class MemoryReviewQueueCreate(BaseModel):
    flag_reason: str = Field(..., min_length=1)


class MemoryReviewQueueRead(BaseModel):
    id: int | None = None
    memory_id: int
    workspace_id: int
    flag_reason: str
    flagged_by: str
    status: str
    created_at: datetime | None = None
