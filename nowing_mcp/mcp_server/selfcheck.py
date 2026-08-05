"""Offline smoke check: every tool registers with a usable name, doc, and schema.

Runs without a backend or network — it only assembles the server and inspects
the tool manifest the client would see. Fails loudly if a tool is missing, its
description is too thin to route on, or its input schema is malformed.
"""

from __future__ import annotations

import asyncio
import sys

from .config import Settings
from .server import build_server

EXPECTED_TOOLS = {
    # search-space selector
    "nowing_list_workspaces",
    "nowing_select_workspace",
    # scrapers (all platforms) + run history
    "nowing_web_crawl",
    "nowing_google_search",
    "nowing_reddit_scrape",
    "nowing_youtube_scrape",
    "nowing_youtube_comments",
    "nowing_tiktok_scrape",
    "nowing_tiktok_comments",
    "nowing_tiktok_user_search",
    "nowing_tiktok_trending",
    "nowing_google_maps_scrape",
    "nowing_google_maps_reviews",
    "nowing_amazon_scrape",
    "nowing_batdongsan_scrape",
    "nowing_chotot_bds_scrape",
    "nowing_muaban_bds_scrape",
    "nowing_vn_bds_aggregate",
    "nowing_instagram_scrape",
    "nowing_instagram_details",
    "nowing_list_scraper_runs",
    "nowing_get_scraper_run",
    "nowing_chainlens_research",
    # knowledge-base management
    "nowing_search_knowledge_base",
    "nowing_list_documents",
    "nowing_get_document",
    "nowing_add_document",
    "nowing_upload_file",
    "nowing_update_document",
    "nowing_delete_document",
    # memory management
    "nowing_remember",
    "nowing_recall",
    "nowing_update_fact",
    "nowing_continue_research",
    "nowing_memory_list",
    "nowing_memory_revalidate",
    # workspace team memory
    "nowing_workspace_memory_get",
    "nowing_workspace_memory_update",
    # image generation
    "nowing_image_generate",
    # automations
    "nowing_automation_list",
    "nowing_automation_run",
    # reports
    "nowing_report_list",
    "nowing_report_export",
    # chat
    "nowing_chat",
}

_MIN_DESCRIPTION_CHARS = 40


async def _collect_tools() -> dict[str, object]:
    settings = Settings(
        base_url="http://localhost:8000",
        api_key="nw_pat_selfcheck",
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace=None,
        host="127.0.0.1",
        port=8080,
    )
    mcp, _client = build_server(settings)
    tools = await mcp.list_tools()
    return {tool.name: tool for tool in tools}


def run() -> list[str]:
    """Return a list of problems; empty means the manifest is healthy."""
    tools = asyncio.run(_collect_tools())
    problems: list[str] = []

    missing = EXPECTED_TOOLS - tools.keys()
    if missing:
        problems.append(f"missing tools: {sorted(missing)}")
    unexpected = tools.keys() - EXPECTED_TOOLS
    if unexpected:
        problems.append(f"unexpected tools: {sorted(unexpected)}")

    for name, tool in tools.items():
        description = tool.description or ""
        if len(description) < _MIN_DESCRIPTION_CHARS:
            problems.append(f"{name}: description too short to route on")
        schema = tool.inputSchema
        if not isinstance(schema, dict) or "properties" not in schema:
            problems.append(f"{name}: malformed input schema")
            continue
        for param, spec in schema["properties"].items():
            if not isinstance(spec, dict) or not spec.get("description"):
                problems.append(f"{name}: parameter '{param}' has no description")
    return problems


def main() -> None:
    problems = run()
    if problems:
        print("selfcheck FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)
    print(f"selfcheck OK: {len(EXPECTED_TOOLS)} tools registered and well-formed")


if __name__ == "__main__":
    main()
