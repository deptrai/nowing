# Kiến trúc - Nowing MCP Server

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

MCP server Python expose các scrapers và knowledge base tools cho Claude, Cursor, và các MCP client khác.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Runtime | Python 3.11 |
| Framework | MCP SDK, Starlette, Uvicorn |
| HTTP client | httpx |
| Auth | Bearer token (NOWING_API_KEY) |

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

- Search-space selector: `nowing_list_workspaces`, `nowing_select_workspace`
- Scrapers: `nowing_web_crawl`, `nowing_google_search`, `nowing_reddit_scrape`, `nowing_youtube_scrape`, `nowing_instagram_scrape`, `nowing_tiktok_scrape`, `nowing_google_maps_scrape`, ...
- Knowledge base: `nowing_search_knowledge_base`, `nowing_list_documents`, `nowing_get_document`, `nowing_add_document`, `nowing_upload_file`, ...

## Entry point

`python -m mcp_server` hoặc `nowing-mcp` script.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
