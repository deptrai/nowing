"""Unit tests for Story 0.2: Base Sub-Agents specs.

Covers:
- AC2: Token budget — all 4 prompts < 500 tokens (NFR-CS1)
- AC3: Tool scoping — each spec's tools match the allowed set
"""

import pytest
import tiktoken

from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ALLOWED_TOOLS,
    DEFILLAMA_ANALYST_DESCRIPTION,
    DEFILLAMA_ANALYST_NAME,
    DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ALLOWED_TOOLS,
    NEWS_ANALYST_DESCRIPTION,
    NEWS_ANALYST_NAME,
    NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ALLOWED_TOOLS,
    SENTIMENT_ANALYST_DESCRIPTION,
    SENTIMENT_ANALYST_NAME,
    SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ALLOWED_TOOLS,
    SMART_CONTRACT_ANALYST_DESCRIPTION,
    SMART_CONTRACT_ANALYST_NAME,
    SMART_CONTRACT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.tokenomics_spec import (
    TOKENOMICS_ALLOWED_TOOLS,
    TOKENOMICS_ANALYST_DESCRIPTION,
    TOKENOMICS_ANALYST_NAME,
    TOKENOMICS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.yield_optimizer_spec import (
    YIELD_OPTIMIZER_ALLOWED_TOOLS,
    YIELD_OPTIMIZER_DESCRIPTION,
    YIELD_OPTIMIZER_NAME,
    YIELD_OPTIMIZER_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_money_spec import (
    SMART_MONEY_ALLOWED_TOOLS,
    SMART_MONEY_ANALYST_DESCRIPTION,
    SMART_MONEY_ANALYST_NAME,
    SMART_MONEY_ANALYST_PROMPT,
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
        ("tokenomics_analyst", TOKENOMICS_ANALYST_PROMPT),
        ("yield_optimizer", YIELD_OPTIMIZER_PROMPT),
        ("smart_money_analyst", SMART_MONEY_ANALYST_PROMPT),
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
        (TOKENOMICS_ANALYST_NAME, TOKENOMICS_ANALYST_DESCRIPTION, TOKENOMICS_ANALYST_PROMPT),
        (YIELD_OPTIMIZER_NAME, YIELD_OPTIMIZER_DESCRIPTION, YIELD_OPTIMIZER_PROMPT),
    ],
)
def test_spec_constants_are_non_empty_strings(name: str, description: str, prompt: str) -> None:
    """All 3 constants per spec must be non-empty strings."""
    assert isinstance(name, str) and name.strip(), f"NAME is empty or not a string: {name!r}"
    assert isinstance(description, str) and description.strip(), f"DESCRIPTION is empty: {description!r}"
    assert isinstance(prompt, str) and prompt.strip(), f"PROMPT is empty: {prompt!r}"


def test_agent_names_are_unique() -> None:
    """All 6 agent names must be distinct."""
    names = [
        DEFILLAMA_ANALYST_NAME,
        SENTIMENT_ANALYST_NAME,
        NEWS_ANALYST_NAME,
        SMART_CONTRACT_ANALYST_NAME,
        TOKENOMICS_ANALYST_NAME,
        YIELD_OPTIMIZER_NAME,
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
    "get_live_token_price",
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
    "get_tokeninsight_rating",
    # Contract analysis
    "get_contract_info",
    "check_token_security",
    "get_certik_audit_score",
    "get_certik_incident_history",
    # Nansen / Smart Money
    "get_smart_money_flow",
    "get_nansen_smart_money",
    "get_nansen_wallet_label",
    "get_nansen_token_god_mode",
    # Unrelated tools (must NOT appear in scoped lists)
    "web_search",
    "read_file",
    "create_document",
]

_YIELD_OPTIMIZER_ALLOWED = YIELD_OPTIMIZER_ALLOWED_TOOLS

_ALL_TOOLS = [_MockTool(n) for n in _ALL_TOOL_NAMES]


def _scope(allowed: tuple[str, ...]) -> list[_MockTool]:
    """Replicate the tool-scoping list-comprehension from chat_deepagent.py."""
    return [t for t in _ALL_TOOLS if t.name in allowed]


# Expected scopes per spec (imported from spec files — single source of truth
# shared with chat_deepagent.py).
_DEFILLAMA_ALLOWED = DEFILLAMA_ALLOWED_TOOLS
_SENTIMENT_ALLOWED = SENTIMENT_ALLOWED_TOOLS
_NEWS_ALLOWED = NEWS_ALLOWED_TOOLS
_SMART_CONTRACT_ALLOWED = SMART_CONTRACT_ALLOWED_TOOLS
_TOKENOMICS_ALLOWED = TOKENOMICS_ALLOWED_TOOLS


@pytest.mark.parametrize(
    "label,allowed",
    [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
        ("tokenomics_analyst", _TOKENOMICS_ALLOWED),
        ("yield_optimizer", _YIELD_OPTIMIZER_ALLOWED),
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


def test_yield_optimizer_does_not_have_sentiment_or_coingecko_tools() -> None:
    """yield_optimizer must not see sentiment, news, or coingecko tools (scope isolation)."""
    yo_scoped = {t.name for t in _scope(_YIELD_OPTIMIZER_ALLOWED)}
    forbidden = {
        "get_cmc_sentiment", "get_reddit_crypto_sentiment",
        "get_crypto_news", "get_coingecko_token_info", "get_contract_info",
        "get_defillama_stablecoins", "get_defillama_bridges", "get_defillama_tvl_overview",
    }
    leaked = yo_scoped & forbidden
    assert not leaked, f"yield_optimizer has unexpected tools: {leaked}"


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
    """chainlens_deep_research must be available to all 6 crypto agents."""
    for label, allowed in [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
        ("tokenomics_analyst", _TOKENOMICS_ALLOWED),
        ("yield_optimizer", _YIELD_OPTIMIZER_ALLOWED),
    ]:
        scoped_names = {t.name for t in _scope(allowed)}
        assert "chainlens_deep_research" in scoped_names, (
            f"{label} is missing chainlens_deep_research"
        )


def test_unrelated_tools_excluded_from_all_crypto_agents() -> None:
    """Tools like read_file/create_document must not leak into any crypto agent.

    web_search is generally excluded BUT smart_money_analyst is whitelisted to use
    it as a fallback when Nansen rate-limits (Story 10.1, prior review finding).
    """
    base_unrelated = {"read_file", "create_document"}
    web_search_users = {"smart_money_analyst"}  # explicit whitelist
    for label, allowed in [
        ("defillama_analyst", _DEFILLAMA_ALLOWED),
        ("sentiment_analyst", _SENTIMENT_ALLOWED),
        ("news_analyst", _NEWS_ALLOWED),
        ("smart_contract_analyst", _SMART_CONTRACT_ALLOWED),
        ("tokenomics_analyst", _TOKENOMICS_ALLOWED),
        ("yield_optimizer", _YIELD_OPTIMIZER_ALLOWED),
        ("smart_money_analyst", SMART_MONEY_ALLOWED_TOOLS),
    ]:
        unrelated = base_unrelated if label in web_search_users else base_unrelated | {"web_search"}
        scoped_names = {t.name for t in _scope(allowed)}
        leaked = scoped_names & unrelated
        assert not leaked, f"{label} has unrelated tools: {leaked}"


# ---------------------------------------------------------------------------
# Story 9.1 AC3 — explicit: tokenomics has exactly the expected 2 tools
# ---------------------------------------------------------------------------

def test_tokenomics_has_exactly_coingecko_and_chainlens() -> None:
    """Story 9.1 AC3: tokenomics_analyst must have exactly these tools."""
    assert set(TOKENOMICS_ALLOWED_TOOLS) == {
        "get_coingecko_token_info",
        "get_tokeninsight_rating",
        "chainlens_deep_research",
    }


def test_smart_money_has_exactly_nansen_and_web_search() -> None:
    """Story 10.1.1: smart_money_analyst must have exactly these tools."""
    assert set(SMART_MONEY_ALLOWED_TOOLS) == {
        "get_smart_money_flow",
        "get_nansen_smart_money",
        "get_nansen_wallet_label",
        "get_nansen_token_god_mode",
        "web_search",
    }


def test_tokenomics_does_not_have_defi_or_security_tools() -> None:
    """Story 9.1 AC3: tokenomics must not accidentally see DeFiLlama, GoPlus,
    or CryptoPanic tools (scope isolation)."""
    tokenomics = set(TOKENOMICS_ALLOWED_TOOLS)
    forbidden = {
        "get_defillama_protocol", "get_defillama_tvl_overview",
        "get_defillama_yields", "get_defillama_stablecoins", "get_defillama_bridges",
        "check_token_security", "get_contract_info",
        "get_crypto_news", "get_cmc_sentiment", "get_reddit_crypto_sentiment",
    }
    leaked = tokenomics & forbidden
    assert not leaked, f"tokenomics_analyst has unexpected tools: {leaked}"


def test_tokenomics_tools_are_stateless() -> None:
    """Story 9.1 AC4 (NFR-CS4): both tokenomics tools must declare requires=[]
    in ToolDefinition so the agent can spawn fresh per request without DB/session
    context."""
    from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

    by_name = {td.name: td for td in BUILTIN_TOOLS}
    for tool_name in TOKENOMICS_ALLOWED_TOOLS:
        assert tool_name in by_name, (
            f"tokenomics tool {tool_name!r} missing from BUILTIN_TOOLS registry"
        )
        td = by_name[tool_name]
        assert td.requires == [], (
            f"tokenomics tool {tool_name!r} must be stateless (requires=[]), "
            f"got requires={td.requires!r}. NFR-CS4 violated."
        )


# ---------------------------------------------------------------------------
# Patch #2: validate allowed tools against REAL registry (catches typos)
# ---------------------------------------------------------------------------

def test_allowed_tools_exist_in_real_registry() -> None:
    """Every tool name in *_ALLOWED_TOOLS must exist in the real tool registry.

    This catches typos like ``get_defilllama_protocol`` that mock-based tests
    (using _ALL_TOOL_NAMES) would silently pass. Imports the real registry to
    ensure our whitelists are always in sync with BUILTIN_TOOLS.
    """
    from app.agents.new_chat.tools.registry import get_all_tool_names

    registered = set(get_all_tool_names())
    assert registered, "Registry returned empty tool list — registry import broken"

    for label, allowed in [
        ("defillama_analyst", DEFILLAMA_ALLOWED_TOOLS),
        ("sentiment_analyst", SENTIMENT_ALLOWED_TOOLS),
        ("news_analyst", NEWS_ALLOWED_TOOLS),
        ("smart_contract_analyst", SMART_CONTRACT_ALLOWED_TOOLS),
        ("tokenomics_analyst", TOKENOMICS_ALLOWED_TOOLS),
        ("yield_optimizer", YIELD_OPTIMIZER_ALLOWED_TOOLS),
        ("smart_money_analyst", SMART_MONEY_ALLOWED_TOOLS),
    ]:
        missing = set(allowed) - registered
        assert not missing, (
            f"{label}: allowed-tool name(s) not registered in BUILTIN_TOOLS: "
            f"{sorted(missing)}. Either fix the typo in the spec or register "
            f"the tool in app/agents/new_chat/tools/registry.py."
        )


# ---------------------------------------------------------------------------
# Story 10.1: assert SubAgentMiddleware registers exactly 8 sub-agents
# (general_purpose + 4 Epic 0.2 base + tokenomics + yield_optimizer + smart_money)
# whale_tracker is conditional on feature flag — counted separately.
# ---------------------------------------------------------------------------

def test_subagent_middleware_registers_eight_agents() -> None:
    """chat_deepagent.py must wire exactly 8 unconditional sub-agents.

    Greps the source for the SubAgentMiddleware(...) block to verify the
    subagents= list contains exactly the expected spec identifiers. The
    whale_tracker is wrapped in a conditional spread (`*([...] if ...)`),
    which is normalized to a single placeholder before token comparison so
    the test stays stable across formatting changes of that conditional.
    """
    import re
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[4]
        / "app" / "agents" / "new_chat" / "chat_deepagent.py"
    )
    assert source_path.exists(), f"chat_deepagent.py not found at {source_path}"

    source = source_path.read_text(encoding="utf-8")

    # Pre-normalize the conditional spread for whale_tracker into a single
    # identifier BEFORE extraction so the inner `]` of `[whale_tracker_spec]`
    # does not prematurely close the outer subagents=[...] capture.
    normalized_source = re.sub(
        r"\*\(\s*\[whale_tracker_spec\].*?\)",
        "whale_tracker_spec_optional",
        source,
        flags=re.DOTALL,
    )

    match = re.search(
        r"SubAgentMiddleware\s*\(\s*.*?subagents\s*=\s*\[(.*?)\]\s*,?\s*\)",
        normalized_source,
        re.DOTALL,
    )
    assert match, "Could not locate SubAgentMiddleware(subagents=[...]) in chat_deepagent.py"

    subagents_block = match.group(1)
    # Strip inline comments
    cleaned = re.sub(r"#[^\n]*", "", subagents_block)

    expected_specs = {
        "general_purpose_spec",
        "defillama_analyst_spec",
        "sentiment_analyst_spec",
        "news_analyst_spec",
        "smart_contract_analyst_spec",
        "tokenomics_analyst_spec",
        "yield_optimizer_spec",
        "smart_money_spec",
        "whale_tracker_spec_optional",
    }
    found_specs = {
        token.strip() for token in cleaned.split(",") if token.strip()
    }

    assert found_specs == expected_specs, (
        f"SubAgentMiddleware subagent registration drift.\n"
        f"  Expected: {sorted(expected_specs)}\n"
        f"  Found:    {sorted(found_specs)}"
    )


# ---------------------------------------------------------------------------
# Story 9.4 AC3 — explicit: yield_optimizer has exactly the expected 4 tools
# ---------------------------------------------------------------------------

def test_yield_optimizer_has_exactly_four_tools() -> None:
    """Story 9.4 AC3: yield_optimizer must have ONLY the 4 specified tools."""
    assert set(YIELD_OPTIMIZER_ALLOWED_TOOLS) == {
        "get_defillama_yields",
        "get_defillama_protocol",
        "check_token_security",
        "chainlens_deep_research",
    }


def test_yield_optimizer_does_not_have_coingecko_or_news_tools() -> None:
    """Story 9.4 AC3: yield_optimizer must not see CoinGecko, news, or sentiment tools."""
    yo_tools = set(YIELD_OPTIMIZER_ALLOWED_TOOLS)
    forbidden = {
        "get_coingecko_token_info",
        "get_crypto_news",
        "get_cmc_sentiment",
        "get_reddit_crypto_sentiment",
        "get_contract_info",
        "get_defillama_stablecoins",
        "get_defillama_bridges",
    }
    leaked = yo_tools & forbidden
    assert not leaked, f"yield_optimizer has unexpected tools: {leaked}"


def test_yield_optimizer_tools_are_stateless() -> None:
    """Story 9.4 AC4 (NFR-CS4): all yield_optimizer tools must declare requires=[]."""
    from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

    by_name = {td.name: td for td in BUILTIN_TOOLS}
    for tool_name in YIELD_OPTIMIZER_ALLOWED_TOOLS:
        assert tool_name in by_name, (
            f"yield_optimizer tool {tool_name!r} missing from BUILTIN_TOOLS registry"
        )
        td = by_name[tool_name]
        assert td.requires == [], (
            f"yield_optimizer tool {tool_name!r} must be stateless (requires=[]), "
            f"got requires={td.requires!r}. NFR-CS4 violated."
        )

