# Nowing — Audit tính năng & Technical-Debt Review

> Ngày: 2026-08-30  
> Commit: `9d1fca0b8` trên nhánh `develop`  
> Phạm vi: toàn repo `nowing` (backend, web, tests, docker, mcp, evals, desktop, obsidian)  

---

## 1. Tóm tắt điều hành

- **Codebase lớn**: 5.287 file, ~36.528 node, ~314.234 cạnh call/dependency trong code-review-graph.
- **Backend Python**: ~1.218.565 dòng (chủ yếu `nowing_backend/app`).
- **Frontend Next.js**: ~183.668 dòng TS/TSX.
- **Test**: 866 file Python test, 90 file Playwright `.spec.ts`.
- **Graph phát hiện 16 cộng đồng code**, với Python backend chiếm cộng đồng lớn nhất (`services-fake`, 22.514 node), Next.js web (`apis-handle`, 4.332 node).
- Nợ kỹ thuật tập trung ở: **monolith `db.py`**, ** các route/service khổng lồ**, **xử lý ngoại lệ quá rộng**, **thành phần React quá lớn**, **frontend 3,6 GB**, và **thiếu cô lập giữa nhiều domain**.

---

## 2. Inventory tính năng sản phẩm

### 2.1 Nền tảng (platform)

| # | Tính năng | Mô tả ngắn | Stack chính | File then chốt |
|---|---|---|---|---|
| 1 | **Auth / SSO / OAuth** | Đăng nhập session, Google OAuth, PAT (personal access token), fastapi-users | FastAPI, fastapi-users, PyJWT, httpx | `nowing_backend/app/users.py`, `auth_routes.py`, `auth/context.py` |
| 2 | **Workspace & RBAC** | Quản lý workspace, membership, role, quyền chi tiết | PostgreSQL, SQLAlchemy | `nowing_backend/app/utils/rbac.py`, `db.py:Workspace/WorkspaceRole/Permission` |
| 3 | **Quản trị (Admin)** | Quản lý users, workspaces, credits, model connections, telemetry, scraper rules | Next.js Admin, FastAPI | `nowing_web/app/admin/*`, `admin_*_routes.py` |
| 4 | **Chat AI / Agents** | Chat streaming, multi-agent, tool use, memory, citations, subagents | LangGraph, LangChain, LiteLLM, assistant-ui | `tasks/chat/streaming/flows/new_chat/orchestrator.py`, `agents/chat/multi_agent_chat/*`, `components/assistant-ui/thread.tsx` |
| 5 | **Deep Research** | Nghiên cứu web sâu, ChainLens executor, token metering | ChainLens, custom agents | `capabilities/chainlens/research/executor.py`, `services/chainlens/*` |
| 6 | **Knowledge Base / Documents** | Upload, lập chỉ mục, tìm kiếm hybrid, chunking, RAG | pgvector, SQLAlchemy, unstructured, docling | `routes/documents_routes.py`, `db.py:Document/Chunk` |
| 7 | **Connectors (Indexing)** | Kết nối 20+ nguồn dữ liệu (Notion, Google Drive, GitHub, Confluence, Dropbox, OneDrive, v.v.) | REST, OAuth, Celery | `routes/search_source_connectors_routes.py`, `services/connector_service.py`, `connectors/*` |
| 8 | **Live Data Scrapers** | Reddit, YouTube, Instagram, TikTok, Google Maps, Google Search, Amazon, Web Crawl, Walmart, v.v. | Python proprietary, httpx, trafilatura | `capabilities/*`, `proprietary/platforms/*` |
| 9 | **Lead Intelligence / CRM** | Enrichment, scoring, campaigns, pipeline, clipper, batch leads | PostgreSQL, custom ML | `lead_intelligence/*`, `routes/leads_routes.py`, `components/leads/CampaignBuilder.tsx` |
| 10 | **Automations & Alerts** | Trigger, action, scheduler, alert rules, sequences | Celery, APScheduler | `automations/*`, `alerts/*`, `routes/alert_rules_routes.py` |
| 11 | **MCP Server / Tools** | Cung cấp tool `nowing_*` cho Claude/Cursor qua MCP | MCP SDK, FastAPI | `nowing_mcp/*`, `mcp_tools.py` |
| 12 | **Billing & Credits** | Stripe, token quota, usage, credits, promo code, subscriptions | Stripe SDK, Redis | `services/token_quota_service.py`, `routes/stripe_routes.py` |
| 13 | **Presentation / Podcast / Web Builder** | Tạo slide, podcast, web app từ dữ liệu | python-pptx, kokoro, Marp, Daytona | `services/presentation/*`, `podcasts/*`, `services/web_builder/*` |
| 14 | **Observability** | OpenTelemetry, metrics tùy chỉnh, logging, rate limiter | otel, slowapi, Redis | `observability/metrics.py`, `app.py`, `rate_limiter.py` |
| 15 | **Gateway (Chat ngoài)** | Discord, Slack, Telegram, WhatsApp, Zalo inbound/outbound | Bot SDK, Redis long-poll | `gateway/*` |
| 16 | **Evals / QA** | Kiểm thử chat regression, mutation killing | Python eval suites | `nowing_evals/*` |

