"""Walmart product and reviews scraper tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Walmart product and review tools."""

    @mcp.tool(
        name="nowing_walmart_scrape",
        title="Scrape Walmart products",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def walmart_scrape(
        keyword: Annotated[
            str | None,
            Field(description="Search keyword, e.g. 'wireless earbuds'. Provide keyword OR url."),
        ] = None,
        url: Annotated[
            str | None,
            Field(description="Walmart product page URL containing /ip/ or /dp/. Provide keyword OR url."),
        ] = None,
        page: Annotated[
            int,
            Field(ge=1, description="Search result page to start from."),
        ] = 1,
        max_items: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum product results to return."),
        ] = 50,
        max_reviews: Annotated[
            int,
            Field(ge=0, description="Maximum review summary items to attach per product page."),
        ] = 5,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search Walmart product listings or fetch a product detail page.

        Returns title, price, rating, seller, availability, image, and a short
        review summary. Use keyword to discover products or url to target a
        specific product page.
        Example: keyword='mechanical keyboard', max_items=5.
        Example: url='https://www.walmart.com/ip/Great-Value-Milk-Gallon/123456789'.
        """
        payload: dict[str, Any] = {
            "keyword": keyword,
            "url": url,
            "page": page,
            "max_items": max_items,
            "max_reviews": max_reviews,
        }
        return await run_scraper(
            client,
            context,
            platform="walmart",
            verb="scrape",
            payload=payload,
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="nowing_walmart_reviews",
        title="Fetch Walmart product reviews",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def walmart_reviews(
        url: Annotated[
            str,
            Field(description="Walmart product page URL containing /ip/ or /dp/."),
        ],
        max_reviews: Annotated[
            int,
            Field(ge=1, le=1000, description="Maximum reviews to return."),
        ] = 100,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch paginated customer reviews for a Walmart product.

        Returns review text, rating, date, and verified status. Pass a product
        page URL from nowing_walmart_scrape.
        Example: url='https://www.walmart.com/ip/Great-Value-Milk-Gallon/123456789', max_reviews=20.
        """
        payload: dict[str, Any] = {
            "url": url,
            "max_reviews": max_reviews,
        }
        return await run_scraper(
            client,
            context,
            platform="walmart",
            verb="reviews",
            payload=payload,
            workspace=workspace,
            response_format=response_format,
        )
