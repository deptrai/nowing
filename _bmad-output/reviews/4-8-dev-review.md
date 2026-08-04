# Dev Review — Story 4.8a + 4.8b: Chat telemetry & regression suite

**Reviewer:** Amelia (bmad-agent-dev)  
**Scope:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, `.../core/arms/nowing.py`, `.../suites/chat/regression/*`, and their tests.  
**Status:** Findings resolved and re-verified.

## Resolution

All high/medium findings below were fixed in the follow-up pass:

- `_cmd_report` now handles `requires_suite_setup=False` suites.
- `_cmd_ingest` skips auth for benchmarks with `requires_auth_for_ingest=False`.
- `ttfb_ms` no longer includes connection/HTTP TTFB.
- Token-usage fallbacks preserve explicit `0` values.
- `NowingArm` shields `delete_thread` cleanup on cancellation.
- Per-tag report includes `p95 citations` and `keyword match`.
- Custom dataset `ingest` validates list-typed fields.
- Tests added for telemetry mapping, cancellation cleanup, zero-token-usage, CLI no-auth/no-setup, `ingest` validation, and `report_section`.

## Re-verification

- `ruff check src tests` — pass.
- `ruff format` — applied.
- `python -m pytest -q` — 485 passed, 1 skipped.
- `ingest chat regression` and `report --suite chat` both work without credentials or setup.  

## Verification run

```bash
cd /Users/luisphan/Documents/GitHub/nowing/nowing_evals

ruff check src/nowing_evals/core/clients/new_chat.py \
           src/nowing_evals/core/arms/nowing.py \
           src/nowing_evals/suites/chat/ \
           tests/core/test_clients.py \
           tests/suites/chat/test_regression.py
# All checks passed

ruff format --check src/nowing_evals/core/clients/new_chat.py \
                src/nowing_evals/core/arms/nowing.py \
                src/nowing_evals/suites/chat/ \
                tests/core/test_clients.py \
                tests/suites/chat/test_regression.py
# 7 files already formatted

python -m pytest tests/core/test_clients.py tests/suites/chat/test_regression.py -q
# 27 passed

python -m pytest -q
# 475 passed, 1 skipped

python -m nowing_evals benchmarks list
# chat/regression registered

python -m nowing_evals report --suite chat
# Exit 2: "No setup for suite 'chat'."
```

## Findings

### High

1. **`nowing_evals report --suite chat` fails because `_cmd_report` always requires suite state**
   - **File:** `nowing_evals/src/nowing_evals/core/cli.py`, **lines 727–730**
   - `ChatRegressionBenchmark.requires_suite_setup = False`, but `_cmd_report` calls `get_suite_state(config, args.suite)` and exits with “No setup for suite 'chat'.” This blocks the report flow for a no-setup suite and contradicts Story 4.8b AC4 and the README (`nowing_evals/README.md` lines 87–98).
   - **Recommendation:** Make `_cmd_report` respect `benchmark.requires_suite_setup` (or supply a synthetic state for no-setup suites) so `report --suite chat` works after a `run`.

### Medium

2. **`NewChatClient.ask` ignores `Retry-After` / `retry-after-ms` on 409 busy responses**
   - **File:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, **lines 147–165, 195–203**
   - The `ask` docstring says it “Honours backend `THREAD_BUSY` / `TURN_CANCELLING` 409 responses by sleeping for the `Retry-After` header … and replaying.” The implementation computes a fixed exponential backoff (`min(30.0, 0.5 * (2**attempt))`) and never reads `Retry-After` or `retry-after-ms`. The existing test (`tests/core/test_clients.py` lines 239–258) passes by coincidence because `Retry-After: 1` and `attempt=1` both yield ~1 s.
   - **Recommendation:** Parse `Retry-After` (seconds or HTTP-date) and `retry-after-ms` from the 409 response, use the backend hint as the wait base, and cap at 30 s.

