---
title: 'Story 39.5 — Intent Classification via Jev Choice (R5-low)'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '3c4b110f91496adaa78d47b1cd5a38e18ec3f291'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Vietnamese user chat messages carry no typed intent label — downstream analytics, auto-response templates, and escalation rules (per epics.md 39.5) have nothing machine-readable to act on. Jev already proves 95% accuracy on 20 VN intent cases at ~300ms.

**Approach:** Add `classify_intent()` — one `DecisionService.decide()` call with the registered `intent_classify@1.0.0` Choice set — and wire it into `persist_user_turn` so the intent label + confidence land on `new_chat_messages.platform_metadata["intent"]`. Advisory/fail-open; nothing blocks or mutates the message.

## Boundaries & Constraints

**Always:**
- Go through `get_decision_service().decide()` — never import `typesafe_sdk` outside `app/services/decision/backends/`.
- Use registry set `intent_classify` verbatim (no `dataclasses.replace`, no criteria override) — its 8 options carry the eval-tuned VN descriptions; pass `question_set=f"{qs.name}@{qs.version}"` (built from the registry, never hardcoded), `required_state_keys=qs.required_state_keys`, `task="intent"`.
- Gate with `ConfidenceGate.for_task("intent")` (env `DECISION_INTENT_THRESHOLD`, default 0.5). Only store when `gate.passes(answer)` — below threshold: log only, no metadata key (automation triggers must be able to read `label` naively).
- Fail-open everywhere: flag off, backend error, malformed answer, timeout → no metadata, message still persists. `classify_intent` never raises.
- Skip empty/whitespace `user_query` before any paid call.
- Never mutate the caller's `platform_metadata` dict — the same object is also passed to `persist_assistant_shell`; merge into a copy so the intent lands on the USER row only.
- Telemetry log-only (`[intent_classify]` logger) — persist context has no request `session`/`workspace_id`; do not open a session just for TokenUsage.

