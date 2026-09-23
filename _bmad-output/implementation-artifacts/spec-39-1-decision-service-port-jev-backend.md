---
title: 'Story 39.1: DecisionService Port + Jev Backend + Question Registry'
type: 'feature'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
baseline_commit: '4caa09e42017e2c8bc41cb36caffca6ce8965b90'
context:
  - '_bmad-output/implementation-artifacts/epic-39-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-jev-decision-service-2026-09-21/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Các lời gọi typed-decision tới TypeSafe Jev hiện đang ad-hoc — `jev_router.py` gọi SDK trực tiếp với `jev-latest`, chỉ check threshold, không validate answer, không telemetry. Mọi consumer tương lai (routing, entity match, guardrails, intent) sẽ phải tự wire SDK và không có chuẩn chung.

**Approach:** Xây `app/services/decision/` — `DecisionService` port (Protocol) với `JevBackend` (typesafe-sdk) + `MockBackend` (tests); kèm `QuestionRegistry`, `ConfidenceGate`, strict answer validation, env flags, và TokenUsage telemetry — theo ARCHITECTURE-SPINE AD-J1..J10. LLMJsonBackend + fallback chain: story sau (deferred-work).

## Boundaries & Constraints

**Always:**
- Caller chỉ dùng `DecisionService.decide(state, questions) -> DecisionResult`; chỉ `backends/jev.py` được import `typesafe_sdk` (AD-J1).
- Strict validation mọi `Answer` trước khi vào `DecisionResult`: Choice/Score — id ∈ offered ids, probability keys khớp ids, values finite ∈[0,1], sum ≈1±0.02, chosen=argmax; Noul — finite float ∈[0,1]. Fail → `InvalidDecisionAnswer` → caller fallback, không bao giờ thành action (port pattern `validate_choice()` từ jev-ultrafast — reference only, không vendor).
- Pin model `jev-1.13.0` qua `DECISION_JEV_MODEL`; log `model` trên mọi response (AD-J3). Không dùng `jev-latest`.
- `DECISION_ENABLED` master + `DECISION_{TASK}_ENABLED` per-task flags gate mọi call; khi tắt/error, caller giữ nguyên behavior cũ (advisory/additive).
- Jev error (5xx/529/timeout/missing key) → raise `DecisionError` → caller fallback. (LLM fallback chain: deferred.)
- Mọi `decide()` log `input_tokens`, `output_tokens`, `latency_ms`, `model`, `backend` vào `TokenUsage` qua `record_token_usage` (fail-open) (AD-J7).
- Question instructions viết English; `state` giữ nguyên Vietnamese — không dịch (AD-J8).
- Timeout ceiling `DECISION_TIMEOUT_SECONDS` (default 5.0s).

**Ask First:**
- Thêm dependency mới (hiện `typesafe-sdk>=0.7.0` đã có trong pyproject — không cần thêm).
- Sửa `jev_router.py` hoặc wire `DecisionService` vào caller nào (thuộc story 39.2+).

**Never:**
- Không integrate vào caller cụ thể (middleware routing, entity pipeline, guardrail path) — story này chỉ build foundation.
- Không LLMJsonBackend/litellm fallback trong story này — đã split sang story sau.
- Không import `typesafe_sdk` ngoài `backends/jev.py`; không generation path (AD-J6).
- Không decision nào trong billing path; không streaming; không vendor code jev-ultrafast.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| happy_jev | `TYPESAFE_API_KEY` set, `DECISION_BACKEND=jev`, state + questions hợp lệ | `DecisionResult(answers, model="jev-1.13.0", backend="jev", latency_ms, input_tokens)` | n/a |
| jev_error | Jev trả 5xx/529/timeout hoặc thiếu API key | `decide()` raise `DecisionError` → caller fallback | `DecisionError` |
| disabled | `DECISION_ENABLED=false` | `decide()` raise `DecisionError(code="disabled")` | `DecisionError` |
| malformed_answer | choice ∉ ids / probs sum≠1 / chosen≠argmax / noul ∉[0,1] | Không trả answer về caller | `InvalidDecisionAnswer` |
| mock_backend | `DECISION_BACKEND=mock` | `MockBackend` trả deterministic answers | n/a |
| registry | `registry.get("subagent_routing")` | Versioned dict `Choice`/`Score`/`Noul`; tên lạ → `KeyError` kèm available names | n/a |
| gate | `ConfidenceGate(threshold=0.6)` + answer.confidence | `passes()` true/false; env `DECISION_{TASK}_THRESHOLD` override | n/a |

</frozen-after-approval>

## Code Map

