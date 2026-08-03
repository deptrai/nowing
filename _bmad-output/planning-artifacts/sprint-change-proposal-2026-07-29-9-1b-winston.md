# Sprint Change Proposal — 9.1b Winston Course Correction (2026-07-29)

**Workflow:** `bmad-correct-course` (batch mode)
**Project:** Nowing
**Date:** 2026-07-29
**Author:** bmad-correct-course
**Status:** APPROVED / IMPLEMENTED
**Story:** `9-1b-research-contract-regression-guard`
**Review:** `_bmad-output/test-artifacts/9-1b-winston-review.md` (Winston, 2026-07-29)

**Artifacts bị ảnh hưởng:**
- `_bmad-output/implementation-artifacts/9-1b-research-contract-regression-guard.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §4.9
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` AD-15
- `_bmad-output/test-artifacts/9-1b-winston-review.md`

---

## 1. Issue Summary

Winston architecture + implementation-readiness review của Story 9.1b (`9-1b-winston-review.md`) đã xác định **3 quyết định kiến trúc chưa chốt** và **2 vấn đề traceability/contract** trước khi dev. Các vấn đề này đều có thể giải quyết bằng cập nhật tài liệu + contract-test spec, **không cần đổi implementation code ngay** (dev sẽ làm sau khi SCP được duyệt).

| # | Vấn đề | Nguồn | Cách chốt |
|---|---|---|---|
| **1** | Query clamp vs. Pydantic schema: executor có nên clamp? | `schemas.py:63-65`, `executor.py:379-380` | Pydantic là cổng chặn duy nhất; executor không clamp. |
| **2** | Fixture sync với ChainLens 42-2: làm thế nào để tránh viết fixture thứ hai? | `nowing-sse-parser.ts` (ChainLens repo) | Copy fixture vào `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` + drift test tại build time. |
| **3** | Request body `tier`/`stream`: có thuộc contract không? | `executor.py:382,385`, PRD §4.9:579, AD-15:195 | Giữ nguyên trong code; cập nhật PRD/AD-15; thêm contract test assert body chính xác. |
| **4** | Docstring `_parse_sse` lỗi thời | `executor.py:325-331` | Cập nhật docstring trong dev: data-only frame, terminal `{"type":"done"}`. |
| **5** | RFC6902 patch thủ công vs. thư viện | `executor.py:192-202`, `nowing-sse-parser.ts` | Giữ thủ công `replace`/`add` trên `/data`; khoá bằng contract test từ fixture. Chuyển sang `rfc6902`/`jsonpatch` nếu fixture xuất hiện thêm op/path. |

---

## 2. Impact Analysis

### 2.1 Story / Epic Impact

| Story | Ảnh hưởng |
|---|---|
| **9-1b** | Resolved Decisions được mở rộng (D3, D5, D6, D7, D8, D9); AC-1/3/5/6 được điều chỉnh; task T1/T3/T5/T6 được cập nhật; test matrix phản ánh Pydantic gate, fixture drift, `tier`/`stream`. |
| **9-2 (cost metering)** | Không đổi scope. Contract data-only SSE giữ nguyên, `costDollars` event vẫn được parse theo FR-37. |
| **9-3 (latency/State A/B)** | Không đổi. `tier`/`stream` không ảnh hưởng latency framing. |

### 2.2 Artifact Impact

| Artifact | Thay đổi |
|---|---|
| Story 9.1b | Thêm D5–D9; D3 chuyển từ executor clamp sang Pydantic gate; AC-1/3/5/6 cập nhật; trạng thái IR → `READY-FOR-DEV` sau approval. |
| PRD §4.9 | Request shape thêm `tier`, `stream`; Response đổi từ `event:`/`data:[DONE]` sang data-only SSE frames; AC query đổi sang Pydantic validation. |
| AD-15 | Request shape thêm `tier`, `stream`; Response đổi sang data-only SSE, terminal `{"type":"done"}`. |
| Winston review | Thêm section Course Correction ghi các findings đã resolved. |

### 2.3 Technical Impact

- **Không cần deploy code ngay.** Đây là artifact correction + SCP batch.
- **Dev cần làm sau khi SCP approved:**
  - Cập nhật docstring `_parse_sse` trong `executor.py`.
  - Viết contract test request shape với `tier`/`stream`.
  - Copy fixture ChainLens + drift test.
  - Giữ logic RFC6902 thủ công, không thêm clamp query.

