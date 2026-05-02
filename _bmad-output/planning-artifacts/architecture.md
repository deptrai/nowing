---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-05-01T00:00:00+07:00'
lastUpdated: '2026-05-01'
editHistory:
  - date: '2026-05-01'
    changes: 'Senior Architect Critical Review: Triaged 10 proposals into 3 tiers (Implement/Revise/Reject). Rejected #2 Dynamic Pacing (oscillation risk), #6 Prompt Cache Hash (5min TTL auto-expire), #7 Adaptive ETA (over-engineered). Revised #4 Breaker (Redis primary, not fallback), #9 Lock (reduce TTL, no bypass), #10 Quota (add client-side expiry check). Added #11 HTTP/2 multiplexing, #12 Shared breaker state, #13 Stale data indicator, #14 Orchestra graceful shutdown (deferred). Identified 5 architectural gaps: browser SSE connection limits, circuit breaker worker isolation, Zero-sync stale data, quota bypass via IndexedDB, graceful shutdown.'
  - date: '2026-05-01'
    changes: 'Adversarial Review Resolutions: (1) Redis-based Global Circuit Breaker. (2) Outbound Pacing Middleware. (3) Global Tool Error Decorator. (4) Optimistic Fallback (500ms). (5) Crypto Cache Workspace Isolation (search_space_id). (6) Vector DB Scaling ADR.'
  - date: '2026-04-23'
    changes: 'Thêm Crypto Orchestra Architecture: (1) Per-agent SSE event contract (6 event types, resolve 4 open questions từ UX handoff §3). (2) ParallelismTelemetryMiddleware design (Story 0.5). (3) Circuit breaker + graceful degradation (Story 0.6). (4) Tool registry pattern cho 11 crypto tools (Story 0.1). (5) Multi-agent orchestration prompt architecture (Story 0.3). (6) NFR-Q1..Q4 measurement architecture. (7) Resolved 5 open design questions từ UX handoff §7. (8) C4-inspired component diagram cho 11-agent orchestration.'
  - date: '2026-04-18'
    changes: 'Fix Chainlens Integration Architecture: (1) Health check đổi sang /api/v1/b2b/health (public, không cần auth) — /api/config yêu cầu Supabase session nên không dùng được. (2) B2B route ĐÃ CÓ AUTH qua middleware (Bearer token + rate limit 120req/min + daily quota) — sửa lại nhận định trước đó. (3) Tool registration đổi sang ToolDefinition + BUILTIN_TOOLS registry (đúng pattern thực tế). (4) CHAINLENS_RESEARCH_API_KEY bắt buộc vì B2B yêu cầu Bearer auth.'
  - date: '2026-04-16'
    changes: 'Thêm Gift Subscription Architecture: Data Architecture (gift_codes/gift_requests tables), API Patterns (3 endpoints mới), Project Structure (new files), Integration Points (gift flow)'
inputDocuments: [
  "/Users/luisphan/Documents/GitHub/Nowing/_bmad-output/planning-artifacts/prd.md",
  "/Users/luisphan/Documents/GitHub/Nowing/_bmad-output/planning-artifacts/research/technical-gift-subscription-research-2026-04-16.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/index.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/architecture-backend.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/architecture-web.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/integration-architecture.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/deployment-guide.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/development-guide.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/api-contracts.md",
  "/Users/luisphan/Documents/GitHub/Nowing/docs/data-models.md"
]
workflowType: 'architecture'
project_name: 'Nowing'
user_name: 'Luisphan'
date: '2026-04-13'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
14 Functional Requirements (FRs) tập trung vào các domain chính sau:
- Xử lý dữ liệu (Document Ingestion, OCR, Chunking, Vector Storage).
- AI & Search (Hybrid Search, Graph RAG, Agentic reasoning, streaming response).
- Giao diện và tương tác (Streaming UI, Local-first caching, Offline mode).
- Cơ chế đồng bộ (Zero-sync giữa IndexedDB và Postgres).
=> Kiến trúc phân tán (Distributed) rõ rệt: xử lý nặng diễn ra ở Backend (FastAPI + Celery), còn tính năng Offline/Real-time yêu cầu Front-end (Next.js) phải có bộ đệm mạnh mẽ và đồng bộ liên tục.

**Non-Functional Requirements:**
7 NFRs đặc biệt nhấn mạnh vào hiệu năng và bảo mật:
- Performance: TTFT (Time To First Token) < 1.5s; Sync Latency < 3.0s. Định tuyến dữ liệu phải tối ưu (WebSockets/SSE) và khả năng caching tỉnh vượt trội.
- Security: Row-level Security (RLS) để cô lập dữ liệu người dùng, xóa cache local tự động ngay khi logout.
- Offline-first: Logic và state UI phải hoạt động liền mạch ngay cả khi rớt mạng.

**Scale & Complexity:**
- Độ phức tạp của dự án (Complexity level): Mức độ Cao (High).
- Miền kỹ thuật chính (Primary domain): Full-stack Web3/AI (Next.js + FastAPI + Background queues).
- Số lượng Component ước tính: ~5 khối lớn (Web Client, API Gateway, Async Workers, Vector DB, Realtime Sync Service).

### Technical Constraints & Dependencies

- Giao thức đồng bộ: Bắt buộc sử dụng framework `@rocicorp/zero` ở front-end và xử lý JWT Auth tương ứng.
- AI Models & Frameworks: Cần tích hợp với hệ thống RAG pipeline qua FastAPI/Python.
- Cơ sở hạ tầng dữ liệu: Ràng buộc phải có PostgreSQL với pgvector extension cho việc tìm kiếm vector.

### Cross-Cutting Concerns Identified

- **Data Consistency & Conflict Resolution**: Quản lý rủi ro khi thay đổi offline trên IndexedDB cập nhật lên Postgres. 
- **Security & Authorization**: Row-level security phải ánh xạ đúng tới logic middleware API.
- **Latency & Streaming Handling**: Luồng gửi dữ liệu tokens (AI responses) cần trơn tru, độc lập với đồng bộ Zero-sync.

## Starter Template Evaluation

### Primary Technology Domain

Full-stack Web3/AI Application (Next.js + FastAPI) based on project requirements analysis.

### Starter Options Considered

Dựa trên yêu cầu của PRD và hệ sinh thái công nghệ, tôi đã khảo sát các giải pháp Boilerplate/Starter template chuẩn công nghiệp:

**1. Dành cho Next.js (Front-end Web Client):**
Công cụ chính chủ `create-next-app` vẫn là bộ khung đáng tin cậy nhất. Nó linh hoạt cấu hình App Router, TailwindCSS và TypeScript. Vì Nowing chạy mô hình Local-first đòi hỏi thiết lập bộ đệm Zero-sync (IndexedDB) cực kỳ đặc thù, việc dùng một boilerplate cồng kềnh chứa sẵn logic DB/Auth khác (như T3 Stack) sẽ dẫn tới rủi ro xung đột cao.

**2. Dành cho FastAPI (Backend API & Async Workers):**
- **Full Stack FastAPI Template (Official):** Chứa đủ SQLModel, Docker, rất tốt nhưng bị nhồi nhét sẵn React admin thừa kềnh càng.
- **Modern Standard Architecture (Custom):** Khuyến nghị tự thiết lập kiến trúc phân lớp chuẩn 2026 (`api`, `services`, `repositories`, `schemas`) sử dụng `uv` làm trình quản lý dependency và `Ruff` làm linter để tối ưu hiệu năng cho AI/Celery queue.

### Selected Starter: Official Next.js CLI & Custom Fast-Modern Async API

**Rationale for Selection:**
Hệ thống Agentic RAG và Zero-sync quá đặc thù, yêu cầu một khung xương sạch (clean foundation). Setup nguyên bản từ official tools giúp tránh "nợ kỹ thuật" (technical debt) khi scale, cho phép tích hợp trực tiếp Supabase RLS và Zero middle-tier dễ dàng.

**Initialization Command:**

