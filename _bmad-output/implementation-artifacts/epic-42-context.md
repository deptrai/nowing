# Epic 42 Context: Agent Experience & Lead Pipeline Hardening

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Nowing đang "lỗi vô hình" với cả agent external lẫn internal: `dryRun` stub trông giống success, `data:[]` nhầm lẫn "kênh chết" với "không có lead", agent scrape xong không có đường persist chính thức, PAT/session auth không có seam cho non-browser consumer, và turn dài chết không partial output. Epic 42 làm mọi failure phân biệt được `empty_result | failed | degraded` kèm lý do + recovery path, mở cửa sau đúng chuẩn (PAT + ingest REST/MCP), tập trung lead-write funnel tại một service, và bảo đảm HITL/step-cap không giết turn.

## Stories

- Story 42.1: PAT-scoped REST batch ingest — verify & harden contract + document persistence guard (`unindexed` flag + reindex retry khi embed fail)
- Story 42.2: `ToolResultEnvelope` — một result contract `{status, reason, recovery_hint, items}` xuyên mọi boundary
- Story 42.3: `GET /api/v1/scrapers/health` — aggregated channel status từ `runs` table (cached, không live-probe)
- Story 42.4: `nowing_mcp` lead tools — `leads.ingest`, `tables.create`, `leads.list`, `credits.balance`
- Story 42.5: HITL approve/reject → Gemini functionResponse mismatch fix (repro trước, fix sau)
- Story 42.6: Step-cap graceful degradation — force-synthesize partial answer thay vì `text=0`
- Story 42.7: IA fix — real `/dashboard/{id}/leads` route + service-level auto-table + empty state
- Story 42.8: Forward `context.workspaceId` qua medirus_gateway + `NOWING_DEV_BYPASS_QUOTA` flag cho dev

## Requirements & Constraints

### Invariants (ràng buộc mọi story)

- **AD-1 — Lead-write funnel:** mọi ghi vào `leads` (REST ingest, `save_leads`, `multi_source_lead_gen`, scripts, MCP tools) đi qua `LeadBatchService.ingest_batch` — điểm duy nhất gắn DNC filter, `_reject_degenerate_leads`, HMAC dedup, Fernet encrypt. **AD-1b exception được chỉ định:** auto-table get-or-create nằm TRONG `ingest_batch` (table-creation không phải lead-write).
- **AD-2 — PAT authz contract:** bypass `require_session_context` chỉ qua MỘT seam có tên (PAT scope check hiện có). Scope đầu tiên `leads:write`; PAT scoped workspace A gọi path workspace B → 403; ledger phải log `actor_pat_token_id` cho attribution (PDPD).
- **AD-3 — Một `ToolResultEnvelope` xuyên mọi boundary:** `{status: 'success'|'empty_result'|'failed'|'degraded'|'preview', reason, recovery_hint, items}` — `status` + `items` bắt buộc; `recovery_hint` sanitize + length-cap ≤500 chars, đánh dấu untrusted khi forward từ Medirus `suggestedAction`. Không được có kiểu `failed` thứ hai.
- **AD-4 — Ingest contract:** idempotency qua header `Idempotency-Key` + `UNIQUE(client_id, value_hmac)` + `ON CONFLICT DO NOTHING`; validation ≥1 contact field per lead; batch trộn degenerate+valid → reject-all 422 `{status:'failed', rejected_indexes:[], reason_map:{}}` (không partial-drop lặng lẽ); `client_id` = campaign/source namespace.
- **AD-6 — Repro-before-fix:** áp cho MỌI correctness bug trong epic (42.5 HITL, E1 memory spike, regenerate 400) — fixture/log chứng minh root cause TRƯỚC khi fix, không đoán.
- **B3 cached aggregation:** `scrapers/health` chỉ đọc DB aggregate, không live-probe (sẽ làm xấu kênh đang rate-limit).

### Medirus contract facts (đã verify trong code, supersedes spine cũ)

- `dryRun:true` trả echo stub `"[dryRun] Scrape operation previewed..."` — KHÔNG scrape. Muốn data thật BẮT BUỘC `dryRun:false`.
- Stream mode (`REDIS_STREAM_ENABLED=true`) cắt `envelope.data` còn 10-item preview → phải gửi `fullData:true` để giữ data in-band.
- Medirus daemon port dev là `:3333` (spine ghi `:3001` — sai).
- `medirus_crawl_post` không phải tool thật → fallback duy nhất `medirus_scrape` với `{platform, action, args:{...}}`.

### Contract chi tiết đã pin trong AC

- **`ToolResultEnvelope`:** module `app/capabilities/core/tool_result.py` với `from_medirus(result)` + `from_exception(exc)`; hint map seed MEDIRUS_4001/4010/4030/5000 + default branch cho code lạ; `preview` ≠ `success` (dryRun stub không bao giờ trông giống executed).
- **`scrapers/health`:** `WHERE created_at >= now() - interval '24 hours' GROUP BY capability`; `success_rate_24h = attempts ? hits/attempts : null`; channel chưa chạy → `last_status:'unknown'`; auth workspace-scoped, filter `runs` theo `workspace_id` caller; response <200ms trên 10k runs (index `ix_runs_workspace_created`).
- **`leads.list` MCP:** `limit = max(1, min(limit or 50, 200))`, `offset >= 0`; `credits.balance` chỉ scope workspace caller, workspace không wallet → `{status:'failed', reason:'no_wallet'}`.
- **Auto-table:** `WorkspaceTable` get-or-create keyed `client_id` với `UNIQUE(workspace_id, key)` + `ON CONFLICT DO NOTHING` rồi re-select (race-safe); dangling `table_id` (table đã xóa) → recreate default + relink.
- **Step-cap partial:** khi hit `ModelCallLimitMiddleware run_limit=80`, force-synthesize partial + `partial: true` trong `status_marker`; synthesize lỗi → fallback notice-only; 0 tool results → "no tool calls completed" + `partial: true`; `status_marker` phải enumerate allowed values, consumer cũ ignore-unknown.
- **HITL:** cả approve LẪN reject path đều phải match `functionResponse` count với pending `functionCall` (reject → drop pending + emit `cancelled` functionResponse).
- **`NOWING_DEV_BYPASS_QUOTA`:** chỉ honor khi `settings.is_self_hosted == true` VÀ không phải production profile — prod self-hosted vẫn bị chặn; `DEBUG=true` KHÔNG tự động bypass; log warning khi active.
- **workspaceId propagation:** fix ở tool-wiring layer (`create_medirus_meta_tools` deps / registry), KHÔNG patch trong `_execute_medirus_tool` call; mọi MCP call gửi `{context: {workspaceId: <id>}}`.

