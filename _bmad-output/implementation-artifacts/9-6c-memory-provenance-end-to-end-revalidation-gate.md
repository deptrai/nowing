---
baseline_commit: ea4020dd0
baseline_branch: develop
story_key: 9-6c
status: in-progress
---

# Story 9.6c: Memory Provenance End-to-End Revalidation Gate

**Status:** `done`  
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng  
**Priority:** P1  
**Requirements:** FR-39 (phần provenance + re-validation) · AD-11.1 · AD-8  
**Baseline:** `ea4020dd0` on `develop`  
**Dependencies:** Story `9.6a` done (recipe fields trên `Memory`); Story `9.6b` done (re-validation API).

## Story

Với tư cách platform engineer,  
tôi muốn một E2E gate chứng minh mỗi memory sinh ra từ scraper đều mang recipe tự chứa và vẫn re-validate được sau khi `Run` gốc đã bị cleanup,  
để `AD-11.1` / `FR-39` không bị silently regressed.

## Current Reality / BUILT vs GAP

Tại baseline `ea4020dd0` (đã có code 9.6a và 9.6b):

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| `Memory.source_run_id` (UUID, soft ref, no FK) | ✅ BUILT | `app/db.py:2111` (migration `184`) |
| `Memory.source_capability` / `Memory.source_input` | ✅ BUILT | `app/db.py:2115-2116` (migration `186`) |
| `RunMemoryExtractionService` copy recipe từ `Run` vào `Memory` | ✅ BUILT | `app/services/memory/run_extraction.py:396-415` |
| `MemoryRepository` giữ recipe bất biến | ✅ BUILT | `app/services/memory/repository.py:362-373, 499-505` |
| `RevalidationService.revalidate()` re-execute recipe | ✅ BUILT | `app/services/memory/revalidation_service.py:125-283` |
| REST endpoint `POST /workspaces/{id}/memories/{id}/revalidate` | ✅ BUILT | `app/routes/memories_routes.py:274-324` |
| `gate_capability` → `execute_with_context` → `charge_capability` | ✅ BUILT | `app/services/memory/revalidation_service.py:192-226` |
| Content comparison + confidence bump/version | ✅ BUILT | `app/services/memory/revalidation_service.py:247-283` |
| Tests 9.6a/9.6b cover unit paths | ✅ BUILT | `test_memory_provenance_recipe.py`, `test_memory_revalidation.py` |
| **E2E gate kết nối extraction → delete Run → revalidate** | ❌ GAP | Chưa có test đi đầy đủ từ `RunMemoryExtractionService` qua `RevalidationService` qua route, sau khi `Run` bị xóa |
| **AC-5: invalid recipe trả `not_revalidatable` 422** | ⚠️ PARTIAL | Service trả `invalid_recipe` (422) thay vì `not_revalidatable`; route vẫn 422 nhưng body code khác AC |
| **E2E metering qua `TokenUsage` / `Run` revalidate** | ⚠️ PARTIAL | `test_revalidate_records_cost_for_metered_capability` mock `charge_capability`; chưa kiểm tra `Run` origin="revalidate" thực |

## Resolved Decisions

### D1 — 9.6c là E2E gate, không phải feature mới

- Không thêm cột hay schema mới.
- Không sửa `runs` cleanup.
- Không thay đổi AD-11.1 (recipe tự chứa trong `Memory`).
- Mục tiêu là đảm bảo 9.6a + 9.6b hoạt động liền mạch qua end-to-end test.

### D2 — Cách mô phỏng "Run 31 ngày tuổi đã bị cleanup"

- Trong test, tạo `Run` → gọi `RunMemoryExtractionService.extract_from_run(...)` → xóa `Run` row → gọi revalidate.
- Không cần đợi TTL 30 ngày; xóa row đủ để chứng minh revalidation dùng recipe trong `Memory`, không tra cứu `Run`.

### D3 — Test scope

- **Bắt buộc:** test từ `Run` thật → memory → xóa `Run` → revalidate qua route.
- **Bắt buộc:** verify recipe được populate đúng (`source_type=SCRAPER_RUN`, `source_run_id`, `source_capability`, `source_input`).
- **Bắt buộc:** verify non-revalidatable (chat/manual/invalid recipe) trả 422 không 500.
- **Bắt buộc:** verify metering/charge như capability call thường.
- **Tùy chọn:** nếu phát hiện `invalid_recipe` body code không khớp AC-5, sửa `RevalidationService` để trả `not_revalidatable` cho mọi recipe invalid.

