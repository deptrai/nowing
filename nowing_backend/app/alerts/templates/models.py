"""Data models and schemas for Vertical Alert Rule Templates (Story 6.11)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertTemplateParameter(BaseModel):
    """Definition of a single parameter accepted by an alert template."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Parameter machine name")
    label: str = Field(..., description="Human-readable label for UI form")
    description: str | None = Field(default=None, description="Help text or placeholder guide")
    type: str = Field(default="string", description="Type: string, number, integer, boolean, select")
    required: bool = Field(default=True)
    default: Any | None = Field(default=None)
    options: list[dict[str, str]] | None = Field(
        default=None, description="Options for select-type fields (value, label)"
    )


class AlertTemplate(BaseModel):
    """Vertical alert template definition."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    template_id: str = Field(..., description="Unique template identifier slug")
    name: str = Field(..., description="Template title")
    description: str = Field(..., description="Explanation of what this alert monitors")
    category: str = Field(
        ..., description="Vertical category: news, finance, company, ecommerce, jobs"
    )
    required_capability: str = Field(
        ..., description="Primary capability required from CapabilityRegistry"
    )
    fallback_capabilities: list[str] = Field(
        default_factory=list, description="Alternative capabilities if primary is missing"
    )
    diff_strategy: str = Field(
        ..., description="diff_strategy used by Generic Alert Engine: new_items, price_change, threshold_cross"
    )
    default_schedule: str = Field(
        default="daily", description="Default cron schedule: daily, weekly, none"
    )
    parameters: list[AlertTemplateParameter] = Field(
        default_factory=list, description="List of user parameters required to instantiate"
    )


class AlertTemplateRead(BaseModel):
    """API response model for an alert template with availability flag."""

    model_config = ConfigDict(extra="ignore")

    template_id: str
    name: str
    description: str
    category: str
    required_capability: str
    diff_strategy: str
    default_schedule: str
    parameters: list[AlertTemplateParameter]
    is_available: bool = True
    unavailable_reason: str | None = None
