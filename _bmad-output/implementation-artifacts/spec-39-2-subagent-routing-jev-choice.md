---
title: 'Story 39.2 — Subagent Routing via DecisionService Choice'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'dispatch'
baseline_commit: 'd7bc300c919e709716a322cc690ac2b7c415132f'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `JevRouterMiddleware` gọi `typesafe_sdk` trực tiếp (bypass DecisionService): không strict validation, không telemetry `token_usage`, model mặc định `jev-latest` vi phạm pin `jev-1.13.0`, không fallback chain, và nằm trong import-guard allowlist như legacy exception.

**Approach:** Rewire middleware qua `DecisionService.decide()` với `subagent_routing` question set, confidence ≥ `DECISION_ROUTING_THRESHOLD` (default 0.6) inject `<jev_routing_hint>` SystemMessage advisory; fail-open tuyệt đối. Xóa mọi import `typesafe_sdk` khỏi `jev_router.py`. Đồng thời fix dedup semantics: hint fire đúng 1 lần per user message (hiện tại marker persist suốt thread history → không bao giờ fire lại; còn below-threshold/error re-fire mỗi model call trong react loop → trả tiền lặp lại).

## Boundaries & Constraints

**Always:**
- Giữ public API: `JevRouterMiddleware`, `build_jev_router_mw(flags, subagent_descriptors=None, ...)`, `<jev_routing_hint>` marker + advisory wording VERBATIM (xem Design Notes). Ctor được đổi signature nội bộ (không caller ngoài).
- Trigger: classify trên **last HumanMessage trong state** (không nhất thiết trailing — sau tool calls vẫn tìm thấy), `len(user_text.strip()) >= 3`; `state["user_message"] = user_text.strip()`.
- Once-per-user-message: dedup scan chỉ xét messages SAU last HumanMessage (marker turn cũ không block turn mới) + nhớ text đã classify (`self._last_classified`) để failure/below-threshold không re-fire mỗi model call.
- Fail-open tuyệt đối: wrap TOÀN BỘ body `abefore_model` trong `except Exception → return None` (DecisionError/InvalidDecisionAnswer log theo level riêng; InvalidDecisionAnswer là subclass DecisionError). Một exception trong hook không được kill turn.
- Criteria = registry `subagent_routing` options ∩ live `subagent_descriptors` names + `none_needed`, build bằng `dataclasses.replace(q, criteria={...})` (frozen dataclass); **criteria values giữ nguyên eval-tuned registry descriptions**, không lấy descriptor text. `descriptors=None/empty` → full registry set.
- Gọi `get_decision_service().decide()` với `task="routing"`, `question_set=f"{qs.name}@{qs.version}"`, `required_state_keys=qs.required_state_keys`, `model=None` (để service dùng pin — truyền giá trị khác pin → `invalid_model`), `timeout=None` (ceiling `DECISION_TIMEOUT_SECONDS`).
- Gate: `ConfidenceGate.for_task("routing").passes(answer)`; choice id lấy từ `result.answers["subagent"].value` (KHÔNG `.choice`), confidence từ `.confidence`.
- Telemetry: `async with async_session_maker() as session:` mở CHỈ khi thực sự classify (sau dedup/trigger) và có ids; `await session.commit()` trong `finally` — commit BẤT KỂ decide() outcome (InvalidDecisionAnswer leg cũng có row từ `_record_usage` finally).
- `user_id` từ stack là `str | None` → convert guarded `UUID(user_id)` với `try/except (TypeError, ValueError)` (precedent `factory.py:179-185`) trước khi truyền `decide()` — str thô sẽ fail flush → telemetry mất lặng.
- Dual gating giữ: `build_jev_router_mw` check `enable_jev_router` + kill-switch như cũ.

