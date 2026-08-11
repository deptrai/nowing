"""Internal chainlens-research callback routes.

These endpoints are called by the chainlens-research engine, not by the
Nowing web client. Authentication is service-to-service via a shared
``Authorization: Bearer <CHAINLENS_SERVICE_TOKEN>`` header plus
``X-Workspace-Id`` for workspace scoping.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.canonical.tenant_context import set_request_tenant_context
from app.db import Workspace, get_async_session
from app.observability import metrics as ot_metrics
from app.rate_limiter import limiter
from app.services.chainlens.auth import (
    ChainLensAuthContext,
    get_chainlens_auth,
)
from app.services.chainlens.private_provider import PrivateProviderService
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
)
from app.utils.rbac import check_workspace_access

router = APIRouter()


def chainlens_auth_dependency(request: Request) -> ChainLensAuthContext:
    """FastAPI dependency that validates an inbound chainlens-research request."""
    return get_chainlens_auth().validate_inbound_token(request)


@router.post("/scraper/{scraper_id}/run")
@limiter.limit("100/minute")
async def run_scraper_for_chainlens(
    request: Request,
    scraper_id: str,
    context: ChainLensAuthContext = Depends(chainlens_auth_dependency),
) -> dict[str, Any]:
    """Trigger a Nowing scraper on behalf of chainlens-research."""
    return {
        "status": "accepted",
        "scraper_id": scraper_id,
        "workspace_id": context.workspace_id,
    }


@router.post("/private-data/search")
@limiter.limit("100/minute")
async def private_data_search_for_chainlens(
    request: Request,
    context: ChainLensAuthContext = Depends(chainlens_auth_dependency),
    body: PrivateDataSearchRequest = Body(...),
    session: AsyncSession = Depends(get_async_session),
) -> PrivateDataSearchResponse:
    """Search Nowing private data on behalf of chainlens-research.

    Validates the service token, checks workspace access, and delegates to
    ``PrivateProviderService``. The service sets the tenant context and persists
    a zero-cost ``TokenUsage`` row; the route commits the transaction before
    returning.
    """
    if body.workspaceId != context.workspace_id:
        ot_metrics.record_chainlens_auth_failed(
            workspace_id=context.workspace_id,
            reason="workspace_id_mismatch",
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    # Establish tenant context before querying workspace/membership rows.
    await set_request_tenant_context(
        session,
        workspace_id=context.workspace_id,
        client_id=None,
        user_id=None,
    )

    result = await session.execute(
        select(Workspace)
        .options(selectinload(Workspace.user))
        .where(Workspace.id == context.workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        ot_metrics.record_chainlens_auth_failed(
            workspace_id=context.workspace_id,
            reason="workspace_not_found",
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    if workspace.user is None:
        ot_metrics.record_chainlens_auth_failed(
            workspace_id=context.workspace_id,
            reason="workspace_owner_missing",
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    auth = AuthContext.system(user=workspace.user, source="chainlens")
    await check_workspace_access(session, auth, context.workspace_id)

    service = PrivateProviderService(session)
    response = await service.search(
        body,
        workspace,
        correlation_id=context.correlation_id,
    )

    ot_metrics.record_chainlens_private_search(
        workspace_id=context.workspace_id,
        result="ok" if response.chunks else "empty",
        hit_count=len(response.chunks),
    )

    await session.commit()

    return response