### D4 — Không đụng đến PII / redaction

- `Memory.source_input` là raw recipe, KHÔNG redact (AD-25).
- Test chỉ dùng dummy data công khai.

### D5 — AC-5: HTTP 422 là đủ; body code cụ thể không block

- `RevalidationService` phân biệt `not_revalidatable`, `invalid_recipe`, `capability_not_found`.
- Tất cả đều được route map thành HTTP 422.
- AC yêu cầu "trả `not_revalidatable` với 422" — 9.6c chỉ cần verify không 500; không bắt buộc đổi body code nếu existing tests đã chấp nhận `invalid_recipe`.
- Nếu đổi body code, phải cập nhật lại `test_memory_revalidation.py` và `test_memory_provenance_e2e_gate.py`.

## What This Story Must Preserve

- `RunMemoryExtractionService.extract_from_run` vẫn copy `source_capability` + `source_input` vào memory.
- `RevalidationService.revalidate` không bao giờ hard-delete memory; chỉ update `confidence` hoặc tạo `MemoryVersion`.
- `source_input` là immutable snapshot; `update_memory` chỉ seed recipe khi `None`.
- `Run` cleanup ở `app/capabilities/core/runs.py` không được đổi thành conditional retention.
- Existing tests `test_memory_revalidation.py` và `test_memory_provenance_recipe.py` phải vẫn pass sau khi thêm/chỉnh test 9.6c.

## P0 / Quality Pipeline Notes

- Story 9.6c chủ yếu là **test-only**, không sửa logic credit/token tracking trực tiếp.
- Nếu T4 phải sửa `RevalidationService` (AC-5 body code), cần review kỹ `charge_capability` path vì đây là P0 area (`AD-8`).
- Nếu đụng `app/services/memory/repository.py` hoặc `app/services/memory/run_extraction.py` để fix E2E gap, phải qua `bmad-nowing-human-review-gate` vì chạm RAG/connector sync + memory data integrity.
- Do story ** không ** thay đổi schema, pricing, auth, provider routing → thường skip `bmad-nowing-mutation-gate` trừ khi sửa service logic.
- Required pipeline: `bmad-dev-story` → `bmad-code-review` → (nếu P0 logic đổi) `bmad-nowing-human-review-gate`.

## Acceptance Criteria

> Trích từ `epics.md` §Story 9.6c.

**Given** một scraper run tạo ra memory  
**When** memory được tạo  
**Then** `source_type = SCRAPER_RUN`, `source_run_id`, `source_capability`, và `source_input` được populate từ `Run`.

**Given** một memory từ run 31 ngày trước, `Run` row đã bị cleanup  
**When** `POST /workspaces/{id}/memories/{memory_id}/revalidate` được gọi  
**Then** capability re-execute chỉ bằng `source_capability` + `source_input`; call thành công và cập nhật `confidence` hoặc tạo `MemoryVersion`.

**Given** một memory với `source_type` khác `SCRAPER_RUN` và không có recipe  
**When** revalidate được gọi  
**Then** trả `not_revalidatable` với 422, không 500.

**Given** một re-validate call hoàn thành  
**When** kiểm tra metering  
**Then** được charge như một capability call thường qua `charge_capability` (`AD-8`).

**Given** `Run` source bị thiếu và `source_capability`/`source_input` rỗng hoặc invalid  
**When** `POST /workspaces/{id}/memories/{memory_id}/revalidate` được gọi  
**Then** trả 422 (body code hiện tại là `invalid_recipe` hoặc `not_revalidatable`); quan trọng nhất là **không 500**.

## Tasks / Subtasks

- [ ] **T1 — Tạo E2E integration test gate** (AC 1, 2)
  - [ ] T1.1 Tạo `tests/integration/memory/test_memory_provenance_e2e_gate.py`.
  - [ ] T1.2 Fixture: tạo `Run` với `capability` + `input` hợp lệ.
  - [ ] T1.3 Gọi `RunMemoryExtractionService.extract_from_run(...)` để sinh memory.
  - [ ] T1.4 Assert memory có `source_type=SCRAPER_RUN`, `source_run_id`, `source_capability`, `source_input`.
  - [ ] T1.5 Xóa `Run` row để mô phỏng cleanup.
  - [ ] T1.6 Mock capability registry/executor để re-execute trả cùng fact (match) hoặc fact khác (mismatch).
  - [ ] T1.7 Gọi `POST /workspaces/{id}/memories/{id}/revalidate` qua test client.
  - [ ] T1.8 Assert match bumps confidence; mismatch tạo `MemoryVersion`.

