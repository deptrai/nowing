---
date: 2026-08-11
---

# Nowing Backlog Analysis — Tổng quan toàn bộ backlog

**Date:** 2026-08-11
**Sources:** `sprint-status.yaml` + `epics.md`

## 1. Executive Summary

### Epic status
- **done:** 4
- **in-progress:** 13
- **backlog:** 1

### Story status
- **backlog:** 28
- **ready-for-dev:** 10
- **in-progress:** 1
- **done:** 68
- **deferred:** 7

## 2. Epic Overview

| Epic | Title | Status | Stories (done / r4d / in-progress / backlog / deferred) |
|---|---|---|---|
| Epic 1 | Identity, Auth & Workspace RBAC — ✅ DONE | done | 0 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 2 | Connectors — ✅ DONE (retrospective 2026-08-08) | done | 6 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 3 | Knowledge Base + Long-Term Memory — ✅ DONE | in-progress | 10 done / 1 r4d / 0 ip / 0 bl / 0 def |
| Epic 4 | Chat & Agents — ✅ DONE | in-progress | 9 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 5 | Deliverables — ✅ DONE | done | 0 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 6 | Automations — ✅ CORE DONE (4 gap mới: playbook layer) | in-progress | 5 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 7 | Multi-surface Clients — ✅ DONE | in-progress | 2 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 8 | Người dùng thấy và kiểm soát được chi phí — ✅ DONE (2026-08-02) | in-progress | 8 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 9 | Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng — ✅ DONE (2026-08-05) | in-progress | 6 done / 1 r4d / 0 ip / 1 bl / 0 def |
| Epic 10 | Connector & Scraper Expansion | done | 5 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 11 | Telegram Automation & Bot `[done]` | in-progress | 3 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 12 | HR/Recruitment Vertical — Vietnam Job Market Pilot | in-progress | 3 done / 4 r4d / 0 ip / 1 bl / 0 def |
| Epic 13 | Canonical Entity Storage & Multi-Domain Indexing `[DROPPED 2026-08-08 — ARCHIVED]` | dropped | 0 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 14 | News Aggregation (Vietnam) | in-progress | 1 done / 0 r4d / 0 ip / 3 bl / 0 def |
| Epic 15 | Financial Data (Vietnam) | in-progress | 1 done / 0 r4d / 0 ip / 3 bl / 0 def |
| Epic 16 | Company Directory (Vietnam) | in-progress | 1 done / 0 r4d / 0 ip / 3 bl / 0 def |
| Epic 17 | E-commerce Intelligence (Vietnam) | backlog | 0 done / 0 r4d / 0 ip / 4 bl / 0 def |
| Epic 18 | Vertical Client Platform (Public Agent-Chat) | in-progress | 8 done / 0 r4d / 0 ip / 0 bl / 0 def |
| Epic 20 | Nowing Ecosystem Integration — Feed & Recall from chainlens-research | in-progress | 0 done / 4 r4d / 0 ip / 0 bl / 0 def |
| Epic 21 | Lead Gen Intelligence `[PROPOSED]` (mới 2026-08-10) | proposed | 0 done / 0 r4d / 0 ip / 6 bl / 1 def |

## 3. Stories by Status

### in-progress (1)
- **tech-debt** (Epic ?): *(title not found in epics.md)*

