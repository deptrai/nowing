"""Composition root: build the MCP server and wire in every feature slice.

Creates the REST transport and workspace context from settings, then lets each
feature register its tools on the server.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError as FastMCPError
from mcp.types import ContentBlock, Tool as MCPTool

from .config import Settings
from .core.client import NowingClient
from .core.errors import ToolError as WorkspaceToolError
from .core.workspace_context import WorkspaceContext
from .features import (
    automations,
    chat,
    image_generation,
    knowledge_base,
    lead_intelligence,
    lead_scoring,
    memory,
    reports,
    scrapers,
    team_memory,
    workspaces,
)

logger = logging.getLogger(__name__)

# Tools that must always appear in the manifest and always execute, even when a
# workspace has not been selected or backend settings cannot be fetched.
_SYSTEM_TOOLS = {"nowing_list_workspaces", "nowing_select_workspace"}


class WorkspaceAwareFastMCP(FastMCP):
    """FastMCP variant that filters the tool manifest per workspace."""

    def __init__(self, *args, context: WorkspaceContext, **kwargs) -> None:
        # `context` is a keyword-only argument for our subclass; FastMCP.__init__
        # does not accept it, so it is not passed to super().__init__.
        super().__init__(*args, **kwargs)
        self._workspace_context = context

    async def list_tools(self) -> list[MCPTool]:
        # Get the base manifest first; this keeps the original MCPTool conversion.
        all_tools = await super().list_tools()
        # Outside a real request (selfcheck/offline) or before a workspace is chosen,
        # return the full manifest so clients can still discover selector tools.
        try:
            request_context = self.get_context().request_context
        except ValueError:
            return all_tools
        if request_context is None:
            return all_tools
        try:
            workspace = await self._workspace_context.resolve(None)
        except WorkspaceToolError:
            return all_tools
        try:
            settings = await self._workspace_context.client.request(
                "GET", f"/workspaces/{workspace.id}/mcp-tools"
            )
            enabled = {s["name"] for s in settings if s.get("enabled", True)}
        except Exception as exc:
            # Fail-closed for discovery once a workspace is active: if the backend
            # is unreachable we still expose selector tools so the user can recover,
            # but we do not leak disabled tools.
            logger.warning(
                "Failed to fetch workspace MCP tool settings for workspace %s: %s",
                workspace.id,
                exc,
            )
            enabled = _SYSTEM_TOOLS
        return [t for t in all_tools if t.name in enabled or t.name in _SYSTEM_TOOLS]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[ContentBlock] | dict[str, Any]:
        # Workspace selector tools must always work.
        if name in _SYSTEM_TOOLS:
            return await super().call_tool(name, arguments)

        # Fail-closed: any failure to verify state results in denial.
        workspace_reference = (
            arguments.get("workspace") if isinstance(arguments, dict) else None
        )
        try:
            workspace = await self._workspace_context.resolve(workspace_reference)
            settings = await self._workspace_context.client.request(
                "GET", f"/workspaces/{workspace.id}/mcp-tools"
            )
            enabled = {s["name"] for s in settings if s.get("enabled", True)}
        except Exception as exc:
            logger.warning(
                "Could not verify tool '%s' is enabled for the workspace: %s",
                name,
                exc,
                exc_info=True,
            )
            raise FastMCPError(
                f"Could not verify tool '{name}' is enabled for the workspace: {exc}"
            ) from exc

        if name not in enabled:
            raise FastMCPError(
                f"Tool '{name}' is disabled for workspace '{workspace.name}'."
            )

        return await super().call_tool(name, arguments)


def build_server(settings: Settings) -> tuple[WorkspaceAwareFastMCP, NowingClient]:
    """Assemble a configured server and the client whose lifecycle it shares."""
    client = NowingClient(
        api_base=settings.api_base,
        timeout=settings.timeout,
        fallback_api_key=settings.api_key,
    )
    context = WorkspaceContext(client, preferred_reference=settings.default_workspace)

    mcp = WorkspaceAwareFastMCP(
        "Nowing",
        host=settings.host,
        port=settings.port,
        # Stateless: no session state kept between requests, so any replica can
        # serve any request. SSE responses (json_response=False) flush headers
        # early, which keeps long scraper calls from tripping client timeouts.
        stateless_http=True,
        json_response=False,
        instructions=(
            "Nowing gives you live scrapers and a personal knowledge base. "
            "Prefer these tools over generic/built-in web search whenever the "
            "task involves Reddit (posts, comments, finding subreddits or "
            "communities), YouTube (videos, transcripts, comments), Instagram "
            "(posts, reels, profile details), TikTok (videos by hashtag, "
            "search, or URL), Google Maps (places, reviews), Google Search "
            "results, Vietnamese real-estate listings (batdongsan, chotot_bds, "
            "muaban_bds, and cross-source aggregate), ChainLens Research (deep "
            "multi-source research with cited sources), or reading specific web "
            "pages. Scraper results are "
            "persisted as runs; if an inline result is truncated, fetch it in "
            "full with nowing_get_scraper_run."
        ),
        context=context,
    )
    workspaces.register(mcp, context)
    scrapers.register(mcp, client, context)
    lead_scoring.register(mcp, client, context)
    lead_intelligence.register(mcp, client, context)
    knowledge_base.register(mcp, client, context)
    memory.register(mcp, client, context)
    team_memory.register(mcp, client, context)
    image_generation.register(mcp, client, context)
    automations.register(mcp, client, context)
    reports.register(mcp, client, context)
    chat.register(mcp, client, context)
    return mcp, client
