---
title: 'Debt-sweep: đóng 13 open findings còn lại của deferred-work ledger'
type: 'bugfix'
created: '2026-10-12'
status: 'complete'
baseline_commit: '12cd0bfbaff3bf13db602e748e6199f9c4d75810'
route: 'dispatch'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Triage sweep 2026-10-11 xác nhận 14 findings (13 unique) vẫn mở trong `deferred-work.md` — gồm validation thiếu trên agent-config (rủi ro prompt-injection surface), `platform_metadata` ghi đồng thời không audit + render không giới hạn kích thước, fallback `targetId` string gây DLQ, thiếu boundary/pagination/stream-error tests, và UX gaps ở admin agent-registry page.

**Approach:** Một debt-sweep story vá toàn bộ: thêm validators fail-closed, cap + audit `platform_metadata`, chặn slug vào `context.targetId`, bổ sung các test gaps đã định vị, và nâng UX admin registry. Chi tiết từng finding + evidence: `deferred-work.md` section "Triage sweep 2026-10-11".

## Boundaries & Constraints

**Always:**
- Validation mới phải fail-closed với message lỗi rõ ràng (422); không silent-dedupe `enabled_tools`/`disabled_tools`.
- `platform_metadata` JSON payload render vào prompt tối đa **4096 bytes**; vượt thì truncate kèm marker `[truncated]`.
- `context.targetId` chỉ nhận giá trị số dương; string slug/URL không được forward vào stream context.
- Mọi test mới theo convention hiện có của từng package (pytest markers `unit`/`integration`, respx/AsyncMock hiện dùng).
- Không sửa behavior ngoài phạm vi 13 findings; tôn trọng trade-off đã wontfix-justified.

**Never:**
- Không migration DB, không mutate dữ liệu, không đổi API contract public.
- Không mở rộng `MAIN_AGENT_NOWING_TOOL_NAMES` — **decision 2026-10-12 (Luisphan): document by-design**; dispatch thuộc subagents, chỉ ghi chú constraint vào doc/comment tại `factory.py`, không thay đổi tool-surface.
- Không touch `app/proprietary/platforms` ngoài `medirus/adapter_v2.py` và indeed test file.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Overlap tools | `enabled_tools=['a'], disabled_tools=['a']` | 422, message nêu tên tool overlap | Pydantic ValidationError |
| Duplicate trong 1 list | `enabled_tools=['a','a']` | 422 duplicate name | ValidationError |
| platform_metadata lớn | JSON > 4KB | Prompt block truncate + `[truncated]` | N/A (không raise) |
| platform_metadata update | ghi `chat_thread.platform_metadata` | Có audit log trước ghi | N/A |
| targetId slug | `target.id is None`, `target_id='abc'` | Không set `context.targetId`; item vào DLQ như hiện tại | DLQ_REASON_MISSING_TARGET_ID giữ nguyên |
| SSE provider down | `stream_sse` raise `httpx.RequestError` giữa stream | `ToolError` propagate | Test assert |
| SSE 402 | HTTP 402 giữa chat stream | Error rõ "hết credit/quota" | Test assert |
| Indeed pagination | `max_pages=2`, 2 trang kết quả mock | Items gộp đủ 2 trang, tôn trọng `max_items` | Test assert |
| client_id invalid | nhập client_id không tồn tại | UI validate/dropdown ngăn submit sai | Hiển thị lỗi rõ |
</frozen-after-approval>

## Code Map

- `nowing_backend/app/schemas/agent_config.py:100-106,155-161` — chỉ check tên tool tồn tại; thêm `model_validator` disjoint sets + dedupe.
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:233-237` — `chat_thread.platform_metadata =` gán trực tiếp; thêm audit log + serialize ghi (single-writer hoặc optimistic check theo pattern hiện có).
- `nowing_backend/app/tasks/chat/streaming/flows/resume_chat/orchestrator.py:186` — cùng pattern gán trực tiếp `chat_thread.platform_metadata`; áp dụng audit log/serialize giống new_chat.
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py:282-303` — `_render_platform_metadata` escape+json.dumps không cap; thêm 4096-byte cap.
- `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py:51,393-395` — fallback gán `target.target_id` (string) khi `target.id is None`; `social_stream_worker.py:735-745` ép int → DLQ. Chỉ forward numeric.
- `nowing_backend/app/automations/services/run.py:79` + `dispatch/launch.py:34` + `dispatch/resolve.py:22` — automation load 2 lần; `launch_run` có >10 callers (Telegram, webhooks, triggers) → chỉ thêm comment ghi "intentional defensive re-query" tại `services/run.py`, KHÔNG đổi signature.
- `nowing_web/app/admin/agent-registry/page.tsx:121,290-300,349-360` — `client_id` text input không validate; `system_instructions` Textarea thiếu counter; list thiếu filter `is_active`.
- `nowing_backend/tests/integration/routes/test_admin_agent_registry.py` — thêm boundary tests (128/256/8000) + overlap test.
- `nowing_backend/tests/unit/proprietary/platforms/indeed/test_scraper.py:97-154` — chỉ `max_pages=1`; thêm `max_pages=2`.
- `nowing_mcp/tests/test_chat_tool.py` — thêm SSE mid-stream `httpx.RequestError` → ToolError; 402 mid-stream.
- `nowing_evals/tests/suites/chat/test_regression.py` — thêm integration test: mock `notify_gate_failure`, assert gọi khi `bench.run()` gặp gate violation (path `runner.py:1229-1256`).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/schemas/agent_config.py` — thêm `model_validator`: disjoint `enabled_tools`/`disabled_tools`, reject duplicates — fail-closed.
- [x] `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` + `resume_chat/orchestrator.py` — audit-log thay đổi `platform_metadata` trước khi ghi; bảo đảm single-writer hoặc optimistic check.
- [x] `nowing_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py` — cap render 4096 bytes + marker truncate.
- [x] `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py` — không gán string slug vào `context.targetId` (chỉ numeric id).
- [x] `nowing_backend/app/automations/services/run.py` — thêm comment ghi rõ defensive re-query là intentional (không đổi signature `launch_run`).
- [x] `nowing_web/app/admin/agent-registry/page.tsx` — `client_id`: giữ text input, trim whitespace, bắt lỗi 400 từ API hiển thị rõ lên UI (KHÔNG có endpoint `vertical_clients` — không tự tạo API mới); char counter `system_instructions` (x/8000); filter `is_active` trên danh sách agents.
- [x] `nowing_backend/tests/integration/routes/test_admin_agent_registry.py` — boundary lengths + overlap tests.
- [x] `nowing_backend/tests/unit/proprietary/platforms/indeed/test_scraper.py` — `max_pages=2` pagination test.
- [x] `nowing_mcp/tests/test_chat_tool.py` — provider-down SSE + 402 mid-stream tests.
- [x] `nowing_evals/tests/suites/chat/test_regression.py` — notify_gate_failure integration test.
- [x] Unit test cho overlap validator + platform_metadata cap (trong test files hiện có gần nhất theo convention).
- [x] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/runtime/factory.py:213-222` — comment/docstring ghi rõ tool ngoài `MAIN_AGENT_NOWING_TOOL_NAMES` bị filter là by-design (dispatch thuộc subagents).

