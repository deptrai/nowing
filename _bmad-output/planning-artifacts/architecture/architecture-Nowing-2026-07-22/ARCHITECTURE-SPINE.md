---
name: 'Nowing Architecture Spine'
type: architecture-spine
purpose: build-substrate
altitude: feature
paradigm: 'layered modular monolith + stateless MCP server + client-server with Zero sync'
scope: 'Toàn bộ hệ sinh thái Nowing: backend FastAPI, web Next.js, desktop Electron, browser extension, Obsidian plugin, MCP server, và evals.'
status: active
created: '2026-07-22'
updated: '2026-08-08'
binds: []
sources:
  - /Users/luisphan/Documents/nowing/docs/architecture-backend.md
  - /Users/luisphan/Documents/nowing/docs/architecture-web.md
  - /Users/luisphan/Documents/nowing/docs/architecture-mcp.md
  - /Users/luisphan/Documents/nowing/docs/api-contracts-backend.md
  - /Users/luisphan/Documents/nowing/docs/api-contracts-mcp.md
  - /Users/luisphan/Documents/nowing/docs/integration-architecture.md
  - /Users/luisphan/Documents/chainlens-research/_bmad-output/planning-artifacts/architecture/architecture-chainlens-research-2026-08-08/ARCHITECTURE-SPINE.md
companions:
  - /Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
  - /Users/luisphan/Documents/chainlens-research/_bmad-output/planning-artifacts/architecture/architecture-chainlens-research-2026-08-08/ARCHITECTURE-SPINE.md
  - /Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md
  - /Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md
  - /Users/luisphan/Documents/chainlens-research/_bmad-output/planning-artifacts/architecture/ADR-CHAINLENS-AS-NOWING-MICROSERVICE.md
---

# Architecture Spine — Nowing

