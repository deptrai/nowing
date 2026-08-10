"""Schemas for the platform admin Agent Registry (AD-30)."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.chat.multi_agent_chat.main_agent.tools.index import (
    MAIN_AGENT_NOWING_TOOL_NAMES,
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-._]{0,62}$")
_MAX_DISPLAY_NAME_LEN = 256


def _validate_slug(value: str | None, field: str) -> str:
    """Return a trimmed, lower-cased, non-empty slug matching ``_SLUG_RE``."""
    if value is None:
        raise ValueError(f"{field} is required")
    value = value.strip().lower()
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(
            f"{field} must be a lowercase slug (a-z, 0-9, '-', '.', '_'), "
            f"starting with a letter or number, 1-63 characters"
        )
    return value


def _derive_slug(name: str | None, explicit_slug: str | None) -> str:
    """Generate a valid slug from ``explicit_slug`` or fall back to ``name``."""
    if explicit_slug:
        return _validate_slug(explicit_slug, "slug")
    if not name:
        raise ValueError("name is required when slug is not provided")
    # ponytail: slugify while keeping the regex-legal character set.
    s = re.sub(r"[^a-z0-9-._]+", "-", name.strip().lower())
    s = re.sub(r"[-]+", "-", s).strip("-.")
    if not _SLUG_RE.fullmatch(s):
        raise ValueError("slug derived from name is not a valid slug")
    return s


class AgentConfigCreate(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=256)
    slug: str | None = Field(default=None, max_length=64)
    system_instructions: str | None = Field(default=None, max_length=100_000)
    enabled_tools: list[str] = Field(default_factory=list, max_length=256)
    disabled_tools: list[str] = Field(default_factory=list, max_length=256)
    model_name: str | None = Field(default=None, max_length=256)
    citations_enabled: bool = True
    is_active: bool = True

    @field_validator("client_id", mode="before")
    @classmethod
    def _normalize_client_id(cls, v):
        return _validate_slug(v, "client_id")

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, v, info):
        return _derive_slug(info.data.get("name"), v)

    @field_validator("enabled_tools", "disabled_tools", mode="before")
    @classmethod
    def _coerce_tool_list(cls, v):
        if v is None:
            return []
        return list(v)

    @field_validator("enabled_tools", "disabled_tools")
    @classmethod
    def _validate_tool_names(cls, v):
        if not v:
            return v
        unknown = [n for n in v if n not in MAIN_AGENT_NOWING_TOOL_NAMES]
        if unknown:
            raise ValueError(f"unknown tool names: {unknown}")
        return v


class AgentConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    slug: str | None = Field(default=None, max_length=64)
    system_instructions: str | None = Field(default=None, max_length=100_000)
    enabled_tools: list[str] | None = Field(default=None, max_length=256)
    disabled_tools: list[str] | None = Field(default=None, max_length=256)
    model_name: str | None = Field(default=None, max_length=256)
    citations_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, v):
        if v is None or v == "":
            return None
        return _validate_slug(v, "slug")

    @field_validator("enabled_tools", "disabled_tools", mode="before")
    @classmethod
    def _coerce_tool_list(cls, v):
        if v is None:
            return None
        return list(v)

    @field_validator("enabled_tools", "disabled_tools")
    @classmethod
    def _validate_tool_names(cls, v):
        if not v:
            return v
        unknown = [n for n in v if n not in MAIN_AGENT_NOWING_TOOL_NAMES]
        if unknown:
            raise ValueError(f"unknown tool names: {unknown}")
        return v


class AgentConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: str
    name: str
    display_name: str
    slug: str
    system_instructions: str | None
    enabled_tools: list[str]
    disabled_tools: list[str]
    model_name: str | None
    citations_enabled: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
