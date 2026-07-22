"""Red-phase acceptance tests for workspace MCP tool toggles (Story 2.5).

These tests describe the expected HTTP contract for the new
`/api/v1/workspaces/{workspace_id}/mcp-tools` endpoints.
They will fail until the backend routes and schema are implemented.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/workspaces"


async def test_owner_can_list_mcp_tools(client, db_workspace):
    """GET returns all built-in MCP tools with default enabled=true."""
    resp = await client.get(f"{BASE}/{db_workspace.id}/mcp-tools")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    names = {item["name"] for item in body}
    assert "nowing_google_search" in names
    assert "nowing_search_knowledge_base" in names
    assert "nowing_list_workspaces" in names
    assert "nowing_select_workspace" in names
    assert all(item.get("enabled", False) is True for item in body)


async def test_owner_can_disable_and_list_reflects_change(client, db_workspace):
    """PUT toggles a tool off and the next GET shows enabled=false."""
    put_resp = await client.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={"enabled": False},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["enabled"] is False

    get_resp = await client.get(f"{BASE}/{db_workspace.id}/mcp-tools")
    assert get_resp.status_code == 200
    tool = next(
        item for item in get_resp.json() if item["name"] == "nowing_google_search"
    )
    assert tool["enabled"] is False


async def test_editor_can_list_but_not_update(client_as_editor, db_workspace):
    """Editor has SETTINGS_VIEW but not SETTINGS_UPDATE."""
    get_resp = await client_as_editor.get(f"{BASE}/{db_workspace.id}/mcp-tools")
    assert get_resp.status_code == 200

    put_resp = await client_as_editor.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={"enabled": False},
    )
    assert put_resp.status_code == 403


async def test_viewer_can_list_but_not_update(client_as_viewer, db_workspace):
    """Viewer has SETTINGS_VIEW but not SETTINGS_UPDATE."""
    get_resp = await client_as_viewer.get(f"{BASE}/{db_workspace.id}/mcp-tools")
    assert get_resp.status_code == 200

    put_resp = await client_as_viewer.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={"enabled": False},
    )
    assert put_resp.status_code == 403


async def test_non_member_cannot_access(client_as_other, db_workspace):
    """A user with no workspace membership is denied both read and write."""
    get_resp = await client_as_other.get(f"{BASE}/{db_workspace.id}/mcp-tools")
    assert get_resp.status_code == 403

    put_resp = await client_as_other.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={"enabled": False},
    )
    assert put_resp.status_code == 403


async def test_put_rejects_unknown_tool_name(client, db_workspace):
    """Toggling a tool not in the catalog returns 400."""
    resp = await client.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_not_a_real_tool",
        json={"enabled": False},
    )
    assert resp.status_code == 400


async def test_put_rejects_system_tools(client, db_workspace):
    """Workspace selector tools cannot be disabled."""
    for tool_name in ("nowing_list_workspaces", "nowing_select_workspace"):
        resp = await client.put(
            f"{BASE}/{db_workspace.id}/mcp-tools/{tool_name}",
            json={"enabled": False},
        )
        assert resp.status_code == 400


async def test_put_validates_enabled_boolean(client, db_workspace):
    """Missing or malformed `enabled` body returns 422."""
    resp = await client.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={},
    )
    assert resp.status_code == 422

    resp2 = await client.put(
        f"{BASE}/{db_workspace.id}/mcp-tools/nowing_google_search",
        json={"enabled": "false"},
    )
    assert resp2.status_code == 422