---

## 3. Recommended Approach

1. **Approve SCP batch này** để artifacts phản ánh đúng contract thật.
2. **Chấp nhận các quyết định đã chốt:**
   - Pydantic gate duy nhất cho `query`.
   - Fixture copy + drift test thay vì chờ ChainLens export golden JSON.
   - `tier`/`stream` là một phần của contract.
   - Manual `replace`/`add` RFC6902 là đủ cho hiện tại.
   - Docstring `_parse_sse` phải cập nhật khi dev.
3. **Implementation handoff** giao cho backend team theo story 9.1b đã chỉnh sửa.

---

## 4. Detailed Change Proposals

### Change 1 — Story 9.1b: Resolved Decisions D3, D5, D6, D7, D8, D9

**Artifact:** `_bmad-output/implementation-artifacts/9-1b-research-contract-regression-guard.md`

**Before (D3 cũ):**
> ### D3 — Query > `MAX_QUERY_LENGTH` phải bị clamp trước khi gọi engine
> - Executor phải đảm bảo `query` trong body HTTP không vượt 500 ký tự.
> - Query rỗng sau khi clamp (hoặc input rỗng) phải không gửi đến engine.

**After (D3 mới):**
> ### D3 — Pydantic schema là cổng chặn duy nhất cho `query`
> - `ResearchInput.query` đã có `min_length=1, max_length=500`.
> - Executor **không** thêm clamp thủ công; Pydantic từ chối `query > 500` và `query < 1` trước khi `_call_chainlens` chạy.
> - Query rỗng không bao giờ vào executor.

**Before (AC-3 cũ):**
> Query dài bị clamp về ≤ 500 trước khi gửi; query rỗng sau clamp không gửi đến engine.

**After (AC-3 mới):**
> Pydantic `ResearchInput.query` (`min_length=1, max_length=500`) từ chối `query > 500` và `query` rỗng/toàn khoảng trắng; executor không clamp thêm.

**Before (AC-1 cũ):**
> Test xác nhận body chứa đúng các trường `{query, optimizationMode, sources, history, systemInstructions?, chatId?, tier, stream}`.

**After (AC-1 mới):**
> Test assert body chính xác `{query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId?}` — bao gồm `tier` và `stream`.

**Before (AC-6 cũ):**
> Tham chiếu/đồng bộ fixture `nowing-sse-parser.ts`; đề xuất ChainLens export golden JSON.

**After (AC-6 mới):**
> Copy fixture `nowing-sse-parser.ts` vào `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và thêm drift test tại build time.

---

### Change 2 — PRD §4.9: Request shape + data-only SSE

**Artifact:** `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (lines 579-580, 584)

**Before:**
> - Request: `{ query, optimizationMode, sources, history, systemInstructions?, chatId? }`.
> - Response: block-based SSE (`event:`/`data:`, `type:block` / `type:updateBlock` RFC6902 patch, `data:[DONE]`, `event:error`) → `{ answer, sources[] }`.
> - Query dài > 500 ký tự bị clamp trước khi gọi.

**After:**
> - Request: `{ query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId? }` — `tier: "research"` và `stream: true` là một phần của contract.
> - Response: data-only SSE frames (`data: <json>\n\n`); `type` nằm trong JSON payload; terminal thật là `{"type":"done", ...}` — **không** có `event:` hay `data:[DONE]`.
> - Query được kiểm soát bởi Pydantic `ResearchInput.query` (`min_length=1, max_length=500`); executor không clamp thêm.

---

### Change 3 — AD-15: Request shape + data-only SSE

