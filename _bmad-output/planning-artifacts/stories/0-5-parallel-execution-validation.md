---
storyId: 0.5
storyTitle: Parallel Execution Validation
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.1, 0.2, 0.3, 0.4 DONE]
blocks: [Story 0.6, Epic 9 Phase 1]
relatedFRs: [FR-T2, FR33 Parallel Orchestration]
relatedNFRs: [NFR-CS2 Parallel Execution, NFR-Q2 Parallelism Ratio, NFR-Q4 Speed]
priority: P0 (BLOCKING Phase 1)
estimatedEffort: 2-3 days
status: done
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 8.2: Parallel Execution Validation

## User Story

**As a** developer,
**I want** to verify multiple sub-agents run truly in parallel inside a single LangGraph ToolNode step,
**So that** full crypto analysis doesn't take N times longer than a single agent — proving parallelism ratio gate (NFR-Q2 < 1.3x) và speed gate (NFR-Q4 < 90s P95).

---

## Context

Story 8.1 validate **tools** trả data đúng. Story 8.2 validate **orchestration** — main agent có thực sự spawn parallel hay vô tình tuần tự.

**Critical insight**: LangGraph ToolNode chỉ batch parallel khi LLM emit MULTIPLE `task()` calls trong CÙNG 1 response. Nếu main agent emit 1 call → wait → emit call khác → wait, đó là tuần tự (anti-pattern).

**Quality Gate gate-keeper**: NFR-Q2 (parallelism ratio < 1.3x) là 1 trong 4 quality gates Phase 1 — fail → no Phase 2 launch.

---

## Prerequisites

### Pre-flight Checklist

- [ ] **Epic 0 DONE**: 4 base sub-agents (defillama, sentiment, news, smart_contract) wired vào SubAgentMiddleware
- [ ] **Epic 0 Story 0.3 DONE**: main agent system prompt có crypto orchestration section với Rule C (parallel)
- [ ] **Story 8.1 DONE**: 11 tools verified responsive (no 429/timeout cascading)
- [ ] LangGraph trace logging enabled (cần `langsmith` env vars hoặc local trace export)

**Nếu BẤT KỲ item nào FAIL** → không start Story 8.2.

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/tests/integration/agents/test_parallel_execution.py`

Integration test verify orchestration behavior với real agent spawn.

```python
"""Integration tests for parallel sub-agent execution.

Validates NFR-CS2 (LangGraph ToolNode parallel batch) và NFR-Q2 (parallelism ratio < 1.3x).
"""
import pytest
import time
from typing import Any

pytestmark = pytest.mark.integration


class TestParallelOrchestration:
    """Validate main agent spawns sub-agents in parallel batch."""

    async def test_comprehensive_query_triggers_parallel_spawn(self, agent_factory):
        """AC1: Comprehensive analysis triggers parallel spawn of 4 base agents."""
        agent = await agent_factory(user_id="test", search_space_id="test-ws")

        # Trace context
        trace_events = []
        # Hook into LangGraph callbacks to capture agent spawn events
        # ... (use langchain.callbacks or langsmith)

        start = time.perf_counter()
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]
        })
        elapsed = time.perf_counter() - start

        # Extract per-agent timings từ trace
        agent_timings = parse_agent_timings_from_trace(trace_events)
        # Expect 4 agents spawned
        assert len(agent_timings) >= 4, f"Expected 4+ agents, got {len(agent_timings)}"
        assert {"defillama_analyst", "sentiment_analyst", "news_analyst", "smart_contract_analyst"}.issubset(
            set(t["agent_name"] for t in agent_timings)
        )

        # AC2: All 4 agents start trong cùng 1 ToolNode step
        step_ids = set(t["graph_step_id"] for t in agent_timings)
        assert len(step_ids) == 1, f"Agents spawned in multiple steps (sequential!): {step_ids}"

        # AC3: Parallelism ratio < 1.3x
        max_individual = max(t["duration_sec"] for t in agent_timings)
        ratio = elapsed / max_individual
        assert ratio < 1.3, f"Parallelism ratio {ratio:.2f}x exceeds 1.3x — agents may be sequential"


