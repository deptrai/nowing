"""CRM REST routes (Story 21.5)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import CrmSyncLog, Permission, WorkspaceMembership, get_async_session
from app.dependencies.auth import RequirePermission
from app.lead_intelligence.crm.schemas import (
    CrmConnectionCreate,
    CrmConversionLogInput,
    CrmConversionRead,
    CrmDedupInput,
    CrmSyncInput,
)
from app.lead_intelligence.crm.service import CrmConnectionService, CrmSyncService
from app.users import require_session_context

router = APIRouter()


def _to_read(connection: Any) -> dict[str, Any]:
    return {
        "id": connection.id,
        "workspace_id": connection.workspace_id,
        "client_id": connection.client_id,
        "provider": connection.provider,
        "status": connection.status,
        "sync_config": connection.sync_config,
        "last_sync_at": connection.last_sync_at,
        "created_at": connection.created_at,
    }


@router.post("/{workspace_id}/crm/{provider}/connect")
async def connect_crm(
    workspace_id: int,
    provider: str,
    request: CrmConnectionCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Start OAuth for a CRM provider."""
    service = CrmConnectionService(session)
    auth_url = await service.create_pending(
        auth,
        workspace_id,
        provider,
        None,
        request.sync_config.model_dump() if request.sync_config else None,
    )
    return {"auth_url": auth_url}


