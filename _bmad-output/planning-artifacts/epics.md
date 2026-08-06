---
title: Nowing - Epic Breakdown
description: ''
createdAt: '2026-07-28T12:47:48.297Z'
updatedAt: '2026-08-06T00:00:00.000Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-epics-md
---

---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/prfaq-Nowing-distillate.md (context)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22.md (epic taxonomy)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-22-vision-pivot.md (epic taxonomy)"
  - "_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md (Epic 9 + FR-24 re-bind)"
  - "_bmad-output/planning-artifacts/prfaq-hr-vertical-vietnam-2026-08-05.md (context)"
  - "_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md (context)"
  - "_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md (context)"
  - "_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md (context)"
  - "_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md (context)"
---

# Nowing - Epic Breakdown

## Overview

Phân rã epic/story cho Nowing từ PRD (reality-corrected 2026-07-24), Architecture spine, và 2 sprint-change-proposal (nguồn taxonomy epic).

> **Bối cảnh (đã verify code):** Nowing là **brownfield** — taxonomy **Epic 1–8 đã tồn tại và phần lớn ĐÃ IMPLEMENT** (migration tới 179; memory layer đã build: mig 177 tables/enums/confidence/HNSW+GIN/RBAC, 179 auto-extract, endpoints `memories_routes.py`, 4 MCP tools). Tài liệu này **không tạo epic mới đè lên epic đã xong**, mà: (a) ghi lại taxonomy thật với trạng thái `[DONE]`/`[PARTIAL]`/`[GAP]`, (b) thêm story **mới** chỉ cho phần còn thiếu (recall eval-gate, data-loss recovery, dedupe tuning, cost guardrails, docs sync).
>
> **Epic 9 (mới 2026-07-25)** là **ngoại lệ có chủ đích** của nguyên tắc trên: nó là epic *mới thật*, không phải retag. Lý do: ChainLens được thăng từ "một connector trong Epic 2" lên **external dependency hạng nhất** (`AD-15`), và ba việc trong đó (contract guard, cost metering, degradation) là **lỗi đang chạy trong production path**, không phải tính năng chưa build. Xem SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`.

## Requirements Inventory

### Functional Requirements
`[DONE]` FR-1 Auth · FR-2 API/PAT · FR-3 Workspace lifecycle · FR-4 Invites/memberships · FR-10 RBAC 3 roles · FR-6 Scrapers · FR-7 OAuth connectors · FR-8 MCP connectors · FR-9 Doc upload/index · FR-11 Folders · FR-12 Hybrid search · FR-13 Citation panel · FR-14 Chat threads · FR-15 Multi-agent runtime (+auto-extract) · FR-16 Realtime chat · FR-17 Anonymous chat · **FR-42 Chat Response Benchmark** *(mới 2026-08-04 — telemetry, regression, quality, production query sampler; stories 4.8a–4.8g)* · FR-21 Reports · FR-22 Podcast/video · FR-23 Image · FR-19 Automation triggers · FR-20 Automation runs · FR-25 Web · FR-26 Desktop · FR-27 Extension · FR-28 Obsidian · FR-29 MCP server · FR-30 Token tracking · **FR-32 Memory storage/retrieval** *(dedupe primitive + recall quality gate done; baseline ratified 2026-08-04)* · FR-33 Research continuity · FR-34 Memory correction · **FR-18 Automation actions** *(cải chính 2026-07-25: registry có `agent_task` + `continue_research` + `write_back_jira/linear/notion/slack`)* · **FR-31 Credit wallet** *(dashboard `8-3` = done)* · **FR-35 Memory-driven automations** *(cải chính 2026-07-25: trigger `memory_change` + action `continue_research` + `AutomationRun.research_thread_id` đều có)* · **FR-24 Deep-research via ChainLens engine** *(E9.1b contract regression guard done; mode default handled)* · **FR-38 Research degradation & self-host independence** *(E9.1a done)* · **FR-39 Memory→scraper-run provenance & re-validation** *(E9.6 done)* · **FR-40 First-run value: research run sinh memory** *(E3.13 done)* · **FR-41 Admin UI cho Global LLM Model Configuration** *(E8.11 done)*.
`[DONE]` **FR-37 Deep-research cost metering** (`costDollars` parser done; fallback ~$0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671) → **E9.2 P0**.
`[PROPOSED]` **FR-43 VietnamWorks scraper** → **E12.1 P0** (public API, no auth; spike passed; ToS gate).
`[PROPOSED]` **FR-44 TopCV scraper** → **E12.2 P0** (HTML + anti-bot; Cloudflare challenge; POC required).
`[PROPOSED]` **FR-45 ITviec scraper** → **E12.3 P0** (HTML server-rendered; salary hidden).
`[PROPOSED]` **FR-46 `vn_jobs.aggregate`** → **E12.4 P0** (cross-source normalization, dedupe, confidence, conflict detection).
`[PROPOSED]` **FR-47 PII redaction for job data** → **E12.5 P0** (mask/drop phone, email, names before memory).

`[DONE — NFR]` **NFR-1b/1c/1d Memory latency & injection bound** *(E3.14 done, AD-18)*.
`[RESOLVED]` FR-36 Legacy memory data-loss (2026-07-25 — không mất dữ liệu; 178 chưa apply prod, `memory_md` rỗng, snapshot đã tạo; guard + backfill + 5 test qua `3-10a`/`3-10b`).
`[REMOVED]` FR-5 AI File Sorting.

> **⚠️ Re-bind 2026-07-25 (SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`, ✅ ADOPTED):** **FR-24 rời Epic 2 (Connectors) sang Epic 9.** ChainLens không phải connector/scraper ngang hàng Reddit — nó là external dependency hạng nhất (`AD-15`). FR-37, FR-38, NFR-9 là mới. Story `2-4` giữ `done` làm lịch sử (nó đã ship tool thật), không revert.

### NonFunctional Requirements
`[DONE]` NFR-2 Security · NFR-3 Observability · NFR-4 Reliability · NFR-5 Multi-tenancy isolation · **NFR-6 Citation jump-to-source** *(cải chính 2026-07-25: `editorPanelAtom` CÓ `chunkId`; `AD-DEFER-1` đã đóng)* · **NFR-7 Usage dashboard** *(story `8-3` = done)* · **NFR-8 Recall quality eval-gate** *(story `3-9` = done; baseline ratified 2026-08-04)* · **NFR-9 Deep-research latency & availability budget** *(story `9-3` = done; State A async deliverable default; State B sync chat-mode gated on measured p95 `balanced` ≤30s)* · **NFR-10 Chat Response Regression Gate** *(mới 2026-08-04 — stories 4.8b/4.8e/4.8f/4.8g/4.8h done; `chat/regression` baseline ratification pending measured run)*.  **NFR-11 Scraping compliance & anti-bot resilience (Vietnam job market)** *(mới 2026-08-05 — ToS review, legal counsel, anti-bot POC, PII pipeline)*. `[PARTIAL]` NFR-1 Performance (bounds mơ hồ — **và không có epic nào nhận**, xem readiness C-1).

### Additional Requirements
Starter template: **KHÔNG — brownfield**. Component mới thật sự duy nhất trong Structural Seed: `nowing_evals/` (đã tồn tại, cần thêm memory suite).
- **AR-1** Thêm **suite memory-recall** vào `nowing_evals` (**DONE**: suite + dataset + oracle + metrics + gate đã có; 168 tests passed; baseline ratified 2026-08-04).
- **AR-2** Backfill/recovery markdown→`Memory` (mig 178 drop `memory_md`/`shared_memory_md` KHÔNG backfill; `downgrade` chỉ tạo cột rỗng → data-loss có thể đã xảy ra).
- **AR-3** Dedupe/confidence *validation & tuning* (primitive đã có: `repository.py` cosine<0.08 + `update_on_duplicate`, đã wire vào auto-extract) — bench + tune qua eval.
- **AR-4** Retention + right-to-delete cho `Memory`/versions/relations + scrape data (doc retention đã có mig 176; memory chưa).
- **AR-5** Observability + cost/turn quantification (spans extraction/recall + aggregate).
- **AR-6** Auto-extract cost control — **DONE**: kill-switch/global + per-workspace flags, wallet pre-check, spend/budget cap, rate-limit thời gian; 59 tests passed.
- **AR-7** Legacy memory bridge parity tests (`/…/memory`, `/users/me/memory` backed by `Memory`).
- **AR-8** MCP tool contract/selfcheck CI (`EXPECTED_TOOLS`, e2e smoke), toggle-aware.
- **AR-9** Memory security: verify `memory:*` RBAC enforced + workspace/user isolation + audit-log writes (hiện chỉ `logger.warning`).
- **AR-10** Docs/README/epics sync sang research-memory (Fumadocs) + CI docs-drift.

**Requirements signals:** RS-1 auto-extract budget (item-cap + spend-cap + wallet pre-check + rate-limit done) · RS-2 recall top_k≤5 (verify) · RS-3 beachhead agent-builder→team · RS-4 "MCP trước UI sau"/"semantic facts first" · RS-5 docs-sync bắt buộc · RS-6 right-to-delete + self-host/cloud split · RS-7 eval-gated launch + chốt số SM · RS-8 data export · RS-9 "project memory"=`ResearchThread`? · RS-10 cost/turn beta trước pricing.

### UX Design Requirements
UX contracts tồn tại trong `ux-designs/ux-Nowing-2026-07-22/` dưới dạng behavior contract (không layout/màu):
- `ux-contract-async-deep-research.md` — chặn story 9.3 (NFR-9 State A)
- `ux-contract-admin-global-model-config.md` — chặn story 8.11 (FR-41)
- `ux-contract-chat-benchmark.md` — chặn stories 4.8a–4.8g (FR-42, NFR-10)
- `ux-contract-usage-dashboard.md` — chặn story 8.12, bổ sung story 8.3 (FR-31, NFR-7)
- `ux-contract-sync-offline-indicator.md` — chặn stories 9.1a, 9.3 (FR-38, NFR-9)
- `ux-contract-first-run-onboarding.md` — chặn story 3.13 (FR-40)

Các story có UI vẫn cần UX spec riêng trước khi build UI chi tiết.

### FR Coverage Map
- FR-1/2/3/4/10 → **E1** [DONE] · FR-6/7/8 → **E2** [DONE] · **FR-6 mở rộng → E10.1** [DONE] (batdongsan scraper) · FR-9/11/12/13 → **E3** [DONE] · **FR-14/15/16/17/42 → E4** [DONE] (4.8a–4.8g chat benchmark & regression gate) · FR-21/22/23 → **E5** [DONE] · FR-19/20 → **E6** [DONE] · FR-25/26/27/28/29 → **E7** [DONE] · FR-30 → **E8** [DONE] · **FR-41 → E8.11** [DONE]
- **FR-6/7/8 + FR-8.1 → E2** [DONE] · FR-8.1 = **E2.10** Exa MCP Search Connector `[DONE 2026-08-05]`
- **FR-24/37/38/39 + NFR-9 → E9** (mới 2026-07-25; tách story theo readiness Q-3/Q-4): FR-38 → **E9.1a** [DONE, P0] · FR-24 → **E9.1b** [DONE, P0] · FR-37 → **E9.2** [DONE, P0, parser `done.usage.costDollars` + `done.usage.estimated` + `done.resolvedMode` + canonical golden fixtures + fallback 60k micros; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671] · NFR-9 → **E9.3** [DONE] · OQ-6/AR-10 (phần Nowing↔engine) → **E9.4** [DONE, P1] · D5-Phase2 → **E9.5** [deferred] · **FR-39 → E9.6** (provenance + re-validation) [DONE]
- FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11) · FR-33 → E4 (4.6 done) · FR-34 → E3/E4 (done)
- FR-36 → **E3.10** [RESOLVED 2026-07-25] · FR-18 → **E6.4** [DONE] · FR-31/NFR-7 → **E8.3** [DONE] · FR-35 → **E6.5** [DONE — cải chính 2026-07-25]
- NFR-8 → **E3.9** [DONE — baseline ratified 2026-08-04] · NFR-6 → **E3.6** [DONE] · NFR-10 → **E4** [DONE — 4.8b/4.8e/4.8f/4.8g] · OQ-3/AR-4 → **E3.7** [PARTIAL] · OQ-4 → **E2.5** [DONE] · **OQ-5 → E6.4 [DONE]** *(2026-07-25: `6-4` = done; 4 action type `write_back_notion/slack/linear/jira` đã có ⇒ câu hỏi "action type riêng vs `agent_task`" **code đã trả lời: action type riêng**)* · OQ-6/AR-10 → **E8.10 + E9.4** [DONE] · **OQ-7 (5 câu hỏi từ ChainLens `42-3`, ADOPTED 2026-08-05) → E9.1b/E9.2/E9.3** [DONE] · FR-5 → [REMOVED]
- **Mới 2026-07-25 (readiness Nhóm 3 — trước đây KHÔNG có FR lẫn epic):** **FR-40** (first-run value: research run sinh memory; M1; brief §9 H-4) → **E3.13** [DONE, HIGH] · **NFR-1b/1c/1d** (bound cho memory injection + recall + auto-extract; `AD-18`) → **E3.14** [DONE, đi kèm E3.13]
  - ⚠️ **NFR-1 trước đây KHÔNG map sang epic nào** (readiness C-1) và không phủ memory (P-5). Nay: **NFR-1a** (CRUD/scraper) = nền tảng, không cần story riêng · **NFR-1b/1c/1d → E3.14**.
  - ⚠️ **Ràng buộc thứ tự mới:** **E3.14 nên chạy trước khi chốt số SM-10 của E3.9** (`AD-18` rule 6) — baseline recall quality đo trên lượng inject phụ thuộc N thì không tái lập được.
- AR-1/AR-3/AR-8 → E3.9/3.11 · AR-2/AR-7 → E3.10 · AR-9 → E3.12 · AR-5 → E8.9 · AR-6 → E8.8/8.7 · RS-5→E8.10 · RS-6/8→E3.7 · RS-7→E3.9 · RS-10→E8.9
- **NG-1/NG-2/NG-3 (§2.4 PRD Non-Goals)** → không map sang epic nào; là ràng buộc chặn phạm vi. Owned index = `AD-DEFER-7`.
- **Defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default toggle) → backlog.
- **OQ-8 HR/Recruitment Vertical in Vietnam** → **E12 P0** (ToS, legal classification, anti-bot, salary hidden, willingness-to-pay, PII).
- **SM-12 HR pilot metrics** → **E12 P0** (workspace active, aggregate queries, listings indexed, dedupe, confidence, PII coverage).
- **AR-11 HR anti-bot validation** → **E12.2 P0** (TopCV Cloudflare bypass/residential proxy feasibility).

## Epic List

> **⚠️ RECONCILED 2026-07-24 với `implementation-artifacts/sprint-status.yaml` (nguồn chân lý tiến độ):** một sprint đã chạy — **E1,2,5,7 = done; E3/E4/E6/E8 gần done**. Nhiều story dưới đây gắn `[GAP]` ở phiên planning này THỰC RA ĐÃ DONE (2.5, 3.6, 3.7, 6.4, 8.3, 3.11 dedupe, 3.12 security, 8.4a kill-switch, 8.5 obs) — đã retag `[DONE]`.
> **Việc CÒN LẠI thật sự:**
> - Từ sprint cũ: ~~4-6~~ research-continuity (done) · ~~6-5~~ memory-driven-automations (done) — cả hai đã verify code.
> - **Đã đóng 2026-08-01:** 3.9 memory recall eval-gate (baseline ratified 2026-08-04) · 3.10 legacy data-loss recovery · 8.7 auto-extract spend/budget cap · 8.8 kill-switch · 8.9 observability.
> **✅ Cập nhật 2026-08-01 (ops):** memory (mig 177–179) **CHƯA lên production** (prod=`alembic 174`; 175–179 ở branch `develop`). ⇒ Các gap memory là **cổng TRƯỚC KHI merge memory lên prod**, KHÔNG phải sự cố prod đang chạy. 3.10a **done** (không mất dữ liệu) · 3.10b **done** (guard + backfill command + 5 test; deploy-order `mig177→backfill→mig178`) ⇒ **FR-36 RESOLVED**. **3.9** eval-gate (**`done`** — baseline ratified 2026-08-04) · **8.7** spend-cap (**`done`** — 59 tests passed; cổng trước khi bật auto-extract trên prod). *(auto-extract KHÔNG đang bleed trên prod vì 179 chưa deploy.)*
>
> **🆕 2026-07-25 — Epic 9 *(Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng)*:** SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED). **FR-24 rời E2 → E9.** Các việc P0/P1, đều là lỗi thương mại/kiến trúc đang chạy trong production path chứ không phải tính năng mới: **9.1a** degradation + self-host độc lập (P0, **chặn public repo**) · **9.1b** contract regression guard (P0, không chặn) · **9.2** cost metering thật — **DONE**: parser `done.usage.costDollars` + fallback 60k micros (~$0.06), cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671 (P0) · **9.3** latency budget State A/B + mode default `quality`→`balanced` (P1) · **9.4** docs (P1) · **9.6a/9.6b** provenance + re-validate. **Gate:** pricing có thể bắt đầu định hình dựa trên số thật, vẫn giữ margin 1.5–2.5× cho full-pipeline cost aggregation.