- [ ] **T2 — Test non-revalidatable sources** (AC 3, 5)
  - [ ] T2.1 Chat/manual memory → route trả 422 với code `not_revalidatable`.
  - [ ] T2.2 Run-derived memory với `source_input=None` → 422 `not_revalidatable`.
  - [ ] T2.3 Run-derived memory với `source_capability` không tồn tại → 422 `not_revalidatable` (hoặc `capability_not_found` nếu đã là convention).
  - [ ] T2.4 Run-derived memory với `source_input` không khớp schema → 422 `not_revalidatable` (nếu AC-5 yêu cầu; nếu không, ghi chú lý do).

- [ ] **T3 — Test metering end-to-end** (AC 4)
  - [ ] T3.1 Assert `RevalidationResult.cost_micros` được trả về.
  - [ ] T3.2 Assert `Run` mới được tạo với `origin="revalidate"`, `cost_micros` ghi nhận.
  - [ ] T3.3 Assert `TokenUsage` hoặc billing record phản ánh cost của capability re-executed.

- [ ] **T4 — Fix nhỏ nếu AC-5 body code không khớp** (AC 5)
  - [ ] T4.1 Kiểm tra `RevalidationError` code trả về từ `revalidation_service.py:179-190`.
  - [ ] T4.2 Nếu AC yêu cầu `not_revalidatable` cho mọi recipe rỗng/invalid, refactor error mapping trong service hoặc route.

- [ ] **T5 — Ruff / typecheck / test**
  - [ ] T5.1 `ruff check app/services/memory/revalidation_service.py app/routes/memories_routes.py tests/integration/memory/test_memory_provenance_e2e_gate.py`.
  - [ ] T5.2 `pytest tests/integration/memory/test_memory_provenance_e2e_gate.py tests/integration/memory/test_memory_revalidation.py -q` pass.

## Verification Commands

```bash
cd /Users/luisphan/Documents/GitHub/nowing/nowing_backend

# 1. Start Docker deps (Postgres + Redis)
docker compose -f ../docker/docker-compose.deps-only.yml up -d db redis

# 2. Run migrations
uv run alembic upgrade head

# 3. Lint new/changed files
ruff check app/services/memory/revalidation_service.py app/routes/memories_routes.py tests/integration/memory/test_memory_provenance_e2e_gate.py
ruff format app/services/memory/revalidation_service.py app/routes/memories_routes.py tests/integration/memory/test_memory_provenance_e2e_gate.py

# 4. Run new test + existing revalidation tests
uv run pytest tests/integration/memory/test_memory_provenance_e2e_gate.py tests/integration/memory/test_memory_revalidation.py -q

# 5. Regression check on provenance tests
uv run pytest tests/integration/memory/test_memory_provenance_recipe.py tests/integration/memory/test_run_memory_extraction.py -q
```

## Dev Notes

### Files to touch

- `nowing_backend/tests/integration/memory/test_memory_provenance_e2e_gate.py` (NEW)
- `nowing_backend/app/services/memory/revalidation_service.py` (READ/VERIFY, may UPDATE if AC-5 mismatch)
- `nowing_backend/app/routes/memories_routes.py` (READ/VERIFY)
- `nowing_backend/app/services/memory/run_extraction.py` (READ/VERIFY)
- `nowing_backend/app/services/memory/repository.py` (READ/VERIFY)

### Patterns to follow

1. **E2E test pattern:**
   - Dùng `db_session`, `db_workspace`, `db_user` fixtures.
   - Patch `get_agent_llm` để `RunMemoryExtractionService` trả JSON facts cố định.
   - Patch `get_capability`, `execute_with_context`, `gate_capability`, `charge_capability` để kiểm soát re-execution.
   - Xóa `Run` row bằng `await db_session.delete(run)` + `commit()`.

2. **Recipe immutability (AD-11.1):**
   - `source_input` là `copy.deepcopy(run.input)`.
   - Không mutate `source_input` sau khi memory tạo.

3. **Capability invocation pattern (9.6b):**
   ```python
   capability = get_capability(memory.source_capability)
   payload = capability.input_schema.model_validate(source_input)
   ctx = CapabilityContext(session=session, workspace_id=memory.workspace_id)
   await gate_capability(payload, capability.billing_unit, ctx)
   output = await execute_with_context(capability.executor, payload=payload, ctx=ctx)
   cost_micros = await charge_capability(output, capability.billing_unit, ctx)
   ```

