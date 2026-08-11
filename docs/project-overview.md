# Nowing — Tổng quan dự án

**Phiên bản quét:** 2026-08-11  
**Kỹ năng:** `bmad-document-project` full-scan workflow  
**Ngôn ngữ tài liệu:** Tiếng Việt

> **Nowing là open-core research memory cho AI agents — nó nhớ những gì nó đi tìm, không chỉ những gì bạn nói với nó.**

Nowing là một **self-hosted research workspace** có **bộ nhớ nghiên cứu dài hạn (long-term memory)** cho agents và đội nhóm, được xây dựng trên lõi **Apache-2.0** và một **hosted deep-research engine**. Agents có thể nghiên cứu web trực tiếp thông qua dữ liệu có cấu trúc từ Reddit, YouTube, Instagram, TikTok, Amazon, Google Maps, Google Search và các trang web khác — thông qua một **REST API** hoặc **MCP server** duy nhất. Agents chạy theo lịch hoặc sự kiện, chuyển kết quả thành briefs, reports, podcasts, presentations, và hệ thống knowledge base giữ mọi phát hiện có thể tìm kiếm với trích dẫn nguồn.

## Sản phẩm mục tiêu

Sản phẩm cuối cùng là một nền tảng **research-memory mở lõi**, cho phép:

1. **Tự lưu trữ miễn phí (self-host)** với đầy đủ lõi Apache-2.0: knowledge base, hybrid search, citations, chat, deliverables, automations và MCP tools.
2. **Cloud pay-as-you-go** với deep-research engine được meter và các hosted connectors.
3. **Multi-surface**: web (Next.js), desktop (Electron), browser extension, Obsidian plugin, MCP server và evals harness.
4. **Agentic research workspace**: agents tự động nghiên cứu web, trích xuất memory, tạo deliverables, viết lại (write-back) Notion/Slack/Linear/Jira, và gửi thông báo Telegram.
5. **Vertical expansion**: hiện tập trung pilot **HR/Recruitment Việt Nam** (VietnamWorks, TopCV, ITviec) và **Lead Intelligence** (Epic 21) như hướng mở rộng thị trường.

## Trạng thái hiện tại (tính đến 2026-08-11)

- **18+ Epics** được định nghĩa, trong đó nền tảng cốt lõi (E1–E9, E11, E18) phần lớn **DONE**.
- **Epic 12 (HR Việt Nam)** đang in-progress; 12-1, 12-2 done; 12-3/12-4/12-5 in-progress; 12-9 ready-for-dev.
- **Epic 20 (Ecosystem / ChainLens integration)** đang in-progress với 4 story 20-1→20-4 in-progress.
- **Epic 21 (Lead Intelligence)** ở trạng thái **backlog**; `bmad-architecture` validate **PASS** (architecture FIT for implementation), nhưng còn các governance gate pháp lý/kỹ thuật chưa đóng.
- **Migration 175–179 (memory layer)** chưa lên production tính đến 2026-08-01 (prod đang ở alembic 174).
- **Cổng public repo** bị chặn bởi vấn đề attribution/license kế thừa từ upstream SurfSense (AD-16.1) cần luật sư xem xét.

## Kiến trúc tổng thể

Dự án là **monorepo 7 phần**:

| Phần | Công nghệ | Vai trò |
|---|---|---|
| `nowing_backend` | Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL/pgvector, Redis/Celery | REST API, business logic, agents, scrapers, automations, billing |
| `nowing_web` | Next.js 16, React 19, TypeScript, Tailwind v4, Jotai/Zustand, Zero sync | Web app, dashboard, landing, docs site |
| `nowing_desktop` | Electron 42, TypeScript | Desktop app bọc web + native IPC |
| `nowing_browser_extension` | Plasmo, React | Tiện ích trình duyệt |
| `nowing_obsidian` | TypeScript, esbuild, Obsidian API | Plugin Obsidian |
| `nowing_mcp` | Python 3.11, MCP SDK, Starlette | MCP server stateless gọi backend |
| `nowing_evals` | Python 3.12, CLI | Evaluation harness (chat regression, memory recall, canonical) |

### Kiến trúc backend (AD chính)

