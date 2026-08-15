"""MCP tools for intent signal detection (Story 21.1)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext, WorkspaceParam

SIGNAL_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

SIGNAL_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _render_signal(payload: dict) -> str:
    """Render a SignalOutput payload as markdown for the MCP client."""
    if payload.get("degraded"):
        reasons = payload.get("degradation_reasons") or ["unknown"]
        return f"Signal detection degraded: {', '.join(reasons)}."

    items = payload.get("items") or []
    if not items:
        return "No signals detected."

    lines = ["| Type | Company | Confidence | Source |", "|---|---|---|---|"]
    for item in items:
        lines.append(
            f"| {item.get('signal_type', '—')} | {item.get('company_name', '—')} | "
            f"{item.get('confidence', '—')} | {item.get('source_url') or '—'} |"
        )
    return "\n".join(lines)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register signal-detection tools."""

    @mcp.tool(
        name="nowing_detect_signal",
        title="Detect buying-intent signals for a company",
        annotations=SIGNAL_WRITE,
        structured_output=False,
    )
    async def detect_signal(
        company_name: Annotated[
            str,
            Field(description="Company name to research."),
        ],
        signal_type: Annotated[
            str,
            Field(
                description="Signal type to detect: funding, hiring, tech_stack, news, or executive_move."
            ),
        ],
        lookback_days: Annotated[
            int,
            Field(
                ge=0,
                le=365,
                description="How many days back to look for news/mentions.",
            ),
        ] = 30,
        confidence_threshold: Annotated[
            float,
            Field(
                ge=0.0,
                le=100.0,
                description="Minimum confidence to include a signal.",
            ),
        ] = 0.0,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Detect a buying-intent signal (funding, hiring, tech stack, news, executive move)
        for a company and persist the result.
        """
        ws = await context.resolve(workspace)
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/signals/detect",
            json={
                "company_name": company_name,
                "signal_type": signal_type,
                "lookback_days": lookback_days,
                "confidence_threshold": confidence_threshold,
            },
        )
        return _render_signal(result)

    @mcp.tool(
        name="nowing_list_signals",
        title="List detected signals",
        annotations=SIGNAL_READ,
        structured_output=False,
    )
    async def list_signals(
        signal_type: Annotated[
            str | None,
            Field(description="Filter by signal type."),
        ] = None,
        company_name: Annotated[
            str | None,
            Field(description="Filter by company name (case-insensitive substring)."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of signals to return."),
        ] = 20,
        workspace: WorkspaceParam = None,
    ) -> str:
        """List previously detected signals for the workspace."""
        ws = await context.resolve(workspace)
        params: dict = {"limit": limit}
        if signal_type:
            params["signal_type"] = signal_type
        if company_name:
            params["company_name"] = company_name

        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/signals",
            params=params,
        )
        return _render_signal(result)
