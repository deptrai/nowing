"""REST endpoints for Lead Gen Campaign Builder (Story 25.5 / Signal-First UX)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    CampaignLead,
    CampaignRun,
    CampaignSource,
    CampaignStatus,
    CampaignTrigger,
    Lead,
    LeadCampaign,
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
from app.lead_intelligence.schemas import LeadRead
from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.campaign_service import (
    CampaignQuotaExceededError,
    ConcurrentCampaignRunError,
)
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)
from app.users import require_session_context
from app.tenant_context import set_request_tenant_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["campaigns"])

# Epic 44.2: status user settable qua PATCH — 'running'/'completed'/'failed'
# là machine-managed (open/finalize), không cho set tay.
_USER_SETTABLE_STATUSES = {
    CampaignStatus.DRAFT.value,
    CampaignStatus.SCHEDULED.value,
    CampaignStatus.PAUSED.value,
    CampaignStatus.ARCHIVED.value,
}

# 45.3 G-1: frequency user settable qua PATCH; 'custom' bắt buộc schedule_cron.
_USER_SETTABLE_FREQUENCIES = {
    "once",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "custom",
}


def _cron_is_valid(expr: str) -> bool:
    """Validate cron bằng croniter (pattern campaign_service.compute_next_run_at)."""
    try:
        from croniter import croniter

        croniter(expr)
    except Exception:
        return False
    return True


def _launch_schedule_from_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """45.3 T2: map ``launch_config`` trong create payload → schedule scalars.

    ``schedule_type='recurring'`` → bắt buộc ``cron_expression`` hợp lệ
    (422 khi thiếu/sai); ``max_runs`` int ≥ 1 nếu có. ``'once'``/không có
    launch_config → ``None`` (scalars giữ default, không wire ngược).
    """
    launch_config = (payload or {}).get("launch_config") or {}
    if launch_config.get("schedule_type") != "recurring":
        return None
    cron = launch_config.get("cron_expression")
    if not isinstance(cron, str) or not cron.strip() or not _cron_is_valid(cron):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lịch chạy định kỳ yêu cầu biểu thức cron hợp lệ.",
        )
    max_runs = launch_config.get("max_runs")
    if max_runs is not None:
        try:
            max_runs = int(max_runs)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="max_runs phải là số nguyên ≥ 1.",
            ) from exc
        if max_runs < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="max_runs phải là số nguyên ≥ 1.",
            )
    return {
        "schedule_frequency": "custom",
        "schedule_cron": cron.strip(),
        "max_runs": max_runs,
    }


class CampaignUpdateRequest(BaseModel):
    """PATCH body — name + status + schedule scalars (45.3 G-1)."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    status: str | None = None
    schedule_frequency: str | None = None
    schedule_cron: str | None = None
    max_runs: int | None = Field(default=None, ge=1)


class CampaignRunResponse(BaseModel):
    """Run shape trả cho FE launch/execute?async (spec 44.2)."""

    id: str
    campaign_id: str
    status: str
    trigger: str | None = None
    started_at: str | None = None


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


# Epic 44.2: không response_model — nhánh ?async=true trả dict run-shape
# {campaign_id, run_id, status:'queued'}, filter qua LeadGenOrchestratorResult
# sẽ nuốt mất keys.
@router.post("/{workspace_id}/campaigns/execute")
async def execute_campaign(
    workspace_id: int,
    payload: dict[str, Any],
    persist: bool = Query(
        default=True, description="Whether to atomically persist results into database"
    ),
    run_async: bool = Query(
        default=False,
        alias="async",
        description="Queue execution via celery task (requires persist=true)",
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> LeadGenOrchestratorResult | dict[str, Any]:
    """
    Execute multi-source AI lead generation for a declarative campaign specification
    with semaphore bounding, timeout isolation, composite scoring, and deduplication.

    Epic 44.2: ``?async=true`` (yêu cầu persist=true) → bookkeeping + queue
    celery ``launch_campaign_run`` ngay, trả ``{campaign_id, run_id, status}``.
    """
    perm = Permission.LEADS_WRITE if persist else Permission.LEADS_READ
    await check_permission(session, auth, workspace_id, perm)

    # Epic 44.1: 3 bảng campaign mới có FORCE RLS theo workspace_id. Route này
    # không đi qua _set_lead_tenant_context nên set GUC transaction-local ở đây
    # (superuser bypass trong dev/test; prod role non-superuser cần GUC này).
    await set_request_tenant_context(session, workspace_id=workspace_id)

    if run_async and not persist:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="async=true yêu cầu persist=true",
        )

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
        except CampaignQuotaExceededError as exc:
            # 44.3: quota guard — 429, KHÔNG tạo run row.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Chiến dịch đã đạt giới hạn ({exc}).",
            ) from exc
        if run_async:
            # Epic 44.2: commit bookkeeping (run 'running') rồi queue celery
            # — task dùng session riêng. open_campaign_run chèn status
            # 'running' ngay (seam 44.1); FE chấp nhận run-shape này.
            await session.commit()
            _launch_campaign_run.apply_async(
                args=[str(campaign.id), str(campaign_run.id), workspace_id]
            )
            return {
                "campaign_id": str(campaign.id),
                "run_id": str(campaign_run.id),
                "status": "queued",
            }
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


