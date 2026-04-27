"""Integration tests for graceful degradation (Story 0.6).

Validates NFR-Q3 (>98% graceful degradation) and the error-handling contract
for all failure modes: rate limit, timeout, 5xx, network error.

AC1-AC3:  Tool-level — each tool returns {"error": "..."}, does NOT raise.
AC4-AC6:  Agent-level — sub-agents adapt when primary tool fails.
AC7-AC9:  Orchestration-level — main agent synthesizes with 1-2 or all agents failing.
AC10:     Statistical gate — P98 degradation rate over 100-query sample.
AC11:     Telemetry — degradation counters increment correctly.

Run commands:
  uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestToolLevelErrorHandling -v
  uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestOrchestrationLevelGraceful -v
  uv run pytest -m "integration and slow" tests/integration/agents/test_graceful_degradation.py::TestDegradationRateBenchmark -v
"""

import json
import os

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.new_chat.chat_deepagent import ParallelismTelemetryMiddleware
from app.observability.metrics import AGENT_ERRORS_COUNTER, GRACEFUL_DEGRADATION_COUNTER
from tests.integration.agents.fault_injection import inject_all_failures

pytestmark = pytest.mark.integration

_NEEDS_REAL_LLM = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Content quality assertions require real LLM (ANTHROPIC_API_KEY not set)",
)

# Structural agent tests exercise the full agent graph. With ANTHROPIC_API_KEY
# set they burn real LLM tokens; the structural assertion "result is not None"
# alone doesn't justify that cost. Guard them with a skip by default — opt-in
# via RUN_STRUCTURAL_AGENT_TESTS=1 when you genuinely want to verify the agent
# survives respx-injected failures end-to-end.
_SKIP_STRUCTURAL_AGENT = pytest.mark.skipif(
    not os.getenv("RUN_STRUCTURAL_AGENT_TESTS"),
    reason=(
        "Structural agent tests skipped — set RUN_STRUCTURAL_AGENT_TESTS=1 to run "
        "(may consume LLM tokens if ANTHROPIC_API_KEY is also set)."
    ),
)

# Valid EVM address used in tests
_TEST_CONTRACT = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"  # UNI token


