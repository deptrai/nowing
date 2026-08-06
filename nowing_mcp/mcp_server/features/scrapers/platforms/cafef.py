"""CafeF stock/financials/news scraper tool."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the CafeF scraper tool."""

    @mcp.tool(
        name="nowing_cafef_scrape",
        title="Scrape CafeF stock quotes, financials and news",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def cafef_scrape(
        symbol: Annotated[
            str,
            Field(
                description="Vietnamese stock symbol, e.g. VCB, FPT, HPG.",
                min_length=1,
                max_length=20,
            ),
        ],
        include_financials: Annotated[
            bool,
            Field(description="Include balance sheet, income statement and cash flow."),
        ] = True,
        include_news: Annotated[
            bool,
            Field(description="Include latest market news for the symbol."),
        ] = False,
        max_news: Annotated[
            int,
            Field(
                ge=0,
                le=50,
                description="Maximum news articles to return.",
            ),
        ] = 10,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape CafeF data for a Vietnamese stock.

        Returns current price, OHLCV, key ratios, and (when requested)
        financial statements and market news. Example: symbol='VCB'.
        """
        return await run_scraper(
            client,
            context,
            platform="cafef",
            verb="scrape",
            payload={
                "symbol": symbol,
                "include_financials": include_financials,
                "include_news": include_news,
                "max_news": max_news,
            },
            workspace=workspace,
            response_format=response_format,
        )