# ---------------------------------------------------------------------------
# Epic 44.2 — Campaign CRUD + launch + async runs.
# Các literal route (/presets, /plan, /execute, /sources/status...) ở trên đã
# đăng ký trước nên không bị shadow bởi /{campaign_id}.
# ---------------------------------------------------------------------------


def _run_to_response(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "campaign_id": str(run.campaign_id),
        "status": run.status,
        "trigger": run.trigger,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "stats": run.stats or {},
        "cost_micros": run.cost_micros,
        "error": run.error,
    }


async def _get_campaign_or_404(
    session: AsyncSession, workspace_id: int, campaign_id: str
) -> LeadCampaign:
    try:
        cid = UUID(campaign_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign không tồn tại"
        ) from exc
    campaign = await session.get(LeadCampaign, cid)
    if campaign is None or campaign.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign không tồn tại"
        )
    return campaign


@router.get("/{workspace_id}/campaigns")
async def list_campaigns_route(
    workspace_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    include_implicit: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> dict[str, Any]:
    """Danh sách campaign (paged) — default chỉ source='created'."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    return await campaign_service.list_campaigns(
        session,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        include_implicit=include_implicit,
    )


@router.get("/{workspace_id}/campaigns/{campaign_id}")
async def get_campaign_route(
    workspace_id: int,
    campaign_id: str,
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> dict[str, Any]:
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)
    return await campaign_service.campaign_to_response(session, campaign)


@router.get("/{workspace_id}/campaigns/{campaign_id}/runs")
async def list_campaign_runs_route(
    workspace_id: int,
    campaign_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> dict[str, Any]:
    """Run history paged, mới nhất trước."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)
    total = (
        await session.execute(
            select(func.count())
            .select_from(CampaignRun)
            .where(CampaignRun.campaign_id == campaign.id)
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign.id)
            .order_by(CampaignRun.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [_run_to_response(r) for r in rows],
        "total": total or 0,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }


@router.get("/{workspace_id}/campaigns/{campaign_id}/leads")
async def list_campaign_leads_route(
    workspace_id: int,
    campaign_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value)
    ),
) -> dict[str, Any]:
    """Leads thu qua campaign (paged join campaign_leads → leads, mới nhất trước).

    Epic 45.2 — reader đầu tiên của junction ``campaign_leads``: item =
    ``LeadRead`` + ``lead_role``/``run_id``/``added_at`` (created_at junction).
    Composite FK bắt buộc join trên cả ``lead_id`` lẫn ``workspace_id``.
    """
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)
    total = (
        await session.execute(
            select(func.count())
            .select_from(CampaignLead)
            .where(CampaignLead.campaign_id == campaign.id)
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(CampaignLead, Lead)
            .join(
                Lead,
                (Lead.id == CampaignLead.lead_id)
                & (Lead.workspace_id == CampaignLead.workspace_id),
            )
            .where(CampaignLead.campaign_id == campaign.id)
            .order_by(CampaignLead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = []
    for campaign_lead, lead in rows:
        item = LeadRead.model_validate(lead).model_dump(mode="json")
        item["lead_role"] = campaign_lead.role
        item["run_id"] = (
            str(campaign_lead.run_id) if campaign_lead.run_id else None
        )
        item["added_at"] = campaign_lead.created_at.isoformat()
        items.append(item)
    return {
        "items": items,
        "total": total or 0,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }


@router.post("/{workspace_id}/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign_route(
    workspace_id: int,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value)
    ),
) -> dict[str, Any]:
    """Tạo campaign từ FE payload; lưu raw dict vào input_payload."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_WRITE)
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

    # 45.3 T2: validate launch_config schedule TRƯỚC insert — recurring thiếu
    # cron → 422, không tạo campaign (M9).
    launch_schedule = _launch_schedule_from_payload(payload)

    # Dup (workspace_id, name, direction) → 409 friendly.
    existing = (
        await session.execute(
            select(LeadCampaign.id).where(
                LeadCampaign.workspace_id == workspace_id,
                LeadCampaign.name == spec.name[:300],
                LeadCampaign.direction == spec.direction,
            )
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Chiến dịch '{spec.name}' đã tồn tại trong workspace này "
                f"(trùng tên + chiều {spec.direction})."
            ),
        )

    campaign = await campaign_service.get_or_create_campaign(
        session,
        workspace_id=workspace_id,
        name=spec.name,
        direction=spec.direction,
        source=CampaignSource.CREATED.value,
        created_by=getattr(auth.user, "id", None),
        input_payload=payload,
    )
    if launch_schedule is not None:
        # Scalars = source of truth cho scheduler; campaign mới → runs_count=0.
        campaign.schedule_frequency = launch_schedule["schedule_frequency"]
        campaign.schedule_cron = launch_schedule["schedule_cron"]
        campaign.max_runs = launch_schedule["max_runs"]
        campaign.next_run_at = campaign_service.compute_next_run_at(
            campaign, runs_count=0
        )
    await session.commit()
    return await campaign_service.campaign_to_response(session, campaign)


@router.patch("/{workspace_id}/campaigns/{campaign_id}")
async def update_campaign_route(
    workspace_id: int,
    campaign_id: str,
    payload: CampaignUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value)
    ),
) -> dict[str, Any]:
    """PATCH — name + status + schedule scalars (45.3); machine-managed → 422."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_WRITE)
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)
    fields_set = payload.model_fields_set

    # 45.3 G-6: 'archived' là one-way — mọi PATCH status trên campaign đã
    # archive → 422 (PATCH name/schedule không đụng status vẫn OK).
    if (
        payload.status is not None
        and campaign.status == CampaignStatus.ARCHIVED.value
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chiến dịch đã lưu trữ, không thể thay đổi trạng thái.",
        )

    if payload.status is not None and payload.status not in _USER_SETTABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Trạng thái '{payload.status}' không hợp lệ. Chỉ chấp nhận: "
                f"{sorted(_USER_SETTABLE_STATUSES)}."
            ),
        )

    # ---- 45.3 G-1: apply schedule scalars (single source of truth) ----
    recompute_needed = False
    if payload.schedule_frequency is not None:
        freq = payload.schedule_frequency
        if freq not in _USER_SETTABLE_FREQUENCIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Tần suất lịch chạy '{freq}' không hợp lệ. Chỉ chấp nhận: "
                    f"{sorted(_USER_SETTABLE_FREQUENCIES)}."
                ),
            )
        if freq == "once":
            # 'once' → clear schedule (spec: cron=None, next_run_at=None).
            campaign.schedule_frequency = "once"
            campaign.schedule_cron = None
        elif freq == "custom":
            # 'custom' bắt buộc cron hợp lệ — mới từ PATCH hoặc sẵn có.
            cron = (
                payload.schedule_cron
                if "schedule_cron" in fields_set
                else campaign.schedule_cron
            )
            if not cron or not _cron_is_valid(cron):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tần suất 'custom' yêu cầu biểu thức cron hợp lệ.",
                )
            campaign.schedule_frequency = "custom"
            campaign.schedule_cron = cron
        else:
            # Frequency khác → clear cron, trừ khi PATCH gửi kèm cron mới.
            new_cron = (
                payload.schedule_cron if "schedule_cron" in fields_set else None
            )
            if new_cron is not None and not _cron_is_valid(new_cron):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Biểu thức cron không hợp lệ.",
                )
            campaign.schedule_frequency = freq
            campaign.schedule_cron = new_cron
        recompute_needed = True
    elif "schedule_cron" in fields_set:
        # PATCH cron đơn lẻ: null → clear; set → freq='custom' (cron thắng
        # trong compute_next_run_at).
        cron = payload.schedule_cron
        if cron is None:
            campaign.schedule_cron = None
        else:
            if not _cron_is_valid(cron):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Biểu thức cron không hợp lệ.",
                )
            campaign.schedule_cron = cron
            campaign.schedule_frequency = "custom"
        recompute_needed = True

    if "max_runs" in fields_set:
        campaign.max_runs = payload.max_runs  # None = unlimited; ge=1 ở schema
        recompute_needed = True

    # Mọi PATCH đổi schedule hoặc status→'scheduled' → recompute next_run_at.
    if recompute_needed or payload.status == CampaignStatus.SCHEDULED.value:
        runs_count = (
            await session.execute(
                select(func.count())
                .select_from(CampaignRun)
                .where(CampaignRun.campaign_id == campaign.id)
            )
        ).scalar_one() or 0
        next_run_at = campaign_service.compute_next_run_at(
            campaign, runs_count=runs_count
        )
        if (
            payload.status == CampaignStatus.SCHEDULED.value
            and next_run_at is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Chiến dịch chưa có lịch chạy hợp lệ — không thể chuyển "
                    "sang 'scheduled'."
                ),
            )
        campaign.next_run_at = next_run_at

    if payload.status is not None:
        campaign.status = payload.status

    if payload.name is not None and payload.name != campaign.name:
        clash = (
            await session.execute(
                select(LeadCampaign.id).where(
                    LeadCampaign.workspace_id == workspace_id,
                    LeadCampaign.name == payload.name[:300],
                    LeadCampaign.direction == campaign.direction,
                    LeadCampaign.id != campaign.id,
                )
            )
        ).first()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tên chiến dịch '{payload.name}' đã tồn tại.",
            )
        campaign.name = payload.name[:300]

    await session.commit()
    await session.refresh(campaign)
    return await campaign_service.campaign_to_response(session, campaign)


