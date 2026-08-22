"""Celery worker task for async phone waterfall resolution and auto-refund SLA (Story 21.3)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from celery import shared_task

from app.db import async_session_maker
from app.services.billing_service import BillingService
from app.services.phone_waterfall_service import PhoneWaterfallService
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)


@shared_task(
    name="resolve_phone_waterfall_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def resolve_phone_waterfall_task(
    self,
    workspace_id: int,
    client_id: str | None,
    lead_id: str,
    user_id: str | None,
    source_url: str | None = None,
    raw_text: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Async celery task to run 3-tier phone waterfall resolution for a lead."""

    async def _run() -> dict[str, Any]:
        async with async_session_maker() as session:
            await set_request_tenant_context(
                session, workspace_id=workspace_id, client_id=client_id
            )
            service = PhoneWaterfallService(session)
            res = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id=client_id,
                lead_id=UUID(lead_id),
                user_id=UUID(user_id) if user_id else None,
                source_url=source_url,
                raw_text=raw_text,
                force_refresh=force_refresh,
            )
            return {
                "lead_id": str(res.lead_id),
                "phone_masked": res.phone_masked,
                "tier_reached": res.tier_reached,
                "provider_used": res.provider_used,
                "status": res.status,
                "cost_micros": res.cost_micros,
                "confidence": res.confidence,
                "carrier": res.carrier,
                "is_cached": res.is_cached,
                "contact_id": str(res.contact_id) if res.contact_id else None,
                "degraded": res.degraded,
                "degradation_reason": res.degradation_reason,
            }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("resolve_phone_waterfall_task failed for lead %s", lead_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        return {
            "lead_id": lead_id,
            "status": "failed",
            "error": str(exc),
        }


@shared_task(
    name="auto_refund_lead_task",
    bind=True,
    max_retries=1,
)
def auto_refund_lead_task(
    self,
    workspace_id: int,
    lead_id: str,
    user_id: str | None,
    reason: str = "reported_invalid_phone",
) -> dict[str, Any]:
    """Async celery task to process lead auto-refund."""

    async def _run() -> dict[str, Any]:
        async with async_session_maker() as session:
            await set_request_tenant_context(
                session, workspace_id=workspace_id, client_id=None
            )
            billing = BillingService(session)
            return await billing.auto_refund_lead(
                workspace_id=workspace_id,
                lead_id=UUID(lead_id),
                user_id=UUID(user_id) if user_id else None,
                reason=reason,
            )

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("auto_refund_lead_task failed for lead %s", lead_id)
        return {
            "lead_id": lead_id,
            "refunded": False,
            "error": str(exc),
        }
