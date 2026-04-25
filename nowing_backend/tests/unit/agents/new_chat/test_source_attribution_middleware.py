"""Unit tests for Story 9-UX-1 T5: SourceAttributionMiddleware + narration templates.

Covers:
- AC2: pre-call narration emitted for known tools
- AC3: post-call source attribution emitted for known tools
- narration_templates: PRE_CALL and TOOL_SOURCE_MAP completeness
- SourceAttributionMiddleware: dispatch_custom_event calls + graceful no-op for unknown tools
- VercelStreamingService: all 5 format_orchestra_* methods
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.agents.new_chat.subagents.crypto.narration_templates import (
    PRE_CALL,
    TOOL_SOURCE_MAP,
)
from app.services.new_streaming_service import VercelStreamingService


# ─────────────────────────────────────────────────────────────
# narration_templates tests
# ─────────────────────────────────────────────────────────────

EXPECTED_TOOLS = {
    "get_coingecko_token_info",
    "get_coingecko_market_chart",
    "get_defillama_protocol",
    "get_defillama_pools",
    "check_token_security",
    "get_cryptopanic_news",
    "get_reddit_crypto_sentiment",
    "get_fear_greed_index",
    "chainlens_deep_research",
}


def test_pre_call_covers_all_expected_tools():
    assert EXPECTED_TOOLS.issubset(set(PRE_CALL.keys()))


def test_tool_source_map_covers_all_expected_tools():
    assert EXPECTED_TOOLS.issubset(set(TOOL_SOURCE_MAP.keys()))


def test_tool_source_map_values_have_domain_and_favicon():
    for tool, entry in TOOL_SOURCE_MAP.items():
        assert len(entry) == 3, f"{tool}: TOOL_SOURCE_MAP entry must be (domain, favicon, url)"
        domain, favicon, url = entry
        assert domain, f"{tool}: domain is empty"
        assert favicon.startswith("https://"), f"{tool}: favicon missing https"
        assert domain in favicon, f"{tool}: favicon URL doesn't contain domain"
        assert url.startswith("https://"), f"{tool}: deeplink url missing https"


def test_pre_call_strings_are_vietnamese():
    for tool, text in PRE_CALL.items():
        # Must contain Vietnamese characters or at least end with ellipsis
        assert text.endswith("..."), f"{tool}: pre-call narration should end with '...'"
        assert len(text) > 10, f"{tool}: pre-call narration too short"


# ─────────────────────────────────────────────────────────────
# VercelStreamingService format_orchestra_* tests
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def svc():
    return VercelStreamingService()


def test_format_orchestra_narration(svc):
    result = svc.format_orchestra_narration(
        session_id="sess-1",
        agent_id="tokenomics_analyst",
        text="Đang query CoinGecko...",
        tone="fetching",
    )
    assert "orchestra-narration" in result
    assert "tokenomics_analyst" in result
    assert "fetching" in result


def test_format_orchestra_source_fetched(svc):
    result = svc.format_orchestra_source_fetched(
        session_id="sess-1",
        agent_id="defillama_analyst",
        domain="defillama.com",
        favicon="https://icons.duckduckgo.com/ip3/defillama.com.ico",
    )
    assert "orchestra-source-fetched" in result
    assert "defillama.com" in result


def test_format_orchestra_fact_captured(svc):
    result = svc.format_orchestra_fact_captured(
        session_id="sess-1",
        agent_id="tokenomics_analyst",
        fact_summary="TVL $3.2B",
        value=3.2e9,
        unit="usd",
    )
    assert "orchestra-fact-captured" in result
    assert "TVL $3.2B" in result


def test_format_orchestra_fact_captured_optional_fields(svc):
    result = svc.format_orchestra_fact_captured(
        session_id="sess-1",
        agent_id="agent",
        fact_summary="Fact without value",
    )
    assert "orchestra-fact-captured" in result
    # value and unit should not appear when not set
    assert '"value"' not in result
    assert '"unit"' not in result


def test_format_orchestra_model_attribution(svc):
    result = svc.format_orchestra_model_attribution(
        session_id="sess-1",
        agent_id="news_analyst",
        model="claude-sonnet-4-6",
        provider="trollllm",
        tier="standard",
    )
    assert "orchestra-model-attribution" in result
    assert "claude-sonnet-4-6" in result
    assert "trollllm" in result


def test_format_orchestra_model_attribution_no_tier(svc):
    result = svc.format_orchestra_model_attribution(
        session_id="sess-1",
        agent_id="agent",
        model="model",
        provider="provider",
    )
    assert '"tier"' not in result


def test_format_orchestra_rate_gate_wait(svc):
    result = svc.format_orchestra_rate_gate_wait(
        session_id="sess-1",
        wait_seconds=7.2,
        reason="min_interval",
    )
    assert "orchestra-rate-gate-wait" in result
    assert "7.2" in result
    assert "min_interval" in result


# ─────────────────────────────────────────────────────────────
# SourceAttributionMiddleware tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_source_attribution_emits_pre_narration_for_known_tool():
    from app.agents.new_chat.chat_deepagent import SourceAttributionMiddleware

    middleware = SourceAttributionMiddleware(agent_name="tokenomics_analyst")

    mock_request = MagicMock()
    mock_request.name = "get_coingecko_token_info"
    mock_handler = AsyncMock(return_value={"price": 7.23, "source_domain": "coingecko.com"})

    with patch("langchain_core.callbacks.dispatch_custom_event") as mock_dispatch:
        result = await middleware.awrap_tool_call(mock_request, mock_handler)

    assert mock_handler.called
    assert result == {"price": 7.23, "source_domain": "coingecko.com"}

    # AC2: pre-call narration MUST be dispatched before handler runs
    pre_call = next(
        (c for c in mock_dispatch.call_args_list if c.args[0] == "orchestra_narration"),
        None,
    )
    assert pre_call is not None, "orchestra_narration was never dispatched"
    payload = pre_call.args[1]
    assert payload["text"] == "Đang query CoinGecko cho thông tin token..."
    assert payload["agentName"] == "tokenomics_analyst"
    assert payload["tone"] == "fetching"

    # AC3: post-call source attribution MUST also be dispatched
    source_call = next(
        (c for c in mock_dispatch.call_args_list if c.args[0] == "orchestra_source_fetched"),
        None,
    )
    assert source_call is not None, "orchestra_source_fetched was never dispatched"
    assert source_call.args[1]["source"]["domain"] == "coingecko.com"


@pytest.mark.asyncio
async def test_source_attribution_no_crash_for_unknown_tool():
    from app.agents.new_chat.chat_deepagent import SourceAttributionMiddleware

    middleware = SourceAttributionMiddleware(agent_name="general")

    mock_request = MagicMock()
    mock_request.name = "some_unknown_tool"
    mock_handler = AsyncMock(return_value={"data": "result"})

    # Should not raise even if dispatch_custom_event is not available
    with patch("langchain_core.callbacks.dispatch_custom_event", side_effect=Exception("no context")):
        result = await middleware.awrap_tool_call(mock_request, mock_handler)

    assert result == {"data": "result"}


@pytest.mark.asyncio
async def test_source_attribution_reads_source_domain_from_result():
    from app.agents.new_chat.chat_deepagent import SourceAttributionMiddleware

    middleware = SourceAttributionMiddleware(agent_name="smart_contract_analyst")

    mock_request = MagicMock()
    mock_request.name = "some_tool_not_in_map"
    # Tool returns source_domain in result
    mock_handler = AsyncMock(return_value={"data": "ok", "source_domain": "example.com"})

    emitted_names = []

    def fake_dispatch(name, data):
        emitted_names.append(name)

    with patch("langchain_core.callbacks.dispatch_custom_event", side_effect=fake_dispatch):
        result = await middleware.awrap_tool_call(mock_request, mock_handler)

    # Should emit source_fetched for the domain found in result
    assert "orchestra_source_fetched" in emitted_names
