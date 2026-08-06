"""Request/response schemas for the ``Playbook`` resource."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.automations.schemas.definition import AutomationDefinition


class PlaybookCreate(BaseModel):
    """Create a playbook from an existing automation."""

    model_config = ConfigDict(extra="forbid")

    source_automation_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    tool_scope: list[str] = Field(default_factory=list)
    verticals: list[str] = Field(default_factory=list)


class PlaybookUpdate(BaseModel):
    """Partial update of a playbook. Bumps version when ``definition`` changes."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    definition: AutomationDefinition | None = None
    tool_scope: list[str] | None = None
    verticals: list[str] | None = None


class PlaybookInstantiate(BaseModel):
    """Create a new automation from a playbook with a set of inputs."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: int
    inputs: dict[str, Any] = Field(default_factory=dict)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class PlaybookSummary(BaseModel):
    """Lightweight playbook view for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int | None
    name: str
    description: str | None = None
    version: int
    scope: Literal["workspace", "system"]
    verticals: list[str]
    created_at: datetime
    updated_at: datetime


class PlaybookDetail(PlaybookSummary):
    """Full playbook view including the template definition."""

    definition: AutomationDefinition
    inputs_schema: dict[str, Any]
    tool_scope: list[str]
    source_automation_id: int | None = None


class PlaybookList(BaseModel):
    """Paginated list of playbooks."""

    items: list[PlaybookSummary]
    total: int