### Non-Goals (không làm trong epic này)

- `CampaignSpec` supply-side (Epic 43); credential provisioning thật (FB cookie, YOUTUBE_API_KEY, Zalo/IG, Shopee proxy, Telegram relay) — chỉ surface recovery hints.
- Medirus daemon refactor (`mcp.sh` → `mcp_client.py` là job repo dainganxanh).
- `_prepare_lead_record` `contact_name` drop (fix riêng).
- E1 memory-spike fix KHÔNG thuộc epic — chỉ investigation lane nền; fix commit sau khi py-spy/tracemalloc có data (vẫn tuân AD-6).
- Deferred scope: single lock rule, single credit authority, config contract ports/env.

## Technical Decisions

- **Verify-don't-rebuild:** route `POST /api/v1/workspaces/{id}/leads/batch-ingest` (`app/routes/lead_batch_routes.py:118`, `RequirePermission(LEADS_WRITE)`) và PAT resolution (`get_auth_context` `app/users.py:336`, `AuthContext.pat_auth`) ĐÃ TỒN TẠI — story 42.1 là verify + harden, không viết lại. Tương tự `medirus_proxy` trong spec thực chất là `medirus_gateway.py`.
- **Envelope ở boundary-only:** không chuẩn hóa 3 schema executor/gateway/proxy — bọc adapter `ToolResultEnvelope` ở ranh giới tool→agent.
- **Hint map minimal:** seed đúng 4 code đã gặp thực tế, forward `suggestedAction` verbatim (đánh dấu untrusted), không viết từ điển cho lỗi chưa xảy ra.
- **Auto-table owner = `LeadBatchService`** (AD-1b), không phải tool layer — nếu gắn ở tool layer, REST/MCP path sẽ tái tạo orphan `table_id=NULL` (đã xảy ra: 109 leads mất hiển thị).
- **Embed-fail persistence:** document row vẫn commit với `unindexed: true` + `schedule_reindex`/backfill retry — không nằm unindexed mãi.
- **Quota bypass là dev-only:** `NOWING_DEV_BYPASS_QUOTA` chỉ cho local self-hosted non-prod testing; không phải fix cho `auto_pin_invalid` (single credit authority là deferred).
- **E1 memory spike (+700–900MB RSS/turn trên `stream_new_chat`)**: chạy py-spy/tracemalloc nền song song, không block epic; fix chỉ sau khi có data.

## UX & Interaction Patterns

- **Status badge 3 trạng thái** trên mọi tool/scrape result: `empty_result` (kênh sống, không data) / `degraded` (kèm `degraded_sources`) / `failed` (kèm recovery hint cụ thể — credential nào, ở đâu set, lệnh retest). KHÔNG BAO GIỜ render `data:[]` như "0 lead".
- **`/dashboard/{id}/leads` là route thật** (shareable, deep-link `?table=<id>`); `new-chat?mode=leads` redirect sang route mới, không 404 link cũ.
- **Step-cap partial:** banner "Đã xử lý N/M — gửi 'tiếp tục' để hoàn thành"; không bao giờ kết thúc turn `text=0`.
- **Dead-end phải có lối thoát:** regenerate trên thread crash → offer "Gửi như tin nhắn mới" thay vì 400.
- **Leads empty state** dạy cách săn lead (CTA chat + ví dụ query mẫu); mọi lead từ mọi nguồn tự gắn table — không có "lead vô chủ".
- **P1 external agent = service consumer:** UX của họ là contract + error hint, không phải trang web.

## Cross-Story Dependencies

- **42.1 ↔ 42.4:** cả hai dùng chung AD-1 funnel (`LeadBatchService.ingest_batch`) + AD-4 ingest contract — implement 42.1 trước để 42.4 wrap cùng validation/dedupe/attribution.
- **42.2 → 42.3:** `scrapers/health` dùng status semantics của `ToolResultEnvelope` (42.2 là nền cho B3).
- **42.2 → 42.4:** `nowing_mcp` tools phải emit cùng envelope contract.
- **42.5 ↔ 42.6:** cả hai là chat-turn resilience (Lane C) — độc lập về code nhưng cùng fixture/test infra (checkpoint-state, status_marker).
- **42.7 phụ thuộc AD-1b:** auto-table phải nằm trong `ingest_batch` nên về mặt kiến trúc gắn với 42.1; FE route + empty state độc lập.
- **42.8 độc lập** về code nhưng `MissingWorkspaceId` fix ảnh hưởng mọi Medirus stream call — nên verify cùng lúc với 42.2 envelope work.
- **Review findings đã patch vào spec:** 34 findings (12 adversarial + 16 edge-case + 6 structure) — các điểm contract-tightening quan trọng nhất đã nằm trong AC ở trên (batch-reject policy, race-safe idempotency, workspace-match guard, status_marker enumeration, quota-gate prod hole).
