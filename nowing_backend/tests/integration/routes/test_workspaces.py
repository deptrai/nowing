"""Integration tests for workspace routes."""

from __future__ import annotations

import httpx
import pytest


async def test_create_workspace_defaults_to_general_vertical(client_as_regular_user: httpx.AsyncClient):
    """POST /workspaces creates a workspace with vertical defaulting to general."""
    resp = await client_as_regular_user.post(
        "/api/v1/workspaces",
        json={"name": "Default Vertical Space", "description": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vertical"] == "general"


async def test_create_workspace_accepts_vertical(client_as_regular_user: httpx.AsyncClient):
    """POST /workspaces accepts an explicit vertical."""
    resp = await client_as_regular_user.post(
        "/api/v1/workspaces",
        json={"name": "Real Estate Space", "description": "test", "vertical": "real_estate"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vertical"] == "real_estate"


async def test_update_workspace_vertical(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace,
):
    """PUT /workspaces/{id} updates the workspace vertical."""
    resp = await client_as_regular_user.put(
        f"/api/v1/workspaces/{db_workspace.id}",
        json={"vertical": "auto"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vertical"] == "auto"


async def test_update_workspace_rejects_invalid_vertical(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace,
):
    """PUT /workspaces/{id} rejects an unknown vertical."""
    resp = await client_as_regular_user.put(
        f"/api/v1/workspaces/{db_workspace.id}",
        json={"vertical": "invalid_vertical"},
    )
    assert resp.status_code == 422


async def test_create_workspace_auto_provisions_xactions_connector(
    client_as_regular_user: httpx.AsyncClient,
):
    """POST /workspaces auto-provisions an XACTIONS_MCP_CONNECTOR for the new workspace."""
    resp = await client_as_regular_user.post(
        "/api/v1/workspaces",
        json={"name": "XActions Auto Seed", "description": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    workspace_id = data["id"]

    connectors_resp = await client_as_regular_user.get(
        f"/api/v1/search-source-connectors?workspace_id={workspace_id}"
    )
    assert connectors_resp.status_code == 200
    connectors = connectors_resp.json()
    xactions = [c for c in connectors if c["connector_type"] == "XACTIONS_MCP_CONNECTOR"]
    assert len(xactions) == 1
    assert xactions[0]["name"] == "XActions"
    assert xactions[0]["config"]["consumer_id"] == "nowing"
    assert xactions[0]["config"]["trusted_tools"] == ["x_scrape", "x_search", "x_crawl_post"]


@pytest.mark.integration
async def test_list_workspaces_returns_persisted_retention_values(
    client_as_regular_user,
    db_session,
    db_workspace,
):
    """Verify GET /workspaces returns persisted retention values in WorkspaceWithStats."""
    db_workspace.document_retention_days = 90
    db_workspace.auto_archive_enabled = True
    db_workspace.document_retention_action = "delete"
    db_workspace.memory_retention_days = 45
    db_workspace.memory_auto_archive_enabled = True
    db_workspace.memory_retention_action = "delete"
    db_workspace.memory_auto_extract_enabled = False
    await db_session.commit()

    resp = await client_as_regular_user.get("/workspaces")
    assert resp.status_code == 200
    data = resp.json()
    ws_item = next((w for w in data if w["id"] == db_workspace.id), None)
    assert ws_item is not None
    assert ws_item["document_retention_days"] == 90
    assert ws_item["auto_archive_enabled"] is True
    assert ws_item["document_retention_action"] == "delete"
    assert ws_item["memory_retention_days"] == 45
    assert ws_item["memory_auto_archive_enabled"] is True
    assert ws_item["memory_retention_action"] == "delete"
    assert ws_item["memory_auto_extract_enabled"] is False
