"""Automation tools: list automations and their run history."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.errors import ToolError
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import READ, WRITE


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register automation tools on the MCP server."""

    @mcp.tool(
        name="nowing_automation_list",
        title="List automations in a workspace",
        annotations=READ,
        structured_output=False,
    )
    async def automation_list(
        limit: Annotated[
            int, Field(ge=1, le=200, description="Maximum automations to return.")
        ] = 50,
        offset: Annotated[
            int, Field(ge=0, description="Number of automations to skip.")
        ] = 0,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List the workspace's automations, with id, name, status, and version.

        Use this to inventory which automations exist before inspecting a
        specific one or triggering a run.
        Example: limit=20.
        """
        resolved = await context.resolve(workspace)
        data = await client.request(
            "GET",
            "/automations",
            params={"workspace_id": resolved.id, "limit": limit, "offset": offset},
        )
        data = data or {}
        items = data.get("items", [])
        total = data.get("total", len(items))
        if response_format == "json":
            return to_json(items)
        return _render_automation_list(items, total)

    @mcp.tool(
        name="nowing_automation_run",
        title="Start an automation run on demand",
        annotations=WRITE,
        structured_output=False,
    )
    async def automation_run(
        automation_id: Annotated[
            int, Field(ge=1, description="Id of the automation to run.")
        ],
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Kick off a manual run of an automation and return the run id/status.

        Fire-and-return: the run is queued as ``pending`` and executes in the
        background; this tool does not wait for it to finish. Check the run
        history later to see the outcome.
        Example: automation_id=3.
        """
        # Resolve the active workspace for context/auth even though the
        # backend automation run endpoint derives the workspace from the
        # automation_id itself.
        await context.resolve(workspace)
        return await _run_automation(
            client=client,
            automation_id=automation_id,
            response_format=response_format,
        )


def _render_automation_list(items: list[dict], total: int) -> str:
    if not items:
        return "No automations found in this workspace."
    lines = [f"# {total} automation(s)", ""]
    for automation in items:
        name = automation.get("name") or f"(id {automation.get('id')})"
        description = automation.get("description")
        suffix = f" — {clip(description, 120)}" if description else ""
        lines.append(
            f"- **{automation.get('id')}**: {name} "
            f"[{automation.get('status')}, v{automation.get('version')}]{suffix}"
        )
    return "\n".join(lines).strip()


def _render_run_started(run: dict) -> str:
    run_id = run.get("id")
    status = run.get("status") or "pending"
    return (
        f"Run started: **#{run_id}** (status: {status}). "
        "Track it via the automation run history."
    )


async def _run_automation(
    *,
    client: NowingClient,
    automation_id: int,
    response_format: str,
) -> str:
    # The backend resolves the workspace from the authenticated automation, so
    # do not send a workspace_id body that the endpoint does not consume.
    try:
        run = await client.request(
            "POST",
            f"/automations/{automation_id}/run",
        )
    except ToolError as exc:
        raise ToolError(f"Could not start automation {automation_id}: {exc}") from exc
    run = run or {}
    if not isinstance(run, dict) or not isinstance(run.get("id"), int):
        raise ToolError(
            f"Backend did not return a valid run for automation {automation_id}."
        )
    if response_format == "json":
        return to_json(
            {"run_id": run.get("id"), "status": run.get("status") or "pending"}
        )
    return _render_run_started(run)
