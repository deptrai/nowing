"""Integration tests for workspace routes."""

from __future__ import annotations

import httpx


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
