# Epic 42 — Agent Experience & Lead Pipeline Hardening (Architecture Update)

Ngày: 2026-11-16 · Nguồn: `ux-plan-agent-experience-improvements-2026-11-16.md` (v4) + 2 case study trực tiếp (Pi trầm-hương session, Hermes daingan-ops). Bổ sung / sửa cho `architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md`.

## Sửa contract cũ trong spine (supersedes)

1. **AD-2 `x_scrape` dryRun semantics** — Spine ghi dryRun mặc định + stream-mode preview. Thực tế code (Medirus `src/mcp/server.js` `executeScrapeTool`): `dryRun:true` trả **echo stub không scrape** (`"[dryRun] Scrape operation previewed without executing network requests"`). Mọi executor/agent muốn data thật BẮT BUỘC `dryRun:false`.
2. **Stream-mode data contract** — Với `REDIS_STREAM_ENABLED=true`, `envelope.data` bị cắt còn 10-item `preview`. Medirus đã thêm top-level arg `fullData: true` → data giữ nguyên in-band (stream event vẫn publish). Nowing phải gửi `dryRun:false, fullData:true` (đã áp ở `medirus_proxy.py` + `medirus_gateway.py`).
3. **Medirus daemon port** — spine ghi `:3001`; dev hiện `:3333` (`MCP_TRANSPORT=http PORT=3333`). Xem config contract ở §11 plan (port drift từng gây login-loop).
4. **`medirus_crawl_post`** — không phải tool thật trên MCP server (Nowing gateway gọi tên này → `MEDIRUS_4002`/unlisted). Fallback duy nhất là `medirus_scrape` với contract `{platform, action, args:{...}}`.

## AD-42-1 — Lead-write funnel tại service layer (không phải tool layer)

Mọi ghi lead (REST ingest, `save_leads`, `multi_source_lead_gen`, script, `nowing_mcp`, websets import) đều đi qua `LeadBatchService.ingest_batch` — điểm duy nhất gắn DNC filter, `_reject_degenerate_leads`, HMAC dedup, Fernet encrypt. **Auto-table nằm trong service**: `table_id` vắng → get-or-create default `WorkspaceTable` keyed `client_id`. Gắn rule ở tool layer sẽ để REST/MCP path trả `table_id=NULL` → lead vô hình trên canvas (đã xảy ra: 109 lead mất hiển thị).

## AD-42-2 — PAT authz seam

Bypass `require_session_context` chỉ qua **một seam có tên** (PAT scope check hiện có — `test_pat_fail_closed_*`). Scope đầu tiên: `leads:write`. Bắt buộc: revocation/rotation contract, per-token audit attribution (PDPD cần biết ai push lead nào — ledger ghi `actor_pat_token_id`), không impersonation.

## AD-42-3 — Một `ToolResultEnvelope` xuyên mọi agent-facing boundary

`{status: success|empty_result|failed|degraded, reason, recovery_hint, items}` — schema duy nhất cho medirus_gateway, medirus_proxy, REST scrape endpoints và `nowing_mcp`. Home: `app/capabilities/core/tool_result.py` với `from_medirus(result)` + `from_exception(exc)`. DryRun/preview KHÔNG phải `success`. Hint map seeded từ MEDIRUS_4001/4010/4030/5000, forward `suggestedAction` gốc của Medirus.

## AD-42-4 — Ingest contract (external callers)

`POST /api/v1/workspaces/{id}/leads/batch-ingest` pin contract: idempotency key (header), validation ≥1 contact field per lead (`_reject_degenerate_leads` semantics), `client_id` semantic = campaign/source namespace, HMAC-conflict resolution = keep higher `fit_score`.

## AD-42-5 — Channel health = cached aggregate, không phải probe

`GET /api/v1/scrapers/health` chỉ đọc aggregate từ `runs` table (`capability`, `status`, `error`, `duration_ms`, `item_count`, 24h window). Không bao giờ fire live scrape — sẽ làm xấu các kênh đang rate-limit.

## AD-42-6 — Repro-before-fix

Correctness bugs (HITL `functionResponse` mismatch, memory spike +800MB/turn, regenerate 400) bắt buộc fixture/log repro trước khi fix — không đoán.

## Deferred invariants (named, chưa assign)

- **Single lock rule**: mọi workspace-scoped debit qua `pg_advisory_xact_lock` (đã áp ở `charge_capability`).
- **Single credit authority**: user-level vs workspace-level balance là hai nguồn truth gây `auto_pin_invalid`; `NOWING_DEV_BYPASS_QUOTA` chỉ là dev bypass, không phải fix.
- **Config contract**: FE/backend/zero-cache/Medirus port map (:3200/:4445/:4848/:3333) + `ZERO_QUERY_URL` phải resolve từ `docker/.env` — drift từng gây login-loop 401→429.
- **AD-5 CampaignSpec joint validation** (`direction × match_mode × corpus_scope × visibility` matrix) → Epic 43, pool gating sau `platform_b2b` corpus.

## Open investigation

- **E1 memory spike**: `stream_new_chat_END` +700–900MB RSS/turn trên backend — py-spy/tracemalloc trước khi fix. Chạy nền, không block epic.
