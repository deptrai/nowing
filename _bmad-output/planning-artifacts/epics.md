---
title: Nowing - Epic Breakdown
description: ''
createdAt: '2026-07-28T12:47:48.297Z'
updatedAt: '2026-08-23T04:18:00Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-epics-md
---

---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prfaq-Nowing.md (primary PRFAQ / vision source)"
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md"
  - "_bmad-output/planning-artifacts/ux-spec-epic26-mission-control-phone-unlock-2026-08-20.md"
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

Phân rã epic/story cho Nowing từ PRD (reality-corrected 2026-07-24), Architecture spine, PRFAQ `prfaq-Nowing.md`, và 2 sprint-change-proposal (nguồn taxonomy epic).

> **Bối cảnh (đã verify code):** Nowing là **brownfield** — taxonomy **Epic 1–8 đã tồn tại và phần lớn ĐÃ IMPLEMENT** (migration tới 179; memory layer đã build: mig 177 tables/enums/confidence/HNSW+GIN/RBAC, 179 auto-extract, endpoints `memories_routes.py`, 4 MCP tools). Tài liệu này **không tạo epic mới đè lên epic đã xong**, mà: (a) ghi lại taxonomy thật với trạng thái `[DONE]`/`[PARTIAL]`/`[GAP]`, (b) thêm story **mới** chỉ cho phần còn thiếu (recall eval-gate, data-loss recovery, dedupe tuning, cost guardrails, docs sync).
>
> **Epic 9 (mới 2026-07-25)** là **ngoại lệ có chủ đích** của nguyên tắc trên: nó là epic *mới thật*, không phải retag. Lý do: ChainLens được thăng từ "một connector trong Epic 2" lên **external dependency hạng nhất** (`AD-15`), và ba việc trong đó (contract guard, cost metering, degradation) là **lỗi đang chạy trong production path**, không phải tính năng chưa build. Xem SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`.

## Requirements Inventory

### Functional Requirements
`[DONE]` FR-1 Auth · FR-2 API/PAT · FR-3 Workspace lifecycle · FR-4 Invites/memberships · FR-10 RBAC 3 roles · FR-6 Scrapers · FR-7 OAuth connectors · FR-8 MCP connectors · FR-9 Doc upload/index · FR-11 Folders · FR-12 Hybrid search · FR-13 Citation panel · FR-14 Chat threads · FR-15 Multi-agent runtime (+auto-extract) · FR-16 Realtime chat · FR-17 Anonymous chat · **FR-42 Chat Response Benchmark** *(mới 2026-08-04 — telemetry, regression, quality, production query sampler; stories 4.8a–4.8g)* · FR-21 Reports · FR-22 Podcast/video · FR-23 Image · FR-19 Automation triggers · FR-20 Automation runs · FR-25 Web · FR-26 Desktop · FR-27 Extension · FR-28 Obsidian · FR-29 MCP server · FR-30 Token tracking · **FR-32 Memory storage/retrieval** *(dedupe primitive + recall quality gate done; baseline ratified 2026-08-04)* · FR-33 Research continuity · FR-34 Memory correction · **FR-18 Automation actions** *(cải chính 2026-07-25: registry có `agent_task` + `continue_research` + `write_back_jira/linear/notion/slack`)* · **FR-31 Credit wallet** *(dashboard `8-3` = done)* · **FR-35 Memory-driven automations** *(cải chính 2026-07-25: trigger `memory_change` + action `continue_research` + `AutomationRun.research_thread_id` đều có)* · **FR-24 Deep-research via ChainLens engine** *(E9.1b contract regression guard done; mode default handled)* · **FR-38 Research degradation & self-host independence** *(E9.1a done)* · **FR-39 Memory→scraper-run provenance & re-validation** *(E9.6 done)* · **FR-40 First-run value: research run sinh memory** *(E3.13 done)* · **FR-41 Admin UI cho Global LLM Model Configuration** *(E8.11 done)*.
`[DONE]` **FR-37 Deep-research cost metering** (`costDollars` parser done; fallback ~$0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671) → **E9.2 P0**.
`[DONE]` **FR-43 VietnamWorks scraper** → **E12.1 P0** (public API, no auth; spike passed; legal/ToS approved, anti-bot POC passed).
`[DONE]` **FR-44 TopCV scraper** → **E12.2 P0** (HTML + anti-bot; Cloudflare challenge; legal/ToS approved, anti-bot POC passed).
`[DONE]` **FR-45 ITviec scraper** → **E12.3 P0** (HTML server-rendered; salary hidden; legal/ToS approved, anti-bot POC passed).
`[DONE]` **FR-46 `vn_jobs.aggregate`** → **E12.4a–e P0 (split: normalization, dedupe/conflict, PII, ingest, exposure)** (cross-source normalization, dedupe, confidence, conflict detection; legal/ToS approved).
`[DONE]` **FR-47 PII redaction for job data** → **E12.5 P0** (mask/drop phone, email, names before memory; legal/ToS approved).

> **Reconciliation note (2026-08-24):** FR-43–47 are `DONE` in `epics.md` and Stories `12.1–12.5` are `done` in `sprint-status.yaml` because the code is merged. PRD tags were ratified to `[DONE]` in the 2026-08-25 `bmad-prd` pass; see `AMENDMENT-PRD-Status-Ratification-2026-08-24.md` and the updated `prd-Nowing-2026-07-22/prd.md`.

`[RE-SCOPED]` **FR-49/50/51/52 News/Financial/Company/E-commerce Intelligence** → **E14/E15/E16/E17** (re-scoped 2026-08-08 — feed `chainlens-research` via `NowingIngestService`; governed by `AD-34`, `AD-35`).
`[DONE]` **FR-56 Public Agent-Chat API + FR-57 Agent Registry + NFR-MULTI-1** → **E18** (public API endpoints, `AgentConfig` registry, `client_id` tenancy, cost traceability, rate limiting + RLS).
`[DONE]` **FR-58 Scraper Feed + FR-59 Gap-Fill + FR-60 Private Provider + FR-61 Service Auth + FR-62 Canonical Chunk Schema** → **E20** (ingest to `chainlens-research`, `NowingPrivateProvider`, service-to-service auth + `TokenUsage`, canonical `Chunk` contract).

`[IN-PROGRESS]` **FR-63 Intent Signal Detection** → **E21.1** (buying signals: funding, hiring, tech stack, executive moves).
`[IN-PROGRESS]` **FR-64 Lead Scoring & Prioritization** → **E21.2** (composite score: fit + intent).
`[IN-PROGRESS]` **FR-65 Vietnam Phone & Contact Waterfall Engine** → **E21.3 P0** (3-tier: Batdongsan Token Pool → Chotot API → Zalo UID verification + Auto-refund SLA).
`[IN-PROGRESS]` **FR-66 Outbound Prospecting Automation & Panel** → **E21.4** (email + multi-source lead generation from all scrapers).
`[IN-PROGRESS]` **FR-67 CRM Integration & Lark Base / Google Sheets 1-Click Sync** → **E21.5** (HubSpot, Salesforce, Lark Base, Google Sheets, Pancake/Haravan webhooks).
`[IN-PROGRESS]` **FR-68 Vietnam Outbound Automation (Zalo OA & Telegram Sender)** → **E21.6 P0** (Zalo Assisted Chat Deep-link `zalo.me/{phone}`, Zalo OA ZNS, Telegram Bot alert).
`[IN-PROGRESS]` **FR-69 Outcome-Based Pricing & Transparent Credit Ledger** → **E21.7** ($0 chat & sequencer, pay per verified lead / outcome meeting).
`[DONE]` **FR-80 1-Click Reverse-ICP from Website / Project URL** → **E21.10** (auto-generate buyer personas, scraper targets & filter presets).
`[DONE]` **FR-81 Actionable Turn Dispatches (Suggested Action Pills)** → **E21.11** (contextual 1-click execution chips after scrape turns).
`[DONE]` **FR-82 Viral Social Outbound Co-pilot** → **E21.12** (AI Voice Learner + Viral post analyzer via XActions FB/Twitter).
`[DONE]` **FR-84 Smart Whitelist & Do-Not-Call (DNC) Compliance Engine** → **E21.14 P0** (Decree 91/2020/NĐ-CP, CSV import, opt-out protection).
`[DONE]` **FR-85 Unified Multi-Source AI Lead Generation Orchestrator** → **E21.15 P0** (1-chat parallel retrieval across all 15+ scrapers into live table).
`[NEW]` **FR-69.2 Customer Location Profile** → **E26.25** (progressive province/district/ward selector, GSO/TCTK codes, smart search & quick chips).
`[NEW]` **FR-69.3 Location-Aware Adapter Routing** → **E26.26** (coverage quality, location-weighted fit scoring, adapter re-ranking).
`[NEW]` **FR-69.4 Pre-Flight Lead Plan Summary** → **E26.27** (PlanSummaryCard, estimated leads/cost, source coverage badges).
`[NEW]` **FR-69.5 Source Coverage in Right-Canvas** → **E26.28** (source status panel, contextual coverage badges, enable/disable per source).
`[NEW]` **FR-69.6 Smoke Test Feedback Loop** → **E26.29** (5-lead preview, location refinement, re-run diff).
`[DONE]` **FR-86 Nowing Split-View Canvas & Workspace Modernization** → **E21.16 P0** (Unified New Chat, 340px Chat + Dynamic Multi-Mode Matrix, Real Credits & APIs, Sọc Caro, Emerald Green).
`[DONE]` **FR-87 Complete Origami Landing Page & Public Site Transformation** → **E21.17 P0** (10 sections, Origami Mint Logo, 12 verticals).
`[DONE]` **FR-88 Partners Affiliate Portal & $0 Pricing Page Deployment** → **E21.18 P1** ($0 Free tier, 15% recurring affiliate ledger).

`[DONE]` **FR-70 Telegram Web Preview Scraper** → **E22.1** (`t.me/s/{channel}`, no login, zero-risk).
`[DONE]` **FR-71 Telegram MTProto Client Ingestion** → **E22.2** (Telethon, private channels, discussion comments).
`[DONE]` **FR-72 Telegram Scraper Platform Accounts & Session Onboarding** → **E22.2** (AES-256 encrypted `StringSession` in DB).
`[DONE]` **FR-73 Telegram Rate Limiter & FloodWait Cooldown** → **E22.2** (`ScraperPlatformAccountRotator`, Redis mutex lock).
`[DONE]` **FR-74 Telegram Async S3 Media Streaming** → **E22.3** (128KB chunk stream directly to S3/MinIO).
`[DONE]` **FR-75 Telegram Entity Extraction** → **E22.3** (VN phone, BĐS price, email into `raw_entities` JSONB).
`[DONE]` **FR-76 Telegram Realtime Stream Daemon** → **E22.3** (`events.NewMessage` -> Redis Stream `stream:telegram:raw_events`).
`[DONE]` **FR-77 Telegram Alert Engine Trigger** → **E22.3** (matching Telegram messages trigger `AlertRule`).
`[DONE]` **FR-78 Telegram AI Agent Tools** → **E22.3** (`telegram_search_channel`, `telegram_fetch_recent_posts`).
`[DONE]` **FR-79 Telegram PostgreSQL Storage & Zero Cache Sync** → **E22.1** (composite unique `(channel_id, message_id)`).

`[DONE]` **FR-89 Async Scraper Worker Pool (Celery + Redis Streams)** → **E23.1 P0** (Non-blocking background scraping + live matrix stream).
`[DONE]` **FR-90 Official Zalo OA Webhook & ZNS Template Automation** → **E23.2 P0** (Zalo OpenAPI v3 signature verification + ZNS template delivery).
`[DONE]` **FR-91 Automated VietQR Affiliate Payout Reconciliation** → **E23.3 P1** (Instant 24/7 Napas bank settlement + cryptographic audit receipts).
`[DONE]` **FR-92 PostgreSQL RLS & Table Partitioning for Multi-Million Leads** → **E23.4 P1** (Sub-10ms query isolation on partitioned lead stores).

`[IN-PROGRESS]` **FR-93 Full-Stack Web App Builder & Instant Hosting** → **E27.1** (27.1a `done`; 27.1b/27.1c `in-progress`; 27.1 parent/tracking `in-progress`; governed by `AD-113`).
`[IN-PROGRESS]` **FR-94 Design View Mark Tool & Presentation Studio** → **E27.2** (27.2a/27.2b `ready-for-dev`; 27.1d `in-progress`; governed by `AD-114`).

> **⚠️ Out-of-PRD scope (FR-70–FR-92):** Các FR từ **FR-70 đến FR-92** (Telegram scraper Epic 22, lead-gen extensions Epic 21 mở rộng, infrastructure Epic 23) không xuất hiện trong PRD canonical `prd-Nowing-2026-07-22/prd.md`. Chúng được giữ lại trong `epics.md` như **implementation backlog / market-specific elaboration**, không phải nguồn sự thật về requirements. **FR-93/FR-94 (Epic 27) là in-PRD** theo PRD Amendment `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`.

> **✅ Implementation Readiness Closeout (2026-08-20):**
> - `FR-48` đã bị loại bỏ khỏi PRD Nowing (moved to `chainlens-research`).
> - `FR-50`, `FR-51`, `FR-52` đã được re-scope thành "feed to `chainlens-research`"; coverage trong `epics.md` thể hiện qua `Story 20.1`, `FR-58`, `FR-62` và các story 15.1/15.2/16.1/16.2/17.1/17.2.
> - `FR-70–FR-92` được ratify là out-of-PRD implementation backlog.
> - `FR-93–FR-94` được đưa vào PRD canonical qua `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`; Epic 27 nâng lên `in-progress` (27.1a `done`, 27.1/27.1b/c/d `in-progress` per `web-builder-27-1-status-audit-2026-08-25.md`, 27.2a/27.2b `ready-for-dev`).
> - Forward dependencies 2.10→3.15 (soft), 9.5→9.6 (deferred hard), 20.1→20.4 (prerequisite satisfied) đã được phân loại và ghi rõ trong `epics.md` và PRD Amendment `AMENDMENT-Implementation-Readiness-Closeout-2026-08-20.md`.

`[DONE — NFR]` **NFR-1b/1c/1d Memory latency & injection bound** *(E3.14 done, AD-18)*.
`[RESOLVED]` FR-36 Legacy memory data-loss (2026-07-25 — không mất dữ liệu; 178 chưa apply prod, `memory_md` rỗng, snapshot đã tạo; guard + backfill + 5 test qua `3-10a`/`3-10b`).
`[REMOVED]` FR-5 AI File Sorting.

> **⚠️ Re-bind 2026-07-25 (SCP `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`, ✅ ADOPTED):** **FR-24 rời Epic 2 (Connectors) sang Epic 9.** ChainLens không phải connector/scraper ngang hàng Reddit — nó là external dependency hạng nhất (`AD-15`). FR-37, FR-38, NFR-9 là mới. Story `2-4` giữ `done` làm lịch sử (nó đã ship tool thật), không revert.

#### PRFAQ-derived Functional Requirement Gaps (post-pivot 2026-08-04)

`[BACKLOG]` **FR-95 Data export & portability** → workspace/self-host user có thể export memory, research threads, và citations ra JSON/CSV (PRFAQ Q5, RS-8).
`[BACKLOG]` **FR-96 Encryption-at-rest & key management for cloud memory** → dữ liệu `content`, PII trong `source_input`, và metadata memory/version/relation trong cloud được mã hóa với BYOK hoặc managed key; `embedding` v1 giữ plaintext để HNSW/GIN search hoạt động, mã hóa embedding deferred cho đến khi benchmark searchable encryption (PRFAQ Q4, AD-28.1).
`[BACKLOG]` **FR-97 ToS/legal review + retention policy for long-term scraped data** → review ToS các nguồn, đặt retention + right-to-delete policy + workspace memory count cap trước GA cloud (PRFAQ IQ9, RS-11, AD-DEFER-4, AD-18).
`[BACKLOG]` **FR-98 Self-host OSS onboarding <10 min** → README + `docker compose` + local LLM/embedding config để dev tự host trong 10 phút (PRFAQ Q6, IQ6, RS-13).
`[BACKLOG]` **FR-99 Recall precision/noise gate before scale** → chốt ngưỡng precision và top-k noise trên `nowing_evals` trước khi mở rộng auto-extract (PRFAQ IQ1, Q8, RS-7).

`[NEW — BACKLOG]` **FR-100 Custom Workspace Roles & Permissions Builder** → workspace owner hoặc superuser có thể tạo/custom role ngoài 3 system roles mặc định, gán permissions chi tiết theo resource/action (PRD FR-10, PRFAQ Q9 context, admin nâng cấp cho SaaS operations).
`[NEW — BACKLOG]` **FR-101 Workspace Health & Adoption Analytics Dashboard** → owner/admin/analyst xem tổng quan workspace (active members, memory growth, query volume, credit burn, source coverage, recall quality) để quản lý adoption và cost.
`[NEW — BACKLOG]` **FR-102 Tenant Subscription Tier & Quota Management** → superadmin quản lý plan/trial/upgrade/downgrade cho workspace, gán quota memory/credits/users theo tier, ghi ledger thay đổi.
`[NEW — BACKLOG]` **FR-103 Admin Bulk Operations Console** → superadmin thực hiện bulk credit, suspend, export, delete, broadcast trên nhiều workspace/user từ một màn hình với dry-run và audit log.
`[NEW — BACKLOG]` **FR-104 Memory Browser & Research Timeline for Analyst** → analyst/owner duyệt memory theo thread, source type, confidence, time; click-to-source citation; filter và flag noisy/corrupted facts (PRFAQ Q9, UX-DR-PRFAQ-1).

### NonFunctional Requirements
`[DONE]` NFR-2 Security · NFR-3 Observability · NFR-4 Reliability · NFR-5 Multi-tenancy isolation · **NFR-6 Citation jump-to-source** *(cải chính 2026-07-25: `editorPanelAtom` CÓ `chunkId`; `AD-DEFER-1` đã đóng)* · **NFR-7 Usage dashboard** *(story `8-3` = done)* · **NFR-8 Recall quality eval-gate** *(story `3-9` = done; baseline ratified 2026-08-04)* · **NFR-9 Deep-research latency & availability budget** *(story `9-3` = done; State A async deliverable default; State B sync chat-mode gated on measured p95 `balanced` ≤30s)* · **NFR-10 Chat Response Regression Gate** *(mới 2026-08-04 — stories 4.8b/4.8e/4.8f/4.8g/4.8h done; `chat/regression` baseline ratification pending measured run)*.  **NFR-11 Scraping compliance & anti-bot resilience (Vietnam job market)** *(mới 2026-08-05 — ToS review, legal counsel, anti-bot POC, PII pipeline)*. `[PARTIAL]` NFR-1 Performance (bounds mơ hồ — **và không có epic nào nhận**, xem readiness C-1).

### Additional Requirements
Starter template: **KHÔNG — brownfield**. Component mới thật sự duy nhất trong Structural Seed: `nowing_evals/` (đã tồn tại, cần thêm memory suite).
- **AR-1** Thêm **suite memory-recall** vào `nowing_evals` (**DONE**: suite + dataset + oracle + metrics + gate đã có; 168 tests passed; baseline ratified 2026-08-04).
- **AR-2** Backfill/recovery markdown→`Memory` (mig 178 drop `memory_md`/`shared_memory_md` KHÔNG backfill; `downgrade` chỉ tạo cột rỗng → data-loss có thể đã xảy ra).
- **AR-3** Dedupe/confidence *validation & tuning* (primitive đã có: `repository.py` cosine<0.08 + `update_on_duplicate`, đã wire vào auto-extract) — bench + tune qua eval.
- **AR-4** Retention + right-to-delete cho `Memory`/versions/relations + scrape data (doc retention đã có mig 176 **[DONE]**; memory chưa).
- **AR-5** Observability + cost/turn quantification (spans extraction/recall + aggregate).
- **AR-6** Auto-extract cost control — **DONE**: kill-switch/global + per-workspace flags, wallet pre-check, spend/budget cap, rate-limit thời gian; 59 tests passed.
- **AR-7** Legacy memory bridge parity tests (`/…/memory`, `/users/me/memory` backed by `Memory`).
- **AR-8** MCP tool contract/selfcheck CI (`EXPECTED_TOOLS`, e2e smoke), toggle-aware.
- **AR-9** Memory security: verify `memory:*` RBAC enforced + workspace/user isolation + audit-log writes (hiện chỉ `logger.warning`).
- **AR-10** Docs/README/epics sync sang research-memory (Fumadocs) + CI docs-drift.
- **AR-11** Data export / portability cho workspace memory và research threads (PRFAQ Q5 — self-host/cloud split, giảm lock-in trước GA).
- **AR-12** Encryption-at-rest + key management cho cloud memory content/PII/metadata; BYOK/managed key; embedding encryption deferred sau benchmark (PRFAQ Q4, AD-28.1).
- **AR-13** ToS/legal review + retention / right-to-delete policy cho dữ liệu scrape lưu dài hạn (PRFAQ IQ9 — Reddit/YouTube/TikTok/Amazon).
- **AR-14** Self-host onboarding <10 phút (`docker compose up`, local LLM/embedding, README mới) (PRFAQ Q6/IQ6 — OSS motion / aha moment).
- **AR-15** Refine recall precision gate: xác định ngưỡng precision/noise trên `nowing_evals` trước khi scale (PRFAQ IQ1 — rủi ro sản phẩm #1; NFR-8 đã có, cần chốt số).
- **AR-16** Epic 13 canonical entity cleanup — `CanonicalEntity` / `app/canonical/` / `canonical_entities_routes.py` và migration/schema liên quan đã dropped khỏi kiến trúc, migration `d33c362fa627` drop tables shipped (commit `542b84d61`, 2026-08-22). [DONE 2026-08-22 — fast-track approved; deprecation skipped because zero live callers verified].
- **AR-17** Admin console nâng cấp cho SaaS operations: custom workspace roles, tenant subscription tier, bulk operations, workspace health analytics, memory browser/research timeline (PRFAQ Q9, PRD FR-10, admin/SaaS/analyst upgrade — **Epic 29**).
- **AR-18** Auditability & traceability cho mọi admin bulk op và tier change: append-only `audit_events` với `actor_id`, `subject_type`, `subject_id`, `diff_payload`, `idempotency_key`.

**Requirements signals:** RS-1 auto-extract budget (item-cap + spend-cap + wallet pre-check + rate-limit done) · RS-2 recall top_k≤5 (verify) · RS-3 beachhead agent-builder→team · RS-4 "MCP trước UI sau"/"semantic facts first" · RS-5 docs-sync bắt buộc · RS-6 right-to-delete + self-host/cloud split · RS-7 eval-gated launch + chốt số SM · RS-8 data export · RS-9 "project memory"=`ResearchThread`? · RS-10 cost/turn beta trước pricing · **RS-11 legal/ToS + retention policy trước GA cloud (PRFAQ)** · **RS-12 encryption-at-rest + key management cho cloud (PRFAQ)** · **RS-13 self-host onboarding <10 phút / aha recall (PRFAQ)**.

### UX Design Requirements
Các UX contract dưới đây đã được lưu trữ tại `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/` dưới dạng behavior contract (không layout/màu). UX chuẩn hiện tại là `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/` (`DESIGN.md` + `EXPERIENCE.md`); các đường dẫn cũ chỉ còn giá trị tham chiếu lịch sử.
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-async-deep-research.md` — chặn story 9.3 (NFR-9 State A)
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-admin-global-model-config.md` — chặn story 8.11 (FR-41)
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-chat-benchmark.md` — chặn stories 4.8a–4.8g (FR-42, NFR-10)
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-usage-dashboard.md` — chặn story 8.12, bổ sung story 8.3 (FR-31, NFR-7)
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-sync-offline-indicator.md` — chặn stories 9.1a, 9.3 (FR-38, NFR-9)
- `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-first-run-onboarding.md` — chặn story 3.13 (FR-40)

Các story có UI vẫn cần UX spec riêng trước khi build UI chi tiết. UX chuẩn (2026-08-15) là nguồn thiết kế cho mọi tính năng mới.

#### UX Design Requirements — PRFAQ (Memory Layer)

*Nguồn:* `_bmad-output/planning-artifacts/prfaq-Nowing.md`.

**UX-DR-PRFAQ-1: Memory browser / research timeline (post-MVP)**
- Analyst dùng web UI cần xem danh sách memory theo research thread, filter theo source type / confidence / time, và click-to-source citation.
- *Priority:* post-MVP; agent/MCP là beachhead trước (PRFAQ Q9/IQ7).

**UX-DR-PRFAQ-2: Self-host onboarding flow**
- Landing page + README phải dẫn dev qua `docker compose up`, chọn local vs remote LLM/embedding, kết nối MCP client trong ≤10 phút.
- *Priority:* fast-follow cho OSS motion (PRFAQ Q6/IQ6).

**UX-DR-PRFAQ-3: Memory correction / version history**
- UI cho phép user/agent flag memory sai, update fact, xem version history và relations bị ảnh hưởng.
- *Priority:* fast-follow sau 4 MCP tools (PRFAQ Q1/Q8).

**UX-DR-PRFAQ-4: Cost control / per-workspace auto-extract budget**
- Dashboard hiển thị chi phí extract + embedding + recall per turn, cấu hình ngân sách và toggle auto-extract.
- *Priority:* fast-follow (PRFAQ Q7/IQ5).

**UX-DR-PRFAQ-5: SaaS Admin Operations Console (post-MVP / Epic 29)**
- Admin console `/admin/saas` hiển thị workspace directory với plan/tier, quota usage, health score, search, filter, bulk action bar; consistent với design system `/admin/*` hiện có.
- *Priority:* fast-follow cho SaaS positioning và analyst workspace (PRFAQ Q9 context, Epic 29).

**UX-DR-PRFAQ-6: Analyst Memory Browser / Research Timeline (post-MVP / Epic 29)**
- Analyst dùng web UI xem danh sách memory theo research thread, filter theo source type / confidence / time / workspace, click-to-source citation, flag/update fact, xem version history.
- *Priority:* fast-follow sau 4 MCP tools và Memory correction/version (PRFAQ Q9/IQ7, Epic 29).

#### UX Design Requirements — Epic 26 Mission Control & Two-Tier Phone Unlock Refinement

*Nguồn:* `_bmad-output/planning-artifacts/ux-spec-epic26-mission-control-phone-unlock-2026-08-20.md` (produced 2026-08-20 from browser-tested baseline of Story 26.5).

**UX-DR1: Mission Control header clarity**
- Title must be user-facing (`Trợ lý tìm lead`) instead of internal (`DSH Mission Control`).
- Subtitle must display the active mission query (e.g. `“20 công ty AI Agent tại TP.HCM”`) so users know what is running.
- Phase badge must map internal phase names (`terminal`, `crawl`, `extraction`) to Vietnamese labels (`Hoàn thành`, `Đang chạy`, `Đang trích xuất`, `Lỗi`).

**UX-DR2: Running-state affordance in progress bar**
- Progress bar must animate (`animate-stripes` or `animate-pulse`) when `status === 'running'`.
- Percentage label must remain visible and update smoothly.

**UX-DR3: Cost transparency in Mission Control**
- Token velocity cost must display both credits and dollar equivalent (e.g. `1.2 credits ≈ $0.0012`).
- When budget data is available, show a small budget progress bar (`Đã dùng 12% ngân sách tháng`).
- When running, show estimated remaining credits based on token velocity.

**UX-DR4: Deliverable download prominence and PII safety**
- Deliverable cards must use file-type icons (`FileSpreadsheet`, `FileText`, `FileImage`) and a primary `Tải xuống` button.
- Each card must show metadata (`3 nguồn · 3 khía cạnh · 6.5 KB`).
- PII badge must be amber, near the filename, with tooltip explaining data sensitivity.
- Successful download must trigger a Sonner toast (`Đã tải xuống {filename} ({size})`).
- Failed download must show an error toast with retry guidance.

**UX-DR5: Reasoning (CoT) progressive disclosure**
- The CoT section must expand the current subtask by default.
- Past subtasks remain collapsible.
- Each subtask card must show title, status badge, tokens used, cost, and reasoning content (line-clamp-3 with expand).

**UX-DR6: SmartUnlockPopover cost clarity and anti-accidental spend**
- Cost must display `1.5 credits ≈ $0.0015` (or VNĐ equivalent) before any action.
- `1-Click Fast Unlock` checkbox must default to unchecked and clearly state TTL (`15 phút`).
- Helper text must explain: `“Bỏ qua hộp thoại này trong 15 phút tới.”`
- Bulk unlock must always show the popover, display total cost, and disable fast unlock toggle.

**UX-DR7: Fast unlock session safety rules**
- Fast unlock session TTL must be `15 phút` (down from `30 phút`).
- Session must expire on: 15 min inactivity, leaving the leads view, or logout.
- When fast unlock is active, clicking a pill must show an inline spinner before the API call (no silent spend).
- After fast unlock, toast must show an undo action for `10s`.

