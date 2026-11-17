"""REST API endpoints for ChainLens Pulse Intelligence Feed (Story 20.10/20.11)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.context import AuthContext
from app.capabilities.chainlens.pulse_feed.executor import (
    PulseFeedExecutor,
    build_pulse_feed_executor,
)
from app.capabilities.chainlens.pulse_feed.schemas import (
    PulseAngleResponse,
    PulseFeedInput,
    PulseFeedOutput,
)
from app.capabilities.chainlens.research.sse_parser import _parse_sse
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/pulse",
    tags=["pulse_feed"],
)

_executor = build_pulse_feed_executor()


class PulseResearchRequest(BaseModel):
    """Request payload for running a deep-research stream on a Pulse angle."""

    item_id: str = Field(..., alias="itemId", min_length=1)
    angle_id: str = Field(..., alias="angleId", min_length=1)
    mode: str = Field(
        "balanced",
        pattern="^(research|balanced|deep|speed|auto|fast|instant|quality)$",
    )
    chat_id: str | None = Field(None, alias="chatId")


def _get_executor() -> PulseFeedExecutor:
    return _executor


@router.get(
    "/feed",
    response_model=PulseFeedOutput,
    summary="Get curated market intelligence feed with keyset pagination",
)
async def get_pulse_feed(
    workspace_id: int,
    topic: str = Query("all", pattern="^(all|tech|ai|finance|science|security|startup)$"),
    cursor: str | None = Query(None, description="ISO datetime cursor"),
    limit: int = Query(20, ge=1, le=50),
    auth: AuthContext = Depends(require_session_context),
    executor: PulseFeedExecutor = Depends(_get_executor),
) -> PulseFeedOutput:
    """Fetch curated news items and proactive market intelligence."""
    input_data = PulseFeedInput(topic=topic, cursor=cursor, limit=limit)
    return await executor.execute(input_data)


@router.get(
    "/items/{item_id}/angles",
    response_model=list[PulseAngleResponse],
    summary="Get pre-generated research angles for a pulse feed item",
)
async def get_pulse_item_angles(
    workspace_id: int,
    item_id: str,
    auth: AuthContext = Depends(require_session_context),
    executor: PulseFeedExecutor = Depends(_get_executor),
) -> list[PulseAngleResponse]:
    """Retrieve available deep research angles and credit hints for an item."""
    return await executor.get_item_angles(item_id, workspace_id=workspace_id)


@router.post(
    "/research",
    summary="Run a cited deep-research stream on a Pulse feed angle (SSE)",
)
async def run_pulse_angle_research(
    workspace_id: int,
    req: PulseResearchRequest,
    auth: AuthContext = Depends(require_session_context),
) -> dict:
    """Stream a deep-research report for a chosen Pulse feed angle.

    Returns the parsed ``ResearchOutput`` (same contract as chainlens.research).
    """
    from app.capabilities.chainlens.pulse_research.executor import (
        ChainLensPulseResearchError,
        ChainLensPulseResearchNotFoundError,
        PulseResearchExecutor,
    )
    from app.capabilities.chainlens.pulse_research.schemas import PulseResearchInput

    executor = PulseResearchExecutor()
    input_data = PulseResearchInput(
        itemId=req.item_id,
        angleId=req.angle_id,
        mode=req.mode,
        chatId=req.chat_id,
    )

    try:
        lines = executor.stream_research(input_data)
        result = _parse_sse(lines)
        if hasattr(result, "__await__"):
            result = await result
        return result.model_dump(mode="json", by_alias=True)
    except ChainLensPulseResearchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ChainLensPulseResearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
