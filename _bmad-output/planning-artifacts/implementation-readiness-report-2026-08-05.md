---
outputFile: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-05.md
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
includedFiles:
  prd: _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
  architecture: _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md
  epics: _bmad-output/planning-artifacts/epics.md
  ux:
    - _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md
  archived:
    - _bmad-output/planning-artifacts/archive/ux-audit-improvement-spec-2026-07-27.md (STALE, archived)
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05
**Project:** Nowing

## Step 1: Document Discovery

Bắt đầu **Document Discovery** để kiểm kê tất cả tài liệu dự án.

### PRD Files Found

**Sharded Documents:**
- Folder: `prds/prd-Nowing-2026-07-22/`
  - `prd.md` (108,838 bytes, modified 2026-08-05 02:40)
  - `.memlog.md`
  - `review-prfaq-gap.md`
  - `review-rubric.md`
  - `validation-report.md`

### Architecture Files Found

**Sharded Documents:**
- Folder: `architecture/architecture-Nowing-2026-07-22/`
  - `ARCHITECTURE-SPINE.md` (78,269 bytes, modified 2026-08-05 02:40)

**Supplementary Review:**
- `epic-11-architecture-review-2026-08-03.md` (9,154 bytes, modified 2026-08-04 20:16)

### Epics & Stories Files Found

**Whole Documents:**
- `epics.md` (95,649 bytes, modified 2026-08-05 02:38)

**Supplementary Review:**
- `epic-11-architecture-review-2026-08-03.md` (9,154 bytes, modified 2026-08-04 20:16)

### UX Design Files Found

**Whole Documents:**
- `ux-audit-improvement-spec-2026-07-27.md` (14,931 bytes, modified 2026-08-04 20:16)

**Sharded Documents:**
- Folder: `ux-designs/ux-Nowing-2026-07-22/`
  - `ux-contract-async-deep-research.md` (7,417 bytes, modified 2026-08-04 20:16)

### Issues Found

⚠️ **WARNING: Có thể có tài liệu phụ trội**
- `epic-11-architecture-review-2026-08-03.md` xuất hiện trong cả Architecture và Epics — đây là tài liệu review, không phải bản chính.
- Không phát hiện duplicate toàn vẹn giữa whole vs sharded cho cùng một loại tài liệu.

### Required Actions

- Xác nhận tập tài liệu trên đủ để đánh giá.
- Nếu cần thêm tài liệu khác, hãy cho biết vị trí.

**Select an Option:** [C] Continue to File Validation

## Step 2: PRD Analysis

PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (108,838 bytes).

### Functional Requirements Extracted

