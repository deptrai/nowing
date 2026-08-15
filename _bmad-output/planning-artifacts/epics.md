---
title: Nowing - Epic Breakdown
description: ''
createdAt: '2026-07-28T12:47:48.297Z'
updatedAt: '2026-08-07T00:00:00.000Z'
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
`[PROPOSED]` **FR-46 `vn_jobs.aggregate`** → **E12.4a–e P0 (split: normalization, dedupe/conflict, PII, ingest, exposure)** (cross-source normalization, dedupe, confidence, conflict detection).
`[PROPOSED]` **FR-47 PII redaction for job data** → **E12.5 P0** (mask/drop phone, email, names before memory).

`[PROPOSED]` **FR-63 Intent Signal Detection** → **E21.1** (buying signals: funding, hiring, tech stack, executive moves).
`[PROPOSED]` **FR-64 Lead Scoring & Prioritization** → **E21.2** (composite score: fit + intent).
`[PROPOSED]` **FR-65 Enriched Contact Data** → **E21.3** (verified email/phone via waterfall).
`[PROPOSED]` **FR-66 Outbound Prospecting Automation** → **E21.4** (email in MVP; LinkedIn/Zalo deferred; multi-source lead generation from all FR-6 scrapers).
`[PROPOSED]` **FR-67 CRM Integration & Write-Back** → **E21.5** (Salesforce, HubSpot, Pipedrive).
`[DEFERRED]` **FR-68 Zalo Integration (Vietnam)** → **E21.6** (Zalo OA, 81% VN professionals; disabled in MVP).
`[PROPOSED]` **FR-69 Outcome-Based Pricing** → **E21.7** (pay per meeting / lead).

`[READY]` **FR-70 Telegram Web Preview Scraper** → **E22.1** (`t.me/s/{channel}`, no login, zero-risk).
`[READY]` **FR-71 Telegram MTProto Client Ingestion** → **E22.2** (Telethon, private channels, discussion comments).
`[READY]` **FR-72 Telegram Scraper Platform Accounts & Session Onboarding** → **E22.2** (AES-256 encrypted `StringSession` in DB).
`[READY]` **FR-73 Telegram Rate Limiter & FloodWait Cooldown** → **E22.2** (`ScraperPlatformAccountRotator`, Redis mutex lock).
`[READY]` **FR-74 Telegram Async S3 Media Streaming** → **E22.3** (128KB chunk stream directly to S3/MinIO).
`[READY]` **FR-75 Telegram Entity Extraction** → **E22.3** (VN phone, BĐS price, email into `raw_entities` JSONB).
`[READY]` **FR-76 Telegram Realtime Stream Daemon** → **E22.3** (`events.NewMessage` -> Redis Stream `stream:telegram:raw_events`).
`[READY]` **FR-77 Telegram Alert Engine Trigger** → **E22.3** (matching Telegram messages trigger `AlertRule`).
`[READY]` **FR-78 Telegram AI Agent Tools** → **E22.3** (`telegram_search_channel`, `telegram_fetch_recent_posts`).
`[READY]` **FR-79 Telegram PostgreSQL Storage & Zero Cache Sync** → **E22.1** (composite unique `(channel_id, message_id)`).

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
- **Mới 2026-08-10 (Market Research → Lead Intelligence):** FR-63 (Intent Signals) → **E21.1** `[PROPOSED]` · FR-64 (Lead Scoring) → **E21.2** `[PROPOSED]` · FR-65 (Contact Enrichment) → **E21.3** `[PROPOSED]` · FR-66 (Outbound Automation) → **E21.4** `[PROPOSED]` (Email in MVP; LinkedIn/Zalo deferred) · FR-67 (CRM Integration) → **E21.5** `[PROPOSED]` · FR-68 (Zalo Integration) → **E21.6** `[DEFERRED]` · FR-69 (Outcome Pricing) → **E21.7** `[PROPOSED]`.

## Epic List

> **📋 Language convention (readiness audit 2026-08-08):** Epic descriptions and context notes may use Vietnamese (project context). Acceptance Criteria (ACs) MUST use English with Given/When/Then format for testability and automated test conversion. Story titles use English. This is a documentation standard — existing mixed-language content is accepted as brownfield.

> **⚠️ RECONCILED 2026-07-24 với `implementation-artifacts/sprint-status.yaml` (nguồn chân lý tiến độ):** một sprint đã chạy — **E1,2,5,7 = done; E3/E4/E6/E8 gần done**. Nhiều story dưới đây gắn `[GAP]` ở phiên planning này THỰC RA ĐÃ DONE (2.5, 3.6, 3.7, 6.4, 8.3, 3.11 dedupe, 3.12 security, 8.4a kill-switch, 8.5 obs) — đã retag `[DONE]`.
> **Việc CÒN LẠI thật sự:**
> - Từ sprint cũ: ~~4-6~~ research-continuity (done) · ~~6-5~~ memory-driven-automations (done) — cả hai đã verify code.
> - **Đã đóng 2026-08-01:** 3.9 memory recall eval-gate (baseline ratified 2026-08-04) · 3.10 legacy data-loss recovery · 8.7 auto-extract spend/budget cap · 8.8 kill-switch · 8.9 observability.
> **✅ Cập nhật 2026-08-01 (ops):** memory (mig 177–179) **CHƯA lên production** (prod=`alembic 174`; 175–179 ở branch `develop`). ⇒ Các gap memory là **cổng TRƯỚC KHI merge memory lên prod**, KHÔNG phải sự cố prod đang chạy. 3.10a **done** (không mất dữ liệu) · 3.10b **done** (guard + backfill command + 5 test; deploy-order `mig177→backfill→mig178`) ⇒ **FR-36 RESOLVED**. **3.9** eval-gate (**`done`** — baseline ratified 2026-08-04) · **8.7** spend-cap (**`done`** — 59 tests passed; cổng trước khi bật auto-extract trên prod). *(auto-extract KHÔNG đang bleed trên prod vì 179 chưa deploy.)*
>
> **🆕 2026-07-25 — Epic 9 *(Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng)*:** SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (✅ ADOPTED). **FR-24 rời E2 → E9.** Các việc P0/P1, đều là lỗi thương mại/kiến trúc đang chạy trong production path chứ không phải tính năng mới: **9.1a** degradation + self-host độc lập (P0, **chặn public repo**) · **9.1b** contract regression guard (P0, không chặn) · **9.2** cost metering thật — **DONE**: parser `done.usage.costDollars` + fallback 60k micros (~$0.06), cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671 (P0) · **9.3** latency budget State A/B + mode default `quality`→`balanced` (P1) · **9.4** docs (P1) · **9.6a/9.6b** provenance + re-validate. **Gate:** pricing có thể bắt đầu định hình dựa trên số thật, vẫn giữ margin 1.5–2.5× cho full-pipeline cost aggregation.

### Epic 1: Identity, Auth & Workspace RBAC — ✅ DONE
Đăng ký/đăng nhập/OAuth/PAT + workspace RBAC Owner/Editor/Viewer. **FRs:** FR-1,2,3,4,10.
> **Brownfield note (readiness audit 2026-08-08):** Implemented prior to epic breakdown. No individual story files — functionality verified through code review and production usage.

### Epic 2: Connectors — ✅ DONE (retrospective 2026-08-08)
Built-in scrapers + OAuth connectors + external MCP connectors; connectors là memory ingestion source. **FRs:** FR-6,7,8. **All 6 stories done:** 2.5 MCP toggle, 2.6 Indeed, 2.7 Walmart, 2.8 Amazon EU, 2.9 input validation, 2.10 Exa MCP (with citation ACs).
> **⚠️ 2026-07-25: FR-24 (ChainLens) đã rời Epic 2 → Epic 9.** ChainLens không phải connector. Story `2-4-chainlens-research-mcp-tool` giữ `done` làm lịch sử — nó đã ship tool thật; việc còn lại thuộc Epic 9.

### Epic 3: Knowledge Base + Long-Term Memory — ✅ DONE
KB + long-term research memory. **FRs:** FR-9,11,12,13,32,33,34, **FR-40** *(mới)*, **NFR-1b/1c/1d** *(mới)*. **Open:** 3.15 run citations `[ready-for-dev]`, 3.16 OKF export `[ready-for-dev]`.
> **🆕 2026-07-25 (readiness Nhóm 3):** hai story mới, cả hai đều là **gap trước đây không có FR lẫn epic**. **3.13** — `MemoryExtractionService` chỉ có `extract_from_turn` và workspace mới không seed gì ⇒ `nowing_recall` session đầu **rỗng theo cấu trúc**, **M1 (first-run value ≤15 phút) không tồn tại**. **3.14** — `MemoryInjectionMiddleware` **chặn mọi lượt chat** với `SELECT` không LIMIT, bỏ qua cả HNSW + GIN index đã có sẵn ⇒ chi phí mỗi lượt tăng tuyến tính theo mức dùng. **3.14 nên chạy trước khi chốt số SM-10 của 3.9.**

### Epic 4: Chat & Agents — ✅ DONE
Multi-agent runtime + memory tools + research continuity. **FRs:** FR-14,15,16,17 (+4.5, 4.6). **Open:** 4.7 pointer-based tabs `[ready-for-dev]`, 4.8d chat quality LLM-as-judge `[ready-for-dev]`.

### Epic 5: Deliverables — ✅ DONE
Report/podcast/video/image. **FRs:** FR-21,22,23.
> **Brownfield note (readiness audit 2026-08-08):** Implemented prior to epic breakdown. No individual story files — functionality verified through code review and production usage.

### Epic 6: Automations — ✅ CORE DONE (4 gap mới: playbook layer; plus Story 6.8 Generic Alert Engine `[ready-for-dev]`)
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

### Epic 10: Connector & Scraper Expansion — ✅ DONE
Vietnam BĐS (batdongsan, chotot, muaban) + broader scraper port. **FRs:** FR-6 variants. **All core stories done:** 10.1–10.4.

### Epic 11: Telegram Automation & Bot — ✅ DONE
Notification, write-back, builder UI, inline keyboard, commands. **FRs:** FR-20 variants. **All done.**

### Epic 12: HR/Recruitment Vertical — Vietnam Job Market Pilot — 🔄 IN PROGRESS
VietnamWorks, TopCV, ITviec scrapers; job listing normalization/dedup/PII/ingest; saved searches + job market alerts. **Open:** 12.1–12.5, 12.4a–e, 12.6, 12.9.

### Epic 13: Canonical Entity Storage & Multi-Domain Indexing — 🗑️ DROPPED 2026-08-08
Canonical index moved to `chainlens-research`; Nowing scrapers feed via `POST /v1/ingest/scraper`.

### Epic 14: News Aggregation (Vietnam) — 📋 BACKLOG
RSS feed integration, entity enrichment, alerts, digest/synthesis. **Open:** 14.1–14.4.

### Epic 15: Financial Data (Vietnam) — 📋 BACKLOG
CafeF / Vietstock data, stock price alerts, financial trend detection. **Open:** 15.1–15.4.

### Epic 16: Company Directory (Vietnam) — 📋 BACKLOG
masothue.com company data, official business registry, company alerts, timeline. **Open:** 16.1–16.4.

### Epic 17: E-commerce Intelligence (Vietnam) — 📋 BACKLOG
Lazada/Shopee product data, price-drop alerts, competitor tracking. **Open:** 17.1–17.4.

### Epic 18: Vertical Client Platform (Public Agent-Chat) — 🔄 IN PROGRESS
Public agent-chat endpoints, AgentConfig registry, client_id tenancy, cost traceability, rate limiting + RLS. **Open:** 18.1–18.8.

### Epic 20: Nowing Ecosystem Integration — Feed & Recall from chainlens-research — ✅ DONE
`NowingIngestService` + `to_chunks()`, gap-fill caller, `NowingPrivateProvider`, service-to-service auth. **Open:** none.

### Epic 21: Lead Gen Intelligence — ⏸️ PROPOSED
Intent signals, lead scoring, contact enrichment, outbound sequences, CRM sync, Zalo deferred, outcome pricing. **Gated:** legal/ToS, vendor POC, PII, CRM, outcome pricing. Full scope in `epic21-proposal-2026-08-11.md`.

### Epic 22: Telegram Scraper & Channel Ingestion Engine — 🚀 READY FOR DEV
Public channel web preview, MTProto Userbot session pool, distributed mutex lock, FloodWait cooldown state machine, regex entity extractor, S3 media chunk streaming, realtime stream daemon, Alert Engine trigger, AI Agent tools. **Open:** 22.1–22.3. Governed by `architecture-telegram-scraper-2026-08-15`.

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
**Given** the Walmart product page payload is missing `__NEXT_DATA__`, returns malformed JSON, or the requested product variant is out of stock, **When** the scraper parses the response, **Then** it returns `degraded=true` with `degradation_reason: parse_error` or `not_found` and does not crash.

**Kỹ thuật:** parse `__NEXT_DATA__`, rotate proxies on block, add `walmart.scrape` + `walmart.reviews` verbs, register billing units.
_FR-6 · upstream PR #1614._

### Story 2.8: Amazon EU Marketplaces  `(mới 2026-07-30)`  `[ready-for-dev]`
As a seller watching European markets,
I want the Amazon scraper to support EU marketplaces (`amazon.de`, `amazon.fr`, `amazon.co.uk`, etc.),
So that I can track prices and listings across regions.

**Acceptance Criteria:**
**Given** an Amazon product URL on an EU domain, **When** I scrape it, **Then** it returns localized product metadata, price, currency, and availability.
**And** URL validator accepts EU TLDs; **And** region/currency are exposed in output schema.
**Given** an Amazon EU product URL points to an unsupported TLD, returns a 404/403, or the page is blocked by a bot challenge, **When** the scraper runs, **Then** it rejects the invalid input or returns `degraded=true` with `degradation_reason` and does not retry indefinitely.
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
**Given** the Exa MCP server returns a 401/403, 429 rate-limit, or times out during `web_search_exa`/`web_fetch_exa`, **When** the tool is invoked, **Then** the capability returns `degraded=true` with `degradation_reason` and does not crash the chat turn.

**Kỹ thuật:** add `EXA_MCP_CONNECTOR` to `SearchSourceConnectorType`, `MCP_SERVICES`, connector agent/searchable maps, and validation; create route-level `server_config` builder from `exa_api_key`; reuse `mcp_discovery` subagent with curated `allowed_tools` / `readonly_tools`.
_FR-8 · FR-8.1 · OQ-4._

> **🆕 Extend 2026-08-08 (SCP `sprint-change-proposal-2026-08-08.md`):** `web_search_exa`/`web_fetch_exa` là MCP tools return text trực tiếp — không qua `_capability_tool` hay citation registry. Agent nhận search results nhưng không có `[n]` labels để cite. Append ACs dưới đây.

**Acceptance Criteria (appended 2026-08-08 — Exa MCP citation registration):**

**Given** the agent calls `web_search_exa` and receives results with URLs, **When** the tool returns, **Then** each result URL is registered as a `WEB_RESULT` citation in the `CitationRegistry`.
**Given** the agent calls `web_fetch_exa` for a specific URL, **When** the tool returns, **Then** the fetched URL is registered as a `WEB_RESULT` citation.
**Given** the registry contains Exa `WEB_RESULT` entries, **When** the model emits `[n]` labels referencing them, **Then** URL citation chips render in chat.
**And** existing MCP tool behavior (readonly, no HITL) is unchanged.

**Kỹ thuật (appended):** hook vào MCP tool wrapper hoặc post-processing step — extract URLs from `web_search_exa` results, register URL directly for `web_fetch_exa`. Reuse `register_web_citations()` helper from Story 3.15 extension.

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
**Given** `chunkId` trong citation không tồn tại (chunk not found) hoặc document đã bị re-index, **When** editor mở, **Then** editor fallback về đầu document và hiển thị error thay vì crash.
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
**Given** `source_type`/`source_id` dùng cho ToS takedown bị thiếu hoặc không hợp lệ, **When** thực hiện bulk-delete, **Then** hệ thống trả `invalid_source` và không xóa memory không liên quan.
_OQ-3 · AR-4 · AD-DEFER-4._

### Story 3.7-followup: Retention Hardening  `(tech debt)`  `[backlog]`
As a platform engineer,
I want retention settings có DB-level guards + concurrent safety + test robustness,
So that retention không corrupt dưới concurrent access và tests không pass for wrong reasons.

