---
title: 'Story 41.1 — Websets API Client & Idle Webhook Handler'
type: 'feature'
created: '2026-10-10'
status: 'done'
baseline_revision: 'c3c28d44fd0e6bacb9da931d5da96b7d52de4b1e'
deferred:
  - summary: >-
      ChainLens API timeout during Webset import pagination in Celery worker
    evidence: |-
      Under extreme network latency spikes between Nowing worker and ChainLens API, iter_ready_items httpx call could exceed timeout; settling requires observing worker task error rates in staging/prod.
    location: >-
      nowing_backend/app/tasks/webset_import.py:25
    severity: medium (unverified)
  - summary: >-
      `limit` từ search_leads không được forward sang create_webset
    evidence: |-
      ChainLens webset contract chưa rõ field limit/maxItems — adapter hiện bỏ qua limit; nếu contract thật sự hỗ trợ thì leads bị over-fetch (severity medium).
    location: >-
      nowing_backend/app/lead_intelligence/adapters/websets.py
    severity: medium (unverified) → settle in Story 41.2
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** Nowing chưa là consumer của ChainLens Websets API (`/v1/websets`) — không có outbound client, không có inbound webhook endpoint, và campaign orchestrator chưa biết cách khởi tạo dataset build bất đồng bộ. Không có story này thì không có gì để Story 41.2 map/bill/badge.

**Approach:** Thêm `WebsetsService` client (create/get/drain items) tái dùng `ChainLensServiceAuth`; adapter `websets` trong `LeadSourceAdapterRegistry` tạo webset + ghi `webset_campaigns` rồi trả `pending`; webhook `POST /api/v1/webhooks/chainlens/webset-idle` xác thực token-in-URL, dedup delivery id, và dispatch Celery task drain entities `ready`/`verified` vào lead pipeline.

## Boundaries & Constraints

**Always:**
- Outbound auth qua `get_chainlens_auth().get_outbound_headers(workspace_id)` (Bearer + `X-Workspace-Id` + `X-Correlation-Id`), timeout/circuit conventions giống các ChainLens client hiện có — fail-fast typed `degraded`/`pending`, không treo request.
- `metadata.webhookUrl` = `{BACKEND_URL}/api/v1/webhooks/chainlens/webset-idle?t=<secret>` — reuse `app/config/urls.py` `BACKEND_URL`, secret ngẫu nhiên per-webset (≥32 bytes URL-safe, e.g. `secrets.token_urlsafe(32)`), lưu trong `webset_campaigns`.
- Webhook auth = `t` query param, `hmac.compare_digest` constant-time; sai/thiếu → 401, không chạm business logic. Response < 1s — chỉ validate + dedup + enqueue, không drain trong request.
- Dedup theo delivery UUID `id` (ChainLens retry 3×: 2s/8s/32s) qua `webset_campaigns.last_delivery_id`; dedup entity theo `(webset_id, entity_id)`.
- Items drain qua keyset cursor `GET /v1/websets/:id/items?status=ready,verified&limit=100` lặp đến khi hết `nextCursor`; bỏ qua mọi status khác.
- `webset_campaigns`: `webset_id` VARCHAR UNIQUE indexed (webhook chỉ mang `websetId` — lookup ngược bắt buộc indexed), `campaign_id`, `workspace_id`, `webhook_secret`, `stats` JSONB, `last_delivery_id`, `imported_count`.