> **⛵ Amendment 2026-07-25 — Nowing = sản phẩm, ChainLens = engine.** Nguồn: `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED). Thay đổi: **AD-15 mới** (ChainLens là external deep-research dependency, không phải scraper capability) · **AD-16 mới** (ranh giới license ba tầng; `app/proprietary/` là biên BSL 1.1) · **AD-DEFER-7 mới** (owned web index / crawl-at-scale = NON-GOAL) · **AD-3 amended** (bỏ FR-24 khỏi binds) · **AD-8 amended** (cost thật từ `costDollars`, không giá phẳng) · **AD-11 amended** (provenance phải nối được về nguồn chạy lại được — FR-39, hiện đang bị defect schema) · Capability map re-bind. Đối ứng phía ChainLens: `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` (✅ ACCEPTED).
>
> **🧹 Dọn 2026-07-25 (readiness check `implementation-readiness-report-2026-07-25.md`).** Section `## Deferred / Gaps` có **5 mục lỗi thời** — hoãn thứ mà code đã làm. Đã verify từng cái bằng code rồi đóng: **AD-DEFER-1** (citation highlight) · **AD-DEFER-2** (write-back actions) · **AD-DEFER-3** (MCP tool toggle) · **AD-DEFER-5** (usage dashboard) · **AD-DEFER-6** (memory-driven automations). **AD-DEFER-4** hạ xuống `PARTIAL` (doc-retention schema đã có; legal/right-to-delete cho memory mới là phần còn mở). Sửa thêm: **AD-16 bị đặt lạc vào section Deferred** → chuyển về `## Invariants & Rules`; **`AD-REMOVED` trùng lặp hai chỗ** → giữ một.
>
> **✅ Bổ sung 2026-07-25 (đợt 2) — hai AD giải nốt readiness Q-2 / U-1 / U-2:**
> - **`AD-11.1`** (trong AD-11) — **chốt:** `Memory` **tự chứa recipe** (`source_capability` + `source_input` + soft `source_run_id`), **không** dùng retention có điều kiện cho `runs`. Story **`9.6a`/`9.6b`** giờ có AC xác định.
> - **`AD-17` mới** — deep research chạy trên **async door SẴN CÓ** của capability. **Cải chính readiness U-1:** hạ tầng async đã build end-to-end (`?mode=async` → 202, SSE `runs/<id>/events`, ring buffer replay 500 event, cancel, history) và **web đã có typed client**; `chainlens.research` đã nằm sau nó. **U-2 chốt:** đi SSE, **không** thêm `runs` vào `ZERO_PUBLICATION`. ⇒ Story `9.3` **thu hẹp** còn 3 việc thật: **Redis-backed bus** (bus hiện *single-process*, nhiều replica sẽ im lặng mất event), **async agent door** (agent door đang sync — đây mới là chỗ block chat turn), **notification + deliverable persistence**.
>
> **✅ Bổ sung 2026-08-04 (đợt 4 — docs sync sau reconcile):**
> - **`AD-8` amended** — `costDollars` parse từ terminal `done` frame (`done.usage.costDollars`), không phải event `usage` riêng; fallback 60k micros khi missing.
> - **`AD-15` amended** — terminal `done` contract ghi rõ `usage.costDollars`, `resolvedMode`, `estimated`; `costDollars` là USD float toàn pipeline.
> - **`AD-21` mới** — client tab state pointer-only, local-first, v2 storage key (Story 4.7); sửa lỗi story file ghi `Architecture: AD-17`.
>
> **✅ Bổ sung 2026-08-05 (đợt 5 — Epic 12 HR/Recruitment Vertical):**
> - **`AD-22` mới** — VietnamWorks scraper: public API no-auth, BSL 1.1 fetcher nếu cần HTML fallback, Apache-2.0 capability/executor/schemas.
> - **`AD-23` mới** — TopCV/ITviec scraper: HTML scraping trong `app/proprietary/`, anti-bot reuse `AD-19`, ITviec server-rendered, TopCV Cloudflare challenge cần headless/proxy POC.
> - **`AD-24` mới** — `vn_jobs.aggregate`: copy-modify từ `app/services/bds_aggregator/`, fan-out 3 sources, normalize/dedupe/conflict/salary-consistency.
> - **`AD-25` mới** — PII redaction pipeline: chạy trước khi job data vào `Memory`, regex phone/email + heuristic name, chỉ log counts.
> - **`AD-26` mới** — ToS/legal gates: không build scraper mới cho đến khi ToS cho phép và legal counsel xác nhận không cần license môi giới việc làm.
>
> **✅ Bổ sung 2026-08-06 (đợt 6 — Canonical Entity Storage & Multi-Domain Indexing):**
> - **`AD-27` mới** — Canonical entity convention: mỗi domain aggregator MUST implement 3 methods (`fingerprint()`, `merge()`, `search_text()`) với signature nhất quán. Inherits AD-24 pattern, prevents matching logic divergence across domains.
> - **`AD-28` mới** — Unified matching-engine trigger: build DomainPlugin engine khi có domain thứ 3 HOẶC cross-source overlap >30%. Shared canonical storage (Epic 13.1) ships earlier; trước engine trigger chỉ giữ copy-modify matching + AD-27 convention.
>
> **✅ Amend 2026-08-06 (đợt 7 — Reviewer Gate findings):**
> - **`AD-27` tightened:** Define `MergeResult` TypedDict inline; align Jobs fingerprint with AD-24 (add `posted_at`); mandate default merge strategies per conflict type; specify `normalize()` contract + module path convention; clarify cosine similarity notation (> 0.92).
> - **`AD-28` tightened:** Define fingerprint match rate formula precisely (`entities with ≥2 sources / total entities`, weekly, 2 consecutive weeks); remove subjective "đáng kể" (3rd domain = trigger); add SLA (refactor within 1 sprint); acknowledge plugin ABC migration cost.
> - **`AD-27`/`AD-28` + Epic 13 align 2026-08-06:** Shared canonical tables/source lineage ship in Story 13.1 **before** the plugin-engine trigger. AD-28 only gates DomainPlugin matching refactor. Module exports may wrap existing `dedupe.py`/`normalize.py`. Tenant RLS uses `SET LOCAL app.workspace_id` + FORCE RLS + NOBYPASSRLS.
>
> **✅ Bổ sung 2026-08-08 (đợt 8 — Ecosystem alignment with chainlens-research):**
> - **`AD-27` RE-SCOPED** — từ *"canonical entity convention/multi-domain indexing trong Nowing"* → *"Nowing scraper output feeds `chainlens-research`"*. Nowing không giữ canonical index.
> - **`AD-28` RE-SCOPED** — từ *"unified engine trigger trong Nowing"* → *"unified domain engine thuộc `chainlens-research`"*.
> - **`AD-34` mới** — scraper feed contract: `Chunk[]` schema + `POST /v1/ingest/scraper`.
> - **`AD-35` mới** — `Nowing` không build public/vertical search corpus; `Memory`/`ResearchThread` chỉ cho private user memory + product state.
>
> **✅ Correct-course 2026-08-07 — Vertical Client Platform split:**
> - Public agent-chat / Agent Registry / vertical `client_id` tenancy moved from Epic 13 drafts into **Epic 18**.
> - **`AD-13` amended** — ResearchThread remains continuation context; public agent-chat is allowed only under AD-29 guardrails.
> - **`AD-29`/`AD-30`/`AD-31` added** — public agent-chat surface, AgentConfig registry, vertical client tenancy (orthogonal to workspace RLS).
> - Do **not** bind Agent Registry or public chat to AD-27/AD-28.
> - **`AD-29`/`AD-30`/`AD-31` ✅ ACCEPTED 2026-08-07** (owner accept).
> - **Epic 18 entry #3 ✅ 2026-08-07** — PAT scope + composite RLS test plan + threat model: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md`.
>
> **✅ Bổ sung 2026-07-26 (đợt 3) — hai AD về trích xuất trang khó (verified code cả hai repo):**
> - **`AD-19` mới** — năng lực anti-bot/CAPTCHA **thuộc Nowing** (đã tồn tại 100%: thang 3 tầng + `solve_cloudflare` + detect/inject CAPTCHA + proxy geo/sticky + `BlockType` classifier); **engine có 0%** (`deepExtractor.ts` race Crawl4AI/Jina, 403 → `null` → về snippet SearXNG, không có playwright/proxy/captcha trong deps). Chốt: engine **không** dựng stack riêng, **không** gọi ngược inline (`AD-15` giữ một chiều), escalation chạy **async/enrichment** qua door `AD-17` để không đánh `NFR-9`. Cost trên ledger Nowing (`WEB_CRAWL_*` đã có) và `SM-11a` phải nói rõ điều đó. **Gated trên số đo tỷ lệ 403/CAPTCHA** — chưa đo thì chưa build. Cộng cổng pháp lý `AD-16.1`.
> - **`AD-20` mới** — screenshot-as-evidence dùng **browser tier sẵn có** (patchright đã mở đúng trang, `page.screenshot()` là một lời gọi) + vision model **đã có** (`get_vision_llm`, `Workspace.vision_model_id`) khi extraction mỏng. **KHÔNG** adopt visual-RAG stack (PixelRAG): `AD-2` pgvector **không đổi**, không FAISS/Qdrant, không GPU cho self-host, không nhân storage 100–500×, citation `FR-13`/`NFR-6` không vỡ. Cải chính một nhầm lẫn loại: **visual RAG không phải giải pháp CAPTCHA**.

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Web["nowing_web<br/>Next.js"]
        Desktop["nowing_desktop<br/>Electron"]
        MCP["MCP Client"]
        Ext["Browser Extension"]
    end

    subgraph APIGW["API / Gateway"]
        NJS["Next.js Server Proxy"]
        API["FastAPI Monolith<br/>nowing_backend"]
    end

    subgraph Core["Nowing Core Modules"]
        Chat["Chat & Agents"]
        Mem["Memory Service<br/>HNSW + GIN"]
        Scrapers["Domain Scrapers<br/>app/proprietary/platforms/"]
        CapReg["Capability Registry"]
        Auto["Automations"]
        Bill["Billing / Usage"]
        Conn["Connectors / OAuth"]
        Admin["Admin / RBAC"]
        PDP["NowingPrivateProvider"]
    end

    subgraph Data["Data Layer"]
        PG["(PostgreSQL<br/>pgvector + Alembic)"]
        Redis["(Redis<br/>Celery + events)"]
        S3["(S3 / MinIO<br/>screenshots)"]
    end

    subgraph External["External"]
        CL["chainlens-research<br/>POST /api/v1/search SSE"]
        LLM["LLM Providers"]
        Stripe["Stripe"]
        OAuth["OAuth Providers"]
    end

    Web -->|/api/*| NJS
    MCP -->|MCP over stdio/sse| API
    Ext -->|native| Desktop --> Web
    NJS -->|HTTP| API

    API --> Chat
    Chat --> Mem
    Chat --> CapReg
    Chat -->|deep research| CL
    CapReg --> Scrapers
    CapReg --> Auto
    Scrapers -->|to_chunks()| PG
    Scrapers -->|POST /v1/ingest/scraper| CL
    Chat -->|POST /v1/gap-fill| CL
    CL -->|POST /v1/private-data/search| PDP
    PDP -->|query docs| PG
    PDP --> Conn
    CapReg -->|async jobs| Redis
    API --> Bill
    Bill -->|charge| Stripe
    API -->|auth| OAuth
    API --> Admin
    Admin --> PG
    Mem --> PG
    Auto --> Redis
    Conn -->|tokens| PG
    Chat -->|screenshot on anti-bot| S3
```

## Design Paradigm

**Backend: Layered modular monolith.**
```
HTTP request
    ↓
app/routes/          (FastAPI controllers / request validation)
    ↓
app/services/        (business logic, external services)
app/capabilities/    (scraper capabilities, self-registering routes)
app/agents/          (multi-agent chat runtime)
app/automations/     (trigger/action/run engine)
app/tasks/           (Celery background tasks)
    ↓
app/db.py            (SQLAlchemy models)
app/retriever/       (hybrid search)
```

**Client-Server: Server-driven state với Zero sync.**
- Web (Next.js App Router) proxy mọi REST call tới backend qua `/api/v1/[...path]`.
- Real-time state (chat, comments, automations) sync qua Rocicorp Zero publication.
- Desktop bọc web app và thêm native capabilities qua preload IPC.
- Browser extension / Obsidian plugin gọi REST trực tiếp bằng PAT.

**MCP Server: Stateless HTTP service.**
- Không giữ session; mỗi request mang `Authorization: Bearer <NOWING_API_KEY>`.
- `WorkspaceContext` chọn workspace active; tool gọi backend REST qua `NowingClient`.

## Inherited Invariants

Không có parent spine; đây là spine cao nhất.

## Invariants & Rules

### AD-1 — Backend là monolith module hóa, không microservice
- **Binds:** toàn bộ backend
- **Prevents:** việc tách scraper/agent/automation thành các service riêng lẻ gây overhead giao tiếp
- **Rule:** Mọi nghiệp vụ nằm trong một process FastAPI; giao tiếp nội bộ qua function call; chỉ gọi ngoài qua HTTP (OAuth, LLM, Stripe, **ChainLens deep-research engine**) hoặc queue (Celery). Mỗi domain có thư mục riêng (`app/capabilities/`, `app/agents/`, `app/automations/`).
- **Ghi chú 2026-07-25:** AD-1 cấm tách **nghiệp vụ nội bộ** thành microservice; nó **không** cấm gọi service ngoài. ChainLens (AD-15) là service ngoài gọi qua HTTP — nằm trong ngoại lệ đã có của AD-1, không phải vi phạm.

### AD-2 — Async SQLAlchemy + Alembic + PostgreSQL/pgvector
- **Binds:** toàn bộ persistence
- **Prevents:** blocking I/O trên database; schema drift không kiểm soát
- **Rule:** Mọi DB I/O dùng `AsyncSession`. Mọi thay đổi schema phải có migration Alembic. Mọi model dùng `DeclarativeBase` trong `app/db.py`. Vector search dùng `pgvector` với embedding column.

### AD-3 — Scraper capabilities tự đăng ký route
- **Binds:** FR-6, built-in connectors *(amended 2026-07-25: **FR-24 đã rời AD-3** → governed by AD-15)*
- **Prevents:** phải sửa `app/routes/__init__.py` khi thêm scraper mới
- **Rule:** Mỗi capability trong `app/capabilities/<platform>/` export `definition.py` với `build_capabilities_router()`; `app/routes/__init__.py` gọi registry để mount động. Mỗi capability tạo `Run` row.
- **⚠️ Amendment 2026-07-25 (SCP chainlens-engine-boundary, A2):** `app/capabilities/chainlens/` **KHÔNG** còn được governed bởi AD-3. Module code giữ nguyên vị trí trong `app/capabilities/` (không refactor — đổi layout là churn không giá trị), nhưng nó là **external service dependency**, không phải scraper: nó có contract phải giữ ổn định, cost thật phải đo, failure mode phải degrade. Governed by **AD-15**. Không được suy ra bất kỳ tính chất "scraper" nào (ví dụ: billing phẳng per-run) cho ChainLens từ AD-3.

### AD-4 — Multi-agent chat runtime với tool registry và permission middleware
- **Binds:** FR-15, FR-16, agent tools
- **Prevents:** agent tự do gọi tool không kiểm soát, hoặc ghi đè dữ liệu không mong muốn
- **Rule:** Main agent chọn tool từ `main_agent/tools/registry.py`. Mọi tool call ghi `AgentActionLog`. `PermissionMiddleware`/`AgentPermissionRule` kiểm tra trước khi cho phép mutate documents/folders. Revert dùng `DocumentRevision`/`FolderRevision`.

### AD-5 — Zero sync cho real-time client state
- **Binds:** FR-16, real-time web chat
- **Prevents:** polling hoặc WebSocket custom
- **Rule:** Backend tạo `zero_publication` Postgres publication. Web dùng `/api/zero/mutate` và `/api/zero/query` để đồng bộ `new_chat_threads`, `new_chat_messages`, `chat_comments`, `notifications`, `automation_runs`.

### AD-6 — Next.js server proxy tới backend
- **Binds:** FR-25, web client
- **Prevents:** CORS và env leak ở browser
- **Rule:** `app/api/v1/[...path]/route.ts` forward mọi method/body/query/header tới `BACKEND_URL`. Client không gọi backend trực tiếp ngoại trừ Zero.

### AD-7 — MCP server stateless với workspace context
- **Binds:** FR-29, FR-24, OQ-4
- **Prevents:** MCP server giữ state per client
- **Rule:** `mcp_server/server.py` tạo `FastMCP` với `stateless_http=True`. Mọi tool nhận `WorkspaceParam`; `WorkspaceContext` resolve workspace theo tên/id hoặc active workspace. `NowingClient` gọi backend với API key.

### AD-8 — Unified credit wallet
- **Binds:** FR-31, FR-30, **FR-37** *(amended 2026-07-25)*
- **Prevents:** nhiều loại credit/token khác nhau; **và (mới) cost basis phỏng đoán làm nguồn chân lý**
- **Rule:** `User.credit_micros_balance` là ví duy nhất. `TokenUsage.cost_micros` ghi chi phí **LLM/token**. `BillingEvent.cost_micros` ghi chi phí **business event không phải LLM** (enrichment, scoring, outcomes, signals, email). Cả hai đều debit cùng một ví qua `wallet_credit.py`.
- **⚠️ Amendment 2026-07-25 (SCP chainlens-engine-boundary, A3) — cost thật, không giá phẳng:**
  - Chi phí của external service phải lấy từ **cost do service báo về**, không từ hằng số env. Với ChainLens: parse `costDollars` từ **SSE terminal `done` frame** (`done.usage.costDollars`) → `TokenUsage` với `usage_type = "deep_research"` → wallet debit.
  - `CHAINLENS_QUERY_MICROS_PER_CALL` (`app/config/__init__.py:806`) và `BillingUnit.CHAINLENS_QUERY` **xuống hạng fallback**, chỉ dùng khi engine không emit cost, và **mỗi lần dùng phải log warning** để đo tần suất.
  - **Lý do (verified 2026-07-25):** giá phẳng $0.005/call trong khi `mode` default là `quality` (target cost $0.0105; deep research $0.0164) → **under-meter 2.1–3.3×**. Tệ hơn: các số target đó tính trên DeepSeek stack chưa vào prod (ChainLens `DEFAULT_MODEL_POLICY` = 100% `ag/` Gemini, output đắt hơn DeepSeek ~3.5×).
  - **Gate:** không chốt con số pricing/subscription nào trước khi FR-37 và story `8-7` (auto-extract spend cap) có số đo thật.

### AD-9 — RBAC chỉ ba system roles
- **Binds:** FR-10
- **Prevents:** reintroduce Admin system role
- **Rule:** `get_default_roles_config()` chỉ tạo Owner/Editor/Viewer. `WorkspaceRole.is_system_role=True` chỉ dành cho 3 role này. Custom role có `is_system_role=False`. Migration 72 đã xóa Admin; không tạo lại Admin.

### AD-10 — Token usage tracking per message/workspace/user
- **Binds:** FR-30
- **Prevents:** mất dấu vết chi phí
- **Rule:** `TokenUsage` row được tạo qua `record_token_usage()` trong `app/services/token_tracking_service.py` cho **LLM token consumption** (prompt/completion/total tokens). `message_id` unique khi not null. `usage_type` cho phép mở rộng trong nhóm LLM (chat, indexing, image, podcast, deep_research). **Business events không phải LLM (enrichment, scoring, outcomes, signals, email)** phải dùng `BillingEvent` (AD-8, AD-42), không `TokenUsage`.

### AD-11 — Long-term research memory là first-class persistence layer (unified)
- **Binds:** FR-32, Story 3.8, Story 4.5
- **Prevents:** nhiều hệ thống memory chồng chéo (markdown user/team memory vs. structured research memory)
- **Rule:**
  - `Memory` table là single source of truth cho workspace memory. `User.memory_md` và `Workspace.shared_memory_md` deprecated; migration sẽ `DROP COLUMN` sau khi bridge hoạt động.
  - `Memory` là workspace-wide (`workspace_id` bắt buộc). `research_thread_id` là nullable FK trên `Memory` cho optional thread link (MVP); nếu sau này một memory thuộc nhiều thread thì tách thành bảng join.
  - `Memory` lưu `content`, `embedding`, `type` (semantic/episodic/procedural/working), `source_type`, `source_id`, `tags`, `confidence`, `created_by_id`.
  - `MemoryVersion` ghi lịch sử mỗi correction/update.
  - `MemoryRelation` lưu edges giữa memories/documents/chats/scraper runs bằng adjacency list trong Postgres; không dùng graph DB riêng cho MVP.
  - `app/services/memory/` trở thành canonical memory package: `repository.py` (CRUD/search), `renderer.py` (render `Memory` rows ra markdown cho agent prompt), `parser.py` (parse markdown từ old PUT endpoints thành facts), `service.py` (markdown-compatible public API cho routes và `MemoryInjectionMiddleware` cũ).
  - `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` load user/team memory từ `Memory` table thay vì `User.memory_md`/`Workspace.shared_memory_md`.
  - Structured endpoints: `POST /workspaces/<id>/memories`, `POST /workspaces/<id>/memories/search`, `PATCH /memories/<id>`, `DELETE /memories/<id>`. Legacy bridge endpoints (`GET/PUT /workspaces/<id>/memory`, `GET/PUT /users/me/memory`) vẫn hoạt động nhưng backed by `Memory` table.
  - `TokenUsage.usage_type` mở rộng thêm `memory_create` (và `memory_recall` nếu recall có bước summarization) để theo dõi chi phí extraction/embedding.
  - **Memory search is for private workspace memory only.** `POST /workspaces/<id>/memories/search` searches user docs and extracted facts, not BĐS/jobs/news/finance/company listings. Public/vertical search queries route through `chainlens-research` (`POST /api/v1/search`) and are governed by AD-34/AD-35.
  - **Provenance phải nối được về nguồn có thể chạy lại (bổ sung 2026-07-25, FR-39).** `source_type`/`source_id` không chỉ để hiển thị citation — với nguồn `scraper_run`, `Memory` phải giữ đủ thông tin để **chạy lại đúng truy vấn cũ** và kiểm fact còn đúng không. Đây là nền của khả năng re-validate.
  - **🔒 AD-11.1 — Memory tự chứa recipe, KHÔNG phụ thuộc retention của `Run`** *(quyết định chốt 2026-07-25; giải readiness **Q-2**)*
    - **Quyết định:** khi tạo memory từ dữ liệu scrape, `Memory` **sao chép** `capability` (ví dụ `reddit.scrape`) và `input` (JSONB) từ `Run` vào chính nó, cộng thêm một **soft reference** tới `run_id` để truy vết.
    - **Loại bỏ:** retention có điều kiện cho `runs` (giữ `Run` nào đang được `Memory` tham chiếu). **Không** làm cách này.
    - **Vì sao:** (a) `RUNS_RETENTION_DAYS = 30` với cleanup **cơ hội** (`_maybe_cleanup` chạy trên ~1% insert, `app/capabilities/core/runs.py:33-37`) — làm nó có điều kiện nghĩa là mỗi lần xoá phải join sang `memories`, biến một cleanup rẻ thành truy vấn có khoá; (b) `runs.output_text` có thể rất lớn (JSONL) nên giữ vô hạn vì memory là **đắt sai chỗ** — cái cần giữ chỉ là *recipe*, không phải *payload*; (c) memory là first-class persistence layer theo chính AD-11 này, nên nó **không được** phụ thuộc lifecycle của bảng log; (d) một `Memory` sống 2 năm vẫn re-validate được dù `Run` đã bị xoá 23 tháng trước.
    - **Rule cụ thể:** `Memory` thêm `source_capability` (String) + `source_input` (JSONB) + `source_run_id` (UUID, nullable, **không** FK cứng — `Run` được phép biến mất). `Memory.source_id` (Integer) **giữ nguyên** cho nguồn `document`/`chat_message`; **không** đổi kiểu cột đó (chống hồi quy).
    - **Re-validate:** `revalidate(memory_id)` đọc `source_capability` + `source_input` → gọi lại capability → so sánh → cập nhật `confidence` hoặc tạo `MemoryVersion`. **Không** xoá cứng memory cũ (giữ kỷ luật FR-34).
    - **Ràng buộc:** `source_input` là **snapshot bất biến** — không sửa sau khi tạo. Nếu cần đổi truy vấn thì tạo memory mới, không mutate recipe cũ (nếu không thì "re-validate" mất nghĩa).
    - **Quan hệ với AD-25 (PII):** `source_input` chứa **raw `Run.input` JSONB** (recipe) và **không bị redact**. `Memory.content` / `Memory.embedding` là bản redact theo `AD-25`; `source_input` không được embedded, không gửi engine, không hiển thị UI.
    - **Áp dụng cho:** Story **`9.6a`** (provenance recipe) và **`9.6b`** (re-validation API) — AC giờ **xác định**, không còn "chọn một trong hai".
    - **⚠️ Hiện trạng vi phạm rule này (defect, verified 2026-07-25):** `Memory.source_id` là `Integer` (`app/db.py:2077`) nhưng `Run.id` là `UUID` (`app/db.py:3155`) → không lưu được link; **không có code nào ghi** `MemorySourceType.SCRAPER_RUN` (enum khai báo ở `app/db.py:572` rồi bỏ đó); và chưa có `source_capability`/`source_input`.

### AD-12 — MCP server expose memory tools
- **Binds:** FR-29, Story 4.5
- **Prevents:** MCP client phải tự quản lý memory hoặc inject full file context
- **Rule:**
  - `app/mcp_tools.py` thêm `McpToolGroup.MEMORY` và catalog entries cho `nowing_remember`, `nowing_recall`, `nowing_update_fact`, `nowing_continue_research`.
  - `nowing_mcp/mcp_server/features/memory.py` đăng ký 4 memory tools.
  - Các tool gọi backend `MemoryService` qua `NowingClient` tại structured endpoints (`/workspaces/<id>/memories/*`).
  - `nowing_remember` có thể được gọi bởi agent **hoặc** bởi backend auto-extraction sau mỗi chat turn.
  - `nowing_recall` trả về compact string, `top_k` mặc định thấp (≤5), có thể filter `type`/`tags` để tiết kiệm context window.
  - `nowing_continue_research` load `ResearchThread` context và `Memory` liên quan trước khi trả lời.

### AD-13 — Research Thread là continuation context
- **Binds:** Story 4.6, Story 6.5, Epic 18 (ResearchThread auto-linkage for vertical clients)
- **Prevents:** mỗi chat là một island, mất lịch sử research; public clients tạo chat không có memory continuity
- **Rule:**
  - `ResearchThread` liên kết 1-n `ChatThread` (`new_chat_threads.research_thread_id` nullable FK).
  - `ResearchThread` workspace-wide, optional link với `Memory` qua `Memory.research_thread_id` (MVP).
  - Agent loop load `ResearchThread` context qua `nowing_recall` với `research_thread_id` trước khi trả lời.
  - `AutomationRun` có thể reference `research_thread_id` (post-MVP cho memory-driven automations).
  - **Amendment 2026-08-07:** Public/vertical agent-chat may create and link `ResearchThread` instances, but only through the AD-29 public surface. AD-13 does **not** by itself authorize public HTTP exposure, PAT auth, or `client_id` tenancy — those are AD-29/AD-31.

### AD-14 — Auto-extract memory từ chat turn
- **Binds:** Story 4.5, FR-32
- **Prevents:** mất context giữa các session và agent phải tự nhớ mọi thứ
- **Rule:**
  - Sau khi một assistant message được lưu, `MemoryExtractionService` (chạy async/Celery) gọi cheap model để extract facts từ user + assistant messages.
  - Mỗi fact được kiểm tra `confidence >= threshold` (configurable, default 0.7) và **deduplicate** với existing memory (vector similarity; nếu similarity > 0.92 thì update, không insert mới).
  - Mỗi turn giới hạn số memory items extract (vd tối đa 3) để tránh pollution.
  - Mỗi extraction/upsert ghi `TokenUsage.usage_type = "memory_create"`.
  - Workspace có thể bật/tắt qua `MEMORY_AUTO_EXTRACT_ENABLED` (default `True` cloud, `False` self-host nếu muốn tiết kiệm).

### AD-15 — ChainLens là external deep-research dependency, KHÔNG phải scraper capability
- **Binds:** FR-24, FR-37, FR-38, NFR-9; Epic 9 (Story 9.1–9.4)
- **Supersedes:** AD-3 đối với `app/capabilities/chainlens/` (xem amendment AD-3)
- **Đối ứng:** ChainLens `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` (✅ ACCEPTED 2026-07-25) + `sprint-change-proposal-2026-07-25-v4-nowing-microservice.md`
- **Prevents:**
  - Coi ChainLens như một connector/scraper ngang hàng Reddit → mất contract discipline, mất cost accounting, mất failure handling.
  - Merge ChainLens vào monolith (khác runtime/ngôn ngữ) hoặc ngược lại, biến ChainLens thành sản phẩm độc lập cạnh tranh Nowing.
  - Nowing hard-fail khi engine không khả dụng, dù chính Nowing đã có hybrid search.
- **Rule:**
  - **Ranh giới.** Nowing sở hữu: account/auth/onboarding, workspace/RBAC, memory, connectors, chat, deliverables, automations, **billing/credit/metering**, đa client, distribution. ChainLens sở hữu: deep-research pipeline (classifier → planner → researcher → writer → reflection), provider chain search/extract + failover, cost-optimized LLM routing, semantic cache, citations/quality. **ChainLens không có end-user auth và không có billing.**
  - **Contract (🔒 versioned + regression-guarded).** `POST {CHAINLENS_API_URL}/api/v1/search`, SSE. Auth `Authorization: Bearer <CHAINLENS_API_KEY>` — **service-to-service, Nowing giữ một key**; ChainLens không biết end-user, định danh/hạn mức end-user do Nowing quản. Request `{ query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId? }` — `query` được strip khoảng trắng đầu/cuối qua `field_validator("query", mode="before")` `_strip_query` trước khi `min_length=1`/`max_length=500` kiểm tra; `tier: "research"` và `stream: true` là một phần của contract (đã thêm từ 9.1a). Response là data-only SSE frames (`data: <json>\n\n`); `type` nằm trong JSON payload (`type:block` / `type:updateBlock` RFC6902 patch, `type:done`, `type:error`); terminal thật là `{"type":"done", "chatId": ..., "webUrl": ..., "usage": {"costDollars": <float>, "resolvedMode": "speed|balanced|quality|...", "estimated": true|false, ...}}` — **không** có dòng `event:` hay sentinel `data:[DONE]`. Contract này được khoá bằng regression test trong CI (marker `contract: contract regression tests for ChainLens integration` trong `pyproject.toml`, target `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`), sử dụng golden fixture `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` đồng bộ với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` qua drift test.
  - **Cost.** Lấy từ `costDollars` do engine emit (xem AD-8 amendment). Giá phẳng chỉ là fallback có log.
  - **Failure → degrade, không hard-fail.** Timeout / 5xx / chưa cấu hình → fallback sang `app/retriever/` hybrid search + trạng thái tường minh `partial` / `engine_unavailable`. **Không bịa citation**, không giả vờ là câu trả lời đầy đủ. Nowing self-host không cấu hình ChainLens vẫn dùng được mọi tính năng khác.
  - **Không merge.** Nowing = Python/FastAPI, ChainLens = TypeScript/NestJS. Giữ hai service riêng, giao tiếp qua HTTP. Đây là ngoại lệ hợp lệ của AD-1 (monolith): AD-1 cấm tách *nghiệp vụ nội bộ* thành microservice, không cấm gọi *service ngoài*.
  - **Mode.** Default `balanced` (quyết định D3, 2026-07-25). `quality` là opt-in tường minh cho deep-research/deliverable. Đổi default phải validate trên `nowing_evals`.
  - **Ranh giới OSS/Cloud (D5, 2026-07-25).** Engine **closed-source, hosted**; chỉ Nowing được public. ⇒ **Mọi self-host instance chạy ở trạng thái không có engine** → FR-38 degradation là **tiền đề trước khi public repo**, không phải một tính năng reliability tuỳ chọn.
  - **Phase 2 (post-MVP, nếu mở):** self-host dùng deep research phải đi theo `self-host Nowing → Nowing Cloud API (metered, key theo account) → engine (vẫn 1 service key)`. **CẤM** `self-host → engine trực tiếp`: cách đó biến engine thành public multi-tenant SaaS với end-user auth, phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 và SCP v4 de-scope. Nowing Cloud là biên multi-tenant duy nhất, vì nó vốn đã sở hữu account + credit wallet (`AD-8`).
  - **Latency.** Xem NFR-9: State A (async deliverable) là sàn bắt buộc; State B (sync chat-mode sau flag) mở khi có số đo. Nowing đo p50/p95 **từ phía mình**, không chờ engine tự báo.
- **Ghi chú (verified 2026-07-25):** ChainLens đã de-facto là research backend của Nowing từ trước — `app/capabilities/chainlens/research/executor.py` gọi `POST {CHAINLENS_API_URL}/api/v1/search`. AD-15 chỉ ghi lại đúng thực tế và bổ sung kỷ luật thiếu (contract guard, cost thật, degradation).

### AD-16 — Ranh giới license ba tầng; `app/proprietary/` là biên BSL
- **Binds:** D5; toàn bộ `nowing_backend/app/proprietary/**`; mọi tài liệu công khai
- **Prevents:** (a) code BSL trôi ra ngoài biên hoặc code Apache-2.0 bị kéo vào trong; (b) tài liệu công khai gọi sai license
- **Rule:**
  - **Ba tầng:** Apache-2.0 cho mọi thứ **ngoài** `nowing_backend/app/proprietary/` · **BSL 1.1** cho `app/proprietary/**` (84 file Python, ~16.6k dòng: fetcher từng nền tảng, YouTube InnerTube, CAPTCHA, session/pool, stealth testbench, proxy registry — ⚠️ **kế thừa từ SurfSense, KHÔNG phải tự xây**, xem `AD-16.1`) · **closed-source hosted** cho deep-research engine (không nằm trong repo, `AD-15`).
  - **Chiều import một phía:** code Apache-2.0 **được** import từ `app.proprietary`; code đặt **bên trong** `app/proprietary/` không được tính là Apache-2.0. Đừng move logic Apache-2.0 vào trong biên, và đừng copy logic BSL ra ngoài.
  - **BSL Additional Use Grant:** cho phép production use; **cấm** đem Licensed Work (hoặc sản phẩm/dịch vụ mà giá trị chủ yếu bắt nguồn từ nó) bán cho bên thứ ba như commercial product hoặc hosted/managed service. Change Date: 4 năm → Apache-2.0.
  - **Tài liệu công khai:** không gọi cả sản phẩm là "open source"; dùng *"Apache-2.0 core + BSL 1.1 crawler engine"*. BSL là điểm bán (bảo vệ moat, vẫn cho self-host chạy production) — nói thẳng, không lấp liếm.
  - Thêm capability scraper mới → phần fetch/anti-bot thuộc `app/proprietary/`; phần `definition.py`/`schemas.py` (contract) có thể ở ngoài. Giữ nguyên tách biệt này (`AD-3` vẫn áp dụng cho lớp đăng ký route).
- **Nguồn:** `LICENSE` (root) · `nowing_backend/app/proprietary/LICENSE` · docstring `app/proprietary/__init__.py`
- **Ghi chú:** đây là mô hình **đã tồn tại trong code**, AD-16 chỉ ghi lại và đặt kỷ luật quanh nó. Trước 2026-07-25 nó không có trong bất kỳ artifact planning nào — PRD/brief đang gọi sai là "OSS thuần".

---

#### 🔴 AD-16.1 — CẢI CHÍNH: Nowing là FORK của SurfSense; `app/proprietary/` KHÔNG phải "tự xây"
- **Giải:** readiness **`L-1`** · **Cổng thứ hai trước public repo** (cạnh `9-1a`) · chủ sở hữu: action item **`AI-2026-07-25-7`** (`Founder + Legal`, P0, `blocks: public-repo`)

> **Phát hiện 2026-07-25 khi thiết lập versioning cho artifact.** `git remote` có `upstream = https://github.com/MODSetter/SurfSense.git`. Không artifact planning nào — kể cả AD-16, SCP, brief, PRD — **từng nhắc tới việc Nowing là fork**. Việc này đổi tiền đề thực tế của chính AD-16.

**Đo bằng git, không suy đoán** (so `nowing_backend/app/proprietary/` với `upstream/main:surfsense_backend/app/proprietary/`):

| Phép đo | Kết quả |
|---|---|
| Số file `.py` hai bên | **84 vs 84** |
| Đường dẫn tương đối trùng nhau | **84 / 84 (100%)** |
| **Giống hệt byte-for-byte** | **73 / 84 (87%)** |
| File có khác biệt | 11 — mỗi file **2–4 dòng** |
| Tổng dòng khác biệt | **~26 / ~16.600 dòng (0,16%)** |
| **26 dòng đó là gì** | **Chỉ đổi chuỗi `SurfSense` → `Nowing`** — comment, docstring, và một thuộc tính `name = "surfsense_site"` → `"nowing_site"`. **Không có thay đổi chức năng nào.** |

**⇒ Câu "crawler engine tự xây" trong AD-16 ở trên là SAI VỀ THỰC TẾ.** `app/proprietary/` là crawler engine của SurfSense, đổi tên, không sửa logic.

> #### 🔴🔴 AD-16.1a — CẢI CHÍNH PHẠM VI (2026-07-26): fork là TOÀN REPO, không chỉ `app/proprietary/`
>
> **AD-16.1 ở trên đo thiếu.** Nó chỉ so thư mục BSL rồi kết luận "99,84% code kế thừa" — đúng, nhưng **hẹp**. Đo lại rộng hơn (verify bằng git 2026-07-26, mọi số tái lập được):
>
> | Phép đo | Kết quả |
> |---|---|
> | `git merge-base HEAD upstream/main` | `bea603e22` = upstream tag **`0.0.34.1`** |
> | Commit upstream tại điểm fork | **7.713** |
> | Commit của Nowing kể từ đó | **45** |
> | **Cả 7 component đều là rename 1:1** | `surfsense_{backend,web,desktop,browser_extension,obsidian,mcp,evals}` → `nowing_*` |
> | Mọi file top-level cũng kế thừa | `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `README.md` + 4 bản dịch, `VERSION`, `manifest.json`, `versions.json`, `docker/`, `docs/`, `scripts/`, `.github/` |
> | Thư mục **của Nowing**, không có ở upstream | chỉ `.agents`, `.claude`, `.devin`, `.kiro`, `_bmad` — **config AI tooling, không phải code sản phẩm** |
> | **Phần Apache-2.0** (backend `app/**/*.py`, TRỪ `proprietary/`) | upstream 1.227 file → **993 byte-identical (81%)**, 234 sửa, **0 xoá** |
>
> **Hệ quả — nặng hơn AD-16.1:** nghĩa vụ attribution của **Apache-2.0 §4** áp lên **toàn bộ phần core** (993 file y nguyên + 234 file sửa mà **không file nào** có change-notice theo §4(b)), không chỉ lên thư mục BSL. Và dòng `Copyright (c) SurfSense` → `(c) Nowing` ở root `LICENSE` giờ phủ **cả một codebase Apache-2.0 kế thừa**, không phải một subdirectory.
>
> **Rule bổ sung:** mọi tài liệu — kể cả `AD-16`, PRD §1.1, brief — **không** được mô tả tier Apache-2.0 là "core của Nowing" theo nghĩa tự viết. Nó là core kế thừa **có** phần đóng góp của Nowing (memory layer, tích hợp engine, billing) đặt lên trên.
>
> **Brief gửi luật sư:** `_bmad-output/planning-artifacts/legal/legal-brief-upstream-attribution-2026-07-26.md` — 5 câu hỏi (Apache-2.0 §4 · quyền đặt mình làm BSL Licensor · Additional Use Grant vs hosted engine · điều kiện trước khi public · phơi nhiễm giai đoạn chưa publish) + 5 phương án A–E + lệnh tái lập mọi số liệu.
>
> **Sau khi có kết luận:** amend `AD-16` + `AD-16.1` phạm vi · cập nhật PRD §1.1 · quyết lại `D5` nếu cấu trúc BSL phải đổi · gỡ chặn `public-repo`.

**Cả hai file license cũng là bản copy đổi tên — attribution bị THAY, không phải được bổ sung:**

| Trường | SurfSense (upstream) | Nowing |
|---|---|---|
| root `LICENSE` | `Copyright (c) SurfSense` | `Copyright (c) Nowing` |
| BSL `Licensor` | `SurfSense` | `Nowing` |
| BSL `Licensed Work` | `The SurfSense Proprietary Components…` `(c) 2026 SurfSense` | `The Nowing Proprietary Components…` `(c) 2026 Nowing` |
| `Change Date` / `Change License` | Four years / Apache-2.0 | **giống hệt** |
| `Additional Use Grant` | — | **giống hệt** |

Và: **không có `NOTICE`** (upstream cũng không có), **README không credit SurfSense**, cấu trúc dual-license ba tầng mà AD-16 trình bày như quyết định của Nowing thực ra **thừa hưởng nguyên vẹn**.

**Hệ quả với lập luận thương mại — đây là phần nặng nhất:**
- **`D5` và brief bán BSL như "moat" và "điểm bán".** Moat đó là **99,84% code Nowing không viết**. Lập luận "bảo vệ crawler engine tự xây" không đứng được ở dạng hiện tại.
- **`AD-16` đặt `Licensor: Nowing`** trên khối code này. Nowing tự đặt mình làm Licensor của BSL cho code kế thừa.
- `9-1a` (degradation) hiện là **cổng duy nhất** trước public repo. Phát hiện này là **cổng thứ hai**, độc lập, chạy song song được.

**Rule bổ sung (hiệu lực ngay):**
1. **KHÔNG public repo** trước khi vấn đề attribution được luật sư xem xét và xử lý. Đây là **cổng thứ hai** cạnh `9-1a`.
2. **Không tài liệu nào được gọi `app/proprietary/` là "tự xây" / "self-built" / "our own crawler engine"** cho tới khi có kết luận. Sửa AD-16 dòng trên, PRD, brief, và mọi marketing copy.
3. **Mọi lập luận moat dựa trên BSL phải nêu lại tiền đề.** Nếu moat thật của Nowing là research memory (theo brief §1) thì đừng dựa vào crawler engine để biện minh BSL.
4. Câu hỏi cần luật sư trả lời — **không phải việc của artifact này quyết**: (a) Apache-2.0 §4 yêu cầu giữ attribution tới mức nào, và việc **thay** dòng copyright có thoả không; (b) Nowing có quyền đặt mình làm **BSL Licensor** cho code kế thừa không, và BSL gốc của SurfSense ràng buộc gì; (c) cần `NOTICE` + credit ở README/LICENSE dạng nào.
- **Nguồn (tái lập được):** `git remote -v` · `git show upstream/main:LICENSE` · `git show upstream/main:surfsense_backend/app/proprietary/LICENSE` · so hash 84 file như bảng trên · `upstream/main` = tag `0.0.34.1`, commit `bea603e22`.

### AD-17 — Deep research chạy trên async door SẴN CÓ của capability; không phát minh flow mới
- **Binds:** NFR-9 State A, FR-24, FR-38; Story `9.3`
- **Prevents:** story `9.3` tự thiết kế một cơ chế job/progress/notify riêng cho deep research trong khi hạ tầng đó **đã tồn tại và đã có typed client ở web**
- **Rule:** Story `9.3` **PHẢI** dùng async capability door đã có (`POST .../chainlens/research?mode=async` → 202 + `X-Run-Id`, SSE progress, cancel, history). Không tạo bảng job mới, không tạo endpoint progress mới, không thêm `runs` vào `ZERO_PUBLICATION`.

#### 🔎 Cải chính U-1 — hạ tầng async ĐÃ CÓ end-to-end (verified 2026-07-25)

Readiness report ghi *"không AD nào định nghĩa flow này"* và ngụ ý phải xây mới. **Không đúng.** Async door cho capability đã build đủ, và `chainlens.research` **đã nằm sau nó** vì nó là capability đăng ký qua `register_capability` (`app/capabilities/chainlens/research/definition.py:23`):

| Mảnh | Đã có ở đâu |
|---|---|
Submit fire-and-forget | `POST /workspaces/<id>/scrapers/chainlens/research?mode=async` → insert `Run` status `running`, spawn background task, trả **202** + `X-Run-Id` (`app/capabilities/core/access/rest.py:312-330`) |
Progress live | `GET .../runs/<run_id>/events` — SSE (`rest.py:493`), nguồn từ `emit_progress` qua `progress_scope` |
Replay khi reconnect | `run_event_bus` giữ **ring buffer 500 event** per run (`app/capabilities/core/events.py`) |
Terminal | event `run.finished`; client kết nối muộn đọc snapshot cuối từ hàng `runs` |
Cancel | `POST .../runs/<run_id>/cancel` (`rest.py:559`) — bus giữ luôn `asyncio.Task` để với tới |
History | `GET .../runs` + `GET .../runs/<run_id>` (`rest.py:463`, `482`) |
**Typed client ở web** | `nowing_web/lib/apis/scrapers-api.service.ts:68` đã build `?mode=async`; `contracts/types/scraper.types.ts:56` type response 202 |

⇒ **Rule: Story `9.3` PHẢI dùng đường này.** Không tạo bảng job mới, không tạo endpoint progress mới, không thêm `runs` vào `ZERO_PUBLICATION`.

#### Quyết định U-2 — delivery đi bằng SSE của `run_event_bus`, KHÔNG mở Zero cho `runs`
- **Chọn:** SSE (đã có) · **Loại:** thêm `runs` vào `ZERO_PUBLICATION` · **Loại:** polling.
- **Vì sao không Zero:** `runs` là bảng **log khối lượng lớn, TTL 30 ngày**, có `output_text` JSONL cỡ lớn. Zero sync là cho **state client cần theo dõi liên tục** (chat, comments, automations, notifications) — đẩy một bảng log ephemeral vào publication làm phình sync payload mà không ai cần lịch sử realtime của nó. `AD-5` giữ nguyên phạm vi.
- **Vì sao không polling:** SSE + ring buffer đã giải đúng bài toán reconnect; polling thêm độ trễ và tải DB mà không được gì.

#### 🔴 Ba việc CÒN THIẾU thật — đây mới là nội dung của Story `9.3`

1. **Bus chỉ hoạt động trong MỘT process.** `events.py` tự ghi: *"`ponytail:` single-process only — a multi-worker deployment needs Redis pub/sub (or Postgres LISTEN/NOTIFY) behind this same interface."* Nếu API chạy nhiều replica/worker, client tail SSE ở replica A sẽ **không thấy** event của run đang chạy ở replica B — im lặng, không lỗi. **Rule:** trước khi bật deep-research async trên môi trường nhiều replica, phải đặt **Redis pub/sub** (Redis đã có sẵn cho Celery — `AD-4`) sau **cùng interface `run_event_bus`**. Không đổi call-site.
2. **Agent door là SYNC — đây mới là chỗ block chat turn.** `app/capabilities/core/access/agent.py` gọi executor inline, không có `mode=async`. Nên khi agent gọi deep research trong một chat turn, nó **chặn** tới 300s. State A yêu cầu agent door cũng submit-and-return: agent nhận `run_id` + thông báo "đang chạy", chat turn kết thúc, kết quả về sau. **Đây là phần khó nhất của `9.3`**, không phải phần transport.
3. **Không có notify khi xong, và kết quả không thành deliverable.** `run.finished` chỉ là event trên bus — grep `Notification|notify` trong `rest.py`/`runs.py` = **0 hit**. Client đóng tab là mất. Và kết quả deep research nằm trong `runs.output_text` (TTL 30 ngày), **không** phải deliverable hạng nhất như `Report`/`Podcast`. **Rule:** State A hoàn chỉnh cần (a) emit `Notification` khi `run.finished` — bảng `notifications` đã có (`app/notifications/persistence.py`) và **đã nằm trong `ZERO_PUBLICATION`** nên realtime sẵn; (b) persist kết quả thành deliverable nếu user yêu cầu, không dựa vào TTL của `runs`.

#### Ràng buộc phụ thuộc ngoài
Progress hiện chỉ có **2 event** cho deep research — `emit_progress("starting")` (`executor.py:189`) và `("done")` (`:206`). Transport chạy tốt nhưng **không có gì để truyền** trong 57–198s ở giữa. Progress theo phase (classifier → planner → researcher → writer → reflection) phải do **engine** emit ⇒ đây là câu hỏi phải gửi ChainLens, **bổ sung vào OQ-7** (readiness **U-3**).

#### Consequences
- Story `9.3` thu hẹp lại: **không** xây flow, mà (1) Redis-backed bus, (2) async agent door, (3) notification + deliverable persistence, (4) đo p50/p95, (5) ngưỡng cổng A→B.
- `AD-5` không đổi (`runs` **không** vào Zero publication).
- `AD-4` được tái dùng (Redis đã có cho Celery).
- Story `9.4` docs phải nói deep research là tác vụ **async** ở self-host lẫn cloud.

### AD-18 — Memory injection dùng retrieval CÓ CHẶN TRÊN; hai đường recall phải tách tên
- **Binds:** NFR-1b, NFR-1c, NFR-1d, NFR-8, FR-32, FR-40; Story `3-14`
- **Prevents:** prompt size và DB cost của **mọi lượt chat** tăng tuyến tính theo số memory của workspace — im lặng, không lỗi, và tệ dần đúng theo mức độ người dùng dùng sản phẩm nhiều
- **Rule:** Memory injection **PHẢI** dùng retrieval có chặn trên (HNSW/GIN đã có, top-k bounded), tổng ký tự inject ≤ 8.000, fail-soft phải phát counter, và hai đường `memory_injection` / `memory_recall` phải tách tên trong mọi tài liệu + metric. `NFR-8` không đo trước khi rule này xong.

#### 🔎 Phát hiện — có HAI đường recall, PRD chỉ mô tả một (verified 2026-07-25)

| Đường | Code | Chặn lượt chat? | Dùng index? | Có LIMIT? |
|---|---|---|---|---|
| **Memory injection** | `MemoryInjectionMiddleware.abefore_agent` | ✅ **mọi lượt** | ❌ **không** | ❌ **không** |
| **Recall tool** | `nowing_recall` · `/memories/search` | chỉ khi agent gọi | ✅ | ✅ top_k ≤5 |

Schema `memories` **đã có sẵn hai index chuyên dụng cho retrieval**:
- `ix_memories_embedding` — HNSW, `vector_cosine_ops`
- `ix_memories_content_search` — GIN trên `to_tsvector('english', content)`

Nhưng đường nóng **không dùng cái nào**. Nó chạy:
```sql
SELECT * FROM memories WHERE workspace_id = ? ORDER BY created_at   -- không LIMIT
```
rồi `render_memory_markdown(...)` toàn bộ vào prompt. Docstring của model tự nói `Memory` là *"A single, embedded long-term memory fact"* — **fact-level, nhiều row mỗi workspace**, không có unique constraint nào trên `workspace_id`. Nên N tăng vô hạn.

#### Vì sao phanh hiện tại KHÔNG đóng được lỗ này
- `MEMORY_HARD_LIMIT = 25.000` được enforce bởi `validate_memory_size(content)` — trên **một** `content`, ở **đường ghi**. Aggregate của N fact **chưa từng bị kiểm tra**.
- Middleware chỉ **báo** `chars=` và, khi vượt `MEMORY_SOFT_LIMIT = 18.000`, chèn `<memory_warning>` nhờ LLM tự gọi `update_memory` để consolidate. Đây là **vòng lặp phụ thuộc LLM hợp tác**, và nó **không thể** thắng được `extract_from_turn` (Celery) — vốn ghi thêm row mà LLM chưa từng consolidate. Tốc độ sinh vượt tốc độ dọn.
- Fail-soft `except → return None` khiến recall vắng mặt **im lặng**: chỉ có `logger.exception`, không counter, không alert.

#### Rules
1. **Memory injection PHẢI có chặn trên ở đường ĐỌC** — top-k bounded qua HNSW/GIN đã có, **không** full-scan. Chi phí phải là **O(top-k)**, không phải O(N).
2. **Tổng ký tự inject ≤ 8.000, cắt ở đường đọc.** Không tin vào `<memory_warning>` như cơ chế giới hạn — giữ nó như một tín hiệu chất lượng, không phải một cái phanh.
3. **Hai đường phải tách tên trong mọi tài liệu và metric.** "Recall" không được dùng mơ hồ. `memory_injection` ≠ `memory_recall`.
4. **Fail-soft giữ nguyên, nhưng phải phát counter.** Degrade im lặng trên đường nóng là không chấp nhận được.
5. **Auto-extract KHÔNG được lên critical path.** Hiện đúng (Celery), nhưng **không có test nào giữ** — cần regression test khoá bất biến.
6. **NFR-8 (recall quality) không đo được trước khi rule 1+2 xong.** Baseline chất lượng lấy trên một lượng inject phụ thuộc N là baseline không tái lập được. ⇒ `3-14` **nên chạy trước khi chốt số SM-10** của `3-9`.

#### Hệ quả
- Hook đo **đã có sẵn**: `_perf_log.info("[memory_injection] scope=%s injected=%d db=%.3fs total=%.3fs")`. `3-14` là **chốt ngân sách + assert + cắt**, không phải dựng instrumentation → phạm vi nhỏ hơn vẻ ngoài.
- `FR-40` (research → memory) làm N tăng **nhanh hơn** hiện tại. ⇒ `3-14` là **điều kiện đi kèm** của `3-13`, không phải việc dọn dẹp để sau.
- `AD-11.1` không đổi.

### AD-19 — Năng lực vượt tường (anti-bot / CAPTCHA) thuộc Nowing; engine KHÔNG có stack riêng và KHÔNG gọi ngược inline
- **Binds:** FR-38, FR-24, NFR-9, FR-39; Story `9-1a`, `9-3`, `9-6b`
- **Prevents:**
  - Dựng lại stack anti-bot thứ hai trong ChainLens (TypeScript) — hai bộ credential proxy, hai account solver, hai stack bypass phải bảo trì, cho **một** use case.
  - Cắm thang stealth vào **critical path** của deep research → làm `NFR-9` State B không bao giờ mở được.
  - Tạo phụ thuộc **hai chiều** Nowing ↔ engine, phá phát biểu một chiều của `AD-15`.
  - Đục lỗ vào `FR-37`: chi phí proxy/CAPTCHA phát sinh bên Nowing nhưng bị hiểu là thiếu trong `costDollars` → tái diễn under-meter từ hướng khác.
  - Coi "vượt CAPTCHA" là một tính năng có trạng thái hoàn thành.
- **Rule:** Anti-bot/captcha/crawler bypass logic chỉ thuộc Nowing (`app/proprietary/**` BSL, `app/utils/{captcha,proxy,crawl}/` Apache-2.0); engine không có anti-bot stack và không gọi ngược Nowing crawler inline. URL bị chặn trở thành capability run async trên door đã có (`AD-17`). Chi phí Nowing (proxy/CAPTCHA) ghi trên ledger riêng, không nằm trong `costDollars` của engine.
- **Liên quan:** `AD-15` (biên engine — **không** amend), `AD-16`/`AD-16.1` (biên BSL + cổng pháp lý), `AD-17` (async door), `AD-8` (cost), `AD-DEFER-7`/NG-1 (không owned index).

#### 🔎 Trạng thái thật (verified 2026-07-26 — đọc code cả hai repo)

| | Nowing | ChainLens engine |
|---|---|---|
| Thang fetch nhiều tầng | ✅ `app/proprietary/web_crawler/connector.py` — AsyncFetcher (static, TLS `impersonate="chrome"`) → DynamicFetcher (browser) → StealthyFetcher (patchright) | ❌ `deepExtractor.ts` — `raceFirstNonNull([crawl4ai, jinaDirect])`, timeout 8s |
| Giải Cloudflare | ✅ `solve_cloudflare=True` (in-framework, không vendor) | ❌ |
| Detect + giải CAPTCHA | ✅ `web_crawler/captcha.py` (v2/v3/hCaptcha; widget + iframe `?k=` + api.js `?render=`) + `app/utils/captcha/solvers.py` (2captcha, capsolver, có Enterprise `data-s`) | ❌ |
| Proxy provider / geo / sticky | ✅ `app/utils/proxy/` — ABC + registry + `get_geo_proxy_url` / `get_sticky_proxy_url` / `rotation.py` | ❌ |
| Hardening fingerprint | ✅ `web_crawler/stealth.py` — `block_webrtc`, `hide_canvas`, `dns_over_https`, referer Google, locale/timezone khớp IP exit | ❌ |
| Phân loại tường | ✅ `app/utils/crawl/classifier.py` — `BlockType`: `CLOUDFLARE` / `CAPTCHA_RECAPTCHA` / `CAPTCHA_HCAPTCHA` / `DATADOME` / `KASADA` / `RATE_LIMITED` … stamp trên **mọi** `CrawlOutcome` | ❌ |
| Session ấm theo nền tảng | ✅ `proprietary/platforms/{reddit,tiktok,instagram}` | ❌ |
| Dependency browser/proxy | ✅ patchright/camoufox, curl_cffi | ❌ `apps/api/package.json` **không có** playwright/puppeteer/patchright; không có code proxy/captcha; Firecrawl chỉ là assumption A1, **chưa implement** |

**Hành vi engine khi trang bị chắn:** `jina-retry.ts` retry **chỉ** 408/429/5xx — **không bao giờ** 403. Non-ok → `null` → chunk giữ snippet SearXNG, chỉ `logger.warn`. Nguồn đó **âm thầm mất full-text**. CAPTCHA duy nhất engine xử lý nằm ở **tầng search** (SearXNG bị chắn → failover Brave), không phải tầng đọc trang.

⇒ Năng lực này **đã tồn tại 100% ở Nowing và 0% ở engine.** AD-19 chỉ ghi lại đúng thực tế và đặt kỷ luật quanh nó.

#### Rule 1 — Code sống ở Nowing. Engine không được có stack anti-bot riêng.
Biên giữ nguyên như `AD-16`: **bypass logic** (detect/inject/tuning) trong `app/proprietary/**` (BSL 1.1); **seam vendor-agnostic** (client solver, provider proxy, classifier) ở Apache-2.0 `app/utils/{captcha,proxy,crawl}/`. Chiều import một phía, không đổi.

Nếu ai đề xuất port sang TypeScript: Rule of Three — engine có **một** use case, không phải ba; và nó nhân đôi đúng thứ `D5` gọi là moat.

#### Rule 2 — Engine KHÔNG gọi ngược vào crawler của Nowing trong lượt research.
`AD-15` vẫn **một chiều**: Nowing → engine. Engine chỉ **báo tín hiệu** "URL này không đọc được + lý do", **không** yêu cầu Nowing fetch hộ.

Engine **đã emit** đủ tín hiệu đó rồi — `{type:'partial', state:'insufficient_evidence', reason}`, `{type:'insufficientEvidence', partial, reason}`, `heartbeat` — và Nowing đang **bỏ hết 6 loại event** vì `_parse_sse` chỉ dispatch 4 type (`AI-2026-07-25-5`). Việc đọc chúng thuộc `9-1a`, không phải việc mới.

**Cấm:** thêm `workspace_id` hay bất kỳ khái niệm tenancy nào của Nowing vào contract engine. Đó là thứ biến engine thành multi-tenant surface mà `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 đã de-scope.

#### Rule 3 — Escalation chạy ASYNC/enrichment, KHÔNG inline.
Thang stealth chạy tuần tự: browser launch + `solve_cloudflare` + `CAPTCHA_SOLVE_TIMEOUT_S = 120`. Một URL xấu có thể mất 2–3 phút; deep research fan-out N URL.

`NFR-9` latency đang là **"chưa biết"** và đang bị gate State A→B. Cắm thang stealth vào critical path là tự tay đóng State B.

⇒ Blocked URL trở thành **capability run async** trên door **đã có** (`?mode=async` → 202 + `X-Run-Id`, SSE `runs/<id>/events` — `AD-17`), bổ sung nguồn *sau*. Không tạo bảng job mới, không endpoint progress mới, không thêm `runs` vào `ZERO_PUBLICATION` (`AD-5` giữ nguyên).

**Lợi ích kép:** đây **đúng là** hạ tầng `FR-39`/`9-6b` (re-validation) cần — không phải việc phát sinh thêm.

#### Rule 4 — Thứ tự đầu tư: bậc 0/1 trước bậc 3. CAPTCHA là arms race không có trạng thái kết thúc.
| Bậc | Nội dung | Trạng thái Nowing | Biên chi phí |
|---|---|---|---|
| **0. Đừng chạm vào nó** | TLS fingerprint thật · residential proxy có geo coherence · hardening fingerprint · sticky session ấm · pacing | ✅ gần đủ | **0** |
| **1. Đi cửa chính site tự mở** | API chính thức · RSS/Atom · sitemap · JSON-LD nhúng · oEmbed · AMP · `r.jina.ai` | 🟠 **dùng chưa tới** (engine đã special-case arxiv Atom) | **0**, hợp lệ, ổn định |
| **2. Giải challenge in-framework** | Cloudflare Turnstile/interstitial | ✅ `solve_cloudflare=True` | 0 vendor |
| **3. Solver farm trả tiền** | 2captcha / capsolver; token bind IP proxy; cap 1 attempt/URL; latch process | ✅ đã có | ~$1–3/1000 solve, 10–60s |
| **4. Vendor scraping-API nguyên gói** | Bright Data / Zyte / Oxylabs / ScrapingBee / Firecrawl | ❌ chưa | đắt/request, bảo trì 0, họ gánh tư thế ToS |
| **5. KHÔNG vượt** | tường login · ToS cấm tường minh · giải = vượt access control | ✅ đã ghi thành nguyên tắc trong config | — |

**Rule:** dư địa bậc 0/1 phải cạn trước khi tăng chi ở bậc 3, và **bậc 5 là ranh giới cứng** — config hiện đã ghi đúng: solving có thể vi phạm ToS, coi là opt-in/owner-acknowledged, **chỉ dữ liệu công khai, không bypass trạng thái đăng nhập**. Giữ nguyên câu đó.

#### Rule 5 — Cost nằm trên ledger Nowing, và `SM-11a` phải nói rõ điều đó.
Chi phí crawl/CAPTCHA phát sinh **bên Nowing**, và **đã được meter** — `CrawlOutcome.captcha_attempts`/`captcha_solved` + `WEB_CRAWL_MICROS_PER_SUCCESS` (default 2000) + `WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE` (default 3000), mỗi cái một cờ billing riêng.

⇒ Nó **không** nằm trong `costDollars` của engine, và **đó là đúng** — hai BillingUnit khác nhau, không phải cost ẩn. Nhưng `SM-11a` ("cost thật per deep-research call theo mode") phải **ghi tường minh** rằng nó loại trừ chi phí escalation phía Nowing, kèm một chỉ số phụ cho phần đó. Nếu không, số đọc lên sẽ trông như under-meter — đúng cái bug `FR-37` sinh ra để vá.

#### 🚧 Gate — đo trước khi build
Chưa ai đo **tỷ lệ URL deep-research bị 403/CAPTCHA** và **ảnh hưởng thật lên citation coverage**. 3% thì snippet fallback là câu trả lời đúng và việc này xếp sau `9-1a`/`9-2`; 30% thì là gap chất lượng thật.

**Rule:** không build escalation trước khi có số này. Nó **rẻ**: `9-1a` dù sao cũng phải đọc `partial`/`insufficientEvidence` — gắn counter theo `BlockType` vào đó là gần như miễn phí (classifier đã stamp sẵn trên mọi outcome).

#### ⚠️ Cổng pháp lý — không xây kiến trúc mới lên câu hỏi license chưa đóng
`AD-16.1`: `app/proprietary/` là fork SurfSense, 73/84 file giống byte-for-byte, attribution chưa xử lý (`AI-2026-07-25-7`, P0, chặn public repo).

BSL Additional Use Grant cấm bán Licensed Work — **hoặc sản phẩm mà giá trị chủ yếu bắt nguồn từ nó** — dưới dạng hosted/managed service cho bên thứ ba. Engine deep-research **là** hosted service bán cho bên thứ ba. Nếu nó bắt đầu lấy giá trị trích xuất từ khối BSL kế thừa đó, câu hỏi đang chờ luật sư trở thành **load-bearing về kiến trúc**.

**Rule:** nếu kết luận pháp lý đòi đổi cấu trúc license hoặc trả attribution vào 84 file, việc biến khối đó thành cross-service dependency **phải chờ** — không vì thủ tục, mà vì có thể phải sửa lại chính chỗ vừa xây. Rule 2/Rule 3 (không gọi ngược, chạy async) **giảm** phơi nhiễm này, vì engine không bao giờ dùng trực tiếp code BSL.

#### Ranh giới với `AD-DEFER-7`/NG-1
Đây là **trích xuất per-request cho một URL cụ thể**, KHÔNG phải crawl-at-scale dựng corpus. Không vi phạm `AD-DEFER-7`. Ghi lại để không tranh luận lại.

---

### AD-20 — Screenshot-as-evidence dùng browser tier SẴN CÓ; KHÔNG adopt visual-RAG stack
- **Binds:** FR-9, FR-12, FR-13, FR-39; NFR-6
- **Prevents:**
  - Kéo một hệ retrieval thứ hai (FAISS/Qdrant + pipeline embed riêng + lifecycle index riêng) vào repo cho **một** use case.
  - Thêm một class hạ tầng mới (GPU cho VL embedding) vào một sản phẩm self-hostable.
  - Nhân storage lên hai bậc độ lớn trong lúc `OQ-3` retention còn chưa đóng.
  - Nhầm "visual RAG" là giải pháp CAPTCHA — **nó không phải** (xem dưới).
- **Rule:** Screenshot/structured visual evidence chỉ dùng browser tier sẵn có (`DynamicFetcher`/`StealthyFetcher`/`app/proprietary/web_crawler/`). Không adopt visual-RAG stack mới (FAISS/Qdrant/VL embedding/GPU), không tạo pipeline embed/index lifecycle riêng.
- **Liên quan:** `AD-2` (pgvector — **không** đổi), `AD-19` (browser tier), `AD-11.1` (provenance recipe), `AD-DEFER-7`/NG-1.

#### 🔎 Bài toán có thật, và code của chính Nowing đã khai báo nó

`app/proprietary/web_crawler/stealth.py` ghi đo thực tế: trafilatura drop div-grid pricing card / stat table như "boilerplate" — `duplicati.com/pricing` giữ **15%** text nhìn thấy được; `goauthentik.io/pricing` mất **0 trên 5** con số giá **dù mọi giá đều nằm trong static DOM**.

Cách chữa hiện tại là một **regex tiền tệ** (`_CURRENCY_AMOUNT_RE`, 13 ký hiệu + ISO code + dạng amount-trước-symbol) để: mất giá → re-extract `favor_recall` → vẫn mất → `markdown_of_whole_body()`. Comment trong code tự gọi nó là *"recall 100%, precision be damned"*.

Đó là band-aid thông minh cho một vấn đề **cấu trúc**: HTML→text làm rơi cấu trúc thị giác. Regex chỉ bắt được tiền — không bắt được biểu đồ, bảng so sánh, infographic.

#### ❌ Cải chính một nhầm lẫn loại: visual RAG ≠ giải pháp CAPTCHA
[PixelRAG](https://github.com/StarTrail-org/PixelRAG) (Berkeley SkyLab/BAIR, Apache-2.0, arXiv 2606.28344) render trang/PDF thành tile ảnh rồi retrieve trên ảnh bằng Qwen3-VL-Embedding-2B LoRA-tuned. Bộ render `pixelshot` chạy Playwright/CDP với profile Chrome dùng-rồi-bỏ — **không stealth, không proxy, không anti-bot**. Trang bị CAPTCHA chắn thì nó chụp cho bạn ảnh của cái CAPTCHA.

**Rule:** không được viện visual RAG như giải pháp cho tường bot. Tường bot thuộc `AD-19`.

#### ✅ Quyết định — lấy Ý TƯỞNG, không lấy dependency

Visual RAG có hai đóng góp: **(a)** render-thay-vì-parse, **(b)** model VL embedding fine-tune + index.

**Nowing lấy (a) gần như miễn phí từ hạ tầng đang chạy.** StealthyFetcher tier **đã** mở patchright Chromium trên đúng trang đó, đúng thời điểm extraction sắp thất bại; `page_action` đã nhận `page` object. `page.screenshot()` là một lời gọi — **không dependency mới, không GPU, không vector store thứ hai**.

**Rule:** khi extraction mỏng (đã có tripwire: `looks_like_js_shell` hoặc `dropped_currency_amounts`), tier browser chụp ảnh trang và đưa **vision model** đọc thay — thay cho việc mở rộng regex.

Hạ tầng vision **đã có sẵn**: `get_vision_llm(session, workspace_id)` (dùng thật ở `file_processors.py`, `google_drive_indexer.py`), role `Workspace.vision_model_id` + capability `"vision"`, `supports_image_input` derivation, và `AD-8` metering.

Ảnh đó nuôi hai thứ cùng lúc:
1. **Đọc nội dung thị giác** — bảng giá/biểu đồ mà text extraction làm rơi.
2. **Evidence artifact cho provenance** — `FR-39`/`9-6b` cần biết trang *lúc đó* trông thế nào. Ảnh mạnh hơn markdown đã qua lossy extraction, và `RUNS_RETENTION_DAYS = 30` nên artifact **phải tự chứa** (đúng tinh thần `AD-11.1`).

#### ❌ Bác bỏ — visual RAG như retrieval stack (5 lý do, xếp theo độ nặng)
1. **Là hệ retrieval thứ hai, không phải thư viện.** `AD-2` chốt pgvector trong Postgres; PixelRAG ship FAISS/Qdrant + pipeline embed + lifecycle index riêng. Adopt trọn gói phải amend `AD-2`. Rule of Three: một use case.
2. **Citation vỡ.** `FR-13`/`NFR-6` = chunk → highlight text span trong full editor; story `3-6` vừa ship đường đó. Citation trỏ vào **tile ảnh** không có text span để highlight ⇒ cần đường citation UX song song, trong khi `ux-designs/` còn scaffold rỗng.
3. **Class hạ tầng mới cho sản phẩm self-hostable.** Embedding hiện tại là `all-MiniLM-L6-v2` (CPU, bé). VL-Embedding-2B cần GPU cho throughput; self-hoster CPU nhận đường tệ rõ rệt → đánh trực diện câu chuyện self-host của `D5`.
4. **Storage.** Text chunk ~1KB vs tile ảnh 100–500KB = 100–500× cho cùng lượng nội dung, **và** vẫn phải giữ text cho hybrid search. Đặt cạnh `OQ-3` chưa đóng + doc-retention cron (mig 176) vừa bật xoá dữ liệu.
5. **Độ chín.** Tác giả mạnh, license Apache-2.0 sạch (không bẫy BSL) — nhưng là research codebase mới công bố, có `train/` pin cứng torch. *Boring technology*: chưa phải lúc, ở vị trí core dependency.

#### 🚧 Ranh giới với `AD-DEFER-7`/NG-1 — nêu rõ để không trôi
Artifact nổi nhất của PixelRAG là **index Wikipedia 8.28M trang dựng sẵn (~217GB)**. Dùng *pipeline* trên tài liệu của chính user = trong scope. **Tải/serve index Wikipedia của họ = đã trôi sang NG-1** (owned index, `AD-DEFER-7`, Epic 26 0/7 gate). Không làm.

#### Việc còn phải quyết khi làm (không giả vờ là miễn phí)
- **Chưa có code screenshot nào trong backend** — `grep screenshot app/**/*.py` = 0 hit. (`nowing_desktop` có screenshot assist nhưng đó là phía user, khác hoàn toàn.)
- **`app/file_storage/` hiện document-scoped** — chỉ có `store_document_file` / `build_document_file_key`. Artifact ảnh crawl cần quyết một key namespace + retention riêng, **không** mượn nhờ khoá document.
- **Cost:** một lượt vision-read là một premium model call → phải đi qua `AD-8` như mọi call khác, và bị chặn bởi cùng cơ chế quota. Không có đường tính phí ẩn.
- **Cờ tắt:** đi cùng họ `CRAWL_*` hiện có (`CRAWL_BLOCK_WEBRTC`, `CRAWL_HIDE_CANVAS`, …) — mặc định **OFF**, bật opt-in, để không âm thầm nhân chi phí mỗi lượt crawl.

---

### AD-REMOVED — AI File Sorting đã bị gỡ bỏ
- **Binds:** FR-5
- **Prevents:** lập kế hoạch xây dựng tính năng không còn tồn tại
- **Rule:** Migration `172_remove_ai_file_sort.py` đã `DROP COLUMN workspaces.ai_file_sort_enabled`. Không thêm lại cột, API, hay UI cho AI file sorting.
- *(Mục trùng lặp trong `## Deferred / Gaps` đã xoá 2026-07-25 — chỉ giữ bản này ở `## Invariants & Rules`.)*