**Acceptance Criteria:**
**Given** concurrent retention update trên cùng workspace, **When** 2 requests update document_retention_days cùng lúc, **Then** dùng SELECT FOR UPDATE tránh last-write-wins.
**Given** test_archived_document_excluded_from_hybrid_search, **When** chạy, **Then** có negative assertion verify cả 2 chunks tồn tại trong DB trước khi assert search filter.
**Given** test-archived-sync.spec.ts, **When** backend không chạy, **Then** test skip với clear message thay vì fail.
**Given** data-retention.spec.ts, **When** test fail mid-execution, **Then** workspace cleanup chạy trong finally block.

_Source: code review defer items từ 3-7. Priority: P2. Effort: 1-2 days. Trigger: khi có concurrent retention updates._

---

### Story 3.9: Memory Recall Eval-Gate  `(mới)`  `[DONE — SHIP-GATE implementation complete; baseline ratification pending]`
As a platform team,
I want một eval gate đo chất lượng recall của memory trên `nowing_evals`,
So that không ship recall rác (agent "đoán" thay vì "nhớ").

**Acceptance Criteria:**
**Given** harness `nowing_evals` (đã có `retrieval.py` recall@k/MRR/nDCG + `wilson_ci`), **When** thêm **suite memory-recall** nhắm `nowing_recall`/`/memories/search`, **Then** suite chạy được qua CLI với dataset gán nhãn.
**Given** cần đo chất lượng, **When** định nghĩa oracle "recall hit" (top_k≤5 + ngưỡng similarity, verify RS-2) + thêm metric **noise-rate**, **Then** đo được precision@5 và noise với Wilson CI.
**Given** baseline đã đo, **When** chốt **số SM-10** (precision@5 ≥ 0.80, noise ≤ 0.10) — **cấm placeholder "≥X%"**, **Then** gate chặn ship nếu chưa đạt (RS-7).
**And** MCP selfcheck CI (AR-8) chạy trong pipeline.
**Given** dataset của `memory-recall` eval bị rỗng hoặc `gate.yaml` thiếu `judge_model`/`oracle`, **When** `nowing_evals run memory recall` khởi động, **Then** nó raise `QualityBenchmarkConfigError` với validation message rõ ràng và không gọi judge.
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
**Given** một memory row có embedding rỗng hoặc malformed trong bench dedupe, **When** tính cosine similarity, **Then** hệ thống log `invalid_embedding`, bỏ qua row đó, và tiếp tục tuning ngưỡng.
_AR-3 · gắn với 3.9._

### Story 3.12: Memory Security — RBAC Enforcement, Isolation & Audit  `(mới)`  `[DONE — sprint 8-5 security + IDOR fix (deferred-work 4.5)]`
As a security-conscious team,
I want memory an toàn multi-tenant + có audit,
So that recall không rò rỉ cross-tenant và mọi memory write có vết.

**Acceptance Criteria:**
**Given** quyền `memory:*` đã backfill (mig 177), **When** gọi mọi memory endpoint + MCP tool, **Then** permission được enforce (test khẳng định, không chỉ tin backfill).
**Given** 2 workspace/user khác nhau, **When** recall/search, **Then** không trả memory cross-tenant (test isolation, NFR-5).
**And** mọi memory write (create/correct/delete) ghi **audit log** (hiện chỉ `logger.warning`).
**Given** một user không có quyền `memory:read` hoặc thuộc workspace khác, **When** gọi memory endpoint/MCP tool, **Then** request bị denied với 403 và ghi `unauthorized_memory_access` vào audit log.
_AR-9 · NFR-2/NFR-5 (memory-scoped)._

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
**Given** research run đầu tiên của người dùng mới trả về kết quả rỗng hoặc auto-extract pipeline lỗi (ví dụ kill-switch OFF hoặc vượt spend cap), **When** `nowing_recall` được gọi, **Then** nó trả `empty`/`error` status với message rõ ràng thay vì trả về rỗng im lặng.

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
**Given** truy vấn memory injection bị timeout hoặc embedding index unavailable, **When** middleware rơi vào fallback, **Then** nó tăng counter `memory_injection_timeout`/`unavailable` và trả `None` mà không block lượt chat.
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
**Given** the `Run` record referenced by a citation is missing or has been cleaned up after `RUNS_RETENTION_DAYS`, **When** the citation is rendered, **Then** the UI shows `run not found` with the input snapshot instead of a broken link.

**Kỹ thuật:** add `RUN` to citation source enum, mint run citation from capability tool, parse `run_<uuid>` tokens in chat, render citation chip, open run in citation panel.
_FR-13 · FR-39 · upstream PR #1619._

> **🆕 Extend 2026-08-08 (SCP `sprint-change-proposal-2026-08-08.md`):** Story 3.15 cover sync `RUN` citations cho scraper runs. Gap phát hiện post-implementation: ChainLens Research `ResearchOutput.sources[]` (URL list) không được register as `WEB_RESULT` citation — `CitationSourceType.WEB_RESULT` enum có, `markers.py` render được, nhưng **0 code call `registry.register(WEB_RESULT, ...)`**. FR-24 yêu cầu "câu trả lời tổng hợp **có trích dẫn**" + "sources[] giữ nguyên thứ tự trích dẫn để map về citation UI" — **VIOLATED** cho ChainLens. Append ACs dưới đây để đóng gap.

**Acceptance Criteria (appended 2026-08-08 — WEB_RESULT citations for ChainLens sources):**

**Given** a sync ChainLens research call completes with `ResearchOutput.sources[]`, **When** the capability tool finalizes, **Then** each source URL is registered as a `WEB_RESULT` citation in the `CitationRegistry` with its title and URL.
**Given** the registry contains `WEB_RESULT` entries, **When** `normalize_citations()` resolves `[n]` ordinals, **Then** they are rewritten to `[citation:https://...]` markers.
**Given** an assistant message contains `[citation:https://...]`, **When** rendered in chat, **Then** the `UrlCitation` chip displays with domain name + favicon, and clicking opens the URL in a new tab.
**Given** a ChainLens answer with 5 sources, **When** the model emits `[1][3][5]` labels, **Then** exactly 3 URL chips render, each linking to the correct source URL.
**And** existing `RUN` and `KB_CHUNK` citations continue to work unchanged.
**And** the `RUN` citation (run panel) and `WEB_RESULT` citations (URL chips) coexist — run chip shows "Source" opening run panel, URL chips show domain opening external link.

**Kỹ thuật (appended):** add `register_web_citations(registry, sources: list[Source])` helper; call in `agent.py` sync ChainLens path after executor returns, before `attach_run_citation()`. Frontend: no changes — `citation-parser.ts` already handles `kind: "url"`, `UrlCitation` component already renders.

### Story 3.16: Open Knowledge Format (OKF) Export  `(mới 2026-07-30)`  `[ready-for-dev]`
As a data owner or integrator,
I want to export my workspace knowledge base in Open Knowledge Format (OKF),
So that I can move, archive, or integrate Nowing knowledge with other tools.

**Acceptance Criteria:**
**Given** a workspace with documents, memories, and source provenance, **When** I request an OKF export, **Then** it produces a valid OKF bundle (documents, chunks, facts, relations, citations) that can be validated against the OKF schema.
**Given** the export, **When** inspected, **Then** it does not leak data from other workspaces and redacts API keys / secrets.
**Given** a workspace has no documents, memories, or source provenance, **When** an OKF export is requested, **Then** it returns a valid `empty` bundle with `item_count=0` instead of a 500 error.

**Kỹ thuật:** build an export job over workspace-scoped `Document`, `Chunk`, `Memory`, `MemoryRelation`; serialize to OKF JSON; stream/limit size for large KBs.
_FR-32 · RS-8 · upstream PR #1617._

### Story 3.17: Memory Injection Bounded-Retrieval Performance Gate  `(mới 2026-08-08)`  `[ready-for-dev]`

As a platform engineer,
I want a performance + regression gate proving `MemoryInjectionMiddleware` stays O(top-k),
So that `AD-18` is not silently regressed as the product accumulates memories.

**Acceptance Criteria:**

**Given** a workspace with 10,000 memory rows,
**When** `MemoryInjectionMiddleware.abefore_agent` runs,
**Then** the DB query uses the `ix_memories_embedding` (HNSW) or `ix_memories_content_search` (GIN) indexes with a `top_k`/`LIMIT` bound; a full-scan `SELECT ... ORDER BY created_at` without `LIMIT` is not present in the query plan.

**Given** the same 10,000-row workspace,
**When** measured over 100 turns,
**Then** p95 DB time ≤ 150ms and p95 total time ≤ 300ms.

**Given** the raw memory content for a single turn would exceed 8,000 chars,
**When** `render_bounded_memory_injection` is called,
**Then** it truncates/renders at most 8,000 chars and emits a `memory_injection_truncated` counter.

**Given** the middleware hits an exception,
**When** it falls back to `None`,
**Then** a `memory_injection_failure` counter is incremented (not just `logger.exception`).

_Governed by `AD-18`, NFR-1b._

---

## Epic 4: Chat & Agents
### Story 4.7: Pointer-Based Tabs with Live Title Resolution  `(mới 2026-07-30)`  `[ready-for-dev]`
As a user with many open documents and chats,
I want tabs to be lightweight pointers that resolve titles from the live source,
So that tab state is fast to save/load and titles stay up to date without stale snapshots.

**Acceptance Criteria:**
**Given** a workspace with documents and chats open in tabs, **When** a document/chat title changes, **Then** the tab bar reflects the new title without a full refresh.
**Given** many tabs, **When** the app loads, **Then** tab state is small (pointer: entity id + kind) and titles are fetched via `useResolvedTabs`.
**And** tab state uses the v2 storage key; **And** fallback navigation works for pointer tabs.
**Given** tab pointer trỏ đến document/chat đã bị xóa hoặc `useResolvedTabs` fetch trả về 404 not found, **When** tab bar render, **Then** nó hiển thị placeholder, xóa pointer cũ, và không crash.

**Kỹ thuật:** refactor `Tab` to pointer-only state, add `useResolvedTabs` hook, resolve document/chat title via Zero/`react-query`, render `TabBar` from resolved tabs.
_FR-14 · upstream PR #1609._

### Story 4.8a: Extend `NewChatClient` telemetry  `[done]`
As a benchmark runner, I want `NewChatClient` capture token usage, TTFB, turn id and finish status from `/api/v1/new_chat` SSE, so that `nowing_evals` can measure chat cost, latency and outcome per turn.