**Never:**
- Không import `typesafe_sdk`/`AsyncTypeSafeClient`/`Choice` trong `jev_router.py`; xóa `jev_router.py` khỏi allowlist `test_import_guard.py` + sửa comment "legacy path pending story 39.2".
- Không check `TYPESAFE_API_KEY` trong `build_jev_router_mw` nữa — `missing_api_key` là fallback-trigger code; check này giết fallback chain và vô hiệu middleware khi `DECISION_BACKEND=llm_json|mock`.
- Không đọc `JEV_ROUTER_CONFIDENCE`/`JEV_MODEL` (thay bằng `DECISION_ROUTING_THRESHOLD`/pin `DECISION_JEV_MODEL`); không truyền `model=` cho `decide()`.
- Không force routing — hint advisory; LLM vẫn tự quyết `task()`.
- Không đổi registry `subagent_routing` version/options; không thêm sync `before_model` (chỉ `abefore_model` — không có sync invoke path nào cho main agent hiện nay).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| ROUTED | last HumanMessage "Tìm chung cư Q7", `answer.value="batdongsan"`, conf=0.9 | `{"messages": [SystemMessage(<jev_routing_hint> batdongsan ...)]}` | N/A |
| NONE_NEEDED | `answer.value="none_needed"`, conf=0.8 | Hint variant "answer directly, no task()" verbatim | N/A |
| BELOW_THRESHOLD | conf=0.5 < 0.6 | `None`, `_last_classified` set → không re-fire loop | log debug |
| DECIDE_RAISES | `decide()` raise `DecisionError` (timeout/backend_unavailable/missing_api_key/disabled) | `None`, `_last_classified` set | log warning |
| MALFORMED | `InvalidDecisionAnswer` | `None` | log warning |
| ANY_EXCEPTION | SQLAlchemy/UUID/KeyError/`dataclasses.replace` bug | `None` — generic except catch-all | log exception |
| NO_FRESH_MSG | Không có HumanMessage / stripped <3 chars | `None`, không gọi decide() | N/A |
| DEDUP_SAME_TURN | Marker trong messages sau last HumanMessage, hoặc text == `_last_classified` | `None`, không gọi decide() | N/A |
| NEW_TURN | Marker tồn tại nhưng TRƯỚC last HumanMessage mới | Classify lại bình thường (behavior change — fix) | N/A |
| FLAGS_OFF | `enable_jev_router=false` hoặc kill-switch | `build_jev_router_mw` → `None` | N/A |
| STALE_ROSTER | descriptors={chainlens,batdongsan} | criteria={chainlens,batdongsan,none_needed} | N/A |
| TELEMETRY | ROUTED + session+ids | row `usage_type=decision`, `task="routing"`, `question_set="subagent_routing@1.0.0"`, committed kể cả failed leg | commit fail → log warning, vẫn trả hint |
| UUID_BAD | `user_id="not-a-uuid"` | `decide(user_id=None)` → `_record_usage` skip (cần đủ session+workspace+user), hint vẫn trả | log debug |

</frozen-after-approval>

## Code Map