**Never:**
- No blocking/rerouting/answering based on intent — storage only.
- No rewiring of `auto_reply_agent.InboundIntentClassifier` (regex HOT path stays; it's a separate surface — see Design Notes).
- No update to `platform_metadata` on the conflict/`race_recovered` path (row already exists; advisory only).
- No second `decide()` call, no retries beyond the service's built-in fallback leg.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| PASS | `DECISION_ENABLED=true`, VN message, answer `value="search"`, conf=0.9 | `platform_metadata["intent"]={"label":"search","confidence":0.9,"model":...,"backend":...}` on user row; `[intent_classify]` log | N/A |
| BELOW_GATE | conf=0.3 (< 0.5) | no `intent` key; info log | N/A |
| FLAG_OFF | `DECISION_ENABLED=false` or `DECISION_INTENT_ENABLED=false` | `decide` raises `disabled` → caught → no `intent` key, insert proceeds | caught, debug log |
| BACKEND_ERR | backend raises / malformed answer | no `intent` key, insert proceeds | warning log, never raises |
| EMPTY_MSG | `user_query=""` or whitespace | zero `decide()` calls, no `intent` key | N/A |
| META_NONE | `platform_metadata=None` + PASS | creates `{"intent": {...}}` fresh dict | N/A |
| META_MERGE | `platform_metadata={"mode_x": True}` + PASS | user row gets `{"mode_x":True,"intent":{...}}`; caller's dict object unchanged (assistant row unaffected) | N/A |
| RACE | conflict → `race_recovered` | existing row returned, metadata NOT rewritten | N/A |

</frozen-after-approval>

## Code Map

- `app/services/decision/questions/intent_classify.py` — registered `intent_classify@1.0.0`: `QUESTIONS["intent"]` = `ChoiceQuestion` over 8 intents (`INTENT_OPTIONS`), `REQUIRED_STATE_KEYS=("user_message",)`. Do not modify.
- `app/services/decision/questions/registry.py` — `get_question_registry().get_set("intent_classify")` → `QuestionSet(name, version, questions, required_state_keys)`.
- `app/services/decision/service.py` — `get_decision_service().decide(state, questions, task=, question_set=, required_state_keys=)`; `model=None`/`timeout=None` → service pins (`jev-1.13.0`, `DECISION_TIMEOUT_SECONDS`).
- `app/services/decision/gate.py` — `ConfidenceGate.for_task("intent").passes(answer)` (:33-39, 77-86); choice `answer.value` = label str, `answer.confidence` = float.
- `app/services/decision/types.py` — `Answer{kind,value,confidence,probabilities}`, `DecisionResult{answers,model,backend,latency_ms,...}`.
- `app/tasks/chat/persistence.py` — `persist_user_turn` (:170): existing advisory `check_passage` block (:217-223, Story 39.4) is the co-location point; `platform_metadata` written at `.values(...)` (:256). Run both advisory checks via `asyncio.gather` so latencies overlap (~300ms total, not serial ~600ms — this task is awaited before streaming starts).
- `app/services/content_guardrails/service.py` — mirror module shape/fail-open style.
- `app/config/decision.py` — `decision_task_enabled("intent")` already registered; flag defaults on under master switch.
- `tests/unit/tasks/chat/test_persistence_guardrails.py` — fake-session fixture pattern to reuse for wiring tests.
- `app/services/decision/backends/mock.py` — MockBackend picks FIRST criteria key (`"search"`) at 0.9 → deterministic but single-label; tests needing other labels/below-gate use a stub backend (pattern: `tests/unit/services/entity_resolution` `_StubBackend`).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/intent_classification/__init__.py` + `service.py` — new module exporting `async classify_intent(user_message: str) -> dict | None`; returns `{"label","confidence","model","backend"}` on gate-pass else `None`; never raises
- [x] `nowing_backend/app/tasks/chat/persistence.py` — gather `check_passage` + `classify_intent` concurrently; merge intent payload into a copied `platform_metadata` before `.values()`
- [x] `nowing_backend/tests/unit/services/intent_classification/test_service.py` — service tests: pass/below-gate/flag-off/backend-error/malformed/empty; decide-kwargs spy (task, question_set, required_state_keys, model/timeout None)
- [x] `nowing_backend/tests/unit/tasks/chat/test_persistence_intent.py` — wiring tests: metadata written on pass, absent on flag-off/below-gate, caller dict unmutated, insert still succeeds on classify raise, race path untouched
- [x] `nowing_backend/scripts/verify_intent_classification_39_5.py` — live battery: ~10 VN messages across intents → real Jev labels/confidence printed (no DB needed)

**Acceptance Criteria:**
- Given `DECISION_ENABLED=true` + `DECISION_INTENT_ENABLED=true`, when a Vietnamese user message persists via `persist_user_turn`, then `decide()` is called with `intent_classify@1.0.0` and the passing label+confidence are stored on the message's `platform_metadata["intent"]`.
- Given any flag off / backend failure / malformed answer / low confidence, when a user message persists, then no `intent` key is written and persistence succeeds unchanged.
- Given eval harness baseline (95% on 20 VN cases, `scripts/jev_eval/summary.md`), when `intent_classify` is used verbatim, then AC eval bullet is satisfied without new eval work.

## Implementation Notes

- `classify_intent` short-circuits BEFORE `decide()` on empty/whitespace input and on either flag off (`decision_enabled()` + `decision_task_enabled("intent")`, both re-read env at call time) — same zero-work shape as `check_passage`; the FLAG_OFF row's observable outcome (no `intent` key, no paid call) is identical to catching the `disabled` raise.
- `persist_user_turn` wraps both advisory calls in per-leg `try/except` helpers and `asyncio.gather`s them — a raise in either (bug, not contract) can't break persistence and latencies overlap.
- Intent merge is `{**(platform_metadata or {}), "intent": payload}` assigned back to the local — the caller's dict object is never mutated (shared with `persist_assistant_shell`); on the conflict/`race_recovered` path the INSERT no-ops so the existing row's metadata is untouched.
- Wiring tests extract the INSERT payload via `stmt._values` (keys are `Column` objects → normalize with `.name`; values are `BindParameter` → `.value`).
- `pyproject.toml` gained a T201 per-file-ignore for the verify script (same as the 39.3/39.4 scripts).
- Verified: ruff clean (all touched paths); 141 targeted tests pass (`tests/unit/services/intent_classification` + `tests/unit/tasks/chat`); full unit suite 6953 pass — 8 fails all pre-existing (7 phone_waterfall AsyncMock `scalar_one_or_none`, 1 pat_fail_closed_static route drift; spec's "5" was bounded by `--maxfail=5`, actual phone-waterfall count is 7 on baseline).
- Live verify RUN against real Jev (`jev-1.13.0`, `intent_classify@1.0.0`, 10 real calls): **9/10 labels matched** — the single MISS is `intent_01` ("Tìm quán phở ngon" → `recommendation` conf 0.97 vs expected `search`), the exact borderline case documented in the 95% eval baseline. Edge cases return `None` with zero backend calls. Confidences 0.76–1.00. Note: `TYPESAFE_API_KEY` lives in `XActions/.env` (sibling repo), not `nowing_backend/.env` — export it before running the script.
- Post-review state: 14 triage rows, 11 patched (input hardening, spoofed-`"intent"` strip, dict-copy, perf-log t0, vacuous turn_id test, hermeticity fixture, verify-script asserts) + 3 rejected (see Triage Log). Post-patch targeted run: **170 passed** (`tests/unit/services/intent_classification` + `tests/unit/tasks/chat` + `tests/unit/services/content_guardrails`), ruff clean.

## Spec Change Log

## Review Triage Log

- `persistence.py` guardrail tests don't stub `classify_intent` → host `DECISION_ENABLED=true` makes unit tests issue real paid calls — **medium** → patch (autouse `_stub_intent` fixture added to `test_persistence_guardrails.py`).
- `test_advisory_skipped_when_turn_id_missing` vacuous — AssertionError swallowed by the advisory wrapper — **medium** → patch (flag-recording spies assert zero invocations on both legs).
- `run_edge` prints without asserting; `_check_env` accepts `1`/`yes` while `_env_flag` only honors `true`; no `DECISION_BACKEND=jev` check — **medium** → patch (strict flag parse, backend check, `assert payload is None`).
- `user_message` non-str escapes via `.strip()` before the try — violates never-raises — **low** → patch (`isinstance` guard).
- `user_message` sent to paid `decide()` untruncated (sibling caps at 4000) — **medium** → patch (`_MAX_MESSAGE_CHARS = 4000`).
- `{**platform_metadata}` raises TypeError on truthy non-dict outside the try — **low** → patch (`isinstance` guard).
- Caller-supplied `"intent"` key survives when classifier returns None — `platform_metadata` is client-controlled → spoofable label — **medium** → patch (pre-existing `"intent"` stripped before merge).
- `qs.questions` passed by reference (only `registry.get()` copies) — **low** → patch (`dict(qs.questions)`; spy test now asserts copy).
- `t0` after gather → advisory latency invisible in perf log; success log missing `latency_ms`; docstring doesn't mention `intent` key — **low** → patch (t0 moved, latency logged, docstring line added).
- `_choice_answer` helper ignores `confidence` param in the distribution (argmax 0.9 vs claimed 0.3) — **low** → patch (distribution built from `confidence`).
- No test for `check_passage`-raises-while-classify-succeeds leg — **low** → patch (`test_guardrail_raise_does_not_block_intent`).
- TokenUsage could be wired via the `ws` session + `thread.workspace_id` — **rejected**: spec's frozen boundary deliberately chose log-only telemetry; passing the shielded persist session into `decide()` couples a paid advisory call to the write transaction and re-opens the shared-session concern 39.4 removed.
- Paid classify call wasted on the conflict/`race_recovered` path — **rejected**: the RACE matrix row accepts it; pre-checking row existence adds a query on every persist for a rare path.
- `_bmad/marketing-growth` `-dirty` submodule marker in the diff — **rejected**: unrelated working-tree artifact, excluded from the commit.

## Design Notes

- **Why `persist_user_turn` and not the orchestrator:** it is the single chokepoint where the user row is written — intent must land in the same INSERT or it needs a second UPDATE. The 39.4 advisory hook already sits here; gathering both keeps wall-clock at ~max(checks) instead of sum.
- **Gate-only storage:** storing low-confidence labels would poison naive downstream triggers; the log line keeps them observable for tuning `DECISION_INTENT_THRESHOLD`.
- **`auto_reply_agent.InboundIntentClassifier` stays regex:** that classifier drives hot-lead Telegram alerts on *external inbound* channels — a different surface with its own scoring semantics. Rewiring it is a separate product decision (candidate for deferred-work).
- **Coverage scope:** `persist_user_turn` only runs on the new_chat flow (`persistence_spawn.py` is its sole caller); resume/edit flows never re-persist the user row, so a resumed turn keeps the intent classified at original persist — correct, not a gap. External inbound channels (auto_reply) don't pass through here at all.
- **Shared-dict hazard is real:** `platform_metadata` is the same object in `spawn_persist_user_task` (orchestrator:299) and `spawn_persist_assistant_shell_task` (_stages:562) — mutating it in `persist_user_turn` would stamp the user's intent onto the assistant row. Merge into `{**platform_metadata, "intent": payload}` instead.
- **MockBackend caution:** choice answers always pick the first criteria key — `"search"` at 0.9 — so mock-mode yields a constant label; fine for plumbing tests, wrong for label-coverage assertions.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/intent_classification app/tasks/chat tests/unit/services/intent_classification tests/unit/tasks/chat` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/services/intent_classification tests/unit/tasks/chat -m unit -q` — expected: all pass
- `cd nowing_backend && uv run pytest tests/unit/ -m unit -q` — expected: no new failures vs known baseline (7 phone-waterfall + 1 pat-static pre-existing)
- `TYPESAFE_API_KEY=... DECISION_ENABLED=true DECISION_INTENT_ENABLED=true DECISION_BACKEND=jev uv run python scripts/verify_intent_classification_39_5.py` — expected: real labels for ~10 VN messages, no errors
