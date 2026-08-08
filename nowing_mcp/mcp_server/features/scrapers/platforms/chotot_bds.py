"""Chotot BĐS (Chợ Tốt Nhà) scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

ChototListingType = Literal["buy", "rent"]
ChototPropertyType = Literal["apartment", "house", "land", "office", "all"]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Chotot BĐS scraper tool."""

    @mcp.tool(
        name="nowing_chotot_bds_scrape",
        title="Scrape Vietnamese real-estate listings from Chotot (Chợ Tốt Nhà)",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def chotot_bds_scrape(
        city: Annotated[
            str,
            Field(
                min_length=1,
                description="City name or slug, e.g. 'hanoi', 'ho chi minh', 'da nang'.",
            ),
        ],
        listing_type: Annotated[
            ChototListingType,
            Field(description="'buy' for sale listings, 'rent' for lease listings."),
        ] = "buy",
        property_type: Annotated[
            ChototPropertyType,
            Field(description="Property type to filter by."),
        ] = "all",
        district: Annotated[
            str | None,
            Field(min_length=1, description="Optional district name or slug."),
        ] = None,
        district_id: Annotated[
            int | None,
            Field(ge=0, description="Optional district ID to restrict the search."),
        ] = None,
        min_price: Annotated[
            int | None,
            Field(ge=0, description="Minimum price in VND."),
        ] = None,
        max_price: Annotated[
            int | None,
            Field(ge=0, description="Maximum price in VND."),
        ] = None,
        min_area: Annotated[
            int | None,
            Field(ge=0, description="Minimum area in square meters."),
        ] = None,
        max_area: Annotated[
            int | None,
            Field(ge=0, description="Maximum area in square meters."),
        ] = None,
        max_pages: Annotated[
            int, Field(ge=1, le=20, description="Maximum result pages to fetch.")
        ] = 5,
        max_items: Annotated[
            int, Field(ge=1, le=100, description="Maximum listings to return.")
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape property listings from nha.chotot.com.

        Use this for Vietnamese real-estate research on Chợ Tốt Nhà: tracking
        market trends, prices, supply, or locations. Returns typed listings
        with title, price, area, location, and detail URL.
        Example: city='hanoi', listing_type='buy', max_items=20.
        """
        if (min_price is not None and max_price is not None and min_price > max_price) or (
            min_area is not None and max_area is not None and min_area > max_area
        ):
            raise ValueError("min value cannot exceed max value")
        return await run_scraper(
            client,
            context,
            platform="chotot_bds",
            verb="scrape",
            payload={
                "city": city,
                "listing_type": listing_type,
                "property_type": property_type,
                "district": district,
                "district_id": district_id,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "max_pages": max_pages,
                "max_items": max_items,
            },
            workspace=workspace,
            response_format=response_format,
        )
