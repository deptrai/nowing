"""Schemas for the platform admin Agent Registry (AD-30)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentConfigCreate(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    slug: str | None = Field(default=None, max_length=256)
    system_instructions: str | None = Field(default=None, max_length=100_000)
    enabled_tools: list[str] = Field(default_factory=list, max_length=256)
    disabled_tools: list[str] = Field(default_factory=list, max_length=256)
    model_name: str | None = Field(default=None, max_length=256)
    citations_enabled: bool = False
    is_active: bool = True

    @field_validator("slug", mode="before")
    @classmethod
    def _default_slug(cls, v, info):
        if v is None or v == "":
            return info.data.get("name", "").strip().lower().replace(" ", "-")
        return v

    @field_validator("enabled_tools", "disabled_tools", mode="before")
    @classmethod
    def _coerce_tool_list(cls, v):
        if v is None:
            return []
        return list(v)


class AgentConfigUpdate(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=256)
    slug: str | None = Field(default=None, max_length=256)
    system_instructions: str | None = Field(default=None, max_length=100_000)
    enabled_tools: list[str] | None = Field(default=None, max_length=256)
    disabled_tools: list[str] | None = Field(default=None, max_length=256)
    model_name: str | None = Field(default=None, max_length=256)
    citations_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("enabled_tools", "disabled_tools", mode="before")
    @classmethod
    def _coerce_tool_list(cls, v):
        if v is None:
            return None
        return list(v)


class AgentConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: str
    name: str
    slug: str
    system_instructions: str | None
    enabled_tools: list[str]
    disabled_tools: list[str]
    model_name: str | None
    citations_enabled: bool
    is_active: bool