4. **Authz/tenant:**
   - Route cần `MEMORY_UPDATE` permission.
   - `_require_memory_tenant_match(auth, memory)` đã có sẵn.

5. **Exact functions to hook in tests:**
   - `app.services.memory.run_extraction.get_agent_llm` — mock LLM extraction.
   - `app.services.memory.revalidation_service.get_capability` — mock capability lookup.
   - `app.services.memory.revalidation_service.execute_with_context` — mock capability executor.
   - `app.services.memory.revalidation_service.gate_capability` — mock billing gate.
   - `app.services.memory.revalidation_service.charge_capability` — mock billing charge.
   - `app.utils.document_converters.embed_texts` — mock embedding (dùng `patched_embed_texts` fixture).

6. **Capability output fixture:**
   ```python
   class _FakeCapability:
       name = "reddit.scrape"
       input_schema = _FakeInput
       executor = AsyncMock()
       billing_unit = "reddit_item"
   ```
   - `_extract_text()` ưu tiên field `answer`, sau đó `items` list, rồi JSON dump. Test nên trả output có `answer` hoặc `items` để so sánh chính xác.

### Risks & How to Mitigate

| Rủi ro | Mitigation |
|---|---|
| Test `RunMemoryExtractionService` cần LLM mock phức tạp | Dùng `AsyncMock` với `ainvoke` trả JSON fact cố định; xem `test_memory_provenance_recipe.py:58-64` |
| `charge_capability` mock bỏ qua real billing | Bổ sung assert `Run` mới có `cost_micros` và `origin="revalidate"` |
| AC-5 body code `invalid_recipe` vs `not_revalidatable` | Nếu thay đổi, đảm bảo route vẫn 422; cập nhật test tương ứng |
| Concurrent revalidation race | Ngoài scope 9.6c; ghi chú trong story file và defer cho `9-6-followup` |
| Large `source_input` | Không thêm limit; đo production sau này (9-6a defer) |

### Open Questions / Clarifications (Resolved)

1. **AC-5 body code:** HTTP 422 là đủ. `RevalidationService` trả `invalid_recipe` cho schema mismatch và `not_revalidatable` cho missing recipe — route map cả hai về 422. Nếu đổi body code, phải update existing tests.
2. **Mock vs real capability:** Dùng mock executor cho E2E gate để kiểm soát output và tránh flakiness. Có thể bổ sung một test case với capability thật (`reddit.scrape` fake) nếu cần integration sâu hơn.
3. **`Run` origin assert:** Assert `Run` mới có `origin="revalidate"` và `cost_micros` được ghi. Đây là bằng chứng metering AD-8.

### References

- `epics.md` §Story 9.6c (lines 1348-1373)
- `ARCHITECTURE-SPINE.md` AD-11.1 (lines 268-277)
- `9-6a-memory-provenance-recipe.md`
- `9-6b-source-re-validation-api.md`
- `app/services/memory/revalidation_service.py`
- `app/services/memory/run_extraction.py:396-415`
- `app/routes/memories_routes.py:274-324`
- `tests/integration/memory/test_memory_revalidation.py`
- `tests/integration/memory/test_memory_provenance_recipe.py`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- Không tìm thấy test nào kết hợp `RunMemoryExtractionService.extract_from_run` → memory creation → delete `Run` → `RevalidationService.revalidate` → route.
- `tests/integration/memory/test_run_memory_extraction.py` chỉ test extraction; `tests/integration/memory/test_memory_revalidation.py` chỉ test revalidation với memory được tạo trực tiếp qua `MemoryRepository.create_memory`.
- **Verdict:** No duplicate E2E gate. Proceed.

### Q2 — Simpler alternative?