**Acceptance Criteria:**
**Given** a chat turn completes and the SSE stream emits `data-token-usage` and `data-turn-info` frames,
**When** `NewChatClient` processes the stream,
**Then** it exposes `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `ttfb_ms`, `turn_id`, and `finish_status` on `ArmResult` in the expected integer/string types.

**Given** an SSE frame is malformed, missing required fields, or the stream is closed early,
**When** the client parses it,
**Then** it logs the failure with `turn_id` (if available), sets missing numeric fields to `0` and string fields to `null`, and does not raise an unhandled exception.

_FR-42 · NFR-10 · `nowing_evals/core/clients/new_chat.py`._

### Story 4.8b: Chat Regression Benchmark Suite  `[done/review]`
As a release engineer, I want `nowing_evals run chat regression` over a representative query set, so that every deploy is checked for latency/cost/citation drift.

**Acceptance Criteria:**
**Given** a representative query dataset with tags (memory, document, deep-research, multi-tool, creative) is ingested,
**When** `nowing_evals run chat regression` executes,
**Then** it runs every case, computes p95 latency/TTFB, error rate, finish rate, citation count, and cost/turn, and produces a `gate.yaml`-compatible report that flags drift against the ratified baseline.

**Given** the ratified `baseline.yaml` is missing or has no matching tag,
**When** the suite runs,
**Then** it raises `QualityBenchmarkConfigError` with the missing tag/baseline path and exits non-zero.

**Given** a live web source returns CAPTCHA, rate-limit, or 5xx,
**When** the suite runs,
**Then** it classifies the error as `external_flake`, does not retry more than the configured limit, and includes the failure in the aggregate `error_rate`.

_FR-42 · NFR-10 · `nowing_evals/suites/chat/regression/`._

### Story 4.8c: Production query sampler + anonymizer  `[done]`
As an eval operator, I want to extract and anonymize real production queries for the benchmark dataset, so that regression tests reflect actual usage without leaking PII.

**Acceptance Criteria:**
**Given** production query logs exist and the environment has `EVAL_QUERY_SAMPLING_OPT_IN=true`,
**When** the sampler runs,
**Then** it reads the logs, strips PII (phone, email, IP, user names), replaces workspace/user identifiers with stable hashes, and writes a `gate.yaml`-compatible dataset.

**Given** no logs exist, PII stripping fails, or `EVAL_QUERY_SAMPLING_OPT_IN` is not true,
**When** the sampler runs,
**Then** it logs the reason, outputs an empty or unchanged dataset, and exits `0` without crashing or writing partial data.

_FR-42 · NFR-10 · `market-*-production-query-sampler-research-2026-08-02.md`._

### Story 4.8c-followup: Sampler Hardening  `(tech debt)`  `[backlog]`
As an eval operator,
I want sampler có HMAC hash + DB error handling + test cleanup,
So that sampler robust khi trở thành automated job.

**Acceptance Criteria:**
**Given** workspace hash, **When** generate, **Then** dùng HMAC thay vì plain SHA256 (defense-in-depth).
**Given** DB query fail, **When** sampler chạy, **Then** log error rõ ràng thay vì crash silently.
**Given** test_chat_query_sampler.py session context manager, **When** test fail, **Then** __aexit__ rollback transaction.

_Source: code review defer items từ 4-8c. Priority: P3. Effort: 1 day. Trigger: khi sampler trở thành automated job._

### Story 4.8d: Chat quality benchmark with LLM-as-judge  `[ready-for-dev]`
As an ML/QA engineer, I want `chat/quality` judge responses on groundedness, citation accuracy, and helpfulness, so that quality regressions are caught before deploy.

**Acceptance Criteria:**

**Given** the `chat/quality` suite is configured with a judge model distinct from the tested model and a representative dataset with tags (memory, document, deep-research, multi-tool, creative),
**When** `nowing_evals run chat quality` executes,
**Then** it judges every turn for groundedness, citation accuracy, and helpfulness; reports an aggregate score and per-tag breakdown; and writes a `gate.yaml`-compatible report with p50/p95 per metric.

**Given** a turn contains no citations but the metric requires citation scoring,
**When** the judge evaluates,
**Then** citation accuracy for that turn is recorded as `0` (not `null` or `NaN`) and included in the aggregate denominator.

**Given** the judge model is unavailable, returns malformed JSON, or returns scores outside the configured rubric range,
**When** the suite runs,
**Then** it logs the failing turn with `turn_id` and `judge_error`, skips scoring for that turn, exits with a non-zero status, and does not publish partial/invalid results.

**Given** the dataset is empty, smaller than the configured minimum-sample threshold, or missing required tags,
**When** the suite starts,
**Then** it raises `QualityBenchmarkConfigError` with a clear validation message before any judge calls are made.

**Validation:**
- Unit test: `test_chat_quality_judge_scoring.py` — mock judge returns deterministic groundedness/citation/helpfulness scores; assert aggregate and per-tag breakdown.
- Unit test: `test_chat_quality_missing_config.py` — missing `judge_model` or dataset path raises `QualityBenchmarkConfigError`.
- Unit test: `test_chat_quality_invalid_judge_response.py` — malformed JSON / out-of-range scores are logged and the run fails closed.
- Integration test: `test_chat_quality_end_to_end.py` — run on a 10-turn labeled dataset and verify output schema and metric bounds.

_FR-42 · `nowing_evals/suites/chat/quality/`._

### Story 4.8d-followup: Quality Benchmark Test Robustness  `(tech debt)`  `[backlog]`
As an ML/QA engineer,
I want quality benchmark tests handle missing gate.yaml gracefully,
So that tests không fail trong CI nếu file missing.

**Acceptance Criteria:**
**Given** gate.yaml missing, **When** test chạy, **Then** skip với clear message thay vì crash.

_Source: code review defer item từ 4-8d. Priority: P3. Effort: 0.5 day. Trigger: làm trước — rủi ro thấp nhất._

### Story 4.8e: CI / deploy gate for chat regression  `[done]`
As a release engineer, I want CI block deploy if `chat/regression` drifts beyond ratified baseline, so that bad changes do not reach production.

**Acceptance Criteria:**
**Given** a CI workflow runs `nowing_evals run chat regression` with a ratified `baseline.yaml`,
**When** any per-tag metric drifts beyond the configured tolerance,
**Then** the workflow exits non-zero, blocks the deploy, and sends a Slack/Telegram notification with the drift summary.

**Given** the baseline is not yet ratified and `--fail-on-unratified` is set,
**When** the workflow runs,
**Then** it fails with a clear message that the baseline is unratified.

**Given** the baseline is not yet ratified and `--fail-on-unratified` is not set,
**When** the workflow runs,
**Then** it prints a warning, records the current run as a candidate baseline, and exits `0`.

**Given** the eval command crashes or returns a non-`0` exit code,
**When** CI runs,
**Then** it fails the build, logs the exit code, and does not proceed to deploy.

_NFR-10 · `gate.yaml` · CI workflow._

### Story 4.8f: Benchmark stability — scrape, CAPTCHA, rate-limit, multi-turn  `[done]`
As a release engineer, I want the benchmark robust against live web variance, so that flaky external factors do not mask real regressions.

**Acceptance Criteria:**
**Given** a benchmark run hits live web sources and observes CAPTCHA, rate-limit, or 5xx responses,
**When** the runner classifies the failure,
**Then** it records operational metrics (`scrape_drop_rate`, `rate_limited_count`, `captcha_count`), does not count the failed turn in the regression gate, and continues the run.

**Given** a multi-turn thread fails mid-run (e.g. second turn returns `error` or stream is closed),
**When** the runner continues,
**Then** it marks the remaining turns in that thread as `error`, releases the thread context, and does not leak state into the next case.

**Given** the scrape drop rate for a tag exceeds the configured `max_external_flake_rate`,
**When** the suite finishes,
**Then** it flags the tag as `under_instrumented` in the report and does not block the deploy on that tag alone.

_FR-42 · NFR-10 · `nowing_evals` runner._

### Story 4.8g: Benchmark mode/tier matrix and local vs production parity  `[done]`
As a release engineer, I want benchmark matrix cover speed/balanced/quality/auto modes and local vs prod parity, so that cost/latency claims are validated across configurations.

**Acceptance Criteria:**
**Given** `chat/regression` is run across `speed`, `balanced`, `quality`, and `auto` modes with a consistent query set,
**When** results are aggregated,
**Then** the report contains p50/p95/p99 latency, cost/turn, finish rate, and citation count per resolved mode, and a `mode=auto` breakdown of how many turns resolved to each sub-mode.

**Given** a resolved-mode bucket has fewer samples than `min_bucket_samples`,
**When** percentiles are computed,
**Then** the bucket is flagged `under-sampled` and no percentiles are fabricated.

**Given** a local run and a production run of the same query set both complete,
**When** the local/prod comparison runs,
**Then** it reports per-mode p95 latency/cost diff and flags any divergence beyond the configured tolerance with a diff summary.

_FR-42 · NFR-10 · `report-per-mode.md`._

### Story 4.8h: Mode-Aware Chat Policy for Latency/Cost  `(mới 2026-08-05)`  `[done]`
As a user,
I want `new_chat` to respect the requested `mode` (speed/balanced/quality/auto) when selecting tools, retrieval depth, and escalation to deep research,
So that `chat/regression` passes latency, TTFB, and cost gates without losing answer quality.

**Acceptance Criteria:**
**Given** `mode=speed` and a question about an uploaded document, **When** the agent runs, **Then** it performs a minimal knowledge-base search (`top_k=1`, `max_passages=4`), does not use `task`/deep research/web tools, and answers within the speed-mode latency gate of **≤15 seconds**.
**Given** `mode=balanced` with a mentioned document, **When** the agent runs, **Then** it uses at most two knowledge-base calls and one `task`, does not escalate to deep research, and `chat/regression` p95 cost stays under the balanced-mode budget of **≤100,000 micros** (~$0.10).
**Given** `mode=quality` and no document is mentioned, **When** the first knowledge-base search returns no relevant hits, **Then** the agent may call deep research for web/deep research.
**Given** `mode=auto` and a single-document question, **When** the agent has made **5 tool calls**, **Then** a tool-call budget forces it to answer.
**And** `chat/regression` with the large-doc dataset passes all p95 latency, TTFB, and cost gates; `chat/quality` still passes correctness/citation/completeness. Detailed spec: `@doc/specs/2026-08-05/new-chat-mode-aware-latency-cost-policy`.
_FR-42 · NFR-10 · `sprint-change-proposal-2026-08-05-chat-mode-policy.md`._

### Story 4.8h-followup: Mode-Aware Chat Policy Hardening  `(tech debt)`  `[backlog]`
As a platform engineer,
I want mode budget có concurrent safety + ChainLens conditional gating,
So that budget counter không race và ChainLens chỉ trigger khi cần.

**Acceptance Criteria:**
**Given** concurrent tool calls trong 1 turn, **When** budget counter update, **Then** dùng atomic update tránh race.
**Given** mode=quality và mentioned_document_ids không rỗng, **When** agent chạy, **Then** KHÔNG trigger ChainLens (user đã scope document).
**Given** mode=quality, no mentioned_docs, AND first KB search trả hits, **When** agent chạy, **Then** KHÔNG trigger ChainLens.
**Given** mode=quality, no mentioned_docs, AND first KB search trả empty, **When** agent chạy, **Then** ChainLens được phép trigger.

_Source: code review defer items từ 4-8h. Priority: P2. Effort: 2-3 days. Trigger: khi ChainLens cost là pain point._

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
**Given** API Notion/Slack/Linear/Jira trả về 401/403/429 hoặc OAuth token đã expired, **When** write-back action chạy, **Then** nó fail với `provider_error` typed, trigger `on_failure`, và không retry vô hạn.
_FR-18 · OQ-5 · AD-DEFER-2. Lưu ý: agent_task đã cho phép write-back → đây là nâng cấp, không chặn beachhead._

### Story 6.5: Memory-Driven Automations  `[DONE per sprint-status: 6-5 — cải chính 2026-07-25]`

> **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Header trước ghi `[GAP, post-MVP]` — **SAI**. Verify code: trigger `memory_change` (`app/automations/triggers/builtin/memory_change/`, đăng ký trong `triggers/builtin/__init__.py`) · action `continue_research` (`actions/builtin/continue_research/`, đăng ký trong `actions/builtin/__init__.py`) · `AutomationRun.research_thread_id` (`db.py:712` + relationship `db.py:746`) · resolve qua `dispatch/launch.py:44`. `sprint-status.yaml` (`6-5: done`) là bên đúng.
As a workspace owner,
I want automation trigger khi memory đổi / tiếp tục research thread theo lịch,
So that workflow nghiên cứu chạy liên tục không cần prompt tay.

**Acceptance Criteria:**
**Given** automation có trigger `memory_change` hoặc schedule, **When** memory mới match query/tags **OR** cron đến hạn, **Then** `AutomationRun` chạy với `research_thread_id` + memory context; action `continue_research`/`agent_task` write-back kết quả.
**Given** trigger `memory_change` query trả về empty hoặc `AutomationRun` vượt timeout, **When** automation thực thi, **Then** nó log `trigger_empty`/`timeout` và không enqueue run mới.
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

### Story 6.8: Generic Alert Engine `[ready-for-dev P1]`

As a workspace user,
I want a single alert engine that watches any data source and notifies me when meaningful changes occur,
So that I don't end up with 8 separate scheduler/notification implementations for different verticals.

**Acceptance Criteria:**
- **Given** the Epic 6 automation scheduler, RunService, and notification dispatch exist, **When** the Generic Alert Engine is built, **Then** it reuses them instead of creating a new scheduler service.
- **Given** an alert rule is defined with `capability_id`, `query`, `schedule`, `diff_strategy`, and `notification_channels`, **When** the scheduler triggers, **Then** it runs the capability, computes delta against the last `alert_snapshot`, and dispatches notifications via the configured channels.
- **Given** the engine supports the built-in diff strategies `new_items`, `price_change`, and `threshold_cross`, **When** a vertical story registers an `AlertRule` template, **Then** it only provides data-specific parameters and does not implement its own scheduler or notification path.
- **Given** the engine runs, **When** it creates or updates an `alert_snapshot`, **Then** it stores `alert_rule_id`, `snapshot_json`, and `created_at` in Postgres.
- **Given** a signal capability (e.g. `funding.signal`, `hiring.signal`) is registered with `emits_signals=true`, **When** an alert rule targets a sequence (`target_sequence_id`), **Then** the engine emits an `EnrollmentRequested` domain event/Celery task to the Sequence bounded context; it does NOT treat `sequence_enrollment` as a notification channel.
- **Given** user preferences are configured, **When** an alert triggers, **Then** it respects `alert_subscriptions` (`user_id`, `alert_rule_template_id`, `channels`, `enabled`) and does not create per-vertical preference tables.

**Diff Strategies:**
- `new_items`: query, compare to last snapshot, notify new items. Used for job alerts (12.9), news alerts (14.3).
- `price_change`: compare price field, notify if delta > threshold. Used for stock alerts (15.3), price-drop alerts (17.3).
- `threshold_cross`: compare field to threshold, notify on cross. Used for trend alerts (15.4), company event alerts (16.3).

_Kỹ thuật (không phải AC):_ `AlertRule` table: `id` (UUID), `workspace_id`, `client_id` (CITEXT), `capability_id`, `query` (JSONB), `schedule`, `diff_strategy`, `threshold`, `notification_channels`, `target_sequence_id`, `target_step_id`, `enabled`. `alert_snapshots`, `alert_subscriptions`. Built as an Automation template/extension in `app/automations/` or `app/alerts/`. Governed by `AD-33`, Epic 6 scheduler, FR-44/49/50/51/52.

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

## Epic 7: Multi-surface Clients
### Story 7.4: Dedicated Connectors Layout  `(mới 2026-07-30)`  `[ready-for-dev]`
As a workspace member,
I want a dedicated page (not a modal) for managing connectors,
So that I can search, group, view health, and connect new data sources in a focused UI.

**Acceptance Criteria:**
**Given** I open workspace settings, **When** I click "Connectors", **Then** I navigate to a dedicated route with a sidebar panel and a searchable grid/list of connectors.
**Given** the connectors page, **When** I view a connector, **Then** I see its type, health, indexing state, and grouped rows by category.
**And** the layout supports live connectors without a saved config; **And** the MCP icon masks `currentColor`.
**Given** connectors backend trả về 5xx hoặc connector health endpoint timeout, **When** connectors page load, **Then** UI hiển thị `degraded` state với cached data và nút retry thay vì màn hình trắng.

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
**Given** agent gọi tool mà capability backing bị disabled hoặc MCP server trả về invalid response, **When** `nowing_memory_list`/`nowing_image_generate`/etc. thực thi, **Then** nó trả `capability_unavailable`/`invalid_response` error và không crash agent.

**Kỹ thuật (backfill):** Slice 0–3 đã implement + verified (selfcheck 42 tools, MCP suite 83 passed, ruff clean); Slice 4–5 còn pending chờ `bmad-dev-story`. Khác biệt với FR-8 (External MCP Connectors — Nowing tiêu thụ MCP third-party): story này là MCP server của Nowing (FR-29).
_FR-29 · FR-21/23 · FR-18/19/20 · FR-32/33/34 · AD-7 · story file `7-7-mcp-server-tool-expansion.md`._

---

## Epic 8: Platform Operations (Billing / Usage / Token)
### Story 8.3: Usage & Credit Dashboard  `[DONE per sprint-status: 8-3]`
As a user,
I want dashboard xem usage/chi phí theo workspace/model/thời gian,
So that tôi hiểu mình tiêu gì (dữ liệu `TokenUsage`/`credit_micros_balance` đã có, thiếu UI).

**Acceptance Criteria:**
**Given** `TokenUsage` đã ghi, **When** mở usage dashboard, **Then** hiển thị aggregate theo workspace/model/`usage_type`/thời gian (gồm `memory_create`).
**And** buy-credits page hiển thị lịch sử, không chỉ current balance.
**Given** `TokenUsage` rỗng cho workspace/model/time range chọn hoặc credit wallet bị thiếu, **When** dashboard load, **Then** UI hiển thị `no_data`/`missing_wallet` state thay vì màn hình trắng.
**UX Notes (nhẹ, brownfield):** bám pattern settings/buy-credits page hiện có trong `nowing_web/`; dashboard = bảng + biểu đồ aggregate theo workspace/model/thời gian. Cần contract đầy đủ → `bmad-ux`.
_NFR-7 · FR-31 · AD-DEFER-5._

### Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit  `(mới)`  `[DONE — 59 tests passed; gate before auto-extract goes to prod]`
As a workspace owner,
I want spend budget cap + wallet pre-check + rate-limit theo thời gian cho auto-extract,
So that chi phí dự đoán được khi auto-extract bật.

**Acceptance Criteria:**
**Given** một workspace, **When** vượt **spend budget cap** trong kỳ HOẶC ví không đủ (wallet pre-check **TRƯỚC** khi enqueue LLM call phụ), **Then** extraction bị skip + log, không âm thầm đốt credit.
**And** rate-limit theo thời gian (ngoài `MAX_ITEMS=3` sẵn có); **And** edge anonymous-chat (FR-17) attribution rõ ràng.
**Given** ví credit rỗng hoặc rate-limit window bị vượt, **When** yêu cầu auto-extract, **Then** extraction bị skip và emit counter `wallet_empty`/`rate_limited` thay vì âm thầm đốt credit.
_AR-6 · RS-1. **Dep: 8.8** (kill-switch/flags đã có)._

### Story 8.8: Auto-Extract Kill-Switch & Safe Default  `(mới)` `(đánh lại số từ 8.4a — C-C)`  `[DONE — flags MEMORY_AUTO_EXTRACT_ENABLED (global) + workspaces.memory_auto_extract_enabled (per-ws) đã có]`
As a platform engineer,
I want kill-switch tin cậy + default an toàn cho auto-extract,
So that chi phí per-turn không kiểm soát dừng ngay lập tức.

**Acceptance Criteria:**
**Given** `MEMORY_AUTO_EXTRACT_ENABLED` + `workspaces.memory_auto_extract_enabled`, **When** đặt global kill-switch OFF, **Then** không task extraction nào enqueue ở bất kỳ turn (verify `assistant_finalize`); không cần redeploy; có test.
**Given** một workspace, **When** owner tắt riêng, **Then** extraction dừng cho workspace đó, không ảnh hưởng khác.
**Given** default an toàn, **When** tạo workspace mới, **Then** `memory_auto_extract_enabled` default phản ánh policy đã chốt (OFF tới khi gates ship).
**Given** flag `MEMORY_AUTO_EXTRACT_ENABLED` bị thiếu trong config hoặc `workspaces.memory_auto_extract_enabled` là `NULL`, **When** đánh giá auto-extract, **Then** mặc định là `OFF` và log `missing_flag` để extraction không chạy bất ngờ.
_AR-6 · FR-15. **Dep: none** (P0)._

### Story 8.9: Memory Cost/Turn Observability  `(mới)` `(đánh lại số từ 8.5 — C-C)`  `[DONE — code-complete qua sprint story 8-4 observability-logging]`
As a team,
I want cost/turn của memory extraction/recall được đo,
So that định lượng unit economics cloud trước khi pricing (SM-C2/RS-10).

**Acceptance Criteria:**
**Given** turn có extraction/recall, **When** hoàn tất, **Then** ghi span + cost với `usage_type="memory_create"`, attribute workspace+user.
**And** aggregate cost/turn (auto-extract ON vs OFF) đo trên staging/beta → input cho pricing.
**Given** extraction/recall span thiếu `workspace_id`/`user_id` hoặc cost là `null`, **When** observability aggregate chạy, **Then** row được tag `invalid` và route đến dead-letter table thay vì làm corrupt dashboard.
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
**Given** docs sync phát hiện placeholder token hoặc tên feature đã bị removed, **When** CI docs-drift check chạy, **Then** build fail với `docs_drift_detected` và chỉ đến file vi phạm.

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

### Story 8.11-followup: Admin Model Config Hardening  `(tech debt)`  `[backlog]`
As a platform operator,
I want admin model config có provider validation + pagination,
So that config không corrupt và list không chậm khi scale.

**Acceptance Criteria:**
**Given** provider name, **When** create/update connection, **Then** validate against known provider list (enum).
**Given** >1000 connections, **When** list, **Then** hỗ trợ pagination (limit/offset).

_Source: code review defer items từ 8-11. Priority: P3. Effort: 1 day. Trigger: khi connections > 1000. API key trim + provider change block đã patched._

---

### Story 8.12: Workspace Limits  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-12]`
As a platform admin,
I want to enforce per-workspace limits (documents, members, storage, runs),
So that I can offer tiered plans and prevent abuse on the cloud offering.