### ready-for-dev (10)
- **3-17** (Epic 3): Memory Injection Bounded-Retrieval Performance Gate  `(mới 2026-08-08)`  `[ready-for-dev]`
- **9-6c** (Epic 9): Memory Provenance End-to-End Revalidation Gate  `(mới 2026-08-08)`  `[ready-for-dev]`
- **12-3** (Epic 12): ITviec Scraper `[ready-for-dev P0]`
- **12-4** (Epic 12): Vietnam Job Aggregator `[ready-for-dev P0]`
- **12-5** (Epic 12): PII Redaction for Job Data `[ready-for-dev P0]`
- **12-9** (Epic 12): Job Market Alerts `[P1 — depends on 12.6]`
- **20-1** (Epic 20): Service-to-Service Auth + Cost Ledger Sync  `(mới 2026-08-08)`  `[ready-for-dev]`
- **20-2** (Epic 20): Nowing Scraper `to_chunks()` + `NowingIngestService`  `(mới 2026-08-08)`  `[ready-for-dev]`
- **20-3** (Epic 20): Gap-Fill Caller + Cost Allocation (Nowing side)  `(mới 2026-08-08)`  `[ready-for-dev]`
- **20-4** (Epic 20): `NowingPrivateProvider` for `POST /v1/private-data/search`  `(mới 2026-08-08)`  `[ready-for-dev]`

### backlog (28)
- **9-5** (Epic 9): Metered Deep-Research Endpoint cho Self-Host  `(mới)`  `[POST-MVP — CHƯA PHÊ DUYỆT, đăng ký để không bị mất]`
- **12-6** (Epic 12): Saved Searches `[P0 — must ship before 12.9]`
- **14-2** (Epic 14): News Entity Enrichment `[P1]`
- **14-3** (Epic 14): News Alerts & Topic Monitoring `[P1]`
- **14-4** (Epic 14): News Digest & Synthesis `[P2]`
- **15-2** (Epic 15): Vietstock Deep Financials `[P1]`
- **15-3** (Epic 15): Stock Price Alerts `[P1]`
- **15-4** (Epic 15): Financial Trend Detection `[P2]`
- **16-2** (Epic 16): Official Business Registry `[P1]`
- **16-3** (Epic 16): Company Alerts `[P1]`
- **16-4** (Epic 16): Company Timeline `[P1]`
- **17-1** (Epic 17): Lazada Product Data `[P1]`
- **17-2** (Epic 17): Shopee Product Data `[P2]`
- **17-3** (Epic 17): Price Drop Alerts `[P1]`
- **17-4** (Epic 17): Competitor Tracking `[P2]`
- **21-1** (Epic 21): Intent Signal Detection `[PROPOSED]`
- **21-2** (Epic 21): Lead Scoring & Prioritization `[PROPOSED]`
- **21-3** (Epic 21): Enriched Contact Data `[PROPOSED]`
- **21-4** (Epic 21): Outbound Prospecting Automation `[PROPOSED]`
- **21-5** (Epic 21): CRM Integration & Write-Back `[PROPOSED]`
- **21-7** (Epic 21): Outcome-Based Pricing `[PROPOSED]`
- **td-1** (Epic ?): *(title not found in epics.md)*
- **td-2** (Epic ?): *(title not found in epics.md)*
- **td-3** (Epic ?): *(title not found in epics.md)*
- **td-4** (Epic ?): *(title not found in epics.md)*
- **td-5** (Epic ?): *(title not found in epics.md)*
- **td-6** (Epic ?): *(title not found in epics.md)*
- **td-7** (Epic ?): *(title not found in epics.md)*

### deferred (7)
- **3-7-followup** (Epic ?): *(title not found in epics.md)*
- **4-8c-followup** (Epic ?): *(title not found in epics.md)*
- **4-8d-followup** (Epic ?): *(title not found in epics.md)*
- **4-8h-followup** (Epic ?): *(title not found in epics.md)*
- **8-11-followup** (Epic ?): *(title not found in epics.md)*
- **9-6-followup** (Epic ?): *(title not found in epics.md)*
- **21-6** (Epic 21): Zalo Integration (Vietnam Market) `[DEFERRED]`

