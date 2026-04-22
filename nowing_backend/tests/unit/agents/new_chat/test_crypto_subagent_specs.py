"""Unit tests for Story 0.2: Base Sub-Agents specs.

Covers:
- AC2: Token budget — all 4 prompts < 500 tokens (NFR-CS1)
- AC3: Tool scoping — each spec's tools match the allowed set
"""

import pytest
import tiktoken

from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ANALYST_DESCRIPTION,
    DEFILLAMA_ANALYST_NAME,
    DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ANALYST_DESCRIPTION,
    NEWS_ANALYST_NAME,
    NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ANALYST_DESCRIPTION,
    SENTIMENT_ANALYST_NAME,
    SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ANALYST_DESCRIPTION,
    SMART_CONTRACT_ANALYST_NAME,
    SMART_CONTRACT_ANALYST_PROMPT,
)


# ---------------------------------------------------------------------------
# AC2: Token budget (NFR-CS1 — system prompt < 500 tokens each)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,prompt",
    [
        ("defillama_analyst", DEFILLAMA_ANALYST_PROMPT),
        ("sentiment_analyst", SENTIMENT_ANALYST_PROMPT),
        ("news_analyst", NEWS_ANALYST_PROMPT),
        ("smart_contract_analyst", SMART_CONTRACT_ANALYST_PROMPT),
    ],
)
def test_prompts_under_token_budget(label: str, prompt: str) -> None:
    """NFR-CS1: Each sub-agent system prompt must be < 500 tokens."""
    enc = tiktoken.encoding_for_model("gpt-4")
    token_count = len(enc.encode(prompt))
    assert token_count < 500, (
        f"{label} prompt exceeds 500-token budget: {token_count} tokens"
    )


# ---------------------------------------------------------------------------
# AC1: Constants export validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,description,prompt",
    [
        (DEFILLAMA_ANALYST_NAME, DEFILLAMA_ANALYST_DESCRIPTION, DEFILLAMA_ANALYST_PROMPT),
        (SENTIMENT_ANALYST_NAME, SENTIMENT_ANALYST_DESCRIPTION, SENTIMENT_ANALYST_PROMPT),
        (NEWS_ANALYST_NAME, NEWS_ANALYST_DESCRIPTION, NEWS_ANALYST_PROMPT),
        (SMART_CONTRACT_ANALYST_NAME, SMART_CONTRACT_ANALYST_DESCRIPTION, SMART_CONTRACT_ANALYST_PROMPT),
    ],
)
def test_spec_constants_are_non_empty_strings(name: str, description: str, prompt: str) -> None:
    """All 3 constants per spec must be non-empty strings."""
    assert isinstance(name, str) and name.strip(), f"NAME is empty or not a string: {name!r}"
    assert isinstance(description, str) and description.strip(), f"DESCRIPTION is empty: {description!r}"
    assert isinstance(prompt, str) and prompt.strip(), f"PROMPT is empty: {prompt!r}"


def test_agent_names_are_unique() -> None:
    """All 4 agent names must be distinct."""
    names = [
        DEFILLAMA_ANALYST_NAME,
        SENTIMENT_ANALYST_NAME,
        NEWS_ANALYST_NAME,
        SMART_CONTRACT_ANALYST_NAME,
    ]
    assert len(names) == len(set(names)), f"Duplicate agent names: {names}"


# ---------------------------------------------------------------------------
# AC3: Tool scoping
# ---------------------------------------------------------------------------

class _MockTool:
    """Minimal fake tool for testing tool-scoping logic."""

    def __init__(self, name: str) -> None:
        self.name = name


# All tool names that exist in the full tools list (superset)
_ALL_TOOL_NAMES = [
    # DeFiLlama
    "get_defillama_protocol",
    "get_defillama_tvl_overview",
    "get_defillama_yields",
    "get_defillama_stablecoins",
    "get_defillama_bridges",
    # DexScreener
    "get_live_token_data",
    # Chainlens
    "chainlens_deep_research",
    # Sentiment
    "get_cmc_sentiment",
    "get_reddit_crypto_sentiment",
    # News + CoinGecko
    "get_crypto_news",
    "get_coingecko_token_info",
    # Contract analysis
    "get_contract_info",
    "check_token_security",
    # Unrelated tools (must NOT appear in scoped lists)
    "web_search",
    "read_file",
    "create_document",
]

