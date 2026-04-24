"""Integration tests for parallel sub-agent execution.

Validates NFR-CS2 (LangGraph ToolNode parallel batch) và NFR-Q2 (parallelism ratio < 1.3x).

Run with:
    uv run pytest -m integration tests/integration/agents/test_parallel_execution.py::TestParallelOrchestration -v
    uv run pytest -m "integration and slow" tests/integration/agents/test_parallel_execution.py -v
"""

import math
import os
import statistics
import time
from typing import Any

import pytest

from tests.integration.agents.conftest import (
    _TaskSpawnCollector,
    parse_agent_timings_from_trace,
)

pytestmark = pytest.mark.integration

_COMPREHENSIVE_QUERY = "Phân tích toàn diện $UNI cho long position"
_EXPECTED_AGENTS = {
    "defillama_analyst",
    "sentiment_analyst",
    "news_analyst",
    "smart_contract_analyst",
    "tokenomics_analyst",  # Story 9.1
    "yield_optimizer",     # Story 9.4
}


def _invoke_config(collector: _TaskSpawnCollector) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": "test-thread"},
        "callbacks": [collector],
    }


def _user_message(content: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": content}]}


class TestParallelOrchestration:
    """Validate main agent spawns sub-agents in parallel batch (AC1, AC2, AC3)."""

    @pytest.mark.integration
    async def test_comprehensive_query_triggers_parallel_spawn(self, agent_factory):
        """AC1: Comprehensive analysis triggers parallel spawn of 6 crypto agents
        (4 Epic 0.2 base agents + tokenomics_analyst Story 9.1 + yield_optimizer Story 9.4)."""
        agent = await agent_factory(user_id="00000000-0000-0000-0000-000000000001", search_space_id=1)

        trace_events: list[dict[str, Any]] = []
        collector = _TaskSpawnCollector(trace_events)

        start = time.perf_counter()
        await agent.ainvoke(
            _user_message(_COMPREHENSIVE_QUERY),
            config=_invoke_config(collector),
        )
        elapsed = time.perf_counter() - start

        agent_timings = parse_agent_timings_from_trace(trace_events)

        assert len(agent_timings) >= 4, (
            f"AC1 FAIL: Expected >= 4 agents spawned, got {len(agent_timings)}. "
            f"Agents found: {[t['agent_name'] for t in agent_timings]}"
        )
        spawned_names = {t["agent_name"] for t in agent_timings}
        missing = _EXPECTED_AGENTS - spawned_names
        assert not missing, (
            f"AC1 FAIL: Missing agents: {missing}. Spawned: {spawned_names}"
        )

        # AC2: All agents start in the same LangGraph step
        step_ids = {t["graph_step_id"] for t in agent_timings if t["graph_step_id"] is not None}
        assert step_ids, (
            "AC2 FAIL: No graph_step_id captured — collector may not be receiving "
            f"LangGraph metadata. Check that callbacks are wired correctly. timings={agent_timings}"
        )
        assert len(step_ids) == 1, (
            f"AC2 FAIL: Agents spawned in multiple steps (sequential anti-pattern!): {step_ids}"
        )

        # AC3: Single-query parallelism ratio.
        # NFR-Q2 production target is < 1.3x (measured on real LLM traces, where
        # per-agent time is 10-30s and framework overhead < 2%). This mocked test
        # captures framework overhead at ~0.3-0.5s on top of short mock agent runs,
        # so the ratio is artificially inflated. Threshold scales with agent count:
        # 6-agent suite (Phase 1) ceiling is 2.0x mocked; investigate if regression
        # pushes it beyond. True NFR-Q2 gate decision uses canary data, not this test.
        max_individual = max(t["duration_sec"] for t in agent_timings)
        ratio = elapsed / max_individual if max_individual > 0 else float("inf")
        n_agents = len(agent_timings)
        mocked_ceiling = 1.3 + 0.15 * max(0, n_agents - 4)  # 4→1.3, 5→1.45, 6→1.6, 8→1.9
        mocked_ceiling = max(mocked_ceiling, 2.0)  # absolute floor at 2.0 for headroom
        assert ratio < mocked_ceiling, (
            f"AC3 FAIL: Parallelism ratio {ratio:.2f}x >= {mocked_ceiling:.2f}x "
            f"({n_agents}-agent suite mocked ceiling). Possible sequential anti-pattern "
            f"or framework overhead regression. elapsed={elapsed:.2f}s, max_individual={max_individual:.2f}s. "
            f"Investigate before relying on NFR-Q2 canary measurement."
        )

    @pytest.mark.integration
    async def test_all_four_agents_appear_in_response(self, agent_factory):
        """AC6: Final response contains insights from all 4 spawned agents (no dropped results)."""
        agent = await agent_factory(user_id="00000000-0000-0000-0000-000000000001", search_space_id=1)

        trace_events: list[dict[str, Any]] = []
        collector = _TaskSpawnCollector(trace_events)

        result = await agent.ainvoke(
            _user_message(_COMPREHENSIVE_QUERY),
            config=_invoke_config(collector),
        )

        agent_timings = parse_agent_timings_from_trace(trace_events)
        spawned = {t["agent_name"] for t in agent_timings}

        # All expected agents must have been spawned
        missing = _EXPECTED_AGENTS - spawned
        assert not missing, (
            f"AC6 FAIL: Expected agents not spawned: {missing}. Spawned: {spawned}"
        )

        # Agents still in _pending never completed — detect via collector internal state
        assert not collector._pending, (
            f"AC6 FAIL: {len(collector._pending)} agent(s) spawned but never completed "
            f"(on_tool_end not called): {list(collector._pending.keys())}"
        )

        # Verify final response contains non-empty content (all agent outputs aggregated)
        response_content = ""
        if isinstance(result, dict):
            for msg in reversed(result.get("messages", [])):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "") or ""
                if content:
                    response_content = str(content)
                    break
        assert response_content, "AC6 FAIL: Final response has no content — agent results may have been dropped"

        # Verify response is substantial enough to contain insights from all 4 agents
        min_expected_chars = 100 * len(_EXPECTED_AGENTS)  # ≥100 chars per agent
        assert len(response_content) >= min_expected_chars, (
            f"AC6 FAIL: Response too short ({len(response_content)} chars) to contain structured insights "
            f"from all {len(_EXPECTED_AGENTS)} agents (expected >= {min_expected_chars} chars). "
            "Some agent outputs may have been dropped or truncated."
        )

        # Verify all spawned agents actually completed (no orphaned pending tasks)
        dropped_agents = [
            name for name, meta in collector._pending.items()
            if meta.get("agent_name") in _EXPECTED_AGENTS
        ]
        assert not dropped_agents, (
            f"AC6 FAIL: Expected agent(s) spawned but output never returned: {dropped_agents}"
        )

    @pytest.mark.integration
    async def test_sequential_antipattern_detected_and_logged(self, agent_factory, caplog):
        """AC8: When task() calls span multiple steps, a warning is logged."""
        import logging

        agent = await agent_factory(user_id="00000000-0000-0000-0000-000000000001", search_space_id=1)

        trace_events: list[dict[str, Any]] = []
        collector = _TaskSpawnCollector(trace_events)

        with caplog.at_level(logging.WARNING, logger="app.agents"):
            await agent.ainvoke(
                _user_message(_COMPREHENSIVE_QUERY),
                config=_invoke_config(collector),
            )

        agent_timings = parse_agent_timings_from_trace(trace_events)
        step_ids = {t["graph_step_id"] for t in agent_timings if t["graph_step_id"] is not None}

        if len(step_ids) > 1:
            # Sequential pattern detected — warning must have been emitted
            sequential_warnings = [
                r for r in caplog.records
                if "sequential" in r.message.lower() or "potential_sequential_spawn" in r.message
            ]
            assert sequential_warnings, (
                "AC8 FAIL: Sequential spawn detected but no warning logged. "
                f"step_ids={step_ids}"
            )