1. **FR-1**: User Authentication — đăng ký, đăng nhập, refresh/revoke token, logout-all, Google OAuth.
2. **FR-2**: API Access for External Clients — Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng PAT/API key.
3. **FR-3**: Workspace Lifecycle — tạo, liệt kê, xem, cập nhật, xóa workspace.
4. **FR-4**: Workspace Invites & Memberships — mời thành viên, quản lý membership, invite có mã/hạn/số lần dùng.
5. **FR-10**: RBAC với ba system roles — Owner, Editor, Viewer.
6. **FR-6**: Built-in Scraper Connectors — Reddit, YouTube, Instagram, TikTok, Google Search/Maps, Amazon, web crawl.
7. **FR-7**: External OAuth Connectors — Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, v.v.
8. **FR-8**: External MCP Connectors — thêm MCP server bên ngoài vào workspace.
9. **FR-9**: Document Upload, Parse & Index — upload file/URL, parse, chunk, embed, hỗ trợ 50+ định dạng.
10. **FR-11**: Folders & Document Management — tạo/thư mục, di chuyển, đổi tên, xóa documents/folders.
11. **FR-12**: Hybrid Search over Knowledge Base — pgvector semantic + full-text + reciprocal rank fusion.
12. **FR-13**: Citation Panel for Knowledge-base Chunks — click citation mở right panel với chunk window ±5.
13. **FR-32**: Long-Term Research Memory — lưu facts/decisions/observations dưới dạng `Memory`, hybrid search, REST/MCP. `[BUILT/PARTIAL]`
14. **FR-33**: Research Continuity — tiếp tục research thread, tự động recall memory/citations.
15. **FR-34**: Memory Correction — update hoặc flag memory sai, lưu version history.
16. **FR-36**: Legacy Memory Data-Loss Assessment & Recovery — `[RESOLVED 2026-07-25]` không mất dữ liệu.
17. **FR-40**: First-Run Value — Research Runs Produce Memory — `[GAP]` workspace mới không seed, `MemoryExtractionService` chỉ extract từ chat turn.
18. **FR-5**: AI File Sorting — `[REMOVED]`.
19. **FR-14**: Chat Threads & Messages — tạo thread, gửi message, streaming response.
20. **FR-15**: Multi-agent Runtime with Tools — main agent gọi tools, subagents, recall workspace memory.
21. **FR-16**: Real-time Collaborative Chat — multi-user qua Zero sync, comments, mentions.
22. **FR-17**: Anonymous Chat with Quota — chat với document upload và quota giới hạn.
23. **FR-42**: Chat Response Benchmark — benchmark trong `nowing_evals`.
24. **FR-21**: Report Generation & Export — report từ document/folder, export nhiều định dạng.
25. **FR-22**: Podcast & Video Presentation — podcast 2 host dưới 20s, video presentation.
26. **FR-23**: Image Generation — tạo ảnh từ prompt.
27. **FR-18**: Automation Action Types — `agent_task`, direct write-back Notion/Slack/Linear/Jira, `continue_research`. `[DONE]`
28. **FR-19**: Automation Triggers — `schedule` (cron) và `event` (webhook/connector).
29. **FR-20**: Automation Runs & Retries — `AutomationRun` với status, error, retry policy.
30. **FR-35**: Memory-Driven Automations — trigger khi memory thay đổi hoặc continue research. `[DONE]`
31. **FR-25**: Web Client (Next.js) — landing, dashboard, chat, connectors, settings, docs.
32. **FR-26**: Desktop Client (Electron) — bọc web app, global shortcut, quick assist, folder watcher.
33. **FR-27**: Browser Extension (Plasmo) — thu thập lịch sử duyệt web.
34. **FR-28**: Obsidian Plugin — đồng bộ vault qua REST.
35. **FR-29**: MCP Server — expose scraper, KB, memory, research tools qua MCP. `[BUILT]`
36. **FR-30**: Token Usage Tracking — ghi `TokenUsage` per assistant turn.
37. **FR-31**: Credit Wallet & Purchases — `credit_micros_balance`, Stripe, auto-reload. `[GAP]` usage/credit dashboard.
38. **FR-41**: Admin UI cho Global LLM Model Configuration — `[GAP]` quản lý global model qua UI không cần restart.
39. **FR-24**: Deep Open-Web Research via ChainLens Engine — deep research đa nguồn có trích dẫn. `[DONE/PARTIAL]`
40. **FR-37**: Deep-Research Cost Metering — parse `costDollars` thật từ engine, không dùng giá phẳng. `[DONE]`
41. **FR-38**: Research Degradation & Self-Host Independence — degrade sang hybrid search khi engine unavailable. `[DONE/P0]`
42. **FR-39**: Memory → Scraper-Run Provenance & Source Re-Validation — `[GAP]` memory lưu recipe scrape để re-validate.

**Total FRs: 42**

### Non-Functional Requirements Extracted

1. **NFR-1**: Performance — chia thành:
   - **NFR-1a**: CRUD & scraper p95 < 500ms.
   - **NFR-1b**: Memory injection p95 ≤ 150ms, O(top-k), ≤ 8.000 chars. `[GAP]`
   - **NFR-1c**: Recall tool p95 ≤ 300ms, top_k ≤ 5, vượt ngưỡng similarity. `[PARTIAL]`
   - **NFR-1d**: Auto-extract trên Celery, không chặn chat, freshness ≤ 60s.
