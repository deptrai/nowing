"""Vietstock stock/financials scraper tool."""

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
    """Register the Vietstock scraper tool."""

    @mcp.tool(
        name="nowing_vietstock_scrape",
        title="Scrape Vietstock stock quotes and financials",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def vietstock_scrape(
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
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape Vietstock data for a Vietnamese stock.

        Returns current price, OHLCV, key ratios, and (when requested)
        financial statements. Example: symbol='VCB'.
        """
        return await run_scraper(
            client,
            context,
            platform="vietstock",
            verb="scrape",
            payload={
                "symbol": symbol,
                "include_financials": include_financials,
            },
            workspace=workspace,
            response_format=response_format,
        )
