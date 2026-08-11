# ruff: noqa: N815
"""Pydantic schemas for the Nowing -> chainlens-research scraper feed."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChunkValidationError(ValueError):
    """Raised when scraper data cannot be normalized to a canonical Chunk."""

    def __init__(self, *, domain: str, missing: list[str], message: str | None = None):
        self.domain = domain
        self.missing = missing
        super().__init__(message or f"{domain}: missing {', '.join(missing)}")


class ChunkMetadata(BaseModel):
    """Metadata contract for a single scraper-derived chunk (AD-34)."""

    model_config = ConfigDict(extra="allow")

    source: Literal["nowing_scraper"]
    sourceId: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    fetchedAt: str = Field(..., min_length=1)
    contentType: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1)
    url: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)

    @field_validator("fetchedAt")
    @classmethod
    def _validate_fetched_at(cls, value: str) -> str:
        if value:
            datetime.fromisoformat(value)
        return value
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_count: int | None = Field(default=None, ge=0)
    conflict_flags: list[dict[str, Any]] | None = Field(default=None)
    chunkIndex: int | None = Field(default=None, ge=0)
    chunkTotal: int | None = Field(default=None, ge=1)
    canonicalEntityId: str | None = Field(default=None)


class Chunk(BaseModel):
    """One searchable chunk sent to chainlens-research."""

    model_config = ConfigDict(extra="allow")

    content: str = Field(..., min_length=1)
    metadata: ChunkMetadata
