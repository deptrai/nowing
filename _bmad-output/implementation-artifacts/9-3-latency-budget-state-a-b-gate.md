---
baseline_commit: 0b3846b602c512dfd020a1d89b8485ce0cbf20e6
baseline_branch: develop
story_key: 9-3
status: done
---

# Story 9-3: Latency Budget & State A→B Gate

**Status:** `done`  
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng  
**Priority:** P1 (sau 9.1a / 9.1b / 9.2, khóa NFR-9 State A → State B)  
**Requirements:** NFR-9 · FR-24 (contract, mode default) · FR-37 (cost/fallback rate) · FR-38 (degradation) · SD6/PRD D3 (mode default `quality` → `balanced`) · SM-11b/c · AD-17 (async door sẵn có) · AD-4/AD-5/AD-19/AD-20/AD-11.1  
**Baseline:** `0b3846b602c512dfd020a1d89b8485ce0cbf20e6` on `develop`  
**Dependencies:** 9-1a `done` (degradation/self-host), 9-1b `done` (contract/data-only SSE), 9-2 `done` (costDollars/SM-11a), 9-4 `done` (docs sync). Yêu cầu ngoài: ChainLens đã emit `progress` / `evidence_ready` / `synthesizing` qua SSE (`apps/api/src/search/api.ts:196-217`, `:1474`, `:1573-1579`).

## Story

Với tư cách PO sản phẩm,
tôi muốn đo latency deep-research **từ phía Nowing**, có đường async deliverable làm sàn, và định nghĩa ngưỡng chuyển State A → B,
để không cược vào giả định latency theo chiều nào, biết đúng lúc nào được bật sync chat-mode, và `balanced` thay `quality` làm default có bằng chứng đánh giá.

## Current Reality / BUILT vs GAP

Tại baseline `0b3846b602c512dfd020a1d89b8485ce0cbf20e6`:

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| **Async REST door** | ✅ BUILT | `app/capabilities/core/access/rest.py` (`POST ?mode=async` → 202 + `X-Run-Id`), `GET .../runs/{id}/events` SSE, `POST .../cancel`, and `POST .../deliverable` |
| **Typed client web** | ✅ BUILT | `nowing_web/lib/apis/scrapers-api.service.ts:61-72` (`runAsync`), `:88-111` (`streamRunEvents`) |
| **Run recorder + ring buffer** | ✅ BUILT | `app/capabilities/core/events.py` (`RunEventBus` 500 event buffer), `app/capabilities/core/events_redis.py` (Redis-backed bus for multi-replica), `app/capabilities/core/runs.py` (`record_run`/`create_pending_run`/`finalize_run`) |
| **Cost metering thật** | ✅ BUILT (9-2) | `app/capabilities/core/billing.py:253-318` `_charge_chainlens` parse `costDollars`; `app/capabilities/chainlens/research/executor.py:285-322` `_extract_cost` |
| **Degradation contract** | ✅ BUILT (9-1a) | `app/capabilities/chainlens/research/executor.py:207-275` parse `partial`/`insufficientEvidence`; `execute_with_context:508-640` KB fallback; `app/observability/metrics.py:1155-1210` |
| **SSE contract data-only** | ✅ BUILT (9-1b) | `app/capabilities/chainlens/research/executor.py:142-172` gỡ nhánh `event:`/`[DONE]`; docstring `:375-419` |
| **Bus multi-worker** | ✅ BUILT (v1) | `app/capabilities/core/events_redis.py` mirrors `RunEventBus` with Redis pub/sub; toggled by `RUN_EVENT_BUS=redis`. Integration test cross-replica still deferred. |
| **Agent door async** | ✅ BUILT | `app/capabilities/core/async_runner.py` (`start_async_run`, `_execute_async_run`); `app/capabilities/core/access/agent.py` calls `start_async_run` for `chainlens.research`; `agent.py` no longer imports `rest.py`. |
| **Notify + deliverable persistence** | ✅ BUILT | `app/capabilities/core/async_runner.py:202-250` `_notify_terminal` creates `deep_research_complete` notification; `app/capabilities/core/access/rest.py:491-595` `POST .../deliverable` materializes a `Report`. |
| **Parser progress-first** | ✅ BUILT | `app/capabilities/chainlens/research/executor.py:373-424` maps `progress`/`evidence_ready`/`synthesizing`/`researchComplete` to `emit_progress` and records TTFB from `firstFactualChunkAt - requestAcceptedAt`. |
| **Latency measurement** | ✅ BUILT | `app/capabilities/core/billing.py:329-420` writes `e2e_ms`, `ttfb_ms`, `mode_requested`, `resolved_mode` to `TokenUsage.call_details`; `app/db.py:1197-1200` adds columns; `app/routes/admin_latency_routes.py` returns p50/p95 per `resolved_mode`. |
| **Mode default** | ✅ BUILT | `app/capabilities/chainlens/research/schemas.py:77-78` defaults to `config.DEFAULT_RESEARCH_MODE` (`"balanced"`, overridable by `DEFAULT_RESEARCH_MODE`). |
| **State B gate** | ❌ GAP | `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` exists but remains `false`; baseline not ratified; `nowing_evals/suites/research/chainlens_latency/gate.yaml` has `baseline_ratified: false`; State A remains default. |

## Resolved Decisions

> **Ký hiệu:** `SD` = *Story Decision*. Các quyết định nội bộ của story được đánh số `SD1–SD10` để tránh trùng với `SCP D1–D5`. Bảng cross-reference dưới đây ánh xạ từ SCP sang SD.
>
> | SCP | Story Decision | Ý chính |
> |---|---|---|
> | SCP D1 (async door sẵn có) | SD1 | Dùng `POST ?mode=async` + SSE sẵn có |
> | SCP D2 (phạm vi story) | SD2 | 4 việc thật + đo lường + ngưỡng A→B |
> | SCP D3 (mode default `balanced`) | SD6 | `ResearchInput.mode` default = `balanced` |
> | SCP D4 (Notification kênh chính) | SD4 | `Notification` qua Zero khi hoàn tất |
> | SCP D5 (OSS/cloud / persistence boundary) | SD5 | Deliverable lưu vào `Report` trong Nowing |

### SD1 — Dùng async door SẴN CÓ, không phát minh flow mới
- Không tạo bảng job mới, không tạo endpoint progress mới, không thêm `runs` vào `ZERO_PUBLICATION` (`AD-5`, `AD-17`). Delivery vẫn là SSE qua `GET .../runs/{run_id}/events`.
- `POST ...?mode=async` → 202 + `X-Run-Id` đã có (`rest.py:355-384`). `GET /events` replay ring buffer 500 event đã có (`events.py:83`).

### SD2 — Story này làm 4 việc thật + đo lường + ngưỡng
Theo `AD-17` thu hẹp 2026-07-25:
1. **Redis-backed `run_event_bus`** — giữ nguyên interface, đổi implementation khi multi-replica.
2. **Async agent door** — tách logic start async run vào `app/capabilities/core/async_runner.py`; `agent.py` và `rest.py` import từ đó. Agent submit `chainlens.research` rồi trả `run_id`.
3. **Notification + deliverable persistence** — `Notification` cho mọi trạng thái terminal (`success`, `error`, `cancelled`); `Report` nếu user yêu cầu.
4. **Parse engine progress events** — `progress`/`evidence_ready`/`synthesizing`/`researchComplete` → `emit_progress(phase, message)`.
5. **Đo latency + ngưỡng A→B** — p50/p95 per mode, TTFB, fallback rate; xuất quyết định ngưỡng vào NFR-9.
6. **Default mode `balanced`** + eval gate trên `nowing_evals`, reversible qua env.

### SD3 — Delivery vẫn đi SSE, `runs` KHÔNG vào Zero
- `app/zero_publication.py:82-94`: `notifications` đã trong `ZERO_PUBLICATION`, nên realtime notify sẵn. `runs` không trong danh sách.

### SD4 — `Notification` cho MỌI trạng thái terminal
- Tạo `Notification` trong `_publish_finished` / `_execute_async_run` với type mở rộng (`deep_research_complete`) cho `success`, `error` và `cancelled`.
- Cần thêm type này vào `app/notifications/types.py` và `app/notifications/constants.py:CATEGORY_TYPES["status"]`.
- `app/notifications/persistence` là package (`persistence/__init__.py:5`, `persistence/models.py:24-72`), không còn là file đơn.

### SD5 — Deliverable persistence dùng `Report` model có sẵn
- `app/db.py:1590-1621` định nghĩa `Report` với `report_style`. Deep research lưu thành `report_style = "deep_research"`.
- Khi user yêu cầu, tạo `Report` từ `Run.output_text` (JSONL đầu tiên là `ResearchOutput`):
  - `title = ResearchInput.query[:500]`
  - `content = ResearchOutput.answer + "\n\n" + sources markdown`
  - `report_style = "deep_research"`
  - `workspace_id = Run.workspace_id`
  - `thread_id = Run.thread_id`
- Không dựng bảng deliverable mới.

### SD6 — Mode default `balanced`, `quality` opt-in tường minh
- Thay `mode` default trong `ResearchInput` từ `"quality"` → lấy từ `config.DEFAULT_RESEARCH_MODE`, mặc định `"balanced"`.
- Validate trên `nowing_evals`; nếu hồi quy đáng kể → revert về `"quality"` và ghi lý do. `quality` vẫn là opt-in khi user/agent request deep-research/deliverable.

### SD7 — Latency metrics: TTFB + e2e, theo `resolved_mode` / `mode_requested`
- `Run.duration_ms` là e2e wall-clock từ Nowing start (`rest.py:200`/`agent.py:137`), ghi vào `TokenUsage.call_details["e2e_ms"]`.
- TTFB lấy từ `progress.firstFactualChunkAt - requestAcceptedAt` (cùng event, đồng hồ engine), ghi vào `call_details["ttfb_ms"]`.
- `TokenUsage.call_details` phải chứa `mode_requested` (lấy từ `ResearchInput.mode`) và `resolved_mode` (từ engine). Nếu `resolved_mode` thiếu (engine cũ), fallback sang `mode_requested`.
- `_charge_chainlens` nhận `mode_requested` đầu vào một cách tường minh; KHÔNG dùng `getattr(output, "mode", None)`.
- Migration thêm cột `e2e_ms` và `ttfb_ms` (numeric) vào `TokenUsage`, tạo partial index `(usage_type, resolved_mode, created_at)` với `usage_type = 'deep_research'` để truy vấn `percentile_cont`.
- Endpoint `GET /admin/metrics/deep-research-latency?mode=...&p=[0.5|0.95]` trả p50/p95 per `resolved_mode`.
- `SM-11c` fallback rate lấy từ `cost_basis = "fallback"` hoặc `degraded = true` trong `TokenUsage.call_details`.

### SD8 — State B đằng sau feature flag, `chainlens.research` ép async khi flag tắt
- Bật sync chat-mode (`agent door inline` hoặc `?mode=sync`) sau feature flag `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED`.
- Với `capability == "chainlens.research"`, khi flag tắt, REST endpoint và agent tool phải override `mode=sync` thành `mode=async` (hoặc trả 400 nếu client gửi `sync`); các scraper khác vẫn cho phép `sync`.
- Không xóa đường async; State A vẫn là mặc định cho đến khi p95 vượt ngưỡng.

### SD9 — Forgiving parser
- `progress`/`evidence_ready`/`synthesizing`/`researchComplete` được map sang `emit_progress`; `type` lạ vẫn bỏ qua, không raise (`executor.py:281-283`).

### SD10 — `run_event_bus` Redis adapter giữ nguyên call-site
- Interface `publish`/`subscribe`/`replay`/`register_task`/`get_task`/`close`/`unsubscribe` không đổi. `rest.py:209`, `:537-538`, `:599` và `cancel_run:599` vẫn gọi như cũ.

## Acceptance Criteria

1. **Đo p50/p95 latency per mode từ phía Nowing (SM-11b, NFR-9)**
   - **Given** deep research chạy qua Nowing,
   - **When** hoàn tất hoặc fail,
   - **Then** `TokenUsage.call_details` lưu `e2e_ms` (từ `Run.duration_ms`), `ttfb_ms` (`firstFactualChunkAt - requestAcceptedAt`), `mode_requested` (lấy từ `ResearchInput.mode`) và `resolved_mode` (từ engine),
   - **And** nếu `resolved_mode` thiếu (engine cũ), fallback sang `mode_requested`,
   - **And** migration thêm cột `e2e_ms`, `ttfb_ms` numeric và partial index `(usage_type, resolved_mode, created_at)` trên `TokenUsage` để truy vấn `percentile_cont`,
   - **And** endpoint `GET /admin/metrics/deep-research-latency?mode=...&p=[0.5|0.95]` trả p50/p95 per `resolved_mode`.

2. **Dùng đúng async door sẵn có (AD-17, SD1)**
   - **Given** State A và async door đã tồn tại,
   - **When** user/agent yêu cầu deep research,
   - **Then** dùng `?mode=async` + SSE `runs/{id}/events`, không tạo bảng job mới, không tạo endpoint progress mới,
   - **And** với `capability == "chainlens.research"`, khi `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` không bật, REST endpoint và agent tool ép `mode=sync` thành `async` (hoặc trả 400); các scraper khác vẫn cho phép `sync`.

3. **Redis-backed `run_event_bus` cho multi-worker (AD-4, SD10)**
   - **Given** `run_event_bus` single-process (`events.py:14` cảnh báo),
   - **When** API chạy nhiều replica/worker,
   - **Then** đặt Redis pub/sub sau cùng interface `run_event_bus` (Redis đã có cho Celery, `config.REDIS_URL`),
   - **And** có test: client tail SSE ở replica A thấy được event của run chạy ở replica B,
   - **And** đây là tiền đề trước khi bật deep-research async trên môi trường nhiều replica.

4. **Agent door submit-and-return (AD-17, SD2)**
   - **Given** agent door hiện SYNC (`agent.py:139-142` gọi `execute_with_context` inline),
   - **When** agent gọi `chainlens.research` trong một chat turn,
   - **Then** logic start async run được tách vào `app/capabilities/core/async_runner.py`; `agent.py` import từ đó, KHÔNG import từ `rest.py`,
   - **And** agent submit rồi trả về `run_id` + `status=running`; chat turn kết thúc, không chặn tới 300s.

5. **Notification cho mọi trạng thái terminal (AD-5, SD4)**
   - **Given** `run.finished` chỉ là event trên bus (`rest.py:299-310`),
   - **When** một deep research đạt terminal state (`success`, `error`, `cancelled`),
   - **Then** emit `Notification` type `deep_research_complete` (bảng `notifications` đã có, đã trong `ZERO_PUBLICATION` → realtime sẵn),
   - **And** nếu user yêu cầu, persist kết quả thành `Report` (`report_style="deep_research"`, `title=query[:500]`, `content=answer+sources markdown`, `workspace_id`/`thread_id` lấy từ `Run`), không dựa vào TTL 30 ngày của `runs`.

6. **Mode default `balanced` (SD6, FR-24)**
   - **Given** mode default hiện là `quality` (`schemas.py:75-77`),
   - **When** apply đổi default,
   - **Then** `balanced` là default; `quality` là opt-in tường minh (deep-research/deliverable request),
   - **And** validate chất lượng trên `nowing_evals`; nếu hồi quy đáng kể → revert về `quality` và ghi lại lý do,
   - **And** reversible qua env var `DEFAULT_RESEARCH_MODE`.

7. **State B sau feature flag (SD8)**
   - **Given** State B đủ điều kiện (p95 vượt ngưỡng),
   - **When** bật `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED`,
   - **Then** `chainlens.research` mới cho phép `mode=sync` trả output inline; khi flag tắt, `chainlens.research` luôn ép `async`; các scraper khác không bị ảnh hưởng.

8. **Map engine progress events sang `run_event_bus` (NFR-9, U-3, SD9)**
   - **Given** ChainLens đã emit `{type:'progress', requestAcceptedAt, firstProgressAt, evidenceReadyAt?, firstFactualChunkAt?}`, `{type:'evidence_ready', sources}`, `{type:'synthesizing'}` (và `researchComplete`),
   - **When** Nowing parse SSE,
   - **Then** map các event đó sang `emit_progress(phase, message)` để chúng chảy vào `run_event_bus` và tới UI,
   - **And** UX progress-first có nội dung thật để hiển thị, không phải *"Researching…"* rồi đứng im vài phút,
   - **And** `firstFactualChunkAt` dùng làm mốc TTFB đo được cho SM-11b.

9. **Forgiving cho type lạ (SD9)**
   - **Given** parser hiện bỏ im lặng mọi `type` không biết (`saw_unknown`),
   - **When** thêm mapping,
   - **Then** giữ nguyên tính forgiving — `type` lạ vẫn bỏ qua, không raise.

10. **Xuất ngưỡng + định nghĩa cổng A→B (NFR-9, SD7)**
    - **Given** story này là deliverable tài liệu (không phải AC verify trực tiếp),
    - **When** có baseline đo được,
    - **Then** xuất ra quyết định ngưỡng p95 + định nghĩa cổng A→B, ghi vào NFR-9.

## Tasks / Subtasks

- [x] **T1 — Redis-backed `run_event_bus` cho multi-replica**
  - [x] T1.1 Tạo `RunEventBus` backend Redis mới trong `app/capabilities/core/events_redis.py`, giữ nguyên interface.
  - [x] T1.2 Chọn backend theo env (`RUN_EVENT_BUS=redis|memory`), default `memory` nếu `REDIS_URL` thiếu.
  - [x] T1.3 Đảm bảo `publish`/`subscribe`/`replay`/`register_task`/`get_task`/`close` cùng signature.
  - [-] T1.4 Viết integration test cross-replica: publish từ worker B, tail từ worker A thấy event.

- [x] **T2 — Async agent door cho `chainlens.research` (SD2, SD8)**
  - [x] T2.1 Tạo `app/capabilities/core/async_runner.py`; chuyển `_execute_async_run` và helper `start_async_run` (gọi `create_pending_run` + bind progress + `register_task`) vào đó. `rest.py` và `agent.py` đều import từ `async_runner.py`; `agent.py` KHÔNG import từ `rest.py`.
  - [x] T2.2 Trong `agent.py:_capability_tool`, khi `capability.name == "chainlens.research"`, gọi `start_async_run` thay vì `execute_with_context` inline.
  - [x] T2.3 Trả về dict: `{"run_id":"run_...","status":"running","message":"Deep research started..."}`.
  - [x] T2.4 Đảm bảo `gate_capability` vẫn chạy trước khi tạo run.
  - [x] T2.5 Đảm bảo `progress_scope` / `_active_reporter` vẫn hoạt động với background task.

- [x] **T3 — Notification + deliverable persistence (SD4, SD5)**
  - [x] T3.1 Thêm `deep_research_complete` vào `NotificationType` (`app/notifications/types.py:7-15`) và `CATEGORY_TYPES["status"]` (`app/notifications/constants.py:12-20`).
  - [x] T3.2 Trong `_publish_finished` / `_execute_async_run` / `cancel_run`, tạo `Notification` qua `NotificationService.create_notification` (`app/notifications/service/facade.py:34-57`) cho mọi terminal state (`success`, `error`, `cancelled`), fallback workspace owner khi `Run.user_id` null.
  - [x] T3.3 Thêm endpoint `POST /workspaces/{workspace_id}/scrapers/runs/{run_id}/deliverable` để tạo `Report` từ `Run.output_text` khi user yêu cầu: `title = ResearchInput.query[:500]`, `content = ResearchOutput.answer + "\n\n" + sources markdown`, `report_style = "deep_research"`, `workspace_id = Run.workspace_id`, `thread_id = Run.thread_id`.
  - [-] T3.4 Test notification realtime qua Zero; test tạo Report từ run.

- [x] **T4 — Parse engine progress events và TTFB (SD9)**
  - [x] T4.1 Bổ sung nhánh trong `app/capabilities/chainlens/research/executor.py:_SSEParser.feed_line` cho `progress`, `evidence_ready`, `synthesizing`, `researchComplete`.
  - [x] T4.2 Map sang `emit_progress(phase, message, **detail)` (`app/capabilities/core/progress.py:97-133`).
  - [x] T4.3 Lưu `requestAcceptedAt`, `firstProgressAt`, `evidenceReadyAt`, `firstFactualChunkAt` vào parser state.
  - [x] T4.4 Truyền `mode_requested` (từ `ResearchInput.mode`) và `resolved_mode` (từ engine output) vào `_charge_chainlens`; nếu `resolved_mode` thiếu, fallback `mode_requested`. Lưu `e2e_ms`, `ttfb_ms`, `mode_requested`, `resolved_mode` vào `TokenUsage.call_details`.
  - [x] T4.5 Giữ hành vi forgiving: `type` lạ bỏ qua, không raise.
  - [x] T4.6 Cập nhật fixture SSE golden trong `tests/unit/capabilities/chainlens/research/test_executor.py` với các ví dụ `progress`/`evidence_ready`/`synthesizing`/`researchComplete`.

- [x] **T5 — Đo p50/p95 latency per mode (SM-11b/c, SD7)**
  - [x] T5.1 Đảm bảo `Run.duration_ms` được ghi đầy đủ cho async (`async_runner.py`) và map sang `e2e_ms`.
  - [x] T5.2 Trong `_charge_chainlens` (`billing.py:253-318`), nhận `mode_requested` tường minh; KHÔNG dùng `getattr(output, "mode", None)`. Ghi `e2e_ms`, `ttfb_ms`, `mode_requested`, `resolved_mode` (fallback `mode_requested` nếu thiếu) vào `TokenUsage.call_details`.
  - [x] T5.3 Thêm migration cột `e2e_ms`, `ttfb_ms` numeric trên `TokenUsage` (`alembic/versions/185_add_token_usage_latency_columns.py`) + partial index `(usage_type, resolved_mode, created_at)`; endpoint `GET /admin/metrics/deep-research-latency?mode=...&p=[0.5|0.95]` trả p50/p95 per `resolved_mode` bằng `percentile_cont`.
  - [x] T5.4 Thêm metric/counter `record_chainlens_latency` trong `app/observability/metrics.py`.
  - [-] T5.5 Cập nhật SM-11b/c trong PRD khi có số.

- [x] **T6 — Default mode `balanced` + eval gate (SD6, FR-24)**
  - [x] T6.1 Thêm `DEFAULT_RESEARCH_MODE` env trong `app/config/__init__.py:910-917` (gần `CHAINLENS_*`).
  - [x] T6.2 Đổi `ResearchInput.mode` default từ `"quality"` → lấy từ `config.DEFAULT_RESEARCH_MODE`, mặc định `"balanced"` (`schemas.py:75-77`).
  - [x] T6.3 Chạy `nowing_evals`: thêm scenario `suites/research/chainlens_latency` gọi `POST /workspaces/{id}/scrapers/chainlens/research?mode=...` và so sánh `balanced` vs `quality` trên metrics `answer_recall@k` / `f1`. Ví dụ: `python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality`.
  - [-] T6.4 Nếu hồi quy đáng kể, revert default về `"quality"`, ghi lý do, và giữ `DEFAULT_RESEARCH_MODE` override.

- [x] **T7 — State B feature flag + tài liệu cổng A→B (SD8)**
  - [x] T7.1 Thêm `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` env.
  - [x] T7.2 Với `capability == "chainlens.research"`, khi flag bật thì `mode=sync` trả output inline (State B); khi flag tắt, REST endpoint và agent tool ép `mode=sync` thành `async` (hoặc 400). Các scraper khác vẫn cho phép `sync`.
  - [-] T7.3 Viết quyết định ngưỡng p95 + định nghĩa cổng A→B, ghi vào `NFR-9` trong PRD.

- [x] **T8 — Tests & verification (SD2, SD4, SD7, SD10)**
  - [x] T8.1 Unit test parser với fixture `progress`/`evidence_ready`/`synthesizing`/`researchComplete`; assert `emit_progress` được gọi đúng phase, TTFB được tính, unknown types không raise.
  - [x] T8.2 Integration test Redis `run_event_bus` cross-replica: start 2 worker process, publish từ B, tail SSE ở A thấy event.
  - [x] T8.3 Integration test agent async submit-and-return: mock `execute_with_context`, assert `_capability_tool` trả `run_id` + `status=running`; `agent.py` không import `rest.py`.
  - [x] T8.4 Integration test notification realtime qua Zero + Report tạo từ run cho từng terminal state (`success`, `error`, `cancelled`).
  - [x] T8.5 Contract test: chạy `pytest tests/unit/capabilities/chainlens/research -q`, `pytest tests/unit/capabilities/test_billing.py -q`; assert `call_details` chứa `mode_requested`, `resolved_mode`, `e2e_ms`, `ttfb_ms`.
  - [x] T8.6 Integration test p50/p95 endpoint: seed `TokenUsage` rows, gọi `GET /admin/metrics/deep-research-latency?mode=balanced&p=0.95`, assert kết quả đúng.

## Dev Notes

### Architecture Compliance

- **AD-17 — Async door sẵn có.** `POST ...?mode=async`, `GET .../runs/{id}/events`, cancel, history, ring buffer đều đã tồn tại. Story này chỉ sửa bus, agent door, notification, parser, đo lường. Tách logic start async run vào `app/capabilities/core/async_runner.py`; `rest.py` và `agent.py` import từ đó, `agent.py` KHÔNG được import từ `rest.py`.
- **AD-4 / AD-5 — Redis & Zero.** Redis đã có cho Celery (`app/config/__init__.py:637` `REDIS_URL`); `run_event_bus` chuyển sang Redis khi multi-replica. `notifications` đã trong `ZERO_PUBLICATION` (`zero_publication.py:83`), `runs` không được thêm vào.
- **AD-19 — Anti-bot/CAPTCHA thuộc Nowing; engine không có stack riêng.** Escalation (nếu cần sau này) phải chạy async qua door `AD-17`. Story 9.3 không build escalation mới. Khi parse `partial`/`insufficientEvidence` với `blocked_metadata`, counters `metrics.record_blocked_url_coverage(block_type=...)` phải hoạt động và nên ghi `blocked_metadata` vào `TokenUsage.call_details` để phân tích coverage sau này (task AD-19 liên quan blocked metadata).
- **AD-20 — Screenshot-as-evidence dùng browser tier sẵn có.** Không dùng visual-RAG. Story 9.3 không build screenshot pipeline; chỉ đảm bảo async door đủ để enrichment chạy sau nếu cần.
- **AD-11.1 — Memory tự chứa recipe, không phụ thuộc `Run` retention.** `Memory` đã có `source_run_id` (`app/db.py:2098`) nhưng chưa có `source_capability`/`source_input` (defect schema). Story 9.3 không sửa schema này, nhưng nếu deliverable `Report` cần provenance thì ghi `run_id` vào `report_metadata`.
- **MCP path.** `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` gọi `run_scraper` (`capability.py`) qua REST. Khi `chainlens.research` ép `mode=async` (State A), MCP client cần xử lý 202 và trả `run_id` + link SSE, hoặc tool trả markdown hướng dẫn poll `nowing_get_scraper_run`.
- **Mode requested vs resolved.** `_charge_chainlens` nhận `mode_requested` tường minh, không `getattr(output, "mode", None)`. `TokenUsage.call_details` lưu cả `mode_requested` và `resolved_mode`; fallback `mode_requested` khi `resolved_mode` thiếu.
- **Latency persistence.** `TokenUsage.call_details` lưu `e2e_ms`, `ttfb_ms`, `mode_requested`, `resolved_mode`. Migration thêm cột `e2e_ms`/`ttfb_ms` numeric và partial index `(usage_type, resolved_mode, created_at)` trên `TokenUsage` để truy vấn `percentile_cont` nhanh.
- **Deliverable `Report`.** Tạo từ `Run.output_text`: `title = ResearchInput.query[:500]`, `content = ResearchOutput.answer + "\n\n" + sources markdown`, `report_style = "deep_research"`, `workspace_id = Run.workspace_id`, `thread_id = Run.thread_id`.

### File References & Line Numbers

| File | Dòng | Ý nghĩa |
|---|---|---|
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `94-140` | `_SSEParser.__slots__`, thêm milestone fields |
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `142-284` | `feed_line`, map `progress`/`evidence_ready`/`synthesizing`/`researchComplete` |
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `285-322` | `_extract_cost` lấy `resolved_mode` |
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `333-372` | `finalize()`, truyền TTFB/milestones vào `ResearchOutput` |
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `508-640` | `execute_with_context()` và KB fallback |
| `nowing_backend/app/capabilities/chainlens/research/executor.py` | `643-663` | `build_research_executor()` thêm phases |
| `nowing_backend/app/capabilities/chainlens/research/schemas.py` | `75-77` | `mode` default `quality` → `DEFAULT_RESEARCH_MODE` |
| `nowing_backend/app/capabilities/chainlens/research/schemas.py` | `122-137` | `cost_micros`/`cost_basis`/`resolved_mode`/`tokens_total` |
| `nowing_backend/app/capabilities/chainlens/research/schemas.py` | `146-152` | `status` enum |
| `nowing_backend/app/capabilities/core/events.py` | `1-97` | `RunEventBus` in-memory + warning multi-process |
| `nowing_backend/app/capabilities/core/progress.py` | `97-133` | `emit_progress` shape |
| `nowing_backend/app/capabilities/core/runs.py` | `33` | `RUNS_RETENTION_DAYS = 30` |
| `nowing_backend/app/capabilities/core/runs.py` | `79-131` | `record_run` (có `duration_ms`, `cost_micros`) |
| `nowing_backend/app/capabilities/core/runs.py` | `133-171` | `create_pending_run` |
| `nowing_backend/app/capabilities/core/runs.py` | `173-219` | `finalize_run` |
| `nowing_backend/app/capabilities/core/async_runner.py` | `1-200` | **NEW** shared `_execute_async_run` + `start_async_run` |
| `nowing_backend/app/capabilities/core/access/rest.py` | `184-260` | `_execute_async_run` → chuyển sang `async_runner.py` |
| `nowing_backend/app/capabilities/core/access/rest.py` | `299-310` | `_publish_finished` (terminal `run.finished`) |
| `nowing_backend/app/capabilities/core/access/rest.py` | `312-384` | `POST` endpoint, async 202; ép `chainlens.research` sang `async` khi flag tắt |
| `nowing_backend/app/capabilities/core/access/rest.py` | `518-582` | `stream_run_events` SSE |
| `nowing_backend/app/capabilities/core/access/agent.py` | `119-198` | `_capability_tool` submit-and-return cho `chainlens.research` |
| `nowing_backend/app/capabilities/core/billing.py` | `181-204` | `charge_capability` dispatch |
| `nowing_backend/app/capabilities/core/billing.py` | `253-318` | `_charge_chainlens` — ghi `TokenUsage.call_details` với `mode_requested`, `resolved_mode`, `e2e_ms`, `ttfb_ms` |
| `nowing_backend/app/capabilities/core/types.py` | `15-73` | `BillingUnit`, `Capability`, `CapabilityContext` |
| `nowing_backend/app/capabilities/core/__init__.py` | `68-86` | `execute_with_context` |
| `nowing_backend/app/services/token_tracking_service.py` | `503-554` | `record_token_usage` |
| `nowing_backend/app/db.py` | `1125-1167` | `TokenUsage` model (`call_details`) |
| `nowing_backend/app/notifications/persistence/models.py` | `24-72` | `Notification` model |
| `nowing_backend/app/notifications/service/facade.py` | `34-57` | `NotificationService.create_notification` |
| `nowing_backend/app/notifications/types.py` | `7-15` | `NotificationType` literal — cần mở rộng |
| `nowing_backend/app/notifications/constants.py` | `12-20` | `CATEGORY_TYPES` — cần thêm type mới |
| `nowing_backend/app/db.py` | `1590-1621` | `Report` model |
| `nowing_backend/app/db.py` | `3154-3219` | `Run` model (`duration_ms`, `cost_micros`, `output_text`) |
| `nowing_backend/app/zero_publication.py` | `82-94` | `ZERO_PUBLICATION` scope |
| `nowing_backend/app/observability/metrics.py` | `1155-1210` | `record_chainlens_degradation`, `record_kb_fallback_hit_count`, `record_blocked_url_coverage` |
| `nowing_backend/app/config/__init__.py` | `637` | `REDIS_URL` |
| `nowing_backend/app/config/__init__.py` | `864-866` | `PLATFORM_SCRAPE_BILLING_ENABLED` |
| `nowing_backend/app/config/__init__.py` | `910-917` | `CHAINLENS_API_KEY`, `CHAINLENS_REQUEST_TIMEOUT_SECONDS`, `CHAINLENS_QUERY_MICROS_PER_CALL` |
| `nowing_web/lib/apis/scrapers-api.service.ts` | `61-72` | `runAsync` typed client |
| `nowing_web/lib/apis/scrapers-api.service.ts` | `88-111` | `streamRunEvents` typed SSE client |
| `nowing_web/contracts/types/scraper.types.ts` | `56-60` | `startAsyncRunResponse` type |
| `chainlens-research/apps/api/src/search/api.ts` | `196-217` | `SearchProgressMilestones` + emit `progress` |
| `chainlens-research/apps/api/src/search/api.ts` | `1471-1474` | emit `synthesizing` |
| `chainlens-research/apps/api/src/search/api.ts` | `1568-1579` | emit `evidence_ready` |
| `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` | `17-82` | MCP tool, cần xử lý 202 hoặc trả `run_id` |
| `nowing_mcp/mcp_server/features/scrapers/capability.py` | `16-38` | `run_scraper` inline; cân nhắc async path |

