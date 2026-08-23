---
title: "AD-28.3 — Memory Retention, Right-to-Delete & Storage Cap"
status: ADOPTED
date: 2026-08-23
owner: Architecture / Legal
binds: FR-97, AR-13, RS-11, AD-DEFER-4, AD-18, NFR-1b/1c/1d
---

# AD-28.3 — Memory Retention, Right-to-Delete & Storage Cap

## Context

Dữ liệu scrape lưu vào memory dài hạn (Reddit, YouTube, TikTok, Amazon, v.v.) mang rủi ro pháp lý nếu nguồn ToS thay đổi hoặc user yêu cầu xóa. Cần hệ thống retention và right-to-delete mà không cascade toàn bộ workspace. Đồng thời, workspace memory không thể tăng vô hạn vì chi phí storage, embedding index, và inference sẽ phình theo — cần một giới hạn cứng (count cap) làm lớp phòng vệ sớm.

## Decision

### Source risk tier (owned by Story 28.3)

Mỗi `source_type` được gán `legal_risk_tier ∈ {low, medium, high}` trong bảng `memory_source_legal_tiers`:

| Source type | Risk tier | Ghi chú |
|---|---|---|
| `web_crawl`, `document` | low | User-owned hoặc public |
| `reddit`, `youtube`, `google_maps` | medium | Public but ToS có attribution / rate-limit |
| `tiktok`, `amazon` (product data), `instagram` | high | Restrictive ToS; disable by default |

*Story 28.5 KHÔNG tạo bảng này; nó đọc `legal_risk_tier` (nếu đã có) để quyết định default `memory_retention_days` cho từng `source_type`, hoặc dùng default workspace khi chưa có.*

### Storage cap

- `WorkspaceLimit.max_memory_count` và `WorkspaceLimit.max_memory_bytes` ràng buộc số lượng memory và kích thước ước tính của một workspace.
- `max_memory_count` là **hard gate**: khi đạt ngưỡng, `MemoryRepository.create_memory` từ chối insert mới với `403 limit_exceeded`.
- `max_memory_bytes` là **soft visibility**: hiển thị trong usage dashboard như metric ước lượng; v1 không enforce chính xác vì pgvector + TOAST nén không cho tính bytes đúng.
- Self-host default `None` (unlimited) trừ khi admin override.
- Binds: `AD-DEFER-4` (data lifecycle), `AD-18` + `NFR-1b/1c/1d` (bound cho memory).

### Retention policy

- `Workspace.memory_retention_days` (nullable Integer), `Workspace.memory_auto_archive_enabled` (Boolean, default false), `Workspace.memory_retention_action` (String, default `"archive"`) — **mirror pattern `document_retention_*` đã có**.
- Default cloud: `memory_retention_days = 365`, `memory_auto_archive_enabled = false`, `memory_retention_action = "archive"`.
- Self-host default: `memory_retention_days = null`, `memory_auto_archive_enabled = false` (admin tự chịu trách nhiệm).
- `Memory.archived_at` (nullable TIMESTAMP) là soft-delete marker — **giống `Document.archived_at`**, dễ index, dễ tích hợp với UI sẵn có.
- Hết hạn → task `apply_memory_retention_policies` xử lý:
  - `memory_retention_action = "archive"`: set `archived_at = now()`.
  - `memory_retention_action = "delete"`: hard delete `Memory` + `MemoryVersion` + `MemoryRelation` + embedding. *(v1 không có grace period; nếu legal yêu cầu sau này, thêm `Workspace.memory_grace_period_days`.)*
- `MemoryHybridSearch`, `list_memories`, MCP recall, chat memory injection **phải** filter `archived_at IS NULL`.

### Right-to-delete

- Single memory: `DELETE /workspaces/{id}/memories/{memory_id}` → hard delete + `audit_events`.
- Bulk by `source_type` + `source_id` (admin API): chạy dry-run trả preview count, sau confirm mới purge chunked.
- Bulk >100.000: chunked batches 1.000 rows, `DELETE ... WHERE id IN (...)` với progress reporting; có thể cancel giữa các batch.

### Audit

- Mọi xóa (single, bulk, retention purge) ghi `audit_events` với `action=memory_delete|bulk_delete|retention_purge`, `actor_id`, `affected_count`, `reason`.

## Consequences

- **Positive:** Cloud GA có thể chứng minh compliance.
- **Positive:** Self-host không bị ép policy.
- **Positive:** Workspace memory không thể phình vô hạn; phù hợp `AD-18` / `NFR-1b`.
- **Negative:** Bulk delete lớn cần background job, không thể synchronous.
- **Risk:** High-risk source disable by default có thể làm giảm auto-extract coverage.