### 2.2 Giao diện người dùng

| # | Tính năng | Stack | File then chốt |
|---|---|---|---|
| 17 | **Marketing website** | Next.js App Router, fumadocs | `app/(home)/*`, `app/docs` |
| 18 | **Dashboard workspace** | Next.js, Jotai, TanStack Query, assistant-ui | `app/dashboard/[workspace_id]/*` |
| 19 | **Connector popup / management** | React hooks + atoms | `components/assistant-ui/connector-popup/*` |
| 20 | **Chat thread UI** | assistant-ui, Plate editor, PlateJS | `components/assistant-ui/thread.tsx`, `lib/chat/stream-engine/engine.ts` |
| 21 | **Desktop app & Browser extension** | Tauri/Plasmo | `nowing_desktop/`, `nowing_browser_extension/` |
| 22 | **Obsidian plugin** | Obsidian API + TS | `nowing_obsidian/` |

---

## 3. Kiến trúc tổng quan

- **Monorepo**: `pnpm` workspace (web, desktop, browser extension, obsidian), backend `uv` + Python 3.12.
- **Backend**: FastAPI + SQLAlchemy async + PostgreSQL/pgvector + Redis + Celery + LiteLLM Router.
- **Frontend**: Next.js 14/15 (App Router, Turbopack), Tailwind, Radix UI, Plate, Jotai, TanStack Query, assistant-ui.
- **Cơ sở dữ liệu**: ~220 bảng/model trong `db.py`; migration bằng Alembic; có `zero_publication` cho ElectricSQL/Zero.
- **Graph cộng đồng**: Backend là một khối khổng lồ (`services-fake`), web là một khối lớn (`apis-handle`), không có cạnh liên cộng đồng (cross_community_edges = 0), cho thấy phân tách ngôn ngữ rõ ràng nhưng **backend bị gộp chung một cộng đồng duy nhất**.

---

## 4. Technical Debt — xếp hạng P0–P3

### P0 — Critical (ảnh hưởng sản xuất / bảo mật / downtime)

#### 1. `db.py` 6.955 dòng — monolith mô hình & enum
- **File**: `nowing_backend/app/db.py:1-6955`
- **Bằng chứng**: Graph `find_large_functions` báo file lớn nhất repo (6.955 dòng, vượt xa file thứ 2 là 3.284 dòng). `grep` cho thấy 40+ enum và 60+ class model trong cùng file.
- **Mô tả**: Tất cả SQLAlchemy models, enums, helpers, mixins, type definitions chất vào một file duy nhất. Mọi thay đổi schema đều conflict, review khó khăn, import cycle dễ xảy ra, build graph chậm.
- **Đề xuất**: Tách thành `models/`, `enums/`, `mixins/` theo domain. Ưu tiên tách enum trước để giảm compile-time.
- **Effort**: 2–3 tuần (lớn, cần test toàn bộ migration).