2. **NFR-2**: Security & Auth — JWT/cookie, PAT, permission check, secrets qua `.env`.
3. **NFR-3**: Observability — OpenTelemetry, `Log` model, SlowAPI, Celery monitoring.
4. **NFR-4**: Reliability — async DB I/O, Celery+Redis, retry policy.
5. **NFR-5**: Multi-tenancy Isolation — workspace-scoped query, `api_access_enabled`.
6. **NFR-6**: Citation Full-Editor Highlight — click citation scroll/highlight trong editor. `[DONE]`
7. **NFR-7**: Usage & Credit Dashboard — `[GAP]` thiếu dashboard tổng hợp.
8. **NFR-8**: Recall Quality (eval-gated) — precision@k/noise rate, cổng chặn launch. `[IN-PROGRESS]`
9. **NFR-9**: Deep-Research Latency & Availability Budget — State A (async) mặc định, State B (sync) khi p95 đạt ngưỡng. `[PARTIAL]`
10. **NFR-10**: Chat Response Regression Gate — mọi deploy production phải qua chat regression gate. `[NEW 2026-08-04]`

**Total NFRs: 10**

### Additional Requirements / Constraints

- **Non-Goals (frozen tới 2026-08-24):** NG-1 (bán research data), NG-2 (parity consumer kiểu Perplexity), NG-3 (ChainLens độc lập).
- **Open Questions:** OQ-1 (MCP marketplace), OQ-2 (agent tool default enable/disable), OQ-3 (retention/right-to-delete/pháp lý), OQ-4 (per-workspace MCP toggle — RESOLVED), OQ-5 (direct write-back architecture — RESOLVED), OQ-6 (docs sync — DONE), OQ-7 (ChainLens answers).
- **Success Metrics:** SM-1..SM-11 với SM-10 (recall quality) và SM-11 (deep-research cost/latency/fallback) là cổng chặn.
- **Assumptions:** self-host tắt billing, MCP per-workspace toggle, write-back via agent_task, citation highlight deferred, retention pháp lý, memory pgvector, 4 MCP tools, memory correction, migration 178 không mất data, ChainLens là engine, cost meter theo `costDollars`, deep research latency "chưa biết", `balanced` mode đủ chất lượng.

### PRD Completeness Assessment

- PRD rất chi tiết, có 42 FR + 10 NFR, đánh số toàn cục, trạng thái `[BUILT]`/`[DONE]`/`[PARTIAL]`/`[GAP]` gắn với code reality.
- Các vùng `GAP` chính: **FR-40** (first-run memory), **FR-39** (provenance/re-validation), **FR-41** (admin global model UI), **NFR-1b/c** (memory injection bounded), **NFR-7** (usage dashboard), **NFR-8** (recall quality gate đang `in-progress`).
- **NFR-8 đã được ratified 2026-08-04** — `memory/recall/gate.yaml` `baseline_ratified: true`.
- **FR-39 / FR-41 đã verify code** — không còn conflict.
- **NFR-10 / Story 4.8 còn `in-progress`** — 4.8f operational metrics done, multi-turn + stress + ChainLens latency remaining; gate chưa ratified.

## Step 3: Epic Coverage Validation

Epic document: `_bmad-output/planning-artifacts/epics.md` (95,649 bytes).

### Epic FR Coverage Extracted

Tất cả **42 FRs** và **10 NFRs** từ PRD đều xuất hiện trong `epics.md`. FR Coverage Map tổng hợp:

- **E1** Auth/RBAC: FR-1/2/3/4/10 — ✅ DONE
- **E2** Connectors: FR-6/7/8 — ✅ DONE
- **E3** KB + Long-Term Memory: FR-9/11/12/13/32/33/34/40, NFR-1b/1c/1d — 🔄 IN-PROGRESS
- **E4** Chat & Agents: FR-14/15/16/17/42, NFR-10 — 🔄 IN-PROGRESS
- **E5** Deliverables: FR-21/22/23 — ✅ DONE
- **E6** Automations: FR-18/19/20/35 — ✅ DONE
- **E7** Multi-surface Clients: FR-25/26/27/28/29 — ✅ DONE
- **E8** Billing/Usage: FR-30/31/41, NFR-7 — ✅ DONE
- **E9** Deep Research: FR-24/37/38/39, NFR-9 — ✅ DONE (theo header) / PARTIAL/GAP ở chi tiết
- **E10** Connector Expansion: FR-6 mở rộng — ✅ DONE
- **E11** Telegram Automation & Bot — ✅ DONE

### FR Coverage Matrix

