"""Vietnam BĐS aggregate tool."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


ListingType = Literal["buy", "rent"]
PropertyType = Literal["apartment", "house", "land", "office", "all"]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Vietnam BĐS aggregate tool."""

    @mcp.tool(
        name="nowing_vn_bds_aggregate",
        title="Aggregate Vietnamese real-estate listings from multiple sources",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def vn_bds_aggregate(
        city: Annotated[
            str,
            Field(
                description="City name or Batdongsan code, e.g. 'Hà Nội', 'hanoi', 'HN', 'Ho Chi Minh'."
            ),
        ],
        listing_type: Annotated[
            ListingType,
            Field(description="'buy' for sale listings, 'rent' for lease listings."),
        ] = "buy",
        property_type: Annotated[
            PropertyType,
            Field(description="Property type filter across Chotot and Muaban."),
        ] = "all",
        sources: Annotated[
            list[str],
            Field(
                description="Sources to aggregate. Defaults to all: batdongsan, chotot_bds, muaban_bds."
            ),
        ] = None,
        district: Annotated[
            str | None,
            Field(description="Optional district name/slug for Chotot and Muaban."),
        ] = None,
        district_id: Annotated[
            int | None,
            Field(description="Optional district ID for Batdongsan."),
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
        max_items_per_source: Annotated[
            int,
            Field(ge=0, le=100, description="Maximum listings to fetch per source."),
        ] = 10,
        max_pages: Annotated[
            int,
            Field(ge=0, le=20, description="Maximum pages to fetch per source."),
        ] = 5,
        min_confidence: Annotated[
            float,
            Field(ge=0.0, le=1.0, description="Drop listings below this confidence score."),
        ] = 0.0,
        resolve_phones: Annotated[
            bool,
            Field(
                description="Open Batdongsan detail pages to resolve full phone numbers (slower)."
            ),
        ] = True,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Merge and score BĐS listings from batdongsan, chotot_bds, and muaban_bds.

        Use this to compare price, area, phone, and location across sources and
        spot fake/duplicate listings. Returns deduplicated listings with a
        cross-source confidence score and price-conflict flags.
        Example: city='Hà Nội', listing_type='buy', max_items_per_source=10.
        """
        payload: dict[str, Any] = {
            "city": city,
            "listing_type": listing_type,
            "property_type": property_type,
            "district": district,
            "district_id": district_id,
            "min_price": min_price,
            "max_price": max_price,
            "min_area": min_area,
            "max_area": max_area,
            "max_items_per_source": max_items_per_source,
            "max_pages": max_pages,
            "min_confidence": min_confidence,
            "resolve_phones": resolve_phones,
        }
        if sources:
            payload["sources"] = sources

        return await run_scraper(
            client,
            context,
            platform="vn_bds",
            verb="aggregate",
            payload=payload,
            workspace=workspace,
            response_format=response_format,
        )