**Artifact:** `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (line 195)

**Before:**
> Request `{ query, optimizationMode, sources, history, systemInstructions?, chatId? }`. Response block-based SSE (`event:`/`data:`, `type:block` / `type:updateBlock` RFC6902, `data:[DONE]`, `event:error`) → `{ answer, sources[] }`.

**After:**
> Request `{ query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId? }` — `tier: "research"` và `stream: true` là một phần của contract. Response là data-only SSE frames (`data: <json>\n\n`); `type` nằm trong JSON payload; terminal thật là `{"type":"done", ...}` — **không** có `event:` hay `data:[DONE]`.

---

### Change 4 — Winston Review: Ghi nhận resolved findings

**Artifact:** `_bmad-output/test-artifacts/9-1b-winston-review.md`

**Change:** Thêm section **Course Correction (2026-07-29)** liệt kê 5 findings từ IR/CA đã được chốt bởi SCP này:
- R1 wire-format mismatch / docstring → resolved (D9).
- R2 request-shape drift (`tier`/`stream`) → resolved (D7).
- R3 query clamp/schema conflict → resolved (D3).
- R4 RFC6902 patch divergence → resolved (D5).
- R5 fixture drift với ChainLens 42-2 → resolved (D6).

---

### Change 5 — SCP §3 (ChainLens engine boundary) — Không thay đổi

**Artifact:** `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` §3

**Reasoning:** SCP §3 chỉ chứa bảng impact ở mức epic/section; không mô tả chi tiết SSE format hay request shape. Các chi tiết contract nằm ở PRD §4.9 và AD-15. Do đó **không cần chỉnh sửa** SCP §3 cho story 9.1b.

---

## 5. Implementation Handoff

### Artifacts đã cập nhật
- `_bmad-output/implementation-artifacts/9-1b-research-contract-regression-guard.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `_bmad-output/test-artifacts/9-1b-winston-review.md` (sắp thêm)
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-29-9-1b-winston.md` (file này)

### Việc cần làm tiếp theo (sau khi SCP approved)

| Owner | Task | Acceptance |
|---|---|---|
| Backend | Viết contract test request shape với `tier`/`stream` (T1) | Pass `test_executor.py`; fail khi body shape thay đổi. |
| Backend | Viết contract test SSE từ `chainlens-sse-golden.json` (T2) | Pass data-only block/updateBlock/done/error. |
| Backend | Copy `nowing-sse-parser.ts` → `chainlens-sse-golden.json` + drift test (T6) | Drift test đỏ nếu fixture lệch. |
| Backend | Cập nhật docstring `_parse_sse`, gỡ/mark `event:`/`[DONE]` (T5) | Docstring đúng data-only frame; parser không dựa `event:`. |
| QA/CI | Đảm bảo contract test chạy trong CI workflow. | CI fail nếu engine đổi format. |
| PO | Approve SCP batch | Trạng thái story chuyển sang `ready-for-dev`. |

### Cách tiếp cận ưu tiên (ponytail)
- **Không** thêm clamp query trong executor; dựa vào Pydantic.
- **Không** thêm dependency `rfc6902`/`jsonpatch` trừ khi fixture thật sự có thêm op/path.
- **Không** tự viết fixture SSE thứ hai; luôn copy từ ChainLens fixture.
- **Không** sửa PRD/AD-15 ngoài request shape + data-only SSE; tránh scope creep.

---

## 6. Resolution Log (2026-07-29)

Các open items trong `implementation-readiness-report-2026-07-29-9-1b.md` đã được giải quyết bằng code changes:

1. **AC3 — query whitespace:** Thêm `field_validator("query", mode="before")` `_strip_query` vào `nowing_backend/app/capabilities/chainlens/research/schemas.py`; thêm `test_research_input_rejects_blank_query` vào `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`.
2. **AC5 — SSE `event:` branch:** Gỡ `pending_event_type` khỏi `_SSEParser` (`__slots__`, `__init__`, `feed_line`) và các nhánh `event:` / `pending_event_type == "error"`; cập nhật docstring `_parse_sse` thành data-only frames; đổi tên `test_parse_sse_raises_on_error_event` thành `test_parse_sse_raises_on_error_data_frame` dùng `_sse_line({"type":"error","data":"upstream boom"})`.
3. **AC6 — ChainLens fixture sync:** Tạo `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và `nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` với golden fixture validation và drift test tùy chọn so với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
4. **CI target:** Thêm marker `contract: contract regression tests for ChainLens integration` vào `nowing_backend/pyproject.toml`; command `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.

Command đã chạy:
```bash
uv run --active python -m pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v
```
Kết quả: **25 passed, 1 skipped**.

## 7. Approval

**Proposed by:** bmad-correct-course
**Date:** 2026-07-29
**Decision:** APPROVED / IMPLEMENTED
