"""CRM REST routes (Story 21.5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import CrmSyncLog, get_async_session
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
):
    """List sync logs for a CRM connection."""
    from sqlalchemy import select

    from app.db import Permission
    from app.utils.rbac import check_permission

    await check_permission(session, auth, workspace_id, Permission.CRM_READ)

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