class TestParallelismRatioBenchmark:
    """Statistical benchmark — 100 query sample for production-realistic metric."""

    @pytest.mark.slow  # only run nightly
    async def test_parallelism_ratio_p95_under_threshold(self, agent_factory, query_sample_100):
        """AC4: 100 sample queries → ratio P95 < 1.3x"""
        ratios = []
        for query in query_sample_100:
            agent = await agent_factory(user_id="test", search_space_id="test-ws")
            start = time.perf_counter()
            result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
            elapsed = time.perf_counter() - start

            timings = parse_agent_timings_from_trace(...)
            if len(timings) < 2:
                continue  # skip queries that don't trigger parallel spawn (Rule A)
            max_individual = max(t["duration_sec"] for t in timings)
            ratios.append(elapsed / max_individual)

        # P95 calculation
        import statistics
        ratios_sorted = sorted(ratios)
        p95_idx = int(len(ratios_sorted) * 0.95)
        p95 = ratios_sorted[p95_idx]

        assert p95 < 1.3, f"P95 parallelism ratio {p95:.2f}x exceeds 1.3x gate"


class TestSpeedGate:
    """NFR-Q4: P95 full-suite response time < 90s."""

    @pytest.mark.slow
    async def test_p95_response_time_under_90s(self, agent_factory, query_sample_100):
        """AC5: 100 full-suite queries → P95 < 90s end-to-end"""
        durations = []
        for query in query_sample_100:
            agent = await agent_factory(user_id="test", search_space_id="test-ws")
            start = time.perf_counter()
            await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
            durations.append(time.perf_counter() - start)

        durations_sorted = sorted(durations)
        p95 = durations_sorted[int(len(durations_sorted) * 0.95)]
        assert p95 < 90.0, f"P95 response time {p95:.1f}s exceeds 90s gate"
```

#### 2. `nowing_backend/tests/integration/agents/conftest.py`

Helpers cho trace parsing và sample query loading.

```python
import pytest
from typing import Any

@pytest.fixture
def query_sample_100() -> list[str]:
    """100 representative queries cho benchmark — mix Rule A/B/C/D theo Story 0.3."""
    return [
        # Rule C — Comprehensive (40 queries trong sample)
        "Phân tích toàn diện $UNI cho long position",
        "Comprehensive analysis of Aave",
        # ... (98 queries khác)
    ]


@pytest.fixture
async def agent_factory():
    """Factory tạo fresh agent instance cho mỗi test."""
    from app.agents.new_chat.chat_deepagent import create_deepagent
    async def _create(user_id: str, search_space_id: str):
        return await create_deepagent(
            user_id=user_id,
            search_space_id=search_space_id,
            # ... other required params
        )
    return _create


def parse_agent_timings_from_trace(trace_events: list[dict]) -> list[dict]:
    """Extract per-agent timing data từ LangGraph trace events."""
    timings = []
    for event in trace_events:
        if event.get("event") == "on_tool_start" and event.get("name") == "task":
            agent_name = event["data"]["input"].get("agent")
            step_id = event.get("metadata", {}).get("langgraph_step")
            timings.append({
                "agent_name": agent_name,
                "graph_step_id": step_id,
                "start_time": event["timestamp"],
            })
        elif event.get("event") == "on_tool_end" and event.get("name") == "task":
            # Match end với start để tính duration
            ...
    return timings
```

### 📝 Files to Modify

#### 1. `nowing_backend/app/agents/new_chat/chat_deepagent.py`

Add **telemetry middleware** capture parallel execution metrics:

```python
# Add custom middleware tracking task() spawn timing
class ParallelismTelemetryMiddleware(...):
    """Log parallelism ratio + per-agent timing for monitoring."""

    async def on_tool_call(self, tool_call):
        if tool_call.name == "task":
            # Record start time + step_id
            ...

    async def on_step_end(self, state):
        # If multiple task() calls in this step → calculate parallelism ratio
        # Emit metric: parallelism_ratio = step_duration / max(agent_duration)
        # Log to structured logger với fields: query_id, ratio, agents_spawned
        ...