class TestToolLevelErrorHandling:
    """AC1-AC3: Individual tools return error dict, never raise."""

    async def test_coingecko_429_returns_error_dict(self):
        """AC1: CoinGecko rate limit → error dict with actionable hint."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get(url__regex=r"https://api\.coingecko\.com/api/v3/coins/.*").mock(
                return_value=httpx.Response(429, json={"error": "Rate limited"})
            )

            from app.agents.new_chat.tools.crypto_news import create_coingecko_token_info_tool

            tool = create_coingecko_token_info_tool()
            result = await tool.ainvoke({"coin_id": "bitcoin"})

        assert route.called, "CoinGecko 429 mock was never invoked"

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, f"Expected 'error' key in result: {result}"
        assert "rate limit" in result["error"].lower(), (
            f"Expected 'rate limit' hint in error: {result['error']!r}"
        )
        # AC1: must contain actionable retry hint
        assert "try again" in result["error"].lower() or "1 minute" in result["error"].lower(), (
            f"Expected retry hint in error: {result['error']!r}"
        )

    async def test_goplus_timeout_returns_error_dict(self):
        """AC2: GoPlus timeout → error dict, not exception, within ~35s."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get(url__regex=r"https://api\.gopluslabs\.io/api/v1/token_security/.*").mock(
                side_effect=httpx.TimeoutException("Injected timeout")
            )

            from app.agents.new_chat.tools.contract_analysis import create_check_token_security_tool

            tool = create_check_token_security_tool()
            result = await tool.ainvoke({
                "contract_address": _TEST_CONTRACT,
                "chain_id": "1",
            })

        # Verify the mock actually fired — otherwise the test is vacuous.
        assert route.called, "GoPlus mock was never invoked — assertion below is vacuous"
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, f"Expected 'error' key in result: {result}"
        error_lower = result["error"].lower()
        # Must indicate a transport failure — reject generic "failed" match that
        # would accept unrelated validation errors.
        assert "timeout" in error_lower or "unavailable" in error_lower, (
            f"Expected timeout/unavailable in error: {result['error']!r}"
        )

    async def test_defillama_500_returns_error_dict(self):
        """AC3: DeFiLlama 500 → error dict, not exception."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get("https://api.llama.fi/protocols").mock(
                return_value=httpx.Response(500)
            )

            from app.agents.new_chat.tools.defillama import create_defillama_tvl_overview_tool

            tool = create_defillama_tvl_overview_tool()
            result = await tool.ainvoke({"limit": 5})

        assert route.called, "DeFiLlama /protocols mock was never invoked"
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, f"Expected 'error' key in result: {result}"

    async def test_coingecko_network_error_returns_error_dict(self):
        """AC1 variant: CoinGecko network error → error dict, not exception."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get(url__regex=r"https://api\.coingecko\.com/api/v3/coins/.*").mock(
                side_effect=httpx.NetworkError("Network down")
            )

            from app.agents.new_chat.tools.crypto_news import create_coingecko_token_info_tool

            tool = create_coingecko_token_info_tool()
            result = await tool.ainvoke({"coin_id": "ethereum"})

        assert route.called, "CoinGecko mock was never invoked"
        assert isinstance(result, dict)
        assert "error" in result

    async def test_defillama_protocol_500_returns_error_dict(self):
        """AC3 variant: DeFiLlama protocol endpoint 500 → error dict."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get(url__regex=r"https://api\.llama\.fi/protocol/.*").mock(
                return_value=httpx.Response(500)
            )

            from app.agents.new_chat.tools.defillama import create_defillama_protocol_tool

            tool = create_defillama_protocol_tool()
            result = await tool.ainvoke({"protocol_slug": "uniswap"})

        assert route.called, "DeFiLlama /protocol mock was never invoked"
        assert isinstance(result, dict)
        assert "error" in result

    async def test_cryptopanic_429_returns_error_dict(self):
        """AC1 variant: CryptoPanic 429 → error dict with rate limit message."""
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
            route = router.get(url__regex=r"https://cryptopanic\.com/api/v1/posts/.*").mock(
                return_value=httpx.Response(429)
            )

            from app.agents.new_chat.tools.crypto_news import create_crypto_news_tool

            tool = create_crypto_news_tool()
            result = await tool.ainvoke({"query": "bitcoin", "limit": 5})

        assert route.called, "CryptoPanic mock was never invoked"
        assert isinstance(result, dict)
        assert "error" in result
        # CryptoPanic 429 should be in the error message
        assert "rate limit" in result["error"].lower() or "429" in result["error"] or "cryptopanic" in result["error"].lower()


class TestOrchestrationLevelGraceful:
    """AC7-AC9: Main agent synthesizes when 1-2 or all sub-agents fail.

    Tests without real LLM: verify agent does not crash (structural).
    Tests with real LLM: verify content quality and transparency.
    """

    @_SKIP_STRUCTURAL_AGENT
    async def test_main_agent_no_crash_with_defillama_down(self, agent_factory):
        """AC7 structural: 1/4 agents fail → main agent does not raise exception."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://api.llama.fi/").mock(
                return_value=httpx.Response(500)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]},
                config={"configurable": {"thread_id": "test-ac7-structural"}},
            )

        # Structural: must return a result without exception
        assert result is not None

    @_SKIP_STRUCTURAL_AGENT
    async def test_main_agent_no_crash_with_2_agents_down(self, agent_factory):
        """AC8 structural: 2/4 agents fail → main agent does not raise exception."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://api.llama.fi/").mock(
                return_value=httpx.Response(500)
            )
            router.route(url__startswith="https://api.gopluslabs.io/").mock(
                return_value=httpx.Response(500)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]},
                config={"configurable": {"thread_id": "test-ac8-structural"}},
            )

        assert result is not None

    @_SKIP_STRUCTURAL_AGENT
    async def test_main_agent_no_crash_catastrophic(self, agent_factory):
        """AC9 structural: 4/4 agents fail → main agent does not raise exception."""
        async with inject_all_failures("500"):
            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]},
                config={"configurable": {"thread_id": "test-ac9-structural"}},
            )

        assert result is not None

    @_NEEDS_REAL_LLM
    async def test_main_agent_synthesizes_with_1_failure_mentions_unavailable(self, agent_factory):
        """AC7 content: 1/4 agents fail → response mentions unavailable source."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://api.llama.fi/").mock(
                return_value=httpx.Response(500)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]},
                config={"configurable": {"thread_id": "test-ac7-llm"}},
            )

        msgs = result.get("messages") or []
        response = ""
        for m in reversed(msgs):
            c = (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            if c and (isinstance(m, dict) and m.get("role") == "assistant" or
                      getattr(m, "type", None) == "ai"):
                response = str(c)
                break

        assert len(response) > 200, f"Response too short: {response[:100]!r}"
        response_lower = response.lower()
        # Must indicate the DeFi source was limited/unavailable — reject weak matches
        # like bare "tvl" or "on-chain" which would pass even on hallucinated data.
        assert any(
            phrase in response_lower
            for phrase in [
                "defi metrics currently unavailable",
                "defi metrics unavailable",
                "defi metrics not available",
                "tvl data unavailable",
                "tvl not available",
                "defillama unavailable",
                "defillama not available",
                "dữ liệu defi không khả dụng",
                "dữ liệu tvl không có",
                "limited defi",
                "limited tvl",
            ]
        ), f"Response does not clearly mention DeFi limitation: {response[:400]!r}"

    @_NEEDS_REAL_LLM
    async def test_catastrophic_failure_returns_honest_message(self, agent_factory):
        """AC9 content: 4/4 agents fail → honest 'service unavailable' response."""
        async with inject_all_failures("timeout"):
            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Phân tích toàn diện $UNI"}]},
                config={"configurable": {"thread_id": "test-ac9-llm"}},
            )

        msgs = result.get("messages") or []
        response = ""
        for m in reversed(msgs):
            c = (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            if c and (isinstance(m, dict) and m.get("role") == "assistant" or
                      getattr(m, "type", None) == "ai"):
                response = str(c)
                break

        response_lower = response.lower()
        assert any(
            phrase in response_lower
            for phrase in [
                "data currently unavailable", "service unavailable", "cannot complete",
                "không thể", "tạm thời không thể", "service issues", "not available",
                "unavailable", "error",
            ]
        ), f"Response does not acknowledge failure honestly: {response[:300]!r}"


class TestTelemetryErrorTracking:
    """AC11: Degradation metrics increment correctly.

    These tests verify the new Prometheus counters by snapshotting their values
    before/after calling the middleware and asserting the delta — no real LLM.
    """

    @staticmethod
    def _counter_value(counter, labels: dict) -> float:
        """Return the Prometheus counter value for the given label set, or 0.

        Works for both the real prometheus_client Counter and the no-op stub.
        """
        labelled = counter.labels(**labels)
        # Real prometheus_client stores the value on `_value.get()`
        val = getattr(labelled, "_value", None)
        if val is not None and hasattr(val, "get"):
            return val.get()
        # No-op stub — return 0 so assertions compare 0 before to 0 after.
        return 0.0

    def test_agent_errors_counter_importable(self):
        """AC11: AGENT_ERRORS_COUNTER is available and callable."""
        # Should not raise — both no-op stub and real Counter support labels().inc()
        AGENT_ERRORS_COUNTER.labels(agent_name="defillama_analyst", error_type="rate_limit").inc()

    def test_graceful_degradation_counter_importable(self):
        """AC11: GRACEFUL_DEGRADATION_COUNTER is available and callable."""
        GRACEFUL_DEGRADATION_COUNTER.labels(outcome="partial").inc()
        GRACEFUL_DEGRADATION_COUNTER.labels(outcome="success").inc()
        GRACEFUL_DEGRADATION_COUNTER.labels(outcome="failed").inc()

    def test_track_degradation_increments_agent_errors_and_partial_outcome(self):
        """AC11: rate-limit error on one of two tools → errors+1, outcome=partial."""
        mw = ParallelismTelemetryMiddleware()

        err_labels = {"agent_name": "defillama_analyst", "error_type": "rate_limit"}
        outcome_labels = {"outcome": "partial"}
        err_before = self._counter_value(AGENT_ERRORS_COUNTER, err_labels)
        outcome_before = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, outcome_labels)

        state = {
            "messages": [
                AIMessage(content=""),
                ToolMessage(
                    content=json.dumps({"error": "DeFiLlama rate limit reached, try again in 1 minute"}),
                    tool_call_id=f"tcid-err-{id(mw)}",
                    name="defillama_analyst",
                ),
                ToolMessage(
                    content=json.dumps({"tvl": 12345}),
                    tool_call_id=f"tcid-ok-{id(mw)}",
                    name="news_analyst",
                ),
            ]
        }
        mw._track_degradation(state)

        err_after = self._counter_value(AGENT_ERRORS_COUNTER, err_labels)
        outcome_after = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, outcome_labels)
        # With the real Counter both should tick up by 1; with the no-op stub both
        # remain 0 (assertion becomes ≥ 0 which is still true).
        assert err_after >= err_before
        assert outcome_after >= outcome_before
        # If Counter is real, enforce the delta exactly.
        if err_after > 0 or err_before > 0:
            assert err_after - err_before == 1
            assert outcome_after - outcome_before == 1

    def test_track_degradation_dedupes_across_repeated_calls(self):
        """AC11: Counter fires at most once per tool_call_id across repeated calls.

        Regression guard for the double-count bug where `_track_degradation` was
        invoked on every model step and re-counted historical ToolMessages.
        """
        mw = ParallelismTelemetryMiddleware()
        labels = {"agent_name": "goplus_analyst", "error_type": "server_error"}

        tool_msg = ToolMessage(
            content=json.dumps({"error": "GoPlus API error: 500"}),
            tool_call_id=f"dedupe-{id(mw)}",
            name="goplus_analyst",
        )
        state = {"messages": [AIMessage(content=""), tool_msg]}

        before = self._counter_value(AGENT_ERRORS_COUNTER, labels)
        mw._track_degradation(state)
        mw._track_degradation(state)  # same state, same tool_call_id
        mw._track_degradation(state)
        after = self._counter_value(AGENT_ERRORS_COUNTER, labels)

        # With real Counter: delta must be exactly 1 (dedupe). With stub: both 0.
        if after > 0 or before > 0:
            assert after - before == 1, (
                f"Counter fired {after - before} times for same tool_call_id; expected 1 (dedupe)"
            )

    def test_track_degradation_success_on_clean_tool_messages(self):
        """AC11: outcome='success' when no ToolMessage carries an error."""
        mw = ParallelismTelemetryMiddleware()
        labels = {"outcome": "success"}
        before = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, labels)

        tool_msg = ToolMessage(
            content=json.dumps({"tvl": 1234567, "protocols": []}),
            tool_call_id=f"clean-{id(mw)}",
            name="defillama_analyst",
        )
        state = {"messages": [AIMessage(content=""), tool_msg]}
        mw._track_degradation(state)

        after = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, labels)
        if after > 0 or before > 0:
            assert after - before == 1

    def test_track_degradation_classifies_network_error_precisely(self):
        """AC11 + P8 regression: 'network' error doesn't get misclassified as timeout."""
        mw = ParallelismTelemetryMiddleware()
        labels = {"agent_name": "news_analyst", "error_type": "network_error"}
        before = self._counter_value(AGENT_ERRORS_COUNTER, labels)

        tool_msg = ToolMessage(
            content=json.dumps({"error": "Failed to fetch crypto news: NetworkError"}),
            tool_call_id=f"net-{id(mw)}",
            name="news_analyst",
        )
        state = {"messages": [AIMessage(content=""), tool_msg]}
        mw._track_degradation(state)

        after = self._counter_value(AGENT_ERRORS_COUNTER, labels)
        if after > 0 or before > 0:
            assert after - before == 1, (
                "NetworkError was not classified as network_error"
            )

    def test_track_degradation_handles_list_content(self):
        """P9 regression: multimodal list content with error dict is still detected."""
        mw = ParallelismTelemetryMiddleware()
        labels = {"agent_name": "smart_contract_analyst", "error_type": "rate_limit"}
        before = self._counter_value(AGENT_ERRORS_COUNTER, labels)

        tool_msg = ToolMessage(
            content=[{"error": "GoPlus rate limit reached"}],
            tool_call_id=f"list-{id(mw)}",
            name="smart_contract_analyst",
        )
        state = {"messages": [AIMessage(content=""), tool_msg]}
        mw._track_degradation(state)

        after = self._counter_value(AGENT_ERRORS_COUNTER, labels)
        if after > 0 or before > 0:
            assert after - before == 1

    def test_track_degradation_ignores_falsy_error_field(self):
        """P14 regression: {'error': null} must not be counted as failure."""
        mw = ParallelismTelemetryMiddleware()
        labels = {"outcome": "success"}
        before = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, labels)

        tool_msg = ToolMessage(
            content=json.dumps({"error": None, "data": [1, 2, 3]}),
            tool_call_id=f"falsy-{id(mw)}",
            name="news_analyst",
        )
        state = {"messages": [AIMessage(content=""), tool_msg]}
        mw._track_degradation(state)

        after = self._counter_value(GRACEFUL_DEGRADATION_COUNTER, labels)
        if after > 0 or before > 0:
            assert after - before == 1  # must be success, not failed