#### 2. `except Exception:` phổ biến và nuốt lỗi
- **File**: toàn `nowing_backend/app` — 1.753 lần `except Exception` (699 chỉ trong `routes/` và `services/`).
- **Bằng chứng**:
  - `routes/documents_routes.py` có 15 `except Exception as e`.
  - `routes/search_source_connectors_routes.py` có 19 `except Exception`.
  - `services/connector_service.py` khởi tạo `source_id_counter` với `except Exception as e: print(...); self.source_id_counter = 1` (dòng 57).
  - `services/connector_service.py` dùng `except Exception: pass` trong format title/description (dòng 583, 608).
- **Mô tả**: Nuốt lỗi làm giấu bugs, khó debug, dễ rò rỉ dữ liệu sai, giảm reliability.
- **Đề xuất**:
  - Cấm `except Exception` trong route/service trừ entrypoint cuối.
  - Dùng exception hierarchy riêng (`NowingError` subclasses).
  - Chuyển các `print()` trong except thành `logger.exception()`.
- **Effort**: 1–2 tuần (điều tra + refactor từng module).

#### 3. `documents_routes.py` set event loop policy tại module import
- **File**: `nowing_backend/app/routes/documents_routes.py:45-49`
- **Bằng chứng**:
  ```python
  try:
      asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
  except RuntimeError as e:
      print("Error setting event loop policy", e)
      pass
  ```
- **Mô tả**: Side effect global khi import module, `print()` thay vì log, cùng một pattern lặp lại ở `tasks/process_meeting_minutes.py`, `tasks/celery_tasks/video_presentation_tasks.py`. Có thể gây race condition giữa worker và event loop.
- **Đề xuất**: Đưa vào hàm khởi tạo rõ ràng, kiểm tra platform, bỏ `print`, dùng `logger.warning`.
- **Effort**: 1–2 ngày.

#### 4. `print()` còn sót trong production code
- **File**: `services/connector_service.py:54,58`, `services/kokoro_tts_service.py:37,79,115`, `routes/documents_routes.py:48`, `config/__init__.py:108`.
- **Bằng chứng**: `grep -R "print(" ...` tìm thấy 106 lần trong backend (một phần là test/debug script, nhưng vẫn còn trong service/route).
- **Mô tả**: `print()` không đi qua hệ thống log/observability, khó trace, có thể làm rò dữ liệu nhạy cảm ra stdout.
- **Đề xuất**: Thay bằng `logger.*` phù hợp; thêm lint rule (`ruff` T201).
- **Effort**: 2–3 ngày.

#### 5. `use-connector-dialog.ts` 1.433 dòng — React hook khổng lồ
- **File**: `nowing_web/components/assistant-ui/connector-popup/hooks/use-connector-dialog.ts`
- **Bằng chứng**: Graph `find_large_functions` báo 1.433 dòng. Quản lý ~20 state trong một hook.
- **Mô tả**: Quá nhiều responsibility: OAuth cookie, indexing config, create/update/delete, accounts list, MCP list, edit mode, tracking, date range, vision LLM. Khó test, dễ regression.
- **Đề xuất**: Tách thành các hook nhỏ theo subflow (`useConnectorOAuth`, `useConnectorIndexing`, `useConnectorEdit`, `useConnectorAccounts`, `useMCPConnectors`).
- **Effort**: 1 tuần.

---

### P1 — High (ảnh hưởng hiệu năng / maintainability đáng kể)

#### 6. `search_source_connectors_routes.py` 3.284 dòng — route khổng lồ
- **File**: `nowing_backend/app/routes/search_source_connectors_routes.py`
- **Bằng chứng**: 19 `except Exception`, hàng chục endpoint CRUD + indexing logic + OAuth + MCP connector + GitHub repo list trong một file.
- **Mô tả**: Violates SRP. Mỗi connector type nên do service/indexer riêng quản lý.
- **Đề xuất**: Tách thành `connectors/routes/<type>.py` hoặc dùng service layer `connector_service` làm mediator.
- **Effort**: 1–2 tuần.