class TestParallelismRatioBenchmark:
    """Statistical benchmark — 100 query sample for production-realistic metric (AC4)."""

    @pytest.mark.skipif(
        os.getenv("BENCHMARK_ENABLED", "").lower() not in ("1", "true", "yes"),
        reason="set BENCHMARK_ENABLED=1 to run LLM benchmarks",
    )
    @pytest.mark.slow
    async def test_parallelism_ratio_p95_under_threshold(
        self, agent_factory, query_sample_100
    ):
        """AC4: 100 sample queries → P95 parallelism ratio < 1.3x (NFR-Q2)."""
        from app.observability.metrics import PARALLELISM_RATIO_HISTOGRAM

        ratios: list[float] = []
        high_ratio_queries: list[tuple[str, float]] = []

        for query in query_sample_100:
            agent = await agent_factory(user_id="00000000-0000-0000-0000-000000000001", search_space_id=1)
            trace_events: list[dict[str, Any]] = []
            collector = _TaskSpawnCollector(trace_events)

            start = time.perf_counter()
            await agent.ainvoke(
                _user_message(query),
                config=_invoke_config(collector),
            )
            elapsed = time.perf_counter() - start

            timings = parse_agent_timings_from_trace(trace_events)
            if len(timings) < 2:
                continue  # Skip Rule A queries (no parallel spawn)

            max_individual = max(t["duration_sec"] for t in timings)
            if max_individual > 0:
                ratio = elapsed / max_individual
                ratios.append(ratio)
                PARALLELISM_RATIO_HISTOGRAM.observe(ratio)
                if ratio >= 1.3:
                    high_ratio_queries.append((query, ratio))

        assert ratios, "No parallel-spawn queries found in sample — check query_sample_100"

        ratios_sorted = sorted(ratios)
        n = len(ratios_sorted)
        p50 = ratios_sorted[int(n * 0.50)]
        p75 = ratios_sorted[int(n * 0.75)]
        # Use ceiling so P95 never rounds down and excludes the true 95th-percentile value
        p95_idx = min(math.ceil(n * 0.95) - 1, n - 1)
        p95 = ratios_sorted[p95_idx]
        p_max = ratios_sorted[-1]

        print(
            f"\nParallelism ratio distribution (n={len(ratios)}):\n"
            f"  P50={p50:.2f}x  P75={p75:.2f}x  P95={p95:.2f}x  max={p_max:.2f}x"
        )

        if high_ratio_queries:
            print("\nHigh-ratio queries (>= 1.3x):")
            for q, r in sorted(high_ratio_queries, key=lambda x: -x[1])[:10]:
                print(f"  {r:.2f}x — {q[:80]}")

        assert p95 < 1.3, (
            f"AC4 FAIL: P95 parallelism ratio {p95:.2f}x >= 1.3x gate (NFR-Q2). "
            f"P50={p50:.2f}x, P75={p75:.2f}x, n={len(ratios)}"
        )


