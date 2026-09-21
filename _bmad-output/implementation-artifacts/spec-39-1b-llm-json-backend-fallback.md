---
title: 'Story 39.1b: LLMJsonBackend + Jev→LLM Fallback Chain'
type: 'feature'
created: '2026-09-22'
status: 'done'
review_loop_iteration: 0
baseline_commit: '93c40fbdebb128eef034e0fdee78b00e81ab4c9b'
context:
  - '_bmad-output/implementation-artifacts/epic-39-context.md'
  - '_bmad-output/implementation-artifacts/spec-39-1-decision-service-port-jev-backend.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 39.1 đã reserve `DECISION_BACKEND=llm_json` nhưng raise `backend_unavailable` — khi Jev down/timeout/không có API key, decision path chết hoàn toàn thay vì fallback sang LLM (AD-J2, epic context: "fallback chain jev → llm_json on 5xx/529/timeout").

**Approach:** Implement `LLMJsonBackend` (litellm structured output, port từ `scripts/jev_eval/runner.py:193-296` LLM baseline) + service-level fallback: primary backend raise `DecisionError` code ∈ {`timeout`, `backend_error`, `backend_unavailable`, `missing_api_key`} → retry một lần qua `llm_json`, `DecisionResult.backend` phản ánh backend thật sự trả lời.

## Boundaries & Constraints

**Always:**
- `LLMJsonBackend` implement đúng `DecisionBackend` protocol (`backends/base.py`) — trả `BackendResult` unvalidated, mọi failure raise `DecisionError` (không leak litellm exceptions); service-level strict validation giữ nguyên không đổi.
- Một `decide()` = MỘT `litellm.acompletion` call cho toàn bộ `questions` (batch như `system_one`), `temperature=0`, `response_format` json_schema strict.
- LLM phải trả per-option `probabilities` cho choice/score — `Answer.probabilities` keys == offered ids, sum 1±0.02, argmax = chosen (strict validation đòi, không được nới).
- Fallback CHỈ trigger trên `DecisionError` code ∈ {`timeout`, `backend_error`, `backend_unavailable`, `missing_api_key`}; `InvalidDecisionAnswer`/`disabled`/`invalid_request`/`invalid_model` KHÔNG fallback (malformed answer không retry — tốn tiền).
- Telemetry ghi backend+model+tokens của leg thắng; fallback event log `logger.warning` rõ primary code lỗi.
- `DECISION_LLM_MODEL` env (default `"claude-haiku-4-5-20251001"` — eval baseline model), `DECISION_FALLBACK_BACKEND` env (`"llm_json"`|`"none"`, default `"llm_json"`).
- Model pin backend-aware: jev → `DECISION_JEV_MODEL`, llm_json → `DECISION_LLM_MODEL`; `model` kwarg nếu truyền phải bằng pin của backend đang dùng.

**Ask First:** chọn default LLM model khác `claude-haiku-4-5-20251001`; thay đổi semantics `DECISION_BACKEND` hiện có; bật fallback cho `InvalidDecisionAnswer`.

**Never:**
- Không fallback/retry trên `InvalidDecisionAnswer` hoặc caller errors.
- Không vendor/copy `typesafe_sdk`; chỉ `backends/jev.py` được import nó (import-guard test đang enforce).
- Không dùng Jev cho text generation; LLMJsonBackend chỉ trả typed answers qua structured output.
- Không thêm dependency mới (litellm đã có); không wire callers (`jev_router.py` vẫn là scope 39.2).
- Không tách fallback thành per-question calls; không nới strict validation cho LLM answers.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LLM_PRIMARY | `DECISION_BACKEND=llm_json`, questions hợp lệ | `DecisionResult.backend="llm_json"`, `model=DECISION_LLM_MODEL`, typed answers qua validation | N/A |
| FALLBACK_TIMEOUT | jev primary, `system_one` timeout | llm_json trả lời, `backend="llm_json"`, warning log code=`timeout` | fallback thành công → result bình thường |
| FALLBACK_FAILS | jev timeout + llm_json cũng fail | `DecisionError` của llm_json propagate | caller fallback như cũ |
| NO_FALLBACK_INVALID | jev trả malformed answer (`InvalidDecisionAnswer`) | `InvalidDecisionAnswer` propagate, llm_json KHÔNG được gọi | không tốn paid call |
| NO_FALLBACK_FLAG | `DECISION_FALLBACK_BACKEND=none`, jev fail | `DecisionError` của jev propagate nguyên trạng | N/A |
| LLM_BAD_JSON | llm_json trả invalid JSON/schema mismatch | `InvalidDecisionAnswer` | malformed ≠ retryable |
| LLM_TRANSPORT | litellm `Timeout`/`APIConnectionError`/`RateLimitError` | `DecisionError(code="timeout"` hoặc `"backend_error")` | taxonomy thống nhất |
| MODEL_PER_BACKEND | `model="gpt-4o"` khi backend=llm_json | `DecisionError(code="invalid_model")` nếu ≠ `DECISION_LLM_MODEL` | pin per-backend |
| BOTH_DISABLED | `DECISION_ENABLED=false` | `code="disabled"`, không backend nào chạy | gate trước fallback |

