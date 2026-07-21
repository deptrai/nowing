# Kiến trúc - SurfSense MCP Server

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

MCP server Python expose các scrapers và knowledge base tools cho Claude, Cursor, và các MCP client khác.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Runtime | Python 3.11 |
| Framework | MCP SDK, Starlette, Uvicorn |
| HTTP client | httpx |
| Auth | Bearer token (SURFSENSE_API_KEY) |

## Cấu trúc

| File/Thư mục | Mục đích |
|---|---|
| `mcp_server/__main__.py` | Entry chạy server |
| `mcp_server/server.py` | Server setup, tool registration |
| `mcp_server/core/client.py` | HTTP client gọi backend |
| `mcp_server/core/workspace_context.py` | Workspace selection context |
| `mcp_server/core/features/scrapers/` | Tool implementations cho scrapers |
| `mcp_server/core/features/knowledge_base/` | Tool implementations cho KB |
| `mcp_server/core/auth/` | Auth headers/identity middleware |

## Tools chính

- Search-space selector: `surfsense_list_workspaces`, `surfsense_select_workspace`
- Scrapers: `surfsense_web_crawl`, `surfsense_google_search`, `surfsense_reddit_scrape`, `surfsense_youtube_scrape`, `surfsense_instagram_scrape`, `surfsense_tiktok_scrape`, `surfsense_google_maps_scrape`, ...
- Knowledge base: `surfsense_search_knowledge_base`, `surfsense_list_documents`, `surfsense_get_document`, `surfsense_add_document`, `surfsense_upload_file`, ...

## Entry point

`python -m mcp_server` hoặc `surfsense-mcp` script.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
