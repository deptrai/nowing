"""Admin SaaS plan catalog routes (Story 29.3 / FR-102 / PM-1..PM-6)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas import (
    PlanDefinitionCreate,
    PlanDefinitionRead,
    PlanDefinitionUpdate,
)
from app.services.workspace_limits import workspace_limit_service
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/saas/plans", tags=["admin"])


@router.get("", response_model=list[PlanDefinitionRead])
async def list_saas_plans(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> list[PlanDefinitionRead]:
    """List all SaaS plans in the catalog."""
    plans = await workspace_limit_service.get_plan_catalog(session)
    return [PlanDefinitionRead.model_validate(p) for p in plans]


@router.get("/{plan_tier}", response_model=PlanDefinitionRead)
async def get_saas_plan(
    plan_tier: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PlanDefinitionRead:
    """Get details for a specific plan tier."""
    plan = await workspace_limit_service.get_plan_definition(session, plan_tier)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_tier}' not found",
        )
    return PlanDefinitionRead.model_validate(plan)


@router.post(
    "",
    response_model=PlanDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_saas_plan(
    payload: PlanDefinitionCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PlanDefinitionRead:
    """Create a new SaaS plan tier."""
    try:
        plan = await workspace_limit_service.create_plan_definition(
            session=session,
            data=payload,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(plan)
        return PlanDefinitionRead.model_validate(plan)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create plan: {e!s}",
        ) from e


@router.put("/{plan_tier}", response_model=PlanDefinitionRead)
async def update_saas_plan(
    plan_tier: str,
    payload: PlanDefinitionUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PlanDefinitionRead:
    """Update an existing SaaS plan tier defaults with grandfathered limit preservation."""
    try:
        plan = await workspace_limit_service.update_plan_definition(
            session=session,
            plan_tier=plan_tier,
            data=payload,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(plan)
        return PlanDefinitionRead.model_validate(plan)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan: {e!s}",
        ) from e


@router.delete("/{plan_tier}", response_model=dict[str, Any])
async def delete_saas_plan(
    plan_tier: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Delete a custom SaaS plan tier. System defaults cannot be deleted."""
    try:
        await workspace_limit_service.delete_plan_definition(
            session=session,
            plan_tier=plan_tier,
            user_id=auth.user_id,
        )
        await session.commit()
        return {"message": f"Plan '{plan_tier}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete plan: {e!s}",
        ) from e