```bash
# Frontend
npx create-next-app@latest nowing-web

# Backend (Khởi tạo bằng uv)
uv venv
uv pip install fastapi uvicorn celery pydantic-settings sqlmodel psycopg2-binary
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Frontend: TypeScript, Node.js. (App Router).
- Backend: Python 3.11+, hỗ trợ Native Async.

**Styling Solution:**
- Frontend: Tích hợp sẵn Tailwind CSS.

**Build Tooling:**
- Frontend: Next.js Turbopack.
- Backend: Trình quản lý package `uv` (Nhanh hơn từ 10-100 lần so với pip truyền thống).

**Testing Framework:**
- Frontend: Sẵn sàng cấu hình Vitest.
- Backend: `pytest` chuẩn công nghiệp.

**Code Organization:**
- Frontend: `app/` directory (Strictly App Router usage, Client Components chỉ dùng cho Zero-sync hooks).
- Backend: Strict layered architecture: `api/` (Thin routers), `services/` (Business/AI logic), `repositories/` (Database access), `schemas/`, `models/`.

**Development Experience:**
- Hot module reloading (HMR) mượt mà cho Next CLI và Uvicorn.
- Linting/Formatting hợp nhất và siêu nhanh qua `Ruff` cho Python, `ESLint/Prettier` cho TypeScript.

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data Sync & Caching Layer (Quyết định cách Zero-sync giao tiếp với FastAPI & Postgres).
- Authentication & JWT Rotation (Quyết định sinh token cho Zero-sync client).
- Asynchronous Processing (Cách quản lý luồng chunking và RAG pipeline bên ngoài luồng chính).

**Important Decisions (Shape Architecture):**
- Component State Management (Zustand kết hợp với cache cục bộ của IndexedDB).
- Vector Storage Engine (Sử dụng pgvector trong cùng database gốc hay tách rời).

**Deferred Decisions (Post-MVP):**
- Multi-tenancy Scaling (Sẽ ưu tiên RLS chạy trong 1 instance DB cho MVP, Scale out sẽ quyết định sau).

### Data Architecture

- **Database Choice:** PostgreSQL 16+.
- **Vector Storage:** Extension `pgvector` (Version đã verify: `0.8.2`) tích hợp trực tiếp vào DB chính nhằm tận dụng ưu thế JOIN data và RLS.
- **ORM / Query Builder:** `SQLModel` trên Backend và auto-generated Schema của Prisma cung cấp DDL cho Zero-sync.
- **Caching & Local-First Strategy:** Dùng `@rocicorp/zero` (Version đã verify: `1.1.1`) đổ dữ liệu xuống IndexedDB, Next.js sẽ subscribe trực tiếp qua Zero cache thay vì gọi FETCH thông thường.
- **Local File Synchronization (Desktop Only):** Tích hợp `chokidar` vào tiến trình nền của Electron để giám sát (monitor) các thư mục tài liệu cục bộ của người dùng. Mọi thay đổi sẽ được gửi qua Zero-sync mutators để cập nhật Metadata trong Knowledge Base ngay lập tức.

**Gift Subscription Tables (thêm vào migration 127+):**
(Đã cập nhật logic extension: Chỉ cộng dồn thời gian vào kỳ hiện tại; pro-rata logic cho việc đổi plan được đẩy sang v2).

**Crypto Data Cache & Security (Updated 2026-05-01):**
- **Workspace Isolation:** Bảng `crypto_data_snapshots` bắt buộc có cột `workspace_id` và áp dụng Postgres RLS để ngăn rò rỉ dữ liệu giữa các không gian tìm kiếm.
- **Cache Persistence:** Dữ liệu cuối cùng (Final Report) được lưu qua Zero-sync để local-first, nhưng trạng thái "đang chạy" (Orchestra Strip) chỉ truyền qua SSE để giảm tải cho hạ tầng đồng bộ.

- **Authentication Method:** JWT Token Auth do Backend FastAPI kiểm soát. Frontend nhận JWT và trao nó cho bộ khởi tạo `ZeroClient`.
- **Authorization Pattern:** Row-level Security (RLS) bắt buộc trên mọi tables Postgres. Logic từ FastAPI đến DB và luồng Zero repl-stream từ DB chọc xuống Next.js đều chịu chung bộ luật RLS này.
- **Security Middleware:** Áp dụng purge (làm sạch) lập tức IndexedDB & localStorage bằng hook `onLogout()`.
- **Desktop Native Security Bypass:** Tận dụng `ipcMain` và Node.js context trong Electron để thực hiện các cuộc gọi API tới Ollama Local, vượt qua các giới hạn về CORS/CSP của trình duyệt và cho phép ứng dụng tự động cấu hình hệ thống.

### API & Communication Patterns

- **API Design Patterns:** 
  - Standard RESTFul API cho các tác vụ CRUD thường và logic.
  - **Server-Sent Events (SSE) / WebSockets:** Quyết định dùng SSE cho luồng Streaming Response của Agentic RAG vì nó mượt hơn, một chiều từ Server gửi câu trả lời về UI.
  - Zero-sync protocol quản lý kết nối WebSocket cho dữ liệu đồng bộ tĩnh.
- **Job Orchestration:** Kết nối FastAPI và Celery Workers qua Redis Message Broker (`redis:7.4+`).
- **Hybrid LLM Routing Strategy:** 
  - **Cloud-first:** Mặc định sử dụng các API LLM (GPT-4, Claude) qua LiteLLM Router trên Server.
  - **Privacy-centric (Web SaaS):** Khi chọn model Local trên trình duyệt, Frontend sẽ gọi trực tiếp Ollama (`localhost:11434`).
  - **Embedded Backend (Desktop):** Electron sẽ quản lý vòng đời của một instance FastAPI Backend cục bộ (đóng gói qua `PyInstaller`), hỗ trợ tự động định tuyến (failover) giữa Cloud và Local.

**Gift Subscription Endpoints (thêm vào `nowing_backend/app/routes/gift_routes.py`):**

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| `POST` | `/api/v1/stripe/create-gift-checkout` | JWT | Tạo Stripe one-time payment checkout cho gift. Body: `{plan_id, duration_months, recipient_email?}`. Clone pattern từ `create_token_topup_checkout` với `mode="payment"` và `price_data` động. |
| `POST` | `/api/v1/stripe/redeem-gift` | JWT | Redeem gift code. Body: `{code}`. Verify code valid, extend subscription dùng extension formula, đánh dấu code `redeemed`. |
| `GET`  | `/api/v1/stripe/gift-codes` | JWT | Lấy danh sách gift codes đã mua bởi current user (lịch sử mua quà). |

**Gift Pricing Config (`nowing_backend/app/config/__init__.py`):**
```python
GIFT_PRICING = {
    # Aligned with Pro/Max subscription pricing (pricing-section.tsx):
    # Pro: $12/mo monthly, $96/yr annual (save $48)
    # Max: $100/mo monthly, $960/yr annual (save $240)
    "pro_monthly": {
        1:  1200,    # $12.00
        3:  3600,    # $36.00
        6:  7200,    # $72.00
        12: 9600,    # $96.00  (annual rate)
    },
    "max_monthly": {
        1:  10000,   # $100.00
        3:  30000,   # $300.00
        6:  60000,   # $600.00
        12: 96000,   # $960.00 (annual rate)
    },
}
```

**Webhook Extension (trong `stripe_webhook()` handler):**
```python
# Thêm branch mới trong checkout.session.completed handler
if session.metadata.get("purchase_type") == "gift":
    await _fulfill_gift_purchase(session)
# Existing branches: "subscription", "token_topup" vẫn giữ nguyên
```

**Admin-Approval Fallback:** Tương tự `SubscriptionRequest` — khi Stripe checkout thất bại, tạo `GiftRequest(status="pending")`, admin approve thủ công qua existing admin panel.

### Frontend Architecture

- **State Management:** Xử lý State toàn cục bằng `Zustand`. Data trả về từ backend đi thẳng vào UI (Offline-first approach), xử lý form với `react-hook-form`.
- **Component Architecture:** Next.js Server Components cho SEO và giao diện tĩnh; các tính năng tương tác với ZeroClient bắt buộc là Client Components (`"use client"`).
- **Styling:** Tailwind CSS + Radix UI / Shadcn (đảm bảo hỗ trợ Darkmode/Glassmorphism).

### Infrastructure & Deployment

- **Hosting Strategy:** Docker-Compose cho toàn bộ hệ thống (đáp ứng PRD local-first).
- **Environment Configuration:** Quản lý môi trường cứng qua `.env` kết nối bằng `pydantic-settings` (FastAPI). 
- **Message Broker:** Redis phiên bản containerized.
- **Desktop Packaging:** Sử dụng `electron-builder` kết hợp với `esbuild` để đóng gói ứng dụng. File thực thi bao gồm cả Web UI (Next.js export) và Backend binary (FastAPI) để đảm bảo khả năng chạy Offline hoàn toàn.

### Decision Impact Analysis

**Implementation Sequence:**
1. Cấu hình Data Models (SQLModel + pgvector).
2. Thiết lập RLS Policies tại DB.
3. Kích hoạt `@rocicorp/zero` Sync Server và kết nối với Frontend.
4. Xây dựng SSE Streaming cho luồng AI RAG.

**Cross-Component Dependencies:**
- API Gateway thay đổi token Auth -> Zero Sync phải lập tức reset websocket và xin lại credentials.
- Schema Postgres nếu thay đổi -> Zero SDK phải sync lại type-safety ở Next.js.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
Có 4 khu vực rủi ro cao nơi AI Agents dễ bị đụng độ:
1. Xung đột chữ hoa/thường giữa Python (thích snake_case) và TypeScript (thích camelCase).
2. Quy chuẩn cấu trúc JSON trả về từ FastAPI để Next.js (hoặc Zero-sync) dễ parse.
3. Cách gom nhóm files trên Next.js App Router.
4. Xử lý lỗi (Error handling) khi API throw 500 hay khi Zero offline.

### Naming Patterns

**Database Naming Conventions (Postgres/SQLModel):**
- **Tables:** Bắt buộc dùng `snake_case`, số nhiều (VD: `users`, `document_chunks`).
- **Columns:** Bắt buộc dùng `snake_case` (VD: `created_at`, `is_active`). KHÔNG DÙNG `camelCase` trong DB.
- **Foreign Keys:** Hậu tố `_id` (VD: `workspace_id`).

**API Naming Conventions:**
- **Endpoints:** Dùng `kebab-case` và danh từ số nhiều (VD: `/api/v1/knowledge-bases`).
- **Query Params:** Dùng `snake_case` ở phía raw URL (VD: `?sort_by=created_at&limit=10`).

**Code Naming Conventions:**
- **Python (Backend):** Variables & Functions dùng `snake_case` (`def get_user()`); Classes dùng `PascalCase` (`class DatabaseConfig`).
- **TypeScript (Frontend):** Variables & Hooks dùng `camelCase` (`useZeroSync()`); React Components dùng `PascalCase` (`DocumentUploader.tsx`).
- **File Names:** Component là `PascalCase.tsx`, các file helper/util là `kebab-case.ts`.

### Structure Patterns

**Project Organization:**
- Monorepo structure ảo: Tất cả code backend nằm trong thư mục gốc `backend/`, code frontend nằm trong thư mục gốc `web/`.
- Frontend Components: Chia theo feature-based (`web/src/components/features/auth/`), thay vì type-based.

### Format Patterns

**API Response Formats:**
- **Standard Wrapper:** Mọi FastAPI Response trả về REST đều phải được bọc trong cấu trúc chuẩn:
  ```json
  {
    "data": { ... },       // Payload chính (null nếu lỗi)
    "error": null,         // Object lỗi nếu có { "code": 400, "message": "..." }
    "meta": { "page": 1 }  // Dành cho pagination
  }
  ```
- Streaming API (SSE): Phải trả về chuẩn Server-Sent Event format `data: {"chunk": "..."}\n\n`.

**Data Exchange Formats:**
- FastAPI Pydantic Models **phải alias** các trường `snake_case` thành `camelCase` khi dump ra JSON để Client TypeScript sử dụng.

### Communication Patterns

**State Management Patterns:**
- **Zero-first approach:** Mọi Data state cho entity phải được lấy ra từ hook `useQuery(zero.query...)`. Hạn chế cache local dư thừa.
- **UI State:** Dùng `Zustand` cho các state giao diện.

### Process Patterns

**Error Handling Patterns:**
- **Backend:** Phải ném `HTTPException` và có Global Exception Handler túm lại trả về format lỗi chuẩn.
- **Frontend Error Boundary:** React Error Boundaries phải bọc quanh từng Feature Widget để tránh sập toàn trang.

### Enforcement Guidelines

**All AI Agents MUST:**
- LUÔN kiểm tra Schema Postgres (nếu là Dev Agent) trước khi viết Model Python.
- LUÔN validate Pydantic output dùng `by_alias=True` để convert sang camelCase.

### Pattern Examples

**Good Examples:**
`const { data: userData } = useQuery(zero.query.users.where('is_active', true));`

**Anti-Patterns:**
`def GetUserData(): pass` (Python hàm viết hoa là sai).
Dùng `Fetch()` gọi API ngoài luồng Zero-sync cho các đối tượng đã sync qua Zero.

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
nowing/
├── .github/                  # CI/CD workflows & PR templates
├── nowing_backend/        # FastAPI Backend (Python)
│   ├── pyproject.toml        
│   └── app/
│       ├── main.py           # Application entry point
│       ├── api/routes/       # API Routers
│       ├── db.py             # SQLAlchemy & PgVector definitions
│       ├── etl_pipeline/     # Text extraction (Docling/Unstructured/Llamacloud)
│       ├── indexing_pipeline/# Chunking, hashing & deduplication
│       ├── retriever/        # Hybrid Search (Full-text + PgVector RRF)
│       ├── schemas/          # Pydantic validation
│       └── tasks/            # Celery workers & beat (Redis)
├── nowing_web/            # Next.js Frontend (TypeScript)
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/                  # App Router
│   │   ├── dashboard/[search_space_id]/
│   │   │   └── gift/page.tsx          # [NEW] Gift purchase page (chọn plan, duration)
│   │   └── redeem/page.tsx            # [NEW] Public gift redemption page
│   ├── components/           # UI and Feature Components
│   │   └── gift/             # [NEW] Gift-specific components
│   │       ├── GiftPurchaseForm.tsx   # Plan/duration selector + Stripe checkout
│   │       └── GiftRedeemForm.tsx     # Code input + redeem action
│   ├── lib/                  # Generic utilities
│   ├── hooks/                # Custom hooks (Zero-sync wrappers)
│   └── store/                # UI State
├── nowing_browser_extension/  # Trình duyệt mở rộng
├── nowing_desktop/            # App Desktop (TBD)
├── docker/                       # Cấu hình Docker & Infrastructure
│   └── docker-compose.yml        # Orchestration (DB, Redis, Zero Cache, Backend, SearXNG)
├── docs/                         # Documentation files
└── README.md
```

