from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
        return _bounded_metadata(v)


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

    @field_validator("external_metadata")
    @classmethod
    def _validate_external_metadata(cls, v):
        return _bounded_metadata(v)


class AgentChatThreadCreated(BaseModel):
    """Response body returned when a public thread is created."""

    thread_id: int
    research_thread_id: int
    run_id: str


def _bounded_metadata(v: dict[str, Any] | None) -> dict[str, Any] | None:
    """Clamp metadata to small, primitive values to prevent payload abuse."""
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ValueError("metadata must be a flat JSON object")
    if len(v) > 32:
        raise ValueError("metadata may contain at most 32 keys")
    for key, val in v.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError("metadata keys must be strings <= 64 characters")
        if isinstance(val, str):
            if len(val) > 1024:
                raise ValueError("metadata string values must be <= 1024 characters")
        elif not isinstance(val, (int, float, bool, type(None))):
            raise ValueError("metadata values must be primitive")
    return v