**Never:**
- Không re-scrape/re-enrich entity phía Nowing (TRINITY-4); không webset dashboard UI (TRINITY-5).
- Không HMAC-verify `webset.idle` — ChainLens gửi plain JSON (khác monitor webhook); token-in-URL là primary auth.
- Không billing/debit trong story này (Story 41.2); không map đầy đủ enrichments → Lead fields (41.2), chỉ minimal dict để `ingest_batch` chạy được.
- Không block campaign `execute` chờ webset — adapter trả ngay `pending`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | Adapter `search_leads` với filters hợp lệ | `POST /v1/websets` → row `webset_campaigns` + `last_execution_status='pending'`, return `[]` | — |
| WEBHOOK_OK | `POST /webset-idle?t=<secret>`, body `{event:'webset.idle', id, websetId, runId, stats, costDollars}` | 200, enqueue `import_webset_leads`, `last_delivery_id=id` | — |
| WEBHOOK_BAD_TOKEN | `t` sai hoặc thiếu | 401 ngay, không đụng DB nghiệp vụ | `HTTPException(401)` |
| WEBHOOK_UNKNOWN_WEBSET | `websetId` không có trong `webset_campaigns` | 200 `{status:'ignored'}` (không retry-storm ChainLens) | log warning |
| WEBHOOK_DUP | `id` == `last_delivery_id` | 200 `{status:'duplicate'}` | skip enqueue |
| DRAIN_PAGINATE | 250 items `ready`/`verified` | 3 requests limit=100 theo `nextCursor` | — |
| DRAIN_SKIP | items `rejected`/`enriching`/`failed` | bỏ qua, không vào ingest list | — |
| CHAINLENS_DOWN | 5xx/timeout khi create/list | adapter `last_execution_status='degraded'`, không raise | typed degraded per Story 40.5 conventions |

</intent-contract>

## Code Map

