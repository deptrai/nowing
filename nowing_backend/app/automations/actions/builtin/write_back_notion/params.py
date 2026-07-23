"""``NotionActionParams`` — params for the ``write_back_notion`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NotionActionParams(BaseModel):
    """Create or update a Notion page from an automation step."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    content: str | None = Field(default=None)
    parent_page_id: str | None = Field(default=None)
    connector_name: str | None = Field(default=None)
    object_id: str | None = Field(
        default=None,
        description="Existing page_id to update; omitted to create.",
    )
