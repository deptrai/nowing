# Nowing — Tài liệu dự án

> **Nowing là open-core research memory cho AI agents — nó nhớ những gì nó đi tìm, không chỉ những gì bạn nói với nó.**

**Ngày quét:** 2026-08-11  
**Ngôn ngữ tài liệu:** Tiếng Việt  
**Skill:** `bmad-document-project` full rescan

Đây là chỉ mục chính (master index) cho AI-assisted development. Từ đây có thể đi đến mọi tài liệu kỹ thuật, kiến trúc, lập kế hoạch và vận hành.

## Bắt đầu nhanh

| Bạn muốn biết... | Tài liệu |
|---|---|
| Nowing là gì, sản phẩm mục tiêu, trạng thái hiện tại | [project-overview.md](./project-overview.md) |
| Từ kế hoạch đến sản phẩm: epic, sprint, cổng mở, path to final product | [planning-to-product.md](./planning-to-product.md) |
| Bố cục repository và cây thư mục | [source-tree-analysis.md](./source-tree-analysis.md) |
| Các phần giao tiếp với nhau như thế nào | [integration-architecture.md](./integration-architecture.md) |
| Chạy dự án, test, kiểm thử | [testing.md](./testing.md) |
| CI/CD, Docker, triển khai | [ci.md](./ci.md), [docker/docker-compose.yml](../docker/docker-compose.yml) |

## Tổng quan dự án

### Monorepo 7 phần

| Phần | Loại | Công nghệ chính | Tài liệu kiến trúc |
|---|---|---|---|
| `nowing_backend` | Backend | Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL/pgvector, Redis/Celery | [architecture-backend.md](./architecture-backend.md) |
| `nowing_web` | Web app | Next.js 16, React 19, TypeScript, Tailwind v4, Jotai/Zustand, Zero sync | [architecture-web.md](./architecture-web.md) |
| `nowing_desktop` | Desktop | Electron 42, TypeScript | [architecture-desktop.md](./architecture-desktop.md) |
| `nowing_browser_extension` | Browser extension | Plasmo, React | [architecture-browser_extension.md](./architecture-browser_extension.md) |
| `nowing_obsidian` | Obsidian plugin | TypeScript, esbuild | [architecture-obsidian.md](./architecture-obsidian.md) |
| `nowing_mcp` | MCP server | Python 3.11, MCP SDK, Starlette | [architecture-mcp.md](./architecture-mcp.md) |
| `nowing_evals` | Evals harness | Python 3.12, CLI | [architecture-evals.md](./architecture-evals.md) |

### Stack chung

- **Cơ sở dữ liệu:** PostgreSQL 17 + pgvector.
- **Cache / queue:** Redis 8 (Celery + event bus).
- **ORM / migrations:** SQLAlchemy 2 async + Alembic.
- **Real-time sync:** Rocicorp Zero (Postgres logical replication).
- **LLM/ML:** LiteLLM, LangChain/LangGraph, sentence-transformers, chonkie, Docling, LlamaCloud, Unstructured.
- **Auth:** fastapi-users, JWT, Google OAuth, PAT.
- **Billing:** Stripe + `User.credit_micros_balance` unified wallet.
- **Observability:** OpenTelemetry.
- **Search:** pgvector hybrid + full-text + reciprocal rank fusion.
- **Container:** Docker, Docker Compose, Caddy reverse proxy.

## Kiến trúc và quyết định thiết kế

Các Architecture Decision (AD) chính được ghi trong `ARCHITECTURE-SPINE.md` và tóm tắt ở [project-overview.md](./project-overview.md):

- **AD-1:** Backend monolith module hóa.
- **AD-2:** Async SQLAlchemy + Alembic + PostgreSQL/pgvector.
- **AD-3:** Scraper capabilities tự đăng ký route.
- **AD-4:** Multi-agent chat runtime với tool registry và permission middleware.
- **AD-5:** Zero sync cho real-time client state.
- **AD-6:** Next.js server proxy tới backend.
- **AD-7:** MCP server stateless với workspace context.
- **AD-8:** Unified credit wallet + cost thật từ ChainLens.
- **AD-11:** Long-term research memory là first-class persistence layer.
- **AD-15:** ChainLens là external deep-research dependency, không phải scraper.
- **AD-16 / AD-16.1:** Ranh giới license 3 tầng và cổng attribution.
- **AD-17:** Deep research dùng async door sẵn có.
- **AD-18:** Memory injection có bounded retrieval.
- **AD-19 / AD-20:** Anti-bot/CAPTCHA và screenshot-as-evidence.
- **AD-29 / AD-30 / AD-31:** Public agent-chat, AgentConfig registry, vertical client tenancy.
- **AD-32 / AD-33:** Connector management page canonical, Generic Alert Engine.
- **AD-36 → AD-42:** Epic 21 Lead Intelligence (waterfall, signal, scoring, sequencer, CRM, Zalo/LinkedIn deferred, outcome pricing).