@router.post("/{workspace_id}/campaigns/{campaign_id}/launch")
async def launch_campaign_route(
    workspace_id: int,
    campaign_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value)
    ),
) -> dict[str, Any]:
    """Launch: bookkeeping run + queue celery task (async execution)."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_WRITE)
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)

    if campaign.status in (CampaignStatus.PAUSED.value, CampaignStatus.ARCHIVED.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Chiến dịch đang ở trạng thái '{campaign.status}', "
                "không thể kích hoạt."
            ),
        )

    payload = campaign.input_payload or {}
    snapshot = campaign.input_payload
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Chiến dịch chưa có cấu hình thực thi (input_payload rỗng) — "
                "không thể kích hoạt."
            ),
        )
    try:
        spec = CampaignSpec.from_payload({**payload, "workspace_id": workspace_id})
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cấu hình chiến dịch không hợp lệ: {exc}",
        ) from exc

    try:
        run = await campaign_service.open_campaign_run(
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
    except CampaignQuotaExceededError as exc:
        # 44.3: quota guard — 429, KHÔNG tạo run row.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Chiến dịch đã đạt giới hạn ({exc}).",
        ) from exc

    await session.commit()
    _launch_campaign_run.apply_async(
        args=[str(campaign.id), str(run.id), workspace_id]
    )
    return {
        "id": str(run.id),
        "campaign_id": str(campaign.id),
        "status": "queued",
        "trigger": run.trigger,
    }


@router.post("/{workspace_id}/campaigns/{campaign_id}/pause")
async def pause_campaign_route(
    workspace_id: int,
    campaign_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value)
    ),
) -> dict[str, Any]:
    """Pause — FE pauseCampaign gọi POST /pause; chỉ cho phép từ 'running'/'scheduled'."""
    await check_permission(session, auth, workspace_id, Permission.LEADS_WRITE)
    await set_request_tenant_context(session, workspace_id=workspace_id)
    campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)
    if campaign.status not in (CampaignStatus.RUNNING.value, CampaignStatus.SCHEDULED.value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Chỉ có thể tạm dừng chiến dịch đang chạy/lên lịch "
                f"(hiện tại: '{campaign.status}')."
            ),
        )
    campaign.status = CampaignStatus.PAUSED.value
    await session.commit()
    await session.refresh(campaign)
    return await campaign_service.campaign_to_response(session, campaign)


class _LaunchCampaignRunProxy:
    """Late-import proxy — tránh import cycle celery_app ↔ routes lúc startup.

    Call sites gọi ``_launch_campaign_run.apply_async(...)`` giống celery task
    thật; test patch nguyên module attr nên vẫn mock được.
    """

    def apply_async(self, *args: Any, **kwargs: Any) -> Any:
        from app.tasks.campaign_tasks import launch_campaign_run

        return launch_campaign_run.apply_async(*args, **kwargs)


_launch_campaign_run = _LaunchCampaignRunProxy()
