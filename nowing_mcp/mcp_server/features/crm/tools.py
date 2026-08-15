"""MCP tools for CRM integration (Story 21.5)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext, WorkspaceParam

CRM_READ = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

CRM_WRITE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


def _render_list(payload: list[dict]) -> str:
    if not payload:
        return "No CRM connections."
    lines = ["| Provider | Status | Last sync |", "|---|---|---|"]
    for item in payload:
        lines.append(
            f"| {item.get('provider', '—')} | {item.get('status', '—')} | "
            f"{item.get('last_sync_at') or '—'} |"
        )
    return "\n".join(lines)


def _render_logs(payload: list[dict]) -> str:
    if not payload:
        return "No sync logs."
    lines = ["| Direction | Entity | Status | Synced |", "|---|---|---|---|"]
    for item in payload:
        lines.append(
            f"| {item.get('direction')} | {item.get('entity_type')} | "
            f"{item.get('status')} | {item.get('synced_at') or '—'} |"
        )
    return "\n".join(lines)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register CRM tools."""

    @mcp.tool(
        name="nowing_connect_crm",
        title="Start connecting a CRM provider",
        annotations=CRM_WRITE,
        structured_output=False,
    )
    async def connect_crm(
        provider: Annotated[
            str,
            Field(description="CRM provider: salesforce, hubspot, or pipedrive."),
        ],
        workspace: WorkspaceParam = None,
    ) -> str:
        """Start OAuth authorization for a CRM provider and return the auth URL."""
        ws = await context.resolve(workspace)
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/crm/{provider}/connect",
            json={"provider": provider},
        )
        return f"Open this URL in a browser to authorize: {result['auth_url']}"

    @mcp.tool(
        name="nowing_list_crm_connections",
        title="List active CRM connections",
        annotations=CRM_READ,
        structured_output=False,
    )
    async def list_crm_connections(
        workspace: WorkspaceParam = None,
    ) -> str:
        """List active CRM connections for the workspace."""
        ws = await context.resolve(workspace)
        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/crm/connections",
        )
        return _render_list(result)

    @mcp.tool(
        name="nowing_sync_crm",
        title="Trigger a CRM sync",
        annotations=CRM_WRITE,
        structured_output=False,
    )
    async def sync_crm(
        connection_id: Annotated[
            str,
            Field(description="CRM connection UUID."),
        ],
        entity_type: Annotated[
            str,
            Field(description="Entity type: lead or lead_score."),
        ] = "lead",
        entity_ids: Annotated[
            list[str] | None,
            Field(description="List of entity UUIDs to sync."),
        ] = None,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Trigger a one-way sync for the given entities."""
        ws = await context.resolve(workspace)
        payload = {
            "entity_type": entity_type,
            "direction": "nowing_to_crm",
            "entity_ids": entity_ids,
        }
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/crm/connections/{connection_id}/sync",
            json=payload,
        )
        items = result.get("results") or []
        degraded = any(i.get("degraded") for i in items)
        if degraded:
            reasons = [i.get("degradation_reasons") for i in items if i.get("degraded")]
            return f"Sync degraded: {reasons}"
        return f"Sync initiated for {len(items)} entity(s)."

    @mcp.tool(
        name="nowing_list_crm_sync_logs",
        title="List CRM sync logs",
        annotations=CRM_READ,
        structured_output=False,
    )
    async def list_crm_sync_logs(
        connection_id: Annotated[
            str,
            Field(description="CRM connection UUID."),
        ],
        workspace: WorkspaceParam = None,
    ) -> str:
        """List recent sync logs for a CRM connection."""
        ws = await context.resolve(workspace)
        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/crm/connections/{connection_id}/sync-logs",
        )
        return _render_logs(result)
