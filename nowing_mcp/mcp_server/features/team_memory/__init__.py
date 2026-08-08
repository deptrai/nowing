"""Workspace team-memory tools: read and overwrite the shared markdown brief.

Distinct from the long-term ``nowing_remember``/``nowing_recall`` tools — those
are the semantic fact store. Team memory is one editable markdown document that
sets context for every member of the workspace. ``PUT`` overwrites the whole
document, so the update tool requires read-before-write by convention.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import DESTRUCTIVE, READ


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the workspace team-memory tools."""

    @mcp.tool(
        name="nowing_workspace_memory_get",
        title="Read workspace team memory",
        annotations=READ,
        structured_output=False,
    )
    async def workspace_memory_get(
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Read the workspace's team memory (one shared markdown brief).

        Use this to load the team's standing context — goals, conventions,
        decisions — that every member and agent of the workspace shares.
        This is the collaborative brief, NOT the personal long-term memory
        (that is nowing_recall). Returns the full markdown and the document
        size limits.
        """
        resolved = await context.resolve(workspace)
        memory = await client.request(
            "GET",
            f"/workspaces/{resolved.id}/memory",
        )
        if response_format == "json":
            return to_json(memory)
        return _render_memory(memory, resolved.name)

    @mcp.tool(
        name="nowing_workspace_memory_update",
        title="Overwrite workspace team memory",
        annotations=DESTRUCTIVE,
        structured_output=False,
    )
    async def workspace_memory_update(
        memory_md: Annotated[
            str,
            Field(
                min_length=1,
                description="The complete new team-memory markdown. This "
                "REPLACES the entire document — read the current memory with "
                "nowing_workspace_memory_get first, then pass the full "
                "combined text.",
            ),
        ],
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Overwrite the workspace's team memory with the given markdown.

        Use this to persist shared context every member should see. DESTRUCTIVE:
        the current document is replaced entirely — always read first with
        nowing_workspace_memory_get, edit the returned text, then pass the full
        new content. Returns the stored memory and its size limits.
        """
        resolved = await context.resolve(workspace)
        memory = await client.request(
            "PUT",
            f"/workspaces/{resolved.id}/memory",
            json={"memory_md": memory_md},
        )
        if response_format == "json":
            return to_json(memory)
        return _render_memory(memory, resolved.name)


def _render_memory(memory: dict | None, workspace_name: str) -> str:
    if not memory:
        return (
            f"Team memory for '{workspace_name}' is empty. "
            "Set it with `nowing_workspace_memory_update`."
        )
    content = memory.get("memory_md") or "(empty)"
    limits = memory.get("limits") or {}
    soft = limits.get("soft")
    hard = limits.get("hard")
    lines = [f"# Team memory — {workspace_name}"]
    if soft is not None and hard is not None:
        lines.append(f"- size limits: {soft} soft / {hard} hard")
    lines.append("")
    lines.append(clip(content))
    return "\n".join(lines).strip()
