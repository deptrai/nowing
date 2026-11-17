"""REST endpoints for ChainLens Asynchronous Deep Research (Story 20.9)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.context import AuthContext
from app.services.chainlens.async_jobs import (
    ChainLensAsyncJobError,
    ChainLensAsyncJobsClient,
)
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/research/async-jobs",
    tags=["async_research"],
)

_async_client = ChainLensAsyncJobsClient()


def _get_async_jobs_client() -> ChainLensAsyncJobsClient:
    return _async_client


class AsyncResearchSubmitRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    mode: str = Field("balanced", pattern="^(speed|balanced|quality|auto|deep|research)$")
    sources: list[str] | None = None
    chat_id: str | None = None


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an asynchronous deep research query (> 60s)",
)
async def submit_async_research_job(
    workspace_id: int,
    req: AsyncResearchSubmitRequest,
    auth: AuthContext = Depends(require_session_context),
    client: ChainLensAsyncJobsClient = Depends(_get_async_jobs_client),
) -> dict[str, Any]:
    """Submit a deep research job for background execution on ChainLens."""
    try:
        job = await client.submit_job(
            workspace_id=workspace_id,
            query=req.query,
            mode=req.mode,
            sources=req.sources,
            chat_id=req.chat_id,
        )
        return job
    except ChainLensAsyncJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ChainLens engine error: {exc}",
        ) from exc


@router.get(
    "/{run_id}",
    summary="Get async job status and recover completed deliverables without re-billing",
)
async def get_async_research_job(
    workspace_id: int,
    run_id: str,
    auth: AuthContext = Depends(require_session_context),
    client: ChainLensAsyncJobsClient = Depends(_get_async_jobs_client),
) -> dict[str, Any]:
    """Inspect async research job state; returns report when completed."""
    try:
        job = await client.get_job(run_id, workspace_id=workspace_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research job {run_id} not found",
            )
        return job
    except ChainLensAsyncJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query job {run_id}: {exc}",
        ) from exc
