# Edge Case Hunter Findings — Story 3.17

Reviewed the diff in `3-17-prompt-edge-case-hunter.md` and the related source files:

- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py`
- `nowing_backend/app/observability/metrics.py`
- `nowing_backend/app/services/memory/renderer.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py`

No p0 issues were found. The most significant finding is a **p1 undercount** in the new `memory_injection_truncated` counter: the middleware only fires the counter when the renderer emits `_MEMORY_WARNING`, which only happens in Rule 9 (memory-body truncation). Rule 8 name truncation and the name-only truncation path do not emit the warning, so they are not counted.

## Findings

- **Name-only and Rule-8 name truncation are not counted as truncations** — **p1**
  - **Edge case:** `_render_name_only` and Rule 8 both truncate long display names, but neither path appends `_MEMORY_WARNING`. The middleware only checks for `_MEMORY_WARNING` before calling `record_memory_injection_truncated`, so any truncation that happens in the name (or the name-only path) is silently not counted, even though the final injected text was truncated to fit `max_chars`.
  - **Evidence:**
    - `nowing_backend/app/services/memory/renderer.py:184-194` (`_render_name_only` truncates the name with `_TRUNCATION_MARKER`, no `_MEMORY_WARNING`)
    - `nowing_backend/app/services/memory/renderer.py:329-339` (Rule 8 shrinks/omits the name, no `_MEMORY_WARNING`)
    - `nowing_backend/app/services/memory/renderer.py:341-343` (Rule 9 is the only path that appends `_MEMORY_WARNING`)
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:304-305` (counter is keyed solely on `_MEMORY_WARNING`)
    - `nowing_backend/tests/unit/services/test_bounded_memory_injection_renderer.py:174-193` and `:291-296` show name truncation without a warning
    - `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:539-550` only exercises Rule 9 body truncation

- **Exact `max_chars` boundary is correct but untested at the middleware layer** — **p2**
  - **Edge case:** Rule 7 uses `len(full_message) <= max_chars` (`renderer.py:326`), so a result that is exactly `max_chars` with full content has no warning and the counter does not fire — which is correct. Rule 9 checks `len(result) > max_chars` (`renderer.py:344`) and then returns a result that is at most `max_chars`, so a Rule-9 result that lands exactly on `max_chars` still contains `_MEMORY_WARNING` and the counter fires. However, the middleware tests only use very short ("Short fact.") and very long (`"W" * 20_000`) inputs; they do not exercise the 7,999/8,000/8,001 boundary.
  - **Evidence:**
    - `nowing_backend/app/services/memory/renderer.py:325-327` (Rule 7, `<= max_chars`)
    - `nowing_backend/app/services/memory/renderer.py:341-345` (Rule 9, `> max_chars` guard)
    - `nowing_backend/tests/unit/services/test_bounded_memory_injection_renderer.py:263-281` (renderer boundary tests)
    - `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:538-565` (no boundary cases)

- **User-controlled content cannot currently trigger a false counter, but the defense is single-layer** — **p2**
  - **Edge case:** A user cannot inject the literal `_MEMORY_WARNING` string into the rendered output because both `display_name` (`renderer.py:167-173`) and memory `content` lines (`renderer.py:205-207`) are run through `html.escape(..., quote=True)`, which escapes `<` and `>`. The test `test_golden_team_escapes_malicious_close_tag` confirms this. But if a future change skips escaping or uses `quote=False`, the middleware's substring check (`_MEMORY_WARNING in rendered`) becomes exploitable for false positives and prompt injection. Note that `_TRUNCATION_MARKER` (`[...truncated...]`) is not escaped, but it is not used for detection in the middleware.
  - **Evidence:**
    - `nowing_backend/app/services/memory/renderer.py:22` (`_TRUNCATION_MARKER`)
    - `nowing_backend/app/services/memory/renderer.py:167-173` (name escaping)
    - `nowing_backend/app/services/memory/renderer.py:205-207` (content escaping)
    - `nowing_backend/app/services/memory/renderer.py:23-26` (`_MEMORY_WARNING`)
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:304` (`_MEMORY_WARNING in rendered`)
    - `nowing_backend/tests/unit/services/test_bounded_memory_injection_renderer.py:70-80` (escape regression test)

- **Truncation detection depends on a private, string-based marker instead of an explicit signal** — **p2**
  - **Edge case:** The middleware imports the private `_MEMORY_WARNING` constant from the renderer and uses a substring check to infer that truncation happened. This couples the two modules to the exact warning text and its location. If the renderer changes the warning text, rephrases it, or moves it, the counter will silently false-negative. A cleaner contract would be a return flag or a small dataclass from the renderer.
  - **Evidence:**
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:41-42` (imports private `_MEMORY_WARNING`)
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:304` (`if _MEMORY_WARNING in rendered`)
    - `nowing_backend/app/services/memory/renderer.py:23-26` (definition of `_MEMORY_WARNING`)

- **Middleware tests only cover user scope and avoid boundary/team cases** — **p2**
  - **Edge case:** Both new AC3 tests use the default `_mw()` helper, which sets `visibility=ChatVisibility.PRIVATE` (`test_memory_injection_middleware.py:153`) and therefore `scope="user"`. There is no test for `ChatVisibility.SEARCH_SPACE` (`scope="team"`) or for the exact `max_chars=8_000` boundary, so the counter could silently misbehave for team threads.
  - **Evidence:**
    - `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:150-157` (`_mw` defaults to private)
    - `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:538-565` (both new tests use the default private scope)
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:187-188` (team/user scope selection)

