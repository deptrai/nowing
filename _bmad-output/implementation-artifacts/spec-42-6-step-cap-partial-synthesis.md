---
title: '42.6 — Step-cap graceful degradation: partial synthesis thay vì text=0'
type: feature
created: '2026-11-17'
status: 'done'
baseline_revision: 'a4aaf9b214a9b32a604dccbec2a468b739af0086'
review_loop_iteration: 1
followup_review_recommended: false
context: []
warnings: ['multiple-goals']
deferred: []
---

## Intent Contract

- **Purpose**: khi `ModelCallLimitMiddleware(run_limit=80)` chặn run, user phải nhận partial answer (tóm tắt tool results đã có) + `status` part `partial:true` — không còn turn trống/`text=0` hay chỉ thấy raw "Model call limits exceeded".
- **Source**: `_bmad-output/planning-artifacts/epics.md:5658-5668` (story 42.6) + epic-42-context.
- **Always**
  - Cap hit → force-synthesize: tóm tắt tool results đã có, text nêu "đã xử lý N tool calls, chưa hoàn tất"; emit `partial: true` trong `status_marker` của finalize payload.
  - Synthesis fail/timeout → fallback notice-only partial (liệt kê tool calls đã chạy); KHÔNG crash.
  - Cap với 0 tool results → text "no tool calls completed" + `partial:true`; không summarize tập rỗng.
  - `status_marker` enumerated: allowed values documented; consumer cũ ignore-unknown — verify FE/parser không vỡ.
- **Never**
  - Không đổi `thread_limit=120`/`run_limit=80`/`exit_behavior="end"` (`shared/middleware/resilience/model_call_limit.py:17-21`).
  - Không patch package langchain; không đổi `_STATUS_NO_RESPONSE` (`tasks/chat/persistence.py:99-101`).
  - Scope chỉ model-call cap; KHÔNG đụng tool_call_limit (sibling middleware — deferred).
  - Không throw từ synthesis/finalize path (best-effort); không phá `mark_interrupted`/citation pipeline.
  - Không sửa FE (verify-only: `status` parts đã bị history loader drop → ignore-unknown đạt sẵn, `persistence.py:95-98`).

## I/O Matrix

| Case | Input | Expected |
|---|---|---|
| CAP_WITH_TOOLS | run cap, ≥1 tool-call completed | text part synthesized "đã xử lý N tool calls…" + status part `{type:'status', partial:true, …}`; raw "Model call limits exceeded" message không leak vào persisted parts |
| CAP_SYNTH_FAIL | run cap, synthesis LLM throw/timeout | text part = notice liệt kê tool names + status partial:true; finalize không raise |
| CAP_ZERO_TOOLS | run cap, 0 tool results | status partial:true + text "no tool calls completed"; không gọi LLM |
| NO_CAP | run bình thường | flow y như hiện tại — zero behavior change |
| THREAD_CAP | `thread_model_call_count>=120` | cùng xử lý CAP (đã cover bởi detection qua marker/counts) |
| FE_CONSUME | part `{type:'status', partial:true}` | history loader drop, không crash render |

## Code Map

- `app/tasks/chat/streaming/agent/event_loop.py:79-84` — sau `agent.aget_state(config)`, `state_values` chứa `run_model_call_count`/`thread_model_call_count` (ModelCallLimitState keys — langchain `model_call_limit.py` `after_model` increments) + `messages` (tin nhắn cuối = injected `AIMessage("Model call limits exceeded: run limit (80/80)")`).
  - **Detection seam**: cap-hit = last AIMessage content startswith `"Model call limits exceeded"` (langchain `_build_limit_exceeded_message` — deterministic) hoặc `state_values.get("run_model_call_count",0) >= 80`. Dùng message-prefix làm primary (định danh trực tiếp sự kiện cap).