**Backend Gift Files (mới):**
- `nowing_backend/app/routes/gift_routes.py` — 3 endpoints: create-gift-checkout, redeem-gift, gift-codes
- `nowing_backend/alembic/versions/128_add_gift_tables.py` — migration tạo `gift_codes` + `gift_requests`
- Webhook branch thêm vào `nowing_backend/app/routes/stripe_routes.py` (không tạo file mới)

### Architectural Boundaries

**API Boundaries:**
- **FastAPI Endpoint Boundaries:** Chỉ phục vụ các tác vụ backend, AI Streaming RAG (Server-Sent Events), ETL, và Celery queueing.
- **Next.js Route Handlers (`nowing_web/app/api/`):** Chỉ đóng vai trò Proxy an toàn hoặc xử lý Zero-Sync mutators (`/api/zero/mutate`) & query.

**Component Boundaries:**
- **UI vs Feature Components:** Component được định hình rõ ràng giữa các khối giao diện UI thông thường và smart components kết nối trực tiếp với Zero queries.

**Zero-Sync Boundaries (Data):**
- Mọi thao tác Read và Create/Update cho entity cơ bản (như hiển thị Documents list) đều thông qua Zero-Sync (`useQuery` / `zero.mutate`). Trạng thái Offline từ browser sẽ đẩy ngầm về DB Postgres (`zero-cache` process, port 4848).

### Requirements to Structure Mapping

**Epic/Feature Mapping (Agentic RAG & Streaming):**
- *Tính năng:* AI Search Streaming & Semantic Retreival
- **Backend Components:** `nowing_backend/app/retriever/chunks_hybrid_search.py` (chứa Postgres RRF queries kết hợp vector).
- **Frontend Components:** `nowing_web/app/...` và các hook chat streaming.

**Cross-Cutting Concerns (Local-First Experience):**
- *Tính năng:* Đồng bộ siêu trễ, UI luôn mượt dù mạng chậm.
- **Zero Configuration:** Quản lý trong `docker/docker-compose.yml` image `rocicorp/zero`.
- **Tương tác Interface:** Dùng hooks gọi Zero client để UI render tức thì.

### Integration Points

**Internal Communication:**
- Frontend giao tiếp với Backend qua 2 đường:
  1. Cổng SSE trực tiếp `[Web] ----(SSE)----> [FastAPI]` cho AI Streaming & RAG.
  2. Cổng Đồng bộ Dữ liệu Cục bộ: `[Web] <---(WebSockets)---> [Zero Cache] <---(Logical Replication)---> [Postgres]`.

**Data Flow:**
Luồng Upload tài liệu & RAG:
1. User upload file. API FastAPI nhận phản hồi lập tức nhờ `create_placeholder_documents()` (để trạng thái `pending` của tài liệu hiện ngay trên UI via Zero-Sync).
2. Tác vụ đẩy vào Pipeline `IndexingPipelineService` (Có thể process ở Background via Celery hoặc Parallel Batch).
3. `EtlPipelineService` trích xuất text (Plaintext/Docling/Vision_LLM). Chunks được hash và deduplicate.
4. Pgvector lưu Vectors thành công và đổi status => `ready`. Zero Server bắt được thay đổi qua Replication từ Postgres và push qua Web Socket về giao diện, UI tự động cập nhật mà không cần tải lại trang.

**Gift Subscription Data Flow:**

*Luồng Mua Gift (Purchaser):*
1. User vào `/dashboard/[id]/gift` → chọn plan + duration → click "Buy Gift".
2. Frontend gọi `POST /api/v1/stripe/create-gift-checkout` với `{plan_id, duration_months}`.
3. Backend tạo Stripe Checkout Session (`mode="payment"`, `price_data` động từ `GIFT_PRICING`), lưu `metadata.purchase_type="gift"`.
4. Redirect sang Stripe hosted checkout. User thanh toán.
5. Stripe gửi webhook `checkout.session.completed` → Backend handler phát hiện `purchase_type="gift"`.
6. `_fulfill_gift_purchase()`: generate `GIFT-XXXX-XXXX-XXXX` code, tạo `gift_codes` record (`status=active`), email code cho purchaser.
7. Purchaser chia sẻ code cho recipient qua bất kỳ kênh nào.

*Luồng Redeem Gift (Recipient):*
1. Recipient vào `/redeem` → nhập `GIFT-XXXX-XXXX-XXXX` → click "Redeem".
2. Frontend gọi `POST /api/v1/stripe/redeem-gift` với `{code}`.
3. Backend verify: code tồn tại, `status=active`, `expires_at` chưa qua.
4. Áp dụng extension formula: `new_expiry = max(current_period_end, now()) + duration`.
5. Update `users.subscription_current_period_end`, đổi `gift_codes.status=redeemed`, ghi `redeemed_at`.
6. Return success → Frontend hiển thị confirmation với ngày hết hạn mới.

## Deep Research — Chainlens Integration Architecture

### Bối cảnh & Động lực

Tính năng Deep Research hiện tại của Nowing chỉ là một `report_style="deep_research"` parameter trong tool `generate_report()` — chạy qua LLM nội bộ, dùng KB search hoặc conversation context. Không có web research chuyên sâu thực sự.

Giải pháp: Tích hợp **Chainlens Research** (`/api/v1/b2b/research`) làm engine research chuyên sâu bên ngoài, với cơ chế fallback tự động về Nowing khi Chainlens không khả dụng.

### Nguyên tắc thiết kế

1. **Zero-downtime cho user:** Nếu Chainlens API không live → fallback về Nowing ngay lập tức, user không chờ.
2. **Health check trước khi gọi:** Cached health check (TTL 30s) qua `GET /api/v1/b2b/health` (public, không cần auth) tránh gọi API chết gây delay.
3. **Sửa ít nhất có thể:** Tận dụng 100% kiến trúc hiện tại (tool system, SSE streaming, system prompt).
4. **Feature flag:** Bật/tắt qua env var `CHAINLENS_RESEARCH_ENABLED`.

### B2B Authentication (Đã có sẵn)

Chainlens Research B2B API **đã được bảo vệ** qua Next.js middleware (`src/middleware.ts`):

- **Bearer Token Auth:** Mọi request tới `/api/v1/b2b/*` (trừ `/health`) bắt buộc header `Authorization: Bearer <api_key>`.
- **API Key Storage:** SHA-256 hashed, lưu trong bảng `api_keys` (Drizzle ORM + Supabase Postgres).
- **Rate Limiting:** 120 requests/phút per API key (in-memory, auto-cleanup).
- **Daily Quota:** Configurable per key (`quotaLimit = -1` = unlimited), tự động reset hàng ngày.
- **Key Management:** Generate, revoke qua `src/lib/b2b/auth.ts`.

**Nowing backend cần:** Một API key hợp lệ trong env var `CHAINLENS_RESEARCH_API_KEY` để gọi B2B endpoints.

**Ngoại lệ:** `GET /api/v1/b2b/health` — public endpoint, middleware skip auth, dùng cho health check.

### Chainlens B2B API Contract

