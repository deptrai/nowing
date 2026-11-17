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

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CampaignRunStatus, CampaignStatus
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
