"""REST routes for contact enrichment (Story 21.3, Task 5)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    Permission,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.enrichment.schemas import (
    BulkEnrichmentInput,
    EnrichmentCostOutput,
    EnrichmentInput,
    EnrichmentOutput,
    EnrichmentRequestRead,
    VerifiedContactRead,
)
from app.lead_intelligence.enrichment.service import EnrichmentService
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

_DEGRADED_STATUS: dict[str, int] = {
    "lead_not_found": status.HTTP_404_NOT_FOUND,
    "workspace_not_found": status.HTTP_404_NOT_FOUND,
    "insufficient_wallet": status.HTTP_402_PAYMENT_REQUIRED,
}


def _client_id(auth: AuthContext) -> str | None:
    return auth.pat.client_id if auth.pat is not None else None


async def _require_lead_read(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> None:
    """Allow callers holding either LEADS_READ or CONTACTS_READ (Task 5.2)."""
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.LEADS_READ.value,
            error_message="You don't have permission to view leads in this workspace",
        )
    except HTTPException:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CONTACTS_READ.value,
            error_message=(
                "You don't have permission to view contacts in this workspace"
            ),
        )


@router.post(
    "/workspaces/{workspace_id}/leads/enrich",
    response_model=list[EnrichmentOutput],
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrich_leads_bulk(
    workspace_id: int,
    body: BulkEnrichmentInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[EnrichmentOutput]:
    """Enrich many leads at once (AC-8); one EnrichmentOutput per lead."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_ENRICH.value,
        error_message="You don't have permission to enrich leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    ctx = SimpleNamespace(
        session=session,
        workspace_id=workspace_id,
        run_id=None,
        client_id=_client_id(auth),
        user_id=auth.user.id,
    )
    service = EnrichmentService()
    outputs: list[EnrichmentOutput] = []
    for lead_id in body.lead_ids:
        output = await service.enrich(
            session, ctx, lead_id=lead_id, requested_count=body.requested_count
        )
        outputs.append(output)
    return outputs


@router.get(
    "/workspaces/{workspace_id}/leads/enrich/cost",
    response_model=EnrichmentCostOutput,
)
async def enrich_cost(
    workspace_id: int,
    lead_ids: list[UUID] = Query(default=[]),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> EnrichmentCostOutput:
    """Project the cost of enriching a set of leads (AC-8)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_ENRICH.value,
        error_message="You don't have permission to enrich leads in this workspace",
    )

    per_contact = int(config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT or 0)
    per_lead = per_contact * config.CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD
    return EnrichmentCostOutput(
        cost_per_contact_micros=per_contact,
        estimated_cost_micros=per_lead * len(lead_ids),
        lead_count=len(lead_ids),
    )


@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/enrich",
    response_model=EnrichmentOutput,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrich_lead(
    workspace_id: int,
    lead_id: UUID,
    body: EnrichmentInput | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> EnrichmentOutput:
    """Enrich one lead with verified contacts (AC-1, returns 202 Accepted)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_ENRICH.value,
        error_message="You don't have permission to enrich leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    ctx = SimpleNamespace(
        session=session,
        workspace_id=workspace_id,
        run_id=None,
        client_id=_client_id(auth),
        user_id=auth.user.id,
    )
    requested_count = body.requested_count if body is not None else 5
    service = EnrichmentService()
    output = await service.enrich(
        session, ctx, lead_id=lead_id, requested_count=requested_count
    )
    if output.degraded and output.degradation_reasons:
        http_code = _DEGRADED_STATUS.get(output.degradation_reasons[0])
        if http_code is not None:
            raise HTTPException(
                status_code=http_code,
                detail=output.degradation_reasons[0],
            )
    return output


@router.get(
    "/workspaces/{workspace_id}/leads/{lead_id}/contacts",
    response_model=list[VerifiedContactRead],
)
async def list_verified_contacts(
    workspace_id: int,
    lead_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[VerifiedContactRead]:
    """Return decrypted verified contacts for a lead (AC-6, newest first)."""
    await _require_lead_read(session, auth, workspace_id)

    service = EnrichmentService()
    contacts = await service.get_contacts(
        session,
        workspace_id=workspace_id,
        client_id=_client_id(auth),
        lead_id=lead_id,
        user_id=auth.user.id,
        limit=limit,
        offset=offset,
    )
    return [
        VerifiedContactRead.model_validate(c, from_attributes=True) for c in contacts
    ]


@router.get(
    "/workspaces/{workspace_id}/leads/{lead_id}/enrichments",
    response_model=list[EnrichmentRequestRead],
)
async def list_enrichment_requests(
    workspace_id: int,
    lead_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[EnrichmentRequestRead]:
    """List enrichment requests for one lead (newest first, AC-8)."""
    await _require_lead_read(session, auth, workspace_id)

    service = EnrichmentService()
    rows = await service.list_enrichment_requests(
        session,
        workspace_id=workspace_id,
        client_id=_client_id(auth),
        lead_id=lead_id,
        limit=limit,
        offset=offset,
    )
    return [
        EnrichmentRequestRead.model_validate(row, from_attributes=True)
        for row in rows
    ]
