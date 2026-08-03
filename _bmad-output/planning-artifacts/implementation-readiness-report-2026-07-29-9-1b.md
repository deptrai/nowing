---
story: 9-1b-research-contract-regression-guard
status: READY
date: 2026-07-29
---

# Implementation Readiness Report — Story 9.1b

## Tóm tắt

Đã kiểm tra traceability của 6 AC trong Story 9.1b tới PRD §4.9, AD-15, Epics và SCP Winston. 5/6 AC đã có đầy đủ inputs, expected outputs và file references. **4 open items đã được giải quyết bằng code changes (2026-07-29); focused contract tests: 25 passed, 1 skipped.** Trạng thái là `READY`.

## Traceability nhanh

| AC | Nguồn | File/line tham chiếu | Inputs / Expected outputs | Đánh giá |
|---|---|---|---|---|
| **AC-1** Request shape | FR-24, D2, D7, PRD §4.9:579, AD-15:195 | `executor.py:379-390`; T1 `test_executor.py` | `POST {CHAINLENS_API_URL}/api/v1/search` + headers; assert body `{query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId?}`; fail nếu đổi shape. | ✅ Khớp. PRD/AD-15 đã cập nhật `tier`/`stream`. |
| **AC-2** SSE parse | FR-24, D1, D2, D5, PRD §4.9:580, AD-15:195 | `executor.py:96-317`; fixture `chainlens-sse-golden.json` | Data-only frames `block`, `updateBlock` RFC6902 `replace`/`add` trên `/data`, `done`, `error`; parse đúng `chatId`/`webUrl`; fail nếu engine đổi format. | ✅ Khớp với wire thật. |
| **AC-3** Pydantic query | FR-24, D3, PRD §4.9:584 | `schemas.py:63-65`; `executor.py:379-380` | `query > 500` hoặc `query` rỗng/toàn khoảng trắng; Pydantic từ chối trước khi `_call_chainlens`; executor không clamp. | ✅ RESOLVED. Đã thêm `field_validator("query", mode="before")` `_strip_query` trong `schemas.py` và test `test_research_input_rejects_blank_query` trong `test_executor.py`; query toàn khoảng trắng bị từ chối. |
| **AC-4** Source order | FR-24, D4, PRD §4.9:585 | `executor.py:69-93`; `schemas.py:107-110` | Nhiều source; `ResearchOutput.sources[]` giữ đúng thứ tự engine. | ✅ Khớp. |
| **AC-5** Sửa doc / gỡ `event:` | OQ-7, D1, D8, D9, PRD §4.9:578-581, AD-15:195 | `executor.py:143-156`, `151-152`, `325-331`; PRD/AD-15 | PRD/AD-15 ghi data-only frame; docstring `_parse_sse` cập nhật; gỡ/mark defensive nhánh `event:`/`[DONE]`. | ✅ RESOLVED. Đã gỡ bỏ `pending_event_type`/nhánh `event:`/`[DONE]`, cập nhật docstring `_parse_sse`, đổi tên test thành `test_parse_sse_raises_on_error_data_frame` với `_sse_line({"type":"error","data":"upstream boom"}). |
| **AC-6** Fixture sync | OQ-7, D6, Epics:488-491 | ChainLens `apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`; local `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` | Copy fixture; drift test so sánh tại build time. | ✅ RESOLVED. Đã tạo `test_chainlens_fixture_drift.py` với golden fixture validation và drift test tùy chọn so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`. |

## Kiểm tra SCP & Winston

- **SCP 2026-07-29** (`_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-29-9-1b-winston.md`) đã được phản ánh vào Story 9.1b (D3, D5–D9, AC cập nhật), PRD §4.9:579-580 và AD-15:195.
- **Winston review** (`_bmad-output/test-artifacts/9-1b-winston-review.md`) đã thêm Course Correction section, đánh dấu R1–R5 resolved. Finding IR-5 (CI target) đã giải quyết: thêm marker `contract` trong `pyproject.toml` và target `pytest ... -m contract -v`.
- **PRD §4.9** đã cập nhật request shape có `tier`/`stream` và response data-only SSE terminal `{"type":"done"}`.
- **AD-15** đã cập nhật contract tương ứng.
- **Epics** Story 9.1b (`epics.md:462-493`) đã bao quát FR-24, AD-15, OQ-7; các AC trong story mới hơn và chi tiết hơn epic gốc.

## Các open items đã giải quyết

1. **AC3 — Query whitespace**
   - Đã thêm `field_validator("query", mode="before")` `_strip_query` trong `nowing_backend/app/capabilities/chainlens/research/schemas.py` để strip khoảng trắng trước khi `min_length=1` kiểm tra.
   - Đã thêm `test_research_input_rejects_blank_query` trong `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`.
   - Query rỗng hoặc toàn khoảng trắng bị từ chối trước khi `_call_chainlens` chạy.

2. **AC5 — SSE `event:` branch**
   - Đã gỡ `pending_event_type` khỏi `_SSEParser` (`__slots__`, `__init__`, `feed_line`) và các nhánh `event:` / `pending_event_type == "error"` trong `nowing_backend/app/capabilities/chainlens/research/executor.py`.
   - Cập nhật docstring `_parse_sse` thành data-only frames, terminal `{"type":"done"}`.
   - Đổi tên test `test_parse_sse_raises_on_error_event` thành `test_parse_sse_raises_on_error_data_frame` và dùng `_sse_line({"type":"error","data":"upstream boom"})` trong `test_executor.py`.

3. **AC6 — ChainLens fixture sync**
   - Đã tạo `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` là bản sao của `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
   - Đã tạo `nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` với golden fixture validation và drift test tùy chọn so sánh với ChainLens fixture tại build time.

4. **CI target**
   - Đã thêm marker `contract: contract regression tests for ChainLens integration` vào `nowing_backend/pyproject.toml`.
   - Target command: `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.

**Kết quả kiểm thử:** focused contract tests `25 passed, 1 skipped`.

## Khuyến nghị

- **Status:** `READY` (2026-07-29).
- Cập nhật story `9-1b-research-contract-regression-guard.md` sang `status: ready-for-dev` và `sprint-status.yaml`.
- Tất cả open items đã được giải quyết; focused contract tests `25 passed, 1 skipped`.
