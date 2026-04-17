---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-04-13T01:02:23+07:00'
lastUpdated: '2026-04-16'
editHistory:
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

**Gift Subscription Tables (thêm vào migration 127+):**

```sql
-- gift_codes: lưu gift code được tạo sau khi payment thành công
gift_codes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code          VARCHAR(16) UNIQUE NOT NULL,  -- format: GIFT-XXXX-XXXX-XXXX
  plan_id       VARCHAR(50) NOT NULL,          -- e.g. "pro_monthly"
  duration_months INTEGER NOT NULL,            -- 1, 3, 6, 12
  amount_paid   INTEGER NOT NULL,              -- cents (e.g. 1200 = $12.00)
  purchaser_id  INTEGER NOT NULL REFERENCES users(id),
  stripe_payment_intent_id VARCHAR(255),
  redeemer_id   INTEGER REFERENCES users(id), -- NULL cho đến khi redeem
  status        VARCHAR(20) DEFAULT 'active',  -- active|redeemed|expired|revoked
  expires_at    TIMESTAMP NOT NULL,            -- 1 năm từ ngày tạo
  created_at    TIMESTAMP DEFAULT now(),
  redeemed_at   TIMESTAMP                      -- NULL cho đến khi redeem
)

-- gift_requests: admin-approval fallback khi Stripe checkout không hoạt động
gift_requests (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         INTEGER NOT NULL REFERENCES users(id),
  plan_id         VARCHAR(50) NOT NULL,
  duration_months INTEGER NOT NULL,
  status          VARCHAR(20) DEFAULT 'pending', -- pending|approved|rejected
  gift_code_id    UUID REFERENCES gift_codes(id), -- gán khi approved
  created_at      TIMESTAMP DEFAULT now(),
  updated_at      TIMESTAMP DEFAULT now()
)
```

**Gift Code Generation:**
- Format: `GIFT-XXXX-XXXX-XXXX` (12 chars từ `string.ascii_uppercase + string.digits`)
- Entropy: 36^12 ≈ 4.7 × 10^18 combinations (brute-force không khả thi)
- Implementation: `secrets.choice(alphabet)` — cryptographically secure

**Extension Formula khi redeem:**
```python
new_expiry = max(current_period_end, now()) + timedelta(days=30 * duration_months)
```

### Authentication & Security

- **Authentication Method:** JWT Token Auth do Backend FastAPI kiểm soát. Frontend nhận JWT và trao nó cho bộ khởi tạo `ZeroClient`.
- **Authorization Pattern:** Row-level Security (RLS) bắt buộc trên mọi tables Postgres. Logic từ FastAPI đến DB và luồng Zero repl-stream từ DB chọc xuống Next.js đều chịu chung bộ luật RLS này.
- **Security Middleware:** Áp dụng purge (làm sạch) lập tức IndexedDB & localStorage bằng hook `onLogout()`.

### API & Communication Patterns

- **API Design Patterns:** 
  - Standard RESTFul API cho các tác vụ CRUD thường và logic.
  - **Server-Sent Events (SSE) / WebSockets:** Quyết định dùng SSE cho luồng Streaming Response của Agentic RAG vì nó mượt hơn, một chiều từ Server gửi câu trả lời về UI.
  - Zero-sync protocol quản lý kết nối WebSocket cho dữ liệu đồng bộ tĩnh.
- **Job Orchestration:** Kết nối FastAPI và Celery Workers qua Redis Message Broker (`redis:7.4+`).

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
