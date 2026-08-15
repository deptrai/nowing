"""REST API routes for Outcome-Based Pricing & Outcome Event Tracking (Story 21.7 / AD-42 / AD-48)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, get_async_session
from app.schemas.outcome_pricing import (
    OutcomeEventCreate,
    OutcomeEventRead,
    PricingPlanRead,
    PricingPlanUpdate,
)
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.outcome_pricing_service import OutcomePricingService
from app.users import get_auth_context
from app.utils.rbac import check_permission, check_workspace_access

router = APIRouter(tags=["outcome-pricing"])


@router.get(
    "/workspaces/{workspace_id}/pricing-plan",
    response_model=PricingPlanRead,
)
async def get_workspace_pricing_plan(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PricingPlanRead:
    """Retrieve active pricing plan and outcome rate card for workspace."""
    await check_workspace_access(session, auth, workspace_id)
    service = OutcomePricingService(session)
    plan = await service.get_or_create_workspace_plan(workspace_id)
    return PricingPlanRead.model_validate(plan)


@router.put(
    "/workspaces/{workspace_id}/pricing-plan",
    response_model=PricingPlanRead,
)
async def update_workspace_pricing_plan(
    workspace_id: int,
    payload: PricingPlanUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PricingPlanRead:
    """Update workspace pricing plan configuration (Admin/Owner only)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        error_message="Only workspace admins or owners can modify pricing plans.",
    )
    service = OutcomePricingService(session)
    plan = await service.update_workspace_plan(workspace_id, payload)
    return PricingPlanRead.model_validate(plan)


@router.post(
    "/workspaces/{workspace_id}/outcomes/meeting-booked",
    response_model=OutcomeEventRead,
)
async def record_meeting_booked(
    workspace_id: int,
    payload: OutcomeEventCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> OutcomeEventRead:
    """Record a qualified meeting booked outcome, debit wallet, and write BillingEvent."""
    await check_workspace_access(session, auth, workspace_id)
    if not auth.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "USER_REQUIRED",
                "message": "User wallet context required for billable outcomes.",
            },
        )

    service = OutcomePricingService(session)

    try:
        outcome = await service.record_meeting_booked(
            workspace_id=workspace_id,
            lead_id=payload.lead_id,
            user_id=auth.user.id,
            attribution=payload.attribution,
            metadata=payload.metadata,
            client_id=str(auth.client_id) if auth.client_id else None,
        )
        return OutcomeEventRead.model_validate(outcome)
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": str(e)
                or "Wallet balance is insufficient for outcome meeting recording.",
            },
        ) from e
