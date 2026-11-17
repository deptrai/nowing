"""Schemas for chainlens.pulse_research capability (Story 20.11)."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Reuse the exact SSE output contract from chainlens.research (Story 20.11
# requirement: same parser, same output shape — no reimplementation).
from app.capabilities.chainlens.research.schemas import ResearchOutput

__all__ = ["PulseResearchInput", "ResearchOutput"]

_RESEARCH_MODES = (
    "research",
    "balanced",
    "deep",
    "speed",
    "auto",
    "fast",
    "instant",
    "quality",
)


class PulseResearchInput(BaseModel):
    """Input for running a deep-research stream on a Pulse feed angle."""

    item_id: str = Field(..., alias="itemId", min_length=1)
    angle_id: str = Field(..., alias="angleId", min_length=1)
    mode: str = Field(
        "balanced",
        description="Research depth mode (research|balanced|deep|speed|auto|fast|instant|quality)",
    )
    chat_id: str | None = Field(None, alias="chatId")