| FR | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | User Authentication | E1 | ✅ DONE |
| FR-2 | API Access for External Clients | E1 | ✅ DONE |
| FR-3 | Workspace Lifecycle | E1 | ✅ DONE |
| FR-4 | Workspace Invites & Memberships | E1 | ✅ DONE |
| FR-5 | AI File Sorting | — | ❌ REMOVED |
| FR-6 | Built-in Scraper Connectors | E2, E10 | ✅ DONE |
| FR-7 | External OAuth Connectors | E2 | ✅ DONE |
| FR-8 | External MCP Connectors | E2 | ✅ DONE |
| FR-9 | Document Upload, Parse & Index | E3 | 🔄 IN-PROGRESS |
| FR-10 | RBAC với ba system roles | E1 | ✅ DONE |
| FR-11 | Folders & Document Management | E3 | 🔄 IN-PROGRESS |
| FR-12 | Hybrid Search over Knowledge Base | E3 | 🔄 IN-PROGRESS |
| FR-13 | Citation Panel for Knowledge-base Chunks | E3 | ✅ DONE |
| FR-14 | Chat Threads & Messages | E4 | 🔄 IN-PROGRESS |
| FR-15 | Multi-agent Runtime with Tools | E4 | 🔄 IN-PROGRESS |
| FR-16 | Real-time Collaborative Chat | E4 | 🔄 IN-PROGRESS |
| FR-17 | Anonymous Chat with Quota | E4 | 🔄 IN-PROGRESS |
| FR-18 | Automation Action Types | E6 | ✅ DONE |
| FR-19 | Automation Triggers | E6 | ✅ DONE |
| FR-20 | Automation Runs & Retries | E6 | ✅ DONE |
| FR-21 | Report Generation & Export | E5 | ✅ DONE |
| FR-22 | Podcast & Video Presentation | E5 | ✅ DONE |
| FR-23 | Image Generation | E5 | ✅ DONE |
| FR-24 | Deep Open-Web Research via ChainLens Engine | E9.1b | ✅ DONE |
| FR-25 | Web Client (Next.js) | E7 | ✅ DONE |
| FR-26 | Desktop Client (Electron) | E7 | ✅ DONE |
| FR-27 | Browser Extension (Plasmo) | E7 | ✅ DONE |
| FR-28 | Obsidian Plugin | E7 | ✅ DONE |
| FR-29 | MCP Server | E7 | ✅ DONE |
| FR-30 | Token Usage Tracking | E8 | ✅ DONE |
| FR-31 | Credit Wallet & Purchases | E8.3 | ✅ DONE |
| FR-32 | Long-Term Research Memory | E3 (3.8/3.9/3.11) | 🔄 PARTIAL |
| FR-33 | Research Continuity | E4.6 | ✅ DONE |
| FR-34 | Memory Correction | E3/E4 | ✅ DONE |
| FR-35 | Memory-Driven Automations | E6.5 | ✅ DONE |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | E3.10a/b | ✅ RESOLVED |
| FR-37 | Deep-Research Cost Metering | E9.2 | ✅ DONE |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a | ✅ DONE |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | E9.6a/b | ✅ DONE |
| FR-40 | First-Run Value — Research Runs Produce Memory | E3.13 | ✅ DONE |
| FR-41 | Admin UI cho Global LLM Model Configuration | E8.11 | ✅ DONE |
| FR-42 | Chat Response Benchmark | E4.8 | 🔄 IN-PROGRESS |

### Missing / Conflict Coverage

| FR | Issue | Mức độ | Khuyến nghị |
|---|---|---|---|
| **NFR-8** | ✅ **RESOLVED** — `sprint-status.yaml` + `epics.md` + `memory/recall/gate.yaml` đều ghi `baseline_ratified: true` (2026-08-04); PRD cập nhật `[DONE]`. | Resolved | Story 3-9 done; SM-10 ratified. |
| **FR-39** | ✅ **RESOLVED** — `sprint-status.yaml` ghi `9-6a: done`, `9-6b: done`; code verified: migration 184/186, `revalidation_service.py`, `repository.py`, tests tồn tại. | Resolved | Close conflict. |
| **FR-41** | ✅ **RESOLVED** — `sprint-status.yaml` ghi `8-11: done`; code verified: `admin_global_model_connections_routes.py` + schemas tồn tại. | Resolved | Close conflict. |

