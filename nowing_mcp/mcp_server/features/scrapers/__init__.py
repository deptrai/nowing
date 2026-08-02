"""Scraper tools: one MCP surface per Nowing platform capability.

Web crawl, Google Search, Reddit, YouTube, and Google Maps each get a tool that
maps a natural-language request to the workspace's scraper. Two run-history tools
list and fetch past runs, so a large result truncated inline can be retrieved in
full later. Each platform lives in its own module under platforms/.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ...core.client import NowingClient
from ...core.workspace_context import WorkspaceContext
from . import run_history
from .platforms import (
    amazon,
    batdongsan,
    chainlens,
    google_maps,
    google_search,
    instagram,
    reddit,
    tiktok,
    web,
    youtube,
)

_REGISTRARS = (
    web,
    google_search,
    reddit,
    youtube,
    instagram,
    tiktok,
    google_maps,
    amazon,
    chainlens,
    batdongsan,
    run_history,
)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register every scraper and run-history tool on the server."""
    for module in _REGISTRARS:
        module.register(mcp, client, context)
