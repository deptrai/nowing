import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceMembership,
    get_async_session,
)
from app.dependencies.auth import RequirePermission
from app.schemas import (
    AutoExtractUsage,
    PlanDefinitionRead,
    SubscriptionChangeCreate,
    SubscriptionChangeRead,
    WorkspaceLimitsResponse,
    WorkspaceLimitUsage,
    WorkspaceSubscriptionResponse,
)
from app.services.memory.extract_budget import get_auto_extract_usage
from app.services.workspace_limits import workspace_limit_service
from app.users import get_auth_context

router = APIRouter()

# ----------------------------------------------------------------------
# Story 29.3: Workspace Subscriptions & Changes (FR-102, PM-1..PM-6)
# ----------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=WorkspaceSubscriptionResponse,
)
async def get_workspace_subscription(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view workspace subscription",
        )
    ),
):
    """Get current workspace subscription details, active pending/recent change,
    and available plan catalog definitions.

    Requires SETTINGS_VIEW permission.
    """
    try:
        workspace = await session.get(Workspace, workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        limits = await workspace_limit_service.get_effective_limits(
            session, workspace_id
        )
        usage = await workspace_limit_service.get_usage_snapshot(session, workspace_id)
        auto_extract_usage = await get_auto_extract_usage(session, workspace_id)

        limits_resp = WorkspaceLimitsResponse(
            plan_tier=limits.plan_tier,
            max_documents=limits.max_documents,
            max_members=limits.max_members,
            max_runs=limits.max_runs,
            max_storage_bytes=limits.max_storage_bytes,
            max_memory_count=limits.max_memory_count,
            max_memory_bytes=limits.max_memory_bytes,
            run_period_hours=limits.run_period_hours,
            auto_extract_item_cap=limits.auto_extract_item_cap,
            auto_extract_spend_cap_micros=limits.auto_extract_spend_cap_micros,
            auto_extract_wallet_pre_check=limits.auto_extract_wallet_pre_check,
            news_entity_extraction_item_cap=limits.news_entity_extraction_item_cap,
            news_entity_extraction_spend_cap_micros=limits.news_entity_extraction_spend_cap_micros,
            news_entity_extraction_wallet_pre_check=limits.news_entity_extraction_wallet_pre_check,
            max_monthly_credits=limits.max_monthly_credits,
            max_sources=limits.max_sources,
            support_level=limits.support_level,
            price_micros=limits.price_micros,
            currency=limits.currency,
            auto_extract_usage=AutoExtractUsage(**auto_extract_usage),
            usage=WorkspaceLimitUsage(**usage),
        )

        changes = await workspace_limit_service.get_subscription_changes(
            session, workspace_id
        )
        active_change = None
        for c in changes:
            if c.status in ("pending", "active"):
                active_change = SubscriptionChangeRead.model_validate(c)
                break

        plans = await workspace_limit_service.get_plan_catalog(session)
        available_plans = [PlanDefinitionRead.model_validate(p) for p in plans]

        return WorkspaceSubscriptionResponse(
            current_plan=workspace.plan_tier or "free",
            limits=limits_resp,
            active_change=active_change,
            available_plans=available_plans,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspace subscription: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes",
    response_model=SubscriptionChangeRead,
)
async def create_workspace_subscription_change(
    workspace_id: int,
    body: SubscriptionChangeCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to change workspace subscription",
        )
    ),
):
    """Request a subscription plan change (upgrade/downgrade).

    Requires SETTINGS_UPDATE permission.
    Returns 409 if resource usage exceeds target plan limits.
    """
    try:
        change = await workspace_limit_service.create_subscription_change(
            session=session,
            workspace_id=workspace_id,
            to_plan=body.to_plan,
            immediate=body.immediate,
            user_id=auth.user_id,
            payment_method_id=body.payment_method_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to change subscription: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/subscription-changes",
    response_model=list[SubscriptionChangeRead],
)
async def list_workspace_subscription_changes(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view workspace subscription changes",
        )
    ),
):
    """List audit history of subscription changes for a workspace.

    Requires SETTINGS_VIEW permission.
    """
    try:
        changes = await workspace_limit_service.get_subscription_changes(
            session=session,
            workspace_id=workspace_id,
        )
        return [SubscriptionChangeRead.model_validate(c) for c in changes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list subscription changes: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes/{change_id}/revert",
    response_model=SubscriptionChangeRead,
)
async def revert_workspace_subscription_change(
    workspace_id: int,
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to revert workspace subscription",
        )
    ),
):
    """Revert a subscription plan change within the 7-day reversible window.

    Requires SETTINGS_UPDATE permission.
    """
    try:
        change = await workspace_limit_service.revert_subscription_change(
            session=session,
            workspace_id=workspace_id,
            change_id=change_id,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to revert subscription change: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes/{change_id}/cancel",
    response_model=SubscriptionChangeRead,
)
async def cancel_workspace_subscription_change(
    workspace_id: int,
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to cancel workspace subscription change",
        )
    ),
):
    """Cancel a pending scheduled subscription plan change before it takes effect.

    Requires SETTINGS_UPDATE permission.
    """
    try:
        change = await workspace_limit_service.cancel_subscription_change(
            session=session,
            workspace_id=workspace_id,
            change_id=change_id,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel subscription change: {e!s}"
        ) from e
