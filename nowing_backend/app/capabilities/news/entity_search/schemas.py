"""``news.entity_search`` I/O contracts.

Allows querying articles and named entities indexed by ChainLens Research.
"""

from __future__ import annotations

from typing import Literal

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

    @field_validator("entity_name")
    @classmethod
    def validate_entity_name_non_empty(cls, v: str) -> str:
        """Reject empty or whitespace-only entity names."""
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("entity_name cannot be empty or whitespace")
        return trimmed


class EntitySearchOutput(BaseModel):
    """Output containing matching articles with citations."""

    entity_name: str = Field(description="The queried entity name.")
    entity_type: str = Field(description="The entity category filter applied.")
    articles: list[Source] = Field(
        default_factory=list,
        description="List of citing news articles.",
    )
    total_count: int = Field(
        default=0,
        description="Total matching articles count.",
    )
    degraded: bool = Field(
        default=False,
        description="Whether the result is degraded due to engine unavailability or redaction.",
    )
    message: str | None = Field(
        default=None,
        description="Optional informational or degradation message.",
    )
