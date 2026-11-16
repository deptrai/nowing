"""MCP tools for lead ingestion, tables, listing, and credits (Story 42.4)."""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.errors import ToolError
from ...core.workspace_context import WorkspaceContext, WorkspaceParam

LEADS_READ = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

LEADS_WRITE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


def _render_leads(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)
    items = payload.get("items") or []
    total = payload.get("total", len(items))
    if not items:
        return f"No leads (total: {total})."
    lines = ["| Company | Status | Score | Source |", "|---|---|---|---|"]
    for item in items:
        if isinstance(item, dict):
            lines.append(
                f"| {item.get('company') or item.get('company_name') or '—'} "
                f"| {item.get('status', '—')} "
                f"| {item.get('composite_score') or item.get('fit_score') or '—'} "
                f"| {item.get('source', '—')} |"
            )
    lines.append(f"Total: {total}")
    return "\n".join(lines)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register lead workspace tools."""

    @mcp.tool(
        name="nowing_ingest_leads",
        title="Ingest a batch of leads",
        annotations=LEADS_WRITE,
        structured_output=False,
    )
    async def ingest_leads(
        leads: Annotated[
            list[dict[str, Any]],
            Field(description="List of lead objects to ingest (1-100 items)."),
        ],
        idempotency_key: Annotated[
            str | None,
            Field(
                description=(
                    "Optional key forwarded to the backend and logged in the "
                    "lead activity ledger for audit. Real dedupe is per-lead "
                    "via value_hmac upsert; a replayed key does not create "
                    "duplicate leads."
                )
            ),
        ] = None,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Ingest a batch of leads and return the backend result as JSON
        (ingested_count, skipped_blacklisted_count, failed_count, lead_ids)."""
        ws = await context.resolve(workspace)
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/leads/batch-ingest",
            json={"leads": leads},
            headers=headers,
        )
        return json.dumps(result, default=str)

    @mcp.tool(
        name="nowing_create_leads_table",
        title="Create a leads table",
        annotations=LEADS_WRITE,
        structured_output=False,
    )
    async def create_leads_table(
        name: Annotated[
            str,
            Field(description="Name of the leads table to create."),
        ],
        icon: Annotated[
            str,
            Field(description="Table icon (emoji or icon name, default 'table')."),
        ] = "table",
        workspace: WorkspaceParam = None,
    ) -> str:
        """Create a new leads table in the workspace."""
        ws = await context.resolve(workspace)
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/tables",
            json={"name": name, "icon": icon},
        )
        return json.dumps(result, default=str)

    @mcp.tool(
        name="nowing_list_leads",
        title="List leads in the workspace",
        annotations=LEADS_READ,
        structured_output=False,
    )
    async def list_leads(
        limit: Annotated[
            int | None,
            Field(description="Maximum number of leads to return (1-200, default 50)."),
        ] = None,
        offset: Annotated[
            int | None,
            Field(description="Number of leads to skip for pagination."),
        ] = None,
        client_id: Annotated[
            str | None,
            Field(description="Filter by client/campaign id."),
        ] = None,
        source: Annotated[
            str | None,
            Field(description="Filter by lead source."),
        ] = None,
        workspace: WorkspaceParam = None,
    ) -> str:
        """List leads in the workspace with pagination, as a compact table."""
        ws = await context.resolve(workspace)
        safe_limit = max(1, min(limit if limit is not None else 50, 200))
        safe_offset = max(0, offset if offset is not None else 0)
        params: dict[str, Any] = {"limit": safe_limit, "offset": safe_offset}
        if client_id:
            params["client_id"] = client_id
        if source:
            params["source"] = source
        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/leads",
            params=params,
        )
        return _render_leads(result)

    @mcp.tool(
        name="nowing_get_credits_balance",
        title="Get the workspace credit balance",
        annotations=LEADS_READ,
        structured_output=False,
    )
    async def get_credits_balance(
        workspace: WorkspaceParam = None,
    ) -> str:
        """Return the workspace's remaining credit balance (fails with no_wallet if none exists)."""
        ws = await context.resolve(workspace)
        try:
            result = await client.request(
                "GET",
                f"/workspaces/{ws.id}/credits/balance",
            )
        except ToolError as exc:
            # The client collapses HTTP status into a sentence; a missing wallet
            # (404) reads as "resource was not found" / "Nowing returned 404".
            text = str(exc)
            if "404" in text or "not found" in text.lower():
                return '{"status": "failed", "reason": "no_wallet"}'
            raise
        return json.dumps(result, default=str)