**UX-DR8: PhoneUnlockPill state distinction and copy behavior**
- Locked pill must use neutral colors (`bg-slate-100`, dashed border, `Lock` icon).
- Unlocked pill must use emerald (`bg-emerald-500/10`, solid border, `Phone` icon).
- Disabled pill (DNC/invalid) must be muted with `Ban` icon and tooltip.
- Click unlocked pill must copy normalized phone number and show a brief `✓` state.
- Flip animation (`rotateX`, 150ms) must play on unlock/relock.

**UX-DR9: Undo / relock affordance**
- Single unlock undo toast must last `30s` with a `Hoàn tác` action.
- Fast unlock undo toast must last `10s`.
- Undo must call `relockContact`, flip pill back to masked, and refund credits.

**UX-DR10: Accessibility for phone unlock and Mission Control**
- Locked pill `aria-label` must state cost: `“Số điện thoại bị ẩn. Click để mở khóa với chi phí 1.5 credits.”`
- Unlocked pill `aria-label` must state phone and copy action.
- Popover must be a focus trap with `Enter/Space/Tab/Esc` keyboard navigation.
- Color contrast for emerald cost text must meet ≥ 4.5:1.
- Animation must respect `prefers-reduced-motion`.

**UX-DR11: Error states for unlock and download**
- Insufficient credits (402): replace popover content with `“Không đủ credits. Nạp thêm để tiếp tục.”` and a link/button to top-up.
- DNC / blocked (403): show `“Số điện thoại bị chặn bởi DNC. Không thể mở khóa.”`
- Missing research thread (404): return clear `“Research thread not found”` error without implicit creation.

**UX-DR12: Analytics instrumentation**
- `mission_control.impression` (phase, status, has_deliverable).
- `mission_control.deliverable.download` (filename, size, include_pii, mission_type).
- `phone_unlock.popover.open`, `phone_unlock.confirm`, `phone_unlock.fast.unlock`, `phone_unlock.undo`, `phone_unlock.error`.


### FR Coverage Map
- FR-1/2/3/4/10 → **E1** [DONE] · FR-6/7/8 → **E2** [DONE] · **FR-6 mở rộng → E10.1** [DONE] (batdongsan scraper) · FR-9/11/12/13 → **E3** [DONE] · **FR-14/15/16/17/42 → E4** [DONE] (4.8a–4.8g chat benchmark & regression gate) · FR-21/22/23 → **E5** [DONE] · FR-19/20 → **E6** [DONE] · FR-25/26/27/28/29 → **E7** [DONE] · FR-30 → **E8** [DONE] · **FR-41 → E8.11** [DONE]
- **FR-6/7/8 + FR-8.1 → E2** [DONE] · FR-8.1 = **E2.10** Exa MCP Search Connector `[DONE 2026-08-05]`
- **FR-24/37/38/39 + NFR-9 → E9** (mới 2026-07-25; tách story theo readiness Q-3/Q-4): FR-38 → **E9.1a** [DONE, P0] · FR-24 → **E9.1b** [DONE, P0] · FR-37 → **E9.2** [DONE, P0, parser `done.usage.costDollars` + `done.usage.estimated` + `done.resolvedMode` + canonical golden fixtures + fallback 60k micros; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671] · NFR-9 → **E9.3** [DONE] · OQ-6/AR-10 (phần Nowing↔engine) → **E9.4** [DONE, P1] · D5-Phase2 → **E9.5** [deferred] · **FR-39 → E9.6** (provenance + re-validation) [DONE]
- FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11) · FR-33 → E4 (4.6 done) · FR-34 → E3/E4 (done)
- FR-36 → **E3.10** [RESOLVED 2026-07-25] · FR-18 → **E6.4** [DONE] · FR-31/NFR-7 → **E8.3** [DONE] · FR-35 → **E6.5** [DONE — cải chính 2026-07-25]
- **FR-49/50/51/52 → E14/E15/E16/E17** `[BACKLOG]` (re-scoped 2026-08-08 — feed `chainlens-research`; governed by `AD-34`, `AD-35`)
- **FR-56/57 + NFR-MULTI-1 → E18** `[IN PROGRESS]` (public agent-chat endpoints, `AgentConfig` registry, `client_id` tenancy, cost traceability)
- **FR-58/59/60/61/62 → E20** `[DONE]` (scraper feed to `chainlens-research`, gap-fill trigger, `NowingPrivateProvider`, service-to-service auth + cost allocation, canonical `Chunk` schema)
- NFR-8 → **E3.9** [DONE — baseline ratified 2026-08-04] · NFR-6 → **E3.6** [DONE] · NFR-10 → **E4** [DONE — 4.8b/4.8e/4.8f/4.8g] · OQ-3/AR-4 → **E3.7** [DONE for document retention; PARTIAL for memory retention] · OQ-4 → **E2.5** [DONE] · **OQ-5 → E6.4 [DONE]** *(2026-07-25: `6-4` = done; 4 action type `write_back_notion/slack/linear/jira` đã có ⇒ câu hỏi "action type riêng vs `agent_task`" **code đã trả lời: action type riêng**)* · OQ-6/AR-10 → **E8.10 + E9.4** [DONE] · **OQ-7 (5 câu hỏi từ ChainLens `42-3`, ADOPTED 2026-08-05) → E9.1b/E9.2/E9.3** [DONE] · FR-5 → [REMOVED]
- **Mới 2026-07-25 (readiness Nhóm 3 — trước đây KHÔNG có FR lẫn epic):** **FR-40** (first-run value: research run sinh memory; M1; brief §9 H-4) → **E3.13** [DONE, HIGH] · **NFR-1b/1c/1d** (bound cho memory injection + recall + auto-extract; `AD-18`) → **E3.14** [DONE, đi kèm E3.13]
  - ⚠️ **NFR-1 trước đây KHÔNG map sang epic nào** (readiness C-1) và không phủ memory (P-5). Nay: **NFR-1a** (CRUD/scraper) = nền tảng, không cần story riêng · **NFR-1b/1c/1d → E3.14**.
  - ⚠️ **Ràng buộc thứ tự mới:** **E3.14 nên chạy trước khi chốt số SM-10 của E3.9** (`AD-18` rule 6) — baseline recall quality đo trên lượng inject phụ thuộc N thì không tái lập được.
- AR-1/AR-3/AR-8 → E3.9/3.11 · AR-2/AR-7 → E3.10 · AR-9 → E3.12 · AR-5 → E8.9 · AR-6 → E8.8/8.7 · RS-5→E8.10 · RS-6/8→E3.7 · RS-7→E3.9 · RS-10→E8.9
- **NG-1/NG-2/NG-3 (§2.4 PRD Non-Goals)** → không map sang epic nào; là ràng buộc chặn phạm vi. Owned index = `AD-DEFER-7`.
- **Defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default toggle) → backlog.
- **OQ-8 HR/Recruitment Vertical in Vietnam** → **E12 P0** (ToS, legal classification, anti-bot, salary hidden, willingness-to-pay, PII).
- **SM-12 HR pilot metrics** → **E12 P0** (workspace active, aggregate queries, listings indexed, dedupe, confidence, PII coverage).
- **AR-11 HR anti-bot validation** → **E12.2 P0** (TopCV Cloudflare bypass/residential proxy feasibility).
- **Mới 2026-08-10 (Market Research → Lead Intelligence) — đã hoàn thành 2026-08-16:** FR-63 (Intent Signals) → **E26.1** `[DONE]` · FR-64 (Lead Scoring) → **E26.2** `[DONE]` · FR-65 (Contact Enrichment / Phone Waterfall) → **E23.2** `[DONE]` · FR-66 (Outbound Automation) → **E23.3** `[DONE]` · FR-67 (CRM Integration) → **E24.3** `[DONE]` · FR-68 (Zalo Integration) → **E24.7** `[backlog]` · FR-69 (Outcome Pricing) → **E23.4** `[DONE]` · FR-80 (Reverse-ICP) → **E26.x** `[DONE]` · FR-81/82/83 (Actionable dispatches / Viral copilot / Social) → **E24.6 / E23.x** · FR-84 (DNC) → **E25.x** · FR-85 (Lead Orchestration) → **E26.x** `[ready-for-dev]` · FR-86 (Split Canvas) → **E25 / E27** · FR-87 (Landing page) → **E25 / E27** · FR-88 (Affiliate) → **E25.x** · FR-91 (VietQR) → **E25.x`. **Epic 21 là umbrella tracking; Epic con E23–E26/E25 nhận việc.**
- **Mới 2026-08-29 (Customer Location Profile & Pre-Flight Lead Plan):** FR-69.2 (Location Profile) → **E26.25** `[ready-for-dev]` · FR-69.3 (Location-Aware Adapter Routing) → **E26.26** `[ready-for-dev]` · FR-69.4 (Pre-Flight Plan Summary) → **E26.27** `[ready-for-dev]` · FR-69.5 (Source Coverage in Right-Canvas) → **E26.28** `[ready-for-dev]` · FR-69.6 (Smoke Test Feedback Loop) → **E26.29** `[ready-for-dev]`. **Đã remap từ Story 21.25–21.29 sang E26.25–E26.29 (Autonomous Lead Missions)._

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
KB + long-term research memory. **FRs:** FR-9,11,12,13,32,33,34, **FR-40** *(mới)*, **NFR-1b/1c/1d** *(mới)*, **FR-99** *(mới 2026-08-21 — recall precision/noise gate từ PRFAQ)*. **Story 3.18 (FR-99)** là backlog thuộc Epic 3; thuật toán gate được triển khai trong `nowing_evals`, gán về Epic 3 vì đây là memory recall gate. **Open:** 3.15 run citations `[ready-for-dev]`, 3.16 OKF export `[ready-for-dev]`, 3.17 memory injection perf gate `[ready-for-dev]`, 3.18 recall precision gate `[backlog]`.
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
Token tracking, ví credit, dashboard usage, guardrail chi phí, docs/vision sync, admin UI cho global LLM model config, workspace limits, và PostHog analytics. **FRs:** FR-30, FR-31, **FR-41** *(mới)*. 8.10, 8.11, 8.12, 8.13 **done**. **Open:** 8.14 Usage & Credit Dashboard v2 — per-turn cost + auto-extract budget toggle `[ready-for-dev]` *(mới 2026-08-21 từ PRFAQ, UX-DR-PRFAQ-4; re-scope 2026-08-23 là follow-up của Story 8.3)*.
> **⚠️ Đổi tên + đánh lại số hiệu 2026-07-25 (readiness Q-7 + C-C).** Tên trước *"Platform Operations (Billing/Usage/Token)"* là framing ops. **Và quan trọng hơn — số hiệu story đã bị xung đột với `sprint-status.yaml`:** `8.4a`/`8.5`/`8.6` trong tài liệu này nghĩa **khác** `8-4`/`8-5`/`8-6` trong sprint-status (observability-logging / security-permissions / multi-tenant-isolation). Đã đánh lại theo số **chưa dùng**: `8.4a → 8.8` · `8.5 → 8.9` · `8.6 → 8.10`. Từ giờ số hiệu ở hai tài liệu khớp 1-1.

### Epic 9: Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng — ✅ DONE (2026-08-05)
Người dùng research sâu được mà **không vỡ** khi engine chết (9.1a), **không treo** cả chat turn khi engine chậm (9.3, State A mặc định), và **trả đúng tiền** cho thứ mình dùng (9.2). **FRs:** FR-38 [DONE,P0], FR-24 [DONE,P0], FR-37 [DONE,P0, parser `done.usage.costDollars` + `done.usage.estimated` + `done.resolvedMode` (top-level canonical) + `promptTokens`/`completionTokens`/`totalTokens`/`model` + canonical golden fixtures + fallback 60k micros ≈ $0.06; cost thực tế ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671], FR-39 [DONE — 9.6 provenance + re-validation], NFR-9 [DONE — State A async deliverable default; sync chat-mode chỉ cho `speed`/`balanced`; `quality`/`deep` async-only; State B mở khi ChainLens 34.1 full-pipeline cost + Nowing e2e p95 `balanced` ≤ 30s]. **Deferred / Post-MVP:** **9.5** metered self-host endpoint (chưa phê duyệt). **Governed by:** `AD-15` · `AD-16` (license — cho 9.4) · **`AD-11.1`** (provenance recipe — cho 9.6) · **`AD-17`** (async door — cho 9.3) · **`AD-19`** (trang khó: anti-bot ở Nowing, engine không gọi ngược inline, escalation async — cho 9.1a/9.3) · **`AD-20`** (screenshot-as-evidence, không adopt visual-RAG stack) · AD-7, AD-8 amended.
> **✅ Cập nhật 2026-08-05:** 9.1a, 9.1b, 9.2, 9.3, 9.4, 9.6 **done**. 9.5 **deferred**.
>
> **🆕 2026-08-03 — Epic 10: Connector & Scraper Expansion** (Vietnam BĐS + broader scraper port). **Open:** 10.1 batdongsan `[done]`, 10.2 chotot `[done]`, 10.3 muaban `[done]`, 10.4 cross-source aggregator `[done]`.
> **⚠️ Đổi tên 2026-07-25 (readiness Q-1).** Tên trước — *"Deep-Research Engine Integration (ChainLens)"* — là **technical epic**: nó mô tả hạ tầng, không mô tả điều user làm được. Ba mệnh đề trong tên mới map thẳng vào ba story P0/P1.
>
> **🆕 2026-08-03 — Epic 11: Telegram Automation & Bot** (notification, write-back, inline keyboard, commands). **Open:** 11.1 notification foundation `[done]`, 11.2 write-back & builder `[done]`, 11.3 interactive bot & commands `[done]`.

### Epic 10: Connector & Scraper Expansion (Vietnam Real Estate & Spatial GIS) — 🔄 IN PROGRESS
Vietnam BĐS (batdongsan, chotot, muaban) + PostGIS spatial land zoning (`ONT`/`ODT`/`DGT`/`CX`). **Open:** 10.6–10.8.

### Epic 11: Telegram Automation & Bot — ✅ DONE
Notification, write-back, builder UI, inline keyboard, commands. **FRs:** FR-20 variants. **All done.**

### Epic 12: HR/Recruitment Vertical — Vietnam Job Market & LinkedIn B2B — 🔄 IN PROGRESS
VietnamWorks, TopCV, ITviec, Indeed, LinkedIn Public Guest API (`seeMoreJobPostings`); job listing normalization/dedup/PII/ingest; saved searches + job market alerts. **Done:** 12.1–12.5, 12.4a–e (code merged; FR-43–47 marked `DONE` here, PRD status to be ratified in next `bmad-prd` pass). **Open:** 12.6, 12.9, 12.10.

### Epic 13: Canonical Entity Storage & Multi-Domain Indexing — 🗑️ DROPPED 2026-08-08
Canonical index moved to `chainlens-research`; Nowing scrapers feed via `POST /v1/ingest/scraper`.

### Epic 14: News Aggregation (Vietnam) — ♻️ RE-SCOPED
RSS feed integration, entity enrichment. **FR-49 re-scoped 2026-08-08:** Nowing feed/crawl infrastructure is done, but Nowing does not keep a local news index. News alerts/digest merged into Epic 6.11/6.12. **Done:** 14.1, 14.2a; **Blocked/Backlog:** 14.2b.

### Epic 15: Financial Data (Vietnam) — ♻️ RE-SCOPED
CafeF / Vietstock data. **FR-50 re-scoped 2026-08-08:** Nowing feed/crawl infrastructure is done, but Nowing does not keep a local financial index. Stock price alerts/financial trend merged into Epic 6.11/6.12. **Done:** 15.1, 15.1b, 15.2.

### Epic 16: Company Directory & Public Procurement (Vietnam) — ♻️ RE-SCOPED
masothue.com company data, official business registry, national public procurement tenders. **FR-51 re-scoped 2026-08-08:** Nowing feed/crawl partially done (16.1, 16.5), but Nowing does not keep a local company index. Company alerts/timeline merged into Epic 6.11/6.12. **Done:** 16.1, 16.5; **Backlog:** 16.2.

### Epic 17: E-commerce Intelligence (Vietnam) — ♻️ RE-SCOPED
Lazada / Shopee / TikTok Shop product data. **FR-52 re-scoped 2026-08-08:** Nowing feed/crawl partially done (17.2), 17.1 and 17.5 blocked-by-external XActions. Nowing does not keep a local product index. Price-drop alerts/competitor tracking merged into Epic 6.11. **Done:** 17.2; **Backlog/Blocked:** 17.1, 17.5. Governed by `architecture-shopee-ecommerce-2026-08-15`.

### Epic 18: Vertical Client Platform (Public Agent-Chat) — ✅ DONE
Public agent-chat endpoints, AgentConfig registry, client_id tenancy, cost traceability, rate limiting + RLS. **FR-56/57 [DONE] in PRD 2026-08-24.** **Done:** 18.1–18.8.

### Epic 20: Nowing Ecosystem Integration — Feed & Recall from chainlens-research — ✅ DONE
`NowingIngestService` + `to_chunks()`, gap-fill caller, `NowingPrivateProvider`, service-to-service auth. **Open:** none.

### Epic 21: Lead Gen Intelligence — ✅ DONE *(umbrella)*
Umbrella / tracking epic cho hệ sinh thái săn lead: Lead Capture & Enrichment (E23), Multi-Channel Outreach & CRM (E24), Platform Admin & Multi-Tenant (E25), Autonomous Lead Missions / DSH (E26), Growth & Affiliate (E29). Chi tiết triển khai đã chuyển sang các epic con. **FRs:** FR-63–69, FR-80–88, FR-91. **Dependencies:** E10, E12, E22. _Tách 2026-08-29: epic con E23–E26/E29 nhận stories từ Epic 21 nguyên bản. Customer Location Profile & Pre-Flight Lead Plan stories (21.25–21.29 từ main) đã remap E26.25–E26.29._

### Epic 22: Telegram Scraper & Channel Ingestion Engine — ⏳ READY-FOR-DEV
Public channel web preview, MTProto Userbot session pool, distributed mutex lock, FloodWait cooldown state machine, regex entity extractor, S3 media chunk streaming, realtime stream daemon, Alert Engine trigger, AI Agent tools. **Stories:** 22.1–22.3. Governed by `architecture-telegram-scraper-2026-08-15`.

### Epic 28: Self-Host Trust, Data Portability & Cloud GA Legal Readiness — 📋 BACKLOG *(mới 2026-08-21 từ PRFAQ)*
Người dùng self-host và cloud có thể tin tưởng Nowing với research memory dài hạn: dữ liệu có thể xuất, được mã hóa, quản lý bởi policy rõ ràng, và self-host chạy trong <10 phút. **FRs:** FR-95 (Data export & portability), FR-96 (Encryption-at-rest & key management), FR-97 (ToS/legal review + retention), FR-98 (Self-host OSS onboarding <10 min), **FR-99** (recall precision/noise gate — GA launch gate). **ARs:** AR-11, AR-12, AR-13, AR-14, AR-15. **UX-DRs:** UX-DR-PRFAQ-2 (self-host onboarding), UX-DR-PRFAQ-4 (cost control dashboard). **Stories:** 28.1–28.6 (28.6 = recall precision ratification, FR-99). **Dependencies:** Epic 1 (auth), Epic 3 (memory schema), Epic 8 (billing/cost). Post-MVP UX-DR-PRFAQ-1/3 (memory browser/correction) thuộc Epic 3.

### Epic 29: SaaS Operations, Advanced Admin Governance & Analyst Workspace — 📋 BACKLOG *(mới 2026-08-29 — admin nâng cấp, SaaS operations, analyst)*
Nowing nâng cấp từ single-tenant ops lên SaaS operations console: superadmin quản lý workspace/tenant, subscription tier/quota, bulk operations, audit; owner/admin/analyst có dashboard health/adoption và memory browser/research timeline. **FRs:** FR-100 (Custom workspace roles & permissions builder), FR-101 (Workspace health & adoption analytics dashboard), FR-102 (Tenant subscription tier & quota management), FR-103 (Admin bulk operations console), FR-104 (Memory browser & research timeline for analyst). **ARs:** AR-17, AR-18. **UX-DRs:** UX-DR-PRFAQ-5 (SaaS admin operations console), UX-DR-PRFAQ-6 (analyst memory browser / research timeline). **Stories:** 29.1–29.6. **Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory schema/provenance), Epic 8 (billing/cost/wallet), Epic 25 (admin platform operations baseline), Epic 28 (retention/right-to-delete cho 29.6).

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

**Regression (post-Story 3.15):**
**Given** Story 3.15 finalizes the `WEB_RESULT` citation contract and `register_web_citations()` helper, **When** the Exa MCP `web_search_exa` and `web_fetch_exa` tools are invoked, **Then** their result URLs are registered as `WEB_RESULT` citations and render as `UrlCitation` chips in chat.
**Given** the 3.15 citation contract changes, **When** Exa MCP tool tests run, **Then** they pass without modification to the Exa connector logic (only citation registration call site may need updating).

_FR-8 · FR-8.1 · OQ-4._

> **🆕 Extend 2026-08-08 (SCP `sprint-change-proposal-2026-08-08.md`):** `web_search_exa`/`web_fetch_exa` là MCP tools return text trực tiếp — không qua `_capability_tool` hay citation registry. Agent nhận search results nhưng không có `[n]` labels để cite. Append ACs dưới đây.

**Acceptance Criteria (appended 2026-08-08 — Exa MCP citation registration):**

**Given** the agent calls `web_search_exa` and receives results with URLs, **When** the tool returns, **Then** each result URL is registered as a `WEB_RESULT` citation in the `CitationRegistry`.
**Given** the agent calls `web_fetch_exa` for a specific URL, **When** the tool returns, **Then** the fetched URL is registered as a `WEB_RESULT` citation.
**Given** the registry contains Exa `WEB_RESULT` entries, **When** the model emits `[n]` labels referencing them, **Then** URL citation chips render in chat.
**And** existing MCP tool behavior (readonly, no HITL) is unchanged.

**Kỹ thuật (appended):** hook vào MCP tool wrapper hoặc post-processing step — extract URLs from `web_search_exa` results, register URL directly for `web_fetch_exa`. Reuse `register_web_citations()` helper from Story 3.15 extension.

> **Dependency note:** Story 2.10 reuses the `WEB_RESULT` citation contract that Story 3.15 will finalize. Because 2.10 was completed on 2026-08-05, it uses a provisional citation format; when 3.15 is merged, the E2 team should regression-test 2.10 against the final 3.15 citation contract.

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

### Story 3.18: Recall Precision / Noise Gate Ratification  `(mới 2026-08-21 từ PRFAQ)`  `[backlog]`

As a platform team,
I want to ratify a precise precision/noise threshold for `nowing_recall` on `nowing_evals` before scaling,
So that Nowing does not ship "AI guessing" instead of "AI remembering".

**Acceptance Criteria:**

**Given** the `memory-recall` eval suite in `nowing_evals` already measures recall@k, MRR, nDCG, and Wilson CI,
**When** I add the `precision@5` and `noise_rate` metrics with a documented oracle,
**Then** `nowing_evals report memory recall` prints both metrics with confidence intervals and a pass/fail verdict.

**Given** a candidate threshold (e.g. `precision@5 ≥ 0.80`, `noise_rate ≤ 0.10`),
**When** the baseline is measured on the current corpus,
**Then** the chosen threshold is recorded in `_bmad-output/planning-artifacts/memory-recall-thresholds-2026-08-21.md` and wired into the CI gate so any PR that regresses recall below the threshold is blocked.

**Given** a regression in precision or noise,
**When** the CI gate runs,
**Then** it fails with a clear diff of metric deltas and a link to the oracle dataset, not a generic assertion failure.

**Given** the threshold document is missing or the oracle is empty,
**When** the gate runs,
**Then** it raises `QualityBenchmarkConfigError` with a validation message and does not silently pass.

_FR-99 · AR-15 · NFR-8 · AD-46 · AR-1 · AR-3 · RS-7 · SM-10. Threshold artifact: `memory-recall-thresholds-2026-08-21.md`._

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
**Given** a workspace identifier and the configured `EVAL_QUERY_SAMPLING_HMAC_KEY` secret,
**When** the sampler hashes an identifier for the dataset,
**Then** it uses HMAC-SHA256 with that secret rather than plain SHA256 so the same workspace always yields the same keyed hash but the hash cannot be reversed offline.

**Given** the database connection drops, the query times out, or a SQL error is raised while the sampler is reading production logs,
**When** the sampler catches the exception,
**Then** it logs the error with a `sampler_db_error` event and `workspace_id` context, returns an empty or unchanged dataset, and exits `0` without crashing.

**Given** `tests/evals/chat/test_chat_query_sampler.py` uses an async database session with a context manager,
**When** any test inside that session fails,
**Then** `__aexit__` rolls back the transaction and does not leave rows behind for the next test.

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
So that tests don't fail in CI if the fixture file is missing.

**Acceptance Criteria:**
**Given** the `chat/quality` test looks for a `gate.yaml` fixture and the file is missing or empty,
**When** the test starts,
**Then** it calls `pytest.skip` (or equivalent) with a clear message naming the missing fixture path and does not raise `FileNotFoundError` or `QualityBenchmarkConfigError`.

**Given** the same missing `gate.yaml` scenario,
**When** CI runs the quality benchmark test suite,
**Then** the suite exits `0` for that test as `skipped` and the CI job is not marked as failed.

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
- `new_items`: query, compare to last snapshot, notify new items. Used for job alerts (12.9) and news/competitor alerts (6.11).
- `price_change`: compare price field, notify if delta > threshold. Used for stock alerts and price-drop alerts (6.11).
- `threshold_cross`: compare field to threshold, notify on cross. Used for trend alerts and company event alerts (6.11).

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

### Story 7.8: Vietnamese i18n & Smart Geo-Locale Auto-Detection  `(mới 2026-08-17)`  `[ready-for-dev]`

As a Vietnamese user or international visitor,
I want Nowing to support Vietnamese language and automatically detect my location on my first visit to present the appropriate language,
So that I can immediately experience the application in my native language without manual switching, while retaining my language preferences if I choose to change them.

**Acceptance Criteria:**
1. **Given** a user accesses Nowing with no prior `nowing-locale` in `localStorage`, **When** their browser language is Vietnamese (`vi`, `vi-VN`) OR their timezone is within Vietnam (`Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`), **Then** the application automatically selects `vi` and renders all messages in Vietnamese.
2. **Given** a first-time user from a non-Vietnamese locale with no prior preference, **When** their browser language matches a supported locale (`es`, `pt`, `hi`, `zh`, `ko`), **Then** the application auto-selects that locale; otherwise it defaults to `en`.
3. **Given** a user changes language via `LanguageSwitcher` or `SidebarUserProfile` (or has existing `nowing-locale` in `localStorage`), **When** the user revisits or refreshes the page, **Then** the application strictly retains the stored language preference without overriding it.
4. **Given** the language switcher UI in header and sidebar, **When** viewed, **Then** `🇻🇳 Tiếng Việt` is present, selectable, and dynamically switches all UI components with 0 errors.

**Kỹ thuật:** Add `nowing_web/messages/vi.json`, update `routing.ts`, `LocaleContext.tsx`, `LanguageSwitcher.tsx`, `SidebarUserProfile.tsx`.

---

## Epic 8: Workspace Billing & Usage Transparency
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
**Given** a superuser creates or updates a global model connection with a provider name,
**When** the form is submitted,
**Then** the backend validates the provider against the known provider enum and rejects with a `provider_not_supported` error if the provider is not in the allow-list.

**Given** the global model connection count exceeds the configured `ADMIN_MODEL_LIST_PAGE_SIZE` (default 1000),
**When** a superuser calls the admin list endpoint with `limit` and `offset` query parameters,
**Then** it returns the requested page, includes a total count, and rejects `limit` values above a server-side maximum.

**Given** a duplicate provider + model name pair is submitted,
**When** the create/update request is processed,
**Then** the backend returns a `409 Conflict` with a clear message instead of inserting a duplicate row.

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

### Story 8.14: Usage & Credit Dashboard v2 — Per-Turn Cost & Auto-Extract Budget Toggle `(mới 2026-08-21 từ PRFAQ)` `[ready-for-dev]`

> **Re-scope 2026-08-23:** Story này là **follow-up / v2** của **Story 8.3 (Usage & Credit Dashboard)**. Không duplicate 8.3; 8.3 vẫn `done` với aggregate theo workspace/model/time. Story 8.14 mở rộng thêm **per-turn cost breakdown** và **auto-extract budget toggle UI** trên cùng data.

As a workspace owner,
I want the existing Usage & Credit Dashboard to show cost per turn and to expose a per-workspace auto-extract budget toggle,
So that I can control spend and avoid surprise bills from memory extraction.

**Acceptance Criteria:**

**Given** the workspace owner opens the existing `Usage & Credit` dashboard (Story 8.3), **When** the page loads, **Then** it extends the current view with a per-turn cost breakdown: auto-extract LLM tokens, embedding tokens, and recall tokens, sourced from `TokenUsage` and reconciled with `credit_transactions`.

**Given** a `TokenUsage` row is missing `workspace_id` or `cost_micros`, **When** the dashboard queries the data, **Then** it excludes incomplete rows and logs a `usage_reconcile_warning` rather than inflating totals.

**Given** auto-extract is enabled for the workspace, **When** the owner sets an item cap, spend cap, or wallet pre-check via a new budget toggle, **Then** the existing kill-switch/guardrails (Story 8.7) enforce those limits and surface a warning when 80% of the cap is reached.

**Given** the cost dashboard is open, **When** the owner hovers a bar, **Then** it shows the capability (e.g. `chainlens.research`, `memory.extraction`, `memory.recall`) and the resolved model, and the value created (memories created, citations generated) alongside the cost.

**And** the dashboard reuses the existing `workspace_limits` and `credit_wallet` infrastructure from 8.3/8.7 so it does not duplicate ledgers.

_UX-DR-PRFAQ-4 · AR-5 · AR-6 · FR-31 · NFR-7 · Story 8.3 v2 extension._

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
>
> **Dependency note:** Story 9.5 requires Story 9.6 (Memory Provenance & Re-Validation) provenance recipe for any metered deep-research output that must be traceable and re-validated. This is a hard dependency, but 9.5 remains deferred until the SCP is approved.

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
**Given** a memory row whose `confidence` is being updated,
**When** the value is persisted,
**Then** the database CHECK constraint enforces `confidence` in the range `[0.1, 1.0]` and a new Alembic migration applies that constraint without data loss.

**Given** two re-validation requests for the same `memory_id` arrive at the same time,
**When** both attempt to update the memory,
**Then** the code uses `SELECT FOR UPDATE` (or an equivalent atomic path) so one wins and the other waits, and no duplicate `MemoryVersion` rows are created.

**Given** a capability re-execution produces an output larger than the configured `REVALIDATION_OUTPUT_MAX_BYTES` (default 100KB),
**When** the re-validator compares it with the stored content,
**Then** it truncates both sides to the same byte limit before comparison and logs a `revalidation_truncated` warning.

**Given** `tests/unit/memory/test_memory_revalidation.py` exercises a failure path,
**When** the test runs,
**Then** it asserts the mock capability executor was called at least once and the memory `confidence` is decreased, but no unhandled exception is raised.

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

### Story 10.8: Spatial Planning & Land Zoning GIS (PostGIS Map Layers) `[P1]`

As a real estate researcher, investor, or appraiser,
I want to query land zoning classifications (`ONT`, `ODT`, `DGT`, `CX`) by GPS coordinates,
So that I can immediately verify if a property listing in Batdongsan/Chotot/Telegram is in a road expansion or public park planning zone.

**Acceptance Criteria:**
- **Given** spatial polygon dataset of Vietnam land zoning (Shapefile/GeoJSON in VN-2000 or WGS84), **When** ingested, **Then** geometry is validated with `ST_MakeValid()`, converted to WGS84 via `ST_Transform(geom, 4326)` or `pyproj`, subdivided with `ST_Subdivide()` for fast spatial indexing, and stored in `spatial_planning_zones` with unique constraint `(province, district, zone_code, polygon_hash)` and PostGIS GIST index on `polygon_geometry`.
- **Given** GPS coordinates (`latitude`, `longitude`), **When** calling `SpatialPlanningService.query_zoning(lat, lng)`, **Then** it validates coordinate bounds (`102.0 <= lng <= 109.5`, `8.5 <= lat <= 23.5`), constructs point `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` (preserving `(X=lng, Y=lat)` ordering), and executes `ST_Intersects()`, returning zoning classification within $\le 10$ms; if outside mapped zones, falls back safely to `zone_code: "UNZONED"` with `status: "NO_PLANNING_RESTRICTION"`.
- **Given** property listings scraped from Batdongsan, Chotot, or Telegram, **When** geocoded, **Then** the system automatically enriches the listing with spatial zoning tags (`"Dính quy hoạch mở đường"` or `"100% Đất ở đô thị"`).
- **Given** an AI Agent session, **When** calling `realestate_check_zoning(lat, lng)`, **Then** spatial planning status and confidence level are returned.

**Validation & Testing:**
- Unit tests: `test_spatial_planning.py` (Coordinate ordering assertion `(lng, lat)`, VN-2000 reprojection).
- Integration test: `test_postgis_spatial_query.py` (PostGIS `ST_Intersects` query latency $\le 10$ms).
- Mutation gate target: `SpatialPlanningService` $\ge 85\%$ mutation score.

_AD-GIS-1 · AD-GIS-2 · AD-GIS-4 · AD-GIS-5 · AD-GIS-6 · Governed by `architecture-bds-planning-and-dkkd-2026-08-15`_

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

### Story 12.9: Job Market Alerts `[P1]`

As a job market researcher,
I want to receive alerts when new postings match my criteria,
So that I don't have to manually re-run searches every day.

> **Prerequisite:** Saved search infrastructure (Story 12.6 or equivalent) is available. If not, the alert scheduler uses an inline query equivalent to maintain story independence.

**Acceptance Criteria:**
- **Given** a saved job search with filters (title, location, salary range), **When** a new posting matches, **Then** I receive an in-app notification.
- **Given** an alert is triggered, **When** I click it, **Then** I see the new matching results.
- **Given** multiple alerts, **When** viewed, **Then** they are grouped by search query with match count.
- **Given** saved job search bị xóa hoặc source scraper trả về `degraded=true` với không có posting mới, **When** alert job chạy, **Then** nó skip alert, log `search_missing`/`degraded_source`, và scheduler tiếp tục.
**Validation:**
- Unit test: `test_job_alert_matching.py` — new posting triggers alert
- Integration test: `test_job_alert_notification.py` — notification delivered

_AD-33 (Generic Alert Engine — AlertRule template, `new_items` diff strategy)._

### Story 12.10: LinkedIn Public Guest Jobs & Headcount Growth Signals `[P1]`

As an executive recruiter or B2B SaaS founder,
I want to scrape job listings via LinkedIn Public Guest API (`seeMoreJobPostings`) without login and track hiring velocity,
So that I can identify expanding companies and source high-level candidates.

**Acceptance Criteria:**
- **Given** search criteria (keyword, location `geoId`, time filter `f_TPR`), **When** `LinkedInGuestScraper.search_jobs()` runs, **Then** it fetches HTML fragments from `seeMoreJobPostings/search` using rotating residential proxies (`socks5h://` with remote DNS resolution) and token-bucket rate limit $\le 25$ req/min/IP without requiring user credentials.
- **Given** raw HTML chunks, **When** `selectolax` parser processes `data-entity-urn="urn:li:jobPosting:<id>"` with semantic fallback selectors, **Then** it extracts `title`, `company_name`, `company_slug`, `location`, `posted_at`, and `salary` into `linkedin_jobs` with unique constraint on `job_id`.
- **Given** recruiter/contact information inside job descriptions, **When** persisted, **Then** it runs through `app/canonical/services/canonical_pii.py` to redact personal emails/phones before vector embedding generation (`vector(1536)`).
- **Given** new jobs for a target company, **When** ingested, **Then** `linkedin_companies.active_jobs_count` is updated and `hiring_velocity_30d` is recomputed.
- **Given** HTTP 429 or 302 Authwall challenge, **When** encountered, **Then** it triggers exponential backoff jitter with proxy rotation.
- **Given** an AI Agent session, **When** calling `linkedin_search_jobs(query, location, limit)`, **Then** matched job postings with company metrics are returned.

