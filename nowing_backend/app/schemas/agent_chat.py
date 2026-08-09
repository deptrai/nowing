from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatThreadCreate(BaseModel):
    """Request body to start a public agent-chat thread."""

    agent_id: str = Field(
        ..., min_length=1, description="Agent slug to bind this thread to."
    )
    client_id: str = Field(
        ..., min_length=1, description="Vertical client this thread belongs to."
    )
    platform_metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata from the calling platform."
    )


class AgentChatMessageCreate(BaseModel):
    """Request body to send a message in a public agent-chat thread."""

    content: str = Field(..., min_length=1, description="User message content.")
    external_metadata: dict[str, Any] | None = Field(
        default=None, description="Optional external platform metadata."
    )


class AgentChatThreadCreated(BaseModel):
    """Response body returned when a public thread is created."""

    thread_id: int
    research_thread_id: int
    run_id: str
