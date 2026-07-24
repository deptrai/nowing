"""Pydantic schemas for long-term memory resources."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db import MemorySourceType, MemoryType


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
    content: Annotated[str, Field(min_length=1)]
    type: str = "semantic"
    source_type: str = "manual"
    source_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    research_thread_id: int | None = None

    @field_validator("type", "source_type", mode="before")
    @classmethod
    def _validate_enum_strings(cls, value: Any, info) -> Any:
        if not isinstance(value, str):
            return value
        enum_cls = MemoryType if info.field_name == "type" else MemorySourceType
        try:
            enum_cls(value)
        except ValueError as exc:
            raise ValueError(f"Invalid {info.field_name}: {value}") from exc
        return value


class MemoryUpdate(BaseModel):
    corrected_content: Annotated[str, Field(min_length=1)]


class MemorySearchRequest(BaseModel):
    # Empty query is allowed only for thread-scoped recall (see validator);
    # nowing_continue_research relies on this to resume a thread with no query.
    query: str = ""
    top_k: int = Field(default=5, ge=1, le=100)
    type: str | None = None
    tags: list[str] = Field(default_factory=list)
    research_thread_id: int | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, value: Any) -> Any:
        if value is None or not isinstance(value, str):
            return value
        try:
            MemoryType(value)
        except ValueError as exc:
            raise ValueError(f"Invalid type: {value}") from exc
        return value

    @model_validator(mode="after")
    def _require_query_or_thread(self) -> MemorySearchRequest:
        if not self.query.strip() and self.research_thread_id is None:
            raise ValueError(
                "query must be non-empty unless research_thread_id is provided"
            )
        return self


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
