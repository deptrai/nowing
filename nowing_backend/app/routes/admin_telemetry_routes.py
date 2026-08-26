"""Admin routes for real-time LLM token cost, proxy health, and Celery telemetry."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.admin_telemetry import (
    CeleryQueueResponse,
    GrossMarginSummary,
    LlmCostBreakdown,
    ProxyHealthResponse,
    PurgeDeadQueueResponse,
)
from app.services.admin_telemetry_service import AdminTelemetryService
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/telemetry", tags=["admin"])


@router.get("/llm-cost", response_model=LlmCostBreakdown)
async def get_llm_cost(
    window_hours: int = Query(default=24, ge=1, le=720),
    provider: str | None = Query(default=None, max_length=50),
    workspace_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return aggregate LLM cost and token usage for the requested window."""
    service = AdminTelemetryService(session)
    result = await service.get_llm_cost_breakdown(
        window_hours=window_hours,
        provider=provider,
        workspace_id=workspace_id,
    )
    return result


@router.get("/gross-margin", response_model=GrossMarginSummary)
async def get_gross_margin(
    window_hours: int = Query(default=24, ge=1, le=720),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return revenue, COGS, and gross margin over the requested window."""
    service = AdminTelemetryService(session)
    return await service.get_gross_margin(window_hours=window_hours)


@router.get("/proxy-health", response_model=ProxyHealthResponse)
async def get_proxy_health(
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return the active proxy provider's health snapshot."""
    # Proxy health does not require a DB session; it probes the proxy directly.
    service = AdminTelemetryService(session=None)  # type: ignore[arg-type]
    return await service.get_proxy_health()


@router.get("/celery-queues", response_model=CeleryQueueResponse)
async def get_celery_queues(
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return Celery queue and worker telemetry."""
    service = AdminTelemetryService(session=None)  # type: ignore[arg-type]
    return await service.get_celery_queue_stats()


@router.post("/celery-queues/{queue_name}/purge", response_model=PurgeDeadQueueResponse)
async def purge_celery_queue(
    queue_name: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Purge stalled tasks from a Celery queue. Requires interactive superadmin session."""
    if not auth.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    service = AdminTelemetryService(session)
    try:
        result = await service.purge_dead_letter_queue(
            queue_name=queue_name,
            actor_id=str(auth.user.id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return result
