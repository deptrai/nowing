"""Integration tests for saved search / alert rule lifecycle."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.schemas import AlertRuleCreate, AlertRuleUpdate, AlertSubscriptionCreate
from app.alerts.services import (
    create_alert_rule,
    create_alert_subscription,
    get_alert_rule,
    list_alert_rules,
)
from app.db import User, Workspace

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_alert_rule(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """AC-1: a saved search persists with schedule, timezone, and enabled flag."""
    rule = await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="daily",
            timezone="UTC",
            notification_channels=["in_app"],
        ),
    )

    assert rule.id is not None
    assert rule.workspace_id == db_workspace.id
    assert rule.name == "Python jobs"
    assert rule.schedule == "daily"
    assert rule.timezone == "UTC"
    assert rule.cron == "0 0 * * *"
    assert rule.next_fire_at is not None
    assert rule.enabled is True


async def test_list_alert_rules(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="none",
            timezone="UTC",
            notification_channels=["in_app"],
        ),
    )

    rules = await list_alert_rules(session=db_session, workspace_id=db_workspace.id)
    assert len(rules) == 1
    assert rules[0].name == "Python jobs"


async def test_get_alert_rule(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    rule = await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="none",
            timezone="UTC",
        ),
    )

    loaded = await get_alert_rule(
        session=db_session,
        alert_rule_id=rule.id,
        workspace_id=db_workspace.id,
    )
    assert loaded is not None
    assert loaded.id == rule.id


async def test_create_alert_subscription(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    from app.db import WorkspaceMembership

    # Create a second workspace member to subscribe.
    other_user = User(
        id=__import__("uuid").uuid4(),
        email="alert-subscriber@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    db_session.add(
        WorkspaceMembership(
            workspace_id=db_workspace.id,
            user_id=other_user.id,
        )
    )
    await db_session.flush()

    # Avoid the creator auto-subscription by disabling channels on create.
    rule = await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="none",
            timezone="UTC",
            notification_channels=[],
        ),
    )

    sub = await create_alert_subscription(
        session=db_session,
        workspace_id=db_workspace.id,
        alert_rule_id=rule.id,
        data=AlertSubscriptionCreate(
            user_id=other_user.id,
            channels=["in_app", "telegram"],
            enabled=True,
        ),
    )

    assert sub.id is not None
    assert sub.workspace_id == db_workspace.id
    assert sub.alert_rule_id == rule.id
    assert sub.user_id == other_user.id
    assert sub.channels == ["in_app", "telegram"]


async def test_update_alert_rule_schedule_and_timezone(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    rule = await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="none",
            timezone="UTC",
        ),
    )

    from app.alerts.services import update_alert_rule

    updated = await update_alert_rule(
        session=db_session,
        rule=rule,
        data=AlertRuleUpdate(
            schedule="daily",
            timezone="Asia/Ho_Chi_Minh",
        ),
    )

    assert updated.schedule == "daily"
    assert updated.timezone == "Asia/Ho_Chi_Minh"
    assert updated.cron == "0 0 * * *"