**Acceptance Criteria:**
**Given** a workspace on a free/team/enterprise plan, **When** it reaches a limit, **Then** subsequent operations are blocked with a clear upgrade message.
**Given** the workspace settings, **When** an admin opens it, **Then** they see current usage vs limits and an upgrade CTA.
**And** limits are enforced backend-side (not just UI); **And** anonymous/self-host defaults keep existing behavior.
**Given** workspace chưa có plan cấu hình hoặc metadata limit bị thiếu, **When** operation bị gate, **Then** nó bị denied với `plan_missing` và message rõ ràng yêu cầu admin cấu hình.

**Kỹ thuật:** add `WorkspaceLimit` / plan config, gate document upload, member invite, and run creation; expose usage/limit API; build settings UI.
_FR-3 · FR-30 · upstream PR #1609._

### Story 8.13: PostHog Product Analytics  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-13]`
As a product team,
I want PostHog analytics integrated into the web app,
So that I can understand user flows, feature adoption, and retention.

**Acceptance Criteria:**
**Given** `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` are configured, **When** the web app loads, **Then** PostHog is initialized and captures pageviews and key events.
**Given** a superuser, **When** viewing analytics, **Then** identifiable data is hashed/anonymized and no API keys or workspace content is sent.
**Given** `NEXT_PUBLIC_POSTHOG_KEY` bị thiếu hoặc PostHog unavailable (network error/5xx), **When** web app load, **Then** analytics initialization fail gracefully, pageviews vẫn hoạt động, và log `posthog_unavailable`.

**Kỹ thuật:** add `@posthog-js` (if not already), initialize in layout, wrap key events, keep server-side observability separate.
_NFR-3 · upstream PR #1622._

## Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`
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

> **🆕 Extend 2026-08-08 (SCP `sprint-change-proposal-2026-08-08.md`):** Story 9.3 built async door + notification nhưng **result + citations không flow back to chat thread**. `run.finished` event chỉ chứa metadata (`run_id`, `status`, `item_count`) — không chứa output hay `sources[]`. Chat streaming flow (`event_relay.py`) **không subscribe `run_event_bus`**. Khi async research hoàn tất (57-198s), user phải navigate runs page để xem result — FR-24 "câu trả lời tổng hợp có trích dẫn" **VIOLATED** cho async mode. Append ACs dưới đây.

**Acceptance Criteria (appended 2026-08-08 — Async research result + citation delivery to chat):**

**Given** an async ChainLens research run completes successfully, **When** `run.finished` fires, **Then** the research answer + sources[] are delivered back to the originating chat thread as a new assistant message with `[citation:url]` markers.
**Given** the async run was initiated from a chat turn, **When** it completes, **Then** the user sees the synthesized answer with clickable URL citation chips in the chat thread (not just the notifications bell).
**Given** the async run fails or degrades, **When** `run.finished` fires with `status=error`, **Then** a message appears in the chat thread explaining the failure with the `next_action` guidance.
**Given** the user has closed the chat tab, **When** the async run completes, **Then** the notification (existing `notifications` table) includes `run_id` + `thread_id` so the user can navigate to the result.
**And** the existing async door (`?mode=async` → 202 + SSE `runs/{id}/events`) continues to work unchanged for REST API callers.
**And** `WEB_RESULT` citations are registered from `ResearchOutput.sources[]` when the result is delivered (reuse `register_web_citations()` from Story 3.15 extension).

**Kỹ thuật (appended):** design decision needed — 3 options: (A) chat streaming subscribes to `run_event_bus` for run_ids started during the turn; (B) notification → frontend fetches run detail → renders inline (recommended — robust when tab closed, reuses notification infra); (C) agent "resume" turn when run completes (best UX but extra LLM call). AD-17 amendment needed: add piece (c) to "Three Missing Pieces" — deliver result + WEB_RESULT citations back to chat thread.

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
>
> **Approval criteria (readiness audit 2026-08-08):** Story 9.5 requires a new SCP before dev can start. SCP must address: (1) self-host demand evidence (≥5 self-host instances requesting deep research), (2) pricing model (metered per-call vs subscription), (3) abuse prevention design, (4) revenue attribution to Nowing Cloud vs engine. Without SCP approval, this story remains deferred indefinitely.

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

### Story 9.6-followup: Re-Validation Hardening  `(tech debt)`  `[backlog]`
As a platform engineer,
I want revalidation có DB constraint + concurrent safety + output limits + test robustness,
So that confidence không corrupt và revalidation robust dưới load.

**Acceptance Criteria:**
**Given** Memory.confidence, **When** set value, **Then** DB CHECK constraint đảm bảo [0.1, 1.0] (Alembic migration).
**Given** concurrent revalidation trên cùng memory, **When** 2 requests chạy cùng lúc, **Then** dùng SELECT FOR UPDATE tránh race.
**Given** capability output > 100KB, **When** revalidate, **Then** truncate text trước khi compare (tránh OOM).
**Given** test_memory_revalidation.py, **When** test failure path, **Then** assert mock executor call_count > 0.

_Source: code review defer items từ 9-6b. Priority: P2. Effort: 2-3 days. Trigger: khi có automated revalidation._

### Story 9.6c: Memory Provenance End-to-End Revalidation Gate  `(mới 2026-08-08)`  `[ready-for-dev]`

As a platform engineer,
I want an E2E gate proving every scraper-derived memory carries a self-contained recipe and can be re-validated after its source `Run` is gone,
So that `AD-11.1` / `FR-39` is not silently regressed.

**Acceptance Criteria:**

**Given** a scraper run produces a memory,
**When** the memory is created,
**Then** `source_type = SCRAPER_RUN`, `source_run_id`, `source_capability`, and `source_input` are populated from the `Run`.

**Given** a memory created from a run 31 days ago whose `Run` row has been cleaned up,
**When** `POST /workspaces/{id}/memories/{memory_id}/revalidate` is called,
**Then** the capability re-executes using only `source_capability` + `source_input`; the call succeeds and updates `confidence` or creates a `MemoryVersion`.

**Given** a memory with `source_type` other than `SCRAPER_RUN` and no recipe,
**When** revalidate is called,
**Then** it returns `not_revalidatable` with 422, not 500.

**Given** a re-validate call completes,
**When** metering is checked,
**Then** it is charged as a normal capability call via `charge_capability` (`AD-8`).
**Given** `Run` source bị thiếu và `source_capability`/`source_input` rỗng hoặc invalid, **When** `POST /workspaces/{id}/memories/{memory_id}/revalidate` được gọi, **Then** nó trả `not_revalidatable` với 422, không 500.

_Governed by `AD-11.1`, `FR-39`, `AD-8`._
---

## Epic 10: Connector & Scraper Expansion
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

**Given** `N` listings are scraped and normalized to `Chunk[]`, **When** the batch is ready, **Then** Nowing calls `POST /v1/ingest/scraper` on `chainlens-research` with `source: 'nowing_scraper'` and returns `ingestJobId` to the user/run.

**Given** duplicate listings and confidence scores, **When** the aggregator sends normalized `Chunk[]` to `chainlens-research`, **Then** deduplication and confidence metadata (`source_count`, `confidence_score`, `conflict_flags`) are returned as chunk metadata and are not stored in Nowing `Memory`/`ResearchThread` as a search corpus.
**Given** một nguồn (`batdongsan`, `chotot`, `muaban`) trả về 403/429/5xx hoặc listing set rỗng, **When** aggregator chạy, **Then** kết quả `degraded=true` với `degradation_reasons` và các source còn lại vẫn được ingest.

