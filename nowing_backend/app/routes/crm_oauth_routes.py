"""CRM OAuth callback route (Story 21.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.lead_intelligence.crm.service import CrmConnectionService

router = APIRouter()


@router.get("/auth/crm/{provider}/callback")
async def crm_oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """Handle CRM OAuth callback."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    service = CrmConnectionService(session)
    connection = await service.handle_callback(provider, code, state)
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
