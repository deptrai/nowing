---
baseline_commit: 029ba6923
baseline_branch: develop
story_key: 9-6a
status: done
---

# Story 9.6a: Memory Provenance Recipe (nền của re-validation)

**Status:** `done`  
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng  
**Priority:** P0 nếu muốn kể câu chuyện re-validation; không chặn launch (FR-39, AD-11.1)  
**Requirements:** FR-39 (phần provenance) · AD-11.1 · `app/db.py:Memory` · `app/services/memory/run_extraction.py` · `app/services/memory/repository.py`  
**Baseline:** `029ba6923` on `develop`  
**Dependencies:** Story `3.13` done (`RunMemoryExtractionService` đã tồn tại, migration `184` đã thêm `source_run_id`); `9.6b` dep trên `9.6a`.  

## Story

Với tư cách agent hoặc người dùng,  
tôi muốn một memory sinh ra từ dữ liệu scrape trỏ được về đúng lần scrape và chạy lại được truy vấn đó,  
để hệ thống biết fact nào đã cũ thay vì trả về thông tin hết hạn kèm citation trông đáng tin.

## Current Reality / BUILT vs GAP

Tại baseline `029ba6923`:

| Mảnh | Trạng thái | Bằng chứng code |
|---|---|---|
| `Run` lưu `capability` + `input` JSONB | ✅ BUILT | `app/db.py:3203-3207` — `Run.capability = Column(String(100))`, `Run.input = Column(JSONB, nullable=True)` |
| `Run` có TTL 30 ngày, cleanup cơ hội | ✅ BUILT | `app/capabilities/core/runs.py:33` `RUNS_RETENTION_DAYS = 30`; `_maybe_cleanup` trên ~1% insert |
| `Memory` có `source_run_id` UUID soft ref | ✅ BUILT (Story 3.13) | `app/db.py:2105-2111`; migration `184_add_run_memory_provenance.py` |
| `Memory.source_id` là `Integer` | ✅ BUILT | `app/db.py:2104` — dùng cho `document`/`chat_message`, không đổi kiểu |
| `RunMemoryExtractionService` gọi `repo.create_memory` với `source_run_id` | ✅ BUILT | `app/services/memory/run_extraction.py:373-386` |
| `Memory.source_capability` | ❌ GAP | chưa có cột |
| `Memory.source_input` (JSONB snapshot) | ❌ GAP | chưa có cột |
| Code ghi `source_capability`/`source_input` khi tạo memory từ run | ❌ GAP | `run_extraction.py` không truyền |
| `MemoryRepository.create_memory` / `update_memory` nhận recipe | ❌ GAP | `app/services/memory/repository.py:233-250`, `361-378` chưa có tham số |
| `MemoryRead` / `MemorySearchHit` hiển thị recipe | ❌ GAP | `app/schemas/memory.py:43-65`, `142-196` chưa có trường |
| Migration cho `source_capability` + `source_input` | ❌ GAP | head hiện tại là `185_add_token_usage_latency_columns.py`; cần `186` |

**Defect schema đã verify (2026-07-25):**
- `Memory.source_id` là `Integer` (`app/db.py:2077`) còn `Run.id` là `UUID` (`app/db.py:3155`) → không lưu được link bằng `source_id`.
- Không có code nào ghi `MemorySourceType.SCRAPER_RUN` (enum khai báo ở `app/db.py:572` rồi bỏ đó) — **đã sửa** ở Story 3.13.
- `RUNS_RETENTION_DAYS=30` → re-validate hỏng sau một tháng nếu recipe nằm ở `Run`. **AD-11.1 chốt: recipe tự chứa trong `Memory`.**

## Resolved Decisions

### D1 — `Memory` tự chứa recipe theo AD-11.1

- Thêm `source_capability` (String(100), nullable) và `source_input` (JSONB, nullable) vào bảng `memories`.
- Không đặt `ForeignKey` từ `Memory.source_run_id` → `Run.id` — `Run` được phép biến mất sau 30 ngày.
- Không đổi kiểu `Memory.source_id` (Integer) — vẫn dùng cho `document`/`chat_message`.

### D2 — Migration `186_add_memory_provenance_recipe.py`

- `revision = "186"`, `down_revision = "185"`.
- `upgrade()`:
  - `op.add_column("memories", Column("source_capability", sa.String(100), nullable=True))`
  - `op.add_column("memories", Column("source_input", postgresql.JSONB, nullable=True))`
  - Không cần index cho `source_capability`/`source_input` — chưa có truy vấn production nào lọc/group theo chúng.
- `downgrade()` drop 2 cột.

### D3 — `MemoryRepository` nạp và giữ recipe

