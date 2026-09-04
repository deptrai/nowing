"""Admin routes for real-time LLM token cost, proxy health, and Celery telemetry."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.models.admin_health import AdminHealthAlertRule
from app.rate_limiter import limiter
from app.schemas.admin_health import (
    HealthAlertAcknowledgeRequest,
    HealthAlertItem,
    HealthAlertResolveRequest,
    HealthAlertRuleCreateRequest,
    HealthAlertRuleItem,
    HealthAlertRuleListResponse,
    HealthAlertsListResponse,
    HealthCategoriesListResponse,
    HealthHistoryListResponse,
    HealthOverviewResponse,
    HealthProbeResultResponse,
    HealthProbeRunRequest,
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
from app.services.health.result_store import HealthResultStore
from app.services.health.third_party_health_service import ThirdPartyHealthService
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/telemetry", tags=["admin"])

# Also mount health endpoints at the spec-required /admin/health prefix.
health_router = APIRouter(prefix="/admin/health", tags=["admin-health"])


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


def _build_health_routes() -> None:
    """Register health endpoints on both /admin/telemetry and /admin/health prefixes."""
    for target in (router, health_router):
        # health_router already has /admin/health prefix; its subpaths must not repeat /health.
        prefix = "" if target is health_router else "/health"

        @target.get(f"{prefix}/overview", response_model=HealthOverviewResponse)
        async def get_health_overview(
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """Return aggregated platform health overview and counts."""
            return await ThirdPartyHealthService.get_overview(session)

        @target.get(f"{prefix}/categories", response_model=HealthCategoriesListResponse)
        async def get_health_categories(
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """List all registered health probe categories and counts."""
            items = ThirdPartyHealthService.list_categories()
            return {"items": items, "total": len(items)}

        @target.get(f"{prefix}/statuses", response_model=HealthStatusesListResponse)
        async def get_health_statuses(
            category: str | None = Query(default=None, max_length=50),
            service_id: str | None = Query(default=None, max_length=255),
            limit: int = Query(default=1000, ge=1, le=10000),
            offset: int = Query(default=0, ge=0),
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """List current health status snapshots across services or filtered by category."""
            items = await HealthResultStore.get_latest_status(
                session, category=category, service_id=service_id
            )
            total = len(items)
            return {"items": items[offset : offset + limit], "total": total}

        @target.get(f"{prefix}/alerts", response_model=HealthAlertsListResponse)
        async def get_health_alerts(
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """List active (unresolved, unexpired) health alert incidents."""
            items = await ThirdPartyHealthService.get_active_alerts(session)
            return {"items": items, "total": len(items)}

        @target.post(f"{prefix}/alerts/{{alert_id}}/acknowledge", response_model=HealthAlertItem)
        @limiter.limit("20/minute")
        async def acknowledge_health_alert(
            request: Request,
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
                    detail="Alert not found or already resolved",
                )
            return alert

        @target.post(f"{prefix}/alerts/{{alert_id}}/resolve", response_model=HealthAlertItem)
        @limiter.limit("20/minute")
        async def resolve_health_alert(
            request: Request,
            alert_id: int,
            _payload: HealthAlertResolveRequest = HealthAlertResolveRequest(),
            session: AsyncSession = Depends(get_async_session),
            auth: AuthContext = Depends(require_superuser),
        ) -> Any:
            """Manually resolve an active health alert."""
            if not auth.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            alert = await ThirdPartyHealthService.resolve_alert(session=session, alert_id=alert_id)
            if not alert:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Alert not found",
                )
            return alert

        @target.get(f"{prefix}/history/{{service_id:path}}", response_model=HealthHistoryListResponse)
        async def get_health_history(
            service_id: str,
            hours: int = Query(default=24, ge=1, le=168),
            limit: int = Query(default=1000, ge=1, le=10000),
            offset: int = Query(default=0, ge=0),
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """Return historical probe logs for a specific service ID."""
            clean_id = service_id.strip()
            items = await ThirdPartyHealthService.get_history(
                session,
                service_id=clean_id,
                hours=hours,
                limit=limit,
                offset=offset,
            )
            return {
                "service_id": service_id,
                "items": items,
                "total": len(items),
                "limit": limit,
                "offset": offset,
            }

        @target.post(f"{prefix}/probe/category/{{category}}", response_model=list[HealthProbeResultResponse])
        @limiter.limit("10/minute")
        async def run_category_health_probe(
            request: Request,
            category: str,
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> Any:
            """Trigger an on-demand probe execution for all services in a category."""
            results = await ThirdPartyHealthService.run_category_probes(session, category=category)
            if not results:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No probes registered for category '{category}'",
                )
            return results

        @target.post(f"{prefix}/probe/{{service_id:path}}", response_model=HealthProbeResultResponse)
        @limiter.limit("30/minute")
        async def run_single_health_probe(
            request: Request,
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

        @target.get(f"{prefix}/rules", response_model=HealthAlertRuleListResponse)
        async def get_health_rules(
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> dict[str, Any]:
            """List admin health alert rules."""
            items = await ThirdPartyHealthService.list_rules(session)
            return {"items": items, "total": len(items)}

        @target.get(f"{prefix}/rules/{{rule_id}}", response_model=HealthAlertRuleItem)
        async def get_health_rule(
            rule_id: int,
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> Any:
            """Get a single admin health alert rule."""
            rule = await ThirdPartyHealthService.get_rule(session, rule_id)
            if not rule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Rule not found",
                )
            return rule

        @target.post(f"{prefix}/rules", response_model=HealthAlertRuleItem, status_code=status.HTTP_201_CREATED)
        @limiter.limit("10/minute")
        async def create_health_rule(
            request: Request,
            payload: HealthAlertRuleCreateRequest,
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> Any:
            """Create a new admin health alert rule."""
            rule = AdminHealthAlertRule(
                name=payload.name,
                category=payload.category,
                service_id_pattern=payload.service_id_pattern,
                condition_json=payload.condition_json,
                severity=payload.severity,
                channels=payload.channels,
                cooldown_minutes=payload.cooldown_minutes,
                enabled=payload.enabled,
            )
            created = await ThirdPartyHealthService.create_rule(session, rule)
            return created

        @target.put(f"{prefix}/rules/{{rule_id}}", response_model=HealthAlertRuleItem)
        @limiter.limit("10/minute")
        async def update_health_rule(
            request: Request,
            rule_id: int,
            payload: HealthAlertRuleCreateRequest,
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> Any:
            """Update an admin health alert rule."""
            rule = await ThirdPartyHealthService.get_rule(session, rule_id)
            if not rule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Rule not found",
                )
            rule.name = payload.name
            rule.category = payload.category
            rule.service_id_pattern = payload.service_id_pattern
            rule.condition_json = payload.condition_json
            rule.severity = payload.severity
            rule.channels = payload.channels
            rule.cooldown_minutes = payload.cooldown_minutes
            rule.enabled = payload.enabled
            updated = await ThirdPartyHealthService.update_rule(session, rule)
            return updated

        @target.delete(f"{prefix}/rules/{{rule_id}}", status_code=status.HTTP_204_NO_CONTENT)
        @limiter.limit("10/minute")
        async def delete_health_rule(
            request: Request,
            rule_id: int,
            session: AsyncSession = Depends(get_async_session),
            _auth: AuthContext = Depends(require_superuser),
        ) -> None:
            """Delete an admin health alert rule."""
            deleted = await ThirdPartyHealthService.delete_rule(session, rule_id)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Rule not found",
                )


_build_health_routes()
