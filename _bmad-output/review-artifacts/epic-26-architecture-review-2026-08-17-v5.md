# Architecture Review v5 — Epic 26 (Final, Post-Resolution)

**Target:** `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`  
**Story:** `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`  
**Review date:** 2026-08-17  
**Reviewer:** Manual  

## Verdict: READY FOR APPROVAL → FINAL

Tất cả 5 cảnh báo từ v4 đã được giải quyết. Architecture spine lint **PASS**. Story 26.1 coherent với architecture. Không còn BLOCKER, HIGH, MEDIUM, hay LOW unresolved.

## Lint

```json
{
  "ok": true,
  "spine": "ARCHITECTURE-SPINE.md",
  "total_findings": 0,
  "findings": []
}
```

## Resolution of v4 warnings

| # | Warning | Resolution |
|---|---|---|
| 1 | PII encryption method (AES-256-GCM vs Fernet) | **Decided:** canonical là `VerifiedContactEncryption` (Fernet/TokenEncryption). Đã xóa mọi `AES-256-GCM` deferred khỏi AD-105, data plane, assumptions, và story. Code block AES-GCM trong story được thay bằng pattern dùng `VerifiedContactEncryption`. |
| 2 | Migration number hardcoded 225 | **Resolved:** Story giờ yêu cầu tạo `alembic revision --autogenerate` và dùng revision ID do Alembic gán, không hardcode số. |
| 3 | Unit economics in architecture | **Resolved:** Đã chuyển bảng giá/margin sang `UNIT-ECONOMICS-HYPOTHESIS.md` (business hypothesis). Spine §5 chỉ còn yêu cầu engineering: ghi `TokenUsage.cost_micros`, debit wallet, log model usage. |
| 4 | MCP tool optional | **Resolved:** AD-109 và story chốt rõ: **không** làm MCP tool trong epic này. DSH gọi trực tiếp REST endpoint. Nếu sau này cần MCP, sẽ có story riêng. |
| 5 | Contact unlock billing | **Resolved:** AD-105 thêm endpoint, balance check, transaction gồm decrypt + `is_unlocked` + `wallet_credit.apply_debit` + `BillingEvent`. Story thêm Task 7 với các bước cụ thể và tests. |

## Sanity checks

- [x] Không còn `AES-256-GCM` trong `ARCHITECTURE-SPINE.md`.
- [x] Không còn `AES-256-GCM` / `pii_vault_service` trong Story 26.1.
- [x] Không còn `225_add` hay `218` hardcoded trong Story 26.1.
- [x] Không còn `MCP tool` / `nowing_mcp` optional trong Story 26.1.
- [x] Unit economics table đã chuyển ra `UNIT-ECONOMICS-HYPOTHESIS.md`.
- [x] Contact unlock billing có endpoint, `wallet_credit`, `BillingEvent`, tests.
- [x] `lint_spine.py` pass.

## Recommendation

- Đổi `ARCHITECTURE-SPINE.md` frontmatter `status: review` → `status: final`.
- Đổi Story 26.1 `Status: in-review` → `Status: ready-for-dev`.
- Chuyển giao cho dev team.

## Artifacts

- v5 review: `epic-26-architecture-review-2026-08-17-v5.md`
- Updated spine: `ARCHITECTURE-SPINE.md`
- Updated story: `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`
- Business hypothesis: `UNIT-ECONOMICS-HYPOTHESIS.md`
- Memlog: `.memlog.md`