### Coverage Statistics

- **Total PRD FRs: 42**
- **FRs covered in epics: 41** (FR-5 removed)
- **Coverage percentage: 97.6%** (không tính FR-5 removed)
- **NFRs covered: 10/10**
- **Trạng thái epic:** E1,2,5,6,7,10,11 = DONE; E3,4 = IN-PROGRESS; E8 header DONE nhưng có story GAP; E9 header DONE nhưng có story GAP/PARTIAL.

### Critical Findings

1. **Mâu thuẫn trạng thái FR-39 giữa header Epic 9 và story 9.6a/9.6b** — cần reconcile.
2. **Mâu thuẫn trạng thái FR-41 giữa header Epic 8 và story 8.11** — cần reconcile.
3. **NFR-8 (recall quality eval-gate) là launch gate** — PRD + `epics.md` + `sprint-status.yaml` vừa reconcile về `in-progress`, cần baseline ratified.
4. **NFR-10 (chat regression gate)** mới 2026-08-04, map E4.8 — cần theo dõi.
5. **E3.14 nên chạy trước E3.9** khi chốt SM-10 — đã ghi trong `epics.md` nhưng cần kiểm tra thứ tự thực tế.

## Step 4: UX Alignment

### UX Document Status

- **`_bmad-output/planning-artifacts/archive/ux-audit-improvement-spec-2026-07-27.md`** (14,931 bytes): Draft 2026-07-27. **ĐÃ ARCHIVED vì lỗi thời** — dùng ngôn ngữ "Crypto-Native Report Layout", "Token Hero", "Nansen/CertiK/Dune/TokenInsight", "Token PAYG", "plan free@nowing.ai"; tham chiếu PRD 2026-05-01; không khớp PRD Nowing hiện tại (research memory, documents, citations, workspace). File đã được chuyển sang `archive/`.
- **`_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md`** (7,417 bytes): UX contract cho async deep research, **khớp** PRD NFR-9 State A, FR-38, `AD-17`, `AD-18`.

### UX ↔ PRD Alignment

| PRD yêu cầu | UX coverage | Đánh giá |
|---|---|---|
| UJ-1..7 (Key User Journeys) | Không có UX spec đầy đủ cho từng journey | ⚠️ Implied / partial |
| FR-13 Citation Panel | Spec cũ (2026-04-13) bị thay thế bởi audit draft, không có spec mới rõ ràng | ⚠️ Gap |
| NFR-9 State A async deep-research | `ux-contract-async-deep-research.md` định nghĩa 10 trạng thái UI (S1-S10) | ✅ Aligned |
| FR-38 Degradation | Contract yêu cầu S9 phân biệt nguồn kết quả hybrid search | ✅ Aligned |
| FR-25 Web Client | Audit chỉ ra 4 tầng bị bỏ trống, nhưng tài liệu lỗi thời | ⚠️ Needs reconciliation |
| NFR-7 / FR-31 Usage/Credit Dashboard | UX contract ghi hoãn vì chờ `9-2` costDollars thật; `8-3` done nhưng chưa có UX spec | ⚠️ Deferred with trigger |
| FR-40 First-Run Value | PRD gap — UI memory browser/research timeline hoãn đến sau `3-13`/`3-14` | ⚠️ Deferred |
| FR-41 Admin UI Global LLM Model Config | Không có UX spec | ⚠️ Gap |
| FR-42 Chat Response Benchmark | Không có UX spec | ⚠️ Gap |

### UX ↔ Architecture Alignment

- **Async deep-research progress:** `AD-17` (async door sẵn có), `run_event_bus` SSE, ring buffer 500 event, `runs` không vào Zero publication — UX contract tôn trọng đúng.
- **Multi-replica warning:** UX contract ghi rõ progress UI không được bật trên multi-replica trước khi Redis-backed bus xong (`9-3`).
- **Degradation labeling:** `AD-18` (bounded memory) + FR-38 yêu cầu S9 nói rõ nguồn hybrid search — cần architecture support.
- **Missing UX for local-first/offline:** PRD §1.1 self-host/cloud split cần UI trạng thái; `ux-audit-improvement-spec` đề cập `SyncStatusChip` nhưng không có spec implementation.