#### 7. `ConnectorService` class 2.242 dòng
- **File**: `nowing_backend/app/services/connector_service.py:25-2266`
- **Bằng chứng**: Class chứa đến 2.242 dòng, quản lý search files, search youtube, search extension, chunk sources, cache invalidation.
- **Mô tả**: God class, kết hợp discovery, cache, search, chunk building. Khó unit test.
- **Đề xuất**: Tách thành `ConnectorSearchService`, `ConnectorCacheManager`, `ChunkSourceBuilder`.
- **Effort**: 1 tuần.

#### 8. `llm_router_service.py` — singleton pattern với mutable class vars
- **File**: `nowing_backend/app/services/llm_router_service.py`
- **Bằng chứng**: `_instance`, `_router`, `_model_list`, `_router_settings`, `_initialized` là class-level mutable state.
- **Mô tả**: Singleton by `__new__` không thread-safe, khó test song song, khó reset giữa các test.
- **Đề xuất**: Dùng dependency injection hoặc `contextvars`/module-level singleton với lock; viết lại để hỗ trợ testability.
- **Effort**: 3–5 ngày.

#### 9. `config/__init__.py` 1.948 dòng — global config monolith
- **File**: `nowing_backend/app/config/__init__.py`
- **Bằng chứng**: 1.948 dòng, chứa `Config` class từ dòng 584–1939, hơn 800 trường config.
- **Mô tả**: Config quá lớn, khó tìm, khó validate. `print()` còn sót (dòng 108). Dùng `os.getenv` trực tiếp khắp nơi.
- **Đề xuất**: Tách thành các module `config/db.py`, `config/llm.py`, `config/auth.py`, `config/connectors.py`; dùng Pydantic Settings với validation và default rõ ràng.
- **Effort**: 2–3 tuần.

#### 10. `documents_routes.py` 2.074 dòng — CRUD + upload + dispatch + processing
- **File**: `nowing_backend/app/routes/documents_routes.py`
- **Bằng chứng**: 2.074 dòng, 15 `except Exception`, xử lý upload 500 MB, OCR, parse, dispatch task.
- **Mô tả**: Route làm quá nhiều việc; nên giao cho `DocumentService`, `UploadService`, `TaskDispatcher`.
- **Đề xuất**: Tách phần xử lý upload/parse ra service, giữ route làm thin adapter.
- **Effort**: 1 tuần.

#### 11. `thread.tsx` 2.413 dòng — component chat khổng lồ
- **File**: `nowing_web/components/assistant-ui/thread.tsx`
- **Bằng chứng**: File 2.413 dòng, hub node `Composer` 281 degree, `ComposerAction` 250 degree.
- **Mô tả**: Component chat chứa nhiều subcomponent (Composer, Action, Thread, v.v.) trong một file. Khó maintain, khó lazy-load.
- **Đề xuất**: Tách `Composer`, `Thread`, `Action` thành file/component riêng.
- **Effort**: 4–6 ngày.

---

### P2 — Medium (technical debt nội bộ, không nguy cơ trực tiếp)

#### 12. Frontend build quá nặng — `nowing_web` 3,6 GB
- **Bằng chứng**: `du -sh` báo `3.6G` cho `nowing_web/`.
- **Mô tả**: Khả năng có nhiều dependency, bundle lớn, `.next`/node_modules nặng, asset images, screenshots. Cần kiểm tra bundle size thực.
- **Đề xuất**: Audit `node_modules` + `.next` + assets; dùng `next-bundle-analyzer`; loại bỏ Plate plugins không dùng; lazy-load icons/images.
- **Effort**: 3–5 ngày.

#### 13. Các hub nodes UI bị dùng quá nhiều — `Button`, `cn`, `Input`, `Skeleton`, `Label`
- **Bằng chứng**: `Button` in-degree 788, `cn` 756, `Skeleton` 259, `Input` 218.
- **Mô tả**: UI primitives là hot-spot; thay đổi signature ảnh hưởng hàng trăm files. `cn` (tailwind merge) là utility bridge node.
- **Đề xuất**: Freeze API các primitives; dùng barrel export ổn định; không thêm prop mới vào `Button` mà không review impact.
- **Effort**: 1 ngày (policy) + ongoing.

