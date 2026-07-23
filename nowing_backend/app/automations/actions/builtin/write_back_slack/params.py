"""``SlackActionParams`` — params for the ``write_back_slack`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SlackActionParams(BaseModel):
    """Send or update a Slack message from an automation step."""

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    thread_ts: str | None = Field(default=None)
    connector_name: str | None = Field(default=None)
    object_id: str | None = Field(
        default=None,
        description="Existing message ts to update (v1 create-only fallback).",
    )
