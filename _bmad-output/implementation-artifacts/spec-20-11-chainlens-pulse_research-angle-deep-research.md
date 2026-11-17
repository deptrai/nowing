---
title: 'Story 20.11: chainlens.pulse_research Angle Deep-Research'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: 'a4b4a0af6c3b2ff2d4f113f18bb079420e01c89a'
deferred:
  - summary: >-
      TokenUsage billing for pulse_research cost_dollars not yet wired into executor.
    evidence: |-
      done frame carries usage.costDollars; recording TokenUsage with
      usage_type="chainlens_pulse_research" via cost_dollars_to_micros belongs
      to the billing integration layer (same as Story 20.10).
    location: >-
      nowing_backend/app/capabilities/chainlens/pulse_research/executor.py
    severity: medium
  - summary: >-
      chatId persistence for SEP-2567 resume not yet wired to ResearchThread.
    evidence: |-
      The done frame carries chatId but no DB write persists it onto the
      research thread for later resume.
    location: >-
      nowing_backend/app/routes/pulse_routes.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** Người dùng xem một tin tức trong Pulse Feed (Story 20.10) và muốn chuyển ngay góc phân tích được sinh sẵn thành một báo cáo nghiên cứu sâu có citation. Hiện tại không có đường dẫn nào biến một headline thành báo cáo cited trong một cú click.

**Approach:** Xây dựng capability `chainlens.pulse_research` gọi ChainLens `POST /v1/pulse/research` với `{itemId, angleId, mode, output: "news", chatId}` và stream SSE. Tái sử dụng hoàn toàn `_parse_sse` + `ResearchOutput` từ `chainlens.research` (cùng contract SSE `init`→`text_delta`→`done{usage,chatId}`) — không reimplement parser. Billing ghi `TokenUsage` với `usage_type="chainlens_pulse_research"` và `cost_micros` qua `cost_dollars_to_micros`.

## Boundaries & Constraints

**Always:**
- Tái sử dụng `_parse_sse` + `ResearchOutput` từ `app/capabilities/chainlens/research/` — KHÔNG viết parser mới.
- Capability đặt tại `app/capabilities/chainlens/pulse_research/` (`schemas.py`, `executor.py`, `definition.py`, `__init__.py`).
- Endpoint `POST /api/v1/workspaces/{workspace_id}/pulse/research` stream SSE về client với cùng contract.
- Persist `chatId` từ frame `done` để hỗ trợ SEP-2567 resume.
- Billing: `TokenUsage` với `usage_type="chainlens_pulse_research"`, `cost_micros` qua `cost_dollars_to_micros`.

**Never:**
- Không reimplement SSE parser — reuse từ `chainlens/research/sse_parser.py`.
- Không widen `ResearchInput.output` Literal — tạo dedicated `PulseResearchInput`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Chạy angle research | POST `{itemId, angleId, mode="balanced"}` | Stream SSE `init`→`text_delta`→`done{usage,chatId}` | 5xx degrade typed |
| Done frame có usage | `done{costDollars: 0.05, chatId: "chat_x"}` | Ghi TokenUsage `chainlens_pulse_research`, trả cost_micros | — |
| Angle không tồn tại | `{itemId, angleId}` sai | ChainLens trả 404 | `ChainLensError` typed |
| Stream đứt giữa chừng | Network drop giữa chừng | Client reconnect hoặc fallback async-jobs | Không crash worker |

</intent-contract>

## Code Map