#### 14. Isolated nodes trong Alembic migrations
- **Bằng chứng**: `get_knowledge_gaps` báo 50 isolated nodes, hầu hết là `downgrade()` trong các file `alembic/versions/*.py`.
- **Mô tả**: Các hàm `downgrade` không được gọi/test, downgrade script có thể lỗi thời hoặc không hoạt động.
- **Đề xuất**: Thêm CI job kiểm tra `alembic downgrade -1` trên test DB; loại bỏ merge migration không cần.
- **Effort**: 2–3 ngày.

#### 15. `check_permission` được gọi rất nhiều nhưng graph không hiển thị đầy đủ caller
- **Bằng chứng**: Query `callers_of` cho `rbac.py::check_permission` trả về quá nhiều kết quả, file bị lưu tạm (166.397 ký tự).
- **Mô tả**: RBAC là cross-cutting concern. Nên có decorator `@require_permission` thay vì gọi manual khắp nơi.
- **Đề xuất**: Tạo FastAPI dependency `RequirePermission(...)` hoặc decorator; giảm lặp lại.
- **Effort**: 3–5 ngày.

#### 16. `web_builder` chạy subprocess với lệnh tuỳ chỉnh
- **File**: `nowing_backend/app/services/web_builder/builder.py:558`, `services/web_builder/deploy_service.py`.
- **Bằng chứng**: `asyncio.create_subprocess_exec` được gọi với command từ config/template.
- **Mô tả**: Nguy cơ command injection nếu input không được sanitize; cần audit đường dẫn lệnh và args.
- **Đề xuất**: Dùng allow-list command/args; không pass user input trực tiếp; chạy trong sandbox (Daytona/Container).
- **Effort**: 2–3 ngày.

#### 17. Subprocess/Popen trong `admin_scraper_platform_accounts_routes.py`
- **File**: `nowing_backend/app/routes/admin_scraper_platform_accounts_routes.py:195-200`
- **Bằng chứng**: `subprocess.Popen(..., stdout=DEVNULL, stderr=DEVNULL)`.
- **Mô tả**: Chạy process từ route admin mà không giám sát/timeout; có thể orphan process.
- **Đề xuất**: Chuyển sang Celery task hoặc ít nhất dùng `asyncio.create_subprocess` với timeout và `waitpid`.
- **Effort**: 1–2 ngày.

---

### P3 — Low (cải tiến chất lượng, quick wins)

#### 18. `console.*` trong web (262 lần)
- **Bằng chứng**: `grep console.` tìm thấy 262 lần trong `nowing_web`.
- **Mô tả**: Console log/error còn sót, một phần trong development; nên dùng logger abstraction hoặc xóa trước build.
- **Đề xuất**: Thêm lint `no-console` (cho phép trong dev script); thay bằng Posthog/Sentry capture.
- **Effort**: 1 ngày.

#### 19. Test `.only` / `.skip` và `@pytest.mark.skip`
- **Bằng chứng**: 23 lần `.only`/`.skip` trong frontend tests, 46 lần `@pytest.mark.skip`/`skip(` trong backend.
- **Mô tả**: Có thể có test bị bỏ quên, gây giảm coverage thực.
- **Đề xuất**: Lập danh sách skip/only, đánh giá từng cái; xóa hoặc sửa; thêm CI check chống `.only`.
- **Effort**: 2–3 ngày.

#### 20. `Biome` format script dùng `--max-diagnostics 500`
- **File**: `nowing_web/package.json`
- **Bằng chứng**: `"format": "biome check --write ./ --max-diagnostics 500"`.
- **Mô tả**: Giới hạn diagnostics có thể giấu lỗi lint/format thực.
- **Đề xuất**: Bỏ `--max-diagnostics 500` ở CI; chỉ dùng khi local dev.
- **Effort**: 1 giờ.