- `app/services/decision/service.py` — NEW: `DecisionResult`/`Answer` types + `DecisionService` facade (flag → backend → validate → telemetry) + `get_decision_service()` singleton — copy `app/services/composio/service.py:37-49`.
- `app/services/decision/backends/{jev,mock}.py` — NEW: backend-by-config precedent `app/file_storage/factory.py:16-38`.
- `app/services/decision/questions/` — NEW: `QuestionRegistry` + 4 question sets port từ `scripts/jev_eval/cases.py:846-903` (AD-J5).
- `app/services/decision/gate.py` — NEW: `ConfidenceGate` + thresholds (AD-J4).
- `app/services/decision/validation.py` — NEW: strict `validate_answer()`.
- `app/services/decision/errors.py` — NEW: `DecisionError` + `InvalidDecisionAnswer` extends `NowingError` (`app/exceptions.py:27-42`; per-module precedent `app/etl_pipeline/exceptions.py`).
- `app/config/decision.py` — NEW flags; copy `app/config/memory.py:14-54` + `app/config/_helpers.py:31-86`; register `app/config/__init__.py:48-71`.
- `app/services/token_tracking_service.py:54-77` — thêm `UsageType.DECISION`; signature `record_token_usage` `:573-594`; call-site mẫu `app/capabilities/core/billing.py:607-619`.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py:126-135,196-201` — REFERENCE ONLY (không sửa): `client.system_one(state, questions, model=)` call shape.
- `scripts/jev_eval/runner.py:99-185` — canonical system_one call + `response.answers`/`response.usage` extraction.
- `nowing_backend/pyproject.toml:108` — `typesafe-sdk>=0.7.0` đã là dep.
- `tests/unit/services/news/test_rss_fetcher.py` + `test_code_search.py:196-218` — test style (module-level async, `@pytest.mark.unit`, monkeypatch/respx fakes); `pyproject.toml:254,269-276` asyncio auto + markers.

## Tasks & Acceptance

**Execution:**
- [x] `app/services/decision/errors.py` — NEW — `DecisionError(NowingError)` + `InvalidDecisionAnswer` — taxonomy fallback thống nhất.
- [x] `app/services/decision/validation.py` — NEW — `validate_answer(answer, question)` strict checks per matrix.
- [x] `app/services/decision/backends/jev.py` — NEW — `AsyncTypeSafeClient().system_one(state, questions, model=DECISION_JEV_MODEL)` → map `response.answers`/`response.usage`; timeout `DECISION_TIMEOUT_SECONDS`; lazy import SDK.
- [x] `app/services/decision/backends/mock.py` — NEW — deterministic answers theo question type.
- [x] `app/services/decision/questions/` — NEW — registry + 4 question modules port từ `cases.py`.
- [x] `app/services/decision/gate.py` — NEW — `ConfidenceGate` + `DECISION_{TASK}_THRESHOLD` env override.
- [x] `app/services/decision/service.py` — NEW — facade + `get_decision_service()` + telemetry logging.
- [x] `app/config/decision.py` + `app/config/__init__.py` — NEW flags + register.
- [x] `app/services/token_tracking_service.py` — `UsageType.DECISION = "decision"`.
- [x] `tests/unit/services/decision/` — NEW — validation per malformed case, disabled flag, jev_error → DecisionError, registry load/KeyError, gate thresholds + env override, mock determinism, telemetry args (monkeypatch `record_token_usage`).

**Acceptance Criteria:**
- Given `TYPESAFE_API_KEY` set, when `DecisionService` instantiated với `DECISION_BACKEND=jev`, then `decide(state, questions)` gọi `POST /v1/systemone` qua `AsyncTypeSafeClient` và trả `DecisionResult` với typed answers + confidence + latency + token usage.
- And `DecisionResult` carries `model` field (vd `jev-1.13.0`) logged per call (AD-J3).
- And `QuestionRegistry` loads named question sets từ `app/services/decision/questions/` — versioned dicts of `Choice`/`Score`/`Noul` (AD-J5).
- And `ConfidenceGate` applies per-task thresholds (routing=0.6, filter=0.5, entity=0.7, intent=0.5) với env-var overrides (AD-J4).
- And `MockBackend` returns expected answers deterministically cho unit tests.
- And feature flag `DECISION_ENABLED` + per-task flags gate all decision calls.
- And all calls log `input_tokens`, `output_tokens`, `latency_ms`, `model`, `backend` to `TokenUsage` (AD-J7).
- And mọi answer qua strict structural validation — malformed/miscalibrated → `InvalidDecisionAnswer` → caller falls back, never becomes an action.
- And Jev error (5xx/529/timeout) → `DecisionError` propagate tới caller (LLMJsonBackend fallback chain: deferred story).

## Spec Change Log

## Design Notes

- `decide()` tự check `DECISION_ENABLED` → raise `DecisionError(code="disabled")` — caller chỉ catch `DecisionError`, khỏi check flag mọi call site.
- `Answer` shape: `{"kind": "choice"|"score"|"noul", "value": ..., "confidence": float, "probabilities": dict|None}` — validation branch theo `kind`.
- Error taxonomy: `InvalidDecisionAnswer` (answer xấu — không retry) vs `DecisionError` (transport/backend/flag) — cả hai đều → caller fallback.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/decision app/config/decision.py app/config/__init__.py app/services/token_tracking_service.py tests/unit/services/decision` — clean
- `cd nowing_backend && ruff format app/services/decision app/config/decision.py tests/unit/services/decision` — no diff
- `cd nowing_backend && uv run pytest tests/unit/services/decision -m unit -q` — all pass
- `cd nowing_backend && uv run python -c "from app.services.decision.service import get_decision_service; print('import OK')"` — import OK

