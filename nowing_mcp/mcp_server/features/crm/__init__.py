"""CRM tools for MCP clients (Story 21.5)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext
from . import tools


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register CRM tools on the server."""
    tools.register(mcp, client, context)
