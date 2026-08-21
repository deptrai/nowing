"""Request/response schemas for the ``Playbook`` resource."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    author_badge: str | None = None
    author_name: str | None = None
    estimated_credits_cost: int | None = None
    run_count: int | None = 0
    is_featured: bool | None = None
    tags: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _extract_metadata(cls, data: Any) -> Any:
        """Pull marketplace card metadata from the persisted definition."""
        if isinstance(data, dict):
            definition = data.get("definition") or {}
            metadata = definition.get("metadata") or {}
            scope = data.get("scope")
            scope_value = getattr(scope, "value", scope)
            data.setdefault(
                "author_badge",
                metadata.get("author_badge") or ("workspace" if scope_value == "workspace" else None),
            )
            data.setdefault("author_name", metadata.get("author_name"))
            data.setdefault(
                "estimated_credits_cost",
                metadata.get("estimated_credits_cost"),
            )
            data.setdefault(
                "run_count",
                metadata.get("run_count", 0 if scope_value == "workspace" else None),
            )
            data.setdefault("is_featured", metadata.get("is_featured"))
            data.setdefault("tags", list(metadata.get("tags") or []))
            return data

        # ``from_attributes=True`` path: ``data`` is a Playbook ORM instance.
        definition = getattr(data, "definition", {}) or {}
        metadata = definition.get("metadata") or {}
        scope = getattr(data, "scope", None)
        scope_value = getattr(scope, "value", scope)
        values: dict[str, Any] = {}

        table = getattr(data, "__table__", None)
        if table is not None:
            for col in table.columns:
                values[col.name] = getattr(data, col.name)
        else:
            values = dict(data.__dict__)
            values.pop("_sa_instance_state", None)

        values.setdefault(
            "author_badge",
            metadata.get("author_badge") or ("workspace" if scope_value == "workspace" else None),
        )
        values.setdefault("author_name", metadata.get("author_name"))
        values.setdefault(
            "estimated_credits_cost",
            metadata.get("estimated_credits_cost"),
        )
        values.setdefault(
            "run_count",
            metadata.get("run_count", 0 if scope_value == "workspace" else None),
        )
        values.setdefault("is_featured", metadata.get("is_featured"))
        values.setdefault("tags", list(metadata.get("tags") or []))
        return values


class PlaybookDetail(PlaybookSummary):
    """Full playbook view including the template definition."""

    definition: AutomationDefinition
    inputs_schema: dict[str, Any]
    tool_scope: list[str]
    source_automation_id: int | None = None


class PlaybookValidateInputs(BaseModel):
    """Check a playbook's inputs against its schema before instantiation."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: int
    inputs: dict[str, Any]


class PlaybookValidationResult(BaseModel):
    """Result of a pre-flight inputs validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


class PlaybookList(BaseModel):
    """Paginated list of playbooks."""

    items: list[PlaybookSummary]
    total: int
