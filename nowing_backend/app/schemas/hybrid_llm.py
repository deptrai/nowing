from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HybridLLMRequest(BaseModel):
    """Request body for the Hybrid LLM router.

    ``workspace_id`` and ``user_id`` are optional in the public/internal route
    schemas because they are supplied from the path and auth context.  The
    ``HybridLLMRouter`` itself requires them once assembled.
    """

    workspace_id: int | None = None
    user_id: UUID | None = None
    task_type: str
    sensitivity: str
    messages: list[dict[str, Any]]
    response_model: dict[str, Any]


class HybridLLMResponse(BaseModel):
    """Response payload returned by the Hybrid LLM router."""

    content: dict[str, Any] | list | str | None = None
    tier: str
    reasoning_content: str | None = None

    model_config = ConfigDict(extra="ignore")
