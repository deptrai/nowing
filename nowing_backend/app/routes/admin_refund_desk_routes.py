"""Admin Desk routes for the manual refund-review queue (Story 37.7 / AD-110).

When the 15% monthly auto-refund circuit breaker trips for a workspace,
invalid-contact refund requests stop auto-processing and queue here:
``PhoneWaterfallLog.status == "refund_review"``. Platform admins list the
queue and approve (refund, bypassing the cap) or reject each entry.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import PhoneWaterfallLog, get_async_session
from app.services.billing_service import (
    REFUND_REJECTED_STATUS,
    REFUND_REVIEW_STATUS,
    BillingService,
)
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/refund-desk", tags=["admin"])


class RefundDeskEntry(BaseModel):
    log_id: str
    workspace_id: int
    lead_id: str
    contact_id: str | None
    phone_masked: str | None
    provider_used: str | None
    tier_reached: int | None
    cost_micros: int
    error_code: str | None
    created_at: str | None


class RefundDeskListResponse(BaseModel):
    entries: list[RefundDeskEntry]
    total: int


class ResolveRefundRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class ResolveRefundResponse(BaseModel):
    log_id: str
    lead_id: str
    refunded: bool
    status: str


@router.get("", response_model=RefundDeskListResponse)
async def list_refund_desk(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> RefundDeskListResponse:
    """List invalid-contact refunds queued for manual review."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(PhoneWaterfallLog)
            .where(PhoneWaterfallLog.status == REFUND_REVIEW_STATUS)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(PhoneWaterfallLog)
                .where(PhoneWaterfallLog.status == REFUND_REVIEW_STATUS)
                .order_by(desc(PhoneWaterfallLog.created_at))
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return RefundDeskListResponse(
        total=total,
        entries=[
            RefundDeskEntry(
                log_id=str(row.id),
                workspace_id=row.workspace_id,
                lead_id=str(row.lead_id),
                contact_id=str(row.contact_id) if row.contact_id else None,
                phone_masked=row.phone_masked,
                provider_used=row.provider_used,
                tier_reached=row.tier_reached,
                cost_micros=row.cost_micros or 0,
                error_code=row.refund_reason,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ],
    )


@router.post("/{log_id}/resolve", response_model=ResolveRefundResponse)
async def resolve_refund_desk_entry(
    log_id: UUID,
    body: ResolveRefundRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> ResolveRefundResponse:
    """Approve (execute the credit refund) or reject a queued refund request."""
    billing = BillingService(session)
    result = await billing.resolve_admin_desk_refund(
        log_id=log_id,
        approve=body.action == "approve",
        admin_user_id=auth.user_id,
        note=body.note,
    )
    status_value = (
        REFUND_REJECTED_STATUS if body.action == "reject" else result["status"]
    )
    return ResolveRefundResponse(
        log_id=str(log_id),
        lead_id=result["lead_id"],
        refunded=bool(result.get("refunded")),
        status=status_value,
    )