## Epic và trạng thái phát triển

> Chi tiết đầy đủ: [planning-to-product.md](./planning-to-product.md).

| Trạng thái | Số epic |
|---|---|
| ✅ Done | E1, E2, E3, E4, E5, E6 (core), E7, E8, E9, E10, E11 |
| 🔄 In-progress | E12, E14, E15, E16, E18, E20, Tech Debt |
| ⏸️ Proposed | E21 |
| ❌ Dropped | E13 (re-scoped sang `chainlens-research`) |

### Các epic đang mở (tính đến 2026-08-11)

- **E12 — HR/Recruitment Việt Nam:** VietnamWorks (done), TopCV/ITviec (in-progress), `vn_jobs.aggregate`, PII redaction, Saved Searches.
- **E14–E16 — Data verticals VN:** News, Financial, Company Directory.
- **E18 — Vertical Client Platform (Public Agent-Chat):** done các story chính; tiếp tục hardening.
- **E20 — ChainLens Ecosystem Integration:** ingest, gap-fill, private provider, cost ledger sync.
- **E21 — Lead Intelligence:** proposed, chờ governance gates.

## Cổng mở và rủi ro

### Kỹ thuật

1. Memory production deploy (migrations 175–179 chưa lên prod).
2. Deep-research multi-replica (Redis pub/sub) và async agent door.
3. NFR-1 Performance chưa gán epic.
4. Tech debt backlog 7 mục.

### Pháp lý / chiến lược

1. Public repo attribution/license (AD-16.1).
2. Epic 12 ToS/anti-bot POC (TopCV/ITviec).
3. Epic 21 governance (email outreach, vendor, Zalo, PII, CRM sync).
4. Story 9.5 metered self-host endpoint chờ SCP.

### Path to final product

1. Hoàn thành Epic 12 pilot.
2. Hoàn thành Epic 20 (ChainLens integration).
3. Production memory rollout.
4. Đóng deep-research async scale-out.
5. Chuẩn bị Epic 21 sau khi governance gates đóng.
6. Resolve tech debt + NFR-1.
7. Public repo sau khi luật sư xử lý attribution.

## Tài liệu kỹ thuật chi tiết

### Backend

- [architecture-backend.md](./architecture-backend.md)
- [api-contracts-backend.md](./api-contracts-backend.md)
- [data-models-backend.md](./data-models-backend.md)
- [development-guide-backend.md](./development-guide-backend.md)
- [chinese-llm-setup.md](./chinese-llm-setup.md)

### Web

- [architecture-web.md](./architecture-web.md)
- [component-inventory-web.md](./component-inventory-web.md)
- [development-guide-web.md](./development-guide-web.md)

### Các client khác

- [architecture-desktop.md](./architecture-desktop.md) / [development-guide-desktop.md](./development-guide-desktop.md)
- [architecture-browser_extension.md](./architecture-browser_extension.md) / [development-guide-browser_extension.md](./development-guide-browser_extension.md)
- [architecture-obsidian.md](./architecture-obsidian.md) / [development-guide-obsidian.md](./development-guide-obsidian.md)
- [architecture-mcp.md](./architecture-mcp.md) / [api-contracts-mcp.md](./api-contracts-mcp.md) / [development-guide-mcp.md](./development-guide-mcp.md)
- [architecture-evals.md](./architecture-evals.md) / [development-guide-evals.md](./development-guide-evals.md)

### Tích hợp và vận hành

- [integration-architecture.md](./integration-architecture.md)
- [source-tree-analysis.md](./source-tree-analysis.md)
- [testing.md](./testing.md)
- [ci.md](./ci.md)
- [ci-secrets-checklist.md](./ci-secrets-checklist.md)
- [project-parts.json](./project-parts.json)

### Artifact nguồn (nằm ngoài `docs/`)

- [`_bmad-output/planning-artifacts/epics.md`](../_bmad-output/planning-artifacts/epics.md)
- [`_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`](../_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md)
- [`_bmad-output/implementation-artifacts/sprint-status.yaml`](../_bmad-output/implementation-artifacts/sprint-status.yaml)
- [`_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11.md`](../_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11.md)

## Cách sử dụng index này

- **Bắt đầu từ đâu:** [project-overview.md](./project-overview.md) để hiểu sản phẩm và trạng thái.
- **Muốn biết còn gì chưa xong:** [planning-to-product.md](./planning-to-product.md) phần *Cổng mở* và *Đường đến sản phẩm*.
- **Muốn tìm code:** [source-tree-analysis.md](./source-tree-analysis.md) hoặc [architecture-{part}.md](./architecture-backend.md).
- **Muốn chạy / test:** [testing.md](./testing.md) và [ci.md](./ci.md).

---

_Tài liệu được tạo/cập nhật bởi BMAD Method `document-project` full-scan workflow._
