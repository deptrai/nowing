"""Inbound Webhook receiver for ChainLens recurring search monitors (Story 20.8)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch.launch import launch_run
from app.automations.persistence import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.db import get_async_session
from app.services.chainlens.monitors import ChainLensMonitorClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/webhooks/chainlens",
    tags=["chainlens_webhooks"],
)

_monitor_client = ChainLensMonitorClient()


def _get_monitor_client() -> ChainLensMonitorClient:
    return _monitor_client


@router.post(
    "/monitors",
    status_code=status.HTTP_200_OK,
    summary="Receive ChainLens recurring monitor findings delta",
)
async def receive_chainlens_monitor_webhook(
    request: Request,
    x_chainlens_signature: str | None = Header(None, alias="X-ChainLens-Signature"),
    session: AsyncSession = Depends(get_async_session),
    client: ChainLensMonitorClient = Depends(_get_monitor_client),
) -> dict[str, Any]:
    """Process incoming monitor delta results from ChainLens.

    Security Gate:
    1. Evaluates HMAC-SHA256 signature from ``X-ChainLens-Signature`` header
       against the raw bytes. Fails with 401 if missing or invalid.
    2. Maps ``monitorId`` to the registered ``AutomationTrigger`` via
       ``params->>'monitor_id'``.
    3. Launches an ``AutomationRun`` with the new delta search findings.
    """
    raw_body = await request.body()

    # 1. HMAC Signature Verification
    if not client.verify_webhook_signature(raw_body, x_chainlens_signature):
        logger.warning(
            "[ChainLensWebhook] Invalid or missing signature on /monitors webhook"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC-SHA256 webhook signature",
        )

    # 2. Parse payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON body: {exc}",
        ) from exc

    monitor_id = payload.get("monitorId") or payload.get("monitor_id")
    if not monitor_id:
        logger.warning("[ChainLensWebhook] Webhook payload missing monitorId")
        return {"status": "ignored", "reason": "missing_monitor_id"}

    # 3. Locate AutomationTrigger by monitor_id in params
    # Handles both JSONB string matching in SQLite/Postgres
    stmt = select(AutomationTrigger).where(
        AutomationTrigger.type == TriggerType.CHAINLENS_MONITOR
    )
    res = await session.execute(stmt)
    triggers = list(res.scalars().all())

    matched_trigger: AutomationTrigger | None = None
    for trg in triggers:
        if trg.params and str(trg.params.get("monitor_id")) == str(monitor_id):
            matched_trigger = trg
            break

    if not matched_trigger:
        logger.warning(
            "[ChainLensWebhook] No active trigger found for monitorId=%s",
            monitor_id,
        )
        return {
            "status": "ignored",
            "reason": f"unknown_monitor:{monitor_id}",
        }

    # 4. Enqueue AutomationRun
    runtime_inputs = {
        "monitor_id": str(monitor_id),
        "query": payload.get("query", ""),
        "results": payload.get("results", []),
        "timestamp": payload.get("timestamp"),
        "event": payload.get("event", "delta_findings"),
    }

    try:
        run = await launch_run(
            session=session,
            trigger=matched_trigger,
            runtime_inputs=runtime_inputs,
        )
        await session.commit()
        logger.info(
            "[ChainLensWebhook] Enqueued AutomationRun id=%s for trigger=%s monitorId=%s",
            run.id,
            matched_trigger.id,
            monitor_id,
        )
        return {"status": "enqueued", "run_id": str(run.id), "trigger_id": str(matched_trigger.id)}
    except Exception as exc:
        logger.error(
            "[ChainLensWebhook] Failed to launch run for monitorId=%s: %s",
            monitor_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue automation run: {exc}",
        ) from exc