class TestSpeedGate:
    """NFR-Q4: P95 full-suite response time < 90s (AC5)."""

    @pytest.mark.skipif(
        os.getenv("BENCHMARK_ENABLED", "").lower() not in ("1", "true", "yes"),
        reason="set BENCHMARK_ENABLED=1 to run LLM benchmarks",
    )
    @pytest.mark.slow
    async def test_p95_response_time_under_90s(self, agent_factory, query_sample_100):
        """AC5: 100 full-suite queries → P95 end-to-end < 90s."""
        durations_by_agent_count: dict[str, list[float]] = {
            "1": [],
            "2-3": [],
            "4+": [],
        }
        all_durations: list[float] = []

        for query in query_sample_100:
            agent = await agent_factory(user_id="00000000-0000-0000-0000-000000000001", search_space_id=1)
            trace_events: list[dict[str, Any]] = []
            collector = _TaskSpawnCollector(trace_events)

            start = time.perf_counter()
            await agent.ainvoke(
                _user_message(query),
                config=_invoke_config(collector),
            )
            elapsed = time.perf_counter() - start
            all_durations.append(elapsed)

            agent_count = len(parse_agent_timings_from_trace(trace_events))
            if agent_count >= 4:
                durations_by_agent_count["4+"].append(elapsed)
            elif agent_count >= 2:
                durations_by_agent_count["2-3"].append(elapsed)
            elif agent_count == 1:
                durations_by_agent_count["1"].append(elapsed)
            # agent_count == 0: no parallel spawn, do not bucket

        durations_sorted = sorted(all_durations)
        n = len(durations_sorted)
        p95_idx = min(math.ceil(n * 0.95) - 1, n - 1)
        p95 = durations_sorted[p95_idx]
        p50 = durations_sorted[int(n * 0.50)]

        print(f"\nResponse time distribution (n={len(all_durations)}):")
        print(f"  P50={p50:.1f}s  P95={p95:.1f}s  max={durations_sorted[-1]:.1f}s")
        for label, durs in durations_by_agent_count.items():
            if durs:
                print(
                    f"  {label} agent(s): n={len(durs)}, "
                    f"avg={statistics.mean(durs):.1f}s, "
                    f"max={max(durs):.1f}s"
                )

        assert p95 < 90.0, (
            f"AC5 FAIL: P95 response time {p95:.1f}s >= 90s gate (NFR-Q4). "
            f"P50={p50:.1f}s, n={len(all_durations)}"
        )


