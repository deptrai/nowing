# ruff: noqa: N815
"""Pydantic schemas for the chainlens-research private-data provider (Story 20.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrivateDataSearchRequest(BaseModel):
    """Body of ``POST /v1/private-data/search``."""

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    workspaceId: int = Field(..., gt=0)
    userId: UUID | None = Field(default=None)
    connectorId: int | None = Field(default=None, gt=0)
    sources: list[str] | None = Field(default=None)
    topK: int = Field(default=20, ge=1, le=100)

    @field_validator("query", mode="before")
    @classmethod
    def _strip_query(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _mutually_exclusive_filters(self) -> PrivateDataSearchRequest:
        """``connectorId`` and ``sources`` are alternative filters, not combined."""
        if self.connectorId is not None and self.sources:
            raise ValueError(
                "connectorId and sources are mutually exclusive; provide only one"
            )
        return self


class PrivateProviderChunkMetadata(BaseModel):
    """Canonical metadata for a chunk returned by the private provider."""

    model_config = ConfigDict(extra="allow")

    source: Literal["private_provider"] = "private_provider"
    sourceId: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    fetchedAt: str = Field(..., min_length=1)
    contentType: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1)
    url: str | None = Field(default=None, min_length=1)
    document_id: int | None = None
    chunk_id: int | None = None
    connector_id: int | None = None
    workspace_id: int | None = None

    @field_validator("fetchedAt")
    @classmethod
    def _validate_fetched_at(cls, value: str) -> str:
        if value:
            datetime.fromisoformat(value)
        return value


class PrivateProviderChunk(BaseModel):
    """One private search result chunk."""

    content: str = Field(..., min_length=1)
    metadata: PrivateProviderChunkMetadata


class PrivateDataSearchResponse(BaseModel):
    """Nowing alias for the chainlens ``SearchProviderResult`` contract."""

    chunks: list[PrivateProviderChunk] = Field(default_factory=list)
    costDollars: float = Field(default=0.0, ge=0.0)
