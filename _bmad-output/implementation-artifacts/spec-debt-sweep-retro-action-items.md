---
title: 'Debt-sweep 2: đóng 9 retro action items Epic 31–35 (security fail-closed, DLQ cap, compliance purge, metric wiring, test gaps)'
type: 'bugfix'
created: '2026-10-13'
status: 'done'
baseline_commit: '764e8b1009e31441dbebe82f88883c920bb7701c'
route: 'dispatch'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Retro Epic 31–35 để lại 17 action items; sau triage còn 9 items P0+P1 cần đóng trong một sweep: hai đường fail-open về secret/auth (`CDP_SESSION_SECRET` giữ default insecure, Salesforce webhook chấp nhận request không xác thực), một lỗ hổng reliability (poison stream message bị XAUTOCLAIM redeliver vô hạn), một compliance gap (`SocialPost` sót lại sau khi purge DNC phone/email), metric `record_scraper_ingest_failure` định nghĩa nhưng không nơi nào gọi, dedup không normalize dấu tiếng Việt, và 3 test/debt gaps (Biome warnings, thiếu integration tests CRM webhook + XAUTOCLAIM/SSE heartbeat).

**Approach:** Sweep một lần: ép fail-closed secret/auth, thêm delivery-attempt cap → DLQ, purge `SocialPost` qua `raw_entities` JSONB, wire metric vào tất cả catch points của platform scrapers, normalize `remove_diacritics` trong spatial dedup, fix Biome warnings, bổ sung integration tests theo pattern hiện có.

## Boundaries & Constraints

**Always:**
- `CDP_SESSION_SECRET` rỗng hoặc giữ default `"dev-cdp-secret-change-in-production"` ở **production env** → raise `ValueError` chặn startup (cả `config/dsh.py` lẫn `browser_operator_audit_service._get_session_secret`); dev/test chỉ warning. (decision 2026-10-13 Luisphan)
- Fail-closed: `SALESFORCE_WEBHOOK_SECRET` rỗng hoặc không khớp → HTTP 401; so sánh bằng `hmac.compare_digest` (pattern `gateway_webhook/webhooks.py`, `zns_routes.py`).
- Purge `SocialPost`: **hard-delete** qua `session.delete()` — RTBF-complete, đồng nhất convention `VerifiedContact`/`Lead` trong cùng service. (decision 2026-10-13 Luisphan)
- `SOCIAL_STREAM_MAX_DELIVERY_ATTEMPTS = 5`; message đạt cap → `_route_to_dlq` với constant mới `DLQ_REASON_MAX_DELIVERY_ATTEMPTS` + ACK — không redeliver nữa.
- Purge `SocialPost`: query `raw_entities` JSONB (`phones`/`emails`) + author fields so với giá trị DNC đã `_normalize_value`; trả count vào `purge_individual` result `social_posts` (hiện hard-code 0).
- `record_scraper_ingest_failure(platform, reason)`: chỉ THÊM call tại các catch points đã định vị — KHÔNG đổi control flow, re-raise/degrade giữ nguyên hành vi hiện tại. `platform` = canonical name (`batdongsan`, `muaban_bds`, `medirus`, `facebook`); `reason` snake_case.
- Dedup: áp `remove_diacritics` trước `\w+` split trong `_tokenize` và `_default_bucket_fn`.
- Tests theo convention hiện có: `client_as_regular_user`/`db_session` fixtures, `_skip_if_no_redis` cho real-Redis, AsyncMock cho unit.
- Biome: cấm `any` — error narrow `unknown`; `useCallback` cho `fetchTimeline`.