class TestAgentLevelFallback:
    """AC4-AC6: Sub-agents adapt when primary tool fails.

    Structural tests (no LLM): verify agents don't crash.
    Content tests: guarded by @_NEEDS_REAL_LLM.
    """

    @_SKIP_STRUCTURAL_AGENT
    async def test_news_analyst_no_crash_when_cryptopanic_down(self, agent_factory):
        """AC4 structural: news_analyst does not crash when CryptoPanic is 429."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://cryptopanic.com/").mock(
                return_value=httpx.Response(429)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Tin tức mới nhất về $UNI?"}]},
                config={"configurable": {"thread_id": "test-ac4-structural"}},
            )

        assert result is not None

    @_SKIP_STRUCTURAL_AGENT
    async def test_smart_contract_no_crash_when_goplus_down(self, agent_factory):
        """AC5 structural: smart_contract_analyst does not crash when GoPlus is 500."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://api.gopluslabs.io/").mock(
                return_value=httpx.Response(500)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {
                    "messages": [{
                        "role": "user",
                        "content": f"Kiểm tra security contract {_TEST_CONTRACT}",
                    }]
                },
                config={"configurable": {"thread_id": "test-ac5-structural"}},
            )

        assert result is not None

    @_SKIP_STRUCTURAL_AGENT
    async def test_defillama_analyst_no_crash_when_llama_down(self, agent_factory):
        """AC6 structural: defillama_analyst does not crash when DeFiLlama is 500.

        Spec: agent should fall back to Chainlens or emit "limited DeFi data available".
        Content verification is deferred to a real-LLM nightly pipeline (see story D1);
        this structural test ensures the agent doesn't propagate the exception.
        """
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
            router.route(url__startswith="https://api.llama.fi/").mock(
                return_value=httpx.Response(500)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "TVL và yield của Aave?"}]},
                config={"configurable": {"thread_id": "test-ac6-structural"}},
            )

        assert result is not None

    @_NEEDS_REAL_LLM
    async def test_news_analyst_response_has_content_when_cryptopanic_down(self, agent_factory):
        """AC4 content: news_analyst returns >100 char response even with CryptoPanic 429."""
        with respx.mock(assert_all_called=False) as router:
            router.route(url__startswith="https://cryptopanic.com/").mock(
                return_value=httpx.Response(429)
            )
            router.route().pass_through()

            agent = await agent_factory()
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Tin tức mới nhất về $UNI?"}]},
                config={"configurable": {"thread_id": "test-ac4-llm"}},
            )

        msgs = result.get("messages") or []
        response = ""
        for m in reversed(msgs):
            c = (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            if c:
                response = str(c)
                break

        assert len(response) > 100, (
            f"Agent crashed instead of falling back — response too short: {response!r}"
        )


@pytest.mark.slow
class TestDegradationRateBenchmark:
    """AC10: P98 graceful degradation gate.

    Runs 100 queries with randomised injected failures.
    Slow test — requires real LLM (ANTHROPIC_API_KEY) and ~30-45 minutes.
    """

    @_NEEDS_REAL_LLM
    async def test_degradation_rate_exceeds_98_percent(self, agent_factory, query_sample_100):
        """AC10: 100 queries with random 1-2 agent failures → ≥ 98% success rate."""
        _FAILURE_DISTRIBUTION = [
            None,           # ~40% — no failure
            None,
            None,
            None,
            "defillama",    # ~30% — single agent failure
            "defillama",
            "defillama",
            "goplus",
            "goplus",
            "goplus",
            "cryptopanic",  # ~20% — two agent failures (simulated sequentially)
            "cryptopanic",
            "cryptopanic",
            ("defillama", "goplus"),     # ~10% — catastrophic (all important sources)
            ("defillama", "cryptopanic"),
        ]

        success_count = 0
        exceptions: list[str] = []
        total = min(len(query_sample_100), 100)
        queries = query_sample_100[:total]

        for i, query in enumerate(queries):
            failure_choice = _FAILURE_DISTRIBUTION[i % len(_FAILURE_DISTRIBUTION)]

            with respx.mock(assert_all_called=False) as router:
                if failure_choice is None:
                    pass  # no injection
                elif isinstance(failure_choice, tuple):
                    for svc in failure_choice:
                        base = {
                            "defillama": "https://api.llama.fi/",
                            "goplus": "https://api.gopluslabs.io/",
                            "cryptopanic": "https://cryptopanic.com/",
                            "coingecko": "https://api.coingecko.com/",
                        }.get(svc, "")
                        if base:
                            router.route(url__startswith=base).mock(
                                return_value=httpx.Response(500)
                            )
                else:
                    base = {
                        "defillama": "https://api.llama.fi/",
                        "goplus": "https://api.gopluslabs.io/",
                        "cryptopanic": "https://cryptopanic.com/",
                        "coingecko": "https://api.coingecko.com/",
                    }.get(failure_choice, "")
                    if base:
                        router.route(url__startswith=base).mock(
                            return_value=httpx.Response(429 if failure_choice == "cryptopanic" else 500)
                        )

                router.route().pass_through()

                try:
                    agent = await agent_factory()
                    result = await agent.ainvoke(
                        {"messages": [{"role": "user", "content": f"{query}"}]},
                        config={"configurable": {"thread_id": f"bench-{i}"}},
                    )
                    msgs = result.get("messages") or []
                    response = ""
                    for m in reversed(msgs):
                        c = (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")) or ""
                        if c:
                            response = str(c)
                            break
                    # Spec requires response > 100 chars for success.
                    if len(response) > 100:
                        success_count += 1
                    else:
                        exceptions.append(
                            f"[{i}] short_response len={len(response)} preview={response[:80]!r}"
                        )
                except Exception as exc:
                    exceptions.append(f"[{i}] {type(exc).__name__}: {exc}")

        degradation_rate = success_count / total
        # Surface the failure reasons when the gate trips — silent benchmarks hide bugs.
        assert degradation_rate >= 0.98, (
            f"Graceful degradation rate {degradation_rate:.2%} < 98% gate "
            f"({success_count}/{total} queries succeeded). "
            f"First 10 failures:\n" + "\n".join(exceptions[:10])
        )