```
POST /api/v1/b2b/research
Content-Type: application/json

Request Body:
{
  "query": string,           // Required, min 1 char
  "sources": ["web", "discussions", "academic"],  // Optional, default ["web"]
  "stream": boolean           // Optional, default false
}

Response (non-stream, HTTP 200):
{
  "message": string,          // Full research result (markdown)
  "sources": [...]            // Array of source references
}

Response (stream, SSE):
  { "type": "init", "data": "Stream connected" }
  { "type": "response", "data": "<chunk>" }   // Repeated
  { "type": "sources", "data": [...] }
  { "type": "done" }

Timeout: 120 seconds (internal)
Error responses: 400 (validation), 500 (internal), 504 (timeout)
```

### Luồng Fallback (Flowchart)

```
User gửi query cần Deep Research
       │
       ▼
┌──────────────────────────┐
│ CHAINLENS_RESEARCH_      │
│ ENABLED == TRUE?         │
│                          │
│  NO ──────────────────────────────────────────┐
│  YES                     │                    │
│   │                      │                    │
│   ▼                      │                    │
│ Health Check             │                    │
│ GET /api/v1/b2b/health   │                    │
│ (cached 30s, timeout 3s) │                    │
│                          │                    │
│  NOT LIVE ────────────────────────────────────┤
│  LIVE ✅                  │                    │
│   │                      │                    │
│   ▼                      │                    │
│ POST /b2b/research       │                    │
│ (stream=false,           │                    │
│  timeout=120s)           │                    │
│                          │                    │
│  ERROR/TIMEOUT ──────────────────────────────┤
│  SUCCESS ✅               │                    │
│   │                      │                    │
│   ▼                      │                    ▼
│ Return Chainlens result  │    FALLBACK: generate_report()
│ {message, sources}       │    report_style="deep_research"
│                          │    source_strategy="kb_search"
└──────────────────────────┘    + web_search tool
```

### Configuration (Thêm vào `.env` + `Config` class)

```python
# .env — Thêm 4 biến mới
CHAINLENS_RESEARCH_API_URL=http://localhost:3001  # hoặc production URL
CHAINLENS_RESEARCH_API_KEY=                        # REQUIRED — B2B API key (Bearer token auth)
CHAINLENS_RESEARCH_ENABLED=TRUE                    # feature flag bật/tắt
CHAINLENS_HEALTH_CACHE_TTL=30                      # seconds, cache health check
```

```python
# config/__init__.py — Thêm vào class Config:
CHAINLENS_RESEARCH_API_URL = os.getenv("CHAINLENS_RESEARCH_API_URL", "")
CHAINLENS_RESEARCH_API_KEY = os.getenv("CHAINLENS_RESEARCH_API_KEY", "")
CHAINLENS_RESEARCH_ENABLED = os.getenv("CHAINLENS_RESEARCH_ENABLED", "FALSE").upper() == "TRUE"
CHAINLENS_HEALTH_CACHE_TTL = int(os.getenv("CHAINLENS_HEALTH_CACHE_TTL", "30"))
```

### Service Layer — `ChainlensResearchService`

File mới: `nowing_backend/app/services/chainlens_research_service.py` (~100 LOC)

```python
import time
import httpx
from app.config import Config

class ChainlensUnavailableError(Exception):
    """Raised when Chainlens API is unreachable or returns error."""
    pass

class ChainlensResearchService:
    """Proxy service gọi Chainlens Research B2B API với health check cached."""

    _health_cache: tuple[bool, float] = (False, 0.0)  # (is_live, timestamp)

    @classmethod
    async def is_available(cls) -> bool:
        """Health check với cache TTL. Dùng HEAD request nhẹ."""
        now = time.monotonic()
        is_live, cached_at = cls._health_cache
        if now - cached_at < Config.CHAINLENS_HEALTH_CACHE_TTL:
            return is_live

        if not Config.CHAINLENS_RESEARCH_ENABLED or not Config.CHAINLENS_RESEARCH_API_URL:
            cls._health_cache = (False, now)
            return False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{Config.CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/health")
                live = resp.status_code == 200
                cls._health_cache = (live, now)
                return live
        except Exception:
            cls._health_cache = (False, now)
            return False

    @classmethod
    async def research(cls, query: str, sources: list[str] | None = None) -> dict:
        """Gọi Chainlens B2B API (non-stream). Raise nếu fail."""
        if not await cls.is_available():
            raise ChainlensUnavailableError("Chainlens API not available")

        headers = {"Content-Type": "application/json"}
        if Config.CHAINLENS_RESEARCH_API_KEY:
            headers["Authorization"] = f"Bearer {Config.CHAINLENS_RESEARCH_API_KEY}"
        else:
            raise ChainlensUnavailableError("CHAINLENS_RESEARCH_API_KEY not configured")

        payload = {
            "query": query,
            "sources": sources or ["web"],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=125.0) as client:
                resp = await client.post(
                    f"{Config.CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/research",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    raise ChainlensUnavailableError(f"HTTP {resp.status_code}")
                return resp.json()
        except httpx.TimeoutException:
            # Invalidate health cache khi timeout
            cls._health_cache = (False, time.monotonic())
            raise ChainlensUnavailableError("Chainlens API timeout")
        except Exception as e:
            cls._health_cache = (False, time.monotonic())
            raise ChainlensUnavailableError(str(e))
```

### Tool Layer — `chainlens_deep_research`

File mới: `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` (~60 LOC)

```python
from langchain_core.tools import tool
from langchain_core.callbacks import dispatch_custom_event
from app.services.chainlens_research_service import (
    ChainlensResearchService,
    ChainlensUnavailableError,
)

def create_chainlens_research_tool():
    @tool
    async def chainlens_deep_research(
        query: str,
        sources: list[str] | None = None,
    ) -> dict:
        """Perform deep web research using Chainlens Research engine.

        Use this when the user asks for deep research, thorough investigation,
        or comprehensive web research on a topic. This tool provides
        significantly better research quality than built-in search.

        Falls back automatically to Nowing's built-in research if Chainlens
        is unavailable.

        Args:
            query: The research question or topic.
            sources: Research sources to use. Options: "web", "discussions",
                     "academic". Default: ["web"].
        """
        try:
            dispatch_custom_event(
                "research_status",
                {"phase": "chainlens", "message": "Starting deep research via Chainlens..."},
            )
            result = await ChainlensResearchService.research(query, sources)
            return {
                "status": "success",
                "provider": "chainlens",
                "message": result.get("message", ""),
                "sources": result.get("sources", []),
            }
        except ChainlensUnavailableError:
            dispatch_custom_event(
                "research_status",
                {"phase": "fallback", "message": "Chainlens unavailable, using Nowing research..."},
            )
            return {
                "status": "fallback",
                "provider": "nowing",
                "message": "Chainlens Research is currently unavailable. "
                           "Please use generate_report with report_style='deep_research' "
                           "and source_strategy='kb_search' to produce a research report "
                           "using Nowing's built-in capabilities.",
            }

    return chainlens_deep_research
```

### System Prompt Integration

Thêm vào `system_prompt.py` — `_TOOL_INSTRUCTIONS` và `_TOOL_EXAMPLES`:

```python
_TOOL_INSTRUCTIONS["chainlens_deep_research"] = """
- chainlens_deep_research: Perform deep web research using Chainlens Research engine.
  - Use this when the user explicitly asks for "deep research", "thorough research",
    "comprehensive investigation", or needs high-quality web research results.
  - This tool provides significantly better research than web_search — it synthesizes
    multiple sources into a structured research report.
  - Falls back automatically to Nowing's built-in research if Chainlens is unavailable.
  - Args:
    - query: The research question or topic
    - sources: ["web", "discussions", "academic"] — types of sources to search
  - Returns: { status, provider, message, sources }
  - FALLBACK HANDLING: If status is "fallback", use generate_report with
    report_style="deep_research" and source_strategy="kb_search" instead.
  - Do NOT use this for simple factual questions — use web_search for those.
"""

_TOOL_EXAMPLES["chainlens_deep_research"] = """
- User: "Do a deep research on AI agents in 2026"
  - Call: `chainlens_deep_research(query="AI agents landscape and trends in 2026", sources=["web", "academic"])`
- User: "Thoroughly investigate the impact of DeFi on traditional banking"
  - Call: `chainlens_deep_research(query="Impact of DeFi on traditional banking industry", sources=["web", "discussions"])`
- If result has status="fallback":
  - Call: `generate_report(topic="DeFi Impact on Banking", source_strategy="kb_search", search_queries=["DeFi banking impact", "decentralized finance disruption"], report_style="deep_research")`
"""

# Thêm vào _ALL_TOOL_NAMES_ORDERED:
_ALL_TOOL_NAMES_ORDERED = [
    "search_nowing_docs",
    "web_search",
    "chainlens_deep_research",   # ← NEW
    "generate_podcast",
    "generate_video_presentation",
    "generate_report",
    "generate_image",
    "scrape_webpage",
    "update_memory",
]
```

### Tool Binding Integration

Đăng ký trong `tools/registry.py` — thêm vào `BUILTIN_TOOLS` list (đúng pattern hiện tại):

```python
# Trong BUILTIN_TOOLS list (tools/registry.py):
from app.agents.new_chat.tools.chainlens_research import create_chainlens_research_tool

ToolDefinition(
    name="chainlens_deep_research",
    description="Perform deep web research using Chainlens Research engine with auto-fallback",
    factory=create_chainlens_research_tool,
    requires=[],  # No DB/connector dependencies — uses external API
    enabled_by_default=True,  # Controlled by CHAINLENS_RESEARCH_ENABLED env var inside tool
),
```

**Lưu ý:** Feature flag `CHAINLENS_RESEARCH_ENABLED` được kiểm tra **bên trong tool** (qua `ChainlensResearchService.is_available()`), không phải ở registry level. Tool luôn được register nhưng sẽ fallback ngay nếu flag tắt.

### Project Structure (Files thay đổi)

```text
nowing_backend/
├── app/
│   ├── config/__init__.py                          # [EDIT] +4 env vars
│   ├── services/
│   │   └── chainlens_research_service.py           # [NEW] ~100 LOC
│   ├── agents/new_chat/
│   │   ├── system_prompt.py                        # [EDIT] +30 dòng tool instructions
│   │   └── tools/
│   │       ├── registry.py                         # [EDIT] +1 ToolDefinition entry
│   │       └── chainlens_research.py               # [NEW] ~60 LOC
├── .env                                            # [EDIT] +4 biến
```

