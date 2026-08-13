"""REST routes for saved searches / alert rules."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.tick import alert_engine_tick
from app.alerts.persistence.models.alert_rule import AlertRule
from app.alerts.schemas import (
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
    AlertSubscriptionCreate,
    AlertSubscriptionRead,
)
from app.alerts.services import (
    create_alert_rule,
    create_alert_subscription,
    delete_alert_rule,
    get_alert_rule,
    list_alert_rules,
    list_snapshots,
    update_alert_rule,
)
from app.auth.context import AuthContext
from app.db import Permission, WorkspaceMembership, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter(
    tags=["alert-rules"], prefix="/workspaces/{workspace_id}/alert-rules"
)


async def _load_rule(
    session: AsyncSession,
    workspace_id: int,
    alert_rule_id: UUID,
) -> AlertRule:
    rule = await get_alert_rule(
        session=session,
        alert_rule_id=alert_rule_id,
        workspace_id=workspace_id,
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="alert rule not found"
        )
    return rule


@router.get("", response_model=list[AlertRuleRead])
async def list_alert_rules_route(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_READ.value,
        "You don't have permission to read alert rules in this workspace",
    )
    return await list_alert_rules(session=session, workspace_id=workspace_id)


@router.post("", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alert_rule_route(
    workspace_id: int,
    data: AlertRuleCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_CREATE.value,
        "You don't have permission to create alert rules in this workspace",
    )
    return await create_alert_rule(
        session=session,
        workspace_id=workspace_id,
        client_id=None,
        user_id=auth.user.id,
        data=data,
    )


@router.get("/{alert_rule_id}", response_model=AlertRuleRead)
async def get_alert_rule_route(
    workspace_id: int,
    alert_rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_READ.value,
        "You don't have permission to read alert rules in this workspace",
    )
    return await _load_rule(session, workspace_id, alert_rule_id)


@router.put("/{alert_rule_id}", response_model=AlertRuleRead)
async def update_alert_rule_route(
    workspace_id: int,
    alert_rule_id: UUID,
    data: AlertRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_UPDATE.value,
        "You don't have permission to update alert rules in this workspace",
    )
    rule = await _load_rule(session, workspace_id, alert_rule_id)
    return await update_alert_rule(session=session, rule=rule, data=data)


@router.delete("/{alert_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule_route(
    workspace_id: int,
    alert_rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_DELETE.value,
        "You don't have permission to delete alert rules in this workspace",
    )
    rule = await _load_rule(session, workspace_id, alert_rule_id)
    await delete_alert_rule(session=session, rule=rule)


@router.post("/{alert_rule_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_alert_rule_route(
    workspace_id: int,
    alert_rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Manually trigger an alert rule (async Celery task)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_EXECUTE.value,
        "You don't have permission to execute alert rules in this workspace",
    )
    rule = await _load_rule(session, workspace_id, alert_rule_id)
    alert_engine_tick.apply_async()  # Simpler: full tick; could optimize to single rule.
    return {"status": "queued", "alert_rule_id": str(rule.id)}


@router.post(
    "/{alert_rule_id}/subscriptions",
    response_model=AlertSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription_route(
    workspace_id: int,
    alert_rule_id: UUID,
    data: AlertSubscriptionCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_UPDATE.value,
        "You don't have permission to update alert rules in this workspace",
    )
    rule = await _load_rule(session, workspace_id, alert_rule_id)

    # Only workspace members can be subscribed to alerts.
    membership = await session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == data.user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user is not a member of this workspace",
        )

    return await create_alert_subscription(
        session=session,
        workspace_id=rule.workspace_id,
        alert_rule_id=alert_rule_id,
        data=data,
    )


@router.get("/{alert_rule_id}/snapshots")
async def list_snapshots_route(
    workspace_id: int,
    alert_rule_id: UUID,
    limit: int = 20,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_READ.value,
        "You don't have permission to read alert rules in this workspace",
    )
    await _load_rule(session, workspace_id, alert_rule_id)
    return await list_snapshots(
        session=session,
        alert_rule_id=alert_rule_id,
        limit=limit,
    )
