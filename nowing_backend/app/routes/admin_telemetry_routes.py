"""Admin routes for real-time LLM token cost, proxy health, and Celery telemetry."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.admin_health import (
    HealthAlertAcknowledgeRequest,
    HealthAlertItem,
    HealthAlertsListResponse,
    HealthHistoryListResponse,
    HealthOverviewResponse,
    HealthProbeResultResponse,
    HealthStatusesListResponse,
)
from app.schemas.admin_telemetry import (
    CeleryQueueResponse,
    GrossMarginSummary,
    LlmCostBreakdown,
    ProxyHealthResponse,
    PurgeDeadQueueResponse,
)
from app.services.admin_telemetry_service import AdminTelemetryService
from app.services.health.third_party_health_service import ThirdPartyHealthService
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


# ============================================================================
# Third-Party Health & Operations Endpoints (Story 25.7)
# ============================================================================


@router.get("/health/overview", response_model=HealthOverviewResponse)
async def get_health_overview(
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return aggregated platform health overview and counts."""
    return await ThirdPartyHealthService.get_overview(session)


@router.get("/health/statuses", response_model=HealthStatusesListResponse)
async def get_health_statuses(
    category: str | None = Query(default=None, max_length=50),
    service_id: str | None = Query(default=None, max_length=255),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """List current health status snapshots across services or filtered by category."""
    items = await ThirdPartyHealthService.get_statuses(session, category=category, service_id=service_id)
    return {"items": items, "total": len(items)}


@router.get("/health/alerts", response_model=HealthAlertsListResponse)
async def get_health_alerts(
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """List active (unresolved, unexpired) health alert incidents."""
    items = await ThirdPartyHealthService.get_active_alerts(session)
    return {"items": items, "total": len(items)}


@router.post("/health/alerts/{alert_id}/acknowledge", response_model=HealthAlertItem)
async def acknowledge_health_alert(
    alert_id: int,
    payload: HealthAlertAcknowledgeRequest = HealthAlertAcknowledgeRequest(),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> Any:
    """Acknowledge an active health alert and snooze notifications/banner."""
    if not auth.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user_id = auth.user.id
    alert = await ThirdPartyHealthService.acknowledge_alert(
        session=session,
        alert_id=alert_id,
        user_id=user_id,
        duration_minutes=payload.duration_minutes,
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    return alert


@router.get("/health/history/{service_id:path}", response_model=HealthHistoryListResponse)
async def get_health_history(
    service_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Return historical probe logs for a specific service ID."""
    clean_id = service_id.strip()
    items = await ThirdPartyHealthService.get_history(session, service_id=clean_id, hours=hours)
    return {"service_id": service_id, "items": items, "total": len(items)}


@router.post("/health/probe/{service_id:path}", response_model=HealthProbeResultResponse)
async def run_single_health_probe(
    service_id: str,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> Any:
    """Trigger an on-demand probe execution for a single service."""
    clean_id = service_id.strip()
    result = await ThirdPartyHealthService.run_single_probe(session, service_id=clean_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' probe not registered",
        )
    return result

