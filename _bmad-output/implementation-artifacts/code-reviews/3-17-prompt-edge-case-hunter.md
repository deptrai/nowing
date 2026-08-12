# Edge Case Hunter Prompt — Story 3.17

## Diff to Review

```diff
--- a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py
+++ b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py
@@ -33,8 +33,12 @@ from sqlalchemy.ext.asyncio import AsyncSession
 from app.agents.chat.shared.middleware.compaction import PROTECTED_SYSTEM_PREFIXES
 from app.config import config
 from app.db import ChatVisibility, shielded_async_session
-from app.observability.metrics import record_memory_injection_failure
+from app.observability.metrics import (
+    record_memory_injection_failure,
+    record_memory_injection_truncated,
+)
 from app.services.memory.renderer import (
+    _MEMORY_WARNING,
     MemoryRenderError,
     render_bounded_memory_injection,
 )
@@ -294,6 +298,12 @@ class MemoryInjectionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
                 )
             return None
 
+        # Story 3.17 AC3: emit truncation counter when the renderer had to
+        # truncate the memory body to fit within the char budget.  The
+        # warning marker is only embedded in the truncated output path.
+        if _MEMORY_WARNING in rendered:
+            record_memory_injection_truncated(scope=scope)
+
         if pending is not None:
             record_memory_injection_failure(
                 scope=scope, stage=pending[0], reason=pending[1]
--- a/nowing_backend/app/observability/metrics.py
+++ b/nowing_backend/app/observability/metrics.py
@@ -1032,6 +1032,25 @@ def record_memory_injection_failure(*, scope: str, stage: str, reason: str) -> N
         _add(_memory_injection_failures(), 1, attrs)
 
 
+@lru_cache(maxsize=1)
+def _memory_injection_truncated():
+    return _get_meter().create_counter(
+        "nowing.memory.injection.truncated",
+        description="Count of memory injection truncations by scope.",
+    )
+
+
+def record_memory_injection_truncated(*, scope: str) -> None:
+    """"Count one memory injection that was truncated to fit the char budget.
+
+    Story 3.17 AC3: emitted when ``render_bounded_memory_injection`` produces
+    output that was truncated to stay within ``max_chars``.
+    """
+    attrs = {"scope": scope}
+    with contextlib.suppress(Exception):
+        _add(_memory_injection_truncated(), 1, attrs)
+
+
 def _runtime_snapshot_value(key: str, transform: Any = None) -> list[Any]:
     from opentelemetry.metrics import Observation
 
@@ -1499,6 +1518,7 @@ __all__ = [
     "record_kb_fallback_hit_count",
     "record_kb_search_duration",
     "record_memory_injection_failure",
+    "record_memory_injection_truncated",
     "record_model_call_duration",
     "record_model_token_usage",
     "record_perf_elapsed",
--- a/nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py
+++ b/nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py
@@ -518,3 +520,46 @@ async def test_transcript_query_render_error_records_query_failure(monkeypatch)
     result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
     assert result is None
     assert failures == [{"scope": "user", "stage": "query", "reason": "render_error"}]
+
+
+# --- Story 3.17 AC3: truncation counter --------------------------------------
+
+
+def _install_truncation_recorder(monkeypatch) -> list[dict[str, str]]:
+    calls: list[dict[str, str]] = []
+
+    def _fake_record(*, scope: str) -> None:
+        calls.append({"scope": scope})
+
+    monkeypatch.setattr(mw_module, "record_memory_injection_truncated", _fake_record)
+    return calls
+
+
+@pytest.mark.asyncio
+async def test_truncation_counter_emitted_when_memory_overflows(monkeypatch) -> None:
+    """AC3: memory_injection_truncated counter fires when the renderer truncates."""
+    _install_embedding(monkeypatch)
+    session = _FakeSession(display_name="Ada")
+    _install_session(monkeypatch, session)
+    _install_search(monkeypatch, hits=[_hit("W" * 20_000)])
+    _install_failure_recorder(monkeypatch)
+    truncations = _install_truncation_recorder(monkeypatch)
+    mw = _mw()
+    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
+    assert result is not None
+    assert truncations == [{"scope": "user"}]
+
+
+@pytest.mark.asyncio
+async def test_truncation_counter_not_emitted_when_no_truncation(monkeypatch) -> None:
+    """AC3: counter stays at zero when the rendered output fits without truncation."""
+    _install_embedding(monkeypatch)
+    session = _FakeSession(display_name="Ada")
+    _install_session(monkeypatch, session)
+    _install_search(monkeypatch, hits=[_hit("Short fact.")])
+    _install_failure_recorder(monkeypatch)
+    truncations = _install_truncation_recorder(monkeypatch)
+    mw = _mw()
+    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
+    assert result is not None
+    assert truncations == []
```

## Context

Story: Memory Injection Bounded-Retrieval Performance Gate (3.17)
- Adds `record_memory_injection_truncated` metric and emits it from `MemoryInjectionMiddleware` when memory injection output is truncated.
- Counter uses `lru_cache` instrument creation, `contextlib.suppress(Exception)` to prevent metric emission from crashing the request path.
- Middleware detects truncation by checking for `_MEMORY_WARNING` marker in rendered output.

## Task

You are an Edge Case Hunter. Focus on edge cases, boundary conditions, and unusual paths:
- What if the warning marker appears in user-controlled memory content? (XSS / injection)
- What if `rendered` is exactly `max_chars`? Does the warning still appear?
- What if name truncation happens (Rule 8) vs memory truncation (Rule 9)?
- What if the metric helper is called before OTel is initialized?
- What if `_add` raises a non-Exception subclass?
- What if the renderer returns None after a truncation warning path?
- Are tests covering both user and team scope?
- Are tests covering the case where truncation counter should NOT fire?

Output findings as a Markdown list. Each finding: one-line title, the edge case, evidence (file + line), and severity (p0/p1/p2).