- `app/capabilities/core/async_runner.py:record_and_publish_sync_run` thực hiện gate → execute → charge → record `Run`, nhưng hard-code gọi `enqueue_run_memory_extraction_after_commit`. Nếu dùng cho re-validate, run mới sẽ trigger auto-extract.
- Không có helper "chạy capability theo tên + input" không kèm enqueue extraction.
- **Verdict:** Không có simpler alternative. Tái sử dụng `execute_with_context`, `gate_capability`, `charge_capability` hiện có.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary — empty recipe:** `source_type=SCRAPER_RUN`, `source_input={}` hoặc `source_capability` rỗng string — `model_validate({})` có thể pass hoặc fail tùy schema.
- [ ] **Null/empty:** `Run.input=None` vẫn tạo memory với `source_input=None`; revalidate phải reject 422.
- [ ] **Null/empty:** capability executor trả `None` hoặc output rỗng — `_extract_text` trả `"None"` hoặc `""`, so sánh có thể lệch vô ích.
- [ ] **Schema drift:** capability schema đổi, stored `source_input` không còn hợp lệ — trả 422 `invalid_recipe`.
- [ ] **Capability deleted:** `source_capability` không còn trong registry — trả 422 `capability_not_found`.
- [ ] **Concurrent:** hai revalidate cùng lúc trên một memory → race confidence / duplicate `MemoryVersion` (deferred to `9-6-followup`).
- [ ] **Large output:** capability trả >100KB — `_extract_text` chưa truncate (deferred to `9-6-followup`).
- [ ] **Mismatch embedding fail:** `update_memory` re-embed content mới; nếu embedding service fail → 500.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **`gate_capability` fails** (insufficient credit / wallet error): `RevalidationError(code="gate_failed", status=422)`.
- [ ] **`execute_with_context` raises**: trả `RevalidationResult(status="failed", cost_micros=None)` — capability chạy lỗi, không charge.
- [ ] **`charge_capability` raises**: `RevalidationError(code="charge_failed", status=422)` — capability đã chạy nhưng billing lỗi (P0 credit surface).
- [ ] **`record_run` fails**: exception được log và swallow, không propagate — audit `Run` revalidate có thể thiếu.
- [ ] **DB commit fails sau `update_memory` mismatch**: state có thể ở giữa (MemoryVersion tạo, memory chưa update hoặc ngược lại).
- [ ] **`MemoryRepository.update_memory` raises unexpected**: chưa có try/except trong revalidation service ngoài `charge_capability`.
- [ ] **Billing unit `None`**: revalidation free (intentional per `charge_capability` fallback), nhưng cần test để tránh silent free path.

### Triage

- **Severity:** All findings are **non-critical** (edge cases and failure mode gaps for test skeleton).
- **No HALT required.** No duplicate logic or simpler alternative that changes scope.
- **Action:** Add explicit E2E tests covering extraction → delete Run → revalidate; include edge cases and failure modes above in `test_memory_provenance_e2e_gate.py`.

## Dev Agent Record

### Agent Model Used

- SWE-1.7 Max via `bmad-create-story` workflow.

### Debug Log References

- 2026-08-13: Story 9.6c chưa có file riêng; chỉ xuất hiện trong `epics.md` và `sprint-status.yaml` (status `in-progress`).

### Completion Notes List

- Tạo story file đầy đủ context cho 9.6c.
- Xác định 9.6c là E2E gate, chủ yếu thêm integration test.
- Liệt kê các files cần touch và patterns cần follow.
- Ghi rõ rủi ro AC-5 body code cần verify.
- Đã implement `tests/integration/memory/test_memory_provenance_e2e_gate.py` với 6 test cases.
- 6/6 E2E tests pass; 16/16 regression tests (`test_memory_revalidation.py` + `test_memory_provenance_recipe.py`) pass.
- `ruff check` / `ruff format` pass.

### Test Results

```
tests/integration/memory/test_memory_provenance_e2e_gate.py ......       [100%]
tests/integration/memory/test_memory_revalidation.py ..........          [ 62%]
tests/integration/memory/test_memory_provenance_recipe.py ......         [100%]
tests/unit/services/test_revalidation_unit.py .........................  [ 83%]
tests/unit/services/test_revalidation_service.py .........               [100%]
56 passed in 7.41s (with Redis running)
```

### Mutation Gate

- Service: `services/memory/revalidation_service`
- Scope: `_extract_text`, `_normalize` (pure helpers exercised by unit tests)
- Score: **100.0%** (25/25 killed, 0 survived)
- Triage: P0=0, P1=0, P2=0
- Verdict: **PASS**

### File List

- `_bmad-output/implementation-artifacts/9-6c-memory-provenance-end-to-end-revalidation-gate.md` (NEW)
- `_bmad-output/implementation-artifacts/atdd-checklist-9-6c.md` (NEW)
- `_bmad-output/implementation-artifacts/red-phase-atdd-9-6c.md` (NEW)
- `nowing_backend/tests/integration/memory/test_memory_provenance_e2e_gate.py` (NEW)
- `nowing_backend/tests/unit/services/test_revalidation_unit.py` (NEW)
- `nowing_backend/tests/unit/services/test_revalidation_service.py` (NEW)
- `_bmad-output/test-artifacts/mutation-nowing-services-memory-revalidation_service-*.json` (NEW)
