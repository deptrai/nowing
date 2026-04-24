"""Wiring + structural tests for Story 0.2: Base Sub-Agents.

Covers:
- AC4: SubAgentMiddleware registers 7 agents (structural source check)
- AC10 / NFR-CS4: each sub-agent spec uses a fresh middleware factory call
  (not a shared mutable instance) — structural source check
- P1 regression: no spec dict uses ``"prompt"`` key (must be ``"system_prompt"``)
- P3 guard: chainlens missing → ERROR log before wiring continues
- Prompt fidelity: every tool mentioned in a prompt is in that agent's scope

AC5–AC9 (functional spawn + parallel-ratio timing) require LLM mocking and
live graph execution; tracked in Story 0-4 (api-integration-tests) and
Story 0-5 (parallel-execution-validation).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ALLOWED_TOOLS,
    DEFILLAMA_ANALYST_NAME,
    DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ALLOWED_TOOLS,
    NEWS_ANALYST_NAME,
    NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ALLOWED_TOOLS,
    SENTIMENT_ANALYST_NAME,
    SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ALLOWED_TOOLS,
    SMART_CONTRACT_ANALYST_NAME,
    SMART_CONTRACT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.tokenomics_spec import (
    TOKENOMICS_ALLOWED_TOOLS,
    TOKENOMICS_ANALYST_NAME,
    TOKENOMICS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.yield_optimizer_spec import (
    YIELD_OPTIMIZER_ALLOWED_TOOLS,
    YIELD_OPTIMIZER_NAME,
    YIELD_OPTIMIZER_PROMPT,
)

_CHAT_DEEPAGENT_PATH = (
    Path(__file__).resolve().parents[4]
    / "app"
    / "agents"
    / "new_chat"
    / "chat_deepagent.py"
)


@pytest.fixture(scope="module")
def chat_deepagent_source() -> str:
    return _CHAT_DEEPAGENT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def chat_deepagent_ast(chat_deepagent_source: str) -> ast.Module:
    return ast.parse(chat_deepagent_source)


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name} not found in chat_deepagent.py")


def _collect_dict_keys(node: ast.AST) -> list[list[str]]:
    """Return the list of string-key tuples for every ``ast.Dict`` inside node."""
    result: list[list[str]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Dict):
            keys = [
                k.value
                for k in sub.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            if keys:
                result.append(keys)
    return result


# ---------------------------------------------------------------------------
# Story 9.4: SubAgentMiddleware registers exactly 7 agents
# ---------------------------------------------------------------------------

def test_subagent_middleware_registers_seven_specs(chat_deepagent_source: str) -> None:
    """Story 9.4: SubAgentMiddleware(subagents=[...]) must include all 7 specs."""
    m = re.search(
        r"SubAgentMiddleware\(\s*[^)]*?subagents\s*=\s*\[([^\]]+)\]",
        chat_deepagent_source,
        re.DOTALL,
    )
    assert m, "Could not locate SubAgentMiddleware(subagents=[...]) in chat_deepagent.py"
    block = m.group(1)
    expected = [
        "general_purpose_spec",
        "defillama_analyst_spec",
        "sentiment_analyst_spec",
        "news_analyst_spec",
        "smart_contract_analyst_spec",
        "tokenomics_analyst_spec",
        "yield_optimizer_spec",
    ]
    for name in expected:
        assert name in block, f"Spec '{name}' not registered in SubAgentMiddleware"


# ---------------------------------------------------------------------------
# P1 regression: no spec uses the wrong "prompt" key
# ---------------------------------------------------------------------------

def test_no_spec_uses_prompt_key_instead_of_system_prompt(
    chat_deepagent_source: str,
) -> None:
    """deepagents.SubAgent TypedDict requires ``system_prompt`` — ``prompt`` key
    would KeyError inside SubAgentMiddleware.wrap_agent at runtime.
    """
    # Look inside the file scope for any occurrence of `"prompt":` followed by
    # an *_ANALYST_PROMPT constant (which is the tell-tale shape of the bug).
    offending = re.findall(
        r'"prompt"\s*:\s*[A-Z_]+_ANALYST_PROMPT',
        chat_deepagent_source,
    )
    assert not offending, (
        f"Found SubAgent spec(s) using wrong key 'prompt' instead of 'system_prompt': {offending}. "
        f"deepagents SubAgent TypedDict requires 'system_prompt'."
    )


def test_every_crypto_spec_uses_system_prompt_key(chat_deepagent_source: str) -> None:
    """Each of the 6 crypto agent specs must use the ``system_prompt`` key."""
    for const in (
        "DEFILLAMA_ANALYST_PROMPT",
        "SENTIMENT_ANALYST_PROMPT",
        "NEWS_ANALYST_PROMPT",
        "SMART_CONTRACT_ANALYST_PROMPT",
        "TOKENOMICS_ANALYST_PROMPT",
        "YIELD_OPTIMIZER_PROMPT",
    ):
        pattern = rf'"system_prompt"\s*:\s*{const}\b'
        assert re.search(pattern, chat_deepagent_source), (
            f"Crypto spec using {const} must be wired with key 'system_prompt'"
        )


# ---------------------------------------------------------------------------
# AC10 / NFR-CS4: each spec gets a *fresh* middleware list via the factory
# ---------------------------------------------------------------------------

def test_each_crypto_spec_uses_fresh_middleware_factory(
    chat_deepagent_source: str,
) -> None:
    """NFR-CS4: mutable middleware instances must NOT be shared across sub-agent
    specs. Every crypto spec's ``middleware`` value must be a *call* to the
    factory ``_build_gp_middleware()``, not a bare variable reference.
    """
    spec_name_constants = [
        "DEFILLAMA_ANALYST_NAME",
        "SENTIMENT_ANALYST_NAME",
        "NEWS_ANALYST_NAME",
        "SMART_CONTRACT_ANALYST_NAME",
        "TOKENOMICS_ANALYST_NAME",
        "YIELD_OPTIMIZER_NAME",
    ]
    for name_const in spec_name_constants:
        # Find the dict literal that starts with "name": <name_const>
        dict_match = re.search(
            rf'"name"\s*:\s*{name_const}\b[^}}]*?"middleware"\s*:\s*(_build_gp_middleware\(\)|[A-Za-z_][A-Za-z_0-9]*)',
            chat_deepagent_source,
            re.DOTALL,
        )
        assert dict_match, f"Could not locate spec dict for {name_const}"
        middleware_value = dict_match.group(1)
        assert middleware_value == "_build_gp_middleware()", (
            f"Spec for {name_const} uses '{middleware_value}' for middleware — "
            f"must be a fresh factory call '_build_gp_middleware()' to prevent "
            f"cross-agent state leakage (NFR-CS4)."
        )


# ---------------------------------------------------------------------------
# AC3 (real): each spec uses _scope_tools with the correct ALLOWED_TOOLS const
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scope_var,allowed_const,agent_const",
    [
        ("defillama_tools", "DEFILLAMA_ALLOWED_TOOLS", "DEFILLAMA_ANALYST_NAME"),
        ("sentiment_tools", "SENTIMENT_ALLOWED_TOOLS", "SENTIMENT_ANALYST_NAME"),
        ("news_tools", "NEWS_ALLOWED_TOOLS", "NEWS_ANALYST_NAME"),
        ("smart_contract_tools", "SMART_CONTRACT_ALLOWED_TOOLS", "SMART_CONTRACT_ANALYST_NAME"),
        ("tokenomics_tools", "TOKENOMICS_ALLOWED_TOOLS", "TOKENOMICS_ANALYST_NAME"),
        ("yield_optimizer_tools", "YIELD_OPTIMIZER_ALLOWED_TOOLS", "YIELD_OPTIMIZER_NAME"),
    ],
)
def test_scope_tools_uses_correct_allowed_const(
    chat_deepagent_source: str,
    scope_var: str,
    allowed_const: str,
    agent_const: str,
) -> None:
    """AC3: production code calls _scope_tools(<ALLOWED_TOOLS>, <NAME>) for each agent."""
    pattern = rf"{scope_var}\s*=\s*_scope_tools\(\s*{allowed_const}\s*,\s*{agent_const}\s*\)"
    assert re.search(pattern, chat_deepagent_source), (
        f"Expected '{scope_var} = _scope_tools({allowed_const}, {agent_const})' in production code"
    )


# ---------------------------------------------------------------------------
# P3: chainlens guard is present before spec wiring
# ---------------------------------------------------------------------------

def test_chainlens_missing_guard_is_present(chat_deepagent_source: str) -> None:
    """P3: if chainlens_deep_research is absent from the registry (feature flag off),
    an ERROR-level log must fire so the silent prompt/tool mismatch is noticed.
    """
    # The guard should log at error level and mention chainlens_deep_research.
    assert re.search(
        r'chainlens_deep_research\b.*?NOT in the tool registry',
        chat_deepagent_source,
        re.DOTALL,
    ), "Expected chainlens registry-absence guard in chat_deepagent.py"
    assert re.search(
        r"_perf_log\.error\s*\(\s*[\"']\[create_agent\][^\"']*chainlens",
        chat_deepagent_source,
    ), "Expected _perf_log.error(...) for missing chainlens"


# ---------------------------------------------------------------------------
# Prompt fidelity: every tool named in a prompt is in that agent's scope
# ---------------------------------------------------------------------------

_CRYPTO_AGENTS = [
    pytest.param(
        DEFILLAMA_ANALYST_NAME, DEFILLAMA_ANALYST_PROMPT, DEFILLAMA_ALLOWED_TOOLS, id="defillama"
    ),
    pytest.param(
        SENTIMENT_ANALYST_NAME, SENTIMENT_ANALYST_PROMPT, SENTIMENT_ALLOWED_TOOLS, id="sentiment"
    ),
    pytest.param(NEWS_ANALYST_NAME, NEWS_ANALYST_PROMPT, NEWS_ALLOWED_TOOLS, id="news"),
    pytest.param(
        SMART_CONTRACT_ANALYST_NAME,
        SMART_CONTRACT_ANALYST_PROMPT,
        SMART_CONTRACT_ALLOWED_TOOLS,
        id="smart_contract",
    ),
    pytest.param(
        TOKENOMICS_ANALYST_NAME,
        TOKENOMICS_ANALYST_PROMPT,
        TOKENOMICS_ALLOWED_TOOLS,
        id="tokenomics",
    ),
    pytest.param(
        YIELD_OPTIMIZER_NAME,
        YIELD_OPTIMIZER_PROMPT,
        YIELD_OPTIMIZER_ALLOWED_TOOLS,
        id="yield_optimizer",
    ),
]


@pytest.mark.parametrize("agent_name,prompt,allowed", _CRYPTO_AGENTS)
def test_prompt_only_references_scoped_tools(
    agent_name: str, prompt: str, allowed: tuple[str, ...]
) -> None:
    """Every tool named in a prompt's 'Use/Call <tool>' lines must be in the agent's scope."""
    # Matches both "Use get_foo" (defillama/sentiment/news/smart_contract/tokenomics pattern)
    # and "Call get_foo" / "call get_foo" (yield_optimizer pattern).
    mentioned = set(re.findall(
        r"\b(?:Use|Call|call)\s+(get_[a-z_]+|check_[a-z_]+|chainlens_deep_research)\b",
        prompt,
    ))
    allowed_set = set(allowed)
    unscoped = mentioned - allowed_set
    assert not unscoped, (
        f"{agent_name} prompt references tools that are NOT in its scope: {unscoped}. "
        f"Scoped tools: {sorted(allowed_set)}"
    )
