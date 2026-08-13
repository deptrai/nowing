"""Pydantic schemas for alert rules and subscriptions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertRuleBase(BaseModel):
    """Common fields for alert rule requests/responses."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    capability_id: str = Field(..., min_length=1, max_length=200)
    query: dict
    schedule: str = Field(default="none", pattern="^(none|daily|weekly)$")
    timezone: str = Field(default="UTC", max_length=64)
    diff_strategy: str = Field(
        default="new_items",
        pattern="^(new_items|price_change|threshold_cross|trend_detect)$",
    )
    threshold: dict | None = Field(default=None)
    target_sequence_id: UUID | None = Field(default=None)
    target_step_id: UUID | None = Field(default=None)
    notification_channels: list[str] = Field(default_factory=lambda: ["in_app"])
    enabled: bool = Field(default=True)

    @field_validator("notification_channels", mode="after")
    @classmethod
    def _validate_channels(cls, channels: list[str]) -> list[str]:
        allowed = {"in_app", "telegram"}
        for channel in channels:
            if channel not in allowed:
                raise ValueError(f"notification channel {channel!r} is not allowed")
        return channels


class AlertRuleCreate(AlertRuleBase):
    """Create a new alert rule."""


class AlertRuleUpdate(BaseModel):
    """Update an existing alert rule (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    capability_id: str | None = Field(default=None, min_length=1, max_length=200)
    query: dict | None = Field(default=None)
    schedule: str | None = Field(default=None, pattern="^(none|daily|weekly)$")
    timezone: str | None = Field(default=None, max_length=64)
    diff_strategy: str | None = Field(
        default=None, pattern="^(new_items|price_change|threshold_cross|trend_detect)$"
    )
    threshold: dict | None = Field(default=None)
    target_sequence_id: UUID | None = Field(default=None)
    target_step_id: UUID | None = Field(default=None)
    notification_channels: list[str] | None = Field(default=None)
    enabled: bool | None = Field(default=None)


class AlertRuleRead(AlertRuleBase):
    """Alert rule as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None
    cron: str | None
    next_fire_at: datetime | None
    last_fired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertSubscriptionCreate(BaseModel):
    """Subscribe a user to an alert rule."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    channels: list[str]
    enabled: bool = True


class AlertSubscriptionRead(AlertSubscriptionCreate):
    """Subscription as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_rule_id: UUID
