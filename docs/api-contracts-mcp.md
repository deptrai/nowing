# Nowing MCP Server - Tool Contracts

**Ngày tạo:** 2026-07-21 16:49:13

## Tổng quan

MCP server expose các tools qua Model Context Protocol. Mỗi tool gọi backend Nowing qua REST API.

## Search-space selector

- `nowing_list_workspaces` – list workspaces có thể truy cập
- `nowing_select_workspace` – chọn workspace active

## Scraper tools

- `nowing_web_crawl`
- `nowing_google_search`
- `nowing_reddit_scrape`
- `nowing_youtube_scrape`
- `nowing_youtube_comments`
- `nowing_instagram_scrape`
- `nowing_instagram_details`
- `nowing_tiktok_scrape`
- `nowing_tiktok_comments`
- `nowing_tiktok_user_search`
- `nowing_tiktok_trending`
- `nowing_google_maps_scrape`
- `nowing_google_maps_reviews`
- `nowing_list_scraper_runs`
- `nowing_get_scraper_run`

## Knowledge base tools

- `nowing_search_knowledge_base`
- `nowing_list_documents`
- `nowing_get_document`
- `nowing_add_document`
- `nowing_upload_file`
- `nowing_update_document`
- `nowing_delete_document`

## Transport

- **Hosted:** `https://mcp.nowing.com/mcp` với header `Authorization: Bearer <API_KEY>`
- **Self-host (stdio):** `uv run --directory <path> python -m mcp_server`

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
