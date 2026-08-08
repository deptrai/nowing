---
baseline_commit: 9f6a4c594
story_key: 7-7-mcp-server-tool-expansion
status: review
---

# Story 7.7 — MCP Server Tool Expansion

**Story ID:** 7.7
**Epic:** Epic 7 — Multi-surface Clients
**Title:** MCP Server Tool Expansion
**Status:** review
**Priority:** P1
**Source artifacts:**
- PRD: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (FR-29, FR-21, FR-22, FR-23, FR-18/19/20, FR-32/33/34)
- Epics: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md` (Epic 7 — Story 7.6 MCP server `[done]`)
- Architecture: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-7)
- Previous story: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/4-5-agent-memory-tools-via-mcp.md`
- MCP tool-toggle pattern: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/2-5-workspace-mcp-tool-toggle.md`

---

## 1. Goal

Mở rộng MCP server của Nowing (`nowing_mcp`) từ bộ tool lõi (scrapers, knowledge base, 4 memory tool) thành bề mặt đầy đủ phủ các capability backend đã build: **memory list/revalidate**, **workspace team memory**, **image generation**, **2 nền tảng BĐS bổ sung (chotot, muaban)**, **automations list**, **reports list + export đa định dạng**, và sau đó **chat** + **automation run**.

Story này đóng vai trò **backfill** — Slice 0–3 đã được implement và verify trước khi story file tồn tại (ad-hoc quick-dev, không đi qua bmad gates). Story file này ghi nhận scope đầy đủ: các task đã xong được đánh `[x]` kèm evidence verify; Slice 4–5 (chat, automation run) còn pending sẽ được `bmad-dev-story` triển khai tiếp theo quy trình bắt buộc.

Đây là **MCP server của Nowing** (FR-29 — Nowing expose bề mặt tools cho clients AI như Claude/Cursor/OpenCode), **KHÔNG phải** FR-8 "External MCP Connectors" (Nowing tiêu thụ MCP của third-party) — khác hướng, nằm ngoài scope.

---

## 2. User Story & Acceptance Criteria

> As an AI agent builder,
> I want to drive Nowing's full backend surface — memory, team memory, image generation, BĐS platforms, automations, reports — through Nowing's own MCP server,
> So that agents can operate the research workspace end-to-end without the web UI.

### AC-1: Memory list & revalidate tools  `[x] DONE — verified`
**Given** MCP server đã đăng ký `features/memory`
**When** agent gọi `nowing_memory_list(limit, type, tags, workspace)` với workspace active
**Then** tool gọi `GET /workspaces/{id}/memories` và render danh sách memory mới nhất trước, có id/type/tags/confidence/content excerpt
**And** khi gọi `nowing_memory_revalidate(memory_id, workspace)` thì tool gọi `POST /workspaces/{id}/memories/{memory_id}/revalidate` và render memory đã refresh, giữ previous versions.

### AC-2: Workspace team-memory tools  `[x] DONE — verified`
**Given** workspace có team memory
**When** agent gọi `nowing_workspace_memory_get(workspace)`
**Then** tool gọi `GET /workspaces/{id}/memory` và render nội dung team memory (hoặc hướng dẫn tạo nếu chưa có)
**And** khi gọi `nowing_workspace_memory_update(workspace, content)` thì tool gọi `PUT /workspaces/{id}/memory`.

### AC-3: Image generation tool  `[x] DONE — verified`
**Given** agent muốn tạo image từ workspace
**When** agent gọi `nowing_image_generate(prompt, ...)`
**Then** tool gọi `POST /image-generations` và trả về generation id / status / download.

### AC-4: BĐS platform tools (chotot, muaban)  `[x] DONE — verified`
**Given** MCP server đã đăng ký `features/scrapers/platforms/chotot_bds` + `muaban_bds`
**When** agent gọi `nowing_chotot_bds_scrape` hoặc `nowing_muaban_bds_scrape` với `city`
**Then** tool chạy qua `run_scraper` capability chung và trả listings typed như các nền tảng BĐS hiện có
**And** `nowing_vn_bds_aggregate` vẫn hoạt động (3 nguồn BĐS: batdongsan, chotot, muaban).

### AC-5: Automation list tool  `[x] DONE — verified`
**Given** agent muốn xem automations của workspace
**When** agent gọi `nowing_automation_list(limit, offset, workspace)`
**Then** tool gọi `GET /automations` và render danh sách automation (name, trigger type, status, next run).

### AC-6: Report list + export tools  `[x] DONE — verified`
**Given** workspace có reports
**When** agent gọi `nowing_report_list(limit, offset)` 
**Then** tool gọi `GET /reports` và render danh sách report.
**And** khi gọi `nowing_report_export(report_id, format)` với `format ∈ {pdf, docx, html, latex, epub, odt, plain}`:
**Then** tool gọi `GET /reports/{id}/export?format=...` qua `NowingClient.request_bytes()`; text formats (html/latex/plain) decode utf-8 trả trực tiếp, binary formats (pdf/docx/epub/odt) trả base64 kèm hint giải mã.

### AC-7: Backend catalog + selfcheck sync  `[x] DONE — verified`
**Given** `app/mcp_tools.py` chứa `MCP_TOOL_CATALOG` và `McpToolGroup`
**When** 11 tool mới được thêm vào MCP server
**Then** catalog bổ sung groups `TEAM_MEMORY`/`IMAGE_GENERATION`/`AUTOMATION`/`REPORT` + entries cho 8 tool mới (memory_list, memory_revalidate, workspace_memory_get/update, image_generate, automation_list, report_list, report_export)
**And** `selfcheck.py EXPECTED_TOOLS` = 42 tool; `uv run python -m mcp_server.selfcheck` in `selfcheck OK: 42 tools registered and well-formed`
**And** `/workspaces/{id}/mcp-tools` (backend) tự phản ánh vì iterate `MCP_TOOL_CATALOG`.

### AC-8: Chat tool  `[x] DONE — verified`
**Given** backend new-chat SSE flow (`flows/new_chat/orchestrator.py`) đã sẵn
**When** agent gọi `nowing_chat(...)`
**Then** tool buffered toàn bộ SSE stream rồi trả câu trả lời hoàn chỉnh (Hướng A), kèm mode support (speed/balanced/quality/auto).
_Verified: `nowing_chat` buffered `text-delta` theo id, tự tạo thread khi thiếu `chat_id`, retry `THREAD_BUSY` (max 4, cap 30s), trả `_(chat_turn: <id>)_`; 10 tests MCP pass._

### AC-9: Automation run tool  `[x] DONE — verified`
**Given** backend có cơ chế chạy automation theo yêu cầu (mirror Telegram `/run`)
**When** agent gọi `nowing_automation_run(automation_id, ...)`
**Then** tool kích hoạt `POST /automations/{id}/run` và trả về run id / status.
_Verified: backend `RunService.launch` (thin wrapper `launch_run` + `TriggerType.MANUAL`, check `automations:execute`), endpoint trả `RunSummary` PENDING fire-and-return; 6 unit + 4 integration backend tests pass._

---

## 3. Technical Context

### 3.1 MCP server pattern (đã có — Story 7.6, AD-7)
- `nowing_mcp/mcp_server/server.py` — `WorkspaceAwareFastMCP` (stateless HTTP, filter manifest per workspace), `build_server()` register từng feature module qua contract `register(mcp, client, context)`.
- Mỗi feature module: `features/<name>/__init__.py` (định nghĩa tool qua `@mcp.tool`) + `features/<name>/annotations.py` (policy hints `ToolAnnotations`: READ/WRITE/DESTRUCTIVE).
- Params dùng chung: `WorkspaceParam`, `ResponseFormatParam` (`markdown`/`json`), `MemoryType`, `MemoryTags`, `MemoryId` (từ `features/memory/annotations.py`).
- `NowingClient` (`core/client.py`) — wrapper HTTP gọi backend với API key; `request()` (JSON) và `request_bytes()` (MỚI — trả `(bytes, content_type)` cho binary export).

### 3.2 Backend endpoints đã có (Story 3.8, 7.6, automations/reports/deliverables)
- Memory: `POST /workspaces/{id}/memories`, `POST /workspaces/{id}/memories/search`, `PATCH /memories/{id}`, `POST /workspaces/{id}/memories/{id}/revalidate`. MỚI: `GET /workspaces/{id}/memories` (list, `limit` 1–100, `type`, `tags` CSV).
- Team memory: `GET/PUT /workspaces/{id}/memory`.
- Image generation: `POST /image-generations`.
- Automations: `GET /automations`, `GET /automations/{id}`.
- Reports: `GET /reports`, `GET /reports/{id}/export?format=`.
- Catalog: `GET /workspaces/{id}/mcp-tools` (iterate `MCP_TOOL_CATALOG`).

### 3.3 RBAC
- Route mới `GET /workspaces/{id}/memories` check `Permission.MEMORY_READ`.
- Tool server chỉ thổi backend error (403 PAT thiếu membership) lên cho client.

---

## 4. Scope

### In scope
- MCP tools mới: `nowing_memory_list`, `nowing_memory_revalidate`, `nowing_workspace_memory_get`, `nowing_workspace_memory_update`, `nowing_image_generate`, `nowing_chotot_bds_scrape`, `nowing_muaban_bds_scrape`, `nowing_automation_list`, `nowing_report_list`, `nowing_report_export` (10 tool — Slice 0–3, **DONE + verified**).
- Backend: `MemoryRepository.list_memories` + route `GET /workspaces/{id}/memories`; catalog groups + entries; `selfcheck` = 42.
- `NowingClient.request_bytes()` cho binary export.
- **Pending (Slice 4–5):** `nowing_chat`, `nowing_automation_run`.

### Out of scope
- FR-8 "External MCP Connectors" — Nowing tiêu thụ MCP của third-party (hướng ngược lại).
- Các scraper platform khác ngoài chotot/muaban; podcast/video presentation deliverable tools (chỉ report export).
- `nowing_automation_get` — đã cân nhắc, bỏ để giữ đúng scope (chỉ list; detail qua list hoặc backend).
- API contract docs (`docs/api-contracts-*.md`) — chỉ update nếu được duy trì.

---

## 5. Implementation Plan

### Slice 0 — Infra: catalog sync + teams + image gen  `[x] DONE + verified`
- `app/mcp_tools.py`: thêm `McpToolGroup.TEAM_MEMORY`/`IMAGE_GENERATION` + entries `nowing_workspace_memory_get/update`, `nowing_image_generate`.
- `features/team_memory/` (`nowing_workspace_memory_get`, `nowing_workspace_memory_update` → `GET/PUT /workspaces/{id}/memory`) + `annotations.py` (READ, DESTRUCTIVE).
- `features/image_generation/` (`nowing_image_generate` → `POST /image-generations`) + `annotations.py` (WRITE).

### Slice 1 — Memory list + revalidate  `[x] DONE + verified`
- `features/memory/__init__.py`: thêm `nowing_memory_list`, `nowing_memory_revalidate`.
- Backend `MemoryRepository.list_memories` + route `GET /workspaces/{id}/memories` (`limit`, `type`, `tags` CSV → `tags &&` array overlap; `selectinload(Memory.versions)`; order newest-first).

### Slice 2 — BĐS scraper platforms (chotot, muaban)  `[x] DONE + verified`
- `features/scrapers/platforms/chotot_bds.py`, `muaban_bds.py` — sử dụng `run_scraper` capability chung.
- Register trong `features/scrapers/__init__.py` (`_REGISTRARS`).
- Selfcheck bổ sung `nowing_chotot_bds_scrape`, `nowing_muaban_bds_scrape` (+ `nowing_vn_bds_aggregate` sync).

### Slice 3 — Automations + Reports  `[x] DONE + verified`
- `features/automations/` (`nowing_automation_list` → `GET /automations`, limit/offset) + `annotations.py` (READ).
- `features/reports/` (`nowing_report_list` → `GET /reports`; `nowing_report_export` → `GET /reports/{id}/export` qua `request_bytes`; text vs binary; base64 + hint) + `annotations.py` (READ).
- `core/client.py`: thêm `NowingClient.request_bytes()` → `(response.content, content_type)`.
- Catalog: groups `AUTOMATION`/`REPORT` + 4 entries; selfcheck = 42.

### Slice 4 — Chat tool  `[x] DONE + verified`
- `core/sse.py` (`SseEvent` + `iter_sse_events`, port từ evals) + `core/errors.py` `ThreadBusyError` (`error_code` THREAD_BUSY/TURN_CANCELLING).
- `core/client.py`: `stream_sse(method, path, *, json, timeout_s=600)` — async generator, `Accept: text/event-stream`, 409 → `ThreadBusyError`, non-2xx → `ToolError`, `RequestError` → readable unreachable message.
- `features/chat/` với `nowing_chat(user_query, chat_id?, mode?, workspace, response_format)` — Hướng A: SSE buffered; `_ask_turn` busy-retry + `_consume_once` gom `text-delta` theo id + capture `chat_turn_id`; tự tạo thread khi không có `chat_id`.

### Slice 5 — Automation run tool  `[x] DONE + verified`
- Backend `RunService.launch` (`app/automations/services/run.py`): check `Permission.AUTOMATIONS_EXECUTE`, build transient `AutomationTrigger(type=MANUAL, params={}, static_inputs={})`, gọi `launch_run(runtime_inputs={"fired_by": "mcp"})`; `DispatchError` → 404 ("not found") / 400 (khác).
- Backend route `POST /automations/{id}/run` (`app/automations/api/run.py`) — `RunSummary`, fire-and-return (trả `pending`).
- `features/automations/` thêm `nowing_automation_run(automation_id ge=1, workspace, response_format)` — POST `/automations/{id}/run` với body `{"workspace_id": ...}`; markdown "Run started: **#{run_id}**..."; json `{"run_id", "status"}`; wrap ToolError readable. Annotations `WRITE`.
- Sync: `selfcheck.py` EXPECTED_TOOLS = 44, backend catalog + `nowing_automation_run` + `nowing_chat` (group `CHAT`).

### Slice 6 — Verification (mọi slice)  `[x] DONE + verified`
- `uv run python -m mcp_server.selfcheck` trong `nowing_mcp` → `selfcheck OK: 44 tools`.
- `uv run python -m pytest nowing_mcp/tests -q` → **103 passed** (gồm cả `test_research_continuity.py`).
- Backend: `tests/unit/automations/services/test_run_service_launch.py` (6) + `tests/integration/automations/api/test_run_endpoint.py` (4) pass; full `tests/unit/automations/` 276 pass.
- `ruff check` trên file thay đổi (dùng `/Users/luisphan/.agent-reach-venv/bin/ruff` — `uv run ruff` trigger env build >120s timeout).

---

## 6. API Contract

### Backend REST endpoints (mới)
`GET /workspaces/{workspace_id}/memories`
```
limit (query, int, default 20, ge 1, le 100)
type (query, str|None — semantic|episodic|procedural|working)
tags (query, str|None — CSV → array overlap)
```
Trả `list[MemoryRead]` 200, newest-first (`created_at desc, id desc`). Check `Permission.MEMORY_READ`.

### MCP tool schemas (mới)

`nowing_memory_list`
```
limit (int, default 20, ge 1 le 100)
type (MemoryType, optional)
tags (list[str], optional)
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_memory_revalidate`
```
memory_id (int, required)
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_workspace_memory_get`
```
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_workspace_memory_update`
```
content (str, required)
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_image_generate`
```
prompt (str, required, min 1 max 4000)
n (int, optional, 1-10)
size (str, optional, e.g. '1024x1024')
quality (str, optional, 'standard'|'hd')
style (str, optional, 'vivid'|'natural')
model (str, optional, e.g. 'gpt-image-1')
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_chotot_bds_scrape` / `nowing_muaban_bds_scrape`
```
city (str, required) — giống batdongsan: HN, SG, ...
listing_type (buy|rent, default buy)
district_id (int, optional)
min_price / max_price / min_area / max_area (int, optional)
max_pages (int, default 5) / max_items (int, default 10)
```

`nowing_automation_list`
```
limit (int, default 50, ge 1 le 200)
offset (int, default 0, ge 0)
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_report_list`
```
limit (int, default 20, ge 1 le 100)
workspace (str|int, optional)
response_format (markdown|json, default markdown)
```

`nowing_report_export`
```
report_id (int, required)
format (ExportFormat: pdf|docx|html|latex|epub|odt|plain, default pdf)
```

---

## 7. Files to Create / Modify

### Create
- `nowing_mcp/mcp_server/features/team_memory/__init__.py` + `annotations.py`
- `nowing_mcp/mcp_server/features/image_generation/__init__.py` + `annotations.py`
- `nowing_mcp/mcp_server/features/automations/__init__.py` + `annotations.py`
- `nowing_mcp/mcp_server/features/reports/__init__.py` + `annotations.py`
- `nowing_mcp/mcp_server/features/chat/__init__.py` + `annotations.py`  `[x] Slice 4`
- `nowing_mcp/mcp_server/core/sse.py`  `[x] Slice 4`
- `nowing_mcp/mcp_server/features/scrapers/platforms/chotot_bds.py`
- `nowing_mcp/mcp_server/features/scrapers/platforms/muaban_bds.py`
- `nowing_mcp/tests/test_team_memory_tools.py`
- `nowing_mcp/tests/test_image_generation_tools.py`
- `nowing_mcp/tests/test_memory_slice2_tools.py`
- `nowing_mcp/tests/test_automation_report_tools.py`
- `nowing_mcp/tests/test_chat_tool.py`  `[x] Slice 4`
- `nowing_backend/tests/unit/automations/services/test_run_service_launch.py`  `[x] Slice 5`
- `nowing_backend/tests/integration/automations/api/test_run_endpoint.py`  `[x] Slice 5`

### Modify
- `nowing_mcp/mcp_server/core/client.py` — `request_bytes()` + `stream_sse()`  `[x]`
- `nowing_mcp/mcp_server/core/errors.py` — `ThreadBusyError`  `[x] Slice 4`
- `nowing_mcp/mcp_server/features/memory/__init__.py` — thêm `memory_list`, `memory_revalidate`
- `nowing_mcp/mcp_server/features/scrapers/__init__.py` — register chotot_bds, muaban_bds
- `nowing_mcp/mcp_server/features/automations/__init__.py` — thêm `nowing_automation_run` + annotations WRITE  `[x] Slice 5`
- `nowing_mcp/mcp_server/server.py` — register `team_memory`, `image_generation`, `automations`, `reports`, `chat`
- `nowing_mcp/mcp_server/selfcheck.py` — `EXPECTED_TOOLS` = 44
- `nowing_backend/app/mcp_tools.py` — groups `TEAM_MEMORY`/`IMAGE_GENERATION`/`AUTOMATION`/`REPORT`/`CHAT` + 10 entries
- `nowing_backend/app/services/memory/repository.py` — `list_memories`
- `nowing_backend/app/routes/memories_routes.py` — route `GET /workspaces/{id}/memories`
- `nowing_backend/app/automations/services/run.py` — `RunService.launch`  `[x] Slice 5`
- `nowing_backend/app/automations/api/run.py` — `POST /automations/{id}/run`  `[x] Slice 5`

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Binary report export vỡ khi truyền qua tool | `request_bytes()` lấy `response.content` thô; binary base64-encode kèm hint `echo <payload> | base64 -d > report.<ext>` |
| Catalog vs selfcheck drift | `test_mcp_tool_filter.py::test_backend_catalog_matches_selfcheck` assert `MCP_TOOL_NAMES == EXPECTED_TOOLS` |
| Scraper platform thêm mới đổi schema response | Dùng `run_scraper` chung → response shape chuẩn như batdongsan |
| PAT thiếu workspace membership | Route check `check_permission` → 403; MCP server surface backend error |
| `memory_revalidate` 422 (RevalidationError) | Route bọc HTTPException 422 code/message; tool render rõ |
| `uv run ruff` timeout (env build) | Dùng binary standalone `/Users/luisphan/.agent-reach-venv/bin/ruff` |

---

## 9. Definition of Done

- [x] 12 tool mới register + `selfcheck` pass (44 tools).
- [x] `nowing_memory_list` list memory newest-first; `nowing_memory_revalidate` refresh + giữ versions.
- [x] `nowing_workspace_memory_get/update` đọc/ghi team memory workspace.
- [x] `nowing_image_generate` gọi `POST /image-generations`.
- [x] `nowing_chotot_bds_scrape` / `nowing_muaban_bds_scrape` chạy qua `run_scraper`.
- [x] `nowing_automation_list` gọi `GET /automations`.
- [x] `nowing_report_list` + `nowing_report_export` (7 formats; text decoded, binary base64 + hint).
- [x] Backend catalog: 5 groups + 10 entries; route list memories + `MemoryRepository.list_memories`.
- [x] MCP suite xanh: **103 passed**; ruff clean.
- [x] Slice 4 — `nowing_chat` (SSE buffered, mode support, thread auto-create, busy retry).
- [x] Slice 5 — `nowing_automation_run` (+ backend `POST /automations/{id}/run` + `RunService.launch`).
- [x] Selfcheck = 44 tools; catalog sync qua `test_backend_catalog_matches_selfcheck`.

---

## 10. Tasks / Subtasks

### Backend
- [x] `MemoryRepository.list_memories` (filters type/tags, selectinload versions, newest-first)
- [x] Route `GET /workspaces/{id}/memories` + `Permission.MEMORY_READ`
- [x] `app/mcp_tools.py`: groups `TEAM_MEMORY`/`IMAGE_GENERATION`/`AUTOMATION`/`REPORT`/`CHAT` + 10 entries
- [x] `RunService.launch` — check `automations:execute`, transient MANUAL trigger, `launch_run(runtime_inputs={"fired_by": "mcp"})`, `DispatchError` → 404/400  `[x] Slice 5`
- [x] Route `POST /automations/{id}/run` — `RunSummary`, fire-and-return  `[x] Slice 5`

### MCP features
- [x] `core/client.py`: `request_bytes()` + `stream_sse()`
- [x] `core/sse.py` — `SseEvent` + `iter_sse_events` (port từ evals)  `[x] Slice 4`
- [x] `core/errors.py` — `ThreadBusyError` (`error_code` THREAD_BUSY/TURN_CANCELLING)  `[x] Slice 4`
- [x] `features/team_memory/` — `nowing_workspace_memory_get/update` + annotations
- [x] `features/image_generation/` — `nowing_image_generate` + annotations
- [x] `features/memory/` — `nowing_memory_list`, `nowing_memory_revalidate`
- [x] `features/scrapers/platforms/chotot_bds.py` + `muaban_bds.py`; register trong `scrapers/__init__.py`
- [x] `features/automations/` — `nowing_automation_list` + `nowing_automation_run` + annotations
- [x] `features/chat/` — `nowing_chat` (SSE buffered, thread auto-create, busy retry)  `[x] Slice 4`
- [x] `features/reports/` — `nowing_report_list`, `nowing_report_export` + annotations
- [x] `server.py`: register 5 feature mới
- [x] `selfcheck.py`: `EXPECTED_TOOLS` = 44

### Tests
- [x] `tests/test_team_memory_tools.py`
- [x] `tests/test_image_generation_tools.py`
- [x] `tests/test_memory_slice2_tools.py`
- [x] `tests/test_automation_report_tools.py` (gồm base64 binary export test + `nowing_automation_run`)
- [x] `tests/test_chat_tool.py` (10 tests — buffering, thread create, busy retry, mode, json format)  `[x] Slice 4`
- [x] `nowing_backend/tests/unit/automations/services/test_run_service_launch.py` (6 tests)  `[x] Slice 5`
- [x] `nowing_backend/tests/integration/automations/api/test_run_endpoint.py` (4 tests, real Postgres)  `[x] Slice 5`

### Verification
- [x] `uv run python -m mcp_server.selfcheck` → `selfcheck OK: 44 tools`
- [x] `uv run python -m pytest nowing_mcp/tests -q` → 103 passed
- [x] Backend pytest: unit automations 276 passed; run service launch 6 passed; run endpoint integration 4 passed
- [x] `ruff check` clean (standalone binary)

### Pending (Slice 4–5)
- [x] `features/chat/` — `nowing_chat` (SSE buffered, mode support) — **DONE**
- [x] `features/automations/` — `nowing_automation_run` + backend `POST /automations/{id}/run` — **DONE**

---

## 10.1 Review Findings (code review 2026-08-05)

3 review layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) ran inline (no subagents). After verification, all 3 candidate patches were reclassified as false positives.

### Dismissed (5 — false positive / out of scope)
- [x] [Review][Dismiss] `stream_sse` 409 busy-detail read "deadlock on empty body" — httpx memoizes `_content` after `aread()`; `response.text` returns cached bytes. Safe.
- [x] [Review][Dismiss] `_extract_busy_detail` fallback to `response.text` after `aread()` — same caching; no double-consume error.
- [x] [Review][Dismiss] retry count off-by-one vs AC-8 "max 4 retries" — verified: `attempt > 4` raises on attempt 5 = exactly 4 retries. Matches spec.
- [x] [Review][Dismiss] `request_bytes` unused by slices 4–5 — belongs to reports story (shared working tree).
- [x] [Review][Dismiss] Mixed working-tree lines in `selfcheck.py`/`mcp_tools.py`/`client.py` — other stories' uncommitted changes, not 7.7.

### Deferred (5 — pre-existing / out of scope, written to deferred-work.md)
- [x] [Review][Defer] Double-submit: no idempotency guard on `POST /run` → 2 PENDING runs [nowing_backend/app/automations/api/run.py:13] — deferred, pre-existing
- [x] [Review][Defer] `DispatchError` → HTTP mapping by string `"not found"` is fragile [nowing_backend/app/automations/services/run.py:86] — deferred, pre-existing
- [x] [Review][Defer] `nowing_chat` retry loop has no jitter; thundering herd on concurrent busy [nowing_mcp/mcp_server/features/chat/__init__.py:137] — deferred, pre-existing
- [x] [Review][Defer] AC-9 "mirror Telegram /run" — Telegram persists trigger; here trigger is transient (trigger_id=NULL) [nowing_backend/app/automations/services/run.py:72] — deferred, pre-existing
- [x] [Review][Defer] `nowing_chat` SSE: no per-event stall timeout (only total 600s) [nowing_mcp/mcp_server/core/client.py:144] — deferred, pre-existing

**Verdict:** APPROVED — 0 patches, 5 deferred, 5 dismissed. All candidate patches dissolved under verification.

## 11. Notes for Downstream Stories

- **Slice 4 (chat):** đã reuse client SSE pattern của `nowing_evals/src/nowing_evals/core/clients/new_chat.py` — port `iter_sse_events` vào `core/sse.py`, `ThreadBusyError` retry vào `core/errors.py`, `stream_sse()` vào `core/client.py`. `NewChatRequest.mode` đã có speed/balanced/quality/auto.
- **Slice 5 (automation run):** đã reuse `launch_run()` + `TriggerType.MANUAL` (pattern Telegram `_handle_rerun`); backend `POST /automations/{id}/run` = thin wrapper. Đã tồn tại `GET /automations/{id}/runs` + `GET .../runs/{run_id}` ở `app/automations/api/run.py`.
- Bất kỳ tool mới nào tiếp theo phải sync cả 3 nơi: `features/<name>/` (register), `selfcheck.py EXPECTED_TOOLS`, `app/mcp_tools.py MCP_TOOL_CATALOG` — nếu không test `test_backend_catalog_matches_selfcheck` sẽ đỏ.

---

## 12. ATDD Artifacts

- **MCP tests:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/tests/test_team_memory_tools.py" />
- **MCP tests:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/tests/test_image_generation_tools.py" />
- **MCP tests:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/tests/test_memory_slice2_tools.py" />
- **MCP tests:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/tests/test_automation_report_tools.py" />
- **MCP tests:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/tests/test_chat_tool.py" />  `[x] Slice 4`
- **Backend unit:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/unit/automations/services/test_run_service_launch.py" />  `[x] Slice 5`
- **Backend integration:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/automations/api/test_run_endpoint.py" />  `[x] Slice 5`
- **Selfcheck:** `uv run python -m mcp_server.selfcheck` → 44 tools OK

---

## 13. Dev Agent Record

### Agent Model Used
opencode / deepseek-v4-flash-free (backfill — work được implement ad-hoc trước khi có story file)

### Debug Log References
- Thêm `NowingClient.request_bytes()` — trả `(response.content, content_type)`; xử lý failure như `request`.
- `nowing_report_export` default `pdf`; text formats (html/latex/plain) decode utf-8; binary (pdf/docx/epub/odt) base64 + hint.
- Cân nhắc rồi **bỏ** `nowing_automation_get` — giữ scope đúng plan (chỉ list).
- Test base64 fix 2 lần: không phải `JVBERg==` cố định; payload nằm trong repr → dùng regex `JVBER[A-Za-z0-9+/=]+`.

### Completion Notes List
- Slice 0–3 verified: selfcheck 42 tools; MCP suite 83 passed (excl. `test_research_continuity.py` pre-existing fail); ruff clean.
- **Slice 4–5 (đợt này):** +2 tool (`nowing_chat`, `nowing_automation_run`) → selfcheck 44 tools; MCP suite **103 passed** (research_continuity nay pass); backend unit 276 + run-launch 6 + run-endpoint integration 4 pass; ruff clean.
- Backend pytest integration nay CHẠY được local (Postgres tại localhost:5432 sẵn) — test run endpoint dùng `db_session` transactional + `enqueue_spy` (patch `apply_async`, không cần Redis).
- `uv run ruff` trong `nowing_backend` trigger env build >120s timeout → dùng binary `/Users/luisphan/.agent-reach-venv/bin/ruff` (0.15.8).
- Story là backfill: slices 0–3 làm trước gates; slices 4–5 hoàn tất đợt này → **status: review** (chờ bmad-code-review).

### File List
- `nowing_mcp/mcp_server/core/client.py`
- `nowing_mcp/mcp_server/core/sse.py`  `[x] Slice 4`
- `nowing_mcp/mcp_server/core/errors.py`  `[x] Slice 4`
- `nowing_mcp/mcp_server/features/team_memory/__init__.py`, `annotations.py`
- `nowing_mcp/mcp_server/features/image_generation/__init__.py`, `annotations.py`
- `nowing_mcp/mcp_server/features/automations/__init__.py`, `annotations.py`
- `nowing_mcp/mcp_server/features/reports/__init__.py`, `annotations.py`
- `nowing_mcp/mcp_server/features/chat/__init__.py`, `annotations.py`  `[x] Slice 4`
- `nowing_mcp/mcp_server/features/memory/__init__.py`
- `nowing_mcp/mcp_server/features/scrapers/__init__.py`
- `nowing_mcp/mcp_server/features/scrapers/platforms/chotot_bds.py`, `muaban_bds.py`
- `nowing_mcp/mcp_server/server.py`
- `nowing_mcp/mcp_server/selfcheck.py`
- `nowing_mcp/tests/test_team_memory_tools.py`, `test_image_generation_tools.py`, `test_memory_slice2_tools.py`, `test_automation_report_tools.py`
- `nowing_mcp/tests/test_chat_tool.py`  `[x] Slice 4`
- `nowing_backend/app/mcp_tools.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/routes/memories_routes.py`
- `nowing_backend/app/automations/services/run.py`  `[x] Slice 5`
- `nowing_backend/app/automations/api/run.py`  `[x] Slice 5`
- `nowing_backend/tests/unit/automations/services/test_run_service_launch.py`  `[x] Slice 5`
- `nowing_backend/tests/integration/automations/api/test_run_endpoint.py`  `[x] Slice 5`
- `_bmad-output/implementation-artifacts/7-7-mcp-server-tool-expansion.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## 14. References