**Kỹ thuật (không phải AC):** thêm `app/services/bds_aggregator/` để normalize/dedupe listings rồi gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`; không mở rộng `Memory`/`ResearchThread` để lưu aggregated listing làm search corpus.
_FR-6 · FR-32 · FR-39 · AD-11.1 · `market-vietnam-real-estate-data-scraping-landscape-research-2026-08-03.md`._

### Story 10.5: Anti-Bot / CAPTCHA Screenshot Escalation  `(mới 2026-08-08)`  `[ready-for-dev]`

As a scraper operator,
I want CAPTCHA or anti-bot blocks to be captured as a screenshot and surfaced in the Inbox for human review,
So that we can audit blocks and decide whether to rotate credentials, proxy, or rate-limit.

**Acceptance Criteria:**

**Given** a scraper fetcher detects a CAPTCHA/anti-bot challenge (HTTP 403/429 with challenge page, HTML containing "captcha", "robot check", or known anti-bot markers),
**When** the capability executor handles the failure,
**Then** it captures a screenshot of the page, uploads it to durable storage, and creates an `InboxItem` with kind `anti_bot_escalation`, linking the run id, capability, and screenshot URL.

**Given** the `InboxItem` is created,
**When** an admin opens the Inbox,
**Then** they see the item with metadata (domain, capability, timestamp, screenshot thumbnail, run id) and can mark it resolved/retry.

**Given** a scraper hits an anti-bot escalation,
**When** the capability returns to the user/agent,
**Then** it returns `degraded=true` with a clear `reason` and `next_action` guidance, and does not crash or silently return empty.

**Given** the screenshot storage is unavailable,
**When** the escalation occurs,
**Then** the Inbox item is still created without the screenshot, and a counter `anti_bot_screenshot_failure` is emitted.

_Governed by `AD-19`, `AD-3`, `AD-16`._

### Story 10.6: Chợ Tốt Multi-Category Scraper `[ready-for-dev]`

As a researcher using the Chợ Tốt scraper,
I want to scrape listings from any major vertical (`xe cộ`, `điện tử`, `việc làm`, `đồ gia dụng`, `vật nuôi`, `dịch vụ`, `thời trang`, v.v.) in addition to real estate,
So that one scraper foundation returns typed, useful data for each category instead of a BĐS-shaped record full of nulls.

**Acceptance Criteria:**
**Given** the existing Chợ Tốt BĐS scraper uses `gateway.chotot.com/v1/public/ad-listing` with `cg` and `st` parameters,
**When** Story 10.6 is complete,
**Then** the fetcher supports a `category` input that maps to the correct `cg`, `st`, and detail URL origin for each vertical, and the BĐS `property_type` mapping keeps working.

**Given** public `cg` codes for each vertical (`2010/2020` BĐS, `4010/4020` vehicles, `5000` electronics, `7000` home goods, `9000` fashion, v.v.),
**When** the mapping module is loaded,
**Then** it exposes a deterministic lookup from stable slugs (`cars`, `motorbikes`, `electronics`, `jobs`, `home_goods`, `pets`, `fashion`, `services`) to `cg` and per-vertical `listing_type` default.

**Given** an unsupported category slug,
**When** the scraper runs,
**Then** it fails fast with `category_not_supported` and does not silently fall back to BĐS.

**Given** a listing is parsed,
**When** `detail_url` is built,
**Then** it uses the vertical's canonical origin (`nhatot.com`, `xe.chotot.com`, `vieclamtot.com`, `www.chotot.com`, v.v.) and `list_id` as `/{list_id}.htm` (best-effort; redirect acceptable), not hardcoded to `nhatot.com`.

**Given** the public `loadRegions` endpoint returns the shared region/area tree,
**When** the scraper resolves `city`/`district` for any supported category,
**Then** it reuses the existing `_resolve_region_v2` / `_resolve_area_v2` logic. A per-vertical region loader is added only if a real category proves the tree differs.

**Given** the current `ChototBdsListing` schema with BĐS-only fields (`area`, `rooms`, `floors`, `toilets`, `property_type`),
**When** Story 10.6 is complete,
**Then** there is a generic `ChototListing` schema with common fields plus a per-category `attributes: dict[str, Any]` bag for vertical-specific fields.

**Given** a vehicle ad from `xe.chotot.com`,
**When** it is parsed,
**Then** `attributes` includes `make`, `model`, `year`, `mileage`, `fuel_type`, `transmission`, `condition`, `vehicle_type` where present.

**Given** a job ad from `vieclamtot.com`,
**When** it is parsed,
**Then** `attributes` includes `salary_min`, `salary_max`, `salary_string`, `job_type`, `company_name`, `experience`, `education`, `benefits` where present.

**Given** an electronics / home goods / fashion ad,
**When** it is parsed,
**Then** `attributes` includes `brand`, `condition`, `warranty`, `accessories` where present; no BĐS-only fields are emitted as null.

**Given** the gateway returns an unmapped `cg`,
**When** the listing is parsed,
**Then** `parse_generic` captures fields into `attributes`, sets `category="unknown"`, and the executor marks the run `degraded` and does not bill the listing.

**Kỹ thuật (không phải AC):** Spike `cg`/`st`/region/detail URL/phone behavior; replace `_PROPERTY_TYPE_TO_CG` with `_CATEGORY_CONFIG` dict; refactor `scraper.py` to `scrape_chotot`; move `_build_detail_url`; update `schemas.py` with `ChototListing` and mark `ChototBdsListing` deprecated; implement lightweight parser dispatch (`parse_vehicle`, `parse_job`, `parse_general_goods`, `parse_generic`). Tests for mapping, parsers, and one live integration.

_See full story file: `implementation-artifacts/stories/10-6-chotot-multi-category-scraper.md`._

### Story 10.7: Chợ Tốt Multi-Category Capability and Billing `[ready-for-dev]`

As a workspace owner,
I want a single `chotot.scrape` capability that accepts any supported category and bills per returned listing on the correct meter,
So that users can research Chợ Tốt vehicles, jobs, electronics, and goods without separate capabilities or mis-billed BĐS rates.

**Acceptance Criteria:**
**Given** the existing `chotot_bds.scrape` capability is registered with `BillingUnit.CHOTOT_BDS_ITEM`,
**When** Story 10.7 is complete,
**Then** a single `chotot.scrape` capability is registered with `category` as required input, and `chotot_bds.scrape` is kept as a deprecated alias.

**Given** `chotot.scrape` runs with `category=cars` and returns 12 listings,
**When** billing is recorded,
**Then** `TokenUsage.usage_type="chotot_item"`, `cost_micros = 12 × CHOTOT_SCRAPE_MICROS_PER_ITEM`, and `call_details` includes `category="cars"`.

**Given** `chotot.scrape` runs with `category=electronics` and returns 0 listings due to a block,
**When** the output is `degraded=true`,
**Then** `cost_micros=0` and `degradation_reason` is preserved.

**Given** `chotot.scrape` returns a listing with `category="unknown"`,
**When** billing is computed,
**Then** that listing is not counted and `degradation_reason="unknown_category"` is returned.

**Given** the pre-flight wallet gate `gate_capability`,
**When** `chotot.scrape` is called with `max_items=20` and `category=jobs`,
**Then** the gate reserves `20 × CHOTOT_SCRAPE_MICROS_PER_ITEM` micros.

**Given** existing `chotot_bds.scrape` consumers,
**When** the new capability is live,
**Then** `chotot_bds.scrape` keeps working for at least one release as an alias, with a deprecation note in the docs.

**Kỹ thuật (không phải AC):** Architecture decision recorded for single `chotot.scrape`; add `BillingUnit.CHOTOT_ITEM` and `CHOTOT_SCRAPE_MICROS_PER_ITEM` config; update `app/capabilities/core/billing.py`; register/alias in `definition.py`, `executor.py`, `schemas.py`; add docs and `.env.example`. Unit + integration + regression tests.

_See full story file: `implementation-artifacts/stories/10-7-chotot-multi-category-capability.md`._

---

## Epic 11: Telegram Automation & Bot `[done]`
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

## Epic 20: Nowing Ecosystem Integration — Feed & Recall from chainlens-research
### Story 20.4: Service-to-Service Auth + Cost Ledger Sync  `(mới 2026-08-08)`  `[done]`

As a platform engineer,
I want secure service-to-service auth and a shared cost envelope between Nowing and `chainlens-research`,
So that `chainlens-research` can meter usage and Nowing can bill the user.

**Acceptance Criteria:**

**Given** any `chainlens-research` internal endpoint call,
**When** the request leaves Nowing,
**Then** it carries a Bearer service token + `X-Correlation-Id` + `X-Workspace-Id` headers.

**Given** `chainlens-research` receives the request,
**When** validating,
**Then** it checks the service token against a shared secret; it rejects with `401` if missing/invalid.

**Given** a search/gap-fill/ingest call completes,
**When** `chainlens-research` reports `costDollars`,
**Then** Nowing writes a `TokenUsage` record with `usage_type` mapped from the operation (e.g. `chainlens_search`, `chainlens_gap_fill`, `chainlens_ingest`), linked to `workspace_id` and `run_id`.

**Given** a `costDollars` value,
**When** converting to credits,
**Then** Nowing applies the same `costDollars → micros` rate as external provider calls (`AD-8`).

**Given** the service token is within 30 days of expiration or `chainlens-research` returns `401` due to token expiry,
**When** the next outbound request is made,
**Then** `ChainLensServiceAuth` rotates the token from a secure secret store and updates the stored token without dropping the in-flight request.

**Given** token rotation fails,
**When** `NowingIngestService` / gap-fill / private-provider calls need auth,
**Then** the request fails open with `service_auth_unavailable` and a `chainlens_auth_failed` counter is emitted; no user data is sent with an invalid token.

_Governed by `AD-3`, `AD-4`, `AD-5`, FR-61, `AD-8`._

### Story 20.1: Nowing Scraper `to_chunks()` + `NowingIngestService`  `(mới 2026-08-08)`  `[done]`

As a Nowing user / chat user,
I want my scraper data to be searchable through chainlens,
so that the agent can answer with fresh data.

**Acceptance Criteria:**

**Given** a scraper result (e.g. `batdongsan` listings, `vn_jobs.aggregate` entities),
**When** `to_chunks()` is called,
**Then** it returns `Chunk[]` with `metadata` containing: `source: 'nowing_scraper'`, `sourceId` (stable fingerprint), `domain`, `fetchedAt`, `contentType`, and `canonicalEntityId` if applicable.

**Given** `Chunk[]` from any scraper,
**When** `NowingIngestService.ingest(scraper_id, chunks)` is called,
**Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, `source: 'nowing_scraper'`, and the chunk batch; it returns `ingestJobId` and stores the job mapping in `Nowing` Postgres.

**Given** a batch larger than 1,000 chunks,
**When** ingesting,
**Then** `NowingIngestService` paginates the batch and tracks a parent `ingestJobId` plus child job IDs.

**Given** `chainlens-research` returns `409` for duplicate `sourceId`,
**When** handling the response,
**Then** `NowingIngestService` maps duplicates to `noop` status and continues the rest of the batch.

**Given** a scraper result is missing required fields (`title`, `company`, `location` for jobs; equivalent for other domains),
**When** `to_chunks()` is called,
**Then** it raises `ChunkValidationError` with field details and the batch is not sent.

**Given** `chainlens-research` returns `5xx` or times out,
**When** `NowingIngestService.ingest()` is called,
**Then** it retries with exponential backoff (max 3 attempts) and stores the failed batch in a dead-letter queue; after max retries it marks the job `failed` and emits a `chainlens_ingest_failed` counter.

**Given** a chunk has `content` larger than 8,000 tokens,
**When** `to_chunks()` is called,
**Then** it splits into multiple `Chunk` objects with sequential `metadata.chunkIndex` / `metadata.chunkTotal` and stable `sourceId` suffixes.

**Given** `to_chunks()` produces a `Chunk[]`,
**When** the batch is sent to `chainlens-research`,
**Then** each `Chunk` conforms to the canonical schema and `source` enum defined in `chainlens-research` Story 47-1 (FR-62, AD-35); if `chainlens-research` rejects a chunk for schema violation, `NowingIngestService` logs the first failing chunk and fails the batch.

**Kỹ thuật (không phải AC):** Tách `to_chunks()` thành mixin hoặc helper trong `app/services/scraper_chunks/`; `NowingIngestService` nằm ở `app/services/chainlens/ingest.py`. Auth qua `ChainLensServiceAuth` (`Story 20.4`).

_Governed by `AD-34`, `AD-35`, FR-58, FR-62._


### Story 20.2: Gap-Fill Caller + Cost Allocation (Nowing side)  `(mới 2026-08-08)`  `[done]`

As a chat user,
I want the agent to ask `chainlens-research` to index missing data on demand,
So that the answer does not say "I don't know" when the data is available on the public web or via a Nowing scraper.

**Acceptance Criteria:**

**Given** a user query in chat,
**When** `chainlens-research` `POST /api/v1/search` returns a `gap-fill-needed` signal (or empty result with `suggested_domains`),
**Then** the chat orchestrator calls `POST /v1/gap-fill` with `{ query, domains?, source?, priority }` and `workspace_id`.

**Given** a gap-fill request,
**When** `chainlens-research` decides the gap is in a domain owned by Nowing (e.g. `batdongsan`, `vn_jobs`),
**Then** `chainlens-research` calls `POST /v1/scraper/{scraper_id}/run` on Nowing (internal), Nowing runs the scraper, and the result is pushed back to `chainlens-research` via `Story 20.1`.

**Given** the final `SSE done` frame,
**When** `costDollars` is reported,
**Then** Nowing bills the user once for the total (search + gap-fill + scraper usage), and internal cost allocation is recorded separately for Nowing scraper infra vs `chainlens-research` indexing.

**Given** gap-fill takes longer than 60s,
**When** the chat orchestrator waits,
**Then** it uses the async research door (`AD-17`, `?mode=async`) and returns a `run_id` to the user; the result arrives via SSE `run_event_bus`.

_Governed by `AD-4`, FR-59, `AD-8`._


### Story 20.3: `NowingPrivateProvider` for `POST /v1/private-data/search`  `(mới 2026-08-08)`  `[done]`

As a Nowing user,
I want my private data to stay in Nowing while still being used for answers,
so that privacy is preserved.

**Acceptance Criteria:**

**Given** `chainlens-research` calls `POST /v1/private-data/search` with `{ query, userId, workspaceId, connectorId?, sources? }`,
**When** the request arrives,
**Then** Nowing validates the service auth token and `workspaceId` RLS, then runs the search against the user's private data sources.

**Given** private search executes,
**When** results are collected,
**Then** it returns `SearchProviderResult { chunks: Chunk[], costDollars? }` with `metadata.source = 'private_provider'` and `sourceId` scoped per document/connector.

**Given** a `connectorId` is provided,
**When** searching,
**Then** only data from that connector is returned, and OAuth tokens are fetched from `Nowing` Postgres (never sent to `chainlens-research`).

**Given** the request has no matching data,
**When** complete,
**Then** it returns `chunks: []` and `costDollars: 0`, not 404.
**Given** service auth token bị thiếu/invalid hoặc workspace RLS check fail, **When** `POST /v1/private-data/search` được gọi, **Then** nó trả 401/403 và không leak private chunks.

_Governed by `AD-5`, FR-60, `AD-16`._
---
## Epic 12: HR/Recruitment Vertical — Vietnam Job Market Pilot

### Story 12.0: ToS & Legal Review `[PREREQUISITE — approved by legal counsel 2026-08-08]`

As a product owner,
I want to confirm ToS and legal classification for VietnamWorks, TopCV, and ITviec,
So that we do not build or launch a non-compliant pilot.

**Acceptance Criteria:**
- **Given** the source list, **When** ToS review is performed, **Then** each source's automated access / commercial use status is documented in `_bmad-output/planning-artifacts/legal/`.
- **Given** the pilot design, **When** legal counsel reviews, **Then** an opinion exists confirming Nowing is not classified as an "employment service provider" / "môi giới việc làm".
- **Given** a source is blocked by ToS or legal, **When** the decision is made, **Then** that source is removed from the default `sources` list and the implementation plan is updated.
- **Given** legal approval, **When** the pilot launches, **Then** public messaging clearly positions Nowing as a research/memory layer, not a job board/ATS/intermediary.

_Kỹ thuật (không phải AC):_ No code. Output: legal review memo + ToS decision log.

> ✅ **Completed 2026-08-08.** Legal counsel approved all 3 sources (VietnamWorks, TopCV, ITviec). Nowing confirmed not classified as employment service provider. See `legal/tos-legal-epic-12-hr-vertical-2026-08-05.md` (closed) and `legal/tos-review-memo-epic-12-2026-08-08.md` (analysis). Epic 12 P0 unblocked — Stories 12.1-12.5 may proceed.

_FR-43..FR-47 · NFR-11 · OQ-8 · AD-26_

### Story 12.1: VietnamWorks Scraper `[ready-for-dev P0]`

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

_FR-43 · AD-3 · AD-16 · AD-22 · `technical-spike-vietnamworks-api-2026-08-05.md`._

### Story 12.2: TopCV Scraper `[ready-for-dev P0]`

As a recruiter,
I want to search TopCV job postings,
So that I can access the largest local Vietnamese job board.

**Acceptance Criteria:**
- **Given** a query + optional city filter, **When** `topcv.scrape` runs, **Then** it fetches TopCV search and detail pages.
- **Given** a Cloudflare/anti-bot challenge, **When** encountered, **Then** the scraper uses warmed browser/headless/proxy and returns `degraded=true` with reason on block.
- **Given** a successful fetch, **When** parsed, **Then** it returns typed `JobItem` with title, company, location, salary (if visible), JD, requirements, skills, post date.
- **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.TOPCV_JOB`), capability registry, MCP, and REST routes.

_Kỹ thuật (không phải AC):_ `app/proprietary/platforms/topcv/` (BSL 1.1 fetcher/parser/anti-bot) + `app/capabilities/topcv/scrape/` (Apache-2.0 capability). Anti-bot POC là hard gate; không merge trước khi POC pass.

_FR-44 · AD-3 · AD-16 · AD-19 · AD-23 · `technical-spike-topcv-itviec-2026-08-05.md`._

### Story 12.3: ITviec Scraper `[ready-for-dev P0]`

As a tech recruiter,
I want to search ITviec job postings,
So that I can monitor IT/AI hiring trends.

**Acceptance Criteria:**
- **Given** a query, **When** `itviec.scrape` runs, **Then** it fetches `https://itviec.com/it-jobs/{query}` (server-rendered HTML, no CAPTCHA in spike).
- **Given** the list page, **When** parsed, **Then** it extracts 20 job cards per page via selectors `job-card ipt-2`, `h3/a`, `employer-name`.
- **Given** a detail page, **When** parsed, **Then** it extracts title, company, location, work mode, posted time, skills, job domain, JD.
- **Given** salary is hidden, **When** displayed as `Sign in to view salary`, **Then** salary is parsed from title when possible or marked low-confidence.
- **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.ITVIEC_JOB`), capability registry, MCP, and REST routes.
- **Given** ITviec server trả về 403 anti-bot challenge, 5xx error, hoặc detail page selectors không còn match, **When** scraper chạy, **Then** nó trả `degraded=true` với `degradation_reason: anti_bot`/`parse_failed` và không retry vô hạn.

_Kỹ thuật (không phải AC):_ `app/proprietary/platforms/itviec/` (BSL 1.1 fetcher/parser) + `app/capabilities/itviec/scrape/` (Apache-2.0 capability). Rate-limit + user-agent rotation + circuit-breaker.
_FR-45 · AD-3 · AD-16 · AD-23 · `technical-spike-topcv-itviec-2026-08-05.md`._

### Story 12.4a: Vietnam Job Listing Normalization `[ready-for-dev P0]`

As a research analyst,
I want the Vietnamese job market data from multiple sources normalized into a common schema,
So that downstream deduplication and indexing can work on a single shape.

**Acceptance Criteria:**
- **Given** a query and optional filters (`location`, `salaryMin/Max`, `employmentType`, `experienceYears`), **When** `vn_jobs.aggregate` is called, **Then** it fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` (default all 3; source list configurable; `maxItemsPerSource` and `maxPages` caps enforced).
- **Given** results from multiple sources, **When** normalized, **Then** they map to `VnJobAggregatedListing` with `salary`, `location`, `employment_type`, `experience`, `posted_at`, and `source` fields.
- **Given** a source fails or is blocked by anti-bot, **When** aggregation completes, **Then** it returns `degraded=true` with `degradation_reasons` drawn from `{SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}` and `degraded_source_ids`; successful source listings are still normalized.

### Story 12.4b: Vietnam Job Deduplication, Confidence & Conflict Detection `[ready-for-dev P0]`

As a research analyst,
I want duplicate job listings merged and conflicts surfaced,
So that the agent presents a trustworthy single answer with source transparency.

**Acceptance Criteria:**
- **Given** normalized listings, **When** deduplicated, **Then** it matches by `company` + `title` + `location` + `posted_at` (±3 days) across sources; fuzzy title matching uses Jaro-Winkler ≥ 0.85 and location normalization uses `app/services/location_normalize/`.
- **Given** two listings matched with salary difference ≤ 10%, **When** compared, **Then** `confidence_score ≥ 0.8` and `salary_consistency_score = stable`; the aggregated record is kept as a single record with `metadata.source_count` and `metadata.confidence_score`.
- **Given** two listings matched with salary difference > 20% or location mismatch, **When** compared, **Then** it sets `conflict_flag = SALARY_MISMATCH` or `LOCATION_MISMATCH`, lowers `confidence_score` to 0.5–0.7, and preserves both source records so `chainlens-research` can display conflict metadata.

### Story 12.4c: PII Redaction for Job Data Chunks `[ready-for-dev P0]`

As a workspace owner,
I want personal information removed from job descriptions before storage or ingest,
So that Nowing does not retain unconsented PII.

**Acceptance Criteria:**
- **Given** PII (phone, email, person names) is found in `job_description` or `job_requirement`, **When** chunks are built, **Then** AD-25 redaction is applied before any data is sent to `chainlens-research` or stored in `Memory`.
- **Given** redaction completes, **When** the chunk is persisted or sent, **Then** it contains only masked/dropped PII and audit stats log counts (not values).

### Story 12.4d: Job Chunks Ingest to chainlens-research `[ready-for-dev P0]`

As a platform engineer,
I want normalized, deduplicated, redacted job listings handed off to `chainlens-research` reliably,
So that the research index stays fresh without building a local corpus.

**Acceptance Criteria:**
- **Given** the aggregator has normalized listings, **When** `to_chunks()` is called, **Then** each listing becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, `sourceId` (stable: `sha256(company|title|location|posted_at)`), `domain`, `fetchedAt`, `contentType: 'job'`, `salary`, `confidence_score`, `salary_consistency_score`, and `conflict_flags`.
- **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, and the batch; it returns `ingestJobId` and stores the job mapping in Nowing Postgres.
- **Given** `chainlens-research` returns `5xx` or times out, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts) and stores the failed batch in a dead-letter queue; after max retries it marks the job `failed` and emits a `chainlens_ingest_failed` counter.

### Story 12.4e: Vietnam Job Aggregator Exposure (REST / MCP / Chat Agent) `[ready-for-dev P0]`

As a research analyst,
I want to call the job aggregator from chat, MCP, and REST,
So that I can ask job market questions anywhere I work.

**Acceptance Criteria:**
- **Given** the aggregator is exposed, **When** called via REST, MCP (`nowing_vn_jobs_aggregate`), or chat agent, **Then** it returns `VnJobAggregateOutput { items: VnJobAggregatedListing[], degraded, degradationReasons, sourceBreakdown, costMicros, ingestJobId }`; it does not query a local Nowing search corpus.
- **Given** `to_chunks()` produces a `Chunk[]`, **When** the batch is sent to `chainlens-research`, **Then** each `Chunk` conforms to the canonical schema and `source` enum defined in `chainlens-research` Story 47-1 (FR-62, AD-35); if `chainlens-research` rejects a chunk for schema violation, `NowingIngestService` logs the first failing chunk and fails the batch.

### Story 12.5: PII Redaction for Job Data `[ready-for-dev P0]`

As a workspace owner,
I want job postings to be scanned for personal information before storage,
So that Nowing does not accidentally retain candidate PII.

**Acceptance Criteria:**
- **Given** `job_description` / `job_requirement` from any source, **When** PII redaction runs, **Then** it detects Vietnamese phone numbers and email addresses via regex.
- **Given** person names in JD text, **When** detected, **Then** it flags via NER/heuristic and masks or drops the field.
- **Given** detected PII, **When** logged, **Then** only counts are recorded (no values).
- **Given** redaction runs, **When** storing to memory, **Then** the full raw JD is not stored unredacted.
- **Given** redaction regex thiếu pattern số điện thoại Việt Nam hoặc input JD rỗng, **When** PII redaction chạy, **Then** nó trả `invalid`/`empty` và raw JD không được lưu unredacted.

_Kỹ thuật (không phải AC):_ Shared PII pipeline in `app/services/pii/` or inside jobs aggregator. Unit tests for representative samples from VietnamWorks, TopCV, ITviec.
_FR-47 · NFR-11 · OQ-3 · `feature-brief-hr-vertical-vietnam-2026-08-05.md`._

