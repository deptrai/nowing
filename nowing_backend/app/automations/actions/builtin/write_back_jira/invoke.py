"""Execute a ``write_back_jira`` automation step."""

from __future__ import annotations

from typing import Any

from ..write_back.shared import execute_write_back
from .params import JiraActionParams

PROVIDER = "jira"


async def write_back(
    ctx: Any,
    params: dict[str, Any],
    *,
    tool: Any | None = None,
    connectors: list[Any] | None = None,
    load_mcp_tools: Any | None = None,
) -> dict[str, Any]:
    """Create or update a Jira issue through an MCP connector."""
    return await execute_write_back(
        PROVIDER,
        JiraActionParams,
        ctx,
        params,
        tool=tool,
        connectors=connectors,
        load_mcp_tools=load_mcp_tools,
    )