**Validation & Testing:**
- Unit test: `test_linkedin_guest.py` (Hermetic `selectolax` parsing on golden HTML fixtures, 429 backoff).
- Drift Canary: Periodic 6-hour test verifying selector validity against LinkedIn public guest endpoint.

_AD-LI-1 · AD-LI-2 · AD-LI-3 · AD-LI-5 · Governed by `architecture-linkedin-b2b-2026-08-15`_

---

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

### Story 14.2a: News Entity Extraction `[P1]`

As a researcher,
I want named entities (people, organizations, locations) extracted from news articles and attached to `Chunk` metadata before the article is sent to `chainlens-research`,
So that `chainlens-research` can index those entities later without needing a re-ingest.

**Acceptance Criteria:**
- **Given** a news article is parsed, **When** entity extraction runs, **Then** named entities (people, organizations, locations) are extracted with confidence scores.
- **Given** extracted entities, **When** the article is normalized to a `Chunk`, **Then** `metadata.entities` contains the entity mentions, types, and redacted surface forms; the article is still sent to `chainlens-research` via `NowingIngestService`.
- **Given** the entity extraction model returns an empty entity list or malformed JSON, **When** entity enrichment runs, **Then** it falls back to `metadata.entities = []` and the article is still indexed.
- **Given** the workspace cannot pay for entity extraction (insufficient wallet / `QuotaInsufficientError`, news-entity-extraction budget exceeded, or rate-limited), **When** extraction is requested, **Then** no LLM call is made, extraction degrades to `metadata.entities = []`, logs `news_entity_extraction_{reason}`, and the article is still indexed.
- **Given** `NowingIngestService` fails to ingest a news `Chunk[]` to `chainlens-research` (5xx, auth unavailable, timeout, max retries), **When** the failure occurs, **Then** it logs `chainlens_news_ingest_failed`, emits a metric, persists a `ChainLensIngestJob` with status `failed`, continues processing the rest of the batch, and does not fall back to a local `Document`/`Chunk` index (AD-35).

**Validation:**
- Unit test: `test_news_entity_extraction.py` — entity accuracy ≥ 0.85, fallback, confidence threshold, deduplication
- Unit test: `test_news_entity_redaction.py` — person surface forms masked to `<NAME>` in `Chunk.content` and `metadata.entities`
- Unit test: `test_news_entity_extract_budget.py` — gate blocks when disabled, budget exceeded, rate-limited, wallet insufficient
- Integration test: `test_news_entity_chunk_metadata.py` — `NowingIngestService.ingest()` called with `metadata.entities` and correct AD-34 fields

_AD-34 · AD-35 · AD-25 (PII redaction for person names)_

### Story 14.2b: News Entity Search `[P1]`

> **Blocked-by-external (2026-08-24):** `chainlens-research` chưa hỗ trợ entity search / ingest với entity metadata. Câu chuyện này phụ thuộc vào contract của engine; Nowing chỉ cần agent wiring khi contract sẵn sàng. Giữ `backlog` trong `sprint-status.yaml`.

As a researcher,
I want to ask the chat agent about people, organizations, or locations mentioned in news,
So that the agent can query the canonical index and return relevant articles with citations.

**Acceptance Criteria:**
- **Given** `chainlens-research` exposes entity search and accepts `metadata.entities` at ingest, **When** a `Chunk` with `metadata.entities` is ingested, **Then** the canonical index stores and indexes the entity metadata; `chainlens-research` handles entity linking and disambiguation.
- **Given** entity tracking is active in the canonical index, **When** a user queries an entity in chat, **Then** the agent calls `chainlens-research` and returns mentioning articles with citations; no local entity table is built in Nowing.

**Validation:**
- Integration test: `test_news_entity_search_chainlens.py` — entity query returns indexed articles (stub/mocked until chainlens contract lands)

_AD-34 · AD-35 · AD-27_

---

### Story 14.3: News Alerts & Topic Monitoring `[P1, MERGED INTO Story 6.11]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.11 — Vertical Alert Rule Templates**. Giữ lại để traceability; không implement riêng.

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

### Story 14.4: News Digest & Synthesis `[P2, MERGED INTO Story 6.12]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.12 — Narrative Report Engine for Indexed Data**. Giữ lại để traceability; không implement riêng.

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

_AD-34 · AD-35 · Reuses archived `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-ecosystem-search.md` (citation model; UX chuẩn hiện tại: `ux-Nowing-2026-08-15`) · AD-33 (scheduler)_

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

### Story 15.3: Stock Price Alerts `[P1, MERGED INTO Story 6.11]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.11 — Vertical Alert Rule Templates**. Giữ lại để traceability; không implement riêng.

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

### Story 15.4: Financial Trend Detection `[P2, MERGED INTO Story 6.12]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.12 — Narrative Report Engine for Indexed Data**. Giữ lại để traceability; không implement riêng.

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

> **Implementation status (2026-08-20):** `app/proprietary/platforms/masothue/` scraper and MCP tool `nowing_masothue_scrape` already exist. Missing `app.capabilities.masothue.scrape` executor, `BillingUnit.MASOTHUE_COMPANY`, and mutation-gate retest. Sprint status updated to `in-progress`.

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

### Story 16.2: Official Business Registry (`dangkykinhdoanh.gov.vn`) `[P1]`

As a compliance researcher, corporate lawyer, or due diligence analyst,
I want official company registration data, authentic charter capital, founding shareholders, and PDF change declarations from `dangkykinhdoanh.gov.vn`,
So that I can verify authentic legal data rather than unverified third-party estimates.

**Acceptance Criteria:**
- **Given** a Tax Code (MST), **When** `NationalBusinessRegistryScraper.lookup_enterprise(tax_code)` runs, **Then** it queries `dangkykinhdoanh.gov.vn` and downloads official public declaration PDFs.
- **Given** the declaration PDF, **When** parsed by Nowing PDF Parser, **Then** text is normalized via `unicodedata.normalize('NFC')` and converted from legacy TCVN3/VNI font encodings to UTF-8 (with OCR fallback for scanned image PDFs), and charter capital, founding shareholders, and legal representative history are saved into `official_enterprise_registrations`.
- **Given** official data is fetched, **When** normalized to `Chunk[]`, **Then** it uses the same canonical `sourceId` as the masothue record with `metadata.conflict_flags` (e.g. `charter_capital_mismatch`) set for `chainlens-research`.
- **Given** government portal returns 403 or tax code is not found, **When** scraper runs, **Then** it returns `degraded=true` with `not_found` and preserves existing data.

**Validation & Testing:**
- Unit test: `test_dangkykinhdoanh_pdf.py` — Vietnamese font & Unicode NFC decoding.
- Integration test: `test_business_gov_vn.py` — official data accessible and stored in `official_enterprise_registrations`.

_AD-GIS-3 · AD-GIS-5 · AD-34 · AD-35 · AD-SOC-1 · AD-SOC-9 · Governed by `architecture-bds-planning-and-dkkd-2026-08-15` & `architecture-xactions-social-integration-2026-08-15`_

> **XActions Delegation Note (AD-SOC-1 & AD-SOC-9):** Do NOT build raw headless browser crawlers or captcha solvers inside Nowing. Raw portal scraping of `dangkykinhdoanh.gov.vn` (government captcha, session warmup, PDF download) is delegated to XActions (`x_dangkykinhdoanh` MCP tool). Nowing focuses purely on `DkkdLeadAdapter` ingestion, PDF/Unicode normalization, extraction of charter capital/shareholders into `official_enterprise_registrations`, and Confidence Gate verification (Story 21.21).

---

### Story 16.3: Company Alerts `[P1, MERGED INTO Story 6.11]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.11 — Vertical Alert Rule Templates**. Giữ lại để traceability; không implement riêng.

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

---

### Story 16.4: Company Timeline `[P1, MERGED INTO Story 6.12]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.12 — Narrative Report Engine for Indexed Data**. Giữ lại để traceability; không implement riêng.

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

### Story 16.5: National Public Procurement & Tender Intelligence (`muasamcong.mpi.gov.vn`) `[P1]`

As a business development manager or bid analyst,
I want to ingest public bidding notices (TBMT), award results (KQLCNT), and parse attached tender dossiers (E-HSMT PDF/ZIP) from `muasamcong.mpi.gov.vn`,
So that I never miss lucrative government procurement projects and can semantically search tender requirements with AI.

**Acceptance Criteria:**
- **Given** search filters (field, date range, price), **When** `MuasamcongScraper.search_tenders()` runs, **Then** it queries the e-GP v2.0 REST API with residential VN proxy, throttled by token-bucket rate limit $\le 15$ req/min/IP, and parses structured JSON bidding notices into `procurement_tenders` with composite unique constraint `(bid_code, bid_turn_no)`.
- **Given** a bidding notice with attached HSMT files (PDF/ZIP/RAR), **When** `download_hsmt_documents_task` runs, **Then** files are streamed into S3 bucket `s3://nowing-procurement-docs/{bid_code}/` in 128KB chunks via `aioboto3` (memory safe, never buffering full file into RAM), ZIP files are safely unarchived decoding CP437/CP1258 filenames, and parsed text is chunked into `procurement_tender_chunks` with `embedding vector(1536)` and HNSW index.
- **Given** an active `AlertRule` matching enterprise field and price threshold, **When** a matching tender is published, **Then** `AlertEngine` fires an instant alert notification.
- **Given** an AI Agent session, **When** calling `procurement_search_tenders()` or `procurement_summarize_hsmt(bid_code)`, **Then** the agent extracts key requirements, contractor financial prerequisite (3-year average revenue, similar contracts, bid guarantee), and submission deadlines directly from vector chunks.

**Validation & Testing:**
- Unit test: `test_muasamcong_client.py` (Rate-limiter throttling, JSON parsing).
- Integration test: `test_muasamcong_s3_stream.py` (S3 128KB streaming memory safety, MD5 hash verification).

_AD-PROC-1 · AD-PROC-2 · AD-PROC-3 · AD-PROC-4 · AD-PROC-5 · AD-PROC-6 · AD-PROC-7 · Governed by `architecture-muasamcong-procurement-2026-08-15`_

---

## Epic 17: E-commerce Intelligence (Vietnam)

### Story 17.1: Lazada Product Data `[P1]`

> **Blocked-by-external (2026-08-23):** Raw scraping và anti-bot proxy rotation được giao cho `XActions` (`x_lazada_search` / `x_lazada_product` MCP tools) theo AD-SOC-1/AD-SOC-9. Story 17.1 chỉ implement `LazadaLeadAdapter` + normalization sau khi MCP tool sẵn sàng. Chuyển `backlog` trong `sprint-status.yaml` cho đến khi XActions tool tồn tại.

As a product researcher,
I want product data from Lazada Vietnam including price, seller, ratings, and variants,
So that I can perform pricing analysis and competitor tracking.

**Acceptance Criteria:**
- **Given** the `XActions` `x_lazada_search` / `x_lazada_product` MCP tool is available and returns product data, **When** a user searches by product keyword, **Then** product listings are returned with: title, price, original price, discount, rating, review count, seller name, variants.
- **Given** product data is fetched from XActions, **When** normalized to `Chunk[]`, **Then** `metadata.source: 'xactions_adapter'`, `sourceId` (stable: normalized `title` + `seller_id` + `sku` if available), `domain: 'lazada.vn'`, `fetchedAt`, `contentType: 'product'` are set.
- **Given** the XActions tool returns anti-bot/captcha, **When** the adapter handles it, **Then** it propagates `degraded=true` with `degradation_reason: ANTI_BOT`; no in-house Playwright crawler is built inside Nowing.
- **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** the user queries product data, **When** the agent calls `chainlens-research` `POST /api/v1/search`, **Then** indexed results are returned with citations.

**Validation:**
- Integration test: `test_lazada_scrape.py` — product data extracted
- Unit test: `test_lazada_to_chunks.py` — `sourceId` stable
- Anti-bot test: `test_lazada_graceful_degradation.py` — backs off on 403/CAPTCHA
- Integration test: `test_lazada_ingest_chainlens.py` — chunks sent to `chainlens-research`

_AD-34 · AD-35 · AD-SOC-1 · AD-SOC-9 · Method: Consumes XActions MCP tool / Fast API JSON_

> **XActions Delegation Note (AD-SOC-1 & AD-SOC-9):** Do NOT build in-house Lazada Playwright crawlers inside Nowing. Raw product scraping and anti-bot proxy rotation are delegated to XActions (`x_lazada_search` / `x_lazada_product` MCP tools). Nowing focuses on `LazadaLeadAdapter`, schema normalization into `ecommerce_products`, Confidence Gate verification, and `chainlens-research` ingestion.

### Story 17.2: Shopee Vietnam In-House Scraper & Price Normalization `[P1]`

As a market intelligence analyst,
I want product data from Shopee Vietnam (70%+ market share) via internal fast JSON API (`/api/v4/search/search_items` and `/api/v4/item/get`),
So that I can track products, historical units sold, ratings, and price history with high performance (<200ms) without headless browser overhead.

**Acceptance Criteria:**
- **Given** search parameters (keyword, sort by relevancy/sales/price), **When** `ShopeeScraper.search_items()` is called, **Then** it queries `https://shopee.vn/api/v4/search/search_items` with mobile headers (`User-Agent: Shopee/3.x`, `x-api-source: rsrc`) and residential VN proxy, returning paginated items within $\le 200$ms.
- **Given** item price from Shopee API, **When** parsed, **Then** the engine divides price by `100,000` using `Decimal(raw_price) / Decimal("100000")` quantized to `NUMERIC(18, 2)` with `ROUND_HALF_UP` (preventing floating point inaccuracies) and saves into `ecommerce_products.current_price` and `original_price`.
- **Given** item data is fetched, **When** stored in PostgreSQL, **Then** it executes an idempotent UPSERT on `(platform, item_id, shop_id)` and records a new entry into `ecommerce_price_history` ONLY when `new_price != last_recorded_price` (time-series deduplication).
- **Given** product details request (`item_id`, `shop_id`), **When** calling `ShopeeScraper.get_item_detail()`, **Then** it returns full specs, description, brand, shop location, rating count breakdown, and historical units sold.
- **Given** Shopee API returns 429 or CAPTCHA, **When** detected, **Then** `ScraperPlatformAccountRotator` rotates proxies with backoff jitter and returns `degraded=true` if all retries are exhausted.

**Validation & Testing:**
- Unit test: `test_shopee_price_scaling.py` — verifies `Decimal` division by 100,000 and bounds sanity check.
- Integration test: `test_shopee_search_and_upsert.py` — checks idempotent PostgreSQL persistence and price deduplication.
- Mutation gate target: `ShopeeScraper.normalizer` $\ge 85\%$ mutation score.

_AD-EC-1 · AD-EC-2 · AD-EC-3 · AD-EC-4 · Governed by `architecture-shopee-ecommerce-2026-08-15`_

---

### Story 17.5: TikTok Shop Product & Trending SKUs Ingestion `[P2]`

> **Blocked-by-external (2026-08-23):** Codebase hiện chỉ có public TikTok video scraper, không có TikTok Shop. Raw scraping TikTok Shop được giao cho `XActions` (`x_tiktok_shop_products` MCP tool) theo AD-SOC-1/AD-SOC-2/AD-SOC-9. Story 17.5 chỉ implement adapter + normalization sau khi MCP tool sẵn sàng. When implemented, reuse `ecommerce_products` + `ecommerce_price_history` schema and alert patterns from Shopee architecture (AD-EC-1..6).

As a social commerce researcher,
I want product, pricing, and sales volume data from TikTok Shop Vietnam,
So that I can analyze viral e-commerce trends, top KOC promoted products, and competitive pricing.

**Acceptance Criteria:**
- **Given** the `XActions` `x_tiktok_shop_products` MCP tool is available, **When** a user provides a search query or category, **Then** product listings are returned with title, current price (using divisor `1.0`), units sold, shop name, rating, and creator/affiliate metrics.
- **Given** product data is fetched from XActions, **When** normalized and stored, **Then** records are saved into `ecommerce_products` with `platform: 'tiktok_shop'` and linked to `ecommerce_price_history`.
- **Given** historical product runs, **When** analyzed, **Then** the engine calculates sales velocity `(sold_t2 - sold_t1) / delta_days` to classify trending breakout SKUs.
- **Given** an AI Agent session, **When** calling `ecommerce_search_products(platform='tiktok_shop', query=...)`, **Then** top trending products with sales velocity metrics are returned.

_AD-EC-1 · AD-EC-2 · AD-EC-3 · AD-EC-6 · AD-SOC-1 · AD-SOC-2 · AD-SOC-9_

> **XActions Delegation Note (AD-SOC-1, AD-SOC-2 & AD-SOC-9):** Do NOT build anti-tamper TikTok signature bridges (`msToken`, `_signature`) inside Nowing. Raw TikTok Shop scraping and crawler sessions are delegated to XActions (`x_tiktok_shop_products` MCP tool). Nowing focuses on `TikTokShopLeadAdapter`, schema mapping into `ecommerce_products` / `ecommerce_price_history`, trending sales velocity calculations, and AI Agent query tools.



---

### Story 17.3: Price Drop Alerts `[P1, MERGED INTO Story 6.11]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.11 — Vertical Alert Rule Templates**. Giữ lại để traceability; không implement riêng.

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

### Story 17.4: Competitor Tracking `[P2, MERGED INTO Story 6.11]`

> **Merged 2026-08-20:** Nội dung story này được gộp vào **Story 6.11 — Vertical Alert Rule Templates**. Giữ lại để traceability; không implement riêng.

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

_Kỹ thuật: `app/routes/agent_chat_routes.py`, PAT auth middleware, rate limiter. **AD-29** (public agent-chat surface). **Prerequisite:** AD-13 ResearchThread linkage; if not yet accepted, the endpoint returns 503 for auto-link and falls back to `research_thread_id = null` with a clear warning._

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

_Kỹ thuật: `app/db.py` (AgentConfig model), Alembic migration (number assigned at implement time), seed script. **AD-30**. UX (đã lưu trữ): `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-agent-registry.md`; UX chuẩn hiện tại: `ux-Nowing-2026-08-15`._

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

_Kỹ thuật: `app/routes/agent_chat_routes.py` — auto-create ResearchThread, update response schema. **AD-13** + **AD-29**. **Prerequisite:** AD-13 ResearchThread linkage accepted; if not, the response omits `research_thread_id` and logs `research_thread_link_degraded`._
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

_Kỹ thuật: Alembic migration for memory tenant tags, update `app/retriever/`. **AD-31**, NFR-MULTI-1. **Prerequisite:** AD-31 tenancy design accepted; ACs are conditional on `AD-31_accepted=true`._
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

_Kỹ thuật: Middleware in `app/middleware/tenant_context.py`, rate limiter with Redis. **AD-29** + **AD-31**, NFR-MULTI-1. **Prerequisite:** AD-31 composite RLS design accepted; if AD-31 is not yet accepted, this story is conditional and may be split into an AD-31 prerequisite plus implementation story._

---


---


## Epic 21: Lead Gen Intelligence `[in-progress]` *(umbrella — implementation ở E23, E24, E25, E26)*

> **Epic Goal:** Umbrella / tracking epic cho hệ sinh thái săn lead. Implementation chi tiết đã phân tán sang các epic con: E23 (Lead Capture, Real-Time Enrichment & Automated Outreach), E24 (Enterprise Lead Conversion & Multi-Channel Outreach + Team CRM), E25 (Platform Administration & Multi-Tenant Operations), E26 (Autonomous Lead Missions & Deep Sales Research). Epic 21 detailed stories (21.1–21.21) below are **superseded** by E23–E26 stories; kept for historical traceability.

**Status:** `[in-progress]`  
**Governed by Architecture Spines:** `architecture-xactions-social-integration-2026-08-15`, `architecture-linkedin-b2b-2026-08-15`, `epic21-architecture-update.md` (AD-31 to AD-49).  
**UX Contracts (đã lưu trữ):** `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-lead-intelligence-panel.md`, `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-workspace-mode-switch.md`, `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-sidebar-onboarding.md`, `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-positive-reply-notifications.md`. UX chuẩn hiện tại: `ux-designs/ux-Nowing-2026-08-15/`.

---

### Story 21.1: Intent Signal Detection `[DONE]`

As a sales development representative or investor,
I want to detect buying signals from target companies and market posts (funding, hiring surges, tech stack changes, executive moves, social buy/sell requests),
So that I can reach out at the exact moment of highest conversion intent.

**Acceptance Criteria:**
- **Given** a monitored company or social feed in workspace, **When** signals are detected, **Then** funding events, job postings, tech stack changes, and executive moves are surfaced with `signal_type`, `confidence` (float 0.0–1.0), `source_url`, and `detected_at` timestamp.
- **Given** a signal is detected, **When** stored, **Then** it writes a `SignalEvent` row (with `id: UUID`, `workspace_id`, `client_id`) and a redacted `Memory` row of type `semantic` with tag `lead_signal` and `source_uuid: UUID`, `source_entity_type: 'signal_event'` (AD-44).
- **Given** a signal trigger is configured, **When** it fires, **Then** it uses an AD-33 `AlertRule` template with `capability_id` set to a registered signal capability (e.g. `funding.signal`, `hiring.signal`) and `notification_channels` (`in_app`, `telegram`, `email`).
- **Given** a signal scan runs, **When** metered, **Then** LLM token costs go to `TokenUsage`, and the business scan event writes to `BillingEvent` with `usage_type = "signal_scan"`.

_FR-63 · AD-31 · AD-33 · AD-37 · AD-44_

---

### Story 21.2: Lead Scoring & Prioritization `[DONE]`

As a sales manager,
I want leads automatically scored and ranked by conversion likelihood (Fit Score & Intent Score),
So that my team focuses attention on the highest-value prospects.

