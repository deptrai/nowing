"""Pydantic schemas for the skills hub domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import IDModel, TimestampModel


class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-_]+$")
    description: str | None = None
    trigger_pattern: str = Field(..., min_length=1, max_length=255)
    content_markdown: str = Field(..., min_length=1)
    skill_type: Literal["prompt", "workflow"] = "prompt"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-_]+$")
    description: str | None = None
    trigger_pattern: str | None = Field(default=None, min_length=1, max_length=255)
    content_markdown: str | None = Field(default=None, min_length=1)
    skill_type: Literal["prompt", "workflow"] | None = None
    parameters_schema: dict[str, Any] | None = None
    is_active: bool | None = None


class SkillRead(SkillBase, IDModel, TimestampModel):
    workspace_id: int
    created_by_id: UUID | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SkillParseRequest(BaseModel):
    file_content: str = Field(..., min_length=1, description="Raw .skill.md content with YAML frontmatter")


class SkillParseResponse(BaseModel):
    name: str
    slug: str
    description: str | None = None
    trigger_pattern: str
    skill_type: str = "prompt"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    content_markdown: str


class SkillExecuteRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
