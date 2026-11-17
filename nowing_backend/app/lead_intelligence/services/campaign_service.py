"""Campaign persistence service (Epic 44.1).

Seam duy nhất để INSERT vào ``campaign_runs`` là
:func:`open_campaign_run` — nó khóa ``pg_advisory_xact_lock`` theo campaign
rồi từ chối nếu còn run ``'running'`` (route trả 409; scheduled skip, không
queue). Bookkeeping junction + finalize đi qua :func:`persist_campaign_leads`
và :func:`finalize_campaign_run`, luôn fail-open đối với junction.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CampaignRunStatus, CampaignSource, CampaignStatus
from app.models.campaigns import CampaignLead, CampaignRun, LeadCampaign

logger = logging.getLogger(__name__)


class ConcurrentCampaignRunError(Exception):
    """Đã có một run ``'running'`` cho cùng campaign (HTTP 409 / skip scheduled)."""

    def __init__(self, campaign_id: UUID, run_id: UUID) -> None:
        self.campaign_id = campaign_id
        self.run_id = run_id
        super().__init__(
            f"campaign {campaign_id} already has a running run ({run_id})"
        )


async def get_or_create_campaign(
    session: AsyncSession,
    *,
    workspace_id: int,
    name: str,
    direction: str,
    source: str = "created",
    created_by: UUID | None = None,
    input_payload: dict[str, Any] | None = None,
) -> LeadCampaign:
    """Get-or-create race-safe theo ``(workspace_id, name, direction)``.

    Precedent: ``lead_batch_service.py`` workspace_tables get-or-create —
    ``ON CONFLICT DO NOTHING`` + re-SELECT.
    """
    stmt = (
        pg_insert(LeadCampaign)
        .values(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name[:300],
            direction=direction,
            source=source,
            created_by=created_by,
            input_payload=input_payload,
        )
        .on_conflict_do_nothing(
            index_elements=["workspace_id", "name", "direction"]
        )
        .returning(LeadCampaign.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is not None:
        campaign = await session.get(LeadCampaign, row[0])
        assert campaign is not None
        return campaign
    # Row lost to a concurrent insert — re-select.
    campaign = (
        await session.execute(
            select(LeadCampaign).where(
                LeadCampaign.workspace_id == workspace_id,
                LeadCampaign.name == name[:300],
                LeadCampaign.direction == direction,
            )
        )
    ).scalar_one()
    return campaign


async def open_campaign_run(
    campaign_id: UUID,
    trigger: str,
    session: AsyncSession,
    *,
    spec_snapshot: dict[str, Any] | None = None,
) -> CampaignRun:
    """Seam DUY NHẤT chèn ``campaign_runs``.

    Lock ``pg_advisory_xact_lock(hashtext('campaign_run'), hashtext(cid))``
    trước, rồi reject nếu còn run ``'running'`` (caller quyết định 409 hoặc
    skip). Đánh dấu campaign ``'running'`` trong lúc chạy.
    """
    # Two-arg advisory lock (precedent workspace_limits/service.py:112).
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtext('campaign_run'), hashtext(:cid))"
        ),
        {"cid": str(campaign_id)},
    )
    existing = (
        await session.execute(
            select(CampaignRun.id).where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == CampaignRunStatus.RUNNING.value,
            )
        )
    ).first()
    if existing is not None:
        raise ConcurrentCampaignRunError(campaign_id, existing[0])

    campaign = await session.get(LeadCampaign, campaign_id)
    if campaign is None:
        raise LookupError(f"campaign {campaign_id} not found")
    campaign.status = CampaignStatus.RUNNING.value

    run = CampaignRun(
        id=uuid4(),
        campaign_id=campaign_id,
        workspace_id=campaign.workspace_id,
        status=CampaignRunStatus.RUNNING.value,
        trigger=trigger,
        spec_snapshot=spec_snapshot,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


async def persist_campaign_leads(
    session: AsyncSession,
    *,
    campaign: LeadCampaign,
    run_id: UUID,
    accepted_lead_ids: list[UUID],
    role: str,
    stats: dict[str, Any],
) -> None:
    """Insert junction ``campaign_leads`` trong SAVEPOINT — fail-open.

    Lỗi junction KHÔNG được hủy ingest (leads đã commit được): raise bị nuốt,
    release savepoint, log warn và đánh dấu ``junction_failed=true`` trong
    stats. ID nguồn là ``summary['accepted_lead_ids']`` của ``ingest_batch``.
    """
    if not accepted_lead_ids:
        return
    try:
        async with session.begin_nested():
            rows = [
                {
                    "id": uuid4(),
                    "campaign_id": campaign.id,
                    "run_id": run_id,
                    "lead_id": lead_id,
                    "workspace_id": campaign.workspace_id,
                    "role": role,
                }
                for lead_id in accepted_lead_ids
            ]
            stmt = (
                pg_insert(CampaignLead)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["campaign_id", "lead_id"])
            )
            await session.execute(stmt)
    except Exception as exc:  # noqa: BLE001 — fail-open theo spec
        stats["junction_failed"] = True
        logger.warning(
            "campaign_leads junction insert failed (fail-open) "
            "campaign=%s run=%s: %s",
            campaign.id,
            run_id,
            exc,
        )


async def finalize_campaign_run(
    session: AsyncSession,
    *,
    run_id: UUID,
    status: str,
    stats: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Kết thúc run (``succeeded``/``failed``) + cập nhật campaign status.

    Mọi return path của ``execute_and_persist`` phải gọi hàm này khi
    ``campaign_run_id`` có mặt — không bao giờ bỏ run ở trạng thái
    ``'running'``.
    """
    finished_at = datetime.now(UTC)
    await session.execute(
        update(CampaignRun)
        .where(CampaignRun.id == run_id)
        .values(
            status=status,
            finished_at=finished_at,
            stats=stats or {},
            error=(error[:2000] if error else None),
        )
    )
    campaign_status = (
        CampaignStatus.COMPLETED.value
        if status == CampaignRunStatus.SUCCEEDED.value
        else CampaignStatus.FAILED.value
    )
    run = await session.get(CampaignRun, run_id)
    campaign_id = run.campaign_id if run is not None else None
    if campaign_id is not None:
        await session.execute(
            update(LeadCampaign)
            .where(LeadCampaign.id == campaign_id)
            .values(status=campaign_status)
        )