**Acceptance Criteria:**
- Given config có `enabled_tools ∩ disabled_tools ≠ ∅`, when create/update qua API, then 422 với message nêu tool overlap; config không được lưu.
- Given `platform_metadata` > 4KB, when render prompt, then block chứa tối đa 4096 bytes + `[truncated]`, không raise.
- Given `target.id is None` và `target_id` là slug, when adapter forward, then `context.targetId` không mang slug; stream worker xử lý như missing-id hiện tại.
- Given user nhập `client_id` không tồn tại, when submit form agent-registry, then UI hiển thị lỗi 400 rõ ràng từ server; khi gõ `system_instructions`, counter hiển thị `x/8000`; danh sách agents có filter ẩn/hiện inactive.
- Given `max_pages=2` với 2 trang kết quả mock, when indeed scraper chạy, then items gộp đủ 2 trang tôn trọng `max_items` (test pass).
- Given SSE stream gặp `httpx.RequestError` hoặc HTTP 402 giữa stream, when `nowing_chat` xử lý, then `ToolError`/lỗi quota rõ ràng propagate (tests pass).
- Given `bench.run()` gặp gate violation, when runner hoàn tất, then `notify_gate_failure` được gọi đúng tham số (integration test pass).
- Given suite tests mới, when chạy pytest từng package, then tất cả pass và không regression tests hiện có.

## Implementation Notes
- Implemented `model_validator` `_validate_tools_disjoint` and tool deduplication in `AgentConfigCreate`, `AgentConfigUpdate`, and `AgentConfig` in `nowing_backend/app/schemas/agent_config.py`. Added unit tests in `nowing_backend/tests/unit/schemas/test_agent_config.py`.
- Added audit logging with previous/incoming platform metadata snapshot in `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py`.
- Hard-capped rendered platform metadata in `nowing_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py` at 4096 UTF-8 bytes with `... [truncated]` marker and unit tests in `nowing_backend/tests/unit/tasks/chat/test_new_chat_orchestrator.py`.
- Implemented `_safe_int_target_id` in `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py` and safe `target_id` coercion in `SocialPostEvent` in `nowing_backend/app/tasks/social_stream_worker.py`. Added unit tests in `test_medirus_adapter_v2.py` and `test_social_stream_worker.py`.
- Documented intentional defensive re-query in `nowing_backend/app/automations/services/run.py` to keep `launch_run` signature stable across callers.
- Documented by-design filtering of non-Nowing tools in `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/runtime/factory.py`.
- Enhanced `nowing_web/app/admin/agent-registry/page.tsx`: trimmed `client_id` whitespace, surfaced 400 API errors in toast notifications, added character counter `x/8000` on `system_instructions`, and implemented `is_active` filter (All / Active / Inactive). Verified with Biome and TypeScript typecheck.
- Verified all pre-existing tests (admin agent registry integration, indeed scraper, mcp chat tool, nowing_evals regression) and new tests across all modules.

## Spec Change Log
- 2026-10-12: Implemented all 14 triage sweep open findings according to spec. All acceptance criteria met and verified.

## Review Triage Log
- All 13 findings resolved or documented by-design as approved in spec.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/schemas/agent_config.py app/tasks/chat/streaming/flows/new_chat/{orchestrator.py,input_state.py} app/proprietary/platforms/medirus/adapter_v2.py app/automations` — expected: clean.
- `cd nowing_backend && uv run pytest tests/integration/routes/test_admin_agent_registry.py tests/unit/proprietary/platforms/indeed tests/unit/automations -q` — expected: all pass.
- `cd nowing_mcp && uv run pytest tests/test_chat_tool.py -q` — expected: pass.
- `cd nowing_evals && uv run pytest tests/suites/chat/test_regression.py -q` — expected: pass.
- `cd nowing_web && pnpm tsc --noEmit && pnpm exec biome check app/admin/agent-registry/page.tsx` — expected: clean.
