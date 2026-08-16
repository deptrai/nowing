# Architecture Review v3 — Epic 26 (Manual, Post-Partial-Update)

**Target:** `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`  
**Story:** `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`  
**Review date:** 2026-08-17  
**Reviewer:** Manual (subagent quota exhausted)  

## Verdict: CHANGES REQUESTED — Update in Progress

Epic 26 spine đã được cập nhật một phần để giải quyết các BLOCKER trong v2 review, nhưng nhiều AD và story vẫn chưa đồng bộ. Không nên chuyển sang dev cho đến khi update hoàn tất.

## Lint

```json
{
  "ok": true,
  "spine": "ARCHITECTURE-SPINE.md",
  "total_findings": 0,
  "findings": []
}
```

- [x] Không còn placeholder/template token.
- [x] Không còn AD trùng hay missing fields.

## Các thay đổi đã áp dụng (delta từ v2)

| Vị trí | Thay đổi |
|---|---|
| Frontmatter | `status: final` → `status: review` |
| §1 Topology | Ghi rõ Control Plane là "authenticated REST/MCP Tool Gateway" |
| Mermaid diagram | Sửa nhãn FastMCP, model names/prices, DeepSeek names |
| AD-101 | Rõ ràng ChainLens → Nowing `POST /v1/chainlens/ingest` bằng API key; yêu cầu retire `NowingIngestService` legacy; `chunks.id` phải UUID |
| AD-102 | Thêm exception to parent AD-1; sidecar gọi `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` hoặc MCP tool; dùng Redis Streams XAUTOCLAIM/DLQ |

## Các BLOCKER vẫn chưa được giải quyết

1. **AD-103** vẫn còn:
   - Giá DeepSeek cũ (`$0.14/$0.28`, `$0.435/$0.87`).
   - Tên model sai (`DeepSeek-V4-Flash`, `DeepSeek-V4-Pro-0813`).
   - `Qwen 3.8-27B AWQ` không chính thức.
   - `$0 COGS` cho Gemini Flash và local vLLM chưa sửa thành warning/assumption.

2. **AD-104** vẫn còn:
   - Không liệt kê cột `leads` nào được publish/exclude.
   - Không đề cập `value_hmac` leak risk.

3. **AD-105** vẫn còn:
   - Yêu cầu AES-256-GCM trong khi code hiện dùng Fernet/TokenEncryption.
   - Cột `phone_encrypted`/`email_encrypted` vẫn trong data plane diagram.
   - Không đề cập `is_unlocked`, billing event, HMAC chuẩn.

4. **AD-109** vẫn còn:
   - Ghi `POST /mcp/v1/tools/batch_ingest_leads` trong FastMCP Gateway.
   - Không phân biệt REST endpoint vs MCP tool.
   - Không đề cập `value_hmac` NOT NULL + unique constraint.

5. **AD-110** vẫn còn:
   - `pii_blacklists` bảng mới, trong khi đã có `workspace_dnc_records`/`global_dnc_records`.
   - Không chi tiết refund cap, two-tier unlock, opt-out workflow.

6. **§5 Tokenomics** vẫn còn:
   - COGS `$15.30`, margin `89.8%` sai.
   - `$0.00` cho Gemini/vLLM.

7. **Story 26.1** chưa được sửa:
   - AC-1 vẫn mô tả `POST /mcp/v1/tools/batch_ingest_leads`, AES-256-GCM, `pii_blacklists`.
   - AC-2 vẫn `value_hmac` nullable, chưa unique constraint.
   - AC-3 vẫn `ChainLensIngestPayload` với embedding 1536/1024.
   - AC-5 vẫn thiếu test scaffolds.

## HIGH/MEDIUM vẫn mở

- FastMCP protocol confusion.
- Zero-Cache CDC column scope.
- Redis Streams DLQ/XAUTOCLAIM chưa implement.
- `is_blacklisted` column thiếu.
- Rate limit thiếu.
- RLS policy gaps.
- Refund cap, two-tier unlock ACs, opt-out workflow, audit logs.
- Migration number conflict (224/218).
- Contact unlock billing integration.
- Next.js 16 cache breaking change.

## Khuyến nghị

1. Hoàn tất update AD-103, AD-104, AD-105, AD-109, AD-110, §5, data plane diagram.
2. Cập nhật Story 26.1 ACs/Tasks/DoD theo các AD đã sửa.
3. Chạy lại lint sau khi update xong.
4. Chạy review v4 (hoặc subagent panel) trên bản hoàn chỉnh.

## Artifacts

- v1 HTML: `epic-26-architecture-review-2026-08-17.html`
- v2 HTML: `epic-26-architecture-review-2026-08-17-v2.html`
- v3 Markdown: `epic-26-architecture-review-2026-08-17-v3.md`
