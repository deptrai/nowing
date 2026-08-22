# Kiến trúc - Nowing Backend

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Backend FastAPI cung cấp REST API cho toàn bộ hệ sinh thái Nowing: xác thực, quản lý workspaces, tài liệu, chat agents, scrapers, connectors, podcast/video, automations, notifications, billing, gateway messaging.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Runtime | Python 3.12, Uvicorn |
| Framework | FastAPI, Starlette, Pydantic v2 |
| ORM/DB | SQLAlchemy 2 async, Alembic, PostgreSQL, pgvector |
| Cache/Queue | Redis, Celery |
| Auth | fastapi-users, JWT, Google OAuth, PAT |
| Search | pgvector hybrid + full-text + reciprocal rank fusion |
| LLM/ML | LiteLLM, LangChain/LangGraph, sentence-transformers, chonkie, Docling/Unstructured/LlamaCloud |
| Observability | OpenTelemetry, SlowAPI rate limiter |
| Deployment | Docker, Docker Compose |

## Kiến trúc tổng thể

- **Layered / modular monolith:** `app/routes/` (controllers) → `app/services/` / `app/tasks/` / `app/capabilities/` (business logic) → `app/db.py` (models) + `app/retriever/` (search).
- **Async-first:** tất cả database I/O dùng `AsyncSession` của SQLAlchemy.
- **Lifespan hooks:** khởi tạo DB, Zero publication, OpenTelemetry, embedding model, agent caches, gateway workers.
- **Capability pattern:** các scraper (reddit, youtube, tiktok, instagram, google_search, google_maps, amazon, web) kế thừa chung từ `app/capabilities/core/` và tự đăng ký route qua `build_capabilities_router()`.

## Entry points

- `main.py` – khởi động Uvicorn với config từ `app/config/uvicorn.py`.
- `celery_worker.py` – khởi động Celery worker.
- `app/app.py` – tạo FastAPI app, đăng ký middleware & routers.
- `app/routes/__init__.py` – xây dựng `crud_router` bao gồm hơn 40 module route.

## Các module nghiệp vụ chính

| Module | Mục đích |
|---|---|
| `app/routes/` | FastAPI endpoints |
| `app/capabilities/` | Scraper APIs (Reddit, YouTube, TikTok, Instagram, Google Search/Maps, Amazon, Web) |
| `app/agents/` | Multi-agent chat runtime, LangGraph/LangChain pipelines |
| `app/indexing_pipeline/` | Xử lý upload, chunking, embedding, lưu tài liệu |
| `app/retriever/` | Hybrid semantic + full-text search |
| `app/etl_pipeline/` | Parsers (Docling, Azure DI, LlamaCloud, Unstructured) |
| `app/connectors/` | Google Drive, OneDrive, Dropbox, external OAuth connectors |
| `app/services/` | Notion, Linear, Slack, Gmail, Calendar, memory, mcp_oauth |
| `app/gateway/` | Discord, Telegram, Slack, WhatsApp BYO messaging gateway |
| `app/notifications/` | Real-time notifications qua Zero |
| `app/podcasts/` | Tạo podcast, transcript, TTS |
| `app/automations/` | Scheduled/event-triggered agent workflows |
| `app/file_storage/` | Quản lý file gốc đã upload |
| `app/utils/` | Helpers, proxy, crawl, captcha |

## API Design

Xem chi tiết trong [api-contracts-backend.md](./api-contracts-backend.md) và [data-models-backend.md](./data-models-backend.md).

## Testing

- `tests/unit/` – unit tests theo domain.
- `tests/integration/` – cần PostgreSQL thật.
- `tests/e2e/` – end-to-end tests với fakes/fixtures.
- `pytest` với markers `unit`/`integration`.

## Deployment

- `Dockerfile` build backend image.
- `docker/` chứa `docker-compose` và script cài đặt (`install.sh`/`install.ps1`).
- `.env.example` liệt kê tất cả biến môi trường cần thiết.

## Cập nhật 2026-08-11

Các module mới / thay đổi kể từ đợt scan trước:

- `app/canonical/` — canonical entity persistence (E13 kế thừa, E20).
- `app/event_bus/` — Redis-backed event bus cho async runs (E9.3).
- `app/notifications/` — real-time notifications qua Zero (E11.1).
- `app/observability/` — OpenTelemetry spans/metrics (E8.9).
- `app/gateway/` — Discord, Telegram, Slack, WhatsApp messaging gateway.
- `app/automations/` — automation engine với `RunService`, scheduler, playbook (E6).
- AD-15/AD-17 — `chainlens.research` dùng async door sẵn có; cost parse từ `done.usage.costDollars`.
- AD-27/AD-28 re-scoped — scraper output feeds `chainlens-research`; Nowing không giữ canonical index.
- AD-29/AD-30/AD-31 — public/vertical agent-chat, `client_id` tenancy.
- AD-32/AD-33 — connector dedicated page, Generic Alert Engine dùng Automation runtime.

## Cập nhật 2026-08-23

- AD-119 — **Deterministic-First Parsing & Selective Micro-LLM Fallback**: quy chuẩn chính thức rằng mọi scraper BẮT BUỘC thực hiện bóc tách dữ liệu bằng Regex/BS4/Pydantic trước (Pass 1, 0 token LLM). Chỉ record có confidence < 0.70 hoặc thiếu trường quan trọng mới được chuyển sang Micro-LLM Fallback (Pass 2, Tier 1 model). Pipeline hậu xử lý (Deduplication, Scoring, DNC Suppression) hoàn toàn deterministic.

## Scraper Data Engineering Pipeline

Mọi dữ liệu scrape đều đi qua pipeline đa tầng trước khi đến LLM Agent:

```
Raw HTML/JSON (Source)
    ↓
Pass 1: Pure Deterministic Parsers (Regex, BS4, Pydantic) — 0 token LLM
    ↓
Confidence Gate (≥ 0.85 → direct persist, < 0.70 → Pass 2 eligible)
    ↓
Pass 2: Selective Micro-LLM (Tier 1 only, ≤ 200 tokens/call) — chỉ trường bị thiếu
    ↓
Deduplication (Union-Find on phone/address/image hash)
    ↓
Rule-Based Scoring (Source Trust, Overlap, Freshness, Price Consistency)
    ↓
DNC/Blacklist Suppression
    ↓
Token Budget Guard (RUN_OUTPUT_CHAR_CAP = 40k chars)
    ↓
Agent Context (inline hoặc run_<uuid> reference)
```

Xem chi tiết AD-119 tại [ARCHITECTURE-SPINE.md (Unified)](../_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md).

Xem chi tiết tại [project-overview.md](./project-overview.md) và [planning-to-product.md](./planning-to-product.md).

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
