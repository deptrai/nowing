"""``LinearActionParams`` — params for the ``write_back_linear`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LinearActionParams(BaseModel):
    """Create or update a Linear issue from an automation step."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    description: str | None = Field(default=None)
    team_id: str | None = Field(default=None)
    state: str | None = Field(default=None)
    connector_name: str | None = Field(default=None)
    object_id: str | None = Field(
        default=None,
        description="Existing issue id to update; omitted to create.",
    )
