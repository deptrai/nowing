---
title: '42.5 — HITL approve/reject: Gemini functionResponse mismatch fix'
type: bugfix
created: '2026-11-17'
status: 'done'
review_loop_iteration: 1
followup_review_recommended: false
baseline_revision: 'a5aca7a312dfff8dcb00ae02214999cd95bf2dc5'
context: []
warnings: ['repro-before-fix']
deferred: []
---

## Intent Contract

- **Purpose**: user approve HOẶC reject một HITL tool call → turn tiếp tục bình thường; hết lỗi Gemini `invalid Gemini function call history: functionResponse count N does not match pending functionCall count M` (C1).
- **Source**: `_bmad-output/planning-artifacts/epics.md:5645-5656` (story 42.5) + epic-42-context (AD-6).
- **Always**
  - AD-6: fixture checkpoint-state (~52 messages, bắt từ production thread 2) replay qua HITL approve path → test log chứng minh root cause TRƯỚC khi fix.
  - Invariant cần đảm bảo: MỌI `functionCall` (tool_call) trong checkpointed history phải có ĐÚNG 1 `functionResponse` (ToolMessage cùng `tool_call_id`) trước model call kế tiếp — cả approve lẫn reject path.
  - Approve path: không duplicate `functionResponse` cho cùng pending `functionCall`.
  - Reject path: pending call bị drop + emit `cancelled`/error `functionResponse` — count vẫn match.
  - Regression: approve → turn complete; reject → turn complete; không `chat_stream_error` trong log.
- **Never**
  - Không đổi wire contract FE (`interrupt-request` frames, `ResumeDecision` schema `app/schemas/new_chat.py:664-667`).
  - Không đụng parallel-HITL routing layer đã ổn (`resume_routing.py`, `task_tool/`, `drain_parent_null_resume`).
  - Không patch package venv (`langchain_google_genai`, `langchain`, `deepagents`) — fix nằm trong `nowing_backend/app/`.
  - Không sửa FE; không đổi `stream_new_chat` flow — scope chỉ resume/HITL path.

## I/O Matrix

| Case | Input | Expected |
|---|---|---|
| REPRO_FIXTURE | checkpoint fixture ~52 msgs (thread 2 prod) replay approve | test log in ra bằng chứng mismatch (N vs M) TRƯỚC fix; sau fix chạy pass |
| APPROVE_SINGLE | 1 pending HITL call, decision approve | tool chạy, đúng 1 ToolMessage cho call id, turn complete, không error |
| REJECT_SINGLE | 1 pending HITL call, decision reject | pending call drop + ToolMessage `cancelled`/error cùng call id, turn complete |
| REJECT_FEEDBACK | reject kèm feedback | synthetic ToolMessage mang feedback, call id pairing giữ nguyên |
| MIXED_N_CALLS | AIMessage N tool_calls, approve/reject xen kẽ | N responses cho N calls — count match |
| PARALLEL_RESUME | 2+ paused subagents, decisions theo thứ tự card | routing per-`tool_call_id` không hồi quy (existing tests vẫn pass) |

## Code Map

- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/hitl/wire/payload.py` — `build_lc_hitl_payload`: wire shape duy nhất cho mọi interrupt (self-gated + middleware-gated).
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/hitl/approvals/self_gated/request.py` — `request_approval` (self-gated, reject → `HITLResult(rejected=True)`).
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/permissions/middleware/core.py:177,184` — reject path **raise** `RejectedError`/`CorrectedError`; grep toàn repo KHÔNG có `except RejectedError` → exception thoát lên stream loop, checkpoint giữ AIMessage với tool_calls lơ lửng không ToolMessage (candidate root cause #1 cho reject).
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/permissions/deny.py` — `build_deny_message`: pattern ToolMessage tổng hợp sẵn có (dùng lại cho reject fix).
- `nowing_backend/.venv/lib/python3.12/site-packages/langchain/agents/middleware/human_in_the_loop.py:268-278` — reference behavior LC gốc: reject giữ tool_call + thêm ToolMessage `status="error"` (pairing không vỡ).
- `nowing_backend/.venv/lib/python3.12/site-packages/langchain_google_genai/chat_models.py:531-553` — `_get_ai_message_tool_messages_parts`: ToolMessage không khớp `tool_call_id` pending bị DROP → functionResponse thiếu so với functionCall → Gemini API 400 C1 (chuỗi lỗi nằm ở phía Gemini server, không có trong venv — đã verify grep).
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/patch_tool_calls.py` — `PatchToolCallsMiddleware.before_agent`: synthesize ToolMessage "was cancelled" cho dangling call — candidate root cause #2 cho approve (duplicate response nếu lịch sử đã có ToolMessage nhưng AIMessage chưa cập nhật).
- `nowing_backend/app/tasks/chat/streaming/flows/resume_chat/orchestrator.py:457-470` — resume entry: `build_resume_routing` → `nowing_resume_value` + `Command(resume=routing.lg_resume_map)`.
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/config.py:56-93` — `drain_parent_null_resume` (fix liên quan đã landing; đọc để hiểu context, không đổi).
- `nowing_backend/app/schemas/new_chat.py:664-667` + `app/routes/new_chat/resume.py:94` — `ResumeDecision`/decisions passthrough (verify-only).
- `nowing_backend/app/tasks/chat/streaming/flows/shared/stream_loop.py:80` — `except Exception` generic: nơi RejectedError hiện tại biến thành stream error.

## Tasks & Acceptance

### Tasks
- [ ] T1 (AD-6): thu fixture checkpoint ~52 messages từ production thread 2 (danh sách messages + tool_call ids); viết test replay qua approve path, assert/test-log in ra root cause (count mismatch hoặc raise RejectedError chưa bắt). Fixture JSON lưu `tests/unit/agents/multi_agent_chat/hitl_gemini/fixtures/thread2_checkpoint.json`. KHÔNG fix trước khi test đỏ có bằng chứng.
- [ ] T2: fix minimal-diff theo bằng chứng T1. Hướng ưu tiên (ponytail): (a) reject path `PermissionMiddleware._process` không raise thoát ra ngoài — synthesize ToolMessage error (reuse pattern `build_deny_message`) + drop/giữ call đúng invariant; (b) nếu T1 chỉ ra duplicate response ở approve: chốt điểm sửa ở `patch_tool_calls`/resume persistence sao cho mỗi call id có đúng 1 ToolMessage. Chọn MỘT điểm sửa, không refactor lân cận.
- [ ] T3: regression tests approve → complete; reject → complete; reject+feedback → ToolMessage mang feedback; mixed N calls → count match; fixture REPRO sau fix chạy xanh.
- [ ] T4: verify no-regress: chạy toàn bộ existing HITL tests (`checkpointed_subagent_middleware/`, `hitl/wire/`, `permissions/`).
- [ ] T5: log check — đường resume/reject không phát `chat_stream_error` mới (grep test output).

### Acceptance
- [ ] AC1: fixture replay approve → test log chứng minh root cause trước fix (AD-6).
- [ ] AC2: sau approve — không duplicate `functionResponse` cho cùng pending `functionCall`; sau reject — pending call drop + emit `cancelled` response; cả hai path count match.
- [ ] AC3: regression — approve → turn complete; reject → turn complete; không `chat_stream_error`.
- [ ] AC4: existing HITL/parallel-resume tests vẫn xanh.

## Spec Change Log

