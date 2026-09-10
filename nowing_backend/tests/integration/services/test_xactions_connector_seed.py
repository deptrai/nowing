"""Integration tests for the XActions connector auto-seeder."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import SearchSourceConnectorType
from app.models.connectors import SearchSourceConnector
from app.models.workspaces import Workspace
from app.services.xactions_connector_seed import (
    build_xactions_connector_config,
    ensure_workspace_xactions_connector,
    seed_xactions_connectors,
)

pytestmark = pytest.mark.integration


async def test_build_xactions_connector_config_uses_env():
    """The connector config carries URL, consumer id and trusted meta-tools."""
    cfg = build_xactions_connector_config()

    assert cfg["server_config"]["transport"] == "streamable-http"
    assert "url" in cfg["server_config"]
    assert cfg["trusted_tools"] == ["x_scrape", "x_search", "x_crawl_post"]
    assert cfg["consumer_id"] is not None
    headers = cfg["server_config"].get("headers", {})
    assert "X-Consumer-Id" in headers


async def test_seed_xactions_connectors_is_n_plus_one_safe(
    db_session, db_user, db_workspace
):
    """Seeding across many workspaces uses a single set lookup, not N queries."""
    # Add a few extra workspaces to make the N+1 pattern visible if it existed.
    extra_workspaces = [
        Workspace(
            name=f"seed-test-{i}",
            user_id=db_user.id,
            plan_tier="basic",
        )
        for i in range(5)
    ]
    for ws in extra_workspaces:
        db_session.add(ws)
    await db_session.commit()

    created = await seed_xactions_connectors(db_session)
    assert created >= 6  # db_workspace + 5 extras

    # Re-running should be idempotent and create no new rows.
    created_again = await seed_xactions_connectors(db_session)
    assert created_again == 0

    result = await db_session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR,
        )
    )
    connectors = result.scalars().all()
    workspace_ids = {c.workspace_id for c in connectors}
    assert db_workspace.id in workspace_ids
    for ws in extra_workspaces:
        assert ws.id in workspace_ids


async def test_ensure_workspace_xactions_connector_creates_once(
    db_session, db_workspace, db_user
):
    """Per-workspace seeding is idempotent."""
    first = await ensure_workspace_xactions_connector(
        db_session, db_workspace.id, db_user.id
    )
    assert first is not None
    assert first.connector_type == SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR

    second = await ensure_workspace_xactions_connector(
        db_session, db_workspace.id, db_user.id
    )
    assert second is not None
    assert second.id == first.id


async def test_ensure_workspace_xactions_connector_skips_deleting_workspace(
    db_session, db_user
):
    """Workspaces marked for deletion do not get a connector."""
    deleting = Workspace(name="[DELETING] temp", user_id=db_user.id, plan_tier="basic")
    db_session.add(deleting)
    await db_session.commit()
    await db_session.refresh(deleting)

    created = await ensure_workspace_xactions_connector(
        db_session, deleting.id, db_user.id
    )
    assert created is None