**Tổng impact: 2 file mới, 4 file sửa nhỏ (dưới 40 dòng mỗi file). Frontend: 0 thay đổi.**

### Data Flow — Deep Research Integration

*Luồng thành công (Chainlens live):*
1. User gửi "deep research about X" trong chat.
2. Nowing Agent detect intent → gọi tool `chainlens_deep_research(query="X")`.
3. Tool gọi `ChainlensResearchService.is_available()` → check cached health → LIVE ✅.
4. Tool gọi `ChainlensResearchService.research(query, sources)` → POST tới Chainlens B2B API.
5. Chainlens trả về `{message, sources}` trong ≤120s.
6. Tool return `{status: "success", provider: "chainlens", message, sources}`.
7. Agent trình bày kết quả research cho user trên chat (SSE streaming).

*Luồng fallback (Chainlens down):*
1. User gửi "deep research about X" trong chat.
2. Nowing Agent detect intent → gọi tool `chainlens_deep_research(query="X")`.
3. Tool gọi `ChainlensResearchService.is_available()` → NOT LIVE ❌ (hoặc timeout).
4. Tool return `{status: "fallback", provider: "nowing", message: "use generate_report..."}`.
5. Agent tự động gọi `generate_report(report_style="deep_research", source_strategy="kb_search")`.
6. Nowing's built-in research chạy, kết quả trả về user qua report card.
7. User không bị gián đoạn, chỉ nhận thông báo nhẹ "Using Nowing's built-in research".

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- Tuyệt đối tương thích: Việc chia tách trách nhiệm rõ ràng (Web Client quản lý state bằng Zero Sync; FastAPI chỉ xử lý các tác vụ nặng & Streaming RAG) giúp tránh conflict về source of truth. Zero-Sync tương thích hoàn hảo với Postgres Logical Replication.
- Celery + Redis là combo battle-tested cho Async task, không có rủi ro về stack.
- **Gift Subscription:** Dùng Stripe `mode="payment"` (không phải `mode="subscription"`) tránh hoàn toàn proration edge cases. Gift codes được lưu trong separate tables (`gift_codes`, `gift_requests`) — không ảnh hưởng existing `SubscriptionRequest` model.

**Pattern Consistency:**
- Quy ước Naming Conventions (TypeScript: `camelCase`, DB & Python: `snake_case`) cùng nguyên tắc tự chuyển đổi (Alias `by_alias=True` trong Pydantic) giải quyết triệt để rủi ro lệch chuẩn dữ liệu khi các AI Agents Gen code tự động.
- Gift endpoints follow cùng pattern với `create_token_topup_checkout` (dynamic `price_data`, no pre-created Stripe Price IDs).

**Structure Alignment:**
- Cấu trúc "Monorepo ảo tĩnh" chia đôi `web/` và `backend/` tách biệt hoàn toàn Development Environment (uv cho Python, pnpm cho Node) nên không lấn cấn cấu hình.

### Requirements Coverage Validation ✅

**Epic/Feature Coverage:**
- **Local-first (FR9):** Covered 100% nhờ `@rocicorp/zero` và cấu hình IndexedDB cached.
- **DeepRAG & Streaming (FR4):** Covered 100% nhờ sự kết hợp giữa FastAPI Server-Sent Events (SSE) và Postgres `pgvector`.
- **Gift Subscription (FR18–FR23):**
  - FR18 (Gift purchase flow): `POST /create-gift-checkout` → Stripe → webhook → `gift_codes` record.
  - FR19 (Gift code generation): `secrets.choice()` 12-char, format `GIFT-XXXX-XXXX-XXXX`.
  - FR20 (Gift code redemption): `POST /redeem-gift` với extension formula.
  - FR21 (Subscription extension): `max(current_period_end, now()) + duration`.
  - FR22 (Admin fallback): `GiftRequest(status=pending)` → admin approves → generate code.
  - FR23 (Gift history): `GET /gift-codes` trả về danh sách codes của purchaser.

**Non-Functional Requirements Coverage:**
- **Latency (TTFT < 1.5s):** Fast API async router và Streaming trực tiếp nén TTFT cực tốt.
- **Scalability:** Scale Backend độc lập với Frontend. Khâu process văn bản được tách riêng ra worker nodes qua Celery tránh sập web server.

### Implementation Readiness Validation ✅

**Decision Completeness:**
- Stack rõ ràng, version cụ thể (`Next.js 14+`, `FastAPI 0.100+`, `pgvector 0.8+, Postgres 16`, `@rocicorp/zero 1.1.1`).
- Đã quy định rõ AI Error Boundaries.
- **Gift Subscription:** 6 architectural decisions đã chốt. Migration số, file paths, pricing config đều rõ ràng.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Đã phân tích toàn diện 14 FRs và 7 NFRs.
- [x] Đã xác định được "Local-first" và "Fast AI Streaming" là yêu cầu cốt lõi.
- [x] Đã phân tích 6 FRs bổ sung (FR18–FR23) cho Gift Subscription.

**✅ Architectural Decisions**
- [x] Quyết định 4 trụ cột công nghệ (Next.js, FastAPI, Postgres+Zero, Redis+Celery).
- [x] Các Quyết định bảo mật RLS và JWT tích hợp Zero.
- [x] Gift Subscription: Stripe `mode=payment`, separate tables, extension formula, admin fallback.

**✅ Implementation Patterns**
- [x] Thiết lập Rule đặt tên rõ ràng chéo ngôn ngữ (TS & Python).
- [x] Chốt cấu trúc Request/Response bọc Standard Error Handler.

**✅ Project Structure**
- [x] Lên cây thư mục (Directory Tree) độc lập Backend - Web - Zero Config.
- [x] Gift files: `gift_routes.py`, migration 128, `app/dashboard/[id]/gift/`, `app/redeem/`, `components/gift/`.

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH (Cao)
- Kiến trúc giải quyết được bài toán khó nhất là: "Làm sao vừa chạy Local-first nhanh chóng lại vừa chạy Tác vụ AI siêu nặng".
- Gift Subscription được thiết kế isolate hoàn toàn: không ảnh hưởng existing billing code, dùng separate tables, clone proven patterns.

**Implementation Handoff**
- **First Implementation Priority:** Dùng hệ thống sẵn có (đã khởi tạo Next.js `nowing_web` và FastAPI `nowing_backend`). Môi trường local chạy qua `docker compose -f docker/docker-compose.dev.yml up -d` với đầy đủ Postgres (pgvector), Redis, Zero-Cache và SearXNG.

## Crypto Orchestra Architecture

### Bối cảnh & Phạm vi

**Mục tiêu**: Hỗ trợ Journey #8 (Crypto Power User "Khoa") — query "phân tích toàn diện $UNI" → main agent spawn 4-11 sub-agents song song → trả về aggregated insights trong P95 < 90s với graceful degradation > 98%.

**Scope mới (delta so với Epic 1-7 baseline):**
- **Epic 0** (foundation): 6 stories (0.1–0.6) — tool infrastructure, sub-agents, orchestration prompt, parallel telemetry, circuit breaker.
- **Epic 9** (advanced): 6 sub-agents bổ sung (tokenomics, whale tracker, token unlock, yield optimizer, governance, technical analysis).
- **UX layer**: 7 frontend components mới + 8 telemetry events (chi tiết ở `ux-crypto-orchestra-handoff.md`).

**Baseline KHÔNG đổi**: SSE pipe `/api/v1/chat` (Epic 7), LangGraph DeepAgent framework, system prompt structure, Zero-sync layer.

---

### Architecture Overview (C4-Inspired Component Diagram)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Next.js Web Client)                   │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  ChatBubble                                                      │  │
│  │  ├─ <OrchestraStrip />          ◀──── SSE: orchestra.* events    │  │
│  │  │   ├─ <AgentRow /> × N        ◀──── orchestra.update           │  │
│  │  │   └─ <DegradationNotice />   ◀──── orchestra.fail             │  │
│  │  ├─ <MessageContent />          ◀──── existing SSE: chunk        │  │
│  │  │   └─ <MultiCitationBadge />                                   │  │
│  │  └─ <SourceTabsPanel />                                          │  │
│  │                                                                   │  │
│  │  useOrchestraStore (Zustand) ── PGLite snapshot via Zero mutator │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ SSE  /api/v1/chat
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (nowing_backend)                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  ChatRouter (api/routes/chat.py)                                  │ │
│  │      └─ stream_event_publisher (SSE wrapper)                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  chat_deepagent.create_deepagent()                                 │ │
│  │  ├── Middleware Stack (gp_middleware):                            │ │
│  │  │   ├─ TodoListMiddleware                                         │ │
│  │  │   ├─ MemoryMiddleware                                           │ │
│  │  │   ├─ NowingFilesystemMiddleware                                │ │
│  │  │   ├─ SummarizationMiddleware                                    │ │
│  │  │   ├─ PatchToolCalls                                             │ │
│  │  │   ├─ AnthropicPromptCaching                                     │ │
│  │  │   ├─ ParallelismTelemetryMiddleware  ★ Story 0.5                │ │
│  │  │   └─ CircuitBreakerMiddleware        ★ Story 0.6                │ │
│  │  │                                                                  │ │
│  │  ├── SubAgentMiddleware (registry of 11 specialists):              │ │
│  │  │   ├─ general_purpose                                            │ │
│  │  │   ├─ defillama_analyst       ─┐                                 │ │
│  │  │   ├─ sentiment_analyst        │                                 │ │
│  │  │   ├─ news_analyst             ├─ Epic 0 base (4 agents)         │ │
│  │  │   ├─ smart_contract_analyst  ─┘                                 │ │
│  │  │   ├─ tokenomics_analyst      ─┐                                 │ │
│  │  │   ├─ whale_tracker            │                                 │ │
│  │  │   ├─ token_unlock_scheduler   ├─ Epic 9 advanced (6 agents)     │ │
│  │  │   ├─ yield_optimizer          │                                 │ │
│  │  │   ├─ governance_analyst       │                                 │ │
│  │  │   └─ technical_analyst       ─┘                                 │ │
│  │  │                                                                  │ │
│  │  └── ToolNode (LangGraph) — parallel batch executor                 │ │
│  │      └─ task() tool — spawns sub-agent in same graph step           │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Tool Registry (BUILTIN_TOOLS, requires=[])                       │ │
│  │   • defillama.py          (5 tools)                                │ │
│  │   • crypto_sentiment.py   (2 tools: F&G, Reddit)                   │ │
│  │   • crypto_news.py        (2 tools: CryptoPanic, CoinGecko)        │ │
│  │   • contract_analysis.py  (2 tools: Etherscan, GoPlus)             │ │
│  │   • chainlens_research.py (1 tool — fallback engine)               │ │
│  │   • crypto_realtime.py    (DexScreener live price)                 │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  ObservabilityClient (app/observability/metrics.py)                │ │
│  │   • crypto_orchestra_parallelism_ratio (histogram)                 │ │
│  │   • crypto_orchestra_full_suite_duration_seconds (histogram)       │ │
│  │   • crypto_orchestra_agent_errors_total (counter)                  │ │
│  │   • crypto_orchestra_graceful_degradation_total (counter)          │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│   External APIs (stateless, requires=[])                                │
│   DeFiLlama │ CoinGecko │ GoPlus │ CryptoPanic │ Etherscan │ Reddit    │
│   alternative.me F&G │ Chainlens B2B (fallback)                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 1. Per-Agent SSE Event Contract

