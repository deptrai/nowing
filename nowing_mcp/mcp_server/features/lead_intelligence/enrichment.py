"""MCP tools for contact enrichment (Story 21.3)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext, WorkspaceParam

ENRICH_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

ENRICH_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _render_enrichment(payload: dict) -> str:
    """Render an EnrichmentOutput payload as markdown for the MCP client."""
    if payload.get("degraded"):
        reasons = payload.get("degradation_reasons") or ["unknown"]
        return f"Contact enrichment degraded: {', '.join(reasons)}."
    request_id = payload.get("enrichment_request_id") or "—"
    return (
        f"Enrichment request {request_id} accepted for lead {payload.get('lead_id')}. "
        f"Found {payload.get('contact_count', 0)} verified contacts "
        f"(cost {payload.get('cost_micros', 0)} micros)."
    )


def _render_contacts(payload: list[dict]) -> str:
    """Render VerifiedContactRead payloads as a markdown table."""
    if not payload:
        return "No verified contacts found for this lead."
    lines = [
        "| Name | Title | Email | Phone | Status | Confidence | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload:
        lines.append(
            f"| {item.get('name') or '—'} | {item.get('title') or '—'} | "
            f"{item.get('email') or '—'} | {item.get('phone') or '—'} | "
            f"{item.get('verification_status') or '—'} | "
            f"{item.get('confidence') or '—'} | {item.get('source_provider') or '—'} |"
        )
    return "\n".join(lines)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register contact-enrichment tools."""

    @mcp.tool(
        name="nowing_enrich_lead",
        title="Enrich a lead with verified contacts",
        annotations=ENRICH_WRITE,
        structured_output=False,
    )
    async def enrich_lead(
        lead_id: Annotated[
            str,
            Field(description="UUID of the lead to enrich."),
        ],
        requested_count: Annotated[
            int,
            Field(ge=1, le=50, description="Maximum number of contacts to request."),
        ] = 5,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Run contact enrichment for one lead.

        Enriches company contacts (name/title/email/phone) through Cleanlist and
        BetterContact, falling back to basic verification when providers fail.
        Returns an enrichment request id; verified contacts can be listed with
        `nowing_list_contacts`.
        """
        ws = await context.resolve(workspace)
        result = await client.request(
            "POST",
            f"/workspaces/{ws.id}/leads/{lead_id}/enrich",
            json={"requested_count": requested_count},
        )
        return _render_enrichment(result)

    @mcp.tool(
        name="nowing_list_contacts",
        title="List verified contacts for a lead",
        annotations=ENRICH_READ,
        structured_output=False,
    )
    async def list_verified_contacts(
        lead_id: Annotated[
            str,
            Field(description="UUID of the lead to list contacts for."),
        ],
        limit: Annotated[
            int,
            Field(ge=1, le=200, description="Maximum number of contacts to return."),
        ] = 20,
        offset: Annotated[
            int,
            Field(ge=0, description="Number of contacts to skip."),
        ] = 0,
        workspace: WorkspaceParam = None,
    ) -> str:
        """List the verified contacts discovered for a lead (newest first)."""
        ws = await context.resolve(workspace)
        result = await client.request(
            "GET",
            f"/workspaces/{ws.id}/leads/{lead_id}/contacts",
            params={"limit": limit, "offset": offset},
        )
        return _render_contacts(result)