- `create_memory` thêm `source_capability: str | None = None`, `source_input: Any | None = None`.
- `update_memory` thêm 2 tham số tương tự, nhưng theo AC **chỉ ghi khi memory hiện tại chưa có recipe**:
  - `if source_capability is not None and memory.source_capability is None: memory.source_capability = source_capability`
  - `if source_input is not None and memory.source_input is None: memory.source_input = source_input`
- Lý do: `source_input` là **snapshot bất biến** (epics AC); nếu một run mới trùng nội dung với memory đã có recipe, không mutate recipe cũ. Story `9.6b` sẽ xử lý re-validate bằng `MemoryVersion`.
- `Memory(...)` constructor cũng nhận 2 trường này.
- Nhánh `update_on_duplicate=False` trong `create_memory` (cập nhật metadata memory trùng nội dung) cũng cần gán recipe theo cùng quy tắc.

### D4 — `RunMemoryExtractionService` sao chép recipe vào memory

- Khi tạo memory từ run, truyền:
  - `source_type=MemorySourceType.SCRAPER_RUN`
  - `source_id=None`
  - `source_run_id=run.id`
  - `source_capability=run.capability`
  - `source_input=copy.deepcopy(run.input)` (deep copy để đảm bảo snapshot bất biến — dù `Run.input` thường không mutate, deep copy an toàn hơn).
- Thực hiện ở `RunMemoryExtractionService.extract_from_run`, vòng lặp `for fact in ... repo.create_memory(...)`.

### D5 — Schema hiển thị (tùy chọn nhưng nên làm)

- `MemoryRead` thêm `source_capability: str | None = None`, `source_input: Any | None = None`.
- `MemorySearchHit` thêm `source_capability: str | None = None`, `source_input: Any | None = None` (cập nhật `from_memory`).
- `MemoryCreate` **không** thêm — recipe chỉ được gán nội bộ, không qua REST/MCP.
- Kiểm tra `nowing_evals` client: `MemorySearchHit.from_memory` không chết vì thêm trường (Pydantic cho phép), nhưng các test `test_memories_search_*` có thể cần cập nhật nếu assert đầy đủ payload.

### D6 — Giữ nguyên behavior hiện có

- Không đổi chat-extraction (`app/services/memory/extraction.py:215-227`) — chat memory vẫn dùng `source_type=CHAT_MESSAGE`, `source_id=assistant_message_id`, recipe = `None`.
- Không đổi markdown memory service (`app/services/memory/service.py:205-226`) — vẫn không gán recipe.
- Không đổi `runs` cleanup (`app/capabilities/core/runs.py:303-...`) — cleanup vẫn cơ hội, không join sang `memories`.

## Acceptance Criteria

> Trích từ `epics.md` §Story 9.6a, đã cải chính theo `AD-11.1`.

**Given** `Memory.source_id` là Integer (`app/db.py:2077`) vs `Run.id` UUID (`app/db.py:3155`)  
**When** thêm khả năng re-validate  
**Then** `Memory` có `source_capability` (String), `source_input` (JSONB), `source_run_id` (UUID nullable, không FK cứng)  
**And** `Memory.source_id` (Integer) giữ nguyên cho nguồn `document`/`chat_message` — không đổi kiểu cột đó  
**And** có migration + test không hồi quy cho hai nguồn cũ.

**Given** auto-extract chạy trên một chat turn có kết quả scrape  
**When** tạo memory từ đó  
**Then** set `source_type = SCRAPER_RUN` + sao chép `capability` và `input` từ `Run` vào `Memory` + ghi `source_run_id`.

**Given** `RUNS_RETENTION_DAYS = 30` và cleanup cơ hội `_maybe_cleanup`  
**When** `Run` bị xoá sau 30 ngày  
**Then** memory tham chiếu nó vẫn re-validate được (đã có recipe riêng)  
**And** cleanup `runs` KHÔNG được sửa thành có điều kiện — không join sang `memories`.

**Given** `source_input` là snapshot bất biến  
**When** ai đó muốn đổi truy vấn  
**Then** tạo memory mới, KHÔNG mutate recipe cũ.

## Tasks / Subtasks

- [x] **T1 — Migration `186_add_memory_provenance_recipe.py`** (AC: 1)
  - [x] T1.1 Tạo migration thêm `source_capability` (String 100) + `source_input` (JSONB) trên `memories`.
  - [x] T1.2 Viết `downgrade()` drop 2 cột.
  - [x] T1.3 Migration round-trip test pass (`test_migration_186_roundtrip.py`).

- [x] **T2 — `app/db.py` cập nhật `Memory` model** (AC: 1)
  - [x] T2.1 Thêm `source_capability = Column(String(100), nullable=True)`.
  - [x] T2.2 Thêm `source_input = Column(JSONB, nullable=True)`.

