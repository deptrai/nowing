---
title: "AD-28.3 — Retention & Right-to-Delete for Long-Term Scrape Data"
status: ADOPTED
date: 2026-08-21
owner: Architecture / Legal
binds: FR-97, AR-13, INV-28.2
---

# AD-28.3 — Retention & Right-to-Delete for Long-Term Scrape Data

## Context

Dữ liệu scrape lưu vào memory dài hạn (Reddit, YouTube, TikTok, Amazon, v.v.) mang rủi ro pháp lý nếu nguồn ToS thay đổi hoặc user yêu cầu xóa. Cần hệ thống retention và right-to-delete mà không cascade toàn bộ workspace.

## Decision

### Source risk tier

Mỗi `source_type` được gán `legal_risk_tier ∈ {low, medium, high}` trong bảng `memory_source_legal_tiers`:

| Source type | Risk tier | Ghi chú |
|---|---|---|
| `web_crawl`, `document` | low | User-owned hoặc public |
| `reddit`, `youtube`, `google_maps` | medium | Public but ToS có attribution / rate-limit |
| `tiktok`, `amazon` (product data), `instagram` | high | Restrictive ToS; disable by default |

### Retention policy

- `Workspace.retention_days` default 365 ngày cho cloud; self-host default 0 (unlimited, admin tự chịu trách nhiệm).
- Hết hạn → memory chuyển `status='archived'`; sau `grace_period_days` (30) mới purge.
- Purge xóa row `Memory`, `MemoryVersion`, `MemoryRelation`, và embedding. `ResearchThread` giữ lại nếu còn memory khác.

### Right-to-delete

- Single memory: `DELETE /workspaces/{id}/memories/{memory_id}` → soft-delete + `audit_events`.
- Bulk by `source_type` + `source_id`: admin API chạy dry-run trả preview count, sau confirm mới purge chunked.
- Bulk >100k: chunked batches 1.000 rows, `DELETE ... WHERE id IN (...)` với progress reporting; có thể cancel giữa các batch.

### Audit

- Mọi xóa ghi `audit_events` với `action=memory_delete|bulk_delete|retention_purge`, `actor_id`, `affected_count`, `reason`.

## Consequences

- **Positive:** Cloud GA có thể chứng minh compliance.
- **Positive:** Self-host không bị ép policy.
- **Negative:** Bulk delete lớn cần background job, không thể synchronous.
- **Risk:** High-risk source disable by default có thể làm giảm auto-extract coverage.