### Epic 1: Identity, Auth & Workspace RBAC — ✅ DONE
Đăng ký/đăng nhập/OAuth/PAT + workspace RBAC Owner/Editor/Viewer. **FRs:** FR-1,2,3,4,10.

### Epic 2: Connectors — ✅ DONE
Built-in scrapers + OAuth connectors + external MCP connectors; connectors là memory ingestion source. **FRs:** FR-6,7,8. **Open:** 2.6 Indeed `[ready-for-dev]`, 2.7 Walmart `[ready-for-dev]`, 2.8 Amazon EU `[ready-for-dev]`, 2.9 input validation `[DONE]`.
> **⚠️ 2026-07-25: FR-24 (ChainLens) đã rời Epic 2 → Epic 9.** ChainLens không phải connector. Story `2-4-chainlens-research-mcp-tool` giữ `done` làm lịch sử — nó đã ship tool thật; việc còn lại thuộc Epic 9.

### Epic 3: Knowledge Base + Long-Term Memory — ✅ DONE
KB + long-term research memory. **FRs:** FR-9,11,12,13,32,33,34, **FR-40** *(mới)*, **NFR-1b/1c/1d** *(mới)*. **Open:** 3.15 run citations `[ready-for-dev]`, 3.16 OKF export `[ready-for-dev]`.
> **🆕 2026-07-25 (readiness Nhóm 3):** hai story mới, cả hai đều là **gap trước đây không có FR lẫn epic**. **3.13** — `MemoryExtractionService` chỉ có `extract_from_turn` và workspace mới không seed gì ⇒ `nowing_recall` session đầu **rỗng theo cấu trúc**, **M1 (first-run value ≤15 phút) không tồn tại**. **3.14** — `MemoryInjectionMiddleware` **chặn mọi lượt chat** với `SELECT` không LIMIT, bỏ qua cả HNSW + GIN index đã có sẵn ⇒ chi phí mỗi lượt tăng tuyến tính theo mức dùng. **3.14 nên chạy trước khi chốt số SM-10 của 3.9.**

### Epic 4: Chat & Agents — ✅ DONE
Multi-agent runtime + memory tools + research continuity. **FRs:** FR-14,15,16,17 (+4.5, 4.6). **Open:** 4.7 pointer-based tabs `[ready-for-dev]`, 4.8d chat quality LLM-as-judge `[ready-for-dev]`.

### Epic 5: Deliverables — ✅ DONE
Report/podcast/video/image. **FRs:** FR-21,22,23.

