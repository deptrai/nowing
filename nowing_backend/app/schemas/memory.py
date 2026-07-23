"""Pydantic schemas for long-term memory resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryVersionRead(BaseModel):
    previous_content: str
    corrected_content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryRead(BaseModel):
    id: int
    workspace_id: int | None = None
    created_by_id: Any | None = None
    research_thread_id: int | None = None
    type: str
    content: str
    source_type: str
    source_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime
    updated_at: datetime
    previous_versions: list[MemoryVersionRead] = Field(
        default_factory=list,
        alias="versions",
        serialization_alias="previous_versions",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MemoryCreate(BaseModel):
    content: str
    type: str = "semantic"
    source_type: str = "manual"
    source_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    research_thread_id: int | None = None


class MemoryUpdate(BaseModel):
    corrected_content: str


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    type: str | None = None
    tags: list[str] = Field(default_factory=list)
    research_thread_id: int | None = None


class MemorySearchHit(BaseModel):
    id: int
    content: str
    type: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    source_type: str
    source_id: int | None = None
    score: float


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchHit]


class MemoryLimits(BaseModel):
    soft: int
    hard: int


class MemoryReadLegacy(BaseModel):
    memory_md: str
    limits: MemoryLimits