# ---------------------------------------------------------------------------
# Epic 44.2 — response mapper khớp FE ``campaignSchema``
# (nowing_web/contracts/types/campaign.types.ts). Ưu tiên ``input_payload``
# (FE shape gốc lúc create); fallback reconstruct từ ``spec_snapshot`` mới
# nhất của ``campaign_runs`` (implicit campaigns từ execute route).
# ---------------------------------------------------------------------------

_DEFAULT_LAUNCH_CONFIG: dict[str, Any] = {
    "schedule_type": "once",
    "cron_expression": None,
    "start_time": None,
    "auto_start": True,
    "export_destination": "workspace",
    "notification_webhook": None,
}


def _spec_snapshot_to_fe_shape(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Rebuild FE shape (icp_config/source_budget_config/launch_config) từ
    CampaignSpec model_dump — cho implicit campaigns không có input_payload."""
    icp = snapshot.get("icp_criteria") or {}
    location_profile = icp.get("location_profile")
    budgets = snapshot.get("source_budgets") or []
    sources = snapshot.get("target_sources") or [
        b.get("source_name") for b in budgets if b.get("source_name")
    ]
    launch_meta = (snapshot.get("metadata") or {}).get("launch_config") or {}
    return {
        "icp_config": {
            "template": "custom",
            "target_industries": icp.get("target_industries") or [],
            "locations": icp.get("target_locations") or [],
            "company_size_range": (icp.get("target_company_sizes") or [None])[0],
            "tech_stack": icp.get("target_tech_stack") or [],
            "intents": snapshot.get("intent_tags") or [],
            "negative_keywords": icp.get("negative_keywords") or [],
            "reverse_icp_url": None,
            "custom_instructions": None,
            "location_profile": location_profile,
        },
        "source_budget_config": {
            # FE schema: sources min-1 — fallback adapter đầu tiên trong budgets.
            "sources": sources or ([budgets[0]["source_name"]] if budgets else ["muasamcong"]),
            "expected_leads_target": snapshot.get("max_total_leads") or 100,
            "max_daily_spend_vnd": 0,
            "min_fit_score": float(
                (snapshot.get("icp_criteria") or {}).get("min_fit_score", 0) or 0
            ),
            "min_intent_score": 0,
            "max_contacts_per_lead": 3,
            "exclude_dnc": True,
            "auto_unlock_verified_phones": bool(
                budgets and budgets[0].get("auto_unlock")
            ),
        },
        "launch_config": {**_DEFAULT_LAUNCH_CONFIG, **launch_meta},
    }


async def campaign_to_response(session: AsyncSession, campaign: LeadCampaign) -> dict[str, Any]:
    """Map ``LeadCampaign`` → dict khớp FE ``campaignSchema``.

    ``input_payload`` truthy → merge scalar fields lên payload gốc (giữ nguyên
    FE shape); fallback build từ ``spec_snapshot`` run mới nhất. ``sources``
    đảm bảo min-1. Wire test backend là source-of-truth.
    """
    payload: dict[str, Any]
    if campaign.input_payload:
        payload = dict(campaign.input_payload)
        payload.setdefault("icp_config", {})
        payload.setdefault("source_budget_config", {})
        payload.setdefault("launch_config", dict(_DEFAULT_LAUNCH_CONFIG))
    else:
        latest_run = (
            await session.execute(
                select(CampaignRun.spec_snapshot)
                .where(CampaignRun.campaign_id == campaign.id)
                .order_by(CampaignRun.started_at.desc())
                .limit(1)
            )
        ).first()
        snapshot = (latest_run[0] if latest_run else None) or {}
        payload = _spec_snapshot_to_fe_shape(snapshot)

    budget_cfg = payload.get("source_budget_config") or {}
    if not (budget_cfg.get("sources") or []):
        budget_cfg["sources"] = ["muasamcong"]
        payload["source_budget_config"] = budget_cfg

    # Đếm leads junction + run mới nhất (2 query nhẹ — không denormalize v1).
    collected = (
        await session.execute(
            select(func.count())
            .select_from(CampaignLead)
            .where(CampaignLead.campaign_id == campaign.id)
        )
    ).scalar_one()
    last_run = (
        await session.execute(
            select(CampaignRun.finished_at)
            .where(CampaignRun.campaign_id == campaign.id)
            .order_by(CampaignRun.started_at.desc())
            .limit(1)
        )
    ).first()

    return {
        "id": str(campaign.id),
        "workspace_id": campaign.workspace_id,
        "name": campaign.name,
        "description": payload.get("description"),
        "status": campaign.status,
        "icp_config": payload.get("icp_config") or {},
        "source_budget_config": budget_cfg,
        "launch_config": payload.get("launch_config") or dict(_DEFAULT_LAUNCH_CONFIG),
        "collected_leads_count": collected or 0,
        "qualified_leads_count": 0,
        "estimated_cost_vnd": 0,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else "",
        "updated_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "created_by_user_id": (
            str(campaign.created_by) if campaign.created_by else None
        ),
        "last_run_at": last_run[0].isoformat() if last_run and last_run[0] else None,
    }


async def list_campaigns(
    session: AsyncSession,
    *,
    workspace_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    include_implicit: bool = False,
) -> dict[str, Any]:
    """Paged list trả ``{items, total, limit, offset}`` (FE campaignListResponseSchema).

    Default ``source='created'``; ``?include_implicit=true`` expose cả
    ``'execute'``/``'api'`` (44.1 implicit campaigns).
    """
    conditions = [LeadCampaign.workspace_id == workspace_id]
    if not include_implicit:
        conditions.append(LeadCampaign.source == CampaignSource.CREATED.value)
    if status:
        conditions.append(LeadCampaign.status == status)

    total = (
        await session.execute(
            select(func.count()).select_from(LeadCampaign).where(*conditions)
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(LeadCampaign)
            .where(*conditions)
            .order_by(LeadCampaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    items = [await campaign_to_response(session, c) for c in rows]
    return {"items": items, "total": total or 0, "limit": page_size, "offset": (page - 1) * page_size}