### Warnings

1. **✅ Stale UX audit document**: đã archived sang `_bmad-output/planning-artifacts/archive/ux-audit-improvement-spec-2026-07-27.md`.
2. **⚠️ Sparse UX spec**: chỉ có 1 UX contract thực sự dùng được (`async deep research`). Nhiều story UI (FR-42 chat regression, first-run memory browser) chưa có UX spec.
3. **⚠️ UX deferred items cần trigger rõ ràng**: UI memory browser/research timeline hoãn đến sau `3-13`/`3-14`; admin console pattern đã được `8.11` cover.

## Step 5: Epic Quality Review

### Epic User Value Focus

| Epic | Title | User-centric? | Đánh giá |
|---|---|---|---|
| E1 | Identity, Auth & Workspace RBAC | ✅ | User value rõ: đăng ký/đăng nhập, workspace, RBAC. |
| E2 | Connectors | ✅ | User value: kết nối nguồn dữ liệu. |
| E3 | Knowledge Base + Long-Term Memory | ✅ | User value: lưu trữ, truy cứu, memory. |
| E4 | Chat & Agents | ✅ | User value: chat đa agent. |
| E5 | Deliverables | ✅ | User value: báo cáo, podcast, video, ảnh. |
| E6 | Automations | ✅ | User value: automation schedule/event. |
| E7 | Multi-surface Clients | ✅ | User value: web/desktop/extension/Obsidian/MCP. |
| E8 | Người dùng thấy và kiểm soát được chi phí | ✅ | User value: token, credit, usage. |
| E9 | Deep Research đáng tin cậy | ✅ | User value: deep research không vỡ, không treo, tính phí đúng. |
| E10 | Connector & Scraper Expansion | ✅ | User value: thêm nguồn scraper BĐS VN. |
| E11 | Telegram Automation & Bot | ✅ | User value: notification, write-back, bot. |

### Story Quality & Sizing

#### 🔴 Critical / Major Issues — UPDATED

1. **✅ Epic 9 / 9.6a/9.6b resolved**
   - `sprint-status.yaml`: `9-6a: done`, `9-6b: done`.
   - Code verified: migrations 184/186, `app/services/memory/revalidation_service.py`, `app/services/memory/repository.py`, tests tồn tại.
   - Epic 9 header consistent.

2. **✅ Epic 8 / 8.11 resolved**
   - `sprint-status.yaml`: `8-11: done`.
   - Code verified: `app/routes/admin_global_model_connections_routes.py`, `app/schemas/admin_global_model_connections.py`.
   - Epic 8 header consistent.

3. **✅ NFR-8 / Story 3.9 resolved**
   - `sprint-status.yaml`: `3-9: done`.
   - `memory/recall/gate.yaml`: `baseline_ratified: true` (2026-08-04).
   - PRD + `epics.md` updated.

#### 🟠 Major Issues

4. **Story 3.14 quá lớn / epic-sized**
   - AC bao gồm: bounded top-k injection, 8.000 chars limit, p95 latency, error counter, auto-extract not on critical path, expose RRF score.
   - Mặc dù user-centric, nhưng có thể cần tách thành nhiều story (injection bounded, recall score, perf assert).

5. **Story 4.8 Chat Response Benchmark in-progress với nhiều sub-story `ready-for-dev`**
   - 4.8a/4.8b done; 4.8c/4.8d/4.8e ready-for-dev; CI/deploy gate chưa có.
   - NFR-10 yêu cầu mọi deploy production phải qua gate — cần 4.8e done trước khi áp dụng.

6. **Forward dependency 9.6b → 9.6a**
   - Chấp nhận được vì trong cùng epic, nhưng 9.6a vẫn `[GAP]` nên 9.6b bị block.

7. **Cross-epic business gating**
   - `9.1a` phải done trước public repo (business rule).
   - `9.2` và `8.7` phải có số thật trước khi chốt pricing.
   - `3.14` nên chạy trước khi chốt SM-10 của `3.9`.
   - Các ràng buộc này hợp lý nhưng cần theo dõi chặt.