- **AD-1:** Backend là monolith module hóa, không microservice nội bộ.
- **AD-2:** Async SQLAlchemy + Alembic + PostgreSQL/pgvector.
- **AD-3:** Scraper capabilities tự đăng ký route qua `build_capabilities_router()`.
- **AD-4:** Multi-agent chat runtime với tool registry và permission middleware.
- **AD-5:** Zero sync (Rocicorp) cho real-time client state.
- **AD-6:** Next.js server proxy tới backend.
- **AD-7:** MCP server stateless với workspace context.
- **AD-8:** Unified credit wallet, cost thật từ `costDollars` của ChainLens.
- **AD-11:** Long-term research memory là first-class persistence layer (unified `Memory` table).
- **AD-15:** ChainLens là external deep-research dependency, không phải scraper.
- **AD-16 / AD-16.1:** Ranh giới license 3 tầng (Apache-2.0 core / BSL 1.1 `app/proprietary/` / closed-source deep-research engine) và cổng attribution.
- **AD-17:** Deep research dùng async door sẵn có, không tạo flow mới.
- **AD-18:** Memory injection có bounded retrieval, tách `memory_injection` vs `memory_recall`.
- **AD-19 / AD-20:** Anti-bot/CAPTCHA thuộc Nowing; screenshot-as-evidence dùng browser sẵn có.
- **AD-29 / AD-30 / AD-31:** Public agent-chat surface, AgentConfig registry, vertical client tenancy.

### Tích hợp cross-part

- Web → Backend: REST proxy `app/api/v1/[...path]/route.ts` và Zero sync `/api/zero/{mutate,query}`.
- MCP → Backend: REST qua `mcp_server/core/client.py`.
- Evals → Backend: REST clients.
- Desktop → Web: Electron embed; Desktop → Backend: HTTP/IPC.
- Extension / Obsidian → Backend: REST với PAT (`nw_pat_...`).
- Backend → ChainLens: `POST /api/v1/search` SSE; deep-research cost phản hồi qua `done.usage.costDollars`.
- Backend → Stripe: billing.
- Scrapers → ChainLens: `POST /v1/ingest/scraper` theo AD-34.

## Danh sách Epic và trạng thái

> Nguồn: `sprint-status.yaml` (cập nhật 2026-08-11) + `epics.md`.

| Epic | Tên | Trạng thái | Ghi chú nhanh |
|---|---|---|---|
| E1 | Identity, Auth & Workspace RBAC | ✅ done | Brownfield, đã hoạt động trên production |
| E2 | Connectors | ✅ done | 6 story done; retrospective 2026-08-08 |
| E3 | Knowledge Base + Long-Term Memory | ✅ done | 3.15/3.16 done; 3.17 in-progress |
| E4 | Chat & Agents | ✅ done | 4.7/4.8 done; benchmark suite done |
| E5 | Deliverables | ✅ done | Brownfield |
| E6 | Automations | ✅ core done | 6.4–6.5 done; playbook layer business-gated |
| E7 | Multi-surface Clients | ✅ done | 7-4, 7-7 done |
| E8 | Cost Visibility & Control | ✅ done | 8.3/8.7/8.8/8.10/8.11/8.12/8.13 done |
| E9 | Deep Research đáng tin cậy | ✅ done | 9.1–9.4, 9.6 done; 9.5 deferred; 9.6c in-progress |
| E10 | Connector & Scraper Expansion | ✅ done | BĐS scraper/aggregator done |
| E11 | Telegram Automation & Bot | ✅ done | 11-1/11-2/11-3 done |
| E12 | HR/Recruitment — Vietnam Job Market | 🔄 in-progress | 12-1/12-2 done; 12-3/12-4/12-5 in-progress; 12-9 ready-for-dev |
| E14 | News Aggregation (Vietnam) | 🔄 in-progress | 14-1 done |
| E15 | Financial Data (Vietnam) | 🔄 in-progress | 15-1 done |
| E16 | Company Directory (Vietnam) | 🔄 in-progress | 16-1 done |
| E17 | E-commerce Intelligence (Vietnam) | ⏸️ backlog | P2 — deferred to Phase 2; product data fed to `chainlens-research` |
| E18 | Vertical Client Platform (Public Agent-Chat) | 🔄 in-progress | 18-1→18-8 done |
| E20 | Nowing Ecosystem Integration (ChainLens) | 🔄 in-progress | 20-1→20-4 in-progress |
| E21 | Lead Gen Intelligence | ⏸️ backlog | Architecture FIT (`bmad-architecture` PASS); governance gates chưa đóng |
| E13 | Canonical Entity Storage | ❌ dropped | Re-scoped sang `chainlens-research` |
| Tech Debt | — | 🔄 in-progress | 7 mục backlog (idempotency, Redis event bus, storage reconcile, notification race, timeout/retry, test coverage) |

