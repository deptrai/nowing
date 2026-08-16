"""Admin routes for manual workspace credit adjustments and ledger."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import CreditTransaction, Workspace, get_async_session
from app.services.manual_credit_service import (
    CREDIT_TO_MICROS,
    ManualCreditAdjustmentService,
    ManualCreditQuotaExceededError,
    ManualCreditValidationError,
)
from app.users import require_superuser

router = APIRouter(prefix="/admin/credits", tags=["admin"])


class ManualCreditAdjustRequest(BaseModel):
    workspace_id: int = Field(..., gt=0)
    amount_credits: int = Field(..., gt=0)
    direction: str = Field(..., pattern="^(CREDIT|DEBIT)$")
    reason: str = Field(..., min_length=10)
    ticket_ref: str = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class ManualCreditAdjustResponse(BaseModel):
    transaction_id: int
    workspace_id: int
    actor_admin_id: str
    direction: str
    amount_credits: int
    amount_micros: int
    reason: str
    ticket_ref: str
    idempotency_key: str
    new_balance_credits: int
    created_at: str | None


class ManualCreditLedgerEntry(BaseModel):
    transaction_id: int
    workspace_id: int
    actor_admin_id: str
    direction: str
    amount_credits: int
    amount_micros: int
    reason: str
    ticket_ref: str
    created_at: str


@router.post(
    "/adjust",
    response_model=ManualCreditAdjustResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_manual_credit_adjust(
    payload: ManualCreditAdjustRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Apply a manual credit or debit adjustment to a workspace wallet."""
    stripped_key = idempotency_key.strip() if idempotency_key else ""
    if not stripped_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    if len(stripped_key) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header must be 64 characters or less",
        )

    service = ManualCreditAdjustmentService(session)
    try:
        result = await service.adjust_credits(
            workspace_id=payload.workspace_id,
            amount_credits=payload.amount_credits,
            direction=payload.direction,
            reason=payload.reason,
            ticket_ref=payload.ticket_ref,
            actor_admin_id=auth.user.id,
            idempotency_key=stripped_key,
        )
    except ManualCreditValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ManualCreditQuotaExceededError:
        # The quota failure is audited. Commit the AuditEvent before returning 403.
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily manual adjustment quota exceeded. Manager approval required.",
        ) from None

    await session.commit()

    workspace = await session.get(Workspace, payload.workspace_id)
    if workspace is not None:
        new_balance_credits = workspace.credit_micros_balance // CREDIT_TO_MICROS
    else:
        new_balance_credits = 0

    return {
        **result,
        "new_balance_credits": new_balance_credits,
    }


@router.get("/ledger", response_model=list[ManualCreditLedgerEntry])
async def get_manual_credit_ledger(
    workspace_id: int | None = None,
    admin_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reason: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> list[dict[str, Any]]:
    """Return the immutable manual credit adjustment ledger."""
    stmt = select(CreditTransaction).order_by(CreditTransaction.created_at.desc())

    if workspace_id is not None:
        stmt = stmt.where(CreditTransaction.workspace_id == workspace_id)
    if admin_id is not None:
        stmt = stmt.where(CreditTransaction.actor_admin_id == admin_id)
    if reason is not None and reason.strip():
        # Escape LIKE wildcards so a search string containing % or _ matches literally.
        escaped = (
            reason.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        stmt = stmt.where(CreditTransaction.reason.ilike(f"%{escaped}%", escape="\\"))
    if date_from is not None:
        start = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
        stmt = stmt.where(CreditTransaction.created_at >= start)
    if date_to is not None:
        end = datetime.combine(date_to, datetime.max.time(), tzinfo=UTC)
        stmt = stmt.where(CreditTransaction.created_at <= end)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "transaction_id": row.id,
            "workspace_id": row.workspace_id,
            "actor_admin_id": str(row.actor_admin_id),
            "direction": row.direction,
            "amount_credits": row.amount_micros // CREDIT_TO_MICROS,
            "amount_micros": row.amount_micros,
            "reason": row.reason,
            "ticket_ref": row.ticket_ref,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
