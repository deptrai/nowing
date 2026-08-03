"""Batdongsan scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

BatdongsanListingType = Literal["buy", "rent"]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Batdongsan tool."""

    @mcp.tool(
        name="nowing_batdongsan_scrape",
        title="Scrape Vietnamese real-estate listings from Batdongsan",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def batdongsan_scrape(
        city: Annotated[
            str,
            Field(
                description="City code: HN, SG, HP, CT, DN, VT, ... (see "
                "batdongsan.com.vn location codes)."
            ),
        ],
        listing_type: Annotated[
            BatdongsanListingType,
            Field(description="'buy' for property for sale, 'rent' for lease."),
        ] = "buy",
        district_id: Annotated[
            int | None,
            Field(description="District ID to restrict the search, if any."),
        ] = None,
        min_price: Annotated[
            int | None,
            Field(description="Minimum price in VND."),
        ] = None,
        max_price: Annotated[
            int | None,
            Field(description="Maximum price in VND."),
        ] = None,
        min_area: Annotated[
            int | None,
            Field(description="Minimum area in square meters."),
        ] = None,
        max_area: Annotated[
            int | None,
            Field(description="Maximum area in square meters."),
        ] = None,
        max_pages: Annotated[
            int, Field(ge=0, le=20, description="Maximum result pages to fetch.")
        ] = 5,
        max_items: Annotated[
            int, Field(ge=0, le=100, description="Maximum listings to return.")
        ] = 10,
        resolve_phones: Annotated[
            bool,
            Field(
                description="Open detail pages to resolve full phone numbers "
                "(slower, requires a batdongsan session)."
            ),
        ] = True,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape property listings from batdongsan.com.vn.

        Use this for Vietnamese real-estate research: tracking market
        trends, prices, supply, or locations. Returns typed listings with
        title, price, area, location, district, city, post date, thumbnail,
        and detail URL.
        Example: city='HN', listing_type='buy', min_area=50, max_items=20.
        """
        return await run_scraper(
            client,
            context,
            platform="batdongsan",
            verb="scrape",
            payload={
                "city": city,
                "listing_type": listing_type,
                "district_id": district_id,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "max_pages": max_pages,
                "max_items": max_items,
                "resolve_phones": resolve_phones,
            },
            workspace=workspace,
            response_format=response_format,
        )
