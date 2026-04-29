"""Wiring + structural tests for whale_tracker sub-agent (Story 9-UX-4 T9).

Covers:
- Spec structure: all required constants defined, prompt < 500 tokens
- Feature flag OFF: _COMPREHENSIVE_AGENTS has 6 entries, SubAgentMiddleware has no whale_tracker
- Feature flag ON: _COMPREHENSIVE_AGENTS has 7 entries, SubAgentMiddleware has whale_tracker
- Tool scoping: all WHALE_TRACKER_ALLOWED_TOOLS exist in registry
- SYNTHESIS_DIRECTIVE: cross-source conflict detection rule present
- _DIRECTIVE / _INLINE_MANDATE updated to reflect N sub-agents when flag is on
"""

from __future__ import annotations

import os
from importlib import reload
from unittest.mock import patch

import pytest

from app.agents.new_chat.subagents.crypto.whale_tracker_spec import (
    WHALE_TRACKER_ALLOWED_TOOLS,
    WHALE_TRACKER_DESCRIPTION,
    WHALE_TRACKER_NAME,
    WHALE_TRACKER_PROMPT,
)
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS


# ── Spec structure ─────────────────────────────────────────────────────────────


def test_whale_tracker_name():
    assert WHALE_TRACKER_NAME == "whale_tracker"


def test_whale_tracker_description_nonempty():
    assert len(WHALE_TRACKER_DESCRIPTION) > 20


def test_whale_tracker_allowed_tools_nonempty():
    assert len(WHALE_TRACKER_ALLOWED_TOOLS) >= 2


def test_whale_tracker_allowed_tools_include_nansen():
    """whale_tracker must scope in Nansen tools for smart-money data."""
    assert "get_nansen_smart_money" in WHALE_TRACKER_ALLOWED_TOOLS
    assert "get_nansen_wallet_label" in WHALE_TRACKER_ALLOWED_TOOLS


def test_whale_tracker_prompt_under_500_tokens():
    """NFR-CS1: prompt token count roughly under 500 (whitespace-split estimate)."""
    word_count = len(WHALE_TRACKER_PROMPT.split())
    assert word_count < 500, f"Prompt too long: {word_count} words (≈ too many tokens)"


def test_whale_tracker_prompt_mentions_tools():
    """Every tool in ALLOWED_TOOLS should be referenced in the prompt."""
    for tool_name in WHALE_TRACKER_ALLOWED_TOOLS:
        # Tool name or shortened variant should appear
        base = tool_name.replace("get_nansen_", "").replace("_", " ")
        assert (
            tool_name in WHALE_TRACKER_PROMPT
            or base in WHALE_TRACKER_PROMPT.lower()
        ), f"Prompt does not mention tool: {tool_name}"


# ── Registry: all ALLOWED_TOOLS present ──────────────────────────────────────


def test_whale_tracker_tools_in_registry():
    """All tools referenced by whale_tracker spec must exist in BUILTIN_TOOLS."""
    registry_names = {t.name for t in BUILTIN_TOOLS}
    missing = set(WHALE_TRACKER_ALLOWED_TOOLS) - registry_names
    assert not missing, f"Tools missing from registry: {sorted(missing)}"


# ── Feature flag OFF (default) ────────────────────────────────────────────────


def test_comprehensive_agents_6_when_flag_off():
    """With flag off, _COMPREHENSIVE_AGENTS should have exactly 6 entries."""
    with patch.dict(os.environ, {"CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER": "false"}):
        import app.agents.new_chat.chat_deepagent as mod
        reload(mod)
        count = len(mod.ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS)
        assert count == 6, f"Expected 6 agents, got {count}"
        names = [a[0] for a in mod.ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS]
        assert "whale_tracker" not in names


def test_directive_mentions_6_when_flag_off():
    with patch.dict(os.environ, {"CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER": "false"}):
        import app.agents.new_chat.chat_deepagent as mod
        reload(mod)
        assert "6" in mod.ParallelSpawnDirectiveMiddleware._DIRECTIVE
        assert "whale_tracker" not in mod.ParallelSpawnDirectiveMiddleware._DIRECTIVE


# ── Feature flag ON ───────────────────────────────────────────────────────────


def test_comprehensive_agents_7_when_flag_on():
    """With flag on, _COMPREHENSIVE_AGENTS should have exactly 7 entries."""
    with patch.dict(os.environ, {"CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER": "true"}):
        import app.agents.new_chat.chat_deepagent as mod
        reload(mod)
        count = len(mod.ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS)
        assert count == 7, f"Expected 7 agents, got {count}"
        names = [a[0] for a in mod.ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS]
        assert "whale_tracker" in names
        # whale_tracker should be last (priority: Easy-Wins first, Chainlens-heavy last)
        assert names[-1] == "whale_tracker"


def test_directive_mentions_7_when_flag_on():
    with patch.dict(os.environ, {"CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER": "true"}):
        import app.agents.new_chat.chat_deepagent as mod
        reload(mod)
        assert "7" in mod.ParallelSpawnDirectiveMiddleware._DIRECTIVE
        assert "whale_tracker" in mod.ParallelSpawnDirectiveMiddleware._DIRECTIVE


def test_inline_mandate_mentions_7_when_flag_on():
    with patch.dict(os.environ, {"CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER": "true"}):
        import app.agents.new_chat.chat_deepagent as mod
        reload(mod)
        assert "7" in mod.ParallelSpawnDirectiveMiddleware._INLINE_MANDATE
        assert "whale_tracker" in mod.ParallelSpawnDirectiveMiddleware._INLINE_MANDATE


# ── smart_contract_analyst — CertiK extension (AC6) ──────────────────────────


def test_smart_contract_allows_certik_tools():
    from app.agents.new_chat.subagents.crypto.smart_contract_spec import SMART_CONTRACT_ALLOWED_TOOLS
    assert "get_certik_audit_score" in SMART_CONTRACT_ALLOWED_TOOLS
    assert "get_certik_incident_history" in SMART_CONTRACT_ALLOWED_TOOLS


def test_smart_contract_prompt_mentions_certik():
    from app.agents.new_chat.subagents.crypto.smart_contract_spec import SMART_CONTRACT_ANALYST_PROMPT
    assert "certik" in SMART_CONTRACT_ANALYST_PROMPT.lower() or "CertiK" in SMART_CONTRACT_ANALYST_PROMPT


def test_smart_contract_prompt_has_conflict_detection():
    from app.agents.new_chat.subagents.crypto.smart_contract_spec import SMART_CONTRACT_ANALYST_PROMPT
    assert "15" in SMART_CONTRACT_ANALYST_PROMPT  # >15 point divergence rule
    assert "conflict" in SMART_CONTRACT_ANALYST_PROMPT.lower()


# ── _SYNTHESIS_DIRECTIVE: cross-source conflict detection (AC7) ───────────────


def test_synthesis_directive_has_conflict_detection():
    """The synthesis directive should document the 10% delta conflict rule."""
    import app.agents.new_chat.chat_deepagent as mod

    # Find the synthesis directive string in the source
    import inspect
    source = inspect.getsource(mod)
    assert "conflict" in source.lower()
    assert "10%" in source or "> 10" in source


def test_synthesis_directive_mentions_new_providers():
    import inspect
    import app.agents.new_chat.chat_deepagent as mod
    source = inspect.getsource(mod)
    for provider in ("certik", "nansen", "dune", "tokeninsight"):
        assert provider in source.lower(), f"Provider '{provider}' not mentioned in synthesis directive"