**Acceptance Criteria:**
- **Given** a lead list, **When** scored by `LeadScoringService`, **Then** each lead receives a composite score ($0.0 \le \text{Score} \le 100.0$) calculated as: $\text{Composite} = 0.5 \times \text{FitScore} + 0.5 \times \text{IntentScore}$.
- **Given** computed scores, **When** displayed on UI, **Then** badges render in 3 color tiers (`🟩 Hot >= 80`, `🟨 Warm 50-79`, `⬜ Cold < 50`) with inline breakdown factors in a clickable popover.
- **Given** a score calculation completes, **When** persisted, **Then** it writes a `LeadScore` row (`id: UUID`, `workspace_id`, `client_id`, `factors_json`, `computed_at`) and records a `BillingEvent` row with `usage_type = "lead_scoring"`.
- **Given** vector search is unavailable, **When** scoring runs, **Then** it falls back to heuristic rule-based firmographic scoring without failing the request.

_FR-64 · AD-31 · AD-38 · AD-42_

---

### Story 21.3: Vietnam Phone & Contact Waterfall Engine `[DONE]`

As an SDR or real estate broker in Vietnam,
I want a multi-tiered phone resolution engine that unlocks hidden mobile numbers from scraped listings with real-time verification and auto-refund SLA,
So that I obtain verified, callable phone numbers without wasting credits on dead contacts.

**Acceptance Criteria:**
- **Given** a raw lead or scraped property listing (Batdongsan, Muaban, Chotot), **When** phone resolution is triggered, **Then** `PhoneWaterfallEngine` executes a 3-tier fallback sequence:
  1. *Tier 1 (Batdongsan/Muaban Token Pool):* Uses internal session token pool with Redis Mutex rotation (`batdongsan:token:{id}`) to decode masked phone numbers (`0908 123 ***` $\to$ `0908 123 456`).
  2. *Tier 2 (Chotot Mobile API):* Fallbacks to Chotot Mobile API `/v1/public/ad-listing/{id}?phone=true` with device UUID spoofing.
  3. *Tier 3 (Zalo UID & Carrier Prefix Verification):* Validates carrier prefix (Viettel, VNPT, Mobi) and performs passive HLR/Zalo verification.
- **Given** successful phone resolution, **When** contact is stored, **Then** raw phone is encrypted via AES-256 in `VerifiedContact` table (PII Vault, AD-25) and masked in standard API responses (`0908***456`).
- **Given** phone resolution succeeds, **When** billed, **Then** it debits 1.5 credits (1,500đ) into `BillingEvent` with `usage_type = "contact_enrichment"`. If all tiers fail, 0 credits are debited.
- **Given** a user reports a dead/disconnected number within 24h, **When** verified, **Then** `BillingService.auto_refund_lead()` refunds 100% credits back to `User.credit_micros_balance` and marks the number `invalid`.

**Validation & Testing:**
- Unit test: `test_waterfall_failover_circuit.py` — verifies transition Tier 1 $\to$ Tier 2 $\to$ Tier 3.
- Unit test: `test_pii_encryption_at_rest.py` — asserts phone is encrypted in DB and redacted in logs.
- Integration test: `test_auto_refund_credit_ledger.py` — verifies credit refund on dead number report.

_FR-65 · AD-25 · AD-31 · AD-36 · AD-42 · Nghị định 13/2023/NĐ-CP_

---

### Story 21.4: Outbound Prospecting Automation & Panel `[DONE]`

As a sales team,
I want to create multi-step outbound email sequences connected to dynamic lead lists in a 2-panel split interface,
So that I can scale personalized outreach while tracking live delivery, open, and reply rates.

**Acceptance Criteria:**
- **Given** a lead list, **When** a sequence is created, **Then** it uses independent Bounded Context tables (`Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`) with `id: UUID`, `workspace_id`, `client_id` (AD-39, not polluting `automations` table).
- **Given** step execution, **When** personalized emails are sent via Amazon SES / SMTP, **Then** Jinja template renders lead attributes (name, company, property details) and records `BillingEvent` (`usage_type = "email_send"`).
- **Given** inbound email replies, **When** received via SES webhook / IMAP idle, **Then** `ReplyClassifier` detects positive replies and dispatches instant notifications to user's Telegram / In-app inbox.

_FR-66 · AD-31 · AD-33 · AD-39 · AD-42_

---

### Story 21.5: CRM Integration & Lark Base / Google Sheets 1-Click Sync `[DONE]`

As a sales operations manager,
I want to sync lead data bi-directionally with HubSpot, Salesforce, Lark Base, and Google Sheets,
So that reps work seamlessly within their existing company workflows.

**Acceptance Criteria:**
- **Given** an authorized CRM connection, **When** lead data changes, **Then** `CrmSyncService` executes read-first deduplication before pushing records to prevent overwriting existing CRM data (AD-40).
- **Given** a user triggers "Export to Lark Base / Google Sheets", **When** processed by Celery worker, **Then** it batches rows (500 records/chunk) with column type mapping (Text, Phone, SingleSelect, Email) using idempotency header `X-Nowing-Sync-Id`.
- **Given** local Vietnam CRMs (Pancake, Haravan, KiotViet, Getfly), **When** configured, **Then** webhook payloads are dispatched on lead status update events.

_FR-67 · AD-3 · AD-31 · AD-40_

---

### Story 21.6: Vietnam Outbound Automation (Zalo OA & Telegram Sender) `[DONE]`

As a Vietnamese sales representative or real estate agent,
I want 1-click Zalo outreach assistance and Telegram notifications for high-intent leads,
So that I can communicate with prospects on Vietnam's primary messaging channels (85%+ open rate) safely without account ban risks.

**Acceptance Criteria:**
- **Given** a verified lead with phone number, **When** SDR clicks `[ 💬 Nhắn Zalo ]` in UI, **Then** the client opens direct deep-link `https://zalo.me/{phone}` with AI pre-composed personalized greeting message based on listing details (Assisted Outbound Co-pilot mode, 100% ToS compliant).
- **Given** an enterprise workspace with connected Zalo OA, **When** official transactional/meeting notifications are triggered, **Then** backend sends official ZNS (Zalo Notification Service) templates via Zalo OpenAPI.
- **Given** a lead showing positive buying signal or reply, **When** triggered, **Then** Telegram Bot sends instant rich alert with inline action buttons (`[ Xem Lead ]`, `[ Gọi ngay ]`).

_FR-68 · AD-31 · AD-41 · AD-SOC-7_

---

### Story 21.7: Outcome-Based Pricing & Transparent Credit Ledger `[DONE]`

As a sales team founder,
I want a transparent economic model with $0 cost for AI Chat & Sequencer and pay-as-you-go credits for verified leads and booked meetings,
So that software costs directly reflect business value generated.

**Acceptance Criteria:**
- **Given** any workspace, **When** using AI Chat, transforming tables, creating sequences, or exporting CSVs, **Then** cost is 0 credits ($0.00).
- **Given** enrichment or outcome events, **When** recorded, **Then** `BillingEvent` debits `User.credit_micros_balance`:
  - Verified Phone Unlock: 1.5 credits (1,500đ / $0.06).
  - Deep Research Dossier: 5.0 credits (5,000đ / $0.20).
  - Qualified Meeting Booked (`OutcomeEvent`): 50.0 credits (50,000đ / $2.00).
- **Given** the usage dashboard, **When** viewed, **Then** it renders real-time donut & bar charts breakdown by service (`AI Generation`, `Web Search`, `Social Media`, `Phone Waterfall`) with `[ 🎁 Claim Promo Code ]` input.

_FR-69 · AD-8 · AD-10 · AD-31 · AD-42_

---

### Story 21.8: Social Ingress via XActions Integration (Facebook Groups & Twitter/X Feed) `[DONE]`

As a B2B sales development representative or real estate investor,
I want to ingest targeted Facebook Group posts and Twitter keyword searches via XActions integration (`/Users/luisphan/Documents/GitHub/XActions`),
So that I can capture real-time social conversations and extract contact numbers without building scrapers from scratch.

**Acceptance Criteria:**
- **Given** target groups or search keywords, **When** `XActionsSocialAdapter` calls `x_facebook_group_posts` or `x_search_tweets`, **Then** raw social posts are fetched via XActions stealth session pool with sticky 1-to-1 residential proxy IP binding per account.
- **Given** raw post data, **When** ingested into PostgreSQL, **Then** records are saved into `social_monitored_targets` and `social_posts` with unique constraint `(platform, external_post_id)` and pushed to Redis Stream `stream:social:raw_posts`.
- **Given** post content, **When** `SocialEntityExtractor` processes the text, **Then** it runs a 3-step pipeline (pre-normalization of letter-substitutions `o/O->0`, punctuation stripping, Vietnamese regex pattern matching) protected by a 50ms timeout against ReDoS, extracting phone numbers (formats `0912...`, `o9.xx...`, `+84...`), prices, and locations into `raw_entities JSONB`, and assigning `intent_tag: 'sell'`, `'buy'`, `'hiring'`, or `'seeking'`.
- **Given** new ingested posts, **When** matching active `AlertRule` saved searches, **Then** `AlertEngine` fires instant notifications via Telegram/Email.
- **Given** an AI Agent session, **When** calling `social_search_posts(platform, intent, keyword)`, **Then** matched posts with extracted contact numbers are returned.

**Validation & Testing:**
- Unit test: `test_obfuscated_phone_regex.py` — verifies extraction of 10+ obfuscated VN phone variants.
- Unit test: `test_phone_regex_redos_safety.py` — asserts execution $\le 50$ms on pathological input strings.
- Integration test: `test_social_redis_stream.py` — verifies Redis Stream ingestion and Celery processing.

_AD-SOC-1 · AD-SOC-2 · AD-SOC-4 · AD-SOC-5 · AD-SOC-6 · AD-SOC-7_

---

### Story 21.9: Executive Decision Maker Mapping & B2B Lead Outreach `[DONE]`

As an enterprise sales team or SaaS founder,
I want to identify C-Level executives and HR leaders of expanding companies,
So that I can initiate personalized outreach and CRM synchronization.

**Acceptance Criteria:**
- **Given** a target company (`company_slug` or company name), **When** `LinkedInCompanyService.enrich_executives()` runs, **Then** it executes public Google SERP dorking (`site:linkedin.com/in/ "Company" ("CEO" OR "Director" OR "Founder")`) avoiding login wall, extracting public professional leadership profiles into `linkedin_companies.decision_makers JSONB` in strict compliance with Nghị định 13/2023/NĐ-CP.
- **Given** an AI Agent session, **When** calling `linkedin_lookup_company_executives(company_name)` or `social_search_posts(platform, intent, keyword)`, **Then** verified leadership names, titles, and public contact signals are returned.

_AD-LI-4 · AD-LI-6_

---

### Story 21.10: 1-Click Reverse-ICP from Website / Project URL `[DONE]`

As a business owner or broker,
I want to paste my website domain or a real estate project link and have Nowing automatically generate the Ideal Customer Profile (ICP), search filters, and lead table,
So that I can launch targeted lead discovery in under 10 seconds without manual prompt writing.

**Acceptance Criteria:**
- **Given** a valid URL (e.g. `vinhomes.vn`, `topcv.vn`, or project landing page), **When** `ReverseIcpService.analyze_url(url)` executes, **Then** `FastCrawler` extracts OpenGraph tags, schema JSON-LD, and hero content within 2.5s.
- **Given** extracted metadata, **When** processed by `LLMBundle`, **Then** it generates `ReverseIcpResponse`: Value Proposition, 3 Target Buyer Personas (Title, Industry, Company size), Suggested Search Queries, Negative Keywords, and Auto-configured Filter Presets.
- **Given** generated ICP response, **When** returned to frontend, **Then** the UI auto-populates the Multi-Table filter bar and pre-fills the chat prompt box with ready-to-run discovery tasks.

_FR-80 · AD-31 · AD-37_

---

### Story 21.11: Actionable Turn Dispatches (Suggested Action Pills) `[DONE]`

As an active user in the split-view chat interface,
I want AI responses to include contextual 1-click execution chips (Suggested Action Pills),
So that I can advance lead workflows (decode numbers, trigger Zalo drafts, find similar leads) with zero typing friction.

**Acceptance Criteria:**
- **Given** any discovery or scraper chat turn completion, **When** `ChatOrchestrator` emits response stream, **Then** it appends structured JSON `suggested_actions`: array of `{ id, label, icon, action_type, prompt_template, cost_credits, payload }` (max 3 pills).
- **Given** action pills rendered below chat bubble, **When** user clicks a pill (e.g. `[ 📱 Giải mã 9 SĐT (13.5 credits) ]`), **Then** frontend dispatches the linked action immediately without requiring user re-typing.
- **Given** action execution, **When** table rows update via Zero-cache, **Then** newly affected cells flash a brief green pulse highlight (`1s ease-out`).

_FR-81 · AD-31 · UX-Contract-Lead-Panel_

---

### Story 21.12: Viral Social Outbound Co-pilot (Voice Learner & Outlier Analyzer) `[DONE]`

As a founder or real estate influencer,
I want AI to analyze high-performing viral posts in my industry across Facebook, X, and TikTok, learn my voice, and rewrite proven formats into original lead-magnet posts,
So that I can build an organic inbound lead engine alongside outbound prospecting.