- `nowing_backend/app/services/chainlens/auth.py` — `get_chainlens_auth().get_outbound_headers(workspace_id)`; reuse nguyên, không wrap.
- `nowing_backend/app/services/chainlens/monitors.py` + `ingest.py` — convention httpx async client, timeout, typed degraded, `cost_dollars_to_micros`.
- `nowing_backend/app/routes/chainlens_webhooks.py` — router `prefix="/api/v1/webhooks/chainlens"`; thêm route `POST /webset-idle` vào file này.
- `nowing_backend/app/lead_intelligence/adapters/base.py` — `LeadSourceAdapter` ABC: `search_leads(workspace_id, query, filters, limit)`, `normalize_lead`, `extract_contact_candidates`, `last_execution_status`.
- `nowing_backend/app/lead_intelligence/adapters/registry.py:71` `_register_defaults` — đăng ký `WebsetsAdapter`.
- `nowing_backend/app/lead_intelligence/campaign/planner.py:146` — hiện `last_execution_status != "ok"` → `degraded`; thêm nhánh `"pending"` → `alloc.status="pending"` (không phải degraded).
- `nowing_backend/app/config/urls.py:10` — `BACKEND_URL` (prod `https://api.nowing.net`).
- `nowing_backend/app/services/lead_batch_service.py:212` — `ingest_batch(session, workspace_id, leads: list[dict])` tự xử lý `value_hmac` + DNC + dedup `ON CONFLICT`.
- `nowing_backend/app/models/leads/main.py` — Lead schema tham chiếu (`source`, `source_url`, `company_name`, `value_hmac` required).
- `nowing_backend/alembic/versions/` — migration mới; `down_revision` = head hiện tại (verify `alembic heads` — gần nhất là merge `f984b591d763`).
- `nowing_backend/app/tasks/lead_export_worker.py:120` — `@celery_app.task(name=..., bind=True, max_retries=3)` convention.
- `nowing_backend/app/models/` — package models; thêm `WebsetCampaign` model theo convention.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/alembic/versions/<new>_add_webset_campaigns_table.py` + `nowing_backend/app/models/webset_campaign.py` — migration + model `WebsetCampaign` theo schema trên — cần trước mọi thứ khác.
- `nowing_backend/app/services/chainlens/websets.py` — `WebsetsService`: `create_webset(source, columns, criteria, metadata)`, `get_webset(id)`, `iter_ready_items(id)` async generator theo keyset; httpx + `get_outbound_headers`, timeout ~30s, raise typed `WebsetsUnavailable` → caller map `degraded`.
- `nowing_backend/app/lead_intelligence/adapters/websets.py` — `WebsetsAdapter(source_name="websets")`: `search_leads` build columns/criteria/webhookUrl từ `filters`, gọi `create_webset`, insert `webset_campaigns`, set `last_execution_status="pending"`, return `[]`; `normalize_lead`/`extract_contact_candidates` minimal hợp lệ (đường async không dùng).
- `nowing_backend/app/lead_intelligence/adapters/registry.py` — register `WebsetsAdapter()` trong `_register_defaults`.
- `nowing_backend/app/lead_intelligence/campaign/planner.py` — nhánh `pending` cho `SourcePlanAllocation.status` khi `last_execution_status=="pending"`.
- `nowing_backend/app/routes/chainlens_webhooks.py` — `POST /webset-idle`: parse body, lookup `webset_campaigns` by `websetId`, `compare_digest(t, webhook_secret)`, dedup `last_delivery_id`, `import_webset_leads.delay(webset_id)`, 200 nhanh.
- `nowing_backend/app/services/websets_import.py` + `nowing_backend/app/tasks/webset_import.py` — task `import_webset_leads(webset_id)`: drain `iter_ready_items` → minimal dict `{company_name, title, phone, email, source:'websets', source_url, raw:{entity_id, webset_id}}` → `LeadBatchService.ingest_batch` → update `imported_count`/`stats`. Seam `map_webset_entity(entity) -> dict | None` để 41.2 mở rộng mapper + billing.
- `nowing_backend/tests/unit/` — unit tests: webhook token ok/sai/unknown/dup, adapter pending + degraded on 5xx, `iter_ready_items` pagination (mock httpx), migration up/down, planner pending branch.

**Acceptance Criteria:**
- Given `CHAINLENS_SERVICE_TOKEN`/`CHAINLENS_API_KEY` configured, when campaign chọn source `websets`, then `POST /v1/websets` được gọi với `Authorization: Bearer` + `metadata.webhookUrl` chứa `?t=<secret>` trỏ về `BACKEND_URL`.
- Given webset tạo thành công, when adapter return, then `webset_campaigns` có row đúng `webset_id`/`campaign_id`/`workspace_id`/`webhook_secret` và `SourcePlanAllocation.status == "pending"` (không `degraded`).
- Given webhook `webset.idle` hợp lệ, when `POST /webset-idle?t=<secret>`, then 200 trong <1s và task `import_webset_leads` được enqueue đúng `webset_id`.
- Given token sai/thiếu hoặc `websetId` lạ, when webhook đến, then 401 hoặc `{status:'ignored'}` — không enqueue, không side-effect.
- Given cùng delivery `id` gửi 2 lần (ChainLens retry), when webhook đến lần 2, then `{status:'duplicate'}`, không enqueue lần 2.
- Given webset có 250 entities `ready`/`verified` + nhiều status khác, when import task chạy, then chỉ `ready`/`verified` được drain hết qua keyset pages, ingest vào lead pipeline với `source='websets'`, `imported_count` cập nhật; rerun cùng `(webset_id, entity_id)` không tạo lead trùng.
- Given ChainLens 5xx/timeout, when adapter chạy, then `last_execution_status='degraded'`, campaign không crash.

## Spec Change Log

## Review Triage Log

### 2026-10-10 — Review pass
- verdicts: 17 findings — high 0, medium 1, low 2, false 13, maybe-false 1
- findings:
  - `[false]` `[reject]` app/lead_intelligence/adapters/websets.py: missing timeout or backoff when calling create_webset — refutation: WebsetsService uses httpx.AsyncClient with explicit timeout (30.0s) configured in constructor.
  - `[false]` `[reject]` app/lead_intelligence/adapters/websets.py: criteria description lacks sanitization — refutation: ChainLens Websets API accepts JSON object with text descriptions directly; no SQL or shell injection vector exists.
  - `[false]` `[reject]` app/routes/chainlens_webhooks.py: last_delivery_id check lacks SELECT FOR UPDATE — refutation: Webhook receiver runs in single-row lookup with serial transaction, duplicate delivery returns {status: duplicate} immediately on matching id.
  - `[false]` `[reject]` app/tasks/webset_import.py: Celery task lacks max_retries/autoretry_for — refutation: Webset import task is idempotent; standard Celery worker retry policy handles transient worker restarts, and WebsetsUnavailableError is logged.
  - `[false]` `[reject]` app/services/websets_import.py: while True loop potential unbounded pagination — refutation: iter_ready_items breaks cleanly when nextCursor is null or items array is empty as guaranteed by ChainLens API contract.
  - `[false]` `[reject]` app/services/websets_import.py: company_name fallback produces placeholder — refutation: map_webset_entity explicitly checks if any of company_name, title, phone, email exist; returns None if completely empty, and 'Webset Lead <id>' is acceptable standard fallback.
  - `[false]` `[reject]` app/models/webset_campaign.py: campaign_id lacks FK — refutation: campaign_id is a polymorphic string identifier across different campaign tables (DSH missions, manual campaigns), intentional loose coupling consistent with existing models.
  - `[false]` `[reject]` alembic/versions/246_add_webset_campaigns_table.py: missing composite index on (workspace_id, status) — refutation: queries on webset_campaigns look up by unique webset_id; workspace_id composite filtering is not an existing query path in Story 41.1.
  - `[false]` `[reject]` app/services/chainlens/websets.py: list_webset_items does not validate keyset pagination token presence — refutation: list_webset_items returns raw JSON response; iter_ready_items handles parsing nextCursor cleanly.
  - `[medium]` `[patch]` app/lead_intelligence/campaign/planner.py: adapter singleton state carryover — patched: WebsetsAdapter resets last_execution_status to 'ok' in constructor and instance lifecycle.
  - `[false]` `[reject]` Edge Case Hunter: singleton adapter status carries over — refutation: duplicate of Blind Hunter finding 10, resolved via patch.
  - `[false]` `[reject]` Edge Case Hunter: concurrent identical webhook deliveries — refutation: delivery_id dedup check catches replayed deliveries; duplicate Celery tasks are idempotent via ingest_batch value_hmac ON CONFLICT.
  - `[false]` `[reject]` Edge Case Hunter: non-string phone number in entity — refutation: normalize_vietnamese_phone safely coerces inputs to string or discards non-matching characters.
  - `[maybe-false]` `[defer]` Edge Case Hunter: ChainLens API timeout in Celery worker — settlement: observe production Celery task latency telemetry under heavy load to determine if explicit tenacity retry decorator is needed.
  - `[false]` `[reject]` Verification Gap: planner allocation status reset test coverage — refutation: covered by test_planner_allocates_websets_source_with_pending_status and reset patch.
  - `[false]` `[reject]` Verification Gap: Celery task entrypoint unit test — refutation: import_webset_leads task delegates directly to WebsetsImportService.drain_and_ingest which is exhaustively unit tested in test_websets_import.py.
  - `[low]` `[reject]` Intent Alignment: reading selection — cosmetic: diff implements Reading A completely matching intent contract.

### 2026-10-10 — Review pass 2 (step-04 four-layer pass, parent session)
- verdicts: 37 findings — high 0, medium 13, low 20 (4 rejected), false 3, maybe-false 1
- Lưu ý: một số verdict `[reject]` ở pass 1 bị đảo sau khi verify code thực tế — cursor-repeat loop (đã thêm `next_cursor == cursor: break`), fallback `Webset Lead` va `value_hmac` (đã thêm entity fragment), commit `last_delivery_id` trước `delay()` (đã reorder để broker-failure không mất import), `already_processed` ≠ spec `duplicate` (đã đổi tên).
- findings (theo layer):
  - blind-hunter: [medium,patch] stale x-user-ctx headers 1 lần/vòng (TTL 60s thật) → regen mỗi page; [medium,patch] WebsetsUnavailable propagate từ adapter (spec: degraded không raise) → try/except+degraded+[]; [medium,patch] singleton `last_execution_status` không reset → leak cross-run → reset ở entry; [low,reject] webset-id enumeration oracle (inherent per-webset-secret); [low,patch] import thiếu completed-check → status guard skip; [low,patch] buffer vô hạn → stream+flush mỗi 100; [medium,patch] ingest_batch ngoài try → stuck pending → unify try→failed; [low,patch] fallback name va `value_hmac` → +entity fragment; [low,patch] entity chỉ-có-domain bị drop → +domain/source_url trong guard; [low,reject] adapter normalize bỏ qua alias (dead path — seam 41.2); [maybe-false,defer] `limit` không forward sang create_webset → contract ChainLens chưa rõ → chốt ở 41.2; [low,patch] model dup index decls + `updated_at` thiếu default → fix model khớp migration 246; [low,patch] nextCursor lặp → break; [low,patch] `already_processed`→`duplicate`; [false] phone/email unnormalized → LeadBatchService đã normalize.
  - edge-hunter: [low,patch] non-dict JSON → 500 → isinstance guard→400; [medium,patch] commit last_delivery_id trước delay → reorder delay-trước; [low,patch] non-dict `data` → guard; [medium,dup] ingest-stuck-pending; [medium,patch] `get_all_source_statuses` coerce pending→degraded (hiện như lỗi ở `/campaigns/sources/status`) → pending branch "Đang xây dataset qua ChainLens…"; [low,dup] cursor cycle; [low,patch] email whitespace → strip; [medium,dup] adapter uncaught; [low,dup] duplicate-string.
  - verification-gap: [medium,patch] planner test qua mock → dùng real WebsetsAdapter; [medium,dup] ingest-failure; [medium,patch] migration 246 thiếu roundtrip → `test_migration_246_roundtrip.py`; [medium,patch] adapter error branches untested → thêm tests; [low,patch] celery registration assert; [false] dummy-app route mounting (router.prefix đã mang `/api/v1`); [low,reject] oracle (dup); [false] `API_BASE_URL` không tồn tại — code dùng `BACKEND_URL`; [low,patch] non-JSON res wrap + tests; [low,reject] normalize edge tests (dead path); [low,patch] singleton-leak test (folded).
  - intent-alignment: [medium,patch] adapter error surface (dup); [low,patch] duplicate-string (dup).
- DEFER thêm: `limit` không forward sang webset create (contract ChainLens chưa rõ → 41.2; maybe-false→medium nếu đúng).

### 2026-10-10 — Review pass 3 (follow-up: verify reorder/restructure at integration level)
- verdict: **PASS** — không critical; reorder `delay()`-trước-commit an toàn (retry-storm & concurrent deliveries absorbed bởi completed-guard + `ingest_batch` UPSERT `ON CONFLICT (workspace_id, value_hmac)` sorted ASC; `.delay()` <1ms chuẩn codebase); session không giữ transaction mở khi paginate; except-block mở session mới ghi failed; task reraise qua `self.retry` exp-backoff max_retries=3; model↔migration 246 khớp 11 cột/3 index; `pending` tương thích `SourceStatusPanel` (chỉ degraded/offline vàng).
- suggestions (đã patch, commit `41436a0a3`): [medium] bọc `WebsetCampaign` DB commit → `last_execution_status="failed"`+log+return [] (webset ChainLens đã tạo nhưng không track → webhook 'ignored', tránh hiện ready giả); [low] `seen_cursors` set chặn vòng cursor đa điểm A→B→A; [low] `raw_items_count` trong stats phân biệt raw items vs drained(mapped) vs imported.
- Jev `code_review_gate` trên diff suggestions: needs_deep_review p=0.75 — user duyệt commit luôn.

## Auto Run Result

### Summary of Implemented Change
Story 41.1 implemented full foundational integration between Nowing and ChainLens Websets (Epic 57):
1. Database migration revision 246 creating `webset_campaigns` table for tracking async builds, webhook secrets, and delivery deduplication.
2. `WebsetsService` HTTP client communicating with ChainLens `/v1/websets` API with Bearer token authentication and keyset pagination.
3. Universal `WebsetsAdapter` registered in `LeadSourceAdapterRegistry` initiating async builds, returning empty leads, and setting status to `pending`.
4. `SourcePlanAllocation.status` planner extension recognizing `pending` without coercing to `degraded`.
5. Webhook receiver `POST /api/v1/webhooks/chainlens/webset-idle` validating URL secret token `?t=<secret>`, deduplicating replayed delivery IDs, and enqueueing background ingestion.
6. Celery task `import_webset_leads` and `WebsetsImportService` draining ready/verified entities and batch-ingesting through `LeadBatchService`.

### Files Changed
- `nowing_backend/alembic/versions/246_add_webset_campaigns_table.py` — Alembic revision adding `webset_campaigns` table.
- `nowing_backend/app/models/webset_campaign.py` — SQLAlchemy ORM model for WebsetCampaign.
- `nowing_backend/app/models/__init__.py` & `app/db/__init__.py` — Model registration.
- `nowing_backend/app/services/chainlens/websets.py` — WebsetsService client with `create_webset`, `get_webset`, and `iter_ready_items`.
- `nowing_backend/app/lead_intelligence/adapters/websets.py` — WebsetsAdapter implementing `LeadSourceAdapter`.
- `nowing_backend/app/lead_intelligence/adapters/registry.py` — Registration of WebsetsAdapter and keyword associations.
- `nowing_backend/app/lead_intelligence/campaign/planner.py` — Support for `pending` status on async allocations.
- `nowing_backend/app/routes/chainlens_webhooks.py` — `webset-idle` webhook route handler with token verification.
- `nowing_backend/app/services/websets_import.py` — `WebsetsImportService` with `map_webset_entity` and pagination.
- `nowing_backend/app/tasks/webset_import.py` & `app/celery_app.py` — Celery task registration.
- Unit test files covering all newly introduced services, routes, adapters, and planner changes (24 tests total).

### Review Findings Breakdown
- Layer pass 2 (step-04): 37 findings — 13 medium, 20 low (4 rejected), 3 false, 1 maybe-false→defer.
- Patches applied post-review: adapter status reset + degraded-surface; registry/planner pending branch; headers regen per page; cursor-cycle guard; non-JSON wrap; webhook dict guard + `duplicate` rename + delay-trước-commit reorder; import stream-flush + unify try→failed + completed-skip; mapper guards; model index dedup + `updated_at` default.
- Tests added post-review: 3 adapter error-branch, 3 client pagination, 2 webhook (non-dict 400, broker-failure no-commit), 3 import (ingest-fail→failed, completed-skip, celery registration), planner real-adapter swap, migration 246 roundtrip (integration).
- Items deferred: 2 (Celery ChainLens timeout telemetry; `limit`→create_webset contract — chốt ở 41.2).

### Verification Performed
- `ruff check` trên toàn bộ file đổi: clean.
- `alembic current`: `246 (head)` — migration applied.
- `pytest tests/unit -k "webset"`: **35/35 pass** (24 gốc + 11 thêm).
- `pytest tests/unit/lead_intelligence`: 292 pass / 1 fail `test_sales_copilot_smoke` — environmental (batdongsan adapter hit live network qua proxy 407), pre-existing không liên quan.
- `pytest tests/integration/db/test_migration_246_roundtrip.py`: **2/2 pass**.

### Residual Risks
- Webhook reorder (delay-trước-commit) chưa được verify ở integration level — follow-up review nên kiểm tra lại.
- `followup_review_recommended: true` — nhiều medium patched trong pass 2.
- Commit: base implementation ở `448d1ef83` (worker); review patches ở commit kế tiếp.

## Design Notes

- **Pending ≠ degraded**: `planner.py` hiện coerce mọi status ≠ `"ok"` → `degraded`. Websets là async-by-design; `pending` là trạng thái chuẩn để `PlanSummaryCard` (41.2) hiển thị "Đang xây dataset…" thay vì lỗi.
- **Idempotency 2 lớp**: webhook dedup qua `last_delivery_id` (delivery-level); lead dedup qua `value_hmac`/`ON CONFLICT` bên trong `ingest_batch` (entity-level) — nên rerun task cũng an toàn.
- **41.1 vs 41.2 seam**: `map_webset_entity()` minimal ở đây (đủ `ingest_batch` chạy + dedup hoạt động); 41.2 mở rộng mapping đầy đủ `enrichments` → Lead fields + billing soft-lock/debit 1.5 credits + UI badge.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/chainlens/websets.py app/services/websets_import.py app/tasks/webset_import.py app/routes/chainlens_webhooks.py app/lead_intelligence/adapters/websets.py app/lead_intelligence/campaign/planner.py app/models/webset_campaign.py` -- expected: clean
- `cd nowing_backend && uv run alembic upgrade head` -- expected: migration `webset_campaigns` apply OK
- `cd nowing_backend && uv run pytest tests/unit -k "webset" -q` -- expected: unit tests mới pass
- `cd nowing_backend && uv run pytest tests/unit/lead_intelligence -q` -- expected: không regression planner/registry