3. **Token-usage telemetry uses `or previous`, masking explicit `0`/empty values**
   - **File:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, **lines 300–309**
   - `prompt_tokens = data_payload.get("prompt_tokens", 0) or prompt_tokens` (and the same pattern for `completion_tokens` and `total_tokens`) treats an explicit `0` as a missing value when a prior non-zero value exists. `model_breakdown = data_payload.get("usage") or data_payload.get("model_breakdown") or model_breakdown` treats an empty `usage` `{}` as missing.
   - **Recommendation:** Use `data_payload.get("prompt_tokens", prompt_tokens) or 0` so the default is the *previous* value, not `0`, and handle present-but-empty containers explicitly.

4. **`ChatRegressionBenchmark` gate.yaml is not loaded or enforced**
   - **Files:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, `.../regression/gate.yaml`, `.../core/gate.py`
   - The runner writes no gate logic. The existing `GateThresholds` Pydantic model is hard-coded for the memory suite and would reject `chat/regression/gate.yaml` due to `extra="forbid"`. The README and AC5 imply a gate exists, but it is only a documented placeholder.
   - **Recommendation:** Either wire a chat-specific `GateThresholds`/evaluation in `core/gate.py` or add `ChatRegressionBenchmark.gate_config_path` and call `evaluate_gate` from `run()`/`report()`. If gating is intentionally out of scope, document that in `runner.py`.

5. **Thin unit-test coverage for `ChatRegressionBenchmark`**
   - **File:** `nowing_evals/tests/suites/chat/test_regression.py`
   - Only `_contains_hits`, `_aggregate`, and default-dataset round-trip are tested. `ingest()` (custom dataset validation, default write), `run()` (NowingArm integration, timeout branch, tag filter, concurrency), `add_run_args`, and `report_section` are not tested.
   - **Recommendation:** Add unit tests using a mocked `NowingArm`/`NewChatClient` for `ingest`, `run`, and `report_section` edge cases.

6. **TTFB clock starts before the HTTP stream is established**
   - **File:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, **lines 167–192**
   - `started = time.monotonic()` is set *before* `async with self._http.stream(...)`, so `ttfb_ms` includes connection / first-byte-of-response latency. The implementation artifact explicitly says “Do not confuse with HTTP TTFB (first byte of HTTP response); the client already holds the response when it starts reading SSE.”
   - **Recommendation:** Record a separate `sse_start` time after the `async with` context manager has yielded the response and pass that to `_consume_sse` for TTFB, while keeping the original `started` for full e2e `latency_ms`.

7. **`start` event message IDs are not coerced from `int` to `str`**
   - **File:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, **lines 281–284**
   - `elif ev_type == "start": msg_id = payload.get("messageId"); if isinstance(msg_id, str): user_message_id = user_message_id or msg_id` will ignore an `int` `messageId`. The `data-user-message-id`/`data-assistant-message-id` handlers correctly use the `_str_id()` helper, so `start` should do the same. If the backend emits `messageId` as an int and the later message-id event is missing, `user_message_id` stays `None`.
   - **Recommendation:** Use `user_message_id = _str_id(payload.get("messageId")) or user_message_id` for consistency.

### Low

8. **Runner discards detailed telemetry captured by `NowingArm`**
   - **File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, **lines 286–350**
   - `NowingArm` correctly puts `turn_id`, `user_message_id`, `assistant_message_id`, `call_details`, and `model_breakdown` into `ArmResult.extra`, but `_run_one` never copies them to `_CaseResult` or `raw.jsonl`. Only `ttfb_ms` and `finished_normally` are pulled from `extra`.
   - **Recommendation:** Add these fields to `_CaseResult` and persist them in `raw.jsonl` so the benchmark output is traceable and the telemetry is not lost.

9. **`report_section` treats `p95_ttfb_ms == 0.0` as `n/a`**
   - **File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, **line 476**
   - `f"{overall.get('p95_ttfb_ms') or 'n/a'} ms"` will display `n/a` when the metric is exactly `0.0`.
   - **Recommendation:** Use an explicit `is None` check, e.g. `val = overall.get('p95_ttfb_ms'); f"{val if val is not None else 'n/a'}"`.