**Acceptance Criteria:**
- **Given** user's social profile handle or sample writings in `Content Mode`, **When** `VoiceProfileLearner` runs, **Then** it analyzes tone, sentence structure, hook patterns, and vocabulary, saving a `VoiceProfile` record in Knowledge Base (`tag: "voice_profile"`).
- **Given** industry niche keywords, **When** `ViralPostAnalyzer` queries XActions feed, **Then** it identifies outlier posts (engagement $\ge 3\times$ author baseline), categorizes "Why it worked" (`contrarian_hook`, `story_shift`, `value_list`), and generates draft variations matching user's voice.
- **Given** generated post draft, **When** presented on UI, **Then** the user reviews, edits, and copies the post (Human-in-the-loop: AI never auto-posts to user's personal account).

_FR-82 · AD-SOC-1 · AD-SOC-6_

---

### Story 21.13: Multi-Table Tabs & Send/Export Hub `[DONE]`

As a sales rep managing multiple target campaigns,
I want a browser-tabbed spreadsheet interface supporting multiple simultaneous lead tables with live Zero-cache sync and multi-format export,
So that I can switch between property types, industries, and candidate lists without losing filter state.

**Acceptance Criteria:**
- **Given** a workspace with multiple lead tables, **When** user opens the workspace, **Then** the top toolbar renders scrollable tabs (`TableTabs`), persisting active tab ID in URL query parameter `?table={id}`.
- **Given** active table view, **When** backend streams new leads from scrapers, **Then** Zero-cache (`zero.nowing.net`) updates the reactive table grid with sub-100ms latency without full-page reload.
- **Given** table export, **When** clicking `Send & Export ⌄`, **Then** options modal allows: (1) `Download CSV`, (2) `Sync to Lark Base`, (3) `Sync to Google Sheets`, (4) `Share Read-only Team Link`.

_FR-83 · AD-31 · AD-40 · Zero-Cache-Publication_

---

### Story 21.14: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine `[DONE]`

As a compliance manager and sales leader,
I want to manage Do-Not-Call / Exclusion lists for contacts and domains with CSV bulk import,
So that Nowing automatically blocks outreach to existing clients, competitors, and opt-out leads, ensuring strict compliance with Decree 91/2020/NĐ-CP.

**Acceptance Criteria:**
- **Given** a workspace DNC list, **When** importing CSV or adding individual phone/email/domain, **Then** records are persisted in `workspace_dnc_records` with fields `(workspace_id, entity_type, entity_value, reason, added_by_user_id)`.
- **Given** an active Outbound Sequence, AI Agent session, or phone decode action, **When** a candidate lead matches any DNC rule, **Then** the outreach action is immediately aborted with status `blocked_by_dnc`, and 0 credits are charged.
- **Given** customer right-to-delete requests (Decree 13/2023/NĐ-CP), **When** admin invokes `DELETE /api/leads/{id}/pii`, **Then** all raw PII records are permanently purged within 60s while preserving anonymous aggregated analytical metrics.

_FR-84 · AD-25 · AD-31 · Nghị định 91/2020/NĐ-CP · Nghị định 13/2023/NĐ-CP_

---

### Story 21.15: Unified Multi-Source AI Lead Generation Orchestrator & Universal Scraper Adapters `[DONE]`

As an active sales rep or researcher,
I want to describe my target prospect in natural language in the chat,
So that Nowing's AI Orchestrator automatically plans and triggers parallel searches across ALL available scrapers (Batdongsan, Chợ Tốt, TopCV, ITviec, Masothue, Mua Sắm Công, Facebook Groups, Twitter, Telegram, Google SERP), deduplicates results, enriches verified phone numbers, and streams a structured Lead Table in real-time.

**Acceptance Criteria:**
- **Given** the multi-source scraper ecosystem, **When** `LeadSourceAdapter` abstract base class is defined, **Then** it enforces 3 standardized methods: `search_leads(workspace_id, query)`, `normalize_lead(raw_record)`, and `extract_contact_candidates(raw_record)`.
- **Given** existing implemented scrapers, **When** retrofitted, **Then** 5 concrete adapters are implemented and registered into `LeadSourceAdapterRegistry`:
  1. `BatdongsanLeadAdapter` (Batdongsan.com.vn & Muaban.net BĐS)
  2. `ChototLeadAdapter` (Chợ Tốt Nhà, BĐS, Xe, Đồ điện tử)
  3. `JobMarketLeadAdapter` (TopCV & ITviec recruitment postings)
  4. `EnterpriseProcurementLeadAdapter` (Masothue & Cổng Mua Sắm Công)
  5. `SocialLeadAdapter` (Facebook Groups & Twitter Feed via XActions)
- **Given** a chat prompt (e.g. *"Tìm 30 công ty IT tại Hà Nội và 20 môi giới BĐS Cầu Giấy"*), **When** `LeadGenOrchestrator` executes, **Then** it decomposes the query into sub-tasks and invokes all relevant scraper adapters concurrently via `asyncio.gather(return_exceptions=True)`.
- **Given** raw multi-source streams, **When** ingested, **Then** `EntityDeduplicationService` unifies duplicates by Phone/Email/TaxID into standard `Lead` records.
- **Given** lead creation, **When** persisted, **Then** Zero-cache (`zero.nowing.net`) streams rows directly into the active Table tab with cell highlight animation.

_FR-85 · AD-31 · AD-37 · AD-44_

---

### Story 21.16: Nowing Split-View Canvas & Workspace Modernization `[DONE]`

As a workspace user,
I want a 2-panel split canvas (340px Chat Co-pilot on the left + Resizable Dynamic Canvas on the right) with Mint Green theme, Sọc Caro grid background, bi-directional context sync, and 100% production-ready real APIs,
So that I can interactively chat with AI while inspecting, filtering, and managing real-time leads, research reports, and automations simultaneously without placeholder mocks.

**Acceptance Criteria:**
- **Given** `/dashboard/[workspace_id]/new-chat/[[...chat_id]]`, **When** loaded, **Then** it renders a Split-View (Chat Left + Dynamic Canvas Right) with a draggable divider (`cursor: col-resize`), double-click reset to 340px, and full-screen toggle.
- **Given** the visual system, **When** rendered, **Then** it applies CSS Design Tokens: Emerald `#10B981`, Sọc Caro Grid Paper background, font `Plus Jakarta Sans` and `JetBrains Mono` numbers with proportional sizing (13.5px body, 11px uppercase headers, h-10 row height).
- **Given** user navigation, **When** clicking the 4-Mode Switcher, **Then** the canvas switches smoothly between `Leads Matrix`, `Research Studio`, `Automation Flow`, and `Scraper Health` without losing chat history.
- **Given** real features integration, **When** interacted with, **Then** Credits balance dynamically tracks `currentUserAtom`, Empty State renders 1-click Quickstart Action cards, Research Studio exports real `.md` downloads and printable PDF, and Scraper / Automation tabs connect to live backend APIs.

_FR-86 · AD-31 · UX-Contract-Lead-Panel_

---

### Story 21.17: Complete Origami Landing Page & Public Site Transformation `[DONE]`

As a prospective visitor,
I want a world-class, clean, editorial-style Landing Page with 10 full sections, interactive 3-tab product demo, 12 verticals menu, and clear $0 pricing,
So that I immediately understand Nowing's value proposition as Vietnam's #1 AI Lead Intelligence Platform.

**Acceptance Criteria:**
- **Given** `nowing_web/app/(home)/page.tsx`, **When** deployed, **Then** it replaces the old homepage with the 10-section structure from `landing-page.html`:
  - Section 1: Hero Header with Mint Origami Logo, Badge, Sọc Caro background.
  - Section 2: Interactive 3-Tab Product Showcase (`Lead Generation`, `Data Enrichment`, `Viral Content`).
  - Section 3: Value Metrics & Live Data Feed Counter.
  - Section 4: 12 Industry Verticals Grid (BĐS, Tuyển dụng, Bán sỉ, F&B, Logistics...).
  - Section 5: Step-by-Step Workflow ("From URL to 1000 Leads in 3 Clicks").
  - Section 6: Compare Table (Nowing vs. Apollo / Clay / Manual Scraping).
  - Section 7: Live Pricing Matrix ($0 Chat & Sequencer).
  - Section 8: Affiliate Partner Banner (15% Recurring Commission).
  - Section 9: FAQ Accordion & Knowledge Guide Teaser.
  - Section 10: Final CTA & Editorial Footer.
- **Given** site branding, **When** loaded, **Then** favicon, open-graph cards, and navbar brand render the new **Origami Mint Green Logo**.

_FR-87 · UX-Design-Landing-Page_

---

### Story 21.18: Partners Affiliate Portal & $0 Pricing Page Deployment `[DONE]`

As an affiliate partner or agency,
I want dedicated `/pricing` and `/partners` pages with commission tracking and Stripe/VietQR payout ledger,
So that I can refer clients and earn 15% lifetime recurring commissions.

**Acceptance Criteria:**
- **Given** `/pricing`, **When** viewed, **Then** it displays $0 Free Tier (Unlimited Chat, Sequencer, CSV export) and transparent Credit Pay-as-you-go table for Phone Unlock & Deep Research.
- **Given** `/partners`, **When** an agency applies, **Then** it generates unique referral links with cookie tracking (30 days) and registers a Partner Profile in the database.

_FR-88 · AD-42_

---

### Story 21.19: Lead Source Adapter Live Data Integration & Persistence `[DONE]`

As a sales rep or real estate broker in Vietnam,
I want to describe my target prospects in natural language in chat and get a live multi-source lead table,
So that I can immediately see, persist, and act on verified BĐS, recruitment, and company leads without manual scraping.

**Acceptance Criteria:**

- **Given** a chat prompt like "Tìm 20 nhà đất Hà Nội giá dưới 5 tỷ" or "Tìm công ty logistics tuyển dụng tại TP.HCM", **when** the user sends it, **then** the main agent can trigger `multi_source_lead_gen` and receive a formatted markdown table.
- **Given** the `multi_source_lead_gen` capability, **when** executed, **then** it calls `LeadGenOrchestrator` which dispatches the right adapters (`batdongsan`, `chotot`, `topcv`, `itviec`, `enterprise`) concurrently with `asyncio.Semaphore(5)` and 12s timeout.
- **Given** each adapter, **when** it runs, **then** it calls the existing live scraper function and returns `RawLeadRecord`s with data shapes the `normalize_lead` method can consume.
- **Given** normalized leads, **when** persistence is triggered, **then** `LeadBatchService.ingest_batch` is used to create `Lead` and `VerifiedContact` rows with correct `value_hmac`, DNC filtering, and PII encryption.
- **Given** a lead with phone or email, **when** persisted, **then** `VerifiedContact` is created with `verification_status="verified"`, `consent=True`, `legal_basis="legitimate_interest"`.
- **Given** job-market leads without direct contact, **when** persisted, **then** `Lead` is still created using `company_name` for `value_hmac` and no `VerifiedContact` is created.
- **Given** the feature, **when** `ruff check` and `pytest` run, **then** lint/type errors are 0 and relevant tests pass.

_FR-89 · AD-42 · AD-44_

---

### Story 21.20: Extend Multi-Source Lead Gen Adapters `[done]`

As a sales rep or real estate broker in Vietnam,
I want `multi_source_lead_gen` to also cover the sources it currently advertises but does not yet wire (`muaban_bds`, `vn_jobs`/`VietnamWorks`, `Mua Sắm Công` / `muasamcong`),
So that the prompt, routing, capability description, and adapter registry stay consistent and those sources are searchable through the same natural-language tool.

**Acceptance Criteria:**

- **Given** a BĐS-related chat prompt, **when** `multi_source_lead_gen` runs, **then** `MuabanBdsLeadAdapter` is dispatched alongside `batdongsan` and `chotot`, calls `scrape_muaban_bds`, and returns `RawLeadRecord`s with `degraded` handling consistent with 21.19.
- **Given** a recruitment-related chat prompt, **when** `multi_source_lead_gen` runs, **then** `VnJobsLeadAdapter` calls `aggregate_jobs(..., ctx=None)` to fetch across TopCV/ITviec/VietnamWorks without self-persisting, and `VietnamWorksLeadAdapter` is dispatched only when the query explicitly mentions "vietnamworks".
- **Given** a public-procurement-related chat prompt, **when** `multi_source_lead_gen` runs, **then** `MuaSamCongLeadAdapter` calls `MuasamcongScraper.search_tenders()` and returns company/tender leads.
- **Given** the new adapters are registered, **when** `LeadSourceAdapterRegistry.resolve_adapters_for_intent(query)` is called, **then** it returns the right adapters and avoids duplicate calls across `vn_jobs`/`vietnamworks`/`job_market`.
- **Given** the feature, **when** `ruff check` and `pytest` run, **then** lint/type errors are 0 and relevant tests pass.

_FR-85 · FR-43 · FR-44 · FR-45 · FR-46 · AD-42_

---

### Story 21.21: Deterministic Confidence Gate & Selective Micro-LLM Fallback Worker `[ready-for-dev]`

As a sales rep or lead researcher,
I want scraped lead records to be automatically classified by schema completeness and only the truly incomplete records to be selectively enriched by a lightweight micro-LLM,
So that lead data completeness reaches ≥98% while keeping LLM token cost near $0 and maintaining sub-second deterministic parsing speed.

**Acceptance Criteria:**

- **Given** raw records processed by Pass 1 deterministic parsers (`parsers.py` / `normalize_lead()`), **When** schema completeness is evaluated after normalization, **Then** each record receives a `schema_completeness_score` based on the ratio of required fields successfully matched (Phone, Price, Address District, Area, Title):
  - `schema_completeness_score >= 0.85`: Record goes directly to Data Plane (Deduplication → Scoring → Persistence) with **0 LLM calls**.
  - `0.70 <= schema_completeness_score < 0.85`: Record goes to Data Plane but is marked `needs_enrichment = True` for non-blocking async batch enrichment.
  - `schema_completeness_score < 0.70` OR missing critical required fields (Phone, Price, or District-level Address): Record is enqueued to `MicroExtractionWorker`.
- **Given** an enqueued low-confidence record, **When** `MicroExtractionWorker` processes it, **Then** it isolates ONLY the ambiguous text snippet using Anchor Sliding-Window regex (`lh`, `sđt`, `alo`, `zalo`, `không`, `chín`...) capped at **≤ 250 characters (≤ 200 input tokens)**, supports dynamic micro-batching (5–10 snippets/call) with `asyncio.Semaphore(20)`, and routes to Tier 1 Model (Google Gemini Flash Free / Local Qwen via `HybridLLMRouter` per AD-103).
- **Given** the Micro-LLM returns an extraction result, **When** the result is received, **Then** the extracted values (phone digits, numeric price, district) are **re-validated** against Pass 1 Regex/Schema rules (E.164 phone format, 1900/1800 suppression, positive price). Validated fields are merged **ONLY into missing (`None`) fields** without overwriting valid Pass 1 fields; LLM output failing re-validation is discarded.
- **Given** extracted contact information, **When** persisted, **Then** raw phone numbers are immediately encrypted via AES-256 (`VerifiedContactEncryption`), blind `phone_hmac` is generated for deduplication, and database update executes via atomic `COALESCE` SQL to ensure zero-locking and immediate Zero-cache WAL synchronization (`zero.nowing.net`).
- **Given** a batch of 100 scraped records from any adapter (Batdongsan, Chotot, Muaban, TopCV, ITviec), **When** end-to-end extraction completes, **Then** ≥85% of records bypass LLM entirely (confidence ≥ 0.85 after Pass 1), and total LLM token spend across the batch is **< 4,000 tokens** (avg < 40 tokens per micro-extraction call).
- **Given** `MicroExtractionWorker` encounters a Tier 1 model timeout (>2.0s per call, >3.5s per batch) or HTTP 429 rate limit, **When** the circuit breaker trips, **Then** it gracefully degrades: the record is persisted with its original low confidence score and `needs_enrichment = True`, no error is raised, and the worker continues processing remaining records.
- **Given** the feature is deployed, **When** regression tests in `tests/unit/lead_intelligence/` run against a 100-record Golden Dataset (covering Vietnamese word numbers, homoglyphs, and false-positive traps like "không thương lượng"), **Then** Phone F1 score improves from baseline ~85% to ≥95% without regression on records that were already passing Pass 1.
- **And** the existing `LeadGenOrchestrator` and `EntityDeduplicationService` interfaces remain unchanged — `MicroExtractionWorker` operates as a post-normalization enrichment step that feeds back into the existing pipeline.

_FR-85 · AD-103 · AD-119 (Rules 1-3, 6) · Decree 13/2023 Compliance_

---

### Story 26.25: Customer Location Profile Selector with Progressive Disclosure `[ready-for-dev]`

As a sales rep or broker in Vietnam,
I want to specify where my target customers live, work, and transact using a structured province/district/ward selector that starts simple and expands only when I need more detail,
So that lead searches match the right geography without overwhelming me with too many fields up front.

**Acceptance Criteria:**
- **Given** the Playbook Builder reaches the location step, **When** the user opens it, **Then** a `LocationSelector` component is displayed with a required Province/Thành phố combobox, an optional Quận/Huyện multi-select that appears after a province is selected, and an optional Phường/Xã multi-select collapsed behind a "Khu vực chi tiết (nâng cao)" toggle.
- **Given** the location type row, **When** the user sees it, **Then** the default is "both" (residence + transaction) and the user can switch to "customer_residence", "customer_work", or "transaction".
- **Given** a smart-search text box, **When** the user types a ward, district, province, or common alias ("HCM", "Saigon", "Hà Nội", "Ha Noi"), **Then** the system normalizes Unicode and diacritics, suggests matching GSO/TCTK codes, and tags the selected location as chips.
- **Given** quick-location chips ("Hà Nội", "TP.HCM", "Đà Nẵng", "Hải Phòng", "Cần Thơ"), **When** the user clicks one, **Then** the corresponding province code is selected and nearby districts are optionally suggested.
- **Given** a selected province, **When** the user opens the district dropdown, **Then** it lists only districts belonging to that province; when a district is selected, the ward dropdown lists only wards belonging to that district.
- **Given** the user selects multiple districts or wards, **When** the selection is saved, **Then** the UI displays compact chips with remove buttons and `location_text` is updated for the final summary.
- **Given** no province selected, **When** the user tries to proceed, **Then** the form shows a validation error and prevents advancing.

_FR-69.2 · FR-85 · AD-31 · UX-Origami-Split-Canvas_

---

### Story 26.26: Location-Aware Adapter Routing & Coverage Quality `[ready-for-dev]`

As a lead generation orchestrator,
I want the system to prefer and rank adapters that actually cover the selected provinces, districts, and wards,
So that scraping budget is spent on sources that are most likely to return relevant local leads.

**Acceptance Criteria:**
- **Given** a `LeadSourceAdapter` implementation, **When** it is registered, **Then** it may declare `supported_provinces: list[str]` and `coverage_quality_by_location: dict[str, float | str]` (province/district code → quality enum or score).
- **Given** a campaign with a `LocationProfile`, **When** `resolve_adapters_for_campaign()` runs, **Then** the system first resolves adapters by intent/keyword/category as today, then re-orders the result using a composite score: `location_coverage_score * 0.4 + vertical_relevance_score * 0.4 + cost_efficiency_score * 0.2`.
- **Given** two adapters in the same category, **When** one has `coverage_quality_by_location` >= "medium" for the target province and the other has "low" or none, **Then** the higher-coverage adapter gets a larger budget share and higher execution priority.
- **Given** no location match, **When** all adapters are otherwise available, **Then** the system falls back to keyword-based routing and surfaces a warning in the plan summary.
- **Given** the orchestrator filters leads, **When** `pre_filter_by_icp()` runs with a `LocationProfile`, **Then** it tokenizes and normalizes the lead's `city`, `address`, `title`, and `content_snippet`, matches province/district/ward codes against the location name trie with Unicode normalization and diacritic stripping, and rejects leads that do not match.
- **Given** adversarial inputs (e.g. "Quận 1" vs "Quận 10-12", "Châu Thành" in multiple provinces, mixed NFD/NFC), **When** the matcher runs, **Then** it uses word-boundary token matching and hierarchical precedence (ward → district → province) to avoid false positives.
- **Given** a lead matches the target location, **When** fit scoring runs, **Then** `location_weight` (default 0.3) is applied to blend the location match (0–100) with the existing `fit_score`.

_FR-69.2 · FR-69.3 · FR-85 · AD-31 · AD-42 · NFR-1_

---

### Story 26.27: Pre-Flight Lead Plan Summary & PlanSummaryCard `[ready-for-dev]`

As a sales rep,
I want to review a concise plan summary (sources, locations, intent, product, channels, estimated lead count, estimated cost) before the system starts scraping,
So that I can adjust inputs without wasting credits on a poorly targeted run.

**Acceptance Criteria:**
- **Given** a completed playbook wizard, **When** the user reaches the final step, **Then** a `PlanSummaryCard` is rendered inside the playbook dialog and a mirror of the card is available in the Right-Canvas (Origami split-view) for persistent review.
- **Given** the plan summary, **When** it is displayed, **Then** it shows: selected preset, intent, product, `LocationProfile` summary, active channels, target sources, estimated reachable lead count, and estimated credit cost.
- **Given** each source in the plan, **When** the user expands its coverage badge, **Then** the card displays `supported_provinces`, `coverage_quality_by_location` for the selected locations (high/medium/low/none), and any `degraded` reason.
- **Given** a source with insufficient coverage for the selected location, **When** the plan is rendered, **Then** the card shows a warning and suggests a broader province or nearby alternative.
- **Given** the smoke-test button, **When** clicked, **Then** the plan runs with `limit=5`, updates the card with actual reachable and cost numbers, and switches the CTA to "Chạy đầy đủ" or "Chỉnh sửa kế hoạch".
- **Given** the plan summary, **When** the user clicks "Quay lại", **Then** they can edit any previous step without losing selections; when they click "Chạy chiến dịch", **Then** the multi-source lead orchestrator starts the full run.

_FR-69.4 · FR-85 · FR-86 · AD-31 · UX-Origami-Split-Canvas_

---

### Story 26.28: Source Coverage Badge in Right-Canvas `[ready-for-dev]`

As a sales rep actively monitoring a lead discovery run,
I want to see source status and coverage context inside the Right-Canvas instead of a separate page,
So that I can keep the chat/table in focus while checking why a source is slow, degraded, or missing from the plan.

**Acceptance Criteria:**
- **Given** a playbook run or active multi-source search, **When** the Right-Canvas is open, **Then** it renders a `SourceStatusPanel` showing each source's `last_execution_status`, `coverage_quality_by_location` for the current `LocationProfile`, and toggle to enable/disable the source for this run.
- **Given** a source in the panel, **When** its coverage for the selected location is "high", "medium", "low", or "none", **Then** the badge uses the corresponding color and tooltip text, and the panel explains what the rating means.
- **Given** a degraded source, **When** the user expands it, **Then** the panel shows the reason (rate-limited, proxy down, anti-bot, location unsupported) and the last successful/failed heartbeat time.
- **Given** a source is toggled off, **When** the user runs the playbook, **Then** the orchestrator excludes that source for this run only and updates the plan summary in real time.
- **Given** the user is not in an active run, **When** they open Right-Canvas, **Then** the panel shows the global source health dashboard from cached `capability status` data without requiring a new run.

_FR-69.4 · FR-86 · AD-31 · AD-42 · UX-Origami-Split-Canvas_

---

### Story 26.29: Smoke Test Feedback Loop for Location Refinement `[ready-for-dev]`

As a sales rep,
I want a 5-lead smoke test that previews real results and lets me refine the location profile before committing a full run,
So that I can correct location mismatches early and avoid paying for irrelevant leads.

**Acceptance Criteria:**
- **Given** a playbook plan summary, **When** the user clicks "Chạy thử 5 lead", **Then** the orchestrator runs a low-cost preview, returns up to 5 leads, and renders a compact `NowingLeadMatrix` preview with location, source, and content snippet.
- **Given** the smoke test results, **When** the user is asked "Địa điểm có đúng không?", **Then** they can choose "Đúng — chạy đầy đủ", "Thu hẹp khu vực", "Mở rộng khu vực", "Đổi nguồn", or "Chỉnh vị trí chi tiết".
- **Given** the user chooses to refine the location, **When** the location step reopens, **Then** the previous `LocationProfile` is pre-filled and the user can add/remove province, district, or ward selections.
- **Given** a refined location, **When** the user re-runs smoke test, **Then** the new 5-lead preview reflects the updated profile and a diff summary highlights what changed (added/removed locations, source order, estimated cost).
- **Given** the user approves after smoke test, **When** they click "Chạy đầy đủ", **Then** the full run uses the final `LocationProfile` and the smoke-test leads are included in the final results with deduplication.
- **Given** the smoke test returns 0 leads, **When** the panel renders, **Then** it explains why (no source coverage, too narrow, source degraded) and suggests next actions.

_FR-69.4 · FR-85 · AD-31 · UX-Origami-Split-Canvas_

---

---

## Epic 22: Telegram Scraper & Channel Ingestion Engine `ready-for-dev`

> **Epic Goal:** Cung cấp giải pháp trích xuất dữ liệu đa nguồn từ Telegram (kênh công khai, nhóm thảo luận, bài đăng, bình luận, media), tự động phân tích thực thể (SĐT, giá BĐS, email), bảo vệ tài khoản chống khóa (Anti-ban/FloodWait), tích hợp thông báo tức thời (Alert Engine) và cung cấp công cụ tra cứu cho AI Agent.

**Status:** `[ready-for-dev]`
**Governed by Architecture Spine:** `_bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md` (AD-1 to AD-8).
**UX Contract (đã lưu trữ):** `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-telegram-scraper-engine.md` (U1 to U7). UX chuẩn hiện tại: `ux-designs/ux-Nowing-2026-08-15/`.

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

**Given** Telegram messages containing lead contacts,
**When** queried by `LeadGenOrchestrator` (Story 21.15),
**Then** `TelegramLeadAdapter` implements `LeadSourceAdapter` (AD-44), converting message entities and contacts into standard `Lead` records streamed directly into the Split-View Table Matrix.

---

## Epic 23: Lead Capture, Real-Time Enrichment & Automated Outreach `done`
*Governed by Architecture Spine: `architecture-epic23-lead-infrastructure.md`*
*Reviewed & Ratified: 2026-08-16 by Winston (Arch), Mary (BA), Sally (UX), Amelia (Dev), Murat (QA)*

### Architectural Invariants (INV-23.1 – INV-23.11)
- **INV-23.1 (Worker Queue Isolation):** Scraper tasks BẮT BUỘC route vào Celery queue riêng biệt `nowing.lead_scrapers` với priority thấp hơn chat/gateway queue.
- **INV-23.2 (Bounded Redis Streams):** Mọi lệnh đẩy vào stream BẮT BUỘC dùng approximate cap: `XADD stream_key MAXLEN ~ 10000`. Redis chỉ đóng vai trò transit buffer.
- **INV-23.3 (Circuit Breaker Persistence):** Trạng thái Circuit Breaker per-platform BẮT BUỘC lưu trữ trên Redis với key `circuit_breaker:scraper:{platform}` có TTL 10 phút.
- **INV-23.4 (Composite Partition Key):** Bảng `leads` và các bảng quan hệ BẮT BUỘC định nghĩa Primary Key bao gồm `workspace_id`: `PRIMARY KEY (id, workspace_id)`.
- **INV-23.5 (Zero-Cache Partition CDC Replication):** PostgreSQL Logical Publication cho Zero-cache BẮT BUỘC phải bật cờ `ALTER PUBLICATION zero_publication SET (publish_via_partition_root = true);`.
- **INV-23.6 (Fail-Closed RLS Enforcement):** Mọi query tương tác với `leads` BẮT BUỘC phải thiết lập `SET LOCAL app.current_workspace_id = :ws_id` và bật `FORCE ROW LEVEL SECURITY`.
- **INV-23.7 (Payout Mutual Exclusion & Row Lock):** Mọi bước chuyển trạng thái của `PartnerPayout` BẮT BUỘC phải acquire Database Row Lock (`SELECT ... FOR UPDATE`).
- **INV-23.8 (Reconciliation-Before-Retry):** Khi gặp timeout khi gọi Napas/VietQR Gateway, worker TUYỆT ĐỐI KHÔNG retry chuyển tiền mà BẮT BUỘC phải gọi API tra cứu trạng thái giao dịch trước.
- **INV-23.9 (Cryptographic Audit Signatures):** Mọi payout hoàn tất BẮT BUỘC lưu trữ chữ ký HMAC-SHA256 gồm `(payout_id + partner_id + amount_micros + tx_reference + timestamp)` vào trường `audit_signature`.
- **INV-23.10 (Constant-Time HMAC Webhook Verification):** Webhook Zalo OA và VietQR Gateway BẮT BUỘC xác thực bằng `hmac.compare_digest()`, kiểm tra `timestamp` không lệch quá 300 giây.
- **INV-23.11 (Async Webhook ACK < 500ms):** Webhook endpoint chỉ làm nhiệm vụ verify chữ ký, validate payload schema, đẩy event vào Celery/Redis queue và trả về HTTP 200 trong < 100ms.

---

### Story 23.1: Asynchronous Scraper Worker Pool (Celery + Redis Streams)
- **User Value:** Lead scraping across 15+ Vietnamese platforms runs asynchronously in parallel Celery workers without blocking chat SSE responses, streaming individual leads to the browser matrix via Zero-cache / Redis pub-sub as they are found.
- **Key Deliverables:**
  - `LeadScraperWorker`: Celery tasks on dedicated queue `nowing.lead_scrapers` with per-platform rate limiters (Leaky bucket in Lua) and circuit breaker.
  - Redis Stream channel `workspace:{id}:leads_stream` with dual flush triggers (Batch size >= 5 OR Time window >= 3s).
  - Zero-cache reactive ingestion into PostgreSQL with `ON CONFLICT (workspace_id, value_hmac) DO UPDATE`.
  - Frontend Hardware-Accelerated Cell Pulse Shimmer animation (`.streamed-lead-row-entering`).
- **Acceptance Criteria:**
  - **Given** a lead generation prompt requiring multi-source scraping (Batdongsan, Chợ Tốt, TopCV, Masothue),  
    **When** `LeadGenOrchestrator` dispatches scraping tasks,  
    **Then** Celery returns a `job_id` within 100ms and executes workers concurrently across independent worker pools.
  - **Given** active scraping workers discovering leads in real time,  
    **When** any individual worker extracts 5+ leads OR when 3 seconds elapse with buffered leads,  
    **Then** it pushes records directly to Redis Stream `workspace:{id}:leads_stream`, triggering Zero-cache WAL mutation and CSS cell pulse animations in the frontend table without waiting for full job completion.
  - **Given** a scraper encountering Cloudflare anti-bot challenge or HTTP 429 rate limit,  
    **When** consecutive failures reach 3,  
    **Then** the circuit breaker trips for that specific adapter for 10 minutes, logging the incident to `AntiBotEscalation` while remaining adapters continue execution uninterrupted.
  - **Given** a worker process experiencing an unexpected crash (`SIGKILL`/OOM),  
    **When** Celery retries the task (`acks_late=True`),  
    **Then** `ON CONFLICT (workspace_id, value_hmac) DO UPDATE` ensures zero duplicate rows are created in the database.

### Story 23.2: Official Zalo OA Webhook & ZNS Template Automation Hub
- **User Value:** Integrate official Zalo OpenAPI v3 Webhooks and ZNS (Zalo Notification Service) templates, allowing automated verification, instant template messaging, and two-way chat logging directly in Nowing.
- **Compliance Gates:**
  - **Nghị định 91/2020/NĐ-CP (Anti-Spam):** ZNS chỉ dùng cho giao dịch/CSKH (Verified Opt-in Leads). Khung giờ gửi tin bị chặn nghiêm ngặt trong khoảng **08:00 – 21:30**.
  - **National DNC Check:** Mọi số điện thoại gửi đi phải được kiểm tra qua blacklist và DNC.
- **Key Deliverables:**
  - Backend Webhook endpoint `/api/v1/workspaces/{id}/gateways/zalo/webhook` đọc raw body bytes và xác thực `hmac.compare_digest`.
  - Fast ACK (< 100ms) enqueuing payload to `zalo_inbox_events`.
  - Split-Pane ZNS Template Modal with dynamic variable mapping (`{customer_name}`, `{property_name}`, `{price}`) and live mobile preview.
  - Two-way conversation sync: Prospect reply (`user_send_text`) updates `Lead.status = 'responded'`.
- **Acceptance Criteria:**
  - **Given** an incoming webhook POST from Zalo Official Account server,  
    **When** validated against the workspace app secret using HMAC-SHA256 with timestamp delta <= 300s,  
    **Then** the event is enqueued into `zalo_inbox_events` and acknowledged with `HTTP 200 OK` in < 100ms.
  - **Given** a verified lead with an unlocked Vietnamese mobile number within the valid sending window (08:00–21:30),  
    **When** a user clicks `⚡ Send ZNS`,  
    **Then** Nowing opens the Split-Pane Modal with pre-filled variables, live preview, dispatches via Zalo OpenAPI v3, and records the delivery receipt in `outbound_messages`.
  - **Given** a prospect responding to an outbound Zalo message,  
    **When** Zalo OA fires the `user_send_text` webhook event within the 48h active conversation window,  
    **Then** the lead record status updates to `responded`, and an in-app notification alerts the workspace owner with the prospect's reply.

### Story 23.3: Automated VietQR Affiliate Payout Reconciliation
- **User Value:** Affiliate partners and agencies receive instantaneous, automated 24/7 bank payouts via VietQR / Napas API as soon as payout requests are approved.
- **Compliance & Financial Invariants:**
  - **Double-Entry Ledger Integrity:** Tách `available_balance` và `hold_balance`. Chỉ ghi nhận `total_paid_micros` khi có xác nhận thành công từ cổng thanh toán.
  - **Thuế TNCN (TT 111/2013/TT-BTC):** Tự động tính và khấu trừ 10% thuế TNCN cho các giao dịch rút tiền > 2.000.000 VNĐ.
- **Key Deliverables:**
  - Payout reconciliation service (`nowing_backend/app/services/payout_reconciliation_service.py`) với Row Lock `SELECT ... FOR UPDATE`.
  - Webhook listener `/api/v1/partners/payouts/webhook` với HMAC-SHA256 verification.
  - Celery Beat task `reconcile_pending_payouts` chạy định kỳ 2 phút xử lý giao dịch treo (`processing`).
- **Acceptance Criteria:**
  - **Given** an approved affiliate payout request with valid Napas 24/7 bank account details,  
    **When** admin or automated policy triggers payout execution,  
    **Then** the database locks the row, moves funds to `hold_balance`, calls the gateway API with an idempotent `tx_reference`, and transitions state to `processing`.
  - **Given** a webhook callback confirming bank transfer success,  
    **When** signature and checksum match the gateway secret key,  
    **Then** `hold_balance` is deducted, `total_paid_micros` is credited, `PartnerPayout.status` becomes `completed`, and an automated email receipt with the Napas transaction ID and cryptographic HMAC audit signature is dispatched.
  - **Given** a transient network failure or timeout (Two-Generals problem),  
    **When** the reconciliation background worker runs,  
    **Then** it queries the gateway transaction status API (`GET /transactions/{tx_ref}`) before attempting any retry, preventing duplicate bank payouts.

### Story 23.4: PostgreSQL Row-Level Security (RLS) & Table Partitioning for Multi-Million Lead Scale
- **User Value:** High-performance database infrastructure capable of handling millions of scraped leads across multi-tenant workspaces with sub-10ms query latency and strict tenant isolation.
- **Key Deliverables:**
  - Alembic migration `217_partition_leads_table_zero_downtime.py`: 5-phase zero-downtime shadow table pattern with 16 hash partition shards (`leads_p0` .. `leads_p15`) and fallback `leads_default`.
  - Composite Primary Key `(id, workspace_id)` on `leads` and composite FKs on child tables (`lead_scores`, `verified_contacts`, `zalo_message_logs`).
  - Zero-cache publication configured with `publish_via_partition_root = true`.
  - PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`) with session context `app.current_workspace_id`.
- **Acceptance Criteria:**
  - **Given** a database connection with tenant session variable set to `app.current_workspace_id = '1'`,  
    **When** executing `SELECT * FROM leads`,  
    **Then** PostgreSQL engine-level RLS strictly filters out rows belonging to any other `workspace_id`, even in raw SQL queries.
  - **Given** a partitioned `leads` table containing over 5,000,000 lead records,  
    **When** executing workspace-scoped filter and search queries,  
    **Then** `EXPLAIN ANALYZE` confirms partition pruning eliminates unneeded partitions, maintaining p95 query response time under 15ms.
  - **Given** an active production database,  
    **When** applying partition migration,  
    **Then** shadow table creation, dual-write triggers, and batched backfill migrate records with zero table locking and zero downtime.

---

---

## Epic 24: Enterprise Lead Conversion, Automated Multi-Channel Outreach & Team CRM Ecosystem
*Governed by Strategic Product Plan: 2026-08-16 by Mary (BA), Winston (Arch), Sally (UX), Amelia (Dev), Murat (QA)*

### Architectural Invariants (INV-24.1 – INV-24.8)
- **INV-24.1 (Stateful Cadence Scheduler & Quiet Hours Deferral):** Multi-channel outbound drip steps BẮT BUỘC lưu trạng thái execution step trong bảng `campaign_steps` và schedule qua Celery Beat / Redis delayed sets. Khung giờ gửi tin tuân thủ nghiêm ngặt **08:00 – 21:30 (Asia/Ho_Chi_Minh)**; các tin nhắn đến hạn ngoài khung giờ BẮT BUỘC tự động lùi `eta` thực thi sang `08:05` sáng hôm sau kèm Jitter & Leaky Bucket rate limiting.
- **INV-24.2 (Opt-Out, DNC & ZNS Template Compliance):** Mọi tin nhắn gửi đi BẮT BUỘC kiểm tra trạng thái Unsubscribe, `workspace_dnc_records` và `global_dnc_records` (Fail-closed). Với Zalo ZNS, BẮT BUỘC sử dụng `zns_template_id` đã được VNG duyệt; tin nhắn chat tự do chỉ gửi trong cửa sổ 24h tương tác chủ động từ prospect. Khi nhận phản hồi "STOP"/"HUY", chiến dịch tự động hủy ngay lập tức.
- **INV-24.3 (Waterfall Phone & Tax Code Isolation):** API tra cứu MST (masothue, dangkykinhdoanh) và Phone Waterfall BẮT BUỘC có caching Redis (TTL 7 ngày cho MST, 24h cho Phone), Circuit Breaker (`circuit_breaker:scraper:masothue`) và Proxy Rotation.
- **INV-24.4 (Team Credit Pooling & Atomic Quota Locks):** Thành viên trong Workspace dùng chung `Workspace.credit_micros_balance` với Row-level Locking (`SELECT ... FOR UPDATE`), hỗ trợ cấu hình Spend Cap cho từng User qua Atomic SQL Query trên `workspace_memberships.monthly_spent_micros`.
- **INV-24.5 (Clipper Extension Isolated Token Architecture):** Chrome Extension (Manifest V3) giao tiếp với Nowing qua Personal Access Token (PAT) có scope `leads:clipper:write`. Content Script TUYỆT ĐỐI KHÔNG lưu PAT; mọi API request BẮT BUỘC chuyển tiếp qua Background Service Worker để tránh vi phạm CSP và ngăn ngừa rò rỉ token.
- **INV-24.6 (Template Sandbox & AST Security):** Vertical Playbooks BẮT BUỘC khai báo JSON Schema đầu vào (`inputs_schema`), có giới hạn cứng `max_leads_per_run` (mặc định <= 200), và được validate trước khi khởi chạy. Community Playbooks phải qua kiểm duyệt `is_approved = True` trước khi xuất hiện trên Marketplace.
- **INV-24.7 (Inbound Auto-Reply Grounding & Async ACK SLA):** Webhook Zalo/Telegram BẮT BUỘC trả về `HTTP 200 OK` trong `< 100ms` và đẩy payload vào Redis Queue. AI Auto-Reply Bot chạy bất đồng bộ với `temperature = 0.0`, RAG Embedding Cosine Threshold `>= 0.75`, tuyệt đối từ chối tự ý cam kết giá/chiết khấu/hợp đồng ngoài tài liệu tham chiếu.
- **INV-24.8 (Human Escalation Handover & Auto-Reply Pause):** Khi phát hiện ý định mua hàng (Buying Signals) hoặc khi Sales Rep nhắn tin thủ công/nhận tư vấn, bot tự động tạm dừng (`auto_reply_paused`) 24 giờ cho cuộc hội thoại đó và bắn thông báo khẩn qua Telegram Bot.

---

### Story 24.1: Multi-Channel Drip Outreach Campaign Engine (Sequence Backend — Email-first MVP) `[done]`
- **User Value:** Sales teams and researchers can define automated multi-step outreach Sequences (Email in MVP; Zalo ZNS and Telegram reserved behind feature gates) with conditional delays, quiet-hour compliance, and real-time opt-out/reply handling.
- **Acceptance Criteria:**
  - **Given** an active lead list in Nowing Workspace,  
    **When** a user creates a new Sequence,  
    **Then** the UI provides a visual cadence editor to configure `send_email`, `wait`, and `condition` steps; the `email` channel is active and `zalo`/`telegram` are deferred with feature-gate messaging.
  - **Given** a scheduled step due outside 08:00 – 21:30 (Asia/Ho_Chi_Minh),  
    **When** `SequencerService.calculate_step_eta()` evaluates the step,  
    **Then** it defers execution to `08:05 + uniform(0, 1800)` seconds next morning.
  - **Given** an active enrollment and an inbound opt-out keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`) or reply,  
    **When** the inbound event arrives,  
    **Then** `SequencerService.handle_inbound_interruption()` acquires a Redis lock, performs an OCC version update, writes a `WorkspaceDncRecord` if opt-out, and halts future steps.
  - **Given** an existing sequence,  
    **When** the analytics view loads,  
    **Then** the backend returns `SequenceAnalyticsResponse` with `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, `failed_count`, `total_cost_micros`.

---

### Story 24.2: Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine `[ready-for-dev]`
- **User Value:** Automatically enrich scraped leads with verified phone numbers, Zalo registration status, and corporate legal entity details (Tax Code / MST, charter capital, legal representative, operating status) to maximize lead quality.
- **Acceptance Criteria:**
  - **Given** raw lead records with business names or addresses,  
    **When** enrichment is triggered,  
    **Then** `CorporateVerificationService` queries official business registries / masothue API with proxy rotation and Redis caching (TTL 7d), attaching MST, founding date, legal rep, and active status.
  - **Given** phone numbers discovered (including legacy 11-digit numbers converted to 2018 10-digit prefixes),  
    **When** the 3-tier Waterfall executes (Listing Phone ➔ Zalo UID Check ➔ Masothue Rep Phone),  
    **Then** it verifies carrier format, eliminates invalid/disposable numbers, and cross-checks with `workspace_dnc_records` and `global_dnc_records` (Fail-closed).
  - **Given** enriched data,  
    **When** saved,  
    **Then** Zero-cache updates the Table Matrix with verified badges (Green Check for MST & Zalo active).

---

### Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling `[ready-for-dev]`
- **User Value:** Enable agencies and sales teams to collaborate in real-time on a shared Kanban pipeline, assign leads via Round-robin, track conversation history, and share a central workspace credit wallet with granular per-member caps.
- **Acceptance Criteria:**
  - **Given** `/dashboard/[workspace_id]/leads/pipeline`,  
    **When** loaded,  
    **Then** it renders a reactive Kanban board with stages: `New Lead`, `Contacted`, `Qualified`, `Won`, `Lost`, with drag-and-drop column movement synced via Zero-cache and protected by Optimistic Concurrency Control (`version` column).
  - **Given** new batch of leads imported from scrapers or chat,  
    **When** auto-assignment is enabled,  
    **Then** `LeadAssignmentService` distributes leads evenly across active team members (`is_accepting_leads=True` and `current_leads < capacity`) using Round-Robin logic.
  - **Given** workspace billing,  
    **When** team members initiate scraping or AI enrichment,  
    **Then** costs debit from `workspaces.credit_micros_balance` with Two-Phase Reservation and atomic check against `workspace_memberships.monthly_spend_cap_micros`.

---

### Story 24.4: Nowing Lead Clipper — Chrome Extension for 1-Click Lead Capturing `[ready-for-dev]`
- **User Value:** Sales reps and sourcers browsing Facebook Groups, LinkedIn, Batdongsan.com.vn, or TopCV can capture leads, posts, and contact information directly into their Nowing Workspace table with 1 click.
- **Acceptance Criteria:**
  - **Given** the Nowing Chrome Extension (Manifest V3) installed and authenticated with `leads:clipper:write` scoped PAT,  
    **When** browsing a supported platform (Facebook Group post, Batdongsan listing, TopCV candidate/company),  
    **Then** Content Script injects a non-intrusive floating `⚡ Clip to Nowing` button and sends parsed DOM to Background Service Worker.
  - **Given** the user clicks `Clip to Nowing`,  
    **When** Background Service Worker dispatches REST payload to `POST /api/v1/workspaces/{id}/leads/clip`,  
    **Then** backend enforces deduplication hash `SHA256(workspace_id + source_url + phone)`, streams the new row into the active Nowing table within 500ms, and queues offline if disconnected.

---

### Story 24.5: Vertical Playbook Marketplace & Community Workflow Templates `[ready-for-dev]`
- **User Value:** Users can browse, install, and execute pre-built 1-click workflows tailored to specific industries (Real Estate Brokerage, IT Headhunting, B2B SaaS Sales, E-Commerce Price Monitoring).
- **Acceptance Criteria:**
  - **Given** `/dashboard/[workspace_id]/playbooks/marketplace`,  
    **When** viewed,  
    **Then** it displays categorized cards (Bất Động Sản, Tuyển Dụng Nhân Sự, B2B Sales, E-Commerce) with verified tags, run counts, estimated credit cost preview, and `max_leads_per_run <= 200` safety caps.
  - **Given** a user selects a playbook (e.g. *"Săn nhà phố ngộp giá & tự động gửi Zalo môi giới"*),  
    **When** clicking `Install & Run`,  
    **Then** it generates a schema-driven input modal from `inputs_schema`, collects parameters (Khu vực, Ngân sách), and initiates the multi-step orchestrator pipeline.

---

### Story 24.6: Two-Way AI Outreach Auto-Reply Agent `[ready-for-dev]`
- **User Value:** Automated AI Agent that listens to incoming prospect replies on Zalo OA and Telegram, intelligently answers inquiries based on the workspace's uploaded documents/FAQ, and escalates hot leads to human sales reps.
- **Acceptance Criteria:**
  - **Given** an incoming message from an outreach prospect via Zalo OA or Telegram Bot,  
    **When** received,  
    **Then** Webhook returns `HTTP 200 OK` in < 100ms, aggregates rapid-fire messages via Redis Debounce Buffer (3s window), and triggers asynchronous RAG grounding with Cosine Similarity `>= 0.75` and `temperature = 0.0`.
  - **Given** prospect intent indicating strong buying signal (e.g. *"Báo giá cho tôi"*, *"Hẹn xem nhà"*) or asking ungrounded pricing terms,  

---

### Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence) `[backlog]`
- **User Value:** Sales teams and researchers can define automated multi-step outreach cadences across Zalo ZNS, Telegram Bot, and Email with AI-personalized copy, conditional delays (e.g. "Wait 2 days for reply"), and automated status transitions.
- **Acceptance Criteria:**
  - **Given** an active lead list in Nowing Workspace,  
    **When** a user creates a new Drip Campaign,  
    **Then** the UI provides a visual cadence editor to configure Step 1 (Approved Zalo ZNS Template / Telegram Bot), Step 2 (Conditional Wait 48h if no reply), and Step 3 (Follow-up Email or Sale task creation).
  - **Given** campaign execution within 08:00 – 21:30 (Asia/Ho_Chi_Minh),  
    **When** dispatching each step,  
    **Then** `DripCampaignSchedulerService` dynamically maps pre-approved template variables, defers execution to 08:05 next morning if scheduled during quiet hours, and attempts fallback channels on permanent delivery errors.
  - **Given** a prospect responding to any step or sending an opt-out keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`),  
    **When** the inbound webhook event arrives,  
    **Then** Redis distributed lock `campaign:lock:enrollment:{id}` and `SELECT FOR UPDATE` prevent race conditions, transition the campaign state to `responded` / `unsubscribed`, and halt further automated follow-up steps.