- [x] **T3 — `app/services/memory/repository.py` nhận recipe** (AC: 1, 4)
  - [x] T3.1 `create_memory` thêm `source_capability`, `source_input`.
  - [x] T3.2 `Memory(...)` constructor trong `create_memory` truyền 2 trường.
  - [x] T3.3 `update_memory` thêm 2 tham số, chỉ ghi khi memory chưa có (giữ snapshot bất biến).
  - [x] T3.4 Branch dedup `update_on_duplicate=True` truyền recipe vào `update_memory`.
  - [x] T3.5 Nhánh `update_on_duplicate=False` (`else` trong `create_memory`) cũng gán `source_capability`/`source_input` khi chưa có, vì path này update metadata của memory trùng nội dung.

- [x] **T4 — `app/services/memory/run_extraction.py` sao chép recipe** (AC: 2)
  - [x] T4.1 Truyền `source_capability=run.capability`, `source_input=deepcopy(run.input)` khi gọi `repo.create_memory`.
  - [x] T4.2 `import copy` thêm vào đầu file.

- [x] **T5 — `app/schemas/memory.py` hiển thị recipe** (D5)
  - [x] T5.1 `MemoryRead` thêm `source_capability`, `source_input`.
  - [x] T5.2 `MemorySearchHit` thêm 2 trường + cập nhật `from_memory`.

- [x] **T6 — Tests**
  - [x] T6.1 Migration test `tests/integration/db/test_migration_186_roundtrip.py` verify cột và `downgrade()`.
  - [x] T6.2 `tests/integration/memory/test_run_memory_extraction.py` assert `memory.source_capability == "amazon.scrape"` và `memory.source_input == {"url": "..."}`.
  - [x] T6.3 `tests/integration/memory/test_memory_provenance_recipe.py` (mới) kiểm tra: chat/manual memory `source_capability`/`source_input` là `None`; run memory có recipe; dedup preserve recipe (nếu update đã có recipe thì không ghi đè).
  - [x] T6.4 `tests/integration/workspaces/test_memory_routes.py` kiểm tra search trả về `source_capability`/`source_input`.

- [x] **T7 — Ruff / typecheck / test**
  - [x] T7.1 `ruff check app/db.py app/services/memory/repository.py app/services/memory/run_extraction.py app/schemas/memory.py` — passed.
  - [x] T7.2 `pytest tests/integration/memory tests/integration/db tests/integration/workspaces -q` — 147 passed.

### Review Findings

- [x] [Review][Decision] Migration 186 backfills existing run-derived memories with `source_capability`/`source_input` from their source `Run` where the run still exists — `alembic/versions/186_add_memory_provenance_recipe.py` (applied; added backfill test).
- [x] [Review][Patch] Add test for `RunMemoryExtractionService` when `run.input = None` — `tests/integration/memory/test_memory_provenance_recipe.py` (applied).
- [x] [Review][Patch] Add test verifying `update_memory` with `source_capability=None` does not clear an existing recipe — `tests/integration/memory/test_memory_provenance_recipe.py` (applied).
- [x] [Review][Defer] Test fixtures construct `Memory` objects without new fields (scattered) — deferred, pre-existing
- [x] [Review][Defer] Schema `source_input: Any` loses type safety for API consumers — intentional per spec, deferred

### Re-review Findings (after fixes)

- [x] [Review][Defer] Giới hạn kích thước `source_input` khi lưu vào `Memory` — deferred. Spec định nghĩa `source_input` là snapshot nguyên vẹn của `run.input` để re-execute; thêm cap sẽ phá vỡ tính re-executable. `run.input` là capability args (thường nhỏ), và đã được cắt ngắn bởi `RUN_MEMORY_SOURCE_CHAR_CAP` cho extraction prompt. Đo lường production trước khi thêm giới hạn cứng.
- [x] [Review][Patch] Thêm test migration backfill khi `run.input = None` — `tests/integration/db/test_migration_186_roundtrip.py` (applied).
- [x] [Review][Defer] `Capability.name` không có validation độ dài (pre-existing, `Run.capability` cũng đã là `String(100)`)
- [x] [Review][Dismiss] Manual/chat memory không thể gán recipe — by design, memory chỉ có recipe khi từ run
- [x] [Review][Dismiss] Backfill `UPDATE` không kiểm tra `runs.capability IS NOT NULL` — `Run.capability` là `NOT NULL`

## Dev Notes

### Files to touch