#### 21. `metrics.py` 1.532 dòng — định nghĩa metric thủ công
- **File**: `nowing_backend/app/observability/metrics.py`
- **Bằng chứng**: 70+ hàm `_metric_name()` gần như giống nhau.
- **Mô tả**: Boilerplate lặp lại, dễ quên update khi thêm metric mới.
- **Đề xuất**: Dùng factory/decorator để tạo metric; hoặc chuyển sang OpenTelemetry semantic conventions.
- **Effort**: 2–3 ngày.

---

## 5. Quick Wins (có thể làm nhanh, ROI cao)

1. **Xóa/bật `print()` trong production**: chuyển thành `logger`, thêm lint T201. (2–3 ngày)
2. **Sửa `asyncio.set_event_loop_policy` ở top-level module**: đưa vào hàm khởi tạo rõ ràng. (1–2 ngày)
3. **Thêm CI check chống `.only` và `@pytest.mark.skip` mới**: tránh test bị bỏ quên. (1 ngày)
4. **Bỏ `--max-diagnostics 500` trong format CI**: phát hiện lỗi sớm. (1 giờ)
5. **Freeze API `Button`, `cn`, `Input`, `Skeleton` primitives**: viết ADR, yêu cầu review khi đổi. (1 ngày)

---

## 6. Khuyến nghị dài hạn (3–6 tháng)

1. **Tái cấu trúc backend theo domain**:
   - Tách `db.py` thành package `models/` theo domain (chat, connectors, documents, users, billing).
   - Tách `routes/` khổng lồ thành versioned API modules.
   - Tách `services/connector_service.py` thành các service nhỏ.
   - **Lý do**: giảm conflict, tăng testability, giảm cognitive load.

2. **Cải thiện xử lý lỗi**:
   - Xây dựng exception hierarchy (`NowingError` → `NotFound`, `PermissionDenied`, `ConnectorError`, `LLMError`).
   - Cấm `except Exception` ở route/service; chỉ dùng ở entrypoint để trả lỗi chuẩn.
   - Thêm middleware ghi log đầy đủ request_id, workspace_id, user_id.

3. **Frontend architecture**:
   - Tách các component/hook khổng lồ (`use-connector-dialog.ts`, `thread.tsx`, `CampaignBuilder.tsx`) thành modules nhỏ.
   - Audit bundle size, loại dependency thừa, dùng lazy loading cho Plate plugins.
   - Giới thiệu feature-based colocation thay vì gom theo `components/`, `lib/`, `hooks/`.

4. **Bảo mật & sandbox**:
   - Audit tất cả `subprocess`, `eval`, `Popen`, `web_builder` command execution.
   - Đưa web builder và scraper chạy trong container sandbox (Daytona/Docker).
   - Xoay/encrypt credentials trong DB (`api_key`, `access_token` nên dùng `access_token_encrypted` pattern).

5. **Observability & reliability**:
   - Thêm distributed tracing qua các critical flows: chat, connector indexing, research, billing.
   - Đưa `metrics.py` sang factory/OTel conventions.
   - Thêm health check và circuit breaker cho các external API (Composio, Litellm, Stripe).

6. **Testing & CI**:
   - Tăng coverage cho untested hub nodes (`get_async_session`, `get_auth_context`, `check_permission`).
   - Thêm `alembic downgrade` smoke test trong CI.
   - Chạy mutation testing cho `llm_router_service`, `token_quota_service`, `rbac.py`.

---

## 7. Kết luận

Nowing là một sản phẩm feature-rich với kiến trúc monorepo hợp lý nhưng đang tích lũy nợ kỹ thuật nghiêm trọng từ tốc độ phát triển nhanh. Ba điểm cần ưu tiên ngay:

1. **Monolith `db.py` + các route/service khổng lồ** làm chậm iteration và tăng regression.
2. **`except Exception` + `print()`** làm giấu lỗi và giảm reliability.
3. **Frontend components/hooks quá lớn + bundle nặng** gây khó bảo trì và hiệu năng.

Nếu chỉ làm 5 quick wins và bắt đầu tách `db.py` + `search_source_connectors_routes.py`, repo sẽ dễ maintain và scale đáng kể trong 1–2 tháng tới.