---

## Epic 25: Platform Administration & Multi-Tenant Operations
*Governed by Strategic Architecture & Operations Plan: 2026-08-16 by Winston (Arch), John (PM), Sally (UX), Murat (QA)*

### Architectural Invariants (INV-25.1 – INV-25.8)
- **INV-25.1 (Scoped Short-Lived Impersonation JWT & Privilege Stripping):** Phiên làm việc Impersonation ("Login as User") BẮT BUỘC sinh `impersonation_token` riêng biệt có TTL tối đa 15 phút, chứa claims `impersonated_by: <admin_uuid>`, `target_user: <user_uuid>`, `is_impersonation: true`. Backend Middleware BẮT BUỘC tước bỏ cờ `is_superuser` trong session này và chặn đứng (HTTP 403) mọi API thay đổi mật khẩu, đổi email, xóa tài khoản, xem/sửa API keys, hoặc nested impersonation.
- **INV-25.2 (Dual-Principal Audit Integrity - PDPD Decree 13):** Mọi request thực hiện trong phiên Impersonation hoặc thao tác của Admin trên dữ liệu người dùng BẮT BUỘC ghi log append-only vào `audit_events` với đầy đủ: `actor_id` (Admin thật), `subject_id` (User bị mạo danh), `impersonation_session_id`, `action`, `endpoint`, `origin_ip`, `user_agent`.
- **INV-25.3 (2-Tier Lock & Double-Entry Ledger for Credit Adjustments):** Mọi thao tác cộng/trừ credit thủ công BẮT BUỘC yêu cầu `Idempotency-Key` trên header, sử dụng Redis Redlock (`lock:workspace_wallet:{id}`) kết hợp Postgres `SELECT FOR UPDATE` trên bảng `workspace_wallets`, ghi nhận vào `credit_transactions` append-only kèm trường `reason` bắt buộc và `ticket_reference`.
- **INV-25.4 (Affiliate Anti-Fraud Graph Detection & Napas Name Matching):** Duyệt yêu cầu rút tiền hoa hồng 15% BẮT BUỘC chạy qua Anti-Fraud Engine (quét trùng Device Fingerprint, dải IP, phát hiện Self-referral rings qua Recursive CTE) và xác thực 100% khớp tên chủ tài khoản thụ hưởng từ cổng Napas 24/7 trước khi cho phép 1-Click Payout.
- **INV-25.5 (Realtime Telemetry & Gross Margin Monitoring):** Thu thập số lượng token và chi phí API thực tế (OpenAI, Anthropic, Google, DeepSeek) đối soát với doanh thu nạp tiền thời gian thực (`gross_margin = (revenue - cogs) / revenue`), phát hiện ngay lập tức các tài khoản lạm dụng hoặc tính năng bị âm lợi nhuận gộp.
- **INV-25.6 (Dynamic Scraper Rule Invalidation via Redis Pub/Sub):** Cập nhật CSS Selectors / Delays trực tiếp trên UI được lưu versioned trong Postgres `JSONB` và publish qua kênh Redis Pub/Sub `scraper_config_updated`. Celery workers tự động refresh local in-memory cache mà không cần restart pod; tự động fallback về version trước đó nếu error rate vượt ngưỡng 20%.
- **INV-25.7 (ReDoS Sandbox Hard Limit & Schema AST Validation):** Mọi Regex hoặc CSS Selector do admin cấu hình BẮT BUỘC chạy qua `cssselect.parse` và ReDoS Sandbox Benchmark với hard limit **50ms** (sử dụng engine `google-re2`). Vượt quá 50ms lập tức trả về `422 Unprocessable Entity`.
- **INV-25.8 (Fail-Closed Superadmin Guard & PAT Rejection):** 100% các endpoint `/admin/*` BẮT BUỘC có guard `require_superuser` (kiểm tra `User.is_superuser == True`). Toàn bộ Personal Access Tokens (PAT) bị từ chối tuyệt đối (Fail-Closed) ở tầng `require_session_context`.

---

### Story 25.1: Multi-Tenant User & Workspace Hub + Scoped Impersonation `[ready-for-dev]`
- **User Value:** Superadmin can search, view 360° user/workspace activity, suspend/ban fraudulent accounts, and securely impersonate users in 1-click to triage customer support issues without credential sharing.
- **Acceptance Criteria:**
  - **Given** `/admin/users` and `/admin/workspaces`,  
    **When** loaded by a verified Superadmin interactive session,  
    **Then** it renders high-density data tables (36px row height, monospace IDs/emails) with full-text search, plan badge, credit balance, and action buttons (`Ban`, `Suspend`, `Impersonate`).
  - **Given** a customer support ticket,  
    **When** admin clicks `⚡ Impersonate User`,  
    **Then** backend issues a scoped short-lived JWT (TTL 15m), redirects to the user's workspace, renders a persistent 40px sticky amber hazard banner at `z-[9999]` with remaining time and `1-Click Exit (Esc)`, plus a 4px amber viewport border.
  - **Given** an active impersonation session,  
    **When** attempting to access `/admin/*` routes or modifying account security settings (change password, delete account),  
    **Then** backend privilege stripping middleware rejects with `HTTP 403 Forbidden` and logs the violation.

---

### Story 25.2: Manual Credit Adjustment & Refund Desk with Dual-Audit Ledger `[ready-for-dev]`
- **User Value:** Superadmin can credit or debit tokens/credits to any workspace for customer support compensation, bank transfer top-ups, or partner promotions with strict operational guardrails and immutable audit logs.
- **Acceptance Criteria:**
  - **Given** `/admin/workspaces/{id}/credits`,  
    **When** submitting a manual credit adjustment form,  
    **Then** form enforces mandatory fields: `amount_credits`, `direction (CREDIT/DEBIT)`, `reason (min 10 chars)`, and `ticket_ref (Zendesk/Jira URL)`.
  - **Given** concurrent submission or rapid double-click on the adjustment button,  
    **When** processed by the backend,  
    **Then** Redis Redlock and Postgres `SELECT FOR UPDATE` on `workspace_wallets` ensure exactly one ledger row is inserted into `credit_transactions` and the wallet balance updates atomically.
  - **Given** non-manager support staff,  
    **When** attempting to grant credits exceeding their role limit (e.g. > $10/day),  
    **Then** backend blocks with `HTTP 403 QuotaExceeded` requiring Tier-2 Manager approval.

---

### Story 25.3: Affiliate Partner Payout Desk & Anti-Fraud Engine `[ready-for-dev]`
- **User Value:** Superadmin can audit affiliate partner payout requests, view automated fraud risk scores (IP/Device clusters, self-referral rings), and execute 1-click 24/7 bank payouts via VietQR / Napas API.
- **Acceptance Criteria:**
  - **Given** `/admin/affiliates/payouts`,  
    **When** viewed,  
    **Then** it displays pending payout requests with Fraud Risk Score Pills (`🟢 Low (0-29)`, `🟡 Mid (30-69)`, `🔴 High (70-100)`), bank name match indicator (`100% Match` vs `Name Mismatch`), and tax deduction calculation (10% PIT for > 2M VND).
  - **Given** an affiliate detected with matching device fingerprint or IP subnet with their referred accounts,  
    **When** risk engine evaluates,  
    **Then** the record flags `🔴 High Risk: Self-Referral Ring Detected` and disables 1-click quick approval.
  - **Given** an approved valid payout request,  
    **When** admin clicks `⚡ Approve & Dispatch VietQR`,  
    **Then** backend executes idempotent Napas transfer, updates status to `completed`, stores cryptographic receipt, and sends confirmation email to partner.

---

### Story 25.4: Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry `[ready-for-dev]`
- **User Value:** Superadmin can monitor real-time AI infrastructure costs, gross margins per model/workspace, proxy pool availability, and Celery worker queue health with emergency controls.
- **Acceptance Criteria:**
  - **Given** `/admin/telemetry`,  
    **When** loaded,  
    **Then** it displays real-time aggregate LLM cost graphs (OpenAI, Anthropic, Google, DeepSeek), token consumption by workspace, and live gross margin tracking.
  - **Given** the Proxy Pool monitor,  
    **When** displayed,  
    **Then** it lists active SOCKS5/HTTP proxies with latency (ms), bandwidth (GB), and success rate (%), providing 1-click `Rotate Dead Proxies`.
  - **Given** Celery Worker & Queue section,  
    **When** tasks stall in Dead Letter Queue (DLQ),  
    **Then** it shows workload bars and provides a safe 2-second long-press `Purge Dead Tasks` action with breakdown.

---

### Story 25.5: Dynamic Scraper Rule Engine & ReDoS Sandbox `[ready-for-dev]`
- **User Value:** Superadmin can update CSS selectors, request delays, and retry policies for scrapers (Batdongsan, Chotot, TopCV, Muaban) live on the dashboard without redeploying backend code.
- **Acceptance Criteria:**
  - **Given** `/admin/scrapers/rules`,  
    **When** updating a platform's extraction schema or CSS selector,  
    **Then** backend validates syntax via `cssselect.parse` and runs a ReDoS Benchmark Sandbox (< 50ms limit with `google-re2`).
  - **Given** a valid rule update,  
    **When** saved to Postgres `JSONB`,  
    **Then** backend publishes a Redis Pub/Sub event `scraper_config_updated`, and active Celery workers refresh their local config cache in < 1s.
  - **Given** an emergency where a platform is blocking all IPs,  
    **When** admin toggles `Emergency Circuit Breaker: Trip`,  
    **Then** all workers immediately pause scraping on that target platform.

---

### Story 25.6: Security Audit Trail Logs & In-App Broadcast Announcements `[ready-for-dev]`
- **User Value:** Full compliance audit logging for PDPD Decree 13, global DNC blacklist management, and 1-click in-app banner announcements for system maintenance or promotional campaigns.
- **Acceptance Criteria:**
  - **Given** `/admin/audit-logs`,  
    **When** queried,  
    **Then** it provides an immutable timeline of all admin and impersonation actions with dual-principal tracking (`actor_id`, `subject_id`, IP, timestamp, diff payload).
  - **Given** the Global DNC Blacklist manager,  
    **When** admin adds a VIP phone number, domain, or tax code,  
    **Then** the entry synchronizes immediately to the global blacklist cache, suppressing all outbound scraping and messaging system-wide.
  - **Given** `/admin/broadcasts`,  
    **When** admin creates an announcement banner (Maintenance / Promo),  
    **Then** the banner mounts on top of `/dashboard/*` for targeted or all workspaces via Zero-cache realtime push.

---

## Epic 26: Autonomous Lead Missions & Deep Sales Research `in-progress`
*Governed by Architecture Spine: `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (AD-101 to AD-110) & BMAD Full-Spectrum Panel (Winston, John, Mary, Amelia, Murat, Sally, DevOps)*

> **UX Refinement (2026-08-20):** Epic 26 bổ sung story cải tiến UX cho `MissionControlWidget` (Glass Box) và `PhoneUnlockPill` / `SmartUnlockPopover` (Two-Tier Phone Unlock) dựa trên `ux-spec-epic26-mission-control-phone-unlock-2026-08-20.md` (UX-DR1–UX-DR12). Mục tiêu: mission minh bạch chi phí, tránh mất tiền oan, đảm bảo accessibility và analytics đầy đủ.
>
> **Stories 26.25–26.29 (Customer Location Profile & Pre-Flight Lead Plan):** được remap từ Epic 21.25–21.29 sau merge 2026-08-29. Các story này thuộc E26 vì liên quan Autonomous Lead Missions / Pre-Flight Plan / DSH Location Profile.

### Architectural Invariants (AD-101 – AD-110)
- **AD-101 (Stateless ChainLens & Unified pgvector Ingestion):** ChainLens chỉ đóng vai trò Crawler/Parser không lưu trạng thái. Chunks được đẩy về `POST /v1/chainlens/ingest` để Nowing tự tạo embeddings và lưu vào PostgreSQL 16 `chunks` (HNSW).
- **AD-102 (Decoupled Sidecar Worker & FastMCP Gateway):** Tác vụ chạy nền 1–8h nằm tại `dsh-worker`, giao tiếp qua Redis Streams (`nowing:dsh:tasks`), sử dụng `XAUTOCLAIM` và DLQ (`nowing:dsh:dlq`).
- **AD-103 (Hybrid LLM Inference Router with Circuit Breaker):** Local vLLM (`DeepSeek-R1-Distill-14B AWQ`, COGS $0) làm tầng 1, failover sang DeepSeek Cloud API khi quá tải queue > 8s, tự động strip `<think>` tags hoặc dùng Guided JSON.
- **AD-104 (Zero-Cache CDC Reactivity):** Toàn bộ cập nhật Lead Matrix và Mission State kích hoạt qua PostgreSQL Logical WAL Replication (`zero_publication`), loại trừ bảng `chunks` nặng.
- **AD-105 (PII Vault & Decree 13 Compliance):** Số điện thoại lưu trữ mã hóa AES-256-GCM, khử trùng lặp qua HMAC-SHA256, hiển thị Masked (`0908 *** 456`), ToS định vị Nowing là Data Processor.
- **AD-106 (Harness Hierarchical Delegation & Specialist Team Pattern):** Mission Supervisor phân việc cho Expert Pool (Research, Scraper, Valuation, PII Auditor) theo mô hình Producer-Reviewer.
- **AD-107 (Hermetic Testability & $0 API Cost Gate):** Toàn bộ CI/CD và evals (`nowing_evals`) chạy với Golden Streaming Cassettes (`.sse.jsonl`) và Fake FastMCP in-memory transport. F1 Phone $\ge 98.0\%$, Hallucination $\le 0.1\%$, MST Modulo 11 $\ge 99.5\%$.
- **AD-108 (Container Lifecycle, Zombie Guard & WAL Protection):** Dockerfiles bắt buộc có `tini` PID 1 và timeout context 60s. PostgreSQL cấu hình `max_slot_wal_keep_size = 4096MB`.
- **AD-109 (FastMCP Batch Ingestion & Concurrency Deadlock Prevention):** Gateway hỗ trợ `batch_ingest_leads` (50–100 items). Mọi bulk upsert SQL bắt buộc sắp xếp `ORDER BY value_hmac ASC`.
- **AD-110 (PII Opt-Out Blacklist, Anti-Fraud Refund & Two-Tier Unlock UX):** Bảng `pii_blacklists` (HMAC hash) xử lý quyền được quên; trần Auto-Refund tối đa 15% tổng lead/tháng; giao diện hỗ trợ Two-Tier Fast Unlock.

---

### Story 26.1: FastMCP Ingest Gateway, Batch Ingestion & Stateless ChainLens Pipeline `[done]`
- **User Value:** Nowing backend exposes high-throughput, deadlock-free FastMCP batch ingestion endpoints and an idempotent callback receiver for stateless ChainLens crawls to index chunks directly into Nowing PostgreSQL 16 pgvector.
- **Acceptance Criteria:**
  - **Given** `POST /mcp/v1/tools/batch_ingest_leads`,  
    **When** called by `dsh-worker` with a batch of up to 100 leads,  
    **Then** backend deterministically sorts items by `value_hmac ASC`, executes atomic bulk upsert into `leads` and `verified_contacts` (AES-256-GCM encrypted), and triggers `zero_publication` in < 200ms total.
  - **Given** `POST /v1/chainlens/ingest`,  
    **When** ChainLens streams completed crawl chunks with `UUIDv5` chunk IDs,  
    **Then** backend embeds text via `text-embedding-3-small` / local BGE, inserts into `chunks` with `ON CONFLICT (id) DO NOTHING`, and updates `chainlens_ingest_jobs` status.
  - **Given** a lead matching an existing HMAC hash in `pii_blacklists`,  
    **When** ingestion processes the record,  
    **Then** the contact details are suppressed with `is_blacklisted=True` and no credit unlock is allowed.

---

### Story 26.2: dsh-worker Sidecar Container, Redis Streams & Task Resumption `[done]`
- **User Value:** Autonomous long-running missions (1–8h) execute reliably in an isolated sidecar container without blocking FastAPI/Celery, with automatic task recovery from crashes via Redis `XAUTOCLAIM`.
- **Acceptance Criteria:**
  - **Given** `nowing-dsh-worker` container running with `tini` as PID 1,  
    **When** a mission is dispatched to `nowing:dsh:tasks`,  
    **Then** the worker consumes via `XREADGROUP`, manages hierarchical sub-task state, and acknowledges completion with `XACK`.
  - **Given** an unexpected worker crash mid-mission,  
    **When** a new worker instance starts,  
    **Then** `XAUTOCLAIM` retrieves pending tasks from PEL (min-idle-time > 60s), resumes execution from the latest checkpoint state, or routes to `nowing:dsh:dlq` after 3 failed attempts.

---

### Story 26.3: Multi-Tier Hybrid LLM Router (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8) `[done]`
- **User Value:** AI reasoning and extraction costs are minimized by prioritizing Google Gemini Flash (Free Tier, $0 COGS) and Local vLLM Qwen 3.8-27B ($0 COGS), bursting to DeepSeek-V4-Flash and DeepSeek-V4-Pro-0813 for deep reasoning with 100% Pydantic JSON schema compliance.
- **Acceptance Criteria:**
  - **Given** `HybridLLMRouter` receiving text extraction and tool dispatch tasks,  
    **When** within Google Gemini Flash Free Tier rate limits (15 RPM / 1M TPM),  
    **Then** requests route to Gemini Flash with structured output at **$0.00 Token COGS** in < 600ms TTFT.
  - **Given** offline local GPU environments,  
    **When** local vLLM (`Qwen 3.8-27B AWQ`) is active,  
    **Then** requests route to local vLLM with Outlines/Guided JSON decoding at **$0.00 Token COGS**.
  - **Given** complex multi-step valuation, distress deal inference, and reverse ICP scoring,  
    **When** deep reasoning is requested,  
    **Then** requests route to `DeepSeek-V4-Pro-0813` (with Thinking: High) at $0.435 In / $0.87 Out, or burst to `DeepSeek-V4-Flash` ($0.14/$0.28) upon rate limits.


---

### Story 26.4: PII Vault AES-256 Encryption, HMAC Deduplication & Decree 13 Opt-Out `[done]`
- **User Value:** Full compliance with Decree 13/2023/ND-CP with encrypted phone/email storage, blind HMAC deduplication, and automated opt-out suppression.
- **Acceptance Criteria:**
  - **Given** a new lead contact,  
    **When** saved in `verified_contacts`,  
    **Then** `phone_encrypted` and `email_encrypted` are secured via AES-256-GCM, and `value_hmac` is computed using server-side HMAC-SHA256 secret.
  - **Given** a data subject submitting a Right-to-be-Forgotten request,  
    **When** admin adds their phone HMAC to `pii_blacklists`,  
    **Then** all existing records are purged or anonymized, and future scrapers automatically drop matches.

---

### Story 26.5: Split Canvas Glass Box Mission Control, Two-Tier Phone Unlock & Shimmer Influx `[done]`
- **User Value:** Users can track live autonomous AI reasoning with a 4-stage stepper without feeling UI freeze, and unlock phone numbers smoothly with a 1-Click Fast Unlock session toggle.
- **Acceptance Criteria:**
  - **Given** an active mission in Split Canvas,  
    **When** viewed in the frontend,  
    **Then** the Glass Box Mission Control Widget displays a 4-stage progressive stepper (Crawl -> Reasoning -> Extraction -> Ingest) with live token velocity and collapsible CoT stream drawer.
  - **Given** masked phone pills (`0908 *** 456`),  
    **When** clicked for the first time,  
    **Then** a Smart Confirmation Popover renders with a session toggle `[x] 1-Click Fast Unlock`. Subsequent clicks unmask numbers immediately with a 150ms Number Flip animation and a 5s Undo Toast.

---

### Story 26.6: Telegram Interactive Checkpoint Bot & 1-Click Auto-Refund Dialog `[done]`
- **User Value:** Mobile sales reps receive 3-second glanceable lead cards on Telegram, make inline decisions with `editMessageText`, and trigger automated 24h refunds for invalid numbers with a 15% safety cap.
- **Acceptance Criteria:**
  - **Given** a high-fit lead detected during a mission,  
    **When** Telegram Bot notifies the user,  
    **Then** it renders a structured card with Inline Buttons (`[🔓 Mở khóa SĐT]`, `[🌐 Xem Dossier]`, `[❌ Bỏ qua]`).
  - **Given** the user clicks `[🔓 Mở khóa SĐT]`,  
    **When** processed,  
    **Then** the bot edits the existing message inline with unmasked SĐT and direct action buttons (`[📲 Gọi điện]`, `[💬 Zalo]`, `[🛡️ Báo số sai / Hoàn tiền]`).
  - **Given** a user reporting an invalid number within 24h,  
    **When** the workspace has <= 15% refund rate,  
    **Then** the system verifies via Zalo/HLR check and refunds 100% credits instantly.

---

### Story 26.7: Hermetic Quality Gates, Benchmark Suite & Anti-Zombie Chaos Testing `[done]`
- **User Value:** Automated CI/CD pipelines run at $0 API cost while enforcing strict data extraction accuracy and 0-zombie process guarantees.
- **Acceptance Criteria:**
  - **Given** `nowing_evals` executing the regression benchmark,  
    **When** run with `--mode=replay`,  
    **Then** all tests pass with $0 external token cost, enforcing F1 Phone $\ge 98.0\%$, Hallucination $\le 0.1\%$, and MST Modulo 11 $\ge 99.5\%$.
  - **Given** a 72-hour continuous scraping stress test on Dokploy,  
    **When** monitored via `ps aux`,  
    **Then** the container maintains exactly 0 defunct/zombie Chromium processes due to `tini` PID 1 and 60s hard context timeouts.

---

### Story 26.10: Mission Control Glass Box UX Refinement `[ready-for-dev]`
- **User Value:** Sales managers and SDRs can track the AI mission progress, understand costs, and download deliverables without confusion.
- **Acceptance Criteria:**
  - **Given** an active DSH mission,  
    **When** the Mission Control widget renders,  
    **Then** the title is `Trợ lý tìm lead` (not `DSH Mission Control`), the active mission query is shown as a subtitle, and the phase badge uses Vietnamese user-friendly labels (`Đang chạy`, `Hoàn thành`, `Lỗi`, `Đang trích xuất`).
  - **Given** a mission with `status === 'running'`,  
    **When** the progress bar is displayed,  
    **Then** it has a running animation (`animate-stripes` or `animate-pulse`) and shows the percentage label.
  - **Given** token velocity data is available,  
    **When** the token velocity panel renders,  
    **Then** it displays cost in both credits and dollar equivalent (e.g. `1.2 credits ≈ $0.0012`), and if budget data exists it shows a budget progress bar (`Đã dùng X% ngân sách tháng`) and estimated remaining credits.
  - **Given** the mission has completed and produced deliverables,  
    **When** the deliverables section renders,  
    **Then** each deliverable appears as a card with a file-type icon (`FileSpreadsheet`, `FileText`, `FileImage`), metadata (`sources · aspects · size`), an amber `Chứa PII` badge when `include_pii === true`, and a primary `Tải xuống` button.
  - **Given** a deliverable card with a valid download URL,  
    **When** the user clicks `Tải xuống`,  
    **Then** the browser downloads the file and a Sonner toast `Đã tải xuống {filename} ({size})` appears; on failure an error toast with retry guidance appears.
  - **Given** the mission has reasoning (CoT) subtasks,  
    **When** the widget loads,  
    **Then** the current subtask is expanded by default, past subtasks are collapsed, and each card shows title, status badge, tokens used, cost, and reasoning content (line-clamp-3 with expand).
  - **Given** the user tries to continue a research thread that does not exist,  
    **When** the system receives a 404,  
    **Then** it shows a clear `Research thread not found` error and does **not** create a thread implicitly.
- **UX-DRs covered:** UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR5, UX-DR11 (404), UX-DR12 (analytics).
- **FRs/NFRs covered:** FR-86, FR-85, FR-37, NFR-1, NFR-5.

---

### Story 26.11: Two-Tier Phone Unlock UX Refinement `[ready-for-dev]`
- **User Value:** Sales reps can unlock phone numbers with transparent cost, optional fast unlock, and a reliable undo option without accidental credit spend.
- **Acceptance Criteria:**
  - **Given** a masked phone pill,  
    **When** I click it for the first time,  
    **Then** a `SmartUnlockPopover` opens showing the masked preview and cost in both credits and dollar equivalent (e.g. `1.5 credits ≈ $0.0015`).
  - **Given** the unlock popover is open,  
    **When** I look at the `1-Click Fast Unlock` option,  
    **Then** it defaults to **unchecked**, clearly states a `15 phút` TTL, and shows helper text `Bỏ qua hộp thoại này trong 15 phút tới.`
  - **Given** I have enabled `1-Click Fast Unlock`,  
    **When** I click another masked phone pill within 15 minutes,  
    **Then** the pill unlocks immediately with a brief inline spinner, no popover appears, and the 15-minute TTL resets.
  - **Given** a fast unlock session is active,  
    **When** 15 minutes pass with no interaction, or I leave the leads view, or I log out,  
    **Then** the session expires and the next click reopens the confirmation popover.
  - **Given** I confirm a single phone unlock,  
    **When** the API succeeds,  
    **Then** the pill flips (150ms `rotateX` animation) to display the real number and a Sonner toast `Đã mở khóa SĐT -1.5 credits` appears with a `Hoàn tác` action that lasts **30 seconds**.
  - **Given** I confirm via fast unlock,  
    **When** the API succeeds,  
    **Then** the toast shows the same undo action but it lasts **10 seconds**.
  - **Given** the undo toast is visible,  
    **When** I click `Hoàn tác`,  
    **Then** the system calls `relockContact`, the pill flips back to the masked state, and a toast `Đã hoàn tác mở khóa +1.5 credits` appears.
  - **Given** a phone pill is already unlocked,  
    **When** I click it,  
    **Then** it copies the normalized phone number to the clipboard and briefly shows a `✓` copied state.
  - **Given** a phone pill is disabled (DNC, invalid, or missing `contact_id`),  
    **When** I hover or focus it,  
    **Then** it shows a `Ban` icon and a tooltip explaining why it cannot be unlocked, and the click is blocked.
  - **Given** I try to unlock with insufficient credits (402),  
    **When** the backend returns the error,  
    **Then** the popover content is replaced with `Không đủ credits. Nạp thêm để tiếp tục.` and a clear top-up link/button.
  - **Given** I try to unlock a phone blocked by DNC (403),  
    **When** the backend returns the error,  
    **Then** the popover shows `Số điện thoại bị chặn bởi DNC. Không thể mở khóa.` and disables the unlock action.
  - **Given** I select multiple leads and trigger bulk unlock,  
    **When** the bulk unlock popover opens,  
    **Then** it always shows, displays the total cost (`{count × 1.5} credits ≈ ${dollars}`), disables the fast unlock toggle, and has a single `Mở khóa SĐT hàng loạt` action.
  - **Given** the phone unlock flow is used with a screen reader or keyboard,  
    **When** navigating the popover or pill,  
    **Then** locked pills have `aria-label` stating the cost, unlocked pills state the phone and copy action, the popover is a focus trap with `Enter/Space/Tab/Esc` support, and color contrast meets ≥ 4.5:1.
  - **Given** the user has set `prefers-reduced-motion`,  
    **When** the pill flips or the popover appears,  
    **Then** animations are disabled or reduced.
  - **Given** an unlock or download event occurs,  
    **When** telemetry is enabled,  
    **Then** the frontend emits the analytics events defined in UX-DR12 (`phone_unlock.popover.open`, `phone_unlock.confirm`, `phone_unlock.fast.unlock`, `phone_unlock.undo`, `phone_unlock.error`).
- **UX-DRs covered:** UX-DR6, UX-DR7, UX-DR8, UX-DR9, UX-DR10, UX-DR11 (402/403), UX-DR12 (analytics).
- **FRs/NFRs covered:** FR-65, FR-86, NFR-2, NFR-5.

## Ghi chú
- **Mồ côi/defer có chủ đích:** OQ-1 (MCP marketplace), OQ-2 (agent-tool default enable/disable) → backlog.
- **RS-9** ("project memory" của team = `ResearchThread`?) → resolve trong scope 3.9/3.7.
- Story `[DONE]` không liệt kê AC (đã implement); chỉ story `[GAP]`/`(mới)` có AC để dev thực thi.
- **Epic 13 (DROPPED 2026-08-08):** Canonical entity storage / multi-domain indexing moved to `chainlens-research`. Nowing scrapers feed `chainlens-research` via `POST /v1/ingest/scraper` (Epic 20).
- **Epic 18 (2026-08-08 correct-course):** Public agent-chat API, Agent Registry, vertical `client_id` tenancy, cost attribution and rate limiting live in **Epic 18**. Governed by AD-29/AD-30/AD-31. Entry criteria: AD-29–31 accepted; PAT/RLS threat model reviewed.
- **Epic 22 (2026-08-15):** Telegram Scraper & Channel Ingestion Engine (Web Preview + MTProto StringSession Pool + Alert Engine + AI Agent Tools). Governed by Architecture Spine `architecture-telegram-scraper-2026-08-15`.
- **Epic 25 (2026-08-16):** Superadmin & Platform Operations Control Plane. Governed by BMAD Roundtable Architecture.
- **Epic 26 (2026-08-17):** Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure. Governed by Architecture Spine `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (AD-101 to AD-110).
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
| 6.11 Vertical Alert Rule Templates | Story 6.8 (Generic Alert Engine) | Consolidated alert templates for news, stock, company, price-drop, competitor |
| 6.12 Narrative Report Engine for Indexed Data | Story 6.8 (Generic Alert Engine) | Consolidated news digest, financial trend, company timeline |
| 12.6 Saved Searches | Story 6.8 (Generic Alert Engine) | saved-search `AlertRule` template |
| 12.9 Job Market Alerts | Story 6.8 (Generic Alert Engine), Story 12.6 | job-market `AlertRule` template on top of saved searches |
| 22.3 Telegram Alert & Agent Tools | Story 6.8 (Generic Alert Engine), Story 22.1, Story 22.2 | Realtime message matching triggers `AlertRule` & AI Agent tools |
| 9.5 Metered Deep-Research Endpoint (Self-Host) | Story 9.6 (Memory Provenance & Re-Validation) | 9.5 deferred; requires 9.6 provenance recipe + SCP approval before dev |
| 24.1 Drip Outreach Campaign Engine | Story 23.2 (Zalo Webhook/ZNS), Story 6.8 (Scheduler) | Scheduled cadence execution + ZNS template dispatch |
| 24.2 Waterfall Phone & MST Verification | Story 20.1 (`NowingIngestService`), Story 21.3 (Enriched Contact) | Multi-tier phone & corporate tax registry enrichment |
| 24.3 Multi-Seat Team CRM Pipeline | Story 23.4 (RLS & Partitioning), Story 8.12 (Workspace Limits) | Multi-seat tenant isolation & shared credit quota locks |
| 24.4 Nowing Lead Clipper Extension | Story 21.15 (Universal Lead Orchestrator) | Direct REST payload ingest to workspace leads table |
| 24.5 Vertical Playbook Marketplace | Story 6.6, Story 6.7 (Playbook Reuse & Schema UI) | Schema-driven dynamic modal input & pipeline orchestration |
| 24.6 Two-Way AI Outreach Auto-Reply | Epic 11 (Telegram Bot), Story 23.2 (Zalo Webhook) | Inbound message webhook processing & RAG-grounded auto-reply |
| 25.1 User/Workspace Hub & Impersonation | Story 8.11 (Global Models), Story 8.12 (Workspace Limits) | Multi-tenant user directory & scoped JWT session switching |
| 25.2 Manual Credit Adjustment Desk | Story 21.18 (Credit Wallet Ledger) | 2-tier lock atomic credit topup & audit ledger |
| 25.3 Affiliate Payout Approval Desk | Story 23.3 (Automated VietQR Payouts), Story 21.18 (Partners) | Anti-fraud graph scoring & 1-click Napas 24/7 bank transfer |
| 25.4 Cost & Queue Telemetry | Story 23.1 (Celery Scraper Pool), Story 8.11 (Pricing Registration) | Realtime aggregate token COGS & worker DLQ purge |
| 25.5 Dynamic Scraper Rule Engine | Story 23.1 (Scraper Worker Pool), Story 22.1 | Redis Pub/Sub live selector invalidation without restart |
| 25.6 Security Audit Logs & Broadcasts | Story 21.14 (DNC Registry), Story 23.4 (RLS Isolation) | Decree 13 PDPD immutable audit trail & in-app banner push |
| 26.1 FastMCP & Stateless Ingestion | Story 20.1 (`NowingIngestService`), AD-101, AD-109 | FastMCP batch lead ingestion & idempotent ChainLens callback |
| 26.2 dsh-worker Sidecar & Stream | Story 26.1, AD-102, AD-108 | Redis Streams autonomous worker loop with `XAUTOCLAIM` |
| 26.3 Hybrid LLM Router | Story 26.2, AD-103 | vLLM 14B AWQ local inference & Cloud fallback circuit breaker |
| 26.4 PII Vault & Opt-Out Blacklist | Story 26.1, AD-105, AD-110 | AES-256 encryption, HMAC blind index, Decree 13 compliance |
| 26.5 Glass Box Mission Control | Story 26.2, Story 26.4, AD-104, AD-110 | Split Canvas 4-stage stepper & Two-Tier Phone Unlock UX |
| 26.6 Telegram Checkpoint & Auto-Refund | Story 26.2, Story 26.4, Epic 11, AD-110 | Mobile glanceable card, `editMessageText` & 15% refund cap |
| 26.7 Hermetic Evals & Chaos Testing | Story 26.1 - 26.6, AD-107, AD-108 | $0 replay test suite, quality gates & 0-zombie verification |
| 26.9 Wide Research & Pro Excel | Epic 26, AD-112 | Client gọi Chainlens Wide Research + OpenPyXL Pro Formatter qua Daytona Sandbox |
| 24.8 Browser Operator & Takeover | Story 24.4, AD-111 | Capability `browser_operator.execute` qua Plasmo extension CDP bridge; authenticated tabs; `web_crawler` subagent prompt; live takeover với `requires_human`/`challenge` |
| 6.10 Mail Gateway & Scheduled 2.0 | Epic 6, Story 6.8, AD-115 | Webhook task@nowing.ai + Celery Beat Delta Analysis reporting |
| 3.18 Projects Workspace & Skills Hub | Epic 3, AD-1 | Projects Master Instructions context auto-inject + .skill.md modular hub |
| 27.1 Web App Builder & Design View | AD-113, AD-114 | Next.js generator + 1-click *.apps.nowing.net deploy + Mark Tool AST mutator |
| 27.2a Manus Slides Presentation Studio (Chat) | AD-112, AD-114 | PPTX/Marp chat-first generation, artifact panel, tool binding |
| 27.2b Speaker Diarization Meeting Minutes (Chat) | AD-112 | Chat-first audio diarization, action items, artifact panel |

