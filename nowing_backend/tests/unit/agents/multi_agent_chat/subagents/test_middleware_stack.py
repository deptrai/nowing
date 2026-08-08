"""Tests for the shared subagent middleware stack composition."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.middleware.resilience import (
    ResilienceMiddlewares,
    build_resilience_middlewares,
)
from app.agents.chat.multi_agent_chat.subagents.middleware_stack import (
    build_subagent_middleware_stack,
)


def _resilience() -> ResilienceMiddlewares:
    return build_resilience_middlewares(AgentFeatureFlags())


def test_citation_slot_is_present_and_non_none():
    stack = build_subagent_middleware_stack(
        resilience=_resilience(),
        flags=AgentFeatureFlags(),
    )
    assert "citation" in stack
    assert stack["citation"] is not None


def test_citation_slot_present_even_without_flags():
    stack = build_subagent_middleware_stack(
        resilience=_resilience(),
        flags=None,
    )
    # citation is unconditional — it does not depend on feature flags.
    assert "citation" in stack
    assert stack["citation"] is not None