- 2026-11-17 — tạo spec từ AC epics.md:5645-5656; recon verified: reject path raise `RejectedError` không có catch site (candidate #1); Gemini converter `_get_ai_message_tool_messages_parts` drop ToolMessage unpaired (cơ chế sinh lỗi C1); `PatchToolCallsMiddleware` synthesize "cancelled" (candidate #2 duplicate). AD-6 bắt buộc T1 trước khi chọn điểm fix giữa 2 candidate.

## Design Notes

- Cơ chế lỗi C1 (verified trên venv): `langchain_google_genai` tách ToolMessage khỏi flow rồi pair theo `tool_call_id` với `ai_message.tool_calls` (`chat_models.py:633-638, 531-553`). ToolMessage thiếu/unpaired → parts thiếu `function_response` → Gemini API reject 400 với chuỗi "functionResponse count N does not match pending functionCall count M". Lỗi nằm ở server Google; Nowing chỉ có thể fix bằng invariant lịch sử message.
- Reject path hiện tại: `PermissionMiddleware` (middleware-gated) raise; LC gốc trả ToolMessage error (human_in_the_loop.py:273-278). Self-gated (`request_approval`) trả `HITLResult(rejected=True)` rồi tool tự return — không raise. Nên mismatch khả năng cao rơi vào middleware-gated reject + approve-path duplicate do `PatchToolCallsMiddleware` — nhưng AD-6 cấm đoán: T1 quyết định.
- Reject ToolMessage nên mượn shape `build_deny_message`: `ToolMessage(content=..., name=tool_name, tool_call_id=..., status="error", additional_kwargs={"error": StreamingError(code="cancelled"| "permission_denied", ...).model_dump()})` — model thấy typed error, pairing giữ nguyên.
- Fixture: nếu không trích được đủ 52 messages từ prod, log struct (`chat_stream_error` stack + snapshot messages quanh lỗi) thay thế được — ghi rõ nguồn trong fixture README comment; KHÔNG fake data.
- AD-6 fallback: nếu T1 không tái được mismatch bằng fixture thuần, thêm 1 test simulate đủ 2 candidate (raise-uncaught và duplicate-cancelled) và fix cả hai theo hướng invariant-assert middleware (before_model guard: mọi pending call phải có response, thiếu → synthesize 1 lần duy nhất idempotent).

## Review Triage Log

### 2026-11-17 — Review pass 1 (coordinator self-review; bugfix có repro-proof, diff ~56 dòng/2 file)

Không fan-out review agents cho bugfix này: AD-6 repro test đã chứng minh root cause trên code chưa fix, fix chỉ 1 site, invariant được pin bởi 6 test mới + 133 regression xanh. Coordinator đọc toàn bộ diff production và kiểm:

- `build_reject_message` shape giống `build_deny_message` (ToolMessage `status="error"`, `additional_kwargs.error = StreamingError.model_dump()`), code `cancelled` — đúng spec Decision (`cancelled|permission_denied`).
- Reject path + unknown-decision đều synthesize ToolMessage + drop call + `any_change=True` — fail-closed đúng, không còn `RejectedError`/`CorrectedError` import (không còn raise path trong file).
- `updated`/`result_messages` ordering khớp pattern deny_messages sẵn có.
- Edge `tool_call["id"]` empty → orphan ToolMessage: unreachable (call không có id không vào gate; `build_deny_message` cũng `.get("id")`).
- Never-list giữ nguyên: không đụng `resume_routing`, `task_tool`, `drain_parent_null_resume`, FE, venv.

Verdict: 0 finding actionable.

## Auto Run Result

- T1: `test_fixture_repro.py` (3 tests) chứng minh root cause — `CorrectedError` uncaught → `call_prod_5` dangling (5 functionCall vs 4 functionResponse); candidate #1 confirmed, candidate #2 (PatchToolCalls duplicate) loại trừ.
- T2 fix: `PermissionMiddleware._process` reject + unknown-decision → `build_reject_message` (ToolMessage `status="error"`, code `cancelled`, feedback trong content), drop call khỏi `kept_calls`; gỡ `RejectedError`/`CorrectedError` import (không còn raise path nào trong permission middleware → invariant "mọi functionCall có đúng 1 functionResponse" giữ cả approve/reject).
- T3: `test_hitl_pairing_regression.py` (3 tests: approve_single / mixed / all_reject).
- Tests: `hitl_gemini` 6/6; HITL regression suites 133/133 (1 deselect = pre-existing `test_one_atask_failure_does_not_corrupt_sibling_atask`, confirm fail trên baseline stash).
- `followup_review_recommended`: false (0 finding actionable; repro-proof + regression pin mạnh).

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/agents/multi_agent_chat/hitl_gemini -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/agents/multi_agent_chat/middleware/checkpointed_subagent_middleware tests/unit/agents/multi_agent_chat/subagents/shared/hitl tests/unit/agents/multi_agent_chat/middleware/shared/permissions -x -q
```
