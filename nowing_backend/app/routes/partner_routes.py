"""API routes for the Affiliate Partner program (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.partner import (
    PartnerApplyRequest,
    PartnerCommissionsListResponse,
    PartnerPayoutItem,
    PartnerPayoutRequest,
    PartnerPayoutSettingsUpdate,
    PartnerPayoutsListResponse,
    PartnerProfileResponse,
    PartnerReferralsListResponse,
    VietQrBankItem,
)
from app.services.partner_service import PartnerService
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("/supported-banks", response_model=list[VietQrBankItem])
async def get_supported_banks() -> list[VietQrBankItem]:
    """Return the list of Napas 24/7 banks supported for VietQR payout."""
    return PartnerService.get_supported_banks()


@router.post("/apply", response_model=PartnerProfileResponse)
async def apply_partner(
    request: PartnerApplyRequest,
    auth: Annotated[AuthContext, Depends(require_session_context)],
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerProfileResponse:
    """Register the current authenticated user as an affiliate partner."""
    partner = await PartnerService.apply_partner(
        db_session=db_session,
        user_id=auth.user.id,
        request=request,
    )
    return await PartnerService.get_partner_profile(
        db_session=db_session, user_id=partner.user_id
    )


@router.get("/me", response_model=PartnerProfileResponse)
async def get_partner_profile(
    auth: Annotated[AuthContext, Depends(require_session_context)],
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerProfileResponse:
    """Get current partner profile, referral URL, and aggregated metrics."""
    return await PartnerService.get_partner_profile(
        db_session=db_session, user_id=auth.user.id
    )


@router.put("/payout-settings", response_model=PartnerProfileResponse)
async def update_payout_settings(
    update_data: PartnerPayoutSettingsUpdate,
    auth: Annotated[AuthContext, Depends(require_session_context)],
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerProfileResponse:
    """Update bank account / payout method."""
    return await PartnerService.update_payout_settings(
        db_session=db_session,
        user_id=auth.user.id,
        update_data=update_data,
    )


@router.get("/referrals", response_model=PartnerReferralsListResponse)
async def list_referrals(
    auth: Annotated[AuthContext, Depends(require_session_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerReferralsListResponse:
    """List referred customers and aggregate metrics."""
    return await PartnerService.list_referrals(
        db_session=db_session,
        user_id=auth.user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/commissions", response_model=PartnerCommissionsListResponse)
async def list_commissions(
    auth: Annotated[AuthContext, Depends(require_session_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerCommissionsListResponse:
    """List 15% lifetime recurring commission ledger entries."""
    return await PartnerService.list_commissions(
        db_session=db_session,
        user_id=auth.user.id,
        limit=limit,
        offset=offset,
    )


@router.post("/payouts/request", response_model=PartnerPayoutItem)
async def request_payout(
    request: PartnerPayoutRequest,
    auth: Annotated[AuthContext, Depends(require_session_context)],
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerPayoutItem:
    """Request a commission payout via VietQR or platform credit conversion."""
    return await PartnerService.request_payout(
        db_session=db_session,
        user_id=auth.user.id,
        request=request,
    )


@router.get("/payouts", response_model=PartnerPayoutsListResponse)
async def list_payouts(
    auth: Annotated[AuthContext, Depends(require_session_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db_session: AsyncSession = Depends(get_async_session),
) -> PartnerPayoutsListResponse:
    """List payout withdrawal history and statuses."""
    return await PartnerService.list_payouts(
        db_session=db_session,
        user_id=auth.user.id,
        limit=limit,
        offset=offset,
    )