- PRD: [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` § FR-29, FR-21, FR-22, FR-23, FR-18/19/20, FR-32/33/34]
- Epic 7: [Source: `_bmad-output/planning-artifacts/epics.md` § Epic 7 — Story 7.6 MCP server `[done]`]
- Architecture: [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` § AD-7]
- Previous story format: [Source: `_bmad-output/implementation-artifacts/4-5-agent-memory-tools-via-mcp.md`]
- MCP tool-toggle pattern: [Source: `_bmad-output/implementation-artifacts/2-5-workspace-mcp-tool-toggle.md`]
- MCP server composition: [Source: `nowing_mcp/mcp_server/server.py`]
- MCP client: [Source: `nowing_mcp/mcp_server/core/client.py`]
- Selfcheck: [Source: `nowing_mcp/mcp_server/selfcheck.py`]
- Backend catalog: [Source: `nowing_backend/app/mcp_tools.py`]
- Memory repository: [Source: `nowing_backend/app/services/memory/repository.py`]
- Memory routes: [Source: `nowing_backend/app/routes/memories_routes.py`]

---

## Challenge Log (grill-me)

### Q1 — Already implemented?
- Slice 4 (`nowing_chat`): tool mới, không duplicate. Core engine đã có: backend `POST /new_chat` SSE (`app/routes/new_chat_routes.py:1694`), client SSE buffered pattern trong `nowing_evals/.../clients/new_chat.py` (`.ask()`/`_consume_sse()`/`iter_sse_events`/`ThreadBusyError` retry, lines 148–388). Reuse đúng hướng — không HALT.
- Slice 5 (`nowing_automation_run`): backend `POST /automations/{id}/run` KHÔNG tồn tại (chỉ có `GET /runs` + `GET /runs/{run_id}` ở `app/automations/api/run.py:13,33`). Spec dự đoán chính xác. Reusable engine: `launch_run()` (`app/automations/dispatch/launch.py:27`) + `TriggerType.MANUAL` (`app/automations/persistence/enums/trigger_type.py:16`), đã dùng bởi Telegram `_handle_rerun` (`app/gateway/telegram/callbacks.py:203-265`). Không HALT.