**Decision**: Mở rộng existing SSE pipe `/api/v1/chat` với 6 event types mới namespaced `orchestra.*`. KHÔNG tạo channel WebSocket mới — reuse pipeline đã production-grade từ Epic 7.

**Schema (Pydantic models trong `app/schemas/sse_events.py`):**

```python
# app/schemas/sse_events.py — NEW FILE

from typing import Literal
from pydantic import BaseModel, Field

# ─── Shared types ─────────────────────────────────────────────────────
class AgentManifest(BaseModel):
    name: str                              # snake_case e.g. "defillama_analyst"
    display_name: str                      # human label e.g. "DeFi"
    estimated_p50_ms: int                  # ETA heuristic from telemetry P50
    tools_count: int                       # for UI density hint

class AgentSummary(BaseModel):
    fact_count: int
    sources: list[str]                     # canonical names: "DeFiLlama", "Reddit", ...

FailReason = Literal[
    "rate_limit", "timeout", "unavailable",
    "cancelled_by_user", "circuit_open"
]

# ─── 6 Orchestra Events ───────────────────────────────────────────────
class OrchestraSpawnEvent(BaseModel):
    event: Literal["orchestra.spawn"] = "orchestra.spawn"
    query_hash: str                        # sha256(query + user_id)[:16]
    agents: list[AgentManifest]
    spawn_count: int

class OrchestraUpdateEvent(BaseModel):
    event: Literal["orchestra.update"] = "orchestra.update"
    agent_name: str
    status: Literal["running"]
    elapsed_ms: int
    # Backpressure: server-side throttle to 1 update / agent / 500ms

class OrchestraDoneEvent(BaseModel):
    event: Literal["orchestra.done"] = "orchestra.done"
    agent_name: str
    duration_ms: int
    summary: AgentSummary

class OrchestraFailEvent(BaseModel):
    event: Literal["orchestra.fail"] = "orchestra.fail"
    agent_name: str
    reason: FailReason
    fallback_used: bool = False           # True if agent fell back to chainlens/web_search

class OrchestraCancelEvent(BaseModel):
    event: Literal["orchestra.cancel"] = "orchestra.cancel"
    at_ms: int
    partial_results: bool

class OrchestraCompleteEvent(BaseModel):
    event: Literal["orchestra.complete"] = "orchestra.complete"
    total_ms: int
    success: int
    failed: int
    p95_bucket: Literal["fast", "normal", "slow"]  # < 30s | 30-60s | > 60s
```

**SSE wire format** (consistent với Epic 7 pattern):
```
event: orchestra.spawn
data: {"query_hash":"a3f9...","agents":[{...}],"spawn_count":4}

event: orchestra.update
data: {"agent_name":"defillama_analyst","status":"running","elapsed_ms":1240}
```

#### Resolution — 4 Open Questions từ UX Handoff §3

| # | Question | Decision |
|---|----------|----------|
| 1 | Event naming convention consistent với Epic 7? | ✅ **Namespace `orchestra.*`** — phân biệt với existing `chunk`, `tool_call`, `done`. Reuse SSE wire format `event: <name>\ndata: <json>\n\n`. |
| 2 | Backpressure: rate-limit `orchestra.update` server-side hay client-side? | ✅ **Server-side throttle**: `ParallelismTelemetryMiddleware` debounce update events đến **1 update / agent / 500ms** (configurable via `ORCHESTRA_UPDATE_THROTTLE_MS`). Client KHÔNG cần debounce — tránh complexity. |
| 3 | Multi-session shared hay duplicated? | ✅ **MVP: duplicated per session** (mỗi tab = 1 SSE stream, 1 agent run). v2 sẽ implement shared via Redis pub/sub keyed `(query_hash, user_id)` — hiện tại không justify complexity. |
| 4 | Conflict detection: backend emit `orchestra.conflict` event hay FE tự detect? | ✅ **FE tự detect từ citation metadata** (numeric delta > 5% → render `[2≠4]`). Backend KHÔNG emit conflict event — agent independence + LLM judgment handle disagreements. Conflict UI là pure rendering layer. |

---

### 2. ParallelismTelemetryMiddleware Design (Story 0.5)

**File**: `nowing_backend/app/agents/new_chat/middleware/parallelism_telemetry.py` (NEW)