> **Về số thứ tự bị nhảy:**
> - **E13** từng tồn tại (Canonical Entity Storage) nhưng đã **dropped** 2026-08-08; chức năng canonical multi-domain chuyển sang `chainlens-research`.
> - **E17** tồn tại (E-commerce Intelligence) nhưng ở **backlog/P2**; trước đây bị nhóm chung vào “E14–E17 VN data verticals”.
> - **E19** đã **removed** 2026-08-06 (Search Intelligence) vì trùng với ChainLens generic web crawl (FR-24); Google Places có thể complement BĐS nhưng chưa scope rõ.

## Cổng mở, rủi ro và hành động tiếp theo

### Cổng kỹ thuật / vận hành

1. **Memory production deploy** — Migration 175–179 (memory layer, auto-extract, wallet) chưa lên prod. Cần chạy `alembic upgrade head` theo thứ tự `mig177 → backfill → mig178` sau khi E3.10/3.14 đã xong.
2. **Deep-research multi-replica** — `run_event_bus` hiện single-process; cần Redis pub/sub trước khi bật async trên nhiều replica.
3. **Agent door async** — `app/capabilities/core/access/agent.py` gọi ChainLens sync, block chat turn tới 300s. Cần chuyển sang submit-and-return.
4. **NFR-1 Performance** — vẫn `PARTIAL`, chưa gán epic. Cần benchmark và gán owner.
5. **Tech debt backlog** — 7 mục P0/P1/P2 chưa có story cụ thể.

### Cổng pháp lý / chiến lược

1. **Attribution / license** (AD-16.1) — cần luật sư xác nhận trước khi public repo.
2. **Epic 12 ToS / legal** — Legal counsel approved all 3 sources (VietnamWorks, TopCV, ITviec) 2026-08-08. VietnamWorks/TopCV code verified (AD-22/AD-23 ADOPTED); TopCV anti-bot POC remains a hard gate before merge.
3. **Epic 21 governance** — email outreach legal/ToS, vendor POC (Cleanlist/BetterContact), Zalo OA, PII/consent pipeline, CRM sync scope.
4. **Story 9.5** — metered self-host endpoint chờ SCP approval.

### Hành động tiếp theo (path to final product)

1. **Hoàn thành Epic 12 pilot** — đưa 12-3/12-4/12-5/12-9 về done, chạy pilot BĐS/HR Việt Nam.
2. **Hoàn thành Epic 20** — `NowingIngestService`, gap-fill caller, `NowingPrivateProvider`, cost ledger sync.
3. **Production memory rollout** — merge develop → main, chạy migrations/backfill, bật auto-extract sau khi 8.7 done.
4. **Đóng deep-research multi-replica + agent async** — mở State B sync chat-mode khi p95 `balanced` ≤ 30s.
5. **Chuẩn bị Epic 21** — đóng governance gates, viết lại story với concrete metrics, error paths, PII/consent gating.
6. **Resolve tech debt + NFR-1** — lập story cho td-1→td-7, benchmark performance.
7. **Public repo readiness** — xin ý kiến luật sư về Apache-2.0 §4 attribution và BSL Licensor.

## Tài liệu liên quan

- [Tổng quan kiến trúc](./architecture-backend.md) — chi tiết backend.
- [Kiến trúc tích hợp](./integration-architecture.md) — luồng dữ liệu giữa các phần.
- [Cây thư mục](./source-tree-analysis.md) — bố cục repository.
- [Epic & Sprint](./planning-to-product.md) — chi tiết epic, sprint status, readiness, path to product.
- [Hợp đồng API](./api-contracts-backend.md) — API backend.
- [Mô hình dữ liệu](./data-models-backend.md) — database schema.
