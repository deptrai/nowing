"""MCP tools for lead scoring and prioritization (Story 21.2)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import LEAD_SCORE, LEAD_SCORE_READ


def _render_output(payload: dict) -> str:
    """Render a LeadScoreOutput payload as markdown for the MCP client."""
    if payload.get("degraded"):
        reasons = payload.get("degradation_reasons") or ["unknown"]
        return f"Lead scoring degraded: {', '.join(reasons)}."

    items = payload.get("items") or []
    if not items:
        return "No leads were scored."

    lines = ["| Company | Score | Fit | Intent | Class | Trend |", "|---|---|---|---|---|---|"]
    for item in items:
        lines.append(
            f"| {item.get('company_name', '—')} | {item.get('score', '—')} | "
            f"{item.get('fit_score', '—')} | {item.get('intent_score', '—')} | "
            f"{item.get('classification', '—')} | {item.get('trend') or '—'} |"
        )
    return "\n".join(lines)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register lead-scoring tools."""

    @mcp.tool(
        name="nowing_score_leads",
        title="Score and prioritize leads",
        annotations=LEAD_SCORE,
        structured_output=False,
    )
    async def score_leads(
        lead_ids: Annotated[
            list[str] | None,
            Field(
                description="Lead UUIDs to score. Omit to score all leads in the workspace."
            ),
        ] = None,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Score a list of leads or all leads in the workspace.

        Returns a markdown table with composite score, fit, intent, classification,
        and trend. Scores are persisted and can be listed with
        `nowing_list_lead_scores`.
        """
        ws = await context.resolve(workspace)
        payload = {"lead_ids": lead_ids} if lead_ids else {}
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/leads/score",
            json=payload,
        )
        return _render_output(result)

    @mcp.tool(
        name="nowing_list_lead_scores",
        title="List lead scores",
        annotations=LEAD_SCORE_READ,
        structured_output=False,
    )
    async def list_lead_scores(
        company_name: Annotated[
            str | None,
            Field(description="Filter by company name (case-insensitive substring)."),
        ] = None,
        classification: Annotated[
            str | None,
            Field(description="Filter by hot, warm, or cold."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=200, description="Maximum number of scores to return."),
        ] = 50,
        workspace: WorkspaceParam = None,
    ) -> str:
        """List the most recent lead scores for the workspace."""
        ws = await context.resolve(workspace)
        params: dict = {"limit": limit}
        if company_name:
            params["company_name"] = company_name
        if classification:
            params["classification"] = classification

        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/leads/scores",
            params=params,
        )
        return _render_output({"items": result, "degraded": False})
