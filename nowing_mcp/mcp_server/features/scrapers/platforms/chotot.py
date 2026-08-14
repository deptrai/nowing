"""Chợ Tốt multi-category scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

ChototCategory = Annotated[
    str,
    Field(
        pattern=r"^(bds|cars|motorbikes|electronics|jobs|home_goods|home_appliances|kitchen|pets|fashion|services|home_services|\d+)$",
        description="Category slug (e.g. 'cars', 'jobs') or raw numeric gateway category code (cg).",
    ),
]
ChototListingType = Literal["buy", "rent", "sell", "want_to_buy"]
ChototPropertyType = Literal["apartment", "house", "land", "office", "all"]

# Re-export known slugs for documentation and selfcheck references.
KNOWN_CATEGORIES = frozenset({
    "bds",
    "cars",
    "motorbikes",
    "electronics",
    "jobs",
    "home_goods",
    "home_appliances",
    "kitchen",
    "pets",
    "fashion",
    "services",
    "home_services",
})


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Chợ Tốt multi-category scraper tool."""

    @mcp.tool(
        name="nowing_chotot_scrape",
        title="Scrape Vietnamese listings from Chợ Tốt",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def chotot_scrape(
        category: ChototCategory,
        city: Annotated[
            str,
            Field(
                min_length=1,
                description="City name or slug, e.g. 'hanoi', 'ho chi minh', 'da nang'.",
            ),
        ],
        listing_type: Annotated[
            ChototListingType,
            Field(
                description="'buy'/'sell' for sale listings, 'rent' for lease, "
                "'want_to_buy' for wanted ads. Note: only 'bds' supports 'rent' "
                "on the gateway; other verticals fall back to 'sell'."
            ),
        ] = "buy",
        property_type: Annotated[
            ChototPropertyType,
            Field(
                description="BĐS-only sub-filter. Ignored for non-bds categories."
            ),
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
        """Scrape listings from Chợ Tốt (chotot.com, nhatot.com, xe.chotot.com,
        vieclamtot.com) across real estate, vehicles, jobs, electronics, goods,
        and services.

        Use this for Vietnamese marketplace research: tracking prices, supply,
        or locations. Returns typed listings with title, price, location, detail
        URL, and category-specific attributes.
        Category can be a known slug (e.g. 'cars', 'jobs') or a raw numeric
        gateway category code (cg). Example: category='cars',
        city='ho chi minh', listing_type='buy', max_items=20.
        """
        if (
            min_price is not None
            and max_price is not None
            and min_price > max_price
        ) or (min_area is not None and max_area is not None and min_area > max_area):
            raise ValueError("min value cannot exceed max value")
        return await run_scraper(
            client,
            context,
            platform="chotot",
            verb="scrape",
            payload={
                "category": category,
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