- `app/agents/chat/multi_agent_chat/shared/middleware/resilience/model_call_limit.py:12-21` — chỉ chỗ đọc constants; export `MODEL_RUN_LIMIT = 80`, `MODEL_THREAD_LIMIT = 120` để event_loop so sánh (không hardcode).
- `event_loop.py:150-164` — precedent emit text part ngoài stream (gate_notice): `format_text_start/delta/end` + `content_builder.on_text_*` → text tới cả SSE lẫn persisted payload. Partial synthesis dùng pattern này.
- `app/tasks/chat/streaming/shared/stream_result.py` — `StreamResult` (`accumulated_text`, `final_message_parts`, `content_builder`); finalize đọc builder.
- `app/tasks/chat/streaming/flows/shared/assistant_finalize.py` — `finalize_assistant_message` → `content_builder.mark_interrupted()` → `snapshot()` → `_resolve_citations` → `finalize_assistant_turn`. Status part append vào `content_payload` (trước persist) hoặc qua builder — chọn seam ít invasiveness nhất (gợi ý: append part vào payload trong `finalize_assistant_message` khi `stream_result.partial_cap_hit` flag set — field mới trên StreamResult).
- `app/tasks/chat/persistence.py:95-101` — `_STATUS_NO_RESPONSE = [{"type":"status","text":"(no text response)"}]`; comment: FE `ContentPart` union chưa có `status` → loader drop (ignore-unknown ✓). Status part mới: `{"type":"status","text":"(partial response — step cap reached)","partial":true}`; status_marker vocabulary: `text` hiện chỉ có 2 giá trị nêu trên + `partial` flag boolean optional (default false). Document trong Design Notes.
- Synthesis source: `content_builder.stats()`/`snapshot()` parts `type:'tool-call'` state `completed` → tool names + result text → prompt tóm tắt. Model call: reuse model của turn nếu tiếp cận được (runtime_context/agent), else helper nhận injected `llm_caller` callable (test-friendly); timeout `asyncio.wait_for(..., 15)` + try/except toàn bộ.
- `final_assistant_parts_from_messages` (`message_parts_normalizer.py:65`) — filter bỏ injected limit message khỏi `final_message_parts` khi cap-hit (so persisted parts không chứa raw limit text) — verify message này có xuất hiện trong parts trước khi filter.
- Tests: `nowing_backend/tests/unit/tasks/chat/streaming/` (đặt `test_partial_synthesis.py`); repo có `tests/unit/tasks/chat/` — theo convention hiện hữu.

## Tasks & Acceptance

### Execution
- [ ] T1: constants `MODEL_RUN_LIMIT`/`MODEL_THREAD_LIMIT` export từ `model_call_limit.py`; detection helper `_cap_hit(state_values) -> str | None` (trả 'run'|'thread'|None) trong event_loop hoặc module riêng `streaming/agent/partial_synthesis.py`.
- [ ] T2: `partial_synthesis.py` — `async def synthesize_partial(tool_parts, llm_caller) -> str` (1 LLM call, timeout 15s, try/except → None); `def notice_only_partial(tool_parts) -> str` (liệt kê tên tools); `def no_tools_partial() -> str`.
- [ ] T3: event_loop — cap-hit → chạy T2 theo I/O matrix; emit text part qua pattern `format_text_*` + `content_builder.on_text_*`; set `result.partial_cap_hit=True`; filter limit message khỏi `final_message_parts`.
- [ ] T4: StreamResult field `partial_cap_hit: bool = False`; `finalize_assistant_message` append status part `{"type":"status","text":"(partial response — step cap reached)","partial":true}` khi flag set.
- [ ] T5: tests — CAP_WITH_TOOLS (fake tool parts + stub llm_caller), CAP_SYNTH_FAIL, CAP_ZERO_TOOLS, NO_CAP regression, status part shape.
- [ ] T6: verify FE ignore-unknown — đọc `nowing_web` content-part loader xác nhận `status` parts drop an toàn (đã có comment bảo đảm; chỉ cần double-check nguồn FE nếu tìm nhanh được, không sửa).