### Epic 6: Automations — ✅ CORE DONE (4 gap mới: playbook layer)
Schedule/event/**memory_change** trigger + `agent_task`/`continue_research`/**write_back_notion|slack|linear|jira** action. **FRs:** FR-19, FR-20, **FR-18**, **FR-35**. **Open:** 6.6/6.7/6.9 (playbook reuse + schema-driven UI + workspace vertical & library) — **gated sau pilot BĐS; không có forward dependency kỹ thuật**.
> **⚠️ Cải chính 2026-07-25:** header trước ghi *"DONE (2 gap)"* với 6.4 `[GAP]` và 6.5 `[GAP, post-MVP]` — **cả hai đều đã DONE** (verify code; xem Story 6.4/6.5).
> **➕ Bổ sung 2026-08-05 (pivot bdsai):** core automation đã đủ, nhưng thiếu **lớp playbook** — user hiện phải mô tả lại `intent` mỗi lần, không dùng được cho nghiệp vụ vertical lặp lại.
> **⚠️ Cải chính kiến trúc 2026-08-05 (architect review — Winston).** Bản đầu của 6.6 ghi *"thêm parameterization"* — **SAI**: `AutomationDefinition.inputs` + `Inputs.schema_` (JSON Schema 2020-12) + `PlanStep.params` render-at-execute + Jinja sandboxed `{run, inputs, steps}` **đã tồn tại** ⇒ automation vốn đã là template có tham số. 6.6 đổi thành **"expose cơ chế đã có"** (phạm vi nhỏ hơn nhiều), **cấm thêm lớp params thứ hai**. Thêm **6.9 (workspace `vertical` + playbook library)** vì khái niệm `vertical` chưa tồn tại và cần có để library lọc theo ngành. Bổ sung vào 6.7: **`x-ui` hints** (giữ một renderer, vẫn bản địa hoá được) và **validate output LLM bằng schema** trước khi lưu.
> **ADR cần chốt:** *tool = code (subagent builtin) · nghiệp vụ = data (playbook definition)* — hiện có hai đường mở rộng song song (`registry.py` import tĩnh vs automation JSON); không chốt sẽ dẫn tới nghiệp vụ nửa code nửa data.
> Cả ba story **KHÔNG build trước pilot 2 tuần**.

### Epic 7: Multi-surface Clients — ✅ DONE
Web/desktop/extension/Obsidian/MCP. **FRs:** FR-25,26,27,28,29. **Open:** 7.4 dedicated connectors layout `[ready-for-dev]`.

### Epic 8: Người dùng thấy và kiểm soát được chi phí — ✅ DONE (2026-08-02)
Token tracking, ví credit, dashboard usage, guardrail chi phí, docs/vision sync, admin UI cho global LLM model config, workspace limits, và PostHog analytics. **FRs:** FR-30, FR-31, **FR-41** *(mới)*. 8.10, 8.11, 8.12, 8.13 **done**.
> **⚠️ Đổi tên + đánh lại số hiệu 2026-07-25 (readiness Q-7 + C-C).** Tên trước *"Platform Operations (Billing/Usage/Token)"* là framing ops. **Và quan trọng hơn — số hiệu story đã bị xung đột với `sprint-status.yaml`:** `8.4a`/`8.5`/`8.6` trong tài liệu này nghĩa **khác** `8-4`/`8-5`/`8-6` trong sprint-status (observability-logging / security-permissions / multi-tenant-isolation). Đã đánh lại theo số **chưa dùng**: `8.4a → 8.8` · `8.5 → 8.9` · `8.6 → 8.10`. Từ giờ số hiệu ở hai tài liệu khớp 1-1.

### Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng — ✅ DONE (2026-08-05)
Người dùng research sâu được mà **không vỡ** khi engine chết (9.1a), **không treo** cả chat turn khi engine chậm (9.3, State A mặc định), và **trả đúng tiền** cho thứ mình dùng (9.2). **FRs:** FR-38 [DONE,P0], FR-24 [DONE,P0], FR-37 [DONE,P0, parser `done.usage.costDollars` + `done.usage.estimated` + `done.resolvedMode` (top-level canonical) + `promptTokens`/`completionTokens`/`totalTokens`/`model` + canonical golden fixtures + fallback 60k micros ≈ $0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671], FR-39 [DONE — 9.6 provenance + re-validation], NFR-9 [DONE — State A async deliverable default; sync chat-mode chỉ cho `speed`/`balanced`; `quality`/`deep` async-only; State B mở khi ChainLens 34.1 full-pipeline cost + Nowing e2e p95 `balanced` ≤ 30s]. **Deferred / Post-MVP:** **9.5** metered self-host endpoint (chưa phê duyệt). **Governed by:** `AD-15` · `AD-16` (license — cho 9.4) · **`AD-11.1`** (provenance recipe — cho 9.6) · **`AD-17`** (async door — cho 9.3) · **`AD-19`** (trang khó: anti-bot ở Nowing, engine không gọi ngược inline, escalation async — cho 9.1a/9.3) · **`AD-20`** (screenshot-as-evidence, không adopt visual-RAG stack) · AD-7, AD-8 amended.
> **✅ Cập nhật 2026-08-05:** 9.1a, 9.1b, 9.2, 9.3, 9.4, 9.6 **done**. 9.5 **deferred**.
>
> **🆕 2026-08-03 — Epic 10: Connector & Scraper Expansion** (Vietnam BĐS + broader scraper port). **Open:** 10.1 batdongsan `[done]`, 10.2 chotot `[done]`, 10.3 muaban `[done]`, 10.4 cross-source aggregator `[done]`.
> **⚠️ Đổi tên 2026-07-25 (readiness Q-1).** Tên trước — *"Deep-Research Engine Integration (ChainLens)"* — là **technical epic**: nó mô tả hạ tầng, không mô tả điều user làm được. Ba mệnh đề trong tên mới map thẳng vào ba story P0/P1.
>
> **🆕 2026-08-03 — Epic 11: Telegram Automation & Bot** (notification, write-back, inline keyboard, commands). **Open:** 11.1 notification foundation `[done]`, 11.2 write-back & builder `[done]`, 11.3 interactive bot & commands `[done]`.

---

## Epic 2: Connectors

### Story 2.5: Per-Workspace MCP Tool Enable/Disable Toggle  `[DONE per sprint-status: 2-5]`
As a workspace owner,
I want to enable/disable từng MCP tool theo workspace,
So that tôi kiểm soát agent được dùng tool nào (vd tắt `nowing_reddit_scrape`).

**Acceptance Criteria:**
**Given** owner mở workspace MCP settings, **When** tắt một tool, **Then** `tools/list` của MCP server lọc bỏ tool đó cho workspace này (server-side), workspace khác không đổi.
**And** selfcheck `EXPECTED_TOOLS` (AR-8) phải toggle-aware — không fail khi tool bị ẩn hợp lệ.
_OQ-4 · AD-DEFER-3._

### Story 2.6: Indeed Jobs Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
As a recruiter or market researcher,
I want to scrape job listings and job details from Indeed,
So that I can track hiring trends, competitor headcount, and job market signals in my workspace.

**Acceptance Criteria:**
**Given** a search query (title, location, radius, sort), **When** I call the Indeed scraper, **Then** it returns paginated job cards with title, company, location, salary, summary, and posting date.
**Given** a job detail URL (`/viewjob`), **When** I scrape it, **Then** it returns full job description, requirements, benefits, and apply link.
**And** blocked/paginated pages fail gracefully with a typed `block_type`; **And** billing is metered per `INDEED_JOB` unit.

**Kỹ thuật:** tái dùng pattern scraper hiện có (URL resolver, warmed browser, parse, billing unit). Tạo `indeed.scrape` capability với REST + agent subagent + MCP tool.
_FR-6 · upstream PR #1605._

### Story 2.7: Walmart Product + Reviews Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
As an e-commerce analyst,
I want to scrape Walmart product listings and reviews,
So that I can monitor competitor pricing, ratings, and customer feedback.

**Acceptance Criteria:**
**Given** a product search or product page URL, **When** I call the Walmart scraper, **Then** it returns product title, price, rating, seller, availability, and review summary.
**Given** a product with reviews, **When** I request reviews, **Then** it returns paginated review text, rating, date, and verified status.
**And** the capability is exposed via REST, agent subagent (`walmart` specialist), and MCP tool.

**Kỹ thuật:** parse `__NEXT_DATA__`, rotate proxies on block, add `walmart.scrape` + `walmart.reviews` verbs, register billing units.
_FR-6 · upstream PR #1614._

### Story 2.8: Amazon EU Marketplaces  `(mới 2026-07-30)`  `[ready-for-dev]`
As a seller watching European markets,
I want the Amazon scraper to support EU marketplaces (`amazon.de`, `amazon.fr`, `amazon.co.uk`, etc.),
So that I can track prices and listings across regions.

**Acceptance Criteria:**
**Given** an Amazon product URL on an EU domain, **When** I scrape it, **Then** it returns localized product metadata, price, currency, and availability.
**And** URL validator accepts EU TLDs; **And** region/currency are exposed in output schema.
_FR-6 · upstream PR #1628._

### Story 2.9: Scraper API Input Validation & Error Handling  `(mới 2026-07-30)`  `[done]`
As an API consumer,
I want clear 422 validation errors and inline feedback when I submit invalid scrape URLs,
So that I can fix my request without guessing.

**Acceptance Criteria:**
**Given** an invalid or unsupported URL for any scraper, **When** I submit, **Then** the response returns structured field errors with the offending field and a human-readable hint.
**Given** the playground UI, **When** a validation error occurs, **Then** it surfaces inline and persists a toast.
**And** all scrapers (web, amazon, walmart, youtube, reddit, tiktok, google maps, indeed) reuse a shared URL validator and `HttpUrlStr` type.
_FR-6 · upstream PR #1623._

### Story 2.10: Exa MCP Search Connector  `(mới 2026-08-05)`  `[DONE 2026-08-05]`
As a workspace user,
I want to connect the Exa AI MCP server as a first-class search connector,
So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.

**Acceptance Criteria:**
**Given** the workspace has no Exa connector, **When** an owner POSTs `/search-source-connectors` with `connector_type: "EXA_MCP_CONNECTOR"` and an optional `exa_api_key`, **Then** the backend persists a connector whose `config.server_config` points to `https://mcp.exa.ai/mcp` with `x-api-key` injected as a header, and `is_indexable` is forced to `false`.
**Given** the connector is saved, **When** the multi-agent chat loads tools, **Then** it discovers only `web_search_exa` and `web_fetch_exa` and treats them as `readonly` so no HITL prompt is shown.
**Given** a user asks a question in chat, **When** the agent calls `web_search_exa`, **Then** it receives clean, ready-to-use text from top web results.
**Given** a user provides a known URL, **When** the agent calls `web_fetch_exa`, **Then** it returns the page content as clean markdown.
**And** alembic migration `190_add_exa_mcp_connector.py` is applied to the database.
**And** the new connector type is wired into `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS`, `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`, `_CONNECTOR_TYPE_TO_SEARCHABLE`, `BASE_NAME_FOR_TYPE`, and connector config validation.
**And** `ruff check` on changed files and `pytest tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py` pass.

**Kỹ thuật:** add `EXA_MCP_CONNECTOR` to `SearchSourceConnectorType`, `MCP_SERVICES`, connector agent/searchable maps, and validation; create route-level `server_config` builder from `exa_api_key`; reuse `mcp_discovery` subagent with curated `allowed_tools` / `readonly_tools`.
_FR-8 · FR-8.1 · OQ-4._

---

## Epic 3: Knowledge Base + Long-Term Memory

_Đã DONE: 3.1 upload/index, 3.2 folders, 3.3 hybrid search, 3.4 citation panel, 3.5 AI-file-sort [REMOVED], 3.8 long-term memory storage/retrieval (FR-32, mig 177 + `memories_routes.py` + MCP)._
_Mới 2026-07-25 (readiness Nhóm 3): **3.13** first-run value (FR-40) · **3.14** memory injection bound (`AD-18`)._

### Story 3.6: Citation Scroll-to-Highlight in Full Document Editor  `[DONE per sprint-status: 3-6]`
As a researcher,
I want click citation nhảy đúng đoạn chunk trong full editor,
So that tôi lần ngược câu trả lời về nguồn chính xác.

**Acceptance Criteria:**
**Given** một citation trong chat, **When** bấm "Open" mở full editor, **Then** editor scroll tới + highlight đúng chunk (truyền `chunkId`, không chỉ `documentId`).
**And** `editorPanelAtom` có trường `chunkId` + highlight state; **And** không có chunk match thì fallback về đầu document + thông báo.
**UX Notes (nhẹ, brownfield):** bám component `nowing_web/components/citation-panel/citation-panel.tsx` (đã có scroll/highlight chunk) + editor hiện có — chỉ mở rộng state, KHÔNG thiết kế mới. Cần contract đầy đủ → `bmad-ux`.
_NFR-6 · AD-DEFER-1._

### Story 3.7: Memory Retention, Right-to-Delete & Legal Readiness  `[DONE retention: 3-7; memory right-to-delete/legal → xác nhận khi GA cloud]`
As a workspace owner / DPO,
I want retention + right-to-delete cho memory và dữ liệu scrape lưu dài hạn,
So that Nowing đáp ứng ToS/bản quyền/PII và người dùng kiểm soát dữ liệu (chốt TRƯỚC GA cloud).

**Acceptance Criteria:**
**Given** một `Memory` có `memory_versions`/`memory_relations`/embedding, **When** thực hiện right-to-delete (erasure), **Then** memory + versions + relations + embedding bị purge (hoặc anonymize theo policy) — test e2e: create→correct→cite→erase→assert sạch mọi bảng.
**Given** dữ liệu phái sinh từ scrape, **When** có ToS takedown theo nguồn, **Then** bulk-delete theo `source_type`/`source_id` (cần provenance tag).
**And** policy tách rõ **self-host vs cloud** (RS-6); **And** data export (RS-8); **And** doc retention (mig 176) được nối vào cùng policy.
_OQ-3 · AR-4 · AD-DEFER-4._

### Story 3.9: Memory Recall Eval-Gate  `(mới)`  `[DONE — SHIP-GATE implementation complete; baseline ratification pending]`
As a platform team,
I want một eval gate đo chất lượng recall của memory trên `nowing_evals`,
So that không ship recall rác (agent "đoán" thay vì "nhớ").

**Acceptance Criteria:**
**Given** harness `nowing_evals` (đã có `retrieval.py` recall@k/MRR/nDCG + `wilson_ci`), **When** thêm **suite memory-recall** nhắm `nowing_recall`/`/memories/search`, **Then** suite chạy được qua CLI với dataset gán nhãn.
**Given** cần đo chất lượng, **When** định nghĩa oracle "recall hit" (top_k≤5 + ngưỡng similarity, verify RS-2) + thêm metric **noise-rate**, **Then** đo được precision@5 và noise với Wilson CI.
**Given** baseline đã đo, **When** chốt **số SM-10** (precision@5 ≥ X, noise ≤ Y) — **cấm placeholder "≥X%"**, **Then** gate chặn ship nếu chưa đạt (RS-7).
**And** MCP selfcheck CI (AR-8) chạy trong pipeline.
_NFR-8 · AR-1 (re-scoped: extend harness, KHÔNG bootstrap) · AR-3 · AR-8 · RS-2 · SM-10._
**Phối hợp (KHÔNG hard forward-dep):** dựng suite/harness/label dataset chạy độc lập được; chỉ **đo baseline cuối** trên corpus sau 3.10 (legacy data safety) và sau khi 8.4a đông cứng auto-extract. 3.10 & 8.4a là **P0 theo ưu tiên** (mitigate rủi ro prod), không chặn khởi động story này.

### Story 3.10: Legacy Memory Data Safety (forensic + backfill guard)  `(mới)`  `[DONE 2026-07-25]`
As a user with existing memory data,
I want migration 178 drop legacy `memory_md` columns safely,
So that no user memory is lost when the new `Memory` table goes live.

> **✅ KẾT QUẢ (sprint-status 2026-07-25):** 178 **CHƯA apply prod** (`alembic_version=174`; 175–179 chỉ ở branch `develop`); cột `memory_md`/`shared_memory_md` còn, nội dung **RỖNG** (0/3 users, 0/3 workspaces); bảng `memories` chưa tồn tại trên prod. Snapshot `pre-memory-remediation` (pg_dump -Fc, 18MB) đã tạo. **Kết luận: KHÔNG mất dữ liệu.** ⇒ story đổi từ *recovery* sang *prevention*.

**Acceptance Criteria:**
**Given** production DB, **When** truy vấn `alembic_version` + lịch sử deploy, **Then** ghi rõ 178 đã apply prod chưa (ops ticket **trong ngày** — time-sensitive).
**Given** cấu hình backup/PITR, **When** kiểm tra retention, **Then** gia hạn retention phủ mốc trước-178 + chụp snapshot "pre-memory-remediation", verify restorable trên non-prod.
**Given** `178_drop_legacy_memory_columns.py` trên `develop`, **When** sửa `upgrade()`, **Then** thêm bước backfill: đọc `memory_md`/`shared_memory_md` non-empty → parse → insert `memories` (`source_type='manual'`) **TRƯỚC** `DROP COLUMN`, kèm verify count.
**Given** ngay trước khi deploy 178 lên prod, **When** re-check `users_with_memory`/`workspaces_with_shared_memory`, **Then** =0 (an toàn drop) HOẶC đã được backfill cover.
**And** gate: KHÔNG merge/deploy 178 lên production nếu `upgrade()` chưa có backfill.
_FR-36 · AR-2._

### Story 3.11: Memory Dedupe & Confidence Tuning  `(mới)`  `[DONE dedupe (đã wire cosine<0.08); tuning ngưỡng optional qua 3.9]`
As a platform team,
I want validate/tune ngưỡng dedupe + confidence qua eval,
So that memory không thành "bãi rác" (nhớ trùng/nhiễu) mà cũng không merge nhầm.

**Acceptance Criteria:**
**Given** dedupe primitive đã có (`repository.py` cosine<0.08 + `update_on_duplicate`, đã wire auto-extract `extraction.py`), **When** chạy bench dedupe precision/recall trên `nowing_evals`, **Then** đo được tỷ lệ merge đúng/sai.
**And** tune ngưỡng cosine + confidence default (0.7) dựa trên số đo; **And** phủ cả path auto-extract lẫn manual create.
_AR-3 · gắn với 3.9._

### Story 3.12: Memory Security — RBAC Enforcement, Isolation & Audit  `(mới)`  `[DONE — sprint 8-5 security + IDOR fix (deferred-work 4.5)]`
As a security-conscious team,
I want memory an toàn multi-tenant + có audit,
So that recall không rò rỉ cross-tenant và mọi memory write có vết.

**Acceptance Criteria:**
**Given** quyền `memory:*` đã backfill (mig 177), **When** gọi mọi memory endpoint + MCP tool, **Then** permission được enforce (test khẳng định, không chỉ tin backfill).
**Given** 2 workspace/user khác nhau, **When** recall/search, **Then** không trả memory cross-tenant (test isolation, NFR-5).
**And** mọi memory write (create/correct/delete) ghi **audit log** (hiện chỉ `logger.warning`).
_AR-9 · NFR-2/NFR-5 (memory-scoped)._

---

### Story 3.13: First-Run Value — Research Run sinh ra Memory  `(mới 2026-07-25)`  `[DONE — HIGH]`

**Là** người dùng mới của Nowing,
**tôi muốn** hành động research **đầu tiên** của mình để lại memory,
**để** `nowing_recall` có nội dung ngay trong session đầu — thay vì trả rỗng và làm tôi nghĩ sản phẩm không chạy.

> **Vì sao story này tồn tại (readiness P-4 / C-2).** Verify code 2026-07-25: `MemoryExtractionService` chỉ có **`extract_from_turn`** (`app/services/memory/extraction.py:118`) — không có đường extract từ scrape run, deep research, hay document. Workspace mới **không seed gì** (grep `seed|sample|onboarding|welcome|starter|template` trên `workspaces_routes.py` = rỗng). ⇒ **recall session đầu rỗng theo cấu trúc**, và **M1 (first-run value ≤15 phút) không tồn tại**. Đồng thời câu headline của brief — *"it remembers what it went and found, not just what you told it"* — hiện **chỉ đúng nửa sau**.

**Quyết định:** làm research run sinh memory. **KHÔNG seed dữ liệu mẫu** — memory giả dạy sai mental model, và sẽ đổ rác vào đường inject chưa có chặn trên (xem `3.14`).

**Acceptance Criteria:**
**Given** người dùng mới vừa tạo workspace, **When** chạy **một** research/scrape run (8 platform / 14 verb sẵn có, hoặc deep research), **Then** run sinh memory `source_type = SCRAPER_RUN` + provenance — **không cần chat trước**.
**Given** run vừa xong, **When** gọi `nowing_recall`, **Then** trả fact **có citation trỏ về run gốc**, không rỗng.
**Given** người dùng mới hoàn toàn, **When** đo signup → run đầu → recall có nội dung, **Then** **≤ 15 phút** (M1).
**And** tôn trọng kill-switch `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled` (`8-8` done) và spend cap (`8-7`).
**And** memory sinh ra đếm vào ngân sách 8.000 chars của **NFR-1b** — đây là ràng buộc, không phải ghi chú.

**Ghi chú kỹ thuật:**
- Story này chính là **writer còn thiếu** cho `MemorySourceType.SCRAPER_RUN` (khai báo `app/db.py:572`, **hiện không ai ghi**).
- ⚠️ **`Memory.source_id` là `Integer` (`app/db.py:2077`) còn `Run.id` là `UUID` (`app/db.py:3155`)** ⇒ **không dùng `source_id` cho run**; đi qua `source_run_id` của `AD-11.1`.
- ⚠️ `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) ⇒ memory phải **tự chứa** ngữ cảnh; `Run` gốc sẽ biến mất.
- **Dep mềm với `9-6a`:** provenance đầy đủ (`source_capability` + `source_input`) cần `9-6a`. Bản tối thiểu (`source_type` + `source_run_id`) chạy độc lập ⇒ **không chờ**.

_FR-40 · M1 · brief §9 H-4 · `AD-11.1`._

---

### Story 3.14: Memory Injection — chặn trên & ngân sách latency  `(mới 2026-07-25)`  `[DONE — đi kèm 3.13]`

**Là** người dùng dùng Nowing càng lâu càng nhiều memory,
**tôi muốn** mỗi lượt chat có chi phí ổn định,
**để** sản phẩm không tệ dần đúng theo mức tôi dùng nó nhiều.

> **Vì sao (readiness C-1 / P-5, verify 2026-07-25).** Có **hai** đường recall, PRD chỉ mô tả một:
> - `nowing_recall` / `/memories/search` → bounded top_k ≤5, hybrid. **Có** trong FR-32.
> - `MemoryInjectionMiddleware.abefore_agent` → **chặn mọi lượt chat**, chạy `SELECT * FROM memories WHERE workspace_id=? ORDER BY created_at` **không LIMIT**, **bỏ qua cả `ix_memories_embedding` (HNSW) lẫn `ix_memories_content_search` (GIN)** đã có sẵn. **Không** có trong PRD, **không** có bound.
>
> `MEMORY_HARD_LIMIT = 25.000` chỉ validate **một** `content` ở đường **ghi** — aggregate của N fact **chưa từng bị kiểm tra**. Phanh duy nhất là `<memory_warning>` ở 18.000 nhờ LLM tự consolidate, mà `extract_from_turn` (Celery) ghi row nhanh hơn LLM dọn.
>
> **Cải chính P-5:** P-5 ghi "auto-extract cộng latency mỗi turn" — **sai**. Caller duy nhất là `memory_extraction_task.py` (Celery, ngoài request) ⇒ **không** trên critical path. Nửa còn lại của P-5 đúng, và nặng hơn dự kiến.

**Acceptance Criteria:**
**Given** workspace có N memory bất kỳ, **When** chạy một lượt chat, **Then** memory injection dùng **top-k bounded** qua HNSW/GIN — chi phí **O(top-k), không O(N)**.
**Given** tổng memory render vượt ngân sách, **When** inject, **Then** **cắt ở đường đọc tại ≤ 8.000 chars** (không dựa vào `<memory_warning>`).
**Given** ngân sách đã chốt, **When** đo, **Then** DB p95 **≤ 150ms** cho injection và **≤ 300ms** cho recall tool — assert trong test, dùng hook **đã có** `_perf_log "[memory_injection] ... db=%.3fs total=%.3fs"`.
**Given** injection lỗi, **When** rơi vào `except → return None`, **Then** phát **counter** (hiện chỉ `logger.exception` ⇒ degrade im lặng).
**Given** auto-extract, **When** chạy một lượt chat, **Then** **regression test** khẳng định nó **không** nằm trên critical path (hiện đúng nhờ Celery, nhưng không test nào giữ).
**And** metric + tài liệu **tách tên** `memory_injection` ≠ `memory_recall`.

**Given** `/memories/search` và `nowing_recall`, **When** trả kết quả, **Then** **expose RRF score thật** thay cho `score=0.0` hardcode — để vế *"vượt ngưỡng similarity"* của FR-32 / NFR-1c **áp được**. `[thêm 2026-07-25 — nhận việc treo]`

> **Vì sao việc này ở đây.** `search.py:97` **có** tính RRF score và `order_by(text("score DESC"))`, nhưng cùng file `return [row[0] for row in rows]` bỏ score đi, và `memories_routes.py:117` hardcode `score=0.0`. Không client nào thấy similarity. `nowing_evals/.../memory/recall/gate.yaml` buộc phải đặt `required_oracle_mode: rank_only`.
>
> **Việc này từng bị hoãn sang `3-11`, nhưng `3-11` đã `done` mà không làm** (*"dedupe đã wire; tuning ngưỡng optional qua 3-9"*). Hai note trỏ vòng vào nhau ⇒ mất chủ. Nhận về `3-14` vì `3-14` đã sửa đúng `search.py` và `AD-18` rule 1 (bounded top-k) **buộc** phải làm việc với score.
>
> ✅ Cập nhật 2026-08-01: `gate.yaml` đã trỏ đúng `Story 3.14`; `3-14` done.

**Thứ tự:** nên chạy **trước khi chốt số SM-10** của `3-9`, vì **hai** lý do độc lập:
1. `AD-18` rule 6 — baseline đo trên lượng inject phụ thuộc N thì không tái lập được.
2. **Oracle đang bị làm yếu.** `rank_only` chỉ hỏi *"có trong top 5 không"*, không hỏi *"có đủ giống không"* ⇒ gate **PASS được với kết quả rác** tình cờ rank cao. Chốt SM-10 dưới oracle này sẽ ra số dễ hơn thực tế.

Và là **điều kiện đi kèm** của `3.13`, vì `3.13` làm N tăng nhanh hơn.

_NFR-1b/1c/1d · `AD-18` · tiền đề của NFR-8 · nhận việc treo từ `3-11` (expose RRF score)._

### Story 3.15: Run Citations as Verifiable Sources  `(mới 2026-07-30)`  `[ready-for-dev]`
As a researcher,
I want scraper runs to be citable sources in chat,
So that I can trace claims back to the exact run that produced them.

**Acceptance Criteria:**
**Given** a chat answer that references data from a scraper run, **When** the model emits a citation, **Then** the citation points to the `Run` record (run id + capability + input snapshot) and renders as `run_<uuid>`.
**Given** a run citation in the UI, **When** I click it, **Then** it opens the run detail / citation panel showing the run output.
**And** citations carry a new `source_type = RUN` with structured fields; **And** the `RUN` source type is supported by citation renderers and the citation panel.

**Kỹ thuật:** add `RUN` to citation source enum, mint run citation from capability tool, parse `run_<uuid>` tokens in chat, render citation chip, open run in citation panel.
_FR-13 · FR-39 · upstream PR #1619._

### Story 3.16: Open Knowledge Format (OKF) Export  `(mới 2026-07-30)`  `[ready-for-dev]`
As a data owner or integrator,
I want to export my workspace knowledge base in Open Knowledge Format (OKF),
So that I can move, archive, or integrate Nowing knowledge with other tools.

**Acceptance Criteria:**
**Given** a workspace with documents, memories, and source provenance, **When** I request an OKF export, **Then** it produces a valid OKF bundle (documents, chunks, facts, relations, citations) that can be validated against the OKF schema.
**Given** the export, **When** inspected, **Then** it does not leak data from other workspaces and redacts API keys / secrets.

**Kỹ thuật:** build an export job over workspace-scoped `Document`, `Chunk`, `Memory`, `MemoryRelation`; serialize to OKF JSON; stream/limit size for large KBs.
_FR-32 · RS-8 · upstream PR #1617._

---

## Epic 6: Automations

_Đã DONE: 6.1 triggers, 6.2 runs/retries, 6.3 agent_task._

### Story 6.4: Direct Write-Back Actions  `[DONE per sprint-status: 6-4]`
As a workspace owner,
I want automation ghi trực tiếp Notion/Slack/Linear/Jira như action type,
So that workflow không phải đi vòng qua `agent_task`.

**Acceptance Criteria:**
**Given** automation definition, **When** thêm action type write-back (Notion/Slack/Linear/Jira), **Then** chạy được với retry + audit + **compensating action / best-effort undo** (KHÔNG phải true rollback — không un-send Slack được; nêu rõ giới hạn).
**And** quyết định kiến trúc OQ-5 (action type riêng vs agent_task tool) được ghi lại.
_FR-18 · OQ-5 · AD-DEFER-2. Lưu ý: agent_task đã cho phép write-back → đây là nâng cấp, không chặn beachhead._

### Story 6.5: Memory-Driven Automations  `[DONE per sprint-status: 6-5 — cải chính 2026-07-25]`

> **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Header trước ghi `[GAP, post-MVP]` — **SAI**. Verify code: trigger `memory_change` (`app/automations/triggers/builtin/memory_change/`, đăng ký trong `triggers/builtin/__init__.py`) · action `continue_research` (`actions/builtin/continue_research/`, đăng ký trong `actions/builtin/__init__.py`) · `AutomationRun.research_thread_id` (`db.py:712` + relationship `db.py:746`) · resolve qua `dispatch/launch.py:44`. `sprint-status.yaml` (`6-5: done`) là bên đúng.
As a workspace owner,
I want automation trigger khi memory đổi / tiếp tục research thread theo lịch,
So that workflow nghiên cứu chạy liên tục không cần prompt tay.

**Acceptance Criteria:**
**Given** automation có trigger `memory_change` hoặc schedule, **When** memory mới match query/tags **OR** cron đến hạn, **Then** `AutomationRun` chạy với `research_thread_id` + memory context; action `continue_research`/`agent_task` write-back kết quả.
_FR-35 · AD-DEFER-6._

### Story 6.6: Playbook Reuse — expose `inputs.schema` đã có  `[GAP — P1, gated sau pilot BĐS]`

> **⚠️ Cải chính kiến trúc 2026-08-05 (Winston / architect review).** Bản đầu của story này viết *"thêm parameterization + `params_model` cho playbook"* — **SAI hiện trạng**. Verify code: `AutomationDefinition.inputs: Inputs | None` **đã tồn tại** và `Inputs.schema_` chính là *"JSON Schema (draft 2020-12) for accepted inputs"* (`schemas/definition/inputs.py`); `PlanStep.params` *"rendered at execute time"* (`plan_step.py:21-23`); `build_run_context()` expose namespace `{run, inputs, steps}` cho Jinja **sandboxed** (`templating/context.py:39`, `environment.py` — `SandboxedEnvironment` + `StrictUndefined`).
> ⇒ **Automation ĐÃ là template có tham số.** Story này KHÔNG xây cơ chế mới, mà **expose cơ chế đã có** thành playbook tái dùng được. **Tuyệt đối không thêm lớp params thứ hai** (sẽ tạo hai đường render — nợ kiến trúc tệ nhất).

As a workspace user (môi giới BĐS),
I want lưu một nghiệp vụ thành playbook tái dùng và chạy lại bằng cách điền biến,
So that tôi không phải mô tả lại toàn bộ yêu cầu nghiệp vụ mỗi lần.

**Acceptance Criteria:**
**Given** một `AutomationDefinition` đã chạy đúng, **When** user lưu nó thành playbook, **Then** hệ thống lưu definition đó làm template và **dùng chính `inputs.schema` sẵn có** làm hợp đồng tham số (KHÔNG sinh model params song song).
**And** **Given** một playbook, **When** user tạo instance mới với bộ inputs khác, **Then** automation mới sinh ra không cần viết lại `intent`, inputs được **validate theo `inputs.schema`** trước khi lưu, và audit ghi rõ `derived_from_playbook_id`.
**And** **Given** playbook được sửa sau khi đã có instance, **When** template đổi, **Then** hành vi versioning là tường minh: instance đang chạy **pin theo version cũ**, không bị đổi ngầm (tránh drift âm thầm).
**And** playbook có **ownership rõ ràng**: `workspace` (user tạo) vs `system` (Nowing ship sẵn) — không rò rỉ giữa workspace.
**And** playbook khai **tool-scoping**: chỉ subagent/tool cần thiết được phép gọi (giảm cost + tăng ổn định vs để agent tự chọn trong toàn bộ registry).
_Nền tảng đã có (dùng lại, không xây mới): `AutomationDefinition.inputs` + `Inputs.schema_` · `PlanStep.params` render-at-execute · `templating/` (Jinja sandboxed, `{run, inputs, steps}`) · `ActionDefinition.params_schema` (`actions/types.py`) · `all_actions()` (`actions/store.py`) · `WorkspaceMcpToolSetting` (tiền lệ scope per-workspace)._
_⚠️ Gate: KHÔNG build trước khi pilot BĐS 2 tuần cho tín hiệu retention — chưa biết `inputs.schema` cần field nào cho môi giới thì chưa build (xem `vision-lock-and-this-week-2026-08-04.md`)._

### Story 6.7: Schema-Driven Form UI cho playbook & action  `[GAP — P1, gated sau pilot BĐS]`

> **Vấn đề UX cần giải một lần cho mọi vertical.** Nowing có ~17 subagent builtin + MCP tools, và sẽ thêm nữa (xe, thiết bị B2B, tuyển dụng). Nếu mỗi tool phải code UI riêng → nợ UI tăng theo số tool.
> **Điểm mạnh kiến trúc:** cả `ActionDefinition.params_schema` (action) và `AutomationDefinition.inputs.schema` (playbook) đều là **JSON Schema draft 2020-12** ⇒ **một renderer dùng được cho cả hai**.

As a workspace user,
I want thao tác nghiệp vụ bằng form/filter thay vì viết prompt dài,
So that tôi dùng được mọi tool mà không cần học prompt, và tool mới có UI ngay.

**Acceptance Criteria:**
**Given** một action/playbook có JSON Schema (`params_schema` hoặc `inputs.schema`), **When** UI render nó, **Then** form được **tự sinh từ schema** (không hard-code UI cho từng tool) — thêm tool mới = thêm schema, **không thêm UI**.
**And** **Given** schema cần trải nghiệm bản địa (chọn quận, khoảng giá VNĐ, nhãn tiếng Việt), **When** render, **Then** renderer đọc **`x-ui` hints trong schema** (widget · label · options · đơn vị) để tùy biến — **giữ một renderer duy nhất**, không fork UI theo tool. *(Không có lớp hint này thì dự án sẽ bị kéo về hard-code UI từng tool — đúng thứ story muốn tránh.)*
**And** **Given** user gõ yêu cầu tự nhiên (web hoặc Zalo/Telegram bot), **When** LLM parse thành inputs, **Then** inputs **BẮT BUỘC validate lại bằng schema (Pydantic) trước khi lưu** — không tin trực tiếp output LLM — rồi hiện form/xác nhận gọn để user sửa (chat → parse → **validate** → confirm).
**And** **Given** một nghiệp vụ tần suất cao (Deal-Radar BĐS), **When** cần trải nghiệm tối ưu, **Then** cho phép override bằng filter UI chuyên biệt + nút **"Lưu tìm kiếm này thành cảnh báo"** (tái dùng thói quen filter sẵn có của môi giới, không bắt học prompt).
**And** danh sách tool KHÔNG phơi ra dạng menu kỹ thuật: gom theo vertical + ẩn sau tên nghiệp vụ người dùng hiểu.
_⚠️ Gate: business — chỉ build sau pilot BĐS retention xanh (không phụ thuộc kỹ thuật 6.6)._

### Story 6.9: Workspace `vertical` + Playbook Library  `[GAP — P2, gated sau pilot BĐS]`

> **Phát hiện từ architect review:** khái niệm `vertical` **chưa tồn tại** trong schema. Không có nó thì không thể "gom playbook theo ngành". Story này gộp cả việc khai báo vertical và thư viện playbook lọc theo vertical.

As a workspace user,
I want my workspace to declare its industry and show only relevant playbooks,
So that I can pick a pre-built playbook for my vertical without designing a workflow from scratch.

**Acceptance Criteria:**
**Given** a workspace, **When** it is created or updated, **Then** it has a `vertical` attribute (e.g. `real_estate`, `auto`, `b2b_equipment`, `general`), defaulting to `general` for backward compatibility.

**Given** a playbook or tool declares `verticals[]`, **When** a user browses the library, **Then** they only see items matching the workspace vertical (or `general`).

**Given** a workspace has a configured vertical, **When** a user opens the playbook library, **Then** they only see playbooks for that vertical (e.g. real estate: Deal-Radar, Verify cross-source, Match buyers, Write listing description).

**Given** a new vertical needs to be opened, **When** adding a playbook, **Then** it only requires a **definition + schema (data)**, no UI code changes and no new subagent — satisfying the G6 vertical expansion roadmap target.

**Given** a playbook is selected, **When** the user runs it, **Then** they fill in inputs validated against the playbook schema and the automation runs using the existing parameterized automation engine.

_ADR cần chốt kèm: **tool = code (subagent builtin), nghiệp vụ = data (playbook definition)** — tránh tình trạng nghiệp vụ nửa nằm ở `registry.py` nửa nằm ở JSON._
_Tham chiếu: `vertical-expansion-roadmap-2026-08-04.md` (G6: mở vertical mới bằng config, ≤2-4 tuần)._

---

## Epic 8: Platform Operations (Billing / Usage / Token)

_Đã DONE: 8.1 token usage tracking (FR-30), 8.2 credit wallet + Stripe (FR-31)._

### Story 8.3: Usage & Credit Dashboard  `[DONE per sprint-status: 8-3]`
As a user,
I want dashboard xem usage/chi phí theo workspace/model/thời gian,
So that tôi hiểu mình tiêu gì (dữ liệu `TokenUsage`/`credit_micros_balance` đã có, thiếu UI).

**Acceptance Criteria:**
**Given** `TokenUsage` đã ghi, **When** mở usage dashboard, **Then** hiển thị aggregate theo workspace/model/`usage_type`/thời gian (gồm `memory_create`).
**And** buy-credits page hiển thị lịch sử, không chỉ current balance.
**UX Notes (nhẹ, brownfield):** bám pattern settings/buy-credits page hiện có trong `nowing_web/`; dashboard = bảng + biểu đồ aggregate theo workspace/model/thời gian. Cần contract đầy đủ → `bmad-ux`.
_NFR-7 · FR-31 · AD-DEFER-5._

### Story 8.8: Auto-Extract Kill-Switch & Safe Default  `(mới)` `(đánh lại số từ 8.4a — C-C)`  `[DONE — flags MEMORY_AUTO_EXTRACT_ENABLED (global) + workspaces.memory_auto_extract_enabled (per-ws) đã có]`
As a platform engineer,
I want kill-switch tin cậy + default an toàn cho auto-extract,
So that chi phí per-turn không kiểm soát dừng ngay lập tức.

**Acceptance Criteria:**
**Given** `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled`, **When** đặt global kill-switch OFF, **Then** không task extraction nào enqueue ở bất kỳ turn (verify `assistant_finalize`); không cần redeploy; có test.
**Given** một workspace, **When** owner tắt riêng, **Then** extraction dừng cho workspace đó, không ảnh hưởng khác.
**Given** default an toàn, **When** tạo workspace mới, **Then** `memory_auto_extract_enabled` default phản ánh policy đã chốt (OFF tới khi gates ship).
_AR-6 · FR-15. **Dep: none** (P0)._

### Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit  `(mới)`  `[DONE — 59 tests passed; gate before auto-extract goes to prod]`
As a workspace owner,
I want spend budget cap + wallet pre-check + rate-limit theo thời gian cho auto-extract,
So that chi phí dự đoán được khi auto-extract bật.

**Acceptance Criteria:**
**Given** một workspace, **When** vượt **spend budget cap** trong kỳ HOẶC ví không đủ (wallet pre-check **TRƯỚC** khi enqueue LLM call phụ), **Then** extraction bị skip + log, không âm thầm đốt credit.
**And** rate-limit theo thời gian (ngoài `MAX_ITEMS=3` sẵn có); **And** edge anonymous-chat (FR-17) attribution rõ ràng.
_AR-6 · RS-1. **Dep: 8.4a** (kill-switch/flags đã có)._

### Story 8.9: Memory Cost/Turn Observability  `(mới)` `(đánh lại số từ 8.5 — C-C)`  `[DONE — code-complete qua sprint story 8-4 observability-logging]`
As a team,
I want cost/turn của memory extraction/recall được đo,
So that định lượng unit economics cloud trước khi pricing (SM-C2/RS-10).

**Acceptance Criteria:**
**Given** turn có extraction/recall, **When** hoàn tất, **Then** ghi span + cost với `usage_type="memory_create"`, attribute workspace+user.
**And** aggregate cost/turn (auto-extract ON vs OFF) đo trên staging/beta → input cho pricing.
_AR-5 · SM-C2 · RS-10._

### Story 8.10: Docs / README / Vision Sync  `(mới)` `(đánh lại số từ 8.6 — C-C)`  `[DONE per sprint-status: 8-10]`
As an OSS beachhead user (agent-builder),
I want README/docs to reflect the current research-memory vision and only shipped features,
So that the repo does not look like vaporware with old positioning or removed features.

**Acceptance Criteria:**
**Given** public docs contain outdated positioning or descriptions of removed features
**When** the docs are synced
**Then** they reflect the current "long-term research memory" vision and no longer describe removed features
**And** the one-sentence product promise and a quickstart guide are published
**And** removed features cannot reappear in the docs.

_Implementation hints (not AC):_ Keep `README.md`, `docs/`, and `project-overview.md` synced; include a CI docs-vs-code drift check to catch removed features like the Admin role or AI File Sorting.

_OQ-6 · AR-10 · RS-5._

---

### Story 8.11: Admin UI for Global LLM Model Configuration  `(mới 2026-07-26)`  `[DONE per sprint-status: 8-11]`

**Là** a platform operator with the existing `is_superuser` flag (not a new admin role; workspace RBAC in FR-10 is unchanged),
**tôi muốn** thêm/sửa/xoá/bật-tắt global chat model (model dùng chung cho Auto mode) qua một trang settings trên web UI,
**để** không phải decode/sửa/encode base64 YAML trong `.env` rồi restart backend mỗi lần đổi model — quy trình hiện tại chỉ có thể thao tác thủ công qua terminal.

> **Implementation context (not AC):** global LLM configs currently load from YAML or a base64 `.env` variable at import time, with no UI or hot-reload. The existing `/global-model-connections` endpoint is read-only, and write endpoints block global connections. The `is_superuser` user flag already exists but is not used to gate any route.

**Acceptance Criteria:**

**Given** a non-superuser (including any workspace role)
**When** attempting to manage global chat models
**Then** the request is rejected with **403** — only superusers may manage global models, independently of workspace RBAC (FR-10 workspace roles remain unchanged).

**Given** a superuser opens the admin settings page
**When** they view the global models list
**Then** they see a merged list containing both file-backed models (from existing config) and DB-backed models (created via the UI) with a source label distinguishing them
**And** no real API key is returned to the client — only a boolean flag indicating whether a key is configured.

**Given** a superuser fills out the form to create a new global model
**When** they submit the form
**Then** the new global model is created in the DB and becomes available in the Auto mode pool immediately without requiring a backend restart or a configuration file change.

**Given** a DB-backed global model
**When** a superuser edits its name, price, or enabled status, or deletes it
**Then** the change takes effect for subsequent chat calls, and deleted models no longer appear in the Auto mode pool.

**Given** a file-backed global model
**When** a superuser views it in the UI
**Then** it is read-only except for a temporary enable/disable toggle, with no field edits or delete allowed through the UI (operator-owned file config remains the source of truth).

**Given** a superuser has entered the provider, API key, and model name for a new global model draft
**When** they click "Test connection"
**Then** the system calls the provider once and reports success or failure clearly before the model can be saved.

_Implementation hints (not AC — story 8.11 has no file paths in AC):_
- Thêm dependency `require_superuser()` trong `app/users.py`, song song `require_session_context`/`get_auth_context` hiện có — kiểm tra `AuthContext.user.is_superuser`.
- Mở endpoint mới (không sửa route cũ đang chặn `GLOBAL` cho user thường) dưới path riêng, ví dụ `/admin/global-model-connections`, dùng `require_superuser()` làm dependency; hoặc thêm nhánh rẽ trong route hiện có khi `scope == GLOBAL` **và** caller là superuser — chọn một, ghi lại trong story file.
- Mở rộng `materialize_global_model_catalog()` (`app/services/global_model_catalog.py`) để merge thêm `Connection`/`Model` rows có `scope == GLOBAL` từ DB vào cùng `GLOBAL_CONNECTIONS`/`GLOBAL_MODELS`, bên cạnh nguồn YAML/env hiện tại.
- Sau mỗi CRUD của admin, gọi `refresh_global_model_catalog()` (đã tồn tại, hiện chỉ gọi sau OpenRouter refresh ở `initialize_openrouter_integration()`) để hot-reload — đây là seam có sẵn, không cần dựng mới.
- Billing: field cost phải map đúng vào `litellm_params.input_cost_per_token`/`output_cost_per_token` để `pricing_registration.py` đăng ký giá cho LiteLLM (đúng cơ chế `AD-8`, không phải giá phẳng).
- FE: trang mới, tái dùng component ở `nowing_web/components/settings/model-connections/` (provider picker, connect form) nhưng đặt ở route cấp platform (không phải `/dashboard/[workspace_id]/...`), gate bằng `user.is_superuser` phía client (defense-in-depth, không thay cho check backend).

_References: FR-41 · AD-8 (cost registration) · AD-9 (mở rộng — không đổi 3 role cấp workspace) · `model_connections_routes.py` · `app/config/__init__.py` (`load_global_llm_configs`, `refresh_global_model_catalog`) · `app/services/global_model_catalog.py`._

### Story 8.12: Workspace Limits  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-12]`
As a platform admin,
I want to enforce per-workspace limits (documents, members, storage, runs),
So that I can offer tiered plans and prevent abuse on the cloud offering.

**Acceptance Criteria:**
**Given** a workspace on a free/team/enterprise plan, **When** it reaches a limit, **Then** subsequent operations are blocked with a clear upgrade message.
**Given** the workspace settings, **When** an admin opens it, **Then** they see current usage vs limits and an upgrade CTA.
**And** limits are enforced backend-side (not just UI); **And** anonymous/self-host defaults keep existing behavior.

**Kỹ thuật:** add `WorkspaceLimit` / plan config, gate document upload, member invite, and run creation; expose usage/limit API; build settings UI.
_FR-3 · FR-30 · upstream PR #1609._

### Story 8.13: PostHog Product Analytics  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-13]`
As a product team,
I want PostHog analytics integrated into the web app,
So that I can understand user flows, feature adoption, and retention.

**Acceptance Criteria:**
**Given** `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` are configured, **When** the web app loads, **Then** PostHog is initialized and captures pageviews and key events.
**Given** a superuser, **When** viewing analytics, **Then** identifiable data is hashed/anonymized and no API keys or workspace content is sent.

**Kỹ thuật:** add `@posthog-js` (if not already), initialize in layout, wrap key events, keep server-side observability separate.
_NFR-3 · upstream PR #1622._

---

## Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`

> **Nguồn:** `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED, D1–D4). **Governed by:** `AD-15` (+ AD-7; AD-8 amended cho cost; AD-3 amended bỏ FR-24).
> **Đối ứng phía ChainLens:** Epic 42 (`42-1` costDollars-in-SSE *spec ready*, `42-2` contract regression-guard, `42-3` verify Nowing needs) + Epic 43 (`43-1` eval-harness GATE 0, `43-2` planner-DAG, `43-5` cache hit-rate).
> **Gate quan trọng:** không chốt bất kỳ con số pricing/subscription nào trước khi **9.2** và **8.7** có số cost đo thật.
> **⛓️ Architecture dependency sequence (D5, 2026-07-25 · không phải epic-ordering, là kiến trúc constraint):** `9.1a` (degradation) → `public repo` → `9.1b` + `9.2` + `8-7` → `9.3` → `9.4` → *(tuỳ chọn)* `9.6`.
> - Sequence này được ghi ở **Architecture Decision Record (`AD-15` §D5)** làm ràng buộc kiến trúc, không phải vì các story trong Epic 9 phụ thuộc lẫn nhau theo nghiệp vụ.
> - **Chỉ `9.1a` chặn public repo** — vì lý do **mô hình kinh doanh**, không phải kỹ thuật: engine closed-source + Nowing public ⇒ **mọi self-host instance chạy ở trạng thái không có engine**; thiếu degradation thì self-host không dùng được và đường OSS/PLG sụp.
> - Các story còn lại trong Epic 9 có thể dev song song trong cùng sprint, nhưng deploy/release tuân theo sequence trên.
> - `9.1b` (contract guard) là P0 nhưng **không** chặn public repo. Nguồn: SCP §8 D5, PRD §1.1 + §4.9 FR-38, `AD-15`.

> **⚠️ Tách story 2026-07-25 (readiness Q-3).** `9.1` cũ gộp **hai concern khác nhau**: (a) contract regression test — bảo vệ Nowing khỏi việc engine đổi format; (b) degradation — bảo vệ **mô hình kinh doanh** self-host. Khác mục đích, khác rủi ro, khác file, test được độc lập. Quan trọng hơn: chỉ **(b)** mới thật sự chặn public repo; gộp lại làm public repo bị chặn oan bởi (a). ⇒ tách thành **`9.1a`** (chặn public repo) và **`9.1b`** (P0, không chặn).

### Story 9.1a: Research Degradation & Self-Host Independence  `(mới)`  `[DONE — P0, tiền đề trước khi public repo]`
As a self-hoster,
I want Nowing dùng được đầy đủ **mà không cần** deep-research engine, và deep research **không hard-fail** khi engine chậm/chết/chưa cấu hình,
So that tôi không cài xong mới phát hiện một tính năng vỡ, và đường OSS/PLG không sụp.

**Acceptance Criteria:**

**Given** the deep-research engine times out or returns a 5xx error
**When** a deep-research request is made
**Then** Nowing **degrades** to its hybrid-search retriever and returns an explicit `partial` (some evidence) or `engine_unavailable` (none) status
**And** **không bịa citation**, không giả vờ là câu trả lời đầy đủ; trạng thái degrade hiển thị được cho user/agent.

**Given** a self-hosted instance has the deep-research engine unconfigured
**When** a user uses Nowing
**Then** all other features work normally; deep research returns `engine_unavailable` with setup instructions
**And** không có exception chưa bắt, không có 500.

**Given** the engine emits `partial`/`insufficientEvidence` events carrying an explicit `reason`
**When** parsing the SSE stream
**Then** Nowing maps those events to a `partial` state and surfaces the `reason` to the user/agent
**And** it no longer infers the state from a heuristic that conflates "no evidence" with "broken stream".

**Given** the engine emits periodic `heartbeat` events
**When** a stream is in progress
**Then** Nowing uses those heartbeats to distinguish "still running" from "dead", instead of relying solely on a fixed timeout.

**Given** the success, timeout-degrade, and unconfigured branches
**When** the test suite runs
**Then** all three branches are covered by tests.

**Given** the deep-research engine is closed-source and Nowing is public (OSS/Cloud boundary, D5)
**When** the repo is reviewed before going public
**Then** this story is done first, and all setup docs clearly state that deep research is a cloud capability in Phase 1
**And** self-hosters are not left to discover the feature is unavailable only after install.

_Implementation hints (not AC):_
- Timeout/degrade threshold is configured by `CHAINLENS_REQUEST_TIMEOUT_SECONDS` (default 300s) and routes to the existing hybrid-search retriever under `app/retriever/`.
- Verify the exact `partial`/`insufficientEvidence` event shapes in ChainLens `api.ts:1299-1309`.
- Update `README.md`, `docker/`, and `.env.example` to document deep research as a cloud-only Phase 1 capability.

_FR-38 · AD-15 · D5. Files: `app/capabilities/chainlens/research/executor.py`, `app/retriever/`, `tests/unit/capabilities/chainlens/`, `docker/`, `.env.example`._

### Story 9.1b: Research Contract Regression Guard  `(mới)`  `[DONE — P0, không chặn public repo]`
As a Nowing maintainer,
I want contract với deep-research engine được khoá bằng test trong CI,
So that engine đổi format thì tôi biết trước khi vỡ production, chứ không phát hiện qua báo lỗi của user.

**Acceptance Criteria:**

**Given** the research SSE contract (request and response shapes)
**When** CI runs
**Then** a contract regression test locks both the request shape and the SSE parse behavior (block create/replace, patch application, terminal marker, error event, metadata)
**And** the test fails if the engine changes format, so regressions are caught before production.

**Given** a query longer than the configured maximum length
**When** it is sent
**Then** it is clamped before calling the engine.

**Given** a response with multiple sources
**When** parsing the SSE
**Then** the `sources[]` array preserves citation order so it maps correctly to the citation UI.

**Given** the documented contract does not match the real engine format
**When** tests are written and docs are fixed
**Then** the contract test and all related docs reflect the real wire format, not the outdated documentation
**And** any dead parser branch is removed or clearly marked as defensive-only
**And** tests are driven by the real format, not the outdated docs.

**Given** the upstream engine provides a shared golden SSE contract fixture
**When** writing Nowing's contract tests
**Then** Nowing reuses or imports that fixture instead of creating a second one
**And** the team proposes a shared golden JSON export that both sides consume.

_Implementation hints (not AC):_
- The current query clamp limit is `MAX_QUERY_LENGTH = 500`.
- The real SSE format is data-only frames with `type` inside JSON; terminal marker is `{"type":"done"}`; there is no `event:` or `data: [DONE]` line.
- Patches apply RFC6902 JSON Patch to `/data` inside the block.
- ChainLens issue `42-2` already has `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`, a mirror parser using `rfc6902 applyPatch`; reuse or sync with it.
- Remove or mark as defensive-only the dead `event:` branch in `_parse_sse`.
- Update PRD §4.9 FR-24, `AD-15`, and SCP §3 to match the real SSE format.

_FR-24 · AD-15 · OQ-7(1)+(4). Files: `tests/unit/capabilities/chainlens/research/test_executor.py`, `app/capabilities/chainlens/research/executor.py` (gỡ nhánh `event:`), PRD §4.9, `AD-15`. **Đối ứng ChainLens:** `42-2`._

### Story 9.2: Deep-Research Cost Metering (cost thật, không giá phẳng)  `(mới)`  `[DONE — P0, parser + fallback in place; waits ChainLens 34.1 full-pipeline cost, target 2026-08-19]`
As a PO định giá cloud,
I want cost mỗi deep-research call được ghi theo **cost thật engine báo về**, không theo hằng số env,
So that pricing/subscription có cost basis thật thay vì phỏng đoán sai 2–3×.

_Implementation context (not AC — verified 2026-08-05):_ The current flat rate under-meters quality/deep modes by 2.1–3.3×. Nowing parser now reads `costDollars`, `estimated`, `resolvedMode` (top-level canonical, with `usage.resolvedMode` as mirror/fallback), `promptTokens`, `completionTokens`, `totalTokens`, and `model` from the terminal `done` frame. ChainLens 42-1 emits writer-only `costDollars` with `estimated: true`; ChainLens 34.1 (in-progress, target 2026-08-19) will emit full-pipeline cost with `estimated: false`. Golden fixtures `sse-done-estimated-2026-08-05.json` and `sse-done-actual-2026-08-05.json` are in `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/` and covered by contract tests.

**Acceptance Criteria:**

**Given** the engine reports a real `costDollars` value in the terminal SSE event
**When** a deep-research call completes
**Then** the executor records a usage entry for the call with the call scope (workspace, user, thread) and the real cost
**And** the executor records `cost_basis`, `resolved_mode`, `model`, `tokens_total`, `tokens_prompt`, and `tokens_completion`
**And** the wallet is debited using that real cost.

**Given** the engine does not emit a cost (old version or error)
**When** the call completes
**Then** the executor falls back to a configured flat micros-per-call rate and logs a warning
**And** the flat billing unit is no longer treated as the source of truth.

**Given** real cost data exists
**When** querying aggregate usage
**Then** cost per call by mode and fallback rate are measurable, and the data feeds the usage dashboard when available.

**Given** the engine reports `costDollars` with `estimated: true`
**When** the call completes
**Then** the executor records `cost_basis = "estimated"` and does not treat the number as final for pricing decisions.

**Given** the engine reports `costDollars` with `estimated: false` (ChainLens 34.1)
**When** the call completes
**Then** the executor records `cost_basis = "actual"` and uses it for wallet debit and pricing analysis.

**Given** real cost data is not yet available
**When** someone proposes finalizing subscription pricing
**Then** the proposal is blocked until 9.2 and 8.7 provide real numbers.

_Implementation hints (not AC):_
- The current flat rate is `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` in `app/config/__init__.py`; it under-meters quality/deep modes 2.1–3.3×.
- Fields to update: parse `costDollars` from the terminal SSE event; write `TokenUsage.usage_type="deep_research"` with `workspace_id`/`user_id`/`thread_id`; debit wallet via `app/capabilities/core/billing.py`.
- Deprecate `BillingUnit.CHAINLENS_QUERY` as the source of truth.

_FR-37 · AD-8(amended) · AD-15 · SM-11a · OQ-7(3). Files: `app/capabilities/chainlens/research/executor.py`, `app/capabilities/core/billing.py`, `app/capabilities/core/types.py`, `app/services/token_tracking_service.py`._

### Story 9.3: Latency Budget & State A→B Gate  `(mới)`  `[DONE per sprint-status: 9-3]`
As a product owner,
I want đo latency deep-research **từ phía Nowing** và có đường async deliverable làm sàn,
So that không cược vào giả định latency theo chiều nào, và biết đúng lúc nào được bật sync chat-mode.

**Bối cảnh:** baseline ChainLens cuối (2026-07-18) FAIL (Ask 57–136s, quality 198s) **nhưng có thể stale** — `ADR-DEEP-RESEARCH-SPEED` phases 1-7 đã ship mà `20-0`/`20-8` chưa đo lại. Trạng thái đúng = **"chưa biết"**. Lộ trình giảm latency: ChainLens `43-1` (GATE 0) → `43-2` planner-DAG + `43-5` cache hit-rate. **Không** phụ thuộc owned index (Epic 26, `AD-DEFER-7`).

**Acceptance Criteria:**

**Given** deep research chạy qua Nowing
**When** hoàn tất hoặc fail
**Then** Nowing ghi p50/p95 latency **per mode** từ phía mình (SM-11b) + fallback rate (SM-11c) — không chờ engine tự báo.

> **✅ Thu hẹp theo `AD-17` (2026-07-25, giải readiness U-1/U-2).** **Cải chính:** hạ tầng async **đã có end-to-end** — `?mode=async` → 202 + `X-Run-Id`, SSE `GET .../runs/{id}/events`, ring buffer replay 500 event, cancel, history; và **web đã có typed client** (`scrapers-api.service.ts:68`). `chainlens.research` **đã nằm sau door đó**. ⇒ Story này **KHÔNG xây flow mới**, chỉ làm 3 việc còn thiếu thật (dưới) + đo lường + ngưỡng.
> **U-2 chốt:** delivery đi **SSE**; **KHÔNG** thêm `runs` vào `ZERO_PUBLICATION` (bảng log lớn, TTL 30 ngày, `output_text` JSONL — `AD-5` giữ nguyên phạm vi).

**Given** State A và async door đã tồn tại
**When** user/agent yêu cầu deep research
**Then** dùng **đúng door sẵn có** (`?mode=async` + SSE `runs/{id}/events`) — không tạo bảng job mới, không tạo endpoint progress mới.

**Given** `run_event_bus` hiện **single-process** (`events.py` tự ghi: *"a multi-worker deployment needs Redis pub/sub … behind this same interface"*)
**When** API chạy nhiều replica/worker
**Then** đặt **Redis pub/sub** sau **cùng interface** `run_event_bus` (Redis đã có cho Celery, `AD-4`); **không đổi call-site**
**And** có test: client tail SSE ở replica A **thấy được** event của run chạy ở replica B
**And** đây là **tiền đề trước khi bật deep-research async trên môi trường nhiều replica** — thiếu nó thì mất event **im lặng, không lỗi**.

**Given** agent door hiện **SYNC** (`app/capabilities/core/access/agent.py` gọi executor inline, không có `mode`)
**When** agent gọi deep research trong một chat turn
**Then** agent **submit rồi trả về** `run_id` + thông báo đang chạy; chat turn kết thúc, **không** chặn tới 300s
**And** đây là **phần khó nhất của story này** — transport đã xong, chỗ block nằm ở agent door.

**Given** `run.finished` chỉ là event trên bus (grep `Notification|notify` trong `rest.py`/`runs.py` = 0 hit) và kết quả nằm trong `runs.output_text` (TTL 30 ngày)
**When** một deep research hoàn tất
**Then** emit `Notification` (bảng `notifications` đã có ở `app/notifications/persistence.py` và **đã nằm trong `ZERO_PUBLICATION`** → realtime sẵn)
**And** nếu user yêu cầu, persist kết quả thành **deliverable hạng nhất**, không dựa vào TTL của `runs`.

**Given** mode default hiện là `quality` (D3: đổi sang `balanced`)
**When** apply đổi default
**Then** `balanced` là default; `quality` là opt-in tường minh (deep-research/deliverable request)
**And** validate chất lượng trên `nowing_evals`; nếu hồi quy đáng kể → revert `quality` và **ghi lại lý do**
**And** reversible qua env var.

**Given** `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` is off
**When** agent or REST requests deep research
**Then** `chainlens.research` is forced to async mode; sync requests are rejected or downgraded.

**Given** State B conditions are met
**When** enabling sync chat-mode
**Then** enable only behind `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED`, keep async path intact, and allow sync only for `speed`/`balanced` modes; `quality`/`deep-research`/`deep-reasoning` remain async-only.

**Given** ChainLens 34.1 full-pipeline cost telemetry (target 2026-08-19), a rerun of 29-5 with `deepseek-v3.2`, and a clean Nowing e2e benchmark
**When** p95 `balanced` latency is ≤ 30s and cost per mode is within 2× of PRD targets or async-only is documented
**Then** PO may ratify State B and flip the feature flag.

**Deliverable tài liệu (không phải AC — sửa readiness Q-5):** story này **xuất ra** một quyết định ngưỡng p95 + định nghĩa cổng A→B, ghi vào NFR-9. Trước đây điều này bị viết thành AC (*"Then định nghĩa ngưỡng cụ thể"*) → AC tự tham chiếu, không verify được. Ngưỡng vẫn phải đặt **sau** khi có baseline đo được (kỷ luật đúng: không đặt ngưỡng trước khi đo — đó là lỗi của NFR6 phía ChainLens); nhưng nó là *sản phẩm đầu ra*, không phải *tiêu chí nghiệm thu*.

> **✅ Cải chính U-3 (2026-07-25, sau khi verify code ChainLens — OQ-7 câu 4 đã RÚT).** Readiness ghi *"progress chỉ có 2 event, phải chờ engine emit thêm"*. **Sai.** ChainLens **đã emit progress từ trước**: `api.ts:414` (`requestAcceptedAt`, `firstProgressAt`) · `api.ts:1298` (`+evidenceReadyAt`) · `api.ts:221` (`+firstFactualChunkAt`) · `api.ts:1299` (`evidence_ready` kèm `sources`) · cộng `synthesizing`, `heartbeat`. **Parser Nowing bỏ hết** — `_parse_sse` chỉ dispatch 4 type (`error`/`done`/`block`/`updateBlock`), block chỉ đọc `text` + `source`. ⇒ **Không chờ ChainLens.** Đây là việc của story này.

**Given** ChainLens đã emit `{type:'progress', requestAcceptedAt, firstProgressAt, evidenceReadyAt?, firstFactualChunkAt?}`, `{type:'evidence_ready', sources}`, `{type:'synthesizing'}`
**When** Nowing parse SSE
**Then** map các event đó sang `emit_progress(phase, message)` để chúng chảy vào `run_event_bus` (`AD-17`) và tới UI
**And** UX progress-first có nội dung thật để hiển thị, không phải *"Researching…"* rồi đứng im vài phút
**And** `firstFactualChunkAt` dùng làm mốc TTFB đo được cho SM-11b.

**Given** parser hiện bỏ im lặng mọi `type` không biết
**When** thêm mapping
**Then** giữ nguyên tính **forgiving** — `type` lạ vẫn bỏ qua, không raise (để ChainLens ship event mới mà không làm vỡ Nowing).

_NFR-9 · **`AD-17`** · FR-24(mode default, D3) · SM-11b/c · AD-4 (Redis) · AD-5 (giữ nguyên — `runs` không vào Zero). Tiền đề UX: `ux-designs/` chỉ có scaffold rỗng → cần UX spec async/progress-first trước khi build UI deep-research._

### Story 9.4: Docs — Quan hệ Nowing ↔ ChainLens  `(mới)`  `[DONE — P1, README/docs/.env.example synced]`
As an OSS user / self-hoster,
I want docs nói rõ Nowing là sản phẩm, deep research là năng lực hosted, và Nowing dùng được mà không có nó,
So that tôi không cài xong mới phát hiện một tính năng vỡ.

> **⚠️ AC đã sửa 2026-07-25 theo D5.** Bản trước ghi *"docs hướng dẫn self-host chạy ChainLens hoặc chấp nhận degradation"* — **sai**: engine closed-source nên self-host **không thể chạy nó**. Docs phải nói deep research là **năng lực cloud** (Phase 1), không phải một biến môi trường cần cấu hình.

**Acceptance Criteria:**

**Given** README/`docs/` hiện pre-pivot và không nói gì về ranh giới
**When** sync
**Then** có mục **Nowing = sản phẩm** + **deep research chạy trên hosted engine của Nowing**
**And** gọi engine là *"Nowing's hosted deep-research engine"* — **KHÔNG** nêu tên ChainLens ở bất kỳ tài liệu công khai nào (NG-3, D5)
**And** nêu **non-goals** (NG-1 không bán research data / không owned index; NG-2 không parity consumer).

**Given** ranh giới OSS/Cloud (D5)
**When** người self-host đọc README
**Then** có **bảng feature self-host vs cloud** ghi thẳng: deep open-web research là năng lực cloud (Phase 1)
**And** `docker/` + `.env.example` nói rõ Nowing chạy đầy đủ **không cần** engine; nếu không cấu hình thì deep research trả `engine_unavailable` (FR-38)
**And** không có hướng dẫn nào ngụ ý self-host tự dựng được engine.

**Given** repo dùng dual-license (`AD-16`): Apache-2.0 cho core, **BSL 1.1** cho `nowing_backend/app/proprietary/**`
**When** viết README/landing/docs
**Then** **KHÔNG** gọi cả sản phẩm là "open source" — BSL tự tuyên bố không phải OSS; dùng *"Apache-2.0 core + BSL 1.1 crawler engine"*
**And** nói rõ BSL cho phép production use nhưng cấm bán lại dạng hosted/managed service — kể thẳng, không lấp liếm.

**Given** luật messaging ở `briefs/brief-Nowing-2026-07-25/brief.md` §7
**When** viết README/landing
**Then** copy tuân thủ bảng NÓI/KHÔNG NÓI: chỉ tiếng Anh · không gọi tên đối thủ · không dẫn bằng "citations" · không định vị VN/tiếng Việt · không nêu tên engine.

_OQ-6(mở rộng) · AR-10 · FR-38 · D5 · NG-1/2/3. Phối hợp với Story 8.10 (vision sync) — nên làm cùng một lượt. Nguồn copy: `briefs/brief-Nowing-2026-07-25/brief.md` §1, §5.1, §7, §8._

### Story 9.5: Metered Deep-Research Endpoint cho Self-Host  `(mới)`  `[POST-MVP — CHƯA PHÊ DUYỆT, đăng ký để không bị mất]`
As a self-hoster,
I want trả tiền theo call để dùng deep research trên bản self-host,
So that tôi không phải chuyển sang cloud chỉ vì một năng lực.

> **Trạng thái: deferred.** Đây là **Phase 2** của D5. Mở khi (a) có số self-host thật, và (b) story `9.2` cho số cost để định giá. Không build trước hai điều đó.

**Acceptance Criteria (nháp — cần SCP phê duyệt trước khi dev):**

**Given** Phase 2 được phê duyệt
**When** self-host gọi deep research
**Then** request đi theo đường `self-host Nowing → Nowing Cloud API (metered, key theo account) → engine (vẫn 1 service key)`
**And** **CẤM** `self-host → engine trực tiếp` — cách đó biến engine thành public multi-tenant SaaS có end-user auth, phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 và SCP v4 de-scope
**And** metering/quota/chống abuse nằm ở Nowing Cloud (tái dụng account + credit wallet, `AD-8`), không nằm ở engine.

**Given** self-host không có key Nowing Cloud
**When** gọi deep research
**Then** hành vi giữ nguyên như Phase 1 — `engine_unavailable`, không hard-fail (FR-38).

_D5 · AD-15 · AD-8 · FR-37/FR-38. **Đã loại (không mở lại mà không có SCP mới):** phát hành binary/Docker closed-source của engine._

> **✅ Gộp story 2026-08-05 (readiness fix):** `9.6a` và `9.6b` được gộp thành story 9.6 duy nhất — provenance recipe và re-validation API là hai nhóm AC trong cùng một story, không còn forward dependency.

### Story 9.6: Memory Provenance & Re-Validation  `(mới)`  `[DONE per sprint-status: 9-6]`
As an agent hoặc người dùng,
I want memories created from scraped data to be traceable and re-executable,
So that the system knows when a fact is stale instead of returning outdated information with a citation.

> **Đây là tiền đề của differentiator "memory có nguồn sống, tự re-validate"** — thứ phân biệt Nowing sau khi "memory có citation" thành table-stakes (5 bên ship trong 90 ngày, xem brief §4). Nền tảng đắt nhất **đã có**: `Run` lưu `capability` + `input` JSONB nên re-execute được chính xác. Chỉ bị chặn ở 3 chỗ nhỏ.

**Vấn đề (verified 2026-07-25):**
1. `Memory.source_id` = `Integer` (`db.py:2077`) vs `Run.id` = `UUID` (`db.py:3155`) → không lưu được link
2. Không có code nào ghi `MemorySourceType.SCRAPER_RUN` — enum khai báo ở `db.py:572` rồi bỏ đó
3. `RUNS_RETENTION_DAYS = 30` (`capabilities/core/runs.py:33`) → re-validate hỏng sau một tháng

> **✅ Quyết định kiến trúc đã chốt — `AD-11.1` (2026-07-25, giải readiness Q-2).** AC trước đây chứa *"chọn một trong hai, ghi lý do trong ADR"* → không testable, dev không biết verify gì. Nay đã chốt: **`Memory` tự chứa recipe**; **KHÔNG** dùng retention có điều kiện cho `runs`.

**Acceptance Criteria (provenance recipe):**

**Given** `Memory.source_id` là Integer (`db.py:2077`) vs `Run.id` = UUID (`db.py:3155`)
**When** thêm khả năng re-validate
**Then** `Memory` có **`source_capability`** (String), **`source_input`** (JSONB), **`source_run_id`** (UUID nullable, **không FK cứng** — `Run` được phép biến mất)
**And** `Memory.source_id` (Integer) **giữ nguyên** cho nguồn `document`/`chat_message` — không đổi kiểu cột đó
**And** có migration + test không hồi quy cho hai nguồn cũ.

**Given** auto-extract chạy trên một chat turn có kết quả scrape
**When** tạo memory từ đó
**Then** set `source_type = SCRAPER_RUN` + **sao chép** `capability` và `input` từ `Run` vào `Memory` + ghi `source_run_id`.

**Given** `RUNS_RETENTION_DAYS = 30` và cleanup cơ hội `_maybe_cleanup`
**When** `Run` bị xoá sau 30 ngày
**Then** memory tham chiếu nó **vẫn re-validate được** (đã có recipe riêng)
**And** cleanup `runs` **KHÔNG** được sửa thành có điều kiện — không join sang `memories`.

**Given** `source_input` là snapshot bất biến
**When** ai đó muốn đổi truy vấn
**Then** tạo memory mới, **không** mutate recipe cũ (mutate làm "re-validate" mất nghĩa).

**Acceptance Criteria (re-validation API):**

**Given** một memory có `source_capability` + `source_input`
**When** gọi `revalidate(memory_id)`
**Then** chạy lại capability với input đó → so sánh kết quả với `content`
**And** nếu khớp → cập nhật timestamp "last verified"; nếu lệch → hạ `confidence` **và** tạo `MemoryVersion` ghi lại thay đổi
**And** **không** tự động xoá memory cũ (giữ kỷ luật FR-34 — không xoá cứng).

**Given** memory nguồn `document`/`chat_message` (không có recipe)
**When** gọi `revalidate`
**Then** trả trạng thái tường minh "không re-validate được cho nguồn này", **không** lỗi 500.

**Given** re-validate gọi lại một capability có phí
**When** chạy
**Then** chi phí được meter như một capability call bình thường (`AD-8`) — không có đường tính phí ẩn.

**Given** `Run` gốc đã bị xoá sau 30 ngày
**When** gọi `revalidate`
**Then** vẫn chạy được (recipe nằm trong `Memory` theo `AD-11.1`)

_FR-39 · **`AD-11.1`** · FR-34 · AD-8. **Ưu tiên:** không chặn launch, nhưng **P0 nếu muốn kể câu chuyện re-validation** — xem brief §4, §8, §12 H-3._

---

## Epic 4: Chat & Agents

_Đã DONE: 4.5 MCP memory tools, 4.6 research continuity._
_Đã DONE 2026-08-04: 4.8a–4.8g chat response benchmark & regression gate (FR-42, NFR-10)._

### Story 4.7: Pointer-Based Tabs with Live Title Resolution  `(mới 2026-07-30)`  `[ready-for-dev]`
As a user with many open documents and chats,
I want tabs to be lightweight pointers that resolve titles from the live source,
So that tab state is fast to save/load and titles stay up to date without stale snapshots.

**Acceptance Criteria:**
**Given** a workspace with documents and chats open in tabs, **When** a document/chat title changes, **Then** the tab bar reflects the new title without a full refresh.
**Given** many tabs, **When** the app loads, **Then** tab state is small (pointer: entity id + kind) and titles are fetched via `useResolvedTabs`.
**And** tab state uses the v2 storage key; **And** fallback navigation works for pointer tabs.

**Kỹ thuật:** refactor `Tab` to pointer-only state, add `useResolvedTabs` hook, resolve document/chat title via Zero/`react-query`, render `TabBar` from resolved tabs.
_FR-14 · upstream PR #1609._

### Story 4.8a: Extend `NewChatClient` telemetry  `[done]`
As a benchmark runner, I want `NewChatClient` capture token usage, TTFB, turn id and finish status from `/api/v1/new_chat` SSE, so that `nowing_evals` can measure chat cost, latency and outcome per turn.
_AC:_ parse `data-token-usage`, `data-turn-info`; expose `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `ttfb_ms`, `turn_id`; pass to `ArmResult`.
_FR-42 · NFR-10 · `nowing_evals/core/clients/new_chat.py`._

### Story 4.8b: Chat Regression Benchmark Suite  `[done/review]`
As a release engineer, I want `nowing_evals run chat regression` over a representative query set, so that every deploy is checked for latency/cost/citation drift.
_AC:`nowing_evals run chat regression` ingests cases, runs per-tag (memory, document, deep-research, multi-tool, creative), reports p95 latency/TTFB, error rate, finish rate, citation count, cost/turn, and flags drift against baseline.
_FR-42 · NFR-10 · `nowing_evals/suites/chat/regression/`._

### Story 4.8c: Production query sampler + anonymizer  `[done]`
As an eval operator, I want to extract and anonymize real production queries for the benchmark dataset, so that regression tests reflect actual usage without leaking PII.
_AC: sampler reads production logs; strips PII (phone, email, IPs); outputs `gate.yaml` compatible dataset; opt-in per environment.
_FR-42 · NFR-10 · `market-*-production-query-sampler-research-2026-08-02.md`._

### Story 4.8d: Chat quality benchmark with LLM-as-judge  `[ready-for-dev]`
As an ML/QA engineer, I want `chat/quality` judge responses on groundedness, citation accuracy, and helpfulness, so that quality regressions are caught before deploy.
_AC: `nowing_evals run chat quality` judges each turn; reports aggregate score + per-tag breakdown; uses judge model separate from the tested model.
_FR-42 · `nowing_evals/suites/chat/quality/`._

### Story 4.8e: CI / deploy gate for chat regression  `[done]`
As a release engineer, I want CI block deploy if `chat/regression` drifts beyond ratified baseline, so that bad changes do not reach production.
_AC: CI workflow runs `nowing_evals run chat regression`; fails on unratified drift; sends Slack/Telegram notification; supports `--fail-on-unratified`.
_NFR-10 · `gate.yaml` · CI workflow._

### Story 4.8f: Benchmark stability — scrape, CAPTCHA, rate-limit, multi-turn  `[done]`
As a release engineer, I want the benchmark robust against live web variance, so that flaky external factors do not mask real regressions.
_AC: operational metrics per run; multi-turn thread reuse; scrape drop-rate gating; error classification; CAPTCHA/rate-limit handling.
_FR-42 · NFR-10 · `nowing_evals` runner._

### Story 4.8g: Benchmark mode/tier matrix and local vs production parity  `[done]`
As a release engineer, I want benchmark matrix cover speed/balanced/quality/auto modes and local vs prod parity, so that cost/latency claims are validated across configurations.
_AC: per-mode aggregation (p50/p95/p99); resolved-mode bucket divergence fixed; local/prod comparison report; `one_case_per_tag` fixed.
_FR-42 · NFR-10 · `report-per-mode.md`._

### Story 4.8h: Mode-Aware Chat Policy for Latency/Cost  `(mới 2026-08-05)`  `[done]`
As a user,
I want `new_chat` to respect the requested `mode` (speed/balanced/quality/auto) when selecting tools, retrieval depth, and escalation to deep research,
So that `chat/regression` passes latency, TTFB, and cost gates without losing answer quality.

**Acceptance Criteria:**
**Given** `mode=speed` and a question about an uploaded document, **When** the agent runs, **Then** it performs a minimal knowledge-base search, does not use heavy research or web tools, and answers within the speed-mode latency gate.
**Given** `mode=balanced` with a mentioned document, **When** the agent runs, **Then** it uses a moderate number of knowledge-base calls and tool calls, does not escalate to deep research, and `chat/regression` p95 cost stays under the balanced-mode budget.
**Given** `mode=quality` and no document is mentioned, **When** the first knowledge-base search returns no relevant hits, **Then** the agent may call deep research for web/deep research.
**Given** `mode=auto` and a single-document question, **When** the agent has made a configured number of tool calls, **Then** a tool-call budget forces it to answer.
**And** `chat/regression` with the large-doc dataset passes all p95 latency, TTFB, and cost gates; `chat/quality` still passes correctness/citation/completeness.

_Implementation hints (not AC):_ system prompt per mode + tool availability filter + tool-call budget middleware + `search_knowledge_base` `top_k`/`max_passages` clamp. For `mode=speed`, clamp to `top_k=1, max_passages=4`, no `task`/deep research/web tools, target ≤15s. For `mode=balanced`, allow at most two KB calls and one `task`, no deep research, p95 cost ≤100k micros. For `mode=auto`, force answer after 5 tool calls. Detailed spec: `@doc/specs/2026-08-05/new-chat-mode-aware-latency-cost-policy`.
_FR-42 · NFR-10 · `sprint-change-proposal-2026-08-05-chat-mode-policy.md`._

---

## Epic 7: Multi-surface Clients

_Đã DONE: 7.1 web, 7.2 desktop, 7.3 browser extension, 7.5 Obsidian, 7.6 MCP server._

### Story 7.4: Dedicated Connectors Layout  `(mới 2026-07-30)`  `[ready-for-dev]`
As a workspace member,
I want a dedicated page (not a modal) for managing connectors,
So that I can search, group, view health, and connect new data sources in a focused UI.

**Acceptance Criteria:**
**Given** I open workspace settings, **When** I click "Connectors", **Then** I navigate to a dedicated route with a sidebar panel and a searchable grid/list of connectors.
**Given** the connectors page, **When** I view a connector, **Then** I see its type, health, indexing state, and grouped rows by category.
**And** the layout supports live connectors without a saved config; **And** the MCP icon masks `currentColor`.

**Kỹ thuật:** add `/connectors` route, build `useConnectorRows` hook, group connectors by type, add mobile drawer for adding connectors.
_FR-25 · FR-7/8 · upstream PR #1624._

### Story 7.7: MCP Server Tool Expansion  `(mới 2026-08-05)`  `[ready-for-dev]`  `[backfill]`

As an AI agent builder,
I want to drive Nowing's full backend surface — memory, team memory, image generation, BĐS platforms, automations, reports — through Nowing's own MCP server,
So that agents can operate the research workspace end-to-end without the web UI.

**Acceptance Criteria:**
**Given** the MCP server has registered `features/memory`, **When** an agent calls `nowing_memory_list` / `nowing_memory_revalidate`, **Then** it lists workspace memories newest-first and revalidates a memory against its source, preserving previous versions.
**Given** workspace team memory exists, **When** an agent calls `nowing_workspace_memory_get` / `nowing_workspace_memory_update`, **Then** it reads/writes `GET/PUT /workspaces/{id}/memory`.
**Given** an agent wants an image, **When** it calls `nowing_image_generate(prompt)`, **Then** it triggers `POST /image-generations`.
**Given** the scrapers module, **When** an agent calls `nowing_chotot_bds_scrape` / `nowing_muaban_bds_scrape`, **Then** it returns typed BĐS listings via the shared `run_scraper` capability.
**Given** workspace automations, **When** an agent calls `nowing_automation_list`, **Then** it lists automations from `GET /automations`.
**Given** workspace reports, **When** an agent calls `nowing_report_list` / `nowing_report_export`, **Then** it lists reports and exports in 7 formats (text decoded, binary base64 + decode hint).
**Given** `app/mcp_tools.py` and `selfcheck.py`, **When** 11 tools are added, **Then** the catalog adds `TEAM_MEMORY`/`IMAGE_GENERATION`/`AUTOMATION`/`REPORT` groups and selfcheck reports 42 tools.
**And** (pending Slice 4–5) `nowing_chat` (SSE buffered) and `nowing_automation_run`.

**Kỹ thuật (backfill):** Slice 0–3 đã implement + verified (selfcheck 42 tools, MCP suite 83 passed, ruff clean); Slice 4–5 còn pending chờ `bmad-dev-story`. Khác biệt với FR-8 (External MCP Connectors — Nowing tiêu thụ MCP third-party): story này là MCP server của Nowing (FR-29).
_FR-29 · FR-21/23 · FR-18/19/20 · FR-32/33/34 · AD-7 · story file `7-7-mcp-server-tool-expansion.md`._

---

## Epic 10: Connector & Scraper Expansion

_Tạo 2026-08-03 để chứa các scraper/capability mới ngoài phạm vi epic cũ._

### Story 10.1: Batdongsan.com.vn Scraper  `[DONE per sprint-status: 10-1]`

As a real-estate researcher or investor in Vietnam,
I want to scrape property listings from batdongsan.com.vn,
So that I can track market trends, prices, supply, and locations in my workspace.

**Acceptance Criteria:**
**Given** a valid batdongsan.com.vn mobile API request, **When** the scraper receives an obfuscated response, **Then** it decodes the response into a typed listing list with standard fields (`listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `phone`, `phone_display`).

**Given** a listing detail page with authenticated cookies, **When** the scraper fetches the phone number, **Then** it returns the full `phone` number and keeps the session valid for the token lifetime.

**Given** a scraping job, **When** pagination, `max_pages`/`max_items`, or a 0.5s/proxy rate limit is applied, **Then** the system respects those limits and returns results without hard-failing.

**Given** the upstream API returns an unexpected shape, rate limit, or decode error, **When** the scraper handles it, **Then** it returns `degraded=true` with a clear reason and does not crash.

**Given** a listing is successfully scraped, **When** billing is recorded, **Then** each listing is billed via the appropriate usage unit and the capability is exposed through REST, agent, and MCP interfaces.

**Given** an admin user pastes JSON cookies on the scraper-accounts page, **When** the system processes them, **Then** it extracts the bearer token automatically, persists the account, and supports session renewal capture.

_Implementation hints (not AC):_ Decode pipeline is `gzip → base64 → nibble-swap → Latin-1 JSON`. Phone unmask uses `AsyncStealthySession` + `DecryptPhone` XHR and pre-warms `/dang-nhap` before `con.ses.id` expires. Billing unit is `BATDONGSAN_ITEM`. Session capture can use `scripts/capture_batdongsan_session.py` with CDP or headed Playwright. Add `app/proprietary/platforms/batdongsan/` (BSL 1.1) for fetcher/parser and `app/capabilities/batdongsan/scrape/` (Apache-2.0) for capability/executor/definition, following the `reddit.scrape` pattern.

_FR-6 · AD-3 · AD-16 · AD-19 · `technical-batdongsan-scraper-research-2026-08-02.md`._

### Story 10.2: Chotot.vn / Nhà Tốt Scraper  `[done]`

As a real-estate researcher or investor in Vietnam,
I want to scrape property listings from `chotot.com` (Nhà Tốt),
So that I can cross-compare classified listings with batdongsan.com.vn and identify real market prices.

**Acceptance Criteria:**
**Given** a Chotot Nhà Tốt category URL (`nha-dat`, `ban-can-ho`, `ban-nha-rieng`, `cho-thue`), **When** the scraper runs, **Then** it returns a typed listing list with `listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.

**Given** a JS-rendered page or anti-bot challenge, **When** the scraper encounters it, **Then** it uses a headless browser, retries with proxy rotation on block, and returns `degraded=true` with reason on CAPTCHA or layout change without hard-failing.

**Given** a scraping job with pagination settings, **When** `max_pages`/`max_items` or a 1s/proxy rate limit is configured, **Then** the system respects those limits and returns results.

**Given** a listing is successfully scraped, **When** billing is recorded, **Then** each listing is billed via `CHOTOT_BDS_ITEM` and the capability is exposed through REST, agent, and MCP interfaces.

**Kỹ thuật (không phải AC):** thêm `app/proprietary/platforms/chotot/` (BSL 1.1) cho fetcher/parser và `app/capabilities/chotot/scrape/` (Apache-2.0) cho capability/executor/definition, theo pattern `reddit.scrape`.

_FR-6 · AD-3 · AD-16 · AD-19 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

### Story 10.3: Muaban.net BĐS Scraper  `[done]`

As a real-estate researcher or investor in Vietnam,
I want to scrape property listings from `muaban.net` (mục BĐS),
So that I can broaden cross-compare coverage beyond batdongsan and chotot.

**Acceptance Criteria:**
**Given** a Muaban BĐS category URL (`nha-dat` bán/cho thuê, căn hộ, nhà riêng, đất), **When** the scraper runs, **Then** it returns a typed listing list with `listing_id`, `title`, `price`, `area`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.

**Given** sub-category and region pagination, **When** the scraper paginates, **Then** it handles sub-category + region pages and reuses anti-bot patterns from the chotot scraper where applicable.

**Given** a scraping job with pagination settings, **When** `max_pages`/`max_items` or a 1s/proxy rate limit is configured, **Then** the system respects those limits and returns results.

**Given** an upstream block, layout change, or decode error, **When** the scraper handles it, **Then** it returns `degraded=true` with a clear reason and does not hard-fail.

**Given** a listing is successfully scraped, **When** billing is recorded, **Then** each listing is billed via `MUABAN_BDS_ITEM` and the capability is exposed through REST, agent, and MCP interfaces.

**Kỹ thuật (không phải AC):** thêm `app/proprietary/platforms/muaban/` (BSL 1.1) cho fetcher/parser và `app/capabilities/muaban/scrape/` (Apache-2.0) cho capability/executor/definition.

_FR-6 · AD-3 · AD-16 · AD-19 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

### Story 10.4: Vietnam BĐS Listing Aggregator & Cross-Source Trust Score  `[DONE per sprint-status: 10-4]`

As a real-estate researcher,
I want the system to merge and score listings from multiple Vietnamese BĐS sources,
So that I can trust the price and detect fake/duplicate listings.

**Acceptance Criteria:**
**Given** listings from `batdongsan`, `chotot`, `muaban` and future P1/P2 sources, **When** the aggregator runs, **Then** it normalizes them into a common schema.

**Given** a group of normalized listings for the same property, **When** the aggregator computes `confidence_score`, **Then** the score reflects source authority, number of matching sources, `post_date`, and price similarity.

**Given** two listings with the same address or title but price difference greater than 20%, **When** the aggregator compares them, **Then** it flags a conflict for review.

**Given** duplicate listings across sources, **When** the aggregator deduplicates, **Then** it matches by phone, normalized address, or image hash and keeps a single merged record with provenance.

**Given** aggregated listing data, **When** a user or agent queries via REST or MCP, **Then** the system supports filtering by location, price range, and source.

**Kỹ thuật (không phải AC):** thêm `app/services/bds_aggregator/` hoặc mở rộng `Memory`/`ResearchThread` để lưu aggregated listing với provenance.

_FR-6 · FR-32 · FR-39 · AD-11.1 · `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`._

---

## Epic 11: Telegram Automation & Bot `[done]`

_Tạo 2026-08-03 để mở rộng gateway Telegram hiện có thành automation notification channel, write-back action, và bot tương tác._

**FRs:** FR-TELE-1 (automation run notification), FR-TELE-2 (notification preference), FR-TELE-3 (`write_back_telegram`), FR-TELE-4 (inline keyboard), FR-TELE-5 (bot commands), FR-TELE-6 (UI builder + settings), FR-TELE-7 (rate limit & error handling). **NFRs:** NFR-TELE-1 (async), NFR-TELE-2 (rate limit), NFR-TELE-3 (token encryption), NFR-TELE-4 (4096-char limit), NFR-TELE-5 (webhook/longpoll). **Governed by:** `AD-15` (gateway là shared dependency), `AD-16` (license), `AD-19` (anti-bot/escalation async).

> **🆕 2026-08-03 — Epic 11** là epic *mới thật* dựa trên request PO; reuse `app/gateway/telegram/` đã có (`TelegramClient`, `TelegramAdapter`, `TelegramStreamTranslator`, `TelegramGatewayCommands`). Không xây gateway từ đầu. Crypto `market_data` pending sau Telegram.

### Story 11.1: Telegram Notification Foundation `[done]`

As a user,
I want to enable or disable Telegram notifications for automation runs and receive a clear message with a deep link when a run completes or fails,
So that I can control whether Nowing messages me on Telegram and quickly review results without keeping the dashboard open.

**Acceptance Criteria:**
**Given** a user has an active `ExternalChatBinding` for Telegram, **When** they open User Settings, **Then** a Telegram notification toggle is visible.

**Given** the Telegram notification toggle, **When** a user turns it on or off, **Then** the preference persists immediately; off stops future Telegram notifications but still creates an in-app `Notification`.

**Given** an `AutomationRun` reaches `succeeded` or `failed`, **When** the run completes, **Then** the system creates an in-app `Notification` of type `automation_run_complete`.

**Given** the user has an active Telegram binding and the preference is enabled, **When** an `AutomationRun` completes, **Then** a Telegram message is sent within 30 seconds; if no binding or the preference is off, only the in-app notification is created.

**Given** a Telegram completion message, **When** it is generated, **Then** success messages start with `✅ Automation '<name>' finished successfully`, failure messages start with `❌ Automation '<name>' failed` and include the first error line, the automation name is bold, the status is highlighted, and a deep link to `/dashboard/{workspace_id}/automations/{automation_id}/runs/{run_id}` is included.

**Given** a long completion message, **When** it exceeds 4096 UTF-16 units, **Then** it is split into multiple parts with a summary and link in the first part, and `RetryAfter` is handled; delivery failure does not fail the automation run.

**Kỹ thuật (không phải AC):** Alembic migration thêm `notification_preferences` JSONB vào `User` (hoặc bảng riêng) (`AD-2`); endpoint `PATCH /api/v1/users/me/notification-preferences`; UI toggle trong `MessagingChannelsContent`; hook vào `app/automations/runtime/executor.py` sau `mark_succeeded`/`mark_failed`; dispatch gửi Telegram qua Celery task; reuse `NotificationService` + `TelegramAdapter` + `chunk_message` và rate-limit.

### Story 11.2: Telegram Write-Back, Builder UI & Chat Resolution `[done]`

As an automation builder,
I want a "Send Telegram message" action that authors a custom message and automatically resolves the right bot and chat,
So that I can push results or alerts to Telegram without writing JSON or looking up chat IDs.

**Acceptance Criteria:**
**Given** the automation builder adds a "Send Telegram message" action, **When** the action is configured, **Then** it is registered as `write_back_telegram` with params `text`, optional `chat_id`, `parse_mode` (default `Markdown`), `reply_markup`, optional `account_id`, and `use_system_bot` (default `true`).

**Given** an action with `use_system_bot=true` and no `account_id`, **When** the step runs, **Then** it uses the system bot; if `use_system_bot=false` and `account_id` is missing, the step fails with a clear error.

**Given** a resolved bot account, **When** the step needs a default `chat_id`, **Then** it resolves from the automation creator's active `ExternalChatBinding` for that account; it fails clearly if no binding and no explicit `chat_id` are provided.

**Given** a message with invalid Markdown or malformed `reply_markup`, **When** the step sends it, **Then** it falls back to plain text or no keyboard, and the run continues based on `on_failure` config.

**Given** a missing bot token or chat ID, **When** the step runs, **Then** it fails with a clear error and the automation run continues according to `on_failure`.

**Given** the builder action list, **When** a user selects "Send Telegram message", **Then** the UI shows fields for text, chat ID hint, and parse mode; the action serializes as `write_back_telegram` / `writeBackParams` provider `telegram`.

**Kỹ thuật (không phải AC):** package `app/automations/actions/builtin/write_back_telegram/` (`definition.py`, `params.py`, `factory.py`, `invoke.py`); reuse `TelegramAdapter`; mở rộng `nowing_web/lib/automations/builder-schema.ts` và `app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`.

### Story 11.3: Telegram Interactive Bot & Commands `[done]`

As a Telegram user,
I want inline keyboards and `/status`, `/run` commands so I can view runs and trigger automations directly from the chat,
So that I can take action without opening the dashboard.

**Acceptance Criteria:**
**Given** a bot message with an `inline_keyboard` in `reply_markup`, **When** `TelegramClient.send_message` or `edit_message` is called, **Then** `url` buttons open the URL and `callback_data` buttons trigger a `callback_query`.

**Given** a malformed `reply_markup`, **When** the bot sends or edits a message, **Then** it falls back to a message without keyboard and logs a warning.

**Given** an inbound `callback_query` or `inline_message_id`, **When** `TelegramAdapter.parse_inbound` processes it, **Then** the callback is persisted and dispatched by `inbox_processor`.

**Given** a `view_run:` callback, **When** it is dispatched, **Then** the bot fetches run details and edits or sends a message with the run status.

**Given** a `rerun:` callback, **When** it is dispatched, **Then** the bot triggers the automation and replies with a confirmation.

**Given** any callback query, **When** the bot finishes handling it, **Then** it calls `answerCallbackQuery` to remove the loading spinner.

**Given** a user sends `/status`, **When** the bot checks `Permission.AUTOMATIONS_READ`, **Then** it returns the latest run or "No recent runs".

**Given** a user sends `/run <name>`, **When** the bot checks `Permission.AUTOMATIONS_EXECUTE`, **Then** it triggers the automation and replies "Run started..."; if the name is missing it lists available automations; if the automation does not exist it replies "Automation '<name>' not found".

**Given** an inbound command or callback, **When** the bot resolves workspace context, **Then** it respects workspace visibility, permissions, and unpaired onboarding state.

**Kỹ thuật (không phải AC):** `TelegramClient` methods `answer_callback_query`, `edit_message_reply_markup`; `TelegramAdapter.edit_message` handles `inline:` peer prefix; `inbox_processor` callback dispatch; `app/gateway/telegram/commands.py` handlers; transient `AutomationTrigger(type=MANUAL)` + `launch_run`.

---

## Epic 12: HR/Recruitment Vertical — Vietnam Job Market Pilot

_Tạo 2026-08-05 để chạy 8-week pilot kết nối VietnamWorks, TopCV, ITviec và cung cấp `vn_jobs.aggregate` cho nghiên cứu thị trường tuyển dụng Việt Nam._

**FRs:** FR-43 (`vietnamworks.scrape`), FR-44 (`topcv.scrape`), FR-45 (`itviec.scrape`), FR-46 (`vn_jobs.aggregate`), FR-47 (PII redaction). **NFRs:** NFR-11 (ToS/anti-bot/PII). **OQ-8.** **SM-12.**
**Stories:** 12.0 (ToS/Legal Review), 12.1–12.5.

> **Pilot scope (Plan C):** P0 = cả 3 nguồn. Hard gates: ToS review cho 3 nguồn; legal counsel opinion; anti-bot POC cho TopCV; SCP về NG-1. Effort ước tính 18–24 dev-days. Go/No-Go sau 8 tuần beta 20–50 workspaces.

### Story 12.0: ToS & Legal Review `[proposed P0]`

As a product owner,
I want to confirm ToS and legal classification for VietnamWorks, TopCV, and ITviec,
So that we do not build or launch a non-compliant pilot.

**Acceptance Criteria:**
- **Given** the source list, **When** ToS review is performed, **Then** each source's automated access / commercial use status is documented in `_bmad-output/planning-artifacts/legal/`.
- **Given** the pilot design, **When** legal counsel reviews, **Then** an opinion exists confirming Nowing is not classified as an "employment service provider" / "môi giới việc làm".
- **Given** a source is blocked by ToS or legal, **When** the decision is made, **Then** that source is removed from the default `sources` list and the implementation plan is updated.
- **Given** legal approval, **When** the pilot launches, **Then** public messaging clearly positions Nowing as a research/memory layer, not a job board/ATS/intermediary.

_Kỹ thuật (không phải AC):_ No code. Output: legal review memo + ToS decision log.

_FR-43..FR-47 · NFR-11 · OQ-8 · AD-26_

### Story 12.1: VietnamWorks Scraper `[proposed P0]`

As a recruiter or market researcher,
I want to search VietnamWorks job postings via the public API,
So that I can source live job data into my Nowing workspace.

**Acceptance Criteria:**
- **Given** a query + optional city filter, **When** `vietnamworks.scrape` runs, **Then** it calls `POST https://ms.vietnamworks.com/job-search/v1.0/search` no-auth and returns typed `JobItem`.
- **Given** the response, **When** parsed, **Then** it maps: `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `salaryCurrency`, `salaryPeriodId`, `jobDescription`, `jobRequirement`, `jobFunction`, `yearsOfExperience`, `createdOn`, `approvedOn`, `typeWorkingId`, `expiredOn`, `isActive`.
- **Given** pagination, **When** `hitsPerPage` (max 100) and `page` are set, **Then** the scraper iterates correctly and respects rate-limit (429) with backoff and circuit-breaker.
- **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.VIETNAMWORKS_JOB`), capability registry, MCP, and REST routes.
- **Given** upstream schema changes, **When** detected, **Then** golden fixture regression tests fail before deployment.

_Kỹ thuật (không phải AC):_ `app/capabilities/vietnamworks/scrape/` (Apache-2.0 executor/definition/schemas) + `app/proprietary/platforms/vietnamworks/` (BSL 1.1 fetcher nếu cần HTML fallback). ToS review là hard gate.

_FR-43 · AD-3 · AD-16 · `technical-spike-vietnamworks-api-2026-08-05.md`._

### Story 12.2: TopCV Scraper `[proposed P0]`

As a recruiter,
I want to search TopCV job postings,
So that I can access the largest local Vietnamese job board.

**Acceptance Criteria:**
- **Given** a query + optional city filter, **When** `topcv.scrape` runs, **Then** it fetches TopCV search and detail pages.
- **Given** a Cloudflare/anti-bot challenge, **When** encountered, **Then** the scraper uses warmed browser/headless/proxy and returns `degraded=true` with reason on block.
- **Given** a successful fetch, **When** parsed, **Then** it returns typed `JobItem` with title, company, location, salary (if visible), JD, requirements, skills, post date.
- **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.TOPCV_JOB`), capability registry, MCP, and REST routes.

_Kỹ thuật (không phải AC):_ `app/proprietary/platforms/topcv/` (BSL 1.1 fetcher/parser/anti-bot) + `app/capabilities/topcv/scrape/` (Apache-2.0 capability). Anti-bot POC là hard gate; không merge trước khi POC pass.

_FR-44 · AD-3 · AD-16 · AD-19 · `technical-spike-topcv-itviec-2026-08-05.md`._

### Story 12.3: ITviec Scraper `[proposed P0]`

As a tech recruiter,
I want to search ITviec job postings,
So that I can monitor IT/AI hiring trends.

**Acceptance Criteria:**
- **Given** a query, **When** `itviec.scrape` runs, **Then** it fetches `https://itviec.com/it-jobs/{query}` (server-rendered HTML, no CAPTCHA in spike).
- **Given** the list page, **When** parsed, **Then** it extracts 20 job cards per page via selectors `job-card ipt-2`, `h3/a`, `employer-name`.
- **Given** a detail page, **When** parsed, **Then** it extracts title, company, location, work mode, posted time, skills, job domain, JD.
- **Given** salary is hidden, **When** displayed as `Sign in to view salary`, **Then** salary is parsed from title when possible or marked low-confidence.
- **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.ITVIEC_JOB`), capability registry, MCP, and REST routes.

_Kỹ thuật (không phải AC):_ `app/proprietary/platforms/itviec/` (BSL 1.1 fetcher/parser) + `app/capabilities/itviec/scrape/` (Apache-2.0 capability). Rate-limit + user-agent rotation + circuit-breaker.

_FR-45 · AD-3 · AD-16 · `technical-spike-topcv-itviec-2026-08-05.md`._

### Story 12.4: Vietnam Job Aggregator `[proposed P0]`

As a research analyst,
I want to query Vietnamese job data in one call,
So that I get a normalized, deduped, confidence-scored view of the job market from multiple sources.

**Acceptance Criteria:**
- **Given** a query, **When** `vn_jobs.aggregate` is called, **Then** it fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` (default all 3; source list configurable).
- **Given** results from multiple sources, **When** normalized, **Then** they map to `VnJobAggregatedListing` with salary/location/employment-type/experience.
- **Given** normalized listings, **When** deduplicated, **Then** it matches by company + title + location + posted_at across sources.
- **Given** conflicting salary/location between sources, **When** compared, **Then** it flags conflict and computes `confidence_score` + `salary_consistency_score`.
- **Given** a source fails, **When** aggregation completes, **Then** it returns `degraded=true` with `degradation_reasons`.
- **Given** the aggregator is built, **When** exposed, **Then** it is available via REST, MCP (`nowing_vn_jobs_aggregate`), and chat agent.

_Kỹ thuật (không phải AC):_ `app/services/jobs_aggregator/` (Apache-2.0, copy-modify from `bds_aggregator`). Location filter at aggregator level; PII redaction before memory.

_FR-46 · FR-32 · FR-39 · AD-11.1 · `pilot-plan-c-memo-2026-08-05.md`._

### Story 12.5: PII Redaction for Job Data `[proposed P0]`

As a workspace owner,
I want job postings to be scanned for personal information before storage,
So that Nowing does not accidentally retain candidate PII.

**Acceptance Criteria:**
- **Given** `job_description` / `job_requirement` from any source, **When** PII redaction runs, **Then** it detects Vietnamese phone numbers and email addresses via regex.
- **Given** person names in JD text, **When** detected, **Then** it flags via NER/heuristic and masks or drops the field.
- **Given** detected PII, **When** logged, **Then** only counts are recorded (no values).
- **Given** redaction runs, **When** storing to memory, **Then** the full raw JD is not stored unredacted.

_Kỹ thuật (không phải AC):_ Shared PII pipeline in `app/services/pii/` or inside jobs aggregator. Unit tests for representative samples from VietnamWorks, TopCV, ITviec.

_FR-47 · NFR-11 · OQ-3 · `feature-brief-hr-vertical-vietnam-2026-08-05.md`._
---

## Epic 13: Canonical Entity Storage & Multi-Domain Indexing

Hệ thống lưu trữ, dedup và index entities từ nhiều nguồn — tra cứu nhanh, giữ được provenance, cô lập tenant ở tầng database và mở rộng cho nhiều domain mà chưa cần dựng matching engine chung quá sớm.

**FRs covered:** FR-48 (canonical entity search & indexing), FR-46 (extend `vn_jobs.aggregate`)
**ADs governed:** AD-27 (canonical entity convention), AD-28 (unified engine trigger), inherits AD-24, AD-14, AD-2, AD-25

> **Scope reduced 2026-08-06 (Party Mode review):** Existing aggregators (`bds_aggregator`, `jobs_aggregator`) already implement matching/dedupe. Epic 13 adds a shared persistence, lineage and search layer; it does not replace domain matching logic.
>
> **Architect hardening 2026-08-06:** Shared canonical storage is established by Story 13.1 before the AD-28 trigger. AD-28 controls when standalone domain functions are wrapped behind one `DomainPlugin` matching engine; it does not delay the shared tables. All persistence is tenant-scoped, idempotent and retryable. Search extends the existing rank-based RRF path rather than mixing incomparable raw cosine and full-text scores.
>
> **Sequencing:** Epic 12 must ship before Jobs persistence and the HR benchmark. Story 13.1 and BDS contract work may run in parallel. Story 13.3 starts only after source lineage and RLS gates are green.

### Story 13.1: Canonical Persistence, Tenancy & Convention `[P0]`

As a developer,
I want a canonical persistence contract with database-enforced tenancy and explicit source lineage,
So that every domain can persist and search merged entities safely without inventing a new matching engine.

**Acceptance Criteria:**
- **Given** the migration runs, **When** complete, **Then** it creates `canonical_entities`, `canonical_entity_sources`, `canonical_merge_history`, and `canonical_persist_outbox` with Alembic-owned indexes and downgrade support for a database that has not accepted production writes.
- **Given** `canonical_entities`, **Then** each row stores: `id` (UUID PK), `workspace_id` (Integer FK), `entity_type` (String), `canonical_title` (String), `canonical_data` (JSONB), `fingerprint` (String), `search_text` (Text), `source_count` (Integer), `confidence_score` (Float), `conflict_flags` (JSONB), `version` (Integer), `first_seen_at`, `last_seen_at`, `embedding` (Vector), `embedding_model_name`, `embedding_content_hash`, and `embedding_status` (`pending`/`ready`/`failed`).
- **Given** two domains can produce the same fingerprint text, **Then** the database unique constraint and every upsert target are exactly `(workspace_id, entity_type, fingerprint)`.
- **Given** provenance is required by search, review and revert flows, **Then** `canonical_entity_sources` stores `workspace_id`, `canonical_entity_id`, `source_name`, `source_record_id`, redacted source snapshot, source URL, source timestamps and source fingerprint, with a domain-safe uniqueness constraint.
- **Given** concurrent merge/revert is possible, **Then** writes use `version` for compare-and-swap or an equivalent row lock; no update may silently overwrite a later entity version.
- **Given** the application uses pooled SQLAlchemy sessions, **Then** every API request and Celery task opens a transaction and executes `SET LOCAL app.workspace_id = :workspace_id` before canonical reads/writes; the workspace ID is passed explicitly in task payloads and never inferred from process-global state.
- **Given** database RLS is the isolation boundary, **Then** all four tables use `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and policies based on `current_setting('app.workspace_id', true)`; the application role is non-owner and `NOBYPASSRLS`, while the unset/invalid workspace context fails closed.
- **Given** BDS currently has a context-free capability executor, **When** it becomes persistent, **Then** `vn_bds.aggregate` accepts the execution context/workspace explicitly before any write path is enabled. Jobs follows the same contract.
- **Given** AD-27, **Then** BDS and Jobs expose `fingerprint()`, `merge()`, and `search_text()` through the documented domain module boundary while reusing their current dedupe behavior.
- **Given** a canonical row is created or its `search_text` changes, **Then** commit succeeds with `embedding_status='pending'`; an idempotent Celery task keyed by `(entity_id, version, embedding_model_name)` populates the embedding only if the entity version still matches.
- **Given** search/review UI requires real-time state, **Then** the minimal non-PII columns for canonical entities, source links and merge history are added to `ZERO_PUBLICATION`; bulky snapshots remain REST-fetched.

**Validation:**
- Backend convention tests cover both domains and the exact module signatures.
- Migration tests verify upgrade, clean downgrade-before-writes, constraints and required indexes.
- Raw SQL tests run as the real non-owner application role and prove cross-workspace reads/writes, missing context and pooled-connection reuse fail closed.
- Celery tests prove workspace propagation, idempotent embedding backfill and stale-version protection.

_AD-27 · AD-28 clarified above · AD-2 (pgvector) · Inherits AD-24 pattern._

### Story 13.2: Persist Aggregator Output to Canonical Storage `[P0]`

As a user,
I want aggregator results persisted with provenance and reversible history,
So that search survives the originating request and merge decisions remain auditable.

> Story 13.2 is implemented as five independently shippable sub-stories. A note alone is not a split: each item below has its own dependency and acceptance gate.

#### Story 13.2a: BDS Persistence & Retry `[P0]`

- **Dependency:** Story 13.1; may run before Epic 12.
- **Given** `vn_bds.aggregate` completes, **When** results are returned, **Then** the capability passes `workspace_id` through its execution context and idempotently upserts `canonical_entities` on `(workspace_id, entity_type, fingerprint)`.
- **Given** a source contributes to an entity, **Then** its redacted provenance is upserted into `canonical_entity_sources`; `source_count` is derived from distinct linked sources, not trusted from request payloads.
- **Given** persistence fails, **Then** aggregation still returns results with `persistence_status`, while a durable outbox/retry record preserves the workspace, idempotency key and payload reference; retries cannot create duplicate entities or source links, and terminal failure emits a metric/alert.

#### Story 13.2b: Jobs Persistence & Retry `[P0]`

- **Dependency:** Story 13.1 and Epic 12 aggregator output contract.
- **Given** `vn_jobs.aggregate` completes, **Then** it uses the same tenant, idempotency, source-link and outbox contract as BDS without replacing its existing Jobs dedupe key.
- **Given** partial source failure, **Then** successful source results are persisted, failed sources remain visible in degradation metadata, and later retry can add missing source links without rewriting unrelated fields.

#### Story 13.2c: Merge History, Conflict Resolution & Revert `[P0]`

- **Dependency:** Stories 13.2a or 13.2b can supply the first persisted entity.
- **Given** a merge, manual resolution, split or revert occurs, **Then** `canonical_merge_history` records the entity version before/after, linked-source set before/after, operation, actor (`user_id` or `system`), conflicts, method and timestamp.
- **Given** two writers update the same entity, **Then** exactly one expected-version write succeeds; the loser reloads/retries or surfaces a conflict, and `test_canonical_concurrent_merge.py` proves no lost update.
- **Given** an admin reverts a historical operation, **Then** the revert is a new audited transition against an expected current version; it never overwrites changes committed after the selected history item.
- **Given** review queue updates must be real time, **Then** Zero publishes only the fields required to render queue/list state; full snapshots are fetched through workspace-authorized REST endpoints.

#### Story 13.2d: PII-Safe Canonicalization `[P0]`

- **Dependency:** Story 13.1; blocks enabling either persistence path.
- **Given** BDS or Jobs data contains PII, **Before** writing canonical data, source snapshots, outbox payloads or merge history, **Then** AD-25-compatible redaction runs for every domain.
- **Given** BDS exposes `contact`/`phone_key` or Jobs exposes JD text, **Then** raw values never enter golden records or history; a one-way keyed digest may be retained only when required for matching.
- **Given** logs and metrics, **Then** they contain counts/status only, never raw PII values.

#### Story 13.2e: Dedup Benchmark & Release Gate `[P1]`

- **Dependency:** Stories 13.2a–d; Jobs fixtures additionally depend on Epic 12 pilot data.
- **Given** BDS and Jobs fixtures at 15%, 30% and 70% entity-level cross-source overlap, **Then** each domain/tier reports precision, recall and F1 with hard gates `precision ≥ 0.95`, `recall ≥ 0.90`, and `F1 ≥ 0.92`.
- **Given** benchmark metadata, **Then** `overlap_rate = multi_source_ground_truth_entities / total_ground_truth_entities`; fixture counts must satisfy that equation and raw-record totals independently.
- **Given** the Nowing eval harness, **Then** fixtures live under `nowing_evals/data/canonical/fixtures/`, benchmark packages under `nowing_evals/src/nowing_evals/suites/canonical/`, and execution uses `python -m nowing_evals ...`.

_AD-27 (domain convention) · AD-24 (aggregator output) · AD-25 (PII redaction)._

### Story 13.3: Unified Search API `[P0]`

As a user,
I want one ranked result set across canonical entities and documents,
So that linked raw sources collapse under their canonical entity while unmatched documents remain discoverable.

**Acceptance Criteria:**
- **Given** a query, **When** submitted, **Then** document and canonical retrieval run in parallel with identical workspace, date, status and type filters on both vector and full-text paths.
- **Given** the existing retriever uses Reciprocal Rank Fusion, **When** vector/full-text and document/canonical candidate lists fuse, **Then** ranking uses weighted RRF `w_vector/(k + rank_vector) + w_fts/(k + rank_fts)` with `k=60`, default weights `0.7/0.3`, non-negative workspace configuration and no direct addition of raw cosine distance to `ts_rank_cd`.
- **Given** an entity embedding is NULL, stale or generated by another model, **Then** that row remains eligible through full-text retrieval but is excluded from vector ranking until the current-model backfill succeeds.
- **Given** a document/source row is linked through `canonical_entity_sources`, **When** its canonical entity is present, **Then** the raw result is grouped beneath that entity rather than emitted as a second top-level hit; unmatched documents retain their own result group.
- **Given** a canonical entity is displayed, **Then** the API supplies source count, source-link identifiers, confidence, conflict state and a workspace-authorized `View N sources` expansion contract.
- **Given** workspace isolation, **Then** both corpora are protected by the same authenticated workspace context; canonical RLS does not substitute for existing document authorization.
- **Given** the release benchmark, **Then** end-to-end recall@10 ≥ 0.85, precision@5 ≥ 0.80, duplicate top-level result groups = 0, and p95 < 500 ms including query embedding and fusion.
- **Given** p95 exceeds 500 ms or embedding/outbox failures cross the configured threshold, **Then** low-cardinality metrics and alerts identify corpus, retrieval path and workspace without logging query PII.

**Validation:**
- Canonical eval suite measures quality and latency through the public API, not backend imports.
- Tests cover weighted-RRF ordering, identical filter application, pending/stale embeddings, cross-corpus collapse, source expansion authorization and RLS isolation.
- A/B comparison uses the same query set and relevance judgments for documents-only versus documents+canonical, reporting absolute metrics and relative change.

_AD-27 (search_text convention) · AD-2 (pgvector) · workspace isolation contract in Story 13.1._

---

## Ghi chú
- **Mồ côi/defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default enable/disable) → backlog.
- **RS-9** ("project memory" của team = `ResearchThread`?) → resolve trong scope 3.9/3.7.
- Story `[DONE]` không liệt kê AC (đã implement); chỉ story `[GAP]`/`(mới)` có AC để dev thực thi.
- **Epic 13** phụ thuộc Epic 12 (HR scrapers) hoàn thành để có data deduplicate — story 13.2 cần aggregator output.
- **Epic 13 scope reduced 2026-08-06:** 7→3 stories. Existing aggregators already do matching/dedupe — Epic 13 adds persistence + convention, not new engine.
---

## Ghi chú
- **Mồ côi/defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default enable/disable) → backlog.
- **RS-9** ("project memory" của team = `ResearchThread`?) → resolve trong scope 3.9/3.7.
- Story `[DONE]` không liệt kê AC (đã implement); chỉ story `[GAP]`/`(mới)` có AC để dev thực thi.