```

#### 2. Telemetry sink config

`nowing_backend/app/observability/metrics.py` (hoặc Prometheus/Datadog client) — register 2 new metrics:
- `crypto_orchestra_parallelism_ratio` (histogram)
- `crypto_orchestra_full_suite_duration_seconds` (histogram, label: `agents_count`)

---

## Acceptance Criteria

### AC1: Comprehensive query triggers 4-agent spawn

**Given** main agent nhận câu "Phân tích toàn diện $UNI"
**When** main agent xử lý request
**Then** trace logs show 4 `task()` tool calls được emit trong CÙNG 1 LLM response
**And** 4 agent names được spawn: `defillama_analyst`, `sentiment_analyst`, `news_analyst`, `smart_contract_analyst`

### AC2: All agents start in single LangGraph step

**Given** 4 agents được spawn (AC1 trigger)
**When** inspect trace events theo `langgraph_step` metadata
**Then** tất cả 4 spawn events có cùng `step_id`
**And** không có agent nào spawn ở step sau (proof of parallel batch, not sequential)

### AC3: Single-query parallelism ratio < 1.3x

**Given** 1 comprehensive query với 4 agents spawned
**When** đo `total_elapsed_time` (end-to-end) và `max(individual_agent_duration)`
**Then** ratio = `total_elapsed / max_individual` **< 1.3x**
**And** result được log với context fields cho debugging

### AC4: P95 parallelism ratio gate (NFR-Q2)

**Given** 100 sample queries (mix Rule A/B/C/D), filter ra ~40 queries triggering parallel spawn
**When** tính ratio cho mỗi parallel-spawn query
**Then** **P95 ratio < 1.3x**
**And** test report show distribution: P50, P75, P95, max
**And** nếu fail → output identify specific queries có ratio cao nhất để debug

### AC5: P95 speed gate (NFR-Q4)

**Given** 100 sample queries (full mix)
**When** đo end-to-end response time cho mỗi query
**Then** **P95 < 90 giây**
**And** breakdown theo agent count: queries với 1 agent (Rule B), 2 agents (Rule D), 4+ agents (Rule C)

### AC6: Result aggregation completeness

**Given** 4 agents spawned parallel
**When** main agent compose final response
**Then** response chứa structured insights từ TẤT CẢ 4 agents (không bỏ sót agent nào)
**And** response không có duplicate sections (mỗi agent contribute distinct angle)

### AC7: Telemetry dashboard live

**Given** parallelism telemetry middleware deployed
**When** production traffic flowing
**Then** dashboard hiển thị 2 metrics realtime:
1. `parallelism_ratio` distribution (histogram with P50/P95/P99 lines)
2. `full_suite_duration_seconds` distribution (similar)
**And** alerts cấu hình: P95 ratio > 1.3x trong 1h → warn ops team

### AC8: Sequential anti-pattern detection

**Given** trace event stream
**When** detect 2 `task()` calls trong khác step (sequential!)
**Then** log warning với metadata "potential_sequential_spawn" + query content
**And** structured log có thể query để find regression

---

## Definition of Done (8 checkpoints)

- [ ] **DoD-1** Pre-flight: Epic 0 + Story 8.1 DONE
- [ ] **DoD-2** Test files created (`test_parallel_execution.py` + `conftest.py`)
- [ ] **DoD-3** `query_sample_100` fixture có 100 representative queries (40 Rule C, 30 Rule A/B, 30 Rule D)
- [ ] **DoD-4** `ParallelismTelemetryMiddleware` implemented và wired trong `chat_deepagent.py`
- [ ] **DoD-5** AC1-AC3 (single query) tests pass trên local dev
- [ ] **DoD-6** AC4-AC5 (P95 benchmark) tests run thành công, kết quả meet thresholds
- [ ] **DoD-7** Telemetry dashboard config (Grafana panel hoặc equivalent) deployed
- [ ] **DoD-8** Documentation: how to interpret parallelism ratio, what to do nếu fail

---

## Dev Notes

### Testing Commands

```bash
cd nowing_backend

# Single-query tests (fast, real APIs)
uv run pytest -m integration tests/integration/agents/test_parallel_execution.py::TestParallelOrchestration -v

# Full P95 benchmark (slow — 100 queries x ~30s avg = ~50 min)
uv run pytest -m "integration and slow" tests/integration/agents/test_parallel_execution.py -v

# Local trace inspection (without running tests)
uv run python -c "
from app.agents.new_chat.chat_deepagent import create_deepagent
import asyncio, time

async def main():
    agent = await create_deepagent(user_id='test', search_space_id='test', ...)
    start = time.perf_counter()
    result = await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Phân tích toàn diện UNI'}]})
    print(f'Total elapsed: {time.perf_counter() - start:.1f}s')
    print(f'Agents spawned: {result[\"metadata\"].get(\"agents_spawned\")}')