> **Merge decision (2026-08-20):**
> - 14.3, 15.3, 16.3, 17.3, 17.4 merged into **Story 6.11 — Vertical Alert Rule Templates**.
> - 14.4, 15.4, 16.4 merged into **Story 6.12 — Narrative Report Engine for Indexed Data**.
> - Các section cũ giữ lại dưới dạng `[MERGED INTO ...]` để traceability.
> - 17.5 should reuse `ecommerce_products` + `ecommerce_price_history` tables and price-drop alert patterns built for Shopee (AD-EC-1..6).
> - 27.2 split into **27.2a PPTX/Marp chat-first presentation studio** and **27.2b speaker-diarization meeting minutes** (2026-08-24), both applying 27.1a chat-mode/tool-binding/artifact pattern.

---

### Mở rộng Epic 26: Story 26.9a — Wide Research Crawl Subgraph `[ready-for-dev]`
**Scope:** Tách phần "Wide Research" ra khỏi client độc lập, biến thành **LangGraph `crawl` subgraph** trong DSH mission (bổ sung cho `LangGraphMissionExecutor` của Story 26.8). Subgraph gọi `chainlens.research` với **`output=table` + `outputSchema`** (Direction A — sử dụng contract ChainLens đã có, không chờ `output=wide_research` query param), parse `ResearchOutput.structured_output` / `answer`, ghi `cost_micros` vào `checkpoint.cost_micros`, và lưu ma trận `sources` / `wide_research_matrix` vào `dsh_missions.checkpoint` JSONB để resumption. **Tận dụng code đã có:** `ChainLensServiceAuth` (`app/services/chainlens/auth.py`), `ResearchInput`/`ResearchOutput` (`app/capabilities/chainlens/research/schemas.py`), ChainLens research executor (`app/capabilities/chainlens/research/executor.py`), `DshRestClient` (`app/tasks/dsh_worker.py`), DSH mission routes (`app/routes/dsh_routes.py`), `LangGraphMissionExecutor` (`app/tasks/dsh_worker_langgraph.py`). **Code mới:** `app/tasks/dsh_worker_crawl_subgraph.py`, unit tests cassettes. Story 26.9a xong mới unblock 26.9b. Governed by `AD-102`, `AD-106`, `AD-107`, `AD-108`, `AD-112`.

### Mở rộng Epic 26: Story 26.9b — Pro Excel Formatter in Daytona Sandbox `[backlog]`
**Scope:** Nhận `checkpoint.wide_research_matrix` từ 26.9a, chạy Pro Excel Template Script trong **Daytona sandbox đã có sẵn** để xuất `.xlsx` đa tab. **Tận dụng code đã có:** Daytona sandbox lifecycle (`middleware/filesystem/sandbox.py`), `sandbox_routes.py`, pre-installed `pandas`/`numpy`/`openpyxl` (`execute_code/description.py`). **Code mới:** template `scripts/sandbox_pro_excel_template.py` và node `deliver` trong LangGraph (hoặc mở rộng `ingestion`). Governed by `AD-112`.

---

### Mở rộng Epic 24: Story 24.8 — Browser Operator CDP Tool for DSH Crawl + Human Live Takeover
**Scope:** 24.8 cung cấp một **capability `browser_operator.execute`** để agent điều khiển trình duyệt Chrome của user qua CDP thông qua Plasmo extension. Chi tiết:
- (a) `app/capabilities/browser_operator/` (`definition.py`, `schemas.py`, `executor.py`) đăng ký CDP tool với các action `navigate`, `click`, `fill`, `scroll`, `extract`, `take_screenshot`, `detect_challenge`.
- (b) `app/agents/chat/multi_agent_chat/subagents/builtins/web_crawler/system_prompt.md` hướng dẫn subagent gọi `browser_operator.execute` khi user yêu cầu điều khiển trình duyệt (`mở trang`, `click`, `scroll`, `screenshot`, etc.).
- (c) `GET /api/v1/dsh/cdp/stream` (SSE) và `POST /api/v1/dsh/cdp/result` (REST) kết nối backend với extension; kết quả chứa `requires_human`/`challenge` khi gặp CAPTCHA/2FA.
- (d) Chrome extension `background/cdp-bridge.ts` dùng `fetch` SSE reader, `chrome.debugger`, tìm/focus tab theo hostname, tạo tab mới nếu cần, tự động detect challenge signature, retry khi gửi kết quả.
- (e) UI Human Live Takeover trong `popup.tsx` cho phép user tạm dừng/resume khi gặp challenge (hiện tại lưu `activeMissionId` để popup render nút "Release Control"; dashboard popover vẫn là công việc mở rộng).
- (f) `app/tasks/dsh_worker_browser_operator.py` / `dsh_worker_langgraph.py` giữ nguyên làm DSH subgraph wrapper gọi capability.

**Tận dụng code đã có:** Plasmo framework (`@plasmohq/storage`, popup routing, `background/index.ts`), capability/tool registry (`app.capabilities`), Redis pubsub, `LangGraphMissionExecutor`. **Code mới:** `app/capabilities/browser_operator/`, SSE endpoint `cdp_stream`, REST endpoint `cdp_result`, challenge detection trong extension. WebSocket điều khiển thủ công bị loại bỏ. Có thể tách thành 24.8a (CDP capability + prompt-in-UI) và 24.8b (full mission pause/resume + dashboard takeover). Governed by `AD-111`.

---

### Mở rộng Epic 6: Story 6.10 — Inbound Mail Gateway (`task@nowing.ai`) & Stateful Scheduled Tasks 2.0
**Scope:** Thêm email adapter vào gateway framework và nâng cấp Celery scheduler thêm delta analysis. Với `LangGraphMissionExecutor` (26.8) đã có checkpoint/resumption qua `dsh_missions.checkpoint`, phần **Stateful Scheduled Tasks 2.0** nên được triển khai như một **DSH mission template** (`schedule_type=recurring_report`) thay vì snapshot storage + scheduler riêng. **Tận dụng code đã có:** Gateway webhook framework (`gateway_webhook_routes.py`), Celery Beat scheduler (`celery_app.py`), `LangGraphMissionExecutor` (`app/tasks/dsh_worker_langgraph.py`), `dsh_missions.checkpoint` JSONB. **Code mới:** (a) `app/gateway/email/adapter.py` tiếp nhận webhook SendGrid/Mailgun, parse attachment, enqueue DSH mission, reply SMTP, (b) `app/tasks/dsh_worker_scheduled_mission.py` enqueue recurring missions từ Celery Beat, (c) `ingestion` node viết snapshot vào checkpoint. Snapshot storage table riêng bị loại bỏ. Có thể tách thành 6.10a (Mail Gateway) và 6.10b (Scheduled DSH Mission). Governed by `AD-115`.

---


### Mở rộng Epic 6: Story 6.11 — Vertical Alert Rule Templates
**Scope:** Đăng ký sẵn các `AlertRule` template cho news (`new_items`), stock (`price_change`/`threshold_cross`), company (`threshold_cross`), e-commerce price-drop (`price_change`) và competitor tracking (`new_items`/`price_change`) trên nền **Generic Alert Engine** (Story 6.8). Mỗi template điền sẵn `capability_id`, `query`, `schedule`, `diff_strategy` và `notification_channels` để user bật cảnh báo trong một click mà không cần viết automation. Tận dụng `app/alerts/`, bảng `AlertRule`/`AlertSnapshot`/`AlertSubscription`, và các scraper/capability hiện có (`news.rss`, `cafef.scrape`, `vietstock.scrape`, `masothue.scrape`, `shopee.scrape`, `lazada.scrape` khi có). **Không xây scheduler hay notification path mới.** Với `LangGraphMissionExecutor` (26.8), `notification_channels` có thể thêm `dsh_mission` để alert trigger một DSH mission (ví dụ: tự động research khi có competitor news).

**Acceptance Criteria:**
- **Given** Generic Alert Engine đã có, **When** user bật template "News Alerts & Topic Monitoring", **Then** tạo `AlertRule` với `capability_id='news.rss'`, `diff_strategy='new_items'`, lịch daily mặc định.
- **Given** template "Stock Price Alerts", **When** bật, **Then** tạo `AlertRule` với `capability_id='vietstock.scrape'`/`cafef.scrape`, `diff_strategy='price_change'` hoặc `threshold_cross`.
- **Given** template "Company Alerts", **When** bật, **Then** tạo `AlertRule` với `capability_id='masothue.scrape'`, `diff_strategy='threshold_cross'` theo dõi thay đổi trạng thái/ngành/người đại diện.
- **Given** template "Price Drop Alerts", **When** bật, **Then** tạo `AlertRule` với `capability_id='shopee.scrape'`/`lazada.scrape`, `diff_strategy='price_change'`.
- **Given** template "Competitor Tracking", **When** bật, **Then** tạo `AlertRule` theo dõi `new_items` (biến thể mới, tồn kho) và `price_change` trên sản phẩm đối thủ.
- **Given** template cần capability chưa có (ví dụ `lazada.scrape`), **When** user bật, **Then** UI hiển thị `not_available` và không tạo rule lỗi.
- **Given** alert từ template kích hoạt, **When** user xem notification, **Then** có deep-link đến kết quả đã index trên `chainlens-research` và hiển thị old-vs-new / lý do trigger.

**Gộp từ:** Story 14.3, 15.3, 16.3, 17.3, 17.4.
**Governed by:** AD-33, AD-34, AD-35.

---

### Mở rộng Epic 6: Story 6.12 — Narrative Report Engine for Indexed Data
**Scope:** Re-scope thành **DSH mission deliverable** / `ingestion` node extension: truy vấn `chainlens-research` lấy dữ liệu đã index theo topic/công ty/sản phẩm, rồi prompt LLM tổng hợp thành narrative (digest, trend, timeline) và ghi vào `checkpoint.deliverables`. Tận dụng `generate_report` deliverable tool, `chainlens.research` capability, `LangGraphMissionExecutor` (26.8), và Generic Alert Engine scheduler để trigger DSH mission. Output: news digest, financial trend detection, company timeline. **Không viết scheduler hay synthesis code riêng cho từng vertical.** Sau 26.8, report engine nên chạy như một mission type `narrative_report` với `crawl` → `reasoning` → `extraction` → `ingestion` nodes.

**Acceptance Criteria:**
- **Given** các topic đang theo dõi, **When** schedule "News Digest" chạy, **Then** engine query `chainlens-research` cho mỗi topic, lấy articles đã index, prompt LLM sinh summary có cấu trúc kèm `sourceId` citations.
- **Given** công ty/cổ phiếu theo dõi, **When** schedule "Financial Trend" chạy, **Then** engine query historical financial `Chunk[]`, mô tả trend (revenue growth, margin change) với supporting data points và citations.
- **Given** một công ty, **When** request "Company Timeline", **Then** engine gọi `chainlens-research` timeline API (hoặc search với timeline filters) và render events theo trình tự thời gian với source badges.
- **Given** LLM synthesis fail hoặc dataset rỗng, **When** engine chạy, **Then** trả `degraded=true` với `degradation_reasons` và retry action.
- **Given** report được tạo, **When** user click citation, **Then** source mở trong chat với provenance drawer.

**Gộp từ:** Story 14.4, 15.4, 16.4.
**Governed by:** AD-34, AD-35.

---

### Mở rộng Epic 3: Story 3.18 — Projects Persistent Workspace & Modular Skills Hub
**Scope:** Thêm layer Project vào workspace hiện có và xây concept Skills Hub mới. **Tận dụng code đã có:** Workspace CRUD + RBAC (`workspaces_routes.py` — 619 dòng, roles, limits, MCP tool toggles), Prompt CRUD (`prompts_routes.py` — name, mode, content), Documents management (`documents_routes.py` — File/Note/Extension types), `LangGraphMissionExecutor` (`app/tasks/dsh_worker_langgraph.py`). **Code mới (gần toàn bộ):** (a) entity `Project` (DB migration + API) chứa Master Instructions + pinned documents, (b) auto-inject project context vào system prompt trước mỗi chat turn (middleware hook trong `new_chat_routes.py`), (c) document pinning field + API, (d) `.skill.md` parser và Modular Skills registry. **Kiến trúc mới:** Skills Hub có thể đăng ký skill như một **LangGraph subgraph** hoặc **DSH mission template**, cho phép agent sử dụng DSH mission làm một skill có thể gọi (ví dụ: "Research competitor X").

---

## Epic 27: Full-Stack Web App Builder, Instant Hosting & Creative Studio (2026-08-20) `[in-progress]` — 27.1a `done`, 27.1 parent/children `backlog`, 27.2a/27.2b `ready-for-dev`
**Epic goal:** Cung cấp trọn bộ công cụ sáng tạo và sản xuất phần mềm tự hành gồm Web Builder deploy `*.apps.nowing.net`, công cụ chỉnh sửa trực quan Design View (Mark Tool), studio soạn thảo slide thuyết trình PPTX/Marp, và pipeline bóc tách ghi âm cuộc họp thành Action Items.
**FRs:** FR-93 (Web App Builder & Instant Hosting), FR-94 (Design View Mark Tool & Presentation Studio).
**ADs:** AD-113, AD-114.

**Stories:**
- **27.1 Full-Stack Web App Builder, 1-Click Hosting `*.apps.nowing.net` & Design View Mark Tool** — `[in-progress]` parent/tracking story. Split 2026-08-24 because it bundled four subsystems. 27.1a `done`; 27.1b/c/d `in-progress` per `web-builder-27-1-status-audit-2026-08-25.md`.
  - **27.1a Web Builder Chat Mode MVP for Sales & Marketing** — `[done]` chat-first static publish (Option A).
  - **27.1b Web App Build & Preview Runner** — `[in-progress]` generation/validation/registry/cost done; missing real `npm install` + `next build`/preview runner.
  - **27.1c Web App Container Deploy & Custom CNAME** — `[in-progress]` static publish / host route / Dockerfile / custom-domain endpoint done; missing real Docker build/run and CNAME DNS validation.
  - **27.1d Web App Mark Tool & JSX AST Mutator** — `[in-progress]` UI/iframe postMessage/regex-based patch endpoint done; missing real AST parser.
- **27.2a Manus Slides Presentation Studio from Chat (PPTX/Marp)** — `[ready-for-dev]` chat-first deliverable theo pattern 27.1a. **Tận dụng code đã có:** Video presentation model/routes (`video_presentations_routes.py`), report/export flow (`reports_routes.py`), chat tool + artifact sidebar (`build_web_app` pattern). **Code mới:** `SlidePresentation` table, `PresentationStudioService` (`python-pptx` + Marp Markdown driver), `generate_presentation` LangChain tool, `PresentationToolUI` card, quick chip `/slides`, `PRESENTATION_STUDIO_ENABLED` gate.
- **27.2b Speaker Diarization Meeting Minutes from Chat** — `[ready-for-dev]` chat-first deliverable theo pattern 27.1a. **Tận dụng code đã có:** Whisper STT (`services/stt_service.py`), Circleback meeting notes webhook, chat tool + artifact sidebar. **Code mới:** `MeetingMinutes` table, `MeetingMinutesService` (diarization via `pyannote.audio`/`whisperx` + LLM action-item extraction), `generate_meeting_minutes` tool, `MeetingMinutesToolUI` card, quick chip `/meeting`, `MEETING_MINUTES_ENABLED` gate.



**Acceptance Criteria (đã phê duyệt 2026-08-20):**

**27.1 — Web App Builder:**
- **Given** người dùng mô tả web app bằng ngôn ngữ tự nhiên, **When** builder sinh code, **Then** một dự án Next.js + Tailwind được ghi vào `/workspace/web-app` và trả về preview URL.
- **Given** người dùng bấm `Publish`, **When** app vượt qua validation, **Then** nó được deploy lên `https://[app].apps.nowing.net` với chứng chỉ SSL hợp lệ.
- **Given** Mark Tool đang hoạt động, **When** người dùng bấm một phần tử trên trang, **Then** công cụ bắt bounding box selector và cập nhật JSX AST.

**27.2 — Slides & Meeting Minutes:**
- **Given** một prompt trình bày, **When** người dùng yêu cầu xuất PPTX, **Then** một file `.pptx` 16:9 được sinh ra với speaker notes và biểu đồ.
- **Given** một bản ghi cuộc họp, **When** người dùng yêu cầu diarization, **Then** output chứa action items theo từng người nói và tài liệu meeting minutes.
- **Given** STT service không nhận diện được giọng nói, **When** yêu cầu diarization, **Then** hệ thống trả về kết quả rỗng mà không crash pipeline.


> **Prerequisite definitions:**
> - **Story 20.1** = `NowingIngestService.to_chunks()` + `POST /v1/ingest/scraper` contract.
> - **Story 20.2** = gap-fill caller + cost allocation (Nowing side).
> - **Story 20.3** = `NowingPrivateProvider` for `POST /v1/private-data/search`.
> - **Story 20.4** = `ChainLensServiceAuth` + cost ledger sync.
> - **Story 6.8** = Generic Alert Engine in Epic 6 Automation infrastructure (scheduler + `RunService` + notification dispatch).

---

## Epic 28: Self-Host Trust, Data Portability & Cloud GA Legal Readiness `(mới 2026-08-21 từ PRFAQ)`

**Epic goal:** Người dùng self-host và cloud có thể tin tưởng Nowing với research memory dài hạn: dữ liệu có thể xuất, được mã hóa, quản lý bởi policy rõ ràng, và self-host chạy trong <10 phút.

**FRs:** FR-95 (Data export & portability), FR-96 (Encryption-at-rest & key management cho cloud), FR-97 (ToS/legal review + retention policy cho scrape data), FR-98 (Self-host OSS onboarding <10 min).

**ARs:** AR-11 (data export/portability), AR-12 (encryption-at-rest + key management), AR-13 (ToS/legal review + right-to-delete), AR-14 (self-host onboarding <10 phút).

**UX-DRs:** UX-DR-PRFAQ-2 (self-host onboarding flow).

**NFRs / NFR signals:** NFR-2 (Security), NFR-3 (Observability), RS-11 (legal/ToS + retention policy), RS-12 (encryption-at-rest), RS-13 (self-host onboarding / aha recall).

**Architectural invariants (INV-28.1 – INV-28.4):**
- **INV-28.1 (Cloud key hierarchy):** Cloud hỗ trợ managed key mặc định và BYOK (customer-managed key) tùy chọn; v1 encrypt `content`, PII trong `source_input`, và metadata `MemoryVersion`/`MemoryRelation` trước khi ghi disk; **defer** encrypt `embedding` cho đến khi có benchmark searchable encryption, vì `embedding` dùng HNSW/GIN search.
- **INV-28.2 (Right-to-delete without cascade):** Retention policy cho phép user xóa 1 memory cụ thể + versions + relations mà không xóa workspace hoặc research thread; mọi xóa phải có dry-run và ghi `audit_events`.
- **INV-28.3 (Self-host billing off by default):** Self-host install không yêu cầu Nowing Cloud API key để chạy core; deep-research engine gọi qua Cloud API key tùy chọn, local model có thể thay thế embedding/LLM.
- **INV-28.4 (Portability format stable):** Data export dùng OKF (đã có) làm canonical bundle; JSON/CSV là derived view; import-OKF là fast-follow để giảm lock-in fear.

**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory schema/provenance), Epic 8 (billing/cost/wallet), Epic 9 (self-host research path qua Nowing Cloud API). Không phụ thuộc Epic 4/7.

**Architecture Decisions:**
- `AD-28.1` — Encryption-at-Rest Strategy for Nowing Memory.
- `AD-28.2` — Data Export / OKF Bundle.
- `AD-28.3` — Retention & Right-to-Delete.
- `AD-28.4` — Self-Host OSS Onboarding.
- `AD-46` — Recall Precision / Noise Threshold Ratification (Story 3.18).

**Stories:**

### Story 28.1: Workspace Memory & Research Data Export `(mới 2026-08-21 từ PRFAQ)` `[backlog]`