</frozen-after-approval>

## Code Map

- `app/services/decision/backends/llm_json.py` — NEW — port `scripts/jev_eval/runner.py:193-296` (`_build_llm_prompt` + `run_llm_json`): prompt build, strict `json_schema`, `temperature=0`, `json.loads(content)` → `Answer`.
- `scripts/jev_eval/runner.py:193-296` — REFERENCE ONLY — LLM baseline prompt/schema/parse; eval trả 1 question/call → adapt sang batch 1 call cho `dict[str, Question]`.
- `app/tasks/chat/streaming/flows/new_chat/title_gen.py:143-153` — canonical litellm call envelope: `acompletion(timeout=..., num_retries=1)` + `asyncio.wait_for` (port-level `wait_for` đã có sẵn ở service — backend không cần wrap lại, giống jev.py vẫn giữ belt-and-suspenders được).
- `app/services/hybrid_llm_router.py:487-521` — `_build_response_format` + retry `{"type":"json_object"}` khi provider không support strict schema; `litellm.drop_params` precedent `app/lead_intelligence/reverse_icp.py:224-246`.
- `app/services/memory/pipeline.py:24-61` — litellm exception taxonomy: transient (`Timeout`/`APIConnectionError`/`RateLimitError`/`ServiceUnavailableError`/`InternalServerError`) vs terminal (`AuthenticationError`/`BadRequestError`).
- `app/services/decision/service.py:57-194` — `decide()` gate order hiện tại; fallback hook ngay sau `except DecisionError`/`timeout` của leg primary (trước validation/telemetry block); `DecisionResult.backend`/`model` lấy từ leg thắng.
- `app/services/decision/service.py:258-276` — `_build_backend()`: `"llm_json"` hiện raise `backend_unavailable` → map sang `LLMJsonBackend()`; fallback backend resolve qua helper riêng.
- `app/services/decision/backends/mock.py` — contract deterministic answers (cho fallback tests: fake backend raise từng code).
- `app/config/decision.py` — thêm `DECISION_LLM_MODEL`, `DECISION_FALLBACK_BACKEND` (`_env_choice` pattern dòng 33); export ở `__all__`.
- `tests/unit/services/decision/` — test conventions: `_enabled` fixture pin flags, monkeypatch `record_token_usage`, import-guard AST test.
- `nowing_backend/.env.example:837-` — DECISION_* block đã có, thêm 2 vars mới.

## Tasks & Acceptance

**Execution:**
- [x] `app/services/decision/backends/llm_json.py` — NEW — `LLMJsonBackend(name="llm_json")`: build prompt+strict schema cho batch questions, `acompletion` (`timeout`, `num_retries=1`), parse JSON → `Answer`s, map exceptions → `DecisionError` taxonomy, malformed → `InvalidDecisionAnswer`, `BackendResult` với usage từ `response.usage`.
- [x] `app/config/decision.py` — `DECISION_LLM_MODEL` + `DECISION_FALLBACK_BACKEND` (`_env_choice`); update `__all__` + `nowing_backend/.env.example`.
- [x] `app/services/decision/service.py` — `_build_backend()` map `llm_json`; model pin per-backend; fallback block sau leg primary (codes whitelist), fallback model = `DECISION_LLM_MODEL`, `DecisionResult.backend` = leg thắng, warning log.
- [x] `tests/unit/services/decision/test_llm_json_backend.py` — NEW — schema/prompt build, parse+normalize (probabilities array→dict), error taxonomy, malformed JSON → `InvalidDecisionAnswer`, usage extraction (fake `acompletion` qua monkeypatch).
- [x] `tests/unit/services/decision/test_service.py` — extend — fallback trên từng trigger code, no-fallback (`InvalidDecisionAnswer`, disabled, `none`), `DecisionResult.backend` đúng leg, telemetry ghi leg thắng, model pin per-backend, `DECISION_BACKEND=llm_json` path.

**Acceptance Criteria:**
- Given `DECISION_BACKEND=llm_json`, when `decide(state, questions)`, then một `litellm.acompletion` strict-schema call trả `DecisionResult(backend="llm_json")` với answers pass strict validation (probabilities đủ ids, sum≈1, argmax=chosen).
- And `DECISION_BACKEND=jev` + Jev fail (`timeout`/`backend_error`/`missing_api_key`/`backend_unavailable`) → auto-fallback `llm_json`, result `backend="llm_json"`, `model=DECISION_LLM_MODEL`.
- And `InvalidDecisionAnswer` hoặc `DECISION_FALLBACK_BACKEND=none` → KHÔNG fallback, error propagate nguyên trạng.
- And cả hai leg fail → `DecisionError` của fallback leg propagate tới caller.
- And mọi call (primary hoặc fallback) vẫn log `input_tokens`/`output_tokens`/`latency_ms`/`model`/`backend` của leg thắng vào `TokenUsage` (fail-open như hiện tại).

