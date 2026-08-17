---
title: "Amendment — Epic 12 / 21 / 22 / 23 Readiness Correction"
prd: "prd-Nowing-2026-07-22/prd.md"
amendment_date: 2026-08-17
status: ADOPTED
---

# Phụ lục cải chính sẵn sàng triển khai — Epic 12, 21, 22, 23

## Tóm tắt

Báo cáo `implementation-readiness-report-2026-08-17.md` đã ghi nhận các yêu cầu HR/Recruitment (FR-43..47), lead-gen (FR-63..69), Telegram scraper (FR-70..79) và Zalo/Scalability/Affiliate (FR-89..92) ở trạng thái `PROPOSED` / `READY` / `DEFERRED`, đồng thời đánh dấn pháp lý / ToS là cổng cứng (hard gate). Sau khi kiểm tra lại code thực tế (`nowing_backend/app/capabilities/vietnamworks/`, `topcv/`, `itviec/`, `vn_jobs/`, `nowing_backend/app/lead_intelligence/`, `nowing_mcp/mcp_server/features/scrapers/platforms/vn_jobs.py`, `nowing_mcp/mcp_server/selfcheck.py`, v.v.) và `sprint-status.yaml` (cập nhật 2026-08-17), pháp lý đã phê duyệt, và các câu chuyện trong Epic 12/21/22/23 đều ở trạng thái `done`, phụ lục này cải chính trạng thái các FR tương ứng trong `epics.md` và làm rõ rằng PRD `prd-Nowing-2026-07-22/prd.md` vẫn là nguồn chân lý cho lõi sản phẩm, còn phụ lục này bổ sung các yêu cầu đã được triển khai thực tế.

## 1. HR / Recruitment Vertical — Epic 12 (FR-43..47)

Tất cả các FR liên quan đến thị trường việc làm Việt Nam đã được implement và kiểm tra:

| FR | Tên | Epic / Story | Trạng thái cải chính | Ghi chú |
|---|---|---|---|---|
| FR-43 | VietnamWorks Scraper | E12.1 | `DONE` | `app/capabilities/vietnamworks/scrape/` (executor/definition/schemas), `app/proprietary/platforms/vietnamworks/`, MCP/REST/capability registered. |
| FR-44 | TopCV Scraper | E12.2 | `DONE` | `app/capabilities/topcv/scrape/`, `app/proprietary/platforms/topcv/`, anti-bot POC pass, Cloudflare/residential proxy fallback. |
| FR-45 | ITviec Scraper | E12.3 | `DONE` | `app/capabilities/itviec/scrape/`, `app/proprietary/platforms/itviec/`, server-rendered parsing, salary hidden handling. |
| FR-46 | `vn_jobs.aggregate` | E12.4a–e | `DONE` | `app/capabilities/vn_jobs/aggregate/` (executor/definition/schemas), normalization/dedupe/confidence/PII/ingest/exposure. |
| FR-47 | PII Redaction for Job Data | E12.5 | `DONE` | Pipeline `app/services/pii/redact.py` áp dụng trước khi lưu / gửi `Chunk[]`. |

- **Pháp lý / ToS:** Phê duyệt bởi legal counsel ngày 2026-08-08 — Nowing không bị phân loại là "môi giới việc làm" / employment service provider đối với VietnamWorks, TopCV, ITviec.
- **Anti-bot:** TopCV anti-bot / Cloudflare POC pass; ITviec rate-limit + user-agent rotation + circuit-breaker pass; VietnamWorks public API không yêu cầu auth.
- **Câu chuyện liên quan trong `sprint-status.yaml`:** 12-0..12-10 đều `done`.

## 2. Lead Gen Intelligence — Epic 21 (FR-63..69)

Tất cả các FR lead-gen đã được implement:

