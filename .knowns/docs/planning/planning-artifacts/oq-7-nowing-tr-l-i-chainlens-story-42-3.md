---
title: 'OQ-7 — Nowing trả lời ChainLens (story `42-3`)'
description: ''
createdAt: '2026-07-28T12:47:48.233Z'
updatedAt: '2026-08-04T14:53:26.339Z'
tags:
  - oq-7
  - chainlens
  - nowing
  - integration
  - cost-contract
---

# OQ-7 — Nowing trả lời ChainLens (story `42-3`)

## Context
Story `42-3` xác nhận nhu cầu tích hợp từ phía Nowing trước khi ChainLens hoàn tất contract v4 (`ADR-CHAINLENS-AS-NOWING-MICROSERVICE`).

## 4 câu hỏi Nowing → ChainLens (E9.1b/E9.2/E9.3)

### Q1 — Endpoint surface
**Nowing chỉ cần `POST /api/v1/search` SSE.** Không cần `/api/v1/answer`, `/api/v1/contents`, `/api/v1/reason` hay `/api/v1/extract` trong v4.
- Các endpoint `33-4/33-5` (`contents`/`answer` REST) bị `deferred`.
- `39-2` playground chỉ hiển thị `/search` + `/extract` (JSON) với tab "Coming soon" cho các endpoint chưa có.

### Q2 — SSE cost contract ⚠️ CORRECTED 2026-08-04
**Bản gốc story 42-3 ghi "flat billing (`CHAINLENS_QUERY`) → no per-query cost needed" — ĐÃ LỖI THỜI.**

Nowing PRD `FR-37` + Epic 9.2 (done 2026-08-02) yêu cầu parse `costDollars` thật từ terminal `done` frame:
- `done.usage.costDollars` là **số USD** (float), tính toàn pipeline (classifier + researcher + writer + reflection).
- Nowing parse thành `TokenUsage.cost_micros` (1 USD = 1_000_000 micros).
- Fallback 60k micros (~$0.06) chỉ khi engine không emit `costDollars`.
- Số thật đo 2026-08-02: speed $0.0353 · balanced $0.0482 · quality $0.0671 (avg $0.0519).
- `CHAINLENS_QUERY_MICROS_PER_CALL` hạ xuống fallback, log warning mỗi lần dùng.

### Q3 — Geo-access
**Nowing không cần geo-routed research (41-2).** Nowing crawler có proxy pool riêng, geo-access của ChainLens là redundant.
- `41-2-geo-access-feature` trạng thái `deferred`.

### Q4 — Auth / rate-limit
**Nowing cần API key + per-key rate limit (Story 39-1, done).**
- ChainLens `ApiKeyService` / `ApiKeyGuard` / `B2bRateLimiterService` mở rộng để lưu `rateLimit` per key.
- Không dùng JWT/HMAC context của Nowing user trực tiếp; service-to-service qua API key.

### Q5 — Mode mapping
Nowing UX modes: `speed`, `balanced`, `quality`, `auto`.
- ChainLens `mode` trong `/api/v1/search`: `ask` | `reason` | `research` | `speed` | `balanced` | `quality`.
- Nowing map nội bộ: `speed/balanced/quality` đến các policy tương ứng; `auto` để ChainLens chọn.

## Liên kết
- ChainLens: `42-3-verify-nowing-endpoint-needs.md`, `sprint-status.yaml` 42-3.
- Nowing: `PRD` FR-37/NFR-9, `epics.md` E9.2, `9-2-deep-research-cost-metering.md`.

## Action items
- [ ] Sửa story `42-3-verify-nowing-endpoint-needs.md` dòng "flat billing" thành "real costDollars parsing".
- [ ] Đồng bộ `chainlens-research/_bmad-output/sprint-status.yaml` reason dòng 42-3.
- [ ] Xác nhận `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` parse `costDollars` theo FR-37.