- **The "counter should NOT fire" test is shallow and does not cover name-truncation ambiguity** — **p2**
  - **Edge case:** A no-fire test exists for a short fact with a short name (`test_truncation_counter_not_emitted_when_no_truncation`), but it does not exercise the cases where the renderer truncates the display name (Rule 8 or the name-only path). Because the counter does not fire in those paths today, a test for them would currently pass but would be the only thing preventing a future regression if the intended behavior is to count all truncation events.
  - **Evidence:**
    - `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:553-565` (no-fire test)
    - `nowing_backend/app/services/memory/renderer.py:184-194` and `:329-339` (name-truncation paths with no `_MEMORY_WARNING`)

- **Counter instrument is created before the `is_enabled()` check, but no crash occurs before OTel init** — **p2**
  - **Edge case:** `record_memory_injection_truncated` passes `_memory_injection_truncated()` as an argument to `_add`, so the counter is created before `_add`'s `if not _is_enabled(): return` check (`metrics.py:105`). In practice this is safe because `opentelemetry.metrics.get_meter` returns a proxy/no-op meter when no provider is configured, so `create_counter` and `add` do not crash. The instrument is still created on the request path even when telemetry is disabled.
  - **Evidence:**
    - `nowing_backend/app/observability/metrics.py:104-108` (`_add` checks `_is_enabled()` after the callable is evaluated)
    - `nowing_backend/app/observability/metrics.py:1035-1040` (`_memory_injection_truncated` calls `_get_meter().create_counter`)
    - `nowing_backend/app/observability/metrics.py:1050-1051` (`record_memory_injection_truncated` calls `_add(_memory_injection_truncated(), ...)`)
    - `nowing_backend/app/observability/otel.py:90-92` (`is_enabled()`)

- **Non-Exception `BaseException`s can leak through the metric helper's suppression** — **p2**
  - **Edge case:** Both `record_memory_injection_truncated` and `_add` use `contextlib.suppress(Exception)`. If the OpenTelemetry `create_counter` or `.add` call raises a `BaseException` subclass that is not an `Exception` (e.g., `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`), it will not be caught and can propagate out of `abefore_agent`. This follows the normal Python convention of not swallowing system-level exceptions, but it is the only gap in the "metrics must never crash the request" guarantee.
  - **Evidence:**
    - `nowing_backend/app/observability/metrics.py:104-108` (`_add` suppresses only `Exception`)
    - `nowing_backend/app/observability/metrics.py:1050` (`record_memory_injection_truncated` suppresses only `Exception`)

- **A future renderer path that returns `None` after truncating would be missed** — **p2**
  - **Edge case:** The middleware checks `if rendered is None` and returns `None` before the `_MEMORY_WARNING` check. Today, `render_bounded_memory_injection` only returns `None` when there is nothing to inject, so it cannot contain the warning. If a future change adds a truncated path that returns `None` as a fallback, the middleware would not call `record_memory_injection_truncated`.
  - **Evidence:**
    - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:294-305` (ordering of `None` check and warning check)
    - `nowing_backend/app/services/memory/renderer.py:313-316` (current `None` return path has no body)
    - `nowing_backend/app/services/memory/renderer.py:341-346` (current truncation path returns a string)
