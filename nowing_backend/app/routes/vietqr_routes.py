"""VietQR / Napas 24/7 dynamic top-up checkout (Story 37.7 / AC-2).

- ``GET  /vietqr/pricing-tiers`` — hybrid packages for the packaging UI.
- ``POST /vietqr/topup-intents`` — create a 10-minute dynamic-transfer intent.
- ``GET  /vietqr/topup-intents/{id}`` — poll status from the checkout modal.
- ``POST /vietqr/webhook`` — Napas bank-transfer webhook; verifies the HMAC
  signature and credits the wallet in the same request (< 5s SLA).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, WorkspaceMembership, get_async_session
from app.dependencies.auth import RequirePermissionFromBody
from app.services import vietqr_topup_service
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vietqr", tags=["vietqr"])


class PricingTierRead(BaseModel):
    id: str
    name: str
    price_vnd: int
    credits: int
    credit_micros: int
    seats: int | None
    highlighted: bool


class PricingTiersResponse(BaseModel):
    tiers: list[PricingTierRead]
    vnd_per_usd: int  # drives the credit-calculator slider on the FE


class CreateTopupIntentRequest(BaseModel):
    workspace_id: int = Field(..., gt=0)
    tier_id: str | None = None
    amount_vnd: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


class TopupIntentResponse(BaseModel):
    intent_id: str
    status: str
    amount_vnd: int
    credit_micros: int
    credits: int
    transfer_memo: str
    bank_bin: str
    bank_name: str
    bank_account_number: str
    bank_account_name: str
    qr_url: str
    expires_at: str
    created_at: str | None


@router.get("/pricing-tiers", response_model=PricingTiersResponse)
async def get_pricing_tiers(
    _auth: AuthContext = Depends(require_session_context),
) -> PricingTiersResponse:
    """Return the 3 hybrid pricing packages (Starter / Professional / Business)."""
    return PricingTiersResponse(
        tiers=[PricingTierRead(**t) for t in vietqr_topup_service.pricing_tiers()],
        vnd_per_usd=config.VIETQR_VND_PER_USD,
    )


@router.post("/topup-intents", response_model=TopupIntentResponse)
async def create_topup_intent(
    body: CreateTopupIntentRequest,
    auth: AuthContext = Depends(require_session_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromBody(
            Permission.BILLING_READ.value,
            "You don't have permission to buy credits in this workspace",
        )
    ),
    session: AsyncSession = Depends(get_async_session),
) -> TopupIntentResponse:
    """Create a dynamic VietQR top-up intent (10-minute transfer window)."""
    if not config.VIETQR_TOPUP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VietQR top-up is temporarily unavailable.",
        )
    try:
        intent = await vietqr_topup_service.create_topup_intent(
            session,
            user_id=auth.user_id,
            tier_id=body.tier_id,
            amount_vnd=body.amount_vnd,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return TopupIntentResponse(**intent)


@router.get("/topup-intents/{intent_id}", response_model=TopupIntentResponse)
async def get_topup_intent(
    intent_id: UUID,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> TopupIntentResponse:
    """Poll a top-up intent's status from the checkout modal."""
    intent = await vietqr_topup_service.get_topup_intent(
        session, intent_id=intent_id, user_id=auth.user_id
    )
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Top-up intent not found"
        )
    return TopupIntentResponse(**intent)


@router.post("/webhook")
async def vietqr_transfer_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Napas bank-transfer webhook.

    HMAC-SHA256 signature over the raw body is required in the
    ``x-vietqr-signature`` (or ``x-signature``) header. Fulfilment is
    synchronous — the wallet is credited inside this request, within the
    5-second crediting SLA.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-vietqr-signature") or request.headers.get(
        "x-signature"
    )
    result = await vietqr_topup_service.process_transfer_webhook(
        session, raw_body=raw_body, signature=signature
    )
    if result["status"] == "invalid_signature":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    if result["status"] == "webhook_unconfigured":
        # 503 so the aggregator retries — a later delivery after ops fixes the
        # secret can still settle the intent.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook fulfilment is not configured",
        )
    return {k: str(v) for k, v in result.items()}
