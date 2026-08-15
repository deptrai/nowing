"""REST API routes for Promo Codes & Gift Vouchers (Story 21.7 / AC-5 / AC-7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.promo_code import (
    PromoCodeAdminRead,
    PromoCodeClaimRequest,
    PromoCodeClaimResponse,
    PromoCodeCreateRequest,
)
from app.services.promo_code_service import (
    PromoCodeAlreadyExistsError,
    PromoCodeAlreadyRedeemedError,
    PromoCodeExhaustedError,
    PromoCodeExpiredError,
    PromoCodeNotFoundError,
    PromoCodeService,
)
from app.users import get_auth_context, require_session_context, require_superuser

router = APIRouter(tags=["promo-codes"])


@router.post(
    "/credits/promo-code/claim",
    response_model=PromoCodeClaimResponse,
)
async def claim_promo_code(
    payload: PromoCodeClaimRequest,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> PromoCodeClaimResponse:
    """Claim a promotional or gift voucher code to receive credit in wallet."""
    if not auth.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to claim promo codes.",
        )

    service = PromoCodeService(session)

    try:
        return await service.claim_promo_code(user=auth.user, code_input=payload.code)
    except PromoCodeNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROMO_CODE_NOT_FOUND", "message": str(e)},
        ) from e
    except PromoCodeExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PROMO_CODE_EXPIRED", "message": str(e)},
        ) from e
    except PromoCodeExhaustedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PROMO_CODE_EXHAUSTED", "message": str(e)},
        ) from e
    except PromoCodeAlreadyRedeemedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PROMO_CODE_ALREADY_USED", "message": str(e)},
        ) from e


@router.post(
    "/admin/promo-codes",
    response_model=PromoCodeAdminRead,
    dependencies=[Depends(require_superuser)],
)
async def create_promo_code_admin(
    payload: PromoCodeCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PromoCodeAdminRead:
    """Create a new promotional code campaign (SuperAdmin only)."""
    user_id = auth.user.id if auth.user else None
    service = PromoCodeService(session)
    try:
        promo = await service.create_promo_code(payload, created_by_user_id=user_id)
        return PromoCodeAdminRead.model_validate(promo)
    except PromoCodeAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PROMO_CODE_EXISTS", "message": str(e)},
        ) from e
