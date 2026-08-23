"""``news.entity_search`` I/O contracts.

Allows querying articles and named entities indexed by ChainLens Research.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.capabilities.chainlens.research.schemas import Source

MAX_ENTITY_NAME_LENGTH = 200
EntityType = Literal["person", "organization", "location", "all"]


class EntitySearchInput(BaseModel):
    """Input for searching news articles mentioning a named entity."""

    entity_name: str = Field(
        min_length=1,
        max_length=MAX_ENTITY_NAME_LENGTH,
        description="The name of the entity to search for (e.g. company, public figure, location).",
    )
    entity_type: EntityType = Field(
        default="all",
        description="Category filter for the entity: person, organization, location, or all.",
    )
    workspace_id: int = Field(
        gt=0,
        description="Workspace context ID.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of articles to return.",
    )

    @field_validator("entity_name", mode="before")
    @classmethod
    def validate_entity_name_non_empty(cls, v: Any) -> str:
        """Strip and reject empty or whitespace-only entity names."""
        if not isinstance(v, str):
            raise ValueError("entity_name must be a string")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("entity_name cannot be empty or whitespace")
        return trimmed

    @field_validator("entity_type", mode="before")
    @classmethod
    def normalize_entity_type(cls, v: Any) -> str:
        """Normalize entity_type to lowercase and stripped."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @property
    def estimated_units(self) -> int:
        """Estimated billing units for capability gate checking."""
        return 1


class EntitySearchOutput(BaseModel):
    """Output containing matching articles with citations."""

    entity_name: str = Field(description="The queried entity name.")
    entity_type: EntityType = Field(
        default="all", description="The entity category filter applied."
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="List of citing news articles / sources.",
    )
    total_count: int = Field(
        default=0,
        description="Total matching articles count.",
    )
    status: str = Field(
        default="complete",
        description="Execution status ('complete' or 'engine_unavailable').",
    )
    degraded: bool = Field(
        default=False,
        description="Whether the result is degraded due to engine unavailability or redaction.",
    )
    message: str | None = Field(
        default=None,
        description="Optional informational or degradation message.",
    )
    cost_micros: int | None = Field(
        default=0,
        description="Cost in micros for query billing tracking.",
    )
    cost_basis: str | None = Field(
        default="actual",
        description="Cost basis ('actual', 'estimated', or 'fallback').",
    )

    @property
    def articles(self) -> list[Source]:
        """Backward-compatible alias for sources."""
        return self.sources