| FR | Tên | Epic / Story | Trạng thái cải chính | Ghi chú |
|---|---|---|---|---|
| FR-63 | Intent Signal Detection | E21.1 | `DONE` | `app/lead_intelligence/signals/service.py`, `SignalEvent`, unit + integration tests. |
| FR-64 | Lead Scoring & Prioritization | E21.2 | `DONE` | `app/lead_intelligence/scoring/service.py`, `LeadScore`, fit/intent composite 0.5/0.5. |
| FR-65 | Vietnam Phone & Contact Waterfall Engine | E21.3 | `DONE` | 3-tier waterfall (Batdongsan token pool → Chotot API → Zalo UID verification), auto-refund SLA. |
| FR-66 | Outbound Prospecting Automation | E21.4 | `DONE` | Email + multi-source lead generation, `lead_gen_orchestrator`. |
| FR-67 | CRM Integration & Write-Back | E21.5 | `DONE` | `app/lead_intelligence/crm/` (HubSpot, Salesforce, Pipedrive, Lark Base, Google Sheets adapters). |
| FR-68 | Zalo / Telegram Outbound (Vietnam) | E21.6 | `DONE` | Zalo OA ZNS, Telegram bot alert, `zalo.me/{phone}` deep-link; không còn deferred. |
| FR-69 | Outcome-Based Pricing & Transparent Credit Ledger | E21.7 | `DONE` | `$0 chat & sequencer`, pay per verified lead / outcome, `BillingEvent` + `OutcomeEvent`. |

- **Câu chuyện liên quan trong `sprint-status.yaml`:** 21-1..21-18 đều `done`.
- **Ghi chú pháp lý:** DNC/Decree 91/2020, consent, PII pipeline (FR-47/AD-25), affiliate audit đã được legal review và accepted.

## 3. Telegram Scraper & Channel Ingestion — Epic 22 (FR-70..79)

Các FR Telegram đã được implement:

| FR | Tên | Story | Trạng thái cải chính |
|---|---|---|---|
| FR-70 | Telegram Web Preview Scraper | 22.1 | `DONE` |
| FR-71 | Telegram MTProto Client Ingestion | 22.2 | `DONE` |
| FR-72 | Telegram Scraper Platform Accounts & Session Onboarding | 22.2 | `DONE` |
| FR-73 | Telegram Rate Limiter & FloodWait Cooldown | 22.2 | `DONE` |
| FR-74 | Telegram Async S3 Media Streaming | 22.3 | `DONE` |
| FR-75 | Telegram Entity Extraction | 22.3 | `DONE` |
| FR-76 | Telegram Realtime Stream Daemon | 22.3 | `DONE` |
| FR-77 | Telegram Alert Engine Trigger | 22.3 | `DONE` |
| FR-78 | Telegram AI Agent Tools | 22.3 | `DONE` |
| FR-79 | Telegram PostgreSQL Storage & Zero Cache Sync | 22.1 | `DONE` |

- **Câu chuyện liên quan trong `sprint-status.yaml`:** 22-1..22-3 đều `done`.

## 4. Enterprise Lead Infrastructure — Epic 23 (FR-89..92)

Các FR infrastructure/scalability/outreach đã được implement:

| FR | Tên | Story | Trạng thái cải chính |
|---|---|---|---|
| FR-89 | Async Scraper Worker Pool (Celery + Redis Streams) | 23.1 | `DONE` |
| FR-90 | Official Zalo OA Webhook & ZNS Template Automation | 23.2 | `DONE` |
| FR-91 | Automated VietQR Affiliate Payout Reconciliation | 23.3 | `DONE` |
| FR-92 | PostgreSQL RLS & Table Partitioning for Multi-Million Leads | 23.4 | `DONE` |

- **Câu chuyện liên quan trong `sprint-status.yaml`:** 23-1..23-4 đều `done`.

## 5. Quan hệ với PRD chính

- `prd-Nowing-2026-07-22/prd.md` vẫn là nguồn chân lý cho scope lõi (Auth, Workspace, KB/Memory, Chat, Deliverables, Automations, Clients, Billing, Deep Research, Admin).
- Phụ lục này không thay thế PRD; nó bổ sung các yêu cầu mở rộng (HR vertical, lead-gen, Telegram, Zalo/scalability/affiliate) đã được triển khai và xác thực sau ngày PRD được cập nhật lần cuối (2026-08-10).
- Các FR-70..92 trong `epics.md` không còn là scope creep — chúng là kết quả của các quyết định sprint 2026-08-10..2026-08-16 và đã được implement, được phản ánh trong `sprint-status.yaml`.

## 6. Cổng còn mở

- **NFR-9 State B** (deep-research sync chat-mode) vẫn cần benchmark p95 `balanced` ≤ 30s để ratify trước khi bật mặc định.
- **Docs sync:** Một số tiêu đề epic kỹ thuật (E20, E22, E24, E25) cần bổ sung user-value framing khi cập nhật marketing/docs, nhưng code đã done.
- **UX archive:** Các `ux-contract-*` cũ đã được chuyển sang `_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/`; UX chuẩn hiện tại là `ux-Nowing-2026-08-15`.
