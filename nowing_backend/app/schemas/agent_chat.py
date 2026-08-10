from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.new_chat import _bounded_chat_metadata


class AgentChatThreadCreate(BaseModel):
    """Request body to start a public agent-chat thread."""

    agent_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-._]*$",
        description="Agent slug to bind this thread to. Defaults to PAT scope.",
    )
    client_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-._]*$",
        description="Vertical client this thread belongs to. Defaults to PAT scope.",
    )
    platform_metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata from the calling platform."
    )

    @field_validator("platform_metadata")
    @classmethod
    def _validate_platform_metadata(cls, v):
        return _bounded_chat_metadata(v)

    @field_validator("client_id", "agent_id", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    # ponytail: client_id is supplied by the PAT scope; route-level checks
    # enforce that any body client_id/agent_id is a subset of that scope.
    # Requiring body client_id here would reject valid PAT-only creation.


class AgentChatMessageCreate(BaseModel):
    """Request body to send a message in a public agent-chat thread."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="User message content.",
    )
    external_metadata: dict[str, Any] | None = Field(
        default=None, description="Optional external platform metadata."
    )
    platform_metadata: dict[str, Any] | None = Field(
        default=None, description="Optional platform metadata for this turn."
    )

    @field_validator("external_metadata", "platform_metadata")
    @classmethod
    def _validate_external_metadata(cls, v):
        return _bounded_chat_metadata(v)


class AgentChatThreadCreated(BaseModel):
    """Response body returned when a public thread is created."""

    thread_id: int
    research_thread_id: int
    run_id: str


class CostReportItem(BaseModel):
    """One daily bucket of cost attribution for a vertical client."""

    day: date
    client_id: str | None = None
    usage_type: str
    total_cost_micros: int
    total_tokens: int


class CostReport(BaseModel):
    """Workspace-scoped cost report for public agent-chat usage."""

    workspace_id: int
    client_id: str | None = None
    start_date: date
    end_date: date
    items: list[CostReportItem]