- `nowing_backend/alembic/versions/186_add_memory_provenance_recipe.py` (NEW)
- `nowing_backend/app/db.py` (UPDATE `Memory` model)
- `nowing_backend/app/services/memory/repository.py` (UPDATE `create_memory`, `update_memory`, `Memory` construction)
- `nowing_backend/app/services/memory/run_extraction.py` (UPDATE `extract_from_run`)
- `nowing_backend/app/schemas/memory.py` (UPDATE `MemoryRead`, `MemorySearchHit`)
- `nowing_backend/tests/integration/memory/test_run_memory_extraction.py` (UPDATE)
- `nowing_backend/tests/integration/memory/test_run_memory_provenance_schema.py` (UPDATE hoặc spawn `test_memory_provenance_recipe.py`)
- `nowing_backend/tests/integration/db/test_migration_186_roundtrip.py` (NEW, tương tự `test_migration_184`)

### Patterns to follow

- Migration style: dùng `sa.String(100)` + `postgresql.JSONB`; index không cần thiết.
- `source_run_id` không FK: xem `184_add_run_memory_provenance.py`.
- `JSONB` usage: `from sqlalchemy.dialects.postgresql import JSONB` đã import ở `app/db.py:30`.
- Deep copy: `import copy; source_input=copy.deepcopy(run.input)`.
- Pydantic `Any` cho `source_input`: trong `MemoryRead`/`MemorySearchHit` dùng `Any | None` hoặc `dict | None`; `Run.input` có thể là list/dict.

### Risks & How to Mitigate

| Rủi ro | Mitigation |
|---|---|
| Đổi schema migration ảnh hưởng `source_id` | Giữ `source_id` Integer; không FK mới; test migration round-trip |
| Dedup overwrite làm mất recipe | `update_memory` chỉ ghi recipe khi chưa có (D3) |
| `source_input` lớn / chứa secret | `Run.input` thường là capability args công khai; vẫn deep copy; không expose qua `MemoryCreate` |
| `nowing_evals` client break | Kiểm tra `test_clients.py` sau khi thêm trường; Pydantic `model_validate` bỏ qua trường thừa? Không, `MemorySearchHit` gán tường minh; `MemoryRead` thêm trường sẽ xuất hiện trong response. Có thể cần cập nhật eval client nếu nó assert đủ payload. |
| `source_run_id` UUID string hóa trong schema | Đã có validator `_stringify_run_id`; `source_capability`/`source_input` không cần validator. |

### References

- `epics.md` §Epic 9, Story 9.6a/9.6b (provenance + re-validation).
- `ARCHITECTURE-SPINE.md` AD-11, AD-11.1 (provenance recipe, memory tự chứa recipe).
- `sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (FR-39, AD-11.1).
- `app/db.py:2025-2123` (`Memory` model), `app/db.py:3167-3231` (`Run` model).
- `app/services/memory/run_extraction.py:242-422` (`extract_from_run`).
- `app/services/memory/repository.py:233-415` (`create_memory`, `update_memory`).
- `app/schemas/memory.py:43-196` (`MemoryRead`, `MemorySearchHit`).
- `alembic/versions/184_add_run_memory_provenance.py` (mẫu migration source_run_id).

## Dev Agent Record

### Agent Model Used

- SWE-1.7 Max via `bmad-dev-story` workflow.

### Debug Log References

- 2026-08-02: `test_search_hit_exposes_run_citation` initially failed because `MemorySearchHit.from_memory` now reads `source_capability`/`source_input`; fixed the unit-test helper `_memory_row` to include the new fields.
- 2026-08-02: Full suite `pytest -q` shows 4 unrelated environment failures (CHAINLENS_API_KEY not set, PDF processing fails). These are not caused by this story.

### Completion Notes List

- Added `source_capability` (String 100) and `source_input` (JSONB) to `Memory` model, migration 186, `MemoryRepository`, `RunMemoryExtractionService`, `MemoryRead`, and `MemorySearchHit`.
- Recipe is immutable: `update_memory` and both `create_memory` dedup branches only set recipe when `source_capability`/`source_input` are currently `None`.
- `RunMemoryExtractionService` passes `source_capability=run.capability` and `source_input=copy.deepcopy(run.input)` when creating run-derived memories.
- New integration tests: migration 186 round-trip, run-extraction recipe copy, dedup-preserve, exact-match recipe seeding, route search response.
- Updated existing `test_run_memory_extraction.py` and `test_memory_routes.py` assertions.
- Ruff passed; focused integration suite `tests/integration/memory tests/integration/db tests/integration/workspaces` passed 147/147.

### File List

- `nowing_backend/alembic/versions/186_add_memory_provenance_recipe.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/services/memory/run_extraction.py`
- `nowing_backend/app/schemas/memory.py`
- `nowing_backend/tests/integration/memory/test_run_memory_extraction.py`
- `nowing_backend/tests/integration/memory/test_memory_provenance_recipe.py`
- `nowing_backend/tests/integration/workspaces/test_memory_routes.py`
- `nowing_backend/tests/integration/db/test_migration_186_roundtrip.py`
- `nowing_backend/tests/unit/services/test_memory_run_citation.py`
