"""Celery task that runs the contact-enrichment waterfall (Story 21.3, Task 10).

The task opens its own DB session (via ``get_celery_session_maker``), loads
the ``EnrichmentRequest``, and runs ``EnrichmentService._run_waterfall``. The
provider waterfall performs its own retries with backoff, so the task itself
does not auto-retry: re-running a request would duplicate contacts and billing.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.lead_intelligence.enrichment.service import EnrichmentService
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)


async def _run_enrichment(
    request_id: str,
    workspace_id: int,
    client_id: str | None,
) -> None:
    """Run the provider waterfall for one enrichment request."""
    from app.canonical.tenant_context import set_request_tenant_context
    from app.tasks.celery_tasks import get_celery_session_maker

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        # RLS on enrichment_requests is workspace-scoped: the tenant GUCs must
        # be set BEFORE the request row is read, otherwise it is invisible.
        await set_request_tenant_context(
            session,
            workspace_id=workspace_id,
            client_id=client_id,
        )
        service = EnrichmentService()
        try:
            await service._run_waterfall(session, request_id)
        except Exception as exc:
            logger.exception(
                "enrichment request %s failed with unhandled error: %s",
                request_id,
                exc,
            )
            await service._mark_failed(session, request_id, workspace_id, client_id)


@celery_app.task(name="enrich_lead_task", bind=True)
def enrich_lead_task(
    self,
    request_id: str,
    workspace_id: int,
    client_id: str | None = None,
) -> None:
    """Enrich a lead with verified contacts (best-effort, no auto-retry)."""
    return run_async_celery_task(
        lambda: _run_enrichment(request_id, workspace_id, client_id)
    )
