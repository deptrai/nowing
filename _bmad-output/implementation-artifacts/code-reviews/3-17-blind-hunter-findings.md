# Blind Hunter Findings — Story 3.17

## Findings

- **p1 — Truncation telemetry is driven by a private renderer marker and a substring check, coupling middleware to renderer internals and under-counting non-body truncation paths.**
  - **Problem:** `MemoryInjectionMiddleware` imports the private `_MEMORY_WARNING` constant from `app.services.memory.renderer` and uses `if _MEMORY_WARNING in rendered:` to infer that truncation occurred. This is a tight, hidden coupling to a renderer-internal string and an ad-hoc detection heuristic. It only fires when `render_bounded_memory_injection` reaches Rule 9 (memory-body overflow). It does *not* fire for Rule 8 display-name shrinkage/truncation (`_fit_name`) or the name-only render path (`_render_name_only`), which also truncate to fit the 8,000-char budget. The `nowing.memory.injection.truncated` counter therefore under-reports truncation events and will silently break if the warning string is renamed, moved, or embedded differently.
  - **Evidence:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:40-43` (private import) and `:301-305` (substring check); `nowing_backend/app/services/memory/renderer.py:176-194` (`_render_name_only` / `_fit_name`), `:331-339` (Rule 8 name shrink), `:341-343` (Rule 9 appends `_MEMORY_WARNING`).

- **p2 — `record_memory_injection_truncated` silently swallows all exceptions and provides no log fallback.**
  - **Problem:** The helper wraps `_add` in `contextlib.suppress(Exception)`, which is consistent with neighbors but hides any OpenTelemetry setup or attribute error without a trace. Unlike `record_memory_injection_failure`, it does not log to a Python logger, so when OTel is disabled or the `add` fails, the truncation event leaves no audit trail and cannot be debugged from logs.
  - **Evidence:** `nowing_backend/app/observability/metrics.py:1043-1051` (new helper, no log) vs. `:1019-1032` (failure helper logs and counts).

- **p2 — The new metric name is inconsistent with the adjacent failure counter.**
  - **Problem:** Existing counter is `nowing.memory.injection.failures` (plural noun). The new counter is `nowing.memory.injection.truncated` (past participle) while its description refers to "truncations". Inconsistent naming makes metric discovery, dashboards, and query patterns error-prone.
  - **Evidence:** `nowing_backend/app/observability/metrics.py:1013-1015` (`...failures`) and `:1037-1039` (`...truncated`).

- **p2 — Truncation counter attributes only capture `scope`, missing the richer label model used elsewhere.**
  - **Problem:** The new counter records only `{"scope": scope}`. The failure counter records `scope`, `stage`, and `reason`. At minimum, a `stage`/`component` label on the truncation counter (body / name-only) would make the under-counting in Finding 1 observable from metrics and allow the team to distinguish memory-body truncations from display-name truncations.
  - **Evidence:** `nowing_backend/app/observability/metrics.py:1049` (truncation attrs) vs. `:1026` (failure attrs).

- **p2 — New unit tests do not cover name-only or name-shrink truncation paths.**
  - **Problem:** The added tests only exercise Rule 9 body overflow and the no-truncation case. They do not exercise Rule 8 (display name is shrunk or omitted to fit) or the `_render_name_only` path, so the suite cannot catch the missing counter emissions described in Finding 1.
  - **Evidence:** `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:538-565`.

- **p2 — A truncated memory can be double-counted with a pending display-name failure for the same turn.**
  - **Problem:** `record_memory_injection_truncated` is emitted *before* the `pending` failure handling. If display-name lookup fails (`pending = ("display_name", "lookup_error")`) and the memory body is also truncated, both `record_memory_injection_truncated` and `record_memory_injection_failure` fire. The turn is still injected, but this conflates a "truncated but injected" event with a "recoverable failure" event and may over-state the failure/truncation correlation in dashboards.
  - **Evidence:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:301-310`.

## Validation notes

- `ruff check` on the three changed files passed.
- `pytest` could not be executed because the active venv has an incompatible `huggingface-hub`/`sentence-transformers` stack that fails during `conftest.py` import, unrelated to the diff.