### done (68)
- **2-5** (Epic 2): Per-Workspace MCP Tool Enable/Disable Toggle  `[DONE per sprint-status: 2-5]`
- **2-6** (Epic 2): Indeed Jobs Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
- **2-7** (Epic 2): Walmart Product + Reviews Scraper  `(mới 2026-07-30)`  `[ready-for-dev]`
- **2-8** (Epic 2): Amazon EU Marketplaces  `(mới 2026-07-30)`  `[ready-for-dev]`
- **2-9** (Epic 2): Scraper API Input Validation & Error Handling  `(mới 2026-07-30)`  `[done]`
- **2-10** (Epic 2): Exa MCP Search Connector  `(mới 2026-08-05)`  `[DONE 2026-08-05]`
- **3-6** (Epic 3): Citation Scroll-to-Highlight in Full Document Editor  `[DONE per sprint-status: 3-6]`
- **3-7** (Epic 3): Memory Retention, Right-to-Delete & Legal Readiness  `[DONE retention: 3-7; memory right-to-delete/legal → xác nhận khi GA cloud]`
- **3-9** (Epic 3): Memory Recall Eval-Gate  `(mới)`  `[DONE — SHIP-GATE implementation complete; baseline ratification pending]`
- **3-10** (Epic 3): Legacy Memory Data Safety (forensic + backfill guard)  `(mới)`  `[DONE 2026-07-25]`
- **3-11** (Epic 3): Memory Dedupe & Confidence Tuning  `(mới)`  `[DONE dedupe (đã wire cosine<0.08); tuning ngưỡng optional qua 3.9]`
- **3-12** (Epic 3): Memory Security — RBAC Enforcement, Isolation & Audit  `(mới)`  `[DONE — sprint 8-5 security + IDOR fix (deferred-work 4.5)]`
- **3-13** (Epic 3): First-Run Value — Research Run sinh ra Memory  `(mới 2026-07-25)`  `[DONE — HIGH]`
- **3-14** (Epic 3): Memory Injection — chặn trên & ngân sách latency  `(mới 2026-07-25)`  `[DONE — đi kèm 3.13]`
- **3-15** (Epic 3): Run Citations as Verifiable Sources  `(mới 2026-07-30)`  `[ready-for-dev]`
- **3-16** (Epic 3): Open Knowledge Format (OKF) Export  `(mới 2026-07-30)`  `[ready-for-dev]`
- **4-7** (Epic 4): Pointer-Based Tabs with Live Title Resolution  `(mới 2026-07-30)`  `[ready-for-dev]`
- **4-8a** (Epic 4): Extend `NewChatClient` telemetry  `[done]`
- **4-8b** (Epic 4): Chat Regression Benchmark Suite  `[done/review]`
- **4-8c** (Epic 4): Production query sampler + anonymizer  `[done]`
- **4-8d** (Epic 4): Chat quality benchmark with LLM-as-judge  `[ready-for-dev]`
- **4-8e** (Epic 4): CI / deploy gate for chat regression  `[done]`
- **4-8f** (Epic 4): Benchmark stability — scrape, CAPTCHA, rate-limit, multi-turn  `[done]`
- **4-8g** (Epic 4): Benchmark mode/tier matrix and local vs production parity  `[done]`
- **4-8h** (Epic 4): Mode-Aware Chat Policy for Latency/Cost  `(mới 2026-08-05)`  `[done]`
- **6-4** (Epic 6): Direct Write-Back Actions  `[DONE per sprint-status: 6-4]`
- **6-5** (Epic 6): Memory-Driven Automations  `[DONE per sprint-status: 6-5 — cải chính 2026-07-25]`
- **6-6** (Epic 6): Playbook Reuse — expose `inputs.schema` đã có  `[GAP — P1, gated sau pilot BĐS]`
- **6-7** (Epic 6): Schema-Driven Form UI cho playbook & action  `[GAP — P1, gated sau pilot BĐS]`
- **6-9** (Epic 6): Workspace `vertical` + Playbook Library  `[GAP — P2, gated sau pilot BĐS]`
- **7-4** (Epic 7): Dedicated Connectors Layout  `(mới 2026-07-30)`  `[ready-for-dev]`
- **7-7** (Epic 7): MCP Server Tool Expansion  `(mới 2026-08-05)`  `[ready-for-dev]`  `[backfill]`
- **8-3** (Epic 8): Usage & Credit Dashboard  `[DONE per sprint-status: 8-3]`
- **8-7** (Epic 8): Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit  `(mới)`  `[DONE — 59 tests passed; gate before auto-extract goes to prod]`
- **8-8** (Epic 8): Auto-Extract Kill-Switch & Safe Default  `(mới)` `(đánh lại số từ 8.4a — C-C)`  `[DONE — flags MEMORY_AUTO_EXTRACT_ENABLED (global) + workspaces.memory_auto_extract_enabled (per-ws) đã có]`
- **8-9** (Epic 8): Memory Cost/Turn Observability  `(mới)` `(đánh lại số từ 8.5 — C-C)`  `[DONE — code-complete qua sprint story 8-4 observability-logging]`
- **8-10** (Epic 8): Docs / README / Vision Sync  `(mới)` `(đánh lại số từ 8.6 — C-C)`  `[DONE per sprint-status: 8-10]`
- **8-11** (Epic 8): Admin UI for Global LLM Model Configuration  `(mới 2026-07-26)`  `[DONE per sprint-status: 8-11]`
- **8-12** (Epic 8): Workspace Limits  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-12]`
- **8-13** (Epic 8): PostHog Product Analytics  `(mới 2026-07-30)`  `[DONE per sprint-status: 8-13]`
- **9-2** (Epic 9): Deep-Research Cost Metering (cost thật, không giá phẳng)  `(mới)`  `[DONE — P0, parser + fallback in place; waits ChainLens 34.1 full-pipeline cost, target 2026-08-19]`
- **9-3** (Epic 9): Latency Budget & State A→B Gate  `(mới)`  `[DONE per sprint-status: 9-3]`
- **9-4** (Epic 9): Docs — Quan hệ Nowing ↔ ChainLens  `(mới)`  `[DONE — P1, README/docs/.env.example synced]`
- **9-6** (Epic 9): Memory Provenance & Re-Validation  `(mới)`  `[DONE per sprint-status: 9-6]`
- **9-1a** (Epic 9): Research Degradation & Self-Host Independence  `(mới)`  `[DONE — P0, tiền đề trước khi public repo]`
- **9-1b** (Epic 9): Research Contract Regression Guard  `(mới)`  `[DONE — P0, không chặn public repo]`
- **10-1** (Epic 10): Batdongsan.com.vn Scraper  `[DONE per sprint-status: 10-1]`
- **10-2** (Epic 10): Chotot.vn / Nhà Tốt Scraper  `[done]`
- **10-3** (Epic 10): Muaban.net BĐS Scraper  `[done]`
- **10-4** (Epic 10): Vietnam BĐS Listing Aggregator & Cross-Source Trust Score  `[DONE per sprint-status: 10-4]`
- **10-5** (Epic 10): Anti-Bot / CAPTCHA Screenshot Escalation  `(mới 2026-08-08)`  `[ready-for-dev]`
- **11-1** (Epic 11): Telegram Notification Foundation `[done]`
- **11-2** (Epic 11): Telegram Write-Back, Builder UI & Chat Resolution `[done]`
- **11-3** (Epic 11): Telegram Interactive Bot & Commands `[done]`
- **12-0** (Epic 12): ToS & Legal Review `[PREREQUISITE — approved by legal counsel 2026-08-08]`
- **12-1** (Epic 12): VietnamWorks Scraper `[ready-for-dev P0]`
- **12-2** (Epic 12): TopCV Scraper `[ready-for-dev P0]`
- **14-1** (Epic 14): RSS Feed Integration `[P0]`
- **15-1** (Epic 15): CafeF Financial Data Integration `[P0]`
- **16-1** (Epic 16): masothue.com Company Data `[P0]`
- **18-1** (Epic 18): Public Agent-Chat Endpoints `[P0]`
- **18-2** (Epic 18): NewChatRequest Extension `[P0]`
- **18-3** (Epic 18): Agent Registry `[P0]`
- **18-4** (Epic 18): AgentConfig Prompt Injection `[P0]`
- **18-5** (Epic 18): ResearchThread Auto-Linkage `[P0]`
- **18-6** (Epic 18): Memory Tagging + RAG Filter `[P1]`
- **18-7** (Epic 18): Cost Traceability `[P1]`
- **18-8** (Epic 18): Rate Limiting + Tenant Isolation `[P1]`

## 4. Orphaned Sprint-Status Items

- 3-7-followup: deferred
- 4-8c-followup: deferred
- 4-8d-followup: deferred
- 4-8h-followup: deferred
- 6-6a-playbook-reuse: business-gated
- 6-7a-schema-form-ui: business-gated
- 6-9a-workspace-vertical: business-gated
- 8-11-followup: deferred
- 9-6-followup: deferred
- 13-1: dropped
- 13-2: dropped
- 13-2a: dropped
- 13-2b: dropped
- 13-2c: dropped
- 13-2d: dropped
- 13-2e: dropped
- 13-3: dropped
- tech-debt: in-progress
- td-1: backlog
- td-2: backlog
- td-3: backlog
- td-4: backlog
- td-5: backlog
- td-6: backlog
- td-7: backlog
- tech-debt-retrospective: optional

## 6. Tech Debt / Follow-up Items

- 3-7-followup: deferred
- 4-8c-followup: deferred
- 4-8d-followup: deferred
- 4-8h-followup: deferred
- 8-11-followup: deferred
- 9-6-followup: deferred
- tech-debt: in-progress
- td-1: backlog
- td-2: backlog
- td-3: backlog
- td-4: backlog
- td-5: backlog
- td-6: backlog
- td-7: backlog

## 7. Risks & Overlap Analysis

| Risk | Severity | Notes |
|---|---|---|
| Epic 21 Lead Gen newly added to sprint-status as `proposed` | Medium | Scope refined: Email-only outbound; Zalo/LinkedIn deferred; all FR-6 scrapers as lead sources |
| Epic 12 HR/BĐS + Epic 21 lead enrichment both use PII/enrichment | Medium | Boundary documented, but reuse of connector/scraper infrastructure must be explicit |
| Epic 6 automations + Epic 21 outbound sequences | Medium | Epic 21 should reuse automation runtime and notification service (Story 11.1) |
| Many `ready-for-dev` stories in Vietnam verticals (12, 14, 15, 16, 17, 20) | Medium | Resource contention if all started; needs prioritization |
| NFR-1 Performance remains PARTIAL and unassigned | Medium | Long-standing C-1 readiness item; blocks performance claims |
| Tech-debt/followup items deferred | Low | 6 followups tracked; should be triaged regularly |

## 8. Recommendations

1. **Epic 21 scope is now refined:** Email-only outbound; Zalo/LinkedIn deferred; lead sources = all FR-6 scrapers/ connectors. AD-39/AD-41 in `ARCHITECTURE-SPINE.md` updated. Move to `ready-for-dev` after governance gates close.
2. **Prioritize `ready-for-dev` stories** by business value and dependency order:
   - Epic 12 (HR vertical) is ready cluster; 12-1/12-2/12-3/12-4/12-5 depend on legal/ToS approval.
   - Epic 20 (ChainLens ecosystem integration) is ready and unblocks deep-research ingestion.
   - Epic 4.8d/7.4/7.7 are platform chat/client improvements.
3. **Resolve Epic 21 remaining open questions** (Q1–Q7 in hand-off) before freezing contracts.
4. **Assign NFR-1 Performance** to an epic (likely E3.14 or E9.3) before launch claims.
5. **Run `bmad-sprint-planning`** when Epic 21 moves to ready-for-dev to sequence dependencies and avoid resource clashes.