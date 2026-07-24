"""``ContinueResearchActionParams`` — params for the ``continue_research`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ContinueResearchActionParams(BaseModel):
    """Resume a saved research thread: recall its memories + prior citations."""

    model_config = ConfigDict(extra="forbid")

    research_thread_id: int = Field(
        ...,
        description="Id of the research thread to continue (must exist in the workspace).",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of thread-scoped memories to recall.",
    )
