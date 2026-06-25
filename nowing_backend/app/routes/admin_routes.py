"""Admin routes — superuser-only operations."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    GiftCode,
    GiftRequest,
    GiftRequestStatus,
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
from app.routes.stripe_routes import _mint_gift_code
from app.schemas.stripe import (
    GiftRequestApproveResponse,
    GiftRequestItem,
    GiftRequestListResponse,
    GiftRequestRejectRequest,
)
from app.users import current_superuser

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SubscriptionRequestItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    plan_id: str
    status: str
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# List pending subscription requests
# ---------------------------------------------------------------------------


@router.get(
    "/subscription-requests",
    response_model=list[SubscriptionRequestItem],
)
async def list_subscription_requests(
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> list[SubscriptionRequestItem]:
    """Return all pending subscription requests."""
    result = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.status == SubscriptionRequestStatus.PENDING)
        .order_by(SubscriptionRequest.created_at.asc())
    )
    requests = result.scalars().all()

    # Collect user IDs and batch-load to avoid N+1
    user_ids = [req.user_id for req in requests]
    email_map: dict[uuid.UUID, str] = {}
    if user_ids:
        user_rows = await db_session.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_rows.scalars():
            email_map[u.id] = u.email

    items: list[SubscriptionRequestItem] = [
        SubscriptionRequestItem(
            id=req.id,
            user_id=req.user_id,
            user_email=email_map.get(req.user_id, "<deleted>"),
            plan_id=req.plan_id,
            status=req.status.value,
            created_at=req.created_at,
            approved_at=req.approved_at,
            approved_by=req.approved_by,
        )
        for req in requests
    ]
    return items


# ---------------------------------------------------------------------------
# Approve a subscription request
# ---------------------------------------------------------------------------


@router.post(
    "/subscription-requests/{request_id}/approve",
    response_model=SubscriptionRequestItem,
)
async def approve_subscription_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> SubscriptionRequestItem:
    """Approve a pending subscription request and activate the user's subscription."""
    result = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.id == request_id)
        .with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription request not found.",
        )
    if req.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    user_result = await db_session.execute(
        select(User).where(User.id == req.user_id).with_for_update()
    )
    req_user = user_result.scalar_one_or_none()
    if req_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    # Activate subscription
    plan_limits = config.PLAN_LIMITS.get(req.plan_id, config.PLAN_LIMITS["free"])
    req_user.subscription_status = SubscriptionStatus.ACTIVE
    req_user.plan_id = req.plan_id
    req_user.monthly_token_limit = plan_limits["monthly_token_limit"]
    req_user.pages_limit = max(req_user.pages_used or 0, plan_limits["pages_limit"])
    req_user.tokens_used_this_month = 0
    req_user.token_reset_date = datetime.now(UTC).date()

    # Mark request approved
    now = datetime.now(UTC)
    req.status = SubscriptionRequestStatus.APPROVED
    req.approved_at = now
    req.approved_by = admin.id

    await db_session.commit()
    await db_session.refresh(req)

    user_result2 = await db_session.execute(select(User).where(User.id == req.user_id))
    req_user2 = user_result2.scalar_one_or_none()
    email = req_user2.email if req_user2 else "<deleted>"

    return SubscriptionRequestItem(
        id=req.id,
        user_id=req.user_id,
        user_email=email,
        plan_id=req.plan_id,
        status=req.status.value,
        created_at=req.created_at,
        approved_at=req.approved_at,
        approved_by=req.approved_by,
    )


# ---------------------------------------------------------------------------
# Reject a subscription request
# ---------------------------------------------------------------------------