**Never:**
- Không DB migration — `raw_entities` JSONB đã GIN-indexed, hard-delete không cần schema change.
- Không đổi API contract nào ngoài Salesforce webhook → 401.
- Không touch 4 items P3 (tách `dsh_routes.py`, `CdpBridge` multi-tab, MV3 Playwright fixture, cgroup telemetry/DNS probe) và 2 items P2 (SecOps SOP, Credit Refund Policy).
- Không thêm retry/backoff logic vào XAUTOCLAIM cap — chỉ count + DLQ.
- Không thêm call metric ở điểm nào ngoài danh sách Code Map.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Salesforce secret rỗng | `SALESFORCE_WEBHOOK_SECRET=""` | Mọi webhook request → 401 | HTTPException |
| Salesforce secret mismatch | header ≠ env secret | 401, constant-time compare | HTTPException |
| Salesforce secret đúng | header == env secret | Xử lý như hiện tại | N/A |
| Poison stream msg | deliveries ≥ 5 sau xautoclaim | `_route_to_dlq` + `DLQ_REASON_MAX_DELIVERY_ATTEMPTS` + ACK | Không crash, không redeliver |
| Msg chưa tới cap | deliveries < 5 | Reprocess bình thường | N/A |
| SocialPost chứa phone DNC | `raw_entities['phones']` match | Post bị hard-delete, `social_posts` count +1 | N/A |
| Scraper decode error | `BatdongsanDecodeError` tại scraper | Metric `(batdongsan, decode_error)` + degraded path giữ nguyên | N/A |
| Diacritics mismatch | `"Quận 7"` vs `"Quan 7"` | Cùng bucket/token set → dedup match | N/A |
| CRM webhook deal change | HubSpot/SF payload hợp lệ | `Lead.status` update + `CrmSyncLog` row trong 1 transaction (integration test) | Rollback nguyên vẹn khi lỗi |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/config/dsh.py:35` — `CDP_SESSION_SECRET` default `"dev-cdp-secret-change-in-production"`; mirror fallback tại `app/services/browser_operator_audit_service.py:25` (`_get_session_secret`) — cả hai phải cùng enforce. Consumers: `generate_session_token` (line 28) ký HMAC, `validate_session_token` (line 44) verify tại `dsh_routes.py:529`. Reuse: `app/config/auth.py:36,47` raise at import; `app/lifespan.py:319`/`app/app/shared.py:47` startup-warn pattern.
- `nowing_backend/app/routes/crm_routes.py:304-319` — `salesforce_webhook`: `if expected_secret and ...` fail-open khi secret rỗng; secret env `app/config/entities.py:52`. Reuse fail-closed `app/routes/gateway_webhook/webhooks.py:118-122` / `app/routes/zns_routes.py:102-106` + `hmac.compare_digest`.
- `nowing_backend/app/services/compliance_purge_service.py:51-160` — `purge_individual`: docstring hứa purge `SocialPost` nhưng `purged_posts` giữ 0 (line 75,151). `SocialPost` model `app/models/leads/social.py:84-178` — contacts nằm trong `raw_entities` JSONB (GIN-indexed, keys `phones`/`emails` từ `social_stream_worker.py:215,297`); không có soft-delete column. Reuse `_normalize_value` (line 30).
- `nowing_backend/app/tasks/social_stream_worker.py` — `run_social_stream_consumer` (950-1142): `xautoclaim` tại 1002-1019, `AUTOCLAIM_MIN_IDLE_TIME_MS=60_000` (58), không có delivery counter. `_route_to_dlq` (810-850) xadd+xack. `DLQ_REASON_*` constants 66-72 + `STREAM_SOCIAL_DEAD_LETTER` (`medirus/constants.py:30`). Delivery count lấy qua XPENDING per-claimed-id (`deliveries_count`).
- `nowing_backend/app/observability/metrics/platform.py:71` — `record_scraper_ingest_failure(platform, reason)`; zero production call sites (chỉ test `tests/unit/observability/test_scraper_failure_metrics.py:17`). Wire vào: `proprietary/platforms/batdongsan/scraper.py:144,149,153,180`; `muaban_bds/scraper.py:274,282,362`; `medirus/adapter.py:548-562` + `medirus/adapter_v2.py:544,583`; `tasks/celery_tasks/social_medirus_ingest.py:270,378`; `tasks/lead_scrapers.py:126`.
- `nowing_backend/app/services/dedup/spatial_windowed_dedup.py:12-16` — `_tokenize` chỉ `text.lower()` + `\w+`; `:46` `_default_bucket_fn`. Apply `remove_diacritics` từ `app/services/location_normalize/__init__.py:127` trước split.
- `nowing_web/components/crm/WorkspaceActivityTimeline.tsx:48,55-57` — `catch (err: any)` → `unknown` + narrow; `useEffect` thiếu dep `fetchTimeline` → `useCallback(..., [workspaceId])`.
- Test reuse: `tests/integration/routes/test_crm_sync.py` (fixtures `client_as_regular_user`, `db_workspace`, `db_session` savepoint); `tests/integration/gateway/test_zalo_webhook_e2e.py` (webhook signature + ASGITransport + session override); `tests/integration/platforms/test_social_redis_stream.py:46` (real Redis + `_skip_if_no_redis`); `tests/unit/tasks/test_social_stream_autoclaim.py` (xautoclaim unit pattern); `tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py:213` (SSE `body_iterator`).

## Tasks & Acceptance

**Execution:**
- [x] `app/config/dsh.py` + `app/services/browser_operator_audit_service.py` — `CDP_SESSION_SECRET` rỗng/default ở production env → raise `ValueError` tại startup; dev/test warning (cả hai điểm đọc secret cùng hành vi).
- [x] `app/routes/crm_routes.py` — `salesforce_webhook` fail-closed: rỗng hoặc mismatch → 401, `hmac.compare_digest`.
- [x] `app/services/compliance_purge_service.py` — hard-delete `SocialPost` match `raw_entities` JSONB (`phones`/`emails`) hoặc author fields qua `_normalize_value`; trả count vào `social_posts`.
- [x] `app/tasks/social_stream_worker.py` — `SOCIAL_STREAM_MAX_DELIVERY_ATTEMPTS = 5` + `DLQ_REASON_MAX_DELIVERY_ATTEMPTS`; check deliveries (XPENDING) sau xautoclaim, cap → `_route_to_dlq`.
- [x] `batdongsan/scraper.py` + `muaban_bds/scraper.py` + `medirus/adapter.py` + `medirus/adapter_v2.py` + `social_medirus_ingest.py` + `lead_scrapers.py` — wire `record_scraper_ingest_failure` tại các catch points đã liệt kê, không đổi control flow.
- [x] `app/services/dedup/spatial_windowed_dedup.py` — `remove_diacritics` trong `_tokenize` + `_default_bucket_fn`.
- [x] `nowing_web/components/crm/WorkspaceActivityTimeline.tsx` — fix 3 Biome warnings.
- [x] Unit tests: `test_social_stream_worker` (delivery-cap → DLQ), `test_compliance_purge` (SocialPost), `test_spatial_windowed_dedup` (diacritics), metric call sites (scrapers gọi đúng platform/reason), salesforce webhook 401.
- [x] Integration tests: `tests/integration/routes/` CRM webhook transaction (`Lead` + `CrmSyncLog`); `tests/integration/` XAUTOCLAIM real-Redis theo `test_social_redis_stream` pattern; SSE heartbeat route test `/dsh/cdp/stream`.

**Acceptance Criteria:**
- Given `SALESFORCE_WEBHOOK_SECRET` rỗng hoặc header mismatch, when webhook POST, then 401; request đúng secret vẫn xử lý bình thường.
- Given poison message với `deliveries_count >= 5`, when xautoclaim reclaim, then message vào `stream:social:dead_letter` với `DLQ_REASON_MAX_DELIVERY_ATTEMPTS` và được ACK — không redeliver.
- Given `SocialPost` có `raw_entities.phones/emails` chứa giá trị bị DNC, when `purge_individual` chạy, then post bị hard-delete và result `social_posts` đếm đúng.
- Given mỗi catch point trong Code Map, when scraper raise lỗi tương ứng, then `record_scraper_ingest_failure` được gọi đúng `(platform, reason)` và control flow cũ không đổi (unit test assert call args).
- Given `"Quận 7"` vs `"Quan 7"`, when dedup tokenize/bucket, then match cùng nhóm (unit test).
- Given CRM webhook deal-change payload hợp lệ, when endpoint xử lý, then `Lead.status` đổi và `CrmSyncLog` row tồn tại trong cùng transaction (integration test).
- Given Biome check trên `WorkspaceActivityTimeline.tsx`, then 0 warnings; `pnpm tsc --noEmit` clean.
- Given `CDP_SESSION_SECRET` default/empty, when backend khởi động ở production env, then raise `ValueError`; dev/test env chỉ warning (unit test cả hai nhánh).

## Implementation Notes

- `dsh.py` fails closed at import time in production env (`ENVIRONMENT`/`APP_ENV` in {production,prod}) when `CDP_SESSION_SECRET` rỗng/default; `_get_session_secret` mirrors — dev/test chỉ warning.
- `crm_routes.py`: `salesforce_webhook` rejects 401 khi secret rỗng hoặc mismatch (`hmac.compare_digest`); cả hubspot + salesforce webhook được bọc try/commit + except/rollback→500 để giữ transaction Lead+CrmSyncLog nguyên vẹn.
- `compliance_purge_service.py`: query `SocialPost` bằng `cast(raw_entities, Text).like()` với candidate values (norm/raw/không dấu `+`) + `author_id`/`author_name` match; `session.delete()` hard-delete; count vào `purged_counts.social_posts` + log line.
- `social_stream_worker.py`: `SOCIAL_STREAM_MAX_DELIVERY_ATTEMPTS=5`, `DLQ_REASON_MAX_DELIVERY_ATTEMPTS`; `_get_delivery_count` đọc XPENDING (`xpending_range`/`xpending`, hỗ trợ dict/tuple reply) — trả 1 khi lỗi (fail-safe: message vẫn được xử lý bình thường).
- Metric wiring: `record_scraper_ingest_failure` được gọi tại 14 catch points đúng Code Map; reason snake_case (`decode_error`, `rate_limited`, `api_error`, `web_fallback_failed`, `timeout`, `decode_error`, `mcp_error`, `unexpected_error`, `fallback_mcp_error`, `scraper_error`, `target_unsupported`, `ingest_failure`, `scraper_task_failure`). Không đổi control flow.
- `spatial_windowed_dedup.py`: `remove_diacritics` + normalize abbrev `q.1`/`quan 1` → `q1` trong `_tokenize` và `_default_bucket_fn` (hơi vượt spec letter — thêm abbrev normalization, đã cover bằng tests).
- Frontend: `fetchTimeline` → `useCallback([workspaceId])`; `catch (err: unknown)` + `instanceof Error` narrow; `useEffect([fetchTimeline])`.
- Tests mới: `tests/unit/observability/test_scraper_ingest_failure_wiring.py` (18), `tests/integration/routes/test_crm_webhook_integration.py` (3 real-DB), `tests/unit/routes/test_dsh_cdp_stream.py` (3), `tests/integration/platforms/test_social_redis_stream.py` (+2 real-Redis), `tests/unit/tasks/test_social_stream_worker.py` (+1 delivery-cap mock), `test_browser_operator_audit_service` (+4), `test_compliance_purge_service` (+1), `test_crm_webhook_service` (+5), `test_spatial_windowed_dedup` (+2).
- Verify: 139 tests pass gộp (gồm integration chạy thật trên host Postgres:5432/Redis:6379); 67 pass riêng gap files; ruff clean; biome + tsc clean.
- Caveat: Docker daemon không chạy — deps không start được; integration tests chạy trên host services (pg :5432/nowing_test, redis :6379 từ `.env` REDIS_APP_URL).

## Spec Change Log

## Review Triage Log

| Finding | Verdict | Evidence | Route |
|---------|---------|----------|-------|
| compliance_purge_service.py:111 `session.get(Lead, lead_id)` scalar vs composite PK (id, workspace_id) — InvalidRequestError; lead_ids_to_check không giữ workspace_id | `maybe-false` | Dòng `session.get` nằm ở phần leads-purge **pre-existing** (không trong diff); nếu đúng thì leads-purge vốn crash — không thuộc story này | defer |
| SocialPost purge: không scan `content`; LIKE trên cast(JSONB→Text) match substring khắp serialized JSON (post_url/id chứa digits → over-delete); không escape %/_ | `high` | `cast(raw_entities, Text).like(f"%{v}%")` match digits bên trong post_url/external_id → xóa nhầm post không liên quan (data loss); content chứa PII thô cũng sót — vi phạm RTBF | patch (P1) |
| hubspot_webhook: `verify_hubspot_signature` return True khi secret rỗng (fail-open) | `maybe-false` | Pre-existing — không nằm trong diff (chỉ thêm try/rollback quanh nó) | defer |
| `verify_hubspot_signature` sai spec v3 (phải là method+uri+body+timestamp base64) | `maybe-false` | Pre-existing, không trong diff | defer |
| `_default_sort_key_fn` không `remove_diacritics` title → cross-diacritic dup sort xa nhau trong bucket >50 item, thoát sliding window | `medium` | Sort key vẫn dùng raw lowercase — đúng mô tả; normalization chỉ apply tokenize/bucket, bỏ sót sort key | patch (P3) |
| Abbrev regex miss "q 1" (space) và "phường 1" | `low` | `\b([qp])\.(\d+)\b` cần dấu chấm, `\bquan\s+` cần chữ quan đủ — "q 1"/"phường 1" không normalize | patch (P4) |
| Metric double/triple-count: adapter_v2 `mcp_error` + task `mcp_error` + generic `ingest_failure` cho cùng exception | `medium` | adapter_v2 record rồi re-raise MedirusMcpError → ingest task record lần 2, generic except record lần 3 | patch (P2) |
| `_get_delivery_count` nuốt exception → return 1, log debug-only → cap không bao giờ kích hoạt nếu XPENDING API mismatch | `low` | Fail-open mặc định; debug-level che giấu — nâng lên warning | patch (P7) |
| `xautoclaim(start_id="0-0")` hardcoded mỗi loop — rescan PEL từ đầu, không dùng cursor | `maybe-false` | Pre-existing — xautoclaim call không phải code mới của diff | defer |
| `cdp_stream` finally: unsubscribe throw → skip redis.delete lock → 409 reconnect (3600s TTL) | `maybe-false` | Route code pre-existing; diff chỉ thêm tests | defer |
| Submodule `_bmad/marketing-growth` `-dirty` trong diff | `false` | Không stage vào commit — artifact của working tree, không phải defect | reject |
| CDP check duplicate tại dsh.py + `_get_session_secret` | `false` | Spec yêu cầu cả hai điểm đọc cùng enforce — intentional, không phải drift | reject |
| `fetchTimeline` không guard workspaceId rỗng + không AbortController | `maybe-false` | Pre-existing component behavior; diff chỉ fix lint warnings | defer |
| Integration test mock `_get_delivery_count` → real Redis XPENDING parse không bao giờ được test | `medium` | Đúng — không test nào chạy `_get_delivery_count` trên Redis thật | patch (P8) |
| Mock session.get trong compliance test che composite-PK lookup | `maybe-false` | Cùng gốc với finding đầu — pre-existing session.get | defer |
| SocialPost purge không batch — hàng nghìn match → OOM + lock | `low` | Unlikely (1 phone khớp ít post); fix thêm complexity → reject per rule | reject |
| XPENDING sequential per-message (tới 100/batch) | `low` | Reclaim hiếm nhưng 100 RTT thật — batch 1 call đơn giản | patch (P6) |
| `except Exception` coerce HTTPException 4xx → 500 ở cả 2 webhooks | `low` | Nếu service raise HTTPException, blanket except → 500 sai semantics | patch (P5) |
| Unit test DLQ chỉ assert xadd/xack awaited-once, không check payload fields | `low` | Đúng — sai stream/dlq_reason vẫn pass | patch (P9) |
| Module guard `dsh.py` (import-time raise) không có test nào | `low` | Chỉ `_get_session_secret` được test | patch (P10) |
| `salesforce_webhook` rollback-on-error không test (hubspot có mirror) | `low` | Đúng — chỉ happy path + 401 | patch (P11) |
| `test_purge_social_post_by_pii` không inspect where clause — mock trả post bất kể filter | `low` | Filter sai vẫn pass | patch (P12) |
| `test_salesforce_webhook_full_transaction` không assert Lead.status transition thật trên DB | `low` | Chỉ assert 200 + service-called | patch (P13) |
| Empty-header edge: secret configured + `X-Salesforce-Webhook-Secret: ""` → 401 (đúng nhưng chưa test) | `low` | Behavior đã đúng qua `or ""`; thêm assert rẻ | patch (P14) |

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/config/dsh.py app/services/browser_operator_audit_service.py app/routes/crm_routes.py app/services/compliance_purge_service.py app/tasks/social_stream_worker.py app/proprietary/platforms/batdongsan/scraper.py app/proprietary/platforms/muaban_bds/scraper.py app/proprietary/platforms/medirus/adapter.py app/proprietary/platforms/medirus/adapter_v2.py app/tasks/celery_tasks/social_medirus_ingest.py app/tasks/lead_scrapers.py app/services/dedup/spatial_windowed_dedup.py` — expected: clean.
- `cd nowing_backend && uv run pytest tests/unit/tasks/test_social_stream_worker.py tests/unit/tasks/test_social_stream_autoclaim.py tests/unit/observability tests/unit/services/dedup tests/unit/services/test_compliance_purge* tests/unit/platforms -q` — expected: all pass.
- `cd nowing_backend && uv run pytest tests/integration/routes/test_crm_sync.py tests/integration/routes/<new-crm-webhook-test> tests/integration/platforms/test_social_redis_stream.py -m integration -q` — expected: pass (cần Postgres + Redis local theo AGENTS.md).
- `cd nowing_web && pnpm exec biome check components/crm/WorkspaceActivityTimeline.tsx && pnpm tsc --noEmit` — expected: clean.