@router.get("/{workspace_id}/crm/connections")
async def list_crm_connections(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """List active CRM connections."""
    service = CrmConnectionService(session)
    connections = await service.list_connections(auth, workspace_id)
    return [_to_read(c) for c in connections]


@router.get("/{workspace_id}/crm/connections/{connection_id}")
async def get_crm_connection(
    workspace_id: int,
    connection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Get a CRM connection."""
    service = CrmConnectionService(session)
    connection = await service.get_connection(auth, workspace_id, connection_id)
    return _to_read(connection)


@router.delete("/{workspace_id}/crm/connections/{connection_id}")
async def disconnect_crm(
    workspace_id: int,
    connection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Disconnect a CRM connection."""
    service = CrmConnectionService(session)
    await service.disconnect(auth, workspace_id, connection_id)
    return {"status": "disconnected"}


@router.post("/{workspace_id}/crm/connections/{connection_id}/dedup")
async def dedup_crm(
    workspace_id: int,
    connection_id: UUID,
    request: CrmDedupInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Run read-only CRM dedup for a lead."""
    if not request.lead_ids:
        raise HTTPException(status_code=400, detail="lead_ids required")

    service = CrmSyncService(session)
    results: list[dict[str, Any]] = []
    for lead_id in request.lead_ids:
        result = await service.dedup_lead(auth, workspace_id, connection_id, lead_id)
        results.append(
            {
                "degraded": result.degraded,
                "degradation_reasons": result.degradation_reasons,
                "sync_log_id": result.sync_log.id if result.sync_log else None,
            }
        )
    return {"results": results}


@router.post("/{workspace_id}/crm/connections/{connection_id}/sync")
async def sync_crm(
    workspace_id: int,
    connection_id: UUID,
    request: CrmSyncInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Trigger a CRM sync."""
    service = CrmSyncService(session)

    if request.direction == "nowing_to_crm" and request.entity_type == "lead":
        if not request.entity_ids:
            raise HTTPException(status_code=400, detail="entity_ids required")
        results: list[dict[str, Any]] = []
        for entity_id in request.entity_ids:
            result = await service.push_lead(
                auth, workspace_id, connection_id, entity_id
            )
            results.append(
                {
                    "degraded": result.degraded,
                    "degradation_reasons": result.degradation_reasons,
                    "sync_log_id": result.sync_log.id if result.sync_log else None,
                }
            )
        return {"results": results}

    if request.entity_type == "lead_score":
        if not request.entity_ids:
            raise HTTPException(status_code=400, detail="entity_ids required")
        results = []
        for entity_id in request.entity_ids:
            result = await service.sync_lead_score(
                auth, workspace_id, connection_id, entity_id
            )
            results.append(
                {
                    "degraded": result.degraded,
                    "degradation_reasons": result.degradation_reasons,
                    "sync_log_id": result.sync_log.id if result.sync_log else None,
                }
            )
        return {"results": results}

    raise HTTPException(status_code=400, detail="Unsupported sync direction/entity")


@router.get("/{workspace_id}/crm/connections/{connection_id}/sync-logs")
async def list_crm_sync_logs(
    workspace_id: int,
    connection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.CRM_READ.value)
    ),
):
    """List sync logs for a CRM connection."""
    from sqlalchemy import select

    result = await session.execute(
        select(CrmSyncLog)
        .where(
            CrmSyncLog.workspace_id == workspace_id,
            CrmSyncLog.connection_id == connection_id,
        )
        .order_by(CrmSyncLog.synced_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "workspace_id": log.workspace_id,
            "client_id": log.client_id,
            "connection_id": log.connection_id,
            "direction": log.direction,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "status": log.status,
            "error_message": log.error_message,
            "synced_at": log.synced_at,
        }
        for log in logs
    ]


@router.post("/{workspace_id}/crm/conversions", response_model=CrmConversionRead)
async def log_crm_conversion(
    workspace_id: int,
    request: CrmConversionLogInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Log a lead conversion event and attribute it (Story 27.5)."""
    service = CrmSyncService(session)
    outcome_event = await service.log_conversion(auth, workspace_id, request)
    return CrmConversionRead(
        id=outcome_event.id,
        workspace_id=outcome_event.workspace_id,
        client_id=outcome_event.client_id,
        lead_id=outcome_event.lead_id,
        event_type=outcome_event.event_type,
        attribution=outcome_event.attribution,
        cost_micros=outcome_event.cost_micros,
        outcome_metadata=outcome_event.outcome_metadata or {},
        created_at=outcome_event.created_at,
    )


@router.get("/{workspace_id}/crm/conversions", response_model=list[CrmConversionRead])
async def list_crm_conversions(
    workspace_id: int,
    lead_id: UUID | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """List logged conversions for attribution reporting (Story 27.5)."""
    service = CrmSyncService(session)
    events = await service.list_conversions(
        auth=auth,
        workspace_id=workspace_id,
        lead_id=lead_id,
        limit=limit,
    )
    return [
        CrmConversionRead(
            id=e.id,
            workspace_id=e.workspace_id,
            client_id=e.client_id,
            lead_id=e.lead_id,
            event_type=e.event_type,
            attribution=e.attribution,
            cost_micros=e.cost_micros,
            outcome_metadata=e.outcome_metadata or {},
            created_at=e.created_at,
        )
        for e in events
    ]



from fastapi import Header, Request


@router.post("/webhooks/hubspot", tags=["crm"])
async def hubspot_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    x_hubspot_signature_v3: str | None = Header(None),
):
    """Ingest HubSpot webhook events (e.g. deal stage changes) (Story 34.1)."""
    body = await request.body()
    from app.services.crm_webhook_service import (
        CrmWebhookService,
        verify_hubspot_signature,
    )

    if not verify_hubspot_signature(body, x_hubspot_signature_v3):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HubSpot signature",
        )

    try:
        events = json.loads(body.decode("utf-8"))
        if not isinstance(events, list):
            events = [events]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        ) from exc

    service = CrmWebhookService(session)
    results = await service.handle_hubspot_deal_change(events)
    await session.commit()
    return {"status": "ok", "processed": len(results), "results": results}


@router.post("/webhooks/salesforce", tags=["crm"])
async def salesforce_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    x_salesforce_webhook_secret: str | None = Header(None),
):
    """Ingest Salesforce outbound message / webhook event (Story 34.1).

    Authenticated via a shared secret header (X-Salesforce-Webhook-Secret)
    configured in Salesforce outbound message settings.
    """
    expected_secret = getattr(config, "SALESFORCE_WEBHOOK_SECRET", "")
    if expected_secret and x_salesforce_webhook_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Salesforce webhook secret",
        )
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        ) from exc

    from app.services.crm_webhook_service import CrmWebhookService

    service = CrmWebhookService(session)
    result = await service.handle_salesforce_deal_change(payload)
    await session.commit()
    return {"status": "ok", "result": result}


@router.get("/{workspace_id}/crm/activity-timeline", tags=["crm"])
async def get_workspace_activity_timeline(
    workspace_id: int,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value, "Permission denied")
    ),
):
    """Retrieve chronological CRM activity timeline for a workspace (Story 34.3)."""
    stmt = (
        select(CrmSyncLog)
        .where(CrmSyncLog.workspace_id == workspace_id)
        .order_by(CrmSyncLog.synced_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    items = [
        {
            "id": str(log.id),
            "workspace_id": log.workspace_id,
            "direction": log.direction,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id),
            "status": log.status,
            "error_message": log.error_message,
            "synced_at": log.synced_at.isoformat() if log.synced_at else None,
        }
        for log in logs
    ]

    return {
        "items": items,
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }
