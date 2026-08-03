---
baseline_commit: 029ba6923
baseline_branch: develop
story_key: 9-6b
status: done
---

# Story 9.6b: Source Re-Validation API

**Status:** `done`  
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng  
**Priority:** P0 nếu muốn kể câu chuyện re-validation; không chặn launch (FR-39, AD-11.1, FR-34, AD-8)  
**Requirements:** FR-39 (phần re-validate) · AD-11.1 · FR-34 · AD-8  
**Baseline:** `029ba6923` on `develop`  
**Dependencies:** Story `9.6a` done (`Memory` đã có `source_capability`, `source_input`, `source_run_id`)

## Story

Với tư cách agent hoặc người dùng,  
tôi muốn hệ thống chạy lại được truy vấn gốc của một memory để biết fact còn đúng không,  
để memory không trả về thông tin đã cũ kèm citation trông đáng tin — thứ tệ hơn là không trả gì.

## Current Reality / BUILT vs GAP

Tại baseline `029ba6923` (bao gồm code Story 9.6a đã xong):

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| `Memory` tự chứa recipe (`source_capability` + `source_input`) | ✅ BUILT | `app/db.py:2115-2116`; migration `186` |
| `Memory` soft ref `source_run_id` (UUID, không FK cứng) | ✅ BUILT | `app/db.py:2111`; migration `184` |
| `MemoryVersion` ghi lại mỗi correction | ✅ BUILT | `app/db.py:2143-2164` |
| `MemoryRepository.update_memory` tạo `MemoryVersion` khi `content` đổi | ✅ BUILT | `app/services/memory/repository.py:398-406` |
| Capability registry + executor runner | ✅ BUILT | `app/capabilities/core/store.py`, `app/capabilities/core/__init__.py:68-86` |
| REST door chạy capability sync/async + meter | ✅ BUILT | `app/capabilities/core/access/rest.py:177-309`, `app/capabilities/core/billing.py:111-204` |
| `POST /workspaces/{id}/memories` và `PATCH /memories/{id}` | ✅ BUILT | `app/routes/memories_routes.py` |
| API `revalidate(memory_id)` | ✅ BUILT | `app/routes/memories_routes.py:163-209` |
| Logic so sánh kết quả re-run với `Memory.content` | ✅ BUILT | `app/services/memory/revalidation_service.py:220-256` |
| Cập nhật `confidence`/tạo `MemoryVersion` khi lệch | ✅ BUILT | `app/services/memory/revalidation_service.py:240-256` + `MemoryRepository.update_memory` |
| Meter chi phí re-validate như capability call thường | ✅ BUILT | `app/services/memory/revalidation_service.py:196-199` (`charge_capability`)

## Resolved Decisions

### D1 — `revalidate` là một capability call thông thường

- `revalidate(memory_id)` sẽ:
  1. Load `Memory` theo `memory_id`.
  2. Kiểm tra `source_capability` + `source_input` tồn tại (memory phải là `SCRAPER_RUN` hoặc có recipe).
  3. Nếu không có recipe → trả về typed error `not_revalidatable` (không 500).
  4. Lấy `capability = get_capability(memory.source_capability)`.
  5. Build `payload` từ `memory.source_input` bằng `capability.input_schema(**input)`.
  6. Gọi `execute_with_context(capability.executor, payload=payload, ctx=CapabilityContext(session, workspace_id))`.
  7. Gọi `gate_capability` + `charge_capability` như mọi capability call khác (AD-8).
  8. So sánh output mới với `memory.content`.
- Không dùng async runner: re-validate cần kết quả ngay để trả về memory/version.
- `Run` gốc có thể đã bị xóa; ta không dùng `source_run_id` để lookup, chỉ dùng recipe trong `Memory`.

### D2 — So sánh kết quả và ghi lại

- Nếu output mới tạo ra một fact có `content` giống (hoặc tương đương) với `memory.content`:
  - Cập nhật `memory.updated_at` và `memory.confidence` (tăng nhẹ, ví dụ từ 0.85 → 0.95, tối đa 1.0).
  - Không tạo `MemoryVersion`.
- Nếu output mới khác:
  - Hạ `memory.confidence` (ví dụ × 0.8, tối thiểu 0.1).
  - Tạo `MemoryVersion` với `previous_content=memory.content`, `corrected_content` = nội dung mới.
  - **Không** tự động xóa memory cũ (FR-34).
- So sánh: dùng `content` string match cơ bản (case-insensitive, whitespace normalized) là đủ cho MVP. LLM semantic compare là upgrade path.

### D3 — API shape

- REST: `POST /workspaces/{workspace_id}/memories/{memory_id}/revalidate`.
  - Response: `MemoryRead` (memory đã update/create version).
- MCP / agent: chưa bắt buộc trong 9.6b; re-validate được gọi qua REST hoặc internal service. Nếu cần, thêm tool sau.
- Auth: dùng `require_session_context`, kiểm tra `workspace_id` (memory phải thuộc workspace) qua `check_permission` hoặc `check_workspace_access`.

### D4 — Metering

- Re-validate chạy lại capability nên gọi `gate_capability` trước và `charge_capability` sau.
- `TokenUsage.usage_type` = capability's `billing_unit` (ví dụ `reddit_item`).
- Nếu capability `billing_unit` là `None` thì free.

## Acceptance Criteria

> Trích từ `epics.md` §Story 9.6b.

**Given** một memory có `source_capability` + `source_input` (từ `9.6a`)  
**When** gọi `revalidate(memory_id)`  
**Then** chạy lại capability với input đó → so sánh kết quả với `content`  
**And** nếu khớp → cập nhật timestamp "last verified"; nếu lệch → hạ `confidence` **và** tạo `MemoryVersion` ghi lại thay đổi  
**And** **không** tự động xóa memory cũ (giữ kỷ luật FR-34 — không xóa cứng).

**Given** memory nguồn `document`/`chat_message` (không có recipe)  
**When** gọi `revalidate`  
**Then** trả trạng thái tường minh "không re-validate được cho nguồn này", **không** lỗi 500.

**Given** re-validate gọi lại một capability có phí  
**When** chạy  
**Then** chi phí được meter như một capability call bình thường (`AD-8`) — không có đường tính phí ẩn.

**Given** `Run` gốc đã bị xoá sau 30 ngày  
**When** gọi `revalidate`  
**Then** vẫn chạy được (recipe nằm trong `Memory` theo `AD-11.1`) — đây là AC chứng minh quyết định `AD-11.1` đúng.

## Tasks / Subtasks

- [x] **T1 — Tạo `RevalidationService`** (AC 1, 2, 3, 4)
  - [x] T1.1 `app/services/memory/revalidation_service.py` với `RevalidationService.revalidate(memory_id)`.
  - [x] T1.2 Load memory + workspace, verify recipe tồn tại.
  - [x] T1.3 Lấy capability từ registry; validate `source_input` qua `input_schema`.
  - [x] T1.4 Gọi `gate_capability` → `execute_with_context` → `charge_capability`.
  - [x] T1.5 Serialize output và so sánh với `memory.content`.
  - [x] T1.6 Nếu khớp: bump `confidence` + `updated_at`; nếu lệch: giảm `confidence` + tạo `MemoryVersion` (dùng `MemoryRepository.update_memory` hoặc tương tự).
  - [x] T1.7 Nếu không có recipe: raise typed `RevalidationError` mà route bắt và trả 422.

- [x] **T2 — Tạo REST route** (AC 1, 2, 3)
  - [x] T2.1 `POST /workspaces/{workspace_id}/memories/{memory_id}/revalidate` trong `app/routes/memories_routes.py`.
  - [x] T2.2 Auth + permission check (`MEMORY_UPDATE` vì ghi `MemoryVersion`/`confidence`).
  - [x] T2.3 Response `MemoryRead`.

- [x] **T3 — Schema + exceptions** (AC 1, 2)
  - [x] T3.1 Dùng `MemoryRead` làm response; không cần schema mới.
  - [x] T3.2 `RevalidationError` trong `app/services/memory/revalidation_service.py` với `code` (`not_revalidatable`, `capability_not_found`, `invalid_recipe`, `workspace_mismatch`, `gate_failed`).

- [x] **T4 — Tests**
  - [x] T4.1 `tests/integration/memory/test_memory_revalidation.py` (mới):
    - [x] Re-validate run-derived memory → output khớp → confidence tăng.
    - [x] Re-validate run-derived memory → output lệch → `MemoryVersion` tạo + confidence giảm.
    - [x] Re-validate chat/manual memory → trả `not_revalidatable`.
    - [x] Re-validate memory với `Run` gốc đã xóa → vẫn chạy được.
    - [x] Re-validate capability có phí → `cost_micros` ghi nhận đúng.
    - [x] Route trả memory update và route reject non-revalidatable.
  - [x] T4.2 Không cần sửa `tests/integration/workspaces/test_memory_routes.py` vì route tests nằm trong `test_memory_revalidation.py`.

- [x] **T5 — Lint / typecheck / test**
  - [x] T5.1 `ruff check app/services/memory/revalidation_service.py app/routes/memories_routes.py app/schemas/memory.py` pass.
  - [x] T5.2 `pytest tests/integration/memory/test_memory_revalidation.py -q` pass (8 tests).
  - [x] T5.3 `pytest tests/integration/memory tests/integration/db tests/integration/workspaces -q` pass (159 tests, không regression).

## Dev Notes

### Files to touch

- `nowing_backend/app/services/memory/revalidation_service.py` (NEW)
- `nowing_backend/app/routes/memories_routes.py` (UPDATE — thêm endpoint)
- `nowing_backend/app/schemas/memory.py` (UPDATE — `RevalidationResult` hoặc chỉ dùng `MemoryRead`)
- `nowing_backend/app/exceptions.py` (UPDATE — thêm `RevalidationError`)
- `nowing_backend/app/services/memory/repository.py` (READ — dùng lại `update_memory`, có thể cần expose `create_version` helper)
- `nowing_backend/app/capabilities/core/store.py` (READ — `get_capability(name)`)
- `nowing_backend/app/capabilities/core/__init__.py` (READ — `execute_with_context`)
- `nowing_backend/app/capabilities/core/billing.py` (READ — `gate_capability`, `charge_capability`)
- `nowing_backend/tests/integration/memory/test_memory_revalidation.py` (NEW)

### Patterns to follow

- Capability invocation:
  ```python
  from app.capabilities.core import execute_with_context
  from app.capabilities.core.store import get_capability
  from app.capabilities.core.types import CapabilityContext
  from app.capabilities.core.billing import gate_capability, charge_capability

  capability = get_capability(memory.source_capability)
  payload = capability.input_schema(**memory.source_input)
  ctx = CapabilityContext(session=session, workspace_id=memory.workspace_id)
  await gate_capability(payload, capability.billing_unit, ctx)
  output = await execute_with_context(capability.executor, payload=payload, ctx=ctx)
  cost_micros = await charge_capability(output, capability.billing_unit, ctx)
  ```
- `source_input` có thể là `None`, `dict`, `list`, hoặc `str` — validate qua `input_schema.model_validate(...)` nếu schema là Pydantic.
- Serialize output: dùng `app/capabilities/core/runs.py:serialize_output(output).text` hoặc `output.model_dump_json()`.
- So sánh content: `memory.content.strip().casefold()` vs `extracted_text.strip().casefold()`. Nếu output là `BaseModel` có `.answer` (như `ResearchOutput`), ưu tiên lấy `.answer`; nếu output là list/items, join first item text.
- Confidence bump/damp: đơn giản, ví dụ:
  - match: `min(1.0, confidence + (1.0 - confidence) * 0.2)`
  - mismatch: `max(0.1, confidence * 0.8)`
- Tạo `MemoryVersion`: dùng `MemoryRepository.update_memory` với `corrected_content` mới, `skip_version_if_unchanged=False`, hoặc tạo `MemoryVersion` trực tiếp rồi gán `memory.content` và `confidence`.

### Risks & How to Mitigate

| Rủi ro | Mitigation |
|---|---|
| Capability gọi lại fail (network, rate limit, 5xx) | Bắt `ExternalServiceError`/capability exceptions → trả `RevalidationResult(status="failed", reason=...)` không throw 500. |
| `source_input` không khớp `input_schema` hiện tại (schema đổi) | `ValidationError` → trả `invalid_recipe`, không cố gắng chạy. |
| Re-validate kéo theo cost lớn | Dùng `gate_capability` trước, từ chối nếu không đủ balance. |
| So sánh chuỗi quá đơn giản | Đủ cho MVP; ghi chú upgrade path: semantic compare hoặc LLM judge. |
| Dead loop: re-validate tạo run mới, run mới trigger auto-extract tạo memory mới | `revalidation_service` không tạo `Run` record? Hoặc nếu tạo `Run` để meter thì không auto-extract từ nó (origin = `revalidate`, không phải `api`/`agent`). |

## Challenge Log (grill-me)

### Q1 — Already implemented?
- Không tìm thấy logic `revalidate` / re-execute nào trong codebase.
- `source_capability` / `source_input` mới chỉ được gán trong `RunMemoryExtractionService` (Story 9.6a) và test; chưa có service nào đọc ngược lại để chạy lại capability.
- **Verdict:** No duplicate. Proceed.

### Q2 — Simpler alternative?
- `app/capabilities/core/async_runner.py:record_and_publish_sync_run` thực hiện gate → execute → charge → record `Run`, **nhưng** nó hard-code gọi `enqueue_run_memory_extraction_after_commit`. Nếu dùng nó cho re-validate, run mới sẽ trigger auto-extract và tạo memory mới → không mong muốn.
- Không có helper "chạy capability theo tên + input" không kèm theo enqueue extraction.
- **Verdict:** Cần viết `RevalidationService` mới, nhưng tái sử dụng `execute_with_context`, `gate_capability`, `charge_capability` có sẵn. No simpler alternative that avoids the extraction side-effect.

### Q3 — Edge cases spec misses
- [ ] `source_input = None` hoặc `source_capability = None` — phải reject `not_revalidatable`.
- [ ] `source_capability` không còn trong registry (capability bị gỡ) — `capability_not_found`.
- [ ] `source_input` không validate được với `input_schema` hiện tại (schema đổi) — `invalid_recipe`.
- [ ] `source_input` là list/string thay vì dict — dùng `input_schema.model_validate(...)`/`model_validate_json` tùy kiểu.
- [ ] Memory thuộc workspace khác (route `workspace_id` mismatch `memory.workspace_id`) — 403.
- [ ] Concurrent `revalidate` trên cùng memory: hai call đọc confidence cũ, cả hai ghi đè. Có thể cần row-level lock hoặc accept eventual consistency ở MVP.
- [ ] `confidence` đã ở biên (`1.0` hoặc rất thấp) — clamp khi bump/damp.
- [ ] Output của capability là async/`chainlens.research` (mặc định async) — sync re-validate có thể timeout. Cân nhắc giới hạn hoặc từ chối re-validate capability async.
- [ ] Capability trả về output structure khác nhau (`ResearchOutput.answer`, scraper `items`, v.v.) — cần hàm `extract_text` thống nhất.

### Q4 — Failure modes unspecified
- [ ] Capability executor raise `ExternalServiceError` / `HTTPException` (network, rate limit, 5xx) → `RevalidationResult(status="failed", reason=...)` không throw 500.
- [ ] `charge_capability` fail sau khi executor success → log, trả kết quả với `cost_micros=None`; không nên để user mất phí mà không nhận kết quả.
- [ ] DB commit fail khi tạo `MemoryVersion` / cập nhật `confidence` → 500, transaction rollback.
- [ ] `Memory` bị xóa giữa chừng (race) → 404.
- [ ] `Run` gốc đã bị xóa (AC chủ đạo của story) — phải vẫn chạy được nhờ recipe trong `Memory`.
- [ ] LLM / embedding service down khi update `content` tạo `MemoryVersion` (do `update_memory` re-embed khi content đổi) → 500.

### Triage
- **No critical finding.** Edge cases và failure modes đều là non-critical. Cần thêm vào test skeleton.
- **Cần clarify:**
  - Memory lệch: **có cập nhật `memory.content` thành nội dung mới** (và re-embed) hay chỉ tạo `MemoryVersion` và giữ `content` cũ? Đề xuất: cập nhật `content` vì `MemoryVersion` đã lưu previous.
  - Permission: dùng `MEMORY_UPDATE` vì ghi `MemoryVersion`/`confidence`.
  - Có cần record một `Run` row cho audit không? Đề xuất: record `Run` với `origin="revalidate"` để có cost/duration log, nhưng **không** enqueue memory extraction.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max (Devin)

### Debug Log References

- `app/services/memory/revalidation_service.py` — red-phase stub → full implementation.
- `tests/integration/memory/test_memory_revalidation.py` — red-phase tests → green.
- `app/routes/memories_routes.py` — `POST .../revalidate` endpoint.

### Completion Notes List

- Quyết định: khi mismatch, cập nhật `memory.content` thành nội dung mới và tạo `MemoryVersion` lưu previous. Điều này trigger re-embed trong `MemoryRepository.update_memory`.
- Permission chọn `MEMORY_UPDATE` vì endpoint ghi `confidence`/`MemoryVersion`.
- Record `Run` với `origin="revalidate"` cho audit cost/duration, nhưng **không** gọi `enqueue_run_memory_extraction_after_commit` để tránh loop.
- `source_input` snapshot có thể là `dict`, `list`, hoặc `None` — validate qua `capability.input_schema.model_validate`.
- So sánh content dùng `_normalize` (casefold + whitespace) đủ cho MVP, đánh dấu `ponytail:` comment cho upgrade path.

### File List

- `nowing_backend/app/services/memory/revalidation_service.py` (NEW + UPDATE)
- `nowing_backend/app/routes/memories_routes.py` (UPDATE)
- `nowing_backend/tests/integration/memory/test_memory_revalidation.py` (NEW)
- `_bmad-output/test-artifacts/atdd-checklist-9-6b.md` (NEW)