### AD-21 — Client tab state là pointer-only, local-first, v2 storage key
- **Binds:** Story 4.7, FR-14
- **Prevents:** tab state lưu snapshot đầy đủ (title, visibility, hasComments) gây stale và lớn; v1 key `nowing:tabs` không migrate được sang pointer shape
- **Rule:**
  - Tab chỉ lưu lightweight pointer: `{ id, type: "chat" | "document", entityId, workspaceId }`.
  - Persist dưới **v2 localStorage key** khác v1 (`nowing:tabs` → `nowing:tabs:v2`); v1 snapshot bị drop, không merge.
  - Titles/metadata resolve **live** qua `useResolvedTabs` hook kết hợp react-query/Zero; rename/delete mutations patch cache để tab tự cập nhật.
  - Fallback navigation dựa trên `entityId` + `workspaceId` khi metadata chưa load.
- **Nguồn:** SurfSense PR #1609 pattern; `nowing_web/atoms/tabs/tabs.atom.ts`, `TabBar.tsx`, `LayoutShell.tsx` cần refactor.

### AD-22 — VietnamWorks Scraper (public API + BSL fallback) `[ADOPTED 2026-08-11 — code verified: unit tests pass; ToS approved]`
- **Binds:** FR-43, Epic 12.1
- **Prevents:** treat VietnamWorks like a generic HTML scraper; leaking PII into memory
- **Rule:**
  - Primary path: call `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth, `hitsPerPage` max 100, 1-based `page`).
  - `app/proprietary/platforms/vietnamworks/` (BSL 1.1) owns the fetcher and low-level response parsing; `app/capabilities/vietnamworks/scrape/` (Apache-2.0) owns `Capability` registration, `definition.py`, `schemas.py`, `executor.py`, billing, and MCP exposure.
  - Capability `vietnamworks.scrape` registers `BillingUnit.VIETNAMWORKS_JOB`.
  - Output maps to a normalized `JobItem` schema shared with `vn_jobs.aggregate`.
  - Golden fixture regression tests guard API contract drift in `tests/unit/capabilities/vietnamworks/`.
  - PII redaction (`AD-25`) runs on `job_description` / `job_requirement` before memory storage.
  - **Hard gate:** ToS review must permit automated access and commercial use before build.

### AD-23 — TopCV & ITviec Scrapers (HTML + anti-bot) `[ADOPTED 2026-08-11 — code verified: unit tests pass; ToS approved; TopCV anti-bot POC remains hard gate]`
- **Binds:** FR-44, FR-45, Epic 12.2, 12.3
- **Prevents:** anti-bot logic diverging from existing crawler stack; anti-bot bypass via exploit/CAPTCHA token storage
- **Rule:**
  - Both scrapers live in `app/proprietary/platforms/topcv/` and `app/proprietary/platforms/itviec/` (BSL 1.1); capabilities live in `app/capabilities/topcv/scrape/` and `app/capabilities/itviec/scrape/` (Apache-2.0).
  - **TopCV:** initial recon shows Cloudflare "Just a moment..." challenge on `GET https://www.topcv.vn/viec-lam/<keyword>`. Anti-bot POC must pass before merge. Reuse `AD-19` stack: headless browser / stealth / residential proxy / `BlockType` classifier / rate-limit. **Cost model decision (chọn Option A):** TopCV fetcher **MUST** be metered through the existing `WEB_CRAWL` billing path (`WEB_CRAWL_MICROS_PER_SUCCESS` + `WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE`) by calling `app/proprietary/web_crawler/connector.py` (`crawl_url`) and returning a `CrawlOutcome`. This is the only existing ledger that can accurately capture anti-bot cost. Capability `topcv.scrape` may register `BillingUnit.TOPCV_JOB` as a pass-through if needed, but the actual cost accounting flows through `WEB_CRAWL`/`captcha` usage. If this is not feasible (e.g., Cloudflare blocks all `AD-19` tiers), disable gracefully and do not merge. Cost gate: total per-query anti-bot cost >$0.05 disables TopCV.
  - **ITviec:** server-rendered HTML (`GET https://itviec.com/it-jobs/<keyword>`), no Cloudflare in initial spike. Use static HTML parser (`lxml`) + rate-limit + user-agent rotation + circuit-breaker. Selectors: `job-card ipt-2`, `h3/a`, `employer-name`, `jd-main`.
  - Salary on ITviec is hidden (`Sign in to view salary`); parse from title when possible or mark `salary_confidence` low.
  - Capabilities register `BillingUnit.TOPCV_JOB` and `BillingUnit.ITVIEC_JOB`.
  - **Hard gate:** TopCV anti-bot POC; ToS review for both.