- `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py` — **rewrite**: bỏ `_get_client`/`_classify` (:87-156) + `TYPESAFE_API_KEY` gate (:235-237) + `JEV_ROUTER_CONFIDENCE`/`JEV_MODEL` env (:55-56); giữ `abefore_model` skeleton + hint strings (:203-219) verbatim; thêm `_last_classified` + scoped dedup + session/UUID/decide/gate wiring.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/stack.py:268-274` — caller duy nhất; truyền thêm `workspace_id`, `user_id` (str → UUID trong middleware), `client_id` — có sẵn trong scope `build_main_agent_deepagent_middleware` (:103-110).
- `app/services/decision/service.py` — `get_decision_service()` (:516), `decide()` signature (:59-73): session=None hợp lệ (telemetry skip), `required_state_keys` fail-fast `invalid_request` (:129-135), `_record_usage` chạy trong finally (:285-312).
- `app/services/decision/questions/subagent_routing.py` + `registry.py` — `get_question_registry().get_set("subagent_routing")` → `QuestionSet(name,version,questions,required_state_keys)`; `questions["subagent"]` là `ChoiceQuestion` frozen (:23-28 types.py).
- `app/services/decision/gate.py` — `ConfidenceGate.for_task("routing")` → `DECISION_ROUTING_THRESHOLD` default 0.6 (:33-39,51-75); `passes()` (:77-86).
- `app/config/decision.py` — `DECISION_ROUTING_ENABLED` (default true, :83) đã tồn tại; `.env.example:855,862` đã document cả hai — không cần task env.
- `app/db/base.py:71` — `async_session_maker`; in-middleware precedent: `context_editing/middleware.py:324`, `run_reader.py:187`.
- `app/agents/chat/multi_agent_chat/main_agent/factory.py:179-185` — precedent guarded `UUID(user_id)` conversion.
- `shared/feature_flags.py` + `shared/middleware/flags.py:8-10` — `enable_jev_router` + kill-switch `enabled()`.
- `tests/unit/services/decision/test_import_guard.py:13-21` — xóa `jev_router.py` khỏi allowlist + update docstring.
- `tests/unit/agents/multi_agent_chat/middleware/` — test dir convention (test_mode_budget.py, checkpointed_subagent_middleware/, memory/).
- `tests/unit/services/decision/test_service.py:31-78` — `_StubBackend`/`_enabled` fixture patterns để reuse.

## Tasks & Acceptance

**Execution:**
- [x] `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py` — rewrite: lazy `get_decision_service()` (patchable), registry∩descriptors question build, scoped dedup + `_last_classified`, session `async with` + unconditional commit, guarded UUID, `except Exception → None`, verbatim hints — core change
- [x] `app/agents/chat/multi_agent_chat/main_agent/middleware/stack.py` — truyền `workspace_id`/`user_id`/`client_id` vào `build_jev_router_mw` — telemetry context
- [x] `tests/unit/services/decision/test_import_guard.py` — bỏ `jev_router.py` khỏi allowlist + docstring "legacy" comment — enforcement
- [x] `tests/unit/agents/multi_agent_chat/middleware/test_jev_router.py` — tests mới cover toàn bộ 13-row I/O matrix (mock `get_decision_service`, fake/mock session, monkeypatch flags) — edge coverage

**Acceptance Criteria:**
- Given `DECISION_ENABLED=true`, `DECISION_ROUTING_ENABLED=true`, `enable_jev_router=true`, khi Vietnamese message vào multi-agent chat, then `decide()` được gọi với `subagent_routing@1.0.0` set trước LLM call; conf ≥ `DECISION_ROUTING_THRESHOLD` → `<jev_routing_hint>` SystemMessage advisory verbatim; <threshold → không hint.
- Given BẤT KỲ exception nào (backend, validation, DB, UUID), when `abefore_model` chạy, then turn tiếp tục không hint — không exception propagate.
- Given cùng một user message, when react loop gọi model nhiều lần, then classify chỉ chạy 1 lần (success và failure đều vậy); given turn mới (HumanMessage mới), then classify chạy lại kể cả khi marker cũ còn trong history.
- Given routing chạy với session+ids hợp lệ, then `token_usage` row `usage_type=decision` với `task="routing"` + `question_set="subagent_routing@1.0.0"` được commit (kể cả khi `decide()` raise sau `_record_usage`).
- `grep typesafe_sdk jev_router.py` → 0 kết quả; `test_import_guard.py` pass; model = pin `DECISION_JEV_MODEL`; không còn `TYPESAFE_API_KEY` gate ở builder.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Pass 1 (3 layers: blind-hunter 12, edge-case 4, verification-gap 2 — deduped into 11 groups):

- `jev_router.py __init__` registry get_set/dataclasses.replace outside fail-open → ctor raise kills whole agent build via `build_jev_router_mw`. **high → patch** (builder try/except → None; verified: get_set→KeyError propagates through ctor, no catch on path).
- `jev_router.py` criteria collapse: live roster non-empty but ∩ registry = ∅ → criteria={none_needed} → hint actively suppresses live agents. **medium → patch** (intersection rỗng → full registry).
- `_last_classified` text-dedup on cached middleware instance (agent_cache drops thread_id, cross-thread default on) → same-text new message suppressed cross-thread/turn; dùng `msg.id` làm dedup key (fallback text) giữ đúng intent "1 lần per user message". **medium → patch**. Member: marker-found path không set `_last_classified` → re-pay nếu marker bị context-editing xóa.
- Backward scan bỏ qua HumanMessage content falsy → có thể classify message cũ hơn khi msg mới rỗng. **low → patch** (break on first HumanMessage regardless of content).
- `_decide` mở session trước khi biết flags → `DECISION_ENABLED=false` (default) vẫn checkout DB session mỗi message. **low → patch** (pre-check `decision_enabled()`+`decision_task_enabled("routing")` trước session).
- `session.commit()` + `_record_usage` ngoài decision timeout → commit hang stall pre-LLM hook vượt budget. **medium → patch** (`asyncio.wait_for` commit ~2s).
- `thread_id` có ở `stack.py:111` + `record_token_usage` hỗ trợ nhưng `decide()` không có param → rows không link chat thread. **defer** — service API từ 39.1 thiếu param; thêm là cross-story surface.
- Tests fabricate `Answer(probabilities=None)` (shape validation thật reject) + không có test nào qua real `decide()`+stub backend → contract drift không bị khóa. **low → patch** (1 integration test qua real service).
- `build_main_agent_deepagent_middleware` → `build_jev_router_mw` id-forwarding không có test (verification-gap pre-verified: drop kwarg = telemetry mất lặng, 20 tests vẫn xanh). **medium → patch** (assembly test spy `stack.build_jev_router_mw`).
- Import guard chỉ bắt AST `import/from` — miss `importlib`/`__import__` dynamic. **defer** — pre-existing guard limitation từ 39.1, không phải story này gây.
- Docs stale: `docs/system-architecture-2026-09-21.md` + `INTEGRATION-POINTS.md` mô tả direct typesafe integration; `.env.example` thiếu `NOWING_ENABLE_JEV_ROUTER`. **defer** — doc sync ngoài spec intent.

## Design Notes

- **Verbatim hint strings** (từ `jev_router.py:203-219`, `hint_marker = "<jev_routing_hint>"`):
  ```
  {marker}\nJev pre-classification suggests routing to `{choice}` (confidence={conf:.0%}). Use `task(subagent_type="{choice}", ...)` if this matches the user's intent. You may override if the suggestion is wrong.\n</jev_routing_hint>
  {marker}\nJev pre-classification: this message likely needs no specialist (confidence={conf:.0%}). Consider answering directly without a `task()` call.\n</jev_routing_hint>
  ```
- **Dedup fix (behavior change có chủ đích):** marker checkpointed vào thread state → scan-all hiện tại nghĩa là router không bao giờ fire lại suốt thread; failure paths thì re-fire mỗi model call. Fix = scope scan sau last HumanMessage + `_last_classified` string trên self → đúng "1 lần per user message" cả hai hướng.
- **Coverage regression (reviewed decision):** live roster ~24 agents nhưng registry chỉ 15 specialists + `none_needed` → connector agents (amazon, google_drive, onedrive, cafef, indeed, mcp_discovery, chotot_bds, muaban_bds…) sẽ không bao giờ được hint. Chấp nhận: registry là eval'd set (100% baseline), hint advisory; registry mở rộng thuộc story khác.
- **Bỏ `TYPESAFE_API_KEY` gate:** `missing_api_key` trigger fallback `llm_json` — gate cũ giết đúng case fallback được build cho. `DECISION_BACKEND=llm_json|mock` cũng không cần key.
- **Latency note:** hook chạy pre-LLM trên TTFT path; worst case = 2 legs × 5s = ~10s khi Jev timeout + fallback timeout. Điển hình ~300ms; giữ service default (fallback chain là feature của story 39.1b). `_perf_log` timing bỏ — service có `[decision]` log riêng.
- **Sync `before_model`:** không cần — không có sync `.invoke()` path nào cho main agent (chỉ subagent graphs dùng sync invoke, không mang middleware này).

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/agents/chat/multi_agent_chat/main_agent/middleware/ tests/unit/agents/multi_agent_chat/middleware/ tests/unit/services/decision/` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/agents/multi_agent_chat/middleware/test_jev_router.py tests/unit/services/decision -m unit -q` — expected: all pass
- `cd nowing_backend && grep -n "typesafe_sdk\|AsyncTypeSafeClient\|JEV_ROUTER_CONFIDENCE\|JEV_MODEL\|TYPESAFE_API_KEY" app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py` — expected: no output

## Live Verification (2026-09-23)

`JevRouterMiddleware` instance thật (roster 6 subagents, ws=1, uid thật), `abefore_model` trên 2 message Việt:

- "Tìm giúp tôi nhà bán ở Quận 7 dưới 5 tỷ" → hint `batdongsan` conf=1.00 (1114ms, 457 tok) → `<jev_routing_hint>` SystemMessage injected
- "chào bạn, hôm nay thế nào?" → hint `none_needed` conf=1.00 (294ms) → hint "answer directly"

Cả 2 ghi `token_usage` rows `task='routing', backend='jev'`. Chưa verify trong full chat traffic (cần backend + `NOWING_ENABLE_JEV_ROUTER=true` trong deploy).