**Mục tiêu**:
1. Capture per-agent timing (start, end, duration) qua LangGraph callbacks.
2. Compute `parallelism_ratio = step_duration / max(agent_duration)` real-time per request.
3. Emit metrics `parallelism_ratio` + `full_suite_duration` ra Prometheus/Datadog.
4. Throttle `orchestra.update` SSE events (xem §1, decision #2).
5. Detect sequential anti-pattern (2+ `task()` calls trong khác step) → log warning.

**Skeleton**:

```python
# app/agents/new_chat/middleware/parallelism_telemetry.py

from collections import defaultdict
from typing import Any
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from app.observability.metrics import (
    parallelism_ratio_histogram,
    full_suite_duration_histogram,
    sequential_antipattern_counter,
)
import time

class ParallelismTelemetryMiddleware(BaseCallbackHandler):
    """Track parallel sub-agent execution metrics + emit SSE update events."""

    def __init__(self, sse_publisher, throttle_ms: int = 500):
        self.sse = sse_publisher
        self.throttle_ms = throttle_ms
        self._step_starts: dict[str, float] = {}            # step_id -> start_time
        self._agent_starts: dict[str, dict] = {}            # call_id -> {agent_name, step_id, start}
        self._last_update_emit: dict[str, float] = {}       # agent_name -> last_emit_ms
        self._task_calls_per_step: dict[str, list] = defaultdict(list)

    async def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id, tags=None, metadata=None, **kwargs):
        if serialized.get("name") != "task":
            return
        agent_name = self._parse_agent_name(input_str)
        step_id = (metadata or {}).get("langgraph_step", "unknown")
        now = time.perf_counter()

        self._agent_starts[str(run_id)] = {
            "agent_name": agent_name, "step_id": step_id, "start": now,
        }
        self._task_calls_per_step[step_id].append(agent_name)
        self._step_starts.setdefault(step_id, now)

    async def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        ctx = self._agent_starts.pop(str(run_id), None)
        if not ctx:
            return
        duration = time.perf_counter() - ctx["start"]
        await self.sse.emit("orchestra.done", {
            "agent_name": ctx["agent_name"],
            "duration_ms": int(duration * 1000),
            "summary": self._extract_summary(output),
        })

    async def on_chain_end(self, outputs, **kwargs):
        """When LangGraph step ends — compute parallelism_ratio if multi-spawn."""
        for step_id, agents in self._task_calls_per_step.items():
            if len(agents) < 2:
                continue
            step_duration = time.perf_counter() - self._step_starts[step_id]
            # Find max individual agent duration in this step
            max_individual = max(
                (time.perf_counter() - ctx["start"])
                for ctx in self._agent_starts.values()
                if ctx["step_id"] == step_id
            ) or step_duration
            ratio = step_duration / max_individual
            parallelism_ratio_histogram.observe(ratio, labels={"agents_count": len(agents)})

            # Sequential anti-pattern detection: if same query has 2+ steps with task() calls
            if self._has_sequential_pattern():
                sequential_antipattern_counter.inc()

    async def heartbeat_update(self, agent_name: str, elapsed_ms: int):
        """Throttled emit of orchestra.update — call from agent ainvoke loop."""
        last = self._last_update_emit.get(agent_name, 0)
        now_ms = time.monotonic() * 1000
        if now_ms - last < self.throttle_ms:
            return
        self._last_update_emit[agent_name] = now_ms
        await self.sse.emit("orchestra.update", {
            "agent_name": agent_name,
            "status": "running",
            "elapsed_ms": elapsed_ms,
        })
```

**Wiring vào `chat_deepagent.py`**:
```python
# Add to gp_middleware stack (cần inject sse_publisher từ chat route)
gp_middleware = [
    TodoListMiddleware(),
    MemoryMiddleware(),
    # ... existing
    ParallelismTelemetryMiddleware(sse_publisher=sse_pub),  # NEW
    CircuitBreakerMiddleware(),                              # NEW (§3)
]
```

**Feature flag**: `PARALLELISM_TELEMETRY_ENABLED=true` (default true). Disable nếu phát hiện perf regression.

---

### 3. Circuit Breaker + Graceful Degradation Pattern (Story 0.6)

**Mục tiêu**: Đáp ứng NFR-Q3 (≥ 98% requests có ≥1 agent error vẫn trả response đúng cấu trúc) qua 3 lớp bảo vệ:

#### Layer 1 — Tool-level Error Contract

**Convention bắt buộc**: Mọi tool **return `{"error": "<msg>"}` dict**, KHÔNG raise exception.

```python
# Pattern chuẩn cho tools (tools/defillama.py, crypto_news.py, ...)
@tool
async def get_defillama_protocol(protocol_slug: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"https://api.llama.fi/protocol/{protocol_slug}")
            if resp.status_code == 429:
                return {"error": "DeFiLlama rate limit reached, try again in 1 minute"}
            if resp.status_code >= 500:
                return {"error": f"DeFiLlama API unavailable (HTTP {resp.status_code})"}
            return resp.json()
    except httpx.TimeoutException:
        return {"error": "DeFiLlama timeout"}
    except Exception as exc:
        logger.warning("get_defillama_protocol failed", exc_info=True)
        return {"error": f"Unexpected: {type(exc).__name__}"}
```

#### Layer 2 — CircuitBreakerMiddleware (per-API circuit)

**File**: `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py` (NEW)

**Algorithm** (simplified Hystrix pattern):

```python
class CircuitBreaker:
    """Per-source circuit breaker: open after 5 consecutive failures, half-open after 30s."""

    STATE_CLOSED = "closed"      # normal operation
    STATE_OPEN = "open"          # blocking — fail-fast
    STATE_HALF_OPEN = "half_open"  # probe with 1 request

    def __init__(self, source: str, failure_threshold: int = 5, reset_timeout_s: int = 30):
        self.source = source
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.failure_count = 0
        self.state = self.STATE_CLOSED
        self.opened_at: float | None = None

    def record_success(self):
        self.failure_count = 0
        self.state = self.STATE_CLOSED
        self.opened_at = None

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN
            self.opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self.state == self.STATE_CLOSED:
            return False
        if self.state == self.STATE_OPEN:
            if time.monotonic() - self.opened_at > self.reset_timeout_s:
                self.state = self.STATE_HALF_OPEN
                return False  # allow 1 probe
            return True
        return False  # half_open allows 1 request

# Registry (singleton per source)
_BREAKERS: dict[str, CircuitBreaker] = {
    src: CircuitBreaker(src) for src in
    ["defillama", "coingecko", "goplus", "cryptopanic", "etherscan", "reddit"]
}
```

**Integration**: Tools call `_BREAKERS[source].is_open()` trước khi gọi HTTP — nếu open thì trả về `{"error": "circuit_open", "fallback_hint": "use chainlens_deep_research"}` ngay (fail-fast, không waste time).

#### Layer 3 — Agent-level Fallback (sub-agent system prompts)

Mỗi sub-agent có system prompt instruct: "If primary tool returns `{error: ...}`, fall back to (1) alternative tool listed below, OR (2) `chainlens_deep_research`, OR (3) honest 'data unavailable' note. NEVER hallucinate."

**Fallback matrix:**

| Sub-agent | Primary tool | Fallback chain |
|-----------|-------------|----------------|
| `defillama_analyst` | `get_defillama_*` | → `chainlens_deep_research` → "limited DeFi data" note |
| `sentiment_analyst` | `get_cmc_sentiment` | → `get_reddit_crypto_sentiment` → `web_search` → note |
| `news_analyst` | `get_crypto_news` (CryptoPanic) | → `chainlens_deep_research` → `web_search` → note |
| `smart_contract_analyst` | `check_token_security` (GoPlus) | → `get_contract_info` (Etherscan only) → note "security score unavailable" |

#### Layer 4 — Orchestration-level Synthesis (main agent prompt)

Main agent system prompt instruct (xem §5 Rule C):
- Nếu 1-2 sub-agents fail → synthesize từ remaining agents, **explicitly mention** unavailable source.
- Nếu 4/4 fail → trả "service issues, please retry in a few minutes" — **KHÔNG hallucinate**.

#### Telemetry — Degradation Outcome Classification

Per request, `ParallelismTelemetryMiddleware` (extended trong Story 0.6) classifies outcome:

| Outcome | Definition | Counter label |
|---------|-----------|---------------|
| `success` | All spawned agents return non-error result | `outcome="success"` |
| `partial` | 1+ agent error nhưng response > 100 chars | `outcome="partial"` |
| `failed` | All agents error AND response < 100 chars | `outcome="failed"` |

**Quality Gate NFR-Q3**: `(success + partial) / total >= 0.98` over 1h rolling window.

---

### 4. Tool Registry Pattern cho 11 Crypto Tools (Story 0.1)

**File**: `nowing_backend/app/agents/new_chat/tools/registry.py` (EDIT — append entries)

**Constraint chuẩn**:
- ✅ Mọi crypto tool có `requires=[]` (NFR-CS4 — stateless, no DB).
- ✅ Factory pattern `factory=lambda deps: create_<name>_tool()` — instance per spawn.
- ✅ Tool function async (httpx.AsyncClient — non-blocking).
- ✅ Error contract Layer 1 (xem §3).

**11 ToolDefinition entries**:

```python
# tools/registry.py — extension

from app.agents.new_chat.tools.defillama import (
    create_defillama_protocol_tool,
    create_defillama_tvl_overview_tool,
    create_defillama_yields_tool,
    create_defillama_stablecoins_tool,
    create_defillama_bridges_tool,
)
from app.agents.new_chat.tools.crypto_sentiment import (
    create_cmc_sentiment_tool,
    create_reddit_sentiment_tool,
)
from app.agents.new_chat.tools.crypto_news import (
    create_crypto_news_tool,
    create_coingecko_token_info_tool,
)
from app.agents.new_chat.tools.contract_analysis import (
    create_contract_info_tool,
    create_check_token_security_tool,
)

CRYPTO_TOOLS = [
    ToolDefinition(name="get_defillama_protocol",       factory=lambda d: create_defillama_protocol_tool(),       requires=[]),
    ToolDefinition(name="get_defillama_tvl_overview",   factory=lambda d: create_defillama_tvl_overview_tool(),   requires=[]),
    ToolDefinition(name="get_defillama_yields",         factory=lambda d: create_defillama_yields_tool(),         requires=[]),
    ToolDefinition(name="get_defillama_stablecoins",    factory=lambda d: create_defillama_stablecoins_tool(),    requires=[]),
    ToolDefinition(name="get_defillama_bridges",        factory=lambda d: create_defillama_bridges_tool(),        requires=[]),
    ToolDefinition(name="get_cmc_sentiment",            factory=lambda d: create_cmc_sentiment_tool(),            requires=[]),
    ToolDefinition(name="get_reddit_crypto_sentiment",  factory=lambda d: create_reddit_sentiment_tool(),         requires=[]),
    ToolDefinition(name="get_crypto_news",              factory=lambda d: create_crypto_news_tool(),              requires=[]),
    ToolDefinition(name="get_coingecko_token_info",     factory=lambda d: create_coingecko_token_info_tool(),     requires=[]),
    ToolDefinition(name="get_contract_info",            factory=lambda d: create_contract_info_tool(),            requires=[]),
    ToolDefinition(name="check_token_security",         factory=lambda d: create_check_token_security_tool(),     requires=[]),
]
BUILTIN_TOOLS.extend(CRYPTO_TOOLS)
```

**Sub-agent scoped tool list** (NFR-CS1 — avoid context confusion): SubAgentMiddleware passes scoped subset, KHÔNG full registry. Mapping:

| Sub-agent | Scoped tools |
|-----------|-------------|
| `defillama_analyst` | `get_defillama_*` (5) + `get_live_token_data` + `web_search` |
| `sentiment_analyst` | `get_cmc_sentiment`, `get_reddit_crypto_sentiment`, `web_search`, `scrape_webpage` |
| `news_analyst` | `get_crypto_news`, `get_coingecko_token_info`, `web_search`, `scrape_webpage`, `chainlens_deep_research` |
| `smart_contract_analyst` | `get_contract_info`, `check_token_security`, `web_search`, `scrape_webpage` |
| `tokenomics_analyst` (Epic 9) | `get_coingecko_token_info`, `web_search`, `scrape_webpage`, `chainlens_deep_research` |
| `whale_tracker` (Epic 9) | `web_search`, `scrape_webpage`, `chainlens_deep_research` |
| `token_unlock_scheduler` (Epic 9) | `web_search`, `scrape_webpage` |
| `yield_optimizer` (Epic 9) | `get_defillama_yields`, `get_defillama_protocol`, `check_token_security` |
| `governance_analyst` (Epic 9) | `web_search`, `scrape_webpage`, `chainlens_deep_research` |
| `technical_analyst` (Epic 9) | `get_live_token_data`, `web_search`, `scrape_webpage` |

---

### 5. Multi-Agent Orchestration Prompt Architecture (Story 0.3)

**File**: `nowing_backend/app/agents/new_chat/system_prompt.py` (EDIT — add section)

**Architecture intent**: Convert "smart agent selection" (FR-34) thành deterministic LLM behavior qua structured prompt với 4-rule decision tree.

**Decision Tree**:

```text
                    ┌──────────────────────┐
                    │  User query received │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Intent classification │
                    │  (LLM judgment)       │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┬─────────────────────┐
        ▼                      ▼                      ▼                     ▼
  Rule A: Direct tool   Rule B: Single        Rule C: Parallel       Rule D: Selective
  "Giá BTC?"            "Audit 0xabc"         "Phân tích toàn diện"  "Token có scam?"
        │                      │                      │                     │
        ▼                      ▼                      ▼                     ▼
  call get_*()          task(1 agent)         task(4-11 agents) ★    task(2-3 agents)
                                              ★ ALL in 1 LLM turn
                                              → LangGraph batch
```

**Critical insight cho NFR-Q2 (parallelism ratio < 1.3x)**: LangGraph chỉ batch parallel khi LLM emit MULTIPLE `task()` calls trong **CÙNG 1 response**. Prompt phải chứa explicit example block để LLM internalize pattern.

**Token budget**: ~2000 tokens added vào main prompt (acceptable trong 47KB total budget).

**Anti-pattern detection** (capture bởi `ParallelismTelemetryMiddleware` §2):
- Multiple `task()` calls across different `langgraph_step` IDs → log `sequential_antipattern_counter`.
- Operations team alert khi rate > 5% trong 1h.

---

### 6. NFR-Q1..Q5 Measurement Architecture

**Mapping**: 5 quality gates → telemetry → dashboard tiles. (NFR-Q1-Q4 = product gates per PRD; NFR-Q5 = orchestrator routing gate added 2026-04-23 to disambiguate from accuracy.)

| NFR | Definition | Metric source | Dashboard tile | Alert threshold |
|-----|-----------|---------------|----------------|----------------|
| **NFR-Q1** Accuracy | Factual error rate < 3% (sample QA vs raw API ground truth) | Manual QA 100 queries / 2 weeks + automated cross-check sampling | Gauge "% factual errors" | > 3% trong 2-week window |
| **NFR-Q2** Parallelism ratio | P95 `total_elapsed / max(individual)` < 1.3x | `parallelism_ratio_histogram` (Story 0.5) | Histogram with P50/P95/P99 lines | P95 > 1.3x trong 1h |
| **NFR-Q3** Graceful degradation | ≥ 98% requests `success+partial` outcome | `crypto_orchestra_graceful_degradation_total{outcome}` | Gauge "% graceful" | < 98% trong 1h |
| **NFR-Q4** Speed | P95 full-suite duration < 90s | `full_suite_duration_seconds` histogram | Histogram with P50/P95 + 90s threshold line | P95 > 90s trong 1h |
| **NFR-Q5** Smart selection accuracy | ≥ 90% queries route đúng Rule A/B/C/D | Manual classification 20 sample queries (Story 0.3 AC6) + production sampling | `orchestra.spawn` event distribution by agent_count buckets {1, 2, 3, 4+} | < 85% trong tuần |

**Telemetry stack:**
- **Backend metrics**: Prometheus client (`prometheus_client` lib) — 4 metrics defined trong `app/observability/metrics.py`.
- **Frontend events**: 8 telemetry events (xem `ux-crypto-orchestra-handoff.md` §4) → existing analytics pipe.
- **Dashboard**: Grafana panel "Crypto Orchestra Health" với 4 tiles + sequential anti-pattern counter.

**Sample sizing**:
- NFR-Q1: Manual QA 100 queries / 2 weeks (production sampling vs raw API ground truth).
- NFR-Q5: 20 manual queries cho Story 0.3 AC, then production sampling 100 queries/day.
- NFR-Q2/Q4: Statistical benchmark 100 queries (Story 0.5 AC4-AC5) + production rolling P95.
- NFR-Q3: 100 queries với fault injection (Story 0.6 AC10) + production rolling.

---

### 7. Resolution — 5 Open Design Questions từ UX Handoff §7

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Agent display names i18n? | ✅ **Technical EN-only cho v1** (`whale_tracker` → `display_name: "whale-track"`) | i18n sẽ thêm complexity ở `AgentManifest`; v2 evaluate sau khi có user feedback. |
| 2 | Retry agent-level vs query-level? | ✅ **Query-level only cho v1** | Single-agent re-spawn đòi hỏi state preservation phức tạp (graph step replay). v1 retry button → re-run full query. v2 implement single-agent retry với cached results from successful agents. |
| 3 | Cancel semantics — terminate ongoing LLM streams? | ✅ **Best-effort terminate** — issue `agent.cancel()` trên `asyncio.Task` của mỗi sub-agent. Cost vẫn count cho tokens đã consumed (industry standard). Frontend hiển thị "cancelled, partial cost incurred". | Hard-stop LLM streams unsafe (provider abstraction). Best-effort matches OpenAI/Anthropic patterns. |
| 4 | Conflict threshold cho `[2≠4]` citation? | ✅ **Numeric field với delta > 5%** (UX recommendation accepted). Implement trong `<MultiCitationBadge />` rendering layer — backend KHÔNG emit conflict event (xem §1 decision #4). | Pure FE detection avoids backend coupling; threshold tunable via constants. |
| 5 | Background mode cross-tab sync? | ✅ **Single-tab MVP**, v2 cross-tab via BroadcastChannel | MVP scope; cross-tab adds complexity to Zustand persistence layer + race conditions. |

---

### 8. Files Touched / Created (Backend Summary)

**New files (Epic 0)**:
- `app/agents/new_chat/tools/defillama.py` (5 tools)
- `app/agents/new_chat/tools/crypto_sentiment.py` (2 tools)
- `app/agents/new_chat/tools/crypto_news.py` (2 tools)
- `app/agents/new_chat/tools/contract_analysis.py` (2 tools)
- `app/agents/new_chat/middleware/parallelism_telemetry.py`
- `app/agents/new_chat/middleware/circuit_breaker.py`
- `app/agents/new_chat/subagents/crypto/` (4 base + 6 advanced specs)
- `app/schemas/sse_events.py` (6 Orchestra event types)
- `app/observability/metrics.py` (4 Prometheus metrics)

**Modified files**:
- `app/agents/new_chat/tools/registry.py` (+11 ToolDefinition entries)
- `app/agents/new_chat/chat_deepagent.py` (+ParallelismTelemetryMiddleware + CircuitBreakerMiddleware in `gp_middleware`; wire 10 crypto sub-agents into SubAgentMiddleware)
- `app/agents/new_chat/system_prompt.py` (+"Crypto Analysis Orchestration" section ~2000 tokens)
- `app/api/routes/chat.py` (inject sse_publisher into telemetry middleware)

**Frontend** (xem `ux-crypto-orchestra-handoff.md` §8 cho danh sách đầy đủ): 8 components mới + 1 Zustand store + 1 telemetry helper.

---

### 9. Cross-cutting Concerns & Constraints

**Performance**:
- HTTP timeout: 30s mặc định (override per-tool nếu cần). Total per-agent budget ~45s.
- ToolNode parallel: LangGraph dùng `asyncio.gather` — concurrency unbounded; rely on per-API rate limiter (CoinGecko 30/min, GoPlus 2000/day).
- `httpx.AsyncClient` reused per-tool-call (connection pooling) — NOT shared across tools (avoid coupling).

**Security**:
- All crypto tools `requires=[]` → no DB session, no user PII access. Safe to run in Celery worker pool standalone.
- API keys (Etherscan, BscScan) qua `pydantic-settings` env vars; NOT logged.
- Tool errors logged với `exc_info=True` nhưng KHÔNG include user query content (PII safety).

**Observability**:
- All 4 NFR-Q metrics exported qua `/metrics` endpoint (Prometheus scraping).
- Structured logs (JSON): `{request_id, query_hash, agents_spawned, parallelism_ratio, outcome}`.
- LangSmith tracing optional (env `LANGSMITH_TRACING=true`) cho deep debugging.

**Rollback / Feature Flags**:
- `PARALLELISM_TELEMETRY_ENABLED` (default true) — disable middleware nếu perf regression.
- `CIRCUIT_BREAKER_ENABLED` (default true) — disable nếu false-positive opens.
- `DEGRADATION_TELEMETRY_ENABLED` (default true).
- Per-agent kill switch: `CRYPTO_AGENT_<NAME>_ENABLED` env vars (e.g., `CRYPTO_AGENT_WHALE_TRACKER_ENABLED=false`) — agent KHÔNG được spawn nếu false.

---

### 10. Implementation Sequence (Crypto Orchestra Delta)

**Phase 0 (Foundation, blocking Phase 1)** — Stories 0.1 → 0.6 sequential:
1. **Story 0.1** Tool infrastructure (4 files, 11 tools, registry).
2. **Story 0.2** 4 base sub-agent specs + SubAgentMiddleware wiring.
3. **Story 0.3** Main agent orchestration prompt (system_prompt.py).
4. **Story 0.4** API integration tests (real API calls).
5. **Story 0.5** Parallel execution validation + `ParallelismTelemetryMiddleware`.
6. **Story 0.6** Error handling + `CircuitBreakerMiddleware` + degradation tests.

**Gate**: Quality Gates NFR-Q2/Q3/Q4 PASS trên 100-query benchmark → Phase 1.

**Phase 1 (Epic 9 base + UX MVP)** — Parallel:
- Backend: Stories 9.1 (Tokenomics) + 9.4 (Yield Optimizer) — leverages existing tools.
- Frontend: UX phase 9.0 (`OrchestraStrip` + `AgentRow` + `DegradationNotice` + extended `CitationBadge`).

**Phase 2 (Epic 9 advanced + Trust polish)**:
- Backend: Stories 9.2 (Whale) + 9.5 (Governance).
- Frontend: UX phase 9.1 (`ConflictCompare` + `SourceTabsPanel` + 8 telemetry events).

**Phase 3 (Final batch)**:
- Backend: Stories 9.3 (Token Unlock) + 9.6 (Technical Analysis).
- Frontend: UX phase 9.2 (background mode + 5-min cache + soft-attention milestone).

---

### 11. Coherence with Existing Architecture

**Decision Compatibility ✅**:
- Reuses Epic 7 SSE pipeline (`/api/v1/chat`) — zero net-new transport layer.
- LangGraph DeepAgent + SubAgentMiddleware pattern đã production cho `general_purpose` agent — extension chỉ là registry entries.
- Tool factory + `requires=[]` pattern đã established bởi `chainlens_research.py` — clone proven approach.
- Pydantic schemas alias `by_alias=True` (existing rule) áp dụng cho `OrchestraEvent` types → camelCase JSON cho frontend.

**Non-conflicting với baseline**:
- KHÔNG đổi DB schema (no new tables backend-side; FE Rocicorp Zero `orchestra_sessions` table optional, separate concern).
- KHÔNG đổi authentication/RLS — sub-agents chạy trong cùng request context của main agent.
- KHÔNG đổi Celery worker pool — crypto tools chạy in-request (FastAPI async), không enqueue.

**Naming compliance**:
- Sub-agent names: `snake_case` ✅ (Python convention).
- SSE event names: `orchestra.<verb>` lower dot-notation ✅.
- Pydantic event classes: `PascalCase` ✅.
- Tool function names: `snake_case` ✅ (Python convention + LangChain tool naming).