As a workspace owner,
I want to export all workspace memory, research threads, and citations in JSON or CSV on top of OKF,
So that I can back up, migrate, or leave the platform without lock-in.

**Acceptance Criteria:**

**Given** a workspace with memories, research threads, and citations, **When** an owner requests a portable export, **Then** the backend produces a ZIP containing JSON/CSV files plus the canonical OKF bundle, and the export is scoped strictly to that workspace.

**Given** a workspace with no memories or documents, **When** an export is requested, **Then** it returns an empty but valid bundle with `item_count=0` instead of a 500 error.

**Given** the export contains memory with `source_run_id` or `source_uuid`, **When** the CSV is opened, **Then** provenance fields are preserved as stable identifiers so citations can be re-linked after import.

**Given** a large workspace with >10,000 memories, **When** the export runs, **Then** it streams in batches, enforces a file size limit per part, and does not OOM the worker.

**Given** a memory has a corrupted embedding or missing `content`, **When** the export reaches that row, **Then** it logs a `export_row_skipped` warning and continues, producing a valid bundle.

**And** the export redacts API keys, OAuth tokens, and embeddings if the user selects a human-readable format (CSV/JSON without vectors).

_FR-95 · AR-11 · RS-8 · INV-28.4 · AD-28.2._

### Story 28.2: Encryption-at-Rest for Cloud Memory `(mới 2026-08-21 từ PRFAQ)` `[backlog]`

As a cloud workspace user,
I want memory content, PII source input, and metadata encrypted at rest with a managed or customer-managed key,
So that my long-term research data is protected if the underlying storage is compromised.

**Acceptance Criteria:**

**Given** cloud deployment with `NOWING_ENCRYPTION_KEY_PROVIDER=managed|byok`, **When** a memory row is inserted or updated, **Then** `content`, sensitive `source_input`, `MemoryVersion.content`, and `MemoryRelation` soft-delete metadata are encrypted before being written to disk, not just protected by TLS.

**Given** `embedding` encryption is not enabled (v1), **When** a vector search runs, **Then** it uses the existing HNSW index on plaintext `embedding` with no additional latency, satisfying the performance gate.

**Given** the same cloud deployment, **When** a memory is read, **Then** the backend decrypts it transparently and returns plaintext to authorized callers; unauthorized tenants never see plaintext or raw ciphertext.

**Given** a feature flag `MEMORY_ENCRYPTION_V1` is OFF, **When** a memory is written, **Then** it is written as before, allowing staged rollout and rollback.

**Given** a BYOK key is rotated, **When** the rotation job runs, **Then** old ciphertext is re-encrypted with the new key without downtime, without exposing plaintext in logs, and row-level `key_id` metadata is updated.

**Given** a self-host deployment with `NOWING_ENCRYPTION_KEY_PROVIDER=none` (default), **When** memory is written, **Then** it remains plaintext unless the admin explicitly configures a local key, preserving OSS simplicity.

**And** encryption metadata (`key_id`, `algorithm`, `iv`) is stored per row so a single compromised key does not force a full database restore.

_FR-96 · AR-12 · RS-12 · NFR-2 · INV-28.1 · AD-28.1._

### Story 28.3: ToS / Legal Review & Retention Policy for Long-Term Scrape Data `(mới 2026-08-21 từ PRFAQ)` `[backlog]`

As a data protection officer / cloud user,
I want Nowing to have a documented ToS/legal review and a retention / right-to-delete policy for data kept in long-term memory,
So that the cloud GA is legally safe and users can remove infringing or outdated content.

**Acceptance Criteria:**

**Given** a list of scrape sources used by Nowing (Reddit, YouTube, TikTok, Amazon, Google Maps, etc.), **When** legal review is performed, **Then** a `_bmad-output/planning-artifacts/legal/tos-review-2026-08-21.md` document records: (a) which sources permit long-term storage, (b) which require attribution, (c) which prohibit reproduction, (d) recommended retention windows per source type, and (e) a **source risk tier** (low/medium/high) for cloud enablement decisions.

**Given** a high-risk source (e.g. TikTok with restrictive ToS), **When** cloud workspace owner browses settings, **Then** that source is disabled by default with an explicit legal warning and does not appear in auto-extract unless owner opts in.

**Given** the ToS review is approved, **When** an admin initiates a bulk deletion by `source_type` + `source_id`, **Then** the system runs a dry-run that lists affected `Memory` rows and total bytes, and only purges after explicit confirmation, with all actions logged to `audit_events`.

**Given** a workspace owner requests right-to-delete for a specific memory, **When** the erasure is confirmed, **Then** the memory, its versions, its relations, and its embedding are purged within the SLA, and an audit log entry is written to `audit_events`.

**Given** a bulk deletion of >100,000 memories, **When** the job runs, **Then** it is chunked into batches with progress reporting and can be cancelled without corrupting the index.

**Given** self-host vs cloud deployment, **When** the policy is published, **Then** it clearly states that self-host users retain responsibility for source compliance, while cloud Nowing acts as a processor with documented retention windows.

**And** the policy is linked from the public docs, signup flow, and workspace settings before cloud GA.

_FR-97 · AR-13 · RS-11 · INV-28.2 · AD-28.3. Legal review approved 2026-08-21; see `legal/tos-review-2026-08-21.md`._

### Story 28.4: Self-Host OSS Onboarding in Under 10 Minutes `(mới 2026-08-21 từ PRFAQ)` `[backlog]`

As a developer evaluating Nowing,
I want to self-host the open-core with `docker compose` and have a working workspace with local or remote LLM/embedding in under 10 minutes,
So that I can trust the product and try it without a cloud account.

**Acceptance Criteria:**

**Given** a fresh Linux, macOS, or Windows WSL2 machine with Docker installed, **When** the user runs `curl -fsSL .../install.sh | bash`, **Then** within 10 minutes Postgres, Redis, backend, frontend, and MCP server are healthy and the web UI is reachable at `http://localhost:3000`.

**Given** a host with existing Postgres/Redis on default ports, **When** the install script detects the conflict, **Then** it prompts for alternative ports and updates `.env` + `docker-compose` accordingly.

**Given** the install script runs, **When** the user has no OpenAI/Anthropic key, **Then** the script detects and offers a local embedding/LLM option (e.g. Ollama with `nomic-embed-text` + `llama3.1`) and sets `LOCAL_MODEL=true` so core memory features work offline.

**Given** a first-time user opens the web UI, **When** they create an account and ask the agent to remember a fact, **Then** `nowing_remember` writes to `Memory`, `nowing_recall` returns it, and the aha moment happens without cloud dependency.

**Given** the install environment has no internet, **When** the user pre-pulls the Ollama model image, **Then** the offline path still completes within 10 minutes after `install.sh` is available locally.

**Given** the user later wants cloud deep-research, **When** they add `NOWING_CLOUD_API_URL` + `NOWING_SELF_HOST_API_KEY`, **Then** self-host routes research through Nowing Cloud metered API and does not need an engine key.

**And** the README quick-start is rewritten to match the new install script and local-model path, and a CI smoke test runs the install on a fresh Ubuntu VM nightly.

_FR-98 · AR-14 · RS-13 · INV-28.3 · AD-28.4._

### Story 28.5: Workspace Memory Storage Cap & Retention Lifecycle `(mới 2026-08-23)` `[ready-for-dev]`

As a cloud workspace owner,
I want my workspace to enforce a memory count/storage cap and apply a retention lifecycle to old memories,
So that my workspace cannot grow unbounded, my costs are predictable, and I stay compliant with scraped-source ToS.

**Acceptance Criteria:**

**Given** a workspace is at or over its `max_memory_count` or `max_memory_bytes` limit, **When** any code path calls `MemoryRepository.create_memory`, **Then** the request is rejected with `403 limit_exceeded` before a new row is inserted.

**Given** a memory write matches an existing near-duplicate, **When** `MemoryRepository.create_memory` updates the existing row, **Then** the limit check does not reject the write because the count does not increase.

**Given** a workspace with no memory limit or a self-hosted deployment, **When** a memory is created, **Then** the write succeeds without a limit check.

**Given** the workspace owner configures `memory_retention_days`, `memory_auto_archive_enabled`, and `memory_retention_action` in settings, **When** the daily retention task runs, **Then** it archives (`Memory.archived_at = now()`) or hard-deletes old memories accordingly and excludes archived rows from all recall/search.

**And** `DELETE /workspaces/{id}/memories/{id}` hard-deletes a specific memory with audit; bulk deletion of >100,000 memories is chunked into 1,000-row batches with dry-run, progress reporting, and cancel-ability, with all actions logged to `audit_events`.

_Full implementation spec in `_bmad-output/implementation-artifacts/stories/28-5-workspace-memory-storage-cap-and-retention.md`._
_FR-97 (retention/right-to-delete) · NFR-1b/1c/1d (memory bound) · AD-18 · AR-13 · RS-11 · INV-28.2 · AD-DEFER-4 · AD-28.3._

### PRFAQ-Derived Requirements Coverage Map

| Requirement | Epic | Notes |
|---|---|---|
| **FR-95** Data export & portability | **Epic 28** | Export workspace memory/research threads/citations ra JSON/CSV trên OKF bundle (28.1). |
| **FR-96** Encryption-at-rest & key management (cloud) | **Epic 28** | Tiered encryption: content + PII/metadata v1, embedding v2 (28.2, AD-28.1). |
| **FR-97** ToS/legal review + retention policy | **Epic 28** | Review ToS nguồn scrape, source risk tier, right-to-delete workflow (28.3); cap/retention lifecycle implementation (28.5). |
| **FR-98** Self-host OSS onboarding <10 min | **Epic 28** | README + `docker compose` + local LLM/embedding config + install script (28.4). |
| **FR-99** Recall precision/noise gate | **Epic 3** | Chốt ngưỡng precision/noise trên `nowing_evals` trước khi scale (3.18). |
| **AR-11** Data export/portability | **Epic 28** | Same as FR-95. |
| **AR-12** Encryption-at-rest + key management | **Epic 28** | Same as FR-96. |
| **AR-13** ToS/legal review + right-to-delete | **Epic 28** | Same as FR-97. |
| **AR-14** Self-host onboarding <10 phút | **Epic 28** | Same as FR-98. |
| **AR-15** Refine recall precision gate | **Epic 3** | Same as FR-99. |
| **AR-17** SaaS admin operations console | **Epic 29** | Custom roles, subscription tier, bulk operations, health analytics, memory browser (29.1–29.6). |
| **AR-18** Auditability & traceability admin bulk op | **Epic 29** | Append-only `audit_events` cho mọi bulk op và tier change. |
| **UX-DR-PRFAQ-1** Memory browser / research timeline | **Epic 29** *(chính)* | UI cho analyst duyệt memory theo thread/source/confidence (29.5). |
| **UX-DR-PRFAQ-2** Self-host onboarding flow | **Epic 28** | Landing page + README hướng dẫn `docker compose` + MCP. |
| **UX-DR-PRFAQ-3** Memory correction / version history | **Epic 3** *(post-MVP)* | UI flag/update fact, xem version history & relations. |
| **UX-DR-PRFAQ-4** Cost control / auto-extract budget dashboard | **Epic 8** *(chính)* | Per-workspace budget toggle + cost/turn panel (8.14). |
| **UX-DR-PRFAQ-5** SaaS admin operations console | **Epic 29** | `/admin/saas` workspace directory, plan/tier, quota usage, health score, bulk action. |
| **UX-DR-PRFAQ-6** Analyst memory browser / research timeline | **Epic 29** | Filter memory theo thread/source/confidence/time, click-to-source, flag fact. |

---

## Epic 26 UX Refinement — Requirements Coverage Map

| Requirement | Epic / Story | Notes |
|---|---|---|
| `UX-DR1` Mission Control header clarity | **Epic 26** (Story 26.10) | Title, query display, Vietnamese phase badges. |
| `UX-DR2` Running progress bar animation | **Epic 26** (Story 26.10) | `animate-stripes`/`animate-pulse`. |
| `UX-DR3` Cost transparency (credits + $, budget %) | **Epic 26** (Story 26.10) | Token velocity panel + budget progress. |
| `UX-DR4` Deliverable card + PII safety + toast | **Epic 26** (Story 26.10) | Download prominence and safety UX. |
| `UX-DR5` CoT progressive disclosure | **Epic 26** (Story 26.10) | Expand current subtask by default. |
| `UX-DR6` SmartUnlockPopover cost & anti-accidental | **Epic 26** (Story 26.10) | Cost display, fast unlock 15m, bulk confirm. |
| `UX-DR7` Fast unlock session safety | **Epic 26** (Story 26.10) | TTL 15m, expire on leave/logout, inline spinner. |
| `UX-DR8` PhoneUnlockPill state distinction | **Epic 26** (Story 26.10) | Locked/unlocked/disabled visual states + copy. |
| `UX-DR9` Undo / relock affordance | **Epic 26** (Story 26.10) | 30s single / 10s fast undo toast. |
| `UX-DR10` Accessibility | **Epic 26** (Story 26.10) | aria-label, focus trap, keyboard, contrast, motion. |
| `UX-DR11` Error states (402/403/404) | **Epic 26** (Story 26.10) | Insufficient credits, DNC, missing thread. |
| `UX-DR12` Analytics instrumentation | **Epic 26** (Story 26.10) | Mission control + phone unlock events. |
| `FR-86` Split-View Canvas & Workspace Modernization | **Epic 26** | UX refinement builds on done Story 26.5. |
| `FR-65` Enriched Contact Data | **Epic 26** | Phone unlock flow, cost display, DNC. |
| `NFR-1` Performance bounds | **Epic 26** | Progress animation, token velocity display. |
| `NFR-2` Security & Auth | **Epic 26** | DNC block, PII badge, disabled state. |
| `NFR-5` Multi-tenancy | **Epic 26** | Workspace-scoped mission data, fast unlock session. |


---

## Epic 29: SaaS Operations, Advanced Admin Governance & Analyst Workspace (mới 2026-08-29)

**Epic goal:** Nowing nâng cấp từ single-tenant ops lên SaaS operations console: superadmin quản lý workspace/tenant, subscription tier/quota, bulk operations, audit; owner/admin/analyst có dashboard health/adoption và memory browser/research timeline.

**FRs:** FR-100 (Custom workspace roles & permissions builder), FR-101 (Workspace health & adoption analytics dashboard), FR-102 (Tenant subscription tier & quota management), FR-103 (Admin bulk operations console), FR-104 (Memory browser & research timeline for analyst).

**ARs:** AR-17 (SaaS admin operations console), AR-18 (Auditability & traceability admin bulk op).

**UX-DRs:** UX-DR-PRFAQ-5 (SaaS admin operations console), UX-DR-PRFAQ-6 (Analyst memory browser / research timeline).

**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory schema/provenance/versioning), Epic 8 (billing/cost/wallet), Epic 25 (admin platform operations baseline), Epic 28 (retention/right-to-delete cho 29.6).

### Architectural Invariants (INV-29.1 – INV-29.4)

- **INV-29.1 (Custom Role Boundary):** Vai trò custom trong workspace không thể vượt quyền của `Owner` (giá trị trần mặc định), không thể tự ý sửa/xóa `Owner`, không thể gán quyền `is_superuser` hay `billing_admin` cho bản thân khi không được phép.
- **INV-29.2 (Bulk Operation Idempotency):** Mọi admin bulk op (xóa, cấp/quỷ quyền, gán tier) bắt buộc gửi kèm `Idempotency-Key` do client sinh ra; backend lưu kết quả 24h, từ chối thực thi lại khi key đã tồn tại trừ khi request body khớp byte-by-byte.
- **INV-29.3 (Analyst Browser Isolation):** `MemoryBrowser` chỉ trả memory thuộc workspace mà analyst được gán; query bắt buộc áp dụng `workspace_id` RLS + row-level permission check trước khi lọc theo source/confidence/time.
- **INV-29.4 (Subscription Tier Reversibility):** Thay đổi tier (upgrade/downgrade) được ghi nhận nhưng có hiệu lực tối đa 7 ngày sau (hoặc ngay nếu owner xác nhận); downgrade gây ảnh hưởng hạ tầng được cảnh báo, rollback trong 7 ngày không mất dữ liệu nếu quota mới vẫn chứa được.

### Story 29.1: Custom Workspace Roles & Permissions Builder `[backlog]`

As a workspace Owner,
I want to define custom roles (e.g. Analyst, Editor, Billing Viewer) with a fine-grained permissions matrix,
So that I can delegate access without granting full admin or accidentally leaking sensitive operations.

**Acceptance Criteria:**

**Given** the Owner opens `/workspace-settings/roles`, **When** they click "New Role", **Then** they can name the role, choose a base template (`Viewer`, `Editor`, `Analyst`, `Billing`), and toggle individual permissions across categories: `memory_read`, `memory_write`, `memory_delete`, `source_configure`, `tool_enable`, `billing_read`, `billing_manage`, `member_invite`, `member_remove`, `analytics_read`, `settings_read`, `settings_write`.

**Given** a permission toggle that conflicts with the base template (e.g. `member_remove` on an Analyst template), **When** the Owner enables it, **Then** the UI shows a warning ("This exceeds the recommended template") but allows save if the Owner confirms.

**Given** a custom role is saved, **When** the backend receives `POST /workspaces/{id}/roles`, **Then** it validates that no permission exceeds the `Owner` ceiling (INV-29.1), persists the role to `workspace_roles`, and immediately invalidates the workspace permission cache.

**Given** a user is assigned a custom role, **When** they call any API or load any UI, **Then** the permission resolver merges system roles, custom role, and workspace-scoped overrides; `403` is returned for any disallowed action without leaking the existence of unauthorized resources.

**Given** migration 72 removed the `Admin` system role, **When** the role builder renders system roles, **Then** `Admin` is reserved and cannot be re-created as a custom role name; any legacy `Admin` assignment is mapped to the closest template (`Editor` + `billing_read`).

**And** the role builder supports clone, archive, and version history with `audit_events` per change.

_FR-100 · AR-17 · UX-DR-PRFAQ-5 · NFR-2 · NFR-5 · INV-29.1 · AD-RBAC-1._

### Story 29.2: Workspace Health & Adoption Analytics Dashboard `[backlog]`

As a workspace Owner or Admin,
I want a SaaS-style health dashboard showing adoption, memory growth, query volume, credit burn, and source coverage,
So that I can understand usage patterns, justify cost, and decide when to upgrade.

**Acceptance Criteria:**

**Given** the Owner opens `/dashboard/health`, **When** the page loads, **Then** it displays aggregate metrics: active members (daily/weekly), total memories, memory growth rate, `nowing_recall` / `nowing_remember` / `nowing_research` query volume, credits consumed, cost per turn, top sources, and source coverage gaps.

**Given** the dashboard has a time-range selector (7d/30d/90d/custom), **When** the user changes range, **Then** all charts and tables refresh in < 500ms from pre-aggregated materialized views (`workspace_health_daily`).

**Given** the user clicks a metric (e.g. "Top source: Reddit"), **When** the drill-down opens, **Then** it shows the underlying memory count, query count, and cost attribution for that source within the selected period, filtered by workspace RLS.

**Given** the workspace approaches its plan quota (memory count, credits, storage bytes), **When** the threshold exceeds 80%, **Then** the dashboard surfaces an upgrade CTA with the estimated tier needed, without blocking current usage.

**Given** the user has the `analytics_read` permission, **When** they access the dashboard, **Then** they see only data they are authorized to view; members with `memory_read` but not `analytics_read` see a reduced public snapshot.

**And** the dashboard is instrumented with analytics events and can be exported to CSV/JSON.

_FR-101 · AR-17 · UX-DR-PRFAQ-5 · NFR-1 · NFR-5 · INV-29.3._

### Story 29.3: Tenant Subscription Tier & Quota Management `[backlog]`

As a Superadmin,
I want to manage tenant workspaces by plan tier (Free / Team / Growth / Enterprise), trial status, quotas, and reversible upgrades/downgrades,
So that Nowing can operate as a multi-tenant SaaS with predictable unit economics.

**Acceptance Criteria:**

**Given** the Superadmin opens `/admin/saas/plans`, **When** the page loads, **Then** it lists all plan definitions with limits: `max_members`, `max_memory_count`, `max_memory_bytes`, `max_monthly_credits`, `max_sources`, `support_level`, `price_vnd`, and enabled/disabled flags.

**Given** a workspace is on the `Free` plan, **When** the Superadmin (or Owner via self-serve) upgrades to `Team`, **Then** the backend creates a `subscription_change` record, sets `effective_at` to now + 7 days by default (INV-29.4), and sends an email confirmation with quota delta and first charge.

**Given** the Owner requests an immediate downgrade from `Growth` to `Team`, **When** the current usage (memory count, members, credits) exceeds the new tier limits, **Then** the backend rejects with `409 conflict` and a checklist of what must be reduced; the change can be scheduled 7 days out with a remediation email.

**Given** a subscription change is within the 7-day reversible window, **When** the Owner or Superadmin clicks "Undo tier change", **Then** the tier reverts, no data is lost, and the reversal is logged to `audit_events` with `diff_payload`.

**Given** the trial period ends, **When** the cron job runs, **Then** it converts the workspace to `Free` if no payment method exists, suspends new writes if over `Free` quota, and notifies the Owner with a grace period of 72 hours.

**Given** the Superadmin edits a plan definition, **When** the change affects active workspaces, **Then** it only applies to new workspaces or workspaces that explicitly re-select the plan; existing workspaces keep grandfathered limits with a visible "legacy plan" badge.

**And** quota enforcement hooks into `MemoryRepository.create_memory`, member invite, and source enable; proration credits are calculated daily.

_FR-102 · AR-17 · AR-18 · UX-DR-PRFAQ-5 · NFR-1 · NFR-5 · INV-29.2 · INV-29.4 · AD-BILLING-1._

### Story 29.4: Admin Bulk Operations Console `[backlog]`

As a Superadmin or delegated Workspace Owner,
I want a bulk operations console to query, dry-run, and execute actions across workspaces or members,
So that I can respond to abuse, compliance requests, and tenant-wide changes safely and auditably.

**Acceptance Criteria:**

**Given** the admin opens `/admin/saas/bulk-ops`, **When** they build a query (e.g. "workspaces on Free plan with > 1000 memories"), **Then** the backend validates the query against an allow-list of filterable fields and returns a paginated preview with exact row count.

**Given** the admin selects an action (e.g. `archive_inactive_workspaces`, `rotate_api_keys`, `assign_role`, `delete_source_type_memories`), **When** they click "Dry-run", **Then** the system simulates the action, lists affected subjects, estimates duration/credits, and reports conflicts without mutating data.

**Given** the admin confirms a dry-run and provides an `Idempotency-Key`, **When** the backend executes, **Then** it schedules an async `bulk_op_job`, returns `202 Accepted` with `job_id`, and enforces INV-29.2 by rejecting duplicate keys with identical effect.

**Given** a bulk op is running, **When** the admin polls `GET /admin/saas/bulk-ops/{job_id}`, **Then** they see progress %, processed count, failed rows, and a cancel button if the job supports cancellation.

**Given** any bulk op completes or fails, **When** the job finishes, **Then** it writes one `audit_events` row per affected subject (`actor_id`, `subject_type`, `subject_id`, `diff_payload`, `idempotency_key`) and a summary row; failed rows are written to `bulk_op_errors` for retry.

**And** only Superadmin can execute cross-workspace actions; Workspace Owner can only execute within their own workspace and must hold `settings_write` + `member_remove`.

_FR-103 · AR-17 · AR-18 · UX-DR-PRFAQ-5 · NFR-2 · NFR-5 · INV-29.1 · INV-29.2 · AD-AUDIT-1._

### Story 29.5: Memory Browser & Research Timeline for Analyst `[backlog]`

As an Analyst in a workspace,
I want a memory browser that lists, filters, and explores research memories with source citation and version history,
So that I can verify facts, trace research lineage, and flag outdated or low-confidence claims.

**Acceptance Criteria:**

**Given** the Analyst opens `/workspace/memory-browser`, **When** the page loads, **Then** it shows a paginated, sortable list of `Memory` rows scoped to the workspace, with columns: content snippet, source type, source URL, confidence, created at, updated at, created by, version count, and flag status.

**Given** the Analyst uses the filter bar, **When** they select source type, confidence range, time range, creator, or search by keyword, **Then** the backend applies `workspace_id` RLS first (INV-29.3), then filters, and returns results in < 300ms for workspaces up to 100,000 memories.

**Given** the Analyst clicks a memory row, **When** the detail panel opens, **Then** it shows: full content, all source citations with click-to-source, version history (who changed what, when), linked research threads, and a "Flag for review" action.

**Given** the Analyst flags a memory as outdated or incorrect, **When** they submit a note, **Then** the system creates a `memory_review_queue` entry with `flag_reason`, notifies the Owner/Editor, and does not auto-delete or auto-rewrite the memory.

**Given** the Analyst has only `memory_read` permission, **When** they try to flag or edit, **Then** the UI hides the actions and the backend rejects with `403`; with `memory_write` they can propose an edit that goes through approval workflow.

**Given** the Analyst toggles "Research timeline" view, **When** the view switches, **Then** memories are grouped by research thread, ordered chronologically, with branch/merge markers when a memory appears in multiple threads.

**And** the browser is reachable from the analyst workspace dashboard and is keyboard-navigable / screen-reader friendly.

_FR-104 · AR-17 · UX-DR-PRFAQ-1 · UX-DR-PRFAQ-6 · NFR-1 · NFR-2 · NFR-5 · INV-29.3 · AD-MEMORY-1._

### Story 29.6: Data Governance & Retention Policy Console `[backlog]`

As a workspace Owner or Superadmin,
I want a governance console to define retention policy, source risk tiers, DNC list, and right-to-delete flows,
So that Nowing cloud stays compliant with scraped-source ToS and data-subject requests.

**Acceptance Criteria:**

**Given** the Owner opens `/workspace/governance`, **When** the page loads, **Then** it shows the active retention policy (`memory_retention_days`, `memory_auto_archive_enabled`, `memory_retention_action`), source risk tier mapping, DNC list entries, and a "Right-to-delete" request queue.

**Given** the Owner edits the retention policy, **When** they save, **Then** the backend validates the window against source risk tiers (shortest required window wins), schedules the lifecycle job, and logs the change to `audit_events`.

**Given** a source risk tier is changed from `low` to `high`, **When** the change is saved, **Then** the system pauses all active scrapes for that source type across the workspace and shows a warning requiring explicit opt-in before resuming.

**Given** the Owner receives a right-to-delete request, **When** they approve it, **Then** the system runs a dry-run listing affected `Memory` rows, versions, relations, and embeddings, and only purges after explicit confirmation; bulk deletion > 100,000 rows is chunked into 1,000-row batches with progress and cancel-ability.

**Given** a DNC phone/email/tax code is added, **When** the entry is saved, **Then** it propagates to the workspace blacklist within < 1s, suppresses future scraping/messaging for that value, and writes an `audit_events` entry.

**Given** self-host vs cloud deployment, **When** the policy is published, **Then** it clearly states that self-host users retain responsibility for source compliance, while cloud Nowing acts as a processor with documented retention windows (tái khẳng định Story 28.3).

**And** all bulk lifecycle actions are idempotent, auditable (AR-18), and reversible within 7 days for archived rows.

_FR-97 · FR-104 · AR-13 · AR-17 · AR-18 · UX-DR-PRFAQ-5 · UX-DR-PRFAQ-6 · NFR-1 · NFR-2 · NFR-5 · INV-28.2 · INV-29.2 · AD-28.3._

### Epic 29 — Requirements Coverage Map

| Requirement | Story | Notes |
|---|---|---|
| **FR-100** Custom workspace roles & permissions builder | **29.1** | Permission matrix, custom CRUD, Owner ceiling, `Admin` name reservation. |
| **FR-101** Workspace health & adoption analytics dashboard | **29.2** | Health metrics, drill-down, quota CTA, export. |
| **FR-102** Tenant subscription tier & quota management | **29.3** | Plan directory, trial, upgrade/downgrade, 7-day reversal, proration. |
| **FR-103** Admin bulk operations console | **29.4** | Query builder, dry-run, Idempotency-Key, async job, per-subject audit. |
| **FR-104** Memory browser & research timeline for analyst | **29.5** | Paginated memory list, filter, click-to-source, flag, version/timeline. |
| **AR-17** SaaS admin operations console | **29.1–29.6** | Custom roles, health dashboard, tier, bulk ops, memory browser, governance. |
| **AR-18** Auditability & traceability admin bulk op | **29.3–29.6** | `audit_events` cho tier change, bulk op, retention, DNC, right-to-delete. |
| **UX-DR-PRFAQ-5** SaaS admin operations console | **29.1–29.4** | `/admin/saas` role/tier/quota/health/bulk console. |
| **UX-DR-PRFAQ-6** Analyst memory browser / research timeline | **29.5** | UI filter memory theo thread/source/confidence/time, click-to-source, flag. |

**Story count:** 29.1–29.6 (6 stories) · **Status:** all `[backlog]` · **Dependencies:** Epic 1, Epic 3, Epic 8, Epic 25, Epic 28.
