---
date: 2026-08-11
---

# Sprint Plan — 2026-08-11 → 2026-08-25

**Project:** Nowing  |  **Sprint:** 2026-08-11 → 2026-08-25  |  **Capacity:** 2 backend, 1 frontend, 1 QA × 2 weeks

## Sprint Goal

Ship the Vietnam HR/Recruitment vertical P0 stories (ITviec, aggregator, PII redaction) and land ChainLens ecosystem integration client-side (service auth, chunk normalization). Strengthen platform quality (memory performance, chat benchmark, connectors UI).

## Selected Stories

| Story | Title | Epic | Priority | Owner | Effort | Dependencies | Status Goal |
|---|---|---|---|---|---|---|---|
| 12-3 | ITviec Scraper `[ready-for-dev P0]` | Epic 12 — HR/Recruitment Vertical + BĐS (Extended) | P0 | Backend | M | Crawl ITviec server-rendered HTML; no Cloudflare. | in-progress |
| 12-4 | Vietnam Job Aggregator `[ready-for-dev P0]` | Epic 12 — HR/Recruitment Vertical + BĐS (Extended) | P0 | Backend | M | Normalize + dedupe + confidence across 3 job sources; feed chainlens-research. | in-progress |
| 12-5 | PII Redaction for Job Data `[ready-for-dev P0]` | Epic 12 — HR/Recruitment Vertical + BĐS (Extended) | P0 | Backend | M | Mask/drop PII before chunks sent to ChainLens. | in-progress |
| 20-1 | Service-to-Service Auth + Cost Ledger Sync `(mới 2026-08-08)` `[ready-for-dev]` | Epic 20 — Nowing Ecosystem Integration — Feed & Recall from chainlens-research | P1 | Backend | M | ChainLens ↔ Nowing auth and cost ledger. | in-progress |
| 20-2 | Nowing Scraper `to_chunks()` + `NowingIngestService` `(mới 2026-08-08)` `[ready-for-dev]` | Epic 20 — Nowing Ecosystem Integration — Feed & Recall from chainlens-research | P1 | Backend | M | Scraper output normalized to Chunk[]. | in-progress |
| 3-17 | Memory Injection Bounded-Retrieval Performance Gate `(mới 2026-08-08)` `[ready-for-dev]` | Epic 3 — Knowledge Base + Long-Term Memory | P1 | Backend | M | Fix unbounded SELECT in memory injection. | in-progress |
| 9-6c | Memory Provenance End-to-End Revalidation Gate `(mới 2026-08-08)` `[ready-for-dev]` | Epic 9 — Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)` | P1 | Backend | M | End-to-end provenance revalidation. | in-progress |
| 4-8d | Chat quality benchmark with LLM-as-judge `[ready-for-dev]` | Epic 4 — Chat & Agents | P1 | Backend/Evals | M | Quality regression suite. | in-progress |
| 7-4 | Dedicated Connectors Layout `(mới 2026-07-30)` `[ready-for-dev]` | Epic 7 — Multi-surface Clients | P1 | Frontend | M | Connectors UI re-layout. | in-progress |

## Sprint Logic

1. **Epic 12 (HR vertical)** có 3 story P0 `ready-for-dev` và legal đã approved (2026-08-08). Đây là quick win có customer validation.
2. **Epic 20 (ChainLens integration)** có 4 story `ready-for-dev`; 20-1 và 20-2 là foundation, unblock 20-3/20-4.
3. **Epic 3/9 platform hardening** (3-17, 9-6c) giải quyết tech debt và provenance gate trước khi memory lên prod.
4. **Epic 20** stories 20-1..20-4 được chọn hết vì đều `ready-for-dev` và lấp đầy ChainLens integration end-to-end.
5. **Epic 21 (Lead Gen)** vẫn `proposed`; không đưa vào sprint cho đến khi governance gates đóng.

## Not Selected (and why)

| Story | Epic | Reason |
|---|---|---|
| 21-1..21-7 | Epic 21 | PROPOSED; governance/legal/ToS + vendor POC chưa xong. |
| 12-6 | Epic 12 | `backlog`; depends on 12-1..12-5 xong; P1. |
| 12-9 | Epic 12 | `backlog`; depends on 12-6. |
| 9-5 | Epic 9 | `backlog`; POST-MVP, chưa phê duyệt. |
| 14-2..14-4, 15-2..15-4, 16-2..16-4, 17-1..17-4 | Epic 14-17 | P2 Vietnam verticals; deferred to Phase 2. |
| 3-15, 3-16 | Epic 3 | `ready-for-dev` nhưng không khẩn hơn HR P0. |

## Risks & Blockers

| Risk | Mitigation |
|---|---|
| Anti-bot / CAPTCHA trên TopCV (12-2) vẫn đang POC | Giữ 12-2 ngoài sprint; 12-3/12-4/12-5 vẫn chạy với VietnamWorks + ITviec. |
| ChainLens API cost/signature thay đổi | 20-1 + 20-2 sử dụng contract đã agree (OQ-7). |
| QA bandwidth hạn chế | Ưu tiên regression Epic 12 + 20 trước. |

## Definition of Done

- Code merged vào `develop`.
- Unit/integration tests pass (theo verification commands trong `AGENTS.md` nếu có).
- Story status trong `sprint-status.yaml` chuyển thành `done`.
- Retro/action items ghi nhận các tech-debt phát sinh.

## Next Actions

1. PO xác nhận sprint scope.
2. Chuyển các story selected trong `sprint-status.yaml` từ `ready-for-dev`/`backlog` → `in-progress`.
3. Backend lead phân công 12-3/12-4/12-5 và 20-1/20-2.
4. Frontend lead bắt đầu 7-4; QA chuẩn bị test plan cho Epic 12.