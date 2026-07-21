# SurfSense MCP Server - Tool Contracts

**Ngày tạo:** 2026-07-21 16:49:13

## Tổng quan

MCP server expose các tools qua Model Context Protocol. Mỗi tool gọi backend SurfSense qua REST API.

## Search-space selector

- `surfsense_list_workspaces` – list workspaces có thể truy cập
- `surfsense_select_workspace` – chọn workspace active

## Scraper tools

- `surfsense_web_crawl`
- `surfsense_google_search`
- `surfsense_reddit_scrape`
- `surfsense_youtube_scrape`
- `surfsense_youtube_comments`
- `surfsense_instagram_scrape`
- `surfsense_instagram_details`
- `surfsense_tiktok_scrape`
- `surfsense_tiktok_comments`
- `surfsense_tiktok_user_search`
- `surfsense_tiktok_trending`
- `surfsense_google_maps_scrape`
- `surfsense_google_maps_reviews`
- `surfsense_list_scraper_runs`
- `surfsense_get_scraper_run`

## Knowledge base tools

- `surfsense_search_knowledge_base`
- `surfsense_list_documents`
- `surfsense_get_document`
- `surfsense_add_document`
- `surfsense_upload_file`
- `surfsense_update_document`
- `surfsense_delete_document`

## Transport

- **Hosted:** `https://mcp.surfsense.com/mcp` với header `Authorization: Bearer <API_KEY>`
- **Self-host (stdio):** `uv run --directory <path> python -m mcp_server`

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