asyncio.run(main())
"
```

### Trace Data Sources

3 cách capture trace events (pick 1):

1. **LangSmith** (cloud) — set `LANGSMITH_TRACING=true` + API key. Pros: rich UI, auto-capture. Cons: external dependency.
2. **Local OpenTelemetry export** — config `OTEL_EXPORTER_OTLP_ENDPOINT`. Pros: self-hosted. Cons: setup complexity.
3. **Custom callback** — implement `BaseCallbackHandler` capture `on_tool_start`/`on_tool_end`. Pros: zero external. Cons: need to write code.

**Recommended for Story 8.2**: Option 3 (custom callback) — minimal dependency, fits CI well.

### Common Pitfalls

1. ❌ **Đừng** dùng `time.time()` cho timing — dùng `time.perf_counter()` (monotonic, ns precision)
2. ❌ **Đừng** assert chính xác duration (e.g., max 5s) — APIs vary, dùng ratio thay vì absolute
3. ⚠️ **LangGraph step metadata**: cần verify field name chính xác trong runtime — có thể là `langgraph_node`, `langgraph_step`, hoặc `step_id` tùy version
4. ⚠️ **Sample size**: 100 queries có thể tốn $5-10 token cost — budget cho benchmark
5. ⚠️ **Rate limit cascade**: 100 queries x 4 CoinGecko calls = 400 calls / ~2 min = vượt 30 req/min. Add delay giữa queries hoặc use cache fixture.

### Sample Query Distribution (cho `query_sample_100`)

| Rule | Type | Count | Examples |
|------|------|-------|----------|
| A | Direct tool (no spawn) | 30 | "Giá BTC?", "TVL Aave?", "F&G hôm nay?" |
| B | Single specialist | 20 | "Audit 0xabc...", "DeFi yields USDC", "News về Solana" |
| C | Comprehensive (4 agents) | 40 | "Phân tích toàn diện $UNI", "Đánh giá AAVE", "Comprehensive review of Curve" |
| D | Selective subset | 10 | "Token X có scam không?", "Yield + security cho USDT" |

### Reference Files

- **Wiring**: `nowing_backend/app/agents/new_chat/chat_deepagent.py:437-477`
- **Existing test pattern**: `nowing_backend/tests/integration/` (nếu có) — follow conventions
- **LangGraph docs** trên parallel execution: https://langchain-ai.github.io/langgraph/concepts/low_level/#parallel-execution

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR-T2 Test parallel execution | `epics.md` Epic 0 | AC1, AC2, AC3 |
| FR33 Parallel orchestration | `prd.md` | AC1, AC2 |
| NFR-CS2 Parallel execution (single graph step) | `prd.md` + `epics.md` | AC2, AC3 |
| NFR-Q2 Parallelism ratio < 1.3x | `prd.md` Quality Gates | AC3, AC4 |
| NFR-Q4 Speed P95 < 90s | `prd.md` Quality Gates | AC5 |

---

## Rollback Plan

Test code = zero production risk. Nếu telemetry middleware có bug → feature flag tắt: `PARALLELISM_TELEMETRY_ENABLED=false`.

---

**Status**: ready-for-dev ✅ (blocked on Story 8.1)
**Next**: Story 8.3 Error Handling & Fallback Validation.

---

## Review Findings (2026-04-24, bmad-code-review)

### decision-needed
- [ ] [Review][Decision] No gating for ~200+ real LLM calls in benchmark suites — `TestParallelismRatioBenchmark` + `TestSpeedGate` iterate 100 queries each, spawning up to 4 sub-agents = ~800 LLM calls + external HTTP per run. Options: (a) gate on `RUN_SLOW_LLM_BENCHMARK` env var, (b) VCR/record-replay, (c) mock LLM fixture. Need budget/CI-safety decision. [test_parallel_execution.py]
- [ ] [Review][Decision] AC-8 detection mechanic contradicts spec intent — spec requires "detect 2 task() calls trong khác step"; code detects "single task call per step" (will false-positive on legitimate Rule B queries). Middleware sees only current step, so cross-step detection needs session-level state OR reframe spec to "batch size < 2". Need intent clarification. [chat_deepagent.py:177-215]

### patch
- [ ] [Review][Patch] [CRITICAL] `ParallelismTelemetryMiddleware` uses non-existent contract; hooks never fire → AC8 unreachable — must subclass `AgentMiddleware` and implement `after_model` (or equivalent hook) instead of bare `__call__(state, config, next_middleware)` [chat_deepagent.py:177-215]
- [ ] [Review][Patch] [CRITICAL] `agent_factory` passes `llm=None` — `create_nowing_deep_agent` requires `BaseChatModel`; `create_summarization_middleware(llm, ...)` raises at build-time. Every integration test errors before parallelism can be measured. Fix: construct real ChatLiteLLM from env or lazy-create when `None`. [conftest.py:97-103]
- [ ] [Review][Patch] [MAJOR] `(state or {}).get(...)` and `(msg or {}).get(...)` raise `AttributeError` on Pydantic/dataclass state and `BaseMessage` instances — guard with `isinstance(state, dict)` / `isinstance(msg, dict)` [chat_deepagent.py:193,196,199]
- [ ] [Review][Patch] [MAJOR] `task_calls` loop can accumulate older assistant-message tool_calls before `break` — break on first assistant message encountered regardless of tool_calls length [chat_deepagent.py:192-205]
- [ ] [Review][Patch] [MAJOR] Module-level Prometheus `Histogram` registration raises `ValueError: Duplicated timeseries` on reimport; `try/except ImportError` does not catch this — wrap in `try/except ValueError` or use dedicated `CollectorRegistry()` [metrics.py:6-17]
- [ ] [Review][Patch] [MAJOR] `MagicMock()` for `connector_service` — any non-patched async method returns sync MagicMock and raises `TypeError: object MagicMock can't be used in 'await' expression` downstream. Use `AsyncMock(spec=ConnectorService)`. [conftest.py:91-93]
- [ ] [Review][Patch] [MAJOR] `_TaskSpawnCollector._pending` dict not thread-safe — concurrent LangChain callbacks from parallel tool executions can race, silently invalidating AC3/AC4/AC5 timings. Add `threading.Lock` around `_pending` mutations. [conftest.py:46,76]
- [ ] [Review][Patch] [MAJOR] AC2 tautology — `graph_step_id=None` is filtered out by `if t['graph_step_id'] is not None`, so `len(step_ids) <= 1` trivially passes. Assert non-None AND equal, and include count of None step_ids in failure diagnostics. [test_parallel_execution.py:107-112]
- [ ] [Review][Patch] [MAJOR] AC-7 histograms are defined but never `.observe()`d — dashboard would have no data even if deployed. Call `PARALLELISM_RATIO_HISTOGRAM.observe(ratio)` + `FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count=...).observe(elapsed)` from the telemetry middleware. [metrics.py + chat_deepagent.py]
- [ ] [Review][Patch] [MINOR] `agent_count == 0` falls into the `"1"` bucket; add explicit `elif agent_count == 1:` + separate `"0"` bucket [test_parallel_execution.py:549-555]
- [ ] [Review][Patch] [MINOR] P95 index uses `int(n*0.95)`, off-by-one for small n (effectively P90 for n=10); use `math.ceil(n*0.95) - 1` [test_parallel_execution.py:503]
- [ ] [Review][Patch] [MINOR] `parse_agent_timings_from_trace` filter is a no-op (every event already has `duration_sec`), making `dropped = spawned - completed` in AC-6 a tautology — also capture `on_tool_error` events so dropped-agent detection is real [conftest.py:79-83]
- [ ] [Review][Patch] [MINOR] AC-6 test only verifies agents completed; spec requires "response chứa structured insights từ TẤT CẢ 4 agents" — add assertion inspecting final assistant message content mentions each agent's angle [test_parallel_execution.py:87-108]
- [ ] [Review][Patch] [MINOR] DoD-3 fixture has 99 queries (30 A + 20 B + 39 C + 10 D) not 100 — add 1 Rule C query to restore count [conftest.py: rule_c list]

### defer
- [x] [Review][Defer] DoD-6 P95 benchmark not yet run on local dev — deferred, operational (needs API budget + ~50 min runtime; blocked by decision on benchmark gating)
- [x] [Review][Defer] DoD-7 Grafana/Datadog dashboard panel + P95 > 1.3x ratio alert — deferred, out-of-code infra artifact
- [x] [Review][Defer] DoD-8 Documentation on interpreting parallelism ratio and fallback-when-fail procedure — deferred, doc task
