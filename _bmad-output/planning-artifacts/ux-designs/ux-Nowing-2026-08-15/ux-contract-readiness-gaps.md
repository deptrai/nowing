# UX Contract — Readiness Gaps (Agent Registry, Vertical Client, Benchmark, Pricing, CRM, Memory Bounds)

**Ngày:** 2026-08-20
**Phạm vi:** Bổ sung UX contracts cho các requirement còn thiếu trong canonical UX `ux-Nowing-2026-08-15`.
**Bám vào:** FR-56 · FR-57 · NFR-MULTI-1 · FR-42 · NFR-10 · FR-69 · FR-67 · NFR-1b
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI bắt buộc.

---

## 1. Agent Registry (FR-57)

### Bài toán
Platform admin cần quản lý agent cho từng vertical client (`agent_configs` table).

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| AR-1 | **Admin — Global Model & Agent Console** — danh sách `AgentConfig` với `client_id`, `name`, `enabled_tools`, `is_active` | ✅ |
| AR-2 | **Create/Edit Agent** — form nhập `system_instructions`, tool allowlist/blocklist, model, `citations_enabled` | ✅ |
| AR-3 | **Agent Test Sandbox** — chạy 1 turn với agent để xem system prompt injection trước khi publish | ✅ |

---

## 2. Vertical Client Tenancy (FR-56, NFR-MULTI-1)

### Bài toán
Public API client phải nhìn thấy boundary của `client_id`; UI admin/workspace phải hiển thị tenant label.

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| VT-1 | **Workspace Switcher / Client Badge** — hiển thị `client_id` / client name trong header khi đang ở chế độ vertical client | ✅ |
| VT-2 | **Tenant Isolation Indicator** — trên public chat UI, hiển thị khóa / "Dữ liệu chỉ trong client X" | ✅ |
| VT-3 | **PAT Scope Viewer** — user thấy `client_id` và `agent_id` scope trong màn hình API key / PAT management | ✅ |

---

## 3. Chat Benchmark / Regression Gate (FR-42, NFR-10)

### Bài toán
Đội QA/PM cần xem trạng thái regression gate sau mỗi deploy.

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| BM-1 | **Benchmark Dashboard** — bảng tổng hợp `chat/regression`, `chat/quality`, drift so với baseline | ✅ |
| BM-2 | **Drift Alert Card** — khi metric vượt ngưỡng, hiển thị cảnh báo trước khi mở traffic | ✅ |
| BM-3 | **Run Detail View** — latency, TTFB, tokens, cost, citation count, finish status per query | ✅ |

---

## 4. Outcome-Based Pricing (FR-69)

### Bài toán
Bán theo verified lead / meeting booked thay vì seat.

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| OP-1 | **Pricing Plan Selector** — toggle giữa "per seat" và "per outcome" trong billing settings | ✅ |
| OP-2 | **Verified Lead Ledger** — danh sách lead/outcome đã verify và cost-per-meeting | ✅ |
| OP-3 | **Credit Refund / Auto-Refund Dialog** — khi lead không verify, hiển thị refund flow (gắn E26.6) | ✅ |

---

## 5. CRM Integration & Write-Back (FR-67)

### Bài toán
User cần thấy trạng thái sync với CRM/sheet và kết quả write-back.

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| CRM-1 | **Connector Config — CRM** — chọn HubSpot / Salesforce / Lark Base / Google Sheets, map field | ✅ |
| CRM-2 | **Sync Status Pill** — trên lead row, hiển thị "Đã ghi Lark Base" / "Lỗi sync" / "Đang chờ xác nhận" | ✅ |
| CRM-3 | **Write-Back Log** — drawer liệt kê các lần sync, trạng thái, thời gian, lỗi nếu có | ✅ |

---

## 6. Bounded Memory Injection (NFR-1b)

### Bài toán
User cần biết khi memory injection bị bound/truncate để không ngạc nhiên khi context bị cắt.

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| MB-1 | **Context Bound Tooltip** — hiển thị số token / ký tự đang inject, giới hạn 8.000 chars, cảnh báo khi gần vượt | ✅ |
| MB-2 | **Injection Shimmer / Latency Budget** — trong quá trình recall, hiển thị "Đang tổng hợp trí nhớ (≤ N ms)" | ✅ |
| MB-3 | **Truncation Notice** — khi 1 memory bị cắt, hiển thị "…" với hover xem toàn bộ hoặc mở panel | ✅ |

---

## 7. PRFAQ 2026-08-21 UX Contracts

### 7.1 Memory Browser / Research Timeline (UX-DR-PRFAQ-1)