> **Boundary note (2026-08-10):** Epic 12 outputs are research/job-market data with PII redaction. They are not reused as lead-enrichment contact data for Epic 21. Lead gen uses separate data sources and a separate PII/consent policy (SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`).

---

### Story 12.6: Saved Searches `[P0 — must ship before 12.9]`

As a researcher,
I want to save complex search queries and auto-run them on schedule,
So that I always have fresh results without manual work.

**Acceptance Criteria:**
- **Given** a search query with filters, **When** saved, **Then** it persists with `schedule: 'daily' | 'weekly' | 'none'`, `timezone`, and `enabled` flag; it appears in my saved searches list.
- **Given** a saved search with `schedule='daily'`, **When** the automation scheduler triggers at the configured time (default 00:00 UTC), **Then** it runs as an Epic 6 automation via `RunService` and emits a run record.
- **Given** run N and run N+1 complete, **When** delta is computed, **Then** `new_items = source_ids in run N+1 not present in run N` (by `sourceId`); `removed_items` and `changed_items` are also tagged.
- **Given** `new_items > 0`, **When** the run completes, **Then** a notification is delivered via the configured channel (in-app, email, Telegram) with a link to the saved search and a summary count.
- **Given** the saved search run fails or returns `degraded=true`, **When** it completes, **Then** the notification states the failure/degraded state and `degradation_reasons`, and the next scheduled run still fires unless `enabled=false`.

**Validation:**
- Unit test: `test_saved_search_crud.py` — create/update/delete saved searches
- Integration test: `test_saved_search_schedule.py` — scheduled execution works
- Integration test: `test_saved_search_delta.py` — delta calculation correct

_AD-33 (Generic Alert Engine — Saved Search AlertRule template)._

### Story 12.7: Property Price Alerts `[DROPPED 2026-08-08]`

> **DROPPED per SCP 2026-08-08.** Nowing does not build canonical property entities. Property price alerting may be implemented on `chainlens-research` index data in a future Phase 2.

_As originally scoped, this alert required `canonical_entities` storage which is no longer built in Nowing._

### Story 12.8: Cross-Source Entity Timeline `[DROPPED 2026-08-08]`

> **DROPPED per SCP 2026-08-08.** Nowing does not build canonical entity storage. Cross-source entity timelines (if needed) will be provided by `chainlens-research` as a product feature, not built as a Nowing index.

_As originally scoped, this timeline required `canonical_entities`, source-lineage and merge-history tables which are no longer built in Nowing._

---

### Story 12.9: Job Market Alerts `[P1 — depends on 12.6]`

As a job market researcher,
I want to receive alerts when new postings match my criteria,
So that I don't have to manually re-run searches every day.

> **Dependency:** Story 12.6 (Saved Searches) must ship first — alerts use saved search infrastructure.

**Acceptance Criteria:**
- **Given** a saved job search with filters (title, location, salary range), **When** a new posting matches, **Then** I receive an in-app notification.
- **Given** an alert is triggered, **When** I click it, **Then** I see the new matching results.
- **Given** multiple alerts, **When** viewed, **Then** they are grouped by search query with match count.
- **Given** saved job search bị xóa hoặc source scraper trả về `degraded=true` với không có posting mới, **When** alert job chạy, **Then** nó skip alert, log `search_missing`/`degraded_source`, và scheduler tiếp tục.
**Validation:**
- Unit test: `test_job_alert_matching.py` — new posting triggers alert
- Integration test: `test_job_alert_notification.py` — notification delivered

_AD-33 (Generic Alert Engine — AlertRule template, `new_items` diff strategy)._

## Epic 14: News Aggregation (Vietnam)

### Story 14.1: RSS Feed Integration `[P0]`

As a user,
I want news from major Vietnamese portals available in my workspace,
So that I can search and reference news articles via the Nowing chat agent.

**Acceptance Criteria:**
- **Given** RSS feeds are configured, **When** the system polls (every 15 min), **Then** new articles from VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet are fetched and parsed.
- **Given** an article is parsed, **When** it is normalized to a `Chunk`, **Then** `metadata` contains: `source: 'nowing_scraper'`, `sourceId` (stable URL hash), `domain` (e.g. `vnexpress.net`), `fetchedAt`, `contentType: 'news'`, `title`, `link`, `category`, `pubDate`, and `source` (portal name).
- **Given** a batch of news `Chunk[]`, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, and the batch; it returns `ingestJobId` and stores the job mapping in Nowing Postgres.
- **Given** a batch larger than 1,000 chunks, **When** ingesting, **Then** the service paginates the batch and tracks a parent `ingestJobId` plus child job IDs.
- **Given** `chainlens-research` returns `409` for a duplicate `sourceId`, **When** handling the response, **Then** the duplicate is mapped to `noop` status and the rest of the batch continues.
- **Given** `chainlens-research` returns `5xx` or times out, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts), stores the failed batch in a dead-letter queue, and after max retries marks the job `failed` and emits a `chainlens_ingest_failed` counter.
- **Given** the user searches for news, **When** the chat agent queries `chainlens-research` `POST /api/v1/search`, **Then** it returns indexed news articles with citations; Nowing does not search a local news corpus.

**Validation:**
- Integration test: `test_news_rss_integration.py` — all 4 portals polled
- Unit test: `test_news_to_chunks.py` — chunk metadata is complete and stable
- Integration test: `test_news_ingest_service.py` — `POST /v1/ingest/scraper` called with correct auth and batch; 409 and 5xx handled
- Integration test: `test_news_search_via_chainlens.py` — user query returns results from `chainlens-research`

_AD-34 · AD-35 · AD-25 · Method: RSS (official feeds, no anti-bot)_

### Story 14.2: News Entity Enrichment `[P1]`

As a researcher,
I want key entities (people, organizations, locations) attached to news chunks before they are indexed,
So that I can track mentions and trends via `chainlens-research` entity search.

**Acceptance Criteria:**
- **Given** a news article is parsed, **When** entity extraction runs, **Then** named entities (people, organizations, locations) are extracted with confidence scores.
- **Given** extracted entities, **When** the article is normalized to a `Chunk`, **Then** `metadata.entities` contains the entity mentions, types, and surface forms.
- **Given** a `Chunk` with `metadata.entities`, **When** it is ingested into `chainlens-research`, **Then** the canonical index stores and indexes the entity metadata; `chainlens-research` handles entity linking and disambiguation.
- **Given** entity tracking is active, **When** a user queries an entity in chat, **Then** the agent calls `chainlens-research` and returns mentioning articles with citations; no local entity table is built in Nowing.
- **Given** entity extraction model trả về empty entity list hoặc malformed JSON, **When** entity enrichment chạy, **Then** nó fallback về `metadata.entities` rỗng và article vẫn được indexed.
**Validation:**
- Unit test: `test_news_entity_extraction.py` — entity accuracy ≥ 0.85
- Integration test: `test_news_entity_chunk_metadata.py` — entities attached to chunk metadata
- Integration test: `test_news_entity_search_chainlens.py` — entity query returns indexed articles

_AD-34 · AD-35 · AD-25 (PII redaction for person names)_

---

### Story 14.3: News Alerts & Topic Monitoring `[P1]`

As a news researcher,
I want to monitor topics and receive alerts for new articles,
So that I stay informed without manually checking news sites.

**Acceptance Criteria:**
- **Given** a saved topic query (e.g., `"company X" OR "industry Y"`), **When** the scheduler triggers (daily default), **Then** the alert rule re-runs the RSS fetch, normalizes new articles to `Chunk[]`, and calls `NowingIngestService.ingest()` to send them to `chainlens-research`.
- **Given** the new run completes, **When** `chainlens-research` reports `ingestJobId` success, **Then** `new_items` are computed as `sourceId`s present in the latest run but absent from the previous successful run.
- **Given** `new_items > 0`, **When** the alert fires, **Then** a notification is delivered via the configured channel (in-app, email, Telegram) with a link to the topic and a summary count.
- **Given** an alert is triggered, **When** a user clicks it, **Then** the chat agent queries `chainlens-research` for the topic and displays the indexed articles with citations.
- **Given** RSS feed unavailable, trả về 5xx, hoặc tất cả articles đều là duplicate (409 từ chainlens ingest), **When** alert scheduler trigger, **Then** nó log `feed_unavailable`/`5xx`/`duplicate` và không spam notifications.
**Validation:**
- Integration test: `test_news_alert_topic_matching.py` — new articles trigger alert
- Integration test: `test_news_alert_ingest.py` — `NowingIngestService` called on alert run
- Integration test: `test_news_alert_notification.py` — notification delivered

_AD-33 (Generic Alert Engine — AlertRule template, `new_items` diff strategy) · AD-34 · AD-35_

### Story 14.4: News Digest & Synthesis `[P2]`

As a researcher,
I want daily/weekly synthesis of news across my monitored topics,
So that I can quickly understand what happened without reading 50 articles.

**Acceptance Criteria:**
- **Given** monitored topics, **When** the digest scheduler triggers, **Then** the automation queries `chainlens-research` `POST /api/v1/search` for each topic, fetches indexed articles, and prompts an LLM to produce a structured summary.
- **Given** the summary is generated, **When** it references a claim, **Then** each claim includes the source article link and `sourceId` so the UI can render citations.
- **Given** the digest is viewed, **When** a user clicks a citation, **Then** the source article opens; long-press opens a provenance drawer if `chainlens-research` returns multiple sources for the same entity.
- **Given** the digest run fails (e.g., `chainlens-research` unavailable), **When** it completes, **Then** the user sees a degraded state with `degradation_reasons` and a retry action.

**Validation:**
- Integration test: `test_news_synthesis.py` — synthesis produces coherent narrative
- Unit test: `test_news_digest_structure.py` — structured summary contains key events, entity mentions, sentiment
- Integration test: `test_news_digest_citations.py` — each claim links to indexed source

_AD-34 · AD-35 · Reuses `ux-contract-ecosystem-search` (citation model) · AD-33 (scheduler)_

---

## Epic 15: Financial Data (Vietnam)

### Story 15.1: CafeF Financial Data Integration `[P0]`

As an investment researcher,
I want stock prices, financial statements, and market news from CafeF,
So that I can analyze company fundamentals via the Nowing chat agent.

**Acceptance Criteria:**
- **Given** CafeF unofficial API is connected, **When** a user queries a stock symbol, **Then** current price, OHLCV, and key ratios are fetched.
- **Given** financial statements are fetched, **When** normalized to `Chunk[]`, **Then** each chunk has `metadata.source: 'nowing_scraper'`, `sourceId` (stable per symbol + statement type + period), `domain: 'cafef.vn'`, `fetchedAt`, `contentType`, and the statement data (balance sheet, income statement, cash flow).
- **Given** market news is fetched, **When** the batch is ready, **Then** it is ingested into `chainlens-research` via `NowingIngestService`.
- **Given** the user queries financial data, **When** the chat agent calls `chainlens-research` `POST /api/v1/search`, **Then** it returns indexed CafeF data with citations.
- **Given** data is fetched, **When** rate limit approached (20 req/min), **Then** requests are throttled gracefully and a `degraded` flag is set if throttling exceeds a configurable timeout.
- **Given** `chainlens-research` is unavailable, **When** `NowingIngestService.ingest()` is called, **Then** it retries and, after max retries, stores the batch in a dead-letter queue and returns `ingestJobId: null` with `degraded=true`.

**Validation:**
- Integration test: `test_cafef_api_connection.py` — API responds correctly
- Unit test: `test_cafef_financial_parsing.py` — financial statements parsed accurately
- Rate limit test: `test_cafef_throttling.py` — graceful throttling
- Integration test: `test_cafef_to_chainlens.py` — `POST /v1/ingest/scraper` called

_AD-34 · AD-35 · Method: Unofficial public API (no auth needed)_

### Story 15.2: Vietstock Deep Financials `[P1]`

As a deep researcher,
I want comprehensive financial data from Vietstock (3000+ companies, 130K+ statements),
So that I can perform historical analysis and cross-company comparison.

**Acceptance Criteria:**
- **Given** Vietstock scraper is authenticated, **When** a company is queried, **Then** 20+ years of historical data are fetched.
- **Given** financial ratios are extracted, **When** normalized to `Chunk[]`, **Then** P/E, P/B, ROE, ROA are stored as comparable numeric values in `content` and `metadata.ratios`.
- **Given** Vietstock data conflicts with CafeF for the same symbol and period, **When** both source `Chunk[]` are produced, **Then** each chunk is sent with the same canonical `sourceId` (e.g. normalized `symbol + statement + period`) and `metadata.conflict_flags` and `metadata.source_count` so `chainlens-research` canonical index handles cross-source merge; Nowing does not merge them locally.
- **Given** a batch of Vietstock `Chunk[]`, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** the cookie-based session expires, **When** the scraper detects `401/403`, **Then** it refreshes the cookie and retries once; if refresh fails, it marks `degraded=true` with `degradation_reason: AUTH_REFRESH_FAILED`.

**Validation:**
- Integration test: `test_vietstock_auth.py` — cookie refresh works
- Unit test: `test_vietstock_ratio_normalization.py` — ratios comparable across companies
- Integration test: `test_vietstock_chainlens_feed.py` — chunks sent to `chainlens-research`

_AD-34 · AD-35 · AD-24 (cross-source sourceId convention)_

---

### Story 15.3: Stock Price Alerts `[P1]`

As an investment researcher,
I want alerts when stock prices cross thresholds,
So that I can act on market movements.

**Acceptance Criteria:**
- **Given** a saved stock symbol with alert rules (price > X, change > Y%), **When** the scheduler triggers, **Then** the alert rule fetches fresh data from CafeF/Vietstock, normalizes it to `Chunk[]`, and calls `NowingIngestService.ingest()` to update `chainlens-research`.
- **Given** the new price is ingested, **When** `chainlens-research` returns the latest indexed value, **Then** the rule compares it to the previous indexed value and triggers the alert if a threshold is crossed.
- **Given** an alert is triggered, **When** the user receives the notification, **Then** it includes a chart snapshot and the trigger reason.
- **Given** multiple alerts, **When** viewed, **Then** they are grouped by symbol with trigger history.
- **Given** CafeF/Vietstock data source trả về 5xx, 429 rate limit, hoặc symbol không tìm thấy, **When** alert rule fetch fresh data, **Then** nó đánh dấu run `degraded` với `degradation_reasons` và không fire false alert.
**Validation:**
- Unit test: `test_stock_price_alert_rules.py` — threshold logic correct
- Integration test: `test_stock_ingest_on_alert.py` — `NowingIngestService` called on alert run
- Integration test: `test_stock_alert_notification.py` — notification delivered with chart

_AD-33 (Generic Alert Engine — AlertRule template, `price_change` diff strategy) · AD-34 · AD-35_

### Story 15.4: Financial Trend Detection `[P2]`

As an analyst,
I want automatic detection of financial trends across my watched companies,
So that I don't miss significant patterns.

**Acceptance Criteria:**
- **Given** financial data is indexed in `chainlens-research` over time, **When** the trend detection job runs, **Then** it queries `chainlens-research` for historical financial `Chunk[]` and computes trends (revenue growth, margin change, etc.).
- **Given** a significant trend is detected, **When** the insight is generated, **Then** it includes supporting data points with `sourceId` links to `chainlens-research` results.
- **Given** the insight is viewed, **When** a user clicks a supporting data point, **Then** the source financial statement opens with citation.
- **Given** `chainlens-research` historical data query trả về empty hoặc LLM synthesis fail với `judge_error`, **When** digest job chạy, **Then** nó trả `degraded=true` với `empty_dataset`/`synthesis_failed` và một retry action.
**Validation:**
- Unit test: `test_financial_trend_detection.py` — trend detection logic
- Integration test: `test_trend_chainlens_query.py` — queries `chainlens-research` for historical data
- Integration test: `test_trend_insight_generation.py` — insight generated with source links

_AD-33 (Generic Alert Engine — AlertRule template, `threshold_cross` diff strategy) · AD-34 · AD-35_

---

## Epic 16: Company Directory (Vietnam)

### Story 16.1: masothue.com Company Data `[P0]`

As a business researcher,
I want access to 2M+ Vietnamese company profiles with tax codes and registration data,
So that I can verify business partners and research market players via the Nowing chat agent.

**Acceptance Criteria:**
- **Given** masothue.com scraper is built, **When** a user searches by company name or tax code, **Then** company profile is returned with: name, tax code, address, legal representative, status.
- **Given** company data is fetched, **When** normalized to `Chunk[]`, **Then** `metadata.source: 'nowing_scraper'`, `sourceId` (stable: normalized `tax_code` or normalized `name + address`), `domain: 'masothue.com'`, `fetchedAt`, and `contentType: 'company'` are set.
- **Given** PII such as personal phone numbers or emails appears in the raw profile, **When** chunks are built, **Then** AD-25 redaction is applied before any data is sent to `chainlens-research`.
- **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** the user searches by tax code, **When** the agent queries `chainlens-research`, **Then** the indexed company profile is returned with citations.
- **Given** masothue.com HTML structure thay đổi hoặc search trả về zero results cho một tax code, **When** scraper chạy, **Then** nó trả `degraded=true` với `not_found` và không sinh company data giả.
**Validation:**
- Integration test: `test_masothue_scrape.py` — company data extracted correctly
- Unit test: `test_company_to_chunks.py` — chunk metadata and stable `sourceId`
- PII redaction test: `test_company_pii_redaction.py` — phone/email/names masked before ingest
- Integration test: `test_company_ingest_chainlens.py` — `POST /v1/ingest/scraper` called

_AD-34 · AD-35 · AD-25 · Method: HTML scrape (simple, low anti-bot)_

### Story 16.2: Official Business Registry `[P1]`

As a compliance researcher,
I want official company registration data from Vietnamese government portals,
So that I can verify legal status and regulatory compliance.

**Acceptance Criteria:**
- **Given** government portal scraper is built, **When** a user queries by tax code, **Then** official registration data is returned: charter capital, business lines, ownership structure.
- **Given** official data is fetched, **When** normalized to `Chunk[]`, **Then** it uses the same canonical `sourceId` as the masothue record when the tax code matches, and `metadata.source_count` and `metadata.conflict_flags` are set for `chainlens-research` to apply the `most_confident` strategy.
- **Given** official data contains PII, **When** chunks are built, **Then** AD-25 redaction is applied before ingest.
- **Given** a batch of official registry `Chunk[]`, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** government portal trả về 403/401 do auth expired hoặc tax code không tìm thấy, **When** scraper chạy, **Then** nó trả `degraded=true` với `degradation_reason: auth_expired`/`not_found` và giữ link masothue.
**Validation:**
- Integration test: `test_business_gov_vn.py` — official data accessible
- Unit test: `test_official_source_chunk_metadata.py` — `sourceId` matches masothue and `conflict_flags` present
- Integration test: `test_business_gov_ingest_chainlens.py` — chunks sent to `chainlens-research`

_AD-34 · AD-35 · AD-24 (cross-source sourceId convention)_

---

### Story 16.3: Company Alerts `[P1]`

As a business researcher,
I want alerts when tracked companies have significant events,
So that I stay informed about competitors and partners.

**Acceptance Criteria:**
- **Given** a tracked company (by tax code or canonical `sourceId`), **When** the scheduler triggers, **Then** the alert rule runs the masothue/business.gov.vn scrapers, normalizes new data to `Chunk[]`, and calls `NowingIngestService.ingest()` to update `chainlens-research`.
- **Given** the new run is ingested, **When** `chainlens-research` returns indexed company data, **Then** the rule detects significant changes (e.g., legal representative change, status change, new business lines) compared to the previous indexed version.
- **Given** a significant change is detected, **When** the alert fires, **Then** a notification is delivered with an event summary and source links.
- **Given** a company alert is viewed, **When** the user opens it, **Then** the agent queries `chainlens-research` for the company profile and renders source links; no local entity timeline is required.
- **Given** masothue/business.gov.vn scraper trả về `degraded=true` hoặc company tax code không tìm thấy, **When** alert rule chạy, **Then** nó skip change detection, log `source_degraded`/`not_found`, và lên lịch run tiếp theo.
**Validation:**
- Integration test: `test_company_event_detection.py` — change detection triggers alert
- Unit test: `test_company_alert_rules.py` — rule logic
- Integration test: `test_company_ingest_on_alert.py` — `NowingIngestService` called on alert run

_AD-33 (Generic Alert Engine — AlertRule template, `threshold_cross` diff strategy) · AD-34 · AD-35_

### Story 16.4: Company Timeline `[P1]`

As a researcher,
I want to see a company's event history across all sources,
So that I understand its evolution and trajectory.

**Acceptance Criteria:**
- **Given** a company is indexed in `chainlens-research`, **When** the user requests a timeline, **Then** Nowing calls the `chainlens-research` timeline API (or `POST /api/v1/search` with timeline filters) and renders the events chronologically.
- **Given** the timeline response, **When** it contains events from masothue, business.gov.vn, news, and hiring sources, **Then** the UI shows: founding, funding rounds, hiring spikes, product launches, news mentions — all chronologically with source badges.
- **Given** the timeline, **When** the user filters by event type, **Then** only selected event types are displayed.
- **Given** the `chainlens-research` timeline API is unavailable, **When** the user requests a timeline, **Then** the UI degrades to a plain search result list with a banner explaining the timeline is temporarily unavailable.

**Validation:**
- Integration test: `test_company_timeline_chainlens.py` — timeline API called and results rendered
- UI test: `test_company_timeline_render.py` — UI shows events and filters
- Integration test: `test_company_timeline_degradation.py` — graceful degradation when API unavailable

_AD-34 · AD-35 · Timeline data owned by `chainlens-research`_

---

## Epic 17: E-commerce Intelligence (Vietnam)

### Story 17.1: Lazada Product Data `[P1]`

As a product researcher,
I want product data from Lazada Vietnam including price, seller, ratings, and variants,
So that I can perform pricing analysis and competitor tracking.

**Acceptance Criteria:**
- **Given** Lazada scraper is built, **When** a user searches by product keyword, **Then** product listings are returned with: title, price, original price, discount, rating, review count, seller name, variants.
- **Given** product data is fetched, **When** normalized to `Chunk[]`, **Then** `metadata.source: 'nowing_scraper'`, `sourceId` (stable: normalized `title` + `seller_id` + `sku` if available), `domain: 'lazada.vn'`, `fetchedAt`, `contentType: 'product'` are set.
- **Given** Lazada anti-bot measures trigger, **When** detected, **Then** the scraper backs off gracefully and retries with proxy rotation; after max retries it returns `degraded=true` with `degradation_reason: ANTI_BOT`.
- **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** the user queries product data, **When** the agent calls `chainlens-research` `POST /api/v1/search`, **Then** indexed results are returned with citations.

**Validation:**
- Integration test: `test_lazada_scrape.py` — product data extracted
- Unit test: `test_lazada_to_chunks.py` — `sourceId` stable
- Anti-bot test: `test_lazada_graceful_degradation.py` — backs off on 403/CAPTCHA
- Integration test: `test_lazada_ingest_chainlens.py` — chunks sent to `chainlens-research`

_AD-34 · AD-35 · Method: HTML scrape (moderate anti-bot, residential proxies preferred)_

### Story 17.2: Shopee Product Data `[P2]`

As a market intelligence analyst,
I want product data from Shopee Vietnam (56% market share),
So that I can track the dominant e-commerce platform.

**Acceptance Criteria:**
- **Given** Shopee data source is connected (third-party API or in-house scraper), **When** a user searches by keyword, **Then** product listings are returned.
- **Given** product data is fetched, **When** normalized to `Chunk[]`, **Then** `metadata.source: 'nowing_scraper'`, `sourceId` (stable per product + platform), `domain: 'shopee.vn'`, `fetchedAt`, `contentType: 'product'` are set.
- **Given** Shopee data is fetched, **When** the batch is ingested, **Then** `NowingIngestService` calls `POST /v1/ingest/scraper` with the same canonical `sourceId` pattern as Lazada for cross-platform deduplication.
- **Given** the same product appears on Lazada and Shopee, **When** `chainlens-research` indexes both, **Then** the `chainlens-research` canonical index handles cross-platform deduplication; Nowing does not merge them locally.
- **Given** the third-party Shopee data source is unavailable, returns 5xx, or the API quota is exhausted (429), **When** the scraper runs, **Then** it returns `degraded=true` with a `degradation_reason` and does not block Lazada data ingestion.
**Validation:**
- Integration test: `test_shopee_data_source.py` — data accessible
- Unit test: `test_shopee_to_chunks.py` — `sourceId` matches cross-platform convention
- Integration test: `test_shopee_ingest_chainlens.py` — chunks sent to `chainlens-research`
- Integration test: `test_cross_platform_dedup_chainlens.py` — `chainlens-research` returns merged product

_AD-34 · AD-35 · Method: Third-party API (Apify/Bright Data) recommended; in-house requires 8-12w_



---

### Story 17.3: Price Drop Alerts `[P1]`

As a product researcher,
I want alerts when tracked products change price,
So that I can identify pricing trends and opportunities.

**Acceptance Criteria:**
- **Given** a tracked product (by canonical `sourceId` or keyword), **When** the scheduler triggers, **Then** the alert rule re-runs the Lazada/Shopee scrapers, normalizes product data to `Chunk[]`, and calls `NowingIngestService.ingest()` to update `chainlens-research`.
- **Given** the new price is indexed, **When** `chainlens-research` returns the latest product `Chunk[]`, **Then** the rule compares price to the previous indexed value and triggers an alert if the price dropped or crossed a threshold.
- **Given** a price alert is triggered, **When** it is viewed, **Then** it shows old vs new price and a link to the indexed product in `chainlens-research`.
- **Given** a price alert is viewed, **When** historical prices are requested, **Then** the UI queries `chainlens-research` for historical `Chunk[]` with the same `sourceId` and renders a price history chart.
- **Given** the tracked product `sourceId` is missing in `chainlens-research` or the price history query returns an empty dataset, **When** the alert rule compares prices, **Then** it returns `no_history`/`not_indexed` and does not fire a false price-drop alert.
**Validation:**
- Unit test: `test_product_price_alert.py` — price drop detection
- Integration test: `test_price_ingest_on_alert.py` — `NowingIngestService` called on alert run
- Integration test: `test_price_history_tracking.py` — historical prices queried from `chainlens-research`

_AD-33 (Generic Alert Engine — AlertRule template, `price_change` diff strategy) · AD-34 · AD-35_

### Story 17.4: Competitor Tracking `[P2]`

As a product researcher,
I want to track competitor products and receive change notifications,
So that I stay aware of market movements.

**Acceptance Criteria:**
- **Given** competitor products are tracked (by keyword, seller, or product family), **When** the scheduler triggers, **Then** the alert rule refreshes Lazada/Shopee data, normalizes to `Chunk[]`, and calls `NowingIngestService.ingest()` to update `chainlens-research`.
- **Given** new product `Chunk[]` are indexed, **When** the rule compares them to the previous run, **Then** changes (price, availability, new variants) are detected and a notification is sent.
- **Given** the competitor dashboard is viewed, **When** the user opens it, **Then** the UI queries `chainlens-research` for tracked products and renders a side-by-side comparison with change indicators and source badges.
- **Given** a competitor product source returns 403/429/5xx or the `chainlens-research` comparison query times out, **When** the dashboard refreshes, **Then** it displays a `degraded` banner with cached data and a retry action.
**Validation:**
- Integration test: `test_competitor_change_detection.py` — changes detected after ingest
- UI test: `test_competitor_dashboard.py` — side-by-side comparison renders
- Integration test: `test_competitor_ingest_chainlens.py` — `NowingIngestService` called on refresh

_AD-33 (Generic Alert Engine — AlertRule template, `new_items` diff strategy) · AD-34 · AD-35_

---

## Epic 13: Canonical Entity Storage & Multi-Domain Indexing `[DROPPED 2026-08-08 — ARCHIVED]`
## Epic 18: Vertical Client Platform (Public Agent-Chat)
### Story 18.1: Public Agent-Chat Endpoints `[P0]`

As a vertical client,
I want to create chat threads and send messages via public API,
So that I can integrate Nowing chat into my application.

**Acceptance Criteria:**
- **Given** a valid PAT and workspace membership, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, **Then** a chat thread is created and returned with `thread_id` and `research_thread_id`.
- **Given** a valid PAT, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called, **Then** the message is processed by the chat agent and a response is returned.
- **Given** an invalid PAT or non-member, **When** any public endpoint is called, **Then** 401/403 is returned.
- **Given** a request with a malformed JSON body or missing required fields (`workspace_id`, `message`), **When** processed, **Then** 422 is returned with field-level errors.
- **Given** an invalid `agent_id` or a valid `agent_id` not allowed for this `client_id`, **When** processed, **Then** 404 is returned with a clear error message.
- **Given** an invalid `client_id` (not in PAT scope or not registered for this workspace), **When** processed, **Then** 400 is returned.
- **Given** a valid PAT, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called and the chat service times out or is unavailable, **Then** 503 is returned with `Retry-After` or a `partial` status frame, not 500.
- **Given** a `client_id` in the request, **When** the chat processes, **Then** all data access is filtered by `client_id`.
- **Given** rate limit is exceeded, **When** the endpoint is called, **Then** 429 is returned with `Retry-After` header.
- **Given** a PAT is presented, **When** authorized, **Then** the token's allowed `workspace_id` (and optional `client_id`/`agent_id` scopes from AD-29) are enforced server-side; client-supplied IDs cannot escalate scope.
- **Given** every public call, **When** completed or rejected, **Then** an audit log records actor, workspace, client, agent, route, status and run id without storing message PII bodies by default.

_Kỹ thuật: `app/routes/agent_chat_routes.py`, PAT auth middleware, rate limiter. **AD-29** (public agent-chat surface). Depends on AD-13 ResearchThread linkage._

---

### Story 18.2: NewChatRequest Extension `[P0]`

As a vertical chat user,
I want to include `agent_id`, `client_id`, and `platform_metadata` in chat requests,
So that my agent is configured per client and context is forwarded correctly.

**Acceptance Criteria:**
- **Given** a chat request with `agent_id`, **When** it is processed, **Then** the system loads the corresponding `AgentConfig` and injects `system_instructions` into the prompt.
- **Given** a chat request with `client_id`, **When** it is processed, **Then** all memory recall and storage is tagged with `client_id`.
- **Given** `platform_metadata` in the request, **When** it is processed, **Then** the metadata is forwarded to the chat prompt context.
- **Given** no `agent_id`, **When** the request is processed, **Then** the default Nowing chat agent is used (backward compatible).
- **Given** `agent_id` or `client_id` is missing from `AgentConfig`, or the request contains invalid `platform_metadata`, **When** the chat request is processed, **Then** it returns 400/404 with a clear field error and only falls back to the default agent when `agent_id` is absent.

_Kỹ thuật: Extend `NewChatRequest` schema in `app/schemas/new_chat.py`. **AD-29** + **AD-30**._
---

### Story 18.3: Agent Registry `[P0]`

As a platform administrator,
I want to register agents with custom system prompts and tool configurations,
So that different vertical clients can have specialized chat agents.

**Acceptance Criteria:**
- **Given** the migration runs, **When** complete, **Then** an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`.
- **Given** the seed script runs, **When** complete, **Then** `bdsai-listing-assistant` is seeded as the first agent.
- **Given** an `agent_id` is provided in a chat request, **When** processed, **Then** the system loads the corresponding `AgentConfig` or returns 404 if not found.
- **Given** `AgentConfig` is global (not workspace-scoped), **When** same agent is used across workspaces, **Then** the same config applies.

_Kỹ thuật: `app/db.py` (AgentConfig model), Alembic migration (number assigned at implement time), seed script. **AD-30**. UX: `ux-contract-agent-registry.md`._

---

### Story 18.4: AgentConfig Prompt Injection `[P0]`

As a vertical chat user,
I want agent-specific system instructions injected into the chat prompt,
So that my client gets a specialized agent experience.

**Acceptance Criteria:**
- **Given** a chat request with `agent_id`, **When** the chat flow starts, **Then** `AgentConfig.system_instructions` is prepended to the default system prompt.
- **Given** an `agent_id` with `enabled_tools`, **When** the chat agent selects tools, **Then** only tools in the allowlist are available.
- **Given** no `agent_id`, **When** the request is processed, **Then** the default Nowing chat agent is used (backward compatible).
- **Given** `agent_id` points to a disabled or non-existent `AgentConfig`, **When** the chat flow starts, **Then** it returns 404 `agent_not_found` and uses the default Nowing chat agent.

_Kỹ thuật: chat orchestrator — load config, inject prompt, filter tools. **AD-30**._
---

### Story 18.5: ResearchThread Auto-Linkage `[P0]`

As a vertical client,
I want chat threads to be automatically linked to ResearchThreads,
So that memory is properly isolated and contextual across sessions.

**Acceptance Criteria:**
- **Given** a chat thread is created with `agent_id`, **When** the thread is created, **Then** a new `ResearchThread` is auto-created and linked.
- **Given** the ResearchThread is created, **When** the API response is returned, **Then** it includes `research_thread_id`.
- **Given** memories are extracted from the chat, **When** stored, **Then** they are tagged with `research_thread_id`.
- **Given** chat thread creation fails because `agent_id` is invalid or the workspace lacks permission, **When** the API processes the request, **Then** it returns 400/403 with a clear error and does not create an orphan `ResearchThread`.

_Kỹ thuật: `app/routes/agent_chat_routes.py` — auto-create ResearchThread, update response schema. **AD-13** + **AD-29**._
---

### Story 18.6: Memory Tagging + RAG Filter `[P1]`

As a workspace owner,
I want memories tagged with `client_id`/`agent_id` and RAG recall to hard-filter by tenant,
So that one client's data never leaks into another client's chat.

**Acceptance Criteria:**
- **Given** a memory is created from a chat with `client_id`, **When** it is stored, **Then** the memory row has `client_id` set.
- **Given** a recall query with `client_id`, **When** the RAG system searches, **Then** only memories with matching `client_id` are returned (hard filter, not boost).
- **Given** a recall query without `client_id`, **When** it is processed, **Then** only memories with `client_id = NULL` (Nowing-internal) are returned.
- **Given** `client_id` is missing from the request or the tenant RLS context is not set, **When** RAG recall runs, **Then** it returns an empty result set and logs `tenant_filter_missing` instead of leaking memory across tenants.

_Kỹ thuật: Alembic migration for memory tenant tags, update `app/retriever/`. **AD-31**, NFR-MULTI-1. Blocked until AD-31 tenancy design is accepted._
---

### Story 18.7: Cost Traceability `[P1]`

As a vertical client,
I want to attribute costs to my users and listings,
So that I can track and bill for Nowing usage.

**Acceptance Criteria:**
- **Given** a chat request with `external_metadata` (listing_id, broker_id, user_id), **When** it is processed, **Then** the `TokenUsage` row stores the metadata.
- **Given** a `client_id`, **When** querying TokenUsage, **Then** cost reports can be generated per client per day.
- **Given** an `X-Run-Id` header in the response, **When** the client receives it, **Then** they can correlate costs with their internal records.
- **Given** `external_metadata` is missing required fields (`listing_id`, `broker_id`, `user_id`) or the `TokenUsage` cost is `null`, **When** the chat request completes, **Then** the row is marked `invalid` and queued for manual reconciliation.

_Kỹ thuật: Alembic migration for TokenUsage/Run external_metadata, update `app/services/token_tracking_service.py`. **AD-29** cost attribution; FR-37 patterns reused. Not AD-28._
---

### Story 18.8: Rate Limiting + Tenant Isolation `[P1]`

As a workspace owner,
I want rate limits enforced per workspace and per client,
So that no single client can degrade service for others.

**Acceptance Criteria:**
- **Given** a public chat endpoint is called, **When** the rate limit is exceeded, **Then** 429 is returned with a `Retry-After` header.
- **Given** a PAT is validated, **When** the request is processed, **Then** the PostgreSQL RLS context is set (`SET LOCAL app.current_client_id`).
- **Given** RLS is active, **When** any query runs, **Then** rows are filtered by `client_id` automatically.
- **Given** a request with a valid PAT but no `client_id` in a workspace that requires one, **When** the rate limiter or RLS check runs, **Then** the request is rejected with 403 and does not reach the database.

_Kỹ thuật: Middleware in `app/middleware/tenant_context.py`, rate limiter with Redis. **AD-29** + **AD-31**, NFR-MULTI-1. Composite RLS (`workspace_id` + `client_id`) must be designed before implementation._

---


---


## Epic 21: Lead Gen Intelligence `[PROPOSED]`

_This epic is currently a proposal. Full scope, governance gates, stories and UX contracts are maintained in `epic21-proposal-2026-08-11.md`._

**Status:** `PROPOSED` — cannot be scheduled until governance gates close.

**Governance gates before scheduling:**
- Legal / ToS review for email outreach.
- Vendor contracts and data-quality POC for contact-enrichment providers (Cleanlist / BetterContact).
- Zalo OA business verification and Decree 356 compliance sign-off — `DEFERRED` out of MVP.
- PII pipeline design with `consent_status` / `legal_basis` fields.
- CRM sync scope: read-first, then write-back phased sync and conflict-resolution policy.

---

## Epic 22: Telegram Scraper & Channel Ingestion Engine `[ready-for-dev]`

> **Epic Goal:** Cung cấp giải pháp trích xuất dữ liệu đa nguồn từ Telegram (kênh công khai, nhóm thảo luận, bài đăng, bình luận, media), tự động phân tích thực thể (SĐT, giá BĐS, email), bảo vệ tài khoản chống khóa (Anti-ban/FloodWait), tích hợp thông báo tức thời (Alert Engine) và cung cấp công cụ tra cứu cho AI Agent.

**Status:** `[ready-for-dev]`
**Governed by Architecture Spine:** `_bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md` (AD-1 to AD-8).
**UX Contract:** `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-telegram-scraper-engine.md` (U1 to U7).

### Story 22.1: Telegram Storage Schema & Public Web Preview Ingestion Engine

As a data analyst or automated research agent,
I want to store Telegram metadata and scrape public channels via HTTP Web Preview (`t.me/s/{channel}`),
So that I can ingest public channel posts reliably without configuring Telegram phone accounts or risking rate limits.

**Acceptance Criteria:**

**Given** a clean or existing database environment,
**When** Alembic migrations are executed,
**Then** tables `telegram_channels`, `telegram_messages`, and `telegram_media` are created with composite unique constraint `(channel_id, message_id)`, `embedding vector(1536)` indexed via HNSW (`vector_cosine_ops`), and appropriate GIN indexes for full-text search and `raw_entities` JSONB.

**Given** a valid public Telegram channel username or URL (e.g. `batdongsan_vietnam` or `https://t.me/s/batdongsan_vietnam`),
**When** `TelegramWebPreviewScraper.scrape_channel(channel_name, limit=50)` is executed,
**Then** the HTTP/2 client queries `https://t.me/s/{channel_name}` with custom User-Agent and parses message text, publication date, views count, forward headers, and media thumbnail URLs.

**Given** a public channel with non-text messages (e.g. photos/stickers without caption) or edited posts,
**When** `TelegramWebPreviewScraper.scrape_channel()` parses the page,
**Then** it gracefully sets `text=""`, `has_media=True`, extracts media thumbnail URLs, and does not raise unhandled parsing exceptions.

**Given** existing messages in `telegram_messages` for a channel,
**When** a subsequent scrape processes the same `(channel_id, message_id)`,
**Then** PostgreSQL executes `ON CONFLICT (channel_id, message_id) DO UPDATE` updating `text`, `views`, and `updated_at` without duplicating rows or raising unique constraint errors.

**Given** a periodic Celery scrape task for registered public channels,
**When** the scheduler triggers `scrape_telegram_public_channels_task`,
**Then** it updates `last_scraped_message_id` on `telegram_channels` and syncs new records to Zero Cache.

### Story 22.2: Telegram MTProto Userbot Client, Encrypted Session Pool & Anti-Ban Cooldown

As a system administrator and background worker,
I want to onboard Telegram phone accounts into encrypted `StringSession` records with distributed mutex locks and automatic `FloodWait` cooldowns,
So that Nowing workers can securely access private channels and deep discussion threads without risking account bans or session conflicts.

**Acceptance Criteria:**

**Given** an admin supplying phone number, `api_id`, and `api_hash`,
**When** calling `/api/admin/scraper-accounts/telegram/request-otp` or running `scripts/telegram_auth_helper.py`,
**Then** Telegram sends an authentication code, and the backend stores `phone_code_hash` and temporary session string in Redis (`telegram:auth_flow:{phone}`, TTL=300s).

**Given** a pending Telegram authentication request with 2FA enabled,
**When** `/api/admin/scraper-accounts/telegram/verify-otp` is called with valid OTP,
**Then** if 2FA password is required, the API returns HTTP 200 with `status: "2fa_required"`; upon calling `/api/admin/scraper-accounts/telegram/verify-2fa` with Cloud Password, `TelethonScraperClient` exports a `StringSession`, encrypts it using `TokenEncryption(config.SECRET_KEY)`, and persists it in `scraper_platform_accounts.encrypted_credentials` with `platform="telegram"`.

**Given** an authorized `ScraperPlatformAccount`,
**When** a worker initializes `TelethonScraperClient.from_credentials(credentials)`,
**Then** the session string is decrypted in memory, connected over MTProto via SOCKS5 proxy (`socks5h://` with remote DNS resolution), and zero `.session` files are written to the container disk.

**Given** multiple enabled Telegram accounts in `scraper_platform_accounts`,
**When** `ScraperPlatformAccountRotator.get_credentials()` is requested across distributed Celery workers,
**Then** it acquires a Redis distributed mutex lock `telegram:session:lock:{account_id}` (TTL 120s) preventing concurrent multi-worker session clashes on the same account.

**Given** Telegram API raises `FloodWaitError(seconds=N)` during an MTProto operation,
**When** the worker catches the error,
**Then** it calls `rotator.record_use(account, success=False, error_type="rate_limited")`, sets `banned_until = now + N + uniform(2, 5)`, releases the Redis lock, and rotates to an alternate account without retrying immediately.

### Story 22.3: Telegram Data Enrichment, Realtime Alert Trigger, AI Agent Tools & Scraper UI

As a market intelligence user and AI researcher,
I want scraped Telegram messages to have entities extracted, media offloaded to S3, real-time alerts fired for matching posts, AI agent search tools enabled, and account status visible on the dashboard,
So that I receive instant listing leads, query Telegram history via AI chat, and manage scraper channels easily.

**Acceptance Criteria:**

**Given** raw Telegram message text containing Vietnamese phone numbers (`0912.345.678`, `+84987654321`), prices (`12.5 tỷ`, `35 triệu/tháng`), or emails,
**When** `TelegramEntityExtractor.extract_entities(text)` runs,
**Then** all detected entities are normalized and stored in `telegram_messages.raw_entities` JSONB, falling back safely to `[]` when message has no text.

**Given** a Telegram message containing media files,
**When** text ingestion finishes,
**Then** `download_telegram_media_task` streams media < 5MB directly via single `put_object` (or multipart upload with >= 5MB parts for large files) directly to S3/MinIO using `aiobotocore`, updating `telegram_media` with `storage_url` without buffering the full file on worker disk.

**Given** the `TelegramStreamDaemon` running with Redis leader election (`telegram:daemon:leader`),
**When** a new message arrives on a monitored channel via `@client.on(events.NewMessage)`,
**Then** the event is pushed to Redis Stream `stream:telegram:raw_events`, processed by Celery, and evaluated against active `AlertRule` saved searches in `app/alerts/engine/notify.py`.

**Given** a user chatting with Nowing AI Assistant,
**When** the agent calls `telegram_search_channel(channel, query, limit)` or `telegram_fetch_recent_posts(channel, limit)`,
**Then** it queries `telegram_messages` and returns formatted post summaries with author, date, views, and extracted phone numbers.

**Given** an administrator accessing `/admin/scraper-accounts` on `nowing_web`,
**When** viewing the Telegram tab,
**Then** the UI displays account statuses (`Active`, `Rate-Limited`, `Cooldown` with live countdown timer), token balances, an OTP/2FA onboarding modal, and a channel management table with realtime stream toggles.

---

## Ghi chú
- **Mồ côi/defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default enable/disable) → backlog.
- **RS-9** ("project memory" của team = `ResearchThread`?) → resolve trong scope 3.9/3.7.
- Story `[DONE]` không liệt kê AC (đã implement); chỉ story `[GAP]`/`(mới)` có AC để dev thực thi.
- **Epic 13 (DROPPED 2026-08-08):** Canonical entity storage / multi-domain indexing moved to `chainlens-research`. Nowing scrapers feed `chainlens-research` via `POST /v1/ingest/scraper` (Epic 20).
- **Epic 18 (2026-08-08 correct-course):** Public agent-chat API, Agent Registry, vertical `client_id` tenancy, cost attribution and rate limiting live in **Epic 18**. Governed by AD-29/AD-30/AD-31. Entry criteria: AD-29–31 accepted; PAT/RLS threat model reviewed.
- **Epic 22 (2026-08-15):** Telegram Scraper & Channel Ingestion Engine (Web Preview + MTProto StringSession Pool + Alert Engine + AI Agent Tools). Governed by Architecture Spine `architecture-telegram-scraper-2026-08-15`.
- **Epic structure:** Epics 12–17 may have Original + Extended sections. Sprint-status tracks all stories under one epic key.
- **Vision notes:** FR-53/FR-55 covered by existing scrapers; FR-54 deferred (ChainLens). Epics 14–17 are Phase 2 priority unless already in flight.

