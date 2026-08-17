"""REST routes for batch lead ingestion (Story 26.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, VerifiedContact, Workspace, get_async_session
from app.rate_limiter import limiter
from app.services.billing_event_service import BillingEventService
from app.services.lead_batch_service import LeadBatchService, LeadItemValidationError
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


class LeadItem(BaseModel):
    """One lead in a batch ingest payload."""

    source: str = "batch_ingest"
    source_url: str | None = None
    client_id: str | None = None
    company_name: str | None = None
    title: str | None = None
    domain: str | None = None
    industry: str | None = None
    company_size: str | None = None
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    tax_id: str | None = None
    fit_score: float = 0.0
    intent_score: float = 0.0
    composite_score: float | None = None
    status: str = "new"


class BatchLeadIngestRequest(BaseModel):
    """Batch lead ingestion request body."""

    task_id: str | None = None
    leads: list[LeadItem] = Field(..., min_length=1, max_length=100)

    @field_validator("leads")
    @classmethod
    def _reject_degenerate(cls, leads: list[LeadItem]) -> list[LeadItem]:
        for idx, lead in enumerate(leads):
            if not any([lead.phone, lead.email, lead.domain]):
                raise ValueError(
                    f"Lead at index {idx} is degenerate: phone, email and domain are all empty"
                )
        return leads


class BatchLeadIngestResponse(BaseModel):
    """Batch lead ingestion response body."""

    ingested_count: int
    skipped_blacklisted_count: int
    failed_count: int
    execution_time_ms: float
    lead_ids: list[UUID]


@router.post(
    "/workspaces/{workspace_id}/leads/batch-ingest",
    response_model=BatchLeadIngestResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
async def batch_ingest_leads(
    request: Request,
    workspace_id: int,
    body: BatchLeadIngestRequest = Body(...),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> BatchLeadIngestResponse:
    """Ingest a batch of leads with DNC filtering and PII encryption."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to create leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    service = LeadBatchService()
    try:
        result = await service.ingest_batch(
            session,
            workspace_id=workspace_id,
            leads=[item.model_dump() for item in body.leads],
        )
    except LeadItemValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return BatchLeadIngestResponse(**result)


class ContactUnlockResponse(BaseModel):
    """Contact unlock response."""

    contact_id: UUID
    is_unlocked: bool
    cost_micros: int


@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock",
    response_model=ContactUnlockResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("60/minute")
async def unlock_contact(
    request: Request,
    workspace_id: int,
    lead_id: UUID,
    contact_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ContactUnlockResponse:
    """Unlock a verified contact, bill 1500 micros, and record an audit log."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to unlock contacts in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    contact = (
        await session.execute(
            select(VerifiedContact).where(
                VerifiedContact.id == contact_id,
                VerifiedContact.workspace_id == workspace_id,
                VerifiedContact.lead_id == lead_id,
            )
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    if contact.is_unlocked:
        return ContactUnlockResponse(
            contact_id=contact.id,
            is_unlocked=True,
            cost_micros=0,
        )

    try:
        await BillingEventService().record_contact_unlock(
            session,
            verified_contact_id=contact.id,
            workspace_id=workspace_id,
            client_id=None,
            user_id=auth.user.id,
            cost_micros=1_500,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc),
        ) from exc

    contact.is_unlocked = True
    existing_logs = list(contact.pii_access_audit_logs or [])
    contact.pii_access_audit_logs = [
        *existing_logs,
        {
            "user_id": str(auth.user.id),
            "workspace_id": workspace_id,
            "lead_id": str(lead_id),
            "contact_id": str(contact_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "access_type": "unlock",
        },
    ]
    await session.flush()

    return ContactUnlockResponse(
        contact_id=contact.id,
        is_unlocked=True,
        cost_micros=1_500,
    )