#### 🟢 Good Examples

- **Story 3.13** — user-centric (first-run value), rõ ràng, có M1 metric ≤15 phút.
- **Story 9.1a** — rõ ràng, P0, user value self-host.
- **Story 8.11** — ACs chi tiết (superuser, global model config, test connection) — dù status GAP.

### Best Practices Compliance Checklist

| Epic | User value | Independence | Story sizing | No forward dep | DB when needed | Clear AC | Traceability |
|---|---|---|---|---|---|---|---|
| E1 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E2 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E3 | ✅ | ✅ | ⚠️ 3.14 lớn | ✅ | ✅ | ✅ | ✅ |
| E4 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E5 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E6 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E7 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E8 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E9 | ✅ | ✅ | ✅ | ⚠️ 9.6b→9.6a | ✅ | ✅ | ✅ |
| E10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| E11 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Quality Findings Summary

- **Status inconsistencies resolved**: Epic 8/9 headers và stories đã khớp sau verify code.
- **NFR-8 / 3.9 status drift resolved** — baseline ratified 2026-08-04.
- **Story 3.14** may need splitting before implementation.
- **No pure technical epics found** — all epics deliver user value.
- **Dependencies are mostly within-epic and logical**.
- **Epic 4 remains IN-PROGRESS** vì 4.8f/4.8e chưa done.

## Step 6: Final Assessment

### Overall Readiness Status

**🟡 CONDITIONALLY READY — REMAINING ITEM: NFR-10 / Story 4.8**

Dự án Nowing đã **reconcile hầu hết các mâu thuẫn trạng thái** (3-9, 8-11, 9-6a/b) và **archived tài liệu UX lỗi thời**. Chỉ còn **NFR-10 / Story 4.8 chat regression gate** đang `in-progress` (4.8f operational metrics done; multi-turn + stress + ChainLens latency remaining). Có thể tiến sang `bmad-sprint-planning` cho các epic done, nhưng cần theo dõi E4 cho đến khi 4.8e CI/deploy gate hoàn thiện.

### Resolved Critical Issues

1. **✅ NFR-8 / Story 3.9 (recall quality eval-gate)** — `baseline_ratified: true` 2026-08-04; PRD/epics/sprint-status reconciled.
2. **✅ Epic 8 / Story 8.11 (FR-41 Admin UI Global LLM Model Config)** — code verified; status reconciled.
3. **✅ Epic 9 / Story 9.6a/9.6b (FR-39 Memory Provenance & Re-Validation)** — code verified; status reconciled.
4. **✅ Stale UX audit document** — archived to `_bmad-output/planning-artifacts/archive/`.

### Remaining Issue Requiring Action

5. **NFR-10 / Story 4.8 chat regression gate chưa hoàn thiện**
   - 4.8a/4.8b/4.8c done; 4.8d/4.8e/4.8g `ready-for-dev`; 4.8f `in-progress`.
   - `chat/regression/gate.yaml` chưa ratified (`baseline_ratified: false`).
   - **Hành động:** hoàn thiện 4.8f (multi-turn/stress/ChainLens latency) và 4.8e (CI/deploy gate) trước khi enforce NFR-10.

### Recommended Next Steps

1. **✅ Status reconciliation** — đã xong cho 3.9, 8.11, 9.6a/b.
2. **✅ UX audit document** — đã archived.
3. **Hoàn thiện Story 4.8f** (multi-turn/stress/ChainLens latency benchmark stability).
4. **Hoàn thiện Story 4.8e** (CI / deploy gate) để NFR-10 có thể enforce.
5. **Ratify `chat/regression/gate.yaml`** sau khi có baseline đo.
6. **Cân nhắc `bmad-sprint-planning`** cho các epic đã done, với E4 theo dõi riêng.

### Final Note

This assessment initially identified **5 critical issues** across **3 categories** (status reconciliation, launch gates, UX/artifact hygiene). **4 of 5 issues have been resolved**; **1 remains** (NFR-10 / Story 4.8 chat regression gate). Address the remaining issue before full launch, or proceed with `bmad-sprint-planning` for done epics while tracking E4.

**Assessor:** Devin Agent (bmad-check-implementation-readiness skill)
**Report generated:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-05.md`
