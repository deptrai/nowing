"""Masothue scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

SearchType = Literal[
    "auto",
    "enterpriseTax",
    "enterpriseName",
    "legalName",
    "personalTax",
    "identity",
]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the masothue scraper tool."""

    @mcp.tool(
        name="nowing_masothue_scrape",
        title="Scrape Vietnamese company data from masothue.com",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def masothue_scrape(
        query: Annotated[
            str,
            Field(description="Company name, tax code, or representative name to search."),
        ],
        search_type: Annotated[
            SearchType,
            Field(description="Search field: auto, enterpriseTax, enterpriseName, legalName, personalTax, or identity."),
        ] = "auto",
        tax_code: Annotated[
            str | None,
            Field(description="Optional tax code to filter results after search."),
        ] = None,
        max_pages: Annotated[
            int,
            Field(ge=0, le=20, description="Maximum result pages to fetch."),
        ] = 5,
        max_items: Annotated[
            int,
            Field(ge=0, le=100, description="Maximum companies to return."),
        ] = 10,
        resolve_detail: Annotated[
            bool,
            Field(description="Open detail pages to resolve full company fields."),
        ] = True,
        include_phone: Annotated[
            bool,
            Field(description="Include phone numbers in the output (not stored in canonical)."),
        ] = False,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape company profiles from masothue.com.

        Use this for Vietnamese business research: verify tax codes, legal
        representatives, company status, and industry information.
        Example: query='Vinamilk', search_type='enterpriseName', max_items=5.
        """
        return await run_scraper(
            client,
            context,
            platform="masothue",
            verb="scrape",
            payload={
                "query": query,
                "search_type": search_type,
                "tax_code": tax_code,
                "max_pages": max_pages,
                "max_items": max_items,
                "resolve_detail": resolve_detail,
                "include_phone": include_phone,
            },
            workspace=workspace,
            response_format=response_format,
        )
