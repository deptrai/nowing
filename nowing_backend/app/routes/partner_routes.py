"""API routes for the Affiliate Partner program (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
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
from app.services.partner_payout_service import PartnerPayoutService
from app.services.partner_service import PartnerService
from app.services.vietqr_payout_client import VietQRPayoutClient
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


@router.post("/payouts/webhook")
async def handle_payout_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
    x_webhook_signature: Annotated[
        str | None, Header(alias="x-webhook-signature")
    ] = None,
) -> dict[str, Any]:
    """Bank & VietQR Webhook Callback endpoint for payout settlement & reconciliation (Story 23.3)."""
    raw_body = await request.body()
    secret = (
        getattr(config, "VIETQR_WEBHOOK_SECRET", None)
        or getattr(config, "NAPAS_WEBHOOK_SECRET", None)
        or ""
    )

    if not secret:
        logger.error("Payout webhook secret is not configured in server environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification is unconfigured on server",
        )

    if not x_webhook_signature or not VietQRPayoutClient.verify_webhook_signature(
        raw_body, x_webhook_signature, secret
    ):
        logger.warning(
            "Invalid or missing webhook signature received for payout callback"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = await request.json()
    except Exception as e:
        logger.error("Failed to parse JSON payload in payout webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from e

    receipt = await PartnerPayoutService.handle_webhook_confirmation(
        session=db_session,
        payload=payload,
    )
    await db_session.commit()

    return {
        "status": "success",
        "payout_id": str(receipt.payout_id),
        "payout_status": receipt.status,
        "napas_ref": receipt.napas_transaction_number,
        "hmac_audit_hash": receipt.hmac_audit_hash,
    }
