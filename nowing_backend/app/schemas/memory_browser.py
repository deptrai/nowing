"""Pydantic schemas for Memory Browser (Story 29.5 / FR-104)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    research_thread_id: int | None = None
    relation_marker: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryBrowserListResponse(BaseModel):
    items: list[MemoryBrowserListItem]
    total: int
    page: int
    page_size: int


class MemoryBrowserCreatorListResponse(BaseModel):
    """Distinct creators for the creator filter dropdown (AC-2.4)."""

    items: list[MemoryBrowserCreator]


class MemoryBrowserTimelineThread(BaseModel):
    id: int
    title: str
    memories: list[MemoryBrowserListItem]


class MemoryBrowserTimelineResponse(BaseModel):
    """AC-4: memories grouped by research thread, chronological order."""

    threads: list[MemoryBrowserTimelineThread]
    unthreaded: list[MemoryBrowserListItem] = []


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


class MemoryVersionListResponse(BaseModel):
    items: list[MemoryVersionRead]


class MemoryRelationListResponse(BaseModel):
    items: list[MemoryRelationRead]


class MemoryReviewQueueCreate(BaseModel):
    flag_reason: str = Field(..., min_length=1, max_length=1000)


class MemoryReviewQueueRead(BaseModel):
    id: int | None = None
    memory_id: int | None = None
    workspace_id: int
    flag_reason: str
    flagged_by: str | None = None
    status: str
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