### AD-24 — Vietnam Job Market Aggregator (`vn_jobs.aggregate`)
- **Binds:** FR-46, Epic 12.4
- **Prevents:** duplicating BĐS aggregator logic; source-specific normalization leaking into aggregator; location filtering done inside individual scrapers
- **Rule:**
  - `app/services/jobs_aggregator/` (Apache-2.0) is a copy-modify of `app/services/bds_aggregator/`.
  - Orchestrator fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` via `get_capability()` and the shared `Capability` registry (`AD-3`).
  - Normalizer maps each source to `VnJobAggregatedListing` with common fields: title, company, location, salary_min/max/currency/period, employment_type, experience_years, skills, posted_at, job_description, job_requirement, source, source_url.
  - Deduplication key: `company + title + location + posted_at` (cross-source), where `posted_at` is **normalized to a UTC date string** before being used as a key. `VnJobAggregatedListing.posted_at` is a `datetime.date | None` derived from each source (`createdOn` for VietnamWorks, parsed "Posted X ago" for ITviec, etc.).
  - Scoring: `confidence_score` (source authority, overlap, freshness, salary consistency) and `salary_consistency_score`; flag `conflict` when salary/location differs materially across sources.
  - Location filter is applied at aggregator level (VietnamWorks `locationId` does not filter server-side; verified by spike). To prevent runaway cost, the aggregator enforces `max_items_per_source` and `max_pages` with the same default per-source caps as the BĐS aggregator (`app/services/bds_aggregator/orchestrator.py`). If `location` is set, filtering happens after normalization, not by re-fetching.
  - Capability `vn_jobs.aggregate` registers `BillingUnit.VN_JOBS_AGGREGATE_QUERY` and a per-query fee on top of child scraper costs.
  - Output includes `degraded`, `degradation_reasons`, `source_breakdown`, `cost_micros`.
  - Exposed via REST, MCP (`nowing_vn_jobs_aggregate`), and chat agent tool.
  - **Agent/subagent wiring (UX finding U1):** A `vn_jobs` subagent package (`app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/`) is created, exposing both per-source `*.scrape` and `vn_jobs.aggregate`. This satisfies the PRFAQ promise that the agent can answer cross-source salary/job-market questions. If the existing per-source subagent pattern is reused, `vn_jobs.aggregate` must be added to the tool roster of each per-source subagent; the dedicated `vn_jobs` subagent is preferred.

### AD-25 — Unified PII Redaction Pipeline (cross-vertical)
- **Binds:** FR-47, NFR-11, Epic 12.5, **Epic 21.3** (lead enrichment)
- **Prevents:** storing candidate/lead PII in `Memory`; logging PII values; rebuilding redaction per vertical
- **Rule:**
  - **Insertion point:** PII redaction runs on long-text / enriched fields **before** they are embedded, extracted into facts, sent to `chainlens-research`, or returned to a user-facing surface. The raw `Run.output_text` remains unredacted for short-term audit (`RUNS_RETENTION_DAYS`).
  - **Immutable recipe vs. redacted content are separate objects:** `Memory.source_input` (raw `Run.input` JSONB) and `Memory.source_capability` are the **immutable re-validation recipe** (AD-11.1) and **must not** be redacted. The redacted text is stored in `Memory.content` / `Memory.embedding` and in `Chunk[]` sent to the engine. `Memory.source_input` is never embedded, never sent to the engine, and never shown in UI.
  - `app/services/pii/redact.py` (Apache-2.0) exposes a single entry point: `redact_pii(text: str, context: str) -> RedactedText` with `text`, `phones_detected`, `emails_detected`, `names_detected`, `has_pii`.
    - `context` selects the rule set: `job_data` (E12.5), `lead_enrichment` (E21.3), or `default`.
    - `redact_job_pii()` is kept as a thin alias for backward compatibility.
  - `MemoryExtractionService` / `build_run_source_block` calls `redact_pii(..., context="job_data")` when `run.capability` matches a job source or `vn_jobs.aggregate`.
  - `EnrichmentService` (E21.3) calls `redact_pii(..., context="lead_enrichment")` after waterfall enrichment and before storing verified contact data or generating chunks.
  - Detection: regex for Vietnamese and international phone numbers, email addresses; heuristic/NER for person names. Configurable per context.
  - Mask or drop detected PII; do not store raw unredacted values in `Memory`.
  - Audit logs only counts (e.g., `phones_detected`, `emails_detected`, `names_detected`), never values.
  - Unit tests for representative VietnamWorks/TopCV/ITviec (job) and Cleanlist/BetterContact sample (lead) outputs.
  - If PII cannot be reliably redacted for a source, that source must be disabled until the pipeline is improved.
- **Enforcement:** E12.5 and E21.3 **must** use the same `app/services/pii/redact.py`; do not create separate `redact_lead_pii()` or `redact_candidate_pii()` modules.

### AD-26 — ToS & Legal Gates for New Scrapers
- **Binds:** NFR-11, OQ-8, Epic 12 P0
- **Prevents:** building scrapers that violate source ToS or Vietnamese employment-service regulation
- **Rule:**
  - ToS review for VietnamWorks, TopCV, and ITviec is a hard gate before any scraper code is merged. Document the review in `_bmad-output/planning-artifacts/legal/`.
  - Legal counsel opinion on whether the pilot classifies Nowing as an "employment service provider" / "môi giới việc làm" in Vietnam is a hard gate before pilot launch.
  - Messaging: Nowing is a **research/memory layer**, not a job board, ATS, or employment intermediary. Do not expose apply/shortlist/candidate matching features.
  - If ToS or legal counsel blocks a source, that source is disabled gracefully (`degraded=true`) and removed from default `sources` list; do not bypass blocks.
  - **Observability (Dev finding D12):** Add low-cardinality counters for `pii_phones_detected`, `pii_emails_detected`, `pii_names_detected`, `vn_jobs_aggregate_degraded`, and per-source block rate. These support SM-12 and do not leak PII values.

### AD-27 — Nowing Domain Scraper Output Feeds chainlens-research (RE-SCOPED 2026-08-08)

- **Binds:** AD-22/AD-23/AD-24 (scraper/aggregator outputs), all future domain scrapers
- **Prevents:** `Nowing` building its own searchable canonical index; `chainlens-research` missing domain-specific data
- **Rule:**
  - `Nowing` owns domain-specific scrapers and aggregators (anti-bot, business-specific logic, PII redaction).
  - Scraper/aggregator output **must** be normalized to `Chunk[]` with `source: 'nowing_scraper'` and `metadata.domain`/`metadata.sourceId`/`metadata.fetchedAt`/`metadata.contentType`.
  - `Nowing` sends the `Chunk[]` batch to `chainlens-research` via `POST /v1/ingest/scraper` (service-to-service Bearer) and receives `ingestJobId`.
  - Deduplication, embedding, full-text/vector indexing, and search happen in `chainlens-research`. `Nowing` does **not** create a `pgvector` index or full-text search corpus for this vertical data.
  - Matching/dedup logic may run in `Nowing` for immediate aggregation output (e.g., `confidence_score`, conflict flags) but the merged result is sent as `Chunk[]` to `chainlens-research`; it is **not** stored in a Nowing `canonical_entities` table.

### AD-28 — Unified Domain Engine Belongs in chainlens-research (RE-SCOPED 2026-08-08)

- **Binds:** Future domain expansion (domain thứ 3+)
- **Prevents:** `Nowing` owning canonical entity storage, shared indexing, or unified cross-domain search
- **Rule:**
  - Any future unified matching engine, canonical entity storage, or cross-domain search index is owned by `chainlens-research`, not `Nowing`.
  - `Nowing` may keep product state (raw scraper logs, billing records, automation runs) and private user `Memory`, but these are **not** the canonical search index.
  - `Nowing` triggers gap-fill in `chainlens-research` (`POST /v1/gap-fill`) when a query misses data; `chainlens-research` either crawls the public web or invokes the relevant `Nowing` scraper.

### AD-29 — Public Agent-Chat Surface (vertical clients) ✅ ACCEPTED 2026-08-07

- **Binds:** Epic 18 / FR-56; PAT auth; rate limiting; cost attribution headers
- **Prevents:** ad-hoc public chat routes without authz, audit, or tenant scope; confusing internal web chat with partner API
- **Rule:**
  - Public routes live under a dedicated prefix (e.g. `/api/v1/workspaces/<workspace_id>/agent-chat/...`) and are **explicitly allowlisted**. Internal web chat routes stay internal.
  - Auth is **PAT (or equivalent machine credential)** with server-enforced scopes: at minimum `workspace_id`; optional `client_id` and `agent_id`. Client-supplied IDs cannot escalate beyond token scope.
  - Every request sets transaction-local DB context for workspace (existing `app.workspace_id`) and, when present, vertical client (`app.current_client_id` per AD-31) **before** any business query.
  - Rate limit per workspace and per client; exceed → `429` + `Retry-After`. Emit low-cardinality metrics; do not log full message bodies by default.
  - Responses carry correlation ids (e.g. `X-Run-Id`) for cost/audit. `external_metadata` on TokenUsage/Run is additive and untrusted for authorization.
  - Security review required before enabling in production. Prompt-injection and tool-exfiltration risks from partner-supplied context must be threat-modeled with AD-30.

### AD-30 — AgentConfig Registry ✅ ACCEPTED 2026-08-07

- **Binds:** Epic 18 / FR-57; UX `ux-contract-agent-registry.md`
- **Prevents:** hard-coded per-vertical prompts in app code; tool allowlists drifting per deploy
- **Rule:**
  - `agent_configs` stores named agents: identity, `system_instructions`, tool allow/deny lists, model preference, citations flag, active flag.
  - **Ownership model (MVP):** platform-superuser managed registry (not end-user workspace CRUD). Whether rows are global or platform-tenant-scoped is decided with AD-31; default recommendation is **platform-scoped with `client_id`**, readable by authorized runtimes, writable only by superuser/admin tools.
  - Missing/inactive `agent_id` → fail closed (`404`), never silently fall through to a more powerful agent.
  - Tool allowlists are **explicit**. New connectors do not auto-enable on existing agents.
  - Prompt injection: `system_instructions` are trusted admin content; still subject to length limits, audit, and no raw secret interpolation from client metadata.

### AD-31 — Vertical Client Tenancy (`client_id`) ✅ ACCEPTED 2026-08-07

- **Binds:** Epic 18 / NFR-MULTI-1; memory recall; TokenUsage/Run attribution
- **Prevents:** cross-vertical-client memory/data leakage inside one workspace; treating `client_id` as a soft ranking boost
- **Rule:**
  - `client_id` is a **hard isolation key orthogonal to `workspace_id`**. Workspace membership alone is insufficient for vertical-client data.
  - Define `client_id` representation before migrations (stable string vs FK to `clients` table). Prefer a first-class `clients` (or `vertical_clients`) table if more than one partner will land.
  - Tables that carry vertical-client data gain nullable `client_id` (NULL = Nowing-internal / web app). The list includes, at minimum: `Memory`, `Run`, `TokenUsage`, `ResearchThread`, `BillingEvent`, plus every Epic 21 table: `Lead`, `LeadSource`, `EnrichmentRequest`, `VerifiedContact`, `SignalEvent`, `SignalSubscription`, `LeadScore`, `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`, `CrmConnection`, `CrmSyncLog`, `OutcomeEvent`, `PricingPlan`.
  - Recall and list paths **hard-filter**:
    - request with `client_id=X` → only rows with `client_id=X`
    - request without `client_id` → only rows with `client_id IS NULL` (or explicit internal scope)
  - Never use `client_id` as a ranking boost. Application bugs must not be the only barrier — prefer DB policy (`current_setting('app.current_client_id')`) composed with workspace RLS.
  - Composite policy order: authenticate → authorize workspace → set workspace RLS context → authorize client scope → set client RLS context → run query.
  - **Blocked:** implementing Stories 18.6/18.8 before this AD is accepted and test-planned (including pooled-connection context reset).
  - **Test plan:** `epic-18-pat-scope-rls-threat-model.md` §4 (L0–L5) — design accepted 2026-08-07.

## Consistency Conventions

| Concern | Convention |
|---|---|
| Naming (Python) | `snake_case` cho modules, functions, variables; `PascalCase` cho classes; `SCREAMING_SNAKE_CASE` cho constants/enums. |
| Naming (TypeScript) | `camelCase` cho variables/functions; `PascalCase` cho components/types; file components dùng `kebab-case`. |
| IDs | `uuid.UUID` cho user, `int` auto-increment cho workspace/document/folder/thread, `UUID` cho purchases. |
| Dates/Times | Lưu UTC `TIMESTAMP(timezone=True)` ở backend; ISO 8601 string ở API; client render theo local timezone. |
| Error shapes | FastAPI trả HTTPException với `detail` string; client hiển thị toast hoặc inline error. |
| State & cross-cutting | Mọi mutation workspace-scoped kiểm tra `workspace_id` và permission; mọi tool call ghi log; mọi async task chạy qua Celery. |
| Config | Biến môi trường tập trung trong `app/config/__init__.py` (backend) và `.env.local` (web). Không hardcode secrets. |

## Stack

Pin actual versions from `pyproject.toml` / `package.json`; do not use "latest".

| Name | Version | Source |
|---|---|---|
| Python | 3.12 | `nowing_backend/pyproject.toml` |
| FastAPI | `>=0.115.8` (current pin) | `nowing_backend/pyproject.toml` |
| SQLAlchemy | 2.x async (requires `psycopg[binary,pool]>=3.3.2`) | `nowing_backend/pyproject.toml` |
| Alembic | `>=1.13.0` | `nowing_backend/pyproject.toml` |
| PostgreSQL | 17+ với pgvector extension | `docker/docker-compose.deps-only.yml: pgvector/pgvector:pg17` |
| Redis | 8+ (cache + Celery broker) | `docker/docker-compose.deps-only.yml: redis:8-alpine` |
| Celery | `>=5.5.3` | `nowing_backend/pyproject.toml` |
| LiteLLM | `>=1.83.7` | `nowing_backend/pyproject.toml` |
| LangChain / LangGraph | `langchain>=1.2.13`, `langgraph>=1.1.3` | `nowing_backend/pyproject.toml` |
| OpenTelemetry | API/SDK/Exporter `>=1.40.0`, semantic-conventions `>=0.61b0` | `nowing_backend/pyproject.toml` |
| Node.js | 20+ (web/desktop); `>=18.0.0 <23.0.0` (browser extension) | `nowing_web/package.json`, `nowing_browser_extension/package.json` |
| Next.js | `^16.1.0` | `nowing_web/package.json` |
| React | `^19.2.3` (web), `18.2.0` (browser extension) | `nowing_web/package.json`, `nowing_browser_extension/package.json` |
| Tailwind CSS | `^4.1.11` | `nowing_web/package.json` |
| Jotai | `^2.15.1` | `nowing_web/package.json` |
| Zustand | `^5.0.9` | `nowing_web/package.json` |
| Tanstack Query | `^5.90.7` | `nowing_web/package.json` |
| Plate.js | `^52.0.17` | `nowing_web/package.json` |
| Electron | `^42.4.0` | `nowing_desktop/package.json` |
| Plasmo | `0.90.5` | `nowing_browser_extension/package.json` |
| Obsidian API | `latest` (plugin API, intentional) | `nowing_obsidian/package.json` |
| MCP SDK Python | `>=1.25.0` | `nowing_backend/pyproject.toml` |

## Structural Seed

```text
/Users/luisphan/Documents/nowing/
├── nowing_backend/                 # Python FastAPI monolith
│   ├── app/
│   │   ├── app.py                  # FastAPI app, middleware, routers
│   │   ├── routes/                 # FastAPI route modules (>40 modules)
│   │   ├── capabilities/           # Built-in scraper capabilities
│   │   ├── agents/                 # Multi-agent chat runtime
│   │   ├── automations/            # Trigger/action/run engine
│   │   ├── connectors/             # OAuth connector logic
│   │   ├── indexing_pipeline/      # Upload, chunk, embed
│   │   ├── etl_pipeline/           # Parsers (Docling, Unstructured, LlamaCloud)
│   │   ├── retriever/              # Hybrid semantic + full-text search
│   │   ├── memory/                 # Long-term memory storage, retrieval, auto-extract
│   │   ├── services/               # Business services (wallet, token tracking, ...)
│   │   ├── tasks/                  # Celery task definitions
│   │   ├── db.py                   # SQLAlchemy models + helpers
│   │   └── config/                 # Config modules
│   ├── alembic/versions/           # Alembic migrations
│   └── tests/                      # Unit/integration/e2e tests
├── nowing_web/                     # Next.js 16 App Router
│   ├── app/                        # Routes (home, dashboard, api, docs)
│   ├── components/                 # UI components (assistant-ui, citation-panel, editor, ...)
│   ├── lib/                        # API clients, auth fetch
│   ├── atoms/                      # Jotai global state
│   ├── zero/                       # Zero sync config
│   └── content/docs/               # Fumadocs docs
├── nowing_desktop/                 # Electron 42 + TypeScript
├── nowing_browser_extension/       # Plasmo + React 18
├── nowing_obsidian/                # Obsidian plugin TypeScript
├── nowing_mcp/                     # MCP server Python
│   └── mcp_server/
│       ├── server.py               # FastMCP composition
│       ├── core/                   # Client, auth, workspace context
│       └── features/               # scrapers, knowledge_base, workspaces, memory
├── nowing_evals/                   # Evaluation harness Python
├── docker/                         # Docker Compose, install scripts
└── docs/                           # Markdown docs (auto-generated)
```

## Capability → Architecture Map

| Capability / Area | Lives in | Governed by |
|---|---|---|
| Auth (email/Google/PAT/session) | `nowing_backend/app/routes/auth_routes.py`, `app/users.py` | AD-2, AD-9 |
| Workspace CRUD + RBAC | `nowing_backend/app/routes/workspaces_routes.py`, `app/db.py` (Workspace, WorkspaceRole, WorkspaceMembership) | AD-9 |
| Built-in scrapers (Reddit, YouTube, ...) | `nowing_backend/app/capabilities/<platform>/` | AD-1, AD-3 |
| **Deep-Research Engine (ChainLens)** — external dependency | `nowing_backend/app/capabilities/chainlens/research/` (executor/definition/schemas), `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/`, `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py`, config `app/config/__init__.py:798-807` | **AD-15**, AD-7 *(không còn AD-3 — amended 2026-07-25)* |
| Deep-research cost metering | `nowing_backend/app/capabilities/chainlens/research/executor.py`, `app/capabilities/core/billing.py`, `app/services/token_tracking_service.py` | AD-15, **AD-8** |
| **Crawler engine (biên BSL 1.1)** — fetcher từng nền tảng, InnerTube, CAPTCHA, session/pool, stealth testbench | `nowing_backend/app/proprietary/**` (84 file, ~16.6k dòng) | **AD-16**, **AD-19**, AD-3 |
| Proxy provider registry + rotation | `nowing_backend/app/utils/proxy/` (registry + providers) | AD-16, **AD-19** |
| **Thang fetch + escalation trang khó** (static → browser → stealth + `solve_cloudflare`) | `app/proprietary/web_crawler/connector.py` (`crawl_url`, `_run_tier_with_proxy_retry`) | **AD-19** |
| **Detect / giải CAPTCHA** — bypass logic (BSL) vs seam vendor (Apache-2.0) | `app/proprietary/web_crawler/captcha.py` · `app/utils/captcha/solvers.py` (2captcha, capsolver) | **AD-19**, AD-16 |
| **Phân loại tường bot** (`BlockType`, additive telemetry) | `app/utils/crawl/classifier.py` | **AD-19** |
| Escalation trang bị chắn → enrichment async *(còn thiếu)* | sẽ chạy trên door `?mode=async` sẵn có; tín hiệu từ engine (`partial` / `insufficientEvidence`) | **AD-19**, AD-17, AD-15 |
| **Screenshot-as-evidence + vision fallback** *(còn thiếu — `grep screenshot app/**/*.py` = 0 hit)* | sẽ chụp tại tier StealthyFetcher (`page_action` đã nhận `page`); đọc bằng `get_vision_llm` đã có; key namespace ảnh **chưa quyết** (`app/file_storage/` hiện document-scoped) | **AD-20**, AD-8, AD-11.1 |
| Memory → scraper-run provenance & re-validation | `nowing_backend/app/services/memory/`, `app/db.py` (Memory.source_capability/source_input/source_run_id) | **AD-11.1** (FR-39 — hiện có defect) |
| **Async capability door** (submit/SSE/replay/cancel/history) — deep research chạy trên đây | `nowing_backend/app/capabilities/core/access/rest.py` (`?mode=async`, `runs/<id>/events`, `cancel`), `core/events.py` (`run_event_bus` + ring buffer 500), `core/progress.py`; client `nowing_web/lib/apis/scrapers-api.service.ts` | **AD-17**, AD-3 |
| Multi-replica bus cho async run *(còn thiếu)* | sẽ đặt Redis pub/sub sau interface `run_event_bus` | **AD-17**, AD-4 |
| Research degradation → hybrid search | `nowing_backend/app/capabilities/chainlens/research/executor.py`, `app/retriever/` | AD-15 |
| External OAuth connectors | `nowing_backend/app/routes/*_add_connector_route.py`, `app/connectors/` | AD-1 |
| External MCP connectors | `nowing_backend/app/routes/composio_routes.py`, `app/routes/mcp_oauth_route.py` | AD-1, AD-7 |
| Knowledge base upload/index | `nowing_backend/app/indexing_pipeline/`, `app/etl_pipeline/`, `app/file_storage/` | AD-2 |
| Hybrid search | `nowing_backend/app/retriever/` | AD-2 |
| Long-term memory storage & retrieval | `nowing_backend/app/services/memory/`, `app/db.py` (Memory, MemoryVersion, MemoryRelation, ResearchThread) | AD-11 |
| **Memory injection vào chat prompt** (đường NÓNG, chặn mọi lượt) | `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` | **AD-18** (NFR-1b — hiện unbounded, bỏ qua HNSW+GIN) |
| **First-run value: research run → memory** | `app/services/memory/extraction.py`, `app/capabilities/core/runs.py` | **AD-18**, `AD-11.1` (FR-40 — `SCRAPER_RUN` chưa có writer) |
| Citation panel | `nowing_web/components/citation-panel/citation-panel.tsx`, `nowing_backend/app/routes/documents_routes.py` | AD-5, AD-6 |
| Multi-agent chat | `nowing_backend/app/agents/chat/multi_agent_chat/` | AD-1, AD-4 |
| MCP memory tools | `nowing_mcp/mcp_server/features/memory.py` | AD-7, AD-12 |
| Research continuity | `nowing_backend/app/agents/chat/multi_agent_chat/` | AD-4, AD-13 |
| Real-time chat/comments | `nowing_backend/app/notifications/`, `nowing_web/zero/`, `app/zero_publication.py` | AD-5 |
| Report / Podcast / Video / Image | `nowing_backend/app/routes/reports_routes.py`, `app/podcasts/`, `app/routes/image_generation_routes.py` | AD-1, AD-2 |
| Automations trigger/run | `nowing_backend/app/automations/` | AD-1 |
| Web client | `nowing_web/` | AD-5, AD-6 |
| Desktop client | `nowing_desktop/` | AD-6 |
| Browser extension | `nowing_browser_extension/` | AD-6 |
| Obsidian plugin | `nowing_obsidian/` | AD-6 |
| MCP server | `nowing_mcp/mcp_server/` | AD-7 |
| Token usage tracking | `nowing_backend/app/services/token_tracking_service.py`, `app/db.py` (TokenUsage) | AD-2, AD-10 |
| Credit wallet | `nowing_backend/app/services/wallet_credit.py`, `app/db.py` (User.credit_micros_balance, CreditPurchase) | AD-2, AD-8 |
| VietnamWorks scraper | `nowing_backend/app/proprietary/platforms/vietnamworks/`, `app/capabilities/vietnamworks/scrape/` | AD-22, AD-3, AD-16, AD-25, AD-26 |
| TopCV scraper | `nowing_backend/app/proprietary/platforms/topcv/`, `app/capabilities/topcv/scrape/` | AD-23, AD-3, AD-16, AD-19, AD-25, AD-26 |
| ITviec scraper | `nowing_backend/app/proprietary/platforms/itviec/`, `app/capabilities/itviec/scrape/` | AD-23, AD-3, AD-16, AD-25, AD-26 |
| Vietnam job aggregator | `nowing_backend/app/services/jobs_aggregator/`, `app/capabilities/vn_jobs/aggregate/` | AD-24, AD-3, AD-8, AD-11.1, AD-25, **AD-27** |
| Canonical entity storage & indexing *(convention, chưa phải engine riêng)* | Follow AD-27 convention trong mỗi domain aggregator; sẽ refactor thành engine khi trigger AD-28 hit | **AD-27**, **AD-28**, AD-2, AD-14 |
| PII redaction (job data) | `nowing_backend/app/services/pii/` (or `jobs_aggregator/pii.py`) | AD-25, AD-11 |

## Deferred / Gaps

Các quyết định kiến trúc được cố ý hoãn lại hoặc chưa có:

### ~~AD-DEFER-1~~ — Citation scroll/highlight trong full document editor  `✅ ĐÓNG 2026-07-25`
- **Status:** **KHÔNG CÒN DEFERRED — đã implement.** Lý do hoãn ghi ở đây đã lỗi thời.
- **~~Reason (lỗi thời)~~:** ~~Citation panel đã cung cấp chunk window với highlight. Để mở full editor đúng chunk cần map `chunkId` -> block/range trong Plate/Monaco và thêm state `chunkId` vào `editorPanelAtom`.~~
- **Verify code 2026-07-25 (readiness check U-4):** `nowing_web/atoms/editor/editor-panel.atom.ts` **đã có** `chunkId: number | null` (dòng 12, 23, 38, 64, 79, 93); logic dùng nó ở `components/editor-panel/editor-panel.tsx` + `components/editor/plugins/citation-kit.tsx`. Story `3-6` = `done` trong `sprint-status.yaml`.
- **Linked PRD:** NFR-6 → đã sửa thành `[DONE]` cùng lượt này.

> **🧹 Dọn section này 2026-07-25 (readiness check + Nhóm 1 remediation).** Bốn AD-DEFER dưới đây đã **lỗi thời** — việc chúng hoãn thì code **đã làm rồi**. Cùng loại lỗi với `AD-DEFER-1`. Verify bằng code trước khi đóng từng cái. Đây đúng là rủi ro mà readiness check tìm ra: tài liệu kiến trúc báo "hoãn" cho thứ đã ship → team lập kế hoạch làm lại.

### ~~AD-DEFER-2~~ — Direct write-back automation actions  `✅ ĐÓNG 2026-07-25`
- **Status:** **ĐÃ IMPLEMENT.** Không còn deferred.
- **~~Reason (lỗi thời)~~:** ~~Agent có thể viết lại Notion/Slack/Linear/Jira trong một `agent_task` bằng agent tools. Direct action types riêng sẽ cần retry/audit/rollback chuyên biệt.~~
- **Verify code:** `app/automations/actions/builtin/__init__.py` import `write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack` — mỗi cái một subpackage tự đăng ký. ⇒ **OQ-5 đã được trả lời trong thực thi: chọn action type riêng.**
- **Linked PRD:** FR-18 → `[DONE]` · Story `6-4` = `done`

### ~~AD-DEFER-3~~ — Per-workspace MCP tool enable/disable toggle  `✅ ĐÓNG 2026-07-25`
- **Status:** **ĐÃ IMPLEMENT.**
- **~~Reason (lỗi thời)~~:** ~~MCP server hiện expose tất cả tools. Thêm toggle đòi hỏi schema `workspace_mcp_tool_enabled` và filter `tools/list`/`tool call` server-side.~~
- **Verify code:** bảng `workspace_mcp_tool_settings` (`app/db.py:1945`, unique constraint `uq_workspace_mcp_tool` dòng 1950) · migration `175_add_workspace_mcp_tool_settings.py` · `McpToolGroup` + catalog trong `app/mcp_tools.py`.
- **Linked PRD:** OQ-4 → `[DONE]` · Story `2-5` = `done`

### AD-DEFER-4 — Data retention & lifecycle per workspace  `⚠️ PARTIAL 2026-07-25 — schema đã có, legal còn mở`
- **Status:** **không còn deferred hoàn toàn.** Schema + enforcement đã có; phần **legal/right-to-delete cho MEMORY** mới là chỗ còn mở.
- **Verify code:** migration `176_add_document_retention.py` · `Workspace.document_retention_days` (`app/db.py:1804`), `auto_archive_enabled` (dòng 1805) · cron `apply-document-retention-policies` (xem `merge-to-prod-checklist.md` G5 — **automation xoá dữ liệu, chạy ngay khi deploy**).
- **Còn mở thật:** retention + right-to-delete cho `memories`/versions/relations (khác doc retention) · phơi nhiễm ToS/bản quyền/PII cho dữ liệu scrape lưu dài hạn · tách trách nhiệm self-host vs cloud. **Chốt trước GA cloud.**
- **Linked PRD:** OQ-3 `[GAP]` · Story `3-7` = `done` (phần doc retention)

### ~~AD-DEFER-5~~ — Usage & credit dashboard  `✅ ĐÓNG 2026-07-25`
- **Status:** **ĐÃ IMPLEMENT** (cả API lẫn UI).
- **~~Reason (lỗi thời)~~:** ~~Dữ liệu `TokenUsage`/`credit_micros_balance` đã có nhưng chưa có aggregate API và UI.~~
- **Verify code:** `app/routes/usage_routes.py` (`APIRouter(prefix="/usage")`) · UI `nowing_web/app/dashboard/[workspace_id]/usage/`.
- **Linked PRD:** NFR-7 / FR-31 → `[DONE]` · Story `8-3` = `done`

### ~~AD-DEFER-6~~ — Memory-driven automation triggers (`memory_change`, `continue_research`)  `✅ ĐÓNG 2026-07-25`
- **Status:** **ĐÃ IMPLEMENT.**
- **~~Reason (lỗi thời)~~:** ~~`AutomationTrigger` hiện chỉ có `schedule` và `event`; thêm `memory_change` đòi hỏi event stream từ `Memory` writes và action handler mới. Nên deferred post-MVP.~~
- **Verify code:** `triggers/builtin/__init__.py`: `from . import event, memory_change, schedule` · `triggers/builtin/memory_change/` (`params.py`, `selector.py` — có guard *"a memory-writing automation cannot re-fire a matching `memory_change` trigger"*) · `actions/builtin/continue_research/` · `AutomationRun.research_thread_id` (`app/db.py:712`, relationship dòng 746) · `dispatch/launch.py:44` `resolve_research_thread_id`.
- **Linked PRD:** FR-35 → `[DONE]` · Story `6-5` = `done`

### AD-DEFER-7 — Owned web index / crawl-at-scale: OUT OF SCOPE (không phải "hoãn")
- **Status:** **NON-GOAL**, không phải deferred-with-intent. Khác các AD-DEFER khác trong section này.
- **Rule:** Nowing **không** xây owned web index, không xây crawl-at-scale corpus, và **không** bán research data như một sản phẩm dữ liệu. Deep open-web research đến từ ChainLens (AD-15), mà bản thân ChainLens là **orchestrator gọi provider** (Brave / Jina / Exa / Tavily / Perplexity Sonar / SearXNG) + extraction per-URL (Jina Reader / Firecrawl / Crawl4AI) — **không** phải index riêng.
- **Reason (evidence, verified 2026-07-25):**
  - ChainLens `epic-26-gate-tracking.md` (pre-indexed hybrid search): **DEFERRED — 0 of 7 gates passing**. Gate 1 demand ≥5K q/day = UNKNOWN; Gate 3 & 6 = *"infrastructure doesn't exist"*.
  - `prd-epic-vs-exa-coverage-2026-07-23.md`: *"Owned index | Out of scope P3 | ❌ | Exa tự xây index; Chainlens dùng providers"*.
  - Mô hình kinh doanh của Exa **là** owned index. Bán lại thứ đang mua, ở giá đã commoditize (~$7/1k), đấu specialist có vốn (Tavily→Nebius $400M, 2/2026) = arbitrage âm biên.
  - `chainlens-direction-decision-brief-2026-07-24.md` §11: corpus moat không đáng xây cho team nhỏ — Stack Overflow đã khoá crawl (pay-per-crawl 2/2026, mất quyền là retroactive); a16z *"Empty Promise of Data Moats"*.
- **Hệ quả cho latency:** kế hoạch giảm latency deep-research **không được dựa vào index search**. Ba đòn bẩy hợp lệ nằm trên ChainLens Epic 43 — `43-5` semantic cache hit-rate, `43-2` planner-DAG parallel sub-research (lever lớn nhất), `43-4` multi-stage rerank — cộng `29-5` cost routing (done). Xem NFR-9.
- **Muốn mở lại?** Phải qua SCP mới, và điều kiện tối thiểu là ChainLens Epic 26 pass các gate của nó trước.
- **Linked PRD:** §2.4 NG-1 / §6.2 / NFR-9

*(`AD-REMOVED — AI File Sorting` đã chuyển về `## Invariants & Rules` để không trùng lặp — 2026-07-25.)*

---

### AD-32 — Connector management: dedicated page là canonical, modal deprecated  `✅ ACCEPTED 2026-08-08`

- **Binds:** Story 7-4 (dedicated connectors layout), Story 7-7 (MCP tool expansion), mọi future connector management UI
- **Prevents:** Hai surface quản lý connector song song (modal + page) → maintenance gấp đôi, UX không nhất quán, hook chạy 2 lần
- **Context (verified 2026-08-08):**
  - Story 7-4 đã ship `/dashboard/<workspace_id>/connectors` — dedicated page với rail + detail pane.
  - `connector-popup.tsx` (modal, 388 dòng) vẫn render trên mọi page khác qua `ConnectorIndicator` trong `client-layout.tsx`.
  - Composer "+" (Story 7-4 pass 2) dùng `importConnectorRequestAtom` → vẫn mở modal cho connector cụ thể, nhưng "Browse all" → navigate đến page.
  - `ConnectorDetailPane` reuse `useConnectorDialog` hook — hook consume atom, set `isOpen=true`. Trên `/connectors` page, modal bị ẩn (`!isConnectorsPage`) nhưng hook vẫn chạy.
  - Kết quả: 2 UX khác nhau (edit trong modal vs edit trong page), hook chạy kép, maintenance gấp đôi.
- **Rule:**
  - **Dedicated page (`/connectors`) là canonical surface** cho connector management — connect, edit, accounts, indexing config, periodic sync, vision LLM.
  - **Modal deprecated theo 3 phase:**
    - **Phase 1 (ngay, Story 7-4 pass 3):** Composer "+" MCP submenu → `setImportRequest` chỉ navigate đến `/connectors?type={connectorType}`, không mở modal. `importConnectorRequestAtom` trở thành deep-link trigger cho page, không còn trigger cho modal.
    - **Phase 2 (next sprint):** `ConnectorIndicator` chỉ render trigger button (badge/indicator), click → navigate đến `/connectors`. Modal content (`connector-popup.tsx` view routing section) gỡ bỏ.
    - **Phase 3 (cleanup):** `useConnectorDialog` hook tách thành `useConnectorOperations` (mutations: create/update/delete/index) + `useConnectorRouting` (view state). Page dùng cả hai; modal code xóa hoàn toàn.
  - **`importConnectorRequestAtom` giữ nguyên** — nó là deep-link contract (`{connectorType, mode}`), page consume nó để auto-route (0→connect, 1→edit, many→accounts).
  - **Composer "+" submenu** giữ flat connector list + "Browse all integrations" — nhưng click connector → navigate, không mở modal.
- **Trade-offs:**
  - **(A) Deprecate modal hoàn toàn (chọn):** Mọi connector management → page. UX nhất quán, maintenance giảm. Trade-off: mất "quick connect" inline trong chat — user phải rời chat page để connect. Acceptable vì connector connect là rare action, không phải frequent.
  - **(B) Giữ modal làm "quick connect":** Modal chỉ cho connect mới, edit/manage → page. Trade-off: vẫn 2 surface, hook vẫn chạy kép, phải tách logic. Phức tạp hơn (A).
- **Migration path:** `ConnectorDetailPane` đã reuse `useConnectorDialog` hook → Phase 1 chỉ cần thay `setImportRequest` handler trong composer "+" từ "mở modal" sang "navigate to page". Mechanical change.
- **Linked PRD:** FR-6, FR-7, FR-8 · Story `7-4` = `review` · Story `7-7` = `review`

### AD-33 — Generic Alert Engine: một scheduler cho tất cả domain alerts  `✅ ACCEPTED 2026-08-08`

- **Binds:** Story 12-6 (job alerts), 12-7 (property price alerts), 14-3 (news alerts), 15-3 (stock alerts), 15-4 (financial trend), 16-3 (company alerts), 17-3 (price drop alerts), 17-4 (competitor tracking), **Story 21.1 (intent signal detection)**, **Story 21.4 (signal-driven sequence triggers)**
- **Prevents:** 8 stories × independent scheduler + diff logic + notification dispatch = 8 implementation trùng lặp, 8 cron jobs, 8 notification path
- **Context (verified 2026-08-08):**
  - Epic 6 đã có Automation infrastructure: scheduler (cron-based), RunService, capability execution, notification dispatch (in-app + Telegram).
  - 8 stories backlog đều là cùng 1 pattern: "query định kỳ → so sánh delta → notify nếu thay đổi."
  - Nếu build độc lập → 8 scheduler, 8 diff logic, 8 notification path, 8 user preference schema.
- **Rule:**
  - **Alert Engine là một Automation template type**, không phải service mới. Dùng Epic 6 scheduler + RunService + notification dispatch.
  - **`AlertRule` là data, không phải code:**
    ```python
    AlertRule = {
      capability_id: str,       # registered Capability ID (e.g. "vn_jobs.aggregate", "bds_aggregator", "funding.signal"). Must exist in CapabilityRegistry.
      query: dict,              # structured query cho capability
      schedule: str,            # cron expr (e.g. "0 9 * * 1" = every Monday 9am)
      diff_strategy: str,       # "new_items" | "price_change" | "threshold_cross" | "trend_detect"
      threshold: dict | None,   # cho threshold_cross: {"field": "price", "op": "<", "value": 1000}
      notification_channels: list[str],  # ["in_app", "telegram", "email", "sequence_enrollment"]
      target: dict | None,      # for "sequence_enrollment": {"sequence_id": uuid, "step_id": uuid | None}
    }
    ```
  - **Capability registration required:** `capability_id` must match a registered capability. Signal capabilities register `emits_signals=true` (AD-37); lead-source capabilities register `emits_leads=true` (AD-39).
  - **Notification channels:** `in_app`, `telegram`, `email` (subject to legal gate), `sequence_enrollment` (triggers AD-39 sequencer). Do not invent new channels per story.
  - **4 diff strategies builtin** (không thêm nữa trừ khi Rule of Three):
    - `new_items`: query → so sánh với last snapshot → notify items mới. Dùng cho 12-6 (job alerts), 14-3 (news alerts).
    - `price_change`: query → so sánh price field với last snapshot → notify nếu delta > threshold. Dùng cho 12-7 (property), 15-3 (stock), 17-3 (price drop).
    - `threshold_cross`: query → so sánh field với threshold → notify nếu cross. Dùng cho 15-4 (trend), 16-3 (company events).
  - **Mỗi story 12-6/12-7/14-3/15-3/15-4/16-3/17-3/17-4 chỉ đăng ký một `AlertRule` template** — không viết scheduler riêng, không viết notification dispatch riêng.
  - **User preferences:** một table `alert_subscriptions` (user_id, alert_rule_template_id, channels, enabled). Không 8 table riêng.
  - **Snapshot storage:** `alert_snapshots` (alert_rule_id, snapshot_json, created_at). Diff logic đọc last snapshot, compare, notify, write new snapshot.
- **Trade-offs:**
  - **(A) Generic Alert Engine (chọn):** 1 scheduler, 1 diff framework, 1 notification path. 8 stories = 8 AlertRule templates (data). Trade-off: upfront cost xây engine (~2-3 days) trước khi story đầu tiên có thể dev. Nhưng save 8× implementation sau.
  - **(B) Build độc lập từng story:** Nhanh cho story đầu tiên, nhưng story thứ 2+ phải duplicate. Tech debt tích lũy. Không chọn.
- **Dependency:** Cần Epic 6 scheduler đã stable (✅ done). Alert Engine là extension của Automation, không phải rewrite.
- **Migration path:** Story 12-6 (job alerts) là first consumer — build Alert Engine cùng lúc với 12-6. Stories sau chỉ đăng ký template.
- **Linked PRD:** FR-44 (job alerts), FR-49 (news alerts), FR-50 (stock alerts), FR-51 (company alerts), FR-52 (price alerts) · Epic 6 (Automations) = `done` · Epic 12 stories 12-6→12-9 = `backlog`

---


### AD-34 — Nowing Scraper Feed Contract (NEW 2026-08-08)

- **Binds:** All `Nowing` scraper and aggregator capabilities
- **Prevents:** Ingestion protocol divergence between `Nowing` and `chainlens-research`
- **Rule:**
  - Each `Nowing` scraper/aggregator implements a `to_chunks()` step that returns `Chunk[]`.
  - `Chunk` uses the canonical schema from `@chainlens/types`: `content` (string) + `metadata` (strict) with required `source`, `sourceId`, `domain`, `fetchedAt`, `contentType`.
  - `source` enum is owned by `chainlens-research`: `public_crawl`, `nowing_scraper`, `brave`, `searxng`, `jina`, `exa`, `tavily`, `perplexity`, `private_provider`. `Nowing` scrapers set `source: 'nowing_scraper'` and `domain` to the vertical domain (e.g. `bds`, `vn_jobs`, `news`, `finance`, `company`, `ecommerce`).
  - `Nowing` calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth. Batches are idempotent keyed by `sourceId`.
  - On success `chainlens-research` returns `ingestJobId`; `Nowing` may surface this in `Run`/`ResearchThread` provenance.


### AD-35 — Nowing Does Not Build Public/Vertical Search Corpus (NEW 2026-08-08)

- **Binds:** `Nowing` `Memory`, `ResearchThread`, aggregators, and any product state
- **Prevents:** `Nowing` duplicating `chainlens-research` index; chat/agent queries bypassing the canonical engine
- **Rule:**
  - `Nowing` may keep `Memory` rows for private user facts, chat context, and extracted semantic memories (`source_type` = `document`, `chat_message`, `scraper_run_fact`). These live in `Nowing` and are exposed via `NowingPrivateProvider` on demand.
  - `Nowing` may keep raw scraper run logs and aggregation provenance for product state/billing.
  - `Nowing` does **not** expose a search/filter API over BĐS, jobs, news, finance, or company listings from its own index. All user-facing search for public/vertical data goes through `chainlens-research`.


### AD-36 — Waterfall enrichment: buy via API, không build 14+ provider integrations `[ADOPTED 2026-08-10 — validation required before dev]`

- **Binds:** FR-65 (Enriched Contact Data), Epic 21
- **Prevents:** Build và maintain 14+ email/phone provider integrations trong `app/proprietary/`
- **Rule:**
  - Enrichment requests gọi external waterfall API (Cleanlist/BetterContact) qua Celery async tasks
  - Pay-per-result pricing: chỉ trả khi verified data returned
  - Cache verification results (TTL: 30 days) trong Redis để tránh re-query
  - Fallback: nếu primary API down, dùng basic verification (MX check + pattern matching)
- **Data flow:**
  ```
  Lead discovered → Celery task → Waterfall API → Verified? → Cache + Store in Memory
                                                       ↓ No
                                                  Next provider → ... → Exhausted → Flag low confidence
  ```
- **New models:**
  - `EnrichmentRequest` (id: UUID, workspace_id, client_id, lead_id, status, provider_results, cost_micros)
  - `VerifiedContact` (id: UUID, workspace_id, client_id, lead_id, email, phone, verification_status, confidence, source_provider)
- **BillingEvent.usage_type mở rộng:** thêm `contact_enrichment` (do not put business events in `TokenUsage`).
- **Enforcement:** Before any verified contact data is embedded or stored, `EnrichmentService` **must** call `app/services/pii/redact.py` (`context="lead_enrichment"`) per **AD-25**. Do not create a separate lead PII redaction module.

---

### AD-37 — Signal detection framework: hybrid build + buy data feeds `[ADOPTED 2026-08-10 — validation required before dev]`

- **Binds:** FR-63 (Intent Signal Detection), Epic 21
- **Prevents:** Build 8+ independent scheduler/notification paths (giống AD-33 Anti-Pattern); building a separate bespoke knowledge graph for signals
- **Rule:**
  - **Signal Engine là một AlertRule template type** (governed by AD-33), không phải service mới.
  - **Signal types → capability_id mapping:** Each signal type is produced by one registered capability:
    - `funding` → `funding.signal` (Crunchbase/TechCrunch feeds + web scrape)
    - `hiring` → `hiring.signal` (consumes `vn_jobs.aggregate` or other job scraper `Chunk[]`)
    - `tech_stack` → `tech_stack.signal` (website change detection)
    - `executive_move` → `executive_move.signal` (LinkedIn monitoring)
    - `news` → `news.signal` (News API + RSS)
  - **Signal capabilities register themselves** in `CapabilityRegistry` with `emits_signals=true` and `signal_types=[...]`. `AlertRule.source` is the `capability_id` (e.g. `hiring.signal`).
  - **Signal storage:** `SignalEvent` is the canonical signal table. It stores a **pointer** (`chunk_id`/`source_url`) to the public/vertical data in `chainlens-research` (AD-27/AD-35), plus derived metadata (company, signal_type, confidence, detected_at). It does **not** duplicate the full public document into a second Nowing-owned corpus.
  - **Memory row:** A `Memory` row of type `semantic` + tag `lead_signal` is created from a **redacted summary** of the signal (per AD-25) with `source_input` pointing to the original `chunk_id`/`capability`/`input`, so it participates in workspace RAG without becoming a public search index.
  - **Signal → Lead Score:** High-confidence signals boost lead scoring (governed by AD-38).
  - **Notification:** Reuse AD-33 notification dispatch. `AlertRule.notification_channels` may include `in_app`, `telegram`, `sequence_enrollment` (AD-39), `email` (subject to legal gate).
  - **Monitoring frequency:** Daily scan + real-time webhooks for funding events.
- **New models:**
  - `SignalEvent` (id: UUID, workspace_id, client_id, company_name, signal_type, source_url, chunk_id, confidence, detected_at, processed)
  - `SignalSubscription` (id: UUID, workspace_id, client_id, signal_types, notification_channels)
- **Enforcement:**
  - Signal scheduler, diff, and notification dispatch **must** use AD-33 `AlertRule` and `Automation` runtime.
  - Signal ingestion **must** write a `SignalEvent` and a redacted `Memory` row; no separate `signals` search index or vector store.
  - Signal jobs **must** be registered as `CapabilityRegistry` capabilities with `emits_signals=true` so they are metered and billed like any other capability.

---

### AD-38 — Lead scoring engine: composite fit + intent scoring `[ADOPTED 2026-08-10 — validation required before dev]`

- **Binds:** FR-64 (Lead Scoring & Prioritization), Epic 21
- **Prevents:** Rule-based scoring không capture non-obvious signals
- **Rule:**
  - **Composite score = Fit (50%) + Intent (50%)**
  - **Fit score:** Firmographics (company size, industry, location, tech stack) + ICP match
  - **Intent score:** Signal strength (funding, hiring, tech stack changes) + recency
  - **Scoring method:**
    - Weighted scoring system (configurable per workspace)
    - RAG-based similarity matching against converted leads
    - AI reasoning + rule fallback
  - **Output:** Hot / Warm / Cold classification + numeric score (0-100)
  - **Storage:** `LeadScore` (id: UUID, workspace_id, client_id, company_name, score, fit_score, intent_score, factors_json, computed_at)
- **Integration with Memory:** Lead scores stored as `Memory` rows with type `semantic` + tags `lead_score` (redacted summary of factors, per AD-25).
- **BillingEvent.usage_type mở rộng:** thêm `lead_scoring` (do not put business events in `TokenUsage`).

---

### AD-39 — Sequencer: email-first outreach; multi-source lead ingestion `[REVISED 2026-08-11 — validation: email-outreach legal/ToS; lead-source registry]`

- **Binds:** FR-66 (Outbound Prospecting Automation), Epic 21
- **Prevents:** Build separate outreach tools per channel; hard-coding lead sources
- **Rule:**
  - **Sequence is a new bounded context, not an `Automation` subtype.** `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun` are first-class tables. The **only** reuse from Epic 6 is the scheduler/Celery execution pattern and the notification dispatcher; the data schema is **not** shared with `Automation`/`AutomationRun`.
  - **Sequence builder:** Multi-step sequences (trigger → wait → action → condition → action). A step is one of: `send_email`, `wait`, `condition`, `update_lead_score`, `update_crm`, `tag`.
  - **Outbound channel (MVP):** Email only (SMTP/SES, reuse existing email infrastructure). `linkedin`/`zalo` reserved in enum but **disabled in MVP**.
  - **Lead source:** Leads can be generated from any workspace capability that emits `Lead` records. A lead-source capability **registers itself** in `CapabilityRegistry` with `emits_leads=true`; `LeadSource` is a **derived cache** (not a separate source of truth) updated by the ingestion pipeline.
  - **Lead ingestion:** A single `lead_extractor` capability consumes `Chunk[]`/typed records from scrapers and normalizes to `Lead` rows. It is the **only** writer of `Lead` and `LeadSource`.
  - **Personalization:** AI-generated messages using lead context + ICP + intent signals.
  - **Tracking:** Delivery, open, reply, meeting booked → feedback loop to lead scoring. Each event is a `SequenceEvent` AND a `BillingEvent` (AD-42).
  - **Compliance:** Unsubscribe handling, rate limiting, email outreach legal/ToS. Email sending disabled until legal gate closes.
- **New models** (all with `workspace_id`; see AD-31 for `client_id`):
  - `Lead` (id: UUID, workspace_id, client_id, source, source_url, company_name, domain, industry, fit_score, intent_score, status, enriched, created_at)
  - `LeadSource` (id, workspace_id, client_id, provider, enabled_for_leads, last_ingest_at, lead_count)
  - `Sequence` (id: UUID, workspace_id, client_id, name, trigger_type, status)
  - `SequenceStep` (id: UUID, sequence_id, step_order, step_type, channel, template, wait_duration, condition)
  - `SequenceEnrollment` (id: UUID, sequence_id, lead_id, status, current_step, enrolled_at)
  - `SequenceEvent` (id: UUID, enrollment_id, event_type, channel, metadata, created_at)
  - `SequenceRun` (id: UUID, workspace_id, client_id, sequence_id, enrollment_id, status, started_at, completed_at) — used for cost/audit, **not** `AutomationRun`.
- **Enforcement (cross-epic reuse):**
  - `Sequence`/`SequenceStep` use **new tables**; do not reuse `Automation`/`AutomationRun` schema literally. `AutomationRun.id` is `int` and `TokenUsage.run_id` is UUID — these are incompatible for cost attribution.
  - Sequencer scheduling/execution/retry **must** use the Epic 6 pattern (Celery task, `RunService`-style executor, idempotency, retry) but **on the `SequenceRun` model**, not `AutomationRun`.
  - Positive-reply/delivery/delivery-failure notifications **must** reuse the Story 11.1 notification dispatcher by adding `email_reply`, `email_delivered`, `email_bounced` to `NotificationChannel` and implementing an inbound email handler (SES webhook or IMAP idle) as a capability.
  - Lead source discovery **must** query `CapabilityRegistry` metadata (`emits_leads`); do not hard-code a source list.
  - Signal-driven sequence triggers **must** be implemented as AD-33 `AlertRule` templates with `notification_channels` containing `sequence_enrollment` (AD-33).
- **Ghi chú:** Start email-only. LinkedIn/Zalo may be added later behind feature/ToS gates.

---

### AD-40 — CRM integration: bidirectional sync, read-first pattern `[ADOPTED 2026-08-10 — validation required before dev]`

- **Binds:** FR-67 (CRM Integration & Write-Back), Epic 21
- **Prevents:** CRM sync failures gây data inconsistency
- **Rule:**
  - **Phase 1: Read-only dedup** (giống Origami)
    - Match incoming leads against existing CRM contacts by email, domain
    - Flag duplicates before they reach CRM
    - Generate CRM context document for agent understanding
  - **Phase 2: Write-back**
    - Push verified leads to CRM (Salesforce, HubSpot)
    - Map Nowing fields to CRM properties (configurable)
    - Support lead assignment rules
  - **Phase 3: Bidirectional sync**
    - CRM updates → Nowing (contact changes, deal stages)
    - Nowing updates → CRM (lead scores, signals, enrichment)
  - **Conflict resolution:** Last-write-wins with audit log
- **Integration pattern:** OAuth 2.0 + webhooks for real-time sync
- **New models:**
  - `CrmConnection` (id: UUID, workspace_id, client_id, provider, credentials_encrypted, sync_config, last_sync_at)
  - `CrmSyncLog` (id: UUID, workspace_id, client_id, connection_id, direction, entity_type, entity_id, status, error_message, synced_at)
- **Ghi chú:** Reuse existing OAuth connector infrastructure (AD-3, FR-7)

---

### AD-41 — Zalo/LinkedIn channels: deferred out of MVP `[DEFERRED 2026-08-11]`

- **Binds:** FR-68 (Zalo Integration), Epic 21
- **Prevents:** Premature build of channels that lack legal/ToS/business verification gates
- **Rule:**
  - **Zalo/LinkedIn are disabled in MVP.**
  - AD-39 `channel` enum reserves `zalo` and `linkedin` values, but UI/ sequencer rejects them with a clear "deferred" message until this AD is re-activated.
  - **Future activation conditions:**
    - Zalo OA business verification complete
    - Zalo business messaging ToS review + Decree 356 compliance sign-off
    - LinkedIn automation legal/ToS review (API vs browser automation)
- **New models (design only; do not build in MVP):**
  - `ZaloConnection` (id: UUID, workspace_id, client_id, oa_id, access_token_encrypted, refresh_token_encrypted)
  - `ZaloMessage` (id: UUID, workspace_id, client_id, lead_id, direction, content, status, sent_at, delivered_at, read_at)
- **Ghi chú:** Do not build Zalo/LinkedIn senders in MVP. Keep UI extensible so they can be enabled via feature flag later.

---

### AD-42 — Outcome-based pricing: pay per meeting/lead support `[ADOPTED 2026-08-10 — validation required before dev]`

- **Binds:** FR-69 (Outcome-Based Pricing Option), Epic 21
- **Prevents:** Pricing model không align với customer value
- **Rule:**
  - **Dual pricing model:**
    - Seat-based (existing): $29/mo (Starter), $99/mo (Pro), Custom (Enterprise)
    - Outcome-based (new): $50/meeting booked, $0.50/lead enriched
  - **Tracking:**
    - Meeting booked = calendar event created from Nowing outreach
    - Lead enriched = verified contact data delivered
  - **Billing:** Reuse existing credit wallet (`User.credit_micros_balance` per AD-8) + Stripe integration.
  - **Attribution:** First-touch attribution (sequence that started the journey).
  - **Business-event ledger (new):** `BillingEvent` is the canonical ledger for non-LLM business events (`contact_enrichment`, `lead_scoring`, `outcome_meeting_booked`, `outcome_lead_enriched`, `signal_scan`). `BillingEvent` debits `User.credit_micros_balance` via the same wallet service (AD-8). `TokenUsage` remains strictly for LLM token consumption (prompt/completion tokens) and is not overloaded.
  - **Enforcement:** `BillingEvent` is a new table (see New models), but it **reuses the existing wallet and attribution pattern** from AD-8. Outcome dashboard reuses the usage/credit UI from Story 8.3.
- **New models:**
  - `BillingEvent` (id: UUID, workspace_id, client_id, user_id, event_id: UUID, event_type: `contact_enrichment` | `lead_scoring` | `outcome_meeting_booked` | `outcome_lead_enriched` | `signal_scan` | `email_send`, cost_micros, currency, cost_basis, created_at) — the single ledger for non-LLM business events. Links to `User.credit_micros_balance` (AD-8).
  - `OutcomeEvent` (id: UUID, workspace_id, client_id, event_type, lead_id, sequence_id, billing_event_id, attribution, cost_micros, created_at)
  - `PricingPlan` (id: UUID, workspace_id, client_id, plan_type, seat_price, outcome_rates_json, billing_period)
- **Ghi chú:** Đây là pricing strategy, không phải technical architecture — nhưng cần infrastructure support

---

## Implementation Readiness

**Status:** 🟡 Ready to start cross-project implementation **after** the following are closed.

| # | Gate | State | Story / Artifact |
|---|---|---|---|
| 1 | AD-34 — scraper feed contract (`to_chunks()` + `POST /v1/ingest/scraper`) | Spec complete; needs Nowing-side story assignment | `Epic 20` (created) · `Story 20.1` |
| 2 | AD-4 — gap-fill caller (Nowing side) | Spec complete | `Story 20.2` |
| 3 | AD-5 — `NowingPrivateProvider` | Spec complete | `Story 20.3` |
| 4 | AD-19 — anti-bot screenshot escalation | Open | `Story 10.5` (P0) |
| 5 | AD-18 — bounded memory injection | Verified implemented; needs perf regression gate | `Story 3.17` |
| 6 | AD-11.1 — memory provenance re-validation | Verified implemented; needs E2E gate | `Story 9.6c` |
| 7 | Epic 13 deprecated code with P0 defects | Dropped; do not merge until cleaned | `deferred-work.md` |

**Recommended start order:**
1. `Story 47-1` (chainlens-research canonical `Chunk` schema + `source` enum) — foundation; no blocker.
2. `Story 47-2` (chainlens-research service auth + cost allocation) — trust boundary for all cross-project calls.
3. `Story 20.4` (Nowing service auth + cost ledger sync) — parallel with `47-2`; shared secret + `TokenUsage` mapping.
4. `Story 47-3` (chainlens-research `POST /v1/ingest/scraper`) + `Story 20.1` (Nowing `to_chunks()` + `NowingIngestService`) — parallel; `20.1` consumes `47-1` schema and `47-2`/`20.4` auth.
5. `Story 47-4` (chainlens-research `POST /v1/gap-fill`) + `Story 20.2` (Nowing gap-fill caller) — after `47-3`/`20.1`.
6. `Story 47-5` (chainlens-research `NowingPrivateProvider`) + `Story 20.3` (Nowing private provider client) — after `47-4`/`20.2`.
7. `Story 47-IT1` (cross-project integration test gate) — after `47-1`..`47-5` and `20.1`..`20.4`.
8. `Story 10.5` (AD-19 anti-bot screenshot escalation) — P0 for HR/BĐS vertical; can run in parallel with Epic 20.
