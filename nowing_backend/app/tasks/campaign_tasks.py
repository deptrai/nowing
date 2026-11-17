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
from typing import Any
from uuid import UUID

from celery import shared_task

from app.db import async_session_maker
from app.lead_intelligence.campaign.schemas import CampaignSpec
from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator
from app.models.campaigns import CampaignRun, LeadCampaign
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
