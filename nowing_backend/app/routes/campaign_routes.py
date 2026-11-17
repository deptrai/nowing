"""REST endpoints for Lead Gen Campaign Builder (Story 25.5 / Signal-First UX)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    CampaignSource,
    CampaignTrigger,
    Permission,
    WorkspaceMembership,
    get_async_session,
)
from app.dependencies.auth import RequirePermission
from app.lead_intelligence.campaign.planner import LeadGenPlanner
from app.lead_intelligence.campaign.presets import (
    VerticalPreset,
    generate_reverse_icp,
    get_vertical_preset,
    list_vertical_presets,
)
from app.lead_intelligence.campaign.schemas import (
    CampaignPlanResponse,
    CampaignSpec,
    SourcePlanAllocation,
)
from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.campaign_service import (
    ConcurrentCampaignRunError,
)
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)
from app.users import require_session_context
from app.tenant_context import set_request_tenant_context
from app.utils.rbac import check_permission

router = APIRouter(prefix="/workspaces", tags=["campaigns"])


class ReverseIcpRequest(BaseModel):
    """Request payload for reverse-ICP analysis."""

    url: str = Field(..., description="Target website or business URL")
    description: str = Field(
        default="", description="Optional business description or product summary"
    )





@router.get("/{workspace_id}/campaigns/presets", response_model=list[VerticalPreset])
async def get_campaign_presets(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> list[VerticalPreset]:
    """List all available vertical presets for Campaign Builder."""
    return list_vertical_presets()


@router.get("/{workspace_id}/campaigns/presets/{preset_id}", response_model=VerticalPreset)
async def get_single_campaign_preset(
    workspace_id: int,
    preset_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> VerticalPreset:
    """Retrieve a specific vertical preset by identifier."""
    return get_vertical_preset(preset_id)


@router.post("/{workspace_id}/campaigns/reverse-icp", response_model=dict[str, Any])
async def analyze_reverse_icp(
    workspace_id: int,
    request: ReverseIcpRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> dict[str, Any]:
    """
    Reverse-ICP Analyzer: Infer target vertical, ICP criteria, keywords, and recommended
    sources based on a customer website URL or business profile prompt.
    """
    return generate_reverse_icp(request.url, request.description)


@router.post("/{workspace_id}/campaigns/plan", response_model=CampaignPlanResponse)
async def plan_campaign(
    workspace_id: int,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> CampaignPlanResponse:
    """Preview subtasks, budget splits, source adapter allocations, and cost estimates."""
    if payload.get("workspace_id") != workspace_id:
        payload["workspace_id"] = workspace_id

    try:
        spec = CampaignSpec.from_payload(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cấu hình chiến dịch không hợp lệ: {exc}",
        ) from exc
    planner = LeadGenPlanner()
    return await planner.create_preflight_plan(spec)


@router.post("/{workspace_id}/campaigns/execute", response_model=LeadGenOrchestratorResult)
async def execute_campaign(
    workspace_id: int,
    payload: dict[str, Any],
    persist: bool = Query(
        default=True, description="Whether to atomically persist results into database"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> LeadGenOrchestratorResult:
    """
    Execute multi-source AI lead generation for a declarative campaign specification
    with semaphore bounding, timeout isolation, composite scoring, and deduplication.
    """
    perm = Permission.LEADS_WRITE if persist else Permission.LEADS_READ
    await check_permission(session, auth, workspace_id, perm)

    # Epic 44.1: 3 bảng campaign mới có FORCE RLS theo workspace_id. Route này
    # không đi qua _set_lead_tenant_context nên set GUC transaction-local ở đây
    # (superuser bypass trong dev/test; prod role non-superuser cần GUC này).
    await set_request_tenant_context(session, workspace_id=workspace_id)

    if payload.get("workspace_id") != workspace_id:
        payload["workspace_id"] = workspace_id

    try:
        spec = CampaignSpec.from_payload(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cấu hình chiến dịch không hợp lệ: {exc}",
        ) from exc
    orchestrator = LeadGenOrchestrator()

    if persist:
        # Epic 44.1: get-or-create campaign (implicit, source='execute') +
        # open run qua seam duy nhất. Chạy khi persist=true; persist=false
        # không đụng bookkeeping (0 row).
        campaign = await campaign_service.get_or_create_campaign(
            session,
            workspace_id=workspace_id,
            name=spec.name,
            direction=spec.direction,
            source=CampaignSource.EXECUTE.value,
            created_by=getattr(auth.user, "id", None),
            input_payload=spec.model_dump(mode="json"),
        )
        try:
            campaign_run = await campaign_service.open_campaign_run(
                campaign.id,
                CampaignTrigger.API.value,
                session,
                spec_snapshot=spec.model_dump(mode="json"),
            )
        except ConcurrentCampaignRunError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        result = await orchestrator.execute_and_persist(
            session=session,
            workspace_id=workspace_id,
            campaign_spec=spec,
            limit=spec.max_total_leads,
            campaign=campaign,
            campaign_run_id=campaign_run.id,
        )
    else:
        result = await orchestrator.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            campaign_spec=spec,
            limit=spec.max_total_leads,
        )

    return result


@router.get("/{workspace_id}/campaigns/sources/status", response_model=list[SourcePlanAllocation])
async def get_campaign_sources_status(
    workspace_id: int,
    province_code: str | None = None,
    district_codes: list[str] = Query(default=[]),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> list[SourcePlanAllocation]:
    """Retrieve operational status, latency, and location coverage across all registered scraper adapters."""
    location_profile = None
    if province_code:
        from app.lead_intelligence.schemas import LocationProfilePayload
        location_profile = LocationProfilePayload(
            province_code=province_code,
            province_name=province_code,
            district_codes=district_codes,
        )

    from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
    registry = LeadSourceAdapterRegistry.get_default()
    return await registry.get_all_source_statuses(
        location_profile=location_profile, workspace_id=workspace_id
    )
