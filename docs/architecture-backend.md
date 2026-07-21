# Kiến trúc - SurfSense Backend

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Backend FastAPI cung cấp REST API cho toàn bộ hệ sinh thái SurfSense: xác thực, quản lý workspaces, tài liệu, chat agents, scrapers, connectors, podcast/video, automations, notifications, billing, gateway messaging.

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

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