### Q2 — Simpler alternative?
- Slice 5: backend endpoint = **thin HTTP wrapper quanh `launch_run`** với `AutomationTrigger(type=MANUAL)`, reuse pattern Telegram — KHÔNG "mirror /run" thủ công. Đã sửa story để làm rõ.
- Slice 4: reuse trực tiếp pattern evals `NewChatClient.ask`/`_consume_sse` (httpx stream + `iter_sse_events`), không viết SSE parser mới.
- Không HALT — cả 2 reuse hợp lý.

### Q3 — Edge cases spec misses (Pattern 3)
- [x] Chat: `THREAD_BUSY`/`TURN_CANCELLING` 409 — tool retry (max 4, cap 30s như evals); `TURN_CANCELLING` → ToolError readable.
- [x] Chat: thread không tồn tại / visibility sai → 404/403 backend trả lỗi; tool surface qua ToolError.
- [x] Chat: `mode` invalid → `Literal[speed|balanced|quality|auto] | None`; tool expose `mode` optional (bỏ qua khi None).
- [x] Chat: connection reset giữa stream / `[DONE]` không tới — `stream_sse` timeout 600s; exception map ToolError; non-JSON event skip.
- [x] Automation run: automation_id không tồn tại → 404; status != ACTIVE → 400 ("automation X is {status}, not active").
- [x] Automation run: fire-and-return (trả `pending`), KHÔNG wait; user poll qua `GET /runs/{run_id}` — đã confirm scope trong AC-9.
- [ ] Automation run: double-submit → 2 runs (backend không dedupe manual trigger) — chấp nhận, note trong docstring.
- [x] Automation run: permission `automations:execute` — endpoint check qua `RunService._authorize`; integration test Viewer → 403.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] Chat provider down / LLM timeout (OpenRouter/OpenAI) → SSE fail giữa stream — `stream_sse`/`_consume_once` raise ToolError readable; chưa có test mô phỏng provider down.
- [ ] Credit/quota cạn (deep-research cost) → backend chặn; tool surface qua ToolError — chưa có test riêng (backend đã map 402/403).
- [ ] Celery `apply_async` fail sau khi `launch_run` committ → run kẹt `PENDING` vĩnh viễn (không có transition PENDING→TIMED_OUT) — ⚠️ failure mode thật, đã note; ngoài scope slice này.
- [x] `DispatchError` (invalid definition) → map 400/500 sang lỗi readable — `RunService.launch` map "not found" → 404, còn lại → 400; unit test.

### Triage
- Critical findings: **0** (Q2 Slice 5 đã resolve bằng thin-wrapper reuse, đã sửa story).
- Non-critical (Q3/Q4): 12 findings → mang vào test skeleton bước `bmad-nowing-test-first-atdd`.
- Verdict: **Clean — proceed to test-first-atdd.**

---

## 13. Mutation Gate 4.10 (P0-gated)

**Target:** `RunService.launch` in `app/automations/services/run.py` — touches `automations:execute` auth surface.

**Config:** `nowing_backend/mutation-run-7-7.toml`
- `module-path = "app/automations/services/run.py"`
- `test-command = "python -m pytest tests/unit/automations/services/test_run_service_launch.py -q --no-header --tb=no"`
- `timeout = 120.0`
- `distributor = "local"`

**Result:**
- Total jobs: 78
- Complete: 78 (100.00%)
- Surviving mutants: 0 (0.00%)
- Verdict: **PASS**

**Triage (6 anti-patterns):**
- Pattern 3/4/6 (auth/exception/comparison) on critical service: **0 survived**.
- No P0/P1/P2 mutants to address.

---

## 14. Human Review Gate 4.13

**P0 areas touched:** `Authorization` — `automations:execute` on `RunService.launch`.

**Reviewed:**
- `app/automations/services/run.py:63-103` — `_authorize` + `launch`.
- `app/automations/api/run.py:13-22` — `POST /automations/{automation_id}/run`.
- `app/utils/rbac.py:129-174` — `check_permission` workspace/role/API gate.
- `app/automations/dispatch/launch.py:27-68` — `launch_run` + `DispatchError`.

**Human verdict:** PASS — 5 P0 review points accepted. No changes required.

**Status after gate:** `done`.

---

## 15. Web E2E Gate 4.14

**Scope:** Story 7.7 does not add a web UI for manual runs, but the new `POST /automations/{id}/run` endpoint produces a `PENDING` run that the `AutomationRunsSection` component must display without crashing.

**Generated:**
- `nowing_web/tests/helpers/api/automations.ts` — API helper to create/delete automation and trigger manual run.
- `nowing_web/tests/automations/automation-manual-run.spec.ts` — Playwright spec verifying the detail page shows a `Pending` run after the backend endpoint is hit.

**Static checks:**
- `pnpm tsc --noEmit` ✅
- `pnpm exec biome check` ✅

**Execution:** Chưa chạy (Docker daemon off → không thể khởi Postgres/Redis/backend). Có thể chạy bằng:

```bash
cd nowing_web
pnpm test:e2e tests/automations/automation-manual-run.spec.ts
```

**Verdict:** `deferred-to-runtime` — script sẵn sàng, cần E2E env để chạy.