## Spec Change Log

## Design Notes

- Schema strict cần tránh dynamic keys (question ids + option ids động) → dùng array form: `{"answers": [{"question_id": str, "answer": str|number, "confidence": number, "probabilities": [{"id": str, "p": number}]}]}`; normalize `probabilities` array → dict str-keyed, noul thì omit. Provider không support strict schema → retry 1 lần `{"type":"json_object"}` (hybrid_llm_router precedent).
- Fallback nằm ở service layer (không phải composite backend) vì telemetry + model pin + `DecisionResult.backend` cần biết leg nào thắng. Mỗi leg chịu `wait_for` riêng với cùng clamped timeout → worst-case latency = 2× `DECISION_TIMEOUT_SECONDS` (document trong docstring).
- Model pin: `model is not None and model != pinned_for_active_backend` → `invalid_model`; `None` → pin của backend đó.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/decision app/config/decision.py tests/unit/services/decision` — clean
- `cd nowing_backend && ruff format app/services/decision app/config/decision.py tests/unit/services/decision` — no diff
- `cd nowing_backend && uv run pytest tests/unit/services/decision -m unit -q` — all pass
- `cd nowing_backend && DECISION_ENABLED=true DECISION_BACKEND=llm_json uv run python -c "..."` — decide() qua LLMJsonBackend path (fake acompletion) OK

## Suggested Review Order

**Fallback chain (P0 — paid-call routing)**

- Trigger-code check chạy TRƯỚC khi build fallback — malformed/caller errors không tốn tiền.
  [`service.py:165`](../../nowing_backend/app/services/decision/service.py#L165)

- Construction-time `backend_unavailable` cũng đi qua fallback — backend resolution wrap trong try.
  [`service.py:122`](../../nowing_backend/app/services/decision/service.py#L122)

- Whitelist trigger codes — InvalidDecisionAnswer/caller errors cố tình absent.
  [`service.py:349`](../../nowing_backend/app/services/decision/service.py#L349)

- Model pin per-backend — llm_json → DECISION_LLM_MODEL, còn lại → Jev pin.
  [`service.py:354`](../../nowing_backend/app/services/decision/service.py#L354)

- Fallback builder: `none` tắt; `llm_json`/`mock` primary không fallback (no paid self-retry).
  [`service.py:410`](../../nowing_backend/app/services/decision/service.py#L410)

- Fallback leg fail → warning log backend+code trước khi propagate (spend leg fail vẫn visible).
  [`service.py:189`](../../nowing_backend/app/services/decision/service.py#L189)

**LLMJsonBackend (P0 — external paid calls)**

- Port entry: guarded litellm import, prompt→call→parse→usage, exception taxonomy.
  [`llm_json.py:310`](../../nowing_backend/app/services/decision/backends/llm_json.py#L310)

- Strict json_schema array-form — không dynamic keys, probabilities là [{"id","p"}].
  [`llm_json.py:52`](../../nowing_backend/app/services/decision/backends/llm_json.py#L52)

- Prompt batch 1 call cho mọi questions, spell out strict-validation constraints.
  [`llm_json.py:98`](../../nowing_backend/app/services/decision/backends/llm_json.py#L98)

- Schema-rejection gate — chỉ degrade sang json_object khi provider từ chối response_format.
  [`llm_json.py:169`](../../nowing_backend/app/services/decision/backends/llm_json.py#L169)

- `_call`: temperature=0, num_retries=1, max_tokens=4096, timeout forwarded.
  [`llm_json.py:185`](../../nowing_backend/app/services/decision/backends/llm_json.py#L185)

- Parse defensive: quoted-qid strip, duplicate/invalid → InvalidDecisionAnswer, không retry.
  [`llm_json.py:280`](../../nowing_backend/app/services/decision/backends/llm_json.py#L280)

- Missing/bool confidence → InvalidDecisionAnswer; noul value doubles as confidence.
  [`llm_json.py:238`](../../nowing_backend/app/services/decision/backends/llm_json.py#L238)

**Config & peripherals**

- `DECISION_FALLBACK_BACKEND` default `llm_json` + `DECISION_LLM_MODEL` pin.
  [`decision.py:36`](../../nowing_backend/app/config/decision.py#L36)

- `.env.example` document paid-call consequence + 2x worst-case latency.
  [`.env.example:845`](../../nowing_backend/.env.example#L845)

- Backend tests: taxonomy, parse edge cases, schema degrade, usage extraction.
  [`test_llm_json_backend.py`](../../nowing_backend/tests/unit/services/decision/test_llm_json_backend.py)

- Service fallback tests + literal config-default pinning tests.
  [`test_service.py`](../../nowing_backend/tests/unit/services/decision/test_service.py)
