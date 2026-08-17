# Architecture Review v4 — Epic 26 (Post-Update)

**Target:** `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`  
**Story:** `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`  
**Review date:** 2026-08-17  
**Reviewer:** Manual  

## Verdict: READY FOR REVIEW — BLOCKERS RESOLVED

Sau khi hoàn thành update, tất cả BLOCKER trong v2 đã được giải quyết hoặc ghi rõ [ASSUMPTION]/[DEFERRED]. Architecture spine **lint PASS**; story 26.1 đã đồng bộ với AD mới.

## Lint

```json
{
  "ok": true,
  "spine": "ARCHITECTURE-SPINE.md",
  "total_findings": 0,
  "findings": []
}
```

## Delta từ v3 sang v4

### Architecture spine — đã cập nhật

| AD / Section | Thay đổi chính |
|---|---|
| Frontmatter | `status: review` |
| AD-101 | ChainLens → Nowing; API key auth; `chunks.id` UUID; retire legacy `NowingIngestService` |
| AD-102 | Sidecar là exception AD-1; `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`; Redis XAUTOCLAIM/DLQ; centralized stream registry |
| AD-103 | Tên model chuẩn (`deepseek-v4-*`, `Qwen/Qwen3.8-27B`), giá peak/off-peak, warning Gemini PII, vLLM overhead |
| AD-104 | Liệt kê cột `leads` được publish; loại trừ PII; Next.js 16 cache note |
| AD-105 | PII encryption deferred to Fernet/TokenEncryption; HMAC canonical form; `value_hmac` NOT NULL unique; unlock billing; audit log; opt-out |
| AD-109 | REST endpoint canonical; optional MCP tool; `value_hmac` NOT NULL/unique; rate limit; degenerate rejection |
| AD-110 | Dùng DNC tables thay vì `pii_blacklists`; refund cap chi tiết; two-tier unlock UX; opt-out workflow |
| §5 | [ASSUMPTION] COGS working range $17–$35, margin 76.7%–88.7% |
| §6 | Thêm assumption về DeepSeek, Gemini, proxy/HLR, PII encryption [DEFERRED] |
| Data plane | `chunks.embedding: Vector(1536)`; `leads.value_hmac` NOT NULL unique; `verified_contacts` encrypted (Fernet/AES-GCM deferred) |
| API contract 4.2 | `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`; response thêm `failed_count` |

### Story 26.1 — đã cập nhật

- Title/status: `in-review`, REST endpoint thay vì FastMCP route.
- AC-1: `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`; reject degenerate leads; DNC check; Fernet/TokenEncryption; rate limit; `failed_count`.
- AC-2: `value_hmac` NOT NULL + `UNIQUE(workspace_id, value_hmac)`; sort by `value_hmac ASC`; concurrency stress test.
- AC-3: API key auth; `sha256(content).hexdigest()`; single 1536-dim embedding; `chunks.id` UUID; `chainlens_ingest_jobs` status/counts.
- AC-4: Column list cho `zero_publication`; exclude PPI columns.
- AC-5: Thêm chi tiết test scope.
- Tasks: đúng file paths, migration 225, không tạo `pii_blacklists` mới, `lead_batch_routes.py`, optional MCP tool.

## Cảnh báo / vẫn cần verify

1. **PII encryption method:** AD-105 chọn Fernet/TokenEncryption hiện có; AES-256-GCM ghi [DEFERRED]. Nếu sau này migrate sang AES-GCM, cần AD amendment + migration decrypt/re-encrypt.
2. **Migration số thứ tự:** Story gợi ý 225; dev phải `ls alembic/versions` để chọn số thực tế chưa dùng.
3. **Unit economics:** Các số vẫn là [ASSUMPTION]; cần vendor quotes và số đo thực trước khi dùng cho pricing.
4. **MCP tool optional:** Nếu DSH sidecar không dùng MCP transport, có thể bỏ qua `nowing_mcp/mcp_server/features/lead_intelligence/batch_ingest_leads.py`.
5. **Contact unlock billing:** AD-105 quy định 1.5 credits; cần đảm bảo code `BillingEvent` + `wallet_credit` integration được implement.

## Tổng kết

Epic 26 architecture + Story 26.1 hiện coherent với existing codebase và parent AD. Có thể chuyển sang implementation sau khi team review/approve.

## Artifacts

- v2 HTML: `epic-26-architecture-review-2026-08-17-v2.html`
- v3 Markdown: `epic-26-architecture-review-2026-08-17-v3.md`
- v4 Markdown: `epic-26-architecture-review-2026-08-17-v4.md`