### Acceptance
- [ ] AC1: run cap → synthesized text "đã xử lý N tool calls, chưa hoàn tất" + `partial:true` status part trong persisted payload.
- [ ] AC2: synthesis throw → notice-only partial, không exception propagate.
- [ ] AC3: 0 tool results → "no tool calls completed" + `partial:true`, không LLM call.
- [ ] AC4: status part documented (Design Notes); FE loader ignore-unknown verified.
- [ ] AC5: unit test e2e-level: fake state cap → emitted SSE chứa partial text; không blank.

## Spec Change Log

- 2026-11-17 — tạo spec từ AC epics.md:5658-5668.

## Design Notes

- Langchain mechanism (verified trên `.venv` langchain.agents.middleware.model_call_limit): `before_model` check counts → cap → `{"jump_to":"end","messages":[AIMessage("Model call limits exceeded: run limit (80/80)")]}`; counts trong state `run_model_call_count`/`thread_model_call_count`.
- `status` part vocabulary (enumerate): `text` ∈ `{"(no text response)", "(partial response — step cap reached)"}`; `partial` boolean optional (vắng = false). Consumer ignore-unknown: FE history loader drop `status` type (`persistence.py:95-98`).
- Synthesis prompt gợi ý: "Tóm tắt ngắn các kết quả tool sau và nói rõ đã xử lý {N} tool calls, chưa hoàn tất" — 1 call, max_tokens ~500.
- Detection qua message prefix "Model call limits exceeded" là stable theo langchain hiện tại; nếu langchain đổi text, state-count fallback trong `_cap_hit` vẫn cover.

## Review Triage Log

### 2026-11-17 — Review pass 1 (coordinator self-review)

- [low] [patch] Prompt synthesis unbounded: cap-hit run có thể ~80 tool parts × 2000 chars ≈ 160KB prompt cho 1 notice. Patch: `tool_parts[:20]` khi build snippets (tổng số vẫn báo trong prompt).
- [reject] Fallback `run_model_call_count`/`thread_model_call_count` có thể không tồn tại trong state → `get(..., 0)` → 0 → no-op an toàn (prefix detection là primary).
- [reject] ContextVar stale workspace_id: set lại mỗi turn trong cả 2 orchestrator trước `run_stream_loop`; orchestrator khác không set → `_default_llm_caller` trả None → notice-only (graceful).
- [reject] `yield` trong `try/except` ở event_loop: consumer CancelledError/GeneratorExit không bị Exception nuốt; các exception khác log-only đúng intent.
- [reject] `llm.ainvoke` content non-str (list parts) → `_default_llm_caller` trả None → fallback notice. Chấp nhận — workspace AGENT model trả str trong thực tế.
- [defer] `notice` emit xong không đi qua `content_builder` text-end cleanup nào khác — `on_text_*` đã gọi đủ 3 hook giống path chính.

Verdict: 0 high / 0 medium / 1 low (đã patch) / 4 reject / 1 defer.

## Auto Run Result

- T1 export `MODEL_THREAD_LIMIT=120`/`MODEL_RUN_LIMIT=80` không đổi giá trị (Never giữ nguyên).
- T2 `partial_synthesis.py` mới (134 dòng): `cap_hit` prefix + count fallback, `completed_tool_parts`, `notice_only_partial`/`no_tools_partial`, `synthesize_partial` (15s `asyncio.wait_for`, mọi lỗi → None), `PARTIAL_STATUS_PART`.
- T3 `event_loop.py` emit text frames + `result.partial_cap_hit=True`, wrap try/except log-only; `stream_result.py` + field; ContextVar `_synthesis_workspace_id` inject từ cả 2 orchestrator (new_chat + resume_chat).
- T4 `assistant_finalize.py` append `PARTIAL_STATUS_PART` vào persisted payload.
- T5 `test_partial_synthesis.py` 12 tests xanh; suite `tests/unit/tasks/chat/streaming` 59/59.
- T6 verify-only FE: loader drop unknown `status` parts — không sửa FE (Never).
- `followup_review_recommended`: false.

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/tasks/chat/streaming/test_partial_synthesis.py -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/tasks/chat/streaming -x -q
```
