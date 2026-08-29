"""REST routes for batch lead ingestion (Story 26.1)."""

from __future__ import annotations

import ipaddress
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Lead, Permission, VerifiedContact, Workspace, get_async_session
from app.rate_limiter import limiter
from app.services import wallet_credit
from app.services.billing_event_service import BillingEventService
from app.services.contact_unlock_service import ContactUnlockService
from app.services.lead_batch_service import LeadBatchService, LeadItemValidationError
from app.services.pii.opt_out_service import OptOutService, OptOutValidationError
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

logger = logging.getLogger(__name__)


def _is_trusted_proxy(host: str) -> bool:
    """Return True when the immediate remote address is a private/trusted proxy."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        addr.is_loopback
        or addr.is_private
        or addr in ipaddress.ip_network("10.0.0.0/8")
        or addr in ipaddress.ip_network("172.16.0.0/12")
        or addr in ipaddress.ip_network("192.168.0.0/16")
        or addr in ipaddress.ip_network("100.64.0.0/10")
    )


def _get_client_ip(request: Request) -> str | None:
    """Return the real client IP behind trusted proxies / Cloudflare."""
    remote = request.client.host if request.client else None
    if remote and _is_trusted_proxy(remote):
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.split(",")[0].strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return remote


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
    lead_id_mapping: dict[str, UUID] = Field(default_factory=dict)


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

    await session.commit()
    return BatchLeadIngestResponse(**result)


class PIIOptOutRequest(BaseModel):
    """PII opt-out request body."""

    record_type: str = Field(..., pattern="^(phone|email)$")
    value: str = Field(..., min_length=1)
    reason: str | None = "Right to be forgotten"


class PIIOptOutResponse(BaseModel):
    """PII opt-out response."""

    purged_contact_count: int
    refunded_micros: int
    dnc_record_id: UUID


class ContactUnlockResponse(BaseModel):
    """Contact unlock response."""

    contact_id: UUID
    is_unlocked: bool
    cost_micros: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


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
            select(VerifiedContact)
            .where(
                VerifiedContact.id == contact_id,
                VerifiedContact.workspace_id == workspace_id,
                VerifiedContact.lead_id == lead_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    lead = await session.get(Lead, (lead_id, workspace_id))
    service = ContactUnlockService()
    result = await service.unlock_contact(
        session=session,
        workspace_id=workspace_id,
        contact=contact,
        user_id=auth.user.id,
        lead=lead,
        ip_address=_get_client_ip(request),
        reason="contact_unlock",
    )
    await session.commit()
    return ContactUnlockResponse(
        contact_id=result.contact_id,
        is_unlocked=result.is_unlocked,
        cost_micros=result.cost_micros,
        name=result.name,
        title=result.title,
        email=result.email,
        phone=result.phone,
    )


@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/relock",
    response_model=ContactUnlockResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("60/minute")
async def relock_contact(
    request: Request,
    workspace_id: int,
    lead_id: UUID,
    contact_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ContactUnlockResponse:
    """Accidentally re-lock a contact and refund the 1.5 credit unlock (Story 26.5)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to relock contacts in this workspace",
    )

    contact = (
        await session.execute(
            select(VerifiedContact)
            .where(
                VerifiedContact.id == contact_id,
                VerifiedContact.workspace_id == workspace_id,
                VerifiedContact.lead_id == lead_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # ponytail: set is_unlocked and audit log before the billing service call so
    # the single commit inside BillingEventService.record_contact_relock persists
    # everything atomically. If the refund fails, the contact stays unlocked.
    contact.is_unlocked = False
    existing_logs = list(contact.pii_access_audit_logs or [])
    contact.pii_access_audit_logs = [
        *existing_logs,
        {
            "user_id": str(auth.user.id),
            "workspace_id": workspace_id,
            "lead_id": str(lead_id),
            "contact_id": str(contact_id),
            "access_type": "relock",
            "timestamp": datetime.now(UTC).isoformat(),
            "ip_address": _get_client_ip(request),
            "reason": "accidental_unlock",
        },
    ]

    try:
        await BillingEventService().record_contact_relock(
            session,
            verified_contact_id=contact.id,
            workspace_id=workspace_id,
            user_id=auth.user.id,
            cost_micros=1_500,
        )
    except ValueError as exc:
        detail = str(exc)
        if "relock window expired" in detail:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Relock window expired",
            ) from exc
        if "relock budget exhausted" in detail:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không thể hoàn tác: đã hết hạn mức hoàn tiền tự động",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        ) from exc
    except Exception as exc:
        logger.exception("Failed to relock contact %s: %s", contact_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to relock contact.",
        ) from exc

    from app.services.pii.mask import mask_email, mask_name, mask_phone

    enc = VerifiedContactEncryption()

    def _decrypt_field(value: str | None) -> str | None:
        if not value:
            return None
        if enc.is_encrypted(value):
            try:
                return enc.decrypt(value)
            except Exception:
                return None
        return value

    await session.commit()
    return ContactUnlockResponse(
        contact_id=contact.id,
        is_unlocked=False,
        cost_micros=0,
        name=mask_name(_decrypt_field(contact.name)),
        title=mask_name(_decrypt_field(contact.title)),
        email=mask_email(_decrypt_field(contact.email)),
        phone=mask_phone(_decrypt_field(contact.phone)),
    )


@router.post(
    "/workspaces/{workspace_id}/pii-opt-out",
    response_model=PIIOptOutResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
async def pii_opt_out(
    request: Request,
    workspace_id: int,
    body: PIIOptOutRequest = Body(...),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> PIIOptOutResponse:
    """Process a PDPD Decree 13 opt-out request (Right to be Forgotten)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to opt-out PII in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    service = OptOutService(session)
    try:
        result = await service.process_opt_out(
            workspace_id=workspace_id,
            record_type=body.record_type,
            value=body.value,
            actor_user_id=auth.user.id,
            ip_address=_get_client_ip(request),
            global_scope=False,
            reason=body.reason,
        )
    except OptOutValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except wallet_credit.InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits to process opt-out.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Billing validation failed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process opt-out.",
        ) from exc

    await session.commit()

    return PIIOptOutResponse(
        purged_contact_count=result.purged_contact_count,
        refunded_micros=result.refunded_micros,
        dnc_record_id=result.dnc_record_id,
    )