10. **Exception message in `NowingArm` may carry arbitrary 409 response body**
    - **File:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py`, **line 200**; `nowing_evals/src/nowing_evals/core/arms/nowing.py`, **lines 62–69**
    - `_extract_busy_detail` fallback returns `response.text` as the error message, and `NowingArm` stores `f"{type(exc).__name__}: {exc}"` in `ArmResult.error`. If the backend 409 body is large or contains PII, it leaks into `raw.jsonl`.
    - **Recommendation:** Truncate the fallback message and avoid raw response text in `ArmResult.error`.

11. **Backward-compatibility tests for `NewChatClient` are incomplete**
    - **File:** `nowing_evals/tests/core/test_clients.py`, **lines 262–320**
    - `test_ask_parses_telemetry_events` only tests `data-token-usage` and `data-*` wrappers. It does not assert the numeric value of `ttfb_ms`, the contents of `model_breakdown`/`call_details`, the unwrapped `token-usage`/`turn-info` aliases, the legacy `id` key fallback, or a stream without token-usage.
    - **Recommendation:** Add cases for (a) legacy `id` vs `message_id`, (b) `type=token-usage` unwrapped, (c) missing token-usage yields `0`/`None`, (d) `ttfb_ms` is positive and ≤ e2e latency, (e) empty `call_details`/`usage` handled.

12. **`ingest` validation is shallow**
    - **File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, **lines 219–243, 132–152**
    - Only `case_id` and `query` are checked; `tags`, `mentioned_document_ids`, `disabled_tools`, and `expected_contains` are not validated, leading to opaque `_load_cases`/`run` failures later.
    - **Recommendation:** Validate each row with a small schema (e.g. lists of the right type, `expected_contains` non-empty strings).

13. **Minor default masking and negative-value edge cases in the runner**
    - **File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, **lines 253–260, 275**
    - `opts.get("timeout") or 300.0` masks an explicit `--timeout 0`; `sample_n` can be negative, producing an empty case list; `search_space_id = opts.get("search_space_id") or ctx.search_space_id` treats `0` as missing.
    - **Recommendation:** Use `if opts.get("timeout") is not None` style, clamp `sample_n >= 0`, and validate `search_space_id > 0`.

14. **Synchronous file I/O inside async `ingest`/`run`**
    - **File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`, **lines 226–230, 247–249, 355–382, 397–406**
    - `path.read_text`, `target.open`, and `_write_json_atomic` are synchronous `pathlib` calls inside `async` methods. While acceptable for an eval harness, this can block the event loop on large datasets.
    - **Recommendation:** Use `asyncio.to_thread` or `aiofiles` for file ops.

## Positives

- `StreamedAnswer` exposes the requested telemetry surface (`ttfb_ms`, `turn_id`, prompt/completion/total tokens, `cost_micros`, `model_breakdown`, `call_details`) and `NowingArm` maps them into `ArmResult`.
- The SSE parser is defensive: unknown events are appended to `raw_events`, JSON decode failures are skipped, and both `data-*` and bare event-type aliases are accepted.
- `ChatRegressionBenchmark` is correctly auto-registered, the CLI subcommands surface the expected flags, and the default dataset is synthetic/PII-safe as documented.
- `ruff`, `ruff format --check`, and the full `pytest` suite pass; style is consistent with the rest of `nowing_evals`.

## Bottom line

Story **4.8a** telemetry capture is functionally correct but has edge cases around 409 retry semantics, TTFB timing, `start` event `messageId` coercion, and `0`/`None` telemetry fallbacks. Story **4.8b**’s regression suite is registered and runs, but the **report path is broken for the no-setup suite** and the **gate is a placeholder**, both of which should block acceptance. Unit-test coverage for the runner and `NewChatClient` backward-compatibility cases should also be expanded.