@router.post(
    "/subscription-requests/{request_id}/reject",
    response_model=SubscriptionRequestItem,
)
async def reject_subscription_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> SubscriptionRequestItem:
    """Reject a pending subscription request."""
    result = await db_session.execute(
        select(SubscriptionRequest).where(SubscriptionRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription request not found.",
        )
    if req.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    req.status = SubscriptionRequestStatus.REJECTED

    await db_session.commit()
    await db_session.refresh(req)

    user_result = await db_session.execute(select(User).where(User.id == req.user_id))
    req_user = user_result.scalar_one_or_none()
    email = req_user.email if req_user else "<deleted>"

    return SubscriptionRequestItem(
        id=req.id,
        user_id=req.user_id,
        user_email=email,
        plan_id=req.plan_id,
        status=req.status.value,
        created_at=req.created_at,
        approved_at=req.approved_at,
        approved_by=req.approved_by,
    )


# ---------------------------------------------------------------------------
# Gift requests — list / approve / reject (Story 6.8)
# ---------------------------------------------------------------------------


_GIFT_STATUS_FILTERS = {"pending", "approved", "rejected", "all"}


@router.get("/gift-requests", response_model=GiftRequestListResponse)
async def list_gift_requests(
    status_filter: str = Query("pending", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftRequestListResponse:
    """List gift requests for admin review, optionally filtered by status."""
    if status_filter not in _GIFT_STATUS_FILTERS:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(_GIFT_STATUS_FILTERS)}",
        )
    query = select(GiftRequest, User.email).join(User, User.id == GiftRequest.user_id)
    if status_filter != "all":
        query = query.where(GiftRequest.status == GiftRequestStatus(status_filter))
    query = query.order_by(GiftRequest.created_at.desc()).limit(limit).offset(offset)

    rows = (await db_session.execute(query)).all()

    code_ids = [row.GiftRequest.gift_code_id for row in rows if row.GiftRequest.gift_code_id]
    code_map: dict[uuid.UUID, str] = {}
    if code_ids:
        code_rows = await db_session.execute(
            select(GiftCode.id, GiftCode.code).where(GiftCode.id.in_(code_ids))
        )
        code_map = {row.id: row.code for row in code_rows}

    items = [
        GiftRequestItem(
            id=row.GiftRequest.id,
            user_id=row.GiftRequest.user_id,
            user_email=row.email,
            plan_id=row.GiftRequest.plan_id,
            duration_months=row.GiftRequest.duration_months,
            status=row.GiftRequest.status.value,
            gift_code_id=row.GiftRequest.gift_code_id,
            gift_code=(
                code_map.get(row.GiftRequest.gift_code_id)
                if row.GiftRequest.gift_code_id
                else None
            ),
            created_at=row.GiftRequest.created_at,
            updated_at=row.GiftRequest.updated_at,
        )
        for row in rows
    ]
    return GiftRequestListResponse(items=items, count=len(items))


@router.post(
    "/gift-requests/{request_id}/approve",
    response_model=GiftRequestApproveResponse,
)
async def approve_gift_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftRequestApproveResponse:
    """Approve a pending gift request: mint a GiftCode and link it to the request."""
    result = await db_session.execute(
        select(GiftRequest).where(GiftRequest.id == request_id).with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift request not found.",
        )
    if req.status != GiftRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    plan_pricing = config.GIFT_PRICING.get(req.plan_id)
    if not plan_pricing or req.duration_months not in plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid plan_id/duration in request: {req.plan_id}/{req.duration_months}. "
                f"Valid plans: {list(config.GIFT_PRICING)}"
            ),
        )
    amount_paid = plan_pricing[req.duration_months]

    gift = await _mint_gift_code(
        db_session,
        plan_id=req.plan_id,
        duration_months=req.duration_months,
        amount_paid=amount_paid,
        purchaser_id=req.user_id,
        stripe_payment_intent_id=None,
    )

    req.status = GiftRequestStatus.APPROVED
    req.gift_code_id = gift.id
    req.updated_at = datetime.now(UTC)

    await db_session.commit()
    await db_session.refresh(gift)

    logger.info(
        "Admin %s approved gift request %s → code %s (plan=%s, months=%d)",
        admin.id, req.id, gift.code, gift.plan_id, gift.duration_months,
    )

    return GiftRequestApproveResponse(
        request_id=req.id,
        gift_code_id=gift.id,
        gift_code=gift.code,
        plan_id=gift.plan_id,
        duration_months=gift.duration_months,
    )


@router.post(
    "/gift-requests/{request_id}/reject",
    response_model=GiftRequestItem,
)
async def reject_gift_request(
    request_id: uuid.UUID,
    body: GiftRequestRejectRequest | None = None,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftRequestItem:
    """Reject a pending gift request (no gift code minted)."""
    result = await db_session.execute(
        select(GiftRequest).where(GiftRequest.id == request_id).with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift request not found.",
        )
    if req.status != GiftRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    req.status = GiftRequestStatus.REJECTED
    req.updated_at = datetime.now(UTC)

    await db_session.commit()
    await db_session.refresh(req)

    logger.info(
        "Admin %s rejected gift request %s (reason: %s)",
        admin.id, req.id, body.reason if body else None,
    )

    user_result = await db_session.execute(select(User).where(User.id == req.user_id))
    req_user = user_result.scalar_one_or_none()
    email = req_user.email if req_user else "<deleted>"

    return GiftRequestItem(
        id=req.id,
        user_id=req.user_id,
        user_email=email,
        plan_id=req.plan_id,
        duration_months=req.duration_months,
        status=req.status.value,
        gift_code_id=req.gift_code_id,
        gift_code=None,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )
