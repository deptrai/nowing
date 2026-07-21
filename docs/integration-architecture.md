# Nowing - Kiến trúc tích hợp giữa các phần

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan

Nowing là hệ thống multi-part; các phần giao tiếp chủ yếu qua HTTP REST API do backend cung cấp, ngoại trừ đồng bộ real-time sử dụng Rocicorp Zero.

## Sơ đồ tích hợp

```
+---------------+       REST/WebSocket       +------------------+
|  Web (Next.js)|<--------------------------->|  Backend FastAPI |
+---------------+                            +------------------+
       ^                                            ^
       | Zero sync                                  | REST
       |                                            |
+---------------+         +---------------+        |
|  Desktop      |<------->|  Browser Ext  |        |
|  (Electron)   |         |  (Plasmo)     |        |
+---------------+         +---------------+        |
       ^                                            |
       | REST                                       |
+---------------+                                  |
| Obsidian Plugin|                                 |
+---------------+                                  |
                                                    |
+---------------+         +------------------+     |
|  MCP Server   |<-------->|  Evals Harness |     |
|  (Python)     |   REST    |  (Python CLI)  |     |
+---------------+          +------------------+    |
```

## Các điểm tích hợp chính

| Từ | Tới | Giao thức | Chi tiết |
|---|---|---|---|
| Web | Backend | HTTP REST | `app/api/v1/[...path]/route.ts` proxy tới `BACKEND_URL` |
| Web | Backend | Zero sync | `app/api/zero/mutate` & `app/api/zero/query` (Rocicorp Zero) |
| Desktop | Web | Embed | Electron load `http://localhost:3000` hoặc production URL |
| Desktop | Backend | REST/IPC | Main process gọi backend qua HTTP, preload exposes API |
| Browser Extension | Backend | REST | Background/service worker gọi API Nowing |
| Obsidian Plugin | Backend | REST | `src/api-client.ts` gọi các endpoint `/obsidian/...` |
| MCP Server | Backend | REST | `mcp_server/core/client.py` gọi backend với API key |
| Evals | Backend | REST | `nowing_evals` core clients gọi `/api/v1/...` |

## Chi tiết proxy Web → Backend

- `app/api/v1/[...path]/route.ts` nhận mọi phương thức, chuyển tiếp headers, body, query params tới backend.
- Web app Next.js chạy server proxy để tránh CORS trong môi trường local/self-host.

## Chi tiết Zero sync

- `app/api/zero/mutate/route.ts` và `app/api/zero/query/route.ts` xử lý đồng bộ dữ liệu real-time giữa frontend và backend.
- Backend cấu hình `zero_publication` Postgres publication (kiểm tra bởi `/ready`).

## Authentication cross-part

- Backend sử dụng `fastapi-users` với cookie/session và JWT bearer.
- Web sử dụng NextAuth/Auth.js (`app/auth/[...path]`) hoặc fastapi-users cookie.
- Desktop dùng bearer token hoặc cookie session.
- Browser extension và Obsidian dùng API key cá nhân (`nw_pat_...`).
- MCP server dùng `Authorization: Bearer <NOWING_API_KEY>`.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