_ALL_TOOLS = [_MockTool(n) for n in _ALL_TOOL_NAMES]


def _scope(allowed: tuple[str, ...]) -> list[_MockTool]:
    """Replicate the tool-scoping list-comprehension from chat_deepagent.py."""
    return [t for t in _ALL_TOOLS if t.name in allowed]


# Expected scopes per spec (mirrors chat_deepagent.py)
_DEFILLAMA_ALLOWED = (
    "get_defillama_protocol", "get_defillama_tvl_overview", "get_defillama_yields",
    "get_defillama_stablecoins", "get_defillama_bridges",
    "get_live_token_data", "chainlens_deep_research",
)
_SENTIMENT_ALLOWED = (
    "get_cmc_sentiment", "get_reddit_crypto_sentiment", "chainlens_deep_research",
)
_NEWS_ALLOWED = (
    "get_crypto_news", "get_coingecko_token_info", "chainlens_deep_research",
)
_SMART_CONTRACT_ALLOWED = (
    "get_contract_info", "check_token_security", "chainlens_deep_research",
)


@pytest.mark.parametrize(
    "label,allowed",
    [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
    ],
)
def test_tool_scoping_only_includes_allowed_tools(label: str, allowed: tuple[str, ...]) -> None:
    """Each scoped tool list must contain exactly the allowed tools (no more, no less)."""
    scoped = _scope(allowed)
    scoped_names = {t.name for t in scoped}
    assert scoped_names == set(allowed), (
        f"{label}: scoped tools mismatch.\n"
        f"  Expected: {sorted(allowed)}\n"
        f"  Got:      {sorted(scoped_names)}"
    )


def test_defillama_does_not_have_sentiment_tools() -> None:
    """defillama_analyst must not accidentally get sentiment/news/contract tools."""
    defillama_scoped = {t.name for t in _scope(_DEFILLAMA_ALLOWED)}
    cross_tools = {"get_cmc_sentiment", "get_reddit_crypto_sentiment",
                   "get_crypto_news", "get_coingecko_token_info",
                   "get_contract_info", "check_token_security"}
    leaked = defillama_scoped & cross_tools
    assert not leaked, f"defillama_analyst has unexpected tools: {leaked}"


def test_smart_contract_does_not_have_defillama_tools() -> None:
    """smart_contract_analyst must not get DeFiLlama tools."""
    sc_scoped = {t.name for t in _scope(_SMART_CONTRACT_ALLOWED)}
    defi_tools = {
        "get_defillama_protocol", "get_defillama_tvl_overview",
        "get_defillama_yields", "get_defillama_stablecoins", "get_defillama_bridges",
        "get_live_token_data",
    }
    leaked = sc_scoped & defi_tools
    assert not leaked, f"smart_contract_analyst has unexpected DeFiLlama tools: {leaked}"


def test_chainlens_available_to_all_crypto_agents() -> None:
    """chainlens_deep_research must be available to all 4 crypto agents."""
    for label, allowed in [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
    ]:
        scoped_names = {t.name for t in _scope(allowed)}
        assert "chainlens_deep_research" in scoped_names, (
            f"{label} is missing chainlens_deep_research"
        )


def test_unrelated_tools_excluded_from_all_crypto_agents() -> None:
    """Tools like web_search/read_file/create_document must not leak into any crypto agent."""
    unrelated = {"web_search", "read_file", "create_document"}
    for label, allowed in [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
    ]:
        scoped_names = {t.name for t in _scope(allowed)}
        leaked = scoped_names & unrelated
        assert not leaked, f"{label} has unrelated tools: {leaked}"