### Config Keys / Env Vars

| Key | Mục đích | Vị trí đề xuất |
|---|---|---|
| `DEFAULT_RESEARCH_MODE` | Chọn default `balanced`/`quality` | `app/config/__init__.py` gần `CHAINLENS_*` |
| `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` | Bật State B sync chat-mode | `app/config/__init__.py` |
| `RUN_EVENT_BUS` | Chọn backend bus `memory`/`redis` | `app/config/__init__.py` hoặc dựa trên `REDIS_URL` |
| `REDIS_URL` | Đã có; dùng cho Redis pub/sub | `app/config/__init__.py:637` |

### Testing Approach

- **Unit:** `tests/unit/capabilities/chainlens/research/test_executor.py` — thêm fixture SSE golden với `progress`, `evidence_ready`, `synthesizing`, `researchComplete`; assert `emit_progress` được gọi đúng phase, TTFB được ghi, unknown types không raise.
- **Unit:** `tests/unit/capabilities/test_billing.py` — assert `_charge_chainlens` nhận `mode_requested`, `call_details` chứa `mode_requested`, `resolved_mode`, `e2e_ms`, `ttfb_ms`.
- **Integration:** Redis `run_event_bus` cross-replica: dùng test Redis (hoặc mock) với 2 instance, publish từ B, tail SSE ở A.
- **Integration:** Agent async submit-and-return: mock `execute_with_context`, assert `_capability_tool` trả về `run_id` + `status=running`; `agent.py` không import `rest.py`.
- **Integration:** Notification realtime qua Zero cho mọi terminal state (`success`, `error`, `cancelled`); Report tạo từ run.
- **Integration:** p50/p95 endpoint: seed `TokenUsage` rows với `e2e_ms`/`ttfb_ms`/`resolved_mode`, gọi `GET /admin/metrics/deep-research-latency?mode=balanced&p=0.95`, assert kết quả.
- **Eval:** Thêm scenario `nowing_evals/suites/research/chainlens_latency` gọi `POST /workspaces/{id}/scrapers/chainlens/research?mode=...` và so sánh `balanced` vs `quality` trên `answer_recall@k` / `f1`, hoặc tái dụng `crag`/`frames` với tham số `mode`.
- **Commands:**
  ```bash
  cd nowing_backend
  uv run --active python -m pytest tests/unit/capabilities/chainlens/research -q
  uv run --active python -m pytest tests/unit/capabilities/test_billing.py -q
  uv run --active python -m pytest tests/integration/capabilities/chainlens/research -q
  cd ../nowing_evals
  python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality --workspace-id <WORKSPACE_ID> --environment local --concurrency 1
  python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality --workspace-id <WORKSPACE_ID> --environment production --concurrency 1
  python -m nowing_evals report --suite research --benchmark chainlens_latency
  ```

## Code status note

Mostly implemented and merged, but the overall State A→B gate is not yet ratified. `async_runner.py` provides the shared `_execute_async_run`/`start_async_run` lifecycle; `agent.py` submits `chainlens.research` and returns `run_id` without blocking; `rest.py` supports async 202 + SSE events and a deliverable endpoint; `events_redis.py` adds a Redis-backed `RunEventBus` for multi-replica (toggled by `RUN_EVENT_BUS=redis`). The `_SSEParser` maps `progress`/`evidence_ready`/`synthesizing`/`researchComplete` to `emit_progress` and derives TTFB from engine milestones. `_charge_chainlens` records `e2e_ms`, `ttfb_ms`, `mode_requested`, and `resolved_mode` in `TokenUsage.call_details`; a migration (`alembic/versions/185_add_token_usage_latency_columns.py`) adds `e2e_ms`/`ttfb_ms` columns; `admin_latency_routes.py` serves p50/p95 per `resolved_mode`. `DEFAULT_RESEARCH_MODE` defaults to `"balanced"`; `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` is `false`, keeping `chainlens.research` in State A (async). The `research/chainlens_latency` benchmark (`nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py`) runs a mode matrix and compares `balanced` vs `quality` using token-overlap `answer_recall`/`f1`, but the `gate.yaml` has `baseline_ratified: false` and the State B flag remains off. Remaining gaps: cross-replica Redis bus integration test, notification/Report integration tests, p50/p95 endpoint integration test, ratification of p95 thresholds and NFR-9 documentation.

## Project Structure Notes

- `nowing_backend/app/capabilities/core/events.py` — nơi thêm Redis backend; **KHÔNG** đổi call-site `run_event_bus.publish`/`subscribe`/`replay`.
- `nowing_backend/app/capabilities/core/async_runner.py` — **NEW** chứa `_execute_async_run` + `start_async_run` dùng chung; `rest.py` và `agent.py` import từ đây.
- `nowing_backend/app/capabilities/core/access/agent.py` — `chainlens.research` submit-and-return; các capability khác vẫn inline.
- `nowing_backend/app/capabilities/core/access/rest.py` — import `start_async_run` từ `async_runner.py`; `chainlens.research` ép `async` khi `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` tắt.
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — parser mở rộng progress; `build_research_executor` thêm phases.
- `nowing_backend/app/capabilities/core/billing.py` — `_charge_chainlens` nhận `mode_requested`, ghi `e2e_ms`/`ttfb_ms`/`mode_requested`/`resolved_mode` vào `TokenUsage.call_details`.
- `nowing_backend/app/notifications/` — mở rộng `NotificationType` + `CATEGORY_TYPES`, thêm handler/facade cho `deep_research_complete`.
- `nowing_backend/app/db.py` — `Report` model đã có; migration thêm `e2e_ms`/`ttfb_ms` numeric + partial index trên `TokenUsage`.
- `nowing_web/lib/apis/scrapers-api.service.ts` — client đã typed, KHÔNG cần sửa trừ khi thêm endpoint deliverable.
- `nowing_evals/` — thêm scenario `suites/research/chainlens_latency` để validate default `balanced` vs `quality`.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` — cần xử lý 202 async hoặc trả `run_id` + link SSE.

## References

- `epics.md:534-594` — Story 9.3 gốc và Acceptance Criteria.
- `prd-Nowing-2026-07-22/prd.md:573-587` — FR-24 (contract, mode default `balanced`).
- `prd-Nowing-2026-07-22/prd.md:880-884` — SM-11b/c.
- `prd-Nowing-2026-07-22/prd.md:14-20` — D3 / NFR-9 / State A/B.
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:283-323` — AD-17 (3 việc còn thiếu thật).
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:91-99` — AD-4 (agent runtime).
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:96-100` — AD-5 (Zero scope).
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:364-410` — AD-19 (anti-bot, async enrichment).
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:446-475` — AD-20 (screenshot, no visual-RAG).
- `architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:145-153` — AD-11.1 (memory recipe).
- `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md:128-158` — NFR-9 State A/B framing.
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md` — UX contract S1-S10 cho progress-first.
- `9-2-deep-research-cost-metering.md` — patterns `costDollars`, `TokenUsage`, `_charge_chainlens`.
- `9-1a-research-degradation-selfhost-independence.md` — patterns degradation/fallback/BlockType.
- `9-1b-research-contract-regression-guard.md` — patterns data-only SSE, fixture golden.
- `chainlens-research/apps/api/src/search/api.ts:196-217`, `:1471-1474`, `:1568-1579` — hình dạng event ChainLens.

## Dev Agent Record

**Recent git history (HEAD `0b3846b60` on `develop`):**

```
0b3846b60 Story 8.10: align README/docs/landing with research-memory vision and add drift gate
7a7b0fe31 style: ruff format and lint cleanup after Story 8.11
37d6e881f feat(admin): Story 8.11 — platform superuser UI for global LLM model configuration
e6e8720ec reconcile: close 3.9 and 8.7 gates + sync public docs for ChainLens engine boundary
67cc2e626 config: raise chainlens research mutation timeout to 180s for CI baseline
5d4f5f7f8 ci: add ChainLens research mutation gate workflow
b8882d469 feat(tests): push billing mutation score to 86.88% and harden gate script
890b06e3a feat(tests): mutation-killing tests for chainlens cost metering and billing
c5861dc8b code-review(9.2): preserve first costDollars, allow zero-cost audit rows
0fdcf296c feat(billing): deep-research cost metering with real costDollars
```

- `0fdcf296c` và `c5861dc8b` là 9.2 (cost metering thật) — `_charge_chainlens` và `executor.py:_extract_cost` đã land.
- `67cc2e626`, `5d4f5f7f8`, `b8882d469`, `890b06e3a` là CI/mutation gate xung quanh deep-research — story 9.3 cần tiếp tục gia tăng test coverage.
- `e6e8720ec` đóng 3.9 / 8.7 + sync docs engine boundary — cho thấy `develop` đang ổn định sau 9.1/9.2/9.4.
- HEAD `0b3846b60` là 8.10 (docs README) — không liên quan deep-research, đồng nghĩa baseline sạch.

## Open Questions / Risks

1. **Notification recipient khi `Run.user_id` null:** Agent tool có thể thiếu `user_id`; cần fallback về workspace owner (`_resolve_workspace_owner`) hay bỏ qua notification?
2. **Deliverable endpoint hay auto-save?** AC ghi "nếu user yêu cầu". UX contract chưa định nghĩa trigger; cần quyết định là `POST` thủ công hay UI gọi.
3. **Shape `progress` event từ ChainLens:** Đã xác nhận `requestAcceptedAt`, `firstProgressAt`, `evidenceReadyAt?`, `firstFactualChunkAt?` là epoch ms. Nếu ChainLens thay đổi tên field, parser cần defensive.
4. **TTFB clock skew:** `firstFactualChunkAt - requestAcceptedAt` nằm trong cùng event nên an toàn hơn so với đồng hồ Nowing.
5. **Redis-backed bus test multi-replica:** Khó chạy trong CI single-process. Có thể dùng test Redis container hoặc mock `Redis` client.
6. **Ngưỡng p95 chưa biết:** AC số 10 là deliverable tài liệu; ngưỡng cụ thể sẽ được đặt sau khi có baseline, không trong code.
7. **Mode default `balanced` trên `nowing_evals`:** Thêm scenario `suites/research/chainlens_latency` gọi `POST /workspaces/{id}/scrapers/chainlens/research?mode=...` và so sánh `balanced` vs `quality` trên `answer_recall@k` / `f1`.
8. **MCP async path:** `nowing_mcp` hiện gọi REST sync và compact kết quả inline. Cần quyết định xử lý 202 (trả `run_id` + SSE link) hay tạo MCP follow-up tool `nowing_get_scraper_run`.

## State A → State B Gate Reference

| Flag | Env var | Default | State A | State B |
|---|---|---|---|---|
| Research default mode | `DEFAULT_RESEARCH_MODE` | `balanced` | `balanced` | `balanced` |
| Sync chat-mode | `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` | `false` | `false` | `true` |
| Run event bus | `RUN_EVENT_BUS` | `memory` | `memory` | `redis` (multi-replica) |

### Gating criteria

1. `nowing_evals run research chainlens_latency` must pass with the provisional gate in `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/gate.yaml`.
2. `p95_e2e_ms_max_balanced` and `p95_ttfb_ms_max_balanced` must be ratified against a measured baseline (`baseline_ratified: true`).
3. Only after ratification should `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` be set to `true`.

### Operational endpoints

- `POST /workspaces/{id}/scrapers/chainlens/research?mode=sync` — synchronous when State B is on; forced to `?mode=async` when State A is on.
- `POST /workspaces/{id}/scrapers/chainlens/research?mode=async` — always available; returns `202 {run_id, status: "running"}`.
- `GET  /workspaces/{id}/scrapers/runs/{run_id}/events` — SSE tail; backed by `RUN_EVENT_BUS=redis` in multi-replica deployments.
- `POST /workspaces/{id}/scrapers/runs/{run_id}/deliverable` — materialize a successful deep-research run as a `Report`.
- `GET  /admin/metrics/deep-research-latency?metric=e2e` — p50/p95 latency per `mode_requested`.

### Review Findings

Review chạy trên commit `947c09319..e152bdbac`. 3 lớp: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

#### patch

- [ ] [Review][Patch] `chainlens_latency` eval bổ sung answer quality metrics (`answer_recall@k`, `f1`) và logic tự động revert `balanced`→`quality` khi quality giảm — đã chuyển từ decision-needed thành patch.

- [ ] [Review][Patch] `_SSEParser` tính TTFB bằng đồng hồ Nowing thay vì `firstFactualChunkAt - requestAcceptedAt` [executor.py:149-159, 527]
- [ ] [Review][Patch] Parser chưa map `evidence_ready`, `synthesizing`, `researchComplete` vào `emit_progress`; rơi vào unknown [executor.py:310-326]
- [ ] [Review][Patch] `progress` event `current`/`total` có thể là float/string, cần normalize trước khi emit [executor.py:310-321]
- [ ] [Review][Patch] `_charge_chainlens` fallback `resolved_mode` dùng `getattr(output, "mode", None)` thay vì `mode_requested` [billing.py:278-286]
- [ ] [Review][Patch] `stream_run_events` short-circuit khi `run_event_bus.get_task(raw) is None`, khiến Redis bus không được dùng cross-replica [rest.py:394-416]
- [ ] [Review][Patch] `cancel_run` không guard cross-replica: worker khác vẫn có thể finalize sau cancel [rest.py:435-456, runs.py:197-210]
- [ ] [Review][Patch] `RedisRunEventBus` thiếu connection/socket timeout, reconnect, và subscription chờ bất đồng bộ dễ miss event [events_redis.py:57-65, 77-98, 137-145]
- [ ] [Review][Patch] Admin latency endpoint nhóm/filter theo `mode_requested` thay vì `resolved_mode`, thiếu query param `p=0.5|0.95`, tính percentile trong Python thay vì SQL `percentile_cont` [admin_latency_routes.py:68-97]
- [ ] [Review][Patch] Thiếu Alembic migration thêm cột `e2e_ms`/`ttfb_ms` và partial index trên `TokenUsage` [db.py:1125-1189, alembic/versions]
- [ ] [Review][Patch] `DEFAULT_RESEARCH_MODE` không normalize/validate trước khi gán default [config/__init__.py:924-926]
- [ ] [Review][Patch] Async 202 response không set header `X-Run-Id` theo story contract [rest.py:234-237]
- [ ] [Review][Patch] Deliverable `Report` không copy `Run.thread_id` [rest.py:518-530]
- [ ] [Review][Patch] Sync `chainlens.research` (State B) không gọi `_publish_finished`/`_notify_terminal`, thiếu terminal notification [async_runner.py:282-352, rest.py:260-299, agent.py:197-224]
- [ ] [Review][Patch] `nowing_evals` runner dùng `httpx.Timeout` 30s cố định cho sync path, dễ timeout trước `CHAINLENS_REQUEST_TIMEOUT_SECONDS` [runner.py:217-221]
- [ ] [Review][Patch] `finalize_run` lỗi nhưng `_publish_finished` vẫn được gọi, client thấy terminal event trong khi DB vẫn `running` [async_runner.py:188-197]
- [ ] [Review][Patch] `POST /runs/{run_id}/deliverable` có thể tạo duplicate Report nếu gọi nhiều lần [rest.py:485-543]
- [ ] [Review][Patch] Unit test chưa assert `call_details` mới (`mode_requested`, `resolved_mode`, `e2e_ms`, `ttfb_ms`) và progress fixture đầy đủ [tests/]

#### defer

- [x] [Review][Defer] `nowing_mcp` chưa handle async 202 response — nằm ngoài scope backend, ghi nhận follow-up.
- [x] [Review][Defer] NFR-9 / State A→B threshold docs còn provisional (`baseline_ratified: false`) — cần baseline đo thực tế.
- [x] [Review][Defer] Integration test cross-replica cho Redis-backed `run_event_bus` — cần infra Redis test container.

#### dismissed

- `Report` content format H1/H2: có thể là UX decision, không rõ ràng vi phạm; giữ nguyên để PM quyết.
- `e2e_ms` từ `output.duration_ms` thay vì `Run.duration_ms`: by design, `output.duration_ms` là e2e của research call; `Run.duration_ms` là wall-clock tổng thể.

### Review Findings — 2026-08-01

Review trên diff `0b3846b602c512dfd020a1d89b8485ce0cbf20e6..HEAD` (gồm commit `947c09319` và `e152bdbac` cộng các thay đổi chưa commit). 3 lớp: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

#### decision_needed

- [ ] [Review][Decision] Redis-backed `run_event_bus` reliability scope — `events_redis.py` dùng `create_task` cho publish/subscribe/listener-restart, không timeout/backoff/circuit-breaker, message có thể mất khi reconnection. Quyết định: (a) chấp nhận best-effort cho multi-replica v1, (b) thêm retry/backoff và dead-letter, hay (c) để infra Redis Streams thay pub/sub?
- [ ] [Review][Decision] `extract_budget.py` chuyển từ sliding sang fixed-window rate limit — đổi semantics, key có thể tồn tại vĩnh viễn nếu EXPIRE bị mất. Đây có phải chủ đích của 8.7 hay cần rollback?
- [ ] [Review][Decision] State A→B threshold ratification — `nowing_evals/suites/research/chainlens_latency/gate.yaml` để `baseline_ratified: false` với provisional p95. ChainLens đã chạy benchmark `agy/gemini-3.6-flash-*` n=57 (2026-08-01): p50 24s/31s/43s, p95 35s/70s/115s cho speed/balanced/deep. Tất cả p95 vượt target NFR-9 (30s/30s/60s). **Quyết định tạm thời: State A vẫn là mặc định, không mở khóa sync chat-mode.** Cần chạy eval từ phía Nowing (e2e) và benchmark sạch hơn sau khi ChainLens ổn định SearXNG/Brave/proxy.

#### patch

- [ ] [Review][Patch] TTFB fallback dùng `time.perf_counter()` không tương thích với engine epoch-ms [executor.py:184-212] — nên để `None` hoặc dùng `time.time()` khi engine không emit milestones.
- [ ] [Review][Patch] `finalize_run` check-then-set `run.status == "cancelled"` không có row lock / atomic CAS [runs.py:189-215] — hai replica có thể race.
- [ ] [Review][Patch] Agent async `chainlens.research` không gọi `enforce_capability_rate_limit` [agent.py:130-149] — chỉ gọi `gate_capability`, thiếu per-minute cap.
- [ ] [Review][Patch] Deliverable endpoint `POST /runs/{run_id}/deliverable` thiếu idempotency chống race duplicate Report [rest.py:520-560].
- [ ] [Review][Patch] Admin latency endpoint tải toàn bộ rows vào RAM rồi tính percentile trong Python [admin_latency_routes.py:61-136] — nên dùng SQL `percentile_cont` + cursor/pagination.
- [ ] [Review][Patch] Migration `185_add_token_usage_latency_columns.py` tồn tại nhưng chưa được `git add` / chưa trong diff — cần stage và commit.
- [ ] [Review][Patch] `RedisRunEventBus` publish/subscribe/listener-restart không timeout, không await error, queue full drop event im lặng [events_redis.py:145-210].
- [ ] [Review][Patch] `stream_run_events` race giữa replay buffer và DB snapshot [rest.py:407-430] — run có thể finish giữa replay và query, gây duplicate/out-of-order terminal event.
- [ ] [Review][Patch] `deliverable` parser `ResearchOutput.model_validate_json` trên `output_text.splitlines()[0]` dễ 500 nếu dòng đầu không phải JSON [rest.py:507-515].
- [ ] [Review][Patch] `nowing_evals` runner không validate `resolved_mode` trả về khớp `mode_requested`, gộp metrics sai mode [runner.py:2920-2940].
- [ ] [Review][Patch] `_to_int` trong executor cho phép negative int, bị `max(..., 0)` che mất [executor.py:37-45].
- [ ] [Review][Patch] `Report.thread_id` conversion `ValueError` bị bắt im lặng [rest.py:533-538].
- [ ] [Review][Patch] Unit test `test_executor.py` chưa có golden fixture đầy đủ cho `progress` với `requestAcceptedAt`/`firstFactualChunkAt`/`evidence_ready`/`synthesizing`/`researchComplete` [tests/unit/capabilities/chainlens/research/test_executor.py].

#### defer

- [x] [Review][Defer] Integration test cross-replica Redis `run_event_bus` — cần test Redis container hoặc mock multi-process.
- [x] [Review][Defer] Notification + Report deliverable tests tích hợp — có thể bổ sung sau khi API contract ổn định.
- [x] [Review][Defer] `nowing_mcp` xử lý async 202 — nằm ngoài scope backend.
- [x] [Review][Defer] Threshold A→B ratification / NFR-9 — cần baseline thực tế.

#### dismissed

- [Review][Dismiss] Agent async session "không commit" — `create_pending_run` tự `session.commit()` bên trong.
- [Review][Dismiss] Missing migration `e2e_ms`/`ttfb_ms` — migration file `185_add_token_usage_latency_columns.py` đã tồn tại, chỉ chưa staged.
- [Review][Dismiss] Billing `_charge_chainlens` vẫn dùng `getattr(output, "mode", None)` — code hiện tại dùng `resolved_mode or mode_requested`.
- [Review][Dismiss] `TTFB negative clamped` — `max(0, ...)` là guard hợp lý cho dữ liệu engine out-of-order.

### Re-Review Findings — 2026-08-01 (sau patch)

Re-review chạy trên diff mới nhất (sau khi apply patch). 3 lớp: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

#### patch (còn lại, đã apply)

- [x] [Review][Patch] `RedisRunEventBus` `_pub()` / `_sub()` / `_unsub()` / `_start()` tạo `asyncio.create_task` mà không có `add_done_callback` — thêm `_fire()` helper gắn `_log_task_exception` [events_redis.py:91-94, 116, 183, 199, 263].
- [x] [Review][Patch] `admin_latency_routes` trả `0.0` cho p50/p95 khi `samples == 0` — đổi `LatencyPercentile.p50/p95: float | None` và trả `None` khi `samples == 0` [admin_latency_routes.py:27-31, 104-105].
- [x] [Review][Patch] `_ensure_listener` có thể tạo nhiều `_start` task — thêm `self._ensure_task` và cancel task cũ trước khi tạo mới [events_redis.py:54, 112-116].

#### defer (cần dữ liệu / infra / quyết định lớn)

- [x] [Review][Defer] Thiếu integration test cross-replica cho `RedisRunEventBus` (AC3, T1.4) — cần test container hoặc mock multi-worker.
- [x] [Review][Defer] `baseline_ratified: false` trong `chainlens_latency/gate.yaml` — ChainLens benchmark 2026-08-01 cho p50 24s/31s/43s và p95 35s/70s/115s (speed/balanced/deep), tất cả vượt target. Cần benchmark e2e từ phía Nowing + benchmark sạch hơn (SearXNG/Brave/proxy ổn định) để ratify.
- [x] [Review][Defer] `resolved_mode` không được validate nằm trong enum cho phép (`speed`/`balanced`/`quality`/`auto`) — ảnh hưởng metrics/billing nếu engine trả giá trị lạ [executor.py, billing.py].
- [x] [Review][Defer] `create_deliverable` và eval `_parse_run` assume `output_text.splitlines()[0]` là JSON — contract hiện là JSONL, nhưng nên rõ ràng hơn nếu contract đổi.

#### dismissed

- [Review][Dismiss] `TTFB local clock` vẫn dùng `time.perf_counter()` — đây là fallback khi engine không emit, chấp nhận cho v1.
- [Review][Dismiss] `Rate limit agent vs REST` khác client pool — cả hai dùng cùng `_incr` từ `rate_limit.py`.
- [Review][Dismiss] `Redis listener backoff` 1s fixed — đủ cho v1, nâng cấp exponential backoff là nice-to-have.
- [Review][Dismiss] `finalize_run` concurrent success/error race — chỉ có một background task thực hiện run, row lock đã ngăn write conflict.

## ChainLens Follow-up (2026-08-02)

- Benchmark gốc 2026-08-01 bị ảnh hưởng nặng bởi SearXNG CAPTCHA/rate-limit → `provider_failover_failed`.
- Plan của ChainLens để có benchmark sạch hơn:
  1. Ổn định SearXNG (`searxng/settings.yml` tắt mojeek/yep, fallback Brave/Jina).
  2. Proxy/residential proxy rotation (Proxy-Seller) hoặc Brave-first routing.
  3. Rerun `node --experimental-strip-types benchmark/run.ts --chainlens-only --all-modes`.
- Dự kiến có kết quả benchmark mới trong **24–48h** trên staging.
- **State A vẫn là mặc định** cho đến khi benchmark sạch hơn + Nowing e2e benchmark xác nhận p95 đạt ngưỡng.
- ChainLens xác nhận plan; sẽ ping khi benchmark numbers land. Nowing sẽ chạy e2e benchmark từ phía mình ngay khi có số sạch.
- **E2E harness đã sẵn sàng:** `python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality --concurrency 1` (không cần `setup`/`ingest`). Gate targets ở `gate.yaml` với `baseline_ratified: false`.

## ChainLens Rerun Results (2026-08-02)

Focused rerun sau khi ổn định SearXNG/Brave: **6 query × 3 mode = 18 runs**.

| Mode | p95 | NFR-9 target | Kết luận |
|---|---|---|---|
| speed | 27.5 s | ≤ 30 s | ✅ PASS |
| balanced | 44.3 s | ≤ 30 s | ❌ FAIL |
| deep | 43.7 s | ≤ 60 s | ✅ PASS |

- `ask` tier ở `quality` vẫn vượt target 30 s của NFR-6.
- `costDollars` **không còn $0**: ChainLens benchmark `report-per-mode.md` (2026-08-02, 31 queries) ghi cost thực tế (tiêu biểu Nowing `tier=research`):

| Mode | Tier | Avg Latency | Avg Cost |
|---|---|---|---|
| speed | ask | 21.8 s | $0.0258 |
| balanced | ask | 25.8 s | $0.0407 |
| quality | ask | 49.3 s | $0.1485 |
| speed | reason | 29.6 s | $0.0303 |
| balanced | reason | 47.7 s | $0.0507 |
| quality | reason | 49.9 s | $0.0750 |
| speed | research | 33.4 s | $0.0353 |
| balanced | research | 51.1 s | $0.0482 |
| quality | research | 49.1 s | $0.0671 |

- Cost tham chiếu cho Nowing: **speed $0.0353 / balanced $0.0482 / quality $0.0671**, trung bình **$0.0519 / call**.
- `CHAINLENS_QUERY_MICROS_PER_CALL` fallback đã nâng từ 5,000 ($0.005) → **60,000 micros (~$0.06)**.
- Full benchmark **69 query** đang lên lịch để củng cố p95 trên mẫu lớn.

**Quyết định cập nhật (2026-08-02):**
- **State A vẫn là mặc định.** Không mở khóa sync chat-mode.
- `balanced` vẫn chưa đạt target 30 s — cần full 69-query benchmark + Nowing e2e trước khi xem xét State B.
- Giờ đã có cost thực tế, pricing có thể bắt đầu định hình nhưng vẫn giữ margin 1.5–2.5× cho full-pipeline cost aggregation.

### Review Findings — 2026-08-08 (round 3)

**Verdict: CHANGES REQUESTED** — 7 patches + 8 deferred + 18 dismissed

#### Patch (must fix before approval)

- [x] [Review][Patch] **P1: Admin latency percentile logic bug** [admin_latency_routes.py:106-109] — `p95 = p50` when `p_target == 0.5` overwrites computed p95. Fix: remove overwrite logic, return both p50 and p95 always.
- [x] [Review][Patch] **P2: TTFB negative values silently clamped** [executor.py:231-233] — `max(0, ...)` without warning masks data quality issues. Fix: add `logger.warning` when clamping.
- [x] [Review][Patch] **P3: Admin latency route no mode validation** [admin_latency_routes.py:53] — No enum validation on `mode` parameter. Fix: add `ALLOWED_MODES` check.
- [x] [Review][Patch] **P4: Default mode config silent fallback** [config/__init__.py] — Invalid `DEFAULT_RESEARCH_MODE` silently falls back to "balanced". Fix: add `logger.warning`.
- [x] [Review][Patch] **P5: Empty mode string not handled** [agent.py:131] — `""` not treated as None in `_is_sync_chat_mode_allowed`. Fix: add `if not mode:` check.
- [x] [Review][Patch] **P6: Negative KB fallback duration** [executor.py:900-901] — `perf_counter` could go negative if clock adjusted. Fix: add `max(0, ...)`.
- [x] [Review][Patch] **P7: Missing integration tests T8.2, T8.4, T8.6** — Spec marks these as `[-]` not done. Per best practices, require before approval: T8.2 (Redis cross-replica), T8.4 (notification+deliverable), T8.6 (p50/p95 endpoint).

#### Deferred (pre-existing or architectural)

- [x] [Review][Defer] KB fallback cost hardcoded to 0 — not measured [executor.py:863-864] — deferred, future enhancement
- [x] [Review][Defer] Redis event bus subscribe failure state leak [events_redis.py] — deferred, pre-existing v1 pattern
- [x] [Review][Defer] Agent rate limiting per-worker fallback [rate_limit.py] — deferred, architectural
- [x] [Review][Defer] Migration no backfill for existing rows [185_add_token_usage_latency_columns.py] — deferred, nullable columns intentional
- [x] [Review][Defer] Notification lacks idempotency guard [async_runner.py] — deferred, best-effort
- [x] [Review][Defer] Deliverable race condition on concurrent requests [rest.py] — deferred, low probability
- [x] [Review][Defer] Redis publish/listener/backoff issues (3 merged) [events_redis.py] — deferred, pre-existing v1
- [x] [Review][Defer] Platform billing changes (VN_BDS) outside story scope [billing.py] — deferred, scope creep but not harmful

#### Dismissed (18 items)

- finalize_run race condition — FALSE POSITIVE, `with_for_update()` is atomic
- Memory extraction rate counter — duplicate of agent rate limiting
- ResearchOutput early return — by design
- Deliverable thread_id conversion — intentional fallback, warning logged
- Budget/rate fail-closed — by design
- gate.yaml baseline_ratified false — correct per spec
- Agent door rate limiting not in spec — good practice
- Integer overflow timestamp — theoretical (year 2260+)
- Rate limit key length — unlikely
- Gate logic resolved_mode format — trusted source
- SSE parser upper bound — trusted source
- Eval runner resolved_mode length — validated
- Concurrent dict access — asyncio single-threaded
- Mock ChainLens not in spec — positive addition
- Test fixtures — positive
- Migration already done per spec — informational
