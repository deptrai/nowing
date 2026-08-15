"""Lead scoring tools for MCP clients (Story 21.2)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext
from . import lead_score


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register lead-scoring tools on the server."""
    lead_score.register(mcp, client, context)
