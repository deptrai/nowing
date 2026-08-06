"""API schemas for the action catalog."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActionCatalogItem(BaseModel):
    """One runnable action exposed to the automation builder."""

    type: str
    name: str
    description: str = ""
    params_schema: dict[str, Any]
    verticals: list[str] = Field(default_factory=lambda: ["general"])
    business_name: str | None = None