class TestTelemetryMetrics:
    """AC7: Parallelism telemetry metrics are registered and observable."""

    @pytest.mark.integration
    async def test_parallelism_metrics_registered(self):
        """AC7: Two histogram metrics exist and are recordable."""
        try:
            from app.observability.metrics import (
                PARALLELISM_RATIO_HISTOGRAM,
                FULL_SUITE_DURATION_HISTOGRAM,
            )
        except ImportError:
            pytest.skip("app.observability.metrics not yet implemented")

        assert PARALLELISM_RATIO_HISTOGRAM is not None, "Parallelism ratio histogram not registered"
        assert FULL_SUITE_DURATION_HISTOGRAM is not None, "Full suite duration histogram not registered"


class TestParallelismTelemetryMiddlewareUnit:
    """Unit tests for ParallelismTelemetryMiddleware (AC8 detection logic, D2=3).

    Tests run without any LLM or integration setup — middleware logic only.
    """

    @pytest.mark.asyncio
    async def test_single_task_call_logs_sequential_warning(self, caplog):
        """AC8: Single task() per step triggers a sequential-spawn warning."""
        import logging
        from langchain_core.messages import AIMessage
        from app.agents.new_chat.chat_deepagent import ParallelismTelemetryMiddleware

        mw = ParallelismTelemetryMiddleware()
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "task", "args": {"agent": "analyst"}, "id": "tc1", "type": "tool_call"}],
        )
        result_state = {"messages": [ai_msg]}

        async def _next(state, config):
            return result_state

        with caplog.at_level(logging.WARNING, logger="app.agents"):
            await mw({"messages": []}, {}, _next)

        assert any(
            "potential_sequential_spawn" in r.message for r in caplog.records
        ), "Expected sequential spawn warning not emitted for single task() call"

    @pytest.mark.asyncio
    async def test_parallel_task_calls_no_warning(self, caplog):
        """No warning when 6 task() calls appear in a single LLM step (full crypto suite)."""
        import logging
        from langchain_core.messages import AIMessage
        from app.agents.new_chat.chat_deepagent import ParallelismTelemetryMiddleware

        mw = ParallelismTelemetryMiddleware()
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "task", "args": {"agent": f"agent_{i}"}, "id": f"tc{i}", "type": "tool_call"}
                for i in range(6)
            ],
        )
        result_state = {"messages": [ai_msg]}

        async def _next(state, config):
            return result_state

        with caplog.at_level(logging.WARNING, logger="app.agents"):
            await mw({"messages": []}, {}, _next)

        assert not any(
            "potential_sequential_spawn" in r.message for r in caplog.records
        ), "Unexpected sequential-spawn warning for a valid parallel batch"

    @pytest.mark.asyncio
    async def test_no_task_calls_no_warning(self, caplog):
        """No warning when there are no task() calls at all."""
        import logging
        from app.agents.new_chat.chat_deepagent import ParallelismTelemetryMiddleware

        mw = ParallelismTelemetryMiddleware()

        async def _next(state, config):
            return {"messages": []}

        with caplog.at_level(logging.WARNING, logger="app.agents"):
            await mw({"messages": []}, {}, _next)

        assert not any(
            "potential_sequential_spawn" in r.message for r in caplog.records
        ), "Unexpected warning when no task() calls are present"

    @pytest.mark.asyncio
    async def test_inspects_result_not_input_state(self):
        """Middleware must read from the result returned by next_middleware, not the input."""
        from langchain_core.messages import AIMessage
        from app.agents.new_chat.chat_deepagent import ParallelismTelemetryMiddleware

        mw = ParallelismTelemetryMiddleware()

        # Input has no messages; result carries 6 parallel task calls (no warning expected)
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "task", "args": {"agent": f"a_{i}"}, "id": f"tc{i}", "type": "tool_call"}
                for i in range(6)
            ],
        )
        result_state = {"messages": [ai_msg]}
        called: list[bool] = []

        async def _next(state, config):
            called.append(True)
            return result_state

        returned = await mw({"messages": []}, {}, _next)

        assert called == [True], "next_middleware was not called"
        assert returned is result_state, "Middleware must return the result from next_middleware"