## Suggested Review Order

**Port contract — entry point**

- Toàn bộ contract của story: flag gate → backend → strict validation → telemetry; đọc hàm này trước.
  [`service.py:57`](../../nowing_backend/app/services/decision/service.py#L57)

**Gating & port-level guarantees**

- Backend resolve lazy sau flag check — `DECISION_BACKEND=llm_json` chỉ lỗi khi thật sự được gọi, không phá `get_decision_service()` khi disabled.
  [`service.py:52`](../../nowing_backend/app/services/decision/service.py#L52)

- Pin `jev-1.13.0` ở port — caller truyền model khác → `invalid_model`, không bypass được AD-J3.
  [`service.py:109`](../../nowing_backend/app/services/decision/service.py#L109)

- Hard ceiling ở port (`asyncio.wait_for`) — mọi backend kể cả Mock đều bị chặn, timeout → `code="timeout"`.
  [`service.py:129`](../../nowing_backend/app/services/decision/service.py#L129)

**Strict answer validation**

- Dispatch theo `kind` — mọi answer phải qua đây trước khi vào `DecisionResult`.
  [`validation.py:42`](../../nowing_backend/app/services/decision/validation.py#L42)

- Argmax check với `1e-9` tolerance — float near-tie của model không bị reject oan.
  [`validation.py:107`](../../nowing_backend/app/services/decision/validation.py#L107)

- Confidence validate cho cả 3 kinds, reject `bool`/non-finite — lỗ hổng noul đã bịt.
  [`validation.py:141`](../../nowing_backend/app/services/decision/validation.py#L141)

**Jev adapter (duy nhất import typesafe_sdk)**

- Adapter `AsyncTypeSafeClient.system_one` — timeout SDK + `TimeoutError` → `code="timeout"` riêng.
  [`jev.py:135`](../../nowing_backend/app/services/decision/backends/jev.py#L135)

- Normalize SDK answer → `Answer`; field thiếu → `InvalidDecisionAnswer` thống nhất, không còn `str(None)`/`float(None)`.
  [`jev.py:75`](../../nowing_backend/app/services/decision/backends/jev.py#L75)

**Registry & confidence gate**

- `get()` trả copy — caller mutate không phá singleton registry.
  [`registry.py:41`](../../nowing_backend/app/services/decision/questions/registry.py#L41)

- `for_task` đọc env override tại call time; non-finite → warning + fallback default.
  [`gate.py:44`](../../nowing_backend/app/services/decision/gate.py#L44)

**Config & telemetry**

- Model pin + non-finite timeout guard — `DECISION_TIMEOUT_SECONDS=inf` không tắt được ceiling.
  [`decision.py:36`](../../nowing_backend/app/config/decision.py#L36)

- `UsageType.DECISION` — enum member mới; `usage_type` là `String(50)`, không cần migration.
  [`token_tracking_service.py:78`](../../nowing_backend/app/services/token_tracking_service.py#L78)

- Persist `TokenUsage` fail-open trong `finally` — kể cả path `InvalidDecisionAnswer` vẫn ghi spend.
  [`service.py:205`](../../nowing_backend/app/services/decision/service.py#L205)

**Peripherals**

- 4 question sets versioned port từ `jev_eval/cases.py`; mock backend deterministic cho tests.
  [`questions/registry.py`](../../nowing_backend/app/services/decision/questions/registry.py)

- 65 unit tests + import-guard AST test cấm `typesafe_sdk` ngoài `backends/jev.py` (AD-J1).
  [`tests/unit/services/decision/`](../../nowing_backend/tests/unit/services/decision/)

- Env docs cho toàn bộ `DECISION_*` flags + `TYPESAFE_API_KEY`.
  [`.env.example:837`](../../nowing_backend/.env.example#L837)