---

## Cross-Cutting Dependency Mapping

The following stories rely on shared building blocks introduced in **Epic 20** and on the **Story 6.8 Generic Alert Engine**. They must not be scheduled before their prerequisite is complete.

| Story | Prerequisite | Why |
|---|---|---|
| 12.4 Vietnam Job Aggregator | Story 20.1 (`NowingIngestService`) | sends normalized job listings to `chainlens-research` |
| 14.1 RSS Feed Integration | Story 20.1 (`NowingIngestService`) | sends RSS articles to `chainlens-research` |
| 15.1 CafeF Financial Data Integration | Story 20.1 (`NowingIngestService`) | sends CafeF financial chunks to `chainlens-research` |
| 15.2 Vietstock Deep Financials | Story 20.1 (`NowingIngestService`) | sends Vietstock chunks to `chainlens-research` |
| 16.1 masothue.com Company Data | Story 20.1 (`NowingIngestService`) | sends company chunks to `chainlens-research` |
| 16.2 Official Business Registry | Story 20.1 (`NowingIngestService`) | sends registry chunks to `chainlens-research` |
| 17.1 Lazada Product Data | Story 20.1 (`NowingIngestService`) | sends Lazada product chunks to `chainlens-research` |
| 17.2 Shopee Product Data | Story 20.1 (`NowingIngestService`), Story 6.8 | sends Shopee product chunks + alert template |
| 12.6 Saved Searches | Story 6.8 (Generic Alert Engine) | saved-search `AlertRule` template |
| 12.9 Job Market Alerts | Story 6.8 (Generic Alert Engine), Story 12.6 | job-market `AlertRule` template on top of saved searches |
| 14.3 News Alerts & Topic Monitoring | Story 20.1 (`NowingIngestService`), Story 6.8 | news alert fetch/ingest + `AlertRule` |
| 14.4 News Digest & Synthesis | Story 6.8 (Generic Alert Engine) | news digest `AlertRule` template |
| 15.3 Stock Price Alerts | Story 20.1 (`NowingIngestService`), Story 6.8 | stock price `AlertRule` |
| 15.4 Financial Trend Detection | Story 6.8 (Generic Alert Engine) | financial trend `AlertRule` |
| 16.3 Company Alerts | Story 20.1 (`NowingIngestService`), Story 6.8 | company `AlertRule` |
| 17.3 Price Drop Alerts | Story 20.1 (`NowingIngestService`), Story 6.8 | price-drop `AlertRule` |
| 17.4 Competitor Tracking | Story 20.1 (`NowingIngestService`), Story 6.8 | competitor `AlertRule` |
| 22.3 Telegram Alert & Agent Tools | Story 6.8 (Generic Alert Engine), Story 22.1, Story 22.2 | Realtime message matching triggers `AlertRule` & AI Agent tools |

> **Prerequisite definitions:**
> - **Story 20.1** = `NowingIngestService.to_chunks()` + `POST /v1/ingest/scraper` contract.
> - **Story 20.2** = gap-fill caller + cost allocation (Nowing side).
> - **Story 20.3** = `NowingPrivateProvider` for `POST /v1/private-data/search`.
> - **Story 20.4** = `ChainLensServiceAuth` + cost ledger sync.
> - **Story 6.8** = Generic Alert Engine in Epic 6 Automation infrastructure (scheduler + `RunService` + notification dispatch). If no dedicated implementation story exists, treat it as a prerequisite work package before any alert story is scheduled.