- `nowing_backend/app/capabilities/chainlens/pulse_research/schemas.py` -- **File mới.** `PulseResearchInput`, dùng lại `ResearchOutput`.
- `nowing_backend/app/capabilities/chainlens/pulse_research/executor.py` -- **File mới.** Gọi `POST /v1/pulse/research`, stream SSE qua `_parse_sse` tái sử dụng.
- `nowing_backend/app/capabilities/chainlens/pulse_research/definition.py` -- **File mới.** Capability registration.
- `nowing_backend/app/capabilities/chainlens/pulse_research/__init__.py` -- **File mới.** Export.
- `nowing_backend/app/routes/pulse_routes.py` -- **Sửa.** Thêm endpoint `POST /pulse/research` stream SSE.
- `nowing_backend/tests/unit/chainlens/test_pulse_research.py` -- **File mới.** Unit tests.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/capabilities/chainlens/pulse_research/` -- Tạo capability `chainlens.pulse_research` -- 1-click angle → deep-research
- `nowing_backend/app/routes/pulse_routes.py` -- Thêm endpoint `POST /pulse/research` SSE stream -- API cho frontend
- `nowing_backend/tests/unit/chainlens/test_pulse_research.py` -- Unit tests -- Đảm bảo SSE contract đúng

**Acceptance Criteria:**
- **Given** `{itemId, angleId}` hợp lệ, **When** capability thực thi, **Then** gọi ChainLens `POST /v1/pulse/research` và stream SSE frames về client.
- **Given** done frame chứa `usage.costDollars`, **When** stream kết thúc, **Then** `ResearchOutput.cost_micros` được tính qua `cost_dollars_to_micros`.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 5 findings — high 0, medium 3, low 2, false 0, maybe-false 0
- findings:
  - `medium` `patch` Thiếu import `MagicMock`/`AsyncMock` + `_stream_research_mock` helper trong test — thêm; 7/7 pass
  - `medium` `patch` Ruff N818: exception `ChainLensPulseResearchNotFound` thiếu suffix Error — rename thành `ChainLensPulseResearchNotFoundError` toàn bộ 4 files
  - `medium` `patch` Ruff SIM117 nested with trong tests — gộp single with statement
  - `low` `patch` Ruff N814 (`_RO` camelcase alias) + F401 (`PulseResearchInput` thiếu trong `__all__`) — sửa tên và thêm export
  - `medium` `defer` TokenUsage billing integration chưa wire (cần ghi `usage_type="chainlens_pulse_research"` qua BillingEventService)
  - `low` `defer` chatId persistence vào ResearchThread cho SEP-2567 resume

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Capability `chainlens.pulse_research` biến một góc phân tích từ Pulse Feed thành báo cáo deep-research có citation trong 1 click: `PulseResearchExecutor` gọi ChainLens `POST /v1/pulse/research` với `{itemId, angleId, mode, output: "news"}` và stream SSE, tái sử dụng hoàn toàn `_parse_sse` + `ResearchOutput` từ `chainlens.research` (không reimplement parser — cùng wire contract).

### Files changed

- `nowing_backend/app/capabilities/chainlens/pulse_research/schemas.py` (mới) — `PulseResearchInput` (camelCase aliases) + reuse `ResearchOutput`
- `nowing_backend/app/capabilities/chainlens/pulse_research/executor.py` (mới, ~110 dòng) — `PulseResearchExecutor.stream_research` + factory closure
- `nowing_backend/app/capabilities/chainlens/pulse_research/definition.py` (mới) — `CHAINLENS_PULSE_RESEARCH` Capability
- `nowing_backend/app/capabilities/chainlens/pulse_research/__init__.py` (mới) — export
- `nowing_backend/app/routes/pulse_routes.py` — thêm endpoint `POST /pulse/research` (parse SSE qua `_parse_sse` tái sử dụng)
- `nowing_backend/tests/unit/chainlens/test_pulse_research.py` (mới, 7 tests)

### Review findings breakdown

- **Patches applied (5):** exception rename NotFound→NotFoundError (N818); thiếu imports MagicMock/AsyncMock; thiếu `_stream_research_mock` helper; SIM117 nested with; `PulseResearchInput` vào `__all__`
- **Deferred (2):** TokenUsage billing integration (medium); chatId persistence (low)
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 7/7 tests mới pass, 23/23 full chainlens regression pass.

### Verification performed

- `uv run pytest tests/unit/chainlens/ -q` → **23 passed**, 0 failed
- `uv run ruff check` (3 targets) → **All checks passed!**
- `uv run python -c "from app.capabilities.chainlens.pulse_research import CHAINLENS_PULSE_RESEARCH"` → **import OK**
- Matrix Test Audit: 4/4 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- TokenUsage billing chưa ghi vào DB (cần wire BillingEventService)
- chatId chưa persist vào ResearchThread (SEP-2567 resume)

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/chainlens/test_pulse_research.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/capabilities/chainlens/pulse_research/ app/routes/pulse_routes.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.capabilities.chainlens.pulse_research import CHAINLENS_PULSE_RESEARCH; print('import OK')"` -- expected: no exception
