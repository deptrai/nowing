"""Celery task chạy campaign run async (Epic 44.2).

Pattern verbatim ``app.tasks.phone_waterfall_worker``: ``@shared_task`` +
``run_async_celery_task`` (fresh loop + engine dispose), session riêng từ
``async_session_maker``, GUC tenant qua ``set_request_tenant_context``.

Run row được route tạo sẵn (``open_campaign_run`` — seam 44.1, status
'running'). Task chỉ: load campaign + run, chạy ``execute_and_persist``
(commit point duy nhất bên trong), exception → finalize run 'failed' +
commit.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import func, select

from app.db import async_session_maker
from app.db.enums import CampaignRunStatus, CampaignStatus, CampaignTrigger
from app.lead_intelligence.campaign.schemas import CampaignSpec
from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.campaign_service import (
    CAMPAIGN_RUN_STALE_SECONDS,
    CampaignQuotaExceededError,
    ConcurrentCampaignRunError,
)
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator
from app.models.campaigns import CampaignRun, LeadCampaign
from app.models.workspaces import Workspace
from app.tasks.celery_tasks import run_async_celery_task
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)


@shared_task(
    name="launch_campaign_run",
    bind=True,
    max_retries=1,
    soft_time_limit=600,
)
def launch_campaign_run(
    self,
    campaign_id: str,
    run_id: str,
    workspace_id: int,
) -> dict[str, Any]:
    """Async chạy một campaign run đã mở (spec 44.2 — auto_refund pattern)."""

    async def _run() -> dict[str, Any]:
        async with async_session_maker() as session:
            await set_request_tenant_context(session, workspace_id=workspace_id)
            try:
                campaign = await session.get(LeadCampaign, UUID(campaign_id))
                run = await session.get(CampaignRun, UUID(run_id))
                if campaign is None or run is None:
                    raise LookupError(
                        f"campaign {campaign_id} or run {run_id} not found"
                    )
                spec = CampaignSpec.from_payload(
                    {
                        **(campaign.input_payload or {}),
                        "workspace_id": campaign.workspace_id,
                    }
                )
                result = await LeadGenOrchestrator().execute_and_persist(
                    session=session,
                    workspace_id=workspace_id,
                    campaign_spec=spec,
                    limit=spec.max_total_leads,
                    campaign=campaign,
                    campaign_run_id=run.id,
                )
                return {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "status": result.status,
                }
            except Exception as exc:
                # Rollback trước: exception từ execute_and_persist có thể để
                # session ở trạng thái aborted (PendingRollbackError) — finalize
                # 'failed' + commit riêng, run không bao giờ kẹt 'running'.
                await session.rollback()
                await campaign_service.finalize_campaign_run(
                    session, run_id=UUID(run_id), status="failed", error=str(exc)
                )
                await session.commit()
                raise

    try:
        return run_async_celery_task(_run)
    except Exception as exc:  # task-level guard: log + retry once, else failed dict
        logger.exception(
            "launch_campaign_run failed campaign=%s run=%s", campaign_id, run_id
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        return {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "status": "failed",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Epic 44.3 — meta-scheduler: tick campaign đến hạn + stale-run reaper.
# MỘT beat entry (celery_app.conf.beat_schedule['check-campaign-schedules'])
# quét mỗi phút — KHÔNG beat per-campaign (precedent
# check-social-monitored-targets).
# ---------------------------------------------------------------------------


@shared_task(name="check_campaign_schedules")
def check_campaign_schedules() -> dict[str, int]:
    """Meta-scheduler cho campaign định kỳ (Epic 44.3).

    Quét ``lead_campaigns`` ``status='scheduled'`` + ``next_run_at <= now()``:
    mỗi campaign → ``open_campaign_run(trigger='scheduled')`` → commit →
    ``launch_campaign_run.apply_async``. Quota/concurrent → skip +
    ``skipped_by_quota += 1`` (không tạo run row hư). ``next_run_at`` recompute
    sau mỗi skip/launch. Reap run ``'running'`` quá
    ``CAMPAIGN_RUN_STALE_SECONDS`` → ``failed``/``stale_run_timeout``.
    """
    return run_async_celery_task(_check_campaign_schedules)


async def _check_campaign_schedules() -> dict[str, int]:
    launched = skipped = reaped = completed = 0
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        # lead_campaigns/campaign_runs/campaign_leads đều FORCE RLS → phải
        # set tenant GUC từng workspace trước khi scan (workspaces root
        # không RLS nên đọc danh sách id trước được).
        workspace_ids = (
            await session.execute(select(Workspace.id))
        ).scalars().all()
        for workspace_id in workspace_ids:
            await set_request_tenant_context(session, workspace_id=workspace_id)

            # (1) Stale-run reaper: run 'running' quá threshold → failed.
            stale_cutoff = now - timedelta(seconds=CAMPAIGN_RUN_STALE_SECONDS)
            stale_runs = (
                (
                    await session.execute(
                        select(CampaignRun).where(
                            CampaignRun.workspace_id == workspace_id,
                            CampaignRun.status
                            == CampaignRunStatus.RUNNING.value,
                            CampaignRun.started_at.isnot(None),
                            CampaignRun.started_at < stale_cutoff,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for run in stale_runs:
                await campaign_service.finalize_campaign_run(
                    session,
                    run_id=run.id,
                    status=CampaignRunStatus.FAILED.value,
                    error="stale_run_timeout",
                )
                reaped += 1

            # (2) Tick: campaign scheduled + next_run_at quá hạn.
            due_campaigns = (
                (
                    await session.execute(
                        select(LeadCampaign).where(
                            LeadCampaign.workspace_id == workspace_id,
                            LeadCampaign.status == CampaignStatus.SCHEDULED.value,
                            LeadCampaign.next_run_at.isnot(None),
                            LeadCampaign.next_run_at <= now,
                        )
                    )
                )
                .scalars()
                .all()
            )
            pending_launches: list[tuple[UUID, UUID]] = []
            for campaign in due_campaigns:
                # max_runs đếm trên tổng số run của campaign.
                runs_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(CampaignRun)
                        .where(CampaignRun.campaign_id == campaign.id)
                    )
                ).scalar_one() or 0
                if (
                    campaign.max_runs is not None
                    and runs_count >= campaign.max_runs
                ):
                    campaign.next_run_at = None
                    campaign.status = CampaignStatus.COMPLETED.value
                    completed += 1
                    continue
                try:
                    run = await campaign_service.open_campaign_run(
                        campaign.id,
                        CampaignTrigger.SCHEDULED.value,
                        session,
                        spec_snapshot=campaign.input_payload,
                    )
                except (CampaignQuotaExceededError, ConcurrentCampaignRunError):
                    # Skip im lặng + counter — KHÔNG tạo run row hư (44.3 pin).
                    campaign.skipped_by_quota = (
                        campaign.skipped_by_quota or 0
                    ) + 1
                    skipped += 1
                else:
                    runs_count += 1
                    pending_launches.append((campaign.id, run.id))
                    launched += 1
                # Recompute sau mỗi skip/launch; max_runs vừa đạt → completed.
                campaign.next_run_at = campaign_service.compute_next_run_at(
                    campaign, runs_count=runs_count, now=now
                )
                if (
                    campaign.next_run_at is None
                    and campaign.max_runs is not None
                    and runs_count >= campaign.max_runs
                ):
                    campaign.status = CampaignStatus.COMPLETED.value
                    completed += 1
            # Commit TRƯỚC apply_async — task chạy session riêng, chưa commit
            # thì run row không tồn tại bên kia (LookupError).
            await session.commit()
            for campaign_id, run_id in pending_launches:
                launch_campaign_run.apply_async(
                    args=[str(campaign_id), str(run_id), workspace_id]
                )

    return {
        "launched": launched,
        "skipped": skipped,
        "reaped": reaped,
        "completed": completed,
    }
