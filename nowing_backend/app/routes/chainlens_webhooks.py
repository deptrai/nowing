"""Inbound Webhook receiver for ChainLens recurring search monitors (Story 20.8)."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch.launch import launch_run
from app.automations.persistence import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.db import get_async_session
from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.monitors import ChainLensMonitorClient
from app.tasks.webset_import import import_webset_leads

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
        return {
            "status": "enqueued",
            "run_id": str(run.id),
            "trigger_id": str(matched_trigger.id),
        }
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


@router.post(
    "/webset-idle",
    status_code=status.HTTP_200_OK,
    summary="Receive ChainLens Webset idle completion notification (Story 41.1)",
)
async def receive_chainlens_webset_idle_webhook(
    request: Request,
    t: str | None = Query(None, description="Per-webset webhook secret token"),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Process incoming webset.idle webhook event from ChainLens.

    Validates per-webset secret query parameter 't', deduplicates against
    last_delivery_id, updates webset campaign stats, and enqueues asynchronous
    lead ingestion.
    """
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON body: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected JSON object body",
        )

    event = payload.get("event")
    item_status = payload.get("status")
    if not (event == "webset.idle" or item_status == "idle"):
        logger.warning(
            "[ChainLensWebsetWebhook] Invalid event type: event=%s status=%s",
            event,
            item_status,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event type; expected 'webset.idle' or status 'idle'",
        )

    webset_id = payload.get("websetId") or payload.get("webset_id")
    if not webset_id:
        logger.warning("[ChainLensWebsetWebhook] Missing websetId in payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing websetId in payload",
        )

    if not t:
        logger.warning("[ChainLensWebsetWebhook] Missing webhook auth token '?t='")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook authentication token",
        )

    stmt = select(WebsetCampaign).where(WebsetCampaign.webset_id == str(webset_id))
    res = await session.execute(stmt)
    campaign = res.scalar_one_or_none()
    if not campaign:
        logger.warning(
            "[ChainLensWebsetWebhook] Webset campaign not found for webset_id=%s",
            webset_id,
        )
        # Spec 41.1: ack với 'ignored' thay vì 4xx để ChainLens không retry-storm
        # các webset mà Nowing không theo dõi.
        return {"status": "ignored", "webset_id": webset_id}

    if not campaign.webhook_secret or not hmac.compare_digest(
        t, campaign.webhook_secret
    ):
        logger.warning(
            "[ChainLensWebsetWebhook] Invalid webhook authentication token for webset_id=%s",
            webset_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authentication token",
        )

    delivery_id = (
        payload.get("id")
        or payload.get("deliveryId")
        or payload.get("delivery_id")
        or request.headers.get("x-delivery-id")
    )
    if delivery_id and campaign.last_delivery_id == str(delivery_id):
        logger.info(
            "[ChainLensWebsetWebhook] Duplicate webhook delivery %s for webset %s; skipping enqueue",
            delivery_id,
            webset_id,
        )
        return {
            "status": "duplicate",
            "webset_id": str(webset_id),
        }

    # Enqueue trước khi ghi last_delivery_id: nếu broker fail → 5xx để
    # ChainLens retry, tránh đánh dấu đã xử lý mà mất luôn job import.
    import_webset_leads.delay(str(webset_id))

    if delivery_id:
        campaign.last_delivery_id = str(delivery_id)
    if "stats" in payload and isinstance(payload["stats"], dict):
        campaign.stats = payload["stats"]
    await session.commit()
    logger.info(
        "[ChainLensWebsetWebhook] Enqueued import_webset_leads for webset_id=%s delivery_id=%s",
        webset_id,
        delivery_id,
    )
    return {
        "status": "accepted",
        "webset_id": str(webset_id),
    }
