"""REST API endpoints for ChainLens Pulse Intelligence Feed (Story 20.10)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

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
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/pulse",
    tags=["pulse_feed"],
)

_executor = build_pulse_feed_executor()


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
