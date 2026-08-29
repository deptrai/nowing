"""REST endpoints for Lead Gen Campaign Builder (Story 25.5 / Signal-First UX)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, get_async_session
from app.lead_intelligence.campaign.planner import LeadGenPlanner
from app.lead_intelligence.campaign.presets import (
    VerticalPreset,
    generate_reverse_icp,
    get_vertical_preset,
    list_vertical_presets,
)
from app.lead_intelligence.campaign.schemas import CampaignSpec, SubTaskPlan
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)
from app.users import require_session_context
from app.utils.rbac import check_permission

router = APIRouter(prefix="/workspaces", tags=["campaigns"])


class ReverseIcpRequest(BaseModel):
    """Request payload for reverse-ICP analysis."""

    url: str = Field(..., description="Target website or business URL")
    description: str = Field(
        default="", description="Optional business description or product summary"
    )


class CampaignPlanResponse(BaseModel):
    """Execution plan breakdown for a campaign spec."""

    campaign_name: str
    workspace_id: int
    total_planned_sources: int
    expected_sources: list[str]
    subtasks: list[SubTaskPlan]


@router.get("/{workspace_id}/campaigns/presets", response_model=list[VerticalPreset])
async def get_campaign_presets(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> list[VerticalPreset]:
    """List all available vertical presets for Campaign Builder."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_READ)
    return list_vertical_presets()


@router.get("/{workspace_id}/campaigns/presets/{preset_id}", response_model=VerticalPreset)
async def get_single_campaign_preset(
    workspace_id: int,
    preset_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> VerticalPreset:
    """Retrieve a specific vertical preset by identifier."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_READ)
    return get_vertical_preset(preset_id)


@router.post("/{workspace_id}/campaigns/reverse-icp", response_model=dict[str, Any])
async def analyze_reverse_icp(
    workspace_id: int,
    request: ReverseIcpRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> dict[str, Any]:
    """
    Reverse-ICP Analyzer: Infer target vertical, ICP criteria, keywords, and recommended
    sources based on a customer website URL or business profile prompt.
    """
    await check_permission(session, auth, workspace_id, Permission.LEADS_READ)
    return generate_reverse_icp(request.url, request.description)


@router.post("/{workspace_id}/campaigns/plan", response_model=CampaignPlanResponse)
async def plan_campaign(
    workspace_id: int,
    spec: CampaignSpec,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> CampaignPlanResponse:
    """Preview subtasks, budget splits, and source adapter allocations for a CampaignSpec."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_READ)
    if spec.workspace_id != workspace_id:
        spec.workspace_id = workspace_id

    planner = LeadGenPlanner()
    subtasks, expected_sources = planner.plan_from_campaign(spec)

    return CampaignPlanResponse(
        campaign_name=spec.name,
        workspace_id=workspace_id,
        total_planned_sources=len(expected_sources),
        expected_sources=expected_sources,
        subtasks=subtasks,
    )


@router.post("/{workspace_id}/campaigns/execute", response_model=LeadGenOrchestratorResult)
async def execute_campaign(
    workspace_id: int,
    spec: CampaignSpec,
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

    if spec.workspace_id != workspace_id:
        spec.workspace_id = workspace_id

    orchestrator = LeadGenOrchestrator()

    if persist:
        result = await orchestrator.execute_and_persist(
            session=session,
            workspace_id=workspace_id,
            campaign_spec=spec,
            limit=spec.max_total_leads,
        )
    else:
        result = await orchestrator.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            campaign_spec=spec,
            limit=spec.max_total_leads,
        )

    return result
