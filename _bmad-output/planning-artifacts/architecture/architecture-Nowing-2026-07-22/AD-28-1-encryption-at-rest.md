---
title: "AD-28.1 — Encryption-at-Rest Strategy for Nowing Memory"
status: PROPOSED
date: 2026-08-21
owner: Architecture / Security
deciders: Luisphan (PO), Architect
category: security
---

# AD-28.1 — Encryption-at-Rest Strategy for Nowing Memory

## Context

`prfaq-Nowing.md` (2026-08-21) đặt câu hỏi về trust của self-host và cloud GA (Q4/IQ9). Dữ liệu memory trong cloud cần được bảo vệ nếu DB volume bị lộ. Đồng thời, self-host phải vẫn hoạt động hiệu quả với local LLM/embedding mặc định, không gây ma sát cho onboarding <10 phút.

## Decision

Chọn **tiered encryption** với **managed key mặc định** trên cloud và **plaintext-by-default** trên self-host; **BYOK** là option.

### Tier 1 (v1, bắt buộc)
Mã hóa trước khi ghi DB:
- `Memory.content`
- `Memory.source_input` PII fields
- `MemoryVersion.corrected_content` / `previous_content`
- `ResearchThread` user-defined title/description
- `memory_relations` edge metadata nếu chứa PII

Dùng **AES-256-GCM** với key derivation từ master key. IV + salt + `key_id` lưu cùng row.

### Tier 2 (v2, deferred)
Mã hóa embedding vector `Memory.embedding`. Chỉ bật sau khi benchmark chứng minh searchable encryption hoặc thiết kế proxy index không phá vỡ HNSW/GIN. V1 giữ plaintext để HNSW search hoạt động.

### Key Management

| Mode | Mô tả |
|---|---|
| **Managed** | Nowing Cloud quản lý master key trong KMS (Hoặc `AGE`/`cryptography` local managed envelope). Key rotation hỗ trợ re-encrypt background task. |
| **BYOK** | `ENCRYPTION_KEY_PROVIDER=byok`; user cung cấp key qua API/admin; hệ thống encrypt bằng user key + envelope key của Nowing để có thể revoke mà không mất dữ liệu. |
| **Self-host** | Mặc định plaintext (`MEMORY_ENCRYPTION_ENABLED=false`). Có thể bật managed local envelope nếu admin chọn. Không bắt buộc để giữ onboarding đơn giản. |

### Rotation
- Mỗi row lưu `key_id`. Rotation tạo key mới, re-encrypt row khi row được đọc/ghi tiếp theo hoặc qua background job.
- `key_id` null → plaintext legacy; migration sẽ set `key_id='legacy'`.

## Consequences

- **Positive:** Cloud GA có thể chứng minh encrypted-at-rest; breach DB volume không lộ plaintext.
- **Positive:** Self-host không bị ma sát.
- **Negative:** ~10-20% overhead encryption trên write/read memory; cần benchmark trước khi mặc định cloud.
- **Negative:** Backup/restore phải handle `key_id`; không thể đơn giản `pg_dump` nếu BYOK.
- **Trade-off:** Embedding v2 deferred, chấp nhận risk ngắn hạn để bảo toàn search quality.

## ADR-28 Conflict Note

`AD-28` gốc trong architecture spine là "Unified matching-engine trigger" (canonical domain engine) — đã RE-SCOPED sang `chainlens-research`. Vì vậy, quyết định encryption này được đặt tên `AD-28.1` để tránh trùng lặp ID.

## Related

- `FR-96`, `AR-12`, `RS-12`, `NFR-2`, `INV-28.1`
- Epic 28, Story 28.2