**Bài toán:** Analyst cần duyệt workspace memory theo research thread, source type, confidence và time, với click-to-source citation.

| # | Trạng thái UI bắt buộc |
|---|---|
| MB-1 | **Research Timeline Panel** — danh sách memory theo thread, sort theo `created_at`, group theo `source_type` / `research_thread_id`. |
| MB-2 | **Source Type + Confidence Filter** — chips cho `SCRAPER_RUN`, `CHAT_TURN`, `DOCUMENT`, `CONNECTOR`; slider confidence ≥ threshold. |
| MB-3 | **Click-to-Source Citation** — click citation badge mở drawer/source panel hiển thị `citation = "run_<uuid>"` hoặc chunk/document origin. |
| MB-4 | **Version History Peek** — hover/long-press memory hiển thị số version và timestamp correction gần nhất. |

### 7.2 Self-Host Onboarding Flow (UX-DR-PRFAQ-2)

**Bài toán:** Dev self-host cần hoàn tất onboarding trong <10 phút.

| # | Trạng thái UI bắt buộc |
|---|---|
| SH-1 | **Landing Hero — Self-Host CTA** — prominent "Self-host in 10 min" button dẫn đến README + Docker Compose. |
| SH-2 | **Install Wizard Steps** — 1) `docker compose up` 2) Chọn local LLM/embedding (`llama.cpp`/`ollama` mặc định) hoặc nhập API key 3) Tạo first workspace 4) Connect MCP client. |
| SH-3 | **First-Run Aha Panel** — sau `docker compose up`, hiển thị quick prompt "Tìm 1 tin bất động sản và lưu vào memory" với progress indicator. |
| SH-4 | **Offline vs Remote LLM Toggle** — rõ ràng local mode (free, slow) vs cloud API key (fast, metered). |

### 7.3 Memory Correction / Version History (UX-DR-PRFAQ-3)

**Bài toán:** User/agent cần flag/update memory sai và xem version history + affected relations.

| # | Trạng thái UI bắt buộc |
|---|---|
| MC-1 | **Flag Memory Button** — trên memory card, nút "Báo sai / Correct" mở form với lý do (`outdated`, `hallucination`, `conflict`, `other`). |
| MC-2 | **Correction Form** — input `corrected_content`, chọn propagate scope (chỉ memory này / cả thread / workspace). MVP: chỉ memory này. |
| MC-3 | **Version History Drawer** — list `MemoryVersion` với `previous_content`, `corrected_content`, `corrected_by`, timestamp. |
| MC-4 | **Affected Relations View** — hiển thị relations bị ảnh hưởng (post-MVP: auto propagate). |

### 7.4 Cost Control / Auto-Extract Budget Dashboard (UX-DR-PRFAQ-4)

**Bài toán:** Admin/workspace owner cần xem và điều chỉnh chi phí auto-extract, embedding, recall per turn.

| # | Trạng thái UI bắt buộc |
|---|---|
| CC-1 | **Auto-Extract Budget Card** — input max items/turn, max spend/turn, toggle `memory_auto_extract_enabled`, rate-limit interval. |
| CC-2 | **Cost Breakdown Per Turn** — bar/stack chart hoặc table hiển thị `memory_create`, `embedding`, `recall` cost micros cho mỗi chat turn. |
| CC-3 | **Wallet + Reserved Balance** — hiển thị `credit_micros_balance`, `credit_micros_reserved`, và projected cost trước mỗi lệnh scrape/enrich. |
| CC-4 | **Budget Alert Toast** — khi một turn vượt ngưỡng, hiển thị cảnh báo trước khi tiếp tục hoặc auto-pause auto-extract. |

## 8. Truy vết

| Contract | Chặn |
|---|---|
| Agent Registry | E18.3 / FR-57 |
| Vertical Client Tenancy | E18 / FR-56 / NFR-MULTI-1 |
| Chat Benchmark | E4.8 / FR-42 / NFR-10 |
| Outcome-Based Pricing | E21.7 / FR-69 |
| CRM Integration | E21.5 / FR-67 |
| Bounded Memory Injection | E3.14 / E3.17 / NFR-1b |
| Memory Browser / Research Timeline | Epic 29.5 / FR-104 / UX-DR-PRFAQ-1+6 |
| Self-Host Onboarding Flow | E28.4 / FR-98 / UX-DR-PRFAQ-2 |
| Memory Correction / Version History | E3 (post-MVP) / FR-34 / UX-DR-PRFAQ-3 |
| Cost Control / Auto-Extract Budget | E8.14 / FR-30 / UX-DR-PRFAQ-4 |
