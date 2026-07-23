"""``JiraActionParams`` — params for the ``write_back_jira`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class JiraActionParams(BaseModel):
    """Create or update a Jira issue from an automation step."""

    model_config = ConfigDict(extra="forbid")

    project_key: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    description: str | None = Field(default=None)
    issue_type: str = Field(default="Task")
    connector_name: str | None = Field(default=None)
    object_id: str | None = Field(
        default=None,
        description="Existing issue key or id to update; omitted to create.",
    )
