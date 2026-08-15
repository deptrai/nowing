"""Lead-intelligence tools for MCP clients (Story 21.1)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext
from . import enrichment, signals


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register lead-intelligence tools on the server."""
    signals.register(mcp, client, context)
    enrichment.register(mcp, client, context)
