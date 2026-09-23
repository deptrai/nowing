"""Integration tests for Vertical Alert Rule Templates routes (Story 6.11)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.templates.models import AlertTemplate
from app.alerts.templates.registry import VerticalAlertTemplateRegistry
from app.app import app
from app.auth.context import AuthContext
from app.db import (
    Permission,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def authed_workspace_setup(
    db_session: AsyncSession,
) -> tuple[AsyncClient, User, Workspace]:
    """Create a user, workspace with OWNER membership, and an authenticated client."""
    user = User(
        id=uuid4(),
        email=f"owner_{uuid4().hex[:8]}@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name=f"Workspace_{uuid4().hex[:6]}",
        user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    owner_role = WorkspaceRole(
        workspace_id=workspace.id,
        name="Owner",
        permissions=[p.value for p in Permission],
        is_system_role=True,
    )
    db_session.add(owner_role)
    await db_session.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role_id=owner_role.id,
    )
    db_session.add(membership)
    await db_session.commit()

    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(user)

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0,
    ) as client:
        yield client, user, workspace

    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_auth_context, None)


async def test_get_alert_templates_catalog(authed_workspace_setup) -> None:
    """GET /workspaces/{id}/alerts/templates returns canonical templates with availability."""
    client, _user, workspace = authed_workspace_setup

    res = await client.get(f"/workspaces/{workspace.id}/alerts/templates")
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 5

    template_ids = {t["template_id"] for t in data}
    assert "stock_price_threshold" in template_ids
    assert "news_topic_monitoring" in template_ids
    assert "company_status_change" in template_ids
    assert "ecommerce_price_drop" in template_ids
    assert "competitor_item_tracking" in template_ids

    # Every template has availability metadata
    for t in data:
        assert "is_available" in t
        assert "category" in t
        assert "diff_strategy" in t
        assert "parameters" in t


async def test_create_alert_from_template_success(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/alerts/from-template creates an alert rule and auto-subscribes."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "stock_price_threshold",
        "name": "Vinamilk VNM Drop Alert",
        "parameters": {
            "symbol": "VNM",
            "price_threshold": 65000,
            "direction": "below",
        },
        "schedule": "daily",
        "notification_channels": ["in_app", "telegram"],
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/alerts/from-template",
        json=payload,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["name"] == "Vinamilk VNM Drop Alert"
    assert data["capability_id"] == "cafef.scrape"
    assert data["diff_strategy"] == "threshold_cross"
    assert data["schedule"] == "daily"
    assert data["query"] == {"symbol": "VNM", "include_financials": False}
    assert data["threshold"] == {
        "field": "price",
        "value": 65000.0,
        "direction": "below",
    }
    assert "in_app" in data["notification_channels"]
    assert "telegram" in data["notification_channels"]
    assert data["enabled"] is True


async def test_create_alert_from_template_missing_template_404(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/alerts/from-template returns 404 for unknown template."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "nonexistent_template_slug",
        "name": "Nonexistent Alert",
        "parameters": {},
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/alerts/from-template",
        json=payload,
    )
    assert res.status_code == 404, res.text
    assert "not found" in res.text.lower()


async def test_create_alert_from_template_missing_required_param_400(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/alerts/from-template returns 400 when missing required param."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "stock_price_threshold",
        "name": "Missing Params Alert",
        "parameters": {
            # missing symbol and direction
            "price_threshold": 65000,
        },
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/alerts/from-template",
        json=payload,
    )
    assert res.status_code == 400, res.text
    assert "compilation error" in res.text.lower() or "missing required parameter" in res.text.lower()


async def test_create_alert_from_template_unavailable_capability_400(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/alerts/from-template returns 400 CAPABILITY_UNAVAILABLE."""
    client, _user, workspace = authed_workspace_setup

    # Temporarily register an unavailable template
    unavail_tmpl = AlertTemplate(
        template_id="unavail_test_template",
        name="Unavailable Test",
        description="Testing unavailable capability rejection",
        category="custom",
        required_capability="strictly.unregistered.fake.capability",
        fallback_capabilities=[],
        diff_strategy="new_items",
        default_schedule="daily",
        parameters=[],
    )
    VerticalAlertTemplateRegistry.register(unavail_tmpl)

    payload = {
        "template_id": "unavail_test_template",
        "name": "Should Fail Alert",
        "parameters": {},
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/alerts/from-template",
        json=payload,
    )
    assert res.status_code == 400, res.text
    data = res.json()
    assert "CAPABILITY_UNAVAILABLE" in str(data)


async def test_alert_rules_prefix_alias_supported(authed_workspace_setup) -> None:
    """Both /alert-rules/templates and /alerts/templates prefixes are supported."""
    client, _user, workspace = authed_workspace_setup

    res1 = await client.get(f"/workspaces/{workspace.id}/alert-rules/templates")
    assert res1.status_code == 200, res1.text

    res2 = await client.get(f"/workspaces/{workspace.id}/alerts/templates")
    assert res2.status_code == 200, res2.text
    assert res1.json() == res2.json()

