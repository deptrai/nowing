"""Canonical catalog of built-in MCP tools exposed by the Nowing MCP server.

This module is the single source of truth for tool names and groups used by:
- the backend API that returns per-workspace tool settings,
- the web UI that renders toggles,
- and (indirectly) the MCP server's own tool manifest.

Keep it alphabetized by tool name for stable diffs.
"""

from __future__ import annotations

from enum import StrEnum


class McpToolGroup(StrEnum):
    WORKSPACE = "workspace"
    SCRAPER = "scraper"
    RUN_HISTORY = "run_history"
    KNOWLEDGE_BASE = "knowledge_base"
    MEMORY = "memory"
    TEAM_MEMORY = "team_memory"
    IMAGE_GENERATION = "image_generation"
    AUTOMATION = "automation"
    REPORT = "report"
    CHAT = "chat"


MCP_TOOL_CATALOG: list[dict[str, str]] = [
    {"name": "nowing_list_workspaces", "group": McpToolGroup.WORKSPACE},
    {"name": "nowing_select_workspace", "group": McpToolGroup.WORKSPACE},
    {"name": "nowing_amazon_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_batdongsan_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_chotot_bds_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_muaban_bds_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_vietnamworks_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_topcv_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_itviec_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_masothue_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_vn_jobs_aggregate", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_chainlens_research", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_maps_reviews", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_maps_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_search", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_instagram_details", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_instagram_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_reddit_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_comments", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_trending", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_user_search", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_vn_bds_aggregate", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_web_crawl", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_youtube_comments", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_youtube_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_get_scraper_run", "group": McpToolGroup.RUN_HISTORY},
    {"name": "nowing_list_scraper_runs", "group": McpToolGroup.RUN_HISTORY},
    {"name": "nowing_add_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_delete_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_get_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_list_documents", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_search_knowledge_base", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_update_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_upload_file", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_remember", "group": McpToolGroup.MEMORY},
    {"name": "nowing_recall", "group": McpToolGroup.MEMORY},
    {"name": "nowing_update_fact", "group": McpToolGroup.MEMORY},
    {"name": "nowing_continue_research", "group": McpToolGroup.MEMORY},
    {"name": "nowing_memory_list", "group": McpToolGroup.MEMORY},
    {"name": "nowing_memory_revalidate", "group": McpToolGroup.MEMORY},
    {"name": "nowing_workspace_memory_get", "group": McpToolGroup.TEAM_MEMORY},
    {"name": "nowing_workspace_memory_update", "group": McpToolGroup.TEAM_MEMORY},
    {"name": "nowing_image_generate", "group": McpToolGroup.IMAGE_GENERATION},
    {"name": "nowing_automation_list", "group": McpToolGroup.AUTOMATION},
    {"name": "nowing_automation_run", "group": McpToolGroup.AUTOMATION},
    {"name": "nowing_report_list", "group": McpToolGroup.REPORT},
    {"name": "nowing_report_export", "group": McpToolGroup.REPORT},
    {"name": "nowing_chat", "group": McpToolGroup.CHAT},
]

MCP_TOOL_SYSTEM_TOOLS = {"nowing_list_workspaces", "nowing_select_workspace"}
MCP_TOOL_NAMES = {t["name"] for t in MCP_TOOL_CATALOG}
MCP_TOOL_GROUP_MAP: dict[str, str] = {t["name"]: t["group"] for t in MCP_TOOL_CATALOG}
